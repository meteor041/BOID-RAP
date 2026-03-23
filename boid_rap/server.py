from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from boid_rap.config import load_dotenv
from boid_rap.database import initialize_database
from boid_rap.domain import ObjectType
from boid_rap.llm import MockLLMProvider, OpenAIResponsesProvider
from boid_rap.object_data import MockCommodityDataProvider, MockCompanyDataProvider, MockStockDataProvider
from boid_rap.repositories import (
    AuditLogRepository,
    ModelRepository,
    ReportRepository,
    ResearchJobRepository,
    RetrievalResultRepository,
    SessionRepository,
    TokenRepository,
    UserRepository,
)
from boid_rap.retrieval import HttpRetrievalProvider, MockRetrievalProvider, RetrievalRegistry, TavilyRetrievalProvider
from boid_rap.services import AuditService, AuthService, ModelService, ResearchJobRunner, ResearchService


load_dotenv()


DB_PATH = initialize_database()
audit_service = AuditService(AuditLogRepository(DB_PATH))
auth_service = AuthService(UserRepository(DB_PATH), TokenRepository(DB_PATH), audit_service)
model_service = ModelService(ModelRepository(DB_PATH), audit_service)
http_retrieval_enabled = os.getenv("BOID_RAP_HTTP_RETRIEVAL_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
tavily_retrieval_enabled = os.getenv("BOID_RAP_TAVILY_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
http_retrieval_request_template = json.loads(os.getenv("BOID_RAP_HTTP_RETRIEVAL_REQUEST_TEMPLATE", "null"))
http_retrieval_request_headers = json.loads(os.getenv("BOID_RAP_HTTP_RETRIEVAL_REQUEST_HEADERS", "{}"))
http_retrieval_response_mapping = json.loads(os.getenv("BOID_RAP_HTTP_RETRIEVAL_RESPONSE_MAPPING", "{}"))
openai_llm_enabled = os.getenv("BOID_RAP_OPENAI_LLM_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
llm_provider = (
    OpenAIResponsesProvider(
        api_key=os.getenv("BOID_RAP_OPENAI_API_KEY"),
        enabled=openai_llm_enabled,
        timeout=float(os.getenv("BOID_RAP_OPENAI_TIMEOUT", "20")),
        base_url=os.getenv("BOID_RAP_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        endpoint=os.getenv("BOID_RAP_OPENAI_ENDPOINT") or None,
        model=os.getenv("BOID_RAP_OPENAI_MODEL", "gpt-5-mini"),
    )
    if openai_llm_enabled or os.getenv("BOID_RAP_OPENAI_API_KEY")
    else MockLLMProvider()
)
retrieval_registry = RetrievalRegistry(
    [
        MockRetrievalProvider(),
        TavilyRetrievalProvider(
            api_key=os.getenv("BOID_RAP_TAVILY_API_KEY"),
            enabled=tavily_retrieval_enabled,
            timeout=float(os.getenv("BOID_RAP_TAVILY_TIMEOUT", "10")),
            endpoint=os.getenv("BOID_RAP_TAVILY_ENDPOINT", "https://api.tavily.com/search"),
            max_results=int(os.getenv("BOID_RAP_TAVILY_MAX_RESULTS", "5")),
            include_raw_content=os.getenv("BOID_RAP_TAVILY_INCLUDE_RAW_CONTENT", "text"),
            include_favicon=os.getenv("BOID_RAP_TAVILY_INCLUDE_FAVICON", "true").lower() in {"1", "true", "yes", "on"},
            search_depth=os.getenv("BOID_RAP_TAVILY_SEARCH_DEPTH", "basic"),
        ),
        HttpRetrievalProvider(
            endpoint=os.getenv("BOID_RAP_HTTP_RETRIEVAL_ENDPOINT", "https://api.example.com/deepsearch"),
            api_key=os.getenv("BOID_RAP_HTTP_RETRIEVAL_API_KEY"),
            enabled=http_retrieval_enabled,
            timeout=float(os.getenv("BOID_RAP_HTTP_RETRIEVAL_TIMEOUT", "10")),
            method=os.getenv("BOID_RAP_HTTP_RETRIEVAL_METHOD", "POST"),
            api_key_header=os.getenv("BOID_RAP_HTTP_RETRIEVAL_API_KEY_HEADER", "Authorization"),
            request_body_template=http_retrieval_request_template,
            request_headers=http_retrieval_request_headers,
            response_mapping=http_retrieval_response_mapping,
        ),
    ],
    default_provider="mock_deepsearch",
)
research_service = ResearchService(
    model_service,
    SessionRepository(DB_PATH),
    ReportRepository(DB_PATH),
    ResearchJobRepository(DB_PATH),
    RetrievalResultRepository(DB_PATH),
    audit_service,
    retrieval_cache_ttl_seconds=int(os.getenv("BOID_RAP_RETRIEVAL_CACHE_TTL_SECONDS", "3600")),
    llm_provider=llm_provider,
    company_data_provider=MockCompanyDataProvider(),
    stock_data_provider=MockStockDataProvider(),
    commodity_data_provider=MockCommodityDataProvider(),
    retrieval_registry=retrieval_registry,
)
job_runner = ResearchJobRunner(research_service)
CORS_ALLOW_ORIGIN = os.getenv("BOID_RAP_CORS_ALLOW_ORIGIN", "*")
CORS_ALLOW_METHODS = "GET, POST, PATCH, DELETE, OPTIONS"
CORS_ALLOW_HEADERS = "Authorization, Content-Type, X-Auth-Token"


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "BOID-RAP/0.3"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/health":
                self._json_response({"status": "ok", "database": str(Path(DB_PATH))})
                return
            if path == "/api/meta/object-types":
                self._json_response({"items": [item.value for item in ObjectType]})
                return
            if path == "/api/meta/retrieval-providers":
                self._json_response(research_service.list_retrieval_providers())
                return
            if path == "/api/meta/search-insights":
                user = self._require_user()
                limit = int(query.get("limit", ["10"])[0])
                self._validate_positive_int("limit", limit, minimum=1)
                self._json_response(research_service.get_search_insights(user, limit=limit))
                return
            if path == "/api/models":
                user = self._require_user()
                object_type = query.get("object_type", [None])[0]
                self._validate_object_type(object_type, allow_none=True)
                self._json_response(
                    {"items": model_service.list_available_models(user.role.value, object_type)}
                )
                return
            if path == "/api/admin/models":
                user = self._require_user()
                auth_service.require_admin(user)
                self._json_response({"items": model_service.list_models()})
                return
            if path == "/api/admin/users":
                user = self._require_user()
                auth_service.require_admin(user)
                self._json_response({"items": auth_service.list_users()})
                return
            if path.startswith("/api/admin/users/"):
                user = self._require_user()
                auth_service.require_admin(user)
                user_id = path.removeprefix("/api/admin/users/")
                self._json_response(auth_service.get_user(user_id))
                return
            if path == "/api/admin/audit-logs":
                user = self._require_user()
                auth_service.require_admin(user)
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
                created_from = query.get("created_from", [None])[0]
                created_to = query.get("created_to", [None])[0]
                self._validate_positive_int("limit", limit, minimum=1)
                self._validate_positive_int("offset", offset, minimum=0)
                self._validate_iso_datetime(created_from, "created_from", allow_none=True)
                self._validate_iso_datetime(created_to, "created_to", allow_none=True)
                self._json_response(
                    audit_service.list_logs(
                        limit=limit,
                        offset=offset,
                        actor_user_id=query.get("actor_user_id", [None])[0],
                        action=query.get("action", [None])[0],
                        resource_type=query.get("resource_type", [None])[0],
                        created_from=created_from,
                        created_to=created_to,
                    )
                )
                return
            if path == "/api/reports":
                user = self._require_user()
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
                created_from = query.get("created_from", [None])[0]
                created_to = query.get("created_to", [None])[0]
                self._validate_positive_int("limit", limit, minimum=1)
                self._validate_positive_int("offset", offset, minimum=0)
                self._validate_iso_datetime(created_from, "created_from", allow_none=True)
                self._validate_iso_datetime(created_to, "created_to", allow_none=True)
                self._json_response(
                    research_service.list_reports(
                        user,
                        limit=limit,
                        offset=offset,
                        created_from=created_from,
                        created_to=created_to,
                        keyword=query.get("keyword", [None])[0],
                    )
                )
                return
            if path.startswith("/api/reports/") and path.endswith("/profile"):
                user = self._require_user()
                report_id = path.removesuffix("/profile").removeprefix("/api/reports/")
                self._json_response(research_service.get_report_profile(report_id, user))
                return
            if path.startswith("/api/reports/") and not path.endswith("/markdown"):
                user = self._require_user()
                report_id = path.removeprefix("/api/reports/")
                self._json_response(
                    research_service.get_report(
                        report_id,
                        user,
                        keyword=query.get("keyword", [None])[0],
                    )
                )
                return
            if path.startswith("/api/reports/") and path.endswith("/markdown"):
                user = self._require_user()
                report_id = path.removesuffix("/markdown").removeprefix("/api/reports/")
                exported = research_service.export_report_markdown(
                    report_id,
                    user,
                    keyword=query.get("keyword", [None])[0],
                )
                self._text_response(
                    exported["markdown"],
                    content_type=exported["content_type"],
                    filename=exported["filename"],
                )
                return
            if path == "/api/research/jobs":
                user = self._require_user()
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
                session_id = query.get("session_id", [None])[0]
                status = query.get("status", [None])[0]
                self._validate_positive_int("limit", limit, minimum=1)
                self._validate_positive_int("offset", offset, minimum=0)
                self._validate_job_status(status, allow_none=True)
                self._json_response(
                    research_service.list_jobs(
                        user,
                        limit=limit,
                        offset=offset,
                        session_id=session_id,
                        status=status,
                    )
                )
                return
            if path.startswith("/api/research/jobs/") and path.endswith("/retrieval"):
                user = self._require_user()
                job_id = path.removesuffix("/retrieval").removeprefix("/api/research/jobs/")
                self._json_response(
                    research_service.get_job_retrieval_result_filtered(
                        job_id,
                        user,
                        keyword=query.get("keyword", [None])[0],
                    )
                )
                return
            if path.startswith("/api/research/jobs/"):
                user = self._require_user()
                job_id = path.removeprefix("/api/research/jobs/")
                self._json_response(research_service.get_job(job_id, user))
                return
            if path == "/api/research/sessions":
                user = self._require_user()
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
                object_type = query.get("object_type", [None])[0]
                model_id = query.get("model_id", [None])[0]
                status = query.get("status", [None])[0]
                created_from = query.get("created_from", [None])[0]
                created_to = query.get("created_to", [None])[0]
                self._validate_positive_int("limit", limit, minimum=1)
                self._validate_positive_int("offset", offset, minimum=0)
                self._validate_object_type(object_type, allow_none=True)
                self._validate_session_status(status, allow_none=True)
                self._validate_iso_datetime(created_from, "created_from", allow_none=True)
                self._validate_iso_datetime(created_to, "created_to", allow_none=True)
                self._json_response(
                    research_service.list_sessions(
                        user,
                        limit=limit,
                        offset=offset,
                        object_type=object_type,
                        model_id=model_id,
                        status=status,
                        created_from=created_from,
                        created_to=created_to,
                    )
                )
                return
            if path.startswith("/api/research/sessions/") and path.endswith("/retrievals"):
                user = self._require_user()
                session_id = path.removesuffix("/retrievals").removeprefix("/api/research/sessions/")
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
                provider = query.get("provider", [None])[0]
                cache_hit_raw = query.get("cache_hit", [None])[0]
                created_from = query.get("created_from", [None])[0]
                created_to = query.get("created_to", [None])[0]
                keyword = query.get("keyword", [None])[0]
                self._validate_positive_int("limit", limit, minimum=1)
                self._validate_positive_int("offset", offset, minimum=0)
                self._validate_iso_datetime(created_from, "created_from", allow_none=True)
                self._validate_iso_datetime(created_to, "created_to", allow_none=True)
                self._json_response(
                    research_service.list_session_retrieval_results(
                        session_id,
                        user,
                        limit=limit,
                        offset=offset,
                        provider=provider,
                        cache_hit=self._parse_optional_bool(cache_hit_raw, "cache_hit"),
                        created_from=created_from,
                        created_to=created_to,
                        keyword=keyword,
                    )
                )
                return
            if path.startswith("/api/research/sessions/"):
                user = self._require_user()
                session_id = path.removeprefix("/api/research/sessions/")
                self._json_response(research_service.get_session(session_id, user))
                return

            self._json_response({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except PermissionError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.FORBIDDEN)

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            payload = self._read_json_body()

            if path == "/api/auth/register":
                actor = self._optional_user()
                if payload.get("role") == "admin":
                    if actor is None:
                        raise PermissionError("admin permission required")
                    auth_service.require_admin(actor)
                self._json_response(
                    auth_service.register_user(payload, actor),
                    status=HTTPStatus.CREATED,
                )
                return
            if path == "/api/auth/login":
                self._validate_required_fields(payload, ["username", "password"])
                self._json_response(auth_service.login(payload))
                return
            if path == "/api/auth/logout":
                user = self._require_user()
                token = self._extract_token()
                auth_service.logout(token, user)
                self._json_response({"status": "ok"})
                return
            if path == "/api/auth/refresh":
                user = self._require_user()
                token = self._extract_token()
                self._json_response(auth_service.refresh_token(token, user))
                return
            if path == "/api/auth/change-password":
                user = self._require_user()
                self._validate_required_fields(payload, ["current_password", "new_password"])
                auth_service.change_password(user, payload)
                self._json_response({"status": "ok"})
                return
            if path.startswith("/api/admin/users/") and path.endswith("/reset-password"):
                user = self._require_user()
                auth_service.require_admin(user)
                self._validate_required_fields(payload, ["new_password"])
                user_id = path.removesuffix("/reset-password").removeprefix("/api/admin/users/")
                auth_service.admin_reset_password(user_id, payload["new_password"], user)
                self._json_response({"status": "ok"})
                return
            if path == "/api/admin/models":
                user = self._require_user()
                auth_service.require_admin(user)
                self._validate_model_payload(payload, is_update=False)
                self._json_response(
                    model_service.create_model(payload, user),
                    status=HTTPStatus.CREATED,
                )
                return
            if path == "/api/research/sessions":
                user = self._require_user()
                self._validate_research_payload(payload)
                payload["user_id"] = user.id
                self._json_response(
                    research_service.create_session(payload, user),
                    status=HTTPStatus.CREATED,
                )
                return
            if path.startswith("/api/reports/") and path.endswith("/follow-up"):
                user = self._require_user()
                self._validate_required_fields(payload, ["question"])
                report_id = path.removesuffix("/follow-up").removeprefix("/api/reports/")
                paragraph_index = payload.get("paragraph_index")
                if paragraph_index is not None:
                    if not isinstance(paragraph_index, int):
                        raise ValueError("paragraph_index must be an integer")
                    self._validate_positive_int("paragraph_index", paragraph_index, minimum=0)
                self._json_response(
                    research_service.answer_report_follow_up(
                        report_id,
                        str(payload["question"]),
                        user,
                        paragraph_index=paragraph_index,
                        keyword=str(payload["keyword"]).strip() if payload.get("keyword") is not None else None,
                    ),
                    status=HTTPStatus.CREATED,
                )
                return
            if path.startswith("/api/research/sessions/") and path.endswith("/messages"):
                user = self._require_user()
                self._validate_required_fields(payload, ["role", "content"])
                session_id = path.removesuffix("/messages").removeprefix("/api/research/sessions/")
                self._json_response(research_service.add_message(session_id, payload, user))
                return
            if path.startswith("/api/research/sessions/") and path.endswith("/run"):
                user = self._require_user()
                session_id = path.removesuffix("/run").removeprefix("/api/research/sessions/")
                force_refresh = bool(payload.get("force_refresh", False))
                if "force_refresh" in payload and not isinstance(payload["force_refresh"], bool):
                    raise ValueError("force_refresh must be a boolean")
                job = research_service.create_job(session_id, user, force_refresh=force_refresh)
                job_runner.enqueue(job["id"])
                self._json_response({"job": job}, status=HTTPStatus.ACCEPTED)
                return
            if path.startswith("/api/research/jobs/") and path.endswith("/cancel"):
                user = self._require_user()
                job_id = path.removesuffix("/cancel").removeprefix("/api/research/jobs/")
                self._json_response({"job": research_service.cancel_job(job_id, user)})
                return
            if path.startswith("/api/research/jobs/") and path.endswith("/retry"):
                user = self._require_user()
                job_id = path.removesuffix("/retry").removeprefix("/api/research/jobs/")
                job = research_service.retry_job(job_id, user)
                job_runner.enqueue(job["id"])
                self._json_response({"job": job}, status=HTTPStatus.ACCEPTED)
                return

            self._json_response({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except PermissionError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.FORBIDDEN)

    def do_PATCH(self) -> None:
        try:
            path = urlparse(self.path).path
            payload = self._read_json_body()

            if path.startswith("/api/admin/models/"):
                user = self._require_user()
                auth_service.require_admin(user)
                model_id = path.removeprefix("/api/admin/models/")
                self._validate_model_payload(payload, is_update=True)
                self._json_response(model_service.update_model(model_id, payload, user))
                return
            if path.startswith("/api/admin/users/") and path.endswith("/status"):
                user = self._require_user()
                auth_service.require_admin(user)
                user_id = path.removesuffix("/status").removeprefix("/api/admin/users/")
                self._validate_required_fields(payload, ["enabled"])
                self._json_response(auth_service.update_user_status(user_id, bool(payload["enabled"]), user))
                return

            self._json_response({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except PermissionError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.FORBIDDEN)

    def do_DELETE(self) -> None:
        try:
            path = urlparse(self.path).path
            if path.startswith("/api/admin/models/"):
                user = self._require_user()
                auth_service.require_admin(user)
                model_id = path.removeprefix("/api/admin/models/")
                model_service.delete_model(model_id, user)
                self._json_response({"status": "ok"})
                return
            if path.startswith("/api/admin/users/"):
                user = self._require_user()
                auth_service.require_admin(user)
                user_id = path.removeprefix("/api/admin/users/")
                auth_service.soft_delete_user(user_id, user)
                self._json_response({"status": "ok"})
                return

            self._json_response({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except PermissionError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.FORBIDDEN)

    def log_message(self, format: str, *args) -> None:
        return

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _validate_required_fields(self, payload: dict, fields: list[str]) -> None:
        missing = [field for field in fields if field not in payload]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

    def _validate_object_type(self, object_type: str | None, allow_none: bool = False) -> None:
        if allow_none and object_type is None:
            return
        if object_type not in {item.value for item in ObjectType}:
            raise ValueError("invalid object_type")

    def _validate_model_payload(self, payload: dict, is_update: bool) -> None:
        if not is_update:
            self._validate_required_fields(payload, ["name", "provider"])
        if "recommended_for" in payload:
            if not isinstance(payload["recommended_for"], list):
                raise ValueError("recommended_for must be a list")
            invalid_types = [item for item in payload["recommended_for"] if item not in {obj.value for obj in ObjectType}]
            if invalid_types:
                raise ValueError(f"invalid recommended_for values: {', '.join(invalid_types)}")
        if "permissions" in payload:
            if not isinstance(payload["permissions"], list):
                raise ValueError("permissions must be a list")
            invalid_permissions = [item for item in payload["permissions"] if item not in {"admin", "user", "all"}]
            if invalid_permissions:
                raise ValueError(f"invalid permissions: {', '.join(invalid_permissions)}")
        if "parameters" in payload and not isinstance(payload["parameters"], dict):
            raise ValueError("parameters must be an object")

    def _validate_research_payload(self, payload: dict) -> None:
        self._validate_required_fields(payload, ["object_name", "object_type", "model_id"])
        self._validate_object_type(payload["object_type"])
        if not str(payload["object_name"]).strip():
            raise ValueError("object_name cannot be empty")
        if "retrieval_provider" in payload and payload["retrieval_provider"] is not None:
            if not str(payload["retrieval_provider"]).strip():
                raise ValueError("retrieval_provider cannot be empty")

    def _validate_session_status(self, status: str | None, allow_none: bool = False) -> None:
        if allow_none and status is None:
            return
        if status not in {"draft", "running", "completed"}:
            raise ValueError("invalid status")

    def _validate_job_status(self, status: str | None, allow_none: bool = False) -> None:
        if allow_none and status is None:
            return
        if status not in {"queued", "running", "completed", "failed", "cancelled"}:
            raise ValueError("invalid job status")

    def _validate_positive_int(self, name: str, value: int, minimum: int = 0) -> None:
        if value < minimum:
            raise ValueError(f"{name} must be >= {minimum}")

    def _validate_iso_datetime(self, value: str | None, name: str, allow_none: bool = False) -> None:
        if allow_none and value is None:
            return
        try:
            datetime.fromisoformat(value)  # type: ignore[arg-type]
        except Exception as exc:
            raise ValueError(f"{name} must be an ISO datetime") from exc

    def _parse_optional_bool(self, value: str | None, name: str) -> bool | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"{name} must be a boolean")

    def _optional_user(self):
        token = self._extract_token()
        if not token:
            return None
        return auth_service.authenticate(token)

    def _require_user(self):
        return auth_service.authenticate(self._extract_token())

    def _extract_token(self) -> str | None:
        authorization = self.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            return authorization.removeprefix("Bearer ").strip()
        return self.headers.get("X-Auth-Token")

    def _json_response(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text_response(
        self,
        content: str,
        content_type: str = "text/plain; charset=utf-8",
        status: HTTPStatus = HTTPStatus.OK,
        filename: str | None = None,
    ) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", content_type)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", CORS_ALLOW_METHODS)
        self.send_header("Access-Control-Allow-Headers", CORS_ALLOW_HEADERS)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"BOID-RAP server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
