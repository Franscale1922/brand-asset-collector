"""
logo_fetcher.py – Download the highest-quality logo for a brand.

Strategy:
  1. Clearbit Logo API (free, high quality, no key needed).
  2. Scrape brand's website for Open Graph image or apple-touch-icon.
  3. Fallback: None (logged for manual handling).
"""

import logging
import os
from typing import Optional
from urllib.parse import urlparse

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

CLEARBIT_URL = "https://logo.clearbit.com/{domain}?size=512"


def _domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    netloc = parsed.netloc or url
    # Strip www.
    return netloc.replace("www.", "").split(":")[0]


def _try_clearbit(domain: str, dest_path: str, timeout: int = 10) -> bool:
    """Try downloading logo from Clearbit."""
    url = CLEARBIT_URL.format(domain=domain)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code == 200 and resp.headers.get("Content-Type", "").startswith("image"):
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            logger.info("  Logo via Clearbit: %s", url)
            return True
    except Exception as e:
        logger.debug("Clearbit failed for %s: %s", domain, e)
    return False


def _try_og_image(consumer_url: str, dest_path: str, timeout: int = 10) -> bool:
    """Try scraping OG image / apple-touch-icon from homepage."""
    try:
        resp = requests.get(consumer_url, headers=HEADERS, timeout=timeout)
        soup = BeautifulSoup(resp.text, "html.parser")

        candidates = []

        # OG image
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            candidates.append(og["content"])

        # Apple touch icon (usually high res)
        for rel in ["apple-touch-icon", "apple-touch-icon-precomposed"]:
            icon = soup.find("link", rel=lambda r: r and rel in r)
            if icon and icon.get("href"):
                href = icon["href"]
                if not href.startswith("http"):
                    href = consumer_url.rstrip("/") + "/" + href.lstrip("/")
                candidates.append(href)

        for img_url in candidates:
            try:
                img_resp = requests.get(img_url, headers=HEADERS, timeout=timeout)
                if img_resp.status_code == 200 and img_resp.headers.get("Content-Type", "").startswith("image"):
                    with open(dest_path, "wb") as f:
                        f.write(img_resp.content)
                    logger.info("  Logo via OG/icon scrape: %s", img_url)
                    return True
            except Exception:
                continue
    except Exception as e:
        logger.debug("OG image scrape failed for %s: %s", consumer_url, e)
    return False


def fetch_logo(brand: str, consumer_url: Optional[str], output_dir: str, slug: str) -> Optional[str]:
    """
    Download logo for a brand.

    Returns the local file path on success, None on failure.
    """
    os.makedirs(output_dir, exist_ok=True)
    dest_path = os.path.join(output_dir, f"{slug}_logo.png")

    domain = _domain_from_url(consumer_url)

    # Strategy 1: Clearbit
    if domain and _try_clearbit(domain, dest_path):
        return dest_path

    # Strategy 2: Scrape OG image
    if consumer_url and _try_og_image(consumer_url, dest_path):
        return dest_path

    # Strategy 3: Try brand name as domain guess
    guessed_domain = brand.lower().replace(" ", "") + ".com"
    if guessed_domain != domain and _try_clearbit(guessed_domain, dest_path):
        return dest_path

    logger.warning("  Could not fetch logo for %s — manual review needed.", brand)
    return None
