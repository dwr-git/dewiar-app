"""Частые сбои 18.11 (компьютер 1.0.24, в один и тот же час): «Prompt tokens limit exceeded: 17987 > 17725. To increase,
visit https://openrouter.ai/settings/credits and upgrade to a paid account» рядом с «на ключе нет оплаченного пакета».
Это предел бесплатного ключа OpenRouter, а не окно модели: не «урезать подсказку», а одна понятная фраза — пополнить
OpenRouter или выбрать облако Dewiar, как при нехватке денег."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import httpx  # noqa: E402
import llm  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


body = '{"error":{"message":"Prompt tokens limit exceeded: 17987 > 17725. To increase, visit https://openrouter.ai/settings/credits and upgrade to a paid account","code":402}}'
e = httpx.HTTPStatusError("402", request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
                          response=httpx.Response(402, text=body))
t = llm._humanize(e, "https://openrouter.ai/api/v1", "deepseek/deepseek-chat")
ok(t.startswith(llm.NO_MONEY_TEXT) and "openrouter.ai/settings/credits" in t and "Dewiar" in t,
   f"предел бесплатного ключа OpenRouter — «пополните или облако Dewiar»: {t[:120]!r}")
ok(not llm.ctx_full(t), "это не «не хватило окна модели» — подсказку не урезаем")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
