"""«Радар»: срочное в виджете (владелец 12.11: «⚡ Радар: важное — …» всё в кучу, слитно; разметка или переход в Радар).
Теперь весточка с разделом студии (push: open, head, body) — карточкой: метка, заголовок, суть в несколько строк и кнопка
«Открыть в Радаре» (и нажатие на заголовок) — студия на «Радаре». Обычные весточки — как раньше одной строкой."""
import json, os, re, sys, tempfile, time, types
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# --- ядро: срочное Радара уходит с полями для виджета (и материал, и всплеск темы) ---
import engine_insight as EI  # noqa: E402


class S:
    d = {"insight": {}, "ui": {"lang": "ru"}}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]
    def active_llm(self): return {}


pushes = []
eng = types.SimpleNamespace(s=S(), emit=lambda *a, **k: None, push=lambda title, text="", **kw: pushes.append((title, text, kw)))
r = EI.Radar(eng, tmp / "r")
TITLE = "[Перевод] 594 млрд параметров, 68 часов предобучения и девять дней RL: как создавали Inkling 2 Small"
r.st.add_items({"id": "s1", "name": "habr.com"}, [{"title": TITLE, "url": "https://habr.com/ru/articles/1/", "text": "t"}])
iid = r.st.items()[0]["id"]
r.st.set_analysis(iid, {"summary": "Thinking Machines Lab представила мультимодальную модель Inkling 2 Small с 594 млрд параметров.",
                        "why": "w", "type": "release", "tags": ["llm"], "entities": [], "signal": 9.1})
r.urgent()
t, txt, kw = pushes[0]
ok(kw.get("open") == "insight:" + iid and kw.get("head") == TITLE and kw.get("body", "").startswith("Thinking Machines"),
   f"срочное: сразу к материалу (insight:<id>), заголовок и суть — отдельно: {kw}")
ok(txt.startswith(TITLE) and "Thinking Machines" in txt, "текст целиком — как раньше (Telegram, уведомление системы)")
import insight as I  # noqa: E402
I_urgent = I.urgent
I.urgent = lambda *a, **k: [{"kind": "trend", "id": "t:llm", "title": "llm", "day": 5, "impulse": 4}]
r.st.save("log", {}); pushes.clear(); r.urgent(); I.urgent = I_urgent
ok(pushes and pushes[0][2].get("open") == "insight" and pushes[0][2].get("head") == "llm" and "5 материалов" in pushes[0][2].get("body", ""), f"всплеск темы — тоже карточкой: {pushes[:1]}")

# движок: push пропускает только поля карточки
import engine_remote as ER  # noqa: E402
ev = []
fake = types.SimpleNamespace(emit=lambda t, **k: ev.append((t, k)), chat=types.SimpleNamespace(notify_on=lambda: False))
ER.desktop_notify = lambda *a, **k: None
cls = next(c for c in vars(ER).values() if isinstance(c, type) and "push" in vars(c))
cls.push(fake, "⚡ Радар: важное", "t", quiet=True, open="insight", head="H", body="B", junk="x")
ok(ev and ev[0][1].get("open") == "insight" and ev[0][1].get("head") == "H" and "junk" not in ev[0][1], f"событие push: {ev}")

# --- виджет ---
CORE = r"""(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async () => ({}); window.pywebview = { api: { open_settings: (p) => { window.__opened = p; return Promise.resolve(true); } } };
  setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neon", lang: "%s" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira",
    personas: [{ id: "lira", name: "Лира" }], reminders: [], state: "idle" }); }, 150); }; ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for lang in ("ru", "en"):
        pg = b.new_page(viewport={"width": 330, "height": 520}, device_scale_factor=2); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda q: q.abort()); pg.add_init_script(CORE % lang)
        pg.goto((ROOT / "ui/hud.html").as_uri() + f"?port=1&mode=card&lang={lang}"); pg.wait_for_timeout(1200)
        pg.evaluate("window.dwSetLang && dwSetLang('%s')" % lang)
        pg.evaluate("(a) => core.emit('push', a)", dict(title="⚡ Радар: важное" if lang == "ru" else "⚡ Radar: important", text=txt, **dict(kw, quiet=True)))
        pg.wait_for_timeout(300)
        o = pg.evaluate("""() => ({tag: (document.querySelector('#bot .pc-tag') || {}).textContent, head: (document.querySelector('#bot .pc-head') || {}).textContent,
          body: (document.querySelector('#bot .pc-body') || {}).textContent, btn: (document.querySelector('#bot .pc-go') || {}).textContent,
          show: document.getElementById('cap').classList.contains('show')})""")
        if lang == "ru":
            ok(o["show"] and o["head"] == TITLE and o["body"].startswith("Thinking") and o["tag"].startswith("⚡"), f"карточка: метка, заголовок, суть отдельно: {o}")
            ok(o["btn"] == "Открыть в Радаре", f"кнопка «Открыть в Радаре»: {o['btn']!r}")
            if os.environ.get("SHOT"):
                pg.locator("#cap").screenshot(path=os.environ["SHOT"])
            pg.click("#bot .pc-go"); pg.wait_for_timeout(200)
            ok(pg.evaluate("window.__opened") == "insight:" + iid, "кнопка открывает студию сразу на материале (читалка Радара)")
            pg.evaluate("window.__opened = null"); pg.evaluate("(a) => core.emit('push', a)", dict(title="⚡ Радар: важное", text=txt, **kw)); pg.wait_for_timeout(200)
            pg.click("#bot .pc-head"); pg.wait_for_timeout(200)
            ok(pg.evaluate("window.__opened") == "insight:" + iid, "нажатие на заголовок — тоже к материалу")
            pg.evaluate("() => core.emit('push', {title: 'Задача готова', text: 'Отчёт в папке'})"); pg.wait_for_timeout(200)
            plain = pg.evaluate("document.getElementById('bot').textContent")
            ok(plain == "Задача готова — Отчёт в папке" and not pg.evaluate("document.querySelector('#bot .pc-go')"), f"обычная весточка — как раньше: {plain!r}")
        else:
            ok(o["btn"] == "Open in Radar", f"по-английски: {o['btn']!r}")
        pg.close()
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
