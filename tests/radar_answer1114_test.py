"""Владелец 14.11 (снимок Радара): «ответ по основным трендам весь такой неструктурированный, как каша, нужно сделать
более красиво, иначе сложно читать». Ответ «Спросите Лиру о теме» теперь: главное одним предложением (крупно), пункты
«тема — суть [n]», «→ что сделать первым» отдельной плашкой. Модель ответила сплошным абзацем — делим сами."""
import json, os, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import insight as I, engine_insight as EI  # noqa: E402
sysp, _ = I.question_prompt("что главное?", {"items": []}, "", "ru")
ok("главное одним коротким предложением" in sysp and "«• »" in sysp and "«→ »" in sysp, "модель просят: главное, пункты, что сделать")
MUSH = ("Самым значимым событием является расширение FAA применения ИИ-системы для управления воздушным движением по всему США, "
        "что демонстрирует масштабное внедрение технологий в критическую инфраструктуру [1]. В сфере безопасности выявлен новый вектор "
        "атак: вредоносный код, спрятанный в ZIP-архивах с предложениями о работе [2]. Параллельно растёт зрелость агентных интерфейсов: "
        "тестирование Figma AI показало, что агенты справляются с задачами по дизайн-системам [3]. Для локальной инфраструктуры "
        "актуальны скрытые инженерные издержки при создании домашних суперкомпьютеров [4].")
txt = I.structure_answer(MUSH)
ok(txt.count("\n• ") == 3 and txt.startswith("Самым значимым событием"), f"сплошной абзац — главное и пункты: {txt[:160]!r}")
ok(I.structure_answer("Коротко: всё спокойно [1].") == "Коротко: всё спокойно [1].", "короткий ответ не трогаем")
GOOD = "ИИ уходит в критическую инфраструктуру.\n• FAA — ИИ управляет воздушным движением [1]\n• Безопасность — вредонос в ZIP с вакансиями [2]\n→ Проверьте, кто в команде открывает такие архивы."
ok(I.structure_answer(GOOD) == GOOD, "ответ уже по формату — как есть")

tmp = Path(tempfile.mkdtemp()); now = time.time()
st = I.Store(tmp / "s")
st.add_sources("https://habr.com/ru/rss/all/all/ @ai_newz")
src = st.sources()[0]
st.save("items", [{"id": f"i{i}", "src": src["id"], "src_name": src["name"], "kind": src["kind"], "title": f"Материал {i}", "url": f"https://example.com/{i}",
                   "ts": int(now - i * 3600), "seen": int(now - i * 3600), "text": "",
                   "a": {"summary": "суть", "why": "", "type": "news", "tags": ["ии"], "entities": [], "signal": 8 - i * .5}} for i in range(5)])


class S:
    d = {"insight": {"mission": "ИИ"}, "ui": {"lang": "ru"}}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]
    def active_llm(self): return {}


eng = types.SimpleNamespace(s=S(), emit=lambda *a, **k: None, push=lambda *a, **k: None)
eng.insight = EI.Radar(eng, tmp / "s")
eng.insight._ask = lambda system, user, max_tokens=700: MUSH + "\n→ Проверьте, кто в команде открывает архивы с вакансиями."
R = {"insight_question": EI.command(eng, "insight_question", {"q": "Подготовь мне самое главное"})}
R.update({c: EI.command(eng, c, {}) for c in ("insight_pulse", "insight_feed", "insight_trends", "insight_sources", "insight_control")})
from playwright.sync_api import sync_playwright  # noqa: E402
core = """(() => { const R = %s; const ready = () => { if (!window.core) return setTimeout(ready, 5);
core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
core.connected = true; core.call = async (c, a) => (c in R ? R[c] : null); }; ready(); })();""" % json.dumps(R, ensure_ascii=False)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=1)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(core)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&lang=ru"); pg.wait_for_timeout(900)
    pg.evaluate("document.querySelector('nav button[data-p=insight]').click()"); pg.wait_for_timeout(700)
    pg.evaluate("document.querySelector('.rd-sg') && document.querySelector('.rd-sg').click()"); pg.wait_for_timeout(600)
    r = pg.evaluate("""() => ({ lead: (document.querySelector('#rd-ans .rd-alead') || {}).innerText || '',
      li: [...document.querySelectorAll('#rd-ans .rd-alist li')].map(x => x.innerText),
      next: (document.querySelector('#rd-ans .rd-anext') || {}).innerText || '', refs: document.querySelectorAll('#rd-ans .rd-ref').length })""")
    if os.environ.get("SHOT"):
        pg.locator("#rd-ans").screenshot(path=os.environ["SHOT"])
    b.close()
ok(r["lead"].startswith("Самым значимым событием"), f"главное — первой строкой, крупно: {r['lead'][:60]!r}")
ok(len(r["li"]) == 3, f"остальное — пунктами: {len(r['li'])}")
ok("Проверьте" in r["next"], f"«что сделать» — отдельной плашкой: {r['next']!r}")
ok(r["refs"] >= 3, f"ссылки на материалы — на месте: {r['refs']}")
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
