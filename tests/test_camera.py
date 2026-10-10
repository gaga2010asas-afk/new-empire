import pygame
import pytest

from src.frontend.camera import (
    Camera,
    TILE_SIZE,
    EDGE_MARGIN,
    KEY_SCROLL_SPEED_DEFAULT,
    EDGE_SCROLL_SPEED_DEFAULT,
    DEFAULT_DT,
)


class FakeKeys:
    def __init__(self, pressed=()):
        self._set = set(pressed)

    def __getitem__(self, code):
        return code in self._set


@pytest.fixture
def cam():
    return Camera(1024, 768)


def test_keyboard_scroll_moves_camera(cam):
    cam.update((512, 384), FakeKeys([pygame.K_d, pygame.K_s]), dt=DEFAULT_DT)
    assert cam.camera_x == pytest.approx(KEY_SCROLL_SPEED_DEFAULT * DEFAULT_DT)
    assert cam.camera_y == pytest.approx(KEY_SCROLL_SPEED_DEFAULT * DEFAULT_DT)


def test_edge_scroll_top_left(cam):
    cam.update((EDGE_MARGIN - 1, EDGE_MARGIN - 1), FakeKeys(), dt=DEFAULT_DT)
    assert cam.camera_x == pytest.approx(-EDGE_SCROLL_SPEED_DEFAULT * DEFAULT_DT)
    assert cam.camera_y == pytest.approx(-EDGE_SCROLL_SPEED_DEFAULT * DEFAULT_DT)


def test_center_mouse_no_scroll(cam):
    cam.update((512, 384), FakeKeys(), dt=DEFAULT_DT)
    assert cam.camera_x == 0.0
    assert cam.camera_y == 0.0


def test_clamp_bounds(cam):
    cam.camera_x = 9_999_999.0
    cam.camera_y = 9_999_999.0
    cam.clamp(64, 64)
    assert cam.camera_x == float(64 * TILE_SIZE - 1024)
    assert cam.camera_y == float(64 * TILE_SIZE - 768)

    cam.camera_x = -500.0
    cam.camera_y = -500.0
    cam.clamp(64, 64)
    assert (cam.camera_x, cam.camera_y) == (0.0, 0.0)


def test_tile_screen_roundtrip(cam):
    cam.camera_x = 300.0
    cam.camera_y = 200.0
    sx, sy = cam.tile_to_screen(10, 5)
    assert (sx, sy) == (10 * TILE_SIZE - 300, 5 * TILE_SIZE - 200)
    assert cam.screen_to_tile(sx, sy) == (10, 5)