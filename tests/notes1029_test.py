"""Заметки (29.10, владелец, снимок студии на Ubuntu): «1. поле для заголовка очень большое; 2. сразу присвоить цвет или
тип; 3. замочек — защита от случайного удаления важных заметок; 4. сортировка или раскидывание по разделам».
Название в правке — одной строкой (класс совпадал с картинкой плитки .nt-ti, 130 px); «Закрепить», «Цвет», «Метка» и
замок — и в правке, и у новой заметки; замок: заметку не удалить ни из студии, ни голосом/командой ядра, ни с телефона,
ни удалением с другого устройства через синхронизацию; папку с такой заметкой — тоже; порядок «Новые», «А–Я»,
«По цвету» (цвет — разделом); новая заметка при открытой метке — сразу с этой меткой.
Тот же день: «плитками создание новой заметки выглядит ещё хуже; картинка — красиво в плитке или списком»: картинка в плитке —
во всю ширину в своих пропорциях (была полоской: flex:1 от поля названия), в списке — крупная миниатюра."""
import os, re, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ["DEWIAR_WORKSPACE"] = tempfile.mkdtemp()
os.environ.setdefault("DEWIAR_DATA", tempfile.mkdtemp())
sys.path.insert(0, str(ROOT / "core"))
import workspace  # noqa: E402
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- ядро ----------
w = workspace.Workspace(None); w.ensure()
rel = w.save_note("Пароль от роутера", "важное")
rel2 = w.save_note("Черновик", "можно удалить")
n = w.note_meta(rel, {"locked": True})
ok(n and n["locked"], f"замок — в шапку заметки, в списке видно: {n and n.get('locked')}")
txt = w.safe(rel).read_text(encoding="utf-8")
ok("locked: true" in txt and "важное" in txt, "в файле: «locked: true» (видит и Obsidian), текст на месте")
try:
    w.remove(rel); ok(False, "защищённая заметка удалилась")
except workspace.WorkspaceError as e:
    ok("защищ" in str(e) and w.safe(rel).is_file(), f"удалить защищённую нельзя: «{e}»")
n = w.note_meta(rel, {"color": "RED", "pinned": True})
ok(n["locked"] and n["color"] == "RED", "цвет и «закрепить» замок не снимают")
w.safe("Заметки/Дом").mkdir(parents=True, exist_ok=True)
sub = w.save_note("Счётчики", "вода 123", folder="Дом")
w.note_meta(sub, {"locked": True})
try:
    w.remove_dir("Заметки/Дом"); ok(False, "папка с защищённой заметкой удалилась")
except workspace.WorkspaceError as e:
    ok("защищ" in str(e) and w.safe(sub).is_file(), f"папку с защищённой заметкой — тоже нельзя: «{e}»")
w.note_meta(rel, {"locked": False})
ok(not w.note_meta(rel, {})["locked"] and "locked" not in w.safe(rel).read_text(encoding="utf-8"), "замок снят — из шапки убран")
w.note_meta(rel, {"locked": True})
ok(w.remove(rel2) is True, "обычная заметка удаляется как раньше")

# синхронизация: удаление с другого устройства защищённую заметку не трогает, и она уходит туда обратно (новее удаления)
import sync as SY  # noqa: E402


class _Host:
    workspace = w


sy = SY.Sync.__new__(SY.Sync)
sy.host = _Host(); sy.state = {"map": {"s1": rel[len("Заметки/"):]}, "idx": {}}
sy._pad_event = lambda *a: None
old = time.time() - 3600
os.utime(w.safe(rel), (old, old))
r = sy._apply({"kind": "note", "id": "s1", "data": {}, "deleted": True})
ok(r is False and w.safe(rel).is_file() and w.safe(rel).stat().st_mtime > old + 1000,
   f"удаление с телефона: заметка с замком осталась и стала новее удаления (вернётся туда): {r}")

src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok("self.workspace.remove(a.get(\"path\", \"\"))" in src, "ws_delete идёт через workspace.remove — там и проверка замка")

# ---------- студия ----------
NOW = time.time()
NOTES = [
    {"path": "Заметки/Яблоки.md", "title": "Яблоки", "mtime": NOW - 10, "folder": "", "snippet": "сорт", "att": 0, "img": "", "tags": ["дача"], "color": "GREEN", "pinned": False, "archived": False, "locked": False},
    {"path": "Заметки/Арбуз.md", "title": "Арбуз", "mtime": NOW - 20, "folder": "", "snippet": "август", "att": 1, "img": "Заметки/Вложения/Арбуз/фото.png", "tags": [], "color": "RED", "pinned": False, "archived": False, "locked": False},
    {"path": "Заметки/Ключи.md", "title": "Ключи", "mtime": NOW - 30, "folder": "", "snippet": "от сейфа", "att": 0, "img": "", "tags": [], "color": "", "pinned": True, "archived": False, "locked": True},
    {"path": "Заметки/Бег.md", "title": "Бег", "mtime": NOW - 200000, "folder": "", "snippet": "5 км", "att": 0, "img": "", "tags": ["дача"], "color": "RED", "pinned": False, "archived": False, "locked": False},
    {"path": "Заметки/Вода.md", "title": "Вода", "mtime": NOW - 40, "folder": "", "snippet": "", "att": 0, "img": "", "tags": [], "color": "", "pinned": False, "archived": False, "locked": False}]
FILES = {"Заметки/Ключи.md": "---\npinned: true\nlocked: true\n---\n# Ключи\n\nот сейфа\n", "Заметки/Яблоки.md": "---\ntags: [дача]\ncolor: GREEN\n---\n# Яблоки\n\nсорт\n"}
with sync_playwright() as p:
    b_ = p.chromium.launch(); errs = []
    pg = b_.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve('') }) }; try { localStorage.removeItem('nt_grid'); localStorage.removeItem('nt_sort'); } catch (e) {}")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""([notes, files]) => { window._calls = []; window._notes = notes; window._files = files; window._toasts = [];
      const t0 = window.toast; window.toast = (m, ms) => { _toasts.push(m); return t0 && t0(m, ms); };
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'notes_list') return Promise.resolve(_notes);
        if (c === 'note_file') return Promise.resolve({ url: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200"><rect width="900" height="1200" fill="#3a7"/></svg>') });
        if (c === 'ws_read') return Promise.resolve({ path: a.path, text: _files[a.path] || '# ' + a.path.split('/').pop().replace('.md', '') + '\\n\\nтекст\\n', mtime: Date.now() / 1000 });
        if (c === 'ws_new_note') { _notes.unshift({ path: 'Заметки/Новая заметка.md', title: 'Новая заметка', mtime: Date.now() / 1000, folder: '', snippet: '', att: 0, img: '', tags: [], color: '', pinned: false, archived: false, locked: false });
          return Promise.resolve({ path: 'Заметки/Новая заметка.md' }); }
        if (c === 'note_meta') { const n = _notes.find(x => x.path === a.path); Object.assign(n, a.patch);
          let fm = Object.entries(a.patch).filter(([k, v]) => v && (!Array.isArray(v) || v.length)).map(([k, v]) => k + ': ' + (Array.isArray(v) ? '[' + v.join(', ') + ']' : v === true ? 'true' : v)).join('\\n');
          _files[a.path] = (fm ? '---\\n' + fm + '\\n---\\n' : '') + '# ' + n.title + '\\n\\nтекст\\n'; return Promise.resolve(n); }
        return Promise.resolve({}); };
      $('nav button[data-p="notes"]').click(); }""", [NOTES, FILES])
    pg.wait_for_timeout(700)
    rows = lambda: pg.evaluate("[...document.querySelectorAll('#nt-list .nt-row b')].map(x => x.textContent)")
    heads = lambda: pg.evaluate("[...document.querySelectorAll('#nt-list .nt-gh')].map(x => x.textContent)")
    ok(pg.evaluate("document.querySelector('#nt-sort [data-s=\"new\"]').classList.contains('on')") and rows()[0] == "Ключи", "по умолчанию — «Новые», закреплённые сверху")
    ok(pg.evaluate("!!document.querySelector('#nt-list .nt-row[data-p=\"Заметки/Ключи.md\"] .nt-lock')"), "в списке у защищённой — замочек")
    pg.click('#nt-sort [data-s="az"]'); pg.wait_for_timeout(300)
    ok(rows() == ["Ключи", "Арбуз", "Бег", "Вода", "Яблоки"] and heads() == ["Закреплённые", "Остальные"], f"«А–Я»: {rows()} {heads()}")
    pg.click('#nt-sort [data-s="color"]'); pg.wait_for_timeout(300)
    ok(rows() == ["Ключи", "Арбуз", "Бег", "Яблоки", "Вода"] and heads() == ["Закреплённые", "Красный", "Зелёный", "Без цвета"], f"«По цвету» — цвет разделом: {rows()} {heads()}")
    ok(pg.evaluate("localStorage.getItem('nt_sort')") == "color", "порядок запоминается")
    pg.click('#nt-vw [data-v="grid"]'); pg.wait_for_timeout(400)
    ok(pg.evaluate("document.querySelectorAll('#nt-list .nt-masonry').length") == 4, "плитками — те же разделы по цвету")
    pg.wait_for_timeout(300)
    r = pg.evaluate("() => { const i = document.querySelector('#nt-list .nt-tile .nt-ti'), t = i.closest('.nt-tile'); return [i.offsetHeight, i.offsetWidth, t.offsetWidth, i.classList.contains('on')]; }")
    ok(r[0] > r[1] * 1.15 and r[1] >= r[2] - 2 and r[3], f"картинка в плитке — во всю ширину, в своих пропорциях (портретная — выше), не полоской: {r}")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-notes-sort-color.png"))
    pg.click('#nt-vw [data-v="list"]'); pg.click('#nt-sort [data-s="new"]'); pg.wait_for_timeout(400)
    r = pg.evaluate("() => { const i = document.querySelector('#nt-list .nt-row .nt-th'); return [i.offsetWidth, i.offsetHeight, getComputedStyle(i).backgroundImage.startsWith('url')]; }")
    ok(r[0] >= 70 and r[1] >= 70 and r[2], f"в списке — крупная миниатюра картинки: {r}")
    # замок: «Удалить» не спрашивает и не удаляет — подсказывает
    pg.click('#nt-list .nt-row[data-p="Заметки/Ключи.md"]'); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.querySelector('#nt-lockb').classList.contains('on') && document.querySelector('#nt-lockb').textContent.includes('Защищено')"), "кнопка замка — «Защищено»")
    pg.evaluate("() => { window._asked = 0; window.ask = () => { _asked++; return Promise.resolve(true); }; }")
    pg.click("#nt-del"); pg.wait_for_timeout(300)
    ok(not any(c[0] == "ws_delete" for c in pg.evaluate("_calls")) and pg.evaluate("_asked") == 0 and any("защищ" in t for t in pg.evaluate("_toasts")),
       "защищённую «Удалить» не удаляет — подсказка, где снять")
    pg.click("#nt-lockb"); pg.wait_for_timeout(400)
    ok(["note_meta", {"path": "Заметки/Ключи.md", "patch": {"locked": False}}] in pg.evaluate("_calls"), "«Защищено» → снять замок")
    pg.click("#nt-lockb"); pg.wait_for_timeout(400)
    ok(["note_meta", {"path": "Заметки/Ключи.md", "patch": {"locked": True}}] in pg.evaluate("_calls"), "«Защитить» → замок")
    # новая заметка при открытой метке — сразу с ней; в правке — название одной строкой и «Цвет», «Метка», замок
    pg.click('#nt-filt [data-f="#дача"]'); pg.wait_for_timeout(300)
    pg.click("#nt-add"); pg.wait_for_timeout(700)
    ok(["note_meta", {"path": "Заметки/Новая заметка.md", "patch": {"tags": ["дача"]}}] in pg.evaluate("_calls"), "открыта метка «дача» — новая заметка сразу с ней")
    r = pg.evaluate("""() => { const t = document.querySelector('#nt-title'), cs = getComputedStyle(t);
      return [t.className, t.offsetHeight, cs.fontFamily, !!document.querySelector('#nt-view #nt-colb'), !!document.querySelector('#nt-view #nt-tbtn'),
              !!document.querySelector('#nt-view #nt-lockb'), !!document.querySelector('#nt-view #nt-pinb'), document.activeElement === t, cs.backgroundImage]; }""")
    ok(r[0] == "nt-tedit" and 30 <= r[1] <= 56 and "Unbounded" in r[2] and r[8] == "none", f"название в правке — одной строкой, не 130 px: {r[:3]}")
    ok(all(r[3:7]) and r[7], f"в правке — «Цвет», «Метка», «Защитить», «Закрепить»; курсор в названии: {r[3:8]}")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-notes-edit.png"))
    pg.fill("#nt-text", "купить сетку"); pg.wait_for_timeout(100)
    pg.click("#nt-colb"); pg.wait_for_timeout(150); pg.click('#nt-pal [data-c="YELLOW"]'); pg.wait_for_timeout(600)
    c = pg.evaluate("_calls")
    iw = max(i for i, x in enumerate(c) if x[0] == "ws_write"); im = max(i for i, x in enumerate(c) if x[0] == "note_meta" and x[1]["patch"] == {"color": "YELLOW"})
    ok(iw < im and "купить сетку" in c[iw][1]["text"], "цвет в правке: набранный текст сохраняется до смены шапки (не затирает её)")
    ok(pg.evaluate("!!document.querySelector('#nt-view #nt-text') && !!document.querySelector('#nt-view #nt-done')"), "после выбора цвета — остаёмся в правке")
    pg.evaluate("() => { const t = document.querySelector('#nt-title'); t.focus(); }")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    ok(pg.evaluate("document.activeElement && document.activeElement.id") == "nt-text", "Enter в названии — к тексту")
    pg.set_viewport_size({"width": 900, "height": 900}); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    b_.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")

# ---------- телефон: замок с компьютера соблюдается ----------
import shutil, subprocess  # noqa: E402,E401
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)], capture_output=True, text=True, check=True).stdout, encoding="utf-8")
perrs = []
with sync_playwright() as p:
    b_ = p.chromium.launch(); pg = b_.new_page(viewport={"width": 400, "height": 820}); pg.on("pageerror", lambda x: perrs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("""() => { saveNotes([{ id: 'k1', title: 'Ключи', text: '---\\nlocked: true\\n---\\n# Ключи\\n\\nот сейфа\\n', time: Date.now() },
                                     { id: 'k2', title: 'Черновик', text: 'x', time: Date.now() }]); window.confirm = () => true; noteDelete('k1', true); noteDelete('k2', true); }""")
    ids = pg.evaluate("notes().map(x => x.id)")
    ok(ids == ["k1"], f"телефон: защищённая на компьютере не удаляется, обычная — да: {ids}")
    b_.close()
ok(not perrs, f"телефон: без ошибок: {perrs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
