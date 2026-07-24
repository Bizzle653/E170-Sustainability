from __future__ import annotations

from backend.models import InvestorProfile, QuestionnaireAnswers


def build_profile(answers: QuestionnaireAnswers) -> InvestorProfile:
    risk_points = {
        "move_to_safety": 25,
        "stay_invested": 58,
        "invest_more": 82,
    }[answers.risk]
    reaction_adjustment = {"sell": -12, "hold": 0, "buy_more": 10}[answers.decline_reaction]
    horizon_adjustment = {"under_3_years": -15, "3_to_10_years": 0, "10_plus_years": 10}[answers.horizon]
    risk_score = max(5, min(95, risk_points + reaction_adjustment + horizon_adjustment))

    selected = list(dict.fromkeys(answers.priorities))
    priority_weights = {key: 0.0 for key in (
        "climate", "renewable_energy", "fair_labor", "human_rights",
        "biodiversity", "clean_water", "sustainable_agriculture",
        "circular_economy", "governance",
    )}
    if selected:
        descending = [1.0, 0.75, 0.55]
        raw = [descending[min(i, 2)] for i in range(len(selected))]
        total = sum(raw)
        for key, weight in zip(selected, raw):
            priority_weights[key] = round(weight / total, 4)

    profile_name = "Purpose Builder"
    if risk_score < 40:
        profile_name = "Steady Steward"
    elif risk_score > 72:
        profile_name = "Impact Growth Seeker"

    return InvestorProfile(
        profile_name=profile_name,
        profile_description=(
            f"A {'growth-oriented' if risk_score > 72 else 'cautious' if risk_score < 40 else 'balanced'} "
            f"investor prioritizing {', '.join(selected).replace('_', ' ') or 'broad sustainability'}."
        ),
        risk_score=risk_score,
        return_priority={"long_term_growth": 0.85, "growth_and_stability": 0.65, "income_and_preservation": 0.4}[answers.goal],
        sustainability_priority_weights=priority_weights,
        exclusions=list(dict.fromkeys(answers.exclusions)),
        time_horizon=answers.horizon,
        investment_objective=answers.goal,
        sustainability_tradeoff=answers.tradeoff,
        company_preference=answers.philosophy,
        max_concentration=answers.max_concentration,
    )
