# src/backend/chokepoint.py
"""
NEW EMPIRE v1.5.22 — Backend Agent (Proto #5).
Поиск Chokepoints.

Патч v1.5.22, п.3: крайние линии региона и карты отсекаются —
тайлы на границе НЕ могут быть тактическим chokepoint.
Кластеризация — по расстоянию Чебышёва (`max(|dx|, |dy|)`), строго < radius.
Один кандидат на тайл (лучший по score).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .constants import (
    CHOKEPOINT_CLUSTER_RADIUS, CHOKEPOINT_MAX_WIDTH, MapLayer,
)
from .map_data import MapData


@dataclass
class Chokepoint:
    grid_x: int
    grid_y: int
    width: int
    orientation: str
    score: float

    def center(self) -> Tuple[int, int]:
        return (self.grid_x, self.grid_y)


def _wall_distance(map_data: MapData, x: int, y: int,
                   dx: int, dy: int, max_dist: int) -> int:
    for d in range(1, max_dist + 1):
        nx, ny = x + dx * d, y + dy * d
        if not map_data.is_inside(nx, ny):
            return d
        if map_data.get_layer(nx, ny) != int(MapLayer.GROUND):
            return d
    return max_dist + 1


def _tile_chokepoint_info(map_data: MapData, x: int, y: int,
                          max_width: int) -> List[Tuple[str, int]]:
    if not map_data.is_passable(x, y):
        return []

    n = _wall_distance(map_data, x, y, 0, -1, max_width)
    s = _wall_distance(map_data, x, y, 0, +1, max_width)
    e = _wall_distance(map_data, x, y, +1, 0, max_width)
    w = _wall_distance(map_data, x, y, -1, 0, max_width)

    results: List[Tuple[str, int]] = []

    if n <= max_width and s <= max_width:
        horiz_w = n + s - 1
        if 1 <= horiz_w <= max_width:
            results.append(("horizontal", horiz_w))

    if e <= max_width and w <= max_width:
        vert_w = e + w - 1
        if 1 <= vert_w <= max_width:
            results.append(("vertical", vert_w))

    return results


def find_chokepoints(
    map_data: MapData,
    region: Optional[Tuple[int, int, int, int]] = None,
    max_width: int = CHOKEPOINT_MAX_WIDTH,
    cluster_radius: int = CHOKEPOINT_CLUSTER_RADIUS,
) -> List[Chokepoint]:
    if region is None:
        region = (0, 0, map_data.width, map_data.height)
    x_min, y_min, x_max, y_max = region

    # Патч v1.5.22, п.3: отсечка границ. Внутри региона оставляем только
    # тайлы со координатами 1 .. (max-1). Это одновременно исключает
    # границы карты и границы переданного региона.
    x_start = max(1, x_min)
    y_start = max(1, y_min)
    x_end   = min(map_data.width - 1, x_max)
    y_end   = min(map_data.height - 1, y_max)

    # 1. Один лучший кандидат на тайл.
    best_per_tile: Dict[Tuple[int, int], Chokepoint] = {}
    for y in range(y_start, y_end):
        for x in range(x_start, x_end):
            for orientation, width in _tile_chokepoint_info(map_data, x, y,
                                                             max_width):
                score = float(max_width + 1 - width)
                cp = Chokepoint(grid_x=x, grid_y=y, width=width,
                                orientation=orientation, score=score)
                prev = best_per_tile.get((x, y))
                if prev is None or cp.score > prev.score:
                    best_per_tile[(x, y)] = cp

    candidates: List[Chokepoint] = list(best_per_tile.values())
    candidates.sort(key=lambda c: (-c.score, c.grid_y, c.grid_x))

    # 2. Кластеризация Чебышёва — строго < cluster_radius.
    chosen: List[Chokepoint] = []
    for c in candidates:
        is_neighbour = False
        for p in chosen:
            dx = abs(c.grid_x - p.grid_x)
            dy = abs(c.grid_y - p.grid_y)
            if max(dx, dy) < cluster_radius:
                is_neighbour = True
                break
        if not is_neighbour:
            chosen.append(c)
    return chosen