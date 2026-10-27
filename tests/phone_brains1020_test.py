"""Отчёт №117 (19.10, телефон 0.6.68): «на ПК настроил модель, отправил настройки на телефон — телефон не может
подключиться. Не могу на стандартную Dewiar вернуться. На ПК могу переключаться между разными моделями, на телефоне нет».
У телефона один мозг: подключили другой — прежний (Dewiar Облако с ключом) пропадал. Теперь:
— прежние мозги запоминаются (до 5), в «Мозге» — «Прежние мозги» и «Вернуть»;
— кто подключался раньше этого списка — Dewiar Облако возвращается по ключу, что остался у слуха;
— «Забыть ключ» убирает и прежние облачные;
— Groq и другие сервисы: 403 (закрыт для страны) и 413 (лимит тарифа) — по-человечески, с путём назад.
И компьютер (отчёты №121–124): своя модель думает больше минуты — один раз сказать, что делать."""
import json, os, subprocess, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ── компьютер: медленная своя модель ──
import engine_answer as EA  # noqa: E402
notes = []
me = types.SimpleNamespace(note=notes.append)
EA.AnswerMixin._slow_local(me, {"base_url": "http://127.0.0.1:11434/v1", "model": "llama3"}, 131)
EA.AnswerMixin._slow_local(me, {"base_url": "http://127.0.0.1:11434/v1", "model": "llama3"}, 150)
ok(len(notes) == 1 and "131 с" in notes[0] and "облако" in notes[0], f"своя модель отвечает через 131 с — одна подсказка: {notes}")
me2 = types.SimpleNamespace(note=notes.append)
EA.AnswerMixin._slow_local(me2, {"base_url": "https://api.example.com/v1"}, 200)
EA.AnswerMixin._slow_local(me2, {"base_url": "http://localhost:1234/v1"}, 20)
ok(len(notes) == 1, "облачный сервис или быстрый ответ — без подсказки")

# ── компьютер: голоса Vosk TTS не успевают за речью — Piper ──
import engine_remote as ER  # noqa: E402


class FakeS:
    def __init__(self):
        self.d = {"tts": {"engine": "vosk"}, "persona": "lira"}

    def get(self, *k):
        v = self.d
        for x in k:
            v = (v or {}).get(x)
        return v

    def update(self, p):
        self.d["tts"].update(p["tts"])


def vme(load):
    return types.SimpleNamespace(s=FakeS(), vosk_tts=types.SimpleNamespace(load_s=load), note=notes.append, apply_engines=lambda: None,
                                 ensure_voice=lambda p: None)


notes.clear()
m1 = vme(30)
for ch, sec in ((40, 5.5), (40, 1.0), (70, 6.6)):
    ER.RemoteMixin._vosk_slow(m1, ch, sec)
ok(m1.s.d["tts"]["engine"] == "vosk", "две медленные фразы — ещё Vosk TTS")
ER.RemoteMixin._vosk_slow(m1, 120, 17.7)
ok(m1.s.d["tts"]["engine"] == "piper" and m1.s.d["tts"].get("auto_piper") and len(notes) == 1 and "Piper" in notes[0],
   f"третья медленная — голос Piper и подсказка: {m1.s.d['tts']}")
m2 = vme(465)
ER.RemoteMixin._vosk_slow(m2, 38, 5.5)
ok(m2.s.d["tts"]["engine"] == "piper", "голоса грузились 7 минут — хватает одной медленной фразы")

# ── телефон ──
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
MODE = {"llm": 403}


def cloud(route):
    u = route.request.url
    if "balance" in u:
        return route.fulfill(status=200, body=json.dumps({"balance": 3, "percent": 60, "turns": 100}), headers={"Content-Type": "application/json"})
    if "models" in u:
        return route.fulfill(status=200, body=json.dumps({"data": [{"id": "chat", "title": "Dewiar"}], "stt": True, "tts": True}), headers={"Content-Type": "application/json"})
    route.fulfill(status=200, body="{}", headers={"Content-Type": "application/json"})


def groq(route):
    if MODE["llm"] == 403:
        return route.fulfill(status=403, body='{"error":{"message":"Forbidden"}}', headers={"Content-Type": "application/json"})
    route.fulfill(status=413, body='{"error":{"message":"Request too large for model on tokens per minute (TPM)"}}', headers={"Content-Type": "application/json"})


from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 860}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://cloud.test/**", cloud)
    pg.route("https://groq.test/**", groq)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    # был Dewiar по ключу → прислали «как на компьютере» Groq
    r = pg.evaluate("""() => { document.querySelectorAll('.sheet.on').forEach(s => s.classList.remove('on'));
        S.llm = Object.assign({}, DEF.llm, { name: "Dewiar Облако", base_url: "https://cloud.test/dwrapp/cloud.php?p=", api_key: "dw-test-key", model: "chat", cloud: true });
        S.stt = { engine: "server", url: "https://cloud.test/dwrapp/cloud.php?p=", key: "dw-test-key", model: "gigaam" }; saveS();
        S.llm = Object.assign({}, DEF.llm, { name: "OpenAI", base_url: "https://groq.test/openai/v1", api_key: "gsk", model: "openai/gpt-oss-120b" }); saveS();
        return S.llmSaved.map(brainNameOf); }""")
    ok(r == ["Dewiar Облако"], f"подключили Groq — Dewiar Облако запомнилось: {r}")
    # 403 и 413 — по-человечески
    pg.evaluate("() => { S.textMode = true; saveS(); ask('Привет'); }"); pg.wait_for_function("!busy", timeout=20000); pg.wait_for_timeout(300)
    t403 = pg.evaluate("() => document.getElementById('bot').textContent")
    ok("не пускает (403)" in t403 and "Прежние мозги" in t403, f"403 — закрыт для страны или ключа, путь назад: {t403[-260:]}")
    MODE["llm"] = 413
    pg.evaluate("() => ask('Привет ещё раз')"); pg.wait_for_function("!busy", timeout=20000); pg.wait_for_timeout(300)
    t413 = pg.evaluate("() => document.getElementById('bot').textContent")
    ok("лимит токенов в минуту" in t413, f"413 — лимит тарифа: {t413[-200:]}")
    why = pg.evaluate("() => hLoad().net_why || {}")
    ok(why.get("cloud:key") == 1 and why.get("cloud:rejected") == 1, f"причины — в пульс «Здоровья» (ключ сервиса: доступ, отклонил): {why}")
    # «Мозг» → «Прежние мозги» → «Вернуть»
    pg.evaluate("() => openSettings('brain')"); pg.wait_for_timeout(500)
    card = pg.inner_text("#br-back")
    ok("Прежние мозги" in card and "Dewiar Облако" in card and "Вернуть" in card, f"в «Мозге» — прежние мозги: {card!r}")
    pg.click("#br-back [data-back='0']"); pg.wait_for_timeout(800)
    st = pg.evaluate("() => [S.llm.cloud, S.llm.api_key, S.llm.model, brainNameOf(S.llmSaved[0] || {base_url: ''})]")
    ok(st[:3] == [True, "dw-test-key", "chat"] and "OpenAI" in st[3], f"«Вернуть» — снова Dewiar Облако, а Groq — в прежних: {st}")
    # кто подключался до списка: прежних нет, а ключ у слуха остался
    r = pg.evaluate("""() => { S.llmSaved = []; S.llm = Object.assign({}, DEF.llm, { name: "OpenAI", base_url: "https://groq.test/openai/v1", model: "x" });
        llmSeen = JSON.parse(JSON.stringify(S.llm)); saveS(); return llmBack().map(brainNameOf); }""")
    ok(r == ["Dewiar Облако"], f"старые настройки: Dewiar Облако — по ключу, что у слуха: {r}")
    # «Забыть ключ» — прежние облачные уходят, а сам забытый ключ остаётся, чтобы вернуть (YouTube 27.10: «случайно нажал»)
    r = pg.evaluate("""async () => { await llmRestore(0); S.llm.account = false; saveS(); await forgetKey(); return [S.llm.base_url, (S.llmSaved || []).filter(x => x.cloud).map(x => !!x.forgot)]; }""")
    ok(r == ["", [True]], f"«Забыть ключ» — из облачных остался только забытый ключ (его можно вернуть): {r}")
    # звук на нуле: кнопка «включить и прочитать» вместо незаметного тоста
    r = pg.evaluate("""() => { const mock = D.mock; window.VOL = 0; D.mock = false; const vol = D.volume;
        D.volume = (op, v) => op === "get" ? VOL : (VOL = v); S.textMode = false;
        say("Завтра в Минске плюс двенадцать."); say("Возьмите зонт.");
        return new Promise(res => setTimeout(() => { const b = document.getElementById("vol-up"); const had = !!b && b.textContent;
            if (b) b.click(); const after = [VOL, !!document.getElementById("vol-up"), volMuted]; D.mock = mock; D.volume = vol; res([had, after]); }, 100)); }""")
    ok(r[0] and "Звук на нуле" in r[0] and r[1] == [50, False, ""], f"звук на нуле — кнопка: прибавить и прочитать ответ: {r}")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
# ── телефон: код 11 — один распознаватель на всё время, а не новый на каждую фразу ──
sp = (ROOT / "android/src/pro/dewiar/app/Speech.java").read_text(encoding="utf-8")
body = sp[sp.index("public void listenSystem"):sp.index("public void stop()")]
ok("if (rec != null) { rec.destroy(); rec = null; }" not in body and "if (rec == null) { rec = SpeechRecognizer.createSpeechRecognizer(ctx)" in body
   and "code == 11" in body and "rec.destroy()" not in sp[sp.index("public void cancel()"):sp.index("public void cancel()") + 600],
   "код 11 (пакет 20.10, 50 телефонов): распознаватель не пересоздаётся на каждую фразу, отпускается только сломанный")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
