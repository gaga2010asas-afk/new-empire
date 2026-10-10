# src/backend/unit_ai.py
"""
NEW EMPIRE v1.5.23 — Backend Agent (Proto #4).
CombatEngine с баллистикой (v1.5.5), кулдаун 60 тиков, event_bus.

Патч v1.5.23, пп.1-2:
  * _tick_attacks() декрементирует КД каждый тик.
  * Projectile физически добавляется в self.projectiles
    в момент выстрела, ДО любых проверок выживаемости цели.
  * Нет преждевременных return до self.projectiles.append(...).
  * attack_count++ и projectiles.append(...) в одном блоке.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .combat import UpgradeRegistry, apply_damage, calculate_damage
from .constants import (
    ATTACK_COOLDOWN_TICKS, BuildingState,
    PROJECTILE_HIT_RADIUS_PX, TILE_SIZE, UnitState,
)
from .entities import Building, Unit
from .events import EventBus


DEFAULT_ATTACK_RANGE_PX: float = TILE_SIZE * 1.5
DEFAULT_PROJECTILE_SPEED_PX_PER_SEC: float = 600.0

PROJECTILE_KINDS: Tuple[str, ...] = (
    "arrow", "axe", "ballista_bolt", "cannon_ball",
)


@dataclass
class Projectile:
    id: int
    kind: str
    faction: str
    attacker_id: int
    target_id: int
    target_is_building: bool
    pixel_x: float
    pixel_y: float
    target_x: float
    target_y: float
    vx: float
    vy: float
    damage: int
    hit_radius: float
    alive: bool = True


class CombatEngine:
    def __init__(self,
                 units: Dict[int, Unit],
                 buildings: Dict[str, Building],
                 upgrades: Optional[UpgradeRegistry] = None,
                 event_bus: Optional[EventBus] = None,
                 attack_range_px: float = DEFAULT_ATTACK_RANGE_PX,
                 projectile_speed: float = DEFAULT_PROJECTILE_SPEED_PX_PER_SEC,
                 hit_radius: float = PROJECTILE_HIT_RADIUS_PX,
                 cooldown_ticks: int = ATTACK_COOLDOWN_TICKS) -> None:
        self.units = units
        self.buildings = buildings
        self.upgrades = upgrades if upgrades is not None else UpgradeRegistry()
        for f in ("human", "orc"):
            self.upgrades.register(f)
        self.event_bus = event_bus
        self.attack_range_px = float(attack_range_px)
        self.projectile_speed = float(projectile_speed)
        self.hit_radius = float(hit_radius)
        self.cooldown_ticks = int(cooldown_ticks)

        self.projectiles: List[Projectile] = []
        self.attack_count: int = 0
        self.tick: int = 0
        # Отсутствие uid = 0 КД = готов стрелять.
        self._cooldown_counter: Dict[int, int] = {}
        self._targets: Dict[int, Tuple] = {}
        self._next_proj_id: int = 1

    # ---------------------------------------------------------------- API
    def set_target(self, attacker_id: int, target_id,
                   target_is_building: bool = False) -> None:
        if attacker_id not in self.units:
            raise KeyError(f"Атакующий {attacker_id} не найден")
        self._targets[attacker_id] = (target_id, bool(target_is_building))
        self.units[attacker_id].state = int(UnitState.ATTACK)

    def clear_target(self, attacker_id: int) -> None:
        self._targets.pop(attacker_id, None)

    # ================================================================
    # update() — публичный вход.
    # ================================================================
    def update(self, dt: float) -> None:
        if dt <= 0:
            raise ValueError("dt должен быть > 0")
        self._tick_attacks()
        self._tick_projectiles(dt)
        self.tick += 1

    # ================================================================
    # _tick_attacks() — единственное место, где рождаются снаряды.
    # ================================================================
    def _tick_attacks(self) -> None:
        for uid, unit in list(self.units.items()):
            # --- 0. Мёртвый юнит — снимаем всё и идём дальше.
            if unit.state == int(UnitState.DEAD) or unit.hp <= 0:
                self._cooldown_counter.pop(uid, None)
                self._targets.pop(uid, None)
                continue

            # --- 1. Декремент КД каждый тик, независимо от цели.
            cd = self._cooldown_counter.get(uid, 0)
            if cd > 0:
                cd -= 1
                self._cooldown_counter[uid] = cd

            # --- 2. Атаковать можно только в состоянии ATTACK.
            if unit.state != int(UnitState.ATTACK):
                continue

            # --- 3. И только когда КД истёк.
            if cd > 0:
                continue

            # --- 4. Проверка/поиск цели.
            pair = self._targets.get(uid)
            target = None
            if pair is not None:
                target = self._get_entity(pair[0], pair[1])
                if target is None or target.hp <= 0:
                    self._targets.pop(uid, None)
                    target = None

            if target is None:
                found = self._find_nearest_enemy(unit)
                if found is None:
                    continue
                pair = found
                self._targets[uid] = pair
                target = self._get_entity(pair[0], pair[1])
                if target is None:
                    continue

            # --- 5. Дистанция.
            tid, is_b = pair
            tx, ty = self._entity_center(target, is_b)
            dist = math.hypot(tx - unit.pixel_x, ty - unit.pixel_y)
            if dist > self.attack_range_px:
                continue

            # --- 6. ЕДИНЫЙ БЛОК: spawn + append + counter + count.
            #          Никаких return'ов между этими строками.
            new_projectile = self._spawn_projectile(unit, target, tid, is_b)
            self.projectiles.append(new_projectile)      # <-- вот здесь append
            self._cooldown_counter[uid] = self.cooldown_ticks
            self.attack_count += 1

    # ================================================================
    # _spawn_projectile() — СОЗДАЁТ объект, но НЕ добавляет его в список.
    #                       Append делает _tick_attacks().
    # ================================================================
    def _spawn_projectile(self, attacker: Unit, target, target_id,
                          is_building: bool) -> Projectile:
        kind = self._pick_projectile_kind(attacker)
        damage = calculate_damage(attacker, target, self.upgrades)
        tx, ty = self._entity_center(target, is_building)
        dx, dy = tx - attacker.pixel_x, ty - attacker.pixel_y
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            vx = vy = 0.0
        else:
            vx = dx / dist * self.projectile_speed
            vy = dy / dist * self.projectile_speed

        proj = Projectile(
            id=self._next_proj_id, kind=kind,
            faction=attacker.faction, attacker_id=attacker.id,
            target_id=target_id, target_is_building=bool(is_building),
            pixel_x=attacker.pixel_x, pixel_y=attacker.pixel_y,
            target_x=tx, target_y=ty,
            vx=vx, vy=vy,
            damage=int(damage),
            hit_radius=self.hit_radius,
        )
        self._next_proj_id += 1
        return proj

    # ================================================================
    # _tick_projectiles() — полёт и попадание.
    # ================================================================
    def _tick_projectiles(self, dt: float) -> None:
        survivors: List[Projectile] = []
        for p in self.projectiles:
            if not p.alive:
                continue

            step_x = p.vx * dt
            step_y = p.vy * dt
            step_dist = math.hypot(step_x, step_y)
            dist_to_target = math.hypot(p.target_x - p.pixel_x,
                                        p.target_y - p.pixel_y)

            if step_dist >= dist_to_target:
                p.pixel_x = p.target_x
                p.pixel_y = p.target_y
            else:
                p.pixel_x += step_x
                p.pixel_y += step_y

            ddx = p.pixel_x - p.target_x
            ddy = p.pixel_y - p.target_y
            if ddx * ddx + ddy * ddy > p.hit_radius * p.hit_radius:
                survivors.append(p)
                continue

            target = self._get_entity(p.target_id, p.target_is_building)
            if target is not None and target.hp > 0:
                tcx, tcy = self._entity_center(target, p.target_is_building)
                tdx = tcx - p.target_x
                tdy = tcy - p.target_y
                if tdx * tdx + tdy * tdy <= p.hit_radius * p.hit_radius:
                    apply_damage(target, p.damage, self.event_bus)
            p.alive = False

        self.projectiles = survivors

    # ---------------------------------------------------------------- цели
    def _find_nearest_enemy(self, unit: Unit) -> Optional[Tuple]:
        best = None
        best_d: Optional[float] = None

        for tid, other in self.units.items():
            if other.faction == unit.faction:
                continue
            if other.hp <= 0 or other.state == int(UnitState.DEAD):
                continue
            d = math.hypot(other.pixel_x - unit.pixel_x,
                           other.pixel_y - unit.pixel_y)
            if d > self.attack_range_px:
                continue
            if best_d is None or d < best_d:
                best_d, best = d, (tid, False)

        for bid, b in self.buildings.items():
            if b.faction == unit.faction:
                continue
            if b.hp <= 0 or b.state == int(BuildingState.DESTROYED):
                continue
            bx, by = self._entity_center(b, True)
            d = math.hypot(bx - unit.pixel_x, by - unit.pixel_y)
            if d > self.attack_range_px:
                continue
            if best_d is None or d < best_d:
                best_d, best = d, (bid, True)

        return best

    # ---------------------------------------------------------------- утилиты
    def _get_entity(self, eid, is_building: bool):
        if is_building:
            return self.buildings.get(eid)
        return self.units.get(eid)

    @staticmethod
    def _entity_center(entity, is_building: bool) -> Tuple[float, float]:
        if is_building:
            return ((entity.grid_x + entity.width / 2.0) * TILE_SIZE,
                    (entity.grid_y + entity.height / 2.0) * TILE_SIZE)
        return (entity.pixel_x, entity.pixel_y)

    @staticmethod
    def _pick_projectile_kind(attacker: Unit) -> str:
        role = (attacker.stats or {}).get("triad_role")
        if role == "artillery":
            return "ballista_bolt"
        if role == "ranged":
            return "arrow"
        return "axe"