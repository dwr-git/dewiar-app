"""№689 (13.11, Андрей, Windows 10, 0.93.0): «у меня стоит локальное распознавание, но периодически оно сбрасывается на Dewiar
и обратно не возвращается». Лёгкий режим (сам включается, когда компьютеру не хватает памяти) отдавал распознавание серверу
Dewiar, а выключаясь — возвращал только голос. Теперь: что отдал лёгкий режим — он и возвращает; выбранное человеком
(свой сервер распознавания, облако по своему выбору) — не трогает."""
import os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
os.environ["DEWIAR_CONFIG_DIR"], os.environ["DEWIAR_STATE_DIR"] = tempfile.mkdtemp(), tempfile.mkdtemp()
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from settings import Settings  # noqa: E402
import engine_brain as EB  # noqa: E402


def eng(cloud_ok=True, acc=""):
    s = Settings(); s.update({"tts": {"engine": "vosk"}, "stt": {"engine": "gigaam"}})
    me = types.SimpleNamespace(s=s, device={"sig": "x"}, stt=None, apply_engines=lambda: None, ensure_voice=lambda p: None,
                               emit=lambda *a, **k: None, device_status=lambda: {}, _cloud_stt_ok=lambda: cloud_ok)
    me.account = types.SimpleNamespace(service_url=lambda k: acc, token=lambda: "t")
    me.cloud = types.SimpleNamespace(set_stt=lambda on: s.update({"stt": {"engine": "remote", "remote": {"base_url": "https://dewiar.pro/x", "cloud": True}}}))
    me._apply_light_stt = lambda how: EB.BrainMixin._apply_light_stt(me, how)
    return me, s


me, s = eng()
EB.BrainMixin.set_light(me, True)
ok(s.get("stt", "engine") == "remote" and s.get("device", "light_stt") == "cloud", "лёгкий режим: речь — серверу Dewiar (отмечено, что это он)")
done = EB.BrainMixin.set_light(me, False)
ok(s.get("stt", "engine") == "gigaam" and not (s.get("stt", "remote") or {}).get("cloud"), f"выключился — распознавание снова своё: {done}")
ok(s.get("tts", "engine") == "vosk", "и голос — снова Vosk, как было")

me, s = eng(cloud_ok=False, acc="https://dewiar.pro/stt")
EB.BrainMixin.set_light(me, True)
ok(s.get("stt", "engine") == "remote" and (s.get("stt", "remote") or {}).get("from_account"), "через аккаунт — тоже сервер")
EB.BrainMixin.set_light(me, False)
ok(s.get("stt", "engine") == "gigaam", "и тоже возвращается")

me, s = eng()
s.update({"stt": {"engine": "remote", "remote": {"base_url": "https://dewiar.pro/x", "cloud": True}}})   # человек сам выбрал облако
EB.BrainMixin.set_light(me, False)
ok(s.get("stt", "engine") == "remote", "облако, выбранное человеком (не лёгким режимом), — не трогаем")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
