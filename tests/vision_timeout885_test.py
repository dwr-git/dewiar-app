"""№885 (18.11, журнал): «Модель … не приняла картинку (сервер модели не ответил вовремя)» — медленный сервер записывал модель
в «не видит картинок» на 15 минут, и следующие снимки уходили без картинки. Не дождались — не значит «не видит»: в _blind —
только настоящий отказ, не тайм-аут."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from health import why_kind  # noqa: E402
from llm import LLMError  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ok(why_kind(LLMError("сервер модели не ответил вовремя")) == "timeout", "«не ответил вовремя» — тайм-аут")
ok(why_kind(LLMError("model does not support image input")) != "timeout", "«не поддерживает картинки» — не тайм-аут")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
m = re.search(r"не приняла картинку.*?\n(.*?)msgs = _drop_images\(msgs\)", src, re.S)
ok(m and 'why_kind(e) in ("rejected", "other")' in m.group(1) and "self._blind.add(blind_key)" in m.group(1),
   "в «не видит картинок» — только настоящий отказ модели")
# №1150 (28.11): 429, 503, 401, нет связи — временное, а не «не видит картинок» на 15 минут
blind = lambda t: why_kind(LLMError(t)) in ("rejected", "other")   # noqa: E731
for t in ("HTTP 429 Too Many Requests", "503 Service Unavailable", "401 Unauthorized", "не удалось подключиться к серверу модели",
          "сервер модели не ответил вовремя"):
    ok(not blind(t), f"«{t}» — не «слепая»")
for t in ("400 Bad Request: image input is not supported", "model does not support image input"):
    ok(blind(t), f"«{t}» — да, не видит картинок")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
