"""Отчёты и комментарии 19.10 (пакет «Здоровья» + комментарии под видео) — каждое исправление проверкой:

1. Студия, «Мозг» → «Ключ любимого сервиса»: кнопка «Подключить» не работала — у неё был тот же id, что у «Отправить» в
   «Близких» (cl-go), обработчик доставался той кнопке. Комментарии: «почему нельзя подключить кастомного провайдера»,
   «почему только OpenRouter, OpenAI и Anthropic». Теперь — свои id, DeepSeek и «Другой — по адресу» (адрес без /v1 —
   допишем сами). Телефон — тоже «Другой — по адресу».
2. «Засыпает на половине фразы» (жалоба №83): после ответа длинный вопрос без имени принимался за разговор людей рядом —
   даже «…давай расскажи мне…» и «Я так и начал. Лира, расскажи…». Теперь просьба ко мне и имя внутри — вопрос.
3. Жалоба голосом оборвалась на паузе (№90: «передай разработчику приложения что» ушло как есть) — переспросить и дописать.
4. «Как пройти регистрацию? Только окно входа» (№88–89 и комментарии): студия больше не шлёт «зарегистрироваться на
   dewiar.pro» — там вход для тех, кому выдали аккаунт; ведёт в «Подключить бесплатно».
5. Телефон: «Рефералы» — «Пригласить» налезала на код (№91); «Управлять приложениями» — Dewiar серый в «Специальных
   возможностях» на Android 13+ (№87): шаги и кнопка «Страница Dewiar».
6. Журналы: нет папки «Документы» (342 сбоя за сутки) — запасная ~/Dewiar; сетевое хранилище Obsidian пропало — реже и
   без потока ошибок; «модели не хватило контекста» (LM Studio) — повтор с короткой историей и понятный совет;
   проверка порта окном — не «сбой» в журнале.
7. Windows: «оба окна просто чёрные» — пустое окно узнаём по снимку (blank_image) и включаем простую отрисовку."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import collections, http.server, json, logging, os, shutil, socket, subprocess, sys, tempfile, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
sys.path.insert(0, str(ROOT / "core"))
fails = []
TMP = Path(tempfile.mkdtemp())


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


# ---------- 2. длинная фраза в «продолжении разговора» ----------
from engine_base import name_inside, to_me  # noqa: E402
AL = {"lira": ["лира"], "patrik": ["патрик"], "eva": ["эва"]}
ok(name_inside("Я так и начал. Лира, расскажи мне что-нибудь о трендах", AL) == "lira" and name_inside("спроси у Лиры про погоду", AL) == "lira"
   and name_inside("Позови Патрика, пусть посмотрит", AL) == "patrik", "имя внутри фразы: во втором предложении и в падеже")
ok(name_inside("лирика — это жанр, а мы пошли в кино", AL) is None and name_inside("для мира это важно", AL) is None,
   "«лирика», «для мира» — не имя")
ok(to_me("Хорошо, давай расскажи мне, что можно создать сейчас из приложений") and not to_me(
    "Ну мы вчера с ним ходили туда и там было очень много людей а потом"), "просьба ко мне — по повелительному глаголу в начале")

# ---------- 3. жалоба оборвалась на паузе (компьютер) ----------
import health  # noqa: E402
ok(health.bug_note("приложения что") == ("", True) and health.bug_note("радио молчит") == ("радио молчит", False)
   and health.bug_note("приложения что во вкладке рефералы кнопка перекрывает код") == ("во вкладке рефералы кнопка перекрывает код", False)
   and health.bug_note("не работает радио и")[1] is True, "суть жалобы: служебное слово в конце — оборвалась")
sent, said = [], []
h = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *a, **k: ""), personas=types.SimpleNamespace(all=lambda: []),
                          follow_up_until=0.0, set_state=lambda s_: None)
h._say_quick = lambda msg, text, via, then=None: said.append(msg)
h.complaint_send = lambda note, who="", shot=True, via="": sent.append(note) or {"id": 92}
h._bug_cmd = types.MethodType(health.HealthMixin._bug_cmd, h)
r1 = h._bug_cmd("передай разработчику приложения что")
r2 = h._bug_cmd("во вкладке рефералы кнопка пригласить перекрывает код")
time.sleep(0.4)
ok(r1 and r2 and bool(said) and ("договорите" in said[0] or "Что случилось" in said[0]), f"оборвалось — переспросил: {said[:1]}")
ok(sent == ["во вкладке рефералы кнопка пригласить перекрывает код"], f"отправлена вся жалоба, а не «приложения что»: {sent}")

# ---------- 8. «Напомню тебе…» без напоминания (скриншот 19.10: «должен был утром напомнить, но не напомнил») ----------
import quality  # noqa: E402
ok(quality.remind_claim("Понял, моя королева. Исправляю: встреча с Ирой — на вторник, 12:00. Напомню тебе в понедельник утром в 9:00.")
   and quality.remind_claim("Поставила тебе напоминание на 9:00") and quality.remind_claim("Будильник поставлен на 7")
   and not quality.remind_claim("Напомню, что у тебя встреча в 12") and not quality.remind_claim("Напомню тебе в 9", ["set_reminder"]),
   "«напомню тебе в понедельник в 9» без set_reminder — проверка; «напомню, что…» и поставленное — нет")

ok(quality.appt_ask("Патрик Запиши встречу с Ирой лечитской на следующую неделю на вторник Ориентировочно на 12:00 и Напомни мне за день")
   and quality.appt_ask("Завтра в 13:00 у меня массаж.") and quality.appt_ask("Запиши на двадцать второе число 12:00 дня к Юле на массаж")
   and not quality.appt_ask("запиши в заметки: завтра купить хлеб") and not quality.appt_ask("Запиши идею: приложение для танцев"),
   "дело со временем («запиши встречу на вторник в 12», «завтра в 13 массаж») — в «Дела», а заметка — по слову «заметки» (отчёт №94)")
import engine_tools  # noqa: E402
et = types.SimpleNamespace(toolbox=types.SimpleNamespace(policy=lambda n: (True, False), title=lambda n: n))
r_ = engine_tools.ToolsMixin._use_tool(et, types.SimpleNamespace(asked="Патрик запиши встречу с Ирой на вторник в 12 и напомни за день"),
                                       {"name": "save_note", "args": {"title": "Встреча", "text": "Понял, моя королева…"}}, None) \
    if hasattr(engine_tools, "ToolsMixin") else ""
ok("set_reminder" in str(r_), f"компьютер: save_note на встречу со временем — «поставь напоминанием»: {str(r_)[:80]}")

et2 = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *k, **kw: False if k == ("net", "web_via") else None))
try:
    engine_tools.ToolsMixin._dewiar_web(et2, "search", "x"); wv = ""
except RuntimeError as e:
    wv = str(e)
ok("выключен" in wv, f"компьютер: запасной путь через сервер Dewiar выключается настройкой net.web_via: {wv}")

import net as _net  # noqa: E402
ok(_net.lan_url("http://127.0.0.1:1234/v1", "192.168.1.5") == ("http://192.168.1.5:1234/v1", True)
   and _net.lan_url("https://api.openai.com/v1", "192.168.1.5") == ("https://api.openai.com/v1", False),
   "QR для телефона: модель «127.0.0.1:1234» компьютера → адрес компьютера в домашней сети (19.10: 16 сбоев «Failed to connect to 127.0.0.1»)")
src = srctext.text(ROOT, "core/engine_commands.py")
ok("_net.lan_url(" in src and "Serve on Local" in src, "phone_config: адрес модели переписывается и есть подсказка про LM Studio / Ollama")

# ---------- 6. рабочая папка, Obsidian, контекст ----------
bad = TMP / "file.txt"; bad.write_text("x")
code = ("import os,sys; sys.path.insert(0, sys.argv[1]); import workspace; print(workspace.Workspace(None).root)")
out = subprocess.run([PY, "-c", code, str(ROOT / "core")], capture_output=True, text=True,
                     env=dict(os.environ, DEWIAR_WORKSPACE_DIR=str(bad / "Документы" / "Dewiar"), DEWIAR_WORKSPACE_FALLBACK=str(TMP / "home-Dewiar"))).stdout.strip()
ok(out == str(TMP / "home-Dewiar") and (TMP / "home-Dewiar").is_dir(), f"«Документы» недоступны — рабочая папка ~/Dewiar, а не сбой на каждом шаге: {out}")

import obsidian  # noqa: E402
waits, recs = [], []


class Stop:
    def wait(self, w):
        waits.append(w); return len(waits) > 7


class H(logging.Handler):
    def emit(self, r): recs.append(r)


obsidian.log.addHandler(H()); obsidian.log.setLevel(logging.DEBUG)
cls = obsidian.Obsidian
o = cls.__new__(cls)
o.cfg = lambda: {"vault": "X:\\Obsidian Vault"}
o.sync = lambda: (_ for _ in ()).throw(OSError(121, "Превышен таймаут семафора"))
cls.loop(o, Stop(), every=20)
warn = [r for r in recs if r.levelno >= logging.WARNING]
ok(waits[1:4] == [40, 80, 160] and max(waits) == 600 and len(warn) == 1 and not any(r.levelno >= logging.ERROR for r in recs),
   f"Obsidian: сетевое хранилище пропало — реже (до 10 мин) и одно предупреждение, а не поток ошибок: {waits}, {len(warn)}")

import llm  # noqa: E402
ok(all(llm.ctx_full(x) for x in ['Engine protocol predict stream returned an error: {"code":500,"message":"Context size has been exceeded."}',
                                 "the request exceeds the available context size, try increasing it",
                                 "This model's maximum context length is 8192 tokens", "context_length_exceeded"])
   and not llm.ctx_full("сервер модели не ответил вовремя"), "«не хватило контекста» узнаётся у LM Studio, llama.cpp, vLLM, OpenAI")
ok(len(llm._ctx_cut([{"role": "user", "content": "старое"}, {"role": "assistant", "content": "a"}, {"role": "user", "content": "новое"}])) == 1,
   "короткая история — только текущая просьба")
LLMP, seen = free(), []


class LM(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append(len(d["messages"]))
        if len(d["messages"]) > 2:                 # system + история — «не влезло»
            b = b'{"error":{"code":500,"message":"Context size has been exceeded.","type":"server_error"}}'
            self.send_response(500); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"\\u0413\\u043e\\u0442\\u043e\\u0432\\u043e"}}]}\n\ndata: [DONE]\n\n')


srv = http.server.ThreadingHTTPServer(("127.0.0.1", LLMP), LM); threading.Thread(target=srv.serve_forever, daemon=True).start()
prof = {"kind": "openai", "base_url": f"http://127.0.0.1:{LLMP}/v1", "model": "m", "disable_thinking": True, "tools_mode": "prompt"}
hist = [{"role": "user", "content": "раз"}, {"role": "assistant", "content": "два"}, {"role": "user", "content": "привет"}]
try:
    text = "".join(v for k, v in llm.stream_events(prof, "sys", hist) if k == "text")
except Exception as e:  # noqa: BLE001
    text = f"ошибка: {e}"
ok(text == "Готово" and seen[0] > 2 and seen[-1] == 2, f"контекст переполнен — повтор с короткой историей и ответ: {text!r}, сообщений {seen}")
srv.shutdown()
LLMP2, seen2 = free(), []


class LM2(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"])); seen2.append(1)
        if len(seen2) == 1:                        # LM Studio выгрузил модель по таймеру
            b = b'{"error":"Model is unloaded."}'
            self.send_response(400); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n')


srv2 = http.server.ThreadingHTTPServer(("127.0.0.1", LLMP2), LM2); threading.Thread(target=srv2.serve_forever, daemon=True).start()
try:
    text2 = "".join(v for k, v in llm.stream_events(dict(prof, base_url=f"http://127.0.0.1:{LLMP2}/v1"), "sys", hist[-1:]) if k == "text")
except Exception as e:  # noqa: BLE001
    text2 = f"ошибка: {e}"
ok(text2 == "ok" and len(seen2) == 2, f"«Model is unloaded» (LM Studio выгрузил модель) — один повтор, и ответ: {text2!r}, запросов {len(seen2)}")
srv2.shutdown()

# ---------- 7. чёрное окно WebView2 ----------
sys.path.insert(0, str(ROOT / "ui"))
from PIL import Image, ImageDraw  # noqa: E402
import app as uiapp  # noqa: E402
full = Image.new("RGB", (300, 200), (11, 11, 14)); d = ImageDraw.Draw(full); d.ellipse((100, 20, 200, 120), fill=(200, 190, 210)); d.text((90, 150), "Я вас слушаю", fill=(240, 240, 240))
ok(uiapp.blank_image(Image.new("RGB", (300, 200), (11, 11, 14))) and not uiapp.blank_image(full), "чёрная заливка без содержимого — «не отрисовалось»; виджет с обликом — нет")
os.environ.pop("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", None)
uiapp.soft_render_env(True); a1 = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
uiapp.soft_render_env(False)
ok("--disable-gpu" in a1 and "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS" not in os.environ, "простая отрисовка — флаг WebView2 включается и снимается")
ws_src = (ROOT / "ui/winshell.py").read_text(encoding="utf-8")
ok("Окна чёрные? Перерисовать проще" in (ROOT / "ui/app.py").read_text(encoding="utf-8") and "fix=None" in ws_src, "пункт в меню значка у часов")

# ---------- 1, 4, 6 (журнал): студия с настоящим ядром ----------
import re  # noqa: E402
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ids = re.findall(r'\bid="([^"$]+)"', html)
dup = sorted({i for i in ids if ids.count(i) > 1})
ok(not dup, f"в студии нет повторяющихся id (из-за cl-go не работала кнопка «Подключить»): {dup}")
ok("арегистрируйтесь на" not in html + (ROOT / "ui/studio/dewiar.js").read_text(encoding="utf-8") + (ROOT / "ui/assets/help.js").read_text(encoding="utf-8"),
   "студия не отправляет «зарегистрироваться на dewiar.pro» (там нет регистрации)")
ctmp = TMP / "c"; (ctmp / "cfg").mkdir(parents=True)
PORT, MOCK = free(), free()
(ctmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "llm": {"active": "t", "profiles": {"t": {"name": "Mock", "kind": "openai", "base_url": f"http://127.0.0.1:{MOCK}/v1", "disable_thinking": True}}},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(ctmp / "cfg"), DEWIAR_STATE_DIR=str(ctmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(ctmp / "ws"))
mock = subprocess.Popen([sys.executable, str(ROOT / "tests/mock_llm.py"), str(MOCK)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(ROOT / "tests/silence90.wav"), "--null-audio"], env=env,
                        stdout=open(ctmp / "core.log", "w"), stderr=subprocess.STDOUT)
from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
try:
    for _ in range(150):
        time.sleep(0.2)
        if (ctmp / "cfg/token").exists():
            break
    time.sleep(2)
    for _ in range(3):                                   # окно проверяет порт: подключилось и сразу закрыло
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=1).close()
        except OSError:
            pass
    tok = (ctmp / "cfg/token").read_text().strip()
    import asyncio, websockets  # noqa: E402,E401

    async def pc_turn(q):
        ws = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None)
        await ws.send(json.dumps({"cmd": "hello", "token": tok})); ev = []

        async def reader():
            async for raw in ws:
                ev.append(json.loads(raw))
        rd = asyncio.ensure_future(reader()); await asyncio.sleep(1.5)
        await ws.send(json.dumps({"id": 1, "cmd": "say", "args": {"text": q}}))
        for _ in range(150):
            await asyncio.sleep(0.2)
            if any(e.get("type") == "answer" and e.get("done") for e in ev):
                break
        await asyncio.sleep(0.5); rd.cancel(); await ws.close()
        return ev
    ev = asyncio.run(pc_turn("слушай встреча с Ирой переносится на послезавтра на 12 напомни мне завтра в 9 утра"))
    rem = [e for e in ev if e.get("type") == "tool" and e.get("name") == "set_reminder" and e.get("status") == "done"]
    ans = next((e.get("text") for e in reversed(ev) if e.get("type") == "answer" and e.get("done")), "")
    ok(rem and "поставлен" in (rem[0].get("result") or "").lower(), f"компьютер: пообещала «напомню» — проверка заставила поставить напоминание: "
                                                             f"{[(e.get('result') or '')[:60] for e in rem]} | {ans[:120]}")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script(FAKE)
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?port={PORT}&token={tok}"); pg.wait_for_timeout(4000)
        pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")
        pg.evaluate("() => document.querySelector('nav button[data-p=\"brain\"]').click()"); pg.wait_for_timeout(400)
        pg.evaluate("() => document.querySelector('#wz [data-w=\"cloud\"]').click()"); pg.wait_for_timeout(300)
        opts = pg.evaluate("() => [...document.querySelectorAll('#ck-prov option')].map(o => o.value)")
        ok({"openrouter", "openai", "anthropic", "deepseek", "custom"} <= set(opts), f"сервисы: + DeepSeek и «Другой — по адресу»: {opts}")
        pg.select_option("#ck-prov", "custom"); pg.wait_for_timeout(150)
        ok(pg.is_visible("#ck-url"), "«Другой — по адресу» — поле адреса")
        pg.fill("#ck-url", f"http://127.0.0.1:{MOCK}"); pg.fill("#ck-key", "sk-test")
        pg.evaluate("() => { document.querySelectorAll('dialog[open]').forEach(d => d.close()); document.querySelector('#ck-go').click(); }")
        for _ in range(40):
            pg.wait_for_timeout(250)
            if "Готово" in (pg.inner_text("#w-done") or "") or "Не получилось" in pg.inner_text("#ck-res") or "Выберите модель" in pg.inner_text("#ck-res"):
                break
        # №882 (18.11): советовать нечего — сами ничего не запускаем: человек выбирает модель, проверяем только её
        ok("Выберите модель" in pg.inner_text("#ck-res") and "Готово" not in (pg.inner_text("#w-done") or ""),
           f"№882 свой сервис: ключ принят, модель выбирает человек — до выбора ни одного настоящего запроса: {pg.inner_text('#ck-res')}")
        pg.click("#ck-use")
        for _ in range(40):
            pg.wait_for_timeout(250)
            if "Готово" in (pg.inner_text("#w-done") or "") or "не ответила" in (pg.inner_text("#w-done") or ""):
                break
        prof = pg.evaluate("() => S.llm.profiles[S.llm.active]")
        ok(prof.get("base_url") == f"http://127.0.0.1:{MOCK}/v1" and prof.get("model") == "mock-qwen" and prof.get("api_key") == "sk-test"
           and "Готово" in pg.inner_text("#w-done"), f"«Подключить» работает: свой адрес без /v1 → /v1, модель из списка, проверка: "
                                                     f"{prof.get('base_url')} {prof.get('model')} | {pg.inner_text('#ck-res')} {pg.inner_text('#w-done')[:80]}")
        # «Подключить бесплатно» из «Dewiar.pro»
        pg.evaluate("() => document.querySelector('nav button[data-p=\"dewiar\"]') && document.querySelector('nav button[data-p=\"dewiar\"]').click()")
        pg.wait_for_timeout(400)
        pg.evaluate("() => document.querySelector('[data-free]').click()"); pg.wait_for_timeout(600)
        cur = pg.evaluate("() => (document.querySelector('nav button.cur') || {}).dataset.p")
        ok(cur == "brain", f"ссылка «Подключить бесплатно» ведёт в «Мозг» к плитке: {cur}")
        ok(not errs, f"студия без ошибок: {errs[:2]}")
        pg.close()

        # ---------- телефон ----------
        www = TMP / "www"; shutil.copytree(ROOT / "android/assets/www", www)
        for x in ("entities.js", "speechnorm.js", "skins.css", "skins.js"):
            shutil.copy(ROOT / "ui/assets" / x, www / x)
        (www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                        capture_output=True, text=True, check=True).stdout, encoding="utf-8")
        pg = b.new_page(viewport={"width": 320, "height": 700}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
        r = pg.evaluate("""async () => { const out = [], got = [];
          complaintSend = async (note) => { got.push(note); return { id: 93 }; };         // eslint-disable-line
          out.push((await bugQuick("передай разработчику приложения что")).say);
          out.push((await bugQuick("во вкладке рефералы кнопка пригласить перекрывает код")).say);
          out.push((await bugQuick("сообщи об ошибке: радио молчит")).say);
          return { out, got }; }""")
        ok("договорите" in r["out"][0] or "Что случилось" in r["out"][0], f"телефон: оборвалось — переспросила: {r['out'][0]}")
        ok(r["got"] == ["во вкладке рефералы кнопка пригласить перекрывает код", "радио молчит"], f"телефон: жалобы целиком: {r['got']}")
        box = pg.evaluate("""() => { const w = document.createElement('div'); w.style.padding = '16px'; w.innerHTML = '<div id="rf-body"></div>';
          document.body.prepend(w); refInfo = { code: "K7QX2M", invited: [], bonus: 1, days: 7, bonus_new: 1 }; refDraw(true);   // eslint-disable-line
          const a = document.querySelector('.rfcode').getBoundingClientRect(), s = document.querySelector('#rf-share').getBoundingClientRect(),
                c = document.querySelector('#rf-copy').getBoundingClientRect();
          const hit = (x, y) => !(x.right <= y.left || y.right <= x.left || x.bottom <= y.top || y.bottom <= x.top);
          return { share: hit(a, s), copy: hit(a, c), w: s.width }; }""")
        ok(not box["share"] and not box["copy"] and box["w"] > 200, f"«Рефералы» на узком экране: код не перекрыт кнопками: {box}")
        hc = pg.evaluate("""() => { D.handsState = () => ""; D.info = () => JSON.stringify({ sdk: 34, version: "0.6.67" });
          const h = handsCard(); const d = document.createElement('div'); d.id = 'hands-card'; d.innerHTML = h; document.body.appendChild(d);
          let opened = ""; D.openSettings = (w) => { opened = w; return true; }; wireHands(); document.querySelector('#hands-app').click();
          return { h, opened, off: HANDS_OFF }; }""")
        ok("Разрешить ограниченные настройки" in hc["h"] and hc["opened"] == "app" and "ограниченные настройки" in hc["off"],
           f"«Управлять приложениями» на Android 13+: шаг про серый Dewiar и кнопка «Страница Dewiar»: {hc['opened']}")
        rem = pg.evaluate("""async () => {
          Object.assign(S.llm, { kind: "openai", base_url: "https://dewiar.pro/dwrapp/cloud.php?p=", api_key: "dw-x", model: "chat", cloud: true });
          S.onboarded = true; window.resolveModel = async () => "chat";
          const NL = String.fromCharCode(10, 10), set = [];
          const realSet = D.alarmSet; D.alarmSet = (j) => { set.push(JSON.parse(j).title); return realSet ? realSet(j) : j; };
          const sse = (o) => "data: " + JSON.stringify(o) + NL;
          const PROMISE = "Понял, моя королева. Исправляю: встреча с Ирой — на вторник, 12:00. Напомню тебе в понедельник утром в 9:00.";
          let stubborn = false;
          window.http = async (m, u, o) => {
            if (!o.onChunk) return { status: 200, body: "{}" };
            const body = typeof o.body === "string" ? JSON.parse(o.body) : o.body, last = body.messages[body.messages.length - 1];
            let out;
            if (last.role === "tool") out = sse({ choices: [{ delta: { content: "Поставила." } }] });
            else if (/^ПРОВЕРКА: ты пообещал/.test(String(last.content)) && !stubborn)
              out = sse({ choices: [{ delta: { tool_calls: [{ index: 0, id: "c1", function: { name: "set_reminder", arguments: JSON.stringify({ text: "встреча с Ирой во вторник в 12", when: "завтра в 9:00" }) } }] } }] });
            else out = sse({ choices: [{ delta: { content: PROMISE } }] });
            o.onChunk(out + "data: [DONE]" + NL); return { status: 200, body: "" };
          };
          const wait = async () => { for (let i = 0; i < 300 && busy; i++) await new Promise(r => setTimeout(r, 30)); };
          await ask("исправь встреча с Ирой переносится на вторник на 12 и напомни мне в понедельник утром"); await wait();
          const a1 = set.slice();
          stubborn = true; set.length = 0;
          await ask("встреча с Ирой во вторник в 12 не забудь"); await wait();
          return { a1, a2: set.slice(), bot: document.querySelector("#bot").textContent };
        }""")
        ok(any("Ир" in x for x in rem["a1"]), f"телефон: «напомню тебе в понедельник» без напоминания — проверка, и оно поставлено: {rem['a1']}")
        ok(not rem["a2"] and "Напоминание при этом не поставлено" in rem["bot"], f"телефон: так и не поставила — честно говорит, что напоминания нет: {rem['bot'][-120:]}")
        ph = pg.evaluate("""async () => { let shot = 0; window.takePhoto = async () => { shot++; return { ok: true, dataUrl: "data:," }; };
          turnAsk = "Я просто не расслышал ты сказала то что на Айфоне можно пользоваться Web версией";      // eslint-disable-line
          const r1 = await runTool("take_photo", { camera: "front" });
          turnAsk = "Сфотографируй и скажи, что передо мной";
          const r2 = await runTool("take_photo", { camera: "back" });
          return { r1: typeof r1 === "string" ? r1 : r1.text, shot }; }""")
        ok(ph["r1"].startswith("Снимок не сделан") and ph["shot"] == 1, f"телефон: камера только по просьбе (№92): {ph}")
        an = pg.evaluate("""async () => { turnAsk = "Патрик Запиши встречу с Ирой лечитской на следующую неделю на вторник на 12:00 и напомни мне за день";
          const before = notes().length; const r = await runTool("save_note", { title: "Понял, моя королева", text: "Понял, моя королева. Исправляю…" });
          return { r, added: notes().length - before }; }""")
        ok("set_reminder" in an["r"] and an["added"] == 0, f"телефон: встреча со временем — не заметка, а напоминание (№94): {an}")
        wv = pg.evaluate("""async () => { S.net.web_via = false; let e = ""; try { await dewiarWeb("search", "x"); } catch (x) { e = x.message; } S.net.web_via = true; return e; }""")
        ok("выключен" in wv, f"телефон: запасной путь через сервер Dewiar выключается (письмо 19.10): {wv}")
        lh = pg.evaluate("""async () => { const m = D.mock; D.mock = false; let e = ""; try { await probeServer("127.0.0.1:1234"); } catch (x) { e = x.message; } D.mock = m; return e; }""")
        ok("сам телефон" in lh, f"телефон: адрес 127.0.0.1 — объясняет, что это сам телефон, и как найти адрес компьютера: {lh[:90]}")
        pv = pg.evaluate("() => Object.keys(CLOUD)")
        ok("custom" in pv and "deepseek" in pv, f"телефон: «Другой — по адресу» и DeepSeek: {pv}")
        ok(not errs, f"телефон без ошибок: {errs[:2]}")
        b.close()
finally:
    core.terminate(); mock.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
log_ = (ctmp / "core.log").read_text(encoding="utf-8", errors="replace")
ok("opening handshake failed" not in log_, "проверка порта окном — не «сбой» в журнале (opening handshake failed)")
shutil.rmtree(TMP, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
