"""Владелец 19.11 про утреннюю сводку в виджете (Ubuntu): «текста много, и он немного плотный, одной кашей». Длинный ответ —
абзацами: пустые строки — абзацы; сплошной текст длиннее ~300 знаков делится по концам предложений на абзацы по 2–3
предложения (не рвём «+6°, днём до +8°» и сокращения со строчной буквы после точки). Короткий ответ — как был, одной строкой.
DEWIAR_SHOTS=<папка> — снимок cap-paras.png."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = re.search(r'CORE = r"""(.*?)"""', (ROOT / "tests/cap1103_test.py").read_text(encoding="utf-8"), re.S).group(1)
BRIEF = ("Доброе утро, Миша! Сегодня четверг, 19 ноября, в Минске пасмурно, +6°, днём до +8°, и дождь вероятен почти на сто "
         "процентов — зонт обязателен. Дел на сегодня у тебя нет, так что день можно провести спокойно и без спешки. Из интересного "
         "в Радаре — OpenAI представила GPT-6.2 Astra с контекстом в миллион токенов, но у модели уже выявили проблемы с контролем, "
         "так что протоколы безопасности, видимо, придётся пересматривать. Если хочешь, могу открыть её в Радаре. По деньгам всё "
         "тихо: за месяц ни доходов, ни расходов. Хорошего тебе дня, т. е. спокойного!")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 400, "height": 700}, device_scale_factor=2); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1200)
    pg.evaluate("(t) => { core.emit('state', { state: 'idle' }); core.emit('heard', { text: 'Утренняя сводка' }); core.emit('answer', { text: t, done: true }); }", BRIEF)
    pg.wait_for_timeout(300)
    ps = pg.evaluate("() => [...document.querySelectorAll('#bot p')].map(p => p.textContent)")
    ok(3 <= len(ps) <= 5, f"сводка — {len(ps)} абзаца, а не одна каша")
    ok(" ".join(ps) == BRIEF, "текст тот же, ничего не потеряно и не добавлено")
    ok(all(len(x) <= 330 for x in ps), f"абзацы по 2–3 предложения: {[len(x) for x in ps]}")
    ok(not any(x.startswith(("е.", "днём")) for x in ps) and any("+6°, днём до +8°" in x for x in ps), "не рвём «+6°, днём…» и «т. е.»")
    ok(pg.evaluate("() => document.getElementById('bot').classList.contains('long')"), "длинный ответ — чуть просторнее строки")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "cap-paras.png"))
    pg.evaluate("() => core.emit('answer', { text: 'Сейчас 09:31.', done: true })"); pg.wait_for_timeout(200)
    ok(pg.evaluate("() => document.querySelectorAll('#bot p').length") == 0 and pg.inner_text("#bot") == "Сейчас 09:31.", "короткий ответ — как был")
    pg.evaluate("() => core.emit('answer', { text: 'Первое.\\n\\nВторое.', done: true })"); pg.wait_for_timeout(200)
    ok(pg.evaluate("() => [...document.querySelectorAll('#bot p')].map(p => p.textContent)") == ["Первое.", "Второе."], "пустая строка — абзац")
    ok(not errs, f"без ошибок на странице: {errs}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
