"""GitHub №30–34 (04.11, открытая копия): отказ или поздний ответ ядра не должен выдаваться за успех и не должен ничего
затирать. Страницы — в Chromium; ответы ядра задерживаем и отклоняем подменой core.call (студия — с настоящим ядром).
№30 — «Мозг» персонажа: отказ — прежний выбор на месте; поздний ответ — своему персонажу, без ошибки после закрытия
       редактора; два быстрых выбора — остаётся последний (и в ядре).
№31 — «Прослушать»: голос сервера из поля редактора, а не сохранённый; при eSpeak подсказка не называет Piper.
№32 — напоминание: «Готово» / «Отложить» — итог только после ответа; отказ виден, повтор — тем же нажатием.
№33 — суфлёр: окно закрывается только после подтверждённой остановки; отказ — ошибка и повтор; поздний ответ
       не закрывает новую встречу.
№34 — блокнот: отказ записи не даёт сменить вкладку и не перезапускается сам; переподключение и поздний ответ
       чтения не затирают несохранённый текст; оборванная запись — «не знаю, сохранилось ли»."""
import json, os, socket, subprocess, sys, tempfile, time, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails, errs = [], []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


# подмена core.call: MODE[cmd] = 'fail' (отказ ядра) | 'lost' (связь оборвалась после отправки) | 'hold' (ответ задержан —
# HELD[i].go() / .no(текст)) | 'stub' (true без ядра); иначе — ANSWER(cmd, args) или настоящее ядро (REAL)
HOOK = r"""
(() => { window.CALLS = []; window.HELD = []; window.MODE = {};
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    if (window.NO_CORE) { core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} } core.connected = true; }
    const real = core.call.bind(core);
    const answer = (c, a) => window.ANSWER ? Promise.resolve().then(() => window.ANSWER(c, a || {})) : real(c, a);
    core.call = (c, a) => { CALLS.push([c, JSON.parse(JSON.stringify(a || {}))]); const m = MODE[c];
      if (m === 'fail') return Promise.reject(new Error('ядро отказало'));
      if (m === 'lost') return Promise.reject(Object.assign(new Error('нет связи с ядром'), { lost: true }));
      if (m === 'stub') return Promise.resolve(true);
      if (m === 'hold') return new Promise((res, rej) => HELD.push({ c, a, go: () => answer(c, a).then(res, rej), no: (t) => rej(new Error(t)) }));
      return answer(c, a); }; };
  ready(); })();
"""
NO_CORE = "window.NO_CORE = true;"


def page(b, url, init=(), size=(440, 640)):
    pg = b.new_page(viewport={"width": size[0], "height": size[1]})
    pg.on("pageerror", lambda e: errs.append(f"{url.split('/')[-1][:40]}: {e}"))
    for s in init:
        pg.add_init_script(s)
    pg.add_init_script(HOOK)
    pg.goto(url)
    return pg


def held(pg, cmd):
    return pg.evaluate("(c) => HELD.filter(h => h.c === c).length", cmd)


def release(pg, cmd, how="go()", msg=""):
    pg.evaluate("([c, how, msg]) => { const i = HELD.findIndex(h => h.c === c); const h = HELD.splice(i, 1)[0]; how === 'go()' ? h.go() : h.no(msg); }", [cmd, how, msg])


def calls(pg, cmd):
    return pg.evaluate("(c) => CALLS.filter(x => x[0] === c).map(x => x[1])", cmd)


# ---------------- №30, №31: студия с настоящим ядром ----------------
tmp = Path(tempfile.mkdtemp())
LLM, LLM2, PORT = free(), free(), free()
mocks = [subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(x)], env=dict(os.environ, MOCK_LOG=str(tmp / f"{x}.log"))) for x in (LLM, LLM2)]
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({
    "persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "memory_motion": "off"},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"},
    "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"},
                                        "c": {"name": "Claude", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM2}/v1", "model": "mock"}}}}))
st = tmp / "st"; st.mkdir()
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(st), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)


def disk_persona():
    try:
        return json.loads((cfg / "settings.json").read_text())["llm"].get("persona", {}).get("patrik")
    except Exception:  # noqa: BLE001
        return "?"


try:
    for _ in range(150):
        time.sleep(0.2)
        if (cfg / "token").exists():
            break
    time.sleep(2)
    tok = (cfg / "token").read_text().strip()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = page(b, (ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}", size=(1400, 1000)); time.sleep(3)
        pg.click('nav button[data-p="personas"]'); time.sleep(0.8)

        def edit(name):
            pg.locator("#pgrid .card", has_text=name).first.locator(".edit").click(); time.sleep(0.6)

        def on():
            return pg.evaluate("(document.querySelector('#e-brain .bp.on') || {}).dataset?.b ?? null")
        edit("Патрик")
        ok(on() == "", "Патрик: по умолчанию «Как у всех»")
        # отказ
        pg.evaluate("MODE.settings_save = 'fail'")
        pg.click("#e-brain [data-b='c']"); time.sleep(0.5)
        toast = pg.evaluate("document.querySelector('#toast').textContent")
        ok(on() == "" and pg.evaluate("((S.llm || {}).persona || {}).patrik || ''") == "" and "Не сохранилось" in toast and "думает моделью" not in toast,
           f"№30: отказ — выбор прежний, ошибка словами, «думает моделью» не говорим ({toast!r})")
        # поздний ответ после закрытия редактора и открытия другого персонажа
        pg.evaluate("MODE.settings_save = 'hold'")
        pg.click("#e-brain [data-b='c']"); time.sleep(0.2)
        ok(held(pg, "settings_save") == 1 and on() == "" and pg.evaluate("document.querySelector(\"#e-brain [data-b='c']\").classList.contains('wait')"),
           "№30: пока ядро не ответило — выбор «сохраняется», а не «выбран»")
        pg.click("#e-x"); time.sleep(0.4); edit("Лира")
        release(pg, "settings_save"); time.sleep(0.8)
        ok(pg.evaluate("ed && ed.id") == "lira" and on() == "" and disk_persona() == "c",
           f"№30: поздний ответ — Патрику; у открытой Лиры всё как было ({pg.evaluate('ed && ed.id')}, {on()!r}, {disk_persona()!r})")
        pg.click("#e-x"); time.sleep(0.3)
        pg.evaluate("MODE.settings_save = 'hold'"); edit("Патрик")
        pg.click("#e-brain [data-b='c']"); time.sleep(0.1)
        pg.click("#e-x"); time.sleep(0.2)
        release(pg, "settings_save"); time.sleep(0.6)
        ok(not [e for e in errs if "settings" in e], f"№30: ответ после закрытия редактора — без ошибок страницы {errs[:1]}")
        # два быстрых выбора: «Как у всех», затем «Мок» — остаётся последний, что бы ни ответили раньше
        edit("Патрик")
        pg.click("#e-brain [data-b='']"); time.sleep(0.05); pg.click("#e-brain [data-b='m']"); time.sleep(0.2)
        n1 = held(pg, "settings_save")
        release(pg, "settings_save"); time.sleep(0.4)
        n2 = held(pg, "settings_save")
        if n2:
            release(pg, "settings_save")
        time.sleep(0.8)
        sent = [c["patch"]["llm"]["persona"]["patrik"] for c in calls(pg, "settings_save")[-2:]]
        ok(n1 == 1 and n2 == 1 and sent == ["", "m"], f"№30: сохранения по очереди, второе — после ответа на первое ({n1}, {n2}, {sent})")
        ok(on() == "m" and pg.evaluate("S.llm.persona.patrik") == "m" and disk_persona() == "m",
           f"№30: два быстрых выбора — остаётся последний и в студии, и в ядре ({on()!r}, {disk_persona()!r})")
        pg.evaluate("MODE.settings_save = ''")
        # №31: «Прослушать» — несохранённый голос сервера
        pg.evaluate("MODE.voice_test = 'stub'")
        pg.fill("#e-remote", "ryan-новый"); pg.click("#e-listen"); time.sleep(0.3)
        vt = calls(pg, "voice_test")
        ok(vt and vt[-1].get("voice", {}).get("remote") == "ryan-новый", f"№31: «Прослушать» — голос сервера из поля, без сохранения ({vt[-1:] })")
        hint = pg.evaluate("S.tts = Object.assign({}, S.tts, { engine: 'espeak' }); voiceHint(); document.querySelector('#e-vhint').textContent")
        ok("eSpeak" in hint and "звучит Piper" not in hint, f"№31: при eSpeak подсказка не называет Piper ({hint!r})")
        b.close()
finally:
    core.terminate()
    for m in mocks:
        m.terminate()

# ---------------- №32: окно напоминания ----------------
ALARM_API = "window.CLOSED = 0; window.pywebview = { api: { close_alarm() { window.CLOSED++; }, open_note() {} } };"
ALARM_ANS = "window.ANSWER = (c, a) => c === 'alarm_snooze' ? { when: 'в 12:40' } : c === 'alarm_ack' ? { id: 'r1', result: 'ack' } : c === 'reminder_files' ? { files: [] } : c === 'alarm_get' ? null : {};"
AURL = (ROOT / "ui/alarm.html").as_uri() + "?id=r1&text=" + urllib.parse.quote("полить цветы")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = page(b, AURL, [NO_CORE, ALARM_API, ALARM_ANS], (380, 520)); pg.wait_for_timeout(400)
    pg.evaluate("MODE.alarm_ack = 'fail'"); pg.click("#ok"); pg.wait_for_timeout(300)
    hint = pg.evaluate("document.querySelector('#hint').textContent")
    ok(pg.evaluate("document.querySelector('#kind').textContent") != "Готово" and "Не получилось" in hint and pg.is_visible("#ok")
       and pg.evaluate("CLOSED") == 0, f"№32: отказ «Готово» — не «Готово», ошибка видна, кнопка на месте ({hint!r})")
    pg.wait_for_timeout(1500)
    ok(len(calls(pg, "alarm_ack")) == 1, "№32: сам не повторяет")
    pg.evaluate("MODE.alarm_ack = 'hold'"); pg.click("#ok"); pg.wait_for_timeout(150)
    ok("wait" in pg.evaluate("document.querySelector('#wrap').className") and pg.evaluate("document.querySelector('#kind').textContent") != "Готово",
       "№32: пока ждём ответа — ожидание, не «Готово»")
    pg.click("#ok", force=True); pg.wait_for_timeout(100)
    ok(len(calls(pg, "alarm_ack")) == 2, "№32: второе нажатие во время ожидания не шлёт ещё один запрос")
    release(pg, "alarm_ack"); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#kind').textContent") == "Готово", "№32: повтор удался — «Готово»")
    # отложить: отказ, затем удачно
    pg2 = page(b, AURL, [NO_CORE, ALARM_API, ALARM_ANS], (380, 520)); pg2.wait_for_timeout(400)
    pg2.evaluate("MODE.alarm_snooze = 'fail'"); pg2.click("#snooze button[data-m='10']"); pg2.wait_for_timeout(300)
    sub, hint = pg2.evaluate("[document.querySelector('#sub').textContent, document.querySelector('#hint').textContent]")
    ok("Напомню" not in sub and "Не получилось отложить" in hint and pg2.is_visible("#snooze") and pg2.evaluate("CLOSED") == 0,
       f"№32: отказ «Отложить» — не «Напомню…», ошибка видна ({sub!r}, {hint!r})")
    pg2.evaluate("MODE.alarm_snooze = ''"); pg2.click("#snooze button[data-m='10']"); pg2.wait_for_timeout(300)
    ok("Напомню в 12:40" in pg2.evaluate("document.querySelector('#sub').textContent"), "№32: повтор — «Напомню в 12:40»")
    # dewiar.js: связь оборвалась, ответ на отправленный запрос потерян — ошибка с пометкой lost
    pg3 = b.new_page()
    pg3.add_init_script("window.WebSocket = class { constructor() { window.WS = this; } send() {} close() {} };")
    pg3.goto(AURL); pg3.wait_for_timeout(200)
    lost = pg3.evaluate("""new Promise(r => { core.connected = true; core.ws = WS; core.call('pad_write', {}).catch(e => r(!!e.lost)); WS.onclose(); })""")
    ok(lost is True, "связь оборвалась после отправки — ошибка помечена lost (результат неизвестен)")
    b.close()

# ---------------- №33: суфлёр ----------------
PR_API = "window.CLOSED = 0; window.pywebview = { api: { close_prompter() { window.CLOSED++; }, open_settings() {} } };"
PR_ANS = """window.ST = { on: true, brain: true, paused: false, status: '', meeting: { title: 'Встреча', started: 1000 }, hints: [], lines: [{ who: 'me', text: 'Привет' }], files: [], sheet: [] };
window.ANSWER = (c, a) => c === 'prompter_state' ? ST : c === 'prompter_stop' ? Object.assign({}, ST, { on: false }) : {};"""
PURL = (ROOT / "ui/prompter.html").as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = page(b, PURL, [NO_CORE, PR_API, PR_ANS], (440, 690))
    pg.wait_for_timeout(200); pg.evaluate("core.emit('hello', {})"); pg.wait_for_timeout(300)
    ok(pg.evaluate("view") == "live", "суфлёр: идёт встреча")
    pg.evaluate("MODE.prompter_stop = 'hold'")
    pg.click("#b-close"); pg.click("#endask-yes"); pg.wait_for_timeout(300)
    ok(pg.evaluate("CLOSED") == 0 and pg.is_visible("#endask") and pg.is_disabled("#endask-yes"),
       "№33: ответа на остановку ещё нет — окно открыто, «Заканчиваю…»")
    release(pg, "prompter_stop", "no", "диск переполнен"); pg.wait_for_timeout(200)
    d = pg.evaluate("document.querySelector('#endask-d').textContent")
    ok(pg.evaluate("CLOSED") == 0 and pg.is_visible("#endask") and "Не получилось" in d and not pg.is_disabled("#endask-yes"),
       f"№33: отказ — окно открыто, ошибка и «Закончить» для повтора ({d!r})")
    pg.evaluate("MODE.prompter_stop = ''"); pg.click("#endask-yes"); pg.wait_for_timeout(300)
    ok(pg.evaluate("CLOSED") == 1, "№33: повтор удался — окно закрылось")
    # поздний ответ старой остановки, а уже идёт другая встреча
    pg2 = page(b, PURL, [NO_CORE, PR_API, PR_ANS], (440, 690))
    pg2.wait_for_timeout(200); pg2.evaluate("core.emit('hello', {})"); pg2.wait_for_timeout(300)
    pg2.evaluate("MODE.prompter_stop = 'hold'"); pg2.click("#b-close"); pg2.click("#endask-yes"); pg2.wait_for_timeout(200)
    pg2.evaluate("st = Object.assign({}, ST, { on: true, meeting: { title: 'Новая', started: 2000 } }); render()")
    release(pg2, "prompter_stop"); pg2.wait_for_timeout(300)
    ok(pg2.evaluate("CLOSED") == 0, "№33: поздний ответ старой остановки не закрывает новую встречу")
    b.close()

# ---------------- №34: блокнот ----------------
PAD_API = "window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(k === 'get_pos' ? [1500, 300] : true) }) };"
PAD_ANS = r"""window.STORE = { 'Альфа': 'Текст альфы\n', 'Бета': 'Текст беты\n' }; window.MT = 1;
window.ANSWER = (c, a) => {
  if (c === 'pad_tabs') return { tabs: Object.keys(STORE).map(n => ({ name: n, mtime: 1 })), active: 'Альфа' };
  if (c === 'pad_read') return { name: a.name, text: STORE[a.name] || '', mtime: MT };
  if (c === 'pad_write') { STORE[a.name] = a.text; return { mtime: ++MT }; }
  if (c === 'sync_status') return { available: false };
  return {}; };"""
DURL = (ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "left", "gap": 14, "clips": []}))


def ed_text(pg):
    return pg.evaluate("document.querySelector('#ed').innerText")


def st_text(pg):
    return pg.evaluate("document.querySelector('#st').textContent")


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = page(b, DURL, [NO_CORE, PAD_API, PAD_ANS], (440, 560)); pg.wait_for_timeout(1000)
    ok(pg.evaluate("P.active") == "Альфа" and "Текст альфы" in ed_text(pg), "блокнот: открыта «Альфа»")
    # 1. отказ записи → смена вкладки
    pg.evaluate("MODE.pad_write = 'fail'")
    pg.click("#ed"); pg.keyboard.press("End"); pg.keyboard.type(" черновик"); pg.wait_for_timeout(1100)
    ok("Не сохранилось" in st_text(pg) and pg.evaluate("P.dirty"), f"№34: отказ записи виден и правка помечена несохранённой ({st_text(pg)!r})")
    pg.wait_for_timeout(1600)
    ok(len(calls(pg, "pad_write")) == 1 and "Сохраняю" not in st_text(pg), f"№34: после отказа сам не повторяет, «Сохраняю…» ошибку не прячет ({len(calls(pg, 'pad_write'))})")
    pg.click(".tab >> text=Бета"); pg.wait_for_timeout(500)
    ok(pg.evaluate("P.active") == "Альфа" and "черновик" in ed_text(pg) and pg.evaluate("P.dirty") and "Не переключаю" in st_text(pg),
       f"№34: запись не прошла — вкладку не меняем, черновик на месте ({pg.evaluate('P.active')}, {st_text(pg)!r})")
    pg.evaluate("MODE.pad_write = ''"); pg.click(".tab >> text=Бета"); pg.wait_for_timeout(500)
    ok(pg.evaluate("P.active") == "Бета" and "черновик" in pg.evaluate("STORE['Альфа']"), "№34: запись прошла — черновик сохранён, вкладка сменилась")
    # 2. связь оборвалась во время записи → переподключение
    pg.evaluate("MODE.pad_write = 'lost'")
    pg.click("#ed"); pg.keyboard.press("End"); pg.keyboard.type(" после обрыва"); pg.wait_for_timeout(1100)
    ok("не знаю, сохранилось ли" in st_text(pg), f"№34: оборванная запись — «не знаю, сохранилось ли» ({st_text(pg)!r})")
    pg.evaluate("MODE.pad_write = 'fail'; core.emit('hello', {})"); pg.wait_for_timeout(600)
    ok("после обрыва" in ed_text(pg) and pg.evaluate("P.dirty"), "№34: переподключение, а записать всё ещё нельзя — текст не перечитан с диска")
    pg.evaluate("MODE.pad_write = ''; core.emit('hello', {})"); pg.wait_for_timeout(600)
    ok("после обрыва" in ed_text(pg) and "после обрыва" in pg.evaluate("STORE['Бета']") and not pg.evaluate("P.dirty"),
       "№34: переподключение — сначала записали, текст на месте")
    # 3. поздний ответ чтения другой вкладки, пока печатают
    pg.evaluate("MODE.pad_read = 'hold'"); pg.click(".tab >> text=Альфа"); pg.wait_for_timeout(200)
    pg.click("#ed"); pg.keyboard.press("End"); pg.keyboard.type(" пока грузилось"); pg.wait_for_timeout(100)
    pg.evaluate("MODE.pad_read = ''"); release(pg, "pad_read"); pg.wait_for_timeout(1200)
    ok(pg.evaluate("P.active") == "Бета" and "пока грузилось" in ed_text(pg) and "пока грузилось" in pg.evaluate("STORE['Бета']"),
       f"№34: поздний ответ чтения не затирает набранное — остались во вкладке и записали ({pg.evaluate('P.active')}, {st_text(pg)!r})")
    ok("пока грузилось" not in pg.evaluate("STORE['Альфа']"), "№34: и в чужую вкладку набранное не попало")
    b.close()

ok(not errs, f"без ошибок страниц: {errs[:3]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
