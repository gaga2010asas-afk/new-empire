import pygame
import pytest

from src.frontend.ui_banner import (
    BannerPanel,
    BannerPanelView,
    STATE_LABELS,
    STATE_COLORS,
    STATE_IDLE,
    STATE_GATHERING,
    STATE_MARCHING,
    STATE_COMBAT,
)


@pytest.fixture(autouse=True, scope="module")
def _display():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


@pytest.fixture
def panel():
    return BannerPanel(x=0, y=0, width=320, height=150)


def _view(**kw):
    base = dict(
        hero_name="Паладин",
        state=STATE_GATHERING,
        gathered_units=12,
        gathering_timer_ticks=3600,
        gathering_total_ticks=3600,
        target_region_name="Северный рубеж",
    )
    base.update(kw)
    return BannerPanelView(**base)


# --- should_render (v1.5.10) -------------------------------------------------

def test_should_render_false_on_idle(panel):
    assert panel.should_render(_view(state=STATE_IDLE)) is False


def test_should_render_true_on_active_states(panel):
    for st in (STATE_GATHERING, STATE_MARCHING, STATE_COMBAT):
        assert panel.should_render(_view(state=st)) is True


def test_render_is_noop_in_idle(panel):
    """v1.5.10: render не рисует панель в IDLE."""
    surf = pygame.Surface((1024, 768))
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    panel.render(surf, _view(state=STATE_IDLE))
    assert pygame.image.tobytes(surf, "RGBA") == before


# --- базовые ---------------------------------------------------------------

def test_render_draws_panel_background(panel):
    surf = pygame.Surface((1024, 768))
    surf.fill((255, 255, 255))
    panel.render(surf, _view())
    assert surf.get_at((2, 2)) == pygame.Color(*(18, 18, 18))


def test_all_canon_states_have_labels():
    for st in (0, 1, 2, 3):
        assert st in STATE_LABELS
        assert st in STATE_COLORS


def test_gathering_state_is_yellow():
    r, g, b = STATE_COLORS[STATE_GATHERING]
    assert r > 180 and g > 140 and b < 120


def test_marching_state_is_blue():
    r, g, b = STATE_COLORS[STATE_MARCHING]
    assert b > 180 and r < 150


def test_combat_state_is_red():
    r, g, b = STATE_COLORS[STATE_COMBAT]
    assert r > 180 and g < 120


def test_render_all_active_states_does_not_crash(panel):
    surf = pygame.Surface((1024, 768))
    for st in (STATE_GATHERING, STATE_MARCHING, STATE_COMBAT, 99):
        panel.render(surf, _view(state=st))


def test_render_zero_timer_does_not_crash(panel):
    surf = pygame.Surface((1024, 768))
    panel.render(surf, _view(gathering_timer_ticks=0, gathering_total_ticks=0))


def test_timer_bar_fills_as_gathering_progresses(panel):
    surf = pygame.Surface((1024, 768))
    surf.fill((0, 0, 0))
    panel.render(surf, _view(gathering_timer_ticks=3600, gathering_total_ticks=3600))
    just_started = pygame.image.tobytes(surf, "RGBA")
    surf.fill((0, 0, 0))
    panel.render(surf, _view(gathering_timer_ticks=0, gathering_total_ticks=3600))
    finished = pygame.image.tobytes(surf, "RGBA")
    assert just_started != finished