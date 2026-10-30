"""№419 (30.10, Windows 11 сборки 28000, WebView2 156, «Dewiar не запускается»): ядро работало, а окна открылись старым
MSHTML (Internet Explorer) — страница виджета в нём не грузится, окна прятались. pywebview ищет WebView2 в реестре только
у пользователя и в 32-битной части машины (WOW6432Node); наша диагностика нашла среду — значит, она записана в 64-битной
части. app.wv2_registry_fix даёт pywebview и это место. Проверяем настоящим кодом pywebview на поддельном реестре."""
import os, re, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


WV2 = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
HKLM, HKCU = "HKLM", "HKCU"


def fake_winreg(keys):
    """keys: {(корень, путь): {имя: значение}}"""
    w = types.ModuleType("winreg")
    w.HKEY_LOCAL_MACHINE, w.HKEY_CURRENT_USER = HKLM, HKCU

    class K:
        def __init__(self, v): self.v = v
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def OpenKey(root, sub, *a, **k):
        if (root, sub) not in keys:
            raise FileNotFoundError(2, "нет ключа", sub)
        return K(keys[(root, sub)])
    w.OpenKey = OpenKey
    w.QueryValueEx = lambda k, name: (k.v[name], 1)
    w.CloseKey = lambda k: None
    return w


REG = {(HKLM, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"): {"Release": 533325},
       (HKLM, r"SOFTWARE\Microsoft\EdgeUpdate\Clients" + "\\" + WV2): {"pv": "156.0.4314.56"}}   # только 64-битная часть


def pywebview_check(w):
    """_is_chromium и _is_new_version — исходник установленного pywebview (или копия 6.2.1, если его нет)."""
    try:
        import webview
        src = (Path(webview.__file__).parent / "platforms/winforms.py").read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    code = re.search(r"^def _is_new_version.*?(?=^def _is_chromium)", src, re.S | re.M).group(0) + \
        re.search(r"^def _is_chromium\(\):.*?(?=^is_cef|^\S)", src[src.index("def _is_chromium"):], re.S | re.M).group(0)
    g = {"winreg": w, "settings": {"WEBVIEW2_RUNTIME_PATH": None}, "machine": lambda: "AMD64",
         "logger": types.SimpleNamespace(exception=lambda e: None, debug=print, warning=print)}
    exec(code, g)
    return g["_is_chromium"]()


w = fake_winreg(REG)
before = pywebview_check(w)
if before is None:
    print("pywebview не установлен — проверяю только наш код")
else:
    ok(before is False, f"без поправки pywebview не видит WebView2 из 64-битной части — открыл бы MSHTML: {before}")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
fix = re.search(r"^def wv2_registry_fix\(\):.*?(?=^\S)", app, re.S | re.M).group(0)
sys.modules["winreg"] = w
g = {}; exec(fix, g); g["wv2_registry_fix"]()
if before is not None:
    ok(pywebview_check(w) is True, "с поправкой — WebView2 найден (Edge Chromium)")
try:
    w.OpenKey(HKLM, r"SOFTWARE\Microsoft\Nothing"); ok(False, "чужой ключ открылся")
except FileNotFoundError:
    ok(True, "другие ключи реестра — как были (ошибка остаётся ошибкой)")
g["wv2_registry_fix"]()
ok(getattr(w, "_dewiar_wv2", False), "поправка ставится один раз")
ok("wv2_registry_fix()\n    try:\n        webview.start(on_start, gui=\"edgechromium\"" in app and "Окна: {getattr(_wf, 'renderer'" in app,
   "поправка — перед запуском окон; в журнале — каким движком открылись окна")
# диагностика: где записана среда
doc = (ROOT / "ui/doctor.py").read_text(encoding="utf-8")
fn = re.search(r"^def webview2\(\):.*?(?=^\S)", doc, re.S | re.M).group(0)
sys.modules["winreg"] = fake_winreg(REG)
g = {}; exec(fn, g)
ok(g["webview2"]() == "156.0.4314.56 (машина, 64 бит)", f"диагностика пишет, где записан WebView2: {g['webview2']()}")
del sys.modules["winreg"]
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
