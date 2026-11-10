"""№592 и №611 (06–07.11, Windows): «любой ассистент читает вслух то, чего нет: ЭСССР ноль градусов, ЭРРРРРР», «при
замене голоса Лиры и имени Джарвис — РРР сССС, вибро р градусов умножить на рррр градусов». Причины:
— голос Windows (SAPI, в своём процессе) получал текст в UTF-8, а Python в Windows читает стандартный ввод в кодировке
  системы (cp1251): «а» (D0 B0) превращалась в «Р°» — «эр градусов»; теперь текст уходит только в ASCII (\\uXXXX);
— №611: в голосе Лиры после правки в «Персонажах» оказался пустой голос Piper («Голос не скачался: not enough values to
  unpack») — и говорил аварийный голос Windows. Пустое или чужое имя голоса чинится при чтении и при сохранении
  (голос шаблона или по полу), студия не отправляет пустой выбор, Piper отвечает понятной ошибкой."""
import json, os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
d = tempfile.mkdtemp(); os.environ.update(DEWIAR_CONFIG_DIR=d + "/cfg", DEWIAR_STATE_DIR=d + "/st")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import subprocess  # noqa: E402
import tts  # noqa: E402
sent = {}


def fake_run(cmd, input=None, env=None, **kw):
    sent.update(input=input, env=env or {})
    return types.SimpleNamespace(returncode=0, stdout="AAAA", stderr="")


real_run = subprocess.run
subprocess.run = fake_run
try:
    list(tts.SapiTTS().synth("Сейчас -5°C, в СССР было холоднее.", {"_gender": "female"}))
finally:
    subprocess.run = real_run
raw = sent["input"]
ok(raw.isascii(), "в процесс голоса Windows текст уходит только ASCII-символами")
# так его прочтёт Python в Windows с кодировкой системы cp1251 (стандартный ввод — канал, не консоль)
got = json.loads(raw.encode("utf-8").decode("cp1251"))["text"]
ok(got.startswith("Сейчас минус пять градусов") and "Р°" not in got, f"и в cp1251 читается тем же текстом: «{got}»")
old = json.dumps({"text": "Сейчас"}, ensure_ascii=False).encode("utf-8").decode("cp1251")
ok("Р" in old and "Сейчас" not in old, f"(раньше в cp1251 было: {old!r} — «эр… градусов»)")
ok(sent["env"].get("PYTHONIOENCODING") == "utf-8", "процессу голоса — ввод и вывод в UTF-8")

# №611: пустой голос Piper у персонажа
import personas as P  # noqa: E402
from settings import PERSONAS_DIR  # noqa: E402
PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
(PERSONAS_DIR / "lira.json").write_text(json.dumps({"name": "Лира", "voice": {"piper": "", "length_scale": 1.0, "remote": "serena"}},
                                                   ensure_ascii=False), encoding="utf-8")
ps = P.Personas()
v = ps.get("lira")["voice"]
ok(v["piper"] == "ru_RU-irina-medium" and v.get("remote") == "serena", f"сохранённый пустой голос Лиры чинится при чтении: {v}")
pid = ps.save({"id": "lira", "name": "Джарвис", "gender": "male", "wake": ["джарвис"], "voice": {"piper": "", "length_scale": 1}})
saved = json.loads((PERSONAS_DIR / "lira.json").read_text(encoding="utf-8"))
ok(P.piper_ok(saved["voice"]["piper"]), f"студия прислала пустой голос — сохранён настоящий: {saved['voice']}")
pid2 = ps.save({"name": "Мой", "gender": "male", "voice": {"piper": "ru_RU-ruslan-medium"}})
ok(ps.get(pid2)["voice"]["piper"] == "ru_RU-ruslan-medium", "выбранный голос не трогаем")
ok(P.fix_voice({"piper": "kseniya"}, "male")["piper"] == "ru_RU-denis-medium", "чужое имя (голос сервера) — голос Piper по полу")
try:
    tts.PiperTTS().ensure("")
    err = ""
except ValueError as e:
    err = str(e)
ok("нет такого голоса" in err, f"Piper на пустое имя — понятная ошибка, а не «not enough values to unpack»: {err!r}")
js = (ROOT / "ui/studio/personas.js").read_text(encoding="utf-8")
ok(js.count('$("#e-piper").value || ed.voice.piper') == 2 and "pvs[ed.voice.piper] = ed.voice.piper" in js,
   "студия: голоса нет в списке — он остаётся выбранным, пустой выбор не уходит")
src = (ROOT / "core/engine_remote.py").read_text(encoding="utf-8")
ok("fix_voice(voice" in src, "«Прослушать» в студии тоже не отдаёт пустой голос аварийному")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
