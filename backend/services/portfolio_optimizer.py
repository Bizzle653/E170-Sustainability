from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from backend.models import InvestorProfile


@dataclass
class OptimizationResult:
    weights: np.ndarray
    warning: str | None = None


def optimize_weights(
    prices: pd.DataFrame,
    alignment: list[float],
    income_ranks: list[float],
    profile: InvestorProfile,
    max_weight: float,
    force_failure: bool = False,
) -> OptimizationResult:
    returns = prices.pct_change().dropna(how="any")
    if returns.empty or prices.shape[1] < 5:
        raise ValueError("At least five investments with overlapping history are required")
    annual_returns = returns.mean().to_numpy() * 252
    covariance = returns.cov().to_numpy() * 252
    n = len(annual_returns)
    sustainability = np.asarray(alignment, dtype=float) / 100
    income = np.asarray(income_ranks, dtype=float)
    risk_penalty = 1.25 + (100 - profile.risk_score) / 18
    sustainability_bonus = {
        "none": 0.05,
        "small": 0.16,
        "moderate": 0.28,
        "strong": 0.42,
    }[profile.sustainability_tradeoff]
    # Growth-oriented expected return is already rewarded directly by the
    # expected_return term below, so this only needs to add a nudge for
    # income-oriented investors -- it fades to near-zero as return_priority
    # rises toward "long-term growth" and strengthens toward "income and
    # preservation", using each candidate's dividend-yield percentile rank
    # (income_ranks) rather than any fabricated income score.
    income_tilt = 0.18 * (1 - profile.return_priority)

    def objective(weights: np.ndarray) -> float:
        expected_return = float(weights @ annual_returns)
        variance = float(weights @ covariance @ weights)
        alignment_value = float(weights @ sustainability)
        income_value = float(weights @ income)
        return -(
            expected_return
            - risk_penalty * variance
            + sustainability_bonus * alignment_value
            + income_tilt * income_value
        )

    bounds = [(0.02, max_weight)] * n
    initial = np.repeat(1 / n, n)
    result = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=bounds,
        constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1}],
        options={"maxiter": 500},
    )
    if force_failure or not result.success or not np.isfinite(result.x).all():
        return OptimizationResult(np.repeat(1 / n, n), "Optimization failed; documented equal-weight fallback was used.")
    weights = np.maximum(result.x, 0)
    weights /= weights.sum()
    return OptimizationResult(weights)


def portfolio_metrics(prices: pd.DataFrame, weights: np.ndarray) -> dict[str, float]:
    returns = prices.pct_change().dropna(how="any")
    portfolio_returns = returns.to_numpy() @ weights
    wealth = pd.Series(1 + portfolio_returns, index=returns.index).cumprod()
    drawdown = wealth / wealth.cummax() - 1
    annual_return = float((1 + portfolio_returns.mean()) ** 252 - 1)
    annual_volatility = float(portfolio_returns.std(ddof=1) * np.sqrt(252))
    return {
        "annualized_historical_return": annual_return,
        "annualized_volatility": annual_volatility,
        "maximum_drawdown": float(drawdown.min()),
    }


def rounded_allocations(weights: np.ndarray, amount: float) -> tuple[list[float], list[float]]:
    percentages = [round(float(weight) * 100, 2) for weight in weights]
    percentages[-1] = round(100 - sum(percentages[:-1]), 2)
    dollars = [round(amount * pct / 100, 2) for pct in percentages]
    dollars[-1] = round(amount - sum(dollars[:-1]), 2)
    return percentages, dollars
