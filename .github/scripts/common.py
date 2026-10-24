"""Shared helpers for the generated README cards and the light-theme assets."""

import html
import json
import os
import re
import sys
import urllib.request

# Dark -> light colors for GitHub's light themes, shared by every card and static asset.
# Card backgrounds are transparent and borders, slots and tints are see-through #8b949e, so every card takes
# the page's own shade in any dark or light variant (default, soft dark, high contrast, colour-blind).
LIGHT = {
    "#0d1117": "#ffffff",  # ring cut around the Discord status dot
    "#e6edf3": "#1f2328",
    "#c9d1d9": "#1f2328",
    "#8b949e": "#59636e",
    "#6e7681": "#8c959f",
    "#7ee787": "#2da44e",
    "#3fb950": "#1a7f37",
    "#56d364": "#1a7f37",
    "#c25bd4": "#a02db0",
    "#d670e0": "#a02db0",
    "#b42fc4": "#a02db0",
    "#d29922": "#9a6700",
    "#f85149": "#cf222e",
    "#034525": "#9be9a8",
    "#0f6d31": "#40c463",
    "#00c647": "#30a14e",
    "#0e4429": "#9be9a8",  # GitHub's contribution levels 1-4
    "#006d32": "#40c463",
    "#26a641": "#30a14e",
    "#39d353": "#216e39",
    "#1a7f37": "#6fdd8b",  # green glow
    "#800080": "#e2b6f2",  # purple glow
}
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")

# Soft light spots on the box edges. A box's bottom spot matches the next box's top spot (same side, same color),
# so the light seems to continue across the gap. The static assets (header, terminal, social buttons) carry
# copies of their spots.
GREEN, PURPLE = "#1a7f37", "#800080"
GLOWS = {
    "header": ((750, 0, GREEN), (150, 220, PURPLE)),
    "social": ((150, 0, PURPLE), (750, 112, GREEN)),
    "terminal": ((750, 0, GREEN), (750, 376, PURPLE)),
    "stats": ((750, 0, PURPLE), (150, 196, GREEN)),
    "snake": ((150, 0, GREEN), (750, 232, PURPLE)),
}


def glow(box: str, shift: int = 0) -> str:
    """Spots of one box; `shift` is the image's x offset inside a box made of several images.
    Needs a #blur filter (stdDeviation 45) and the .glow breathing animation in the same SVG."""
    spots = "".join(f'<circle cx="{x - shift}" cy="{y}" r="110" fill="{color}"/>' for x, y, color in GLOWS[box])
    return f'<g class="glow" filter="url(#blur)" opacity=".45">{spots}</g>'


def recolor(text: str, table: dict[str, str]) -> str:
    # one pass, so a color that is both a key and a value is never remapped twice
    return HEX.sub(lambda m: table.get(m.group(0).lower(), m.group(0)), text)


def fetch(url: str, headers: dict[str, str] | None = None, body: bytes | None = None) -> bytes:
    # a body turns the request into a POST
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "korrnik-profile-readme", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.read()


def graphql(query: str, variables: dict) -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is required: the GraphQL API does not accept anonymous requests")
    body = json.dumps({"query": query, "variables": variables}).encode()
    reply = json.loads(fetch("https://api.github.com/graphql", {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, body))
    if reply.get("errors"):
        # failing the run keeps the previously published card
        sys.exit(f"graphql error: {reply['errors']}")
    return reply["data"]


def esc(text: str, limit: int) -> str:
    # external text is clipped and escaped before it goes into an SVG
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return html.escape(text, quote=True)
