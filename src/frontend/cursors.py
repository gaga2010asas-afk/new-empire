# src/frontend/cursors.py
"""
CursorRenderer — кастомный курсор поверх всего Z-порядка.
Зона: src/frontend/.

Канон v1.5 §1: системная мышь ОС скрыта — курсор рисует игра.
Канон v1.5 §2: курсоры общие (assets/ui/cursors/), без фракционного деления.
Канон v1.5 §1: слой 2 (Скалы/Лес) — коллизия.

Логика:
  Мышь над тайлом, где get_tile_at(2, x, y) >= 0 → коллизия → 'attack' (красный прицел).
  Иначе → 'normal' (золотая стрелка).
"""

from __future__ import annotations

import pygame

from .renderer import HP_BAR_HEIGHT


# --- Имена файлов курсоров в assets/ui/cursors/ ---
CURSOR_NORMAL: str = "normal"
CURSOR_ATTACK: str = "attack"

# Технический fallback — только если PNG отсутствует. Не художественный ассет.
FALLBACK_GOLD: tuple[int, int, int] = (255, 210, 70)
FALLBACK_GOLD_OUTLINE: tuple[int, int, int] = (60, 40, 0)
FALLBACK_RED: tuple[int, int, int] = (220, 30, 30)


class CursorRenderer:
    """Рисует курсор мыши. Ничего не знает о юнитах, бое, экономике."""

    def __init__(
        self,
        normal_key: str = CURSOR_NORMAL,
        collision_key: str = CURSOR_ATTACK,
    ) -> None:
        self.normal_key: str = normal_key
        self.collision_key: str = collision_key

    # --- выбор курсора -------------------------------------------------------
    def pick_cursor_key(self, map_data, tile_x: int, tile_y: int) -> str:
        """Вернуть ключ курсора для тайла. Слой 2 → коллизия."""
        if 0 <= tile_x < map_data.width and 0 <= tile_y < map_data.height:
            layer2_idx = map_data.get_tile_at(2, tile_x, tile_y)
            if layer2_idx is not None and layer2_idx >= 0:
                return self.collision_key
        return self.normal_key

    # --- отрисовка ------------------------------------------------------------
    def render(
        self,
        surface: pygame.Surface,
        mouse_pos: tuple[int, int],
        map_data,
        camera,
        assets,
    ) -> None:
        """Отрисовать курсор поверх всего. mouse_pos — экранные координаты."""
        mx, my = int(mouse_pos[0]), int(mouse_pos[1])

        tile_x, tile_y = camera.screen_to_tile(mx, my)
        cursor_key = self.pick_cursor_key(map_data, tile_x, tile_y)

        cursor_surf = assets.get_cursor(cursor_key)
        if cursor_surf is None:
            # PNG отсутствует — технический fallback, чтобы игрок видел позицию.
            self._draw_fallback(surface, mx, my, cursor_key)
            return
        surface.blit(cursor_surf, (mx, my))

    # --- технический fallback -----------------------------------------------
    def _draw_fallback(
        self, surface: pygame.Surface, x: int, y: int, cursor_key: str
    ) -> None:
        """Временный примитив, если PNG курсора не загружен. Не заменяет арт."""
        if cursor_key == self.collision_key:
            pygame.draw.circle(surface, FALLBACK_RED, (x, y), 10, 2)
            pygame.draw.line(surface, FALLBACK_RED, (x - 14, y), (x + 14, y), 2)
            pygame.draw.line(surface, FALLBACK_RED, (x, y - 14), (x, y + 14), 2)
            return

        pts = [
            (x, y),
            (x, y + 16),
            (x + 4, y + 12),
            (x + 8, y + 18),
            (x + 11, y + 16),
            (x + 7, y + 10),
            (x + 12, y + 9),
        ]
        pygame.draw.polygon(surface, FALLBACK_GOLD, pts)
        pygame.draw.polygon(surface, FALLBACK_GOLD_OUTLINE, pts, 1)