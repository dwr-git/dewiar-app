"""№645 (10.11): «виджет выскакивает на экран без вызова». По журналу: играла музыка, быстрый слух поймал «имя»
(«🎤 Имя „патрик“ услышано» → «Ложное срабатывание: имени во фразе нет»), а виджет поднимался из трея на само имя.
Теперь на имя виджет ждёт подтверждения точным распознаванием (heard — вопрос или «Слушаю…», думает, говорит);
ложное срабатывание — остаётся в трее. «Слушаю» без имени (горячая клавиша) — поднимается сразу, как раньше."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = r"""(() => { window.SHOWN = 0; window.pywebview = { api: { show: () => { SHOWN++; return Promise.resolve(); }, tray_back: () => Promise.resolve(),
    auto_back: () => {}, cancel_back: () => {} } };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async () => ({}); setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neon" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira", personas: [{ id: "lira", name: "Лира" }], reminders: [], state: "idle" }); }, 150); }; ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 300, "height": 520}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1200)
    run = lambda js: (pg.evaluate("SHOWN = 0"), pg.evaluate(js), pg.wait_for_timeout(150), pg.evaluate("SHOWN"))[-1]
    # музыка: «имя» → слушаю → ложное срабатывание → снова тихо
    n = run("() => { core.emit('wake', { phrase: 'патрик' }); core.emit('state', { state: 'listening' }); core.emit('state', { state: 'idle' }); }")
    ok(n == 0, f"ложное срабатывание в музыке — виджет не поднялся из трея (show: {n})")
    n = run("() => { core.emit('wake', { phrase: 'лира' }); core.emit('state', { state: 'listening' }); core.emit('heard', { text: 'какая погода' }); core.emit('state', { state: 'thinking' }); }")
    ok(n >= 1, f"«Лира, какая погода» — поднялся, как только вопрос распознан (show: {n})")
    pg.evaluate("core.emit('state', { state: 'idle' })")
    n = run("() => { core.emit('wake', { phrase: 'лира' }); core.emit('state', { state: 'listening' }); core.emit('heard', { text: '' }); }")
    ok(n >= 1, f"просто «Лира.» — «Слушаю вопрос» — поднялся (show: {n})")
    pg.evaluate("core.emit('state', { state: 'idle' })")
    n = run("() => { core.emit('state', { state: 'listening' }); }")
    ok(n >= 1, f"«Слушаю» без имени (горячая клавиша) — сразу, как раньше (show: {n})")
    pg.evaluate("core.emit('state', { state: 'idle' })")
    n = run("() => { core.emit('push', { text: 'Новое письмо' }); }")
    ok(n >= 1, "уведомление — поднимается, как раньше")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
