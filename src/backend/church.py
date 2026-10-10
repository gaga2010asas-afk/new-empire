# src/backend/church.py
"""
NEW EMPIRE v1.5.8 — Backend Agent (Proto #6).
Церковь: спавн 5 героев, складчина вассалов, возрождение за 500 золота.
Патч v1.5.8: формула tick_contribution = BASE × (1 − tax)^3, жёсткий блок 90%+.
Канон: MASTER BRIEF v1.5 (Proto #6, раздел 1).
Без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import (
    CHURCH_CONTRIBUTION_BASE, CHURCH_REVIVE_COOLDOWN_TICKS,
    CHURCH_REVIVE_COST, CHURCH_TAX_HARD_BLOCK, FACTION_IDS,
    TARGET_FPS, TILE_SIZE,
)
from .hero import Hero
from .tax_buffer import Vassal


_HERO_SLOTS: Tuple[str, ...] = (
    "captain", "ranger", "paladin", "mage", "griffin",
)


class ChurchError(Exception):
    pass


@dataclass
class Church:
    id: str
    faction: str
    grid_x: int
    grid_y: int
    contribution_pool: int = 0
    dead_heroes_queue: List[Dict] = field(default_factory=list)
    cooldown_ticks: int = 0
    active_revive: Optional[Dict] = None
    _pool_fraction: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.faction not in FACTION_IDS:
            raise ChurchError(f"Неизвестная фракция '{self.faction}'")

    # ------------------------------------------------------------ спавн
    def spawn_initial_heroes(self, first_unit_id: int = 1000
                             ) -> List[Hero]:
        """
        Мгновенно и бесплатно — 5 героев 1-го уровня, по канону.
        Позиции — рядом с ратушей.
        """
        heroes: List[Hero] = []
        for i, slot in enumerate(_HERO_SLOTS):
            gx = self.grid_x + 2 + (i % 3)
            gy = self.grid_y + (i // 3)
            hero = Hero.from_role(
                unit_id=first_unit_id + i,
                faction=self.faction,
                slot=slot,
                pixel_x=(gx + 0.5) * TILE_SIZE,
                pixel_y=(gy + 0.5) * TILE_SIZE,
            )
            heroes.append(hero)
        return heroes

    # ------------------------------------------------------------ смерть
    def on_hero_died(self, hero: Hero) -> None:
        self.dead_heroes_queue.append({
            "slot": hero.stats.get("slot", "captain"),
            "hero_level": hero.hero_level,
            "xp": hero.xp,
            "abilities": list(hero.abilities),
        })

    # ------------------------------------------------------------ обновление
    def update(self, dt: float,
               vassals: List[Vassal],
               global_tax: float,
               current_tick: int = 0) -> Optional[Hero]:
        """
        Один вызов — один тик (или несколько, если dt > 1/60).
        Возвращает Hero, если возрождение произошло на этом шаге.
        """
        if dt <= 0:
            raise ChurchError("dt должен быть > 0")
        if not (0.0 <= global_tax <= 1.0):
            raise ChurchError(f"global_tax {global_tax} вне [0, 1]")

        ticks = max(1, int(round(dt * TARGET_FPS)))

        # Кулдаун возрождения
        if self.cooldown_ticks > 0:
            self.cooldown_ticks = max(0, self.cooldown_ticks - ticks)

        # Ждём окончания кулдауна перед спавном
        if self.active_revive is not None:
            if self.cooldown_ticks == 0:
                hero = self._spawn_from_spec(self.active_revive)
                self.active_revive = None
                return hero
            return None

        if not self.dead_heroes_queue:
            return None

        # Собираем складчину
        self._collect_contributions(dt, vassals, global_tax)

        if self.contribution_pool >= CHURCH_REVIVE_COST:
            self.contribution_pool -= CHURCH_REVIVE_COST
            spec = self.dead_heroes_queue.pop(0)
            self.active_revive = spec
            self.cooldown_ticks = CHURCH_REVIVE_COOLDOWN_TICKS
            hero = self._spawn_from_spec(spec)
            self.active_revive = None
            return hero
        return None

    # ------------------------------------------------------------ внутреннее
    def _collect_contributions(self, dt: float,
                               vassals: List[Vassal],
                               global_tax: float) -> None:
        """
        Патч v1.5.8: tick_contribution = BASE × (1 − tax)^3.
        При tax >= 0.90 — жёсткий блок.
        """
        if global_tax >= CHURCH_TAX_HARD_BLOCK:
            return
        rate_per_vassal = CHURCH_CONTRIBUTION_BASE * (1.0 - global_tax) ** 3
        total = 0.0
        for v in vassals:
            if v.faction != self.faction:
                continue
            want = rate_per_vassal * dt
            if want <= 0:
                continue
            give = min(want, v.colony_treasury_gold)
            if give <= 0:
                continue
            v.colony_treasury_gold -= give
            total += give
        self._pool_fraction += total
        whole = int(self._pool_fraction)
        if whole > 0:
            self.contribution_pool += whole
            self._pool_fraction -= whole

    def _spawn_from_spec(self, spec: Dict) -> Hero:
        slot = spec.get("slot", "captain")
        hero = Hero.from_role(
            unit_id=100_000 + hash((self.id, slot, self.cooldown_ticks)) % 900_000,
            faction=self.faction,
            slot=slot,
            pixel_x=(self.grid_x + 2.5) * TILE_SIZE,
            pixel_y=(self.grid_y + 2.5) * TILE_SIZE,
        )
        hero.hero_level = int(spec.get("hero_level", 1))
        hero.xp = int(spec.get("xp", 0))
        hero.abilities = list(spec.get("abilities", []))
        hero.mana = hero.max_mana
        return hero