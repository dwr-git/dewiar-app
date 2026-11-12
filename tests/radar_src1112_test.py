"""«Радар»: источники, в которых ничего не находится (владелец, 12.11: «добавил два источника — пару часов ни одной
новости»). Ссылка из веб-Telegram (web.telegram.org/a/#-100…) читалась как сайт, «Моя лента» Хабра (habr.com/ru/feed/)
— как RSS, обе давали ноль материалов, а студия писала «прочитан». Теперь: веб-Telegram с @каналом — канал, с номером —
понятный отказ; «лента», оказавшаяся страницей, — лента со страницы или ссылки на статьи; старые источники при обходе
определяются заново; ноль найденного — «ничего не нашлось» с подсказкой, кнопка «Прочитать сейчас» говорит, сколько нашлось."""
import json, os, sys, tempfile, time, types
from pathlib import Path
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

# --- detect ---
d = I.detect("https://web.telegram.org/a/#-1001720833502")
ok(d and d.get("bad") == "tg_web", f"веб-Telegram с номером канала — понятный отказ: {d}")
d = I.detect("https://web.telegram.org/k/#@ai_newz")
ok(d and d["kind"] == "telegram" and d["feed"] == "https://t.me/s/ai_newz" and not d.get("bad"), f"веб-Telegram с @каналом — канал: {d}")
d = I.detect("https://web.telegram.org/a/#ai_newz")
ok(d and d["feed"] == "https://t.me/s/ai_newz", "веб-Telegram с именем без @ — канал")
d = I.detect("https://habr.com/ru/feed/")
ok(d["kind"] == "rss" and d["feed"] == "https://habr.com/ru/rss/articles/?fl=ru" and d["name"] == "Хабр", f"«Моя лента» Хабра — RSS статей: {d}")
d = I.detect("https://habr.com/en/feed")
ok(d["feed"] == "https://habr.com/en/rss/articles/?fl=en", "Хабр по-английски — своя лента")
ok(I.detect("https://habr.com/ru/rss/all/all/")["feed"] == "https://habr.com/ru/rss/all/all/", "настоящий RSS Хабра — как был")
ok(I.looks_html("<!doctype html><html><body><div>x</div></body></html>") and not I.looks_html('<?xml version="1.0"?><rss><channel></channel></rss>'),
   "страница отличается от ленты")

# --- добавление ---
st = I.Store(tmp / "add")
added, bad, why = st.add_sources("https://web.telegram.org/a/#-1001720833502 https://habr.com/ru/feed/ мусор")
ok([s["name"] for s in added] == ["Хабр"] and set(bad) == {"https://web.telegram.org/a/#-1001720833502", "мусор"}
   and why == {"https://web.telegram.org/a/#-1001720833502": "tg_web"}, f"добавление: Хабр — да, веб-Telegram — с причиной: {added} {bad} {why}")
ok(added[0]["v"] == I.DETECT_V, "новый источник помечен версией определения")

# --- обход ---
NOW = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(time.time() - 3600))
RSS = f"""<?xml version="1.0"?><rss><channel><item><title>Статья раз</title><link>https://habr.com/ru/articles/1/</link><pubDate>{NOW}</pubDate>
<description>Текст</description></item><item><title>Статья два</title><link>https://habr.com/ru/articles/2/</link><pubDate>{NOW}</pubDate></item></channel></rss>"""
HABR_PAGE = "<!doctype html><html><head><title>Моя лента</title></head><body><div>Войдите, чтобы увидеть ленту</div></body></html>"
ALT_PAGE = ('<!doctype html><html><head><link rel="alternate" type="application/rss+xml" href="https://ex.by/real.xml"></head>'
            "<body><div>новости</div></body></html>")
LINKS_PAGE = ("<!doctype html><html><body><div>" + "".join(f'<a href="/news/2026/11/kak-my-pereehali-na-novyj-server-{k}">Как мы переехали '
              f"на новый сервер, часть {k}</a>" for k in range(1, 4)) + "</div></body></html>")
TG_WEB_APP = "<!doctype html><html><head><title>Telegram Web</title></head><body><div id=root></div></body></html>"
TG_EMPTY = "<!doctype html><html><body><div class=tgme_page>Если у вас есть Telegram, вы можете связаться</div></body></html>"
PAGES = {"https://habr.com/ru/rss/articles/?fl=ru": RSS, "https://habr.com/ru/feed/": HABR_PAGE,
         "https://ex.by/rss": ALT_PAGE, "https://ex.by/real.xml": RSS.replace("habr.com/ru/articles", "ex.by/n"),
         "https://ex2.by/feed": LINKS_PAGE, "https://web.telegram.org/a/#-1001720833502": TG_WEB_APP, "https://t.me/s/closedchan": TG_EMPTY}
got = []


class S:
    d = {"insight": {}, "ui": {"lang": "ru"}}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]
    def active_llm(self): return {}


eng = types.SimpleNamespace(s=S(), emit=lambda *a, **k: None, push=lambda *a, **k: None)
r = EI.Radar(eng, tmp / "r")
r.fetch = lambda url: (got.append(url), PAGES[url])[1]
eng.insight = r
# источники так, как их сохранил прежний Радар (без версии определения) — как у владельца
old = [{"id": "tgweb", "kind": "site", "url": "https://web.telegram.org/a/#-1001720833502", "feed": "", "name": "web.telegram.org", "on": True, "last": 0, "err": ""},
       {"id": "habr", "kind": "rss", "url": "https://habr.com/ru/feed/", "feed": "https://habr.com/ru/feed/", "name": "habr.com", "on": True, "last": 0, "err": ""},
       {"id": "alt", "kind": "rss", "url": "https://ex.by/rss", "feed": "https://ex.by/rss", "name": "ex.by", "on": True, "last": 0, "err": "", "v": 2},
       {"id": "links", "kind": "rss", "url": "https://ex2.by/feed", "feed": "https://ex2.by/feed", "name": "ex2.by", "on": True, "last": 0, "err": "", "v": 2},
       {"id": "closed", "kind": "telegram", "url": "https://t.me/closedchan", "feed": "https://t.me/s/closedchan", "name": "@closedchan", "on": True, "last": 0, "err": "", "v": 2}]
r.st.save("sources", old)
r.crawl(force=True)
src = {s["id"]: s for s in r.sources_view()}
ok(src["tgweb"]["err"] == "@tg_web" and "https://web.telegram.org/a/#-1001720833502" not in got,
   f"старый веб-Telegram: не «прочитан», а понятная ошибка, страница даже не открывается: {src['tgweb']}")
h = src["habr"]
ok(h["feed"] == "https://habr.com/ru/rss/articles/?fl=ru" and h["name"] == "Хабр" and h["found"] == 2 and h["last_new"] == 2 and h["v"] == I.DETECT_V,
   f"старый «Моя лента» Хабра: определён заново, читается лента статей, 2 материала: {h}")
ok("https://habr.com/ru/feed/" not in got, "страница «Моя лента» больше не открывается")
a = src["alt"]
ok(a["feed"] == "https://ex.by/real.xml" and a["found"] == 2, f"RSS-адрес оказался страницей — лента найдена в ней и запомнена: {a}")
ok(src["links"]["found"] == 3, f"RSS-адрес оказался страницей без ленты — ссылки на статьи: {src['links']}")
ok(src["closed"]["found"] == 0 and not src["closed"]["err"], "закрытый канал: обход прошёл, нашлось 0 — это видно")
ok(len([x for x in r.st.items()]) == 7, "материалы в очереди на разбор")

# --- «Прочитать сейчас» ---
c = EI.command(eng, "insight_src", {"id": "habr", "crawl": True})
ok(c["found"] == 2 and c["new"] == 0, f"«Прочитать сейчас»: сколько нашлось и сколько нового: {c.get('found')}/{c.get('new')}")
c = EI.command(eng, "insight_src", {"id": "tgweb", "crawl": True})
ok(c.get("err") == "@tg_web", "«Прочитать сейчас» на веб-Telegram — объяснение, а не сырая ошибка")
c = EI.command(eng, "insight_src", {"id": "closed", "crawl": True})
ok(c["found"] == 0, "«Прочитать сейчас» на пустом — 0")
add = EI.command(eng, "insight_add", {"text": "https://web.telegram.org/a/#-100123"})
ok(add["why"] == {"https://web.telegram.org/a/#-100123": "tg_web"} and not add["added"], "команда добавления отдаёт причину")

# --- студия ---
from playwright.sync_api import sync_playwright  # noqa: E402
R = {"insight_sources": EI.command(eng, "insight_sources", {}), "insight_pulse": EI.command(eng, "insight_pulse", {}),
     "insight_src": {"sources": EI.command(eng, "insight_sources", {})["sources"], "found": 0, "new": 0},
     "insight_add": add}


def run(lang):
    core = """(() => { const R = %s; const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true; core.call = async (c, a) => (c in R ? R[c] : null); }; ready(); })();""" % json.dumps(R, ensure_ascii=False)
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        pg = b.new_page(viewport={"width": 1300, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", lambda q: q.abort() if q.request.url.startswith("http") else q.continue_())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(core)
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?port=1&lang={lang}"); pg.wait_for_timeout(900)
        pg.evaluate("window.dwSetLang && dwSetLang('%s')" % lang)
        pg.evaluate("document.querySelector('nav button[data-p=insight]').click()"); pg.wait_for_timeout(600)
        pg.evaluate("document.querySelector('#rd-tabs button[data-t=sources]').click()"); pg.wait_for_timeout(600)
        out["rows"] = pg.evaluate("[...document.querySelectorAll('#rd-sources tr[data-id]')].map(t => [t.dataset.id, t.children[2].innerText])")
        out["warn"] = pg.evaluate("document.querySelectorAll('#rd-sources .rd-state.warn').length")
        if os.environ.get("SHOT"):
            pg.locator("#rd-sources .rd-srcs").screenshot(path=os.environ["SHOT"] + f"-{lang}.png")
        pg.evaluate("document.querySelector('#rd-sources tr[data-id=closed] [data-crawl]').click()"); pg.wait_for_timeout(400)
        out["toast"] = pg.evaluate("[...document.querySelectorAll('.toast, #toast, [class*=toast]')].map(x => x.innerText).join(' | ')")
        out["errs"] = [e for e in errs if "insight" in e]
        b.close()
    return out


ru, en = run("ru"), run("en")
rows = dict(ru["rows"])
ok(not ru["errs"] and not en["errs"], f"страница без ошибок: {ru['errs'][:2]} {en['errs'][:2]}")
ok("веб-версии Telegram" in rows["tgweb"] and "t.me/имя" in rows["tgweb"], f"веб-Telegram — видно, что делать: {rows['tgweb']!r}")
ok("ничего не нашлось" in rows["closed"] and "закрытый" in rows["closed"], f"закрытый канал — «ничего не нашлось» и почему: {rows['closed']!r}")
ok("прочитан" in rows["habr"] and "ничего" not in rows["habr"], f"Хабр — прочитан: {rows['habr']!r}")
ok(ru["warn"] == 1, "предупреждение — только у пустого")
ok("Ничего не нашлось" in ru["toast"], f"«Прочитать сейчас» на пустом — так и говорит: {ru['toast']!r}")
en_rows = dict(en["rows"])
ok("Telegram Web" in en_rows["tgweb"] and "nothing found" in en_rows["closed"] and "insight." not in json.dumps(en["rows"]), f"по-английски: {en_rows}")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
