"""Телефон: ловит ответы «нет доступа к камере» на «сфотографируй меня и опиши» и «Позвала Патрика» без переключения.
Проверяет: камера в приложении (живой кадр, отсчёт, снимок модели картинкой; модель без зрения — честно об этом);
«позови Патрика», «Патрик, как думаешь…» — переключение без модели, новый персонаж отвечает сам."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
LLM = free()
LOG = tmp / "llm.jsonl"
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)   # живое лицо Эвы
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG_FULL=str(LOG)))
time.sleep(1)


def proxy(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    try:
        r = urllib.request.urlopen(urllib.request.Request(req.url, data=req.post_data_buffer, method=req.method,
                                                          headers={"Content-Type": "application/json"}), timeout=60)
        body, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "application/json")
    except urllib.error.HTTPError as e:
        body, status, ctype = e.read(), e.code, "application/json"
    route.fulfill(status=status, body=body, headers={"Access-Control-Allow-Origin": "*", "Content-Type": ctype})


reqs = lambda: [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()] if LOG.exists() else []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
        ctx = b.new_context(permissions=["camera"])
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(f"http://127.0.0.1:{LLM}/**", proxy)
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
        pg.evaluate(f"""() => {{ Object.assign(S.llm, {{ kind: "openai", base_url: "http://127.0.0.1:{LLM}/v1", model: "chat", name: "тест" }}); S.persona = "lira"; saveS(); applyPersona(); }}""")

        def say(t, limit=20):
            pg.evaluate("t => { window._done = false; ask(t).then(() => window._done = true); }", t)
            for _ in range(limit * 10):
                pg.wait_for_timeout(100)
                if pg.evaluate("window._done && state === 'idle' && !busy"):
                    break
            return pg.inner_text("#bot")

        ans = say("Сфотографируй меня и опиши")
        shot = pg.evaluate("document.querySelector('#card img.shot') && document.querySelector('#card img.shot').src.slice(0, 23)")
        img_req = [r for r in reqs() if any(isinstance(m.get("content"), list) for m in r["messages"])]
        ok(shot == "data:image/jpeg;base64,", "камера: снимок сделан и показан под ответом")
        sv = pg.evaluate("[!!document.querySelector('#card .appc button[onclick=\"savePhoto()\"]'), (history[history.length - 1] || {}).note || '']")
        ok(sv[0] and "снимок с камеры показан" in sv[1], f"GitHub №20: после ответа — карточка снимка с «Сохранить», модель знает, что снимок на экране: {sv}")
        ok(img_req and "Вижу картинку" in ans, f"снимок ушёл модели картинкой, ответ — по снимку: {ans[:70]}")
        ok(not pg.evaluate("!!document.querySelector('#cam')"), "окно камеры закрылось, камера выключена")
        pg.evaluate("S.llm.model = 'blind'; saveS()")
        ans = say("Сфотографируй меня ещё раз")
        ok("со зрением" in json.dumps(reqs()[-1]["messages"], ensure_ascii=False) and ans.strip(),
           f"модель не видит картинки — честно об этом, без зависания: {ans[:70]}")
        pg.evaluate("S.llm.model = 'chat'; saveS()")
        n0 = len(reqs())
        ans = say("Позови Патрика")
        ok(pg.evaluate("S.persona") == "patrik" and pg.inner_text("#who-name") == "Патрик", "«Позови Патрика» — без модели: отвечает Патрик")
        later = reqs()[n0:]
        ok(later and "Тебя позвали" in json.dumps(later[0]["messages"][-1], ensure_ascii=False) and "Патрик" in later[0]["messages"][0]["content"],
           "Патрик сам откликается своим голосом и характером")
        n0 = len(reqs())
        say("Лира, как думаешь, пойдёт дождь?")
        later = reqs()[n0:]
        ok(pg.evaluate("S.persona") == "lira" and later and "как думаешь, пойдёт дождь" in json.dumps(later[0]["messages"][-1], ensure_ascii=False),
           "«Лира, как думаешь…» — вопрос сразу Лире")
        # модель повторяет «Звоню» из истории без вызова инструмента — звонка нет; её должны попросить позвонить по-настоящему
        pg.evaluate("window._calls = []")
        say("Свяжись с мамой по телефону")
        calls = pg.evaluate("window._calls")
        nudged = any("ты написал, что звонишь" in json.dumps(r["messages"][-1], ensure_ascii=False).lower() for r in reqs())
        ok(nudged and calls == ["+375291234567"], f"«Звоню» словами без звонка — модель просят позвонить по-настоящему, звонок идёт ({calls})")
        q = pg.evaluate("""async () => { window._calls = []; const a = await quick("перезвони"); const b = await quick("можешь позвонить +375 29 765-43-21");
                           const c = await quick("набери ещё раз"); return [a.say, b.say, c.say, window._calls]; }""")
        ok(q[3] == ["+375291234567", "+375297654321", "+375297654321"] and q[0].startswith("Звоню"),
           f"«перезвони», «набери ещё раз» — тому же; «можешь позвонить …» — без модели: {q}")
        ok(not errs, f"без ошибок JavaScript {errs}")
        b.close()
finally:
    mock.terminate()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
