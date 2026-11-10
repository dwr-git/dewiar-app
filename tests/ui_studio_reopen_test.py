"""Ubuntu: студию можно открыть, закрыть и открыть снова — кнопками виджета (настройки, календарь, память), сколько угодно
раз. Было: после первого закрытия кнопки виджета больше ничего не открывали — помогал только перезапуск Dewiar.
Настоящие окна pywebview + GTK на виртуальном экране Xvfb, без ядра. Нужен python3 с gi и webview (DEWIAR_UI_PY)."""
import os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_UI_PY") or shutil.which("python3.12") or sys.executable
if os.environ.get("_STUDIO_CHILD") != "1":
    r = subprocess.run([PY, "-c", "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk; import webview"],
                       capture_output=True)
    if r.returncode or not shutil.which("Xvfb"):
        print("✅ пропуск: нет python с GTK и pywebview или Xvfb"); sys.exit(0)
    tmp = Path(tempfile.mkdtemp())
    rfd, wfd = os.pipe()                  # свободный номер экрана выбирает сам Xvfb: проверки могут идти параллельно
    xv = subprocess.Popen(["Xvfb", "-displayfd", str(wfd), "-screen", "0", "1600x900x24"], pass_fds=(wfd,),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(wfd)
    disp = ":" + os.read(rfd, 16).decode().strip()
    os.close(rfd)
    env = dict(os.environ, DISPLAY=disp, HOME=str(tmp), DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"),
               DEWIAR_NO_CORE="1", PYTHONUNBUFFERED="1", _STUDIO_CHILD="1")
    try:
        r = subprocess.run([PY, __file__], env=env, capture_output=True, text=True, timeout=120)
        out = r.stdout
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        out += "\n❌ окна зависли (2 минуты)"
    xv.kill()
    shutil.rmtree(tmp, ignore_errors=True)
    print(out.strip())
    sys.exit(1 if "❌" in out or "✅" not in out else 0)

# ---------- дочерний процесс: настоящие окна ----------
import threading  # noqa: E402
sys.path.insert(0, str(ROOT / "ui"))
sys.argv = [sys.argv[0]]
import gi  # noqa: E402
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
import webview  # noqa: E402
import app as A  # noqa: E402

api = A.Api("tok")
url, bridge = api._bridged(api._url("hud.html", "&mode=card"))     # как в программе: фасад моста и ключ окна
api.wins["card"] = webview.create_window(A.TITLES["card"], url, width=340, height=520,
                                         frameless=True, hidden=True, js_api=bridge)
api._hud = api.wins["card"]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m, flush=True)
    if not c:
        fails.append(m)


def visible():
    return bool(api._gtk(lambda: any(g.get_title() == A.STUDIO_TITLE and g.get_visible() for g in Gtk.Window.list_toplevels())))


def wait(cond, sec=10):
    end = time.time() + sec
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.2)
    return False


def scenario():
    time.sleep(1.5)
    api._hud.show()
    time.sleep(1.5)
    try:
        for i, (page, how) in enumerate([("", "кнопка «Студия»"), ("calendar", "календарь"), ("memory", "память"),
                                         ("tasks", "задачи"), ("", "кнопка «Студия» ещё раз")]):
            # как кнопки виджета: из страницы виджета через мост pywebview
            threading.Thread(target=lambda: api._hud.evaluate_js(f"window.pywebview.api.open_settings('{page}')"), daemon=True).start()
            ok(wait(visible), f"{i + 1}-й раз открылась ({how})")
            time.sleep(1.0)
            st = api._studio
            closer = ((lambda: st.evaluate_js("document.getElementById('wb-x').click()")) if i % 2 == 0   # своя кнопка «×» студии
                      else (lambda: st.destroy()))                                                         # окно закрыли иначе
            threading.Thread(target=closer, daemon=True).start()
            ok(wait(lambda: not visible()), f"{i + 1}-й раз закрылась")
            time.sleep(0.5)
    finally:
        print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}", flush=True)
        os._exit(0)


A.harden_webview("gtk")                                              # как в программе: охрана моста
webview.start(lambda: threading.Thread(target=scenario, daemon=True).start(), gui="gtk")
