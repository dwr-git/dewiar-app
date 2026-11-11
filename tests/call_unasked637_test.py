"""№637 (10.11, телефон): «прошу Лиру включить будильник или поставить музыку, а она постоянно просит доступ к контактам,
чтобы позвонить». Маленькая модель (qwen3:8b у человека) звала call на «поставь будильник», «включи радио Deep House»,
«какая погода» — телефон спрашивал доступ к контактам, а на «какое завтра число» однажды набрал номер.
Теперь call без просьбы позвонить — ошибка модели («звонок не сделан, выбери нужную функцию»), контакты не спрашиваются,
номер не набирается; без имени — тоже без контактов. Просьба позвонить и ответ на «кому позвонить?» — как раньше."""
import os, shutil, subprocess, sys, tempfile
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
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        res = pg.evaluate("""async () => {
            window._perm = 0; window._dial = []; window._q = [];
            D.has = () => true;
            needPerm = async () => { window._perm++; return false; };
            D.contact = (q) => { window._q.push(q); return JSON.stringify({ need: true }); };
            D.call = (n) => { window._dial.push(n); return true; };
            clLoad = () => ({ people: [] });
            const out = {};
            for (const [k, said, who] of [["alarm", "ты можешь поставить будильник завтра на 6:20 утра", "мама"],
                                          ["radio", "Лера я дал тебе доступ к контактам Включи пожалуйста радио Deep House", "Deep House"],
                                          ["date", "Какое завтра число", "+375290000001"],
                                          ["empty", "Какая погода сейчас там где я живу", ""]]) {
              turnAsk = said; callAskAt = 0; relAsk = null;
              out[k] = String(await runTool("call", { who }));
            }
            out.perm = window._perm; out.dial = window._dial.slice(); out.q = window._q.slice();
            turnAsk = "позвони Людмиле"; callAskAt = 0;
            out.asked = String(await runTool("call", { who: "Людмиле" })); out.perm2 = window._perm; out.q2 = window._q.slice();
            turnAsk = "позвони"; callAskAt = 0;
            out.noname = String(await runTool("call", { who: "" }));
            // Лира переспросила «кому?» — человек отвечает только именем
            D.contact = (q) => JSON.stringify({ name: "Исаева Людмила", number: "+375290000002" });
            callAskAt = Date.now(); turnAsk = "Людмиле Исаевой";
            out.reply = String(await runTool("call", { who: "Людмиле Исаевой" })); out.dial2 = window._dial.slice();
            return out; }""")
        for k in ("alarm", "radio", "date", "empty"):
            ok(res[k].startswith("Ошибка") and "контакт" not in res[k].split("—")[0], f"«{k}»: call без просьбы позвонить — ошибка модели: {res[k][:90]}")
        ok(res["perm"] == 0 and res["q"] == [], f"доступ к контактам не спрашивали, контакты не искали: perm={res['perm']} q={res['q']}")
        ok(res["dial"] == [], f"номер без просьбы не набран: {res['dial']}")
        ok("будильник" in res["alarm"] and "set_reminder" in res["alarm"], "подсказка модели — какая функция нужна")
        ok(res["perm2"] == 1 and res["q2"] == ["Людмиле"] and "контакт" in res["asked"], f"«позвони Людмиле» — как раньше, просим контакты: {res['asked']}")
        ok(res["noname"].startswith("Ошибка") and "кому" in res["noname"], f"«позвони» без имени — спросить кому, не контакты: {res['noname']}")
        ok(res["dial2"] == ["+375290000002"], f"ответ именем на «кому позвонить?» — звоним: {res['dial2']} {res['reply'][:60]}")
        ok(not errs, f"без ошибок: {errs[:2]}")
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
