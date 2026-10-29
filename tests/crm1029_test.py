"""«CRM» (0.69; запрос бизнеса 29.10: «связать с лидами в CRM — Битрикс24»). Битрикс24 — входящим вебхуком: ссылка
проверяется (crm.lead.fields), клиент уходит лидом (crm.lead.add: имя и фамилия отдельно, телефон, почта, история — в
комментарий, источник Dewiar), повторно — только новые записи комментарием в ленту (а если лид уже стал сделкой — в сделку),
не вторым лидом. Свой вебхук — POST JSON (lead/update). Плохая ссылка — понятная ошибка, ключ не сохраняется; в студию —
без ключа; файл — права 600; http наружу — нельзя. «Новых клиентов — сразу в CRM». Инструмент client_crm."""
import json, os, stat, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from clients import Clients  # noqa: E402
from crm import Crm, CrmError, bitrix_base, split_name  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


calls = []
state = {"converted": False, "fail": ""}


def http(url, body):
    calls.append((url, body))
    if state["fail"]:
        return {"error": "INVALID_CREDENTIALS", "error_description": state["fail"]}
    m = url.rsplit("/", 1)[-1]
    if m == "crm.lead.fields.json":
        return {"result": {"TITLE": {}}}
    if m == "crm.lead.add.json":
        return {"result": 42}
    if m == "crm.lead.get.json":
        return {"result": {"ID": "42", "STATUS_ID": "CONVERTED" if state["converted"] else "NEW"}}
    if m == "crm.deal.list.json":
        return {"result": [{"ID": "1811"}]}
    if m == "crm.timeline.comment.add.json":
        return {"result": 7}
    return {"id": "wh-9"}


tmp = Path(tempfile.mkdtemp())
C = Clients(tmp / "clients.json")
R = Crm(tmp / "crm.json", C, http=http)
KEY = "abc123secretkey"
URL = f"https://romashka.bitrix24.ru/rest/1/{KEY}/profile.json"

ok(bitrix_base(URL) == f"https://romashka.bitrix24.ru/rest/1/{KEY}", "ссылку вебхука с методом на конце — понимаю")
for bad in ("https://romashka.bitrix24.ru/crm/lead/", "romashka.bitrix24.ru", ""):
    try:
        bitrix_base(bad); ok(False, f"не ссылка вебхука — ошибка: {bad!r}")
    except CrmError as e:
        ok("входящего вебхука" in str(e), f"не ссылка вебхука — понятная ошибка: {bad!r}")
ok(split_name("Иванов Пётр Сергеевич") == ("Пётр", "Иванов") and split_name("Анна Петрова") == ("Анна", "Петрова")
   and split_name("Петров Иван") == ("Иван", "Петров") and split_name("Ромашка") == ("Ромашка", ""), "имя и фамилия — по отдельности")

state["fail"] = "wrong key"
try:
    R.connect("bitrix", URL); ok(False, "неверный ключ — не подключаю")
except CrmError:
    ok(not R.connected() and not (tmp / "crm.json").exists(), "неверный ключ — не подключаю и ничего не сохраняю")
state["fail"] = ""
pub = R.connect("bitrix", URL)
ok(calls[-1][0].endswith("/crm.lead.fields.json"), "подключение — с проверкой права «CRM»")
ok(pub == {"kind": "bitrix", "name": "Битрикс24", "host": "romashka.bitrix24.ru", "connected": True, "auto": False, "last": None} and KEY not in json.dumps(pub),
   f"студия видит портал, но не ключ: {pub}")
ok(stat.S_IMODE((tmp / "crm.json").stat().st_mode) == 0o600, "ключ — в файле с правами 600")

c = C.add("Иванов Пётр", "ООО «Ромашка»", "+375 29 000-00-00", "petr@romashka.by")
C.note(c["id"], "Хочет 200 коробок до пятницы")
calls.clear()
r = R.send(c["id"])
url, body = calls[-1]
f = body["fields"]
ok(url.endswith("/crm.lead.add.json") and r["new"] and r["id"] == "42", f"первый раз — новым лидом: {r}")
ok(f["NAME"] == "Пётр" and f["LAST_NAME"] == "Иванов" and f["COMPANY_TITLE"] == "ООО «Ромашка»"
   and f["PHONE"][0]["VALUE"] == "+375 29 000-00-00" and f["EMAIL"][0]["VALUE"] == "petr@romashka.by"
   and "200 коробок" in f["COMMENTS"] and f["SOURCE_DESCRIPTION"] == "Dewiar", f"поля лида: {f}")
ok(C.get(c["id"])["crm"]["id"] == "42", "в карточке — номер лида")

calls.clear()
r = R.send(c["id"])
ok(r == {"id": "42", "kind": "bitrix", "new": False, "n": 0} and not calls, "второй раз без новых записей — ничего не шлю и лид не дублирую")
time.sleep(0.01)
C.note(c["id"], "Перезвонил, согласен на скидку 5%", kind="call")
r = R.send(c["id"])
url, body = calls[-1]
ok(url.endswith("/crm.timeline.comment.add.json") and body["fields"]["ENTITY_TYPE"] == "lead" and body["fields"]["ENTITY_ID"] == 42
   and "скидку 5%" in body["fields"]["COMMENT"] and "200 коробок" not in body["fields"]["COMMENT"] and r["n"] == 1,
   "новая запись — комментарием в ленту того же лида, старые не повторяю")
state["converted"] = True
time.sleep(0.01)
C.note(c["id"], "Счёт отправлен", kind="deal")
R.send(c["id"])
url, body = calls[-1]
ok(body["fields"]["ENTITY_TYPE"] == "deal" and body["fields"]["ENTITY_ID"] == 1811 and C.get(c["id"])["crm"].get("deal") == "1811",
   "лид уже стал сделкой (простой режим CRM) — пишу в сделку и запоминаю её")

# новых — сразу
R.set_auto(True)
calls.clear()
n = C.add("Анна Петрова", email="anna@mail.ru")
for _ in range(100):
    if C.get(n["id"]).get("crm"):
        break
    time.sleep(0.02)
ok(C.get(n["id"]).get("crm", {}).get("id") == "42" and calls and calls[-1][0].endswith("crm.lead.add.json"), "«Новых — сразу»: новый клиент ушёл сам")

# свой вебхук
try:
    R.connect("webhook", "http://example.com/hook"); ok(False, "http наружу — нельзя")
except CrmError as e:
    ok("https" in str(e), "свой вебхук по http наружу — нельзя (данные клиентов ушли бы открытыми)")
R.connect("webhook", "https://hook.example.com/abc")
ok(calls[-1][1]["event"] == "test", "свой вебхук: проверка — событие test")
r = R.send(c["id"])
body = calls[-1][1]
ok(body["event"] == "lead" and body["client"]["email"] == "petr@romashka.by" and len(body["notes"]) == 3 and r["id"] == "wh-9" and r["new"],
   "другая CRM — для неё клиент новый: событие lead со всей историей")
C.note(c["id"], "Оплатил")
time.sleep(0.01)
R.send(c["id"])
ok(calls[-1][1]["event"] == "update" and calls[-1][1]["crm_id"] == "wh-9" and [x["text"] for x in calls[-1][1]["notes"]] == ["Оплатил"],
   "дальше — update только с новыми записями")
R.forget()
ok(not R.connected() and KEY not in (tmp / "crm.json").read_text(), "«Отключить» — ключ стёрт")

# инструмент
import tools  # noqa: E402
sp = tools.TOOLS.get("client_crm")
ok(sp and sp[2] == "safe" and "client_crm" in tools.NET_TOOLS, "инструмент client_crm есть и помечен как сетевой")
R.connect("bitrix", URL)
out = tools.t_client_crm({"who": "Анна Петрова"}, {"clients": C, "crm": R})
ok("Битрикс24" in out, f"голосом: «передай Анну Петрову в Битрикс»: {out}")
ok(C.title(C.get(C.find("Петрову"))) == "Анна Петрова", "«передай Петрову» — Анна Петрова, а не Пётр (по началу слова — только длинные слова)")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
