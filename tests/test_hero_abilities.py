import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.entities import Unit
from backend.hero import Hero
from backend.hero_abilities import (
    SPELLS, CastResult, HeroAbilityError, apply_cast_result, can_cast,
    cast_spell,
)


def _hero(slot="mage", faction="human", uid=1, x=0.0, y=0.0):
    h = Hero.from_role(uid, faction, slot, x, y)
    h.abilities = [
        "fireball", "slow", "flame_shield", "invisibility", "polymorph",
        "blizzard", "healing", "haste", "death_coil",
        "summon_spider", "poison_cloud", "summon_demon", "whirlwind",
    ]
    return h


def _enemy(uid, x, y, hp=100, faction="orc"):
    return Unit(id=uid, faction=faction, type="footman",
                pixel_x=float(x), pixel_y=float(y),
                hp=hp, max_hp=hp)


def test_fireball_costs_mana_and_damages():
    h = _hero("mage")
    target = _enemy(2, 100, 0)
    before_mana = h.mana
    res = cast_spell(h, "fireball", target_unit=target, units={2: target})
    assert res.success is True
    assert res.damaged.get(2) == SPELLS["fireball"].damage
    assert h.mana == before_mana - SPELLS["fireball"].mana_cost


def test_cannot_cast_without_learning():
    # Патч v1.5.17, п.4: правильный контракт — faction="human", slot="mage".
    h = Hero.from_role(1, "human", "mage", 0, 0)
    h.abilities = []
    target = _enemy(2, 50, 0)
    res = cast_spell(h, "fireball", target_unit=target, units={2: target})
    assert res.success is False
    assert res.reason == "not_learned"


def test_cannot_cast_without_mana():
    h = _hero("mage")
    h.mana = 0
    target = _enemy(2, 50, 0)
    res = cast_spell(h, "fireball", target_unit=target, units={2: target})
    assert res.success is False
    assert res.reason == "no_mana"


def test_out_of_range_rejected():
    h = _hero("mage")
    target = _enemy(2, 10_000, 0)
    res = cast_spell(h, "fireball", target_unit=target, units={2: target})
    assert res.success is False
    assert res.reason == "out_of_range"


def test_healing_adds_hp():
    h = _hero("paladin")
    ally = Unit(id=2, faction="human", type="footman",
                pixel_x=50.0, pixel_y=0.0, hp=20, max_hp=100)
    res = cast_spell(h, "healing", target_unit=ally, units={2: ally})
    assert res.success is True
    apply_cast_result(res, {2: ally})
    assert ally.hp == 70


def test_blizzard_hits_units_in_radius():
    h = _hero("mage")
    u1 = _enemy(2, 100, 0)
    u2 = _enemy(3, 130, 0)
    u3 = _enemy(4, 10_000, 0)
    res = cast_spell(h, "blizzard",
                     center_px=(100.0, 0.0),
                     units={2: u1, 3: u2, 4: u3})
    assert res.success is True
    assert 2 in res.damaged and 3 in res.damaged
    assert 4 not in res.damaged


def test_haste_returns_buff_spec():
    h = _hero("mage")
    ally = Unit(id=2, faction="human", type="footman",
                pixel_x=50.0, pixel_y=0.0, hp=100, max_hp=100)
    res = cast_spell(h, "haste", target_unit=ally, units={2: ally})
    assert res.success is True
    assert res.buffs[0]["speed_multiplier"] == 1.5


def test_slow_returns_debuff_spec():
    h = _hero("mage")
    target = _enemy(2, 50, 0)
    res = cast_spell(h, "slow", target_unit=target, units={2: target})
    assert res.success is True
    assert res.buffs[0]["speed_multiplier"] == 0.5


def test_polymorph_mutates_type():
    h = _hero("mage")
    target = _enemy(2, 50, 0)
    res = cast_spell(h, "polymorph", target_unit=target, units={2: target})
    assert res.success is True
    assert res.mutated_types.get(2) == "sheep"
    apply_cast_result(res, {2: target})
    assert target.type == "sheep"


def test_summon_returns_request():
    h = _hero("mage")
    h.abilities = ["summon_spider"]
    res = cast_spell(h, "summon_spider", center_px=(100.0, 100.0), units={})
    assert res.success is True
    assert res.summons[0]["kind"] == "spider"


def test_cooldown_blocks_repeat_cast():
    h = _hero("mage")
    target = _enemy(2, 50, 0)
    r1 = cast_spell(h, "fireball", target_unit=target, units={2: target})
    assert r1.success is True
    r2 = cast_spell(h, "fireball", target_unit=target, units={2: target})
    assert r2.success is False
    assert r2.reason == "on_cooldown"


def test_apply_cast_result_kills_unit_on_zero_hp():
    h = _hero("mage")
    target = _enemy(2, 50, 0, hp=10)
    res = cast_spell(h, "fireball", target_unit=target, units={2: target})
    apply_cast_result(res, {2: target})
    assert target.hp == 0
    assert target.state == 5


def test_whirlwind_hits_self_radius():
    h = _hero("mage")
    h.abilities = ["whirlwind"]
    h.pixel_x, h.pixel_y = 100.0, 100.0
    enemy = _enemy(2, 110, 100)
    res = cast_spell(h, "whirlwind", units={2: enemy})
    assert res.success is True
    assert 2 in res.damaged


def test_holy_vision_reveals():
    h = _hero("paladin")
    h.abilities = ["holy_vision"]
    res = cast_spell(h, "holy_vision", center_px=(100.0, 100.0), units={})
    assert res.success is True
    assert res.reveal is not None