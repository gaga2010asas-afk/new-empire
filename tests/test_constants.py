import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from backend.constants import (
    TARGET_FPS, TILE_SIZE, MAX_UNITS_LIMIT,
    WATER_NOISE_THRESHOLD, BLOCK_NOISE_THRESHOLD,
    TRIAD_ROLES, FACTION_IDS, TILESET_PIXEL_WIDTH, TILESET_PIXEL_HEIGHT,
    UnitState, BuildingState, MapLayer,
)


def test_core_numbers():
    assert TARGET_FPS == 60
    assert TILE_SIZE == 128
    assert MAX_UNITS_LIMIT == 10000


def test_noise_thresholds_order():
    assert 0.0 <= WATER_NOISE_THRESHOLD < BLOCK_NOISE_THRESHOLD <= 1.0


def test_enums_contiguous():
    assert [int(s) for s in UnitState] == list(range(7))
    assert [int(s) for s in BuildingState] == list(range(4))
    assert [int(l) for l in MapLayer] == [0, 1, 2]


def test_triad_and_factions_and_tileset_geometry():
    assert set(TRIAD_ROLES) == {"infantry", "tank", "artillery"}
    assert set(FACTION_IDS) == {"human", "orc"}
    assert TILESET_PIXEL_WIDTH == 2048
    assert TILESET_PIXEL_HEIGHT == 3072