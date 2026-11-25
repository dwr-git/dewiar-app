"""Владелец 25.11, плагин «Тендеры» (теперь «Заказы и тендеры»): «добавил ссылку на биржу фриланса — ничего не происходит;
заточено на госзакупки, а нужно универсально; хорошо бы Лира откликалась на заказы». Адрес без {QUERY} молча отбрасывался.
Теперь он — «лента»: страница читается один раз, из неё берутся заказы, где совпали слова запроса; под кнопкой видно,
сколько нашлось и почему ничего. Отклик Лира пишет, отправляет человек (авто-отклики на биржах запрещены)."""
import json, os, shutil, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FX = Path(tempfile.mkdtemp())
shutil.copy(ROOT / "tests/fixtures/tenders/feed.html", FX / "own.html")
os.environ["DEWIAR_TENDERS_FIXTURES"] = str(FX)
os.environ["DEWIAR_PLUGIN_DATA"] = tempfile.mkdtemp()
S = {"queries": "Заказы на создание ИИ ассистентов", "goszakupki": False, "icetrade": False, "own_url": "https://www.fl.ru/projects/"}
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(S, ensure_ascii=False)
sys.path.insert(0, str(ROOT / "data/plugins/tenders"))
import server as TS  # noqa: E402
src = TS.own_sites(S)
ok(len(src) == 1 and src[0].get("feed") and src[0]["name"] == "www.fl.ru", f"адрес без {{QUERY}} — не пропадает, а лента: {src}")
r = TS.scan()
titles = sorted(t["title"] for t in TS.load(TS.STORE, {"items": {}})["items"].values())
ok(titles == ["Голосовой ассистент на базе ИИ для клиники", "Создание ИИ ассистента для интернет-магазина"],
   f"из ленты — только заказы про запрос (логотип и сайт-визитка — нет): {titles}")
ok(r["sources"] == [{"source": "www.fl.ru · лента", "found": 2}], f"под кнопкой видно, откуда и сколько: {r['sources']}")
S2 = dict(S, queries="видеонаблюдение")
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(S2, ensure_ascii=False)
r2 = TS.scan()
ok("ни одного по вашим запросам" in (r2["sources"][0].get("problem") or ""), f"ничего про запрос — сказано почему: {r2['sources']}")
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(dict(S, own_url=""), ensure_ascii=False)
ok("Нет площадок" in (TS.scan().get("error") or ""), "все площадки выключены — понятная подсказка, а не тишина")
ok(TS.own_sites({"own_url": "https://x.by/s?q={QUERY}"})[0].get("feed") is None, "адрес с {QUERY} — как раньше, поиск по каждому запросу")
# ленты RSS (владелец 25.11: «список популярных досок») — честный машинный вход бирж
shutil.copy(ROOT / "tests/fixtures/tenders/feed.rss", FX / "own.html")
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(dict(S, own_url="https://freelancehunt.com/projects.rss"), ensure_ascii=False)
TS.save(TS.STORE, {"items": {}, "gone": []})
r3 = TS.scan()
got = sorted(t["title"] for t in TS.load(TS.STORE, {"items": {}})["items"].values())
ok(got == ["Голосовой помощник для колл-центра", "Чат-бот ИИ ассистент для салона красоты - 15000UAH"],
   f"RSS: заказы по запросу — и по описанию (у «Голосового помощника» «ИИ ассистент» только в описании): {got}")
it = next(t for t in TS.load(TS.STORE, {"items": {}})["items"].values() if t["title"].startswith("Чат-бот"))
ok(it["url"].startswith("https://freelancehunt.com/project/bot/1.html") and it.get("price") == "400 USD", f"ссылка и бюджет из ленты: {it.get('url')} {it.get('price')}")
ok(TS.parse_feed("<html><body>x</body></html>", "https://x.by") is None, "обычная страница — не лента")
ui = (ROOT / "data/plugins/tenders/ui.html").read_text(encoding="utf-8")
ok("const PRESETS" in ui and "freelancer.com/rss.xml" in ui and "freelancehunt.com/projects.rss" in ui and "data-preset" in ui,
   "готовые площадки — одним нажатием")
ok('filter(u => /^https?:\\/\\//.test(u));' in ui and "· лента" in ui and "withQuery(raw) || raw" in ui, "страница плагина принимает любой адрес — как ленту")
ok('id="d-reply"' in ui and "я отправлю сам" in ui, "в карточке заказа — «Написать отклик»")
pj = json.loads((ROOT / "data/plugins/tenders/plugin.json").read_text(encoding="utf-8"))
ok(pj["name"] == "Заказы и тендеры" and "бирж" in pj["tagline"], f"название и описание — не только госзакупки: {pj['name']} · {pj['tagline']}")
ok(any(a["title"] == "Написать отклик" for a in pj["ui"]["asks"]), "«Попросить Лиру» — и отклик")
sk = (ROOT / "data/plugins/tenders/skills/tenders/SKILL.md").read_text(encoding="utf-8")
ok("«Напиши отклик»" in sk and "Сам на бирже ничего не отправляй" in sk, "навык: отклик пишет, отправляет человек")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
