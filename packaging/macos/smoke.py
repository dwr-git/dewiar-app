"""Проверка собранного Dewiar.app (tools/build_mac.sh, задание mac в GitHub Actions): библиотеки грузятся, ядро
запускается и отвечает по WebSocket, окна Cocoa открываются. Падает (код 1), если ядро не поднялось.

    Dewiar.app/Contents/Resources/python/bin/python3 smoke.py Dewiar.app [--ui]

Ядро — с выдуманным микрофоном (--wav, тишина) и без звука (--null-audio), во временных папках настроек и данных,
на свободном порту. Журнал ядра печатается в конце — по нему видно, что на Mac пошло не так, даже если ядро живо.
--ui — ещё и сам интерфейс (пускач приложения, DEWIAR_UI_SMOKE=1): виджет должен загрузиться за 90 с."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

APP = Path(sys.argv[1]).resolve()
RES = APP / "Contents" / "Resources"
PY = RES / "python" / "bin" / "python3"
ROOT = RES / "app"
MODS = ["numpy", "onnxruntime", "vosk", "sounddevice", "webview", "websockets", "objc", "AppKit", "WebKit", "Quartz",
        "PIL", "httpx", "piper", "onnx_asr", "psutil", "truststore", "pypdf", "vosk_tts", "tokenizers"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fail(text, log=None):
    print(f"::error::{text}")
    if log:
        print(log)
    sys.exit(1)


def main():
    t0 = time.monotonic()
    r = subprocess.run([str(PY), "-c", "import importlib,sys\nbad=[]\nfor m in sys.argv[1:]:\n  try: importlib.import_module(m)\n"
                        "  except Exception as e: bad.append(f'{m}: {type(e).__name__}: {e}')\nprint('\\n'.join(bad)); sys.exit(1 if bad else 0)",
                        *MODS], capture_output=True, text=True, timeout=300)
    if r.returncode:
        fail("библиотеки не грузятся:\n" + r.stdout + r.stderr)
    print(f"библиотеки: {len(MODS)} грузятся ({time.monotonic() - t0:.0f} с)")

    tmp = Path(tempfile.mkdtemp(prefix="dewiar-smoke-"))
    wav = tmp / "silence.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000 * 5)
    port = free_port()
    env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "config"), DEWIAR_STATE_DIR=str(tmp / "state"),
               DEWIAR_PORT=str(port), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    env.pop("PYTHONPATH", None)
    log = tmp / "core.log"
    err_f = open(tmp / "core-stderr.txt", "wb")
    core = subprocess.Popen([str(PY), "-X", "utf8", str(ROOT / "core" / "main.py"), "--null-audio", "--wav", str(wav),
                             "--log", str(log)], cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=err_f)

    def journal():
        try:
            return log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    up = False
    t1 = time.monotonic()
    while time.monotonic() - t1 < 180:
        if core.poll() is not None:
            fail(f"ядро завершилось с кодом {core.returncode}", journal() + "\n" + (tmp / "core-stderr.txt").read_text(errors="replace")[-4000:])
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                up = True
                break
        except OSError:
            time.sleep(0.5)
    if not up:
        core.kill()
        fail("ядро не открыло порт за 180 с", journal())
    print(f"ядро слушает порт за {time.monotonic() - t1:.0f} с")
    token = (tmp / "config" / "token").read_text().strip()
    r = subprocess.run([str(PY), "-c",
                        "import json,sys\nfrom websockets.sync.client import connect\n"
                        "ws=connect(f'ws://127.0.0.1:{sys.argv[1]}', open_timeout=20)\n"
                        "ws.send(json.dumps({'cmd':'hello','token':sys.argv[2]}))\n"
                        "m=json.loads(ws.recv(timeout=60)); d=m.get('data') or {}\n"
                        "print(json.dumps({'type':m.get('type'),'keys':sorted(d)[:10]}, ensure_ascii=False))",
                        str(port), token], capture_output=True, text=True, timeout=120)
    if r.returncode or '"hello"' not in r.stdout:
        core.kill()
        fail("ядро не ответило на hello: " + (r.stdout + r.stderr)[-2000:], journal())
    print("ядро ответило:", r.stdout.strip())
    time.sleep(8)                                   # пусть поработает: слух, голос, напоминания — ошибки попадут в журнал
    alive = core.poll() is None
    core.terminate()
    try:
        core.wait(15)
    except subprocess.TimeoutExpired:
        core.kill()
    text = journal()
    print("----- журнал ядра (Mac) -----")
    print(text[-12000:])
    print("----- конец журнала -----")
    errs = [x for x in text.splitlines() if " ERROR " in x or "Traceback" in x]
    for x in errs[:30]:
        print(f"::warning::журнал ядра: {x[:300]}")
    if not alive:
        fail("ядро упало через несколько секунд после запуска")
    if (tmp / "state" / "core.fail").exists():
        fail("ядро записало core.fail: " + (tmp / "state" / "core.fail").read_text()[:2000])

    if "--ui" in sys.argv:
        ui_check(tmp)
    print(f"готово за {time.monotonic() - t0:.0f} с")


def ui_check(tmp):
    """Настоящий запуск приложения (пускач → интерфейс → своё ядро): виджет загрузился — интерфейс пишет метку."""
    port = free_port()
    mark = tmp / "ui-ok.json"
    env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "ui-config"), DEWIAR_STATE_DIR=str(tmp / "ui-state"),
               DEWIAR_PORT=str(port), DEWIAR_UI_SMOKE=str(mark), DEWIAR_FAKE_MIC="1")
    (tmp / "ui-config").mkdir(parents=True, exist_ok=True)     # проверка не подаёт заявок на dewiar.pro (автоподключение)
    (tmp / "ui-config" / "settings.json").write_text(json.dumps({"cloud": {"auto_join": False}, "ui": {"welcome": "done"}}),
                                                       encoding="utf-8")
    out_f = tmp / "ui-out.txt"
    with open(out_f, "wb") as fo:                       # в файл, а не в трубу: зависший потомок не повесит проверку
        p = subprocess.Popen([str(APP / "Contents" / "MacOS" / "Dewiar")], env=env, stdout=fo, stderr=subprocess.STDOUT,
                             start_new_session=True)
    t = time.monotonic()
    while time.monotonic() - t < 120 and not mark.exists() and p.poll() is None:
        time.sleep(0.5)
    ok = mark.exists()
    print(f"интерфейс: {'виджет загрузился' if ok else 'метки нет'} за {time.monotonic() - t:.0f} с")
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            pass
    import signal
    try:                                                # пускач, окна и ядро — одна группа процессов: убрать всех
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass
    out = out_f.read_text(encoding="utf-8", errors="replace")
    print("----- вывод интерфейса -----")
    print(out[-6000:])
    for f in (tmp / "ui-state" / "logs").glob("*.log"):
        print(f"----- {f.name} -----")
        print(f.read_text(encoding="utf-8", errors="replace")[-6000:])
    if not ok:
        fail("интерфейс не загрузил виджет за 120 с")
    print("интерфейс:", mark.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
