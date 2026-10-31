"""Shared helpers for the generated README cards and the static assets."""

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

USER = "KoRrNiK"
# GitHub's holiday palettes for the contribution graph (Primer primitives 11.10), used while GitHub itself
# shows them: they replace the green side of every card, the purple side suits both seasons as it is.
# Keys are base dark colors, as in LIGHT; each season has a (dark, light) pair of tables.
SEASONS = {
    "halloween": (
        {"#0e4429": "#fac68f", "#006d32": "#c46212", "#26a641": "#984b10", "#39d353": "#e3d04f",  # levels 1-4
         "#034525": "#984b10", "#0f6d31": "#c46212", "#00c647": "#f68c41",  # header cells, lines
         "#1a7f37": "#c46212", "#56d364": "#f68c41", "#3fb950": "#f68c41", "#7ee787": "#e3d04f"},  # glow, accents
        {"#0e4429": "#f0db3d", "#006d32": "#ffd642", "#26a641": "#f68c41", "#39d353": "#1f2328",
         "#034525": "#f0db3d", "#0f6d31": "#ffd642", "#00c647": "#f68c41",
         "#1a7f37": "#fdbb7d", "#56d364": "#bc4c00", "#3fb950": "#bc4c00", "#7ee787": "#f68c41"},
    ),
    "winter": (
        {"#0e4429": "#0c2d6b", "#006d32": "#1158c7", "#26a641": "#58a6ff", "#39d353": "#cae8ff",
         "#034525": "#0c2d6b", "#0f6d31": "#1158c7", "#00c647": "#58a6ff",
         "#1a7f37": "#1158c7", "#56d364": "#58a6ff", "#3fb950": "#58a6ff", "#7ee787": "#cae8ff"},
        {"#0e4429": "#b6e3ff", "#006d32": "#54aeff", "#26a641": "#0969da", "#39d353": "#0a3069",
         "#034525": "#b6e3ff", "#0f6d31": "#54aeff", "#00c647": "#0969da",
         "#1a7f37": "#9fd3ff", "#56d364": "#0969da", "#3fb950": "#0969da", "#7ee787": "#54aeff"},
    ),
}

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


def paint(svg: str, light: bool, holiday: str | None) -> str:
    """Base dark colors -> the published ones: the light theme and/or the holiday palette, in one pass."""
    table = dict(LIGHT) if light else {}
    if holiday:
        table.update(SEASONS[holiday][1 if light else 0])
    return recolor(svg, table)


def season() -> str | None:
    """The holiday palette GitHub shows on the contribution graph right now, read from the graph itself,
    so the cards switch on and back exactly when GitHub does."""
    page = fetch(f"https://github.com/users/{USER}/contributions").decode("utf-8")
    found = re.search(r'data-holiday="([\w-]+)"', page)
    # match by name, so e.g. "winter_solstice" still picks the winter palette
    return next((name for name in SEASONS if found and name in found.group(1)), None)


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
