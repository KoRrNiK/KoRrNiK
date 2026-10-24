"""Regenerate assets/*-light.svg from the dark originals; run it after editing any asset.

usage: python .github/scripts/light_assets.py
"""

from pathlib import Path

from common import LIGHT, recolor

ASSETS = Path(__file__).resolve().parents[2] / "assets"


def main() -> None:
    for dark in sorted(ASSETS.glob("*.svg")):
        if dark.stem.endswith("-light"):
            continue
        light = dark.with_name(f"{dark.stem}-light.svg")
        light.write_text(recolor(dark.read_text(encoding="utf-8"), LIGHT), encoding="utf-8", newline="\n")
        print(f"{dark.name} -> {light.name}")


if __name__ == "__main__":
    main()
