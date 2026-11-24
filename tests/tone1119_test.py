"""Эмоции в голосе (19.11, владелец: «эмоций нет… ДА ДА ДА!!!»). Тон фразы — по её словам и настроению вопроса: радость,
сочувствие, шутка, удивление, серьёзное; иначе — обычный тёплый голос. Голос Dewiar (Qwen3-TTS) получает манеру на фразу
(instruct), прочие голоса — чуть темп, лицо — улыбка после радости и шутки, без случайных улыбок при сочувствии."""
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


import tone as T  # noqa: E402

cases = [
    ("Поздравляю! Это огромный успех.", None, "joy"),
    ("Вот, держи анекдот: заходит программист в бар…", None, "playful"),
    ("Мне очень жаль. Держитесь.", None, "sympathy"),
    ("Ого, вот это да!", None, "surprise"),
    ("Осторожно: при такой температуре обратитесь к врачу.", None, "calm"),
    ("Завтра в Минске облачно, около пяти градусов.", None, None),
    ("Хорошо, напомню завтра в 10.", None, None),
    ("Завтра будет солнечно!", "sad", "sympathy"),
    ("Это здорово!", "sad", "sympathy"),
    ("Вы молодец, так держать!", "joy", "joy"),
    ("Отлично, записала.", None, None),
    ("Как здорово, что получилось!", None, "joy"),
]
for s, mood, want in cases:
    ok(T.tone_of(s, mood) == want, f"«{s}» ({mood or 'обычный вопрос'}) → {T.tone_of(s, mood)} (ждали {want})")
ok(T.mood_of("У меня сегодня умерла собака") == "sad" and T.mood_of("Я сдал экзамен!") == "joy" and T.mood_of("Какая погода завтра?") is None,
   "настроение вопроса: грусть, радость, обычный")
ok(T.mood_of("что такое\n\nВложения:\nпохороны.pdf") is None, "вложения не задают настроение")
ok(all(len(v) < 80 for v in T.INSTRUCT.values()) and set(T.SPEED) <= set(T.INSTRUCT), "указания короткие; темп — для тех же тонов")

# --- голос Dewiar получает манеру на фразу; свой сервер человека — нет ---
import tts as TTS  # noqa: E402
seen = []


class R(TTS.RemoteTTS):
    def _stream(self, body, key, retry):
        seen.append(body)
        yield 24000, b"\0\0"


list(R({"base_url": "https://dewiar.pro/dwrapp/cloud.php?p=/v1", "cloud": True}).synth("Поздравляю!", {"_tone": "joy", "_pid": "lira"}))
ok(seen and seen[-1].get("instruct") == T.INSTRUCT["joy"] and seen[-1].get("persona") == "lira", f"голос Dewiar: манера «радость»: {seen[-1] if seen else '—'}")
list(R({"base_url": "https://dewiar.pro/dwrapp/cloud.php?p=/v1", "cloud": True}).synth("Завтра облачно.", {"_pid": "lira"}))
ok("instruct" not in seen[-1], "обычная фраза — без указаний (свой обычный голос)")
list(R({"base_url": "http://192.168.1.5:8000/v1"}).synth("Поздравляю!", {"_tone": "joy"}))
ok("instruct" not in seen[-1], "свой сервер голоса человека — без незнакомых ему полей")

# --- служба голосов: манера на фразу — и встроенным дикторам, и голосам по описанию ---
app = (ROOT / "server/voices/app.py").read_text(encoding="utf-8")
ok('if body.get("instruct") and spec.get("kind") in ("speaker", "design"):' in app, "служба голосов: тон фразы — встроенным и голосам по описанию")

# --- синтез ответа и лицо ---
er = (ROOT / "core/engine_remote.py").read_text(encoding="utf-8")
ok("_tone.tone_of(text, mood)" in er and 'self.emit("tone", tone=tn)' in er and "sp_t = speed * _tone.speed_of(tn)" in er,
   "каждая фраза ответа — со своим тоном и чуть темпом; виджету — событие")
ent = (ROOT / "ui/assets/entities.js").read_text(encoding="utf-8")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("tnWarm" in ent and "!tnSoft && Math.random() < 0.3" in ent and 'core.on("tone"' in hud, "лицо: улыбка после радости, без случайных улыбок при сочувствии")
# --- телефон и веб-версия: тот же тон (ui/assets/tone.js) ---
import json, shutil, subprocess  # noqa: E402
node = shutil.which("node")
if node:
    js = (ROOT / "ui/assets/tone.js").read_text(encoding="utf-8")
    probe = [c[0] for c in cases] + ["У меня сегодня умерла собака", "Я сдал экзамен!", "Какая погода завтра?"]
    r = subprocess.run([node, "-e", js + "\nconst T = globalThis.DewiarTone, a = JSON.parse(process.argv[1]);"
                        "console.log(JSON.stringify({ tone: a.cases.map(c => T.toneOf(c[0], c[1])), mood: a.q.map(q => T.moodOf(q)) }))",
                        json.dumps({"cases": [[c[0], c[1]] for c in cases], "q": probe})], capture_output=True, text=True, timeout=30)
    got = json.loads(r.stdout or "{}")
    ok(got.get("tone") == [T.tone_of(c[0], c[1]) for c in cases] and got.get("mood") == [T.mood_of(q) for q in probe],
       f"телефон решает тон так же, как компьютер: {r.stderr[-200:] if r.returncode else 'да'}")
ph = (ROOT / "android/www-src/app/06-ears-voice.js").read_text(encoding="utf-8")
ok("DewiarTone.toneOf(t" in ph and "instruct: DewiarTone.INSTRUCT[tn]" in ph and "(S.tts.rate || 1.0) * tsp" in ph and "window.DEWIAR_TONE" in ph,
   "телефон: голосу Dewiar — манера, голосу телефона — темп, лицу — тон")
ok('tone.js' in (ROOT / "android/tools/www_assemble.sh").read_text(encoding="utf-8") and 'src="tone.js"' in (ROOT / "android/assets/www/index.html").read_text(encoding="utf-8"),
   "tone.js — в наборе телефона и веб-версии")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
