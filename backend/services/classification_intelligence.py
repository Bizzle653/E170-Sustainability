from __future__ import annotations

import io
import hashlib
import json
import os
import re
import socket
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Callable, Literal, Protocol
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx
from openai import OpenAI
from pydantic import BaseModel, Field, model_validator

from backend.services.market_data import MarketDataError, MarketDataService


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UNIVERSE_PATH = ROOT / "backend" / "data" / "investment_universe.json"
DEFAULT_UPDATES_PATH = ROOT / "backend" / "data" / "classification_updates.json"
DEFAULT_STATE_PATH = ROOT / "backend" / "data" / "classification_agent_state.json"

AGENT_NAME = "Green Canopy Sustainability Intelligence Agent"
DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
POLICY_VERSION = "2026-08-12.1"
PROMPT_VERSION = "classification-v2-exact-citations"
DEFAULT_REMOTE_STATE_URL = (
    "https://raw.githubusercontent.com/highGround-helloThere/"
    "E170-Sustainability/main/backend/data/classification_agent_state.json"
)
_REMOTE_STATE_CACHE: tuple[datetime, dict[str, Any]] | None = None

SUPPORTED_TAGS = (
    "climate",
    "renewable_energy",
    "fair_labor",
    "human_rights",
    "biodiversity",
    "clean_water",
    "sustainable_agriculture",
    "circular_economy",
    "governance",
    "low_carbon",
)
SUPPORTED_EXCLUSIONS = ("fossil_fuels",)

TAG_GUIDANCE = {
    "climate": "Material products, services, or demonstrated operations addressing climate mitigation or adaptation.",
    "renewable_energy": "Material renewable generation, equipment, storage, or enabling infrastructure business.",
    "fair_labor": "Specific, evidenced labor standards, worker safety, wages, or collective-bargaining practices.",
    "human_rights": "Specific, evidenced human-rights or responsible-sourcing practices and controls.",
    "biodiversity": "Material products, services, or demonstrated operations protecting ecosystems or biodiversity.",
    "clean_water": "Material water treatment, conservation, infrastructure, or water-quality business and outcomes.",
    "sustainable_agriculture": "Material regenerative, lower-impact, or resource-efficient agriculture business and outcomes.",
    "circular_economy": "Material reuse, recycling, waste reduction, recovery, or circular product business and outcomes.",
    "governance": "Specific, evidenced governance controls or practices; generic boilerplate is insufficient.",
    "low_carbon": "For funds only: evidenced lower-carbon methodology or material weighted lower-carbon exposure.",
}

RESEARCH_LINK_TERMS = (
    "sustainability",
    "sustainable",
    "esg",
    "environment",
    "climate",
    "impact-report",
    "impact_report",
    "annual-report",
    "annual_report",
)


class EvidenceSource(BaseModel):
    id: str
    kind: Literal["market_profile", "yahoo_sustainability", "fund_holdings", "official_web", "official_pdf"]
    title: str
    source: str
    retrieved_at: str
    published_at: str | None = None
    content: str
    url: str | None = None


class EvidenceCitation(BaseModel):
    evidence_id: str
    quote: str = Field(min_length=8, max_length=600)


class ClassificationAssessment(BaseModel):
    category: str
    action: Literal["add", "keep", "remove", "insufficient"]
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    rationale: str = Field(min_length=1, max_length=800)


class ClassificationDecision(BaseModel):
    summary: str = Field(min_length=1, max_length=1_500)
    tag_assessments: list[ClassificationAssessment]
    exclusion_assessments: list[ClassificationAssessment] = Field(default_factory=list)
    greenwashing_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_assessment_collections(cls, value: Any) -> Any:
        """Accept both JSON arrays and category-keyed objects from the model.

        DeepSeek occasionally follows the semantic schema but chooses
        ``{"climate": {...}}`` instead of ``[{"category": "climate", ...}]``.
        Normalising that harmless shape difference keeps evidence validation and
        the automatic-change threshold in one deterministic code path.
        """
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for field_name in ("tag_assessments", "exclusion_assessments"):
            collection = normalized.get(field_name)
            if not isinstance(collection, dict):
                continue
            items = []
            for category, assessment in collection.items():
                if not isinstance(assessment, dict):
                    continue
                item = dict(assessment)
                item.setdefault("category", category)
                items.append(item)
            normalized[field_name] = items
        return normalized


class ChangeVerification(BaseModel):
    approved: list[str] = Field(default_factory=list)
    rejected: dict[str, str] = Field(default_factory=dict)


class DecisionProvider(Protocol):
    model_name: str

    def classify(
        self,
        security: dict[str, Any],
        evidence: list[EvidenceSource],
    ) -> ClassificationDecision: ...


class _ResearchPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._anchor_text: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._anchor_text)))
            self._href = None
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        self.text.append(cleaned)
        if self._href:
            self._anchor_text.append(cleaned)


class OfficialSourceResearcher:
    """Bounded official-site collector with basic SSRF protection."""

    def __init__(self, timeout_seconds: float = 12.0, max_documents: int = 3) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_documents = max_documents

    @staticmethod
    def _is_public_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
        except OSError:
            return False
        if not addresses:
            return False
        for raw_address in addresses:
            address = ip_address(raw_address)
            if not address.is_global:
                return False
        return True

    def _get(self, url: str) -> httpx.Response:
        current = url
        headers = {"User-Agent": "GreenCanopyResearchAgent/1.0 (+public sustainability research)"}
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False, headers=headers) as client:
            for _ in range(4):
                if not self._is_public_url(current):
                    raise ValueError("Official source URL is not public")
                request = client.build_request("GET", current)
                response = client.send(request, stream=True)
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    response.close()
                    if not location:
                        break
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                byte_limit = 10_000_000 if "pdf" in content_type or current.lower().endswith(".pdf") else 2_000_000
                declared_size = response.headers.get("content-length")
                if declared_size and int(declared_size) > byte_limit:
                    response.close()
                    raise ValueError("Official source exceeds the download limit")
                chunks: list[bytes] = []
                downloaded = 0
                for chunk in response.iter_bytes():
                    downloaded += len(chunk)
                    if downloaded > byte_limit:
                        response.close()
                        raise ValueError("Official source exceeds the download limit")
                    chunks.append(chunk)
                final_url = response.url
                status_code = response.status_code
                response_headers = response.headers
                response.close()
                return httpx.Response(
                    status_code=status_code,
                    headers=response_headers,
                    content=b"".join(chunks),
                    request=request,
                    extensions={"url": final_url},
                )
        raise ValueError("Too many redirects while retrieving official source")

    @staticmethod
    def _clean_text(text: str, limit: int = 12_000) -> str:
        return re.sub(r"\s+", " ", text).strip()[:limit]

    @staticmethod
    def _published_at(response: httpx.Response) -> str | None:
        raw_value = response.headers.get("last-modified")
        if not raw_value:
            return None
        try:
            return parsedate_to_datetime(raw_value).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            return None

    def _html_source(self, response: httpx.Response, source_id: str, title: str) -> tuple[EvidenceSource, list[str]]:
        if len(response.content) > 2_000_000:
            raise ValueError("Official HTML source is too large")
        parser = _ResearchPageParser()
        parser.feed(response.text)
        content = self._clean_text(" ".join(parser.text))
        links = []
        for href, anchor in parser.links:
            candidate = urljoin(str(response.url), href)
            searchable = f"{candidate} {anchor}".lower()
            if any(term in searchable for term in RESEARCH_LINK_TERMS):
                links.append(candidate)
        return EvidenceSource(
            id=source_id,
            kind="official_web",
            title=title,
            source="Official company or fund website",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            published_at=self._published_at(response),
            content=content,
            url=str(response.url),
        ), list(dict.fromkeys(links))

    @staticmethod
    def _pdf_source(response: httpx.Response, source_id: str, title: str) -> EvidenceSource:
        if len(response.content) > 10_000_000:
            raise ValueError("Official PDF source is too large")
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required to read official PDF evidence") from exc
        reader = PdfReader(io.BytesIO(response.content))
        text = " ".join(
            f"[PDF page {page_number}] {page.extract_text() or ''}"
            for page_number, page in enumerate(reader.pages[:40], start=1)
        )
        return EvidenceSource(
            id=source_id,
            kind="official_pdf",
            title=title,
            source="Official company or fund report",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            published_at=OfficialSourceResearcher._published_at(response),
            content=OfficialSourceResearcher._clean_text(text, 20_000),
            url=str(response.url),
        )

    def collect(self, website: str | None) -> list[EvidenceSource]:
        if not website or not self._is_public_url(website):
            return []
        try:
            home_response = self._get(website)
            home, links = self._html_source(home_response, "official-home", "Official website")
        except (httpx.HTTPError, OSError, RuntimeError, ValueError):
            return []

        sources = [home]
        official_host = (urlparse(str(home_response.url)).hostname or "").lower().removeprefix("www.")
        official_links = []
        for link in links:
            candidate_host = (urlparse(link).hostname or "").lower().removeprefix("www.")
            if candidate_host == official_host or candidate_host.endswith(f".{official_host}"):
                official_links.append(link)
        for index, link in enumerate(official_links[: self.max_documents - 1], start=1):
            try:
                response = self._get(link)
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" in content_type or str(response.url).lower().endswith(".pdf"):
                    source = self._pdf_source(response, f"official-report-{index}", "Official sustainability report")
                else:
                    source, _ = self._html_source(
                        response,
                        f"official-page-{index}",
                        "Official sustainability page",
                    )
                if source.content:
                    sources.append(source)
            except (httpx.HTTPError, OSError, RuntimeError, ValueError):
                continue
        return sources


class DeepSeekClassificationProvider:
    model_name = DEFAULT_MODEL

    def __init__(self, client: OpenAI | None = None, model: str = DEFAULT_MODEL) -> None:
        self.model_name = model
        self.client = client or OpenAI(
            api_key=_load_deepseek_key(),
            base_url=DEEPSEEK_BASE_URL,
            timeout=60.0,
            max_retries=2,
        )

    def classify(self, security: dict[str, Any], evidence: list[EvidenceSource]) -> ClassificationDecision:
        evidence_payload = [source.model_dump() for source in evidence]
        guidance = "\n".join(f"- {tag}: {description}" for tag, description in TAG_GUIDANCE.items())
        prompt = f"""
Classify this security using only the supplied evidence bundle.

Security:
{json.dumps({key: security.get(key) for key in ('ticker', 'name', 'type', 'sector', 'industry', 'tags', 'exclusions')}, ensure_ascii=False)}

Categories:
{guidance}
- fossil_fuels exclusion: material extraction, production, transport, refining, or weighted fund exposure.

Rules:
1. Assess every supported tag and the fossil_fuels exclusion.
2. A mention, generic policy, future promise, or risk disclosure alone is not material support.
3. Distinguish operating business, measured outcome, future commitment, and marketing language.
4. For ETFs, rely on mandate/methodology and weighted holdings evidence; state coverage limits.
5. Use only evidence IDs present below. Never invent a source or fact.
6. For a current category choose keep, remove, or insufficient. For a missing category choose add or insufficient.
7. Use add/remove only when the evidence is strong enough to autonomously change production metadata.
8. Every add, keep, or remove must include citations containing evidence_id and a short exact quote copied verbatim
   from that evidence source. Changes without exact, program-verifiable quotes are rejected.
9. When multiple sources are available, cite at least two distinct sources for an add or remove.
10. Absence of a claim is not evidence for removal. Remove only when current evidence explicitly contradicts the label.

Evidence bundle:
{json.dumps(evidence_payload, ensure_ascii=False)}

Return one JSON object with:
- summary: concise basis for the overall classification
- tag_assessments: one object for every supported tag, each containing category, action, confidence (0-1),
  evidence_ids, citations (objects with evidence_id and an exact quote), and rationale
- exclusion_assessments: one object for fossil_fuels with the same fields
- greenwashing_flags: evidence-backed conflicts between sustainability claims and operations; otherwise []
"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Green Canopy's autonomous sustainability classification agent. "
                        "Be conservative, evidence-bound, and return valid JSON only. You do not rate investment quality."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("DeepSeek returned an empty classification response")
        return ClassificationDecision.model_validate_json(_strip_json_fence(content))

    def verify_changes(
        self,
        security: dict[str, Any],
        evidence: list[EvidenceSource],
        decision: ClassificationDecision,
    ) -> ClassificationDecision:
        proposed = [
            item.model_dump()
            for item in decision.tag_assessments + decision.exclusion_assessments
            if item.action in {"add", "remove"}
        ]
        if not proposed:
            return decision
        prompt = f"""
Independently audit proposed autonomous classification changes. Reject a change unless its exact quotes are present,
material to the category, current enough to support the conclusion, and the action follows Green Canopy policy.
Absence of evidence never supports removal. Do not propose new changes.

Security: {json.dumps({key: security.get(key) for key in ('ticker', 'name', 'type', 'tags', 'exclusions')}, ensure_ascii=False)}
Policy version: {POLICY_VERSION}
Proposed changes: {json.dumps(proposed, ensure_ascii=False)}
Evidence: {json.dumps([source.model_dump() for source in evidence], ensure_ascii=False)}

Return JSON with approved (category names) and rejected (an object mapping rejected category names to short reasons).
"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are the independent verification pass. Be adversarial, conservative, and return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("DeepSeek returned an empty verification response")
        verification = ChangeVerification.model_validate_json(_strip_json_fence(content))
        approved = set(verification.approved)

        def filter_assessment(item: ClassificationAssessment) -> ClassificationAssessment:
            if item.action not in {"add", "remove"} or item.category in approved:
                return item
            reason = verification.rejected.get(item.category, "The independent verification pass did not approve this change.")
            return item.model_copy(update={
                "action": "insufficient",
                "rationale": reason[:800],
                "confidence": 0.0,
                "evidence_ids": [],
                "citations": [],
            })

        return decision.model_copy(update={
            "tag_assessments": [filter_assessment(item) for item in decision.tag_assessments],
            "exclusion_assessments": [filter_assessment(item) for item in decision.exclusion_assessments],
        })


def _load_deepseek_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        return key
    for path in (ROOT / ".env.local", ROOT / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "DEEPSEEK_API_KEY" and value.strip():
                return value.strip().strip('"').strip("'")
    raise RuntimeError("DEEPSEEK_API_KEY is required to run the sustainability classification agent")


def _strip_json_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    return cleaned


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _parse_timestamp(raw_value: Any) -> datetime | None:
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def load_agent_status(
    universe_path: Path = DEFAULT_UNIVERSE_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    global _REMOTE_STATE_CACHE
    universe = _read_json(universe_path, {"securities": []})
    state = _read_json(state_path, {"schema_version": 1, "checks": {}, "retry_queue": []})
    remote_url = os.getenv("GREEN_CANOPY_AGENT_STATE_URL")
    if not remote_url and os.getenv("VERCEL") == "1" and state_path == DEFAULT_STATE_PATH:
        remote_url = DEFAULT_REMOTE_STATE_URL
    if remote_url:
        cached = _REMOTE_STATE_CACHE
        if cached and cached[0] > datetime.now(timezone.utc) - timedelta(seconds=60):
            state = cached[1]
        else:
            try:
                response = httpx.get(remote_url, timeout=5.0, follow_redirects=True)
                response.raise_for_status()
                remote_state = response.json()
                if isinstance(remote_state, dict):
                    state = remote_state
                    _REMOTE_STATE_CACHE = (datetime.now(timezone.utc), remote_state)
            except (httpx.HTTPError, ValueError):
                pass
    securities = universe.get("securities", [])
    checks = state.get("checks", {})
    verified = sum(
        (security.get("classification") or {}).get("status") == "agent_verified"
        for security in securities
    )
    failed = [item for item in state.get("retry_queue", []) if item.get("ticker")]
    public_retries = [
        {
            "ticker": item.get("ticker"),
            "failure_count": item.get("failure_count", 0),
            "last_attempt_at": item.get("last_attempt_at"),
            "next_retry_at": item.get("next_retry_at"),
        }
        for item in failed[:25]
    ]
    return {
        "schema_version": state.get("schema_version", 1),
        "agent": AGENT_NAME,
        "policy_version": POLICY_VERSION,
        "prompt_version": PROMPT_VERSION,
        "total_securities": len(securities),
        "verified_securities": verified,
        "coverage_percent": round((verified / len(securities) * 100) if securities else 0.0, 1),
        "checked_securities": len(checks),
        "pending_securities": max(0, len(securities) - verified),
        "retry_queue": public_retries,
        "retry_count": len(failed),
        "last_run": state.get("last_run"),
    }


def load_classification_updates(
    limit: int = 50,
    offset: int = 0,
    ticker: str | None = None,
    updates_path: Path = DEFAULT_UPDATES_PATH,
) -> dict[str, Any]:
    data = _read_json(updates_path, {"schema_version": 1, "updates": []})
    updates = data.get("updates", [])
    if ticker:
        symbol = ticker.upper().strip()
        updates = [item for item in updates if item.get("ticker") == symbol]
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    page = updates[offset:offset + limit]
    next_offset = offset + len(page) if offset + len(page) < len(updates) else None
    return {
        "schema_version": data.get("schema_version", 1),
        "total": len(updates),
        "offset": offset,
        "next_offset": next_offset,
        "updates": page,
    }


def load_security_classification(
    ticker: str,
    universe_path: Path = DEFAULT_UNIVERSE_PATH,
    updates_path: Path = DEFAULT_UPDATES_PATH,
) -> dict[str, Any] | None:
    symbol = ticker.upper().strip()
    universe = _read_json(universe_path, {"securities": []})
    security = next((item for item in universe.get("securities", []) if item.get("ticker") == symbol), None)
    if security is None:
        return None
    history = load_classification_updates(limit=20, ticker=symbol, updates_path=updates_path)["updates"]
    return {
        "universe_version": universe.get("version"),
        "ticker": symbol,
        "name": security.get("name") or symbol,
        "asset_type": security.get("type"),
        "tags": security.get("tags", []),
        "exclusions": security.get("exclusions", []),
        "classification": security.get("classification"),
        "history": history,
    }


class SustainabilityIntelligenceAgent:
    def __init__(
        self,
        market_data: MarketDataService | None = None,
        decision_provider: DecisionProvider | None = None,
        researcher: OfficialSourceResearcher | None = None,
        universe_path: Path = DEFAULT_UNIVERSE_PATH,
        updates_path: Path = DEFAULT_UPDATES_PATH,
        state_path: Path | None = None,
        min_confidence: float = 0.80,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.market_data = market_data or MarketDataService()
        self.decision_provider = decision_provider or DeepSeekClassificationProvider()
        self.researcher = researcher or OfficialSourceResearcher()
        self.universe_path = universe_path
        self.updates_path = updates_path
        self.state_path = state_path or (
            DEFAULT_STATE_PATH if universe_path == DEFAULT_UNIVERSE_PATH
            else universe_path.with_name("classification_agent_state.json")
        )
        self.min_confidence = min_confidence
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _collect_evidence(self, security: dict[str, Any]) -> list[EvidenceSource]:
        symbol = security["ticker"]
        retrieved_at = self.now().isoformat()
        info = self.market_data.get_info(symbol)
        profile = {
            "company_name": info.get("longName") or info.get("shortName") or security.get("name"),
            "quote_type": info.get("quoteType"),
            "sector": info.get("sector") or security.get("sector"),
            "industry": info.get("industry") or security.get("industry"),
            "business_summary": info.get("longBusinessSummary"),
            "website": info.get("website"),
        }
        sources = [EvidenceSource(
            id="market-profile",
            kind="market_profile",
            title="Yahoo Finance company or fund profile",
            source="Yahoo Finance via yfinance",
            retrieved_at=retrieved_at,
            content=json.dumps(profile, ensure_ascii=False),
            url=info.get("website"),
        )]

        sustainability = self.market_data.get_sustainability(symbol)
        if sustainability:
            sources.append(EvidenceSource(
                id="yahoo-sustainability",
                kind="yahoo_sustainability",
                title="Yahoo Finance sustainability fields",
                source="Yahoo Finance via yfinance",
                retrieved_at=retrieved_at,
                content=json.dumps(sustainability, ensure_ascii=False, default=str)[:12_000],
            ))

        if security.get("type") == "etf":
            holdings = self.market_data.get_top_holdings(symbol, limit=25)
            if holdings:
                sources.append(EvidenceSource(
                    id="fund-holdings",
                    kind="fund_holdings",
                    title="Fund top holdings",
                    source="Yahoo Finance via yfinance",
                    retrieved_at=retrieved_at,
                    content=json.dumps(holdings, ensure_ascii=False, default=str),
                ))

        sources.extend(self.researcher.collect(info.get("website")))
        return sources

    @staticmethod
    def _last_checked(security: dict[str, Any], state: dict[str, Any]) -> datetime | None:
        ticker = security.get("ticker", "")
        state_value = (state.get("checks", {}).get(ticker) or {}).get("last_checked_at")
        classification_value = (security.get("classification") or {}).get("last_checked_at")
        return _parse_timestamp(state_value or classification_value)

    def _select(
        self,
        securities: list[dict[str, Any]],
        tickers: list[str] | None,
        stale_days: int,
        limit: int,
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if tickers:
            requested = {ticker.upper().strip() for ticker in tickers}
            selected = [security for security in securities if security.get("ticker") in requested]
            missing = requested.difference({security.get("ticker") for security in selected})
            if missing:
                raise ValueError(f"Ticker(s) not found in the Green Canopy universe: {', '.join(sorted(missing))}")
            return selected[:limit]

        cutoff = self.now() - timedelta(days=max(1, stale_days))
        retry_by_ticker = {item.get("ticker"): item for item in state.get("retry_queue", [])}

        def is_due(security: dict[str, Any]) -> bool:
            retry = retry_by_ticker.get(security.get("ticker"))
            if retry:
                next_retry = _parse_timestamp(retry.get("next_retry_at"))
                if next_retry and next_retry > self.now():
                    return False
                return True
            checked = self._last_checked(security, state)
            return checked is None or checked < cutoff

        stale = [security for security in securities if is_due(security)]

        def priority(item: dict[str, Any]) -> tuple[Any, ...]:
            ticker = item.get("ticker")
            checked = self._last_checked(item, state)
            classification = item.get("classification") or {}
            return (
                ticker not in retry_by_ticker,
                classification.get("status") == "agent_verified",
                not bool(item.get("tags") or item.get("exclusions")),
                checked is not None,
                checked or datetime.min.replace(tzinfo=timezone.utc),
                item.get("rank", 99999),
            )

        stale.sort(key=priority)
        return stale[:limit]

    @staticmethod
    def _normalized_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    @classmethod
    def _valid_assessments(
        cls,
        assessments: list[ClassificationAssessment],
        allowed_categories: tuple[str, ...],
        evidence: list[EvidenceSource],
    ) -> list[ClassificationAssessment]:
        evidence_by_id = {source.id: source for source in evidence}
        by_category: dict[str, ClassificationAssessment] = {}
        for assessment in assessments:
            if assessment.category not in allowed_categories:
                continue
            valid_citations = []
            for citation in assessment.citations:
                source = evidence_by_id.get(citation.evidence_id)
                if not source:
                    continue
                if cls._normalized_text(citation.quote) not in cls._normalized_text(source.content):
                    continue
                valid_citations.append(citation)
            valid_ids = list(dict.fromkeys(citation.evidence_id for citation in valid_citations))
            by_category[assessment.category] = assessment.model_copy(
                update={"evidence_ids": valid_ids, "citations": valid_citations},
            )
        return list(by_category.values())

    def _apply_assessments(
        self,
        current: list[str],
        assessments: list[ClassificationAssessment],
        allowed_categories: tuple[str, ...],
        evidence: list[EvidenceSource],
    ) -> tuple[list[str], list[ClassificationAssessment]]:
        result = set(current)
        accepted: list[ClassificationAssessment] = []
        require_two_sources = len({source.id for source in evidence if source.content.strip()}) >= 2
        for assessment in self._valid_assessments(assessments, allowed_categories, evidence):
            threshold = max(self.min_confidence, 0.90) if assessment.action == "remove" else self.min_confidence
            if assessment.confidence < threshold or not assessment.citations:
                continue
            if assessment.action in {"add", "remove"} and require_two_sources and len(assessment.evidence_ids) < 2:
                continue
            if assessment.action == "add" and assessment.category not in result:
                result.add(assessment.category)
                accepted.append(assessment)
            elif assessment.action == "remove" and assessment.category in result:
                result.remove(assessment.category)
                accepted.append(assessment)
            elif assessment.action == "keep" and assessment.category in result:
                accepted.append(assessment)
        ordered = [category for category in allowed_categories if category in result]
        ordered.extend(category for category in current if category not in allowed_categories and category not in ordered)
        return ordered, accepted

    @staticmethod
    def _announcement_evidence(
        accepted: list[ClassificationAssessment],
        evidence: list[EvidenceSource],
    ) -> list[dict[str, Any]]:
        citations_by_id: dict[str, list[str]] = {}
        for assessment in accepted:
            for citation in assessment.citations:
                citations_by_id.setdefault(citation.evidence_id, []).append(citation.quote)
        output = []
        for source in evidence:
            quotes = list(dict.fromkeys(citations_by_id.get(source.id, [])))
            if not quotes:
                continue
            output.append({
                "id": source.id,
                "kind": source.kind,
                "title": source.title,
                "source": source.source,
                "retrieved_at": source.retrieved_at,
                "published_at": source.published_at,
                "url": source.url,
                "content_sha256": hashlib.sha256(source.content.encode("utf-8")).hexdigest(),
                "quotes": quotes,
                "excerpt": " … ".join(quotes)[:1_500],
            })
        return output

    def run(
        self,
        tickers: list[str] | None = None,
        stale_days: int = 30,
        limit: int = 10,
        apply: bool = False,
    ) -> dict[str, Any]:
        universe = _read_json(self.universe_path, {"securities": []})
        updates_data = _read_json(self.updates_path, {"schema_version": 1, "updates": []})
        state = _read_json(
            self.state_path,
            {"schema_version": 1, "checks": {}, "retry_queue": [], "last_run": None},
        )
        selected = self._select(
            universe.get("securities", []), tickers, stale_days, max(1, min(limit, 25)), state,
        )
        results: list[dict[str, Any]] = []
        new_updates: list[dict[str, Any]] = []
        universe_changed = False
        run_started_at = self.now().isoformat()
        retry_by_ticker = {item.get("ticker"): item for item in state.get("retry_queue", []) if item.get("ticker")}
        checks = state.setdefault("checks", {})

        for security in selected:
            old_tags = list(security.get("tags", []))
            old_exclusions = list(security.get("exclusions", []))
            checked_at = self.now().isoformat()
            try:
                evidence = self._collect_evidence(security)
                decision = self.decision_provider.classify(security, evidence)
                verifier = getattr(self.decision_provider, "verify_changes", None)
                if callable(verifier):
                    decision = verifier(security, evidence, decision)
                tag_categories = {item.category for item in decision.tag_assessments}
                exclusion_categories = {item.category for item in decision.exclusion_assessments}
                missing = set(SUPPORTED_TAGS).difference(tag_categories)
                missing_exclusions = set(SUPPORTED_EXCLUSIONS).difference(exclusion_categories)
                if missing or missing_exclusions:
                    categories = sorted(missing.union(missing_exclusions))
                    raise ValueError(f"Incomplete classification response; missing: {', '.join(categories)}")
            except (MarketDataError, httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
                results.append({"ticker": security.get("ticker"), "status": "failed", "error": str(exc)})
                if apply:
                    ticker = security.get("ticker")
                    previous = retry_by_ticker.get(ticker, {})
                    failure_count = int(previous.get("failure_count", 0)) + 1
                    retry_at = self.now() + timedelta(hours=min(24, 2 ** min(failure_count, 4)))
                    retry_by_ticker[ticker] = {
                        "ticker": ticker,
                        "failure_count": failure_count,
                        "last_attempt_at": checked_at,
                        "next_retry_at": retry_at.isoformat(),
                        "last_error": str(exc)[:300],
                    }
                    checks[ticker] = {
                        "status": "failed",
                        "last_attempt_at": checked_at,
                        "failure_count": failure_count,
                    }
                continue

            new_tags, accepted_tags = self._apply_assessments(
                old_tags, decision.tag_assessments, SUPPORTED_TAGS, evidence,
            )
            new_exclusions, accepted_exclusions = self._apply_assessments(
                old_exclusions, decision.exclusion_assessments, SUPPORTED_EXCLUSIONS, evidence,
            )
            accepted = accepted_tags + accepted_exclusions
            changed = new_tags != old_tags or new_exclusions != old_exclusions
            confidence = round(max((item.confidence for item in accepted), default=0.0), 3)
            was_verified = (security.get("classification") or {}).get("status") == "agent_verified"
            verified_categories = {item.category for item in accepted}
            fully_verified = set(new_tags + new_exclusions).issubset(verified_categories)

            if apply:
                security["tags"] = new_tags
                security["exclusions"] = new_exclusions
                if changed or (not was_verified and fully_verified):
                    security["classification"] = {
                        "status": "agent_verified",
                        "agent": AGENT_NAME,
                        "model": self.decision_provider.model_name,
                        "policy_version": POLICY_VERSION,
                        "prompt_version": PROMPT_VERSION,
                        "verification": "independent_model_pass" if callable(verifier) else "deterministic_quote_validation",
                        "verified_at": checked_at,
                        "last_changed_at": checked_at if changed else None,
                        "confidence": confidence,
                        "evidence_source_count": len(evidence),
                    }
                    universe_changed = True
                checks[security["ticker"]] = {
                    "status": "succeeded",
                    "last_checked_at": checked_at,
                    "changed": changed,
                    "confidence": confidence,
                    "evidence_source_count": len(evidence),
                }
                retry_by_ticker.pop(security["ticker"], None)

            result = {
                "ticker": security["ticker"],
                "status": "changed" if changed else "unchanged",
                "old_tags": old_tags,
                "new_tags": new_tags,
                "old_exclusions": old_exclusions,
                "new_exclusions": new_exclusions,
                "confidence": confidence,
                "verification_complete": fully_verified,
                "summary": decision.summary,
            }
            results.append(result)

            if changed:
                added_tags = [tag for tag in new_tags if tag not in old_tags]
                removed_tags = [tag for tag in old_tags if tag not in new_tags]
                added_exclusions = [item for item in new_exclusions if item not in old_exclusions]
                removed_exclusions = [item for item in old_exclusions if item not in new_exclusions]
                update = {
                    "id": str(uuid4()),
                    "ticker": security["ticker"],
                    "name": security.get("name") or security["ticker"],
                    "asset_type": security.get("type"),
                    "published_at": checked_at,
                    "agent": AGENT_NAME,
                    "model": self.decision_provider.model_name,
                    "policy_version": POLICY_VERSION,
                    "prompt_version": PROMPT_VERSION,
                    "verification": "independent_model_pass" if callable(verifier) else "deterministic_quote_validation",
                    "old_tags": old_tags,
                    "new_tags": new_tags,
                    "added_tags": added_tags,
                    "removed_tags": removed_tags,
                    "old_exclusions": old_exclusions,
                    "new_exclusions": new_exclusions,
                    "added_exclusions": added_exclusions,
                    "removed_exclusions": removed_exclusions,
                    "summary": decision.summary,
                    "confidence": confidence,
                    "accepted_assessments": [item.model_dump() for item in accepted if item.action in {"add", "remove"}],
                    "evidence": self._announcement_evidence(accepted, evidence),
                    "greenwashing_flags": (
                        decision.greenwashing_flags
                        if accepted_exclusions and len({item for assessment in accepted for item in assessment.evidence_ids}) >= 2
                        else []
                    ),
                    "evidence_limitations": [
                        "Evidence is limited to retrievable market data, fund holdings, and issuer-controlled sources.",
                        "Exact quotes are program-verified, but the Agent's interpretation can still be wrong.",
                    ],
                    "portfolio_impact": (
                        "Saved Green Canopy portfolios containing this security may show a different alignment score. "
                        "Allocations are not changed automatically."
                    ),
                }
                new_updates.append(update)

        if apply:
            if universe_changed:
                universe["version"] = self.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            if new_updates:
                updates_data["updates"] = new_updates + updates_data.get("updates", [])
            succeeded = sum(item["status"] != "failed" for item in results)
            failed = sum(item["status"] == "failed" for item in results)
            state["retry_queue"] = sorted(
                retry_by_ticker.values(), key=lambda item: item.get("next_retry_at", ""),
            )
            state["last_run"] = {
                "started_at": run_started_at,
                "completed_at": self.now().isoformat(),
                "status": "failed" if selected and succeeded == 0 else "partial" if failed else "succeeded",
                "selected": len(selected),
                "succeeded": succeeded,
                "changed": len(new_updates),
                "failed": failed,
            }
            if universe_changed:
                _write_json(self.universe_path, universe)
            if new_updates:
                _write_json(self.updates_path, updates_data)
            _write_json(self.state_path, state)

        failed_count = sum(item["status"] == "failed" for item in results)
        succeeded_count = sum(item["status"] != "failed" for item in results)
        return {
            "agent": AGENT_NAME,
            "mode": "apply" if apply else "dry_run",
            "selected": len(selected),
            "changed": sum(item["status"] == "changed" for item in results),
            "succeeded": succeeded_count,
            "failed": failed_count,
            "run_status": "failed" if selected and succeeded_count == 0 else "partial" if failed_count else "succeeded",
            "results": results,
            "announcements_created": len(new_updates) if apply else 0,
        }
