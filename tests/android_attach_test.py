"""Телефон по отзывам первых людей (10.10): понятное подключение «мозга» при первом запуске; фото и файлы — показать
Лире (скрепка у поля ввода); длинный ответ — в рамке с «Копировать», «В заметки», «Скачать»; «сохранила заметкой»
без save_note — не верим, просим сделать по-настоящему. Страница приложения в Chromium, модель — заглушка."""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request
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
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


LLM = free()
tmp = Path(tempfile.mkdtemp())
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
(www / "radio.js").write_text("window.RADIO_LIST = " + (ROOT / "data/radio.json").read_text(encoding="utf-8") + ";", encoding="utf-8")
log = tmp / "llm.jsonl"
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG_FULL=str(log)))
time.sleep(1)
from PIL import Image  # noqa: E402
Image.new("RGB", (2400, 1600), (40, 120, 200)).save(tmp / "photo.jpg")
(tmp / "list.txt").write_text("Молоко\nХлеб\nЯблоки", encoding="utf-8")
(tmp / "doc.pdf").write_bytes(b"%PDF-1.4 test")


def proxy(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    try:
        r = urllib.request.urlopen(urllib.request.Request(req.url, data=req.post_data_buffer, method=req.method,
                                                          headers={"Content-Type": "application/json"}), timeout=20)
        body, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "application/json")
    except urllib.error.HTTPError as e:
        body, status, ctype = e.read(), e.code, "application/json"
    route.fulfill(status=status, body=body, headers={"Access-Control-Allow-Origin": "*", "Content-Type": ctype})


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 393, "height": 820})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(f"http://127.0.0.1:{LLM}/**", proxy)
        pg.route("https://**", lambda r: r.abort())
        pg.goto((www / "index.html").as_uri())
        pg.wait_for_timeout(900)

        # первый запуск: одна главная кнопка — бесплатно; остальное — второй кнопкой
        first = pg.evaluate("() => [...document.querySelectorAll('#card .start button')].map(b => b.textContent)")
        # 23.10 (№216): второе устройство — код, а не вторая заявка
        ok(first == ["Подключить мозг Dewiar", "Dewiar уже есть на компьютере — ввести код", "Свой ключ или своя модель"], f"первый запуск — понятные кнопки: {first}")
        ok("подключить" in pg.evaluate("document.querySelector('#bot').textContent") and "Ollama" not in pg.content().split('id="sheet')[0],
           "приветствие простыми словами, без названий моделей")
        pg.evaluate("openBrain()"); pg.wait_for_timeout(400)
        tiles = pg.evaluate("() => [...document.querySelectorAll('.tiles > .tile')].map(t => [t.querySelector('b').textContent, !!t.closest('details.pro')])")
        ok(tiles[0] == ["Подключить мозг Dewiar", False] and all(pro for n, pro in tiles if n in ("Своя модель", "Ключ любимого сервиса")),
           f"в выборе мозга — сначала бесплатно, своя модель и ключи — в «Для опытных»: {tiles}")
        ok(not pg.evaluate("() => [...document.querySelectorAll('.card, .tile')].some(e => getComputedStyle(e).borderTopWidth !== '0px')"),
           "карточки и плитки — без рамок (стекло и тень)")
        pg.evaluate("closeSheets()")
        pg.evaluate(f"""() => {{ Object.assign(S.llm, {{ kind: "openai", base_url: "http://127.0.0.1:{LLM}/v1", model: "chat", name: "тест" }}); saveS(); }}""")

        # фото и файлы
        pg.click("#b-kb")
        ok(pg.evaluate("document.body.classList.contains('typing')"), "поле ввода открыто — сцена выше него")
        pg.set_input_files("#att-file", [str(tmp / "photo.jpg"), str(tmp / "list.txt"), str(tmp / "doc.pdf")])
        pg.wait_for_timeout(800)
        chips = pg.evaluate("() => [...document.querySelectorAll('#atts .at')].map(a => a.querySelector('img') ? 'img' : a.textContent)")
        tst = pg.evaluate("document.querySelector('#toast').textContent")
        ok(chips == ["img", "list.txt"] and "PDF" in tst, f"фото миниатюрой и текстовый файл названием; PDF — честное «не читаю»: {chips} / {tst}")
        pg.fill("#typed", "Что на фото и что в списке?")
        pg.click("#send")
        for _ in range(40):
            pg.wait_for_timeout(250)
            if pg.evaluate("state") == "idle" and pg.evaluate("document.querySelector('#bot').textContent"):
                break
        bot = pg.evaluate("document.querySelector('#bot').textContent")
        reqs = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
        last = reqs[-1]["messages"][-1]["content"] if reqs else ""
        img = next((x["image_url"]["url"] for x in last if x.get("type") == "image_url"), "") if isinstance(last, list) else ""
        txt = " ".join(x.get("text", "") for x in last if x.get("type") == "text") if isinstance(last, list) else str(last)
        ok(img.startswith("data:image/jpeg") and "Молоко" in txt and "list.txt" in txt and "Что на фото" in txt,
           f"модели ушли вопрос, фото и текст файла: {txt[:90]!r}")
        import base64, io
        im = Image.open(io.BytesIO(base64.b64decode(img.split(",", 1)[1]))) if img else None
        ok(im is not None and max(im.size) == 1280, f"фото уменьшено до 1280 точек: {im and im.size}")
        ok("Вижу картинку 1280x853" in bot, f"ответ про фото: {bot[:80]}")
        ok(pg.evaluate("document.querySelectorAll('#card .attshow img').length") == 1, "присланное фото видно на экране")
        h = pg.evaluate("history.filter(m => m.role === 'user').slice(-1)[0].content")
        ok("[приложено: фото, файл «list.txt»]" in h and "base64" not in h, f"в истории — пометка, а не сами данные: {h}")
        ok(pg.evaluate("document.querySelectorAll('#atts .at').length") == 0, "после отправки вложения убраны")

        # длинный ответ — в рамке с кнопками
        pg.evaluate("""() => { showBot('Собрала список:\\n\\n| Курс | Цена |\\n|---|---|\\n| Belhard | 950 BYN |\\n\\n- новичкам\\n- без кода'); frameAnswer(document.querySelector('#bot').textContent); }""")
        fr = pg.evaluate("""() => ({ cls: document.querySelector('#bot').className, long: document.querySelector('#stage').classList.contains('long'),
            th: [...document.querySelectorAll('#bot th')].map(x => x.textContent), li: document.querySelectorAll('#bot li').length,
            acts: [...document.querySelectorAll('#bot .acts button')].map(x => x.textContent) })""")
        ok(fr["cls"] == "framed" and fr["long"] and fr["th"] == ["Курс", "Цена"] and fr["li"] == 2, f"рамка, таблица и пункты, облик меньше: {fr}")
        ok(fr["acts"] == ["Копировать", "В заметки", "Скачать"], f"кнопки: {fr['acts']}")
        pg.click("#bot .acts button[data-a=copy]"); pg.wait_for_timeout(200)
        ok("Belhard" in (pg.evaluate("window._copied") or ""), "«Копировать» — в буфер обмена")
        n0 = pg.evaluate("notes().length")
        pg.click("#bot .acts button[data-a=note]"); pg.wait_for_timeout(200)
        ok(pg.evaluate("notes().length") == n0 + 1 and "Belhard" in pg.evaluate("notes().slice(-1)[0].text"), "«В заметки» — заметка появилась")
        pg.click("#bot .acts button[data-a=save]"); pg.wait_for_timeout(200)
        dl = pg.evaluate("window._downloads || []")
        ok(dl and dl[-1][0].endswith(".md") and "Belhard" in dl[-1][1], f"«Скачать» — файл в «Загрузки/Dewiar»: {dl and dl[-1][0]}")
        pg.evaluate("showBot('Коротко.')")
        ok(pg.evaluate("document.querySelector('#bot').className") == "" and not pg.evaluate("document.querySelector('#stage').classList.contains('long')"),
           "короткий ответ — как раньше, без рамки")

        # «сохранила заметкой» без save_note — просим сделать по-настоящему
        c = pg.evaluate("t => { const x = claimedAction(t, new Set(['find_notes']), 'сохрани список'); return x && x.tool; }", "Теперь она точно в твоих заметках.")
        c2 = pg.evaluate("t => { const x = claimedAction(t, new Set(['save_note']), 'сохрани'); return x && x.tool; }", "Сохранила её заметкой.")
        c3 = pg.evaluate("t => { const x = claimedAction(t, new Set(['find_notes']), 'где заметка'); return x && x.tool; }", "Я проверила твои заметки и не нашла такого списка.")
        ok(c == "save_note" and c2 is None and c3 is None, f"«сохранила» без save_note — не верим; с ним или «не нашла» — верим: {c}, {c2}, {c3}")
        ok("СПИСКИ И ТЕКСТЫ" in pg.evaluate("systemPrompt()"), "правило: список — прямо в ответе, заметка — только по просьбе")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    mock.terminate()
src = (ROOT / "android/src/pro/dewiar/app/MainActivity.java").read_text(encoding="utf-8")
ok("EXTRA_ALLOW_MULTIPLE" in src and "getAcceptTypes" in src and "getClipData" in src, "Android: выбор фото и файлов, несколько сразу")
ok("public boolean copy(" in (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8"), "Android: копирование в буфер")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
