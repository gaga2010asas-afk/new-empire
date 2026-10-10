import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from backend.netplay import (
    LockstepNetplay, NetRole, NetplayError, NetplayNotImplemented,
    deterministic_seed,
)


def test_initial_session_role_is_none():
    n = LockstepNetplay()
    assert n.session.role == NetRole.NONE
    assert n.session.players_connected == 0


def test_start_host_sets_role():
    n = LockstepNetplay(port=7000)
    s = n.start_host()
    assert s.role == NetRole.HOST
    assert s.port == 7000
    assert s.players_connected == 1
    assert n.session.role == NetRole.HOST


def test_connect_sets_role_and_address():
    n = LockstepNetplay(port=7000)
    s = n.connect("192.168.1.5")
    assert s.role == NetRole.CLIENT
    assert s.host_address == "192.168.1.5"


def test_double_init_raises():
    n = LockstepNetplay()
    n.start_host()
    with pytest.raises(NetplayError):
        n.connect("1.2.3.4")


def test_invalid_port_raises():
    with pytest.raises(NetplayError):
        LockstepNetplay(port=0)
    with pytest.raises(NetplayError):
        LockstepNetplay(port=99999)


def test_lockstep_methods_are_stubs():
    n = LockstepNetplay()
    n.start_host()
    with pytest.raises(NetplayNotImplemented):
        n.send_command(1, {"cmd": "move"})
    with pytest.raises(NetplayNotImplemented):
        n.poll_remote_commands()


def test_pause_flag_toggle():
    n = LockstepNetplay()
    n.start_host()
    assert n.session.paused is False
    n.set_paused(True)
    assert n.session.paused is True


def test_close_clears_session():
    n = LockstepNetplay()
    n.start_host()
    n.close()
    assert n.session.role == NetRole.NONE
    assert n.session.players_connected == 0


def test_deterministic_seed_is_stable():
    a = deterministic_seed(1234, [2, 1])
    b = deterministic_seed(1234, [1, 2])   # порядок слотов — не важен
    assert a == b
    c = deterministic_seed(1234, [1, 3])
    assert a != c


def test_deterministic_seed_empty_slots_raises():
    with pytest.raises(NetplayError):
        deterministic_seed(1, [])