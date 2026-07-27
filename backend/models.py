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
    philosophy: Literal["avoid_harm", "fund_solutions", "leaders", "transitioners", "combination"] = "combination"
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
    investment_amount: float = Field(ge=500, le=1_000_000)
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


class EsgField(BaseModel):
    key: str
    label: str
    raw_value: float


class AlignmentDetail(BaseModel):
    explanation: str
    priority_breakdown: list[PriorityMatch]
    esg_snapshot: list[EsgField]


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


class PortfolioAnalysisResponse(BaseModel):
    investor_profile: InvestorProfile
    total_value: float
    holdings: list[HoldingAssessment]
    sustainability_alignment_score: float
    sector_distribution: dict[str, float]
    diversification_score: float
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


class PortfolioResponse(BaseModel):
    investor_profile: InvestorProfile
    total_investment_amount: float
    allocations: list[Allocation]
    sustainability_alignment_score: float
    annualized_historical_return: float
    annualized_volatility: float
    maximum_drawdown: float
    number_of_holdings: int
    sector_distribution: dict[str, float]
    diversification_score: float
    data_retrieved_at: str
    sources: list[str]
    warnings: list[str]
    limitations: list[str]
    excluded_investments: list[dict[str, str]]
