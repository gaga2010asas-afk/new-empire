import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.attack_command import AttackCommandManager
from backend.banner import Banner, BannerError, BannerManager
from backend.constants import (
    BANNER_DAMAGE_BUFF, BannerState,
    EVENT_BANNER_LOST, EVENT_BANNER_RAISED, UnitState,
)
from backend.entities import Unit
from backend.events import EventBus
from backend.tax_buffer import ColonyType, Vassal
from backend.vassal_ai import VassalAI


def _hero(uid=1, faction="human", x=0.0, y=0.0):
    u = Unit(id=uid, faction=faction, type="paladin",
             pixel_x=float(x), pixel_y=float(y), hp=200, max_hp=200,
             stats={"triad_role": "infantry", "damage": 20, "armor": 4})
    u.state = int(UnitState.IDLE)
    return u


def _soldier(uid, faction="human", x=0.0, y=0.0):
    u = Unit(id=uid, faction=faction, type="footman",
             pixel_x=float(x), pixel_y=float(y), hp=60, max_hp=60,
             stats={"triad_role": "infantry", "damage": 8, "armor": 3})
    u.state = int(UnitState.IDLE)
    return u


def _vassal_ai(vid, faction="human", army=10, colony=ColonyType.MID):
    v = Vassal(id=vid, faction=faction, colony_type=colony,
               hall_grid_x=0, hall_grid_y=0)
    return VassalAI(vassal=v, hall_id=f"hall_{vid}",
                    region_center=(5, 5), main_hall_grid=(50, 50),
                    army_ids=list(range(1000 + vid * 100,
                                        1000 + vid * 100 + army)))


# --- Базовая механика штандарта ---
def test_raise_banner_sets_gathering_and_emits_event():
    bus = EventBus(); events = []
    bus.subscribe(EVENT_BANNER_RAISED, lambda p: events.append(p))
    m = BannerManager(event_bus=bus)
    b = m.raise_banner(1, 42, (100.0, 100.0), {1: _hero(1)})
    assert b.state == int(BannerState.GATHERING)
    assert b.assigned_hero_id == 1
    assert events[0]["hero_id"] == 1


def test_cannot_raise_when_already_active():
    m = BannerManager()
    units = {1: _hero(1), 2: _hero(2)}
    m.raise_banner(1, 10, (0.0, 0.0), units)
    with pytest.raises(BannerError):
        m.raise_banner(2, 20, (0.0, 0.0), units)


def test_cannot_raise_with_dead_hero():
    m = BannerManager()
    hero = _hero(1); hero.hp = 0; hero.state = int(UnitState.DEAD)
    with pytest.raises(BannerError):
        m.raise_banner(1, 10, (0.0, 0.0), {1: hero})


def test_gathering_transitions_to_marching():
    m = BannerManager(gathering_ticks=60)
    units = {1: _hero(1)}
    m.raise_banner(1, 10, (0.0, 0.0), units)
    m.update(dt=1.0, units=units)
    assert m.get().state == int(BannerState.MARCHING)


# --- Аура ---
def test_damage_buff_inside_aura():
    m = BannerManager(aura_radius_px=200.0)
    hero = _hero(1, x=0.0, y=0.0)
    near = _soldier(2, x=50.0, y=0.0)
    far  = _soldier(3, x=1000.0, y=0.0)
    units = {1: hero, 2: near, 3: far}
    m.raise_banner(1, 10, (0.0, 0.0), units)
    assert m.damage_multiplier(near, units) == pytest.approx(
        1.0 + BANNER_DAMAGE_BUFF)
    assert m.damage_multiplier(far, units) == 1.0


def test_damage_buff_only_same_faction():
    m = BannerManager(aura_radius_px=200.0)
    hero = _hero(1, faction="human", x=0.0, y=0.0)
    enemy = _soldier(2, faction="orc", x=50.0, y=0.0)
    units = {1: hero, 2: enemy}
    m.raise_banner(1, 10, (0.0, 0.0), units)
    assert m.damage_multiplier(enemy, units) == 1.0


def test_damage_buff_off_when_hero_dead():
    m = BannerManager(aura_radius_px=200.0)
    hero = _hero(1, x=0.0, y=0.0)
    near = _soldier(2, x=50.0, y=0.0)
    units = {1: hero, 2: near}
    m.raise_banner(1, 10, (0.0, 0.0), units)
    hero.hp = 0
    assert m.damage_multiplier(near, units) == 1.0


def test_damage_buff_off_for_dead_receiver():
    m = BannerManager(aura_radius_px=200.0)
    hero = _hero(1, x=0.0, y=0.0)
    dead = _soldier(2, x=50.0, y=0.0)
    dead.hp = 0
    dead.state = int(UnitState.DEAD)
    units = {1: hero, 2: dead}
    m.raise_banner(1, 10, (0.0, 0.0), units)
    assert m.damage_multiplier(dead, units) == 1.0


# --- События banner_lost ---
def test_hero_death_dismisses_banner_and_emits_lost():
    bus = EventBus(); events = []
    bus.subscribe(EVENT_BANNER_LOST, lambda p: events.append(p))
    m = BannerManager(event_bus=bus)
    hero = _hero(1)
    units = {1: hero}
    m.raise_banner(1, 10, (0.0, 0.0), units)
    hero.hp = 0
    m.update(dt=1 / 60, units=units)
    assert m.is_active() is False
    assert events[0]["reason"] == "hero_died"


def test_dismiss_emits_lost_with_reason():
    bus = EventBus(); events = []
    bus.subscribe(EVENT_BANNER_LOST, lambda p: events.append(p))
    m = BannerManager(event_bus=bus)
    m.raise_banner(1, 10, (0.0, 0.0), {1: _hero(1)})
    m.dismiss()
    assert m.is_active() is False
    assert events[0]["reason"] == "dismissed"


# --- Мобилизованные юниты ---
def test_register_mobilized_units():
    m = BannerManager()
    m.raise_banner(1, 10, (0.0, 0.0), {1: _hero(1)})
    m.register_mobilized([101, 102, 103])
    m.register_mobilized([103, 104])
    assert m.mobilized_ids() == [101, 102, 103, 104]


def test_register_mobilized_requires_active_banner():
    m = BannerManager()
    with pytest.raises(BannerError):
        m.register_mobilized([1, 2])


# --- v1.5.16, п.18: обнуление мобилизации через шину ---
def test_dismiss_resets_affected_vassals_mobilization_via_event_bus():
    """
    Интеграционный сценарий:
    AttackCommandManager (subscribed to banner_lost) + BannerManager +
    VassalAI + EventBus.
      raise → vassal.mobilization > 0
      dismiss → banner_lost → handler → vassal.mobilization == 0
    """
    bus = EventBus()
    bm = BannerManager(event_bus=bus)
    ac = AttackCommandManager(bm, event_bus=bus)

    hero = _hero(1)
    vassal_ai = _vassal_ai(10, army=10, colony=ColonyType.MID)
    units = {1: hero}
    for uid in vassal_ai.army_ids:
        units[uid] = _soldier(uid, faction="human")
    vassals = {10: vassal_ai}

    ac.issue_attack(hero_id=1, target_region_id=20,
                    target_center_px=(0.0, 0.0),
                    units=units, vassals=vassals)
    assert vassal_ai.get_mobilization() > 0

    bm.dismiss()
    assert vassal_ai.get_mobilization() == 0.0
    assert vassal_ai.economy_multiplier() == 1.0


def test_hero_death_resets_mobilization_via_banner_manager():
    """
    v1.5.11 + v1.5.16, п.18: гибель Героя-Штандарта гарантированно
    возвращает вассалов в автономию.
    """
    bus = EventBus()
    bm = BannerManager(event_bus=bus)
    ac = AttackCommandManager(bm, event_bus=bus)

    hero = _hero(1)
    vassal_ai = _vassal_ai(10, army=10, colony=ColonyType.MID)
    units = {1: hero}
    for uid in vassal_ai.army_ids:
        units[uid] = _soldier(uid, faction="human")

    ac.issue_attack(1, 20, (0.0, 0.0), units, {10: vassal_ai})
    assert vassal_ai.get_mobilization() > 0

    hero.hp = 0
    hero.state = int(UnitState.DEAD)
    bm.update(dt=1 / 60, units=units)     # эмитит banner_lost

    assert bm.is_active() is False
    assert vassal_ai.get_mobilization() == 0.0