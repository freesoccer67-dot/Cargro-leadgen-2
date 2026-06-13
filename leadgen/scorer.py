from __future__ import annotations

from typing import Any


FIT_CATEGORIES = {
    "garden furniture",
    "fitness equipment",
    "beds and mattresses",
    "furniture",
    "home and garden",
    "bulky goods",
}


def score_and_classify(lead: dict[str, Any]) -> dict[str, Any]:
    lead = dict(lead)
    score = score_lead(lead)
    lead["lead_score"] = score
    lead["lead_priority"] = priority_from_score(score)
    lead["opportunity_type"] = classify_opportunities(lead, score)
    return lead


def score_lead(lead: dict[str, Any]) -> int:
    score = 0

    category = str(lead.get("category", "")).lower()
    country = str(lead.get("country", "")).lower()

    if lead.get("bulky_product_signals") or category in FIT_CATEGORIES:
        score += 25
    if lead.get("webshop_signal"):
        score += 15
    if lead.get("appointment_delivery_signal"):
        score += 10
    if lead.get("return_signals"):
        score += 10
    if lead.get("showroom_signal"):
        score += 10
    if lead.get("own_delivery_signal"):
        score += 10
    if has_fast_or_seasonal_signal(lead):
        score += 5
    if country in {"netherlands", "belgium"}:
        score += 10
    if lead.get("generic_email") or lead.get("phone"):
        score += 5
    if category in FIT_CATEGORIES:
        score += 10

    if not lead.get("bulky_product_signals") and category not in FIT_CATEGORIES:
        score -= 20
    if lead.get("small_parcel_signal") and not lead.get("bulky_product_signals"):
        score -= 15
    if not lead.get("webshop_signal") and not lead.get("delivery_signals"):
        score -= 15

    return max(0, min(100, score))


def has_fast_or_seasonal_signal(lead: dict[str, Any]) -> bool:
    text = " ".join(
        str(value).lower()
        for key, value in lead.items()
        if key in {"delivery_signals", "possible_pain_points", "short_summary", "evidence_snippets"}
    )
    return any(term in text for term in ["fast", "snel", "season", "seizoen", "drukke periode", "same day"])


def priority_from_score(score: int) -> str:
    if score >= 80:
        return "High priority"
    if score >= 60:
        return "Medium priority"
    if score >= 40:
        return "Low priority"
    return "Ignore/archive"


def classify_opportunities(lead: dict[str, Any], score: int | None = None) -> str:
    score = score if score is not None else score_lead(lead)
    if score < 40:
        return "Not relevant"

    opportunities: list[str] = []
    category = str(lead.get("category", "")).lower()
    text_blob = " ".join(str(lead.get(key, "")).lower() for key in lead)

    if lead.get("bulky_product_signals") or category in FIT_CATEGORIES:
        opportunities.append("Last-mile bulky delivery")
    if lead.get("own_delivery_signal"):
        opportunities.append("Overflow transport")
    if lead.get("return_signals"):
        opportunities.append("Return pickup service")
    if lead.get("appointment_delivery_signal"):
        opportunities.append("Scheduled delivery")
    if any(term in text_blob for term in ["bed", "matras", "meubel", "fitness", "zwaar", "bulky"]):
        opportunities.append("Two-man delivery")
    if any(term in text_blob for term in ["laadklep", "pallet", "grote pakketten", "grote producten"]):
        opportunities.append("Bakwagen with laadklep route")
    if any(term in text_blob for term in ["snel", "same day", "klein transport", "sprinter"]):
        opportunities.append("Sprinter route")
    if lead.get("fulfillment_signals"):
        opportunities.append("E-fulfillment pilot")
        opportunities.append("Storage + delivery")

    if not opportunities:
        return "Not relevant"
    return "; ".join(dict.fromkeys(opportunities))
