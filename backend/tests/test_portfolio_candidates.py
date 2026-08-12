from backend.models import QuestionnaireAnswers
from backend.services.investor_profile import build_profile
from backend.services.portfolio import REDUNDANT_FUND_FAMILIES, _dedupe_redundant_funds, select_candidates


def test_dedupe_keeps_only_the_first_ranked_member_of_each_family():
    # Input must already be best-first ranked, same as select_candidates provides it.
    ranked = [
        {"ticker": "SPY"},
        {"ticker": "VOO"},
        {"ticker": "SOME_OTHER"},
        {"ticker": "IVV"},
        {"ticker": "QQQM"},
        {"ticker": "QQQ"},
    ]
    kept = [item["ticker"] for item in _dedupe_redundant_funds(ranked)]
    assert kept == ["SPY", "SOME_OTHER", "QQQM"]


def test_dedupe_is_a_no_op_when_no_family_overlaps():
    ranked = [{"ticker": "VTI"}, {"ticker": "SOME_OTHER"}]
    assert [item["ticker"] for item in _dedupe_redundant_funds(ranked)] == ["VTI", "SOME_OTHER"]


def test_select_candidates_never_returns_more_than_one_fund_per_family():
    # Exercised across a few different priority profiles since which ETFs make the
    # cut (and therefore which family members are even in play) depends on tag
    # matching -- the invariant that must hold regardless is "no duplicates."
    for priorities in [["climate"], ["governance"], ["fair_labor", "biodiversity"]]:
        profile = build_profile(QuestionnaireAnswers(priorities=priorities))
        candidates, _ = select_candidates(profile, limit=24)
        tickers = {item["ticker"] for item in candidates}
        for family in REDUNDANT_FUND_FAMILIES:
            overlap = tickers & family
            assert len(overlap) <= 1, f"more than one fund kept from {family}: {overlap}"
