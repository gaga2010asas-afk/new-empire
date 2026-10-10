import pygame
import pytest

from src.frontend.camera import Camera, TILE_SIZE
from src.frontend.cursors import (
    CursorRenderer,
    CURSOR_NORMAL,
    CURSOR_ATTACK,
)


class FakeMap:
    def __init__(self, w, h):
        self.width = w
        self.height = h
        self._cells = {}

    def set(self, layer, x, y, idx):
        self._cells[(layer, x, y)] = idx

    def get_tile_at(self, layer, x, y):
        return self._cells.get((layer, x, y), -1)


class FakeAssets:
    def __init__(self):
        self.cursors = {
            CURSOR_NORMAL: pygame.Surface((16, 16), pygame.SRCALPHA),
            CURSOR_ATTACK: pygame.Surface((16, 16), pygame.SRCALPHA),
        }
        self.cursors[CURSOR_NORMAL].fill((255, 210, 70, 255))
        self.cursors[CURSOR_ATTACK].fill((220, 30, 30, 255))

    def get_cursor(self, key):
        return self.cursors.get(key)


@pytest.fixture
def cam():
    return Camera(1024, 768)


def test_pick_cursor_normal_on_empty_layer2(cam):
    m = FakeMap(64, 64)
    cr = CursorRenderer()
    assert cr.pick_cursor_key(m, 5, 5) == CURSOR_NORMAL


def test_pick_cursor_attack_on_layer2(cam):
    m = FakeMap(64, 64)
    m.set(2, 5, 5, 42)  # скалы/лес
    cr = CursorRenderer()
    assert cr.pick_cursor_key(m, 5, 5) == CURSOR_ATTACK


def test_render_blits_cursor_at_mouse_pos(cam):
    m = FakeMap(64, 64)
    a = FakeAssets()
    cr = CursorRenderer()
    surf = pygame.Surface((1024, 768))
    surf.fill((0, 0, 0))
    cr.render(surf, (200, 150), m, cam, a)
    # Проверяем пиксель под курсором (курсор 16x16, залит золотым).
    px = surf.get_at((200, 150))
    assert px.r > 200 and px.g > 150


def test_render_fallback_when_cursor_missing(cam):
    m = FakeMap(64, 64)
    a = FakeAssets()
    a.cursors = {}  # нет PNG
    cr = CursorRenderer()
    surf = pygame.Surface((1024, 768))
    surf.fill((0, 0, 0))
    cr.render(surf, (100, 100), m, cam, a)
    # Fallback что-то нарисовал — пиксель изменился.
    assert surf.get_at((100, 100)) != pygame.Color(0, 0, 0, 255)


def test_render_switches_to_attack_cursor(cam):
    m = FakeMap(64, 64)
    # Мышь в мировых координатах (200, 150) → тайл (1, 1).
    m.set(2, 1, 1, 7)
    a = FakeAssets()
    cr = CursorRenderer()
    surf = pygame.Surface((1024, 768))
    surf.fill((0, 0, 0))
    cr.render(surf, (200, 150), m, cam, a)
    px = surf.get_at((200, 150))
    assert px.r > 180 and px.g < 100  # красный