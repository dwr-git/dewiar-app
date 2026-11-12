"""Владелец 12.11, утренняя сводка — «три бага в простом действии»:
1) «опять рассказала про ежедневные „не забыть карту в столовую“, „17:50 выключать компьютер“, „21:00 итог дня“» — в
   данных сводки привычки (каждый день и по будням) и сами дела по расписанию больше не перечисляются;
2) сводку начала, не договорила и начала заново: переспрос «ты сказала, что дел нет, а они есть» брал дела из справки о
   планах (там привычки снова есть) — для сводки он смотрит только её данные;
3) после неё — бесконечное «Я вас слушаю» при выключенном микрофоне: окно «ваша очередь» при выключенном микрофоне не
   открывается, а если «слушаю» осталось, а слух не идёт, — сторож раз в 5 с возвращает покой."""
import os, sys, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_music as EM  # noqa: E402
import morning  # noqa: E402
import quality as Q  # noqa: E402

items = [{"id": "r1", "text": "Обед, не забудь карту", "kind": "reminder", "repeat": {"kind": "weekly", "days": [0, 1, 2, 3, 4], "time": "12:28"}},
         {"id": "r2", "text": "Пора выключать компьютер", "kind": "reminder", "repeat": {"kind": "daily", "time": "17:50"}},
         {"id": "r3", "text": "Позвонить в банк", "kind": "reminder", "at": "2026-11-12T15:00"},
         {"id": "j1", "text": "Итог дня…", "kind": "job", "repeat": {"kind": "daily", "time": "21:00"}}]
TODAY = {"meet": [], "todo": [{"time": "12:28", "title": "Обед, не забудь карту", "id": "r1", "kind": "reminder"},
                              {"time": "15:00", "title": "Позвонить в банк", "id": "r3", "kind": "reminder"},
                              {"time": "17:50", "title": "Пора выключать компьютер", "id": "", "kind": "reminder"},
                              {"time": "21:00", "title": "Итог дня", "id": "j1", "kind": "job"}]}
morning.gather = lambda eng, net=True: {"today": TODAY, "weather": {"line": "Минск +1"}, "tasks": None}
morning.context = lambda d: ""
e = types.SimpleNamespace(reminders=types.SimpleNamespace(items=items),
                          money=types.SimpleNamespace(summary=lambda a, b: {"by_currency": []}),
                          tasks=types.SimpleNamespace(list=lambda: []), night=types.SimpleNamespace(morning_note=lambda: ""),
                          morning_share=lambda d: None)
e._habits = types.MethodType(EM.MusicMixin._habits, e)
ctx = EM.MusicMixin._brief_context(e, net=False)
line = next(x for x in ctx.splitlines() if x.startswith("Дела и напоминания на сегодня:"))
ok(line == "Дела и напоминания на сегодня: 15:00 Позвонить в банк.", f"в данных сводки — только дела дня: {line!r}")
ok("не называй их" in ctx, "и прямо сказано: привычки и дела по расписанию не называть")
TODAY["todo"] = TODAY["todo"][:1] + TODAY["todo"][2:]
ctx2 = EM.MusicMixin._brief_context(e, net=False)
ok("Дела и напоминания на сегодня: нет." in ctx2, f"кроме привычек ничего — «нет»: {ctx2!r}")
ok(next(x for x in morning._today.__code__.co_consts if isinstance(x, str) and x == "kind") == "kind",
   "morning._today отдаёт id и вид дела (по ним и отбираем)")

# переспрос «дел нет» в сводке — только по её данным
ask = ctx2 + "\n\n[Утро с Лирой] Составь по этим данным короткую утреннюю сводку"
agenda = "Сегодня:\n12:28 Обед, не забудь карту\n17:50 Пора выключать компьютер"
ok(not Q.agenda_missed(ask, "Доброе утро! Дел на сегодня нет.", agenda), "сводка: привычки из справки о планах — не повод переспрашивать")
ok(Q.agenda_missed("что у меня сегодня?", "Дел на сегодня нет.", agenda), "обычный вопрос о планах — переспрос как раньше")
ask1 = ctx + "\n\n[Утро с Лирой] …"
ok(Q.agenda_missed(ask1, "Доброе утро! Дел на сегодня нет.", ""), "в данных сводки есть разовое дело, а ответ «дел нет» — переспрос")

# «Я вас слушаю» без конца
st = []
w = types.SimpleNamespace(state="listening", turn=None, hold=None, follow_up_until=time.monotonic() - 10, _listen_live=time.monotonic() - 20,
                          _mute_pass=True)
w.set_state = lambda s: (st.append(s), setattr(w, "state", s))
ok(EM.MusicMixin._listen_watchdog(w) and st == ["idle"] and w.follow_up_until == 0.0 and not w._mute_pass,
   "«слушаю», окно истекло, слух не идёт — покой")
w.state, st[:] = "listening", []
w.follow_up_until, w._listen_live = time.monotonic() - 10, time.monotonic()
ok(not EM.MusicMixin._listen_watchdog(w) and not st, "слух идёт — окно закроет он сам (сторож не вмешивается)")
w.follow_up_until, w._listen_live = time.monotonic() + 5, 0
ok(not EM.MusicMixin._listen_watchdog(w), "окно ещё открыто — не трогаем")
w.follow_up_until, w.hold = 0, {"pcm": []}
ok(not EM.MusicMixin._listen_watchdog(w), "держат «говорить» — не трогаем")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('if getattr(self, "muted", False) or getattr(self, "_mic_pause", 0):\n            follow = 0.0' in ea,
   "микрофон выключен — «ваша очередь» после ответа не открывается")
au = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
mu = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok("self._listen_live = now" in au and "self._listen_watchdog()" in mu, "слух отмечает, что идёт; сторож — в фоновом потоке присутствия")
# 4) «Не получилось: 407 Proxy Authentication Required» (дважды, 09:01 и 09:02): понятный текст и свежий логин прокси
import httpx  # noqa: E402
import llm  # noqa: E402
import net  # noqa: E402
t = llm._humanize(httpx.ProxyError("407 Proxy Authentication Required"), "https://dewiar.pro/x")
ok("просит логин и пароль" in t and "Proxy Authentication" not in t, f"407 — по-русски и что делать: {t}")
called = []
net.on_proxy_auth = lambda: called.append(1)
lz = net._Lazy("http://127.0.0.1:9", True, None)


class T407:
    def handle_request(self, req):
        raise httpx.ProxyError("407 Proxy Authentication Required")


lz.t = T407()
try:
    lz._via_proxy(httpx.Request("GET", "https://dewiar.pro/x"))
    ok(False, "407 — ошибка наружу")
except httpx.ProxyError:
    ok(called == [1], "прокси ответил 407 — сразу просим свежий логин и не повторяем впустую")
net.on_proxy_auth = None
import engine_brain as EB  # noqa: E402
cls = next(c for c in vars(EB).values() if isinstance(c, type) and hasattr(c, "_proxy_auth_stale"))
fetched = []
b = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda a, k: "http://u:p@px:1" if (a, k) == ("net", "dewiar_secret") else None),
                          _dewiar_proxy_fetch=lambda force=False: fetched.append(force))
ok(cls._proxy_auth_stale(b) and not cls._proxy_auth_stale(b), "свежий логин — не чаще раза в 10 минут")
time.sleep(0.2)
ok(fetched == [True], f"берётся с сайта (force): {fetched}")
lsrc = (ROOT / "core/llm.py").read_text(encoding="utf-8")
ok("if r.status_code == 407:" in lsrc, "ответ 407 от сервера модели через прокси — тот же понятный текст")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
