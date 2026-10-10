import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from backend.constants import (
    MapLayer, ROAD_MAX_LEVEL, MIN_MAP_SIZE, MAX_MAP_SIZE,
)
from backend.map_data import MapData


def test_generation_deterministic_and_shaped():
    m1 = MapData(width=64, height=64, seed=42)
    m2 = MapData(width=64, height=64, seed=42)
    assert m1.passability_matrix.shape == (64, 64)
    assert m1.roads_matrix.shape == (64, 64)
    assert m1.passability_matrix.dtype == np.uint8
    assert m1.roads_matrix.dtype == np.uint8
    assert np.array_equal(m1.passability_matrix, m2.passability_matrix)
    assert int(m1.roads_matrix.max()) == 0


def test_size_validation_raises():
    with pytest.raises(ValueError):
        MapData(width=MIN_MAP_SIZE - 1, height=64)
    with pytest.raises(ValueError):
        MapData(width=64, height=MAX_MAP_SIZE + 1)


def test_get_tile_at_out_of_bounds():
    m = MapData(width=32, height=32, seed=1)
    assert m.get_tile_at(0, -1, 0) == -1
    assert m.get_tile_at(0, 32, 0) == -1
    assert m.get_tile_at(1, 0, 100) == -1
    assert m.get_tile_at(2, 0, 0) == -1   # неизвестный слой


def test_step_on_tile_increments_and_caps():
    m = MapData(width=16, height=16, seed=7)
    target = None
    for y in range(m.height):
        for x in range(m.width):
            if m.is_passable(x, y):
                target = (x, y); break
        if target: break
    assert target is not None
    x, y = target
    assert m.step_on_tile(x, y) == 1
    assert m.step_on_tile(x, y) == 2
    assert m.step_on_tile(x, y) == 3
    assert m.step_on_tile(x, y) == ROAD_MAX_LEVEL


def test_step_on_water_keeps_zero():
    m = MapData(width=32, height=32, seed=3)
    water = None
    for y in range(m.height):
        for x in range(m.width):
            if m.passability_matrix[y, x] == int(MapLayer.WATER):
                water = (x, y); break
        if water: break
    if water:
        assert m.step_on_tile(*water) == 0


def test_validate_map_with_mines():
    m = MapData(width=64, height=64, seed=11)
    report = m.validate_map([(32, 32)], mine_positions=[(35, 35)], radius=12)
    assert len(report) == 1
    assert report[0]["mines_ok"] is True
    assert isinstance(report[0]["forest_ok"], bool)


def test_validate_map_without_mines_marks_unknown():
    m = MapData(width=64, height=64, seed=11)
    report = m.validate_map([(32, 32)], mine_positions=None, radius=12)
    assert report[0]["mines_ok"] is None