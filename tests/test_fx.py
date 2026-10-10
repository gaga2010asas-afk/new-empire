import pygame
import pytest

from src.frontend.fx import ExplosionFX, FXPool, FX_FRAME_TICKS


@pytest.fixture(scope="module", autouse=True)
def _display():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


def _frames(n=4, size=32):
    out = []
    for i in range(n):
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        s.fill((255, i * 40, 0, 255))
        out.append(s)
    return out


class FakeCamera:
    camera_x = 0.0
    camera_y = 0.0

    def world_to_screen(self, x, y):
        return (int(x), int(y))


def test_pool_reuses_free_objects():
    pool = FXPool(max_size=4)
    f = _frames(2)
    fx1 = pool.spawn_explosion(f, 10, 20, tick=0)
    assert fx1 is not None
    pool.update(tick=1000)  # fx1 умер
    assert pool.active_count() == 0
    assert pool.free_count() == 1
    fx2 = pool.spawn_explosion(f, 30, 40, tick=1000)
    assert fx2 is fx1  # тот же объект переиспользован


def test_pool_returns_none_when_full():
    pool = FXPool(max_size=1)
    f = _frames(4)  # длинная анимация
    assert pool.spawn_explosion(f, 0, 0, tick=0) is not None
    assert pool.spawn_explosion(f, 0, 0, tick=0) is None


def test_pool_returns_none_on_empty_frames():
    pool = FXPool(max_size=4)
    assert pool.spawn_explosion([], 0, 0, tick=0) is None
    assert pool.spawn_explosion(None, 0, 0, tick=0) is None


def test_explosion_updates_frames_by_tick():
    fx = ExplosionFX()
    frames = _frames(4)
    fx.reset(frames, 0, 0, tick=0)
    fx.update(tick=0)
    assert fx.frame_index == 0
    fx.update(tick=FX_FRAME_TICKS)
    assert fx.frame_index == 1
    fx.update(tick=FX_FRAME_TICKS * 2)
    assert fx.frame_index == 2


def test_explosion_dies_after_full_duration():
    fx = ExplosionFX()
    frames = _frames(3)
    fx.reset(frames, 0, 0, tick=0)
    fx.update(tick=FX_FRAME_TICKS * 3 - 1)
    assert fx.dead is False
    fx.update(tick=FX_FRAME_TICKS * 3)
    assert fx.dead is True


def test_explosion_render_does_nothing_when_dead():
    fx = ExplosionFX()
    surf = pygame.Surface((64, 64))
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGBA")
    fx.render(surf, FakeCamera())
    assert pygame.image.tobytes(surf, "RGBA") == before


def test_pool_render_draws_active_explosion():
    pool = FXPool(max_size=4)
    frames = _frames(2, size=32)
    pool.spawn_explosion(frames, 30, 30, tick=0)
    pool.update(tick=0)
    surf = pygame.Surface((64, 64))
    surf.fill((0, 0, 0))
    pool.render(surf, FakeCamera())
    # Пиксель в центре взрыва не чёрный.
    assert surf.get_at((30, 30)) != pygame.Color(0, 0, 0, 255)