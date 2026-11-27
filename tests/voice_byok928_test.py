"""№928 и идея №363 (20.11, телефон 0.9.73): своя модель по API (мозг), а слух — облако Dewiar своим ключом. В телефоне нет
своего синтеза речи — ответы шли только текстом («мой голос записывает, а твоего не слышно»); помогала лишь установка
«Синтеза речи Google». Теперь тот же ключ облака озвучивает ответы — как было с мозгом Dewiar."""
import os, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 820})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1300); pg.evaluate("closeSheets()")
    r = pg.evaluate("""() => { S.account = Object.assign({}, S.account, { token: "" }); S.accCloud = null;
        S.llm = Object.assign({}, DEF.llm, { kind: "openai", base_url: "https://glm.example/v1", api_key: "k", model: "glm", cloud: false });
        S.stt = Object.assign({}, S.stt, { engine: "server", url: "https://dewiar.pro/dwrapp/cloud.php?p=/v1", key: "dw-test" });
        const a = cloudVoice();
        S.stt = Object.assign({}, S.stt, { engine: "system", url: "", key: "" });
        const b = cloudVoice();
        S.stt = Object.assign({}, S.stt, { engine: "server", url: "https://my.server/v1", key: "x" });
        const c = cloudVoice();
        return { a, b, c }; }""")
    ok(r["a"] and r["a"]["url"] == "https://dewiar.pro/dwrapp/cloud.php?p=" and r["a"]["key"] == "dw-test",
       f"своя модель + слух облаком Dewiar — голос облака тем же ключом: {r['a']}")
    ok(r["b"] is None and r["c"] is None, "без ключа облака (свой сервер слуха, слух устройства) — как раньше")
    src = (ROOT / "android/www-src/app/06-ears-voice.js").read_text(encoding="utf-8")
    ok('(S.tts.engine === "system" && !ttsOk())) ? cloudVoice()' in src, "голос облака — только когда своего голоса в телефоне нет или выбран «Голос Dewiar»")
    ok(not errs, f"без ошибок страницы {errs[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
