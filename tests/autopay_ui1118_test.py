"""1.0.32 автопополнение в программах (студия и телефон, веб-версия — тот же app.js): блок виден только когда на сайте есть
способ с сохранением карты (autopay.available); правила — словами рядом с переключателем; без карты — сайт отвечает
need_card и адресом оплаты, программа его открывает; «Забыть карту». ЮMoney — только в русской программе (владелец 18.11:
по-русски — ЮMoney, по-английски — израильская система). Ядро: команда cloud_autopay → POST /autopay."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


for name, path, html in (("студия", "ui/studio/dewiar.js", "ui/settings.html"), ("телефон", "android/www-src/app/17-cloud.js", "android/www-src/app/15-leisure-settings.js")):
    src = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(r"^const payLangOk = .*?;$", src, re.M)
    js = (m.group(0) if m else "") + """
let L = "ru"; globalThis.window = globalThis; globalThis.dwLang = () => L;
const a = [payLangOk({ lang: "ru" }), payLangOk({ lang: "en" }), payLangOk({})];
L = "en"; const b = [payLangOk({ lang: "ru" }), payLangOk({ lang: "en" }), payLangOk({})];
console.log(JSON.stringify([a, b]));"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    try:
        a, b = json.loads(r.stdout)
    except ValueError:
        ok(False, f"{name}: payLangOk не запустилась: {r.stderr[:200]}"); continue
    ok(a == [True, False, True] and b == [False, True, True], f"{name}: по-русски — ЮMoney, по-английски — карта, общие — везде: {a} {b}")
    ok("payLangOk({ lang: \"ru\" })" in src and "autoFill(c.autopay)" in src, f"{name}: ЮMoney по языку, автопополнение из /balance")
    ok("a && a.available" in src and "need_card" in src and "forget: true" in src and "не больше" in src, f"{name}: виден только при способе с картой, согласие словами, «Забыть карту»")
    h = (ROOT / html).read_text(encoding="utf-8")
    ok("Автопополнение" in h and ("cc-auto-on" in h or "cl-auto-on" in h) and "Забыть карту" in h, f"{name}: разметка блока «Автопополнение»")
cb = (ROOT / "core/commands_brain.py").read_text(encoding="utf-8")
ok('"cloud_autopay"' in cb and "autopay_set(a)" in cb, "ядро: команда cloud_autopay")
import cloud as CL  # noqa: E402
calls = []
CL.fetch = lambda url, key, path, timeout=10, body=None: calls.append((path, body)) or {"ok": True}
cls = next(v for v in vars(CL).values() if isinstance(v, type) and hasattr(v, "autopay_set"))
c = cls.__new__(cls)
c.s = type("S", (), {"get": lambda self, *k: {("cloud", "key"): "dw-test", ("cloud", "url"): "https://dewiar.pro/dwrapp/cloud.php?p="}.get(k)})()
c.autopay_set({"on": True, "below": "1", "amount": "5", "cap": "", "x": 1})
ok(calls == [("/autopay", {"on": True, "below": "1", "amount": "5"})], f"ядро: POST /autopay без пустых и лишних полей: {calls}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
