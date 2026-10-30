"""Служба голосов (server/voices/app.py, Qwen3-TTS) — без видеокарты, с поддельной моделью (TTS_FAKE=1):
— текст режется на фразы: первая короткая (раньше голос), длинное предложение — по запятой, ударения и разметка убираются;
— кто каким голосом говорит: персонаж (persona) сильнее псевдонима, псевдоним — своего голоса, OpenAI-имена и
  незнакомые — голос по умолчанию для пола, петли псевдонимов не вешают службу;
— /v1/audio/speech: pcm — поток 24 кГц, первая фраза отдельно, дальше пачкой; wav целиком — с честными длинами (телефон
  играет его MediaPlayer), wav потоком — с заголовком, sse — base64-кусками; скорость сокращает звук; манера на один ответ;
— клиент компьютера (RemoteTTS) говорит со службой напрямую и передаёт персонажа;
— свой голос по образцу: короткая запись — понятная ошибка, хорошая — голос в списке, образец слушается, персонаж говорит им;
— голос по описанию: проба с номером, большая модель сразу выгружается, проба сохраняется голосом;
— удалённый голос снимается с персонажей; ключ управления закрывает управление, но не озвучку;
— больше TTS_MAX_MODELS моделей одновременно не держится; два разговора сразу — оба договаривают."""
import http.client, io, json, os, re, shutil, sys, tempfile, threading, time, wave
from pathlib import Path
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
os.environ.update(TTS_FAKE="1", TTS_DATA=str(tmp / "data"), TTS_MAX_MODELS="2", TTS_PRELOAD="custom")
sys.path.insert(0, str(ROOT / "server/voices"))
sys.path.insert(0, str(ROOT / "core"))
import app as A  # noqa: E402

# ── фразы ──
p = A.split_text("Привет! Сегодня у тебя три дела, и первое из них — позвонить маме, потому что она ждёт с утра. Потом спорт.")
ok(len(p) >= 3 and len(p[0][0]) <= 40 and p[0][0].startswith("Привет"), f"первая фраза короткая: {p[:2]}")
p = A.split_text("Длинное предложение без точки, " * 12)
ok(all(len(x) <= 220 for x, _ in p) and len(p) >= 2, f"длинное — по запятым, не длиннее 220: {[len(x) for x, _ in p]}")
ok(A.clean("**Дэвиа\u0301р** — `код`") == "Дэвиа\u0301р — код" and A.plain("Дэвиа\u0301р, прив+ет, 2+2") == "Дэвиар, привет, 2+2"
   and A.stress_marks("Дэвиа\u0301р") == "Дэви+ар", "разметка убрана; ударения: ESpeech — «+» перед гласной, Qwen — без них (2+2 не трогаем)")
ok(A.lang_of("Привет") == "Russian" and A.lang_of("Hello") == "Auto" and A.lang_of("x", "en") == "English", "язык по тексту")
ok(A.lang_of("14:10") == "Russian" and A.lang_of("2026.") == "Russian" and A.lang_of("iPhone 15") == "Auto",
   "одни цифры («14:10») — по-русски (отзыв 16.10: время прозвучало «ствисе»)")
import numpy as _np  # noqa: E402
_sr = A.OUT_SR
_loud = 0.5 * _np.sin(_np.arange(int(_sr * 0.6)) / _sr * 2 * _np.pi * 220)
_quiet = 0.006 * _np.sin(_np.arange(int(_sr * 0.25)) / _sr * 2 * _np.pi * 220)       # тихое последнее слово
_w = _np.concatenate([_np.zeros(_sr // 5), _loud, _quiet, _np.zeros(_sr // 2)]).astype(_np.float32)
_t = A.trim(_w)
ok(_t.size >= _loud.size + _quiet.size and _t.size < _w.size - _sr // 5,
   f"обрезка тишины не срезает тихое последнее слово («…равно два», отзыв 16.10): {_t.size / _sr:.2f} с из {_w.size / _sr:.2f}")

_w2 = _np.concatenate([_np.zeros(_sr // 5), _quiet, _loud, _np.zeros(_sr // 5)]).astype(_np.float32)
_t2 = A.trim(_w2)
ok(_t2.size >= _loud.size + _quiet.size and _t2.size < _w2.size - _sr // 10,
   f"и тихое первое слово не срезается («Что у нас с Ивановым», отзыв 29.10): {_t2.size / _sr:.2f} с из {_w2.size / _sr:.2f}")

# ── кто каким голосом ──
A.cfg_save({"voices": {"anna": {"kind": "clone", "audio": "anna.wav", "text": "т", "gender": "female"}},
            "personas": {"lira": "anna"}, "aliases": {"serena": "vivian", "loop1": "loop2", "loop2": "loop1"},
            "default": {"female": "serena", "male": "ryan"}})
ok(A.resolve("serena", "lira")["id"] == "anna", "персонаж сильнее псевдонима: Лира говорит своим голосом")
ok(A.resolve("serena", "eva")["id"] == "vivian", "псевдоним: serena → vivian для остальных")
ok(A.resolve("aiden")["id"] == "aiden" and A.resolve("aiden")["kind"] == "speaker", "встроенный диктор")
ok(A.resolve("onyx")["id"] == "ryan" and A.resolve("nova")["id"] == "serena", "имена OpenAI — голос по умолчанию для пола")
ok(A.resolve("kto-to", gender="male")["id"] == "ryan", "незнакомый — по полу")
ok(A.resolve("loop1")["kind"] == "speaker", f"петля псевдонимов не вешает: {A.resolve('loop1')}")
# встроенные Qwen выключены — их имена ведут к своим голосам того же пола
A.cfg_save({"voices": {"anna": {"kind": "clone", "audio": "a.wav", "text": "т", "gender": "female"},
                       "oleg": {"kind": "clone", "audio": "o.wav", "text": "т", "gender": "male"}},
            "personas": {"eva": "vivian"}, "default": {"female": "serena", "male": "aiden"}})
A.BUILTIN_ON = False
ok(A.resolve("serena")["id"] == "anna" and A.resolve("aiden")["id"] == "oleg" and A.resolve("x", "eva")["id"] == "anna"
   and A.resolve("onyx")["id"] == "oleg" and A.resolve("")["id"] == "anna",
   f"встроенные выключены — свои голоса по полу: {[A.resolve(v)['id'] for v in ('serena', 'aiden', 'onyx', '')]}")
A.BUILTIN_ON = True
ok(A.resolve("serena")["id"] == "serena", "встроенные включены — как раньше")
# ESpeech: первая фраза одна, дальше куски до ~180 знаков (образец проходится раз на кусок, а не на каждую фразу)
A.ENGINE.calls.clear()
long_text = "Привет! " + " ".join(f"Это предложение номер {i}, в нём есть немного слов." for i in range(1, 9))
list(A.synth_iter(long_text, {"id": "anna", "kind": "clone", "audio": "a.wav", "text": "т"}))
lens = [len(c["texts"][0]) for c in A.ENGINE.calls]
ok(A.ENGINE.calls[0]["role"] == "espeech" and A.ENGINE.calls[0]["texts"] == ["Привет!"] and all(len(c["texts"]) == 1 for c in A.ENGINE.calls)
   and all(n <= 200 for n in lens) and len(A.ENGINE.calls) <= 4, f"ESpeech: «Привет!» отдельно, дальше куски: {lens}")
A.cfg_save({})

# видеокарта общая с vLLM: вторая модель не влезла — служба выгружает первую и продолжает, а не падает
import types  # noqa: E402
_tries = []


class _Q:
    @staticmethod
    def from_pretrained(name, **kw):
        _tries.append(name)
        if "Base" in name and _tries.count(name) == 1:
            raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
        if "VoiceDesign" in name:
            raise RuntimeError("401 Unauthorized")
        return "model:" + name


_stub_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False, empty_cache=lambda: None), float32="f32", bfloat16="bf16")
sys.modules["torch"], sys.modules["qwen_tts"] = _stub_torch, types.SimpleNamespace(Qwen3TTSModel=_Q)
QE = A.QwenEngine()
QE.get("custom")
m = QE.get("base")
ok(m.endswith("0.6B-Base") and sorted(QE.models) == ["base"] and A.STATE["loaded"] == ["base"], f"не хватило видеопамяти на вторую модель — первая выгружена, вторая загружена: {sorted(QE.models)}")
try:
    QE.get("design"); ok(False, "другая ошибка загрузки — не прячется")
except RuntimeError as e:
    ok("401" in str(e), "другая ошибка загрузки — не прячется")

# ESpeech (русский движок своих голосов): ударения RUAccent, свои «+» и а́ не трогаются, образец — не длиннее 12 с
_f5 = {"calls": []}


class _Acc:
    def load(self, **kw):
        _f5["acc_load"] = kw

    def process_all(self, text, skip_regex=None):
        _f5.setdefault("acc", []).append((text, skip_regex))
        return text.replace("голос", "г+олос")


def _ibp(ref, ref_text, gens, model, voc, nfe_step=32, speed=1.0, device=None):
    _f5["calls"].append({"ref_len": ref[0].shape[-1], "ref_text": ref_text, "gen": gens, "nfe": nfe_step, "dev": device})
    yield np.ones(2400, np.float32) * 0.1, 24000, None


class _T:                                                 # torch.from_numpy(...).unsqueeze(0)
    def __init__(self, a):
        self.a = a
        self.shape = (1, len(a))

    def unsqueeze(self, i):
        return self


sys.modules["torch"].from_numpy = _T
sys.modules["huggingface_hub"] = types.SimpleNamespace(hf_hub_download=lambda repo_id, filename: f"/m/{repo_id}/{filename}")
sys.modules["f5_tts"] = types.SimpleNamespace()
sys.modules["f5_tts.infer"] = types.SimpleNamespace()
sys.modules["f5_tts.infer.utils_infer"] = types.SimpleNamespace(load_model=lambda *a, **k: ("model", a[2], k["vocab_file"]),
                                                               load_vocoder=lambda **k: "vocos", infer_batch_process=_ibp)
sys.modules["f5_tts.model"] = types.SimpleNamespace(DiT="DiT")
sys.modules["ruaccent"] = types.SimpleNamespace(RUAccent=_Acc)
os.makedirs(A.vdir(), exist_ok=True)
long_wav = A.vdir("long.wav")
open(long_wav, "wb").write(A.wav_bytes(np.full(24000 * 15, 0.2, np.float32)))
E2 = A.Engine()
outs, sr = E2.generate({"id": "anna", "kind": "clone", "audio": "long.wav", "text": "Это мой голос."}, ["Привет, я голос Дэвиа\u0301ра.", "Скажи «прив+ет»."], "Russian")
c0 = _f5["calls"]
ok(len(c0) == 2 and sr == 24000 and c0[0]["ref_len"] <= 24000 * 12 and c0[0]["ref_text"] == "Это мой г+олос." and c0[0]["nfe"] == A.ESPEECH_NFE,
   f"ESpeech: образец обрезан до 12 с, текст образца — с ударениями, шагов {A.ESPEECH_NFE}: {[(c['ref_len'], c['ref_text']) for c in c0]}")
ok(c0[0]["gen"] == ["Привет, я г+олос Дэви+ара."] and _f5["acc"][1][1] == r"\S*\+\S*", f"ударения: своё (а́ → +) сохранено, остальное — RUAccent: {c0[0]['gen']}")
ok(c0[1]["gen"] == ["Скажи «прив+ет»."], f"«+» пользователя не перебивается: {c0[1]['gen']}")
ok(sorted(E2.models) == ["espeech"] and _f5["acc_load"]["omograph_model_size"] == "turbo3.1", "загружен ESpeech с RUAccent turbo3.1")
# прогрев при запуске: ESpeech загружен, образцы своих голосов подготовлены, одна фраза уже прогнана
_save_cfg, _save_eng, _save_pre = A.cfg_load(), A.ENGINE, A.PRELOAD
c = A.cfg_load(); c["voices"]["anna"] = {"kind": "clone", "audio": "long.wav", "text": "Это мой голос.", "gender": "female"}; A.cfg_save(c)
A.ENGINE, A.PRELOAD, _f5["calls"] = A.Engine(), ["auto"], []
A.ENGINE.device = lambda: "cpu"
A.preload()
ok("espeech" in A.ENGINE.models and len(A.ENGINE.refs) == 1 and any("Проверка голоса" in x["gen"][0].replace("+", "") for x in _f5["calls"]),
   f"прогрев: ESpeech загружен, образец своего голоса готов, одна фраза прогнана: {sorted(A.ENGINE.models)} refs={len(A.ENGINE.refs)} {[x['gen'] for x in _f5['calls']]}")
A.cfg_save(_save_cfg); A.ENGINE, A.PRELOAD = _save_eng, _save_pre
ok(A.role_for({"kind": "clone"}) == "espeech" and A.role_for({"kind": "clone", "engine": "qwen"}) == "base"
   and A.role_for({"kind": "speaker"}) == "custom" and A.role_for({"kind": "design"}) == "design", "кто что озвучивает: свои — ESpeech, встроенные — Qwen")

# быстрый Qwen (faster-qwen3-tts) — по одной фразе, без знаков ударения
_fq = []


class _FQ:
    @staticmethod
    def from_pretrained(name, **kw):
        _fq.append(("load", name, kw.get("device")))
        return _FQ()

    def generate_custom_voice(self, text, speaker, language, instruct=None):
        _fq.append(("custom", text, speaker, language, instruct))
        return [np.ones(2400, np.float32)], 24000


sys.modules["faster_qwen3_tts"] = types.SimpleNamespace(FasterQwen3TTS=_FQ)
E3 = A.Engine()
E3.device = lambda: "cuda:0"
outs, sr = E3.generate({"id": "serena", "kind": "speaker", "speaker": "serena"}, ["Я Дэвиа\u0301р.", "Прив+ет."], "Russian")
ok(_fq[0][0] == "load" and _fq[0][2] == "cuda:0" and [x[1] for x in _fq[1:]] == ["Я Дэвиар.", "Привет."] and "custom" in E3.fast and len(outs) == 2,
   f"быстрый Qwen: по фразе, без знаков ударения: {_fq}")
for k in ("faster_qwen3_tts", "huggingface_hub", "f5_tts", "f5_tts.infer", "f5_tts.infer.utils_infer", "f5_tts.model", "ruaccent"):
    del sys.modules[k]
del sys.modules["torch"], sys.modules["qwen_tts"]
A.STATE["loaded"] = []

srv = A.serve(0)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def req(method, path, body=None, headers=None, raw=False):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=30)
    h = dict(headers or {})
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode()
        h.setdefault("Content-Type", "application/json")
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, dict((k.lower(), v) for k, v in r.getheaders()), data if raw else (json.loads(data or b"{}") if data[:1] in (b"{", b"[") else data)


def wav_of(sec, sr=16000):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        x = np.arange(int(sec * sr)) / sr
        w.writeframes((0.3 * np.sin(2 * np.pi * 180 * x) * 32767).astype("<i2").tobytes())
    return b.getvalue()


def multipart(fields, file):
    bnd = "----dw" + str(time.time_ns())
    out = b""
    for k, v in fields.items():
        out += f'--{bnd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    out += f'--{bnd}\r\nContent-Disposition: form-data; name="file"; filename="v.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode() + file + b"\r\n"
    out += f"--{bnd}--\r\n".encode()
    return out, {"Content-Type": "multipart/form-data; boundary=" + bnd}


try:
    st, _, h = req("GET", "/health")
    ok(st == 200 and h.get("ok") and h.get("fake"), f"/health: {st} {h.get('fake')}")

    TEXT = "Привет! Это проверка голоса. Вторая фраза. Третья фраза. Четвёртая фраза."
    A.ENGINE.calls.clear()
    st, hd, pcm = req("POST", "/v1/audio/speech", {"input": TEXT, "voice": "serena", "response_format": "pcm", "stream": True}, raw=True)
    ok(st == 200 and hd.get("content-type") == "audio/pcm" and hd.get("transfer-encoding") == "chunked" and hd.get("x-sample-rate") == "24000",
       f"pcm — поток 24 кГц: {st} {hd.get('content-type')} {hd.get('transfer-encoding')}")
    ok(len(pcm) % 2 == 0 and len(pcm) / 2 / 24000 > 2, f"звук пришёл целиком: {len(pcm) / 48000:.2f} с")
    ok([len(c["texts"]) for c in A.ENGINE.calls] == [1, 4] and A.ENGINE.calls[0]["voice"] == "serena" and A.ENGINE.calls[0]["lang"] == "Russian",
       f"первая фраза отдельно, остальные пачкой: {[c['texts'] for c in A.ENGINE.calls]}")

    st, hd, w = req("POST", "/v1/audio/speech", {"input": "Привет, я Лира.", "voice": "serena", "response_format": "wav", "speed": 1}, raw=True)
    with wave.open(io.BytesIO(w)) as wf:
        ok(st == 200 and wf.getframerate() == 24000 and wf.getnframes() * 2 + 44 == len(w), f"wav целиком — честные длины для телефона: {wf.getnframes()} кадров, {len(w)} байт")
        dur1 = wf.getnframes() / 24000
    ok(float(hd.get("x-audio-duration", 0)) > 0.5 and hd.get("x-voice") == "serena", f"длительность и голос в заголовках: {hd.get('x-audio-duration')} {hd.get('x-voice')}")
    st, hd, w2 = req("POST", "/v1/audio/speech", {"input": "Привет, я Лира.", "voice": "serena", "response_format": "wav", "speed": 1.5}, raw=True)
    with wave.open(io.BytesIO(w2)) as wf:
        dur2 = wf.getnframes() / 24000
    # темп меняет ffmpeg (atempo); без него (машина проверок GitHub) служба ускоряет только паузы — фраза короче, но чуть
    # (23.10, «Проверки» #132: 1.19 → 1.11 с — письма «workflow run failed» владельцу)
    import shutil as _sh
    ok(dur2 < dur1 * (0.8 if _sh.which("ffmpeg") else 0.98), f"скорость 1.5 — короче: {dur1:.2f} → {dur2:.2f} с"
       + ("" if _sh.which("ffmpeg") else " (нет ffmpeg — только паузы)"))
    st, hd, ws = req("POST", "/v1/audio/speech", {"input": "Раз. Два.", "voice": "aiden", "response_format": "wav", "stream": True}, raw=True)
    ok(st == 200 and ws[:4] == b"RIFF" and ws[36:40] == b"data" and len(ws) > 44, "wav потоком — с заголовком")
    st, hd, ev = req("POST", "/v1/audio/speech", {"input": "Раз. Два.", "voice": "aiden", "response_format": "pcm", "stream_format": "sse"}, raw=True)
    lines = [json.loads(x[5:]) for x in ev.decode().split("\n") if x.startswith("data:")]
    ok(hd.get("content-type") == "text/event-stream" and lines[-1]["type"] == "speech.audio.done" and lines[0].get("audio"), f"sse: {len(lines)} событий")
    A.ENGINE.calls.clear()
    req("POST", "/v1/audio/speech", {"input": "Ура!", "voice": "serena", "instruct": "радостно", "response_format": "wav"}, raw=True)
    ok(A.ENGINE.calls and A.ENGINE.calls[-1]["instruct"] == "радостно", f"манера на один ответ: {A.ENGINE.calls[-1:]}")
    st, _, e = req("POST", "/v1/audio/speech", {"input": "", "voice": "serena"})
    ok(st == 400 and "input" in e["error"]["message"], "пустой текст — 400 с объяснением")
    st, _, e = req("POST", "/v1/audio/speech", {"input": "а" * (A.MAX_CHARS + 1)})
    ok(st == 413, "слишком длинный — 413")

    # клиент компьютера — напрямую в службу
    from tts import RemoteTTS
    A.ENGINE.calls.clear()
    out = list(RemoteTTS({"base_url": f"http://127.0.0.1:{PORT}/v1"}).synth("Привет. Я Лира.", {"remote": "serena", "_gender": "female", "_pid": "lira"}, 1.0))
    ok(out and out[0][0] == 24000 and sum(len(b) for _, b in out) > 24000, f"RemoteTTS играет поток службы: {len(out)} кусков")

    # свой голос по образцу
    body, hh = multipart({"title": "Короткий", "text": "раз"}, wav_of(1.5))
    st, _, e = req("POST", "/v1/voices", body, hh)
    ok(st == 400 and "3 секунд" in e["error"]["message"], f"короткий образец — понятная ошибка: {e}")
    body, hh = multipart({"title": "Анна тёплая", "gender": "female", "text": "Привет, это мой голос для проверки."}, wav_of(6))
    st, _, e = req("POST", "/v1/voices", body, hh)
    ok(st == 200 and e["voice"]["id"] == "anna_teplaya" and e["voice"]["kind"] == "clone", f"образец принят, имя из названия: {e}")
    st, _, lst = req("GET", "/v1/audio/voices")
    ids = [v["id"] for v in lst["voices"]]
    ok("anna_teplaya" in ids and "serena" in ids and len([v for v in lst["voices"] if v["builtin"]]) == 9, f"в списке свой и 9 встроенных: {ids}")
    st, hd, smp = req("GET", "/v1/voices/anna_teplaya/sample", raw=True)
    ok(st == 200 and smp[:4] == b"RIFF", "образец слушается")
    st, _, e = req("POST", "/v1/voices/config", {"personas": {"Lira": "anna_teplaya"}})
    ok(st == 200 and e["personas"] == {"lira": "anna_teplaya"}, f"Лире — этот голос: {e.get('personas')}")
    st, _, e = req("POST", "/v1/voices/config", {"personas": {"lira": "net_takogo"}})
    ok(st == 400 and "net_takogo" in e["error"]["message"], "несуществующий голос персонажу не назначить")
    A.ENGINE.calls.clear()
    list(RemoteTTS({"base_url": f"http://127.0.0.1:{PORT}/v1"}).synth("Привет.", {"remote": "serena", "_gender": "female", "_pid": "lira"}, 1.0))
    ok(A.ENGINE.calls and A.ENGINE.calls[-1]["voice"] == "anna_teplaya" and A.ENGINE.calls[-1]["kind"] == "clone",
       f"компьютер передаёт персонажа — Лира говорит своим голосом: {A.ENGINE.calls[-1:]}")
    st, _, e = req("POST", "/v1/voices/update", {"id": "serena", "instruct": "мягко и тепло"})
    ok(st == 200 and A.resolve("serena")["instruct"] == "мягко и тепло", "встроенному можно задать манеру")

    # голос по описанию
    st, _, e = req("POST", "/v1/voices/design", {"instruct": "тихо"})
    ok(st == 400 and "подробнее" in e["error"]["message"], "слишком короткое описание — подсказка")
    A.ENGINE.calls.clear()
    st, hd, dw = req("POST", "/v1/voices/design", {"instruct": "Низкий мужской голос, лет сорок, спокойный, бархатный"}, raw=True)
    did = hd.get("x-draft-id", "")
    ok(st == 200 and dw[:4] == b"RIFF" and len(did) == 12 and A.ENGINE.calls[-1]["kind"] == "design" and len(A.ENGINE.calls[-1]["texts"]) == 1 and "рад " in A.ENGINE.calls[-1]["texts"][0],
       f"проба по описанию — одним проходом, мужская фраза: {st} {did} {A.ENGINE.calls[-1:]}")
    ok("design" not in A.STATE["loaded"], f"большая модель сразу выгружена: {A.STATE['loaded']}")
    st, hd, dd = req("GET", f"/v1/voices/drafts/{did}", raw=True)
    ok(st == 200 and dd == dw, "пробу можно переслушать")
    st, _, e = req("POST", "/v1/voices", {"draft": did, "title": "Бархат"})
    ok(st == 200 and e["voice"]["id"] == "barhat" and e["voice"]["designed"].startswith("Низкий") and e["voice"]["gender"] == "male",
       f"проба сохранена голосом: {e}")
    st, _, e = req("POST", "/v1/voices", {"draft": "0" * 12, "title": "x"})
    ok(st == 400 and "устарела" in e["error"]["message"], "чужая или старая проба — понятная ошибка")

    # удаление
    st, _, e = req("POST", "/v1/voices/delete", {"id": "anna_teplaya"})
    ok(st == 200 and A.cfg_load()["personas"] == {} and not (tmp / "data/voices/anna_teplaya.wav").exists(), "удалённый голос снят с Лиры, файл убран")
    st, _, e = req("POST", "/v1/voices/delete", {"id": "net"})
    ok(st == 404, "удалить несуществующий — 404")

    # ключ управления
    A.ADMIN_KEY = "adm"
    st, _, _ = req("POST", "/v1/voices/config", {"personas": {}})
    st2, _, _ = req("POST", "/v1/voices/config", {"personas": {}}, {"Authorization": "Bearer adm"})
    st3, _, _ = req("POST", "/v1/audio/speech", {"input": "Да.", "response_format": "wav"}, raw=True)
    ok(st == 401 and st2 == 200 and st3 == 200, f"ключ управления: без него {st}, с ним {st2}, озвучка {st3}")
    A.ADMIN_KEY = ""

    # модели в памяти и два разговора сразу
    ok(len(A.STATE["loaded"]) <= 2, f"не больше двух моделей: {A.STATE['loaded']}")
    A.ENGINE.delay = 0.05
    res = []

    def talk(v):
        res.append(req("POST", "/v1/audio/speech", {"input": "Раз. Два. Три. Четыре. Пять.", "voice": v, "response_format": "pcm"}, raw=True)[0])
    th = [threading.Thread(target=talk, args=(v,)) for v in ("serena", "barhat")]
    [t.start() for t in th]; [t.join(20) for t in th]
    ok(res == [200, 200], f"два разговора сразу — оба договорили: {res}")
    st, _, h = req("GET", "/health")
    ok(h["requests"] >= 8 and h["chars"] > 50 and h["audio_sec"] > 1 and h["ttfa_ms_avg"] >= 0 and h["waiting"] == 0, f"счётчики: {h['requests']} {h['chars']} {h['audio_sec']:.1f}")

    # цифры — словами (отзыв 15.10: «вместо цифр — очень странные звуки»), в роде следующего слова и с датами
    A.ENGINE.calls.clear()
    st, _, _ = req("POST", "/v1/audio/speech", {"input": "Через 1 минуту, 15 октября в 10:30, 54 рубля и +12°.", "voice": "serena", "response_format": "wav"})
    said = " ".join(t for c in A.ENGINE.calls for t in c["texts"])
    ok(st == 200 and "одну минуту" in said and "пятнадцатое октября" in said and "десять тридцать" in said and "пятьдесят четыре рубля" in said
       and "плюс двенадцать градусов" in said and not re.search(r"\d", said), f"цифры — словами: {said}")
    A.ENGINE.calls.clear()
    req("POST", "/v1/audio/speech", {"input": "Call me at 5 pm", "voice": "serena", "response_format": "wav"})
    ok(any("5" in t for c in A.ENGINE.calls for t in c["texts"]), "английский текст не трогаем — модель читает его сама")
    V0 = ROOT / "server/voices"
    vb = ROOT / "tools/voices_bundle.py"                  # сборщик пакета «Голоса» — только в закрытом репозитории
    ok("COPY *.py" in (V0 / "Dockerfile").read_text(encoding="utf-8")
       and (not vb.exists() or '"src/vllm/tts/speechnorm.py"' in vb.read_text(encoding="utf-8")), "пакет «Голоса» везёт speechnorm.py, образ его копирует")
    st, _, h = req("GET", "/health")
    ok(h.get("numbers") is True, "/health: цифры словами — включены (панель покажет, если служба собрана без них)")
    # «Обновить службу» собирает образ из tar, который делает панель: раньше там были только Dockerfile и app.py — образ
    # с новым модулем не собирался, и цифры оставались (отзыв 15.10 после 0.38.52)
    import subprocess as _sp
    if shutil.which("php") and (V0 / "vllm/lib/ttsctl.php").exists():     # панели сервера в открытой копии нет
        tc = tmp / "tc"; (tc / "lib").mkdir(parents=True); (tc / "tts").mkdir()
        shutil.copy(V0 / "vllm/lib/ttsctl.php", tc / "lib/ttsctl.php")
        for f in ("Dockerfile", "app.py"):
            shutil.copy(V0 / f, tc / "tts" / f)
        shutil.copy(ROOT / "core/speechnorm.py", tc / "tts/speechnorm.py")
        out = _sp.run(["php", "-r", f'require "{tc}/lib/ttsctl.php"; $t = TtsCtl::tarContext(); preg_match_all("/(Dockerfile|[a-z_]+\\.py)\\x00/", $t, $m); echo implode(",", array_unique($m[1]));'],
                      capture_output=True, text=True).stdout
        ok(set(out.split(",")) == {"Dockerfile", "app.py", "speechnorm.py"}, f"сборка образа берёт и speechnorm.py: {out}")
    # наплыв людей: очередь к видеокарте длинная — сразу «занято» (503), приложение скажет своим голосом, а не ждёт минуту
    A.STATE["waiting"] = A.MAX_WAITING
    st, _, e = req("POST", "/v1/audio/speech", {"input": "Привет", "voice": "serena"})
    A.STATE["waiting"] = 0
    st2, _, _ = req("GET", "/health")
    ok(st == 503 and "заняты" in json.dumps(e, ensure_ascii=False) and A.STATE["busy_rejects"] >= 1, f"очередь длинная — 503 «голоса заняты»: {st} {e}")
    st, _, _ = req("POST", "/v1/audio/speech", {"input": "Привет", "voice": "serena", "response_format": "wav"})
    ok(st == 200, "очередь разошлась — снова говорит")
    js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
    ok('persona: persona().id || ""' in js, "телефон тоже передаёт персонажа в «Голос Dewiar»")
    # файлы для сервера на месте
    V = ROOT / "server/voices"
    ok((V / "Dockerfile").is_file() and "qwen-tts" in (V / "Dockerfile").read_text(encoding="utf-8"), "Dockerfile ставит qwen-tts")
    ok("HF_HUB_CACHE=/models" in (V / "Dockerfile").read_text(encoding="utf-8"), "веса — прямо в папке моделей (как у vLLM)")
finally:
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
