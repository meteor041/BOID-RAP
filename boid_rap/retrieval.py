from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse
from typing import Any, Protocol
from urllib import error, request

from boid_rap.domain import ObjectType, ResearchSession, utc_now


OBJECT_STRATEGY_INCLUDE_DOMAINS: dict[str, list[str]] = {
    ObjectType.COMPANY.value: [
        "qcc.com",
        "tianyancha.com",
        "finance.sina.com.cn",
        "36kr.com",
        "stcn.com",
    ],
    ObjectType.STOCK.value: [
        "cninfo.com.cn",
        "eastmoney.com",
        "finance.sina.com.cn",
        "stcn.com",
        "10jqka.com.cn",
    ],
    ObjectType.COMMODITY.value: [
        "100ppi.com",
        "sci99.com",
        "oilchem.net",
        "cngold.org",
        "51qh.com",
    ],
}

OBJECT_STRATEGY_EXCLUDE_DOMAINS: dict[str, list[str]] = {
    ObjectType.COMPANY.value: ["m.liepin.com"],
    ObjectType.STOCK.value: [],
    ObjectType.COMMODITY.value: [],
}


@dataclass
class RetrievalDocument:
    title: str
    summary: str
    source: str
    url: str
    published_at: str = field(default_factory=utc_now)
    tags: list[str] = field(default_factory=list)
    score: float = 0.0
    category: str = "general"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RetrievalBundle:
    provider: str
    object_name: str
    object_type: str
    documents: list[RetrievalDocument]
    created_at: str = field(default_factory=utc_now)
    grouped_documents: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["documents"] = [item.to_dict() for item in self.documents]
        return data


class RetrievalProvider(Protocol):
    name: str

    def search(self, session: ResearchSession) -> RetrievalBundle:
        ...


class RetrievalProviderError(RuntimeError):
    pass


def enrich_retrieval_bundle(bundle: RetrievalBundle) -> RetrievalBundle:
    scored_documents = [enrich_retrieval_document(item, bundle.object_type) for item in bundle.documents]
    deduped_documents = dedupe_retrieval_documents(scored_documents)
    sorted_documents = sorted(deduped_documents, key=lambda item: (-item.score, item.title))
    grouped = group_retrieval_documents(sorted_documents)
    return RetrievalBundle(
        provider=bundle.provider,
        object_name=bundle.object_name,
        object_type=bundle.object_type,
        documents=sorted_documents,
        created_at=bundle.created_at,
        grouped_documents=grouped,
    )


def enrich_retrieval_document(document: RetrievalDocument, object_type: str) -> RetrievalDocument:
    source = document.source.strip().lower()
    title = document.title.strip().lower()
    url = document.url.strip().lower()
    summary = document.summary.strip().lower()
    tags = list(document.tags)
    if object_type not in tags:
        tags.append(object_type)
    category = infer_document_category(title, summary, tags, object_type)
    score = score_document(source, title, summary, object_type)
    return RetrievalDocument(
        title=document.title,
        summary=document.summary,
        source=document.source,
        url=document.url,
        published_at=document.published_at,
        tags=tags,
        score=score,
        category=category,
    )


def dedupe_retrieval_documents(documents: list[RetrievalDocument]) -> list[RetrievalDocument]:
    seen: dict[str, RetrievalDocument] = {}
    for item in documents:
        key = build_document_dedupe_key(item)
        existing = seen.get(key)
        if existing is None or item.score > existing.score:
            seen[key] = item
    return list(seen.values())


def build_document_dedupe_key(document: RetrievalDocument) -> str:
    normalized_url = normalize_document_url(document.url)
    if normalized_url:
        return f"url::{normalized_url}"
    normalized_title = "".join(ch for ch in document.title.lower() if ch.isalnum())
    normalized_source = document.source.lower().strip()
    return f"title::{normalized_source}::{normalized_title}"


def normalize_document_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


def infer_document_category(title: str, summary: str, tags: list[str], object_type: str) -> str:
    text = f"{title} {summary} {' '.join(tags)}"
    if object_type == ObjectType.COMPANY.value:
        if any(keyword in text for keyword in ["财报", "业绩", "经营", "收入", "利润"]):
            return "fundamentals"
        if any(keyword in text for keyword in ["政策", "监管", "合规"]):
            return "policy"
        if any(keyword in text for keyword in ["出海", "海外", "竞争", "行业"]):
            return "market"
    if object_type == ObjectType.STOCK.value:
        if any(keyword in text for keyword in ["公告", "财报", "估值", "机构"]):
            return "financials"
        if any(keyword in text for keyword in ["行情", "涨跌", "价格", "股价"]):
            return "market"
    if object_type == ObjectType.COMMODITY.value:
        if any(keyword in text for keyword in ["库存", "供需", "产量", "价格"]):
            return "supply_demand"
        if any(keyword in text for keyword in ["期货", "现货", "报价"]):
            return "pricing"
    return "general"


def score_document(source: str, title: str, summary: str, object_type: str) -> float:
    score = 0.0
    source_boosts = {
        "cninfo.com.cn": 3.0,
        "eastmoney.com": 2.5,
        "finance.sina.com.cn": 2.0,
        "stcn.com": 2.0,
        "qcc.com": 2.0,
        "tianyancha.com": 1.8,
        "100ppi.com": 2.2,
        "sci99.com": 2.0,
        "oilchem.net": 2.0,
    }
    for domain, boost in source_boosts.items():
        if domain in source:
            score += boost
    text = f"{title} {summary}"
    keyword_boosts = {
        ObjectType.COMPANY.value: ["经营", "财报", "行业", "政策", "海外"],
        ObjectType.STOCK.value: ["公告", "财报", "估值", "机构", "股价"],
        ObjectType.COMMODITY.value: ["供需", "库存", "价格", "期货", "现货"],
    }
    for keyword in keyword_boosts.get(object_type, []):
        if keyword in text:
            score += 0.5
    return round(score, 2)


def group_retrieval_documents(documents: list[RetrievalDocument]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in documents:
        grouped.setdefault(item.category, []).append(item.to_dict())
    return grouped


class MockRetrievalProvider:
    name = "mock_deepsearch"

    def search(self, session: ResearchSession) -> RetrievalBundle:
        object_type = (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        focus_text = "、".join(session.focus_areas) if session.focus_areas else "基本面"
        docs = [
            RetrievalDocument(
                title=f"{session.object_name}基础信息综述",
                summary=f"围绕{session.object_name}的{focus_text}做基础梳理，包含主体情况与关键背景。",
                source="Mock Corporate Registry",
                url=f"https://example.com/{object_type}/{session.object_name}/overview",
                tags=[object_type, "overview"],
            ),
            RetrievalDocument(
                title=f"{session.object_name}市场与行业信号",
                summary=f"聚合{session.object_name}相关的行业环境、竞争格局与市场信号。",
                source="Mock Market Intelligence",
                url=f"https://example.com/{object_type}/{session.object_name}/market",
                tags=[object_type, "market"],
            ),
            RetrievalDocument(
                title=f"{session.object_name}政策与风险观察",
                summary=f"归纳{session.object_name}相关政策、舆情与潜在风险点。",
                source="Mock Policy Monitor",
                url=f"https://example.com/{object_type}/{session.object_name}/risk",
                tags=[object_type, "risk"],
            ),
        ]
        return RetrievalBundle(
            provider=self.name,
            object_name=session.object_name,
            object_type=object_type,
            documents=docs,
        )


class HttpRetrievalProvider:
    name = "http_deepsearch"

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        enabled: bool = False,
        timeout: float = 10.0,
        method: str = "POST",
        api_key_header: str = "Authorization",
        request_body_template: dict[str, Any] | None = None,
        request_headers: dict[str, str] | None = None,
        response_mapping: dict[str, Any] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.enabled = enabled
        self.timeout = timeout
        self.method = method.upper()
        self.api_key_header = api_key_header
        self.request_body_template = request_body_template
        self.request_headers = request_headers or {}
        self.response_mapping = response_mapping or {}

    def search(self, session: ResearchSession) -> RetrievalBundle:
        if not self.enabled:
            raise RetrievalProviderError("http retrieval provider is configured but disabled")
        payload = self._build_payload(session)
        headers = {"Content-Type": "application/json", "Accept": "application/json", **self.request_headers}
        if self.api_key:
            if self.api_key_header.lower() == "authorization":
                headers[self.api_key_header] = f"Bearer {self.api_key}"
            else:
                headers[self.api_key_header] = self.api_key
        req = request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if self.method != "GET" else None,
            headers=headers,
            method=self.method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RetrievalProviderError(
                f"http retrieval provider request failed with status {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RetrievalProviderError(
                f"http retrieval provider network error: {exc.reason}"
            ) from exc
        except Exception as exc:
            raise RetrievalProviderError(f"http retrieval provider request failed: {exc}") from exc

        try:
            raw = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RetrievalProviderError("http retrieval provider returned invalid JSON") from exc
        return self._parse_response(session, raw)

    def _build_payload(self, session: ResearchSession) -> dict:
        object_type = (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        context = {
            "object_name": session.object_name,
            "object_type": object_type,
            "query": session.query,
            "focus_areas": session.focus_areas,
            "time_range": session.time_range,
            "authority_level": session.authority_level,
            "depth": session.depth,
            "session_id": session.id,
            "model_id": session.model_id,
        }
        if self.request_body_template:
            rendered = self._render_value(self.request_body_template, context)
            if not isinstance(rendered, dict):
                raise RetrievalProviderError("http retrieval provider request template must render to an object")
            return rendered
        return context

    def _parse_response(self, session: ResearchSession, payload: dict) -> RetrievalBundle:
        documents = self._resolve_documents(payload)
        if not isinstance(documents, list) or not documents:
            raise RetrievalProviderError("http retrieval provider returned no documents")

        object_type = self._resolve_scalar(payload, "object_type") or (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        object_name = self._resolve_scalar(payload, "object_name") or session.object_name
        provider = self._resolve_scalar(payload, "provider") or self.name
        created_at = self._resolve_scalar(payload, "created_at") or utc_now()

        normalized_documents: list[RetrievalDocument] = []
        for index, item in enumerate(documents):
            if not isinstance(item, dict):
                raise RetrievalProviderError(
                    f"http retrieval provider document at index {index} is not an object"
                )
            title = str(self._resolve_document_field(item, "title") or "").strip()
            summary = str(self._resolve_document_field(item, "summary") or "").strip()
            source = str(self._resolve_document_field(item, "source") or "HTTP Retrieval").strip()
            url = str(self._resolve_document_field(item, "url") or "").strip()
            if not title:
                raise RetrievalProviderError(
                    f"http retrieval provider document at index {index} is missing title"
                )
            tags = self._resolve_document_field(item, "tags")
            if not isinstance(tags, list):
                tags = []
            normalized_documents.append(
                RetrievalDocument(
                    title=title,
                    summary=summary,
                    source=source,
                    url=url,
                    published_at=str(self._resolve_document_field(item, "published_at") or utc_now()),
                    tags=[str(tag) for tag in tags],
                )
            )

        return enrich_retrieval_bundle(RetrievalBundle(
            provider=str(provider),
            object_name=str(object_name),
            object_type=str(object_type),
            documents=normalized_documents,
            created_at=str(created_at),
        ))

    def _resolve_documents(self, payload: dict) -> Any:
        path = self.response_mapping.get("documents_path")
        if isinstance(path, str):
            return self._get_path(payload, path)
        return payload.get("documents") or payload.get("items") or payload.get("results")

    def _resolve_scalar(self, payload: dict, field_name: str) -> Any:
        path = self.response_mapping.get(f"{field_name}_path")
        if isinstance(path, str):
            return self._get_path(payload, path)
        return payload.get(field_name)

    def _resolve_document_field(self, item: dict, field_name: str) -> Any:
        document_fields = self.response_mapping.get("document_fields")
        if isinstance(document_fields, dict):
            mapped = document_fields.get(field_name)
            if isinstance(mapped, str):
                return self._get_path(item, mapped)
            if isinstance(mapped, list):
                for path in mapped:
                    if isinstance(path, str):
                        value = self._get_path(item, path)
                        if value not in (None, "", []):
                            return value
        defaults = {
            "title": ["title", "name"],
            "summary": ["summary", "snippet", "content"],
            "source": ["source", "publisher"],
            "url": ["url", "link"],
            "published_at": ["published_at", "publishedAt"],
            "tags": ["tags"],
        }
        for key in defaults.get(field_name, [field_name]):
            value = self._get_path(item, key)
            if value not in (None, "", []):
                return value
        return None

    def _render_value(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: self._render_value(inner, context) for key, inner in value.items()}
        if isinstance(value, list):
            return [self._render_value(item, context) for item in value]
        if isinstance(value, str):
            if value.startswith("{{") and value.endswith("}}"):
                return self._get_path(context, value[2:-2].strip())
            return value
        return value

    def _get_path(self, payload: Any, path: str) -> Any:
        current = payload
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


class TavilyRetrievalProvider(HttpRetrievalProvider):
    name = "tavily_search"

    def __init__(
        self,
        api_key: str | None = None,
        enabled: bool = False,
        timeout: float = 10.0,
        endpoint: str = "https://api.tavily.com/search",
        max_results: int = 5,
        include_raw_content: str | bool = "text",
        include_favicon: bool = True,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> None:
        super().__init__(
            endpoint=endpoint,
            api_key=api_key,
            enabled=enabled,
            timeout=timeout,
            method="POST",
            api_key_header="Authorization",
            response_mapping={
                "documents_path": "results",
                "document_fields": {
                    "title": ["title", "url"],
                    "summary": ["content", "raw_content"],
                    "source": ["url", "favicon"],
                    "url": "url",
                },
            },
        )
        self.max_results = max_results
        self.include_raw_content = include_raw_content
        self.include_favicon = include_favicon
        self.search_depth = search_depth
        self.include_domains = include_domains or []
        self.exclude_domains = exclude_domains or []

    def search(self, session: ResearchSession) -> RetrievalBundle:
        try:
            return super().search(session)
        except RetrievalProviderError as exc:
            if "returned no documents" not in str(exc):
                raise
            payload = self._build_payload(session, relaxed_domains=True)
            return self._search_with_payload(session, payload)

    def _build_payload(self, session: ResearchSession, relaxed_domains: bool = False) -> dict:
        object_type = (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        strategy = self._build_object_strategy(session)
        payload = {
            "query": strategy["query"],
            "topic": strategy["topic"],
            "search_depth": self.search_depth,
            "max_results": self.max_results,
            "include_raw_content": self.include_raw_content,
            "include_favicon": self.include_favicon,
            "time_range": strategy["time_range"],
        }
        include_domains = ([] if relaxed_domains else strategy["include_domains"]) or self.include_domains
        exclude_domains = ([] if relaxed_domains else strategy["exclude_domains"]) or self.exclude_domains
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        return payload

    def _parse_response(self, session: ResearchSession, payload: dict) -> RetrievalBundle:
        bundle = super()._parse_response(session, payload)
        normalized_documents: list[RetrievalDocument] = []
        for item in bundle.documents:
            normalized_documents.append(
                RetrievalDocument(
                    title=item.title,
                    summary=item.summary,
                    source=self._normalize_source(item.source, item.url),
                    url=item.url,
                    published_at=item.published_at,
                    tags=item.tags,
                )
            )
        bundle.documents = normalized_documents
        bundle.provider = self.name
        return enrich_retrieval_bundle(bundle)

    def _build_query(self, session: ResearchSession) -> str:
        object_type = (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        if object_type == ObjectType.COMPANY.value:
            return self._build_company_query(session)
        if object_type == ObjectType.STOCK.value:
            return self._build_stock_query(session)
        if object_type == ObjectType.COMMODITY.value:
            return self._build_commodity_query(session)
        return self._build_generic_query(session)

    def _build_object_strategy(self, session: ResearchSession) -> dict[str, Any]:
        object_type = (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        include_domains = self._select_include_domains(object_type, session.authority_level)
        exclude_domains = OBJECT_STRATEGY_EXCLUDE_DOMAINS.get(object_type, [])
        return {
            "query": self._build_query(session),
            "topic": self._map_topic(object_type),
            "time_range": self._map_time_range(session.time_range),
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
        }

    def _build_generic_query(self, session: ResearchSession) -> str:
        focus = f" 重点关注：{'、'.join(session.focus_areas)}" if session.focus_areas else ""
        query = f" 调研问题：{session.query}" if session.query else ""
        return f"{session.object_name} {self._object_label(session)} 深度调研{focus}{query}".strip()

    def _build_company_query(self, session: ResearchSession) -> str:
        focus = "、".join(session.focus_areas) if session.focus_areas else "经营数据、行业地位、政策动态"
        query = f" 补充问题：{session.query}" if session.query else ""
        return (
            f"{session.object_name} 公司调研 关注企业资质、经营数据、行业竞争、政策影响、海外进展。"
            f"重点领域：{focus}。{query}"
        ).strip()

    def _build_stock_query(self, session: ResearchSession) -> str:
        focus = "、".join(session.focus_areas) if session.focus_areas else "行情表现、财务报表、估值、市场舆情"
        query = f" 补充问题：{session.query}" if session.query else ""
        return (
            f"{session.object_name} 股票调研 关注行情走势、财报表现、估值变化、机构观点、市场情绪。"
            f"重点领域：{focus}。{query}"
        ).strip()

    def _build_commodity_query(self, session: ResearchSession) -> str:
        focus = "、".join(session.focus_areas) if session.focus_areas else "价格走势、供需关系、库存变化、竞品替代"
        query = f" 补充问题：{session.query}" if session.query else ""
        return (
            f"{session.object_name} 商品调研 关注价格走势、供需格局、库存变化、进出口、下游需求。"
            f"重点领域：{focus}。{query}"
        ).strip()

    def _object_label(self, session: ResearchSession) -> str:
        object_type = (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        return {
            "company": "公司",
            "stock": "股票",
            "commodity": "商品",
        }.get(object_type, "对象")

    def _map_topic(self, object_type: str) -> str:
        if object_type in {"company", "stock"}:
            return "finance"
        return "general"

    def _map_time_range(self, time_range: str) -> str:
        mapping = {
            "recent_7_days": "week",
            "recent_30_days": "month",
            "recent_3_months": "month",
            "recent_6_months": "year",
            "recent_12_months": "year",
        }
        return mapping.get(time_range, "month")

    def _select_include_domains(self, object_type: str, authority_level: str) -> list[str]:
        if authority_level not in {"high", "very_high"}:
            return []
        return OBJECT_STRATEGY_INCLUDE_DOMAINS.get(object_type, [])

    def _normalize_source(self, source: str, url: str) -> str:
        if source.startswith("http://") or source.startswith("https://"):
            try:
                return source.split("//", 1)[1].split("/", 1)[0]
            except Exception:
                return source
        if source:
            return source
        if url.startswith("http://") or url.startswith("https://"):
            try:
                return url.split("//", 1)[1].split("/", 1)[0]
            except Exception:
                return url
        return "Tavily"

    def _search_with_payload(self, session: ResearchSession, payload: dict) -> RetrievalBundle:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method=self.method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RetrievalProviderError(
                f"http retrieval provider request failed with status {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RetrievalProviderError(
                f"http retrieval provider network error: {exc.reason}"
            ) from exc
        except Exception as exc:
            raise RetrievalProviderError(f"http retrieval provider request failed: {exc}") from exc
        try:
            raw = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RetrievalProviderError("http retrieval provider returned invalid JSON") from exc
        return self._parse_response(session, raw)


class RetrievalRegistry:
    def __init__(self, providers: list[RetrievalProvider], default_provider: str) -> None:
        if not providers:
            raise ValueError("at least one retrieval provider is required")
        self._providers = {provider.name: provider for provider in providers}
        if default_provider not in self._providers:
            raise ValueError(f"default retrieval provider '{default_provider}' is not registered")
        self.default_provider = default_provider

    def list_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    def get_provider(self, provider_name: str | None = None) -> RetrievalProvider:
        resolved_name = provider_name or self.default_provider
        provider = self._providers.get(resolved_name)
        if not provider:
            raise RetrievalProviderError(f"retrieval provider '{resolved_name}' is not registered")
        return provider

    def search(self, session: ResearchSession, provider_name: str | None = None) -> RetrievalBundle:
        provider = self.get_provider(provider_name)
        return provider.search(session)
