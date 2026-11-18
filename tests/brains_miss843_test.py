"""№843 (17.11, телефон 0.9.51): «При попытке подключить мозги из компьютера пишет, что других устройств не обнаружено,
хотя на скрине видно, что комп подключён». Синхронизация и передача мозгов — разные каналы: второй открывается, когда
компьютер сам представится серверу. Теперь: список своих устройств перед ответом «нет» спрашивается заново, а если
компьютер виден в «Все устройства» — ответ называет его и говорит, что сделать (запустить Dewiar, обновить)."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


js = r"""const src = require('fs').readFileSync(process.argv[1], 'utf8');
const cut = (a, b) => src.slice(src.indexOf(a), src.indexOf(b, src.indexOf(a)));
globalThis.DEV_APP = { pc: "Компьютер", phone: "Телефон", web: "В браузере", cloud: "Облако Dewiar" };
globalThis.DEVS = null; globalThis.syncStatus = { all: [] };
let hellos = 0, devs = [];
globalThis.syncCred = () => ({ token: "x" }); globalThis.DC = () => ({ b64d: (x) => x, encryptFor: () => "env" });
globalThis.clKeys = () => ({ dev: "me", pub: "P", priv: "Q" }); globalThis.clLoad = () => ({ me: { pid: "p1" } });
globalThis.CLS = { hello: Date.now(), me: { devs: [] } };
globalThis.clHello = async () => { hellos++; CLS.me = { devs }; CLS.hello = Date.now(); };
let posted = 0; globalThis.clReq = async () => { posted++; };
eval((cut('async function devOwnSend(', 'function devBrainsShare(')).replace(/^(async )?function (\w+)/gm, 'globalThis.$2 = $1function'));
(async () => {
  const out = {};
  out.none = await devOwnSend({ want: ["brains"] });
  out.hellosNone = hellos;
  out.missEmpty = devBrainsMiss(false);
  syncStatus.all = [{ me: true, app: "phone" }, { name: "N95", app: "pc", ver: "1.0.22", me: false }];
  out.missPc = devBrainsMiss(true);
  devs = [{ dev: "pc1", pub: "K" }]; CLS.me = { devs: [] }; hellos = 0;
  out.late = await devOwnSend({ want: ["brains"] });
  out.hellosLate = hellos; out.posted = posted;
  console.log(JSON.stringify(out));
})();"""
r = subprocess.run(["node", "-e", js, str(ROOT / "android/assets/www/devices.js")], capture_output=True, text=True)
d = json.loads(r.stdout or "{}")
if not d:
    print(r.stderr[-1500:])
ok(d.get("none") is False and d.get("hellosNone") == 1, "никого — список своих устройств спрошен заново, и только потом «нет»")
ok("подключите их кодом" in (d.get("missEmpty") or ""), "других устройств и правда нет — прежний совет")
ok("«N95» связан с этим телефоном" in (d.get("missPc") or "") and "1.0.22" in d["missPc"] and "Запустите на нём Dewiar" in d["missPc"],
   f"компьютер виден в «Все устройства» — назван по имени и что сделать: {d.get('missPc')}")
ok(d.get("late") is True and d.get("hellosLate") == 1 and d.get("posted") == 1, "компьютер представился позже — заново спрошенный список его находит, просьба уходит")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("devBrainsMiss(true)" in app, "кнопка «Взять мозги» в «Мозге» — тот же ответ")
close = (ROOT / "core/close.py").read_text(encoding="utf-8")
ok("_hello_boot" in close, "компьютер представляется серверу сразу при запуске, а не через час")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
