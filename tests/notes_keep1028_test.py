"""«Заметки как Keep, только умнее» (0.58; 28.10, пользователь: «теги слева, цвет, закреплять заметки вверху, поиск —
визуально легко ориентироваться»; владелец: «полностью поддерживаю»).
Ядро: перенос из Google Keep (архив Takeout: метки, цвет, закреплённые, архив, списки дел, ссылки, картинки; удалённые —
нет; второй раз — без копий); метки, цвет, «закрепить», «в архив» — в шапку заметки (остальная шапка не трогается);
закреплённые — сверху; #метки из текста — тоже метки. Студия: фильтр над списком, «Закреплённые» сверху, вид плитками
с цветом и заметкой поверх, под названием — «Закрепить», «Цвет», метки, «В архив»; ссылка отдельной строкой — карточкой."""
import io, json, os, re, sys, tempfile, time, zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ["DEWIAR_WORKSPACE"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT / "core"))
import workspace  # noqa: E402
import keep_import  # noqa: E402
import linkmeta  # noqa: E402
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("Takeout/Keep/Эйнштейн.json", json.dumps({"title": "Эйнштейн", "textContent": "Теория относительности — 1905.", "color": "BROWN",
        "isPinned": True, "labels": [{"name": "наука"}, {"name": "история"}], "userEditedTimestampUsec": 1700000000000000}))
    z.writestr("Takeout/Keep/Покупки.json", json.dumps({"title": "Покупки", "listContent": [{"text": "молоко", "isChecked": True}, {"text": "хлеб", "isChecked": False}],
        "color": "DEFAULT", "labels": [{"name": "дом"}], "attachments": [{"filePath": "чек.png", "mimetype": "image/png"}]}))
    z.writestr("Takeout/Keep/чек.png", PNG)
    z.writestr("Takeout/Keep/Видео.json", json.dumps({"title": "", "textContent": "Посмотреть потом", "isArchived": True,
        "annotations": [{"source": "WEBLINK", "url": "https://youtu.be/dQw4w9WgXcQ", "title": "Мир рабов"}]}))
    z.writestr("Takeout/Keep/Старое.json", json.dumps({"title": "Удалённое", "textContent": "x", "isTrashed": True}))
    z.writestr("Takeout/Keep/Labels.txt", "наука\nдом")
zp = Path(tempfile.mkdtemp()) / "takeout.zip"; zp.write_bytes(buf.getvalue())
w = workspace.Workspace(None); w.ensure()
r = keep_import.import_keep(w, zp)
ok(r["added"] == 3 and r["trashed"] == 1 and not r["errors"], f"перенос из Keep: три заметки, удалённая — нет: {r}")
n = {x["title"]: x for x in w.notes()}
e = n["Эйнштейн"]
ok(e["tags"] == ["наука", "история"] and e["color"] == "BROWN" and e["pinned"] and e["folder"] == "Google Keep" and abs(e["mtime"] - 1.7e9) < 2,
   f"метки, цвет, закреплено и время правки — как в Keep: {e}")
ok(e["snippet"].startswith("Теория") and "source" not in e["snippet"], "в списке — текст, не служебная шапка")
b = n["Покупки"]
txt = w.safe(b["path"]).read_text(encoding="utf-8")
ok("- [x] молоко" in txt and "- [ ] хлеб" in txt and b["att"] == 1 and b["img"].endswith("чек.png") and b["color"] == "", "список дел — галочками, картинка — вложением; цвет «по умолчанию» — без цвета")
v = n["Посмотреть потом"]
ok(v["archived"] and "[Мир рабов](https://youtu.be/dQw4w9WgXcQ)" in w.safe(v["path"]).read_text(encoding="utf-8"), "архив Keep — в архиве; ссылка Keep — строкой")
ok(keep_import.import_keep(w, zp)["skipped"] == 3 and len(w.notes()) == 3, "второй раз тот же архив — без копий")
ok(w.notes()[0]["title"] == "Эйнштейн", "закреплённые — сверху")
# метки, цвет, закрепить — в шапку, остальное в шапке не трогается
w.note_meta(b["path"], {"pinned": True, "color": "teal", "tags": ["дом", "дача"]})
t2 = w.safe(b["path"]).read_text(encoding="utf-8")
m2, _ = workspace.note_front(t2)
ok(m2["source"] == "Google Keep" and m2["keep"] == "Покупки.json" and m2["tags"] == ["дом", "дача"] and m2["color"] == "TEAL" and m2["pinned"],
   f"«Закрепить», цвет, метки — в шапку; source и keep на месте: {m2}")
w.note_meta(b["path"], {"pinned": False, "color": ""})
m3, _ = workspace.note_front(w.safe(b["path"]).read_text(encoding="utf-8"))
ok(not m3["pinned"] and "color" not in m3 and m3["tags"] == ["дом", "дача"], "открепить, убрать цвет — метки остаются")
w.save_note("Идеи", "проект на #golang и #linux, ссылка https://x.com/#anchor")
ok([x for x in w.notes() if x["title"] == "Идеи"][0]["tags"] == ["golang", "linux"], "#метки из текста — тоже метки (как в Obsidian), «#» в ссылке — нет")
pg_ = '<html><head><meta property="og:title" content="Как я сделал Linux"><meta content="https://e.com/i.jpg" property="og:image"><title>x</title>'
ok(linkmeta._meta(pg_, "og:title") == "Как я сделал Linux" and linkmeta._meta(pg_, "og:image") == "https://e.com/i.jpg"
   and linkmeta.YT_RX.search("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3").group(1) == "dQw4w9WgXcQ", "ссылка: название, картинка; YouTube — по номеру ролика")
# «сохрани это видео» — заметка-карточка с меткой «интересное»
import tools as TL  # noqa: E402
class _LM:
    def get(self, url): return {"url": url, "site": "YouTube", "title": "Как я сделал свой Linux", "image": "", "video": True}
out = TL.t_save_link({"url": "https://youtu.be/dQw4w9WgXcQ", "summary": "Автор собирает дистрибутив с нуля.", "tags": ["linux"]}, {"workspace": w, "linkmeta": _LM()})
sl = [x for x in w.notes() if x["title"] == "Как я сделал свой Linux"]
ok(sl and sl[0]["tags"] == ["интересное", "linux"] and "Автор собирает" in w.safe(sl[0]["path"]).read_text(encoding="utf-8") and "видео" in out,
   f"«сохрани это видео и перескажи» — заметка с названием ролика, меткой «интересное» и пересказом: {out}")
ok("save_link" in TL.SAFE_CORE and "save_link" in TL.TOOLS, "save_link — среди безопасных умений")
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('cmd == "note_meta"' in src and 'cmd == "notes_import_keep"' in src and 'cmd == "link_meta"' in src, "ядро: note_meta, notes_import_keep, link_meta")

NOTES = [
    {"path": "Заметки/Google Keep/Эйнштейн.md", "title": "Эйнштейн", "mtime": time.time() - 50, "folder": "Google Keep", "snippet": "Теория относительности", "att": 0, "img": "",
     "tags": ["наука", "история"], "color": "BROWN", "pinned": True, "archived": False},
    {"path": "Заметки/Linux.md", "title": "Как я сделал Linux", "mtime": time.time() - 10, "folder": "", "snippet": "https://youtu.be/dQw4w9WgXcQ", "att": 0, "img": "",
     "tags": ["linux"], "color": "TEAL", "pinned": False, "archived": False},
    {"path": "Заметки/Покупки.md", "title": "Покупки", "mtime": time.time() - 5, "folder": "", "snippet": "молоко, хлеб", "att": 0, "img": "",
     "tags": ["дом"], "color": "", "pinned": False, "archived": False},
    {"path": "Заметки/Старое.md", "title": "Старое", "mtime": time.time() - 99999, "folder": "", "snippet": "в архиве", "att": 0, "img": "",
     "tags": [], "color": "", "pinned": False, "archived": True}]
FILES = {"Заметки/Linux.md": "---\ntags: [linux]\ncolor: TEAL\n---\n# Как я сделал Linux\n\nСмотреть:\n\nhttps://youtu.be/dQw4w9WgXcQ\n\nи ещё #ядро\n",
         "Заметки/Google Keep/Эйнштейн.md": "---\nsource: Google Keep\ntags: [наука, история]\ncolor: BROWN\npinned: true\n---\n\n# Эйнштейн\n\nТеория относительности.\n",
         "Заметки/Покупки.md": "# Покупки\n\nмолоко, хлеб\n", "Заметки/Старое.md": "---\narchived: true\n---\n# Старое\n\nв архиве\n"}
with sync_playwright() as p:
    b_ = p.chromium.launch(); errs = []
    pg = b_.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.fulfill(status=200, content_type="image/svg+xml",
             body='<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#c33"/></svg>'))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve('') }) }; try { localStorage.removeItem('nt_grid'); } catch (e) {}")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""([notes, files]) => { window._calls = []; window._notes = notes; window._files = files;
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'notes_list') return Promise.resolve(_notes);
        if (c === 'ws_read') return Promise.resolve({ path: a.path, text: _files[a.path] || '# x', mtime: Date.now() / 1000 });
        if (c === 'note_meta') { const n = _notes.find(x => x.path === a.path); Object.assign(n, a.patch);
          return Promise.resolve(n); }
        if (c === 'link_meta') return Promise.resolve({ url: a.url, site: 'YouTube', title: 'Как я сделал свой Linux', image: 'https://i.ytimg.com/vi/x/hqdefault.jpg', desc: 'Канал', video: true });
        return Promise.resolve({}); };
      $('nav button[data-p="notes"]').click(); }""", [NOTES, FILES])
    pg.wait_for_timeout(700)
    r = pg.evaluate("() => [...document.querySelectorAll('#nt-filt .nt-fc')].map(x => x.textContent)")
    ok(r[0] == "Все3" and r[1] == "Закреплённые1" and "#наука1" in r and r[-1] == "Архив1", f"над списком — «Все», «Закреплённые», метки, «Архив»: {r}")
    r = pg.evaluate("() => [document.querySelector('#nt-list .nt-gh').textContent, [...document.querySelectorAll('#nt-list .nt-row b')].map(x => x.textContent)]")
    ok(r[0] == "Закреплённые" and r[1][0] == "Эйнштейн" and "Старое" not in r[1], f"закреплённые — первой группой; архив — не в общем списке: {r}")
    pg.click('#nt-filt [data-f="#linux"]'); pg.wait_for_timeout(400)
    ok(pg.evaluate("[...document.querySelectorAll('#nt-list .nt-row b')].map(x => x.textContent)") == ["Как я сделал Linux"], "метка — фильтр")
    pg.click('#nt-list .nt-row[data-p="Заметки/Linux.md"]'); pg.wait_for_timeout(700)
    r = pg.evaluate("""() => { const c = document.querySelector('#nt-view .nt-card'); return c && [c.dataset.ext, c.querySelector('b').textContent, c.classList.contains('vid'),
      getComputedStyle(c.querySelector('.nt-cimg')).backgroundImage.includes('ytimg')]; }""")
    ok(r and r[0] == "https://youtu.be/dQw4w9WgXcQ" and r[1] == "Как я сделал свой Linux" and r[2] and r[3], f"ссылка отдельной строкой — карточкой с обложкой и названием: {r}")
    ok(pg.evaluate("[...document.querySelectorAll('#nt-view .nt-tags .nt-tag')].map(x => x.textContent.replace('×',''))") == ["#linux", "#ядро"],
       "метки заметки: своя (с ×) и из текста")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-notes-keep-list.png"))
    pg.click("#nt-pinb"); pg.wait_for_timeout(400)
    ok(["note_meta", {"path": "Заметки/Linux.md", "patch": {"pinned": True}}] in pg.evaluate("_calls"), "«Закрепить»")
    pg.click("#nt-colb"); pg.wait_for_timeout(150); pg.click('#nt-pal [data-c="PINK"]'); pg.wait_for_timeout(400)
    ok(["note_meta", {"path": "Заметки/Linux.md", "patch": {"color": "PINK"}}] in pg.evaluate("_calls"), "«Цвет» — палитра как в Keep")
    pg.click("#nt-tbtn"); pg.fill("#nt-tadd", "проекты"); pg.press("#nt-tadd", "Enter"); pg.wait_for_timeout(400)
    ok(["note_meta", {"path": "Заметки/Linux.md", "patch": {"tags": ["linux", "проекты"]}}] in pg.evaluate("_calls"), "своя метка — Enter")
    pg.click('#nt-filt [data-f=""]'); pg.wait_for_timeout(300)
    pg.click('#nt-vw [data-v="grid"]'); pg.wait_for_timeout(500)
    r = pg.evaluate("""() => [document.querySelector('.nt-cols').classList.contains('grid'), document.querySelectorAll('#nt-list .nt-tile').length,
      getComputedStyle(document.querySelector('#nt-list .nt-tile[data-p="Заметки/Google Keep/Эйнштейн.md"]')).backgroundColor, getComputedStyle(document.querySelector('#nt-view')).display]""")
    ok(r[0] and r[1] == 3 and r[2] != "rgba(0, 0, 0, 0)" and r[3] == "none", f"плитками: цвет заметки фоном, открытой заметки сбоку нет: {r}")
    # 28.10 (снимок владельца, Ubuntu): CSS-колонки в WebKitGTK резали плитки на границе колонок — теперь колонки из
    # блоков, каждая плитка целиком в самой короткой
    pg.set_viewport_size({"width": 1600, "height": 1000})
    pg.evaluate("""async () => { for (let i = 0; i < 13; i++) _notes.push({ path: `Заметки/Тест ${i}.md`, title: `Заметка ${i}`, mtime: Date.now() / 1000 - 20 - i,
        folder: '', snippet: 'слово '.repeat(8 + (i * 37) % 70), att: 0, img: i % 5 === 2 ? 'Вложения/x.png' : '', tags: [], color: i % 4 === 1 ? 'TEAL' : '', pinned: false, archived: false });
      await ntLoad(); }""")
    pg.wait_for_timeout(500)
    r = pg.evaluate("""() => { const boxes = [...document.querySelectorAll('#nt-list .nt-masonry')], big = boxes.sort((a, b) => b.querySelectorAll('.nt-tile').length - a.querySelectorAll('.nt-tile').length)[0];
      const cols = [...big.querySelectorAll(':scope > .nt-mcol')], hs = cols.map(c => c.offsetHeight), tiles = [...big.querySelectorAll('.nt-tile')];
      const inCols = tiles.every(t => t.parentElement.classList.contains('nt-mcol'));
      const tall = Math.max(...tiles.map(t => t.offsetHeight));
      return [cols.length, inCols, Math.max(...hs) - Math.min(...hs) <= tall + 14, getComputedStyle(big).columnCount]; }""")
    ok(r[0] >= 3 and r[1] and r[2] and r[3] == "auto", f"плитки — колонками-блоками (не CSS-колонки), каждая целиком, колонки ровные: {r}")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-notes-keep-grid.png"))
    pg.set_viewport_size({"width": 1000, "height": 1000}); pg.wait_for_timeout(500)
    n2 = pg.evaluate("Math.max(...[...document.querySelectorAll('#nt-list .nt-masonry')].map(b => b.querySelectorAll(':scope > .nt-mcol').length))")
    ok(n2 < r[0], f"окно уже — колонок меньше: {r[0]} → {n2}")
    pg.click('#nt-list .nt-tile[data-p="Заметки/Покупки.md"]'); pg.wait_for_timeout(600)
    ok(pg.evaluate("getComputedStyle(document.querySelector('#nt-view')).position") == "fixed" and pg.evaluate("!!document.querySelector('#nt-close')"),
       "плитка → заметка поверх, с «×»")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-notes-keep-open.png"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    ok(pg.evaluate("getComputedStyle(document.querySelector('#nt-view')).display") == "none", "Esc — закрыть")
    pg.set_viewport_size({"width": 760, "height": 950}); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    b_.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")

# Телефон: шапка заметки не видна, галочка и правка её не теряют (заметки приходят с компьютера синхронизацией)
import shutil, subprocess  # noqa: E402,E401
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)], capture_output=True, text=True, check=True).stdout, encoding="utf-8")
FM = "---\nsource: Google Keep\ntags: [дом]\ncolor: TEAL\n---\n\n# Покупки\n\n- [ ] хлеб\n- [ ] молоко\n"
perrs = []
with sync_playwright() as p:
    b_ = p.chromium.launch(); pg = b_.new_page(viewport={"width": 400, "height": 820}); pg.on("pageerror", lambda x: perrs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("(t) => { saveNotes([{ id: 'k1', title: 'Покупки', text: t, time: Date.now() }]); openNote('k1'); }", FM)
    pg.wait_for_timeout(400)
    t = pg.inner_text("#nt-read")
    ok("source" not in t and "tags" not in t and "хлеб" in t, f"телефон: шапки не видно: {t[:60]!r}")
    pg.click("#nt-read .tk >> nth=0"); pg.wait_for_timeout(200)
    x = pg.evaluate("notes().find(x => x.id === 'k1').text")
    ok(x.startswith("---\nsource: Google Keep\ntags: [дом]\ncolor: TEAL\n---\n") and "- [x] хлеб" in x, f"галочка — шапка на месте: {x[:80]!r}")
    pg.click("#nt-edit"); pg.wait_for_timeout(200)
    ok("source" not in pg.input_value("#nt-text"), "в правке на телефоне шапки нет")
    pg.fill("#nt-text", "- [x] хлеб\n- [ ] молоко\n- [ ] сыр"); pg.click("#nt-save"); pg.wait_for_timeout(300)
    x = pg.evaluate("notes().find(x => x.id === 'k1').text")
    ok(x.startswith("---\nsource: Google Keep") and x.rstrip().endswith("- [ ] сыр"), f"правка на телефоне — шапка сохранена: {x[:70]!r}")
    b_.close()
ok(not perrs, f"телефон: без ошибок: {perrs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
