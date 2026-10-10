import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pathlib import Path
import pytest

from backend.content_loader import ContentLoader, ContentError


FOOTMAN = {
    "id": "footman", "faction": "human", "hp": 60, "damage": 8,
    "armor": 3, "sprite": "sprites/human/units/footman.png",
    "cost": {"gold": 600, "wood": 0}, "build_time": 45,
    "triad_role": "infantry",
}
FARM = {
    "id": "farm", "faction": "human", "hp": 400,
    "cost": {"gold": 500, "wood": 250}, "build_time": 100,
    "grid_width": 2, "grid_height": 2,
}


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_load_data_only(tmp_path):
    _write(tmp_path / "data/units/footman.json", FOOTMAN)
    _write(tmp_path / "data/buildings/farm.json", FARM)
    _write(tmp_path / "data/factions/human.json", {"id": "human"})

    loader = ContentLoader(tmp_path / "data", tmp_path / "mods")
    report = loader.load_all()
    assert report.units_loaded == 1
    assert report.buildings_loaded == 1
    assert report.factions_loaded == 1
    assert loader.get_unit("footman")["hp"] == 60
    assert loader.get_building("farm")["grid_width"] == 2


def test_mod_overrides_data(tmp_path):
    _write(tmp_path / "data/units/footman.json", FOOTMAN)
    _write(tmp_path / "mods/balance/manifest.json", {"name": "balance"})
    _write(tmp_path / "mods/balance/units/footman.json", dict(FOOTMAN, hp=99))

    loader = ContentLoader(tmp_path / "data", tmp_path / "mods")
    loader.load_all()
    assert loader.get_unit("footman")["hp"] == 99
    assert loader.report.mods_applied == 1


def test_missing_required_field_raises(tmp_path):
    bad = dict(FOOTMAN); bad.pop("hp")
    _write(tmp_path / "data/units/footman.json", bad)

    loader = ContentLoader(tmp_path / "data", tmp_path / "mods")
    with pytest.raises(ContentError):
        loader.load_all()


def test_unknown_faction_raises(tmp_path):
    bad = dict(FOOTMAN, faction="elves")
    _write(tmp_path / "data/units/footman.json", bad)
    loader = ContentLoader(tmp_path / "data", tmp_path / "mods")
    with pytest.raises(ContentError):
        loader.load_all()


def test_get_missing_unit_raises(tmp_path):
    loader = ContentLoader(tmp_path / "data", tmp_path / "mods")
    loader.load_all()
    with pytest.raises(ContentError):
        loader.get_unit("ghost")


def test_invalid_grid_size_raises(tmp_path):
    bad = dict(FARM, grid_width=0)
    _write(tmp_path / "data/buildings/farm.json", bad)
    loader = ContentLoader(tmp_path / "data", tmp_path / "mods")
    with pytest.raises(ContentError):
        loader.load_all()