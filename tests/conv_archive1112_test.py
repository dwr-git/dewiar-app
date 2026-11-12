"""Владелец 12.11: «как я с тобой в одной беседе два месяца — ответы не деградируют, ты хранишь в памяти, делаешь
записи и пометки и не забываешь… вот бы такое в Лиру». Разговор Лиры: последние реплики — дословно, раньше — содержание
(conversation.py). Теперь: 1) содержание при свёртке не теряет чисел, ссылок, кодов прежнего (quality.keep_facts — как
блокнот задачи); 2) кончился разговор (долгая тишина, «новый разговор», кончился, пока программа выключена) — его
содержание и последние реплики ложатся в «Память/Разговоры» (поиск по записям находит их: «о чём говорили во вторник?»),
а не стираются."""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import conversation as C  # noqa: E402

tmp = Path(tempfile.mkdtemp())
cv = C.Conversation(tmp / "conversation.json")
got = []
cv.archive_to = lambda name, text: got.append((name, text))
cv.summary = "- Пользователь бронирует отель, номер брони 77-1234\n- Бюджет 300 евро\n- Любит тишину"
hist = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"реплика {i}"} for i in range(10)]
cv.started = time.time() - 3600
ok(cv.archive(hist) and got and "77-1234" in got[0][1] and "## Последние реплики" in got[0][1] and "реплика 9" in got[0][1],
   "законченный разговор — содержание и последние реплики в архив")
got.clear()
cv2 = C.Conversation(tmp / "c2.json")
cv2.archive_to = lambda name, text: got.append((name, text))
ok(not cv2.archive(hist[:4]) and not got, "короткий разговор без содержания — не архивируем")
# свёртка не теряет чисел прежнего содержания
cv3 = C.Conversation(tmp / "c3.json")
cv3.summary = "- Номер брони 77-1234\n- Бюджет 300 евро"
h3 = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"реплика {i}"} for i in range(40)]
n = cv3.fold(lambda: h3, 8, lambda sysm, msgs: "- Пользователь выбирает отель у моря\n- Бюджет 300 евро")
ok(n and "77-1234" in cv3.summary and "Из прежнего содержания" in cv3.summary, f"свёртка: потерянный номер брони вернулся: {cv3.summary!r}")
# кончился, пока программа была выключена — в архив, когда папка готова
p4 = tmp / "c4.json"
p4.write_text(json.dumps({"summary": "- Договорились созвониться в 15:00", "turns": 9, "started": time.time() - 99999,
                          "last": time.time() - 90000, "history": hist}, ensure_ascii=False), encoding="utf-8")
cv4 = C.Conversation(p4)
got.clear()
cv4.archive_to = lambda name, text: got.append((name, text))
ok(cv4.restored(28800) == [] and not got, "после долгой тишины история не продолжается")
ok(cv4.archive_pending() and got and "15:00" in got[0][1], "прошлый разговор ушёл в архив, когда программа была готова")
ok(cv4.summary == "" and not cv4.archive_pending(), "состояние нового разговора чистое; повторно не пишем")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("self.conv.archive(self.history)" in ea and '"Память" / "Разговоры"' in ea, "долгая тишина и «новый разговор» — в «Память/Разговоры»")
ok("archive_pending" in (ROOT / "core/engine.py").read_text(encoding="utf-8"), "при запуске — то, что кончилось, пока программа была выключена")
rc = (ROOT / "core/recall.py").read_text(encoding="utf-8")
ok('("Память", "память")' in rc, "поиск по записям смотрит в «Память» — найдёт и разговоры")
if fails:
    sys.exit(1)
print("\n✅ всё в порядке")
