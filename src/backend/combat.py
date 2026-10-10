# src/backend/combat.py
"""
NEW EMPIRE v1.5.5 — Backend Agent (Proto #4).
Триада урона x2.0, апгрейды кузницы, формула урона, событие building_destroyed.
Патч v1.5.5: UpgradeRegistry.get() бросает KeyError, apply_damage шлёт событие.
Без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .constants import (
    EVENT_BUILDING_DESTROYED,
    TRIAD_COUNTER_MULTIPLIER,
    TRIAD_ROLE_ARTILLERY,
    TRIAD_ROLE_INFANTRY,
    TRIAD_ROLE_TANK,
    BuildingState,
    UnitState,
)
from .entities import Building, Unit
from .events import EventBus


# ---------------------------------------------------------------------------
# Триады
# ---------------------------------------------------------------------------
PLAYER_TRIAD: Dict[str, str] = {
    TRIAD_ROLE_TANK:      TRIAD_ROLE_ARTILLERY,
    TRIAD_ROLE_ARTILLERY: TRIAD_ROLE_INFANTRY,
    TRIAD_ROLE_INFANTRY:  TRIAD_ROLE_TANK,
}

VASSAL_TRIAD: Dict[str, str] = {
    "cavalry":  "ranged",
    "ranged":   "infantry",
    "infantry": "cavalry",
}

# [НЕТ ДАННЫХ] — строковые роли авиации канон не задаёт → x1.0 всегда.
AVIATION_ROLES: frozenset = frozenset()


def triad_multiplier(attacker_role: Optional[str],
                     defender_role: Optional[str]) -> float:
    if not attacker_role or not defender_role:
        return 1.0
    if PLAYER_TRIAD.get(attacker_role) == defender_role:
        return TRIAD_COUNTER_MULTIPLIER
    if VASSAL_TRIAD.get(attacker_role) == defender_role:
        return TRIAD_COUNTER_MULTIPLIER
    return 1.0


# ---------------------------------------------------------------------------
# Апгрейды кузницы
# ---------------------------------------------------------------------------
MAX_UPGRADE_LEVEL: int = 3
UPGRADE_COSTS: tuple[int, int, int] = (100, 200, 400)


@dataclass
class UpgradeState:
    faction: str
    damage_level: int = 0
    armor_level: int = 0

    def __post_init__(self) -> None:
        if not (0 <= self.damage_level <= MAX_UPGRADE_LEVEL):
            raise ValueError(
                f"damage_level {self.damage_level} вне [0, {MAX_UPGRADE_LEVEL}]")
        if not (0 <= self.armor_level <= MAX_UPGRADE_LEVEL):
            raise ValueError(
                f"armor_level {self.armor_level} вне [0, {MAX_UPGRADE_LEVEL}]")


class UpgradeRegistry:
    """
    v1.5.5, п.4: get() бросает KeyError для незарегистрированных фракций.
    Регистрация — только явная, через register().
    """

    def __init__(self) -> None:
        self._states: Dict[str, UpgradeState] = {}

    def register(self, faction: str) -> UpgradeState:
        if faction not in self._states:
            self._states[faction] = UpgradeState(faction=faction)
        return self._states[faction]

    def get(self, faction: str) -> UpgradeState:
        if faction not in self._states:
            raise KeyError(
                f"Фракция '{faction}' не зарегистрирована в UpgradeRegistry")
        return self._states[faction]

    def cost_to_next_damage(self, faction: str) -> Optional[int]:
        st = self.get(faction)
        if st.damage_level >= MAX_UPGRADE_LEVEL:
            return None
        return UPGRADE_COSTS[st.damage_level]

    def cost_to_next_armor(self, faction: str) -> Optional[int]:
        st = self.get(faction)
        if st.armor_level >= MAX_UPGRADE_LEVEL:
            return None
        return UPGRADE_COSTS[st.armor_level]

    def upgrade_damage(self, faction: str) -> bool:
        st = self.get(faction)
        if st.damage_level >= MAX_UPGRADE_LEVEL:
            return False
        st.damage_level += 1
        return True

    def upgrade_armor(self, faction: str) -> bool:
        st = self.get(faction)
        if st.armor_level >= MAX_UPGRADE_LEVEL:
            return False
        st.armor_level += 1
        return True


# ---------------------------------------------------------------------------
# Урон
# ---------------------------------------------------------------------------
def _get_role(entity) -> Optional[str]:
    stats = getattr(entity, "stats", None)
    if isinstance(stats, dict):
        return stats.get("triad_role")
    return None


def _get_damage(entity) -> int:
    stats = getattr(entity, "stats", None)
    if isinstance(stats, dict):
        return int(stats.get("damage", 0))
    return 0


def _get_armor(entity) -> int:
    stats = getattr(entity, "stats", None)
    if isinstance(stats, dict):
        return int(stats.get("armor", 0))
    return 0


def calculate_damage(attacker, defender,
                     upgrades: Optional[UpgradeRegistry] = None,
                     attacker_role: Optional[str] = None,
                     defender_role: Optional[str] = None) -> int:
    """
    damage_per_hit = max(1, atk * multiplier - armor)
    Если upgrades передан — фракции должны быть зарегистрированы.
    """
    atk_role = attacker_role if attacker_role is not None else _get_role(attacker)
    def_role = defender_role if defender_role is not None else _get_role(defender)

    atk = _get_damage(attacker)
    armor = _get_armor(defender)

    if upgrades is not None:
        a_fac = getattr(attacker, "faction", None)
        d_fac = getattr(defender, "faction", None)
        if a_fac:
            atk += upgrades.get(a_fac).damage_level
        if d_fac:
            armor += upgrades.get(d_fac).armor_level

    mult = triad_multiplier(atk_role, def_role)
    raw = atk * mult - armor
    return max(1, int(raw))


def apply_damage(target, damage: int,
                 event_bus: Optional[EventBus] = None) -> bool:
    """
    Списывает HP. При hp <= 0 — DEAD (Unit) / DESTROYED (Building).
    v1.5.5, п.2: при уничтожении Building эмитит 'building_destroyed'.
    """
    if damage < 0:
        raise ValueError("damage должен быть >= 0")
    target.hp = max(0, target.hp - int(damage))
    if target.hp <= 0:
        if isinstance(target, Unit):
            target.state = int(UnitState.DEAD)
        elif isinstance(target, Building):
            target.state = int(BuildingState.DESTROYED)
            if event_bus is not None:
                event_bus.emit(EVENT_BUILDING_DESTROYED, {
                    "id": target.id,
                    "grid_x": target.grid_x,
                    "grid_y": target.grid_y,
                    "width": target.width,
                    "height": target.height,
                    "faction": target.faction,
                    "type": target.type,
                })
        return True
    return False