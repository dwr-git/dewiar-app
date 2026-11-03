"""Окно виджета на Windows (ui/winshell.py), 03.11.
№453, №458 (01.11, Windows 11): «по углам виджета чёрные треугольники». pywebview в тёмной теме Windows ставит окну фон
Mica (DWMWA_SYSTEMBACKDROP_TYPE = 2), а Windows 11 рисует его на весь прямоугольник окна, не по форме SetWindowRgn —
в углах тёмная подложка. Теперь каждой форме окна — flat_frame (без подложки, своего скругления и рамки DWM), а сторож
формы снимает подложку снова, если pywebview вернул её при смене темы.
№453: «на панели задач значок Python, а не Dewiar» — ID приложения ставится первым делом (до значка в трее), а ярлыкам
«Пуска» записывается тот же System.AppUserModel.ID: по нему панель задач Windows 11 и берёт значок.
№476 (журнал): «ctypes.ArgumentError: argument 5: TypeError: 'NoneType' object cannot be interpreted as an integer» —
наши argtypes на ОБЩЕМ ctypes.windll.user32.SetWindowPos ломали window.move у pywebview (он передаёт размер None):
окна «Закинуть идею» и суфлёр не перетаскивались. Теперь у winshell и app.py свои экземпляры библиотек.
Windows здесь нет — ctypes подменяем: смотрим, что зовётся и что остаётся нетронутым."""
import ctypes, os, re, sys, types, uuid
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CALLS = []


class Fn:
    def __init__(self, dll, name):
        self.dll, self.name = dll, name

    def __call__(self, *a):
        CALLS.append((self.dll.name, self.name, a))
        if self.name in ("GetDpiForWindow",):
            return 96
        if self.name == "GetWindowRect":
            r = a[1]._obj
            r.left, r.top, r.right, r.bottom = 0, 0, 300, 420
            return 1
        return 1 if not self.name.startswith("Dwm") else 0


class DLL:
    def __init__(self, name):
        self.name, self._f = name, {}

    def __getattr__(self, k):
        if k.startswith("_"):
            raise AttributeError(k)
        return self._f.setdefault(k, Fn(self, k))


SHARED = {}
ctypes.windll = types.SimpleNamespace(**{n: SHARED.setdefault(n, DLL(n)) for n in ("user32", "gdi32", "kernel32", "shell32", "dwmapi", "ole32")})
ctypes.WinDLL = lambda name, **k: DLL(name)
ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
import winshell  # noqa: E402

# №476: общие windll.* — нетронуты (их делим с pywebview)
touched = [(d, f) for d, dll in SHARED.items() for f, fn in dll._f.items() if hasattr(fn, "argtypes") or hasattr(fn, "restype")]
ok(not touched, f"№476: winshell не меняет argtypes/restype общих ctypes.windll.* ({touched[:3]})")
ok(winshell.user32 is not SHARED["user32"] and hasattr(winshell.user32.SetWindowPos, "argtypes"), "№476: у winshell своя user32 (с типами)")
src_app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
src_ws = (ROOT / "ui/winshell.py").read_text(encoding="utf-8")
bad = re.findall(r"ctypes\.windll\.\w+\.\w+\.(?:argtypes|restype)|=\s*ctypes\.windll\.(?:user32|kernel32|gdi32|shell32)\b", src_app + src_ws)
ok(not bad, f"№476: ни app.py, ни winshell не берут общие windll.* с типами ({bad[:3]})")

# №453/№458: форма окна — и без подложки DWM
CALLS.clear()
winshell.shape(1234, "card", 28)
names = [c[1] for c in CALLS]
ok("SetWindowRgn" in names, "форма окна ставится (SetWindowRgn)")
dwm = [(c[2][1], c[2][2]._obj.value) for c in CALLS if c[1] == "DwmSetWindowAttribute"]
ok((38, 1) in dwm, f"№458: подложка Mica снята — DWMWA_SYSTEMBACKDROP_TYPE = нет ({dwm})")
ok((33, 1) in dwm and (34, 0xFFFFFFFE) in dwm, "своё скругление и рамка DWM — тоже сняты (не спорят с формой)")
ok(names.index("SetWindowRgn") < names.index("DwmSetWindowAttribute"), "подложка снимается после формы")
CALLS.clear()
winshell.shape_rects(1234, [(0, 0, 10, 10), (10, 0, 5, 5)])
ok(any(c[1] == "DwmSetWindowAttribute" for c in CALLS), "и окнам из прямоугольников (блокнот) — тоже")
ok(winshell.backdrop_wrong(2) and winshell.backdrop_wrong(3) and not winshell.backdrop_wrong(1)
   and not winshell.backdrop_wrong(0) and not winshell.backdrop_wrong(None), "Mica / акрил под формой — «не то», нет подложки и Windows 10 — в порядке")
ok("winshell.backdrop_wrong(winshell.backdrop(h))" in src_app and "winshell.flat_frame(h)" in src_app,
   "сторож формы снимает подложку, если pywebview вернул её (смена темы Windows)")

# №453: значок на панели задач — ID приложения первым делом и ярлыкам «Пуска»
mw = src_app[src_app.index("def main_win(args, extra):"):]
ok(mw.index("winshell.app_id()") < mw.index("winshell.Tray(") and mw.index("winshell.app_id()") < mw.index("ensure_core()"),
   "№453: ID приложения — до ядра, значка в трее и окон")
ok("winshell.links_app_id" in mw, "№453: ярлыкам «Пуска» — тот же ID (по нему Windows 11 берёт значок)")
g = winshell.guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3")
ok(ctypes.string_at(ctypes.addressof(g), 16) == uuid.UUID("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3").bytes_le, "GUID ключа собирается байт в байт (как в Windows)")
ok(winshell.PKEY_AppUserModel_ID[1] == 5 and winshell.VT_LPWSTR == 31 and winshell.GPS_READWRITE == 2, "ключ System.AppUserModel.ID и тип строки — верные")
ok(ctypes.sizeof(winshell.PROPVARIANT) == (24 if ctypes.sizeof(ctypes.c_void_p) == 8 else 16), "PROPVARIANT нужного размера")
lk = src_ws[src_ws.index("def link_app_id"):src_ws.index("def dewiar_links")]
ok("method(5," in lk and "method(6," in lk and "method(7)" in lk and "method(2," in lk, "IPropertyStore: Get 5, Set 6, Commit 7, Release 2")
ok("if now == aumid:" in lk, "ярлык с нашим ID не переписываем каждый запуск")
# масштаб экрана: тот же режим, что у pywebview (system aware), но до первого окна — значка в трее
CALLS.clear()
ok(winshell.dpi_aware() and any(c[1] == "SetProcessDpiAwarenessContext" and c[2][0].value == ctypes.c_void_p(-2).value for c in CALLS),
   "процесс «знает масштаб» (DPI_AWARENESS_CONTEXT_SYSTEM_AWARE) — как pywebview, без смены размеров")
ok(mw.index("winshell.dpi_aware()") < mw.index("winshell.Tray("), "и это — до значка в трее (первого окна процесса)")
os.environ["APPDATA"] = str(ROOT / "tests" / "__no_such_dir__")
ok(winshell.dewiar_links() == [], "нет ярлыков — нечего и править")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
