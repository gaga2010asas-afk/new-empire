# src/backend/netplay.py
"""
NEW EMPIRE v1.5.12 — Backend Agent (Proto #8).
Сетевая игра LAN: безопасный стаб с базовой инициализацией хоста.
Канон: 1v1, lockstep, детерминированный RNG, хост — авторитет,
разрыв → пауза + переподключение.
[НЕТ ДАННЫХ] — протокол, seed-деривация, формат команд.
Алгоритмы перенесены в будущие DLC-модули.
Без pygame.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .constants import NET_DEFAULT_PORT, NET_MAX_PLAYERS


class NetplayError(Exception):
    pass


class NetplayNotImplemented(NetplayError):
    """Выбрасывается на вызовах, где канон ещё не определён."""
    pass


class NetRole(str, Enum):
    NONE   = "none"
    HOST   = "host"
    CLIENT = "client"


@dataclass
class NetSession:
    role: NetRole
    port: int
    host_address: Optional[str] = None
    players_connected: int = 0
    tick: int = 0
    paused: bool = False


def deterministic_seed(user_seed: int, player_slots: List[int]) -> int:
    """
    [НЕТ ДАННЫХ] — точный алгоритм каноном не задан.
    Возвращает детерминированный int из seed + слотов игроков.
    Реализация — sha256 (воспроизводимо на всех платформах).
    Перенесён в DLC-модуль network_rng.
    """
    if not player_slots:
        raise NetplayError("player_slots пуст")
    key = f"{int(user_seed)}:" + \
          ",".join(str(int(s)) for s in sorted(player_slots))
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)


class LockstepNetplay:
    """
    Базовая инициализация LAN-сессии. Полный lockstep-протокол [НЕТ ДАННЫХ].
    Реализованы: создание, start_host, connect, close, set_paused.
    Методы send_command / poll_remote_commands / wait_for_tick —
    заглушки с NetplayNotImplemented.
    """

    def __init__(self,
                 port: int = NET_DEFAULT_PORT,
                 max_players: int = NET_MAX_PLAYERS) -> None:
        if port <= 0 or port > 65535:
            raise NetplayError(f"port {port} вне 1..65535")
        if max_players < 2:
            raise NetplayError(
                f"max_players {max_players} должен быть >= 2")
        self.port = int(port)
        self.max_players = int(max_players)
        self.session = NetSession(role=NetRole.NONE, port=self.port)
        self._closed = False

    # ------------------------------------------------------------ жизненный цикл
    def start_host(self) -> NetSession:
        """
        [НЕТ ДАННЫХ] — реальные сокеты не открываются.
        Устанавливает роль HOST и возвращает сессию.
        """
        if self._closed:
            raise NetplayError("Сессия закрыта")
        if self.session.role != NetRole.NONE:
            raise NetplayError(
                f"Сессия уже инициализирована как "
                f"{self.session.role.value}")
        self.session = NetSession(
            role=NetRole.HOST, port=self.port,
            host_address=None, players_connected=1,
            tick=0, paused=False,
        )
        return self.session

    def connect(self, host_address: str) -> NetSession:
        """
        [НЕТ ДАННЫХ] — реальные сокеты не открываются.
        Устанавливает роль CLIENT. Адрес хоста сохраняется как строка.
        """
        if self._closed:
            raise NetplayError("Сессия закрыта")
        if self.session.role != NetRole.NONE:
            raise NetplayError(
                f"Сессия уже инициализирована как "
                f"{self.session.role.value}")
        if not host_address:
            raise NetplayError("host_address пуст")
        self.session = NetSession(
            role=NetRole.CLIENT, port=self.port,
            host_address=str(host_address), players_connected=1,
            tick=0, paused=False,
        )
        return self.session

    def close(self) -> None:
        self._closed = True
        self.session.role = NetRole.NONE
        self.session.players_connected = 0

    # ------------------------------------------------------------ lockstep (стабы)
    def send_command(self, tick: int,
                     payload: Dict[str, Any]) -> None:
        raise NetplayNotImplemented(
            "Lockstep-протокол не определён в каноне v1.5")

    def poll_remote_commands(self) -> List[Dict[str, Any]]:
        raise NetplayNotImplemented(
            "Lockstep-протокол не определён в каноне v1.5")

    def wait_for_tick(self, tick: int) -> None:
        raise NetplayNotImplemented(
            "Ожидание синхронного тика не определено в каноне v1.5")

    # ------------------------------------------------------------ пауза / разрыв
    def set_paused(self, value: bool) -> None:
        """Канон: разрыв связи → пауза + переподключение."""
        self.session.paused = bool(value)