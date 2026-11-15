"""«Без ответа» (1.0 «Надёжность», аналитика 14.11): на компьютере первая причина — «сервер модели не ответил вовремя»
(406 раз у 119 устройств за 30 дней); отчёт №69 — через 5 с: облако не успевало даже соединиться (рукопожатие TLS через
прокси, VPN, телефон-модем). Соединение с облаком ждём 10 с, со своей моделью на компьютере и в сети — по-прежнему 5 с;
ответа ждём как раньше (облако 3 мин, своя — 10)."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import llm  # noqa: E402

seen = []
real = llm.httpx.Timeout


def spy(*a, **k):
    seen.append((a, k))
    raise RuntimeError("стоп")


llm.httpx.Timeout = spy
try:
    for base in ("https://dewiar.pro/v1", "http://127.0.0.1:11434/v1", "http://192.168.1.5:1234/v1"):
        try:
            list(llm.stream_events({"base_url": base, "model": "m", "api_key": "k", "kind": "openai"}, "s", [{"role": "user", "content": "привет"}]))
        except Exception:  # noqa: BLE001
            pass
finally:
    llm.httpx.Timeout = real
ok(len(seen) == 3, f"таймауты собраны для трёх адресов ({len(seen)})")
if len(seen) == 3:
    (c, r, l) = seen
    ok(c[0][0] == 10 and c[1]["read"] == 180, f"облако: соединение 10 с, ответ 180 с ({c})")
    ok(r[0][0] == 5 and r[1]["read"] == 600 and l[0][0] == 5, f"своя модель на компьютере и в сети: соединение 5 с, ответ 10 мин ({r}, {l})")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
