"""Отчёт №845 (17.11, снимки): «Персонажи»: у Патрика выбран профиль OpenRouter и в «Модель Патрик» — google/gemini-4-hydrogen
(«сохранить» нажимал), а на карточке и на кнопке профиля — «OpenRouter — deepseek…»: показывалась модель профиля, а не своя
модель персонажа (llm.persona_model). Отвечал он при этом верной (ядро брало persona_model) — казалось, что выбор не
сохранился. Теперь своя модель — в названии везде: карточка, кнопка профиля в редакторе, «Кто чем думает» и «Мозг».
Настоящие ui/studio/personas.js и brain.js в settings.html."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


LLM = {"active": "dw", "profiles": {"dw": {"cloud": True, "name": "Dewiar"},
                                    "or": {"name": "OpenRouter — deepseek/deepseek-v4.1-flash", "model": "deepseek/deepseek-v4.1-flash",
                                           "base_url": "https://openrouter.ai/api/v1", "kind": "openai"}},
       "persona": {"patrick": "or", "lira": "or"}, "persona_model": {"patrick": "google/gemini-4-hydrogen"}}
PERS = [{"id": "lira", "name": "Лира", "color": "#7a7ff0", "tagline": "помощница", "skills": []},
        {"id": "patrick", "name": "Патрик", "color": "#4BE3A1", "tagline": "наставник", "skills": []}]
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda q: q.abort())
    pg.add_init_script("window.__stack = []; window.addEventListener('error', e => window.__stack.push(String(e.error && e.error.stack)));")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(800)
    pg.evaluate("""([llm, pers]) => { const w = document.querySelector('#wlc'); if (w) w.remove();
        core.call = async (c) => c === 'llm_models' ? ['deepseek/deepseek-v4.1-flash', 'google/gemini-4-hydrogen'] : [];
        S = S || {}; S.llm = llm; S.persona_memory = { own: [] }; personas = pers; active = "patrick"; SEC.seen.add("personas"); renderPersonas(); }""", [LLM, PERS])
    ok(pg.evaluate("brainLabel('patrick')") == "OpenRouter — google/gemini-4-hydrogen", f"своя модель Патрика: {pg.evaluate('brainLabel(\"patrick\")')}")
    ok(pg.evaluate("brainLabel('lira')") == "OpenRouter — deepseek/deepseek-v4.1-flash", "у Лиры своей модели нет — модель профиля")
    cards = pg.evaluate("[...document.querySelectorAll('#pgrid .card .pbrain')].map(x => x.textContent)")
    ok(any("gemini-4-hydrogen" in c for c in cards) and not any("Патрик" in c and "deepseek" in c for c in cards), f"на карточке Патрика — gemini: {cards}")
    pg.evaluate("() => { ed = personas[1]; document.querySelector('#e-brain') || document.body.insertAdjacentHTML('beforeend', '<div id=\"e-brain\"></div>'); renderBrain(); }")
    pg.wait_for_timeout(200)
    on = pg.evaluate("(document.querySelector('#e-brain .bp.on') || {}).textContent || ''")
    ok("gemini-4-hydrogen" in on and "deepseek" not in on, f"в редакторе выбранная кнопка — своя модель: {on!r}")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]} {pg.evaluate('window.__stack')[:1]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
