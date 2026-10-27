using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

// KeyboardLock - toggle the keyboard off/on with Ctrl+Alt+K (cleaning, cats, kids, presenting).
// Mouse stays alive on purpose: it is the escape hatch (tray icon or the on-screen banner).
// Optional: KeyboardLock.exe --minutes 30   sets the auto-unlock time (1 to 240, default 10).
class KeyboardLock : ApplicationContext
{
    const int WH_KEYBOARD_LL = 13;
    const int WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101, WM_SYSKEYDOWN = 0x0104, WM_SYSKEYUP = 0x0105;
    const int LLKHF_INJECTED = 0x10;
    const int VK_CONTROL = 0x11, VK_MENU = 0x12, VK_SHIFT = 0x10, VK_LWIN = 0x5B, VK_RWIN = 0x5C;
    const int TOGGLE_VK = 0x4B; // K
    const int DEFAULT_MINUTES = 10;
    const int WS_EX_NOACTIVATE = 0x08000000, WS_EX_TOOLWINDOW = 0x80;

    // Small always-on-top strip shown while locked. Clicking it unlocks; it never takes keyboard focus.
    class Banner : Form
    {
        public Banner()
        {
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            TopMost = true;
            StartPosition = FormStartPosition.Manual;
            BackColor = Color.FromArgb(255, 170, 0);
            Size = new Size(340, 40);
            Cursor = Cursors.Hand;
            var area = Screen.PrimaryScreen.WorkingArea;
            Location = new Point(area.Left + (area.Width - Width) / 2, area.Top + 8);
            var label = new Label {
                Text = "Keyboard locked - click here to unlock",
                Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Segoe UI", 10f, FontStyle.Bold), ForeColor = Color.Black
            };
            label.Click += (s, e) => { if (_locked) Toggle(); };
            Click += (s, e) => { if (_locked) Toggle(); };
            Controls.Add(label);
        }
        protected override bool ShowWithoutActivation { get { return true; } }
        protected override CreateParams CreateParams
        {
            get { var cp = base.CreateParams; cp.ExStyle |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW; return cp; }
        }
    }

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
    static MenuItem[] _timeoutItems;
    static Banner _banner;
    static int _minutes = DEFAULT_MINUTES;

    [STAThread]
    static void Main(string[] args)
    {
        for (int i = 0; i < args.Length - 1; i++)
        {
            int m;
            if (args[i] == "--minutes" && int.TryParse(args[i + 1], out m) && m >= 1 && m <= 240) _minutes = m;
        }
        Application.EnableVisualStyles();
        Application.Run(new KeyboardLock());
    }

    KeyboardLock()
    {
        _toggleItem = new MenuItem("Lock keyboard (Ctrl+Alt+K)", (s, e) => Toggle());
        int[] choices = { 1, 5, 10, 30, 60 };
        _timeoutItems = new MenuItem[choices.Length];
        for (int i = 0; i < choices.Length; i++)
        {
            int m = choices[i];
            _timeoutItems[i] = new MenuItem(m + (m == 1 ? " minute" : " minutes"), (s, e) => SetMinutes(m));
        }
        var timeoutMenu = new MenuItem("Auto-unlock after", _timeoutItems);

        var menu = new ContextMenu(new MenuItem[] {
            _toggleItem,
            timeoutMenu,
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

        _failsafe = new Timer { Interval = _minutes * 60 * 1000 };
        SetMinutes(_minutes);
        _failsafe.Tick += (s, e) => { if (_locked) Toggle(); };

        _proc = HookCallback;
        _banner = new Banner();
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
            _banner.Show();
            Balloon("Keyboard LOCKED", "Ctrl+Alt+K, the banner or the tray icon unlocks it. It also unlocks itself after "
                    + _minutes + " minutes.");
        }
        else
        {
            _failsafe.Stop();
            _banner.Hide();
            Balloon("Keyboard unlocked", "Typing works again.");
        }
    }

    static void SetMinutes(int m)
    {
        _minutes = m;
        _failsafe.Interval = m * 60 * 1000;
        if (_locked) { _failsafe.Stop(); _failsafe.Start(); }
        foreach (var item in _timeoutItems) item.Checked = (item.Text == m + (m == 1 ? " minute" : " minutes"));
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
        if (_banner != null) { _banner.Close(); _banner = null; }
        if (_tray != null) { _tray.Visible = false; _tray.Dispose(); }
        Application.Exit();
    }
}
