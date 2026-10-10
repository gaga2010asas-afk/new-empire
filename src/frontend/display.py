# src/frontend/display.py
"""
GameDisplay — окно Pygame для NEW EMPIRE.
Зона: src/frontend/. Backend не импортируется. Логики мира нет.

Канон v1.5 §1: 1024x768, TARGET_FPS=60, системная мышь скрыта.
Канон v1.5.13 §5: pygame.mixer.pre_init(44100, -16, 2, 512) ДО pygame.init().
"""

from __future__ import annotations

import pygame


# --- Канон v1.5 §1 ---
DEFAULT_WIDTH: int = 1024
DEFAULT_HEIGHT: int = 768
DEFAULT_TITLE: str = "NEW EMPIRE"
TARGET_FPS: int = 60

# --- Канон v1.5.13 §5: аудио-параметры ---
AUDIO_FREQUENCY: int = 44100
AUDIO_SIZE: int = -16
AUDIO_CHANNELS: int = 2
AUDIO_BUFFER: int = 512


class GameDisplay:
    """Обёртка над окном Pygame: surface, caption, clock, скрытие мыши."""

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        title: str = DEFAULT_TITLE,
    ) -> None:
        # v1.5.13 §5: pre_init ДО pygame.init() — иначе mixer возьмёт дефолты.
        pygame.mixer.pre_init(AUDIO_FREQUENCY, AUDIO_SIZE, AUDIO_CHANNELS, AUDIO_BUFFER)
        pygame.init()

        self.width: int = int(width)
        self.height: int = int(height)
        self.title: str = title

        self.screen: pygame.Surface = pygame.display.set_mode(
            (self.width, self.height)
        )
        pygame.display.set_caption(self.title)

        # Канон v1.5 §1: системный курсор скрыт — рисуем свой.
        pygame.mouse.set_visible(False)

        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.running: bool = True

    # --- поверхность ----------------------------------------------------------
    def get_surface(self) -> pygame.Surface:
        return self.screen

    def get_size(self) -> tuple[int, int]:
        return (self.width, self.height)

    # --- цикл -----------------------------------------------------------------
    def pump_events(self) -> list[pygame.event.Event]:
        """Забрать события кадра. QUIT переводит окно в stopped."""
        events: list[pygame.event.Event] = list(pygame.event.get())
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
        return events

    def tick(self, fps: int = TARGET_FPS) -> int:
        """Ограничить кадр. Возвращает dt в миллисекундах."""
        return self.clock.tick(fps)

    def flip(self) -> None:
        pygame.display.flip()

    def request_quit(self) -> None:
        self.running = False

    def close(self) -> None:
        pygame.quit()