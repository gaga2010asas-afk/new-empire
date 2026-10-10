# src/backend/vassal_builder.py
"""
NEW EMPIRE v1.5.6 — Backend Agent (Proto #5).
Красивая застройка: фермы улицей вдоль дорог, казармы кварталом,
кузница рядом с казармами.
Канон: MASTER BRIEF v1.5 (Proto #5, раздел 1) + патч v1.5.6.
Без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .constants import MapLayer
from .map_data import MapData


_DIRECTIONS: Dict[str, Tuple[int, int]] = {
    "N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0),
}


@dataclass
class BuildPlan:
    farms: List[Tuple[int, int]] = field(default_factory=list)
    barracks: List[Tuple[int, int]] = field(default_factory=list)
    blacksmith: Optional[Tuple[int, int]] = None
    towers: List[Tuple[int, int]] = field(default_factory=list)

    def all_positions(self) -> List[Tuple[int, int]]:
        result = list(self.farms) + list(self.barracks) + list(self.towers)
        if self.blacksmith is not None:
            result.append(self.blacksmith)
        return result


class BeautyBuilder:
    """Планировщик красивой застройки. Не ставит здания — выдаёт позиции."""

    def __init__(self, map_data: MapData) -> None:
        self.map_data = map_data

    # ------------------------------------------------------------ улицы
    def farm_street(self, anchor: Tuple[int, int], direction: str,
                    count: int, spacing: int = 2,
                    occupied: Optional[Set[Tuple[int, int]]] = None
                    ) -> List[Tuple[int, int]]:
        if direction not in _DIRECTIONS:
            raise ValueError(f"Направление '{direction}' не из N/S/E/W")
        if count <= 0:
            return []
        occupied = occupied or set()
        dx, dy = _DIRECTIONS[direction]
        result: List[Tuple[int, int]] = []
        for i in range(count):
            fx = anchor[0] + dx * i * spacing
            fy = anchor[1] + dy * i * spacing
            if not self.map_data.is_inside(fx, fy):
                continue
            if self.map_data.get_layer(fx, fy) != int(MapLayer.GROUND):
                continue
            if (fx, fy) in occupied:
                continue
            result.append((fx, fy))
        return result

    # ------------------------------------------------------------ кварталы
    def barracks_quarter(self, base_grid: Tuple[int, int],
                         offset: Tuple[int, int] = (6, 6),
                         count: int = 2, spacing: int = 3,
                         occupied: Optional[Set[Tuple[int, int]]] = None
                         ) -> List[Tuple[int, int]]:
        if count <= 0:
            return []
        occupied = occupied or set()
        bx = base_grid[0] + offset[0]
        by = base_grid[1] + offset[1]
        result: List[Tuple[int, int]] = []
        for i in range(count):
            fx = bx + i * spacing
            fy = by
            if not self.map_data.is_inside(fx, fy):
                continue
            if self.map_data.get_layer(fx, fy) != int(MapLayer.GROUND):
                continue
            if (fx, fy) in occupied:
                continue
            result.append((fx, fy))
        return result

    def blacksmith_near_barracks(self,
                                 barracks_positions: List[Tuple[int, int]],
                                 offset: Tuple[int, int] = (0, 3),
                                 occupied: Optional[Set[Tuple[int, int]]] = None
                                 ) -> Optional[Tuple[int, int]]:
        if not barracks_positions:
            return None
        occupied = occupied or set()
        bx, by = barracks_positions[0]
        cx, cy = bx + offset[0], by + offset[1]
        if not self.map_data.is_inside(cx, cy):
            return None
        if self.map_data.get_layer(cx, cy) != int(MapLayer.GROUND):
            return None
        if (cx, cy) in occupied:
            return None
        return (cx, cy)

    # ------------------------------------------------------------ оркестрация
    def plan(self, hall_grid: Tuple[int, int],
             road_direction: str = "E",
             farm_count: int = 4,
             barracks_count: int = 2,
             occupied: Optional[Set[Tuple[int, int]]] = None
             ) -> BuildPlan:
        occupied = set(occupied or set())
        plan = BuildPlan()

        plan.farms = self.farm_street(hall_grid, road_direction,
                                      count=farm_count, spacing=2,
                                      occupied=occupied)
        occupied.update(plan.farms)

        plan.barracks = self.barracks_quarter(hall_grid, offset=(6, 6),
                                              count=barracks_count,
                                              spacing=3, occupied=occupied)
        occupied.update(plan.barracks)

        plan.blacksmith = self.blacksmith_near_barracks(
            plan.barracks, offset=(0, 3), occupied=occupied,
        )
        if plan.blacksmith is not None:
            occupied.add(plan.blacksmith)

        return plan