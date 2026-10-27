#!/usr/bin/env python3
"""macOS Quartz event tap and Cocoa menu bar. No network or key logging."""

import signal
import sys

from keyboard_lock_core import HeldKeys, SafetyLock, arguments


def main():
    args = arguments("macOS Keyboard Lock (Control+Option+K)")
    if sys.platform != "darwin":
        print("Use this entry point on macOS only.", file=sys.stderr)
        return 1
    try:
        import Cocoa
        import Quartz
        import objc
    except ImportError:
        print("Missing PyObjC: run bash setup.sh first.", file=sys.stderr)
        return 1

    class KeyboardLock(Cocoa.NSObject):
        @objc.python_method
        def setup(self):
            self.safety, self.held = SafetyLock(args.minutes), HeldKeys()
            self.tap = self.source = self.timer = self.banner = None
            self.swallow_k = False
            self.roles = {59: "ctrl", 62: "ctrl", 58: "alt", 61: "alt", 40: "k"}
            self.item = Cocoa.NSStatusBar.systemStatusBar().statusItemWithLength_(
                Cocoa.NSVariableStatusItemLength)
            menu = Cocoa.NSMenu.alloc().init()
            self.toggle_item = self.menu_item(menu, "Lock keyboard (Ctrl+Alt+K)", "toggle:")
            timeout = Cocoa.NSMenu.alloc().init()
            self.timeout_items = []
            for minutes in (1, 5, 10, 30, 60):
                item = self.menu_item(timeout, "%s minutes" % minutes, "setMinutes:")
                item.setTag_(minutes)
                self.timeout_items.append(item)
            parent = self.menu_item(menu, "Auto-unlock after", None)
            parent.setSubmenu_(timeout)
            menu.addItem_(Cocoa.NSMenuItem.separatorItem())
            self.menu_item(menu, "Exit (unlocks)", "quit:")
            self.item.setMenu_(menu)
            self.refresh()

            if hasattr(Quartz, "CGPreflightListenEventAccess"):
                if not Quartz.CGPreflightListenEventAccess():
                    Quartz.CGRequestListenEventAccess()
            mask = sum(1 << event for event in (Quartz.kCGEventKeyDown,
                                                Quartz.kCGEventKeyUp,
                                                Quartz.kCGEventFlagsChanged))
            self.callback = self.event  # Retain the Python callback for the tap lifetime.
            self.tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault, mask, self.callback, None)
            if self.tap is None:
                self.cleanup()
                raise RuntimeError("Cannot create the keyboard event tap. Grant Accessibility and "
                                   "Input Monitoring to the launching terminal/Python in System "
                                   "Settings > Privacy & Security, then quit and relaunch.")
            self.source = Quartz.CFMachPortCreateRunLoopSource(None, self.tap, 0)
            Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetMain(), self.source,
                                     Quartz.kCFRunLoopCommonModes)
            self.seed_keys()
            Quartz.CGEventTapEnable(self.tap, True)
            self.timer = Cocoa.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
                0.05, self, "tick:", None, True)
            Cocoa.NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, Cocoa.NSRunLoopCommonModes)

        @objc.python_method
        def seed_keys(self):
            self.held.keys.clear()
            for code in range(128):
                if code == 57:  # Caps Lock's toggled state must not prevent arming.
                    continue
                if Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, code):
                    self.held.update((0, code), True, self.roles.get(code))

        @objc.python_method
        def menu_item(self, menu, title, action):
            item = Cocoa.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
            if action:
                item.setTarget_(self)
            menu.addItem_(item)
            return item

        @objc.python_method
        def event(self, proxy, event_type, event, context):
            try:
                if event_type in (Quartz.kCGEventTapDisabledByTimeout,
                                  Quartz.kCGEventTapDisabledByUserInput):
                    # A disabled tap means keys may already have passed: fail open.
                    self.safety.unlock()
                    self.seed_keys()
                    self.swallow_k = False
                    Quartz.CGEventTapEnable(self.tap, True)
                    return event
                code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                if event_type == Quartz.kCGEventFlagsChanged:
                    if code == 57:  # Caps Lock toggles its LED, rather than holding a modifier.
                        return None if self.safety.blocked else event
                    down = (0, code) not in self.held.keys
                else:
                    down = event_type == Quartz.kCGEventKeyDown
                toggle = self.held.update((0, code), down, self.roles.get(code))
                if toggle:
                    self.safety.toggle()
                    self.swallow_k = True
                consume = self.safety.blocked or (code == 40 and self.swallow_k)
                if code == 40 and not down:
                    self.swallow_k = False
                return None if consume else event
            except Exception:
                # Never leave input blocked after a Python callback failure.
                self.safety.unlock()
                Quartz.CGEventTapEnable(self.tap, False)
                print("Keyboard tap failed; unlocked. Quit and relaunch.", file=sys.stderr)
                return event

        def tick_(self, sender):
            self.safety.poll(bool(self.held.keys))
            self.refresh()

        def toggle_(self, sender):
            if self.safety.blocked or self.safety.state == "arming":
                self.safety.unlock()
            else:
                self.safety.toggle()
            self.refresh()

        def mouseUnlock_(self, sender):
            self.safety.unlock()
            self.refresh()

        def setMinutes_(self, sender):
            self.safety.set_minutes(sender.tag())
            self.refresh()

        @objc.python_method
        def refresh(self):
            locked = self.safety.blocked
            self.item.button().setTitle_("LOCKED" if locked else "Keys")
            self.item.button().setToolTip_("Keyboard Lock: " + self.safety.state)
            title = {"unlocked": "Lock keyboard (Ctrl+Alt+K)",
                     "arming": "Waiting for key releases (click to cancel)",
                     "locked": "Unlock keyboard (Ctrl+Alt+K)",
                     "releasing": "Release keys to unlock (click to unlock now)"}[self.safety.state]
            self.toggle_item.setTitle_(title)
            for item in self.timeout_items:
                item.setState_(1 if item.tag() == self.safety.minutes else 0)
            if locked:
                if self.banner is None:
                    frame = Cocoa.NSScreen.mainScreen().visibleFrame()
                    rect = ((frame.origin.x + (frame.size.width - 400) / 2,
                             frame.origin.y + frame.size.height - 52), (400, 44))
                    self.banner = Cocoa.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                        rect, Cocoa.NSWindowStyleMaskBorderless | Cocoa.NSWindowStyleMaskNonactivatingPanel,
                        Cocoa.NSBackingStoreBuffered, False)
                    self.banner.setLevel_(Cocoa.NSFloatingWindowLevel)
                    self.banner.setHidesOnDeactivate_(False)
                    self.banner.setBackgroundColor_(Cocoa.NSColor.orangeColor())
                    button = Cocoa.NSButton.alloc().initWithFrame_(((0, 0), (400, 44)))
                    button.setTitle_("Keyboard locked - click here to unlock")
                    button.setBordered_(False)
                    button.setTarget_(self)
                    button.setAction_("mouseUnlock:")
                    self.banner.contentView().addSubview_(button)
                self.banner.orderFrontRegardless()
            elif self.banner is not None:
                self.banner.orderOut_(None)

        @objc.python_method
        def cleanup(self):
            self.safety.unlock()
            if self.timer is not None:
                self.timer.invalidate()
            if self.tap is not None:
                Quartz.CGEventTapEnable(self.tap, False)
                Quartz.CFMachPortInvalidate(self.tap)
            if self.source is not None:
                Quartz.CFRunLoopRemoveSource(Quartz.CFRunLoopGetMain(), self.source,
                                            Quartz.kCFRunLoopCommonModes)
            if self.banner is not None:
                self.banner.orderOut_(None)
            Cocoa.NSStatusBar.systemStatusBar().removeStatusItem_(self.item)

        def applicationWillTerminate_(self, notification):
            self.cleanup()

        def quit_(self, sender):
            Cocoa.NSApplication.sharedApplication().terminate_(None)

    app = Cocoa.NSApplication.sharedApplication()
    app.setActivationPolicy_(Cocoa.NSApplicationActivationPolicyAccessory)
    delegate = KeyboardLock.alloc().init()
    app.setDelegate_(delegate)
    try:
        delegate.setup()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    signal.signal(signal.SIGINT, lambda *_: delegate.quit_(None))
    signal.signal(signal.SIGTERM, lambda *_: delegate.quit_(None))
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
