"""Render the contribution snake for the profile README from the GitHub GraphQL calendar."""

import sys
from pathlib import Path
from string import Template

from common import LIGHT, glow, graphql, recolor

USER = "KoRrNiK"
CALENDAR_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { weeks { contributionDays { date weekday contributionCount contributionLevel } } }
    }
  }
}
"""
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
# GitHub's own dark contribution colors for levels 0-4; common.LIGHT maps them to the light ones
COLORS = ("#161b22", "#0e4429", "#006d32", "#26a641", "#39d353")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
PITCH, CELL, TOP = 16, 12, 62  # grid pitch, drawn cell size, grid top
LENGTH = 4  # snake segments
SWEEP = 1  # extra columns the snake may look ahead, so each level is eaten as one sweep across the year
STEP = 0.1  # seconds per cell, as in Platane/snk
# like snk, the snake lives just above the top-left corner (hidden by the grid clip), lying to the right,
# and comes back to exactly that spot, so the end of the loop matches its start
HOME = [(k, -1) for k in range(LENGTH)]
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))

Cell = tuple[int, int]

CARD = Template("""\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="900" height="196" viewBox="0 0 900 196" role="img" aria-label="$aria">
  <defs>
    <clipPath id="card"><rect width="900" height="196" rx="16"/></clipPath>
    <clipPath id="grid"><rect x="$left" y="62" width="$grid_width" height="112"/></clipPath>
    <filter id="blur" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="45"/></filter>
    <radialGradient id="halo"><stop offset="0" stop-color="#d670e0" stop-opacity=".45"/><stop offset="1" stop-color="#d670e0" stop-opacity="0"/></radialGradient>
    <linearGradient id="line" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="900" y2="0">
      <stop offset="0" stop-color="#00c647" stop-opacity="0"/>
      <stop offset=".5" stop-color="#00c647"/>
      <stop offset="1" stop-color="#b42fc4" stop-opacity="0"/>
      <animateTransform attributeName="gradientTransform" type="translate" values="-450 0;450 0;-450 0" dur="8s" repeatCount="indefinite"/>
    </linearGradient>
    <path id="route" d="$route"/>
  </defs>
  <style>
    .mono { font-family: ui-monospace, SFMono-Regular, "Cascadia Code", Consolas, "Liberation Mono", Menlo, monospace; }
    .head { font-size: 12px; letter-spacing: 2px; fill: #6e7681; }
    .num { font-size: 13px; font-weight: 700; letter-spacing: 0; fill: #e6edf3; }
    .month { font-size: 10px; fill: #6e7681; }
    /* every eaten cell gets its own keyframe at the moment the head reaches it */
    .eat { animation-duration: ${loop}s; animation-timing-function: step-end; animation-iteration-count: infinite; }
    $keyframes
    .glow { animation: breathe 6s ease-in-out infinite alternate; }
    @keyframes breathe { to { opacity: .3; } }
    @media (prefers-reduced-motion: reduce) { .eat, .glow { animation: none; } .snake { display: none; } }
  </style>

  <g clip-path="url(#card)">
    <rect width="900" height="196" fill="#0d1117"/>
    $glow
    <rect y="194" width="900" height="2" fill="url(#line)"/>
  </g>
  <rect x=".5" y=".5" width="899" height="195" rx="15.5" fill="none" stroke="#30363d"/>

  <text class="mono head" x="$text_left" y="32">LAST 12 MONTHS</text>
  <text class="mono head" x="$text_right" y="32" text-anchor="end">LONGEST STREAK <tspan class="num">$longest</tspan><tspan dx="16">CURRENT </tspan><tspan class="num">$current</tspan></text>
  $months
  $cells
  <g class="snake" clip-path="url(#grid)">
  $segments
  </g>
</svg>
""".replace("$glow", glow("snake")))


def shortest(body: list[Cell], targets: set[Cell], width: int, walls: set[Cell] | None = None) -> list[Cell]:
    """Moves to the nearest target around `walls`. body[k] stays occupied for the first len(body) - 1 - k moves,
    so a shortest path never runs into the snake's own body."""
    busy = {cell: len(body) - 1 - k for k, cell in enumerate(body)}
    busy.update(dict.fromkeys(walls or (), float("inf")))
    prev: dict[Cell, Cell] = {}
    seen, layer, moves = {body[0]}, [body[0]], 0
    while layer:
        moves += 1
        nxt = []
        for x, y in layer:
            for dx, dy in DIRS:
                cell = (x + dx, y + dy)
                if cell in seen or not (0 <= cell[0] < width and 0 <= cell[1] < 7) or busy.get(cell, -1) >= moves:
                    continue
                seen.add(cell)
                prev[cell] = (x, y)
                nxt.append(cell)
        found = [cell for cell in nxt if cell in targets]
        if found:
            cell, steps = min(found), []  # min() keeps the output deterministic
            while cell != body[0]:
                steps.append(cell)
                cell = prev[cell]
            return steps[::-1]
        layer = nxt
    return []


def route(levels: dict[Cell, int], width: int) -> tuple[list[Cell], dict[Cell, int]]:
    """Head positions from HOME back to HOME, and the move at which each cell is eaten.

    Cells are eaten strictly from the lowest level to the highest, each level as one sweep across the year
    in alternating directions. Bigger cells are walked around, or crossed without being eaten if there is
    no way around. When everything is eaten, the snake goes back along the edge of the grid to the
    top-left door and climbs home."""
    body = list(HOME)
    path: list[Cell] = [body[0]]
    eaten: dict[Cell, int] = {}
    left = {cell: level for cell, level in levels.items() if level}

    def walk(steps: list[Cell], level: int = 0) -> None:
        nonlocal body
        for cell in steps:
            body = [cell] + body[:-1]
            path.append(cell)
            if 0 < left.get(cell, 0) <= level:
                eaten[cell] = len(path) - 1
                del left[cell]

    for n, level in enumerate(sorted(set(left.values()))):
        rightward = n % 2 == 0
        while todo := {cell for cell, lvl in left.items() if lvl == level}:
            edge = min(x for x, _ in todo) if rightward else max(x for x, _ in todo)
            window = {cell for cell in todo if abs(cell[0] - edge) <= SWEEP}
            bigger = {cell for cell, lvl in left.items() if lvl > level}
            steps = shortest(body, window, width, bigger) or shortest(body, window, width)
            if not steps:
                # a 4-cell snake on an open grid can always reach its tail, so this means a bug; the old card stays published
                sys.exit("the snake got stuck")
            walk(steps, level)

    # back along the edge of the grid, the shorter way round, to the door under HOME's tail end
    ring = ([(x, 0) for x in range(width)] + [(width - 1, y) for y in range(1, 7)]
            + [(x, 6) for x in range(width - 2, -1, -1)] + [(0, y) for y in range(5, 0, -1)])
    door = (LENGTH - 1, 0)
    if body[0] not in ring:
        walk(shortest(body, set(ring), width))
    start, goal = ring.index(body[0]), ring.index(door)
    ways = []
    for step in (1, -1):
        cells, i = [], start
        while i != goal:
            i = (i + step) % len(ring)
            cells.append(ring[i])
        if not cells or cells[0] != body[1]:
            ways.append(cells)
    walk(min(ways, key=len))
    walk([(LENGTH - 1 - k, -1) for k in range(LENGTH)])  # up through the door and left into HOME
    return path, eaten


def streaks(days: list[dict]) -> tuple[int, int]:
    """Longest and current run of days with contributions; an empty today doesn't break the current run yet."""
    counts = [day["contributionCount"] for day in days]
    longest = run = 0
    for count in counts:
        run = run + 1 if count else 0
        longest = max(longest, run)
    if counts and not counts[-1]:
        counts.pop()
    current = 0
    for count in reversed(counts):
        if not count:
            break
        current += 1
    return longest, current


def render(weeks: list[list[dict]]) -> str:
    width = len(weeks)
    left = (900 - width * PITCH) // 2
    levels = {(w, day["weekday"]): LEVELS[day["contributionLevel"]] for w, week in enumerate(weeks) for day in week}
    path, eaten_at = route(levels, width)
    moves = len(path) - 1
    eaten = {cell: move / moves for cell, move in eaten_at.items()}

    def center(cell: Cell) -> tuple[int, int]:
        return left + cell[0] * PITCH + PITCH // 2, TOP + cell[1] * PITCH + PITCH // 2

    cells, keyframes = [], []
    for n, (cell, level) in enumerate(sorted(levels.items())):
        x, y = center(cell)
        eat = ""
        if cell in eaten:
            eat = f' class="eat" style="animation-name:e{n}"'
            keyframes.append(f"@keyframes e{n} {{ {eaten[cell] * 100:.3f}% {{ fill: {COLORS[0]}; }} }}")
        cells.append(f'<rect x="{x - CELL // 2}" y="{y - CELL // 2}" width="{CELL}" height="{CELL}" rx="2.5" fill="{COLORS[level]}"{eat}/>')

    x, y = center(path[0])
    route_d = [f"M{x} {y}"]
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        route_d.append(f"h{(bx - ax) * PITCH}" if ay == by else f"v{(by - ay) * PITCH}")

    loop = f"{moves * STEP:.1f}"
    segments = []
    for k in reversed(range(LENGTH)):  # tail first, so the head is drawn on top
        size = 12 - k
        fill = "#d670e0" if k == 0 else "#b42fc4"
        halo = '<circle r="14" fill="url(#halo)"/>' if k == 0 else ""
        segments.append(
            f'<g opacity="{1 - k * 0.18:.2f}">{halo}'
            f'<rect x="{-size / 2}" y="{-size / 2}" width="{size}" height="{size}" rx="3" fill="{fill}"/>'
            f'<animateMotion dur="{loop}s" begin="{k * STEP:.1f}s" repeatCount="indefinite"><mpath xlink:href="#route"/></animateMotion></g>'
        )

    labels, last = [], -3
    for w in range(1, width - 1):
        month = int(weeks[w][0]["date"][5:7])
        if month != int(weeks[w - 1][0]["date"][5:7]) and w - last >= 3:
            labels.append(f'<text class="mono month" x="{left + w * PITCH + 2}" y="54">{MONTHS[month - 1]}</text>')
            last = w

    longest, current = streaks([day for week in weeks for day in week])
    return CARD.substitute(
        aria=f"Contribution snake eating the last 12 months. Longest streak {longest} days, current streak {current} days.",
        left=left,
        grid_width=width * PITCH,
        route="".join(route_d),
        loop=loop,
        keyframes="\n    ".join(keyframes),
        text_left=left + 2,
        text_right=left + width * PITCH - 2,
        longest=longest,
        current=current,
        months="\n  ".join(labels),
        cells="\n  ".join(cells),
        segments="\n  ".join(segments),
    )


def main(out_dir: str) -> None:
    calendar = graphql(CALENDAR_QUERY, {"login": USER})["user"]["contributionsCollection"]["contributionCalendar"]
    svg = render([week["contributionDays"] for week in calendar["weeks"]])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "snake.svg").write_text(svg, encoding="utf-8")
    # no external text in this card, so the whole output can be recolored
    (out / "snake-light.svg").write_text(recolor(svg, LIGHT), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: snake_card.py <output-dir>")
    main(sys.argv[1])
