"""Распознавание речи (фразы целиком, 16 кГц int16): GigaAM v3 локально (onnx-asr), любой OpenAI-совместимый
/audio/transcriptions удалённо (свой сервер или Dewiar Облако), Vosk — запасной: его маленькая модель уже есть
для слова запуска (listen.py), поэтому работает сразу. Выбор движка и зеркала моделей — engine_audio.py.
У всех классов одно лицо: name, transcribe(pcm) -> текст; у GigaAM и удалённого — ещё ready."""

import io
import json
import logging
import os
import re
import threading
import time
import wave
from pathlib import Path

import numpy as np

from settings import MODELS_DIR

log = logging.getLogger("dewiar.stt")


def pcm_to_wav(pcm: bytes, rate=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


class VoskSTT:
    name = "Vosk (запасной)"

    def __init__(self, model):
        self.model = model

    def transcribe(self, pcm: bytes) -> str:
        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(self.model, 16000)
        rec.AcceptWaveform(pcm)
        return json.loads(rec.FinalResult()).get("text", "")


def _heavy():
    """Замок тяжёлых загрузок (ortcfg.HEAVY): слух и голоса грузятся по очереди, а не вместе."""
    try:
        import ortcfg
        return ortcfg.HEAVY
    except Exception:  # noqa: BLE001
        import contextlib
        return contextlib.nullcontext()


def oom_error(e):
    """Ошибка — нехватка памяти (Python MemoryError или onnxruntime «Failed to allocate» / bad_alloc) -> bool."""
    return isinstance(e, MemoryError) or bool(re.search(r"bad_alloc|failed to allocate|out of memory|cannot allocate memory|"
                                                        r"memoryerror|не хватает памяти", str(e), re.I))


class GigaAMSTT:
    def __init__(self, model_name="gigaam-v3-e2e-rnnt"):
        self.model_name = model_name
        self.name = f"GigaAM ({model_name})"
        self.model = None
        self.error = ""
        self.oom = False                # не загрузился из-за нехватки памяти — повторять в фоне бессмысленно
        self.loading = False
        self.mirror = None              # {"url", "sha256"} — архив модели на своём сайте (dewiar.pro/dwrapp)
        self._lock = threading.Lock()

    @property
    def local_dir(self):
        return MODELS_DIR / self.model_name

    def _local_ok(self):
        d = self.local_dir
        return d.is_dir() and any(d.glob("*.onnx")) and any(d.glob("*vocab*.txt"))

    def cached(self):
        """Модель уже есть на диске: своя папка (с зеркала) или полный кэш Hugging Face (HF_HOME = MODELS_DIR/hf)."""
        if self._local_ok():
            return True
        return self._hub_ok()

    def _hub_ok(self):
        """Кэш Hugging Face полный: есть все части нашей модели (у RNNT — кодер, декодер и joint).
        Оборванное скачивание оставляет снимок без кодера, и повторные попытки его не докачивают —
        без этой проверки (и _drop_hub) GigaAM не загрузился бы уже никогда."""
        hub = MODELS_DIR / "hf" / "hub"
        if not hub.is_dir():
            return False
        prefix = self.model_name.removeprefix("gigaam-").replace("-", "_")
        for snap in hub.glob("models--*gigaam*/snapshots/*"):
            names = [p.name for p in snap.glob("*.onnx") if p.stat().st_size > 1024]
            if "rnnt" in prefix:
                if all(any(n.startswith(f"{prefix}_{part}") for n in names) for part in ("encoder", "decoder", "joint")):
                    return True
            elif any(n.startswith(prefix) for n in names):
                return True
        return False

    def _drop_hub(self):
        import shutil
        for d in (MODELS_DIR / "hf" / "hub").glob("models--*gigaam*"):
            shutil.rmtree(d, ignore_errors=True)
        log.info("GigaAM: неполный кэш Hugging Face удалён — скачаю заново")

    def _from_mirror(self, on_progress=None):
        """Архив модели со своего сайта → MODELS_DIR/<модель>/ (с проверкой sha256). Распаковка во временную папку
        и замена целиком — чтобы оборванная распаковка не оставила полупустую папку, которую _local_ok сочтёт годной."""
        import zipfile
        from updater import download
        z = MODELS_DIR / f"{self.model_name}.zip"
        download(self.mirror["url"], z, self.mirror.get("sha256"), on_progress)
        tmp = MODELS_DIR / f"{self.model_name}.tmp"
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(z) as zz:
            for n in zz.namelist():                   # файлы — плоско, без вложенных папок из архива
                if n.endswith("/") or ".." in n:
                    continue
                (tmp / Path(n).name).parent.mkdir(parents=True, exist_ok=True)
                (tmp / Path(n).name).write_bytes(zz.read(n))
        shutil.rmtree(self.local_dir, ignore_errors=True)
        tmp.replace(self.local_dir)
        z.unlink(missing_ok=True)

    def load(self, on_status=None, on_progress=None):
        """Скачивает (один раз, ~250 МБ) и загружает модель. Вызывать в фоне: долго, держит self._lock.
        Порядок: своя папка → зеркало (если модели нет) → кэш/скачивание Hugging Face (int8, иначе полная).
        -> True, если модель готова; иначе причина — в self.error."""
        with self._lock:
            if self.model is not None:
                return True
            self.loading = True
            os.environ.setdefault("HF_HOME", str(MODELS_DIR / "hf"))
            try:
                # №455/№464: после переустановки системы onnx_asr не оказалось — докачиваем сами (pydeps), а не
                # падаем ModuleNotFoundError; не вышло — причина словами (engine скажет, что делать, и слушает Vosk)
                import pydeps
                have, why = pydeps.ensure("onnx_asr", on_status=on_status)
                if not have:
                    raise RuntimeError(why)
                import onnx_asr
                import onnxruntime as _rt
                so = _rt.SessionOptions()           # половина ядер: созвон, браузер и сам компьютер не должны тормозить
                so.intra_op_num_threads = max(1, min(4, (os.cpu_count() or 2) // 2))
                so.inter_op_num_threads = 1
                if on_status:
                    on_status("Загружаю GigaAM — при первом запуске скачивается ~250 МБ")
                t0 = time.monotonic()
                tried = False
                if not self.cached() and self.mirror:
                    tried = True
                    try:
                        log.info("GigaAM: скачиваю со своего сайта %s", self.mirror["url"])
                        self._from_mirror(on_progress)
                    except Exception as e:  # noqa: BLE001
                        log.warning("GigaAM со своего сайта не скачался (%s) — беру с Hugging Face", e)
                if self._local_ok():
                    q = "int8" if any(self.local_dir.glob("*int8*.onnx")) else None
                    with _heavy():                      # не одновременно с загрузкой голосов
                        self.model = onnx_asr.load_model(self.model_name, str(self.local_dir), quantization=q, sess_options=so)
                        self.model.recognize(np.zeros(8000, dtype=np.float32))
                    log.info("GigaAM готов за %.1f с (%s)", time.monotonic() - t0, self.local_dir)
                    self.error = ""
                    return True
                if not self._hub_ok() and any((MODELS_DIR / "hf" / "hub").glob("models--*gigaam*")):
                    self._drop_hub()                       # оборванное скачивание: снимок без кодера — заново
                with _heavy():                          # кэш Hugging Face — тоже не вместе с голосами
                    try:
                        try:
                            self.model = onnx_asr.load_model(self.model_name, quantization="int8", sess_options=so)
                        except Exception as e:  # noqa: BLE001  нет int8-варианта — берём полный
                            log.info("int8-вариант недоступен (%s), загружаю полный", e)
                            self.model = onnx_asr.load_model(self.model_name, sess_options=so)
                    except Exception as e:  # noqa: BLE001
                        if "not found" not in str(e) and "No such file" not in str(e):
                            raise
                        self._drop_hub()                       # файла модели нет — кэш неполный: со своего сайта или заново
                        if self.mirror and not tried:
                            self._from_mirror(on_progress)
                            q = "int8" if any(self.local_dir.glob("*int8*.onnx")) else None
                            self.model = onnx_asr.load_model(self.model_name, str(self.local_dir), quantization=q, sess_options=so)
                        else:
                            self.model = onnx_asr.load_model(self.model_name, sess_options=so)
                    self.model.recognize(np.zeros(8000, dtype=np.float32))     # прогрев
                log.info("GigaAM готов за %.1f с", time.monotonic() - t0)
                self.error = ""
                return True
            except Exception as e:  # noqa: BLE001
                self.error = str(e) or type(e).__name__          # MemoryError() — без текста, а это тоже «не загрузился»
                self.oom = oom_error(e)
                log.warning("GigaAM не загрузился: %s", self.error)
                return False
            finally:
                self.loading = False

    @property
    def ready(self):
        return self.model is not None

    def transcribe(self, pcm: bytes) -> str:
        if self.model is None:
            # пакет 22.10, №194: «'NoneType' object has no attribute 'recognize'» — модель ещё грузится (или не скачалась),
            # а запасного Vosk нет; говорим это словами
            raise RuntimeError("точное распознавание речи ещё загружается — скажите ещё раз через минуту" if self.loading
                               else f"точное распознавание речи не загрузилось{': ' + self.error[:120] if self.error else ''}")
        a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        res = self.model.recognize(a, sample_rate=16000)
        return res if isinstance(res, str) else getattr(res, "text", str(res))


def stt_error_text(stt, e, spare=None):
    """Сбой распознавателя -> подсказка человеку (№455): кто не ответил, что это значит, что делать и чем слушаю пока."""
    name = getattr(stt, "name", "Распознавание")
    cfg = getattr(stt, "cfg", None) or {}
    st = getattr(getattr(e, "response", None), "status_code", None)
    low = str(e).lower()
    if isinstance(stt, RemoteSTT) and cfg.get("cloud"):
        what = "Облако Dewiar сейчас не распознало речь" + (f" (ошибка {st})" if st else "")
        fix = "обычно это ненадолго"
    elif isinstance(stt, RemoteSTT):
        host = re.sub(r"^https?://", "", str(cfg.get("base_url") or "")).split("/")[0] or "сервер"
        if st and st >= 500:
            what = f"Ваш сервер распознавания {host} ответил ошибкой {st} — на нём сбой"
            fix = ("проверьте службу на сервере (журнал: sudo journalctl -u dewiar-speech -n 50); если сервер переустанавливали — "
                   "поставьте службу заново (sudo ./install-server.sh из архива Dewiar Server)")
        elif st in (401, 403):
            what, fix = f"Сервер распознавания {host} не принял ключ (ошибка {st})", "проверьте ключ в студии → «Слух»"
        elif st:
            what, fix = f"Сервер распознавания {host} ответил ошибкой {st}", "проверьте адрес и модель в студии → «Слух»"
        elif any(w in low for w in ("connect", "timed out", "timeout", "refused", "unreachable", "name or service")):
            what, fix = f"Сервер распознавания {host} не отвечает", "проверьте, что он включён и в той же сети"
        else:
            what, fix = f"Сервер распознавания {host} не распознал фразу: {str(e)[:120]}", "проверьте его в студии → «Слух»"
    else:
        what, fix = f"{name} не распознал фразу: {str(e)[:160]}", ""
    pend = f"Пока слушаю {'точным GigaAM на этом компьютере' if isinstance(spare, GigaAMSTT) else 'запасной моделью (она ошибается чаще)'}." \
        if spare is not None else "Другой модели распознавания нет — пока можно писать текстом."
    alt = "" if cfg.get("cloud") or not isinstance(stt, RemoteSTT) else " Или выберите другое распознавание: студия → «Слух»."
    return f"{what}. {pend}" + (f" Что сделать: {fix}." if fix else "") + alt


class RemoteSTT:
    """OpenAI-совместимый сервер распознавания (Whisper, vLLM, шлюзы). base_url — с /v1, путь /audio/transcriptions
    дописывается сам. Ответ — JSON {"text"}; если сервер вернул не JSON — берём тело как текст."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.name = "Dewiar Облако" if cfg.get("cloud") else f"Удалённый ({cfg.get('base_url', '')})"

    @property
    def ready(self):
        return bool(self.cfg.get("base_url"))

    def transcribe(self, pcm: bytes) -> str:
        import httpx
        headers = {}
        if self.cfg.get("api_key"):
            headers["Authorization"] = f"Bearer {self.cfg['api_key']}"
        data = {"model": self.cfg.get("model") or "whisper-1", "language": self.cfg.get("language") or "ru",
                "response_format": "json"}
        r = httpx.post(self.cfg["base_url"].rstrip("/") + "/audio/transcriptions", headers=headers, data=data,
                       files={"file": ("speech.wav", pcm_to_wav(pcm), "audio/wav")}, timeout=30)
        r.raise_for_status()
        try:
            return r.json().get("text", "")
        except ValueError:
            return r.text
