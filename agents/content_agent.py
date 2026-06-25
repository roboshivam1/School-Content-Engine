# agents/content_agent.py
# Claude Sonnet middleware — reads the registry + schemas, selects a template,
# fills all its fields, and returns structured render instructions.

import json
from pathlib import Path
from typing import Optional
import anthropic

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.registry_loader import load_registry, load_schema


# ── Layout params for multiple_achievement grid ───────────────────────────────

def compute_grid_layout(student_count: int) -> dict:
    """Compute CSS grid layout params based on number of students."""
    if student_count <= 2:
        return {"grid_cols": 2, "name_font_size": 26, "score_font_size": 32,
                "photo_size": 130, "card_padding": 20}
    elif student_count <= 3:
        return {"grid_cols": 3, "name_font_size": 22, "score_font_size": 28,
                "photo_size": 110, "card_padding": 16}
    elif student_count <= 4:
        return {"grid_cols": 2, "name_font_size": 22, "score_font_size": 28,
                "photo_size": 110, "card_padding": 16}
    elif student_count <= 6:
        return {"grid_cols": 3, "name_font_size": 20, "score_font_size": 24,
                "photo_size": 90, "card_padding": 14}
    else:
        return {"grid_cols": 4, "name_font_size": 17, "score_font_size": 20,
                "photo_size": 76, "card_padding": 12}


def chunk_students(students: list, per_slide: int = 6) -> list[list]:
    """Split large student lists into carousel-sized chunks."""
    return [students[i:i+per_slide] for i in range(0, len(students), per_slide)]


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    school_config: dict,
    job_description: str,
    event_context: dict,
    registry: dict,
    all_schemas: dict,
    requested_post_types: list[str],
    requested_variants: list[str],
) -> str:
    """Build the full prompt Claude Sonnet receives."""

    # Summarise registry for template selection
    template_options = []
    for t in registry["templates"]:
        tid = t["id"]
        if requested_post_types != ["auto"] and tid not in requested_post_types:
            continue
        schema = all_schemas.get(tid, {})
        fields_summary = {
            k: {
                "required": v.get("required"),
                "type": v.get("type"),
                "max_chars": v.get("max_chars"),
                "description": v.get("description", ""),
            }
            for k, v in schema.get("fields", {}).items()
        }
        template_options.append({
            "id": tid,
            "use_when": t["use_when"],
            "is_carousel": schema.get("is_carousel", False),
            "carousel_notes": schema.get("carousel_notes", ""),
            "available_variants": t["variants"],
            "fields": fields_summary,
        })

    variants_instruction = (
        "all available variants for the chosen template"
        if requested_variants == ["all"]
        else f"only these variants: {requested_variants}"
    )

    school = school_config
    colors = school.get("colors", {})
    content_prefs = school.get("content", {})

    prompt = f"""You are a professional school social media content manager.

SCHOOL PROFILE
--------------
Name:             {school["school_name"]}
City:             {school["city"]}
Tagline:          {school["tagline"]}
Brand tone:       {content_prefs.get("tone", "warm")}
Language:         {content_prefs.get("language", "en")}
Instagram handle: {school.get("social", {}).get("instagram_handle", "")}
Always-on hashtags: {content_prefs.get("hashtags", {}).get("always_on", [])}

OPERATOR JOB BRIEF
------------------
{job_description}

EVENT CONTEXT (from vision analysis)
-------------------------------------
Event type:     {event_context.get("event_type", "Unknown")}
Summary:        {event_context.get("event_summary", "")}
Mood:           {event_context.get("mood", "celebratory")}
Sub-events:     {event_context.get("sub_events", [])}
Vision notes:   {event_context.get("image_quality_notes", "")}

AVAILABLE TEMPLATES
-------------------
{json.dumps(template_options, indent=2)}

YOUR TASK
---------
1. Select the single best template_id from the list above.
2. Fill in every field defined in that template's `fields` object.
   - Respect max_chars limits strictly.
   - For image_path fields: write the string "AUTO" — the pipeline will assign real images.
   - For array fields (like `students` or `slides`): produce realistic placeholder items
     with all sub-fields filled. Use the event context to make them feel real.
   - For carousel templates with a `slides` array: produce 3-5 slide items.
3. Write the Instagram caption (2-4 sentences, warm and proud).
4. Select hashtags: always-on + 4-6 event-relevant ones.
5. Specify which variants to render: {variants_instruction}.

RESPONSE FORMAT
---------------
Respond ONLY with a JSON object — no preamble, no markdown fences:

{{
  "template_id": "chosen_template_id",
  "variants": ["list", "of", "variants", "to", "render"],
  "filled_fields": {{
    // all fields from the template's schema, fully filled
  }},
  "caption": "full Instagram caption here",
  "hashtags": ["#tag1", "#tag2"],
  "reasoning": "one sentence explaining why this template was chosen"
}}"""

    return prompt


# ── Main content agent ────────────────────────────────────────────────────────

def run_content_agent(
    school_config: dict,
    job_description: str,
    event_context: dict,
    requested_post_types: list[str] = None,
    requested_variants: list[str] = None,
    client: Optional[anthropic.Anthropic] = None,
) -> dict:
    """
    Core content agent. Calls Claude Sonnet to select template + fill fields.

    Returns:
    {
      "template_id":   str,
      "variants":      list[str],
      "filled_fields": dict,
      "caption":       str,
      "hashtags":      list[str],
      "reasoning":     str,
      "layout_params": dict  (only for multiple_achievement)
    }
    """
    if client is None:
        client = anthropic.Anthropic()

    requested_post_types = requested_post_types or ["auto"]
    requested_variants   = requested_variants   or ["all"]

    # Load registry + all schemas
    registry    = load_registry()
    all_schemas = {}
    for t in registry["templates"]:
        try:
            all_schemas[t["id"]] = load_schema(t["id"])
        except FileNotFoundError:
            pass

    prompt = _build_prompt(
        school_config, job_description, event_context,
        registry, all_schemas, requested_post_types, requested_variants
    )

    print("[content_agent] Calling Claude Sonnet...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=(
            "You are a school social media content manager. "
            "You always respond with valid JSON only — no markdown, no preamble."
        ),
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"[content_agent] Claude returned invalid JSON: {e}\n\nRaw:\n{raw}")

    template_id = result.get("template_id")
    print(f"[content_agent] Template selected: {template_id} — {result.get('reasoning', '')}")

    # Post-process: compute layout params for multiple_achievement
    if template_id == "multiple_achievement":
        students = result.get("filled_fields", {}).get("students", [])
        layout   = compute_grid_layout(len(students))
        result["layout_params"] = layout
        print(f"[content_agent] Grid layout: {len(students)} students → {layout['grid_cols']} columns")

    return result