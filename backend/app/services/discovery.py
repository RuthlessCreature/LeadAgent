from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from app.models import DiscoveredUrl


DUCKDUCKGO_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
BING_SEARCH_URL = "https://www.bing.com/search"
YAHOO_SEARCH_URL = "https://search.yahoo.com/search"
DEFAULT_BROWSER_UA = (
    "Mozilla/5.0"
)
SOCIAL_DOMAINS = {
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "linkedin.com",
    "www.linkedin.com",
    "tiktok.com",
    "www.tiktok.com",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "youtube.com",
    "www.youtube.com",
    "pinterest.com",
    "www.pinterest.com",
}
LOW_SIGNAL_DOMAINS = {
    "en.wikipedia.org",
    "www.britannica.com",
    "www.history.com",
    "blog.wego.com",
}


def discover_public_urls(
    queries: list[str],
    limit_per_query: int = 10,
    exclude_social: bool = True,
    engines: list[str] | tuple[str, ...] | None = None,
) -> list[DiscoveredUrl]:
    discovered: list[DiscoveredUrl] = []
    seen_urls: set[str] = set()
    max_workers = max(1, min(6, len(queries)))
    selected_engines = _normalize_engines(engines)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_discover_for_query_sessionless, query, limit_per_query, exclude_social, selected_engines): query
            for query in queries
        }
        for future in as_completed(future_map):
            query_results = future.result()
            for row in query_results:
                if row.url in seen_urls:
                    continue
                seen_urls.add(row.url)
                discovered.append(row)

    return discovered


def _discover_for_query_sessionless(
    query: str,
    limit_per_query: int,
    exclude_social: bool,
    engines: tuple[str, ...],
) -> list[DiscoveredUrl]:
    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_BROWSER_UA})
    return _discover_for_query(session, query, limit_per_query, exclude_social, engines)


def _discover_for_query(
    session: requests.Session,
    query: str,
    limit_per_query: int,
    exclude_social: bool,
    engines: tuple[str, ...],
) -> list[DiscoveredUrl]:
    parsers: list[list[DiscoveredUrl]] = []
    for engine in engines:
        if engine == "duckduckgo":
            parsers.append(_parse_duckduckgo_results(_search_duckduckgo_html(session, query), query))
        elif engine == "yahoo":
            parsers.append(_parse_yahoo_results(_search_yahoo_html(session, query), query))
        elif engine == "bing":
            parsers.append(_parse_bing_results(_search_bing_html(session, query), query))

    results: list[DiscoveredUrl] = []
    seen_urls: set[str] = set()
    for batch in parsers:
        for row in batch:
            if row.url in seen_urls:
                continue
            if _should_skip_result(row.domain, exclude_social):
                continue
            seen_urls.add(row.url)
            results.append(row)
            if len(results) >= limit_per_query:
                return results
    return results


def _search_duckduckgo_html(session: requests.Session, query: str) -> str:
    try:
        response = session.get(
            f"{DUCKDUCKGO_HTML_SEARCH_URL}?q={quote_plus(query)}",
            timeout=10,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""
    return response.text


def _search_bing_html(session: requests.Session, query: str) -> str:
    try:
        response = session.get(
            f"{BING_SEARCH_URL}?q={quote_plus(query)}",
            timeout=10,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""
    return response.text


def _search_yahoo_html(session: requests.Session, query: str) -> str:
    try:
        response = session.get(
            f"{YAHOO_SEARCH_URL}?p={quote_plus(query)}",
            timeout=10,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""
    return response.text


def _parse_duckduckgo_results(html: str, query: str) -> list[DiscoveredUrl]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results: list[DiscoveredUrl] = []
    for node in soup.select(".result"):
        title_node = node.select_one(".result__title")
        link_node = node.select_one(".result__title a")
        if title_node is None or link_node is None:
            continue

        url = _resolve_result_url(link_node.get("href") or "")
        if not url:
            continue

        domain = (urlparse(url).netloc or "").lower()
        snippet_node = node.select_one(".result__snippet")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        results.append(
            DiscoveredUrl(
                query=query,
                title=title_node.get_text(" ", strip=True),
                url=url,
                snippet=snippet[:300],
                domain=domain,
            )
        )
    return results


def _parse_bing_results(html: str, query: str) -> list[DiscoveredUrl]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results: list[DiscoveredUrl] = []
    for node in soup.select("li.b_algo"):
        title_node = node.select_one("h2 a")
        if title_node is None:
            continue

        url = _resolve_bing_result_url(title_node.get("href") or "")
        if not url:
            continue

        domain = (urlparse(url).netloc or "").lower()
        snippet_node = node.select_one(".b_caption p")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        results.append(
            DiscoveredUrl(
                query=query,
                title=title_node.get_text(" ", strip=True),
                url=url,
                snippet=snippet[:300],
                domain=domain,
            )
        )
    return results


def _parse_yahoo_results(html: str, query: str) -> list[DiscoveredUrl]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results: list[DiscoveredUrl] = []
    for node in soup.select("div.algo"):
        link_node = node.select_one(".compTitle a[href]")
        title_node = node.select_one("h3.title")
        if link_node is None or title_node is None:
            continue

        url = _resolve_yahoo_result_url(link_node.get("href") or "")
        if not url:
            continue

        domain = (urlparse(url).netloc or "").lower()
        snippet_node = node.select_one(".compText p")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        results.append(
            DiscoveredUrl(
                query=query,
                title=title_node.get_text(" ", strip=True),
                url=url,
                snippet=snippet[:300],
                domain=domain,
            )
        )
    return results


def _resolve_result_url(href: str) -> str:
    raw = (href or "").strip()
    if not raw:
        return ""

    if raw.startswith("//duckduckgo.com/l/?"):
        raw = f"https:{raw}"
    if raw.startswith("https://duckduckgo.com/l/?") or raw.startswith("http://duckduckgo.com/l/?"):
        parsed = urlparse(raw)
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return target

    if raw.startswith("/l/?"):
        parsed = urlparse(raw)
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return target

    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    return ""


def _resolve_bing_result_url(href: str) -> str:
    raw = (href or "").strip()
    if not raw:
        return ""

    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if parsed.netloc.lower() != "www.bing.com":
            return raw
        query = parse_qs(parsed.query)
        encoded = query.get("u", [""])[0]
        if encoded.startswith("a1"):
            encoded = encoded[2:]
        if not encoded:
            return ""
        try:
            missing_padding = (-len(encoded)) % 4
            encoded += "=" * missing_padding
            decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
            return decoded
        except Exception:
            return ""

    return ""


def _resolve_yahoo_result_url(href: str) -> str:
    raw = (href or "").strip()
    if not raw:
        return ""

    if raw.startswith("http://") or raw.startswith("https://"):
        match = re.search(r"/RU=([^/]+)/RK=", raw)
        if match:
            return unquote(match.group(1))
        if urlparse(raw).netloc.lower() != "r.search.yahoo.com":
            return raw
    return ""


def _should_skip_result(domain: str, exclude_social: bool) -> bool:
    if not domain or domain.endswith(".pdf"):
        return True
    if exclude_social and domain in SOCIAL_DOMAINS:
        return True
    if domain in LOW_SIGNAL_DOMAINS:
        return True
    return False


def _normalize_engines(engines: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not engines:
        return ("duckduckgo", "yahoo", "bing")

    normalized: list[str] = []
    for engine in engines:
        lowered = str(engine or "").strip().lower()
        if lowered in {"duckduckgo", "yahoo", "bing"} and lowered not in normalized:
            normalized.append(lowered)

    return tuple(normalized) or ("duckduckgo", "yahoo", "bing")
