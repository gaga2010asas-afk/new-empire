# src/backend/vassal_defense.py
"""
NEW EMPIRE v1.5.6 — Backend Agent (Proto #5).
Умная оборона: башни на chokepoints (шаг >= 4 тайла), обнос фермами,
катапульты за башнями по направлению к базе.
Патч v1.5.6 (замечание №1): лимиты берутся из vassal_ai.policy_for.
Без pygame.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from .chokepoint import Chokepoint
from .constants import MIN_TOWER_SPACING, MapLayer
from .map_data import MapData
from .vassal_ai import policy_for


@dataclass
class TowerPlacement:
    grid_x: int
    grid_y: int
    chokepoint: Chokepoint


def select_towers(chokepoints: List[Chokepoint],
                  existing_towers: Optional[List[Tuple[int, int]]] = None,
                  min_spacing: int = MIN_TOWER_SPACING,
                  max_towers: int = 6) -> List[TowerPlacement]:
    result: List[TowerPlacement] = []
    existing = list(existing_towers or [])
    all_positions: List[Tuple[int, int]] = list(existing)

    for cp in chokepoints:
        if len(result) >= max_towers:
            break
        x, y = cp.grid_x, cp.grid_y
        ok = True
        for (ox, oy) in all_positions:
            if (x - ox) ** 2 + (y - oy) ** 2 < min_spacing * min_spacing:
                ok = False
                break
        if not ok:
            continue
        result.append(TowerPlacement(grid_x=x, grid_y=y, chokepoint=cp))
        all_positions.append((x, y))
    return result


def encircle_with_farms(tower_grid: Tuple[int, int],
                        map_data: MapData,
                        occupied: Optional[Set[Tuple[int, int]]] = None
                        ) -> List[Tuple[int, int]]:
    occupied = occupied or set()
    x, y = tower_grid
    farms: List[Tuple[int, int]] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if (nx, ny) in occupied:
                continue
            if not map_data.is_inside(nx, ny):
                continue
            if map_data.get_layer(nx, ny) != int(MapLayer.GROUND):
                continue
            farms.append((nx, ny))
    return farms


def place_catapult_behind(tower_grid: Tuple[int, int],
                          base_grid: Tuple[int, int],
                          distance: int = 3,
                          map_data: Optional[MapData] = None
                          ) -> Optional[Tuple[int, int]]:
    dx = base_grid[0] - tower_grid[0]
    dy = base_grid[1] - tower_grid[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return None
    ux, uy = dx / dist, dy / dist
    cx = int(round(tower_grid[0] + ux * distance))
    cy = int(round(tower_grid[1] + uy * distance))
    if map_data is not None:
        if not map_data.is_inside(cx, cy):
            return None
        if map_data.get_layer(cx, cy) != int(MapLayer.GROUND):
            return None
    return (cx, cy)


def max_towers_for_colony(colony_type: str) -> int:
    """
    v1.5.6, замечание №1: обёртка над vassal_ai.policy_for.
    Единый источник правды — policy_for.
    """
    return policy_for(colony_type).max_towers


def max_catapults_for_colony(colony_type: str) -> int:
    """v1.5.6, замечание №1: обёртка над vassal_ai.policy_for."""
    return policy_for(colony_type).max_catapults