# agents/vision_agent.py
# Scans a raw media folder, scores image quality, selects best images,
# then sends the top picks to Claude Vision for event understanding.

import os
import base64
import json
from pathlib import Path
from typing import Optional
import anthropic

# OpenCV imported lazily — not everyone will have it, degrade gracefully
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


# ── Image scoring ──────────────────────────────────────────────────────────────

def score_image(path: str) -> dict:
    """
    Returns a quality dict for a single image.
    blur_score: higher = sharper (Laplacian variance)
    brightness: 0-255 mean pixel value
    usable: True if image passes minimum thresholds
    """
    if not CV2_AVAILABLE:
        # No OpenCV — accept everything, let AI decide
        return {"path": path, "blur_score": 999, "brightness": 128, "usable": True}

    img = cv2.imread(path)
    if img is None:
        return {"path": path, "blur_score": 0, "brightness": 0, "usable": False}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_score  = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness  = float(gray.mean())

    usable = blur_score > 80 and 40 < brightness < 230
    return {
        "path":        path,
        "blur_score":  round(blur_score, 1),
        "brightness":  round(brightness, 1),
        "usable":      usable,
    }


def scan_and_rank(media_dir: str, max_images: int = 12) -> list[dict]:
    """
    Scan a folder for images, score and rank them.
    Returns list of scored dicts sorted best-first, capped at max_images.
    """
    media_dir = Path(media_dir)
    if not media_dir.exists():
        raise FileNotFoundError(f"Media folder not found: {media_dir}")

    candidates = [
        str(f) for f in media_dir.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not candidates:
        return []

    scores = [score_image(p) for p in candidates]
    usable = [s for s in scores if s["usable"]]
    # Sort by blur_score descending (sharpest first)
    ranked = sorted(usable, key=lambda x: x["blur_score"], reverse=True)
    return ranked[:max_images]


# ── Event understanding via Claude Vision ─────────────────────────────────────

def _encode_image(path: str) -> tuple[str, str]:
    """Returns (base64_data, media_type) for an image file."""
    ext = Path(path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png",  ".webp": "image/webp"}
    mime = mime_map.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8"), mime


def understand_event(
    image_paths: list[str],
    job_description: str,
    school_name: str,
    client: Optional[anthropic.Anthropic] = None,
) -> dict:
    """
    Sends up to 4 best images to Claude Vision with the job description.
    Returns structured event context dict.
    """
    if client is None:
        client = anthropic.Anthropic()

    # Cap at 4 images — enough for understanding, keeps tokens low
    sample_paths = image_paths[:4]

    # Build content blocks
    content = []
    for path in sample_paths:
        b64, mime = _encode_image(path)
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": b64}
        })

    content.append({
        "type": "text",
        "text": f"""You are analyzing raw photos from a school event for {school_name}.

Job description from the operator:
\"\"\"{job_description}\"\"\"

Look at the photos and return ONLY a JSON object — no preamble, no markdown — with this structure:

{{
  "event_type": "brief event category, e.g. Annual Sports Day / Science Fair / Prize Distribution",
  "event_summary": "2-3 sentence factual summary of what happened",
  "mood": "celebratory / formal / fun / solemn",
  "sub_events": ["list", "of", "distinct", "moments", "visible", "in", "photos"],
  "suggested_cover_headline": "punchy 3-7 word headline for the main post, can use newlines",
  "suggested_caption": "full Instagram caption, 2-4 sentences, warm and proud tone",
  "suggested_hashtags": ["#relevant", "#hashtags", "up to 8"],
  "image_quality_notes": "brief note on which photos look best for the cover"
}}"""
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": content}]
    )

    raw = response.content[0].text.strip()
    # Strip accidental markdown fences
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback — return minimal structure so pipeline doesn't crash
        return {
            "event_type":              "School Event",
            "event_summary":           job_description,
            "mood":                    "celebratory",
            "sub_events":              [],
            "suggested_cover_headline": "A Day to Remember.",
            "suggested_caption":       job_description,
            "suggested_hashtags":      ["#SchoolLife", "#ProudMoment"],
            "image_quality_notes":     "Could not auto-analyse. Review manually.",
        }


# ── Main entry point ──────────────────────────────────────────────────────────

def run_vision_agent(
    media_dir: str,
    job_description: str,
    school_name: str,
    max_images: int = 12,
    client: Optional[anthropic.Anthropic] = None,
) -> dict:
    """
    Full vision agent run:
      1. Scan + rank images in media_dir
      2. Send best picks to Claude Vision for event understanding
      3. Return combined result

    Returns:
      {
        "ranked_images": [...scored image dicts...],
        "best_paths":    [...paths of usable images...],
        "event_context": {...event understanding from Claude...}
      }
    """
    print(f"[vision_agent] Scanning: {media_dir}")
    ranked = scan_and_rank(media_dir, max_images)

    if not ranked:
        print("[vision_agent] No usable images found.")
        return {
            "ranked_images": [],
            "best_paths":    [],
            "event_context": {
                "event_type": "School Event",
                "event_summary": job_description,
                "mood": "celebratory",
                "sub_events": [],
                "suggested_cover_headline": "A Memorable Day.",
                "suggested_caption": job_description,
                "suggested_hashtags": ["#SchoolLife"],
                "image_quality_notes": "No images provided.",
            }
        }

    best_paths = [r["path"] for r in ranked]
    print(f"[vision_agent] {len(ranked)} usable images found, sending top {min(4, len(ranked))} to Claude Vision")

    event_context = understand_event(best_paths, job_description, school_name, client)
    print(f"[vision_agent] Event identified: {event_context.get('event_type', 'Unknown')}")

    return {
        "ranked_images": ranked,
        "best_paths":    best_paths,
        "event_context": event_context,
    }