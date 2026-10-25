"""Windows: окна виджета (форма, положение, панель задач), значок в трее, запуск ядра, один экземпляр.

То, что в Linux делают GTK/X11 и systemd, здесь — через Win32 (ctypes), без сторонних библиотек; пользуется
им ui/app.py (импортируется только на Windows). Окна создаёт pywebview (WinForms + WebView2), здесь им меняют
стиль и форму по дескриптору. Координаты наружу (в JS и настройки) — «логические» пиксели, как в CSS; внутри —
физические пиксели экрана (масштаб 125 %/150 % учитывается через DPI окна).
"""

import ctypes
import os
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)    # код ошибки — ctypes.get_last_error(): GetLastError() к моменту вызова уже затёрт самим ctypes

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0004, 0x0010
MONITOR_DEFAULTTONEAREST = 2
NO_WINDOW = 0x08000000                       # CREATE_NO_WINDOW
DETACHED = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: живёт без нас

# Типы аргументов и результатов задаём явно: по умолчанию ctypes считает всё int (32 бита) и на 64-битной Windows
# портит дескрипторы и значения размером с указатель (LONG_PTR).

user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
gdi32.CreateRoundRectRgn.restype = wintypes.HRGN
gdi32.CreateEllipticRgn.restype = wintypes.HRGN
gdi32.CreateRectRgn.restype = wintypes.HRGN
gdi32.CombineRgn.argtypes = [wintypes.HRGN, wintypes.HRGN, wintypes.HRGN, ctypes.c_int]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def hwnd(title):
    """Дескриптор окна по заголовку или None (запасной путь, когда у pywebview нет Form.Handle)."""
    return user32.FindWindowW(None, title) or None


def window_shot(title):
    """Снимок окна с заголовком title, если оно видно на экране (картинка PIL), иначе None."""
    h = hwnd(title)
    if not h or not user32.IsWindowVisible(h):
        return None
    x, y, w, hh = rect(h)
    if w < 60 or hh < 60:
        return None
    try:
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=(x + 10, y + 10, x + w - 10, y + hh - 10), all_screens=True)
    except Exception:  # noqa: BLE001
        return None


def scale(h):
    """Масштаб экрана, на котором окно: 1.0 = 96 dpi, 1.25 = 125 %…"""
    try:
        return max(1.0, user32.GetDpiForWindow(h) / 96.0)
    except (AttributeError, OSError):         # Windows 10 до 1607
        return 1.0


def rect(h):
    """(x, y, ширина, высота) окна в физических пикселях."""
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def get_pos(h):
    """Левый верхний угол в логических пикселях."""
    x, y, _, _ = rect(h)
    k = scale(h)
    return [round(x / k), round(y / k)]


def cursor(h=None):
    """Где курсор мыши — в логических px (масштаб — окна h). Для перетаскивания виджета: координаты из страницы
    (screenX) в WebView2 при движении окна бывают устаревшими — курсор «убегал» от окна (№169)."""
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    k = scale(h) if h else 1.0
    return [pt.x / k, pt.y / k]


def raise_top(h):
    """Окно — наверх среди окон «поверх всех», без кражи фокуса (окно напоминания над виджетом и блокнотом, 25.10)."""
    user32.SetWindowPos(h, wintypes.HWND(-1), 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)    # HWND_TOPMOST


def move(h, x, y):
    k = scale(h)
    user32.SetWindowPos(h, None, int(round(x * k)), int(round(y * k)), 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


def clamp(h, x, y, w, hgt):
    """Не дать окну уехать за край рабочей области монитора (без панели задач). Всё в логических px."""
    k = scale(h)
    pt = wintypes.POINT(int((x + w / 2) * k), int((y + hgt / 2) * k))
    mon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
        return max(0, int(x)), max(0, int(y))
    wa = mi.rcWork
    l, t, r, b = wa.left / k, wa.top / k, wa.right / k, wa.bottom / k
    return int(max(l, min(x, r - w))), int(max(t, min(y, b - hgt)))


user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]


def monitor_area(h):
    """Весь монитор, на котором окно h (с панелью задач), логические px: (лево, верх, право, низ). Нет — None."""
    mon = user32.MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
        return None
    k, m = scale(h), mi.rcMonitor
    return m.left / k, m.top / k, m.right / k, m.bottom / k


def work_area(h=None):
    """Рабочая область монитора, на котором окно h (без h — основного), логические px. 21.10, №161: блокнот считался по
    основному монитору — у виджета на втором мониторе он вставал за край экрана и не был виден."""
    if h:
        mon = user32.MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if mon and user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            k, wa = scale(h), mi.rcWork
            return wa.left / k, wa.top / k, wa.right / k, wa.bottom / k
    r = wintypes.RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)       # SPI_GETWORKAREA
    try:
        k = user32.GetDpiForSystem() / 96.0
    except (AttributeError, OSError):
        k = 1.0
    return r.left / k, r.top / k, r.right / k, r.bottom / k


def shape(h, kind, radius=28):
    """Форма окна: kind "mini" — круг, иначе скруглённый прямоугольник (radius — в логических px). Размер берём у
    самого окна (уже с учётом масштаба). Показ, смена масштаба и пересоздание окна форму сбрасывают — app.py
    ставит её заново (_win_shape)."""
    _, _, w, hgt = rect(h)
    if kind == "mini":
        # круг по меньшей стороне, по центру окна: на мониторе с масштабом 100 % Windows не даёт окну быть уже своей
        # минимальной ширины (~120 px), и значок 96×96 становился 120×96 — овалом (отзыв 16.10, широкий монитор).
        # Значок на странице и так стоит по центру (hud.html body.mini #card)
        d = min(w, hgt)
        x0, y0 = (w - d) // 2, (hgt - d) // 2
        rgn = gdi32.CreateEllipticRgn(x0, y0, x0 + d + 1, y0 + d + 1)
    else:
        r = int(radius * scale(h)) * 2
        rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, hgt + 1, r, r)
    user32.SetWindowRgn(h, rgn, True)           # регион теперь принадлежит окну — не освобождаем


def shape_rects(h, rects):
    """Форма окна из прямоугольников [(x, y, ш, в)] в физических px (блокнот: лист + «крепления», app.pad_rects)."""
    rgn = None
    for x, y, w, hh in rects:
        r = gdi32.CreateRectRgn(int(x), int(y), int(x + w), int(y + hh))
        if rgn is None:
            rgn = r
        else:
            gdi32.CombineRgn(rgn, rgn, r, 2)           # RGN_OR
            gdi32.DeleteObject(r)
    if rgn is not None:
        user32.SetWindowRgn(h, rgn, True)           # регион теперь принадлежит окну


def no_capture(h):
    """Окно не видно при показе экрана и в записи (Windows 10 2004+: WDA_EXCLUDEFROMCAPTURE) — суфлёр на встрече.
    Старые Windows флага не знают — тогда окно хотя бы чёрное в записи (WDA_MONITOR). -> удалось ли."""
    try:
        if user32.SetWindowDisplayAffinity(h, 0x11):
            return True
        return bool(user32.SetWindowDisplayAffinity(h, 0x01))
    except Exception:  # noqa: BLE001
        return False


def dark_title(h):
    """Тёмная (чёрная на Windows 11) полоса заголовка у студии — в тон окну."""
    dwm = ctypes.windll.dwmapi
    one = ctypes.c_int(1)
    for attr in (20, 19):                       # DWMWA_USE_IMMERSIVE_DARK_MODE (20; 19 — старые сборки Windows 10)
        if dwm.DwmSetWindowAttribute(h, attr, ctypes.byref(one), ctypes.sizeof(one)) == 0:
            break
    black = ctypes.c_uint(0x000000)
    dwm.DwmSetWindowAttribute(h, 35, ctypes.byref(black), ctypes.sizeof(black))     # DWMWA_CAPTION_COLOR, Windows 11


def tool_window(h):
    """Виджет не показывается кнопкой на панели задач и в Alt+Tab (для этого есть значок в трее)."""
    ex = user32.GetWindowLongPtrW(h, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(h, GWL_EXSTYLE, (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)


# ---------- один экземпляр интерфейса ----------

_MUTEX = []


def single_instance(name):
    """True — мы первые. Именованный мьютекс сеанса (Local\\): живёт, пока жив процесс (дескриптор держим в _MUTEX).
    Второй запуск получает False и просит первый показаться через файл signal_path()."""
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    h = kernel32.CreateMutexW(None, False, f"Local\\Dewiar-{name}")
    if not h:
        return True
    if ctypes.get_last_error() == 183:          # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(h)
        return False
    _MUTEX.append(h)
    return True


def message_box(text, title="Dewiar", wait=False):
    """Обычное окно-сообщение Windows поверх всех (не держит программу: в отдельном потоке; wait — дождаться «ОК»)."""
    show = lambda: user32.MessageBoxW(None, str(text), str(title), 0x40 | 0x40000 | 0x10000)  # noqa: E731
    if wait:
        show()
        return
    threading.Thread(target=show, daemon=True).start()


def ask_yes_no(text, title="Dewiar"):
    """Вопрос «Да / Нет» поверх всех окон (ждёт ответа) → True, если «Да»."""
    return user32.MessageBoxW(None, str(text), str(title), 0x4 | 0x30 | 0x40000 | 0x10000) == 6       # MB_YESNO, IDYES


def kill_pid(pid):
    """Завершить процесс по номеру (вместе с дочерними), только если это python/pythonw: номер из ui.pid/core.pid
    мог уже достаться другой программе. -> False, если номер негодный или наш собственный."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0 or pid == os.getpid():
        return False
    for exe in ("pythonw.exe", "python.exe"):
        subprocess.run(["taskkill", "/F", "/T", "/FI", f"PID eq {pid}", "/IM", exe], creationflags=NO_WINDOW,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def signal_path():
    """Файл-сигнал «покажись» для уже запущенного интерфейса (пишет второй запуск, читает main_win в app.py)."""
    return Path(tempfile.gettempdir()) / f"dewiar-show-{os.environ.get('USERNAME', 'user')}"


# ---------- ядро ----------

def pythonw():
    """pythonw.exe рядом с текущим Python — запуск без чёрного окна консоли."""
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def log_dir():
    from settings import STATE_DIR
    d = STATE_DIR / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def start_core(root):
    """Ядро — отдельный процесс без окна, который переживает интерфейс; журнал —
    %LOCALAPPDATA%\\Dewiar\\logs\\core.log. -> Popen (по нему сторож в app.py видит, что ядро упало)."""
    return subprocess.Popen([pythonw(), "-X", "utf8", str(root / "core" / "main.py"), "--log", str(log_dir() / "core.log")],
                            cwd=str(root), creationflags=DETACHED | NO_WINDOW, close_fds=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def core_call(port, token, cmd, args=None, timeout=4):
    """Одна команда ядру через WebSocket по тому же протоколу, что у страниц (assets/dewiar.js): hello с токеном,
    затем {id, cmd, args} -> data из ответа или None. Ошибки связи и таймауты — исключением."""
    import json
    from websockets.sync.client import connect
    with connect(f"ws://127.0.0.1:{port}", open_timeout=timeout, close_timeout=1) as ws:
        ws.send(json.dumps({"cmd": "hello", "token": token}))
        ws.recv(timeout=timeout)
        ws.send(json.dumps({"id": 1, "cmd": cmd, "args": args or {}}))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            m = json.loads(ws.recv(timeout=timeout))
            if m.get("type") == "reply" and m.get("id") == 1:
                return m.get("data")
    return None


# ---------- значок в трее (Shell_NotifyIcon напрямую, без сторонних библиотек) ----------

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
WM_DESTROY, WM_CLOSE, WM_COMMAND, WM_APP = 0x0002, 0x0010, 0x0111, 0x8000
WM_LBUTTONUP, WM_RBUTTONUP, WM_LBUTTONDBLCLK, WM_CONTEXTMENU = 0x0202, 0x0205, 0x0203, 0x007B
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
TPM_RIGHTBUTTON, TPM_RETURNCMD, TPM_NONOTIFY = 0x0002, 0x0100, 0x0080
MF_STRING, MF_SEPARATOR, MF_DEFAULT = 0, 0x800, 0x1000
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
TRAY_MSG = WM_APP + 1
WM_HOTKEY, WM_HOTKEY_SET, HOTKEY_ID = 0x0312, WM_APP + 2, 0xD3A1    # «Закинуть идею» (ui/hotkey.py)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON), ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON)]


def _api():
    u, s, k = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
    u.DefWindowProcW.restype = LRESULT
    u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.RegisterClassExW.restype = wintypes.ATOM
    u.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    u.CreateWindowExW.restype = wintypes.HWND
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                  wintypes.HINSTANCE, wintypes.LPVOID]
    u.LoadImageW.restype = wintypes.HANDLE
    u.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    u.CreatePopupMenu.restype = wintypes.HMENU
    u.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    u.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.LPVOID]
    u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.RegisterWindowMessageW.restype = wintypes.UINT
    u.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
    u.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    s.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    s.Shell_NotifyIconW.restype = wintypes.BOOL
    k.GetModuleHandleW.restype = wintypes.HMODULE
    k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    return u, s, k


class Tray:
    """Значок возле часов: щелчок — показать виджет, правая кнопка — меню «Показать / Студия / Выход».
    Своё скрытое окно и цикл сообщений — в потоке tray (конструктор ждёт его до 5 с); пункты меню выполняются
    каждый в своём потоке, чтобы не держать цикл. ok — значок действительно добавлен."""

    def __init__(self, icon_path, on_show, on_studio, on_quit, on_capture=None, fix=None):
        """fix — (подпись, действие): «Окна чёрные? Перерисовать проще» (комментарии 19.10 — студия и виджет чёрные)."""
        self.icon_path, self.hwnd, self.ok = str(icon_path), None, False
        self.items = [(1, "Показать Dewiar", on_show)] + ([(4, "Закинуть идею", on_capture)] if on_capture else []) + \
                     [(2, "Студия", on_studio)] + ([(0, None, None), (5, fix[0], fix[1])] if fix else []) + \
                     [(0, None, None), (3, "Выход", on_quit)]
        self._ready = threading.Event()
        threading.Thread(target=self._run, name="tray", daemon=True).start()
        self._ready.wait(5)

    def _nid(self):
        n = NOTIFYICONDATAW()
        n.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        n.hWnd, n.uID = self.hwnd, 1
        return n

    def _add(self):
        n = self._nid()
        n.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        n.uCallbackMessage, n.hIcon, n.szTip = TRAY_MSG, self.hicon, "Dewiar — голосовой ассистент"
        return bool(self.s.Shell_NotifyIconW(NIM_ADD, ctypes.byref(n)))

    def _menu(self):
        m = self.u.CreatePopupMenu()
        for cid, text, _ in self.items:
            self.u.AppendMenuW(m, MF_SEPARATOR if not cid else MF_STRING, cid, text)
        pt = wintypes.POINT()
        self.u.GetCursorPos(ctypes.byref(pt))
        self.u.SetForegroundWindow(self.hwnd)             # иначе меню не закроется щелчком мимо
        cmd = self.u.TrackPopupMenu(m, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY, pt.x, pt.y, 0, self.hwnd, None)
        self.u.DestroyMenu(m)
        self._fire(cmd)

    def _fire(self, cmd):
        for cid, _, fn in self.items:
            if cid and cid == cmd and fn:
                threading.Thread(target=fn, daemon=True).start()

    def _proc(self, hwnd, msg, wp, lp):
        try:
            if msg == TRAY_MSG:
                ev = lp & 0xFFFF
                if ev in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self._fire(1)
                elif ev in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._menu()
                return 0
            if msg == WM_HOTKEY_SET:
                self._hk_apply()
                return 0
            if msg == WM_HOTKEY and wp == HOTKEY_ID and getattr(self, "_hk_fn", None):
                threading.Thread(target=self._hk_fn, daemon=True).start()
                return 0
            if msg == self.taskbar_created:                # Проводник перезапустился — значок пропал, вернуть
                self._add()
                return 0
            if msg == WM_CLOSE:
                n = self._nid()
                self.s.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(n))
                self.u.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                self.u.PostQuitMessage(0)
                return 0
        except Exception as e:  # noqa: BLE001 — исключение в оконной процедуре уронило бы процесс
            print(f"Трей: {e}", file=sys.stderr)
        return self.u.DefWindowProcW(hwnd, msg, wp, lp)

    def _run(self):
        try:
            self.u, self.s, k = _api()
            hinst = k.GetModuleHandleW(None)
            self._wndproc = WNDPROC(self._proc)            # держим ссылку — иначе сборщик мусора уберёт колбэк
            wc = WNDCLASSEXW()
            wc.cbSize, wc.lpfnWndProc, wc.hInstance = ctypes.sizeof(WNDCLASSEXW), self._wndproc, hinst
            wc.lpszClassName = f"DewiarTray{os.getpid()}"
            if not self.u.RegisterClassExW(ctypes.byref(wc)):
                raise ctypes.WinError()
            self.taskbar_created = self.u.RegisterWindowMessageW("TaskbarCreated")
            # обычное скрытое окно верхнего уровня: только такие получают TaskbarCreated
            self.hwnd = self.u.CreateWindowExW(0, wc.lpszClassName, "Dewiar tray", 0, 0, 0, 0, 0, None, None, hinst, None)
            if not self.hwnd:
                raise ctypes.WinError()
            self.hicon = self.u.LoadImageW(None, self.icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            self.ok = self._add()
            if not self.ok:
                print("Значок в трее не добавлен (нет области уведомлений?)", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"Значок в трее не создан: {e}", file=sys.stderr)
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        while self.u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            self.u.TranslateMessage(ctypes.byref(msg))
            self.u.DispatchMessageW(ctypes.byref(msg))

    def hotkey(self, mods, vk, fn):
        """Сочетание клавиш на всю систему (RegisterHotKey окна значка): fn — в своём потоке. Регистрировать можно только
        из потока окна — просим его сообщением и ждём ответа. mods=None — снять. -> True, если Windows приняла."""
        if not (self.ok and self.hwnd):
            return False
        self._hk = (mods, vk, fn, threading.Event(), [False])
        self.u.PostMessageW(self.hwnd, WM_HOTKEY_SET, 0, 0)
        self._hk[3].wait(3)
        return self._hk[4][0]

    def _hk_apply(self):
        mods, vk, fn, done, res = self._hk
        try:
            self.u.UnregisterHotKey(self.hwnd, HOTKEY_ID)
            self._hk_fn = fn
            res[0] = True if mods is None else bool(self.u.RegisterHotKey(self.hwnd, HOTKEY_ID, mods, vk))
        finally:
            done.set()

    def notify(self, text, title="Dewiar"):
        """Всплывающее сообщение от значка (в Windows 10/11 — уведомление). Длины обрезаем под поля NOTIFYICONDATAW."""
        if not (self.ok and self.hwnd):
            return False
        n = self._nid()
        n.uFlags, n.szInfo, n.szInfoTitle, n.dwInfoFlags = NIF_INFO, text[:255], title[:63], 0x1   # NIIF_INFO
        return bool(self.s.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(n)))

    def stop(self):
        if self.hwnd:
            self.u.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
