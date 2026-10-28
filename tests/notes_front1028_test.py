"""28.10, пользователь (318 заметок, перенесённых из Google Keep): «в заметке сверху „source: Google Keep, id: Эйнштейн, --“
— это не то», в списке у каждой — «-- source: Google Keep id: …», название дважды; «если большой текст листать вниз, левая
панель съезжает вверх вместе с текстом». Шапка заметки (строки «ключ: значение» между «---» или «--», как в Obsidian)
больше не показывается и не попадает в отрывок; метки (tags) — чипами «#linux», цвет Keep — полоской у заметки; при
правке шапка сохраняется на месте; список заметок не уезжает при прокрутке длинной заметки."""
import os, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ["DEWIAR_WORKSPACE"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT / "core"))
import workspace  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


F = workspace.note_front
KEEP = "--\nsource: Google Keep\nid: Эйнштейн\nstatus: цвет: BROWN\n--\n\n# Эйнштейн\n\nА что, собственно, представляет собой теория?\n"
ok(F(KEEP)[0] == {"source": "Google Keep", "id": "Эйнштейн", "status": "цвет: BROWN", "color": "BROWN", "pinned": False, "archived": False} and F(KEEP)[1].strip().startswith("# Эйнштейн"),
   "шапка Google Keep разобрана: источник, цвет; текст — без неё")
ok(F("---\ntags: [linux, golang]\npinned: true\n---\nтекст")[0]["tags"] == ["linux", "golang"]
   and F("---\ntags:\n  - c#\n  - cursor\n---\nx")[0]["tags"] == ["c#", "cursor"], "метки Obsidian — строкой и списком")
ok(F("-- не шапка\nтекст")[0] == {} and F("---\n\nпросто текст\n---\n")[0] == {} and F("# Заголовок\n---\nтекст")[0] == {},
   "обычный текст с чертой — не шапка")
w = workspace.Workspace(None); w.ensure()
d = w.safe("Заметки/Google Keep"); d.mkdir(parents=True, exist_ok=True)
(d / "Эйнштейн.md").write_text(KEEP, encoding="utf-8")
time.sleep(0.05)
(w.safe("Заметки") / "Linux.md").write_text("---\ntags: [linux, hardware]\n---\n# Linux\n\nкак я собрал свой Linux\n", encoding="utf-8")
n = {x["title"]: x for x in w.notes()}
ok(n["Эйнштейн"]["snippet"].startswith("А что, собственно") and "source" not in n["Эйнштейн"]["snippet"] and n["Эйнштейн"]["color"] == "BROWN",
   f"в списке — начало текста, не шапка; цвет: {n['Эйнштейн']['snippet'][:40]!r}")
ok(n["Linux"]["tags"] == ["linux", "hardware"], "метки — в списке заметок")

LONG = "--\nsource: Google Keep\nid: Длинная\n--\n\n# Длинная\n\n" + "\n\n".join(f"Абзац {i}: " + "слово " * 60 for i in range(60))
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    notes = [{"path": "Заметки/Google Keep/Эйнштейн.md", "title": "Эйнштейн", "mtime": time.time(), "folder": "Google Keep", "snippet": n["Эйнштейн"]["snippet"],
              "att": 0, "img": "", "tags": [], "color": "BROWN", "source": "Google Keep"},
             {"path": "Заметки/Linux.md", "title": "Linux", "mtime": time.time() - 5, "folder": "", "snippet": "как я собрал", "att": 0, "img": "",
              "tags": ["linux", "hardware"], "color": "", "source": ""}] + [
             {"path": f"Заметки/N{i}.md", "title": f"Заметка {i}", "mtime": time.time() - 100 - i, "folder": "", "snippet": "текст", "att": 0, "img": "", "tags": [], "color": ""}
             for i in range(30)] + [{"path": "Заметки/Длинная.md", "title": "Длинная", "mtime": time.time() - 9999, "folder": "", "snippet": "Абзац", "att": 0, "img": "", "tags": [], "color": ""}]
    pg.evaluate("""([notes, keep, long, linux]) => { window._files = { 'Заметки/Google Keep/Эйнштейн.md': keep, 'Заметки/Длинная.md': long, 'Заметки/Linux.md': linux };
      core.call = (c, a) => {
        if (c === 'notes_list') return Promise.resolve(notes);
        if (c === 'ws_read') return Promise.resolve({ path: a.path, text: _files[a.path] || '# x\\n\\nтекст', mtime: Date.now() / 1000 });
        if (c === 'ws_write') { _files[a.path] = a.text; return Promise.resolve({ path: a.path }); }
        return Promise.resolve({}); };
      $('nav button[data-p="notes"]').click(); }""", [notes, KEEP, LONG, (w.safe("Заметки") / "Linux.md").read_text(encoding="utf-8")])
    pg.wait_for_timeout(700)
    r = pg.evaluate("""() => [document.querySelector('.nt-h').textContent, document.querySelector('.nt-body').innerText,
      getComputedStyle(document.querySelector('#nt-list .nt-row'), '::before').backgroundColor]""")
    ok(r[0] == "Эйнштейн" and "source" not in r[1] and "id:" not in r[1] and not r[1].strip().startswith("Эйнштейн"),
       f"заметка из Keep: название один раз, шапки не видно: {r[1][:60]!r}")
    ok(r[2] == "rgb(167, 123, 90)", f"цвет из Keep — полоской у заметки в списке: {r[2]}")
    pg.click('#nt-list .nt-row[data-p="Заметки/Linux.md"]'); pg.wait_for_timeout(400)
    ok(pg.evaluate("[...document.querySelectorAll('#nt-view .nt-top .nt-tag')].map(x => x.textContent)") == ["#linux", "#hardware"]
       and pg.evaluate("[...document.querySelectorAll('#nt-list .nt-row[data-p=\"Заметки/Linux.md\"] .nt-tag')].length") == 2, "метки — чипами и в списке, и в заметке")
    pg.click('#nt-list .nt-row[data-p="Заметки/Google Keep/Эйнштейн.md"]'); pg.wait_for_timeout(400)
    pg.click("#nt-edit"); pg.wait_for_timeout(300)
    ok("source" not in pg.input_value("#nt-text"), "в правке шапки тоже нет — только текст")
    pg.fill("#nt-text", "Новый текст"); pg.wait_for_timeout(1100)
    saved = pg.evaluate("_files['Заметки/Google Keep/Эйнштейн.md']")
    ok(saved.startswith("--\nsource: Google Keep\nid: Эйнштейн\nstatus: цвет: BROWN\n--\n\n# Эйнштейн\n\nНовый текст"), f"правка: шапка на месте, сверху: {saved[:90]!r}")
    pg.click("#nt-done"); pg.wait_for_timeout(400)
    pg.evaluate("ntOpen('Заметки/Длинная.md')"); pg.wait_for_timeout(500)
    top0 = pg.evaluate("document.querySelector('#nt-list').getBoundingClientRect().top")
    pg.mouse.move(900, 600); pg.mouse.wheel(0, 2500); pg.wait_for_timeout(500)
    top1 = pg.evaluate("document.querySelector('#nt-list').getBoundingClientRect().top")
    moved = pg.evaluate("document.querySelector('#nt-view').getBoundingClientRect().top")
    ok(moved < top0 - 500 and top1 > -5, f"длинная заметка листается, список остаётся на виду: список {top0:.0f}→{top1:.0f}, текст → {moved:.0f}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-notes-front.png"))
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
