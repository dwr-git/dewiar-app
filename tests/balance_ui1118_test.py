"""1.0.31 «Баланс» в программах: студия компьютера и телефон (веб-версия — тот же app.js) показывают, на сколько дней
хватит при нынешних тратах, подарок месяца (сколько осталось, до какого числа, не копится), «Мои лимиты» (день и месяц —
сохраняются на сайте для всех устройств: cloud_limits / POST /limits) и историю пополнений (/topup → history).
Ядро: cloud.limits_set, команда cloud_limits; 429 с user_limit/day_limit не повторяется по 15–60 с (до завтра)."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def fns(src, names):
    out = []
    for n in names:
        m = re.search(r"^(?:const %s = .*?;|function %s\(.*?\n\})$" % (n, n), src, re.S | re.M)
        out.append(m.group(0) if m else "")
    return "\n".join(out)


C = {"days_left": 23, "gift": {"amount": 0.25, "left": 0.1, "until": "2026-12-01"}}
for name, path in (("студия", "ui/studio/dewiar.js"), ("телефон", "android/www-src/app/17-cloud.js")):
    src = (ROOT / path).read_text(encoding="utf-8")
    code = fns(src, ["daysWord", "daysLine", "monthGiftLine"])
    js = code + f"\nconst c = {json.dumps(C)};\nconsole.log(JSON.stringify([daysLine(c), monthGiftLine(c), daysLine({{days_left: 400}}), daysLine({{}}), monthGiftLine({{gift: {{amount: 0.25, left: null}}}})]))"
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    try:
        d, g, far, none, nog = json.loads(r.stdout)
    except ValueError:
        ok(False, f"{name}: функции не запустились: {r.stderr[:300]}")
        continue
    ok(d == " · при нынешних тратах — примерно на 23 дня", f"{name}: на сколько дней хватит: {d!r}")
    ok("Подарок месяца: осталось 0,1 из 0,25 тал. до 1 декабря" in g and "не копится" in g, f"{name}: подарок месяца: {g!r}")
    ok("больше чем на год" in far and none == "" and nog == "", f"{name}: год и больше — словами; нет данных — тихо")
    ok("limFill(c.limits)" in src and ("cloud_limits" in src or 'cloudPost("/limits"' in src), f"{name}: «Мои лимиты» заполняются и сохраняются")
    ok(re.search(r"(cpHist|clHist)\(r\.history\)", src), f"{name}: история пополнений из /topup")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('id="cc-lim-d"' in html and 'id="cc-lim-m"' in html and "Мои лимиты" in html, "студия: поля «Мои лимиты» в карточке ИИ-баланса")
ph = (ROOT / "android/www-src/app/15-leisure-settings.js").read_text(encoding="utf-8")
ok('id="cl-lim-d"' in ph and "Мои лимиты" in ph, "телефон: «Мои лимиты» в карточке «Баланс»")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("function clHist" in app and "function giftLine" in app, "телефон: собранный app.js содержит новое")

import cloud as CL  # noqa: E402
calls = []
CL.fetch = lambda url, key, path, timeout=10, body=None: calls.append((path, body)) or {"ok": True, **(body or {})}
cls = next(v for v in vars(CL).values() if isinstance(v, type) and hasattr(v, "limits_set"))
c = cls.__new__(cls)
c.s = type("S", (), {"get": lambda self, *k: {("cloud", "key"): "dw-test", ("cloud", "url"): "https://dewiar.pro/dwrapp/cloud.php?p="}.get(k)})()
r = c.limits_set("0,5", 10)
ok(calls == [("/limits", {"day": "0,5", "month": 10})] and r.get("ok"), f"ядро: limits_set → POST /limits: {calls}")
cb = (ROOT / "core/commands_brain.py").read_text(encoding="utf-8")
ok('"cloud_limits"' in cb and "limits_set(" in cb, "ядро: команда cloud_limits")
llm_src = (ROOT / "core/llm.py").read_text(encoding="utf-8")
ok("user_limit|day_limit" in llm_src, "429 своего лимита — без повторов по 15–60 с")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
