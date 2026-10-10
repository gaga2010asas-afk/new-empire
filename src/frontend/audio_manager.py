# src/frontend/audio_manager.py
"""
AudioManager — музыкальный движок NEW EMPIRE. Прототип №8.
Зона: src/frontend/. Логики мира нет.

Канон v1.5 §1 (Блок 9, 16):
- Формат музыки .ogg, -3 dBFS, 44100 Hz stereo.
- Меню: main_theme. На Мир/Бой: 3 трека на фракцию, случайный выбор, без повтора.
- Кроссфейд переходов 2000 мс.
- Кулдаун смены режима 30000 мс.
- Тайминги — по реальному времени (мс), не по кадрам (v1.5.13 §4).

Канон v1.5.13 §1: pygame.mixer.music СНЯТ. Музыка — два выделенных
канала (Channel 0 и Channel 1), треки загружаются как Sound.

Канон v1.5.13 §6: собственный float-счётчик громкости; get_volume()
pygame не используется для инкрементов.

[НЕТ ДАННЫХ]:
- Имена SFX-категорий приходят через play_sfx(category, key) — пути
  задаются снаружи (assets/audio/sfx/<category>/<key>.wav).
"""

from __future__ import annotations

import logging
import os
import random
from enum import IntEnum

import pygame


log = logging.getLogger(__name__)

# --- Канон v1.5 §1 ---
FADE_MS: int = 2000
COOLDOWN_MS: int = 30_000
MUSIC_VOLUME: float = 0.7

# --- Пути ---
DEFAULT_MUSIC_ROOT: str = "assets/audio/music"
DEFAULT_SFX_ROOT: str = "assets/audio/sfx"

# --- Файлы музыки (канон) ---
MENU_TRACK: str = "menu/main_theme.ogg"
PEACE_TRACKS: dict[str, tuple[str, ...]] = {
    "human": ("peace/human_1.ogg", "peace/human_2.ogg", "peace/human_3.ogg"),
    "orc":   ("peace/orc_1.ogg",   "peace/orc_2.ogg",   "peace/orc_3.ogg"),
}
BATTLE_TRACKS: dict[str, tuple[str, ...]] = {
    "human": ("battle/human_1.ogg", "battle/human_2.ogg", "battle/human_3.ogg"),
    "orc":   ("battle/orc_1.ogg",   "battle/orc_2.ogg",   "battle/orc_3.ogg"),
}


class MusicMode(IntEnum):
    """Активный музыкальный режим. Канон v1.5 §1."""
    NONE = 0
    MENU = 1
    PEACE = 2
    BATTLE = 3


class AudioManager:
    """Двухканальный кроссфейдер музыки + SFX-проигрыватель.

    Канон v1.5.13 §1: два выделенных канала (CH_A=0, CH_B=1).
    Активный канал сменяется после каждого кроссфейда.
    """

    CH_A: int = 0
    CH_B: int = 1
    SFX_RESERVED_CHANNELS: int = 6     # 2..7 — под SFX

    def __init__(
        self,
        music_root: str = DEFAULT_MUSIC_ROOT,
        sfx_root: str = DEFAULT_SFX_ROOT,
        rng: random.Random | None = None,
    ) -> None:
        self.music_root = music_root
        self.sfx_root = sfx_root
        self.rng = rng if rng is not None else random.Random()

        # Кэши Sound-треков (загружаются один раз).
        self._music_cache: dict[str, pygame.mixer.Sound] = {}
        self._sfx_cache: dict[str, pygame.mixer.Sound] = {}

        # Состояние кроссфейда.
        self.mode: MusicMode = MusicMode.NONE
        self.faction: str = "human"
        self._active_channel_index: int = 0   # 0 → CH_A, 1 → CH_B

        # Текущая фактическая громкость на каждом канале.
        self._vol_a: float = 0.0
        self._vol_b: float = 0.0

        # Отслеживание fade (мс, по реальному времени — v1.5.13 §4).
        self._fade_elapsed_ms: int = 0
        self._fading: bool = False
        self._last_switch_ms: int = -COOLDOWN_MS

        # Ключ последнего проигранного трека (без повтора).
        self._last_track_key: str | None = None

        # Глобальный таймер (мс), двигается через update(dt_ms).
        self._now_ms: int = 0

        # Каналы (числа) — резервируем 0 и 1 под музыку.
        pygame.mixer.set_reserved(2)
        pygame.mixer.set_num_channels(max(8, self.SFX_RESERVED_CHANNELS + 2))

    # --- таймер -------------------------------------------------------------
    def update(self, dt_ms: int) -> None:
        """Продвинуть аудио-состояние. dt_ms — реальное время с прошлого кадра."""
        self._now_ms += int(dt_ms)
        if self._fading:
            self._advance_fade(int(dt_ms))

    # --- музыка: внешний API --------------------------------------------------
    def play_menu(self) -> None:
        """Меню: main_theme.ogg. Всегда с кроссфейдом, если уже что-то играет."""
        self._request_mode(MusicMode.MENU)

    def play_peace(self, faction: str) -> None:
        """Мир. Трек выбирается из 3 (без повтора предыдущего)."""
        self.faction = faction if faction in PEACE_TRACKS else "human"
        self._request_mode(MusicMode.PEACE)

    def play_battle(self, faction: str) -> None:
        """Бой. Трек выбирается из 3 (без повтора предыдущего)."""
        self.faction = faction if faction in BATTLE_TRACKS else "human"
        self._request_mode(MusicMode.BATTLE)

    def stop_music(self) -> None:
        """Мгновенно заглушить оба канала."""
        self._ch_a().stop()
        self._ch_b().stop()
        self._vol_a = 0.0
        self._vol_b = 0.0
        self._fading = False
        self.mode = MusicMode.NONE

    # --- музыка: внутренняя логика -------------------------------------------
    def _request_mode(self, new_mode: MusicMode) -> None:
        """Запросить смену режима с учётом кулдауна (v1.5.13 §4 — мс)."""
        if new_mode == self.mode:
            return
        # Кулдаун: смена разрешена только спустя COOLDOWN_MS реального времени.
        if (self._now_ms - self._last_switch_ms) < COOLDOWN_MS:
            return

        track_path = self._pick_track_for(new_mode)
        if track_path is None:
            return

        self._start_crossfade(track_path)
        self.mode = new_mode
        self._last_switch_ms = self._now_ms

    def _pick_track_for(self, mode: MusicMode) -> str | None:
        """Выбрать трек: 1 для меню, 3 из пула для мира/боя без повтора."""
        if mode == MusicMode.MENU:
            return MENU_TRACK
        if mode == MusicMode.PEACE:
            return self._pick_from_pool(PEACE_TRACKS.get(self.faction, ()))
        if mode == MusicMode.BATTLE:
            return self._pick_from_pool(BATTLE_TRACKS.get(self.faction, ()))
        return None

    def _pick_from_pool(self, pool: tuple[str, ...]) -> str | None:
        if not pool:
            return None
        choices = [t for t in pool if t != self._last_track_key] or list(pool)
        chosen = self.rng.choice(choices)
        self._last_track_key = chosen
        return chosen

    def _start_crossfade(self, rel_path: str) -> None:
        """Запустить новый трек на свободном канале и начать fade-in/out."""
        sound = self._load_music(rel_path)
        if sound is None:
            return

        incoming = self._ch_b() if self._active_channel_index == 0 else self._ch_a()
        outgoing = self._ch_a() if self._active_channel_index == 0 else self._ch_b()

        incoming.stop()
        incoming.set_volume(0.0)
        incoming.play(sound, loops=-1)

        # Сброс счётчика fade — реальное время.
        self._fade_elapsed_ms = 0
        self._fading = True
        # Запомним целевые каналы.
        self._incoming_is_a = (self._active_channel_index == 1)
        self._outgoing_is_a = (self._active_channel_index == 0)

    def _advance_fade(self, dt_ms: int) -> None:
        """Продвинуть кроссфейд на dt_ms реального времени."""
        self._fade_elapsed_ms += dt_ms
        t = min(1.0, self._fade_elapsed_ms / float(FADE_MS))

        # Целевые громкости.
        if self._incoming_is_a:
            self._vol_a = MUSIC_VOLUME * t
            self._vol_b = MUSIC_VOLUME * (1.0 - t)
        else:
            self._vol_a = MUSIC_VOLUME * (1.0 - t)
            self._vol_b = MUSIC_VOLUME * t

        self._ch_a().set_volume(self._vol_a)
        self._ch_b().set_volume(self._vol_b)

        if t >= 1.0:
            # Завершить fade: глушим исходящий канал, меняем активный.
            outgoing = self._ch_a() if self._outgoing_is_a else self._ch_b()
            outgoing.stop()
            if self._outgoing_is_a:
                self._vol_a = 0.0
            else:
                self._vol_b = 0.0
            self._active_channel_index = 1 - self._active_channel_index
            self._fading = False

    # --- каналы --------------------------------------------------------------
    def _ch_a(self) -> pygame.mixer.Channel:
        return pygame.mixer.Channel(self.CH_A)

    def _ch_b(self) -> pygame.mixer.Channel:
        return pygame.mixer.Channel(self.CH_B)

    # --- загрузка ------------------------------------------------------------
    def _load_music(self, rel_path: str) -> pygame.mixer.Sound | None:
        if rel_path in self._music_cache:
            return self._music_cache[rel_path]
        full = os.path.join(self.music_root, rel_path)
        if not os.path.isfile(full):
            log.warning("Музыкальный трек не найден: %s", full)
            return None
        try:
            sound = pygame.mixer.Sound(full)
        except pygame.error as exc:
            log.warning("Не удалось загрузить трек %s: %s", full, exc)
            return None
        self._music_cache[rel_path] = sound
        return sound

    # --- SFX -----------------------------------------------------------------
    def play_sfx(self, category: str, key: str, volume: float = 1.0) -> None:
        """Проиграть SFX на свободном канале. Категория = папка, key = имя файла."""
        cache_key = f"{category}/{key}"
        sound = self._sfx_cache.get(cache_key)
        if sound is None:
            full = os.path.join(self.sfx_root, category, f"{key}.wav")
            if not os.path.isfile(full):
                log.warning("SFX не найден: %s", full)
                return
            try:
                sound = pygame.mixer.Sound(full)
            except pygame.error as exc:
                log.warning("Не удалось загрузить SFX %s: %s", full, exc)
                return
            self._sfx_cache[cache_key] = sound

        channel = pygame.mixer.find_channel()
        if channel is None:
            return
        channel.set_volume(max(0.0, min(1.0, float(volume))))
        channel.play(sound)

    # --- диагностика ---------------------------------------------------------
    def get_current_volume_a(self) -> float:
        return self._vol_a

    def get_current_volume_b(self) -> float:
        return self._vol_b

    def is_fading(self) -> bool:
        return self._fading

    def now_ms(self) -> int:
        return self._now_ms