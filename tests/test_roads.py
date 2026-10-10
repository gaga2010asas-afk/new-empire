import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    ROAD_COST_BASE, ROAD_COST_LEVEL_1, ROAD_COST_LEVEL_2,
    ROAD_COST_LEVEL_3, ROAD_MAX_LEVEL, ROAD_SPEED_MULTIPLIER,
    MapLayer,
)
from backend.map_data import MapData
from backend.roads import (
    speed_multiplier, cost_for_astar, road_cost_function, ambush_targets,
)


def _flat(size: int = 8) -> MapData:
    m = MapData(width=size, height=size, seed=0)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def test_speed_multiplier_only_on_level_3():
    m = _flat()
    assert speed_multiplier(m, 0, 0) == 1.0
    m.trample_tile(0, 0)
    assert speed_multiplier(m, 0, 0) == 1.0
    m.trample_tile(0, 0)
    assert speed_multiplier(m, 0, 0) == 1.0
    m.trample_tile(0, 0)
    assert speed_multiplier(m, 0, 0) == ROAD_SPEED_MULTIPLIER


def test_speed_multiplier_off_map_and_block():
    m = _flat()
    assert speed_multiplier(m, -1, -1) == 1.0
    m.passability_matrix[3, 3] = int(MapLayer.BLOCK)
    m.roads_matrix[3, 3] = ROAD_MAX_LEVEL
    assert speed_multiplier(m, 3, 3) == 1.0


def test_cost_for_astar_decreases_with_road_level():
    m = _flat()
    c0 = cost_for_astar(m, 0, 0)
    m.trample_tile(1, 0)
    c1 = cost_for_astar(m, 1, 0)
    m.trample_tile(2, 0); m.trample_tile(2, 0)
    c2 = cost_for_astar(m, 2, 0)
    m.trample_tile(3, 0); m.trample_tile(3, 0); m.trample_tile(3, 0)
    c3 = cost_for_astar(m, 3, 0)
    assert (c0, c1, c2, c3) == (
        ROAD_COST_BASE, ROAD_COST_LEVEL_1, ROAD_COST_LEVEL_2, ROAD_COST_LEVEL_3,
    )


def test_cost_for_astar_off_map_and_block():
    m = _flat()
    assert cost_for_astar(m, -1, 0) == 999
    m.passability_matrix[0, 0] = int(MapLayer.BLOCK)
    assert cost_for_astar(m, 0, 0) == 999


def test_ambush_targets_finds_level_2_and_3():
    m = _flat()
    m.trample_tile(0, 0)
    m.trample_tile(1, 0); m.trample_tile(1, 0)
    m.trample_tile(2, 0); m.trample_tile(2, 0); m.trample_tile(2, 0)
    targets = ambush_targets(m, min_level=2)
    assert (1, 0) in targets
    assert (2, 0) in targets
    assert (0, 0) not in targets


def test_road_cost_function_returns_callable():
    m = _flat()
    m.trample_tile(0, 0); m.trample_tile(0, 0); m.trample_tile(0, 0)
    fn = road_cost_function(m)
    assert fn(0, 0) == ROAD_COST_LEVEL_3
    assert fn(5, 5) == ROAD_COST_BASE