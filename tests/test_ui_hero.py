import pygame
import pytest

from src.frontend.ui_hero import HeroPanel, HeroPanelView, SPELL_ICON


@pytest.fixture(autouse=True, scope="module")
def _display():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


@pytest.fixture
def panel():
    return HeroPanel(x=0, y=0, width=320, height=180)


def _view(**kw):
    base = dict(
        hero_id=1, name="Паладин", hero_level=3,
        xp=50, xp_to_next=200, mana=40, max_mana=100,
        spells=["healing", "holy_vision"],
        faction="human",
    )
    base.update(kw)
    return HeroPanelView(**base)


def test_render_draws_panel_background(panel):
    surf = pygame.Surface((1024, 768))
    surf.fill((255, 255, 255))
    panel.render(surf, _view())
    assert surf.get_at((2, 2)) == pygame.Color(*(18, 18, 18))


def test_spells_render_as_placeholders_without_icons(panel):
    surf = pygame.Surface((1024, 768))
    panel.render(surf, _view())
    assert len(panel.spell_rects) == 2


def test_spell_rects_is_public_attribute(panel):
    """v1.5.9: spell_rects — публичное поле."""
    assert hasattr(panel, "spell_rects")
    assert not hasattr(panel, "_spell_rects")


def test_spell_at_returns_key_for_clicked_icon(panel):
    surf = pygame.Surface((1024, 768))
    panel.render(surf, _view())
    rect, key = panel.spell_rects[0]
    assert panel.spell_at(rect.center) == key


def test_spell_at_returns_none_outside_icons(panel):
    surf = pygame.Surface((1024, 768))
    panel.render(surf, _view())
    assert panel.spell_at((0, 0)) is None


def test_icon_scaled_once_and_cached(panel):
    """v1.5.9: smoothscale — только один раз на (источник, размер)."""
    src = pygame.Surface((64, 64), pygame.SRCALPHA)
    src.fill((200, 100, 50, 255))
    s1 = panel._scaled_icon(src, SPELL_ICON)
    s2 = panel._scaled_icon(src, SPELL_ICON)
    assert s1 is s2
    assert s1.get_size() == (SPELL_ICON, SPELL_ICON)


def test_icon_source_not_mutated(panel):
    src = pygame.Surface((64, 64), pygame.SRCALPHA)
    src.fill((200, 100, 50, 255))
    before = pygame.image.tobytes(src, "RGBA")
    panel._scaled_icon(src, SPELL_ICON)
    assert pygame.image.tobytes(src, "RGBA") == before


def test_render_with_icons_uses_cached_scaled(panel):
    surf = pygame.Surface((1024, 768))
    icons = {
        "healing": pygame.Surface((64, 64), pygame.SRCALPHA),
        "holy_vision": pygame.Surface((48, 48), pygame.SRCALPHA),
    }
    icons["healing"].fill((200, 100, 50, 255))
    icons["holy_vision"].fill((50, 200, 100, 255))

    panel.render(surf, _view(), spell_icons=icons)
    first_cache_size = len(panel._icon_cache)
    # Второй кадр — новых поверхностей не создаётся.
    panel.render(surf, _view(), spell_icons=icons)
    assert len(panel._icon_cache) == first_cache_size


def test_bar_renders_zero_cap_without_crash(panel):
    surf = pygame.Surface((1024, 768))
    panel.render(surf, _view(xp=0, xp_to_next=0))