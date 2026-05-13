"""
Creative Soul — Amé's creative translator.

Not a generator. A translator. The user shows Amé a visual and says
"I want to make something like this." She looks at it, breaks it down,
names the likely tools, and gives concrete first steps.

Dedicated to the namesake's creative soul. 60% is the bar.
Perfection betrays the point.
"""

from __future__ import annotations
import json
import re


_TOOL_HINTS = {
    "after effects": ("motion graphics", "particle systems", "trapcode", "saber",
                       "video", "looping animation", "kinetic typography"),
    "blender":       ("3d render", "low-poly", "isometric 3d", "voxel", "topology",
                       "procedural materials", "geometry nodes"),
    "photoshop":     ("photo manipulation", "compositing", "double-exposure",
                       "matte painting", "dodge/burn", "color grading on stills"),
    "figma":         ("ui design", "mobile mockup", "dashboard", "marketing site",
                       "design system", "wireframe"),
    "illustrator":   ("vector illustration", "logo", "geometric pattern", "icon set"),
    "touchdesigner": ("audio-reactive visuals", "real-time generative", "vj",
                       "live shader", "interactive installation"),
    "premiere pro":  ("video edit", "subtitle styling", "smooth zoom", "match cut"),
    "davinci resolve":("color grading", "film look", "log footage", "node-based color"),
    "fl studio":     ("electronic music", "trap beats", "808s", "automation clip"),
    "ableton live":  ("electronic music", "live performance", "warping samples", "max for live"),
    "procreate":     ("digital illustration", "ipad sketch", "watercolor brushes", "comic"),
    "krita":         ("digital painting", "fan art", "open-source brushes"),
    "gimp":          ("photo edit", "open-source", "free alternative"),
    "code/webgl":    ("creative coding", "shader", "fragment", "p5.js", "three.js",
                       "generative art", "noise field"),
}


def _detect_tools(description: str) -> list[str]:
    """Quick heuristic pass: which tools fit the user's brief?"""
    low = description.lower()
    hits: list[str] = []
    for tool, hints in _TOOL_HINTS.items():
        if any(h in low for h in hints):
            hits.append(tool)
    return hits[:4]  # cap suggestion count


def translate(brief: str) -> dict:
    """Take a free-form description and return a structured translation
    of likely tools + first concrete steps. Pure-local, no model call."""
    brief = (brief or "").strip()
    if not brief:
        return {"success": False, "error": "empty brief"}

    tools = _detect_tools(brief)
    steps: list[str] = []
    if "loop" in brief.lower() or "seamless" in brief.lower():
        steps.append("Plan the loop's endpoints first — match first and last frame before adding motion.")
    if "color" in brief.lower() or "palette" in brief.lower():
        steps.append("Pick 3 colors and one accent before touching anything else; everything else falls out of that.")
    if "particle" in brief.lower() or "swarm" in brief.lower():
        steps.append("Particles read as a single mass — fight the urge to keyframe individuals.")
    if not steps:
        steps.append("Block the silhouette in 5 minutes. If the silhouette doesn't read, no detail will save it.")

    return {
        "success": True,
        "tools": tools or ["(unsure — share a reference and I can be more specific)"],
        "first_steps": steps,
        "brief": brief,
    }


# Convenience for json-only consumers.
def translate_json(brief: str) -> str:
    return json.dumps(translate(brief), ensure_ascii=False)
