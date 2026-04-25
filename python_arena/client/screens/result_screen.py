"""Final match result screen."""

import pygame

from client.screens.base import BaseScreen
from client.screens.ui import ACCENT, MUTED, Button, draw_text, fill_background
from shared.constants import WINDOW_W


class ResultScreen(BaseScreen):
    def __init__(self, net):
        super().__init__(net)
        self.winner = None
        self.state = None
        self.back_button = Button((265, 545, 190, 42), "Return to Lobby", True)

    def on_enter(self, data: dict | None = None) -> None:
        data = data or {}
        self.winner = data.get("winner")
        self.state = data.get("state")

    def update(self, events: list):
        for event in events:
            if self.back_button.clicked(event):
                return ("transition", "lobby")
        return None

    def draw(self, surface) -> None:
        fill_background(surface)
        title = "Draw" if self.winner is None else f"{self.winner} Wins"
        draw_text(surface, title, WINDOW_W // 2, 120, 40, ACCENT, "center")

        snakes = (self.state or {}).get("snakes", {})
        y = 220
        for username, snake in snakes.items():
            line = (
                f"{username}   HP {snake.get('health', 0)}   "
                f"Pies {snake.get('score', 0)}   "
                f"{'Alive' if snake.get('alive') else 'Out'}"
            )
            draw_text(surface, line, WINDOW_W // 2, y, 20, MUTED, "center")
            y += 42

        self.back_button.draw(surface)
