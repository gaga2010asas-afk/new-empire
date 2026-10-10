# src/backend/ai_difficulty.py
"""
NEW EMPIRE v1.5.12 — Backend Agent (Proto #8).
Уровни сложности ИИ: 1 Лёгкий, 2 Средний, 3 Сложный, 4 Непобедимый.
Уровень 4 — самообучающийся; алгоритм обучения [НЕТ ДАННЫХ].
Канон: MASTER BRIEF v1.5 (Block 8) + Proto #8.
Без pygame.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import (
    AI_DIFFICULTY_MAX, AI_DIFFICULTY_MIN, AI_LEARNING_FILE, SAVES_DIR,
)


class AIDifficultyError(Exception):
    pass


class AIDifficulty(IntEnum):
    EASY       = 1
    MEDIUM     = 2
    HARD       = 3
    INVINCIBLE = 4


@dataclass(frozen=True)
class DifficultyProfile:
    difficulty: AIDifficulty
    name: str
    # [НЕТ ДАННЫХ] — числовые параметры ИИ каноном не заданы.
    # Поля служат каркасом, заполняются балансовым блокнотом.
    reaction_delay_ticks: Optional[int] = None
    aggression: Optional[float] = None
    economy_multiplier: Optional[float] = None
    learning_enabled: bool = False


PROFILES: Dict[AIDifficulty, DifficultyProfile] = {
    AIDifficulty.EASY: DifficultyProfile(
        difficulty=AIDifficulty.EASY, name="Лёгкий",
        reaction_delay_ticks=90, aggression=0.3,
        economy_multiplier=1.0, learning_enabled=False,
    ),
    AIDifficulty.MEDIUM: DifficultyProfile(
        difficulty=AIDifficulty.MEDIUM, name="Средний",
        reaction_delay_ticks=45, aggression=0.6,
        economy_multiplier=1.0, learning_enabled=False,
    ),
    AIDifficulty.HARD: DifficultyProfile(
        difficulty=AIDifficulty.HARD, name="Сложный",
        reaction_delay_ticks=15, aggression=0.9,
        economy_multiplier=1.0, learning_enabled=False,
    ),
    AIDifficulty.INVINCIBLE: DifficultyProfile(
        difficulty=AIDifficulty.INVINCIBLE, name="Непобедимый",
        reaction_delay_ticks=None, aggression=None,
        economy_multiplier=None, learning_enabled=True,
    ),
}


def profile_for(level: int) -> DifficultyProfile:
    if not (AI_DIFFICULTY_MIN <= level <= AI_DIFFICULTY_MAX):
        raise AIDifficultyError(
            f"Уровень сложности {level} вне "
            f"[{AI_DIFFICULTY_MIN}, {AI_DIFFICULTY_MAX}]")
    return PROFILES[AIDifficulty(level)]


class LearningStore:
    """
    Память Непобедимого ИИ.
    [НЕТ ДАННЫХ] — формат и семантика ключей каноном не заданы.
    Реализованы load / save / clear / remember / recall.
    Алгоритм самообучения перенесён в будущие DLC-модули.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None \
            else (SAVES_DIR / AI_LEARNING_FILE)
        self._data: Dict[str, Any] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    def clear(self) -> None:
        self._data = {}

    def remember(self, key: str, value: Any) -> None:
        """[НЕТ ДАННЫХ] — конкретные ключи и значения определяет ИИ."""
        self._data[str(key)] = value

    def recall(self, key: str) -> Optional[Any]:
        return self._data.get(str(key))

    def size(self) -> int:
        return len(self._data)