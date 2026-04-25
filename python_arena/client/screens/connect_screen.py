"""Server address entry screen."""

import pygame

from client.screens.base import BaseScreen
from client.screens.ui import ACCENT, Button, TextInput, draw_popup, draw_text, fill_background
from shared.constants import WINDOW_W


class ConnectScreen(BaseScreen):
    def __init__(self, net):
        super().__init__(net)
        self.host = TextInput((210, 255, 300, 42), "127.0.0.1", "Server IP")
        self.port = TextInput((210, 320, 300, 42), "5555", "Port")
        self.host.active = True
        self.connect_button = Button((285, 390, 150, 42), "Connect", True)

    def update(self, events: list):
        for event in events:
            host_enter = self.host.handle_event(event)
            port_enter = self.port.handle_event(event)

            if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
                self.host.active, self.port.active = self.port.active, self.host.active
            if host_enter:
                self.host.active = False
                self.port.active = True
            if port_enter or self.connect_button.clicked(event):
                return self._connect()
        return None

    def _connect(self):
        try:
            port = int(self.port.text.strip())
            self.net.connect(self.host.text.strip(), port)
        except ValueError:
            self.set_popup("Connection Error", "Port must be a number.")
            return None
        except OSError as exc:
            self.set_popup("Connection Error", f"Connection failed: {exc}")
            return None
        self.clear_feedback()
        return ("transition", "username")

    def draw(self, surface) -> None:
        fill_background(surface)
        draw_text(surface, "Python Arena", WINDOW_W // 2, 140, 44, ACCENT, "center")
        draw_text(surface, "Server", 210, 230, 18)
        self.host.draw(surface)
        draw_text(surface, "Port", 210, 295, 18)
        self.port.draw(surface)
        self.connect_button.draw(surface)
        title, message, color = self.active_popup()
        if message:
            draw_popup(surface, title, message, color)
