"""№917 (Windows, отчёт «сам при сбое»): прокси обрывал ответ — проверка «адрес сайта в домашней сети» писала ERROR с
трассировкой, и программа сама слала отчёт о сбое. Обрыв сети — строка в журнале, не сбой."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
src = (ROOT / "core/engine_brain.py").read_text(encoding="utf-8")
blk = src[src.index("self._lan_fetch()                              # дома"):][:700]
ok = "isinstance(e, (httpx.HTTPError, OSError))" in blk and "log.info(\"Адрес сайта в домашней сети не узнал" in blk \
     and blk.index("log.info") < blk.index("log.exception")
print(("✅ " if ok else "❌ ") + "обрыв сети при проверке домашнего адреса — не сбой (без трассировки и отчёта)")
print("ALL OK" if ok else "FAILED 1")
sys.exit(0 if ok else 1)
