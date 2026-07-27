from backend.models import QuestionnaireAnswers
from backend.services.investor_profile import build_profile
from backend.services.sustainability import alignment_score


def test_missing_esg_reduces_confidence_without_inventing_raw_values():
    profile = build_profile(QuestionnaireAnswers(priorities=["climate"]))
    result = alignment_score(profile, ["climate"], {}, "etf")
    assert result["confidence"] in {"low", "medium"}
    # ESG data is unavailable industry-wide now, so a per-holding "unavailable" notice
    # is no longer useful signal; it's surfaced once in the portfolio-level warnings
    # instead of repeated on every holding.
    assert result["limitations"] == []
    assert "did not provide sustainability risk data" not in result["detail"]["explanation"]


def test_lower_yahoo_risk_score_produces_higher_alignment_component():
    profile = build_profile(QuestionnaireAnswers(priorities=["governance"]))
    lower_risk = alignment_score(profile, ["governance"], {"totalEsg": 10}, "stock")
    higher_risk = alignment_score(profile, ["governance"], {"totalEsg": 40}, "stock")
    assert lower_risk["alignment_score"] > higher_risk["alignment_score"]
