"""Связь телефона и компьютера — понятная (владелец 20.11: «делаем»). В «Устройствах» ошибка обмена — словами, что
случилось и что делать (а не «облако ответило 503» или «Failed to fetch»), и отдельной строкой — компьютер: на связи он
или нет, и что это значит («выключен — получит всё сам, когда включится»). То же — во всплывающей подсказке «Синхронизировать сейчас»."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
bad = 0


def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


js = (ROOT / "android/assets/www/devices.js").read_text(encoding="utf-8")
code = r"""
const vm = require('vm'); const ctx = { S: { llm: {}, sync: {} }, D: { info: () => '{}' }, console };
vm.createContext(ctx); vm.runInContext(process.argv[1] + `
;globalThis.R = {
  net: devSyncHuman('Failed to fetch'), auth: devSyncHuman('облако ответило 401'), busy: devSyncHuman('облако ответило 503'),
  e2e: devSyncHuman('не удалось расшифровать запись'), other: devSyncHuman('что-то своё'),
  none: devPcLine([{ app: 'phone', me: true }]),
  on: devPcLine([{ app: 'pc', name: 'Ноутбук', seen: Date.now() / 1000 - 30 }]),
  off: devPcLine([{ app: 'pc', name: 'Ноутбук', seen: Date.now() / 1000 - 3 * 3600 }, { app: 'pc', name: 'Старый', seen: Date.now() / 1000 - 9 * 86400 }]),
};`, ctx);
console.log(JSON.stringify(ctx.R));
"""
r = json.loads(subprocess.run(["node", "-e", code, js], capture_output=True, text=True, check=True).stdout)
ok("проверьте интернет" in r["net"] and "уйдут сами" in r["net"], f"нет сети — словами: {r['net']}")
ok("войдите снова" in r["auth"], "вход устарел — что нажать")
ok("занят" in r["busy"] and "сама" in r["busy"], "сайт занят — повторит сама")
ok("Ввести код" in r["e2e"], "ключ шифрования — что сделать")
ok(r["other"] == "Не синхронизировалось: что-то своё", "незнакомое — как есть")
ok("пока нет" in r["none"], "компьютера нет — как подключить")
ok("«Ноутбук» на связи" in r["on"], "компьютер на связи")
ok("«Ноутбук» сейчас не на связи" in r["off"] and "был 3 ч назад" in r["off"] and "получит всё" in r["off"], f"выключен — что это значит: {r['off']}")
ok('id="dv-pc"' in js and "devSyncHuman(s.error)" in js, "в «Устройствах» — строка компьютера и ошибка словами")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("devSyncHuman(bad.err.message)" in app, "«Синхронизировать сейчас» — подсказка словами")
st = (ROOT / "ui/studio/devices.js").read_text(encoding="utf-8")
ok("dvSyncHuman(st.error)" in st and "Нет связи с dewiar.pro" in st, "компьютер, студия → «Устройства»: ошибка обмена тоже словами")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
