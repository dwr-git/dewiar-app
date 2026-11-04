"""«Пауза» одним словом, без имени: играет музыка — ставим на паузу; не играет — ничего не делаем."""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
tmp = Path(tempfile.mkdtemp())
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
if not __import__("shutil").which("espeak-ng"):
    print("нет espeak-ng — пропускаю"); print("ALL OK"); sys.exit(0)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vosk_have import skip_without_vosk  # noqa: E402
skip_without_vosk(ROOT)                                 # «пауза» из WAV слышит модель Vosk
subprocess.run(["espeak-ng", "-v", "ru", "-s", "150", "-w", str(tmp / "w.wav"), "пауза"], check=True)
subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-t", "2", "-i", "anullsrc=r=16000:cl=mono", "-i", str(tmp / "w.wav"),
                "-f", "lavfi", "-t", "6", "-i", "anullsrc=r=16000:cl=mono", "-filter_complex",
                "[1:a]aresample=16000,aformat=channel_layouts=mono[w];[0:a][w][2:a]concat=n=3:v=0:a=1", "-ar", "16000", "-ac", "1",
                "-sample_fmt", "s16", str(tmp / "scn.wav")], check=True)


def run(playing):
    d = tmp / ("p" if playing else "n"); (d / "cfg").mkdir(parents=True)
    (d / "cfg/settings.json").write_text(json.dumps({"stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}}))
    env = dict(os.environ, DEWIAR_CONFIG_DIR=str(d / "cfg"), DEWIAR_STATE_DIR=str(d / "st"), DEWIAR_PORT="8803",
               DEWIAR_ASSUME_AEC="1", DEWIAR_DRY_TOOLS=str(d / "dry.jsonl"))
    if playing:
        env["DEWIAR_FAKE_PLAYING"] = "1"
    else:
        env.pop("DEWIAR_FAKE_PLAYING", None)
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(tmp / "scn.wav"), "--null-audio"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logf = d / "st" / "logs" / "core.log"
    end = time.monotonic() + 60
    while time.monotonic() < end:                       # запись 10 с идёт в реальном времени после запуска слуха
        time.sleep(1)
        log = logf.read_text(encoding="utf-8", errors="replace") if logf.exists() else ""
        if "Микрофон:" in log and time.monotonic() > end - 45:
            break
    time.sleep(3)
    core.terminate(); core.wait()
    dry = (d / "dry.jsonl").read_text(encoding="utf-8") if (d / "dry.jsonl").exists() else ""
    return dry, logf.read_text(encoding="utf-8", errors="replace") if logf.exists() else ""


dry, log = run(True)
ok('"media", "pause"' in dry and "⏸" in log, "играет музыка + «пауза» → плеер на паузе")
dry, log = run(False)
ok('"media"' not in dry, "ничего не играет + «пауза» → ничего не делаем")
