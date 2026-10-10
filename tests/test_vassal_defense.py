import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.chokepoint import Chokepoint
from backend.constants import (
    MAX_TOWERS_BORDER, MAX_TOWERS_CENTRAL, MAX_TOWERS_MID,
    MIN_TOWER_SPACING, MapLayer,
)
from backend.map_data import MapData
from backend.vassal_ai import policy_for
from backend.vassal_defense import (
    encircle_with_farms, max_catapults_for_colony, max_towers_for_colony,
    place_catapult_behind, select_towers,
)


def _blank(size: int = 20) -> MapData:
    m = MapData(width=size, height=size, seed=0)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def _cp(x, y, w=1, o="horizontal"):
    return Chokepoint(grid_x=x, grid_y=y, width=w,
                      orientation=o, score=float(4 - w))


def test_select_towers_respects_min_spacing():
    cps = [_cp(5, 5), _cp(7, 5), _cp(10, 10), _cp(15, 10)]
    towers = select_towers(cps, min_spacing=MIN_TOWER_SPACING, max_towers=10)
    for i, a in enumerate(towers):
        for b in towers[i + 1:]:
            d2 = (a.grid_x - b.grid_x) ** 2 + (a.grid_y - b.grid_y) ** 2
            assert d2 >= MIN_TOWER_SPACING * MIN_TOWER_SPACING


def test_select_towers_max_limit():
    cps = [_cp(1, 1), _cp(5, 5), _cp(10, 10), _cp(15, 15)]
    towers = select_towers(cps, min_spacing=4, max_towers=2)
    assert len(towers) == 2


def test_encircle_with_farms_returns_8_neighbors():
    m = _blank()
    farms = encircle_with_farms((10, 10), m)
    assert len(farms) == 8
    assert (10, 10) not in farms


def test_encircle_skips_block_and_occupied():
    m = _blank()
    m.passability_matrix[9, 10] = int(MapLayer.BLOCK)
    farms = encircle_with_farms((10, 10), m, occupied={(11, 10)})
    assert (10, 9) not in farms
    assert (11, 10) not in farms
    assert len(farms) == 6


def test_catapult_placed_toward_base():
    m = _blank()
    pos = place_catapult_behind((10, 10), base_grid=(10, 5),
                                distance=3, map_data=m)
    assert pos == (10, 7)


def test_catapult_returns_none_on_blocked():
    m = _blank()
    m.passability_matrix[7, 10] = int(MapLayer.BLOCK)
    assert place_catapult_behind((10, 10), (10, 5),
                                 distance=3, map_data=m) is None


def test_max_towers_by_colony_matches_policy():
    """v1.5.6, замечание №1: обёртка над policy_for."""
    assert max_towers_for_colony("central") == policy_for("central").max_towers
    assert max_towers_for_colony("mid")     == policy_for("mid").max_towers
    assert max_towers_for_colony("border")  == policy_for("border").max_towers
    assert max_towers_for_colony("central") == MAX_TOWERS_CENTRAL
    assert max_towers_for_colony("mid")     == MAX_TOWERS_MID
    assert max_towers_for_colony("border")  == MAX_TOWERS_BORDER
    with pytest.raises(ValueError):
        max_towers_for_colony("unknown")


def test_max_catapults_by_colony_matches_policy():
    assert max_catapults_for_colony("central") == policy_for("central").max_catapults
    assert max_catapults_for_colony("mid")     == policy_for("mid").max_catapults
    assert max_catapults_for_colony("border")  == policy_for("border").max_catapults