"""
style_guide_generator.py – Automatically generate the Brand Visual Synthesis Guide
using GPT-4o Vision.

Attempts (in order):
  1. Logo + screenshots at detail="low"  (avoids content-filter on mixed images)
  2. Logo only  (if screenshots caused a refusal)
  3. Text only from PDFs  (if all images refused)

Output: brand_visual_synthesis_guide.md saved to the brand's output folder.
"""

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

STYLE_GUIDE_PROMPT = """You are a brand identity specialist.
Analyze the visual and design materials for a franchise brand and produce a structured \
"Brand Visual Synthesis Guide" that can be used to inform slide deck design.

Rules:
- Focus ONLY on visual elements: colors, typography, imagery, layout, logo style.
- If something is not visible, write "Not visible in materials provided."
- Be specific and actionable — a designer should be able to follow your output.
- Do NOT include business strategy, financials, or messaging.

Output this exact structure:

Brand Visual Synthesis Guide
Brand Name: {brand}

1. Color Palette
Primary Colors:
- [Color name] [#hex if visible] — [usage]

Secondary/Accent Colors:
- [Color name] [#hex if visible] — [usage]

Background/Neutral Colors:
- [Color name] [#hex if visible] — [usage]

2. Typography & Text Style
- Heading style:
- Body text style:
- Text hierarchy:
- Distinctive features:

3. Logo Usage & Variations
- Orientation:
- Style:
- Typical placement:
- Visible variations:

4. Visual Style & Design Language
Overall aesthetic (3-5 descriptors):
-
-
-

5. Imagery & Photography Style
- Subject matter:
- Photography style:
- Color treatment:
- Composition:

6. Layout & Composition Patterns
- Layout density:
- Alignment:
- Graphic elements:
- Visual rhythm:

7. Visual Tone & Personality
5-7 adjectives:
-
-
-
-
-

8. Slide Deck Design Recommendations
5-7 specific actionable recommendations:
1.
2.
3.
4.
5.

9. Visual Do's and Don'ts
DO:
-
-
-

DON'T:
-
-
-
"""

_REFUSAL_PHRASES = (
    "i'm sorry, but i can't",
    "i'm sorry, i can't",
    "i cannot assist",
    "i can't assist",
    "i'm not able to",
    "i cannot help",
    "i can't help",
    "sorry, but i can",
    "i'm unable to",
)


def _is_refusal(text: str) -> bool:
    return any(p in text.lower() for p in _REFUSAL_PHRASES)


def _image_to_base64(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.warning("Could not encode image %s: %s", path, e)
        return None


def _mime_for_image(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")


def _extract_pdf_text(pdf_path: Optional[str], max_chars: int = 4000) -> str:
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            if len(text) >= max_chars:
                break
        return text[:max_chars].strip()
    except ImportError:
        logger.debug("pypdf not installed — PDF text extraction skipped")
    except Exception as e:
        logger.warning("PDF text extraction failed for %s: %s", pdf_path, e)
    return ""


def _build_messages(prompt: str, image_paths: list, detail: str = "low") -> list:
    """Build a messages list for the OpenAI Chat API."""
    content = [{"type": "text", "text": prompt}]
    for img_path, label in image_paths:
        b64 = _image_to_base64(img_path)
        if b64:
            content.append({"type": "text", "text": f"[{label}]"})
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{_mime_for_image(img_path)};base64,{b64}",
                    "detail": detail,
                }
            })
    return [{"role": "user", "content": content}]


def _call_gpt(client, messages: list, brand: str) -> Optional[str]:
    """Make one API call; returns text or None on refusal/error."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=2000,
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()
        if _is_refusal(text):
            logger.warning("  GPT-4o refused for %s — will retry", brand)
            return None
        return text
    except Exception as e:
        logger.error("  GPT-4o call failed for %s: %s", brand, e)
        return None


def generate_style_guide(
    brand: str,
    slug: str,
    output_dir: str,
    logo_path: Optional[str],
    website_screenshot: Optional[str],   # brand homepage screenshot (safe, brand-controlled)
    onesheet_pdf: Optional[str],
    presentation_pdf: Optional[str],
    consumer_url: Optional[str],
    api_key: Optional[str] = None,
) -> Optional[str]:
    """
    Generate brand_visual_synthesis_guide.md using GPT-4o Vision.

    Visual inputs (brand-controlled, won't trigger content filters):
      - website_screenshot: brand homepage at detail="high" (colors, layout, fonts)
      - logo_path: brand logo at detail="low"

    Fallback chain:
      1. Website screenshot (high) + logo (low)
      2. Website screenshot only
      3. Logo only
      4. Text only (PDFs + URL)

    Returns the path to the saved file, or None on failure.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        logger.warning(
            "OPENAI_API_KEY not set — skipping style guide for %s. "
            "Set OPENAI_API_KEY in config/settings.py or environment.",
            brand,
        )
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai not installed. Run: pip install openai")
        return None

    client = OpenAI(api_key=key)

    # Build text prompt with context
    prompt = STYLE_GUIDE_PROMPT.replace("{brand}", brand)
    extras = []
    if consumer_url:
        extras.append(f"Website: {consumer_url}")
    txt = _extract_pdf_text(onesheet_pdf)
    if txt:
        extras.append(f"One Sheet excerpt:\n{txt}")
    txt = _extract_pdf_text(presentation_pdf)
    if txt:
        extras.append(f"Presentation Points excerpt:\n{txt}")
    if extras:
        prompt += "\n\nBrand context:\n" + "\n\n".join(extras)

    # Image tuples: (path, label, detail)
    site_imgs = []
    if website_screenshot and os.path.exists(website_screenshot):
        site_imgs.append((website_screenshot, "Brand website homepage", "high"))

    logo_imgs = []
    if logo_path and os.path.exists(logo_path):
        logo_imgs.append((logo_path, "Brand logo", "low"))

    logger.info("  Generating Brand Visual Synthesis Guide via GPT-4o for %s...", brand)

    def build_messages(img_list):
        content = [{"type": "text", "text": prompt}]
        for img_path, label, detail in img_list:
            b64 = _image_to_base64(img_path)
            if b64:
                content.append({"type": "text", "text": f"[{label}]"})
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{_mime_for_image(img_path)};base64,{b64}",
                        "detail": detail,
                    }
                })
        return [{"role": "user", "content": content}]

    # Attempt 1: website (high) + logo (low)
    guide = None
    all_imgs = site_imgs + logo_imgs
    if all_imgs:
        guide = _call_gpt(client, build_messages(all_imgs), brand)

    # Attempt 2: website only
    if guide is None and site_imgs and logo_imgs:
        logger.info("  Retry: website screenshot only for %s...", brand)
        guide = _call_gpt(client, build_messages(site_imgs), brand)

    # Attempt 3: logo only
    if guide is None and logo_imgs:
        logger.info("  Retry: logo only for %s...", brand)
        guide = _call_gpt(client, build_messages(logo_imgs), brand)

    # Attempt 4: text only
    if guide is None:
        logger.info("  Retry: text-only for %s...", brand)
        text_msg = [{"role": "user", "content": prompt + "\n\n(Visual assets unavailable — base analysis on text context only.)"}]
        guide = _call_gpt(client, text_msg, brand)

    if not guide:
        logger.error("  All GPT-4o attempts failed for %s", brand)
        return None

    dest = os.path.join(output_dir, "brand_visual_synthesis_guide.md")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(guide)
    logger.info("  Brand Visual Synthesis Guide saved: %s", dest)
    return dest

