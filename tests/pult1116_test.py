"""«Пульт Лиры» (1.0.6; владелец 16.11: «после экзамена пульт делаем сразу же, он невероятен!»; макеты 15.11):
- первая вкладка блокнота «Пульт», есть всегда (выключить совсем — «Оформление», ui.pult_on); значок у виджета;
- светится только настоящее: созвездие — реальные заметки (pult_data), к вопросу тянутся заметки из события recall,
  шаги — события tool; фон — дневник, Радар, «Дальше» из pult_data; заявка с сайта — зелёная карточка;
- сам открывается, когда Лира думает (вы не печатаете 5 с), и через 4 с после ответа возвращает на вашу вкладку;
  печатаете — не перехватывает: точка на вкладке и живая полоса внизу листа;
- первый раз — карточка «Это Пульт»; что показывать — шестерёнка на вкладке (ui.pult)."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import json, os, re, sys, tempfile, time, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- ядро: pult_data из того, что уже есть ----------
import engine_commands as EC  # noqa: E402


class WS:
    def __init__(self, root): self.root = root
    def notes(self, limit=160): return [{"title": "Рецепт торта", "folder": "Кухня", "mtime": time.time() - 3600, "path": "Заметки/Кухня/Рецепт торта.md"},
                                        {"title": "План на неделю", "folder": "", "mtime": time.time() - 86400 * 5, "path": "Заметки/План на неделю.md"}]
    def memory_get(self): return "- любит кофе\n- дочь Маша\n"


class Ins:
    def analyzed(self, h=None): return [{"title": "Торты без сахара набирают популярность", "src_name": "РБК", "a": {"signal": 0.8}, "ts": time.time() - 600}]
    def day_trend(self): return {"name": "торты без сахара", "day": 6, "status": "up"}


class Rem:
    def __init__(self):
        from datetime import datetime, timedelta
        n = datetime.now()
        self.items = [{"at": (n + timedelta(hours=2)).isoformat(timespec="minutes"), "text": "Позвонить маме", "kind": "remind"},
                      {"at": (n - timedelta(hours=2)).isoformat(timespec="minutes"), "text": "Прошлое", "kind": "remind"},
                      {"at": (n + timedelta(hours=1)).isoformat(timespec="minutes"), "text": "Пауза", "kind": "remind", "paused": True}]


class SC:
    recent = [{"ts": time.time() * 1000 - 60000, "name": "Анна", "contact": "+7 900 000 00 00", "cid": "c1"},
              {"ts": time.time() - 3 * 86400, "name": "Старый", "contact": "x", "cid": "c0"}]


d = Path(tempfile.mkdtemp())
(d / "Дневник").mkdir()
import datetime as dt  # noqa: E402
(d / "Дневник" / f"{dt.date.today():%Y-%m-%d}.md").write_text("# Дневник\n\n### 09:10\n\nУтро.\n\n### 14:20 · Лира\n\nРазобрала почту и\nнапомнила про торт.\n", encoding="utf-8")


class E(EC.CommandsMixin):
    def __init__(self):
        self.workspace, self.insight, self.reminders, self.sitechat = WS(d), Ins(), Rem(), SC()
    def persona_name(self): return "Лира"


r = E()._pult_data()
ok([n["t"] for n in r["notes"]] == ["Рецепт торта", "План на неделю"] and r["notes"][0]["f"] == "Кухня" and r["counts"] == {"notes": 2, "memory": 2},
   f"pult_data: заметки для созвездия и счёт памяти: {r['notes']} {r['counts']}")
ok(r["diary"] and r["diary"]["at"] == "14:20 · Лира" and r["diary"]["text"] == "Разобрала почту и напомнила про торт.", f"дневник — последняя запись сегодня: {r['diary']}")
ok(r["radar"]["trend"]["name"] == "торты без сахара" and r["radar"]["items"][0]["src"] == "РБК", f"Радар — растущая тема и свежее: {r['radar']}")
ok([x["text"] for x in r["next"]] == ["Позвонить маме"], f"«Дальше» — только будущее и не на паузе: {r['next']}")
ok([x["name"] for x in r["leads"]] == ["Анна"] and "contact" not in r["leads"][0], f"заявки — за сутки, без контакта на пульте: {r['leads']}")
ok(r["who"] == "Лира", "имя помощницы")
src = srctext.text(ROOT, "core/engine_commands.py")
ok('if cmd == "pult_data":' in src, "команда pult_data")
ea = srctext.text(ROOT, "core/engine_answer.py")
ok('self.emit("recall", q=shown_q(text)' in ea, "ядро говорит, что подняло к вопросу (событие recall)")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('mode if mode in ("play", "pult")' in app and '"&mode=" + mode' in app, "лист открывается сразу на пульте (pad_toggle('pult'))")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('id="b-pult"' not in hud and "body.rest #corner-l :is(#b-bug, #b-idea" in hud, "значков у виджета не прибавилось (16.11: «иконок стало много»); в отдыхе — только метка")
st = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('data-k="ui.pult_on"' in st, "«Оформление»: пульт выключается совсем")
import settings as S  # noqa: E402
ok(S.DEFAULTS["ui"]["pult_on"] is True and S.DEFAULTS["ui"]["pult_seen"] is False, "по умолчанию пульт есть, карточка «Это Пульт» ещё не показана")

# ---------- окно: блокнот с поддельным ядром ----------
FAKE = """window.apiCalls = []; window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { apiCalls.push([k, ...a]);
  if (k === 'pad_size') return Promise.resolve([440, 560]); return Promise.resolve(true); } }) };"""
DATA = json.dumps({**r, "notes": [{"t": f"Заметка {i}", "f": ["Кухня", "Работа", "Дом"][i % 3], "m": time.time() - i * 7200, "p": ""} for i in range(30)]
                   + [{"t": "Рецепт торта", "f": "Кухня", "m": time.time() - 100, "p": ""}],
                   "leads": [{"ts": int(time.time()) - 7200, "name": "Старая", "cid": "c0"}]}, ensure_ascii=False)
CORE = r"""
(() => { window.calls = []; window.UI = %s;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }, { name: "Покупки", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: "Купить молоко\n", mtime: 1 };
      if (c === "pult_data") return %s;
      return {}; };
    setTimeout(() => core.emit("hello", { settings: { ui: UI, features: {} } }), 250); };
  ready(); })();
"""
URL = (ROOT / "ui/pad.html").as_uri() + "?skin=SKIN&cfg=" + urllib.parse.quote(json.dumps({"side": "left", "gap": 14, "clips": []}))
SHOT = os.environ.get("PULT_SHOTS", "")


def page(b, skin="neusky", ui=None):
    pg = b.new_page(viewport={"width": 454, "height": 620})
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda q: q.abort())
    pg.add_init_script(FAKE)
    pg.add_init_script(CORE % (json.dumps(dict({"skin": skin}, **(ui or {}))), DATA))
    pg.goto(URL.replace("SKIN", skin))
    pg.wait_for_timeout(1100)
    return pg


def shot(pg, name):
    if SHOT:
        pg.screenshot(path=f"{SHOT}/{name}.png")


def think(pg, q="Что у меня по торту на субботу?", notes=("Рецепт торта",)):
    pg.evaluate(f"""core.emit("heard", {{ text: {json.dumps(q)} }}); core.emit("state", {{ state: "thinking" }});
                   core.emit("recall", {{ q: {json.dumps(q)}, notes: {json.dumps(list(notes), ensure_ascii=False)}, memory: ["Обо мне"] }});
                   core.emit("tool", {{ name: "calendar", title: "Смотрю календарь", status: "run" }});""")
    pg.wait_for_timeout(500)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = page(b, ui={"pult_seen": False})
    first = pg.evaluate("document.querySelector('#top').firstElementChild.id")
    ok(first == "pt-tab" and pg.is_visible("#pt-tab") and pg.inner_text("#pt-tab").strip() == "Пульт", f"«Пульт» — первая вкладка: {first}")
    ok(not pg.is_visible("#pult") and pg.is_visible("#ed"), "сначала — ваша заметка, пульт ждёт")
    pg.click("#pt-tab"); pg.wait_for_timeout(600)
    ok(pg.is_visible("#pult") and not pg.is_visible("#ed") and not pg.is_visible("#foot") and pg.evaluate("document.body.classList.contains('pult')"),
       "нажали — пульт вместо листа")
    ok(["pad_mode_mark", "pult"] in pg.evaluate("apiCalls"), "виджет узнаёт, что открыт пульт (подсветка значка)")
    ok(pg.is_visible("#pu-ob") and "Это Пульт" in pg.inner_text("#pu-ob"), "первый раз — карточка «Это Пульт»")
    shot(pg, "onboard")
    pg.click("#pu-ob-ok"); pg.wait_for_timeout(200)
    ok(not pg.is_visible("#pu-ob") and any(c[0] == "settings_save" and c[1]["patch"]["ui"].get("pult_seen") for c in pg.evaluate("calls")), "«Понятно» — больше не показывается")
    n = pg.evaluate("document.querySelectorAll('#pu-sky .pu-ev .e').length")
    ok(n == len(r["day"]) and n >= 3, f"циферблат дня: точка на каждое событие суток — дневник, Радар, заявка, дела ({n} из {len(r['day'])})")
    ok(pg.evaluate("document.querySelector('.pu-time').textContent").count(":") == 1 and "Позвонить маме" in pg.inner_text("#pu-center"),
       "в центре — время и что дальше")
    pg.hover("#pu-sky .pu-ev .e.remind .hit", force=True); pg.wait_for_timeout(150)
    ok(pg.is_visible(".pu-tip") and "Позвонить маме" in pg.inner_text(".pu-tip") and "через" in pg.inner_text(".pu-tip"), "наведение — что это и через сколько")
    pg.click("#pu-sky .pu-ev .e.remind .hit", force=True); pg.wait_for_timeout(150)
    ok(["open_settings", "reminders"] in pg.evaluate("apiCalls"), "нажатие — открывает в студии")
    cards = pg.evaluate("[...document.querySelectorAll('#pu-cards .pu-card')].map(c => c.className)")
    ok(cards == ["pu-card diary", "pu-card radar", "pu-card next"], f"фон: дневник, Радар, «Дальше»: {cards}")
    ok("торты без сахара" in pg.inner_text("#pu-cards") and "Позвонить маме" in pg.inner_text("#pu-cards") and "Разобрала почту" in pg.inner_text("#pu-cards"),
       "в карточках — настоящее из ядра")
    ok(not pg.is_visible("#pu-lead"), "старая заявка (2 ч назад, уже видели) — не всплывает")
    shot(pg, "idle")
    think(pg)
    ok(pg.is_visible("#pu-q") and "по торту" in pg.inner_text("#pu-qt") and not pg.is_visible("#pu-cards"), "думает: вопрос в центре, фон убран")
    steps = pg.inner_text("#pu-steps")
    ok("Подняла заметку «Рецепт торта»" in steps and "Смотрю календарь" in steps and "из памяти" in steps, f"шаги — настоящие: {steps!r}")
    ok(pg.evaluate("document.querySelectorAll('#pu-sky .pu-sweep').length") == 1 and not pg.is_visible("#pu-center"),
       "думает: по кругу бежит свет, в центре — вопрос вместо часов")
    rq = pg.evaluate("(() => { const q = document.getElementById('pu-q'), r = q.getBoundingClientRect(), cs = getComputedStyle(q); return [Math.round(r.width), Math.round(r.height), cs.borderTopLeftRadius]; })()")
    ok(abs(rq[0] - rq[1]) <= 2 and rq[2] == "50%", f"владелец 21.11 «квадрат в круге»: вопрос — в круглой линзе посреди циферблата: {rq}")
    shot(pg, "think")
    pg.evaluate('core.emit("tool", { name: "calendar", title: "Нашла в календаре", status: "done" }); core.emit("state", { state: "speaking" })'); pg.wait_for_timeout(200)
    ok("Нашла в календаре" in pg.inner_text("#pu-steps") and "Смотрю календарь" not in pg.inner_text("#pu-steps"), "шаг обновился на месте, а не продублировался")
    pg.evaluate('core.emit("state", { state: "listening" })'); pg.wait_for_timeout(4600)
    ok(pg.is_visible("#pult"), "сами открыли пульт — он остаётся и после ответа")

    # ---- сам открывается и возвращает ----
    pg.click("#tabs .tab:nth-child(2)"); pg.wait_for_timeout(400)
    ok(not pg.is_visible("#pult") and pg.is_visible("#ed"), "своя вкладка — пульт уступает место")
    pg.wait_for_timeout(5200)
    think(pg, "Какая погода завтра?", ())
    ok(pg.is_visible("#pult") and pg.is_visible("#pu-q"), "Лира думает, вы не печатаете — пульт открылся сам")
    pg.evaluate('core.emit("state", { state: "speaking" })'); pg.wait_for_timeout(300)
    pg.evaluate('core.emit("state", { state: "listening" })'); pg.wait_for_timeout(2500)
    ok(pg.is_visible("#pult"), "ответила — пульт ещё виден 4 с")
    pg.wait_for_timeout(2000)
    ok(not pg.is_visible("#pult") and pg.is_visible("#ed") and pg.evaluate("document.activeElement.id") == "ed", "через 4 с — назад на вашу вкладку, курсор в тексте")

    # ---- печатаете — не перехватывает ----
    pg.click("#ed"); pg.keyboard.type("ещё хлеб")
    think(pg, "Сколько стоит доллар?", ())
    ok(not pg.is_visible("#pult") and pg.is_visible("#pu-strip") and pg.evaluate("document.querySelector('#pt-tab').classList.contains('live')"),
       "печатаете — пульт не открылся: на вкладке дышит точка, внизу живая полоса")
    ok("Смотрю календарь" in pg.inner_text("#pu-strip") or "думает" in pg.inner_text("#pu-strip"), f"в полосе — что делает: {pg.inner_text('#pu-strip')!r}")
    shot(pg, "strip")
    pg.click("#pu-strip-go"); pg.wait_for_timeout(300)
    ok(pg.is_visible("#pult"), "«Открыть пульт» из полосы")
    pg.evaluate('core.emit("state", { state: "idle" })'); pg.wait_for_timeout(300)

    # ---- заявка ----
    pg.evaluate(f'core.emit("sitechat", {{ recent: [{{ ts: {int(time.time() * 1000)}, name: "Анна", contact: "+7", cid: "c9" }}] }})'); pg.wait_for_timeout(500)
    ok(pg.is_visible("#pu-lead") and "Анна" in pg.inner_text("#pu-lead") and "+7" not in pg.inner_text("#pu-lead"), "новая заявка — зелёная карточка сверху, контакт — в «Клиентах»")
    shot(pg, "lead")
    pg.click("#pu-lead [data-go]")
    ok(["open_settings", "clients"] in pg.evaluate("apiCalls"), "«Открыть в «Клиентах»»")

    # ---- шестерёнка ----
    pg.click("#pu-gear"); pg.wait_for_timeout(200)
    ok(pg.is_visible("#pu-pop") and pg.evaluate("document.querySelectorAll('#pu-pop input').length") == 3, "что показывать — на самой вкладке")
    shot(pg, "settings")
    pg.click("#pu-pop label:nth-child(2)"); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelectorAll('#pu-cards .pu-card').length") == 0
       and any(c[0] == "settings_save" and c[1]["patch"]["ui"].get("pult", {}).get("background") is False for c in pg.evaluate("calls")), "фоновые дела выключили — карточек нет, выбор сохранён")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    ok(not pg.is_visible("#pu-pop") and pg.is_visible("#pult"), "Esc закрывает настройки, лист остаётся")
    pg.evaluate('core.emit("settings", { settings: { ui: { pult_on: false } } })'); pg.wait_for_timeout(200)
    ok(not pg.is_visible("#pt-tab") and not pg.is_visible("#pult") and pg.is_visible("#ed"), "выключили в «Оформлении» — вкладки нет")
    ok(not pg.errs, f"без ошибок на странице: {pg.errs}")
    pg.close()

    # тёмная тема и «тихое» движение
    pg = page(b, skin="brand", ui={"pult_seen": True, "pult": {"motion": "calm"}})
    pg.click("#pt-tab"); pg.wait_for_timeout(500)
    think(pg)
    ok(pg.evaluate("document.body.classList.contains('pu-calm')") and pg.evaluate("getComputedStyle(document.querySelector('#pu-steps li.run i') || document.body).animationName") in ("none", ""),
       "«тихое» движение — без анимации")
    shot(pg, "dark")
    ok(not pg.errs, f"тёмная тема без ошибок: {pg.errs}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
