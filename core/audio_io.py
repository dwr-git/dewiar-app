"""Звук: эхоподавление (EchoCancel), микрофон (Capture), воспроизведение (Player), сигналы (tone, alarm_tone).

Linux: слушаем не сырой микрофон, а виртуальный dewiar_mic с эхоподавлением WebRTC (module-echo-cancel в
PipeWire/PulseAudio), а голос играем в парный dewiar_out. Система знает, что звучит из колонок, и вычитает это из
микрофона — ассистент не слышит сам себя, и его можно перебить. Модуль живёт только на время работы.
Без эхоподавления (и всегда в Windows) — полудуплекс: пока ассистент говорит, микрофон не слушаем.
Способы доступа к звуку (_backend): libpulse (pulse.py) → утилиты parec/pacat → sounddevice; кадры — 16 кГц int16.
"""

import logging
import math
import os
import sys
import shutil
import subprocess
import queue
import threading
import time
import wave

import numpy as np

import pulse

log = logging.getLogger("dewiar.audio")

RATE = 16000
FRAME = 512                         # 32 мс — родной размер кадра Silero VAD
AEC_SOURCE = "dewiar_mic"
AEC_SINK = "dewiar_out"
# Аналоговая АРУ WebRTC сама крутит громкость микрофона в системе и часто опускает её до 30 % —
# ассистент перестаёт слышать имя. Выключаем её, оставляя мягкое цифровое усиление тихой речи.
AEC_ARGS = 'aec_args="analog_gain_control=0 digital_gain_control=1"'


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


WIN = os.name == "nt"
MAC = sys.platform == "darwin"


def _backend():
    """libpulse напрямую (есть в любой Ubuntu) → утилиты pulseaudio-utils → sounddevice (Windows)."""
    forced = os.environ.get("DEWIAR_AUDIO_BACKEND", "")
    if forced:
        return forced
    if WIN or MAC:                      # macOS: PulseAudio из Homebrew бывает наполовину (пакет 20.10: «dlopen libpulse.so.0») —
        return "sounddevice"            # CoreAudio через sounddevice надёжнее
    if pulse.available():
        return "libpulse"
    return "cli" if shutil.which("parec") and shutil.which("pacat") else "sounddevice"


def _pulsectl_ok():
    """Управлять устройствами через pulsectl, а не pactl: есть пакет и способ доступа не переопределён вручную."""
    if WIN or MAC:
        return False
    try:
        import pulsectl  # noqa: F401
        return os.environ.get("DEWIAR_AUDIO_BACKEND", "libpulse") == "libpulse"
    except ImportError:
        return False


# PortAudio (Windows) читает список устройств один раз — при первом import sounddevice. Микрофон, подключённый позже,
# не виден, а номер отключённого даёт «device ID out of range» (MME 2) или «Undefined external error» (MME 1) —
# отчёты 21.10 (№165, сбои аудиопотока). sd_refresh перечитывает список, когда ни один наш поток PortAudio не открыт.
_SD_LOCK, _SD_OPEN, _SD_AT = threading.RLock(), [0], [0.0]


def _sd_open(n):
    with _SD_LOCK:
        _SD_OPEN[0] = max(0, _SD_OPEN[0] + n)


def sd_refresh(force=False):
    """Перечитать устройства PortAudio. -> True, если перечитали. Не чаще раза в 3 с и только без открытых потоков:
    Pa_Terminate оборвал бы их."""
    import sounddevice as sd
    with _SD_LOCK:
        if _SD_OPEN[0] or (not force and time.monotonic() - _SD_AT[0] < 3):
            return False
        try:
            sd._terminate()
            sd._initialize()
        except Exception as e:  # noqa: BLE001
            log.warning("Список звуковых устройств не обновлён: %s", e)
            return False
        _SD_AT[0] = time.monotonic()
        return True


def _sd_devices():
    """Windows: устройства одного звукового API (того, что у микрофона по умолчанию — обычно MME: он сам приводит
    частоту к 16 кГц, а одно устройство в разных API иначе показалось бы несколько раз). Имя — его id в настройках."""
    import sounddevice as sd
    devs = sd.query_devices()
    try:
        api = devs[sd.default.device[0]]["hostapi"] if sd.default.device[0] >= 0 else 0
    except Exception:  # noqa: BLE001
        api = 0
    out = []
    for i, d in enumerate(devs):
        if d["hostapi"] != api:
            continue
        name = d["name"].strip()
        if d["max_input_channels"] > 0:
            out.append({"name": name, "description": name, "kind": "source", "index": i})
        if d["max_output_channels"] > 0:
            out.append({"name": name, "description": name, "kind": "sink", "index": i})
    return out


def _sd_index(name, kind):
    """Имя из настроек → номер устройства (None — по умолчанию)."""
    if not name:
        return None
    try:
        for d in _sd_devices():
            if d["kind"] == kind and d["name"] == name:
                return d["index"]
    except Exception:  # noqa: BLE001
        pass
    log.warning("Устройство «%s» не найдено — беру устройство по умолчанию", name)
    return None


def list_devices():
    """-> [{"name", "description", "kind": "source" | "sink"}] — микрофоны и выходы, без наших dewiar_* и мониторов."""
    if WIN:
        try:
            sd_refresh()                        # подключили микрофон после запуска — студия его увидит
            with _SD_LOCK:
                return [{k: d[k] for k in ("name", "description", "kind")} for d in _sd_devices()]
        except Exception as e:  # noqa: BLE001
            log.warning("Список звуковых устройств не получен: %s", e)
            return []
    if _pulsectl_ok():
        try:
            return pulse.list_devices()
        except Exception as e:  # noqa: BLE001
            log.warning("Список устройств через libpulse не получен: %s", e)
    out = []
    for kind in ("sources", "sinks"):
        code, text, _ = _run(["pactl", "list", kind])
        if code:
            continue
        name = None
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("Name:"):
                name = s.split(":", 1)[1].strip()
            elif s.startswith("Description:") and name:
                desc = s.split(":", 1)[1].strip()
                is_monitor = name.endswith(".monitor")
                if not name.startswith("dewiar_") and not is_monitor:
                    out.append({"name": name, "description": desc, "kind": kind[:-1]})
                name = None
    return out


class EchoCancel:
    """Загрузка и выгрузка module-echo-cancel. setup() -> True, если эхоподавление работает (своё или оставшееся
    от прошлого запуска, если тот завершился аварийно); False — работаем в полудуплексе."""

    def __init__(self):
        self.module_id = None
        self.active = False

    def setup(self, source_master="", sink_master=""):
        if WIN:
            if not getattr(EchoCancel, "_said", False):     # один раз, а не при каждом переподключении микрофона
                log.info("Windows: системного эхоподавления нет — пока ассистент говорит, микрофон не слушаем "
                         "(в наушниках включите «Я в наушниках»)")
                EchoCancel._said = True
            return False
        if _pulsectl_ok():
            try:
                if pulse.has_source(AEC_SOURCE):
                    log.info("Эхоподавление уже загружено (остался модуль от прошлого запуска) — использую его")
                    self.active = True
                    return True
                args = (f"aec_method=webrtc source_name={AEC_SOURCE} sink_name={AEC_SINK} "
                        "source_properties=device.description=Dewiar-mic sink_properties=device.description=Dewiar-voice")
                if source_master:
                    args += f" source_master={source_master}"
                if sink_master:
                    args += f" sink_master={sink_master}"
                try:
                    self.module_id = str(pulse.load_module("module-echo-cancel", args + " " + AEC_ARGS))
                except Exception:  # noqa: BLE001 — сервер не понял настройки усиления (AEC_ARGS): загружаем без них
                    self.module_id = str(pulse.load_module("module-echo-cancel", args))
                self.active = True
                log.info("Эхоподавление WebRTC включено (модуль %s)", self.module_id)
                return True
            except Exception as e:  # noqa: BLE001
                log.warning("Не удалось включить эхоподавление (%s) — работаю в полудуплексе", e)
                return False
        if not shutil.which("pactl"):
            log.warning("Нет pactl (pulseaudio-utils) — работаю без эхоподавления")
            return False
        code, text, _ = _run(["pactl", "list", "short", "sources"])
        if code == 0 and AEC_SOURCE in text:
            log.info("Эхоподавление уже загружено (остался модуль от прошлого запуска) — использую его")
            self.active = True
            return True
        args = ["pactl", "load-module", "module-echo-cancel", "aec_method=webrtc",
                f"source_name={AEC_SOURCE}", f"sink_name={AEC_SINK}",
                "source_properties=device.description=Dewiar-микрофон",
                "sink_properties=device.description=Dewiar-голос"]
        if source_master:
            args.append(f"source_master={source_master}")
        if sink_master:
            args.append(f"sink_master={sink_master}")
        code, text, err = _run(args + [AEC_ARGS], timeout=10)
        if code != 0:
            code, text, err = _run(args, timeout=10)
        if code != 0:
            log.warning("Не удалось включить эхоподавление (%s) — работаю в полудуплексе", err or text)
            return False
        self.module_id = text.strip()
        self.active = True
        log.info("Эхоподавление WebRTC включено (модуль %s)", self.module_id)
        return True

    def teardown(self):
        if self.module_id:
            try:
                if _pulsectl_ok():
                    pulse.unload_module(self.module_id)
                else:
                    _run(["pactl", "unload-module", self.module_id])
            except Exception as e:  # noqa: BLE001
                log.warning("Модуль эхоподавления не выгружен: %s", e)
            log.info("Эхоподавление выключено")
        self.module_id, self.active = None, False


class Capture:
    """Поток кадров int16 по 512 сэмплов 16 кГц. Источник — libpulse напрямую, запасные —
    parec и sounddevice, для тестов — WAV-файл."""

    def __init__(self, device="", wav_path=None, realtime=True):
        self.device, self.wav_path, self.realtime = device, wav_path, realtime
        self.proc = None
        self.stream = None
        self._sd_q = None
        self.pa = None
        self._pa_lock = threading.Lock()

    def open(self):
        if self.wav_path:
            w = wave.open(str(self.wav_path), "rb")
            assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
            self._wav = w
            self._t0 = time.monotonic()
            self._n = 0
            return "файл " + str(self.wav_path)
        backend = _backend()
        if backend == "libpulse":
            try:
                self.pa = pulse.SimpleStream(RATE, True, device=self.device, name="Dewiar: слушаю", latency_ms=30)
                return self.device or "микрофон по умолчанию"
            except (OSError, pulse.PulseError) as e:
                log.warning("libpulse: микрофон не открылся (%s), пробую запасные способы", e)
                if self.device:                 # выбранный микрофон не подменяем другим — ошибку видно в окне
                    raise
        if backend in ("libpulse", "cli") and shutil.which("parec"):
            cmd = ["parec", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1",
                   "--latency-msec=30", "--client-name=Dewiar"]
            if self.device:
                cmd.append(f"--device={self.device}")
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            return self.device or "микрофон по умолчанию"
        import queue
        import sounddevice as sd
        self._sd_q = queue.Queue(maxsize=200)

        def cb(data, *_):
            try:
                self._sd_q.put_nowait(bytes(data))
            except queue.Full:                  # ядро не успевает — старый кадр не нужен
                pass
        mk = lambda i: sd.RawInputStream(samplerate=RATE, blocksize=FRAME, channels=1, dtype="int16", callback=cb, device=i)
        label = self.device or "микрофон по умолчанию"
        with _SD_LOCK:
            try:
                self.stream = mk(_sd_index(self.device, "source"))
            except sd.PortAudioError as e:     # номер устарел (микрофон отключили, переподключили) — перечитать список
                # пакет 27.10 (№293, №307): без микрофона эта строка шла каждые 5 с — 1400 строк вытесняли весь журнал.
                # Одна и та же ошибка — раз в 10 минут
                global _MIC_WARN
                key, now = str(e), time.monotonic()
                if _MIC_WARN[0] != key or now - _MIC_WARN[1] > 600:
                    log.warning("Микрофон не открылся (%s) — перечитываю список устройств", e)
                    _MIC_WARN = (key, now)
                sd_refresh(force=True)
                idx = _sd_index(self.device, "source")
                try:
                    self.stream = mk(idx)
                except sd.PortAudioError:
                    if idx is None:
                        raise
                    log.warning("«%s» недоступен — беру микрофон по умолчанию", self.device)
                    self.stream = mk(None)
                    label = "микрофон по умолчанию (выбранный недоступен)"
            self.stream.start()
            _sd_open(1)
        return label

    def read(self) -> bytes:
        """Блокирующее чтение одного кадра. b"" — источник закончился/упал."""
        need = FRAME * 2
        if self.wav_path:
            data = self._wav.readframes(FRAME)
            if len(data) < need:
                return b""
            self._n += FRAME
            if self.realtime:
                lag = self._t0 + self._n / RATE - time.monotonic()
                if lag > 0:
                    time.sleep(lag)
            return data
        if self.pa is not None:
            with self._pa_lock:
                if self.pa is None:
                    return b""
                try:
                    return self.pa.read(need)
                except pulse.PulseError as e:
                    log.warning("libpulse: %s", e)
                    return b""
        if self.proc:
            buf = b""
            while len(buf) < need:
                chunk = self.proc.stdout.read(need - len(buf))
                if not chunk:
                    return b""
                buf += chunk
            return buf
        import queue
        try:
            return self._sd_q.get(timeout=2)
        except queue.Empty:                     # микрофон отключили — пусть ядро переоткроет
            log.warning("Микрофон молчит больше 2 секунд")
            return b""

    def close(self):
        if self.pa is not None:
            with self._pa_lock:          # ждём конца текущего чтения (≤ 32 мс)
                pa, self.pa = self.pa, None
                if pa:
                    pa.close()
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            self.proc = None
        if self.stream:
            s, self.stream = self.stream, None
            try:
                s.stop()
                s.close()
            finally:
                _sd_open(-1)


class LoopbackCapture:
    """Звук компьютера — то, что играет в колонках или наушниках (голос собеседника в онлайн-встрече), для суфлёра
    (core/prompter.py). Те же кадры, что у Capture: 512 сэмплов 16 кГц int16. Linux — монитор устройства вывода по
    умолчанию (@DEFAULT_MONITOR@ в PulseAudio/PipeWire) через Capture; Windows — WASAPI loopback (библиотека soundcard);
    для проверок — WAV-файл (wav_path). open() -> что слушаем; нет способа — RuntimeError с понятным текстом."""

    def __init__(self, wav_path=None):
        self.wav_path = wav_path
        self._cap = None
        self._rec = None
        self._ctx = None

    def open(self):
        if self.wav_path or os.name != "nt":
            self._cap = Capture(device="" if self.wav_path else "@DEFAULT_MONITOR@", wav_path=self.wav_path)
            got = self._cap.open()
            return got if self.wav_path else "звук компьютера"
        try:
            import soundcard as sc
        except Exception as e:  # noqa: BLE001
            raise RuntimeError("для звука компьютера нужна библиотека soundcard — обновите Dewiar") from e
        spk = sc.default_speaker()
        mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
        self._ctx = mic.recorder(samplerate=RATE, channels=1, blocksize=FRAME)
        self._rec = self._ctx.__enter__()
        return "звук компьютера: " + spk.name

    def read(self) -> bytes:
        if self._cap is not None:
            return self._cap.read()
        if self._rec is None:
            return b""
        try:
            a = self._rec.record(numframes=FRAME)
        except Exception as e:  # noqa: BLE001 — устройство вывода сменили или отключили
            log.warning("Звук компьютера: %s", e)
            return b""
        a = np.asarray(a, dtype=np.float32).reshape(-1)
        return (np.clip(a, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

    def close(self):
        if self._cap is not None:
            self._cap.close()
            self._cap = None
        if self._ctx is not None:
            try:
                self._ctx.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self._ctx = self._rec = None


class AudioOutError(Exception):
    """Вывод звука не открылся: нет устройства, занято, выключено."""


_MIC_WARN = ("", -1e9)


class Player:
    """Воспроизведение PCM s16le mono с мгновенной остановкой: start(rate) → write()… → finish(); stop() — из
    другого потока. Пишем с опережением не больше AHEAD — поэтому «стоп» срабатывает сразу, а уровень громкости
    для анимации (on_level) совпадает со звуком. null=True — без звука, куски копятся в captured
    (тесты, запуск с --null-audio)."""

    AHEAD = 0.25
    LEAD = 0.25          # тишина перед ответом: устройство вывода (и эхоподавление) «просыпается» на первых долях секунды —
                         # без неё пропадала первая буква («Я Лира» звучало «лира», отзыв 17.10)

    def __init__(self, device="", on_level=None, null=False):
        self.device, self.on_level, self.null = device, on_level, null
        self.proc = None
        self.rate = 22050
        self._lock = threading.Lock()
        self._stopped = False
        self._t0 = 0.0
        self._written = 0
        self.captured = []           # для тестов (null=True)
        self.gain = 1.0              # приглушить, пока пользователь начинает говорить поверх ответа

    def start(self, rate):
        with self._lock:
            self._kill()
            self.rate, self._stopped, self.gain = rate, False, 1.0
            self._t0, self._written = time.monotonic(), 0
            self._lead = 0 if self.null else int(rate * self.LEAD) * 2
            if self.null:
                return
            backend = _backend()
            if backend == "libpulse":
                try:
                    self.proc = _PulseOut(rate, self.device)
                    return
                except (OSError, pulse.PulseError) as e:
                    log.warning("libpulse: вывод звука не открылся (%s), пробую запасные способы", e)
            if backend in ("libpulse", "cli") and shutil.which("pacat"):
                cmd = ["pacat", "--playback", "--raw", "--format=s16le", f"--rate={rate}", "--channels=1",
                       "--latency-msec=80", "--client-name=Dewiar"]
                if self.device:
                    cmd.append(f"--device={self.device}")
                self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            else:
                try:
                    import sounddevice as sd
                    with _SD_LOCK:
                        self.proc = sd.RawOutputStream(samplerate=rate, channels=1, dtype="int16",
                                                       device=_sd_index(self.device, "sink"))
                        self.proc.start()
                        _sd_open(1)
                except Exception as e:  # noqa: BLE001 — PortAudioError, нет библиотеки: нет устройства вывода или оно занято
                    self.proc = None
                    raise AudioOutError(f"вывод звука не открылся (нет устройства или оно занято): {e}") from e

    def write(self, pcm: bytes) -> bool:
        """Пишет кусками по 40 мс, выдерживая опережение AHEAD. -> False — остановлено (перебили) или вывод упал."""
        step = int(self.rate * 0.04) * 2
        if getattr(self, "_lead", 0):
            pcm, self._lead = b"\x00" * self._lead + pcm, 0
        for i in range(0, len(pcm), step):
            if self._stopped:
                return False
            chunk = pcm[i:i + step]
            if self.gain != 1.0:
                chunk = (np.frombuffer(chunk, dtype=np.int16).astype(np.float32) * self.gain).astype(np.int16).tobytes()
            ahead = self._t0 + self._written / self.rate - time.monotonic()
            if ahead > self.AHEAD:
                time.sleep(ahead - self.AHEAD)
            if self._written == 0 or ahead < 0:
                # догоняем реальное время (после паузы между фразами)
                self._t0 = time.monotonic() - self._written / self.rate
            try:
                if self.null:
                    self.captured.append(chunk)
                elif hasattr(self.proc, "stdin"):
                    self.proc.stdin.write(chunk)
                    self.proc.stdin.flush()
                else:
                    # №311, №315 (пакет 27.10): «access violation» в sounddevice.close — stop() из другого потока закрывал
                    # поток PortAudio посреди write. Запись и закрытие — под одним замком (кусок ≤ 40 мс)
                    with self._lock:
                        if self._stopped or self.proc is None:
                            return False
                        self.proc.write(chunk)
            except (BrokenPipeError, OSError, AttributeError):   # AttributeError: stop() обнулил self.proc на ходу
                return False
            self._written += len(chunk) // 2
            if self.on_level:
                a = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                self.on_level(min(1.0, float(np.sqrt(np.mean(a * a))) / 6000.0) if a.size else 0.0)
        return not self._stopped

    def finish(self):
        """Дождаться, пока доиграет хвост (и буфер сервера или звуковой карты, не дольше 1.5 с), и закрыть вывод."""
        rest = self._t0 + self._written / self.rate - time.monotonic()
        end = time.monotonic() + max(0.0, rest) + 0.15
        while time.monotonic() < end and not self._stopped:
            time.sleep(0.03)
        lat = 0.0
        if isinstance(self.proc, _PulseOut):          # хвост ещё в буфере сервера — доиграть
            lat = self.proc.latency()
        elif self.proc is not None and hasattr(self.proc, "latency") and not hasattr(self.proc, "stdin"):
            try:
                lat = float(self.proc.latency)        # sounddevice: буфер звуковой карты
            except (TypeError, ValueError):
                lat = 0.0
        if lat:
            end = time.monotonic() + min(1.5, lat)
            while time.monotonic() < end and not self._stopped:
                time.sleep(0.03)
        with self._lock:
            self._kill()
        if self.on_level:
            self.on_level(0.0)

    def stop(self):
        self._stopped = True
        with self._lock:
            self._kill()
        if self.on_level:
            self.on_level(0.0)

    def _kill(self):
        p, self.proc = self.proc, None
        if p is None:
            return
        try:
            if isinstance(p, _PulseOut):
                p.close()
            elif hasattr(p, "stdin"):
                p.kill()
                p.wait(timeout=2)
            else:
                try:
                    p.abort()
                    p.close()
                finally:
                    _sd_open(-1)
        except Exception:  # noqa: BLE001
            pass


class _PulseOut:
    """Выход через libpulse. Запись и закрытие — под одним замком: libpulse-simple не потокобезопасен,
    а «стоп» приходит из другого потока."""

    def __init__(self, rate, device):
        # Буфер сервера (2×200 мс) больше, чем Player пишет наперёд (0.25 с), — запись никогда не
        # блокируется, поэтому «стоп» из другого потока не ждёт; незвучавший хвост сбрасывается при закрытии.
        self.s = pulse.SimpleStream(rate, False, device=device, name="Dewiar: голос", latency_ms=200)
        self.lock = threading.Lock()

    def write(self, data):
        with self.lock:
            if self.s is None:
                raise OSError("закрыт")
            self.s.write(data)

    def latency(self):
        with self.lock:
            try:
                return self.s.latency() if self.s is not None else 0.0
            except Exception:  # noqa: BLE001
                return 0.0

    def close(self):
        with self.lock:
            s, self.s = self.s, None
        if s:
            s.close()           # незвучавший хвост сбрасывается сервером


def _fm_note(out, rate, start, f, dur, amp, ratio=3.5, index=2.2, decay=0.55, glide=0.0):
    """FM-колокол (как в tools/alarm_sounds.py): стеклянно-металлический тембр фирменного мотива."""
    i0 = int(rate * start)
    n = min(int(rate * dur), len(out) - i0)
    if n <= 0:
        return
    t = np.arange(n) / rate
    env = np.minimum(1, t / 0.003) * np.exp(-t / decay)
    ff = f * (1 - glide * np.exp(-t / 0.035))
    ph = 2 * math.pi * np.cumsum(ff) / rate
    out[i0:i0 + n] += (amp * env * np.sin(ph + index * np.exp(-t / (decay * 0.35)) * np.sin(ph * ratio))).astype(np.float32)


def _room(x, rate, seconds=1.4, decay=0.5, wet=0.24):
    """Мягкий «зал» без scipy: свёртка с затухающим шумом через FFT."""
    n = int(rate * seconds)
    rng = np.random.default_rng(7)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / rate / decay)
    ir = np.convolve(ir, np.ones(4) / 4, mode="same")              # чуть темнее
    ir /= np.sqrt(np.sum(ir ** 2))
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return ((1 - wet) * x + wet * 0.9 * y).astype(np.float32)


def signature_tone(rate=22050):
    """«Фирменный» звонок Dewiar — тот же мотив, что на телефоне (android/res/raw/alarm_signature.ogg):
    вверх на квинту, мягко вниз на терцию, искра; затем ответ выше."""
    hz = {"G5": 783.99, "D6": 1174.66, "B5": 987.77, "D7": 2349.32, "G6": 1567.98}
    out = np.zeros(int(rate * 3.4), dtype=np.float32)
    for st, nt, a, g in [(0.04, "G5", 0.7, 0.03), (0.2, "D6", 0.75, 0.02), (0.42, "B5", 0.65, 0.0)]:
        _fm_note(out, rate, st, hz[nt], 1.8, a, glide=g)
    _fm_note(out, rate, 0.62, hz["D7"], 1.0, 0.18, ratio=2.0, index=1.2, decay=0.35)
    for st, nt, a, g in [(1.55, "G5", 0.5, 0.03), (1.71, "D6", 0.55, 0.02), (1.93, "G6", 0.5, 0.0)]:
        _fm_note(out, rate, st, hz[nt], 1.4, a, glide=g)
    out = _room(out, rate)
    f = int(rate * 0.25)
    out[-f:] *= np.linspace(1, 0, f) ** 2
    out = out / max(1e-6, float(np.max(np.abs(out)))) * 0.6
    return (out * 32767).astype(np.int16).tobytes()


# Звонки (28.10, владелец выбрал пять из двенадцати): data/sounds/alarm_<id>.wav — моно 32 кГц; источник — звуки Android
# Open Source Project (Apache License 2.0, см. NOTICE): signature «Пульс» (Machina), noon «Полдень» (Solarium), night
# «Ночной город» (Sceptrum, первые 15 с), wave «Волна» (Zeta), sparks «Искры» (Perseus); громкость выровнена (loudnorm).
BRAND_SOUNDS = ("signature", "noon", "night", "wave", "sparks")
ALARM_RATE = 32000


def _wav_tone(name, rate):
    """Готовый звонок из data/sounds (моно 16 бит); другая частота — пересчёт линейной интерполяцией. Нет файла — None."""
    import wave
    from settings import DATA_DIR
    p = DATA_DIR / "sounds" / f"alarm_{name}.wav"
    try:
        with wave.open(str(p), "rb") as w:
            sr, ch, data = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    except (OSError, EOFError, wave.Error):
        return None
    a = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != rate:
        n = int(len(a) * rate / sr)
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)
    return np.clip(a, -32768, 32767).astype(np.int16).tobytes()


def alarm_tone(style="signature", rate=ALARM_RATE) -> bytes:
    """Звонок будильника — один из BRAND_SOUNDS (data/sounds). Прежние звуки (chasha, kolodec, hor, glubina, motif,
    bells, soft, classic — до 0.52) владелец убрал: у тех, кто их выбирал, звенит фирменный «Пульс». Нет файла — старый
    синтезированный мотив (signature_tone), чтобы будильник не молчал; synth:<bells|soft|classic> — синтез ниже (проверки)."""
    if not str(style or "").startswith("synth:"):
        pcm = _wav_tone(style if style in BRAND_SOUNDS else "signature", rate)
        return pcm or signature_tone(rate)
    style = style[6:]
    pats = {"bells": [(1046.5, 0.0), (1318.5, 0.18), (1568.0, 0.36), (2093.0, 0.54), (1568.0, 1.2), (2093.0, 1.38)],
            "soft": [(659.3, 0.0), (783.99, 0.3), (987.8, 0.6), (783.99, 1.2), (987.8, 1.5)],
            "classic": [(1760.0, x * 0.12) for x in range(8)] + [(1760.0, 1.2 + x * 0.12) for x in range(8)]}
    seq = pats.get(style, pats["bells"])
    total = 2.4
    out = np.zeros(int(rate * total), dtype=np.float32)
    for f, start in seq:
        dur = 0.09 if style == "classic" else 1.0
        n = int(rate * dur)
        t = np.arange(n) / rate
        env = np.exp(-t * (30 if style == "classic" else 4.5)) * np.minimum(1, t / 0.004)
        w = (np.sin(2 * math.pi * f * t) + 0.35 * np.sin(2 * math.pi * 2 * f * t) + 0.12 * np.sin(2 * math.pi * 3.01 * f * t))
        i = int(rate * start)
        seg = (0.28 * w * env)[: len(out) - i]
        out[i:i + len(seg)] += seg
    out = np.clip(out, -0.95, 0.95)
    return (out * 32767).astype(np.int16).tobytes()


def tone(kind: str, rate=22050) -> bytes:
    """Короткие сигналы состояний — синтезируются, без звуковых файлов. Колокольчиком: основной тон и мягкие обертоны,
    быстрая атака и затухание, ноты слегка наслаиваются. «Слушаю» — вверх и звонко, «не слушаю» / «сплю» — вниз и ниже,
    «ваша очередь» (ответ закончен, можно говорить без имени) — тихо и мягко, чтобы не надоедал в долгом разговоре.
    Отличаются на слух, не глядя на экран."""
    seq = {"wake": [(1046.5, 0.0), (1568.0, 0.07)],          # до → соль, вверх
           "turn": [(1318.5, 0.0), (1046.5, 0.11)],          # ми → до, мягко: «я договорила, ваша очередь»
           "done": [(1318.5, 0.0), (1760.0, 0.06)],
           "sleep": [(784.0, 0.0), (523.3, 0.08)],           # соль → до октавой ниже: «перестала слушать»
           "error": [(440.0, 0.0), (349.2, 0.12)]}.get(kind, [(1000.0, 0.0)])
    total = max(t for _, t in seq) + 0.26
    n = int(rate * total)
    a = np.zeros(n, dtype=np.float32)
    for f, start in seq:
        i0 = int(rate * start)
        t = np.arange(n - i0) / rate
        env = np.minimum(1.0, t / 0.004) * np.exp(-t / 0.075)            # щелчка нет, хвост — короткий
        wave = np.sin(2 * math.pi * f * t) + 0.28 * np.sin(2 * math.pi * 2 * f * t) + 0.08 * np.sin(2 * math.pi * 3.01 * f * t)
        a[i0:] += ((0.11 if kind == "turn" else 0.17) * env * wave).astype(np.float32)   # «ваша очередь» звучит часто — тише
    fade = min(n, int(rate * 0.01))
    a[-fade:] *= np.linspace(1, 0, fade)
    return (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()


class ToneOut:
    """Вывод для сигналов: открывается на первый сигнал и держится открытым ещё IDLE секунд — следующий звучит сразу
    (открытие звука занимает десятки–сотни миллисекунд). Свой Player — сигнал не мешает голосу ассистента."""

    IDLE = 30.0

    def __init__(self, device="", null=False):
        self.device, self.null = device, null
        self.pl, self.last, self._lock = None, 0.0, threading.Lock()
        self.q = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def play(self, pcm: bytes):
        self.q.put(pcm)

    def _run(self):
        while True:
            try:
                pcm = self.q.get(timeout=5)
            except queue.Empty:
                if self.pl is not None and time.monotonic() - self.last > self.IDLE:
                    self.pl.stop()
                    self.pl = None
                continue
            try:
                if self.pl is None:
                    self.pl = Player(device=self.device, null=self.null)
                    self.pl.start(22050)
                if not self.pl.write(pcm):                  # вывод упал (устройство пропало) — откроем заново
                    self.pl.stop()
                    self.pl = None
                self.last = time.monotonic()
            except Exception as e:  # noqa: BLE001 — сигнал не важнее работы: не вышло — тихо
                log.debug("сигнал не прозвучал: %s", e)
                self.pl = None
