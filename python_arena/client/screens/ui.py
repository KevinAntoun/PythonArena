"""Small pygame UI helpers shared by client screens."""

from __future__ import annotations

import pygame

from shared.constants import (
    COLOR_BG,
    COLOR_GRID,
    COLOR_HP_BAR_LOW,
    COLOR_HP_BAR_OK,
    COLOR_HUD,
    COLOR_OBSTACLE,
    COLOR_SPIKE,
    COLOR_TEXT,
)

ACCENT = (88, 210, 255)
ACCENT_DARK = (36, 120, 155)
MUTED = (145, 154, 166)
PANEL = (28, 31, 36)
PANEL_2 = (36, 40, 47)
DANGER = (238, 94, 82)
SUCCESS = (89, 210, 136)

SNAKE_COLORS = {
    "green": (65, 205, 110),
    "blue": (73, 132, 235),
    "red": (232, 78, 80),
    "cyan": (88, 210, 255),
}

PIE_COLORS = {
    "regular": (255, 200, 80),
    "golden": (255, 215, 0),
    "poison": (80, 200, 80),
    "shield": (100, 180, 255),
}

OBSTACLE_COLORS = {
    "rock": COLOR_OBSTACLE,
    "spike": COLOR_SPIKE,
}

_font_cache: dict[int, pygame.font.Font] = {}


def get_font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        _font_cache[size] = pygame.font.SysFont("consolas", size)
    return _font_cache[size]


def draw_text(
    surface: pygame.Surface,
    text: str,
    x: int,
    y: int,
    size: int = 20,
    color=COLOR_TEXT,
    anchor: str = "topleft",
) -> pygame.Rect:
    render = get_font(size).render(str(text), True, color)
    rect = render.get_rect(**{anchor: (x, y)})
    surface.blit(render, rect)
    return rect


def fill_background(surface: pygame.Surface) -> None:
    surface.fill(COLOR_BG)
    pygame.draw.rect(surface, COLOR_HUD, surface.get_rect(), 0)
    for y in range(72, surface.get_height(), 24):
        pygame.draw.line(surface, COLOR_GRID, (0, y), (surface.get_width(), y))


def draw_popup(
    surface: pygame.Surface,
    title: str,
    message: str,
    color=DANGER,
) -> None:
    rect = pygame.Rect(0, 0, min(520, surface.get_width() - 80), 130)
    rect.center = (surface.get_width() // 2, surface.get_height() // 2)
    shadow = rect.move(0, 8)
    pygame.draw.rect(surface, (0, 0, 0), shadow, border_radius=8)
    pygame.draw.rect(surface, (30, 34, 40), rect, border_radius=8)
    pygame.draw.rect(surface, color, rect, 2, 8)
    draw_text(surface, title, rect.centerx, rect.y + 26, 22, color, "center")
    draw_text(surface, message, rect.centerx, rect.y + 72, 16, COLOR_TEXT, "center")


class Button:
    def __init__(self, rect, label: str, accent: bool = False) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.accent = accent

    def clicked(self, event) -> bool:
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )

    def draw(self, surface: pygame.Surface) -> None:
        hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        if self.accent:
            color = ACCENT if hovered else ACCENT_DARK
            text_color = (5, 18, 24)
        else:
            color = PANEL_2 if hovered else PANEL
            text_color = COLOR_TEXT
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, ACCENT if hovered else (62, 68, 78), self.rect, 1, 6)
        draw_text(
            surface,
            self.label,
            self.rect.centerx,
            self.rect.centery,
            17,
            text_color,
            "center",
        )


class TextInput:
    def __init__(self, rect, text: str = "", placeholder: str = "") -> None:
        self.rect = pygame.Rect(rect)
        self.text = text
        self.placeholder = placeholder
        self.active = False

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
            return False
        if event.type != pygame.KEYDOWN or not self.active:
            return False
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return True
        elif event.unicode and event.unicode.isprintable():
            self.text += event.unicode
        return False

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=6)
        border = ACCENT if self.active else (62, 68, 78)
        pygame.draw.rect(surface, border, self.rect, 1, 6)
        shown = self.text if self.text else self.placeholder
        color = COLOR_TEXT if self.text else MUTED
        draw_text(surface, shown, self.rect.x + 12, self.rect.centery, 18, color, "midleft")


def draw_health_bar(surface, x, y, w, h, current, maximum) -> None:
    ratio = 0 if maximum <= 0 else max(0, min(1, current / maximum))
    color = COLOR_HP_BAR_OK if ratio > 0.3 else COLOR_HP_BAR_LOW
    pygame.draw.rect(surface, (58, 63, 72), (x, y, w, h), border_radius=3)
    pygame.draw.rect(surface, color, (x, y, int(w * ratio), h), border_radius=3)
    pygame.draw.rect(surface, (95, 102, 114), (x, y, w, h), 1, 3)


def snake_rgb(name: str):
    return SNAKE_COLORS.get(name, SNAKE_COLORS["green"])
