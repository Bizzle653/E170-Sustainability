from backend.models import QuestionnaireAnswers
from backend.services.investor_profile import build_profile
from backend.services.portfolio import (
    REDUNDANT_FUND_FAMILIES,
    SMALLER_STYLE_ETF_SECTORS,
    _dedupe_redundant_funds,
    select_candidates,
)


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


def test_asset_preference_stocks_only_returns_no_etfs():
    profile = build_profile(QuestionnaireAnswers())
    candidates, _ = select_candidates(profile, limit=24, asset_preference="stocks_only")
    assert candidates
    assert all(item["type"] == "stock" for item in candidates)


def test_asset_preference_etfs_only_returns_no_stocks():
    profile = build_profile(QuestionnaireAnswers())
    candidates, _ = select_candidates(profile, limit=24, asset_preference="etfs_only")
    assert candidates
    assert all(item["type"] == "etf" for item in candidates)


def test_asset_preference_stocks_only_does_not_shrink_the_candidate_pool():
    # stocks_only shouldn't be capped at the mixed-pool half-and-half reservation --
    # with no ETFs competing for slots it should get up to the full limit.
    profile = build_profile(QuestionnaireAnswers())
    candidates, _ = select_candidates(profile, limit=24, asset_preference="stocks_only")
    assert len(candidates) == 24


def test_asset_preference_both_is_unaffected():
    profile = build_profile(QuestionnaireAnswers())
    with_default = select_candidates(profile, limit=24)[0]
    with_explicit_both = select_candidates(profile, limit=24, asset_preference="both")[0]
    assert [item["ticker"] for item in with_default] == [item["ticker"] for item in with_explicit_both]


def test_size_style_established_favors_larger_companies_and_funds():
    profile = build_profile(QuestionnaireAnswers(size_style="established"))
    candidates, _ = select_candidates(profile, limit=24)
    stocks = [item for item in candidates if item["type"] == "stock"]
    etfs = [item for item in candidates if item["type"] == "etf"]
    assert stocks and etfs
    # "Established" should never surface a small/mid-cap-style fund over the many
    # large-cap-oriented funds available in this universe.
    assert all(item.get("sector") not in SMALLER_STYLE_ETF_SECTORS for item in etfs)
    assert sum(item.get("fortune_rank", 1000) for item in stocks) / len(stocks) < 100


def test_size_style_smaller_growth_favors_smaller_companies_and_funds():
    profile = build_profile(QuestionnaireAnswers(size_style="smaller_growth"))
    candidates, _ = select_candidates(profile, limit=24)
    stocks = [item for item in candidates if item["type"] == "stock"]
    etfs = [item for item in candidates if item["type"] == "etf"]
    assert stocks and etfs
    assert any(item.get("sector") in SMALLER_STYLE_ETF_SECTORS for item in etfs)
    assert sum(item.get("fortune_rank", 1000) for item in stocks) / len(stocks) > 400


def test_size_style_mix_does_not_shift_candidates():
    # "mix" is the default answer, so it must behave identically to leaving size_style
    # unset -- otherwise every profile built before this field existed would change.
    profile_default = build_profile(QuestionnaireAnswers())
    profile_mix = build_profile(QuestionnaireAnswers(size_style="mix"))
    default_tickers = [item["ticker"] for item in select_candidates(profile_default, limit=24)[0]]
    mix_tickers = [item["ticker"] for item in select_candidates(profile_mix, limit=24)[0]]
    assert default_tickers == mix_tickers


def test_size_style_still_reflects_priorities():
    # A fixed size preference shouldn't erase values-matching entirely -- different
    # priorities should still surface different top stocks.
    climate = select_candidates(build_profile(QuestionnaireAnswers(size_style="smaller_growth", priorities=["climate"])), limit=24)[0]
    labor = select_candidates(build_profile(QuestionnaireAnswers(size_style="smaller_growth", priorities=["fair_labor"])), limit=24)[0]
    climate_top = [item["ticker"] for item in climate if item["type"] == "stock"][:5]
    labor_top = [item["ticker"] for item in labor if item["type"] == "stock"][:5]
    assert climate_top != labor_top
