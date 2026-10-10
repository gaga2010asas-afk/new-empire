# src/frontend/camera.py
"""
Camera — смещение мира в пикселях для NEW EMPIRE (Прототип №1 «Клетка»).
Зона: src/frontend/. Скролл и кламп — только отображение.

Канон v1.5 §1: WASD/стрелки + автопрокрутка у краёв (20 px), dt-масштаб,
TILE_SIZE=128, карты 64x64 … 1024x1024.
Канон v1.5 §7: логические (тайлы) → мировые (пиксели) → экранные (world − camera).
"""

from __future__ import annotations

import pygame


# --- Канон v1.5 §1 (зеркало backend/constants.py, без импорта) ---
TILE_SIZE: int = 128
EDGE_MARGIN: int = 20
KEY_SCROLL_SPEED_DEFAULT: float = 640.0
EDGE_SCROLL_SPEED_DEFAULT: float = 800.0
TARGET_FPS: int = 60
DEFAULT_DT: float = 1.0 / TARGET_FPS


class Camera:
    """Хранит camera_x, camera_y — пиксельные координаты левого верхнего угла."""

    def __init__(
        self,
        viewport_w: int,
        viewport_h: int,
        tile_size: int = TILE_SIZE,
        edge_margin: int = EDGE_MARGIN,
        key_scroll_speed: float = KEY_SCROLL_SPEED_DEFAULT,
        edge_scroll_speed: float = EDGE_SCROLL_SPEED_DEFAULT,
    ) -> None:
        self.viewport_w: int = int(viewport_w)
        self.viewport_h: int = int(viewport_h)
        self.tile_size: int = int(tile_size)
        self.edge_margin: int = int(edge_margin)
        self.key_scroll_speed: float = float(key_scroll_speed)
        self.edge_scroll_speed: float = float(edge_scroll_speed)

        self.camera_x: float = 0.0
        self.camera_y: float = 0.0

    # --- вьюпорт --------------------------------------------------------------
    def set_viewport(self, w: int, h: int) -> None:
        self.viewport_w = int(w)
        self.viewport_h = int(h)

    def get_viewport(self) -> tuple[int, int]:
        return (self.viewport_w, self.viewport_h)

    # --- скролл ---------------------------------------------------------------
    def update(
        self,
        mouse_pos: tuple[int, int],
        keys_pressed,
        dt: float | None = None,
    ) -> None:
        """Сдвинуть камеру за кадр. dt в секундах; None → 1/60."""
        if dt is None:
            dt = DEFAULT_DT

        dx = 0.0
        dy = 0.0

        # Клавиатура: WASD / стрелки
        if keys_pressed[pygame.K_a] or keys_pressed[pygame.K_LEFT]:
            dx -= self.key_scroll_speed
        if keys_pressed[pygame.K_d] or keys_pressed[pygame.K_RIGHT]:
            dx += self.key_scroll_speed
        if keys_pressed[pygame.K_w] or keys_pressed[pygame.K_UP]:
            dy -= self.key_scroll_speed
        if keys_pressed[pygame.K_s] or keys_pressed[pygame.K_DOWN]:
            dy += self.key_scroll_speed

        # Края вьюпорта
        mx, my = mouse_pos
        if mx < self.edge_margin:
            dx -= self.edge_scroll_speed
        elif mx > self.viewport_w - self.edge_margin:
            dx += self.edge_scroll_speed
        if my < self.edge_margin:
            dy -= self.edge_scroll_speed
        elif my > self.viewport_h - self.edge_margin:
            dy += self.edge_scroll_speed

        self.camera_x += dx * dt
        self.camera_y += dy * dt

    # --- границы --------------------------------------------------------------
    def clamp(self, map_w: int, map_h: int) -> None:
        """map_w, map_h — размер карты в ТАЙЛАХ (канон: 64…1024)."""
        world_w = map_w * self.tile_size
        world_h = map_h * self.tile_size

        max_x = max(0, world_w - self.viewport_w)
        max_y = max(0, world_h - self.viewport_h)

        if self.camera_x < 0.0:
            self.camera_x = 0.0
        elif self.camera_x > max_x:
            self.camera_x = float(max_x)

        if self.camera_y < 0.0:
            self.camera_y = 0.0
        elif self.camera_y > max_y:
            self.camera_y = float(max_y)

    # --- преобразования координат --------------------------------------------
    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        return (int(wx - self.camera_x), int(wy - self.camera_y))

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return (sx + self.camera_x, sy + self.camera_y)

    def screen_to_tile(self, sx: float, sy: float) -> tuple[int, int]:
        wx, wy = self.screen_to_world(sx, sy)
        return (int(wx // self.tile_size), int(wy // self.tile_size))

    def tile_to_screen(self, tx: int, ty: int) -> tuple[int, int]:
        return self.world_to_screen(tx * self.tile_size, ty * self.tile_size)

    def snap_offsets(self) -> tuple[int, int]:
        return (int(self.camera_x), int(self.camera_y))