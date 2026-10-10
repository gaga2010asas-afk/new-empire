# src/backend/vassal_ai.py
"""
NEW EMPIRE v1.5.21 — Backend Agent (Proto #5 + #7).
Стейт-машина вассала + мобилизация.

Патч v1.5.21, п.1:
  * Поле сменено на приватное `_encircled`, наружу — property `encircled`
    (для save_load).
  * `set_encircled(False)` БЕЗУСЛОВНО сбрасывает ticks_since_delivery.
  * `update()` инкрементирует ticks_since_delivery ТОЛЬКО под `if self._encircled`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .constants import (
    BREAKTHROUGH_TICKS, MAX_CATAPULTS_BORDER, MAX_CATAPULTS_CENTRAL,
    MAX_CATAPULTS_MID, MAX_TOWERS_BORDER, MAX_TOWERS_CENTRAL,
    MAX_TOWERS_MID, MOBILIZATION_ECONOMY_TABLE,
    MOBILIZATION_FRACTION_BREAKTHROUGH,
    MOBILIZATION_FRACTION_CENTRAL_BORDER_FREE,
    MOBILIZATION_FRACTION_ENCIRCLED,
    MOBILIZATION_FRACTION_MID_FREE,
    TARGET_FPS, UnitState, VassalState,
)
from .entities import Unit
from .map_data import MapData
from .tax_buffer import ColonyType, Vassal


@dataclass
class ColonyPolicy:
    max_towers: int
    max_catapults: int
    troop_kind: str
    tax_low: float
    tax_high: float


def policy_for(colony_type: str) -> ColonyPolicy:
    if colony_type == "central":
        return ColonyPolicy(max_towers=MAX_TOWERS_CENTRAL,
                            max_catapults=MAX_CATAPULTS_CENTRAL,
                            troop_kind="elite",
                            tax_low=0.60, tax_high=0.80)
    if colony_type == "mid":
        return ColonyPolicy(max_towers=MAX_TOWERS_MID,
                            max_catapults=MAX_CATAPULTS_MID,
                            troop_kind="simple",
                            tax_low=0.30, tax_high=0.50)
    if colony_type == "border":
        return ColonyPolicy(max_towers=MAX_TOWERS_BORDER,
                            max_catapults=MAX_CATAPULTS_BORDER,
                            troop_kind="raiders",
                            tax_low=0.10, tax_high=0.20)
    raise ValueError(f"Неизвестный тип колонии '{colony_type}'")


def economy_penalty_from_mobilization(fraction: float) -> float:
    if fraction <= 0.0:
        return 0.0
    if fraction >= 1.0:
        return 1.0
    for upper, penalty in MOBILIZATION_ECONOMY_TABLE:
        if fraction <= upper:
            return float(penalty)
    return 1.0


def economy_multiplier_from_mobilization(fraction: float) -> float:
    return max(0.0, 1.0 - economy_penalty_from_mobilization(fraction))


def _colony_type_str(colony_type) -> str:
    if isinstance(colony_type, ColonyType):
        return colony_type.value
    return str(colony_type)


def mobilization_fraction_for(colony_type: str, state: int) -> float:
    if state == int(VassalState.BREAKTHROUGH):
        return MOBILIZATION_FRACTION_BREAKTHROUGH
    if state == int(VassalState.ENCIRCLED):
        return MOBILIZATION_FRACTION_ENCIRCLED
    if colony_type == "mid":
        return MOBILIZATION_FRACTION_MID_FREE
    return MOBILIZATION_FRACTION_CENTRAL_BORDER_FREE


class VassalAI:
    def __init__(self,
                 vassal: Vassal,
                 hall_id: str,
                 region_center: Tuple[int, int],
                 main_hall_grid: Tuple[int, int],
                 map_data: Optional[MapData] = None,
                 army_ids: Optional[List[int]] = None,
                 worker_ids: Optional[List[int]] = None) -> None:
        self.vassal = vassal
        self.hall_id = hall_id
        self.region_center = (int(region_center[0]), int(region_center[1]))
        self.main_hall_grid = (int(main_hall_grid[0]),
                               int(main_hall_grid[1]))
        self.map_data = map_data
        self.army_ids: List[int] = list(army_ids) if army_ids else []
        self.worker_ids: List[int] = list(worker_ids) if worker_ids else []

        self.state: int = int(VassalState.FREE)
        self.ticks_since_delivery: int = 0
        self._encircled: bool = False
        self.breakthrough_triggered: bool = False
        self.mobilization: float = 0.0

        self.policy = policy_for(_colony_type_str(vassal.colony_type))

    # ------------------------------------------------------------ encircled
    @property
    def encircled(self) -> bool:
        return self._encircled

    @encircled.setter
    def encircled(self, value: bool) -> None:
        """Прямое присваивание — БЕЗ побочных эффектов (для save_load)."""
        self._encircled = bool(value)

    def set_encircled(self, value: bool) -> None:
        """
        Патч v1.5.21, п.1: сброс ticks_since_delivery БЕЗУСЛОВНЫЙ при False.
        """
        self._encircled = bool(value)
        if not self._encircled:
            self.ticks_since_delivery = 0

    def on_caravan_delivered(self) -> None:
        self.ticks_since_delivery = 0

    # ------------------------------------------------------------ тик
    def update(self, dt: float = 1.0 / TARGET_FPS) -> None:
        """
        Патч v1.5.21, п.1: инкремент счётчика ТОЛЬКО под блокадой.
        Вне блокады ticks_since_delivery не растёт.
        """
        if self._encircled:
            ticks = max(1, int(round(dt * TARGET_FPS)))
            self.ticks_since_delivery += ticks
        self._update_state()

    def _update_state(self) -> None:
        if self._encircled and self.ticks_since_delivery >= BREAKTHROUGH_TICKS:
            if self.state != int(VassalState.BREAKTHROUGH):
                self.state = int(VassalState.BREAKTHROUGH)
                self.breakthrough_triggered = True
        elif self._encircled:
            self.state = int(VassalState.ENCIRCLED)
        else:
            self.state = int(VassalState.FREE)
            self.breakthrough_triggered = False

    # ------------------------------------------------------------ мобилизация
    def set_mobilization(self, fraction: float) -> None:
        if not (0.0 <= fraction <= 1.0):
            raise ValueError(f"mobilization {fraction} вне [0, 1]")
        self.mobilization = float(fraction)

    def get_mobilization(self) -> float:
        return self.mobilization

    def recommended_mobilization(self) -> float:
        return mobilization_fraction_for(
            _colony_type_str(self.vassal.colony_type), self.state)

    def economy_multiplier(self) -> float:
        return economy_multiplier_from_mobilization(self.mobilization)

    def mobilized_unit_ids(self, units: Dict[int, Unit]) -> List[int]:
        if self.mobilization <= 0.0:
            return []
        alive: List[int] = []
        for uid in self.army_ids:
            u = units.get(uid)
            if u is None:
                continue
            if u.hp <= 0 or u.state == int(UnitState.DEAD):
                continue
            alive.append(int(uid))
        n = int(self.mobilization * len(alive))
        return alive[:n]

    def add_army_unit(self, uid: int) -> None:
        if uid not in self.army_ids:
            self.army_ids.append(int(uid))

    def remove_army_unit(self, uid: int) -> None:
        try:
            self.army_ids.remove(int(uid))
        except ValueError:
            pass

    # ------------------------------------------------------------ запросы
    def is_free(self) -> bool:
        return self.state == int(VassalState.FREE)

    def is_encircled(self) -> bool:
        return self.state == int(VassalState.ENCIRCLED)

    def is_breakthrough(self) -> bool:
        return self.state == int(VassalState.BREAKTHROUGH)

    def get_breakthrough_force(self) -> Dict:
        return {
            "vassal_id": self.vassal.id,
            "faction": self.vassal.faction,
            "army_ids": list(self.army_ids),
            "worker_ids": list(self.worker_ids),
            "cargo_gold": int(self.vassal.tax_buffer_gold),
            "cargo_wood": int(self.vassal.tax_buffer_wood),
            "target_grid": self.main_hall_grid,
            "origin_grid": self.region_center,
        }