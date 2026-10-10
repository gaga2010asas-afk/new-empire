import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    TILE_SIZE, ROAD_SPEED_MULTIPLIER, ROAD_MAX_LEVEL, MapLayer, UnitState,
)
from backend.entities import Unit
from backend.map_data import MapData
from backend.movement import update_unit_movement, _direction_from_delta


def _all_ground(size=8) -> MapData:
    m = MapData(width=size, height=size, seed=0)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def test_direction_from_delta_cardinal():
    assert _direction_from_delta(1, 0) == 0    # восток
    assert _direction_from_delta(0, 1) == 2    # юг
    assert _direction_from_delta(-1, 0) == 4   # запад
    assert _direction_from_delta(0, -1) == 6   # север


def test_update_movement_reaches_target():
    m = _all_ground()
    u = Unit(id=1, faction="human", type="footman",
             pixel_x=0.0, pixel_y=0.0, hp=10, max_hp=10)
    reached = update_unit_movement(u, 64.0, 0.0, m, dt=1.0, base_speed=100.0)
    assert reached is True
    assert u.pixel_x == pytest.approx(64.0)
    assert u.state == int(UnitState.IDLE)


def test_movement_blocked_by_block_layer():
    m = _all_ground()
    m.passability_matrix[0, 1] = int(MapLayer.BLOCK)
    u = Unit(id=1, faction="human", type="footman",
             pixel_x=10.0, pixel_y=10.0, hp=10, max_hp=10)
    reached = update_unit_movement(
        u, TILE_SIZE + 10.0, 10.0, m, dt=1.0, base_speed=1000.0,
    )
    assert reached is False
    assert u.pixel_x < TILE_SIZE


def test_road_multiplier_doubles_step():
    m = _all_ground()
    for _ in range(ROAD_MAX_LEVEL):
        m.step_on_tile(0, 0)
    assert m.get_road_level(0, 0) == ROAD_MAX_LEVEL

    u = Unit(id=1, faction="human", type="footman",
             pixel_x=0.0, pixel_y=0.0, hp=10, max_hp=10)
    update_unit_movement(u, 1000.0, 0.0, m, dt=0.1, base_speed=100.0)
    # Без дороги: 10.0. С дорогой: 10.0 * 2.0 = 20.0.
    assert u.pixel_x == pytest.approx(100.0 * 0.1 * ROAD_SPEED_MULTIPLIER)


def test_step_on_new_tile_tramples_road():
    m = _all_ground()
    u = Unit(id=1, faction="human", type="footman",
             pixel_x=10.0, pixel_y=10.0, hp=10, max_hp=10)
    update_unit_movement(u, TILE_SIZE + 5.0, 10.0, m, dt=1.0, base_speed=1000.0)
    # Юнит перешёл в тайл (1, 0) — должен натоптать 1
    assert m.get_road_level(1, 0) == 1