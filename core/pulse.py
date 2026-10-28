"""Linux: звук напрямую через libpulse (ctypes) — без консольных утилит pactl/parec/pacat.

libpulse0 есть в любой Ubuntu (на ней работает и PulseAudio, и PipeWire), поэтому лишних пакетов из apt не нужно.
  • SimpleStream — запись/воспроизведение (libpulse-simple);
  • control() и обёртки — устройства, модули, громкость (pulsectl — чистый Python над libpulse).
Используется из audio_io.py. Устройства с именами dewiar_* — наши (эхоподавление, AEC_SOURCE/AEC_SINK в audio_io.py),
в списках для выбора их не показываем.
"""

import ctypes
import ctypes.util
import logging

log = logging.getLogger("dewiar.pulse")

PA_SAMPLE_S16LE = 3
PA_STREAM_PLAYBACK, PA_STREAM_RECORD = 1, 2
_NO = 0xFFFFFFFF                    # (uint32_t)-1 в pa_buffer_attr: «на усмотрение сервера»


class _Spec(ctypes.Structure):
    _fields_ = [("format", ctypes.c_int), ("rate", ctypes.c_uint32), ("channels", ctypes.c_uint8)]


class _Attr(ctypes.Structure):
    _fields_ = [("maxlength", ctypes.c_uint32), ("tlength", ctypes.c_uint32), ("prebuf", ctypes.c_uint32),
                ("minreq", ctypes.c_uint32), ("fragsize", ctypes.c_uint32)]


_lib = None


def _simple():
    global _lib
    if _lib is None:
        name = ctypes.util.find_library("pulse-simple") or "libpulse-simple.so.0"
        lib = ctypes.CDLL(name)
        lib.pa_simple_new.restype = ctypes.c_void_p
        lib.pa_simple_new.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p,
                                      ctypes.POINTER(_Spec), ctypes.c_void_p, ctypes.POINTER(_Attr),
                                      ctypes.POINTER(ctypes.c_int)]
        for fn in ("pa_simple_read", "pa_simple_write"):
            getattr(lib, fn).argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_int)]
        for fn in ("pa_simple_drain", "pa_simple_flush"):
            getattr(lib, fn).argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        lib.pa_simple_free.argtypes = [ctypes.c_void_p]
        lib.pa_simple_get_latency.restype = ctypes.c_uint64
        lib.pa_simple_get_latency.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        pulse = ctypes.CDLL(ctypes.util.find_library("pulse") or "libpulse.so.0")
        pulse.pa_strerror.restype = ctypes.c_char_p
        pulse.pa_strerror.argtypes = [ctypes.c_int]
        lib._strerror = pulse.pa_strerror
        _lib = lib
    return _lib


def available():
    try:
        _simple()
        return True
    except OSError:
        return False


class PulseError(Exception):
    pass


class SimpleStream:
    """Один поток PCM s16le mono. record=True — запись с источника, иначе воспроизведение. device "" — по умолчанию.
    Вызовы блокирующие: read() ждёт, пока наберётся n байт, write() — пока есть место в буфере."""

    def __init__(self, rate, record, device="", name="Dewiar", latency_ms=40, channels=1):
        lib = _simple()
        spec = _Spec(PA_SAMPLE_S16LE, rate, channels)     # 2 — стерео: музыка и радио (№374), голос — моно
        bytes_ = int(rate * 2 * channels * latency_ms / 1000)
        # запись: отдаём кусками по latency; вывод: буфер 2×latency, старт через 20 мс (короткие сигналы не ждут)
        attr = _Attr(_NO, _NO, _NO, _NO, bytes_) if record else _Attr(_NO, bytes_ * 2, int(rate * 2 * channels * 0.02), _NO, _NO)
        err = ctypes.c_int(0)
        self.s = lib.pa_simple_new(None, b"Dewiar", PA_STREAM_RECORD if record else PA_STREAM_PLAYBACK,
                                   device.encode() if device else None, name.encode(), ctypes.byref(spec), None,
                                   ctypes.byref(attr), ctypes.byref(err))
        if not self.s:
            raise PulseError(lib._strerror(err.value).decode(errors="replace"))
        self.lib = lib

    def read(self, n):
        buf = ctypes.create_string_buffer(n)
        err = ctypes.c_int(0)
        if self.lib.pa_simple_read(self.s, buf, n, ctypes.byref(err)) < 0:
            raise PulseError(self.lib._strerror(err.value).decode(errors="replace"))
        return buf.raw

    def write(self, data):
        err = ctypes.c_int(0)
        if self.lib.pa_simple_write(self.s, data, len(data), ctypes.byref(err)) < 0:
            raise PulseError(self.lib._strerror(err.value).decode(errors="replace"))

    def flush(self):
        err = ctypes.c_int(0)
        self.lib.pa_simple_flush(self.s, ctypes.byref(err))

    def drain(self):
        err = ctypes.c_int(0)
        self.lib.pa_simple_drain(self.s, ctypes.byref(err))

    def latency(self):
        """Сколько секунд уже записанного звука ещё не прозвучало."""
        err = ctypes.c_int(0)
        return self.lib.pa_simple_get_latency(self.s, ctypes.byref(err)) / 1e6

    def close(self):
        if self.s:
            self.lib.pa_simple_free(self.s)
            self.s = None


# ---------- управление: устройства и модули ----------

def control():
    import pulsectl
    return pulsectl.Pulse("dewiar")


def list_devices():
    out = []
    with control() as p:
        for s in p.source_list():
            if not s.name.endswith(".monitor") and not s.name.startswith("dewiar_"):
                out.append({"name": s.name, "description": s.description, "kind": "source"})
        for s in p.sink_list():
            if not s.name.startswith("dewiar_"):
                out.append({"name": s.name, "description": s.description, "kind": "sink"})
    return out


def has_source(name):
    with control() as p:
        return any(s.name == name for s in p.source_list())


def load_module(name, args):
    with control() as p:
        return p.module_load(name, args)


def unload_module(idx):
    with control() as p:
        p.module_unload(int(idx))


def volume(percent=None, change=None, mute=None):
    """Громкость выхода по умолчанию — вместо pactl set-sink-volume/-mute. Предел 150 %, как у ползунка системы.
    -> громкость в процентах после изменения."""
    with control() as p:
        sink = p.get_sink_by_name(p.server_info().default_sink_name)
        if mute is not None:
            p.mute(sink, bool(mute))
        if percent is not None:
            p.volume_set_all_chans(sink, max(0, min(150, percent)) / 100)
        if change is not None:
            cur = p.volume_get_all_chans(sink)
            p.volume_set_all_chans(sink, max(0.0, min(1.5, cur + change / 100)))
        return round(p.volume_get_all_chans(p.get_sink_by_name(sink.name)) * 100)
