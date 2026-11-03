#!/usr/bin/env python3
"""Dewiar Speech — распознавание речи GigaAM и русские голоса Vosk TTS с API как у OpenAI для своего сервера (FastAPI).

Ставится server/install-server.sh как служба dewiar-speech, настройки — /etc/dewiar-server.env. Это не server/stt:
там вход по токену сайта, здесь — один общий ключ.

    POST /v1/audio/transcriptions   (multipart: file, model, language, response_format) — model и language не влияют
    POST /v1/audio/speech           (JSON: input, voice, speed, response_format wav|mp3|opus|pcm) — голос Vosk TTS на CPU:
                                    голоса персонажей Dewiar (serena, aiden…) — разные дикторы модели по полу; «vosk:N» — диктор N
    GET  /v1/models
    GET  /health                    (без ключа)
    GET  /.well-known/dewiar.json   описание сервера для клиентов (файл DEWIAR_MANIFEST от install-server.sh)

Работает на GPU (onnxruntime-gpu), если он есть, иначе на CPU. Модель грузится в фоне при запуске.
Окружение: DEWIAR_SPEECH_KEY — ключ доступа (пусто = без ключа, только для доверенной сети);
DEWIAR_SPEECH_MODEL; DEWIAR_SPEECH_TTS — модель голосов (vosk-model-tts-ru-0.9-multi; «0» — без голоса);
DEWIAR_SPEECH_TTS_DIR — куда её скачать; DEWIAR_SPEECH_FAKE — тесты без моделей. Нужен ffmpeg для всего, кроме WAV
16 кГц mono, и для ответа голосом в mp3/opus (без ffmpeg — WAV).
"""

import asyncio
import io
import logging
import os
import subprocess
import threading
import time
import wave

import numpy as np
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response

MODEL = os.environ.get("DEWIAR_SPEECH_MODEL", "gigaam-v3-e2e-rnnt")
KEY = os.environ.get("DEWIAR_SPEECH_KEY", "")
CHUNK_S = 22                         # GigaAM рассчитан на фразы до ~25 с — длинное режем
log = logging.getLogger("dewiar.speech")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Dewiar Speech")
_model, _lock, _model_err = None, threading.Lock(), ""


def model():
    """Модель, загруженная при первом обращении (под _lock: тот же замок держит распознавание)."""
    global _model
    with _lock:
        if _model is None:
            if os.environ.get("DEWIAR_SPEECH_FAKE"):          # для тестов без скачивания модели
                class Fake:
                    def recognize(self, a, sample_rate=16000):
                        return f"тест {len(a) / sample_rate:.1f} секунды"
                _model = Fake()
                return _model
            # №455 (01.11: Ubuntu переустановили — «onnx_asr снова нет, распознавание обрывается»): нет библиотеки — не 500
            # без объяснений, а 503 со словами, что поставить; ошибка видна и в /health
            global _model_err
            try:
                import onnx_asr
                import onnxruntime as rt
            except ImportError as e:
                _model_err = (f"не установлена библиотека {e.name or 'onnx-asr'} — запустите install-server.sh заново "
                              "или: pip install onnx-asr[cpu,hub] onnxruntime")
                log.error("Распознавание: %s", _model_err)
                raise HTTPException(503, _model_err) from e
            prov = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in rt.get_available_providers()]
            log.info("Загружаю %s на %s …", MODEL, prov[0])
            t0 = time.time()
            _model = onnx_asr.load_model(MODEL, providers=prov)
            _model.recognize(np.zeros(16000, dtype=np.float32))
            _model_err = ""
            log.info("Готово за %.1f с", time.time() - t0)
        return _model


def to_pcm16k(data: bytes) -> np.ndarray:
    """WAV 16 кГц mono читаем сами, всё остальное (mp3, ogg, webm, другие частоты) — через ffmpeg."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            if w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2:
                return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    except (wave.Error, EOFError):
        pass
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
                       input=data, capture_output=True, timeout=120)
    if r.returncode:
        raise HTTPException(400, f"не удалось прочитать аудио: {r.stderr.decode()[:200]}")
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768


def auth(authorization: str = Header(default="")):
    if KEY and authorization != f"Bearer {KEY}":
        raise HTTPException(401, "неверный ключ")


MANIFEST = os.environ.get("DEWIAR_MANIFEST", "/etc/dewiar-server/dewiar.json")


@app.get("/.well-known/dewiar.json")
@app.get("/dewiar.json")
def manifest():
    """Описание сервера для клиентов Dewiar: ввёл адрес — всё настроилось.
    Секретов тут нет: ключ пользователь вводит сам, в файле — заглушка ${KEY}."""
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            import json
            data = json.load(f)
    except (OSError, ValueError):
        raise HTTPException(404, "описание сервера не настроено")
    return JSONResponse(data, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=300"})


@app.get("/health")
def health():
    return {"ok": not _model_err, "model": MODEL, "loaded": _model is not None, "error": _model_err,
            "tts": TTS_MODEL if TTS_ON else "", "tts_loaded": _tts is not None, "tts_error": _tts_err}


@app.get("/v1/models", dependencies=[Depends(auth)])
def models():
    data = [{"id": MODEL, "object": "model", "owned_by": "dewiar"}]
    if TTS_ON:
        data.append({"id": "vosk-tts", "object": "model", "owned_by": "dewiar", "type": "tts"})
    return {"object": "list", "data": data}


@app.post("/v1/audio/transcriptions", dependencies=[Depends(auth)])
async def transcribe(file: UploadFile = File(...), model_name: str = Form("", alias="model"),
                     language: str = Form("ru"), response_format: str = Form("json")):
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, f"файл больше {MAX_BYTES // 1048576} МБ")
    t0 = time.time()
    # декодирование и распознавание — в потоке: иначе они держат цикл событий, и пока идёт одна запись, сервер
    # не отвечает даже на /health
    text, secs = await asyncio.get_running_loop().run_in_executor(None, _recognize, raw)
    log.info("%.1f с аудио → %d мс: %s", secs, (time.time() - t0) * 1000, text[:80])
    if response_format == "text":
        return PlainTextResponse(text)
    return JSONResponse({"text": text, "duration": round(secs, 2)})


MAX_BYTES = 50 * 1024 * 1024                 # 50 МБ — больше получаса речи в WAV 16 кГц


def _recognize(raw):
    audio = to_pcm16k(raw)
    m = model()
    step = CHUNK_S * 16000
    with _lock:
        parts = [m.recognize(audio[i:i + step], sample_rate=16000) for i in range(0, max(len(audio), 1), step)]
    return " ".join(str(p).strip() for p in parts if str(p).strip()), len(audio) / 16000


# ---------- голос: Vosk TTS (Alpha Cephei, Apache 2.0) — та же модель, что у Dewiar на компьютере (core/tts.py) ----------

TTS_MODEL = os.environ.get("DEWIAR_SPEECH_TTS", "vosk-model-tts-ru-0.9-multi")
TTS_ON = TTS_MODEL not in ("", "0", "off")
TTS_DIR = os.environ.get("DEWIAR_SPEECH_TTS_DIR") or os.path.join(os.environ.get("HF_HOME") or os.path.expanduser("~"), "vosk-tts")
TTS_URLS = ["https://dewiar.pro/dwrapp/models/{name}.zip", "https://alphacephei.com/vosk/models/{name}.zip"]
TTS_RATE = 22050
# Голоса персонажей Dewiar названы по Qwen3-TTS (core/personas.py, voice.remote). Здесь — дикторы модели 0.9-multi:
# 0–2 женские, 3–4 мужские; разным персонажам одного пола — по возможности разные дикторы.
VOICES = {"serena": 0, "vivian": 1, "ono_anna": 2, "sohee": 2, "dylan": 3, "ryan": 4, "eric": 3, "aiden": 4, "uncle_fu": 3,
          "alloy": 0, "nova": 1, "shimmer": 2, "echo": 3, "onyx": 4, "fable": 3}
_tts, _tts_lock, _tts_err = None, threading.Lock(), ""


def _tts_download(dst):
    """Скачать и распаковать модель голосов (~0,2 ГБ) — один раз, сначала с dewiar.pro, затем с alphacephei.com."""
    import urllib.request
    import zipfile
    os.makedirs(TTS_DIR, exist_ok=True)
    err = ""
    for url in TTS_URLS:
        part = os.path.join(TTS_DIR, TTS_MODEL + ".zip.part")
        try:
            log.info("Скачиваю голоса %s …", url.format(name=TTS_MODEL))
            with urllib.request.urlopen(url.format(name=TTS_MODEL), timeout=60) as r, open(part, "wb") as f:
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        break
                    f.write(b)
            with zipfile.ZipFile(part) as z:
                z.extractall(TTS_DIR)
            os.remove(part)
            if os.path.exists(os.path.join(dst, "model.onnx")):
                return
            err = "в архиве нет model.onnx"
        except Exception as e:  # noqa: BLE001 — пробуем следующий адрес
            err = str(e)
            try:
                os.remove(part)
            except OSError:
                pass
    raise RuntimeError(f"голоса не скачались: {err}")


def tts():
    """Синтезатор, загруженный при первом обращении (в фоне при запуске). Свой замок: голос не ждёт распознавание."""
    global _tts, _tts_err
    with _tts_lock:
        if _tts is None:
            if os.environ.get("DEWIAR_SPEECH_FAKE"):
                class Fake:                                  # тон 220/330 Гц длиной по тексту — для проверок
                    def synth_audio(self, text, speaker_id=0, speech_rate=None):
                        n = int(TTS_RATE * min(10.0, 0.06 * len(text) / (speech_rate or 1.0)))
                        t = np.arange(n) / TTS_RATE
                        return (np.sin(2 * np.pi * (220 + 110 * (speaker_id >= 3)) * t) * 8000).astype(np.int16)
                _tts = Fake()
                return _tts
            from vosk_tts import Model, Synth
            path = os.path.join(TTS_DIR, TTS_MODEL)
            if not os.path.exists(os.path.join(path, "model.onnx")):
                _tts_download(path)
            t0 = time.time()
            _tts = Synth(Model(model_path=path))
            log.info("Голоса готовы за %.1f с", time.time() - t0)
        return _tts


def _speech_norm(text):
    """Числа словами, латиница русскими буквами — speechnorm.py от Dewiar (install-server.sh кладёт его рядом)."""
    try:
        from speechnorm import speech_norm
        return speech_norm(text) or text
    except ImportError:
        return text


def _speaker(voice):
    v = str(voice or "").strip().lower()
    if v.startswith("vosk:") and v[5:].isdigit():
        return int(v[5:])
    if v in VOICES:
        return VOICES[v]
    return sum(map(ord, v)) % 5 if v else 0


def _synth(text, voice, speed):
    """Текст -> int16 PCM 22 050 Гц. Длинный текст — по предложениям (модель лучше держит короткие куски)."""
    import re
    s = tts()
    spk, rate = _speaker(voice), max(0.5, min(2.0, float(speed or 1.0)))
    parts = [p for p in re.split(r"(?<=[.!?…])\s+", _speech_norm(text)) if p.strip()] or [text]
    out = []
    for p in parts:
        try:
            a = s.synth_audio(p, speaker_id=spk, speech_rate=rate)
        except Exception:  # noqa: BLE001 — редкие символы: только русские буквы и знаки, тот же голос
            simple = re.sub(r"[^А-Яа-яЁё ,.!?—-]+", " ", p).strip()
            if not simple:
                continue
            a = s.synth_audio(simple, speaker_id=spk, speech_rate=rate)
        out.append(np.asarray(a, dtype=np.int16))
        out.append(np.zeros(int(TTS_RATE * 0.18), dtype=np.int16))       # пауза между предложениями
    return np.concatenate(out) if out else np.zeros(1, dtype=np.int16)


def _encode(pcm, fmt):
    """PCM -> (байты, тип). wav — сами; mp3/opus/aac/flac — ffmpeg (его нет — WAV). На «pcm» тоже WAV: частота здесь
    22 050 Гц, а клиенты по умолчанию ждут сырой звук 24 кГц (как у OpenAI) — с заголовком частоту берут из него
    (core/tts.py RemoteTTS), и голос не звучит ускоренным при любой настройке sample_rate."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TTS_RATE)
        w.writeframes(pcm.tobytes())
    wav = buf.getvalue()
    if fmt in ("mp3", "opus", "aac", "flac"):
        codec = {"mp3": ["-f", "mp3", "-b:a", "64k"], "opus": ["-f", "ogg", "-c:a", "libopus", "-b:a", "32k"],
                 "aac": ["-f", "adts"], "flac": ["-f", "flac"]}[fmt]
        try:
            r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", *codec, "pipe:1"], input=wav,
                               capture_output=True, timeout=120)
            if r.returncode == 0 and r.stdout:
                return r.stdout, {"mp3": "audio/mpeg", "opus": "audio/ogg", "aac": "audio/aac", "flac": "audio/flac"}[fmt]
        except (OSError, subprocess.SubprocessError):
            pass
    return wav, "audio/wav"


@app.post("/v1/audio/speech", dependencies=[Depends(auth)])
async def speech(body: dict):
    if not TTS_ON:
        raise HTTPException(404, "голос на этом сервере выключен (DEWIAR_SPEECH_TTS=0)")
    text = str(body.get("input") or "").strip()
    if not text:
        raise HTTPException(400, "нужно поле input — текст для озвучки")
    if len(text) > 5000:
        raise HTTPException(413, "не больше 5000 знаков за раз")
    t0 = time.time()
    try:
        pcm = await asyncio.get_running_loop().run_in_executor(None, _synth, text, body.get("voice"), body.get("speed"))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    data, ctype = _encode(pcm, str(body.get("response_format") or "mp3").lower())
    log.info("голос %s: %d знаков → %.1f с звука за %d мс", body.get("voice") or "-", len(text), len(pcm) / TTS_RATE,
             (time.time() - t0) * 1000)
    return Response(content=data, media_type=ctype)


def _warm_tts():
    global _tts_err
    try:
        tts()
    except Exception as e:  # noqa: BLE001 — без голосов распознавание всё равно работает
        _tts_err = str(e)
        log.warning("Голоса не загрузились: %s", e)


@app.on_event("startup")
def warm():
    threading.Thread(target=model, daemon=True).start()
    if TTS_ON:
        threading.Thread(target=_warm_tts, daemon=True).start()
