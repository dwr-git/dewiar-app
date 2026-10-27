"""YouTube 27.10: «На телефоне случайно нажал „Забыть ключ“ — не получается войти». Теперь: вопрос перед тем, как забыть,
называет ключ (…abcd) и говорит, как вернуть; забытый ключ остаётся в «Мозг» → «Прежние мозги» (30 дней) и возвращается
одной кнопкой «Вернуть»; убрать насовсем — корзиной там же."""
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
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    r = pg.evaluate("""async () => {
      S.llm = Object.assign({}, DEF.llm, { kind: 'openai', cloud: true, name: 'Dewiar Облако', base_url: 'https://dewiar.pro/dwrapp/cloud.php?p=', api_key: 'dw-test-ab12', model: 'chat' });
      saveS(); llmSeen = JSON.parse(JSON.stringify(S.llm));
      await forgetKey(); saveS(); llmRemember();
      const back = llmBack(); return { now: S.llm.base_url || '', back: back.map(x => [brainNameOf(x), x.api_key]) }; }""")
    ok(r["now"] == "" and any(k == "dw-test-ab12" for _, k in r["back"]), f"забыли — ключ остался в «Прежних мозгах»: {r}")
    ok(any("забытый ключ …ab12" in n for n, _ in r["back"]), f"подписан понятно: {r['back']}")
    r = pg.evaluate("""() => { const x = (S.llmSaved || []).find(y => y.forgot); x.forgot = Date.now() - 31 * 864e5; saveS(); return llmBack().some(y => y.forgot); }""")
    ok(r is False, "через 30 дней забытый ключ из списка уходит сам")
    app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
    ok("ключ можно будет вернуть одной кнопкой: «Мозг» → «Прежние мозги» → «Вернуть»" in app and "Забыть ключ Dewiar …${k4}?" in app,
       "вопрос называет ключ и говорит, как вернуть")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
