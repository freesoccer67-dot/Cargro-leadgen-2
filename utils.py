from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd

from .config import Settings
from .search_api import SearchResult, discover_urls
from .utils import clean_text, registered_domain, unique_preserve_order


CANDIDATE_COLUMNS = [
    "url",
    "category",
    "keyword",
    "title",
    "snippet",
    "domain",
    "source_provider",
    "search_rank",
    "country",
    "language",
    "discovery_reason",
    "confidence_score",
    "status",
    "notes",
]

BAD_DOMAINS = {
    "google.com",
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
    "tiktok.com",
}

MARKETPLACE_DOMAINS = {
    "bol.com",
    "amazon.nl",
    "amazon.com",
    "marktplaats.nl",
    "ebay.com",
    "etsy.com",
    "aliexpress.com",
}

DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}
COMPANY_URL_TERMS = ["shop", "webshop", "winkel", "store", "meubel", "tuin", "bed", "fitness", "outdoor"]
PRODUCT_TERMS = [
    "webshop",
    "bezorgen",
    "bezorging",
    "levering",
    "tuinmeubelen",
    "loungeset",
    "fitnessapparatuur",
    "meubels",
    "bedden",
    "matras",
    "matrassen",
    "grote pakketten",
    "zware producten",
    "home gym",
]
CONTACT_DELIVERY_TERMS = ["contact", "klantenservice", "bezorgen", "levering", "delivery", "returns", "retour"]
BLOG_NEWS_TERMS = ["blog", "nieuws", "news", "article", "artikel", "review", "top 10", "beste "]


def discover_candidate_websites(
    keywords_df: pd.DataFrame,
    settings: Settings,
    default_max_results: int = 20,
) -> tuple[pd.DataFrame, list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    if keywords_df.empty or "keyword" not in keywords_df.columns:
        return empty_candidates(), ["Upload a search_keywords.csv file with a keyword column."]

    for _, keyword_row in keywords_df.fillna("").iterrows():
        keyword = str(keyword_row.get("keyword", "")).strip()
        if not keyword:
            continue
        max_results = _row_max_results(keyword_row, default_max_results)
        results, result_warnings = discover_urls([keyword], settings, limit_per_keyword=max_results)
        warnings.extend(result_warnings)
        for result in results:
            candidate = build_candidate_row(result, keyword_row)
            if candidate:
                rows.append(candidate)

    return candidates_dataframe(rows), unique_preserve_order(warnings)


def import_candidate_urls(df: pd.DataFrame, source_provider: str = "manual import") -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if df.empty or "url" not in df.columns:
        return empty_candidates()
    for index, row in df.fillna("").iterrows():
        url = normalize_candidate_url(str(row.get("url", "")))
        if not url:
            continue
        domain = registered_domain(url)
        rows.append(
            {
                "url": url,
                "category": str(row.get("category", "")),
                "keyword": str(row.get("keyword", "")),
                "title": str(row.get("title", "")),
                "snippet": str(row.get("snippet", "")),
                "domain": domain,
                "source_provider": str(row.get("source", source_provider)) or source_provider,
                "search_rank": int(row.get("search_rank", index + 1) or index + 1),
                "country": str(row.get("country", "")),
                "language": str(row.get("language", "")),
                "discovery_reason": "Manual candidate URL import",
                "confidence_score": 50,
                "status": str(row.get("status", "New")) or "New",
                "notes": str(row.get("notes", "")),
            }
        )
    return candidates_dataframe(rows)


def build_candidate_row(result: SearchResult, keyword_row: pd.Series) -> dict[str, Any] | None:
    normalized_url = normalize_candidate_url(result.url)
    if not normalized_url:
        return None

    domain = registered_domain(normalized_url)
    title = clean_text(result.title)
    snippet = clean_text(result.snippet)
    keyword = str(keyword_row.get("keyword", result.keyword)).strip()
    category = str(keyword_row.get("category", "")).strip()
    country = str(keyword_row.get("country", "")).strip()
    language = str(keyword_row.get("language", "")).strip()

    if should_exclude(normalized_url, title, snippet):
        return None

    score, reasons = confidence_score(
        url=normalized_url,
        domain=domain,
        title=title,
        snippet=snippet,
        keyword=keyword,
        category=category,
        country=country,
    )
    if score <= 0:
        return None

    return {
        "url": normalized_url,
        "category": category,
        "keyword": keyword,
        "title": title,
        "snippet": snippet,
        "domain": domain,
        "source_provider": result.provider,
        "search_rank": result.rank,
        "country": country,
        "language": language,
        "discovery_reason": "; ".join(reasons),
        "confidence_score": score,
        "status": "New",
        "notes": "",
    }


def normalize_candidate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url if re.match(r"^https?://", url, re.I) else f"https://{url}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path or "/"
    if _path_is_likely_result_page(path):
        path = "/"
    query_items = [(key, value) for key, value in parse_qsl(parsed.query) if key.lower() not in TRACKING_PARAMS]
    query = urlencode(query_items)
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path.rstrip("/") or "/", "", query, ""))


def should_exclude(url: str, title: str, snippet: str) -> bool:
    parsed = urlparse(url)
    domain = registered_domain(url)
    path = parsed.path.lower()
    text = f"{title} {snippet}".lower()

    if domain in BAD_DOMAINS or domain in MARKETPLACE_DOMAINS:
        return True
    if any(path.endswith(extension) for extension in DOCUMENT_EXTENSIONS):
        return True
    if any(social in parsed.netloc.lower() for social in BAD_DOMAINS):
        return True
    if any(term in text for term in ["linkedin", "facebook", "instagram", "youtube"]):
        return True
    return False


def confidence_score(
    url: str,
    domain: str,
    title: str,
    snippet: str,
    keyword: str,
    category: str,
    country: str,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    title_l = title.lower()
    snippet_l = snippet.lower()
    url_l = url.lower()
    domain_l = domain.lower()
    keyword_words = _meaningful_words(keyword)
    category_words = _meaningful_words(category)

    if keyword_words and any(word in title_l for word in keyword_words):
        score += 20
        reasons.append("keyword appears in title")
    if any(word in snippet_l for word in keyword_words + category_words):
        score += 20
        reasons.append("keyword/category words appear in snippet")
    if any(term in url_l or term in domain_l for term in COMPANY_URL_TERMS) or _looks_like_company_domain(domain):
        score += 15
        reasons.append("URL/domain looks like a company website")
    if domain_l.endswith((".nl", ".be")) or country.lower() in {"netherlands", "belgium"}:
        score += 15
        reasons.append("likely Netherlands/Belgium company")
    if any(term in f"{title_l} {snippet_l} {url_l}" for term in PRODUCT_TERMS):
        score += 20
        reasons.append("bulky webshop/product terms detected")
    if any(term in snippet_l for term in CONTACT_DELIVERY_TERMS):
        score += 10
        reasons.append("contact/delivery/returns terms in snippet")

    if domain in MARKETPLACE_DOMAINS or any(market in domain_l for market in MARKETPLACE_DOMAINS):
        score -= 30
        reasons.append("marketplace listing penalty")
    if any(term in title_l or term in url_l for term in BLOG_NEWS_TERMS):
        score -= 20
        reasons.append("blog/news result penalty")

    return max(0, min(100, score)), reasons or ["public search result"]


def candidates_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return empty_candidates()
    df = pd.DataFrame(rows)
    df = df.sort_values(["domain", "confidence_score", "search_rank"], ascending=[True, False, True])
    df = df.drop_duplicates(subset=["domain"], keep="first")
    df = df.sort_values(["confidence_score", "search_rank"], ascending=[False, True]).reset_index(drop=True)
    return df.reindex(columns=CANDIDATE_COLUMNS).fillna("")


def empty_candidates() -> pd.DataFrame:
    return pd.DataFrame(columns=CANDIDATE_COLUMNS)


def _row_max_results(row: pd.Series, default_max_results: int) -> int:
    try:
        return max(1, min(50, int(row.get("max_results", default_max_results) or default_max_results)))
    except (TypeError, ValueError):
        return default_max_results


def _meaningful_words(value: str) -> list[str]:
    return [
        word.lower()
        for word in re.findall(r"[a-zA-Z0-9À-ÿ]+", value or "")
        if len(word) >= 4 and word.lower() not in {"nederland", "netherlands", "webshop"}
    ]


def _looks_like_company_domain(domain: str) -> bool:
    if not domain or domain in BAD_DOMAINS:
        return False
    name = domain.split(".", 1)[0]
    return bool(re.search(r"[a-z]{4,}", name))


def _path_is_likely_result_page(path: str) -> bool:
    path_l = path.lower()
    if path_l in {"", "/"}:
        return False
    if any(path_l.endswith(extension) for extension in DOCUMENT_EXTENSIONS):
        return False
    return any(term in path_l for term in ["/product", "/category", "/collections", "/shop", "/webshop"])
