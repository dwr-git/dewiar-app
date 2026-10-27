"""Отчёт №362 (27.10): «Не может сказать температуру в спальне, 2 дня назад умела». Показания датчиков умного дома
Яндекса (properties: температура, влажность, CO2…) Dewiar не читал вовсе — ни быстрой командой, ни инструментом.
Теперь: «какая температура в спальне», «сколько градусов в детской», «в спальне какая влажность» — сразу, без модели
(компьютер и телефон); нет датчика в комнате — так и сказать; давно не обновлялся — сказать, от какого времени данные;
«температура в Москве» — не умный дом (погода); у модели smart_home list — с показаниями."""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sys.path.insert(0, str(ROOT / "core"))
from smarthome import Home, parse, prop_text  # noqa: E402

ok(parse("Температура в спальне.") == {"op": "read", "target": "в спальне", "what": "temperature"}
   and parse("в спальне какая влажность")["what"] == "humidity" and parse("сколько градусов в детской")["target"] == "в детской"
   and parse("какой уровень углекислого газа в спальне")["what"] == "co2_level", "разбор вопросов о датчиках")
ok(parse("включи свет в спальне")["op"] == "on" and parse("какая погода в спальне") is None, "команды и прочие вопросы — как раньше")
ok(prop_text({"instance": "temperature", "value": 22.46}) == "температура 22,5°" and prop_text({"instance": "humidity", "value": 41.0}) == "влажность 41%"
   and prop_text({"instance": "pressure", "value": 101300, "unit": "unit.pressure.pascal"}) == "давление 101300 Па", "числа по-русски, единицы")

NOW = time.time()
SENSOR = {"id": "d8", "name": "Датчик климата", "room": "r1", "type": "devices.types.sensor.climate", "capabilities": [], "properties": [
    {"type": "devices.properties.float", "parameters": {"instance": "temperature", "unit": "unit.temperature.celsius"},
     "state": {"instance": "temperature", "value": 22.46}, "last_updated": NOW - 60},
    {"type": "devices.properties.float", "parameters": {"instance": "humidity", "unit": "unit.percent"},
     "state": {"instance": "humidity", "value": 41}, "last_updated": NOW - 60}]}
AC = {"id": "d5", "name": "Кондиционер", "room": "r1", "type": "devices.types.thermostat.ac", "capabilities": [], "properties": [
    {"type": "devices.properties.float", "parameters": {"instance": "temperature", "unit": "unit.temperature.celsius"},
     "state": {"instance": "temperature", "value": 25}}]}
OLD = {"id": "d9", "name": "Датчик балкона", "room": "r3", "type": "devices.types.sensor", "capabilities": [], "properties": [
    {"type": "devices.properties.float", "parameters": {"instance": "temperature", "unit": "unit.temperature.celsius"},
     "state": {"instance": "temperature", "value": 3.2}, "last_updated": NOW - 8 * 3600}]}
INFO = {"rooms": [{"id": "r1", "name": "Спальня"}, {"id": "r2", "name": "Кухня"}, {"id": "r3", "name": "Балкон"}],
        "devices": [AC, SENSOR, {"id": "d1", "name": "Люстра", "room": "r2", "type": "devices.types.light", "capabilities": []}, OLD],
        "groups": [], "scenarios": []}

tmp = Path(tempfile.mkdtemp())
h = Home(tmp / "sh.json")
h._req = lambda method, path, body=None: json.loads(json.dumps(INFO))
info = h.info(force=True)
found, vals = h.readings("в спальне", "temperature", info)
ok(found and vals and vals[0]["value"] == 22.46 and vals[0]["device"] == "Датчик климата", f"в спальне — сначала датчик, а не кондиционер: {vals}")
found, vals = h.readings("на кухне", "temperature", info)
ok(found and not vals, "на кухне комната есть, датчика нет")
ok(h.readings("в москве", "temperature", info) == (False, []), "«в Москве» — не дом")
summ = h.summary()
ok("Датчик климата (Спальня) — температура 22,5°, влажность 41%" in summ, f"модель (smart_home list) видит показания: {summ[:160]}")

# телефон
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    r = pg.evaluate("""async (info) => {
      S.home.token = 'y0_test'; homeInfo = { rooms: info.rooms, scenarios: [], devices: info.devices.map(x => Object.assign(x, { room_name: (info.rooms.find(r => r.id === x.room) || {}).name || '' })) };
      homeT = Date.now();
      const q = async (t) => { const x = await homeQuick(t); return x ? x.say : null; };
      return { a: await q('какая температура в спальне'), b: await q('в спальне какая влажность'), c: await q('сколько градусов на кухне'),
               d: await q('какая температура в москве'), e: await q('температура на балконе'), list: await homeTool({ action: 'list' }) }; }""", INFO)
    ok(r["a"] == "В спальне 22,5°." and r["b"] == "В спальне влажность 41%.", f"телефон: температура и влажность сразу: {r['a']!r} {r['b']!r}")
    ok(r["c"] and "нет датчика" in r["c"] and r["d"] is None, f"телефон: нет датчика — так и сказать; Москва — не дом: {r['c']!r} {r['d']!r}")
    ok(r["e"] and r["e"].startswith("На балконе 3,2°.") and "давно не присылал" in r["e"], f"телефон: старые данные — с временем: {r['e']!r}")
    ok("Датчик климата (Спальня) — температура 22,5°, влажность 41%" in r["list"], "телефон: модель видит показания")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
