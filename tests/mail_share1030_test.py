"""Почта — на всех своих компьютерах (30.10, владелец: «на рабочем компьютере добавил почту — всё хорошо, а дома её не
вижу. Стоит ли сделать синхронизацию?»). Ящики с паролями приложений уходят своим устройствам только конвертом
(сквозное шифрование «Близких», как ключ умного дома) — сайт их не видит. Новее — заменяет (подключили, сменили пароль,
отключили); почта, настроенная здесь до 0.73, не теряется — пришедшие ящики добавляются к ней."""
import json, os, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import mail as ML  # noqa: E402
from engine_tools import ToolsMixin  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
sent = []
work = ML.Mail(tmp / "work.json"); work.on_change = lambda: sent.append(work.share())
work.save({"address": "owner@gmail.com", "password": "abcd efgh ijkl mnop"})
ok(sent and sent[-1]["boxes"][0]["address"] == "owner@gmail.com" and sent[-1]["boxes"][0]["password"] == "abcdefghijklmnop" and sent[-1]["at"] > 0,
   "подключили на рабочем — уходит своим устройствам (с паролем — только в конверте)")
home = ML.Mail(tmp / "home.json")
ok(home.adopt(sent[-1]["boxes"], sent[-1]["at"]) and home.configured() and home.box().data["password"] == "abcdefghijklmnop",
   "дома — та же почта, без ввода")
ok(json.loads((tmp / "home.json").read_text())["at"] == sent[-1]["at"], "отметка времени — как у рабочего (обратно не гоняем)")
ok(not home.adopt(sent[-1]["boxes"], sent[-1]["at"]), "то же самое второй раз — ничего не меняет")
time.sleep(0.01)
work.forget(); off = sent[-1]
ok(off["boxes"] == [] and home.adopt(off["boxes"], off["at"]) and not home.configured(), "отключили на рабочем — отключилась и дома")
old = ML.Mail(tmp / "old.json")
(tmp / "old.json").write_text(json.dumps({"boxes": [{"address": "me@yandex.ru", "password": "x"}]}), encoding="utf-8")
old = ML.Mail(tmp / "old.json")
ok(old.adopt([{"address": "owner@gmail.com", "password": "p"}], 5) and [b.data["address"] for b in old.boxes] == ["me@yandex.ru", "owner@gmail.com"],
   "здесь своя почта, настроенная до 0.73, — не теряется, пришедшая добавляется")
ok(not old.adopt([{"address": "z@z.z"}], "мусор") and not old.adopt("не список", 10**15), "мусор в конверте — ничего не ломает")

# ядро: почта в конверте своим устройствам и обратно
emitted = []
e = types.SimpleNamespace(mail=home, home=types.SimpleNamespace(share=lambda: None, adopt=lambda *a: False), ha=None, sync_key=None,
                          toolbox=types.SimpleNamespace(catalog=lambda: []), emit=lambda k, **kw: emitted.append(k))
home.save({"address": "family@mail.ru", "password": "q"})
snap = ToolsMixin.own_snapshot(e)
ok(snap and snap["mail"]["boxes"][0]["address"] == "family@mail.ru", "в конверте своим устройствам — и почта")
e2 = types.SimpleNamespace(mail=ML.Mail(tmp / "third.json"), home=e.home, ha=None, sync_key=None, toolbox=e.toolbox, emit=lambda k, **kw: emitted.append(k), close=None)
ToolsMixin.own_apply(e2, {"mail": snap["mail"]})
ok(e2.mail.configured() and "mail" in emitted, "пришёл конверт — почта настроена, студия обновилась")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
