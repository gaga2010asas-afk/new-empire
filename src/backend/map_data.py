# src/backend/map_data.py
"""
NEW EMPIRE v1.5.17 — Backend Agent.
MapData: матрицы проходимости/дорог, value-noise генератор,
get_tile_at, step_on_tile, trample_tile (v1.5.17), clear_block, validate_map.

Патч v1.5.17, п.3: `trample_tile(x, y)` — самостоятельный метод,
не возвращает значение (None), инкремент 0→3, вне карты и на не-GROUND
тихо выходит. Отличается от `step_on_tile`, который возвращает int.

Без pygame. Только numpy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .constants import (
    BLOCK_NOISE_THRESHOLD, MAX_MAP_SIZE, MIN_MAP_SIZE,
    REFERENCE_MAP_SIZE, ROAD_MAX_LEVEL, WATER_NOISE_THRESHOLD,
    MapLayer,
)


def _fractal_value_noise(width: int, height: int, seed: int,
                         octaves: int = 4, base_freq: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    result = np.zeros((height, width), dtype=np.float32)
    amplitude = 1.0
    total_amp = 0.0
    freq = base_freq

    for _ in range(octaves):
        gw, gh = max(2, freq), max(2, freq)
        grid = rng.random((gh, gw)).astype(np.float32)

        ys = np.linspace(0.0, gh - 1, height, dtype=np.float32)
        xs = np.linspace(0.0, gw - 1, width,  dtype=np.float32)
        y0 = np.floor(ys).astype(np.int32); x0 = np.floor(xs).astype(np.int32)
        y1 = np.clip(y0 + 1, 0, gh - 1);   x1 = np.clip(x0 + 1, 0, gw - 1)

        ty = (ys - y0)[:, None]; tx = (xs - x0)[None, :]
        ty = ty * ty * (3.0 - 2.0 * ty)
        tx = tx * tx * (3.0 - 2.0 * tx)

        top = grid[y0][:, x0] * (1.0 - tx) + grid[y0][:, x1] * tx
        bot = grid[y1][:, x0] * (1.0 - tx) + grid[y1][:, x1] * tx
        result += (top * (1.0 - ty) + bot * ty) * amplitude

        total_amp += amplitude
        amplitude *= 0.5
        freq *= 2

    result /= max(total_amp, 1e-6)
    rmin, rmax = float(result.min()), float(result.max())
    if rmax - rmin > 1e-6:
        result = (result - rmin) / (rmax - rmin)
    return result.astype(np.float32)


class MapData:
    """Индексация: matrix[y, x]. Координаты — логические (тайлы)."""

    def __init__(self,
                 width: int = REFERENCE_MAP_SIZE,
                 height: int = REFERENCE_MAP_SIZE,
                 seed: int = 0,
                 water_threshold: float = WATER_NOISE_THRESHOLD,
                 block_threshold: float = BLOCK_NOISE_THRESHOLD) -> None:
        if not (MIN_MAP_SIZE <= width <= MAX_MAP_SIZE):
            raise ValueError(
                f"width {width} вне [{MIN_MAP_SIZE}, {MAX_MAP_SIZE}]")
        if not (MIN_MAP_SIZE <= height <= MAX_MAP_SIZE):
            raise ValueError(
                f"height {height} вне [{MIN_MAP_SIZE}, {MAX_MAP_SIZE}]")
        if not (0.0 <= water_threshold < block_threshold <= 1.0):
            raise ValueError("Пороги: 0 <= water < block <= 1")

        self.width = int(width)
        self.height = int(height)
        self.seed = int(seed)
        self.water_threshold = float(water_threshold)
        self.block_threshold = float(block_threshold)

        self.passability_matrix = np.zeros((self.height, self.width),
                                            dtype=np.uint8)
        self.roads_matrix = np.zeros((self.height, self.width),
                                      dtype=np.uint8)
        self.generate()

    # --- генерация ---------------------------------------------------------
    def generate(self) -> None:
        noise = _fractal_value_noise(self.width, self.height, self.seed)
        layer = np.full((self.height, self.width), int(MapLayer.GROUND),
                        dtype=np.uint8)
        layer[noise < self.water_threshold] = int(MapLayer.WATER)
        layer[noise > self.block_threshold] = int(MapLayer.BLOCK)
        self.passability_matrix = layer
        self.roads_matrix = np.zeros((self.height, self.width),
                                      dtype=np.uint8)

    # --- контракт ----------------------------------------------------------
    def get_tile_at(self, layer: int, x: int, y: int) -> int:
        if not self.is_inside(x, y):
            return -1
        if layer == 0:
            return int(self.passability_matrix[y, x])
        if layer == 1:
            return int(self.roads_matrix[y, x])
        return -1

    # --- запросы -----------------------------------------------------------
    def is_inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get_layer(self, x: int, y: int) -> int:
        if not self.is_inside(x, y):
            return int(MapLayer.BLOCK)
        return int(self.passability_matrix[y, x])

    def is_passable(self, x: int, y: int) -> bool:
        return self.get_layer(x, y) == int(MapLayer.GROUND)

    def get_road_level(self, x: int, y: int) -> int:
        if not self.is_inside(x, y):
            return 0
        return int(self.roads_matrix[y, x])

    # --- дороги ------------------------------------------------------------
    def step_on_tile(self, x: int, y: int) -> int:
        """Инкремент накатанности до ROAD_MAX_LEVEL. Возвращает int."""
        if not self.is_inside(x, y):
            return -1
        if self.passability_matrix[y, x] != int(MapLayer.GROUND):
            return int(self.roads_matrix[y, x])
        cur = int(self.roads_matrix[y, x])
        if cur < ROAD_MAX_LEVEL:
            self.roads_matrix[y, x] = np.uint8(cur + 1)
        return int(self.roads_matrix[y, x])

    # v1.5.17, п.3: самостоятельный метод без возврата.
    def trample_tile(self, x: int, y: int) -> None:
        """
        Инкремент накатанности 0→3, вне карты и на не-GROUND — тихий выход.
        Возвращает None (в отличие от step_on_tile).
        """
        if not self.is_inside(x, y):
            return
        if self.get_layer(x, y) != int(MapLayer.GROUND):
            return
        cur = int(self.roads_matrix[y, x])
        if cur < ROAD_MAX_LEVEL:
            self.roads_matrix[y, x] = np.uint8(cur + 1)

    # --- v1.5.2: снос блока ------------------------------------------------
    def clear_block(self, x: int, y: int) -> bool:
        if not self.is_inside(x, y):
            return False
        if self.passability_matrix[y, x] == int(MapLayer.BLOCK):
            self.passability_matrix[y, x] = int(MapLayer.GROUND)
            return True
        return False

    # --- валидация ---------------------------------------------------------
    def validate_map(self,
                     starts: List[Tuple[int, int]],
                     mine_positions: Optional[List[Tuple[int, int]]] = None,
                     radius: int = 12,
                     min_forest: int = 5,
                     min_mines: int = 1) -> List[Dict[str, Any]]:
        mine_positions = mine_positions or []
        report: List[Dict[str, Any]] = []
        for (sx, sy) in starts:
            info: Dict[str, Any] = {
                "start": (sx, sy), "ground_ok": False,
                "forest_count": 0, "forest_ok": False,
                "mine_count": 0, "mines_ok": None,
            }
            if not self.is_inside(sx, sy):
                report.append(info); continue
            info["ground_ok"] = self.is_passable(sx, sy)
            y0 = max(0, sy - radius); y1 = min(self.height, sy + radius + 1)
            x0 = max(0, sx - radius); x1 = min(self.width,  sx + radius + 1)
            region = self.passability_matrix[y0:y1, x0:x1]
            cnt = int(np.sum(region == int(MapLayer.BLOCK)))
            info["forest_count"] = cnt
            info["forest_ok"] = cnt >= min_forest
            if mine_positions:
                mc = sum(1 for (mx, my) in mine_positions
                         if abs(mx - sx) <= radius and abs(my - sy) <= radius)
                info["mine_count"] = mc
                info["mines_ok"] = mc >= min_mines
            report.append(info)
        return report