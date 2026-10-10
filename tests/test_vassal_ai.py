import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.constants import (
    BREAKTHROUGH_TICKS, MOBILIZATION_FRACTION_BREAKTHROUGH,
    MOBILIZATION_FRACTION_CENTRAL_BORDER_FREE,
    MOBILIZATION_FRACTION_ENCIRCLED, MOBILIZATION_FRACTION_MID_FREE,
    UnitState, VassalState,
)
from backend.entities import Unit
from backend.tax_buffer import ColonyType, Vassal
from backend.vassal_ai import (
    ColonyPolicy, VassalAI, economy_multiplier_from_mobilization,
    economy_penalty_from_mobilization, mobilization_fraction_for,
    policy_for,
)


def _vassal(colony: ColonyType = ColonyType.MID) -> Vassal:
    return Vassal(
        id=1, faction="human", colony_type=colony,
        hall_grid_x=5, hall_grid_y=5,
    )


def _ai(colony: ColonyType = ColonyType.MID, army: int = 10) -> VassalAI:
    v = _vassal(colony)
    return VassalAI(
        vassal=v, hall_id="hall_1",
        region_center=(5, 5), main_hall_grid=(50, 50),
        army_ids=list(range(100, 100 + army)),
        worker_ids=[201, 202],
    )


def _units_from(ids, dead=()) -> dict:
    units = {}
    for uid in ids:
        alive = uid not in dead
        units[uid] = Unit(id=uid, faction="human", type="footman",
                          pixel_x=0.0, pixel_y=0.0,
                          hp=60 if alive else 0, max_hp=60)
        if not alive:
            units[uid].state = int(UnitState.DEAD)
    return units


# --- стейт-машина ---
def test_initial_state_is_free():
    ai = _ai()
    assert ai.state == int(VassalState.FREE)


def test_encircled_after_signal():
    ai = _ai()
    ai.set_encircled(True)
    ai.update(dt=1 / 60)
    assert ai.state == int(VassalState.ENCIRCLED)


def test_breakthrough_after_5_minutes():
    ai = _ai()
    ai.set_encircled(True)
    ai.update(dt=300.0)
    assert ai.state == int(VassalState.BREAKTHROUGH)


def test_encircled_off_resets_timer():
    ai = _ai()
    ai.set_encircled(True)
    ai.update(dt=17000 / 60)
    ai.set_encircled(False)
    ai.update(dt=1 / 60)
    assert ai.ticks_since_delivery == 0
    assert ai.state == int(VassalState.FREE)


def test_repeated_blockade_does_not_trigger_instantly():
    ai = _ai()
    ai.set_encircled(True)
    ai.update(dt=17000 / 60)
    assert ai.is_breakthrough() is False
    ai.set_encircled(False)
    ai.update(dt=1 / 60)
    assert ai.ticks_since_delivery == 0
    ai.set_encircled(True)
    ai.update(dt=1 / 60)
    assert ai.ticks_since_delivery == 1
    ai.update(dt=17999 / 60)
    assert ai.is_breakthrough() is True


# --- политики ---
def test_policy_by_colony_type():
    assert policy_for("central").troop_kind == "elite"
    assert policy_for("mid").troop_kind == "simple"
    assert policy_for("border").troop_kind == "raiders"
    with pytest.raises(ValueError):
        policy_for("unknown")


# --- экономический множитель ---
def test_economy_penalty_table_midpoints():
    assert economy_penalty_from_mobilization(0.00) == 0.00
    assert economy_penalty_from_mobilization(0.10) == 0.00
    assert economy_penalty_from_mobilization(0.20) == 0.05
    assert economy_penalty_from_mobilization(0.40) == 0.15
    assert economy_penalty_from_mobilization(0.60) == 0.40
    assert economy_penalty_from_mobilization(0.90) == 1.00


def test_economy_multiplier_from_mobilization():
    assert economy_multiplier_from_mobilization(0.00) == 1.00
    assert economy_multiplier_from_mobilization(0.20) == pytest.approx(0.95)
    assert economy_multiplier_from_mobilization(0.60) == pytest.approx(0.60)
    assert economy_multiplier_from_mobilization(0.90) == 0.00


# --- матрица мобилизации (патч v1.5.11, п.4) ---
def test_mobilization_matrix_all_cases():
    F = int(VassalState.FREE)
    E = int(VassalState.ENCIRCLED)
    B = int(VassalState.BREAKTHROUGH)
    assert mobilization_fraction_for("central", F) == MOBILIZATION_FRACTION_CENTRAL_BORDER_FREE
    assert mobilization_fraction_for("border",  F) == MOBILIZATION_FRACTION_CENTRAL_BORDER_FREE
    assert mobilization_fraction_for("mid",     F) == MOBILIZATION_FRACTION_MID_FREE
    assert mobilization_fraction_for("central", E) == MOBILIZATION_FRACTION_ENCIRCLED
    assert mobilization_fraction_for("mid",     E) == MOBILIZATION_FRACTION_ENCIRCLED
    assert mobilization_fraction_for("border",  E) == MOBILIZATION_FRACTION_ENCIRCLED
    assert mobilization_fraction_for("central", B) == MOBILIZATION_FRACTION_BREAKTHROUGH
    assert mobilization_fraction_for("mid",     B) == MOBILIZATION_FRACTION_BREAKTHROUGH
    assert mobilization_fraction_for("border",  B) == MOBILIZATION_FRACTION_BREAKTHROUGH


def test_recommended_mobilization_follows_matrix():
    ai_mid = _ai(ColonyType.MID)
    assert ai_mid.recommended_mobilization() == 0.50

    ai_central = _ai(ColonyType.CENTRAL)
    assert ai_central.recommended_mobilization() == 0.30

    ai_border = _ai(ColonyType.BORDER)
    assert ai_border.recommended_mobilization() == 0.30

    # ENCIRCLED
    ai_mid.set_encircled(True)
    ai_mid.update(dt=1 / 60)
    assert ai_mid.recommended_mobilization() == 0.70

    # BREAKTHROUGH
    ai_mid.update(dt=300.0)
    assert ai_mid.recommended_mobilization() == 1.00


# --- динамический ростер (патч v1.5.11, п.3) ---
def test_mobilized_unit_ids_dynamic_alive_filter():
    ai = _ai(ColonyType.MID, army=10)
    ai.set_mobilization(0.50)
    ids = list(range(100, 110))
    # все живы
    units = _units_from(ids)
    assert len(ai.mobilized_unit_ids(units)) == 5


def test_mobilized_unit_ids_excludes_dead():
    ai = _ai(ColonyType.MID, army=10)
    ai.set_mobilization(0.50)
    ids = list(range(100, 110))
    # 4 мертвы → живы 6 → 50% = 3
    units = _units_from(ids, dead=[100, 101, 102, 103])
    assert len(ai.mobilized_unit_ids(units)) == 3


def test_mobilized_unit_ids_picks_up_new_recruits():
    ai = _ai(ColonyType.MID, army=4)
    ai.set_mobilization(0.50)
    ai.add_army_unit(999)
    ids = list(range(100, 104)) + [999]
    units = _units_from(ids)
    assert len(ai.mobilized_unit_ids(units)) == 2  # 50% от 5


def test_mobilized_unit_ids_zero_when_no_mobilization():
    ai = _ai(ColonyType.MID, army=10)
    assert ai.mobilized_unit_ids(_units_from(range(100, 110))) == []


def test_remove_army_unit():
    ai = _ai(ColonyType.MID, army=5)
    ai.remove_army_unit(102)
    assert 102 not in ai.army_ids
    ai.remove_army_unit(99999)  # no error


# --- разное ---
def test_economy_multiplier_after_mobilization_90():
    ai = _ai()
    ai.set_mobilization(0.90)
    assert ai.economy_multiplier() == 0.0


def test_set_mobilization_out_of_range_raises():
    ai = _ai()
    with pytest.raises(ValueError):
        ai.set_mobilization(-0.1)
    with pytest.raises(ValueError):
        ai.set_mobilization(1.5)


def test_get_breakthrough_force_payload():
    ai = _ai()
    ai.vassal.tax_buffer_gold = 250.7
    ai.vassal.tax_buffer_wood = 130.2
    force = ai.get_breakthrough_force()
    assert force["vassal_id"] == 1
    assert force["cargo_gold"] == 250
    assert force["target_grid"] == (50, 50)