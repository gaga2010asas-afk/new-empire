# src/frontend/ui_hud.py
"""
GameHUD — верхняя панель ресурсов. Прототип №2.
Зона: src/frontend/. Логики мира нет.

Канон v1.5.17: единая дизайн-система панелей (docs/07).
Канон v1.5.19: страховка pygame.font.init() в dummy-окружениях.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame


# --- Канон v1.5.17: единая дизайн-система панелей ---
PANEL_BG_COLOR: tuple[int, int, int] = (18, 18, 18)
PANEL_BORDER_COLOR: tuple[int, int, int] = (60, 50, 30)

# --- Технические дефолты ---
HUD_HEIGHT: int = 28
HUD_TEXT_COLOR: tuple[int, int, int] = (235, 220, 180)
HUD_LABEL_COLOR: tuple[int, int, int] = (170, 150, 105)
HUD_PADDING_X: int = 12
HUD_PADDING_Y: int = 4
HUD_SECTION_GAP: int = 20
FONT_SIZE_FALLBACK: int = 16


@dataclass
class HudState:
    gold: int = 0
    wood: int = 0
    oil: int = 0
    food_used: int = 0
    food_cap: int = 0


class GameHUD:
    """Верхняя полоса ресурсов."""

    def __init__(
        self,
        font: pygame.font.Font | None = None,
        height: int = HUD_HEIGHT,
        bg_color: tuple[int, int, int] = PANEL_BG_COLOR,
        text_color: tuple[int, int, int] = HUD_TEXT_COLOR,
        label_color: tuple[int, int, int] = HUD_LABEL_COLOR,
        padding_x: int = HUD_PADDING_X,
        padding_y: int = HUD_PADDING_Y,
        section_gap: int = HUD_SECTION_GAP,
    ) -> None:
        # v1.5.19: страховка font.init() для headless/dummy.
        if not pygame.font.get_init():
            pygame.font.init()
        self.font = font if font is not None else pygame.font.SysFont(None, FONT_SIZE_FALLBACK)
        self.height = int(height)
        self.bg_color = bg_color
        self.text_color = text_color
        self.label_color = label_color
        self.padding_x = int(padding_x)
        self.padding_y = int(padding_y)
        self.section_gap = int(section_gap)

    def render(self, surface: pygame.Surface, state: HudState) -> None:
        w = surface.get_width()
        pygame.draw.rect(surface, self.bg_color, pygame.Rect(0, 0, w, self.height))
        pygame.draw.line(
            surface,
            PANEL_BORDER_COLOR,
            (0, self.height - 1),
            (w, self.height - 1),
            1,
        )
        x = self.padding_x
        x = self._section(surface, x, "Золото", state.gold)
        x = self._section(surface, x, "Лес", state.wood)
        x = self._section(surface, x, "Нефть", state.oil)
        x = self._section(surface, x, "Еда", f"{state.food_used}/{state.food_cap}")

    def _section(self, surface, x, label, value) -> int:
        label_surf = self.font.render(f"{label}:", True, self.label_color)
        value_surf = self.font.render(str(value), True, self.text_color)
        y = self.padding_y
        surface.blit(label_surf, (x, y))
        x += label_surf.get_width() + 6
        surface.blit(value_surf, (x, y))
        return x + value_surf.get_width() + self.section_gap