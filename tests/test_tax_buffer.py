import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    TAX_CAPACITY_LAND_GOLD, TAX_CAPACITY_LAND_WOOD,
    TAX_CAPACITY_WATER_GOLD, TAX_CAPACITY_WATER_WOOD,
    TAX_TIMEOUT_TICKS, VassalState,
)
from backend.tax_buffer import ColonyType, TaxBuffer, Vassal


def _vassal(**kw) -> Vassal:
    return Vassal(
        id=1, faction="human", colony_type=ColonyType.MID,
        hall_grid_x=0, hall_grid_y=0, **kw,
    )


def test_vassal_state_enum_defaults_to_free():
    v = _vassal()
    assert v.state == int(VassalState.FREE)
    v.state = int(VassalState.ENCIRCLED)
    assert v.state == 1
    v.state = int(VassalState.BREAKTHROUGH)
    assert v.state == 2


def test_buffer_accumulates_per_tick_with_formula():
    tb = TaxBuffer(); v = _vassal()
    for _ in range(10):
        tb.update(v, 10.0, 4.0, tax_rate=0.25)
    assert v.tax_buffer_gold == pytest.approx(25.0)
    assert v.tax_buffer_wood == pytest.approx(10.0)
    assert v.colony_treasury_gold == pytest.approx(75.0)
    assert v.colony_treasury_wood == pytest.approx(30.0)


def test_send_triggered_when_full():
    tb = TaxBuffer(); v = _vassal()
    triggered = False
    for _ in range(100):
        if tb.update(v, 100.0, 0.0, tax_rate=1.0):
            triggered = True; break
    assert triggered
    assert v.tax_buffer_gold >= TAX_CAPACITY_LAND_GOLD


def test_timeout_forces_send_when_over_half_but_not_full():
    tb = TaxBuffer(); v = _vassal()
    v.tax_buffer_gold = TAX_CAPACITY_LAND_GOLD * 0.6
    v.tax_buffer_wood = TAX_CAPACITY_LAND_WOOD * 0.6
    assert v.is_over_half() is True
    assert v.is_full() is False

    triggered = False
    for tick in range(TAX_TIMEOUT_TICKS + 10):
        if tb.update(v, 0.0, 0.0, tax_rate=0.5):
            triggered = True
            assert tick + 1 >= TAX_TIMEOUT_TICKS
            break
    assert triggered


def test_pending_group_blocks_retrigger():
    tb = TaxBuffer(); v = _vassal()
    v.tax_buffer_gold = TAX_CAPACITY_LAND_GOLD * 2
    v.tax_buffer_wood = TAX_CAPACITY_LAND_WOOD * 2
    assert tb.update(v, 0.0, 0.0, 0.0) is True
    tb.mark_group_sent(v)
    v.tax_buffer_gold = TAX_CAPACITY_LAND_GOLD * 2
    assert tb.update(v, 0.0, 0.0, 0.0) is False


def test_group_loss_resets_buffer_and_clears_pending():
    tb = TaxBuffer(); v = _vassal()
    v.tax_buffer_gold = 300.0
    v.tax_buffer_wood = 200.0
    tb.mark_group_sent(v)
    assert v.pending_group is True
    assert v.tax_buffer_gold == 0.0
    tb.on_group_lost(v)
    assert v.pending_group is False
    assert v.tax_buffer_gold == 0.0
    assert v.tax_buffer_wood == 0.0
    assert v.tax_timeout_ticks == 0


def test_water_route_switches_capacity():
    tb = TaxBuffer(); v = _vassal()
    tb.use_water_route(v)
    assert v.tax_capacity_gold == TAX_CAPACITY_WATER_GOLD
    assert v.tax_capacity_wood == TAX_CAPACITY_WATER_WOOD
    tb.use_land_route(v)
    assert v.tax_capacity_gold == TAX_CAPACITY_LAND_GOLD
    assert v.tax_capacity_wood == TAX_CAPACITY_LAND_WOOD


def test_tax_rate_out_of_range_raises():
    tb = TaxBuffer(); v = _vassal()
    with pytest.raises(ValueError):
        tb.update(v, 10.0, 10.0, tax_rate=1.5)
    with pytest.raises(ValueError):
        tb.update(v, -1.0, 0.0, tax_rate=0.2)


def test_zero_tax_rate_keeps_buffer_empty():
    tb = TaxBuffer(); v = _vassal()
    for _ in range(50):
        tb.update(v, 100.0, 100.0, tax_rate=0.0)
    assert v.tax_buffer_gold == 0.0
    assert v.colony_treasury_gold == pytest.approx(5000.0)