"""№339 (19.11, Debian, Bluetooth-наушники): «когда Лира включает голос, весь звук компьютера пропадает — в наушниках её не
слышно, микрофон работает». Эхоподавление (module-echo-cancel) грузилось поверх Bluetooth-наушников, а сервер звука делал
его выход «по умолчанию»: весь звук шёл через Dewiar и пропадал при смене профиля наушников. Теперь: Bluetooth — модуль не
грузим (эха в наушниках нет, слушаем как «Я в наушниках»); обычный выход — после загрузки возвращаем выход и вход
компьютера по умолчанию, если сервер их подменил."""
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import audio_io as A  # noqa: E402

A.WIN = A.MAC = False
A._pulsectl_ok = lambda: False
A.shutil.which = lambda n: "/usr/bin/" + n
calls, state = [], {}


def fake_run(cmd, timeout=5):
    calls.append(cmd)
    if cmd[:2] == ["pactl", "info"]:
        return 0, f"Server Name: PulseAudio\nDefault Sink: {state['sink']}\nDefault Source: {state['src']}\n", ""
    if cmd[:4] == ["pactl", "list", "short", "sources"]:
        return 0, "1\talsa_input.pci.analog-stereo\n", ""
    if cmd[:2] == ["pactl", "load-module"]:
        if state.get("switch"):                     # module-switch-on-connect: новое устройство — по умолчанию
            state["sink"], state["src"] = A.AEC_SINK, A.AEC_SOURCE
        return 0, "42\n", ""
    if cmd[:2] == ["pactl", "set-default-sink"]:
        state["sink"] = cmd[2]
        return 0, "", ""
    if cmd[:2] == ["pactl", "set-default-source"]:
        state["src"] = cmd[2]
        return 0, "", ""
    return 0, "", ""


A._run = fake_run

# 1) Bluetooth-наушники — модуль не грузим
state.update(sink="bluez_output.AA_BB_CC_DD_EE_FF.1", src="bluez_input.AA_BB_CC_DD_EE_FF.0")
ec = A.EchoCancel()
ok(ec.setup() is False and ec.bt is True, "Bluetooth по умолчанию — эхоподавление не включаем, отмечено «наушники»")
ok(not any(c[:2] == ["pactl", "load-module"] for c in calls), "модуль поверх Bluetooth не грузится")
calls.clear()
ok(A.EchoCancel().setup(sink_master="bluez_sink.11_22.a2dp_sink") is False, "выбран Bluetooth-выход в настройках — тоже без модуля")

# 2) обычный выход, сервер подменил «по умолчанию» на модуль — возвращаем
state.update(sink="alsa_output.pci.analog-stereo", src="alsa_input.pci.analog-stereo", switch=True)
calls.clear()
ec = A.EchoCancel()
ok(ec.setup() is True and ec.bt is False and ec.module_id == "42", "обычный выход — эхоподавление включено")
ok(state["sink"] == "alsa_output.pci.analog-stereo" and state["src"] == "alsa_input.pci.analog-stereo",
   f"звук компьютера по умолчанию — прежний: {state['sink']}, {state['src']}")

# 3) сервер ничего не подменял — ничего и не трогаем
state.update(sink="alsa_output.pci.analog-stereo", src="alsa_input.pci.analog-stereo", switch=False)
calls.clear()
A.EchoCancel().setup()
ok(not any(c[:2] in (["pactl", "set-default-sink"], ["pactl", "set-default-source"]) for c in calls), "не подменили — не трогаем")

src = (ROOT / "core/ears_mic.py").read_text(encoding="utf-8")
ok('getattr(self.aec, "bt", False)' in src, "Bluetooth — как «Я в наушниках»: можно перебивать")
pl = (ROOT / "core/pulse.py").read_text(encoding="utf-8")
ok("def defaults():" in pl and "def set_defaults(" in pl, "то же через libpulse (pulsectl)")

print("\nИтог:", "всё хорошо" if not fails else f"ошибок {len(fails)}")
sys.exit(1 if fails else 0)
