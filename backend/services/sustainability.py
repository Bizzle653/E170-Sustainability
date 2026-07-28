from __future__ import annotations

from typing import Any

from backend.models import InvestorProfile
from backend.services.market_data import split_sentences


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

# Used to find a sentence in a company's own business description that grounds a tag
# match in something concrete, e.g. surfacing "...generating capacity consisting of
# nuclear, wind, solar..." as the evidence for a "Climate" match, instead of only
# asserting the tag with no connection to what the company actually does.
TAG_KEYWORDS = {
    "climate": [
        "climate", "carbon", "emission", "greenhouse gas", "clean energy", "renewable", "solar", "wind",
        "nuclear", "hydro", "decarbon", "net zero", "net-zero", "low-carbon", "low carbon", "green energy",
        "energy efficien", "fossil fuel", "electric vehicle",
    ],
    "renewable_energy": [
        "renewable", "solar", "wind", "hydro", "geothermal", "clean energy", "battery storage", "green energy",
        "wind farm", "solar farm", "biofuel", "biomass",
    ],
    "fair_labor": [
        "employee", "workforce", "labor practice", "workplace safety", "fair wage", "union", "benefits",
        "human capital", "diversity and inclusion", "employee training", "occupational health", "collective bargaining",
    ],
    "human_rights": [
        "human rights", "forced labor", "modern slavery", "supply chain", "child labor", "ethical sourcing",
        "responsible sourcing",
    ],
    "biodiversity": [
        "biodiversity", "ecosystem", "conservation", "habitat", "wildlife", "deforestation", "natural resource",
        "land use", "reforestation", "endangered species",
    ],
    "clean_water": [
        "water", "wastewater", "irrigation", "watershed", "water treatment", "water conservation",
        "water quality", "water scarcity", "water management", "water stewardship",
    ],
    "sustainable_agriculture": [
        "agricultur", "farm", "crop", "soil", "livestock", "organic", "food production", "sustainable farming",
        "land stewardship", "regenerative",
    ],
    "circular_economy": [
        "recycl", "circular economy", "reuse", "packaging", "waste reduction", "upcycl", "waste management",
        "materials recovery", "zero waste", "compost",
    ],
    "governance": [
        "board of directors", "corporate governance", "compliance", "audit", "shareholder", "ethics",
        "code of conduct", "risk management", "executive compensation", "transparency", "accountability",
        "anti-corruption", "whistleblower",
    ],
}


def _find_supporting_sentence(sentences: list[str], tag: str) -> str | None:
    keywords = TAG_KEYWORDS.get(tag, [])
    if not keywords:
        return None
    for sentence in sentences:
        lower = sentence.lower()
        if any(keyword in lower for keyword in keywords):
            return sentence
    return None


def compose_fund_snapshot(
    top_holdings: list[dict[str, Any]],
    universe_by_ticker: dict[str, dict[str, Any]],
    active_priorities: list[str],
    limit: int = 3,
) -> tuple[str | None, dict[str, str]]:
    """Turn a fund's real holdings into a short, prioritized snapshot instead of legal
    boilerplate: which of its top holdings actually relate to what this user selected,
    cross-referenced against Green Canopy's own tags where the holding is recognized.
    Returns (one-line snapshot, {tag: evidence sentence}) capped to `limit` holdings."""
    if not top_holdings:
        return None, {}

    active_set = set(active_priorities)
    annotated = []
    for holding in top_holdings:
        item = universe_by_ticker.get(holding["ticker"])
        tags = item.get("tags", []) if item else []
        annotated.append({"name": holding["name"], "tags": tags, "relevant": [t for t in tags if t in active_set]})

    # Prioritize holdings that relate to this user's own selected priorities first,
    # so the snapshot is tailored rather than just "here are the 3 biggest positions".
    annotated.sort(key=lambda h: (-len(h["relevant"]), -len(h["tags"])))
    chosen = annotated[:limit]

    parts = []
    for holding in chosen:
        labels = [PRIORITY_LABELS.get(t, t) for t in holding["relevant"]]
        parts.append(f"{holding['name']} ({', '.join(labels)})" if labels else holding["name"])
    sentence = f"Top holding: {parts[0]}." if len(parts) == 1 else f"Top holdings include {', '.join(parts[:-1])}, and {parts[-1]}."

    fund_evidence: dict[str, str] = {}
    for holding in annotated:
        for tag in holding["relevant"]:
            if tag not in fund_evidence:
                label = PRIORITY_LABELS.get(tag, tag)
                fund_evidence[tag] = f"{holding['name']}, a top holding, is tagged for {label} in Green Canopy's own classification."

    return sentence, fund_evidence


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
    diversification_bonus: float,
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

    # Only mention the diversification credit when this fund actually earned more than
    # the baseline every security gets -- i.e. its real current top holdings back up the
    # priorities it's matched on, not just because it's fund-shaped.
    if diversification_bonus > 3:
        sentences.append(
            "As a fund, it also receives a diversification credit here because its real current top holdings "
            "confirm the priorities it's matched on, rather than spreading risk on an unverified basis."
        )
    return " ".join(sentences)


def alignment_score(
    profile: InvestorProfile,
    tags: list[str],
    raw: dict[str, Any] | None,
    asset_type: str,
    business_summary: str | None = None,
    fund_evidence: dict[str, str] | None = None,
) -> dict[str, Any]:
    raw = raw or {}
    summary_sentences = split_sentences(business_summary)
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
    # A fund only earns extra credit beyond the baseline every security gets when its own
    # real current top holdings actually confirm the priorities it's matched on (real
    # fund_evidence), not simply for being fund-shaped -- an ETF carrying a curated tag
    # that its live holdings don't back up gets no more credit than an individual stock.
    if asset_type == "etf" and matched:
        evidenced_matches = sum(1 for key in matched if key in (fund_evidence or {}))
        diversification_bonus = 3 + 5 * (evidenced_matches / len(matched))
    else:
        diversification_bonus = 3
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
            "explanation": _compose_explanation(matched_labels, unmatched_labels, esg_component, completeness, diversification_bonus),
            "priority_breakdown": [
                {
                    "key": key,
                    "label": PRIORITY_LABELS.get(key, key.replace("_", " ")),
                    "matched": key in matched,
                    "profile_weight": round(profile.sustainability_priority_weights.get(key, 0.0), 4),
                    "supporting_evidence": (fund_evidence or {}).get(key) or _find_supporting_sentence(summary_sentences, key),
                }
                for key in active_priorities
            ],
            "esg_snapshot": esg_fields,
            "business_summary_available": bool(summary_sentences) or bool(fund_evidence),
        },
    }


def compose_portfolio_narrative(
    holdings: list[dict[str, Any]],
    sector_totals: dict[str, float],
    weighted_alignment: float,
    diversification_score: float,
) -> str:
    """A single readable paragraph summarizing a whole portfolio -- built entirely from
    data already computed elsewhere (top holdings, sector mix, matched priorities), not
    a language model. Reads like a personalized summary without calling anything live."""
    if not holdings:
        return ""

    sentences: list[str] = []

    top_sectors = sorted(sector_totals.items(), key=lambda item: -item[1])[:2]
    if top_sectors:
        sector_phrase = " and ".join(sector.lower() for sector, _ in top_sectors)
        top_holdings = sorted(holdings, key=lambda h: -h["weight"])[:3]
        names = [h["name"].rstrip(".") for h in top_holdings]
        anchor = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
        sentences.append(f"This portfolio leans toward {sector_phrase}, anchored by {anchor}.")

    priority_counts: dict[str, int] = {}
    for holding in holdings:
        for priority in holding.get("matched_priorities", []):
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
    if priority_counts:
        top_priority, top_count = max(priority_counts.items(), key=lambda item: item[1])
        share = round(top_count / len(holdings) * 100)
        sentences.append(f"{share}% of holdings were selected at least partly for supporting {top_priority}.")

    if weighted_alignment >= 70:
        align_word = "strongly"
    elif weighted_alignment >= 50:
        align_word = "moderately"
    else:
        align_word = "loosely"
    sector_count = len(sector_totals)
    sentences.append(
        f"Overall it {align_word} reflects your stated priorities (alignment {weighted_alignment}/100), spread "
        f"across {sector_count} sector{'s' if sector_count != 1 else ''} for a diversification score of "
        f"{diversification_score}/100."
    )

    return " ".join(sentences)
