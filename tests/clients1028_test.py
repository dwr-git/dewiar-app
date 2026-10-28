"""«Клиенты» — личная CRM (28.10, владелец: «Лира как личная CRM… изящно, включаемо-отключаемо, чтобы не напугать обычных
пользователей»). Ядро clients.py: карточка заводится сама из фразы, поиск в падежах и по компании, записи в историю,
следующий шаг — напоминанием (переставили — прежнее снято), «сделано», кто ждёт. Инструменты модели — только когда
«Клиенты» включены. Студия: раздел скрыт, пока выключено; список, карточка, запись, следующий шаг, поиск."""
import os, sys, tempfile, types
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ.setdefault("DEWIAR_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import clients as CL  # noqa: E402
import tools as T  # noqa: E402


class Rem:
    def __init__(self):
        self.items = []

    def add(self, at, text, repeat=None, kind="reminder", extra=None):
        it = {"id": f"r{len(self.items) + 1}", "at": at.isoformat(), "text": text}
        self.items.append(it)
        return dict(it)

    def remove(self, rid):
        self.items = [x for x in self.items if x["id"] != rid]
        return True


tmp = Path(tempfile.mkdtemp())
rem = Rem()
C = CL.Clients(tmp / "clients.json", rem)
ctx = {"clients": C}

# ---------- голосом (инструменты модели) ----------
out = T.t_client_note({"who": "Иванов", "company": "Ромашка", "text": "Хочет 200 коробок до пятницы"}, ctx)
c1 = next(iter(C.st["clients"].values()))
ok(c1["name"] == "Иванов" and c1["company"] == "Ромашка" and c1["log"][0]["t"] == "Хочет 200 коробок до пятницы" and "карточка заведена" in out,
   f"«запиши: Иванов из „Ромашки“ хочет 200 коробок» — карточка заведена, запись в истории: {out}")
T.t_client_note({"who": "Иванову", "text": "Звонил, просит скидку 5%", "kind": "call", "phone": "+375 29 123-45-67"}, ctx)
ok(len(C.st["clients"]) == 1 and len(c1["log"]) == 2 and c1["log"][1]["kind"] == "call" and c1["phone"] == "+375 29 123-45-67",
   "«Иванову» — тот же клиент (падеж), звонок и телефон — в карточку")
ok(C.find("Ромашка") == c1["id"] and C.find("Иванов из «Ромашки»") == c1["id"] and C.find("ромашке") == c1["id"], "находится по компании и в падежах")
T.t_client_note({"who": "Петров", "company": "Альфа", "text": "Нужен договор"}, ctx)
T.t_client_note({"who": "Петрова", "company": "Бета", "text": "Ждёт прайс"}, ctx)
try:
    C.find("Петров"); amb = ""
except CL.ClientError as e:
    amb = str(e)
ok("подходят несколько" in amb or C.find("Петров") in C.st["clients"], f"двое похожих — переспросить, а не путать: {amb or 'нашёлся точный'}")
ok(CL.split_who("ООО «Вектор»") == ("", "Вектор") and CL.split_who("Пётр Сидоров из компании Альфа") == ("Пётр Сидоров", "Альфа"),
   "«ООО «Вектор»» — компания; «из компании Альфа» — компания, имя с «ё» не теряет")
info = T.t_client_info({"who": "Иванова"}, ctx)
ok("Иванов («Ромашка»)" in info and "200 коробок" in info and "скидку" in info and "+375 29" in info, f"«что у нас с Ивановым?» — карточка одним текстом: {info[:160]}")
# следующий шаг — напоминание
out = T.t_client_next({"who": "Иванову", "what": "перезвонить", "when": "в четверг в 11"}, ctx)
nx = c1["next"]
ok(nx and nx["what"] == "перезвонить" and nx["at"].endswith("11:00") and rem.items and rem.items[0]["text"] == "Перезвонить — Иванов («Ромашка»)",
   f"«перезвонить Иванову в четверг в 11» — шаг и напоминание в «Делах»: {out} {rem.items}")
T.t_client_next({"who": "Иванов", "what": "отправить счёт", "when": "завтра в 10"}, ctx)
ok(len(rem.items) == 1 and rem.items[0]["text"].startswith("Отправить счёт") and c1["next"]["rid"] == rem.items[0]["id"],
   "переставили шаг — прежнее напоминание снято, новое одно")
# просрочено — сверху и в «кто ждёт»
c1["next"]["at"] = (datetime.now() - timedelta(hours=3)).isoformat(timespec="minutes")
lst = C.list()
ok(lst[0]["id"] == c1["id"] and lst[0]["overdue"], "срок шага прошёл — клиент сверху списка с пометкой")
sm = T.t_client_list({}, ctx)
ok("Ждут, срок прошёл: Иванов" in sm and "Без следующего шага" in sm and "Клиентов: 3" in sm, f"«кому перезвонить?» — кто ждёт, остальные: {sm[:200]}")
out = T.t_client_next({"who": "Иванов", "done": True}, ctx)
ok(c1["next"] is None and c1["log"][-1]["kind"] == "done" and not rem.items, f"«я перезвонил Иванову» — шаг сделан, в историю, напоминание снято: {out}")
_s1, _s2 = [x["name"] for x in C.list("скидк")], [x["name"] for x in C.list("договор")]
ok(_s1 == ["Иванов"] and _s2[:1] == ["Петров"], f"поиск по записям истории: {_s1} {_s2}")
# сохраняется
C2 = CL.Clients(tmp / "clients.json", rem)
ok(len(C2.st["clients"]) == 3 and C2.st["clients"][c1["id"]]["phone"] == "+375 29 123-45-67", "карточки сохраняются в clients.json")
# включаемо-отключаемо
import settings as SET  # noqa: E402
ok(SET.DEFAULTS["features"]["clients"] is False, "по умолчанию «Клиенты» выключены — обычных людей не пугают")


class Sett:
    def __init__(self, on):
        self.on = on

    def get(self, a, b=None):
        if a == "features":
            return {"clients": self.on}
        if a == "tools":
            return {}
        return {}


tb = T.Toolbox(Sett(False), rem); tb.hooks["clients"] = C
ok(not any(tb.policy(n)[0] for n in ("client_note", "client_info", "client_next", "client_list")), "выключено — модель о «Клиентах» не знает")
tb.s = Sett(True)
ok(all(tb.policy(n) == (True, False) for n in ("client_note", "client_info", "client_next", "client_list")), "включено — четыре умения, без «Выполнить?»")

# ---------- студия ----------
C.set_next(c1["id"], "отправить счёт", datetime.now() - timedelta(hours=2))      # для студии: срок прошёл
LIST = C.list()
CARD = C.get(c1["id"])
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    ok(pg.evaluate("() => document.querySelector('nav button[data-p=clients]').hidden"), "в меню «Клиентов» нет, пока не включены")
    ok(pg.evaluate("() => !!document.querySelector('input[data-k=\"features.clients\"]')"), "включить — «Возможности» → «Клиенты — личная CRM»")
    pg.evaluate("""([list, card]) => { window._calls = []; window._card = card;
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'clients_list') return Promise.resolve(a.q ? list.filter(x => (x.name + x.company + x.last).toLowerCase().includes(a.q.toLowerCase())) : list);
        if (c === 'client_get') return Promise.resolve(a.id === card.id ? card : Object.assign({}, card, { id: a.id, name: (list.find(x => x.id === a.id) || {}).name, log: [], next: null }));
        if (c === 'client_note') { _card = Object.assign({}, _card, { log: _card.log.concat([{ id: 'n9', ts: Date.now() / 1000, t: a.text, kind: a.kind }]) }); return Promise.resolve(_card); }
        if (c === 'client_next') return Promise.resolve(Object.assign({}, card, { next: { what: a.what, at: a.at, rid: 'r9' } }));
        return Promise.resolve({}); };
      if (!S) S = {}; S.features = Object.assign({}, S.features, { clients: true });
      const nb = document.querySelector('nav button[data-p=clients]'); nb.hidden = false; nb.click(); }""", [LIST, CARD])
    pg.wait_for_timeout(700)
    r = pg.evaluate("() => [[...document.querySelectorAll('#cr-list .cr-row b')].map(x => x.textContent), !!document.querySelector('#cr-list .cr-row.late em'), document.querySelector('#cr-name').value, document.querySelector('#cr-comp').value, document.querySelectorAll('.cr-h').length, !!document.querySelector('.cr-next.late')]")
    ok(r[0][0] == "Иванов" and r[1] and r[2] == "Иванов" and r[3] == "Ромашка" and r[4] == len(CARD["log"]), f"список (кто ждёт — сверху, с меткой) и карточка: {r}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-clients.png"))
    pg.click(".cr-kinds button[data-k=deal]"); pg.fill("#cr-atext", "Подписали договор на 4 500 руб."); pg.click("#cr-aform button[type=submit]"); pg.wait_for_timeout(400)
    ok(["client_note", {"id": CARD["id"], "text": "Подписали договор на 4 500 руб.", "kind": "deal"}] in pg.evaluate("_calls")
       and pg.evaluate("document.querySelectorAll('.cr-h.deal').length") >= 1, "«Записать» — сделка в историю")
    pg.fill("#cr-q", "альфа"); pg.wait_for_timeout(600)
    ok(pg.evaluate("() => [...document.querySelectorAll('#cr-list .cr-row b')].map(x => x.textContent)") == ["Петров"], "поиск на лету")
    pg.fill("#cr-q", ""); pg.wait_for_timeout(500)
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
