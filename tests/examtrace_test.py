"""Следы экзамена в данных человека (16.10: в «Обо мне» у владельца — «Бюджет Миши на мебель… менялось 13 раз»,
«Дни рождения близких Миши: Аня, Петя, мама» — проверочные фразы экзамена; причина — exam_isolation_test).
Проверяем: похожее на фразы экзамена находится, настоящее — нет; убирается только отмеченное; студия показывает
карточку в «Обо мне» со списком по видам, «Убрать отмеченное» и «Оставить»."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import examtrace as X  # noqa: E402

EXAM = ["Бюджет Миши на мебель для гостиной — 65 000, хочет диван получше (раньше: 50 000 → 70 000 → 65 000; менялось 13 раз). _(16.10.2026)_",
        "Дни рождения близких Миши: Аня — 24 ноября, Петя — 24 октября, мама — 29 декабря (раньше: Аня — 20 ноября; менялось 2 раза). _(15.10.2026)_",
        "Со слов пользователя: в среду в 15:00 у меня встреча с подрядчиком по кухне (на 21.10.2026, среда).",
        "На работе три дела: сдать отчёт по продажам в пятницу, нанять дизайнера, обновить сайт; начальник просил презентацию для инвесторов"]
MINE = ["Жена Миши — Людмила Исаева (в контактах и близких). _(11.10.2026)_",
        "Мишу называют «Малых» (не «немалых» и не «волыха»); Лира не должна отвлекаться на это имя, отвечать по делу _(13.10.2026)_",
        "День рождения жены — 5 марта", "Мама любит розы, день рождения у мамы в мае", "Работаю бухгалтером, начало дня в 9:00",
        "Сын Петя учится в 5 классе", "Любит зелёный чай", "Купить продукты 450 рублей"]
sets = X._phrases()
ok(all(X.like(t, sets) for t in EXAM), f"записи экзамена узнаются: {[t[:30] for t in EXAM if not X.like(t, sets)]}")
ok(not any(X.like(t, sets) for t in MINE), f"настоящие записи — нет: {[t[:30] for t in MINE if X.like(t, sets)]}")


class WS:
    def __init__(self):
        self.mem = "\n".join("- " + x for x in EXAM[:2] + MINE[:2])
        self.gone = []

    def memory_get(self, who=None): return self.mem
    def memory_set(self, body, who=None): self.mem = body; return True
    def notes(self, limit=400):
        return [{"path": "Заметки/Список покупок.md", "title": "Список покупок", "snippet": "молоко, хлеб, яйца"},
                {"path": "Заметки/Рецепт борща.md", "title": "Рецепт борща", "snippet": "свёкла, капуста, говядина"}]
    def remove(self, rel): self.gone.append(rel)


class Money:
    def __init__(self): self.items = [{"id": "m1", "amount": 1200, "currency": "BYN", "category": "Мебель", "note": "диван", "date": "2026-10-10"}]
    def list(self): return self.items
    def delete(self, iid): self.items = [x for x in self.items if x["id"] != iid]


class Done:
    def __init__(self): self.items = [{"id": "d1", "title": "Позвонить маме"}]
    def delete(self, iid): self.items = [x for x in self.items if x["id"] != iid]


ws, mo, dn = WS(), Money(), Done()
found = X.find(ws, mo, dn)
kinds = sorted((x["kind"], x["text"][:14]) for x in found)
ok([k for k, _ in kinds].count("memory") == 2 and ("note", "Список покупок") in kinds and not any(k in ("money", "done") for k, _ in kinds),
   f"нашлись две строки памяти и заметка экзамена; расход и сделанное человека — нет: {kinds}")
keep_one = [x for x in found if x["kind"] == "memory"][:1] + [x for x in found if x["kind"] == "note"]
n = X.remove(ws, mo, dn, keep_one)
ok(n == 2 and ws.gone == ["Заметки/Список покупок.md"] and EXAM[0][:20] not in ws.mem and EXAM[1][:20] in ws.mem and MINE[0][:12] in ws.mem,
   f"убрано только отмеченное (строка памяти — целиком, заметка — в корзину): {n}, {ws.gone}")

# ---------- студия ----------
from playwright.sync_api import sync_playwright  # noqa: E402
ITEMS = [{"kind": "memory", "id": "- " + EXAM[0], "text": EXAM[0][:60]}, {"kind": "memory", "id": "- " + EXAM[1], "text": EXAM[1][:60]},
         {"kind": "note", "id": "Заметки/Список покупок.md", "text": "Список покупок"}]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1360, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    r = pg.evaluate("""async (items) => { window._calls = []; S = Object.assign(S || {}, { ui: {} });
        core.call = (c, a) => { _calls.push([c, a]);
          if (c === 'exam_traces') return Promise.resolve(window._left || items);
          if (c === 'exam_traces_remove') { window._left = items.filter(x => !a.items.some(y => y.id === x.id)); return Promise.resolve({ removed: a.items.length }); }
          if (c === 'memory_get') return Promise.resolve('- Любит зелёный чай');
          if (c === 'settings_save') return Promise.resolve(Object.assign({}, S, { ui: Object.assign({}, S.ui, a.patch.ui) }));
          if (c === 'knowledge_list') return Promise.resolve({ files: [] }); if (c === 'knowledge_folders') return Promise.resolve([]);
          return Promise.resolve({}); };
        loadMe(); await new Promise(r => setTimeout(r, 300));
        const shown = [!$('#me-exam').hidden, [...$$('#me-exam-list h4')].map(x => x.textContent), $$('#me-exam-list input:checked').length];
        $$('#me-exam-list input')[1].click();                          // вторую строку человек решил оставить
        $('#me-exam-go').click(); await new Promise(r => setTimeout(r, 300));
        const rm = _calls.filter(c => c[0] === 'exam_traces_remove').map(c => c[1].items.map(x => x.kind));
        const left = [!$('#me-exam').hidden, $$('#me-exam-list input').length];
        $('#me-exam-keep').click(); await new Promise(r => setTimeout(r, 200));
        const kept = [$('#me-exam').hidden, (_calls.find(c => c[0] === 'settings_save') || [0, { patch: {} }])[1].patch.ui];
        S.ui = kept[1]; loadMe(); await new Promise(r => setTimeout(r, 300));
        return { shown, rm, left, kept: kept[0], keptSig: !!(kept[1] || {}).exam_clean, again: !$('#me-exam').hidden }; }""", ITEMS)
    ok(r["shown"] == [True, ["Память", "Заметки"], 3], f"студия: карточка «записи экзамена» — по видам, всё отмечено: {r['shown']}")
    ok(r["rm"] == [["memory", "note"]] and r["left"] == [True, 1], f"«Убрать отмеченное» — только отмеченное, оставленное видно: {r['rm']} {r['left']}")
    ok(r["kept"] and r["keptSig"] and not r["again"], "«Оставить» — карточка уходит и этот же набор больше не показывается")
    ok(not errs, f"студия без ошибок: {errs[:3]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
