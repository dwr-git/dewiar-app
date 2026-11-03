"""№455/№464 (01.11, ПК 0.76.0): «не загружаются onnx_asr» — распознавание речи падало ModuleNotFoundError.
— №455: на своём сервере распознавания (Ubuntu переустановили с нуля) не оказалось onnx_asr: сервер отвечал 500, а Лира
  молча переходила на маленький Vosk («эйра сколько время»). Теперь запасной — GigaAM на этом компьютере, если загружен,
  и подсказка словами: сервер ответил ошибкой — что сделать;
— onnx_asr нет на этом компьютере — ядро докачивает его само (core/pydeps.py, своя папка, без зависимостей); не вышло —
  понятная причина, как починить и «через облако»; установщик Linux (dewiar-env) — по одной библиотеке, если общий список
  не встал;
— №464: диагностика Windows писала «ОШИБКА onnx_asr: код 3221225477», хотя ядро GigaAM загрузило: сбой процесса
  проверки — повтор и словами; в журнале ядра «GigaAM готов» — не ошибка; «нет связи с моделью» — в ИТОГ."""
import os, subprocess, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import pydeps  # noqa: E402

# ---------- докачка библиотеки ----------
ok(pydeps.ensure("json") == (True, ""), "библиотека на месте — ничего не качаем")
calls = []


def fake_run(cmd, **kw):
    calls.append(cmd)
    i = cmd.index("--target")
    d = Path(cmd[i + 1]) / "dwr_fake_mod"
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").write_text("X = 5\n")
    return subprocess.CompletedProcess(cmd, 0, "", "")


pydeps.PACKAGES["dwr_fake_mod"] = "dwr-fake-mod>=1"
st = []
good, why = pydeps.ensure("dwr_fake_mod", on_status=st.append, run=fake_run)
import importlib  # noqa: E402
ok(good and why == "" and importlib.import_module("dwr_fake_mod").X == 5, f"нет библиотеки — докачана в свою папку и загружается: {why}")
ok(calls and "--no-deps" in calls[0] and str(pydeps.extra_dir()) in calls[0] and "dwr-fake-mod>=1" in calls[0],
   "ставится только сама библиотека (--no-deps), в STATE_DIR/pylib")
ok(sys.path[-1] == str(pydeps.extra_dir()) or str(pydeps.extra_dir()) in sys.path[-3:], "своя папка — в конце sys.path (основное не перекрывает)")
ok(st and "Докачиваю" in st[0], f"человеку сказано, что докачиваем: {st}")


def bad_run(cmd, **kw):
    calls.append(cmd)
    return subprocess.CompletedProcess(cmd, 1, "", "ERROR: Could not find a version (ConnectionError: Failed to establish a new connection)")


pydeps.PACKAGES["dwr_fake_two"] = "dwr-fake-two"
calls.clear()
good, why = pydeps.ensure("dwr_fake_two", run=bad_run)
ok(not good and "не хватает библиотеки dwr_fake_two" in why and "pypi.org" in why, f"не вышло — причина словами: {why}")
n = len(calls)
good2, why2 = pydeps.ensure("dwr_fake_two", run=bad_run)
ok(not good2 and len(calls) == n and why2 == why, "второй раз за запуск не качаем снова")
ok("dewiar-env" in pydeps.fix_hint() or "pip install" in pydeps.fix_hint() or "переустановите" in pydeps.fix_hint(), "есть подсказка, как починить")

# ---------- GigaAM: библиотеки нет и не докачалась ----------
import stt as S  # noqa: E402
real = pydeps.ensure
pydeps.ensure = lambda m, on_status=None, run=None: (False, "не хватает библиотеки onnx_asr, и докачать её не вышло: нет связи с pypi.org (интернет или прокси)")
g = S.GigaAMSTT("gigaam-v3-e2e-rnnt")
ok(g.load() is False and "библиотеки onnx_asr" in g.error, f"GigaAM не загрузился — причина в error: {g.error}")
pydeps.ensure = real
import engine_audio as EA  # noqa: E402
t = EA.AudioMixin._gigaam_fail_text(g.error)
ok("Пока слушаю запасной" in t and "Починить" in t and "Dewiar Облако" in t, f"подсказка человеку — что делать и запасной путь: {t}")
ok("GigaAM не загрузился: файл повреждён. Работаю на Vosk." == EA.AudioMixin._gigaam_fail_text("файл повреждён"), "другие причины — как раньше")
src = (ROOT / "core/stt.py").read_text(encoding="utf-8")
ok('pydeps.ensure("onnx_asr", on_status=on_status)' in src, "загрузка GigaAM сначала докачивает onnx_asr")

# ---------- №455: свой сервер распознавания ответил 500 ----------
import httpx  # noqa: E402
req = httpx.Request("POST", "http://192.168.3.123:8090/v1/audio/transcriptions")
e500 = httpx.HTTPStatusError("Server error '500 Internal Server Error'", request=req, response=httpx.Response(500, request=req))
remote = S.RemoteSTT({"base_url": "http://192.168.3.123:8090/v1", "model": "whisper-turbo"})


class Fake:
    def __init__(self, name, ready=True):
        self.name, self.ready = name, ready

    def transcribe(self, pcm):
        return "Лира, сколько время"


giga, vosk = S.GigaAMSTT("gigaam-v3-e2e-rnnt"), Fake("Vosk")
giga.model = Fake("m")
notes = []
eng = types.SimpleNamespace(gigaam=giga, vosk_stt=vosk, note=notes.append)
spare = EA.AudioMixin._stt_spare(eng, remote, e500)
ok(spare is giga, "сервер распознавания упал — запасной точный GigaAM этого компьютера, а не маленький Vosk")
ok(notes and "192.168.3.123:8090" in notes[0] and "ошибкой 500" in notes[0] and "install-server" in notes[0] and "GigaAM" in notes[0],
   f"подсказка: сервер ответил ошибкой — как проверить и поставить заново; чем слушаю пока: {notes}")
EA.AudioMixin._stt_spare(eng, remote, e500)
ok(len(notes) == 1, "та же беда — подсказка не чаще раза в 10 минут")
eng2 = types.SimpleNamespace(gigaam=None, vosk_stt=vosk, note=[].append)
ok(EA.AudioMixin._stt_spare(eng2, remote, e500) is vosk, "GigaAM не загружен — Vosk, как раньше")
nt = []
eng3 = types.SimpleNamespace(gigaam=None, vosk_stt=None, note=nt.append)
ok(EA.AudioMixin._stt_spare(eng3, remote, e500) is None and "писать текстом" in nt[0], f"запасного нет — сказано честно: {nt}")
cloud = S.RemoteSTT({"base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "cloud": True})
ok("Облако Dewiar" in S.stt_error_text(cloud, e500, vosk), "облако — своими словами, без советов про свой сервер")
eto = httpx.ConnectTimeout("timed out")
ok("не отвечает" in S.stt_error_text(remote, eto, vosk), "сервер не отвечает — так и сказано")
asrc = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok(asrc.count("self._stt_spare(") >= 2 and "пробую Vosk" not in asrc, "фразы и диктовка — через _stt_spare")

# ---------- установщик Linux: по одной, если общий список не встал ----------
env = (ROOT / "packaging/dewiar-env").read_text(encoding="utf-8")
ok("def install_each(" in env and "return install_each(have_uv, cmd)" in env and 'import onnx_asr' in env, "dewiar-env: по одной библиотеке и проверка onnx_asr")
ns = {"__name__": "x"}
exec(compile(env, "dewiar-env", "exec"), ns)
rq = tmp / "requirements.txt"; rq.write_text("numpy>=1.24\nonnx-asr>=0.12\ntruststore>=0.10        # коммент\n\n")
ns["REQ"] = rq
ok(ns["requirements"]() == ["numpy>=1.24", "onnx-asr>=0.12", "truststore>=0.10"], "строки requirements без комментариев")

# ---------- №464: диагностика Windows ----------
sys.path.insert(0, str(ROOT / "ui"))
import doctor  # noqa: E402
ok("0xC0000005" in doctor.crash_text(3221225477) and "памяти" in doctor.crash_text(3221225477) and doctor.crash_text(1) == "",
   f"код 3221225477 — словами: {doctor.crash_text(3221225477)}")
seq = [3221225477, 0]
orig = doctor.subprocess.run
doctor.subprocess.run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, seq.pop(0), "0.12.1\n" if not seq else "", "")
good, info = doctor.check_module("onnx_asr")
doctor.subprocess.run = orig
ok(good and "со второго раза" in info, f"сбой процесса проверки — повтор: {info}")
log = ["14:44:16 INFO    dewiar.stt: GigaAM готов за 29.6 с"]
ok("работает" in doctor.works_in_core("onnx_asr", log) and doctor.works_in_core("onnx_asr", []) == "", "в журнале ядра «GigaAM готов» — не ошибка")
cl = ["13:31:21 INFO    dewiar.llm: Сервер модели: соединение не установилось (ConnectTimeout)"] * 4
ok("нет связи" in doctor.net_note(cl) and doctor.net_note(log) == "", "модель не отвечает — в ИТОГ")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
