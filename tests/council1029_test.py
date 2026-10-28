"""«Совет ИИ» (0.67; владелец 28.10: «несколько персонажей с разными моделями — раздел, где выносим идею, а они все вместе
отвечают, спорят и помогают; как живые, красиво, захватывающе»). Проверяем на настоящем ядре и студии:
- за столом — персонажи; у кого «свой мозг» — думают своей моделью (запросы уходят разным моделям), подпись модели видна;
- три круга: «Мнения» (все сами), «Спор» (видят друг друга и отвечают по имени), «Итог» ведущего (Сошлись / Разошлись /
  Совет / Первый шаг); всё потоком — карточки пишутся на глазах, облик говорящего оживает;
- протокол — «Совет/….md», в «Прошлых советах»; «Остановить» — останавливает; меньше двух — понятная ошибка;
- модель одного участника не ответила — он помечен, совет идёт дальше."""
import json, os, re, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS", "")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


SEEN, MODE = [], {"broken": "", "slow": 0.0}


class M(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "gpt-mock"}, {"id": "claude-mock"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        model = body.get("model", "")
        sysm = next((m["content"] for m in body.get("messages", []) if m.get("role") == "system"), "")
        who = (re.search(r"Ты — ([^,]+),", sysm) or [None, "?"])[1]
        rnd = "sum" if "ведущий" in sysm else "r2" if "Ответь коллегам" in sysm else "r1" if "Совета ИИ" in sysm else "chat"
        SEEN.append((rnd, who, model))
        if MODE["broken"] and MODE["broken"] == model:
            self.send_response(500); self.send_header("Content-Length", "0"); self.end_headers(); return
        text = {"r1": f"Я {who}, и думаю так: стоит попробовать, но осторожно. Главное — посчитать деньги и время заранее.",
                "r2": f"Соглашусь с коллегами в главном, но {who} видит риск в спешке.",
                "sum": "**Сошлись**\nПробовать стоит.\n\n**Разошлись**\nВ сроках.\n\n**Совет**\nНачать с малого.\n\n**Первый шаг**\nПосчитать бюджет сегодня.",
                "chat": "Ответ."}[rnd]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for w in re.findall(r"\S+\s*", text):
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": w}}]}, ensure_ascii=False) + "\n\n").encode()); self.wfile.flush()
            time.sleep(0.02 + MODE["slow"])
        self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


# голосом: «Собери совет: …» — сразу короткий ответ (молчать минуту-две нельзя), итог Лира скажет сама, коротко
sys.path.insert(0, str(ROOT / "core"))
import council as CN  # noqa: E402
import tools as TL  # noqa: E402
ok(CN.spoken_summary("**Сошлись**\nПробовать.\n\n**Разошлись**\nВ сроках.\n\n**Совет**\nНачать с малого.\n\n**Первый шаг**\nПосчитать бюджет.")
   == "Совет закончил. Советуют начать с малого. Первый шаг — посчитать бюджет.", "итог вслух — «Совет» и «Первый шаг», без всего разбора")
calls = []
fake = type("E", (), {"council": type("C", (), {"start": lambda self, q, p, announce=False: calls.append(announce) or
                                                  {"sid": "x", "members": [{"name": "Лира"}, {"name": "Патрик"}]}})(),
                      "emit": lambda self, *a, **k: calls.append(k.get("open"))})()
t0 = time.monotonic(); r = TL.t_council({"question": "Учить Python?"}, {"engine": fake})
ok(time.monotonic() - t0 < 1 and calls == [True, True] and "Лира, Патрик" in r and "одной фразой" in r,
   f"инструмент не ждёт итога: совет собран, студия открыта, итог — потом вслух: {calls} {r[:80]!r}")

srv = ThreadingHTTPServer(("127.0.0.1", 0), M); threading.Thread(target=srv.serve_forever, daemon=True).start()
U = f"http://127.0.0.1:{srv.server_address[1]}/v1"
tmp = Path(tempfile.mkdtemp()); cfg = tmp / "cfg"; cfg.mkdir()
PORT = free()
(cfg / "settings.json").write_text(json.dumps({
    "persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "mode_seen": 1},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}, "workspace": {"path": str(tmp / "ws")},
    "llm": {"active": "g", "profiles": {"g": {"name": "ChatGPT", "kind": "openai", "base_url": U, "model": "gpt-mock"},
                                        "c": {"name": "Claude", "kind": "openai", "base_url": U, "model": "claude-mock"}},
            "persona": {"patrik": "c"}}}), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 1100})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        ok(pg.locator('nav button[data-p="council"]').count() == 1, "в меню — «Совет ИИ»")
        pg.click('nav button[data-p="council"]'); time.sleep(1.5)
        ms = pg.evaluate("() => [...document.querySelectorAll('#co-ms .co-m')].map(b => [b.dataset.id, b.classList.contains('on'), b.querySelector('small').textContent])")
        on = [m[0] for m in ms if m[1]]
        ok(on[:2] == ["lira", "patrik"] and 2 <= len(on) <= 3, f"по умолчанию за столом: ведущая Лира и Патрик со своим мозгом (и ещё один, если есть): {on}")
        N = len(on)
        pat = next(m for m in ms if m[0] == "patrik")
        ok("claude-mock" in pat[2] and "свой мозг" in pat[2] and "gpt-mock" in next(m for m in ms if m[0] == "lira")[2], f"у каждого видна модель: {pat}")
        ok("разными моделями" in pg.inner_text("#co-tip"), f"подсказка: думают разными моделями: {pg.inner_text('#co-tip')!r}")
        ok(pg.locator("#co-seats .co-seat canvas").count() == N, "на «столе» — живые облики участников")
        # меньше двух — понятно
        for x in on[1:]:
            pg.click(f'#co-ms .co-m[data-id="{x}"]')
        pg.fill("#co-q", "Стоит ли мне переходить на удалённую работу?"); pg.click("#co-go"); time.sleep(0.6)
        ok("хотя бы двое" in pg.inner_text("#toast") if pg.locator("#toast").count() else False, "один участник — «нужно хотя бы двое»")
        for x in on[1:]:
            pg.click(f'#co-ms .co-m[data-id="{x}"]')
        MODE["slow"] = 0.05
        pg.click("#co-go"); time.sleep(0.9)
        ok(pg.evaluate("document.querySelector('#co-stage').classList.contains('live')") and "удалённую работу" in pg.inner_text("#co-qline"), "совет идёт: вопрос на «столе»")
        talk = pg.evaluate("() => [...document.querySelectorAll('#co-seats .co-seat')].filter(s => s.classList.contains('talk') || s.classList.contains('think')).length")
        ok(talk >= 1, f"кто пишет — тот «говорит»: {talk}")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "council-live.png"))
        pg.wait_for_selector("#co-feed .co-end", timeout=60000)
        r1 = [x for x in SEEN if x[0] == "r1"]; r2 = [x for x in SEEN if x[0] == "r2"]; sm = [x for x in SEEN if x[0] == "sum"]
        ok(len(r1) == N and len(r2) == N and len(sm) == 1, f"три круга: мнения, спор, итог: {len(r1)}, {len(r2)}, {len(sm)}")
        ok(("r1", "Патрик", "claude-mock") in r1 and ("r1", "Лира", "gpt-mock") in r1, f"Патрик думает своей моделью, Лира — общей: {r1}")
        ok(sm and sm[0][1] == "Лира", "итог подводит ведущая — Лира")
        cards = pg.evaluate("() => [...document.querySelectorAll('#co-feed .co-msg')].map(c => [c.dataset.k, c.querySelector('.co-tx').innerText.trim()])")
        ok(len(cards) == 2 * N + 1 and all(t for _, t in cards), f"в ленте {2 * N + 1} карточек с текстом: {[k for k, _ in cards]}")
        sum_html = pg.inner_html("#co-feed .co-msg.sum .co-tx")
        ok("<b>Сошлись</b>" in sum_html and "<b>Первый шаг</b>" in sum_html, "итог — разделами: Сошлись, Разошлись, Совет, Первый шаг")
        ok([x.get_attribute("class") for x in pg.query_selector_all("#co-steps li")] == ["past"] * 3 or
           all("past" in (x.get_attribute("class") or "") for x in pg.query_selector_all("#co-steps li")), "шаги — все пройдены")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "council-done.png"), full_page=True)
        prot = list((tmp / "ws").rglob("Совет/*.md"))
        txt = prot[0].read_text(encoding="utf-8") if prot else ""
        ok(prot and "# Совет ИИ: Стоит ли мне переходить на удалённую работу?" in txt and "## Мнения" in txt and "## Спор" in txt and "## Итог" in txt
           and "Патрик (claude-mock)" in txt, f"протокол — «Совет/…md»: {prot}")
        ok("удалённую работу" in pg.inner_text("#co-hist"), "в «Прошлых советах»")
        # одна модель не отвечает — участник помечен, совет идёт дальше
        SEEN.clear(); MODE["broken"] = "claude-mock"; MODE["slow"] = 0
        pg.fill("#co-q", "Как подтянуть английский за месяц?"); pg.click("#co-go")
        pg.wait_for_selector("#co-feed .co-end", state="detached", timeout=10000)        # прежний итог ушёл — идёт новый совет
        pg.wait_for_selector("#co-feed .co-end", timeout=60000)
        seats = pg.evaluate("() => [...document.querySelectorAll('#co-seats .co-seat')].map(s => s.className)"); nsum = pg.locator("#co-feed .co-msg.sum").count()
        ok(sum("fail" in x for x in seats) == 1 and nsum == 1,
           f"модель Патрика не ответила — он помечен, итог всё равно есть: {seats} {nsum}")
        # остановить
        MODE["broken"] = ""; MODE["slow"] = 0.4
        pg.fill("#co-q", "Купить квартиру сейчас или копить?"); pg.click("#co-go"); time.sleep(1.2)
        pg.wait_for_selector("#co-feed .co-end", state="detached", timeout=10000)
        pg.click("#co-stop"); pg.wait_for_selector("#co-feed .co-end", timeout=30000)
        ok("остановлен" in pg.inner_text("#co-feed .co-end"), "«Остановить» — совет остановлен")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate(); srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
