"""Сбой из пакета 04.11 (27 раз, 8 компьютеров, 0.82.0): «Модель (openai): на ключе нет оплаченного пакета или закончились
деньги — пополните баланс у сервиса». У какого сервиса, где пополнить, а если не хочется — что тогда? И каждый вопрос
уходил дважды: второй раз «без действий» — с тем же пустым счётом.
Теперь: название сервиса и страница пополнения по адресу, выход без своего ключа — «Dewiar Облако» в «Мозге»; повтора
без действий нет; дела по расписанию по-прежнему не повторяют (ошибка постоянная)."""
import json, os, sys
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


def resp(code, body, url):
    req = httpx.Request("POST", url + "/chat/completions")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req, content=json.dumps(body).encode()))


cases = [("https://openrouter.ai/api/v1", 402, {"error": {"message": "Insufficient credits. Add more using https://openrouter.ai/settings/credits"}},
          "OpenRouter: https://openrouter.ai/settings/credits"),
         ("https://api.openai.com/v1", 429, {"error": {"message": "You exceeded your current quota, please check your plan and billing details."}},
          "OpenAI: https://platform.openai.com/settings/organization/billing"),
         ("https://api.deepseek.com/v1", 402, {"error": {"message": "Insufficient Balance"}}, "DeepSeek: https://platform.deepseek.com/top_up"),
         ("https://my-llm.example.org/v1", 402, {"error": {"message": "insufficient funds"}}, "у сервиса my-llm.example.org")]
for url, code, body, want in cases:
    t = llm._humanize(resp(code, body, url), url)
    ok(want in t and "«Мозге» выберите «Dewiar Облако»" in t and llm.NO_MONEY_TEXT[:40] in t, f"{url}: {t[:150]}")
z = llm._humanize(resp(429, {"error": {"code": "1113", "message": "Insufficient balance or no resource package. Please recharge."}},
                       "https://api.z.ai/api/paas/v4"), "https://api.z.ai/api/paas/v4")
ok("Z.ai" in z and "coding/paas/v4" in z and "Dewiar Облако" in z, f"Z.ai — как раньше и с выходом: {z[:120]}")
ok(llm.topup_page("http://127.0.0.1:1234/v1") == ("127.0.0.1", ""), "незнакомый адрес — без выдуманной ссылки")

import engine_answer as EA  # noqa: E402
ok(EA._no_money(llm.LLMError(z)) and not EA._no_money(llm.LLMError("сервер модели не ответил вовремя")), "«нет денег» узнаётся")
src = (ROOT / "core" / "engine_answer.py").read_text(encoding="utf-8")
ok('and "без текста" not in str(e) and not _no_money(e):' in src, "повтора «без действий» на пустой счёт нет — один запрос на вопрос")
mus = (ROOT / "core" / "engine_music.py").read_text(encoding="utf-8")
ok("NO_MONEY_TEXT[:40] in text" in mus, "дела по расписанию: пустой счёт — без повторов через 5 и 15 минут")
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
