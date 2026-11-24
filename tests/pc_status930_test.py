"""№930 (20.11, телефон 0.9.73): «Всё» → «Компьютер» — зелёное «на связи», хотя компьютер выключен уже три часа; перезапуск
не помогает. Зелёным считалось «связан за две недели». Теперь: отвечал последние 3 минуты — зелёное «на связи»; связан,
но молчит — «сейчас не на связи», без зелёного; не связан — «ещё не связан» и «Скачать»."""
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

    def show(seen_ago):
        return pg.evaluate("""a => { syncStatus.devices = a === null ? [] : [{ pc: true, name: "NB", seen: Date.now() / 1000 - a },
              { pc: true, name: "Облако Dewiar", seen: Date.now() / 1000 }];
            openPcInfo(); const c = document.querySelector('#pci-body .pci-st');
            return { ok: c.classList.contains('ok'), t: c.innerText, dl: !!document.querySelector('#pci-dl') }; }""", seen_ago)
    r = show(3 * 3600)
    ok(not r["ok"] and "не на связи" in r["t"] and "NB" in r["t"] and not r["dl"], f"выключен 3 часа — без зелёного, «не на связи»: {r}")
    r = show(30)
    ok(r["ok"] and "на связи" in r["t"] and "не на связи" not in r["t"], f"отвечал полминуты назад — зелёное «на связи»: {r}")
    r = show(None)
    ok(not r["ok"] and r["dl"], f"не связан — «Скачать»: {r}")
    pg.evaluate("dwSetLang('en')"); r = show(3 * 3600)
    ok("offline" in r["t"], f"по-английски: {r['t'][:60]}")
    ok(not errs, f"без ошибок страницы {errs[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
