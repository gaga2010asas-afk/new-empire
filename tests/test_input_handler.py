import pygame
import pytest

from src.frontend.input_handler import (
    InputHandler,
    MenuAction,
    GameAction,
)


@pytest.fixture(autouse=True, scope="module")
def _display():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


def _key(code):
    return pygame.event.Event(pygame.KEYDOWN, {"key": code})


def _mousedown(button, pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": button, "pos": pos})


def _mouseup(button, pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": button, "pos": pos})


# --- Меню -------------------------------------------------------------------

def test_menu_enter_triggers_new_game():
    ih = InputHandler()
    assert ih.handle_menu_event(_key(pygame.K_RETURN)) == MenuAction.NEW_GAME


def test_menu_escape_triggers_quit():
    ih = InputHandler()
    assert ih.handle_menu_event(_key(pygame.K_ESCAPE)) == MenuAction.QUIT


def test_menu_unrelated_event_is_none():
    ih = InputHandler()
    ev = pygame.event.Event(pygame.MOUSEMOTION, {"pos": (10, 10)})
    assert ih.handle_menu_event(ev) == MenuAction.NONE


# --- Игра -------------------------------------------------------------------

def test_game_space_is_pause_toggle():
    ih = InputHandler()
    assert ih.handle_game_event(_key(pygame.K_SPACE)) == GameAction.PAUSE_TOGGLE


def test_game_escape_is_cancel():
    ih = InputHandler()
    assert ih.handle_game_event(_key(pygame.K_ESCAPE)) == GameAction.CANCEL


def test_game_left_click_starts_and_ends_selection_box():
    ih = InputHandler()
    assert ih.handle_game_event(_mousedown(1, (100, 100))) == GameAction.LEFT_CLICK
    assert ih.selection_box_start == (100, 100)
    assert ih.handle_game_event(_mouseup(1, (200, 200))) == GameAction.SELECTION_BOX_END
    assert ih.selection_box_end == (200, 200)
    assert ih.selection_box_start is None


def test_game_right_click_returned():
    ih = InputHandler()
    assert ih.handle_game_event(_mousedown(3, (400, 300))) == GameAction.RIGHT_CLICK


def test_game_left_click_without_start_no_selection_box_end():
    """MOUSEBUTTONUP без предшествующего DOWN — NONE, не «фантомный» box."""
    ih = InputHandler()
    assert ih.handle_game_event(_mouseup(1, (200, 200))) == GameAction.NONE


def test_get_camera_input_center_is_zero():
    """Без нажатых клавиш — (0, 0)."""
    ih = InputHandler()
    assert ih.get_camera_input() == (0, 0)


def test_camera_keys_constant_contains_wasd_and_arrows():
    from src.frontend.input_handler import CAMERA_KEYS
    for code in (pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s,
                 pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
        assert code in CAMERA_KEYS


# --- Абстрактные действия (v1.5.13 §2) ---------------------------------------

def test_menu_actions_are_enum_values():
    assert MenuAction.NEW_GAME.value == 1
    assert MenuAction.LOAD_GAME.value == 2
    assert MenuAction.MAP_EDITOR.value == 3
    assert MenuAction.QUIT.value == 4


def test_game_actions_are_enum_values():
    assert GameAction.PAUSE_TOGGLE.value == 1
    assert GameAction.LEFT_CLICK.value == 4
    assert GameAction.RIGHT_CLICK.value == 5