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
    result = optimize_weights(sample_prices(), [70] * 8, profile, 0.2)
    assert np.isclose(result.weights.sum(), 1)
    assert result.weights.max() <= 0.20001
    assert result.weights.min() >= 0.01999


def test_dollar_rounding_is_exact():
    percentages, dollars = rounded_allocations(np.array([0.2] * 5), 10003.17)
    assert sum(percentages) == 100
    assert sum(dollars) == 10003.17


def test_optimizer_failure_uses_documented_equal_weight_fallback():
    profile = build_profile(QuestionnaireAnswers())
    result = optimize_weights(sample_prices(5), [60] * 5, profile, 0.2, force_failure=True)
    assert result.warning
    assert np.allclose(result.weights, np.repeat(0.2, 5))
