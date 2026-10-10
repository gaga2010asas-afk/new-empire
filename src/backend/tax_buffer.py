# src/backend/tax_buffer.py
"""
NEW EMPIRE v1.5.3 — Backend Agent (Proto #3).
Буфер налога вассала: формула docs/03, триггер отправки, таймаут 3 мин,
потеря группы → сброс буфера.
Канон: MASTER BRIEF v1.5 (Proto #3) + патч v1.5.3 (п.2, п.3, п.6).
Без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .constants import (
    TAX_CAPACITY_LAND_GOLD, TAX_CAPACITY_LAND_WOOD,
    TAX_CAPACITY_WATER_GOLD, TAX_CAPACITY_WATER_WOOD,
    TAX_TIMEOUT_FILL_RATIO, TAX_TIMEOUT_TICKS,
    VassalState,
)


class ColonyType(str, Enum):
    CENTRAL = "central"
    MID     = "mid"
    BORDER  = "border"


@dataclass
class Vassal:
    """
    v1.5.3, п.2: минимальный Vassal для Proto #3.
    Полная механика вассала — Прототип #5.
    """
    id: int
    faction: str
    colony_type: ColonyType
    hall_grid_x: int
    hall_grid_y: int
    state: int = int(VassalState.FREE)     # v1.5.3, п.2
    tax_buffer_gold: float = 0.0
    tax_buffer_wood: float = 0.0
    tax_capacity_gold: int = TAX_CAPACITY_LAND_GOLD
    tax_capacity_wood: int = TAX_CAPACITY_LAND_WOOD
    tax_timeout_ticks: int = 0
    pending_group: bool = False
    colony_treasury_gold: float = 0.0
    colony_treasury_wood: float = 0.0

    def is_full(self) -> bool:
        return (self.tax_buffer_gold >= self.tax_capacity_gold or
                self.tax_buffer_wood >= self.tax_capacity_wood)

    def fill_ratio(self) -> float:
        g = self.tax_buffer_gold / max(1, self.tax_capacity_gold)
        w = self.tax_buffer_wood / max(1, self.tax_capacity_wood)
        return max(g, w)

    def is_over_half(self) -> bool:
        return self.fill_ratio() > TAX_TIMEOUT_FILL_RATIO


class TaxBuffer:
    """
    Формула docs/03 (применяется каждый тик):
        налог_за_тик     = добыча * tax_rate
        казна_колонии   += добыча * (1 - tax_rate)
        буфер           += налог_за_тик
    tax_rate ∈ [0.0, 1.0] (v1.5.3, п.6). UI конвертирует 0–100% → [0,1].
    """

    def __init__(self,
                 capacity_land: Tuple[int, int] = (TAX_CAPACITY_LAND_GOLD,
                                                   TAX_CAPACITY_LAND_WOOD),
                 capacity_water: Tuple[int, int] = (TAX_CAPACITY_WATER_GOLD,
                                                    TAX_CAPACITY_WATER_WOOD),
                 timeout_ticks: int = TAX_TIMEOUT_TICKS) -> None:
        self.capacity_land = capacity_land
        self.capacity_water = capacity_water
        self.timeout_ticks = int(timeout_ticks)

    # ------------------------------------------------------------ маршрут
    def use_water_route(self, vassal: Vassal) -> None:
        vassal.tax_capacity_gold = int(self.capacity_water[0])
        vassal.tax_capacity_wood = int(self.capacity_water[1])

    def use_land_route(self, vassal: Vassal) -> None:
        vassal.tax_capacity_gold = int(self.capacity_land[0])
        vassal.tax_capacity_wood = int(self.capacity_land[1])

    # ------------------------------------------------------------ обновление
    def update(self, vassal: Vassal,
               income_gold_per_tick: float,
               income_wood_per_tick: float,
               tax_rate: float) -> bool:
        """
        Один тик. tax_rate ∈ [0.0, 1.0].
        Возвращает True, если пора отправлять группу
        (буфер полон ИЛИ таймаут 3 мин при fill_ratio > 0.5).
        """
        if not (0.0 <= tax_rate <= 1.0):
            raise ValueError(f"tax_rate {tax_rate} вне [0, 1]")
        ig, iw = float(income_gold_per_tick), float(income_wood_per_tick)
        if ig < 0 or iw < 0:
            raise ValueError("income не может быть отрицательным")

        vassal.colony_treasury_gold += ig * (1.0 - tax_rate)
        vassal.colony_treasury_wood += iw * (1.0 - tax_rate)
        vassal.tax_buffer_gold += ig * tax_rate
        vassal.tax_buffer_wood += iw * tax_rate

        if vassal.pending_group:
            return False

        if vassal.is_over_half():
            vassal.tax_timeout_ticks += 1
        else:
            vassal.tax_timeout_ticks = 0

        if vassal.is_full():
            return True
        if vassal.tax_timeout_ticks >= self.timeout_ticks:
            return True
        return False

    # ------------------------------------------------------------ отправка
    def mark_group_sent(self, vassal: Vassal) -> Tuple[int, int]:
        """Обнулить буфер, выставить pending_group=True. Вернуть груз."""
        cargo_gold = int(vassal.tax_buffer_gold)
        cargo_wood = int(vassal.tax_buffer_wood)
        vassal.tax_buffer_gold = 0.0
        vassal.tax_buffer_wood = 0.0
        vassal.tax_timeout_ticks = 0
        vassal.pending_group = True
        return cargo_gold, cargo_wood

    def mark_group_delivered(self, vassal: Vassal) -> None:
        vassal.pending_group = False

    def on_group_lost(self, vassal: Vassal) -> None:
        """v1.5.3: группа погибла — налог потерян, флаг снят, буфер пуст."""
        vassal.pending_group = False
        vassal.tax_buffer_gold = 0.0
        vassal.tax_buffer_wood = 0.0
        vassal.tax_timeout_ticks = 0