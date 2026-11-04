"""Идея №135 (04.11): «Возможность корректировать календарь, удалять, редактировать, менять время руками». В календаре
студии напоминание уже правилось (текст, время, дни повтора, удалить), но только в пределах своего дня: перенести разовое
на завтра можно было лишь удалив и создав заново. Теперь у разового — поле даты; прошедшее время не принимается.
(На телефоне дата, время, текст и повтор правятся с 17.10 — remEdit в app.js.)"""
import json, os, re, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


D = date.today().isoformat()
T = (date.today() + timedelta(days=1)).isoformat()
Y = (date.today() - timedelta(days=1)).isoformat()
DAYS = {D: [
    {"type": "reminder", "title": "Позвонить Артёму", "time": "23:58", "id": "r2", "kind": "reminder"},
    {"type": "reminder", "title": "Пора выключать компьютер", "time": "17:50", "id": "r3", "kind": "reminder", "repeat": True,
     "repeat_text": "по будням в 17:50", "rdays": [0, 1, 2, 3, 4]},
    {"type": "reminder", "title": "Итог дня", "text": "Подведи итог дня", "time": "21:00", "id": "j1", "kind": "job", "repeat": True,
     "repeat_text": "каждый день в 21:00", "deliver": "voice"}]}
CORE = r"""
(() => { window.calls = []; window.DAYS = %s;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "calendar_month") return { days: DAYS, currency: "RUB" };
      if (c === "reminder_update") return { when: "завтра в 09:30" };
      return {}; }; };
  ready(); })();
""" % json.dumps(DAYS, ensure_ascii=False)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("() => { S = Object.assign({}, S || {}, { ui: {}, llm: { profiles: {} }, features: {} }); window.ask = () => Promise.resolve(true); }")
    pg.evaluate("() => { $('nav button[data-p=\"calendar\"]').click(); }"); pg.wait_for_timeout(500)
    pg.click(f"#cal-grid .day[data-d='{D}']"); pg.wait_for_timeout(400)
    pg.locator("#dd-body .cit", has_text="Позвонить Артёму").locator(".t").click(); pg.wait_for_timeout(250)
    ok(pg.locator("#dd-body #re-date").count() == 1 and pg.input_value("#dd-body #re-date") == D, "разовое напоминание — поле даты, в нём выбранный день")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-calendar-date135.png"))
    pg.fill("#dd-body #re-date", T); pg.fill("#dd-body #re-time", "09:30"); pg.click("#dd-body #re-save"); pg.wait_for_timeout(300)
    ok(any(c[0] == "reminder_update" and c[1]["id"] == "r2" and c[1]["patch"]["at"] == f"{T}T09:30:00" for c in pg.evaluate("calls")),
       "перенесли на завтра 9:30 — reminder_update с новой датой")
    ok("Перенесено" in pg.inner_text("#toast"), f"и сказано, куда: {pg.inner_text('#toast')!r}")
    n = len(pg.evaluate("calls"))
    pg.locator("#dd-body .cit", has_text="Позвонить Артёму").locator(".t").click(); pg.wait_for_timeout(250)
    pg.fill("#dd-body #re-date", Y); pg.fill("#dd-body #re-time", "10:00"); pg.click("#dd-body #re-save"); pg.wait_for_timeout(300)
    ok(not [c for c in pg.evaluate("calls")[n:] if c[0] == "reminder_update"] and "уже прошло" in pg.inner_text("#toast"),
       "на вчера — нельзя: «Это время уже прошло»")
    pg.locator("#dd-body .cit", has_text="Позвонить Артёму").locator(".t").click(); pg.wait_for_timeout(200)
    pg.locator("#dd-body .cit", has_text="Пора выключать компьютер").locator(".t").click(); pg.wait_for_timeout(250)
    ok(pg.locator("#dd-body #re-date").count() == 0 and pg.locator("#dd-body .remed-days").count() == 1,
       "повторяющееся — без даты (дни недели кнопками, как было)")
    pg.locator("#dd-body .cit", has_text="Пора выключать компьютер").locator(".t").click(); pg.wait_for_timeout(200)
    pg.locator("#dd-body .cit", has_text="Итог дня").click(); pg.wait_for_timeout(250)
    ok(pg.locator("#dd-body #re-date").count() == 0, "дело по расписанию — без даты")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")

# ядро: перенос на другой день — тем же reminder_update (patch.at — любая дата и время)
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
h = src[src.index('if cmd == "reminder_update":'):][:3000]
ok('patch = dict(a.get("patch") or {})' in h and "self.reminders.update(" in h, "ядро: reminder_update берёт новое at целиком (с датой)")
print("ALL OK" if not fails else f"FAILS: {len(fails)}")
sys.exit(1 if fails else 0)
