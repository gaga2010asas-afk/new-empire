# src/frontend/ui_banner.py
"""
BannerPanel — панель Штандарта. Прототип №7.
Зона: src/frontend/. Логики мира нет.

Канон v1.5.10: should_render(view) — обязательный публичный метод.
Канон v1.5.17: только PANEL_BG_COLOR / PANEL_BORDER_COLOR (docs/07).
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame


# --- Канон v1.5.17: единая дизайн-система панелей (docs/07) ---
PANEL_BG_COLOR: tuple[int, int, int] = (18, 18, 18)
PANEL_BORDER_COLOR: tuple[int, int, int] = (60, 50, 30)

PANEL_W: int = 320
PANEL_H: int = 150
TEXT_COLOR: tuple[int, int, int] = (235, 220, 180)
LABEL_COLOR: tuple[int, int, int] = (170, 150, 105)
TIMER_BG: tuple[int, int, int] = (40, 40, 40)
TIMER_FG: tuple[int, int, int] = (220, 180, 60)
BAR_H: int = 10
PADDING: int = 12
LINE_HEIGHT: int = 22
FONT_SIZE_FALLBACK: int = 16

STATE_IDLE: int = 0
STATE_GATHERING: int = 1
STATE_MARCHING: int = 2
STATE_COMBAT: int = 3

STATE_LABELS: dict[int, str] = {
    STATE_IDLE: "—",
    STATE_GATHERING: "Сбор",
    STATE_MARCHING: "Марш",
    STATE_COMBAT: "Бой",
}
STATE_COLORS: dict[int, tuple[int, int, int]] = {
    STATE_IDLE: (150, 150, 150),
    STATE_GATHERING: (220, 180, 60),
    STATE_MARCHING: (90, 180, 240),
    STATE_COMBAT: (220, 60, 50),
}


@dataclass
class BannerPanelView:
    hero_name: str
    state: int
    gathered_units: int
    gathering_timer_ticks: int
    gathering_total_ticks: int
    target_region_name: str = ""


class BannerPanel:
    """Панель Штандарта."""

    def __init__(
        self,
        font: pygame.font.Font | None = None,
        x: int = 16,
        y: int = 8,
        width: int = PANEL_W,
        height: int = PANEL_H,
    ) -> None:
        self.font = font if font is not None else pygame.font.SysFont(None, FONT_SIZE_FALLBACK)
        self.rect = pygame.Rect(int(x), int(y), int(width), int(height))

    def should_render(self, view: BannerPanelView) -> bool:
        return int(view.state) != STATE_IDLE

    def render(self, surface: pygame.Surface, view: BannerPanelView) -> None:
        if not self.should_render(view):
            return

        pygame.draw.rect(surface, PANEL_BG_COLOR, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER_COLOR, self.rect, 2)

        # Заголовок отделяется линией PANEL_BORDER_COLOR (единая палитра).
        header_line_y = self.rect.y + LINE_HEIGHT + 4
        pygame.draw.line(
            surface,
            PANEL_BORDER_COLOR,
            (self.rect.x + PADDING, header_line_y),
            (self.rect.right - PADDING, header_line_y),
            1,
        )
        title = self.font.render("Поход — Штандарт", True, TEXT_COLOR)
        surface.blit(title, (self.rect.x + PADDING, self.rect.y + 6))

        y = header_line_y + 8
        y = self._row(surface, y, "Герой", view.hero_name)
        y = self._row(surface, y, "Регион", view.target_region_name or "—")
        y = self._row(surface, y, "Собрано", f"{view.gathered_units} отр.")

        label_surf = self.font.render("Фаза:", True, LABEL_COLOR)
        phase_color = STATE_COLORS.get(view.state, TEXT_COLOR)
        phase_text = STATE_LABELS.get(view.state, "—")
        phase_surf = self.font.render(phase_text, True, phase_color)
        surface.blit(label_surf, (self.rect.x + PADDING, y))
        surface.blit(phase_surf, (self.rect.x + PADDING + 100, y))
        y += LINE_HEIGHT

        timer_label = self.font.render("Выдвижение", True, LABEL_COLOR)
        surface.blit(timer_label, (self.rect.x + PADDING, y))
        secs = max(0, int(view.gathering_timer_ticks)) // 60
        secs_surf = self.font.render(f"{secs}с", True, TEXT_COLOR)
        surface.blit(secs_surf, (self.rect.right - PADDING - secs_surf.get_width(), y))
        y += LINE_HEIGHT

        bar_rect = pygame.Rect(self.rect.x + PADDING, y, self.rect.w - PADDING * 2, BAR_H)
        pygame.draw.rect(surface, TIMER_BG, bar_rect)
        if view.gathering_total_ticks > 0:
            ratio = 1.0 - (view.gathering_timer_ticks / view.gathering_total_ticks)
            ratio = max(0.0, min(1.0, ratio))
            pygame.draw.rect(
                surface, TIMER_FG,
                pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.w * ratio), bar_rect.h),
            )

    def _row(self, surface: pygame.Surface, y: int, label: str, value: str) -> int:
        label_surf = self.font.render(f"{label}:", True, LABEL_COLOR)
        value_surf = self.font.render(value, True, TEXT_COLOR)
        surface.blit(label_surf, (self.rect.x + PADDING, y))
        surface.blit(value_surf, (self.rect.x + PADDING + 100, y))
        return y + LINE_HEIGHT