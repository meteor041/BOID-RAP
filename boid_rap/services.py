from __future__ import annotations

import hashlib
import json
import hmac
import os
import re
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from secrets import token_hex

from boid_rap.domain import (
    AuditLog,
    ModelConfig,
    ObjectType,
    Report,
    ResearchJob,
    ResearchJobStatus,
    ResearchMessage,
    ResearchSession,
    SessionStatus,
    User,
    UserRole,
    WorkflowEvent,
    utc_now,
)
from boid_rap.llm import FollowUpDraft, LLMProvider, LLMProviderError, MockLLMProvider, ReportDraft
from boid_rap.object_data import (
    CommodityDataProvider,
    CommodityResearchData,
    CompanyDataProvider,
    CompanyResearchData,
    MockCommodityDataProvider,
    MockCompanyDataProvider,
    MockStockDataProvider,
    StockDataProvider,
    StockResearchData,
)
from boid_rap.retrieval import (
    MockRetrievalProvider,
    RetrievalBundle,
    RetrievalDocument,
    RetrievalProvider,
    RetrievalProviderError,
    RetrievalRegistry,
)
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


class AuditService:
    def __init__(self, repo: AuditLogRepository) -> None:
        self.repo = repo

    def log(self, actor_user_id: str | None, action: str, resource_type: str, resource_id: str, detail: str = "") -> None:
        self.repo.save(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
            )
        )

    def list_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        actor_user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> dict:
        total = self.repo.count_all(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            created_from=created_from,
            created_to=created_to,
        )
        items = self.repo.list_all(
            limit=limit,
            offset=offset,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            created_from=created_from,
            created_to=created_to,
        )
        return {
            "items": [item.to_dict() for item in items],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
        }


class AuthService:
    TOKEN_TTL_HOURS = 12

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: TokenRepository,
        audit_service: AuditService,
    ) -> None:
        self.user_repo = user_repo
        self.token_repo = token_repo
        self.audit_service = audit_service
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        if self.user_repo.list_all():
            return

        defaults = [
            ("admin", "admin123", UserRole.ADMIN),
            ("analyst", "analyst123", UserRole.USER),
        ]
        for username, password, role in defaults:
            user = self.user_repo.save(
                User(
                    username=username,
                    password_hash=self.hash_password(password),
                    role=role,
                )
            )
            self.audit_service.log(None, "user.seeded", "user", user.id, username)

    def register_user(self, payload: dict, actor: User | None = None) -> dict:
        username = payload["username"].strip()
        password = payload["password"]
        if not username or not password:
            raise ValueError("username and password are required")
        if self.user_repo.get_by_username(username):
            raise ValueError(f"user '{username}' already exists")
        role = UserRole(payload.get("role", UserRole.USER.value))
        user = User(username=username, password_hash=self.hash_password(password), role=role)
        self.user_repo.save(user)
        self.audit_service.log(actor.id if actor else None, "user.created", "user", user.id, user.username)
        return user.to_dict()

    def get_user(self, user_id: str) -> dict:
        user = self.user_repo.get(user_id)
        if not user:
            raise ValueError(f"user '{user_id}' not found")
        return user.to_dict()

    def login(self, payload: dict) -> dict:
        user = self.user_repo.get_by_username(payload["username"])
        if not user or not self.verify_password(payload["password"], user.password_hash):
            raise ValueError("invalid username or password")
        if not user.enabled:
            raise ValueError("user is disabled")
        return self._issue_token(user)

    def refresh_token(self, current_token: str, actor: User) -> dict:
        self.token_repo.revoke(current_token, utc_now())
        self.audit_service.log(actor.id, "auth.token_refreshed", "token", current_token, actor.username)
        return self._issue_token(actor)

    def _issue_token(self, user: User) -> dict:
        token = token_hex(24)
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(hours=self.TOKEN_TTL_HOURS)
        self.token_repo.save(token, user.id, created_at.isoformat(), expires_at.isoformat())
        self.audit_service.log(user.id, "auth.login", "token", token, user.username)
        return {"token": token, "expires_at": expires_at.isoformat(), "user": user.to_dict()}

    def logout(self, token: str, actor: User) -> None:
        self.token_repo.revoke(token, utc_now())
        self.audit_service.log(actor.id, "auth.logout", "token", token, actor.username)

    def list_users(self) -> list[dict]:
        return [item.to_dict() for item in self.user_repo.list_all()]

    def update_user_status(self, user_id: str, enabled: bool, actor: User) -> dict:
        user = self.user_repo.get(user_id)
        if not user:
            raise ValueError(f"user '{user_id}' not found")
        if user.deleted_at:
            raise ValueError("deleted user cannot be updated")
        user.enabled = enabled
        self.user_repo.save(user)
        if not enabled:
            self.token_repo.revoke_by_user_id(user.id, utc_now())
        self.audit_service.log(actor.id, "user.status_updated", "user", user.id, f"enabled={enabled}")
        return user.to_dict()

    def admin_reset_password(self, user_id: str, new_password: str, actor: User) -> None:
        user = self.user_repo.get(user_id)
        if not user:
            raise ValueError(f"user '{user_id}' not found")
        if user.deleted_at:
            raise ValueError("deleted user cannot reset password")
        user.password_hash = self.hash_password(new_password)
        self.user_repo.save(user)
        self.token_repo.revoke_by_user_id(user.id, utc_now())
        self.audit_service.log(actor.id, "user.password_reset", "user", user.id, user.username)

    def soft_delete_user(self, user_id: str, actor: User) -> None:
        user = self.user_repo.get(user_id)
        if not user:
            raise ValueError(f"user '{user_id}' not found")
        if user.id == actor.id:
            raise ValueError("cannot delete current admin user")
        if user.deleted_at:
            return
        user.enabled = False
        user.deleted_at = utc_now()
        self.user_repo.save(user)
        self.token_repo.revoke_by_user_id(user.id, utc_now())
        self.audit_service.log(actor.id, "user.deleted", "user", user.id, user.username)

    def change_password(self, actor: User, payload: dict) -> None:
        current_password = payload["current_password"]
        new_password = payload["new_password"]
        if not self.verify_password(current_password, actor.password_hash):
            raise ValueError("current password is incorrect")
        actor.password_hash = self.hash_password(new_password)
        self.user_repo.save(actor)
        self.token_repo.revoke_by_user_id(actor.id, utc_now())
        self.audit_service.log(actor.id, "user.password_changed", "user", actor.id, actor.username)

    def authenticate(self, token: str | None) -> User:
        if not token:
            raise PermissionError("missing auth token")
        token_row = self.token_repo.get(token)
        if not token_row:
            raise PermissionError("invalid auth token")
        if token_row["revoked_at"]:
            raise PermissionError("auth token has been revoked")
        expires_at = datetime.fromisoformat(token_row["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            raise PermissionError("auth token has expired")
        user = self.user_repo.get(token_row["user_id"])
        if not user or not user.enabled or user.deleted_at:
            raise PermissionError("user is disabled or missing")
        return user

    def require_admin(self, user: User) -> None:
        if user.role != UserRole.ADMIN:
            raise PermissionError("admin permission required")

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return f"{salt.hex()}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        salt_hex, digest_hex = password_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return hmac.compare_digest(actual, expected)


class ModelService:
    def __init__(self, repo: ModelRepository, audit_service: AuditService) -> None:
        self.repo = repo
        self.audit_service = audit_service
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        if self.repo.list_all():
            return

        defaults = [
            ModelConfig(
                name="DeepSearch Analyst",
                provider="internal",
                recommended_for=["company", "stock", "commodity"],
                parameters={"temperature": 0.2, "max_tokens": 8000},
            ),
            ModelConfig(
                name="Financial Reasoner",
                provider="partner",
                recommended_for=["stock", "company"],
                parameters={"temperature": 0.1, "tools": ["financials", "news"]},
            ),
        ]
        for item in defaults:
            self.repo.save(item)
            self.audit_service.log(None, "model.seeded", "model", item.id, item.name)

    def list_models(self) -> list[dict]:
        return [item.to_dict() for item in self.repo.list_all()]

    def list_available_models(self, role: str, object_type: str | None = None) -> list[dict]:
        models = [item for item in self.repo.list_all() if item.enabled]
        if object_type:
            models = [item for item in models if object_type in item.recommended_for]
        models = [item for item in models if role in item.permissions or "all" in item.permissions]
        return [item.to_dict() for item in models]

    def create_model(self, payload: dict, actor: User) -> dict:
        model = ModelConfig(
            name=payload["name"],
            provider=payload["provider"],
            enabled=payload.get("enabled", True),
            recommended_for=payload.get("recommended_for", []),
            parameters=payload.get("parameters", {}),
            permissions=payload.get("permissions", ["user"]),
        )
        self.repo.save(model)
        self.audit_service.log(actor.id, "model.created", "model", model.id, model.name)
        return model.to_dict()

    def update_model(self, model_id: str, payload: dict, actor: User) -> dict:
        model = self.require_model_exists(model_id)
        if "name" in payload:
            model.name = payload["name"]
        if "provider" in payload:
            model.provider = payload["provider"]
        if "enabled" in payload:
            model.enabled = bool(payload["enabled"])
        if "recommended_for" in payload:
            model.recommended_for = payload["recommended_for"]
        if "parameters" in payload:
            model.parameters = payload["parameters"]
        if "permissions" in payload:
            model.permissions = payload["permissions"]
        self.repo.save(model)
        self.audit_service.log(actor.id, "model.updated", "model", model.id, model.name)
        return model.to_dict()

    def delete_model(self, model_id: str, actor: User) -> None:
        model = self.require_model_exists(model_id)
        if self.repo.count_usage(model_id) > 0:
            raise ValueError("model is already used by research sessions and cannot be deleted")
        self.repo.delete(model_id)
        self.audit_service.log(actor.id, "model.deleted", "model", model.id, model.name)

    def require_model(self, model_id: str) -> ModelConfig:
        model = self.require_model_exists(model_id)
        if not model.enabled:
            raise ValueError(f"model '{model_id}' is disabled")
        return model

    def require_model_exists(self, model_id: str) -> ModelConfig:
        model = self.repo.get(model_id)
        if not model:
            raise ValueError(f"model '{model_id}' not found")
        return model


class ResearchService:
    def __init__(
        self,
        model_service: ModelService,
        session_repo: SessionRepository,
        report_repo: ReportRepository,
        job_repo: ResearchJobRepository,
        retrieval_result_repo: RetrievalResultRepository,
        audit_service: AuditService,
        retrieval_cache_ttl_seconds: int = 3600,
        llm_provider: LLMProvider | None = None,
        company_data_provider: CompanyDataProvider | None = None,
        stock_data_provider: StockDataProvider | None = None,
        commodity_data_provider: CommodityDataProvider | None = None,
        retrieval_provider: RetrievalProvider | None = None,
        retrieval_registry: RetrievalRegistry | None = None,
    ) -> None:
        self.model_service = model_service
        self.session_repo = session_repo
        self.report_repo = report_repo
        self.job_repo = job_repo
        self.retrieval_result_repo = retrieval_result_repo
        self.audit_service = audit_service
        self.retrieval_cache_ttl_seconds = retrieval_cache_ttl_seconds
        self.llm_provider = llm_provider or MockLLMProvider()
        self.company_data_provider = company_data_provider or MockCompanyDataProvider()
        self.stock_data_provider = stock_data_provider or MockStockDataProvider()
        self.commodity_data_provider = commodity_data_provider or MockCommodityDataProvider()
        self.retrieval_registry = retrieval_registry or RetrievalRegistry(
            [retrieval_provider or MockRetrievalProvider()],
            default_provider=(retrieval_provider.name if retrieval_provider else MockRetrievalProvider.name),
        )

    def create_session(self, payload: dict, user: User) -> dict:
        self.model_service.require_model(payload["model_id"])
        retrieval_provider = payload.get("retrieval_provider")
        self.retrieval_registry.get_provider(retrieval_provider)
        allowed_models = self.model_service.list_available_models(
            user.role.value,
            payload["object_type"],
        )
        allowed_ids = {item["id"] for item in allowed_models}
        if payload["model_id"] not in allowed_ids and user.role != UserRole.ADMIN:
            raise PermissionError("no permission to use this model")
        session = ResearchSession(
            user_id=payload["user_id"],
            object_name=payload["object_name"],
            object_type=ObjectType(payload["object_type"]),
            model_id=payload["model_id"],
            retrieval_provider=retrieval_provider,
            time_range=payload.get("time_range", "recent_12_months"),
            authority_level=payload.get("authority_level", "high"),
            depth=payload.get("depth", "standard"),
            focus_areas=payload.get("focus_areas", []),
            query=payload.get("query", ""),
        )
        session.workflow.append(WorkflowEvent(stage="created", detail="研究会话已创建"))
        self.session_repo.save(session)
        self.audit_service.log(user.id, "session.created", "session", session.id, session.object_name)
        return session.to_dict()

    def get_session(self, session_id: str, user: User) -> dict:
        session = self.require_session(session_id)
        self._assert_session_access(session, user)
        return session.to_dict()

    def add_message(self, session_id: str, payload: dict, user: User) -> dict:
        session = self.require_session(session_id)
        self._assert_session_access(session, user)
        message = ResearchMessage(role=payload["role"], content=payload["content"])
        session.messages.append(message)
        session.updated_at = utc_now()
        session.workflow.append(
            WorkflowEvent(stage="interaction", detail=f"收到{payload['role']}新消息")
        )
        self.session_repo.save(session)
        self.audit_service.log(user.id, "session.message_added", "session", session.id, payload["role"])
        return session.to_dict()

    def create_job(self, session_id: str, user: User, force_refresh: bool = False) -> dict:
        session = self.require_session(session_id)
        self._assert_session_access(session, user)
        job = ResearchJob(session_id=session.id, user_id=user.id, force_refresh=force_refresh)
        self.job_repo.save(job)
        self.audit_service.log(
            user.id,
            "job.created",
            "research_job",
            job.id,
            f"{session.id};force_refresh={str(force_refresh).lower()}",
        )
        return job.to_dict()

    def cancel_job(self, job_id: str, user: User) -> dict:
        job = self.require_job(job_id)
        if user.role != UserRole.ADMIN and job.user_id != user.id:
            raise PermissionError("no permission to access this job")
        if job.status in {ResearchJobStatus.COMPLETED, ResearchJobStatus.FAILED, ResearchJobStatus.CANCELLED}:
            return job.to_dict()
        job.cancel_requested = True
        if job.status == ResearchJobStatus.QUEUED:
            job.status = ResearchJobStatus.CANCELLED
            job.current_stage = "cancelled"
            job.progress = 0
        job.updated_at = utc_now()
        self.job_repo.save(job)
        self.audit_service.log(user.id, "job.cancel_requested", "research_job", job.id, job.session_id)
        return job.to_dict()

    def retry_job(self, job_id: str, user: User) -> dict:
        job = self.require_job(job_id)
        if user.role != UserRole.ADMIN and job.user_id != user.id:
            raise PermissionError("no permission to access this job")
        if job.status not in {ResearchJobStatus.FAILED, ResearchJobStatus.CANCELLED}:
            raise ValueError("only failed or cancelled jobs can be retried")
        new_job = ResearchJob(session_id=job.session_id, user_id=job.user_id)
        self.job_repo.save(new_job)
        self.audit_service.log(user.id, "job.retried", "research_job", new_job.id, job.id)
        return new_job.to_dict()

    def run_session(self, session_id: str, user: User) -> dict:
        job = self.create_job(session_id, user)
        finished_job = self.process_job(job["id"])
        session = self.require_session(session_id)
        report = self.report_repo.get(finished_job["report_id"]) if finished_job["report_id"] else None
        return {
            "session": session.to_dict(),
            "report": report.to_dict() if report else None,
            "job": finished_job,
        }

    def process_job(self, job_id: str) -> dict:
        job = self.require_job(job_id)
        session = self.require_session(job.session_id)
        retrieval_bundle: RetrievalBundle | None = None
        retrieval_cache_hit = False
        company_data: CompanyResearchData | None = None
        stock_data: StockResearchData | None = None
        commodity_data: CommodityResearchData | None = None
        try:
            self._guard_job_not_cancelled(job)
            self._update_job(job, ResearchJobStatus.RUNNING, 10, "planning")
            session.status = SessionStatus.RUNNING
            session.updated_at = utc_now()
            session.workflow.append(WorkflowEvent(stage="planning", detail="正在拆解调研问题"))
            self.session_repo.save(session)

            self._refresh_job(job)
            self._guard_job_not_cancelled(job)
            self._update_job(job, ResearchJobStatus.RUNNING, 45, "search")
            retrieval_bundle, retrieval_cache_hit = self._retrieve(session, force_refresh=job.force_refresh)
            self.retrieval_result_repo.save(
                job.id,
                session.id,
                retrieval_bundle,
                cache_key=self._build_retrieval_cache_key(session),
                cache_hit=retrieval_cache_hit,
            )
            session.workflow.append(
                WorkflowEvent(
                    stage="search",
                    detail=(
                        "复用已缓存的检索结果"
                        if retrieval_cache_hit
                        else "强制刷新检索结果" if job.force_refresh else "正在检索权威信息源"
                    ),
                )
            )
            session.updated_at = utc_now()
            self.session_repo.save(session)

            self._refresh_job(job)
            self._guard_job_not_cancelled(job)
            company_data = self._collect_company_data(session, retrieval_bundle)
            stock_data = self._collect_stock_data(session, retrieval_bundle)
            commodity_data = self._collect_commodity_data(session, retrieval_bundle)
            if company_data or stock_data or commodity_data:
                detail = "正在抓取结构化对象数据"
                if company_data:
                    detail = "正在抓取公司结构化数据"
                elif stock_data:
                    detail = "正在抓取股票结构化数据"
                elif commodity_data:
                    detail = "正在抓取商品结构化数据"
                stage = "object_data"
                if company_data:
                    stage = "company_data"
                elif stock_data:
                    stage = "stock_data"
                elif commodity_data:
                    stage = "commodity_data"
                session.workflow.append(WorkflowEvent(stage=stage, detail=detail))
                session.updated_at = utc_now()
                self.session_repo.save(session)

            self._refresh_job(job)
            self._guard_job_not_cancelled(job)
            self._update_job(job, ResearchJobStatus.RUNNING, 80, "analysis")
            session.workflow.append(WorkflowEvent(stage="analysis", detail="正在生成结构化分析结论"))
            session.updated_at = utc_now()
            self.session_repo.save(session)

            self._refresh_job(job)
            self._guard_job_not_cancelled(job)
            report = self._build_report(
                session,
                retrieval_bundle,
                company_data=company_data,
                stock_data=stock_data,
                commodity_data=commodity_data,
            )
            session.report_id = report.id
            session.status = SessionStatus.COMPLETED
            session.updated_at = utc_now()
            session.workflow.append(WorkflowEvent(stage="completed", detail="调研报告已生成"))

            self.report_repo.save(report)
            self.session_repo.save(session)
            self._update_job(job, ResearchJobStatus.COMPLETED, 100, "completed", report_id=report.id)
            if retrieval_cache_hit:
                self.audit_service.log(job.user_id, "retrieval.cache_hit", "research_job", job.id, session.id)
            else:
                self.audit_service.log(job.user_id, "retrieval.cache_miss", "research_job", job.id, session.id)
            self.audit_service.log(job.user_id, "session.completed", "session", session.id, session.object_name)
            self.audit_service.log(job.user_id, "report.generated", "report", report.id, report.title)
            self.audit_service.log(job.user_id, "job.completed", "research_job", job.id, session.id)
        except Exception as exc:
            if str(exc) == "__job_cancelled__":
                session.status = SessionStatus.DRAFT
                session.updated_at = utc_now()
                session.workflow.append(WorkflowEvent(stage="cancelled", detail="调研任务已取消"))
                self.session_repo.save(session)
                self._update_job(job, ResearchJobStatus.CANCELLED, job.progress, "cancelled")
                self.audit_service.log(job.user_id, "job.cancelled", "research_job", job.id, session.id)
            else:
                self._update_job(job, ResearchJobStatus.FAILED, job.progress, "failed", error_message=str(exc))
                self.audit_service.log(job.user_id, "job.failed", "research_job", job.id, str(exc))
                raise
        return self.require_job(job_id).to_dict()

    def list_jobs(
        self,
        user: User,
        limit: int = 100,
        offset: int = 0,
        session_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        scoped_user_id = None if user.role == UserRole.ADMIN else user.id
        total = self.job_repo.count_filtered(user_id=scoped_user_id, session_id=session_id, status=status)
        items = self.job_repo.list_filtered(
            limit=limit,
            offset=offset,
            user_id=scoped_user_id,
            session_id=session_id,
            status=status,
        )
        total = max(total, offset + len(items))
        return {
            "items": [item.to_dict() for item in items],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    def get_job(self, job_id: str, user: User) -> dict:
        job = self.require_job(job_id)
        if user.role != UserRole.ADMIN and job.user_id != user.id:
            raise PermissionError("no permission to access this job")
        return job.to_dict()

    def get_job_retrieval_result(self, job_id: str, user: User) -> dict:
        return self.get_job_retrieval_result_filtered(job_id, user)

    def get_job_retrieval_result_filtered(self, job_id: str, user: User, keyword: str | None = None) -> dict:
        job = self.require_job(job_id)
        if user.role != UserRole.ADMIN and job.user_id != user.id:
            raise PermissionError("no permission to access this job")
        result = self.retrieval_result_repo.get_by_job_id(job_id)
        if not result:
            raise ValueError(f"retrieval result for job '{job_id}' not found")
        attached = self._attach_job_to_retrieval_result(result, job=job, keyword=keyword)
        if keyword and keyword.strip():
            self._record_search_event(user, keyword.strip(), "job_retrieval", job_id)
            attached["search_meta"] = self._build_retrieval_search_meta([attached], keyword.strip())
        return attached

    def list_session_retrieval_results(
        self,
        session_id: str,
        user: User,
        limit: int = 100,
        offset: int = 0,
        provider: str | None = None,
        cache_hit: bool | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        session = self.require_session(session_id)
        self._assert_session_access(session, user)
        if keyword and keyword.strip():
            self._record_search_event(user, keyword.strip(), "session_retrievals", session_id)
            results = self.retrieval_result_repo.list_by_session_id(
                session_id,
                limit=10000,
                offset=0,
                provider=provider,
                cache_hit=cache_hit,
                created_from=created_from,
                created_to=created_to,
            )
            filtered_items = [
                self._attach_job_to_retrieval_result(item, keyword=keyword)
                for item in results
            ]
            filtered_items = [item for item in filtered_items if item.get("documents")]
            total = len(filtered_items)
            items = filtered_items[offset: offset + limit]
            latest = items[0] if items else None
        else:
            total = self.retrieval_result_repo.count_by_session_id(
                session_id,
                provider=provider,
                cache_hit=cache_hit,
                created_from=created_from,
                created_to=created_to,
            )
            results = self.retrieval_result_repo.list_by_session_id(
                session_id,
                limit=limit,
                offset=offset,
                provider=provider,
                cache_hit=cache_hit,
                created_from=created_from,
                created_to=created_to,
            )
            items = [self._attach_job_to_retrieval_result(item) for item in results]
            latest = self._attach_job_to_retrieval_result(results[0]) if results else None
        return {
            "session": session.to_dict(),
            "latest": latest,
            "items": items,
            "filters": {
                "provider": provider,
                "cache_hit": cache_hit,
                "created_from": created_from,
                "created_to": created_to,
                "keyword": keyword,
            },
            "search_meta": self._build_retrieval_search_meta(items, keyword.strip()) if keyword and keyword.strip() else None,
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    def list_retrieval_providers(self) -> dict:
        return {
            "items": self.retrieval_registry.list_providers(),
            "default_provider": self.retrieval_registry.default_provider,
        }

    def list_reports(
        self,
        user: User,
        limit: int = 100,
        offset: int = 0,
        created_from: str | None = None,
        created_to: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        session_ids = None
        if user.role != UserRole.ADMIN:
            sessions = self.session_repo.list_filtered(user_id=user.id, limit=10000, offset=0)
            session_ids = [session.id for session in sessions]
        clean_keyword = keyword.strip() if keyword else None
        if clean_keyword:
            self._record_search_event(user, clean_keyword, "report_list", user.id)
            reports = self.report_repo.list_filtered(
                limit=10000,
                offset=0,
                session_ids=session_ids,
                created_from=created_from,
                created_to=created_to,
            )
            highlighted_items = [
                self._build_report_list_item(self._highlight_report_payload(item.to_dict(), clean_keyword))
                for item in reports
            ]
            matched_items = [item for item in highlighted_items if item.get("has_keyword_match")]
            total = len(matched_items)
            items = matched_items[offset: offset + limit]
        else:
            total = self.report_repo.count_filtered(
                session_ids=session_ids,
                created_from=created_from,
                created_to=created_to,
            )
            items = [
                self._build_report_list_item(item.to_dict())
                for item in self.report_repo.list_filtered(
                    limit=limit,
                    offset=offset,
                    session_ids=session_ids,
                    created_from=created_from,
                    created_to=created_to,
                )
            ]
        return {
            "items": items,
            "filters": {
                "created_from": created_from,
                "created_to": created_to,
                "keyword": clean_keyword,
            },
            "search_meta": self._build_report_search_meta(items, clean_keyword) if clean_keyword else None,
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    def export_report_markdown(self, report_id: str, user: User, keyword: str | None = None) -> dict:
        report = self.report_repo.get(report_id)
        if not report:
            raise ValueError(f"report '{report_id}' not found")
        session = self.require_session(report.session_id)
        self._assert_session_access(session, user)
        report_payload = report.to_dict()
        if keyword and keyword.strip():
            self._record_search_event(user, keyword.strip(), "report_markdown", report_id)
            report_payload = self._highlight_report_payload(report_payload, keyword.strip())
        markdown = self._render_report_markdown(report_payload)
        return {
            "report_id": report.id,
            "filename": f"{report.id}.md",
            "content_type": "text/markdown; charset=utf-8",
            "markdown": markdown,
        }

    def get_report(self, report_id: str, user: User, keyword: str | None = None) -> dict:
        report = self.report_repo.get(report_id)
        if not report:
            raise ValueError(f"report '{report_id}' not found")
        session = self.require_session(report.session_id)
        self._assert_session_access(session, user)
        report_payload = report.to_dict()
        if keyword and keyword.strip():
            self._record_search_event(user, keyword.strip(), "report_detail", report_id)
            report_payload = self._highlight_report_payload(report_payload, keyword.strip())
        return {
            "report": report_payload,
            "session": session.to_dict(),
            "keyword": keyword.strip() if keyword else None,
        }

    def get_report_profile(self, report_id: str, user: User) -> dict:
        report = self.report_repo.get(report_id)
        if not report:
            raise ValueError(f"report '{report_id}' not found")
        session = self.require_session(report.session_id)
        self._assert_session_access(session, user)
        profile_section = None
        for section in report.body:
            if not isinstance(section, dict):
                continue
            structured_data = section.get("structured_data")
            if isinstance(structured_data, dict):
                profile_section = section
                break
        if profile_section is None:
            raise ValueError(f"profile for report '{report_id}' not found")
        return {
            "report_id": report.id,
            "session_id": session.id,
            "object_name": session.object_name,
            "object_type": (
                session.object_type.value if isinstance(session.object_type, ObjectType) else session.object_type
            ),
            "section_heading": str(profile_section.get("heading", "")).strip(),
            "profile": profile_section.get("structured_data"),
        }

    def get_search_insights(self, user: User, limit: int = 10) -> dict:
        actor_user_id = None if user.role == UserRole.ADMIN else user.id
        logs = self.audit_service.repo.list_all(
            limit=1000,
            offset=0,
            actor_user_id=actor_user_id,
            action="search.query",
        )
        entries: list[dict] = []
        keyword_counter: Counter[str] = Counter()
        scope_counter: Counter[str] = Counter()
        for log in logs:
            detail = self._parse_search_log_detail(log.detail)
            keyword = str(detail.get("keyword", "")).strip()
            scope = str(detail.get("scope", "")).strip()
            if not keyword:
                continue
            entries.append(
                {
                    "keyword": keyword,
                    "scope": scope,
                    "resource_id": log.resource_id,
                    "created_at": log.created_at,
                }
            )
            keyword_counter[keyword] += 1
            if scope:
                scope_counter[scope] += 1
        recent_searches = entries[:limit]
        popular_keywords = [
            {"keyword": keyword, "count": count}
            for keyword, count in keyword_counter.most_common(limit)
        ]
        popular_scopes = [
            {"scope": scope, "count": count}
            for scope, count in scope_counter.most_common(limit)
        ]
        return {
            "recent_searches": recent_searches,
            "popular_keywords": popular_keywords,
            "popular_scopes": popular_scopes,
            "total_searches": sum(keyword_counter.values()),
        }

    def answer_report_follow_up(
        self,
        report_id: str,
        question: str,
        user: User,
        paragraph_index: int | None = None,
        keyword: str | None = None,
    ) -> dict:
        report = self.report_repo.get(report_id)
        if not report:
            raise ValueError(f"report '{report_id}' not found")
        session = self.require_session(report.session_id)
        self._assert_session_access(session, user)
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("question cannot be empty")
        clean_keyword = keyword.strip() if keyword else None
        report_payload = report.to_dict()
        highlighted_report = (
            self._highlight_report_payload(report_payload, clean_keyword)
            if clean_keyword
            else report_payload
        )
        resolved_paragraph_index = paragraph_index
        if resolved_paragraph_index is None and clean_keyword:
            resolved_paragraph_index = self._find_first_matching_section_index(highlighted_report)
        section = self._resolve_report_section_payload(highlighted_report, resolved_paragraph_index)
        citations = self._resolve_follow_up_citations(report, section)
        draft = self._generate_follow_up_draft(report, session, clean_question, section=section, citations=citations)
        session.messages.append(ResearchMessage(role="user", content=clean_question))
        session.messages.append(ResearchMessage(role="assistant", content=draft.answer))
        workflow_detail = "已生成报告追问回复"
        if resolved_paragraph_index is not None and section:
            workflow_detail = f"已生成报告段落追问回复：{section.get('heading', '未命名段落')}"
        session.workflow.append(WorkflowEvent(stage="follow_up", detail=workflow_detail))
        session.updated_at = utc_now()
        self.session_repo.save(session)
        self.audit_service.log(user.id, "report.follow_up_answered", "report", report.id, clean_question[:120])
        highlighted_section = self._highlight_section_for_follow_up(section, clean_keyword) if section else None
        highlighted_citations = (
            [self._highlight_report_evidence(item, self._parse_keyword_terms(clean_keyword)) for item in citations]
            if clean_keyword
            else citations
        )
        highlighted_answer = (
            self._highlight_terms_in_text(draft.answer, self._parse_keyword_terms(clean_keyword))
            if clean_keyword
            else draft.answer
        )
        return {
            "report_id": report.id,
            "session_id": session.id,
            "question": clean_question,
            "paragraph_index": resolved_paragraph_index,
            "keyword": clean_keyword,
            "section": highlighted_section or section,
            "citations": highlighted_citations,
            "answer": draft.answer,
            "highlighted_answer": highlighted_answer,
            "context_messages": [item.to_dict() for item in session.messages[-6:]],
        }

    def list_sessions(
        self,
        user: User,
        limit: int = 100,
        offset: int = 0,
        object_type: str | None = None,
        model_id: str | None = None,
        status: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> dict:
        scoped_user_id = None if user.role == UserRole.ADMIN else user.id
        total = self.session_repo.count_filtered(
            user_id=scoped_user_id,
            object_type=object_type,
            model_id=model_id,
            status=status,
            created_from=created_from,
            created_to=created_to,
        )
        items = self.session_repo.list_filtered(
            limit=limit,
            offset=offset,
            user_id=scoped_user_id,
            object_type=object_type,
            model_id=model_id,
            status=status,
            created_from=created_from,
            created_to=created_to,
        )
        return {
            "items": [item.to_dict() for item in items],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    def require_session(self, session_id: str) -> ResearchSession:
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"session '{session_id}' not found")
        return session

    def require_job(self, job_id: str) -> ResearchJob:
        job = self.job_repo.get(job_id)
        if not job:
            raise ValueError(f"job '{job_id}' not found")
        return job

    def _update_job(
        self,
        job: ResearchJob,
        status: ResearchJobStatus,
        progress: int,
        stage: str,
        error_message: str | None = None,
        report_id: str | None = None,
    ) -> None:
        job.status = status
        job.progress = progress
        job.current_stage = stage
        job.error_message = error_message
        job.report_id = report_id if report_id is not None else job.report_id
        job.updated_at = utc_now()
        self.job_repo.save(job)

    def _refresh_job(self, job: ResearchJob) -> None:
        fresh = self.require_job(job.id)
        job.status = fresh.status
        job.progress = fresh.progress
        job.current_stage = fresh.current_stage
        job.cancel_requested = fresh.cancel_requested
        job.error_message = fresh.error_message
        job.report_id = fresh.report_id
        job.updated_at = fresh.updated_at

    def _retrieve(self, session: ResearchSession, force_refresh: bool = False) -> tuple[RetrievalBundle, bool]:
        cache_key = self._build_retrieval_cache_key(session)
        cached = None if force_refresh else self.retrieval_result_repo.get_latest_by_cache_key(cache_key)
        if cached and self._is_cache_fresh(cached):
            return self._bundle_from_dict(cached), True
        try:
            return self.retrieval_registry.search(session, session.retrieval_provider), False
        except RetrievalProviderError:
            fallback = self.retrieval_registry.get_provider("mock_deepsearch")
            return fallback.search(session), False

    def _is_cache_fresh(self, payload: dict) -> bool:
        if self.retrieval_cache_ttl_seconds <= 0:
            return False
        created_at_raw = payload.get("created_at")
        if not created_at_raw:
            return False
        try:
            created_at = datetime.fromisoformat(str(created_at_raw))
        except ValueError:
            return False
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)
        return age <= timedelta(seconds=self.retrieval_cache_ttl_seconds)

    def _build_retrieval_cache_key(self, session: ResearchSession) -> str:
        object_type = (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        payload = {
            "provider": session.retrieval_provider or self.retrieval_registry.default_provider,
            "object_name": session.object_name,
            "object_type": object_type,
            "query": session.query,
            "focus_areas": session.focus_areas,
            "time_range": session.time_range,
            "authority_level": session.authority_level,
            "depth": session.depth,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _bundle_from_dict(self, payload: dict) -> RetrievalBundle:
        return RetrievalBundle(
            provider=str(payload["provider"]),
            object_name=str(payload["object_name"]),
            object_type=str(payload["object_type"]),
            documents=[
                self._document_from_dict(item)
                for item in payload.get("documents", [])
                if isinstance(item, dict)
            ],
            created_at=str(payload.get("created_at") or utc_now()),
        )

    def _attach_job_to_retrieval_result(
        self,
        payload: dict,
        job: ResearchJob | None = None,
        keyword: str | None = None,
    ) -> dict:
        result = dict(payload)
        job_id = result.get("job_id")
        if job_id:
            resolved_job = job or self.job_repo.get(str(job_id))
            result["job"] = resolved_job.to_dict() if resolved_job else None
        else:
            result["job"] = None
        result = self._filter_retrieval_result_documents(result, keyword)
        result["card"] = self._build_retrieval_card(result)
        return result

    def _filter_retrieval_result_documents(self, payload: dict, keyword: str | None = None) -> dict:
        result = dict(payload)
        documents = result.get("documents", [])
        if not isinstance(documents, list):
            result["documents"] = []
            return result
        clean_keyword = (keyword or "").strip()
        if not clean_keyword:
            return result
        terms = self._parse_keyword_terms(clean_keyword)
        filtered_docs = []
        for item in documents:
            if not isinstance(item, dict):
                continue
            highlighted = self._highlight_document_matches(item, terms)
            if highlighted["match_count"] > 0:
                filtered_docs.append(highlighted)
        result["documents"] = filtered_docs
        result["keyword"] = clean_keyword
        result["matched_document_count"] = len(filtered_docs)
        return result

    @staticmethod
    def _parse_keyword_terms(keyword: str) -> list[str]:
        return [term.strip() for term in re.split(r"\s+", keyword) if term.strip()]

    def _highlight_document_matches(self, payload: dict, terms: list[str]) -> dict:
        result = dict(payload)
        fields = {
            "title": str(payload.get("title", "")),
            "summary": str(payload.get("summary", "")),
            "source": str(payload.get("source", "")),
            "url": str(payload.get("url", "")),
        }
        match_count = 0
        matched_fields: list[str] = []
        for field_name, text in fields.items():
            highlighted_text = text
            field_matched = False
            for term in terms:
                if term.lower() in text.lower():
                    highlighted_text = self._highlight_text(highlighted_text, term)
                    match_count += text.lower().count(term.lower())
                    field_matched = True
            if field_matched:
                matched_fields.append(field_name)
                result[f"highlighted_{field_name}"] = highlighted_text
        result["match_count"] = match_count
        result["matched_fields"] = matched_fields
        if "highlighted_summary" in result:
            result["highlight_preview"] = str(result["highlighted_summary"])[:200]
        elif "highlighted_title" in result:
            result["highlight_preview"] = str(result["highlighted_title"])[:200]
        else:
            result["highlight_preview"] = ""
        return result

    @staticmethod
    def _highlight_text(text: str, term: str) -> str:
        return re.sub(
            re.escape(term),
            lambda match: f"<mark>{match.group(0)}</mark>",
            text,
            flags=re.IGNORECASE,
        )

    def _highlight_report_payload(self, report: dict, keyword: str) -> dict:
        terms = self._parse_keyword_terms(keyword)
        highlighted = dict(report)
        highlighted["summary"] = self._highlight_terms_in_text(str(report.get("summary", "")), terms)
        highlighted["conclusion"] = self._highlight_terms_in_text(str(report.get("conclusion", "")), terms)
        body = report.get("body", [])
        highlighted_body = []
        matched_sections = 0
        for section in body if isinstance(body, list) else []:
            if not isinstance(section, dict):
                continue
            enriched_section = dict(section)
            enriched_section["highlighted_heading"] = self._highlight_terms_in_text(
                str(section.get("heading", "")),
                terms,
            )
            enriched_section["highlighted_content"] = self._highlight_terms_in_text(
                str(section.get("content", "")),
                terms,
            )
            enriched_section["content_segments"] = [
                self._highlight_report_segment(item, terms)
                for item in section.get("content_segments", [])
                if isinstance(item, dict)
            ]
            enriched_section["evidence_items"] = [
                self._highlight_report_evidence(item, terms)
                for item in section.get("evidence_items", [])
                if isinstance(item, dict)
            ]
            if self._section_has_keyword_match(enriched_section):
                matched_sections += 1
            highlighted_body.append(enriched_section)
        highlighted["body"] = highlighted_body
        highlighted["citations"] = [
            self._highlight_report_evidence(item, terms)
            for item in report.get("citations", [])
            if isinstance(item, dict)
        ]
        highlighted["keyword"] = keyword
        highlighted["matched_section_count"] = matched_sections
        return highlighted

    def _highlight_report_segment(self, payload: dict, terms: list[str]) -> dict:
        result = dict(payload)
        result["highlighted_text"] = self._highlight_terms_in_text(str(payload.get("text", "")), terms)
        return result

    def _highlight_report_evidence(self, payload: dict, terms: list[str]) -> dict:
        result = dict(payload)
        result["highlighted_title"] = self._highlight_terms_in_text(str(payload.get("title", "")), terms)
        result["highlighted_source"] = self._highlight_terms_in_text(str(payload.get("source", "")), terms)
        return result

    def _highlight_terms_in_text(self, text: str, terms: list[str]) -> str:
        highlighted = text
        for term in terms:
            if term.lower() in highlighted.lower():
                highlighted = self._highlight_text(highlighted, term)
        return highlighted

    @staticmethod
    def _section_has_keyword_match(section: dict) -> bool:
        for field in ("highlighted_heading", "highlighted_content"):
            if "<mark>" in str(section.get(field, "")):
                return True
        for item in section.get("content_segments", []):
            if "<mark>" in str(item.get("highlighted_text", "")):
                return True
        for item in section.get("evidence_items", []):
            if "<mark>" in str(item.get("highlighted_title", "")) or "<mark>" in str(item.get("highlighted_source", "")):
                return True
        return False

    def _build_report_list_item(self, report: dict) -> dict:
        body = report.get("body", [])
        preview = ""
        matched_sections = int(report.get("matched_section_count", 0) or 0)
        if isinstance(body, list) and body:
            preview_source = None
            for section in body:
                if isinstance(section, dict) and (
                    "<mark>" in str(section.get("highlighted_heading", ""))
                    or "<mark>" in str(section.get("highlighted_content", ""))
                ):
                    preview_source = section
                    break
            if preview_source is None:
                preview_source = body[0] if isinstance(body[0], dict) else {}
            preview = str(
                preview_source.get("highlighted_content")
                or preview_source.get("content")
                or report.get("summary", "")
            ).strip()[:180]
        highlighted_title = str(report.get("highlighted_title") or report.get("title", "")).strip()
        highlighted_summary = str(report.get("summary", "")).strip()
        has_keyword_match = (
            "<mark>" in highlighted_title
            or "<mark>" in highlighted_summary
            or "<mark>" in str(report.get("conclusion", ""))
            or matched_sections > 0
            or any("<mark>" in str(item.get("highlighted_title", "")) for item in report.get("citations", []))
        )
        return {
            "id": report.get("id"),
            "session_id": report.get("session_id"),
            "title": report.get("title"),
            "summary": report.get("summary"),
            "created_at": report.get("created_at"),
            "highlighted_title": highlighted_title,
            "highlighted_summary": highlighted_summary,
            "preview": preview,
            "matched_section_count": matched_sections,
            "has_keyword_match": has_keyword_match,
        }

    def _build_report_search_meta(self, items: list[dict], keyword: str) -> dict:
        texts: list[str] = []
        for item in items:
            texts.extend(
                [
                    str(item.get("title", "")),
                    str(item.get("summary", "")),
                    str(item.get("preview", "")),
                ]
            )
        return {
            "keyword": keyword,
            "matched_item_count": len(items),
            "suggested_keywords": self._suggest_keywords(texts, exclude_terms=[keyword]),
        }

    def _record_search_event(self, user: User, keyword: str, scope: str, resource_id: str) -> None:
        self.audit_service.log(
            user.id,
            "search.query",
            "search",
            resource_id,
            json.dumps({"keyword": keyword, "scope": scope}, ensure_ascii=False),
        )

    @staticmethod
    def _parse_search_log_detail(detail: str) -> dict:
        if not detail.strip():
            return {}
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _build_retrieval_search_meta(self, items: list[dict], keyword: str) -> dict:
        texts: list[str] = []
        matched_document_count = 0
        for item in items:
            documents = item.get("documents", [])
            if not isinstance(documents, list):
                continue
            matched_document_count += len(documents)
            for doc in documents:
                if not isinstance(doc, dict):
                    continue
                texts.extend(
                    [
                        str(doc.get("title", "")),
                        str(doc.get("summary", "")),
                        str(doc.get("source", "")),
                    ]
                )
        return {
            "keyword": keyword,
            "matched_item_count": len(items),
            "matched_document_count": matched_document_count,
            "suggested_keywords": self._suggest_keywords(texts, exclude_terms=[keyword]),
        }

    def _suggest_keywords(self, texts: list[str], exclude_terms: list[str] | None = None) -> list[str]:
        stop_terms = {
            "公司",
            "市场",
            "行业",
            "业务",
            "相关",
            "进行",
            "形成",
            "当前",
            "报告",
            "结论",
            "摘要",
            "分析",
            "研究",
            "对象",
            "基础",
            "信号",
            "观察",
            "风险",
        }
        if exclude_terms:
            stop_terms.update(term.strip().lower() for term in exclude_terms if term.strip())
        counter: Counter[str] = Counter()
        for text in texts:
            for token in self._tokenize_keywords(text):
                normalized = token.lower()
                if normalized in stop_terms or len(token) < 2:
                    continue
                counter[token] += 1
        return [token for token, _count in counter.most_common(5)]

    @staticmethod
    def _tokenize_keywords(text: str) -> list[str]:
        tokens: list[str] = []
        tokens.extend(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text))
        tokens.extend(re.findall(r"[\u4e00-\u9fff]{2,6}", text))
        return tokens

    def _find_first_matching_section_index(self, report: dict) -> int | None:
        body = report.get("body", [])
        if not isinstance(body, list):
            return None
        for index, section in enumerate(body):
            if not isinstance(section, dict):
                continue
            if "<mark>" in str(section.get("highlighted_heading", "")):
                return index
            if "<mark>" in str(section.get("highlighted_content", "")):
                return index
            for item in section.get("content_segments", []):
                if "<mark>" in str(item.get("highlighted_text", "")):
                    return index
        for index, section in enumerate(body):
            if isinstance(section, dict) and self._section_has_keyword_match(section):
                return index
        return None

    def _highlight_section_for_follow_up(self, section: dict, keyword: str | None) -> dict:
        if not keyword:
            return section
        terms = self._parse_keyword_terms(keyword)
        highlighted = dict(section)
        highlighted["heading"] = self._highlight_terms_in_text(str(section.get("heading", "")), terms)
        highlighted["content"] = self._highlight_terms_in_text(str(section.get("content", "")), terms)
        highlighted["content_segments"] = [
            self._highlight_report_segment(item, terms)
            for item in section.get("content_segments", [])
            if isinstance(item, dict)
        ]
        highlighted["evidence_items"] = [
            self._highlight_report_evidence(item, terms)
            for item in section.get("evidence_items", [])
            if isinstance(item, dict)
        ]
        return highlighted

    def _build_retrieval_card(self, payload: dict) -> dict:
        documents = payload.get("documents", [])
        if not isinstance(documents, list):
            documents = []
        normalized_docs = [item for item in documents if isinstance(item, dict)]
        top_titles = [str(item.get("title", "")).strip() for item in normalized_docs[:3] if str(item.get("title", "")).strip()]
        top_sources: list[str] = []
        for item in normalized_docs:
            source = str(item.get("source", "")).strip()
            if source and source not in top_sources:
                top_sources.append(source)
            if len(top_sources) >= 3:
                break
        preview = ""
        if normalized_docs:
            preview = str(normalized_docs[0].get("summary", "")).strip() or str(normalized_docs[0].get("title", "")).strip()
        return {
            "provider": payload.get("provider"),
            "cache_hit": bool(payload.get("cache_hit", False)),
            "document_count": len(normalized_docs),
            "category_counts": self._count_retrieval_categories(normalized_docs),
            "top_titles": top_titles,
            "top_sources": top_sources,
            "preview": preview[:160],
            "created_at": payload.get("created_at"),
        }

    @staticmethod
    def _count_retrieval_categories(documents: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in documents:
            category = str(item.get("category", "general"))
            counts[category] = counts.get(category, 0) + 1
        return counts

    @staticmethod
    def _document_from_dict(payload: dict) -> RetrievalDocument:
        return RetrievalDocument(
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            source=str(payload.get("source", "")),
            url=str(payload.get("url", "")),
            published_at=str(payload.get("published_at") or utc_now()),
            tags=[str(tag) for tag in payload.get("tags", [])] if isinstance(payload.get("tags"), list) else [],
        )

    def _guard_job_not_cancelled(self, job: ResearchJob) -> None:
        if job.cancel_requested:
            raise RuntimeError("__job_cancelled__")

    def _assert_session_access(self, session: ResearchSession, user: User) -> None:
        if user.role == UserRole.ADMIN:
            return
        if session.user_id != user.id:
            raise PermissionError("no permission to access this session")

    def _build_report(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
        company_data: CompanyResearchData | None = None,
        stock_data: StockResearchData | None = None,
        commodity_data: CommodityResearchData | None = None,
    ) -> Report:
        draft = self._generate_report_draft(session, retrieval_bundle)
        retrieval_documents = retrieval_bundle.documents if retrieval_bundle else []
        citations = (
            [
                {
                    "title": item.title,
                    "source": item.source,
                    "url": item.url,
                    "category": getattr(item, "category", "general"),
                }
                for item in retrieval_documents
            ]
            if retrieval_documents
            else [
                {"title": "企业/标的基础信息", "source": "模拟数据源", "url": "", "category": "fundamentals"},
                {"title": "市场与行业信号", "source": "模拟数据源", "url": "", "category": "market"},
            ]
        )
        report_body = list(draft.body)
        if company_data:
            report_body = [self._build_company_profile_section(company_data), *report_body]
        if stock_data:
            report_body = [self._build_stock_profile_section(stock_data), *report_body]
        if commodity_data:
            report_body = [self._build_commodity_profile_section(commodity_data), *report_body]
        body = self._attach_section_evidence(report_body, citations)
        return Report(
            session_id=session.id,
            title=draft.title,
            summary=draft.summary,
            body=body,
            conclusion=draft.conclusion,
            citations=citations,
        )

    def _collect_company_data(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> CompanyResearchData | None:
        object_type = (
            session.object_type.value if isinstance(session.object_type, ObjectType) else session.object_type
        )
        if object_type != ObjectType.COMPANY.value:
            return None
        try:
            return self.company_data_provider.collect(session, retrieval_bundle, llm_provider=self.llm_provider)
        except Exception:
            return None

    def _collect_stock_data(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> StockResearchData | None:
        object_type = (
            session.object_type.value if isinstance(session.object_type, ObjectType) else session.object_type
        )
        if object_type != ObjectType.STOCK.value:
            return None
        try:
            return self.stock_data_provider.collect(session, retrieval_bundle, llm_provider=self.llm_provider)
        except Exception:
            return None

    def _collect_commodity_data(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> CommodityResearchData | None:
        object_type = (
            session.object_type.value if isinstance(session.object_type, ObjectType) else session.object_type
        )
        if object_type != ObjectType.COMMODITY.value:
            return None
        try:
            return self.commodity_data_provider.collect(session, retrieval_bundle, llm_provider=self.llm_provider)
        except Exception:
            return None

    @staticmethod
    def _build_company_profile_section(company_data: CompanyResearchData) -> dict[str, object]:
        content = (
            f"注册主体：{company_data.registered_name}。"
            f"经营概览：{company_data.business_overview}。"
            f"行业位置：{company_data.industry_position}"
        )
        return {
            "heading": "公司画像",
            "content": content,
            "structured_data": {
                "company_name": company_data.company_name,
                "registered_name": company_data.registered_name,
                "business_overview": company_data.business_overview,
                "industry_position": company_data.industry_position,
                "policy_watchpoints": company_data.policy_watchpoints,
                "operating_signals": company_data.operating_signals,
                "source_titles": company_data.source_titles,
                "source_urls": company_data.source_urls,
                "generation_mode": "llm_summary_from_retrieval",
            },
        }

    @staticmethod
    def _build_stock_profile_section(stock_data: StockResearchData) -> dict[str, object]:
        content = (
            f"交易概览：{stock_data.trading_snapshot}。"
            f"财务概览：{stock_data.financial_snapshot}"
        )
        return {
            "heading": "股票画像",
            "content": content,
            "structured_data": {
                "security_name": stock_data.security_name,
                "trading_snapshot": stock_data.trading_snapshot,
                "financial_snapshot": stock_data.financial_snapshot,
                "filing_watchpoints": stock_data.filing_watchpoints,
                "market_signals": stock_data.market_signals,
                "source_titles": stock_data.source_titles,
                "source_urls": stock_data.source_urls,
                "generation_mode": "llm_summary_from_retrieval",
            },
        }

    @staticmethod
    def _build_commodity_profile_section(commodity_data: CommodityResearchData) -> dict[str, object]:
        content = (
            f"价格概览：{commodity_data.price_snapshot}。"
            f"供需概览：{commodity_data.supply_demand_snapshot}"
        )
        return {
            "heading": "商品画像",
            "content": content,
            "structured_data": {
                "commodity_name": commodity_data.commodity_name,
                "price_snapshot": commodity_data.price_snapshot,
                "supply_demand_snapshot": commodity_data.supply_demand_snapshot,
                "market_watchpoints": commodity_data.market_watchpoints,
                "trading_signals": commodity_data.trading_signals,
                "source_titles": commodity_data.source_titles,
                "source_urls": commodity_data.source_urls,
                "generation_mode": "llm_summary_from_retrieval",
            },
        }

    def _render_report_markdown(self, report: Report | dict) -> str:
        title = str(report.title if isinstance(report, Report) else report.get("title", "")).strip()
        summary = str(report.summary if isinstance(report, Report) else report.get("summary", "")).strip()
        body = report.body if isinstance(report, Report) else report.get("body", [])
        conclusion = str(report.conclusion if isinstance(report, Report) else report.get("conclusion", "")).strip()
        citations = report.citations if isinstance(report, Report) else report.get("citations", [])
        lines = [f"# {title}", "", "## 摘要", "", summary, ""]
        for section in body:
            heading = section.get("heading", "").strip()
            content = str(section.get("highlighted_content") or section.get("content", "")).strip()
            if heading:
                lines.extend([f"## {heading}", ""])
            if content:
                lines.extend([content, ""])
            content_segments = section.get("content_segments", [])
            if isinstance(content_segments, list) and content_segments:
                lines.append("句子证据：")
                for segment in content_segments:
                    if not isinstance(segment, dict):
                        continue
                    sentence = str(segment.get("text", "")).strip()
                    segment_indexes = segment.get("citation_indexes", [])
                    if not sentence:
                        continue
                    if isinstance(segment_indexes, list) and segment_indexes:
                        joined_segment_indexes = ", ".join(str(index) for index in segment_indexes)
                        lines.append(f"- {sentence} [{joined_segment_indexes}]")
                    else:
                        lines.append(f"- {sentence}")
                lines.append("")
            citation_indexes = section.get("citation_indexes", [])
            if isinstance(citation_indexes, list) and citation_indexes:
                joined_indexes = ", ".join(str(index) for index in citation_indexes)
                lines.extend(["", f"引用回链：[{joined_indexes}]", ""])
        lines.extend(["## 结论", "", conclusion, ""])
        if citations:
            lines.extend(["## 引用", ""])
            for index, citation in enumerate(citations, start=1):
                title = str(citation.get("highlighted_title") or citation.get("title", "")).strip()
                source = str(citation.get("source", "")).strip()
                url = str(citation.get("url", "")).strip()
                citation_line = f"{index}. {title}"
                if source:
                    citation_line += f" | {source}"
                if url:
                    citation_line += f" | {url}"
                lines.append(citation_line)
        return "\n".join(lines).strip() + "\n"

    def _generate_report_draft(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> ReportDraft:
        try:
            return self.llm_provider.generate_report(session, retrieval_bundle)
        except LLMProviderError:
            fallback = MockLLMProvider()
            return fallback.generate_report(session, retrieval_bundle)

    def _generate_follow_up_draft(
        self,
        report: Report,
        session: ResearchSession,
        question: str,
        section: dict | None = None,
        citations: list[dict] | None = None,
    ) -> FollowUpDraft:
        try:
            return self.llm_provider.answer_follow_up(
                report,
                session,
                question,
                section=section,
                citations=citations,
            )
        except LLMProviderError:
            fallback = MockLLMProvider()
            return fallback.answer_follow_up(
                report,
                session,
                question,
                section=section,
                citations=citations,
            )

    @staticmethod
    def _resolve_report_section(report: Report, paragraph_index: int | None) -> dict | None:
        if paragraph_index is None:
            return None
        if paragraph_index < 0:
            raise ValueError("paragraph_index must be >= 0")
        if paragraph_index >= len(report.body):
            raise ValueError("paragraph_index is out of range")
        section = report.body[paragraph_index]
        return {
            "index": paragraph_index,
            "heading": str(section.get("heading", "")).strip(),
            "content": str(section.get("content", "")).strip(),
            "citation_indexes": list(section.get("citation_indexes", []))
            if isinstance(section.get("citation_indexes"), list)
            else [],
            "evidence_items": list(section.get("evidence_items", []))
            if isinstance(section.get("evidence_items"), list)
            else [],
            "content_segments": list(section.get("content_segments", []))
            if isinstance(section.get("content_segments"), list)
            else [],
        }

    @staticmethod
    def _resolve_report_section_payload(report: dict, paragraph_index: int | None) -> dict | None:
        if paragraph_index is None:
            return None
        body = report.get("body", [])
        if not isinstance(body, list):
            raise ValueError("report body is invalid")
        if paragraph_index < 0:
            raise ValueError("paragraph_index must be >= 0")
        if paragraph_index >= len(body):
            raise ValueError("paragraph_index is out of range")
        section = body[paragraph_index]
        if not isinstance(section, dict):
            raise ValueError("report section is invalid")
        return {
            "index": paragraph_index,
            "heading": str(section.get("highlighted_heading") or section.get("heading", "")).strip(),
            "content": str(section.get("highlighted_content") or section.get("content", "")).strip(),
            "citation_indexes": list(section.get("citation_indexes", []))
            if isinstance(section.get("citation_indexes"), list)
            else [],
            "evidence_items": list(section.get("evidence_items", []))
            if isinstance(section.get("evidence_items"), list)
            else [],
            "content_segments": list(section.get("content_segments", []))
            if isinstance(section.get("content_segments"), list)
            else [],
        }

    @staticmethod
    def _resolve_follow_up_citations(report: Report, section: dict | None = None) -> list[dict]:
        if not report.citations:
            return []
        if not section:
            return report.citations[:3]
        section_indexes = section.get("citation_indexes")
        if isinstance(section_indexes, list) and section_indexes:
            resolved = []
            for index in section_indexes:
                if isinstance(index, int) and 1 <= index <= len(report.citations):
                    resolved.append(report.citations[index - 1])
            if resolved:
                return resolved[:3]
        heading = str(section.get("heading", "")).strip().lower()
        content = str(section.get("content", "")).strip().lower()
        matched: list[dict] = []
        for citation in report.citations:
            title = str(citation.get("title", "")).strip().lower()
            source = str(citation.get("source", "")).strip().lower()
            if heading and heading in title:
                matched.append(citation)
                continue
            if source and source in content:
                matched.append(citation)
        if matched:
            return matched[:3]
        return report.citations[:3]

    @staticmethod
    def _attach_section_evidence(body: list[dict[str, str]], citations: list[dict]) -> list[dict[str, object]]:
        category_aliases = {
            "摘要": ["general", "fundamentals"],
            "信息整合": ["market", "policy", "fundamentals", "general"],
            "结论建议": ["policy", "market", "general"],
            "结论": ["policy", "market", "general"],
        }
        enriched: list[dict[str, object]] = []
        for position, section in enumerate(body):
            heading = str(section.get("heading", "")).strip()
            preferred_categories = category_aliases.get(heading, ["general", "fundamentals", "market"])
            citation_indexes = ResearchService._select_section_citation_indexes(
                citations,
                preferred_categories,
                fallback_start=position,
            )
            evidence_items = [
                {
                    "index": citation_index,
                    "title": str(citations[citation_index - 1].get("title", "")).strip(),
                    "source": str(citations[citation_index - 1].get("source", "")).strip(),
                    "url": str(citations[citation_index - 1].get("url", "")).strip(),
                }
                for citation_index in citation_indexes
                if 1 <= citation_index <= len(citations)
            ]
            enriched.append(
                {
                    **section,
                    "citation_indexes": citation_indexes,
                    "evidence_items": evidence_items,
                    "content_segments": ResearchService._build_content_segments(
                        str(section.get("content", "")).strip(),
                        citation_indexes,
                        evidence_items,
                    ),
                }
            )
        return enriched

    @staticmethod
    def _select_section_citation_indexes(
        citations: list[dict],
        preferred_categories: list[str],
        fallback_start: int = 0,
    ) -> list[int]:
        matched_indexes: list[int] = []
        for index, citation in enumerate(citations, start=1):
            category = str(citation.get("category", "general")).strip().lower()
            if category in preferred_categories:
                matched_indexes.append(index)
            if len(matched_indexes) >= 2:
                break
        if matched_indexes:
            return matched_indexes
        if not citations:
            return []
        fallback_index = min(fallback_start + 1, len(citations))
        return [fallback_index]

    @staticmethod
    def _build_content_segments(
        content: str,
        citation_indexes: list[int],
        evidence_items: list[dict],
    ) -> list[dict[str, object]]:
        sentences = ResearchService._split_content_sentences(content)
        if not sentences:
            return []
        if not citation_indexes:
            return [{"text": sentence, "citation_indexes": [], "evidence_items": []} for sentence in sentences]
        segments: list[dict[str, object]] = []
        for position, sentence in enumerate(sentences):
            selected_index = citation_indexes[position % len(citation_indexes)]
            sentence_evidence_items = [
                item
                for item in evidence_items
                if item.get("index") == selected_index
            ]
            segments.append(
                {
                    "text": sentence,
                    "citation_indexes": [selected_index],
                    "evidence_items": sentence_evidence_items,
                }
            )
        return segments

    @staticmethod
    def _split_content_sentences(content: str) -> list[str]:
        if not content.strip():
            return []
        raw_segments = re.split(r"(?<=[。！？!?；;])\s*", content.strip())
        return [segment.strip() for segment in raw_segments if segment.strip()]


class ResearchJobRunner:
    def __init__(self, research_service: ResearchService) -> None:
        self.research_service = research_service

    def enqueue(self, job_id: str) -> None:
        worker = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        worker.start()

    def _run_job(self, job_id: str) -> None:
        try:
            self.research_service.process_job(job_id)
        except Exception:
            return
