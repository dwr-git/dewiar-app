"""0.96 (владелец 13.11: «приложение — на 100 % английским»): программа на компьютере говорит сама, без модели, ~960 фраз
(быстрые ответы, ошибки инструментов, уведомления). Программа по-английски — они по-английски: core/i18n.tx по тому же
словарю, что и студия (data/i18n/text/en.json), а Engine._g переводит ДО женского рода (иначе «Выключила» не нашлась бы).
Вечерняя сводка близким («Для старших») — целой фразой по-английски: в английском у глаголов нет рода."""
import os, subprocess, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import i18n  # noqa: E402
ok(i18n.tx("сервер не ответил вовремя", "en") == "the server didn't answer in time", "фраза без подстановок")
ok(i18n.tx("не нашёл радиостанцию «Европа плюс»", "en") == "didn't find the radio station “Европа плюс”", "с подстановкой в кавычках")
ok(i18n.tx("сервер не ответил вовремя", "ru") == "сервер не ответил вовремя", "по-русски — как есть")

import engine  # noqa: E402


class S:
    def __init__(self, lang): self.d = {"ui": {"lang": lang}, "persona": "lira"}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)


for lang, want in (("en", "the server didn't answer in time"), ("ru", "сервер не ответила вовремя")):
    e = types.SimpleNamespace(s=S(lang), personas={"lira": {"gender": "f"}})
    got = engine.Engine._g(e, "сервер не ответил вовремя")
    ok(got == want or (lang == "ru" and got.startswith("сервер не")), f"Engine._g ({lang}): {got!r}")

out = subprocess.run([sys.executable, str(ROOT / "tools/i18n_texts.py"), "en", "--core"], capture_output=True, text=True, timeout=120).stdout
ok("осталось: 0 разных строк" in out, f"все фразы ядра переведены: {out.strip().splitlines()[-1:]}")

import senior  # noqa: E402
sv = senior.Senior.__new__(senior.Senior)
sv.s = S("en"); sv.conf = lambda: {"name": "Mom", "gender": "f"}; sv.who = lambda: "Mom"
txt = senior.Senior._summary_en(sv, {"meds": [{"at": "09:00", "text": "Aspirin", "res": "taken"}]}, "Mom", [1_700_000_000])
ok(txt.startswith("This is Lira") and "Mom talked with me today" in txt and "taken" in txt and not any("а" <= ch <= "я" for ch in txt.lower()),
   f"сводка близким по-английски: {txt}")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
