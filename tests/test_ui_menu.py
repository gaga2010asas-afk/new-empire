import pygame
import pytest

from src.frontend.ui_menu import MainMenu, BUTTON_W, BUTTON_H
from src.frontend.input_handler import MenuAction


@pytest.fixture(autouse=True, scope="module")
def _display():
    pygame.init()
    pygame.display.set_mode((1024, 768))
    yield
    pygame.quit()


@pytest.fixture
def menu():
    return MainMenu(1024, 768)


def test_menu_has_four_canon_buttons(menu):
    labels = [b.label for b in menu.buttons]
    assert labels == ["Новая игра", "Загрузить игру", "Редактор карт", "Выход"]


def test_load_button_disabled_by_default(menu):
    load = next(b for b in menu.buttons if b.action == MenuAction.LOAD_GAME)
    assert load.enabled is False


def test_set_load_enabled(menu):
    menu.set_load_enabled(True)
    load = next(b for b in menu.buttons if b.action == MenuAction.LOAD_GAME)
    assert load.enabled is True


def test_click_new_game_returns_action(menu):
    new = next(b for b in menu.buttons if b.action == MenuAction.NEW_GAME)
    assert menu.handle_click(new.rect.center) == MenuAction.NEW_GAME


def test_click_disabled_load_returns_none(menu):
    load = next(b for b in menu.buttons if b.action == MenuAction.LOAD_GAME)
    assert menu.handle_click(load.rect.center) == MenuAction.NONE


def test_click_outside_buttons_returns_none(menu):
    assert menu.handle_click((0, 0)) == MenuAction.NONE


def test_click_quit_returns_quit(menu):
    quit_btn = next(b for b in menu.buttons if b.action == MenuAction.QUIT)
    assert menu.handle_click(quit_btn.rect.center) == MenuAction.QUIT


def test_render_fills_background(menu):
    surf = pygame.Surface((1024, 768))
    surf.fill((255, 255, 255))
    menu.render(surf)
    # v1.5.17: PANEL_BG_COLOR = (18, 18, 18)
    assert surf.get_at((0, 0)) == pygame.Color(18, 18, 18)


def test_render_does_not_crash_when_no_mouse(menu):
    surf = pygame.Surface((1024, 768))
    menu.render(surf)


def test_buttons_are_vertically_stacked(menu):
    ys = [b.rect.y for b in menu.buttons]
    assert ys == sorted(ys)
    for i in range(len(ys) - 1):
        assert menu.buttons[i + 1].rect.y >= menu.buttons[i].rect.bottom


def test_buttons_use_panel_border_color(menu):
    """v1.5.17: рамка кнопок — PANEL_BORDER_COLOR (60, 50, 30)."""
    from src.frontend.ui_menu import PANEL_BORDER_COLOR
    assert PANEL_BORDER_COLOR == (60, 50, 30)


def test_buttons_use_panel_bg_color(menu):
    """v1.5.17: фон кнопок по умолчанию — PANEL_BG_COLOR (18, 18, 18)."""
    from src.frontend.ui_menu import BTN_BG
    assert BTN_BG == (18, 18, 18)