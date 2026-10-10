# src/backend/hero_abilities.py
"""
NEW EMPIRE v1.5.19 — Backend Agent (Proto #6).
Математика заклинаний WC2. Спецификации, каст, списание mana, AOE.

Импорты — ТОЛЬКО относительные (.hero, .entities, .constants).
Абсолютные `from backend.*` внутри пакета backend запрещены: это
создаёт циклический импорт и ломает инициализацию модуля.

Без pygame.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .constants import TILE_SIZE
from .entities import Building, Unit
from .hero import Hero


class HeroAbilityError(Exception):
    pass


@dataclass(frozen=True)
class SpellSpec:
    id: str
    name: str
    mana_cost: int
    cooldown_ticks: int
    range_px: float
    target: str           # "self" | "unit_ally" | "unit_enemy" | "point"
    damage: int = 0
    heal: int = 0
    aoe_radius_px: float = 0.0
    duration_ticks: int = 0
    speed_multiplier: float = 1.0


SPELLS: Dict[str, SpellSpec] = {
    # --- Paladin ---
    "healing":         SpellSpec("healing", "Healing", 25, 60, 250,
                                 "unit_ally", heal=50),
    "holy_vision":     SpellSpec("holy_vision", "Holy Vision", 15, 60, 1000,
                                 "point"),
    "exorcism":        SpellSpec("exorcism", "Exorcism", 30, 120, 250,
                                 "unit_enemy", damage=40),
    # --- Mage ---
    "fireball":        SpellSpec("fireball", "Fireball", 30, 60, 400,
                                 "unit_enemy", damage=40),
    "slow":            SpellSpec("slow", "Slow", 25, 120, 350,
                                 "unit_enemy",
                                 duration_ticks=600, speed_multiplier=0.5),
    "flame_shield":    SpellSpec("flame_shield", "Flame Shield", 30, 180, 250,
                                 "unit_ally", duration_ticks=600),
    "invisibility":    SpellSpec("invisibility", "Invisibility", 40, 300, 250,
                                 "unit_ally", duration_ticks=900),
    "polymorph":       SpellSpec("polymorph", "Polymorph", 50, 300, 300,
                                 "unit_enemy", duration_ticks=600),
    "blizzard":        SpellSpec("blizzard", "Blizzard", 60, 240, 500,
                                 "point", damage=30,
                                 aoe_radius_px=TILE_SIZE * 1.5),
    # --- Death Knight ---
    "touch_of_darkness": SpellSpec("touch_of_darkness", "Touch of Darkness",
                                   30, 60, 250, "unit_enemy", damage=40),
    "death_coil":      SpellSpec("death_coil", "Death Coil", 35, 60, 400,
                                 "unit_enemy", damage=45),
    "haste":           SpellSpec("haste", "Haste", 25, 120, 250,
                                 "unit_ally",
                                 duration_ticks=600, speed_multiplier=1.5),
    "unholy_armor":    SpellSpec("unholy_armor", "Unholy Armor", 30, 180, 250,
                                 "unit_ally", duration_ticks=600),
    "raise_dead":      SpellSpec("raise_dead", "Raise Dead", 50, 300, 300,
                                 "point"),
    "death_and_decay": SpellSpec("death_and_decay", "Death and Decay",
                                 60, 240, 500, "point", damage=25,
                                 aoe_radius_px=TILE_SIZE * 1.5),
    "whirlwind":       SpellSpec("whirlwind", "Whirlwind", 40, 120, 0,
                                 "self", damage=30,
                                 aoe_radius_px=TILE_SIZE * 1.0),
    # --- Warlock (WC1) ---
    "summon_spider":   SpellSpec("summon_spider", "Summon Spider", 40, 240, 300,
                                 "point"),
    "poison_cloud":    SpellSpec("poison_cloud", "Poison Cloud", 35, 120, 400,
                                 "point", damage=20,
                                 aoe_radius_px=TILE_SIZE * 1.25),
    "summon_demon":    SpellSpec("summon_demon", "Summon Demon", 70, 400, 300,
                                 "point"),
}


@dataclass
class CastResult:
    success: bool
    spell_id: str = ""
    reason: str = ""
    healed: Dict[int, int] = field(default_factory=dict)
    damaged: Dict[int, int] = field(default_factory=dict)
    buffs: List[Dict[str, Any]] = field(default_factory=list)
    summons: List[Dict[str, Any]] = field(default_factory=list)
    reveal: Optional[Dict[str, Any]] = None
    mutated_types: Dict[int, str] = field(default_factory=dict)


def can_cast(hero: Hero, spell_id: str) -> Tuple[bool, str]:
    if spell_id not in SPELLS:
        return False, "unknown_spell"
    if spell_id not in hero.abilities:
        return False, "not_learned"
    spec = SPELLS[spell_id]
    if hero.is_on_cooldown(spell_id):
        return False, "on_cooldown"
    if hero.mana < spec.mana_cost:
        return False, "no_mana"
    return True, ""


def _distance_px(a: Unit, b: Unit) -> float:
    return math.hypot(a.pixel_x - b.pixel_x, a.pixel_y - b.pixel_y)


def _aoe_hits(center_x: float, center_y: float,
              radius: float, units: Dict[int, Unit],
              hostile_to: Optional[str] = None) -> List[Unit]:
    result: List[Unit] = []
    for u in units.values():
        if u.hp <= 0:
            continue
        if hostile_to is not None and u.faction == hostile_to:
            continue
        d = math.hypot(u.pixel_x - center_x, u.pixel_y - center_y)
        if d <= radius:
            result.append(u)
    return result


def cast_spell(hero: Hero, spell_id: str, *,
               target_unit: Optional[Unit] = None,
               target_building: Optional[Building] = None,
               center_px: Optional[Tuple[float, float]] = None,
               units: Optional[Dict[int, Unit]] = None,
               ) -> CastResult:
    ok, reason = can_cast(hero, spell_id)
    if not ok:
        return CastResult(success=False, spell_id=spell_id, reason=reason)

    spec = SPELLS[spell_id]
    units = units or {}

    if spec.target == "unit_enemy" and target_unit is None:
        return CastResult(False, spell_id, "no_target")
    if spec.target == "unit_ally" and target_unit is None:
        return CastResult(False, spell_id, "no_target")
    if spec.target == "point" and center_px is None:
        return CastResult(False, spell_id, "no_point")

    if target_unit is not None and spec.range_px > 0:
        if _distance_px(hero, target_unit) > spec.range_px:
            return CastResult(False, spell_id, "out_of_range")

    if not hero.spend_mana(spec.mana_cost):
        return CastResult(False, spell_id, "no_mana")
    hero.set_cooldown(spell_id, spec.cooldown_ticks)

    result = CastResult(success=True, spell_id=spell_id)

    # --- лечение ---
    if spec.heal > 0 and target_unit is not None:
        healed = min(spec.heal, target_unit.max_hp - target_unit.hp)
        if healed > 0:
            result.healed[target_unit.id] = healed
        return result

    # --- прямой урон по юниту ---
    if spec.target == "unit_enemy" and spec.damage > 0 and target_unit is not None:
        result.damaged[target_unit.id] = spec.damage
        return result

    # --- AOE по точке ---
    if spec.target == "point" and center_px is not None:
        if spec.aoe_radius_px > 0 and spec.damage > 0:
            cx, cy = center_px
            for u in _aoe_hits(cx, cy, spec.aoe_radius_px, units,
                               hostile_to=hero.faction):
                result.damaged[u.id] = spec.damage
        elif spec.id == "holy_vision":
            result.reveal = {"center": center_px, "radius_px": 500.0}
        elif spec.id in ("summon_spider", "summon_demon", "raise_dead"):
            kind = {"summon_spider": "spider",
                    "summon_demon": "demon",
                    "raise_dead": "skeleton"}[spec.id]
            result.summons.append({"kind": kind, "at": center_px,
                                   "faction": hero.faction})
        return result

    # --- self-AOE (whirlwind) ---
    if spec.target == "self" and spec.damage > 0:
        for u in _aoe_hits(hero.pixel_x, hero.pixel_y, spec.aoe_radius_px,
                           units, hostile_to=hero.faction):
            if u.id == hero.id:
                continue
            result.damaged[u.id] = spec.damage
        return result

    # --- бафф/дебафф ---
    if spec.speed_multiplier != 1.0 and target_unit is not None:
        result.buffs.append({
            "target_id": target_unit.id,
            "kind": spec.id,
            "speed_multiplier": spec.speed_multiplier,
            "duration_ticks": spec.duration_ticks,
        })
        return result

    if spec.id == "invisibility" and target_unit is not None:
        result.buffs.append({
            "target_id": target_unit.id,
            "kind": "invisibility",
            "invisible": True,
            "duration_ticks": spec.duration_ticks,
        })
        return result

    if spec.id == "polymorph" and target_unit is not None:
        result.mutated_types[target_unit.id] = "sheep"
        result.buffs.append({
            "target_id": target_unit.id,
            "kind": "polymorph",
            "duration_ticks": spec.duration_ticks,
        })
        return result

    if spec.id in ("flame_shield", "unholy_armor") and target_unit is not None:
        result.buffs.append({
            "target_id": target_unit.id,
            "kind": spec.id,
            "duration_ticks": spec.duration_ticks,
        })
        return result

    return CastResult(False, spell_id, "unsupported_effect")


def apply_cast_result(result: CastResult,
                      units: Dict[int, Unit]) -> None:
    for uid, heal in result.healed.items():
        u = units.get(uid)
        if u is not None:
            u.hp = min(u.max_hp, u.hp + heal)
    for uid, dmg in result.damaged.items():
        u = units.get(uid)
        if u is not None:
            u.hp = max(0, u.hp - dmg)
            if u.hp == 0:
                u.state = 5  # UnitState.DEAD
    for uid, new_type in result.mutated_types.items():
        u = units.get(uid)
        if u is not None:
            u.stats.setdefault("original_type", u.type)
            u.type = new_type