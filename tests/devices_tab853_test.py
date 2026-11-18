"""№853 (18.11): «Нет такой кнопки, не получается добавить комп к телефону». Телефон был связан с компьютером и через
dewiar.pro, и дома по Wi-Fi — в «Устройствах» открывалась вкладка «Дома по Wi-Fi», а «Подключить ещё устройство» и
«Ввести код» живут во вкладке «Через dewiar.pro». Теперь при входе в Dewiar сначала открыта она; во вкладке Wi-Fi —
подсказка, где кнопки; руководство и экзамен телефона говорят то же."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


js = r"""const src = require('fs').readFileSync(process.argv[1], 'utf8');
const a = src.indexOf('let devWay = ""'), b = src.indexOf('function devBind()');
globalThis.D = {}; globalThis.S = { sync: { home: { t: "t", k: "k", n: "DESKTOP" } } }; globalThis.syncStatus = { chans: [] };
globalThis.esc = (x) => String(x); globalThis.DEV_IC = { cloud: "", home: "" }; globalThis.window = {};
globalThis.devOwnBrain = () => false; globalThis.devBrainsGot = [];
globalThis.homeOn = () => true; let CRED = { token: "x", via: "ключ" };
globalThis.syncCred = () => CRED;
eval(src.slice(a, b).replace(/^let devWay = ""/, 'globalThis.devWay = ""'));
const out = {};
out.both = devWays({ via: "ключ" });
out.homeTab = (devWay = "home", devWays({ via: "ключ" }));
devWay = ""; CRED = null;
out.homeOnly = devWays({ home: true, via: "Wi-Fi" });
console.log(JSON.stringify(out));"""
r = subprocess.run(["node", "-e", js, str(ROOT / "android/assets/www/devices.js")], capture_output=True, text=True)
out = json.loads(r.stdout or "{}")
if not out:
    print(r.stderr[-800:])
both = out.get("both", "")
ok('data-way="cloud" class="on"' in both and "Подключить ещё устройство" in both and "Ввести код" in both,
   "связан и через dewiar.pro, и по Wi-Fi — сначала вкладка dewiar.pro с «Подключить ещё устройство» и «Ввести код»")
ok("во вкладке «Через dewiar.pro»" in out.get("homeTab", ""), "во вкладке Wi-Fi — подсказка, где кнопки")
ok('data-way="home" class="on"' in out.get("homeOnly", ""), "только Wi-Fi, без входа в Dewiar — как раньше, вкладка Wi-Fi")
guide = (ROOT / "data/guide.json").read_text(encoding="utf-8")
ok("во вкладке «Через dewiar.pro» (на телефоне, связанном и по Wi-Fi" in guide, "руководство: где кнопки на телефоне со связью по Wi-Fi")
exam = (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8")
ok('id: "help_pair_tab_853"' in exam, "экзамен телефона: help_pair_tab_853")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
