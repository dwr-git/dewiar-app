"""Студия, «Поручения» → «Приложение Dewiar» (0.55, режим «Сотрудник»; владелец: «рассчитывать только на мессенджеры не
стоит»). Без способов — первым предложено приложение: бот не нужен, «Включить» → team_connect {ch: app}. Включено — у
сотрудника «Печать для приложения» (team_app_invite) → окно с печатью Dewiar и ссылкой; в карточке — маленькая печать
и ссылка; вошедшему — «в приложении Dewiar» и «Новый код» (renew, с вопросом); ушедшему — «ушла из приложения»;
в «Как это работает» — строка «Приложение Dewiar · включено» с «Выключить». Данные — настоящий Team.public()."""
import json, os, sys, tempfile, time, types
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

host = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *a: None), emit=lambda *a, **k: None, push=lambda *a, **k: None,
                             announce=lambda *a: None, close=object(), credentials=lambda: ("tok", ""))
tmp = Path(tempfile.mkdtemp())
team = TM.Team(host, tmp / "team.json", tmp / "team_bot.json")
off = team.public()
ok(not off["connected"] and any(b["ch"] == "app" and not b["connected"] for b in off["bots"]), "без способов — не подключено, приложение в списке")
team.st["app_on"] = True
team.st["company"] = "Ромашка"
exp = int(time.time()) + 13 * 86400
team.st["members"] = {
    "m1": {"id": "m1", "name": "Анна Ким", "role": "продажи", "tg": {"id": "p1", "chat": "p1", "ch": "app"}},
    "m2": {"id": "m2", "name": "Иван Петров", "role": "склад", "app_inv": {"link": "https://dewiar.pro/dwrapp/download.php?work=AbC123", "token": "AbC123", "expires": exp}},
    "m3": {"id": "m3", "name": "Ольга Сидорова", "role": "", "left": time.time()},
    "m4": {"id": "m4", "name": "Пётр Орлов", "role": ""},
}
on = team.public()
mm = {m["id"]: m for m in on["members"]}
ok(on["connected"] and mm["m1"]["chk"] == "app" and mm["m2"]["app"]["link"].endswith("AbC123") and mm["m3"]["left"], "Team.public(): канал, код, «ушла»")
inv = json.loads(json.dumps(on))
for m in inv["members"]:
    if m["id"] == "m4":
        m["app"] = {"link": "https://dewiar.pro/dwrapp/download.php?work=ZzZ999", "expires": exp}

with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""([off, on, inv]) => { window._calls = []; window._st = off;
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'team_get') return Promise.resolve(_st);
        if (c === 'team_connect') { _st = on; return Promise.resolve(on); }
        if (c === 'team_app_invite') { _st = a.id === 'm4' ? inv : on; return Promise.resolve(_st); }
        if (c === 'team_forget') return Promise.resolve(Object.assign({}, on, { connected: false }));
        return Promise.resolve({}); };
      window.ask = () => Promise.resolve(true);
      if (!S) S = {}; S.features = Object.assign({}, S.features, { team: true });
      const nb = document.querySelector('nav button[data-p=team]'); nb.hidden = false; nb.click(); }""", [off, on, inv])
    pg.wait_for_timeout(700)
    r = pg.evaluate("""() => [!document.querySelector('#tm-setup').hidden, document.querySelector('#tm-chs button.on').dataset.ch,
      !document.querySelector('#tm-steps-app').hidden, document.querySelector('#tm-steps-tg').hidden,
      getComputedStyle(document.querySelector('#tm-conn-bot')).display, getComputedStyle(document.querySelector('#tm-conn-app')).display,
      getComputedStyle(document.querySelector('#tm-steps-tg')).display, getComputedStyle(document.querySelector('#tm-tabs')).display]""")
    ok(r == [True, "app", True, True, "none", "flex", "none", "none"], f"настройка: первым — «Приложение Dewiar», без токена, кнопка «Включить»: {r}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-team-app-setup.png"))
    pg.click("#tm-chs button[data-ch=tg]")
    r = pg.evaluate("() => [document.querySelector('#tm-steps-app').hidden, !document.querySelector('#tm-steps-tg').hidden, getComputedStyle(document.querySelector('#tm-conn-bot')).display, document.querySelector('#tm-note-app').hidden]")
    ok(r == [True, True, "flex", True], f"вкладка Telegram — шаги и токен, как раньше: {r}")
    pg.click("#tm-chs button[data-ch=app]"); pg.click("#tm-app-on"); pg.wait_for_timeout(500)
    ok(["team_connect", {"token": "", "ch": "app"}] in pg.evaluate("_calls") and pg.evaluate("!document.querySelector('#tm-peoplewrap').hidden"),
       "«Включить» → team_connect {ch: app}, сразу «Сотрудники»")
    rows = pg.evaluate("() => [...document.querySelectorAll('#tm-people > li')].map(li => [li.querySelector('b').textContent, (li.querySelector('.tm-chip') || {}).textContent, [...li.querySelectorAll('.tm-pacts button')].map(x => x.textContent), !!li.querySelector('.tm-seal svg')])")
    by = {x[0]: x for x in rows}
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-team-app-people.png"))
    ok(by["Анна Ким"][1] == "в приложении Dewiar" and "Новый код" in by["Анна Ким"][2], f"вошла в приложении — «в приложении Dewiar», «Новый код»: {by['Анна Ким']}")
    ok(by["Иван Петров"][1] == "ждём входа" and by["Иван Петров"][3], f"приглашён — маленькая печать и ссылка в карточке: {by['Иван Петров']}")
    ok(by["Ольга Сидорова"][1] == "ушла из приложения" and "Печать для приложения" in by["Ольга Сидорова"][2], f"ушла — видно, можно пригласить снова: {by['Ольга Сидорова']}")
    ok(by["Пётр Орлов"][1] == "ещё не приглашён" and "Печать для приложения" in by["Пётр Орлов"][2] and not any("Новая ссылка" in x for x in by["Пётр Орлов"][2]),
       f"новый — «Печать для приложения» (без бота «Новой ссылки» в мессенджер нет): {by['Пётр Орлов']}")
    pg.locator("#tm-people li", has_text="Пётр Орлов").locator("[data-app]").click(); pg.wait_for_timeout(600)
    r = pg.evaluate("() => [document.querySelector('#tm-sealdlg').open, document.querySelector('#tm-sealdlg h3').textContent, !!document.querySelector('#tm-sealdlg .tm-sealbox svg'), document.querySelector('#tm-sealdlg .tm-sealbox').classList.contains('seal'), document.querySelector('#tm-sealdlg .tm-sealnote').textContent]")
    ok(["team_app_invite", {"id": "m4", "renew": False}] in pg.evaluate("_calls") and r[0] and r[1] == "Пётр Орлов", f"«Печать для приложения» → окно с печатью: {r[:4]}")
    ok(r[2] and r[3] and "наведёт камеру" in r[4] and "13 дней" in r[4], f"печать Dewiar, подсказка и срок: {r[4]}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-team-app-seal.png"))
    pg.click("#tm-sealdlg [data-qr]"); pg.wait_for_timeout(200)
    ok(pg.evaluate("() => !document.querySelector('#tm-sealdlg .tm-sealbox').classList.contains('seal') && !!document.querySelector('#tm-sealdlg .tm-sealbox svg')"), "«Показать обычный QR»")
    pg.click("#tm-sealdlg [data-x]"); pg.wait_for_timeout(200)
    ok(not pg.evaluate("document.querySelector('#tm-sealdlg').open"), "«Готово» закрывает")
    pg.locator("#tm-people li", has_text="Анна Ким").locator("[data-renew]").click(); pg.wait_for_timeout(500)
    ok(["team_app_invite", {"id": "m1", "renew": True}] in pg.evaluate("_calls"), "«Новый код» вошедшей — renew (сменила телефон)")
    pg.evaluate("() => document.querySelector('#tm-sealdlg').open && document.querySelector('#tm-sealdlg').close()")
    ok(pg.inner_text("#tm-padd") == "Добавить и показать печать", "без ботов — «Добавить и показать печать»")
    pg.evaluate("""(inv) => { const nm = inv.members.find(m => m.id === 'm4'); const add = Object.assign({}, nm, { id: 'm5', name: 'Вера Лис' });
      const st1 = Object.assign({}, _st, { members: _st.members.concat([Object.assign({}, add, { app: null })]) });
      const st2 = Object.assign({}, _st, { members: _st.members.concat([add]) });
      const prev = core.call; core.call = (c, a) => { if (c === 'team_member_add') { _calls.push([c, a]); _st = st1; return Promise.resolve(st1); }
        if (c === 'team_app_invite' && a.id === 'm5') { _calls.push([c, a]); _st = st2; return Promise.resolve(st2); } return prev(c, a); }; }""", inv)
    pg.fill("#tm-pname", "Вера Лис"); pg.click("#tm-padd"); pg.wait_for_timeout(700)
    ok(["team_app_invite", {"id": "m5", "renew": False}] in pg.evaluate("_calls") and pg.evaluate("document.querySelector('#tm-sealdlg').open")
       and pg.inner_text("#tm-sealdlg h3") == "Вера Лис", "добавила — сразу печать для приложения")
    pg.click("#tm-sealdlg [data-x]")
    pg.click("#tm-tabs button[data-t=how]"); pg.wait_for_timeout(300)
    bt = pg.inner_text("#tm-bots")
    ok("Приложение Dewiar" in bt and "включено, без бота" in bt and "@" not in bt.split("\n")[0] and pg.locator("#tm-bots [data-off=app]").count() == 1, f"«Как это работает»: {bt!r}")
    pg.click("#tm-bots [data-off=app]"); pg.wait_for_timeout(400)
    ok(["team_forget", {"ch": "app"}] in pg.evaluate("_calls"), "«Выключить» → team_forget {ch: app}")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
