"""Ubuntu: настоящее окно (ui/app.py на pywebview + GTK, виртуальный экран Xvfb) минуту работает и не перезапускается.
0.28.3/0.28.4: окно каждые ~20 с перезапускалось с «Dewiar обновлён» (watch_version читал из version.py не ту строку).
DEWIAR_ROOT — проверить установленный или распакованный пакет. Нужен python3 с gi и webview (DEWIAR_UI_PY)."""
import os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_UI_PY") or shutil.which("python3.12") or sys.executable
SECS = int(os.environ.get("UI_RESTART_SECS") or 60)
r = subprocess.run([PY, "-c", "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk; import webview"],
                   capture_output=True)
if r.returncode:
    print("✅ пропуск: нет python с GTK и pywebview"); sys.exit(0)
tmp = Path(tempfile.mkdtemp())
rfd, wfd = os.pipe()                  # свободный номер экрана выбирает сам Xvfb: проверки могут идти параллельно
xv = subprocess.Popen(["Xvfb", "-displayfd", str(wfd), "-screen", "0", "1600x900x24"], pass_fds=(wfd,),
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.close(wfd)
disp = ":" + os.read(rfd, 16).decode().strip()
os.close(rfd)
env = dict(os.environ, DISPLAY=disp, HOME=str(tmp), XDG_CONFIG_HOME=str(tmp / "cfg"), XDG_DATA_HOME=str(tmp / "data"),
           DEWIAR_CONFIG_DIR=str(tmp / "cfg/dewiar"), DEWIAR_STATE_DIR=str(tmp / "state"), DEWIAR_UPDATE_CMD="1",
           DEWIAR_NO_CORE="1", PYTHONUNBUFFERED="1")
log = open(tmp / "ui.log", "w+")
ui = subprocess.Popen([PY, str(ROOT / "ui/app.py")], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
time.sleep(SECS)
alive = ui.poll() is None
os.killpg(ui.pid, 9) if alive else None
subprocess.run(["pkill", "-9", "-f", str(tmp)], capture_output=True)
subprocess.run(["pkill", "-9", "-f", str(ROOT / "core/main.py")], capture_output=True)
xv.kill()
log.seek(0); out = log.read()
restarts = out.count("перезапускаю интерфейс")
print(("✅ " if restarts == 0 else "❌ ") + f"окно {SECS} с без перезапусков (перезапусков: {restarts})")
print(("✅ " if alive else "❌ ") + "процесс окна жив" + ("" if alive else ": " + out[-600:]))
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(0 if restarts == 0 and alive else 1)
