import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from backend.constants import MapLayer
from backend.map_data import MapData
from backend.pathfinding import PathFinder


def _open_map(size=10) -> MapData:
    m = MapData(width=size, height=size, seed=0)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def test_path_straight_line():
    m = _open_map(10)
    pf = PathFinder(m)
    path = pf.find_path((0, 0), (5, 0))
    assert path[0] == (0, 0)
    assert path[-1] == (5, 0)
    assert len(path) == 6


def test_path_around_wall():
    m = _open_map(10)
    for y in range(0, 9):
        m.passability_matrix[y, 3] = int(MapLayer.BLOCK)
    pf = PathFinder(m)
    path = pf.find_path((0, 0), (5, 0))
    assert path[0] == (0, 0)
    assert path[-1] == (5, 0)
    for (x, y) in path:
        assert m.get_layer(x, y) == int(MapLayer.GROUND)


def test_goal_blocked_falls_back_to_nearest_passable():
    m = _open_map(10)
    m.passability_matrix[5, 5] = int(MapLayer.BLOCK)
    pf = PathFinder(m)
    path = pf.find_path((0, 0), (5, 5))
    assert path
    end = path[-1]
    assert end != (5, 5)
    assert m.get_layer(*end) == int(MapLayer.GROUND)


def test_unreachable_returns_empty():
    m = _open_map(6)
    for x in range(m.width):
        m.passability_matrix[3, x] = int(MapLayer.BLOCK)
    pf = PathFinder(m)
    assert pf.find_path((0, 0), (0, 5)) == []


def test_cache_returns_copy():
    m = _open_map(10)
    pf = PathFinder(m)
    a = pf.find_path((0, 0), (3, 0))
    a.append((99, 99))
    b = pf.find_path((0, 0), (3, 0))
    assert (99, 99) not in b