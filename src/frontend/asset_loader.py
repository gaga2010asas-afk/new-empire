# src/frontend/asset_loader.py
"""
AssetLoader — тайлсет, курсоры, спрайты, снаряды, взрывы, иконки спеллов, кэш теней.
Зона: src/frontend/.

Канон v1.5.1 §2: тень кэшируется, Surface в кадре не создаётся.
Канон v1.5 §2: типы снарядов — "arrow", "axe", "ballista_bolt", "cannon_ball".
Канон v1.5 §2: взрывы — assets/fx/explosions/.
Канон v1.5.16 №16: сетка нарезки СЧИТАЕТСЯ ДИНАМИЧЕСКИ из размера файла
                   (без хардкода 16×24 / 2048×3072 / 2560×3840).
Канон v1.5.16 №15: имя файла ландшафта — summer_hd.png.

[НЕТ ДАННЫХ]:
- Формат assets/fx/explosions/ — поддержаны каталог PNG и лист.
- Имена файлов взрывов и снарядов — задаются снаружи через ключи.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import pygame


log = logging.getLogger(__name__)

# --- Канон v1.5 §1: размер одного тайла (священное число) ---
TILE_SIZE: int = 128

DEFAULT_TERRAIN_PATH: str = "assets/terrain/summer_hd.png"
DEFAULT_CURSORS_DIR: str = "assets/ui/cursors"
DEFAULT_EXPLOSIONS_DIR: str = "assets/fx/explosions"
DEFAULT_PROJECTILES_DIR: str = "assets/fx/projectiles"
DEFAULT_SPELL_ICONS_DIR: str = "assets/ui/spells"


@dataclass
class AnimSpec:
    """Раскладка одной анимации в спрайт-листе."""
    row: int
    frame_count: int
    directions: int = 1


class AssetLoader:
    """Загружает ассеты. Логики мира нет."""

    def __init__(self, tile_size: int = TILE_SIZE) -> None:
        self.tile_size: int = int(tile_size)
        self._terrain_sheet: pygame.Surface | None = None
        self.terrain_tiles: list[pygame.Surface] = []
        self.terrain_cols: int = 0
        self.terrain_rows: int = 0

        self.cursors: dict[str, pygame.Surface] = {}
        self.unit_sheets: dict[str, dict[str, list[list[pygame.Surface]]]] = {}
        self.building_sheets: dict[str, list[pygame.Surface]] = {}
        self.building_size: dict[str, tuple[int, int]] = {}

        self.explosion_frames: dict[str, list[pygame.Surface]] = {}
        self.projectile_sprites: dict[str, pygame.Surface] = {}
        self.spell_icons: dict[str, pygame.Surface] = {}

        self._shadow_cache: dict[tuple[int, int], pygame.Surface] = {}

    # --- тайлсет -------------------------------------------------------------
    def load_terrain(self, path: str = DEFAULT_TERRAIN_PATH) -> None:
        """Нарезать summer_hd.png. Сетка рассчитывается динамически (v1.5.16 №16)."""
        if not os.path.isfile(path):
            raise FileNotFoundError(f"[НЕТ ДАННЫХ] тайлсет не найден: {path}")
        sheet = pygame.image.load(path).convert_alpha()
        sw, sh = sheet.get_size()
        ts = self.tile_size

        cols = sw // ts
        rows = sh // ts
        if cols < 1 or rows < 1:
            raise ValueError(
                f"Тайлсет {sw}x{sh} меньше одного тайла {ts}x{ts}"
            )
        if sw % ts != 0 or sh % ts != 0:
            log.warning(
                "Размер тайлсета %dx%d не кратен TILE_SIZE=%d — правый/нижний край обрезан.",
                sw, sh, ts,
            )

        self._terrain_sheet = sheet
        self.terrain_cols = cols
        self.terrain_rows = rows

        tiles: list[pygame.Surface] = []
        for r in range(rows):
            for c in range(cols):
                tiles.append(sheet.subsurface(pygame.Rect(c * ts, r * ts, ts, ts)))
        self.terrain_tiles = tiles

    def get_tile(self, index: int) -> pygame.Surface | None:
        if index is None or index < 0 or index >= len(self.terrain_tiles):
            return None
        return self.terrain_tiles[index]

    def tile_count(self) -> int:
        return len(self.terrain_tiles)

    # --- курсоры -------------------------------------------------------------
    def load_cursors(self, directory: str = DEFAULT_CURSORS_DIR) -> None:
        self.cursors = {}
        if not os.path.isdir(directory):
            log.warning("Директория курсоров отсутствует: %s", directory)
            return
        for name in sorted(os.listdir(directory)):
            if not name.lower().endswith(".png"):
                continue
            path = os.path.join(directory, name)
            try:
                surf = pygame.image.load(path).convert_alpha()
            except pygame.error as exc:
                log.warning("Не удалось загрузить курсор %s: %s", path, exc)
                continue
            self.cursors[os.path.splitext(name)[0]] = surf

    def get_cursor(self, key: str) -> pygame.Surface | None:
        return self.cursors.get(key)

    # --- спрайты юнитов ------------------------------------------------------
    def load_unit_sheet(
        self,
        key: str,
        path: str,
        frame_w: int,
        frame_h: int,
        anims: dict[str, AnimSpec],
    ) -> None:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"[НЕТ ДАННЫХ] лист юнита не найден: {path}")
        sheet = pygame.image.load(path).convert_alpha()
        sheet_w, sheet_h = sheet.get_size()
        slots: dict[str, list[list[pygame.Surface]]] = {}
        for anim_name, spec in anims.items():
            per_dir: list[list[pygame.Surface]] = []
            for d in range(spec.directions):
                frames: list[pygame.Surface] = []
                for i in range(spec.frame_count):
                    col = d * spec.frame_count + i
                    rect = pygame.Rect(col * frame_w, spec.row * frame_h, frame_w, frame_h)
                    if rect.right > sheet_w or rect.bottom > sheet_h:
                        raise ValueError(f"Анимация '{anim_name}' выходит за границы: {rect}")
                    frames.append(sheet.subsurface(rect))
                per_dir.append(frames)
            slots[anim_name] = per_dir
        self.unit_sheets[key] = slots

    def get_unit_frames(self, key: str, anim: str, direction: int) -> list[pygame.Surface] | None:
        slots = self.unit_sheets.get(key)
        if slots is None:
            return None
        per_dir = slots.get(anim)
        if not per_dir:
            return None
        d = max(0, min(int(direction), len(per_dir) - 1))
        return per_dir[d]

    def get_unit_frame(self, key: str, anim: str, direction: int, frame_index: int = 0):
        frames = self.get_unit_frames(key, anim, direction)
        if not frames:
            return None
        idx = max(0, min(int(frame_index), len(frames) - 1))
        return frames[idx]

    # --- спрайты зданий ------------------------------------------------------
    def load_building_sheet(
        self, key: str, path: str, frame_w: int, frame_h: int, frames: int = 1
    ) -> None:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"[НЕТ ДАННЫХ] лист здания не найден: {path}")
        sheet = pygame.image.load(path).convert_alpha()
        sheet_w, sheet_h = sheet.get_size()
        if frame_w * frames > sheet_w or frame_h > sheet_h:
            raise ValueError(f"Лист здания {key} не вмещает {frames} кадров {frame_w}x{frame_h}")
        out: list[pygame.Surface] = []
        for i in range(frames):
            out.append(sheet.subsurface(pygame.Rect(i * frame_w, 0, frame_w, frame_h)))
        self.building_sheets[key] = out
        self.building_size[key] = (frame_w, frame_h)

    def get_building_frame(self, key: str, frame_index: int = 0):
        frames = self.building_sheets.get(key)
        if not frames:
            return None
        idx = max(0, min(int(frame_index), len(frames) - 1))
        return frames[idx]

    def get_building_size(self, key: str) -> tuple[int, int] | None:
        return self.building_size.get(key)

    # --- тени ----------------------------------------------------------------
    def get_shadow_ellipse(self, w: int, h: int) -> pygame.Surface:
        key = (int(w), int(h))
        surf = self._shadow_cache.get(key)
        if surf is None:
            surf = pygame.Surface(key, pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (0, 0, 0, 90), (0, 0, key[0], key[1]))
            self._shadow_cache[key] = surf
        return surf

    # --- взрывы --------------------------------------------------------------
    def load_explosion_frames_from_dir(self, key: str, directory: str = DEFAULT_EXPLOSIONS_DIR) -> None:
        if not os.path.isdir(directory):
            log.warning("Директория взрывов отсутствует: %s", directory)
            self.explosion_frames.setdefault(key, [])
            return
        frames: list[pygame.Surface] = []
        for name in sorted(os.listdir(directory)):
            if not name.lower().endswith(".png"):
                continue
            try:
                frames.append(pygame.image.load(os.path.join(directory, name)).convert_alpha())
            except pygame.error as exc:
                log.warning("Не удалось загрузить кадр взрыва %s: %s", name, exc)
        self.explosion_frames[key] = frames

    def load_explosion_sheet(
        self, key: str, path: str, frame_w: int, frame_h: int, frames: int
    ) -> None:
        if not os.path.isfile(path):
            log.warning("Лист взрыва не найден: %s", path)
            self.explosion_frames.setdefault(key, [])
            return
        sheet = pygame.image.load(path).convert_alpha()
        sw, sh = sheet.get_size()
        if frame_w * frames > sw or frame_h > sh:
            raise ValueError(f"Лист взрыва {key} не вмещает {frames} кадров {frame_w}x{frame_h}")
        out: list[pygame.Surface] = []
        for i in range(frames):
            out.append(sheet.subsurface(pygame.Rect(i * frame_w, 0, frame_w, frame_h)))
        self.explosion_frames[key] = out

    def get_explosion_frames(self, key: str) -> list[pygame.Surface]:
        return self.explosion_frames.get(key, [])

    # --- снаряды -------------------------------------------------------------
    def load_projectile(
        self, key: str, path: str,
        frame_w: int | None = None, frame_h: int | None = None, frames: int = 1,
    ) -> None:
        if not os.path.isfile(path):
            log.warning("Спрайт снаряда не найден: %s", path)
            return
        sheet = pygame.image.load(path).convert_alpha()
        if frames <= 1:
            self.projectile_sprites[key] = sheet
            return
        if frame_w is None or frame_h is None:
            raise ValueError(f"Снаряд {key}: frame_w/frame_h обязательны при frames>1")
        self.projectile_sprites[key] = sheet.subsurface(pygame.Rect(0, 0, frame_w, frame_h))

    def get_projectile_sprite(self, key: str) -> pygame.Surface | None:
        return self.projectile_sprites.get(key)

    # --- иконки спеллов ------------------------------------------------------
    def load_spell_icons(self, directory: str = DEFAULT_SPELL_ICONS_DIR) -> None:
        self.spell_icons = {}
        if not os.path.isdir(directory):
            log.warning("Директория иконок спеллов отсутствует: %s", directory)
            return
        for name in sorted(os.listdir(directory)):
            if not name.lower().endswith(".png"):
                continue
            try:
                surf = pygame.image.load(os.path.join(directory, name)).convert_alpha()
            except pygame.error as exc:
                log.warning("Не удалось загрузить иконку %s: %s", name, exc)
                continue
            self.spell_icons[os.path.splitext(name)[0]] = surf

    def get_spell_icon(self, key: str) -> pygame.Surface | None:
        return self.spell_icons.get(key)

    def get_all_spell_icons(self) -> dict[str, pygame.Surface]:
        return dict(self.spell_icons)