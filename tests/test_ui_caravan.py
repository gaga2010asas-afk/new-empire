import pygame
import pytest

from src.frontend.ui_caravan import CaravanHud, VassalBufferView


def _vassal(**kw):
    base = dict(
        vassal_id=1, colony_type="central",
        buffer_gold=250, buffer_wood=100,
        capacity_gold=500, capacity_wood=500,
        alert=False,
    )
    base.update(kw)
    return VassalBufferView(**base)


@pytest.fixture
def hud():
    return CaravanHud(x=10, y=40, width=260)


def test_render_empty_list_does_not_draw(hud):
    surf = pygame.Surface((1024, 768))
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    hud.render(surf, [], now_ms=0)
    assert pygame.image.tobytes(surf, "RGBA") == before


def test_render_draws_row(hud):
    surf = pygame.Surface((1024, 768))
    surf.fill((0, 0, 0))
    hud.render(surf, [_vassal()], now_ms=0)
    # Верхний левый пиксель строки теперь фон HUD, не чёрный.
    assert surf.get_at((15, 45)) != pygame.Color(0, 0, 0, 255)


def test_alert_blinks_over_time(hud):
    surf = pygame.Surface((1024, 768))
    surf.fill((0, 0, 0))
    v = _vassal(alert=True)

    hud.render(surf, [v], now_ms=0)     # фаза 0 — тревожный фон
    c0 = surf.get_at((15, 45))
    surf.fill((0, 0, 0))
    hud.render(surf, [v], now_ms=600)   # фаза 1 — обычный фон
    c1 = surf.get_at((15, 45))
    assert c0 != c1


def test_capacity_zero_ratio_is_zero():
    assert CaravanHud._ratio(100, 0) == 0.0


def test_ratio_clamped_to_one():
    assert CaravanHud._ratio(9999, 500) == 1.0


def test_ratio_negative_value_is_zero():
    assert CaravanHud._ratio(-5, 500) == 0.0