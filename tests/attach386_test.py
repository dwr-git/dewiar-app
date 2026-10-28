"""№386 (28.10, веб-версия): «Добавил файл во вложение, а он не смог его разобрать» — прислал JSON-файл, потом спросил
«а почему ты не можешь прочитать вложение?», и модель ответила «файл пришёл как ссылка, я вижу только текст». Текст файла
уходил модели только в том ходе, где его приложили; в истории его нет. Теперь, если в ближайшие 20 минут говорят о файле
(«вложение», «файл», «прочитай», «разбери»…), его текст прикладывается снова."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
seen, errs = [], []


def llm_route(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    seen.append(json.loads(req.post_data or "{}").get("messages") or [])
    d = {"choices": [{"delta": {"content": "Разобрала: в статье три раздела."}}]}
    route.fulfill(status=200, body=f"data: {json.dumps(d, ensure_ascii=False)}\n\ndata: [DONE]\n\n",
                  headers={"Access-Control-Allow-Origin": "*", "Content-Type": "text/event-stream"})


def last_user(msgs):
    u = [m for m in msgs if m.get("role") == "user"][-1]["content"]
    return u if isinstance(u, str) else " ".join(x.get("text", "") for x in u if isinstance(x, dict))


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route("http://127.0.0.1:9/**", llm_route)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { Object.assign(S.llm, { kind: 'openai', base_url: 'http://127.0.0.1:9/v1', model: 'm', name: 'тест', cloud: false }); saveS(); }")
    pg.evaluate("""async () => { const f = new File([JSON.stringify({ title: 'Статья КМС', sections: ['Введение', 'Метод', 'Итоги'] })], 'kms_1310_0.json', { type: 'application/json' });
      await addAttach(f); const att = attached; attached = []; await ask('Сделай чанки по этой статье', { attach: att }); }""")
    pg.wait_for_timeout(600)
    ok("Статья КМС" in last_user(seen[-1]) and "kms_1310_0.json" in last_user(seen[-1]), "файл JSON — в сообщении модели")
    pg.evaluate("async () => { await ask('А почему ты не можешь прочитать вложение?'); }"); pg.wait_for_timeout(600)
    u = last_user(seen[-1])
    ok("Статья КМС" in u and "прикладываю снова" in u, "спросили о вложении — текст файла приложен снова")
    pg.evaluate("async () => { await ask('Какая погода в Минске?'); }"); pg.wait_for_timeout(600)
    ok(len(seen) < 3 or "Статья КМС" not in last_user(seen[-1]), "о другом — файл не тянется")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
