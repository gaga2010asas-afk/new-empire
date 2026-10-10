import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from backend.constants import MapLayer, TILE_SIZE, UnitState
from backend.economy import Economy
from backend.entities import Building, Unit
from backend.map_data import MapData
from backend.worker_state import WorkerController


def _flat(size: int = 16) -> MapData:
    m = MapData(width=size, height=size, seed=1)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def test_two_workers_two_mines_gather_in_parallel():
    m = _flat()
    econ = Economy(); econ.register_faction("human"); econ.activate("human")
    m1 = econ.make_gold_mine(1, 2, 2)
    m2 = econ.make_gold_mine(2, 10, 10)
    units = {
        1: Unit(id=1, faction="human", type="peasant",
                pixel_x=2 * TILE_SIZE, pixel_y=2 * TILE_SIZE,
                hp=30, max_hp=30),
        2: Unit(id=2, faction="human", type="peasant",
                pixel_x=10 * TILE_SIZE, pixel_y=10 * TILE_SIZE,
                hp=30, max_hp=30),
    }
    hall = Building(id="hall_two", grid_x=5, grid_y=5, width=2, height=2,
                    hp=1200, max_hp=1200, faction="human", type="town_hall")
    ctrl = WorkerController(econ, m, units, {99: hall},
                            has_lumber_mill=lambda f: False)
    ctrl.assign(1, m1.id, 99)
    ctrl.assign(2, m2.id, 99)

    for _ in range(120):
        ctrl.update(1, dt=1.0, base_speed=1_000_000.0)
        ctrl.update(2, dt=1.0, base_speed=1_000_000.0)

    assert econ.get("human").gold >= 200


def test_worker_ore_swap_reflects_cargo_kind():
    m = _flat()
    econ = Economy(); econ.register_faction("orc"); econ.activate("orc")
    econ.make_tree(5, 3, 3)
    w = Unit(id=1, faction="orc", type="peon",
             pixel_x=0.0, pixel_y=0.0, hp=30, max_hp=30)
    hall = Building(id="hall_orc", grid_x=0, grid_y=0, width=2, height=2,
                    hp=1200, max_hp=1200, faction="orc", type="great_hall")
    ctrl = WorkerController(econ, m, {1: w}, {10: hall},
                            has_lumber_mill=lambda f: True)
    ctrl.assign(1, 5, 10)
    for _ in range(120):
        ctrl.update(1, dt=1.0, base_speed=1_000_000.0)
        if w.type == "peon_with_wood":
            break
    assert w.type == "peon_with_wood"


def test_dead_worker_update_clears_task():
    m = _flat(8)
    econ = Economy(); econ.register_faction("human"); econ.activate("human")
    econ.make_gold_mine(1, 3, 3)
    w = Unit(id=1, faction="human", type="peasant",
             pixel_x=0.0, pixel_y=0.0, hp=1, max_hp=1)
    hall = Building(id="hall_dead", grid_x=0, grid_y=0, width=2, height=2,
                    hp=1200, max_hp=1200, faction="human", type="town_hall")
    ctrl = WorkerController(econ, m, {1: w}, {10: hall},
                            has_lumber_mill=lambda f: False)
    ctrl.assign(1, 1, 10)
    w.state = int(UnitState.DEAD)
    ctrl.update(1, dt=1.0, base_speed=1_000_000.0)
    assert ctrl.is_busy(1) is False