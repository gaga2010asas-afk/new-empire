import pygame
import pytest

from src.frontend.display import GameDisplay, DEFAULT_WIDTH, DEFAULT_HEIGHT, TARGET_FPS


def test_default_size_and_title():
    d = GameDisplay()
    try:
        assert d.get_size() == (DEFAULT_WIDTH, DEFAULT_HEIGHT) == (1024, 768)
        assert pygame.display.get_caption()[0] == "NEW EMPIRE"
    finally:
        d.close()


def test_mouse_hidden_after_init():
    d = GameDisplay()
    try:
        assert pygame.mouse.get_visible() is False
    finally:
        d.close()


def test_pump_events_handles_quit():
    d = GameDisplay()
    try:
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        d.pump_events()
        assert d.running is False
    finally:
        d.close()


def test_tick_returns_ms():
    d = GameDisplay()
    try:
        ms = d.tick(TARGET_FPS)
        assert isinstance(ms, int)
        assert ms >= 0
    finally:
        d.close()