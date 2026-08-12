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


def _grouped_cap_constraints(
    groups: list[list[int]],
    max_weight: float,
    cap: float,
    label: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """Cap the combined weight of any group (sector, or correlation cluster) with more
    than one member. A singleton group can never breach a cap that's already >= the
    per-position max, so it's skipped -- and it still counts toward uncapped_capacity
    below. If the candidate pool itself is this concentrated, a fixed cap can make the
    sum-to-1 requirement infeasible alongside the per-position bounds; relax it to the
    smallest value that keeps the problem solvable, rather than let SLSQP fail and
    silently fall back to equal weight -- which respects no cap at all."""
    capped_groups = [indices for indices in groups if len(indices) > 1]
    if not capped_groups:
        return [], None
    uncapped_capacity = sum(max_weight for indices in groups if len(indices) == 1)
    min_feasible_cap = (1 - uncapped_capacity) / len(capped_groups)
    effective_cap = max(cap, min_feasible_cap)
    if effective_cap >= 1 - 1e-9:
        # The whole matched pool collapsed into (effectively) one group -- no cap can
        # meaningfully bind here. Worse, a constraint that sits exactly on its own
        # boundary for every feasible point (sum <= ~1 when the group already has to
        # sum to ~1) can destabilize SLSQP rather than act as a harmless no-op, so skip
        # adding it and say plainly why, instead of reporting a hollow "100% cap."
        return [], (
            f"Every matched candidate ended up in the same {label.lower()} group, so no "
            f"{label.lower()} concentration cap could be applied to this selection."
        )
    note = None
    if effective_cap > cap + 1e-9:
        note = (
            f"{label} concentration cap was widened to {effective_cap:.0%} (from {cap:.0%}) "
            f"because the matching investments were concentrated in a few {label.lower()}s."
        )
    constraints = [
        {"type": "ineq", "fun": (lambda w, idx=indices: effective_cap - w[idx].sum())}
        for indices in capped_groups
    ]
    return constraints, note


def _correlation_clusters(correlation: np.ndarray, threshold: float) -> list[list[int]]:
    """Group candidate indices into connected components wherever pairwise historical
    return correlation is at or above the threshold, so that positions which actually
    move together get treated as one concentration risk regardless of sector label --
    e.g. several large-cap growth ETFs from different providers tracking overlapping
    indices, which a same-label sector cap can't see if each is tagged differently."""
    n = correlation.shape[0]
    visited = [False] * n
    clusters: list[list[int]] = []
    for start in range(n):
        if visited[start]:
            continue
        stack = [start]
        visited[start] = True
        component: list[int] = []
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbor in range(n):
                if not visited[neighbor] and neighbor != node and correlation[node, neighbor] >= threshold:
                    visited[neighbor] = True
                    stack.append(neighbor)
        clusters.append(component)
    return clusters


def optimize_weights(
    prices: pd.DataFrame,
    alignment: list[float],
    income_ranks: list[float],
    sectors: list[str],
    profile: InvestorProfile,
    max_weight: float,
    max_sector_weight: float = 0.35,
    max_correlation_weight: float = 0.35,
    # Ordinary equity funds/stocks routinely sit at 0.7-0.9 correlation with each other
    # and the broad market -- that's normal beta, not redundancy. 0.95+ is reserved for
    # positions that are functionally near-duplicates (e.g. several large-cap growth
    # index funds tracking overlapping benchmarks), which is what this cap should catch.
    # A looser threshold chains ordinary correlated assets into one giant cluster via
    # transitive (single-linkage) grouping, which both misses the point of the cap and
    # can produce a degenerate all-encompassing group (see _grouped_cap_constraints).
    correlation_threshold: float = 0.95,
    force_failure: bool = False,
) -> OptimizationResult:
    returns = prices.pct_change().dropna(how="any")
    if returns.empty or prices.shape[1] < 5:
        raise ValueError("At least five investments with overlapping history are required")
    annual_returns = returns.mean().to_numpy() * 252
    covariance = returns.cov().to_numpy() * 252
    correlation = returns.corr().to_numpy()
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

    # Two independent backstops against concentration that the per-position cap alone
    # can't see: several individually-capped positions can still add up to most of the
    # portfolio if they share a sector label, OR if they simply move together (which a
    # label can miss entirely -- e.g. same-sector ETFs from different providers, or a
    # stock alongside a fund that already holds a large position in it).
    sector_groups: dict[str, list[int]] = {}
    for index, sector in enumerate(sectors):
        sector_groups.setdefault(sector, []).append(index)
    correlation_clusters = _correlation_clusters(correlation, correlation_threshold)

    constraints: list[dict[str, Any]] = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    sector_constraints, sector_note = _grouped_cap_constraints(
        list(sector_groups.values()), max_weight, max_sector_weight, "Sector"
    )
    correlation_constraints, correlation_note = _grouped_cap_constraints(
        correlation_clusters, max_weight, max_correlation_weight, "Correlation"
    )
    constraints += sector_constraints + correlation_constraints
    # Each axis relaxes its own cap independently if it alone would be infeasible; the
    # two axes aren't jointly solved for feasibility, but the equal-weight fallback
    # below already covers the rare case where SLSQP still can't satisfy both at once.
    note = " ".join(item for item in (sector_note, correlation_note) if item) or None

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
