"""«Радар» (владелец 12.11, docs/RADAR.md) — ядро без сети и модели: какая ссылка что за источник, разбор лент (RSS,
Atom, YouTube, Telegram, страница без ленты), хранилище без повторов, разбор ответа модели, тренды «сутки против
нормы», поле сигналов, галактика, срочное, бриф и «эволюция» разума (тезис без ссылок — мимо)."""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import insight as I  # noqa: E402

# источники
d = {x: I.detect(x) for x in ["@ai_newz", "https://t.me/durov", "https://www.youtube.com/@lexfridman", "r/LocalLLaMA",
                              "https://github.com/ollama/ollama/issues", "https://habr.com/ru/rss/all/all/", "vc.ru/ai",
                              "https://vc.ru/ai/1234567-kak-my-zapustili-agenta-v-prodakshen", "https://dzen.ru/tproger", "привет"]}
ok(d["@ai_newz"]["kind"] == "telegram" and d["@ai_newz"]["feed"] == "https://t.me/s/ai_newz", "@канал — Telegram, лента — t.me/s/")
ok(d["https://t.me/durov"]["feed"] == "https://t.me/s/durov", "ссылка t.me — тоже")
ok(d["https://www.youtube.com/@lexfridman"]["kind"] == "youtube" and d["https://www.youtube.com/@lexfridman"]["name"] == "@lexfridman",
   "YouTube-канал по @имени (ленту найдём на странице)")
ok(d["r/LocalLLaMA"]["feed"].endswith("/r/LocalLLaMA/.rss"), "r/… — Reddit с лентой")
ok(d["https://github.com/ollama/ollama/issues"]["feed"] == "https://github.com/ollama/ollama/releases.atom", "GitHub — релизы проекта")
ok(d["https://habr.com/ru/rss/all/all/"]["kind"] == "rss", "адрес ленты — RSS")
ok(d["vc.ru/ai"]["kind"] == "site" and d["https://vc.ru/ai/1234567-kak-my-zapustili-agenta-v-prodakshen"]["kind"] == "article",
   "раздел сайта — сайт, длинный путь — одна статья")
ok(d["https://dzen.ru/tproger"]["kind"] == "dzen" and d["привет"] is None, "Дзен; не ссылка — не источник")
ok(I.find_feed('<head><link rel="alternate" type="application/rss+xml" title="RSS" href="https://www.youtube.com/feeds/videos.xml?channel_id=UC1"></head>',
               "https://www.youtube.com/@x") == "https://www.youtube.com/feeds/videos.xml?channel_id=UC1", "лента на странице канала или сайта находится")

# ленты
rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>Хабр</title>
<item><title>Утечка в PHP: CVE-2026-1234</title><link>https://habr.com/ru/news/1/</link><pubDate>Wed, 11 Nov 2026 10:00:00 +0300</pubDate>
<description><![CDATA[<p>Найдена уязвимость в <b>движке PHP</b>.</p>]]></description></item>
<item><title>Второй</title><link>https://habr.com/ru/news/2/?utm_source=rss</link></item></channel></rss>"""
f = I.parse_feed(rss)
ok(len(f) == 2 and f[0]["title"].startswith("Утечка") and "движке PHP" in f[0]["text"] and f[0]["ts"] > 0, f"RSS: {f[:1]}")
atom = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
<entry><yt:videoId>abc</yt:videoId><title>Интервью о будущем ИИ</title><link rel="alternate" href="https://www.youtube.com/watch?v=abc"/>
<published>2026-11-11T08:00:00+00:00</published><media:group><media:description>Длинное интервью про агентов</media:description></media:group></entry></feed>"""
f = I.parse_feed(atom)
ok(f and f[0]["url"].endswith("v=abc") and f[0].get("video") and "агентов" in f[0]["text"], f"YouTube (Atom + media): {f}")
ok(I.parse_feed("<html>не лента") == [], "не лента — пусто, без падения")
tg = ('<div class="tgme_widget_message js-widget_message" data-post="ai_newz/101"><div class="tgme_widget_message_text js-message_text">'
      'Вышла Gemini 4 Carbon<br/>Модель для агентов в 2–6 раз дешевле конкурентов</div><time datetime="2026-11-11T09:00:00+00:00"></time></div>'
      '<div class="tgme_widget_message js-widget_message" data-post="ai_newz/102"><div class="tgme_widget_message_text">ок</div></div>')
t = I.parse_telegram(tg)
ok(len(t) == 1 and t[0]["title"] == "Вышла Gemini 4 Carbon" and t[0]["url"] == "https://t.me/ai_newz/101", f"Telegram: сообщение — материал: {t}")
page = ('<nav><a href="/about">О нас</a></nav><a href="/ru/articles/555/">Как мы ускорили холодный старт vLLM в 60 раз</a>'
        '<a href="https://other.com/x">Чужая длинная ссылка на совсем другой сайт тут</a>')
pl = I.parse_page_links(page, "https://habr.com/ru/")
ok(len(pl) == 1 and pl[0]["url"] == "https://habr.com/ru/articles/555/", f"сайт без ленты — свои статьи, без меню и чужих: {pl}")
ti, tx = I.article_text("<title>T</title><h1>Заголовок статьи</h1><article><p>" + "Текст абзаца, длинный достаточно. " * 3 + "</p></article>")
ok(ti == "Заголовок статьи" and tx.startswith("Текст абзаца"), "одна статья: заголовок и текст")

# хранилище
st = I.Store(tempfile.mkdtemp())
added, bad, _ = st.add_sources("@ai_newz https://habr.com/ru/rss/all/all/\nнепонятно @ai_newz")
ok(len(added) == 2 and bad == ["непонятно"], f"добавить пачкой: два источника, повтор — мимо, непонятное — назван: {bad}")
src = st.sources()[1]
n1 = st.add_items(src, I.parse_feed(rss))
n2 = st.add_items(src, I.parse_feed(rss.replace("?utm_source=rss", "")))
ok(n1 == 2 and n2 == 0, "повтор материала (та же ссылка без utm) — мимо")
q = st.queue()
ok(len(q) == 2, "очередь разбора — неразобранные")

# разбор
a = I.parse_analysis('<think>…</think>Вот: {"summary": "Уязвимость в PHP 8.4", "why": "Срочно обновить", "type": "incident", '
                     '"tags": ["#PHP", "безопасность", "php"], "entities": ["PHP"], "signal": "9,5"}')
ok(a and a["signal"] == 9.5 and a["tags"] == ["php", "безопасность"] and a["type"] == "incident", f"ответ модели разобран: {a}")
ok(I.parse_analysis("не знаю") is None and I.parse_analysis('{"signal": 5}') is None, "без сути — не разбор")
sy, us = I.analyze_prompt("PHP-разработка", q[0], "en")
ok("JSON" in sy and "English" in sy and "PHP-разработка" in us, "подсказка разбора — на языке человека, с миссией")
st.set_analysis(q[0]["id"], a)
ok(st.queue(10)[0]["id"] == q[1]["id"], "разобранный уходит из очереди")

# тренды, поле, галактика, срочное
now = time.time()
items = []
for day in range(8):
    for k in range(1 if day else 4):
        items.append({"id": f"p{day}{k}", "src": "s1" if k % 2 else "s2", "title": f"PHP {day}{k}", "ts": now - day * 86400 - 3600, "seen": now - day * 86400,
                      "a": {"signal": 6 + k, "tags": ["php", "безопасность"] + (["claude"] if day == 0 and k < 2 else []), "entities": [], "summary": "s", "type": "news"}})
tr = I.trends(items, now)
php = next(t for t in tr if t["name"] == "php")
cl = next(t for t in tr if t["name"] == "claude")
ok(php["day"] == 4 and php["norm"] == 1.0 and php["status"] == "up" and php["spark"][-1] == 4, f"тренд: 4 за сутки при норме 1 — растёт: {php}")
ok(cl["status"] == "new" and tr[0]["impulse"] >= tr[-1]["impulse"], f"раньше не было — новая тема: {cl}")
fl = I.field(items, now)
ok(len(fl) == 10 and all(0 <= p["x"] <= 7 for p in fl), "поле сигналов — точки недели")
g = I.galaxy(items)
ok(g["clusters"] and g["clusters"][0]["name"] in ("php", "безопасность") and len(g["points"]) == len(items), f"галактика: {g['clusters']}")
items[0]["a"]["signal"] = 9.1
u = I.urgent(items, tr, set(), now)
ok(any(x["kind"] == "item" and x["id"] == items[0]["id"] for x in u), "сигнал ≥ 8,5 за последние часы — срочное")
ok(not [x for x in I.urgent(items, tr, {items[0]["id"]}, now) if x.get("id") == items[0]["id"]], "уже сказали — второй раз не говорим")

# бриф и разум
b = I.parse_brief(json.dumps({"headline": "PHP — неделя уязвимостей", "points": ["4 материала за сутки"], "main": [{"id": "p00", "why": "обновиться"}, {"id": "нет", "why": "x"}]}), items)
ok(b and b["headline"].startswith("PHP") and [m["id"] for m in b["main"]] == ["p00"], "бриф: заголовок, пункты; выдуманный id — мимо")
mind = I.apply_evolve({}, json.dumps({"theses": [{"text": "PHP под атакой", "refs": ["p00"]}, {"text": "без ссылок", "refs": []}],
                                      "new_hyps": [{"text": "Выйдет PHP 8.4.15 за неделю", "due": "2026-11-20"}]}), items)
ok(mind["v"] == 1 and [t["text"] for t in mind["theses"]] == ["PHP под атакой"] and mind["hyps"][0]["state"] == "open", f"эволюция: {mind}")
hid = mind["hyps"][0]["id"]
mind = I.apply_evolve(mind, json.dumps({"theses": [], "checks": [{"id": hid, "state": "confirmed", "refs": ["p10"]}]}), items)
ok(mind["v"] == 2 and I.accuracy(mind) == {"confirmed": 1, "refuted": 0, "rate": 1.0} and mind["theses"], "гипотеза подтвердилась — точность 100%, тезисы те же")
ctx = I.ask_context(items, tr, b, mind, "уязвимости php")
ok(ctx["items"] and ctx["brief"]["headline"] and ctx["trends"], "«спросите аналитика»: материалы по словам, бриф, тренды")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
