"""
style_guide_generator.py – Automatically generate the Brand Visual Synthesis Guide
using GPT-4o Vision.

Assets sent to GPT-4o:
  - Brand logo (image)
  - 3 Google Images screenshots (images)
  - OneSheet PDF text (extracted, as context)
  - PresentationPoints PDF text (extracted, as context)
  - Consumer URL (mentioned in prompt)

Output: brand_visual_synthesis_guide.md saved to the brand's output folder.
"""

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# The visual analysis prompt (without the "I will now provide materials" tail —
# that's replaced by the actual attached content)
STYLE_GUIDE_PROMPT = """You are a brand identity specialist.
You will be provided with materials for a franchise brand: a logo image, Google Images screenshots showing the brand in franchise, marketing, and interior contexts, and text excerpts from brand marketing documents.

Your task is to analyze ONLY the visual and design elements and produce a clean "Brand Visual Synthesis Guide" that can be uploaded into another AI tool (NotebookLM) to inform presentation slide design.

Follow these rules:
- Work only with the visual information provided (colors, typography, layout style, imagery, tone).
- If something is not visible or unclear, write "Not visible in materials provided."
- Use specific, descriptive language that a designer or AI tool could follow.
- Do NOT include any business strategy, financials, or messaging — focus purely on visual identity.

Output format (use this exact structure):

Brand Visual Synthesis Guide
Brand Name: {brand}

1. Color Palette
List all colors identifiable from the logo, marketing materials, and imagery.
For each color: describe it in words, include hex code if visible, note usage.

Primary Colors:
[Color description] [#HexCode if visible] – [Usage]

Secondary/Accent Colors:
[Color description] [#HexCode if visible] – [Usage]

Background/Neutral Colors:
[Color description] [#HexCode if visible] – [Usage]

2. Typography & Text Style
- Heading style
- Body text style
- Text hierarchy approach
- Distinctive typography features

3. Logo Usage & Variations
- Logo orientation
- Logo style
- Typical placement
- Visible variations

4. Visual Style & Design Language
Describe the overall design aesthetic in 3–5 descriptive phrases.

Overall aesthetic:
[Descriptor 1]
[Descriptor 2]
[Descriptor 3]

5. Imagery & Photography Style
- Subject matter
- Photography style
- Color treatment in photos
- Composition style

6. Layout & Composition Patterns
- Layout density
- Alignment preferences
- Use of shapes, borders, or graphic elements
- Visual rhythm

7. Tone & Personality (Visual)
Choose 5–7 adjectives that capture the visual impression.

Visual personality:
[Adjective 1]
[Adjective 2]
[Adjective 3]
[Adjective 4]
[Adjective 5]

8. Design Recommendations for Presentation Slides
Provide 5–7 specific actionable recommendations for designing a slide deck for this brand.

9. Visual "Do's and Don'ts"
DO:
[Specific visual practice that fits the brand]
[Specific visual practice that fits the brand]
[Specific visual practice that fits the brand]

DON'T:
[Visual practice that would clash with brand identity]
[Visual practice that would clash with brand identity]
[Visual practice that would clash with brand identity]

End of output format.
"""


def _image_to_base64(path: str) -> Optional[str]:
    """Convert an image file to base64 string."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.warning("Could not encode image %s: %s", path, e)
        return None


def _extract_pdf_text(pdf_path: str, max_chars: int = 4000) -> str:
    """Extract text from a PDF file. Returns empty string if unavailable."""
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


def _mime_for_image(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp"}.get(ext.lstrip("."), "image/png")


def generate_style_guide(
    brand: str,
    slug: str,
    output_dir: str,
    logo_path: Optional[str],
    screenshot_paths: list,
    onesheet_pdf: Optional[str],
    presentation_pdf: Optional[str],
    consumer_url: Optional[str],
    api_key: Optional[str] = None,
) -> Optional[str]:
    """
    Generate brand_visual_synthesis_guide.md using GPT-4o Vision.

    Returns the path to the generated file, or None on failure.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        logger.warning(
            "OPENAI_API_KEY not set — skipping style guide generation for %s. "
            "Set it in config/settings.py or export OPENAI_API_KEY=sk-...",
            brand,
        )
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed. Run: pip install openai")
        return None

    client = OpenAI(api_key=key)

    # Build the message content list
    content = []

    # System prompt with brand name substituted
    prompt_text = STYLE_GUIDE_PROMPT.replace("{brand}", brand)

    # Add context from PDFs and URL
    context_parts = []
    if consumer_url:
        context_parts.append(f"Consumer-facing website: {consumer_url}")

    onesheet_text = _extract_pdf_text(onesheet_pdf)
    if onesheet_text:
        context_parts.append(f"--- One Sheet (text excerpt) ---\n{onesheet_text}")

    presentation_text = _extract_pdf_text(presentation_pdf)
    if presentation_text:
        context_parts.append(f"--- Presentation Points (text excerpt) ---\n{presentation_text}")

    full_prompt = prompt_text
    if context_parts:
        full_prompt += "\n\nBrand context from documents:\n" + "\n\n".join(context_parts)

    content.append({"type": "text", "text": full_prompt})

    # Add images: logo first, then screenshots
    image_paths = []
    if logo_path and os.path.exists(logo_path):
        image_paths.append((logo_path, "Brand logo"))
    for i, path in enumerate(screenshot_paths or []):
        if path and os.path.exists(path):
            labels = ["Google Images: franchise search", "Google Images: marketing search", "Google Images: interior search"]
            label = labels[i] if i < len(labels) else f"Screenshot {i+1}"
            image_paths.append((path, label))

    for img_path, label in image_paths:
        b64 = _image_to_base64(img_path)
        if b64:
            content.append({
                "type": "text",
                "text": f"[{label}]"
            })
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{_mime_for_image(img_path)};base64,{b64}",
                    "detail": "high",
                }
            })

    if len(image_paths) == 0:
        logger.warning("No images available for style guide generation for %s", brand)

    logger.info("  Generating Brand Visual Synthesis Guide via GPT-4o for %s...", brand)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=2000,
            temperature=0.3,
        )
        guide_text = response.choices[0].message.content.strip()

        dest = os.path.join(output_dir, "brand_visual_synthesis_guide.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(guide_text)

        logger.info("  Brand Visual Synthesis Guide saved: %s", dest)
        return dest

    except Exception as e:
        logger.error("GPT-4o style guide generation failed for %s: %s", brand, e)
        return None
