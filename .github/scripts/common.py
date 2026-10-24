"""Shared helpers for the generated README cards and the light-theme assets."""

import html
import re
import urllib.request

# dark -> light colors for GitHub's light theme, shared by every card and static asset
LIGHT = {
    "#0d1117": "#ffffff",  # card background
    "#161b22": "#ebedf0",  # contribution cells
    "#30363d": "#d0d7de",  # borders
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
    "#1a7f37": "#6fdd8b",  # green glow
    "#800080": "#e2b6f2",  # purple glow
}
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def recolor(text: str, table: dict[str, str]) -> str:
    # one pass, so a color that is both a key and a value is never remapped twice
    return HEX.sub(lambda m: table.get(m.group(0).lower(), m.group(0)), text)


def fetch(url: str, headers: dict[str, str] | None = None, body: bytes | None = None) -> bytes:
    # a body turns the request into a POST
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "korrnik-profile-readme", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.read()


def esc(text: str, limit: int) -> str:
    # external text is clipped and escaped before it goes into an SVG
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return html.escape(text, quote=True)
