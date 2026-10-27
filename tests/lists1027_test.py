"""№275 (пакет 27.10): «в списке программ все пункты пронумерованы „1“» — модель разделяет пункты пустой строкой, а
студия (folder.js md) и телефон (app.js mdAnswer) открывали на каждый пункт новый <ol>. Теперь — один список, а
начатый не с единицы — с нужного номера (<ol start>)."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


if not shutil.which("node"):
    print("✅ пропуск: нет node"); sys.exit(0)
studio = (ROOT / "ui/studio/folder.js").read_text(encoding="utf-8")
studio = studio[studio.index("function mdInline"):studio.index("const FICON")]
phone = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
i = phone.index("function mdAnswer(t)"); phone = phone[i:phone.index("\nfunction copyText", i)]
JS = """const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;'), escH = esc;
%s
%s
const cases = %s;
console.log(JSON.stringify(cases.map(c => [md(c), mdAnswer(c)])));""" % (studio, phone, json.dumps([
    "1. первое\n\n2. второе\n\n3. третье\n\nтекст", "3. три\n4. четыре", "- а\n\n- б\n\nабзац"]))
out = json.loads(subprocess.run(["node", "-e", JS], capture_output=True, text=True, check=True).stdout)
for who, k in (("студия", 0), ("телефон", 1)):
    a, b, c = out[0][k], out[1][k], out[2][k]
    ok(a.count("<ol") == 1 and a.count("<li>") == 3 and "<p>текст</p>" in a, f"{who}: пункты через пустую строку — один список: {a[:90]}")
    ok('<ol start="3">' in b, f"{who}: список с третьего — с 3: {b[:60]}")
    ok(c.count("<ul") == 1 and c.count("<li>") == 2, f"{who}: маркированный через пустую строку — один: {c[:60]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
