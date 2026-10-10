# src/backend/worker_state.py
"""
NEW EMPIRE v1.5.23 — Backend Agent (Proto #2).
Машина состояний Peasant / Peon.

Патч v1.5.23, п.4: fire срабатывает, когда counter ДОСТИГ порога
MINE_TICKS_N (проверка `>=` — ДО инкремента). Это даёт ровно:
  * дерево: 51 вызов MINING до трансформации в peasant_with_wood;
  * золото: 45 вызовов MINING с внутри inside_mine == True.

`inside_mine` не сбрасывается в 44-м тике — только при fire (45-й тик).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Optional, Tuple

from .constants import (
    MINE_TICKS_GOLD, MINE_TICKS_WOOD, TILE_SIZE, UnitState,
)
from .economy import Economy, EconomyError, NodeKind, ResourceNode
from .entities import Building, Unit
from .map_data import MapData
from .movement import update_unit_movement


WORKER_BASE_TYPES = frozenset({"peasant", "peon"})
WORKER_CARRY_TYPES = frozenset({
    "peasant_with_gold", "peasant_with_wood",
    "peon_with_gold",    "peon_with_wood",
})
WORKER_ALL_TYPES = WORKER_BASE_TYPES | WORKER_CARRY_TYPES

_TYPE_BASE: Dict[str, str] = {
    "peasant_with_gold": "peasant", "peasant_with_wood": "peasant",
    "peon_with_gold":    "peon",    "peon_with_wood":    "peon",
}
_TYPE_CARRY: Dict[Tuple[str, str], str] = {
    ("peasant", "gold"): "peasant_with_gold",
    ("peasant", "wood"): "peasant_with_wood",
    ("peon",    "gold"): "peon_with_gold",
    ("peon",    "wood"): "peon_with_wood",
}

DEFAULT_WORKER_SPEED: float = 100.0
MINE_DISTANCE_TILES: float = 1.0


class WorkerPhase(str, Enum):
    TO_NODE = "to_node"
    MINING  = "mining"
    TO_HALL = "to_hall"


@dataclass
class WorkerTask:
    worker_id: int
    node_id: int
    hall_id: str
    node_kind: NodeKind
    phase: str = WorkerPhase.TO_NODE.value
    mine_timer: int = 0
    carry_kind: str = ""
    carry_amount: int = 0
    exit_px: float = 0.0
    exit_py: float = 0.0


def is_worker(u: Unit) -> bool:
    return u.type in WORKER_ALL_TYPES


def base_worker_type(u: Unit) -> Optional[str]:
    if u.type in WORKER_BASE_TYPES:
        return u.type
    return _TYPE_BASE.get(u.type)


def _apply_carry_type(u: Unit, kind: str) -> None:
    base = base_worker_type(u)
    if base is None:
        return
    u.type = _TYPE_CARRY.get((base, kind), base)


def _reset_type(u: Unit) -> None:
    base = base_worker_type(u)
    if base is not None:
        u.type = base


def _tile_center_px(gx: int, gy: int) -> Tuple[float, float]:
    return (gx * TILE_SIZE + TILE_SIZE * 0.5,
            gy * TILE_SIZE + TILE_SIZE * 0.5)


def _building_center_px(b: Building) -> Tuple[float, float]:
    return b.center_px()


def _distance_tiles(px: float, py: float, gx: int, gy: int) -> float:
    cx, cy = _tile_center_px(gx, gy)
    return math.hypot(px - cx, py - cy) / TILE_SIZE


def _adjacent_ground(map_data: MapData, gx: int, gy: int,
                     from_px: float, from_py: float
                     ) -> Optional[Tuple[int, int]]:
    if map_data.is_passable(gx, gy):
        return (gx, gy)
    candidates = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = gx + dx, gy + dy
            if map_data.is_passable(nx, ny):
                candidates.append((nx, ny))
    if not candidates:
        return None
    return min(candidates, key=lambda c: (
        (c[0] * TILE_SIZE + TILE_SIZE / 2 - from_px) ** 2 +
        (c[1] * TILE_SIZE + TILE_SIZE / 2 - from_py) ** 2
    ))


class WorkerController:
    def __init__(self,
                 economy: Economy,
                 map_data: MapData,
                 units: Dict[int, Unit],
                 buildings: Dict[str, Building],
                 has_lumber_mill: Callable[[str], bool]) -> None:
        self.economy = economy
        self.map_data = map_data
        self.units = units
        self.buildings = buildings
        self.has_lumber_mill = has_lumber_mill
        self.tasks: Dict[int, WorkerTask] = {}

    # ------------------------------------------------------------ API
    def assign(self, worker_id: int, node_id: int, hall_id: str) -> None:
        if worker_id not in self.units:
            raise KeyError(f"Рабочий {worker_id} не найден")
        if node_id not in self.economy.nodes:
            raise KeyError(f"Узел {node_id} не найден")
        if hall_id not in self.buildings:
            raise KeyError(f"Ратуша {hall_id} не найдена")
        node = self.economy.nodes[node_id]
        self.tasks[worker_id] = WorkerTask(
            worker_id=worker_id, node_id=node_id, hall_id=hall_id,
            node_kind=node.kind,
        )
        self.units[worker_id].state = int(UnitState.WALK)

    def cancel(self, worker_id: int) -> None:
        task = self.tasks.pop(worker_id, None)
        if task is None:
            return
        u = self.units.get(worker_id)
        if u is not None:
            u.inside_mine = False
            u.state = int(UnitState.IDLE)

    def is_busy(self, worker_id: int) -> bool:
        return worker_id in self.tasks

    def update(self, worker_id: int, dt: float,
               base_speed: float = DEFAULT_WORKER_SPEED) -> None:
        task = self.tasks.get(worker_id)
        if task is None:
            return
        unit = self.units.get(worker_id)
        if unit is None or unit.state == int(UnitState.DEAD):
            self.tasks.pop(worker_id, None)
            return

        if task.phase == WorkerPhase.TO_NODE.value:
            self._phase_to_node(task, unit, dt, base_speed)
        elif task.phase == WorkerPhase.MINING.value:
            self._phase_mining(task, unit)
        elif task.phase == WorkerPhase.TO_HALL.value:
            self._phase_to_hall(task, unit, dt, base_speed)

    # ------------------------------------------------------------ фазы
    def _phase_to_node(self, task: WorkerTask, unit: Unit,
                       dt: float, base_speed: float) -> None:
        node = self.economy.nodes.get(task.node_id)
        if node is None or node.is_empty():
            if not self._retarget(task, unit):
                return
            node = self.economy.nodes[task.node_id]

        spot = _adjacent_ground(self.map_data, node.grid_x, node.grid_y,
                                unit.pixel_x, unit.pixel_y)
        if spot is None:
            self.tasks.pop(task.worker_id, None)
            unit.state = int(UnitState.IDLE)
            return

        tx, ty = _tile_center_px(*spot)
        reached = update_unit_movement(unit, tx, ty, self.map_data,
                                       dt, base_speed)
        dist = _distance_tiles(unit.pixel_x, unit.pixel_y,
                               node.grid_x, node.grid_y)

        if reached or dist <= MINE_DISTANCE_TILES:
            task.phase = WorkerPhase.MINING.value
            task.mine_timer = 0
            unit.state = int(UnitState.MINE)
            if node.kind == NodeKind.GOLD_MINE:
                task.exit_px = unit.pixel_x
                task.exit_py = unit.pixel_y
                unit.inside_mine = True

    # ================================================================
    # _phase_mining() — вся логика удар/таймер.
    # Проверка `>= MINE_TICKS_N` идёт ДО инкремента.
    # ================================================================
    def _phase_mining(self, task: WorkerTask, unit: Unit) -> None:
        node = self.economy.nodes.get(task.node_id)
        if node is None or node.is_empty():
            if node is not None:
                self.map_data.clear_block(node.grid_x, node.grid_y)
            unit.inside_mine = False
            if not self._retarget(task, unit):
                return
            return

        unit.state = int(UnitState.MINE)

        # ---------------- GOLD ----------------
        if node.kind == NodeKind.GOLD_MINE:
            # fire на 45-й проверке: counter = 0..44 инкрементируются,
            # на 45-й (counter = 45) → выходим.
            if task.mine_timer >= MINE_TICKS_GOLD:
                amount = self.economy.extract_from_gold_mine(node.id)
                if amount <= 0:
                    unit.inside_mine = False
                    self.map_data.clear_block(node.grid_x, node.grid_y)
                    if not self._retarget(task, unit):
                        return
                    return
                # Сбрасываем inside_mine ровно при fire — на 45-м тике.
                unit.inside_mine = False
                unit.pixel_x = task.exit_px
                unit.pixel_y = task.exit_py
                self._start_return(task, unit, "gold", amount)
                return
            task.mine_timer += 1
            return

        # ---------------- TREE ----------------
        # fire на 51-й проверке: counter = 0..50 инкрементируются,
        # на 51-й (counter = 51) → трансформация типа и возврат.
        if task.mine_timer >= MINE_TICKS_WOOD:
            mill = bool(self.has_lumber_mill(unit.faction))
            amount = self.economy.extract_wood_from_tree(node.id, mill)
            if node.is_empty():
                self.map_data.clear_block(node.grid_x, node.grid_y)
            if amount <= 0:
                if not self._retarget(task, unit):
                    return
                return
            self._start_return(task, unit, "wood", amount)
            return
        task.mine_timer += 1

    def _phase_to_hall(self, task: WorkerTask, unit: Unit,
                       dt: float, base_speed: float) -> None:
        hall = self.buildings.get(task.hall_id)
        if hall is None:
            self.tasks.pop(task.worker_id, None)
            unit.state = int(UnitState.IDLE)
            _reset_type(unit)
            return
        tx, ty = _building_center_px(hall)
        reached = update_unit_movement(unit, tx, ty, self.map_data,
                                       dt, base_speed)
        if reached:
            try:
                self.economy.gather_resource(unit.faction,
                                             task.carry_kind,
                                             task.carry_amount)
            except EconomyError:
                pass
            _reset_type(unit)
            task.carry_kind = ""
            task.carry_amount = 0
            task.mine_timer = 0
            task.phase = WorkerPhase.TO_NODE.value
            unit.state = int(UnitState.WALK)

    # ------------------------------------------------------------ внутреннее
    def _start_return(self, task: WorkerTask, unit: Unit,
                      kind: str, amount: int) -> None:
        task.carry_kind = kind
        task.carry_amount = int(amount)
        task.phase = WorkerPhase.TO_HALL.value
        task.mine_timer = 0
        unit.state = int(UnitState.RETURN)
        _apply_carry_type(unit, kind)

    def _retarget(self, task: WorkerTask, unit: Unit) -> bool:
        best: Optional[ResourceNode] = None
        best_d: Optional[float] = None
        for node in self.economy.nodes.values():
            if node.kind != task.node_kind or node.is_empty():
                continue
            d = _distance_tiles(unit.pixel_x, unit.pixel_y,
                                node.grid_x, node.grid_y)
            if best_d is None or d < best_d:
                best_d, best = d, node
        if best is None:
            self.tasks.pop(task.worker_id, None)
            unit.state = int(UnitState.IDLE)
            unit.inside_mine = False
            _reset_type(unit)
            return False
        task.node_id = best.id
        task.phase = WorkerPhase.TO_NODE.value
        task.mine_timer = 0
        unit.state = int(UnitState.WALK)
        return True