"""№891 (19.11): «на телефоне раздела „Платежи“ нет, и Лира на телефоне о них не знает». 1.0.38: счета и оплаты приходят
синхронизацией (bill, pay — только читаются, ведёт компьютер), во вкладке «Деньги» — блок «Платежи» (нового раздела нет): срок,
просрочено, скоро, оплачено; спросили про оплаты — справка Лире. Ни одной правки и удаления отсюда (syncApply -> false)."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sync = (ROOT / "android/www-src/app/16-sync.js").read_text(encoding="utf-8")
ok('"bill", "pay"];' in sync.split("\n")[11] and 'if (it.kind === "bill" || it.kind === "pay") { payApply(it.kind, it.id, d, del); return false; }' in sync,
   "bill и pay — в видах синхронизации телефона, приходят только сюда (return false — назад не уходят)")
ok("payContext(text)" in (ROOT / "android/www-src/app/05-talk.js").read_text(encoding="utf-8"), "справка к вопросу — с платежами")
src = (ROOT / "android/www-src/app/14-sheets.js").read_text(encoding="utf-8")
a, b = src.index("function payStore()"), src.index("function renderDay()")
JS = r"""const P = {}; globalThis.prefGet = (k) => P[k] || ""; globalThis.prefSet = (k, v) => { P[k] = v; };
globalThis.pad = (n) => String(n).padStart(2, "0"); globalThis.esc = (s) => String(s);
globalThis.MON = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
eval(require("fs").readFileSync(process.argv[1], "utf8").replace(/^function (\w+)/gm, "globalThis.$1 = function $1").replace(/^const (PAY_ASK) =/m, "globalThis.$1 ="));
const now = new Date(2026, 10, 19, 10, 0);
payApply("bill", "gas", { name: "Газ", icon: "🔥", kind: "meter", day: 21, amount: 30 });
payApply("bill", "net", { name: "Интернет", icon: "🌐", kind: "fixed", day: 10 });
payApply("bill", "tv", { name: "ТВ", kind: "fixed", day: 15 });
payApply("bill", "old", { name: "Старый", day: 5, archived: true });
payApply("bill", "ins", { name: "Страховка", kind: "yearly", day: 1, month: 12 });
payApply("pay", "p1", { bill: "net", period: "2026-11", amount: 25, date: "2026-11-08", status: "paid" });
payApply("pay", "p2", { bill: "gas", period: "2026-10", amount: 28, date: "2026-10-20" });
const rows = payRows(now).map(r => [r.b.name, r.status, payDueText(r)]);
payApply("bill", "tv", null, true);
const after = Object.keys(payStore().bills);
console.log(JSON.stringify({ rows, after, html: (() => { const r0 = payRows; globalThis.payRows = () => r0(now); const h = payHtml(); globalThis.payRows = r0; return h; })(),
  ctx: (() => { const r0 = payRows; globalThis.payRows = () => r0(now); const c = [payContext("Что мне надо оплатить в этом месяце?"), payContext("Какая погода?")]; globalThis.payRows = r0; return c; })() }));"""
tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "pays891.js"
tmp.write_text(src[a:b], encoding="utf-8")
r = subprocess.run(["node", "-e", JS, str(tmp)], capture_output=True, text=True)
out = json.loads(r.stdout or "{}")
if not out:
    print(r.stderr[-1500:])
rows = out.get("rows", [])
ok([x[0] for x in rows] == ["ТВ", "Газ", "Страховка", "Интернет"], f"порядок: просрочено, скоро, ждёт, оплачено; в архиве — нет: {[x[0] for x in rows]}")
ok(rows and rows[0][1:] == ["overdue", "просрочено — было 15 ноября"], f"ТВ: срок 15-го прошёл: {rows[:1]}")
ok(len(rows) > 1 and rows[1][1:] == ["soon", "до 21 ноября"], f"газ: в октябре платили, ноябрь — скоро, до 21-го: {rows[1:2]}")
ok(len(rows) > 3 and rows[3][1] == "paid" and rows[3][2].startswith("оплачено 25") and "08.11" in rows[3][2], f"интернет — оплачено 25 · 08.11: {rows[3:]}")
ok(len(rows) > 2 and rows[2][1:] == ["wait", "до 1 декабря"], f"страховка раз в год — до 1 декабря: {rows[2:3]}")
ok(out.get("after") == ["gas", "net", "old", "ins"], "удалённый на компьютере счёт уходит и отсюда")
h = out.get("html", "")
ok("Платежи · не оплачено 2" in h and "студия → «Платежи»" in h and 'aria-label="Оплачено"' in h, "во вкладке «Деньги» — блок «Платежи» с подсказкой, где их вести")
c = out.get("ctx", ["", ""])
ok(c[0].startswith("Платежи человека") and "Газ — до 21 ноября" in c[0] and "Интернет — оплачено" in c[0] and c[1] == "", f"спросили про оплаты — справка Лире; про погоду — нет: {c[0][:120]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
