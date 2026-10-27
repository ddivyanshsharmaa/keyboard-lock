"""Run on any OS: python -m unittest discover -s tests -v."""

import argparse
import errno
import types
import unittest
from unittest.mock import Mock, patch

from keyboard_lock_core import HeldKeys, SafetyLock, minutes_value
from keyboard_lock_linux import LinuxLock, has_pointer, is_keyboard


class KeyTests(unittest.TestCase):
    def test_shortcut_repeat_and_both_sides(self):
        held = HeldKeys()
        held.update(("one", 1), True, "ctrl")
        held.update(("two", 2), True, "ctrl")
        held.update(("one", 1), False, "ctrl")
        held.update(("two", 3), True, "alt")
        self.assertTrue(held.update(("one", 4), True, "k"))
        self.assertFalse(held.update(("one", 4), True, "k"))
        held.update(("one", 4), False, "k")
        self.assertTrue(held.update(("one", 4), True, "k"))
        held.remove_device("two")
        held.update(("one", 4), False, "k")
        self.assertFalse(held.update(("one", 4), True, "k"))

    def test_only_chord_triggers_and_released_keys_are_discarded(self):
        held = HeldKeys()
        for code, role in enumerate((None, "ctrl", "k", "alt")):
            self.assertFalse(held.update((0, code), True, role))
        for code in range(4):
            held.update((0, code), False)
        self.assertEqual(held.keys, {})


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.mono, self.wall = 100, 1000
        self.lock = SafetyLock(monotonic=lambda: self.mono, wall=lambda: self.wall)

    def lock_now(self):
        self.lock.toggle()
        self.lock.poll(False)

    def test_waits_for_key_releases_in_both_directions(self):
        self.lock.toggle()
        self.lock.poll(True)
        self.assertEqual(self.lock.state, "arming")
        self.lock.poll(False)
        self.assertTrue(self.lock.blocked)
        self.lock.toggle()
        self.lock.poll(True)
        self.assertEqual(self.lock.state, "releasing")
        self.lock.poll(False)
        self.assertEqual(self.lock.state, "unlocked")

    def test_default_ten_minutes_expires_even_with_keys_held(self):
        self.lock_now()
        self.mono += 599
        self.lock.poll(True)
        self.assertTrue(self.lock.blocked)
        self.mono += 1
        self.lock.poll(True)
        self.assertFalse(self.lock.blocked)

    def test_sleep_and_clock_rollback(self):
        self.lock_now()
        self.wall += 601  # Suspend: monotonic clock need not advance.
        self.lock.poll(True)
        self.assertFalse(self.lock.blocked)
        self.lock_now()
        self.wall -= 3600
        self.mono += 600
        self.lock.poll(True)
        self.assertFalse(self.lock.blocked)

    def test_mouse_unlock_cancel_and_timeout_change(self):
        self.lock.toggle()
        self.lock.toggle()
        self.assertEqual(self.lock.state, "unlocked")
        self.lock_now()
        self.mono += 500
        self.lock.set_minutes(1)
        self.mono += 59
        self.lock.poll(True)
        self.assertTrue(self.lock.blocked)
        self.mono += 1
        self.lock.poll(True)
        self.assertFalse(self.lock.blocked)
        self.lock_now()
        self.lock.unlock()
        self.assertIsNone(self.lock.deadline)

    def test_minutes_validation(self):
        for value in ("1", "10", "240"):
            self.assertEqual(minutes_value(value), int(value))
        for value in ("0", "241", "-1", "cat", "1.5"):
            with self.assertRaises(argparse.ArgumentTypeError):
                minutes_value(value)


# A deliberately small evdev stand-in: never opens or grabs a real device.
CODES = types.SimpleNamespace(EV_KEY=1, EV_REL=2, EV_ABS=3, EV_SYN=0, SYN_DROPPED=3,
                              KEY_A=30, KEY_K=37, KEY_ENTER=28, KEY_LEFTCTRL=29,
                              KEY_RIGHTCTRL=97, KEY_LEFTALT=56, KEY_RIGHTALT=100,
                              BTN_MISC=256)
CODES.KEY = dict.fromkeys((30, 37, 28, 29, 97, 56, 100, 464))
CODES.BTN = dict.fromkeys((256, 272, 273))


class LinuxTests(unittest.TestCase):
    def setUp(self):
        self.app = LinuxLock(types.SimpleNamespace(ecodes=CODES), 10)
        self.addCleanup(self.app.selector.close)

    def device(self):
        device = Mock()
        device.active_keys.return_value = []
        return device

    def test_pointer_and_hybrid_nodes_are_never_eligible(self):
        keyboard = {1: [30, 37, 28, 29, 56]}
        self.assertTrue(is_keyboard(keyboard, CODES))
        self.assertFalse(has_pointer(keyboard, CODES))
        self.assertFalse(is_keyboard({1: [272, 273], 2: [0, 1]}, CODES))
        self.assertTrue(is_keyboard({1: [464]}, CODES))
        self.assertFalse(has_pointer({1: [464]}, CODES))
        for extra in ({2: [0]}, {3: [0]}, {1: keyboard[1] + [272]}):
            self.assertTrue(has_pointer(keyboard | extra, CODES))

    def test_partial_grab_rolls_back_all_successful_grabs(self):
        first, second = self.device(), self.device()
        second.grab.side_effect = OSError(errno.EBUSY, "busy")
        self.app.devices = {"a": first, "b": second}
        self.app.safety.toggle()
        self.app.safety.poll(False)
        with self.assertRaises(OSError):
            self.app.grab_all()
        first.ungrab.assert_called_once()
        self.assertFalse(self.app.safety.blocked)
        self.assertEqual(self.app.grabbed, set())

    def test_key_press_during_grab_returns_to_release_wait(self):
        device = self.device()
        device.active_keys.return_value = [30]
        self.app.devices = {"a": device}
        self.app.safety.toggle()
        self.app.safety.poll(False)
        self.app.grab_all()
        device.ungrab.assert_called_once()
        self.assertEqual(self.app.safety.state, "arming")

    def test_syn_dropped_is_fatal_instead_of_using_stale_keys(self):
        device = self.device()
        device.read.return_value = [types.SimpleNamespace(type=0, code=3)]
        self.app.devices = {"a": device}
        with self.assertRaisesRegex(RuntimeError, "overflow"):
            self.app.read("a")

    def test_shortcut_uses_events_without_repeating(self):
        device = self.device()
        device.read.return_value = [types.SimpleNamespace(type=1, code=code, value=value)
                                   for code, value in ((29, 1), (56, 1), (37, 1), (37, 2))]
        self.app.devices = {"a": device}
        self.app.read("a")
        self.assertEqual(self.app.safety.state, "arming")

    def test_hotplug_unlocks_before_admitting_new_keyboard(self):
        old, new = self.device(), self.device()
        new.capabilities.return_value = {1: [30, 37, 28, 29, 56]}
        self.app.devices = {"old": old}
        self.app.grabbed = {"old"}
        self.app.safety.toggle()
        self.app.safety.poll(False)
        self.app.evdev.InputDevice = Mock(return_value=new)
        with patch("keyboard_lock_linux.glob.glob", return_value=["old", "new"]), \
                patch.object(self.app.selector, "register"):
            self.app.scan()
        old.ungrab.assert_called_once()
        self.assertFalse(self.app.safety.blocked)
        self.assertIn("new", self.app.devices)

    def test_read_permission_failure_does_not_silently_skip_devices(self):
        self.app.evdev.InputDevice = Mock(side_effect=PermissionError("input access denied"))
        with patch("keyboard_lock_linux.glob.glob", return_value=["denied"]):
            with self.assertRaises(PermissionError):
                self.app.scan()

    def test_exit_always_releases_grabs_and_closes_devices(self):
        device = self.device()
        self.app.devices = {"a": device}
        self.app.grabbed = {"a"}
        self.app.scan = Mock(side_effect=RuntimeError("scan failed"))
        with patch.object(self.app.selector, "unregister"):
            with self.assertRaisesRegex(RuntimeError, "scan failed"):
                self.app.run()
        device.ungrab.assert_called_once()
        device.close.assert_called_once()
        self.assertEqual(self.app.devices, {})

    def test_event_loop_timeout_releases_device_with_a_key_held(self):
        device = self.device()
        self.app.devices = {"a": device}
        self.app.grabbed = {"a"}
        self.app.safety.toggle()
        self.app.safety.poll(False)
        self.app.held.update(("a", 30), True)
        self.app.safety.deadline = 0
        self.app.scan = Mock()
        self.app.open_window = Mock()

        def stop_after_poll(**_):
            self.app.running = False
            return []

        with patch.object(self.app.selector, "select", side_effect=stop_after_poll), \
                patch.object(self.app.selector, "unregister"):
            self.app.run()
        device.ungrab.assert_called_once()
        self.assertFalse(self.app.safety.blocked)


if __name__ == "__main__":
    unittest.main()
