"""№480 (02.11, Ubuntu): «с вчерашнего дня в виджете висит ответ про время». Карточку ответа прятал только таймер
hideCapLater, а showCap его снимал: событие после ответа («Таймер — готово», ход работы) оставляло карточку без таймера —
до следующего разговора; мышь «над ответом» (mouseleave не пришёл — окно спрятали) держала её вечно. Теперь сторож
capGuard: без таймера и без дела — прячем через 3 минуты, «под мышью» — через 10; «Да / Нет» и ответ в работе не трогаем.
И карточка «Напоминание поставлено»: строка «когда» была склеена с комментарием и не обновлялась."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = r"""(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async () => ({}); setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neon" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira", personas: [{ id: "lira", name: "Лира" }], reminders: [], state: "idle" }); }, 150); }; ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 300, "height": 520}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1200)
    shown = "() => document.getElementById('cap').classList.contains('show')"
    # ответ готов, а потом «ход работы — готово» снял таймер (как после «Таймер» 01.11, 21:15)
    pg.evaluate("""() => { core.emit('state', { state: 'idle' }); core.emit('heard', { text: 'Поставь таймер на 5 минут' });
      core.emit('answer', { text: 'Таймер — через 5 мин.', done: true }); core.emit('tool', { title: 'Таймер', status: 'done' }); }""")
    pg.wait_for_timeout(300)
    ok(pg.evaluate(shown) and not pg.evaluate("capArmed"), "после «— готово» карточка осталась без таймера (так и было)")
    ok(not pg.evaluate("capGuard(Date.now() + 60e3)"), "через минуту — ещё видна")
    ok(pg.evaluate("capGuard(Date.now() + 200e3)") and not pg.evaluate(shown), "через 3 минуты сторож её спрятал")
    # мышь «над ответом», а mouseleave так и не пришёл
    pg.evaluate("() => { core.emit('answer', { text: 'Сейчас 21:15.', done: true }); capHover = true; }")
    pg.wait_for_timeout(100)
    pg.evaluate("() => { clearTimeout(capTimer); capArmed = false; }")      # таймер сработал при «мыши над ним» и сдался
    ok(pg.evaluate("capGuard(Date.now() + 200e3)") and not pg.evaluate(shown), "«мышь над ним» без настоящего наведения — тоже прячется")
    # «Да / Нет» ждёт ответа — не трогаем; ответ ещё готовится — не трогаем
    pg.evaluate("() => { core.emit('confirm', { text: 'Удалить файл?' }); }")
    pg.wait_for_timeout(100)
    ok(not pg.evaluate("capGuard(Date.now() + 900e3)") and pg.evaluate(shown), "вопрос «Да / Нет» сторож не прячет")
    pg.evaluate("() => { core.emit('confirm_done', {}); core.emit('heard', { text: 'Длинный вопрос' }); core.emit('state', { state: 'thinking' }); }")
    pg.wait_for_timeout(100)
    ok(not pg.evaluate("capGuard(Date.now() + 900e3)"), "ответ ещё готовится — не прячем")
    # обычный ответ с таймером — сторож не мешает
    pg.evaluate("() => { core.emit('state', { state: 'idle' }); core.emit('answer', { text: 'Готово.', done: true }); }")
    pg.wait_for_timeout(100)
    ok(pg.evaluate("capArmed") and not pg.evaluate("capGuard(Date.now() + 900e3)"), "у обычного ответа свой таймер — сторож ждёт его")
    # карточка «напоминание поставлено» — «когда» обновляется
    pg.evaluate("() => { core.emit('note_saved', { kind: 'note', title: 'Покупки', path: 'a.md' }); }")
    pg.evaluate("() => { core.emit('reminder_set', { item: { id: 'r1', kind: 'reminder', when: '22 ноября в 20:05', text: 'Удалить оболочку' } }); }")
    pg.wait_for_timeout(100)
    w = pg.evaluate("document.getElementById('rem-when').textContent")
    ok(w == "22 ноября в 20:05", f"напоминание: показано, когда сработает ({w!r})")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("setInterval(() => capGuard(), 30000)" in hud, "сторож карточки запускается раз в полминуты")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
