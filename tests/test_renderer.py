from types import SimpleNamespace

import pygame
import pytest

from src.frontend.camera import Camera, TILE_SIZE
from src.frontend.fx import FXPool
from src.frontend.renderer import (
    Renderer,
    BannerRenderState,
    BUILDING_CONSTRUCTING,
    BUILDING_ACTIVE,
    STATE_DEAD,
    ANIM_FRAME_TICKS,
    SELECTION_RING_COLOR,
)


class FakeMap:
    def __init__(self, w, h, default=0, roads=None):
        self.width = w
        self.height = h
        self._default = default
        self._cells = {}
        self._roads = dict(roads or {})

    def set(self, layer, x, y, idx):
        self._cells[(layer, x, y)] = idx

    def get_tile_at(self, layer, x, y):
        return self._cells.get((layer, x, y), self._default)

    def get_road_at(self, x, y):
        return self._roads.get((x, y), 0)


class FakeAssets:
    def __init__(self, tile_color=(10, 200, 10)):
        self.tile = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self.tile.fill(tile_color)
        self.tile_calls = 0
        self.building = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self.building.fill((200, 100, 40))
        self.unit = pygame.Surface((128, 128), pygame.SRCALPHA)
        self.unit.fill((240, 240, 240))
        self.projectile = pygame.Surface((12, 12), pygame.SRCALPHA)
        self.projectile.fill((255, 200, 80))
        self._shadow_cache = {}
        self._frames = [self.unit]

    def set_unit_frames(self, count):
        self._frames = []
        for i in range(count):
            s = pygame.Surface((128, 128), pygame.SRCALPHA)
            s.fill((10 + i * 30, 240, 240))
            self._frames.append(s)

    def get_tile(self, index):
        if index is None or index < 0:
            return None
        self.tile_calls += 1
        return self.tile

    def get_building_frame(self, key, frame_index=0):
        return self.building

    def get_unit_frames(self, key, anim, direction):
        return list(self._frames)

    def get_unit_frame(self, key, anim, direction, frame_index=0):
        return self._frames[frame_index % len(self._frames)]

    def get_shadow_ellipse(self, w, h):
        key = (int(w), int(h))
        surf = self._shadow_cache.get(key)
        if surf is None:
            surf = pygame.Surface(key, pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (0, 0, 0, 90), (0, 0, key[0], key[1]))
            self._shadow_cache[key] = surf
        return surf

    def get_projectile_sprite(self, key):
        if key in ("arrow", "axe", "ballista_bolt", "cannon_ball"):
            return self.projectile
        return None


def _unit(**kw):
    base = dict(
        id=1, pixel_x=200, pixel_y=200, direction=0, state=0,
        hp=30, max_hp=30, type="peasant", faction="human",
        is_selected=False,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _building(**kw):
    base = dict(
        grid_x=2, grid_y=3, width=1, height=1,
        hp=100, max_hp=100, state=BUILDING_ACTIVE,
        type="town_hall", faction="human",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _projectile(**kw):
    base = dict(pixel_x=300, pixel_y=300, type="arrow")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def surf():
    return pygame.Surface((1024, 768))


# --- базовые ----------------------------------------------------------------

def test_visible_bounds_at_origin():
    cam = Camera(1024, 768)
    r = Renderer()
    assert r.visible_tile_bounds(cam, 1024, 768, 64, 64) == (0, 0, 7, 5)


def test_visible_bounds_scrolled():
    cam = Camera(1024, 768)
    cam.camera_x = 300.0
    cam.camera_y = 200.0
    r = Renderer()
    assert r.visible_tile_bounds(cam, 1024, 768, 64, 64) == (2, 1, 10, 7)


def test_render_world_draws_only_visible(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    r.render_world(surf, cam, FakeMap(64, 64), a, layer=0)
    assert a.tile_calls == 48


# --- Z-order -----------------------------------------------------------------

def test_render_scene_z_order():
    r = Renderer()
    order = []
    r.render_world = lambda *a, **k: order.append("world")
    r.render_shadows = lambda *a, **k: order.append("shadows")
    r.render_hero_auras = lambda *a, **k: order.append("auras")
    r.render_selection_rings = lambda *a, **k: order.append("rings")
    r.render_buildings = lambda *a, **k: order.append("buildings")
    r.render_units = lambda *a, **k: order.append("units")
    r.render_column_markers = lambda *a, **k: order.append("columns")
    r.render_banner_hero_indicator = lambda *a, **k: order.append("banner")
    r.render_projectiles = lambda *a, **k: order.append("projectiles")
    r.render_fx = lambda *a, **k: order.append("fx")
    r.render_hp_bars = lambda *a, **k: order.append("hp")
    r.render_progress_bars = lambda *a, **k: order.append("progress")
    r.render_scene(
        pygame.Surface((100, 100)), None, None, None, [], [],
        projectiles=[_projectile()], fx_pool=FXPool(),
    )
    assert order == [
        "world", "shadows", "auras", "rings", "buildings", "units",
        "columns", "banner", "projectiles", "fx", "hp", "progress",
    ]


# --- HP-бары ----------------------------------------------------------------

def test_hp_bar_skipped_when_full(surf):
    r = Renderer()
    before = surf.copy()
    r.draw_hp_bar(surf, 10, 10, hp=100, max_hp=100)
    assert pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(before, "RGBA")


def test_hp_bar_drawn_when_damaged(surf):
    r = Renderer()
    before = surf.copy()
    r.draw_hp_bar(surf, 10, 10, hp=50, max_hp=100)
    assert pygame.image.tobytes(surf, "RGBA") != pygame.image.tobytes(before, "RGBA")


def test_hp_bar_not_drawn_for_dead_unit(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    before = surf.copy()
    r.render_hp_bars(surf, cam, [_unit(hp=0, max_hp=30, state=STATE_DEAD)], [])
    assert pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(before, "RGBA")


def test_hp_bar_not_drawn_for_full_hp_unit(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    before = surf.copy()
    r.render_hp_bars(surf, cam, [_unit(hp=30, max_hp=30)], [])
    assert pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(before, "RGBA")


def test_hp_bar_drawn_for_damaged_unit(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    before = surf.copy()
    r.render_hp_bars(surf, cam, [_unit(hp=15, max_hp=30)], [])
    assert pygame.image.tobytes(surf, "RGBA") != pygame.image.tobytes(before, "RGBA")


def test_hp_bar_not_drawn_for_full_hp_building(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    before = surf.copy()
    r.render_hp_bars(surf, cam, [], [_building(hp=100, max_hp=100)])
    assert pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(before, "RGBA")


def test_hp_bar_drawn_for_damaged_building(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    before = surf.copy()
    r.render_hp_bars(surf, cam, [], [_building(hp=60, max_hp=100)])
    assert pygame.image.tobytes(surf, "RGBA") != pygame.image.tobytes(before, "RGBA")


# --- прогресс ---------------------------------------------------------------

def test_progress_bar_only_when_constructing(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    b_active = _building(state=BUILDING_ACTIVE, hp=100, max_hp=100)
    b_active.build_progress = 0.5
    before = surf.copy()
    r.render_progress_bars(surf, cam, [b_active])
    assert pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(before, "RGBA")

    b_cons = _building(state=BUILDING_CONSTRUCTING, hp=1, max_hp=100)
    b_cons.build_progress = 0.5
    r.render_progress_bars(surf, cam, [b_cons])
    assert pygame.image.tobytes(surf, "RGBA") != pygame.image.tobytes(before, "RGBA")


def test_progress_bar_handles_out_of_range_progress(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    b = _building(state=BUILDING_CONSTRUCTING, hp=1, max_hp=100)
    b.build_progress = 5.0
    r.render_progress_bars(surf, cam, [b])


# --- тень --------------------------------------------------------------------

def test_shadow_rendering_uses_cached_surface(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    r.render_shadows(surf, cam, [_unit()], [_building()], a)
    r.render_shadows(surf, cam, [_unit()], [_building()], a)
    assert len(a._shadow_cache) == 2


# --- юниты ---------------------------------------------------------------

def test_render_units_frame_stable_across_same_tick(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    a.set_unit_frames(4)
    u = _unit()
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u], a, tick=0)
    first = pygame.image.tobytes(surf, "RGBA")
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u], a, tick=0)
    second = pygame.image.tobytes(surf, "RGBA")
    assert first == second


def test_render_units_frame_changes_with_tick(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    a.set_unit_frames(4)
    u = _unit(id=0)
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u], a, tick=0)
    first = pygame.image.tobytes(surf, "RGBA")
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u], a, tick=ANIM_FRAME_TICKS)
    second = pygame.image.tobytes(surf, "RGBA")
    assert first != second


# --- tint (v1.5.17) ----------------------------------------------------------

def test_unit_tint_applied_when_present(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()

    u_plain = _unit(id=1, pixel_x=400, pixel_y=400)
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u_plain], a, tick=0)
    plain_px = surf.get_at((400, 400))

    u_tinted = _unit(id=1, pixel_x=400, pixel_y=400, tint=(255, 80, 80))
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u_tinted], a, tick=0)
    tinted_px = surf.get_at((400, 400))

    assert plain_px != tinted_px


def test_unit_tint_not_applied_without_tint(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    u = _unit(id=1, pixel_x=400, pixel_y=400)
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u], a, tick=0)
    px1 = surf.get_at((400, 400))
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u], a, tick=0)
    px2 = surf.get_at((400, 400))
    assert px1 == px2


def test_unit_tint_cached_and_source_not_mutated():
    r = Renderer()
    src = pygame.Surface((16, 16), pygame.SRCALPHA)
    src.fill((200, 200, 200, 255))
    before = pygame.image.tobytes(src, "RGBA")
    t1 = r._tinted_surface(src, (255, 80, 80))
    t2 = r._tinted_surface(src, (255, 80, 80))
    assert t1 is t2
    after = pygame.image.tobytes(src, "RGBA")
    assert before == after


def test_tint_add_brightens_red_channel():
    r = Renderer()
    src = pygame.Surface((4, 4), pygame.SRCALPHA)
    src.fill((100, 100, 100, 255))
    tinted = r._tinted_surface(src, (255, 0, 0))
    px_src = src.get_at((0, 0))
    px_tint = tinted.get_at((0, 0))
    assert px_tint.r > px_src.r


def test_tint_preserves_alpha():
    r = Renderer()
    src = pygame.Surface((4, 4), pygame.SRCALPHA)
    src.fill((100, 100, 100, 200))
    tinted = r._tinted_surface(src, (255, 100, 50))
    assert tinted.get_at((0, 0)).a == 200


def test_unit_tint_from_stats_dict(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    u_plain = _unit(id=1, pixel_x=400, pixel_y=400)
    u_stats = _unit(id=1, pixel_x=400, pixel_y=400, stats={"tint": (80, 80, 255)})
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u_plain], a, tick=0)
    plain_px = surf.get_at((400, 400))
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u_stats], a, tick=0)
    stats_px = surf.get_at((400, 400))
    assert plain_px != stats_px


# --- Фракционный fallback tint (v1.5.17) ------------------------------------

def test_raider_tint_fallback_human_is_blue(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    u = _unit(id=1, pixel_x=400, pixel_y=400, faction="human",
              stats={"is_raider": True})
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u], a, tick=0)
    px = surf.get_at((400, 400))
    assert px.b > 0


def test_raider_tint_fallback_orc_is_red(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    u = _unit(id=1, pixel_x=400, pixel_y=400, faction="orc",
              stats={"is_raider": True})
    surf.fill((0, 0, 0))
    r.render_units(surf, cam, [u], a, tick=0)
    px = surf.get_at((400, 400))
    assert px.r > 0


def test_explicit_tint_wins_over_faction_fallback():
    r = Renderer()
    u = _unit(id=1, faction="human", stats={"is_raider": True}, tint=(10, 20, 30))
    assert r._unit_tint(u) == (10, 20, 30)


# --- выделение ---------------------------------------------------------------

def test_selection_ring_drawn_for_selected_unit(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    r.render_selection_rings(surf, cam, [_unit(is_selected=True)])
    found = False
    for x in range(150, 250):
        for y in range(240, 290):
            px = surf.get_at((x, y))
            if px.r < 100 and px.g > 200 and px.b < 100:
                found = True
                break
        if found:
            break
    assert found


def test_selection_ring_skipped_when_not_selected(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_selection_rings(surf, cam, [_unit(is_selected=False)])
    assert pygame.image.tobytes(surf, "RGBA") == before


def test_selection_ring_skipped_when_dead(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_selection_rings(surf, cam, [_unit(is_selected=True, state=STATE_DEAD)])
    assert pygame.image.tobytes(surf, "RGBA") == before


# --- снаряды ---------------------------------------------------------------

def test_render_projectiles_blits_visible(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    surf.fill((0, 0, 0))
    r.render_projectiles(surf, cam, [_projectile(pixel_x=300, pixel_y=300)], a)
    assert surf.get_at((300, 300)) != pygame.Color(0, 0, 0, 255)


def test_render_projectiles_skips_unknown_type(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_projectiles(surf, cam, [_projectile(type="unknown")], a)
    assert pygame.image.tobytes(surf, "RGBA") == before


def test_render_projectiles_offscreen_skipped(surf):
    cam = Camera(1024, 768)
    cam.camera_x = 10_000.0
    cam.camera_y = 10_000.0
    r = Renderer()
    a = FakeAssets()
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_projectiles(surf, cam, [_projectile(pixel_x=100, pixel_y=100)], a)
    assert pygame.image.tobytes(surf, "RGBA") == before


# --- FX ----------------------------------------------------------------

def test_render_fx_noop_on_none(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_fx(surf, cam, None)
    assert pygame.image.tobytes(surf, "RGBA") == before


def test_render_fx_delegates_to_pool(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    pool = FXPool(max_size=2)
    frames = [pygame.Surface((16, 16), pygame.SRCALPHA)]
    frames[0].fill((255, 100, 0, 255))
    pool.spawn_explosion(frames, 400, 400, tick=0)
    surf.fill((0, 0, 0))
    r.render_fx(surf, cam, pool)
    assert surf.get_at((400, 400)) != pygame.Color(0, 0, 0, 255)


# --- дороги --------------------------------------------------------------

def test_render_roads_debug_highlights_tile(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    m = FakeMap(64, 64, roads={(1, 1): 3})
    surf.fill((0, 0, 0))
    r.render_roads_debug(surf, cam, m)
    sx, sy = cam.tile_to_screen(1, 1)
    assert surf.get_at((sx + 4, sy + 4)) != pygame.Color(0, 0, 0, 255)


def test_render_roads_debug_skips_level_zero(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    m = FakeMap(64, 64, roads={(1, 1): 0})
    surf.fill((0, 0, 0))
    r.render_roads_debug(surf, cam, m)
    sx, sy = cam.tile_to_screen(1, 1)
    assert surf.get_at((sx + 4, sy + 4)) == pygame.Color(0, 0, 0, 255)


def test_render_roads_debug_reads_via_official_api(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    m = FakeMap(64, 64, roads={(3, 4): 2})
    surf.fill((0, 0, 0))
    r.render_roads_debug(surf, cam, m)
    sx, sy = cam.tile_to_screen(3, 4)
    assert surf.get_at((sx + 4, sy + 4)) != pygame.Color(0, 0, 0, 255)


# --- аура героя --------------------------------------------------------------

class _FakeAuraRenderer:
    def __init__(self):
        self.calls = 0
        self.units_seen = []

    def render(self, surface, camera, units):
        self.calls += 1
        self.units_seen = list(units)


def test_render_scene_delegates_aura_renderer(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    m = FakeMap(64, 64)
    aura = _FakeAuraRenderer()
    r.render_scene(surf, cam, m, a, [_unit()], [], aura_renderer=aura)
    assert aura.calls == 1
    assert len(aura.units_seen) == 1


def test_render_scene_without_aura_renderer_does_not_crash(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    a = FakeAssets()
    m = FakeMap(64, 64)
    r.render_scene(surf, cam, m, a, [_unit()], [], aura_renderer=None)


# --- Штандарт (v1.5.10 + v1.5.17) -------------------------------------------

def test_banner_render_state_is_active():
    assert BannerRenderState().is_active is False
    assert BannerRenderState(assigned_hero_id=5).is_active is True


def test_render_banner_hero_indicator_skips_when_inactive(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_banner_hero_indicator(surf, cam, [_unit()], BannerRenderState(), tick=0)
    assert pygame.image.tobytes(surf, "RGBA") == before


def test_render_banner_hero_indicator_draws_for_active_hero(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    hero = _unit(id=7, pixel_x=400, pixel_y=400)
    st = BannerRenderState(assigned_hero_id=7)
    r.render_banner_hero_indicator(surf, cam, [hero], st, tick=0)
    found = False
    for x in range(300, 500):
        for y in range(300, 500):
            if surf.get_at((x, y)) != pygame.Color(0, 0, 0, 255):
                found = True
                break
        if found:
            break
    assert found


def test_render_banner_hero_indicator_skips_dead_hero(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    hero = _unit(id=7, pixel_x=400, pixel_y=400, state=STATE_DEAD)
    st = BannerRenderState(assigned_hero_id=7)
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_banner_hero_indicator(surf, cam, [hero], st, tick=0)
    assert pygame.image.tobytes(surf, "RGBA") == before


def test_banner_pulse_changes_over_time(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    hero = _unit(id=7, pixel_x=400, pixel_y=400)
    st = BannerRenderState(assigned_hero_id=7)
    r.render_banner_hero_indicator(surf, cam, [hero], st, tick=0)
    frame0 = pygame.image.tobytes(surf, "RGBA")
    surf.fill((0, 0, 0))
    r.render_banner_hero_indicator(surf, cam, [hero], st, tick=40)
    frame40 = pygame.image.tobytes(surf, "RGBA")
    assert frame0 != frame40


def test_render_column_markers_draws_for_mobilized(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    u = _unit(id=3, pixel_x=400, pixel_y=400)
    st = BannerRenderState(assigned_hero_id=7, mobilized_unit_ids=(3,))
    r.render_column_markers(surf, cam, [u], st, tick=0)
    found = False
    for x in range(390, 410):
        for y in range(320, 345):
            if surf.get_at((x, y)) != pygame.Color(0, 0, 0, 255):
                found = True
                break
        if found:
            break
    assert found


def test_render_column_markers_skips_non_mobilized(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    u = _unit(id=3, pixel_x=400, pixel_y=400)
    st = BannerRenderState(assigned_hero_id=7, mobilized_unit_ids=(99,))
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_column_markers(surf, cam, [u], st, tick=0)
    assert pygame.image.tobytes(surf, "RGBA") == before


def test_render_column_markers_skips_dead(surf):
    cam = Camera(1024, 768)
    r = Renderer()
    surf.fill((0, 0, 0))
    u = _unit(id=3, pixel_x=400, pixel_y=400, state=STATE_DEAD)
    st = BannerRenderState(assigned_hero_id=7, mobilized_unit_ids=(3,))
    before = pygame.image.tobytes(surf, "RGBA")
    r.render_column_markers(surf, cam, [u], st, tick=0)
    assert pygame.image.tobytes(surf, "RGBA") == before


# --- mobilized set (v1.5.17: без кэша) --------------------------------------

def test_mobilized_set_returns_new_object_each_call():
    r = Renderer()
    s1 = r._get_mobilized_set((1, 2, 3))
    s2 = r._get_mobilized_set((1, 2, 3))
    assert s1 is not s2
    assert s1 == s2 == {1, 2, 3}


def test_mobilized_set_empty_tuple():
    r = Renderer()
    assert r._get_mobilized_set(()) == set()


def test_mobilized_set_different_content():
    r = Renderer()
    s1 = r._get_mobilized_set((1, 2, 3))
    s2 = r._get_mobilized_set((4, 5))
    assert s1 is not s2
    assert s1 == {1, 2, 3}
    assert s2 == {4, 5}