"""№468 (01.11, телефон 0.9.16): «Дозор включил на компьютере, а на телефоне спрашиваю, как там статус дозора, не
изменился ли, — а Лира просто выдумывает что попало». Телефон знал о дозоре только «готово».
— компьютер шлёт своим телефонам снимок дозоров {watch: …} (постановка, остановка, срабатывание, конец срока, раз в
  10 минут, пока идёт, и по просьбе {want: ["watch"]});
— телефон на «как там дозор?» отвечает по снимку без модели, а снимка нет (старый компьютер) — честно: отсюда не видно,
  где посмотреть, и когда было последнее «готово»; «поставь дозор» — что это делается на компьютере."""
import json, os, subprocess, sys, tempfile, time
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


# ---------- компьютер: снимок дозоров своим телефонам ----------
import engine_watch as EW  # noqa: E402
import engine_tools as ET  # noqa: E402
import watch as W  # noqa: E402

sent = []


class Close:
    def _own_quiet(self, body):
        sent.append(body)


class E(EW.WatchMixin, ET.ToolsMixin):
    def __init__(self):
        self.watches = W.Watches(tmp / "watch.json")
        self.close = Close()
        self.events = []

    def emit(self, t, **kw):
        self.events.append(t)

    def device_name(self):
        return "Домашний"

    def _watch_check(self, x):                   # первая проверка — не в этой проверке
        pass


e = E()
it = e.watch_add({"kind": "page", "url": "https://example.org/status", "what": "Одобрено"})
time.sleep(0.3)
w = (sent[-1] if sent else {}).get("watch") or {}
ok(w.get("dev") == "Домашний" and w.get("active") == 1 and w["items"][0]["status"] == "active" and "Одобрено" in w["items"][0]["title"],
   f"поставили дозор — телефону ушёл снимок: {w}")
ok("url" not in w["items"][0] and "folder" not in w["items"][0], "в снимке — без адресов и папок")
n = len(sent)
e.watches.mark(e.watches.get(it["id"]), "пока нет")
ok(e._watch_publish() is False and len(sent) == n, "«пока нет» сразу после снимка — не шлём (раз в 10 минут)")
e._watch_pub_at = 0
ok(e._watch_publish() is True, "через 10 минут — свежий снимок с заметкой проверки")
time.sleep(0.2)
ok(sent[-1]["watch"]["items"][0]["note"] == "пока нет", "в снимке — последняя заметка проверки")
n = len(sent)
e.own_apply({"want": ["watch"]})
time.sleep(0.2)
ok(len(sent) == n + 1 and "watch" in sent[-1], "телефон попросил {want: [watch]} — снимок сразу")
e.watch_stop(it["id"])
time.sleep(0.2)
ok(sent[-1]["watch"]["active"] == 0 and sent[-1]["watch"]["items"][0]["status"] == "stopped", "остановили — снимок сразу")
SNAP = sent[-2]["watch"]

# ---------- телефон ----------
w = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("() => { window.ownSent = []; devOwnSend = async (b) => { ownSent.push(b); return true; }; }")
    q = "как там статус дозора, не изменился?"
    r = pg.evaluate("(q) => pcWatchQuick(q)", q)
    ok(r and "не вижу" in r["say"] and "студия → «Дозор»" in r["say"] and "Обновите Dewiar на компьютере" in r["say"],
       f"снимков нет — честно: отсюда не видно, где посмотреть: {r}")
    pg.wait_for_timeout(100)
    ok(pg.evaluate("ownSent.some(b => (b.want || []).includes('watch'))"), "и попросили компьютер прислать дозоры")
    pg.evaluate("() => ownApply({ ts: Date.now(), ping: { title: '👁 Дозор: готово', text: 'Сборка — готово', dev: 'Домашний', wid: 'a1', what: 'Сборка закончилась', note: 'в терминале «Готово»' } })")
    r = pg.evaluate("(q) => pcWatchQuick(q)", q)
    ok(r and "Последнее такое" in r["say"] and "Сборка закончилась" in r["say"], f"старый компьютер — хотя бы последнее «готово»: {r}")
    pg.evaluate("(w) => ownApply({ ts: Date.now(), watch: w })", SNAP)
    r = pg.evaluate("(q) => pcWatchQuick(q)", q)
    ok(r and "идёт дозор" in r["say"].lower() and "««" not in r["say"] and "Одобрено" in r["say"] and "пока нет" in r["say"] and "смотрит" in r["say"], f"снимок есть — отвечает по нему: {r}")
    r = pg.evaluate("async () => quick('Лира, как там статус дозора, не изменился?')")
    ok(r and "идёт дозор" in r["say"].lower(), f"через quick() — до модели, не выдумка: {r and r['say'][:80]}")
    r = pg.evaluate("(q) => pcWatchQuick(q)", "я включил дозор на компе — как там, сработал?")
    ok(r and "идёт дозор" in r["say"].lower(), "«я включил дозор — как там?» — это вопрос о статусе")
    r = pg.evaluate("(q) => pcWatchQuick(q)", "поставь дозор на загрузку")
    ok(r and "на компьютере" in r["say"] and "присмотри" in r["say"], f"«поставь дозор» — где это делается: {r}")
    ok(pg.evaluate("pcWatchQuick('какая погода завтра')") is None, "без дозора — не перехватываем")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
