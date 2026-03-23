from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol

from boid_rap.domain import ObjectType, ResearchSession, utc_now
from boid_rap.llm import (
    CommodityProfileDraft,
    CompanyProfileDraft,
    LLMProvider,
    LLMProviderError,
    StockProfileDraft,
)
from boid_rap.retrieval import RetrievalBundle, RetrievalDocument


@dataclass
class CompanyResearchData:
    company_name: str
    registered_name: str
    business_overview: str
    industry_position: str
    policy_watchpoints: list[str]
    operating_signals: list[str]
    source_titles: list[str]
    source_urls: list[str]
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StockResearchData:
    security_name: str
    trading_snapshot: str
    financial_snapshot: str
    filing_watchpoints: list[str]
    market_signals: list[str]
    source_titles: list[str]
    source_urls: list[str]
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CommodityResearchData:
    commodity_name: str
    price_snapshot: str
    supply_demand_snapshot: str
    market_watchpoints: list[str]
    trading_signals: list[str]
    source_titles: list[str]
    source_urls: list[str]
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return asdict(self)


class CompanyDataProvider(Protocol):
    name: str

    def collect(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> CompanyResearchData:
        ...


class StockDataProvider(Protocol):
    name: str

    def collect(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> StockResearchData:
        ...


class CommodityDataProvider(Protocol):
    name: str

    def collect(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> CommodityResearchData:
        ...


class MockCompanyDataProvider:
    name = "mock_company_data"

    def collect(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> CompanyResearchData:
        if (
            session.object_type.value if isinstance(session.object_type, ObjectType) else session.object_type
        ) != ObjectType.COMPANY.value:
            raise ValueError("company data provider only supports company sessions")

        documents = retrieval_bundle.documents if retrieval_bundle else []
        if llm_provider:
            try:
                draft = llm_provider.generate_company_profile(session, retrieval_bundle)
                return self._from_llm_draft(session, draft, documents)
            except LLMProviderError:
                pass
        fundamentals = self._pick_documents(documents, "fundamentals")
        market_docs = self._pick_documents(documents, "market")
        policy_docs = self._pick_documents(documents, "policy")
        primary_doc = documents[0] if documents else None
        focus_text = "、".join(session.focus_areas) if session.focus_areas else "主营业务、经营状态与行业位置"

        registered_name = (
            f"{session.object_name}股份有限公司"
            if "集团" not in session.object_name and "公司" not in session.object_name
            else session.object_name
        )
        business_overview = self._join_summaries(
            fundamentals,
            fallback=(
                f"{session.object_name}当前已进入结构化公司画像阶段，重点围绕{focus_text}做经营与主体信息梳理。"
            ),
        )
        industry_position = self._join_summaries(
            market_docs,
            fallback=f"{session.object_name}的行业地位仍需结合更多市场份额、竞对与产业链数据持续验证。",
        )
        policy_watchpoints = self._build_policy_watchpoints(policy_docs)
        operating_signals = self._build_operating_signals(fundamentals, market_docs)
        source_titles = [item.title for item in documents[:3]]
        source_urls = [item.url for item in documents[:3] if item.url]

        if primary_doc and primary_doc.title not in source_titles:
            source_titles.insert(0, primary_doc.title)
        return CompanyResearchData(
            company_name=session.object_name,
            registered_name=registered_name,
            business_overview=business_overview,
            industry_position=industry_position,
            policy_watchpoints=policy_watchpoints,
            operating_signals=operating_signals,
            source_titles=source_titles[:3],
            source_urls=source_urls[:3],
        )

    @staticmethod
    def _from_llm_draft(
        session: ResearchSession,
        draft: CompanyProfileDraft,
        documents: list[RetrievalDocument],
    ) -> CompanyResearchData:
        return CompanyResearchData(
            company_name=session.object_name,
            registered_name=draft.registered_name,
            business_overview=draft.business_overview,
            industry_position=draft.industry_position,
            policy_watchpoints=draft.policy_watchpoints,
            operating_signals=draft.operating_signals,
            source_titles=[item.title for item in documents[:3]],
            source_urls=[item.url for item in documents[:3] if item.url][:3],
        )

    @staticmethod
    def _pick_documents(documents: list[RetrievalDocument], category: str) -> list[RetrievalDocument]:
        picked = [item for item in documents if item.category == category]
        return picked[:2]

    @staticmethod
    def _join_summaries(documents: list[RetrievalDocument], fallback: str) -> str:
        if not documents:
            return fallback
        parts = [item.summary.strip() for item in documents if item.summary.strip()]
        return " ".join(parts[:2]) if parts else fallback

    @staticmethod
    def _build_policy_watchpoints(documents: list[RetrievalDocument]) -> list[str]:
        if not documents:
            return ["需持续跟踪行业监管、合规要求与政策变化。"]
        items = []
        for item in documents:
            items.append(f"{item.title}：{item.summary.strip() or '需持续关注相关政策变化'}")
        return items[:3]

    @staticmethod
    def _build_operating_signals(
        fundamentals: list[RetrievalDocument],
        market_docs: list[RetrievalDocument],
    ) -> list[str]:
        items: list[str] = []
        for item in fundamentals[:2]:
            items.append(f"经营信号：{item.summary.strip() or item.title}")
        for item in market_docs[:2]:
            items.append(f"市场信号：{item.summary.strip() or item.title}")
        if not items:
            items.append("当前缺少稳定的结构化经营数据，建议继续接入企业画像与财务数据源。")
        return items[:4]


class MockStockDataProvider:
    name = "mock_stock_data"

    def collect(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> StockResearchData:
        if (
            session.object_type.value if isinstance(session.object_type, ObjectType) else session.object_type
        ) != ObjectType.STOCK.value:
            raise ValueError("stock data provider only supports stock sessions")
        documents = retrieval_bundle.documents if retrieval_bundle else []
        if llm_provider:
            try:
                draft = llm_provider.generate_stock_profile(session, retrieval_bundle)
                return self._from_llm_draft(draft, documents)
            except LLMProviderError:
                pass
        financial_docs = [item for item in documents if item.category in {"financials", "fundamentals"}]
        market_docs = [item for item in documents if item.category == "market"]
        return StockResearchData(
            security_name=session.object_name,
            trading_snapshot=(
                market_docs[0].summary
                if market_docs
                else f"{session.object_name}当前主要依赖公开检索线索观察价格走势与交易情绪。"
            ),
            financial_snapshot=(
                financial_docs[0].summary
                if financial_docs
                else f"{session.object_name}财务与估值信息仍需继续接入财报与公告数据验证。"
            ),
            filing_watchpoints=[item.summary or item.title for item in financial_docs[:3]]
            or ["需持续跟踪财报、公告和重大事项披露。"],
            market_signals=[item.summary or item.title for item in market_docs[:3]]
            or ["需结合更实时的行情、资金流和舆情数据判断市场信号。"],
            source_titles=[item.title for item in documents[:3]],
            source_urls=[item.url for item in documents[:3] if item.url][:3],
        )

    @staticmethod
    def _from_llm_draft(draft: StockProfileDraft, documents: list[RetrievalDocument]) -> StockResearchData:
        return StockResearchData(
            security_name=draft.security_name,
            trading_snapshot=draft.trading_snapshot,
            financial_snapshot=draft.financial_snapshot,
            filing_watchpoints=draft.filing_watchpoints,
            market_signals=draft.market_signals,
            source_titles=[item.title for item in documents[:3]],
            source_urls=[item.url for item in documents[:3] if item.url][:3],
        )


class MockCommodityDataProvider:
    name = "mock_commodity_data"

    def collect(
        self,
        session: ResearchSession,
        retrieval_bundle: RetrievalBundle | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> CommodityResearchData:
        if (
            session.object_type.value if isinstance(session.object_type, ObjectType) else session.object_type
        ) != ObjectType.COMMODITY.value:
            raise ValueError("commodity data provider only supports commodity sessions")
        documents = retrieval_bundle.documents if retrieval_bundle else []
        if llm_provider:
            try:
                draft = llm_provider.generate_commodity_profile(session, retrieval_bundle)
                return self._from_llm_draft(draft, documents)
            except LLMProviderError:
                pass
        supply_docs = [item for item in documents if item.category == "supply_demand"]
        pricing_docs = [item for item in documents if item.category in {"pricing", "market"}]
        return CommodityResearchData(
            commodity_name=session.object_name,
            price_snapshot=(
                pricing_docs[0].summary
                if pricing_docs
                else f"{session.object_name}当前价格表现仍需结合现货、期货和区间走势继续验证。"
            ),
            supply_demand_snapshot=(
                supply_docs[0].summary
                if supply_docs
                else f"{session.object_name}供需格局仍需结合库存、产量和下游需求进一步判断。"
            ),
            market_watchpoints=[item.summary or item.title for item in supply_docs[:3]]
            or ["需持续跟踪库存、产量、开工率与下游需求变化。"],
            trading_signals=[item.summary or item.title for item in pricing_docs[:3]]
            or ["需结合更实时的价格与基差数据判断交易信号。"],
            source_titles=[item.title for item in documents[:3]],
            source_urls=[item.url for item in documents[:3] if item.url][:3],
        )

    @staticmethod
    def _from_llm_draft(draft: CommodityProfileDraft, documents: list[RetrievalDocument]) -> CommodityResearchData:
        return CommodityResearchData(
            commodity_name=draft.commodity_name,
            price_snapshot=draft.price_snapshot,
            supply_demand_snapshot=draft.supply_demand_snapshot,
            market_watchpoints=draft.market_watchpoints,
            trading_signals=draft.trading_signals,
            source_titles=[item.title for item in documents[:3]],
            source_urls=[item.url for item in documents[:3] if item.url][:3],
        )
