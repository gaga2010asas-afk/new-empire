# src/main.py
"""NEW EMPIRE v1.5.25 — Мост Backend ↔ Frontend."""
from __future__ import annotations
import sys
from pathlib import Path
import pygame

pygame.mixer.pre_init(44100, -16, 2, 512)

from backend.constants import (
    TARGET_FPS, TILE_SIZE, MapLayer, UnitState, DATA_DIR, MODS_DIR,
)
from backend.map_data import MapData
from backend.entities import (
    Unit, Building, unit_from_content, building_from_content,
)
from backend.movement import update_unit_movement
from backend.pathfinding import PathFinder
from backend.economy import Economy
from backend.worker_state import WorkerController
from backend.unit_ai import CombatEngine
from backend.combat import UpgradeRegistry
from backend.events import EventBus
from backend.save_load import SaveLoadManager, GameStateSnapshot
from backend.content_loader import ContentLoader

from frontend.display import GameDisplay
from frontend.camera import Camera
from frontend.asset_loader import AssetLoader
from frontend.renderer import Renderer
from frontend.input_handler import InputHandler, MenuAction, GameAction
from frontend.cursors import CursorRenderer
from frontend.fx import FXPool
from frontend.audio_manager import AudioManager
from frontend.ui_menu import MainMenu
from frontend.ui_hud import GameHUD, HudState
from frontend.ui_tax import TaxPanel


WINDOW_W: int = 1024
WINDOW_H: int = 768
MAP_SIZE: int = 768
MAP_SEED: int = 42
FRACTION: str = "human"
SAVE_DIR: Path = Path("saves")
QUICKSAVE_NAME: str = "quicksave"

START_GOLD: int = 5000
START_WOOD: int = 2000
START_OIL: int = 2000

ASSET_TERRAIN = "assets/terrain/summer_hd.png"
ASSET_CURSORS = "assets/ui/cursors"

FRAME_TIME: float = 1.0 / TARGET_FPS
DEFAULT_WORKER_SPEED: float = 100.0


class Session:
    def __init__(self) -> None:
        self.state: GameStateSnapshot | None = None
        self.worker_controller: WorkerController | None = None
        self.combat_engine: CombatEngine | None = None
        self.pathfinder: PathFinder | None = None
        self.move_targets: dict[int, tuple[float, float]] = {}


def _spawn_starting_units(content_loader, map_data, economy, fraction):
    units: dict[int, Unit] = {}
    buildings: dict[str, Building] = {}
    cx = map_data.width // 2
    cy = map_data.height // 2

    peasant_data = content_loader.get_unit(
        "peasant" if fraction == "human" else "peon")
    worker = unit_from_content(
        unit_id=1, faction=fraction, content=peasant_data,
        pixel_x=(cx + 3) * TILE_SIZE + TILE_SIZE * 0.5,
        pixel_y=cy * TILE_SIZE + TILE_SIZE * 0.5,
    )
    units[1] = worker

    hall_data = content_loader.get_building(
        "town_hall" if fraction == "human" else "great_hall")
    hall = building_from_content(
        grid_x=cx, grid_y=cy, faction=fraction,
        content=hall_data, id_override="hall_1",
    )
    buildings["hall_1"] = hall
    return units, buildings


def _start_new_game(content_loader, event_bus: EventBus) -> Session:
    map_data = MapData(width=MAP_SIZE, height=MAP_SIZE, seed=MAP_SEED)

    economy = Economy()
    economy.register_faction(FRACTION,
                             gold=START_GOLD, wood=START_WOOD,
                             oil=START_OIL)
    economy.activate(FRACTION)

    units, buildings = _spawn_starting_units(
        content_loader, map_data, economy, FRACTION)

    economy.add_food_cap(FRACTION, 1)
    economy.consume_food(FRACTION, 1)

    economy.make_gold_mine(node_id=1,
                           grid_x=map_data.width // 2 + 5,
                           grid_y=map_data.height // 2,
                           town_hall_level=1)
    economy.make_tree(node_id=2,
                      grid_x=map_data.width // 2 + 7,
                      grid_y=map_data.height // 2 + 2)

    upgrades = UpgradeRegistry()
    upgrades.register(FRACTION)

    pathfinder = PathFinder(map_data)
    combat_engine = CombatEngine(
        units=units, buildings=buildings,
        upgrades=upgrades, event_bus=event_bus,
    )
    worker_controller = WorkerController(
        economy=economy, map_data=map_data,
        units=units, buildings=buildings,
        has_lumber_mill=lambda _f: False,
    )

    snap = GameStateSnapshot(
        map_data=map_data, economy=economy,
        units=units, buildings=buildings, upgrades=upgrades,
    )

    session = Session()
    session.state = snap
    session.worker_controller = worker_controller
    session.combat_engine = combat_engine
    session.pathfinder = pathfinder
    return session


def _load_game(event_bus, save_manager, name) -> Session:
    snap = save_manager.load(name, has_lumber_mill=lambda _f: False,
                             event_bus=event_bus)
    session = Session()
    session.state = snap
    session.pathfinder = PathFinder(snap.map_data)
    session.combat_engine = CombatEngine(
        units=snap.units, buildings=snap.buildings,
        upgrades=snap.upgrades, event_bus=event_bus,
    )
    session.worker_controller = WorkerController(
        economy=snap.economy, map_data=snap.map_data,
        units=snap.units, buildings=snap.buildings,
        has_lumber_mill=lambda _f: False,
    )
    return session


def _step_simulation(session: Session, dt: float) -> None:
    snap = session.state
    if snap is None:
        return
    for uid, (tx, ty) in list(session.move_targets.items()):
        u = snap.units.get(uid)
        if u is None or u.hp <= 0:
            session.move_targets.pop(uid, None)
            continue
        reached = update_unit_movement(
            u, tx, ty, snap.map_data, dt, DEFAULT_WORKER_SPEED)
        if reached:
            session.move_targets.pop(uid, None)

    if session.worker_controller is not None:
        for wid in list(session.worker_controller.tasks.keys()):
            session.worker_controller.update(
                wid, dt, base_speed=DEFAULT_WORKER_SPEED)

    if session.combat_engine is not None:
        session.combat_engine.update(dt)


def _pick_unit_at(snap, tx, ty):
    for uid, u in snap.units.items():
        if u.hp <= 0 or u.state == int(UnitState.DEAD):
            continue
        gx = int(u.pixel_x // TILE_SIZE)
        gy = int(u.pixel_y // TILE_SIZE)
        if gx == tx and gy == ty:
            return uid
    return None


def _deselect_all(snap) -> None:
    for u in snap.units.values():
        u.is_selected = False


def _selected_units(snap):
    return [u for u in snap.units.values() if u.is_selected]


def _handle_left_click(session, camera, mouse_pos) -> None:
    snap = session.state
    if snap is None:
        return
    tx, ty = camera.screen_to_tile(mouse_pos[0], mouse_pos[1])
    uid = _pick_unit_at(snap, tx, ty)
    _deselect_all(snap)
    if uid is not None:
        snap.units[uid].is_selected = True


def _handle_right_click(session, camera, mouse_pos) -> None:
    snap = session.state
    if snap is None:
        return
    tx, ty = camera.screen_to_tile(mouse_pos[0], mouse_pos[1])
    selected = _selected_units(snap)
    if not selected:
        return
    target_id = _pick_unit_at(snap, tx, ty)
    if target_id is not None:
        tgt = snap.units[target_id]
        if tgt.faction != FRACTION and session.combat_engine is not None:
            for u in selected:
                session.combat_engine.set_target(u.id, target_id, False)
            return
    px = tx * TILE_SIZE + TILE_SIZE * 0.5
    py = ty * TILE_SIZE + TILE_SIZE * 0.5
    for u in selected:
        session.move_targets[u.id] = (px, py)


def _save_quicksave(session, save_manager) -> None:
    snap = session.state
    if snap is None:
        return
    try:
        save_manager.save(snap, QUICKSAVE_NAME)
    except Exception as exc:
        print(f"[quicksave] ошибка: {exc}", file=sys.stderr)


def _draw_menu_cursor(surface) -> None:
    mx, my = pygame.mouse.get_pos()
    pts = [
        (mx, my), (mx, my + 16), (mx + 4, my + 12),
        (mx + 8, my + 18), (mx + 11, my + 16),
        (mx + 7, my + 10), (mx + 12, my + 9),
    ]
    pygame.draw.polygon(surface, (240, 230, 200), pts)
    pygame.draw.polygon(surface, (60, 50, 30), pts, 1)


def _load_all_assets(assets: AssetLoader) -> None:
    try:
        assets.load_terrain(ASSET_TERRAIN)
    except Exception as exc:
        print(f"[assets] terrain: {exc}", file=sys.stderr)
    try:
        assets.load_cursors(ASSET_CURSORS)
    except Exception as exc:
        print(f"[assets] cursors: {exc}", file=sys.stderr)


def main() -> int:
    display = GameDisplay(width=WINDOW_W, height=WINDOW_H, title="NEW EMPIRE")
    surface = display.get_surface()

    assets = AssetLoader(tile_size=TILE_SIZE)
    _load_all_assets(assets)

    renderer = Renderer(tile_size=TILE_SIZE)
    camera = Camera(WINDOW_W, WINDOW_H)
    input_h = InputHandler()
    cursors = CursorRenderer()
    fx_pool = FXPool(max_size=64)
    audio = AudioManager()

    menu = MainMenu(screen_w=WINDOW_W, screen_h=WINDOW_H)
    hud = GameHUD()
    tax_panel = TaxPanel(x=10, y=WINDOW_H - 60,
                         width=260, height=40, initial_percent=30)

    event_bus = EventBus()
    save_manager = SaveLoadManager(saves_dir=SAVE_DIR)

    content_loader = ContentLoader(DATA_DIR, MODS_DIR)
    try:
        content_loader.load_all()
    except Exception as exc:
        print(f"[content_loader] {exc}", file=sys.stderr)

    in_menu = True
    running = True
    time_scale = 1.0
    accumulator = 0.0
    session = Session()
    session_tick = 0

    try:
        menu.set_load_enabled(bool(save_manager.list_saves()))
    except Exception:
        menu.set_load_enabled(False)

    audio.play_menu()

    while running:
        events = display.pump_events()
        for ev in events:
            if ev.type == pygame.QUIT:
                running = False
                break

            if in_menu:
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    act = menu.handle_click(ev.pos)
                    if act == MenuAction.NEW_GAME:
                        session = _start_new_game(content_loader, event_bus)
                        in_menu = False
                        accumulator = 0.0
                        audio.play_peace(FRACTION)
                    elif act == MenuAction.LOAD_GAME:
                        names = save_manager.list_saves()
                        if names:
                            try:
                                session = _load_game(
                                    event_bus, save_manager, names[0])
                                in_menu = False
                                accumulator = 0.0
                                audio.play_peace(FRACTION)
                            except Exception as exc:
                                print(f"[load] {exc}", file=sys.stderr)
                    elif act == MenuAction.QUIT:
                        running = False
                        break
                elif ev.type == pygame.MOUSEMOTION:
                    menu.handle_motion(ev.pos)
                input_h.handle_menu_event(ev)
                continue

            action = input_h.handle_game_event(ev)
            if action == GameAction.PAUSE_TOGGLE:
                time_scale = 0.0 if time_scale > 0.0 else 1.0
            elif action == GameAction.CANCEL:
                _save_quicksave(session, save_manager)
                in_menu = True
                session = Session()
                audio.stop_music()
                audio.play_menu()
                menu.set_load_enabled(bool(save_manager.list_saves()))
            elif action == GameAction.LEFT_CLICK:
                _handle_left_click(session, camera, pygame.mouse.get_pos())
            elif action == GameAction.RIGHT_CLICK:
                _handle_right_click(session, camera, pygame.mouse.get_pos())

            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
                time_scale = 0.0 if time_scale > 0.0 else 1.0

        if not running:
            break

        dt_ms = 1000.0 / TARGET_FPS
        dt = dt_ms / 1000.0

        audio.update(int(dt_ms))
        if not in_menu and session.state is not None:
            camera.update(pygame.mouse.get_pos(),
                          pygame.key.get_pressed(), dt)
            camera.clamp(session.state.map_data.width,
                         session.state.map_data.height)

        if (not in_menu and session.state is not None
                and time_scale > 0.0):
            accumulator += dt * time_scale
            while accumulator >= FRAME_TIME:
                _step_simulation(session, FRAME_TIME)
                session_tick += 1
                accumulator -= FRAME_TIME
        else:
            accumulator = 0.0

        if in_menu:
            menu.render(surface)
            _draw_menu_cursor(surface)
        elif session.state is not None:
            projectiles = (session.combat_engine.projectiles
                           if session.combat_engine is not None else None)
            renderer.render_scene(
                surface, camera, session.state.map_data, assets,
                units=list(session.state.units.values()),
                buildings=list(session.state.buildings.values()),
                projectiles=projectiles,
                fx_pool=fx_pool,
                tick=session_tick,
            )
            fe = session.state.economy.get(FRACTION)
            hud.render(surface, HudState(
                gold=int(fe.gold), wood=int(fe.wood),
                food_used=int(fe.food_used), food_cap=int(fe.food_cap),
            ))
            tax_panel.render(surface)

            mx, my = pygame.mouse.get_pos()
            cursors.render(surface, (mx, my),
                           session.state.map_data, camera, assets)

        display.flip()
        display.tick(TARGET_FPS)

    display.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        pygame.quit()