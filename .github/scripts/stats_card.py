"""Render the GitHub stats card for the profile README from the GitHub REST API."""

import json
import os
import sys
from pathlib import Path
from string import Template

from common import HEX, LIGHT, esc, fetch, recolor

USER = "KoRrNiK"
TOP = 5
COL_W = 180  # five stat columns over the full width, lined up with the social buttons
BAR_X, BAR_Y, BAR_W = 160, 132, 708
# the same color table GitHub uses; languages without a color there (e.g. ASL) stay gray, as on GitHub
LINGUIST = "https://raw.githubusercontent.com/github-linguist/linguist/main/lib/linguist/languages.yml"
FALLBACK = "#8b949e"

CARD = Template("""\
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="196" viewBox="0 0 900 196" role="img" aria-label="$aria">
  <defs>
    <clipPath id="card"><rect width="900" height="196" rx="16"/></clipPath>
    <clipPath id="bar"><rect x="160" y="132" width="708" height="10" rx="5"/></clipPath>
    <filter id="blur" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="45"/></filter>
    <pattern id="cells" width="16" height="16" patternUnits="userSpaceOnUse"><rect x="2.5" y="2.5" width="11" height="11" rx="2" fill="#161b22"/></pattern>
    <linearGradient id="line" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="900" y2="0">
      <stop offset="0" stop-color="#00c647" stop-opacity="0"/>
      <stop offset=".5" stop-color="#00c647"/>
      <stop offset="1" stop-color="#b42fc4" stop-opacity="0"/>
      <animateTransform attributeName="gradientTransform" type="translate" values="450 0;-450 0;450 0" dur="8s" repeatCount="indefinite"/>
    </linearGradient>
  </defs>
  <style>
    .mono { font-family: ui-monospace, SFMono-Regular, "Cascadia Code", Consolas, "Liberation Mono", Menlo, monospace; }
    .head { font-size: 12px; letter-spacing: 2px; fill: #6e7681; }
    .num { font: 800 32px "Segoe UI", -apple-system, "Helvetica Neue", Arial, sans-serif; fill: #e6edf3; }
    .lbl { font-size: 11px; letter-spacing: 1.5px; fill: #8b949e; }
    .lang { font-size: 12px; fill: #e6edf3; }
    .pct { fill: #8b949e; }
    .other { fill: #6e7681; }
    .in { animation: rise .6s ease-out both; }
    .seg { transform-box: fill-box; transform-origin: left; animation: grow .7s ease-out both; }
    @keyframes rise { from { opacity: 0; transform: translateY(8px); } }
    @keyframes grow { from { transform: scaleX(0); } }
    @media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
  </style>

  <g clip-path="url(#card)">
    <rect width="900" height="196" fill="#0d1117"/>
    <g filter="url(#blur)" opacity=".4">
      <circle cx="120" cy="196" r="90" fill="#1a7f37"/>
      <circle cx="820" cy="0" r="90" fill="#800080"/>
    </g>
    <rect width="900" height="196" fill="url(#cells)" fill-opacity=".5"/>
    <rect y="194" width="900" height="2" fill="url(#line)"/>
  </g>
  <rect x=".5" y=".5" width="899" height="195" rx="15.5" fill="none" stroke="#30363d"/>
  <g fill="#30363d">
    <rect x="180" y="30" width="1" height="64"/><rect x="360" y="30" width="1" height="64"/>
    <rect x="540" y="30" width="1" height="64"/><rect x="720" y="30" width="1" height="64"/>
    <rect x="24" y="110" width="852" height="1"/>
  </g>

  $stats
  <text class="mono head" x="32" y="141">LANGUAGES</text>
  <rect x="160" y="132" width="708" height="10" rx="5" fill="#161b22"/>
  <g clip-path="url(#bar)">$bar</g>
  $legend
</svg>
""")

# light is derived from dark; language colors are inserted after recoloring, so they stay linguist colors
THEMES = {"stats.svg": CARD, "stats-light.svg": Template(recolor(CARD.template, LIGHT))}


def api(path: str):
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return json.loads(fetch(f"https://api.github.com{path}", headers))


def linguist_colors(yaml_text: str) -> dict[str, str]:
    # languages.yml is flat enough to read without a YAML library: a top-level "Name:" line, then "  color:"
    colors: dict[str, str] = {}
    name = None
    for line in yaml_text.splitlines():
        if line[:1] not in ("", " ", "#", "-") and line.endswith(":"):
            name = line[:-1].strip("\"'")
        elif name and line.startswith("  color:"):
            value = line.split(":", 1)[1].strip().strip("\"'")
            if HEX.fullmatch(value):  # the value lands in an SVG attribute, so only plain hex gets through
                colors[name] = value
    return colors


def compact(value: int) -> str:
    return f"{value / 1000:.1f}k".replace(".0k", "k") if value >= 1000 else str(value)


def language_shares(languages: list[dict[str, int]]) -> list[tuple[str, float]]:
    # every repo weighs the same, so one big vendored codebase can't drown the rest
    shares: dict[str, float] = {}
    counted = [langs for langs in languages if sum(langs.values())]
    for langs in counted:
        total = sum(langs.values())
        for name, size in langs.items():
            shares[name] = shares.get(name, 0) + size / total
    if not counted:
        return []
    ranked = sorted(((name, share / len(counted)) for name, share in shares.items()), key=lambda item: -item[1])
    rest = sum(share for _, share in ranked[TOP:])
    return ranked[:TOP] + ([("other", rest)] if rest >= 0.005 else [])


def render(card: Template, stats: list[tuple[str, str]], langs: list[tuple[str, float]], colors: dict[str, str]) -> str:
    stat_cols = "\n  ".join(
        f'<g class="in" style="animation-delay:{i * 0.08:.2f}s">'
        f'<text class="num" x="{COL_W // 2 + i * COL_W}" y="66" text-anchor="middle">{esc(value, 6)}</text>'
        f'<text class="mono lbl" x="{COL_W // 2 + i * COL_W}" y="90" text-anchor="middle">{esc(label.upper(), 10)}</text></g>'
        for i, (value, label) in enumerate(stats)
    )
    bar, legend, x = [], [], float(BAR_X)
    for i, (name, share) in enumerate(langs):
        paint = 'class="seg other"' if name == "other" else f'class="seg" fill="{colors.get(name, FALLBACK)}"'
        bar.append(f'<rect {paint} x="{x:.1f}" y="{BAR_Y}" width="{BAR_W * share:.1f}" height="10" style="animation-delay:{0.3 + i * 0.08:.2f}s"/>')
        x += BAR_W * share
        lx, ly = 32 + i * 140, 174
        dot = 'class="other"' if name == "other" else f'fill="{colors.get(name, FALLBACK)}"'
        legend.append(
            f'<g class="in" style="animation-delay:{0.5 + i * 0.06:.2f}s"><circle {dot} cx="{lx + 5}" cy="{ly - 4}" r="5"/>'
            f'<text class="mono lang" x="{lx + 16}" y="{ly}">{esc(name, 12)}<tspan class="pct"> {round(share * 100)}%</tspan></text></g>'
        )
    aria = "GitHub: " + ", ".join(f"{v} {l}" for v, l in stats) + ". Top languages: " + ", ".join(f"{n} {round(s * 100)}%" for n, s in langs)
    return card.substitute(aria=esc(aria, 300), stats=stat_cols, bar="".join(bar), legend="\n  ".join(legend))


def main(out_dir: str) -> None:
    user = api(f"/users/{USER}")
    repos = [repo for repo in api(f"/users/{USER}/repos?per_page=100&type=owner") if not repo["fork"]]
    stats = [
        (compact(user["public_repos"]), "repos"),
        (compact(sum(repo["stargazers_count"] for repo in repos)), "stars"),
        (compact(api(f"/search/commits?q=author:{USER}&per_page=1")["total_count"]), "commits"),
        (compact(user["followers"]), "followers"),
        (user["created_at"][:4], "since"),
    ]
    langs = language_shares([api(f"/repos/{USER}/{repo['name']}/languages") for repo in repos])
    colors = linguist_colors(fetch(LINGUIST).decode("utf-8"))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, card in THEMES.items():
        (out / name).write_text(render(card, stats, langs, colors), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: stats_card.py <output-dir>")
    main(sys.argv[1])
