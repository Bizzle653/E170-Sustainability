from __future__ import annotations

from typing import Any

from backend.models import InvestorProfile


LOWER_IS_BETTER = {"totalEsg", "environmentScore", "socialScore", "governanceScore", "controversyLevel"}

PRIORITY_LABELS = {
    "climate": "Climate",
    "renewable_energy": "Clean energy",
    "fair_labor": "Fair work",
    "human_rights": "Human rights",
    "biodiversity": "Nature",
    "clean_water": "Water",
    "sustainable_agriculture": "Agriculture",
    "circular_economy": "Circularity",
    "governance": "Governance",
}

ESG_FIELD_LABELS = {
    "totalEsg": "Overall ESG risk",
    "environmentScore": "Environmental risk",
    "socialScore": "Social risk",
    "governanceScore": "Governance risk",
    "controversyLevel": "Controversy level",
}


def _compose_explanation(
    matched_labels: list[str],
    unmatched_labels: list[str],
    esg_component: float | None,
    completeness: float,
    asset_type: str,
) -> str:
    sentences: list[str] = []
    if matched_labels:
        verb = "is" if len(matched_labels) == 1 else "are"
        sentences.append(
            f"Green Canopy's classification data tags this holding for {', '.join(matched_labels)}, which {verb} "
            f"among the priorities you selected."
        )
    else:
        sentences.append(
            "Green Canopy's classification data doesn't tag this holding for any of the priorities you selected."
        )
    if unmatched_labels:
        sentences.append(f"It is not tagged for {', '.join(unmatched_labels)}, which you also prioritized.")

    if esg_component is not None:
        risk_word = "low" if esg_component >= 66 else "moderate" if esg_component >= 33 else "elevated"
        coverage_word = "full" if completeness >= 0.9 else "partial"
        sentences.append(
            f"Yahoo's third-party ESG risk data was available ({coverage_word} coverage) and points to {risk_word} "
            f"overall ESG risk, which nudges the score accordingly."
        )

    if asset_type == "etf":
        sentences.append(
            "As a fund, it also receives a small diversification credit for spreading exposure across many "
            "underlying holdings instead of concentrating risk in one company."
        )
    return " ".join(sentences)


def alignment_score(
    profile: InvestorProfile,
    tags: list[str],
    raw: dict[str, Any] | None,
    asset_type: str,
) -> dict[str, Any]:
    raw = raw or {}
    active_priorities = [key for key, weight in profile.sustainability_priority_weights.items() if weight > 0]
    matched = [key for key in active_priorities if key in tags]
    unmatched = [key for key in active_priorities if key not in tags]
    tag_score = sum(profile.sustainability_priority_weights.get(key, 0) for key in matched) * 100

    esg_fields: list[dict[str, Any]] = []
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
        esg_fields.append({"key": key, "label": ESG_FIELD_LABELS.get(key, key), "raw_value": numeric})

    esg_component = sum(esg_values) / len(esg_values) if esg_values else None
    completeness = min(1.0, len(raw) / 8) if raw else 0.0
    diversification_bonus = 8 if asset_type == "etf" else 3
    score = 25 + tag_score * 0.52 + diversification_bonus
    if esg_component is not None:
        score += esg_component * 0.15 + completeness * 5
    score = round(max(0, min(100, score)), 1)
    # "high" used to require dense third-party ESG coverage, which no longer exists for
    # any security. Confidence is now driven by real, always-available signal: how many
    # of the user's own priorities this holding actually matches (plus ESG coverage as a
    # bonus path, dormant today but ready if Yahoo restores the data).
    strong_esg_coverage = bool(matched) and completeness >= 0.9
    confidence = (
        "high" if len(matched) >= 2 or strong_esg_coverage
        else "medium" if matched or raw
        else "low"
    )

    matched_labels = [PRIORITY_LABELS.get(key, key.replace("_", " ")) for key in matched]
    unmatched_labels = [PRIORITY_LABELS.get(key, key.replace("_", " ")) for key in unmatched]

    return {
        "alignment_score": score,
        "matched_priorities": matched_labels,
        "confidence": confidence,
        "limitations": [],
        "detail": {
            "explanation": _compose_explanation(matched_labels, unmatched_labels, esg_component, completeness, asset_type),
            "priority_breakdown": [
                {
                    "key": key,
                    "label": PRIORITY_LABELS.get(key, key.replace("_", " ")),
                    "matched": key in matched,
                    "profile_weight": round(profile.sustainability_priority_weights.get(key, 0.0), 4),
                }
                for key in active_priorities
            ],
            "esg_snapshot": esg_fields,
        },
    }
