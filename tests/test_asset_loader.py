import pygame
import pytest

from src.frontend.asset_loader import AssetLoader, AnimSpec, TILE_SIZE


def _make_sheet(path, cols, rows, ts=TILE_SIZE):
    sheet = pygame.Surface((cols * ts, rows * ts), pygame.SRCALPHA)
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            color = (idx % 256, (idx * 7) % 256, (idx * 13) % 256, 255)
            sheet.fill(color, pygame.Rect(c * ts, r * ts, ts, ts))
    pygame.image.save(sheet, str(path))


def _make_unit_sheet(path, frame_w, frame_h, max_cols, rows=1):
    sheet = pygame.Surface((max_cols * frame_w, rows * frame_h), pygame.SRCALPHA)
    idx = 0
    for r in range(rows):
        for c in range(max_cols):
            color = (idx % 256, (idx * 5) % 256, (idx * 11) % 256, 255)
            sheet.fill(color, pygame.Rect(c * frame_w, r * frame_h, frame_w, frame_h))
            idx += 1
    pygame.image.save(sheet, str(path))


# --- v1.5.16 №16: динамическая сетка ----------------------------------------

def test_load_terrain_16x24_dynamic(tmp_path):
    p = tmp_path / "summer_hd.png"
    _make_sheet(p, cols=16, rows=24)
    loader = AssetLoader()
    loader.load_terrain(str(p))
    assert loader.tile_count() == 16 * 24 == 384
    assert loader.terrain_cols == 16
    assert loader.terrain_rows == 24
    assert loader.get_tile(0).get_size() == (TILE_SIZE, TILE_SIZE)


def test_load_terrain_20x30_dynamic(tmp_path):
    """Альтернативный апскейл 20×30 — должно работать без правок кода."""
    p = tmp_path / "summer_hd.png"
    _make_sheet(p, cols=20, rows=30)
    loader = AssetLoader()
    loader.load_terrain(str(p))
    assert loader.tile_count() == 20 * 30 == 600
    assert loader.terrain_cols == 20
    assert loader.terrain_rows == 30


def test_load_terrain_single_tile_dynamic(tmp_path):
    p = tmp_path / "summer_hd.png"
    _make_sheet(p, cols=1, rows=1)
    loader = AssetLoader()
    loader.load_terrain(str(p))
    assert loader.tile_count() == 1


def test_load_terrain_too_small_raises(tmp_path):
    """< 1 тайла по каждой оси → ValueError."""
    p = tmp_path / "tiny.png"
    pygame.image.save(pygame.Surface((64, 64)), str(p))
    loader = AssetLoader()
    with pytest.raises(ValueError):
        loader.load_terrain(str(p))


def test_missing_sheet_raises(tmp_path):
    loader = AssetLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_terrain(str(tmp_path / "nope.png"))


# --- курсоры ----------------------------------------------------------------

def test_load_cursors_empty_dir(tmp_path):
    loader = AssetLoader()
    loader.load_cursors(str(tmp_path))
    assert loader.cursors == {}


def test_load_cursors_png(tmp_path):
    cdir = tmp_path / "cursors"
    cdir.mkdir()
    img = pygame.Surface((16, 16), pygame.SRCALPHA)
    img.fill((255, 255, 0, 255))
    pygame.image.save(img, str(cdir / "normal.png"))
    loader = AssetLoader()
    loader.load_cursors(str(cdir))
    assert loader.get_cursor("normal").get_size() == (16, 16)


# --- юниты / здания ---------------------------------------------------------

def test_load_unit_sheet_slices_frames(tmp_path):
    p = tmp_path / "peasant.png"
    _make_unit_sheet(p, 32, 32, max_cols=4, rows=1)
    loader = AssetLoader()
    spec = {"idle": AnimSpec(row=0, frame_count=4, directions=1)}
    loader.load_unit_sheet("peasant", str(p), 32, 32, spec)
    frames = loader.get_unit_frames("peasant", "idle", 0)
    assert frames is not None and len(frames) == 4
    assert frames[0].get_size() == (32, 32)


def test_unit_directions_pick_correct_row(tmp_path):
    p = tmp_path / "peasant.png"
    _make_unit_sheet(p, 32, 32, max_cols=8, rows=1)
    loader = AssetLoader()
    spec = {"walk": AnimSpec(row=0, frame_count=4, directions=2)}
    loader.load_unit_sheet("peasant", str(p), 32, 32, spec)
    d0 = loader.get_unit_frames("peasant", "walk", 0)
    d1 = loader.get_unit_frames("peasant", "walk", 1)
    assert len(d0) == 4 and len(d1) == 4
    assert pygame.image.tobytes(d0[0], "RGBA") != pygame.image.tobytes(d1[0], "RGBA")


def test_load_building_sheet_and_get_size(tmp_path):
    p = tmp_path / "town_hall.png"
    _make_unit_sheet(p, 128, 128, max_cols=2, rows=1)
    loader = AssetLoader()
    loader.load_building_sheet("town_hall", str(p), 128, 128, frames=2)
    assert loader.get_building_size("town_hall") == (128, 128)
    assert loader.get_building_frame("town_hall", 1) is not None


def test_building_sheet_too_small_raises(tmp_path):
    p = tmp_path / "farm.png"
    pygame.image.save(pygame.Surface((64, 64)), str(p))
    loader = AssetLoader()
    with pytest.raises(ValueError):
        loader.load_building_sheet("farm", str(p), 128, 128, frames=1)


# --- тени / spell-иконки ----------------------------------------------------

def test_shadow_ellipse_cached():
    loader = AssetLoader()
    s1 = loader.get_shadow_ellipse(64, 24)
    s2 = loader.get_shadow_ellipse(64, 24)
    assert s1 is s2
    s3 = loader.get_shadow_ellipse(128, 48)
    assert s3 is not s1
    assert s1.get_size() == (64, 24)


def test_load_spell_icons_from_dir(tmp_path):
    d = tmp_path / "spells"
    d.mkdir()
    img = pygame.Surface((32, 32), pygame.SRCALPHA)
    img.fill((255, 100, 0, 255))
    pygame.image.save(img, str(d / "healing.png"))
    pygame.image.save(img, str(d / "fireball.png"))
    loader = AssetLoader()
    loader.load_spell_icons(str(d))
    assert "healing" in loader.spell_icons
    assert "fireball" in loader.spell_icons
    assert loader.get_spell_icon("healing").get_size() == (32, 32)


def test_load_spell_icons_empty_dir(tmp_path):
    loader = AssetLoader()
    loader.load_spell_icons(str(tmp_path))
    assert loader.spell_icons == {}