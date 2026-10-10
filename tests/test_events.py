import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from backend.events import EventBus


def test_subscribe_and_emit():
    bus = EventBus()
    received = []
    bus.subscribe("x", lambda p: received.append(p))
    bus.emit("x", {"v": 1})
    bus.emit("x", {"v": 2})
    assert received == [{"v": 1}, {"v": 2}]


def test_no_subscribers_no_error():
    bus = EventBus()
    bus.emit("nobody_listens", {"a": 1})   # no raise


def test_unsubscribe_removes_callback():
    bus = EventBus()
    received = []
    cb = lambda p: received.append(p)
    bus.subscribe("x", cb)
    bus.emit("x", {"v": 1})
    bus.unsubscribe("x", cb)
    bus.emit("x", {"v": 2})
    assert received == [{"v": 1}]
    assert bus.subscriber_count("x") == 0


def test_clear_removes_all():
    bus = EventBus()
    bus.subscribe("x", lambda p: None)
    bus.subscribe("y", lambda p: None)
    bus.clear()
    assert bus.subscriber_count("x") == 0
    assert bus.subscriber_count("y") == 0


def test_multiple_callbacks_receive_payload():
    bus = EventBus()
    a, b = [], []
    bus.subscribe("x", lambda p: a.append(p))
    bus.subscribe("x", lambda p: b.append(p))
    bus.emit("x", {"v": 42})
    assert a == [{"v": 42}] and b == [{"v": 42}]