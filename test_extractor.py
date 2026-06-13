from __future__ import annotations

from typing import Any


def recommended_pitch(lead: dict[str, Any]) -> str:
    opportunity = str(lead.get("opportunity_type", "logistics support"))
    category = str(lead.get("category", "e-commerce"))
    return f"Position Cargro as a practical partner for {opportunity.lower()} in {category}."


def generate_outreach_draft(lead: dict[str, Any]) -> str:
    """Create a Dutch manual-review outreach draft.

    The system never sends email. This is copy only, intended for human review.
    """

    company = lead.get("company_name") or "jullie bedrijf"
    category = lead.get("category") or "grotere e-commerce producten"
    products = _join_or_default(lead.get("products_detected"), category)
    pain_points = _join_or_default(lead.get("possible_pain_points"), "bezorging, retourritten en piekmomenten")
    opportunity = lead.get("opportunity_type") or "geplande leveringen en transport"

    return (
        "Goedemiddag,\n\n"
        f"Ik kwam {company} tegen en zag dat jullie actief zijn met {products}. "
        "Wij werken met bakwagens, laadklep en Sprinter-capaciteit en ondersteunen bedrijven "
        "met geplande leveringen, retourritten en overflow in drukke periodes.\n\n"
        f"Op basis van wat ik online zag, lijkt vooral {pain_points.lower()} relevant. "
        f"Daar zouden wij mogelijk kunnen helpen met {str(opportunity).lower()}.\n\n"
        "Mocht het interessant zijn, denk ik graag mee over hoe wij jullie bezorging "
        "of retourproces kunnen ondersteunen.\n\n"
        "Met vriendelijke groet,\n"
    )


def _join_or_default(value: Any, default: str) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item) or default
    if value:
        return str(value)
    return default
