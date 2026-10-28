"""«Пишу» (0.68; писатель 28.10 и план владельца: «Документы» — и для своих текстов): сколько слов человек написал сегодня
в своих файлах из папок «Документов». Проверяем подсчёт (прирост по файлам, без минусов, новый файл — с нуля, новая папка —
не прибавка), цель и дни подряд, ответ модели словами и карточку в студии."""
import json, os, socket, subprocess, sys, tempfile, time
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS", "")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import writing as W  # noqa: E402
import knowledge as K  # noqa: E402

ok(W.count_words("---\ntitle: x\n---\nМилева [[Эйнштейн|Альберт]] писала [письмо](http://a.b/c) 12 раз.") == 5, "слова: без заголовка, ссылок и чисел")
ok([W.words_ru(n) for n in (1, 3, 5, 11, 21, 1240)] == ["1 слово", "3 слова", "5 слов", "11 слов", "21 слово", "1 240 слов"], "слова по-русски")
tmp = Path(tempfile.mkdtemp()); book = tmp / "Роман"; book.mkdir()
(book / "Глава 1.md").write_text("слово " * 1000, encoding="utf-8")
(book / "договор.pdf").write_bytes(b"%PDF-1.4")                       # PDF — не своё, не считаем
folders = [str(book)]
w = W.Writing(lambda: folders, tmp / "w.json", extract=K.extract)
s = w.scan()
ok(s["today"] == 0 and s["files"] == 1 and s["total"] == 1000, f"первый подсчёт — точка отсчёта, не «написано»: {s['today']}, файлов {s['files']}")
(book / "Глава 1.md").write_text("слово " * 1300, encoding="utf-8")
s = w.scan()
ok(s["today"] == 300 and s["touched"][0] == {"name": "Глава 1.md", "n": 300}, f"дописал главу — +300: {s['today']} {s['touched']}")
(book / "Глава 2.md").write_text("новое " * 250, encoding="utf-8")
s = w.scan()
ok(s["today"] == 550, f"новая глава сегодня — с нуля: {s['today']}")
(book / "Глава 1.md").write_text("слово " * 900, encoding="utf-8")
s = w.scan()
ok(s["today"] == 250, f"стёр в первой главе — у неё ноль, не минус: {s['today']}")
old = tmp / "Старое"; old.mkdir(); (old / "архив.docx").write_bytes(b"")
import zipfile  # noqa: E402
with zipfile.ZipFile(old / "архив.docx", "w") as z:
    z.writestr("word/document.xml", "<w:document><w:body><w:p><w:t>" + "старое " * 5000 + "</w:t></w:p></w:body></w:document>")
os.utime(old / "архив.docx", (time.time() - 86400 * 30,) * 2)
folders.append(str(old))
s = w.scan()
ok(s["today"] == 250 and s["files"] == 3 and s["total"] >= 6000, f"добавил папку со старыми текстами — не «написал сегодня»: {s['today']}, всего {s['total']}")
w.set_goal(500)
today = datetime.now().date()
w.d["days"].update({(today - timedelta(days=i)).isoformat(): 600 for i in (1, 2, 3)})
s = w.summary()
ok(s["goal"] == 500 and s["streak"] == 4 and s["week"] == 250 + 1800 and len(s["days"]) == 14 and s["days"][-1]["n"] == 250,
   f"цель, дни подряд (сегодня ≥ 50), неделя, две недели: {s['streak']}, {s['week']}")
txt = w.text()
ok("Сегодня написано 250 слов из цели 500 слов" in txt and "«Глава 2.md» (+250)" in txt and "4 дня подряд" in txt, f"модели — словами: {txt[:160]!r}")
w2 = W.Writing(lambda: folders, tmp / "w.json", extract=K.extract)
ok(w2.summary()["today"] == 250, "перезапуск — помнит сегодняшнее")
ok("рукопись" in W.Writing(lambda: [], tmp / "e.json").text(), "нет своих текстов — подскажет добавить папку")
import tools as TL  # noqa: E402
ok("writing_today" in TL.TOOLS and "writing_today" in TL.SAFE_CORE and "250 слов" in TL.t_writing_today({}, {"writing": w}), "инструмент «сколько я написал сегодня»")

# ядро и студия
from playwright.sync_api import sync_playwright  # noqa: E402
s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); PORT = s_.getsockname()[1]; s_.close()
cfg = tmp / "cfg"; cfg.mkdir()
b2 = tmp / "Диплом"; b2.mkdir(); (b2 / "введение.md").write_text("текст " * 400, encoding="utf-8")
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "mode_seen": 1},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}, "workspace": {"path": str(tmp / "ws")},
    "knowledge": {"folders": [str(b2)]}}), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 1100})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        call = lambda c, a=None: pg.evaluate("([c, a]) => core.call(c, a || {})", [c, a])  # noqa: E731
        call("writing_get", {"fresh": True})
        (b2 / "введение.md").write_text("текст " * 1640, encoding="utf-8")
        call("writing_get", {"fresh": True})
        pg.click('nav button[data-p="docs"]'); time.sleep(1.5)
        ok(pg.is_visible("#wr-card") and pg.inner_text("#wr-today").replace(" ", " ") == "1 240" and pg.inner_text("#wr-u") == "слов",
           f"«Документы»: сегодня написано — крупно: {pg.inner_text('#wr-today')!r}")
        ok(pg.locator("#wr-bars .wr-bar.now").count() == 1 and pg.locator("#wr-bars .wr-hit").count() == 14, "две недели столбиками, сегодня — ярче")
        ok("введение" in pg.inner_text("#wr-facts"), "в каких файлах сегодня")
        pg.fill("#wr-goal-n", "1000"); pg.dispatch_event("#wr-goal-n", "change"); time.sleep(0.8)
        ok(pg.evaluate("document.querySelector('#wr-card').classList.contains('met')") and "Цель дня — есть" in pg.inner_text("#wr-facts"),
           "цель 1000 — выполнена: карточка теплеет")
        pg.hover("#wr-bars .wr-hit:last-of-type"); time.sleep(0.2)
        ok("1 240 слов" in pg.inner_text("#wr-tip").replace(" ", " "), f"наведение — число и дата: {pg.inner_text('#wr-tip')!r}")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "writing.png"))
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
