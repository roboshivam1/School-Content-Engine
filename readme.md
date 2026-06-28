> *"Stopping advertising to save money is like stopping your watch to save time."*
---
# JARVIS Content Agent

An AI-powered social media content generation pipeline for Indian schools. Takes raw event photos, understands what happened, designs branded carousels and posts, and delivers ready-to-upload content — automatically.

Built as a standalone agent that plugs into the JARVIS multi-agent system.

---

## What it does

1. You drop raw event photos into a folder and fill in a one-line job description
2. A vision agent scans and ranks photos by quality, then sends the best ones to Claude Vision to understand the event
3. A content agent selects the right post type, writes captions, and assigns each photo to the slide whose caption actually matches what's in that photo
4. A render agent produces finished, school-branded PNGs at Instagram/WhatsApp dimensions
5. Output lands in an organised folder — ready to upload, nothing to edit

One command. One folder of raw photos in. One folder of finished content out.

---

## Output formats

| Variant | Dimensions | Used for |
|---|---|---|
| `instagram_square` | 1080 × 1080px | Instagram feed posts, carousel cover |
| `instagram_carousel` | 1080 × 1080px | Carousel inner slides |
| `instagram_story` | 1080 × 1920px | Instagram & Facebook stories |
| `whatsapp_status` | 1080 × 1920px | WhatsApp status updates |

---

## Post types

| Type | When it's used |
|---|---|
| `event_recap` | Post-event carousel with photos — most common |
| `event_announcement` | Upcoming events, save-the-date posts |
| `single_achievement` | One student/teacher achievement spotlight |
| `multiple_achievement` | Board toppers, JEE/NEET results, merit lists |
| `festival_greeting` | Diwali, Independence Day, Teachers Day etc. |

---

## Project structure

```
jarvis-content-agent/
│
├── run.py                        # Single entrypoint — edit job.json and run this
├── job.json                      # Job definition file — edit this per job
├── registry.json                 # Template registry — maps post types to schemas
├── requirements.txt
├── .env                          # ANTHROPIC_API_KEY goes here (not committed)
│
├── configs/                      # One file per school
│   ├── malviya_convent_jaipur.py
│   └── msmsv_jaipur.py
│
├── templates/
│   ├── event_recap/
│   │   └── schema.json           # Data schema — design-agnostic
│   ├── event_announcement/
│   │   └── schema.json
│   ├── single_achievement/
│   │   └── schema.json
│   ├── multiple_achievement/
│   │   └── schema.json
│   ├── festival_greeting/
│   │   └── schema.json
│   │
│   └── glassmorphism/            # Design set — HTML lives here
│       ├── event_recap/
│       │   ├── instagram_square.html
│       │   ├── instagram_carousel.html
│       │   └── instagram_story.html
│       ├── event_announcement/
│       │   ├── instagram_square.html
│       │   ├── instagram_story.html
│       │   └── whatsapp_status.html
│       └── ...
│
├── agents/
│   ├── vision_agent.py           # Image quality scoring + Claude Vision analysis
│   ├── content_agent.py          # Claude Sonnet — template selection + field filling
│   └── render_agent.py           # Orchestrates Jinja2 + Playwright rendering
│
├── core/
│   ├── job.py                    # ContentJob dataclass
│   ├── config_loader.py          # Loads school config, resolves assets to base64
│   ├── registry_loader.py        # Loads registry + schemas, resolves template paths
│   └── renderer.py               # Pure render function — Jinja2 + Playwright
│
├── assets/
│   ├── malviya_convent_jaipur/
│   │   └── logo.png
│   └── msmsv_jaipur/
│       └── logo.png
│
├── media/                        # Drop raw event photos here per job
│   └── sports_day/
│       ├── photo1.jpg
│       └── photo2.jpg
│
└── output/                       # Finished content lands here
    └── malviya_convent_jaipur/
        └── 20260624_143012__sports_day/
            ├── instagram_square/
            │   ├── slide_01_cover.png
            │   ├── slide_02.png
            │   └── slide_05_closing.png
            ├── instagram_story/
            │   └── slide_01_cover.png
            ├── caption.txt
            └── job_summary.json
```

---

## Setup

**1. Clone and install dependencies**

```bash
cd jarvis-content-agent
pip install -r requirements.txt
playwright install chromium
```

**2. Add your API key**

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get your key from [console.anthropic.com](https://console.anthropic.com).

**3. Add school assets**

Place the school logo in `assets/<school_id>/logo.png`. The `school_id` must match the filename in `configs/`.

---

## Running a job

**Edit `job.json`:**

```json
{
  "school_id":   "malviya_convent_jaipur",
  "media_dir":   "./media/sports_day",
  "description": "Annual Sports Day held 20th June 2025. Students competed in 100m sprint, relay, tug of war. Prize distribution at the end. 400 students and 200 parents attended.",
  "post_types":  ["auto"],
  "variants":    ["all"],
  "design_set":  "auto",
  "output_base": "output"
}
```

**Run:**

```bash
python run.py
```

You can also pass a specific job file:

```bash
python run.py jobs/science_fair.json
```

---

## Job fields

| Field | Required | Description |
|---|---|---|
| `school_id` | ✓ | Must match a file in `configs/` |
| `media_dir` | ✓ | Path to folder containing raw event photos |
| `description` | ✓ | Natural language brief — what happened, when, context |
| `post_types` | | `["auto"]` lets AI decide, or specify e.g. `["event_recap"]` |
| `variants` | | `["all"]` renders everything, or e.g. `["instagram_square"]` |
| `design_set` | | `"auto"` reads from school config, or name a specific design set |
| `output_base` | | Base output folder, default `"output"` |
| `dry_run` | | `true` skips vision AI — useful for template testing |

---

## Adding a new school

**1. Create a config file** at `configs/<school_id>.py`:

```python
SCHOOL_CONFIG = {
    "school_id":   "new_school_city",
    "school_name": "New School",
    "city":        "City",
    "tagline":     "School Tagline",
    "colors": {
        "primary":       "#XXXXXX",
        "primary_dark":  "#XXXXXX",
        "secondary":     "#XXXXXX",
        "accent":        "#XXXXXX",
        "white":         "#FFFFFF",
        "off_white":     "#FAFAFA",
        "text_dark":     "#111111",
        "text_light":    "#FFFFFF",
        "overlay_dark":  "rgba(r, g, b, 0.95)",
        "overlay_mid":   "rgba(r, g, b, 0.75)",
        "overlay_light": "rgba(r, g, b, 0.38)",
    },
    "fonts": {
        "headline":        "Playfair Display",
        "headline_weight": "700",
        "body":            "Poppins",
        "body_weight":     "400",
        "label":           "Poppins",
        "label_weight":    "500",
        "google_fonts_url": "https://fonts.googleapis.com/css2?family=...",
    },
    "assets": {
        "logo_path": "assets/new_school_city/logo.png",
    },
    "design_set": "glassmorphism",
    "content": {
        "language":   "en",
        "tone":       "warm",
        "emoji_usage": "minimal",
        "hashtags": {
            "always_on": ["#SchoolName", "#City"],
        },
    },
    "social": {
        "instagram_handle": "@handle",
    },
    "template_defaults": {
        "logo_size":     80,
        "corner_radius": 16,
        "slide_size":    1080,
        "story_width":   1080,
        "story_height":  1920,
    },
    "carousel": {
        "max_students_per_slide":          6,
        "include_school_name_every_slide": True,
    },
}
```

**2. Add school logo** at `assets/<school_id>/logo.png`

That's it. No code changes needed.

---

## Adding a new design set

Create a folder under `templates/` with your design set name and add HTML files for each post type and variant:

```
templates/
  minimalism/
    event_recap/
      instagram_square.html
      instagram_carousel.html
      instagram_story.html
    event_announcement/
      instagram_square.html
      ...
```

HTML templates use Jinja2. All dynamic values are injected as CSS custom properties in a single `:root {}` block — the rest of the CSS is pure valid CSS:

```html
<style>
  :root {
    /* All Jinja2 lives only here */
    --c-primary:      {{ colors.primary }};
    --c-accent:       {{ colors.accent }};
    --f-headline:     '{{ fonts.headline }}', serif;
    --f-body:         '{{ fonts.body }}', sans-serif;
  }

  /* Everything below is pure CSS — no Jinja2 */
  .headline {
    font-family: var(--f-headline);
    color: var(--c-primary);
  }
</style>
```

Available template variables come from three sources, all merged into one flat dict:

- **School config** — `school_name`, `city`, `colors`, `fonts`
- **Resolved assets** — `logo_b64`, `watermark_b64` (base64 data URIs)
- **AI-filled fields** — defined per post type in `templates/<type>/schema.json`

If a template for a variant doesn't exist in the requested design set, the pipeline automatically falls back to `glassmorphism` and logs a warning — it never crashes mid-job.

Set a school's default design in their config:
```python
"design_set": "minimalism"
```

Or override per job in `job.json`:
```json
"design_set": "dark_luxury"
```

---

## How the pipeline works

```
job.json
    ↓
run.py — loads school config, resolves design_set
    ↓
vision_agent.py
  • scans media_dir, filters by blur + brightness
  • sends best 8 photos to Claude Vision
  • gets back: event type, mood, per-image descriptions, best cover index
    ↓
content_agent.py
  • receives school config + event context + image descriptions
  • reads template registry and all schemas
  • Claude Sonnet picks the right template and fills every field
  • assigns PHOTO_INDEX:N to each slide — matching caption to correct image
    ↓
render_agent.py
  • resolves PHOTO_INDEX:N tokens to real file paths
  • converts all image paths to base64 data URIs
  • merges school config + filled fields into render_data
  • for each variant:
      - renders cover slide (Jinja2 → HTML → Playwright → PNG)
      - renders each inner slide with its matched photo
      - renders closing slide
  • saves caption.txt and job_summary.json
    ↓
output/<school_id>/<job_id>__<event>/
  instagram_square/   slide_01_cover.png  slide_02.png  ...
  instagram_story/    slide_01_cover.png  ...
  caption.txt
  job_summary.json
```

---

## Currently built schools

| School | Config | Design set |
|---|---|---|
| Malviya Convent School, Jaipur | `malviya_convent_jaipur.py` | glassmorphism |
| M.S.M.S. Vidyalaya, Jaipur | `msmsv_jaipur.py` | dark_luxury (falls back to glassmorphism) |

---

## Currently built design sets

| Design set | Status | Character |
|---|---|---|
| `glassmorphism` | ✅ Complete | Frosted glass cards, blur effects, modern |
| `dark_luxury` | 🔲 Planned | Deep blacks, gold accents, heritage feel |
| `minimalism` | 🔲 Planned | Whitespace-heavy, editorial, premium |
| `bold` | 🔲 Planned | Large typography, high energy, sports |

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | Claude Vision + Claude Sonnet API |
| `jinja2` | HTML template rendering |
| `playwright` | Headless Chromium screenshots |
| `opencv-python-headless` | Image quality scoring |
| `Pillow` | Image utilities |
| `python-dotenv` | `.env` file loading |

---

## Part of JARVIS

This agent is designed to run as a module inside the JARVIS multi-agent system. Call `run_pipeline(job_dict)` directly from any JARVIS agent:

```python
from run import run_pipeline

result = run_pipeline({
    "school_id":   "malviya_convent_jaipur",
    "media_dir":   "/path/to/photos",
    "description": "Annual Sports Day recap",
    "post_types":  ["event_recap"],
    "variants":    ["instagram_square", "instagram_story"],
    "design_set":  "auto",
    "output_base": "output",
})

print(result["output_dir"])   # where the files landed
print(result["caption"])      # generated Instagram caption
```