"""№874 (18.11): «Подключён через бота Dewiar · владелец …» и тут же «Telegram ещё не привязан — отправьте боту код из
студии»; из Telegram — «компьютеры не на связи». Сервер бота не знает привязки этого компьютера (ключ сменился, вход в
аккаунт и обратно), а здесь владелец остался записанным. Теперь первое же «не привязан» при отправке: привязка есть у
аккаунта — подхватить; нет — забыть устаревшего владельца и сразу новый код: студия покажет одно — «отправьте боту код»."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import telegram as TG  # noqa: E402

calls, events = [], []


def make(linked_owner=None):
    t = TG.Telegram(on_message=lambda k, d: events.append(k), path=Path(tempfile.mkdtemp()) / "tg.json")
    t.data = {"mode": "dewiar", "token": "dev:" + "a" * 40, "api": "https://dewiar.pro/dwrapp/tg.php",
              "owner": {"id": 7, "chat": 7, "name": "Андрей"}, "bot": {"username": "DewiarABot"}}

    def call(method, timeout=20, files=None, **params):
        calls.append(method)
        if method == "sendMessage":
            raise TG.TelegramError("Telegram ещё не привязан — отправьте боту код из студии")
        return True
    t._call = call

    class R:
        status_code = 200
        def json(self): return {"ok": True, "result": {"linked": bool(linked_owner), "owner": linked_owner}}
    t._http = lambda *a, **k: R()
    return t


t = make()
ok(t.paired(), "до: «подключён», владелец записан")
ok(t.send("Напоминание") is False, "отправка не прошла")
ok(not t.paired() and t.data.get("owner") is None, "сервер не знает привязки — устаревший владелец забыт")
ok("setLinkCode" in calls and t.data.get("code") and "nodes" in events, "сразу новый код — студия покажет «отправьте боту код» (одно, без противоречия)")
calls.clear(); events.clear()
t = make(linked_owner={"id": 9, "chat": 9, "name": "Андрей"})
t.send("Напоминание")
ok(t.paired() and t.data["owner"]["id"] == 9 and "setLinkCode" not in calls, "привязка есть у аккаунта — подхвачена, код не нужен")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
