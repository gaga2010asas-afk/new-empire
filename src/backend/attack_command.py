# src/backend/attack_command.py
"""
NEW EMPIRE v1.5.11 — Backend Agent (Proto #7).
Обработка команды «Атаковать регион»: поднять Штандарт, разослать
приказы мобилизации вассалам, эмитить attack_started и vassal_mobilized.
Патч v1.5.11:
  * подписка на EVENT_BANNER_LOST → жёсткий сброс мобилизации вассалов;
  * матрица мобилизации через vassal_ai.recommended_mobilization().
Канон: MASTER BRIEF v1.5 (Proto #7, раздел 1).
Без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .banner import BannerManager
from .constants import (
    EVENT_ATTACK_STARTED, EVENT_BANNER_LOST, EVENT_VASSAL_MOBILIZED,
)
from .entities import Unit
from .events import EventBus
from .vassal_ai import VassalAI


class AttackCommandError(Exception):
    pass


@dataclass
class AttackOrder:
    hero_id: int
    target_region_id: int
    target_center_px: Tuple[float, float]
    affected_vassals: List[int] = field(default_factory=list)
    total_mobilized_units: int = 0


class AttackCommandManager:
    """
    Диспетчер команды атаки.
    Подписывается на EVENT_BANNER_LOST и сбрасывает мобилизацию
    у затронутых вассалов (патч v1.5.11, п.1).
    """

    def __init__(self,
                 banner_manager: BannerManager,
                 event_bus: Optional[EventBus] = None,
                 override_fraction: Optional[float] = None) -> None:
        """
        override_fraction — только для тестов. Если задан, применяется
        ко всем вассалам вместо матрицы recommended_mobilization().
        """
        if override_fraction is not None and not (0.0 <= override_fraction <= 1.0):
            raise AttackCommandError(
                f"override_fraction {override_fraction} вне [0, 1]")
        self.banner_manager = banner_manager
        self.event_bus = event_bus
        self.override_fraction = override_fraction
        self._affected_vassals: Dict[int, VassalAI] = {}

        if event_bus is not None:
            event_bus.subscribe(EVENT_BANNER_LOST, self._on_banner_lost)

    # ------------------------------------------------------------ API
    def issue_attack(self,
                     hero_id: int,
                     target_region_id: int,
                     target_center_px: Tuple[float, float],
                     units: Dict[int, Unit],
                     vassals: Dict[int, VassalAI],
                     church_built: bool = True) -> AttackOrder:
        if not church_built:
            raise AttackCommandError(
                "Команда атаки недоступна: Церковь не построена")
        if self.banner_manager.is_active():
            raise AttackCommandError("Штандарт уже активен")

        hero = units.get(hero_id)
        if hero is None:
            raise AttackCommandError(f"Герой {hero_id} не найден")

        # 1) Штандарт
        self.banner_manager.raise_banner(
            hero_id=hero_id,
            target_region_id=target_region_id,
            target_center_px=target_center_px,
            units=units,
        )

        order = AttackOrder(
            hero_id=int(hero_id),
            target_region_id=int(target_region_id),
            target_center_px=(float(target_center_px[0]),
                              float(target_center_px[1])),
        )
        self._affected_vassals.clear()

        # 2) Мобилизация вассалов
        for vassal_id, vassal_ai in vassals.items():
            if vassal_ai.vassal.faction != hero.faction:
                continue
            frac = (self.override_fraction
                    if self.override_fraction is not None
                    else vassal_ai.recommended_mobilization())
            vassal_ai.set_mobilization(frac)
            ids = vassal_ai.mobilized_unit_ids(units)
            self.banner_manager.register_mobilized(ids)
            self._affected_vassals[int(vassal_id)] = vassal_ai
            order.affected_vassals.append(int(vassal_id))
            order.total_mobilized_units += len(ids)

            self._emit(EVENT_VASSAL_MOBILIZED, {
                "vassal_id": int(vassal_id),
                "faction": vassal_ai.vassal.faction,
                "fraction": float(frac),
                "unit_ids": list(ids),
            })

        # 3) Итоговое событие
        self._emit(EVENT_ATTACK_STARTED, {
            "hero_id": int(hero_id),
            "target_region_id": int(target_region_id),
            "target_center_px": order.target_center_px,
            "affected_vassals": list(order.affected_vassals),
            "total_mobilized_units": int(order.total_mobilized_units),
        })
        return order

    # ------------------------------------------------------------ отмена
    def cancel_attack(self) -> None:
        """
        Экстренная отмена. `BannerManager.dismiss()` эмитит banner_lost,
        который через _on_banner_lost сбрасывает мобилизацию.
        """
        self.banner_manager.dismiss()

    # ------------------------------------------------------------ обработчик
    def _on_banner_lost(self, payload: Dict) -> None:
        """Патч v1.5.11, п.1: жёсткий сброс мобилизации затронутых вассалов."""
        for vassal_ai in self._affected_vassals.values():
            vassal_ai.set_mobilization(0.0)
        self._affected_vassals.clear()

    # ------------------------------------------------------------ утилиты
    def affected_vassal_ids(self) -> List[int]:
        return sorted(self._affected_vassals.keys())

    def _emit(self, event_type: str, payload: Dict) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event_type, payload)