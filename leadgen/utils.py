from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse, urlunparse

try:
    import tldextract
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    tldextract = None

if tldextract is not None:
    TLD_EXTRACTOR = tldextract.TLDExtract(cache_dir=None, suffix_list_urls=())
else:  # pragma: no cover - dependency is in requirements.txt
    TLD_EXTRACTOR = None


GENERIC_EMAIL_PREFIXES = {
    "info",
    "sales",
    "contact",
    "klantenservice",
    "service",
    "support",
    "logistiek",
    "logistics",
    "planning",
    "orders",
    "order",
    "admin",
    "hello",
    "b2b",
    "zakelijk",
    "webshop",
    "customerservice",
}


def clean_text(value: str) -> str:
    value = unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_url(url: str, base_url: str | None = None) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if base_url:
        url = urljoin(base_url, url)
    parsed = urlparse(url if re.match(r"^https?://", url, re.I) else f"https://{url}")
    scheme = parsed.scheme.lower() if parsed.scheme in {"http", "https"} else "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def registered_domain(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    if TLD_EXTRACTOR is None:
        host_parts = parsed.netloc.split(".")
        return ".".join(host_parts[-2:]) if len(host_parts) >= 2 else parsed.netloc
    extracted = TLD_EXTRACTOR(parsed.netloc)
    return ".".join(part for part in [extracted.domain, extracted.suffix] if part)


def same_registered_domain(left: str, right: str) -> bool:
    return registered_domain(left) == registered_domain(right)


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            output.append(value.strip())
    return output


def extract_emails(text: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text or "", re.I)
    return unique_preserve_order([email.lower() for email in candidates])


def is_generic_business_email(email: str) -> bool:
    local_part = email.split("@", 1)[0].lower()
    if "." in local_part and local_part not in {"customerservice"}:
        return False
    if local_part in GENERIC_EMAIL_PREFIXES:
        return True
    return any(local_part.startswith(f"{prefix}-") for prefix in GENERIC_EMAIL_PREFIXES)


def first_generic_email(text: str) -> str:
    for email in extract_emails(text):
        if is_generic_business_email(email):
            return email
    return ""


def extract_phone(text: str) -> str:
    patterns = [
        r"(?:\+31|0031|0)\s?(?:\d[\s.-]?){8,10}",
        r"(?:\+32|0032|0)\s?(?:\d[\s.-]?){8,10}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def snippet_around(text: str, term: str, radius: int = 90) -> str:
    text = clean_text(text)
    index = text.lower().find(term.lower())
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(text), index + len(term) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"
