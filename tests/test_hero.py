import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    HERO_MANA_REGEN_TICKS, HERO_MAX_LEVEL, TARGET_FPS,
    XP_BUILDING_KILL, XP_CARAVAN_KILL, XP_HERO_KILL,
    XP_THRESHOLDS, XP_UNIT_KILL,
)
from backend.hero import Hero, HeroError, default_max_mana, role_for


def _hero(slot="paladin", faction="human", uid=1):
    return Hero.from_role(uid, faction, slot, 0.0, 0.0)


def test_role_mapping_human_and_orc():
    assert role_for("human", "paladin") == "paladin"
    assert role_for("orc", "paladin")   == "death_knight"
    assert role_for("human", "mage")    == "mage"
    assert role_for("orc", "mage")      == "warlock"
    with pytest.raises(HeroError):
        role_for("elves", "paladin")
    with pytest.raises(HeroError):
        role_for("human", "unknown_slot")


def test_caster_mana_defaults():
    assert default_max_mana("paladin") == 200
    assert default_max_mana("death_knight") == 200
    assert default_max_mana("mage")    == 250
    assert default_max_mana("warlock") == 250
    assert default_max_mana("captain") == 0
    h = _hero("mage")
    assert h.max_mana == 250
    assert h.mana == 250


def test_xp_and_level_up():
    h = _hero("paladin")
    assert h.hero_level == 1
    h.add_xp(XP_THRESHOLDS[2])
    assert h.hero_level == 2
    h.add_xp(XP_THRESHOLDS[3] - h.xp)
    assert h.hero_level == 3


def test_ability_learned_at_level_3():
    h = _hero("paladin")
    assert h.abilities == []
    h.add_xp(XP_THRESHOLDS[3])
    assert h.hero_level == 3
    assert "healing" in h.abilities


def test_ability_schedule_v158_paladin():
    """Патч v1.5.8: Paladin 3→healing, 5→holy_vision, 7→exorcism."""
    h = _hero("paladin")
    h.add_xp(XP_THRESHOLDS[3])
    assert "healing" in h.abilities
    h.add_xp(XP_THRESHOLDS[5] - h.xp)
    assert "holy_vision" in h.abilities
    h.add_xp(XP_THRESHOLDS[7] - h.xp)
    assert "exorcism" in h.abilities
    # 9-й уровень ничего не добавляет по канону [НЕТ ДАННЫХ]
    before = set(h.abilities)
    h.add_xp(XP_THRESHOLDS[9] - h.xp)
    assert set(h.abilities) == before


def test_ability_schedule_v158_mage():
    """Mage 3→fireball, 5→slow, 7→flame_shield, 9→blizzard."""
    h = _hero("mage")
    h.add_xp(XP_THRESHOLDS[3]); assert "fireball" in h.abilities
    h.add_xp(XP_THRESHOLDS[5] - h.xp); assert "slow" in h.abilities
    h.add_xp(XP_THRESHOLDS[7] - h.xp); assert "flame_shield" in h.abilities
    h.add_xp(XP_THRESHOLDS[9] - h.xp); assert "blizzard" in h.abilities
    # invisibility и polymorph не выдаются автоматически
    assert "invisibility" not in h.abilities
    assert "polymorph" not in h.abilities


def test_ability_schedule_v158_death_knight():
    """DK 3→death_coil, 5→haste, 7→raise_dead, 9→death_and_decay."""
    h = _hero("paladin", faction="orc")  # = death_knight
    assert h.hero_role == "death_knight"
    h.add_xp(XP_THRESHOLDS[3]); assert "death_coil" in h.abilities
    h.add_xp(XP_THRESHOLDS[5] - h.xp); assert "haste" in h.abilities
    h.add_xp(XP_THRESHOLDS[7] - h.xp); assert "raise_dead" in h.abilities
    h.add_xp(XP_THRESHOLDS[9] - h.xp); assert "death_and_decay" in h.abilities
    assert "whirlwind" not in h.abilities
    assert "unholy_armor" not in h.abilities


def test_ability_schedule_v158_warlock():
    """Warlock 3→fireball, 5→summon_spider, 7→poison_cloud, 9→summon_demon."""
    h = _hero("mage", faction="orc")   # = warlock
    assert h.hero_role == "warlock"
    h.add_xp(XP_THRESHOLDS[3]); assert "fireball" in h.abilities
    h.add_xp(XP_THRESHOLDS[5] - h.xp); assert "summon_spider" in h.abilities
    h.add_xp(XP_THRESHOLDS[7] - h.xp); assert "poison_cloud" in h.abilities
    h.add_xp(XP_THRESHOLDS[9] - h.xp); assert "summon_demon" in h.abilities


def test_xp_capped_at_level_10():
    h = _hero("mage")
    h.add_xp(10_000)
    assert h.hero_level == HERO_MAX_LEVEL
    assert h.xp_to_next_level() is None
    h.add_xp(5000)
    assert h.hero_level == HERO_MAX_LEVEL


def test_kill_xp_values():
    h = _hero("paladin")
    before = h.xp
    h.on_unit_killed();     assert h.xp - before == XP_UNIT_KILL
    before = h.xp
    h.on_hero_killed();     assert h.xp - before == XP_HERO_KILL
    before = h.xp
    h.on_building_destroyed(); assert h.xp - before == XP_BUILDING_KILL
    before = h.xp
    h.on_caravan_killed();  assert h.xp - before == XP_CARAVAN_KILL


def test_spend_mana_rejects_insufficient():
    h = _hero("mage")
    assert h.spend_mana(50) is True
    assert h.mana == 200
    assert h.spend_mana(10_000) is False


def test_regen_mana_ticks_based():
    """Патч v1.5.8: 1 мана / 12 тиков. 1 сек = 60 тиков → 5 маны."""
    h = _hero("mage")
    h.mana = 0
    h.regen_mana(1.0)             # 60 тиков → 5 маны
    assert h.mana == 5
    h.regen_mana(1.0)
    assert h.mana == 10


def test_regen_mana_partial_tick():
    """Меньше 12 тиков — маны нет."""
    h = _hero("mage")
    h.mana = 0
    ticks_half = (HERO_MANA_REGEN_TICKS - 1) / TARGET_FPS
    h.regen_mana(ticks_half)
    assert h.mana == 0


def test_regen_mana_caps_at_max():
    h = _hero("mage")
    h.mana = 0
    h.regen_mana(1000.0)
    assert h.mana == h.max_mana


def test_cooldowns_tick_down():
    h = _hero("mage")
    h.set_cooldown("fireball", 3)
    assert h.is_on_cooldown("fireball") is True
    h.tick_cooldowns(); assert h.is_on_cooldown("fireball") is True
    h.tick_cooldowns(); assert h.is_on_cooldown("fireball") is True
    h.tick_cooldowns(); assert h.is_on_cooldown("fireball") is False


def test_hero_invalid_level_raises():
    with pytest.raises(HeroError):
        Hero(id=1, faction="human", type="paladin",
             pixel_x=0, pixel_y=0, hp=10, max_hp=10,
             hero_level=0, hero_role="paladin")
    with pytest.raises(HeroError):
        Hero(id=1, faction="human", type="paladin",
             pixel_x=0, pixel_y=0, hp=10, max_hp=10,
             hero_level=11, hero_role="paladin")


def test_hero_mana_over_max_raises():
    with pytest.raises(HeroError):
        Hero(id=1, faction="human", type="mage",
             pixel_x=0, pixel_y=0, hp=10, max_hp=10,
             mana=300, max_mana=200, hero_role="mage")


def test_aura_color_by_role():
    assert _hero("mage").aura_color == (160, 60, 220, 128)
    assert _hero("mage", faction="orc").aura_color == (60, 120, 240, 128)