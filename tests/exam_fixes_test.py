"""Исправления по первому экзамену (0.36.4), на настоящем ядре в режиме сервера с моделью-заглушкой:
«запомни: в среду в 15:00 встреча» — в память с точной датой и в календарь; «сколько раз я менял бюджет» и «если
дождь — напомни…» — модели, а не быстрым ответом; счёт — сразу и точно; калькулятор calc у модели; «сделай потише» на
сервере — честно и с уточнением; экранных инструментов на сервере нет; числа словами — понятные озвучке."""
import asyncio, datetime as dt, json, os, re, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import exam as X  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


SEEN = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = b'{"data": [{"id": "m"}]}'
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        last = body["messages"][-1].get("content")
        sysm = body["messages"][0].get("content") if body["messages"][0].get("role") == "system" else ""
        names = [t["function"]["name"] for t in body.get("tools") or []]
        if not names and isinstance(sysm, str):           # модель без функций полем — инструменты описаны в подсказке
            names = re.findall(r'"name":\s*"(\w+)"', sysm) or re.findall(r"^[-*•]?\s*(\w+)\s*[(:—-]", sysm, re.M)
        SEEN.append({"last": last if isinstance(last, str) else "", "tools": names, "all": json.dumps(body["messages"], ensure_ascii=False)})
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"\\u041c\\u043e\\u0434\\u0435\\u043b\\u044c."}}]}\n\ndata: [DONE]\n\n')


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
prof = {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1", "model": "m"}


async def main():
    core = X.Core(prof, Path(tempfile.mkdtemp()) / "core", log=lambda s: None)
    core.start()
    await core.connect()
    try:
        a, _ = await core.say("Запомни, пожалуйста: в среду в 15:00 у меня встреча с подрядчиком по кухне.")
        today = dt.date.today()
        wed = today + dt.timedelta(days=(2 - today.weekday()) % 7)
        rel = {0: "сегодня", 1: "завтра", 2: "послезавтра"}.get((wed - today).days)
        named = (rel and rel in a.lower()) or ("сред" in a and str(wed.day) in a)   # в саму среду — «сегодня», в понедельник — «послезавтра»
        ok("Запомнил" in a and named, f"запомнил и назвал день: {a}")
        mem = (core.tmp / "ws" / "Память" / "Обо мне.md").read_text(encoding="utf-8")
        ok(f"(на {wed:%d.%m.%Y}, среда)" in mem and "Пожалуйста" not in mem, f"в памяти — с точной датой: {mem.strip().splitlines()[-1]}")
        cal = await core.call("calendar_month", year=wed.year, month=wed.month)
        items = (cal.get("data") or cal).get("days", {}).get(wed.isoformat(), [])
        ok(any(i.get("cal") == "Память" and i.get("time") == "15:00" and "подрядчик" in i.get("title", "") for i in items),
           f"в календаре на среду — встреча из памяти: {items}")
        n = len(SEEN)
        a, _ = await core.say("Сколько будет 17 процентов от 2350?")
        ok("399,5" in a and len(SEEN) == n, f"счёт — сразу и точно, без модели: {a}")
        a, _ = await core.say("Сколько дней осталось до Нового года?")
        days = (dt.date(today.year + 1, 1, 1) - today).days
        ok(str(days) in a and len(SEEN) == n, f"дни до Нового года — без модели: {a}")
        a, _ = await core.say("Сколько раз я менял бюджет на мебель и на какой цифре остановился?")
        ok(len(SEEN) > n and "записей о деньгах нет" not in a, "«сколько раз менял бюджет» — модели (она помнит разговор)")
        ok(any("Сколько раз я менял" in x["last"] and "Расчёт: 2 350 × 17 / 100 = 399,5" in x["all"] for x in SEEN), "быстрый счёт — в разговоре с расчётом: на «как посчитал?» модель покажет числа")
        n = len(SEEN)
        await core.say("Если завтра в Минске будет дождь — напомни мне утром взять зонт, если нет — напомни полить рассаду.")
        ok(len(SEEN) > n, "условное напоминание — модели (сначала узнать прогноз)")
        # заглушка не вызывает функций — фоновая проверка решит, что модель их не умеет; смотрим запрос до этого
        tools = next((x["tools"] for x in SEEN if len(x["tools"]) > 10), [])
        ok("calc" in tools and "web_search" in tools, f"у модели есть калькулятор: {[(x['last'][:30], len(x['tools'])) for x in SEEN]}")
        # экзамен ПК 0.81.1: open_url и open_app на экзамене есть — запуск там записывается (EXAM_LAUNCH), звука и экрана — нет
        ok(not {"play_music", "set_volume", "look_at_screen", "media_control"} & set(tools) and {"open_url", "open_app"} <= set(tools),
           f"на сервере экзамена нет звука и экрана, а открыть сайт — понарошку можно: {sorted(set(tools) & {'open_url', 'play_music', 'set_volume'})}")
        n = len(SEEN)
        a, _ = await core.say("Сделай потише.")
        ok("нет звука" in a and "pulsectl" not in a and "?" in a, f"«потише» на сервере — честно и с уточнением: {a}")
    finally:
        await core.stop()


asyncio.run(main())
import speechnorm as S  # noqa: E402
sn = S.speech_norm("Итого 1 437,50 руб., это 17% от 2 350 — 399,5.")
ok("тысяча четыреста тридцать семь рублей пятьдесят копеек" in sn and "две тысячи триста пятьдесят" in sn
   and "триста девяносто девять и пять десятых" in sn, f"озвучка: суммы, разряды и дроби: {sn}")
import tools as T  # noqa: E402
ok(T.calc_eval('days_until("2027-01-01")', dt.date(2026, 10, 10)) == 83 and T.calc_eval("2350 * 17%") == 399.5, "калькулятор: проценты и даты")
class _M:
    added = []

    def add(self, *a):
        self.added.append(a)
        return {"kind": a[0], "amount": a[1], "currency": "RUB", "category": a[3], "date": "2026-10-10"}


mm = _M()
r1 = T.t_money_add({"kind": "income", "amount": 50000, "category": "Бюджет", "note": "Бюджет на мебель для гостиной"}, {"money": mm})
r2 = T.t_money_add({"kind": "expense", "amount": 70000, "category": "Мебель", "note": "Бюджет на мебель (увеличен с 50 000)"}, {"money": mm})
r3 = T.t_money_add({"kind": "expense", "amount": 20000, "category": "Мебель", "note": "диван из бюджета на мебель"}, {"money": mm})
ok(r1.startswith("Не записано") and r2.startswith("Не записано") and r3.startswith("Записано") and len(mm.added) == 1,
   "бюджет и «заложим 70 тысяч» — не расход и не доход; покупка из бюджета — расход")
ok(T.human_error(ModuleNotFoundError("No module named 'pulsectl'")).startswith("на этом устройстве"), "техническая ошибка — понятными словами")
ok(X.check_answer({"regex": r"\d{2}\s*(?:руб|₽)"}, "Курс — восемьдесят четыре рубля девяносто копеек")[0]["ok"],
   "экзамен: число словами засчитывается")
import quality as Q  # noqa: E402
ok(not Q.looks_like_refusal("Я не умею звонить: у меня нет доступа к твоей телефонной книге и SIM-карте.")
   and Q.looks_like_refusal("У меня нет доступа к интернету, погоду не узнаю."), "«нет доступа к телефонной книге» — не отговорка про интернет")
os.environ["DEWIAR_WORKSPACE"] = tempfile.mkdtemp()
import workspace as W  # noqa: E402
ws = W.Workspace(None)
ws.ensure()
for f in ("Бюджет на мебель для гостиной — 50 тысяч рублей.", "Бюджет на мебель для гостиной — 70 тысяч рублей.",
          "Бюджет на мебель для гостиной — 65 тысяч рублей.", "Со слов пользователя: в среду в 15:00 у меня встреча (на 14.10.2026, среда).",
          "Со слов пользователя: в среду в 18:00 у меня стоматолог (на 14.10.2026, среда)."):
    r = ws.remember(f)
mem = ws.memory_get()
ok(mem.count("Бюджет на мебель") == 1 and "65 тысяч рублей (раньше: 50 тысяч рублей → 70 тысяч рублей; менялось 2 раза)" in mem,
   "память: новое значение заменяет старое и хранит историю")
ok("встреча" in mem and "стоматолог" in mem, "планы на один день не затирают друг друга")
# «вспомни, что я говорил про работу» (экзамен 11.10): в памяти — другими словами, поиск по заметкам видит память
ws.remember("Три задачи на этой неделе: отчёт по продажам в пятницу, найти дизайнера, обновить сайт")
ws.remember("Начальник просил подготовить презентацию для инвесторов")
import tools as TT  # noqa: E402
r = TT.t_find_notes({"query": "работа"}, {"workspace": ws})
ok("отчёт по продажам" in r and "презентацию для инвесторов" in r and "Обо мне" in r, f"поиск «работа» показывает запомненное о работе: {r[-300:]}")
ok("отвечай отсюда" in (ROOT / "core/engine_answer.py").read_text(encoding="utf-8"), "подсказка: «вспомни…» — из памяти")
import privacy as PV  # noqa: E402
ok("на этом компьютере" in PV.rule("https://dewiar.pro/dwrapp/cloud.php?p="), "«где мои данные» — обязательно: у вас на компьютере")
import recall as RC  # noqa: E402
ok(RC.stem("день") == RC.stem("дни") == RC.stem("дней") and RC.stem("мама") == RC.stem("матери"),
   "поиск по записям: «день рождения» находит «дни рождения»")
ok(X.fill("у Пети — {date+9}", dt.date(2026, 10, 10)) == "у Пети — 19 октября" and X._num("days:9") == 9,
   "экзамен: даты в сценарии — от сегодняшнего дня")
import re, shutil, subprocess  # noqa: E402
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok('name: "calc"' in app and 'case "calc":' in app and "только инструментом calc" in app, "телефон: калькулятор и правило счёта")
if shutil.which("node"):
    fn = re.search(r"function calcEval\(src\) \{[\s\S]*?\n\}\n", app).group(0)
    js = fn + 'const r = [calcEval("2350 * 17 / 100"), calcEval("(1 437,50 - 520)"), calcEval(\'weekday("2026-10-14")\')];' \
        + 'let bad = ""; try { calcEval("alert(1)"); } catch (e) { bad = "ok"; } console.log(JSON.stringify(r.concat([bad])));'
    out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True).stdout)
    ok(out == [399.5, 917.5, "среда", "ok"], f"телефон: калькулятор считает и не выполняет чужое: {out}")
# экзамен 0.38.13: напоминание «на 17:00», когда уже 17:26, — на завтра, а не в прошлое; заметка без просьбы — не пишется;
# облако Dewiar по внутреннему адресу сервера — «в облаке», а не «на твоём компьютере»
import tools as T, privacy as PV, engine_tools as ET  # noqa: E402
class _R:
    def __init__(self): self.items = []
    def add(self, when, text, rep, kind): self.items.append((when, text)); return {"id": "x1", "text": text}
rr = _R()
past = (dt.datetime.now() - dt.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")
out = T.t_reminder({"text": "Позвонить Ольге", "at": past}, {"reminders": rr})
w = rr.items[-1][0]
ok(w > dt.datetime.now() and w.strftime("%H:%M") == past[-5:] and "на завтра" in out, f"время уже прошло — на завтра в то же время: {w} · {out[-80:]}")
ok(not ET.NOTE_ASK_RX.search("Напиши четверостишие про осень с настоящей рифмой") and not ET.NOTE_ASK_RX.search("Составь список из пяти идей подарка")
   and ET.NOTE_ASK_RX.search("Сохрани в заметки список покупок") and ET.NOTE_ASK_RX.search("запиши это"), "заметка — только когда просили записать")
ok("облаке Dewiar" in PV.where_model("http://127.0.0.1/dwrapp/cloud.php?p=") and "компьютере" in PV.where_model("http://127.0.0.1:11434/v1"),
   "где думает модель: облако Dewiar и по внутреннему адресу")
srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
print("ALL OK" if not fails else "")
sys.exit(1 if fails else 0)
