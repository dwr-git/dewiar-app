"""№981 (23.11, Ubuntu): «целый день на виджете висит, что Лира не распознала длинную фразу… ни закрыть, ни стереть».
Подсказка про длинную фразу без имени теперь уходит сама через 45 с (если её не сменила другая)."""
import os, sys, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "core/engine.py").read_text(encoding="utf-8")
i = src.index("    def note(self, text, ttl=0):"); j = src.index("\n    def ", i + 10)
ns = {"threading": threading}
exec("class E:\n" + src[i:j] + "\n", ns)
e = ns["E"](); e.status, e.emitted = {}, []
e._g = lambda t: t
e.emit = lambda k, **d: e.emitted.append(dict(d["status"]))
e.note("Длинную фразу без имени я приняла за разговор рядом…", ttl=0.2)
time.sleep(0.4)
ok(e.status["note"] == "", "подсказка ушла сама")
e.note("первая", ttl=0.2); e.note("другая")
time.sleep(0.4)
ok(e.status["note"] == "другая", "новую подсказку старый таймер не стирает")
aud = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok("«найди…».\", ttl=45)" in aud, "подсказка про длинную фразу — с ttl 45 с")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
