# tools/debug_scene.py
import sys
from pathlib import Path

# Корень проекта → добавляем src/, где лежит пакет backend
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from backend.constants import DATA_DIR, MODS_DIR
from backend.content_loader import ContentLoader
from backend.map_data import MapData

# 1. Content loader
try:
    cl = ContentLoader(DATA_DIR, MODS_DIR)
    cl.load_all()
    print("[OK] content_loader загружен")
    for uid in ("peasant", "peon"):
        try:
            u = cl.get_unit(uid)
            print(f"  [OK] unit '{uid}': id={u.get('id')}, hp={u.get('hp')}")
        except Exception as e:
            print(f"  [FAIL] unit '{uid}': {e}")
    for bid in ("town_hall", "great_hall"):
        try:
            b = cl.get_building(bid)
            print(f"  [OK] building '{bid}': id={b.get('id')}")
        except Exception as e:
            print(f"  [FAIL] building '{bid}': {e}")
except Exception as e:
    print(f"[FAIL] content_loader: {e}")
    raise

# 2. MapData — какие индексы генерирует карта по слоям
md = MapData(width=768, height=768, seed=42)
print(f"\n[OK] MapData {md.width}x{md.height}")
for layer in (0, 1, 2):
    samples = {}
    for y in range(0, md.height, 16):
        for x in range(0, md.width, 16):
            idx = md.get_tile_at(layer, x, y)
            samples[idx] = samples.get(idx, 0) + 1
    keys = sorted(k for k in samples if k is not None)
    print(f"  Слой {layer}: индексы = {keys}, распределение = {samples}")