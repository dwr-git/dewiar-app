"""ИИ-правка в блокноте (24.10, владелец: «выделяю фрагмент, правой клавишей — „перевести“, „переформулировать“,
„проверить орфографию“, „упростить“, „саммари“, „структурировать“, „mermaid-диаграмма“… переформулируется выделенное
с учётом всей вкладки… одни функции — для выделенного, другие — для всей страницы»).
core/padai.py: подсказки модели, чистка ответа, поток событий; ui/padai.js: меню по правой кнопке и ✨, карточка ответа,
«Заменить» / «Вставить сверху» / «Вставить схему», Ctrl+Z, схема Mermaid картинкой и блоком ```mermaid в файле."""
import json, os, sys, threading, time, urllib.parse
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- ядро: подсказки и чистка ----------
import padai  # noqa: E402

doc = "# Встреча\n\nОбсудили бюджет проекта «Ромашка». Иван отвечает за смету до пятницы.\n\nСледующий шаг — договор."
sysm, user, temp, mx = padai.prompt("rephrase", "Иван отвечает за смету до пятницы.", doc)
ok("ВЕСЬ ДОКУМЕНТ" in user and "Ромашка" in user and "ФРАГМЕНТ:\nИван отвечает" in user and "НЕ переписывай" in user,
   "переформулировать: выделенное — с контекстом всей вкладки, переписывается только фрагмент")
ok(0.4 <= temp <= 0.7 and 500 <= mx <= 6000 and "без вступлений" in sysm, f"температура и длина ответа разумные: {temp}, {mx}")
_, u2, t2, _ = padai.prompt("translate", "Привет, мир", doc, lang="en")
ok("английский" in u2 and t2 <= 0.3, "перевод: язык назван, температура низкая")
_, u3, _, _ = padai.prompt("summary", doc, doc, scope="doc")
ok("Кратко" in u3 and "ДОКУМЕНТ:" in u3 and "ВЕСЬ ДОКУМЕНТ (только для контекста" not in u3, "краткое содержание — по всей вкладке")
_, u4, _, _ = padai.prompt("write", "", doc, ask="письмо коллегам о переносе встречи", scope="cursor")
ok("письмо коллегам" in u4, "«написать на тему» — тема в задаче")
for bad, why in ((lambda: padai.prompt("rephrase", "  ", doc), "пусто"), (lambda: padai.prompt("ask", "текст", doc, ask=""), "без просьбы"),
                 (lambda: padai.prompt("fix", "я" * 20000, doc), "слишком много"), (lambda: padai.prompt("zzz", "x"), "неизвестное")):
    try:
        bad(); ok(False, f"ошибка: {why}")
    except ValueError as e:
        ok(bool(str(e)), f"понятный отказ ({why}): {e}")
ok(padai.clean("rephrase", "Вот переформулированный текст:\n\nИван готовит смету к пятнице.") == "Иван готовит смету к пятнице.", "чистка: без «Вот …:»")
ok(padai.clean("fix", "```markdown\n# Заголовок\n\nтекст\n```") == "# Заголовок\n\nтекст", "чистка: без обёртки ```markdown")
ok(padai.clean("diagram", "Вот схема:\n```mermaid\nflowchart LR\n  A-->B\n```\nГотово!") == "```mermaid\nflowchart LR\n  A-->B\n```", "схема: только блок mermaid")
ok(padai.clean("diagram", "flowchart TD\n  A-->B").startswith("```mermaid\nflowchart TD"), "схема без обёртки — обёрнута")


# поток событий: модель пишет кусками, страница получает текст и done
class Eng:
    def __init__(self):
        self.ev = []
        self.s = type("S", (), {"active_llm": lambda s: {"kind": "openai", "base_url": "http://x/v1", "model": "m"}})()
    def emit(self, t, **kw):
        self.ev.append(dict(kw, type=t))


import llm  # noqa: E402
calls = []


def fake_stream(p, system, messages, cancel=None, tools=None, _retry=0):
    calls.append((p, system, messages))
    for w in ["Вот новый вариант:\n\n", "Иван ", "готовит ", "смету ", "к пятнице."]:
        time.sleep(0.05)
        if cancel is not None and cancel.is_set():
            return
        yield "text", w


llm.stream_events = fake_stream
e = Eng(); A = padai.PadAI(e)
r = A.start({"act": "rephrase", "text": "Иван отвечает за смету до пятницы.", "doc": doc})
for _ in range(60):
    if any(x.get("done") for x in e.ev):
        break
    time.sleep(0.05)
last = [x for x in e.ev if x.get("id") == r["id"]][-1]
ok(last.get("done") and last.get("text") == "Иван готовит смету к пятнице." and not last.get("error"), f"поток: готовый ответ без вступления: {last}")
ok(calls and calls[0][0].get("max_tokens") and calls[0][0].get("temperature") == 0.6, "модели — свои температура и длина")
e2 = Eng(); e2.s.active_llm = lambda: None
try:
    padai.PadAI(e2).start({"act": "rephrase", "text": "x"}); ok(False, "без мозга — отказ")
except ValueError as er:
    ok("Мозг" in str(er) or "мозг" in str(er), f"без мозга — понятный отказ: {er}")
e3 = Eng(); A3 = padai.PadAI(e3)
r1 = A3.start({"act": "rephrase", "text": "раз", "doc": ""}); r2 = A3.start({"act": "simplify", "text": "два", "doc": ""})
time.sleep(0.6)
ok(not any(x.get("done") and x.get("id") == r1["id"] for x in e3.ev) and any(x.get("done") and x.get("id") == r2["id"] for x in e3.ev),
   "новый запрос останавливает прежний")
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('cmd in ("pad_ai", "pad_ai_stop")' in src, "команды pad_ai и pad_ai_stop у ядра")

# ---------- страница ----------
from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = """window.apiCalls = []; window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { apiCalls.push([k, ...a]);
  if (k === 'pad_size') return Promise.resolve([440, 520]); return Promise.resolve(true); } }) };"""
CORE = r"""
(() => { window.calls = []; window.AI_REPLY = {};
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    let n = 0;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: "# Встреча\n\nОбсудили бюджет проекта Ромашка. Иван отвечает за смету до пятницы.\n\nСледующий шаг — договор.\n", mtime: 1 };
      if (c === "pad_write") return { mtime: 2 };
      if (c === "pad_ai") { const id = "ai" + (++n), full = AI_REPLY[a.act] || "Новый текст.";
        if (full === "ERR") { setTimeout(() => core.emit("pad_ai", { id, text: "", done: true, error: "сервер модели не отвечает" }), 80); return { id }; }
        const parts = full.match(/[\s\S]{1,12}/g);
        parts.forEach((p, i) => setTimeout(() => core.emit("pad_ai", { id, text: parts.slice(0, i + 1).join(""), done: i === parts.length - 1 }), 60 + i * 25));
        return { id }; }
      return {}; }; };
  ready(); })();
"""
md = lambda pg: pg.evaluate("PadMD.html2md(document.querySelector('#ed'))")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 520, "height": 640}); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "right", "gap": 14, "clips": []})))
    pg.wait_for_timeout(1200)
    ok(pg.is_visible("#b-ai"), "на панели — кнопка ✨ ИИ-правки")

    def select_text(t):
        pg.evaluate("""(t) => { const ed = document.querySelector('#ed'); const w = document.createTreeWalker(ed, NodeFilter.SHOW_TEXT);
          let n; while ((n = w.nextNode())) { const i = n.data.indexOf(t); if (i >= 0) { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + t.length);
            ed.focus(); const s = getSelection(); s.removeAllRanges(); s.addRange(r); return true; } } return false; }""", t)

    def answer():
        for _ in range(60):
            if pg.evaluate("PadAI.state().done"):
                break
            pg.wait_for_timeout(50)
        pg.wait_for_timeout(100)

    # 1) выделенное — переформулировать — заменить — Ctrl+Z
    pg.evaluate("AI_REPLY.rephrase = 'Смету готовит Иван — к пятнице.'")
    select_text("Иван отвечает за смету до пятницы.")
    bx = pg.evaluate("(() => { const r = getSelection().getRangeAt(0).getClientRects()[0]; return [r.left + 20, r.top + 5]; })()")
    pg.mouse.click(bx[0], bx[1], button="right"); pg.wait_for_timeout(150)
    items = pg.evaluate("[...document.querySelectorAll('#aim [data-act]')].map(b => b.dataset.act)")
    ok(pg.is_visible("#aim") and items[:3] == ["rephrase", "simplify", "shorter"] and "tr" in items and "fix" in items and "ask" in items,
       f"правая кнопка на выделенном — меню действий над ним: {items}")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.screenshot(path=os.environ["DEWIAR_SHOTS"] + "/padai-menu.png")
    pg.click("#aim [data-act='rephrase']"); pg.wait_for_timeout(120)
    ok(pg.is_visible("#aip") and not pg.is_visible("#aim"), "карточка ответа появилась сразу")
    answer()
    args = [c[1] for c in pg.evaluate("calls") if c[0] == "pad_ai"][-1]
    ok(args["text"].strip() == "Иван отвечает за смету до пятницы." and "Ромашка" in args["doc"] and args["scope"] == "sel",
       f"в ядро — выделенное и вся вкладка для контекста: {args}")
    ok("Смету готовит Иван" in pg.inner_text("#aip .aib") and "Заменить" in pg.inner_text("#aip .aia"), "ответ в карточке, кнопка «Заменить»")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.screenshot(path=os.environ["DEWIAR_SHOTS"] + "/padai-card.png")
    ok("Иван отвечает за смету" in md(pg), "до «Заменить» лист не тронут")
    pg.click("#aip .aib2.p"); pg.wait_for_timeout(250)
    m1 = md(pg)
    ok("Смету готовит Иван — к пятнице." in m1 and "Обсудили бюджет проекта Ромашка." in m1 and "Иван отвечает" not in m1 and not pg.is_visible("#aip"),
       f"«Заменить» — только выделенное, в том же абзаце: {m1!r}")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(200)
    ok("Иван отвечает за смету до пятницы." in md(pg), "Ctrl+Z — вернулось как было")
    pg.wait_for_timeout(900)
    ok(any(c[0] == "pad_write" for c in pg.evaluate("calls")), "правка сохраняется, как обычная")

    # 2) перевод: подменю, первым — английский (текст русский)
    pg.evaluate("AI_REPLY.translate = 'Next step is the contract.'")
    select_text("Следующий шаг — договор.")
    bx = pg.evaluate("(() => { const r = getSelection().getRangeAt(0).getClientRects()[0]; return [r.left + 10, r.top + 5]; })()")
    pg.mouse.click(bx[0], bx[1], button="right"); pg.wait_for_timeout(120)
    pg.click("#aim [data-act='tr']"); pg.wait_for_timeout(120)
    langs = pg.evaluate("[...document.querySelectorAll('#aim .aisub [data-lang]')].map(b => b.dataset.lang)")
    ok(pg.is_visible("#aim .aisub") and langs[0] == "en" and "?" in langs, f"«Перевести» — языки, английский первым: {langs}")
    pg.click("#aim .aisub [data-lang='en']"); answer()
    args = [c[1] for c in pg.evaluate("calls") if c[0] == "pad_ai"][-1]
    ok(args["act"] == "translate" and args["lang"] == "en", "перевод на английский ушёл в ядро")
    ok("Перевод — английский" in pg.inner_text("#aip .ait"), "заголовок карточки — «Перевод — английский»")
    pg.click("#aip .aib2[data-a='below']"); pg.wait_for_timeout(200)
    m2 = md(pg)
    ok("Следующий шаг — договор.\n\nNext step is the contract." in m2, f"«Вставить ниже» — перевод под оригиналом: {m2[-120:]!r}")

    # 3) без выделения — действия над всей вкладкой; краткое содержание — сверху
    pg.evaluate("AI_REPLY.summary = '## Кратко\\n\\nВстреча о бюджете «Ромашки».\\n\\n- Иван — смета к пятнице\\n- Дальше — договор'")
    pg.click("#ed h1"); pg.wait_for_timeout(80)
    pg.click("#b-ai"); pg.wait_for_timeout(120)
    items = pg.evaluate("[...document.querySelectorAll('#aim [data-act]')].map(b => b.dataset.act)")
    ok(items[:3] == ["structure", "beautify", "summary"] and "diagram" in items and "write" in items and "continue" in items,
       f"✨ без выделения — действия со всей вкладкой и «написать»: {items}")
    pg.click("#aim [data-act='summary']"); answer()
    ok("Вставить сверху" in pg.inner_text("#aip .aia"), "краткое содержание — «Вставить сверху»")
    pg.click("#aip .aib2.p"); pg.wait_for_timeout(250)
    ok(md(pg).startswith("## Кратко"), f"вставлено в начало вкладки: {md(pg)[:60]!r}")

    # 4) схема Mermaid — картинкой в листе, в файле — блоком
    pg.evaluate("AI_REPLY.diagram = '```mermaid\\nflowchart LR\\n  A[\"Бюджет\"] --> B[\"Смета\"] --> C[\"Договор\"]\\n```'")
    pg.click("#ed h1"); pg.keyboard.press("End")
    pg.click("#b-ai"); pg.wait_for_timeout(100); pg.click("#aim [data-act='diagram']"); answer()
    pg.wait_for_timeout(1500)
    ok(pg.locator("#aip .aib .dw-diagram > svg").count() == 1, "в карточке схема нарисована")
    pg.click("#aip .aib2.p"); pg.wait_for_timeout(2500)
    ok(pg.locator("#ed .dw-diagram > svg").count() == 1 and pg.evaluate("document.querySelector('#ed .dw-diagram').contentEditable") == "false",
       "в листе — схема картинкой (не правится случайно)")
    ok("```mermaid\nflowchart LR" in md(pg) and "Договор" in md(pg), "в файле схема — блоком ```mermaid")
    pg.dblclick("#ed .dw-diagram"); pg.wait_for_timeout(200)
    ok(pg.locator('#ed pre[data-lang="mermaid"]').count() == 1, "двойной щелчок по схеме — её текст для правки")
    pg.click("#ed h1"); pg.wait_for_timeout(1800)
    ok(pg.locator("#ed .dw-diagram > svg").count() == 1, "ушли из текста схемы — снова картинка")

    # 5) ошибка модели — понятно и «Ещё раз»; Esc закрывает
    pg.evaluate("AI_REPLY.simplify = 'ERR'")
    select_text("Обсудили бюджет")
    bx = pg.evaluate("(() => { const r = getSelection().getRangeAt(0).getClientRects()[0]; return [r.left + 10, r.top + 5]; })()")
    pg.mouse.click(bx[0], bx[1], button="right"); pg.wait_for_timeout(100); pg.click("#aim [data-act='simplify']"); answer()
    ok("Не получилось: сервер модели не отвечает" in pg.inner_text("#aip") and "Ещё раз" in pg.inner_text("#aip .aia"), "ошибка — понятно, с «Ещё раз»")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    ok(not pg.is_visible("#aip"), "Esc — карточка закрыта")

    # 6) Shift + правая кнопка — обычное меню (своё не открывается)
    pg.mouse.click(bx[0], bx[1]); pg.keyboard.down("Shift"); pg.mouse.click(bx[0], bx[1], button="right"); pg.keyboard.up("Shift"); pg.wait_for_timeout(100)
    ok(not pg.is_visible("#aim"), "Shift + правая кнопка — своё меню не мешает")
    pg.keyboard.press("Escape")
    # тёмная тема — снимок
    if os.environ.get("DEWIAR_SHOTS"):
        pg.evaluate("AI_REPLY.rephrase = 'Смету готовит Иван — к пятнице. А договор — следующим шагом.'")
        select_text("Обсудили бюджет проекта Ромашка.")
        pg.mouse.click(bx[0], bx[1], button="right"); pg.wait_for_timeout(100); pg.click("#aim [data-act='rephrase']"); answer()
        pg.screenshot(path=os.environ["DEWIAR_SHOTS"] + "/padai-card2.png")
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
    b.close()

print("\nИТОГ:", "все проверки прошли" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
