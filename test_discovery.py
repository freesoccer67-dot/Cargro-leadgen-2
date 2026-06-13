from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .utils import (
    clean_text,
    extract_phone,
    first_generic_email,
    normalize_url,
    registered_domain,
    snippet_around,
    unique_preserve_order,
)


CATEGORY_TERMS = {
    "garden furniture": [
        "tuinmeubel",
        "loungeset",
        "tuinset",
        "parasols",
        "garden furniture",
        "outdoor furniture",
    ],
    "fitness equipment": [
        "fitnessapparatuur",
        "home gym",
        "loopband",
        "crosstrainer",
        "krachtstation",
        "fitness equipment",
    ],
    "beds and mattresses": ["bedden", "matras", "matrassen", "boxspring", "bed", "mattress"],
    "furniture": ["meubel", "bankstel", "kast", "tafel", "stoelen", "furniture", "sofa"],
    "home and garden": ["wonen", "tuin", "home and garden", "woonwinkel", "buitenleven"],
    "bulky goods": ["grote pakketten", "zware producten", "bulky", "large parcel", "heavy goods"],
}

BULKY_TERMS = [
    "groot pakket",
    "grote pakketten",
    "zwaar",
    "zware producten",
    "bulky",
    "large parcel",
    "pallet",
    "laadklep",
    "bakwagen",
    "two-man",
    "2-man",
    "grote artikelen",
    "grote producten",
]

DELIVERY_TERMS = [
    "bezorgen",
    "bezorging",
    "levering",
    "transport",
    "thuisbezorgd",
    "delivery",
    "shipping",
    "last mile",
]

RETURN_TERMS = ["retour", "retourneren", "retour ophalen", "returns", "return pickup", "omruilen"]

FULFILLMENT_TERMS = ["fulfillment", "e-fulfillment", "warehousing", "opslag", "voorraadbeheer"]

OWN_DELIVERY_TERMS = ["eigen bezorg", "eigen transport", "eigen chauffeurs", "own delivery", "eigen levering"]

APPOINTMENT_TERMS = [
    "bezorgafspraak",
    "afspraak",
    "geplande levering",
    "delivery appointment",
    "scheduled delivery",
    "leverdatum kiezen",
]

SHOWROOM_TERMS = ["showroom", "winkel", "afhalen", "pick-up", "bezoek onze showroom"]

WEBSHOP_TERMS = ["webshop", "winkelwagen", "checkout", "shopify", "woocommerce", "bol.com", "bestellen"]

SMALL_PARCEL_TERMS = ["brievenbuspakje", "kleine pakketten", "small parcel", "pakketpost"]


def extract_lead(website: str, pages: list[Any], category_hint: str = "") -> dict[str, Any]:
    website = normalize_url(website)
    combined_text = clean_text(" ".join(_page_text(page) for page in pages))
    combined_html = " ".join(_page_html(page) for page in pages)
    urls = unique_preserve_order([_page_url(page) for page in pages if _page_url(page)])

    company_name = detect_company_name(website, pages)
    category = category_hint or detect_category(combined_text)

    product_signals = collect_category_signals(combined_text)
    bulky_signals = find_terms(combined_text, BULKY_TERMS)
    delivery_signals = find_terms(combined_text, DELIVERY_TERMS)
    return_signals = find_terms(combined_text, RETURN_TERMS)
    fulfillment_signals = find_terms(combined_text, FULFILLMENT_TERMS)
    own_delivery = bool(find_terms(combined_text, OWN_DELIVERY_TERMS))
    appointment_delivery = bool(find_terms(combined_text, APPOINTMENT_TERMS))
    showroom = bool(find_terms(combined_text, SHOWROOM_TERMS))
    webshop = bool(find_terms(combined_text, WEBSHOP_TERMS) or re.search(r"add to cart|in winkelwagen", combined_html, re.I))

    lead = {
        "lead_id": "",
        "company_name": company_name,
        "website": website,
        "category": category,
        "country": detect_country(website, combined_text),
        "city": "",
        "generic_email": first_generic_email(combined_text),
        "phone": extract_phone(combined_text),
        "contact_url": first_matching_url(urls, ["contact", "klantenservice", "service"]),
        "delivery_url": first_matching_url(urls, ["bezorg", "lever", "delivery", "shipping"]),
        "returns_url": first_matching_url(urls, ["retour", "return"]),
        "about_url": first_matching_url(urls, ["over-ons", "about"]),
        "products_detected": product_signals,
        "bulky_product_signals": bulky_signals,
        "delivery_signals": delivery_signals,
        "return_signals": return_signals,
        "fulfillment_signals": fulfillment_signals,
        "own_delivery_signal": own_delivery,
        "appointment_delivery_signal": appointment_delivery,
        "showroom_signal": showroom,
        "webshop_signal": webshop,
        "small_parcel_signal": bool(find_terms(combined_text, SMALL_PARCEL_TERMS)),
        "possible_pain_points": detect_pain_points(
            delivery_signals, return_signals, own_delivery, appointment_delivery, fulfillment_signals
        ),
        "short_summary": "",
        "source_urls": urls,
        "evidence_snippets": evidence_snippets(pages),
        "date_added": date.today().isoformat(),
        "status": "New",
        "notes": "",
    }
    lead["short_summary"] = build_summary(lead)
    return lead


def detect_company_name(website: str, pages: list[Any]) -> str:
    for page in pages:
        html = _page_html(page)
        if html:
            soup = BeautifulSoup(html, "lxml")
            for selector in ["meta[property='og:site_name']", "meta[name='application-name']"]:
                tag = soup.select_one(selector)
                content = tag.get("content", "").strip() if tag else ""
                if content:
                    return clean_text(content)
            h1 = soup.find("h1")
            if h1 and clean_text(h1.get_text(" ")):
                name = clean_text(h1.get_text(" "))
                if len(name) <= 80:
                    return name
        title = clean_text(_page_title(page))
        if title:
            return re.split(r"\s[-|]\s", title)[0].strip()[:80]

    domain = registered_domain(website).split(".")[0]
    return domain.replace("-", " ").title()


def detect_category(text: str) -> str:
    lowered = text.lower()
    best_category = ""
    best_count = 0
    for category, terms in CATEGORY_TERMS.items():
        count = sum(1 for term in terms if term.lower() in lowered)
        if count > best_count:
            best_category = category
            best_count = count
    return best_category or "Uncategorized"


def collect_category_signals(text: str) -> list[str]:
    signals: list[str] = []
    for terms in CATEGORY_TERMS.values():
        signals.extend(find_terms(text, terms))
    return unique_preserve_order(signals)


def find_terms(text: str, terms: list[str]) -> list[str]:
    lowered = (text or "").lower()
    return unique_preserve_order([term for term in terms if term.lower() in lowered])


def detect_country(website: str, text: str) -> str:
    host = urlparse(website).netloc.lower()
    lowered = text.lower()
    if host.endswith(".be") or "belgie" in lowered or "belgium" in lowered:
        return "Belgium"
    if host.endswith(".nl") or "nederland" in lowered or "netherlands" in lowered:
        return "Netherlands"
    return ""


def first_matching_url(urls: list[str], terms: list[str]) -> str:
    for url in urls:
        lowered = url.lower()
        if any(term in lowered for term in terms):
            return url
    return ""


def detect_pain_points(
    delivery_signals: list[str],
    return_signals: list[str],
    own_delivery: bool,
    appointment_delivery: bool,
    fulfillment_signals: list[str],
) -> list[str]:
    pain_points: list[str] = []
    if delivery_signals:
        pain_points.append("Delivery capacity and route planning")
    if return_signals:
        pain_points.append("Large-item returns and pickup handling")
    if own_delivery:
        pain_points.append("Overflow support for own delivery fleet")
    if appointment_delivery:
        pain_points.append("Scheduled delivery coordination")
    if fulfillment_signals:
        pain_points.append("Potential storage or fulfillment support")
    return pain_points


def evidence_snippets(pages: list[Any]) -> list[str]:
    snippets: list[str] = []
    terms = BULKY_TERMS + DELIVERY_TERMS + RETURN_TERMS + OWN_DELIVERY_TERMS + APPOINTMENT_TERMS + SHOWROOM_TERMS
    for page in pages:
        text = _page_text(page)
        url = _page_url(page)
        for term in terms:
            snippet = snippet_around(text, term)
            if snippet:
                snippets.append(f"{url}: {snippet}")
                break
    return unique_preserve_order(snippets)[:8]


def build_summary(lead: dict[str, Any]) -> str:
    parts = []
    if lead.get("category"):
        parts.append(str(lead["category"]))
    if lead.get("webshop_signal"):
        parts.append("webshop")
    if lead.get("bulky_product_signals"):
        parts.append("bulky-product signals")
    if lead.get("delivery_signals"):
        parts.append("delivery relevance")
    if not parts:
        return "Company-level information found, but logistics fit is unclear."
    return "Detected " + ", ".join(parts) + "."


def _page_text(page: Any) -> str:
    if isinstance(page, dict):
        return page.get("text", "")
    return getattr(page, "text", "")


def _page_html(page: Any) -> str:
    if isinstance(page, dict):
        return page.get("html", "")
    return getattr(page, "html", "")


def _page_title(page: Any) -> str:
    if isinstance(page, dict):
        return page.get("title", "")
    return getattr(page, "title", "")


def _page_url(page: Any) -> str:
    if isinstance(page, dict):
        return page.get("url", "")
    return getattr(page, "url", "")
