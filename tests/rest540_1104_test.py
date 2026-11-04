"""№540 (04.11, ПК 0.82.1): «Хорошо, что Лира всегда под рукой. Но иногда хочется поработать без неё — предусмотрите полное
отключение на время». Было: «выключить микрофон» (имя не слушает, но напоминания, итоги задач и «Близкие» говорили вслух) и
«Спрячься» (в трее, но слушает). Стало «Отдых» (core/engine_rest.py): кнопка в углу виджета, пункт в трее и фраза
«Лира, отдохни час» — не слушает и не говорит сама, напоминания и фразы копятся; конец — по времени, кнопкой «Вернуть»,
нажатием на лицо или написанным вопросом: «Я снова с вами» и накопленное, напоминание — окном, одним звонком.
Перезапуск программы отдых не прерывает."""
import json, os, re, sys, tempfile, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_WORKSPACE=str(tmp / "ws"))
(tmp / "st").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_rest as R  # noqa: E402

# ---------- фраза ----------
for t, want in [("Лира, отдохни час.", 60), ("Отдохни", 60), ("не мешай полчаса", 30), ("Дай мне поработать", 60),
                ("помолчи 20 минут", 20), ("сделай перерыв на два часа", 120), ("не беспокой меня минут 40", 40),
                ("Лира, отдохни полтора часа", 90), ("Джарвис, не слушай меня час", 60), ("отключись на час", 60),
                ("оставь меня в покое", 60)]:
    ok(R.rest_phrase(t) == want, f"«{t}» → отдых {want} мин ({R.rest_phrase(t)})")
for t in ["помолчи", "отключись", "стоп", "Лира, отдохни от новостей", "не мешай мне спать", "расскажи, как отдохнуть на море",
          "напомни через час отдохнуть"]:
    ok(R.rest_phrase(t) is None, f"«{t}» — не отдых (помолчи/отключись без времени — как раньше)")
ok(R.rest_phrase("отдохни 30 часов") == R.REST_MAX, "больше 12 часов — 12 часов")

# ---------- ядро: без настоящего Engine — сама примесь и настоящие ловушки announce/_on_reminder ----------
from engine_remote import RemoteMixin  # noqa: E402
from engine_tools import ToolsMixin  # noqa: E402


class E(R.RestMixin):
    def __init__(self):
        self.muted, self.state, self.stopping = False, "idle", threading.Event()
        self.ev, self.said, self.quick, self.rang, self.follow_up_until = [], [], [], [], 5.0
        self.s = types.SimpleNamespace(get=lambda *a, **k: None)

    def emit(self, t, **kw):
        self.ev.append((t, kw))

    def set_mute(self, on):
        self.muted = bool(on)
        return self.muted

    def interrupt(self, *a, **k):
        self.state = "idle"

    def _g(self, t):
        return t

    def announce(self, text):                    # настоящая ловушка: RemoteMixin.announce, дальше — запись «сказала»
        if self._rest_hold("say", text=text):
            return
        self.said.append(text)

    def _on_reminder(self, item):
        if self._rest_hold("reminder", item=dict(item)):
            return
        self.rang.append(item)

    def _say_quick(self, msg, said, via=None, **k):
        self.quick.append(msg)


e = E()
r = e.rest_start(60)
ok(r["on"] and e.muted and e.resting() and abs(r["until"] - time.time() - 3600) < 5, f"кнопка «Отдых»: на час, микрофон выключен ({r['until_text']})")
ok(e.follow_up_until == 0.0, "и «ваша очередь» без имени — сброшена")
ok(any(t == "rest" and kw.get("on") for t, kw in e.ev), "виджету — событие rest")
ok(json.loads((tmp / "st" / "rest.json").read_text(encoding="utf-8"))["until"] == e._rest_until, "состояние — в rest.json (перезапуск не прерывает)")

# настоящие ловушки в ядре: announce и _on_reminder при отдыхе придерживают и выходят
fake = types.SimpleNamespace(_g=lambda t: t, _rest_hold=e._rest_hold)
RemoteMixin.announce(fake, "Задача «Отчёт» готова.")
ToolsMixin._on_reminder(fake, {"id": "r1", "text": "Позвонить маме", "kind": "reminder"})
ToolsMixin._on_reminder(fake, {"id": "r2", "text": "Выпить таблетку", "kind": "reminder"})
held = e._rest_held
ok([h["kind"] for h in held] == ["say", "reminder", "reminder"], f"announce и напоминания придержаны, ничего не сказано: {[h['kind'] for h in held]}")
ok(e.rest_public()["held"] == 3, "виджет видит, сколько ждёт: 3")

# перезапуск: новый объект читает rest.json — отдых продолжается
e2 = E()
e2.rest_boot()
ok(e2.resting() and e2.muted and len(e2._rest_held) == 3, "после перезапуска программы — всё ещё отдыхает, накопленное на месте")
e2._rest_gen += 1                                 # таймер второго не нужен

# конец: «Я снова с вами» + сводка; последнее напоминание — окном (опоздавшее, один звонок)
e.muted = True
out = e.rest_end("кнопка")
time.sleep(1.3)
ok(not out["on"] and not e.muted and not e.resting(), "«Вернуть» — микрофон снова включён, как был до отдыха")
ok(e.said and e.said[0].startswith("Я снова с вами.") and "Позвонить маме" in e.said[0] and "Выпить таблетку" in e.said[0]
   and "Задача «Отчёт» готова." in e.said[0], f"одной фразой — что накопилось: {e.said[:1]}")
ok(len(e.rang) == 1 and e.rang[0]["id"] == "r2" and e.rang[0].get("late"), "последнее напоминание — окном, как опоздавшее (одним звонком)")
ok(not (tmp / "st" / "rest.json").exists(), "rest.json убран")
ok(R.RestMixin.rest_end(e)["on"] is False and len(e.said) == 1, "второй «Вернуть» — ничего не повторяет")

# микрофон был выключен до отдыха — после отдыха тоже выключен
e3 = E(); e3.muted = True
e3.rest_start(30); e3.rest_end("время")
ok(e3.muted, "микрофон был выключен ещё до отдыха — таким и остаётся")

# голосом
e4 = E()
ok(e4._rest_voice("Лира, отдохни полчаса") and e4.resting() and "полчаса" in e4.quick[0] and "до " in e4.quick[0],
   f"«Лира, отдохни полчаса» — сказала и отдыхает: {e4.quick[:1]}")
ok(not E()._rest_voice("Лира, какая погода?"), "обычный вопрос — не отдых")
e4._rest_gen += 1

# время вышло — сама
e5 = E(); e5.rest_start(60); e5._rest_until = time.time() + 0.3; e5._rest_timer()
time.sleep(1.2)
ok(not e5.resting() and any("Я снова с вами" in s for s in e5.said), "время вышло — вернулась сама и сказала об этом")
e5.stopping.set(); e.stopping.set(); e2.stopping.set(); e4.stopping.set()

# ---------- ядро: кнопки и фразы проведены в настоящих местах ----------
src = {n: (ROOT / "core" / n).read_text(encoding="utf-8") for n in ("engine.py", "engine_commands.py", "engine_answer.py", "engine_remote.py", "engine_tools.py")}
ok("RestMixin" in src["engine.py"] and "self.rest_boot()" in src["engine.py"], "Engine собран с RestMixin, отдых восстанавливается при запуске")
ok('"rest": self.rest_public()' in src["engine_commands.py"], "в hello — состояние отдыха (виджет открылся посреди отдыха)")
ok('cmd in ("rest", "rest_end", "rest_toggle", "rest_state")' in src["engine_commands.py"], "команды rest / rest_end / rest_toggle")
ptt = src["engine_commands.py"][src["engine_commands.py"].index('if cmd == "ptt":'):]
ok('self.rest_end("лицо")' in ptt[:2500], "нажали на лицо во время отдыха — вернулась и слушает")
mute = src["engine_commands.py"][src["engine_commands.py"].index('if cmd == "mute":'):][:400]
ok("resting" in mute and 'self.rest_end("кнопка")' in mute, "включили микрофон кнопкой — отдых закончен")
ask = src["engine_answer.py"]
ok("self._rest_voice(text)" in ask and 'self.rest_end("вопрос")' in ask, "фраза «отдохни» — без модели; написали вопрос — вернулась")
ok('self._rest_hold("say", text=text)' in src["engine_remote.py"] and 'self._rest_hold("reminder", item=dict(item))' in src["engine_tools.py"],
   "announce и напоминания придерживаются во время отдыха")

# ---------- трей ----------
ws = (ROOT / "ui/winshell.py").read_text(encoding="utf-8")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("rest=None" in ws and "if callable(text):" in ws, "Windows: пункт трея «Отдых» с меняющейся подписью")
ok("rest=(api.rest_label," in app and "def rest_toggle(self):" in app and "def rest_note(self, on" in app,
   "трей зовёт тот же переключатель, что виджет; подпись — «Вернуть из отдыха (до …)»")
ok("(api.rest_label(), api.rest_toggle)" in app and "def rest_label(self, text):" in app, "Linux: пункт «Отдых» в меню значка")

# ---------- виджет ----------
from playwright.sync_api import sync_playwright  # noqa: E402
CORE = r"""(() => { window.calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async (c, a) => { calls.push([c, a]);
    if (c === "rest_toggle") return { on: true, until: 1, until_text: "15:40", held: 0 };
    if (c === "rest_end") return { on: false, until: 0, until_text: "", held: 0 };
    return {}; };
  setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neon" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira",
    personas: [{ id: "lira", name: "Лира" }], reminders: [], state: "idle", rest: { on: false } }); }, 150); }; ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 300, "height": 520}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1200)
    ok(pg.is_hidden("#b-rst") and pg.locator("#b-rest").count() == 1, "в углу — кнопка «Отдых», метки «отдыхаю» нет")
    pg.hover("#card"); pg.wait_for_timeout(250); pg.click("#b-rest"); pg.wait_for_timeout(250)
    ok(["rest_toggle", {"minutes": 60}] in pg.evaluate("calls"), "кнопка — rest_toggle на 60 минут")
    ok(pg.is_visible("#b-rst") and "отдыхаю до 15:40" in pg.inner_text("#b-rst"), f"метка видна всегда: {pg.inner_text('#b-rst')!r}")
    pg.evaluate("() => core.emit('state', { state: 'muted' })"); pg.wait_for_timeout(100)
    ok(pg.inner_text("#say").startswith("Отдыхаю до 15:40"), f"под лицом — «Отдыхаю до 15:40», а не «Микрофон выключен»: {pg.inner_text('#say')!r}")
    pg.evaluate("() => core.emit('rest', { on: true, until: 1, until_text: '15:40', held: 2 })"); pg.wait_for_timeout(100)
    ok("ждут: 2" in pg.inner_text("#b-rst"), "накопилось — видно на метке")
    pg.click("#b-rst"); pg.wait_for_timeout(250)
    ok(["rest_end", {}] in pg.evaluate("calls") and pg.is_hidden("#b-rst"), "нажали метку — rest_end, метка пропала")
    pg.evaluate("() => core.emit('state', { state: 'idle' })"); pg.wait_for_timeout(100)
    ok("Отдыхаю" not in pg.inner_text("#say"), "под лицом — снова имя")
    ok(pg.evaluate("typeof window.restToggle") == "function", "restToggle — для пункта в трее")
    for theme in ("light",):
        pg.evaluate("() => { document.body.classList.add('light'); core.emit('rest', { on: true, until: 1, until_text: '15:40', held: 0 }); }")
        pg.wait_for_timeout(100)
        c = pg.evaluate("() => getComputedStyle(document.getElementById('b-rst')).color")
        ok(c != "rgb(169, 216, 255)", f"светлая тема — тёмный текст метки ({c})")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
# ---------- настоящее ядро: «Лира, отдохни час» в чат, состояние в hello, нажатие на лицо — вернулась ----------
import asyncio, socket, subprocess  # noqa: E402
import websockets  # noqa: E402
s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); PORT = s_.getsockname()[1]; s_.close()
ct = Path(tempfile.mkdtemp()); (ct / "cfg").mkdir()
(ct / "cfg/settings.json").write_text(json.dumps({"persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False},
                                                   "ui": {"intro": "done"}, "report": {"pulse": False}, "team": {"route": False}}), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(ct / "cfg"), DEWIAR_STATE_DIR=str(ct / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(ct / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
env.pop("DEWIAR_WORKSPACE", None)
EV, R = [], {}


async def session():
    core = subprocess.Popen([sys.executable, str(ROOT / "core/main.py"), "--wav", str(ROOT / "tests/silence90.wav"), "--null-audio"], env=env,
                            stdout=open(ct / "core.log", "w"), stderr=subprocess.STDOUT)
    try:
        ws_ = None
        for _ in range(300):
            await asyncio.sleep(0.2)
            if (ct / "cfg/token").exists():
                try:
                    ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
                except OSError:
                    continue
        tok = (ct / "cfg/token").read_text().strip()
        await ws_.send(json.dumps({"cmd": "hello", "token": tok}))
        cnt, replies = [0], {}

        async def reader():
            async for raw in ws_:
                e_ = json.loads(raw)
                if e_["type"] == "reply":
                    replies[e_["id"]] = e_
                elif e_["type"] == "hello":
                    R["hello"] = e_["data"]
                elif e_["type"] != "level":
                    EV.append(e_)
        asyncio.ensure_future(reader())

        async def call(cmd, **args):
            cnt[0] += 1; i = cnt[0]
            await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
            for _ in range(600):
                if i in replies:
                    return replies.pop(i)
                await asyncio.sleep(0.05)
        await asyncio.sleep(1.0)
        R["h0"] = (R.get("hello") or {}).get("rest")
        await call("say", text="Лира, отдохни час")
        await asyncio.sleep(1.5)
        R["st"] = (await call("rest_state"))["data"]
        R["ans"] = [e["text"] for e in EV if e["type"] == "answer" and e.get("done")]
        R["muted"] = [e for e in EV if e["type"] == "muted"]
        R["ptt"] = (await call("ptt"))["data"]
        await asyncio.sleep(0.5)
        R["st2"] = (await call("rest_state"))["data"]
        R["file2"] = (ct / "st" / "rest.json").exists()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()
asyncio.run(asyncio.wait_for(session(), 120))
ok(R.get("h0") == {"on": False, "until": 0, "until_text": "", "held": 0}, f"ядро: в hello — состояние отдыха: {R.get('h0')}")
ok(R.get("st", {}).get("on") and any("отдыхаю час" in a for a in R.get("ans", [])), f"ядро: «Лира, отдохни час» — без модели, отдыхает: {R.get('ans')}")
ok(any(e.get("on") for e in R.get("muted", [])), "ядро: микрофон выключен")
ok(R.get("ptt") == "listening" and not R.get("st2", {}).get("on") and not R.get("file2"), f"ядро: нажали на лицо — вернулась и слушает ({R.get('ptt')})")
print("ALL OK" if not fails else f"FAILS: {len(fails)}")
sys.exit(1 if fails else 0)
