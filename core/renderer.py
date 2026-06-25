# core/renderer.py
# Pure render function — no AI, no business logic.
# Takes a template path + data dict → produces a PNG via Jinja2 + Playwright.

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, BaseLoader
from playwright.sync_api import sync_playwright
import os

BASE_DIR = Path(__file__).parent.parent

# Viewport sizes per variant
VARIANT_DIMENSIONS = {
    "instagram_square":   (1080, 1080),
    "instagram_carousel": (1080, 1080),
    "instagram_story":    (1080, 1920),
    "whatsapp_status":    (1080, 1920),
}


def render_slide(template_id: str, variant: str, render_data: dict, output_path: str) -> str:
    """
    Render one slide.
      template_id  — e.g. "event_recap"
      variant      — e.g. "instagram_square"
      render_data  — merged dict from school config + AI filled fields + resolved b64 assets
      output_path  — where the PNG is saved

    Returns the output_path on success.
    """
    template_path = BASE_DIR / "templates" / template_id / f"{variant}.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    width, height = VARIANT_DIMENSIONS.get(variant, (1080, 1080))

    # --- Jinja2 render ---
    env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    template = env.get_template(f"{variant}.html")
    html = template.render(**render_data)

    # --- Playwright screenshot ---
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=output_path, type="png", clip={"x": 0, "y": 0, "width": width, "height": height})
        browser.close()

    print(f"[renderer] ✓ {output_path}")
    return output_path


def render_carousel(template_id: str, variant: str, slides_data: list[dict], output_dir: str) -> list[str]:
    """
    Render multiple slides for a carousel.
    slides_data — list of render_data dicts, one per slide.
    Returns list of output paths.
    """
    paths = []
    for i, render_data in enumerate(slides_data):
        slide_num = i + 1
        out = str(Path(output_dir) / f"slide_{slide_num:02d}.png")
        render_slide(template_id, variant, render_data, out)
        paths.append(out)
    return paths