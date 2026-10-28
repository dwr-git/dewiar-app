"""Режим «Для старших» (0.58; владелец 28.10: «быстрые режимы — детский, для пожилых и обычный… чтобы понятно, чётко»;
«забота, которую видно»). Часть 1 — ядро без звука: senior.py и engine_senior.py на заглушках:
— включили — на «Главной» только нужное, крупнее, голос медленнее, разделы работы выключены; выключили — всё как было;
— лекарство: «выпила» — отмечено; не ответили — через 15 минут ещё раз; снова нет — присматривающим в «Близкие»;
— «всё хорошо» вечером и «ещё не говорила» днём — раз в день; мошенники — сразу «стоп» и сообщение близким;
— обычный вопрос про мошенников — не тревога; в режиме «Для меня» ничего этого нет."""
import os, sys, tempfile, threading
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import senior as SN  # noqa: E402
from engine_senior import SeniorMixin  # noqa: E402
from engine_tools import ToolsMixin  # noqa: E402


class Sett:
    def __init__(self, d): self.d = d
    def get(self, a, b=None):
        v = self.d.get(a)
        return v if b is None else (v or {}).get(b)
    def update(self, patch):
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(self.d.get(k), dict):
                self.d[k].update(v)
            else:
                self.d[k] = v
    def snapshot(self): return self.d


class Close:
    def __init__(self): self.sent = []
    people = [{"pid": "p1", "name": "Миша", "devs": [{"dev": "d"}]}, {"pid": "p2", "name": "Оля", "devs": []}]
    def state(self): return {"people": self.people}
    def person(self, who): return next(p for p in self.people if p["pid"] == who)
    def send(self, pid, text):
        if not self.person(pid)["devs"]:
            raise RuntimeError("не открывался")
        self.sent.append((pid, text))


class Rem:
    def __init__(self): self.items = []
    def add(self, when, text, repeat=None, kind="reminder", extra=None):
        it = dict({"id": f"r{len(self.items)}", "at": when.replace(microsecond=0).isoformat(), "text": text, "repeat": repeat, "kind": kind}, **(extra or {}))
        self.items.append(it); return it


NOW = [datetime(2026, 10, 28, 9, 0)]


class Eng(SeniorMixin):
    _care_item = SeniorMixin._care_item
    def __init__(self):
        self.s = Sett({"ui": {"home_apps": ["chat", "docs", "team", "notes"], "zoom": 1.0, "text": 1.0}, "tts": {"speed": 1.25},
                       "features": {"team": True, "clients": True}, "senior": {}, "user_name": ""})
        self.senior = SN.Senior(self.s, Path(tempfile.mkdtemp()) / "senior.json", now=lambda: NOW[0])
        self.close, self.reminders, self.events, self.said = Close(), Rem(), [], []
        self.stopping = threading.Event()
    def emit(self, ev, **kw): self.events.append((ev, kw))
    def _say_quick(self, msg, said, via=None, **k): self.said.append(msg)


E = Eng()
ok(E.mode() == "me" and not E.senior.scam("мне позвонили из банка, просят код из смс"), "по умолчанию — «Для меня»; тревог про мошенников нет")
E.s.d["ui"]["intro"] = ""
ok(E.mode_public()["first"] is True, "новый человек — первым экраном «Для кого эта Лира?»")
E.s.d["ui"]["mode_seen"] = 1
ok(E.mode_public()["first"] is False, "показан — больше сам не открывается")
E.mode_set("senior")
ui = E.s.d["ui"]
ok(E.mode() == "senior" and ui["home_apps"] == SN.HOME_APPS and ui["zoom"] >= 1.15 and ui["text"] >= 1.2 and E.s.d["tts"]["speed"] == 1.05
   and E.s.d["features"]["team"] is False and E.s.d["features"]["clients"] is False,
   "«Для старших»: на «Главной» только нужное, крупнее, голос медленнее, работа и клиенты выключены")
E.senior_set({"name": "Галина Петровна", "gender": "f", "watchers": ["p1", "p2"], "checkin": "20:30"})
c = E.senior.conf()
ok(c["name"] == "Галина Петровна" and c["watchers"] == ["p1", "p2"] and c["checkin"] == "20:30", "кто присматривает и когда вечерняя сводка")
p = E.senior.prompt()
ok("Галина Петровна" in p and "коды из СМС" in p and "просто" in p, "модель: просто, неторопливо, осторожно с деньгами")

# лекарство
med = E.senior_med_add("Таблетка от давления", ["09:00", "21:00"])
ok(len(med) == 2 and all(m["care"] and m["repeat"] == {"kind": "daily", "time": t} for m, t in zip(med, ("09:00", "21:00"))),
   "лекарство — каждый день в 9:00 и 21:00, с вопросом «выпили?»")
it = dict(med[0], at="2026-10-28T09:00:00")
E._care_after(it, "ack")
ok(E.senior.public()["today"]["meds"][0]["res"] == "taken", "«выпила» — отмечено")
NOW[0] = datetime(2026, 10, 28, 21, 0)
it2 = dict(med[1], at="2026-10-28T21:00:00")
E._care_after(it2, "missed")
again = E.reminders.items[-1]
ok(again["text"].startswith("Вы выпили лекарство?") and again["care_n"] == 1 and again["care_root"] == it2["id"]
   and again["at"] == "2026-10-28T21:15:00" and not E.close.sent, "не ответили — через 15 минут спросить ещё раз, близким пока ничего")
import time as _t  # noqa: E402
E._care_after(again, "seen")
_t.sleep(0.3)
ok(len(E.close.sent) == 1 and E.close.sent[0][0] == "p1" and "не ответила про «Таблетка от давления» в 21:00" in E.close.sent[0][1],
   f"снова нет — присматривающему (у кого Dewiar открыт): {E.close.sent}")
ok(not E._care_item({"text": "Позвонить в ЖЭС", "kind": "reminder"}) and E._care_item({"text": "Выпить капли в нос", "kind": "reminder"})
   and not E._care_item({"text": "Итог дня", "kind": "job"}), "лекарство узнаётся по словам; дела и обычные напоминания — нет")

# «всё хорошо» и полдень
S2 = SN.Senior(E.s, Path(tempfile.mkdtemp()) / "s.json", now=lambda: NOW[0])
NOW[0] = datetime(2026, 10, 29, 12, 5)
d = S2.due_checks()
ok([k for k, _ in d] == ["noon"] and "ещё не говорила" in d[0][1], "к полудню ни слова — «может, позвоните?»")
S2.sent("noon")
NOW[0] = datetime(2026, 10, 29, 13, 0); S2.touch()
NOW[0] = datetime(2026, 10, 29, 20, 31)
d = S2.due_checks()
ok([k for k, _ in d] == ["eve"] and "Всё хорошо" in d[0][1] and "говорила со мной в 13:00" in d[0][1], f"вечером — «всё хорошо»: {d}")
S2.sent("eve")
ok(S2.due_checks() == [], "раз в день")
NOW[0] = datetime(2026, 10, 30, 12, 1); S2.touch()
ok(S2.due_checks() == [], "утром говорила — днём не беспокоим")

# мошенники
for t in ("Мне позвонили из банка, говорят надо назвать код из смс", "Звонили из службы безопасности Сбербанка, просят перевести на безопасный счёт",
          "Внук попал в аварию, просят деньги", "пришло сообщение из госуслуг, просят продиктовать код"):
    ok(E.senior.scam(t), f"мошенники: «{t[:40]}…»")
for t in ("Расскажи про мошенников", "что такое безопасный счёт?", "позвони сыну", "какая погода", "напомни выпить таблетку"):
    ok(not E.senior.scam(t), f"не тревога: «{t}»")
E.close.sent.clear()
E._senior_scam("Мне позвонили из банка, просят код из смс", "Мне позвонили из банка, просят код из смс")
_t.sleep(0.3)
ok(E.said and E.said[-1].startswith("Галина Петровна, стоп.") and "Миша" in E.said[-1] and "коды из СМС" in E.said[-1],
   f"сразу — твёрдо и тепло, без модели: {E.said[-1][:90]}")
ok(E.close.sent and "Похоже на мошенников" in E.close.sent[0][1] and "Позвоните ей" in E.close.sent[0][1], "присматривающему — сразу")

# выключили — как было
E.mode_set("me")
ui = E.s.d["ui"]
ok(E.mode() == "me" and ui["home_apps"] == ["chat", "docs", "team", "notes"] and ui["zoom"] == 1.0 and E.s.d["tts"]["speed"] == 1.25
   and E.s.d["features"]["team"] is True, "«Для меня» — всё как было до режима")
ok(not E.senior.scam("Мне позвонили из банка, просят код из смс"), "вне режима — модель отвечает сама, без тревог")

# голос: «выпила» закрывает звонок лекарства, «нет, не пила» — спросить ещё раз
ok({"выпила", "выпил", "приняла"} <= ToolsMixin.ACK_WORDS, "«выпила», «приняла» — ответ на звонок")
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok('self.alarm_finish("seen" if med else "ack")' in src and "Отлично, отметила." in src, "заговорили о другом — лекарство не считается выпитым")

# Часть 2 — студия: «Лира — для меня ▾» на «Главной», три карточки, раздел «Для старших»
import re  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
SHOTS = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""() => { window._calls = []; window._st = { mode: 'me', senior: { name: '', gender: 'f', watchers: [], checkin: '20:00', noon: true, scam: true, on: false,
        today: { talk: [], meds: [], alerts: [] } }, people: [{ pid: 'p1', name: 'Миша', ready: true }, { pid: 'p2', name: 'Оля', ready: false }], kids_pin: false };
      window._rem = [];
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'mode_get') return Promise.resolve(_st);
        if (c === 'mode_set') { _st = Object.assign({}, _st, { mode: a.mode }); return Promise.resolve(_st); }
        if (c === 'senior_set') { _st = Object.assign({}, _st, { senior: Object.assign({}, _st.senior, a) }); return Promise.resolve(_st); }
        if (c === 'senior_med_add') { a.times.forEach((t, i) => _rem.push({ id: 'm' + _rem.length, text: a.text, care: true, at_hm: t, repeat_text: 'каждый день в ' + t })); return Promise.resolve(_st); }
        if (c === 'reminders') return Promise.resolve(_rem);
        if (c === 'reminder_cancel') { _rem = _rem.filter(x => x.id !== a.id); return Promise.resolve(_rem); }
        if (c === 'senior_test') return Promise.resolve({ sent: 1 });
        return Promise.resolve({}); };
      mdLoad(); }""")
    pg.wait_for_timeout(400)
    ok(pg.inner_text("#hm-mode") == "Лира — для меня", "на «Главной» — «Лира — для меня»")
    pg.click("#hm-mode"); pg.wait_for_timeout(300)
    r = pg.evaluate("() => [...document.querySelectorAll('#md-dlg .md-card .md-txt b')].map(x => x.textContent)")
    ok(r == ["Для меня", "Для ребёнка", "Для старших"] and pg.evaluate("document.querySelector('#md-dlg .md-card[aria-pressed=true]').dataset.m") == "me"
       and pg.evaluate("document.querySelectorAll('#md-dlg .md-card li').length") == 9 and pg.evaluate("document.querySelectorAll('#md-dlg .md-art svg').length") == 3,
       f"три карточки с рисунком, обещанием и тремя пунктами; текущая отмечена: {r}")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-modes.png"))
    pg.set_viewport_size({"width": 720, "height": 1000}); pg.wait_for_timeout(300)
    ok(pg.evaluate("(() => { const d = document.querySelector('#md-dlg'); return d.scrollWidth <= d.clientWidth + 1; })()"), "узкое окно — карточки друг под другом, без прокрутки вбок")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-modes-narrow.png"))
    pg.set_viewport_size({"width": 1400, "height": 1000}); pg.wait_for_timeout(200)
    pg.click('#md-dlg .md-card[data-m="senior"]'); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.querySelector('#p-senior').classList.contains('cur')") and "Режим выключен" in pg.inner_text("#sr-bar"),
       "«Для старших» → свой раздел, сначала настроить")
    pg.fill("#sr-name", "Галина Петровна"); pg.dispatch_event("#sr-name", "change"); pg.wait_for_timeout(200)
    pg.click('#sr-who input[data-pid="p1"]'); pg.wait_for_timeout(200)
    pg.fill("#sr-mtext", "Таблетка от давления"); pg.fill("#sr-mtimes", "09:00, 21:00"); pg.click("#sr-madd"); pg.wait_for_timeout(400)
    calls = pg.evaluate("_calls")
    ok(["senior_set", {"name": "Галина Петровна"}] in calls and ["senior_set", {"watchers": ["p1"]}] in calls
       and ["senior_med_add", {"text": "Таблетка от давления", "times": ["09:00", "21:00"]}] in calls, "имя, кто присматривает, лекарство — сохраняются")
    ok(pg.evaluate("document.querySelectorAll('#sr-meds .sr-med').length") == 2 and "ещё не открывал Dewiar" in pg.inner_text("#sr-who"),
       "лекарства — списком по времени; кто ещё не открыл Dewiar — так и сказано")
    pg.click("#sr-on"); pg.wait_for_timeout(400)
    ok(["mode_set", {"mode": "senior"}] in pg.evaluate("_calls") and "включён — Галина Петровна" in pg.inner_text("#sr-bar")
       and pg.inner_text("#hm-mode") == "Лира — для старших", "«Включить режим» — включён, на «Главной» — «для старших»")
    pg.click("#sr-test"); pg.wait_for_timeout(300)
    ok("Отправлено: 1" in pg.inner_text("#sr-tres"), "«Проверить» — пробное сообщение ушло")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-senior.png"), full_page=True)
    pg.click("#sr-off"); pg.wait_for_timeout(300)
    ok(["mode_set", {"mode": "me"}] in pg.evaluate("_calls") and pg.inner_text("#hm-mode") == "Лира — для меня", "«Вернуть обычный режим»")
    # 28.10, владелец: «удобнее, чтобы режимы удобно переключались… иконка с совой на главной не нужна?» — плитка «Режимы»
    ok(pg.evaluate("HM_APPS.some(a => a.id === 'modes') && !HM_APPS.some(a => a.id === 'kids') && HM_DEFAULT.includes('modes')"), "на «Главной» — «Режимы» вместо «Дети»")
    ok(pg.evaluate("(() => { S = S || {}; S.ui = Object.assign({}, S.ui, { home_apps: ['chat', 'kids', 'notes'], home_known: ['chat', 'kids', 'notes'] }); return hmApps(); })()")[:3] == ["chat", "modes", "notes"],
       "кто настраивал главную — «Дети» стали «Режимами» на том же месте")
    pg.evaluate("hmOpen('modes')"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#md-dlg').open"), "плитка «Режимы» — выбор «Для кого эта Лира?»")
    pg.evaluate("document.querySelector('#md-dlg').close()")
    nav = pg.evaluate("[...document.querySelectorAll('nav > *')].map(x => x.dataset.p || x.textContent)")
    i = nav.index("Режимы Лиры")
    ok(nav[i + 1:i + 3] == ["kids", "senior"], f"в меню — группа «Режимы Лиры»: «Для ребёнка», «Для старших»: {nav[i:i + 3]}")
    pg.set_viewport_size({"width": 700, "height": 1000}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
