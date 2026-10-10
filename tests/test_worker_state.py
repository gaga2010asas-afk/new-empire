import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    MapLayer, MINE_TICKS_GOLD, MINE_TICKS_WOOD, TILE_SIZE, UnitState,
)
from backend.economy import Economy
from backend.entities import Building, Unit
from backend.map_data import MapData
from backend.worker_state import (
    WorkerController, is_worker, base_worker_type, _building_center_px,
)


# --- Сцены ------------------------------------------------------------------
def _flat_map(size: int = 12) -> MapData:
    m = MapData(width=size, height=size, seed=0)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def _scene_tree_on_block():
    m = _flat_map(12)
    econ = Economy(); econ.register_faction("human"); econ.activate("human")
    m.passability_matrix[3, 6] = int(MapLayer.BLOCK)
    tree = econ.make_tree(10, 6, 3)
    w = Unit(id=100, faction="human", type="peasant",
             pixel_x=0.0, pixel_y=0.0, hp=30, max_hp=30)
    hall = Building(id="hall_tree", grid_x=0, grid_y=0, width=2, height=2,
                    hp=1200, max_hp=1200, faction="human", type="town_hall")
    ctrl = WorkerController(econ, m, {100: w}, {500: hall},
                            has_lumber_mill=lambda f: False)
    return econ, m, ctrl, w, tree


def _scene_mine():
    m = _flat_map(12)
    econ = Economy(); econ.register_faction("human"); econ.activate("human")
    mine = econ.make_gold_mine(1, 3, 3, town_hall_level=1)
    w = Unit(id=100, faction="human", type="peasant",
             pixel_x=0.0, pixel_y=0.0, hp=30, max_hp=30)
    hall = Building(id="hall_mine", grid_x=0, grid_y=0, width=2, height=2,
                    hp=1200, max_hp=1200, faction="human", type="town_hall")
    ctrl = WorkerController(econ, m, {100: w}, {500: hall},
                            has_lumber_mill=lambda f: False)
    return econ, m, ctrl, w, mine


def _run(ctrl, wid, ticks, dt=1.0, speed=1_000_000.0):
    for _ in range(ticks):
        ctrl.update(wid, dt=dt, base_speed=speed)


# --- Базовое ----------------------------------------------------------------
def test_worker_type_detection():
    assert is_worker(Unit(id=1, faction="human", type="peasant",
                          pixel_x=0, pixel_y=0, hp=1, max_hp=1))
    assert is_worker(Unit(id=2, faction="human", type="peasant_with_gold",
                          pixel_x=0, pixel_y=0, hp=1, max_hp=1))
    assert not is_worker(Unit(id=3, faction="human", type="footman",
                              pixel_x=0, pixel_y=0, hp=1, max_hp=1))
    assert base_worker_type(Unit(id=4, faction="orc", type="peon_with_wood",
                                 pixel_x=0, pixel_y=0, hp=1, max_hp=1)) == "peon"


# --- v1.5.2, п.1: дистанционная рубка ---------------------------------------
def test_tree_on_block_worker_does_not_enter_block():
    econ, m, ctrl, w, tree = _scene_tree_on_block()
    ctrl.assign(100, node_id=tree.id, hall_id=500)
    _run(ctrl, 100, ticks=5)

    tx, ty = int(w.pixel_x // TILE_SIZE), int(w.pixel_y // TILE_SIZE)
    assert m.get_layer(tx, ty) == int(MapLayer.GROUND)
    assert w.state in (int(UnitState.MINE), int(UnitState.RETURN))


def test_full_wood_cycle_51_ticks_and_deposit():
    """v1.5.25: тикаем до первой сдачи — ровно 100 wood."""
    econ, m, ctrl, w, tree = _scene_tree_on_block()
    ctrl.assign(100, node_id=tree.id, hall_id=500)
    _run(ctrl, 100, ticks=3)

    # Дошли до MINING?
    guard = 0
    while w.state != int(UnitState.MINE) and guard < 20:
        ctrl.update(100, dt=1.0, base_speed=1_000_000.0)
        guard += 1
    assert w.state == int(UnitState.MINE), "рабочий не дошёл до фазы MINING"

    # Тикаем, пока не сменится тип. Считаем тики MINING.
    mining_ticks = 0
    for _ in range(MINE_TICKS_WOOD + 20):
        if w.type == "peasant_with_wood":
            break
        ctrl.update(100, dt=1.0, base_speed=1_000_000.0)
        mining_ticks += 1

    assert w.type == "peasant_with_wood", "тип не сменился на peasant_with_wood"
    assert mining_ticks + 1 == MINE_TICKS_WOOD, (
        f"fire на {mining_ticks + 1}-м MINING-тике, "
        f"ожидалось {MINE_TICKS_WOOD}"
    )

    # Тикаем ТОЛЬКО ДО ПЕРВОЙ СДАЧИ (wood станет 100).
    guard = 0
    while econ.get("human").wood < 100 and guard < 200:
        ctrl.update(100, dt=1.0, base_speed=1_000_000.0)
        guard += 1
    assert econ.get("human").wood == 100

def test_clear_block_when_tree_empty():
    econ, m, ctrl, w, tree = _scene_tree_on_block()
    tree.wood_remaining = 1
    ctrl.assign(100, node_id=tree.id, hall_id=500)
    _run(ctrl, 100, ticks=MINE_TICKS_WOOD + 10)
    assert m.get_layer(tree.grid_x, tree.grid_y) == int(MapLayer.GROUND)


# --- v1.5.2, п.4: шахта -----------------------------------------------------
def test_gold_cycle_hides_worker_45_ticks():
    econ, m, ctrl, w, mine = _scene_mine()
    ctrl.assign(100, node_id=mine.id, hall_id=500)
    _run(ctrl, 100, ticks=2)
    assert w.inside_mine is True
    for _ in range(MINE_TICKS_GOLD - 1):
        ctrl.update(100, dt=1.0, base_speed=1_000_000.0)
        assert w.inside_mine is True
    ctrl.update(100, dt=1.0, base_speed=1_000_000.0)
    assert w.inside_mine is False
    assert w.type == "peasant_with_gold"


def test_gold_full_cycle_deposits_100():
    econ, m, ctrl, w, mine = _scene_mine()
    ctrl.assign(100, node_id=mine.id, hall_id=500)
    _run(ctrl, 100, ticks=MINE_TICKS_GOLD + 10)
    assert econ.get("human").gold == 100
    assert w.type == "peasant"


def test_exhausted_mine_forces_idle():
    econ, m, ctrl, w, mine = _scene_mine()
    mine.trips_remaining = 0
    ctrl.assign(100, node_id=mine.id, hall_id=500)
    _run(ctrl, 100, ticks=10)
    assert ctrl.is_busy(100) is False
    assert w.state == int(UnitState.IDLE)


# --- v1.5.2, п.2: центр здания ----------------------------------------------
def test_building_center_is_geometric():
    b = Building(id="test_b", grid_x=10, grid_y=20, width=4, height=2,
                 hp=1, max_hp=1)
    cx, cy = _building_center_px(b)
    assert cx == (10 + 2) * TILE_SIZE
    assert cy == (20 + 1) * TILE_SIZE


# --- ретаргетинг ------------------------------------------------------------
def test_retarget_after_tree_exhausted():
    m = _flat_map(12)
    econ = Economy(); econ.register_faction("human"); econ.activate("human")
    t1 = econ.make_tree(10, 3, 3, total_wood=10)
    t2 = econ.make_tree(11, 6, 6)
    w = Unit(id=100, faction="human", type="peasant",
             pixel_x=0.0, pixel_y=0.0, hp=30, max_hp=30)
    hall = Building(id="hall_retarget", grid_x=0, grid_y=0,
                    width=2, height=2, hp=1200, max_hp=1200,
                    faction="human", type="town_hall")
    ctrl = WorkerController(econ, m, {100: w}, {500: hall},
                            has_lumber_mill=lambda f: False)
    ctrl.assign(100, node_id=t1.id, hall_id=500)
    _run(ctrl, 100, ticks=MINE_TICKS_WOOD + 5)
    assert t1.is_empty()
    assert ctrl.is_busy(100) is True