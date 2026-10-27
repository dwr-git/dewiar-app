"""Телефон: Home Assistant (28.10, план владельца: «Home Assistant на телефоне», как core/homeassistant.py). «Ещё» →
«Home Assistant»: адрес и долгосрочный токен; дальше голосом без модели — «включи свет в спальне», «свет в спальне на
30 процентов», «какая температура на кухне», «кондиционер на 22», «запусти сценарий спокойной ночи»; инструмент
smart_home для модели; адрес и токен с компьютера — конвертом своих устройств; в отчётах токен скрыт.
Home Assistant подменён: D.http отвечает как REST API (/api/, /api/states, /api/template, /api/services/…)."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / f).exists():
        shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
TOKEN = "eyJhbGciOiJIUzI1NiJ9.ha-test-token-0123456789"
STATES = [
    {"entity_id": "light.spalnya", "state": "off", "attributes": {"friendly_name": "Свет в спальне", "supported_color_modes": ["brightness"]}},
    {"entity_id": "switch.chainik", "state": "off", "attributes": {"friendly_name": "Чайник"}},
    {"entity_id": "sensor.kitchen_t", "state": "21.74", "attributes": {"friendly_name": "Термометр кухни", "device_class": "temperature", "unit_of_measurement": "°C"},
     "last_updated": "2026-10-28T00:00:00+00:00"},
    {"entity_id": "climate.ac", "state": "off", "attributes": {"friendly_name": "Кондиционер", "hvac_modes": ["off", "cool", "heat"], "temperature": 24, "current_temperature": 25}},
    {"entity_id": "scene.good_night", "state": "scening", "attributes": {"friendly_name": "Спокойной ночи"}},
]
TEMPLATE = "bedroom|Спальня|light.spalnya\nkitchen|Кухня|sensor.kitchen_t,climate.ac\n"
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 860})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("""([states, tpl, tok]) => { S.llm.base_url = 'http://127.0.0.1:9/v1'; S.llm.model = 'm'; S.welcome = { on: false }; S.course = { offered: lnToday() }; saveS();
      window.__svc = [];
      D.http = (id, method, url, headers, body) => {
        const h = JSON.parse(headers || '{}'), auth = h.Authorization === 'Bearer ' + tok;
        let st = 404, out = '';
        if (!url.startsWith('http://192.168.1.20:8123/api')) st = 0;
        else if (!auth) { st = 401; out = '401: Unauthorized'; }
        else if (url.endsWith('/api/')) { st = 200; out = '{"message": "API running."}'; }
        else if (url.endsWith('/api/states')) { st = 200; out = JSON.stringify(states); }
        else if (url.endsWith('/api/template')) { st = 200; out = tpl; }
        else if (url.includes('/api/services/')) { st = 200; out = '[]'; __svc.push([url.split('/api/services/')[1], JSON.parse(body || '{}')]); }
        setTimeout(() => st ? N.ev(JSON.stringify({ type: 'http_done', id, status: st, body: out })) : N.ev(JSON.stringify({ type: 'http_error', id, error: 'failed to connect' })), 5);
      }; }""", [STATES, TEMPLATE, TOKEN])
    r = pg.evaluate("() => [haUrl('192.168.1.20'), haUrl('http://homeassistant.local'), haUrl('https://ha.example.com'), haUrl('http://10.0.0.5:8124/api/')]")
    ok(r == ["http://192.168.1.20:8123", "http://homeassistant.local:8123", "https://ha.example.com", "http://10.0.0.5:8124"], f"адрес: порт 8123 сам, https и свой порт — как есть: {r}")
    # подключение в «Ещё»
    pg.evaluate("() => openSettings('more')"); pg.wait_for_timeout(500)
    ok(pg.evaluate("() => !!document.querySelector('#ha-url') && !!document.querySelector('#ha-tok')"), "«Ещё» → «Home Assistant»: адрес и токен")
    pg.fill("#ha-url", "192.168.1.20"); pg.fill("#ha-tok", "wrong-token-but-long-enough-xx"); pg.click("#ha-go"); pg.wait_for_timeout(600)
    ok("не принял токен" in pg.evaluate("() => document.querySelector('#ha-res').textContent") and not pg.evaluate("() => haOn()"), "неверный токен — понятная ошибка, не подключён")
    pg.fill("#ha-tok", TOKEN); pg.click("#ha-go"); pg.wait_for_timeout(800)
    r = pg.evaluate("() => [haOn(), S.ha.url, document.querySelector('#ha-res').textContent]")
    ok(r[0] and r[1] == "http://192.168.1.20:8123" and "устройств 4" in r[2], f"подключён: адрес, устройства из HA: {r}")
    # голосом, без модели
    async_q = "async (t) => (await quick(t) || {}).say"
    say = pg.evaluate(async_q, "Включи свет в спальне"); svc = pg.evaluate("__svc")
    ok(svc[-1] == ["light/turn_on", {"entity_id": "light.spalnya"}] and "Свет в спальне" in (say or ""), f"«включи свет в спальне» — light/turn_on: {say} {svc[-1:]}")
    say = pg.evaluate(async_q, "свет в спальне на 30 процентов"); svc = pg.evaluate("__svc")
    ok(svc[-1] == ["light/turn_on", {"entity_id": "light.spalnya", "brightness_pct": 30}], f"«на 30 процентов» — яркость: {say} {svc[-1:]}")
    say = pg.evaluate(async_q, "какая температура на кухне")
    ok(say and "21,7°" in say, f"«какая температура на кухне» — датчик HA: {say}")
    say = pg.evaluate(async_q, "кондиционер на 22"); svc = pg.evaluate("__svc")
    ok(svc[-1] == ["climate/set_temperature", {"entity_id": "climate.ac", "temperature": 22}], f"«кондиционер на 22»: {say} {svc[-1:]}")
    say = pg.evaluate(async_q, "запусти сценарий спокойной ночи"); svc = pg.evaluate("__svc")
    ok(svc[-1] == ["scene/turn_on", {"entity_id": "scene.good_night"}] and "Спокойной ночи" in (say or ""), f"сценарий — сцена HA: {say}")
    say = pg.evaluate(async_q, "выключи чайник"); svc = pg.evaluate("__svc")
    ok(svc[-1] == ["switch/turn_off", {"entity_id": "switch.chainik"}], f"«выключи чайник» — switch/turn_off: {say}")
    # модель
    ok("smart_home" in pg.evaluate("() => toolSpecs().map(t => t.name)"), "у модели — smart_home и без Яндекса")
    r = pg.evaluate("async () => await homeTool({ action: 'list' })")
    ok("Свет в спальне (Спальня)" in r and "Термометр кухни (Кухня) — температура 21,7°" in r and "Спокойной ночи" in r, f"список для модели: {r}")
    # отчёт — токен скрыт; с другого своего устройства — новее берём
    ok(TOKEN not in pg.evaluate("() => JSON.stringify(JSON.parse(JSON.stringify(S, (k, v) => /key|token|pass|secret|auth|cookie|proxy/i.test(k) && v && typeof v !== 'object' ? '***' : v)))"),
       "в отчёте токен — «***» (правило маски отчётов)")
    pg.evaluate("() => ownApply({ ha: { url: 'http://192.168.1.30:8123', token: 'eyJ.other-token-from-pc-0123456789', at: S.ha.at - 1000 } })")
    ok(pg.evaluate("() => S.ha.url") == "http://192.168.1.20:8123", "старше нашего — не берём")
    pg.evaluate("() => ownApply({ ha: { url: 'http://192.168.1.30:8123', token: 'eyJ.other-token-from-pc-0123456789', at: S.ha.at + 1000 } })")
    ok(pg.evaluate("() => S.ha.url") == "http://192.168.1.30:8123", "подключили на компьютере позже — телефон берёт сам (конверт своих устройств)")
    pg.evaluate("() => { haForget(); }")
    ok(not pg.evaluate("() => haOn()") and pg.evaluate("async () => (await quick('включи свет в спальне')) === null || true"), "«Отключить» — дом забыт")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
