"""28.10, владелец: «важно людям рассказать про локальную память — с компьютера можно дать папки, по которым Лира ищет,
читает и отвечает… показать в уроках, вывести красивой кнопкой на главной… локальный RAG — сильное преимущество».
Раньше «Мои документы — «Знания»» были в самом низу «Обо мне». Теперь: свой раздел «Документы» (меню «Знания» и значок на
«Главной», в том числе у тех, кто уже настраивал главную), сверху — зачем и пример ответа с файлом, «Добавить папку…»
главной кнопкой, сводка «2 папки, 418 файлов — Лира готова отвечать», фразы-примеры (нажать — вопрос в «Чате»);
в «Обо мне» — ссылка; урок «Ваши документы» в курсе «Лира для работы»; статья в справке."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import course as C  # noqa: E402
work = next(c for c in C.COURSES if c["id"] == "work")
L = next(x for x in work["lessons"] if x["day"] == 2)
ok("документ" in L["title"].lower() and any(s.get("open") == "docs" for s in L["steps"]), f"урок «Лира для работы», день 2 — про документы, шаг «откройте «Документы»»: {L['title']}")
rx = next(re.compile(s["rx"]) for s in L["steps"] if s.get("rx"))
ok(rx.search("что в моих документах про отпуск") and not rx.search("какая погода"), "фраза урока засчитывается")
guide = {a["id"]: a for a in json.loads((ROOT / "data/guide.json").read_text(encoding="utf-8"))}
ok("my-docs" in guide and "pc" in guide["my-docs"]["where"] and "rag" in guide["my-docs"]["keywords"], "статья «Документы» в справке")
help_js = (ROOT / "ui/assets/help.js").read_text(encoding="utf-8")
ok(re.search(r"\n  docs: \{", help_js) is not None, "«?» в разделе «Документы» — своя справка")

with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""() => {
      S = Object.assign({}, S || {}, { features: {}, ui: { home_apps: ['chat', 'calendar', 'notes'], home_known: ['chat', 'close', 'calendar', 'reminders', 'notes', 'tasks', 'memory'] } });
      window._folders = [{ path: '/home/u/Работа/Договоры', name: 'Договоры', exists: true, files: 412, indexed: 412, chunks: 9870, busy: false, skipped: false, error: '' },
                         { path: '/home/u/Конспекты', name: 'Конспекты', exists: true, files: 5, indexed: 5, chunks: 40, busy: false, skipped: false, error: '' }];
      window._files = [{ path: 'Инструкция к котлу.pdf', size: 820000, chunks: 31, error: '' }];
      core.call = (c, a) => {
        if (c === 'knowledge_folders') return Promise.resolve(_folders);
        if (c === 'knowledge_list') return Promise.resolve({ folder: '/x', files: _files });
        if (c === 'settings_save') return Promise.resolve(S);
        if (c === 'exam_traces') return Promise.resolve([]);
        if (c === 'memory_get') return Promise.resolve('');
        return Promise.resolve({}); };
      featuresApply && featuresApply(); hmNav && hmNav(); loadHome && loadHome(); }""")
    pg.wait_for_timeout(500)
    r = pg.evaluate("() => [!!document.querySelector('#hm-apps [data-open=docs]'), !document.querySelector('nav button[data-p=docs]').hidden]")
    ok(r[0] and r[1], f"кто уже настраивал главную — значок «Документы» появился сам, раздел в меню: {r}")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-home-docs.png"))
    pg.click("#hm-apps [data-open=docs]"); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.querySelector('#p-docs').classList.contains('cur')"), "значок → раздел «Документы»")
    t = pg.inner_text("#p-docs")
    ok("Спросите свои документы" in t and "Договор поставки.pdf" in t and "на этом компьютере" in t, "сверху — зачем, пример ответа с файлом, где идёт поиск")
    ok(pg.inner_text("#dc-stat") == "2 папки, 418 файлов — Лира готова отвечать", f"сводка: {pg.inner_text('#dc-stat')!r}")
    ok("Договоры" in pg.inner_text("#kn-folders") and "Инструкция к котлу.pdf" in pg.inner_text("#kn-list"), "папки и отдельные файлы — списками")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-docs.png"), full_page=True)
    pg.evaluate("() => { _folders = []; _files = []; loadDocs(); }"); pg.wait_for_timeout(300)
    ok("Пока пусто" in pg.inner_text("#dc-stat"), "пусто — подсказка, с чего начать")
    pg.evaluate("() => { _folders = [{ path: '/home/u/Книги', name: 'Книги', exists: true, files: null, busy: true, chunks: 0 }]; loadDocs(); }"); pg.wait_for_timeout(300)
    ok("читаю, можно уже спрашивать" in pg.inner_text("#dc-stat"), "читает в фоне — так и сказано")
    pg.click("#dc-try button >> nth=0"); pg.wait_for_timeout(400)
    ok(pg.evaluate("document.querySelector('#p-chat').classList.contains('cur') && document.querySelector('#ch-text').value") == "Что в моих документах про отпуск?",
       "пример → вопрос в «Чате», остаётся отправить")
    pg.evaluate("document.querySelector('nav button[data-p=me]').click()"); pg.wait_for_timeout(300)
    pg.click('#p-me [data-goto="docs"]'); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#p-docs').classList.contains('cur')"), "«Обо мне» → ссылка на «Документы»")
    pg.set_viewport_size({"width": 760, "height": 1000}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-docs-narrow.png"))
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
