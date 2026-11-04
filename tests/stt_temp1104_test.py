"""№513 (пакет 04.11, компьютер 0.80.0): «Раздел «Слух»: после обновления слетают настройки распознавания фраз —
переключается на «Сервер Dewiar»». Причина (журнал): ключ Dewiar подключался через 6 с после запуска, пока GigaAM ещё
грузился (stt_ready=False — «не готов», а не «сломался»); _ensure_brain отдавал речь серверу и записывал это в
настройки насовсем («Свой GigaAM не загрузился — речь распознаёт сервер Dewiar», и через секунду «GigaAM готов»).
Теперь: на сервер — только если своя модель правда не загрузилась, и временно (stt.auto_from помнит выбор человека);
при следующем запуске и раз в час — снова своя модель; студия показывает «временно — сервер Dewiar»."""
import os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE=str(tmp / "ws"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings, stt  # noqa: E402,E401
from engine_brain import BrainMixin  # noqa: E402

ok(settings.DEFAULTS["stt"].get("auto_from") == "", "в настройках есть stt.auto_from (выбор человека на время замены)")


class Cloud:
    def __init__(self, s):
        self.s = s

    def set_stt(self, on):          # как cloud.Cloud.set_stt
        if on:
            self.s.update({"stt": {"engine": "remote", "remote": {"base_url": "https://x/", "api_key": "k", "model": "gigaam", "cloud": True}}})
        else:
            self.s.update({"stt": {"engine": "gigaam", "remote": {"cloud": False}}})


class FakeGiga(stt.GigaAMSTT):
    """GigaAM без файлов: load() — успех или ошибка по флагу; скачан ли — по флагу have; gate — задержать загрузку."""
    good, have, loads, gate = False, True, 0, None

    def cached(self):
        return FakeGiga.have

    def load(self, on_progress=None):
        FakeGiga.loads += 1
        if FakeGiga.gate is not None:
            FakeGiga.gate.wait(10)
        if FakeGiga.good:
            self.model = object()
            self.error = ""
            return True
        self.error = "No module named 'onnx_asr'"
        return False


class Eng(BrainMixin):
    def __init__(self):
        self.s = settings.Settings(tmp / "cfg" / f"s{id(self)}.json")
        self.s.update({"cloud": {"key": "dw-test", "stt_ok": True}, "stt": {"engine": "gigaam"}})
        self.cloud = Cloud(self.s)
        self.status = {"stt_ready": False}
        self.pushes, self.applied = [], 0
        self.gigaam = FakeGiga("gigaam-v3-e2e-rnnt")
        self.stt = self.gigaam
        self.vosk_stt = object()

    def apply_engines(self):
        self.applied += 1
        st = self.s.get("stt")
        self.stt = types.SimpleNamespace(name="Dewiar Облако", ready=True) if st["engine"] == "remote" else self.gigaam

    def push(self, title, text, **k):
        self.pushes.append(title)

    def emit(self, *a, **k):
        pass


# 1) GigaAM ещё грузится (ошибки нет) — сервер не трогаем: это и был №513
e = Eng()
e.gigaam.loading = True
ok(not e._own_stt_failed() and not e._stt_temp_server(), "GigaAM ещё грузится — речь серверу не отдаём")
e.gigaam.loading = False
ok(not e._stt_temp_server() and e.s.get("stt", "engine") == "gigaam", "ещё не начинал грузиться (ошибки нет) — тоже не отдаём")
ok(e.s.get("stt", "engine") == "gigaam" and not e.s.get("stt", "auto_from"), "выбор человека — GigaAM — на месте")

# 2) GigaAM правда не загрузился — временно сервер, выбор помним
FakeGiga.good = False
e.gigaam.load()
ok(e._own_stt_failed(), "ошибка загрузки — «не загрузился»")
ok(e._stt_temp_server() is True, "своя модель не загрузилась — временно распознаёт сервер Dewiar")
st = e.s.get("stt")
ok(st["engine"] == "remote" and st["remote"].get("cloud") and st.get("auto_from") == "gigaam", f"на время — сервер, выбор «gigaam» в auto_from: {st.get('auto_from')!r}")
ok(e.pushes and "временно" in e.pushes[-1], f"уведомление честно говорит «временно»: {e.pushes[-1:]}")

# 3) раз в час — пробуем свою модель; не грузится — остаёмся на сервере; загрузилась — возвращаем выбор.
# Рецензия 0.82: GigaAM грузится в отдельном потоке (не в _brain_watch), не больше одного сразу, только если уже скачан;
# не загрузился из-за нехватки памяти — не повторяем
import threading  # noqa: E402


def retry(e, **k):
    r = e._stt_retry_own(**k)
    th = getattr(e, "_stt_retry_thread", None)
    if th is not None:
        th.join(10)
    return r


ok(retry(e, every=3600) is False and e.s.get("stt", "engine") == "remote", "только что переключили — час не пробуем")
ok(retry(e, every=0) is False and e.s.get("stt", "auto_from") == "gigaam", "своя всё ещё не грузится — сервер, выбор помним")
FakeGiga.gate, FakeGiga.good, n0 = threading.Event(), True, FakeGiga.loads
r0 = e._stt_retry_own(every=0)
th = e._stt_retry_thread
ok(r0 is False and th.is_alive() and th is not threading.current_thread(), "загрузка — в отдельном потоке, проверка мозга не ждёт")
ok(e._stt_retry_own(every=0) is False and e._stt_retry_thread is th, "пока грузится — второй попытки нет")
FakeGiga.gate.set(); th.join(10); FakeGiga.gate = None
ok(FakeGiga.loads == n0 + 1, f"загружали один раз: {FakeGiga.loads - n0}")
st = e.s.get("stt")
ok(st["engine"] == "gigaam" and not st.get("auto_from") and not st["remote"].get("cloud"), f"снова GigaAM, временной замены нет: {st['engine']}")
ok(e.pushes[-1] == "Речь снова распознаёт этот компьютер", "человеку сказали, что вернулись")
# не скачан — не качаем в фоне; упал по памяти — не повторяем
e4 = Eng()
FakeGiga.good = False
e4.gigaam.load()
e4._stt_temp_server(quiet=True)
FakeGiga.have, n0 = False, FakeGiga.loads
ok(retry(e4, every=0) is False and FakeGiga.loads == n0 and getattr(e4, "_stt_retry_thread", None) is None, "модель не скачана — повтор не начинаем")
FakeGiga.have = True
e4.gigaam.oom = True
ok(retry(e4, every=0) is False and FakeGiga.loads == n0 and e4.s.get("stt", "auto_from") == "gigaam", "не загрузилась из-за памяти — не повторяем")
ok(stt.oom_error(MemoryError()) and stt.oom_error(RuntimeError("onnxruntime: Failed to allocate memory for requested buffer"))
   and not stt.oom_error(RuntimeError("No module named 'onnx_asr'")), "нехватка памяти узнаётся (MemoryError, onnxruntime)")
src_s = (ROOT / "core/stt.py").read_text(encoding="utf-8")
ok("self.oom = oom_error(e)" in src_s and "str(e) or type(e).__name__" in src_s, "GigaAM помнит, что упал по памяти; MemoryError без текста — тоже ошибка")

# 4) после перезапуска (обновления): временная замена в настройках — сначала снова выбор человека
e2 = Eng()
e2.s.update({"stt": {"engine": "remote", "auto_from": "gigaam", "remote": {"cloud": True, "base_url": "https://x/"}}})
ok(e2._stt_choice_back() is True, "запуск: была временная замена — пробуем свою модель")
st = e2.s.get("stt")
ok(st["engine"] == "gigaam" and not st.get("auto_from") and not st["remote"].get("cloud"), "после обновления распознавание — снова GigaAM, как выбрано")
FakeGiga.good = False
e2.gigaam.load()
n = len(e2.pushes)
ok(e2._stt_temp_server() and e2.s.get("stt", "auto_from") == "gigaam" and len(e2.pushes) == n,
   "снова не загрузилась — опять временно сервер, без повторного уведомления при каждом запуске")

# 5) человек сам выбрал «Сервер Dewiar» — это не замена: при запуске не трогаем
e3 = Eng()
e3.s.update({"stt": {"engine": "remote", "auto_from": "", "remote": {"cloud": True}}})
ok(e3._stt_choice_back() is False and e3.s.get("stt", "engine") == "remote", "выбранный самим «Сервер Dewiar» остаётся")
e3.s.update({"stt": {"engine": "vosk", "auto_from": "gigaam"}})
ok(e3._stt_choice_back() is False and not e3.s.get("stt", "auto_from"), "выбрал другое сам — память о замене стирается")

# 6) ядро: замена — только через _stt_temp_server (и при сбое загрузки), ручной выбор стирает auto_from
src = (ROOT / "core/engine_brain.py").read_text(encoding="utf-8")
eb = src[src.index("def _ensure_brain"):src.index("def _own_stt_failed")]
ok('self.status.get("stt_ready") is False' not in eb and "self._stt_temp_server()" in eb, "_ensure_brain больше не путает «грузится» и «не загрузился»")
ok("self._stt_retry_own()" in src[src.index("def _brain_watch"):], "раз в час при проверке мозга пробуем свою модель")
ok("self._stt_temp_server()" in (ROOT / "core/engine_audio.py").read_text(encoding="utf-8"), "сбой загрузки GigaAM — сразу временная замена")
ok("self._stt_choice_back()" in (ROOT / "core/engine.py").read_text(encoding="utf-8"), "при запуске — выбор человека")
cmd = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok(cmd.count('{"stt": {"auto_from": ""}}') >= 3, "ручной выбор (настройки, «Сервер Dewiar» по ключу и по аккаунту) стирает замену")

# 7) студия: отмечен выбор человека, строка «Сейчас» — «временно — сервер Dewiar»
js = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok("const sttTemp = () =>" in js and "eng = tmp ||" in js, "в «Слухе» отмечена своя модель, а не временный сервер")
ok("временно — сервер Dewiar, пока своя модель не готова" in js, "строка «Сейчас: временно — сервер Dewiar, пока своя модель не готова»")
ok("renderStatus(); })" in (ROOT / "ui/studio/dewiar.js").read_text(encoding="utf-8"), "строка обновляется вместе с настройками")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
