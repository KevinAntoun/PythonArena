"""Serializable game state dataclasses.

These classes contain no socket, thread, or Pygame behavior. They are the
server's in-memory model and can be converted directly into JSON-safe dicts.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from shared.constants import GAME_DURATION


@dataclass
class SnakeState:
    username: str
    body: List[Tuple[int, int]]
    direction: str
    health: int
    alive: bool = True
    color: str = "green"
    score: int = 0
    shielded: bool = False
    shield_ticks: int = 0
    immune_ticks: int = 0
    damage_flash_ticks: int = 0


@dataclass
class PieItem:
    id: str
    col: int
    row: int
    pie_type: str
    spawned_tick: int = 0
    expires_tick: int = 0
    flash_ticks: int = 0


@dataclass
class Obstacle:
    col: int
    row: int
    obs_type: str
    temporary: bool = False
    spawned_tick: int = 0
    expires_tick: int = 0
    flash_ticks: int = 0


@dataclass
class GameState:
    snakes: Dict[str, SnakeState] = field(default_factory=dict)
    pies: List[PieItem] = field(default_factory=list)
    obstacles: List[Obstacle] = field(default_factory=list)
    time_left: float = float(GAME_DURATION)
    tick: int = 0

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary for JSON transmission."""
        return {
            "snakes": {
                username: {
                    "body": snake.body,
                    "direction": snake.direction,
                    "health": snake.health,
                    "alive": snake.alive,
                    "color": snake.color,
                    "score": snake.score,
                    "shielded": snake.shielded,
                    "shield_ticks": snake.shield_ticks,
                    "immune_ticks": snake.immune_ticks,
                    "damage_flash_ticks": snake.damage_flash_ticks,
                }
                for username, snake in self.snakes.items()
            },
            "pies": [
                {
                    "id": pie.id,
                    "col": pie.col,
                    "row": pie.row,
                    "type": pie.pie_type,
                    "spawned_tick": pie.spawned_tick,
                    "expires_tick": pie.expires_tick,
                    "flash_ticks": pie.flash_ticks,
                }
                for pie in self.pies
            ],
            "obstacles": [
                {
                    "col": obs.col,
                    "row": obs.row,
                    "type": obs.obs_type,
                    "temporary": obs.temporary,
                    "spawned_tick": obs.spawned_tick,
                    "expires_tick": obs.expires_tick,
                    "flash_ticks": obs.flash_ticks,
                }
                for obs in self.obstacles
            ],
            "time_left": round(self.time_left, 1),
            "tick": self.tick,
        }
