# Keyboard Lock: lock your keyboard for cleaning, cats, kids and presentations

Keyboard Lock is a tiny, free Windows tray app that switches your keyboard off with one shortcut, **Ctrl+Alt+K**, so you can wipe the keys, or leave the laptop with a cat, a toddler or a presentation running, without typing gibberish, closing windows or triggering shortcuts. Press the same shortcut again to get your keyboard back. Your mouse and trackpad keep working the whole time.

It is a single C# file (about 140 lines). It has no installer, no network access, no settings files and no dependencies beyond the .NET Framework that ships with Windows 10 and Windows 11.

The Windows app and its build command are unchanged. Separate, small Python versions
are available for [macOS](#macos-beta) and [Linux](#linux-beta). They have no runtime
network access or telemetry and retain only the keys currently held in memory, never
a keystroke history. Setup downloads the platform bridge into a local `.venv`.
The features and instructions below describe Windows; platform differences follow.

## Features

- **One-shortcut toggle.** Ctrl+Alt+K locks and unlocks the keyboard. You can also double-click the tray icon or use its right-click menu.
- **Mouse stays active.** The mouse and trackpad are never blocked, so you can always unlock from the tray icon.
- **Auto-unlock safety net.** If you forget, the keyboard unlocks itself after 10 minutes by default. Pick 1, 5, 10, 30 or 60 minutes from the tray menu, or start with `--minutes 45` (1 to 240).
- **Click-to-unlock banner.** While locked, a small orange banner stays on top of your screen. Click it to unlock. It never steals focus from what you are doing.
- **No stuck keys.** On lock, Ctrl, Alt, Shift and Windows are released so apps do not think a modifier is still held down.
- **Clear status.** The tray icon turns into a warning sign and shows a notification while the keyboard is locked.
- **Private by design.** The keyboard hook only decides whether to pass a key through or swallow it. Keystrokes are never stored, logged or sent anywhere. Read the [source](KeyboardLock.cs) to confirm.

## How to Use

1. [Build](#build-from-source) and start `KeyboardLock.exe`. A keyboard-lock icon appears in the system tray (click the `^` arrow if it is hidden).
2. Press **Ctrl+Alt+K** to lock the keyboard. Clean away.
3. Press **Ctrl+Alt+K** again, or double-click the tray icon, to unlock.
4. To close the app, right-click the tray icon and choose **Exit**.

| Action | How |
| --- | --- |
| Lock or unlock | Ctrl+Alt+K, double-click the tray icon, or tray menu |
| Quit | Tray menu, then Exit |
| Automatic unlock | After 10 minutes by default; tray menu, Auto-unlock after, or `KeyboardLock.exe --minutes 30` |
| Unlock with the mouse | Click the orange banner, or the tray icon |

## More Ways to Use It

Cleaning is the classic use, but any time you want key presses ignored while the mouse keeps working:

- Keep a cat or toddler from typing into a long download, render or video call.
- Present or watch a film without an elbow hitting Space, Esc or a shortcut.
- Read a long document or recipe with messy hands.
- Ignore a laptop keyboard that is broken or ghost-typing while you work with the mouse and on-screen keyboard.
- Run a demo or kiosk-style screen where people can only click.

## Build from Source

You need nothing but Windows. The C# compiler is already included with the .NET Framework. In **PowerShell**:

```powershell
& "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /out:KeyboardLock.exe /reference:System.Windows.Forms.dll /reference:System.Drawing.dll KeyboardLock.cs
```

This produces `KeyboardLock.exe` in the same folder. To start it automatically at sign-in, put a shortcut to it in `shell:startup`.

I recommend building it yourself rather than running a binary from the internet. It takes a few seconds, and you can read all the code first.

## Safety, Permissions and Limits

- **Antivirus warnings.** Any program that watches the keyboard can look suspicious to antivirus software. This one is unsigned, so Windows SmartScreen or Defender may warn about a build you compiled. The code is short and open: read it, then decide.
- **Admin windows.** Windows does not let a normal app intercept keys sent to an elevated (Administrator) window. If such a window has focus, the lock may not cover it.
- **Secure screens.** Ctrl+Alt+Delete, the UAC prompt and the sign-in screen are handled by Windows itself and cannot be blocked by any app.
- **Physical keys only.** Keys sent by software, such as the on-screen keyboard, still work while locked.
- **Power button.** The power key is handled by the hardware and is not affected.

## Frequently Asked Questions

**How do I disable my laptop keyboard while cleaning it on Windows?**
Run Keyboard Lock and press Ctrl+Alt+K. Every key is blocked until you press the shortcut again or 10 minutes pass.

**Can I lock the keyboard but keep using the mouse?**
Yes. That is the point: the mouse and trackpad are untouched, so you can still unlock from the tray.

**Does it work on Windows 11?**
Yes, on Windows 10 and Windows 11. It uses the standard Windows low-level keyboard hook.

**Is it a keylogger?**
No. It never records, stores or transmits key presses, and the code has no file or network access. You can verify that in [KeyboardLock.cs](KeyboardLock.cs).

## macOS (beta)

**beta: built and checked on Windows with automated tests and syntax/type checks;
not yet tested on real Mac/Linux hardware.** Here, the checks are Python syntax
checks and automated logic tests; no macOS build, framework type check or event-tap
test has been run.

Requires a logged-in macOS desktop, macOS 11 or later, Python 3.9+ with `venv` and
`pip`, and the PyObjC Cocoa and Quartz bridges. Tk is not used on macOS.
From a terminal in this repository:

```bash
bash setup.sh
bash launch.sh
# Optional: choose a different failsafe (1 to 240 minutes).
bash launch.sh --minutes 30
```

In **System Settings > Privacy & Security**, grant **Accessibility** (to suppress
keyboard events) and **Input Monitoring** (to see the global shortcut) to the
launching terminal/Python identity shown by macOS. Quit and relaunch after granting
permission. Do not run the macOS app with sudo. A denied event tap exits with a
permission explanation rather than displaying a working lock.

- **Control+Option+K** is Ctrl+Alt+K on a Mac keyboard (the physical ANSI K
  position on other layouts). The menu-bar item reads **Keys** or **LOCKED**;
  its menu locks, unlocks, changes the timeout, or exits. Default timeout: 10 minutes.
- Release all held keys to complete a shortcut lock or unlock. This lets apps
  receive modifier releases before blocking starts and prevents shortcut repeat
  from toggling repeatedly. The menu can cancel a pending lock.
- An orange, non-activating window offers click-to-unlock. The mouse and trackpad
  events are excluded from the tap. Menu/banner unlock works immediately.
- Permissions apply to the interpreter/terminal used to launch it; moving or
  rebuilding the environment may require granting them again.
- Coverage is the current GUI session's ordinary key and modifier events. Secure
  Input, login/lock screens, OS-reserved shortcuts, Touch ID, hardware power/Fn
  actions, and media/brightness keys delivered as system-defined events may bypass
  the tap. Caps Lock's hardware LED/toggled state may change while locked.
  Software/on-screen keyboard events routed through this tap are also blocked.
  This is a convenience tool, not a kiosk/security boundary.
- If macOS disables the tap, the app unlocks and re-enables the tap; it does not
  silently pretend the interrupted lock is intact. A crash removes the tap.
- Python's timer runs on the UI thread; a suspended or stalled process cannot
  run the failsafe until it resumes. Expiry also checks wall time after sleep.

Source: [macOS entry point](keyboard_lock_macos.py) and
[shared shortcut/timer state](keyboard_lock_core.py). The tap uses the documented
[Quartz event-tap callback](https://developer.apple.com/documentation/coregraphics/cgeventtapcallback),
with [Input Monitoring access](https://developer.apple.com/documentation/coregraphics/cgrequestlisteneventaccess)
and [Accessibility permissions](https://developer.apple.com/documentation/applicationservices/axisprocesstrustedwithoptions).

## Linux (beta)

**beta: built and checked on Windows with automated tests and syntax/type checks;
not yet tested on real Mac/Linux hardware.** Here, the checks are Python syntax
checks and mocked device/logic tests; no real Linux input device has been grabbed.

Requires Linux `/dev/input/event*`, Python 3.9+ with `venv` and `pip`, and
[`python-evdev`](https://python-evdev.readthedocs.io/en/latest/). Building evdev may
need your distribution's C compiler, Python development headers and Linux input
headers. For the optional mouse control window, install your distribution's
Python Tk package (commonly `python3-tk`); otherwise a terminal status indicator
is used. The input mechanism works independently of X11/Wayland and on a local
virtual console.

```bash
bash setup.sh
bash launch.sh
bash launch.sh --minutes 30  # Optional; default is 10, range 1 to 240.
```

The process needs access to **all** input event nodes so it can identify keyboards
and exclusively grab them with `EVIOCGRAB`. Without access, it exits visibly rather
than quietly leaving an unknown keyboard unlocked. On distributions using the
`input` group, an administrator can grant membership (log out and back in):

```bash
sudo usermod -aG input "$USER"
# After signing in again:
bash launch.sh
```

This group permits reading other input devices as well; grant it only to a trusted
local account. An administrator-managed device ACL is another option. For a
one-session alternative, from the repository after setup:

```bash
sudo .venv/bin/python keyboard_lock_linux.py --minutes 10
```

Running with sudo may prevent Tk from connecting to the desktop; terminal status,
Ctrl+Alt+K and auto-unlock still operate. Do not relax `/dev/input` permissions for
everyone. No `/dev/uinput`, desktop extension, daemon or configuration file is needed.

- **Ctrl+Alt+K** toggles. Release all held keys before a shortcut transition
  completes. The initial lock shortcut **also reaches the focused application**;
  an evdev reader cannot swallow unlocked events without continuously grabbing
  and reinjecting every key. Avoid applications where that shortcut is destructive,
  or use the mouse button to lock. Input remains active while waiting to lock.
- The terminal reports **UNLOCKED**, **LOCKED**, or waiting for releases. If Tk
  is available, an always-on-top window has a mouse lock/unlock button, timeout
  choices (1, 5, 10, 30, 60 minutes), and Exit. The default is 10 minutes; without
  Tk, set the timeout with `--minutes`. Closing the window exits and unlocks.
- Mouse/trackpad nodes are never grabbed. An event node combining keyboard keys
  and pointer axes/buttons is refused, since grabbing it would also block the mouse.
  Separate keyboard/media-key nodes are included. Unusual devices without Linux
  `KEY_*` capabilities are outside coverage.
- Existing keyboards are grabbed together, with rollback if any grab fails. A
  newly attached keyboard is discovered within about one second and **unlocks the
  session for safety**; it can type before detection. Check the indicator and lock
  again. This is not a security or hotplug-proof kiosk lock.
- A process already holding an exclusive grab prevents locking. Input queue
  overflow exits and unlocks rather than trusting an incomplete shortcut state.
- The kernel releases grabs when descriptors close, including process exit or
  crash. Ctrl+C works while unlocked; while locked use the shortcut, mouse window,
  timeout, or terminate the process from another session. Terminal-only mode has
  no mouse button. A suspended/stalled process cannot run the timer until resumed;
  expiry also checks wall time after sleep. Do not suspend the process while locked.
- Kernel/hardware emergency actions, firmware keys and keyboards outside the
  local input subsystem are outside coverage. Software/on-screen keyboard input
  on separate virtual devices remains usable unless exposed as a grabbed keyboard
  event node. The app never creates a virtual keyboard or records key events.

Source: [Linux entry point](keyboard_lock_linux.py). See the documented
[grab/ungrab APIs](https://python-evdev.readthedocs.io/en/latest/apidoc.html#evdev.device.InputDevice.grab)
and [Linux event semantics](https://www.kernel.org/doc/html/latest/input/event-codes.html).

## Development checks

Windows build: use the [unchanged compiler command above](#build-from-source).
The new logic and mock device tests require only Python's standard library:

```bash
python -m unittest discover -s tests -v
python -m py_compile keyboard_lock_core.py keyboard_lock_linux.py keyboard_lock_macos.py tests/test_keyboard_lock.py
bash -n setup.sh launch.sh
```

Tests cover shortcut repeats and both modifier sides, release-before-lock/unlock,
timeout and sleep/clock changes, device classification, partial-grab rollback,
hotplug, permission failures, overflow and cleanup. They do not establish live OS
permission, event routing or GUI behaviour. Platform bridges install only through
`setup.sh`; application code has no networking or telemetry.

## License

[MIT](LICENSE). Free to use, change and share.
