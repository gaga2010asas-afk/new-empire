import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    MapLayer, ROAD_MAX_LEVEL, ROAD_SPEED_MULTIPLIER,
    TILE_SIZE, UnitState,
)
from backend.entities import Unit
from backend.map_data import MapData
from backend.pathfinding import PathFinder
from backend.worker_group import (
    GroupState, WorkerGroupController, DEFAULT_GROUP_SPEED,
)


def _flat(size: int = 12) -> MapData:
    m = MapData(width=size, height=size, seed=0)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def _make_units(n: int) -> dict:
    units = {}
    for i in range(1, n + 1):
        units[i] = Unit(id=i, faction="human", type="peasant",
                        pixel_x=0.0, pixel_y=0.0, hp=30, max_hp=30)
    return units


def _setup(n_workers: int = 3):
    m = _flat()
    units = _make_units(n_workers)
    pf = PathFinder(m)
    ctrl = WorkerGroupController(m, units, pf)
    return m, units, ctrl


def test_spawn_sets_carry_type_and_state():
    m, units, ctrl = _setup(3)
    g = ctrl.spawn(1, "human", [1, 2, 3], (1, 1), (9, 9),
                   carry_gold=200, carry_wood=100)
    assert g.state == GroupState.TO_TARGET.value
    for wid in (1, 2, 3):
        assert units[wid].type == "peasant_with_gold"
        assert units[wid].state == int(UnitState.RETURN)
    assert g.path[0] == (1, 1)
    assert g.path[-1] == (9, 9)


def test_group_marches_and_tramples_roads():
    m, units, ctrl = _setup(2)
    g = ctrl.spawn(1, "human", [1, 2], (0, 0), (6, 0),
                   carry_gold=100, carry_wood=100)
    for _ in range(200):
        ctrl.update(g, dt=1.0, base_speed=200.0)
        if g.state == GroupState.ARRIVED.value:
            break
    trampled = [m.get_road_level(x, 0) for x in range(1, 6)]
    assert any(lvl > 0 for lvl in trampled)


def test_group_arrives_at_target():
    m, units, ctrl = _setup(2)
    g = ctrl.spawn(1, "human", [1, 2], (0, 0), (4, 0),
                   carry_gold=100, carry_wood=100)
    for _ in range(500):
        ctrl.update(g, dt=1.0, base_speed=500.0)
        if g.state == GroupState.ARRIVED.value:
            break
    assert g.state == GroupState.ARRIVED.value
    for wid in (1, 2):
        assert units[wid].state == int(UnitState.IDLE)


def test_group_lost_when_all_dead():
    m, units, ctrl = _setup(2)
    g = ctrl.spawn(1, "human", [1, 2], (0, 0), (6, 0),
                   carry_gold=100, carry_wood=100)
    for wid in (1, 2):
        units[wid].state = int(UnitState.DEAD)
        units[wid].hp = 0
    ctrl.update(g, dt=1.0, base_speed=200.0)
    assert g.state == GroupState.LOST.value
    assert ctrl.is_lost(g) is True


def test_speed_multiplier_on_level_3_road():
    m, units, ctrl = _setup(2)
    for x in range(0, 8):
        m.trample_tile(x, 0); m.trample_tile(x, 0); m.trample_tile(x, 0)
    assert m.get_road_level(0, 0) == ROAD_MAX_LEVEL

    g = ctrl.spawn(1, "human", [1, 2], (0, 0), (7, 0),
                   carry_gold=100, carry_wood=100)
    leader = units[1]
    start_x = leader.pixel_x
    ctrl.update(g, dt=0.1, base_speed=100.0)
    dx = leader.pixel_x - start_x
    assert dx == pytest.approx(100.0 * 0.1 * ROAD_SPEED_MULTIPLIER)


def test_followers_offset_behind_leader():
    m, units, ctrl = _setup(3)
    g = ctrl.spawn(1, "human", [1, 2, 3], (0, 0), (6, 0),
                   carry_gold=100, carry_wood=100)
    ctrl.update(g, dt=1.0, base_speed=200.0)
    leader_x = units[1].pixel_x
    assert units[2].pixel_x < leader_x
    assert units[3].pixel_x < units[2].pixel_x


def test_use_default_group_speed_when_not_passed():
    """v1.5.3, п.5: DEFAULT_GROUP_SPEED — дефолт; в main.py заменяется
    на скорость рабочего из JSON."""
    assert DEFAULT_GROUP_SPEED == 100.0