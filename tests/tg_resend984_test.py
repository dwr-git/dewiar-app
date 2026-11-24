"""№984 (23.11): «связь с ботом пропала… Лира ответила в виджет, но не в бот Telegram». Telegram с компьютера то доступен,
то нет («WinError 10060», «Failed to connect to api.telegram.org»), и ответ пропадал. Теперь сеть не пустила — ответ
уходит повторно (20 с, минута, три минуты) в фоне; ошибка привязки — как раньше, без повторов."""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import telegram as TG  # noqa: E402
tg = TG.Telegram(on_message=lambda k, d: None, path=tmp / "tg.json")
tg.data = {"mode": "own", "token": "1:x", "owner": {"id": 5, "chat": 5}, "code": "", "bot": {"username": "B"}}
tries, sent = [0], []


def reply(chat, text, buttons=None):
    tries[0] += 1
    if tries[0] < 3:
        raise TG.TelegramError("Telegram не отвечает: [WinError 10060] Попытка установить соединение была безуспешной")
    sent.append(text)


tg._reply = reply
orig = tg._resend_later
tg._resend_later = lambda chat, text, buttons=None: orig(chat, text, buttons, waits=(0.05, 0.05, 0.05))
ok(tg.send("Погода в Гадюкино: +3, дождь.") is False, "первая попытка не прошла — send честно говорит «нет»")
time.sleep(0.5)
ok(sent == ["Погода в Гадюкино: +3, дождь."] and tries[0] == 3, f"ответ дошёл с повтора: {sent}, попыток {tries[0]}")
tries[0], sent[:] = 0, []


def deny(chat, text, buttons=None):
    tries[0] += 1
    raise TG.TelegramError("Forbidden: bot was blocked by the user")


tg._reply = deny
tg.send("x"); time.sleep(0.3)
ok(tries[0] == 1, "запрет (бот заблокирован) — без повторов")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
