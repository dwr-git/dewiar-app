"""Студия → «Чат» (просьба 14.10: «на компьютере не понятно, где наша с Лирой переписка — на телефоне есть; вместо значка
памяти — чат, и чтобы можно было писать»). Настоящее ядро и модель-заглушка:
— вопрос, заданный как угодно (здесь — командой say, как из виджета), и ответ попадают в ленту (core/chatlog.py, событие chat);
— в студии: написал в поле и Enter — свой пузырь справа, ответ персонажа слева с его именем; разделитель «Сегодня»;
— переписка переживает перезапуск ядра; «Показать раньше» подгружает старые; «Очистить» — пусто;
— вложения (просьба 14.10): фото и файлы скрепкой — миниатюра и плашка в ленте, файлы во «Входящих», модель их видит;
  картинка из виджета без текста — только миниатюра;
— в виджете вместо «Памяти» — «Чат», он открывает студию на «Чате»; без ошибок JavaScript."""
import json, os, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        q = next((m["content"] for m in reversed(body["messages"]) if m["role"] == "user" and isinstance(m["content"], str)), "")
        q = q.split("(Сообщение пользователя)\n")[-1]          # справка к сообщению (время, найденное) — не сам вопрос
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for part in ("Отвечаю ", "на «" + q[:60] + "»."):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': part}}]}, ensure_ascii=False)}\n\n".encode()); time.sleep(0.2)
        self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


UP, PORT = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = Path(tempfile.mkdtemp()); (tmp / "cfg").mkdir()
base = f"http://127.0.0.1:{UP}/v1"
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done", "welcome": "done", "news_seen": "99.0.0"},
    "report": {"pulse": False}, "team": {"route": False}, "tools": {"enabled_all": False},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")


def start_core():
    c = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                         stdout=open(tmp / "core.log", "a"), stderr=subprocess.STDOUT)
    for _ in range(150):
        time.sleep(0.2)
        if (tmp / "cfg/token").exists():
            break
    time.sleep(2.5)
    return c


errs = []
core = start_core()
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 900})
        pg.on("pageerror", lambda x: errs.append(str(x)))
        url = (ROOT / "ui/settings.html").as_uri() + f"?token={(tmp / 'cfg/token').read_text().strip()}&port={PORT}#chat"
        pg.goto(url); pg.wait_for_timeout(2500)
        ok(pg.evaluate("() => document.getElementById('p-chat').classList.contains('cur')") and pg.is_visible("#ch-empty"),
           "студия открылась на «Чате» (адрес #chat); переписки нет — подсказка")
        pg.fill("#ch-text", "Как дела у Лиры?"); pg.press("#ch-text", "Enter")
        pg.wait_for_selector(".cl-m:not(.out) >> text=Отвечаю", timeout=20000); pg.wait_for_timeout(600)
        R = pg.evaluate("""() => ({ msgs: [...document.querySelectorAll('#ch-msgs .cl-m')].map(m => [m.classList.contains('out'), m.querySelector('.tx').textContent.trim()]),
                                    who: [...document.querySelectorAll('#ch-msgs .ch-who')].map(x => x.textContent.trim()),
                                    day: [...document.querySelectorAll('#ch-msgs .ch-day')].map(x => x.textContent.trim()),
                                    live: !!document.querySelector('.ch-live'), field: document.getElementById('ch-text').value })""")
        ok(R["msgs"][:1] == [[True, "Как дела у Лиры?"]] and R["msgs"][-1][0] is False and "Отвечаю на «Как дела у Лиры?»" in R["msgs"][-1][1],
           f"написал — свой пузырь справа, ответ слева: {R['msgs']}")
        ok(R["who"] == ["Лира"] and R["day"] == ["Сегодня"] and not R["live"] and R["field"] == "", f"имя персонажа над ответом, «Сегодня», поле очищено: {R}")
        # вопрос из виджета (команда say) тоже в ленте
        pg.evaluate("() => core.call('say', { text: 'Второй вопрос' })"); pg.wait_for_timeout(3500)
        n2 = pg.evaluate("() => document.querySelectorAll('#ch-msgs .cl-m').length")
        ok(n2 == 4, f"вопрос из виджета и ответ — тоже в ленте: {n2}")
        # вложения: фото и текстовый файл — скрепкой
        from PIL import Image
        Image.new("RGB", (900, 600), (40, 120, 200)).save(tmp / "фото.png")
        (tmp / "заметка.txt").write_text("Купить молоко и хлеб.", encoding="utf-8")
        pg.set_input_files("#ch-file", [str(tmp / "фото.png"), str(tmp / "заметка.txt")]); pg.wait_for_timeout(700)
        chips = pg.evaluate("() => [...document.querySelectorAll('#ch-atts .ch-chip b')].map(x => x.textContent)")
        ok(chips == ["фото.jpg", "заметка.txt"], f"приложено — плашки над полем: {chips}")
        pg.fill("#ch-text", "Что на фото и в файле?"); pg.click("#ch-go")
        pg.wait_for_selector("#ch-msgs .ch-img img", timeout=15000); pg.wait_for_timeout(3500)
        A = pg.evaluate("""() => { const m = [...document.querySelectorAll('#ch-msgs .cl-m.out')].pop();
            return { img: !!m.querySelector('.ch-img img[src^="data:image/jpeg"]'), file: [...m.querySelectorAll('.cl-f span')].map(x => x.textContent),
                     text: (m.querySelector('.tx') || {}).textContent, chips: document.querySelectorAll('#ch-atts .ch-chip').length,
                     last: [...document.querySelectorAll('#ch-msgs .cl-m:not(.out) .tx')].pop().textContent }; }""")
        ok(A["img"] and A["file"] == ["заметка.txt"] and A["text"] == "Что на фото и в файле?" and A["chips"] == 0,
           f"в ленте — миниатюра фото, плашка файла и текст (без «Вложения:»): {A}")
        inbox = sorted(x.name for x in (tmp / "ws/Входящие").iterdir()) if (tmp / "ws/Входящие").is_dir() else []
        ok("фото.jpg" in inbox and "заметка.txt" in inbox and "Отвечаю" in A["last"], f"файлы — во «Входящих» папки ассистента, модель ответила: {inbox}")
        # только картинка из виджета (вставленная) — тоже в ленте, без текста
        pg.evaluate("() => core.call('say', { text: '', images: [document.querySelector('#ch-msgs .ch-img img').src] })"); pg.wait_for_timeout(3500)
        B = pg.evaluate("() => { const m = [...document.querySelectorAll('#ch-msgs .cl-m.out')].pop(); return [!!m.querySelector('.ch-img'), !!m.querySelector('.tx')]; }")
        ok(B == [True, False], f"картинка без текста — только миниатюра, без «Посмотри вложения…»: {B}")
        b.close()
    core.terminate(); core.wait(10)
    lines = (tmp / "st/chat.jsonl").read_text(encoding="utf-8").splitlines()
    ok(len(lines) == 8 and json.loads(lines[1])["who"] == "lira" and [a["name"] for a in json.loads(lines[4]).get("att", [])] == ["фото.jpg", "заметка.txt"],
       f"лента на диске (state/chat.jsonl): {len(lines)} реплик, у ответа — персонаж, у вопроса — вложения")
    # много старых реплик: подгрузка «раньше»
    old = [json.dumps({"id": f"o{i:04d}", "ts": time.time() - 86400 * 3 + i, "role": "user" if i % 2 == 0 else "assistant", "text": f"старое {i}", "who": None if i % 2 == 0 else "patrik"}, ensure_ascii=False)
           for i in range(150)]
    (tmp / "st/chat.jsonl").write_text("\n".join(old + lines) + "\n", encoding="utf-8")
    core = start_core()
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 900})
        pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.goto(url); pg.wait_for_timeout(2500)
        n = pg.evaluate("() => document.querySelectorAll('#ch-msgs .cl-m').length")
        ok(n == 80 and pg.is_visible("#ch-older") and "Как дела у Лиры?" in pg.inner_text("#ch-msgs") and pg.evaluate("() => !!document.querySelector('#ch-msgs .ch-img img')"),
           f"после перезапуска — последние 80 реплик и «Показать раньше»: {n}")
        pg.click("#ch-older"); pg.wait_for_timeout(600)
        n = pg.evaluate("() => document.querySelectorAll('#ch-msgs .cl-m').length")
        days = pg.evaluate("() => [...document.querySelectorAll('#ch-msgs .ch-day')].map(x => x.textContent.trim())")
        ok(n == 158 and not pg.is_visible("#ch-older") and len(days) == 2 and days[1] == "Сегодня" and "Патрик" in pg.inner_text("#ch-msgs"),
           f"«Показать раньше» — вся лента, разделитель дня, имя Патрика: {n} {days}")
        pg.click("#ch-th"); pg.wait_for_timeout(200)          # 0.86: «Очистить» — в окне «Беседы»
        pg.click("#ch-clear"); pg.wait_for_timeout(300)
        ok(pg.locator(".dwq").count() == 1 and pg.inner_text(".dwq .yes") == "Очистить" and "danger" in pg.get_attribute(".dwq .yes", "class"), "своё окно вопроса: «Очистить» красным, без адреса страницы")
        pg.click(".dwq .yes"); pg.wait_for_timeout(500)
        ok(pg.evaluate("() => document.querySelectorAll('#ch-msgs .cl-m').length") == 0 and pg.is_visible("#ch-empty"), "«Очистить» — пусто")
        # виджет: вместо «Памяти» — «Чат»
        opened = []
        pw = b.new_page(viewport={"width": 380, "height": 560})
        pw.on("pageerror", lambda x: errs.append(str(x)))
        pw.add_init_script("window.pywebview = { api: { open_settings: (p) => { window.__opened = p; return Promise.resolve(); }, get_pos: () => Promise.resolve([0, 0]) } };")
        pw.goto((ROOT / "ui/hud.html").as_uri() + f"?token=x&port=1"); pw.wait_for_timeout(600)
        has = pw.evaluate("() => [!!document.getElementById('b-chat'), !!document.getElementById('b-mem')]")
        pw.evaluate("() => document.getElementById('b-chat').click()"); pw.wait_for_timeout(200)
        opened = pw.evaluate("() => window.__opened")
        ok(has == [True, False] and opened == "chat", f"в виджете — «Чат» вместо «Памяти», открывает студию на «Чате»: {has} {opened}")
        b.close()
finally:
    core.terminate()
    srv.shutdown()
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
