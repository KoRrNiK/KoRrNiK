"""Publish the static assets (header, terminal, social buttons) in the current season's colors, dark and light.

usage: python .github/scripts/static_assets.py <output-dir>
"""

import sys
from pathlib import Path

from common import paint, season

ASSETS = Path(__file__).resolve().parents[2] / "assets"


def main(out_dir: str) -> None:
    holiday = season()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sources = sorted(ASSETS.glob("*.svg"))
    for source in sources:
        svg = source.read_text(encoding="utf-8")
        for name, light in ((source.name, False), (f"{source.stem}-light.svg", True)):
            (out / name).write_text(paint(svg, light, holiday), encoding="utf-8")
    print(f"{len(sources)} assets, palette: {holiday or 'default'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: static_assets.py <output-dir>")
    main(sys.argv[1])
