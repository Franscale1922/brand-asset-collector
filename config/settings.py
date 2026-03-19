"""
Central configuration for brand-asset-collector.
Edit these values to match your environment.
"""

import os

# ─── Google Drive ─────────────────────────────────────────────────────────────
# Root Drive folder where brand subfolders will be created
DRIVE_ROOT_FOLDER_ID = "1IccJPTBcJ19aVwt5H0ZIUz2qWFi0mqEP"

# Path to OAuth 2.0 client secrets JSON (downloaded from GCP Console)
OAUTH_CLIENT_SECRETS = os.path.join(
    os.path.dirname(__file__), "..", "credentials", "client_secrets.json"
)

# Path where the OAuth token will be stored after first login
OAUTH_TOKEN_FILE = os.path.join(
    os.path.dirname(__file__), "..", "credentials", "token.json"
)

# Drive API scopes
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

# ─── Franchise Library ────────────────────────────────────────────────────────
# Path to the franchise_index.json from the franchise-library repo
FRANCHISE_INDEX_PATH = os.path.join(
    os.path.dirname(__file__), "..", "franchise_index.json"
)

# ─── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "manifest.json")
BRAND_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "brands")

# ─── Screenshot Settings ──────────────────────────────────────────────────────
SCREENSHOT_WIDTH = 1600
SCREENSHOT_HEIGHT = 900
SCREENSHOT_WAIT_MS = 3000  # ms to wait for images to load

# Image search queries per brand (use {brand} as placeholder)
IMAGE_SEARCH_QUERIES = [
    "{brand} franchise",
    "{brand} franchise marketing",
    "{brand} franchise interior",
]

IMAGE_SEARCH_FILENAMES = [
    "images_franchise.png",
    "images_marketing.png",
    "images_interior.png",
]

# ─── Logo Fetcher ─────────────────────────────────────────────────────────────
# Clearbit Logo API base URL (free, no key required)
CLEARBIT_LOGO_URL = "https://logo.clearbit.com/{domain}"
LOGO_SIZE = 512  # px (Clearbit supports up to 512)

# ─── Concurrency ─────────────────────────────────────────────────────────────
DEFAULT_CONCURRENCY = 3  # number of brands to process in parallel
RATE_LIMIT_DELAY = 2.0   # seconds between requests to the same domain
