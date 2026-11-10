"""№560 (ПК 0.84.2, 05.11): «можно добавить кнопку стоп, чтобы не говорить, когда работаешь без микрофона». В виджете
писало «Модель отвечает долго — 68 с. «Стоп» — прервать», а нажать было нечего — «стоп» работал только голосом.
Теперь, пока Лира думает или говорит, в строке состояния виджета — кнопка «■ Стоп» (то же, что голосом: ядро «stop»),
в подсказке «отвечает долго» — тоже кнопка, Esc в виджете — то же самое. На телефоне и в веб-версии — «Стоп» рядом
с «Думаю/Говорю»: замолкает, не включая микрофон; Esc на клавиатуре — тоже."""
import os, re, shutil, subprocess, sys, tempfile
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
  window._calls = []; core.call = async (c, a) => { _calls.push(c); return {}; };
  setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "SKIN" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira", personas: [{ id: "lira", name: "Лира" }], reminders: [], state: "idle" }); }, 150); }; ready(); })();"""
errs = []
vis = "() => getComputedStyle(document.getElementById('stopb')).display !== 'none'"
with sync_playwright() as p:
    b = p.chromium.launch()
    for skin in ("neusky", "neudusk"):
        pg = b.new_page(viewport={"width": 368, "height": 690}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE.replace("SKIN", skin))
        pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1200)
        ok(not pg.evaluate(vis), f"{skin}: в покое кнопки «Стоп» нет")
        pg.evaluate("() => core.emit('state', { state: 'thinking' })"); pg.wait_for_timeout(150)
        ok(pg.evaluate(vis), f"{skin}: думаю — «Стоп» в строке состояния")
        box = pg.locator("#stopb").bounding_box(); bub = pg.locator("#bubble").bounding_box()
        ok(box and box["width"] >= 50 and box["height"] >= 20 and box["x"] + box["width"] <= bub["x"] + bub["width"] + 0.5,
           f"{skin}: кнопка крупная и внутри строки: {box} в {bub}")
        ok(pg.get_attribute("#stopb", "aria-label") == "Остановить ответ", f"{skin}: у кнопки понятное имя для экранного диктора")
        fg, bg = pg.evaluate("() => { const s = getComputedStyle(document.getElementById('stopb')); return [s.color, getComputedStyle(document.getElementById('bubble')).color]; }")
        ok(fg == bg, f"{skin}: цвет текста кнопки — как у строки ({fg})")
        pg.click("#stopb"); pg.wait_for_timeout(100)
        ok(pg.evaluate("_calls.includes('stop')") and not pg.evaluate(vis), f"{skin}: нажали — ядру «stop», кнопка ушла сразу")
        pg.evaluate("() => { _calls.length = 0; core.emit('state', { state: 'speaking' }); }"); pg.wait_for_timeout(100)
        ok(pg.evaluate(vis), f"{skin}: говорю — «Стоп» тоже есть")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        ok(pg.evaluate("_calls.includes('stop')"), f"{skin}: Esc в виджете — тоже «стоп»")
        pg.evaluate("() => { _calls.length = 0; core.emit('state', { state: 'idle' }); }"); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        ok(not pg.evaluate("_calls.includes('stop')"), f"{skin}: в покое Esc ничего не останавливает")
        # поле вопроса открыто: Esc закрывает его, а не останавливает
        pg.evaluate("() => { core.emit('state', { state: 'thinking' }); openAsk(); }"); pg.wait_for_timeout(150)
        pg.focus("#askin"); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        ok(not pg.evaluate("_calls.includes('stop')") and pg.evaluate("document.getElementById('ask').style.display") != "block",
           f"{skin}: в поле вопроса Esc — закрыть поле, ответ не обрывается")
        # подсказка «отвечает долго» — с кнопкой
        pg.evaluate("() => { _calls.length = 0; health(`Модель отвечает долго — 68 с.`, false, false, false, true); }")
        hb = pg.locator("#health button.stop")
        ok(hb.count() == 1 and "Стоп" in hb.inner_text(), f"{skin}: в подсказке «отвечает долго» — кнопка «Стоп»")
        hb.click(); pg.wait_for_timeout(100)
        ok(pg.evaluate("_calls.includes('stop')") and not pg.evaluate("document.getElementById('health').classList.contains('on')"),
           f"{skin}: кнопка в подсказке — «стоп», подсказка убрана")
        # диктовка удержанием — «Стоп» не мешает
        pg.evaluate("() => { core.emit('state', { state: 'speaking' }); hold = { on: true, t0: Date.now(), far: false, by: 'key' }; holdShow(); }")
        ok(not pg.evaluate(vis), f"{skin}: пока держат и диктуют — «Стоп» спрятан")
        pg.evaluate("() => { hold = null; holdShow(); }")
        pg.close()
    b.close()
ok(not errs, f"виджет без ошибок страницы: {errs[:2]}")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("«Стоп» — прервать`" not in hud, "подсказка больше не отсылает к несуществующей кнопке")
eng = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('if cmd == "stop":\n            self.interrupt("кнопка", follow=False)' in eng, "ядро: «stop» — тот же обрыв, что голосом, без «слушаю дальше»")

# ---------- телефон и веб-версия ----------
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
perrs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for vp in ((393, 820), (1200, 760)):
        pg = b.new_page(viewport={"width": vp[0], "height": vp[1]}); pg.on("pageerror", lambda e: perrs.append(str(e)))
        pg.route("https://**", lambda r: r.abort())
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
        pg.evaluate("() => { window._listen = 0; listen = async () => { _listen++; }; window._stopped = 0; const s0 = D.stopSpeak; D.stopSpeak = () => { _stopped++; try { s0 && s0(); } catch (e) {} }; }")
        hid = "() => document.querySelector('#stopx').hidden"
        ok(pg.evaluate(hid), f"телефон {vp[0]}: в покое «Стоп» нет")
        pg.evaluate("() => setState('thinking')")
        ok(not pg.evaluate(hid), f"телефон {vp[0]}: думаю — «Стоп» рядом с состоянием")
        sb, st = pg.locator("#stopx").bounding_box(), pg.locator("#state").bounding_box()
        ok(sb["x"] >= st["x"] + st["width"] and abs((sb["y"] + sb["height"] / 2) - (st["y"] + st["height"] / 2)) < 4 and sb["height"] >= 26,
           f"телефон {vp[0]}: кнопка справа от «Думаю», на одной линии, палец попадает: {sb} / {st}")
        ok(sb["x"] + sb["width"] <= vp[0], f"телефон {vp[0]}: не вылезает за экран")
        pg.click("#stopx"); pg.wait_for_timeout(100)
        r = pg.evaluate("[state, _listen, _stopped > 0, document.querySelector('#stopx').hidden]")
        ok(r == ["idle", 0, True, True], f"телефон {vp[0]}: «Стоп» — замолчала, микрофон не включился: {r}")
        pg.evaluate("() => setState('speaking')"); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        ok(pg.evaluate("state") == "idle", f"телефон {vp[0]}: Esc на клавиатуре — тоже «стоп»")
        pg.close()
    b.close()
ok(not perrs, f"телефон без ошибок страницы: {perrs[:2]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
