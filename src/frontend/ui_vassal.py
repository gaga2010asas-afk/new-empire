# src/frontend/ui_vassal.py
"""
VassalPanel — панель вассала. Прототип №5.
Зона: src/frontend/. Логики мира нет.

Канон v1.5 §1: стейты FREE / ENCIRCLED / BREAKTHROUGH.
Канон v1.5 §2: тип колонии central / mid / border.
Канон v1.5.7: close_rect публичный.
Канон v1.5.16 №6: единая дизайн-система панелей.

[НЕТ ДАННЫХ]:
- Позиция панели — технический дефолт.
- Оригинальный шрифт WC2 передаётся снаружи.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame


# --- Канон v1.5.16 №6: единая дизайн-система панелей ---
PANEL_BG_COLOR: tuple[int, int, int] = (18, 18, 18)
PANEL_BORDER_COLOR: tuple[int, int, int] = (60, 50, 30)

# --- Технические дефолты (не панельные цвета) ---
PANEL_W: int = 380
PANEL_H: int = 200
PANEL_X: int = 16
PANEL_Y: int = 440
PANEL_TITLE_BG: tuple[int, int, int] = (40, 30, 15)
TEXT_COLOR: tuple[int, int, int] = (235, 220, 180)
LABEL_COLOR: tuple[int, int, int] = (170, 150, 105)
PADDING: int = 12
LINE_HEIGHT: int = 22
FONT_SIZE_FALLBACK: int = 16
CLOSE_SIZE: int = 18

STATE_COLORS: dict[str, tuple[int, int, int]] = {
    "FREE":          (80, 200, 90),
    "ENCIRCLED":     (230, 170, 60),
    "BREAKTHROUGH":  (220, 60, 50),
}
STATE_LABELS: dict[str, str] = {
    "FREE": "Норма",
    "ENCIRCLED": "В блокаде",
    "BREAKTHROUGH": "Прорыв",
}
COLONY_TYPE_LABELS: dict[str, str] = {
    "central": "Центральная",
    "mid": "Средняя",
    "border": "Пограничная",
}


@dataclass
class VassalPanelView:
    vassal_id: int
    colony_type: str
    treasury_gold: int
    treasury_wood: int
    mobilization_percent: int
    state: str
    colony_name: str = ""


class VassalPanel:
    """Панель выбранной колонии вассала."""

    def __init__(
        self,
        font: pygame.font.Font | None = None,
        x: int = PANEL_X,
        y: int = PANEL_Y,
        width: int = PANEL_W,
        height: int = PANEL_H,
    ) -> None:
        self.font = font if font is not None else pygame.font.SysFont(None, FONT_SIZE_FALLBACK)
        self.rect = pygame.Rect(int(x), int(y), int(width), int(height))
        self.close_rect = pygame.Rect(
            self.rect.right - CLOSE_SIZE - 6,
            self.rect.y + 6,
            CLOSE_SIZE,
            CLOSE_SIZE,
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                return True
        return False

    def render(self, surface: pygame.Surface, view: VassalPanelView) -> None:
        pygame.draw.rect(surface, PANEL_BG_COLOR, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER_COLOR, self.rect, 2)

        title_rect = pygame.Rect(self.rect.x, self.rect.y, self.rect.w, LINE_HEIGHT + 6)
        pygame.draw.rect(surface, PANEL_TITLE_BG, title_rect)
        type_label = COLONY_TYPE_LABELS.get(view.colony_type, view.colony_type)
        name = view.colony_name or f"Колония #{view.vassal_id}"
        title = self.font.render(f"{name} [{type_label}]", True, TEXT_COLOR)
        surface.blit(title, (self.rect.x + PADDING, self.rect.y + 6))

        pygame.draw.rect(surface, PANEL_BORDER_COLOR, self.close_rect, 1)
        cx, cy = self.close_rect.center
        pygame.draw.line(surface, TEXT_COLOR, (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
        pygame.draw.line(surface, TEXT_COLOR, (cx + 5, cy - 5), (cx - 5, cy + 5), 2)

        y = self.rect.y + LINE_HEIGHT + 14
        y = self._row(surface, y, "Казна (золото)", str(view.treasury_gold))
        y = self._row(surface, y, "Казна (лес)", str(view.treasury_wood))
        y = self._row(surface, y, "Мобилизация", f"{view.mobilization_percent}%")

        state_label = STATE_LABELS.get(view.state, view.state)
        state_color = STATE_COLORS.get(view.state, TEXT_COLOR)
        label_surf = self.font.render("Стейт:", True, LABEL_COLOR)
        value_surf = self.font.render(state_label, True, state_color)
        surface.blit(label_surf, (self.rect.x + PADDING, y))
        surface.blit(value_surf, (self.rect.x + PADDING + 90, y))

    def _row(self, surface: pygame.Surface, y: int, label: str, value: str) -> int:
        label_surf = self.font.render(f"{label}:", True, LABEL_COLOR)
        value_surf = self.font.render(value, True, TEXT_COLOR)
        surface.blit(label_surf, (self.rect.x + PADDING, y))
        surface.blit(value_surf, (self.rect.x + PADDING + 180, y))
        return y + LINE_HEIGHT