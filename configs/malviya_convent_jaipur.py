# =============================================================================
# SCHOOL CONFIG — Malviya Convent School, Jaipur
# Created for: JARVIS Content Agent
# Last updated: 2026-06-24
# =============================================================================

SCHOOL_CONFIG = {

    # -------------------------------------------------------------------------
    # IDENTITY
    # -------------------------------------------------------------------------
    "school_id":        "malviya_convent_jaipur",
    "school_name":      "Malviya Convent School",
    "school_name_full": "Malviya Convent School, Jaipur",
    "city":             "Jaipur",
    "tagline":          "Satyameva Jayate",          # सत्यमेव जयते
    "tagline_hindi":    "सत्यमेव जयते",
    "established":      None,                         # fill if known
    "website":          None,                         # fill when available
    "email":            None,

    # -------------------------------------------------------------------------
    # BRANDING — COLOURS
    # -------------------------------------------------------------------------
    "colors": {
        "primary":      "#C0177D",   # deep magenta — dominant brand colour
        "primary_dark": "#7A0E50",   # darkened magenta — for overlays, depth
        "secondary":    "#F2C4E3",   # soft blush pink — light ring in logo
        "accent":       "#F5C842",   # warm gold — yellow banner in logo
        "white":        "#FFFFFF",
        "off_white":    "#FDF5FA",   # very light pink-tinted white for backgrounds
        "text_dark":    "#1A0A12",   # near-black with a warm magenta undertone
        "text_light":   "#FFFFFF",   # for text on dark/magenta backgrounds
        "overlay":      "rgba(192, 23, 125, 0.72)",  # magenta overlay on photos

        # Pre-computed overlay variants (primary_dark = #7A0E50 = rgb(122,14,80))
        # Used in CSS gradients — avoids concatenating hex + alpha in templates
        "overlay_dark":  "rgba(122, 14, 80, 0.95)",
        "overlay_mid":   "rgba(122, 14, 80, 0.75)",
        "overlay_light": "rgba(122, 14, 80, 0.35)",
    },

    # -------------------------------------------------------------------------
    # BRANDING — TYPOGRAPHY
    # Typography system: Playfair Display (headlines) + Poppins (body)
    # Playfair Display: prestigious, serif — suits "Convent" heritage
    # Poppins: modern, geometric sans — clean at small sizes, very readable
    # -------------------------------------------------------------------------
    "fonts": {
        "headline":         "Playfair Display",   # event names, big statements
        "headline_weight":  "700",
        "subheadline":      "Poppins",
        "subheadline_weight": "600",
        "body":             "Poppins",
        "body_weight":      "400",
        "label":            "Poppins",            # small caps labels, tags
        "label_weight":     "500",
        "google_fonts_url": (
            "https://fonts.googleapis.com/css2?"
            "family=Playfair+Display:wght@400;700;900&"
            "family=Poppins:wght@400;500;600;700&"
            "display=swap"
        ),
    },

    # -------------------------------------------------------------------------
    # BRANDING — ASSETS
    # Paths relative to project root. Converted to base64 at render time.
    # -------------------------------------------------------------------------
    "assets": {
        "logo_path":          "assets/malviya_convent_jaipur/logo.png",
        "logo_white_path":    "assets/malviya_convent_jaipur/logo_white.png",  # if available
        "watermark_path":     "assets/malviya_convent_jaipur/watermark.png",   # low-opacity version
        "favicon_path":       "assets/malviya_convent_jaipur/logo.png",
    },

    # -------------------------------------------------------------------------
    # CONTENT PREFERENCES
    # -------------------------------------------------------------------------
    "content": {
        "language":           "en",         # "en" | "hi" | "en+hi"
        "tone":               "warm",       # "formal" | "warm" | "fun"
                                            # warm = proud & celebratory but not stiff
        "caption_style":      "narrative",  # "narrative" | "punchy" | "listicle"
        "emoji_usage":        "minimal",    # "none" | "minimal" | "moderate"
        "always_include_tagline": True,     # append Satyameva Jayate to posts

        # Hashtag tiers — always_on used on every post, event-specific added per job
        "hashtags": {
            "always_on": [
                "#MalviyaConventSchool",
                "#MalviyaConventJaipur",
                "#Jaipur",
            ],
            "school_life": [
                "#SchoolLife",
                "#ConventSchool",
                "#JaipurSchool",
                "#RajasthanSchools",
            ],
            "academics": [
                "#ExcellenceInEducation",
                "#AcademicAchievement",
                "#ProudSchool",
            ],
            "events": [
                "#SchoolEvent",
                "#StudentLife",
                "#MemoriesToTreasure",
            ],
            "results": [
                "#JEE2025",
                "#NEET2025",
                "#BoardResults",
                "#Toppers",
                "#ProudMoment",
            ],
        },
    },

    # -------------------------------------------------------------------------
    # SOCIAL MEDIA
    # -------------------------------------------------------------------------
    "social": {
        "instagram_handle":   "@malviyaconventjaipur",   # update when confirmed
        "facebook_page":      None,
        "youtube_channel":    None,
    },

    # -------------------------------------------------------------------------
    # TEMPLATE DEFAULTS
    # Used when building render_data — these are fallback values
    # -------------------------------------------------------------------------
    "template_defaults": {
        "logo_size":          80,       # px, logo width on slides
        "watermark_opacity":  0.12,     # subtle watermark on photo backgrounds
        "corner_radius":      16,       # px, card border radius
        "slide_size":         1080,     # px, square Instagram format
        "story_width":        1080,     # px
        "story_height":       1920,     # px
    },

    # -------------------------------------------------------------------------
    # CAROUSEL BEHAVIOUR
    # -------------------------------------------------------------------------
    "carousel": {
        "max_students_per_slide":   6,
        "cover_slide_style":        "full_bleed_photo",   # photo behind overlay
        "closing_slide_style":      "branded_solid",       # solid magenta, logo centered
        "include_slide_numbers":    False,
        "include_school_name_every_slide": True,
    },

}