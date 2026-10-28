"""Студия: своя память у персонажа (0.56). «Персонажи» → «Изменить» → «Память»: «Общая» / «Своя» (persona_memory
{name, own}); на карточке — «🗂 своя память». «Обо мне» → вкладки «Общая» и «Патрик» (memory_view {who}) — у каждой свои
факты; добавить и забыть — в выбранную."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""() => { window._calls = []; window._own = [];
      const view = (who) => ({ total: 1, core: 1, fits: true, own: _own, who, pages: [{ key: 'me', group: 'me', icon: '🙂', title: 'О вас', facts: [{ i: 0, text: who ? 'Готовится к марафону' : 'Любит зелёный чай', core: true }] }] });
      core.call = (c, a) => { a = a || {}; _calls.push([c, a]);
        if (c === 'persona_memory') { _own = a.own ? [a.name] : []; return Promise.resolve({ own: _own }); }
        if (c === 'memory_view') return Promise.resolve(view(a.who || ''));
        if (c === 'memory_get') return Promise.resolve((a.who ? '- Готовится к марафону' : '- Любит зелёный чай'));
        if (c === 'knowledge_list') return Promise.resolve({ files: [] });
        if (c === 'knowledge_folders' || c === 'exam_traces' || c === 'gallery') return Promise.resolve([]);
        return Promise.resolve(true); };
      S = Object.assign(S || {}, { persona_memory: { own: [] }, llm: { profiles: {}, persona: {} } });
      const v = { piper: 'ru', length_scale: 1, fx: 'clear' };
      personas = [{ id: 'lira', name: 'Лира', color: '#8b7bff', style: 'aura', skills: [], voice: v }, { id: 'patrik', name: 'Патрик', color: '#4fc3ff', style: 'aura', skills: [], voice: v }];
      S_voices = S_voices || { ru: 'Ирина' }; S_fx = S_fx || []; vkSpeakers = vkSpeakers || [];
      active = 'lira'; document.querySelector('nav button[data-p=personas]').click(); }""")
    pg.wait_for_timeout(600)
    pg.evaluate("() => openEditor(personas[1])"); pg.wait_for_timeout(500)
    r = pg.evaluate("() => [...document.querySelectorAll('#e-mem .bp')].map(x => [x.querySelector('b').textContent, x.classList.contains('on')])")
    ok(r == [["Общая", True], ["Своя", False]], f"редактор: «Память» — «Общая» выбрана: {r}")
    pg.click("#e-mem [data-m='1']"); pg.wait_for_timeout(300)
    ok(["persona_memory", {"name": "Патрик", "own": True}] in pg.evaluate("_calls") and pg.evaluate("document.querySelector('#e-mem [data-m=\"1\"]').classList.contains('on')"),
       "«Своя» — persona_memory, выбрана")
    ok("Патрик теперь помнит своё" in pg.inner_text("#toast"), "сказано, где смотреть")
    pg.evaluate("() => closeEditor()"); pg.wait_for_timeout(200)
    ok("своя память" in pg.inner_text("#pgrid"), "на карточке Патрика — «🗂 своя память»")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-persona-memory.png"))
    pg.evaluate("() => document.querySelector('nav button[data-p=me]').click()"); pg.wait_for_timeout(300)
    pg.evaluate("() => mpxLoad()"); pg.wait_for_timeout(500)
    tabs = pg.evaluate("() => [...document.querySelectorAll('#mpx-who button')].map(x => [x.textContent, x.classList.contains('on')])")
    ok(tabs == [["Общая", True], ["Патрик", False]] and not pg.evaluate("document.querySelector('#mpx-who').hidden"), f"«Обо мне» — вкладки «Общая» и «Патрик»: {tabs}")
    ok("Любит зелёный чай" in pg.inner_text("#mpx-card"), "«Общая» — общие факты")
    pg.click("#mpx-who button[data-w='Патрик']"); pg.wait_for_timeout(500)
    ok("Готовится к марафону" in pg.inner_text("#mpx-card") and ["memory_view", {"who": "Патрик"}] in pg.evaluate("_calls"), "«Патрик» — его факты")
    pg.fill("#mpx-new", "Бегает по утрам"); pg.click("#mpx-addgo"); pg.wait_for_timeout(300)
    ok(["memory_add", {"text": "Бегает по утрам", "who": "Патрик"}] in pg.evaluate("_calls"), "«Запомнить» на вкладке Патрика — в его память")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
