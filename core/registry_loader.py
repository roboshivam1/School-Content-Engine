# core/registry_loader.py
# Loads the template registry and individual schemas.
# The content agent reads these to know what templates exist and what fields to fill.

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def load_registry() -> dict:
    """Load registry.json — the AI's map of all available templates."""
    registry_path = BASE_DIR / "registry.json"
    with open(registry_path) as f:
        return json.load(f)


def load_schema(template_id: str) -> dict:
    """Load the schema.json for a specific template."""
    schema_path = BASE_DIR / "templates" / template_id / "schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"No schema found for template '{template_id}'")
    with open(schema_path) as f:
        return json.load(f)


def load_all_schemas() -> dict:
    """
    Load every schema. Returns dict keyed by template_id.
    Used when building the full prompt context for the content agent.
    """
    registry = load_registry()
    schemas = {}
    for entry in registry.get("templates", []):
        tid = entry["id"]
        try:
            schemas[tid] = load_schema(tid)
        except FileNotFoundError:
            print(f"[registry_loader] WARNING: Schema missing for template '{tid}'")
    return schemas


def get_template_path(template_id: str, variant: str) -> Path:
    """Return the filesystem path to a specific template variant HTML file."""
    path = BASE_DIR / "templates" / template_id / f"{variant}.html"
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path