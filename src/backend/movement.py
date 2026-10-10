# src/backend/movement.py
"""
NEW EMPIRE v1.5.17 — Backend Agent.
Движение: pixel_x/pixel_y, direction 0..7 (math.atan2), коллизия слоёв,
множитель дороги x2.0.

Патч v1.5.17, п.5: при `reached == True` state ПРИНУДИТЕЛЬНО становится
IDLE, даже если шаг был не «внутри тайла», а ровно на цель.

Без pygame.
"""
from __future__ import annotations

import math
from typing import Tuple

from .constants import (
    ROAD_MAX_LEVEL, ROAD_SPEED_MULTIPLIER, TILE_SIZE, UnitState,
)
from .entities import Unit
from .map_data import MapData


def _direction_from_delta(dx: float, dy: float) -> int:
    """8 направлений через math.atan2. 0 = восток, далее по часовой."""
    if dx == 0.0 and dy == 0.0:
        return 0
    angle = math.atan2(dy, dx)
    return int(round(angle / (math.pi / 4.0))) % 8


def _tile_of(px: float, py: float) -> Tuple[int, int]:
    return int(px // TILE_SIZE), int(py // TILE_SIZE)


def _speed_with_road(base_speed: float, road_level: int) -> float:
    if road_level >= ROAD_MAX_LEVEL:
        return base_speed * ROAD_SPEED_MULTIPLIER
    return base_speed


def _pixel_passable(map_data: MapData, px: float, py: float) -> bool:
    tx, ty = _tile_of(px, py)
    return map_data.is_passable(tx, ty)


def update_unit_movement(unit: Unit,
                         target_x: float,
                         target_y: float,
                         map_data: MapData,
                         dt: float,
                         base_speed: float) -> bool:
    """
    Двигает юнита к пиксельной цели за dt. Обновляет pixel_x, pixel_y,
    direction, state. Возвращает True, если цель достигнута.
    """
    dx = target_x - unit.pixel_x
    dy = target_y - unit.pixel_y
    dist = math.hypot(dx, dy)

    if dist <= 1e-3:
        unit.state = int(UnitState.IDLE)
        return True

    unit.direction = _direction_from_delta(dx, dy)

    tx, ty = _tile_of(unit.pixel_x, unit.pixel_y)
    road_lvl = map_data.get_road_level(tx, ty)
    speed = _speed_with_road(base_speed, road_lvl)

    step = speed * dt
    reached = step >= dist
    if reached:
        next_px, next_py = target_x, target_y
    else:
        r = step / dist
        next_px = unit.pixel_x + dx * r
        next_py = unit.pixel_y + dy * r

    if not _pixel_passable(map_data, next_px, next_py):
        unit.state = int(UnitState.IDLE)
        return False

    unit.pixel_x = next_px
    unit.pixel_y = next_py

    # Патч v1.5.17, п.5: при достижении цели — жёсткий IDLE.
    if reached:
        unit.state = int(UnitState.IDLE)
    else:
        unit.state = int(UnitState.WALK)

    ntx, nty = _tile_of(next_px, next_py)
    if (ntx, nty) != (tx, ty):
        map_data.trample_tile(ntx, nty)

    return reached