# src/backend/content_loader.py
"""
NEW EMPIRE v1.5 — Backend Agent.
ContentLoader: чтение JSON-контента из data/, оверрайд через mods/<dlc>/.
Канон: MASTER ARCHITECTURE BRIEF v1.5 (раздел 4.2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .constants import (
    BUILDING_REQUIRED_FIELDS,
    DATA_DIR,
    FACTION_IDS,
    JSON_SUFFIX,
    MANIFEST_FILENAME,
    MODS_DIR,
    TRIAD_ROLES,
    UNIT_REQUIRED_FIELDS,
)


class ContentError(Exception):
    """Ошибка загрузки/валидации контента."""


@dataclass
class LoadReport:
    units_loaded: int = 0
    buildings_loaded: int = 0
    factions_loaded: int = 0
    mods_applied: int = 0
    warnings: List[str] = field(default_factory=list)


class ContentLoader:
    """
    Хранит словари контента: units, buildings, factions (ключ = id).
    Порядок: data/, затем mods/*/ (оверрайд по id).
    Mod действителен, если в его корне есть manifest.json.
    """

    def __init__(self,
                 data_dir: Path = DATA_DIR,
                 mods_dir: Path = MODS_DIR) -> None:
        self.data_dir = Path(data_dir)
        self.mods_dir = Path(mods_dir)
        self.units: Dict[str, Dict[str, Any]] = {}
        self.buildings: Dict[str, Dict[str, Any]] = {}
        self.factions: Dict[str, Dict[str, Any]] = {}
        self.report = LoadReport()

    # ------------------------------------------------------------------ API
    def load_all(self) -> LoadReport:
        """Сканирует data/, затем mods/. Возвращает LoadReport."""
        self.units.clear(); self.buildings.clear(); self.factions.clear()

        self._load_dir(self.data_dir / "units",     self.units,     self._validate_unit)
        self._load_dir(self.data_dir / "buildings", self.buildings, self._validate_building)
        self._load_dir(self.data_dir / "factions",  self.factions,  self._validate_faction)

        if self.mods_dir.exists():
            for mod_dir in sorted(p for p in self.mods_dir.iterdir() if p.is_dir()):
                if not (mod_dir / MANIFEST_FILENAME).exists():
                    continue
                self._apply_mod(mod_dir)
                self.report.mods_applied += 1

        self.report.units_loaded     = len(self.units)
        self.report.buildings_loaded = len(self.buildings)
        self.report.factions_loaded  = len(self.factions)
        return self.report

    def get_unit(self, unit_id: str) -> Dict[str, Any]:
        if unit_id not in self.units:
            raise ContentError(f"Юнит '{unit_id}' не найден")
        return self.units[unit_id]

    def get_building(self, building_id: str) -> Dict[str, Any]:
        if building_id not in self.buildings:
            raise ContentError(f"Здание '{building_id}' не найдено")
        return self.buildings[building_id]

    def get_faction(self, faction_id: str) -> Dict[str, Any]:
        if faction_id not in self.factions:
            raise ContentError(f"Фракция '{faction_id}' не найдена")
        return self.factions[faction_id]

    # ------------------------------------------------------------ внутреннее
    def _load_dir(self,
                  directory: Path,
                  target: Dict[str, Dict[str, Any]],
                  validator) -> None:
        if not directory.exists():
            return
        for path in sorted(directory.glob(f"*{JSON_SUFFIX}")):
            entry = self._load_json(path)
            validator(entry, path)
            target[entry["id"]] = entry

    def _apply_mod(self, mod_dir: Path) -> None:
        for sub, target, validator in (
            ("units",     self.units,     self._validate_unit),
            ("buildings", self.buildings, self._validate_building),
            ("factions",  self.factions,  self._validate_faction),
        ):
            sub_dir = mod_dir / sub
            if not sub_dir.exists():
                continue
            for path in sorted(sub_dir.glob(f"*{JSON_SUFFIX}")):
                entry = self._load_json(path)
                validator(entry, path)
                target[entry["id"]] = entry

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise ContentError(f"Не удалось прочитать {path}: {exc}") from exc

    @staticmethod
    def _require_fields(entry: Dict[str, Any], path: Path,
                        required: Tuple[str, ...]) -> None:
        if not isinstance(entry, dict):
            raise ContentError(f"{path}: корень JSON должен быть объектом")
        for f in required:
            if f not in entry:
                raise ContentError(f"{path}: отсутствует обязательное поле '{f}'")

    def _validate_unit(self, entry: Dict[str, Any], path: Path) -> None:
        self._require_fields(entry, path, UNIT_REQUIRED_FIELDS)
        if entry["faction"] not in FACTION_IDS:
            raise ContentError(f"{path}: неизвестная фракция '{entry['faction']}'")
        if entry["triad_role"] not in TRIAD_ROLES:
            raise ContentError(f"{path}: неизвестная роль '{entry['triad_role']}'")
        if not isinstance(entry["cost"], dict):
            raise ContentError(f"{path}: cost должен быть объектом")

    def _validate_building(self, entry: Dict[str, Any], path: Path) -> None:
        self._require_fields(entry, path, BUILDING_REQUIRED_FIELDS)
        if entry["faction"] not in FACTION_IDS:
            raise ContentError(f"{path}: неизвестная фракция '{entry['faction']}'")
        if not isinstance(entry["cost"], dict):
            raise ContentError(f"{path}: cost должен быть объектом")
        if int(entry["grid_width"]) < 1 or int(entry["grid_height"]) < 1:
            raise ContentError(f"{path}: grid_width/grid_height должны быть >= 1")

    def _validate_faction(self, entry: Dict[str, Any], path: Path) -> None:
        self._require_fields(entry, path, ("id",))
        if entry["id"] not in FACTION_IDS:
            raise ContentError(f"{path}: id фракции '{entry['id']}' неизвестен")