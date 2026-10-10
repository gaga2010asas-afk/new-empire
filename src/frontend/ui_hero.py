# src/frontend/ui_hero.py
"""
HeroPanel — панель героя. Прототип №6.
Зона: src/frontend/. Логики мира нет.

Канон v1.5.9: smoothscale ЗАПРЕЩЁН в кадре; spell_rects публичное.
Канон v1.5.17: только PANEL_BG_COLOR / PANEL_BORDER_COLOR (docs/07).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame


# --- Канон v1.5.17: единая дизайн-система панелей ---
PANEL_BG_COLOR: tuple[int, int, int] = (18, 18, 18)
PANEL_BORDER_COLOR: tuple[int, int, int] = (60, 50, 30)

PANEL_W: int = 320
PANEL_H: int = 180
TEXT_COLOR: tuple[int, int, int] = (235, 220, 180)
LABEL_COLOR: tuple[int, int, int] = (170, 150, 105)
XP_BAR_BG: tuple[int, int, int] = (40, 40, 40)
XP_BAR_FG: tuple[int, int, int] = (200, 170, 60)
MANA_BAR_BG: tuple[int, int, int] = (30, 30, 60)
MANA_BAR_FG: tuple[int, int, int] = (80, 130, 220)
BAR_H: int = 10
PADDING: int = 12
LINE_HEIGHT: int = 22
SPELL_ICON: int = 32
SPELL_GAP: int = 6
FONT_SIZE_FALLBACK: int = 16


@dataclass
class HeroPanelView:
    hero_id: int
    name: str
    hero_level: int
    xp: int
    xp_to_next: int
    mana: int
    max_mana: int
    spells: list[str] = field(default_factory=list)
    faction: str = "human"


class HeroPanel:
    """Панель выделенного героя."""

    def __init__(
        self,
        font: pygame.font.Font | None = None,
        x: int = 16,
        y: int = 220,
        width: int = PANEL_W,
        height: int = PANEL_H,
        spell_icon_size: int = SPELL_ICON,
    ) -> None:
        self.font = font if font is not None else pygame.font.SysFont(None, FONT_SIZE_FALLBACK)
        self.rect = pygame.Rect(int(x), int(y), int(width), int(height))
        self.spell_icon_size: int = int(spell_icon_size)
        self.spell_rects: list[tuple[pygame.Rect, str]] = []
        self._icon_cache: dict[tuple[int, int], tuple[pygame.Surface, pygame.Surface]] = {}

    def _scaled_icon(self, source: pygame.Surface, target: int) -> pygame.Surface:
        key = (id(source), int(target))
        cached = self._icon_cache.get(key)
        if cached is not None and cached[0] is source:
            return cached[1]
        scaled = pygame.transform.smoothscale(source, (target, target))
        self._icon_cache[key] = (source, scaled)
        return scaled

    def render(
        self,
        surface: pygame.Surface,
        view: HeroPanelView,
        spell_icons: dict[str, pygame.Surface] | None = None,
    ) -> None:
        pygame.draw.rect(surface, PANEL_BG_COLOR, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER_COLOR, self.rect, 2)

        header_line_y = self.rect.y + LINE_HEIGHT + 4
        pygame.draw.line(
            surface,
            PANEL_BORDER_COLOR,
            (self.rect.x + PADDING, header_line_y),
            (self.rect.right - PADDING, header_line_y),
            1,
        )
        title = self.font.render(f"{view.name}  ·  ур. {view.hero_level}", True, TEXT_COLOR)
        surface.blit(title, (self.rect.x + PADDING, self.rect.y + 6))

        y = header_line_y + 8

        xp_label = self.font.render("Опыт", True, LABEL_COLOR)
        surface.blit(xp_label, (self.rect.x + PADDING, y))
        xp_rect = pygame.Rect(self.rect.x + PADDING + 60, y + 2, self.rect.w - PADDING * 2 - 60, BAR_H)
        self._bar(surface, xp_rect, view.xp, view.xp_to_next, XP_BAR_BG, XP_BAR_FG)

        y += LINE_HEIGHT
        mana_label = self.font.render("Мана", True, LABEL_COLOR)
        surface.blit(mana_label, (self.rect.x + PADDING, y))
        mana_rect = pygame.Rect(self.rect.x + PADDING + 60, y + 2, self.rect.w - PADDING * 2 - 60, BAR_H)
        self._bar(surface, mana_rect, view.mana, max(1, view.max_mana), MANA_BAR_BG, MANA_BAR_FG)

        y += LINE_HEIGHT + 4
        self.spell_rects.clear()
        sx = self.rect.x + PADDING
        icon_size = self.spell_icon_size
        for key in view.spells:
            icon_rect = pygame.Rect(sx, y, icon_size, icon_size)
            source = spell_icons.get(key) if spell_icons else None
            if source is not None:
                scaled = self._scaled_icon(source, icon_size)
                surface.blit(scaled, icon_rect)
            else:
                pygame.draw.rect(surface, PANEL_BORDER_COLOR, icon_rect, 1)
                pygame.draw.line(surface, LABEL_COLOR, icon_rect.topleft, icon_rect.bottomright, 1)
                pygame.draw.line(surface, LABEL_COLOR, icon_rect.topright, icon_rect.bottomleft, 1)
            self.spell_rects.append((icon_rect, key))
            sx += icon_size + SPELL_GAP

    def _bar(self, surface, rect: pygame.Rect, value: int, cap: int, bg, fg) -> None:
        pygame.draw.rect(surface, bg, rect)
        if cap <= 0:
            return
        ratio = max(0.0, min(1.0, value / cap))
        pygame.draw.rect(surface, fg, pygame.Rect(rect.x, rect.y, int(rect.w * ratio), rect.h))

    def spell_at(self, pos: tuple[int, int]) -> str | None:
        for rect, key in self.spell_rects:
            if rect.collidepoint(pos):
                return key
        return None