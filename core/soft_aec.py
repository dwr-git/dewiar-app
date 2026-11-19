"""Своё эхоподавление (19.11, владелец: «нельзя перебивать Лиру — разговор идёт по очереди»; «готов протестировать, пока
под флагом»). В Windows и на Mac у программ нет системного эхоподавления: пока ассистент говорит, микрофон слышит его
голос из колонок — поэтому без наушников слушаем только «стоп». Но мы сами знаем, что играем: голос, который пишет
Player, — это «дальний» сигнал для эхоподавления WebRTC (то же, что в Chrome и Zoom; aec-audio-processing, BSD-3).
Вычитаем его из микрофона — и перебить можно просто речью, как в наушниках.

Без риска для слуха: пока ассистент молчит (и ещё секунду после), в слух идёт микрофон как есть, а эхоподавление только
учится; очищенный звук — лишь во время своего голоса. Нет библиотеки — ok() == False, всё как раньше.

Поток: Player.write → far(pcm, rate, ch, play_at) — куски голоса с моментом, когда они зазвучат; слух на каждый кадр
микрофона → near(frame) — тот же кадр (int16, 16 кГц, FRAME отсчётов), очищенный, если сейчас звучит голос."""
import collections
import threading
import time

import numpy as np

RATE = 16000
CHUNK = 160                       # 10 мс — размер кадра APM
TAIL_S = 1.0                      # после конца голоса ещё секунду отдаём очищенное (хвост эха в комнате)


def available():
    try:
        import aec_audio_processing  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — нет колеса для этой системы (Mac) или не установилось
        return False


def _to16k(pcm: bytes, rate: int, ch: int) -> np.ndarray:
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if ch > 1:
        a = a[: len(a) // ch * ch].reshape(-1, ch).mean(axis=1)
    if rate != RATE and len(a):
        n = max(1, int(round(len(a) * RATE / rate)))
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)
    return a


class SoftAEC:
    def __init__(self, delay_ms=60, factory=None):
        if factory is None:
            from aec_audio_processing import AudioProcessor
            factory = lambda: AudioProcessor(enable_aec=True, enable_ns=False, enable_agc=False)   # noqa: E731
        self.ap = factory()
        self.ap.set_stream_format(RATE, 1)
        self.ap.set_reverse_stream_format(RATE, 1)
        self.ap.set_stream_delay(int(delay_ms))
        self._lock = threading.Lock()
        self._far = collections.deque()              # (момент звучания, кусок 10 мс float32)
        self._far_rest = np.zeros(0, dtype=np.float32)
        self._far_t = 0.0                            # когда зазвучит начало _far_rest
        self._near_in = np.zeros(0, dtype=np.int16)
        self._near_out = collections.deque()
        self.voice_until = 0.0                       # до какого момента звучит (и ещё TAIL_S) свой голос
        self.frames = self.cleaned = 0

    # ---------- дальний сигнал: что играем ----------

    def far(self, pcm: bytes, rate: int, ch: int, play_at: float):
        """Кусок голоса (s16le, rate, ch), который зазвучит в play_at (monotonic)."""
        a = _to16k(pcm, rate, ch)
        if not len(a):
            return
        with self._lock:
            if not len(self._far_rest) or abs(self._far_t + len(self._far_rest) / RATE - play_at) > 0.05:
                self._flush_rest()
                self._far_t = play_at
            self._far_rest = np.concatenate([self._far_rest, a])
            while len(self._far_rest) >= CHUNK:
                self._far.append((self._far_t, self._far_rest[:CHUNK]))
                self._far_rest, self._far_t = self._far_rest[CHUNK:], self._far_t + CHUNK / RATE
            self.voice_until = max(self.voice_until, play_at + len(a) / RATE + TAIL_S)
            while len(self._far) > 400:              # больше 4 с впереди — не нужно
                self._far.popleft()

    def _flush_rest(self):
        if len(self._far_rest):
            pad = np.zeros(CHUNK, dtype=np.float32)
            pad[: len(self._far_rest)] = self._far_rest[:CHUNK]
            self._far.append((self._far_t, pad))
        self._far_rest = np.zeros(0, dtype=np.float32)

    def _far_chunk(self, now):
        """Кусок дальнего сигнала на эти 10 мс микрофона: то, что уже должно звучать; иначе тишина."""
        with self._lock:
            while len(self._far) > 1 and self._far[1][0] <= now - 0.5:   # отстали больше чем на полсекунды — догоняем
                self._far.popleft()
            if self._far and self._far[0][0] <= now:
                return self._far.popleft()[1]
        return None

    # ---------- микрофон ----------

    def near(self, frame: bytes, now=None) -> bytes:
        now = time.monotonic() if now is None else now
        self._near_in = np.concatenate([self._near_in, np.frombuffer(frame, dtype=np.int16)])
        voice = now < self.voice_until
        while len(self._near_in) >= CHUNK:
            mic, self._near_in = self._near_in[:CHUNK], self._near_in[CHUNK:]
            f = self._far_chunk(now)
            ref = np.zeros(CHUNK, dtype=np.int16) if f is None else np.clip(f, -32768, 32767).astype(np.int16)
            try:
                self.ap.process_reverse_stream(ref.tobytes())
                out = np.frombuffer(self.ap.process_stream(mic.tobytes()), dtype=np.int16)
            except Exception:  # noqa: BLE001 — сбой обработки: этот кусок как есть
                out = mic
            self._near_out.append(out if voice else mic)
        need = len(frame) // 2
        have = sum(len(x) for x in self._near_out)
        self.frames += 1
        if have < need:                              # первые кадры: ещё копим 10 мс — отдаём как есть
            return frame
        buf = np.concatenate(list(self._near_out))
        out, rest = buf[:need], buf[need:]
        self._near_out = collections.deque([rest] if len(rest) else [])
        if voice:
            self.cleaned += 1
        return out.astype(np.int16).tobytes()
