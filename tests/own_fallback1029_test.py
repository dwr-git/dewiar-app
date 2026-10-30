"""Своя модель не отвечает (29.10, пакет: «своя модель · нет связи» — 107 за неделю; у 270 компьютеров из 820 мозг есть, а
ответа не было ни разу). «Мозг» → «Если своя модель не отвечает — отвечать через Dewiar»:
- включено и мозг Dewiar подключён — отвечает он, с заметкой; выключено — подсказка, что делать, один раз; вопрос в облако
  без согласия не уходит;
- только «нет связи» со своей моделью на этом компьютере или в своей сети; облако, чужие сервисы, медленная модель — нет;
- включили, а мозга Dewiar нет — заявка запасным: ключ подключается, но главной остаётся своя модель;
- в студии переключатель виден, только когда главная — своя модель."""
import json, os, re, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402
import engine_brain as EB  # noqa: E402
import engine_commands as EC  # noqa: E402


class S:
    def __init__(self, d):
        self.d = d

    def get(self, *keys):
        v = self.d
        for k in keys:
            v = (v or {}).get(k)
        return v

    def update(self, patch):
        def merge(a, b):
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    merge(a[k], v)
                else:
                    a[k] = v
        merge(self.d, patch)

    def snapshot(self):
        return json.loads(json.dumps(self.d))


CLOUDP = {"name": "Dewiar Облако", "base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "cloud": True, "model": "dw"}
LOCAL = {"name": "LM Studio", "base_url": "http://127.0.0.1:1234/v1", "model": "qwen"}
notes = []


def eng(settings):
    e = types.SimpleNamespace(s=S(settings), note=notes.append)
    e._tools_key = types.MethodType(EA.AnswerMixin._tools_key, e)
    return e


DOWN = "не удалось подключиться к серверу модели http://127.0.0.1:1234 — connection refused"
e = eng({"llm": {"profiles": {"lm": LOCAL, "dewiar-cloud": CLOUDP}, "own_fallback": True}})
fb = EA.AnswerMixin._own_fallback(e, LOCAL, DOWN)
ok(fb and fb.get("cloud") and fb["model"] == "dw" and notes and "ответила через Dewiar" in notes[-1], f"включено — отвечает мозг Dewiar, с заметкой: {notes[-1:]}")

notes.clear()
e = eng({"llm": {"profiles": {"lm": LOCAL, "dewiar-cloud": CLOUDP}, "own_fallback": False}})
ok(EA.AnswerMixin._own_fallback(e, LOCAL, DOWN) is None and notes and "запустите LM Studio" in notes[0] and "«Мозг»" in notes[0],
   "выключено — в облако не уходит, подсказка что делать")
EA.AnswerMixin._own_fallback(e, LOCAL, DOWN)
ok(len(notes) == 1, "подсказка — один раз за запуск")

notes.clear()
e = eng({"llm": {"profiles": {"dewiar-cloud": CLOUDP}, "own_fallback": True}})
for prof, err, why in ((CLOUDP, DOWN, "облако Dewiar"), ({"base_url": "https://api.openai.com/v1"}, DOWN, "чужой облачный сервис"),
                       (LOCAL, "сервер модели не ответил вовремя (timeout)", "своя модель медленная, а не выключена")):
    ok(EA.AnswerMixin._own_fallback(e, prof, err) is None, f"{why} — не подменяем")
ok(EA.AnswerMixin._own_fallback(eng({"llm": {"profiles": {}, "own_fallback": True}}), LOCAL, DOWN) is None, "мозга Dewiar нет — нечем подменить")

# команда: мозга нет — заявка запасным; ключ — подключить без смены главной модели
sent, connected = [], []
e = eng({"llm": {"active": "lm", "profiles": {"lm": LOCAL}}, "cloud": {}})
e.standby_join = lambda: sent.append(1) or False
e.kids = None
r = EC.CommandsMixin.command(e, "own_fallback", {"on": True})
ok(r == {"on": True, "ready": False} and sent and e.s.get("llm", "own_fallback") is True, f"включили без мозга Dewiar — отправлена заявка: {r}")

e.cloud = types.SimpleNamespace(connect=lambda key, url="", activate=True: connected.append(activate) or {"ok": True}, status=lambda: {})
e.emit = lambda *a, **k: None
e.s.update({"cloud": {"join": {"id": 7, "secret": "s", "url": "u", "auto": True, "standby": True}}})
next(c for c in vars(EB).values() if isinstance(c, type) and "_join_done" in vars(c))._join_done(e, "dw-key", {})
ok(connected == [False] and e.s.get("cloud", "join", "standby") is False and e.s.get("llm", "active") == "lm",
   "ключ пришёл — подключён запасным, главная модель та же")

src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("fb = self._own_fallback(prof, e)" in src, "в ходе разговора: облако не ответило — запасной; своя модель не ответила — Dewiar (по согласию)")

from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); if (c === "own_fallback") return { on: a.on, ready: true }; return {}; }; };
  ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(FAKE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""() => { S = S || {}; S.llm = { active: 'lm', profiles: { lm: %s, 'dewiar-cloud': %s }, own_fallback: false };
      document.querySelector('nav button[data-p="brain"]').click(); renderProfiles(); }""" % (json.dumps(LOCAL), json.dumps(CLOUDP)))
    pg.wait_for_timeout(300)
    ok(pg.is_visible("#own-fb-w") and not pg.is_checked("#own-fb"), "студия: главная — своя модель — переключатель виден")
    pg.click("#own-fb-w label.tg"); pg.wait_for_timeout(300)
    ok(["own_fallback", {"on": True}] in pg.evaluate("calls") and "готово" in pg.inner_text("#own-fb-res"), "включили — ядру ушло, ответ понятный")
    pg.evaluate("() => { S.llm.active = 'dewiar-cloud'; renderProfiles(); }"); pg.wait_for_timeout(200)
    ok(pg.is_hidden("#own-fb-w"), "главная — Dewiar — переключателя нет")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
