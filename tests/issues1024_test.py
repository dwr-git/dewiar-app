"""GitHub dwr-git/dewiar-app, 24.10: семь ошибок из открытых issues — каждая теперь проверка.
- #15: «Остановить», а зависший запрос к модели потом упал ReadTimeout — повтор не назначается, задача остаётся остановленной;
- #14: проект без Git, один файл не прочитался при подготовке копии — «Принять» его не удаляет и не перезаписывает;
- #16: Git, неотслеживаемый «новый.py» (кириллица) попадает в рабочую копию с содержимым, changes() — настоящее имя;
- #12: две задачи с одним названием в одну минуту — разные папки; удаление одной не трогает другую;
- #17: «Пять букв» — после победы «Следующее слово» начинает новый раунд (итог не пересоздаётся каждый кадр);
- #18: студия — событие settings (ядро сменило модель) переносит отметку активного профиля в «Мозге»;
- #19: студия — поздний ответ календаря за другой месяц не затирает записи выбранного дня (оба порядка ответов)."""
import datetime as dt, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tasks as TK  # noqa: E402
import codework  # noqa: E402
import tools as T  # noqa: E402
from llm import LLMError  # noqa: E402
from workspace import Workspace  # noqa: E402


class FakeS:
    def get(self, *k): return {} if k[0] == "tools" else None


class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.toolbox = T.Toolbox(FakeS(), None); self.toolbox.hooks["workspace"] = self.workspace
        self.said, self.events = [], []
    def persona_name(self): return "Девиар"
    def memory(self): return ""
    def llm_profile(self): return {"name": "mock", "kind": "openai", "base_url": "http://127.0.0.1:9/v1", "model": "m"}
    def max_steps(self): return 30
    def code_auto_run(self): return False
    def confirm(self, q): return True
    def ask_user(self, t, q): pass
    def announce(self, text): self.said.append(text)
    def emit(self, *a, **k): self.events.append((a, k))


tm = TK.TaskManager(Host())


def wait(cond, sec=8):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


# ---------- #15: остановка во время зависшего запроса ----------
entered, gate = [], threading.Event()


def fake_stream(prof, system, msgs, cancel=None, tools=None, **k):
    entered.append(cancel.is_set() if cancel is not None else None)
    if len(entered) == 1:
        gate.wait(10)                                   # запрос «висит», пока человек не нажал «Остановить»
        raise LLMError("сервер модели не ответил вовремя (ReadTimeout)")
    yield "text", "вторая попытка — её быть не должно"


_se, _rm = TK.stream_events, TK.RETRY_MIN
TK.stream_events = fake_stream
TK.RETRY_MIN = (0, 0, 0, 0)                             # повтор сразу — планировщик (раз в 2 с) успел бы его запустить
try:
    t = tm.create("Зависший запрос", "Проверка остановки во время запроса")
    ok(wait(lambda: len(entered) == 1), "задача отправила запрос к модели, он висит")
    tm.stop(t.id)
    ok(t.status == "stopped", f"сразу после «Остановить» — stopped ({t.status})")
    gate.set()
    ok(wait(lambda: not (t.thread and t.thread.is_alive())), "поток задачи завершился после позднего ReadTimeout")
    time.sleep(4.5)                                     # два такта планировщика
    ok(t.status == "stopped" and not t.data.get("wake_at") and len(entered) == 1,
       f"#15: поздний сбой не назначил повтор: статус {t.status}, wake_at {t.data.get('wake_at')!r}, запросов {len(entered)}")
    ok("Остановлено" in (t.dir / "журнал.md").read_text(encoding="utf-8"), "в журнале — «Остановлено», а не «Попробую снова»")
    # контроль: без остановки временный сбой по-прежнему даёт повтор
    entered.clear(); gate.set(); TK.RETRY_MIN = (30,)
    t2 = tm.create("Сбой сети", "Повтор после временного сбоя")
    ok(wait(lambda: t2.status == "sleeping") and t2.data.get("retries") == 1 and t2.data.get("wake_at"),
       f"без остановки временный сбой — по-прежнему повтор позже ({t2.status}, попытка {t2.data.get('retries')})")
    tm.stop(t2.id)
finally:
    TK.stream_events, TK.RETRY_MIN = _se, _rm

# ---------- #12: одинаковые названия в одну минуту ----------
_real_dt = TK.dt


class FixedDT(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 24, 15, 7, 30)


TK.dt = type("dtmod", (), {"datetime": FixedDT, "timedelta": dt.timedelta, "date": dt.date})
try:
    a = tm.create("Same title", "Goal one", start=False)
    b = tm.create("Same title", "Goal two", start=False)
    c = tm.create("Same title", "Goal three", start=False)
finally:
    TK.dt = _real_dt
ok(len({a.dir, b.dir, c.dir}) == 3, f"#12: три задачи — три папки: {[x.dir.name for x in (a, b, c)]}")
ok(b.dir.name.endswith("(2)") and c.dir.name.endswith("(3)"), "вторая и третья — с суффиксом (2), (3)")
ok(json.loads((a.dir / "задача.json").read_text(encoding="utf-8"))["id"] == a.id and "Goal one" in (a.dir / "план.md").read_text(encoding="utf-8"),
   "состояние и план первой не перезаписаны второй")
tm.delete(b.id)
ok(a.dir.is_dir() and (a.dir / "задача.json").is_file() and c.dir.is_dir() and not b.dir.exists(), "удалили вторую — первая и третья на месте")
tm2 = TK.TaskManager(Host())
ok(a.id in tm2.tasks and c.id in tm2.tasks and b.id not in tm2.tasks, "после перезапуска программы — обе оставшиеся задачи читаются")

# ---------- #14: проект без Git, файл не прочитался при подготовке ----------
cd = Path(tempfile.mkdtemp()); P = cd / "p"; (P / "sub").mkdir(parents=True)
(P / "a.py").write_text("x = 1\n"); (P / "unreadable-once.txt").write_text("важное\n"); (P / "sub/half.bin").write_bytes(b"0123456789" * 100)
(P / "old.txt").write_text("удалить\n")
_cp, _ct, failed = shutil.copy2, shutil.copytree, set()


def flaky(src, dst, **k):
    name = Path(src).name
    if name == "unreadable-once.txt" and name not in failed:
        failed.add(name); raise PermissionError(13, "Permission denied", str(src))
    if name == "half.bin" and name not in failed:          # сбой посреди чтения: в копии остался обрывок
        failed.add(name); Path(dst).write_bytes(b"0123"); raise OSError(5, "Input/output error", str(src))
    return _cp(src, dst, **k)


shutil.copytree = lambda src, dst, *a, **k: _ct(src, dst, *a, **k) if a else _ct(src, dst, **dict(k, copy_function=flaky))   # вложенные папки copytree зовёт с позиционными
try:
    cw = codework.CodeWork(P, cd / "w"); cw.prepare()
finally:
    shutil.copytree = _ct
ok(failed == {"unreadable-once.txt", "half.bin"} and not (cd / "w/unreadable-once.txt").exists() and not (cd / "w/sub/half.bin").exists(),
   "сбой копирования двух файлов, обрывок из копии убран")
ok(sorted(cw.mode.get("skipped") or []) == ["sub/half.bin", "unreadable-once.txt"], f"нескопированные запомнены: {cw.mode.get('skipped')}")
ok(cw.changes() == [], f"#14: без правок изменений нет: {cw.changes()}")
cw.write("a.py", "x = 2\n"); cw.write("new.py", "y = 1\n"); cw.delete("old.txt")
cw.write("sub/half.bin", "модель записала поверх нечитанного")
ch = cw.changes()
ok(sorted(ch) == [("added", "new.py"), ("deleted", "old.txt"), ("modified", "a.py")], f"настоящие правки видны, нечитанные пути — нет: {ch}")
msg = cw.accept()
ok((P / "unreadable-once.txt").is_file() and (P / "unreadable-once.txt").read_text() == "важное\n" and (P / "sub/half.bin").read_bytes() == b"0123456789" * 100,
   "#14: после «Принять» нескопированные файлы на месте и целы")
ok((P / "a.py").read_text() == "x = 2\n" and (P / "new.py").is_file() and not (P / "old.txt").exists(), f"остальное перенесено: {msg}")
ok("остались как были" in msg, "человеку сказано, что нечитанные файлы не тронуты")

# ---------- #16: неотслеживаемые файлы с кириллицей (Git) ----------
G = Path(tempfile.mkdtemp()) / "repo"; G.mkdir()
genv = dict(os.environ, GIT_AUTHOR_NAME="u", GIT_AUTHOR_EMAIL="u@x", GIT_COMMITTER_NAME="u", GIT_COMMITTER_EMAIL="u@x")
g = lambda *a: subprocess.run(["git", "-C", str(G), "-c", "core.quotePath=true"] + list(a), capture_output=True, text=True, env=genv)
(G / "main.py").write_text("print(1)\n"); g("init", "-q"); g("add", "-A"); g("commit", "-qm", "init")
(G / "ascii.py").write_text("a = 1\n"); (G / "новый.py").write_text("б = 2\n"); (G / "папка").mkdir(); (G / "папка/файл с пробелом.txt").write_text("в\n")
cg = codework.CodeWork(G, G.parent / "work"); cg.prepare()
ok(cg.mode.get("mode") == "git", "рабочая копия — git worktree")
ok((G.parent / "work/ascii.py").read_text() == "a = 1\n" and (G.parent / "work/новый.py").is_file()
   and (G.parent / "work/новый.py").read_text(encoding="utf-8") == "б = 2\n"
   and (G.parent / "work/папка/файл с пробелом.txt").is_file() and (G.parent / "work/папка/файл с пробелом.txt").read_text(encoding="utf-8") == "в\n",
   "#16: неотслеживаемые с кириллицей и пробелом — в копии с содержимым")
ok(cg.changes() == [], f"без правок изменений нет: {cg.changes()}")
cg.write("новый.py", "б = 3\n"); cg.write("ещё.py", "г = 4\n")
ch = sorted(cg.changes())
ok(ch == [("added", "ещё.py"), ("modified", "новый.py")], f"changes() — настоящие имена, без C-кавычек: {ch}")
try:
    cg.accept()
except codework.CodeError as e:
    print("   accept:", e)
ok((G / "новый.py").read_text(encoding="utf-8") == "б = 3\n" and (G / "ещё.py").is_file() and (G / "ещё.py").read_text(encoding="utf-8") == "г = 4\n",
   "«Принять» переносит правки в проект")

# ---------- #17, #18, #19: игра и студия ----------
from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = []; window.PEND = [];
  window.OCT = { "2026-10-31": [{ type: "reminder", title: "Хэллоуин: купить тыкву", time: "12:00", id: "r1" }] };
  window.NOV = { "2026-11-01": [{ type: "reminder", title: "Ноябрьское дело", time: "10:00", id: "r2" }] };
  window.answer = (m) => { const i = PEND.findIndex(p => p.m === m); if (i < 0) return false;
    const p = PEND.splice(i, 1)[0]; p.res({ days: m === 10 ? OCT : m === 11 ? NOV : {}, currency: "BYN" }); return true; };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = (c, a) => { calls.push([c, a]);
      if (c === "calendar_month") return new Promise(res => PEND.push({ m: a.month, y: a.year, res }));
      if (c === "settings_save") return Promise.resolve(S);
      return Promise.resolve({}); }; };
  ready(); })();
"""
ARC = ROOT / "ui/assets/arcade"
with sync_playwright() as p:
    br = p.chromium.launch(); errs = []
    # «Пять букв»
    gp = br.new_page(viewport={"width": 420, "height": 860}); gp.on("pageerror", lambda e: errs.append(str(e)))
    gp.goto((ARC / "words/index.html").as_uri()); gp.wait_for_timeout(700); gp.click("#aGo"); gp.wait_for_timeout(400)
    def go():
        try:
            gp.click("#aGo", timeout=3000)                 # обычный клик мышью по кнопке
        except Exception as e:  # noqa: BLE001 — кнопку пересоздают каждый кадр: Playwright её не дождётся
            print("   клик:", str(e).splitlines()[0])
    TYPE = "w => { for (const ch of w) dispatchEvent(new KeyboardEvent('keydown', {key: ch})); dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'})); }"
    w1 = gp.evaluate("__words().word")
    gp.evaluate(TYPE, w1); gp.wait_for_timeout(3000)
    ok(gp.evaluate("__words().mode") == "over" and gp.is_visible("#aOverlay") and "Следующее слово" in gp.inner_text("#aOverlay"),
       "угадал слово — итог «Следующее слово»")
    swaps = gp.evaluate("""() => new Promise(r => { let n = 0; const o = new MutationObserver(() => n++);
      o.observe(document.getElementById('aOverlay'), { childList: true }); setTimeout(() => { o.disconnect(); r(n); }, 750); })""")
    ok(swaps == 0, f"#17: итог не пересоздаётся каждый кадр (замен за 750 мс: {swaps})")
    go(); gp.wait_for_timeout(300)
    st = gp.evaluate("(() => { const S = __words(); return { mode: S.mode, rows: S.rows.length, streak: S.streak, done: S.done }; })()")
    ok(st == {"mode": "play", "rows": 0, "streak": 1, "done": 0} and not gp.is_visible("#aOverlay"),
       f"#17: «Следующее слово» — новый раунд, серия 1: {st}")
    for _ in range(6):                                   # проигрыш: шесть неверных попыток
        gp.evaluate(TYPE, "ааааа" if gp.evaluate("__words().word") != "ааааа" else "ббббб"); gp.wait_for_timeout(1350)
    gp.wait_for_timeout(1600)
    ok(gp.evaluate("__words().mode") == "over" and "Новое слово" in gp.inner_text("#aOverlay"), "не угадал за шесть — итог «Новое слово»")
    go(); gp.wait_for_timeout(300)
    ok(gp.evaluate("__words().mode") == "play" and gp.evaluate("__words().streak") == 0, "«Новое слово» — новый раунд, серия с нуля")
    gp.close()

    # студия
    pg = br.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and not re.search(r"ERR_|Failed to load|net::", m.text) and errs.append(m.text))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    import settings as SETS  # noqa: E402 — настоящий снимок настроек по умолчанию: его и шлёт ядро
    pg.evaluate("""(d) => { S = Object.assign({}, S || {}, d, { llm: Object.assign({}, d.llm, { active: 'pA', profiles: {
        pA: { name: 'Модель A', kind: 'openai', base_url: 'http://a/v1', api_key: '', model: 'a' },
        pB: { name: 'Модель B', kind: 'openai', base_url: 'http://b/v1', api_key: '', model: 'b' } } }) }); }""",
                json.loads(json.dumps(SETS.DEFAULTS, default=str)))
    # #18 «Мозг»
    pg.evaluate("() => { $('nav button[data-p=\"brain\"]').click(); renderProfiles(); }"); pg.wait_for_timeout(300)
    CHK = "() => [...document.querySelectorAll('#profiles .prof')].filter(e => e.querySelector('.head input').checked).map(e => e.dataset.id + (e.classList.contains('on') ? '+on' : ''))"
    ok(pg.evaluate(CHK) == ["pA+on"], f"до события активна A: {pg.evaluate(CHK)}")
    pg.evaluate("() => { const s = JSON.parse(JSON.stringify(S)); s.llm.active = 'pB'; core.emit('settings', { settings: s }); }"); pg.wait_for_timeout(200)
    ok(pg.evaluate("S.llm.active") == "pB" and pg.evaluate(CHK) == ["pB+on"], f"#18: ядро сменило модель — отметка у B: {pg.evaluate(CHK)}")
    pg.evaluate("() => { openProf = 'pA'; renderProfiles(); }"); pg.wait_for_timeout(100)
    pg.click("#profiles .prof:first-child [data-f='name']"); pg.keyboard.press("End"); pg.keyboard.type(" (моя)")
    pg.evaluate("() => { const s = JSON.parse(JSON.stringify(S)); s.llm.active = 'pA'; core.emit('settings', { settings: s }); }"); pg.wait_for_timeout(200)
    ok(pg.evaluate(CHK) == ["pA+on"] and pg.evaluate("document.activeElement.dataset.f") == "name"
       and pg.input_value("#profiles .prof:first-child [data-f='name']") == "Модель A (моя)",
       "человек печатает в поле профиля — отметка сменилась, ввод и фокус не сбиты")
    pg.evaluate("() => document.activeElement.blur()")
    pg.evaluate("""() => { const s = JSON.parse(JSON.stringify(S)); s.llm.profiles.pC = { name: 'Облако', kind: 'openai', base_url: 'http://c/v1', model: 'c' };
      s.llm.active = 'pC'; core.emit('settings', { settings: s }); }"""); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('#profiles .prof')].map(e => e.dataset.id)") == ["pA", "pB", "pC"] and pg.evaluate(CHK) == ["pC+on"],
       "добавился профиль (переключение на облако) — список перерисован, отметка у нового")
    pg.evaluate("() => { document.querySelector('#profiles .prof').__mark = 1; const s = JSON.parse(JSON.stringify(S)); s.ui.x = 1; core.emit('settings', { settings: s }); }")
    pg.wait_for_timeout(100)
    ok(pg.evaluate("document.querySelector('#profiles .prof').__mark") == 1, "профили не менялись — список не перерисовывается (итог «Проверить» не пропадает)")

    # #19 календарь
    pg.evaluate("() => { $('nav button[data-p=\"calendar\"]').click(); }"); pg.wait_for_timeout(300)
    pg.evaluate("() => { while (PEND.length) PEND.shift().res({ days: {}, currency: 'BYN' }); calY = 2026; calM = 10; calSel = '2026-10-31'; loadCalendar(); }")
    pg.wait_for_timeout(100); pg.evaluate("answer(10)"); pg.wait_for_timeout(200)
    pg.evaluate("openDay('2026-10-31')"); pg.wait_for_timeout(200)
    VIEW = "() => ({ m: calM, sel: calSel, oct: !!(calData.days['2026-10-31']), body: document.querySelector('#dd-body').innerText.includes('тыкву'), empty: !!document.querySelector('#dd-body .dd-empty') })"
    ok(pg.evaluate(VIEW) == {"m": 10, "sel": "2026-10-31", "oct": True, "body": True, "empty": False}, f"31 октября — запись видна: {pg.evaluate(VIEW)}")
    for order in ((10, 11), (11, 10)):
        pg.evaluate("() => { dayShift(1); dayShift(-1); }"); pg.wait_for_timeout(100)
        ok(pg.evaluate("PEND.map(p => p.m)") == [11, 10], f"→ и сразу ← — два запроса: {pg.evaluate('PEND.map(p => p.m)')}")
        for m in order:
            pg.evaluate(f"answer({m})"); pg.wait_for_timeout(150)
        v = pg.evaluate(VIEW)
        ok(v == {"m": 10, "sel": "2026-10-31", "oct": True, "body": True, "empty": False},
           f"#19: ответы {'октябрь, потом ноябрь' if order == (10, 11) else 'ноябрь, потом октябрь'} — у 31 октября его запись: {v}")
    pg.evaluate("() => { dayShift(1); }"); pg.wait_for_timeout(100); pg.evaluate("answer(11)"); pg.wait_for_timeout(200)
    ok(pg.evaluate("calSel") == "2026-11-01" and "Ноябрьское" in pg.inner_text("#dd-body"), "просто на 1 ноября — ответ ноября применяется")
    pg.screenshot(path=str(tmp / "issues_cal.png"))
    ok(not errs, f"без ошибок JavaScript: {errs[:3]}")
    br.close()

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
