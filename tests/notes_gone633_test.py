"""№633 (ПК 0.84.2, 09.11): «раздел „Заметки“. Удалённая заметка не пропадает из списка заметок». По журналу: Лира по
просьбе «лишнюю заметку убери» удалила её инструментом delete_files (в корзину), а открытый список «Заметок» не узнал —
карточка осталась, щелчок по ней — «файла нет». Теперь: после инструментов, что меняют «Заметки», ядро шлёт notes_changed
(список освежается сам), а карточка удалённой мимо студии заметки по щелчку убирается из списка без «файла нет»."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from engine_tools import ToolsMixin, NOTE_TOOLS  # noqa: E402
from engine_base import Turn  # noqa: E402


class Box:
    def policy(self, n):
        return True, False

    def title(self, n):
        return n

    def guard(self, n, a):
        return None, False, None

    def auto_ok(self, n, a):
        return True

    def describe(self, n, a):
        return ""

    def run(self, n, a):
        return "Перемещено в корзину: x.md. Восстановить можно из корзины."


class E(ToolsMixin):
    def __init__(self):
        self.pending_confirm, self.events, self.follow_up_until, self.history, self.last_turn_time = None, [], 0, [], 0.0
        self.toolbox = Box()

    def emit(self, k, **d):
        self.events.append((k, d))

    def set_state(self, s):
        pass


ok({"delete_files", "save_note", "update_note"} <= NOTE_TOOLS, f"инструменты, меняющие «Заметки»: {sorted(NOTE_TOOLS)}")
e = E()
t = Turn(1); t.asked = "А лишнюю заметку-то убери"
e._use_tool(t, {"name": "delete_files", "args": {"paths": ["Заметки/x.md"]}}, None)
ok(any(k == "notes_changed" for k, _ in e.events), f"удалила заметку — студии notes_changed: {[k for k, _ in e.events]}")
e.events = []
e._use_tool(t, {"name": "weather", "args": {}}, None)
ok(not any(k == "notes_changed" for k, _ in e.events), "погода — список заметок не трогаем")

NOTES = [{"path": "Заметки/СПИСОК ДЕЛ.md", "title": "СПИСОК ДЕЛ", "mtime": 3, "size": 9, "folder": "", "snippet": "дела", "att": 0, "img": "",
          "tags": [], "color": "", "source": "", "pinned": True, "archived": False, "locked": False},
         {"path": "Заметки/Лишняя.md", "title": "Лишняя", "mtime": 2, "size": 9, "folder": "", "snippet": "лишняя", "att": 0, "img": "",
          "tags": [], "color": "", "source": "", "pinned": False, "archived": False, "locked": False}]
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1300, "height": 860}); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""(notes) => { window._notes = notes; core.call = (c, a) => {
        if (c === 'notes_list') return Promise.resolve(_notes.slice());
        if (c === 'ws_read') { if (!_notes.some(n => n.path === a.path)) return Promise.reject(new Error('файла нет'));
          return Promise.resolve({ path: a.path, text: '# ' + a.path.slice(8, -3) + '\\n\\nтекст', mtime: 1 }); }
        return Promise.resolve({}); };
      $('nav button[data-p="notes"]').click(); }""", NOTES)
    pg.wait_for_timeout(700)
    rows = lambda: pg.evaluate("() => [...document.querySelectorAll('#nt-list .nt-row b')].map(x => x.textContent)")
    ok(rows() == ["СПИСОК ДЕЛ", "Лишняя"], f"две заметки в списке: {rows()}")
    # Лира удалила «Лишнюю» — ядро сообщает notes_changed
    pg.evaluate("() => { _notes = _notes.filter(n => n.title !== 'Лишняя'); (core.handlers['notes_changed'] || []).forEach(f => f({})); }")
    pg.wait_for_timeout(800)
    live = rows()
    # щелчок по устаревшей карточке (если событие не дошло) — убирается без «файла нет»
    pg.evaluate("""() => { _notes.push({ path: 'Заметки/Призрак.md', title: 'Призрак', mtime: 1, size: 1, folder: '', snippet: '', att: 0, img: '', tags: [],
        color: '', source: '', pinned: false, archived: false, locked: false }); return ntLoad(); }""")
    pg.wait_for_timeout(400)
    pg.evaluate("() => { _notes = _notes.filter(n => n.title !== 'Призрак'); }")
    pg.click('#nt-list .nt-row[data-p="Заметки/Призрак.md"]'); pg.wait_for_timeout(800)
    toast = pg.evaluate("() => [...document.querySelectorAll('.toast, #toast')].map(x => x.textContent).join(' | ')")
    ok("Призрак" not in rows() and "файла нет" not in toast, f"щелчок по удалённой заметке — карточка ушла, без «файла нет»: {rows()} / {toast}")
    b.close()
src = (ROOT / "ui/studio/notes.js").read_text(encoding="utf-8")
ok('core.on("notes_changed"' in src, "студия слушает notes_changed")
ok(live == ["СПИСОК ДЕЛ"], f"после notes_changed удалённой нет: {live}")
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
