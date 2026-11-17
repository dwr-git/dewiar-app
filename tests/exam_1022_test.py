"""Экзамен 1.0.22 (17.11, владелец, «DWR Chat Qwen 3.8», 113 из 129): «сказала, что сделала» без дела.
site_watch_791: «Выполнено инструментами: watch (args {…}). Поставила дозор…» — модель переписала НАШУ пометку из истории
  вместо вызова, дозора нет.
disk_free_real_call: «На диске свободно 210 ГБ из 490» — ни одного действия, цифры выдуманы.
skill_create_782: create_skill ждал «Выполнить?», ответа не было — а в ответе «Создала навык «Итог недели»».
open_folder_after_shot573: «Сделай снимок экрана» → «Открой эту папку» — путь снимка не остался в истории, папку угадывала."""
import os, re, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "ucfg"), DEWIAR_STATE_DIR=str(tmp / "ust"), HOME=str(tmp / "home"))
(tmp / "home").mkdir()
sys.path.insert(0, str(ROOT / "core"))
import quality  # noqa: E402
from quality import fake_call, failed_claim, failed_note, hold_sentence, system_invented  # noqa: E402

# ---------- site_watch_791: наша пометка, переписанная моделью
said = 'Выполнено инструментами: watch (args {"kind":"page","url":"https://example.com","every_minutes":30}).\n\nПоставила дозор на эту страницу.'
ok(fake_call(said, ["watch", "app_help"]), "«Выполнено инструментами: watch (…)» — вызов, написанный текстом")
ok(fake_call("Записала.\n[в этом ответе выполнено инструментами: remember]", []), "пометка в квадратных скобках — тоже")
ok(fake_call("Готово. [узнано инструментами — опирайся на это: weather(Минск) → +3]", []), "и пометка «узнано инструментами»")
ok(not fake_call("Поставила дозор: буду смотреть раз в полчаса и скажу, если изменится.", ["watch"]), "обычный ответ — не вызов текстом")
ok(not fake_call("Я много чего умею, инструментами пользуюсь часто: поиск, заметки, напоминания.", ["watch"]), "слово «инструментами» в речи — не вызов")
ok(hold_sentence("Следи за сайтом", "Следи за сайтом", said, (), {"watch", "app_help"}), "такую фразу не озвучиваем до переделки")
src = (ROOT / "core/answer_rules.py").read_text(encoding="utf-8")
ok("[в этом ответе выполнено инструментами: " in src, "пометка в истории осталась (она помогает моделям не путать слова с делом)")

# ---------- disk_free_real_call: цифры этого компьютера без проверки
q = "Проверь, сколько свободного места на диске этого компьютера."
ok(system_invented(q, "На диске свободно 210 ГБ из 490.", []), "«свободно 210 ГБ» без system_status — выдумка, просим проверить")
ok(not system_invented(q, "На диске свободно 210 ГБ из 490.", ["system_status"]), "с system_status — верим")
ok(not system_invented(q, "На диске свободно 210 ГБ из 490.", ["run_command"]), "с командой — тоже")
ok(system_invented("Сколько оперативной памяти занято?", "Занято 63% памяти.", []), "память в процентах без проверки — тоже")
ok(system_invented("Сколько места на диске C?", "Свободно 12 ГБ", []), "«место на диске C»")
for ask, ans in (("Хватит ли места на флешке на 32 ГБ для фильма?", "Да, фильм весит 4 ГБ."),
                 ("Сколько стоит SSD на 1 ТБ?", "Около 6000 рублей за 1 ТБ."),
                 ("Как почистить диск?", "Откройте «Очистка диска» — освободит 5–10 ГБ."),
                 ("Проверь место на диске", "Сейчас посмотрю.")):
    ok(not system_invented(ask, ans, []), f"не про этот компьютер или без цифр — не трогаем: «{ask}»")
ok(hold_sentence(q, q, "На диске свободно 210 ГБ из 490.", (), {"system_status"}), "выдуманные гигабайты не озвучиваются")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok(re.search(r"system_invented\(ask0, step_text, called\) if \"system_status\" in names_", ea), "проверка стоит в ряду «сказала — проверь» разговора")

# ---------- skill_create_782: «Выполнить?» без ответа — не «создала»
pend = [("create_skill", "не выполнено: человек ещё не ответил «да» на «Выполнить?»")]
fix = failed_claim("Создала навык «Итог недели». Теперь, когда скажешь «итог недели», я соберу дела.", pend, ["app_help"])
ok(fix and "«да»" in fix and "Не говори «готово»" in fix, "«Создала навык», а разрешения не было — просим честно сказать, что ждём «да»")
ok(not failed_claim("Сделаю навык «Итог недели» — жду твоего «да»: нажми «Выполнить» или скажи «да».", pend, []),
   "«жду твоего да» — честно, не трогаем")
ok("жду вашего «да»" in failed_note(pend), "если и после этого «создала» — приписка «ещё не сделано — жду вашего «да»»")
ok(failed_claim("Создала навык «Итог недели».", [("create_skill", "навык с таким именем уже есть")], []),
   "create_skill с ошибкой — «создала» тоже ловится (раньше — только «готово/сделала»)")
et = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
i = et.find('error="ответа не было — спрошу ещё раз"')
ok(i > 0 and "turn.tools_err" in et[i:i + 600], "ответа на «Выполнить?» не было — действие записано как невыполненное")

# ---------- open_folder_after_shot573: путь снимка — в истории разговора
import engine_base  # noqa: E402
ok("save_screenshot" in engine_base.FACT_TOOLS, "снимок экрана — среди «что узнала» (путь остаётся в истории)")
line = engine_base.fact_line("save_screenshot", {}, "Снимок экрана сохранён: /home/u/Pictures/Снимки экрана/Снимок 2026-11-17 15-08-07.png. "
                             "Скажи пользователю коротко, что сохранил в «Изображения/Снимки экрана».")
ok("/home/u/Pictures/Снимки экрана/" in line, f"в строке истории — полный путь папки: {line[:120]}")

# ---------- draw_offer_plugin: «Художник» выключен — открытка символами вместо предложения включить
import json  # noqa: E402
from plugins import Plugins  # noqa: E402
from quality import plugin_offer_missed  # noqa: E402
art = json.loads((ROOT / "data/plugins/artist/plugin.json").read_text(encoding="utf-8"))
art.setdefault("id", "artist")
hint = Plugins.offer_hint(None, art)
ok(plugin_offer_missed(hint, "С радостью! Вот открытка:\n```\n  С ДНЁМ РОЖДЕНИЯ, МАМА!\n```", []),
   "справка «Художник выключен», а ответ — открытка символами: переспрос")
ok(not plugin_offer_missed(hint, "Рисует плагин «Художник» — он выключен. Включить?", []), "назвала плагин и предложила — честно")
ok(not plugin_offer_missed(hint, "Включаю «Художника».", ["plugin_enable"]), "вызвала plugin_enable — всё как надо")
ok(not plugin_offer_missed("", "Вот открытка символами", []), "без справки о выключенном плагине — не трогаем")
ok("plugin_offer_missed(getattr(turn, \"plugin_hint\", \"\"), step_text, called)" in ea, "проверка стоит в ряду разговора")

print("\nИТОГ: " + ("всё прошло" if not fails else f"не прошло {len(fails)}"))
sys.exit(1 if fails else 0)
