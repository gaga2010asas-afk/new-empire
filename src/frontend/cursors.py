# src/frontend/cursors.py
"""
CursorRenderer — кастомный курсор поверх всего Z-порядка. Прототип №4/№8.
Зона: src/frontend/.

Канон v1.5.1 §1: системная мышь ОС скрыта — курсор рисует игра.
Канон v1.5 §2: курсоры общие (assets/ui/cursors/), без faction.
Канон v1.5.1 §1: слой 2 (Скалы/Лес) — коллизия.
Канон (фикс размера): курсор рисуется в РАЗМЕРЕ по умолчанию 32x32.
               AssetLoader.load_cursors() уже нормализует PNG —
               CursorRenderer не создаёт Surface в кадре.
"""

from __future__ import annotations

import pygame


# --- Имена файлов курсоров в assets/ui/cursors/ ---
CURSOR_NORMAL: str = "normal"
CURSOR_ATTACK: str = "attack"

# Целевой размер отрисовки курсора (px).
DEFAULT_CURSOR_DRAW_SIZE: int = 32

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
        draw_size: int = DEFAULT_CURSOR_DRAW_SIZE,
    ) -> None:
        self.normal_key: str = normal_key
        self.collision_key: str = collision_key
        self.draw_size: int = int(draw_size)

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
        mx, my = int(mouse_pos[0]), int(mouse_pos[1])

        tile_x, tile_y = camera.screen_to_tile(mx, my)
        cursor_key = self.pick_cursor_key(map_data, tile_x, tile_y)

        cursor_surf = assets.get_cursor(cursor_key)
        if cursor_surf is None:
            # PNG отсутствует — технический fallback, чтобы игрок видел позицию.
            self._draw_fallback(surface, mx, my, cursor_key)
            return

        # Гарантия размера: если asset_loader не нормализовал (старая версия),
        # ужимаем прямо здесь. Кэш — по identity surface, чтобы не плодить копии.
        target = self.draw_size
        if target > 0 and cursor_surf.get_size() != (target, target):
            cached = getattr(self, "_scaled_cache", None)
            if cached is None or cached[0] is not cursor_surf:
                scaled = pygame.transform.smoothscale(cursor_surf, (target, target))
                self._scaled_cache = (cursor_surf, scaled)
            cursor_surf = self._scaled_cache[1]

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