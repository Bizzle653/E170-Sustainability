from __future__ import annotations

import io
import json
import os
import re
import socket
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

AGENT_NAME = "Green Canopy Sustainability Intelligence Agent"
DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

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
    content: str
    url: str | None = None


class ClassificationAssessment(BaseModel):
    category: str
    action: Literal["add", "keep", "remove", "insufficient"]
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
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
                response = client.get(current)
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        break
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                return response
        raise ValueError("Too many redirects while retrieving official source")

    @staticmethod
    def _clean_text(text: str, limit: int = 12_000) -> str:
        return re.sub(r"\s+", " ", text).strip()[:limit]

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
        text = " ".join((page.extract_text() or "") for page in reader.pages[:40])
        return EvidenceSource(
            id=source_id,
            kind="official_pdf",
            title=title,
            source="Official company or fund report",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
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
        for index, link in enumerate(links[: self.max_documents - 1], start=1):
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

Evidence bundle:
{json.dumps(evidence_payload, ensure_ascii=False)}

Return one JSON object with:
- summary: concise basis for the overall classification
- tag_assessments: one object for every supported tag, each containing category, action, confidence (0-1), evidence_ids, rationale
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


def load_classification_updates(
    limit: int = 50,
    ticker: str | None = None,
    updates_path: Path = DEFAULT_UPDATES_PATH,
) -> dict[str, Any]:
    data = _read_json(updates_path, {"schema_version": 1, "updates": []})
    updates = data.get("updates", [])
    if ticker:
        symbol = ticker.upper().strip()
        updates = [item for item in updates if item.get("ticker") == symbol]
    limit = max(1, min(limit, 100))
    return {"schema_version": data.get("schema_version", 1), "updates": updates[:limit]}


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
        min_confidence: float = 0.80,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.market_data = market_data or MarketDataService()
        self.decision_provider = decision_provider or DeepSeekClassificationProvider()
        self.researcher = researcher or OfficialSourceResearcher()
        self.universe_path = universe_path
        self.updates_path = updates_path
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
    def _last_checked(security: dict[str, Any]) -> datetime | None:
        raw_value = (security.get("classification") or {}).get("last_checked_at")
        if not raw_value:
            return None
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    def _select(
        self,
        securities: list[dict[str, Any]],
        tickers: list[str] | None,
        stale_days: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        if tickers:
            requested = {ticker.upper().strip() for ticker in tickers}
            selected = [security for security in securities if security.get("ticker") in requested]
            missing = requested.difference({security.get("ticker") for security in selected})
            if missing:
                raise ValueError(f"Ticker(s) not found in the Green Canopy universe: {', '.join(sorted(missing))}")
            return selected[:limit]

        cutoff = self.now() - timedelta(days=max(1, stale_days))
        stale = [security for security in securities if not self._last_checked(security) or self._last_checked(security) < cutoff]
        stale.sort(key=lambda item: (self._last_checked(item) is not None, item.get("rank", 99999)))
        return stale[:limit]

    @staticmethod
    def _valid_assessments(
        assessments: list[ClassificationAssessment],
        allowed_categories: tuple[str, ...],
        evidence_ids: set[str],
    ) -> list[ClassificationAssessment]:
        by_category: dict[str, ClassificationAssessment] = {}
        for assessment in assessments:
            if assessment.category not in allowed_categories:
                continue
            valid_ids = [source_id for source_id in assessment.evidence_ids if source_id in evidence_ids]
            by_category[assessment.category] = assessment.model_copy(update={"evidence_ids": valid_ids})
        return list(by_category.values())

    def _apply_assessments(
        self,
        current: list[str],
        assessments: list[ClassificationAssessment],
        allowed_categories: tuple[str, ...],
        evidence_ids: set[str],
    ) -> tuple[list[str], list[ClassificationAssessment]]:
        result = set(current)
        accepted: list[ClassificationAssessment] = []
        for assessment in self._valid_assessments(assessments, allowed_categories, evidence_ids):
            if assessment.confidence < self.min_confidence or not assessment.evidence_ids:
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
        used_ids = {source_id for assessment in accepted for source_id in assessment.evidence_ids}
        output = []
        for source in evidence:
            if source.id not in used_ids:
                continue
            output.append({
                "id": source.id,
                "kind": source.kind,
                "title": source.title,
                "source": source.source,
                "retrieved_at": source.retrieved_at,
                "url": source.url,
                "excerpt": source.content[:600],
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
        selected = self._select(universe.get("securities", []), tickers, stale_days, max(1, min(limit, 25)))
        results: list[dict[str, Any]] = []
        new_updates: list[dict[str, Any]] = []

        for security in selected:
            old_tags = list(security.get("tags", []))
            old_exclusions = list(security.get("exclusions", []))
            try:
                evidence = self._collect_evidence(security)
                decision = self.decision_provider.classify(security, evidence)
            except (MarketDataError, httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
                results.append({"ticker": security.get("ticker"), "status": "failed", "error": str(exc)})
                continue

            evidence_ids = {source.id for source in evidence}
            new_tags, accepted_tags = self._apply_assessments(
                old_tags, decision.tag_assessments, SUPPORTED_TAGS, evidence_ids,
            )
            new_exclusions, accepted_exclusions = self._apply_assessments(
                old_exclusions, decision.exclusion_assessments, SUPPORTED_EXCLUSIONS, evidence_ids,
            )
            accepted = accepted_tags + accepted_exclusions
            changed = new_tags != old_tags or new_exclusions != old_exclusions
            checked_at = self.now().isoformat()
            confidence = round(max((item.confidence for item in accepted), default=0.0), 3)

            if apply:
                security["tags"] = new_tags
                security["exclusions"] = new_exclusions
                security["classification"] = {
                    "agent": AGENT_NAME,
                    "model": self.decision_provider.model_name,
                    "last_checked_at": checked_at,
                    "confidence": confidence,
                    "evidence_source_count": len(evidence),
                }

            result = {
                "ticker": security["ticker"],
                "status": "changed" if changed else "unchanged",
                "old_tags": old_tags,
                "new_tags": new_tags,
                "old_exclusions": old_exclusions,
                "new_exclusions": new_exclusions,
                "confidence": confidence,
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
                    "greenwashing_flags": decision.greenwashing_flags,
                    "portfolio_impact": (
                        "Saved Green Canopy portfolios containing this security may show a different alignment score. "
                        "Allocations are not changed automatically."
                    ),
                }
                new_updates.append(update)

        if apply:
            if new_updates:
                universe["version"] = self.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                updates_data["updates"] = new_updates + updates_data.get("updates", [])
            _write_json(self.universe_path, universe)
            _write_json(self.updates_path, updates_data)

        return {
            "agent": AGENT_NAME,
            "mode": "apply" if apply else "dry_run",
            "selected": len(selected),
            "changed": sum(item["status"] == "changed" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "results": results,
            "announcements_created": len(new_updates) if apply else 0,
        }
