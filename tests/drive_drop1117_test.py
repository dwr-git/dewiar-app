"""Владелец 17.11, 21:19: «облачная флешка не работает — перетягиваю pdf и на вкладку возле „Пульта“, и в самой студии…
ничего не происходит». Зоны приёма брали только dataTransfer.files; когда система отдаёт окну не файл, а ссылку
file://… (Linux под Wayland, перетаскивание из браузера и некоторых файловых менеджеров), files пуст — и тишина.
Теперь: ссылки — путями в ядро (drive_add_path, ядро берёт файл с диска само); не дошло ничего — честная подсказка
«нажмите и выберите». Облако выключено — в блокноте сказано, что файл сохранён здесь и уйдёт после включения.
Настоящие ui/pad.html + padcloud.js и ui/settings.html + studio/drive.js в Chromium, ядро — подмена."""
import json, os, re, sys, tempfile, urllib.parse as up
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
_tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(_tmp / "cfg"), DEWIAR_STATE_DIR=str(_tmp / "st"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from playwright.sync_api import sync_playwright  # noqa: E402

ON = {"why": "", "used": 0, "quota": 209715200, "busy": "", "files": []}
CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
  core.connected = true; window.calls = []; window.ST = %s;
  core.call = async (c, a) => { calls.push([c, a]); if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
    if (c === "pad_read") return { name: a.name, text: "", mtime: 1 }; if (c === "drive_status") return ST; if (c === "pult_data") return {};
    return { files: [] }; };
  setTimeout(() => core.emit("hello", { settings: { ui: { skin: "brand", pult_seen: true }, features: {} } }), 200); }; ready(); })();"""
# бросить на элемент: kind = "file" (настоящий файл) | "uri" (только ссылки file://…) | "none" (ничего пригодного)
DROP = """([sel, kind]) => { const el = document.querySelector(sel); const dt = new DataTransfer();
  if (kind === "file") dt.items.add(new File(["%PDF-1.4"], "Договор.pdf", { type: "application/pdf" }));
  if (kind === "uri") dt.setData("text/uri-list", "# из файлового менеджера\\r\\nfile:///home/u/%D0%94%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D1%8B/%D0%A1%D1%87%D1%91%D1%82%201.pdf\\r\\nfile:///C:/Users/u/plan.docx");
  if (kind === "none") dt.setData("text/plain", "просто текст");
  const r = el.getBoundingClientRect(), o = { bubbles: true, cancelable: true, dataTransfer: dt, clientX: r.x + 4, clientY: r.y + 4 };
  for (const t of ["dragenter", "dragover", "drop"]) el.dispatchEvent(new DragEvent(t, o)); }"""
adds = lambda pg: pg.evaluate("calls.filter(c => c[0] === 'knowledge_add' || c[0] === 'drive_add_path').map(c => [c[0], c[1].name || c[1].path])")  # noqa: E731

with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    # блокнот у виджета: вкладка-облачко и зона в открытом облаке
    pg = b.new_page(viewport={"width": 460, "height": 640})
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.route(re.compile(r"^https?://"), lambda q: q.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.add_init_script(CORE % json.dumps(ON))
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=brand&cfg=" + up.quote(json.dumps({"side": "left", "gap": 14, "clips": []})))
    pg.wait_for_timeout(900)
    pg.evaluate(DROP, ["#cl-tab", "file"]); pg.wait_for_timeout(500)
    ok(pg.is_visible("#cloud") and adds(pg) == [["knowledge_add", "Договор.pdf"]], f"файл на вкладку-облачко — облако открылось, файл ушёл: {adds(pg)}")
    pg.evaluate("calls.length = 0"); pg.evaluate(DROP, ["#cl-drop", "uri"]); pg.wait_for_timeout(500)
    ok(adds(pg) == [["drive_add_path", "/home/u/Документы/Счёт 1.pdf"], ["drive_add_path", "C:/Users/u/plan.docx"]],
       f"система отдала только ссылки file:// — пути в ядро (кириллица, пробел, диск Windows): {adds(pg)}")
    ok("в облаке" in pg.inner_text("#cl-say"), f"и сказано, что файл в облаке: {pg.inner_text('#cl-say')}")
    # 1.0.26 (владелец 22:05, Ubuntu: «перетягиваю — ничего»): страница файла не получила, а окно GTK его видело — отдаёт путями
    pg.wait_for_timeout(3100)                                  # прошлое «положили» — давно
    pg.evaluate("calls.length = 0"); pg.evaluate(DROP, ["#cl-drop", "none"]); pg.wait_for_timeout(300)
    pg.evaluate("() => dwNativeDrop(['/home/u/Загрузки/Договор аренды.pdf'])"); pg.wait_for_timeout(1700)
    ok(adds(pg) == [["drive_add_path", "/home/u/Загрузки/Договор аренды.pdf"]] and "не дошёл" not in pg.inner_text("#cl-say"),
       f"страница файла не получила — его отдало окно (GTK), файл в облаке, без подсказки «не дошёл»: {adds(pg)} | {pg.inner_text('#cl-say')}")
    pg.evaluate("calls.length = 0"); pg.evaluate(DROP, ["#cl-drop", "file"]); pg.wait_for_timeout(200)
    pg.evaluate("() => dwNativeDrop(['/tmp/Договор.pdf'])"); pg.wait_for_timeout(400)
    ok(adds(pg) == [["knowledge_add", "Договор.pdf"]], f"страница файл приняла — окно второй раз не кладёт: {adds(pg)}")
    pg.wait_for_timeout(3100)
    pg.evaluate("calls.length = 0"); pg.evaluate(DROP, ["#cl-drop", "none"]); pg.wait_for_timeout(1900)
    ok(not adds(pg) and "нажмите" in pg.inner_text("#cl-say"), f"не дошло ничего — не тишина, а подсказка: {pg.inner_text('#cl-say')}")
    ok(pg.evaluate("calls.some(c => c[0] === 'js_errors' && /drop without a file, got: text\\/plain/.test(c[1].errors[0]))"),
       "и в журнал — что пришло вместо файла (для разбора на Windows)")
    PASTE = """() => { const dt = new DataTransfer(); dt.items.add(new File(["%PDF"], "Скан.pdf", { type: "application/pdf" }));
      document.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true })); }"""
    pg.evaluate("calls.length = 0"); pg.evaluate(PASTE); pg.wait_for_timeout(400)
    ok(adds(pg) == [["knowledge_add", "Скан.pdf"]], f"Ctrl+V файла, скопированного в проводнике, — в облако: {adds(pg)}")
    # облако выключено (нет шифрования): зона приёма скрыта — сказано в видимом месте
    pg.evaluate("() => { ST = Object.assign({}, ST, { why: 'e2e' }); calls.length = 0; }")
    pg.click("#pt-tab"); pg.wait_for_timeout(200); pg.evaluate(DROP, ["#cl-tab", "file"]); pg.wait_for_timeout(600)
    ok(adds(pg) == [["knowledge_add", "Договор.pdf"]] and pg.evaluate("calls.findIndex(c => c[0] === 'sync_e2e' && c[1].on) < calls.findIndex(c => c[0] === 'knowledge_add')")
       and pg.evaluate("calls.some(c => c[0] === 'sync_e2e')"),
       "облако выключено, а файл положили — облако включается само (22:05, владелец: «пусть включается само»), потом файл")
    # 21:25 (снимок владельца): выключенное облако было пустым экраном с текстом — теперь поле приёма на месте и одна кнопка
    ok(pg.is_visible("#cl-drop") and pg.inner_text("#cl-on") == "Включить", "выключено: поле приёма видно, кнопка «Включить» — прямо здесь")
    pg.evaluate("calls.length = 0"); pg.click("#cl-on"); pg.wait_for_timeout(300)
    ok(pg.evaluate("calls.some(c => c[0] === 'sync_e2e' && c[1].on === true)"), "«Включить» включает облако (как кнопка в студии)")
    pg.evaluate("() => { ST = Object.assign({}, ST, { why: '', files: [] }); }"); pg.click("#pt-tab"); pg.click("#cl-tab"); pg.wait_for_timeout(400)
    box = pg.evaluate("(() => { const r = document.querySelector('#cl-drop').getBoundingClientRect(); return [r.height, document.querySelector('#cloud').classList.contains('empty')]; })()")
    ok(box[1] and box[0] > 180 and pg.is_visible(".cl-why"), f"пусто — поле приёма крупное, во всю высоту, с пояснением: {box}")
    ok(pg.inner_text("#cl-used-n") == "0 МБ" and pg.inner_text("#cl-used-q") == "из 200 МБ", f"пустое облако — «0 МБ», а не «1 КБ»: {pg.inner_text('#cl-used')}")
    ok(not pg.query_selector(".cl-bar"), "вместо серой полосы — кольцо места вокруг облачка")
    pg.close()

    # студия → «Мои файлы» → карточка облака
    pg = b.new_page(viewport={"width": 1300, "height": 900})
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.route(re.compile(r"^https?://"), lambda q: q.abort())
    pg.add_init_script(CORE % json.dumps(ON))
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); cldRender(ST); }")
    pg.evaluate(DROP, ["#ld-drop", "file"]); pg.wait_for_timeout(500)
    ok(adds(pg) == [["knowledge_add", "Договор.pdf"]], f"студия: файл в зону — в облако: {adds(pg)}")
    pg.evaluate("calls.length = 0"); pg.evaluate(DROP, ["#ld-drop", "uri"]); pg.wait_for_timeout(500)
    ok(adds(pg) == [["drive_add_path", "/home/u/Документы/Счёт 1.pdf"], ["drive_add_path", "C:/Users/u/plan.docx"]],
       f"студия: только ссылки — пути в ядро: {adds(pg)}")
    pg.evaluate("() => { document.querySelectorAll('.page').forEach(x => x.classList.remove('cur')); document.querySelector('#p-docs').classList.add('cur'); }")
    pg.wait_for_timeout(3100)
    pg.evaluate("calls.length = 0"); pg.evaluate(DROP, ["#ld-drop", "none"]); pg.wait_for_timeout(300)
    pg.evaluate("() => dwNativeDrop(['/home/u/Счёт.pdf'])"); pg.wait_for_timeout(500)
    ok(adds(pg) == [["drive_add_path", "/home/u/Счёт.pdf"]], f"студия: файл отдало окно (GTK) — в облако: {adds(pg)}")
    pg.wait_for_timeout(3100)
    pg.evaluate("calls.length = 0"); pg.evaluate(DROP, ["#ld-drop", "none"]); pg.wait_for_timeout(1900)
    ok(not adds(pg) and "нажмите" in pg.inner_text("#toast"), f"студия: не дошло — подсказка: {pg.inner_text('#toast')}")
    pg.evaluate("calls.length = 0"); pg.evaluate(DROP, ["#ld-grid", "file"]); pg.wait_for_timeout(500)
    ok(adds(pg) == [["knowledge_add", "Договор.pdf"]], f"студия: бросили мимо пунктира, на плитки, — тоже в облако: {adds(pg)}")
    pg.evaluate("() => { document.querySelectorAll('.page').forEach(x => x.classList.remove('cur')); document.querySelector('#p-docs').classList.add('cur'); calls.length = 0; }")
    pg.evaluate(PASTE); pg.wait_for_timeout(400)
    ok(adds(pg) == [["knowledge_add", "Скан.pdf"]], f"студия: Ctrl+V файла на «Моих файлах» — в облако: {adds(pg)}")
    # 21:42 (снимок владельца): «Попробуйте спросить» наезжала на карточку «Сегодня написано» (у неё было margin-top: -6px),
    # а сама карточка без данных ядра показывала «0 слов» с полной полосой
    pg.evaluate("() => { document.querySelectorAll('.page').forEach(x => x.classList.remove('cur')); document.querySelector('#p-docs').classList.add('cur'); }")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#wr-card').hidden"), "«Пишу» без ответа ядра не показывается пустой разметкой")
    pg.evaluate("() => { WR.d = { files: 2, today: 40, goal: 0, days: [], week: 40, total: 900, touched: [] }; wrRender(); }")
    gap = pg.evaluate("(() => { const a = document.querySelector('#dc-try').getBoundingClientRect(), c = document.querySelector('#wr-card').getBoundingClientRect(); return c.top - a.bottom; })()")
    ok(gap >= 12, f"кнопки «Попробуйте спросить» не наезжают на карточку «Пишу»: зазор {gap:.0f}px")
    pg.close()
    # 22:04 (владелец): «Всё облако — в студии» из блокнота открывало «Мои файлы» пустыми — раздел нажимался до связи с ядром
    import copy, settings as SET  # noqa: E401
    SS = copy.deepcopy(SET.DEFAULTS); SS["llm"]["active"] = "d"; SS["llm"]["profiles"] = {"d": {"cloud": True, "name": "Dewiar"}}
    HELLO = (CORE % json.dumps(ON)).replace("core.call = async", "setTimeout(() => core.emit('hello', { settings: %s, personas: [], persona: 'lira', presets: {}, piper_voices: [], voice_fx: [] }), 700); core.call = async" % json.dumps(SS))
    pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda q: q.abort()); pg.add_init_script(HELLO)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1#docs"); pg.wait_for_timeout(1800)
    ok(pg.evaluate("document.querySelector('#p-docs').classList.contains('cur')") and pg.evaluate("calls.some(c => c[0] === 'knowledge_list') && calls.some(c => c[0] === 'drive_status')"),
       f"студия, открытая сразу на «Моих файлах», после связи с ядром грузит файлы и облако: {pg.evaluate('calls.map(c => c[0]).slice(0, 12)')}")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()

sys.path.insert(0, str(ROOT / "ui"))
import app as UI  # noqa: E402
ok(UI.Api.drop_paths(["file:///home/u/%D0%A1%D1%87%D1%91%D1%82%201.pdf", "https://x.ru/a.pdf", "file:///home/u/%D0%A1%D1%87%D1%91%D1%82%201.pdf", "# коммент"])
   == ["/home/u/Счёт 1.pdf"], "окно: адреса file:// — пути (кириллица, пробел), чужие и повторы — мимо")
asrc = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('wv.connect("drag-data-received", on_data)' in asrc and 'wv.connect("drag-drop", on_drop)' in asrc and "_drop_hook(PAD_TITLE, win)" in asrc
   and "_drop_hook(STUDIO_TITLE, win)" in asrc, "окно блокнота и студии на Linux слушают перетаскивание сами (GTK)")
src = (ROOT / "core/commands_sync.py").read_text(encoding="utf-8")
ok('if cmd == "drive_add_path":' in src and "src.is_file()" in src and "FILE_MAX" in src, "ядро берёт файл по пути само и проверяет вид и размер")
print("\nИТОГ: " + ("всё прошло" if not fails else f"не прошло {len(fails)}"))
sys.exit(1 if fails else 0)
