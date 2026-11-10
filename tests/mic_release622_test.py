"""№622 и идея №151 (07–08.11, Windows 11): «при выключенном микрофоне он всё равно занят программой — мессенджеры
ругаются, что микрофон занят другой программой; значок микрофона висит на панели задач». Раньше кнопка «микрофон»
только глушила кадры, а поток оставался открытым. Теперь (настоящий цикл слуха _audio_loop → _listen на поддельном
микрофоне):
— выключили — поток закрыт, кадры больше не читаются, устройство свободно (status.mic_free);
— включили — микрофон открыт заново за доли секунды (не ждём опроса);
— выключенный с самого запуска (замок «только кнопка», текстовый режим) — не открывается вовсе;
— «говорить» при выключенном (одна фраза) и удержание — открывают, после — снова закрыт;
— «Отдых» выключает микрофон тем же путём (set_mute) — поток закрыт;
— кольцо последних кадров очищается: удержание после включения не начинается со звука минутной давности;
— audio.mic_release = false — по-старому, поток открыт;
— идея №165: на время снимка с веб-камеры (mic_paused) поток закрыт, после — открыт снова."""
import collections, os, sys, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_audio  # noqa: E402
import engine_commands  # noqa: E402

FRAME = b"\x10\x00\xf0\xff" * 256              # 512 сэмплов «тихого шума»


class Mic:
    """Поддельный микрофон: считает открытия/закрытия и кадры."""
    opened = closed = reads = 0
    live = False

    def __init__(self):
        self.device, self.wav_path, self.def_sig = "", None, None

    def open(self):
        Mic.opened += 1
        Mic.live = True
        return "поддельный микрофон"

    def read(self):
        if not Mic.live:
            return b""
        Mic.reads += 1
        time.sleep(0.004)
        return FRAME

    def close(self):
        if Mic.live:
            Mic.closed += 1
        Mic.live = False


class Eng(engine_audio.AudioMixin, engine_commands.CommandsMixin):
    def __init__(self, muted=False, cfg=None):
        self.cfg = dict(cfg or {})
        self.s = types.SimpleNamespace(get=lambda sec, key=None: self.cfg.get(key) if key else {})
        self.stopping, self.restart_audio, self._mic_kick = threading.Event(), threading.Event(), threading.Event()
        self.muted, self._mute_pass, self.hold = muted, False, None
        self.wav_input, self.capture, self.player = None, None, None
        self.status = {"aec": False}
        self.state, self.events = "idle", []
        self._mic_ring = collections.deque(maxlen=40)
        self.aec = types.SimpleNamespace(teardown=lambda: None)
        self.spotter = types.SimpleNamespace(feed=lambda f: [], feed_stop_only=lambda f: None, last_final=None,
                                             rec=types.SimpleNamespace(Reset=lambda: None))
        self.vad = types.SimpleNamespace(prob=lambda f: 0.0, reset=lambda: None)
        self._quiet_until = self._wake_tone_due = 0.0
        self._pending_media_stop = 0.0
        self.follow_up_until = 0.0

    def _open_audio(self):
        self.capture = Mic()
        self.status["input"] = self.capture.open()

    def _pause_apply(self):
        pass

    def _mic_zero_step(self, *a):
        return None

    def _level(self, *a):
        pass

    def emit(self, ev, **kw):
        self.events.append((ev, kw))

    def note(self, t):
        pass

    def set_state(self, st):
        self.state = st

    def cancel_turn(self):
        return False

    def play_tone(self, *a):
        pass

    def interrupt(self, *a, **k):
        pass


def wait(cond, sec=2.0):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def run(e):
    t = threading.Thread(target=e._audio_loop, daemon=True)
    t.start()
    return t


# ── 1. включён — открыт и читает; выключили — закрыт совсем ──
Mic.opened = Mic.closed = Mic.reads = 0
e = Eng()
th = run(e)
ok(wait(lambda: Mic.reads > 20), f"микрофон включён — поток открыт и читается ({Mic.reads} кадров)")
e._mic_ring.extend([b"old"] * 30)
e.set_mute(True)
ok(wait(lambda: not Mic.live and e.status.get("mic_free")), "выключили кнопкой — поток закрыт, устройство свободно")
r0 = Mic.reads
time.sleep(0.4)
ok(Mic.reads == r0 and not Mic.live, f"пока выключен — ни одного чтения ({Mic.reads - r0})")
ok(not e._mic_ring, "кольцо последних кадров очищено (удержание не начнётся со старого звука)")
# ── 2. включили — открыт сразу ──
t0 = time.monotonic()
e.set_mute(False)
ok(wait(lambda: Mic.live and Mic.reads > r0, 1.0), f"включили — открыт заново за {time.monotonic() - t0:.2f} с")
ok(time.monotonic() - t0 < 0.4, "открытие не ждёт полусекундного опроса — его будит кнопка")
ok(not e.status.get("mic_free"), "status.mic_free снят")
# ── 3. «говорить» одной фразой и удержание при выключенном ──
e.set_mute(True)
ok(wait(lambda: not Mic.live), "снова выключили — закрыт")
n_open = Mic.opened
e._mute_pass = True
e._mic_kick_now()
ok(wait(lambda: Mic.live and Mic.opened == n_open + 1, 1.0), "«говорить» при выключенном — открыт для одной фразы")
e._mute_pass = False
ok(wait(lambda: not Mic.live), "фраза кончилась — снова закрыт")
e.hold_start = engine_audio.AudioMixin.hold_start.__get__(e)
e.hold_start(back_ms=400)
ok(wait(lambda: Mic.live, 1.0) and e.hold is not None and b"old" not in e.hold["pcm"], "удержание при выключенном — открыт; старого звука в записи нет")
e.hold = None
ok(wait(lambda: not Mic.live), "отпустили — снова закрыт")
# ── 4. идея №165: снимок с камеры при включённом микрофоне ──
e.set_mute(False)
ok(wait(lambda: Mic.live), "включён")
c0 = Mic.closed
with e.mic_paused("камера", wait=1.0):
    ok(not Mic.live and Mic.closed == c0 + 1 and e.status.get("mic_free"), "пока камера снимает — поток микрофона закрыт")
ok(wait(lambda: Mic.live, 1.0), "кадр снят — микрофон открыт снова сам")
e.stopping.set(); e._mic_kick_now(); th.join(2)

# ── 5. выключен с самого запуска — не открывается вовсе ──
Mic.opened = Mic.closed = Mic.reads = 0
e2 = Eng(muted=True)
th2 = run(e2)
time.sleep(0.4)
ok(Mic.opened == 0 and e2.status.get("mic_free"), "замок «только кнопка» / текстовый режим — микрофон при запуске не открывается")
e2.set_mute(False)
ok(wait(lambda: Mic.live, 1.0), "включили — открылся")
e2.stopping.set(); e2._mic_kick_now(); th2.join(2)

# ── 6. по-старому (audio.mic_release = false) — открыт, кадры глушатся ──
Mic.opened = Mic.closed = Mic.reads = 0
e3 = Eng(muted=True, cfg={"mic_release": False})
th3 = run(e3)
ok(wait(lambda: Mic.reads > 20) and Mic.live, "audio.mic_release = false — поток остаётся открытым, как раньше")
e3.stopping.set(); th3.join(2)

# ── 7. «Отдых» выключает микрофон через set_mute — в исходниках ──
src = (ROOT / "core/engine_rest.py").read_text(encoding="utf-8")
ok("self.set_mute(True)" in src, "«Отдых» выключает микрофон через set_mute — значит, поток закрывается тем же путём")
# ── 8. снимок с камеры — через mic_paused, если микрофон из той же камеры ──
tsrc = (ROOT / "core/tools.py").read_text(encoding="utf-8")
ok("mic_paused" in tsrc and "mic_shares_camera" in tsrc, "look_camera закрывает микрофон камеры на время кадра")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
