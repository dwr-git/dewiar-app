"""Отзывы на YouTube 19–22.10: «сервер добавлен, проверен, доступен, но ассистент не хочет» (в ответ было только «не могу
подключиться к http://127.0.0.1:11434/v1 — сервер запущен и адрес верный?»), «не видит LM Studio», «так и не подхватила
модель с OpenRouter». Теперь «Проверить» в «Мозге» объясняет, что именно не так и что нажать: работает другая программа —
«Найти»; Ollama стоит, но не запущена — открыть её; модель на другом компьютере — его адрес вместо 127.0.0.1 и доступ из
сети; у сервиса нет такой модели — «Список моделей»."""
import os, socket, sys
from pathlib import Path
import httpx
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import llm  # noqa: E402

opened, inst = set(), {"ollama": False, "lms": False}
llm._port_open = lambda host, port, timeout=0.35: int(port) in opened
llm.ollama_installed = lambda: inst["ollama"]
llm.lmstudio_installed = lambda: inst["lms"]

h = llm.connect_hint("http://127.0.0.1:11434/v1")
ok("не запущена программа с моделью" in h and "192.168.1.5:11434" in h and "сам этот компьютер" in h,
   f"на этом компьютере ничего нет — объясняем, что 127.0.0.1 — это он сам, и куда вписать адрес сервера: {h}")
opened.add(1234)
h = llm.connect_hint("http://127.0.0.1:11434/v1")
ok("LM Studio (порт 1234)" in h and "«Найти»" in h, f"Ollama нет, а LM Studio работает — «Найти»: {h}")
opened.clear(); inst["ollama"] = True
h = llm.connect_hint("http://127.0.0.1:11434/v1")
ok(h.startswith("Ollama установлена, но не запущена") and "«Проверить»" in h, f"Ollama стоит, но не запущена — открыть её: {h}")
inst["ollama"] = False; inst["lms"] = True
h = llm.connect_hint("http://localhost:1234/v1")
ok("Developer" in h and "«Проверить»" in h, f"LM Studio стоит, а сервер выключен — как включить: {h}")
h = llm.connect_hint("http://192.168.1.40:11434/v1")
ok("192.168.1.40" in h and "OLLAMA_HOST=0.0.0.0" in h and "Serve on Local Network" in h, f"модель на другом компьютере сети: {h}")
ok(llm.connect_hint("https://openrouter.ai/api/v1") == "", "облачный сервис — своя подсказка (интернет, прокси), без этой")

# настоящая ошибка соединения — подсказка в тексте ошибки
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
try:
    httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=2)
    err = None
except httpx.ConnectError as e:
    err = e
inst["lms"] = False
t = llm._humanize(err, f"http://127.0.0.1:{port}/v1")
ok(t.startswith(f"не могу подключиться к http://127.0.0.1:{port}/v1:") and "не запущена программа" in t, f"ошибка соединения — с объяснением: {t}")

# у сервиса нет такой модели
def http_err(code, body):
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, text=body, request=req))
t = llm._humanize(http_err(400, '{"error":{"message":"qwen-max-x is not a valid model ID","code":400}}'), "https://openrouter.ai/api/v1", "qwen-max-x")
ok("нет модели «qwen-max-x»" in t and "«Список моделей»" in t, f"OpenRouter: такой модели нет — выбрать из списка: {t}")
t = llm._humanize(http_err(404, '{"error":"model \\"llama3:70b\\" not found, try pulling it first"}'), "http://127.0.0.1:11434/v1", "llama3:70b")
ok("в Ollama нет модели «llama3:70b»" in t and "скачать" in t and "приложение Ollama" in t, f"Ollama: модель не скачана — как скачать: {t}")
# №211 (пакет 23.10): Ollama на /v1 отвечает 404 с ошибкой объектом
t = llm._humanize(http_err(404, '{"error":{"message":"model \\"llama3.2:latest\\" not found, try pulling it first","type":"api_error"}}'),
                  "http://127.0.0.1:11434/v1", "llama3.2:latest")
ok("в Ollama нет модели «llama3.2:latest»" in t, f"№211: модель не скачана — не «проверьте адрес»: {t}")
t = llm._humanize(http_err(401, '{"error":{"message":"Invalid API key"}}'), "https://api.openai.com/v1", "gpt")
ok("ключ" in t and "модели" not in t, f"неверный ключ — по-прежнему про ключ: {t}")

# пакет 23.10: модель для картинок выбрана как модель разговора
t = llm._humanize(http_err(400, '{"error":{"message":"\\"x/flux2-klein:4b\\" does not support chat","type":"invalid_request_error"}}'),
                  "http://127.0.0.1:11434/v1", "x/flux2-klein:4b")
ok("«x/flux2-klein:4b» не умеет разговаривать" in t and "«Список моделей»" in t, f"модель для картинок — понятно, что выбрать другую: {t}")
src = srctext.text(ROOT, "core/llm.py")
ok("flux" in src[src.index("def list_models"):src.index("def list_models") + 4000], "в списке моделей разговора нет моделей для картинок (flux, sdxl)")

if fails:
    raise SystemExit(1)
