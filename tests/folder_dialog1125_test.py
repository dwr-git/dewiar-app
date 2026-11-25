"""Письмо 25.11 (Windows): «окно выбора папки зависает, ничего не сделать — только закрыть программу в трее; и после
перезапуска выбор папки не работает». pywebview в Windows открывал диалог прямо из потока вызова со страницы, а владелец
диалога — окно студии в своём потоке (как №438 с «поверх всех»); студия «впереди» (TopMost) ещё и заслоняла его.
Теперь все окна выбора файла и папки идут через App._file_dialog: в Windows — в потоке окна (Invoke), TopMost снят."""
import ast, os, sys, threading, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("create_file_dialog(" not in src.replace("w.create_file_dialog(kind, **kw)", ""), "окна выбора — только через _file_dialog")
for name in ("pick_folder", "pick_file", "save_file"):
    body = src[src.index(f"    def {name}("):][:1500]
    ok("self._file_dialog(" in body, f"{name} — через _file_dialog")

# _file_dialog сам по себе: Windows — в потоке окна, TopMost снят; не Windows — как было
tree = ast.parse(src)
fn = next(n for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body if isinstance(n, ast.FunctionDef) and n.name == "_file_dialog")
code = ast.get_source_segment(src, fn)
logs = []
ns = {"WIN": True, "_ui_log": logs.append}
exec("class A:\n" + "\n".join("    " + ln if ln.strip() else ln for ln in code.replace("\n    ", "\n").splitlines()), ns)


class Form:
    TopMost = True
    InvokeRequired = True
    ui = None

    def Invoke(self, act):                       # как в .NET: исключение из потока окна — тому, кто звал
        err = []
        t = threading.Thread(target=lambda: self._run(act, err), name="ui"); t.start(); t.join()
        if err:
            raise err[0]

    @staticmethod
    def _run(act, err):
        try:
            act()
        except Exception as e:  # noqa: BLE001
            err.append(e)


form = Form()
calls = []
win = types.SimpleNamespace(uid="studio", create_file_dialog=lambda kind, **kw: calls.append((threading.current_thread().name, form.TopMost, kind, kw)) or ("C:\\Docs",))
sys.modules["webview"] = types.ModuleType("webview")
sys.modules["webview.platforms"] = types.ModuleType("webview.platforms")
wf = types.ModuleType("webview.platforms.winforms"); wf.BrowserView = types.SimpleNamespace(instances={"studio": form})
sys.modules["webview.platforms.winforms"] = wf
sysm = types.ModuleType("System"); sysm.Action = lambda f: f; sys.modules["System"] = sysm
a = ns["A"](); a._studio = win; a._hud = None
r = a._file_dialog(20, directory="C:\\Users\\me")
ok(r == ("C:\\Docs",) and calls and calls[0][0] == "ui", f"Windows: диалог в потоке окна: {calls}")
ok(calls and calls[0][1] is False, "Windows: на время диалога студия не «поверх всех» — не заслоняет его")


def boom(kind, **kw):
    raise RuntimeError("COM")


a._studio = types.SimpleNamespace(uid="studio", create_file_dialog=boom)
ok(a._file_dialog(20) is None and logs, f"сбой диалога — None и строка в журнале, а не зависание: {logs}")
ns["WIN"] = False
calls.clear(); a._studio = win
ok(a._file_dialog(20) == ("C:\\Docs",) and calls[0][0] != "ui", "Linux и Mac — как было")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
