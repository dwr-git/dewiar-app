"""№289 (17.11) и «чем пользуются»: на телефоне за неделю 112 вопросов остались без ответа — «нет связи». Человек спросил,
связи нет — и вопрос пропадал: спрашивать заново самому. Теперь: «Нет связи — отправлю вопрос сам, как только связь
вернётся», и связь вернулась (событие online, возврат в приложение, проверка раз в 20 с) — вопрос уходит сам. Не уходит,
если за это время спросили другое, прошло больше 10 минут или в ходе уже что-то сделано (повтор был бы небезопасен)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
NET = {"up": False, "n": 0}
seen, errs = [], []


def llm(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    NET["n"] += 1
    if not NET["up"]:
        return route.abort("internetdisconnected")
    seen.append(json.loads(req.post_data or "{}").get("messages") or [])
    d = {"choices": [{"delta": {"content": "Завтра солнечно."}}]}
    route.fulfill(status=200, body=f"data: {json.dumps(d, ensure_ascii=False)}\n\ndata: [DONE]\n\n",
                  headers={"Access-Control-Allow-Origin": "*", "Content-Type": "text/event-stream"})


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route("http://127.0.0.1:9/**", llm)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("() => { Object.assign(S.llm, { kind: 'openai', base_url: 'http://127.0.0.1:9/v1', model: 'm', name: 'тест', cloud: false }); saveS(); }")
    pg.evaluate("async () => { await ask('Придумай короткое поздравление для мамы'); }")
    pg.wait_for_timeout(300)
    bot = pg.inner_text("#bot")
    ok("Вопрос отправится сам" in bot, f"нет связи — честно и с обещанием отправить самой: {bot[:160]!r}")
    ok(pg.evaluate("!!netRetry"), "вопрос запомнен")
    NET["up"] = True
    pg.evaluate("() => window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(2600)
    ok(seen and "поздравление" in json.dumps(seen[-1], ensure_ascii=False), "связь вернулась — тот же вопрос ушёл сам")
    ok("Завтра солнечно" in pg.inner_text("#bot") or "Завтра солнечно" in pg.inner_text("body"), "и ответ пришёл")
    ok(pg.evaluate("!netRetry"), "после отправки — ничего не ждёт")
    # спросили другое, пока связи не было, — старый вопрос не всплывает
    NET["up"] = False; n0 = len(seen)
    pg.evaluate("async () => { await ask('Сколько стоит билет?'); }"); pg.wait_for_timeout(200)
    pg.evaluate("() => { lastUserAct = Date.now() + 1000; }")
    NET["up"] = True
    pg.evaluate("() => window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(2600)
    ok(len(seen) == n0 and pg.evaluate("!netRetry"), "за это время спросили другое — старый вопрос не отправляется")
    # больше 10 минут — не к месту
    NET["up"] = False
    pg.evaluate("async () => { await ask('Напомни, что сегодня?'); }"); pg.wait_for_timeout(200)
    pg.evaluate("() => { netRetry.opts.netFirst = Date.now() - 11 * 60e3; }")
    NET["up"] = True; n0 = len(seen)
    pg.evaluate("() => window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(2600)
    ok(len(seen) == n0, "прошло больше 10 минут — не отправляет")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
