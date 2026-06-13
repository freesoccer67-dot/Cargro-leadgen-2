from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from urllib import robotparser
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .utils import clean_text, normalize_url, same_registered_domain, unique_preserve_order

LOGGER = logging.getLogger(__name__)

PRIORITY_LINK_TERMS = [
    "contact",
    "klantenservice",
    "service",
    "bezorg",
    "lever",
    "delivery",
    "shipping",
    "retour",
    "return",
    "over-ons",
    "about",
    "faq",
    "veelgestelde",
]


@dataclass
class CrawlResult:
    url: str
    status_code: int
    title: str
    text: str
    html: str
    links: list[str]
    fetched_with: str = "requests"
    error: str = ""


@dataclass
class CrawlLogEntry:
    website: str
    url: str
    status_code: int
    fetched_with: str
    error: str


class RobotsCache:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache: dict[str, robotparser.RobotFileParser | None] = {}

    def can_fetch(self, url: str) -> bool:
        if not self.settings.respect_robots:
            return True
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if robots_url not in self._cache:
            parser = robotparser.RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.read()
            except Exception as exc:  # noqa: BLE001 - robots checks should not crash the run
                LOGGER.info("Could not read robots.txt for %s: %s", parsed.netloc, exc)
                self._cache[robots_url] = None
            else:
                self._cache[robots_url] = parser
        parser = self._cache[robots_url]
        if parser is None:
            return True
        return parser.can_fetch(self.settings.user_agent, url)


def crawl_many(
    urls: list[str],
    settings: Settings,
) -> tuple[dict[str, list[CrawlResult]], list[CrawlLogEntry]]:
    robots = RobotsCache(settings)
    all_pages: dict[str, list[CrawlResult]] = {}
    logs: list[CrawlLogEntry] = []
    for url in unique_preserve_order([normalize_url(item) for item in urls if item]):
        pages, site_logs = crawl_site(url, settings, robots)
        all_pages[url] = pages
        logs.extend(site_logs)
    return all_pages, logs


def crawl_site(
    start_url: str,
    settings: Settings,
    robots: RobotsCache | None = None,
) -> tuple[list[CrawlResult], list[CrawlLogEntry]]:
    start_url = normalize_url(start_url)
    robots = robots or RobotsCache(settings)
    session = requests.Session()
    session.headers.update({"User-Agent": settings.user_agent})

    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    seen: set[str] = set()
    pages: list[CrawlResult] = []
    logs: list[CrawlLogEntry] = []

    while queue and len(pages) < settings.max_pages_per_domain:
        url, depth = queue.popleft()
        url = normalize_url(url)
        if url in seen or depth > settings.max_crawl_depth:
            continue
        seen.add(url)

        if not same_registered_domain(start_url, url):
            continue
        if not robots.can_fetch(url):
            logs.append(CrawlLogEntry(start_url, url, 0, "robots.txt", "Blocked by robots.txt"))
            continue

        result = fetch_page(url, settings, session)
        pages.append(result)
        logs.append(CrawlLogEntry(start_url, url, result.status_code, result.fetched_with, result.error))

        if result.links and depth < settings.max_crawl_depth:
            for link in prioritize_links(result.links):
                if link not in seen and same_registered_domain(start_url, link):
                    queue.append((link, depth + 1))

        if settings.rate_limit_seconds > 0:
            time.sleep(settings.rate_limit_seconds)

    return pages, logs


def fetch_page(url: str, settings: Settings, session: requests.Session) -> CrawlResult:
    try:
        response = session.get(url, timeout=settings.request_timeout)
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and response.text.strip().startswith("<") is False:
            return CrawlResult(url, response.status_code, "", "", "", [], error=f"Skipped {content_type}")
        html = response.text
        result = parse_html(url, response.status_code, html, "requests")
        if settings.enable_playwright and response.ok and len(result.text) < 200:
            fallback = fetch_with_playwright(url, settings)
            if fallback and len(fallback.text) > len(result.text):
                return fallback
        return result
    except requests.RequestException as exc:
        fallback = fetch_with_playwright(url, settings) if settings.enable_playwright else None
        if fallback:
            return fallback
        return CrawlResult(url, 0, "", "", "", [], error=str(exc))


def parse_html(url: str, status_code: int, html: str, fetched_with: str) -> CrawlResult:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = clean_text(soup.title.get_text(" ")) if soup.title else ""
    text = clean_text(soup.get_text(" "))
    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        normalized = normalize_url(href, url)
        if normalized.startswith(("http://", "https://")):
            links.append(normalized)
    return CrawlResult(
        url=url,
        status_code=status_code,
        title=title,
        text=text,
        html=html,
        links=unique_preserve_order(links),
        fetched_with=fetched_with,
    )


def fetch_with_playwright(url: str, settings: Settings) -> CrawlResult | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=settings.user_agent)
            response = page.goto(url, timeout=int(settings.request_timeout * 1000), wait_until="networkidle")
            html = page.content()
            status_code = response.status if response else 0
            browser.close()
            return parse_html(url, status_code, html, "playwright")
    except Exception as exc:  # noqa: BLE001 - optional fallback should be best effort
        LOGGER.info("Playwright fetch failed for %s: %s", url, exc)
        return None


def prioritize_links(links: list[str]) -> list[str]:
    priority: list[str] = []
    other: list[str] = []
    for link in links:
        lowered = link.lower()
        if any(term in lowered for term in PRIORITY_LINK_TERMS):
            priority.append(link)
        else:
            other.append(link)
    return unique_preserve_order(priority + other)
