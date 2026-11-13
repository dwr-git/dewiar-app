"""Распознавание речи GigaAM на видеокарте — для приложений Dewiar (и всего, что понимает API OpenAI).

    POST /v1/audio/transcriptions   (multipart: file=<wav/mp3/ogg…>, response_format)  → {"text": "…", "duration": с}
                                    language=en — английская модель (STT_MODEL_EN, Parakeet), иначе GigaAM; model не влияет
    GET  /v1/models                                                                    → {"data": [{"id": …}]}
    GET  /health                                                                       → {"ok": true, "device": …}
    POST /v1/audio/speech           (если задан TTS_UPSTREAM) — синтез речи: тот же вход по токену сайта, запрос
                                    передаётся на ваш TTS-сервер (vLLM-Omni Qwen3-TTS, server/tts) и звук идёт потоком

Вход: заголовок Authorization: Bearer <api_token пользователя сайта> — проверяется через dwrapp/login.php
(ответ кэшируется на 10 минут), или общий ключ STT_KEY (для своих сервисов). Без токена — 401.
Адрес этой службы сайт сообщает приложению через DWR_STT_URL / DWR_TTS_URL в login.php.

Окружение: STT_MODEL, STT_MODEL_EN, STT_MODEL_DIR, STT_LOGIN_URL, STT_KEY, STT_MAX_MB (25), STT_PORT (8020), STT_FAKE (тесты),
TTS_UPSTREAM, TTS_UPSTREAM_KEY, TTS_MODEL. Нужен ffmpeg для всего, кроме WAV 16 кГц.
Запуск: см. server/stt/README.md (Docker с видеокартой). Без видеокарты тоже работает — на процессоре.
"""

import email.parser
import email.policy
import io
import json
import logging
import os
import subprocess
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

log = logging.getLogger("dewiar-stt")
MODEL = os.environ.get("STT_MODEL", "gigaam-v3-e2e-rnnt")
# 0.96: английская речь (language=en) — Parakeet TDT v2 (NVIDIA, CC-BY-4.0, та же onnx-asr), грузится при первой
# английской фразе; «0» — без неё
MODEL_EN = os.environ.get("STT_MODEL_EN", "nemo-parakeet-tdt-0.6b-v2")
MODEL_EN = "" if MODEL_EN in ("0", "off") else MODEL_EN
LOGIN_URL = os.environ.get("STT_LOGIN_URL", "http://app/dwrapp/login.php")     # внутри docker-сети сайта
STATIC_KEY = os.environ.get("STT_KEY", "")
MAX_BYTES = int(os.environ.get("STT_MAX_MB", "25")) * 1024 * 1024
FAKE = os.environ.get("STT_FAKE")             # тесты: вместо модели — длина звука в секундах
TTS_UPSTREAM = os.environ.get("TTS_UPSTREAM", "").rstrip("/")   # например http://dewiar-tts:8091/v1
TTS_UPSTREAM_KEY = os.environ.get("TTS_UPSTREAM_KEY", "")
TTS_MODEL = os.environ.get("TTS_MODEL", "")                     # подставить свою модель (приложение шлёт «tts-1»)

_model, _device, _lock = None, "cpu", threading.Lock()
_en = {"model": None, "err": ""}                 # английская модель: загружается при первой английской фразе
_tokens = {}                                   # токен → срок проверки


def load():
    global _model, _device
    if FAKE:
        _device = "fake"
        return
    import onnx_asr
    import onnxruntime as ort
    prov = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
    _model = onnx_asr.load_model(MODEL, os.environ.get("STT_MODEL_DIR") or None, providers=prov)
    _device = "cuda" if prov and prov[0] == "CUDAExecutionProvider" else "cpu"
    _model.recognize(np.zeros(8000, dtype=np.float32))                     # прогрев
    log.info("GigaAM %s готов (%s)", MODEL, _device)


def decode(data: bytes):
    """Любой звук → float32 mono 16 кГц. WAV 16 кГц — сразу, остальное — через ffmpeg."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            if w.getframerate() == 16000 and w.getsampwidth() == 2:
                a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                if w.getnchannels() > 1:
                    a = a.reshape(-1, w.getnchannels()).mean(axis=1)
                return a.astype(np.float32) / 32768.0
    except (wave.Error, EOFError):
        pass
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
                       input=data, capture_output=True, timeout=120)
    if r.returncode:
        raise ValueError("не удалось прочитать звук: " + r.stderr.decode(errors="replace")[-200:])
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _model_en():
    """Английская модель (под _lock) или None — не загрузилась: тогда слушает GigaAM, причина — в журнале."""
    if _en["model"] is None and not _en["err"]:
        try:
            import onnx_asr
            import onnxruntime as ort
            prov = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
            _en["model"] = onnx_asr.load_model(MODEL_EN, providers=prov)
            log.info("Английская модель %s готова", MODEL_EN)
        except Exception as e:  # noqa: BLE001
            _en["err"] = str(e) or type(e).__name__
            log.warning("Английская модель %s не загрузилась: %s", MODEL_EN, _en["err"])
    return _en["model"]


def recognize(audio, lang=""):
    en = bool(MODEL_EN) and str(lang or "").lower().startswith("en")
    if FAKE:
        return f"recognized {len(audio) / 16000:.1f} seconds" if en else f"распознано {len(audio) / 16000:.1f} секунды"
    with _lock:                                  # одна видеокарта — по очереди, фраза за доли секунды
        m = (_model_en() if en else None) or _model
        res = m.recognize(audio, sample_rate=16000)
    return res if isinstance(res, str) else getattr(res, "text", str(res))


def allowed(auth):
    """Пускать ли запрос: общий ключ STT_KEY или действующий api_token сайта (проверка через login.php,
    удачная запоминается на 10 минут — отозванный токен столько ещё действует)."""
    if not auth.startswith("Bearer "):
        return False
    tok = auth[7:].strip()
    if STATIC_KEY and tok == STATIC_KEY:
        return True
    now = time.time()
    if _tokens.get(tok, 0) > now:
        return True
    try:
        import urllib.request
        req = urllib.request.Request(LOGIN_URL, headers={"Authorization": "Bearer " + tok, "X-App-Id": "dewiar-stt"})
        with urllib.request.urlopen(req, timeout=8) as r:
            ok = r.status == 200 and json.loads(r.read().decode()).get("ok")
    except Exception:  # noqa: BLE001 — 401 или сайт недоступен
        ok = False
    if ok:
        _tokens[tok] = now + 600
    return bool(ok)


class H(BaseHTTPRequestHandler):
    server_version = "dewiar-stt/1"

    def log_message(self, fmt, *a):
        log.info("%s %s", self.address_string(), fmt % a)

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path.endswith("/health"):
            return self._json(200, {"ok": True, "model": MODEL, "device": _device})
        if path.endswith("/models"):
            return self._json(200, {"data": [{"id": MODEL, "object": "model"}, {"id": "gigaam-v3", "object": "model"}]
                                    + ([{"id": MODEL_EN, "object": "model", "language": "en"}] if MODEL_EN else [])})
        self._json(404, {"error": "not found"})

    def _speech(self):
        """Синтез: проверили токен сайта — передаём запрос на TTS-сервер и отдаём звук потоком, как он идёт."""
        import urllib.error
        import urllib.request
        if not TTS_UPSTREAM:
            return self._json(404, {"error": {"message": "синтез речи на этом сервере не настроен (TTS_UPSTREAM)"}})
        if not allowed(self.headers.get("Authorization", "")):
            return self._json(401, {"error": {"message": "нужен вход: Authorization: Bearer <api_token>"}})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 200_000:
            return self._json(413, {"error": {"message": "пустой или слишком длинный запрос"}})
        body = self.rfile.read(n)
        if TTS_MODEL:
            try:
                d = json.loads(body)
                d["model"] = TTS_MODEL
                body = json.dumps(d, ensure_ascii=False).encode()
            except ValueError:
                return self._json(400, {"error": {"message": "нужен JSON"}})
        hdr = {"Content-Type": "application/json"}
        if TTS_UPSTREAM_KEY:
            hdr["Authorization"] = "Bearer " + TTS_UPSTREAM_KEY
        req = urllib.request.Request(TTS_UPSTREAM + "/audio/speech", data=body, headers=hdr, method="POST")
        try:
            up = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            return self._json(e.code, {"error": {"message": e.read()[:300].decode(errors="replace")}})
        except OSError as e:
            return self._json(502, {"error": {"message": f"TTS-сервер недоступен: {e}"}})
        with up:
            self.send_response(200)
            self.send_header("Content-Type", up.headers.get("Content-Type", "application/octet-stream"))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while True:
                chunk = up.read1(8192) if hasattr(up, "read1") else up.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        self.close_connection = True               # длина звука заранее не известна — конец ответа = закрытие соединения

    def do_POST(self):
        if self.path.split("?")[0].rstrip("/").endswith("/audio/speech"):
            return self._speech()
        if not self.path.split("?")[0].rstrip("/").endswith("/audio/transcriptions"):
            return self._json(404, {"error": "not found"})
        if not allowed(self.headers.get("Authorization", "")):
            return self._json(401, {"error": {"message": "нужен вход: Authorization: Bearer <api_token>"}})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BYTES:
            return self._json(413, {"error": {"message": f"файл больше {MAX_BYTES // 1048576} МБ или пустой"}})
        body = self.rfile.read(n)
        ctype = self.headers.get("Content-Type", "")
        msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + body)
        fields, data = {}, None
        for part in msg.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name == "file":
                data = part.get_payload(decode=True)
            elif name:
                fields[name] = part.get_content().strip() if part.get_content_maintype() == "text" else ""
        if not data:
            return self._json(400, {"error": {"message": "нет поля file"}})
        t0 = time.monotonic()
        try:
            audio = decode(data)
            text = recognize(audio, fields.get("language", "")).strip()
        except Exception as e:  # noqa: BLE001
            log.exception("распознавание")
            return self._json(500, {"error": {"message": str(e)[:300]}})
        log.info("%.1f с звука → %d симв. за %d мс", len(audio) / 16000, len(text), (time.monotonic() - t0) * 1000)
        if fields.get("response_format") == "text":
            b = text.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        self._json(200, {"text": text, "duration": round(len(audio) / 16000, 2)})


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load()
    port = int(os.environ.get("STT_PORT", "8020"))
    log.info("Слушаю :%d", port)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    main()
