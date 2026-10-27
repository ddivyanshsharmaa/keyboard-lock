"""Small, OS-neutral state helpers. Only currently held keys live in memory."""

import argparse
import time


def minutes_value(value):
    try:
        minutes = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("minutes must be an integer from 1 to 240")
    if not 1 <= minutes <= 240:
        raise argparse.ArgumentTypeError("minutes must be from 1 to 240")
    return minutes


def arguments(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--minutes", type=minutes_value, default=10,
                        help="auto-unlock after 1 to 240 minutes (default: 10)")
    return parser.parse_args()


class HeldKeys:
    def __init__(self):
        self.keys = {}

    def update(self, key, down, role=None):
        """Return True once per Ctrl+Alt+K press, including across keyboards."""
        fresh = down and key not in self.keys
        if down:
            self.keys[key] = role
        else:
            self.keys.pop(key, None)
        roles = self.keys.values()
        return fresh and role == "k" and "ctrl" in roles and "alt" in roles

    def remove_device(self, device):
        self.keys = {key: role for key, role in self.keys.items() if key[0] != device}


class SafetyLock:
    def __init__(self, minutes=10, monotonic=time.monotonic, wall=time.time):
        self.minutes = minutes
        self.monotonic, self.wall = monotonic, wall
        self.state = "unlocked"
        self.deadline = self.wall_deadline = None

    @property
    def blocked(self):
        return self.state in ("locked", "releasing")

    def toggle(self):
        self.state = {"unlocked": "arming", "arming": "unlocked",
                      "locked": "releasing", "releasing": "locked"}[self.state]

    def unlock(self):
        self.state = "unlocked"
        self.deadline = self.wall_deadline = None

    def set_minutes(self, minutes):
        self.minutes = minutes
        if self.blocked:
            self._start_timer()

    def _start_timer(self):
        self.deadline = self.monotonic() + self.minutes * 60
        self.wall_deadline = self.wall() + self.minutes * 60

    def poll(self, keys_held):
        # Wall time also catches sleep; monotonic time survives clock rollback.
        if self.blocked and (self.monotonic() >= self.deadline or
                             self.wall() >= self.wall_deadline):
            self.unlock()
        elif not keys_held:
            if self.state == "arming":
                self.state = "locked"
                self._start_timer()
            elif self.state == "releasing":
                self.unlock()
