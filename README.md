# Keyboard Lock: lock your laptop keyboard while you clean it (Windows)

Keyboard Lock is a tiny, free Windows tray app that switches your keyboard off with one shortcut, **Ctrl+Alt+K**, so you can wipe the keys without typing gibberish, closing windows or triggering shortcuts. Press the same shortcut again to get your keyboard back. Your mouse and trackpad keep working the whole time.

It is a single C# file (about 140 lines). It has no installer, no network access, no settings files and no dependencies beyond the .NET Framework that ships with Windows 10 and Windows 11.

## Features

- **One-shortcut toggle.** Ctrl+Alt+K locks and unlocks the keyboard. You can also double-click the tray icon or use its right-click menu.
- **Mouse stays active.** The mouse and trackpad are never blocked, so you can always unlock from the tray icon.
- **10-minute auto-unlock.** If you forget, the keyboard unlocks itself after 10 minutes, so you can never be locked out for good.
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
| Automatic unlock | After 10 minutes (change `AUTO_UNLOCK_MINUTES` in the source) |

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

## License

[MIT](LICENSE). Free to use, change and share.
