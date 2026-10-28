"""Ответ сотруднику из студии (0.56; владелец: «сотрудник может написать руководителю, а ответить ему из студии нельзя»).
Ядро: Team.message(who, text) — уходит туда же, где сотрудник получает поручения (бот или приложение Dewiar), с подписью
руководителя; в «Сообщения» ложится исходящее «вы → он»; не вошедшему — понятная ошибка. Голосом — team_message.
Студия: у входящего — «Ответить» → team_message {id, text}; исходящее — «Вы → Анна Ким»; в поручении — «Написать»."""
import os, sys, tempfile, types
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


import team as TM  # noqa: E402
import tools as TL  # noqa: E402

host = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *a: None), emit=lambda *a, **k: None, push=lambda *a, **k: None,
                             announce=lambda *a: None, close=object(), credentials=lambda: ("tok", ""))
tmp = Path(tempfile.mkdtemp())
team = TM.Team(host, tmp / "team.json", tmp / "team_bot.json")
team.st["app_on"] = True
team.st["members"] = {
    "m1": {"id": "m1", "name": "Анна Ким", "role": "продажи", "tg": {"id": "p1", "chat": "p1", "ch": "app"}},
    "m2": {"id": "m2", "name": "Иван Петров", "role": "склад"},
}
sent = []
team._send = lambda chat, text, buttons=None, ch=None: (sent.append((chat, text, ch)), "sent")[1]
team.st.setdefault("inbox", []).append({"ts": 1, "who": "m1", "t": "Клиент просит скидку — можно 5%?"})
pub = team.message("Анна", "Да, 5% можно, оформляй")
ok(sent and sent[-1][0] == "p1" and sent[-1][1].endswith(": Да, 5% можно, оформляй") and sent[-1][2] == "app", f"ушло Анне в приложение, с подписью руководителя: {sent}")
last = pub["inbox"][-1]
ok(last.get("out") and last["name"] == "Анна Ким" and last["t"] == "Да, 5% можно, оформляй", f"в «Сообщения» — исходящее: {last}")
try:
    team.message("m2", "Привет"); ok(False, "не вошедшему — ошибка")
except TM.TeamError as e:
    ok("Иван Петров ещё не вошёл" in str(e), f"не вошедшему — понятно, почему не дойдёт: {e}")
try:
    team.message("m1", "  "); ok(False, "пустое — ошибка")
except TM.TeamError as e:
    ok("что написать" in str(e), "пустое — «что написать?»")
team._send = lambda *a, **k: None
try:
    team.message("m1", "ещё"); ok(False, "не отправилось — ошибка")
except TM.TeamError as e:
    ok("не отправилось" in str(e) and not [x for x in team.st["inbox"] if x.get("t") == "ещё"], "сбой связи — ошибка, в «Сообщения» не записано")
team._send = lambda chat, text, buttons=None, ch=None: (sent.append((chat, text, ch)), "sent")[1]
ctx = {"team": team}
TL._team = lambda c: c["team"]
r = TL.t_team_message({"who": "Анна", "text": "Перезвони мне"}, ctx)
ok("Отправила" in r and sent[-1][1].endswith("Перезвони мне"), "голосом: team_message")
ok("team_message" in TL.TOOLS, "у модели есть инструмент team_message")
team.assign("Анна", "Позвонить в «Ромашку»")
pub = team.public()

with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""(st) => { window._calls = []; window._st = st;
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'team_get' || c === 'team_message') return Promise.resolve(_st);
        return Promise.resolve({}); };
      window.askText = () => Promise.resolve('Хорошо, жду отчёт');
      if (!S) S = {}; S.features = Object.assign({}, S.features, { team: true });
      const nb = document.querySelector('nav button[data-p=team]'); nb.hidden = false; nb.click(); }""", pub)
    pg.wait_for_timeout(700)
    items = pg.evaluate("() => [...document.querySelectorAll('#tm-detail .tm-inbox li')].map(li => [li.className, li.querySelector('b').textContent, !!li.querySelector('.tm-reply')])")
    ok(items and items[0][0] == "out" and items[0][1] == "Вы → Анна Ким" and not items[0][2], f"исходящее — «Вы → Анна Ким», без «Ответить»: {items[:1]}")
    inc = [x for x in items if x[0] != "out"]
    ok(inc and inc[0][1] == "Анна Ким" and inc[0][2], f"входящее — с «Ответить»: {inc}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-team-reply.png"))
    pg.locator("#tm-detail .tm-reply").first.click(); pg.wait_for_timeout(400)
    ok(["team_message", {"id": "m1", "text": "Хорошо, жду отчёт"}] in pg.evaluate("_calls") and "Отправлено: Анна Ким" in pg.inner_text("#toast"),
       "«Ответить» → team_message, «Отправлено: Анна Ким»")
    pg.locator("#tm-board .tm-card").first.click(); pg.wait_for_timeout(300)
    pg.locator("#tm-detail [data-a=write]").click(); pg.wait_for_timeout(400)
    ok(pg.evaluate("_calls.filter(c => c[0] === 'team_message').length") == 2, "в поручении — «Написать» исполнителю")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
