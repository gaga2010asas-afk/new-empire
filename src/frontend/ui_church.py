# src/frontend/ui_church.py
"""
ChurchPanel — панель Церкви. Прототип №6.
Зона: src/frontend/. Логики мира нет.

Канон v1.5.9: hover актуализируется каждый кадр через pygame.mouse.get_pos().
Канон v1.5.17: только PANEL_BG_COLOR / PANEL_BORDER_COLOR (docs/07).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame


# --- Канон v1.5.17: единая дизайн-система панелей ---
PANEL_BG_COLOR: tuple[int, int, int] = (18, 18, 18)
PANEL_BORDER_COLOR: tuple[int, int, int] = (60, 50, 30)

PANEL_W: int = 360
PANEL_H: int = 220
TEXT_COLOR: tuple[int, int, int] = (235, 220, 180)
LABEL_COLOR: tuple[int, int, int] = (170, 150, 105)
BAR_BG: tuple[int, int, int] = (40, 40, 40)
BAR_GOLD: tuple[int, int, int] = (215, 180, 60)
BAR_H: int = 12
PADDING: int = 12
LINE_HEIGHT: int = 22
BUTTON_H: int = 28
BUTTON_BG: tuple[int, int, int] = (60, 45, 20)
BUTTON_BG_HOVER: tuple[int, int, int] = (90, 70, 30)
BUTTON_BORDER: tuple[int, int, int] = (140, 110, 60)
FONT_SIZE_FALLBACK: int = 16
DONATE_STEP: int = 100


@dataclass
class ChurchPanelView:
    target_gold: int = 500
    contribution_pool: int = 0
    cooldown_ticks_left: int = 0
    cooldown_ticks_total: int = 180 * 60
    dead_heroes: list[str] = field(default_factory=list)
    player_gold: int = 0


class ChurchPanel:
    """Панель Церкви."""

    def __init__(
        self,
        font: pygame.font.Font | None = None,
        x: int = 16,
        y: int = 220,
        width: int = PANEL_W,
        height: int = PANEL_H,
    ) -> None:
        self.font = font if font is not None else pygame.font.SysFont(None, FONT_SIZE_FALLBACK)
        self.rect = pygame.Rect(int(x), int(y), int(width), int(height))
        self.donate_rect = pygame.Rect(
            self.rect.x + PADDING,
            self.rect.bottom - PADDING - BUTTON_H,
            self.rect.w - PADDING * 2,
            BUTTON_H,
        )
        self._hover = False

    def handle_event(self, event: pygame.event.Event, view: ChurchPanelView) -> int:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.donate_rect.collidepoint(event.pos)
            return 0
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.donate_rect.collidepoint(event.pos) and view.player_gold > 0:
                needed = max(0, view.target_gold - view.contribution_pool)
                if needed <= 0:
                    return 0
                return min(DONATE_STEP, view.player_gold, needed)
        return 0

    def render(self, surface: pygame.Surface, view: ChurchPanelView) -> None:
        self._hover = self.donate_rect.collidepoint(pygame.mouse.get_pos())

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
        title = self.font.render("Церковь — Возрождение героев", True, TEXT_COLOR)
        surface.blit(title, (self.rect.x + PADDING, self.rect.y + 6))

        y = header_line_y + 8

        if view.dead_heroes:
            dead_label = self.font.render("Павшие: " + ", ".join(view.dead_heroes), True, LABEL_COLOR)
            surface.blit(dead_label, (self.rect.x + PADDING, y))
            y += LINE_HEIGHT
        else:
            empty = self.font.render("Павших героев нет", True, LABEL_COLOR)
            surface.blit(empty, (self.rect.x + PADDING, y))
            y += LINE_HEIGHT

        cd_left = max(0, int(view.cooldown_ticks_left)) // 60
        cd_total = max(1, int(view.cooldown_ticks_total)) // 60
        cd_surf = self.font.render(f"Кулдаун: {cd_left}с / {cd_total}с", True, TEXT_COLOR)
        surface.blit(cd_surf, (self.rect.x + PADDING, y))
        y += LINE_HEIGHT

        pool_label = self.font.render(
            f"Складчина: {view.contribution_pool} / {view.target_gold}",
            True, TEXT_COLOR,
        )
        surface.blit(pool_label, (self.rect.x + PADDING, y))
        y += LINE_HEIGHT

        bar_rect = pygame.Rect(self.rect.x + PADDING, y, self.rect.w - PADDING * 2, BAR_H)
        pygame.draw.rect(surface, BAR_BG, bar_rect)
        if view.target_gold > 0:
            ratio = max(0.0, min(1.0, view.contribution_pool / view.target_gold))
            pygame.draw.rect(
                surface, BAR_GOLD,
                pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.w * ratio), bar_rect.h),
            )

        btn_bg = BUTTON_BG_HOVER if self._hover else BUTTON_BG
        pygame.draw.rect(surface, btn_bg, self.donate_rect)
        pygame.draw.rect(surface, BUTTON_BORDER, self.donate_rect, 2)
        btn_text = self.font.render(f"Внести золото (+{DONATE_STEP})", True, TEXT_COLOR)
        tx = self.donate_rect.centerx - btn_text.get_width() // 2
        ty = self.donate_rect.centery - btn_text.get_height() // 2
        surface.blit(btn_text, (tx, ty))