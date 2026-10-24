"""Regenerate assets/*-light.svg from the dark originals; run it after editing any asset.

usage: python .github/scripts/light_assets.py
"""

from pathlib import Path

from common import LIGHT, recolor

ASSETS = Path(__file__).resolve().parents[2] / "assets"
# the terminal title bar shares its dark color with the contribution cells but should stay lighter
OVERRIDES = {"terminal.svg": {"#161b22": "#f6f8fa"}}


def main() -> None:
    for dark in sorted(ASSETS.glob("*.svg")):
        if dark.stem.endswith("-light"):
            continue
        light = dark.with_name(f"{dark.stem}-light.svg")
        table = {**LIGHT, **OVERRIDES.get(dark.name, {})}
        light.write_text(recolor(dark.read_text(encoding="utf-8"), table), encoding="utf-8", newline="\n")
        print(f"{dark.name} -> {light.name}")


if __name__ == "__main__":
    main()
