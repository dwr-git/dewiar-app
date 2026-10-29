"""«Рассылка» (0.69; запрос бизнеса 29.10: «начальник отправляет письма 10 сотрудникам или 100 клиентам»).
Каждому — своё письмо: {имя} подставлено, в «Кому» — только он (адресов друг друга не видно); повторы и неверные адреса
отсеяны, отписавшиеся пропущены; реклама — со строкой «как отписаться» и заголовком List-Unsubscribe, деловое — без;
дневной предел почты — рассылка ждёт и продолжает; «Отписаться» во «Входящих» — в стоп-лист; уже ушедшую второй раз не
отправить. Сотрудникам — по почте из карточки (team_member_set). Инструмент модели — с подтверждением."""
import os, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import mailing  # noqa: E402
from mailing import Mailing, MailingError, parse_list, render  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class Box:
    def __init__(self, addr):
        self.data = {"address": addr}

    def configured(self):
        return True


class FakeMail:
    def __init__(self):
        self.sent, self.boxes, self.inbox_items, self.fail = [], [Box("boss@firma.ru")], [], set()

    def configured(self):
        return True

    def box(self, which=None):
        return self.boxes[0]

    def send(self, to="", subject="", body="", attachments=(), box=None, headers=None):
        if to in self.fail:
            raise RuntimeError("550 нет такого ящика")
        self.sent.append({"to": to, "subject": subject, "body": body, "headers": headers or {}})

    def inbox(self, limit=10, box=None, **k):
        return self.inbox_items


class S:
    def __init__(self):
        self.d = {}

    def get(self, *k, default=None):
        return self.d.get(k, default)


class Host:
    def __init__(self):
        self.mail, self.s, self.events, self.pushes = FakeMail(), S(), [], []
        self.clients = type("C", (), {"st": {"clients": {
            "1": {"name": "Анна Петрова", "email": "anna@mail.ru", "tags": ["vip"]},
            "2": {"name": "Иван", "email": "ivan@yandex.ru", "tags": []},
            "3": {"name": "Без почты", "email": "", "tags": []},
            "4": {"name": "Сломанная", "email": "не адрес", "tags": []}}}})()
        self.team = type("T", (), {"st": {"members": {"a": {"name": "Ольга", "email": "olga@firma.ru"}, "b": {"name": "Пётр"}}}})()

    def emit(self, ev, **k):
        self.events.append((ev, k))

    def push(self, title, text="", telegram=True, **k):
        self.pushes.append((title, text))


def wait(c, cid, st=("done",), t=5):
    end = time.time() + t
    while time.time() < end and c.st["campaigns"][cid]["status"] not in st:
        time.sleep(0.02)
    return c.st["campaigns"][cid]["status"]


tmp = Path(tempfile.mkdtemp())
# разбор списка
pl = parse_list("Анна Петрова <anna@mail.ru>\nivan@yandex.ru, Иван; office@firma.ru\nмусор без адреса")
ok([(x["name"], x["email"]) for x in pl] == [("Анна Петрова", "anna@mail.ru"), ("Иван", "ivan@yandex.ru"), ("", "office@firma.ru")],
   f"список: «Имя <адрес>», «адрес, Имя», просто адрес; строка без адреса — мимо: {pl}")
ok(render("Здравствуйте, {имя}!", {"name": "Анна Петрова", "email": "a@b.ru"}) == "Здравствуйте, Анна!"
   and render("Здравствуйте, {имя}!", {"name": "", "email": "a@b.ru"}) == "Здравствуйте!", "{имя} — имя; без имени — просто «Здравствуйте!»")

h = Host()
m = Mailing(h, tmp / "mailing.json")
m.pause_s = 0
src = m.sources()
ok(src["clients"] == 2 and src["team"] == 1 and src["tags"] == ["vip"] and src["boxes"] == ["boss@firma.ru"],
   f"источники: клиентов с верной почтой 2, сотрудников с почтой 1, метки и ящики: {src}")

# деловое письмо по списку: повторы отсеяны, каждому своё
d = m.draft("{имя}, расписание", "Здравствуйте, {имя}!\nВ пятницу работаем до 16.", "list",
            "Анна <anna@mail.ru>\nivan@yandex.ru, Иван\nANNA@mail.ru\n")
ok(d["total"] == 2 and d["skipped"]["dup"] == 1 and d["sample"]["subject"] == "Анна, расписание", f"черновик: 2 получателя, повтор убран, пример письма первому: {d['sample']}")
ok(not h.mail.sent, "черновик ничего не отправляет")
m.start(d["id"]); wait(m, d["id"])
ok([x["to"] for x in h.mail.sent] == ["anna@mail.ru", "ivan@yandex.ru"], "каждому — отдельное письмо, в «Кому» только он")
ok(h.mail.sent[1]["body"].startswith("Здравствуйте, Иван!") and "Отписаться" not in h.mail.sent[0]["body"]
   and not h.mail.sent[0]["headers"], "деловое: имя своё, строки об отписке и List-Unsubscribe нет")
ok(h.pushes and "«расписание»: ушло 2 из 2" in h.pushes[-1][1], f"итог — уведомлением: {h.pushes[-1:]}")
try:
    m.start(d["id"]); ok(False, "ушедшую рассылку второй раз не отправить")
except MailingError:
    ok(True, "ушедшую рассылку второй раз не отправить")

# реклама клиентам: стоп-лист из «Входящих», строка об отписке, заголовок
h.mail.sent.clear()
h.mail.inbox_items = [{"from": "Иван <ivan@yandex.ru>", "subject": "Re: Скидки", "snippet": "Отписаться"}]
d = m.draft("Скидки ноября", "{имя}, у нас скидки.", "clients", kind="ads")
ok(d["total"] == 2 and "Отписаться" in d["sample"]["body"], "реклама: в примере письма — как отписаться")
m.start(d["id"]); wait(m, d["id"])
ok([x["to"] for x in h.mail.sent] == ["anna@mail.ru"], f"ответ «Отписаться» во «Входящих» — ему уже не пишу: {[x['to'] for x in h.mail.sent]}")
ok(h.mail.sent and "List-Unsubscribe" in h.mail.sent[0]["headers"] and "boss@firma.ru" in h.mail.sent[0]["headers"]["List-Unsubscribe"],
   "реклама: заголовок List-Unsubscribe на свой адрес")
ok("ivan@yandex.ru" in m.stop_list(), "стоп-лист пополнился сам")
d2 = m.draft("Ещё", "Текст", "clients", kind="work")
ok(d2["total"] == 1 and d2["skipped"]["stop"] == 1, "отписавшимся не пишу и деловое (повторный черновик — его нет в получателях)")
m.stop_set(["anna@mail.ru"])
ok(m.stop_list() == ["anna@mail.ru"], "стоп-лист правится руками")
m.stop_set([])

# метка и сотрудники
ok(m.draft("Т", "Т", "clients", tag="vip")["total"] == 1, "клиентам по метке — только с меткой")
dt = m.draft("Планёрка", "{имя}, планёрка в 10.", "team")
ok(dt["total"] == 1 and dt["sample"]["to"] == "olga@firma.ru", "сотрудникам — у кого почта в карточке")
try:
    m.draft("Т", "Т", "list", "просто текст"); ok(False, "без адресов — понятная ошибка")
except MailingError as e:
    ok("ни одного адреса" in str(e), f"без адресов — понятная ошибка: {e}")

# ошибка доставки и дневной предел
h.mail.sent.clear(); h.mail.fail = {"b@x.ru"}
h.s.d[("mailing", "day_max")] = 2
m.st["day"] = {"date": "", "n": 0}
d = m.draft("Предел", "Текст", "list", "a@x.ru\nb@x.ru\nc@x.ru\nd@x.ru")
m.start(d["id"])
st = wait(m, d["id"], ("waiting",))
p = m.public(m.st["campaigns"][d["id"]])
ok(st == "waiting" and [x["to"] for x in h.mail.sent] == ["a@x.ru", "c@x.ru"] and p["failed"] == 1,
   f"предел 2 в день: ушло два, ошибка у одного считается, рассылка ждёт завтра: {st} {[x['to'] for x in h.mail.sent]} {p['failed']}")
ok(p["errors"] and p["errors"][0]["email"] == "b@x.ru", "у кого ошибка — видно")
m.stop(d["id"])
ok(m.st["campaigns"][d["id"]]["status"] == "stopped", "«Остановить» — останавливает и ожидание")
# новый день — «Продолжить» доотправит остальным
m.st["day"] = {"date": "2000-01-01", "n": 0}
time.sleep(0.05)
m.start(d["id"]); wait(m, d["id"])
ok([x["to"] for x in h.mail.sent] == ["a@x.ru", "c@x.ru", "d@x.ru"], f"«Продолжить» — только тем, кому ещё не ушло: {[x['to'] for x in h.mail.sent]}")

# после перезапуска — продолжает сама
h.mail.sent.clear(); h.s.d[("mailing", "day_max")] = 300
d = m.draft("Перезапуск", "Т", "list", "q@x.ru\nw@x.ru")
m.st["campaigns"][d["id"]]["status"] = "sending"; m._save()
m2 = Mailing(h, tmp / "mailing.json"); m2.pause_s = 0
m2.resume(); wait(m2, d["id"])
ok([x["to"] for x in h.mail.sent] == ["q@x.ru", "w@x.ru"], "после перезапуска рассылка продолжилась сама")

# сотрудник: почта в карточке
import team  # noqa: E402
T = team.Team.__new__(team.Team)
T._lock = threading.RLock(); T.st = {"members": {}, "tasks": {}}; T.bots = {}
T._changed = lambda: None; T.public = lambda: {"members": [dict(v, id=k) for k, v in T.st["members"].items()]}
r = T.member_add("Ольга", "бухгалтерия", "olga@firma.ru")
mid = r["members"][0]["id"]
ok(T.st["members"][mid].get("email") == "olga@firma.ru", "сотрудник с почтой при добавлении")
try:
    T.member_set(mid, email="не почта"); ok(False, "неверная почта — отказ")
except team.TeamError:
    ok(True, "неверная почта — понятный отказ")
T.member_set(mid, email="")
ok("email" not in T.st["members"][mid], "почту можно убрать")

# инструмент модели — с подтверждением, и в описании видно, кому и сколько
import tools  # noqa: E402
sp = tools.TOOLS.get("mailing")
ok(sp and sp[2] == "confirm" and tools.TOOLS.get("mailing_status") and tools.TOOLS["mailing_status"][2] == "safe",
   f"инструмент «mailing» — только с подтверждением, «mailing_status» — сразу: {sp and sp[2]}")
ok(mailing.plain("{имя}, расписание") == "расписание" and mailing.plain("Скидки для {имя}") == "Скидки для", "тема без {имя} — для уведомлений")
ok(mailing.PAUSE_S >= 5 and mailing.DAY_MAX <= 500, "по умолчанию — пауза между письмами и предел ниже почтовых")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
