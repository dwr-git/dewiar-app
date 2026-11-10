"""№586 (телефон 0.9.26, 06.11): «ни один персонаж не вернулся из режима „чат-бот“ в режим исполнителя». По журналу Лира
вызывала действия (поиск, start_task), но «возьми в задачу…» — «передана компьютеру, он уже берётся», а в «Задачах» пусто
(запись задачи приходит, только когда компьютер её взял), и так трижды — человек решил, что Лира только говорит. Теперь
отправленная задача видна сразу («ждёт, когда компьютер возьмёт»); не взята за 10 минут — честно (компьютер выключен или
Dewiar не запущен) и два выхода: «Сделать в облаке» (только облаку) и «Убрать»; пришла запись задачи — строка уходит.
Модели — без «он уже берётся», пока компьютер не взял."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820}); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("""() => { S.sync = { on: true }; window.syncChan = () => ({ base: 'x' }); window.syncSoon = () => {};
        qSet('tasksent', [{ id: 'q1', title: 'Агент Джарвис', goal: 'Сделай агента', ts: Date.now() - 60000, sent: Date.now() - 60000 },
                          { id: 'q2', title: 'Отчёт по продажам', goal: 'Собери отчёт', ts: Date.now() - 11 * 60000, sent: Date.now() - 11 * 60000 }]); }""")
    box = "() => { const d = document.createElement('div'); d.id = 'tkbox'; d.innerHTML = tasksHtml(); document.body.appendChild(d); wireTasks(d, () => { d.innerHTML = tasksHtml(); }); return d.innerText; }"
    t = pg.evaluate(box)
    ok("Агент Джарвис" in t and "ждёт, когда компьютер возьмёт" in t, f"отправленная задача видна сразу: {t[:200]!r}")
    ok("Отчёт по продажам" in t and "Компьютер пока не взял задачу" in t and "Сделать в облаке" in t and "Убрать" in t,
       "не взята за 10 минут — честно и два выхода")
    pg.evaluate("document.querySelector(\"[data-tks-cloud='q2']\").click()"); pg.wait_for_timeout(200)
    q = pg.evaluate("qGet('taskq')")
    ok(len(q) == 1 and q[0]["cloud"] and q[0]["to"] == "pc-cloud" and q[0]["goal"] == "Собери отчёт", f"«Сделать в облаке» — заявка только облаку: {q}")
    ok([x["id"] for x in pg.evaluate("qGet('tasksent')")] == ["q1"], "из ожидающих она ушла")
    # компьютер взял — пришла запись задачи с тем же названием
    pg.evaluate("""() => { const m = mind(); m.tasks = { t1: { title: 'Агент Джарвис', status: 'running', updated: new Date().toISOString() } }; saveMind(m); }""")
    pg.evaluate("() => document.getElementById('tkbox').remove()")
    t = pg.evaluate(box)
    ok("ждёт, когда компьютер возьмёт" not in t and pg.evaluate("qGet('tasksent').length") == 0, f"компьютер взял — строка ожидания ушла, задача — в списке: {t[:160]!r}")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.evaluate("""() => { qSet('tasksent', [{ id: 'q3', title: 'Отчёт по продажам', goal: 'x', ts: 1, sent: Date.now() - 11 * 60000 }]);
            const d = document.getElementById('tkbox'); d.innerHTML = tasksHtml(); d.style.cssText = 'position:fixed;inset:0;z-index:99999;background:var(--bg,#111);padding:16px;overflow:auto'; }""")
        pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "phone-tasksent586.png"))
    b.close()
src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("он уже берётся" not in src.split('case "start_task"')[1][:900], "модели — без «он уже берётся», пока компьютер не взял")
ok('qSet("tasksent"' in src, "отданная синхронизацией задача запоминается как ожидающая")
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
