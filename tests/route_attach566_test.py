"""№566 (ПК 0.84.2, Linux, 05.11): «прикрепил .md файл с задачей. Высвечивается, что диалог ведётся с Лирой, а отвечает Ирис».
По журналу: «👥 Лира передаёт вопрос: Ирис» — в тексте ПРИЛОЖЕННОГО файла (большой промпт) нашлось слово «книгу», и вопрос
ушёл библиотекарю Ирис. Теперь специалиста выбираем только по словам самого человека: без «Вложений» и не по длинной
вставке (документ, промпт). На снимке ещё и студия во всё окно с «кракозябрами»: файл бросили мимо поля приёма — окно
открыло его вместо себя. Теперь в «Чате» такой файл идёт во вложения, в других местах окно его не открывает."""
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


from engine_tools import ToolsMixin  # noqa: E402
from personas import BUILTIN, GALLERY  # noqa: E402

LIB = next(p for p in GALLERY.values() if p.get("name") == "Ирис")


class P:
    def __init__(self):
        self.l = [dict(BUILTIN["lira"], id="lira"), dict(LIB, id="iris")]

    def get(self, pid):
        return next(p for p in self.l if p["id"] == pid)

    def all(self):
        return self.l


class St:
    def get(self, a, b=None):
        return "lira" if b is None else True


class E(ToolsMixin):
    def __init__(self):
        self.personas, self.s = P(), St()


e = E()
ok(e._route("Перескажи книгу «Мастер и Маргарита»") == "iris", "короткая просьба про книгу — Ирис (как раньше)")
prompt = ("Роль:\nТы - мастер Prompt-инжиниринга, эксперт.\n\nКонтекст:\nВ сфере ИИ важно уметь писать промпты.\n\n"
          "ЗАДАЧА:\nПомоги мне создать mega-prompt под мою цель.\n\nКак мы работаем:\n1. Ты задаёшь вопросы.\n2. Я отвечаю.\n"
          "3. Пример: промпт, который пишет книгу за вечер.\n" + "Подробности формата и ограничений. " * 20)
ok(e._route(prompt) is None, "вставили длинный промпт со словом «книгу» — отвечает Лира, не Ирис")
att = ("Посмотри вложения и коротко скажи, что в них.\n\nВложения:\n[Файл «01 - мастер Prompt-инжиниринга.md», сохранён в папке "
       "ассистента: Входящие/01.md]\n" + prompt)
ok(e._route(att) is None, "приложенный .md со словом «книгу» — отвечает Лира, не Ирис")
ok(e._route("Перескажи эту книгу\n\nВложения:\n[Файл «book.pdf»]\nтекст") == "iris", "«перескажи эту книгу» с файлом — по словам человека — Ирис")

errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1300, "height": 860}); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    drop = """(sel) => { const dt = new DataTransfer(); dt.items.add(new File(['# задача'], 'задача.md', { type: 'text/markdown' }));
      const el = document.querySelector(sel) || document.body;
      const o = new DragEvent('dragover', { dataTransfer: dt, bubbles: true, cancelable: true }); el.dispatchEvent(o);
      const d = new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }); el.dispatchEvent(d);
      return [o.defaultPrevented, d.defaultPrevented, (window._got || []).map(f => f.name)]; }"""
    pg.evaluate("() => { window._got = []; window.chatAddFiles = (l) => { _got.push(...l); }; $('nav button[data-p=\"home\"]').click(); }")
    pg.wait_for_timeout(300)
    r = pg.evaluate(drop, "#p-home")
    ok(r[0] and r[1] and r[2] == [], f"файл мимо поля на «Главной» — окно его не открывает: {r}")
    pg.evaluate("() => { _got = []; $('nav button[data-p=\"chat\"]').click(); }"); pg.wait_for_timeout(400)
    r = pg.evaluate(drop, ".ch-list, #ch-list, #p-chat h1, #p-chat")
    ok(r[1] and r[2] == ["задача.md"], f"в «Чате» файл, брошенный куда угодно, — во вложения: {r}")
    b.close()
    # прочие окна — последний рубеж в общем dewiar.js
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1"); pg.wait_for_timeout(600)
    pg.set_content("<html><body><p>окно</p></body></html>")
    pg.add_script_tag(path=str(ROOT / "ui/assets/dewiar.js"))
    r = pg.evaluate(drop, "p")
    ok(r[0] and r[1], f"любое окно Dewiar: брошенный мимо файл не открывается вместо окна: {r}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
