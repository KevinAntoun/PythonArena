"""Short transition screen while waiting for S_GAME_START."""

from client.screens.base import BaseScreen
from client.screens.ui import ACCENT, DANGER, MUTED, draw_popup, draw_text, fill_background
from shared.constants import S_ERROR, S_GAME_START, S_GAME_STATE, WINDOW_H, WINDOW_W


class WaitingScreen(BaseScreen):
    def __init__(self, net):
        super().__init__(net)
        self.opponent = ""
        self.status = "Waiting for game start..."

    def on_enter(self, data: dict | None = None) -> None:
        super().on_enter(data)
        self.opponent = (data or {}).get("opponent", "")
        self.status = "Waiting for game start..."

    def update(self, events: list):
        for msg in self.net.drain_messages():
            if msg.get("type") == S_GAME_START:
                return ("transition", "game", msg)
            if msg.get("type") == S_GAME_STATE:
                return (
                    "transition",
                    "game",
                    {
                        "your_snake": self.net.username,
                        "opponent": self.opponent,
                        "state": msg.get("state"),
                    },
                )
            if msg.get("type") == S_ERROR:
                self.set_popup("Match Error", msg.get("reason", "Server error."), DANGER)
        return None

    def draw(self, surface) -> None:
        fill_background(surface)
        draw_text(surface, "Match Accepted", WINDOW_W // 2, 250, 34, ACCENT, "center")
        detail = f"Opponent: {self.opponent}" if self.opponent else self.status
        draw_text(surface, detail, WINDOW_W // 2, 305, 20, MUTED, "center")
        draw_text(surface, self.status, WINDOW_W // 2, WINDOW_H - 110, 18, MUTED, "center")
        title, message, color = self.active_popup()
        if message:
            draw_popup(surface, title, message, color)
