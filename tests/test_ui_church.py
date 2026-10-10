import pygame
import pytest

from src.frontend.ui_church import ChurchPanel, ChurchPanelView, DONATE_STEP


@pytest.fixture(autouse=True, scope="module")
def _display():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


@pytest.fixture
def panel():
    return ChurchPanel(x=0, y=0, width=360, height=220)


def _view(**kw):
    base = dict(
        target_gold=500, contribution_pool=100,
        cooldown_ticks_left=180 * 30,
        cooldown_ticks_total=180 * 60,
        dead_heroes=["Паладин", "Маг"],
        player_gold=1000,
    )
    base.update(kw)
    return ChurchPanelView(**base)


def test_render_draws_panel_background(panel):
    surf = pygame.Surface((1024, 768))
    surf.fill((255, 255, 255))
    panel.render(surf, _view())
    assert surf.get_at((2, 2)) == pygame.Color(*(18, 18, 18))


def test_donate_button_returns_step(panel):
    v = _view()
    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": panel.donate_rect.center, "button": 1}
    )
    amount = panel.handle_event(ev, v)
    assert amount == DONATE_STEP


def test_donate_capped_by_needed(panel):
    v = _view(contribution_pool=460)
    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": panel.donate_rect.center, "button": 1}
    )
    assert panel.handle_event(ev, v) == 40


def test_donate_blocked_when_no_gold(panel):
    v = _view(player_gold=0)
    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": panel.donate_rect.center, "button": 1}
    )
    assert panel.handle_event(ev, v) == 0


def test_donate_blocked_when_pool_full(panel):
    v = _view(contribution_pool=500)
    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": panel.donate_rect.center, "button": 1}
    )
    assert panel.handle_event(ev, v) == 0


def test_click_outside_button_returns_zero(panel):
    v = _view()
    ev = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (9999, 9999), "button": 1}
    )
    assert panel.handle_event(ev, v) == 0


def test_hover_recomputed_each_frame(panel, monkeypatch):
    """v1.5.9: render обновляет _hover через pygame.mouse.get_pos()."""
    surf = pygame.Surface((1024, 768))

    # Мышь вне кнопки.
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    panel.render(surf, _view())
    assert panel._hover is False

    # Мышь на кнопке.
    monkeypatch.setattr(
        pygame.mouse, "get_pos", lambda: panel.donate_rect.center
    )
    panel.render(surf, _view())
    assert panel._hover is True

    # Мышь снова вне кнопки — hover снимается БЕЗ MOUSEMOTION.
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (9999, 9999))
    panel.render(surf, _view())
    assert panel._hover is False


def test_render_empty_dead_list_does_not_crash(panel):
    surf = pygame.Surface((1024, 768))
    panel.render(surf, _view(dead_heroes=[]))