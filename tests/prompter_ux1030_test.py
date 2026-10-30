"""Суфлёр понятный (30.10, владелец: «запись идёт — ничего не пишет и не отвечает; пробел — не знаю, работает или нет;
„Подсказать“ кнопкой тоже не работает. Если я не разобрался — обычный пользователь никогда не разберётся»; и «остался
в старом стиле»). Было: каждое нажатие отменяло прежнюю подсказку и начинало новую — отменённые оставались пустыми
карточками с курсором («20 из 20»); модель молчит — карточка пустая без конца; пустой ответ по кнопке — тишина.
Стало: пока подсказка пишется, новая по кнопке не начинается (и зажатый пробел — одна); отменённые не показываются;
«Пишу подсказку… N с»; модель молчит 35 с — так и сказано; по кнопке нечего сказать — сказано почему; два огонька
«Собеседник / Вы — слышу / тишина» и «распознаю речь…»; окно — в теме виджета и студии (светлый «Небесный» и др.)."""
import os, shutil, sys, tempfile, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import llm  # noqa: E402
import prompter as PR  # noqa: E402

MODE = {"kind": "slow"}


def fake_stream(prof, system, messages, cancel=None, tools=None):
    if MODE["kind"] == "slow":                    # модель молчит, пока не отменят
        while not (cancel and cancel.wait(0.05)):
            pass
        return
    if MODE["kind"] == "dash":
        yield ("text", "—")
        return
    for w in ["Цена ", "4800 ", "за 30 мест\n", "• скидка 10%"]:
        time.sleep(0.05)
        yield ("text", w)


llm.stream_events = fake_stream
events = []
eng = types.SimpleNamespace(s=types.SimpleNamespace(active_llm=lambda: {"base_url": "x", "model": "m"}), emit=lambda *a, **k: events.append(k),
                            set_state=lambda s: None, mic_voice_t=0.0)
p = PR.Prompter(eng)
p.on, p.meeting = True, {"title": "Т", "goal": "", "mode": "auto", "them": True, "me": True, "place": "online", "started": time.time()}
PR.HINT_WAIT_S = 1.5
r1 = p.hint(why="button")
time.sleep(0.2)
ids = {p.hint(why="button")["id"] for _ in range(19)}
ok(ids == {r1["id"]} and len(p.hints) == 1, f"20 нажатий, пока пишется, — одна подсказка, а не 20: {len(p.hints)}")
time.sleep(2.0)
h = p.hints[-1]
ok(h.get("done") and "не ответила за" in (h.get("error") or ""), f"модель молчит — карточка говорит об этом: {h.get('error')}")
MODE["kind"] = "ok"
p.hint(q="Сколько стоит?", why="them"); time.sleep(0.05)
p.hint(q="А на год?", why="them"); time.sleep(1.0)
pub = p.public()["hints"]
ok(not any(x.get("dropped") for x in pub) and pub[-1]["text"].startswith("Цена 4800") and all(x.get("done") for x in pub),
   f"отменённая (пришла новая) — не висит пустой: {[(x['id'], x.get('dropped'), x.get('done')) for x in p.hints]}")
MODE["kind"] = "dash"
p.lines = []
p.hint(why="button"); time.sleep(0.4)
ok("Разговора пока не слышно" in (p.hints[-1].get("note") or ""), f"по кнопке нечего сказать — сказано почему: {p.hints[-1].get('note')}")
hr = p.hearing()
ok(hr["them"] == "quiet" and hr["me"] == "quiet" and hr["stt"] == 0, f"огоньки: тишина у обоих: {hr}")
p._them_voice_t = time.monotonic(); eng.mic_voice_t = time.monotonic()
ok(p.hearing()["them"] == "talk" and p.hearing()["me"] == "talk", "говорят — «слышу»")

# окно: тема и состояния
from playwright.sync_api import sync_playwright  # noqa: E402
tmp = Path(tempfile.mkdtemp()) / "ui"
shutil.copytree(ROOT / "ui", tmp)
(tmp / "assets/dewiar.js").write_text("""
window.CALLS = [];
window.pywebview = { api: { close_prompter() {}, open_settings() {} } };
window.api = () => window.pywebview.api;
const now = Date.now() / 1000;
window.ST = { on: true, brain: true, paused: false, status: 'слушаю: звук компьютера', meeting: { title: 'Переговоры', started: now - 40, them: true, me: true, place: 'online' },
  hints: [{ id: 1, q: '', why: 'button', text: '', done: false, ts: now - 6 }], lines: [], files: [], sheet: [],
  hear: { them: 'quiet', me: 'talk', stt: 1, err: '', lines: 0 } };
window.core = { _on: {}, on(k, f) { (this._on[k] = this._on[k] || []).push(f); }, emit(k, d) { (this._on[k] || []).forEach(f => f(d)); },
  async call(cmd, a) { window.CALLS.push([cmd, a || {}]); if (cmd === 'prompter_state') return ST; return { id: 1, busy: true }; } };
setTimeout(() => core.emit('hello', { settings: { ui: { skin: 'neusky' } } }), 50);
""", encoding="utf-8")
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as pw:
    b = pw.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 440, "height": 690}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((tmp / "prompter.html").as_uri()); pg.wait_for_timeout(700)
    ok("skin-neusky" in pg.evaluate("document.body.className") and "light" in pg.evaluate("document.body.className")
       and pg.evaluate("getComputedStyle(document.querySelector('#wrap')).backgroundColor") == "rgb(219, 229, 241)",
       "окно суфлёра — в теме студии («Небесный»), а не тёмное")
    ok("Пишу подсказку" in pg.inner_text("#head") and pg.inner_text("#ask") == "Пишу подсказку…", "подсказка пишется — так и написано, кнопка показывает это")
    ok(pg.inner_text("#hc-them") .endswith("тишина") and pg.inner_text("#hc-me").endswith("слышу") and "распознаю" in pg.inner_text("#hc-stt"),
       f"огоньки: собеседник — тишина, вы — слышу, распознаю речь: {pg.inner_text('#hearbar')!r}")
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "prompter-wait.png"))
    pg.evaluate("core.emit('prompter', { kind: 'hint', hint: { id: 1, q: '', why: 'button', text: '', done: true, ts: Date.now() / 1000, note: 'Разговора пока не слышно — подсказать нечего.' } })")
    pg.wait_for_timeout(100)
    ok("Разговора пока не слышно" in pg.inner_text("#head") and pg.inner_text("#ask") == "Подсказать", "нечего подсказать — словами, кнопка снова «Подсказать»")
    n0 = len(pg.evaluate("CALLS.filter(c => c[0] === 'prompter_hint')"))
    pg.keyboard.down(" "); pg.wait_for_timeout(50)
    for _ in range(10):
        pg.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', repeat: true, bubbles: true }))")
    pg.keyboard.up(" ")
    ok(len(pg.evaluate("CALLS.filter(c => c[0] === 'prompter_hint')")) - n0 == 1, "зажатый пробел — одна просьба, не десять")
    pg.evaluate("core.emit('prompter', { kind: 'hint', hint: { id: 2, q: 'Сколько стоит?', why: 'them', text: 'Цена 4800 за 30 мест\\n• скидка 10% при годовом', done: true, ts: Date.now() / 1000 } })")
    pg.evaluate("core.emit('prompter', { kind: 'hear', hear: { them: 'talk', me: 'quiet', stt: 0, err: '', lines: 3 } })"); pg.wait_for_timeout(150)
    ok("4800" in pg.inner_text("#head") and pg.inner_text("#hc-them").endswith("слышу"), "подсказка показана; собеседник — «слышу»")
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "prompter-hint.png"))
    pg.evaluate("core.emit('prompter', { kind: 'hear', hear: { them: 'quiet', me: 'quiet', stt: 0, err: 'нет связи с сервером', lines: 3 } })"); pg.wait_for_timeout(100)
    ok("Распознавание речи не отвечает" in pg.inner_text("#hear"), "распознавание не отвечает — видно сразу")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
