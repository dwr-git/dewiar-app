"""№876 (18.11): «на компьютере нет микрофона и не планируется, а при включении и обновлении приложение очень долго ищет
микрофон и подготавливает транскрибацию — нужна настройка». Настройка есть — «Текстовый режим» (студия → «Чат»): теперь в
нём точное распознавание (GigaAM, до 100 с при первом запуске) не загружается совсем, а выключили режим — загрузится тогда.
И подсказка «Микрофон молчит» без настоящего микрофона сама предлагает «Текстовый режим»."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core")); sys.path.insert(0, str(ROOT / "tests"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import ears_models as EM  # noqa: E402
import srctext  # noqa: E402

loads = []


class G(EM.GigaAMSTT):
    def __init__(self): self._r, self.model_name = False, "gigaam"
    ready = property(lambda self: self._r)
    def cached(self): return True
    def load(self, on_progress=None): loads.append(1); self._r = True; return True


class S:
    def __init__(self, tm): self.tm = tm
    def get(self, a, b=None):
        return {"ui": {"text_mode": self.tm}, "tts": {"engine": "off"}}.get(a, {}).get(b) if b else {}


def eng(tm):
    e = types.SimpleNamespace(s=S(tm), stt=G(), status={}, notes=[])
    for n in ("_names_note", "ensure_voice", "health_mark", "_load", "_loaded", "_dl"):
        setattr(e, n, lambda *a, **k: None)
    e.note = lambda t: e.notes.append(t)
    e._mirror = lambda *a: None
    return e


e = eng(True)
EM.ModelsMixin._background_loads(e)
ok(not loads and not e.stt.ready, "текстовый режим — распознавание не загружается совсем")
e = eng(False)
EM.ModelsMixin._background_loads(e)
ok(loads and e.stt.ready, "обычный режим — как было, загружается")
src = srctext.text(ROOT, "core/commands_talk.py")
ok('if not getattr(self.stt, "ready", True):' in src and "target=self._background_loads" in src, "выключили текстовый режим — распознавание загрузится тогда")
mic = (ROOT / "core/ears_mic.py").read_text(encoding="utf-8")
ok("Микрофона нет и не будет? Включите «Текстовый режим»" in mic, "«Микрофон молчит» без настоящего микрофона — предлагает «Текстовый режим»")

# №1043 (24.11, Linux Mint): «у меня нет микрофона», в списке — аналоговый вход звуковой карты с пустым гнездом, ровные нули
import ears_mic as EMIC  # noqa: E402
import ears_base as EB  # noqa: E402


class Mic(EMIC.MicMixin):
    def __init__(self, cur=""):
        self.s = types.SimpleNamespace(get=lambda *k: cur if k == ("audio", "input") else None, update=lambda d: None)
        self.notes, self.reports = [], []
        self.note = self.notes.append
        self.push = lambda *a, **k: None
        self.report_problem = lambda sig, text: self.reports.append(sig)


EB.list_devices = lambda: [{"kind": "source", "description": "Starship/Matisse HD Audio Controller Аналоговый стерео"}]
_os = EMIC.os.name; EMIC.os.name = "posix"; _pl = EMIC.sys.platform; EMIC.sys.platform = "linux"
m = Mic("dewiar_mic"); m._mic_silent(exact=True)
ok(m.notes and "Текстовый режим" in m.notes[-1], f"ровные нули, вход звуковой карты без микрофона — предлагает «Текстовый режим»: {m.notes[-1][:90] if m.notes else ''!r}")
m = Mic(); m._mic_alive = True; m.s.get = lambda *k: 0 if k == ("audio", "mic_hint_at") else None
m._mic_silent(exact=False)
ok(m.notes and "Текстовый режим" not in m.notes[-1], "почти тишина при настоящем микрофоне — про «Текстовый режим» не говорим (он работает, просто тихо)")
# №1045 (24.11, Windows, QuadCast S): после каждого запуска — минута тишины, тревога и автоотчёт, а микрофон работает
class Mic2(Mic):
    def __init__(self, heard):
        super().__init__()
        self.pushes, st = [], {"audio": {"mic_heard": heard, "mic_hint_at": 0}}
        self.push = lambda *a, **k: self.pushes.append(a)
        self.s = types.SimpleNamespace(get=lambda *k: (st.get(k[0]) or {}).get(k[1]) if len(k) == 2 else None,
                                       update=lambda d: st["audio"].update(d.get("audio", {})))
        self.st = st


EB.list_devices = lambda: [{"kind": "source", "description": "Микрофон (HyperX QuadCast S)"}, {"kind": "source", "description": "Микрофон (Realtek(R) Audio)"}]
m = Mic2(True); m._mic_silent(exact=False)
ok(m.notes and not m.pushes and not m.reports, "микрофон этот компьютер уже слышал — «почти тишина» после запуска: подсказка, без тревоги и отчёта")
m = Mic2(None); m._mic_silent(exact=False)
ok(m.pushes and m.reports == ["mic_silent"], "ни разу не слышал — тревога и отчёт, как раньше")
import numpy as _np  # noqa: E402
m = Mic2(None); m.note = lambda t: None
m._mic_zero_step({"since": None, "told": False, "all": True}, (_np.full(160, 200, dtype=_np.int16)).tobytes(), 0.0)
ok(m.st["audio"]["mic_heard"] is True, "услышали голос — запомнили навсегда (audio.mic_heard)")
EMIC.os.name, EMIC.sys.platform = _os, _pl
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
