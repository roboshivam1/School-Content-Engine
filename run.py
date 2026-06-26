# run.py
# Entrypoint for the JARVIS content pipeline.
#
# Usage:
#   python run.py              → reads job.json from project root
#   python run.py my_job.json  → reads the specified job file
#
# Or import run_pipeline() directly from JARVIS.

import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import anthropic

sys.path.insert(0, str(Path(__file__).parent))

from core.job import ContentJob
from core.config_loader import load_config
from agents.vision_agent import run_vision_agent
from agents.content_agent import run_content_agent
from agents.render_agent import run_render_agent

load_dotenv()

BASE_DIR = Path(__file__).parent


# ── Job file loader ───────────────────────────────────────────────────────────

def load_job_file(path: str = None) -> dict:
    """
    Load a job definition from a JSON file.
    Defaults to job.json in the project root if no path given.
    """
    job_path = Path(path) if path else BASE_DIR / "job.json"

    if not job_path.exists():
        raise FileNotFoundError(
            f"Job file not found: {job_path}\n"
            f"Create a job.json in the project root or pass a path as argument."
        )

    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)

    # Validate required fields
    required = ["school_id", "media_dir", "description"]
    missing  = [k for k in required if k not in job]
    if missing:
        raise ValueError(f"Job file is missing required fields: {missing}")

    # Apply defaults for optional fields
    job.setdefault("post_types",  ["auto"])
    job.setdefault("variants",    ["all"])
    job.setdefault("output_base", "output")
    job.setdefault("design_set",  "auto")
    job.setdefault("dry_run",     False)

    return job


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(job: dict) -> dict:
    """
    Full pipeline. Accepts a job dict (loaded from job.json or built by JARVIS).
    Returns the render_agent result dict.
    """
    school_id   = job["school_id"]
    media_dir   = job["media_dir"]
    description = job["description"]
    post_types  = job["post_types"]
    variants    = job["variants"]
    output_base = job["output_base"]
    dry_run     = job.get("dry_run", False)

    school_config = load_config(school_id)

    # ── Resolve design_set ────────────────────────────────────────────────────
    # Priority: job.json → school config → hardcoded fallback
    design_set = job.get("design_set", "auto")
    if design_set == "auto":
        design_set = school_config.get("design_set", "glassmorphism")

    print(f"\n{'='*55}")
    print(f"  JARVIS Content Agent")
    print(f"  School  : {school_id}")
    print(f"  Design  : {design_set}")
    print(f"  Job     : {description[:55]}...")
    print(f"  Dry run : {dry_run}")
    print(f"{'='*55}\n")

    client = anthropic.Anthropic()

    content_job = ContentJob(
        school_id=school_id,
        description=description,
        raw_media_dir=media_dir,
        post_types=post_types,
        variants=variants,
        output_dir=output_base,
    )
    print(f"[run] Job ID: {content_job.job_id}")

    # ── Step 1: Vision agent ──────────────────────────────────────────────────
    print("\n[run] Step 1 — Vision Agent")
    if dry_run:
        vision_result = {
            "ranked_images": [],
            "best_paths":    [],
            "event_context": {
                "event_type":               "School Event",
                "event_summary":            description,
                "mood":                     "celebratory",
                "sub_events":               [],
                "suggested_cover_headline": "A Day to Remember.",
                "suggested_caption":        description,
                "suggested_hashtags":       ["#SchoolLife"],
                "image_quality_notes":      "Dry run — no images processed.",
            }
        }
    else:
        vision_result = run_vision_agent(
            media_dir=media_dir,
            job_description=description,
            school_name=school_config["school_name"],
            client=client,
        )

    # ── Step 2: Content agent ─────────────────────────────────────────────────
    print("\n[run] Step 2 — Content Agent")
    content_result = run_content_agent(
        school_config=school_config,
        job_description=description,
        event_context=vision_result["event_context"],
        requested_post_types=post_types,
        requested_variants=variants,
        client=client,
    )

    # ── Step 3: Render agent ──────────────────────────────────────────────────
    print("\n[run] Step 3 — Render Agent")
    school_output = Path(output_base) / school_id
    school_output.mkdir(parents=True, exist_ok=True)

    render_result = run_render_agent(
        school_config=school_config,
        content_result=content_result,
        vision_result=vision_result,
        job_id=content_job.job_id,
        base_output_dir=str(school_output),
        design_set=design_set,
    )

    # ── Save job summary ──────────────────────────────────────────────────────
    summary = {
        "job_id":        content_job.job_id,
        "school_id":     school_id,
        "description":   description,
        "design_set":    design_set,
        "template_used": content_result["template_id"],
        "reasoning":     content_result.get("reasoning", ""),
        "output_dir":    render_result["output_dir"],
        "rendered":      render_result["rendered"],
        "caption":       render_result["caption"],
        "hashtags":      render_result["hashtags"],
    }
    summary_path = Path(render_result["output_dir"]) / "job_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n{'='*55}")
    print(f"  ✓ Done — {content_job.job_id}")
    print(f"  Output : {render_result['output_dir']}")
    print(f"  Files  : {sum(len(v) for v in render_result['rendered'].values())} images")
    print(f"{'='*55}\n")

    return render_result


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    job_file = sys.argv[1] if len(sys.argv) > 1 else None
    job      = load_job_file(job_file)
    run_pipeline(job)