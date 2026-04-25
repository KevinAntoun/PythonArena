"""Capture representative Pygame screen snapshots for the report appendix."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from pathlib import Path

import pygame

from client.network import NetworkManager
from client.screens.connect_screen import ConnectScreen
from client.screens.game_screen import GameScreen
from client.screens.lobby_screen import LobbyScreen
from client.screens.result_screen import ResultScreen
from client.screens.username_screen import UsernameScreen
from shared.constants import (
    DIR_LEFT,
    DIR_RIGHT,
    HUD_HEIGHT,
    WINDOW_H,
    WINDOW_W,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"


def fake_state() -> dict:
    return {
        "snakes": {
            "alice": {
                "body": [(7, 6), (6, 6), (5, 6), (4, 6)],
                "direction": DIR_RIGHT,
                "health": 86,
                "alive": True,
                "color": "green",
                "score": 2,
                "shielded": True,
                "shield_ticks": 38,
                "immune_ticks": 0,
                "damage_flash_ticks": 0,
            },
            "bob": {
                "body": [(22, 18), (23, 18), (24, 18), (25, 18)],
                "direction": DIR_LEFT,
                "health": 62,
                "alive": True,
                "color": "blue",
                "score": 1,
                "shielded": False,
                "shield_ticks": 0,
                "immune_ticks": 8,
                "damage_flash_ticks": 5,
            },
        },
        "pies": [
            {"id": "p1", "col": 12, "row": 8, "type": "regular"},
            {"id": "p2", "col": 18, "row": 9, "type": "golden"},
            {"id": "p3", "col": 9, "row": 16, "type": "poison"},
            {"id": "p4", "col": 21, "row": 13, "type": "shield"},
        ],
        "obstacles": [
            {"col": 6, "row": 5, "type": "rock"},
            {"col": 14, "row": 5, "type": "spike"},
            {"col": 23, "row": 5, "type": "rock"},
            {"col": 9, "row": 12, "type": "spike"},
            {"col": 20, "row": 12, "type": "rock"},
            {"col": 6, "row": 19, "type": "spike"},
            {"col": 15, "row": 19, "type": "rock"},
            {"col": 23, "row": 19, "type": "spike"},
        ],
        "time_left": 27.0,
        "tick": 121,
    }


def save_screen(surface: pygame.Surface, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, OUTPUT_DIR / f"{name}.png")


def render(screen_obj, surface: pygame.Surface, name: str) -> None:
    screen_obj.draw(surface)
    save_screen(surface, name)


def main() -> None:
    pygame.init()
    surface = pygame.Surface((WINDOW_W, WINDOW_H))
    net = NetworkManager()
    net.username = "alice"
    net.snake_color = "green"

    connect = ConnectScreen(net)
    render(connect, surface, "01_connect")

    username = UsernameScreen(net)
    username.username.text = "alice"
    username.selected_color = "green"
    render(username, surface, "02_username")

    lobby = LobbyScreen(net)
    lobby.players = ["alice", "bob", "fan"]
    lobby.incoming_from = "bob"
    render(lobby, surface, "03_lobby_challenge")

    game = GameScreen(net)
    game.on_enter(
        {
            "your_snake": "alice",
            "opponent": "bob",
            "state": fake_state(),
        }
    )
    game.chat_log = [("bob", "close match"), ("fan", "go players")]
    render(game, surface, "04_gameplay")

    viewer = GameScreen(net)
    viewer.on_enter({"is_viewer": True, "state": fake_state()})
    render(viewer, surface, "05_viewer")

    result = ResultScreen(net)
    result.on_enter({"winner": "alice", "state": fake_state()})
    render(result, surface, "06_result")

    pygame.quit()
    print(f"Saved screenshots to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
