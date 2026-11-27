"""Владелец 22.11: «голос выбирал мужской, а ответы слышу женским… поле, куда я должен сам вставить голос, — откуда
пользователю это знать». Поле «Голос на сервере» пустое — уходил «alloy» (у службы голосов — женский). Теперь пусто —
голос по полу: явно выбранный мужской (женский) Piper, иначе пол персонажа; службе голосов уходит и сам пол. Поле —
«Свой голос на сервере (необязательно)», подсказка говорит, какой голос звучит."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import tts  # noqa: E402
ok(tts.voice_gender({"piper": "ru_RU-denis-medium", "_gender": "female"}) == "male", "выбран мужской Piper у персонажа «женского» пола — мужской")
ok(tts.voice_gender({"piper": "ru_RU-irina-medium", "_gender": "male"}) == "female", "выбран женский Piper — женский")
ok(tts.voice_gender({"_gender": "male"}) == "male" and tts.voice_gender({}) == "", "Piper не выбран — пол персонажа")
sent = []


r = tts.RemoteTTS({"base_url": "http://voices.invalid/v1", "model": "tts-1"})


def fake(body, key, retry=False):
    sent.append(body)
    return iter(())


r._stream = fake
try:
    list(r.synth("Привет", {"piper": "ru_RU-denis-medium", "_gender": "female", "remote": ""}) or [])
except Exception:  # noqa: BLE001
    pass
ok(sent and sent[-1]["voice"] == "onyx" and sent[-1].get("gender") == "male", f"пустое поле — службе голосов мужской голос и пол: {sent[-1:]}")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok("Свой голос на сервере (необязательно)" in html and "vivian, ryan" not in html, "поле — необязательное, без загадочных имён")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
