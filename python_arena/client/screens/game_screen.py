"""Main gameplay renderer and in-game input handling."""

import math

import pygame

from client.autoplay import choose_auto_move
from client.screens.base import BaseScreen
from client.screens.ui import (
    ACCENT,
    DANGER,
    MUTED,
    OBSTACLE_COLORS,
    PIE_COLORS,
    Button,
    TextInput,
    draw_popup,
    draw_health_bar,
    draw_text,
    fill_background,
    snake_rgb,
)
from shared.constants import (
    C_CHAT,
    C_MOVE,
    CELL_SIZE,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    GRID_COLS,
    GRID_ROWS,
    HUD_HEIGHT,
    MAX_HEALTH,
    RETRO_FLASH_PERIOD_TICKS,
    S_CHAT,
    S_ERROR,
    S_GAME_END,
    S_GAME_START,
    S_GAME_STATE,
    WINDOW_H,
    WINDOW_W,
)


class GameScreen(BaseScreen):
    def __init__(self, net):
        super().__init__(net)
        self.state = None
        self.my_username = ""
        self.opponent = ""
        self.is_viewer = False
        self.chat_log: list[tuple[str, str]] = []
        self.chat_input = TextInput((74, WINDOW_H - 38, WINDOW_W - 156, 30), "", "Chat")
        self.send_button = Button((WINDOW_W - 72, WINDOW_H - 38, 54, 30), "Send", True)
        self.auto_button = Button((WINDOW_W // 2 - 50, 34, 100, 20), "Auto: Off")
        self._last_auto_tick = -1

    def on_enter(self, data: dict | None = None) -> None:
        super().on_enter(data)
        data = data or {}
        self.is_viewer = bool(data.get("is_viewer", False))
        self.my_username = data.get("your_snake", self.net.username)
        self.opponent = data.get("opponent", "")
        if data.get("state"):
            self.state = data["state"]
        self.chat_input.text = ""
        self._last_auto_tick = -1

    def update(self, events: list):
        action = self._handle_messages()
        if action:
            return action

        for event in events:
            if not self.is_viewer and self.auto_button.clicked(event):
                self.net.auto_play = not self.net.auto_play
                self.set_toast(
                    "Auto-pilot enabled." if self.net.auto_play else "Auto-pilot disabled.",
                    ACCENT,
                )
                continue

            chat_submitted = self.chat_input.handle_event(event)
            if chat_submitted or self.send_button.clicked(event):
                self._send_chat()
                continue

            if (
                not self.is_viewer
                and not self.net.auto_play
                and event.type == pygame.KEYDOWN
                and not self.chat_input.active
            ):
                for direction, key in self.net.key_bindings.items():
                    if event.key == key:
                        self._send_move(direction)
                        break
        self._update_auto_play()
        return None

    def _handle_messages(self):
        for msg in self.net.drain_messages():
            msg_type = msg.get("type")
            if msg_type == S_GAME_START:
                self.my_username = msg.get("your_snake", self.net.username)
                self.opponent = msg.get("opponent", "")
                self.state = msg.get("state")
                self.is_viewer = False
            elif msg_type == S_GAME_STATE:
                self.state = msg.get("state")
            elif msg_type == S_GAME_END:
                self.state = msg.get("state", self.state)
                return ("transition", "result", msg)
            elif msg_type == S_CHAT:
                self._append_chat(msg.get("from", "?"), msg.get("message", ""))
            elif msg_type == S_ERROR:
                self.set_popup("Match Error", msg.get("reason", "Server error."), DANGER)
        return None

    def _send_move(self, direction: str) -> None:
        if direction not in {DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT}:
            return
        try:
            self.net.send({"type": C_MOVE, "direction": direction})
        except ConnectionError as exc:
            self.set_popup("Connection Error", str(exc), DANGER)

    def _send_chat(self) -> None:
        message = self.chat_input.text.strip()
        if not message:
            return
        target = None if self.is_viewer else self.opponent or None
        try:
            self.net.send({"type": C_CHAT, "to": target, "message": message})
            self._append_chat(self.net.username or "me", message)
            self.chat_input.text = ""
        except ConnectionError as exc:
            self.set_popup("Chat Error", str(exc), DANGER)

    def _append_chat(self, sender: str, message: str) -> None:
        self.chat_log.append((sender, message))
        self.chat_log = self.chat_log[-8:]

    def _update_auto_play(self) -> None:
        if self.is_viewer or not self.net.auto_play or not self.state:
            return
        tick = int(self.state.get("tick", -1))
        if tick < 0 or tick == self._last_auto_tick:
            return
        self._last_auto_tick = tick
        direction = choose_auto_move(self.state, self.my_username)
        if direction:
            self._send_move(direction)

    def draw(self, surface) -> None:
        fill_background(surface)
        self._draw_hud(surface)
        self._draw_grid(surface)
        if self.state:
            self._draw_obstacles(surface)
            self._draw_pies(surface)
            self._draw_snakes(surface)
            self._draw_legend(surface)
        else:
            draw_text(surface, "Waiting for game state", WINDOW_W // 2, WINDOW_H // 2, 22, MUTED, "center")
        self._draw_feedback(surface)
        self._draw_chat(surface)

    def _draw_hud(self, surface) -> None:
        pygame.draw.rect(surface, (14, 16, 20), (0, 0, WINDOW_W, HUD_HEIGHT))
        if not self.state:
            draw_text(surface, "Python Arena", 24, 20, 22, ACCENT)
            return

        snakes = self.state.get("snakes", {})
        names = list(snakes.keys())
        left = self.my_username if self.my_username in snakes else (names[0] if names else "")
        right = self.opponent if self.opponent in snakes else next((n for n in names if n != left), "")

        self._draw_player_hud(surface, left, 22, 12)
        timer = int(float(self.state.get("time_left", 0)))
        timer_color = DANGER if timer <= 30 else ACCENT
        draw_text(surface, f"{timer // 60:02}:{timer % 60:02}", WINDOW_W // 2, 20, 24, timer_color, "center")
        if self.is_viewer:
            draw_text(surface, "Watching", WINDOW_W // 2, 43, 14, MUTED, "center")
        else:
            self.auto_button.label = "Auto: On" if self.net.auto_play else "Auto: Off"
            self.auto_button.accent = self.net.auto_play
            self.auto_button.draw(surface)
        if right:
            self._draw_player_hud(surface, right, WINDOW_W - 22, 12, align_right=True)

    def _draw_player_hud(self, surface, username: str, x: int, y: int, align_right: bool = False) -> None:
        snake = self.state.get("snakes", {}).get(username, {})
        health = int(snake.get("health", 0))
        score = int(snake.get("score", 0))
        immune = int(snake.get("immune_ticks", 0)) > 0
        if align_right:
            draw_text(surface, f"{username}  {health}hp  Pies {score}", x, y, 16, anchor="topright")
            draw_health_bar(surface, x - 180, y + 27, 180, 12, health, MAX_HEALTH)
            if immune:
                draw_text(surface, "INVULN", x, y + 44, 12, ACCENT, "topright")
        else:
            draw_text(surface, f"{username}  {health}hp  Pies {score}", x, y, 16)
            draw_health_bar(surface, x, y + 27, 180, 12, health, MAX_HEALTH)
            if immune:
                draw_text(surface, "INVULN", x, y + 44, 12, ACCENT)

    def _draw_grid(self, surface) -> None:
        arena = pygame.Rect(0, HUD_HEIGHT, WINDOW_W, GRID_ROWS * CELL_SIZE)
        pygame.draw.rect(surface, (16, 19, 24), arena)
        for col in range(GRID_COLS):
            for row in range(GRID_ROWS):
                rect = self._cell_rect(col, row)
                base = 24 if (col + row) % 2 == 0 else 28
                pygame.draw.rect(surface, (base, base + 2, base + 7), rect)
                if (col * 7 + row * 5) % 11 == 0:
                    pygame.draw.circle(surface, (38, 43, 51), rect.center, 2)
                pygame.draw.rect(surface, (34, 39, 48), rect, 1)
        pygame.draw.rect(surface, (70, 82, 98), arena, 2)

    def _draw_obstacles(self, surface) -> None:
        for obs in self.state.get("obstacles", []):
            if not self._retro_object_visible(obs):
                continue
            rect = self._cell_rect(obs["col"], obs["row"]).inflate(-3, -3)
            if obs.get("type") == "spike":
                base_y = rect.bottom - 1
                spikes = [
                    [
                        (rect.x + 1, base_y),
                        (rect.x + 6, rect.y + 5),
                        (rect.x + 11, base_y),
                    ],
                    [
                        (rect.x + 7, base_y),
                        (rect.centerx, rect.y),
                        (rect.right - 7, base_y),
                    ],
                    [
                        (rect.right - 11, base_y),
                        (rect.right - 6, rect.y + 5),
                        (rect.right - 1, base_y),
                    ],
                ]
                pygame.draw.rect(surface, (88, 96, 108), (rect.x + 2, rect.bottom - 4, rect.w - 4, 4), border_radius=2)
                for points in spikes:
                    pygame.draw.polygon(surface, (235, 239, 244), points)
                    pygame.draw.polygon(surface, (118, 130, 146), points, 1)
                pygame.draw.line(surface, (255, 255, 255), (rect.centerx - 2, rect.y + 4), (rect.centerx - 6, base_y - 3), 1)
            else:
                color = OBSTACLE_COLORS.get(obs.get("type"), (130, 80, 40))
                pygame.draw.rect(surface, (72, 55, 43), rect.move(2, 2), border_radius=5)
                pygame.draw.rect(surface, color, rect, border_radius=5)
                pygame.draw.line(surface, (92, 55, 34), rect.topleft, rect.center, 2)
                pygame.draw.line(surface, (184, 125, 78), (rect.x + 5, rect.y + 4), (rect.right - 5, rect.y + 8), 2)
                if obs.get("temporary"):
                    pygame.draw.rect(surface, (245, 228, 180), rect.inflate(2, 2), 1, 6)

    def _draw_pies(self, surface) -> None:
        for pie in self.state.get("pies", []):
            if not self._retro_object_visible(pie):
                continue
            rect = self._cell_rect(pie["col"], pie["row"]).inflate(-7, -7)
            pie_type = pie.get("type")
            color = PIE_COLORS.get(pie_type, PIE_COLORS["regular"])
            if pie_type == "golden":
                self._draw_star(surface, rect.center, 9, 4, color, (255, 248, 156))
            elif pie_type == "poison":
                pygame.draw.ellipse(surface, color, rect)
                pygame.draw.ellipse(surface, (22, 70, 35), rect, 2)
                pygame.draw.circle(surface, (20, 45, 24), (rect.centerx - 4, rect.centery - 2), 2)
                pygame.draw.circle(surface, (20, 45, 24), (rect.centerx + 4, rect.centery - 2), 2)
                pygame.draw.line(surface, (20, 45, 24), (rect.centerx - 4, rect.centery + 5), (rect.centerx + 4, rect.centery + 5), 2)
            elif pie_type == "shield":
                points = [
                    (rect.centerx, rect.y),
                    (rect.right, rect.centery),
                    (rect.centerx, rect.bottom),
                    (rect.x, rect.centery),
                ]
                pygame.draw.polygon(surface, (42, 105, 180), points)
                pygame.draw.polygon(surface, color, points, 2)
                pygame.draw.line(surface, (180, 230, 255), (rect.centerx, rect.y + 4), (rect.centerx, rect.bottom - 4), 2)
            else:
                pygame.draw.ellipse(surface, (142, 82, 44), rect.inflate(4, 4))
                pygame.draw.ellipse(surface, color, rect)
                pygame.draw.arc(surface, (118, 64, 38), rect.inflate(-2, -2), 0.3, math.pi - 0.3, 2)
                pygame.draw.circle(surface, (255, 236, 142), (rect.centerx - 3, rect.centery - 4), 2)

    def _draw_snakes(self, surface) -> None:
        for username, snake in self.state.get("snakes", {}).items():
            color = snake_rgb(snake.get("color", "green"))
            immune_ticks = int(snake.get("immune_ticks", 0))
            burst_ticks = int(snake.get("damage_flash_ticks", 0))
            visible = self._retro_flash_visible(immune_ticks)
            if immune_ticks > 0 and not visible:
                continue
            for idx, cell in enumerate(snake.get("body", [])):
                col, row = cell
                if not (0 <= col < GRID_COLS and 0 <= row < GRID_ROWS):
                    continue
                rect = self._cell_rect(col, row).inflate(-3, -3)
                shade = color
                if burst_ticks > 0:
                    shade = self._lighten(color, 96) if visible else color
                elif immune_ticks > 0:
                    shade = self._lighten(color, 18) if idx % 2 == 0 else color
                if idx == 0 and snake.get("shielded"):
                    pulse = 90 + (int(self.state.get("tick", 0)) % 4) * 25
                    aura = pygame.Surface(rect.inflate(10, 10).size, pygame.SRCALPHA)
                    pygame.draw.rect(
                        aura,
                        (100, 180, 255, pulse),
                        aura.get_rect(),
                        border_radius=8,
                    )
                    surface.blit(aura, rect.inflate(10, 10).topleft)
                pygame.draw.rect(surface, shade, rect, border_radius=5)
                if immune_ticks > 0:
                    shimmer = pygame.Surface(rect.size, pygame.SRCALPHA)
                    shimmer.fill((255, 248, 220, 38))
                    surface.blit(shimmer, rect.topleft)
                pygame.draw.line(surface, self._lighten(color, 48), (rect.x + 4, rect.y + 4), (rect.right - 5, rect.y + 4), 2)
                pygame.draw.rect(surface, self._darken(color, 52), rect, 1, 5)
                if idx == 0:
                    outline = self._lighten(color, 90) if immune_ticks > 0 else self._lighten(color, 70)
                    pygame.draw.rect(surface, outline, rect.inflate(2, 2), 2, 6)
                    self._draw_snake_eyes(surface, rect, snake.get("direction", DIR_RIGHT))
                    if burst_ticks > 0:
                        self._draw_hit_burst(surface, rect, burst_ticks)
                if idx == 0 and username == self.my_username and not self.is_viewer:
                    pygame.draw.rect(surface, ACCENT, rect.inflate(4, 4), 1, 6)

    def _draw_chat(self, surface) -> None:
        overlay = pygame.Surface((WINDOW_W, 120), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, WINDOW_H - 120))
        y = WINDOW_H - 112
        for sender, message in self.chat_log[-4:]:
            draw_text(surface, f"{sender}: {message}", 20, y, 15)
            y += 18
        draw_text(surface, "Chat", 20, WINDOW_H - 33, 16, MUTED)
        self.chat_input.draw(surface)
        self.send_button.draw(surface)

    def _draw_legend(self, surface) -> None:
        rect = pygame.Rect(WINDOW_W - 168, HUD_HEIGHT + 8, 158, 90)
        alpha = 185
        for snake in self.state.get("snakes", {}).values():
            body = snake.get("body", [])
            if not body:
                continue
            col, row = body[0]
            if rect.colliderect(self._cell_rect(col, row)):
                alpha = 62
                break
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((8, 12, 17, alpha))
        surface.blit(panel, rect.topleft)
        pygame.draw.rect(surface, (75, 88, 105, alpha), rect, 1, 6)
        items = [
            ("Pie +10", PIE_COLORS["regular"]),
            ("Gold +25", PIE_COLORS["golden"]),
            ("Poison -15", PIE_COLORS["poison"]),
            ("Shield", PIE_COLORS["shield"]),
            ("Rock -10", OBSTACLE_COLORS["rock"]),
            ("Spike -20", (235, 239, 244)),
        ]
        for idx, (label, color) in enumerate(items):
            x = rect.x + 8 + (idx % 2) * 76
            y = rect.y + 7 + (idx // 2) * 22
            pygame.draw.rect(surface, color, (x, y + 3, 10, 10), border_radius=2)
            draw_text(surface, label, x + 14, y, 10, (225, 232, 240))
        draw_text(surface, "Blink = expiring", rect.x + 8, rect.bottom - 12, 9, MUTED)

    def _draw_feedback(self, surface) -> None:
        toast, toast_color = self.active_toast()
        if toast:
            badge = pygame.Rect(0, 0, 240, 28)
            badge.center = (WINDOW_W // 2, HUD_HEIGHT + 18)
            overlay = pygame.Surface(badge.size, pygame.SRCALPHA)
            overlay.fill((8, 12, 18, 180))
            surface.blit(overlay, badge.topleft)
            pygame.draw.rect(surface, toast_color or ACCENT, badge, 1, 6)
            draw_text(surface, toast, badge.centerx, badge.centery, 13, toast_color or ACCENT, "center")

        title, message, color = self.active_popup()
        if message:
            draw_popup(surface, title, message, color or DANGER)

    def _retro_object_visible(self, obj: dict) -> bool:
        expires_tick = int(obj.get("expires_tick", 0) or 0)
        flash_ticks = int(obj.get("flash_ticks", 0) or 0)
        if expires_tick <= 0 or flash_ticks <= 0:
            return True
        remaining = expires_tick - int(self.state.get("tick", 0))
        if remaining > flash_ticks:
            return True
        return self._retro_flash_visible(remaining)

    @staticmethod
    def _retro_flash_visible(ticks_remaining: int) -> bool:
        if ticks_remaining <= 0:
            return False
        return (ticks_remaining // RETRO_FLASH_PERIOD_TICKS) % 2 == 0

    @staticmethod
    def _cell_rect(col: int, row: int) -> pygame.Rect:
        return pygame.Rect(
            col * CELL_SIZE,
            row * CELL_SIZE + HUD_HEIGHT,
            CELL_SIZE,
            CELL_SIZE,
        )

    @staticmethod
    def _lighten(color, amount: int):
        return tuple(min(255, c + amount) for c in color)

    @staticmethod
    def _darken(color, amount: int):
        return tuple(max(0, c - amount) for c in color)

    @staticmethod
    def _draw_star(surface, center, outer: int, inner: int, fill, outline) -> None:
        points = []
        for i in range(10):
            radius = outer if i % 2 == 0 else inner
            angle = -math.pi / 2 + i * math.pi / 5
            points.append(
                (
                    center[0] + math.cos(angle) * radius,
                    center[1] + math.sin(angle) * radius,
                )
            )
        pygame.draw.polygon(surface, fill, points)
        pygame.draw.polygon(surface, outline, points, 2)

    @staticmethod
    def _draw_snake_eyes(surface, rect: pygame.Rect, direction: str) -> None:
        offsets = {
            DIR_RIGHT: ((5, -4), (5, 4)),
            DIR_LEFT: ((-5, -4), (-5, 4)),
            DIR_UP: ((-4, -5), (4, -5)),
            DIR_DOWN: ((-4, 5), (4, 5)),
        }.get(direction, ((5, -4), (5, 4)))
        for dx, dy in offsets:
            eye = (rect.centerx + dx, rect.centery + dy)
            pygame.draw.circle(surface, (245, 250, 255), eye, 3)
            pygame.draw.circle(surface, (8, 18, 24), eye, 1)

    @staticmethod
    def _draw_hit_burst(surface, rect: pygame.Rect, burst_ticks: int) -> None:
        extent = 6 + burst_ticks
        color = (255, 248, 232) if burst_ticks % 2 == 0 else (255, 184, 130)
        cx, cy = rect.center
        pygame.draw.line(surface, color, (cx - extent, cy), (cx + extent, cy), 2)
        pygame.draw.line(surface, color, (cx, cy - extent), (cx, cy + extent), 2)
        pygame.draw.line(surface, color, (cx - extent + 2, cy - extent + 2), (cx + extent - 2, cy + extent - 2), 1)
        pygame.draw.line(surface, color, (cx - extent + 2, cy + extent - 2), (cx + extent - 2, cy - extent + 2), 1)
