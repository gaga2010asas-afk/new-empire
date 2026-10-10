import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    EVENT_BUILDING_DESTROYED, BuildingState, UnitState,
)
from backend.entities import Building, Unit
from backend.events import EventBus
from backend.unit_ai import ATTACK_COOLDOWN_TICKS, CombatEngine, PROJECTILE_KINDS


def _unit(uid, faction, role, damage, hp, armor=0, x=0.0, y=0.0):
    u = Unit(id=uid, faction=faction, type="test",
             pixel_x=x, pixel_y=y, hp=hp, max_hp=hp,
             stats={"damage": damage, "armor": armor, "triad_role": role})
    u.state = int(UnitState.IDLE)
    return u


def _building(bid, faction, hp, gx=10, gy=10, w=2, h=2):
    return Building(id=bid, grid_x=gx, grid_y=gy, width=w, height=h,
                    hp=hp, max_hp=hp, faction=faction, type="farm")


def _engine(units, buildings, **kw):
    bus = kw.pop("event_bus", None)
    return CombatEngine(units, buildings, event_bus=bus, **kw)


def test_attack_spawns_projectile():
    attacker = _unit(1, "human", "infantry", 10, 100, x=0.0, y=0.0)
    target   = _unit(2, "orc",   "infantry", 10, 100, x=32.0, y=0.0)
    engine = _engine({1: attacker, 2: target}, {})
    engine.set_target(1, 2, False)
    assert attacker.state == int(UnitState.ATTACK)

    engine.update(1 / 60)
    assert engine.attack_count == 1
    assert len(engine.projectiles) == 1
    p = engine.projectiles[0]
    assert p.kind in PROJECTILE_KINDS
    assert p.damage >= 1
    # v1.5.5: target_x/y зафиксированы, vx/vy заданы
    assert p.target_x == 32.0
    assert p.target_y == 0.0
    assert p.vx > 0


def test_60_tick_cooldown():
    attacker = _unit(1, "human", "infantry", 5, 100, x=0.0, y=0.0)
    target   = _unit(2, "orc",   "infantry", 5, 100000, x=16.0, y=0.0)
    engine = _engine({1: attacker, 2: target}, {},
                     projectile_speed=10000.0)
    engine.set_target(1, 2, False)

    engine.update(1 / 60)                    # tick 0 → 1-я атака
    assert engine.attack_count == 1

    for _ in range(59):                      # ticks 1..59
        engine.update(1 / 60)
    assert engine.attack_count == 1

    engine.update(1 / 60)                    # tick 60 → 2-я атака
    assert engine.attack_count == 2


def test_projectile_damages_target_on_impact():
    attacker = _unit(1, "human", "infantry", 10, 100, x=0.0, y=0.0)
    target   = _unit(2, "orc",   "infantry", 10, 100, x=32.0, y=0.0)
    engine = _engine({1: attacker, 2: target}, {},
                     projectile_speed=10000.0)
    engine.set_target(1, 2, False)
    engine.update(1 / 60)
    assert target.hp == 90


def test_projectile_misses_when_target_moved():
    """v1.5.5, п.1: цель ушла — снаряд падает в землю."""
    attacker = _unit(1, "human", "infantry", 50, 100, x=0.0, y=0.0)
    target   = _unit(2, "orc",   "infantry", 10, 100, x=200.0, y=0.0)
    engine = _engine({1: attacker, 2: target}, {},
                     projectile_speed=200.0, hit_radius=5.0,
                     attack_range_px=500.0)
    engine.set_target(1, 2, False)
    engine.update(1 / 60)    # снаряд выпущен к (200, 0)

    # Сдвигаем цель далеко — на момент прилёта снаряда её там не будет
    target.pixel_x = 1000.0

    # Прогоняем 90 тиков — снаряд долетит до (200,0)
    for _ in range(90):
        engine.update(1 / 60)

    assert target.hp == 100     # промах — урона нет


def test_auto_target_nearest_enemy():
    attacker = _unit(1, "human", "infantry", 10, 100, x=0.0, y=0.0)
    near     = _unit(2, "orc",   "infantry", 10, 100, x=32.0, y=0.0)
    far      = _unit(3, "orc",   "infantry", 10, 100, x=128.0, y=0.0)
    engine = _engine({1: attacker, 2: near, 3: far}, {},
                     attack_range_px=200.0)
    attacker.state = int(UnitState.ATTACK)
    engine.update(1 / 60)
    assert engine.attack_count == 1
    assert engine.projectiles[0].target_id == 2


def test_no_attack_without_target_in_range():
    attacker = _unit(1, "human", "infantry", 10, 100, x=0.0, y=0.0)
    far      = _unit(2, "orc",   "infantry", 10, 100, x=1000.0, y=0.0)
    engine = _engine({1: attacker, 2: far}, {}, attack_range_px=100.0)
    attacker.state = int(UnitState.ATTACK)
    engine.update(1 / 60)
    assert engine.attack_count == 0


def test_target_death_and_switch_to_next():
    attacker = _unit(1, "human", "infantry", 100, 100, x=0.0, y=0.0)
    weak     = _unit(2, "orc",   "infantry", 10, 5, x=32.0, y=0.0)
    strong   = _unit(3, "orc",   "infantry", 10, 500, x=64.0, y=0.0)
    engine = _engine({1: attacker, 2: weak, 3: strong}, {},
                     projectile_speed=10000.0, attack_range_px=200.0)
    engine.set_target(1, 2, False)

    engine.update(1 / 60)   # weak убит
    assert weak.hp == 0
    assert weak.state == int(UnitState.DEAD)

    for _ in range(60):
        engine.update(1 / 60)
    assert engine.attack_count == 2


def test_building_destroyed_emits_event():
    bus = EventBus()
    events = []
    bus.subscribe(EVENT_BUILDING_DESTROYED, lambda p: events.append(p))

    attacker = _unit(1, "human", "artillery", 100, 100, x=200.0, y=100.0)
    b = _building("farm_5", "orc", hp=50, gx=1, gy=0)
    engine = CombatEngine({1: attacker}, {b.id: b}, event_bus=bus,
                          projectile_speed=10000.0, attack_range_px=500.0)
    engine.set_target(1, b.id, target_is_building=True)
    engine.update(1 / 60)

    assert b.hp == 0
    assert b.state == int(BuildingState.DESTROYED)
    assert len(events) == 1
    assert events[0]["id"] == "farm_5"