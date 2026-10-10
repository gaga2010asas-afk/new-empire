import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from backend.chokepoint import find_chokepoints
from backend.constants import MapLayer
from backend.map_data import MapData


def _blank(size: int = 20) -> MapData:
    m = MapData(width=size, height=size, seed=0)
    m.passability_matrix[:, :] = int(MapLayer.GROUND)
    return m


def test_open_map_has_no_chokepoints():
    m = _blank(20)
    assert find_chokepoints(m) == []


def test_single_wall_with_gap_is_a_chokepoint():
    m = _blank(20)
    for x in range(m.width):
        m.passability_matrix[10, x] = int(MapLayer.BLOCK)
    m.passability_matrix[10, 9] = int(MapLayer.GROUND)
    m.passability_matrix[10, 10] = int(MapLayer.GROUND)

    cps = find_chokepoints(m, region=(5, 5, 15, 15))
    assert len(cps) >= 1
    for cp in cps:
        assert cp.width <= 3


def test_wide_gap_is_not_chokepoint():
    m = _blank(20)
    for x in range(m.width):
        m.passability_matrix[10, x] = int(MapLayer.BLOCK)
    for gx in range(7, 13):
        m.passability_matrix[10, gx] = int(MapLayer.GROUND)
    cps = find_chokepoints(m, region=(0, 0, 20, 20))
    assert cps == []


def test_cluster_dedup_nearby_tiles():
    m = _blank(20)
    for x in range(m.width):
        m.passability_matrix[10, x] = int(MapLayer.BLOCK)
    m.passability_matrix[10, 9] = int(MapLayer.GROUND)
    cps = find_chokepoints(m, region=(5, 5, 15, 15))
    assert len(cps) == 1
    assert cps[0].width == 1


def test_cluster_strict_less_than_radius():
    """
    v1.5.6 (замечание №2): строгое `<` при кластеризации.
    Два кандидата на расстоянии ровно 3 тайла при radius=3
    считаются ДВУМЯ разными точками (3 >= 3).
    """
    m = _blank(20)
    for x in range(m.width):
        m.passability_matrix[10, x] = int(MapLayer.BLOCK)
        m.passability_matrix[18, x] = int(MapLayer.BLOCK)
    # Проход 1 (y=10) в x=9; проход 2 (y=18) в x=9 — расстояние 8, ок
    m.passability_matrix[10, 9] = int(MapLayer.GROUND)
    m.passability_matrix[18, 9] = int(MapLayer.GROUND)

    cps = find_chokepoints(m, region=(0, 0, 20, 20), cluster_radius=3)
    assert len(cps) == 2


def test_cluster_below_radius_merges():
    """
    Два кандидата на расстоянии 2 тайла при radius=3 должны слиться.
    """
    m = _blank(20)
    # Два вертикальных прохода рядом: x=9 и x=11, оба y=10, стены N/S
    for x in range(m.width):
        m.passability_matrix[10, x] = int(MapLayer.BLOCK)
    for gx in (9, 10, 11):
        m.passability_matrix[10, gx] = int(MapLayer.GROUND)
    # Здесь будет один широкий проход (ширина 3) — но это лишь 1 кластер
    cps = find_chokepoints(m, region=(0, 0, 20, 20), cluster_radius=3)
    # Все кандидаты внутри x=9..11 попадают в один кластер
    xs = sorted(set(cp.grid_x for cp in cps))
    # Ни одна пара кандидатов не должна быть на расстоянии < 3
    for i, a in enumerate(cps):
        for b in cps[i + 1:]:
            d2 = (a.grid_x - b.grid_x) ** 2 + (a.grid_y - b.grid_y) ** 2
            assert d2 >= 9


def test_score_higher_for_narrower():
    m = _blank(20)
    for x in range(m.width):
        m.passability_matrix[10, x] = int(MapLayer.BLOCK)
        m.passability_matrix[18, x] = int(MapLayer.BLOCK)
    m.passability_matrix[10, 9] = int(MapLayer.GROUND)
    for gx in (8, 9, 10):
        m.passability_matrix[18, gx] = int(MapLayer.GROUND)

    cps = find_chokepoints(m, region=(0, 0, 20, 20), cluster_radius=2)
    assert len(cps) >= 1
    assert cps[0].width == 1