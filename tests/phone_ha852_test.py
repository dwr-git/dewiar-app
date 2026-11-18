"""№852 (18.11): «Раздел „Подключение“: при переносе настроек на телефон мозг перенёсся, а настройки Home Assistant
нет». В QR «Перенести настройки» клали только токен Яндекса. Теперь — и Home Assistant (адрес и токен; localhost →
адрес компьютера в сети), телефон его подключает и спрашивает с адресом HA в списке серверов."""
import json, os, subprocess, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import net  # noqa: E402
import commands_tasks as CT  # noqa: E402
net.my_lan_ip = lambda: "192.168.8.21"
H = lambda d: types.SimpleNamespace(data=d, connected=lambda: bool(d.get("token")))   # noqa: E731
me = types.SimpleNamespace(home=H({}), ha=H({"url": "http://localhost:8123", "token": "t" * 30}))
out = CT.TasksCommands._phone_homes(me)
ok(out.get("ha", {}).get("url") == "http://192.168.8.21:8123" and out["ha"].get("token") == "t" * 30 and "home" not in out,
   f"в коде для телефона — Home Assistant, localhost заменён адресом компьютера: {out.get('ha', {}).get('url')}")
me.home = H({"token": "y" * 20})
ok(set(CT.TasksCommands._phone_homes(me)) == {"home", "ha"}, "Яндекс и Home Assistant — оба")
src = (ROOT / "core/commands_tasks.py").read_text(encoding="utf-8")
ok(src.count("self._phone_homes()") == 2, "и «Перенести настройки», и QR только умного дома берут оба дома")

js = r"""const src = require('fs').readFileSync(process.argv[1], 'utf8');
const cut = (a, b) => src.slice(src.indexOf(a), src.indexOf(b, src.indexOf(a)));
globalThis.D = {}; globalThis.S = {}; globalThis.homeInfo = 1; let saved = 0, shared = 0, yandex = "";
globalThis.saveS = () => saved++; globalThis.ownShare = async () => { shared++; }; globalThis.plog = () => {};
globalThis.homeSet = (t) => { yandex = t; }; globalThis.confirm = (q) => { globalThis.asked = q; return true; };
eval(cut('function haUrl(', '\n}\n') + '\n}\nglobalThis.haUrl = haUrl;');
eval((cut('function cfgHomesName(', 'function applyConfig(') + cut('function cfgAsk(', '\nfunction applyConfig(')).replace(/function (\w+)/g, 'globalThis.$1 = function'));
const m = { llm: { active: "p", profiles: { p: { base_url: "https://x.example/v1" } } }, ha: { url: "http://192.168.8.21:8123", token: "t".repeat(30) } };
cfgAsk(m); cfgHomes(m);
console.log(JSON.stringify({ ha: S.ha, saved, shared, asked, name: cfgHomesName({ ha: { token: "x" } }), both: cfgHomesName({ home: { token: 1 }, ha: { token: 1 } }) }));"""
r = subprocess.run(["node", "-e", js, str(ROOT / "android/assets/www/app.js")], capture_output=True, text=True)
d = json.loads(r.stdout or "{}")
if not d:
    print(r.stderr[-1500:])
ok((d.get("ha") or {}).get("url") == "http://192.168.8.21:8123" and (d.get("ha") or {}).get("token") == "t" * 30 and d.get("saved"),
   "телефон: Home Assistant из кода подключён (адрес и токен сохранены)")
ok(d.get("shared") == 1, "и разослан своим устройствам, как при ручном подключении")
ok("Home Assistant: 192.168.8.21:8123" in (d.get("asked") or ""), "в вопросе «Перенести настройки?» видно адрес Home Assistant")
ok(d.get("name") == "Home Assistant" and d.get("both") == "умный дом Яндекса и Home Assistant", "подпись в вопросе — какой дом подключится")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
