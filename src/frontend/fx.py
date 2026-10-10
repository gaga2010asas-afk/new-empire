# src/frontend/fx.py
"""
fx.py — FX-пул и покадровые эффекты. Прототип №4 «Бой».
Зона: src/frontend/. Логики мира нет — только воспроизведение анимаций.

Канон v1.5 §1: FX-пул, Surface НЕ создаётся в кадре. Объекты переиспользуются.
Канон v1.5 §2: взрыв здания → единоразовый спавн из assets/fx/explosions/.
Канон v1.5 §1 Z-order: FX поверх снарядов, ниже UI и курсора.

[НЕТ ДАННЫХ]:
- Длительность кадра взрыва — FX_FRAME_TICKS технический дефолт.
- Точный формат assets/fx/explosions/ — поддержан и каталог PNG, и лист.
"""

from __future__ import annotations

import pygame


# --- Технические дефолты (не баланс) ---
FX_FRAME_TICKS: int = 4          # [НЕТ ДАННЫХ]: канон не задаёт длительность кадра
DEFAULT_POOL_SIZE: int = 64


class ExplosionFX:
    """Один экземпляр взрыва. Переиспользуется через reset()."""

    def __init__(self) -> None:
        self.frames: list[pygame.Surface] = []
        self.pixel_x: float = 0.0
        self.pixel_y: float = 0.0
        self.start_tick: int = 0
        self.frame_index: int = 0
        self.dead: bool = True

    def reset(
        self,
        frames: list[pygame.Surface],
        pixel_x: float,
        pixel_y: float,
        tick: int,
    ) -> None:
        self.frames = frames
        self.pixel_x = float(pixel_x)
        self.pixel_y = float(pixel_y)
        self.start_tick = int(tick)
        self.frame_index = 0
        self.dead = not frames

    def update(self, tick: int) -> None:
        if self.dead:
            return
        elapsed = int(tick) - self.start_tick
        total = len(self.frames) * FX_FRAME_TICKS
        if elapsed >= total:
            self.dead = True
            return
        idx = elapsed // FX_FRAME_TICKS
        if idx < 0:
            idx = 0
        elif idx >= len(self.frames):
            idx = len(self.frames) - 1
        self.frame_index = idx

    def render(self, surface: pygame.Surface, camera) -> None:
        if self.dead or not self.frames:
            return
        if not (0 <= self.frame_index < len(self.frames)):
            return
        frame = self.frames[self.frame_index]
        w, h = frame.get_size()
        sx, sy = camera.world_to_screen(self.pixel_x, self.pixel_y)
        # Взрыв центрируется на точке (pixel_x, pixel_y).
        surface.blit(frame, (int(sx - w // 2), int(sy - h // 2)))


class FXPool:
    """Пул объектов ExplosionFX. Объекты переиспользуются — нет аллокаций в кадре."""

    def __init__(self, max_size: int = DEFAULT_POOL_SIZE) -> None:
        self.max_size: int = int(max_size)
        self._active: list[ExplosionFX] = []
        self._free: list[ExplosionFX] = []

    # --- жизненный цикл -------------------------------------------------------
    def spawn_explosion(
        self,
        frames: list[pygame.Surface] | None,
        pixel_x: float,
        pixel_y: float,
        tick: int,
    ) -> ExplosionFX | None:
        """Заспавнить взрыв. Возвращает None, если пул забит или frames пуст."""
        if not frames:
            return None
        if len(self._active) >= self.max_size:
            return None
        fx = self._free.pop() if self._free else ExplosionFX()
        fx.reset(frames, pixel_x, pixel_y, tick)
        self._active.append(fx)
        return fx

    def update(self, tick: int) -> None:
        if not self._active:
            return
        alive: list[ExplosionFX] = []
        for fx in self._active:
            fx.update(tick)
            if fx.dead:
                self._free.append(fx)
            else:
                alive.append(fx)
        self._active = alive

    def render(self, surface: pygame.Surface, camera) -> None:
        for fx in self._active:
            fx.render(surface, camera)

    def clear(self) -> None:
        self._free.extend(self._active)
        self._active.clear()

    # --- доступ ---------------------------------------------------------------
    def active_count(self) -> int:
        return len(self._active)

    def free_count(self) -> int:
        return len(self._free)