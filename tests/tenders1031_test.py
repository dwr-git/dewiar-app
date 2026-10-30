"""Плагин «Тендеры» (владелец 30.10 прислал свой TenderWatch: «тендеры и рекрутер… если получится удачно»). Суть его модуля
перенесена во встроенный плагин со своим кодом (data/plugins/tenders/server.py, MCP по stdio):
— выдача площадки разбирается без модели: повторяющиеся строки (таблица goszakupki с колонками по заголовкам, карточки),
  номер / заказчик / срок / цена; меню, подвал и фильтры сайта — не тендеры; «ничего не найдено» узнаётся;
— отменённые и с прошедшим сроком не приходят; минус-слова отбрасывают, плюс-слова поднимают балл;
— один тендер из двух запросов — одна запись; повторный поиск не приносит старое «новым»; удалённое не возвращается;
— плагин ставится как встроенный: навык, настройки (по умолчанию из plugin.json), дело по будням; сервер отвечает по MCP."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_PLUGIN_DATA"] = str(tmp / "data")
FX = ROOT / "tests/fixtures/tenders"
os.environ["DEWIAR_TENDERS_FIXTURES"] = str(FX)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sys.path.insert(0, str(ROOT / "data/plugins/tenders"))
import server as TS  # noqa: E402

G = {"id": "goszakupki", "name": "goszakupki.by", "base": "https://goszakupki.by"}
rows, how, learn = TS.parse_page((FX / "goszakupki.html").read_text(encoding="utf-8"), G)
ok(how == "auto" and len(rows) == 5 and learn and learn["key"].endswith("|tr."), f"goszakupki: пять строк таблицы, рецепт запомнен: {how} {len(rows)}")
r0 = rows[0]
ok(r0["number"] == "auc0003363836" and r0["title"].startswith("Система централизованного сбора") and r0["organization"].startswith("Государственное учреждение")
   and r0["deadline"] == "20.05.2030" and r0["price"] == "22 395 BYN" and r0["status"] == "Подача предложений"
   and r0["procedure_type"] == "Запрос ценовых предложений" and r0["url"] == "https://goszakupki.by/marketing/view/3363836",
   f"колонки по заголовкам: номер, предмет, заказчик, срок, цена, статус, вид процедуры: {r0}")
ok(not any("Видеонаблюдение" == t["title"] or "Войти" in t["title"] for t in rows), "меню и фильтры сайта — не тендеры")
rows2, how2, _ = TS.parse_page((FX / "goszakupki.html").read_text(encoding="utf-8"), G, learn)
ok(how2 == "recipe" and len(rows2) == 5, "второй раз — по запомненному рецепту")
ok(not TS.is_open(rows[1]) and not TS.is_open(rows[2]) and TS.is_open(rows[0]), "отменённый и с прошедшим сроком — закрыты")
cards, how3, _ = TS.parse_page((FX / "own.html").read_text(encoding="utf-8"), {"id": "own", "base": "https://own.example"})
ok(len(cards) == 3 and cards[0]["organization"].startswith("Государственное учреждение") and cards[0]["number"] == "auc0004561230"
   and cards[0]["deadline"] == "14.11.2030" and cards[0]["price"] == "37 500,00 BYN", f"карточки вместо таблицы — тоже: {cards[:1]}")
ok(TS.parse_page((FX / "own_empty.html").read_text(encoding="utf-8"), G)[1] == "empty", "«ничего не найдено» узнаётся")
ok(TS.stem("видеонаблюдения") == TS.stem("видеонаблюдение"), "основы слов: «видеонаблюдения» = «видеонаблюдение»")

os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps({"queries": "видеонаблюдение; информационной безопасности", "plus": "монтаж; Минск",
                                                   "minus": "продукты питания; ремонт кровли", "own_url": "https://own.example/s?q={QUERY}"})
ok(TS.settings()["min_score"] == 3 and TS.settings()["goszakupki"] is True, "чего нет в карточке — по умолчанию из plugin.json (порог 3)")
r = TS.scan()
titles = [t["title"] for t in r["new_good"]]
ok(r["new"] == 10 and {x["source"]: x["found"] for x in r["sources"]} == {"goszakupki.by": 3, "icetrade.by": 4, "own.example": 3},
   f"три площадки: найдено {r['new']}, {r['sources']}")
ok(not [t for t in titles if "Продукты питания" in t or "Ремонт кровли" in t or "Лицензия на обновление" in t or "Приобретение лицензии" in t],
   "минус-слова, отменённые и просроченные — не приходят")
ok(r["new_good"][0]["title"].startswith("Монтаж системы видеонаблюдения") and r["new_good"][0]["score"] > r["new_good"][-1]["score"],
   f"плюс-слова поднимают выше: {[(t['score'], t['title'][:25]) for t in r['new_good'][:3]]}")
again = TS.scan()
ok(again["new"] == 0 and not again["new_good"], "повторный поиск — старое не приходит «новым»")
L = TS.listing()
ok(L["total"] == 10 and L["items"][0]["score"] >= L["items"][-1]["score"], "в учёте — все непросмотренные, лучшие первыми")
TS.mark([L["items"][0]["id"]], "seen")
ok(TS.listing()["total"] == 9 and TS.listing(only_new=False)["total"] == 10, "просмотренный — уходит из новых, но остаётся в учёте")
gone = L["items"][1]["id"]
TS.mark([gone], "delete")
TS.scan()
ok(gone not in [t["id"] for t in TS.listing(only_new=False, limit=50)["items"]], "удалённый не возвращается при новом поиске")
ok(TS.listing(q="обслуживание видеонаблюдения")["total"] >= 1, "поиск по словам в найденном")
TS.mark("all", "seen")
ok(TS.listing()["total"] == 0, "«отметь все просмотренными»")
os.environ["DEWIAR_PLUGIN_SETTINGS"] = "{}"
ok("Нет запросов" in TS.scan().get("error", ""), "без запросов — понятная подсказка, а не пустота")

# ── MCP по stdio, как его запустит программа ──
env = dict(os.environ, DEWIAR_PLUGIN_SETTINGS=json.dumps({"queries": "видеонаблюдение"}), DEWIAR_PLUGIN_DATA=str(tmp / "d2"))
msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "tenders_scan", "arguments": {}}}]
p = subprocess.run([sys.executable, str(ROOT / "data/plugins/tenders/server.py")], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                   capture_output=True, text=True, env=env, timeout=60)
out = [json.loads(x) for x in p.stdout.splitlines() if x.strip()]
ok(len(out) == 3 and out[0]["result"]["serverInfo"]["name"] == "dewiar-tenders", f"MCP: initialize (уведомление без ответа): {p.stderr[-300:]}")
tl = out[1]["result"]["tools"] if len(out) > 1 else []
ok({t["name"] for t in tl} == {"tenders_scan", "tenders_list", "tenders_mark"} and all(t["annotations"]["readOnlyHint"] for t in tl),
   "три действия, без лишних «Выполнить?»")
res = json.loads(out[2]["result"]["content"][0]["text"]) if len(out) > 2 else {}
ok(res.get("new", 0) >= 5, f"tenders_scan через MCP — находит: {str(res)[:120]}")

# ── встроенный плагин ──
sys.path.insert(0, str(ROOT / "core"))
import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import tools as T  # noqa: E402
import mcp as M  # noqa: E402
s = ST.Settings(tmp / "s.json")
P = PL.Plugins(s)
p = P.items.get("tenders")
ok(p and p["builtin"] and p["skill_dirs"] and p["jobs"][0]["when"] == "по будням в 9" and set(p["uses"]) <= set(T.TOOLS),
   "встроенный плагин: навык, дело по будням, только настоящие инструменты")
P.install("tenders", {"queries": "видеонаблюдение; сервер", "min_score": 4})
cfg = (s.get("mcp", "servers") or {}).get("tenders-main") or {}
x = M.plugin_expand(dict(cfg, _values={"queries": "видеонаблюдение; сервер"}))
ok(x["args"][0].endswith(os.path.join("tenders", "server.py")) and json.loads(x["env"]["DEWIAR_PLUGIN_SETTINGS"])["queries"] == "видеонаблюдение; сервер",
   "сервер плагина запускается Python программы и получает его настройки")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
