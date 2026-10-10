import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.ai_difficulty import (
    AIDifficulty, AIDifficultyError, DifficultyProfile, LearningStore,
    PROFILES, profile_for,
)


def test_all_levels_have_profiles():
    for level in (1, 2, 3, 4):
        p = profile_for(level)
        assert isinstance(p, DifficultyProfile)
        assert p.difficulty == AIDifficulty(level)


def test_names_match_canon():
    assert profile_for(1).name == "Лёгкий"
    assert profile_for(2).name == "Средний"
    assert profile_for(3).name == "Сложный"
    assert profile_for(4).name == "Непобедимый"


def test_invincible_has_learning_enabled():
    assert profile_for(4).learning_enabled is True
    for level in (1, 2, 3):
        assert profile_for(level).learning_enabled is False


def test_invalid_level_raises():
    with pytest.raises(AIDifficultyError):
        profile_for(0)
    with pytest.raises(AIDifficultyError):
        profile_for(5)


def test_learning_store_round_trip(tmp_path):
    p = tmp_path / "ai.json"
    store = LearningStore(path=p)
    store.remember("aggression", 0.7)
    store.remember("last_hero", "paladin")
    store.save()

    store2 = LearningStore(path=p)
    store2.load()
    assert store2.recall("aggression") == 0.7
    assert store2.recall("last_hero") == "paladin"
    assert store2.size() == 2


def test_learning_store_missing_file_is_empty(tmp_path):
    store = LearningStore(path=tmp_path / "missing.json")
    store.load()
    assert store.size() == 0


def test_learning_store_clear(tmp_path):
    store = LearningStore(path=tmp_path / "ai.json")
    store.remember("k", 1)
    store.clear()
    assert store.size() == 0