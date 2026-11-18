"""№861 (18.11): «ни один источник Дзена не содержит информации — ни канал, ни сводка новостей». Дзен — страница,
которую собирает скрипт, без ленты: Радар ничего на ней не находил и молчал. Теперь Дзен узнаётся сразу и честно
объясняется (не прочитать — возьмите Telegram-канал или сайт автора), как веб-Telegram с номером канала."""
import json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import insight as I  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


for u in ("https://dzen.ru/rbc", "https://dzen.ru/news", "https://zen.yandex.ru/id/5f2b"):
    d = I.detect(u) or {}
    ok(d.get("kind") == "dzen" and d.get("bad") == "dzen", f"{u} — Дзен, с объяснением: {d}")
ok((I.detect("https://habr.com/ru/feed/") or {}).get("bad") is None, "остальные источники — как были")
for lang in ("ru", "en"):
    t = json.loads((ROOT / f"data/i18n/{lang}.json").read_text(encoding="utf-8")).get("insight.src.why.dzen", "")
    ok("Telegram" in t, f"объяснение ({lang}): {t[:80]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
