"""Плагины (решение владельца 20.10: «скилы отдельно, mcp отдельно — красиво скомпоновать и приправить возможностями»;
«больше разнообразных полезных примеров», без Obsidian — чтобы не путать с синхронизацией).
Плагин = навык + MCP + настройки + фразы + дела по расписанию, одной кнопкой (core/plugins.py, студия → «Плагины»):
— восемь встроенных: Кухня, Курсы и цены, Сказка на ночь, Учитель английского, Путешествие, Дача, Дайджест, Проверка договора;
— установили — навык виден модели, настройки плагина приходят вместе с текстом навыка; удалили — навык, MCP и дела уходят;
— дело по расписанию — с настройками в тексте («{city}» → «Минск»), снимается вместе с плагином;
— свой плагин из zip: опасные пути и подмена встроенного отвергаются, MCP-сервер появляется с пометкой плагина;
— студия: каталог карточками, панель плагина, установка с настройками, «Как сделать свой плагин»."""
import base64, io, json, os, re, sys, tempfile, types, zipfile
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


import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import skills as SK  # noqa: E402
import tools as T  # noqa: E402
import engine_commands as EC  # noqa: E402

s = ST.Settings(tmp / "s.json")
P = PL.Plugins(s); K = SK.Skills(s); K.plugins = P; K.reload()
ids = sorted(P.items)
BUILTIN = ["bedtime", "contract", "dacha", "digest", "english", "kitchen", "rates", "travel", "tenders", "recruiter", "artist"]   # + «Тендеры», «Рекрутер», «Художник» (31.10)
ok(ids == sorted(BUILTIN) and "obsidian" not in ids, f"встроенные, без Obsidian: {ids}")
bad = [pid for pid, p in P.items.items() if not (p["skill_dirs"] and p["phrases"] and p["tagline"] and p["description"] and p["icon"] and (p["dir"] / "README.md").is_file())]
ok(not bad, f"у каждого — навык, фразы, описание, значок и README: {bad}")
used = {u for p in P.items.values() for u in p["uses"]}
ok(used <= set(T.TOOLS), f"плагины опираются только на настоящие инструменты помощницы: {used - set(T.TOOLS)}")
ok(all(re.search(r"\{(\w+)\}", j["task"]) is None or all(k in {x["key"] for x in p["settings"]} for k in re.findall(r"\{(\w+)\}", j["task"]))
       for p in P.items.values() for j in p["jobs"]), "подстановки в делах — только из настроек своего плагина")
ok(not [x for x in K.catalog() if x["plugin"]], "пока не установлены — их навыков у модели нет")

# ── установка с настройками ──
P.install("bedtime", {"child": "Маша", "age": "4–5 лет", "loves": "кот Барсик", "zzz": "лишнее", })
K.reload()
ok("bedtime-story" in K.prompt() and [x["name"] for x in K.catalog() if x["plugin"]] == ["bedtime-story"], "установили — навык «Сказки» виден модели")
txt = K.use("bedtime-story")
ok("Настройки плагина «Сказка на ночь»: Имя ребёнка — Маша; Возраст — 4–5 лет; Что любит — кот Барсик." in txt and "zzz" not in txt,
   "настройки приходят вместе с текстом навыка (лишние поля отброшены)")
P.set_values("bedtime", {"age": "100 лет"})
ok(P.values("bedtime")["age"] == "4–5 лет", "в списке выбора — только свои варианты")

# ── дело по расписанию через ядро ──
rem = T.Reminders(lambda *a: None)
me = types.SimpleNamespace(plugins=P, skills=K, s=s, reminders=rem, mcp=types.SimpleNamespace(reconcile=lambda: None))
cmd = lambda c, a=None: EC.CommandsMixin._plugin_cmd(me, c, a or {})
r = cmd("plugin_install", {"id": "dacha", "values": {"city": "Минск", "grows": "томаты и огурцы"}})
r = cmd("plugin_job", {"id": "dacha", "job": "frost", "on": True})
job = [x for x in rem.items if x.get("kind") == "job"]
ok(len(job) == 1 and "Минск" in job[0]["text"] and "томаты и огурцы" in job[0]["text"] and "{" not in job[0]["text"],
   f"дело «Дачи» — с городом и растениями из настроек: {job and job[0]['text'][:90]}")
card = next(x for x in r["plugins"] if x["id"] == "dacha")
ok(card["installed"] and card["jobs"][0]["on"], "в каталоге — установлен, дело включено")
cmd("plugin_job", {"id": "dacha", "job": "frost", "on": False})
ok(not [x for x in rem.items if x.get("kind") == "job"], "выключили дело — снято")
cmd("plugin_job", {"id": "dacha", "job": "frost", "on": True})
r = cmd("plugin_remove", {"id": "dacha"})
ok(not [x for x in rem.items if x.get("kind") == "job"] and "dacha-garden" not in [x["name"] for x in r["skills"]], "удалили плагин — его навык и дело ушли")
ok("guide" in cmd("plugins") and "plugin.json" in cmd("plugins")["guide"], "«Как сделать свой плагин» — в ответе каталога")


# ── свой плагин из zip ──
def mkzip(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, t in files.items():
            z.writestr(n, t)
    return base64.b64encode(b.getvalue()).decode()


man = {"id": "garden-diary", "name": "Дневник сада", "icon": "🌷", "skills": ["garden-diary"], "phrases": ["Запиши: подкормил розы"],
       "settings": [{"key": "city", "label": "Где сад", "type": "text"}],
       "mcp": {"files": {"type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "~/Сад"]}}}
skill = "---\nname: garden-diary\ndescription: Дневник сада — что сделал в саду, когда подкармливал.\n---\nПиши в заметку «Сад»."
r = cmd("plugin_zip", {"zip_b64": mkzip({"garden/plugin.json": json.dumps(man, ensure_ascii=False), "garden/skills/garden-diary/SKILL.md": skill})})
srv = s.get("mcp", "servers") or {}
ok(any(x["id"] == "garden-diary" and x["installed"] and not x["builtin"] for x in r["plugins"]) and "garden-diary" in [x["name"] for x in r["skills"]],
   "свой плагин из zip — установлен, навык работает")
ok(srv.get("garden-diary-files", {}).get("plugin") == "garden-diary" and srv["garden-diary-files"]["command"] == "npx", "его MCP-сервер — в списке MCP с пометкой плагина")
cmd("plugin_remove", {"id": "garden-diary"})
ok("garden-diary-files" not in (s.get("mcp", "servers") or {}), "удалили — MCP-сервер плагина убран")
for files, why in (({"x/plugin.json": json.dumps(dict(man, id="evil")), "x/../../evil.txt": "x"}, "путь с .."),
                   ({"plugin.json": json.dumps(dict(man, id="kitchen")), "skills/a/SKILL.md": skill}, "подмена встроенного"),
                   ({"readme.txt": "нет описания"}, "без plugin.json")):
    try:
        cmd("plugin_zip", {"zip_b64": mkzip(files)}); bad = False
    except ValueError:
        bad = True
    ok(bad and not (tmp / "evil.txt").exists() and P.items["kitchen"]["builtin"], f"отвергнут: {why}")
cmd("plugin_delete", {"id": "garden-diary"})
ok("garden-diary" not in P.items, "свой плагин можно удалить целиком")

# ── студия ──
from playwright.sync_api import sync_playwright  # noqa: E402
cat = json.loads(json.dumps(cmd("plugins"), default=str))
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1280, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept()); pg.add_init_script(FAKE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""(cat) => { S = { mcp: { servers: {} }, skills: {}, ui: {} }; window.calls = [];
      core.call = async (c, a) => { calls.push([c, a]); if (c === 'skills') return []; if (c === 'mcp_status') return {};
        if (c === 'plugin_install') cat.plugins.find(x => x.id === a.id).installed = true; return cat; };
      $('nav button[data-p="skills"]').click(); }""", cat)
    pg.wait_for_timeout(600)
    ok(pg.inner_text('nav button[data-p="skills"]').strip() == "Плагины" and pg.locator("#plg-grid .plg").count() == len(BUILTIN), "раздел «Плагины»: карточка на каждый встроенный")
    ok(pg.locator("#plg-cats .chip").count() >= 6, "категории — фильтром")
    pg.click('#plg-cats .chip[data-c="Семья"]'); ok(pg.locator("#plg-grid .plg").count() == 1, "фильтр «Семья» — одна «Сказка»")
    pg.click('#plg-cats .chip[data-c="Все"]')
    pg.click('#plg-grid .plg[data-id="kitchen"]'); pg.wait_for_timeout(300)
    d = pg.inner_text("#pld")
    ok("Кухня" in d and "Попробуйте сказать" in d and "Настройки" in d and "Дела по расписанию" in d and "Ничего ставить не нужно" in d, "панель плагина: что сказать, настройки, дела, что внутри")
    pg.fill("#pls-diet", "без орехов"); pg.click("#pld-in"); pg.wait_for_timeout(300)
    last = pg.evaluate("calls.filter(c => c[0] === 'plugin_install').pop()")
    ok(last and last[1]["id"] == "kitchen" and last[1]["values"]["diet"] == "без орехов", f"«Установить» — с настройками: {last}")
    ok("Установлен" in pg.inner_text("#pld"), "после установки — «Установлен — просто говорите»")
    pg.keyboard.press("Escape"); pg.click("#plg-guide-b"); pg.wait_for_timeout(300)
    ok(pg.locator("#plg-guide.open table").count() == 1 and pg.locator("#plg-guide pre").count() >= 2, "«Как сделать свой плагин» — с таблицей полей и примерами")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
