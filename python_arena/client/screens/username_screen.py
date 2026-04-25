"""Username and snake-color handshake screen."""

import pygame

from client.screens.base import BaseScreen
from client.screens.ui import (
    ACCENT,
    DANGER,
    SNAKE_COLORS,
    Button,
    TextInput,
    draw_popup,
    draw_text,
    fill_background,
)
from shared.constants import C_CONNECT, S_CONNECT_ACK, S_ERROR, WINDOW_H, WINDOW_W


class UsernameScreen(BaseScreen):
    def __init__(self, net):
        super().__init__(net)
        self.username = TextInput((210, 250, 300, 42), "", "Username")
        self.username.active = True
        self.join_button = Button((285, 405, 150, 42), "Join", True)
        self.selected_color = "green"
        self.status = ""
        self.waiting = False
        self.color_rects = {}

    def on_enter(self, data: dict | None = None) -> None:
        super().on_enter(data)
        self.waiting = False
        self.status = ""
        self.net.drain_messages()

    def update(self, events: list):
        transition = None
        deferred = []
        for msg in self.net.drain_messages():
            if msg.get("type") == S_CONNECT_ACK:
                self.waiting = False
                if msg.get("status") == "ok":
                    self.net.username = msg.get("username", self.username.text.strip())
                    self.net.snake_color = self.selected_color
                    transition = ("transition", "lobby")
                    continue
                self.set_popup("Join Error", msg.get("reason", "Username rejected."), DANGER)
            elif msg.get("type") == S_ERROR:
                self.waiting = False
                self.set_popup("Join Error", msg.get("reason", "Connection error."), DANGER)
            else:
                deferred.append(msg)

        if transition:
            self.net.defer_messages(deferred)
            return transition

        for event in events:
            submitted = self.username.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for color_name, rect in self.color_rects.items():
                    if rect.collidepoint(event.pos):
                        self.selected_color = color_name
            if submitted or self.join_button.clicked(event):
                self._submit()
        return None

    def _submit(self) -> None:
        name = self.username.text.strip()
        if not name:
            self.set_popup("Join Error", "Username cannot be empty.", DANGER)
            return
        if not self.net.connected:
            self.set_popup("Join Error", "Not connected to server.", DANGER)
            return
        try:
            self.net.send(
                {"type": C_CONNECT, "username": name, "color": self.selected_color}
            )
            self.waiting = True
            self.status = "Joining..."
            self.clear_feedback()
        except ConnectionError as exc:
            self.waiting = False
            self.set_popup("Join Error", str(exc), DANGER)

    def draw(self, surface) -> None:
        fill_background(surface)
        draw_text(surface, "Choose Identity", WINDOW_W // 2, 145, 36, ACCENT, "center")
        draw_text(surface, "Username", 210, 225, 18)
        self.username.draw(surface)

        draw_text(surface, "Snake Color", 210, 320, 18)
        self.color_rects = {}
        x = 210
        for color_name, rgb in SNAKE_COLORS.items():
            rect = pygame.Rect(x, 350, 44, 34)
            self.color_rects[color_name] = rect
            pygame.draw.rect(surface, rgb, rect, border_radius=6)
            border = ACCENT if color_name == self.selected_color else (80, 86, 96)
            pygame.draw.rect(surface, border, rect, 2, 6)
            x += 58

        self.join_button.label = "Joining" if self.waiting else "Join"
        self.join_button.draw(surface)
        if self.waiting and self.status:
            draw_text(surface, self.status, WINDOW_W // 2, WINDOW_H - 90, 18, ACCENT, "center")
        title, message, color = self.active_popup()
        if message:
            draw_popup(surface, title, message, color)
