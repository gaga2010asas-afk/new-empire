import os

import pygame
import pytest

from src.frontend.audio_manager import (
    AudioManager,
    MusicMode,
    FADE_MS,
    COOLDOWN_MS,
    MENU_TRACK,
)


@pytest.fixture(autouse=True, scope="module")
def _audio():
    # SDL_AUDIODRIVER=dummy выставлен в conftest.py.
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.display.set_mode((64, 64))
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    yield
    pygame.quit()


@pytest.fixture
def am():
    return AudioManager()


def test_initial_state_is_none(am):
    assert am.mode == MusicMode.NONE
    assert am.is_fading() is False
    assert am.get_current_volume_a() == 0.0
    assert am.get_current_volume_b() == 0.0


def test_crossfade_starts_when_first_track_requested(am, monkeypatch):
    # Подменяем загрузку музыки — чтобы не зависеть от файлов.
    fake_sound = pygame.mixer.Sound(buffer=b"\x00" * 2048)
    monkeypatch.setattr(am, "_load_music", lambda rel: fake_sound)
    am.play_menu()
    assert am.mode == MusicMode.MENU
    assert am.is_fading() is True


def test_crossfade_progresses_in_real_ms(am, monkeypatch):
    """v1.5.13 §4: 2000 мс — реальное время, не кадры."""
    fake_sound = pygame.mixer.Sound(buffer=b"\x00" * 2048)
    monkeypatch.setattr(am, "_load_music", lambda rel: fake_sound)
    am.play_menu()

    # Через половину fade — оба канала в промежуточном состоянии.
    am.update(FADE_MS // 2)
    a = am.get_current_volume_a()
    b = am.get_current_volume_b()
    assert 0.0 < a < 0.7
    assert 0.0 < b < 0.7

    # После полного fade — только один канал звучит.
    am.update(FADE_MS // 2 + 10)
    assert am.is_fading() is False
    assert am.get_current_volume_a() == 0.0 or am.get_current_volume_b() == 0.0


def test_cooldown_blocks_switch(am, monkeypatch):
    """v1.5.13 §4: 30000 мс кулдаун — попытка сменить режим раньше блокируется."""
    fake_sound = pygame.mixer.Sound(buffer=b"\x00" * 2048)
    monkeypatch.setattr(am, "_load_music", lambda rel: fake_sound)

    am.play_peace("human")
    assert am.mode == MusicMode.PEACE

    # Сразу же пытаемся уйти в бой — должно быть заблокировано кулдауном.
    am.play_battle("human")
    assert am.mode == MusicMode.PEACE

    # Продвигаем время почти до конца кулдауна.
    am.update(COOLDOWN_MS - 100)
    am.play_battle("human")
    assert am.mode == MusicMode.PEACE  # всё ещё блок

    # Через кулдаун — смена разрешена.
    am.update(200)
    am.play_battle("human")
    assert am.mode == MusicMode.BATTLE


def test_same_mode_request_is_noop(am, monkeypatch):
    fake_sound = pygame.mixer.Sound(buffer=b"\x00" * 2048)
    monkeypatch.setattr(am, "_load_music", lambda rel: fake_sound)
    am.play_menu()
    mode_before = am.mode
    am.play_menu()
    assert am.mode == mode_before


def test_menu_track_constant_is_canon():
    assert MENU_TRACK == "menu/main_theme.ogg"


def test_stop_music_resets(am, monkeypatch):
    fake_sound = pygame.mixer.Sound(buffer=b"\x00" * 2048)
    monkeypatch.setattr(am, "_load_music", lambda rel: fake_sound)
    am.play_menu()
    am.stop_music()
    assert am.mode == MusicMode.NONE
    assert am.is_fading() is False
    assert am.get_current_volume_a() == 0.0
    assert am.get_current_volume_b() == 0.0


def test_play_sfx_missing_file_is_silent(am, tmp_path, monkeypatch):
    """SFX отсутствует — no-op, без исключения."""
    am.sfx_root = str(tmp_path)
    am.play_sfx("ui", "click")  # не должно бросить


@pytest.mark.skipif(
    not os.path.isdir("assets/audio/sfx"),
    reason="Физические SFX-файлы отсутствуют в CI.",
)
def test_play_sfx_real_file_if_present(am):
    am.play_sfx("ui", "click")