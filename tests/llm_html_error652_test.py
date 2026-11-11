"""№652 (ночной разбор 11.11, ПК 0.86): «Модель (openai): сервер ответил ошибкой 500: <!DOCTYPE html> <html lang="en">
<head> <meta charset="utf-8"> <title>Error</title> </head> <body> <pre>Internal…» — страница ошибки сервера модели шла
человеку сырой разметкой. Теперь — её текст без тегов и что делать (сбой у сервера модели: повторить, перезапустить,
выбрать другую)."""
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


def err(code, text, ctype="text/html"):
    req = httpx.Request("POST", "http://127.0.0.1:1234/v1/chat/completions")
    resp = httpx.Response(code, text=text, request=req, headers={"content-type": ctype})
    return httpx.HTTPStatusError("x", request=req, response=resp)


page = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>Error</title>\n<style>body{color:red}</style>\n'
        '</head>\n<body>\n<pre>Internal Server Error: model crashed &amp; restarted</pre>\n</body>\n</html>\n')
t = str(llm._humanize(err(500, page), "http://127.0.0.1:1234/v1", "qwen"))
ok("<" not in t and "DOCTYPE" not in t, f"без разметки: {t}")
ok("Internal Server Error: model crashed & restarted" in t, "текст страницы ошибки — словами, &amp; раскрыт")
ok("сбой у сервера модели" in t and "другую" in t, "и что делать")
t4 = str(llm._humanize(err(418, "<html><body><h1>teapot</h1></body></html>"), "http://x/v1", "m"))
ok("teapot" in t4 and "<" not in t4 and "сбой у сервера" not in t4, f"не 5xx — без совета про сбой: {t4}")
tj = str(llm._humanize(err(500, '{"error": "boom"}', "application/json"), "http://x/v1", "m"))
ok(tj.startswith("сервер ответил ошибкой 500"), f"не HTML — как раньше: {tj}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
