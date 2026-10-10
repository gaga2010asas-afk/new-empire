# src/frontend/ui_caravan.py
"""
CaravanHud — индикатор буферов налога вассалов. Прототип №3.
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
HUD_X_MARGIN: int = 12
HUD_Y_MARGIN: int = 36
HUD_W: int = 260
ROW_H: int = 44
ROW_PADDING: int = 6
TEXT_COLOR: tuple[int, int, int] = (230, 215, 175)
LABEL_COLOR: tuple[int, int, int] = (170, 150, 105)
BAR_BG: tuple[int, int, int] = (40, 40, 40)
BAR_GOLD: tuple[int, int, int] = (215, 180, 60)
BAR_WOOD: tuple[int, int, int] = (140, 100, 55)
BAR_H: int = 6

ALERT_BG: tuple[int, int, int] = (120, 20, 20)
ALERT_BLINK_MS: int = 500
FONT_SIZE_FALLBACK: int = 14


@dataclass
class VassalBufferView:
    vassal_id: int
    colony_type: str
    buffer_gold: int
    buffer_wood: int
    capacity_gold: int
    capacity_wood: int
    alert: bool = False


class CaravanHud:
    """Информационное окно буферов."""

    def __init__(
        self,
        font: pygame.font.Font | None = None,
        x: int | None = None,
        y: int = HUD_Y_MARGIN,
        width: int = HUD_W,
        row_height: int = ROW_H,
    ) -> None:
        # v1.5.19: страховка font.init() для headless/dummy.
        if not pygame.font.get_init():
            pygame.font.init()
        self.font = font if font is not None else pygame.font.SysFont(None, FONT_SIZE_FALLBACK)
        self.x = x
        self.y = int(y)
        self.width = int(width)
        self.row_height = int(row_height)

    def render(
        self,
        surface: pygame.Surface,
        vassals: list[VassalBufferView],
        now_ms: int | None = None,
    ) -> None:
        if not vassals:
            return
        if now_ms is None:
            now_ms = pygame.time.get_ticks()

        x = self.x if self.x is not None else surface.get_width() - self.width - HUD_X_MARGIN
        y = self.y

        for v in vassals:
            row_rect = pygame.Rect(x, y, self.width, self.row_height)
            self._render_row(surface, row_rect, v, now_ms)
            y += self.row_height + ROW_PADDING

    def _render_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        v: VassalBufferView,
        now_ms: int,
    ) -> None:
        bg = PANEL_BG_COLOR
        if v.alert:
            phase = (now_ms // ALERT_BLINK_MS) % 2
            if phase == 0:
                bg = ALERT_BG

        pygame.draw.rect(surface, bg, rect)
        pygame.draw.rect(surface, PANEL_BORDER_COLOR, rect, 2)

        title = f"Вассал #{v.vassal_id} [{v.colony_type}]"
        title_surf = self.font.render(title, True, TEXT_COLOR)
        surface.blit(title_surf, (rect.x + 8, rect.y + 4))

        label_surf = self.font.render("буфер налога", True, LABEL_COLOR)
        surface.blit(
            label_surf,
            (rect.right - 8 - label_surf.get_width(), rect.y + 4),
        )

        bar_x = rect.x + 8
        bar_w = rect.w - 16
        bar_y = rect.y + rect.h - BAR_H - 8

        gold_ratio = self._ratio(v.buffer_gold, v.capacity_gold)
        wood_ratio = self._ratio(v.buffer_wood, v.capacity_wood)

        gold_rect = pygame.Rect(bar_x, bar_y, bar_w, BAR_H // 2)
        wood_rect = pygame.Rect(bar_x, bar_y + BAR_H // 2, bar_w, BAR_H - BAR_H // 2)
        pygame.draw.rect(surface, BAR_BG, gold_rect)
        pygame.draw.rect(surface, BAR_BG, wood_rect)
        pygame.draw.rect(
            surface, BAR_GOLD,
            pygame.Rect(gold_rect.x, gold_rect.y, int(gold_rect.w * gold_ratio), gold_rect.h),
        )
        pygame.draw.rect(
            surface, BAR_WOOD,
            pygame.Rect(wood_rect.x, wood_rect.y, int(wood_rect.w * wood_ratio), wood_rect.h),
        )

    @staticmethod
    def _ratio(value: int, capacity: int) -> float:
        if capacity <= 0:
            return 0.0
        return max(0.0, min(1.0, value / capacity))