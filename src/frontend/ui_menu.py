# src/frontend/ui_menu.py
"""
MainMenu — главный экран. Прототип №8.
Зона: src/frontend/. Логики мира нет.

Канон v1.5.17: только PANEL_BG_COLOR / PANEL_BORDER_COLOR (docs/07).
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from .input_handler import MenuAction


# --- Канон v1.5.17: единая дизайн-система панелей ---
PANEL_BG_COLOR: tuple[int, int, int] = (18, 18, 18)
PANEL_BORDER_COLOR: tuple[int, int, int] = (60, 50, 30)

# --- Технические дефолты ---
TITLE_COLOR: tuple[int, int, int] = (220, 180, 60)
TITLE_SHADOW: tuple[int, int, int] = (60, 30, 0)
BTN_BG: tuple[int, int, int] = PANEL_BG_COLOR
BTN_BG_HOVER: tuple[int, int, int] = PANEL_BORDER_COLOR
BTN_BG_DISABLED: tuple[int, int, int] = (24, 24, 24)
BTN_BORDER: tuple[int, int, int] = PANEL_BORDER_COLOR
BTN_TEXT: tuple[int, int, int] = (235, 220, 180)
BTN_TEXT_DISABLED: tuple[int, int, int] = (100, 100, 100)

TITLE_FONT_SIZE: int = 64
BUTTON_FONT_SIZE: int = 24
BUTTON_W: int = 300
BUTTON_H: int = 48
BUTTON_GAP: int = 14


@dataclass
class MenuButton:
    label: str
    action: MenuAction
    enabled: bool = True
    rect: pygame.Rect | None = None


class MainMenu:
    """Стартовый экран с 4 кнопками."""

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        title_font: pygame.font.Font | None = None,
        button_font: pygame.font.Font | None = None,
    ) -> None:
        self.screen_w = int(screen_w)
        self.screen_h = int(screen_h)
        self.title_font = (
            title_font if title_font is not None
            else pygame.font.SysFont(None, TITLE_FONT_SIZE)
        )
        self.button_font = (
            button_font if button_font is not None
            else pygame.font.SysFont(None, BUTTON_FONT_SIZE)
        )
        self.buttons: list[MenuButton] = [
            MenuButton("Новая игра", MenuAction.NEW_GAME, enabled=True),
            MenuButton("Загрузить игру", MenuAction.LOAD_GAME, enabled=False),
            MenuButton("Редактор карт", MenuAction.MAP_EDITOR, enabled=True),
            MenuButton("Выход", MenuAction.QUIT, enabled=True),
        ]
        self._layout_buttons()

    def _layout_buttons(self) -> None:
        total_h = len(self.buttons) * BUTTON_H + (len(self.buttons) - 1) * BUTTON_GAP
        start_y = (self.screen_h - total_h) // 2 + 40
        x = (self.screen_w - BUTTON_W) // 2
        for i, btn in enumerate(self.buttons):
            btn.rect = pygame.Rect(x, start_y + i * (BUTTON_H + BUTTON_GAP), BUTTON_W, BUTTON_H)

    def set_load_enabled(self, enabled: bool) -> None:
        for btn in self.buttons:
            if btn.action == MenuAction.LOAD_GAME:
                btn.enabled = bool(enabled)
                return

    def handle_click(self, pos: tuple[int, int]) -> MenuAction:
        for btn in self.buttons:
            if btn.rect is not None and btn.rect.collidepoint(pos):
                if btn.enabled:
                    return btn.action
                return MenuAction.NONE
        return MenuAction.NONE

    def handle_motion(self, pos: tuple[int, int]) -> None:
        _ = pos

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(PANEL_BG_COLOR)

        title = self.title_font.render("NEW EMPIRE", True, TITLE_COLOR)
        shadow = self.title_font.render("NEW EMPIRE", True, TITLE_SHADOW)
        tx = (self.screen_w - title.get_width()) // 2
        ty = self.screen_h // 4
        surface.blit(shadow, (tx + 3, ty + 3))
        surface.blit(title, (tx, ty))

        mouse_pos = pygame.mouse.get_pos()
        for btn in self.buttons:
            if btn.rect is None:
                continue
            hover = btn.enabled and btn.rect.collidepoint(mouse_pos)

            if not btn.enabled:
                bg = BTN_BG_DISABLED
                fg = BTN_TEXT_DISABLED
            elif hover:
                bg = BTN_BG_HOVER
                fg = BTN_TEXT
            else:
                bg = BTN_BG
                fg = BTN_TEXT

            pygame.draw.rect(surface, bg, btn.rect)
            pygame.draw.rect(surface, BTN_BORDER, btn.rect, 2)

            text = self.button_font.render(btn.label, True, fg)
            ttx = btn.rect.centerx - text.get_width() // 2
            tty = btn.rect.centery - text.get_height() // 2
            surface.blit(text, (ttx, tty))