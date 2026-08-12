from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


PriorityKey = Literal[
    "climate",
    "renewable_energy",
    "fair_labor",
    "human_rights",
    "biodiversity",
    "clean_water",
    "sustainable_agriculture",
    "circular_economy",
    "governance",
]


class QuestionnaireAnswers(BaseModel):
    priorities: list[PriorityKey] = Field(default_factory=lambda: ["climate"])
    goal: Literal["long_term_growth", "growth_and_stability", "income_and_preservation"] = "growth_and_stability"
    horizon: Literal["under_3_years", "3_to_10_years", "10_plus_years"] = "10_plus_years"
    risk: Literal["move_to_safety", "stay_invested", "invest_more"] = "stay_invested"
    decline_reaction: Literal["sell", "hold", "buy_more"] = "hold"
    philosophy: Literal["avoid_harm", "fund_solutions", "combination"] = "combination"
    tradeoff: Literal["none", "small", "moderate", "strong"] = "small"
    exclusions: list[str] = Field(default_factory=list)
    max_concentration: float = Field(default=0.20, ge=0.10, le=0.20)


class InvestorProfile(BaseModel):
    profile_name: str
    profile_description: str
    risk_score: int = Field(ge=0, le=100)
    return_priority: float = Field(ge=0, le=1)
    sustainability_priority_weights: dict[str, float]
    exclusions: list[str]
    time_horizon: str
    investment_objective: str
    sustainability_tradeoff: str
    company_preference: str
    max_concentration: float


class ProfileRequest(BaseModel):
    answers: QuestionnaireAnswers


class PortfolioRequest(BaseModel):
    investment_amount: float = Field(ge=1, le=10_000_000)
    answers: QuestionnaireAnswers | None = None
    profile: InvestorProfile | None = None
    number_of_holdings: int = Field(default=8, ge=5, le=15)

    @model_validator(mode="after")
    def profile_or_answers(self) -> "PortfolioRequest":
        if not self.answers and not self.profile:
            raise ValueError("Provide questionnaire answers or a structured profile")
        return self


class SustainabilityPayload(BaseModel):
    status: Literal["available", "unavailable"]
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: str
    published_at: str | None = None
    rating_date: str | None = None
    source: str = "Yahoo Finance via yfinance"


class CompanyResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str | None = None
    industry: str | None = None
    current_price: float
    price_retrieved_at: str
    annualized_historical_return: float
    annualized_volatility: float
    maximum_drawdown: float
    yahoo_sustainability: SustainabilityPayload
    sources: list[str]
    description: str | None = None


class PricePoint(BaseModel):
    date: str
    close: float


class SparklineResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str | None = None
    current_price: float
    change_amount: float
    change_percent: float
    period: str
    interval: str
    points: list[PricePoint]
    blurb: str | None = None
    retrieved_at: str


class WatchlistResponse(BaseModel):
    period: str
    interval: str
    retrieved_at: str
    items: list[SparklineResponse]


class CompanyAnalysisRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    profile: InvestorProfile


class CompanyAnalysisResponse(CompanyResponse):
    description: str | None = None
    market_cap: float | None = None
    green_canopy_score: float
    green_canopy_confidence: Literal["low", "medium", "high"]
    matched_priorities: list[str]
    assessment_limitations: list[str]


class HoldingInput(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    dollar_amount: float = Field(gt=0)


class PortfolioAnalysisRequest(BaseModel):
    holdings: list[HoldingInput] = Field(min_length=1, max_length=30)
    answers: QuestionnaireAnswers | None = None
    profile: InvestorProfile | None = None

    @model_validator(mode="after")
    def profile_or_answers(self) -> "PortfolioAnalysisRequest":
        if not self.answers and not self.profile:
            raise ValueError("Provide questionnaire answers or a structured profile")
        return self


class PriorityMatch(BaseModel):
    key: str
    label: str
    matched: bool
    profile_weight: float
    supporting_evidence: str | None = None


class EsgField(BaseModel):
    key: str
    label: str
    raw_value: float


class AlignmentDetail(BaseModel):
    explanation: str
    priority_breakdown: list[PriorityMatch]
    esg_snapshot: list[EsgField]
    business_summary_available: bool = False
    classification_status: Literal["agent_verified", "unreviewed", "stale"] = "unreviewed"
    classification_verified_at: str | None = None


class HoldingAssessment(BaseModel):
    ticker: str
    name: str
    asset_type: str
    sector: str
    dollar_amount: float
    weight: float
    alignment_score: float
    confidence: Literal["low", "medium", "high"]
    matched_priorities: list[str]
    sustainability_status: str
    in_green_canopy_universe: bool
    flag: str | None = None
    detail: AlignmentDetail
    business_summary: str | None = None
    website: str | None = None


class SuggestedHolding(BaseModel):
    ticker: str
    name: str
    asset_type: str
    sector: str
    alignment_score: float
    matched_priorities: list[str]
    why_suggested: str
    detail: AlignmentDetail
    business_summary: str | None = None
    website: str | None = None


class BenchmarkComparison(BaseModel):
    ticker: str
    name: str
    annualized_historical_return: float
    annualized_volatility: float
    maximum_drawdown: float


class PortfolioAnalysisResponse(BaseModel):
    investor_profile: InvestorProfile
    total_value: float
    holdings: list[HoldingAssessment]
    sustainability_alignment_score: float
    portfolio_narrative: str = ""
    sector_distribution: dict[str, float]
    diversification_score: float
    annualized_historical_return: float | None = None
    annualized_volatility: float | None = None
    maximum_drawdown: float | None = None
    benchmark: BenchmarkComparison | None = None
    suggestions: list[SuggestedHolding]
    data_retrieved_at: str
    sources: list[str]
    warnings: list[str]
    limitations: list[str]
    excluded_holdings: list[dict[str, str]]


class QuoteRequest(BaseModel):
    tickers: list[str] = Field(min_length=1, max_length=20)


class QuoteItem(BaseModel):
    ticker: str
    current_price: float
    retrieved_at: str


class QuoteResponse(BaseModel):
    quotes: list[QuoteItem]
    cache_seconds: int = 900
    source: str = "Yahoo Finance via yfinance"


class Allocation(BaseModel):
    ticker: str
    name: str
    asset_type: str
    sector: str
    weight: float
    dollar_amount: float
    purchase_price: float
    shares: float
    alignment_score: float
    confidence: Literal["low", "medium", "high"]
    matched_priorities: list[str]
    why_selected: str
    sustainability_status: str
    detail: AlignmentDetail
    business_summary: str | None = None
    website: str | None = None


class PortfolioResponse(BaseModel):
    investor_profile: InvestorProfile
    total_investment_amount: float
    allocations: list[Allocation]
    sustainability_alignment_score: float
    portfolio_narrative: str = ""
    annualized_historical_return: float
    annualized_volatility: float
    maximum_drawdown: float
    benchmark: BenchmarkComparison | None = None
    number_of_holdings: int
    sector_distribution: dict[str, float]
    diversification_score: float
    data_retrieved_at: str
    sources: list[str]
    warnings: list[str]
    limitations: list[str]
    excluded_investments: list[dict[str, str]]


class ClassificationEvidenceResponse(BaseModel):
    id: str
    kind: str
    title: str
    source: str
    retrieved_at: str
    url: str | None = None
    excerpt: str
    content_sha256: str | None = None
    quotes: list[str] = Field(default_factory=list)


class ClassificationUpdateResponse(BaseModel):
    id: str
    ticker: str
    name: str
    asset_type: str
    published_at: str
    agent: str
    model: str
    policy_version: str | None = None
    prompt_version: str | None = None
    verification: str | None = None
    old_tags: list[str]
    new_tags: list[str]
    added_tags: list[str]
    removed_tags: list[str]
    old_exclusions: list[str]
    new_exclusions: list[str]
    added_exclusions: list[str]
    removed_exclusions: list[str]
    summary: str
    confidence: float = Field(ge=0, le=1)
    accepted_assessments: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[ClassificationEvidenceResponse] = Field(default_factory=list)
    greenwashing_flags: list[str] = Field(default_factory=list)
    evidence_limitations: list[str] = Field(default_factory=list)
    portfolio_impact: str


class ClassificationUpdatesResponse(BaseModel):
    schema_version: int
    total: int = 0
    offset: int = 0
    next_offset: int | None = None
    updates: list[ClassificationUpdateResponse]


class AgentStatusResponse(BaseModel):
    schema_version: int
    agent: str
    policy_version: str
    prompt_version: str
    total_securities: int
    verified_securities: int
    coverage_percent: float
    checked_securities: int
    pending_securities: int
    retry_queue: list[dict[str, Any]] = Field(default_factory=list)
    retry_count: int
    last_run: dict[str, Any] | None = None


class SecurityClassificationResponse(BaseModel):
    universe_version: str
    ticker: str
    name: str
    asset_type: str
    tags: list[str]
    exclusions: list[str]
    classification: dict[str, Any] | None = None
    history: list[ClassificationUpdateResponse] = Field(default_factory=list)
