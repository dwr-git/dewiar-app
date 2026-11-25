"""Плагин «Jira команды» (25.11, владелец: «Jira — своя… я бы сейчас сделал плагин», прислал свою «Аналитику Jira»).

Поддельная Jira (свой сервер, токен Bearer) на localhost: 130 задач с историей статусов —
- загрузка постранично (по 50) и с курсором: не уложились в бюджет — следующий вызов продолжает, задачи не теряются и не
  дублируются; повторная загрузка тянет только изменённое (updated >= прошлый раз − запас);
- «кто сделал» — исполнитель в момент закрытия, а не нынешний и не автор задачи; вехи «взято в работу» и «закрыто»
  по категориям статусов из самой Jira (названия русские);
- одно действие помощницы jira: overview / people / person (имя по-русски → латиница из Jira) / stuck / changes / mine /
  find / issue;
- токен — настройка secret: не попадает в текст навыка и в поручения дел (модель его не видит), поле со звёздочками;
- плохой токен — понятная ошибка, а не трассировка;
- страница плагина: сводка, график, люди, застрявшее — без ошибок, с фальшивым мостом dewiar."""
import json
import re
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PLUG = ROOT / "data/plugins/jira"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


TOKEN = "test-pat-123"
TZ = timezone(timedelta(hours=3))
NOW = datetime.now(TZ)
STATUSES = [{"id": "1", "name": "Backlog", "statusCategory": {"key": "new"}},
            {"id": "3", "name": "В работе", "statusCategory": {"key": "indeterminate"}},
            {"id": "10001", "name": "Готово", "statusCategory": {"key": "done"}}]
ST = {s["id"]: s for s in STATUSES}


def jt(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S.000%z")


def user(n):
    return {"name": n.split()[0].lower(), "displayName": n}


PEOPLE = ["Artyom Kolago", "Maria Kudelevich", "Dmitriy Lepushenko"]


def make_issues():
    out = []
    for i in range(1, 131):
        cr = NOW - timedelta(days=60 - (i % 55), hours=i % 7)
        a = PEOPLE[i % 3]
        hist, st = [], "1"
        if i % 4 != 0:                                           # взяли в работу
            go = cr + timedelta(days=1)
            hist.append({"created": jt(go), "author": user(a), "items": [{"field": "status", "from": "1", "to": "3", "fromString": "Backlog", "toString": "В работе"}]})
            st = "3"
            if i % 4 in (1, 2):                                  # закрыли
                dn = min(go + timedelta(days=2 + i % 5), NOW - timedelta(hours=2))
                hist.append({"created": jt(dn), "author": user(a), "items": [{"field": "status", "from": "3", "to": "10001", "fromString": "В работе", "toString": "Готово"}]})
                st = "10001"
        assignee = a
        if i == 5:                                               # закрыла Мария, потом задачу переназначили на Артёма
            hist.append({"created": jt(NOW - timedelta(hours=1)), "author": user("Artyom Kolago"),
                         "items": [{"field": "assignee", "fromString": "Maria Kudelevich", "toString": "Artyom Kolago"}]})
            assignee = "Artyom Kolago"
        up = max([cr] + [datetime.strptime(h["created"], "%Y-%m-%dT%H:%M:%S.000%z") for h in hist])
        if i == 7:                                               # застряла: в работе давно и без движения
            pass
        out.append({"key": f"AI-{i}", "fields": {
            "summary": f"Задача {i}" + (" — распознавание речи" if i % 10 == 0 else ""), "status": ST[st],
            "assignee": user(assignee), "reporter": user("Isaev Michael"),
            "issuetype": {"name": "Ошибка" if i % 9 == 0 else "Задача"}, "project": {"key": "AI"}, "priority": {"name": "Medium"},
            "created": jt(cr), "updated": jt(up), "resolutiondate": None}, "changelog": {"histories": hist}})
    # отпуска и больничные — обычные задачи (проект HR): даты из названия и из полей «Дата начала / окончания»
    soon = NOW + timedelta(days=5)
    ab = [(f"Отпуск Мария {soon:%d.%m} - {soon + timedelta(days=11):%d.%m}",
           "Maria Kudelevich", None),
          ("Больничный", "Artyom Kolago", (NOW - timedelta(days=2), NOW + timedelta(days=3))),
          ("Отпуск за свой счёт", "Dmitriy Lepushenko", None)]
    for n, (title, who, fld) in enumerate(ab, 1):
        f = {"summary": title, "status": ST["3"], "assignee": user(who), "reporter": user(who), "issuetype": {"name": "Задача"},
             "project": {"key": "HR"}, "priority": {"name": "Medium"}, "created": jt(NOW - timedelta(days=3)), "updated": jt(NOW - timedelta(days=3)), "resolutiondate": None}
        if fld:
            f["customfield_201"], f["customfield_202"] = fld[0].strftime("%Y-%m-%d"), fld[1].strftime("%Y-%m-%d")
        out.append({"key": f"HR-{n}", "fields": f, "changelog": {"histories": []}})
    return out


ISSUES = make_issues()
SEEN = {"search": [], "auth": set()}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        SEEN["auth"].add(self.headers.get("Authorization") or "")
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self.send(401, {"errorMessages": ["no"]})
        if u.path == "/rest/api/2/field":
            return self.send(200, [{"id": "summary", "name": "Summary", "schema": {"type": "string"}},
                                   {"id": "customfield_201", "name": "Дата начала", "schema": {"type": "date"}},
                                   {"id": "customfield_202", "name": "Дата окончания", "schema": {"type": "date"}}])
        if u.path == "/rest/api/2/status":
            return self.send(200, STATUSES)
        if u.path == "/rest/api/2/myself":
            return self.send(200, user("Artyom Kolago"))
        if u.path == "/rest/api/2/serverInfo":
            return self.send(200, {"version": "9.12.4", "deploymentType": "Server", "serverTitle": "Jira"})
        if u.path == "/rest/api/2/search":
            SEEN["search"].append(q)
            jql = q.get("jql", "")
            xs = sorted(ISSUES, key=lambda x: x["fields"]["updated"])
            if 'updated >= "' in jql:
                since = datetime.strptime(jql.split('updated >= "')[1][:16], "%Y/%m/%d %H:%M").replace(tzinfo=TZ)
                xs = [x for x in xs if datetime.strptime(x["fields"]["updated"], "%Y-%m-%dT%H:%M:%S.000%z") >= since]
            at, mx = int(q.get("startAt", 0)), int(q.get("maxResults", 50))
            return self.send(200, {"startAt": at, "maxResults": mx, "total": len(xs), "issues": xs[at:at + mx]})
        if u.path == "/rest/agile/1.0/board/25/configuration":
            return self.send(200, {"id": 25, "name": "AI", "filter": {"id": "100"}})
        if u.path == "/rest/api/2/filter/100":
            return self.send(200, {"id": "100", "jql": "project = AI AND labels = asr ORDER BY Rank ASC"})
        if u.path.startswith("/rest/agile/1.0/board/"):
            return self.send(404, {"errorMessages": ["Board does not exist"]})
        if u.path.startswith("/rest/api/2/issue/"):
            k = u.path.rsplit("/", 1)[1]
            x = next((x for x in ISSUES if x["key"] == k), None)
            if not x:
                return self.send(404, {"errorMessages": ["Issue Does Not Exist"]})
            f = dict(x["fields"], description="Развернуть STT\nс потоковой передачей", labels=["asr"],
                     comment={"comments": [{"author": user("Maria Kudelevich"), "created": jt(NOW), "body": "Готово к ревью"}]})
            return self.send(200, {"key": k, "fields": f})
        self.send(404, {})


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_port}"


class Mcp:
    def __init__(self, data, settings):
        env = dict(os.environ, DEWIAR_PLUGIN_DATA=str(data), DEWIAR_PLUGIN_SETTINGS=json.dumps(settings), NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
        env.pop("HTTPS_PROXY", None); env.pop("HTTP_PROXY", None); env.pop("https_proxy", None); env.pop("http_proxy", None)
        self.p = subprocess.Popen([sys.executable, str(PLUG / "server.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True)
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2024-11-05"})

    def rpc(self, m, params=None):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": m, "params": params or {}}) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())["result"]

    def call(self, name, args=None):
        r = self.rpc("tools/call", {"name": name, "arguments": args or {}})
        t = r["content"][0]["text"]
        return (None, t) if r.get("isError") else (json.loads(t), None)

    def close(self):
        self.p.stdin.close()
        self.p.wait(5)


tmp = Path(tempfile.mkdtemp())
SET = {"url": BASE + "/browse/AI-1", "token": TOKEN, "projects": "AI"}

# ---------- инструменты ----------
m = Mcp(tmp / "a", SET)
tools = m.rpc("tools/list")["tools"]
vis = [t["name"] for t in tools if not (t.get("_meta") or {}).get("dewiar/page")]
ok(vis == ["jira"], f"помощнице видно одно действие jira (подсказка не раздувается): {vis}")
ok(all((t.get("annotations") or {}).get("readOnlyHint") for t in tools), "все действия — только чтение (без «Выполнить?»)")
r, e = m.call("jira_check")
ok(r and r["me"] == "Artyom Kolago" and r["version"] == "9.12.4" and r["type"] == "свой сервер", f"проверка связи: кто я и версия Jira: {r or e}")
ok(SEEN["auth"] == {f"Bearer {TOKEN}"}, "личный токен — заголовком Bearer; ссылка на задачу в адресе понята как адрес Jira")

# ---------- загрузка ----------
import importlib.util  # noqa: E402
os.environ["DEWIAR_PLUGIN_DATA"] = str(tmp / "a")
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(SET)
spec = importlib.util.spec_from_file_location("jira_server", PLUG / "server.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
os.environ.update(NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
for k in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
    os.environ.pop(k, None)
r1 = S.sync(budget=0)                     # бюджет кончился после первой страницы
ok(not r1["done"] and r1["loaded"] == 50 and r1["left"] == 83, f"не уложились — загружено 50, осталось 83, курсор сохранён: {r1}")
r2 = S.sync(budget=999)
ok(r2["done"] and r2["issues"] == 133 and r2["loaded"] == 83, f"продолжили с места обрыва — все 133 задачи, без дублей: {r2}")
ok(all(q["startAt"] in ("0", "50", "100") for q in SEEN["search"]) and all('(project in ("AI"))' in q["jql"] for q in SEEN["search"]),
   "постранично по 50, только проекты из настроек")
n0 = len(SEEN["search"])
r3 = S.sync(budget=999)
q3 = SEEN["search"][n0]
ok('updated >= "' in q3["jql"] and r3["loaded"] < 20, f"повторно — только изменённое (updated >= …): загружено {r3['loaded']}")

d = S.load()
x5, x7, x4 = d["issues"]["AI-5"], d["issues"]["AI-7"], d["issues"]["AI-4"]
ok(x5["by"] == "Maria Kudelevich" and x5["a"] == "Artyom Kolago", f"«сделал» — исполнитель в момент закрытия, а не нынешний: {x5['by']} / {x5['a']}")
ok(x5["go"] and x5["dn"] > x5["go"] and x5["c"] == "done", "вехи: взято в работу → закрыто, по категориям статусов Jira")
ok(x4["c"] == "new" and not x4["go"] and not x4["dn"], "в работу не брали — ни вехи «взято», ни «закрыто»")
ok(x7["c"] == "indeterminate" and not x7["dn"], "в работе — не закрыто")

# ---------- отсутствия ----------
ab = S.absences(d)
ok([(x["who"], x["label"]) for x in ab["now"]] == [("Artyom Kolago", "Больничный")] and ab["items"][0]["src"] in ("поля", "название"),
   f"больничный из полей «Дата начала / окончания» — сейчас: {ab['now']}")
mar = [x for x in ab["items"] if x["who"] == "Maria Kudelevich"]
ok(mar and mar[0]["src"] == "название" and mar[0]["days"] == 12 and mar[0]["label"] == "Отпуск", f"отпуск из названия «дд.мм - дд.мм»: {mar}")
ok(len(ab["loose"]) == 1 and ab["loose"][0]["type"] == "За свой счёт", f"«Отпуск за свой счёт» — свой тип, без дат — в списке нераспознанных: {ab['loose']}")
ok(not any(x["k"].startswith("HR") for x in S.pick(d)), "отпуска — не работа: в сводку, людей и «кто чем занят» не идут")
from datetime import date as _d
for t, want in [("Отпуск 15 - 28 июня", ("2026-06-15", "2026-06-28")), ("28 мая - 10 июня отпуск", ("2026-05-28", "2026-06-10")),
                ("Отпуск 15.06 - 28.06", ("2026-06-15", "2026-06-28")), ("Отпуск с 3 по 14 августа", ("2026-08-03", "2026-08-14")),
                ("Отпуск 28 декабря - 10 января", ("2025-12-28", "2026-01-10"))]:
    r = S.parse_range(t, _d(2026, 5, 20))
    ok(r and (r[0].isoformat(), r[1].isoformat()) == want, f"даты из названия: «{t}» → {r}")
g = S.graph(d)
ok(len(g["nodes"]) == 3 and any(e["w"] for e in g["edges"]) and g["nodes"][0]["team"] == "AI", f"связи: люди, команда и общие задачи: {[(e['a'], e['b'], e['w']) for e in g['edges']]}")

# ---------- ответы помощнице ----------
ov, _ = m.call("jira", {"what": "overview", "days": 30})
ok(ov["total"] == 130 and ov["in_progress"] + ov["todo"] + ov["done"] == 130 and ov["bugs_open"] > 0 and ov["cycle"]["median"] != "—",
   f"сводка: всего, в работе, ждут, закрыто, ошибки, время цикла: {ov['in_progress']}/{ov['todo']}/{ov['done']}, цикл {ov['cycle']}")
ok("weeks" not in ov and len(ov["oldest"]) <= 5, "помощнице — без рядов графика, коротко")
pp, _ = m.call("jira", {"what": "people", "days": 60})
names = [p["name"] for p in pp["people"]]
ok(set(names) == set(PEOPLE) and "Isaev Michael" not in names, f"люди — те, кто делал, а не автор задач: {names}")
pc, _ = m.call("jira", {"what": "person", "q": "Марию", "days": 60})
ok(pc.get("name") == "Maria Kudelevich" and pc["done_count"] > 0, f"«что делала Мария» → Maria Kudelevich: {pc.get('name')}, закрыла {pc.get('done_count')}")
pc2, _ = m.call("jira", {"what": "person", "q": "Артём", "days": 60})
ok(pc2.get("name") == "Artyom Kolago", f"«Артём» → Artyom Kolago: {pc2.get('name')}")
sk, _ = m.call("jira", {"what": "stuck"})
ok(sk["count"] > 0 and all(i["quiet_days"] >= 14 for i in sk["items"]), f"застряло: в работе и без движения 2 недели: {sk['count']}")
mn, _ = m.call("jira", {"what": "mine"})
ok(mn["me"] == "Artyom Kolago" and mn["count"] > 0 and all(i["who"] == "Artyom Kolago" for i in mn["items"]), f"мои задачи: {mn['count']}")
fd, _ = m.call("jira", {"what": "find", "q": "распознавания речи"})
ok(fd["count"] == 13, f"поиск по словам (с окончаниями): {fd['count']}")
iss, _ = m.call("jira", {"what": "issue", "q": "ai-10"})
ok(iss and iss["key"] == "AI-10" and "Готово к ревью" in iss["comments"][0]["text"] and iss["url"].endswith("/browse/AI-10"),
   f"задача подробно — описание и комментарии из Jira: {iss and iss['title']}")
aw, _ = m.call("jira", {"what": "away"})
ok(aw and aw["now"] and aw["next_14_days"] and aw["no_dates"] == 1, f"«кто в отпуске» — сейчас и в ближайшие две недели: {aw}")
ch, _ = m.call("jira", {"what": "changes", "hours": 24 * 3})
ok(isinstance(ch["done"], list) and "new_bugs" in ch, "за сутки: закрыто, взяли, новые")
m.close()

# ---------- доски ----------
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(dict(SET, projects="https://x/secure/RapidBoard.jspa?rapidView=25&projectKey=AI; NSHIELD"))
cfg = S.settings()
ok(cfg["boards"] == [25] and cfg["projects"] == ["NSHIELD"], f"ссылка на доску и ключ проекта вперемешку: {cfg}")
sc = S.scope(cfg)
ok(sc == 'project in ("NSHIELD") OR (project = AI AND labels = asr)', f"доска — её фильтр из Jira, без сортировки доски: {sc}")
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(dict(SET, projects="99"))
try:
    S.scope(S.settings()); e = ""
except S.JiraError as x:
    e = str(x)
ok("доска 99 не открылась" in e and "нет к ней доступа" in e, f"нет доступа к доске — так и сказано: {e}")
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(SET)

# ---------- плохой токен ----------
m2 = Mcp(tmp / "b", dict(SET, token="wrong"))
r, e = m2.call("jira", {"what": "overview"})
ok(r is None and "токен" in e and "Traceback" not in e, f"плохой токен — понятная ошибка: {e}")
r, e = m2.call("jira_check")
ok(r is None and "HTTP 401" in e, "проверка связи говорит, что Jira не пускает")
m2.close()
m3 = Mcp(tmp / "c", {"url": BASE})
r, e = m3.call("jira", {"what": "overview"})
ok(r is None and "нет токена" in e and "Персональные токены" in e, f"нет токена — где его взять: {e}")
m3.close()

# ---------- токен — секрет: модель его не видит ----------
sys.path.insert(0, str(ROOT / "core"))
import plugins as PL  # noqa: E402
man = PL.parse_plugin(PLUG, True)
ok([s["type"] for s in man["settings"]] == ["text", "secret", "text"], "plugin.json: токен — настройка secret")


class FakeS:
    def __init__(self):
        self.d = {"plugins": {"on": {"jira": {"values": {"url": "https://jira.x", "token": TOKEN, "projects": "AI"}, "jobs": {}}}}}

    def get(self, *k):
        v = self.d
        for x in k:
            v = (v or {}).get(x)
        return v

    def update(self, patch):
        pass


P = PL.Plugins.__new__(PL.Plugins)
P.s, P.items = FakeS(), {"jira": man}
note = P.note("jira")
ok("jira.x" in note and TOKEN not in note, f"текст навыка — с адресом, без токена: {note!r}")
task, when = P.job_text("jira", "morning")
ok(TOKEN not in task and when == "по будням в 9:30", "поручение дела — без токена")
cl = PL.Plugins._clean(man, {"token": "  abc def\n", "url": "x"})
ok(cl["token"] == "abcdef", "токен сохраняется без пробелов и переносов (вставили с хвостом)")
js = (ROOT / "ui/studio/plugins.js").read_text(encoding="utf-8")
ok('s.type === "secret"' in js and 'type="password"' in js, "в карточке плагина токен — поле со звёздочками")

# ---------- страница ----------
page = S.page({"days": 30})
ok(page["configured"] and page["issues"] == 133 and page["overview"]["weeks"] and page["people"] and page["busy"], "jira_page: всё для страницы одним вызовом")
tk = S.task("AI-5")
ok(tk["done_by"] == "Maria Kudelevich" and tk["history"] and tk["comments"] and tk["started"], f"jira_task: из Jira и ход из учёта: {tk['done_by']}, {len(tk['history'])} шага")
# для снимка — команда побольше (как у владельца: 28 человек, три проекта): граф рисуется по тем же правилам
import random  # noqa: E402
_rnd = random.Random(7)
_names = ["Yanson Arseniy", "Maria Kudelevich", "Vitali Kazhurou", "Evgeny Chirich", "Andrey Shpakovsky", "Artem Pulko", "Denis Gulyakevich",
          "Isaev Michael", "Konstantin Karpov", "Darya Tseluyka", "Artyom Kolago", "Dmitriy Lepushenko", "Valeriya Mikulich", "Nikita Solovei",
          "Marina Borisyuk", "Evgenii Poznyak", "Darya Strizhak", "Michael Sheshilov", "Aleksey Ankushev", "Egor Lavrenov", "Vasili Kruk", "Nikolay Elopov"]
_team = {n: ["AI", "NSHIELD", "WEB"][i % 3] if i > 2 else "AI" for i, n in enumerate(_names)}
RICH = {"days": 90, "nodes": [{"name": n, "done": max(3, int(700 / (i + 1.3))), "team": _team[n]} for i, n in enumerate(_names)], "edges": [], "teams": ["AI", "NSHIELD", "WEB"]}
_seen = set()
for _ in range(70):
    a_, b_ = _rnd.sample(_names, 2)
    if _team[a_] != _team[b_] and _rnd.random() < .6:
        continue
    k_ = tuple(sorted((a_, b_)))
    if k_ not in _seen:
        _seen.add(k_)
        RICH["edges"].append({"a": k_[0], "b": k_[1], "w": _rnd.randint(1, 30)})
for i_, a_ in enumerate(_names):
    for b_ in _names[i_ + 1:]:
        k_ = tuple(sorted((a_, b_)))
        if _team[a_] == _team[b_] and k_ not in _seen:
            RICH["edges"].append({"a": k_[0], "b": k_[1], "w": 0, "team": True})
page["graph"] = RICH
from playwright.sync_api import sync_playwright  # noqa: E402
BRIDGE = """window.calls = []; window.PAGE = %s; window.dewiar = {
  run: async (t, a) => { calls.push([t, a]); if (t === 'jira_page') return { ok: true, data: Object.assign({}, PAGE, a && a.person ? { person: PERSON } : {}) };
    if (t === 'jira_task') return { ok: true, data: TASK };
    if (t === 'jira_sync') return { ok: true, data: { done: true, loaded: 0, issues: 130, total: 0 } }; return { ok: true, data: {} }; },
  settings: async () => ({ values: { url: 'x', token: 'y' } }), saveSettings: async (v) => v, openUrl: async (u) => { calls.push(['url', u]); },
  ask: async (t) => { calls.push(['ask', t]); }, toast: () => {} }; window.PERSON = %s; window.TASK = %s;""" % (json.dumps(page, ensure_ascii=False),
                                                                                          json.dumps(S.person_card(S.load(), "Maria", 30), ensure_ascii=False), json.dumps(S.task("AI-5"), ensure_ascii=False))
KIT = (ROOT / "ui/studio/plugpage.js").read_text(encoding="utf-8").split("const PLP_KIT = `")[1].split("`;")[0]


def themed(theme, bg):
    """Страница так, как её показывает студия: цвета темы студии (plpTheme) + общий набор стилей фрейма; фон — как у студии."""
    out = tmp / f"ui-{abs(hash(theme))}.html"
    out.write_text((PLUG / "ui.html").read_text(encoding="utf-8").replace("<style>", "<style>" + theme + KIT + f"html{{background:{bg}}}", 1), encoding="utf-8")
    return out


with sync_playwright() as p:
    b = p.chromium.launch()
    th = b.new_page()
    th.goto((ROOT / "ui/settings.html").as_uri() + "?port=1")
    th.wait_for_timeout(1200)
    LIGHT = th.evaluate("plpTheme()")                           # тема студии по умолчанию (светлая)
    th.evaluate("document.documentElement.className = ''")
    DARK = th.evaluate("plpTheme()")
    th.close()
    f = themed(LIGHT, "#dbe5f1")
    fd = themed(DARK, "linear-gradient(160deg,#1d1b33,#24203f)")
    pg = b.new_page(viewport={"width": 1180, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(BRIDGE)
    pg.goto(f.as_uri())
    pg.wait_for_timeout(700)
    ok(pg.is_visible("#main") and not pg.is_visible("#setup"), "загружено — сводка, а не подключение")
    pg.wait_for_timeout(1000)                                  # числа «пульса» доросли
    hero = pg.inner_text("#hero")
    ok(pg.locator("#hero .mini b").count() == 4 and pg.locator("#hero svg path").count() == 3 and re.search(r"\d+\s*задач", hero),
       f"главная — «пульс команды»: сколько закрыто, график, в работе, ждут, ошибки, люди: {hero[:120]!r}")
    ok("Команда успевает" in hero or "Бэклог растёт" in hero, "вывод словами")
    ok(pg.locator("#donut svg circle").count() >= 2 and "готово" in pg.inner_text("#donut"), "кольцо статусов")
    ok("Artyom Kolago" in pg.inner_text("#away") and "Больничный" in pg.inner_text("#away"), f"«Кого нет» — сегодня и скоро: {pg.inner_text('#away')!r}")
    pg.screenshot(path="/tmp/claude-0/jira_overview.png", full_page=True)
    ok(pg.locator("#busy .mate").count() == 3 and pg.locator("#busy .mate li[data-key]").count() > 3, "«Сейчас» — кто чем занят: карточка на человека с его задачами в работе")
    pg.screenshot(path="/tmp/claude-0/jira_now.png", full_page=True)
    pg.click("#busy .mate li[data-key] >> nth=0")
    pg.wait_for_timeout(400)
    ok(pg.is_visible("#task") and "Готово к ревью" in pg.inner_text("#task") and "Ход" in pg.inner_text("#task"), "задача — карточка: описание, ход по статусам, комментарии")
    pg.screenshot(path="/tmp/claude-0/jira_task.png")
    pg.click("#t-open")
    ok(any(c[0] == "url" and "/browse/AI-" in c[1] for c in pg.evaluate("calls")), "«Открыть в Jira» — задача в Jira")
    pg.keyboard.press("Escape")
    ok(not pg.is_visible("#task"), "Esc закрывает карточку")
    pg.click('#tabs [data-t="ov"]')
    pg.click("#oldest .key >> nth=0")
    pg.wait_for_timeout(300)
    ok(pg.is_visible("#task"), "номер задачи в таблице тоже открывает карточку")
    pg.click("#t-close")
    pg.click('#tabs [data-t="pp"]')
    pg.click("#people tr.pick >> nth=0")
    pg.wait_for_timeout(300)
    ok(pg.is_visible("#person") and "Maria" in pg.inner_text("#person"), "щелчок по человеку — что закрыл и что в работе")
    pg.click("#p-ask")
    ok(any(c[0] == "ask" and "Jira" in c[1] for c in pg.evaluate("calls")), "«Спросить Лиру про …» — фраза в чат")
    pg.screenshot(path="/tmp/claude-0/jira_people.png", full_page=True)
    pgd = b.new_page(viewport={"width": 1180, "height": 900})
    pgd.on("pageerror", lambda e: errs.append(str(e)))
    pgd.add_init_script(BRIDGE)
    pgd.goto(fd.as_uri())
    pgd.wait_for_timeout(600)
    pgd.screenshot(path="/tmp/claude-0/jira_dark.png", full_page=True)
    pg.wait_for_timeout(2500)                                  # созвездие оседает
    ok(pg.locator("#graph .nd").count() == len(_names) and pg.locator("#graph .ed:not(.team)").count() >= 10, "«Кто с кем работает» — созвездие людей")
    ok(pg.locator("#teams span").count() == 3, "цвета команд подписаны")
    pg.locator(".gpanel").screenshot(path="/tmp/claude-0/jira_graph.png")
    pg.hover("#graph .nd >> nth=0")
    ok(pg.evaluate("document.querySelector('#graph').classList.contains('focus')"), "наведение на человека — подсвечены его связи")
    pg.click('#tabs [data-t="ab"]')
    pg.wait_for_timeout(200)
    ok(pg.locator("#ab-tl .lane button").count() == 2 and pg.locator("#ab-tl .today").count() >= 1, "отсутствия — лента: две полосы и «сегодня»")
    ok(pg.is_visible("#ab-loose-p") and "свой счёт" in pg.inner_text("#ab-loose"), "без распознанных дат — отдельным списком")
    pg.screenshot(path="/tmp/claude-0/jira_absences.png", full_page=True)
    pg.click('#tabs [data-t="sk"]')
    ok(pg.locator("#stuck tr").count() > 1, "вкладка «Застряло» — таблица")
    pg.set_viewport_size({"width": 400, "height": 800})
    pg.click('#tabs [data-t="ov"]')
    pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "узкое окно — без прокрутки вбок")
    # не подключено — форма
    pg2 = b.new_page(viewport={"width": 900, "height": 700})
    pg2.add_init_script(BRIDGE.replace("window.PAGE = {", "window.PAGE = {\"_\":0,", 1) + "PAGE.configured = false; PAGE.issues = 0;")
    pg2.goto(f.as_uri())
    pg2.wait_for_timeout(500)
    ok(pg2.is_visible("#setup") and "сохранён" in pg2.get_attribute("#s-token", "placeholder"), "не подключено — форма; сохранённый токен не показывается")
    pg2.screenshot(path="/tmp/claude-0/jira_setup.png")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()

srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
