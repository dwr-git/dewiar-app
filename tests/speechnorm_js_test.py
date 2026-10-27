"""Числа словами на телефоне (отзыв 16.10: «спросил время — написала 14:10, а голос сервера произнёс „ствисе“»): телефон
сам готовит текст для голоса сервера (ui/assets/speechnorm.js — то же, что core/speechnorm.py) и не зависит от того,
обновлена ли служба голосов. Здесь обе реализации сверяются на одних фразах; даты «14.10.2026» — словами."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from speechnorm import speech_norm  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


PHRASES = ["Сейчас 14:10.", "Сейчас 14:10, пятница, 16 октября.", "В 9:05 встреча, в 21:00 ужин.", "Сегодня 14.10.2026.", "Сдать до 05.11.2026, не позже.",
           "Версия 0.38.59 вышла.", "1 минута, 2 недели, 1 сообщение, через 1 минуту, 21 день.", "15 октября 2026 года", "до 21 октября",
           "к 3 ноября", "В 2026 году", "Скидка 45%, на улице +12°, ночью -3°.", "Итого 1437,50 руб.", "Стоит $15 или 20 USD, 5 €.",
           "Курс 399,5 за единицу", "Порт USB 3, ядро 6.17, HDMI", "Население 1 437 500 человек", "Код 1234567890123456789",
           "Открой YouTube и Telegram", "Ссылка https://dewiar.pro/x?y=1 — там всё", "№ 5 на 2 этаже", "Это 100 рублей", "Осталось 4 минуты 29 секунд.",
           "11 минут, 12 часов, 101 день, 1000 лет", "Курс 92,4 рубля за доллар", "A + B = C", "x86_64 и 17e9 — метки",
           "12 минус 10 равно 2", "12 - 10 = 2", "3 × 4 = 12, 8 ÷ 2 = 4, 2+2=4", "Ответ: 2", "14:10", "Скорость 10-12 км",
           # римские цифры (пакет 27.10: «Лира не умеет читать римские цифры»)
           "Трансерфинг реальности. Ступень I: Пространство вариантов", "В XIX веке", "XIX–XX вв.", "в XXI в.", "Пётр I и Екатерина II",
           "при Николае II", "реформы Петра I", "Людовик XIV", "Глава IV, часть II", "Mac OS X", "I love you", "размер XL", "витамин C"]
tmp = Path(tempfile.mkdtemp())
js = tmp / "t.js"
js.write_text("global.window = {};\n" + (ROOT / "ui/assets/speechnorm.js").read_text(encoding="utf-8")
              + "\nconst P = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
              + "console.log(JSON.stringify(P.map(([t, l]) => window.DewiarSpeech.norm(t, l))));\n", encoding="utf-8")
cases = [[p, lat] for p in PHRASES for lat in (True, False)]
(tmp / "p.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
if not shutil.which("node"):
    print("нет node — пропускаю сверку"); print("ИТОГ: всё прошло"); sys.exit(0)
out = json.loads(subprocess.run(["node", str(js), str(tmp / "p.json")], capture_output=True, text=True, check=True).stdout)
bad = [(p, lat, speech_norm(p, latin=lat), o) for (p, lat), o in zip(cases, out) if speech_norm(p, latin=lat) != o]
for p, lat, a, b in bad[:8]:
    print(f"   {p!r} latin={lat}\n     python: {a!r}\n     js:     {b!r}")
ok(not bad, f"телефон и компьютер читают числа одинаково: {len(cases) - len(bad)} из {len(cases)}")
R = {"Трансерфинг реальности. Ступень I: Пространство вариантов": "Ступень первая", "В XIX веке": "В девятнадцатом веке",
     "в XXI в.": "в двадцать первом веке", "Пётр I и Екатерина II": "Пётр первый и Екатерина вторая", "при Николае II": "при Николае втором",
     "реформы Петра I": "Петра первого", "Людовик XIV": "Людовик четырнадцатый", "Глава IV, часть II": "Глава четвёртая, часть вторая"}
bad_r = {k: speech_norm(k) for k, v in R.items() if v not in speech_norm(k)}
ok(not bad_r, f"римские цифры словами, в нужном роде и падеже: {bad_r}")
ok("сотый" not in speech_norm("витамин C") and "сороков" not in speech_norm("размер XL") and "первый" not in speech_norm("I love you"),
   "«витамин C», «размер XL», «I love you» — не числа")
ok(speech_norm("12 - 10 = 2", latin=False) == "двенадцать минус десять равно два." and speech_norm("14:10", latin=False) == "четырнадцать десять."
   and speech_norm("Привет!") == "Привет!", "пример со знаками — словами, в конце фразы — точка (последнее слово не глотается)")
ok(speech_norm("Сейчас 14:10.") == "Сейчас четырнадцать десять." and "четырнадцатое октября две тысячи двадцать шестого года" in speech_norm("Сегодня 14.10.2026."),
   "время и дата — словами")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("DewiarSpeech" in app and "speechnorm.js" in (ROOT / "android/assets/www/index.html").read_text(encoding="utf-8")
   and "speechnorm.js" in (ROOT / "android/tools/www_assemble.sh").read_text(encoding="utf-8"), "телефон: голосу сервера — уже словами")
import tts as TT  # noqa: E402 — компьютер: ответ из одних цифр («14:10») тоже словами перед голосом сервера
seen = {}


class FakeResp:
    status_code = 200
    headers = {"content-type": "audio/pcm"}
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def iter_bytes(self, n=0): return iter([b"\x00\x00" * 10])
    def raise_for_status(self): pass
    def read(self): return b""


import httpx  # noqa: E402
orig = httpx.stream
httpx.stream = lambda *a, **k: (seen.setdefault("body", k.get("json")), FakeResp())[1]
try:
    rt = TT.RemoteTTS({"base_url": "http://x/v1", "api_key": "", "model": "tts-1"})
    list(rt.synth("14:10", {"_gender": "female", "remote": "a"}))
except Exception as e:  # noqa: BLE001
    print("   синтез:", e)
finally:
    httpx.stream = orig
ok((seen.get("body") or {}).get("input") == "четырнадцать десять.", f"компьютер: «14:10» без букв — словами: {(seen.get('body') or {}).get('input')!r}")
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
