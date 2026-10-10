# src/backend/banner.py
"""
NEW EMPIRE v1.5.11 — Backend Agent (Proto #7).
Штандарт: IDLE → GATHERING → MARCHING → COMBAT → IDLE.
Аура +10% урона. Патч v1.5.11: damage_multiplier отвергает мёртвых.
Канон: MASTER BRIEF v1.5 (Proto #7).
Без pygame.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import (
    BANNER_AURA_RADIUS_PX, BANNER_DAMAGE_BUFF, BANNER_GATHERING_TICKS,
    EVENT_BANNER_LOST, EVENT_BANNER_RAISED, BannerState, TARGET_FPS,
    UnitState,
)
from .entities import Unit
from .events import EventBus


class BannerError(Exception):
    pass


@dataclass
class Banner:
    target_region_id: int
    target_center_px: Tuple[float, float]
    assigned_hero_id: int
    state: int = int(BannerState.IDLE)
    gathering_timer: int = 0
    mobilized_units: List[int] = field(default_factory=list)
    aura_radius_px: float = BANNER_AURA_RADIUS_PX

    def is_active(self) -> bool:
        return self.state != int(BannerState.IDLE)


class BannerManager:
    def __init__(self,
                 event_bus: Optional[EventBus] = None,
                 aura_radius_px: float = BANNER_AURA_RADIUS_PX,
                 gathering_ticks: int = BANNER_GATHERING_TICKS) -> None:
        self.event_bus = event_bus
        self.aura_radius_px = float(aura_radius_px)
        self.gathering_ticks = int(gathering_ticks)
        self.banner: Optional[Banner] = None

    # ------------------------------------------------------------ доступ
    def is_active(self) -> bool:
        return self.banner is not None and self.banner.is_active()

    def get(self) -> Optional[Banner]:
        return self.banner

    def assigned_hero_id(self) -> Optional[int]:
        return self.banner.assigned_hero_id if self.banner else None

    # ------------------------------------------------------------ поднять
    def raise_banner(self,
                     hero_id: int,
                     target_region_id: int,
                     target_center_px: Tuple[float, float],
                     units: Dict[int, Unit]) -> Banner:
        if self.is_active():
            raise BannerError("Штандарт уже активен")
        if hero_id not in units:
            raise BannerError(f"Герой {hero_id} не найден")
        hero = units[hero_id]
        if hero.hp <= 0 or hero.state == int(UnitState.DEAD):
            raise BannerError(f"Герой {hero_id} мёртв")

        self.banner = Banner(
            target_region_id=int(target_region_id),
            target_center_px=(float(target_center_px[0]),
                              float(target_center_px[1])),
            assigned_hero_id=int(hero_id),
            state=int(BannerState.GATHERING),
            gathering_timer=0,
            mobilized_units=[],
            aura_radius_px=self.aura_radius_px,
        )
        hero.state = int(UnitState.WALK)
        self._emit(EVENT_BANNER_RAISED, {
            "hero_id": hero_id,
            "target_region_id": target_region_id,
            "target_center_px": self.banner.target_center_px,
            "state": int(BannerState.GATHERING),
        })
        return self.banner

    # ------------------------------------------------------------ сбор
    def register_mobilized(self, unit_ids: List[int]) -> None:
        if self.banner is None:
            raise BannerError("Штандарт не активен")
        for uid in unit_ids:
            if uid not in self.banner.mobilized_units:
                self.banner.mobilized_units.append(int(uid))

    def mobilized_ids(self) -> List[int]:
        return list(self.banner.mobilized_units) if self.banner else []

    # ------------------------------------------------------------ тик
    def update(self, dt: float, units: Dict[int, Unit]) -> None:
        if self.banner is None or not self.banner.is_active():
            return
        if dt <= 0:
            raise BannerError("dt должен быть > 0")

        if self.banner.state == int(BannerState.GATHERING):
            ticks = max(1, int(round(dt * TARGET_FPS)))
            self.banner.gathering_timer += ticks
            if self.banner.gathering_timer >= self.gathering_ticks:
                self.enter_march()

        hero = units.get(self.banner.assigned_hero_id)
        if hero is None or hero.hp <= 0 \
                or hero.state == int(UnitState.DEAD):
            self.on_hero_died(self.banner.assigned_hero_id)

    # ------------------------------------------------------------ переходы
    def enter_march(self) -> None:
        if self.banner is None:
            raise BannerError("Штандарт не активен")
        self.banner.state = int(BannerState.MARCHING)

    def enter_combat(self) -> None:
        if self.banner is None:
            raise BannerError("Штандарт не активен")
        self.banner.state = int(BannerState.COMBAT)

    def dismiss(self) -> None:
        if self.banner is None:
            return
        payload = {
            "hero_id": self.banner.assigned_hero_id,
            "target_region_id": self.banner.target_region_id,
            "reason": "dismissed",
        }
        self.banner = None
        self._emit(EVENT_BANNER_LOST, payload)

    def on_hero_died(self, hero_id: int) -> None:
        if self.banner is None:
            return
        if self.banner.assigned_hero_id != hero_id:
            return
        payload = {
            "hero_id": hero_id,
            "target_region_id": self.banner.target_region_id,
            "reason": "hero_died",
        }
        self.banner = None
        self._emit(EVENT_BANNER_LOST, payload)

    # ------------------------------------------------------------ аура
    def damage_multiplier(self, unit: Unit,
                          units: Dict[int, Unit]) -> float:
        """
        +10% урона, если unit в радиусе ауры живого Героя-Штандарта.
        Патч v1.5.11, п.2: мёртвый получатель баффа отвергается.
        """
        if unit.hp <= 0 or unit.state == int(UnitState.DEAD):
            return 1.0
        if self.banner is None or not self.banner.is_active():
            return 1.0
        hero = units.get(self.banner.assigned_hero_id)
        if hero is None or hero.hp <= 0 or hero.state == int(UnitState.DEAD):
            return 1.0
        if hero.faction != unit.faction:
            return 1.0
        dx = unit.pixel_x - hero.pixel_x
        dy = unit.pixel_y - hero.pixel_y
        if math.hypot(dx, dy) <= self.banner.aura_radius_px:
            return 1.0 + BANNER_DAMAGE_BUFF
        return 1.0

    # ------------------------------------------------------------ утилиты
    def _emit(self, event_type: str, payload: Dict) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event_type, payload)