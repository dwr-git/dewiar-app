"""Телефон 0.4.27 — по отчёту тестировщика (08.10): звонки родным, снимок на экране, связь на мобильном, пустые ответы.
«Позвони моей жене» — не набирать «Женю» по похожести, а спросить, как жена записана, и запомнить; поправка «нет,
нужно позвонить Наташа МТС» после звонка «маме» — звонок и запоминание. «Посмотри, как я выгляжу» → модель отвечает
«Вот.» без камеры — её возвращают к take_photo; снимок держится на экране и при следующей фразе; «покажи это фото» —
show_photo. Связь оборвалась на первом запросе — круг повторяется сам (без повторных действий). Модель сделала дело и
промолчала — её просят сказать итог словами, а не «Сделала, что просили»."""
import json, os, shutil, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


REQS = []


def stream(h, text="", calls=None, finish="stop"):
    h.send_response(200); h.send_header("Content-Type", "text/event-stream"); h.send_header("Access-Control-Allow-Origin", "*"); h.end_headers()
    if text:
        h.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': text}}]}, ensure_ascii=False)}\n\n".encode())
    for i, (name, args) in enumerate(calls or []):
        tc = {"index": i, "id": f"c{len(REQS)}{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
        h.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'tool_calls': [tc]}}]}, ensure_ascii=False)}\n\n".encode())
    if finish:
        h.wfile.write(f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': finish}]})}\n\n".encode())
    h.wfile.write(b"data: [DONE]\n\n")


def utext(m):
    c = m.get("content")
    return " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c or "")


def said(m):
    """Что сказал сам человек: без справок программы в начале сообщения («О пользователе…» — putProfile, «Справка к этому
    сообщению» — putContext). В справке — журнал недели («Посмотри, как я выгляжу» вчера), по нему отвечать нельзя."""
    t = utext(m)
    for mk in ("(Сообщение пользователя)\n", "(Дальше — разговор)\n"):
        if mk in t:
            return t.rsplit(mk, 1)[1]
    return t


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in (("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Headers", "*"), ("Access-Control-Allow-Methods", "*")):
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        b = json.dumps({"data": [{"id": "chat"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]
        REQS.append(body)
        first_user = next((said(m) for m in reversed(msgs) if m["role"] == "user" and not utext(m).startswith(("СТОП", "Скажи пользователю", "Снимок с камеры"))
                           and not utext(m).startswith("<tool_response>")), "").lower()
        last = msgs[-1]
        lu = utext(last)
        if "image_url" in json.dumps(last):
            return stream(self, "Вижу вас: выглядите отлично, причёска в порядке.")
        if "как я выгляжу" in first_user:
            if lu.startswith("СТОП"):
                return stream(self, "", [("take_photo", {"camera": "front"})])
            return stream(self, "Вот.")
        if "покажи это фото" in first_user:
            if last["role"] == "tool":
                return stream(self, "Снимок снова на экране.")
            return stream(self, "", [("show_photo", {})])
        if "фонарик и помолчи" in first_user:
            if lu.startswith("Скажи пользователю"):
                return stream(self, "Фонарик включён.")
            if last["role"] == "tool":
                return stream(self, "")
            return stream(self, "", [("flashlight", {"on": True})])
        if "радуг" in first_user:
            return stream(self, "Радуга — это солнечный свет, разложенный каплями дождя.")
        return stream(self, "Хорошо.")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
LLM = srv.server_address[1]

tmp = Path(tempfile.mkdtemp())
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
        ctx = b.new_context(permissions=["camera"])
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        cut = {"n": 0}

        def route(r):
            if cut["n"] > 0 and r.request.method == "POST":   # обрыв связи на первом запросе круга
                cut["n"] -= 1
                return r.abort("connectionreset")
            return r.continue_()
        pg.route(f"http://127.0.0.1:{LLM}/**", route)
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
        pg.evaluate(f"""() => {{ Object.assign(S.llm, {{ kind: "openai", base_url: "http://127.0.0.1:{LLM}/v1", model: "chat", name: "тест" }});
            S.persona = "lira"; S.relations = {{}}; saveS(); applyPersona();
            const BOOK = [{{ name: "Женя Петров", number: "+375291111111" }}, {{ name: "Наташа МТС", number: "+375292222222" }},
                          {{ name: "Мама старая", number: "+375293333333" }}];
            D.contact = (q) => {{ q = String(q).toLowerCase(); const c = BOOK.find(x => x.name.toLowerCase() === q)
                || BOOK.find(x => x.name.toLowerCase().split(" ").some(w => w.slice(0, 3) === q.slice(0, 3))); return c ? JSON.stringify(c) : ""; }};
            D.has = () => true; }}""")

        def say(t, limit=25):
            pg.evaluate("t => { window._done = false; ask(t).then(() => window._done = true); }", t)
            for _ in range(limit * 10):
                pg.wait_for_timeout(100)
                if pg.evaluate("window._done && state === 'idle' && !busy"):
                    break
            return pg.inner_text("#bot")

        calls = lambda: pg.evaluate("window._calls || []")
        # ---------- звонки родным ----------
        ans = say("Позвони моей жене")
        ok(not calls() and "записана" in ans, f"«позвони моей жене» — не «Женя» по похожести, а вопрос: {ans}")
        ans = say("Наташа МТС")
        ok(calls() == ["+375292222222"] and "Запомнила" in ans, f"ответ «Наташа МТС» — звонок и «запомнила»: {ans}")
        ok(pg.evaluate("S.relations['жена'] && S.relations['жена'].name") == "Наташа МТС", "кто жена — запомнено")
        say("Позвони жене")
        ok(calls()[-1] == "+375292222222", "«позвони жене» дальше — сразу Наташе")
        pg.evaluate("S.relations['мама'] = { name: 'Мама старая', number: '+375293333333' }; saveS()")
        say("Позвони маме")
        ans = say("Нет, ты не поняла, нужно позвонить Наташа МТС")
        ok(calls()[-2:] == ["+375293333333", "+375292222222"] and pg.evaluate("S.relations['мама'].name") == "Наташа МТС",
           f"поправка после звонка — звонок нужному и запоминание: {ans}")
        ok("Кто есть кто в контактах" in pg.evaluate("systemPrompt()"), "модель знает, кто есть кто")

        # ---------- камера ----------
        n0 = len(REQS)
        ans = say("Посмотри, как я выгляжу")
        stop = [r for r in REQS[n0:] if utext(r["messages"][-1]).startswith("СТОП")]
        ok(stop and "take_photo" in utext(stop[0]["messages"][-1]), "«Вот.» без камеры — модель возвращают к take_photo")
        ok(pg.evaluate("!!document.querySelector('#card img.shot')") and "Вижу вас" in ans, f"снимок сделан и показан, ответ по снимку: {ans[:50]}")
        ans = say("Покажи это фото мне")
        ok(pg.evaluate("!!document.querySelector('#card img.shot')"), "снимок не стёрся новой фразой — на экране")
        ok("show_photo" in json.dumps([c.get("function", {}).get("name") for r in REQS[-2:] for m in r["messages"] for c in (m.get("tool_calls") or [])]),
           "«покажи это фото» — show_photo")
        hist = pg.evaluate("history.slice(-4).map(h => h.note || '').join(' ')")
        ok("снимок с камеры показан" in hist, "в истории для модели — пометка, что снимок показан")
        ok("show_photo" in pg.evaluate("systemPrompt()"), "в подсказке модели — show_photo и камера по просьбам")

        # ---------- связь ----------
        cut["n"] = 1
        n0 = len(REQS)
        # вопрос к модели: погоду телефон с 1028 отвечает сам, без модели (phone_weather1028_test) — обрыв тут не проверить
        ans = say("Откуда берётся радуга", 30)
        ok("Радуга" in ans, f"связь оборвалась — круг повторён сам, ответ пришёл: {ans}")
        ok(len(REQS) - n0 == 1, "после обрыва — один повторный запрос, ход заново не начинается")

        # ---------- пустой ответ после действия ----------
        ans = say("Включи фонарик и помолчи")
        ok("Фонарик включён" in ans and "Сделала, что просили" not in ans, f"действие без слов — модель сказала итог: {ans}")
        logs = pg.evaluate("(window._plog || []).join('\\n')") if pg.evaluate("!!window._plog") else ""
        ok(not errs, f"без ошибок страницы: {errs[:2]}")
        b.close()
finally:
    srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
