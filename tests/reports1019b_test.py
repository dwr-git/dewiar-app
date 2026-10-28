"""Отчёты 19.10, вечер. №110 (телефон): прислал скриншот через скрепку и спросил, потом «посмотри внимательно, я
прикрепил картинку» — модель отвечала, что файла нет: в истории разговора остаётся только текст. Теперь, если человек
говорит о присланном фото (в течение 20 минут), телефон прикладывает его снова; о постороннем — не прикладывает,
после «Начать заново» — тоже."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
r = subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], capture_output=True, text=True)
ok(r.returncode == 0, f"сборка интерфейса телефона: {r.stderr[-200:]}")
PIX = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
from playwright.sync_api import sync_playwright  # noqa: E402
seen = []


def llm(route):
    req = route.request
    if req.method == "GET":
        return route.fulfill(status=200, body=json.dumps({"data": [{"id": "m"}]}), headers={"Content-Type": "application/json"})
    body = json.loads(req.post_data or "{}")
    last = (body.get("messages") or [{}])[-1]
    seen.append(sum(1 for x in last.get("content") if isinstance(x, dict) and x.get("type") == "image_url") if isinstance(last.get("content"), list) else 0)
    sse = 'data: {"choices":[{"delta":{"content":"Вижу дизайн."}}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, body=sse, headers={"Content-Type": "text/event-stream"})


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 852}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("http://llm.test/**", llm)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("""() => { Object.assign(S.llm, { kind: "openai", base_url: "http://llm.test/v1", model: "m", api_key: "k", name: "тест", vision: true }); S.textMode = true; saveS();
        document.querySelectorAll('.sheet.on').forEach(s => s.classList.remove('on')); }""")
    pg.evaluate(f"ask('Какой дизайн тебе больше нравится и почему?', {{ attach: [{{ kind: 'image', name: 'скрин.png', url: '{PIX}' }}] }})")
    pg.wait_for_function("!busy", timeout=15000); pg.wait_for_timeout(200)
    pg.evaluate("ask('Слушай, я прикрепил тебе файл, посмотри внимательно — там скриншот')"); pg.wait_for_function("!busy", timeout=15000)
    # 0.64: погода на телефоне отвечается без модели — посторонний вопрос другой
    pg.evaluate("ask('расскажи анекдот про кота')"); pg.wait_for_function("!busy", timeout=15000)
    pg.evaluate("convReset(); ask('посмотри ещё раз на картинку')"); pg.wait_for_function("!busy", timeout=15000)
    calls = [n for n in seen]
    ok(len(calls) >= 4 and calls[0] == 1, f"первый вопрос — с фото: {calls}")
    ok(len(calls) >= 2 and calls[1] == 1, "«посмотри, я прикрепил файл» — фото приложено снова")
    ok(len(calls) >= 3 and calls[2] == 0, "посторонний вопрос — без фото")
    ok(len(calls) >= 4 and calls[-1] == 0, "после «Начать заново» старое фото не прикладывается")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
