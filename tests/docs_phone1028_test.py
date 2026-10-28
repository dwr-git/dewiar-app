"""«Документы» на телефоне (0.62; план «Идей Лиры»: «спросить телефон о своих папках с компьютера: „что в договоре про
сроки?“»). Телефон с синхронизацией и компьютером: у модели — pc_documents; вопрос уходит задачей именно этому компьютеру
(не облаку — облако папок не видит) с просьбой искать в документах и назвать файл; честно — «ответа ещё нет»."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); w = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(800)
    ok(not pg.evaluate("JSON.stringify(toolSpecs()).includes('pc_documents')"), "без компьютера — инструмента нет")
    pg.evaluate("""() => { S.sync = Object.assign({}, S.sync, { on: true }); S.llm = Object.assign({}, S.llm, { cloud: true, api_key: 'dw-test', base_url: 'http://127.0.0.1:9/cloud.php?p=' }); saveS();
        syncStatus.devices = [{ pc: true, name: 'Облако Dewiar', seen: Date.now() / 1000 }, { pc: true, name: 'Рабочий ноутбук', seen: Date.now() / 1000 - 30 }, { pc: true, name: 'Старый ПК', seen: Date.now() / 1000 - 9 * 86400 }]; }""")
    ok(pg.evaluate("JSON.stringify(toolSpecs()).includes('pc_documents')"), "есть синхронизация и компьютер — у модели pc_documents")
    r = pg.evaluate("async () => await runTool('pc_documents', { question: 'что в договоре с Ромашкой про сроки оплаты?' })")
    q = pg.evaluate("qGet('taskq')")
    ok("Рабочий ноутбук" in r and "ЕЩЁ НЕТ" in r, f"ответ модели — кого спросили и что ответа ещё нет: {r[:90]}")
    ok(q and q[-1]["to"] == "Рабочий ноутбук" and not q[-1].get("cloud") and "search_documents" in q[-1]["goal"] and "Ромашкой" in q[-1]["goal"],
       f"задача — именно последнему компьютеру, не облаку; искать в документах: {q[-1:]}")
    b.close()
ok(not errs, f"без ошибок: {errs[:2]}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
