"""Учиться на ошибках в разговоре: человек поправил ассистента («нет, я же просил коротко») — модель выводит общее правило,
оно ложится в «Память/Уроки.md» и идёт в подсказку разговоров и задач. Не поправка — ничего не пишется; то же правило не
дублируется; файл правится руками — правки учитываются. Распознавание кандидатов — без модели."""
import srctext  # noqa: E402 — текст модуля с частями (чистое ядро)
import os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import quality as Q  # noqa: E402

YES = ["Нет, я же просил коротко.", "Опять не то, я просил погоду на завтра", "Ты снова ошибся с датой", "Неправильно, это не так",
       "В следующий раз сначала спрашивай", "Не делай так больше", "Сколько раз говорить — без смайликов!", "зачем ты открыл ютуб?"]
NO = ["Привет! Как дела?", "Включи музыку", "Нет, спасибо", "Какая погода завтра?", "Да, всё правильно", "Нет", "Спасибо, всё нормально."]
bad = [t for t in YES if not Q.looks_like_correction(t)] + [t for t in NO if Q.looks_like_correction(t)]
ok(not bad, f"поправки узнаются, обычные фразы — нет: {bad}")

tmp = Path(tempfile.mkdtemp())
path = tmp / "Память/Уроки.md"
asked = []


def model(answer):
    def ask(q):
        asked.append(q)
        return answer
    return ask


r = Q.learn_from_correction(model("Отвечай короче — одной-двумя фразами, если не просят подробно."), "Длинный ответ…",
                            "Нет, я же просил коротко.", path)
ok(r.startswith("Отвечай короче") and "Длинный ответ" in asked[-1] and "я же просил" in asked[-1], f"правило из поправки: {r}")
ok(path.exists() and "# Уроки" in path.read_text() and "- Отвечай короче" in path.read_text(), "записано в «Память/Уроки.md»")
r2 = Q.learn_from_correction(model("«отвечай короче — одной-двумя фразами, если не просят подробно»"), "…", "опять длинно", path)
ok(r2 == "" and Q.read_lessons(path).count("Отвечай короче — одной-двумя фразами, если не просят подробно.") == 1, "то же правило не дублируется")
r3 = Q.learn_from_correction(model("НЕТ"), "Сейчас 15 градусов.", "Нет, я спрашивал про завтра", path)
ok(r3 == "" and len(Q.read_lessons(path)) == 1, "модель сказала «не поправка» — ничего не пишется")
r4 = Q.learn_from_correction(model("Правило: Не открывай YouTube без просьбы — музыку включай в Яндекс Музыке."), "Открыл YouTube.", "зачем ты открыл ютуб?", path)
ok(r4.startswith("Не открывай YouTube") and len(Q.read_lessons(path)) == 2, f"«Правило:» в начале снимается: {r4}")
path.write_text(path.read_text().replace("- Не открывай YouTube без просьбы — музыку включай в Яндекс Музыке.\n", "- Музыку — только в Яндекс Музыке.\n"))
blk = Q.talk_lessons_block(path)
ok("ЧЕМУ ТЫ НАУЧИЛСЯ" in blk and "Музыку — только в Яндекс Музыке." in blk and "YouTube" not in blk, "правка файла руками — в подсказке новое")

# в подсказке разговора и задачи
import engine as E  # noqa: E402
eng = E.Engine.__new__(E.Engine)
ws = types.SimpleNamespace(root=tmp, memory_text=lambda: "")
eng.workspace = ws
calls = []
eng.history = [{"role": "user", "content": "Расскажи про Марс"}, {"role": "assistant", "content": "Марс — четвёртая планета… (много текста)"},
               {"role": "user", "content": "Нет, я же просил коротко."}]
eng.emit = lambda *a, **k: calls.append((a, k))
import llm  # noqa: E402
llm.stream_chat = lambda prof, system, msgs, **k: iter(["Отвечай коротко про планеты — две фразы."])
import threading  # noqa: E402
before = set(threading.enumerate())
E.Engine._maybe_learn(eng, "Нет, я же просил коротко.", {"name": "x"})
for t in set(threading.enumerate()) - before:
    t.join(5)
ok(any(a and a[0] == "lesson" for a, k in calls) and "Отвечай коротко про планеты — две фразы." in Q.read_lessons(path),
   f"ядро: поправка после ответа — урок в фоне: {Q.read_lessons(path)[-1:]}")
E.Engine._maybe_learn(eng, "Какая погода?", {"name": "x"})
ok(len(Q.read_lessons(path)) == 3, "обычный вопрос — модель не спрашиваем")
src = srctext.text(ROOT, "core/tasks.py")
ok("talk_lessons_block" in src, "задачи тоже получают уроки из поправок")
print("ALL OK" if not fails else f"ошибок: {len(fails)}")
sys.exit(1 if fails else 0)
