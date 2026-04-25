"""Simple client-side autopilot for demo matches."""

from shared.constants import (
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    GRID_COLS,
    GRID_ROWS,
    OPPOSITE,
)

DIRECTION_DELTA = {
    DIR_UP: (0, -1),
    DIR_DOWN: (0, 1),
    DIR_LEFT: (-1, 0),
    DIR_RIGHT: (1, 0),
}

ALL_DIRECTIONS = [DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]


def choose_auto_move(state: dict, username: str) -> str | None:
    snakes = state.get("snakes", {})
    snake = snakes.get(username)
    if not snake or not snake.get("alive", True):
        return None

    body = [tuple(cell) for cell in snake.get("body", [])]
    if not body:
        return None

    current = snake.get("direction", DIR_RIGHT)
    candidates = [current] + [
        direction
        for direction in ALL_DIRECTIONS
        if direction not in {current, OPPOSITE.get(current)}
    ]

    occupied = _occupied_cells(state, username)
    pies = state.get("pies", [])
    other_heads = {
        tuple(other.get("body", [[-99, -99]])[0])
        for name, other in snakes.items()
        if name != username and other.get("alive", True) and other.get("body")
    }

    best_direction = current
    best_score = float("-inf")
    for direction in candidates:
        score = _score_direction(
            head=body[0],
            direction=direction,
            current=current,
            snake=snake,
            occupied=occupied,
            pies=pies,
            other_heads=other_heads,
        )
        if score > best_score:
            best_score = score
            best_direction = direction
    return best_direction


def _occupied_cells(state: dict, username: str) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for name, snake in state.get("snakes", {}).items():
        if not snake.get("alive", True):
            continue
        body = [tuple(cell) for cell in snake.get("body", [])]
        if name == username:
            occupied.update(body[1:])
        else:
            occupied.update(body)
    occupied.update((obs["col"], obs["row"]) for obs in state.get("obstacles", []))
    return occupied


def _score_direction(
    head: tuple[int, int],
    direction: str,
    current: str,
    snake: dict,
    occupied: set[tuple[int, int]],
    pies: list[dict],
    other_heads: set[tuple[int, int]],
) -> float:
    next_head = _step(head, direction)

    if not _in_bounds(next_head):
        return -100000.0
    if next_head in occupied:
        return -80000.0

    score = 0.0
    score += 4.0 if direction == current else 0.0
    score += _free_neighbors(next_head, occupied) * 14.0
    score += _straight_run(next_head, direction, occupied) * 5.0
    score -= _distance_to_center(next_head) * 0.8

    if next_head in other_heads:
        score -= 120.0

    pie_score = _best_pie_score(next_head, pies, bool(snake.get("shielded", False)), int(snake.get("health", 100)))
    score += pie_score
    return score


def _best_pie_score(
    head: tuple[int, int],
    pies: list[dict],
    shielded: bool,
    health: int,
) -> float:
    if not pies:
        return 0.0

    best = float("-inf")
    for pie in pies:
        pie_type = pie.get("type", "regular")
        target = (pie["col"], pie["row"])
        distance = _manhattan(head, target)

        reward = {
            "regular": 22.0,
            "golden": 38.0,
            "shield": 30.0 if not shielded else 6.0,
            "poison": -30.0 if health < 95 else -12.0,
        }.get(pie_type, 0.0)

        score = reward - distance * 3.0
        if score > best:
            best = score
    return best


def _free_neighbors(cell: tuple[int, int], occupied: set[tuple[int, int]]) -> int:
    return sum(
        1
        for direction in ALL_DIRECTIONS
        if _in_bounds(_step(cell, direction)) and _step(cell, direction) not in occupied
    )


def _straight_run(cell: tuple[int, int], direction: str, occupied: set[tuple[int, int]], limit: int = 6) -> int:
    steps = 0
    current = cell
    while steps < limit:
        current = _step(current, direction)
        if not _in_bounds(current) or current in occupied:
            break
        steps += 1
    return steps


def _distance_to_center(cell: tuple[int, int]) -> int:
    center = (GRID_COLS // 2, GRID_ROWS // 2)
    return _manhattan(cell, center)


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step(cell: tuple[int, int], direction: str) -> tuple[int, int]:
    dc, dr = DIRECTION_DELTA[direction]
    return cell[0] + dc, cell[1] + dr


def _in_bounds(cell: tuple[int, int]) -> bool:
    return 0 <= cell[0] < GRID_COLS and 0 <= cell[1] < GRID_ROWS
