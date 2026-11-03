"""№479 (02.11): «в „Мозге“ выбрана моя первая модель, хотя выбирал вторую; в „Персонажах“ всё верно — у Лиры вторая,
у Патрика первая. Какое-то эфемерное общее подключение?» Теперь в «Мозге» сказано: отмеченная — общая, для персонажей без
своей; и кто думает своей моделью."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    note = pg.evaluate("""() => {
      S = Object.assign({}, S || {}, { ui: {}, features: {}, llm: { active: "p1", persona: { lira: "p2" }, profiles: {
        p1: { name: "Первая", kind: "openai", model: "m1", base_url: "http://x" }, p2: { name: "Вторая", kind: "openai", model: "m2", base_url: "http://y" } } } });
      personas = [{ id: "lira", name: "Лира" }, { id: "patrick", name: "Патрик" }];
      renderProfiles(); const n = document.querySelector("#prof-note"); return n ? n.textContent : ""; }""")
    ok("общая" in note and "без своей" in note and "Лира — «" in note and "Патрик" not in note, f"в «Мозге» — что отмеченная общая и у кого своя: {note!r}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
