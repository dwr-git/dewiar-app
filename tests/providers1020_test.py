"""20.10: «важно, чтобы обязательно поддерживались все оригинальные вендоры — Gemini, DeepSeek, Claude, Kimi, GLM, Qwen и
такого плана признанные международные поставщики», а из российских агрегаторов — только давно работающие (ProxyAPI,
VseGPT; AITunnel и Polza.ai убраны). Компьютер, студия и телефон — одним списком; модель — первая из советуемых, что
у сервиса есть сейчас (имена меняются), Gemini «models/…» — без приставки, не для разговора (голос, картинки) — не первыми."""
import json, os, re, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ["DEWIAR_STATE_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as ST  # noqa: E402
import llm as L  # noqa: E402
V = {"gemini": "https://generativelanguage.googleapis.com/v1beta/openai", "kimi": "https://api.moonshot.ai/v1", "glm": "https://api.z.ai/api/paas/v4",
     "qwen": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "mistral": "https://api.mistral.ai/v1", "xai": "https://api.x.ai/v1",
     "openai": "https://api.openai.com/v1", "deepseek": "https://api.deepseek.com/v1"}
ok(all(ST.LLM_PRESETS.get(k, {}).get("base_url") == u for k, u in V.items()) and ST.LLM_PRESETS["anthropic"]["kind"] == "anthropic",
   "компьютер: Gemini, Kimi, GLM, Qwen, Mistral, Grok, OpenAI, DeepSeek, Claude — напрямую")
ok("polza" not in ST.LLM_PRESETS and "aitunnel" not in ST.LLM_PRESETS and {"proxyapi", "vsegpt"} <= set(ST.LLM_PRESETS), "из агрегаторов — ProxyAPI и VseGPT")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8"); cj = (ROOT / "ui/studio/connect.js").read_text(encoding="utf-8")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok(all(f'<option value="{k}">' in html and re.search(rf"\n  {k}: {{ hint:", cj) for k in ["gemini", "kimi", "glm", "qwen", "mistral", "xai"]),
   "студия: в «Ключ любимого сервиса» — с подсказкой, где взять ключ")
ok(all(f'url: "{u}"' in app for k, u in V.items() if k not in ("openai", "deepseek")) and "polza" not in app and "aitunnel" not in app
   and "polza" not in cj and "aitunnel" not in cj and "polza" not in html, "телефон — тот же список; Polza и AITunnel нигде")


class R:
    status_code = 200
    def raise_for_status(self): pass
    def json(self): return {"data": [{"id": "models/gemini-2.5-flash-preview-tts"}, {"id": "models/gemini-flash-latest"}, {"id": "models/embedding-001"},
                                     {"id": "models/imagen-4.0-generate-001"}, {"id": "models/gemini-2.5-pro"}, {"id": "models/aqa"},
                                     {"id": "models/gemini-live-2.5-flash-preview"}, {"id": "models/gemini-2.5-computer-use-preview-10-2025"},
                                     {"id": "models/gemini-robotics-er-1.5-preview"}, {"id": "models/lyria-realtime-exp"}]}


L.httpx.get = lambda *a, **k: R()
ms = L.list_models({"base_url": V["gemini"], "kind": "openai", "api_key": "k"})
ok(ms == ["gemini-flash-latest", "gemini-2.5-pro", "embedding-001"], f"Gemini: без «models/», голос, картинки, «живой» звук, управление компьютером — не модели разговора: {ms}")
cj_ = (ROOT / "ui/studio/connect.js").read_text(encoding="utf-8")
ok("models = models.filter(m => !side(m))" in cj_ and "ver(b) - ver(a)" in cj_ and '"gemini-flash-latest", "gemini-pro-latest"' in cj_,
   "владелец 22.11: не для разговора — не показываем, новые версии выше старых, советуем «-latest» Google (всегда новейшие)")

from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1280, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    r = pg.evaluate("""async () => { S = Object.assign(S || {}, { llm: { active: '', profiles: {} } }); S_presets = %s;
        window.saved = []; window.save = async (p) => { saved.push(p); }; window.wizardCheck = async () => true; window.renderProfiles = () => {};
        core.call = async (c, a) => { if (c === 'llm_models') { if (a.profile.base_url.includes('z.ai')) throw new Error('сервер ответил ошибкой 404'); return ['mistral-small-latest', 'codestral-latest', 'mistral-medium-latest']; } return {}; };
        const res = [];
        for (const [prov, key] of [['mistral', 'm-key'], ['glm', 'g-key']]) { document.querySelector('#ck-prov').value = prov; document.querySelector('#ck-prov').onchange();
          document.querySelector('#ck-key').value = key; await document.querySelector('#ck-go').onclick({});
          const p = Object.values(S.llm.profiles).find(x => x.api_key === key); res.push([prov, p && p.model, p && p.base_url, document.querySelector('#ck-res').textContent]); }
        return res; }""" % json.dumps(ST.LLM_PRESETS))
    ok(r[0][1] == "mistral-medium-latest" and r[0][2] == V["mistral"], f"Mistral: первая из советуемых, что есть у сервиса: {r[0]}")
    ok(r[1][1] == "glm-4.6" and r[1][2] == V["glm"] and "Не получилось" not in r[1][3], f"GLM не отдал список моделей — проверяем советуемую, а не «не получилось»: {r[1]}")
    ok(not errs, f"студия без ошибок JavaScript: {errs[:2]}")
    # телефон: мастер «Ключ сервиса» — модель по умолчанию, а у сервиса её уже нет: берёт первую советуемую из списка
    import subprocess  # noqa: E402
    www = Path(tempfile.mkdtemp()) / "www"
    subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
    ph = b.new_page(viewport={"width": 400, "height": 820}); ph.on("pageerror", lambda e: errs.append(str(e)))
    ph.goto((www / "index.html").as_uri()); ph.wait_for_timeout(1000)
    r = ph.evaluate("""async () => { const h0 = http; let seen = [];
        http = async (m, u, o) => { seen.push(u); if (u.endsWith('/models')) return { status: 200, body: JSON.stringify({ data: [{ id: 'models/gemini-2.5-flash' }, { id: 'models/gemini-2.5-flash-preview-tts' }, { id: 'models/gemini-pro-latest' }] }) };
          throw new Error('нет сети'); };
        const ms = await svcModels(CLOUD.gemini.url, 'k'); http = h0;
        return [ms, CLOUD.gemini.rec.find(m => ms.includes(m))]; }""")
    ok(r == [["gemini-2.5-flash", "gemini-pro-latest"], "gemini-pro-latest"], f"телефон: модели сервиса без «models/» и голоса, выбрана советуемая («-latest» — у Google всегда новейшая): {r}")
    ok(not errs, f"телефон без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
