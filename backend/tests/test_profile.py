from backend.models import QuestionnaireAnswers
from backend.services.investor_profile import build_profile


def test_profile_is_deterministic_and_weights_sum_to_one():
    answers = QuestionnaireAnswers(
        priorities=["climate", "clean_water", "fair_labor"],
        risk="invest_more",
        decline_reaction="buy_more",
        horizon="10_plus_years",
    )
    first = build_profile(answers)
    second = build_profile(answers)
    assert first == second
    assert first.risk_score == 95
    assert round(sum(first.sustainability_priority_weights.values()), 4) == 1
    assert first.sustainability_priority_weights["climate"] > first.sustainability_priority_weights["fair_labor"]
