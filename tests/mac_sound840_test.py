"""№840 (17.11, Mac mini, macOS 27): 1) «в «Звук и поведение» микрофон и динамики — только «Системные по умолчанию»»:
список устройств на Mac был пуст (его брали только на Windows, а Mac тоже слушает через PortAudio / CoreAudio);
2) «окно портит линия сверху с тремя кнопками» — строка заголовка студии теперь прозрачная, страница под ней."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core")); sys.path.insert(0, str(ROOT / "ui"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sd = types.ModuleType("sounddevice")
sd.query_devices = lambda *a: [{"name": "MacBook Pro Microphone", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
                               {"name": "Shure MV7", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
                               {"name": "Studio Display Speakers", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2}]
sd.default = types.SimpleNamespace(device=[0, 2]); sd._terminate = lambda: None; sd._initialize = lambda: None
sys.modules["sounddevice"] = sd
import audio_io  # noqa: E402
audio_io.MAC, audio_io.WIN = True, False
devs = audio_io.list_devices()
ok([d["name"] for d in devs if d["kind"] == "source"] == ["MacBook Pro Microphone", "Shure MV7"]
   and [d["name"] for d in devs if d["kind"] == "sink"] == ["Studio Display Speakers"],
   f"Mac: микрофоны и динамики видны в списке: {[d['name'] for d in devs]}")
ok(audio_io._sd_index("Shure MV7", "source") == 1, "выбранный внешний микрофон открывается по своему номеру")
mac = (ROOT / "ui/macui.py").read_text(encoding="utf-8")
ok("setTitlebarAppearsTransparent_(True)" in mac and "(1 << 15)" in mac and "seamless(win)" in mac,
   "студия на Mac: строка заголовка прозрачная, страница под ней")
ok("mac-seam" in mac and "html.mac-seam main" in (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8"),
   "страница даёт место светофору сверху")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
