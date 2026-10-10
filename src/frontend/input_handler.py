# src/frontend/input_handler.py
"""
InputHandler — единая точка входа пользовательского ввода. Прототип №8.
Зона: src/frontend/. Логики мира нет, backend не импортируется.

Контракт v1.5.13 §2:
- InputHandler возвращает СТРОГО абстрактные события через enum
  (MenuAction / GameAction). Никаких прямых вызовов backend.
- Оркестратор — src/main.py. Он читает возвращённые действия
  и вызывает нужные методы backend через мост.

[НЕТ ДАННЫХ]:
- Специфические бинды горячих клавиш (постройка, спеллы) — придут от архитектора
  в следующих патчах; здесь только каркас: WASD/стрелки/клик/Space/Esc.
"""

from __future__ import annotations

from enum import IntEnum

import pygame


# --- Абстрактные действия (v1.5.13 §2) ---

class MenuAction(IntEnum):
    """Действия главного меню. Возвращаются InputHandler в режиме меню."""
    NONE = 0
    NEW_GAME = 1
    LOAD_GAME = 2
    MAP_EDITOR = 3
    QUIT = 4


class GameAction(IntEnum):
    """Действия в игровом режиме. Возвращаются InputHandler в игре."""
    NONE = 0
    PAUSE_TOGGLE = 1
    CANCEL = 2
    CAMERA_MOVE = 3       # непрерывное движение — обрабатывается отдельно
    LEFT_CLICK = 4
    RIGHT_CLICK = 5
    SELECTION_BOX_START = 6
    SELECTION_BOX_END = 7


# --- Клавиши камеры (v1.5 §1) ---
CAMERA_KEYS: tuple[int, ...] = (
    pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s,
    pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
)


class InputHandler:
    """Преобразует pygame-события в абстрактные действия. Логики нет."""

    def __init__(self) -> None:
        # Начало прямоугольника выделения (для SELECTION_BOX_*).
        self.selection_box_start: tuple[int, int] | None = None
        self.selection_box_end: tuple[int, int] | None = None

    # --- режим меню -----------------------------------------------------------
    def handle_menu_event(self, event: pygame.event.Event) -> MenuAction:
        """Событие меню → MenuAction. NONE, если событие не относится к меню.

        Кнопки меню нажимаются через ui_menu.MainMenu; этот метод ловит
        глобальные клавиши (Esc / Enter) и проброс клика наружу.
        """
        if event.type != pygame.KEYDOWN:
            return MenuAction.NONE
        if event.key == pygame.K_RETURN:
            return MenuAction.NEW_GAME
        if event.key == pygame.K_ESCAPE:
            return MenuAction.QUIT
        return MenuAction.NONE

    # --- игровой режим --------------------------------------------------------
    def handle_game_event(self, event: pygame.event.Event) -> GameAction:
        """Событие игры → GameAction."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                return GameAction.PAUSE_TOGGLE
            if event.key == pygame.K_ESCAPE:
                return GameAction.CANCEL
            return GameAction.NONE

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.selection_box_start = event.pos
            return GameAction.LEFT_CLICK

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            return GameAction.RIGHT_CLICK

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.selection_box_start is not None:
                self.selection_box_end = event.pos
                action = GameAction.SELECTION_BOX_END
                self.selection_box_start = None
                return action
            return GameAction.NONE

        return GameAction.NONE

    # --- непрерывное состояние (для камеры) ----------------------------------
    @staticmethod
    def get_camera_input() -> tuple[int, int]:
        """Вернуть (dx, dy) в диапазоне -1..1 на основе удержания клавиш.

        main.py вызывает это каждый кадр в игровом режиме и передаёт в Camera.update.
        """
        keys = pygame.key.get_pressed()
        dx = 0
        dy = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1
        return (dx, dy)