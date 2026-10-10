# src/backend/worker_group.py
"""
NEW EMPIRE v1.5.3 — Backend Agent (Proto #3).
Группа рабочих-курьеров налога: идёт от вассальной ратуши к главной ратуше
игрока по A*, зовёт map_data.trample_tile на каждой новой клетке лидера.
Скорость = базовая скорость рабочего (v1.5.3, п.5), множитель x2.0 на дорогах
уровня 3 применяется внутри update_unit_movement.
Без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .constants import TILE_SIZE, UnitState
from .entities import Unit
from .map_data import MapData
from .movement import update_unit_movement
from .pathfinding import PathFinder


# v1.5.3, п.5: скорость = скорость рабочего. Дефолт — до чтения JSON.
# [НЕТ ДАННЫХ] — точное число берётся из data/units/peasant.json в main.py.
DEFAULT_GROUP_SPEED: float = 100.0

FOLLOWER_SPACING_PX: float = 12.0


class GroupState(str, Enum):
    TO_TARGET = "to_target"
    ARRIVED   = "arrived"
    LOST      = "lost"


@dataclass
class WorkerGroup:
    id: int
    faction: str
    worker_ids: List[int]
    source: Tuple[int, int]
    target: Tuple[int, int]
    carry_gold: int
    carry_wood: int
    state: str = GroupState.TO_TARGET.value
    path: List[Tuple[int, int]] = field(default_factory=list)
    path_index: int = 0
    last_tile: Optional[Tuple[int, int]] = None

    def is_marching(self) -> bool:
        return self.state == GroupState.TO_TARGET.value

    def is_done(self) -> bool:
        return self.state in (GroupState.ARRIVED.value, GroupState.LOST.value)


def _tile_center_px(gx: int, gy: int) -> Tuple[float, float]:
    return (gx * TILE_SIZE + TILE_SIZE * 0.5,
            gy * TILE_SIZE + TILE_SIZE * 0.5)


def _carry_type_for(faction: str, kind: str) -> str:
    if faction == "human":
        return "peasant_with_gold" if kind == "gold" else "peasant_with_wood"
    if faction == "orc":
        return "peon_with_gold" if kind == "gold" else "peon_with_wood"
    return "peasant_with_gold"


class WorkerGroupController:
    def __init__(self, map_data: MapData,
                 units: Dict[int, Unit],
                 pathfinder: PathFinder) -> None:
        self.map_data = map_data
        self.units = units
        self.pathfinder = pathfinder

    # ---------------------------------------------------------------- API
    def spawn(self,
              group_id: int,
              faction: str,
              worker_ids: List[int],
              source_grid: Tuple[int, int],
              target_grid: Tuple[int, int],
              carry_gold: int,
              carry_wood: int) -> WorkerGroup:
        if not worker_ids:
            raise ValueError("worker_ids не может быть пустым")
        for wid in worker_ids:
            if wid not in self.units:
                raise KeyError(f"Рабочий {wid} не найден")

        path = self.pathfinder.find_path(source_grid, target_grid)
        if not path:
            path = [source_grid, target_grid]

        group = WorkerGroup(
            id=group_id, faction=faction, worker_ids=list(worker_ids),
            source=source_grid, target=target_grid,
            carry_gold=int(carry_gold), carry_wood=int(carry_wood),
            path=path, path_index=0, last_tile=source_grid,
        )

        sx, sy = _tile_center_px(*source_grid)
        carry_kind = "gold" if carry_gold >= carry_wood else "wood"
        for i, wid in enumerate(worker_ids):
            u = self.units[wid]
            u.type = _carry_type_for(faction, carry_kind)
            u.state = int(UnitState.RETURN)
            u.inside_mine = False
            u.pixel_x = sx - i * FOLLOWER_SPACING_PX
            u.pixel_y = sy
        return group

    def update(self, group: WorkerGroup, dt: float,
               base_speed: float = DEFAULT_GROUP_SPEED) -> None:
        if group.is_done():
            return
        if self.is_lost(group):
            group.state = GroupState.LOST.value
            return

        leader = self.units[group.worker_ids[0]]

        # Конец пути → финализация
        if group.path_index >= len(group.path) - 1:
            tx, ty = _tile_center_px(*group.target)
            for i, wid in enumerate(group.worker_ids):
                u = self.units[wid]
                u.pixel_x = tx - i * FOLLOWER_SPACING_PX
                u.pixel_y = ty
                u.state = int(UnitState.IDLE)
            group.state = GroupState.ARRIVED.value
            return

        next_tile = group.path[group.path_index + 1]
        tx, ty = _tile_center_px(*next_tile)
        reached = update_unit_movement(leader, tx, ty, self.map_data,
                                       dt, base_speed)

        if reached:
            group.path_index += 1
            new_tile = group.path[group.path_index]
            if new_tile != group.last_tile:
                self.map_data.trample_tile(new_tile[0], new_tile[1])
                group.last_tile = new_tile

        # Синхронизация цепочки за лидером
        for i, wid in enumerate(group.worker_ids[1:], start=1):
            u = self.units[wid]
            u.pixel_x = leader.pixel_x - i * FOLLOWER_SPACING_PX
            u.pixel_y = leader.pixel_y
            u.state = int(UnitState.RETURN)
            u.direction = leader.direction

    # ------------------------------------------------------------ утилиты
    def is_lost(self, group: WorkerGroup) -> bool:
        alive = 0
        for wid in group.worker_ids:
            u = self.units.get(wid)
            if u is None:
                continue
            if u.state != int(UnitState.DEAD) and u.hp > 0:
                alive += 1
        return alive == 0