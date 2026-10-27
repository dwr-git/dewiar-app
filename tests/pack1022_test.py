"""Пакет здоровья 22.10 — то, что сломано у людей:
- «Команда llm_test упала: 'base_url'» и «'NoneType' object has no attribute 'rstrip'»: профиль без адреса — понятный
  ответ «не указан адрес сервера», а не падение команды;
- Gemini из России: «User location is not supported» (ошибка списком [{"error":…}]) — словами, что делать;
- Z.ai без оплаченного пакета отвечает 429 «Insufficient balance or no resource package» — раньше три повтора с ожиданием
  до минуты на каждый вопрос; теперь сразу понятный ответ;
- синхронизация на Windows: «FileNotFoundError …(приоритет 1 \\план.md» — имя папки задачи обрезалось с пробелом на конце;
- «Ошибка в виджете: [object ProgressEvent]» (№181) — файл не прочитался; теперь — словами;
- «Ссылка openrouter.ai/keys не работает» (№156) — страница ключей теперь openrouter.ai/settings/keys."""
import json, os, re, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
os.environ["DEWIAR_RATE_WAIT"] = "5,5,5"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import httpx  # noqa: E402
import llm  # noqa: E402

r = llm.test_profile({})
ok(r.get("ok") is False and "адрес сервера" in r.get("error", ""), f"«Проверить» профиль без адреса — понятный ответ: {r}")
r = llm.test_profile({"base_url": None, "model": "x"})
ok(r.get("ok") is False and "адрес сервера" in r.get("error", ""), "адрес None — тоже, без «NoneType … rstrip»")
try:
    llm.list_models({"base_url": None}); bad = False
except llm.LLMError as e:
    bad = "адрес" in str(e)
ok(bad, "список моделей без адреса — LLMError, а не KeyError")


def resp(code, body):
    req = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req, content=json.dumps(body).encode()))


g = llm._humanize(resp(400, [{"error": {"code": 400, "message": "User location is not supported for the API use.", "status": "FAILED_PRECONDITION"}}]),
                  "https://generativelanguage.googleapis.com/v1beta/openai")
ok("Gemini недоступен из вашей страны" in g and "VPN" in g, f"Gemini из России — словами: {g[:70]}")
z = llm._humanize(resp(429, {"error": {"code": "1113", "message": "Insufficient balance or no resource package. Please recharge."}}), "https://api.z.ai/api/paas/v4")
ok("пополните баланс" in z and "coding/paas/v4" in z, f"Z.ai без пакета — что делать: {z[:90]}")

# 429 «нет денег» — без повторов с ожиданием
hits = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"])); hits.append(time.time())
        b = json.dumps({"error": {"code": "1113", "message": "Insufficient balance or no resource package. Please recharge."}}).encode()
        self.send_response(429); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
t0 = time.time()
try:
    list(llm.stream_chat({"base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1", "model": "glm", "kind": "openai"}, "s", [{"role": "user", "content": "привет"}]))
    err = ""
except Exception as e:  # noqa: BLE001
    err = str(e)
ok(len(hits) == 1 and time.time() - t0 < 4 and "пополните баланс" in err, f"429 «нет денег» — без повторов, сразу понятно: запросов {len(hits)}, {time.time() - t0:.1f} с, {err[:60]}")
srv.shutdown()

import tasks  # noqa: E402
name = tasks._clean("Внести правки в Obsidian по результатам аудита (приоритет 1 и 2)")
ok(not name.endswith((" ", ".")) and len(name) <= 60, f"имя папки задачи — без пробела на конце (Windows его срезает): {name!r}")
ok(tasks._clean("отчёт.") == "отчёт" and tasks._clean("   ") == "задача", "точка на конце и пустое имя")
src = (ROOT / "core/sync.py").read_text(encoding="utf-8")
ok("Задача с телефона не создалась" in src, "одна задача с телефона, которая не создалась, не роняет весь обмен")

ok(not any("openrouter.ai/keys\"" in (ROOT / f).read_text(encoding="utf-8") or "openrouter.ai/keys<" in (ROOT / f).read_text(encoding="utf-8")
           for f in ("ui/studio/connect.js", "android/assets/www/app.js")), "ссылка на ключи OpenRouter — рабочая (settings/keys)")
ok("openrouter.ai/settings/keys" in (ROOT / "ui/studio/connect.js").read_text(encoding="utf-8"), "студия: openrouter.ai/settings/keys")

# №185: Vosk TTS не успевал — сам перешёл на Piper (auto_piper); лёгкий режим выключился — Piper остаётся
import tempfile as _tf, types as _ty  # noqa: E402
os.environ["DEWIAR_CONFIG_DIR"], os.environ["DEWIAR_STATE_DIR"] = _tf.mkdtemp(), _tf.mkdtemp()
from settings import Settings  # noqa: E402
import engine_brain as EB  # noqa: E402
for auto, want in ((1792600000, "piper"), (0, "vosk")):
    s = Settings(); s.update({"tts": {"engine": "piper", "auto_piper": auto}, "stt": {"engine": "gigaam"}})
    me = _ty.SimpleNamespace(s=s, device={"sig": "x"}, stt=None, apply_engines=lambda: None, ensure_voice=lambda p: None,
                             emit=lambda *a, **k: None, device_status=lambda: {})
    EB.BrainMixin.set_light(me, False)
    ok(s.get("tts", "engine") == want, f"лёгкий режим выключен: голос {'выбран автоматикой (Vosk не успевал) — остаётся Piper' if auto else 'был Piper лёгкого режима — снова Vosk'}: {s.get('tts', 'engine')}")

# Windows: кто держит микрофон (поддельный реестр). №170: Яндекс Браузер с «Алисой» держит его часами — не созвон;
# №165: «Параметры» Windows — не созвон; Zoom — созвон
import types as _t  # noqa: E402
now_ft = lambda ago: int((time.time() - ago + 11644473600) * 1e7)
REG = {"NonPackaged": {"C:#Users#u#AppData#Local#Yandex#YandexBrowser#Application#browser.exe": (now_ft(3 * 3600), 0),
                       "C:#Users#u#AppData#Roaming#Zoom#bin#Zoom.exe": (now_ft(300), 0),
                       "C:#Program Files#Google#Chrome#Application#chrome.exe": (now_ft(600), 1)},
       "windows.immersivecontrolpanel_cw5n1h2txyewy": (now_ft(60), 0)}
wr = _t.ModuleType("winreg"); wr.HKEY_CURRENT_USER = 0
def _open(k, path=None):
    node = REG if not isinstance(k, dict) else k
    if isinstance(k, int):
        node = REG
        if path.endswith("NonPackaged"):
            node = REG["NonPackaged"]
        return node
    return {"vals": k[path]} if isinstance(k.get(path), tuple) else k[path]
wr.OpenKey = _open
wr.EnumKey = lambda k, i: list(k.keys())[i] if i < len(k) else (_ for _ in ()).throw(OSError())
wr.QueryValueEx = lambda sk, n: ((sk["vals"][0] if n == "LastUsedTimeStart" else sk["vals"][1]), 0)
wr.CloseKey = lambda k: None
sys.modules["winreg"] = wr
# запущенные программы (№261, 27.10: запись в реестре от закрытой программы — не созвон): Zoom и браузеры запущены
ps = _t.ModuleType("psutil")
ps.process_iter = lambda attrs=None: [_t.SimpleNamespace(info={"name": n}) for n in ("Zoom.exe", "browser.exe", "chrome.exe")]
sys.modules["psutil"] = ps
import meeting  # noqa: E402
users = meeting._windows()
ok(users == ["Zoom"], f"Windows: созвон — Zoom; Яндекс Браузер с «Алисой» 3 часа и «Параметры» — не созвон; Chrome закрыл микрофон: {users}")

from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?mode=card&port=1"); pg.wait_for_timeout(800)
    t = pg.evaluate("""async () => { const fr = new FileReader(); const ev = new ProgressEvent('error'); Object.defineProperty(ev, 'target', { value: fr });
        let viaB64 = ''; const RF = window.FileReader;
        window.FileReader = class { readAsDataURL() { this.error = { name: 'NotReadableError' }; setTimeout(() => this.onerror(new ProgressEvent('error')), 5); } };
        try { await b64of({ name: 'Отчёт.pdf' }); } catch (e) { viaB64 = errText(e); } window.FileReader = RF;
        return [errText(ev), errText(new ProgressEvent('error')), viaB64]; }""")
    ok(all("[object" not in x for x in t) and "не прочитался" in t[2] and "Отчёт.pdf" in t[2], f"виджет: ошибка чтения файла — словами: {t}")
    # №173 (Linux Mint): обновление «как будто зависло» — виджет сразу писал «Готово — перезапускаюсь», а установка только
    # начиналась (пароль, ход). Теперь — по шагам, и ошибка видна
    pg2 = b.new_page(); pg2.on("pageerror", lambda e: errs.append(str(e)))
    pg2.add_init_script("""window._st = ['auth', 'auth', 'install', 'install', 'error']; window._pct = 0;
      window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => {
        if (k === 'install_update') return Promise.resolve({ ok: true, started: true });
        if (k === 'update_progress') { const s = _st.length > 1 ? _st.shift() : _st[0]; return Promise.resolve({ stage: s, pct: s === 'install' ? (_pct += 30) : 0, error: s === 'error' ? 'пароль не введён' : '' }); }
        return Promise.resolve(true); } }) };""")
    pg2.goto((ROOT / "ui/hud.html").as_uri() + "?mode=card&port=1"); pg2.wait_for_timeout(700)
    pg2.evaluate("showUpd({ available: { version: '0.39.0', path: '/x/updates/d.deb' } })"); pg2.wait_for_timeout(100)
    pg2.click("#upd"); seen = []
    for _ in range(14):
        pg2.wait_for_timeout(250); s = pg2.inner_text("#upd")
        if not seen or seen[-1] != s:
            seen.append(s)
    ok(any("пароль" in s for s in seen) and any("Ставлю обновление" in s and "%" in s for s in seen) and "Не встало" in seen[-1]
       and not any("Готово" in s for s in seen), f"виджет: обновление по шагам — пароль, ход, ошибка видна: {seen}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
