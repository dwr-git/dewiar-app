"""«Кто чем думает» на «Главной» (владелец 15.11: «вставить ключ Gemini, потом Kimi или GLM — несколькими кликами, чтобы
каждый персонаж мог работать на своей модели… гибридные системы»; «важно подрубать любых внешних вендоров, а в них любые
модели»).
1. Рядом с «Лира — для меня» — кнопка с моделью, которой думает говорящий персонаж.
2. Окно: «Все» и по строке на персонажа → выбор из подключённых («как у всех» у персонажа) → llm.persona / llm.active.
3. «Подключить по ключу»: плитка сервиса → ключ → ВЕСЬ список моделей с поиском и «рекомендую» → проверка живым вопросом →
   кому. Та же пара «сервис + ключ + модель» — тот же профиль. «Свой адрес» — любой сервис «как OpenAI».
4. Подстраховка (llm.key_fallback, по умолчанию да): сервис по ключу не ответил — отвечает Dewiar, одной фразой почему;
   своя модель (LM Studio) — по-прежнему только с согласия (own_fallback)."""
import json, os, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = os.environ.get("DEWIAR_SHOTS", "")
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


S = {"llm": {"active": "dewiar-cloud", "profiles": {
    "dewiar-cloud": {"name": "Dewiar Облако", "kind": "openai", "base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "model": "chat", "cloud": True, "title": "DWR Chat Qwen 3.8"},
    "lm": {"name": "LM Studio — qwen3-8b", "kind": "openai", "base_url": "http://127.0.0.1:1234/v1", "model": "qwen3-8b"}},
    "persona": {}, "persona_model": {}, "key_fallback": True}, "ui": {"news_seen": "99.0.0", "welcome": "done"}}
PERS = [{"id": "lira", "name": "Лира", "color": "#7a7ff0", "tagline": "твоя помощница"}, {"id": "patrick", "name": "Патрик", "color": "#4BE3A1", "tagline": "друг"},
        {"id": "themis", "name": "Фемида", "color": "#e8806a", "role": "юрист"}]
PRESETS = {"gemini": {"name": "Google Gemini", "kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
           "kimi": {"name": "Kimi", "kind": "openai", "base_url": "https://api.moonshot.ai/v1"}}
CORE = r"""(() => { window.calls = []; const S0 = __S__, PERS = __P__, PRE = __PRE__;
  const merge = (a, b) => { for (const k in b) { if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k] && typeof a[k] === "object") merge(a[k], b[k]); else a[k] = b[k]; } return a; };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    window.SS = JSON.parse(JSON.stringify(S0));
    core.call = async (c, a) => { calls.push([c, JSON.parse(JSON.stringify(a || {}))]);
      if (c === "settings_save") { merge(SS, a.patch); return JSON.parse(JSON.stringify(SS)); }
      if (c === "llm_models") { if (a.profile.api_key === "bad") throw new Error("сервер отклонил ключ доступа (проверьте API-ключ)");
        if (/moonshot/.test(a.profile.base_url)) return ["moonshot-v1-8k", "kimi-k2-0905-preview", "kimi-latest", "kimi-k2-turbo-preview"];
        return ["gemini-2.5-pro", "gemini-2.5-flash", "text-embedding-004", "gemini-flash-latest", "gemma-3-27b-it"]; }
      if (c === "llm_test") return a.profile.model === "gemma-3-27b-it" ? { ok: false, error: "модель не поддерживает чат" } : { ok: true, model: a.profile.model, total_ms: 1840, reply: "Привет" };
      if (c === "mail_inbox") return { on: false, items: [] };
      return null; };
    setTimeout(() => { core.emit("hello", { settings: JSON.parse(JSON.stringify(SS)), personas: PERS, persona: "lira", presets: PRE, piper_voices: [], voice_fx: [] }); }, 200); };
  ready(); })();""".replace("__S__", json.dumps(S, ensure_ascii=False)).replace("__P__", json.dumps(PERS, ensure_ascii=False)).replace("__PRE__", json.dumps(PRESETS, ensure_ascii=False))
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1300, "height": 900})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&skin=neusky")
    pg.wait_for_timeout(1800)
    pg.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); }")
    ok(pg.is_visible("#hm-brain") and "Qwen 3.8" in pg.inner_text("#hm-brain"), f"на «Главной» — чем думает Лира: {pg.inner_text('#hm-brain')!r}")
    pg.click("#hm-brain")
    pg.wait_for_timeout(300)
    rows = pg.locator("#br-body .br-row")
    ok(rows.count() == 4 and "Все" in rows.nth(0).inner_text() and "как у всех" in rows.nth(2).inner_text(), "окно: «Все» и по строке на персонажа, у них — «как у всех»")
    # Фемиде — своя модель того, что уже подключено
    rows.nth(3).click()
    pg.wait_for_timeout(200)
    ok("Как у всех" in pg.inner_text("#br-body") and "LM Studio" in pg.inner_text("#br-body"), "выбор: «как у всех» и подключённые модели")
    pg.click('#br-body .br-opt[data-id="lm"]')
    pg.wait_for_timeout(300)
    ok(pg.evaluate("SS.llm.persona.themis") == "lm" and pg.evaluate("SS.llm.persona_model.themis") == "" and "Фемида думает" in pg.inner_text("#br-st"),
       "Фемида думает LM Studio — у остальных всё как было")
    ok(pg.evaluate("SS.llm.active") == "dewiar-cloud", "общий мозг не тронут")
    # Патрику — Kimi по ключу
    pg.locator("#br-body .br-row").nth(2).click()
    pg.click("#br-body [data-add]")
    pg.wait_for_timeout(200)
    ok(pg.locator("#br-body .br-tile").count() >= 12 and "Свой адрес" in pg.inner_text("#br-body"), "плитки сервисов и «Свой адрес»")
    pg.click('#br-body .br-tile[data-p="gemini"]')
    ok("VPN" in pg.inner_text("#br-body") and "aistudio.google.com" in pg.inner_html("#br-body"), "у Gemini — где взять ключ и про VPN")
    pg.click('#br-body .br-tile[data-p="kimi"]')
    pg.fill("#br-k", "bad")
    pg.click("#br-go")
    pg.wait_for_timeout(300)
    ok("ключ" in pg.inner_text("#br-st") and pg.locator("#br-k").count() == 1, "ключ не подошёл — сказано, поле на месте")
    pg.fill("#br-k", "sk-good")
    pg.click("#br-go")
    pg.wait_for_timeout(300)
    ms = pg.evaluate("[...document.querySelectorAll('#br-body [data-m]')].map(b => b.dataset.m)")
    ok(ms[:3] == ["kimi-latest", "kimi-k2-turbo-preview", "kimi-k2-0905-preview"] and "рекомендую" in pg.inner_text("#br-body") and len(ms) == 4,
       f"весь список моделей сервиса, советуемые первыми: {ms}")
    pg.fill("#br-q", "0905")
    pg.wait_for_timeout(150)
    ok(pg.evaluate("[...document.querySelectorAll('#br-body [data-m]')].map(b => b.dataset.m)") == ["kimi-k2-0905-preview"], "поиск по моделям")
    if SHOTS:
        pg.screenshot(path=os.path.join(SHOTS, "brain-who-models.png"))
    pg.click('#br-body [data-m="kimi-k2-0905-preview"]')
    pg.wait_for_timeout(500)
    pid = pg.evaluate("SS.llm.persona.patrick")
    prof = pg.evaluate(f"SS.llm.profiles['{pid}']") if pid else {}
    ok(prof.get("model") == "kimi-k2-0905-preview" and prof.get("api_key") == "sk-good" and "moonshot" in prof.get("base_url", ""),
       f"Патрик думает Kimi K2 — профиль «сервис + ключ + модель»: {prof.get('name')}")
    ok("ответила за 1,8 с" in pg.inner_text("#br-st") and "llm_test" in [c[0] for c in pg.evaluate("calls")], "проверено живым вопросом — сказано, за сколько")
    ok(pg.evaluate("SS.llm.persona.lira || ''") == "" and pg.evaluate("SS.llm.active") == "dewiar-cloud", "Лира и общий мозг — как были")
    # та же модель снова — тот же профиль; Gemini всем; модель, что не отвечает, — не ставится
    n0 = pg.evaluate("Object.keys(SS.llm.profiles).length")
    pg.click("#br-body .br-row >> nth=0")
    pg.click("#br-body [data-add]")
    pg.click('#br-body .br-tile[data-p="gemini"]')
    pg.fill("#br-k", "g-key")
    pg.click("#br-go")
    pg.wait_for_timeout(300)
    ms = pg.evaluate("[...document.querySelectorAll('#br-body [data-m]')].map(b => b.dataset.m)")
    ok(ms[0] == "gemini-flash-latest" and ms[-1] == "text-embedding-004", f"Gemini: советуемые первыми, поиск по смыслу — в конце: {ms}")
    pg.click('#br-body [data-m="gemma-3-27b-it"]')
    pg.wait_for_timeout(400)
    ok("не ответила" in pg.inner_text("#br-st") and pg.evaluate("SS.llm.active") == "dewiar-cloud", "модель не ответила — не ставится, сказано выбрать другую")
    pg.click('#br-body [data-m="gemini-2.5-flash"]')
    pg.wait_for_timeout(400)
    act = pg.evaluate("SS.llm.active")
    ok(pg.evaluate(f"SS.llm.profiles['{act}'].model") == "gemini-2.5-flash" and "Все думают" in pg.inner_text("#br-st"), "«Все» — Gemini стал общим мозгом")
    ok("2.5-flash" in pg.inner_text("#hm-brain") or "Gemini" in pg.inner_text("#hm-brain"), f"кнопка на «Главной» — новая модель: {pg.inner_text('#hm-brain')!r}")
    n1 = pg.evaluate("Object.keys(SS.llm.profiles).length")
    pg.click("#br-body .br-row >> nth=0")
    pg.click("#br-body [data-add]")
    pg.click('#br-body .br-tile[data-p="gemini"]')
    pg.fill("#br-k", "g-key")
    pg.click("#br-go")
    pg.wait_for_timeout(300)
    pg.click('#br-body [data-m="gemini-2.5-flash"]')
    pg.wait_for_timeout(400)
    ok(pg.evaluate("Object.keys(SS.llm.profiles).length") == n1 and n1 == n0 + 1, "та же модель с тем же ключом — тот же профиль; модель, что не ответила, профиля не оставила")
    # подстраховка
    ok(pg.is_checked("#br-fb"), "подстраховка включена по умолчанию")
    pg.click("#br-fb")
    pg.wait_for_timeout(200)
    ok(pg.evaluate("SS.llm.key_fallback") is False, "выключили — сохранено")
    if SHOTS:
        pg.click("#br-x")
        pg.click("#hm-brain")
        pg.wait_for_timeout(300)
        pg.screenshot(path=os.path.join(SHOTS, "brain-who.png"))
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:2]}")

# ядро: подстраховка для сервиса по ключу
import engine_answer as EA  # noqa: E402
notes = []


class Sett:
    def __init__(self, llm): self.llm = llm
    def get(self, a, b=None):
        return self.llm.get(b) if a == "llm" else None


class E:
    note = lambda self, t: notes.append(t)  # noqa: E731
    _tools_key = lambda self, p: "k"  # noqa: E731


e = E()
dw = {"name": "Dewiar Облако", "base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "cloud": True, "model": "chat"}
e.s = Sett({"profiles": {"dewiar-cloud": dw}, "key_fallback": True, "own_fallback": False, "tools_modes": {}})
kimi = {"name": "Kimi — kimi-k2", "base_url": "https://api.moonshot.ai/v1", "model": "kimi-k2"}
fb = EA.AnswerMixin._own_fallback(e, kimi, Exception("402 Payment Required: quota exceeded"))
ok(fb and fb.get("cloud") and notes and "«Kimi» не ответил (кончились деньги на ключе)" in notes[-1], f"Kimi без денег — ответил Dewiar: {notes[-1:]}")
ok(EA.AnswerMixin._own_fallback(e, kimi, Exception("400 bad request: messages invalid")) is None, "ошибка запроса (не связь и не ключ) — не подменяем")
e.s.llm["key_fallback"] = False
ok(EA.AnswerMixin._own_fallback(e, kimi, Exception("connect error")) is None, "подстраховку выключили — не подменяем")
lm = {"name": "LM Studio", "base_url": "http://127.0.0.1:1234/v1", "model": "q"}
e.s.llm["key_fallback"] = True
ok(EA.AnswerMixin._own_fallback(e, lm, Exception("connect error")) is None, "своя модель — только с согласия (own_fallback), как раньше")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
