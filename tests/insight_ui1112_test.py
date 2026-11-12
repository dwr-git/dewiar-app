"""«Радар» в студии (12.11): все вкладки рисуются по настоящим данным ядра (engine_insight на подменном движке),
без ошибок страницы, на русском и английском — без сырых ключей словаря; пустой Радар — приглашение добавить источники."""

import json, os, random, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


LANG = "ru"
sys.path.insert(0, str(ROOT / "core"))
import insight as I, engine_insight as EI
random.seed(7)
tmp = Path(tempfile.mkdtemp())
TOP = [("Утечка исходников движка PHP: в сеть попали ключи сборки", ["php", "безопасность", "утечки"], ["PHP"], 9.4, "incident"),
       ("Глитч напряжения превращает майнинговую CMP 170HX в A100 80GB", ["gpu-инфраструктура", "железо"], ["NVIDIA"], 8.7, "research"),
       ("Google выпустила Gemini 4 Carbon: агентная модель в 2–6 раз дешевле", ["ии-агенты", "llm"], ["Google", "Gemini"], 8.2, "release"),
       ("warmctl сокращает холодный старт vLLM с 30 минут до 30 секунд", ["llm", "devops"], ["vLLM"], 7.6, "practice"),
       ("Московская биржа автоматизировала ночную диагностику с LLM", ["ии-агенты", "devops"], ["MOEX"], 7.1, "practice"),
       ("Dart 3.14: автоматизация миграций, JS interop и Wasm", ["dart", "webassembly"], ["Dart"], 6.9, "release"),
       ("Supabase открыл бесплатный тариф для векторного поиска", ["базы данных", "llm"], ["Supabase"], 6.2, "release"),
       ("Нейромаркеры в текстах: водяные знаки и влияние на SEO", ["seo", "llm"], [], 6.0, "analysis"),
       ("Claude Opus 5.5 обошёл людей в задачах на код по длинному контексту", ["ии-агенты", "llm"], ["Claude", "Anthropic"], 7.8, "news"),
       ("CVE в curl: переполнение при разборе заголовков прокси", ["безопасность", "linux"], ["curl"], 8.1, "incident")]
TAGS = ["php", "безопасность", "llm", "ии-агенты", "devops", "linux", "gpu-инфраструктура", "seo", "базы данных", "open-source", "dart", "маркетинг"]
ENT = ["Claude", "NVIDIA", "Google", "PHP", "Docker", "PostgreSQL", "Go", "Obsidian", "curl", "Supabase"]
now = time.time()
st = I.Store(tmp / "s")
st.add_sources("https://habr.com/ru/rss/all/all/ https://www.youtube.com/@lexfridman @ai_newz https://github.com/ollama/ollama https://vc.ru/ai")
srcs = st.sources()
items = []
for i in range(260):
    age = random.random() ** 1.3 * 7 * 86400
    t = TOP[i] if i < len(TOP) else None
    s = t[3] if t else round(min(9, max(0.5, random.gauss(5, 1.6))), 1)
    tg = t[1] if t else random.sample(TAGS, k=random.randint(2, 3))
    if t: age = random.random() * 20 * 3600
    src = srcs[i % len(srcs)]
    items.append({"id": f"i{i:03d}", "src": src["id"], "src_name": src["name"], "kind": src["kind"],
                  "title": t[0] if t else f"Материал {i}: " + " и ".join(tg), "url": f"https://example.com/{i}", "ts": int(now - age), "seen": int(now - age),
                  "text": "", "a": {"summary": "Суть материала: что произошло и ключевые цифры." if not t else t[0] + " — подробности и цифры из статьи.",
                                    "why": "Для специалиста важно учесть это в ближайших релизах.", "type": t[4] if t else random.choice(I.TYPES),
                                    "tags": tg, "entities": t[2] if t else random.sample(ENT, 1), "signal": s}})
st.save("items", items)
st.save("brief", {"headline": "Разблокировка GPU-железа и новые LLM-агенты меняют экономику HPC и DevOps",
                  "points": ["Утечка исходников PHP: в сеть попали ключи сборки — срочно проверьте зависимости.",
                             "warmctl сокращает холодный старт vLLM с 30 минут до 30 секунд через CRIU.",
                             "Gemini 4 Carbon: агентная модель в 2–6 раз дешевле конкурентов, с режимом /swarm.",
                             "Московская биржа автоматизировала ночную диагностику production с LLM.",
                             "Модель «база плюс пики» снижает затраты на GPU-инфраструктуру до 70%."],
                  "main": [{"id": "i000", "why": "Ключи сборки в открытом доступе — подменённые пакеты возможны уже на этой неделе. Обновите PHP и проверьте подписи."},
                           {"id": "i001", "why": "Дешёвые майнинговые карты становятся заменой A100: стоимость своих серверов для ИИ может упасть вдвое."}],
                  "at": int(now - 2 * 3600), "n": 47, "day": time.strftime("%Y-%m-%d")})
st.save("mind", {"v": 3, "theses": [{"text": "Атаки на цепочку поставок сместились к движкам языков: PHP, curl — за одну неделю.", "refs": ["i000", "i009"]},
                                   {"text": "Стоимость вывода моделей падает быстрее, чем растёт спрос: выигрывают агентные сценарии.", "refs": ["i002", "i003"]}],
                 "hyps": [{"id": "h1", "text": "До конца месяца выйдет внеплановый патч PHP 8.4", "due": "2026-11-30", "state": "open"},
                          {"id": "h2", "text": "NVIDIA ограничит прошивки CMP после публикации глитча", "due": "2026-12-15", "state": "open"},
                          {"id": "h0", "text": "Google снизит цены на Gemini для агентов", "due": "2026-11-10", "state": "confirmed"}],
                 "diary": [{"v": 1, "at": int(now - 3 * 86400), "theses": 2, "new_hyps": 2, "closed": 0}, {"v": 2, "at": int(now - 2 * 86400), "theses": 2, "new_hyps": 1, "closed": 1},
                           {"v": 3, "at": int(now - 86400), "theses": 2, "new_hyps": 0, "closed": 0}]})
st.save("log", {"last_tick": int(now - 3 * 3600), "days": {time.strftime("%Y-%m-%d"): 47},
                "ticks": [{"at": int(now - k * 1200), "profile": "day" if k < 8 else "night", "new": k % 3, "done": (k * 7) % 5, "dur": (k * 13) % 50} for k in range(1, 12)]})
for s in srcs[:3]:
    st.update_source(s["id"], last=int(now - 3 * 3600))
st.update_source(srcs[4]["id"], err="403 Forbidden")
st.update_source(srcs[3]["id"], on=False)
class S:
    d = {"insight": {"mission": "Веб-разработка, ИИ и безопасность"}, "ui": {"lang": LANG}}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]
    def active_llm(self): return {}
eng = types.SimpleNamespace(s=S(), emit=lambda *a, **k: None, push=lambda *a, **k: None)
eng.insight = EI.Radar(eng, tmp / "s")
eng.insight._ask = lambda system, user, max_tokens=700: "Главное за неделю — утечка исходников PHP [1] и дешёвые GPU [2]."
R = {"insight_question": EI.command(eng, "insight_question", {"q": "Что главное за неделю?"})}
R.update({c: EI.command(eng, c, {}) for c in ("insight_pulse", "insight_feed", "insight_trends", "insight_sources", "insight_mind", "insight_galaxy", "insight_control")})
from playwright.sync_api import sync_playwright
EMPTY = {"insight_pulse": {"stats": dict(R["insight_pulse"]["stats"], sources_all=0, sources=0), "brief": None, "field": [], "trends": [], "week": 0, "mission": ""}}


def run(lang, data):
    core = """(() => { const R = %s; const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true; core.call = async (c, a) => (c in R ? R[c] : null); }; ready(); })();""" % json.dumps(data, ensure_ascii=False)
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        pg = b.new_page(viewport={"width": 1400, "height": 950})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(core)
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?port=1&lang={lang}"); pg.wait_for_timeout(900)
        pg.evaluate("window.dwSetLang && dwSetLang('%s')" % lang)
        pg.evaluate("typeof loadHome === 'function' && loadHome()"); pg.wait_for_timeout(500)
        out["home"] = pg.evaluate("(document.querySelector('#hm-today .hm-card.radar') || {}).innerText || ''")
        pg.evaluate("document.querySelector('nav button[data-p=insight]').click()"); pg.wait_for_timeout(700)
        for t in ("pulse", "feed", "trends", "sources", "mind", "galaxy", "control"):
            pg.evaluate(f"document.querySelector('#rd-tabs button[data-t={t}]').click()"); pg.wait_for_timeout(500)
            out[t] = pg.evaluate(f"document.querySelector('#rd-{t}').innerText")
        pg.evaluate("document.querySelector('#rd-tabs button[data-t=pulse]').click()"); pg.wait_for_timeout(500)
        pg.evaluate("document.querySelector('.rd-sg') && document.querySelector('.rd-sg').click()"); pg.wait_for_timeout(500)
        out["ans"] = pg.evaluate("(document.querySelector('#rd-ans') || {}).innerText || ''")
        out["refs"] = pg.evaluate("document.querySelectorAll('#rd-ans .rd-ref').length")
        out["askbar"] = pg.evaluate("!!document.querySelector('form.rd-ask')")
        out["head"] = pg.evaluate("document.querySelector('#rd-room').innerText")
        out["errs"] = [e for e in errs if "insight" in e]
        b.close()
    return out


for lang in ("ru", "en"):
    o = run(lang, R)
    ok(not o["errs"], f"{lang}: страница без ошибок: {o['errs'][:2]}")
    raw = [t for t, v in o.items() if isinstance(v, str) and "insight." in v]
    ok(not raw, f"{lang}: нет сырых ключей словаря (вкладки {raw})")
    ok(all(o[t].strip() for t in ("pulse", "feed", "trends", "sources", "mind", "galaxy", "control")), f"{lang}: каждая вкладка нарисована")
    ok(("Утечка исходников движка PHP" in o["feed"]) and ("habr.com" in o["sources"]), f"{lang}: лента и источники — из данных ядра")
ru, en = run("ru", R), run("en", R)
ok("Поле сигналов" in ru["pulse"] and "Signal field" in en["pulse"] and "Галактика" in ru["head"] and "Galaxy" in en["head"], "русский и английский — свои подписи")
ok("Радар · бриф дня" in ru["home"] and "Разблокировка GPU" in ru["home"] and "⚡ 9,4" in ru["home"], f"«Главная»: бриф дня и сильный сигнал: {ru['home']!r}")
ok("Radar · daily brief" in en["home"] and "⚡ 9.4" in en["home"], f"Home in English: {en['home']!r}")
ok("Главное за неделю" in ru["ans"] and ru["refs"] == 2 and ru["ans"].count("Материал") + ru["ans"].count("Утечка") >= 2 and not ru["askbar"],
   f"«Спросите Лиру о теме»: готовый вопрос — ответ здесь же, ссылки на материалы; старой строки внизу нет: {ru['ans'][:120]!r}")
ok("Continue in chat" in en["ans"], "ответ и по-английски — с переходом в чат")
e = run("ru", EMPTY)
ok(not e["home"], "источников нет — карточки Радара на «Главной» нет")
ok("Радар пока пуст" in e["pulse"] and "Добавить источники" in e["pulse"], f"пустой Радар — приглашение добавить источники: {e['pulse'][:80]!r}")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
