# src/backend/pathfinding.py
"""
NEW EMPIRE v1.5 — Backend Agent.
A* для 8 направлений + кэш путей. При блокировке цели — путь до ближайшей
проходимой клетки (в радиусе 6 тайлов).
Канон: MASTER ARCHITECTURE BRIEF v1.5 (раздел 4.6).
"""
from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple

from .constants import MapLayer
from .map_data import MapData

Tile = Tuple[int, int]

_NEIGHBOURS_8: Tuple[Tuple[int, int], ...] = (
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (1, -1), (-1, 1), (-1, -1),
)

_STRAIGHT_COST = 10
_DIAGONAL_COST = 14


def _heuristic(a: Tile, b: Tile) -> int:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return _STRAIGHT_COST * (dx + dy) + (_DIAGONAL_COST - 2 * _STRAIGHT_COST) * min(dx, dy)


def _is_ground(map_data: MapData, x: int, y: int) -> bool:
    return map_data.get_layer(x, y) == int(MapLayer.GROUND)


class PathFinder:
    """
    A* с кэшем. Ключ = (start, goal). find_path всегда возвращает копию списка.
    """

    def __init__(self, map_data: MapData, cache_limit: int = 512) -> None:
        self.map_data = map_data
        self.cache: Dict[Tuple[Tile, Tile], List[Tile]] = {}
        self.cache_limit = cache_limit

    # ---------------------------------------------------------------- API
    def find_path(self, start: Tile, goal: Tile) -> List[Tile]:
        """Путь [start, ..., goal] или [] если путей нет."""
        key = (start, goal)
        if key in self.cache:
            return list(self.cache[key])

        if not self.map_data.is_inside(*start):
            return []

        actual_goal = goal
        if not _is_ground(self.map_data, *goal):
            fallback = self._nearest_passable(goal, radius=6)
            if fallback is None:
                return []
            actual_goal = fallback

        path = self._astar(start, actual_goal)
        self._store_cache(key, path)
        return list(path)

    def clear_cache(self) -> None:
        self.cache.clear()

    # ------------------------------------------------------------ внутреннее
    def _store_cache(self, key: Tuple[Tile, Tile], path: List[Tile]) -> None:
        if len(self.cache) >= self.cache_limit:
            for k in list(self.cache.keys())[: self.cache_limit // 2]:
                del self.cache[k]
        self.cache[key] = list(path)

    def _nearest_passable(self, origin: Tile, radius: int) -> Optional[Tile]:
        ox, oy = origin
        best: Optional[Tile] = None
        best_d: Optional[int] = None
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                x, y = ox + dx, oy + dy
                if not self.map_data.is_inside(x, y):
                    continue
                if not _is_ground(self.map_data, x, y):
                    continue
                d = dx * dx + dy * dy
                if best_d is None or d < best_d:
                    best_d = d
                    best = (x, y)
        return best

    def _astar(self, start: Tile, goal: Tile) -> List[Tile]:
        if start == goal:
            return [start]
        if not _is_ground(self.map_data, *start):
            return []

        open_heap: List[Tuple[int, int, Tile]] = []
        heapq.heappush(open_heap, (0, 0, start))
        came_from: Dict[Tile, Optional[Tile]] = {start: None}
        g_score: Dict[Tile, int] = {start: 0}

        while open_heap:
            _, g_curr, current = heapq.heappop(open_heap)
            if current == goal:
                return self._reconstruct(came_from, current)
            if g_curr > g_score.get(current, 1 << 30):
                continue

            cx, cy = current
            for dx, dy in _NEIGHBOURS_8:
                nx, ny = cx + dx, cy + dy
                if not self.map_data.is_inside(nx, ny):
                    continue
                if not _is_ground(self.map_data, nx, ny):
                    continue
                if dx != 0 and dy != 0:
                    if not _is_ground(self.map_data, cx + dx, cy):
                        continue
                    if not _is_ground(self.map_data, cx, cy + dy):
                        continue

                step_cost = _DIAGONAL_COST if (dx and dy) else _STRAIGHT_COST
                tentative = g_curr + step_cost
                neighbour = (nx, ny)
                if tentative < g_score.get(neighbour, 1 << 30):
                    g_score[neighbour] = tentative
                    came_from[neighbour] = current
                    f = tentative + _heuristic(neighbour, goal)
                    heapq.heappush(open_heap, (f, tentative, neighbour))
        return []

    @staticmethod
    def _reconstruct(came_from: Dict[Tile, Optional[Tile]],
                     current: Tile) -> List[Tile]:
        path: List[Tile] = [current]
        while came_from[current] is not None:
            current = came_from[current]   # type: ignore[assignment]
            path.append(current)
        path.reverse()
        return path