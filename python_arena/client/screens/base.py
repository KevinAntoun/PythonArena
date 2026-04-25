"""Screen interface base class."""

import pygame


class BaseScreen:
    def __init__(self, net):
        self.net = net
        self._toast_message = ""
        self._toast_color = None
        self._toast_until = 0
        self._popup_title = ""
        self._popup_message = ""
        self._popup_color = None
        self._popup_until = 0

    def on_enter(self, data: dict | None = None) -> None:
        self.clear_feedback()

    def update(self, events: list):
        return None

    def draw(self, surface) -> None:
        raise NotImplementedError

    def clear_feedback(self) -> None:
        self._toast_message = ""
        self._toast_color = None
        self._toast_until = 0
        self._popup_title = ""
        self._popup_message = ""
        self._popup_color = None
        self._popup_until = 0

    def set_toast(self, message: str, color=None, duration_ms: int = 2600) -> None:
        self._toast_message = message
        self._toast_color = color
        self._toast_until = pygame.time.get_ticks() + duration_ms

    def set_popup(
        self,
        title: str,
        message: str,
        color=None,
        duration_ms: int = 3200,
    ) -> None:
        self._popup_title = title
        self._popup_message = message
        self._popup_color = color
        self._popup_until = pygame.time.get_ticks() + duration_ms

    def active_toast(self) -> tuple[str, object | None]:
        if self._toast_message and pygame.time.get_ticks() <= self._toast_until:
            return self._toast_message, self._toast_color
        self._toast_message = ""
        self._toast_color = None
        self._toast_until = 0
        return "", None

    def active_popup(self) -> tuple[str, str, object | None]:
        if self._popup_message and pygame.time.get_ticks() <= self._popup_until:
            return self._popup_title, self._popup_message, self._popup_color
        self._popup_title = ""
        self._popup_message = ""
        self._popup_color = None
        self._popup_until = 0
        return "", "", None
