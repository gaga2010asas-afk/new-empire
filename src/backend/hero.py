# src/backend/hero.py
"""
NEW EMPIRE v1.5.16 — Backend Agent (Proto #6).
Hero — наследник Unit. Уровни, XP, mana, аура, способности.

Патч v1.5.16 (п.4): жёсткий контракт `faction` vs `hero_role`.
  faction   ∈ {"human", "orc"}   — сторона
  hero_role ∈ HERO_ROLES         — класс героя ("mage", "paladin", …)
Если в `faction` случайно передали роль — сообщение об ошибке
объясняет подмену полей.

Без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .constants import (
    ABILITY_SCHEDULE, FACTION_IDS, HERO_AURA, HERO_CASTER_ROLES,
    HERO_MANA_CASTER, HERO_MANA_CASTER_HIGH, HERO_MANA_REGEN_TICKS,
    HERO_MAX_LEVEL, HERO_ROLES, TARGET_FPS, UnitState,
    XP_BUILDING_KILL, XP_CARAVAN_KILL, XP_HERO_KILL,
    XP_THRESHOLDS, XP_UNIT_KILL,
)
from .entities import Unit


# Ростер-слоты → роль. Слот одинаков для обеих фракций.
_HUMAN_TO_ROLE: Dict[str, str] = {
    "captain": "captain",
    "ranger":  "ranger",
    "paladin": "paladin",
    "mage":    "mage",
    "griffin": "griffin",
}
_ORC_TO_ROLE: Dict[str, str] = {
    "captain": "captain",
    "ranger":  "ranger",
    "paladin": "death_knight",
    "mage":    "warlock",
    "griffin": "griffin",
}

# Обратный список — слоты ростера. Используется в валидации.
ROSTER_SLOTS: frozenset = frozenset(_HUMAN_TO_ROLE.keys())


class HeroError(Exception):
    pass


def _validate_faction(faction: str) -> None:
    """
    Патч v1.5.16, п.4: если в `faction` передали роль — подсказываем.
    Частый источник ошибок: Hero.from_role(1, "mage", "mage", ...).
    """
    if faction in FACTION_IDS:
        return
    if faction in HERO_ROLES:
        raise HeroError(
            f"'{faction}' — это роль, а не фракция. "
            f"Ожидается faction ∈ {FACTION_IDS}, "
            f"а '{faction}' передаётся в slot (2-й аргумент).")
    raise HeroError(
        f"Неизвестная фракция '{faction}'. "
        f"Ожидается одно из {FACTION_IDS}.")


def role_for(faction: str, slot: str) -> str:
    """slot ∈ {'captain','ranger','paladin','mage','griffin'} — слот ростера."""
    _validate_faction(faction)
    mapping = _HUMAN_TO_ROLE if faction == "human" else _ORC_TO_ROLE
    if slot not in mapping:
        raise HeroError(f"Неизвестный слот '{slot}'. Допустимо: {sorted(ROSTER_SLOTS)}")
    return mapping[slot]


def default_max_mana(role: str) -> int:
    """Максимум маны: 200 паладин/DK, 250 маг/варлок, 0 прочим."""
    if role in ("paladin", "death_knight"):
        return HERO_MANA_CASTER
    if role in ("mage", "warlock"):
        return HERO_MANA_CASTER_HIGH
    return 0


@dataclass
class Hero(Unit):
    """Наследник Unit. Поля героя инкапсулированы."""

    hero_level: int = 1
    xp: int = 0
    mana: int = 0
    max_mana: int = 0
    aura_color: Tuple[int, int, int, int] = (255, 255, 255, 128)
    hero_role: str = "captain"
    abilities: List[str] = field(default_factory=list)

    _mana_tick_accum: int = field(default=0, init=False, repr=False)
    _cooldowns: Dict[str, int] = field(
        default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.faction not in FACTION_IDS:
            raise HeroError(
                f"Hero.faction = '{self.faction}' не из {FACTION_IDS}")
        if not (1 <= self.hero_level <= HERO_MAX_LEVEL):
            raise HeroError(
                f"hero_level {self.hero_level} вне [1, {HERO_MAX_LEVEL}]")
        if self.xp < 0:
            raise HeroError("xp должен быть >= 0")
        if self.max_mana < 0:
            raise HeroError("max_mana должен быть >= 0")
        if not (0 <= self.mana <= self.max_mana):
            raise HeroError("mana вне [0, max_mana]")
        if self.hero_role not in HERO_ROLES:
            raise HeroError(f"hero_role '{self.hero_role}' неизвестен")

    # ------------------------------------------------------------ XP
    def xp_to_next_level(self) -> Optional[int]:
        if self.hero_level >= HERO_MAX_LEVEL:
            return None
        return max(0, XP_THRESHOLDS[self.hero_level + 1] - self.xp)

    def add_xp(self, amount: int) -> int:
        if amount < 0:
            raise HeroError("amount должен быть >= 0")
        if self.hero_level >= HERO_MAX_LEVEL:
            return 0
        self.xp += int(amount)
        gained = 0
        while (self.hero_level < HERO_MAX_LEVEL
               and self.xp >= XP_THRESHOLDS[self.hero_level + 1]):
            self.hero_level += 1
            gained += 1
            self._learn_for_level(self.hero_level)
        return gained

    def _learn_for_level(self, level: int) -> List[str]:
        schedule = ABILITY_SCHEDULE.get(self.hero_role, ())
        learned: List[str] = []
        for lvl, ability_id in schedule:
            if lvl == level and ability_id not in self.abilities:
                self.abilities.append(ability_id)
                learned.append(ability_id)
        return learned

    def on_unit_killed(self) -> int:
        return self.add_xp(XP_UNIT_KILL)

    def on_hero_killed(self) -> int:
        return self.add_xp(XP_HERO_KILL)

    def on_building_destroyed(self) -> int:
        return self.add_xp(XP_BUILDING_KILL)

    def on_caravan_killed(self) -> int:
        return self.add_xp(XP_CARAVAN_KILL)

    # ------------------------------------------------------------ mana
    def spend_mana(self, cost: int) -> bool:
        if cost < 0:
            raise HeroError("cost должен быть >= 0")
        if self.mana < cost:
            return False
        self.mana -= int(cost)
        return True

    def regen_mana(self, dt: float) -> None:
        """+1 мана каждые HERO_MANA_REGEN_TICKS тиков = 5.0/сек при 60 FPS."""
        if dt <= 0 or self.max_mana <= 0:
            return
        ticks = int(round(dt * TARGET_FPS))
        if ticks <= 0:
            return
        self._mana_tick_accum += ticks
        gained = self._mana_tick_accum // HERO_MANA_REGEN_TICKS
        if gained > 0:
            self.mana = min(self.max_mana, self.mana + int(gained))
            self._mana_tick_accum -= int(gained) * HERO_MANA_REGEN_TICKS
        if self.mana >= self.max_mana:
            self._mana_tick_accum = 0

    # ------------------------------------------------------------ cooldowns
    def is_on_cooldown(self, ability_id: str) -> bool:
        return self._cooldowns.get(ability_id, 0) > 0

    def set_cooldown(self, ability_id: str, ticks: int) -> None:
        if ticks <= 0:
            self._cooldowns.pop(ability_id, None)
        else:
            self._cooldowns[ability_id] = int(ticks)

    def tick_cooldowns(self) -> None:
        for k in list(self._cooldowns.keys()):
            self._cooldowns[k] -= 1
            if self._cooldowns[k] <= 0:
                del self._cooldowns[k]

    # ------------------------------------------------------------ фабрика
    @classmethod
    def from_role(cls, unit_id: int, faction: str, slot: str,
                  pixel_x: float, pixel_y: float,
                  owner_id: int = 0) -> "Hero":
        """
        faction ∈ {"human", "orc"} — сторона.
        slot    ∈ ROSTER_SLOTS       — слот ростера.
        Поле Hero.type устанавливается в роль ("mage", "paladin", …).
        Поле Hero.faction — сторона ("human"/"orc").
        """
        role = role_for(faction, slot)
        max_mana = default_max_mana(role)
        return cls(
            id=unit_id, faction=faction,
            type=f"{role}",
            pixel_x=float(pixel_x), pixel_y=float(pixel_y),
            hp=200, max_hp=200, owner_id=owner_id,
            hero_level=1, xp=0,
            mana=max_mana, max_mana=max_mana,
            aura_color=HERO_AURA.get(role, (255, 255, 255, 128)),
            hero_role=role,
            abilities=[],
            stats={"triad_role": "infantry",
                   "damage": 20, "armor": 4,
                   "is_hero": True,
                   "slot": slot},
        )