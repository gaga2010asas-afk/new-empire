# src/backend/constants.py
"""
NEW EMPIRE v1.5.16 — Backend Agent.
Константы: симуляция, экономика, налог, дороги, бой, вассалы, герои,
штандарт, сохранения, сеть, события, Enums.

Патч v1.5.16 (п.1): MIN_MAP_SIZE снижен до 1.
Проверка 64×64 — обязанность map_generator.py, не MapData.

Канон: MASTER BRIEF v1.5 (Proto #1–#8) + патчи v1.5.2 … v1.5.16.
Без pygame.
"""
from __future__ import annotations

from enum import IntEnum
from pathlib import Path


# --- Симуляция --------------------------------------------------------------
TARGET_FPS: int = 60
TILE_SIZE: int = 128                      # Священное число, неизменно
MAX_UNITS_LIMIT: int = 10000

# Патч v1.5.16, п.1: минимум для микро-сеток в юнит-тестах (8×8 и т. п.).
# Игровое требование 64×64 проверяет map_generator.py.
MIN_MAP_SIZE: int = 1
MAX_MAP_SIZE: int = 1024
REFERENCE_MAP_SIZE: int = 768
DEFAULT_WIDTH: int = 1024
DEFAULT_HEIGHT: int = 768

# --- Дороги -----------------------------------------------------------------
ROAD_MAX_LEVEL: int = 3
ROAD_SPEED_MULTIPLIER: float = 2.0
ROAD_COST_BASE: int = 10
ROAD_COST_LEVEL_1: int = 9
ROAD_COST_LEVEL_2: int = 8
ROAD_COST_LEVEL_3: int = 5
AMBUSH_MIN_ROAD_LEVEL: int = 2

# --- Пороги шума ------------------------------------------------------------
WATER_NOISE_THRESHOLD: float = 0.35
BLOCK_NOISE_THRESHOLD: float = 0.70

# --- Тайлсет (динамически считается во фронте, п.16) ------------------------
TILESET_COLS: int = 16
TILESET_ROWS: int = 24
TILESET_PIXEL_WIDTH: int = TILESET_COLS * TILE_SIZE
TILESET_PIXEL_HEIGHT: int = TILESET_ROWS * TILE_SIZE

# --- Триада -----------------------------------------------------------------
TRIAD_ROLE_INFANTRY: str = "infantry"
TRIAD_ROLE_TANK: str = "tank"
TRIAD_ROLE_ARTILLERY: str = "artillery"
TRIAD_ROLES: tuple[str, ...] = (
    TRIAD_ROLE_INFANTRY, TRIAD_ROLE_TANK, TRIAD_ROLE_ARTILLERY,
)
TRIAD_COUNTER_MULTIPLIER: float = 2.0

VASSAL_ROLE_CAVALRY: str = "cavalry"
VASSAL_ROLE_RANGED: str = "ranged"
VASSAL_ROLE_INFANTRY: str = "infantry"

# --- Пути данных/модов ------------------------------------------------------
DATA_DIR: Path = Path("data")
MODS_DIR: Path = Path("mods")
MANIFEST_FILENAME: str = "manifest.json"
JSON_SUFFIX: str = ".json"

FACTION_IDS: tuple[str, ...] = ("human", "orc")

UNIT_REQUIRED_FIELDS: tuple[str, ...] = (
    "id", "faction", "hp", "damage", "armor",
    "sprite", "cost", "build_time", "triad_role",
)
BUILDING_REQUIRED_FIELDS: tuple[str, ...] = (
    "id", "faction", "hp", "cost", "build_time",
    "grid_width", "grid_height",
)

# --- Экономика --------------------------------------------------------------
WORKER_HP: int = 30
WORKER_GOLD_COST: int = 400
WORKER_FOOD_COST: int = 1
WORKER_BUILD_TIME_TICKS: int = 2700

GOLD_MINE_TRIPS_BASE: int = 100
GOLD_MINE_TRIPS_KEEP: int = 110
GOLD_MINE_TRIPS_CASTLE: int = 120
GOLD_PER_TRIP: int = 100

WOOD_PER_TRIP_BASE: int = 100
WOOD_PER_TRIP_MILL: int = 125
TREE_WOOD_TOTAL: int = 2500

MINE_TICKS_GOLD: int = 45
MINE_TICKS_WOOD: int = 51

TOWN_HALL_FOOD: int = 1
FARM_FOOD: int = 4
FOOD_MAX_CAP: int = 100

# --- Налог (Proto #3) -------------------------------------------------------
TAX_CAPACITY_LAND_GOLD: int = 500
TAX_CAPACITY_LAND_WOOD: int = 500
TAX_CAPACITY_WATER_GOLD: int = 1000
TAX_CAPACITY_WATER_WOOD: int = 1000

TAX_TIMEOUT_TICKS: int = 10800
TAX_TIMEOUT_FILL_RATIO: float = 0.5

# --- Бой (Proto #4) ---------------------------------------------------------
ATTACK_COOLDOWN_TICKS: int = 60
PROJECTILE_HIT_RADIUS_PX: float = 16.0

MAX_UPGRADE_LEVEL: int = 3
UPGRADE_COSTS: tuple[int, int, int] = (100, 200, 400)

# --- События ----------------------------------------------------------------
EVENT_BUILDING_DESTROYED: str = "building_destroyed"
EVENT_HERO_DIED: str = "hero_died"
EVENT_HERO_LEVELED: str = "hero_leveled"
EVENT_HERO_REVIVED: str = "hero_revived"

EVENT_ATTACK_STARTED: str = "attack_started"
EVENT_BANNER_RAISED: str = "banner_raised"
EVENT_BANNER_LOST: str = "banner_lost"
EVENT_VASSAL_MOBILIZED: str = "vassal_mobilized"

# --- Вассал (Proto #5) ------------------------------------------------------
BREAKTHROUGH_TICKS: int = 18000

MIN_TOWER_SPACING: int = 4
MAX_TOWERS_CENTRAL: int = 6
MAX_TOWERS_MID: int = 8
MAX_TOWERS_BORDER: int = 10
MAX_CATAPULTS_CENTRAL: int = 3
MAX_CATAPULTS_MID: int = 0
MAX_CATAPULTS_BORDER: int = 0

DEFAULT_VASSAL_REGION_RADIUS: int = 30
CHOKEPOINT_MAX_WIDTH: int = 3
CHOKEPOINT_CLUSTER_RADIUS: int = 3

# --- Герои (Proto #6) -------------------------------------------------------
HERO_MAX_LEVEL: int = 10
HERO_ROLES: tuple[str, ...] = (
    "captain", "ranger", "paladin", "death_knight",
    "mage", "warlock", "griffin",
)
HERO_CASTER_ROLES: tuple[str, ...] = (
    "paladin", "death_knight", "mage", "warlock",
)

XP_THRESHOLDS: tuple[int, ...] = (
    0, 0, 100, 250, 450, 700, 1000, 1400, 1900, 2500, 3200,
)

XP_UNIT_KILL: int = 1
XP_HERO_KILL: int = 10
XP_BUILDING_KILL: int = 5
XP_CARAVAN_KILL: int = 3

HERO_MANA_CASTER: int = 200
HERO_MANA_CASTER_HIGH: int = 250
HERO_MANA_REGEN_TICKS: int = 12

HERO_AURA: dict[str, tuple[int, int, int, int]] = {
    "captain":      (220,  40,  40, 128),
    "ranger":       ( 40, 200,  40, 128),
    "paladin":      (255, 215,   0, 128),
    "death_knight": (140,  60, 200, 128),
    "mage":         (160,  60, 220, 128),
    "warlock":      ( 60, 120, 240, 128),
    "griffin":      (100, 200, 255, 128),
}

ABILITY_SCHEDULE: dict[str, tuple[tuple[int, str], ...]] = {
    "paladin": (
        (3, "healing"), (5, "holy_vision"), (7, "exorcism"),
    ),
    "death_knight": (
        (3, "death_coil"), (5, "haste"),
        (7, "raise_dead"), (9, "death_and_decay"),
    ),
    "mage": (
        (3, "fireball"), (5, "slow"),
        (7, "flame_shield"), (9, "blizzard"),
    ),
    "warlock": (
        (3, "fireball"), (5, "summon_spider"),
        (7, "poison_cloud"), (9, "summon_demon"),
    ),
}

# --- Церковь (Proto #6) -----------------------------------------------------
CHURCH_GOLD_COST: int = 1000
CHURCH_WOOD_COST: int = 500
CHURCH_REVIVE_COST: int = 500
CHURCH_REVIVE_COOLDOWN_TICKS: int = 10800

CHURCH_CONTRIBUTION_BASE: float = 2.54
CHURCH_TAX_HARD_BLOCK: float = 0.90

# --- Штандарт (Proto #7) ----------------------------------------------------
BANNER_GATHERING_TICKS: int = 3600
BANNER_DAMAGE_BUFF: float = 0.10
BANNER_AURA_RADIUS_PX: float = 2.0 * TILE_SIZE

MOBILIZATION_ECONOMY_TABLE: tuple[tuple[float, float], ...] = (
    (0.10, 0.00),
    (0.30, 0.05),
    (0.50, 0.15),
    (0.70, 0.40),
    (1.00, 1.00),
)

MOBILIZATION_FRACTION_CENTRAL_BORDER_FREE: float = 0.30
MOBILIZATION_FRACTION_MID_FREE: float = 0.50
MOBILIZATION_FRACTION_ENCIRCLED: float = 0.70
MOBILIZATION_FRACTION_BREAKTHROUGH: float = 1.00

# --- Сохранения (Proto #8) --------------------------------------------------
SAVES_DIR: Path = Path("saves")
SAVE_FORMAT_VERSION: int = 1
SAVE_FILE_SUFFIX: str = ".json"
AI_LEARNING_FILE: str = "ai_hard_learning.json"

# --- Сеть (Proto #8) --------------------------------------------------------
NET_DEFAULT_PORT: int = 6112
NET_MAX_PLAYERS: int = 2
# [НЕТ ДАННЫХ] — протокол lockstep и seed-деривация в DLC.

# --- Уровни сложности ИИ (Proto #8) -----------------------------------------
AI_DIFFICULTY_MIN: int = 1
AI_DIFFICULTY_MAX: int = 4

# --- Движение ---------------------------------------------------------------
DIRECTION_COUNT: int = 8
# [НЕТ ДАННЫХ] — base_speed юнита (пикс/сек). Передаётся параметром.


# --- Enums ------------------------------------------------------------------
class MapLayer(IntEnum):
    GROUND = 0
    WATER  = 1
    BLOCK  = 2


class UnitState(IntEnum):
    IDLE = 0
    WALK = 1
    MINE = 2
    ATTACK = 3
    BUILD = 4
    DEAD = 5
    RETURN = 6


class BuildingState(IntEnum):
    CONSTRUCTING = 0
    ACTIVE = 1
    DAMAGED = 2
    DESTROYED = 3


class VassalState(IntEnum):
    FREE         = 0
    ENCIRCLED    = 1
    BREAKTHROUGH = 2


class BannerState(IntEnum):
    IDLE      = 0
    GATHERING = 1
    MARCHING  = 2
    COMBAT    = 3