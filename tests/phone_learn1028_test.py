"""Телефон: «Вопрос — ответ» и курсы (28.10, план владельца: «на телефоне — вопрос-ответ и курсы», как в студии).
«Ещё» → «Вопрос — ответ и курсы»: лист с двумя вкладками. Вопрос — ответ: плитки разделов руководства, статьи раздела,
статья с «Попробуйте сказать» (нажатие — фраза уходит Лире), поиск. Курсы: урок дня, шаги засчитываются сами (сказал
похожее, открыл лист), следующий урок — завтра или «Следующий урок сейчас», другие курсы, карточка «урок дня» раз в
день, «открой курсы» голосом."""
import json, os, shutil, subprocess, sys, tempfile
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
GUIDE = json.loads((ROOT / "data/guide.json").read_text(encoding="utf-8"))
(www / "guide.js").write_text("window.DEWIAR_GUIDE = " + json.dumps(GUIDE, ensure_ascii=False) + ";", encoding="utf-8")
GROUPS = list(dict.fromkeys(s.get("group") or "Ещё" for s in GUIDE))
errs = []
shots = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 860})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("() => { S.llm.base_url = 'http://127.0.0.1:9/v1'; S.llm.model = 'm'; S.welcome = { on: false }; S.course = { offered: lnToday() }; saveS(); }")
    pg.reload(); pg.wait_for_timeout(1200)
    pg.evaluate("() => { window._asked = []; ask = (t) => { _asked.push(t); return Promise.resolve(); }; }")
    # вход — «Ещё»
    pg.evaluate("() => openSettings('more')"); pg.wait_for_timeout(500)
    ok(pg.evaluate("() => !!document.querySelector('#qa-open') && !!document.querySelector('#course-open') && !document.querySelector('#guide-open')"),
       "«Ещё» → «Вопрос — ответ и курсы»: две кнопки вместо ссылки на сайт")
    pg.click("#qa-open"); pg.wait_for_timeout(500)
    r = pg.evaluate("() => [document.querySelector('#sh-learn').classList.contains('on'), [...document.querySelectorAll('.ln-tile b')].map(x => x.textContent), !!document.querySelector('#ln-q')]")
    ok(r[0] and r[1] == GROUPS and r[2], f"лист открыт: плитки всех разделов и поиск: {r[1]}")
    if shots: pg.screenshot(path=str(Path(shots) / "phone-qa.png"))
    pg.click(".ln-tile[data-g='Телефон']"); pg.wait_for_timeout(300)
    rows = pg.evaluate("() => [...document.querySelectorAll('.ln-row')].map(x => x.dataset.id)")
    ok(rows == [s["id"] for s in GUIDE if (s.get("group") or "Ещё") == "Телефон"] and rows, f"раздел «Телефон» — его статьи: {rows}")
    pg.click(f".ln-row[data-id='{rows[0]}']"); pg.wait_for_timeout(300)
    art = next(s for s in GUIDE if s["id"] == rows[0])
    r = pg.evaluate("() => [document.querySelector('.ln-art h3').textContent, document.querySelectorAll('.ln-try').length, document.querySelectorAll('.ln-how li').length]")
    ok(r[0] == art["title"] and r[1] == min(6, len(art.get("say") or [])) and r[2] == len(art.get("how") or []), f"статья: заголовок, «как сделать», фразы: {r}")
    if shots: pg.screenshot(path=str(Path(shots) / "phone-qa-art.png"))
    if r[1]:
        pg.click(".ln-try"); pg.wait_for_timeout(500)
        ok(pg.evaluate("_asked")[-1:] == [art["say"][0]] and not pg.evaluate("document.querySelector('#sh-learn').classList.contains('on')"),
           "«Попробуйте сказать» — фраза уходит Лире, лист закрывается")
    # статья компьютера — пометка
    pc = next((s for s in GUIDE if "phone" not in (s.get("where") or [])), None)
    if pc:
        pg.evaluate("(id) => openLearn('qa', id)", pc["id"]); pg.wait_for_timeout(400)
        ok(pg.evaluate("() => !!document.querySelector('.ln-pc')"), "статья только для компьютера — с пометкой «это на компьютере»")
    # назад и поиск
    pg.click("#ln-back"); pg.wait_for_timeout(200)
    pg.evaluate("() => { LN.group = ''; LN.hits = null; LN.art = ''; lnQA(); }")
    pg.fill("#ln-q", "будильник"); pg.wait_for_timeout(600)
    r = pg.evaluate("() => [document.querySelectorAll('.ln-row').length, document.querySelector('.ln-cnt').textContent, document.activeElement && document.activeElement.id]")
    ok(r[0] >= 1 and r[1].startswith("Нашлось") and r[2] == "ln-q", f"поиск на лету, поле остаётся в фокусе: {r}")
    pg.fill("#ln-q", "квантовая хромодинамика"); pg.wait_for_timeout(600)
    ok(pg.evaluate("() => !document.querySelector('.ln-row') && !!document.querySelector('#ln-ask')"), "ничего не нашлось — «Спросить Лиру»")
    # курсы
    pg.click("#ln-tabs button[data-t='course']"); pg.wait_for_timeout(300)
    r = pg.evaluate("() => [document.querySelector('.ln-ht b').textContent, document.querySelectorAll('.ln-d').length, document.querySelectorAll('.ln-d.today').length, document.querySelectorAll('.ln-step').length, document.querySelectorAll('.ln-oc').length]")
    ok(r == ["Неделя с Лирой", 7, 1, 3, 1], f"курсы: «Неделя с Лирой», семь дней, урок 1 сегодня, три шага, другой курс ниже: {r}")
    if shots: pg.screenshot(path=str(Path(shots) / "phone-course.png"))
    pg.evaluate("() => courseHeard('Лира, что ты умеешь?')"); pg.wait_for_timeout(1100)
    ok(pg.evaluate("() => [S.course.c.week.steps[1], document.querySelectorAll('.ln-steps li.ok').length]") == [[0], 1], "сказал «что ты умеешь» — первый шаг засчитан и отмечен")
    pg.evaluate("() => { courseHeard('Напомни через 10 минут проверить чайник'); courseHeard('Какие у меня дела?'); }"); pg.wait_for_timeout(1100)
    r = pg.evaluate("() => [S.course.c.week.done[1] === lnToday(), document.querySelector('.ln-lesson').classList.contains('wait'), !!document.querySelector('#ln-ahead'), document.querySelectorAll('.ln-d.done').length]")
    ok(r == [True, True, True, 1], f"три шага — урок пройден; второй — завтра или «Следующий урок сейчас»: {r}")
    pg.evaluate("() => courseHeard('Запланируй на завтра в 10 забрать посылку')")
    ok(pg.evaluate("() => !(S.course.c.week.steps[2] || []).length"), "пока урок закрыт — шаги не засчитываются")
    pg.click("#ln-ahead"); pg.wait_for_timeout(300)
    ok(pg.evaluate("() => [document.querySelector('.ln-lh b').textContent, document.querySelectorAll('.ln-step').length]") == ["Мой день", 3], "«Следующий урок сейчас» — урок 2 открыт")
    pg.evaluate("() => { closeSheets(); openSheet('#sh-day'); }"); pg.wait_for_timeout(1100)
    ok(pg.evaluate("() => S.course.c.week.steps[2]") == [2], "открыл «Мой день» — шаг «Нажмите календарик» засчитан сам")
    # нажатие шага: фраза — Лире; «Нажмите…» — открыть лист
    pg.evaluate("() => openLearn('course')"); pg.wait_for_timeout(400)
    pg.click(".ln-step[data-i='0']"); pg.wait_for_timeout(500)
    ok(pg.evaluate("_asked")[-1] == "Запланируй на завтра в 10 забрать посылку", "нажал шаг — фраза ушла Лире")
    # другие курсы
    pg.evaluate("() => openLearn('course')"); pg.wait_for_timeout(400)
    pg.click(".ln-oc[data-c='close']"); pg.wait_for_timeout(300)
    r = pg.evaluate("() => [S.course.course, document.querySelector('.ln-ht b').textContent, document.querySelectorAll('.ln-d').length, document.querySelector('.ln-oc').dataset.c]")
    ok(r == ["close", "Лира и близкие", 3, "week"], f"другой курс — свой ход, «Неделя» осталась ниже: {r}")
    pg.evaluate("() => { S.course.course = 'week'; saveS(); closeSheets(); }")
    # голосом
    r = pg.evaluate("async () => [(await quick('Лира, открой курсы')).say, (await quick('вопрос — ответ')).say]")
    ok("«Мой день»" in r[0] and "Вопрос — ответ" in r[1], f"«открой курсы», «вопрос — ответ» — без модели: {r}")
    pg.wait_for_timeout(600)
    ok(pg.evaluate("() => document.querySelector('#sh-learn').classList.contains('on')"), "и лист открылся")
    # урок дня — карточкой раз в день
    pg.evaluate("() => { closeSheets(); showCard(''); S.course.offered = ''; S.course.skip = ''; saveS(); }")
    r = pg.evaluate("() => [lnOffer(), !!document.querySelector('.ln-card'), lnOffer()]")
    ok(r[0] and r[1], f"урок дня — карточка «Пять минут — начнём?»: {r}")
    if shots: pg.screenshot(path=str(Path(shots) / "phone-course-card.png"))
    pg.click("#ln-skip"); pg.wait_for_timeout(200)
    r = pg.evaluate("() => [S.course.skip === lnToday(), !!document.querySelector('.ln-card'), (S.course.offered = '', lnOffer())]")
    ok(r == [True, False, False], f"«Не сегодня» — до завтра: {r}")
    pg.evaluate("() => { S.course.skip = ''; S.course.offered = ''; S.course.offer = false; saveS(); }")
    ok(pg.evaluate("() => lnOffer()") is False, "«Предлагать урок дня» выключено — карточки нет")
    # сохраняется
    pg.reload(); pg.wait_for_timeout(1000)
    ok(pg.evaluate("() => [S.course.c.week.done[1] === lnToday(), S.course.c.week.ahead]") == [True, 2], "ход курса сохраняется между запусками")
    # светлая тема — без ошибок
    pg.evaluate("() => { document.body.classList.add('light'); openLearn('qa'); }"); pg.wait_for_timeout(300)
    if shots: pg.screenshot(path=str(Path(shots) / "phone-qa-light.png"))
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
