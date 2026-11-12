"""«Радар»: «читалка» материала и справка «?» (владелец 12.11: «нет вопросика, как во всех разделах, и видео»; «с главной
попадаю во внутренний кабинет Радара, а статью не сразу найти — сразу бы прочитать»). Ядро insight_read — материал и текст
статьи целиком (страница читается сейчас; не открылась — что сохранено; пост Telegram — он сам). Студия: нажатие на
материал в «Ленте», «Пульсе», точку поля, ссылку в ответе — боковая «читалка»; «Главная»: строка сильного сигнала —
сразу в «читалку»; весточка виджета — studioGo("insight:<id>"); у заголовка Радара — «?» со справкой (RU/EN) и уроком."""
import json, os, re, sys, tempfile, time, types
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import insight as I, engine_insight as EI  # noqa: E402

LONG = "".join(f"<p>Абзац {k}: Thinking Machines Lab подробно рассказывает, как обучали модель, сколько стоил запуск и что вышло на тестах.</p>" for k in range(1, 40))
PAGE = f"<html><head><title>T</title></head><body><article><h1>Inkling 2 Small</h1>{LONG}</article></body></html>"


class S:
    d = {"insight": {}, "ui": {"lang": "ru"}}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]
    def active_llm(self): return {}


eng = types.SimpleNamespace(s=S(), emit=lambda *a, **k: None, push=lambda *a, **k: None)
r = EI.Radar(eng, tmp / "r")
got = []
r.fetch = lambda u: (got.append(u), PAGE if "habr" in u else (_ for _ in ()).throw(OSError("нет сети")))[1]
eng.insight = r
TITLE = "[Перевод] 594 млрд параметров, 68 часов предобучения: как создавали Inkling 2 Small"
r.st.add_items({"id": "s1", "name": "habr.com", "kind": "rss"}, [{"title": TITLE, "url": "https://habr.com/ru/articles/1/", "text": "Начало статьи из ленты."}])
r.st.add_items({"id": "s2", "name": "vc.ru", "kind": "site"}, [{"title": "Нет сети", "url": "https://vc.ru/x", "text": "Сохранённое начало."}])
r.st.add_items({"id": "s3", "name": "@ai", "kind": "telegram"}, [{"title": "Пост", "url": "https://t.me/ai/5", "text": "Пост целиком.\nВторая строка."}])
ids = {x["title"]: x["id"] for x in r.st.items()}
for t, i in ids.items():
    r.st.set_analysis(i, {"summary": "Суть: " + t, "why": "Почему важно: дешевле в разы.", "type": "release", "tags": ["llm", "gpu"], "entities": [], "signal": 9.1})
a = EI.command(eng, "insight_read", {"id": ids[TITLE]})["item"]
ok(a["full"] and a["text"].count("\n") >= 30 and "Абзац 39" in a["text"] and a["summary"].startswith("Суть"), f"статья целиком, абзацами, с сутью: {len(a['text'])} знаков")
n = len(got); EI.command(eng, "insight_read", {"id": ids[TITLE]})
ok(len(got) == n, "второй раз — без нового запроса к сайту")
b = EI.command(eng, "insight_read", {"id": ids["Нет сети"]})["item"]
ok(not b["full"] and b["text"] == "Сохранённое начало.", "страница не открылась — сохранённое начало, честно «не целиком»")
c = EI.command(eng, "insight_read", {"id": ids["Пост"]})["item"]
ok(c["full"] and c["text"] == "Пост целиком.\nВторая строка." and "https://t.me/ai/5" not in got, "пост Telegram — он сам, без запроса")
try:
    EI.command(eng, "insight_read", {"id": "nope"}); ok(False, "нет материала — ошибка")
except ValueError as e:
    ok("нет" in str(e), f"нет материала — понятная ошибка: {e}")
ok(len(I.article_text(PAGE)[1]) <= I.TEXT_MAX and len(I.article_text(PAGE, I.READ_MAX)[1]) > I.TEXT_MAX, "для разбора — начало, для читалки — целиком")

# --- студия ---
R = {"insight_pulse": EI.command(eng, "insight_pulse", {}), "insight_feed": EI.command(eng, "insight_feed", {}),
     "insight_read": {"item": a}, "insight_mark": {"ok": True}}
R["insight_pulse"]["stats"]["sources"] = R["insight_pulse"]["stats"]["sources_all"] = 2
CORE = """(() => { const R = %s; window.__calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
  core.connected = true; core.call = async (c, x) => { window.__calls.push([c, x]); return c in R ? R[c] : null; }; }; ready(); })();""" % json.dumps(R, ensure_ascii=False)
errs = []
with sync_playwright() as p:
    br = p.chromium.launch()
    for lang in ("ru", "en"):
        pg = br.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", lambda q: q.abort() if q.request.url.startswith("http") else q.continue_())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?port=1&lang={lang}"); pg.wait_for_timeout(900)
        pg.evaluate("window.dwSetLang && dwSetLang('%s')" % lang)
        pg.evaluate("document.querySelector('nav button[data-p=insight]').click()"); pg.wait_for_timeout(600)
        has = pg.evaluate("!!document.querySelector('#p-insight h1 .hbtn:not(.hb-x)')")
        ok(has, f"{lang}: у заголовка Радара — «?»")
        pg.evaluate("document.querySelector('#p-insight h1 .hbtn:not(.hb-x)').click()"); pg.wait_for_timeout(300)
        hb = pg.evaluate("document.getElementById('help-body').innerText")
        if lang == "ru":
            ok("Радар — Лира следит за вашей темой" in hb and "читалка" in hb and "Что нового в моей теме?" in hb and "help.insight" not in hb, f"справка по-русски: {hb[:90]!r}")
        else:
            ok("Radar — Lira keeps an eye on your field" in hb and "reader" in hb and "help.insight" not in hb, f"справка по-английски: {hb[:90]!r}")
        pg.evaluate("document.getElementById('help').classList.remove('open')")
        if lang == "en":
            pg.close(); continue
        # «Лента» → материал → читалка
        pg.evaluate("document.querySelector('#rd-tabs button[data-t=feed]').click()"); pg.wait_for_timeout(500)
        pg.click(f'#rd-feed [data-rid="{ids[TITLE]}"]'); pg.wait_for_timeout(500)
        rr = pg.evaluate("(() => { const d = document.getElementById('rd-reader'); return d ? {open: d.classList.contains('open'), t: d.innerText, ps: d.querySelectorAll('.rr-text p').length} : {} })()")
        ok(rr.get("open") and TITLE in rr["t"] and "Суть от Лиры" in rr["t"] and "Почему важно" in rr["t"] and rr["ps"] >= 30 and "Открыть оригинал" in rr["t"],
           f"«Лента»: нажатие на материал — читалка с сутью и текстом целиком ({rr.get('ps')} абзацев)")
        if os.environ.get("SHOT"):
            pg.screenshot(path=os.environ["SHOT"])
        ok(not any(c[0] == "open_url" for c in pg.evaluate("window.__calls")), "наружу без спроса не уходит")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        ok(not pg.evaluate("document.getElementById('rd-reader').classList.contains('open')"), "Esc закрывает")
        # «Спросить Лиру» из читалки — вопрос на «Пульсе»
        pg.evaluate(f"rdRead('{ids[TITLE]}')"); pg.wait_for_timeout(400)
        pg.click("#rr-ask"); pg.wait_for_timeout(900)
        qs = [c for c in pg.evaluate("window.__calls") if c[0] == "insight_question"]
        ok(qs and TITLE in qs[-1][1]["q"], f"«Спросить Лиру» — вопрос о материале: {qs[-1][1]['q'][:80] if qs else None!r}")
        # весточка виджета и «Главная» — сразу в читалку
        pg.evaluate("rrClose = null; document.getElementById('rd-reader').classList.remove('open')")
        pg.evaluate("document.querySelector('nav button[data-p=home]').click()"); pg.wait_for_timeout(300)
        pg.evaluate(f"studioGo('insight:{ids[TITLE]}')"); pg.wait_for_timeout(700)
        ok(pg.evaluate("document.querySelector('#p-insight').classList.contains('cur') && document.getElementById('rd-reader').classList.contains('open')"),
           "studioGo(«insight:<id>») — Радар и сразу читалка (весточка виджета)")
        pg.evaluate("document.getElementById('rd-reader').classList.remove('open'); document.querySelector('nav button[data-p=home]').click()"); pg.wait_for_timeout(300)
        pg.evaluate(f"hmGo('insight:{ids[TITLE]}')"); pg.wait_for_timeout(700)
        ok(pg.evaluate("document.getElementById('rd-reader').classList.contains('open')"), "«Главная»: строка сильного сигнала — сразу читалка")
        pg.close()
    br.close()
ok(not [e for e in errs if "insight" in e or "rdRead" in e or "helpOf" in e], f"без ошибок страницы: {errs[:2]}")
home = (ROOT / "ui/studio/home.js").read_text()
ok('sgo: sig ? "insight:" + top.id' in home and "data-sgo" in home, "карточка Радара на «Главной»: строка сигнала ведёт к материалу")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
