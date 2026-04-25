"""Key-binding customization screen."""

import pygame

from client.screens.base import BaseScreen
from client.screens.ui import ACCENT, MUTED, Button, draw_text, fill_background
from shared.constants import DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_UP, WINDOW_W

ROWS = [
    (DIR_UP, "Up"),
    (DIR_DOWN, "Down"),
    (DIR_LEFT, "Left"),
    (DIR_RIGHT, "Right"),
]


class CustomizeScreen(BaseScreen):
    def __init__(self, net):
        super().__init__(net)
        self.return_to = "lobby"
        self.capture_dir = ""
        self.back_button = Button((285, 555, 150, 42), "Done", True)
        self.row_buttons: dict[str, Button] = {}

    def on_enter(self, data: dict | None = None) -> None:
        self.return_to = (data or {}).get("return_to", "lobby")
        self.capture_dir = ""

    def update(self, events: list):
        for event in events:
            if self.capture_dir and event.type == pygame.KEYDOWN:
                self.net.key_bindings[self.capture_dir] = event.key
                self.capture_dir = ""
                continue

            if self.back_button.clicked(event):
                return ("transition", self.return_to)

            for direction, button in self.row_buttons.items():
                if button.clicked(event):
                    self.capture_dir = direction
        return None

    def draw(self, surface) -> None:
        fill_background(surface)
        draw_text(surface, "Controls", WINDOW_W // 2, 105, 36, ACCENT, "center")

        self.row_buttons = {}
        for idx, (direction, label) in enumerate(ROWS):
            y = 190 + idx * 68
            key_name = pygame.key.name(self.net.key_bindings.get(direction, 0)).upper()
            draw_text(surface, label, 210, y + 8, 22)
            button_label = "Press a key" if self.capture_dir == direction else key_name
            button = Button((360, y, 150, 42), button_label, self.capture_dir == direction)
            self.row_buttons[direction] = button
            button.draw(surface)

        draw_text(surface, "Changes apply immediately.", WINDOW_W // 2, 490, 17, MUTED, "center")
        self.back_button.draw(surface)
