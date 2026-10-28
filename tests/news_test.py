"""«Что нового» после обновления (отзыв 13.10: «что было в обновлении — непонятно, пришлось догадываться»). data/whatsnew.json —
общий текст: компьютер (core/news.py, студия, приветствие) и телефон (whatsnew.js, лист «Что нового»).
— только выпуски новее того, что человек видел, и только пункты для этой платформы; новая установка — без листа;
— студия: окно один раз, «Понятно» — больше не показывать; «О программе» → «Что нового» — снова (настоящее ядро);
— помощница при встрече говорит о новом одной фразой (presence.plan news);
— телефон: лист после обновления, «Попробовать: «…»» — Лира слышит фразу; «Ещё» → «Что нового»; сборка кладёт whatsnew.js."""
import json, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


import news  # noqa: E402
import presence  # noqa: E402
from version import VERSION  # noqa: E402
N = json.loads((ROOT / "data/whatsnew.json").read_text(encoding="utf-8"))
ok(N and all(r.get("pc") and r.get("phone") and r.get("items") for r in N) and all(i.get("title") and i.get("text") and i.get("where") for r in N for i in r["items"]),
   "whatsnew.json: у выпусков — версии компьютера и телефона, у пунктов — заголовок, текст и где")
ok(N[0]["pc"] == VERSION, f"верхний выпуск — текущая версия компьютера ({N[0]['pc']} = {VERSION})")
bi = (ROOT / "android/src/pro/dewiar/app/BuildInfo.java").read_text(encoding="utf-8")
ok(f'"{N[0]["phone"]}"' in bi, "и телефона")
r = news.releases("0.38.21", VERSION)
PC_RELS = [x["pc"] for x in N if any("pc" in i["where"] for i in x["items"])]       # выпуски, где есть новое для компьютера
ok([x["version"] for x in r] == [v for v in PC_RELS if news.ver_key(v) > news.ver_key("0.38.21")][:3] and all("pc" in i["where"] for x in r for i in x["items"]),
   f"компьютер: новее увиденного, только свои пункты: {[x['version'] for x in r]}")
ok(news.releases(VERSION, VERSION) == [], "всё увидено — пусто")
f = news.say_fact(news.releases("0.38.20", VERSION, "pc", 3))
p = presence.plan(3600, __import__("datetime").datetime.now().replace(hour=12) - __import__("datetime").timedelta(hours=1), [], [], None,
                  now=__import__("datetime").datetime.now().replace(hour=12), news=f)
ok(p and f in p["facts"] and f.startswith(f"Dewiar обновился до {PC_RELS[0]}") and "Что нового" not in f.split("Скажи")[0], f"приветствие: скажет, что нового: {f[:80]}")
ok("whatsnew.json" in (ROOT / "android/tools/www_assemble.sh").read_text(encoding="utf-8") and 'src="whatsnew.js"' in (ROOT / "android/assets/www/index.html").read_text(),
   "телефон: сборка кладёт whatsnew.js")

# студия с настоящим ядром: обновились с 0.38.20
tmp = Path(tempfile.mkdtemp())
for case, ui in (("обновились", {"welcome": "done", "news_seen": "0.38.20"}), ("новая установка", {"welcome": ""})):
    PORT = free(); cfg = tmp / case / "cfg"; cfg.mkdir(parents=True)
    (cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": ui, "welcome": {"on": False}}))
    env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / case / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
               DEWIAR_WORKSPACE_DIR=str(tmp / case / "ws"))
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            time.sleep(0.2)
            if (cfg / "token").exists():
                break
        time.sleep(2)
        tok = (cfg / "token").read_text().strip()
        with sync_playwright() as pw:
            b = pw.chromium.launch(); errs = []
            pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
            g = pg.evaluate("() => ({ open: document.getElementById('news-dlg').open, items: [...document.querySelectorAll('#nw-list .nwi b')].map(x => x.textContent) })")
            if case == "обновились":
                want = [i["title"] for r_ in news.releases("0.38.20", VERSION, "pc") for i in r_["items"]]
                phone_only = {i["title"] for r_ in N for i in r_["items"] if i["where"] == ["phone"]}
                ok(g["open"] and g["items"] == want and not (set(g["items"]) & phone_only),
                   f"студия после обновления: окно «Что нового» — пункты компьютера, без телефонных: {g}")
                pg.click("#nw-ok"); time.sleep(0.8)
                ok(json.loads((cfg / "settings.json").read_text())["ui"].get("news_seen") == VERSION, "«Понятно» — запомнено, больше не покажет")
                pg.reload(); time.sleep(3)
                ok(not pg.evaluate("document.getElementById('news-dlg').open"), "второй раз — не показывает")
                pg.click('nav button[data-p="about"]'); time.sleep(0.5); pg.click("#ab-news"); time.sleep(0.8)
                ok(pg.evaluate("document.getElementById('news-dlg').open"), "«О программе» → «Что нового» — открывает снова")
                if os.environ.get("NEWS_SHOT"):
                    pg.screenshot(path=os.environ["NEWS_SHOT"].replace(".png", "-studio.png"))
            else:
                ok(not g["open"] and json.loads((cfg / "settings.json").read_text())["ui"].get("news_seen") == VERSION, "новая установка — без окна, отмечено увиденным")
            ok(not errs, f"{case}: студия без ошибок: {errs[:2]}")
            b.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()

# телефон
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f_ in ("entities.js", "skins.css", "skins.js", "privacy.js"):
    shutil.copy(ROOT / "ui/assets" / f_, www / f_)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)], capture_output=True, text=True, check=True).stdout, encoding="utf-8")
(www / "whatsnew.js").write_text("window.DEWIAR_NEWS = " + json.dumps(N, ensure_ascii=False) + ";", encoding="utf-8")
with sync_playwright() as pw:
    b = pw.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1800)
    ok(not pg.evaluate("document.getElementById('sh-news').classList.contains('on')"), "телефон: новая установка — без листа")
    v = N[0]["phone"]
    vk = lambda x: tuple(int(p_) for p_ in x.split("."))  # noqa: E731
    PH_WANT = [i["title"] for r_ in sorted([r_ for r_ in N if vk(r_["phone"]) > vk("0.6.18") and any("phone" in i["where"] for i in r_["items"])],
                                           key=lambda r_: vk(r_["phone"]), reverse=True)[:3] for i in r_["items"] if "phone" in i["where"]]
    r = pg.evaluate("""(v) => { D.info = () => JSON.stringify({ version: v }); prefSet("news_seen", "0.6.18"); S.llm.base_url = "http://x/v1"; window._asked = []; ask = (t) => _asked.push(t);
        const shown = newsCheck(); return { shown, items: [...document.querySelectorAll('#news-body .nwi b')].map(x => x.textContent), sub: document.querySelector('.nwsub').textContent,
          seen: prefGet("news_seen"), tries: document.querySelectorAll('.nwtry').length }; }""", v)
    ok(r["shown"] and r["seen"] == v and f"Dewiar {v}" in r["sub"] and r["items"] == PH_WANT and "Отмечайте сделанное — получайте достижения" not in r["items"],
       f"телефон после обновления с 0.6.18: лист — только новее увиденного: {r}")
    if os.environ.get("NEWS_SHOT"):
        pg.screenshot(path=os.environ["NEWS_SHOT"])
    if not pg.evaluate("document.querySelectorAll('.nwtry').length"):      # в последних выпусках нет фразы «попробовать» — покажем выпуск, где она есть
        pg.evaluate("() => newsShow(newsList('', '0.6.19'))"); pg.wait_for_timeout(300)
    pg.click(".nwtry"); pg.wait_for_timeout(300)
    ok(pg.evaluate("_asked.length") == 1 and not pg.evaluate("document.getElementById('sh-news').classList.contains('on')"), f"«Попробовать» — Лира слышит фразу: {pg.evaluate('_asked')}")
    ok(pg.evaluate("newsCheck()") is False, "второй раз — не показывает")
    pg.evaluate("() => openSettings('about')"); pg.wait_for_timeout(400)
    pg.click("#news-open"); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.getElementById('sh-news').classList.contains('on') && document.querySelectorAll('#news-body .nwi').length === newsList('', JSON.parse(D.info()).version).reduce((a, r) => a + r.items.length, 0) && document.querySelectorAll('#news-body .nwi').length >= 3"), "«Ещё» → «Что нового» — открывает с прошлыми выпусками")
    ok(not errs, f"телефон без ошибок: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
