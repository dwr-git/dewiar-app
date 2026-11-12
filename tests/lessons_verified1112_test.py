"""HARNESS 8, п.9 (владелец 12.11: «как у тебя — заметки, что важно»): уроки задач — проверенные правила.
У урока — против какой ошибки он (against из дайджеста). Задачи после него — проверка: ошибка не повторилась
LESSON_OK раз — урок «проверено», идёт в подсказку последним (обрезка его не теряет) с пометкой; повторилась LESSON_WEAK
раз — не помог: из подсказки убран, при следующих выводах модель получает его в «НЕ ПОМОГЛИ» и пишет лучше."""
import json, os, sys, tempfile, time
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


import quality as Q  # noqa: E402

traces = tmp / "traces"
lessons = tmp / "Уроки задач.md"
meta = traces / Q.LESSONS_META
E403 = "read_webpage: HTTP 403 Forbidden для https://site.ru/page/12"
E_ENC = "file_read: 'utf-8' codec can't decode byte 0xcf in position 17"
for i in range(4):
    Q.save_trace(traces, {"id": f"t{i}", "goal": "сравни цены", "ok": i % 2 == 0, "reason": "final",
                          "errors": [{"tool": "read_webpage", "text": E403}, {"tool": "file_read", "text": E_ENC}]})
    time.sleep(0.01)
dig = Q.digest([json.loads(f.read_text()) for f in sorted(traces.glob("*.json"))])
key403 = Q.norm_error(E403)
ok(key403 in dig, f"в дайджесте частая ошибка подписью: {key403}")
seen_msgs = []


def ask(system, msgs):
    seen_msgs.append((system, msgs[0]["content"]))
    return json.dumps({"lessons": [
        {"rule": "При 403 от сайта повтори запрос с заголовком User-Agent браузера", "against": key403},
        {"rule": "Файл не читается как UTF-8 — попробуй cp1251, прежде чем сдаваться", "against": Q.norm_error(E_ENC)},
        "Цены сверяй минимум по двум источникам и указывай дату"]}, ensure_ascii=False)


n = Q.reflect(ask, traces, lessons)
ok(n == 3 and len(Q.read_lessons(lessons)) == 3, f"выводы: три урока, словарь и строка — оба вида ответа: {n}")
ok("against" in seen_msgs[0][0] and "НЕ ПОМОГЛИ" in seen_msgs[0][0], "подсказка выводов просит «against» и знает про «НЕ ПОМОГЛИ»")
m = Q.lessons_meta(meta)
r403, renc, rsrc = Q.read_lessons(lessons)
ok(m[r403]["against"] == key403 and m[rsrc]["against"] == "" and all(m[x]["seen"] == 0 for x in m), f"у уроков — против чего и счётчики: {m}")
blk = Q.lessons_block(lessons, meta)
ok(all(x in blk for x in (r403, renc, rsrc)) and "проверено" not in blk, "новые уроки — в подсказке, без пометки")

time.sleep(1.1)
# следующие задачи: 403 больше нет, а кодировка — опять
for i in range(Q.LESSON_OK):
    ch = Q.lessons_track(meta, {"errors": [{"text": E_ENC}] if i < Q.LESSON_WEAK else []}, lessons)
    if i == Q.LESSON_WEAK - 1:
        ok(ch.get(renc) == "weak", f"кодировка повторилась {Q.LESSON_WEAK} раза — урок «не помог»: {ch}")
    if i == Q.LESSON_OK - 1:
        ok(ch.get(r403) == "ok", f"{Q.LESSON_OK} задач без 403 — урок проверен: {ch}")
m = Q.lessons_meta(meta)
ok(Q.lesson_status(m[rsrc]) == "new" and m[rsrc]["seen"] == Q.LESSON_OK, "урок без «against» не проверяется, но счёт идёт")
blk = Q.lessons_block(lessons, meta)
ok(renc not in blk, "не помогший урок — не в подсказке")
ok(f"{r403} (проверено: {Q.LESSON_OK} задач без этой ошибки)" in blk and blk.rstrip().endswith("без этой ошибки)"),
   "проверенный — последним (обрезка с начала его не потеряет) и с пометкой")
ok("(проверено" not in lessons.read_text(encoding="utf-8"), "пометка — только в подсказке, файл в студии чистый")

# удалённый в студии урок не считается
Q.write_lessons(lessons, [r403, renc])
Q.lessons_track(meta, {"errors": []}, lessons)
ok(Q.lessons_meta(meta)[rsrc]["seen"] == Q.LESSON_OK, "урок удалили в студии — счёт по нему стоит")

# следующие выводы: «не помог» уходит из файла и идёт модели в «НЕ ПОМОГЛИ»
for i in range(3):
    Q.save_trace(traces, {"id": f"u{i}", "goal": "отчёт", "ok": True, "reason": "final", "errors": []})
    time.sleep(0.01)
seen_msgs.clear()


def ask2(system, msgs):
    seen_msgs.append(msgs[0]["content"])
    return json.dumps({"lessons": [{"rule": "Неизвестную кодировку определяй chardet по первым 64 КБ, потом читай",
                                    "against": Q.norm_error(E_ENC)}]}, ensure_ascii=False)


Q.reflect(ask2, traces, lessons)
ok(seen_msgs and "НЕ ПОМОГЛИ" in seen_msgs[0] and renc in seen_msgs[0].split("НЕ ПОМОГЛИ")[1], "модель видит не помогший урок")
now = Q.read_lessons(lessons)
ok(renc not in now and r403 in now and any("chardet" in x for x in now), f"не помогший — заменён новым, проверенный — остался: {now}")
m = Q.lessons_meta(meta)
ok(renc not in m and m[r403]["seen"] >= Q.LESSON_OK and any("chardet" in k and v["seen"] == 0 for k, v in m.items()),
   "проверка: убранный забыт, проверенный хранит счёт, новый — с нуля")

tk = (ROOT / "core/tasks.py").read_text(encoding="utf-8")
ok("Q.lessons_track(" in tk and "Q.LESSONS_META" in tk and "Q.lessons_block(self.lessons_path(), meta)" in tk, "задачи: след каждой — проверка уроков; подсказка — с проверкой")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
