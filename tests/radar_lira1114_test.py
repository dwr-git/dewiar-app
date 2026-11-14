"""Владелец 14.11: «если Радар настроен — чтобы Лира иногда туда смотрела, там действительно может быть полезная
информация, вместо того, чтобы постоянно пересказывать напоминания и заметки»; «на телефоне… интересное в мире — от Лиры
кратко услышать с возможностью перейти для полного прочтения».
Радар настроен — в подсказке Лиры одно-два самых интересных за сутки (бриф дня первым, без «👎 Не то»): рассказать к
месту, не чаще раза за разговор; в «Утре с Лирой» — строкой; на телефон утро уходит со ссылкой — сводка дня говорит одну
новость, под ней карточка «Читать». Радар не настроен — ничего не добавляется."""
import json, os, subprocess, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import insight as I, engine_insight as EI, morning as M  # noqa: E402
tmp = Path(tempfile.mkdtemp()); now = time.time()


class S:
    d = {"insight": {"mission": "ИИ"}, "ui": {"lang": "ru"}}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]


eng = types.SimpleNamespace(s=S(), emit=lambda *a, **k: None, push=lambda *a, **k: None)
r = eng.insight = EI.Radar(eng, tmp / "s")
ok(r.highlights() is None and r.prompt_line() == "", "Радар не настроен — Лире ничего не добавляем")
r.st.add_sources("https://habr.com/ru/rss/all/all/")
src = r.st.sources()[0]
A = lambda s, why="": {"summary": "суть", "why": why, "type": "news", "tags": ["ии"], "entities": [], "signal": s}
r.st.save("items", [
    {"id": "bait", "src": src["id"], "src_name": src["name"], "title": "Кликбейт про ИИ", "url": "https://x/1", "ts": int(now - 600), "a": A(9.6), "fb": -1},
    {"id": "faa", "src": src["id"], "src_name": src["name"], "title": "FAA доверила ИИ управление воздушным движением", "url": "https://x/2", "ts": int(now - 900), "a": A(8.1)},
    {"id": "gpu", "src": src["id"], "src_name": src["name"], "title": "Майнинговые карты превращаются в A100", "url": "https://x/3", "ts": int(now - 1200), "a": A(8.8, "дешёвое железо")},
    {"id": "low", "src": src["id"], "src_name": src["name"], "title": "Мелочь", "url": "https://x/4", "ts": int(now - 1300), "a": A(3)}])
r.st.save("brief", {"headline": "ИИ уходит в критическую инфраструктуру", "main": [{"id": "faa", "why": "первое такое внедрение в стране"}],
                    "day": time.strftime("%Y-%m-%d")})
h = r.highlights()
ok([x["title"][:3] for x in h["items"]] == ["FAA", "Май"], f"главное брифа — первым, затем сильнейшее; «Не то» и слабое — нет: {h['items']}")
ok(h["items"][0]["why"] == "первое такое внедрение в стране" and h["items"][0]["url"] == "https://x/2", "с объяснением и ссылкой")
pl = r.prompt_line()
ok("РАДАР" in pl and "FAA" in pl and "ОДНО" in pl and "не чаще раза за разговор" in pl and "Кликбейт" not in pl, f"подсказка Лиры: {pl[:120]!r}")
ans = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("base += r.prompt_line()" in ans, "в личной части подсказки — Радар (после выводов ночи)")
d = {"radar": h}
ctx = M.context(d)
ok("Радар" in ctx and "FAA" in ctx and "одной фразой" in ctx, f"«Утро с Лирой»: строка Радара: {ctx[:100]!r}")
ok("_radar(eng)" in (ROOT / "core/morning.py").read_text(encoding="utf-8"), "утро собирает Радар (и уходит на свой телефон)")

www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.DW_SYS_LANG = 'ru';")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
    out = pg.evaluate("""async (h) => {
      closeSheets(); const opened = []; D.openUrl = (u) => { opened.push(u); return true; };
      mornTake({ at: Date.now(), date: isoLocal(new Date()).slice(0, 10), dev: 'Ноутбук', radar: h });
      const facts = await mornFacts(); const news = mornFacts.radar;
      newsCard(news); const card = document.querySelector('#card .rd-news');
      const txt = card ? card.innerText : ''; document.querySelector('#rd-news-go').click();
      return { facts, news, txt, opened };
    }""", h)
    b.close()
ok(any("Радар" in f and "FAA" in f for f in out["facts"]), f"телефон: в сводке дня — новость из Радара: {[f[:60] for f in out['facts']]}")
ok("FAA" in out["txt"] and "Читать" in out["txt"], f"под сводкой — карточка с заголовком и «Читать»: {out['txt']!r}")
ok(out["opened"] == ["https://x/2"], f"«Читать» открывает материал целиком: {out['opened']}")
ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
