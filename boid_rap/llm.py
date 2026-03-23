from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request

from boid_rap.domain import ObjectType, Report, ResearchSession
from boid_rap.retrieval import RetrievalBundle


@dataclass
class ReportDraft:
    title: str
    summary: str
    body: list[dict[str, str]]
    conclusion: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "body": self.body,
            "conclusion": self.conclusion,
        }


@dataclass
class FollowUpDraft:
    answer: str

    def to_dict(self) -> dict:
        return {"answer": self.answer}


@dataclass
class CompanyProfileDraft:
    registered_name: str
    business_overview: str
    industry_position: str
    policy_watchpoints: list[str]
    operating_signals: list[str]
    confidence: str = "medium"

    def to_dict(self) -> dict:
        return {
            "registered_name": self.registered_name,
            "business_overview": self.business_overview,
            "industry_position": self.industry_position,
            "policy_watchpoints": self.policy_watchpoints,
            "operating_signals": self.operating_signals,
            "confidence": self.confidence,
        }


@dataclass
class StockProfileDraft:
    security_name: str
    trading_snapshot: str
    financial_snapshot: str
    filing_watchpoints: list[str]
    market_signals: list[str]
    confidence: str = "medium"

    def to_dict(self) -> dict:
        return {
            "security_name": self.security_name,
            "trading_snapshot": self.trading_snapshot,
            "financial_snapshot": self.financial_snapshot,
            "filing_watchpoints": self.filing_watchpoints,
            "market_signals": self.market_signals,
            "confidence": self.confidence,
        }


@dataclass
class CommodityProfileDraft:
    commodity_name: str
    price_snapshot: str
    supply_demand_snapshot: str
    market_watchpoints: list[str]
    trading_signals: list[str]
    confidence: str = "medium"

    def to_dict(self) -> dict:
        return {
            "commodity_name": self.commodity_name,
            "price_snapshot": self.price_snapshot,
            "supply_demand_snapshot": self.supply_demand_snapshot,
            "market_watchpoints": self.market_watchpoints,
            "trading_signals": self.trading_signals,
            "confidence": self.confidence,
        }


class LLMProvider(Protocol):
    name: str

    def generate_report(self, session: ResearchSession, retrieval_bundle: RetrievalBundle | None = None) -> ReportDraft:
        ...

    def answer_follow_up(
        self,
        report: Report,
        session: ResearchSession,
        question: str,
        section: dict | None = None,
        citations: list[dict] | None = None,
    ) -> FollowUpDraft:
        ...

    def generate_company_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> CompanyProfileDraft:
        ...

    def generate_stock_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> StockProfileDraft:
        ...

    def generate_commodity_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> CommodityProfileDraft:
        ...


class LLMProviderError(RuntimeError):
    pass


class MockLLMProvider:
    name = "mock_llm"

    def generate_report(self, session: ResearchSession, retrieval_bundle: RetrievalBundle | None = None) -> ReportDraft:
        object_key = (
            session.object_type.value
            if isinstance(session.object_type, ObjectType)
            else session.object_type
        )
        object_label = {
            ObjectType.COMPANY.value: "公司",
            ObjectType.STOCK.value: "股票",
            ObjectType.COMMODITY.value: "商品",
        }[object_key]
        focus_text = "、".join(session.focus_areas) if session.focus_areas else "综合基本面"
        retrieval_documents = retrieval_bundle.documents if retrieval_bundle else []
        top_titles = "；".join(item.title for item in retrieval_documents[:2]) if retrieval_documents else "暂无外部检索结果"
        provider = retrieval_bundle.provider if retrieval_bundle else "mock"
        return ReportDraft(
            title=f"{session.object_name}{object_label}调研报告",
            summary=f"已完成针对 {session.object_name} 的结构化调研分析。",
            body=[
                {
                    "heading": "摘要",
                    "content": (
                        f"围绕{session.object_name}开展{object_label}调研，结合研究深度“{session.depth}”"
                        f"与重点领域“{focus_text}”，形成初步研究结论。"
                    ),
                },
                {
                    "heading": "信息整合",
                    "content": (
                        "平台按对象类型聚合经营信息、市场表现、行业环境、政策与舆情等多源线索。"
                        f"当前检索提供方为 {provider}，命中的核心材料包括：{top_titles}。"
                    ),
                },
                {
                    "heading": "结论建议",
                    "content": (
                        "建议将报告作为研究底稿，继续补充实时行情、财报、公告、研报与政策数据，"
                        "再进入最终投资或经营判断。"
                    ),
                },
            ],
            conclusion="当前版本已完成研究流程骨架，真实结论需在接入外部数据与模型后增强。",
        )

    def answer_follow_up(
        self,
        report: Report,
        session: ResearchSession,
        question: str,
        section: dict | None = None,
        citations: list[dict] | None = None,
    ) -> FollowUpDraft:
        references = []
        reference_pool = citations if citations is not None else report.citations[:2]
        for item in reference_pool[:3]:
            title = str(item.get("title", "")).strip()
            source = str(item.get("source", "")).strip()
            if title and source:
                references.append(f"{title}（{source}）")
            elif title:
                references.append(title)
        reference_text = "；".join(references) if references else "当前报告引用"
        section_text = ""
        if section:
            heading = str(section.get("heading", "")).strip()
            if heading:
                section_text = f"本次追问聚焦报告段落《{heading}》。"
        return FollowUpDraft(
            answer=(
                f"基于《{report.title}》和当前会话上下文，针对“{question.strip()}”，"
                f"{section_text}现阶段可以先从报告摘要、结论以及引用材料继续展开。"
                f"当前最相关的参考包括：{reference_text}。"
                "如果需要更精确结论，建议进一步补充最新公告、财务和行业数据。"
            )
        )

    def generate_company_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> CompanyProfileDraft:
        documents = retrieval_bundle.documents if retrieval_bundle else []
        fundamentals = [item for item in documents if item.category == "fundamentals"]
        market_docs = [item for item in documents if item.category == "market"]
        policy_docs = [item for item in documents if item.category == "policy"]
        return CompanyProfileDraft(
            registered_name=(
                session.object_name
                if any(token in session.object_name for token in ["集团", "公司", "股份"])
                else f"{session.object_name}股份有限公司"
            ),
            business_overview=(
                fundamentals[0].summary
                if fundamentals
                else f"{session.object_name}当前处于公司画像整理阶段，已开始汇总主营业务与经营线索。"
            ),
            industry_position=(
                market_docs[0].summary
                if market_docs
                else f"{session.object_name}的行业位置仍需结合更多市场份额和竞对信息进一步验证。"
            ),
            policy_watchpoints=[
                item.summary or item.title
                for item in policy_docs[:3]
            ] or ["需持续跟踪行业监管、政策变化与合规要求。"],
            operating_signals=[
                item.summary or item.title
                for item in (fundamentals[:2] + market_docs[:2])
            ] or ["当前经营信号仍以公开检索线索为主，需继续补充财务与业务数据。"],
            confidence="medium",
        )

    def generate_stock_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> StockProfileDraft:
        documents = retrieval_bundle.documents if retrieval_bundle else []
        financial_docs = [item for item in documents if item.category in {"financials", "fundamentals"}]
        market_docs = [item for item in documents if item.category == "market"]
        return StockProfileDraft(
            security_name=session.object_name,
            trading_snapshot=(
                market_docs[0].summary
                if market_docs
                else f"{session.object_name}当前主要依赖公开检索线索观察市场走势与情绪变化。"
            ),
            financial_snapshot=(
                financial_docs[0].summary
                if financial_docs
                else f"{session.object_name}的财务与估值信息仍需进一步接入财报和公告数据校验。"
            ),
            filing_watchpoints=[
                item.summary or item.title
                for item in financial_docs[:3]
            ] or ["需持续跟踪财报、公告和重大事项披露。"],
            market_signals=[
                item.summary or item.title
                for item in market_docs[:3]
            ] or ["当前市场信号仍以公开检索线索为主，需补充更实时的行情数据。"],
            confidence="medium",
        )

    def generate_commodity_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> CommodityProfileDraft:
        documents = retrieval_bundle.documents if retrieval_bundle else []
        supply_docs = [item for item in documents if item.category == "supply_demand"]
        pricing_docs = [item for item in documents if item.category in {"pricing", "market"}]
        return CommodityProfileDraft(
            commodity_name=session.object_name,
            price_snapshot=(
                pricing_docs[0].summary
                if pricing_docs
                else f"{session.object_name}当前价格表现仍需补充现货、期货与区间走势数据。"
            ),
            supply_demand_snapshot=(
                supply_docs[0].summary
                if supply_docs
                else f"{session.object_name}的供需格局仍需继续结合库存、产量与开工率信息判断。"
            ),
            market_watchpoints=[
                item.summary or item.title
                for item in supply_docs[:3]
            ] or ["需持续跟踪库存、产量、开工率与下游需求变化。"],
            trading_signals=[
                item.summary or item.title
                for item in pricing_docs[:3]
            ] or ["当前交易信号仍以公开检索线索为主，需结合更实时的价格数据。"],
            confidence="medium",
        )


class OpenAIResponsesProvider:
    name = "openai_responses"

    def __init__(
        self,
        api_key: str | None = None,
        enabled: bool = False,
        timeout: float = 20.0,
        base_url: str = "https://api.openai.com/v1",
        endpoint: str | None = None,
        model: str = "gpt-5-mini",
    ) -> None:
        self.api_key = api_key
        self.enabled = enabled
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint or f"{self.base_url}/responses"
        self.model = model

    def generate_report(self, session: ResearchSession, retrieval_bundle: RetrievalBundle | None = None) -> ReportDraft:
        if not self.enabled:
            raise LLMProviderError("openai responses provider is configured but disabled")
        if not self.api_key:
            raise LLMProviderError("openai api key is missing")
        prompt = self._build_prompt(session, retrieval_bundle)
        req = request.Request(
            self.endpoint,
            data=json.dumps(
                {
                    "model": self.model,
                    "input": prompt,
                    "text": {"format": {"type": "json_object"}},
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise LLMProviderError(
                f"openai responses request failed with status {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise LLMProviderError(f"openai responses network error: {exc.reason}") from exc
        except Exception as exc:
            raise LLMProviderError(f"openai responses request failed: {exc}") from exc

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("openai responses provider returned invalid JSON") from exc
        text = self._extract_text(payload)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("openai responses provider returned non-json content") from exc
        return self._to_report_draft(data, session)

    def answer_follow_up(
        self,
        report: Report,
        session: ResearchSession,
        question: str,
        section: dict | None = None,
        citations: list[dict] | None = None,
    ) -> FollowUpDraft:
        if not self.enabled:
            raise LLMProviderError("openai responses provider is configured but disabled")
        if not self.api_key:
            raise LLMProviderError("openai api key is missing")
        prompt = self._build_follow_up_prompt(report, session, question, section=section, citations=citations)
        payload = self._request_json(prompt)
        text = self._extract_text(payload)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("openai responses provider returned non-json content") from exc
        answer = str(data.get("answer") or "").strip()
        if not answer:
            raise LLMProviderError("openai responses provider returned empty follow-up answer")
        return FollowUpDraft(answer=answer)

    def generate_company_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> CompanyProfileDraft:
        if not self.enabled:
            raise LLMProviderError("openai responses provider is configured but disabled")
        if not self.api_key:
            raise LLMProviderError("openai api key is missing")
        prompt = self._build_company_profile_prompt(session, retrieval_bundle)
        payload = self._request_json(prompt)
        text = self._extract_text(payload)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("openai responses provider returned non-json content") from exc
        return self._to_company_profile_draft(data, session)

    def generate_stock_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> StockProfileDraft:
        if not self.enabled:
            raise LLMProviderError("openai responses provider is configured but disabled")
        if not self.api_key:
            raise LLMProviderError("openai api key is missing")
        prompt = self._build_stock_profile_prompt(session, retrieval_bundle)
        payload = self._request_json(prompt)
        text = self._extract_text(payload)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("openai responses provider returned non-json content") from exc
        return self._to_stock_profile_draft(data, session)

    def generate_commodity_profile(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
    ) -> CommodityProfileDraft:
        if not self.enabled:
            raise LLMProviderError("openai responses provider is configured but disabled")
        if not self.api_key:
            raise LLMProviderError("openai api key is missing")
        prompt = self._build_commodity_profile_prompt(session, retrieval_bundle)
        payload = self._request_json(prompt)
        text = self._extract_text(payload)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("openai responses provider returned non-json content") from exc
        return self._to_commodity_profile_draft(data, session)

    def _build_prompt(self, session: ResearchSession, retrieval_bundle: RetrievalBundle | None) -> str:
        documents = []
        if retrieval_bundle:
            for item in retrieval_bundle.documents[:5]:
                documents.append(
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "source": item.source,
                        "url": item.url,
                    }
                )
        payload = {
            "object_name": session.object_name,
            "object_type": (
                session.object_type.value
                if isinstance(session.object_type, ObjectType)
                else session.object_type
            ),
            "depth": session.depth,
            "focus_areas": session.focus_areas,
            "query": session.query,
            "retrieval_provider": retrieval_bundle.provider if retrieval_bundle else None,
            "documents": documents,
            "output_schema": {
                "title": "string",
                "summary": "string",
                "body": [{"heading": "string", "content": "string"}],
                "conclusion": "string",
            },
        }
        return (
            "你是商业研究分析助手。请基于给定检索材料生成结构化调研报告，"
            "仅输出 JSON，对象字段必须包含 title, summary, body, conclusion。"
            "body 必须是包含 2-4 个段落对象的数组，每个对象包含 heading 和 content。"
            f"\n\n输入数据：\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _build_follow_up_prompt(
        self,
        report: Report,
        session: ResearchSession,
        question: str,
        section: dict | None = None,
        citations: list[dict] | None = None,
    ) -> str:
        payload = {
            "object_name": session.object_name,
            "object_type": (
                session.object_type.value
                if isinstance(session.object_type, ObjectType)
                else session.object_type
            ),
            "question": question,
            "report": {
                "title": report.title,
                "summary": report.summary,
                "body": report.body,
                "conclusion": report.conclusion,
                "citations": report.citations[:5],
            },
            "focused_section": section,
            "focused_citations": citations[:5] if citations else [],
            "messages": [
                {"role": item.role, "content": item.content}
                for item in session.messages[-6:]
            ],
            "output_schema": {"answer": "string"},
        }
        return (
            "你是商业研究分析助手。请基于给定报告内容、引用和会话上下文回答追问。"
            "如果提供了 focused_section，请优先围绕该段落回答。"
            "不要编造不存在于输入中的事实；如果证据不足，要明确说明。"
            "仅输出 JSON，对象字段必须包含 answer。"
            f"\n\n输入数据：\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _build_company_profile_prompt(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None,
    ) -> str:
        documents = []
        if retrieval_bundle:
            for item in retrieval_bundle.documents[:6]:
                documents.append(
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "source": item.source,
                        "url": item.url,
                        "category": item.category,
                    }
                )
        payload = {
            "company_name": session.object_name,
            "focus_areas": session.focus_areas,
            "depth": session.depth,
            "documents": documents,
            "output_schema": {
                "registered_name": "string",
                "business_overview": "string",
                "industry_position": "string",
                "policy_watchpoints": ["string"],
                "operating_signals": ["string"],
                "confidence": "low|medium|high",
            },
        }
        return (
            "你是资深金融与产业研究专家。请基于给定检索材料，输出公司的结构化画像。"
            "不要编造无法从材料支持的工商真值；不确定时应输出相对保守的归纳。"
            "仅输出 JSON，对象字段必须包含 registered_name, business_overview, industry_position, "
            "policy_watchpoints, operating_signals, confidence。"
            "JSON 示例："
            '{"registered_name":"示例科技股份有限公司","business_overview":"公司主营企业软件与云服务。",'
            '"industry_position":"在细分行业内具备一定竞争力，但市场份额仍需更多材料验证。",'
            '"policy_watchpoints":["需关注数据合规与行业监管变化。"],'
            '"operating_signals":["云服务订单保持增长","企业客户续费率有待持续跟踪"],'
            '"confidence":"medium"}'
            f"\n\n输入数据：\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _build_stock_profile_prompt(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None,
    ) -> str:
        payload = self._build_profile_payload(session, retrieval_bundle)
        payload["output_schema"] = {
            "security_name": "string",
            "trading_snapshot": "string",
            "financial_snapshot": "string",
            "filing_watchpoints": ["string"],
            "market_signals": ["string"],
            "confidence": "low|medium|high",
        }
        return (
            "你是资深金融市场研究专家。请基于给定检索材料，输出股票对象的结构化画像。"
            "不要伪造实时行情或财务真值；不确定时应给出保守归纳。"
            "仅输出 JSON，对象字段必须包含 security_name, trading_snapshot, financial_snapshot, "
            "filing_watchpoints, market_signals, confidence。"
            "JSON 示例："
            '{"security_name":"示例股份","trading_snapshot":"股价近期围绕业绩预期波动，成交活跃度有所提升。",'
            '"financial_snapshot":"财务表现整体稳健，但盈利弹性仍需结合最新财报验证。",'
            '"filing_watchpoints":["需关注季报披露和重大事项公告。"],'
            '"market_signals":["机构观点分化","估值敏感度提升"],'
            '"confidence":"medium"}'
            f"\n\n输入数据：\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _build_commodity_profile_prompt(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None,
    ) -> str:
        payload = self._build_profile_payload(session, retrieval_bundle)
        payload["output_schema"] = {
            "commodity_name": "string",
            "price_snapshot": "string",
            "supply_demand_snapshot": "string",
            "market_watchpoints": ["string"],
            "trading_signals": ["string"],
            "confidence": "low|medium|high",
        }
        return (
            "你是资深大宗商品与产业链研究专家。请基于给定检索材料，输出商品对象的结构化画像。"
            "不要伪造价格、库存或产量真值；不确定时应给出保守归纳。"
            "仅输出 JSON，对象字段必须包含 commodity_name, price_snapshot, supply_demand_snapshot, "
            "market_watchpoints, trading_signals, confidence。"
            "JSON 示例："
            '{"commodity_name":"碳酸锂","price_snapshot":"现货价格仍处于波动区间，市场情绪偏谨慎。",'
            '"supply_demand_snapshot":"供需仍在再平衡阶段，库存与下游需求需要持续跟踪。",'
            '"market_watchpoints":["需关注产能投放和下游需求恢复节奏。"],'
            '"trading_signals":["价格弹性上升","市场对库存变化较敏感"],'
            '"confidence":"medium"}'
            f"\n\n输入数据：\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _build_profile_payload(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None,
    ) -> dict:
        documents = []
        if retrieval_bundle:
            for item in retrieval_bundle.documents[:6]:
                documents.append(
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "source": item.source,
                        "url": item.url,
                        "category": item.category,
                    }
                )
        return {
            "object_name": session.object_name,
            "object_type": (
                session.object_type.value
                if isinstance(session.object_type, ObjectType)
                else session.object_type
            ),
            "focus_areas": session.focus_areas,
            "depth": session.depth,
            "documents": documents,
        }

    def _request_json(self, prompt: str) -> dict:
        req = request.Request(
            self.endpoint,
            data=json.dumps(
                {
                    "model": self.model,
                    "input": prompt,
                    "text": {"format": {"type": "json_object"}},
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise LLMProviderError(
                f"openai responses request failed with status {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise LLMProviderError(f"openai responses network error: {exc.reason}") from exc
        except Exception as exc:
            raise LLMProviderError(f"openai responses request failed: {exc}") from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("openai responses provider returned invalid JSON") from exc

    def _extract_text(self, payload: dict) -> str:
        if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
            return payload["output_text"]
        output = payload.get("output")
        if isinstance(output, list):
            collected: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                for content in item.get("content", []):
                    if isinstance(content, dict) and isinstance(content.get("text"), str):
                        collected.append(content["text"])
            if collected:
                return "\n".join(collected)
        raise LLMProviderError("openai responses provider returned no text output")

    def _to_report_draft(self, data: dict, session: ResearchSession) -> ReportDraft:
        title = str(data.get("title") or f"{session.object_name}调研报告").strip()
        summary = str(data.get("summary") or "").strip()
        conclusion = str(data.get("conclusion") or "").strip()
        body_raw = data.get("body")
        body: list[dict[str, str]] = []
        if isinstance(body_raw, list):
            for item in body_raw:
                if not isinstance(item, dict):
                    continue
                heading = str(item.get("heading") or "").strip()
                content = str(item.get("content") or "").strip()
                if heading and content:
                    body.append({"heading": heading, "content": content})
        if not body:
            raise LLMProviderError("openai responses provider returned empty body")
        return ReportDraft(
            title=title,
            summary=summary or f"已完成针对 {session.object_name} 的结构化调研分析。",
            body=body,
            conclusion=conclusion or "需结合更多实时数据进一步验证结论。",
        )

    def _to_company_profile_draft(self, data: dict, session: ResearchSession) -> CompanyProfileDraft:
        registered_name = str(data.get("registered_name") or session.object_name).strip()
        business_overview = str(data.get("business_overview") or "").strip()
        industry_position = str(data.get("industry_position") or "").strip()
        policy_watchpoints = data.get("policy_watchpoints")
        operating_signals = data.get("operating_signals")
        confidence = str(data.get("confidence") or "medium").strip().lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"
        if not business_overview:
            raise LLMProviderError("openai responses provider returned empty business_overview")
        if not industry_position:
            raise LLMProviderError("openai responses provider returned empty industry_position")
        return CompanyProfileDraft(
            registered_name=registered_name,
            business_overview=business_overview,
            industry_position=industry_position,
            policy_watchpoints=[
                str(item).strip()
                for item in (policy_watchpoints if isinstance(policy_watchpoints, list) else [])
                if str(item).strip()
            ] or ["需持续跟踪行业监管与政策变化。"],
            operating_signals=[
                str(item).strip()
                for item in (operating_signals if isinstance(operating_signals, list) else [])
                if str(item).strip()
            ] or ["当前经营信号仍需结合更多结构化经营数据补充验证。"],
            confidence=confidence,
        )

    def _to_stock_profile_draft(self, data: dict, session: ResearchSession) -> StockProfileDraft:
        trading_snapshot = str(data.get("trading_snapshot") or "").strip()
        financial_snapshot = str(data.get("financial_snapshot") or "").strip()
        confidence = str(data.get("confidence") or "medium").strip().lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"
        if not trading_snapshot or not financial_snapshot:
            raise LLMProviderError("openai responses provider returned incomplete stock profile")
        return StockProfileDraft(
            security_name=str(data.get("security_name") or session.object_name).strip(),
            trading_snapshot=trading_snapshot,
            financial_snapshot=financial_snapshot,
            filing_watchpoints=[
                str(item).strip()
                for item in (data.get("filing_watchpoints") if isinstance(data.get("filing_watchpoints"), list) else [])
                if str(item).strip()
            ] or ["需持续关注财报、公告和重大事项披露。"],
            market_signals=[
                str(item).strip()
                for item in (data.get("market_signals") if isinstance(data.get("market_signals"), list) else [])
                if str(item).strip()
            ] or ["市场信号仍需结合更实时的行情和资金流数据。"],
            confidence=confidence,
        )

    def _to_commodity_profile_draft(self, data: dict, session: ResearchSession) -> CommodityProfileDraft:
        price_snapshot = str(data.get("price_snapshot") or "").strip()
        supply_demand_snapshot = str(data.get("supply_demand_snapshot") or "").strip()
        confidence = str(data.get("confidence") or "medium").strip().lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"
        if not price_snapshot or not supply_demand_snapshot:
            raise LLMProviderError("openai responses provider returned incomplete commodity profile")
        return CommodityProfileDraft(
            commodity_name=str(data.get("commodity_name") or session.object_name).strip(),
            price_snapshot=price_snapshot,
            supply_demand_snapshot=supply_demand_snapshot,
            market_watchpoints=[
                str(item).strip()
                for item in (data.get("market_watchpoints") if isinstance(data.get("market_watchpoints"), list) else [])
                if str(item).strip()
            ] or ["需持续关注库存、产量和下游需求变化。"],
            trading_signals=[
                str(item).strip()
                for item in (data.get("trading_signals") if isinstance(data.get("trading_signals"), list) else [])
                if str(item).strip()
            ] or ["交易信号仍需结合更实时的价格与持仓数据。"],
            confidence=confidence,
        )
