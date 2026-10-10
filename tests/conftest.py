# tests/conftest.py
"""
NEW EMPIRE — Headless-фикстура тестовой среды.
Обязательна для UI-тестов: pygame.font и pygame.mixer нуждаются
в инициализированном видео-контексте (даже фейковом 1×1).
"""
import os
import sys
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pygame.init()
pygame.display.set_mode((1, 1))
pygame.font.init()
pygame.mixer.init()