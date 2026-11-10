"""Идея №165 (08.11): «при обращении к веб-камере зависает общий драйвер, если камера и микрофон работают через один
USB-канал, — микрофон отваливается до ручного перезапуска драйвера» (в журнале №622 то же: «HK 1080P Cam» — и
микрофон, и камера; поток молчит, MME error 1). Теперь:
— микрофон узнаётся как микрофон той же камеры (по своим словам в именах, без общих «USB», «Camera», «Микрофон»);
— на время кадра его поток закрыт (Engine.mic_paused — mic_release622), после кадра открывается сам;
— ffmpeg, не успевший снять кадр, сначала просят закончить («q») — он закрывает камеру сам, и лишь потом убивают."""
import os, stat, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from audio_io import mic_shares_camera  # noqa: E402
for mic, cam, want in (("Микрофон (4- HK 1080P Cam)", "HK 1080P Cam", True),
                       ("Микрофон (HD Pro Webcam C920)", "HD Pro Webcam C920", True),
                       ("alsa_input.usb-046d_HD_Pro_Webcam_C920_ABC-02.analog-stereo", "HD Pro Webcam C920", True),
                       ("Microphone Array (3- Realtek(R)", "Integrated Camera", False),
                       ("Микрофон (AB13X USB Audio)", "HK 1080P Cam", False),
                       ("Микрофон (USB Audio Device)", "USB Camera", False),
                       ("", "HK 1080P Cam", False)):
    ok(mic_shares_camera(mic, cam) is want, f"«{mic}» и камера «{cam}» — {'одно устройство' if want else 'разные'}")

# ffmpeg завис на камере: сперва «q», и он закрывает камеру сам
import eyes  # noqa: E402
d = Path(tempfile.mkdtemp())
mark = d / "quit.txt"
fake = d / "ffmpeg"
fake.write_text("#!/usr/bin/env python3\nimport sys\nline = sys.stdin.read(1)\n"
                f"open({str(mark)!r}, 'w').write('q' if line == 'q' else 'eof')\nsys.exit(0)\n", encoding="utf-8")
fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
eyes.ffmpeg_path = lambda: str(fake)
os.environ["DEWIAR_FAKE_CAMERA"] = "1"
t0 = time.monotonic()
try:
    eyes.capture_camera(timeout=1)
    err = ""
except eyes.EyesError as e:
    err = str(e)
ok("вовремя" in err and mark.exists() and mark.read_text() == "q", f"не успел — попросили закончить «q», а не убили сразу: {err!r}, {mark.read_text() if mark.exists() else '—'}")
ok(time.monotonic() - t0 < 4, "и долго не ждём")

# инструмент look_camera: микрофон той же камеры — кадр под mic_paused
import contextlib, tools  # noqa: E402
paused = []
eng = types.SimpleNamespace(muted=False, status={"input": "Микрофон (4- HK 1080P Cam)"},
                            mic_paused=lambda why="": (paused.append(why), contextlib.nullcontext())[1])
cfg = {("eyes", "camera"): "HK 1080P Cam", ("audio", "input"): "Микрофон (4- HK 1080P Cam)"}
ctx = {"engine": eng, "settings": types.SimpleNamespace(get=lambda a, b=None: cfg.get((a, b), ""))}
got = []
tools_cc = eyes.capture_camera
eyes.camera_label = lambda dev='': dev           # Linux берёт имя из /sys — здесь камера поддельная
eyes.capture_camera = lambda dev, timeout=20: (got.append((dev, list(paused))), (_ for _ in ()).throw(eyes.EyesError("нет")))[1]
try:
    tools.t_look_camera({}, ctx)
except tools.ToolError:
    pass
ok(got and got[0][1] == ["камера"], f"микрофон из той же камеры — кадр снимается при закрытом микрофоне: {got}")
paused.clear(); got.clear(); cfg[("audio", "input")] = "Микрофон (AB13X USB Audio)"
try:
    tools.t_look_camera({}, ctx)
except tools.ToolError:
    pass
ok(got and got[0][1] == [], "микрофон отдельный — его не трогаем")
eyes.capture_camera = tools_cc
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
