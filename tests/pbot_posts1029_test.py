"""«Посты» бота персонажа (0.69; запрос бизнеса 29.10: «чтобы Лира писала в группы Telegram» — честно, от имени канала,
без выдуманных собеседников). Бота назначили администратором канала (my_chat_member) — канал в списке; @канал вписали —
проверка, что бот админ с правом публиковать. Пост сейчас — уходит сразу, ссылка на пост; ко времени — уходит на часах;
с одобрением — ждёт «Опубликовать». Опрос — sendPoll. Рубрика «по будням в 10:00» — в срок персонаж пишет пост и он ждёт
одобрения (уведомление), без одобрения — уходит сам; второй раз за день — нет. Новички в группе — одно приветствие на
всех. Инструмент channel_post — с подтверждением, где и что. Подсказка персонажу — без выдуманных отзывов и цифр."""
import os, sys, tempfile, time
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("DEWIAR_CONFIG_DIR", tempfile.mkdtemp())
import pbot_posts  # noqa: E402
from pbot import PersonaBot  # noqa: E402
from pbot_posts import PostError, Posts  # noqa: E402
from telegram import TelegramError  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class Host:
    def __init__(self):
        self.pushes, self.events = [], []
        self.s = type("S", (), {"get": lambda self, *k, **kw: None})()

    def emit(self, ev, **k):
        self.events.append(ev)

    def push(self, title, text="", telegram=True, **k):
        self.pushes.append((title, text))


tmp = Path(tempfile.mkdtemp())
host = Host()
bot = PersonaBot(host, path=tmp / "pbot.json")
bot.data = {"token": "1:x", "bot": {"id": 77, "username": "chai_bot", "name": "Чайный бот"}}
calls = []
member = {"status": "administrator", "can_post_messages": True}


def call(method, timeout=20, files=None, **p):
    calls.append((method, p))
    if method == "getChat":
        if p["chat_id"] == "@nochan":
            raise TelegramError("chat not found")
        return {"id": -1009, "type": "channel", "title": "Чайный двор", "username": p["chat_id"][1:]}
    if method == "getChatMember":
        return member
    if method == "sendMessage" and p["chat_id"] == "-500":
        raise TelegramError("bot was kicked")
    return {"message_id": 100 + len(calls)}


bot._call = call
bot.connected = lambda: True
bot.persona = lambda: {"id": "lira", "name": "Лира", "character": "тёплая и толковая"}
now = [datetime(2026, 10, 30, 9, 0)]                              # пятница
P = Posts(host, bot, path=tmp / "posts.json", now=lambda: now[0])
P.greet_delay = 0.05

# канал: бота назначили администратором
bot._handle({"update_id": 1, "my_chat_member": {"chat": {"id": -1001, "type": "channel", "title": "Новости чая", "username": "chainews"},
                                                "new_chat_member": {"status": "administrator", "can_post_messages": True}}})
ch = P.chats()
ok(len(ch) == 1 and ch[0]["type"] == "channel" and ch[0]["can"] and ch[0]["username"] == "chainews", f"бота назначили админом канала — канал в списке: {ch}")
try:
    P.add_chat("@nochan"); ok(False, "нет такого канала — понятная ошибка")
except PostError as e:
    ok("администратором" in str(e), f"нет канала — понятная ошибка: {e}")
member.update(status="member")
try:
    P.add_chat("https://t.me/chaidvor"); ok(False, "бот не админ канала — отказ")
except PostError as e:
    ok("не администратор" in str(e), "бот в канале не администратор — отказ с подсказкой, где это включить")
member.update(status="administrator")
P.add_chat("@chaidvor")
ok(any(c["id"] == "-1009" and c["title"] == "Чайный двор" for c in P.chats()), "«@chaidvor» вписали — проверили и добавили")

# пост сейчас
calls.clear()
p = P.add("Новый улун приехал!", ["-1001"])
ok(p["status"] == "sent" and calls[0][0] == "sendMessage" and calls[0][1]["chat_id"] == "-1001" and p["sent"][0]["link"].startswith("https://t.me/chainews/"),
   f"пост сейчас — ушёл, со ссылкой: {p['sent']}")
# ко времени
calls.clear()
p = P.add("Завтра дегустация в 18:00", ["-1001", "-1009"], at=datetime(2026, 10, 30, 10, 0))
P.tick()
ok(p["status"] == "plan" and not calls, "запланированный — до срока не уходит")
now[0] = datetime(2026, 10, 30, 10, 0, 30)
P.tick()
ok(P.st["posts"][p["id"]]["status"] == "sent" and len(calls) == 2, "в срок — ушёл в оба канала")
# с одобрением
calls.clear()
p = P.add("Пост на проверку", ["-1001"], approve=True)
ok(p["status"] == "wait" and not calls, "с одобрением — ждёт")
P.approve(p["id"])
ok(P.st["posts"][p["id"]]["status"] == "sent" and calls, "«Опубликовать» — ушёл")
# опрос
calls.clear()
p = P.add("", ["-1001"], poll={"question": "Какой чай любите?", "options": ["Зелёный", "Чёрный", "Улун"]})
ok(calls[-1][0] == "sendPoll" and calls[-1][1]["options"] == ["Зелёный", "Чёрный", "Улун"] and p["status"] == "sent", "опрос — sendPoll")
try:
    P.add("", ["-1001"], poll={"question": "?", "options": ["один"]}); ok(False, "опрос с одним вариантом — нельзя")
except PostError:
    ok(True, "опрос с одним вариантом — понятная ошибка")
# не ушёл
bot.remember_chat({"id": -500, "type": "supergroup", "title": "Старая группа"})
p = P.add("Привет", ["-500"])
ok(p["status"] == "failed" and "kicked" in p["err"] and host.pushes and host.pushes[-1][0] == "Пост не опубликован", "не ушёл — видно почему и пришло уведомление")

# рубрики
P.write = lambda topic, title="", poll=False: f"Совет дня: {topic}. Заваривайте при 85°."
calls.clear(); host.pushes.clear()
ru = P.rubric_set({"topic": "совет дня о чае", "days": [0, 1, 2, 3, 4], "time": "11:00", "chats": ["-1001"], "approve": True})
ok(P.when_text(ru) == "по будням в 11:00", "рубрика: «по будням в 11:00»")
now[0] = datetime(2026, 10, 30, 10, 59); P.tick()
ok(not [x for x in P.st["posts"].values() if x["source"] == "rubric"], "до срока рубрика молчит")
now[0] = datetime(2026, 10, 30, 11, 0, 20); P.tick(); P.tick()
rp = [x for x in P.st["posts"].values() if x["source"] == "rubric"]
ok(len(rp) == 1 and rp[0]["status"] == "wait" and "совет дня" in rp[0]["text"] and not calls, "в срок — пост написан и ждёт одобрения (один за день)")
ok(host.pushes and host.pushes[-1][0] == "Пост ждёт одобрения", "и пришло уведомление")
now[0] = datetime(2026, 10, 31, 11, 5); P.tick()
ok(len([x for x in P.st["posts"].values() if x["source"] == "rubric"]) == 1, "в субботу по будням — нет")
P.rubric_set(dict(ru, approve=False, days=[5]))
P.tick()
rp = sorted((x for x in P.st["posts"].values() if x["source"] == "rubric"), key=lambda x: x["created"])
ok(len(rp) == 2 and rp[-1]["status"] == "sent", "без одобрения — ушёл сам")

# новички
calls.clear()
P.greet_set(on=True)
grp = {"id": -700, "type": "supergroup", "title": "Клуб"}
bot._handle({"update_id": 5, "message": {"message_id": 1, "chat": grp, "from": {"id": 1, "first_name": "Анна"},
                                         "new_chat_members": [{"id": 1, "first_name": "Анна"}]}})
bot._handle({"update_id": 6, "message": {"message_id": 2, "chat": grp, "from": {"id": 2, "first_name": "Иван"},
                                         "new_chat_members": [{"id": 2, "first_name": "Иван"}, {"id": 3, "first_name": "Спам", "is_bot": True}]}})
time.sleep(0.3)
sent = [p for m, p in calls if m == "sendMessage" and p["chat_id"] == -700]
ok(len(sent) == 1 and sent[0]["text"].startswith("Анна и Иван, добро пожаловать") and "Лира" in sent[0]["text"], f"новички — одно приветствие на всех, без ботов: {sent}")

# что пишет персонаж
ok("не выдумывай собеседников, отзывы, цифры" in pbot_posts.WRITE, "персонажу: без выдуманных собеседников, отзывов и цифр")

# инструмент
import tools  # noqa: E402
sp = tools.TOOLS["channel_post"]
ok(sp[2] == "confirm" and "channel_post" in tools.NET_TOOLS, "channel_post — только с подтверждением")
tb = tools.Toolbox.__new__(tools.Toolbox); tb.hooks = {"pbot_posts": P}
q = tb.describe("channel_post", {"text": "Скидка 10% до воскресенья", "chat": "чайный двор", "when": "завтра в 10"})
ok("Чайный двор" in q and "завтра в 10" in q and "Скидка 10%" in q, f"подтверждение: где, когда и что: {q}")
calls.clear()
out = tools.t_channel_post({"text": "Скидка 10% до воскресенья", "chat": "Новости"}, {"pbot_posts": P})
ok("Опубликовала в «Новости чая»" in out and calls and calls[0][1]["chat_id"] == "-1001", f"голосом — в названный канал: {out}")
try:
    tools.t_channel_post({"text": "x", "chat": "Котики"}, {"pbot_posts": P}); ok(False, "чужой канал — ошибка")
except tools.ToolError as e:
    ok("не состоит" in str(e), "бота нет в названном канале — так и говорю, и где он есть")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
