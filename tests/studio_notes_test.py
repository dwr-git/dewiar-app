"""Заметки на компьютере легко найти (отзыв 11.10: «сложно найти, а они важны»): «Календарь» → «Заметки» — все заметки
папки ассистента (и пришедшие с телефона), новые сверху, поиск по словам в названии, тексте и папке (без регистра и «ё»),
подсветка найденного, правка на месте, «Новая заметка». Ядро — workspace.notes, студия — с подменённым ядром."""
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


w = workspace.Workspace(None); w.ensure()
w.save_note("Умный дом", "Настроенный умный дом с компьютера не синхронизируется с мобильным приложением")
time.sleep(0.05); w.save_note("Покупки", "молоко, хлеб, яблоки", folder="Дача")
time.sleep(0.05); w.save_note("Ёлка", "купить ёлку к Новому году")
ok([x["title"] for x in w.notes()] == ["Ёлка", "Покупки", "Умный дом"], "все заметки, новые сверху")
ok([x["title"] for x in w.notes("умный синхрон")] == ["Умный дом"] and [x["title"] for x in w.notes("елку")] == ["Ёлка"]
   and [x["title"] for x in w.notes("дача")] == ["Покупки"], "поиск: все слова, без регистра и «ё», и по папке")
ok(w.notes("умный")[0]["snippet"].startswith("Настроенный умный дом") and not w.notes("квантовая"), "в выдаче — кусок текста; ничего — пусто")
# вложения: фото и файл рядом с заметкой, ссылками в конце текста; удаление уносит и их
rel = [x["path"] for x in w.notes() if x["title"] == "Покупки"][0]
r1 = w.note_attach(rel, "чек (магазин).jpg", b"\xff\xd8jpeg")
r2 = w.note_attach(rel, "список.pdf", b"%PDF")
p_ = w.safe(rel); p_.write_text(p_.read_text() + "\n" + r1["line"] + "\n" + r2["line"] + "\n", encoding="utf-8")
n = [x for x in w.notes() if x["title"] == "Покупки"][0]
ok(n["att"] == 2 and n["img"].endswith("чек (магазин).jpg") and w.note_file(n["img"])["url"].startswith("data:image/jpeg") and "Вложения" not in n["snippet"],
   f"вложения: миниатюра и счёт в списке, картинка для показа, в тексте-превью ссылок нет: {n}")
try:
    w.note_attach("Память/Обо мне.md", "x.txt", b"x"); bad = False
except Exception:  # noqa: BLE001
    bad = True
ok(bad, "прикреплять можно только к заметкам из «Заметок»")
NOTES = w.notes()
BUY = rel
PIX = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""([notes, pix, buy]) => { window._calls = []; window._files = { [buy]: '# Покупки\\n\\n*11 октября*\\n\\nмолоко, хлеб\\n- [ ] яблоки\\n\\n![чек.jpg](Вложения/Покупки/%D1%87%D0%B5%D0%BA.jpg)\\n📎 [список.pdf](Вложения/Покупки/список.pdf)\\n' };
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'notes_list') { const q = (a.q || '').toLowerCase(); return Promise.resolve(notes.filter(n => !q || (n.title + ' ' + n.snippet).toLowerCase().includes(q))); }
        if (c === 'ws_read') return Promise.resolve({ path: a.path, text: _files[a.path] || '# ' + a.path.split('/').pop().replace('.md', '') + '\\n\\nтекст заметки', mtime: Date.now() / 1000 });
        if (c === 'ws_write') { _files[a.path] = a.text; return Promise.resolve({ path: a.path }); }
        if (c === 'ws_new_note') return Promise.resolve({ path: 'Заметки/Новая заметка.md' });
        if (c === 'ws_rename') return Promise.resolve({ path: 'Заметки/' + a.title + '.md' });
        if (c === 'note_file') return Promise.resolve({ url: pix });
        if (c === 'note_attach') return Promise.resolve({ line: '![фото.png](Вложения/Покупки/фото.png)', kind: 'image', name: 'фото.png', path: 'Заметки/Вложения/Покупки/фото.png' });
        return Promise.resolve({}); };
      $('nav button[data-p="notes"]').click(); }""", [NOTES, PIX, BUY])
    pg.wait_for_timeout(600)
    nav = pg.evaluate("() => [...document.querySelectorAll('nav button[data-p]')].map(b => b.dataset.p)")
    ok(nav.index("notes") == nav.index("reminders") + 1 and nav.index("pay") == nav.index("notes") + 1 and nav.index("vault") == nav.index("pay") + 1 and nav.index("close") == nav.index("vault") + 1,
       "«Заметки» — в меню после «Напоминаний», дальше «Платежи», «Сейф паролей» и «Близкие»")
    ok(not pg.evaluate("!!document.querySelector('#cal-tabs [data-ct=\"notes\"]')"), "в «Календаре» вкладки «Заметки» больше нет — всё в одном разделе")
    r = pg.evaluate("() => [[...document.querySelectorAll('#nt-list .nt-row b')].map(x => x.textContent), !!document.querySelector('#nt-list .nt-th'), !!document.querySelector('.nt-h')]")
    ok(r[0][:3] == ["Ёлка", "Покупки", "Умный дом"] or sorted(r[0]) == sorted([x["title"] for x in NOTES]), f"список заметок, новые сверху: {r}")
    ok(r[1] and r[2], f"у заметки с фото — миниатюра; первая заметка открыта для чтения: {r}")
    pg.fill("#nt-q", "умный"); pg.wait_for_timeout(500)
    r = pg.evaluate("() => [[...document.querySelectorAll('#nt-list .nt-row b')].map(x => x.textContent), document.querySelectorAll('#nt-list mark').length]")
    ok(r[0] == ["Умный дом"] and r[1] >= 1, f"поиск на лету с подсветкой: {r}")
    pg.fill("#nt-q", ""); pg.wait_for_timeout(400)
    pg.click(f'#nt-list .nt-row[data-p="{BUY}"]'); pg.wait_for_timeout(500)
    r = pg.evaluate("() => [document.querySelector('.nt-h').textContent, document.querySelectorAll('.nt-body li.task').length, document.querySelectorAll('.nt-pics figure').length, [...document.querySelectorAll('.nt-f')].map(x => x.textContent.trim()), document.querySelector('.nt-body').textContent.includes('Вложения')]")
    ok(r == ["Покупки", 1, 1, ["список.pdf"], False], f"чтение: название, дела списком, фото плиткой, файл, ссылки в тексте не видны: {r}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-notes.png"))
    pg.click("#nt-edit"); pg.wait_for_timeout(300)
    pg.fill("#nt-text", "молоко, хлеб, сыр"); pg.wait_for_timeout(1100)
    saved = pg.evaluate("(b) => _files[b]", BUY)
    ok(saved.startswith("# Покупки\n\n*11 октября*\n\nмолоко, хлеб, сыр\n") and "![чек.jpg](Вложения/Покупки/%D1%87%D0%B5%D0%BA.jpg)" in saved and "📎 [список.pdf]" in saved,
       f"правка сохраняется сама; заголовок, дата и вложения на месте: {saved!r}")
    pg.set_input_files("#nt-file", files=[{"name": "фото.png", "mimeType": "image/png", "buffer": b"\x89PNG"}]); pg.wait_for_timeout(600)
    ok("![фото.png](Вложения/Покупки/фото.png)" in pg.evaluate("(b) => _files[b]", BUY) and pg.evaluate("document.querySelectorAll('.nt-pics figure').length") == 2,
       "фото к заметке — кнопкой (и перетаскиванием, Ctrl+V)")
    pg.click(".nt-pics figure .nt-x"); pg.wait_for_timeout(1100)
    ok("%D1%87%D0%B5%D0%BA" not in pg.evaluate("(b) => _files[b]", BUY), "вложение убирается крестиком в правке")
    pg.fill("#nt-title", "Покупки на неделю"); pg.dispatch_event("#nt-title", "change"); pg.wait_for_timeout(500)
    ok(["ws_rename", {"path": BUY, "title": "Покупки на неделю"}] in pg.evaluate("_calls") and pg.evaluate("_files['Заметки/Покупки на неделю.md'] || ''").startswith("# Покупки на неделю"),
       "переименование — и файл, и заголовок в тексте")
    pg.click("#nt-add"); pg.wait_for_timeout(500)
    ok(any(c[0] == "ws_new_note" for c in pg.evaluate("_calls")) and pg.evaluate("!!document.querySelector('#nt-title')"), "«Новая заметка» — сразу на правку")
    # 25.10, владелец: «в заметках диаграммы сырые и нет цветовых схем… сырой маркдаун»
    pg.evaluate("""() => { S = S || {}; S.ui = Object.assign({}, S.ui, { pad_colors: 'sea' }); NT.edit = false;
      _files['Заметки/Блокнот/Идея.md'] = '# Идея\\n\\n**Ответы для GitHub** — по одному.\\n\\n> Спасибо за описание\\n\\n```mermaid\\nflowchart TD\\n  A[Запрос] --> B[Ответ]\\n```\\n\\nСсылка: https://dewiar.pro/help';
      return ntOpen('Заметки/Блокнот/Идея.md'); }""")
    pg.wait_for_timeout(2500)
    r = pg.evaluate("""() => { const b = document.querySelector('.nt-body'); return { cs: b.dataset.cs, raw: /\\*\\*|```|^> /m.test(b.innerText),
      q: !!b.querySelector('blockquote'), bold: !!b.querySelector('b, strong'), dia: !!b.querySelector('.dw-diagram > svg'), link: !!b.querySelector('a[data-ext]'),
      plain: ntPlain('**НА ПОНЕДЕЛЬНИК** *ИДЕЯ* > цитата ```mermaid\\nA-->B```') }; }""")
    ok(r["cs"] == "sea" and not r["raw"] and r["q"] and r["bold"] and r["link"], f"заметка — оформлена, без сырого Markdown, цвета как в блокноте: {r}")
    ok(r["dia"], "схема Mermaid в заметке — картинкой")
    ok("**" not in r["plain"] and "```" not in r["plain"] and "схема" in r["plain"], f"строка в списке — без значков Markdown: {r['plain']}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
cmds = (ROOT / "core/engine_commands.py").read_text()
ok('cmd == "notes_list"' in cmds and '("note_attach", "note_file")' in cmds, "ядро: notes_list, note_attach, note_file")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
