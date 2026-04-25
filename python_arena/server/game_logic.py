"""Pure game mechanics for Python Arena.

The functions here do not perform socket, thread, or UI operations. They mutate
the provided GameState in place so the game loop can keep one authoritative
state object.
"""

import random
import uuid

from shared.constants import (
    DAMAGE_FLASH_TICKS,
    DAMAGE_IMMUNITY_TICKS,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    DYNAMIC_OBSTACLE_FLASH_TICKS,
    DYNAMIC_OBSTACLE_LIFETIME_TICKS,
    DYNAMIC_OBSTACLE_SPAWN_TICKS,
    FIXED_OBSTACLES,
    GRID_COLS,
    GRID_ROWS,
    MAX_HEALTH,
    MAX_DYNAMIC_OBSTACLES,
    MAX_PIES,
    OBSTACLE_TYPES,
    OPPOSITE,
    PIE_FLASH_TICKS,
    PIE_LIFETIME_TICKS,
    PIE_TYPES,
    RETRO_FLASH_PERIOD_TICKS,
    SHIELD_DURATION_TICKS,
    SNAKE_HIT_DMG,
    WALL_HIT_DMG,
)
from server.game_state import GameState, Obstacle, PieItem, SnakeState

DIRECTION_DELTA = {
    DIR_UP: (0, -1),
    DIR_DOWN: (0, 1),
    DIR_LEFT: (-1, 0),
    DIR_RIGHT: (1, 0),
}


def apply_damage(snake: SnakeState, amount: int) -> bool:
    """Apply damage if the snake is not immune. Returns True when HP changed."""
    if amount <= 0 or snake.immune_ticks > 0:
        return False
    snake.health -= amount
    snake.immune_ticks = DAMAGE_IMMUNITY_TICKS
    snake.damage_flash_ticks = DAMAGE_FLASH_TICKS
    return True


def redirect_from_wall(snake: SnakeState, col: int, row: int) -> tuple[int, int]:
    """Clamp the head inside the arena and turn the snake back inward."""
    if col < 0:
        snake.direction = DIR_RIGHT
    elif col >= GRID_COLS:
        snake.direction = DIR_LEFT
    elif row < 0:
        snake.direction = DIR_DOWN
    elif row >= GRID_ROWS:
        snake.direction = DIR_UP
    return max(0, min(col, GRID_COLS - 1)), max(0, min(row, GRID_ROWS - 1))


def occupied_cells(state: GameState) -> set[tuple[int, int]]:
    cells = set()
    for snake in state.snakes.values():
        cells.update(snake.body)
    cells.update((obs.col, obs.row) for obs in state.obstacles)
    cells.update((pie.col, pie.row) for pie in state.pies)
    return cells


def random_free_cell(state: GameState) -> tuple[int, int]:
    occupied = occupied_cells(state)
    all_cells = {(col, row) for col in range(GRID_COLS) for row in range(GRID_ROWS)}
    free = list(all_cells - occupied)
    if not free:
        raise RuntimeError("No free cells available")
    return random.choice(free)


def spawn_pies(state: GameState) -> None:
    while len(state.pies) < MAX_PIES:
        col, row = random_free_cell(state)
        pie_type = random.choice(list(PIE_TYPES.keys()))
        state.pies.append(
            PieItem(
                id=uuid.uuid4().hex[:8],
                col=col,
                row=row,
                pie_type=pie_type,
                spawned_tick=state.tick,
                expires_tick=state.tick + PIE_LIFETIME_TICKS,
                flash_ticks=PIE_FLASH_TICKS,
            )
        )


def place_obstacles(state: GameState) -> None:
    """Place the fixed assignment-required obstacle layout once per game."""
    state.obstacles.clear()
    for col, row, obs_type in FIXED_OBSTACLES:
        state.obstacles.append(Obstacle(col=col, row=row, obs_type=obs_type))


def spawn_dynamic_obstacle(state: GameState) -> None:
    temporary_count = sum(1 for obs in state.obstacles if obs.temporary)
    if temporary_count >= MAX_DYNAMIC_OBSTACLES:
        return
    if state.tick <= 0 or state.tick % DYNAMIC_OBSTACLE_SPAWN_TICKS != 0:
        return

    col, row = random_free_cell(state)
    obs_type = random.choice(list(OBSTACLE_TYPES.keys()))
    state.obstacles.append(
        Obstacle(
            col=col,
            row=row,
            obs_type=obs_type,
            temporary=True,
            spawned_tick=state.tick,
            expires_tick=state.tick + DYNAMIC_OBSTACLE_LIFETIME_TICKS,
            flash_ticks=DYNAMIC_OBSTACLE_FLASH_TICKS,
        )
    )


def cull_expired_objects(state: GameState) -> None:
    state.pies = [
        pie
        for pie in state.pies
        if pie.expires_tick <= 0 or state.tick < pie.expires_tick
    ]
    state.obstacles = [
        obs
        for obs in state.obstacles
        if not obs.temporary or obs.expires_tick <= 0 or state.tick < obs.expires_tick
    ]


def advance_snake(snake: SnakeState, new_dir: str) -> None:
    """Move a snake one cell, rejecting immediate 180-degree reversals."""
    if new_dir in DIRECTION_DELTA and OPPOSITE.get(snake.direction) != new_dir:
        snake.direction = new_dir

    dc, dr = DIRECTION_DELTA[snake.direction]
    head_col, head_row = snake.body[0]
    snake.body.insert(0, (head_col + dc, head_row + dr))
    snake.body.pop()


def check_collisions(state: GameState) -> None:
    """Apply health, growth, and alive-state effects from collisions."""
    all_bodies = {
        username: set(snake.body[1:])
        for username, snake in state.snakes.items()
    }
    head_positions: dict[tuple[int, int], list[str]] = {}
    for username, snake in state.snakes.items():
        if snake.alive:
            head_positions.setdefault(snake.body[0], []).append(username)

    for snake in state.snakes.values():
        if not snake.alive:
            continue

        head_col, head_row = snake.body[0]

        hit_wall = not (0 <= head_col < GRID_COLS and 0 <= head_row < GRID_ROWS)
        if hit_wall:
            if not snake.shielded:
                apply_damage(snake, WALL_HIT_DMG)
            snake.body[0] = redirect_from_wall(snake, head_col, head_row)
            head_col, head_row = snake.body[0]

        for obs in state.obstacles:
            if (obs.col, obs.row) == (head_col, head_row):
                apply_damage(snake, abs(OBSTACLE_TYPES[obs.obs_type]))

        if not hit_wall and not snake.shielded:
            for body_set in all_bodies.values():
                if (head_col, head_row) in body_set:
                    apply_damage(snake, SNAKE_HIT_DMG)

        if (
            not hit_wall
            and not snake.shielded
            and len(head_positions.get((head_col, head_row), [])) > 1
        ):
            apply_damage(snake, SNAKE_HIT_DMG)

        for pie in list(state.pies):
            if (pie.col, pie.row) == (head_col, head_row):
                if pie.pie_type == "shield":
                    snake.shielded = True
                    snake.shield_ticks = SHIELD_DURATION_TICKS
                else:
                    delta = PIE_TYPES[pie.pie_type][1]
                    if delta < 0:
                        apply_damage(snake, abs(delta))
                    else:
                        snake.health = min(MAX_HEALTH, snake.health + delta)
                snake.score += 1
                snake.body.append(snake.body[-1])
                state.pies.remove(pie)

        snake.health = max(0, snake.health)
        if snake.health == 0:
            snake.alive = False


def update_shields(state: GameState) -> None:
    for snake in state.snakes.values():
        if snake.shield_ticks > 0:
            snake.shield_ticks -= 1
        snake.shielded = snake.shield_ticks > 0


def update_damage_feedback(state: GameState) -> None:
    for snake in state.snakes.values():
        if snake.immune_ticks > 0:
            snake.immune_ticks -= 1
        if snake.damage_flash_ticks > 0:
            snake.damage_flash_ticks -= 1


def is_flash_visible(current_tick: int, expires_tick: int, flash_ticks: int) -> bool:
    if expires_tick <= 0 or flash_ticks <= 0:
        return True
    remaining = expires_tick - current_tick
    if remaining > flash_ticks:
        return True
    return (remaining // RETRO_FLASH_PERIOD_TICKS) % 2 == 0


def tick(state: GameState, pending_moves: dict[str, str], dt: float) -> None:
    """Advance the authoritative game state by one server tick."""
    state.time_left = max(0.0, state.time_left - dt)
    state.tick += 1
    update_shields(state)
    update_damage_feedback(state)
    cull_expired_objects(state)

    for username, snake in state.snakes.items():
        if snake.alive:
            advance_snake(snake, pending_moves.get(username, ""))

    check_collisions(state)
    cull_expired_objects(state)
    spawn_dynamic_obstacle(state)
    spawn_pies(state)


def is_game_over(state: GameState) -> bool:
    alive = [snake for snake in state.snakes.values() if snake.alive]
    return len(alive) <= 1 or state.time_left <= 0


def determine_winner(state: GameState) -> str | None:
    """Return the winning username, or None for a draw."""
    if not state.snakes:
        return None

    ranked = sorted(
        state.snakes.values(),
        key=lambda snake: (snake.alive, snake.health),
        reverse=True,
    )
    best = ranked[0]
    if len(ranked) > 1:
        second = ranked[1]
        if (best.alive, best.health) == (second.alive, second.health):
            return None
    return best.username
