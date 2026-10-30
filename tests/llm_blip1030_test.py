"""Связь моргнула (пакет 30.10: «не могу подключиться к dewiar.pro» — 25 раз у 15 компьютеров, по одному-два: ноутбук
проснулся, сеть поднимается). Облачной модели при отказе соединения — ещё ≈ 9 с (повтор через 1, 2,5 и 5 с), потом
честная ошибка; ожидание соединения (таймаут) — по-прежнему один повтор; своя модель на компьютере и в сети — как было."""
import contextlib, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import httpx  # noqa: E402
import llm  # noqa: E402

state = {"n": 0, "fail": 0, "exc": httpx.ConnectError, "sleeps": []}


class CM:
    def __enter__(self):
        state["n"] += 1
        if state["n"] <= state["fail"]:
            raise state["exc"]("связь моргнула")
        return "ответ"

    def __exit__(self, *a):
        return False


llm.httpx.stream = lambda *a, **k: CM()
llm.time.sleep = lambda s: state["sleeps"].append(s)
llm._lmstudio_wake = lambda url: None


def run(url, fail, exc=httpx.ConnectError):
    state.update(n=0, fail=fail, exc=exc, sleeps=[])
    try:
        with llm._stream_retry("POST", url) as r:
            return r, state["n"], list(state["sleeps"])
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, state["n"], list(state["sleeps"])


r = run("https://dewiar.pro/dwrapp/cloud.php?p=/chat/completions", 3)
ok(r[0] == "ответ" and r[1] == 4 and r[2] == [1.0, 2.5, 5.0], f"облако: три отказа соединения подряд — четвёртая попытка проходит ({r})")
r = run("https://dewiar.pro/dwrapp/cloud.php?p=/chat/completions", 9)
ok(r[0] == "ConnectError" and r[1] == 4 and sum(r[2]) == 8.5, f"облако: связи так и нет — честная ошибка через ≈ 9 с ({r})")
r = run("https://api.openai.com/v1/chat/completions", 2, httpx.ConnectTimeout)
ok(r[0] == "ConnectTimeout" and r[1] == 2, f"ожидание соединения — один повтор, как было (каждое и так долгое): {r}")
r = run("http://127.0.0.1:11434/v1/chat/completions", 2)
ok(r[0] == "ConnectError" and r[1] == 2 and r[2] == [0.8], f"своя модель на компьютере — как было: {r}")
r = run("http://192.168.1.5:1234/v1/chat/completions", 1)
ok(r[0] == "ответ" and r[1] == 2, f"своя модель в сети — один повтор: {r}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
