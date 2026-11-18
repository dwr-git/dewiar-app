"""№882, №885 (18.11), «Мозг» → «Ключ любимого сервиса»:
— №882: у посредника первая по алфавиту — часто самая дорогая (claude-opus…), и сразу шла проверка — настоящий запрос к ней.
  Советуемой модели в списке нет — ничего не запускаем: «Ключ принят: моделей — N, из них бесплатных — M», бесплатные первыми
  («— бесплатная»), проверка — только выбранной («Выбрать эту»).
— №885: посредник по адресу (AgentRouter) не отдаёт список моделей по ключу (401) — не тупик «ключ отклонён»: поле «Имя модели»,
  проверка разговором.
— у сервиса с советуемыми моделями (OpenRouter) — как раньше: советуемая подключается и проверяется сразу."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


STUB = r"""(models) => { window._calls = []; window.ask = () => Promise.resolve(true);
  window.SS = { llm: { profiles: {}, active: "" }, ui: { welcome: "done", intro: "done" }, tts: {}, stt: {} };
  const merge = (a, b) => { for (const k in b) { if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k] && typeof a[k] === "object") merge(a[k], b[k]); else a[k] = b[k]; } return a; };
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
  core.call = async (c, a) => { _calls.push([c, JSON.parse(JSON.stringify(a || {}))]);
    if (c === 'llm_models') { const k = a.profile.api_key; if (k === 'sk-agent') throw new Error('сервер отклонил ключ доступа (проверьте API-ключ)');
      return models[k] || []; }
    if (c === 'llm_test') return { ok: true, model: a.profile.model, total_ms: 900, reply: 'Привет!' };
    if (c === 'settings_save') { merge(SS, a.patch || {}); return JSON.parse(JSON.stringify(SS)); }
    if (c === 'settings') return SS;
    return {}; };
  core.emit("hello", { settings: JSON.parse(JSON.stringify(SS)), personas: [], persona: "lira", piper_voices: [], voice_fx: [],
    presets: { openrouter: { name: "OpenRouter", kind: "openai", base_url: "https://openrouter.ai/api/v1" } } }); }"""
MODELS = {"sk-list": ["anthropic/claude-opus-4.5", "openai/gpt-5", "qwen/qwen3-coder:free", "z-ai/glm-4.5-air:free", "text-embedding-3"],
          "sk-or": ["anthropic/claude-opus-4.5", "google/gemini-2.5-flash", "openai/gpt-4.1-mini"]}
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate(STUB, MODELS); pg.wait_for_timeout(300)
    pg.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.classList.remove('on'); }")
    pg.evaluate("() => { document.querySelectorAll('dialog[open]').forEach(d => d.close()); document.querySelector('nav button[data-p=\"brain\"]').click(); }"); pg.wait_for_timeout(400)
    pg.evaluate("() => document.querySelector('#wz [data-w=\"cloud\"]').click()"); pg.wait_for_timeout(300)

    def connect(prov, key, url=""):
        pg.select_option("#ck-prov", prov); pg.wait_for_timeout(100)
        if url:
            pg.fill("#ck-url", url)
        pg.fill("#ck-key", key)
        pg.evaluate("() => { _calls = []; document.querySelectorAll('dialog[open]').forEach(d => d.close()); document.querySelector('#ck-go').click(); }")
        pg.wait_for_timeout(600)

    # №882: посредник по адресу, список без советуемых
    connect("custom", "sk-list", "https://router.example/v1")
    opts = pg.evaluate("() => [...document.querySelectorAll('#ck-model option')].map(o => o.textContent)")
    calls = [c for c, a in pg.evaluate("() => _calls")]
    ok("llm_test" not in calls and "Ключ принят: моделей — 5, из них бесплатных — 2" in pg.inner_text("#ck-res"),
       f"№882 ключ принят — ни одного настоящего запроса к модели, пока не выбрали: {calls} | {pg.inner_text('#ck-res')}")
    ok(opts[:2] == ["qwen/qwen3-coder:free — бесплатная", "z-ai/glm-4.5-air:free — бесплатная"] and opts[-1] == "text-embedding-3",
       f"бесплатные — первыми и подписаны, не для разговора — в конце: {opts}")
    pg.select_option("#ck-model", "qwen/qwen3-coder:free"); pg.click("#ck-use"); pg.wait_for_timeout(500)
    tested = [a["profile"]["model"] for c, a in pg.evaluate("() => _calls") if c == "llm_test"]
    ok(tested == ["qwen/qwen3-coder:free"] and "Готово" in pg.inner_text("#w-done") and pg.evaluate("() => S.llm.profiles[S.llm.active].model") == "qwen/qwen3-coder:free",
       f"«Выбрать эту» — проверена только выбранная: {tested}")

    # №885: список по ключу не отдают (401) — имя модели вручную
    connect("custom", "sk-agent", "https://agentrouter.example/v1")
    ok(pg.is_visible("#ck-model-own") and not pg.is_visible("#ck-model") and "Впишите имя модели из консоли сервиса" in pg.inner_text("#ck-res"),
       f"№885 список не отдали (401) — поле «Имя модели», понятно, что делать: {pg.inner_text('#ck-res')[:120]}")
    pg.click("#ck-use"); pg.wait_for_timeout(200)
    ok("Впишите имя модели" in pg.inner_text("#ck-res"), "пусто — «Впишите имя модели»")
    pg.fill("#ck-model-own", "gpt-5-mini"); pg.click("#ck-use"); pg.wait_for_timeout(500)
    prof = pg.evaluate("() => S.llm.profiles[S.llm.active]")
    ok(prof.get("model") == "gpt-5-mini" and prof.get("api_key") == "sk-agent" and prof.get("base_url") == "https://agentrouter.example/v1"
       and "Готово" in pg.inner_text("#w-done"), f"вписали «gpt-5-mini» — подключено и проверено разговором: {prof.get('model')}, {prof.get('base_url')}")

    # сервис с советуемыми моделями — как раньше
    connect("openrouter", "sk-or")
    tested = [a["profile"]["model"] for c, a in pg.evaluate("() => _calls") if c == "llm_test"]
    ok(tested == ["google/gemini-2.5-flash"] and pg.is_visible("#ck-model"), f"OpenRouter: советуемая подключена и проверена сразу: {tested}")
    ok(not errs, f"без ошибок на странице: {errs}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
