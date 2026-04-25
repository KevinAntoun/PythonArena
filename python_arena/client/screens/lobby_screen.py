"""Online player list, challenges, and watch entry point."""

import pygame

from client.screens.base import BaseScreen
from client.screens.ui import ACCENT, DANGER, MUTED, Button, draw_popup, draw_text, fill_background
from shared.constants import (
    C_CHALLENGE,
    C_CHALLENGE_RESP,
    C_WATCH,
    S_CHALLENGE,
    S_CHALLENGE_ACK,
    S_ERROR,
    S_GAME_START,
    S_PLAYER_JOINED,
    S_PLAYER_LEFT,
    S_PLAYER_LIST,
    S_WATCH_ACK,
    WINDOW_W,
)


class LobbyScreen(BaseScreen):
    def __init__(self, net):
        super().__init__(net)
        self.players: list[str] = []
        self.game_in_progress = False
        self.spectatable_usernames: set[str] = set()
        self.incoming_from = ""
        self.duel_buttons: dict[str, Button] = {}
        self.controls_button = Button((562, 28, 110, 34), "Controls")
        self.accept_button = Button((230, 430, 120, 38), "Accept", True)
        self.decline_button = Button((370, 430, 120, 38), "Decline")

    def on_enter(self, data: dict | None = None) -> None:
        super().on_enter(data)
        self.net.auto_play = False

    def update(self, events: list):
        action = self._handle_messages()
        if action:
            return action

        for event in events:
            if self.controls_button.clicked(event):
                return ("transition", "customize", {"return_to": "lobby"})

            if self.incoming_from:
                if self.accept_button.clicked(event):
                    self._respond(True)
                elif self.decline_button.clicked(event):
                    self._respond(False)
                continue

            for username, button in self.duel_buttons.items():
                if button.clicked(event):
                    try:
                        if self.game_in_progress and username in self.spectatable_usernames:
                            self.net.send({"type": C_WATCH})
                            self.set_toast("Joining as spectator...", MUTED)
                        else:
                            self.net.send({"type": C_CHALLENGE, "target": username})
                            self.set_toast(f"Challenge sent to {username}.", MUTED)
                    except ConnectionError as exc:
                        self.set_popup("Lobby Error", str(exc), DANGER)
        return None

    def _handle_messages(self):
        pending_transition = None
        for msg in self.net.drain_messages():
            msg_type = msg.get("type")
            if msg_type == S_PLAYER_LIST:
                self.players = list(msg.get("players", []))
                self.game_in_progress = bool(msg.get("game_in_progress", False))
                self.spectatable_usernames = set(msg.get("spectatable_usernames", []))
            elif msg_type == S_PLAYER_JOINED:
                username = msg.get("username")
                if username and username not in self.players:
                    self.players.append(username)
            elif msg_type == S_PLAYER_LEFT:
                username = msg.get("username")
                self.players = [p for p in self.players if p != username]
            elif msg_type == S_CHALLENGE:
                self.incoming_from = msg.get("from", "")
            elif msg_type == S_CHALLENGE_ACK:
                if msg.get("accepted"):
                    pending_transition = (
                        "transition",
                        "waiting",
                        {"opponent": msg.get("from", "")},
                    )
                    continue
                self.set_toast(f"{msg.get('from', 'Player')} declined.", DANGER)
            elif msg_type == S_WATCH_ACK:
                pending_transition = (
                    "transition",
                    "game",
                    {"is_viewer": True, "state": msg.get("state")},
                )
            elif msg_type == S_GAME_START:
                return ("transition", "game", msg)
            elif msg_type == S_ERROR:
                self.set_popup("Lobby Error", msg.get("reason", "Server error."), DANGER)
        return pending_transition

    def _respond(self, accepted: bool) -> None:
        try:
            self.net.send(
                {
                    "type": C_CHALLENGE_RESP,
                    "from": self.incoming_from,
                    "accepted": accepted,
                }
            )
            self.set_toast(
                "Challenge accepted." if accepted else "Challenge declined.",
                MUTED,
            )
            self.incoming_from = ""
        except ConnectionError as exc:
            self.set_popup("Lobby Error", str(exc), DANGER)

    def draw(self, surface) -> None:
        fill_background(surface)
        draw_text(surface, "Lobby", 48, 38, 34, ACCENT)
        self.controls_button.draw(surface)
        draw_text(surface, f"You: {self.net.username or '-'}", WINDOW_W - 48, 72, 16, MUTED, "topright")

        list_rect = pygame.Rect(48, 105, WINDOW_W - 96, 430)
        pygame.draw.rect(surface, (24, 27, 32), list_rect, border_radius=8)
        pygame.draw.rect(surface, (62, 68, 78), list_rect, 1, 8)
        draw_text(surface, "Online Players", 72, 130, 22)

        self.duel_buttons = {}
        visible_players = [p for p in self.players if p != self.net.username]
        if not visible_players:
            draw_text(surface, "Waiting for another player...", 72, 205, 18, MUTED)
        for idx, username in enumerate(visible_players[:8]):
            y = 178 + idx * 40
            draw_text(surface, username, 78, y + 8, 18)
            label = (
                "Spectate"
                if self.game_in_progress and username in self.spectatable_usernames
                else "Duel"
            )
            button = Button((WINDOW_W - 190, y, 112, 32), label, True)
            self.duel_buttons[username] = button
            button.draw(surface)

        if self.game_in_progress and self.spectatable_usernames:
            players = " vs ".join(sorted(self.spectatable_usernames))
            draw_text(surface, f"Match in progress: {players}", 48, 586, 16, MUTED)

        toast, toast_color = self.active_toast()
        if toast:
            draw_text(surface, toast, WINDOW_W - 48, 586, 16, toast_color or MUTED, "topright")

        title, message, color = self.active_popup()
        if message:
            draw_popup(surface, title, message, color)

        if self.incoming_from:
            popup = pygame.Rect(150, 310, 420, 185)
            pygame.draw.rect(surface, (30, 34, 40), popup, border_radius=8)
            pygame.draw.rect(surface, ACCENT, popup, 1, 8)
            draw_text(surface, f"{self.incoming_from} challenges you", popup.centerx, 350, 22, ACCENT, "center")
            self.accept_button.draw(surface)
            self.decline_button.draw(surface)
