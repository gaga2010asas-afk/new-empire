import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.church import Church, ChurchError
from backend.constants import (
    CHURCH_REVIVE_COOLDOWN_TICKS, CHURCH_REVIVE_COST,
    CHURCH_TAX_HARD_BLOCK, TARGET_FPS,
)
from backend.hero import Hero
from backend.tax_buffer import ColonyType, Vassal


def _vassal(uid=1, faction="human", treasury=200.0):
    v = Vassal(id=uid, faction=faction, colony_type=ColonyType.MID,
               hall_grid_x=0, hall_grid_y=0)
    v.colony_treasury_gold = treasury
    return v


def _church(faction="human"):
    return Church(id="ch_1", faction=faction, grid_x=10, grid_y=10)


def test_initial_heroes_spawn():
    c = _church()
    heroes = c.spawn_initial_heroes(first_unit_id=100)
    assert len(heroes) == 5
    roles = [h.hero_role for h in heroes]
    assert "paladin" in roles and "mage" in roles and "griffin" in roles
    assert all(h.hero_level == 1 for h in heroes)


def test_orc_church_spawns_dk_and_warlock():
    c = _church(faction="orc")
    heroes = c.spawn_initial_heroes()
    roles = sorted(h.hero_role for h in heroes)
    assert "death_knight" in roles and "warlock" in roles


def test_no_revive_when_queue_empty():
    c = _church()
    v = _vassal()
    result = c.update(dt=1.0, vassals=[v], global_tax=0.30)
    assert result is None
    assert c.contribution_pool == 0


def test_contribution_blocked_at_90_percent_tax():
    c = _church()
    c.dead_heroes_queue.append({"slot": "paladin", "hero_level": 1,
                                "xp": 0, "abilities": []})
    v = _vassal(treasury=10_000.0)
    for _ in range(600):
        c.update(dt=1.0, vassals=[v], global_tax=CHURCH_TAX_HARD_BLOCK)
    assert c.contribution_pool == 0
    assert v.colony_treasury_gold == 10_000.0


def test_contribution_faster_at_10_percent_than_50():
    c1 = _church()
    c1.dead_heroes_queue.append({"slot": "paladin", "hero_level": 1,
                                 "xp": 0, "abilities": []})
    v1 = _vassal(treasury=10_000.0)
    for _ in range(60):
        c1.update(dt=1.0, vassals=[v1], global_tax=0.10)
    delta_10 = c1.contribution_pool

    c2 = _church()
    c2.dead_heroes_queue.append({"slot": "paladin", "hero_level": 1,
                                 "xp": 0, "abilities": []})
    v2 = _vassal(treasury=10_000.0)
    for _ in range(60):
        c2.update(dt=1.0, vassals=[v2], global_tax=0.50)
    delta_50 = c2.contribution_pool

    assert delta_10 > delta_50 > 0


def test_revive_after_pool_filled():
    c = _church()
    c.dead_heroes_queue.append({"slot": "paladin", "hero_level": 3,
                                "xp": 300, "abilities": ["healing"]})
    v = _vassal(treasury=100_000.0)
    revived = None
    for _ in range(600):
        revived = c.update(dt=1.0, vassals=[v], global_tax=0.10)
        if revived is not None:
            break
    assert revived is not None
    assert isinstance(revived, Hero)
    assert revived.hero_role == "paladin"
    assert revived.hero_level == 3
    assert "healing" in revived.abilities
    assert c.cooldown_ticks == CHURCH_REVIVE_COOLDOWN_TICKS


def test_cooldown_blocks_next_revive():
    c = _church()
    c.dead_heroes_queue.append({"slot": "paladin", "hero_level": 1,
                                "xp": 0, "abilities": []})
    c.dead_heroes_queue.append({"slot": "mage", "hero_level": 1,
                                "xp": 0, "abilities": []})
    v = _vassal(treasury=1_000_000.0)
    first = None
    for _ in range(2000):
        first = c.update(dt=1.0, vassals=[v], global_tax=0.10)
        if first is not None:
            break
    assert first is not None
    second_immediate = c.update(dt=1.0, vassals=[v], global_tax=0.10)
    assert second_immediate is None


def test_on_hero_died_enqueues():
    c = _church()
    h = Hero.from_role(1, "human", "mage", 0, 0)
    h.hero_level = 5
    h.xp = 500
    h.abilities = ["fireball", "slow"]
    c.on_hero_died(h)
    assert len(c.dead_heroes_queue) == 1
    spec = c.dead_heroes_queue[0]
    assert spec["slot"] == "mage"
    assert spec["hero_level"] == 5
    assert "fireball" in spec["abilities"]


def test_invalid_global_tax_raises():
    c = _church()
    with pytest.raises(ChurchError):
        c.update(dt=1.0, vassals=[], global_tax=1.5)


def test_invalid_dt_raises():
    c = _church()
    with pytest.raises(ChurchError):
        c.update(dt=0.0, vassals=[], global_tax=0.5)