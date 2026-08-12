import numpy as np
import pandas as pd

from backend.models import QuestionnaireAnswers
from backend.services.investor_profile import build_profile
from backend.services.portfolio_optimizer import optimize_weights, rounded_allocations


def sample_prices(columns=8):
    rng = np.random.default_rng(42)
    dates = pd.date_range("2023-01-01", periods=500, freq="B")
    returns = rng.normal(0.00035, 0.008, size=(len(dates), columns))
    return pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=dates, columns=[f"T{i}" for i in range(columns)])


def test_weights_total_100_and_respect_maximum():
    profile = build_profile(QuestionnaireAnswers(max_concentration=0.2))
    sectors = [f"Sector{i}" for i in range(8)]
    result = optimize_weights(sample_prices(), [70] * 8, [0.5] * 8, sectors, profile, 0.2)
    assert np.isclose(result.weights.sum(), 1)
    assert result.weights.max() <= 0.20001
    assert result.weights.min() >= 0.01999


def test_dollar_rounding_is_exact():
    percentages, dollars = rounded_allocations(np.array([0.2] * 5), 10003.17)
    assert sum(percentages) == 100
    assert sum(dollars) == 10003.17


def test_optimizer_failure_uses_documented_equal_weight_fallback():
    profile = build_profile(QuestionnaireAnswers())
    sectors = [f"Sector{i}" for i in range(5)]
    result = optimize_weights(sample_prices(5), [60] * 5, [0.5] * 5, sectors, profile, 0.2, force_failure=True)
    assert result.warning
    assert np.allclose(result.weights, np.repeat(0.2, 5))


def test_sector_weight_is_capped_even_when_positions_dominate_the_objective():
    profile = build_profile(QuestionnaireAnswers(max_concentration=0.2))
    # Four candidates share "Tech" and are ranked far above the rest on both
    # alignment and income, so an uncapped optimizer would pile into them. The
    # other four are each their own sector so only the Tech constraint binds
    # (two 4-way sector groups both capped at 0.35 would make the sum-to-1
    # equality constraint itself infeasible: 0.35 + 0.35 < 1).
    sectors = ["Tech", "Tech", "Tech", "Tech", "A", "B", "C", "D"]
    alignment = [95, 95, 95, 95, 10, 10, 10, 10]
    income = [1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    result = optimize_weights(sample_prices(), alignment, income, sectors, profile, 0.2, max_sector_weight=0.35)
    assert not result.warning
    tech_weight = result.weights[:4].sum()
    assert tech_weight <= 0.35 + 1e-4


def test_sector_cap_auto_relaxes_instead_of_forcing_equal_weight_fallback():
    profile = build_profile(QuestionnaireAnswers(max_concentration=0.2))
    # Mirrors a real narrow-priority profile: 6 of 8 matched candidates share one
    # sector. A flat 0.35 cap here is mathematically infeasible alongside the
    # per-position bounds (0.35 + 2*0.2 = 0.75 < 1), which used to make SLSQP fail
    # and fall back to equal weight -- 75% in that one sector, worse than no cap.
    sectors = ["Growth"] * 6 + ["A", "B"]
    result = optimize_weights(sample_prices(8), [70] * 8, [0.5] * 8, sectors, profile, 0.2, max_sector_weight=0.35)
    assert not result.warning
    assert result.note
    dominant_sector_weight = result.weights[:6].sum()
    assert dominant_sector_weight <= 0.6 + 1e-4  # the smallest feasible cap for this shape
    assert dominant_sector_weight < 0.75 - 1e-4  # strictly better than the old fallback outcome


def test_singleton_sector_does_not_add_a_constraint():
    profile = build_profile(QuestionnaireAnswers(max_concentration=0.2))
    sectors = [f"Sector{i}" for i in range(8)]
    result = optimize_weights(sample_prices(), [70] * 8, [0.5] * 8, sectors, profile, 0.2, max_sector_weight=0.05)
    # Every candidate is its own sector, so even an unreasonably tight sector cap
    # can't bind -- the per-position bound (0.02-0.2) is the only real limit.
    assert np.isclose(result.weights.sum(), 1)
    assert result.weights.max() <= 0.20001
