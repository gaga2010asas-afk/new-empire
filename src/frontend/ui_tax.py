# src/frontend/ui_tax.py
"""
TaxPanel — панель глобального налога. Прототип №3.
Зона: src/frontend/. Логики мира нет.

Канон v1.5.17: единая дизайн-система панелей (docs/07).
Канон v1.5.19: страховка pygame.font.init() в dummy-окружениях.
Канон v1.5.21: клик в правом краю трека даёт TAX_MAX (100%).
Канон v1.5.23: заливка PANEL_BG_COLOR, затем рамка PANEL_BORDER_COLOR width=2.
Канон (визуальный фикс): шрифт 22, PADDING 14, высота панели 64 —
               текст читается без лупы.
"""

from __future__ import annotations

import pygame


# --- Канон v1.5.17/23: единая дизайн-система панелей ---
PANEL_BG_COLOR: tuple[int, int, int] = (18, 18, 18)
PANEL_BORDER_COLOR: tuple[int, int, int] = (60, 50, 30)

# --- Технические дефолты ---
TAX_MIN: int = 0
TAX_MAX: int = 100
PANEL_W: int = 420
PANEL_H: int = 64
TRACK_H: int = 14
TRACK_BG: tuple[int, int, int] = (40, 40, 40)
TRACK_FG: tuple[int, int, int] = (180, 140, 60)
KNOB_R: int = 12
KNOB_COLOR: tuple[int, int, int] = (230, 200, 120)
KNOB_OUTLINE: tuple[int, int, int] = (60, 40, 10)
TEXT_COLOR: tuple[int, int, int] = (235, 220, 180)
PADDING: int = 14
FONT_SIZE_FALLBACK: int = 22


class TaxPanel:
    """Ползунок налога 0–100%."""

    def __init__(
        self,
        font: pygame.font.Font | None = None,
        x: int = 16,
        y: int = 680,
        width: int = PANEL_W,
        height: int = PANEL_H,
        initial_percent: int = 30,
    ) -> None:
        if not pygame.font.get_init():
            pygame.font.init()
        self.font = font if font is not None else pygame.font.SysFont(None, FONT_SIZE_FALLBACK)
        self.rect = pygame.Rect(int(x), int(y), int(width), int(height))
        self._percent = int(max(TAX_MIN, min(TAX_MAX, initial_percent)))
        self._dragging = False
        self._track_rect = pygame.Rect(
            self.rect.x + PADDING,
            self.rect.y + self.rect.h - PADDING - TRACK_H,
            self.rect.w - PADDING * 2,
            TRACK_H,
        )

    # --- доступ ---------------------------------------------------------------
    def get_percent(self) -> int:
        return self._percent

    def set_percent(self, value: int) -> None:
        self._percent = int(max(TAX_MIN, min(TAX_MAX, value)))

    @property
    def current_tax_percent(self) -> int:
        return self._percent

    @current_tax_percent.setter
    def current_tax_percent(self, value: int) -> None:
        self.set_percent(value)

    # --- ввод -----------------------------------------------------------------
    def _is_on_track(self, pos: tuple[int, int]) -> bool:
        x, y = pos
        if y < self._track_rect.y or y > self._track_rect.bottom:
            return False
        return (
            (self._track_rect.x - KNOB_R) <= x
            <= (self._track_rect.right + KNOB_R)
        )

    def _pos_on_knob(self, pos: tuple[int, int]) -> bool:
        return self._knob_rect().collidepoint(pos)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._pos_on_knob(event.pos) or self._is_on_track(event.pos):
                self._dragging = True
                return self._apply_mouse_x(event.pos[0])
            return False

        if event.type == pygame.MOUSEMOTION and self._dragging:
            return self._apply_mouse_x(event.pos[0])

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was = self._dragging
            self._dragging = False
            return was and False

        return False

    def _apply_mouse_x(self, mouse_x: int) -> bool:
        x0 = self._track_rect.x
        w = self._track_rect.width
        if w <= 0:
            return False
        ratio = (int(mouse_x) - x0) / w
        ratio = max(0.0, min(1.0, ratio))
        new_val = int(round(TAX_MIN + ratio * (TAX_MAX - TAX_MIN)))
        new_val = max(TAX_MIN, min(TAX_MAX, new_val))
        changed = new_val != self._percent
        self._percent = new_val
        return changed

    def _knob_rect(self) -> pygame.Rect:
        x0 = self._track_rect.x
        x1 = self._track_rect.right
        ratio = (self._percent - TAX_MIN) / max(1, (TAX_MAX - TAX_MIN))
        cx = int(x0 + ratio * (x1 - x0))
        cy = self._track_rect.centery
        return pygame.Rect(cx - KNOB_R, cy - KNOB_R, KNOB_R * 2, KNOB_R * 2)

    # --- отрисовка ------------------------------------------------------------
    def render(self, surface: pygame.Surface) -> None:
        # v1.5.23: СНАЧАЛА заливка фона, ЗАТЕМ рамка width=2.
        pygame.draw.rect(surface, PANEL_BG_COLOR, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER_COLOR, self.rect, width=2)

        label = self.font.render("Налог:", True, TEXT_COLOR)
        value = self.font.render(f"{self._percent}%", True, TEXT_COLOR)
        surface.blit(label, (self.rect.x + PADDING, self.rect.y + PADDING - 2))
        surface.blit(
            value,
            (self.rect.right - PADDING - value.get_width(), self.rect.y + PADDING - 2),
        )

        pygame.draw.rect(surface, TRACK_BG, self._track_rect)

        x0 = self._track_rect.x
        x1 = self._track_rect.right
        ratio = (self._percent - TAX_MIN) / max(1, (TAX_MAX - TAX_MIN))
        fill_w = int((x1 - x0) * ratio)
        if fill_w > 0:
            pygame.draw.rect(
                surface, TRACK_FG,
                pygame.Rect(x0, self._track_rect.y, fill_w, self._track_rect.h),
            )

        knob = self._knob_rect()
        pygame.draw.circle(surface, KNOB_OUTLINE, knob.center, KNOB_R + 1)
        pygame.draw.circle(surface, KNOB_COLOR, knob.center, KNOB_R)