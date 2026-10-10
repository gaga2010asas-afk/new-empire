# src/backend/economy.py
"""
NEW EMPIRE v1.5.2 — Backend Agent.
Economy: казна, еда, узлы ресурсов. Патч v1.5.2:
  * active=False → gather_resource/consume_food/can_hire не работают;
  * дерево = 2500 wood, N ходок по 100/125;
  * шахта — 45 тиков внутри, извлекается одна ходка за раз.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from .constants import (
    FARM_FOOD, FOOD_MAX_CAP,
    GOLD_MINE_TRIPS_BASE, GOLD_MINE_TRIPS_CASTLE, GOLD_MINE_TRIPS_KEEP,
    GOLD_PER_TRIP, TOWN_HALL_FOOD, TREE_WOOD_TOTAL,
    WOOD_PER_TRIP_BASE, WOOD_PER_TRIP_MILL,
)


class ResourceKind(str, Enum):
    GOLD = "gold"
    WOOD = "wood"
    OIL  = "oil"
    FOOD = "food"


class NodeKind(str, Enum):
    GOLD_MINE = "gold_mine"
    TREE      = "tree"


class EconomyError(Exception):
    pass


@dataclass
class FactionEconomy:
    faction: str
    gold: int = 0
    wood: int = 0
    oil: int = 0
    food_used: int = 0
    food_cap: int = 0
    active: bool = False


@dataclass
class ResourceNode:
    id: int
    kind: NodeKind
    grid_x: int
    grid_y: int
    trips_remaining: int = 0     # GOLD_MINE
    wood_remaining: int = 0      # TREE

    def is_empty(self) -> bool:
        if self.kind == NodeKind.GOLD_MINE:
            return self.trips_remaining <= 0
        if self.kind == NodeKind.TREE:
            return self.wood_remaining <= 0
        return True


class Economy:
    def __init__(self) -> None:
        self.factions: Dict[str, FactionEconomy] = {}
        self.nodes: Dict[int, ResourceNode] = {}

    # --- фракции -----------------------------------------------------------
    def register_faction(self, faction: str, gold: int = 0,
                         wood: int = 0, oil: int = 0) -> FactionEconomy:
        if faction in self.factions:
            raise EconomyError(f"Фракция '{faction}' уже зарегистрирована")
        fe = FactionEconomy(faction=faction, gold=int(gold),
                            wood=int(wood), oil=int(oil))
        self.factions[faction] = fe
        return fe

    def get(self, faction: str) -> FactionEconomy:
        if faction not in self.factions:
            raise EconomyError(f"Фракция '{faction}' не найдена")
        return self.factions[faction]

    def activate(self, faction: str) -> None:
        self.get(faction).active = True

    def is_active(self, faction: str) -> bool:
        return self.get(faction).active

    # --- ресурсы -----------------------------------------------------------
    @staticmethod
    def _peek(fe: FactionEconomy, rtype: str) -> int:
        if rtype == ResourceKind.GOLD.value: return fe.gold
        if rtype == ResourceKind.WOOD.value: return fe.wood
        if rtype == ResourceKind.OIL.value:  return fe.oil
        raise EconomyError(f"Неизвестный ресурс '{rtype}'")

    def gather_resource(self, faction: str, rtype: str, amount: int) -> int:
        if amount < 0:
            raise EconomyError("amount должен быть >= 0")
        fe = self.get(faction)
        if not fe.active:
            return self._peek(fe, rtype)
        if rtype == ResourceKind.GOLD.value:
            fe.gold += int(amount); return fe.gold
        if rtype == ResourceKind.WOOD.value:
            fe.wood += int(amount); return fe.wood
        if rtype == ResourceKind.OIL.value:
            fe.oil += int(amount); return fe.oil
        raise EconomyError(f"Неизвестный ресурс '{rtype}'")

    def can_afford(self, faction: str, gold_cost: int,
                   wood_cost: int, oil_cost: int = 0) -> bool:
        fe = self.get(faction)
        return (fe.gold >= gold_cost and fe.wood >= wood_cost
                and fe.oil >= oil_cost)

    def pay(self, faction: str, gold_cost: int, wood_cost: int,
            oil_cost: int = 0) -> None:
        if not self.can_afford(faction, gold_cost, wood_cost, oil_cost):
            raise EconomyError("Недостаточно ресурсов")
        fe = self.get(faction)
        fe.gold -= int(gold_cost)
        fe.wood -= int(wood_cost)
        fe.oil  -= int(oil_cost)

    # --- еда ---------------------------------------------------------------
    def add_food_cap(self, faction: str, amount: int) -> int:
        fe = self.get(faction)
        fe.food_cap = min(FOOD_MAX_CAP, fe.food_cap + int(amount))
        return fe.food_cap

    def remove_food_cap(self, faction: str, amount: int) -> int:
        fe = self.get(faction)
        fe.food_cap = max(0, fe.food_cap - int(amount))
        return fe.food_cap

    def consume_food(self, faction: str, amount: int = 1) -> bool:
        fe = self.get(faction)
        if not fe.active:
            return False
        if fe.food_used + int(amount) > fe.food_cap:
            return False
        fe.food_used += int(amount)
        return True

    def release_food(self, faction: str, amount: int = 1) -> None:
        fe = self.get(faction)
        fe.food_used = max(0, fe.food_used - int(amount))

    def can_hire(self, faction: str) -> bool:
        fe = self.get(faction)
        if not fe.active:
            return False
        return fe.food_used < fe.food_cap

    # --- узлы --------------------------------------------------------------
    def register_node(self, node: ResourceNode) -> None:
        if node.id in self.nodes:
            raise EconomyError(f"Узел {node.id} уже зарегистрирован")
        self.nodes[node.id] = node

    def make_gold_mine(self, node_id: int, grid_x: int, grid_y: int,
                       town_hall_level: int = 1) -> ResourceNode:
        if town_hall_level == 1:   trips = GOLD_MINE_TRIPS_BASE
        elif town_hall_level == 2: trips = GOLD_MINE_TRIPS_KEEP
        elif town_hall_level == 3: trips = GOLD_MINE_TRIPS_CASTLE
        else:
            raise EconomyError(f"Уровень ратуши {town_hall_level} вне 1..3")
        node = ResourceNode(id=node_id, kind=NodeKind.GOLD_MINE,
                            grid_x=int(grid_x), grid_y=int(grid_y),
                            trips_remaining=trips)
        self.register_node(node)
        return node

    def make_tree(self, node_id: int, grid_x: int, grid_y: int,
                  total_wood: int = TREE_WOOD_TOTAL) -> ResourceNode:
        node = ResourceNode(id=node_id, kind=NodeKind.TREE,
                            grid_x=int(grid_x), grid_y=int(grid_y),
                            wood_remaining=int(total_wood))
        self.register_node(node)
        return node

    def extract_from_gold_mine(self, node_id: int) -> int:
        node = self.nodes.get(node_id)
        if node is None:
            raise EconomyError(f"Узел {node_id} не найден")
        if node.kind != NodeKind.GOLD_MINE:
            raise EconomyError(f"Узел {node_id} не золотая шахта")
        if node.trips_remaining <= 0:
            return 0
        node.trips_remaining -= 1
        return GOLD_PER_TRIP

    def extract_wood_from_tree(self, node_id: int,
                               has_lumber_mill: bool) -> int:
        node = self.nodes.get(node_id)
        if node is None:
            raise EconomyError(f"Узел {node_id} не найден")
        if node.kind != NodeKind.TREE:
            raise EconomyError(f"Узел {node_id} не дерево")
        if node.wood_remaining <= 0:
            return 0
        norm = WOOD_PER_TRIP_MILL if has_lumber_mill else WOOD_PER_TRIP_BASE
        actual = min(norm, node.wood_remaining)
        node.wood_remaining -= actual
        return actual


# --- Реэкспорт справочника еды для зданий -----------------------------------
BUILDING_FOOD_CAP: Dict[str, int] = {
    "town_hall": TOWN_HALL_FOOD,
    "farm": FARM_FOOD,
}