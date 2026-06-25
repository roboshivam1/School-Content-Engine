# core/config_loader.py
# Loads a school config dict by school_id.
# Resolves asset paths to base64 strings so templates never touch the filesystem.

import importlib.util
import base64
import os
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent


def load_config(school_id: str) -> dict:
    """Load school config from configs/<school_id>.py"""
    config_path = BASE_DIR / "configs" / f"{school_id}.py"
    if not config_path.exists():
        raise FileNotFoundError(f"No config found for school_id '{school_id}' at {config_path}")

    spec = importlib.util.spec_from_file_location("school_config", config_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SCHOOL_CONFIG


def resolve_assets(config: dict) -> dict:
    """
    Walk the config's assets dict and convert every image path to base64.
    Returns a new dict with keys like logo_b64, watermark_b64 etc.
    Original path keys are preserved alongside.
    """
    resolved = {}
    assets = config.get("assets", {})

    for key, path in assets.items():
        full_path = BASE_DIR / path
        if full_path.exists():
            with open(full_path, "rb") as f:
                ext = full_path.suffix.lower().lstrip(".")
                mime = "png" if ext == "png" else "jpeg"
                b64 = base64.b64encode(f.read()).decode("utf-8")
                # e.g. logo_path → logo_b64
                b64_key = key.replace("_path", "_b64")
                resolved[b64_key] = f"data:image/{mime};base64,{b64}"
                resolved[key] = str(full_path)  # keep original path too
        else:
            # Asset file missing — warn but don't crash, template will handle gracefully
            print(f"[config_loader] WARNING: Asset not found: {full_path}")
            b64_key = key.replace("_path", "_b64")
            resolved[b64_key] = ""
            resolved[key] = ""

    return resolved


def image_to_b64(image_path: str) -> str:
    """Convert any image path to a base64 data URI. Used for event photos."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    ext = path.suffix.lower().lstrip(".")
    mime = "png" if ext == "png" else "jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{mime};base64,{b64}"