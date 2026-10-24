"""Render the Discord presence part of the social box from Lanyard data."""

import base64
import json
import sys
from pathlib import Path
from string import Template

from common import LIGHT, esc, fetch, glow, recolor

USER_ID = "292279578389643264"
IDLE_TEXT = "probably doing something else..."

# discord_status -> (color, label)
STATUS = {
    "online": ("#3fb950", "online"),
    "idle": ("#d29922", "idle"),
    "dnd": ("#f85149", "do not disturb"),
    "offline": ("#6e7681", "offline"),
}
VERBS = {0: "playing", 1: "streaming", 2: "listening to", 3: "watching", 5: "competing in"}

# left 540px of a 900px box; the social buttons (assets/<name>.svg) fill the remaining 5 x 72px,
# so the pattern, the glow and the bottom line use box-wide coordinates to stay seamless across the images
CARD = Template("""\
<svg xmlns="http://www.w3.org/2000/svg" width="540" height="112" viewBox="0 0 540 112" role="img" aria-label="$aria">
  <defs>
    <clipPath id="card"><rect width="572" height="112" rx="16"/></clipPath>
    <clipPath id="avatar"><circle cx="64" cy="56" r="32"/></clipPath>
    <filter id="blur" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="45"/></filter>
    <filter id="halo" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="16"/></filter>
    <pattern id="cells" width="16" height="16" patternUnits="userSpaceOnUse"><rect x="2.5" y="2.5" width="11" height="11" rx="2" fill="#8b949e"/></pattern>
    <linearGradient id="line" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="900" y2="0">
      <stop offset="0" stop-color="#00c647" stop-opacity="0"/>
      <stop offset=".5" stop-color="#00c647"/>
      <stop offset="1" stop-color="#b42fc4" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <style>
    .name { font: 800 22px "Segoe UI", -apple-system, "Helvetica Neue", Arial, sans-serif; fill: #e6edf3; }
    .mono { font-family: ui-monospace, SFMono-Regular, "Cascadia Code", Consolas, "Liberation Mono", Menlo, monospace; }
    .pulse { transform-origin: 88px 80px; animation: pulse 2s ease-out infinite; }
    .glow { animation: breathe 6s ease-in-out infinite alternate; }
    @keyframes pulse { from { opacity: .6; transform: scale(1); } to { opacity: 0; transform: scale(2.2); } }
    @keyframes breathe { to { opacity: .3; } }
    @media (prefers-reduced-motion: reduce) { .pulse { display: none; } * { animation: none !important; } }
  </style>

  <g clip-path="url(#card)">
    $glow
    <g filter="url(#halo)" opacity=".5"><circle cx="64" cy="56" r="34" fill="$color"/></g>
    <rect width="540" height="112" fill="url(#cells)" fill-opacity=".04"/>
    <rect y="110" width="540" height="2" fill="url(#line)"/>
  </g>
  <rect x=".5" y=".5" width="571" height="111" rx="15.5" fill="none" stroke="#8b949e" stroke-opacity=".3"/>
  <rect x="539" y="16" width="1" height="80" fill="#8b949e" fill-opacity=".3"/>

  <image x="32" y="24" width="64" height="64" clip-path="url(#avatar)" href="data:image/png;base64,$avatar"/>
  <circle cx="64" cy="56" r="32.5" fill="none" stroke="#8b949e" stroke-opacity=".3"/>
  $pulse
  <circle cx="88" cy="80" r="9" fill="$color" stroke="#0d1117" stroke-width="4"/>

  <text class="name" x="116" y="42">$name</text>
  <text class="mono" x="116" y="66" font-size="13"><tspan fill="$color">$label</tspan><tspan fill="#6e7681"> · @$username</tspan></text>
  <text class="mono" x="116" y="90" font-size="13"><tspan fill="#6e7681" font-size="11" letter-spacing="1.5">$verb</tspan><tspan fill="#e6edf3"> $activity</tspan></text>
</svg>
""".replace("$glow", glow("social")))


# output file -> (template, status palette); light is derived from dark so both stay in sync,
# and only the template is recolored, never the Discord text that goes into it
THEMES = {
    "discord.svg": (CARD, STATUS),
    "discord-light.svg": (
        Template(recolor(CARD.template, LIGHT)),
        {key: (recolor(color, LIGHT), label) for key, (color, label) in STATUS.items()},
    ),
}


def current_activity(data: dict) -> tuple[str, str]:
    if data.get("listening_to_spotify") and data.get("spotify"):
        song = data["spotify"]
        return "listening to", f"{song.get('song', '')} · {song.get('artist', '')}"
    activities = data.get("activities") or []
    for act in activities:
        if act.get("type") in VERBS and act.get("name"):
            return VERBS[act["type"]], act["name"]
    for act in activities:
        if act.get("type") == 4 and act.get("state"):
            return "status", act["state"]
    return "currently", IDLE_TEXT


def render(data: dict, avatar_png: bytes, card: Template = CARD, status: dict = STATUS) -> str:
    user = data["discord_user"]
    color, label = status.get(data.get("discord_status"), status["offline"])
    verb, activity = current_activity(data)
    name = user.get("global_name") or user["username"]
    pulse = "" if label == "offline" else f'<circle class="pulse" cx="88" cy="80" r="9" fill="{color}"/>'
    return card.substitute(
        aria=esc(f"Discord: {name}, {label}. {verb} {activity}", 200),
        color=color,
        label=label,
        avatar=base64.b64encode(avatar_png).decode(),
        pulse=pulse,
        name=esc(name, 24),
        username=esc(user["username"], 32),
        verb=esc(verb.upper(), 20),
        activity=esc(activity, 34),
    )


def main(out_dir: str) -> None:
    payload = json.loads(fetch(f"https://api.lanyard.rest/v1/users/{USER_ID}"))
    if not payload.get("success"):
        # failing the run keeps the previously published card instead of replacing it with garbage
        sys.exit(f"lanyard error: {payload}")
    data = payload["data"]
    user = data["discord_user"]
    if user.get("avatar"):
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png?size=128"
    else:
        avatar_url = f"https://cdn.discordapp.com/embed/avatars/{(int(user['id']) >> 22) % 6}.png"
    avatar = fetch(avatar_url)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, (card, status) in THEMES.items():
        (out / name).write_text(render(data, avatar, card, status), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: discord_card.py <output-dir>")
    main(sys.argv[1])
