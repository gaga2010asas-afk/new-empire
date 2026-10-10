# src/backend/save_load.py
"""
NEW EMPIRE v1.5.21 — Backend Agent (Proto #8).
SaveLoadManager: JSON-сериализация полного стейта игры.
Патч v1.5.21: в CombatEngine сохраняется `cooldown_counter` вместо
устаревшего `last_attack`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .banner import Banner, BannerManager
from .church import Church
from .combat import UpgradeRegistry
from .constants import (
    SAVE_FORMAT_VERSION, SAVE_FILE_SUFFIX, SAVES_DIR,
)
from .economy import Economy, FactionEconomy, NodeKind, ResourceNode
from .entities import Building, Unit
from .events import EventBus
from .hero import Hero
from .map_data import MapData
from .tax_buffer import ColonyType, Vassal
from .unit_ai import CombatEngine, Projectile
from .vassal_ai import VassalAI
from .worker_state import WorkerController, WorkerTask


class SaveLoadError(Exception):
    pass


@dataclass
class GameStateSnapshot:
    map_data: MapData
    economy: Economy
    units: Dict[int, Unit]
    buildings: Dict[str, Building]
    upgrades: UpgradeRegistry
    vassals: Dict[int, VassalAI] = field(default_factory=dict)
    worker_controller: Optional[WorkerController] = None
    combat_engine: Optional[CombatEngine] = None
    church: Optional[Church] = None
    banner_manager: Optional[BannerManager] = None
    global_tick: int = 0


# ---------------------------------------------------------------------------
# MapData
# ---------------------------------------------------------------------------
def _ser_map(m: MapData) -> Dict[str, Any]:
    return {
        "width": int(m.width), "height": int(m.height),
        "seed": int(m.seed),
        "water_threshold": float(m.water_threshold),
        "block_threshold": float(m.block_threshold),
        "passability_dtype": str(m.passability_matrix.dtype),
        "roads_dtype": str(m.roads_matrix.dtype),
        "passability": m.passability_matrix.flatten().tolist(),
        "roads": m.roads_matrix.flatten().tolist(),
    }


def _deser_map(d: Dict[str, Any]) -> MapData:
    for key in ("width", "height", "passability", "roads"):
        if key not in d:
            raise SaveLoadError(f"MapData: отсутствует '{key}'")
    width, height = int(d["width"]), int(d["height"])
    pas = np.asarray(d["passability"],
                     dtype=np.dtype(d.get("passability_dtype", "uint8")))
    rds = np.asarray(d["roads"],
                     dtype=np.dtype(d.get("roads_dtype", "uint8")))
    if pas.size != width * height or rds.size != width * height:
        raise SaveLoadError("MapData: неверный размер матриц")

    obj = MapData.__new__(MapData)
    obj.width = width
    obj.height = height
    obj.seed = int(d.get("seed", 0))
    obj.water_threshold = float(d.get("water_threshold", 0.35))
    obj.block_threshold = float(d.get("block_threshold", 0.70))
    obj.passability_matrix = pas.reshape((height, width))
    obj.roads_matrix = rds.reshape((height, width))
    return obj


# ---------------------------------------------------------------------------
# Economy
# ---------------------------------------------------------------------------
def _ser_economy(e: Economy) -> Dict[str, Any]:
    return {
        "factions": [
            {"faction": fe.faction, "gold": fe.gold, "wood": fe.wood,
             "oil": fe.oil, "food_used": fe.food_used,
             "food_cap": fe.food_cap, "active": bool(fe.active)}
            for fe in e.factions.values()
        ],
        "nodes": [
            {"id": n.id, "kind": n.kind.value, "grid_x": n.grid_x,
             "grid_y": n.grid_y, "trips_remaining": n.trips_remaining,
             "wood_remaining": n.wood_remaining}
            for n in e.nodes.values()
        ],
    }


def _deser_economy(d: Dict[str, Any]) -> Economy:
    e = Economy()
    for fe_d in d.get("factions", []):
        fe = FactionEconomy(
            faction=fe_d["faction"], gold=int(fe_d["gold"]),
            wood=int(fe_d["wood"]), oil=int(fe_d["oil"]),
            food_used=int(fe_d["food_used"]),
            food_cap=int(fe_d["food_cap"]),
            active=bool(fe_d["active"]),
        )
        e.factions[fe.faction] = fe
    for nd in d.get("nodes", []):
        node = ResourceNode(
            id=int(nd["id"]), kind=NodeKind(nd["kind"]),
            grid_x=int(nd["grid_x"]), grid_y=int(nd["grid_y"]),
            trips_remaining=int(nd["trips_remaining"]),
            wood_remaining=int(nd["wood_remaining"]),
        )
        e.nodes[node.id] = node
    return e


# ---------------------------------------------------------------------------
# Unit / Hero
# ---------------------------------------------------------------------------
def _ser_unit(u: Unit) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "id": u.id, "faction": u.faction, "type": u.type,
        "pixel_x": float(u.pixel_x), "pixel_y": float(u.pixel_y),
        "direction": int(u.direction), "state": int(u.state),
        "hp": int(u.hp), "max_hp": int(u.max_hp),
        "is_selected": bool(u.is_selected), "owner_id": int(u.owner_id),
        "stats": dict(u.stats), "inside_mine": bool(u.inside_mine),
    }
    if isinstance(u, Hero):
        base["__type__"] = "hero"
        base["hero_level"] = int(u.hero_level)
        base["xp"] = int(u.xp)
        base["mana"] = int(u.mana)
        base["max_mana"] = int(u.max_mana)
        base["aura_color"] = list(u.aura_color)
        base["hero_role"] = u.hero_role
        base["abilities"] = list(u.abilities)
        base["cooldowns"] = dict(u._cooldowns)
        base["mana_tick_accum"] = int(u._mana_tick_accum)
    else:
        base["__type__"] = "unit"
    return base


def _deser_unit(d: Dict[str, Any]) -> Unit:
    if d.get("__type__") == "hero":
        h = Hero(
            id=int(d["id"]), faction=d["faction"], type=d["type"],
            pixel_x=float(d["pixel_x"]), pixel_y=float(d["pixel_y"]),
            direction=int(d["direction"]), state=int(d["state"]),
            hp=int(d["hp"]), max_hp=int(d["max_hp"]),
            is_selected=bool(d["is_selected"]),
            owner_id=int(d["owner_id"]),
            stats=dict(d["stats"]),
            inside_mine=bool(d.get("inside_mine", False)),
            hero_level=int(d["hero_level"]),
            xp=int(d["xp"]),
            mana=int(d["mana"]),
            max_mana=int(d["max_mana"]),
            aura_color=tuple(d["aura_color"]),
            hero_role=d["hero_role"],
            abilities=list(d["abilities"]),
        )
        h._cooldowns = dict(d.get("cooldowns", {}))
        h._mana_tick_accum = int(d.get("mana_tick_accum", 0))
        return h
    return Unit(
        id=int(d["id"]), faction=d["faction"], type=d["type"],
        pixel_x=float(d["pixel_x"]), pixel_y=float(d["pixel_y"]),
        direction=int(d["direction"]), state=int(d["state"]),
        hp=int(d["hp"]), max_hp=int(d["max_hp"]),
        is_selected=bool(d["is_selected"]), owner_id=int(d["owner_id"]),
        stats=dict(d["stats"]),
        inside_mine=bool(d.get("inside_mine", False)),
    )


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------
def _ser_building(b: Building) -> Dict[str, Any]:
    return {
        "id": b.id, "grid_x": int(b.grid_x), "grid_y": int(b.grid_y),
        "width": int(b.width), "height": int(b.height),
        "hp": int(b.hp), "max_hp": int(b.max_hp),
        "state": int(b.state), "faction": b.faction, "type": b.type,
    }


def _deser_building(d: Dict[str, Any]) -> Building:
    return Building(
        id=d["id"], grid_x=int(d["grid_x"]), grid_y=int(d["grid_y"]),
        width=int(d["width"]), height=int(d["height"]),
        hp=int(d["hp"]), max_hp=int(d["max_hp"]), state=int(d["state"]),
        faction=d["faction"], type=d["type"],
    )


# ---------------------------------------------------------------------------
# UpgradeRegistry
# ---------------------------------------------------------------------------
def _ser_upgrades(reg: UpgradeRegistry) -> List[Dict[str, Any]]:
    return [
        {"faction": s.faction, "damage_level": s.damage_level,
         "armor_level": s.armor_level}
        for s in reg._states.values()
    ]


def _deser_upgrades(items: List[Dict[str, Any]]) -> UpgradeRegistry:
    reg = UpgradeRegistry()
    for d in items:
        st = reg.register(d["faction"])
        st.damage_level = int(d["damage_level"])
        st.armor_level = int(d["armor_level"])
    return reg


# ---------------------------------------------------------------------------
# WorkerController
# ---------------------------------------------------------------------------
def _ser_worker_ctrl(wc: WorkerController) -> Dict[str, Any]:
    return {
        "tasks": [
            {"worker_id": t.worker_id, "node_id": t.node_id,
             "hall_id": t.hall_id, "node_kind": t.node_kind.value,
             "phase": t.phase, "mine_timer": t.mine_timer,
             "carry_kind": t.carry_kind, "carry_amount": t.carry_amount,
             "exit_px": t.exit_px, "exit_py": t.exit_py}
            for t in wc.tasks.values()
        ],
    }


def _deser_worker_ctrl(d: Dict[str, Any], economy: Economy,
                       map_data: MapData,
                       units: Dict[int, Unit],
                       buildings: Dict[str, Building],
                       has_lumber_mill: Callable[[str], bool]
                       ) -> WorkerController:
    wc = WorkerController(economy, map_data, units, buildings,
                          has_lumber_mill)
    for td in d.get("tasks", []):
        task = WorkerTask(
            worker_id=int(td["worker_id"]), node_id=int(td["node_id"]),
            hall_id=td["hall_id"], node_kind=NodeKind(td["node_kind"]),
            phase=td["phase"], mine_timer=int(td["mine_timer"]),
            carry_kind=td["carry_kind"],
            carry_amount=int(td["carry_amount"]),
            exit_px=float(td["exit_px"]), exit_py=float(td["exit_py"]),
        )
        wc.tasks[task.worker_id] = task
    return wc


# ---------------------------------------------------------------------------
# CombatEngine / Projectile
# ---------------------------------------------------------------------------
def _ser_projectile(p: Projectile) -> Dict[str, Any]:
    return {
        "id": p.id, "kind": p.kind, "faction": p.faction,
        "attacker_id": p.attacker_id, "target_id": p.target_id,
        "target_is_building": bool(p.target_is_building),
        "pixel_x": float(p.pixel_x), "pixel_y": float(p.pixel_y),
        "target_x": float(p.target_x), "target_y": float(p.target_y),
        "vx": float(p.vx), "vy": float(p.vy), "damage": int(p.damage),
        "hit_radius": float(p.hit_radius), "alive": bool(p.alive),
    }


def _deser_projectile(d: Dict[str, Any]) -> Projectile:
    return Projectile(
        id=int(d["id"]), kind=d["kind"], faction=d["faction"],
        attacker_id=int(d["attacker_id"]), target_id=d["target_id"],
        target_is_building=bool(d["target_is_building"]),
        pixel_x=float(d["pixel_x"]), pixel_y=float(d["pixel_y"]),
        target_x=float(d["target_x"]), target_y=float(d["target_y"]),
        vx=float(d["vx"]), vy=float(d["vy"]), damage=int(d["damage"]),
        hit_radius=float(d["hit_radius"]), alive=bool(d["alive"]),
    )


def _ser_combat(ce: CombatEngine) -> Dict[str, Any]:
    return {
        "attack_range_px": float(ce.attack_range_px),
        "projectile_speed": float(ce.projectile_speed),
        "hit_radius": float(ce.hit_radius),
        "cooldown_ticks": int(ce.cooldown_ticks),
        "attack_count": int(ce.attack_count),
        "tick": int(ce.tick),
        "next_proj_id": int(ce._next_proj_id),
        "projectiles": [_ser_projectile(p) for p in ce.projectiles],
        "cooldown_counter": {str(k): int(v)
                             for k, v in ce._cooldown_counter.items()},
        "targets": [
            {"attacker_id": int(k), "target_id": t[0],
             "target_is_building": bool(t[1])}
            for k, t in ce._targets.items()
        ],
    }


def _deser_combat(d: Dict[str, Any], units: Dict[int, Unit],
                  buildings: Dict[str, Building],
                  upgrades: UpgradeRegistry,
                  event_bus: Optional[EventBus]) -> CombatEngine:
    ce = CombatEngine(
        units=units, buildings=buildings, upgrades=upgrades,
        event_bus=event_bus,
        attack_range_px=float(d["attack_range_px"]),
        projectile_speed=float(d["projectile_speed"]),
        hit_radius=float(d["hit_radius"]),
        cooldown_ticks=int(d["cooldown_ticks"]),
    )
    ce.projectiles = [_deser_projectile(p)
                      for p in d.get("projectiles", [])]
    ce.attack_count = int(d.get("attack_count", 0))
    ce.tick = int(d.get("tick", 0))
    ce._next_proj_id = int(d.get("next_proj_id", 1))
    ce._cooldown_counter = {int(k): int(v)
                            for k, v in d.get("cooldown_counter", {}).items()}
    ce._targets = {int(t["attacker_id"]):
                   (t["target_id"], bool(t["target_is_building"]))
                   for t in d.get("targets", [])}
    return ce


# ---------------------------------------------------------------------------
# Vassal / VassalAI
# ---------------------------------------------------------------------------
def _ser_vassal(v: Vassal) -> Dict[str, Any]:
    return {
        "id": int(v.id), "faction": v.faction,
        "colony_type": v.colony_type.value,
        "hall_grid_x": int(v.hall_grid_x),
        "hall_grid_y": int(v.hall_grid_y),
        "state": int(v.state),
        "tax_buffer_gold": float(v.tax_buffer_gold),
        "tax_buffer_wood": float(v.tax_buffer_wood),
        "tax_capacity_gold": int(v.tax_capacity_gold),
        "tax_capacity_wood": int(v.tax_capacity_wood),
        "tax_timeout_ticks": int(v.tax_timeout_ticks),
        "pending_group": bool(v.pending_group),
        "colony_treasury_gold": float(v.colony_treasury_gold),
        "colony_treasury_wood": float(v.colony_treasury_wood),
    }


def _deser_vassal(d: Dict[str, Any]) -> Vassal:
    return Vassal(
        id=int(d["id"]), faction=d["faction"],
        colony_type=ColonyType(d["colony_type"]),
        hall_grid_x=int(d["hall_grid_x"]),
        hall_grid_y=int(d["hall_grid_y"]),
        state=int(d["state"]),
        tax_buffer_gold=float(d["tax_buffer_gold"]),
        tax_buffer_wood=float(d["tax_buffer_wood"]),
        tax_capacity_gold=int(d["tax_capacity_gold"]),
        tax_capacity_wood=int(d["tax_capacity_wood"]),
        tax_timeout_ticks=int(d["tax_timeout_ticks"]),
        pending_group=bool(d["pending_group"]),
        colony_treasury_gold=float(d["colony_treasury_gold"]),
        colony_treasury_wood=float(d["colony_treasury_wood"]),
    )


def _ser_vassal_ai(ai: VassalAI) -> Dict[str, Any]:
    return {
        "vassal": _ser_vassal(ai.vassal),
        "hall_id": ai.hall_id,
        "region_center": list(ai.region_center),
        "main_hall_grid": list(ai.main_hall_grid),
        "army_ids": list(ai.army_ids),
        "worker_ids": list(ai.worker_ids),
        "state": int(ai.state),
        "ticks_since_delivery": int(ai.ticks_since_delivery),
        "encircled": bool(ai.encircled),        # property → _encircled
        "breakthrough_triggered": bool(ai.breakthrough_triggered),
        "mobilization": float(ai.mobilization),
    }


def _deser_vassal_ai(d: Dict[str, Any],
                     map_data: Optional[MapData]) -> VassalAI:
    vassal = _deser_vassal(d["vassal"])
    ai = VassalAI(
        vassal=vassal, hall_id=d["hall_id"],
        region_center=tuple(d["region_center"]),
        main_hall_grid=tuple(d["main_hall_grid"]),
        map_data=map_data,
        army_ids=list(d["army_ids"]),
        worker_ids=list(d["worker_ids"]),
    )
    ai.state = int(d["state"])
    ai.ticks_since_delivery = int(d["ticks_since_delivery"])
    ai.encircled = bool(d["encircled"])         # сеттер property → _encircled
    ai.breakthrough_triggered = bool(d["breakthrough_triggered"])
    ai.mobilization = float(d["mobilization"])
    return ai


# ---------------------------------------------------------------------------
# Church
# ---------------------------------------------------------------------------
def _ser_church(c: Church) -> Dict[str, Any]:
    return {
        "id": c.id, "faction": c.faction,
        "grid_x": int(c.grid_x), "grid_y": int(c.grid_y),
        "contribution_pool": int(c.contribution_pool),
        "dead_heroes_queue": [dict(x) for x in c.dead_heroes_queue],
        "cooldown_ticks": int(c.cooldown_ticks),
        "active_revive": (dict(c.active_revive)
                          if c.active_revive is not None else None),
        "pool_fraction": float(c._pool_fraction),
    }


def _deser_church(d: Dict[str, Any]) -> Church:
    c = Church(id=d["id"], faction=d["faction"],
               grid_x=int(d["grid_x"]), grid_y=int(d["grid_y"]))
    c.contribution_pool = int(d["contribution_pool"])
    c.dead_heroes_queue = [dict(x)
                           for x in d.get("dead_heroes_queue", [])]
    c.cooldown_ticks = int(d["cooldown_ticks"])
    c.active_revive = (dict(d["active_revive"])
                       if d.get("active_revive") else None)
    c._pool_fraction = float(d.get("pool_fraction", 0.0))
    return c


# ---------------------------------------------------------------------------
# BannerManager
# ---------------------------------------------------------------------------
def _ser_banner(b: Optional[Banner]) -> Optional[Dict[str, Any]]:
    if b is None:
        return None
    return {
        "target_region_id": int(b.target_region_id),
        "target_center_px": list(b.target_center_px),
        "assigned_hero_id": int(b.assigned_hero_id),
        "state": int(b.state),
        "gathering_timer": int(b.gathering_timer),
        "mobilized_units": list(b.mobilized_units),
        "aura_radius_px": float(b.aura_radius_px),
    }


def _deser_banner(d: Optional[Dict[str, Any]]) -> Optional[Banner]:
    if d is None:
        return None
    return Banner(
        target_region_id=int(d["target_region_id"]),
        target_center_px=tuple(d["target_center_px"]),
        assigned_hero_id=int(d["assigned_hero_id"]),
        state=int(d["state"]),
        gathering_timer=int(d["gathering_timer"]),
        mobilized_units=list(d["mobilized_units"]),
        aura_radius_px=float(d["aura_radius_px"]),
    )


def _ser_banner_mgr(bm: BannerManager) -> Dict[str, Any]:
    return {
        "aura_radius_px": float(bm.aura_radius_px),
        "gathering_ticks": int(bm.gathering_ticks),
        "banner": _ser_banner(bm.banner),
    }


def _deser_banner_mgr(d: Dict[str, Any],
                      event_bus: Optional[EventBus]) -> BannerManager:
    bm = BannerManager(event_bus=event_bus,
                       aura_radius_px=float(d["aura_radius_px"]),
                       gathering_ticks=int(d["gathering_ticks"]))
    bm.banner = _deser_banner(d.get("banner"))
    return bm


# ---------------------------------------------------------------------------
# SaveLoadManager
# ---------------------------------------------------------------------------
class SaveLoadManager:
    def __init__(self, saves_dir: Path = SAVES_DIR) -> None:
        self.saves_dir = Path(saves_dir)

    def save(self, snapshot: GameStateSnapshot, name: str) -> Path:
        path = self._resolve_path(name)
        payload = self.to_dict(snapshot)
        try:
            self.saves_dir.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise SaveLoadError(
                f"Не удалось сохранить '{path}': {exc}") from exc
        return path

    def load(self, name: str, *,
             has_lumber_mill: Optional[Callable[[str], bool]] = None,
             event_bus: Optional[EventBus] = None) -> GameStateSnapshot:
        path = self._resolve_path(name)
        if not path.exists():
            raise SaveLoadError(f"Файл сейва '{path}' не найден")
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise SaveLoadError(
                f"Не удалось прочитать '{path}': {exc}") from exc
        return self.from_dict(payload,
                              has_lumber_mill=has_lumber_mill,
                              event_bus=event_bus)

    def list_saves(self) -> List[str]:
        if not self.saves_dir.exists():
            return []
        return sorted(p.stem
                      for p in self.saves_dir.glob(f"*{SAVE_FILE_SUFFIX}"))

    def to_dict(self, s: GameStateSnapshot) -> Dict[str, Any]:
        return {
            "format_version": SAVE_FORMAT_VERSION,
            "global_tick": int(s.global_tick),
            "map_data": _ser_map(s.map_data),
            "economy": _ser_economy(s.economy),
            "upgrades": _ser_upgrades(s.upgrades),
            "units": [_ser_unit(u) for u in s.units.values()],
            "buildings": [_ser_building(b) for b in s.buildings.values()],
            "vassals": [_ser_vassal_ai(ai) for ai in s.vassals.values()],
            "worker_controller": (
                _ser_worker_ctrl(s.worker_controller)
                if s.worker_controller is not None else None),
            "combat_engine": (
                _ser_combat(s.combat_engine)
                if s.combat_engine is not None else None),
            "church": (_ser_church(s.church)
                       if s.church is not None else None),
            "banner_manager": (
                _ser_banner_mgr(s.banner_manager)
                if s.banner_manager is not None else None),
        }

    def from_dict(self, payload: Dict[str, Any], *,
                  has_lumber_mill: Optional[Callable[[str], bool]] = None,
                  event_bus: Optional[EventBus] = None
                  ) -> GameStateSnapshot:
        version = int(payload.get("format_version", 0))
        if version != SAVE_FORMAT_VERSION:
            raise SaveLoadError(
                f"Версия формата {version} не поддерживается "
                f"(ожидается {SAVE_FORMAT_VERSION})")

        map_data = _deser_map(payload["map_data"])
        economy  = _deser_economy(payload["economy"])
        upgrades = _deser_upgrades(payload.get("upgrades", []))

        units: Dict[int, Unit] = {}
        for ud in payload.get("units", []):
            u = _deser_unit(ud)
            units[u.id] = u

        buildings: Dict[str, Building] = {}
        for bd in payload.get("buildings", []):
            b = _deser_building(bd)
            buildings[b.id] = b

        vassals: Dict[int, VassalAI] = {}
        for vd in payload.get("vassals", []):
            ai = _deser_vassal_ai(vd, map_data)
            vassals[ai.vassal.id] = ai

        wc = None
        if payload.get("worker_controller") is not None:
            lm = (has_lumber_mill
                  if has_lumber_mill is not None else (lambda _f: False))
            wc = _deser_worker_ctrl(payload["worker_controller"],
                                    economy, map_data, units, buildings, lm)

        ce = None
        if payload.get("combat_engine") is not None:
            ce = _deser_combat(payload["combat_engine"],
                               units, buildings, upgrades, event_bus)

        ch = (_deser_church(payload["church"])
              if payload.get("church") is not None else None)

        bm = (_deser_banner_mgr(payload["banner_manager"], event_bus)
              if payload.get("banner_manager") is not None else None)

        return GameStateSnapshot(
            map_data=map_data, economy=economy,
            units=units, buildings=buildings, upgrades=upgrades,
            vassals=vassals, worker_controller=wc, combat_engine=ce,
            church=ch, banner_manager=bm,
            global_tick=int(payload.get("global_tick", 0)),
        )

    def _resolve_path(self, name: str) -> Path:
        if not name or "/" in name or "\\" in name:
            raise SaveLoadError(f"Недопустимое имя сейва '{name}'")
        if name.endswith(SAVE_FILE_SUFFIX):
            return self.saves_dir / name
        return self.saves_dir / f"{name}{SAVE_FILE_SUFFIX}"