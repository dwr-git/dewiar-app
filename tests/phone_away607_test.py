"""№607 (07.11): «пришёл к другу, телефон подключился к его Wi-Fi, интернет есть, а Лира не видит; через мобильный интернет
всё заработало. Может, я что-то не настроил?» Это ожидаемо: компьютер (или модель на нём) — по адресу домашней сети, из чужой
сети Wi-Fi его не видно. Вместо «связь оборвалась» / «домашний сервер не отвечает» — понятное объяснение: где телефон сейчас,
что так и задумано и что делать вне дома; в «Устройствах» у «Дома по Wi-Fi» — то же."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


js = r"""const src = require('fs').readFileSync(process.argv[1], 'utf8');
const a = src.indexOf('const HOME_URL ='), b = src.indexOf('/* ---------- настройки: одна строка JSON');
let IPS = '[]'; globalThis.D = { lanIps: () => IPS };
eval(src.slice(a, b).replace('function netErr', 'globalThis.netErr = function').replace('function lanAway', 'globalThis.lanAway = function'));
const out = {};
IPS = JSON.stringify([{ ip: '10.0.0.57', wifi: true }]);
out.friend = netErr('failed to connect to /192.168.0.177 (port 1234) after 15000ms', 'http://192.168.0.177:1234/v1/chat/completions');
out.away = lanAway('http://192.168.0.177:8766/');
IPS = JSON.stringify([{ ip: '10.84.12.3', wifi: false }]);
out.mobile = netErr('timeout', 'http://192.168.0.177:1234/v1/chat/completions');
IPS = JSON.stringify([{ ip: '192.168.0.44', wifi: true }]);
out.same = netErr('timeout', 'http://192.168.0.177:1234/v1/chat/completions');
out.cloud = netErr('timeout', 'https://dewiar.pro/dwrapp/cloud.php?p=/chat/completions');
console.log(JSON.stringify(out));"""
r = json.loads(subprocess.run(["node", "-e", js, str(ROOT / "android/assets/www/app.js")], capture_output=True, text=True).stdout or "{}")
ok("в другой сети Wi-Fi" in r.get("friend", "") and "Так и задумано" in r["friend"] and "Dewiar Облако" in r["friend"], f"у друга в Wi-Fi — понятно, почему и что делать: {r.get('friend')}")
ok(r.get("away") == "wifi", "другая сеть Wi-Fi узнаётся по адресам телефона")
ok("на мобильном интернете" in r.get("mobile", ""), f"на мобильном — так и сказано: {r.get('mobile')}")
ok("возможно, вы не дома" in r.get("same", ""), f"та же сеть, но не отвечает — как раньше: {r.get('same')}")
ok("сервер Dewiar долго не отвечает" in r.get("cloud", ""), "облако — без «домашней сети»")
dv = (ROOT / "android/assets/www/devices.js").read_text(encoding="utf-8")
ok("чужой Wi-Fi его не покажет" in dv and "!cl && hs && hs.ok === false" in dv, "«Устройства» → «Дома по Wi-Fi»: вне дома — объяснение и путь «Через dewiar.pro»")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok('lanAway(c.base) === "wifi"' in app, "синхронизация по Wi-Fi в чужой сети — тоже словами")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
