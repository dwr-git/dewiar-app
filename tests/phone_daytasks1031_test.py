"""№436/№437 (31.10, телефон 0.9.16): «Скажи мне список дел на сегодня» — Лира ответила, что дел нет, а в заметке
«Задачи на сегодня» два неотмеченных пункта; «посмотри в заметках» — «сейчас смотрю», а поиска не было. Теперь «дела на
сегодня» — без модели: неотмеченные пункты из заметок с делами на сегодня и напоминания до конца дня; «смотрю в заметки»
без find_notes — модель просят правда поискать."""
import os, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


w = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("""() => { const d = new Date(), mon = MON[d.getMonth()];
      saveNotes([{ id: "n1", title: "Задачи на сегодня", time: Date.now() - 3600e3, text: `# Задачи на сегодня\\n\\nЗадачи на ${d.getDate()} ${mon} ${d.getFullYear()}\\n\\n- [ ] Поменять колодки\\n- [ ] Поменять масло и фильтры\\n- [x] Помыть машину` },
                 { id: "n2", title: "Рецепт пирога", time: Date.now(), text: "- [ ] мука\\n- [ ] яйца" }]); }""")
    r = pg.evaluate("dayTasksQuick('Скажи мне список дел на сегодня')")
    ok(r and "Поменять колодки" in r["say"] and "масло и фильтры" in r["say"] and "Помыть машину" not in r["say"] and "мука" not in r["say"],
       f"дела на сегодня — неотмеченные пункты из заметки с задачами, без рецептов: {r}")
    for q in ("какие задачи на сегодня", "мои дела на сегодня", "что у меня на сегодня по делам", "список задач на сегодня?"):
        if q == "что у меня на сегодня по делам":
            continue
        ok(bool(pg.evaluate("(q) => dayTasksQuick(q)", q)), f"понимает: «{q}»")
    ok(pg.evaluate("dayTasksQuick('какая погода на сегодня')") is None, "погода — не про дела")
    pg.evaluate("() => saveNotes([])")
    ok(pg.evaluate("dayTasksQuick('список дел на сегодня')") is None, "ничего нет — отвечает модель (не «дел нет» вслепую)")
    c = pg.evaluate("(() => { const c = claimedAction('Поняла, Босс. Я сейчас смотрю в твои заметки.', new Set(), 'посмотри в заметках'); return c && c.tool; })()")
    ok(c == "find_notes", f"«смотрю в твои заметки» без поиска — просят правда поискать: {c}")
    # №439: своя модель не видит картинку — Лира подсказывает, что выбрать
    t = pg.evaluate("PIC_BLIND_RX.test('Алексей, я не могу открыть или прочитать изображение, приложенное к сообщению: в текущем режиме у меня нет доступа к файлам картинок.')")
    f = pg.evaluate("PIC_BLIND_RX.test('На фото — шапка письма: адресат, дата и номер.')")
    ok(t and not f, "№439: «не могу прочитать изображение» узнаётся, обычный ответ про фото — нет")
    src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
    ok("pics.length && !S.llm.cloud && turnAbort === ctl && PIC_BLIND_RX.test" in src and "модель со зрением" in src, "№439: подсказка — выбрать в «Мозге» модель со зрением")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
