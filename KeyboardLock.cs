using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

// KeyboardLock - toggle the keyboard off/on with Ctrl+Alt+K so it can be cleaned.
// Mouse stays alive on purpose: it is the escape hatch (tray icon -> Unlock/Exit).
class KeyboardLock : ApplicationContext
{
    const int WH_KEYBOARD_LL = 13;
    const int WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101, WM_SYSKEYDOWN = 0x0104, WM_SYSKEYUP = 0x0105;
    const int LLKHF_INJECTED = 0x10;
    const int VK_CONTROL = 0x11, VK_MENU = 0x12, VK_SHIFT = 0x10, VK_LWIN = 0x5B, VK_RWIN = 0x5C;
    const int TOGGLE_VK = 0x4B; // K
    const int AUTO_UNLOCK_MINUTES = 10;

    [StructLayout(LayoutKind.Sequential)]
    struct KBDLLHOOKSTRUCT { public uint vkCode, scanCode, flags, time; public IntPtr dwExtraInfo; }

    delegate IntPtr HookProc(int nCode, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    static extern IntPtr SetWindowsHookEx(int idHook, HookProc lpfn, IntPtr hMod, uint dwThreadId);
    [DllImport("user32.dll", SetLastError = true)]
    static extern bool UnhookWindowsHookEx(IntPtr hhk);
    [DllImport("user32.dll")]
    static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);
    [DllImport("kernel32.dll", CharSet = CharSet.Auto)]
    static extern IntPtr GetModuleHandle(string lpModuleName);
    [DllImport("user32.dll")]
    static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    static HookProc _proc;          // kept alive so the GC cannot collect the callback
    static IntPtr _hook = IntPtr.Zero;
    static bool _locked = false;
    static bool _lCtrl, _rCtrl, _lAlt, _rAlt;   // per-side, so releasing one Ctrl/Alt does not hide the other
    static bool _toggleHeld = false;            // true while K is held, so key-repeat cannot re-toggle
    static NotifyIcon _tray;
    static Timer _failsafe;
    static MenuItem _toggleItem;

    [STAThread]
    static void Main() { Application.EnableVisualStyles(); Application.Run(new KeyboardLock()); }

    KeyboardLock()
    {
        _toggleItem = new MenuItem("Lock keyboard (Ctrl+Alt+K)", (s, e) => Toggle());
        var menu = new ContextMenu(new MenuItem[] {
            _toggleItem,
            new MenuItem("-"),
            new MenuItem("Exit", (s, e) => Quit())
        });

        _tray = new NotifyIcon {
            Icon = SystemIcons.Application,
            Text = "Keyboard Lock - unlocked",
            ContextMenu = menu,
            Visible = true
        };
        _tray.DoubleClick += (s, e) => Toggle();

        _failsafe = new Timer { Interval = AUTO_UNLOCK_MINUTES * 60 * 1000 };
        _failsafe.Tick += (s, e) => { if (_locked) Toggle(); };

        _proc = HookCallback;
        _hook = SetWindowsHookEx(WH_KEYBOARD_LL, _proc, GetModuleHandle(null), 0);
        if (_hook == IntPtr.Zero)
        {
            MessageBox.Show("Could not install the keyboard hook. Error " + Marshal.GetLastWin32Error(),
                            "Keyboard Lock", MessageBoxButtons.OK, MessageBoxIcon.Error);
            Quit();
            return;
        }
        Balloon("Keyboard Lock is running", "Press Ctrl+Alt+K to lock the keyboard for cleaning. Press it again to unlock.");
    }

    static IntPtr HookCallback(int nCode, IntPtr wParam, IntPtr lParam)
    {
        if (nCode < 0) return CallNextHookEx(_hook, nCode, wParam, lParam);

        var info = (KBDLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(KBDLLHOOKSTRUCT));
        int msg = wParam.ToInt32();
        bool down = (msg == WM_KEYDOWN || msg == WM_SYSKEYDOWN);
        bool up = (msg == WM_KEYUP || msg == WM_SYSKEYUP);
        bool injected = (info.flags & LLKHF_INJECTED) != 0;

        // Software-generated keys (on-screen keyboard, our own cleanup) always pass.
        if (injected) return CallNextHookEx(_hook, nCode, wParam, lParam);

        // Track modifiers ourselves - we may be swallowing them, so the OS state is unreliable.
        int vk = (int)info.vkCode;
        if (vk == VK_CONTROL || vk == 0xA2) _lCtrl = down ? true : (up ? false : _lCtrl);
        if (vk == 0xA3) _rCtrl = down ? true : (up ? false : _rCtrl);
        if (vk == VK_MENU || vk == 0xA4) _lAlt = down ? true : (up ? false : _lAlt);
        if (vk == 0xA5) _rAlt = down ? true : (up ? false : _rAlt);

        if (vk == TOGGLE_VK && up) _toggleHeld = false;
        if (down && vk == TOGGLE_VK && (_lCtrl || _rCtrl) && (_lAlt || _rAlt))
        {
            if (!_toggleHeld) { _toggleHeld = true; Toggle(); }
            return (IntPtr)1;
        }

        if (_locked) return (IntPtr)1; // swallow every physical key while locked

        return CallNextHookEx(_hook, nCode, wParam, lParam);
    }

    static void Toggle()
    {
        _locked = !_locked;
        _tray.Icon = _locked ? SystemIcons.Warning : SystemIcons.Application;
        _tray.Text = _locked ? "Keyboard Lock - LOCKED (Ctrl+Alt+K to unlock)" : "Keyboard Lock - unlocked";
        _toggleItem.Text = _locked ? "Unlock keyboard (Ctrl+Alt+K)" : "Lock keyboard (Ctrl+Alt+K)";

        if (_locked)
        {
            ReleaseModifiers(); // stop apps thinking Ctrl/Alt are still held
            _lCtrl = _rCtrl = _lAlt = _rAlt = false;
            _failsafe.Stop(); _failsafe.Start();
            Balloon("Keyboard LOCKED", "Safe to clean. Ctrl+Alt+K, or the tray icon, unlocks it. It also unlocks itself after "
                    + AUTO_UNLOCK_MINUTES + " minutes.");
        }
        else
        {
            _failsafe.Stop();
            Balloon("Keyboard unlocked", "Typing works again.");
        }
    }

    static void ReleaseModifiers()
    {
        const uint KEYEVENTF_KEYUP = 0x0002;
        byte[] mods = { VK_CONTROL, 0xA2, 0xA3, VK_MENU, 0xA4, 0xA5, VK_SHIFT, 0xA0, 0xA1, VK_LWIN, VK_RWIN };
        foreach (byte m in mods) keybd_event(m, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
    }

    static void Balloon(string title, string text)
    {
        _tray.BalloonTipTitle = title;
        _tray.BalloonTipText = text;
        _tray.ShowBalloonTip(4000);
    }

    static void Quit()
    {
        if (_hook != IntPtr.Zero) { UnhookWindowsHookEx(_hook); _hook = IntPtr.Zero; }
        if (_tray != null) { _tray.Visible = false; _tray.Dispose(); }
        Application.Exit();
    }
}
