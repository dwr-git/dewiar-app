"""Идея №178 (11.11, Денис): «помощник пишет „Я вас слушаю“, а непонятно, доходит ли речь: говоришь длинную мысль — ответа
нет. Полоска уровня, которая дёргается от голоса, и отметка „слышу / тишина / не разобрал“». Теперь в виджете, пока
слушает, — пять полосок уровня микрофона (голос — ярче); ждал вопрос, а речи не сложилось — строка, почему: «микрофон
тихий или не тот?» или «звук есть, но не речь — вокруг музыка?», с подсказкой, где проверить. Распознанное и так
появляется в «Чате»."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
  core.call = async () => ({}); setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neusky" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira", personas: [{ id: "lira", name: "Лира" }], reminders: [], state: "idle" }); }, 150); }; ready(); })();"""
au = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok('self.emit("listen_none", sound=bool(sound)' in au, "ядро: ждало вопрос, а речи не было — событие listen_none (звук был или нет)")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for lang, none_txt in (("ru", "Не расслышала"), ("en", "Didn't catch that")):
        pg = b.new_page(viewport={"width": 360, "height": 560}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
        pg.goto((ROOT / "ui/hud.html").as_uri() + f"?port=1&mode=card&lang={lang}"); pg.wait_for_timeout(1200)
        pg.evaluate("() => core.emit('state', { state: 'listening' })"); pg.wait_for_timeout(100)
        ok(pg.evaluate("document.querySelector('#bubble').classList.contains('listen')") and pg.is_visible("#lvl"), f"[{lang}] слушает — полоски уровня видны")
        pg.evaluate("() => core.emit('level', { v: 0.3, src: 'mic' })"); pg.wait_for_timeout(150)
        h = pg.evaluate("[...document.querySelectorAll('#lvl i')].map(i => +getComputedStyle(i).height.replace('px', ''))")
        ok(max(h) > 6 and pg.evaluate("document.querySelector('#bubble').classList.contains('hear')"), f"[{lang}] голос — полоски поднялись и ярче: {h}")
        pg.evaluate("() => core.emit('level', { v: 0.9, src: 'voice' })"); pg.wait_for_timeout(100)
        h2 = pg.evaluate("[...document.querySelectorAll('#lvl i')].map(i => +getComputedStyle(i).height.replace('px', ''))")
        ok(h2 == h, f"[{lang}] голос самой Лиры полоски не двигает")
        pg.evaluate("() => { core.emit('state', { state: 'idle' }); core.emit('listen_none', { sound: false, peak: 120, speech: 0.2 }); }"); pg.wait_for_timeout(150)
        ok(none_txt in pg.inner_text("#say") and not pg.is_visible("#lvl"), f"[{lang}] речи не было — сказано почему: {pg.inner_text('#say')}")
        pg.evaluate("() => core.emit('listen_none', { sound: true, peak: 900, speech: 0.7 })"); pg.wait_for_timeout(100)
        ok(("музыка" if lang == "ru" else "music") in pg.inner_text("#say"), f"[{lang}] звук был, но не речь — про музыку и разговор вокруг")
        ok(len(pg.get_attribute("#say", "title") or "") > 20, f"[{lang}] подсказка, где проверить микрофон")
        pg.close()
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
