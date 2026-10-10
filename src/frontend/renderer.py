# src/frontend/renderer.py
"""
Renderer — послойная отрисовка. Прототип №7.
Зона: src/frontend/.

Канон v1.5.21: _tint_cache по ключу (id(surface), tint).
Канон v1.5.23: каскад тинта явно в render_units ПЕРЕД blit.
Канон v1.5.4:  карта читается через map_data.get_tile_at(layer, x, y) -> int.
Канон (индексация ландшафта): LANDSCAPE_TO_TILE транслирует код слоя
               (0 земля / 1 вода / 2 скалы-лес) в индекс тайла summer_hd.png.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from .camera import TILE_SIZE


# --- HP / progress bar ---
HP_BAR_WIDTH_RATIO: float = 0.5
HP_BAR_HEIGHT: int = 4
HP_BAR_BG: tuple[int, int, int] = (20, 20, 20)
HP_BAR_FG: tuple[int, int, int] = (60, 200, 60)
HP_BAR_FG_LOW: tuple[int, int, int] = (220, 80, 40)
HP_BAR_LOW_THRESHOLD: float = 0.33

PROGRESS_BAR_HEIGHT: int = 6
PROGRESS_BAR_BG: tuple[int, int, int] = (20, 20, 20)
PROGRESS_BAR_FG: tuple[int, int, int] = (220, 180, 60)

SHADOW_OFFSET_Y: int = 6

# --- Кольцо выделения ---
SELECTION_RING_COLOR: tuple[int, int, int] = (60, 230, 60)
SELECTION_RING_WIDTH: int = 2
SELECTION_RING_W_RATIO: float = 0.55
SELECTION_RING_H_RATIO: float = 0.22

# --- Tint рейдеров ---
RAIDER_TINT_HUMAN: tuple[int, int, int] = (80, 80, 255)
RAIDER_TINT_ORC: tuple[int, int, int] = (255, 80, 80)

# --- Штандарт ---
BANNER_PULSE_SPEED: float = 0.15
BANNER_RING_W_RATIO: float = 0.62
BANNER_RING_H_RATIO: float = 0.26
BANNER_RING_WIDTH: int = 3
BANNER_FLAG_HEIGHT: int = 14
BANNER_FLAG_WIDTH: int = 14
BANNER_COLUMN_MARKER_SIZE: int = 6
BANNER_COLUMN_PULSE_SPEED: float = 0.2

# --- Debug ---
DEBUG_ROAD_COLORS: dict[int, tuple[int, int, int]] = {
    1: (90, 80, 40), 2: (150, 130, 60), 3: (220, 190, 80),
}
DEBUG_ROAD_ALPHA: int = 90

# --- Анимация ---
ANIM_FRAME_TICKS: int = 8

# --- Стейты юнита ---
STATE_IDLE: int = 0
STATE_WALK: int = 1
STATE_MINE: int = 2
STATE_ATTACK: int = 3
STATE_BUILD: int = 4
STATE_DEAD: int = 5
STATE_RETURN: int = 6

# --- Стейты здания ---
BUILDING_CONSTRUCTING: int = 0
BUILDING_ACTIVE: int = 1
BUILDING_DAMAGED: int = 2
BUILDING_DESTROYED: int = 3

STATE_TO_ANIM: dict[int, str] = {
    STATE_IDLE: "idle",
    STATE_WALK: "walk",
    STATE_MINE: "mine",
    STATE_ATTACK: "attack",
    STATE_BUILD: "build",
    STATE_DEAD: "death",
    STATE_RETURN: "walk",
}


# --- Маппинг слоя проходимости → индекс тайла summer_hd.png ---
# Backend возвращает КОД слоя (0/1/2), а не индекс текстуры.
# Здесь переводим код в индекс тайла для рендера.
# TODO: Подобрать точные индексы фреймов после финальной визуальной проверки.
LANDSCAPE_TO_TILE: dict[int, int] = {
    0: 30,    # Слой 0 (Земля/Трава) -> тайл травы
    1: 200,   # Слой 1 (Вода/Море)   -> тайл чистой воды
    2: 350,   # Слой 2 (Скалы/Лес)   -> тайл непроходимых гор
}


@dataclass
class BannerRenderState:
    """View-model Штандарта для рендера. Собирается в main.py."""
    assigned_hero_id: int = -1
    mobilized_unit_ids: tuple[int, ...] = ()
    state: int = 0

    @property
    def is_active(self) -> bool:
        return self.assigned_hero_id >= 0


class Renderer:
    def __init__(self, tile_size: int = TILE_SIZE) -> None:
        self.tile_size: int = int(tile_size)
        self._tint_cache: dict[tuple[int, tuple[int, int, int]], pygame.Surface] = {}
        self._tint_sources: dict[tuple[int, tuple[int, int, int]], pygame.Surface] = {}

    # --- видимый диапазон ----------------------------------------------------
    def visible_tile_bounds(
        self, camera, viewport_w: int, viewport_h: int, map_w: int, map_h: int
    ) -> tuple[int, int, int, int]:
        ts = self.tile_size
        cam_x, cam_y = camera.camera_x, camera.camera_y
        first_tx = max(0, int(cam_x // ts))
        first_ty = max(0, int(cam_y // ts))
        last_tx = min(map_w - 1, int((cam_x + viewport_w - 1) // ts))
        last_ty = min(map_h - 1, int((cam_y + viewport_h - 1) // ts))
        return (first_tx, first_ty, last_tx, last_ty)

    @staticmethod
    def _is_visible(sx: int, sy: int, w: int, h: int, vw: int, vh: int) -> bool:
        return not (sx + w < 0 or sy + h < 0 or sx > vw or sy > vh)

    # --- tint (v1.5.23) ------------------------------------------------------
    def _tinted_surface(
        self, surface: pygame.Surface, tint: tuple[int, int, int]
    ) -> pygame.Surface:
        """Аппаратный ADD-tint с кэшем по (id(surface), tint)."""
        r = int(max(0, min(255, tint[0])))
        g = int(max(0, min(255, tint[1])))
        b = int(max(0, min(255, tint[2])))
        key: tuple[int, tuple[int, int, int]] = (id(surface), (r, g, b))

        cached = self._tint_cache.get(key)
        if cached is not None and self._tint_sources.get(key) is surface:
            return cached

        result = surface.copy()
        alpha = surface.get_alpha()
        result.fill((r, g, b, 255), special_flags=pygame.BLEND_RGB_ADD)
        if alpha is not None:
            result.set_alpha(alpha)

        self._tint_cache[key] = result
        self._tint_sources[key] = surface
        return result

    def _unit_tint(self, u) -> tuple[int, int, int] | None:
        """Вспомогательный helper. Основной каскад — в render_units."""
        tint = getattr(u, "tint", None)
        if tint is not None:
            try:
                r, g, b = (int(c) for c in tint[:3])
                if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                    return (r, g, b)
            except (TypeError, ValueError):
                pass
        stats = getattr(u, "stats", None)
        if isinstance(stats, dict):
            stats_tint = stats.get("tint")
            if stats_tint is not None:
                try:
                    r, g, b = (int(c) for c in stats_tint[:3])
                    if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                        return (r, g, b)
                except (TypeError, ValueError):
                    pass
            if stats.get("is_raider"):
                faction = str(getattr(u, "faction", "human")).lower()
                return RAIDER_TINT_ORC if faction == "orc" else RAIDER_TINT_HUMAN
        return None

    def _get_mobilized_set(self, ids_tuple: tuple[int, ...]) -> set[int]:
        return set(ids_tuple)

    # --- земля (с маппингом слоя → индекс тайла) -----------------------------
    def render_world(self, surface, camera, map_data, assets, layer: int = 0) -> None:
        vw, vh = surface.get_size()
        first_tx, first_ty, last_tx, last_ty = self.visible_tile_bounds(
            camera, vw, vh, map_data.width, map_data.height
        )
        for ty in range(first_ty, last_ty + 1):
            for tx in range(first_tx, last_tx + 1):
                idx = map_data.get_tile_at(layer, tx, ty)
                if idx is None or idx < 0:
                    continue

                # Превращаем код слоя бэкенда в реальный индекс текстуры WC2.
                tile_idx = LANDSCAPE_TO_TILE.get(idx, idx)
                tile_surf = assets.get_tile(tile_idx)
                if tile_surf is None:
                    continue
                sx, sy = camera.tile_to_screen(tx, ty)
                surface.blit(tile_surf, (sx, sy))

    # --- тени ----------------------------------------------------------------
    def render_shadows(self, surface, camera, units, buildings, assets) -> None:
        vw, vh = surface.get_size()
        w_u = int(self.tile_size * 0.5)
        h_u = int(self.tile_size * 0.2)
        shadow_u = assets.get_shadow_ellipse(w_u, h_u)
        for u in units:
            sx, sy = camera.world_to_screen(u.pixel_x, u.pixel_y)
            bx = sx - w_u // 2
            by = sy - h_u // 2 + SHADOW_OFFSET_Y
            if self._is_visible(bx, by, w_u, h_u, vw, vh):
                surface.blit(shadow_u, (bx, by))
        for b in buildings:
            sx, sy = camera.world_to_screen(b.grid_x * self.tile_size, b.grid_y * self.tile_size)
            w_b = b.width * self.tile_size
            h_b = int(self.tile_size * 0.25)
            shadow_b = assets.get_shadow_ellipse(w_b, h_b)
            by = sy + b.height * self.tile_size - h_b // 2
            if self._is_visible(sx, by, w_b, h_b, vw, vh):
                surface.blit(shadow_b, (sx, by))

    def render_hero_auras(self, surface, camera, units, aura_renderer) -> None:
        if aura_renderer is None:
            return
        aura_renderer.render(surface, camera, units)

    def render_selection_rings(self, surface, camera, units) -> None:
        vw, vh = surface.get_size()
        ring_w = int(self.tile_size * SELECTION_RING_W_RATIO)
        ring_h = int(self.tile_size * SELECTION_RING_H_RATIO)
        for u in units:
            if not getattr(u, "is_selected", False):
                continue
            if u.state == STATE_DEAD:
                continue
            sx, sy = camera.world_to_screen(u.pixel_x, u.pixel_y)
            feet_y = sy + self.tile_size // 2
            rect = pygame.Rect(sx - ring_w // 2, feet_y - ring_h // 2, ring_w, ring_h)
            if not self._is_visible(rect.x, rect.y, rect.w, rect.h, vw, vh):
                continue
            pygame.draw.ellipse(surface, SELECTION_RING_COLOR, rect, SELECTION_RING_WIDTH)

    def render_buildings(self, surface, camera, buildings, assets) -> None:
        vw, vh = surface.get_size()
        for b in buildings:
            sprite = assets.get_building_frame(b.type, 0)
            if sprite is None:
                continue
            sx, sy = camera.world_to_screen(b.grid_x * self.tile_size, b.grid_y * self.tile_size)
            w, h = sprite.get_size()
            if not self._is_visible(sx, sy, w, h, vw, vh):
                continue
            surface.blit(sprite, (sx, sy))

    # --- юниты (v1.5.23: каскад тинта внедрён прямо перед blit) -------------
    def render_units(self, surface, camera, units, assets, tick: int = 0) -> None:
        vw, vh = surface.get_size()
        ordered = sorted(
            units,
            key=lambda u: (float(u.pixel_y), int(getattr(u, "id", 0) or 0)),
        )
        for unit in ordered:
            anim_name = STATE_TO_ANIM.get(unit.state, "idle")
            frames = assets.get_unit_frames(unit.type, anim_name, unit.direction)
            if not frames:
                frames = assets.get_unit_frames(unit.type, "idle", unit.direction)
            if not frames:
                continue
            uid = getattr(unit, "id", 0) or 0
            frame_index = ((tick // ANIM_FRAME_TICKS) + int(uid)) % len(frames)
            sprite = frames[frame_index]

            # === v1.5.23: каскад определения тинта ПЕРЕД blit ===
            tint = getattr(unit, "tint", None)
            if tint is None and hasattr(unit, "stats") and isinstance(unit.stats, dict):
                tint = unit.stats.get("tint")
            if (
                tint is None
                and hasattr(unit, "stats")
                and isinstance(unit.stats, dict)
                and unit.stats.get("is_raider")
            ):
                tint = (80, 80, 255) if unit.faction == "human" else (255, 80, 80)
            if tint is not None:
                sprite = self._tinted_surface(sprite, tint)
            # === /каскад ===

            sx, sy = camera.world_to_screen(unit.pixel_x, unit.pixel_y)
            w, h = sprite.get_size()
            draw_x = sx - w // 2
            draw_y = sy - h + self.tile_size // 2
            if not self._is_visible(draw_x, draw_y, w, h, vw, vh):
                continue
            surface.blit(sprite, (draw_x, draw_y))

    def render_banner_hero_indicator(
        self, surface, camera, units, banner_state, tick: int = 0
    ) -> None:
        if banner_state is None or not banner_state.is_active:
            return
        hero_id = banner_state.assigned_hero_id
        # TODO_OPTIMIZATION: Перевести на индексированный словарь O(1) в main.py
        hero = None
        for u in units:
            if getattr(u, "id", -1) == hero_id and u.state != STATE_DEAD:
                hero = u
                break
        if hero is None:
            return

        vw, vh = surface.get_size()
        sx, sy = camera.world_to_screen(hero.pixel_x, hero.pixel_y)
        feet_y = sy + self.tile_size // 2

        pulse = (math.sin(tick * BANNER_PULSE_SPEED) + 1.0) * 0.5
        brightness = 0.55 + 0.45 * pulse
        color = (int(255 * brightness), int(210 * brightness), int(70 * brightness))

        ring_w = int(self.tile_size * BANNER_RING_W_RATIO)
        ring_h = int(self.tile_size * BANNER_RING_H_RATIO)
        ring_rect = pygame.Rect(sx - ring_w // 2, feet_y - ring_h // 2, ring_w, ring_h)
        if self._is_visible(ring_rect.x, ring_rect.y, ring_rect.w, ring_rect.h, vw, vh):
            pygame.draw.ellipse(surface, color, ring_rect, BANNER_RING_WIDTH)

        pole_bottom = sy - self.tile_size // 2 - 4
        pole_top = pole_bottom - BANNER_FLAG_HEIGHT - 6
        if self._is_visible(sx - 2, pole_top, 20, BANNER_FLAG_HEIGHT + 8, vw, vh):
            pygame.draw.line(surface, (240, 220, 180), (sx, pole_top), (sx, pole_bottom), 2)
            flag_pts = [
                (sx, pole_top),
                (sx + BANNER_FLAG_WIDTH, pole_top + BANNER_FLAG_HEIGHT // 2),
                (sx, pole_top + BANNER_FLAG_HEIGHT),
            ]
            pygame.draw.polygon(surface, color, flag_pts)

    def render_column_markers(
        self, surface, camera, units, banner_state, tick: int = 0
    ) -> None:
        if banner_state is None or not banner_state.is_active:
            return
        ids = self._get_mobilized_set(banner_state.mobilized_unit_ids)
        if not ids:
            return

        pulse = (math.sin(tick * BANNER_COLUMN_PULSE_SPEED) + 1.0) * 0.5
        brightness = 0.65 + 0.35 * pulse
        color = (int(255 * brightness), int(230 * brightness), int(90 * brightness))

        vw, vh = surface.get_size()
        size = BANNER_COLUMN_MARKER_SIZE

        for u in units:
            if getattr(u, "id", -1) not in ids:
                continue
            if u.state == STATE_DEAD:
                continue
            sx, sy = camera.world_to_screen(u.pixel_x, u.pixel_y)
            marker_x = sx
            marker_y = sy - self.tile_size // 2 - 4
            if not self._is_visible(marker_x - size, marker_y - size, size * 2, size * 2, vw, vh):
                continue
            pts = [
                (marker_x, marker_y),
                (marker_x - size, marker_y - size),
                (marker_x + size, marker_y - size),
            ]
            pygame.draw.polygon(surface, color, pts)

    def render_projectiles(self, surface, camera, projectiles, assets) -> None:
        vw, vh = surface.get_size()
        for p in projectiles:
            sprite = assets.get_projectile_sprite(getattr(p, "type", ""))
            if sprite is None:
                sprite = assets.get_projectile_sprite(getattr(p, "sprite_key", ""))
            if sprite is None:
                continue
            sx, sy = camera.world_to_screen(p.pixel_x, p.pixel_y)
            w, h = sprite.get_size()
            draw_x = sx - w // 2
            draw_y = sy - h // 2
            if not self._is_visible(draw_x, draw_y, w, h, vw, vh):
                continue
            surface.blit(sprite, (draw_x, draw_y))

    def render_fx(self, surface, camera, fx_pool) -> None:
        if fx_pool is None:
            return
        fx_pool.render(surface, camera)

    def render_hp_bars(self, surface, camera, units, buildings) -> None:
        vw, vh = surface.get_size()
        for u in units:
            if u.state == STATE_DEAD:
                continue
            if u.max_hp <= 0 or u.hp >= u.max_hp:
                continue
            sx, sy = camera.world_to_screen(u.pixel_x, u.pixel_y)
            w = int(self.tile_size * HP_BAR_WIDTH_RATIO)
            bx = sx - w // 2
            by = sy - self.tile_size // 2 - HP_BAR_HEIGHT - 2
            if not self._is_visible(bx, by, w, HP_BAR_HEIGHT, vw, vh):
                continue
            self._draw_hp_bar_at(surface, bx, by, u.hp, u.max_hp, w)
        for b in buildings:
            if b.state == BUILDING_DESTROYED:
                continue
            if b.max_hp <= 0 or b.hp >= b.max_hp:
                continue
            sx, sy = camera.world_to_screen(b.grid_x * self.tile_size, b.grid_y * self.tile_size)
            w = b.width * self.tile_size
            bx, by = sx, sy - HP_BAR_HEIGHT - 2
            if not self._is_visible(bx, by, w, HP_BAR_HEIGHT, vw, vh):
                continue
            self._draw_hp_bar_at(surface, bx, by, b.hp, b.max_hp, w)

    def _draw_hp_bar_at(self, surface, x, y, hp, max_hp, width, height=HP_BAR_HEIGHT) -> None:
        if max_hp <= 0 or hp >= max_hp or width <= 0:
            return
        hp = max(0, hp)
        ratio = hp / max_hp
        fg = HP_BAR_FG_LOW if ratio < HP_BAR_LOW_THRESHOLD else HP_BAR_FG
        pygame.draw.rect(surface, HP_BAR_BG, (x, y, width, height))
        pygame.draw.rect(surface, fg, (x, y, int(width * ratio), height))

    def draw_hp_bar(self, surface, x, y, hp, max_hp, width=None, height=HP_BAR_HEIGHT) -> None:
        if max_hp <= 0 or hp >= max_hp:
            return
        w = width if width is not None else int(self.tile_size * HP_BAR_WIDTH_RATIO)
        self._draw_hp_bar_at(surface, x, y, hp, max_hp, w, height)

    def render_progress_bars(self, surface, camera, buildings) -> None:
        vw, vh = surface.get_size()
        for b in buildings:
            if b.state != BUILDING_CONSTRUCTING:
                continue
            progress = max(0.0, min(1.0, float(getattr(b, "build_progress", 0.0))))
            sx, sy = camera.world_to_screen(b.grid_x * self.tile_size, b.grid_y * self.tile_size)
            w = b.width * self.tile_size
            bx, by = sx, sy - PROGRESS_BAR_HEIGHT - 2
            if not self._is_visible(bx, by, w, PROGRESS_BAR_HEIGHT, vw, vh):
                continue
            pygame.draw.rect(surface, PROGRESS_BAR_BG, (bx, by, w, PROGRESS_BAR_HEIGHT))
            pygame.draw.rect(
                surface, PROGRESS_BAR_FG,
                (bx, by, int(w * progress), PROGRESS_BAR_HEIGHT),
            )

    def render_roads_debug(self, surface, camera, map_data) -> None:
        vw, vh = surface.get_size()
        first_tx, first_ty, last_tx, last_ty = self.visible_tile_bounds(
            camera, vw, vh, map_data.width, map_data.height
        )
        ts = self.tile_size
        for ty in range(first_ty, last_ty + 1):
            for tx in range(first_tx, last_tx + 1):
                level = map_data.get_road_at(tx, ty)
                if not level or level <= 0:
                    continue
                color = DEBUG_ROAD_COLORS.get(int(level))
                if color is None:
                    continue
                sx, sy = camera.tile_to_screen(tx, ty)
                overlay = pygame.Surface((ts, ts), pygame.SRCALPHA)
                overlay.fill((*color, DEBUG_ROAD_ALPHA))
                surface.blit(overlay, (sx, sy))

    def render_scene(
        self,
        surface,
        camera,
        map_data,
        assets,
        units,
        buildings,
        projectiles=None,
        fx_pool=None,
        aura_renderer=None,
        banner_state=None,
        layer: int = 0,
        tick: int = 0,
        debug_roads: bool = False,
    ) -> None:
        self.render_world(surface, camera, map_data, assets, layer=layer)
        if debug_roads:
            self.render_roads_debug(surface, camera, map_data)
        self.render_shadows(surface, camera, units, buildings, assets)
        self.render_hero_auras(surface, camera, units, aura_renderer)
        self.render_selection_rings(surface, camera, units)
        self.render_buildings(surface, camera, buildings, assets)
        self.render_units(surface, camera, units, assets, tick=tick)
        self.render_column_markers(surface, camera, units, banner_state, tick=tick)
        self.render_banner_hero_indicator(surface, camera, units, banner_state, tick=tick)
        if projectiles:
            self.render_projectiles(surface, camera, projectiles, assets)
        self.render_fx(surface, camera, fx_pool)
        self.render_hp_bars(surface, camera, units, buildings)
        self.render_progress_bars(surface, camera, buildings)