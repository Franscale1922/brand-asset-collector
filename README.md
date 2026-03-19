# Brand Asset Collector

Automated pipeline that collects a standard set of brand assets for every franchise brand in the [franchise-library](https://github.com/Franscale1922/franchise-library) and deposits them into brand-specific Google Drive folders.

---

## Assets Collected Per Brand

| Asset | Filename | Method |
|-------|----------|--------|
| Consumer-facing URL | `urls.md` | DuckDuckGo / web search |
| Franchise offering URL | `urls.md` | Web scrape + search |
| Brand logo | `{slug}_logo.png` | Clearbit API → OG image fallback |
| Google Images: franchise | `images_franchise.png` | Playwright screenshot |
| Google Images: marketing | `images_marketing.png` | Playwright screenshot |
| Google Images: interior | `images_interior.png` | Playwright screenshot |
| Design & style guide | `design_style_guide.md` | Prompt template (see `prompts/`) |
| NotebookLM generic prompt | `notebooklm_generic.md` | Prompt template (see `prompts/`) |
| NotebookLM personalized prompt | `notebooklm_personalized.md` | Prompt template (see `prompts/`) |

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/Franscale1922/brand-asset-collector.git
cd brand-asset-collector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Add the franchise_index.json

```bash
cp ~/Projects/franchise-library/_metadata/franchise_index.json ./franchise_index.json
```

Or use a symlink to keep it in sync:
```bash
ln -s ~/Projects/franchise-library/_metadata/franchise_index.json ./franchise_index.json
```

### 3. Set up Google Drive API credentials

1. Go to [GCP Console](https://console.cloud.google.com/) → **APIs & Services** → **Enable APIs**
   - Enable: **Google Drive API**
2. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
   - Application type: **Desktop app**
3. Download the JSON → save as `credentials/client_secrets.json`
4. On first run, a browser window will open for you to authorize access.
   The token is saved to `credentials/token.json` automatically.

### 4. Verify config

Edit `config/settings.py` if needed:
- `DRIVE_ROOT_FOLDER_ID` — the root Drive folder where brand subfolders are created
- `DEFAULT_CONCURRENCY` — parallel workers (default: 3)

---

## Usage

### Run all brands
```bash
python scripts/collect_assets.py --all
```

### Resume (skip already completed)
```bash
python scripts/collect_assets.py --all --resume
```

### Run a single brand
```bash
python scripts/collect_assets.py --brand 1-800-Packouts
```

### Run select brands
```bash
python scripts/collect_assets.py --brands 1-800-Packouts 360-Painting Bath-Tune-Up
```

### Dry run (no files written or uploaded)
```bash
python scripts/collect_assets.py --all --dry-run
```

### Collect locally, skip Drive upload
```bash
python scripts/collect_assets.py --all --no-upload
```

### Refresh prompt placeholders (after updating templates in `prompts/`)
```bash
python scripts/collect_assets.py --all --refresh-prompts
```

### Set concurrency
```bash
python scripts/collect_assets.py --all --concurrency 5
```

---

## Prompt Templates

Three prompt template files live in `prompts/`:
- `design_style_guide.md.tmpl`
- `notebooklm_generic.md.tmpl`
- `notebooklm_personalized.md.tmpl`

Edit these files with the actual prompt content when ready, then run:
```bash
python scripts/collect_assets.py --all --refresh-prompts
```
to regenerate all brand `.md` files from the updated templates.

---

## Output

Local brand files are written to `output/brands/{slug}/`.

The manifest at `output/manifest.json` tracks completion status:
```json
{
  "1-800-Packouts": {
    "status": "complete",
    "completed_at": "2026-03-19T...",
    "assets": { ... },
    "drive_folder_id": "..."
  }
}
```

---

## Drive Folder Structure

```
[Root Drive Folder]
├── 1-800-Packouts/
│   ├── urls.md
│   ├── 1-800-Packouts_logo.png
│   ├── images_franchise.png
│   ├── images_marketing.png
│   ├── images_interior.png
│   ├── design_style_guide.md
│   ├── notebooklm_generic.md
│   └── notebooklm_personalized.md
├── 360-Painting/
│   └── ...
└── ...
```

---

## Adding a New Brand

New brands should be added to the franchise-library repo. Once `franchise_index.json` is updated, run:
```bash
python scripts/collect_assets.py --brand <new-slug>
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `FileNotFoundError: client_secrets.json` | Follow Step 3 in Setup |
| Logo is wrong/missing | Clearbit doesn't have it — check `output/brands/{slug}/` and add manually |
| Screenshot is blank | Google may have shown a CAPTCHA — try running with a longer `--wait-ms` or manually |
| Drive folder not found | Check `DRIVE_ROOT_FOLDER_ID` in `config/settings.py` |
