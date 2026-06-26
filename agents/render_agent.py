# agents/render_agent.py
# Takes structured output from content_agent + vision_agent,
# merges everything into render_data, and drives core/renderer.py.

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config_loader import load_config, resolve_assets, image_to_b64
from core.renderer import render_slide, render_carousel, VARIANT_DIMENSIONS


# ── Image assignment ──────────────────────────────────────────────────────────

def resolve_photo_indexes(filled_fields: dict, best_paths: list[str]) -> dict:
    """
    Walk filled_fields and replace "PHOTO_INDEX:N" strings with the actual
    filesystem path at best_paths[N]. Falls back to best_paths[0] if index
    is out of range. Also handles legacy "AUTO" strings (assigns sequentially).
    """
    sequential_cursor = [0]

    def _resolve(obj):
        if isinstance(obj, dict):
            return {k: _resolve(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_resolve(item) for item in obj]
        elif isinstance(obj, str):
            if obj.startswith("PHOTO_INDEX:"):
                try:
                    idx = int(obj.split(":")[1])
                    idx = max(0, min(idx, len(best_paths) - 1))  # clamp to valid range
                    return best_paths[idx] if best_paths else ""
                except (IndexError, ValueError):
                    return best_paths[0] if best_paths else ""
            elif obj == "AUTO":
                # Legacy fallback — sequential assignment
                if sequential_cursor[0] < len(best_paths):
                    path = best_paths[sequential_cursor[0]]
                    sequential_cursor[0] += 1
                    return path
                return best_paths[0] if best_paths else ""
        return obj

    return _resolve(filled_fields)


def resolve_image_fields(filled_fields: dict) -> dict:
    """
    Walk filled_fields and convert any image path strings → base64 data URIs.
    Keys ending in _path or _image that contain file paths get converted to _b64.
    """
    def _process(obj, parent_key=""):
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                processed = _process(v, k)
                result[k] = processed
                # If this looks like an image path field and value is a real path, add b64 sibling
                if (k.endswith("_path") or k.endswith("_image")) and isinstance(v, str) and v:
                    b64_key = k.replace("_path", "_b64").replace("_image", "_b64")
                    try:
                        result[b64_key] = image_to_b64(v)
                    except FileNotFoundError:
                        result[b64_key] = ""
            return result
        elif isinstance(obj, list):
            return [_process(item) for item in obj]
        return obj

    return _process(filled_fields)


# ── Render data builder ───────────────────────────────────────────────────────

def build_render_data(school_config: dict, filled_fields: dict, layout_params: dict = None) -> dict:
    """
    Merge school config + resolved assets + filled fields into one flat dict
    for Jinja2 template rendering.
    """
    resolved_assets = resolve_assets(school_config)

    base = {
        # School identity
        "school_name":  school_config["school_name"],
        "city":         school_config["city"],
        "tagline":      school_config["tagline"],
        # Design tokens
        "colors":       school_config["colors"],
        "fonts":        school_config["fonts"],
        # Resolved asset base64 strings
        **resolved_assets,
    }

    # Merge layout params if present (multiple_achievement grid sizing)
    if layout_params:
        base.update(layout_params)

    # Merge AI-filled fields (these override base if keys clash)
    base.update(filled_fields)

    return base


# ── Output folder management ──────────────────────────────────────────────────

def make_output_dir(base_output: str, job_id: str, event_type: str) -> str:
    """Create organised output directory: output/<school_id>/<job_id>__<event_slug>/"""
    slug = event_type.lower().replace(" ", "_").replace("/", "_")[:40]
    folder = Path(base_output) / f"{job_id}__{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


# ── Main render agent ─────────────────────────────────────────────────────────

def run_render_agent(
    school_config:   dict,
    content_result:  dict,
    vision_result:   dict,
    job_id:          str,
    base_output_dir: str = "output",
    design_set:      str = "glassmorphism",
) -> dict:
    """
    Full render agent run:
      1. Assign real images to AUTO placeholders
      2. Resolve image paths → base64
      3. Build render_data
      4. Render each variant (flat or carousel)
      5. Save caption.txt alongside renders
      6. Return summary of all output files

    Returns:
      {
        "job_id":       str,
        "output_dir":   str,
        "rendered":     { variant: [list of png paths] },
        "caption":      str,
        "hashtags":     list[str],
      }
    """
    template_id   = content_result["template_id"]
    variants      = content_result["variants"]
    filled_fields = content_result["filled_fields"]
    layout_params = content_result.get("layout_params", {})
    caption       = content_result["caption"]
    hashtags      = content_result["hashtags"]
    best_paths    = vision_result.get("best_paths", [])
    event_type    = vision_result.get("event_context", {}).get("event_type", "event")

    # Step 1 — resolve PHOTO_INDEX:N tokens to real paths
    filled_fields = resolve_photo_indexes(filled_fields, best_paths)

    # Step 2 — convert image paths → base64
    filled_fields = resolve_image_fields(filled_fields)

    # Step 3 — build render data
    render_data = build_render_data(school_config, filled_fields, layout_params)

    # Step 4 — determine if this is a carousel template
    from core.registry_loader import load_schema
    schema      = load_schema(template_id)
    is_carousel = schema.get("is_carousel", False)

    # Step 5 — create output directory
    output_dir = make_output_dir(base_output_dir, job_id, event_type)
    print(f"[render_agent] Output dir: {output_dir}")

    rendered = {}

    for variant in variants:
        if variant not in VARIANT_DIMENSIONS:
            print(f"[render_agent] Unknown variant '{variant}', skipping.")
            continue

        variant_dir = Path(output_dir) / variant
        variant_dir.mkdir(exist_ok=True)

        if is_carousel and "slides" in render_data:
            slides_data = render_data.get("slides", [])
            total = len(slides_data) + 2  # cover + inner + closing

            # ── Cover slide ───────────────────────────────────────────────────
            cover_image_b64 = render_data.get("cover_image_b64", "")
            if not cover_image_b64 and best_paths:
                best_cover_index = vision_result.get("event_context", {}).get("best_cover_index", 0)
                best_cover_index = max(0, min(best_cover_index, len(best_paths) - 1))
                try:
                    cover_image_b64 = image_to_b64(best_paths[best_cover_index])
                except Exception:
                    cover_image_b64 = ""

            cover_data = {
                **render_data,
                "cover_image_b64": cover_image_b64,
                "slide_number":    1,
                "total_slides":    total,
            }
            cover_path = str(variant_dir / "slide_01_cover.png")
            render_slide(template_id, variant, cover_data, cover_path, design_set)
            all_slide_renders = [cover_path]

            # ── Inner slides ──────────────────────────────────────────────────
            carousel_variant = "instagram_carousel" if variant == "instagram_square" else variant
            for i, slide in enumerate(slides_data):
                slide_render_data = {
                    **render_data,
                    **slide,
                    "slide_number": i + 2,
                    "total_slides": total,
                }
                img_path = slide.get("image_path", "")
                if img_path and not slide.get("image_b64"):
                    try:
                        slide_render_data["image_b64"] = image_to_b64(img_path)
                    except Exception:
                        slide_render_data["image_b64"] = slide.get("image_b64", "")

                slide_path = str(variant_dir / f"slide_{i+2:02d}.png")
                try:
                    render_slide(template_id, carousel_variant, slide_render_data, slide_path, design_set)
                except FileNotFoundError:
                    render_slide(template_id, variant, slide_render_data, slide_path, design_set)
                all_slide_renders.append(slide_path)

            # ── Closing slide ─────────────────────────────────────────────────
            closing_image_b64 = ""
            if best_paths:
                try:
                    closing_image_b64 = image_to_b64(best_paths[-1])
                except Exception:
                    closing_image_b64 = cover_image_b64

            closing_data = {
                **render_data,
                "cover_image_b64": closing_image_b64,
                "cover_headline":  render_data.get("closing_message", "Thank you."),
                "event_name":      render_data.get("event_name", ""),
                "event_date_str":  "",
                "slide_number":    total,
                "total_slides":    total,
                "is_closing":      True,
            }
            closing_path = str(variant_dir / f"slide_{total:02d}_closing.png")
            render_slide(template_id, variant, closing_data, closing_path, design_set)
            all_slide_renders.append(closing_path)

            rendered[variant] = all_slide_renders

        else:
            # Single image
            out_path = str(variant_dir / "post.png")
            render_slide(template_id, variant, render_data, out_path, design_set)
            rendered[variant] = [out_path]

    # Step 6 — save caption + hashtags
    hashtag_str  = " ".join(hashtags)
    caption_text = f"{caption}\n\n{hashtag_str}"
    caption_path = Path(output_dir) / "caption.txt"
    caption_path.write_text(caption_text, encoding="utf-8")
    print(f"[render_agent] ✓ caption.txt saved")

    print(f"\n[render_agent] ── Job complete: {job_id} ──")
    for variant, paths in rendered.items():
        print(f"  {variant}: {len(paths)} file(s)")

    return {
        "job_id":     job_id,
        "output_dir": output_dir,
        "rendered":   rendered,
        "caption":    caption,
        "hashtags":   hashtags,
    }