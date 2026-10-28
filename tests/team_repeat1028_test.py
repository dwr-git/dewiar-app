"""«Поручения» дальше (28.10, «повторяющиеся — каждый понедельник отчёт; итог дня вечером»): срок словами с «каждый»,
«по будням» — правило, а не одно поручение; в день срока утром поручение уходит само, следующий срок — по правилу;
компьютер был выключен — старое не шлётся; «больше не поручать» — повтор убран. Итог дня руководителю в заданное время:
сделано, перенесено с причиной, просрочено, на завтра; за день ничего — молчит; раз в день. Голосом — то же (team_assign).
Бот подменён: Team.connected/_send — заглушки, сотрудники «вошли»."""
import os, sys, tempfile, types
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ.setdefault("DEWIAR_HOME", tempfile.mkdtemp())
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import team as TM  # noqa: E402
import tools as T  # noqa: E402

ok(TM.repeat_parse("каждый понедельник к 18") == {"kind": "weekly", "days": [0], "time": "18:00"}, "«каждый понедельник к 18»")
ok(TM.repeat_parse("по будням до 10") == {"kind": "weekly", "days": [0, 1, 2, 3, 4], "time": "10:00"}, "«по будням до 10»")
ok(TM.repeat_parse("каждую пятницу") == {"kind": "weekly", "days": [4], "time": "18:00"}, "без часа — к 18:00, как обычные поручения")
ok(TM.repeat_parse("каждый день в 9:30") == {"kind": "daily", "time": "09:30"} and TM.repeat_parse("до пятницы") is None and TM.repeat_parse("завтра к 12") is None,
   "«каждый день в 9:30»; «до пятницы», «завтра к 12» — не повтор")
ok(TM.repeat_text({"kind": "weekly", "days": [0], "time": "18:00"}) == "каждый понедельник к 18:00"
   and TM.repeat_text({"kind": "weekly", "days": [0, 1, 2, 3, 4], "time": "10:00"}) == "по будням к 10:00"
   and TM.repeat_text({"kind": "weekly", "days": [2, 4], "time": "12:00"}) == "каждую среду и каждую пятницу к 12:00"
   and TM.repeat_text({"kind": "monthly", "day": 1, "time": "12:00"}) == "каждое 1-е число к 12:00", "правило словами")

said = []
host = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *a: None), emit=lambda *a, **k: None,
                             push=lambda t, x: said.append(("push", t, x)), announce=lambda x: said.append(("say", x)))
tmp = Path(tempfile.mkdtemp())
team = TM.Team(host, tmp / "team.json", tmp / "team_bot.json")
team.connected = lambda: True
sent = []
team._send = lambda chat, text, buttons=None, ch=None: (sent.append((chat, text)), len(sent))[1]
for mid, name, chat in (("m1", "Анна Ким", 601), ("m2", "Иван Петров", 602)):
    team.st["members"][mid] = {"id": mid, "name": name, "tg": {"id": chat, "chat": chat, "ch": "tg"}}

# ---------- повтор ----------
r = team.assign("Анне", "отчёт по продажам", "каждый понедельник к 18")
mon = datetime.fromisoformat(r["first"])
ok(r.get("repeat") and r["rule"] == "каждый понедельник к 18:00" and mon.weekday() == 0 and (mon.hour, mon.minute) == (18, 0),
   f"«поручи Анне отчёт каждый понедельник к 18» — правило, первое — в понедельник 18:00: {r.get('rule')} {r.get('first')}")
n0 = len(team.st["tasks"])
team.tick(now=mon.replace(hour=8, minute=30))
ok(len(team.st["tasks"]) == n0, "до 9 утра понедельника — ещё не ушло")
team.tick(now=mon.replace(hour=9, minute=1))
t = [x for x in team.st["tasks"].values() if x["title"] == "Отчёт по продажам"]
rr = team.st["repeats"][r["id"]]
ok(len(t) == 1 and t[0]["due"] == mon.strftime("%Y-%m-%dT%H:%M") and sent and "Отчёт по продажам" in sent[-1][1] and sent[-1][0] == 601,
   f"в понедельник в 9 — поручение Анне само, со сроком 18:00: {sent[-1:]}")
ok(rr["next"] == (mon + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"), f"следующее — через неделю: {rr['next']}")
team.tick(now=mon.replace(hour=12))
ok(len([x for x in team.st["tasks"].values() if x["title"] == "Отчёт по продажам"]) == 1, "в тот же день второй раз не уходит")
ok(t[0]["log"][0]["t"] == "по расписанию", "в истории поручения — «по расписанию»")
# компьютер был выключен две недели — старое не шлём
team.tick(now=mon + timedelta(days=21, hours=10))
ok(len([x for x in team.st["tasks"].values() if x["title"] == "Отчёт по продажам"]) == 1 and rr["next"] > (mon + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
   "компьютер был выключен — пропущенные не сыпятся, срок сдвинулся вперёд")
pub = team.public()
ok(pub["repeats"] and pub["repeats"][0]["rule"] == "каждый понедельник к 18:00" and pub["repeats"][0]["name"] == "Анна Ким", "студия видит повторы")
ok("повторяется каждый понедельник к 18:00" in team.summary(), "«что с поручениями?» — и повторы")
# голосом
out = T.t_team_assign({"who": "Ивану", "task": "сверить кассу", "due": "по будням к 10"}, {"team": team})
ok("Буду поручать Ивану Петрову" in out and "по будням к 10:00" in out, f"голосом: {out}")
rid = [x for x in team.st["repeats"].values() if x["title"] == "Сверить кассу"][0]["id"]
team.repeat_del(rid)
ok(rid not in team.st["repeats"], "«больше не поручать» — повтор убран")

# ---------- итог дня ----------
day = datetime(2026, 11, 5, 10, 0)
team.st["tasks"].clear(); team.st["repeats"].clear(); said.clear()
team.st["digest"] = "18:30"; team.st.pop("digest_day", None)
team.tick(now=day.replace(hour=18, minute=31))
ok(not said, "за день ничего не было — итог не приходит")
team.st.pop("digest_day", None)
ts = day.timestamp()
team.st["tasks"] = {
    "a": {"id": "a", "who": "m1", "title": "Обновить прайс", "state": "done", "due": "2026-11-05T18:00", "log": [{"ts": ts, "ev": "done", "t": ""}]},
    "b": {"id": "b", "who": "m2", "title": "Договор с «Ромашкой»", "state": "moved", "due": "2026-11-07T18:00", "reason": "клиент заболел",
          "log": [{"ts": ts, "ev": "move", "t": ""}]},
    "c": {"id": "c", "who": "m2", "title": "Счёт поставщику", "state": "work", "due": "2026-11-04T18:00", "log": [{"ts": ts - 86400 * 2, "ev": "take", "t": ""}]},
    "d": {"id": "d", "who": "m1", "title": "Отчёт", "state": "new", "due": "2026-11-06T12:00", "log": [{"ts": ts, "ev": "assign", "t": ""}]},
}
team.tick(now=day.replace(hour=18, minute=10))
ok(not said, "до 18:30 — ещё нет")
team.tick(now=day.replace(hour=18, minute=31))
txt = said[0][2] if said else ""
ok("Сделано 1: Анна — «Обновить прайс»" in txt and "Перенесено 1: Иван — «Договор с «Ромашкой»»" in txt and "причина: клиент заболел" in txt
   and "Просрочено 1: Иван — «Счёт поставщику»" in txt and "На завтра — 1 поручение" in txt, f"итог дня в 18:30: {txt}")
ok(any(x[0] == "say" for x in said), "и вслух (если «Говорить вслух» включено)")
n = len(said); team.tick(now=day.replace(hour=19, minute=40))
ok(len(said) == n, "итог — раз в день")
team.set({"digest": ""}); team.st.pop("digest_day", None); n = len(said)
team.tick(now=day.replace(hour=20))
ok(len(said) == n and team.public()["digest"] == "", "«Не присылать» — итога нет")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
