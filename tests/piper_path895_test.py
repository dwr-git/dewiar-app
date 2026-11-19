"""№895 (19.11, Windows 11, «постоянно отваливается ЯДРО»): имя пользователя кириллицей (C:\\Users\\Екатерина), голос —
Piper (Лира сама перешла на него в лёгком режиме: мало памяти). eSpeak внутри Piper не открывает словари по такому пути,
а при неудачном запуске сам завершает весь процесс (exit(1) в espeak_Initialize) — ядро падало через секунды после
каждого ответа голосом, «код выхода 1», без строчки в журнале. Теперь словари — по ASCII-пути (короткое имя 8.3 или копия,
как модели Vosk: listen.kaldi_path), а не вышло — PiperError: голос берётся другой, ядро живёт.
Не в Windows путь «как в Windows» включает DEWIAR_KALDI_NT=1, ASCII-папку задаёт DEWIAR_KALDI_BASE."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st")
import tts  # noqa: E402

try:
    import piper.phonemize_espeak as PE
except Exception:  # noqa: BLE001
    PE = None
if PE is None:
    print("⚠ piper-tts нет — проверяю только устройство")
else:
    real = Path(PE.ESPEAK_DATA_DIR)
    ok(tts.espeak_dir() == real, "обычный путь (Linux, латиница) — словари на месте, без копий")
    cyr = tmp / "Users" / "Екатерина" / "Dewiar" / "piper" / "espeak-ng-data"
    cyr.mkdir(parents=True)
    (cyr / "phontab").write_bytes(b"x" * 100)
    (cyr / "ru_dict").write_bytes(b"y" * 50)
    PE.ESPEAK_DATA_DIR = cyr
    os.environ["DEWIAR_KALDI_NT"] = "1"
    os.environ["DEWIAR_KALDI_BASE"] = str(tmp / "ascii")
    d = tts.espeak_dir()
    ok(str(d).isascii() and d.name.startswith("espeak-ng-data-piper") and (d / "phontab").exists() and (d / ".complete").exists(),
       f"путь с кириллицей — копия словарей в ASCII-папку, с версией Piper в имени: {d}")
    (d / "phontab").write_bytes(b"z")
    ok(tts.espeak_dir() == d and (d / "phontab").read_bytes() == b"z", "второй раз — та же копия, без повторного копирования")
    os.environ["DEWIAR_KALDI_BASE"] = str(tmp / "Папка")
    os.environ.pop("ProgramData", None)
    try:
        tts.espeak_dir()
        ok(False, "нет ASCII-папки — ошибка")
    except tts.PiperError as e:
        ok("не латинскими" in str(e), "ASCII-копии не сделать — PiperError (другой голос), а не падение ядра")
    ok(issubclass(tts.PiperError, RuntimeError), "PiperError — обычная ошибка синтеза: голос берётся следующий")
    PE.ESPEAK_DATA_DIR = real
    os.environ.pop("DEWIAR_KALDI_NT")

src = (ROOT / "core/tts.py").read_text(encoding="utf-8")
ok("espeak_data_dir=espeak_dir()" in src and "except TypeError:" in src, "Piper загружается со своим путём к словарям (старый piper — как раньше)")
ls = (ROOT / "core/listen.py").read_text(encoding="utf-8")
ok('def kaldi_path(model_dir: Path, name: str = "") -> Path:' in ls, "одна функция ASCII-пути для Vosk и eSpeak")
er = (ROOT / "core/engine_remote.py").read_text(encoding="utf-8")
ok("пробую следующий" in er, "ошибка голоса — следующий голос (как и было)")

print("\nИтог:", "всё хорошо" if not fails else f"ошибок {len(fails)}")
sys.exit(1 if fails else 0)
