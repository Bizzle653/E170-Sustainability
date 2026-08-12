import json
from datetime import datetime, timezone

from backend.services.classification_intelligence import (
    ClassificationAssessment,
    ClassificationDecision,
    EvidenceSource,
    SUPPORTED_TAGS,
    SustainabilityIntelligenceAgent,
    load_classification_updates,
    load_security_classification,
)


class FakeMarket:
    def get_info(self, symbol):
        return {
            "longName": "Example Energy",
            "quoteType": "EQUITY",
            "sector": "Energy",
            "industry": "Renewable Power",
            "longBusinessSummary": "Example Energy develops solar power and still operates a natural gas pipeline.",
            "website": "https://example.com",
        }

    def get_sustainability(self, symbol):
        return {}

    def get_top_holdings(self, symbol, limit=25):
        return []


class FakeResearcher:
    def collect(self, website):
        return [EvidenceSource(
            id="official-report",
            kind="official_web",
            title="Official report",
            source="Official company website",
            retrieved_at="2026-08-11T00:00:00+00:00",
            content="Solar power is a material segment. The company also operates a natural gas pipeline.",
            url=website,
        )]


class FakeProvider:
    model_name = "fake-classifier"

    def __init__(self, renewable_confidence=0.92):
        self.renewable_confidence = renewable_confidence

    def classify(self, security, evidence):
        market_quote = "Example Energy develops solar power and still operates a natural gas pipeline."
        official_solar_quote = "Solar power is a material segment."
        official_fossil_quote = "The company also operates a natural gas pipeline."
        citations = [
            {"evidence_id": "market-profile", "quote": market_quote},
            {"evidence_id": "official-report", "quote": official_solar_quote},
        ]
        tag_assessments = [
            ClassificationAssessment(
                category=category,
                action="insufficient",
                confidence=0.1,
                rationale="No material evidence was supplied for this category.",
            )
            for category in SUPPORTED_TAGS
            if category not in {"climate", "renewable_energy"}
        ]
        tag_assessments.extend([
            ClassificationAssessment(
                category="climate",
                action="remove",
                confidence=0.91,
                evidence_ids=["market-profile", "official-report"],
                citations=citations,
                rationale="The current operating profile does not support the broader climate-solutions label.",
            ),
            ClassificationAssessment(
                category="renewable_energy",
                action="add",
                confidence=self.renewable_confidence,
                evidence_ids=["market-profile", "official-report"],
                citations=citations,
                rationale="Solar power is a material operating segment.",
            ),
        ])
        return ClassificationDecision(
            summary="The cited operating-business evidence supports renewable energy and fossil-fuel exposure.",
            tag_assessments=tag_assessments,
            exclusion_assessments=[ClassificationAssessment(
                category="fossil_fuels",
                action="add",
                confidence=0.89,
                evidence_ids=["market-profile", "official-report"],
                citations=[
                    {"evidence_id": "market-profile", "quote": market_quote},
                    {"evidence_id": "official-report", "quote": official_fossil_quote},
                ],
                rationale="The company operates a natural gas pipeline.",
            )],
            greenwashing_flags=["A renewable claim exists alongside fossil-fuel infrastructure."],
        )


def test_decision_accepts_category_keyed_assessment_objects():
    decision = ClassificationDecision.model_validate({
        "summary": "Structured model result.",
        "tag_assessments": {
            "climate": {
                "action": "keep",
                "confidence": 0.88,
                "evidence_ids": ["market-profile"],
                "rationale": "The cited evidence supports the current category.",
            },
            "clean_water": {
                "category": "clean_water",
                "action": "insufficient",
                "confidence": 0.25,
                "evidence_ids": [],
                "rationale": "No material water evidence was supplied.",
            },
        },
        "exclusion_assessments": {
            "fossil_fuels": {
                "action": "remove",
                "confidence": 0.91,
                "evidence_ids": ["official-report"],
                "rationale": "The cited evidence no longer supports the exclusion.",
            },
        },
        "greenwashing_flags": [],
    })

    assert [item.category for item in decision.tag_assessments] == ["climate", "clean_water"]
    assert decision.exclusion_assessments[0].category == "fossil_fuels"


def _write_universe(path):
    path.write_text(json.dumps({
        "version": "old-version",
        "scope": {},
        "securities": [{
            "ticker": "TEST",
            "name": "Example Energy",
            "type": "stock",
            "sector": "Energy",
            "tags": ["climate"],
            "exclusions": [],
            "rank": 1,
        }],
    }), encoding="utf-8")


def test_agent_applies_high_confidence_changes_and_publishes_announcement(tmp_path):
    universe_path = tmp_path / "universe.json"
    updates_path = tmp_path / "updates.json"
    _write_universe(universe_path)

    fixed_now = datetime(2026, 8, 11, 12, 30, tzinfo=timezone.utc)
    agent = SustainabilityIntelligenceAgent(
        market_data=FakeMarket(),
        decision_provider=FakeProvider(),
        researcher=FakeResearcher(),
        universe_path=universe_path,
        updates_path=updates_path,
        min_confidence=0.80,
        now=lambda: fixed_now,
    )
    result = agent.run(tickers=["TEST"], apply=True)

    assert result["changed"] == 1
    stored = json.loads(universe_path.read_text(encoding="utf-8"))
    security = stored["securities"][0]
    assert security["tags"] == ["renewable_energy"]
    assert security["exclusions"] == ["fossil_fuels"]
    assert security["classification"]["agent"].startswith("Green Canopy")
    assert stored["version"] == "2026-08-11T12:30:00Z"

    updates = load_classification_updates(updates_path=updates_path)["updates"]
    assert len(updates) == 1
    assert updates[0]["added_tags"] == ["renewable_energy"]
    assert updates[0]["removed_tags"] == ["climate"]
    assert updates[0]["added_exclusions"] == ["fossil_fuels"]
    assert {item["id"] for item in updates[0]["evidence"]} == {"market-profile", "official-report"}
    assert all(item["quotes"] for item in updates[0]["evidence"])
    assert updates[0]["greenwashing_flags"]

    current = load_security_classification("test", universe_path, updates_path)
    assert current["tags"] == ["renewable_energy"]
    assert len(current["history"]) == 1


def test_agent_does_not_apply_low_confidence_addition(tmp_path):
    universe_path = tmp_path / "universe.json"
    updates_path = tmp_path / "updates.json"
    _write_universe(universe_path)

    agent = SustainabilityIntelligenceAgent(
        market_data=FakeMarket(),
        decision_provider=FakeProvider(renewable_confidence=0.60),
        researcher=FakeResearcher(),
        universe_path=universe_path,
        updates_path=updates_path,
        min_confidence=0.95,
        now=lambda: datetime(2026, 8, 11, tzinfo=timezone.utc),
    )
    result = agent.run(tickers=["TEST"], apply=True)

    assert result["changed"] == 0
    stored = json.loads(universe_path.read_text(encoding="utf-8"))["securities"][0]
    assert stored["tags"] == ["climate"]
    assert stored["exclusions"] == []
    assert "classification" not in stored
    assert load_classification_updates(updates_path=updates_path)["updates"] == []


def test_partial_batch_persists_success_and_queues_failure(tmp_path):
    universe_path = tmp_path / "universe.json"
    updates_path = tmp_path / "updates.json"
    state_path = tmp_path / "state.json"
    _write_universe(universe_path)
    universe = json.loads(universe_path.read_text(encoding="utf-8"))
    universe["securities"].append({
        "ticker": "FAIL",
        "name": "Unavailable Company",
        "type": "stock",
        "sector": "Unknown",
        "tags": [],
        "exclusions": [],
        "rank": 2,
    })
    universe_path.write_text(json.dumps(universe), encoding="utf-8")

    class PartialMarket(FakeMarket):
        def get_info(self, symbol):
            if symbol == "FAIL":
                raise ValueError("temporary upstream failure")
            return super().get_info(symbol)

    agent = SustainabilityIntelligenceAgent(
        market_data=PartialMarket(),
        decision_provider=FakeProvider(),
        researcher=FakeResearcher(),
        universe_path=universe_path,
        updates_path=updates_path,
        state_path=state_path,
        now=lambda: datetime(2026, 8, 11, tzinfo=timezone.utc),
    )
    result = agent.run(tickers=["TEST", "FAIL"], apply=True)

    assert result["run_status"] == "partial"
    assert result["changed"] == 1
    assert result["failed"] == 1
    assert load_classification_updates(updates_path=updates_path)["total"] == 1
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_run"]["status"] == "partial"
    assert state["retry_queue"][0]["ticker"] == "FAIL"


def test_change_is_rejected_when_model_quote_is_not_in_evidence(tmp_path):
    universe_path = tmp_path / "universe.json"
    updates_path = tmp_path / "updates.json"
    _write_universe(universe_path)

    provider = FakeProvider()
    original_classify = provider.classify

    def classify_with_invented_quotes(security, evidence):
        decision = original_classify(security, evidence)
        for assessment in decision.tag_assessments + decision.exclusion_assessments:
            if assessment.citations:
                assessment.citations[0].quote = "This sentence does not exist in any collected source."
                assessment.citations[1].quote = "Neither does this second invented sentence."
        return decision

    provider.classify = classify_with_invented_quotes
    agent = SustainabilityIntelligenceAgent(
        market_data=FakeMarket(),
        decision_provider=provider,
        researcher=FakeResearcher(),
        universe_path=universe_path,
        updates_path=updates_path,
    )
    result = agent.run(tickers=["TEST"], apply=True)

    assert result["changed"] == 0
    assert load_classification_updates(updates_path=updates_path)["total"] == 0
