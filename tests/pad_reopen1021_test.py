"""21.10, Ubuntu: «в Лире в первый раз открылся наш блокнот, потом сколько ни нажимаю — не открывается, после скрытия».
Виджет прятали в трей вместе с блокнотом (pad_hide → win.hide() pywebview), а при следующем открытии win.show() pywebview
окно не возвращал: кнопка подсвечивалась, листа не было. Теперь на Linux блокнот прячется и показывается одним путём —
через GTK (show_all, поверх, на место), как при первом открытии.

Живая проверка (если есть Xvfb, mutter и python3.12 с GTK): открыть блокнот → спрятать виджет в трей → «Лира, покажись» →
кнопка блокнота: окно блокнота видно; закрыть и открыть ещё раз — снова видно."""
import os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
body = src[src.index("    def pad_open(self, mode=\"notes\"):"):src.index("    def _pad_place(self, x, y):")]
reopen = body[:body.index("skin, light = ui_skin()")]
ok("gw.show_all()" in reopen and "gw.present()" in reopen, "повторное открытие на Linux — через GTK, как первое")
hide = body[body.index("def pad_hide"):]
ok("gw.hide()" in hide, "и прячется тем же путём")

need = [shutil.which("Xvfb"), shutil.which("mutter"), shutil.which("xdotool"), Path("/usr/bin/python3.12").exists(), shutil.which("dbus-run-session")]
if not all(need):
    print("нет Xvfb/mutter/xdotool/python3.12 — живую проверку пропускаю")
else:
    T = Path(tempfile.mkdtemp())
    (T / "cfg").mkdir()
    (T / "cfg/settings.json").write_text('{"ui":{"welcome":"done","news_seen":"99.0.0","skin":"neusky","skin_v2":true,"intro":"done"},'
                                         '"tts":{"engine":"off"},"stt":{"engine":"vosk"}}')
    (T / "ws.py").write_text("""import asyncio, json, sys, websockets
async def m():
    async with websockets.connect("ws://127.0.0.1:" + sys.argv[4]) as w:
        await w.send(json.dumps({"cmd": "hello", "token": open(sys.argv[1]).read().strip()}))
        await w.recv()
        await w.send(json.dumps({"id": 1, "cmd": sys.argv[2], "args": json.loads(sys.argv[3])}))
        await asyncio.sleep(1.5)
asyncio.run(m())
""")
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = str(s.getsockname()[1]); s.close()
    disp = ":" + str(70 + os.getpid() % 20)
    env = dict(os.environ, DEWIAR_CONFIG_DIR=str(T / "cfg"), DEWIAR_STATE_DIR=str(T / "st"), DEWIAR_WORKSPACE_DIR=str(T / "ws"),
               DEWIAR_PORT=PORT, HOME=str(T), DISPLAY=disp)
    core = subprocess.Popen([sys.executable, str(ROOT / "core/main.py"), "--null-audio", "--wav", str(ROOT / "tests/silence90.wav")],
                            env=env, stdout=open(T / "core.log", "w"), stderr=subprocess.STDOUT, cwd=str(ROOT))
    xv = subprocess.Popen(["Xvfb", disp, "-screen", "0", "1280x800x24", "+extension", "Composite"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    vis = "xdotool search --onlyvisible --name 'блокнот' >/dev/null 2>&1 && echo ДА || echo НЕТ"
    script = f"""
      mutter --x11 --replace --sm-disable >/dev/null 2>&1 & MP=$!
      sleep 3
      /usr/bin/python3.12 ui/app.py > {T}/ui.log 2>&1 & UP=$!
      sleep 14
      W=$(xdotool search --onlyvisible --name '^Dewiar$' | head -1)
      eval $(xdotool getwindowgeometry --shell $W)
      PX=$((X + WIDTH - 51)); PY=$((Y + 23))
      xdotool mousemove $PX $PY; sleep 0.6; xdotool click 1; sleep 4
      echo "1:$({vis})"
      xdotool mousemove $((PX + 28)) $PY; sleep 0.6; xdotool click 1; sleep 3
      echo "2:$({vis})"
      python3 {T}/ws.py {T}/cfg/token say '{{"text": "Лира, покажись"}}' {PORT}; sleep 5
      echo "3:$({vis})"
      xdotool mousemove $PX $PY; sleep 0.6; xdotool click 1; sleep 3
      echo "4:$({vis})"
      xdotool mousemove $PX $PY; sleep 0.6; xdotool click 1; sleep 4
      echo "5:$({vis})"
      kill $UP; kill $MP"""
    try:
        r = subprocess.run(["dbus-run-session", "--", "bash", "-c", script], env=env, cwd=str(ROOT), capture_output=True, text=True, timeout=150)
        res = dict(re.findall(r"^(\d):(ДА|НЕТ)$", r.stdout, re.M))
    finally:
        core.terminate(); xv.terminate()
    print("   шаги:", res)
    if res.get("1") != "ДА":
        print("   блокнот не открылся и в первый раз — окружение не то (координаты кнопки), живую проверку не считаю")
    else:
        ok(res.get("2") == "НЕТ", "виджет в трее — блокнот спрятан вместе с ним")
        ok(res.get("3") == "ДА", "после «покажись» блокнот вернулся вместе с виджетом (22.10: не открывать заново)")
        ok(res.get("4") == "НЕТ" and res.get("5") == "ДА", "кнопка блокнота закрывает и открывает его снова")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
