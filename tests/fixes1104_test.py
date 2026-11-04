"""Пакет 04.11 — жалобы №520, №521, №523, №524, №525, №526, №527, частые сбои («close.tmp», «ResizeObserver») и идеи №128, №131.
Все адреса, логины, пароли и имена — выдуманные.

- №520, №527: «микрофон молчит (почти тишина)». Выбрана беспроводная гарнитура, она выключена — брали микрофон Windows по
  умолчанию, а им бывает Steam Streaming Microphone (виртуальный). Теперь взамен — настоящий; подсказка называет выбранный и
  другие микрофоны (у беспроводной — про питание), у единственной гарнитуры — про кнопку выключения микрофона на ней;
  строка «недоступен — беру…» — раз в 10 минут, а не каждые 5 с.
- №521, №523: ядро обрывалось без строчки в журнале, как только начинал звучать голос (вывод — HDMI монитора). Сторож окна
  (ui/app.py core_guard) поднимает упавшее ядро и пишет код выхода; метка «звук играет» — второй раз подряд звук уходит на
  устройство по умолчанию; падения (faulthandler) — в отчёте и в диагностике.
- №524: OpenCode Go — заголовок x-opencode-session (постоянный id).
- №525: «Радио на паузе» → «На паузе» (и своя музыка).
- №526: прокси «адрес:порт:логин:пароль» и 407 — понятная подсказка.
- «PermissionError … close.tmp»: своё имя временного файла и повторы (core/atomicio.py).
- телефон: «ResizeObserver loop …» — шум, не сбой.
- идея №128: своё имя близкого; №131: dewiar-server со своей моделью — вход на dewiar.pro необязателен."""
import json, os, re, sys, tempfile, threading, types
from pathlib import Path
from unittest import mock
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
TMP = Path(tempfile.mkdtemp())
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- №520, №527: какой микрофон и что подсказать ----------
import audio_io  # noqa: E402
devs = [{"name": "Переназначение звуковых устр. - Input", "kind": "source", "index": 0},
        {"name": "Микрофон (USB PnP Audio Devi", "kind": "source", "index": 1},
        {"name": "Микрофон (Steam Streaming Micro", "kind": "source", "index": 2},
        {"name": "Микрофон (Wireless Headset X)", "kind": "source", "index": 3},
        {"name": "Динамики (Wireless Headset X)", "kind": "sink", "index": 4}]
ok(audio_io.fallback_source(devs, "Микрофон (Steam Streaming Micro") == 1,
   "выбранный недоступен, а по умолчанию — Steam Streaming: берём первый настоящий (USB)")
ok(audio_io.fallback_source(devs, "Микрофон (USB PnP Audio Devi") is None, "по умолчанию настоящий — его и берём (None)")
ok(audio_io.fallback_source(devs[:1] + devs[2:3], "Микрофон (Steam Streaming Micro") is None, "настоящих нет — как раньше, по умолчанию")
ok(audio_io.VIRTUAL_MIC_RX.search("Микрофон (Steam Streaming Micro") and not audio_io.VIRTUAL_MIC_RX.search("Микрофон (Wireless Headset X)"),
   "Steam Streaming — виртуальный, гарнитура — настоящая")
with mock.patch.object(audio_io.log, "warning") as w:
    for _ in range(5):
        audio_io.warn_rare("t:k", "«%s» недоступен", "x")
    ok(w.call_count == 1, f"одно и то же предупреждение — раз в 10 минут: {w.call_count}")

import engine  # noqa: E402
import engine_audio  # noqa: E402
E = engine.Engine
told, pushed = [], []


def hint(srcs, cur):
    cfg = {"input": cur}
    st = types.SimpleNamespace(note=lambda t: told.append(t), push=lambda title, text, **k: pushed.append(text),
                               report_problem=lambda *a: None, _mic_alive=False,
                               s=types.SimpleNamespace(get=lambda *k: cfg.get(k[-1], ""), update=lambda p: None))
    engine_audio.list_devices = lambda: [{"name": n, "description": n, "kind": "source"} for n in srcs]
    with mock.patch.object(engine_audio.os, "name", "nt"):
        E._mic_silent(st, exact=False)
    return told[-1] if told else ""


t = hint([d["name"] for d in devs if d["kind"] == "source"], "Микрофон (Wireless Headset X)")
ok("«Микрофон (Wireless Headset X)»" in t and "включена" in t and "«Микрофон (USB PnP Audio Devi»" in t and "Steam" not in t,
   f"№520: выбрана беспроводная гарнитура — про питание и какие ещё есть (без виртуального): {t[:160]}")
t = hint(["Microsoft Sound Mapper - Input", "Микрофон (Gaming Headset 360)"], "")
ok("«Микрофон (Gaming Headset 360)»" in t and "кнопка" in t, f"№527: единственная гарнитура — про кнопку выключения микрофона: {t[-140:]}")
t = hint(["Микрофон (Steam Streaming Micro", "Микрофон (USB PnP Audio Devi"], "Микрофон (Steam Streaming Micro")
ok("виртуальный" in t and "USB PnP" in t, f"выбран Steam Streaming — «похоже, слушаю виртуальный»: {t[:120]}")

# ---------- №521, №523: ядро падало, пока звучал голос ----------
mark = TMP / "audio_out.live"
audio_io.OUT_MARK[0] = mark
audio_io._mark_out(1, "MONITOR (HDMI Audio)")
ok(mark.read_text(encoding="utf-8") == "MONITOR (HDMI Audio)", "звук играет — метка с устройством")
audio_io._mark_out(1, "x"); audio_io._mark_out(-1)
ok(mark.exists(), "два вывода, один закрылся — метка остаётся")
audio_io._mark_out(-1)
ok(not mark.exists(), "всё доиграло — метки нет")
audio_io.OUT_MARK[0] = None
cfg = {"audio": {"output": "MONITOR (HDMI Audio)"}}
notes = []


def get(*k):
    cur = cfg
    for x in k:
        cur = (cur or {}).get(x) if isinstance(cur, dict) else None
    return cur


def upd(p):
    for k, v in p.items():
        cfg.setdefault(k, {}).update(v)


eng = types.SimpleNamespace(s=types.SimpleNamespace(get=get, update=upd), note=notes.append, null_player=True, wav_input=None)
ok(E._out_crash_check(eng, mark) is None, "метки нет — прошлый запуск закончился нормально")
mark.write_text("MONITOR (HDMI Audio)", encoding="utf-8")
ok(E._out_crash_check(eng, mark) == "counted" and cfg["audio"]["out_crash"] == 1 and cfg["audio"]["output"], "оборвался посреди звука — посчитали, звук пока не трогаем")
mark.write_text("MONITOR (HDMI Audio)", encoding="utf-8")
ok(E._out_crash_check(eng, mark) == "switched" and cfg["audio"]["output"] == "" and notes and "по умолчанию" in notes[-1],
   f"второй раз подряд — звук на устройство по умолчанию и сказано об этом: {notes[-1][:90] if notes else ''}")
mark.write_text("-", encoding="utf-8")
ok(E._out_crash_check(eng, mark) == "counted" and cfg["audio"]["output"] == "", "звук и так по умолчанию — только считаем")
E._out_crash_check(eng, mark)
ok(cfg["audio"]["out_crash"] == 0, "нормальный запуск сбрасывает счёт")

import engine_answer  # noqa: E402
import doctor  # noqa: E402
cr = ("\n--- запуск 2026-11-03 20:00:00 · 0.81.2\nWindows fatal exception: code 0xe06d7363\n"
      "\n--- запуск 2026-11-03 20:21:00 · 0.81.2\nWindows fatal exception: int divide by zero\n\nCurrent thread 0x1 (most recent call first):\n"
      '  File "C:\\\\app\\\\core\\\\audio_io.py", line 1 in write\n')
ok(len(engine_answer.crash_blocks(cr)) == 1 and "divide" in engine_answer.crash_blocks(cr)[0], "отчёт: и «int divide by zero», а C++-шум 0xe06d7363 — нет")
(TMP / "logs").mkdir()
(TMP / "logs" / "core.crash").write_text(cr, encoding="utf-8")
ok(any("divide by zero" in x for x in doctor.core_crash_lines(TMP / "logs")) and doctor.crash_blocks(cr) == engine_answer.crash_blocks(cr),
   "диагностика (№521): падение ядра из core.crash — тоже, по тому же правилу")
ok("core_crash_lines(LOCAL / \"logs\")" in (ROOT / "ui/doctor.py").read_text(encoding="utf-8"), "диагностика берёт раздел «Падения ядра»")

import app  # noqa: E402


class Proc:
    def __init__(self, code):
        self.code = code

    def poll(self):
        return self.code


logged, started = [], []
stop = threading.Event()
app.CORE_PROC[:] = [Proc(0xC0000005)]
app.CORE_EXPECTED[0] = 0.0


def fake_start():
    started.append(1)
    app.CORE_PROC[:] = [Proc(0xC0000005) if len(started) < 5 else Proc(None)]
    if len(started) >= 5:
        stop.set()


with mock.patch.object(app, "_ui_log", logged.append), mock.patch("settings.STATE_DIR", TMP):
    th = threading.Thread(target=app.core_guard, kwargs={"stop": stop, "every": 0.01, "alive": lambda: False, "start": fake_start})
    th.start(); th.join(3); stop.set(); th.join(1)
ok(len(started) == 3 and "0xC0000005" in logged[0] and "запускаю снова" in logged[0] and "больше сам не запускаю" in logged[-1],
   f"ядро упало посреди работы — сторож поднимает его (не больше трёх раз за 10 минут) и пишет код: {logged[:1]} … {logged[-1:]}")
ok(json.loads((TMP / "core.exit").read_text(encoding="utf-8"))["code"] == 0xC0000005, "код выхода — в core.exit (ядро напишет его в журнал)")
started.clear(); logged.clear(); stop.clear()
app.CORE_PROC[:] = [Proc(1)]
app.CORE_EXPECTED[0] = __import__("time").time()
th = threading.Thread(target=app.core_guard, kwargs={"stop": stop, "every": 0.01, "alive": lambda: False, "start": fake_start})
th.start(); __import__("time").sleep(0.2); stop.set(); th.join(1)
ok(not started, "ядро остановили нарочно (перезапуск кнопкой, выход) — сторож не вмешивается")
app.CORE_PROC[:] = [Proc(0)]; app.CORE_EXPECTED[0] = 0.0; stop.clear()
th = threading.Thread(target=app.core_guard, kwargs={"stop": stop, "every": 0.01, "alive": lambda: False, "start": fake_start})
th.start(); __import__("time").sleep(0.2); stop.set(); th.join(1)
ok(not started, "ядро вышло само (код 0: перезапуск после восстановления) — не трогаем")
src = (ROOT / "core/main.py").read_text(encoding="utf-8")
ok('"core.exit"' in src and "Прошлый запуск ядра упал" in src, "ядро при запуске пишет в журнал, как упал прошлый запуск")
src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("if core_watch():\n            core_guard()" in src, "Windows: после запуска ядра сторож следит дальше")

# ---------- №524: OpenCode Go ----------
import llm  # noqa: E402
with mock.patch("settings.STATE_DIR", TMP):
    llm._OC_SESSION.clear()
    h = llm._headers({"kind": "openai", "base_url": "https://opencode.ai/zen/go/v1", "api_key": "sk-test-0000"})
    sid = h.get("x-opencode-session", "")
    llm._OC_SESSION.clear()
    h2 = llm._headers({"kind": "openai", "base_url": "https://opencode.ai/zen/go/v1", "api_key": "sk-test-0000"})
ok(re.fullmatch(r"[0-9a-f-]{36}", sid or "") and h2.get("x-opencode-session") == sid, f"OpenCode: x-opencode-session, один и тот же между запусками: {sid}")
ok("x-opencode-session" not in llm._headers({"kind": "openai", "base_url": "https://api.example.com/v1", "api_key": "k"}),
   "другим провайдерам заголовок не шлём")

# ---------- №525: «На паузе» ----------
for f, bad in (("core/engine_answer.py", "Радио на паузе"), ("ui/studio/mymusic.js", "Радио на паузе"),
               ("android/assets/www/app.js", "Радио на паузе"), ("core/tools.py", "» на паузе\"")):
    ok(bad not in (ROOT / f).read_text(encoding="utf-8"), f"{f}: «На паузе» — и для радио, и для своей музыки")

# ---------- №526: прокси с логином ----------
import net  # noqa: E402
ok(net.normalize_proxy("http://203.0.113.7:9667:usr:pw") == "http://usr:pw@203.0.113.7:9667", "«http://адрес:порт:логин:пароль» — понят")
ok(net.normalize_proxy("203.0.113.7:9667:usr:p@ss") == "http://usr:p%40ss@203.0.113.7:9667", "без http:// и с @ в пароле")
ok(net.normalize_proxy("203.0.113.7:9667@usr:pw") == "http://usr:pw@203.0.113.7:9667", "«адрес:порт@логин:пароль» — тоже")
ok(net.normalize_proxy("usr:1234@203.0.113.7:8080") == "http://usr:1234@203.0.113.7:8080", "обычный вид «логин:пароль@адрес:порт» не ломаем")
ok(net.normalize_proxy("socks5://203.0.113.7:1080:a:b") == "socks5://a:b@203.0.113.7:1080", "SOCKS5 с логином")
try:
    net.normalize_proxy("http://203.0.113.7")
    e = ""
except net.NetError as x:
    e = str(x)
ok("логин:пароль@адрес:порт" in e, f"без порта — подсказка и про логин: {e}")


with mock.patch.object(net.httpx, "Client", side_effect=net.httpx.ProxyError("407 Proxy Authentication Required")):
    r1 = net._probe_try("https://example.com/latest.json", "http://203.0.113.7:9667", 1)
    r2 = net._probe_try("https://example.com/latest.json", "http://u:p@203.0.113.7:9667", 1)
ok("логин и пароль" in r1[1] and "http://логин:пароль@адрес:порт" in r1[1], f"407 без логина — как вписать: {r1[1]}")
ok("не подошли" in r2[1], f"407 с логином — логин или пароль не подошли: {r2[1]}")
ok("логин:пароль@адрес:порт" in (ROOT / "ui/settings.html").read_text(encoding="utf-8"), "в «Сети» — подсказка о формате с логином")

# ---------- «PermissionError … close.tmp» ----------
import atomicio  # noqa: E402
target = TMP / "close.json"
real = os.replace
n = {"k": 0}


def flaky(src, dst):
    if n["k"] < 2:
        n["k"] += 1
        raise PermissionError(13, "Permission denied")
    return real(src, dst)


with mock.patch.object(atomicio.os, "replace", flaky):
    atomicio.write_text(target, '{"a": 1}')
ok(json.loads(target.read_text(encoding="utf-8")) == {"a": 1} and n["k"] == 2 and not list(TMP.glob("close.json.*.tmp")),
   "файл на миг занят — записано с третьей попытки, временных файлов не осталось")
names = {atomicio._tmp_name(target).name for _ in range(50)}
ok(len(names) == 50, "у каждой записи своё имя временного файла (два потока не мешают друг другу)")
errs = []


def writer(i):
    try:
        for j in range(30):
            atomicio.write_text(target, json.dumps({"i": i, "j": j}))
    except Exception as x:  # noqa: BLE001
        errs.append(x)


ths = [threading.Thread(target=writer, args=(i,)) for i in range(6)]
[t.start() for t in ths]; [t.join() for t in ths]
ok(not errs and json.loads(target.read_text(encoding="utf-8"))["j"] == 29, f"шесть потоков пишут разом — без ошибок: {errs[:1]}")
ok("atomicio.write_text(self.path, data)" in (ROOT / "core/close.py").read_text(encoding="utf-8"), "«Близкие» сохраняются через atomicio")

# ---------- телефон: ResizeObserver — шум ----------
js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("const JS_NOISE = /^ResizeObserver loop/i;" in js and "!JS_NOISE.test(e.message)" in js, "телефон: «ResizeObserver loop…» в отчёты не идёт")

# ---------- идея №128: своё имя близкого ----------
import close  # noqa: E402
c = close.Close.__new__(close.Close)
c._lock = threading.RLock()
c.st = {"people": [], "names": {}, "unread": {}, "hist": {}, "marks": {}, "groups": [], "me": {}}
c.path = TMP / "close_state.json"
c.error = ""
emitted = []
c.host = types.SimpleNamespace(emit=lambda *a, **k: emitted.append(k))
c.geo_state = lambda: {}
c.st["people"] = c._named([{"pid": "p1", "name": "Без имени"}, {"pid": "p2", "name": "Андрей"}])
st = c.rename("p1", "  Мама ")
p1 = next(p for p in st["people"] if p["pid"] == "p1")
ok(p1["name"] == "Мама" and p1["orig"] == "Без имени", f"контакт «Без имени» переименован: {p1}")
ok(close.match_name("маме", c.st["people"])["pid"] == "p1", "голосом «напиши маме» — тот самый близкий")
c.st["people"] = c._named([{"pid": "p1", "name": "Без имени"}, {"pid": "p2", "name": "Андрей"}])   # пришёл список с сервера
ok(next(p for p in c.st["people"] if p["pid"] == "p1")["name"] == "Мама", "свежий список с сервера своё имя не стирает")
st = c.rename("p1", "")
ok(next(p for p in st["people"] if p["pid"] == "p1")["name"] == "Без имени" and "p1" not in c.st["names"], "пустое имя — снова как он сам себя назвал")
ok('core.call("close_rename"' in (ROOT / "ui/studio/close.js").read_text(encoding="utf-8")
   and 'id="cl-ren"' in (ROOT / "ui/settings.html").read_text(encoding="utf-8")
   and 'cmd == "close_rename"' in (ROOT / "core/engine_commands.py").read_text(encoding="utf-8"), "студия: кнопка «Переименовать» в переписке")

# ---------- идея №131: dewiar-server со своей моделью — без входа ----------
import importlib.machinery, importlib.util  # noqa: E401,E402
ld = importlib.machinery.SourceFileLoader("dewiar_server", str(ROOT / "packaging/dewiar-server"))
ds = importlib.util.module_from_spec(importlib.util.spec_from_loader("dewiar_server", ld)); ld.exec_module(ds)
runs = []
envs = {"DEWIAR_LLM_URL": "http://127.0.0.1:11434/v1", "DEWIAR_LLM_MODEL": "qwen-test", "DEWIAR_LLM_KEY": "", "DEWIAR_LOGIN": ""}
with mock.patch.dict(os.environ, envs), mock.patch.object(ds.subprocess, "run", lambda cmd, **k: runs.append(k.get("input")) or
                                                          types.SimpleNamespace(returncode=0, stdout="", stderr="")):
    acc = ds.configure()
job = json.loads(runs[-1])
ok(acc is False and job["login"] == "" and job["url"].endswith("/v1"), "своя модель (Ollama), логин пустой — настройка идёт без входа")
src = (ROOT / "packaging/dewiar-server").read_text(encoding="utf-8")
ok(src.index('ask("Адрес модели"') < src.index('ask("Логин на dewiar.pro"') and "необязательно" in src,
   "сначала модель, вход — необязательно (Enter — пропустить)")
with mock.patch.dict(os.environ, {"DEWIAR_LLM_URL": "", "DEWIAR_LOGIN": ""}):
    try:
        ds.configure(); quit_ = ""
    except SystemExit as x:
        quit_ = str(x)
ok("Нужна модель или вход" in quit_, f"ни модели, ни входа — понятно, чего не хватает: {quit_}")

print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
