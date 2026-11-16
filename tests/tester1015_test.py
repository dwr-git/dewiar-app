"""Отзывы, отчёты и экзамены 15.10:
— №58: голоса Vosk не скачиваются (плохая сеть до сайта) — повтор не каждые 2 минуты весь день, а через 30 мин и реже,
  и сказать об этом один раз; «Сохранить персонажа», пока слух не поднялся, не падает ('Engine' has no 'vosk_dir');
— №56: «напоминай по будням в 17:30», поставленное в 17:43, звенело сразу — теперь первый раз в следующий будний
  (телефон: set_reminder и addAlarm; компьютер: set_reminder);
— «Мой день» пишет число и день недели («Это офигенно!! А почему он не пишет число и день недели?»);
— экзамены 0.6.40 и 0.38.46: аргументы вызова, пришедшие криво, не становятся молча {} (remember({}) — «Запомнил»,
  а не запомнил); одинаковый вызов несколько раз в одном ответе — один раз; ещё два вида вызова текстом
  («<\\n\\nfunction=f>», {"function": "f"}{…}); «нарисуй схему» — словами → просим нарисовать ```mermaid;
  дата в set_reminder вида «…T08:00:00+03:00» — тоже дата."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import json, os, re, shutil, subprocess, sys, tempfile, threading, time
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ── 1. компьютер: голоса Vosk — повтор с паузой ──
import engine_audio as EA  # noqa: E402


class VT:
    ready, error, speakers, mirror, mirror_sha = False, "", [], "", ""
    def __init__(self): self.tries = 0
    def installed(self): return False
    def ensure(self, on_progress=None, on_status=None):
        self.tries += 1
        raise OSError("timed out")


class FakeEng:
    def __init__(self):
        self.vosk_tts, self._vosk_loading, self.notes = VT(), False, []
        self.s = type("S", (), {"get": lambda self, *k: "vosk" if k == ("tts", "engine") else None})()
        self.updater = type("U", (), {"mirrors": {}})()
    def _mirror(self, k): return None
    def _load(self, *a): pass
    def _loaded(self, *a): pass
    def _dl(self, *a): pass
    def note(self, t): self.notes.append(t)
    def emit(self, *a, **k): pass
    def apply_engines(self): self.ensure_vosk_tts()          # как настоящий: apply_engines → ensure_voice → ensure_vosk_tts


FakeEng.ensure_vosk_tts = EA.AudioMixin.ensure_vosk_tts
e = FakeEng()
e.ensure_vosk_tts()
for _ in range(50):
    time.sleep(0.05)
    if not e._vosk_loading:
        break
time.sleep(0.2)
e.ensure_vosk_tts(); e.ensure_vosk_tts()
ok(e.vosk_tts.tries == 1, f"не скачалось — сразу снова не качаем (раньше — по кругу): попыток {e.vosk_tts.tries}")
ok(e._vosk_retry_at - time.monotonic() > 25 * 60, f"следующая попытка — через ~30 минут: {(e._vosk_retry_at - time.monotonic()) / 60:.0f} мин")
said = [n for n in e.notes if "не загрузились" in n]
ok(len(said) == 1 and "попробую позже" in said[0], f"сказано один раз: {said}")
e._vosk_retry_at = 0; e.ensure_vosk_tts(); time.sleep(0.4)
ok(e.vosk_tts.tries == 2 and e._vosk_retry_at - time.monotonic() > 55 * 60 and len([n for n in e.notes if "не загрузились" in n]) == 1,
   f"второй сбой — пауза больше (час), без нового сообщения: {(e._vosk_retry_at - time.monotonic()) / 60:.0f} мин")

# ── 2. «Сохранить персонажа», пока слух не готов ──
import engine_commands as EC  # noqa: E402
ok("self.vosk_dir = None" in (ROOT / "core/engine.py").read_text(encoding="utf-8"), "vosk_dir есть с самого начала (None, пока слух не готов)")


class FakeP:
    def save(self, p): return "nova"
    def get(self, pid): return {"id": pid, "wake": ["Нова"]}
    def public(self): return []


f = type("F", (), {"personas": FakeP(), "vosk_dir": None, "build_spotter": lambda self: None, "emit": lambda self, *a, **k: None})()
try:
    r = EC.CommandsMixin.command(f, "persona_save", {"persona": {"name": "Нова"}})
    ok(r == {"id": "nova", "missing": []}, f"персонаж сохраняется и без модели слуха: {r}")
except Exception as x:  # noqa: BLE001
    ok(False, f"persona_save без модели слуха упал: {x!r}")

# ── 3. компьютер: повторяющееся на прошедшее время ──
import tools as T  # noqa: E402


class R:
    def __init__(self): self.added = []
    def add(self, when, text, rep, kind): self.added.append(when); return {"id": "1", "text": text}


rr = R()
past = datetime.now() - timedelta(minutes=13)
msg = T.t_reminder({"text": "Тренировка", "at": past.strftime("%Y-%m-%d %H:%M"), "repeat": "weekdays"}, {"reminders": rr})
w = rr.added[-1]
# в выходной «по будням» и так начинается с понедельника — «уже прошло» там не о чем говорить (17.10, суббота)
ok(w > datetime.now() and w.weekday() < 5 and (w.hour, w.minute) == (past.hour, past.minute)
   and ("уже прошло" in msg or datetime.now().weekday() >= 5),
   f"«по будням в {past:%H:%M}», сказанное в {datetime.now():%H:%M}, — не сразу, а {w:%a %d.%m %H:%M}: {msg[:90]}")
T.t_reminder({"text": "Вода", "at": past.strftime("%Y-%m-%d %H:%M"), "repeat": "daily"}, {"reminders": rr})
ok(rr.added[-1].date() == (past + timedelta(days=1)).date(), f"каждый день — с завтрашнего: {rr.added[-1]}")
fut = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
for at in (f"{fut:%Y-%m-%d} 08:00:00", f"{fut:%Y-%m-%d}T08:00:00", f"{fut:%Y-%m-%d} 08:00"):
    T.t_reminder({"text": "Зонт", "at": at}, {"reminders": rr})
    ok(rr.added[-1] == fut, f"дата «{at}» понята: {rr.added[-1]}")

# ── 4. вызовы текстом и «нарисуй схему» ──
import llm  # noqa: E402
import quality as Q  # noqa: E402
ok(llm.parse_tool_call("\n<\n\nfunction=code_list>\n</function>\n") == {"name": "code_list", "args": {}}, "«<\\n\\nfunction=code_list>» разобран")
ok(llm.parse_tool_call("<\nfunction=code_read>\n<path>tests/test_stats.py</path>\n</function>") == {"name": "code_read", "args": {"path": "tests/test_stats.py"}},
   "<path>…</path> внутри <function=…> — аргумент")
ok(llm.parse_tool_call('{"function": "show_images"}\n{"query": "knotwork", "count": 3}\n</function>') == {"name": "show_images", "args": {"query": "knotwork", "count": 3}},
   "{\"function\": f} и аргументы следующим объектом — разобран")
ASK = "Нарисуй схему: как заявка проходит от клиента через менеджера на склад и обратно клиенту."
ok(Q.diagram_missing(ASK, "Клиент → менеджер → склад → клиент.") and "```mermaid" in Q.diagram_missing(ASK, ""), "схема словами — просим нарисовать mermaid")
ok(not Q.diagram_missing(ASK, "Вот:\n```mermaid\nflowchart LR\n```") and not Q.diagram_missing("Нарисуй кота", "Мяу"),
   "нарисовал — тихо; «нарисуй кота» — не схема")
src = srctext.text(ROOT, "core/engine_answer.py")
ok("diagram_missing(text, turn.full + step_text, called)" in src, "разговор на компьютере сверяет ответ со схемой")

# ── 5. телефон ──
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs, seen = [], []
WD = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def sse(delta):
    return "".join(f"data: {json.dumps({'choices': [{'delta': d}]}, ensure_ascii=False)}\n\n" for d in delta) + "data: [DONE]\n\n"


def llm_route(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    if not req.url.endswith("/chat/completions"):
        return route.fulfill(status=200, body='{"data":[{"id":"m"}]}', headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})
    body = json.loads(req.post_data or "{}"); msgs = body.get("messages") or []
    for m in msgs:                                    # справка к вопросу (putContext) — модель отвечает на сам вопрос после неё
        if m.get("role") == "user" and isinstance(m.get("content"), str) and "(Сообщение пользователя)\n" in m["content"]:
            m["content"] = m["content"].split("(Сообщение пользователя)\n", 1)[1]
    seen.append(msgs)
    last = msgs[-1] if msgs else {}
    users = [m.get("content") for m in msgs if m.get("role") == "user" and isinstance(m.get("content"), str)]
    if "бюджет" in (users[-1] if users else "") and last.get("role") == "user":
        calls = [{"index": i, "id": f"c{i}", "type": "function", "function": {"name": "remember", "arguments": a}}
                 for i, a in enumerate(['{"fact": "Бюджет на мебель — 65 тысяч"}', '{"fact": "Бюджет на мебель — 65 тысяч"}',
                                        '{"fact": "Бюджет на мебель — 65 тысяч"}'])]
        d = [{"tool_calls": calls}]
    elif last.get("role") == "tool":
        d = [{"content": "Запомнила: 65 тысяч."}]
    elif str(last.get("content", "")).startswith("ПРОВЕРКА: тебя попросили нарисовать схему"):
        d = [{"content": "Вот схема.\n```mermaid\nflowchart LR\n  A[\"Клиент\"] --> B[\"Менеджер\"] --> C[\"Склад\"] --> A\n```"}]
    else:
        d = [{"content": "Клиент отдаёт заявку менеджеру, менеджер — на склад, склад отправляет клиенту."}]
    route.fulfill(status=200, body=sse(d), headers={"Access-Control-Allow-Origin": "*", "Content-Type": "text/event-stream"})


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route("http://127.0.0.1:9/**", llm_route)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { Object.assign(S.llm, { kind: 'openai', base_url: 'http://127.0.0.1:9/v1', model: 'm', name: 'тест', cloud: false }); saveS(); }")
    # «Мой день»: дата и день недели
    pg.evaluate("() => openDay ? openDay() : null") if pg.evaluate("() => typeof openDay === 'function'") else pg.evaluate("() => { document.getElementById('sh-day').classList.add('on'); renderDay(); }")
    pg.wait_for_timeout(500)
    dd = pg.evaluate("() => document.getElementById('day-date').textContent")
    now = datetime.now()
    ok(re.fullmatch(r"[А-Я][а-я]+, \d{1,2} [а-я]+", dd or "") and dd.lower().startswith(WD[now.weekday()]) and f" {now.day} " in dd,
       f"«Мой день» — {dd!r}")
    head = pg.evaluate("() => { const h = document.querySelector('#sh-day h2'); const c = getComputedStyle(h.querySelector('.hdate')); return [h.textContent, c.marginLeft !== '0px' && c.backgroundColor === 'rgba(0, 0, 0, 0)'] }")
    ok(head[0].startswith("Мой день") and head[1], f"в заголовке: «Мой день» и справа дата, простым текстом (не плашкой): {head}")
    # повторяющееся на прошедшее время
    R1 = pg.evaluate("""async () => { const p = new Date(Date.now() - 13 * 60e3);
        const r = await runTool('set_reminder', { text: 'Тренировка', at: isoLocal(p), repeat: 'weekdays' });
        const x = JSON.parse(D.alarms()).find(a => a.title === 'Тренировка'), d = new Date(x.at);
        return { r, future: x.at > Date.now(), wd: d.getDay(), hm: [d.getHours(), d.getMinutes()], want: [p.getHours(), p.getMinutes()] }; }""")
    ok(R1["future"] and R1["wd"] not in (0, 6) and R1["hm"] == R1["want"] and "уже прошло" in R1["r"],
       f"телефон: «по будням» на прошедшее — следующий будний в то же время, и модель скажет об этом: {R1}")
    R2 = pg.evaluate("""() => { const p = new Date(Date.now() - 20 * 60e3); const x = addAlarm('Будильник', p, 'alarm', 'daily'), d = new Date(x.at);
        return [x.at > Date.now(), d.getDate() === new Date(p.getTime() + 864e5).getDate(), d.getHours() === p.getHours()]; }""")
    ok(R2 == [True, True, True], f"«будильник каждый день» на прошедшее (быстрая команда) — с завтрашнего: {R2}")
    R3 = pg.evaluate("""() => { const sat = new Date(); sat.setDate(sat.getDate() + ((6 - sat.getDay() + 7) % 7 || 7)); sat.setHours(9, 0, 0, 0);
        return rollRepeat(sat, 'weekdays').getDay(); }""")
    ok(R3 == 1, f"«по будням», а дата — суббота: первый раз в понедельник ({R3})")
    # аргументы
    J = pg.evaluate("""() => [safeJSON('{"fact":"a"}{"fact":"a"}'), safeJSON(JSON.stringify(JSON.stringify({ fact: 'b' }))), safeJSON('{"fact": "оборва'),
        safeJSON('{"a": {"b": 1}}'), safeJSON('мусор')]""")
    ok(J == [{"fact": "a"}, {"fact": "b"}, {"fact": "оборва"}, {"a": {"b": 1}}, {}], f"кривые аргументы — спасены: {J}")
    rm = pg.evaluate("async () => [await runTool('remember', {}), await runTool('remember', { text: 'Кошку зовут Муся' }), S.memory.includes('Кошку зовут Муся')]")
    ok(rm[0].startswith("Ошибка") and rm[1] == "Запомнил." and rm[2], f"remember без факта — ошибка, а не «Запомнил»; факт под другим именем — принят: {rm}")
    P = pg.evaluate("""() => [parseToolCall('<\\n\\nfunction=code_list>\\n</function>'), parseToolCall('{"function": "show_images"}\\n{"query": "руны", "count": 3}\\n</function>'),
        parseToolCall('<function=read_page><url>https://a.ru</url></function>')]""")
    ok(P == [{"name": "code_list", "args": {}}, {"name": "show_images", "args": {"query": "руны", "count": 3}}, {"name": "read_page", "args": {"url": "https://a.ru"}}],
       f"вызовы текстом — разобраны: {P}")

    def say(t):
        pg.evaluate("t => { window._done = false; ask(t).then(() => window._done = true, e => { window._done = true; window._err = String(e); }); }", t)
        for _ in range(150):
            pg.wait_for_timeout(100)
            if pg.evaluate("window._done && state === 'idle'"):
                break
        return pg.evaluate("() => document.getElementById('bot').innerHTML")

    # одинаковый вызов трижды в одном ответе — один раз
    mem0 = pg.evaluate("() => S.memory.length")
    say("Ладно, бюджет на мебель — 65 тысяч, запомни.")
    tools_msgs = [m for m in seen[-1] if m.get("role") == "tool"]
    ok(pg.evaluate("() => S.memory.filter(x => x.includes('65 тысяч')).length") == 1 and pg.evaluate("() => S.memory.length") == mem0 + 1,
       "запомнено один раз")
    ok(pg.evaluate("() => PLOG.some(l => l.includes('🔧 remember → Запомнил.'))"),
       "в журнале телефона — какие действия сделаны (№56: по отчёту не понять, ставилось ли напоминание)")
    ok(len(tools_msgs) == 3 and sum("уже сделано" in m["content"] for m in tools_msgs) == 2, f"на повторы модели сказано «уже сделано»: {[m['content'][:30] for m in tools_msgs]}")
    # «нарисуй схему» — словами → ещё раз, со схемой
    n0 = len(seen)
    html = say(ASK)
    ok(len(seen) - n0 == 2 and str(seen[-1][-1].get("content", "")).startswith("ПРОВЕРКА"), f"ответ словами — попросили нарисовать: {len(seen) - n0} запроса")
    ok("Вот схема" in html, "в ответе — схема")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
