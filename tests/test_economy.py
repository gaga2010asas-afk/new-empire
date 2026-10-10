import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    GOLD_MINE_TRIPS_BASE, GOLD_PER_TRIP, TREE_WOOD_TOTAL,
    WOOD_PER_TRIP_BASE, WOOD_PER_TRIP_MILL, FOOD_MAX_CAP,
)
from backend.economy import Economy, EconomyError, NodeKind, ResourceKind


def test_gather_blocked_when_inactive():
    e = Economy(); e.register_faction("human", gold=100, wood=50)
    assert e.gather_resource("human", "gold", 500) == 100
    assert e.get("human").gold == 100
    assert e.get("human").wood == 50
    e.activate("human")
    assert e.gather_resource("human", "gold", 500) == 600
    assert e.get("human").gold == 600


def test_consume_food_blocked_when_inactive():
    e = Economy(); e.register_faction("human")
    e.add_food_cap("human", 5)
    assert e.can_hire("human") is False
    assert e.consume_food("human", 1) is False
    e.activate("human")
    assert e.can_hire("human") is True
    assert e.consume_food("human", 1) is True


def test_food_cap_hard_limit():
    e = Economy(); e.register_faction("orc"); e.activate("orc")
    e.add_food_cap("orc", 500)
    assert e.get("orc").food_cap == FOOD_MAX_CAP


def test_gold_mine_trips_by_town_hall_level():
    e = Economy()
    m1 = e.make_gold_mine(1, 0, 0, town_hall_level=1)
    m2 = e.make_gold_mine(2, 0, 0, town_hall_level=2)
    m3 = e.make_gold_mine(3, 0, 0, town_hall_level=3)
    assert (m1.trips_remaining, m2.trips_remaining, m3.trips_remaining) == \
           (100, 110, 120)
    with pytest.raises(EconomyError):
        e.make_gold_mine(4, 0, 0, town_hall_level=9)


def test_gold_mine_depletes_to_zero():
    e = Economy()
    n = e.make_gold_mine(10, 3, 4, town_hall_level=1)
    for _ in range(GOLD_MINE_TRIPS_BASE):
        assert e.extract_from_gold_mine(10) == GOLD_PER_TRIP
    assert n.is_empty() is True
    assert e.extract_from_gold_mine(10) == 0


def test_tree_wood_total_and_depletion_base():
    e = Economy()
    n = e.make_tree(20, 0, 0)
    assert n.wood_remaining == TREE_WOOD_TOTAL
    trips = 0
    while not n.is_empty():
        e.extract_wood_from_tree(20, has_lumber_mill=False)
        trips += 1
    assert trips == TREE_WOOD_TOTAL // WOOD_PER_TRIP_BASE   # 25


def test_tree_wood_with_mill_trips_count():
    e = Economy()
    n = e.make_tree(21, 0, 0)
    trips = 0
    while not n.is_empty():
        e.extract_wood_from_tree(21, has_lumber_mill=True)
        trips += 1
    assert trips == TREE_WOOD_TOTAL // WOOD_PER_TRIP_MILL   # 20


def test_tree_partial_last_trip():
    e = Economy()
    n = e.make_tree(30, 0, 0, total_wood=50)
    got = e.extract_wood_from_tree(30, has_lumber_mill=False)
    assert got == 50
    assert n.is_empty() is True


def test_extract_wrong_node_kind_raises():
    e = Economy()
    e.make_tree(40, 0, 0)
    with pytest.raises(EconomyError):
        e.extract_from_gold_mine(40)
    e.make_gold_mine(41, 0, 0)
    with pytest.raises(EconomyError):
        e.extract_wood_from_tree(41, has_lumber_mill=False)