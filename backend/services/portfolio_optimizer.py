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
    note: str | None = None


def optimize_weights(
    prices: pd.DataFrame,
    alignment: list[float],
    income_ranks: list[float],
    sectors: list[str],
    profile: InvestorProfile,
    max_weight: float,
    max_sector_weight: float = 0.35,
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

    # Backstop against concentration that the per-position cap alone can't see: several
    # individually-capped positions in the same sector (e.g. three different mega-cap
    # tech names, or overlapping broad-market funds sharing a sector label) can still
    # add up to most of the portfolio. A sector with only one candidate can never
    # breach a cap that's already >= the per-position max, so it's skipped.
    sector_groups: dict[str, list[int]] = {}
    for index, sector in enumerate(sectors):
        sector_groups.setdefault(sector, []).append(index)
    capped_groups = [indices for indices in sector_groups.values() if len(indices) > 1]

    constraints: list[dict[str, Any]] = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    note: str | None = None
    if capped_groups:
        uncapped_capacity = sum(max_weight for indices in sector_groups.values() if len(indices) == 1)
        # If the candidate pool itself is this concentrated (e.g. a niche priority profile
        # matched mostly one sector), a fixed cap can make the sum-to-1 requirement
        # infeasible alongside the per-position bounds. Relax the cap to the smallest
        # value that keeps the problem solvable, rather than let SLSQP fail and silently
        # fall back to equal weight -- which respects no cap at all and would leave the
        # dominant sector even more concentrated than a relaxed cap does.
        min_feasible_cap = (1 - uncapped_capacity) / len(capped_groups)
        effective_cap = max(max_sector_weight, min_feasible_cap)
        if effective_cap > max_sector_weight + 1e-9:
            note = (
                f"Sector concentration cap was widened to {effective_cap:.0%} (from {max_sector_weight:.0%}) "
                "because the matching investments were concentrated in a few sectors."
            )
        for indices in capped_groups:
            constraints.append({
                "type": "ineq",
                "fun": (lambda w, idx=indices: effective_cap - w[idx].sum()),
            })

    result = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500},
    )
    if force_failure or not result.success or not np.isfinite(result.x).all():
        return OptimizationResult(np.repeat(1 / n, n), "Optimization failed; documented equal-weight fallback was used.")
    weights = np.maximum(result.x, 0)
    weights /= weights.sum()
    return OptimizationResult(weights, note=note)


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
