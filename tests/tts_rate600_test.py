"""№600 (07.11, Ubuntu, свой сервер распознавания и озвучки, голоса «kseniya»/«aidar»): «распознавание работает, а озвучка
делает крайне низкий голос — будто pitch передали 0,5; вручную тот же запрос звучит идеально». Сервер отдавал сырой
PCM 48 кГц, а Dewiar играл его как 24 кГц (настройка по умолчанию) — вдвое медленнее и на октаву ниже. Теперь:
— частота из заголовков ответа («audio/pcm; rate=48000», X-Sample-Rate);
— нет её — свой сервер один раз спрашиваем тот же текст в WAV и берём частоту из заголовка WAV (дальше — без вопроса);
— сервер не умеет PCM (400 «Only 'wav' and 'mp3' are supported» — было в том же журнале) или прислал mp3 — сами WAV;
— служба голосов Dewiar и частота, заданная в настройке вручную, — как раньше, без лишних запросов."""
import io, json, os, sys, threading, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tts  # noqa: E402
PCM = b"\x01\x02" * 4800
MODE, REQ = {"m": "silero", "rate": 48000}, []


def wav(rate):
    b = io.BytesIO(); w = wave.open(b, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(PCM); w.close()
    return b.getvalue()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQ.append(body)
        fmt, m = body.get("response_format"), MODE["m"]
        if m == "wavonly" and fmt == "pcm":
            msg = json.dumps({"detail": "Unsupported audio format. Only 'wav' and 'mp3' are supported."}).encode()
            self.send_response(400); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(msg)))
            self.end_headers(); self.wfile.write(msg); return
        self.send_response(200)
        if fmt == "wav":
            data = wav(MODE["rate"]); self.send_header("Content-Type", "audio/wav")
        elif m == "mp3":
            data = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" * 200; self.send_header("Content-Type", "audio/mpeg")
        elif m == "header":
            data = PCM; self.send_header("Content-Type", f"audio/pcm; rate={MODE['rate']}")
        else:
            data = PCM; self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/v1"


def say(cfg, voice="kseniya"):
    t = tts.RemoteTTS(dict({"base_url": URL, "model": "tts-1", "sample_rate": 24000, "extra": {}, "voice_f": voice}, **cfg))
    ch = list(t.synth("Привет, как дела?", {"_gender": "female"}, 1.0))
    return {r for r, _ in ch}, b"".join(c for _, c in ch)


REQ.clear(); rates, data = say({})
ok(rates == {48000} and data == PCM, f"свой сервер, сырой PCM 48 кГц без заголовков — играем 48 кГц, а не 24 (было «на октаву ниже»): {rates}")
ok([r["response_format"] for r in REQ] == ["pcm", "wav"], f"частоту узнали одним запросом WAV: {[r['response_format'] for r in REQ]}")
REQ.clear(); rates, _ = say({})
ok(rates == {48000} and len(REQ) == 1, "дальше — без лишних запросов")
MODE.update(m="header", rate=44100); REQ.clear()
rates, _ = say({}, voice="aidar")
ok(rates == {44100} and len(REQ) == 1, f"частота в заголовке ответа — берём её сразу: {rates}")
MODE.update(m="wavonly", rate=22050); REQ.clear()
rates, data = say({}, voice="baya")
ok(rates == {22050} and data == PCM, f"сервер не умеет PCM (400 «Only wav and mp3») — сами просим WAV: {rates}")
REQ.clear(); say({}, voice="baya")
ok([r["response_format"] for r in REQ] == ["wav"], "и дальше этому голосу — сразу WAV")
MODE.update(m="mp3", rate=16000); REQ.clear()
rates, data = say({}, voice="xenia")
ok(rates == {16000} and data == PCM, f"прислал mp3 вместо PCM — не играем его как шум, а просим WAV: {rates}")
MODE.update(m="silero", rate=48000); REQ.clear()
rates, _ = say({"from_account": True, "cloud": True}, voice="serena")
ok(rates == {24000} and len(REQ) == 1, "служба голосов Dewiar — как раньше, без проверки")
REQ.clear(); rates, _ = say({"sample_rate": 32000}, voice="eugene")
ok(rates == {32000} and len(REQ) == 1, "частота задана в настройке вручную — верим ей")
ok(tts._rate_from_headers({"content-type": "audio/L16; rate=16000; channels=1"}) == 16000 and
   tts._rate_from_headers({"content-type": "audio/pcm", "x-sample-rate": "48000"}) == 48000, "частота из заголовков разных серверов")
srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
