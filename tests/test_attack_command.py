import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.attack_command import (
    AttackCommandError, AttackCommandManager, AttackOrder,
)
from backend.banner import BannerManager
from backend.constants import (
    EVENT_ATTACK_STARTED, EVENT_BANNER_LOST, EVENT_VASSAL_MOBILIZED,
    BannerState, UnitState,
)
from backend.entities import Unit
from backend.events import EventBus
from backend.tax_buffer import ColonyType, Vassal
from backend.vassal_ai import VassalAI


def _hero(uid=1, faction="human"):
    u = Unit(id=uid, faction=faction, type="paladin",
             pixel_x=0.0, pixel_y=0.0, hp=200, max_hp=200,
             stats={"triad_role": "infantry", "damage": 20, "armor": 4})
    u.state = int(UnitState.IDLE)
    return u


def _soldier(uid, faction="human"):
    u = Unit(id=uid, faction=faction, type="footman",
             pixel_x=0.0, pixel_y=0.0, hp=60, max_hp=60,
             stats={"triad_role": "infantry", "damage": 8, "armor": 3})
    u.state = int(UnitState.IDLE)
    return u


def _vassal_ai(vid, faction="human", army=10,
               colony=ColonyType.MID):
    v = Vassal(id=vid, faction=faction, colony_type=colony,
               hall_grid_x=0, hall_grid_y=0)
    ai = VassalAI(vassal=v, hall_id=f"hall_{vid}",
                  region_center=(5, 5), main_hall_grid=(50, 50),
                  army_ids=list(range(1000 + vid * 100,
                                      1000 + vid * 100 + army)),
                  worker_ids=[2000 + vid])
    return ai


def _units_covering(vassals):
    units = {}
    for v in vassals.values():
        for uid in v.army_ids:
            units[uid] = _soldier(uid, faction=v.vassal.faction)
    return units


def test_issue_attack_raises_banner_and_emits_events():
    bus = EventBus()
    started, mobilized = [], []
    bus.subscribe(EVENT_ATTACK_STARTED, lambda p: started.append(p))
    bus.subscribe(EVENT_VASSAL_MOBILIZED, lambda p: mobilized.append(p))

    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)
    units = {1: _hero(1)}
    v10 = _vassal_ai(10)
    v11 = _vassal_ai(11)
    vassals = {10: v10, 11: v11}
    units.update(_units_covering(vassals))

    order = ac.issue_attack(1, 77, (200.0, 200.0), units, vassals)
    assert isinstance(order, AttackOrder)
    assert sorted(order.affected_vassals) == [10, 11]
    assert order.total_mobilized_units > 0
    assert len(started) == 1
    assert len(mobilized) == 2
    assert m.is_active() is True


def test_issue_attack_fails_without_church():
    m = BannerManager()
    ac = AttackCommandManager(m)
    with pytest.raises(AttackCommandError):
        ac.issue_attack(1, 10, (0.0, 0.0), {1: _hero(1)}, {},
                        church_built=False)


def test_issue_attack_fails_when_banner_active():
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)
    units = {1: _hero(1)}
    ac.issue_attack(1, 10, (0.0, 0.0), units, {})
    with pytest.raises(AttackCommandError):
        ac.issue_attack(1, 20, (0.0, 0.0), units, {})


# --- матрица мобилизации (патч v1.5.11, п.4) ---
def test_default_uses_matrix_mid_free_50():
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)
    units = {1: _hero(1)}
    v_mid = _vassal_ai(10, army=10, colony=ColonyType.MID)
    vassals = {10: v_mid}
    units.update(_units_covering(vassals))

    ac.issue_attack(1, 20, (0.0, 0.0), units, vassals)
    assert v_mid.get_mobilization() == 0.50
    assert len(v_mid.mobilized_unit_ids(units)) == 5


def test_default_uses_matrix_central_free_30():
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)
    units = {1: _hero(1)}
    v = _vassal_ai(10, army=10, colony=ColonyType.CENTRAL)
    vassals = {10: v}
    units.update(_units_covering(vassals))
    ac.issue_attack(1, 20, (0.0, 0.0), units, vassals)
    assert v.get_mobilization() == 0.30


def test_default_uses_matrix_border_free_30():
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)
    units = {1: _hero(1)}
    v = _vassal_ai(10, army=10, colony=ColonyType.BORDER)
    vassals = {10: v}
    units.update(_units_covering(vassals))
    ac.issue_attack(1, 20, (0.0, 0.0), units, vassals)
    assert v.get_mobilization() == 0.30


def test_override_fraction_still_works_for_tests():
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus, override_fraction=0.90)
    units = {1: _hero(1)}
    v = _vassal_ai(10, army=10, colony=ColonyType.MID)
    vassals = {10: v}
    units.update(_units_covering(vassals))
    ac.issue_attack(1, 20, (0.0, 0.0), units, vassals)
    assert v.get_mobilization() == 0.90
    assert v.economy_multiplier() == 0.0


def test_invalid_override_fraction_raises():
    m = BannerManager()
    with pytest.raises(AttackCommandError):
        AttackCommandManager(m, override_fraction=1.5)


# --- критический баг (патч v1.5.11, п.1): сброс мобилизации ---
def test_dismiss_resets_affected_vassals_mobilization():
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)
    units = {1: _hero(1)}
    v = _vassal_ai(10, army=10, colony=ColonyType.MID)
    vassals = {10: v}
    units.update(_units_covering(vassals))

    ac.issue_attack(1, 20, (0.0, 0.0), units, vassals)
    assert v.get_mobilization() == 0.50

    m.dismiss()                         # banner_lost → сброс мобилизации
    assert v.get_mobilization() == 0.0
    assert v.economy_multiplier() == 1.0
    assert ac.affected_vassal_ids() == []


def test_hero_death_resets_affected_vassals_mobilization():
    """Обязательный сценарий патча v1.5.11, п.1."""
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)

    hero = _hero(1)
    units = {1: hero}
    v = _vassal_ai(10, army=10, colony=ColonyType.MID)
    vassals = {10: v}
    units.update(_units_covering(vassals))

    ac.issue_attack(1, 20, (0.0, 0.0), units, vassals)
    assert v.get_mobilization() == 0.50

    hero.hp = 0
    hero.state = int(UnitState.DEAD)
    m.update(dt=1 / 60, units=units)   # эмитит banner_lost

    assert m.is_active() is False
    assert v.get_mobilization() == 0.0
    assert v.economy_multiplier() == 1.0


def test_foreign_faction_vassals_ignored():
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)
    units = {1: _hero(1, faction="human")}
    v_human = _vassal_ai(10, faction="human")
    v_orc = _vassal_ai(11, faction="orc")
    vassals = {10: v_human, 11: v_orc}
    units.update(_units_covering(vassals))

    order = ac.issue_attack(1, 20, (0.0, 0.0), units, vassals)
    assert 10 in order.affected_vassals
    assert 11 not in order.affected_vassals
    assert v_orc.get_mobilization() == 0.0


def test_cancel_attack_dismisses_and_zeros_mobilization():
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)
    units = {1: _hero(1)}
    v = _vassal_ai(10)
    vassals = {10: v}
    units.update(_units_covering(vassals))

    ac.issue_attack(1, 20, (0.0, 0.0), units, vassals)
    assert v.get_mobilization() > 0

    ac.cancel_attack()                 # dismiss → banner_lost → сброс
    assert m.is_active() is False
    assert v.get_mobilization() == 0.0


def test_dead_units_excluded_from_mobilization():
    """Проверка динамического фильтра через issue_attack."""
    bus = EventBus()
    m = BannerManager(event_bus=bus)
    ac = AttackCommandManager(m, event_bus=bus)

    v = _vassal_ai(10, army=10, colony=ColonyType.MID)
    units = {1: _hero(1)}
    units.update(_units_covering({10: v}))
    # Убьём 4 юнита — армия из 6 живых
    for uid in list(v.army_ids)[:4]:
        units[uid].hp = 0
        units[uid].state = int(UnitState.DEAD)

    ac.issue_attack(1, 20, (0.0, 0.0), units, {10: v})
    # 50% от 6 = 3
    assert len(v.mobilized_unit_ids(units)) == 3