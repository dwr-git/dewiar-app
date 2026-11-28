"""Папка ассистента и обработка голоса: модули без ядра."""
import shutil, os, sys, tempfile, wave, subprocess
from pathlib import Path
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_WORKSPACE"] = str(tmp / "ws")
os.environ.setdefault("DEWIAR_STATE_DIR", str(tmp / "st")); os.environ.setdefault("DEWIAR_CONFIG_DIR", str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
from workspace import Workspace, WorkspaceError  # noqa: E402
import tools as T  # noqa: E402
import voicefx as V  # noqa: E402

def ok(c, m): print(("✅ " if c else "❌ ") + m)

ws = Workspace(None); r = ws.ensure()
ok(all((r / f).is_dir() for f in ("Заметки", "Лаборатория", "Дневник", "Память")) and (r / "README.md").exists(), "папка создана со структурой и README")
p = ws.save_note("Список покупок", "- хлеб\n- молоко")
p2 = ws.save_note("Список покупок", "- сыр", append=True)
txt = (r / p).read_text()
ok(p == p2 == "Заметки/Список покупок.md" and "сыр" in txt and "хлеб" in txt, "заметка сохранена и дополнена")
p3 = ws.save_note("Список покупок", "новый")
ok(p3.endswith("(2).md"), "одноимённая заметка не затирается")
ok(ws.save_note("План", "шаги", folder="Работа") == "Заметки/Работа/План.md", "заметка в подпапке")
# студия «Память»: новая заметка, правка, переименование, в корзину
os.environ.setdefault("XDG_DATA_HOME", str(tmp / "xdg"))
n1 = ws.new_note("Идеи / для Эвы")
ws.write(n1, "# Идеи\n\nпервая строка\nвторая")
n2 = ws.rename(n1, "Идеи для Эвы")
try:
    ws.write("../вне.md", "x"); out_ok = False
except WorkspaceError:
    out_ok = True
try:
    ws.write("Лаборатория/скрипт.py", "x"); py_ok = False
except WorkspaceError:
    py_ok = True
try:
    ws.remove("Память/Обо мне.md"); mem_ok = False
except WorkspaceError:
    mem_ok = True
ws.remove(n2)
ok(n1 == "Заметки/Идеи для Эвы.md" and n2 == n1 and out_ok and py_ok and mem_ok and not (r / n2).exists(),
   "редактор заметок: создать, править, переименовать, в корзину; вне папки и не заметки — нельзя; «Обо мне» не удаляется")
n3 = ws.new_note("Черновик"); n4 = ws.rename(n3, "Чистовик")
ok(n4 == "Заметки/Чистовик.md" and (r / n4).read_text(encoding="utf-8").startswith("# Черновик"), "переименование заметки")
f = ws.find("молоко")
ok(f and f[0]["path"] == "Заметки/Список покупок.md" and "молоко" in f[0]["snippet"], "поиск по заметкам")
ok(ws.remember("Любит крепкий чай") == "Запомнил." and ws.remember("любит крепкий чай") == "Это я уже знаю.", "память без повторов")
# №1148 (28.11): «Не любит кофе» записано — «Любит кофе» не «уже знаю» (раньше — поиск подстрокой по всему файлу)
ws.remember("Не любит кофе")
ok(ws.remember("Любит кофе") != "Это я уже знаю.", "«Любит кофе» после «Не любит кофе» — не «уже знаю»")
ok(ws.remember("крепкий чай") == "Это я уже знаю." and ws.remember("Не любит кофе.") == "Это я уже знаю.", "часть записи целыми словами и та же запись — по-прежнему «уже знаю»")
ok(ws.remember("Любит кре") == "Запомнил.", "кусок слова — не «уже знаю»")
ok("крепкий чай" in ws.memory_text() and "Обо мне" not in ws.memory_text(), "память читается для подсказки модели")
d = ws.diary("Обсуждали отпуск, важно успеть до пятницы", "Девиар")
ok("Дневник/" in d and "### " in (r / d).read_text() and "Девиар" in (r / d).read_text(), "запись в дневник")
ws.lab_write("sum.py", "import sys\nprint(sum(int(x) for x in sys.argv[1:]))\n")
res = ws.lab_run("sum.py", "2 3 4")
ok(res["code"] == 0 and res["output"].strip() == "9" and (r / res["log"]).exists(), "лаборатория: скрипт запущен, вывод в .log")
try:
    ws.read("../../etc/passwd"); bad = False
except WorkspaceError:
    bad = True
ok(bad, "нельзя выйти за пределы папки")
ws.sync_reminders([{"id": "a1", "at": "2026-10-01T09:00:00", "text": "позвонить маме"}])
ok("позвонить маме" in (r / "Напоминания.md").read_text(), "Напоминания.md обновляется")
tree = ws.tree()
names = [n["name"] for n in tree["items"]]
ok("Заметки" in names and any(c["name"] == "Работа" for n in tree["items"] if n["name"] == "Заметки" for c in n["children"]), "дерево для студии")
# инструменты через Toolbox
class FakeS:
    def get(self, *k): return {} if k[0] == "tools" else None
tb = T.Toolbox(FakeS(), None)
tb.hooks.update(workspace=ws, persona_name=lambda: "Лира")
out = tb.run("save_note", {"title": "Идеи", "text": "фильм"})
ok("Заметки/Идеи.md" in out, "инструмент save_note")
ok("Лира" in (r / tb.run("write_diary", {"entry": "Пользователь любит кино"}).split("(")[1].rstrip(").")).read_text(), "инструмент write_diary подписывает персонажа")
ok(tb.policy("lab_run") == (True, True) and tb.policy("save_note") == (True, False), "запуск скриптов — с подтверждением")
# голос
if shutil.which("espeak-ng"):
    subprocess.run(["espeak-ng", "-v", "ru", "-w", str(tmp / "s.wav"), "Проверка обработки голоса"], check=True)
    w = wave.open(str(tmp / "s.wav")); rate = w.getframerate(); pcm = w.readframes(w.getnframes())
else:                          # нет espeak-ng (на GitHub не всегда ставится) — «голос» из гармоник с плавающей высотой
    rate = 22050
    t = np.arange(int(rate * 1.5)) / rate
    ph = 2 * np.pi * np.cumsum(140 * (1 + 0.2 * np.sin(2 * np.pi * 2 * t))) / rate
    pcm = (6000 * (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t))).astype(np.int16).tobytes()
good = True
for name in V.PRESETS:
    fx = V.VoiceFX(name, rate); a = b"".join(fx.process(pcm[i:i + 3000]) for i in range(0, len(pcm), 3000)) + fx.flush()
    fx2 = V.VoiceFX(name, rate); b = fx2.process(pcm) + fx2.flush()
    x, y = np.frombuffer(a, np.int16).astype(float), np.frombuffer(b, np.int16).astype(float); n = min(len(x), len(y))
    good &= len(x) > 0 and np.abs(x[:n] - y[:n]).max() <= 2 and not np.isnan(x).any()
ok(good, f"обработка голоса: {len(V.PRESETS)} вариантов, потоково = целиком")
ok(V.pitch_of("deep") < 1 and V.pitch_of("off") == 1 and V.pitch_of("нет такого") == 1, "высота по вариантам")
# Vosk TTS: определение мужских/женских дикторов и раздача персонажам (синтезатор — заглушка)
import tts as TT  # noqa: E402
class StubSynth:
    F0 = [210.0, 118.0, 235.0, 102.0]
    def synth_audio(self, text, speaker_id=0, speech_rate=None, **kw):
        if speaker_id >= len(self.F0): raise IndexError("нет диктора")
        t = np.arange(int(22050 * 1.2)) / 22050
        f = self.F0[speaker_id] * (1 + 0.03 * np.sin(2 * np.pi * 3 * t))
        ph = 2 * np.pi * np.cumsum(f) / 22050
        return (8000 * (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph))).astype(np.int16)
vt = TT.VoskTTS(tmp / "models"); vt._load(None, synth=StubSynth())
g = {s["id"]: s["gender"] for s in vt.speakers}
ok(g == {0: "female", 1: "male", 2: "female", 3: "male"}, f"голоса Vosk: пол определён по высоте ({[s['f0'] for s in vt.speakers]})")
order = [("dewiar", "male", 0), ("patrik", "male", 1), ("agent", "male", 2), ("lira", "female", 0), ("eva", "female", 1)]
m = {pid: vt.pick({"_gender": gen, "_pid": pid, "_slot": sl}) for pid, gen, sl in order}
ok(all(g[m[p]] == ("male" if p in ("dewiar", "patrik", "agent") else "female") for p in m) and len({m["lira"], m["eva"]}) == 2,
   f"персонажам — голоса своего пола, Лире и Эве разные ({m})")
ok(vt.pick({"vosk": 2, "_gender": "male"}) == 2, "голос, выбранный вручную, важнее автоматики")
chunks = list(vt.synth("Проверка", {"_gender": "male", "_pid": "dewiar"}, speed=1.1))
ok(chunks and chunks[0][0] == 22050 and len(chunks[0][1]) > 1000, "синтез Vosk TTS отдаёт звук")
