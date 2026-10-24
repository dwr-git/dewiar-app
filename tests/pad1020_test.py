"""Блокнот у виджета (20.10: «вкладки как в Obsidian, одна всегда открыта; ссылки, разметка, картинки, таблицы, списки
с точками, номерами и галочками; правлю дома — на работе открыл, и там всё»).
Ядро (core/pad.py): вкладки — заметки «Заметки/Блокнот/*.md»; правка с двух устройств — ничего не теряется;
синхронизация не дописывает вкладке заголовок и сообщает открытому блокноту; картинки — с путём, другой компьютер
кладёт их туда же. Страница (ui/pad.html): Markdown туда-обратно без потерь, «- », «[] », «# » на лету, галочки,
вставка картинки и таблицы с сайта, сохранение само. Виджет: кнопка в углу; окно — рядом с карточкой."""
import base64, json, os, re, subprocess, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st")
os.environ["DEWIAR_WORKSPACE_DIR"] = str(tmp / "ws")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as ST  # noqa: E402
import workspace as W  # noqa: E402
import pad as PD  # noqa: E402

s = ST.Settings(tmp / "s.json")
ws = W.Workspace(s)
shared, events = [], []
P = PD.Pad(ws, s, emit=lambda *a, **k: events.append((a, k)), share=lambda rel, paths: shared.append((rel, paths)))
t = P.tabs()
ok([x["name"] for x in t["tabs"]] == ["Главное"] and (ws.ensure() / "Заметки/Блокнот/Главное.md").is_file(), "пусто — есть вкладка «Главное» (обычная заметка)")
r = P.new("Работа"); P.new("Ссылки")
ok([x["name"] for x in P.tabs()["tabs"]] == ["Главное", "Работа", "Ссылки"] and P.tabs()["active"] == "Ссылки", "новые вкладки — справа, открыта последняя")
P.order(["Ссылки", "Главное", "Работа"])
ok([x["name"] for x in P.tabs()["tabs"]] == ["Ссылки", "Главное", "Работа"], "порядок — как перетащили")
md = "# План\n\n- [ ] позвонить\n- [x] отправить счёт\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n"
w = P.write("Работа", md)
ok(P.read("Работа")["text"] == md, "текст сохраняется как есть (Markdown)")
time.sleep(1.1)
(ws.ensure() / "Заметки/Блокнот/Работа.md").write_text("правка с работы\n", encoding="utf-8")     # синхронизация принесла другой текст
w2 = P.write("Работа", md + "- [ ] ещё\n", base=w["mtime"])
names = [x["name"] for x in P.tabs()["tabs"]]
ok(w2.get("conflict") == "Работа (с другого устройства)" and "Работа (с другого устройства)" in names
   and P.read("Работа (с другого устройства)")["text"] == "правка с работы\n", f"правили на двух устройствах — их вариант отдельной вкладкой, ничего не потеряно: {w2}")
P.rename("Ссылки", "Ссылки: видео/ролики")
ok("Ссылки  видео ролики" in [x["name"] for x in P.tabs()["tabs"]] or "Ссылки видео ролики" in [x["name"] for x in P.tabs()["tabs"]],
   f"переименовать — знаки, запрещённые в именах файлов, убираются: {[x['name'] for x in P.tabs()['tabs']]}")
png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
a = P.attach("Главное", "скрин.png", "data:image/png;base64," + png)
ok(a["image"] and a["line"].startswith("![скрин](Вложения/") and (ws.ensure() / a["path"]).is_file() and a["path"].startswith("Заметки/Блокнот/Вложения/"),
   f"картинка — в «Блокнот/Вложения», строка Markdown: {a['line']}")
ok(shared and shared[-1] == ("Заметки/Блокнот/Главное.md", [a["path"]]), "и уходит своим устройствам")
ok(P.file(a["line"][a["line"].index("(") + 1:-1])["url"].startswith("data:image/png;base64,"), "показ картинки вкладки")
try:
    P.file("../../Память/Обо мне.md"); ok(False, "выйти из блокнота нельзя")
except (PD.PadError, W.WorkspaceError):
    ok(True, "выйти из блокнота нельзя")
n0 = len(P.tabs()["tabs"])
P.delete("Работа (с другого устройства)")
ok(len(P.tabs()["tabs"]) == n0 - 1, "удалить — в корзину")

# синхронизация: вкладке не дописывается «# заголовок», открытый блокнот узнаёт о правке
import sync as SY  # noqa: E402
host = types.SimpleNamespace(workspace=ws, emit=lambda *a, **k: events.append((a, k)))
sy = SY.Sync.__new__(SY.Sync); sy.host = host; sy.state = {"map": {}}
sy._apply_note("abc", {"title": "С работы", "folder": "Блокнот", "text": "- [ ] купить хлеб\n"}, False)
ok((ws.ensure() / "Заметки/Блокнот/С работы.md").read_text(encoding="utf-8") == "- [ ] купить хлеб\n", "вкладка с другого устройства — как есть, без «# заголовка»")
ok(any(a[0] == "pad_changed" and k.get("name") == "С работы" for a, k in events), "открытый блокнот узнаёт о правке (pad_changed)")
sy._apply_note("abd", {"title": "Идея", "folder": "", "text": "текст"}, False)
ok((ws.ensure() / "Заметки/Идея.md").read_text(encoding="utf-8").startswith("# Идея"), "обычные заметки — с заголовком, как раньше")

# картинки между компьютерами: файл с путём кладётся туда же
import close as CL  # noqa: E402
c = CL.Close.__new__(CL.Close); c.host = host
ok(c._natt_rel("Заметки/Блокнот/Вложения/новый.png") == "Заметки/Блокнот/Вложения/новый.png", "картинки ещё нет — положим по тому же пути")
ok(c._natt_rel(a["path"]) == "" and c._natt_rel("../x.png") == "" and c._natt_rel("Память/Обо мне.md") == "", "уже есть / вне «Заметок» — нет")
src = (ROOT / "core/close.py").read_text(encoding="utf-8")
ok('"rel": str(rel)' in src and "self._natt_rel(f.get(\"rel\"))" in src, "компьютер отправляет путь файла, другой компьютер его принимает")

# команды ядра и окно
ec = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok(all(f'cmd == "{c}"' in ec for c in ("pad_tabs", "pad_read", "pad_write", "pad_new", "pad_rename", "pad_delete", "pad_order", "pad_attach", "pad_file")), "команды pad_* в ядре")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("def pad_toggle" in app and "def pad_hide" in app and "self._pad_follow_at(x, y)" in app and "self.pad_hide()" in app,
   "окно блокнота: открыть/убрать, едет вместе с карточкой, прячется с виджетом")
# «крепления» (20.10: «соединить с виджетом условными крепежами»): форма окна — лист + две защёлки поперёк зазора
src_rects = app[app.index("def _shape_rects"):app.index("def shape_window")]
ns = {"TRANSPARENT": [True], "card_r": lambda: 28}
exec(src_rects, ns)
exec(app[app.index("def pad_rects"):app.index('PROMPTER_TITLE = "')], ns)
R = ns["pad_rects"]("left", 440, 520, 14, [(84, 16), (336, 16)], 22)
ok((440, 84, 14, 16) in R and (440, 336, 14, 16) in R and max(x + w for x, y, w, h in R) == 454 and min(x for x, y, w, h in R) == 0,
   "лист слева, защёлки — справа, до самой карточки")
R = ns["pad_rects"]("right", 440, 520, 14, [(84, 16)], 22)
ok((0, 84, 14, 16) in R and min(x for x, y, w, h in R if h > 16) == 14, "лист справа — защёлки слева, лист сдвинут на зазор")
ok("winshell.shape_rects" in app and "def shape_rects" in (ROOT / "ui/winshell.py").read_text(encoding="utf-8"), "Windows — та же форма (регион окна)")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('id="b-pad"' in hud and 'a.pad_toggle("notes")' in hud, "кнопка блокнота в углу виджета")
bar = re.search(r'<div id="bar">(.*?)</div>', hud, re.S).group(1)
ids = re.findall(r'id="(b-[a-z]+)"', bar)
ok(ids[-2:] == ["b-chat", "b-set"], f"чат — рядом с настройками: {ids}")

from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = """window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { (window.apiCalls = window.apiCalls || []).push(k); return Promise.resolve(true); } }) };"""
CORE = r"""
(() => { const tabs = { "Главное": "# Список дел\n\n- [ ] купить хлеб\n- [x] отправить счёт\n\nСсылка: https://youtu.be/lXRiHj9j9Pk\n" , "Работа": "" };
  window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: Object.keys(tabs).map(n => ({ name: n, mtime: 1 })), active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: tabs[a.name], mtime: 1 };
      if (c === "pad_write") { tabs[a.name] = a.text; return { mtime: 2 }; }
      if (c === "pad_attach") return { line: "![x](Вложения/x.png)", path: "Заметки/Блокнот/Вложения/x.png", image: true };
      if (c === "pad_file") return { url: "data:image/png;base64,iVBORw0KGgo=" };
      if (c === "pad_new") { tabs["Вкладка"] = ""; return { tabs: Object.keys(tabs).map(n => ({ name: n })), active: "Вкладка", created: "Вкладка" }; }
      return {}; }; };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 440, "height": 560}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + __import__("urllib.parse").parse.quote(json.dumps({"side": "left", "gap": 14, "clips": [[84, 16], [336, 16]]}))); pg.wait_for_timeout(1200)
    # Markdown туда-обратно
    cases = ["# Заголовок\n\nАбзац с **жирным**, *курсивом*, ~~зачёркнутым~~, ==выделением== и `кодом`.\nВторая строка абзаца.\n",
             "- один\n- два\n  - вложенный\n  - ещё\n- три\n",
             "1. первый\n2. второй\n",
             "- [ ] купить хлеб\n- [x] отправить счёт\n",
             "> цитата\n> в две строки\n",
             "| Имя | Телефон |\n| --- | --- |\n| Лира | 123 |\n| Патрик | 456 |\n",
             "```python\nprint('x')\n```\n",
             "Ссылки: [видео](https://youtu.be/lXRiHj9j9Pk) и https://dewiar.pro/dwrapp/\n",
             "![скрин](Вложения/скрин%201.png)\n",
             "---\n"]
    rt = pg.evaluate("(cs) => cs.map(c => PadMD.html2md(PadMD.md2html(c)))", cases)
    bad = [(c, r) for c, r in zip(cases, rt) if c != r]
    ok(not bad, f"Markdown → вид → Markdown без потерь (заголовки, списки, задачи, таблицы, код, ссылки, картинки): {bad[:2]}")
    st = pg.evaluate("() => ({ tabs: [...document.querySelectorAll('.tab span')].map(x => x.textContent), on: document.querySelector('.tab.on span').textContent, "
                     "h1: !!document.querySelector('#ed h1'), tasks: [...document.querySelectorAll('#ed li.task')].map(l => l.dataset.done), "
                     "link: document.querySelector('#ed a') && document.querySelector('#ed a').href, cls: document.body.className })")
    ok(st["tabs"] == ["Главное", "Работа"] and st["on"] == "Главное", f"вкладки и открытая: {st['tabs']}")
    ok(st["h1"] and st["tasks"] == ["0", "1"] and st["link"] == "https://youtu.be/lXRiHj9j9Pk", f"вкладка показана «как выглядит»: заголовок, задачи, живая ссылка: {st}")
    ok("skin-neusky" in st["cls"] and "light" in st["cls"] and "side-left" in st["cls"], f"тема виджета и сторона выезда: {st['cls']}")
    cl = pg.evaluate("[...document.querySelectorAll('.clip')].map(c => [c.style.top, getComputedStyle(c).right, getComputedStyle(c).opacity])")
    ok(len(cl) == 2 and cl[0][0] == "84px" and cl[0][1] == "0px" and cl[0][2] == "1", f"защёлки на месте и «щёлкнули» после выезда: {cl}")
    # галочка щелчком по квадратику
    box = pg.evaluate("(() => { const r = document.querySelector('#ed li.task').getBoundingClientRect(); return [r.left + 7, r.top + 11]; })()")
    pg.mouse.click(*box); pg.wait_for_timeout(1000)
    saved = [c for c in pg.evaluate("calls") if c[0] == "pad_write"]
    ok(saved and "- [x] купить хлеб" in saved[-1][1]["text"], f"щелчок по квадратику — задача сделана и сохранена: {saved[-1][1]['text'][:80] if saved else saved}")
    # Markdown на лету: «- », «[] », «# »
    pg.click(".tab:nth-child(2)"); pg.wait_for_timeout(400)          # пустая вкладка «Работа» — как в первый раз
    ok(pg.evaluate("document.querySelector('#ed').classList.contains('blank')"), "пустая вкладка — с подсказкой, как писать")
    pg.click("#ed"); pg.keyboard.type("[] "); pg.keyboard.type("позвонить маме"); pg.keyboard.press("Enter"); pg.keyboard.type("написать Пете")
    pg.wait_for_timeout(1000)
    last = [c for c in pg.evaluate("calls") if c[0] == "pad_write"][-1][1]["text"]
    ok(last == "- [ ] позвонить маме\n- [ ] написать Пете\n", f"«[] » — задача, Enter — следующая задача: {last!r}")
    pg.evaluate("() => { const ed = document.querySelector('#ed'); ed.innerHTML = '<p><br></p>'; const r = document.createRange(); r.setStart(ed.firstChild, 0); getSelection().removeAllRanges(); getSelection().addRange(r); ed.focus(); }")
    pg.keyboard.type("# Встреча"); pg.keyboard.press("Enter"); pg.keyboard.type("- пункт один"); pg.keyboard.press("Enter"); pg.keyboard.type("пункт два")
    pg.wait_for_timeout(1000)
    last = [c for c in pg.evaluate("calls") if c[0] == "pad_write"][-1][1]["text"]
    ok(last == "# Встреча\n\n- пункт один\n- пункт два\n", f"«# » — заголовок, «- » — список: {last!r}")
    # вставка таблицы с сайта и картинки
    pg.evaluate("""() => { const ed = document.querySelector('#ed'); ed.innerHTML = '<p><br></p>'; const r = document.createRange(); r.setStart(ed.firstChild, 0); getSelection().removeAllRanges(); getSelection().addRange(r); ed.focus();
        const dt = new DataTransfer(); dt.setData('text/html', '<meta charset=utf-8><table style="color:red"><tr><td><b>Курс</b></td><td>Цена</td></tr><tr><td>USD</td><td>3,2</td></tr></table>'); dt.setData('text/plain', 'Курс Цена');
        ed.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }""")
    pg.wait_for_timeout(1000)
    last = [c for c in pg.evaluate("calls") if c[0] == "pad_write"][-1][1]["text"]
    ok("| **Курс** | Цена |\n| --- | --- |\n| USD | 3,2 |\n" in last and "color" not in last, f"таблица с сайта — таблицей, без чужих стилей: {last!r}")
    pg.evaluate("""() => { const ed = document.querySelector('#ed'); const bin = atob('iVBORw0KGgo='); const u = Uint8Array.from(bin, c => c.charCodeAt(0));
        const dt = new DataTransfer(); dt.items.add(new File([u], 'image.png', { type: 'image/png' }));
        ed.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }""")
    pg.wait_for_timeout(1300)
    calls = pg.evaluate("calls")
    att = [c for c in calls if c[0] == "pad_attach"]
    last = [c for c in calls if c[0] == "pad_write"][-1][1]["text"]
    ok(att and att[-1][1]["name"] == "Работа" and att[-1][1]["b64"].startswith("data:image/png") and "](Вложения/x.png)" in last,
       f"Ctrl+V с картинкой — картинка во вкладке (в файле — ссылкой): {last[-80:]!r}")
    # новая вкладка, Esc — уезжает и прячется
    pg.click("#b-new"); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.querySelector('.tab.on input') !== null"), "новая вкладка — сразу переименовать")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100); pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    ok("pad_hide" in pg.evaluate("apiCalls || []") and pg.evaluate("document.querySelector('#wrap').classList.contains('away')"), "Esc — блокнот уезжает и прячется")
    pg.screenshot(path=str(tmp / "pad.png"))
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    # тёмная тема — снимок для глаза
    pg2 = b.new_page(viewport={"width": 440, "height": 560}); pg2.add_init_script(FAKE); pg2.add_init_script(CORE)
    pg2.goto((ROOT / "ui/pad.html").as_uri() + "?side=right&skin=neudusk"); pg2.wait_for_timeout(900)
    pg2.screenshot(path=str(tmp / "pad-dark.png"))
    b.close()
print("снимки:", tmp / "pad.png", tmp / "pad-dark.png")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
