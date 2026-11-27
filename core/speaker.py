"""Кто говорит: голос владельца против остальных (суфлёр на очной встрече — один микрофон слышит обоих).

Модель — CAM++ (3D-Speaker, Alibaba, Apache 2.0; обучена на 200 тыс. голосов, китайский и английский — на русском
различает так же: смотрит на тембр, а не на слова). Файл ~28 МБ скачивается при первом «Запомнить мой голос»
в MODELS_DIR/speaker/ — со своего сайта (зеркало «speaker»), иначе с GitHub sherpa-onnx.
Признаки — 80 полос kaldi fbank (окно 25 мс, шаг 10 мс, окно Пови, предыскажение 0,97), минус среднее по фразе;
на выходе — вектор голоса (192 числа). Похожесть — косинус: свой голос обычно 0,6–0,9, чужой — до 0,5 у похожих голосов, поэтому
на встрече запоминаем и голоса собеседников (Diarizer) и сравниваем: к кому фраза ближе.
Отпечаток владельца — среднее нескольких фраз: STATE_DIR/voiceprints/_owner.json (папка уже в резервной копии).
Звук не хранится — только вектор."""
import json
import logging
import threading
import time

import numpy as np

from settings import MODELS_DIR, STATE_DIR

log = logging.getLogger("dewiar.speaker")
MODEL_NAME = "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx"
MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/" + MODEL_NAME
MODEL_SHA256 = "53cab20ba8f2eb2f6e2d89ecc18e88ef3222169b61b4419cbc13666744a4574b"   # №914/916 (20.11): прежняя сумма не от этого файла — «контрольная сумма не совпала», голос в «Суфлёре» не запоминался
OWNER_FILE = STATE_DIR / "voiceprints" / "_owner.json"
SAME, OTHER = 0.55, 0.40        # косинус: выше SAME — вы, ниже OTHER — точно не вы; между — кто ближе (Diarizer)
RATE = 16000


def _mel_banks(nbins=80, nfft=512, low=20.0, high=RATE / 2):
    """Треугольные фильтры kaldi (по шкале мел 1127·ln(1+f/700)), [nbins × nfft/2+1]; последняя (найквист) — 0."""
    def mel(f):
        return 1127.0 * np.log(1.0 + f / 700.0)
    half = nfft // 2
    fbin = RATE / nfft
    mlo, mhi = mel(low), mel(high)
    delta = (mhi - mlo) / (nbins + 1)
    m = mel(np.arange(half) * fbin)
    out = np.zeros((nbins, half + 1), np.float32)
    for b in range(nbins):
        left, center, right = mlo + b * delta, mlo + (b + 1) * delta, mlo + (b + 2) * delta
        up = (m - left) / (center - left)
        down = (right - m) / (right - center)
        out[b, :half] = np.maximum(0.0, np.minimum(up, down))
    return out


_BANKS = _mel_banks()
_POVEY = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(400) / 399)) ** 0.85


def fbank(pcm: bytes):
    """16 кГц int16 -> [кадры × 80] log-mel, как torchaudio.compliance.kaldi.fbank (dither 0), минус среднее."""
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < 400:
        return np.zeros((0, 80), np.float32)
    n = 1 + (len(x) - 400) // 160
    idx = np.arange(400)[None, :] + 160 * np.arange(n)[:, None]
    fr = x[idx].astype(np.float64)
    fr -= fr.mean(1, keepdims=True)
    fr = np.concatenate([fr[:, :1] * (1 - 0.97), fr[:, 1:] - 0.97 * fr[:, :-1]], axis=1)
    fr *= _POVEY
    pw = np.abs(np.fft.rfft(fr, 512)) ** 2
    f = np.log(np.maximum(pw @ _BANKS.T, np.finfo(np.float32).eps)).astype(np.float32)
    return f - f.mean(0, keepdims=True)


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


class Speaker:
    """Вектор голоса фразы и сравнение с владельцем. Модель грузится лениво, в одном экземпляре."""

    def __init__(self, mirror=None):
        self.mirror = mirror            # {"url", "sha256"} — со своего сайта
        self._sess = None
        self._lock = threading.Lock()
        self.owner = None               # np.ndarray или None
        self.owner_n = 0
        self.loading = False
        self._load_owner()

    @property
    def path(self):
        return MODELS_DIR / "speaker" / MODEL_NAME

    def ready(self):
        return self.path.is_file()

    def ensure(self, on_progress=None):
        """Скачать модель, если её нет (со своего сайта, иначе с GitHub; с проверкой sha256). -> путь.
        on_progress(доля 0..1). Не скачалась — RuntimeError с понятным текстом."""
        p = self.path
        if p.is_file():
            return p
        from updater import download
        p.parent.mkdir(parents=True, exist_ok=True)
        self.loading = True
        try:
            m = self.mirror or {}
            srcs = ([(m["url"], m.get("sha256") or MODEL_SHA256)] if m.get("url") else []) + [(MODEL_URL, MODEL_SHA256)]
            err = None
            for url, sha in srcs:
                try:
                    download(url, p, sha, on_progress)
                    log.info("Модель голоса скачана: %s", url)
                    return p
                except Exception as e:  # noqa: BLE001
                    err = e
                    p.unlink(missing_ok=True)
            raise RuntimeError(f"модель голоса не скачалась: {err}")
        finally:
            self.loading = False

    def _session(self):
        with self._lock:
            if self._sess is None:
                import onnxruntime as ort
                self.ensure()
                so = ort.SessionOptions()
                so.intra_op_num_threads = 1
                so.inter_op_num_threads = 1
                self._sess = ort.InferenceSession(str(self.path), so, providers=["CPUExecutionProvider"])
            return self._sess

    def embed(self, pcm: bytes):
        """Вектор голоса фразы (нужно ≥ 0,8 с речи) или None."""
        f = fbank(pcm)
        if len(f) < 80:
            return None
        s = self._session()
        e = s.run(None, {s.get_inputs()[0].name: f[None]})[0][0]
        return e / (np.linalg.norm(e) + 1e-9)

    # ---------- владелец ----------

    def _load_owner(self):
        try:
            d = json.loads(OWNER_FILE.read_text(encoding="utf-8"))
            if d.get("model") == MODEL_NAME:
                self.owner, self.owner_n = np.array(d["vec"], np.float32), int(d.get("n", 1))
        except (OSError, ValueError, KeyError):
            self.owner = None

    def enroll(self, pcms):
        """Запомнить голос владельца по нескольким фразам. -> {n, consistency}; мало речи — ValueError."""
        vecs = [v for v in (self.embed(p) for p in pcms) if v is not None]
        if len(vecs) < 2:
            raise ValueError("мало речи — скажите ещё пару фраз")
        c = np.mean(vecs, 0)
        c /= np.linalg.norm(c) + 1e-9
        cons = min(cos(v, c) for v in vecs)
        OWNER_FILE.parent.mkdir(parents=True, exist_ok=True)
        OWNER_FILE.write_text(json.dumps({"model": MODEL_NAME, "vec": [round(float(x), 6) for x in c], "n": len(vecs),
                                          "ts": int(time.time())}), encoding="utf-8")
        self.owner, self.owner_n = c.astype(np.float32), len(vecs)
        log.info("Голос владельца запомнен: %d фраз, согласованность %.2f", len(vecs), cons)
        return {"n": len(vecs), "consistency": round(cons, 2)}

    def forget(self):
        OWNER_FILE.unlink(missing_ok=True)
        self.owner, self.owner_n = None, 0

    def diarizer(self):
        return Diarizer(self)


class Diarizer:
    """На одну встречу: «вы» или «собеседник» для каждой фразы. Голоса собеседников копятся по ходу (до 4 человек):
    фраза в серой зоне относится к тому, на кого похожа больше; совсем короткая — к тому, кто говорил только что."""

    def __init__(self, sp):
        self.sp = sp
        self.others = []                # векторы голосов собеседников
        self.prev = None

    def who(self, pcm):
        """-> ("me" | "them", похожесть на владельца)."""
        v = self.sp.embed(pcm)
        if v is None:
            return self.prev or "them", 0.0
        so = cos(v, self.sp.owner)
        st = max((cos(v, c) for c in self.others), default=0.0)
        if so >= SAME and so > st:
            w = "me"
        elif so < OTHER:
            w = "them"
        elif abs(so - st) > 0.05 and self.others:
            w = "me" if so > st else "them"
        else:
            w = self.prev or ("me" if so >= (SAME + OTHER) / 2 else "them")
        if w == "them":
            self._learn(v)
        self.prev = w
        return w, round(so, 2)

    def _learn(self, v):
        best = max(range(len(self.others)), key=lambda i: cos(v, self.others[i]), default=None)
        if best is not None and cos(v, self.others[best]) > 0.55:
            c = self.others[best] * 0.8 + v * 0.2
            self.others[best] = c / (np.linalg.norm(c) + 1e-9)
        elif len(self.others) < 4:
            self.others.append(v)
