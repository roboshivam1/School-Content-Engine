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

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"}

# Quality thresholds — intentionally lenient for school event photos
# (phone cameras, indoor lighting, motion blur are all common)
BLUR_THRESHOLD       = 30    # Laplacian variance — below this is genuinely unusable
BRIGHTNESS_MIN       = 20    # below this = almost black
BRIGHTNESS_MAX       = 245   # above this = almost white / blown out


# ── Path resolution ────────────────────────────────────────────────────────────

def resolve_media_dir(media_dir: str) -> Path:
    """
    Resolve the media_dir path robustly.
    Tries: as-is → relative to CWD → relative to this file's project root.
    Prints the resolved absolute path so the user can see exactly what's being scanned.
    """
    path = Path(media_dir)

    # Try as-is (absolute, or relative to CWD)
    if path.exists():
        resolved = path.resolve()
        print(f"[vision_agent] Media dir: {resolved}")
        return resolved

    # Try relative to project root (jarvis-content-agent/)
    project_root = Path(__file__).parent.parent
    alt = (project_root / media_dir).resolve()
    if alt.exists():
        print(f"[vision_agent] Media dir: {alt}")
        return alt

    # Neither worked — give a clear error showing both paths tried
    raise FileNotFoundError(
        f"\n[vision_agent] Could not find media folder.\n"
        f"  Tried (relative to CWD):          {path.resolve()}\n"
        f"  Tried (relative to project root): {alt}\n"
        f"  Check the 'media_dir' value in your job.json."
    )


# ── Image scoring ──────────────────────────────────────────────────────────────

def score_image(path: str) -> dict:
    """
    Returns a quality dict for a single image.
    blur_score: higher = sharper (Laplacian variance)
    brightness: 0-255 mean pixel value
    usable: True if image passes minimum thresholds
    """
    if not CV2_AVAILABLE:
        return {"path": path, "blur_score": 999, "brightness": 128, "usable": True}

    img = cv2.imread(path)
    if img is None:
        return {"path": path, "blur_score": 0, "brightness": 0, "usable": False, "reason": "could not read file"}

    gray        = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_score  = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness  = float(gray.mean())

    reason = None
    if blur_score <= BLUR_THRESHOLD:
        reason = f"too blurry (score {blur_score:.0f} < {BLUR_THRESHOLD})"
    elif brightness <= BRIGHTNESS_MIN:
        reason = f"too dark (brightness {brightness:.0f})"
    elif brightness >= BRIGHTNESS_MAX:
        reason = f"too bright/blown out (brightness {brightness:.0f})"

    return {
        "path":        path,
        "blur_score":  round(blur_score, 1),
        "brightness":  round(brightness, 1),
        "usable":      reason is None,
        "reason":      reason,
    }


def scan_and_rank(media_dir: str, max_images: int = 12) -> list[dict]:
    """
    Scan a folder (and one level of subfolders) for images, score and rank them.
    Returns list of scored dicts sorted best-first, capped at max_images.
    """
    media_path = resolve_media_dir(media_dir)

    # Collect images — top-level + one subfolder level deep
    candidates = []
    for f in media_path.rglob("*"):
        if f.suffix.lower() in {e.lower() for e in SUPPORTED_EXTENSIONS}:
            candidates.append(str(f))

    print(f"[vision_agent] Found {len(candidates)} image file(s) in folder")

    if not candidates:
        print(f"[vision_agent] No images found. Supported formats: jpg, jpeg, png, webp")
        print(f"[vision_agent] Files in folder:")
        for f in media_path.iterdir():
            print(f"  {f.name}")
        return []

    scores = [score_image(p) for p in candidates]
    usable   = [s for s in scores if s["usable"]]
    rejected = [s for s in scores if not s["usable"]]

    # Report rejected images so user knows what was filtered
    if rejected:
        print(f"[vision_agent] {len(rejected)} image(s) filtered out:")
        for r in rejected:
            reason = r.get("reason", "unknown")
            print(f"  ✗  {Path(r['path']).name}  —  {reason}")

    # Safety net: if quality filter wiped everything out, use all images anyway
    # Better to send imperfect photos to Claude than to produce nothing
    if not usable and candidates:
        print(f"[vision_agent] All images failed quality check — using all anyway (letting Claude decide)")
        usable = scores

    print(f"[vision_agent] {len(usable)} image(s) passed quality check")

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
    Sends up to 8 best images to Claude Vision.
    Returns event context AND per-image descriptions so the content agent
    can semantically match captions to the correct photos.
    """
    if client is None:
        client = anthropic.Anthropic()

    # Send up to 8 images — more coverage means better caption↔photo matching
    sample_paths = image_paths[:8]

    # Build content blocks — each image is labelled with its index
    content = []
    for i, path in enumerate(sample_paths):
        b64, mime = _encode_image(path)
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": b64}
        })
        # Label injected as text immediately after each image
        content.append({
            "type": "text",
            "text": f"[Image index {i} above]"
        })

    content.append({
        "type": "text",
        "text": f"""You are analyzing raw school event photos for {school_name}.

Operator job description:
\"\"\"{job_description}\"\"\"

I have sent you {len(sample_paths)} images, each labelled with its index (0 to {len(sample_paths)-1}).

Return ONLY a JSON object — no preamble, no markdown fences — with this exact structure:

{{
  "event_type": "brief event category e.g. Annual Sports Day / Pool Party / Science Fair",
  "event_summary": "2-3 sentence factual summary of what happened",
  "mood": "celebratory / formal / fun / solemn",
  "sub_events": ["distinct moment 1", "distinct moment 2"],
  "suggested_cover_headline": "punchy 3-6 word headline, can use \\n for line breaks",
  "suggested_caption": "full Instagram caption, 2-4 sentences, warm and proud tone",
  "suggested_hashtags": ["#relevant", "#hashtags", "5-8 total"],
  "best_cover_index": 0,
  "image_descriptions": [
    {{"index": 0, "description": "one sentence: what is visually happening in this specific photo"}},
    {{"index": 1, "description": "one sentence: what is visually happening in this specific photo"}}
  ]
}}

Rules:
- image_descriptions must have one entry per image sent, in order.
- best_cover_index is the index of the single most visually striking photo for a carousel cover.
- descriptions must be specific and visual — mention props, expressions, activities, decorations."""
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": content}]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(raw)
        # Ensure image_descriptions is always present
        if "image_descriptions" not in result:
            result["image_descriptions"] = [
                {"index": i, "description": f"Photo {i} from the event"}
                for i in range(len(sample_paths))
            ]
        if "best_cover_index" not in result:
            result["best_cover_index"] = 0
        return result
    except json.JSONDecodeError:
        return {
            "event_type":               "School Event",
            "event_summary":            job_description,
            "mood":                     "celebratory",
            "sub_events":               [],
            "suggested_cover_headline": "A Day to Remember.",
            "suggested_caption":        job_description,
            "suggested_hashtags":       ["#SchoolLife", "#ProudMoment"],
            "best_cover_index":         0,
            "image_descriptions":       [
                {"index": i, "description": f"Photo {i} from the event"}
                for i in range(len(sample_paths))
            ],
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
    ranked = scan_and_rank(media_dir, max_images)

    if not ranked:
        print("[vision_agent] Proceeding with no images — caption/template will be text-only.")
        return {
            "ranked_images": [],
            "best_paths":    [],
            "event_context": {
                "event_type":               "School Event",
                "event_summary":            job_description,
                "mood":                     "celebratory",
                "sub_events":               [],
                "suggested_cover_headline": "A Memorable Day.",
                "suggested_caption":        job_description,
                "suggested_hashtags":       ["#SchoolLife"],
                "image_quality_notes":      "No images found.",
            }
        }

    best_paths = [r["path"] for r in ranked]
    print(f"[vision_agent] Sending top {min(4, len(ranked))} image(s) to Claude Vision...")

    event_context = understand_event(best_paths, job_description, school_name, client)
    print(f"[vision_agent] Event identified: {event_context.get('event_type', 'Unknown')}")

    return {
        "ranked_images": ranked,
        "best_paths":    best_paths,
        "event_context": event_context,
    }