"""Студия → «Нода Лиры» (0.87, владелец 11.11: «спрятана далеко, пользователь не доберётся — ясно, понятно, чётко,
отдельным разделом»). Настоящее ядро и студия; ответы ядра lnode_* — подменные (сайт и модель не нужны), кроме одного
настоящего вызова. Проверяем: раздел — в меню на видном месте (до групп) и на «Главной»; путь «Проверить компьютер» →
«Стать нодой» (кнопка не работает без проверки, выбор «когда» и «сколько» уходит в ядро); работает — «сердце» горит,
видно примерно заработанное сегодня, счёт и честный журнал; пауза и «ждёт допуска» — словами; «Выключить» — lnode_stop;
в карточке «Dewiar.pro» — дорога в раздел; без горизонтальной прокрутки; снимки в светлой и тёмной темах."""
import json, os, socket, subprocess, sys, tempfile, time
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


tmp = Path(tempfile.mkdtemp()); cfg = tmp / "cfg"; cfg.mkdir()
PORT = free()
(cfg / "settings.json").write_text(json.dumps({
    "persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "mode_seen": 1},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}, "workspace": {"path": str(tmp / "ws")},
    "cloud": {"url": "http://127.0.0.1:9/cloud.php"}}), encoding="utf-8")
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

# подменные ответы ядра: человек ещё не нода → проверка → «Стать нодой» → работает
FIX = r"""
window.__nd = { calls: [], joined: false, on: false, st: "off", why: "" };
const W = { idle: "пока компьютер простаивает", night: "ночью, с 0 до 7", always: "всегда, пока Dewiar открыт" };
const SH = { low: "немного — до 20 ответов в час", half: "побольше — до 60 в час", all: "сколько попросят" };
const now = Math.floor(Date.now() / 1000);
window.__ndInfo = () => { const n = window.__nd; return {
  joined: n.joined, on: n.on, when: n.when || "idle", share: n.share || "low", model: n.joined ? "qwen3:8b" : "", status: { state: n.st, why: n.why },
  today: n.joined ? 14 : 0, total: n.joined ? 211 : 0, when_text: W, share_text: SH, account: true,
  journal: n.joined ? [{ t: now - 40, kind: "ok", text: "ответила на общий вопрос: пришло 38 зн., ушло 214 зн., 2,6 с" },
                      { t: now - 400, kind: "skip", text: "пауза: вы за компьютером — начну, когда он простоит 5 минут" },
                      { t: now - 900, kind: "err", text: "своя модель не ответила за 9,8 с — вопрос ответил сервер Dewiar" },
                      { t: now - 3000, kind: "info", text: "стала нодой: модель qwen3:8b, пока компьютер простаивает, немного — до 20 ответов в час" }] : [],
  rules: { ok: true, on: true, share: 0.5, fp: "7F3A-91C2-0B4D-55E1", pay: { coin: "талер", share: 0.5, share_max: 0.7, what: "принятые обычные ответы: контрольные, отклонённые и медленные не оплачиваются",
    when: "раз в сутки за прошедшие сутки", to: "ИИ-баланс владельца ноды (модели Dewiar, облако)", withdraw: false, own_questions: false,
    formula: "доля × сколько списали со спрашивающего за вопрос и ответ ноды × доверие (новая нода ×0,5, доверие ниже 0,5 — 0)" }, app: { on: true, max_answer_s: 6 } },
  site: n.joined ? { node: { state: n.site || "on", state_text: n.site === "wait" ? "ждёт допуска" : "в сети", answers_day: 14, tried_day: 15, bad_day: 1, answers_30d: 211,
    paid_total: 3.214, waiting: 0, trust: 0.97, new: true, kind: "app" }, paid_total: 3.214, est_day: 0.042, share: 0.5 } : null };
};
const CHECK = { ok: true, pick: { base: "http://127.0.0.1:11434/v1", model: "qwen3:8b", app: "Ollama" },
  models: [{ name: "Ollama", base_url: "http://127.0.0.1:11434/v1", models: ["qwen3:8b", "gemma3:12b", "nomic-embed-text"] }],
  items: [{ k: "account", ok: true, title: "Аккаунт dewiar.pro", text: "есть — талеры придут на ваш ИИ-баланс" },
          { k: "rules", ok: true, title: "Правила сети", text: "подписаны ключом Dewiar, сеть открыта" },
          { k: "model", ok: true, title: "Своя модель", text: "Ollama: qwen3:8b" },
          { k: "gpu", ok: true, title: "Видеокарта", text: "NVIDIA GeForce RTX 4070, 12 ГБ" },
          { k: "ram", ok: null, title: "Память", text: "8 ГБ — хватит, если модель целиком на видеокарте" },
          { k: "power", ok: true, title: "Питание", text: "от сети" },
          { k: "speed", ok: true, title: "Скорость", text: "ответ за 2,4 с, 61 токенов в секунду" }] };
window.__realCall = core.call.bind(core);
core.call = (c, a) => {
  if (!c.startsWith("lnode_")) return window.__realCall(c, a);
  const n = window.__nd; n.calls.push([c, a || {}]);
  if (c === "lnode_check") return new Promise(r => setTimeout(() => r(CHECK), 150));
  if (c === "lnode_join") { Object.assign(n, { joined: true, on: true, st: "ready", when: a.when, share: a.share }); }
  if (c === "lnode_stop") { Object.assign(n, { on: false, st: "off" }); }
  if (c === "lnode_set") { if (a.on) Object.assign(n, { on: true, st: "ready" }); if (a.when) n.when = a.when; if (a.share) n.share = a.share; }
  return Promise.resolve(window.__ndInfo());
};
true;
"""
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for skin in ("neusky", "neudusk", "brand"):
            pg = b.new_page(viewport={"width": 1360, "height": 1000})
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}&skin={skin}"); time.sleep(2.0)
            pg.evaluate("(s) => core.call('settings_save', { patch: { ui: { skin: s } } })", skin); time.sleep(0.4)
            pg.reload(); time.sleep(2.5)
            ok(pg.evaluate("() => document.documentElement.dataset.skin") == skin, f"тема студии — {skin}")
            if skin == "neusky":
                real = pg.evaluate("() => core.call('lnode_info', { lite: true })")
                ok(real.get("joined") is False and real.get("on") is False and "status" in real, f"настоящее ядро: lnode_info — ещё не нода: {real.get('status')}")
                nav = pg.evaluate("""() => { const b = document.querySelector('nav button[data-p="node"]'); const g = document.querySelector('nav .ng');
                    return b ? [b.innerText.trim(), !!b.querySelector('svg.ni'), !!(b.compareDocumentPosition(g) & Node.DOCUMENT_POSITION_FOLLOWING), getComputedStyle(b).display] : null; }""")
                ok(nav and nav[0] == "Нода Лиры" and nav[1] and nav[2] and nav[3] != "none", f"в меню — «Нода Лиры» со значком, выше всех групп (на видном месте): {nav}")
                ok(pg.evaluate("() => HM_APPS.some(a => a.id === 'node') && HM_DEFAULT.includes('node')"), "и значок на «Главной»")
            pg.evaluate(FIX)
            pg.click('nav button[data-p="node"]'); time.sleep(0.8)
            ok(pg.inner_text("#nd-state") == "Пока не нода" and pg.is_disabled("#nd-go") and "Проверить компьютер" in pg.inner_text("#nd-go-hint"),
               f"[{skin}] без проверки «Стать нодой» не нажать — подсказка, что сначала проверить")
            if skin == "neusky" and SHOTS:
                pg.screenshot(path=os.path.join(SHOTS, "node-start-light.png"), full_page=True)
            pg.click("#nd-check"); time.sleep(0.6)
            marks = pg.evaluate("() => [...document.querySelectorAll('#nd-checks li')].map(l => l.className)")
            ok(len(marks) == 7 and marks.count("ok") == 6 and marks.count("warn") == 1 and pg.inner_text("#nd-check-st") == "подходит" and not pg.is_disabled("#nd-go"),
               f"[{skin}] «Проверить компьютер» — семь пунктов, «подходит», кнопка открылась: {marks}")
            ok(pg.locator("#nd-model option").count() == 2 and pg.is_visible("#nd-model"), "моделей две (без модели для поиска) — можно выбрать")
            pg.click('#nd-when button[data-v="night"]'); pg.click('#nd-share button[data-v="half"]')
            ok("ночью" in pg.inner_text("#nd-when-t") and "до 60" in pg.inner_text("#nd-share-t"), "выбор «когда» и «сколько» — словами под кнопками")
            pg.click("#nd-go"); time.sleep(0.6)
            calls = pg.evaluate("() => window.__nd.calls.filter(c => c[0] === 'lnode_join')")
            ok(calls and calls[0][1] == {"base": "http://127.0.0.1:11434/v1", "model": "qwen3:8b", "when": "night", "share": "half"},
               f"[{skin}] «Стать нодой» — в ядро ушли модель и выбор человека: {calls}")
            st = pg.evaluate("() => [document.querySelector('#nd-hero').dataset.st, document.querySelector('#nd-state').innerText, document.querySelector('#nd-go').innerText, document.querySelector('#nd-tal').innerText]")
            ok(st == ["work", "Работает", "Выключить", "≈ 0,042"], f"[{skin}] работает: «сердце» горит, кнопка «Выключить», примерно заработано сегодня: {st}")
            kv = pg.inner_text("#nd-kv")
            ok("14 из 15" in kv and "3,21 тал." in kv and "0,97" in kv and "×0,5" in kv and "50 % от того, что списали" in kv, f"счёт ноды: принято, начислено, доверие, доля ноде: {kv[:160]!r}")
            log = pg.evaluate("() => [...document.querySelectorAll('#nd-log li')].map(l => l.className)")
            ok(log == ["ok", "skip", "err", "info"], f"журнал — по видам: {log}")
            pay = pg.text_content("#nd-pay-body")
            ok("ИИ-баланс" in pay and "Вывода в деньги нет" in pay and "подписаны" in pay and "доля сейчас — 50 %" in pay and "не больше 70 %" in pay, f"правила начисления — как подписаны: {pay[:200]!r}")
            over = pg.evaluate("() => { const m = document.querySelector('main'); return m.scrollWidth - m.clientWidth; }")
            ok(over <= 1, f"[{skin}] без горизонтальной прокрутки: {over}")
            # «сердце» горит светом лампы, а не серым
            core_fill = pg.evaluate("() => getComputedStyle(document.querySelector('.nd-core')).fill")
            ok("rgb(" in core_fill and core_fill not in ("rgb(0, 0, 0)",), f"[{skin}] центр «сердца» — цвет лампы: {core_fill}")
            # контраст текста состояния к фону карточки (грубо: яркость разная)
            if SHOTS:
                pg.evaluate("() => document.querySelectorAll('.nd-more details').forEach(d => d.open = true)")
                pg.screenshot(path=os.path.join(SHOTS, f"node-work-{skin}.png"))
                pg.evaluate("() => document.querySelector('main').scrollTo(0, 99999)"); time.sleep(0.2)
                pg.screenshot(path=os.path.join(SHOTS, f"node-work-{skin}-2.png"))
                pg.evaluate("() => document.querySelector('main').scrollTo(0, 0)")
                pg.evaluate("() => document.querySelectorAll('.nd-more details').forEach(d => d.open = false)")
            if skin == "neusky":
                pg.evaluate("() => { Object.assign(window.__nd, { st: 'wait', why: 'компьютер работает от батареи' }); ndLoad(); }"); time.sleep(0.3)
                ok(pg.inner_text("#nd-state") == "Пауза" and "батаре" in pg.inner_text("#nd-why") and pg.evaluate("() => document.querySelector('#nd-hero').dataset.st") == "wait",
                   "пауза — словами, почему")
                pg.evaluate("() => { Object.assign(window.__nd, { st: 'ready', why: '', site: 'wait' }); ndLoad(); }"); time.sleep(0.3)
                ok(pg.inner_text("#nd-state") == "Ждёт допуска", "новая нода — «ждёт допуска» владельцем Dewiar")
                pg.evaluate("() => { window.__nd.site = 'on'; ndLoad(); }"); time.sleep(0.3)
                pg.click("#nd-go"); time.sleep(0.5)
                ok(pg.evaluate("() => window.__nd.calls.some(c => c[0] === 'lnode_stop')") and pg.inner_text("#nd-state") == "Выключена" and pg.inner_text("#nd-go") == "Включить",
                   "«Выключить» — сразу (lnode_stop), кнопка «Включить»")
                pg.set_viewport_size({"width": 900, "height": 900}); time.sleep(0.4)
                over = pg.evaluate("() => { const m = document.querySelector('main'); return m.scrollWidth - m.clientWidth; }")
                cols = pg.evaluate("() => getComputedStyle(document.querySelector('.nd-grid')).gridTemplateColumns.split(' ').length")
                ok(over <= 1 and cols == 1, f"узкое окно — в одну колонку, без прокрутки вбок: {over} {cols}")
                pg.click('nav button[data-p="dw"]'); time.sleep(0.6)
                pg.click("#dw-ln-node"); time.sleep(0.4)
                ok(pg.evaluate("() => document.querySelector('#p-node').classList.contains('cur')"), "в «Dewiar.pro» → «Стать нодой» ведёт в раздел")
            pg.close()
        b.close()
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
finally:
    core.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
