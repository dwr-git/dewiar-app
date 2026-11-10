"""0.86 — «Чат» студии как в других чатах и идеи людей. Настоящее ядро, модель-заглушка, Playwright.

Пользователь: «нельзя ли в чат добавить стандартные для всех чатов вещи — кнопки остановки, перегенерации, исправления
и метрики? Без этого неуютно». Проверяем:
— «Стоп»: пока отвечает, «Отправить» — «Стоп»; нажали — ответ остановлен, написанное осталось в ленте («остановлено»);
— «Подробности»: модель, первое слово, весь ответ, токены (из usage сервера), персонаж;
— «Ещё раз»: новый ответ — вариантом той же записи (‹ 2 из 2 ›, листается), модель не видит прежнего ответа;
— «Изменить»: последний вопрос — новым текстом, ответ после него заменён, модель видит новый вопрос, а не старый;
— «Копировать» — текст ответа в буфере;
— №145: беседы — «Новая беседа» (прежняя в списке), открыть прежнюю — её лента и ПАМЯТЬ модели; переименовать, удалить;
  выгрузка .md / .txt; «вспомни, что я говорил» видит и отложенные беседы;
— №156: Ctrl+B прячет меню слева (раздел на всю ширину), выбор помнится;
— №164: файлы к новой задаче — во «Входящие» папки задачи (у документов — их текст рядом), задача знает о них;
— №154: сочетание «Позвать Лиру» (Ctrl+Alt+Space; GNOME — своё сочетание с «--mic», Windows — второй RegisterHotKey),
  команда mute_toggle;
— №155: карточка виджета — текст крупнее вместе с ней, уголок для растягивания виден, место запоминается при «спрятать»/выходе;
— №159: Джарвис — ворчливый дворецкий с сухой иронией (новый текст, прежний — в OLD_DEFAULTS), сценарий экзамена."""
import base64, json, os, re, socket, stat, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOT = os.environ.get("CHAT086_SHOT")           # папка — снимки всех новых элементов в светлой и тёмной теме
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


REQ = []                                         # что модель получила (сообщения каждого запроса)
CNT = {"n": 0}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body.get("messages") or []
        if any("краткое содержание" in str(m.get("content", "")) for m in msgs[:1]):
            parts = ["- Пользователь говорил о разном."]
        else:
            REQ.append(msgs)
            q = next((m["content"] for m in reversed(msgs) if m["role"] == "user" and isinstance(m["content"], str)), "")
            q = q.split("(Сообщение пользователя)\n")[-1].strip()
            CNT["n"] += 1
            n = CNT["n"]
            if "медленно" in q:
                parts = [f"Слово{i} " for i in range(40)]
            else:
                parts = [f"Ответ №{n} ", f"на «{q[:60]}».", " Готово."]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        try:
            for part in parts:
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': part}}]}, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush(); time.sleep(0.25 if len(parts) > 5 else 0.15)
            self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":1234,"completion_tokens":56}}\n\ndata: [DONE]\n\n')
        except (BrokenPipeError, ConnectionResetError):
            pass


UP, PORT = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = Path(tempfile.mkdtemp()); (tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False},
    "ui": {"intro": "done", "welcome": "done", "news_seen": "99.0.0"},
    "report": {"pulse": False}, "team": {"route": False}, "tools": {"enabled_all": False},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{UP}/v1", "model": "qwen-mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_DRY_TOOLS="1")


def texts(msgs):
    return " | ".join(str(m.get("content")) for m in msgs if isinstance(m.get("content"), str))


errs = []
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "a"), stderr=subprocess.STDOUT)
try:
    for _ in range(150):
        time.sleep(0.2)
        if (tmp / "cfg/token").exists():
            break
    time.sleep(2.5)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1300, "height": 880}, accept_downloads=True)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        pg = ctx.new_page()
        pg.on("pageerror", lambda x: errs.append(str(x)))
        url = (ROOT / "ui/settings.html").as_uri() + f"?token={(tmp / 'cfg/token').read_text().strip()}&port={PORT}#chat"
        pg.goto(url); pg.wait_for_timeout(2500)
        call = lambda cmd, a=None: pg.evaluate("([c, a]) => core.call(c, a || {})", [cmd, a])

        def shot(name):
            if not SHOT:
                return
            for skin in ("neusky", "neudusk"):
                pg.evaluate(f"studioSkin('{skin}', true)"); pg.wait_for_timeout(120)
                pg.screenshot(path=str(Path(SHOT) / f"{name}-{skin}.png"))
            pg.evaluate("studioSkin('neusky', true)")

        # ── «Стоп» ──
        pg.fill("#ch-text", "Расскажи медленно длинную историю"); pg.press("#ch-text", "Enter")
        pg.wait_for_selector("#ch-go.stop", timeout=15000); pg.wait_for_timeout(1500)
        g = pg.evaluate("() => [document.getElementById('ch-go').textContent.trim(), document.getElementById('ch-go').title]")
        ok(g[0] == "Стоп" and "Esc" in g[1], f"пока отвечает — «Отправить» стала «Стоп»: {g}")
        shot("stop")
        pg.fill("#ch-text", "x"); g2 = pg.evaluate("() => document.getElementById('ch-go').classList.contains('stop')"); pg.fill("#ch-text", "")
        ok(not g2, "набрали текст — снова «Отправить» (новый вопрос сам перебьёт ответ)")
        pg.click("#ch-go"); pg.wait_for_timeout(1500)
        S = pg.evaluate("""() => ({ stop: document.getElementById('ch-go').classList.contains('stop'),
            last: [...document.querySelectorAll('#ch-msgs .cl-m:not(.out)')].map(m => [m.querySelector('.tx') && m.querySelector('.tx').textContent, !!m.querySelector('.ch-tag')]).pop(),
            live: !!document.getElementById('ch-live') })""")
        ok(not S["stop"] and S["last"] and "Слово0" in (S["last"][0] or "") and S["last"][1] and not S["live"],
           f"«Стоп» — ответ остановлен, написанное осталось с пометкой «остановлено»: {S}")
        nwords = len(re.findall(r"Слово\d+", S["last"][0] or ""))
        ok(0 < nwords < 40, f"остановлено на полпути ({nwords} из 40 слов)")
        # ── обычный ответ: «Подробности» ──
        pg.fill("#ch-text", "Как дела у Лиры?"); pg.press("#ch-text", "Enter")
        pg.wait_for_selector("#ch-msgs .ch-acts.last [data-regen]", timeout=20000); pg.wait_for_timeout(500)
        L = call("chat_list", {"limit": 10})["items"]
        a1 = L[-1]
        m = a1.get("meta") or {}
        ok(m.get("model") == "qwen-mock" and m.get("tin") == 1234 and m.get("tout") == 56 and 0 <= m.get("first", -1) <= m.get("total", -1) and a1.get("who") == "lira",
           f"у ответа — метрики: модель, первое слово, весь ответ, токены: {m}")
        pg.click(f"#ch-msgs [data-info='{a1['id']}']"); pg.wait_for_timeout(300)
        dl = pg.inner_text(f"#ch-meta-{a1['id']}")
        ok("qwen-mock" in dl and "1 234 на входе" in dl.replace(" ", " ") and "56 в ответе" in dl and "Лира" in dl and "через" in dl and pg.locator(".ch-tl i").count() == 1,
           f"«Подробности» раскрылись: {dl!r}")
        ok(pg.get_attribute(f"#ch-msgs [data-info='{a1['id']}']", "aria-expanded") == "true", "у кнопки — aria-expanded")
        shot("details")
        # ── «Копировать» ──
        pg.click(f"#ch-msgs [data-copy='{a1['id']}']"); pg.wait_for_timeout(300)
        clip = pg.evaluate("() => navigator.clipboard.readText()")
        ok(clip == a1["text"] and "Скопировано" in pg.inner_text(f"#ch-msgs [data-copy='{a1['id']}']"), f"«Копировать» — текст ответа в буфере: {clip!r}")
        # ── «Ещё раз» ──
        nreq = len(REQ)
        pg.click(f"#ch-msgs [data-regen='{a1['id']}']")
        pg.wait_for_function("() => /2 из 2/.test((document.querySelector('#ch-msgs .ch-pg b') || {}).textContent || '')", timeout=20000)
        pg.wait_for_timeout(400)
        L = call("chat_list", {"limit": 10})["items"]
        a2 = L[-1]
        ok(a2["id"] == a1["id"] and len(a2.get("vars") or []) == 1 and a2["vars"][0]["text"] == a1["text"] and a2["text"] != a1["text"]
           and sum(1 for x in L if x["role"] == "user" and x["text"] == "Как дела у Лиры?") == 1,
           f"«Ещё раз» — новый ответ вариантом той же записи, вопрос не задвоился: {a2['text']!r} / {[v['text'] for v in a2.get('vars') or []]}")
        rq = REQ[nreq] if len(REQ) > nreq else []
        ok("Как дела у Лиры?" in texts(rq) and a1["text"] not in texts(rq), "модель переспросили тем же вопросом, прежнего ответа она не видит")
        shot("variants")
        pg.click(f"#ch-msgs [data-vp='{a1['id']}'][data-d='-1']"); pg.wait_for_timeout(200)
        V = pg.evaluate(f"() => [document.querySelector('#ch-msgs .ch-pg b').textContent, [...document.querySelectorAll('#ch-msgs .cl-m:not(.out) .tx')].pop().textContent]")
        ok(V[0] == "1 из 2" and V[1].strip() == a1["text"], f"‹ — виден прежний вариант: {V}")
        pg.click(f"#ch-msgs [data-vp='{a1['id']}'][data-d='1']"); pg.wait_for_timeout(200)
        # ── «Изменить» ──
        u = [x for x in L if x["role"] == "user"][-1]
        pg.click(f"#ch-msgs [data-edit='{u['id']}']"); pg.wait_for_timeout(200)
        ok(pg.is_visible("#ch-edit") and pg.input_value("#ch-edit") == "Как дела у Лиры?", "«Изменить» — поле с текстом вопроса прямо в пузыре")
        shot("edit")
        nreq = len(REQ)
        pg.fill("#ch-edit", "Как дела у Патрика?"); pg.press("#ch-edit", "Enter")
        pg.wait_for_function("() => [...document.querySelectorAll('#ch-msgs .cl-m:not(.out) .tx')].pop().textContent.includes('Патрика')", timeout=20000)
        pg.wait_for_timeout(500)
        L = call("chat_list", {"limit": 10})["items"]
        users = [x for x in L if x["role"] == "user"]
        ok(users[-1]["id"] == u["id"] and users[-1]["text"] == "Как дела у Патрика?" and users[-1].get("edited")
           and not any(x["id"] == a1["id"] for x in L) and L[-1]["role"] == "assistant" and "Патрика" in L[-1]["text"],
           f"вопрос исправлен, прежний ответ убран, новый — после него: {[(x['role'], x['text'][:30]) for x in L[-3:]]}")
        rq = texts(REQ[nreq]) if len(REQ) > nreq else ""
        ok("Как дела у Патрика?" in rq and "Как дела у Лиры?" not in rq and a2["text"] not in rq, f"модель видит исправленный вопрос, а не прежний: {rq[-200:]!r}")
        ok("изменено" in pg.inner_text("#ch-msgs"), "у исправленного вопроса — «изменено»")
        # ── беседы ──
        th0 = call("chat_threads")["threads"]
        ok(len(th0) == 1 and th0[0]["active"] and th0[0]["title"].startswith("Расскажи медленно"), f"одна беседа, название — по первому вопросу: {th0}")
        pg.click("#ch-new"); pg.wait_for_timeout(800)
        ok(pg.evaluate("() => document.querySelectorAll('#ch-msgs .cl-m').length") == 0 and pg.is_visible("#ch-empty"), "«Новая беседа» — чистый лист")
        nreq = len(REQ)
        pg.fill("#ch-text", "Меня зовут Пётр, запомни для этой беседы"); pg.press("#ch-text", "Enter")
        pg.wait_for_selector("#ch-msgs .cl-m:not(.out) >> text=Ответ", timeout=20000); pg.wait_for_timeout(600)
        rq = texts(REQ[nreq])
        ok("Патрика" not in rq and "Лиры" not in rq, "в новой беседе модель не видит прежнюю")
        pg.click("#ch-th"); pg.wait_for_timeout(300)
        rows = pg.evaluate("() => [...document.querySelectorAll('#ch-thl li')].map(li => [li.classList.contains('on'), li.querySelector('b').textContent])")
        ok(len(rows) == 2 and rows[0][0] and rows[0][1].startswith("Меня зовут Пётр") and rows[1][1].startswith("Расскажи медленно"),
           f"список бесед: открытая первой, прежняя — ниже: {rows}")
        shot("threads")
        pg.click("#ch-thl li:nth-child(2) .ch-tho"); pg.wait_for_timeout(1200)
        ok("Как дела у Патрика?" in pg.inner_text("#ch-msgs") and "Пётр" not in pg.inner_text("#ch-msgs"), "открыли прежнюю — её лента")
        nreq = len(REQ)
        pg.fill("#ch-text", "А что я спрашивал?"); pg.press("#ch-text", "Enter")
        pg.wait_for_function("() => [...document.querySelectorAll('#ch-msgs .cl-m:not(.out) .tx')].pop().textContent.includes('что я спрашивал')", timeout=20000)
        rq = texts(REQ[nreq])
        ok("Как дела у Патрика?" in rq and "Пётр" not in rq, f"память модели — своей беседы: {rq[-240:]!r}")
        th = call("chat_threads")["threads"]
        pid = [t for t in th if not t["active"]][0]["id"]
        call("chat_thread_rename", {"id": pid, "title": "Про Петра"})
        th = call("chat_threads")["threads"]
        ok(any(t["title"] == "Про Петра" and t["named"] for t in th), "переименовали")
        # выгрузка
        md = call("chat_export", {"fmt": "md"}); tx = call("chat_export", {"id": pid, "fmt": "txt"})
        ok(md["name"].endswith(".md") and md["text"].startswith("# Расскажи медленно") and "**Вы**" in md["text"] and "**Лира**" in md["text"] and "Как дела у Патрика?" in md["text"],
           f"выгрузка .md: {md['name']} {md['text'][:120]!r}")
        ok(tx["name"] == "Про Петра.txt" and "Вы:" in tx["text"] and "Меня зовут Пётр" in tx["text"] and "**" not in tx["text"], f"выгрузка .txt другой беседы: {tx['text'][:120]!r}")
        pg.click("#ch-exp summary"); pg.wait_for_timeout(200)
        shot("export")
        with pg.expect_download() as dl_info:
            pg.click("#ch-exp [data-fmt='txt']")
        dl = dl_info.value; raw = Path(dl.path()).read_bytes()
        ok(dl.suggested_filename.endswith(".txt") and raw.startswith(b"\xef\xbb\xbf") and "Как дела у Патрика?" in raw.decode("utf-8-sig"),
           f"«Сохранить → .txt» — файл с меткой UTF-8 (Блокнот Windows): {dl.suggested_filename}")
        # «вспомни, что я говорил» видит отложенную беседу
        sys.path.insert(0, str(ROOT / "core"))
        from chatlog import ChatLog
        cl = ChatLog(tmp / "st/chat.jsonl")
        import tools as T
        hit = T._chat_hits({"chatlog": cl}, "меня зовут Пётр")
        ok("Пётр" in hit, f"поиск по прошлым разговорам — и в отложенной беседе: {hit[:120]!r}")
        call("chat_thread_delete", {"id": pid})
        th = call("chat_threads")["threads"]
        ok(len(th) == 1 and not (tmp / f"st/chats/{pid}.jsonl").exists(), "удалили беседу — и её файлы")
        # ── №156: меню слева ──
        pg.keyboard.press("Escape"); pg.click("body", position={"x": 700, "y": 40})
        pg.keyboard.press("Control+b"); pg.wait_for_timeout(300)
        N = pg.evaluate("() => [document.documentElement.classList.contains('nav-off'), getComputedStyle(document.querySelector('nav')).display, document.querySelector('main').getBoundingClientRect().left, getComputedStyle(document.getElementById('nav-show')).display]")
        ok(N[0] and N[1] == "none" and N[2] < 5 and N[3] == "grid", f"Ctrl+B — меню спрятано, раздел на всю ширину, кнопка вернуть: {N}")
        shot("navoff")
        pg.reload(); pg.wait_for_timeout(2000)
        ok(pg.evaluate("() => document.documentElement.classList.contains('nav-off')"), "после перезапуска студии меню всё ещё спрятано")
        pg.click("#nav-show"); pg.wait_for_timeout(200)
        ok(pg.evaluate("() => !document.documentElement.classList.contains('nav-off') && getComputedStyle(document.querySelector('nav')).display !== 'none'"), "кнопка слева вверху — меню вернулось")
        # ── №164: файлы к задаче ──
        (tmp / "смета.txt").write_text("Плитка 12 м², клей 3 мешка.", encoding="utf-8")
        pg.evaluate("() => document.querySelector('nav button[data-p=\"tasks\"]').click()"); pg.wait_for_timeout(500)
        pg.click("#t-new")
        pg.set_input_files("#t-file", [str(tmp / "смета.txt")]); pg.wait_for_timeout(400)
        ok(pg.inner_text("#t-atts").count("смета.txt") == 1 and "Входящие" in pg.inner_text("#t-atts"), "к задаче приложен файл — плашка под полем")
        pg.fill("#t-goal", "Посчитай по смете, сколько всего материалов")
        shot("taskfiles")
        pg.click("#t-go"); pg.wait_for_timeout(1500)
        tdirs = [d for d in (tmp / "ws").rglob("Входящие") if d.parent.name.endswith("Посчитай по смете, сколько всего материалов") or "Посчитай" in d.parent.name]
        got = sorted(x.name for x in tdirs[0].iterdir()) if tdirs else []
        ok(got == ["смета.txt"] and (tdirs[0] / "смета.txt").read_text(encoding="utf-8").startswith("Плитка"), f"файл — во «Входящих» папки задачи: {tdirs} {got}")
        t = json.loads((tdirs[0].parent / "задача.json").read_text(encoding="utf-8")) if tdirs else {}
        ok(t.get("files") == ["Входящие/смета.txt"], f"задача знает о файле: {t.get('files')}")
        ok(pg.evaluate("() => document.querySelectorAll('#t-atts .ch-chip').length") == 0, "после «Начать» плашки очищены")
        b.close()
    # документ — рядом его текст (без браузера, ядро напрямую)
    sys.path.insert(0, str(ROOT / "core"))
    import tasks as TK
    d = tmp / "tdoc"; d.mkdir()
    html = "<html><body><h1>Отчёт</h1><p>Выручка 120 тысяч.</p></body></html>"
    got = TK.TaskManager._inbox_files(d, [{"name": "../отчёт.html", "b64": "data:text/html;base64," + base64.b64encode(html.encode()).decode()},
                                    {"name": "x", "b64": "@@@"}])
    ok(got[0] == "Входящие/отчёт.html" and any(g.endswith("(текст).txt") for g in got) and "Выручка" in (d / "Входящие/отчёт (текст).txt").read_text(encoding="utf-8")
       and not (tmp / "отчёт.html").exists(), f"у документа — его текст рядом, путь из имени не выходит из папки: {got}")
    # ── №154: «Позвать Лиру» ──
    from websockets.sync.client import connect
    ws = connect(f"ws://127.0.0.1:{PORT}", open_timeout=5).__enter__()
    ws.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()})); ws.recv(timeout=10)
    nid = [100]

    def wcall(cmd, args=None):
        nid[0] += 1; ws.send(json.dumps({"id": nid[0], "cmd": cmd, "args": args or {}}))
        while True:
            m = json.loads(ws.recv(timeout=20))
            if m.get("type") == "reply" and m.get("id") == nid[0]:
                return m.get("data")
    m1 = wcall("mute_toggle"); m2 = wcall("mute_toggle")
    ok(m1 is True and m2 is False, f"mute_toggle — микрофон выключить и включить: {m1} {m2}")
    ws.close()
finally:
    core.terminate(); core.wait(10)

sys.path.insert(0, str(ROOT / "ui"))
import hotkey as HK  # noqa: E402
ok(HK.DEFAULT_MIC == "Ctrl+Alt+Space" and HK.to_gnome(HK.DEFAULT_MIC) == "<Control><Alt>space" and HK.to_win(HK.DEFAULT_MIC) == (0x4003, 0x20),
   "Ctrl+Alt+Space — для GNOME и RegisterHotKey")
ok(HK.command(ROOT, "mic").endswith("app.py --mic") and HK.command(ROOT).endswith("app.py --capture") and HK.KINDS["mic"][0] != HK.GN_PATH, "своя запись GNOME и команда «--mic»")
bin_ = tmp / "bin"; bin_.mkdir(); db = tmp / "gs.json"; db.write_text("{}")
fake = bin_ / "gsettings"
fake.write_text(f"""#!{sys.executable}
import json, sys
db = {str(db)!r}; d = json.load(open(db)); a = sys.argv[1:]
if a[0] == "list-relocatable-schemas": print({HK.GN_ONE!r}); sys.exit(0)
if a[0] == "list-schemas": print({HK.GN_SCHEMA!r}); sys.exit(0)
k = a[1] + "|" + a[2]
if a[0] == "get": print(d.get(k, "@as []" if a[2] == "custom-keybindings" else "''")); sys.exit(0)
if a[0] == "set": d[k] = a[3]
if a[0] == "reset": d.pop(k, None)
json.dump(d, open(db, "w"))
""")
fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
os.environ["PATH"] = str(bin_) + os.pathsep + os.environ["PATH"]
r1 = HK.gnome_set(True, "Ctrl+Alt+N", HK.command(ROOT))
r2 = HK.gnome_set(True, "Ctrl+Alt+Space", HK.command(ROOT, "mic"), "mic")
st = HK.gnome_state("Ctrl+Alt+Space", "mic")
lst = json.loads(db.read_text())[f"{HK.GN_SCHEMA}|custom-keybindings"]
ok(r1[0] and r2[0] and st["on"] and st["binding"] == "<Control><Alt>space" and st["command"].endswith("--mic") and lst.count("dewiar-") == 2,
   f"GNOME: оба сочетания рядом: {r2} {st}")
r3 = HK.gnome_set(True, "Ctrl+Alt+N", HK.command(ROOT, "mic"), "mic")
ok(not r3[0] and "закинуть идею" in r3[1], f"та же клавиша, что у «Закинуть идею», — не отбираем: {r3}")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ws_src = (ROOT / "ui/winshell.py").read_text(encoding="utf-8")
ok("def mic_hotkey" in app and '"mic_set", "mic_status"' in app and 'what == "mic"' in app and "HOTKEY_MIC_ID" in app
   and "def hotkey(self, mods, vk, fn, hid=HOTKEY_ID)" in ws_src and "self._hk_fns[wp]" in ws_src,
   "окно: сочетание назначается (Windows — второй номер RegisterHotKey), сигнал «mic» зовёт ядро")
# ── №155 ──
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("--okt" in hud and "var(--okt, 1)" in hud and re.search(r"#grip \{ opacity: \.3; \}", hud), "карточка: текст растёт вместе с ней, уголок виден")
ok(app.count("self._remember_pos()") >= 2 and "def _remember_pos" in app, "место карточки запоминается, когда её прячут и при выходе")
with sync_playwright() as p:
    b = p.chromium.launch()
    sz = {}
    for w, h in ((300, 420), (520, 760)):
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.add_init_script("window.pywebview = { api: { get_pos: () => Promise.resolve([0, 0]) } };")
        pg.goto((ROOT / "ui/hud.html").as_uri() + "?token=x&port=1"); pg.wait_for_timeout(500)
        sz[w] = pg.evaluate("() => parseFloat(getComputedStyle(document.getElementById('bubble')).fontSize)")
        if SHOT:
            pg.hover("#card"); pg.screenshot(path=str(Path(SHOT) / f"hud-{w}.png"))
        pg.close()
    b.close()
ok(sz[300] == 13.5 and 16 < sz[520] <= 17.6, f"строка состояния крупнее на большой карточке: {sz}")
# ── рецензия 0.86: «Ещё раз» после «да» — подтверждение спрашивается заново; детский режим — беседы закрыты ──
import types  # noqa: E402
sys.path.insert(0, str(ROOT / "core"))
import engine_chat, engine_tools, engine_commands  # noqa: E402


class _Conv:
    def save(self, h): pass


class _E(engine_chat.ChatMixin, engine_tools.ToolsMixin):
    pass


def _eng():
    e = _E(); e.cancel_turn = lambda: None; e.conv = _Conv()
    e.history = [{"role": "user", "content": "отправь письмо Ивану, что встреча в 5"},
                 {"role": "assistant", "content": "Отправить Ивану письмо «Встреча в 17:00»?"},
                 {"role": "user", "content": "да"}, {"role": "assistant", "content": "Отправила письмо Ивану."}]
    e.last_turn_time = time.monotonic() - 20
    return e


e = _eng(); e.history = e.history[:2]               # модель только что спросила «Отправить…?»
ok(e._just_agreed(types.SimpleNamespace(asked="да", n=1)), "контроль: живое «да» на вопрос модели — согласие (№478)")
e = _eng()
q = e._chat_rewind({"text": "да"}, {"text": "Отправила письмо Ивану."})
ok(q == "да" and not e._just_agreed(types.SimpleNamespace(asked=q, n=7)),
   "«Ещё раз» после «да» с действием (send_email): переспрошенное «да» — не согласие, «Выполнить?» спросят заново")
e._chat_replay = 0
ok(not e._just_agreed(types.SimpleNamespace(asked=q, n=7, replay=True)), "ход «Ещё раз»/«Изменить» помечен turn.replay — тоже не согласие")
ans = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("turn.replay = bool(rp and" in ans and "self._chat_replay = 0" in ans, "ask переносит метку повтора в ход и сбрасывает её")
kb = engine_commands._kids_blocked
lock = ["chat_thread_open", "chat_thread_new", "chat_thread_rename", "chat_thread_delete", "chat_threads", "chat_export", "chat_regen", "chat_edit", "chat_clear"]
ok(all(kb(c, {}) for c in lock) and not kb("chat_list", {}) and not kb("say", {}) and not kb("stop", {}),
   f"детский режим: беседы, выгрузка, «Ещё раз», «Изменить» закрыты, текущая лента и разговор — нет: {[c for c in lock if not kb(c, {})]}")

# ── №159 ──
import personas as PS  # noqa: E402
ok("ворчлив" in PS.JARVIS_CHAR and "сарказм" in PS.JARVIS_CHAR and "«вы»" in PS.JARVIS_CHAR and "не грубишь" in PS.JARVIS_CHAR
   and PS.TEMPLATES["jarvis"]["character"] == PS.JARVIS_CHAR, "Джарвис — ворчливый дворецкий с сухой иронией, вежлив")
olds = PS.OLD_DEFAULTS["jarvis"]
ok(isinstance(olds, list) and any(o.get("character") == PS.JARVIS_CHAR_085 for o in olds), "прежний текст Джарвиса — в OLD_DEFAULTS (сохранённый персонаж получит новый)")
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ok("jarvis_irony" in sc and sc["jarvis_irony"]["steps"][0].get("template") == "jarvis" and 'stp.get("template")' in (ROOT / "core/exam.py").read_text(encoding="utf-8"),
   "сценарий экзамена: Джарвис отвечает точно, на «вы», с одной сухой ремаркой")
ok(not errs, f"без ошибок JavaScript: {errs[:3]}")
print("\nИТОГ:", "всё хорошо" if not fails else f"{len(fails)} проблем(ы)")
sys.exit(1 if fails else 0)
