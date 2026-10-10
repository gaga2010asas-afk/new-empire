import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import MapLayer
from backend.map_data import MapData
from backend.vassal_builder import BeautyBuilder, BuildPlan


def _blank(size: int = 30) -> MapData:
    m = MapData(width=size, height=size, seed=0)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def test_farm_street_east_line():
    m = _blank()
    b = BeautyBuilder(m)
    farms = b.farm_street((5, 5), "E", count=4, spacing=2)
    assert farms == [(5, 5), (7, 5), (9, 5), (11, 5)]


def test_farm_street_skips_block_tiles():
    m = _blank()
    m.passability_matrix[5, 7] = int(MapLayer.BLOCK)
    b = BeautyBuilder(m)
    farms = b.farm_street((5, 5), "E", count=4, spacing=2)
    assert (7, 5) not in farms
    assert (5, 5) in farms and (9, 5) in farms


def test_farm_street_invalid_direction_raises():
    m = _blank()
    b = BeautyBuilder(m)
    with pytest.raises(ValueError):
        b.farm_street((5, 5), "NE", count=3)


def test_barracks_quarter_offset():
    m = _blank()
    b = BeautyBuilder(m)
    pos = b.barracks_quarter((5, 5), offset=(6, 6), count=2, spacing=3)
    assert pos == [(11, 11), (14, 11)]


def test_blacksmith_near_barracks():
    m = _blank()
    b = BeautyBuilder(m)
    barracks = b.barracks_quarter((5, 5), offset=(6, 6), count=1, spacing=3)
    smith = b.blacksmith_near_barracks(barracks, offset=(0, 3))
    assert smith == (11, 14)


def test_blacksmith_none_when_no_barracks():
    m = _blank()
    b = BeautyBuilder(m)
    assert b.blacksmith_near_barracks([]) is None


def test_plan_returns_full_layout():
    m = _blank(30)
    b = BeautyBuilder(m)
    plan = b.plan((5, 5), road_direction="E", farm_count=3,
                  barracks_count=2)
    assert isinstance(plan, BuildPlan)
    assert len(plan.farms) == 3
    assert len(plan.barracks) == 2
    assert plan.blacksmith is not None
    positions = plan.all_positions()
    assert len(positions) == len(set(positions))


def test_plan_respects_occupied():
    m = _blank(30)
    b = BeautyBuilder(m)
    occupied = {(11, 11)}
    plan = b.plan((5, 5), farm_count=2, barracks_count=2,
                  occupied=occupied)
    assert (11, 11) not in plan.barracks


def test_plan_does_not_mutate_input_occupied():
    """Проверка, что входной set не мутируется."""
    m = _blank(30)
    b = BeautyBuilder(m)
    user_occupied = {(15, 15)}
    original = set(user_occupied)
    b.plan((5, 5), farm_count=2, barracks_count=2,
           occupied=user_occupied)
    assert user_occupied == original