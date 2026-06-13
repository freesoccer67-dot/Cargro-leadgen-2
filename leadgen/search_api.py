from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import requests

from .config import Settings
from .utils import normalize_url, unique_preserve_order


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str
    keyword: str
    provider: str
    rank: int = 0


def discover_urls(
    keywords: Iterable[str],
    settings: Settings,
    limit_per_keyword: int = 10,
) -> tuple[list[SearchResult], list[str]]:
    """Use a configured legal search API to discover company URLs.

    This function intentionally does not scrape Google/Bing result pages. It only
    calls supported API endpoints when an API key is present.
    """

    provider = settings.search_provider.lower()
    if provider in {"", "manual"}:
        return [], ["No search provider configured. Use manual URL mode or add an API key."]

    if provider == "brave":
        return _brave_search(keywords, settings, limit_per_keyword)
    if provider == "bing":
        return _bing_search(keywords, settings, limit_per_keyword)
    if provider == "serpapi":
        return _serpapi_search(keywords, settings, limit_per_keyword)

    return [], [f"Unsupported SEARCH_PROVIDER '{settings.search_provider}'."]


def _brave_search(
    keywords: Iterable[str], settings: Settings, limit_per_keyword: int
) -> tuple[list[SearchResult], list[str]]:
    if not settings.brave_search_api_key:
        return [], ["BRAVE_SEARCH_API_KEY is missing."]

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": settings.brave_search_api_key,
        "User-Agent": settings.user_agent,
    }
    results: list[SearchResult] = []
    warnings: list[str] = []
    for keyword in keywords:
        try:
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": keyword, "count": min(limit_per_keyword, 20)},
                headers=headers,
                timeout=settings.request_timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            warnings.append(f"Brave search failed for '{keyword}': {exc}")
            continue

        for rank, item in enumerate(data.get("web", {}).get("results", []), start=1):
            url = normalize_url(item.get("url", ""))
            if url:
                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        snippet=item.get("description", ""),
                        keyword=keyword,
                        provider="brave",
                        rank=rank,
                    )
                )
    return _dedupe_results(results), warnings


def _bing_search(
    keywords: Iterable[str], settings: Settings, limit_per_keyword: int
) -> tuple[list[SearchResult], list[str]]:
    if not settings.bing_search_api_key:
        return [], ["BING_SEARCH_API_KEY is missing."]

    headers = {
        "Ocp-Apim-Subscription-Key": settings.bing_search_api_key,
        "User-Agent": settings.user_agent,
    }
    results: list[SearchResult] = []
    warnings: list[str] = []
    for keyword in keywords:
        try:
            response = requests.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params={"q": keyword, "count": min(limit_per_keyword, 50)},
                headers=headers,
                timeout=settings.request_timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            warnings.append(f"Bing search failed for '{keyword}': {exc}")
            continue

        for rank, item in enumerate(data.get("webPages", {}).get("value", []), start=1):
            url = normalize_url(item.get("url", ""))
            if url:
                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("name", ""),
                        snippet=item.get("snippet", ""),
                        keyword=keyword,
                        provider="bing",
                        rank=rank,
                    )
                )
    return _dedupe_results(results), warnings


def _serpapi_search(
    keywords: Iterable[str], settings: Settings, limit_per_keyword: int
) -> tuple[list[SearchResult], list[str]]:
    if not settings.serpapi_api_key:
        return [], ["SERPAPI_API_KEY is missing."]

    results: list[SearchResult] = []
    warnings: list[str] = []
    for keyword in keywords:
        try:
            response = requests.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "google",
                    "q": keyword,
                    "num": min(limit_per_keyword, 20),
                    "api_key": settings.serpapi_api_key,
                },
                headers={"User-Agent": settings.user_agent},
                timeout=settings.request_timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            warnings.append(f"SerpAPI search failed for '{keyword}': {exc}")
            continue

        for rank, item in enumerate(data.get("organic_results", []), start=1):
            url = normalize_url(item.get("link", ""))
            if url:
                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        keyword=keyword,
                        provider="serpapi",
                        rank=rank,
                    )
                )
    return _dedupe_results(results), warnings


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    ordered_urls = unique_preserve_order([result.url for result in results])
    by_url = {result.url: result for result in results}
    return [by_url[url] for url in ordered_urls]
