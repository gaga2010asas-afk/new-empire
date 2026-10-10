import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from backend.banner import BannerManager
from backend.church import Church
from backend.combat import UpgradeRegistry
from backend.constants import MapLayer
from backend.economy import Economy
from backend.entities import Building, Unit
from backend.hero import Hero
from backend.map_data import MapData
from backend.save_load import (
    GameStateSnapshot, SaveLoadError, SaveLoadManager,
)
from backend.tax_buffer import ColonyType, Vassal
from backend.vassal_ai import VassalAI


def _flat(size: int = 16, seed: int = 7) -> MapData:
    m = MapData(width=size, height=size, seed=seed)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def _snapshot() -> GameStateSnapshot:
    m = _flat()
    econ = Economy()
    econ.register_faction("human", gold=500, wood=200)
    econ.activate("human")

    hero = Hero.from_role(1, "human", "mage", 64.0, 64.0)
    hero.mana = 100
    hero.add_xp(200)

    soldier = Unit(id=2, faction="human", type="footman",
                   pixel_x=32.0, pixel_y=32.0, hp=60, max_hp=60,
                   stats={"damage": 8, "armor": 3,
                          "triad_role": "infantry"})

    hall = Building(id="hall_1", grid_x=2, grid_y=2, width=2, height=2,
                    hp=1200, max_hp=1200, faction="human",
                    type="town_hall")

    reg = UpgradeRegistry()
    reg.register("human"); reg.register("orc")
    reg.upgrade_damage("human")

    vassal = Vassal(id=10, faction="human", colony_type=ColonyType.MID,
                    hall_grid_x=5, hall_grid_y=5)
    vassal.tax_buffer_gold = 120.5
    ai = VassalAI(vassal=vassal, hall_id="hall_1",
                  region_center=(5, 5), main_hall_grid=(2, 2),
                  map_data=m, army_ids=[2])

    church = Church(id="ch_1", faction="human", grid_x=4, grid_y=4)
    banner_manager = BannerManager()

    return GameStateSnapshot(
        map_data=m, economy=econ,
        units={1: hero, 2: soldier},
        buildings={"hall_1": hall},
        upgrades=reg,
        vassals={10: ai},
        church=church,
        banner_manager=banner_manager,
        global_tick=12345,
    )


def test_numpy_matrix_round_trip(tmp_path):
    m = _flat(24, seed=99)
    m.passability_matrix[3, 3] = int(MapLayer.BLOCK)
    m.passability_matrix[4, 4] = int(MapLayer.WATER)
    m.trample_tile(5, 5); m.trample_tile(5, 5)

    mgr = SaveLoadManager(saves_dir=tmp_path)
    s = GameStateSnapshot(
        map_data=m, economy=Economy(),
        units={}, buildings={}, upgrades=UpgradeRegistry(),
    )
    mgr.save(s, "map_roundtrip")
    loaded = mgr.load("map_roundtrip")

    assert np.array_equal(loaded.map_data.passability_matrix,
                          m.passability_matrix)
    assert np.array_equal(loaded.map_data.roads_matrix,
                          m.roads_matrix)
    assert loaded.map_data.passability_matrix.dtype == \
           m.passability_matrix.dtype


def test_full_snapshot_round_trip(tmp_path):
    snap = _snapshot()
    mgr = SaveLoadManager(saves_dir=tmp_path)
    mgr.save(snap, "full")
    loaded = mgr.load("full")

    assert loaded.global_tick == 12345
    assert len(loaded.units) == 2
    assert isinstance(loaded.units[1], Hero)
    assert loaded.units[1].mana == 100
    assert loaded.units[1].hero_level == 2
    assert loaded.units[1].abilities == []
    assert loaded.units[2].stats["triad_role"] == "infantry"
    assert loaded.buildings["hall_1"].hp == 1200
    assert loaded.economy.get("human").gold == 500
    assert loaded.upgrades.get("human").damage_level == 1
    assert loaded.vassals[10].vassal.tax_buffer_gold == pytest.approx(120.5)
    assert loaded.church.id == "ch_1"


def test_hero_cooldowns_and_mana_accum_survive_round_trip(tmp_path):
    snap = _snapshot()
    hero = snap.units[1]
    hero.set_cooldown("fireball", 5)
    hero._mana_tick_accum = 7

    mgr = SaveLoadManager(saves_dir=tmp_path)
    mgr.save(snap, "hero_state")
    loaded = mgr.load("hero_state")
    lh = loaded.units[1]

    assert lh.is_on_cooldown("fireball") is True
    assert lh._cooldowns.get("fireball") == 5
    assert lh._mana_tick_accum == 7


def test_projectiles_survive_round_trip(tmp_path):
    """Патч v1.5.24: медленный снаряд — живёт несколько тиков, не удаляется сразу."""
    from backend.unit_ai import CombatEngine
    snap = _snapshot()
    ce = CombatEngine(units=snap.units, buildings=snap.buildings,
                      projectile_speed=10.0)
    hero = snap.units[1]
    hero.state = 3  # ATTACK
    soldier = snap.units[2]
    ce.set_target(hero.id, soldier.id, False)
    ce.update(1 / 60)
    assert len(ce.projectiles) == 1
    snap.combat_engine = ce

    mgr = SaveLoadManager(saves_dir=tmp_path)
    mgr.save(snap, "proj")
    loaded = mgr.load("proj")

    assert loaded.combat_engine is not None
    assert len(loaded.combat_engine.projectiles) == 1
    p = loaded.combat_engine.projectiles[0]
    assert p.kind in ("arrow", "axe", "ballista_bolt", "cannon_ball")
    assert p.damage >= 1


def test_missing_file_raises(tmp_path):
    mgr = SaveLoadManager(saves_dir=tmp_path)
    with pytest.raises(SaveLoadError):
        mgr.load("nope")


def test_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    mgr = SaveLoadManager(saves_dir=tmp_path)
    with pytest.raises(SaveLoadError):
        mgr.load("bad")


def test_wrong_format_version_raises(tmp_path):
    mgr = SaveLoadManager(saves_dir=tmp_path)
    snap = _snapshot()
    payload = mgr.to_dict(snap)
    payload["format_version"] = 999
    with pytest.raises(SaveLoadError):
        mgr.from_dict(payload)


def test_list_saves(tmp_path):
    mgr = SaveLoadManager(saves_dir=tmp_path)
    snap = _snapshot()
    mgr.save(snap, "alpha")
    mgr.save(snap, "beta")
    assert mgr.list_saves() == ["alpha", "beta"]


def test_invalid_save_name_rejected(tmp_path):
    mgr = SaveLoadManager(saves_dir=tmp_path)
    with pytest.raises(SaveLoadError):
        mgr.save(_snapshot(), "../escape")