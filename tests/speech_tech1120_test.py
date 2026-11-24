"""Владелец 20.11: «ужасно, когда она произносит английские аббревиатуры, проговаривает ссылки на сайты». Технический
ответ вслух: единицы — словами и в нужной форме, сайт — его именем, «§6.5» — «пункт…», «2–3» — «два-три»."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from speechnorm import speech_norm  # noqa: E402
from llm_speech import speakable  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

def say(t): return speech_norm(speakable(t))

s = say("Карты H200 NVL 141 GB, занято 30 и 27 GB, голос 43 МБ/с, пик 225 тыс./с, 0.26–0.33 Гбит/с.")
ok("сто сорок один гигабайт" in s and "тридцать и двадцать семь гигабайт" in s and "сорок три мегабайта в секунду" in s
   and "двести двадцать пять тысяч в секунду" in s and "гигабита в секунду" in s and "джи-би" not in s, s)
s = say("Окно 12 ч вместо 24 ч, задержка 72 мс, 1 мин.")
ok("двенадцать часов" in s and "двадцать четыре часа" in s and "семьдесят две миллисекунды" in s and "одна минута" in s, s)
s = say("Новости — news.rambler.ru и lenta.ru; скачать — dewiar.pro/dwrapp/download.")
ok("рамблер" in s and "лента" in s and "ру" not in s.split() and "невс" not in s and "дэвиаар" in s, s)
s = say("В §6.5 сказано: 2–3 ядра.")
ok("пункт шесть точка пять" in s and "два-три ядра" in s, s)
s = say("Версия 1.0.49, файл отчёт.pdf, 1.5 книги, 92,4 рубля.")
ok("один точка ноль точка сорок девять" in s and "отчёт" in s and "девяносто два рубля сорок копеек" in s, f"прочее — как было: {s}")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
