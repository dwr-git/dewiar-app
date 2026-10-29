"""Идея №58 (29.10): «кнопку „Прослушать ответ“ под сообщениями Лиры — на прогулке без очков не прочитать, переслушать
проще; паузу/стоп». Телефон: в «Разговоре» под каждым ответом — «Прослушать» (читает и в текстовом режиме), нажали снова —
«Стоп», дочитал — снова «Прослушать». Студия: в «Чате» под ответом — «Прослушать» голосом того, кто отвечал (voice_test
listen, без смены персонажа)."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
FAKE_CORE = """(() => {
  window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "chat_list") return { items: [{ id: "m1", ts: Date.now() / 1000 - 60, role: "user", text: "Как сварить гречку?" },
        { id: "m2", ts: Date.now() / 1000 - 50, role: "assistant", who: "patrik", text: "Промойте гречку и варите **15 минут** под крышкой." }], more: false };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""
with sync_playwright() as p:
    b = p.chromium.launch(); errors = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    pg.evaluate("""() => { window._said = []; const sp = D.speak.bind(D); D.speak = (id, t, ...r) => { window._said.push(t); return sp(id, t, ...r); }; D.ttsReady = () => true;
        S.textMode = true; history.push({ role: "user", content: "Как сварить гречку?" }, { role: "assistant", content: "Промойте гречку и варите **15 минут**.", who: "lira" }); saveH(); }""")
    pg.click("#b-hist"); pg.wait_for_timeout(400)
    n = pg.locator("#hlist .msg.a .mlisten").count()
    pg.click("#hlist .msg.a .mlisten"); pg.wait_for_timeout(100)
    R = {"n": n, "said": pg.evaluate("_said"), "lab": pg.inner_text("#hlist .mlisten")}
    pg.wait_for_timeout(900)
    R["after"] = pg.inner_text("#hlist .mlisten")
    pg.click("#hlist .mlisten"); pg.wait_for_timeout(50)
    pg.click("#hlist .mlisten"); pg.wait_for_timeout(50)
    R["stopped"] = pg.inner_text("#hlist .mlisten")
    R["tm"] = pg.evaluate("S.textMode")
    ok(R["n"] == 1, "под ответом в «Разговоре» — «Прослушать» (под вопросом — нет)")
    ok(R["said"] and "15 минут" in R["said"][0] and "*" not in R["said"][0] and R["lab"] == "Стоп", f"читает вслух и в текстовом режиме, кнопка — «Стоп»: {R['said'][:1]} {R['lab']!r}")
    ok(R["after"] == "Прослушать" and R["stopped"] == "Прослушать" and R["tm"] is True, "дочитал или «Стоп» — снова «Прослушать»; текстовый режим не сбит")
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errors.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort())
    st.add_init_script(FAKE_CORE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1500)
    st.evaluate("document.querySelector('nav button[data-p=\"chat\"]').click()"); st.wait_for_timeout(300)
    st.evaluate("loadChat()"); st.wait_for_timeout(600)
    k = st.locator("#ch-msgs .ch-listen").count()
    st.click("#ch-msgs .ch-listen"); st.wait_for_timeout(200)
    vt = [a for c, a in st.evaluate("calls") if c == "voice_test"]
    ok(k == 1 and vt and vt[0].get("listen") and vt[0].get("persona") == "patrik" and "15 минут" in vt[0].get("text", "") and st.inner_text("#ch-msgs .ch-listen") == "Стоп",
       f"студия: «Прослушать» под ответом — голосом Патрика, без смены персонажа: {vt[:1]}")
    st.click("#ch-msgs .ch-listen"); st.wait_for_timeout(200)
    ok(any(c == "stop" for c, a in st.evaluate("calls")) and st.inner_text("#ch-msgs .ch-listen") == "Прослушать", "«Стоп» — останавливает")
    ok(not errors, f"без ошибок: {errors[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
