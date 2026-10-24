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
PITCH, CELL = 16, 12  # grid pitch and drawn cell size
TOP, BAR_Y = 74, 210  # grid top (a walkable one-cell margin runs all around the grid) and the eaten-cells bar
LENGTH = 4  # snake segments
SWEEP = 1  # extra columns the snake may look ahead, so each level is eaten as one sweep across the year
STEP = 0.1  # seconds per cell, as in Platane/snk
# every loop starts with a reset before the snake sets off: the bar empties and the cells grow back in a wave
RESET, WAVE, POP, DRAIN = 2.5, 1.6, 0.35, 0.5  # reset length, wave across the year, one cell's pop, bar emptying
# Like snk, the snake lives in the top margin above the first week and comes back to exactly the same spot,
# so the end of the loop matches its start. It lies either to the right or down the left margin,
# whichever makes the way home shorter.
HOMES = ([(k, -1) for k in range(LENGTH)], [(0, -1)] + [(-1, k - 2) for k in range(1, LENGTH)])
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))

Cell = tuple[int, int]

CARD = Template("""\
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="232" viewBox="0 0 900 232" role="img" aria-label="$aria">
  <defs>
    <clipPath id="card"><rect width="900" height="232" rx="16"/></clipPath>
    <clipPath id="area"><rect x="$area_left" y="58" width="$area_width" height="144"/></clipPath>
    <clipPath id="bar"><rect x="$left" y="210" width="$grid_width" height="8" rx="4"/></clipPath>
    <filter id="blur" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="45"/></filter>
    <radialGradient id="halo"><stop offset="0" stop-color="#d670e0" stop-opacity=".45"/><stop offset="1" stop-color="#d670e0" stop-opacity="0"/></radialGradient>
    <linearGradient id="line" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="900" y2="0">
      <stop offset="0" stop-color="#00c647" stop-opacity="0"/>
      <stop offset=".5" stop-color="#00c647"/>
      <stop offset="1" stop-color="#b42fc4" stop-opacity="0"/>
      <animateTransform attributeName="gradientTransform" type="translate" values="-450 0;450 0;-450 0" dur="8s" repeatCount="indefinite"/>
    </linearGradient>
  </defs>
  <style>
    .mono { font-family: ui-monospace, SFMono-Regular, "Cascadia Code", Consolas, "Liberation Mono", Menlo, monospace; }
    .head { font-size: 12px; letter-spacing: 2px; fill: #6e7681; }
    .num { font-size: 13px; font-weight: 700; letter-spacing: 0; fill: #e6edf3; }
    .month { font-size: 10px; fill: #6e7681; }
    /* every cell and every bar segment gets its own keyframes, timed to the reset and to the snake's bites */
    .eat, .fill { animation-duration: ${loop}s; animation-iteration-count: infinite; }
    .eat { transform-box: fill-box; transform-origin: center; animation-timing-function: linear; }
    .fill { transform-box: fill-box; transform-origin: left; transform: scaleX(0); animation-timing-function: step-end; }
    $keyframes
    .glow { animation: breathe 6s ease-in-out infinite alternate; }
    @keyframes breathe { to { opacity: .3; } }
    @media (prefers-reduced-motion: reduce) { .eat, .glow { animation: none; } .fill { animation: none; transform: none; } .snake { display: none; } }
  </style>

  <g clip-path="url(#card)">
    <rect width="900" height="232" fill="#0d1117"/>
    $glow
    <rect y="230" width="900" height="2" fill="url(#line)"/>
  </g>
  <rect x=".5" y=".5" width="899" height="231" rx="15.5" fill="none" stroke="#30363d"/>

  <text class="mono head" x="$text_left" y="30">LAST 12 MONTHS</text>
  <text class="mono head" x="$text_right" y="30" text-anchor="end">LONGEST STREAK <tspan class="num">$longest</tspan><tspan dx="16">CURRENT </tspan><tspan class="num">$current</tspan></text>
  $months
  $cells
  <rect x="$left" y="210" width="$grid_width" height="8" rx="4" fill="#161b22"/>
  <g clip-path="url(#bar)">$bar</g>
  <g class="snake" clip-path="url(#area)">
  $segments
  </g>
</svg>
""".replace("$glow", glow("snake")))


def search(body: list[Cell], width: int, walls: set[Cell] | None = None) -> tuple[dict[Cell, int], dict[Cell, Cell]]:
    """Breadth-first search over the grid and its margin: moves to every reachable cell and where each came from.
    body[k] stays occupied for the first len(body) - 1 - k moves, so no path runs into the snake itself."""
    busy = {cell: len(body) - 1 - k for k, cell in enumerate(body)}
    busy.update(dict.fromkeys(walls or (), float("inf")))
    dist, prev = {body[0]: 0}, {}
    layer, moves = [body[0]], 0
    while layer:
        moves += 1
        nxt = []
        for x, y in layer:
            for dx, dy in DIRS:
                cell = (x + dx, y + dy)
                if cell in dist or not (-1 <= cell[0] <= width and -1 <= cell[1] <= 7) or busy.get(cell, -1) >= moves:
                    continue
                dist[cell], prev[cell] = moves, (x, y)
                nxt.append(cell)
        layer = nxt
    return dist, prev


def steps_to(prev: dict[Cell, Cell], head: Cell, cell: Cell) -> list[Cell]:
    steps = []
    while cell != head:
        steps.append(cell)
        cell = prev[cell]
    return steps[::-1]


def shortest(body: list[Cell], targets: set[Cell], width: int, walls: set[Cell] | None = None) -> list[Cell]:
    """Moves to the nearest reachable target; ties go to the smallest cell, so the output is deterministic."""
    dist, prev = search(body, width, walls)
    reachable = [cell for cell in targets if cell in dist]
    return steps_to(prev, body[0], min(reachable, key=lambda cell: (dist[cell], cell))) if reachable else []


def lap(levels: dict[Cell, int], width: int, home: list[Cell]) -> tuple[list[Cell], dict[Cell, int]]:
    """One loop from `home` back to it: head positions and the move at which each cell is eaten.

    Cells are eaten strictly from the lowest level to the highest, each level as one sweep across the year
    in alternating directions. Uneaten cells are walls: only if there is no way round may the snake cross
    cells of the level it is eating (eating them), and as a last resort bigger ones (without eating them).
    Then it goes back along the outer margin, the shorter way round, and lies down at home again."""
    body, path, eaten = list(home), [home[0]], {}
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
            steps = (shortest(body, window, width, set(left) - window)
                     or shortest(body, window, width, bigger)
                     or shortest(body, window, width))
            if not steps:
                # a 4-cell snake on an open grid can always reach its tail, so this means a bug; the old card stays published
                sys.exit("the snake got stuck")
            walk(steps, level)

    # the outer margin, clockwise from the top-left corner
    ring = ([(x, -1) for x in range(-1, width + 1)] + [(width, y) for y in range(8)]
            + [(x, 7) for x in range(width - 1, -2, -1)] + [(-1, y) for y in range(6, -1, -1)])
    step = -1 if home[1] == (1, -1) else 1  # come in from the side the tail lies on
    goal = ring.index(home[0])
    approach = {ring[(goal - step * k) % len(ring)] for k in range(LENGTH)}  # home and the cells right before it
    dist, prev = search(body, width, approach)
    entry = min((cell for cell in ring if cell in dist and cell not in approach),
                key=lambda cell: (dist[cell] + (goal - ring.index(cell)) * step % len(ring), cell))
    walk(steps_to(prev, body[0], entry))
    i = ring.index(entry)
    while i != goal:
        i = (i + step) % len(ring)
        walk([ring[i]])
    return path, eaten


def route(levels: dict[Cell, int], width: int) -> tuple[list[Cell], dict[Cell, int]]:
    """The shorter loop of the two ways of lying at home."""
    return min((lap(levels, width, home) for home in HOMES), key=lambda run: len(run[0]))


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
    path, eaten = route(levels, width)
    moves = len(path) - 1
    loop = round(RESET + moves * STEP, 1)

    def at(seconds: float) -> str:
        return f"{seconds / loop * 100:.3f}%"

    def bite(move: int) -> float:
        return RESET + move * STEP

    def center(cell: Cell) -> tuple[int, int]:
        return left + cell[0] * PITCH + PITCH // 2, TOP + cell[1] * PITCH + PITCH // 2

    # a coloured cell sits empty during the reset until the wave reaches its week, pops back in, and empties again when eaten
    cells, keyframes = [], []
    empty = COLORS[0]
    for n, (cell, level) in enumerate(sorted(levels.items())):
        x, y = center(cell)
        grow = ""
        if cell in eaten:
            pop, eat, full = 0.3 + cell[0] / width * WAVE, bite(eaten[cell]), COLORS[level]
            grow = f' class="eat" style="animation-name:e{n}"'
            keyframes.append(
                f"@keyframes e{n} {{ 0%, {at(pop - 0.01)} {{ fill: {empty}; transform: scale(1); }} "
                f"{at(pop)} {{ fill: {full}; transform: scale(.2); }} "
                f"{at(pop + POP * 0.6)} {{ fill: {full}; transform: scale(1.2); }} "
                f"{at(pop + POP)}, {at(eat - 0.01)} {{ fill: {full}; transform: scale(1); }} "
                f"{at(eat)}, 100% {{ fill: {empty}; transform: scale(1); }} }}"
            )
        cells.append(f'<rect x="{x - CELL // 2}" y="{y - CELL // 2}" width="{CELL}" height="{CELL}" rx="2.5" fill="{COLORS[level]}"{grow}/>')

    # one bar segment per level, as wide as its share of the cells: drained by the reset, then growing with every bite like in snk
    bar, x = [], float(left)
    for level in range(1, 5):
        bites = sorted(move for cell, move in eaten.items() if levels[cell] == level)
        if not bites:
            continue
        share = width * PITCH * len(bites) / len(eaten)
        bar.append(f'<rect class="fill" x="{x:.1f}" y="{BAR_Y}" width="{share + 0.5:.1f}" height="8" fill="{COLORS[level]}" style="animation-name:f{level}"/>')
        growth = " ".join(f"{at(bite(move))} {{ transform: scaleX({k / len(bites):.4f}); }}" for k, move in enumerate(bites, 1))
        keyframes.append(
            f"@keyframes f{level} {{ 0% {{ transform: scaleX(1); animation-timing-function: ease-in; }} "
            f"{at(DRAIN)} {{ transform: scaleX(0); animation-timing-function: step-end; }} {growth} }}"
        )
        x += share

    # every segment gets the loop rotated to start where it lies at home, so all of them wait out the reset
    # in place and then move off together at the same constant speed
    segments = []
    for k in reversed(range(LENGTH)):  # tail first, so the head is drawn on top
        cells_k = path[moves - k:] + path[1 : moves - k + 1]
        x, y = center(cells_k[0])
        d = f"M{x} {y}" + "".join(
            f"h{(bx - ax) * PITCH}" if ay == by else f"v{(by - ay) * PITCH}" for (ax, ay), (bx, by) in zip(cells_k, cells_k[1:])
        )
        size = 12 - k
        fill = "#d670e0" if k == 0 else "#b42fc4"
        halo = '<circle r="14" fill="url(#halo)"/>' if k == 0 else ""
        segments.append(
            f'<g opacity="{1 - k * 0.18:.2f}">{halo}'
            f'<rect x="{-size / 2}" y="{-size / 2}" width="{size}" height="{size}" rx="3" fill="{fill}"/>'
            f'<animateMotion dur="{loop}s" repeatCount="indefinite" calcMode="linear" keyTimes="0;{RESET / loop:.4f};1" keyPoints="0;0;1" path="{d}"/></g>'
        )

    labels, last = [], -3
    for w in range(1, width - 1):
        month = int(weeks[w][0]["date"][5:7])
        if month != int(weeks[w - 1][0]["date"][5:7]) and w - last >= 3:
            labels.append(f'<text class="mono month" x="{left + w * PITCH + 2}" y="50">{MONTHS[month - 1]}</text>')
            last = w

    longest, current = streaks([day for week in weeks for day in week])
    return CARD.substitute(
        aria=f"Contribution snake eating the last 12 months. Longest streak {longest} days, current streak {current} days.",
        left=left,
        area_left=left - PITCH,
        area_width=(width + 2) * PITCH,
        grid_width=width * PITCH,
        loop=loop,
        keyframes="\n    ".join(keyframes),
        text_left=left + 2,
        text_right=left + width * PITCH - 2,
        longest=longest,
        current=current,
        months="\n  ".join(labels),
        cells="\n  ".join(cells),
        bar="".join(bar),
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
