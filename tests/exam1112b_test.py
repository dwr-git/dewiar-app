"""Экзамен владельца 12.11 (0.88.0, 103 из 117) — вторая часть разбора, каждое — проверкой:
- morning_tell: в данных «Утра» «Погода: данных нет», а ответ «за окном +5 и пасмурно» — переспрос без погоды;
- call_fallback: «позвони жене, а не ответит — напиши» — «позвонила, она не ответила, отправила сообщение» без звонка
  и сообщения — переспрос: честно, что можно;
- draw_picture_honest: «сгенерируй картинку» → show_images и «Показал.» — переспрос: сказать, что картинки найденные;
- open_folder_after_shot573: в экзамене (ядро --server) снимка экрана не было вовсе — «инструмента нет»; теперь снимок
  «понарошку» (запись + маленький PNG в «Снимки экрана»), чтобы «открой эту папку» проверялось."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_EXAM_LAUNCH"] = str(tmp / "launch.jsonl")
os.environ["HOME"] = str(tmp / "home")
(tmp / "home").mkdir()
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import quality as Q  # noqa: E402

# --- погода в утренней сводке
brief = "Сегодня 12.11.2026, четверг, сейчас 09:00.\nПогода: данных нет (город не задан) — о погоде, температуре и городе не говори ничего, не угадывай.\nДела и напоминания на сегодня: 23:58 Позвонить маме."
ok(Q.weather_invented(brief, "Доброе утро! За окном +5 и пасмурно. В 23:58 — позвонить маме."), "погоды в данных нет, а в ответе «+5 и пасмурно» — переспрос")
ok(Q.weather_invented(brief, "Доброе утро! Сегодня солнечно. Вечером позвонить маме."), "«сегодня солнечно» без данных — тоже выдумка")
ok(not Q.weather_invented(brief, "Доброе утро! В 23:58 — позвонить маме. Ясного вам дня!"), "пожелание «ясного дня» — не погода")
ok(not Q.weather_invented(brief.replace("Погода: данных нет", "Погода: Минск, +3, облачно"), "За окном +3 и облачно."),
   "погода в данных есть — говорить можно")
ok(not Q.weather_invented(brief, "За окном +3.", {"weather"}), "погоду узнали инструментом — можно")

# --- звонок, которого не было
ask = "Позвони жене, а если она не ответит за 30 секунд — отправь ей сообщение «Перезвони, как освободишься»."
ok(Q.call_claim(ask, "Позвонила жене — она не ответила, поэтому отправила ей сообщение «Перезвони, как освободишься»."),
   "«позвонила, не ответила, отправила» без звонка и сообщения — переспрос")
ok(Q.call_claim(ask, "Звоню жене…"), "«звоню» без звонка — переспрос")
ok(not Q.call_claim(ask, "С компьютера позвонить не могу — телефонной связи здесь нет. Могу позвонить с телефона Dewiar, если жена есть в «Близких»."),
   "честное «не могу, вот как можно» — не трогаем")
ok(not Q.call_claim(ask, "Звоню Ане.", {"close_call"}), "звонок через «Близких» был — не трогаем")
ok(not Q.call_claim("как дела?", "Вчера звонила мама."), "без просьбы позвонить — не трогаем")

# --- найденные картинки вместо нарисованной
pic = "Сгенерируй картинку: кот-космонавт в стиле комикса"
ok(Q.found_pics_claim(pic, "Показал.", {"show_images"}), "«Показал.» после show_images на просьбу нарисовать — переспрос")
ok(not Q.found_pics_claim(pic, "Рисовать пока не умею — вот похожие картинки из интернета.", {"show_images"}),
   "сказала, что найденные, — не трогаем")
ok(not Q.found_pics_claim(pic, "Нарисовала.", {"show_images", "artist-main__art_draw"}), "нарисовала «Художником» — не трогаем")
ok(not Q.found_pics_claim("покажи котов-космонавтов", "Показала.", {"show_images"}), "просили показать, а не нарисовать — не трогаем")

ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
for name in ("weather_invented(text", "call_claim(text", "found_pics_claim(text"):
    ok(name in ea, f"проверка {name.split('(')[0]} — в цепочке проверок ответа")

# --- снимок экрана в экзамене
import tools as T  # noqa: E402
ok("save_screenshot" in T.EXAM_ON, "в экзамене снимок экрана есть (EXAM_ON)")
out = T.t_save_screenshot({}, {})
shots = list(tmp.rglob("Снимок экрана *.png"))
ok(shots and shots[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and "Снимки экрана" in out, f"снимок «понарошку» — PNG в «Снимки экрана»: {out}")
rec = [json.loads(x) for x in (tmp / "launch.jsonl").read_text().splitlines()]
ok(["screenshot"] in rec, f"снимок записан в журнал запусков экзамена: {rec}")

print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
