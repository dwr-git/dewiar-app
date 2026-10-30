"""«Лира перестала говорить, „Прослушать“ тоже не работает» (30.10, отчёт №421, владелец): включился «Текстовый режим»
(студия → «Чат»): голос и микрофон выключены, прежний голос запомнен (ui.text_prev). Включился незаметно — в журнале
ни строки, в виджете ни следа.
Теперь: метка «голос выключен» в виджете видна всегда, нажали — режим выключен; «Прослушать» в текстовом режиме читает
прежним голосом; включение и выключение — в журнале; поиск по студии не ставит курсор на флажки и переключатели."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from engine_remote import RemoteMixin  # noqa: E402
import tts  # noqa: E402


class S:
    def __init__(self, d): self.d = d
    def get(self, a, b=None): v = self.d.get(a, {}); return v if b is None else (v or {}).get(b)


class Fake(RemoteMixin):
    def __init__(self, d):
        self.s = S(d)
        self.tts_remote = None
        self.piper = type("P", (), {"has": lambda *a: False})()
        self.espeak = type("E", (), {"available": lambda *a: False})()
        self.vosk_tts = type("V", (), {"ready": False, "error": ""})()
    def _voice_cfg(self, pid=None): return {}


REM = {"base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "api_key": "k", "model": "tts-1", "cloud": True}
f = Fake({"tts": {"engine": "off", "remote": REM, "eleven": {}}, "ui": {"text_mode": True, "text_prev": "remote"}})
ok(f._engines_for_speech() == [], "текстовый режим: обычные ответы — молча, как и задумано")
ch = f._engines_for_speech(None, True)
ok(len(ch) == 1 and isinstance(ch[0], tts.RemoteTTS), f"«Прослушать» в текстовом режиме — прежним голосом (облако Dewiar): {ch}")
ok(f._engines_for_speech(None, True)[0] is ch[0], "голос для «Прослушать» создаётся один раз")
g = Fake({"tts": {"engine": "off", "remote": REM}, "ui": {}})
ok(g._engines_for_speech(None, True) == [], "голос выключен сам («Без голоса») — «Прослушать» не включает его без спроса")
cmd = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok("⌨ Текстовый режим включён" in cmd and "🔊 Текстовый режим выключен" in cmd, "включение и выключение текстового режима — в журнале")
fj = (ROOT / "ui/studio/find.js").read_text(encoding="utf-8")
ok(":not([type=checkbox]):not([type=radio])" in fj, "поиск по студии не ставит курсор на флажки и переключатели")

CORE = r"""
(() => { window.calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); return true; };
    setTimeout(() => { core.emit("hello", {}); core.emit("settings", { settings: { ui: { text_mode: true } } }); }, 200); };
  ready(); })();"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 520, "height": 400}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1500)
    vis = pg.evaluate("(() => { const b = document.getElementById('b-tm'); const c = document.getElementById('corner-l'); return [!b.hidden, getComputedStyle(c).opacity, b.textContent.trim()]; })()")
    ok(vis[0] and float(vis[1]) == 1 and "голос выключен" in vis[2], f"виджет: метка «голос выключен» видна всегда: {vis}")
    pg.evaluate("document.getElementById('b-tm').click()"); pg.wait_for_timeout(300)
    ok(["text_mode", {"on": False}] in pg.evaluate("calls") and pg.evaluate("document.getElementById('b-tm').hidden")
       and pg.evaluate("getComputedStyle(document.getElementById('b-tm')).display") == "none", "нажали — текстовый режим выключен, метка ушла (и с экрана)")
    # 30.10, владелец: «в 0.72 плашка „голос выключен“ висит, даже когда голос включён» — hidden был, а на экране оставалась
    for skin in ("neusky", "brand"):
        hp = b.new_page(viewport={"width": 520, "height": 400}); hp.on("pageerror", lambda e: errs.append(str(e)))
        hp.route(re.compile(r"^https?://"), lambda r: r.abort())
        hp.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        hp.add_init_script(CORE.replace("ui: { text_mode: true }", f"ui: {{ text_mode: false, skin: '{skin}' }}"))
        hp.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); hp.wait_for_timeout(1200)
        d = hp.evaluate("(() => { const b = document.getElementById('b-tm'); return [b.hidden, getComputedStyle(b).display, b.getBoundingClientRect().width]; })()")
        ok(d[0] and d[1] == "none" and d[2] == 0, f"голос включён ({skin}) — плашки «голос выключен» нет на экране: {d}")
        hp.close()
    # студия → «Чат»: строка «Текстовый режим» и вопрос перед включением
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errs.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort())
    st.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); st.add_init_script(CORE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1500)
    st.evaluate("() => { S.ui = Object.assign({}, S.ui, { text_mode: true }); document.querySelector('nav button[data-p=\"chat\"]').click(); chatTmSync(); }"); st.wait_for_timeout(300)
    ok(st.is_visible("#ch-tmbar") and "голос и микрофон выключены" in st.inner_text("#ch-tmbar"), "«Чат»: пока режим включён — строка «Текстовый режим» с кнопкой")
    if os.environ.get("DEWIAR_SHOTS"): st.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "chat-textmode.png"))
    st.click("#ch-tmbar button"); st.wait_for_timeout(300)
    ok(["text_mode", {"on": False}] in st.evaluate("calls") and st.is_hidden("#ch-tmbar") and not st.is_checked("#ch-tm"), "«Включить голос» — режим выключен, строка ушла")
    st.evaluate("document.querySelector('#ch-tm').click()"); st.wait_for_timeout(300)
    ok(st.locator(".dwq button.yes").count() == 1 and "Голос и микрофон выключатся" in st.inner_text(".dwq"), "включить — только после вопроса")
    st.click(".dwq button:not(.yes)"); st.wait_for_timeout(300)
    ok(not st.is_checked("#ch-tm") and st.evaluate("calls").count(["text_mode", {"on": True}]) == 0, "«Отмена» — режим не включился")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
