"""0.99 (владелец 14.11): новым — набор «Для себя» по умолчанию: в меню нет работы и бизнеса (клиенты, рассылка, сайты,
чат для сайта, суфлёр, боты, рефералы); раз и молча, дальше человек меняет как хочет («Оформление» → «Что показывать»).
Кто уже пользовался — меню как было (ui.preset "all")."""
import json, os, re, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
from settings import Settings  # noqa: E402
new = Settings(tmp / "new.json")
ok(new.get("ui", "preset") == "self", f"новая установка — набор «Для себя»: {new.get('ui', 'preset')}")
(tmp / "old.json").write_text(json.dumps({"ui": {"welcome": "done"}}), encoding="utf-8")
old = Settings(tmp / "old.json")
ok(old.get("ui", "preset") == "all", "уже пользуются — меню как было")

FAKE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "settings_save") return Object.assign({}, S, a.patch, { ui: Object.assign({}, S.ui, (a.patch || {}).ui || {}) });
      return {}; };
  };
  ready(); })();"""
WORK = ["clients", "mailing", "sites", "sitechat", "prompter", "pbot", "ref", "team"]
VIS = "(ps) => ps.filter(p => { const b = document.querySelector(`nav button[data-p=\"${p}\"]`); return b && b.offsetParent !== null; })"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for preset in ("self", "all"):
        pg = b.new_page(viewport={"width": 1360, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        pg.add_init_script(FAKE)
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
        pg.evaluate("""(pr) => { if (!S) S = {}; S.ui = { preset: pr, welcome: "done" }; S.features = { clients: true, team: true, sites: true, prompter: true };
          if (typeof featuresApply === "function") featuresApply(); hmNav(); shFirstPreset(); }""", preset)
        pg.wait_for_timeout(600)
        vis = pg.evaluate(VIS, WORK)
        saves = [a for c, a in pg.evaluate("calls") if a and "ui" in json.dumps(a)]
        if preset == "self":
            ok(vis == [], f"новая установка: работы и бизнеса в меню нет (видно: {vis})")
            ok(any("done" in json.dumps(a) for a in saves) and pg.evaluate("S.ui.preset") == "done", "набор применён один раз и запомнен")
            ok(pg.evaluate(VIS, ["chat", "calendar", "reminders", "notes", "docs", "close"]) == ["chat", "calendar", "reminders", "notes", "docs", "close"],
               "ядро на месте: чат, календарь, дела, заметки, «Мои файлы», близкие")
        else:
            ok(len(vis) >= 6, f"прежний пользователь: работа в меню как была ({vis})")
        pg.close()
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
