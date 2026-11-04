"""Экзамены 15.10, третья пара (телефон 0.6.43 — при плохом интернете, компьютер 0.38.49):
— компьютер: find_notes({}) — модель потеряла аргументы; тема берётся из просьбы («…про работу» → «работу»);
— компьютер: «Поняла, добавила в список» без единого действия — тоже «записала без записи»;
— вызовы текстом: {"function name="f"}; оборванный первый вызов и второй в своём <tool_call> — берём второй (компьютер и телефон);
— картинки не нашлись по «rune knotwork» — сами пробуем слова по отдельности, а не модель трижды тот же запрос;
— телефон: «что у нас по плану?» — сегодняшние планы и напоминания сразу; в экзамене — свои напоминания экзамена, а не
  настоящие с телефона (в ответ попали «17:50 выключить компьютер и бежать на автобус»);
— телефон: «дочка нарисовала мне открытку» — не просьба сделать программу (снова дописалось «Секунду — собираю…»)."""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import llm  # noqa: E402
import quality as Q  # noqa: E402
import engine_tools as ET  # noqa: E402
import tools as T  # noqa: E402

ok(llm.parse_tool_call('\n{"function name="set_reminder"}\n') == {"name": "set_reminder", "args": {}}, "{\"function name=\"f\"} — имя понято")
raw = ('\n{"name": "web_search", "query": "погода в Минске\n\n\nПо прогнозу дождь. Ставлю напоминание.<tool_call>\n'
       '{"\n\nname": "set_reminder", "arguments": {"text": "Взять зонт", "when": "завтра в 8:00"}}\n')
ok(llm.parse_tool_call(raw) == {"name": "set_reminder", "args": {"text": "Взять зонт", "when": "завтра в 8:00"}}, "оборванный вызов и следом целый — взят целый")
ok(Q.saved_claim("И ещё начальник просил подготовить презентацию.", "Поняла, добавила в список.", set()), "«добавила в список» без действия — проверка")


class TB:
    def __init__(self): self.ran = []
    def policy(self, n): return True, False
    def title(self, n): return n
    def guard(self, n, a): return None, False, None
    def auto_ok(self, n, a): return False
    def run(self, n, a): self.ran.append((n, dict(a))); return "ок"


class Turn:
    asked = "Вспомни, что я говорил про работу, и собери это в один список."


f = type("F", (), {"toolbox": TB(), "emit": lambda self, *a, **k: None})()
ET.ToolsMixin._use_tool(f, Turn(), {"name": "find_notes", "args": {}}, None)
ok(f.toolbox.ran == [("find_notes", {"query": "работу"})], f"find_notes без запроса — тема из просьбы: {f.toolbox.ran}")
Turn.asked = "Расскажи про руническую вязь"
ET.ToolsMixin._use_tool(f, Turn(), {"name": "show_images", "args": {"count": 3}}, None)
ok(f.toolbox.ran[-1] == ("show_images", {"count": 3, "query": "руническую вязь"}), f"show_images без запроса: {f.toolbox.ran[-1]}")
ET.ToolsMixin._use_tool(f, Turn(), {"name": "find_notes", "args": {"query": "кухня"}}, None)
ok(f.toolbox.ran[-1] == ("find_notes", {"query": "кухня"}), "свой запрос модели не трогаем")

# картинки: запрос проще — сами
import images as IM  # noqa: E402
asked = []
orig = IM.search
IM.search = lambda q, n, searx_url="", via=None: (asked.append(q) or ([{"title": "Руна", "url": "u", "thumb": "t", "source": "web", "site": "a.ru"}] if q == "knotwork" else []))
try:
    r = T.t_show_images({"query": "rune knotwork", "count": 3}, {"settings": type("S", (), {"get": lambda self, *k: ""})()})
finally:
    IM.search = orig
# экзамен ПК 0.81.1: слова — в порядке запроса (главное модель ставит первым: «runestone knotwork runic inscription» — сначала
# «runestone», а не самое длинное «inscription»); подписи не о том — пробуем дальше, ничего лучше — показываем найденное
ok(asked == ["rune knotwork", "rune", "knotwork"] and r.startswith("На экране показано картинок: 1"), f"не нашлось — попробовали слово отдельно: {asked}")

# ── телефон ──
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    P = pg.evaluate("""(raw) => [parseToolCall('{"function name="set_reminder"}'), parseToolCall(raw)]""", raw)
    ok(P == [{"name": "set_reminder", "args": {}}, {"name": "set_reminder", "args": {"text": "Взять зонт", "when": "завтра в 8:00"}}], f"телефон: те же вызовы текстом: {P}")
    # настоящее напоминание телефона и напоминание экзамена
    A = pg.evaluate("""() => { const eod = new Date(); eod.setHours(23, 59, 59, 0);      // ближе к полуночи «через 30 минут» — уже завтра
        const ahead = m => Date.now() + Math.min(m * 60e3, (eod - Date.now()) / 2), soon = new Date(ahead(30));
        D.alarmSet(JSON.stringify({ title: 'Выключить компьютер и бежать на автобус', at: soon.getTime(), kind: 'reminder', repeat: '' }));
        const real = agendaPlans('Что у нас по плану?');
        EXAM = { alarms: [{ id: 'seedA0', title: 'полить цветы', at: ahead(20), kind: 'reminder', repeat: '', made: 0 }] };
        const ex = agendaPlans('Что у нас по плану?'); EXAM = null; return [real, ex]; }""")
    ok("автобус" in A[0], f"«что у нас по плану?» — сегодняшние напоминания сразу: {A[0][:120]!r}")
    ok("полить цветы" in A[1] and "автобус" not in A[1], f"в экзамене — напоминания экзамена, не настоящие: {A[1][:120]!r}")
    K = pg.evaluate("""() => [claimedAction('Вот это разворот — от «всё валится» до тёплой открытки на руках. А что она нарисовала?', new Set(),
          'Сегодня с утра всё валилось из рук, зато вечером дочка нарисовала мне открытку, и стало тепло.'),
        (claimedAction('Вот твоя открытка — уже на экране!', new Set(), 'Сделай открытку для мамы') || {}).tool]""")
    ok(K[0] is None and K[1] == "make_app", f"«дочка нарисовала открытку» — не просьба; «сделай открытку» — да: {K}")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
