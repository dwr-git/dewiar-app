"""Пакет 28.10 16:45: частые сбои. (1) «Задача: [groq/openai/gpt-oss-120b] [413]: Request too large… tokens per minute
(TPM): Limit 8000» — сырым текстом сервиса; теперь — понятно: лимит бесплатного тарифа, что выбрать. (2) веб-версия:
«Promise: No Listener: tabs:outgoing.message.ready» — сообщение расширения браузера, не наш сбой — разработчику не шлём."""
import os, sys
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
req = httpx.Request("POST", "http://127.0.0.1:4000/v1/chat/completions")
for code, body in ((413, {"error": {"message": "[groq/openai/gpt-oss-120b] [413]: Request too large for model `openai/gpt-oss-120b` in organization `org_x` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 9512"}}),
                   (400, {"error": {"message": "Request too large for model on tokens per minute (TPM): Limit 6000"}})):
    t = llm._humanize(httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req, json=body)), "http://127.0.0.1:4000/v1", "gpt-oss")
    ok("лимит" in t and "токенов в минуту" in t and "org_" not in t and "«Мозге»" in t, f"{code}: понятно, без сырого текста: {t}")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("No Listener: tabs:" in app and "Extension context" in app, "веб: сообщения расширений браузера — не сбой Dewiar")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
