"""Manual no-socket test for server game logic.

Run from this directory:
    python manual_game_logic_test.py
"""

import random

from shared.constants import (
    DIR_LEFT,
    DIR_RIGHT,
    DYNAMIC_OBSTACLE_SPAWN_TICKS,
    DAMAGE_IMMUNITY_TICKS,
    INITIAL_HEALTH,
    MAX_HEALTH,
    MAX_PIES,
    PIE_FLASH_TICKS,
    PIE_LIFETIME_TICKS,
    PIE_TYPES,
    SHIELD_DURATION_TICKS,
    SNAKE_HIT_DMG,
    WALL_HIT_DMG,
)
from server.game_logic import (
    check_collisions,
    cull_expired_objects,
    determine_winner,
    is_game_over,
    place_obstacles,
    spawn_dynamic_obstacle,
    spawn_pies,
    tick,
)
from server.game_state import GameState, PieItem, SnakeState


def main() -> None:
    random.seed(350)

    state = GameState()
    state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(2, 2), (1, 2), (0, 2)],
        direction=DIR_RIGHT,
        health=INITIAL_HEALTH,
    )
    state.snakes["bob"] = SnakeState(
        username="bob",
        body=[(27, 22), (28, 22), (29, 22)],
        direction=DIR_LEFT,
        health=INITIAL_HEALTH,
    )

    place_obstacles(state)
    spawn_pies(state)
    assert len(state.obstacles) == 8
    assert len(state.pies) == MAX_PIES
    assert all(pie.expires_tick == state.tick + PIE_LIFETIME_TICKS for pie in state.pies)
    assert all(pie.flash_ticks == PIE_FLASH_TICKS for pie in state.pies)

    for _ in range(10):
        tick(state, {}, 0.1)

    assert state.tick == 10
    assert state.snakes["alice"].body[0] == (12, 2)
    assert state.snakes["bob"].body[0] == (17, 22)

    wall_state = GameState()
    wall_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(0, 0), (1, 0), (2, 0)],
        direction=DIR_LEFT,
        health=INITIAL_HEALTH,
    )
    tick(wall_state, {}, 0.1)
    assert wall_state.snakes["alice"].body[0] == (0, 0)
    assert wall_state.snakes["alice"].health == INITIAL_HEALTH - WALL_HIT_DMG
    assert wall_state.snakes["alice"].direction == DIR_RIGHT
    assert wall_state.snakes["alice"].immune_ticks == DAMAGE_IMMUNITY_TICKS
    assert wall_state.snakes["alice"].damage_flash_ticks > 0
    tick(wall_state, {}, 0.1)
    assert wall_state.snakes["alice"].health == INITIAL_HEALTH - WALL_HIT_DMG

    collision_state = GameState()
    collision_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(6, 5), (5, 5), (4, 5)],
        direction=DIR_RIGHT,
        health=INITIAL_HEALTH,
    )
    place_obstacles(collision_state)
    check_collisions(collision_state)
    assert collision_state.snakes["alice"].health < INITIAL_HEALTH
    health_after_collision = collision_state.snakes["alice"].health
    check_collisions(collision_state)
    assert collision_state.snakes["alice"].health == health_after_collision

    pie_state = GameState()
    pie_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(4, 4), (3, 4), (2, 4)],
        direction=DIR_RIGHT,
        health=INITIAL_HEALTH,
    )
    pie_state.pies.append(PieItem(id="regular1", col=4, row=4, pie_type="regular"))
    check_collisions(pie_state)
    assert pie_state.snakes["alice"].health == INITIAL_HEALTH + PIE_TYPES["regular"][1]
    assert pie_state.snakes["alice"].score == 1
    assert len(pie_state.snakes["alice"].body) == 4
    assert pie_state.pies == []

    max_health_state = GameState()
    max_health_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(4, 4), (3, 4), (2, 4)],
        direction=DIR_RIGHT,
        health=MAX_HEALTH - 5,
    )
    max_health_state.pies.append(PieItem(id="gold1", col=4, row=4, pie_type="golden"))
    check_collisions(max_health_state)
    assert max_health_state.snakes["alice"].health == MAX_HEALTH

    shield_state = GameState()
    shield_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(4, 4), (3, 4), (2, 4)],
        direction=DIR_RIGHT,
        health=INITIAL_HEALTH,
    )
    shield_state.pies.append(PieItem(id="shield1", col=4, row=4, pie_type="shield"))
    check_collisions(shield_state)
    assert shield_state.snakes["alice"].shielded is True
    assert shield_state.snakes["alice"].shield_ticks == SHIELD_DURATION_TICKS
    assert shield_state.to_dict()["snakes"]["alice"]["shielded"] is True

    shield_wall_state = GameState()
    shield_wall_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(-1, 0), (0, 0), (1, 0)],
        direction=DIR_LEFT,
        health=INITIAL_HEALTH,
        shielded=True,
        shield_ticks=SHIELD_DURATION_TICKS,
    )
    check_collisions(shield_wall_state)
    assert shield_wall_state.snakes["alice"].health == INITIAL_HEALTH

    shield_body_state = GameState()
    shield_body_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(4, 4), (3, 4), (2, 4)],
        direction=DIR_RIGHT,
        health=INITIAL_HEALTH,
        shielded=True,
        shield_ticks=SHIELD_DURATION_TICKS,
    )
    shield_body_state.snakes["bob"] = SnakeState(
        username="bob",
        body=[(10, 10), (4, 4), (11, 10)],
        direction=DIR_LEFT,
        health=INITIAL_HEALTH,
    )
    check_collisions(shield_body_state)
    assert shield_body_state.snakes["alice"].health == INITIAL_HEALTH
    shield_body_state.snakes["alice"].shielded = False
    check_collisions(shield_body_state)
    assert shield_body_state.snakes["alice"].health == INITIAL_HEALTH - SNAKE_HIT_DMG

    expiry_state = GameState()
    expiry_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(4, 4), (3, 4), (2, 4)],
        direction=DIR_RIGHT,
        health=INITIAL_HEALTH,
    )
    expiry_state.pies.append(
        PieItem(
            id="expire1",
            col=10,
            row=10,
            pie_type="regular",
            spawned_tick=0,
            expires_tick=1,
            flash_ticks=PIE_FLASH_TICKS,
        )
    )
    expiry_state.tick = 1
    cull_expired_objects(expiry_state)
    assert expiry_state.pies == []

    dynamic_state = GameState()
    dynamic_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(4, 4), (3, 4), (2, 4)],
        direction=DIR_RIGHT,
        health=INITIAL_HEALTH,
    )
    dynamic_state.tick = DYNAMIC_OBSTACLE_SPAWN_TICKS
    place_obstacles(dynamic_state)
    spawn_dynamic_obstacle(dynamic_state)
    temporary = [obs for obs in dynamic_state.obstacles if obs.temporary]
    assert len(temporary) == 1
    assert temporary[0].expires_tick > dynamic_state.tick

    defeat_state = GameState()
    defeat_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(0, 0), (1, 0), (2, 0)],
        direction=DIR_LEFT,
        health=WALL_HIT_DMG,
    )
    defeat_state.snakes["bob"] = SnakeState(
        username="bob",
        body=[(10, 10), (11, 10), (12, 10)],
        direction=DIR_LEFT,
        health=INITIAL_HEALTH,
    )
    tick(defeat_state, {}, 0.1)
    assert is_game_over(defeat_state)
    assert determine_winner(defeat_state) == "bob"

    timer_state = GameState(time_left=0.05)
    timer_state.snakes["alice"] = SnakeState(
        username="alice",
        body=[(2, 2), (1, 2), (0, 2)],
        direction=DIR_RIGHT,
        health=80,
    )
    timer_state.snakes["bob"] = SnakeState(
        username="bob",
        body=[(27, 22), (28, 22), (29, 22)],
        direction=DIR_LEFT,
        health=90,
    )
    tick(timer_state, {}, 0.1)
    assert is_game_over(timer_state)
    assert determine_winner(timer_state) == "bob"

    print("Game logic test passed.")
    print(state.to_dict())


if __name__ == "__main__":
    main()
