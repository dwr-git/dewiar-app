"""«Радар» в движке (engine_insight.py): источники пачкой → обход (лента, сайт без ленты — лента со страницы, Telegram)
→ разбор моделью с лимитом в сутки → бриф → эволюция ночью → срочное весточкой (раз в час) → команды студии и
инструмент модели insight_ask. Сеть и модель — подменные."""
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


import engine_insight as EI  # noqa: E402

RSS = """<rss><channel><item><title>Утечка исходников PHP-движка</title><link>https://habr.com/ru/news/1/</link>
<pubDate>{d}</pubDate><description>Злоумышленники выложили исходники и ключи. Обновитесь.</description></item>
<item><title>Вышел Dart 3.14</title><link>https://habr.com/ru/news/2/</link><pubDate>{d}</pubDate><description>Миграции и Wasm</description></item>
</channel></rss>""".replace("{d}", time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(time.time() - 3600)))
SITE = '<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>'
TG = ('<div class="tgme_widget_message" data-post="ai/5"><div class="tgme_widget_message_text">Gemini 4 Carbon вышла<br/>Агентная модель, '
      'в 2–6 раз дешевле</div><time datetime="2026-11-12T06:00:00+00:00"></time></div>')
PAGES = {"https://example.by/feed.xml": RSS.replace("habr.com/ru/news", "example.by/n"), "https://example.by": SITE,
         "https://habr.com/ru/rss/all/all/": RSS, "https://t.me/s/ai_news": TG}
asked = []


def ask(system, user, max_tokens=700):
    asked.append(system[:30])
    if "brief" in system or "бриф" in system:
        return json.dumps({"headline": "PHP — утечка исходников", "points": ["Утечка", "Dart 3.14"], "main": []})
    if "спокойный аналитик" in system:
        return "**Главное** — утечка исходников PHP [1], рядом Dart [2] и выдуманное [9]."
    if "ведёшь картину" in system or "maintain an expert" in system:
        return json.dumps({"theses": [], "new_hyps": [{"text": "Выйдет патч", "due": "2026-11-30"}]})
    sig = 9.2 if "Утечка" in user else 4
    return json.dumps({"summary": "Суть: " + user.split("Заголовок: ")[-1][:40] if "Заголовок" in user else "Суть",
                       "why": "Важно", "type": "incident" if sig > 9 else "release", "tags": ["php", "безопасность"] if sig > 9 else ["dart"],
                       "entities": ["PHP"] if sig > 9 else ["Dart"], "signal": sig})


class S:
    def __init__(self):
        self.d = {"insight": {}, "ui": {"lang": "ru"}}

    def get(self, sec, key=None):
        v = self.d.get(sec)
        return v if key is None else (v or {}).get(key)

    def update(self, patch):
        for k, v in patch.items():
            self.d.setdefault(k, {}).update(v)

    def active_llm(self):
        return {"kind": "openai"}


pushes, emits = [], []
eng = types.SimpleNamespace(s=S(), emit=lambda t, **kw: emits.append(t), push=lambda title, text="", **kw: pushes.append((title, text, kw)))
r = EI.Radar(eng, tmp / "radar")
r.fetch = lambda url: PAGES[url.rstrip("/") if url.rstrip("/") in PAGES else url]
r._ask = ask
eng.insight = r
res = EI.command(eng, "insight_add", {"text": "https://habr.com/ru/rss/all/all/ example.by @ai_news мусор"})
ok(set(res["added"]) == {"habr.com", "example.by", "@ai_news"} and res["bad"] == ["мусор"], f"источники пачкой: {res['added']} / {res['bad']}")
time.sleep(0.3)
while r.lock.locked():
    time.sleep(0.2)
st = r.stats()
ok(st["total"] == 5 and st["day"] >= 4, f"первый обход (сразу после добавления): лента, лента со страницы сайта, Telegram — {st}")
srcs = {s["name"]: s for s in r.sources_view()}
ok(srcs["example.by"]["feed"] == "https://example.by/feed.xml" and not srcs["example.by"]["err"], "сайт: лента найдена на странице и запомнена")
ok(r.used_today() == 5, "разборы посчитаны за сутки")
b = r.st.load("brief", {})
ok(b.get("headline") == "PHP — утечка исходников", f"бриф дня собран: {b}")
ok(pushes and "⚡" in pushes[0][0] and "Утечка" in pushes[0][1], f"сигнал 9,2 — срочная весточка: {pushes}")
n = len(pushes)
r.urgent()
ok(len(pushes) == n, "срочное — не чаще раза в час")
# лимит в сутки
r.set_conf({"daily_max": 5})
r.st.add_items({"id": "x", "name": "x"}, [{"title": "Ещё материал про PHP", "url": "https://x/1", "text": "t"}])
ok(r.analyze(10) == 0, "лимит разборов в сутки — дальше не разбираем")
# студия
p = EI.command(eng, "insight_pulse", {})
ok(p["brief"]["headline"] and p["field"] and p["trends"] is not None and p["stats"]["sources"] == 3, "«Пульс»: бриф, поле сигналов, тренды, счётчики")
f = EI.command(eng, "insight_feed", {"q": "php", "sort": "signal"})
ok(f["items"] and f["items"][0]["signal"] == 9.2 and f["items"][0]["tags"] == ["php", "безопасность"], "«Лента»: поиск и сортировка по сигналу")
iid = f["items"][0]["id"]
EI.command(eng, "insight_mark", {"id": iid, "fb": 1, "watch": True})
ok(EI.command(eng, "insight_feed", {"watch": True})["items"][0]["watch"], "«Наблюдаемое» — отмечено и находится")
m = EI.command(eng, "insight_mission", {"text": "Веб-разработка на PHP, безопасность"})
ok(m["mission"].startswith("Веб-разработка") and m["watch"], "«Разум»: миссия сохранена, наблюдаемое видно")
r.evolve()
m = EI.command(eng, "insight_mind", {})
ok(m["v"] == 1 and m["hyps"] and m["hyps"][0]["state"] == "open", f"эволюция: гипотеза поставлена: {m['hyps']}")
g = EI.command(eng, "insight_galaxy", {})
ok(g["clusters"] and len(g["points"]) == 5, "«Галактика»: созвездия и точки")
sid = srcs["@ai_news"]["id"]
EI.command(eng, "insight_src", {"id": sid, "on": False})
ok(not next(s for s in r.sources_view() if s["id"] == sid)["on"], "источник выключается")
EI.command(eng, "insight_src", {"id": sid, "del": True})
ok(sid not in {s["id"] for s in r.sources_view()}, "источник удаляется")
t = EI.ask_tool(eng, "php")
ok(t["items"] and t["items"][0]["signal"] == 9.2 and t["brief"]["headline"], "insight_ask: по теме — материалы, бриф, тренды")
qa_ = EI.command(eng, "insight_question", {"q": "что с PHP?"})
ok(qa_["text"].startswith("Главное") and "**" not in qa_["text"] and "[9]" not in qa_["text"] and [x["n"] for x in qa_["refs"]] == [1, 2]
   and qa_["refs"][0]["url"], f"«Спросите Лиру о теме»: ответ по материалам, ссылки [n] — только настоящие: {qa_}")
eng2 = types.SimpleNamespace(s=S(), emit=lambda *a, **k: None, push=lambda *a, **k: None)
eng2.insight = EI.Radar(eng2, tmp / "empty")
ok("не настроен" in EI.ask_tool(eng2, "")["empty"], "источников нет — модель скажет, как настроить")
ok("не настроен" in EI.command(eng2, "insight_question", {"q": "что нового?"})["text"], "вопрос без источников — подсказка, как начать")
import tools as T  # noqa: E402
ok("insight_ask" in T.TOOLS and T.TOOLS["insight_ask"][2] == "safe", "инструмент модели есть и безопасный")
ec = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
en = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok('cmd.startswith("insight_")' in ec and "engine_insight.radar(self).loop" in en, "команды студии и фоновый обход подключены")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
