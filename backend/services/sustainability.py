from __future__ import annotations

from typing import Any

from backend.models import InvestorProfile


LOWER_IS_BETTER = {"totalEsg", "environmentScore", "socialScore", "governanceScore", "controversyLevel"}


def alignment_score(
    profile: InvestorProfile,
    tags: list[str],
    raw: dict[str, Any] | None,
    asset_type: str,
) -> dict[str, Any]:
    raw = raw or {}
    matched = [key for key, weight in profile.sustainability_priority_weights.items() if weight > 0 and key in tags]
    tag_score = sum(profile.sustainability_priority_weights.get(key, 0) for key in matched) * 100

    esg_values: list[float] = []
    for key in LOWER_IS_BETTER:
        value = raw.get(key)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        # Yahoo ESG risk fields are lower-is-better. Clamp to the documented
        # risk-style 0–100 range before converting to an alignment component.
        esg_values.append(max(0.0, min(100.0, 100.0 - numeric)))

    esg_component = sum(esg_values) / len(esg_values) if esg_values else None
    completeness = min(1.0, len(raw) / 8) if raw else 0.0
    diversification_bonus = 8 if asset_type == "etf" else 3
    score = 25 + tag_score * 0.52 + diversification_bonus
    if esg_component is not None:
        score += esg_component * 0.15 + completeness * 5
    score = round(max(0, min(100, score)), 1)
    confidence = "high" if len(raw) >= 8 and matched else "medium" if matched or raw else "low"
    return {
        "alignment_score": score,
        "matched_priorities": [item.replace("_", " ") for item in matched],
        "confidence": confidence,
        "limitations": [] if raw else ["Yahoo sustainability data was unavailable; alignment relies on Green Canopy classification metadata."],
    }
