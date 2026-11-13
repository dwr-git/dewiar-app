"""Сервер речи (server/speech/server.py): распознавание и голос Vosk TTS с API как у OpenAI — без моделей
(DEWIAR_SPEECH_FAKE). Голос нужен телефонам без русского синтеза (планшет Huawei без Google): облако отдаёт
/audio/speech с этого сервера (DEWIAR_CLOUD_TTS в .env сайта)."""
import io, os, shutil, sys, wave
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ.update(DEWIAR_SPEECH_FAKE="1", DEWIAR_SPEECH_KEY="k1", DEWIAR_MANIFEST="/nonexistent")
sys.path.insert(0, str(ROOT / "server/speech")); sys.path.insert(1, str(ROOT / "core"))
try:
    from fastapi.testclient import TestClient
except ImportError:
    print("✅ пропуск: нет fastapi"); sys.exit(0)
import server  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


H = {"Authorization": "Bearer k1"}
with TestClient(server.app) as c:
    h = c.get("/health").json()
    ok(h.get("tts") == "vosk-model-tts-ru-0.9-multi", f"/health называет голоса: {h}")
    ok(any(m["id"] == "vosk-tts" for m in c.get("/v1/models", headers=H).json()["data"]), "голос в /v1/models")
    ok(c.post("/v1/audio/speech", json={"input": "Привет"}).status_code == 401, "без ключа — 401")
    r = c.post("/v1/audio/speech", headers=H, json={"input": "Сейчас в Минске 12 градусов. Ветер слабый!", "voice": "serena",
                                                   "response_format": "wav"})
    ok(r.status_code == 200 and r.headers["content-type"].startswith("audio/wav"), f"WAV: {r.status_code} {r.headers.get('content-type')}")
    with wave.open(io.BytesIO(r.content)) as w:
        ok(w.getframerate() == 22050 and w.getnchannels() == 1 and w.getnframes() > 22050, f"звук 22 кГц, {w.getnframes() / 22050:.1f} с")
    ok(server._speaker("serena") != server._speaker("aiden") and server._speaker("serena") < 3 <= server._speaker("aiden"),
       "героиня — женский диктор, герой — мужской")
    ok(server._speaker("vivian") != server._speaker("serena"), "разные героини — разные голоса")
    ok(server._speaker("vosk:4") == 4, "«vosk:N» — диктор N")
    ok("двенадцать" in server._speech_norm("12 градусов"), "числа словами (speechnorm)")
    r = c.post("/v1/audio/speech", headers=H, json={"input": "Проверка.", "response_format": "pcm"})
    ok(r.status_code == 200 and r.content[:4] == b"RIFF", "на «pcm» — WAV с частотой в заголовке (не звучит ускоренным)")
    r = c.post("/v1/audio/speech", headers=H, json={"input": "Проверка голоса."})
    if shutil.which("ffmpeg"):
        ok(r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3"),
           f"по умолчанию mp3 (как OpenAI): {r.headers.get('content-type')}")
    else:
        ok(r.status_code == 200 and r.headers["content-type"] == "audio/wav", "без ffmpeg — WAV")
    ok(c.post("/v1/audio/speech", headers=H, json={"input": ""}).status_code == 400, "пустой текст — 400")
    ok(c.post("/v1/audio/speech", headers=H, json={"input": "а" * 5001}).status_code == 413, "длиннее 5000 — 413")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * 32000)
    r = c.post("/v1/audio/transcriptions", headers=H, files={"file": ("a.wav", buf.getvalue(), "audio/wav")})
    ok(r.status_code == 200 and "2.0" in r.json()["text"], f"распознавание по-прежнему: {r.json()}")
    # 0.96: language=en — английская модель (GigaAM слышит только русский)
    r = c.post("/v1/audio/transcriptions", headers=H, data={"language": "en", "model": "gigaam"},
               files={"file": ("a.wav", buf.getvalue(), "audio/wav")})
    ok(r.status_code == 200 and r.json()["text"].startswith("test "), f"английская речь — Parakeet: {r.json()}")
    ok(any(m["id"] == server.MODEL_EN for m in c.get("/v1/models", headers=H).json()["data"]), "английская модель — в списке")
    # №455 (01.11): Ubuntu переустановили — onnx_asr нет: не голый 500, а 503 со словами, что поставить; видно в /health
    os.environ.pop("DEWIAR_SPEECH_FAKE"); server._model = None
    import builtins
    real_imp = builtins.__import__

    def no_asr(name, *a, **kw):
        if name == "onnx_asr":
            raise ImportError("No module named 'onnx_asr'", name="onnx_asr")
        return real_imp(name, *a, **kw)
    builtins.__import__ = no_asr
    try:
        r = c.post("/v1/audio/transcriptions", headers=H, files={"file": ("a.wav", buf.getvalue(), "audio/wav")})
    finally:
        builtins.__import__ = real_imp; os.environ["DEWIAR_SPEECH_FAKE"] = "1"
    h = c.get("/health").json()
    ok(r.status_code == 503 and "install-server.sh" in r.text and not h["ok"] and "onnx_asr" in h["error"],
       f"нет onnx_asr — 503 «что поставить», и в /health: {r.status_code} {h.get('error', '')[:60]}")
print("ALL OK" if not fails else f"ошибок: {len(fails)}")
sys.exit(1 if fails else 0)
