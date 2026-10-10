import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.combat import (
    MAX_UPGRADE_LEVEL, UPGRADE_COSTS, UpgradeRegistry, apply_damage,
    calculate_damage, triad_multiplier,
)
from backend.constants import (
    EVENT_BUILDING_DESTROYED, TRIAD_COUNTER_MULTIPLIER,
    BuildingState, UnitState,
)
from backend.entities import Building, Unit
from backend.events import EventBus


def _unit(uid, faction, role, damage, hp, armor=0):
    u = Unit(id=uid, faction=faction, type="test",
             pixel_x=0.0, pixel_y=0.0, hp=hp, max_hp=hp,
             stats={"damage": damage, "armor": armor, "triad_role": role})
    u.state = int(UnitState.IDLE)
    return u


def _reg() -> UpgradeRegistry:
    r = UpgradeRegistry()
    r.register("human")
    r.register("orc")
    return r


# --- Триада ---
def test_triad_tank_vs_artillery_x2():
    atk = _unit(1, "human", "tank", 20, 100)
    dfn = _unit(2, "orc", "artillery", 10, 100, armor=0)
    assert triad_multiplier("tank", "artillery") == TRIAD_COUNTER_MULTIPLIER
    assert calculate_damage(atk, dfn) == 40


def test_triad_artillery_vs_infantry_x2():
    atk = _unit(1, "human", "artillery", 30, 100)
    dfn = _unit(2, "orc", "infantry", 10, 100, armor=5)
    assert calculate_damage(atk, dfn) == int(30 * 2 - 5)


def test_triad_infantry_vs_tank_x2():
    atk = _unit(1, "human", "infantry", 15, 100)
    dfn = _unit(2, "orc", "tank", 10, 100, armor=4)
    assert calculate_damage(atk, dfn) == int(15 * 2 - 4)


def test_vassal_triad_cavalry_vs_ranged_x2():
    atk = _unit(1, "human", "cavalry", 12, 100)
    dfn = _unit(2, "orc", "ranged", 10, 100, armor=2)
    assert calculate_damage(atk, dfn) == int(12 * 2 - 2)


def test_no_counter_is_x1():
    atk = _unit(1, "human", "tank", 20, 100)
    dfn = _unit(2, "orc", "infantry", 10, 100, armor=3)
    assert triad_multiplier("tank", "infantry") == 1.0
    assert calculate_damage(atk, dfn) == 20 - 3


def test_minimum_damage_is_1():
    atk = _unit(1, "human", "infantry", 2, 100)
    dfn = _unit(2, "orc", "tank", 10, 100, armor=100)
    assert calculate_damage(atk, dfn) == 1


# --- Апгрейды ---
def test_upgrade_damage_increases():
    reg = _reg()
    atk = _unit(1, "human", "infantry", 10, 100)
    dfn = _unit(2, "orc", "infantry", 10, 100, armor=2)
    d0 = calculate_damage(atk, dfn, reg)
    assert reg.upgrade_damage("human") is True
    d1 = calculate_damage(atk, dfn, reg)
    assert d1 == d0 + 1


def test_upgrade_armor_increases():
    reg = _reg()
    atk = _unit(1, "human", "infantry", 10, 100)
    dfn = _unit(2, "orc", "infantry", 10, 100, armor=2)
    d0 = calculate_damage(atk, dfn, reg)
    assert reg.upgrade_armor("orc") is True
    d1 = calculate_damage(atk, dfn, reg)
    assert d1 == max(1, d0 - 1)


def test_upgrade_costs_and_cap():
    reg = _reg()
    assert reg.cost_to_next_damage("human") == UPGRADE_COSTS[0]
    reg.upgrade_damage("human")
    assert reg.cost_to_next_damage("human") == UPGRADE_COSTS[1]
    reg.upgrade_damage("human")
    assert reg.cost_to_next_damage("human") == UPGRADE_COSTS[2]
    reg.upgrade_damage("human")
    assert reg.cost_to_next_damage("human") is None
    assert reg.upgrade_damage("human") is False


# --- v1.5.5, п.4: get бросает KeyError ---
def test_upgrade_get_raises_for_unknown_faction():
    reg = UpgradeRegistry()
    with pytest.raises(KeyError):
        reg.get("elves")


def test_calculate_damage_with_upgrades_needs_registration():
    reg = UpgradeRegistry()
    atk = _unit(1, "human", "infantry", 10, 100)
    dfn = _unit(2, "orc", "infantry", 10, 100)
    with pytest.raises(KeyError):
        calculate_damage(atk, dfn, reg)
    reg.register("human")
    reg.register("orc")
    assert calculate_damage(atk, dfn, reg) >= 1


# --- apply_damage ---
def test_apply_damage_kills_unit():
    u = _unit(1, "human", "infantry", 0, 10)
    assert apply_damage(u, 15) is True
    assert u.hp == 0
    assert u.state == int(UnitState.DEAD)


def test_apply_damage_destroys_building_and_emits_event():
    bus = EventBus()
    events = []
    bus.subscribe(EVENT_BUILDING_DESTROYED, lambda p: events.append(p))

    b = Building(id="farm_1", grid_x=4, grid_y=5, width=2, height=2,
                 hp=100, max_hp=100, faction="orc", type="farm")
    assert apply_damage(b, 100, event_bus=bus) is True
    assert b.hp == 0
    assert b.state == int(BuildingState.DESTROYED)
    assert len(events) == 1
    assert events[0]["id"] == "farm_1"
    assert events[0]["grid_x"] == 4
    assert events[0]["grid_y"] == 5
    assert events[0]["faction"] == "orc"


def test_apply_damage_without_event_bus_is_safe():
    b = Building(id="b1", grid_x=0, grid_y=0, width=1, height=1,
                 hp=10, max_hp=10, faction="human", type="farm")
    assert apply_damage(b, 20, event_bus=None) is True
    assert b.state == int(BuildingState.DESTROYED)


def test_apply_damage_partial_returns_false():
    u = _unit(1, "human", "infantry", 0, 50)
    assert apply_damage(u, 20) is False
    assert u.hp == 30