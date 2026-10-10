# src/backend/roads.py
"""
NEW EMPIRE v1.5.3 — Backend Agent (Proto #3).
Дороги: множитель скорости (x2.0 на уровне 3), стоимость A*, точки засад.
Канон: MASTER BRIEF v1.5 (Proto #3) + патч v1.5.3 (п.1, п.4).
Без pygame.
"""
from __future__ import annotations

from typing import Callable, List, Tuple

from .constants import (
    AMBUSH_MIN_ROAD_LEVEL, ROAD_COST_BASE,
    ROAD_COST_LEVEL_1, ROAD_COST_LEVEL_2, ROAD_COST_LEVEL_3,
    ROAD_MAX_LEVEL, ROAD_SPEED_MULTIPLIER,
    MapLayer,
)
from .map_data import MapData


def speed_multiplier(map_data: MapData, x: int, y: int) -> float:
    """x2.0 только на GROUND-тайле с уровнем дороги 3."""
    if not map_data.is_inside(x, y):
        return 1.0
    if map_data.get_layer(x, y) != int(MapLayer.GROUND):
        return 1.0
    if map_data.get_road_level(x, y) >= ROAD_MAX_LEVEL:
        return ROAD_SPEED_MULTIPLIER
    return 1.0


def cost_for_astar(map_data: MapData, x: int, y: int) -> int:
    """Стоимость шага: чем выше уровень дороги — тем дешевле."""
    if not map_data.is_inside(x, y):
        return 999
    if map_data.get_layer(x, y) != int(MapLayer.GROUND):
        return 999
    lvl = map_data.get_road_level(x, y)
    if lvl >= ROAD_MAX_LEVEL: return ROAD_COST_LEVEL_3
    if lvl == 2:              return ROAD_COST_LEVEL_2
    if lvl == 1:              return ROAD_COST_LEVEL_1
    return ROAD_COST_BASE


def road_cost_function(map_data: MapData) -> Callable[[int, int], int]:
    """Готовый колбэк для PathFinder.find_path(cost_fn=...)."""
    def _fn(x: int, y: int) -> int:
        return cost_for_astar(map_data, x, y)
    return _fn


def ambush_targets(map_data: MapData,
                   min_level: int = AMBUSH_MIN_ROAD_LEVEL
                   ) -> List[Tuple[int, int]]:
    """
    v1.5.3, п.4: список координат тайлов дорог уровня >= min_level.
    Стабильный порядок (построчно сверху вниз, слева направо).
    Входные цели для рейдеров в Прототипе №5.
    """
    result: List[Tuple[int, int]] = []
    for y in range(map_data.height):
        for x in range(map_data.width):
            if map_data.get_road_level(x, y) >= min_level:
                result.append((x, y))
    return result