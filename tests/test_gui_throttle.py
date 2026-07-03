"""ProgressThrottle: rate-limits progress signals without dropping the first update.

Pure logic — no Qt needed (importing hssk_gui.workers for helper classes is the established
pattern, e.g. test_gui_i18n.py). A fake clock drives it so the test never sleeps.
"""

from __future__ import annotations

from hssk_gui.workers import ProgressThrottle


class _FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_first_call_always_passes():
    throttle = ProgressThrottle(interval_s=0.1, clock=_FakeClock())
    assert throttle.allow() is True


def test_second_call_within_interval_is_blocked():
    clock = _FakeClock()
    throttle = ProgressThrottle(interval_s=0.1, clock=clock)
    assert throttle.allow() is True
    clock.advance(0.05)
    assert throttle.allow() is False


def test_call_after_interval_passes_again():
    clock = _FakeClock()
    throttle = ProgressThrottle(interval_s=0.1, clock=clock)
    assert throttle.allow() is True
    clock.advance(0.1)
    assert throttle.allow() is True


def test_long_sequence_allows_about_one_per_interval():
    clock = _FakeClock()
    throttle = ProgressThrottle(interval_s=0.1, clock=clock)
    allowed = 0
    # 1000 ticks of 0.01 s = 10 s of wall time → ~1 pass per 0.1 s interval.
    for _ in range(1000):
        if throttle.allow():
            allowed += 1
        clock.advance(0.01)
    assert 90 <= allowed <= 110
