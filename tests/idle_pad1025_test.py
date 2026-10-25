"""Выпуск 0.44.2 (25.10):
1. Нагрузка в простое (YouTube: «в простое 20–40 % процессора и 10–25 % видеокарты»): облик в покое через 20 с рисуется
   ~6 раз в секунду, окно просыпается таймером, а не 60 раз в секунду; голос, взгляд и смена состояния будят сразу.
   Ядро в тишине не шлёт уровень микрофона 15 раз в секунду.
2. Блокнот: цвета текста «под настроение» (владелец: «тёмно-синий заголовок ассоциируется со ссылками… разные схемы»).
3. Схемы Mermaid: своя палитра, скруглённые блоки, читаемый размер, «смотреть крупно» (владелец: «смотрится нечитаемой…
   скруглить углы, небольшая тень… и во весь экран просмотр»).
4. Телефон, «Что нового»: кнопка «Попробовать» в светлой теме — светлый текст на сиреневом (№243).
5. HOME = «~» — данные писались в папку «~» (выгрузка: «близкие: сохранить — Permission denied: '~/.local'»)."""
import json, os, re, subprocess, sys, tempfile, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "tests")); sys.path.insert(0, str(ROOT / "core"))
import contrast_lib  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- 5) HOME «~»
r = subprocess.run([sys.executable, "-c", "import settings; print(settings.STATE_DIR)"], cwd=str(ROOT / "core"),
                   env={**{k: v for k, v in os.environ.items() if k != "DEWIAR_STATE_DIR"}, "HOME": "~"}, capture_output=True, text=True)
sd = [x for x in r.stdout.splitlines() if x.strip()]
ok(sd and os.path.isabs(sd[-1]) and "~" not in sd[-1], f"HOME «~» — данные всё равно в настоящей домашней папке: {sd[-1:] or r.stderr[-200:]}")

# ---------- 1б) уровень микрофона в тишине
import engine  # noqa: E402


class Stub:
    _intro_ear = None; _intro_probe = None; _level_t = 0.0

    def __init__(self):
        self.sent = []

    def emit(self, ev, **kw):
        self.sent.append(kw)


st = Stub()
import time  # noqa: E402
for i in range(30):                                   # 30 «кадров» тишины с шумом 0.010–0.018
    st._level_t -= 0.07
    engine.Engine._level(st, 0.01 + (i % 5) * 0.002, "mic")
ok(len(st.sent) <= 2, f"тишина — уровень почти не шлётся ({len(st.sent)} из 30)")
st._level_t -= 0.07; engine.Engine._level(st, 0.4, "mic")
ok(st.sent and st.sent[-1]["v"] == 0.4, "заговорили — уровень уходит сразу")
st._level_t -= 0.07; engine.Engine._level(st, 0.01, "mic")
ok(st.sent[-1]["v"] == 0.01, "замолчали — ноль уходит сразу (облик не застынет с открытым ртом)")
st._level_t -= 1.1; n = len(st.sent); engine.Engine._level(st, 0.012, "mic")
ok(len(st.sent) == n + 1, "раз в секунду — всё равно шлём, для порядка")

FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
RAF = """(() => { window.__raf = 0; const o = window.requestAnimationFrame; window.requestAnimationFrame = (f) => o((t) => { window.__raf++; f(t); }); })();"""
HUD_CORE = r"""(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async () => ({}); setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neusky" } }, status: { state: "idle" } }); core.emit("state", { state: "idle" }); }, 200); }; ready(); })();"""
MD = """# План

Идея: **сервер с 4090**, а при *очереди* — туда.

## Шаги

- поставить vLLM
- [ссылка](https://dewiar.pro/)

```mermaid
flowchart TD
  A[Запрос] --> B{Очередь}
  B -->|свободно| C[Основной]
  B -->|занято| D[4090]
```

```mermaid
flowchart LR
  A1[Один] --> A2[Два] --> A3[Три] --> A4[Четыре] --> A5[Пять] --> A6[Шесть] --> A7[Семь] --> A8[Восемь] --> A9[Девять] --> A10[Десять] --> A11[Одиннадцать] --> A12[Двенадцать]
```
"""
PAD_CORE = r"""(() => { window.calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async (c, a) => { calls.push([c, a]); if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
    if (c === "pad_read") return { name: a.name, text: MDTEXT, mtime: 1 }; return {}; };
  setTimeout(() => core.emit("hello", { settings: { ui: { skin: "neusky", pad_colors: "sea" } }, status: { state: "idle" } }), 150); }; ready(); })();""".replace("MDTEXT", json.dumps(MD))

with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    # ---------- 2, 3) блокнот
    pg = b.new_page(viewport={"width": 620, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(PAD_CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "right", "gap": 14, "clips": []})))
    pg.wait_for_timeout(3000)
    ok(pg.evaluate("document.querySelector('#ed').dataset.cs") == "sea", "схема цветов из настроек (ui.pad_colors) — применена")
    pg.click("#b-cs"); pg.wait_for_timeout(150)
    ok(pg.locator("#cs.on button[data-cs]").count() == 9 and pg.evaluate("document.activeElement.dataset.cs") == "sea",
       "палитра рядом с размером текста: девять схем (и яркие, «как в редакторе кода»), выбранная — в фокусе")
    pg.keyboard.press("ArrowDown"); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    ok(pg.evaluate("document.querySelector('#ed').dataset.cs") == "dusk" and not pg.evaluate("document.querySelector('#cs').classList.contains('on')"),
       "стрелка и Enter — выбрали «Вечер», список закрылся")
    ok(["settings_save", {"patch": {"ui": {"pad_colors": "dusk"}}}] in pg.evaluate("calls"), "выбор сохраняется в настройках")
    pg.click("#b-cs"); pg.click("#cs [data-cs='ink']"); pg.wait_for_timeout(150)
    h1, a = pg.evaluate("[getComputedStyle(document.querySelector('#ed h1')).color, getComputedStyle(document.querySelector('#ed a')).color]")
    ok(not pg.evaluate("document.querySelector('#ed').hasAttribute('data-cs')") and h1 != a,
       f"«Чернила» (по умолчанию): заголовок не цвета ссылки ({h1} ≠ {a})")
    ok(["settings_save", {"patch": {"ui": {"pad_colors": None}}}] in pg.evaluate("calls"), "по умолчанию — в настройках пусто")
    for cs in ("ink", "forest", "sea", "dusk", "editor", "monokai", "carnival", "theme", "plain"):
        pg.evaluate(f"colorScheme('{cs}', true)"); pg.wait_for_timeout(60)
        bad = contrast_lib.audit(pg, "#ed", 3.0)
        ok(not bad, f"схема «{cs}»: текст читается (контраст ≥ 3): {bad[:2]}")
    pg.evaluate("skin('neudusk')"); pg.wait_for_timeout(150)
    for cs in ("ink", "forest", "sea", "dusk", "editor", "monokai", "carnival", "theme", "plain"):
        pg.evaluate(f"colorScheme('{cs}', true)"); pg.wait_for_timeout(60)
        bad = contrast_lib.audit(pg, "#ed", 3.0)
        h = pg.evaluate("[getComputedStyle(document.querySelector('#ed h1')).color, getComputedStyle(document.querySelector('#ed h2')).color]")
        ok(not bad and (cs in ("ink", "plain") or h[0] != h[1]), f"тёмная тема, схема «{cs}»: читается, заголовки разного цвета {h} {bad[:2]}")
    pg.evaluate("skin('neusky')"); pg.wait_for_timeout(150)
    figs = pg.locator("#ed .dw-diagram")
    ok(figs.count() == 2, "две схемы нарисованы")
    info = pg.evaluate("""[...document.querySelectorAll('#ed .dw-diagram')].map(f => { const s = f.querySelector(':scope > svg');
      return { rx: [...s.querySelectorAll('.node rect')].every(r => +r.getAttribute('rx') > 0), zoom: !!f.querySelector('.dw-zoom'),
               w: s.getBoundingClientRect().width, vb: +s.getAttribute('viewBox').split(/[\\s,]+/)[2], fw: f.clientWidth,
               fill: getComputedStyle(s.querySelector('.node rect')).fill, lbl: [...s.querySelectorAll('g.edgeLabel')].map(e => e.textContent.trim()).filter(Boolean) }; })""")
    ok(all(i["rx"] for i in info), "блоки скруглены")
    ok(all(i["zoom"] for i in info), "у каждой схемы — «смотреть крупно»")
    ok(info[0]["lbl"] == ["свободно", "занято"], f"подписи стрелок видны: {info[0]['lbl']}")
    ok("255, 255, 222" not in info[0]["fill"] and "236, 236, 255" not in info[0]["fill"], f"не жёлто-сиреневая палитра по умолчанию: {info[0]['fill']}")
    ok(info[0]["w"] <= info[0]["vb"] + 1, "маленькая схема — не крупнее натуральной величины")
    ok(info[1]["vb"] > info[1]["fw"] and info[1]["w"] >= info[1]["vb"] * 0.59, f"широкая — не мельче 60 %, листается вбок: {info[1]}")
    figs.nth(1).scroll_into_view_if_needed(); figs.nth(1).hover(); pg.click("#ed .dw-diagram >> nth=1 >> .dw-zoom"); pg.wait_for_timeout(300)
    ok(pg.locator(".dw-view").count() == 1 and pg.locator('#ed pre[data-lang="mermaid"]').count() == 0, "«смотреть крупно» — просмотр на всё окно, схема не превратилась в текст")
    k0 = pg.evaluate("document.querySelector('.dw-view svg').style.transform")
    pg.mouse.move(300, 400); pg.mouse.wheel(0, -400); pg.wait_for_timeout(150)
    ok(pg.evaluate("document.querySelector('.dw-view svg').style.transform") != k0, "колёсико — масштаб")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    ok(pg.locator(".dw-view").count() == 0, "Esc — закрыть")
    pg.close()

    # ---------- 1) облик в простое
    pg = b.new_page(viewport={"width": 300, "height": 420}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(HUD_CORE); pg.add_init_script(RAF)
    pg.goto((ROOT / "ui/hud.html").as_uri()); pg.wait_for_timeout(1500)
    pg.evaluate("window.__d = 0; const o = entity.draw.bind(entity); entity.draw = (n) => { const r = o(n); if (r === undefined) window.__d++; return r; }")
    pg.wait_for_timeout(2000)
    d0 = pg.evaluate("__d"); pg.wait_for_timeout(2000); live = (pg.evaluate("__d") - d0) / 2
    pg.wait_for_timeout(19000)
    d0, r0 = pg.evaluate("[__d, __raf]"); pg.wait_for_timeout(4000); d1, r1 = pg.evaluate("[__d, __raf]")
    deep, raf = (d1 - d0) / 4, (r1 - r0) / 4
    ok(live >= 12, f"первые секунды покоя — живой темп ({live:.1f} кадров/с)")
    ok(deep <= 7.5 and raf <= 16, f"20 с покоя — ~6 кадров/с и редкие пробуждения ({deep:.1f} кадров/с, {raf:.1f} rAF/с)")
    pg.evaluate("core.emit('state', { state: 'listening' })")
    d0 = pg.evaluate("__d"); pg.wait_for_timeout(1000); woke = pg.evaluate("__d") - d0
    ok(woke >= 12, f"заговорили — сразу живой темп ({woke} кадров за секунду)")
    pg.close()

    # ---------- 4) телефон: «Что нового», кнопка «Попробовать» в светлой теме
    tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
    subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
    for skin in ("neusky", "snow", "glass", "brand"):
        pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        pg.evaluate(f"""S.skin = '{skin}'; try {{ applyLook(); }} catch (e) {{}}
          newsShow([{{ phone: '0.6.98', items: [{{ icon: '⚫', title: 'Пять в ряд', text: 'Игра.', try: '«Лира, давай поиграем в пять в ряд»' }}] }}])""")
        pg.wait_for_timeout(600)
        n = pg.locator("#news-body .nwtry").count()
        bad = contrast_lib.audit(pg, "#news-body", 3.0) if n else ["нет кнопки"]
        ok(n == 1 and not bad, f"«Что нового», тема {skin}: «Попробовать…» читается: {bad[:2]}")
        if skin == "neusky":       # №241: Лира спросила «…?» — слушание включилось само; ответ остаётся на экране
            pg.evaluate("closeSheets()")
            long = "Давай так: открой Dewiar на телефоне, нажми «Ещё» и поищи там пункт «Сообщить об ошибке». " * 3 + "Нашёл?"
            pg.evaluate("(t) => { showBot(t); frameAnswer(t); }", long); pg.wait_for_timeout(200)
            pg.evaluate("D.recognizer = () => true; D.has = () => true; D.listen = () => {}; listen()"); pg.wait_for_timeout(400)
            ok("Сообщить об ошибке" in pg.inner_text("#bot") and pg.evaluate("$('#bot').classList.contains('framed')"),
               "слушание после ответа не стирает ответ — дочитать можно на главном экране")
            pg.evaluate("ask('а теперь короче')"); pg.wait_for_timeout(300)
            ok("Сообщить об ошибке" not in pg.inner_text("#bot"), "новый вопрос — старый ответ уходит")
            pg.evaluate("openSheet('#sh-day'); dayTab = 'rem'; renderDay()"); pg.wait_for_timeout(500)
            sh = pg.evaluate("getComputedStyle(document.querySelector('.donehd')).boxShadow")
            ok("36, 50, 74" in sh, f"«Дела»: верхний блок с чёткой кромкой, не сливается с листом (№244): {sh[:60]}")
            pg.evaluate("""saveNotes([{ id: 'n1', title: 'Главное', folder: 'Блокнот', time: Date.now(),
              text: '## Ответы\\n**Ответы для GitHub** — по одному.\\n> Спасибо за *точное* описание\\n- [x] готово\\n- пункт [ссылка](https://x.y)\\n```mermaid\\nflowchart TD\\nA-->B\\n```' }]);
              dayTab = 'notes'; renderDay()"""); pg.wait_for_timeout(400)
            pv = pg.inner_text(".it.note .ntpv")
            ok(not any(x in pv for x in ("**", "##", "> ", "[x]", "](", "```")) and "Ответы для GitHub" in pv and "☑" in pv
               and pg.locator(".it.note .ntpv b").count() >= 1, f"заметки на телефоне — без сырого Markdown (№246): {pv[:120]!r}")
            mu = pg.evaluate("getComputedStyle(document.body).getPropertyValue('--muted')")
            ok(float(re.findall(r"[\d.]+", mu)[-1]) >= 0.7, f"второстепенный текст светлой темы — плотнее (№242): {mu}")
        pg.close()
    ok(not errs, f"без ошибок на страницах: {errs[:2]}")
    b.close()
if fails:
    raise SystemExit(1)
