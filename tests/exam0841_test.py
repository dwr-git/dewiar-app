"""Экзамен 0.84.1 (05.11, 94 из 107) — что провалилось и почему, каждое — проверкой:
- «И ещё 1250 на кафе» — ответ «Записал: 1 250 руб.» без записи: продолжение после записи — запись без модели; ответ «записала /
  меняю» без действия — переспрос (и «давай заложим 70 тысяч» — «Хорошо, меняю» без remember);
- «Расскажи утро»: в данных «23:58 Позвонить маме», а ответ «дел нет» — переспрос; навык morning-brief не велит искать погоду
  поиском, когда данные «Утра» уже даны;
- «штук пять песен» — три песни: переспрос;
- «расскажи о себе» дважды — длинный ответ слово в слово: ловим, когда и вопрос повторён;
- большие задачи: проверяющий принимал обрезанную выдержку за обрыв файла, «код 0» команды критерия — за «0 слайдов», а файлы
  задачи по коду искал среди готовых файлов (там _undo/…, код.json);
- синтез речи у исполнителя на сервере: нет tts_remote — не падаем."""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import money as M  # noqa: E402
import quality as Q  # noqa: E402
last = {"kind": "expense", "currency": "BYN", "category": "Кафе и рестораны"}
r = M.parse_more("И ещё 1250 на кафе.", last, "BYN")
ok(r and r["amount"] == 1250 and r["category"] == "Кафе и рестораны" and r["kind"] == "expense", f"«И ещё 1250 на кафе» после записи — расход: {r}")
ok((M.parse_more("и ещё 500 на такси", last) or {}).get("category") == "Транспорт", "«и ещё 500 на такси» — своя категория")
ok(M.parse_more("ещё 5 минут", last) is None and M.parse_more("И ещё раз", last) is None and M.parse_more("ещё 3 песни", last) is None,
   "«ещё 5 минут», «ещё раз», «ещё 3 песни» — не деньги")
ok(M.parse_more("И ещё 1250 на кафе.", None) is None, "без недавней записи — не перехватываем")
et = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("parse_more(text, last" in et and "time.time() - last[\"ts\"] < 15 * 60" in et and "self._money_last = {" in et,
   "ядро: продолжение — только 15 минут после записи")

ok(Q.saved_claim("Хотя нет, давай заложим 70 тысяч, хочу диван получше.", "Хорошо, меняю: заложим 70 тысяч — диван того стоит.", ()),
   "«давай заложим 70 тысяч» — «Хорошо, меняю» без remember: переспрос (общая проверка «сказала, но не сделала»)")
ok(Q.saved_claim("И ещё 1250 на кафе.", "Записал: 1 250 руб. — кафе и рестораны.", ()), "«Записал: 1 250 руб.» без действия — переспрос")
ok(not Q.saved_claim("Ладно, остановимся на 65 тысячах.", "Хорошо, меняю.", ("remember",)), "с действием — не переспрос")
ask = "[Утро] Сегодня 05.11.2026, четверг.\nДела и напоминания на сегодня: 23:58 Позвонить маме.\nДеньги: …"
ok(Q.agenda_missed(ask, "На сегодня в справке нет записанных дел и встреч.") and "Позвонить маме" in Q.agenda_missed(ask, "Дел нет."),
   "«Расскажи утро»: в данных дело, а ответ «дел нет» — переспрос с делом")
ok(not Q.agenda_missed("Дела и напоминания на сегодня: нет.\n", "Дел на сегодня нет.") and not Q.agenda_missed(ask, "В 23:58 — позвонить маме."),
   "дел правда нет или дело названо — не переспрос")
sk = (ROOT / "data/skills/morning-brief/SKILL.md").read_text(encoding="utf-8")
ok("данные «Утра с Лирой»" in sk and "только инструментом weather" in sk and "web_search с запросом «погода сегодня»" not in sk,
   "навык morning-brief: есть данные «Утра» — только по ним; погода — weather, не поиском и не по памяти")

songs = "Три проверенных:\n\n1. **«Ветер» — Сплин**. Тёплая\n2. **«Здесь» — Дельфин**. Спокойная\n3. **«Тёплый ветер» — Земфира**."
ok(Q.songs_count("Подбери мне плейлист под настроение, штук пять песен.", songs), "просили пять песен — дали три: переспрос")
ok(not Q.songs_count("посоветуй 3 песни", songs) and not Q.songs_count("что послушать?", songs), "три из трёх или без числа — не переспрос")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("РОВНО сколько просили" in ea and "не сокращай список" in ea, "правило о песнях: ровно сколько просили")
for name in ("songs_count(ask0", "agenda_missed(text"):
    ok(name in ea, f"проверка {name.split('(')[0]} — в цепочке проверок ответа")
ok("_norm_answer(ask0) in prev_asked" in ea and "prev_asked = {" in ea, "длинный повтор слово в слово ловим, когда и вопрос повторён")

tk = (ROOT / "core/tasks.py").read_text(encoding="utf-8")
ok('"прошла (код выхода 0)" + (f", вывод: {tail}"' in tk, "команда критерия: «прошла (код выхода 0), вывод: 5», а не голое «код 0»")
ok("выдержка обрезана: показано" in tk and "это не обрыв" in tk, "обрезанная выдержка помечена — не «обрыв файла»")
ok("Изменено в рабочей копии:" in tk, "задача по коду: изменённые файлы рабочей копии — в списке для проверяющего")
ok({"_undo", "код.json", "_snap"} <= set(Q.SERVICE), "служебные _undo, код.json, _snap — не «готовые файлы»")
ok("по выдержкам их не оспаривай" in Q.VERIFY and "чего в выдержке не видно — не ошибка" in Q.VERIFY, "проверяющему: ✓ и факты — истина; невидимое в выдержке — не повод")
er = (ROOT / "core/engine_remote.py").read_text(encoding="utf-8")
ok('remote = getattr(self, "tts_remote", None)' in er, "синтез речи без tts_remote — не падает")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
