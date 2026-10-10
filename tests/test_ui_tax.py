import pygame
import pytest

from src.frontend.ui_tax import (
    TaxPanel,
    TAX_MIN,
    TAX_MAX,
)


@pytest.fixture
def panel():
    return TaxPanel(x=0, y=0, width=360, height=56, initial_percent=30)


def test_initial_percent_kept(panel):
    assert panel.get_percent() == 30


def test_set_percent_clamped_high(panel):
    panel.set_percent(999)
    assert panel.get_percent() == TAX_MAX


def test_set_percent_clamped_low(panel):
    panel.set_percent(-50)
    assert panel.get_percent() == TAX_MIN


def test_click_at_track_left_sets_near_zero(panel):
    track = panel._track_rect
    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (track.x, track.centery), "button": 1}
    )
    changed = panel.handle_event(ev)
    assert changed is True
    assert panel.get_percent() == TAX_MIN


def test_click_at_track_right_sets_max(panel):
    track = panel._track_rect
    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (track.right, track.centery), "button": 1}
    )
    panel.handle_event(ev)
    assert panel.get_percent() == TAX_MAX


def test_drag_updates_percent(panel):
    track = panel._track_rect
    panel.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": (track.x, track.centery), "button": 1}
        )
    )
    mid_x = track.x + track.w // 2
    panel.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, {"pos": (mid_x, track.centery)})
    )
    # Ожидаем около 50% с допуском ±3.
    assert abs(panel.get_percent() - 50) <= 3


def test_click_outside_panel_does_nothing(panel):
    before = panel.get_percent()
    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (5000, 5000), "button": 1}
    )
    changed = panel.handle_event(ev)
    assert changed is False
    assert panel.get_percent() == before


def test_render_does_not_crash(panel):
    surf = pygame.Surface((800, 600))
    panel.render(surf)
    assert surf.get_at((panel.rect.x, panel.rect.y)) == pygame.Color(*panel.rect  # smoke
        and (18, 18, 18))