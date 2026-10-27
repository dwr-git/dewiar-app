"""№261 (пакет 25.10): «пишет, что идёт созвон VoiceAttack — он установлен, но не запущен». Реестр Windows «кто держит
микрофон» (ConsentStore\\microphone) — подставной: голосовые команды и диктовка (VoiceAttack, Handy, Voicemeeter…) —
не созвон; запись осталась от закрытой программы — не созвон; настоящий Zoom, который запущен, — созвон."""
import os, sys, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


now = int((time.time() + 11644473600) * 1e7)
BASE = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
TREE = {BASE: {}, BASE + r"\NonPackaged": {}}


def setup(apps):
    TREE[BASE + r"\NonPackaged"] = {a.replace("\\", "#"): {"LastUsedTimeStop": 0, "LastUsedTimeStart": now - 600 * 10**7} for a in apps}


wr = types.ModuleType("winreg")
wr.HKEY_CURRENT_USER = 1
wr.OpenKey = lambda k, path: path if not isinstance(k, str) else k + "\\" + path
def _enum(k, i):
    keys = list(TREE.get(k, {}).keys()) + (["NonPackaged"] if k == BASE else [])
    if i >= len(keys):
        raise OSError
    return keys[i]
wr.EnumKey = _enum
def _q(k, name):
    parent, sub = k.rsplit("\\", 1)
    return (TREE[parent][sub][name], 4)
wr.QueryValueEx = _q
wr.CloseKey = lambda k: None
sys.modules["winreg"] = wr
RUN = {"zoom.exe"}
ps = types.ModuleType("psutil")
ps.process_iter = lambda attrs: [types.SimpleNamespace(info={"name": n}) for n in RUN]
sys.modules["psutil"] = ps
import meeting  # noqa: E402

setup([r"C:\Program Files (x86)\Steam\steamapps\common\VoiceAttack\VoiceAttack.exe", r"C:\Users\u\AppData\Local\Handy\handy.exe"])
ok(meeting._windows() == [], f"VoiceAttack и Handy держат микрофон — не созвон: {meeting._windows()}")
setup([r"C:\Program Files\Zoom\bin\Zoom.exe"])
ok(meeting._windows() == ["Zoom"], f"запущенный Zoom — созвон: {meeting._windows()}")
RUN.clear()
ok(meeting._windows() == [], "Zoom закрыт, а запись в реестре осталась — не созвон")
setup([r"C:\Apps\Voicemeeter\voicemeeter8x64.exe"]); RUN.add("voicemeeter8x64.exe")
ok(meeting._windows() == [], "Voicemeeter — не созвон")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
