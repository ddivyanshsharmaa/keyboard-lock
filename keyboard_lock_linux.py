#!/usr/bin/env python3
"""Linux evdev keyboard lock. No X11/Wayland hooks, uinput or key logging."""

import glob
import selectors
import signal
import sys
import time

from keyboard_lock_core import HeldKeys, SafetyLock, arguments


def is_keyboard(capabilities, codes):
    keys = capabilities.get(codes.EV_KEY, [])
    # Include separate media-key nodes, but not pointer buttons (BTN_*).
    return any(key in codes.KEY for key in keys)


def has_pointer(capabilities, codes):
    # Never grab an event node that also carries mouse/tablet/touch input.
    return (codes.EV_REL in capabilities or codes.EV_ABS in capabilities or
            any(key in codes.BTN for key in capabilities.get(codes.EV_KEY, [])))


class LinuxLock:
    def __init__(self, evdev, minutes):
        self.evdev, self.codes = evdev, evdev.ecodes
        self.safety, self.held = SafetyLock(minutes), HeldKeys()
        self.selector = selectors.DefaultSelector()
        self.devices, self.grabbed = {}, set()
        self.running, self.window = True, None
        self.last_status = None
        self.roles = {self.codes.KEY_LEFTCTRL: "ctrl", self.codes.KEY_RIGHTCTRL: "ctrl",
                      self.codes.KEY_LEFTALT: "alt", self.codes.KEY_RIGHTALT: "alt",
                      self.codes.KEY_K: "k"}

    def open_window(self):
        try:
            import tkinter as tk
            self.window = tk.Tk()
            self.window.title("Keyboard Lock")
            self.window.attributes("-topmost", True)
            self.label = tk.Label(self.window, padx=18, pady=12)
            self.label.pack()
            tk.Button(self.window, text="Lock / unlock", command=self.toggle).pack(fill="x")
            choices = tk.StringVar(value=str(self.safety.minutes))
            tk.OptionMenu(self.window, choices, "1", "5", "10", "30", "60",
                          command=lambda value: self.safety.set_minutes(int(value))).pack(fill="x")
            tk.Button(self.window, text="Exit (unlocks)", command=self.stop).pack(fill="x")
            self.window.protocol("WM_DELETE_WINDOW", self.stop)
        except (ImportError, RuntimeError) as error:
            self.window = None
            print("Mouse window unavailable; using terminal indicator:", error, flush=True)
        except Exception as error:
            # Tk raises TclError for headless sessions (without importing Tk globally).
            self.window = None
            print("Mouse window unavailable; using terminal indicator:", error, flush=True)

    def toggle(self):
        if self.safety.blocked or self.safety.state == "arming":
            self.unlock()  # Mouse escape does not need keyboard releases.
        else:
            self.safety.toggle()

    def unlock(self):
        self.safety.unlock()
        for path in list(self.grabbed):
            device = self.devices.get(path)
            if device:
                try:
                    device.ungrab()
                except OSError:
                    # Closing the descriptor also drops EVIOCGRAB.
                    self.remove(path)
            self.grabbed.discard(path)

    def stop(self, *_):
        self.running = False

    def remove(self, path):
        device = self.devices.pop(path)
        self.selector.unregister(device.fd)
        self.grabbed.discard(path)
        device.close()
        self.held.remove_device(path)

    def scan(self):
        paths = set(glob.glob("/dev/input/event*"))
        for path in set(self.devices) - paths:
            self.remove(path)
        for path in sorted(paths - set(self.devices)):
            device = self.evdev.InputDevice(path)
            try:
                capabilities = device.capabilities()
                if not is_keyboard(capabilities, self.codes):
                    continue
                if has_pointer(capabilities, self.codes):
                    raise RuntimeError("Refusing combined keyboard/pointer node " + path +
                                       "; grabbing it would block the mouse")
                if self.safety.blocked:
                    # New hardware invalidates the set we promised to lock.
                    self.unlock()
                    print("Keyboard attached: unlocked for safety; press Ctrl+Alt+K again.", flush=True)
                self.devices[path] = device
                self.selector.register(device.fd, selectors.EVENT_READ, path)
                for code in device.active_keys():
                    self.held.update((path, code), True, self.roles.get(code))
                print("Keyboard:", path, device.name, flush=True)
            finally:
                if path not in self.devices:
                    device.close()
        if not self.devices:
            raise RuntimeError("No supported keyboard event devices found")

    def grab_all(self):
        try:
            for path, device in self.devices.items():
                device.grab()
                self.grabbed.add(path)
            # Close the race between the release check and grabbing all devices.
            if any(device.active_keys() for device in self.devices.values()):
                self.unlock()
                self.safety.toggle()  # Wait for releases and try again.
        except Exception:
            self.unlock()  # Never leave a partially locked set of keyboards.
            raise

    def read(self, path):
        try:
            for event in self.devices[path].read():
                if event.type == self.codes.EV_SYN and event.code == self.codes.SYN_DROPPED:
                    raise RuntimeError("Input queue overflow; unlocked for safety. Restart the app.")
                if event.type != self.codes.EV_KEY:
                    continue
                if self.held.update((path, event.code), event.value != 0,
                                    self.roles.get(event.code)):
                    self.safety.toggle()
        except BlockingIOError:
            pass
        except OSError as error:
            if error.errno != 19:  # ENODEV: physically unplugged.
                raise
            self.remove(path)

    def status(self):
        state = self.safety.state
        status = (state, self.safety.minutes)
        if status == self.last_status:
            return
        self.last_status = status
        text = {"unlocked": "UNLOCKED - Ctrl+Alt+K to lock",
                "arming": "Release all keys to lock",
                "locked": "LOCKED - Ctrl+Alt+K or the mouse button to unlock",
                "releasing": "Release all keys to unlock"}[state]
        print(text, "(auto-unlock: %s minutes)" % self.safety.minutes, flush=True)
        if self.window:
            self.label.config(text=text, bg="orange" if self.safety.blocked else "lightgrey")

    def run(self):
        try:
            self.scan()
            self.open_window()
            next_scan = time.monotonic() + 1
            while self.running:
                for key, _ in self.selector.select(timeout=0.05):
                    self.read(key.data)
                was_blocked = self.safety.blocked
                held = bool(self.held.keys)
                if self.safety.state in ("arming", "releasing"):
                    held = any(device.active_keys() for device in self.devices.values())
                self.safety.poll(held)
                if self.safety.blocked and not was_blocked:
                    self.grab_all()
                elif was_blocked and not self.safety.blocked:
                    self.unlock()
                if time.monotonic() >= next_scan:
                    self.scan()
                    next_scan = time.monotonic() + 1
                self.status()
                if self.window:
                    self.window.update()
        finally:
            self.unlock()
            for path in list(self.devices):
                self.remove(path)
            self.selector.close()
            if self.window:
                self.window.destroy()
            print("UNLOCKED - Keyboard Lock stopped", flush=True)


def main():
    args = arguments("Linux Keyboard Lock (Ctrl+Alt+K; mouse stays active)")
    if sys.platform != "linux":
        print("Use this entry point on Linux only.", file=sys.stderr)
        return 1
    try:
        import evdev
    except ImportError:
        print("Missing evdev: run bash setup.sh first.", file=sys.stderr)
        return 1
    app = LinuxLock(evdev, args.minutes)
    signal.signal(signal.SIGINT, app.stop)
    signal.signal(signal.SIGTERM, app.stop)
    try:
        app.run()
    except (OSError, RuntimeError) as error:
        print("Keyboard Lock:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
