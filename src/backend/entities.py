# src/backend/entities.py
"""
NEW EMPIRE v1.5.16 — Backend Agent.
dataclass Unit / Building + фабрики из JSON.

Патч v1.5.16 (п.9): Building получил метод `center_px()` — единая
каноничная точка сдачи ресурсов (математический центр здания).

Без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from .constants import BuildingState, TILE_SIZE, UnitState


@dataclass
class Unit:
    id: int
    faction: str
    type: str
    pixel_x: float
    pixel_y: float
    direction: int = 0
    state: int = int(UnitState.IDLE)
    hp: int = 1
    max_hp: int = 1
    is_selected: bool = False
    owner_id: int = 0
    stats: Dict[str, Any] = field(default_factory=dict)
    inside_mine: bool = False

    def __post_init__(self) -> None:
        if not (0 <= self.direction <= 7):
            raise ValueError(f"direction {self.direction} вне 0..7")
        if not (0 <= int(self.state) <= 6):
            raise ValueError(f"state {self.state} вне 0..6")
        if self.max_hp <= 0:
            raise ValueError("max_hp должен быть > 0")
        if self.hp < 0 or self.hp > self.max_hp:
            raise ValueError("hp должен быть в [0, max_hp]")

    def is_alive(self) -> bool:
        return self.state != int(UnitState.DEAD) and self.hp > 0


@dataclass
class Building:
    id: str
    grid_x: int
    grid_y: int
    width: int
    height: int
    hp: int = 1
    max_hp: int = 1
    state: int = int(BuildingState.CONSTRUCTING)
    faction: str = "human"
    type: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("Building.id должен быть непустой строкой")
        if self.width < 1 or self.height < 1:
            raise ValueError("width/height должны быть >= 1")
        if not (0 <= int(self.state) <= 3):
            raise ValueError(f"state {self.state} вне 0..3")
        if self.max_hp <= 0:
            raise ValueError("max_hp должен быть > 0")
        if self.hp < 0 or self.hp > self.max_hp:
            raise ValueError("hp должен быть в [0, max_hp]")

    def is_alive(self) -> bool:
        return self.state != int(BuildingState.DESTROYED) and self.hp > 0

    # ------------------------------------------------------------ v1.5.16
    def center_px(self) -> Tuple[float, float]:
        """
        Патч v1.5.16, п.9: математический центр строения в пикселях.
        Формула: (grid_x + width/2, grid_y + height/2) × TILE_SIZE.
        Рабочие несут мешки строго сюда — не в левый верхний угол.
        """
        cx = (self.grid_x + self.width / 2.0) * TILE_SIZE
        cy = (self.grid_y + self.height / 2.0) * TILE_SIZE
        return (cx, cy)


# --- Фабрики из JSON --------------------------------------------------------
def unit_from_content(unit_id: int, faction: str, content: Dict[str, Any],
                      pixel_x: float, pixel_y: float,
                      owner_id: int = 0) -> Unit:
    return Unit(
        id=unit_id, faction=faction, type=content["id"],
        pixel_x=float(pixel_x), pixel_y=float(pixel_y),
        hp=int(content["hp"]), max_hp=int(content["hp"]),
        owner_id=owner_id,
        stats={
            "damage": int(content["damage"]),
            "armor": int(content["armor"]),
            "sprite": content["sprite"],
            "cost": dict(content["cost"]),
            "build_time": int(content["build_time"]),
            "triad_role": content["triad_role"],
        },
    )


def building_from_content(grid_x: int, grid_y: int, faction: str,
                          content: Dict[str, Any],
                          id_override: Optional[str] = None) -> Building:
    bid = id_override or f"{content['id']}_{int(grid_x)}_{int(grid_y)}"
    return Building(
        id=bid,
        grid_x=int(grid_x), grid_y=int(grid_y),
        width=int(content["grid_width"]), height=int(content["grid_height"]),
        hp=int(content["hp"]), max_hp=int(content["hp"]),
        faction=faction, type=content["id"],
    )