"""
url_resolver.py – Find consumer-facing URL and franchise offering URL for a brand.

Strategy (in priority order):
  1. Smart domain guess from brand name/slug (fastest, most reliable)
  2. DuckDuckGo Instant Answer API (no key required)
  3. Google search scrape (fallback)
  4. Fallback: return None and log for manual review.
"""

import re
import time
import logging
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

FRANCHISE_PATH_KEYWORDS = [
    "/franchise",
    "/franchising",
    "/own-a-franchise",
    "/become-a-franchisee",
    "/open-a-franchise",
    "/franchise-opportunity",
    "/franchise-info",
]


def _slug_to_domain_candidates(brand: str, slug: str) -> list:
    """
    Generate likely domain candidates from brand name/slug.
    e.g. '1-800-Packouts' → ['1800packouts.com', '1-800packouts.com', ...]
    """
    name = brand.lower()
    slug_lower = slug.lower()

    candidates = []

    # Strip common words and punctuation variants
    cleaned = re.sub(r"[^a-z0-9]", "", name)           # 1800packouts
    hyphen_clean = re.sub(r"[^a-z0-9-]", "", slug_lower)  # 1-800-packouts

    tlds = [".com", ".net", ".co"]
    for base in [cleaned, hyphen_clean, name.replace(" ", ""), name.replace(" ", "-")]:
        for tld in tlds:
            candidates.append(f"https://www.{base}{tld}")
            candidates.append(f"https://{base}{tld}")

    return list(dict.fromkeys(candidates))  # dedupe preserving order


def _verify_url(url: str, timeout: int = 8) -> Optional[str]:
    """Return the final URL if it resolves successfully, else None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code < 400:
            parsed = urlparse(resp.url)
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return None


def _ddg_search(query: str, timeout: int = 10) -> Optional[str]:
    """Use DuckDuckGo Instant Answer API to get top result URL."""
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            headers=HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("AbstractURL"):
            return data["AbstractURL"]
        topics = data.get("RelatedTopics", [])
        if topics and isinstance(topics[0], dict):
            return topics[0].get("FirstURL")
    except Exception as e:
        logger.debug("DDG search failed for '%s': %s", query, e)
    return None


def _google_search_url(query: str, timeout: int = 10) -> Optional[str]:
    """Fallback: scrape Google search results."""
    try:
        resp = requests.get(
            "https://www.google.com/search",
            params={"q": query, "num": 3},
            headers=HEADERS,
            timeout=timeout,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a[href]"):
            href = a["href"]
            if href.startswith("/url?q="):
                url = href.split("/url?q=")[1].split("&")[0]
                if "google.com" not in url and url.startswith("http"):
                    return url
    except Exception as e:
        logger.debug("Google search failed for '%s': %s", query, e)
    return None


def find_consumer_url(brand: str, slug: str = "", timeout: int = 8) -> Optional[str]:
    """Find the consumer-facing website for a brand."""

    # Strategy 1: Try domain guessing from slug/name (fastest + most reliable)
    for candidate in _slug_to_domain_candidates(brand, slug or brand):
        result = _verify_url(candidate, timeout)
        if result:
            logger.debug("  Domain guess hit: %s → %s", candidate, result)
            return result

    # Strategy 2: DuckDuckGo
    url = _ddg_search(f"{brand} official website", timeout)
    if url:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    # Strategy 3: Google scrape
    url = _google_search_url(brand, timeout)
    if url:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    return None


def find_franchise_url(brand: str, consumer_url: Optional[str], timeout: int = 8) -> Optional[str]:
    """Find the franchise offering URL for a brand."""

    # Strategy 1: check known franchise path keywords on the consumer site
    if consumer_url:
        for path in FRANCHISE_PATH_KEYWORDS:
            candidate = urljoin(consumer_url, path)
            try:
                resp = requests.head(candidate, headers=HEADERS, timeout=timeout, allow_redirects=True)
                if resp.status_code < 400:
                    return candidate
                time.sleep(0.2)
            except Exception:
                continue

    # Strategy 2: scrape homepage for franchise links
    if consumer_url:
        try:
            resp = requests.get(consumer_url, headers=HEADERS, timeout=timeout)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                text = a.get_text(strip=True).lower()
                if any(kw in href or kw in text for kw in ["franchise", "franchis"]):
                    full = urljoin(consumer_url, a["href"])
                    if urlparse(full).netloc == urlparse(consumer_url).netloc:
                        return full
        except Exception as e:
            logger.debug("Scraping franchise link failed for %s: %s", brand, e)

    # Strategy 3: search directly
    url = _ddg_search(f"{brand} franchise opportunity official site", timeout)
    if not url:
        url = _google_search_url(f"{brand} franchise opportunity", timeout)
    return url


def resolve_urls(brand: str, slug: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve both consumer URL and franchise offering URL for a brand.
    Returns (consumer_url, franchise_url).
    """
    logger.info("Resolving URLs for: %s", brand)
    consumer_url = find_consumer_url(brand, slug)
    franchise_url = find_franchise_url(brand, consumer_url)
    logger.info("  consumer_url = %s", consumer_url)
    logger.info("  franchise_url = %s", franchise_url)
    return consumer_url, franchise_url

