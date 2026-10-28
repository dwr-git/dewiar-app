"""Телефон: детский режим (28.10, план владельца: «детский режим на телефоне», как на компьютере — core/kids.py).
«Ещё» → «Детский режим»: ребёнок, «можно», время, PIN родителя, «Включить». Включён — говорит Совёнок Уго (своя
подсказка с правилами, только безопасные умения, другие инструменты не выполняются), настройки, персонажи, «Близкие»
и «Душа» — только с PIN (неверный — нет; 15 минут после верного), время за день и «пора спать», просьбы вне правил —
в отчёт родителю; выключить — только с PIN, персонаж возвращается прежний."""
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
for f in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / f).exists():
        shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
shots = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 860})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("() => { S.llm.base_url = 'http://127.0.0.1:9/v1'; S.llm.model = 'm'; S.welcome = { on: false }; S.persona = 'patrik'; S.course = { offered: lnToday() }; saveS(); }")
    pg.reload(); pg.wait_for_timeout(1000)
    ok(pg.evaluate("() => !!window.DEWIAR_KIDS_PERSONA && DEWIAR_KIDS_PERSONA.id === 'ugo' && DEWIAR_KIDS_PERSONA.avatar.startsWith('data:image')"),
       "Совёнок Уго — в personas.js телефона, с обликом")
    pg.evaluate("() => openSettings('more')"); pg.wait_for_timeout(500)
    pg.evaluate("() => document.querySelector('#kids-open').click()"); pg.wait_for_timeout(500)
    ok(pg.evaluate("() => document.querySelector('#sh-kids').classList.contains('on') && !!document.querySelector('#kd-on')"), "«Ещё» → «Детский режим» → лист настройки")
    if shots: pg.screenshot(path=str(Path(shots) / "phone-kids-setup.png"), full_page=True)
    pg.fill("#kd-name", "Миша"); pg.fill("#kd-age", "7")
    pg.click("#kd-on"); pg.wait_for_timeout(400)
    ok(pg.evaluate("() => [kidsOn(), document.querySelector('#kd-res').textContent]") == [False, "Сначала задайте PIN родителя"], "без PIN не включается")
    pg.fill("#kd-pin", "1234"); pg.fill("#kd-pin2", "1243"); pg.click("#kd-on"); pg.wait_for_timeout(400)
    ok(pg.evaluate("() => !kidsOn() && document.querySelector('#kd-res').textContent.includes('не совпал')"), "PIN не совпал — не включается")
    pg.fill("#kd-pin", "1234"); pg.fill("#kd-pin2", "1234")
    pg.evaluate("() => document.querySelector('.kd-chip[data-k=homework]').click()")   # уроки — выключить
    pg.click("#kd-on"); pg.wait_for_timeout(1200)
    r = pg.evaluate("() => [kidsOn(), persona().id, document.body.classList.contains('kids'), S.kids.prev_persona, !(prefGet('kids_pin') || '').includes('1234'), JSON.stringify(S).includes('kids_pin')]")
    ok(r == [True, "ugo", True, "patrik", True, False], f"включён: говорит Уго, прежний персонаж запомнен, PIN — хэшем и не в настройках: {r}")
    sp = pg.evaluate("() => systemPrompt()")
    ok("ДЕТСКИЙ РЕЖИМ" in sp and "Миша, 7 лет" in sp and "С уроками не помогаешь" in sp and "Совёнок Уго" in sp, "подсказка модели — правила для ребёнка, его имя и возраст, без уроков")
    tools = pg.evaluate("() => toolSpecs().map(t => t.name)")
    ok(tools and set(tools) <= {"calc", "world_time", "weather", "set_reminder", "list_reminders", "cancel_reminder", "play_radio", "radio_control",
                                 "set_volume", "save_note", "find_notes", "show_images"} and "call" not in tools, f"только безопасные умения: {tools}")
    r = pg.evaluate("async () => [await runTool('call', { who: 'мама' }), await runTool('money_add', { amount: 5 })]")
    ok(all(str(x).startswith("Ошибка: в детском режиме") for x in r), "звонок и деньги — не выполняются, даже если модель попросит")
    # взрослые кнопки — за PIN
    pg.evaluate("() => document.querySelector('#b-set').click()"); pg.wait_for_timeout(500)
    ok(pg.evaluate("() => [document.querySelector('#sh-kpin').classList.contains('on'), document.querySelector('#sh-set').classList.contains('on')]") == [True, False],
       "шестерёнка — сначала PIN родителя, настройки закрыты")
    if shots: pg.screenshot(path=str(Path(shots) / "phone-kids-pin.png"))
    pg.fill("#kpin-in", "0000"); pg.click("#kpin-go"); pg.wait_for_timeout(1200)
    ok(pg.evaluate("() => [document.querySelector('#kpin-res').textContent, document.querySelector('#sh-set').classList.contains('on')]") == ["Неверный PIN", False], "неверный PIN — нет")
    pg.fill("#kpin-in", "1234"); pg.click("#kpin-go"); pg.wait_for_timeout(1500)
    ok(pg.evaluate("() => document.querySelector('#sh-set').classList.contains('on') && kidsUnlocked()"), "верный PIN — настройки открыты (на 15 минут)")
    ok(pg.evaluate("() => getComputedStyle(document.querySelector('#b-close')).display === 'none' && getComputedStyle(document.querySelector('#b-soul')).display === 'none'"),
       "«Близкие» и «Душа» в детском режиме спрятаны")
    pg.evaluate("() => { kidsUnlockUntil = 0; closeSheets(); }")
    # время и «пора спать»
    pg.evaluate("() => { S.kids.bedtime = '00:00'; S.kids.morning = '23:59'; saveS(); ask('Расскажи сказку'); }"); pg.wait_for_timeout(500)
    ok("пора спать" in pg.evaluate("() => document.querySelector('#bot').textContent"), "после «спать с» — Уго говорит, что пора спать, и не отвечает")
    pg.evaluate("() => { S.kids.bedtime = ''; S.kids.morning = ''; S.kids.min_weekday = S.kids.min_weekend = 1; saveS(); fileSave('kids.json', JSON.stringify({ days: { [kidsDayKey()]: { min: ['08:00'], asked: [], off: [] } } })); ask('Расскажи сказку'); }")
    pg.wait_for_timeout(500)
    ok("время закончилось" in pg.evaluate("() => document.querySelector('#bot').textContent"), "минуты на сегодня кончились — «наше время закончилось»")
    pg.evaluate("() => { S.kids.min_weekday = S.kids.min_weekend = 60; saveS(); }")
    pg.evaluate("() => { window._tg = []; S.account = Object.assign({}, S.account, { token: 'acc-test', services: { tg: 'dwrapp/tg.php' } }); S.tg = { linked: true }; tgCall = (m, b) => { _tg.push([m, b]); return Promise.resolve(true); }; }")
    r = pg.evaluate("() => [kidsTouch('Купи мне новую игру'), kidsTouch('Почему небо голубое?'), kidsReport()]")
    ok(r[0] is True and r[1] is False and len(r[2]["off"]) == 1 and r[2]["asked"][-1]["q"] == "Почему небо голубое?", f"вопросы — в отчёт, «купи» — вне правил: {r[2]['off']}")
    tg = pg.evaluate("_tg")
    ok(len(tg) == 1 and tg[0][0] == "sendMessage" and "Миша" in tg[0][1]["text"] and "Купи мне новую игру" in tg[0][1]["text"],
       f"вне правил — сразу родителю в Telegram (бот Dewiar привязан), обычные вопросы — нет: {tg}")
    # отчёт родителю и выключение
    pg.evaluate("() => kidsUnlockUntil = Date.now() + 60e3"); pg.evaluate("() => openKids()"); pg.wait_for_timeout(500)
    r = pg.evaluate("() => [document.querySelectorAll('.kd-q').length, document.querySelectorAll('.kd-q.off').length, !!document.querySelector('#kd-off')]")
    ok(r[0] >= 2 and r[1] == 1 and r[2], f"отчёт: о чём спрашивал, вне правил — отмечено; «Выключить»: {r}")
    if shots: pg.screenshot(path=str(Path(shots) / "phone-kids-report.png"), full_page=True)
    pg.click("#kd-off"); pg.wait_for_timeout(400)
    ok(pg.evaluate("() => [kidsOn(), persona().id, document.body.classList.contains('kids')]") == [False, "patrik", False], "выключен — снова Патрик, кнопки на месте")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
