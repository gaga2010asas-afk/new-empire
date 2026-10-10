import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    BuildingState, TILE_SIZE, UnitState,
)
from backend.entities import (
    Building, Unit, building_from_content, unit_from_content,
)


# --- Unit ---
def test_unit_creation_and_alive():
    u = Unit(id=1, faction="human", type="footman",
             pixel_x=0.0, pixel_y=0.0, hp=50, max_hp=60)
    assert u.is_alive()
    u.state = int(UnitState.DEAD)
    assert not u.is_alive()


def test_unit_invalid_direction_raises():
    with pytest.raises(ValueError):
        Unit(id=1, faction="human", type="footman",
             pixel_x=0, pixel_y=0, hp=1, max_hp=1, direction=8)


def test_unit_hp_over_max_raises():
    with pytest.raises(ValueError):
        Unit(id=1, faction="human", type="footman",
             pixel_x=0, pixel_y=0, hp=100, max_hp=50)


# --- Building ---
def test_building_creation_and_destroy():
    b = Building(id="hall_1", grid_x=10, grid_y=10, width=2, height=2,
                 hp=400, max_hp=400)
    assert b.is_alive()
    b.state = int(BuildingState.DESTROYED)
    assert not b.is_alive()


def test_building_invalid_size_raises():
    with pytest.raises(ValueError):
        Building(id="b", grid_x=0, grid_y=0, width=0, height=2,
                 hp=1, max_hp=1)


def test_building_requires_nonempty_id():
    with pytest.raises(ValueError):
        Building(id="", grid_x=0, grid_y=0, width=1, height=1,
                 hp=1, max_hp=1)


# --- v1.5.16, п.9: центр здания ---
def test_building_center_px_math():
    """Математический центр, не левый верхний угол."""
    b = Building(id="townhall", grid_x=10, grid_y=20,
                 width=4, height=2, hp=1, max_hp=1)
    cx, cy = b.center_px()
    assert cx == (10 + 2) * TILE_SIZE
    assert cy == (20 + 1) * TILE_SIZE


def test_building_center_px_2x2():
    """Town Hall 2×2 — центр в углу 4 тайлов."""
    b = Building(id="hall", grid_x=0, grid_y=0, width=2, height=2,
                 hp=1, max_hp=1)
    cx, cy = b.center_px()
    assert cx == pytest.approx(1.0 * TILE_SIZE)
    assert cy == pytest.approx(1.0 * TILE_SIZE)


def test_building_center_px_single_tile():
    """Здание 1×1 — центр совпадает с центром тайла."""
    b = Building(id="small", grid_x=5, grid_y=5, width=1, height=1,
                 hp=1, max_hp=1)
    cx, cy = b.center_px()
    assert cx == pytest.approx((5 + 0.5) * TILE_SIZE)
    assert cy == pytest.approx((5 + 0.5) * TILE_SIZE)


def test_building_center_px_not_top_left():
    """Явная проверка: центр ≠ (grid_x, grid_y) для зданий >1×1."""
    b = Building(id="hall", grid_x=3, grid_y=3, width=2, height=2,
                 hp=1, max_hp=1)
    cx, cy = b.center_px()
    assert (cx, cy) != (3 * TILE_SIZE, 3 * TILE_SIZE)


# --- Фабрики ---
def test_unit_from_content_maps_stats():
    content = {
        "id": "footman", "faction": "human", "hp": 60, "damage": 8,
        "armor": 3, "sprite": "sprites/human/units/footman.png",
        "cost": {"gold": 600, "wood": 0}, "build_time": 45,
        "triad_role": "infantry",
    }
    u = unit_from_content(1, "human", content, 128.0, 256.0)
    assert u.max_hp == 60
    assert u.stats["damage"] == 8
    assert u.stats["triad_role"] == "infantry"


def test_building_from_content_generates_unique_id():
    content = {
        "id": "farm", "faction": "human", "hp": 400,
        "cost": {"gold": 500, "wood": 250}, "build_time": 100,
        "grid_width": 2, "grid_height": 3,
    }
    b1 = building_from_content(5, 6, "human", content)
    b2 = building_from_content(7, 6, "human", content)
    assert (b1.grid_x, b1.grid_y, b1.width, b1.height) == (5, 6, 2, 3)
    assert b1.id != b2.id
    b3 = building_from_content(9, 9, "human", content, id_override="my_farm")
    assert b3.id == "my_farm"