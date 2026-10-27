"""Напоминания на телефоне (пакет 27.10): №338 «просил на 7:40 — поставлено на 7:23» (модель передала in_minutes=7) —
названные человеком часы и минуты важнее модели; №339 «отложил на 10 минут, нажал „Отменить“ — всё равно сработало» —
«Отменить» снимает и отложенные копии (<id>-s<время>)."""
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
    r = pg.evaluate("""async () => { turnAsk = 'Напоминание 7:40'; const t = await runTool('set_reminder', { title: 'встать', in_minutes: 7 });
      const l = JSON.parse(D.alarms() || '[]'); const x = l[l.length - 1]; const d = new Date(x.at); return [t, d.getHours(), d.getMinutes()]; }""")
    ok(r[1] == 7 and r[2] == 40, f"«напоминание 7:40» — на 7:40, а не «через 7 минут»: {r}")
    r = pg.evaluate("""async () => { turnAsk = 'напомни через 20 минут выключить духовку'; const t0 = Date.now(); await runTool('set_reminder', { title: 'духовка', in_minutes: 20 });
      const l = JSON.parse(D.alarms() || '[]'); const x = l.find(y => y.title === 'духовка'); return Math.round((x.at - t0) / 60000); }""")
    ok(r == 20, f"«через 20 минут» — как было: {r}")
    r = pg.evaluate("""() => { D.alarmSet ? 0 : 0; const l0 = JSON.parse(D.alarms() || '[]');
      const add = (x) => { const l = JSON.parse(D.alarms() || '[]'); };
      return l0.map(x => x.id); }""")
    # отложенная копия: как её заводит AlarmActivity.snoozeLater
    pg.evaluate("""() => { const l = JSON.parse(D.alarms() || '[]'); const x = l.find(y => y.title === 'встать');
      window._base = x.id; D.alarmSet(JSON.stringify(Object.assign({}, x, { id: x.id + '-s123', at: Date.now() + 600000 }))); }""")
    ids = pg.evaluate("JSON.parse(D.alarms()).map(x => x.id)")
    ok(any(i.endswith("-s123") for i in ids), f"отложенная копия заведена: {ids}")
    pg.evaluate("cancelAlarm(_base)")
    ids = pg.evaluate("JSON.parse(D.alarms()).map(x => x.id)")
    ok(not any(i.startswith(pg.evaluate("_base")) for i in ids), f"«Отменить» — сняты и отложенные копии: {ids}")
    # №301/№304: open-meteo не открывается — погода через сервер Dewiar
    w = pg.evaluate("""async () => { const h = window.http; window.http = async (m, u, o) => { if (/open-meteo/.test(u)) throw new Error('сервер долго не отвечает'); return h(m, u, o); };
      window.dewiarWeb = async (k, u) => ({ text: JSON.stringify(/geocoding/.test(u) ? { results: [{ name: 'Москва', latitude: 55.7, longitude: 37.6 }] }
        : { current: { temperature_2m: 7.2, apparent_temperature: 4, weather_code: 3, wind_speed_10m: 11 }, daily: {} }) });
      try { return await weather('Москва', 1); } finally { window.http = h; } }""")
    ok(w.startswith("Москва: сейчас 7°"), f"погода на телефоне — через сервер Dewiar: {w[:60]!r}")
    # №333: «включи пожалуйста фонарик» — без модели
    r = pg.evaluate("""async () => { window._torch = []; window.devTorch = (on) => { _torch.push(on); return true; };
      const a = await quick('включи пожалуйста фонарик'), b = await quick('Выключи, пожалуйста, фонарик'); return [a && a.say, b && b.say, _torch]; }""")
    ok(r[2] == [True, False], f"фонарик с «пожалуйста» посередине — сразу: {r}")
    # №329: «Добавить устройство» — в «Синхронизации», и когда мозг свой
    pg.evaluate("""() => { S.llm = Object.assign({}, DEF.llm, { kind: 'openai', base_url: 'https://routerai.ru/v1', model: 'm', api_key: 'k' }); S.sync = Object.assign({}, S.sync, { on: true, key: 'dw-abcd-1234' });
      saveS(); window._pairReq = []; const h = window.http; window.http = async (m, u, o) => { if (/pair\/new/.test(u)) { _pairReq.push([u, o.headers.Authorization]); return { status: 200, body: '{"code":"123456"}' }; } return h(m, u, o); };
      setTab = 'more'; openSettings('more'); }""")
    pg.wait_for_timeout(400)
    ok(pg.locator("#sy-pair").count() == 1, "в «Синхронизации» есть «Добавить устройство» при своём мозге")
    pg.evaluate("document.querySelector('#sy-pair').scrollIntoView()"); pg.click("#sy-pair"); pg.wait_for_timeout(300)
    ok("123 456" in pg.inner_text("#sy-pair-res") and pg.evaluate("_pairReq[0][1]") == "Bearer dw-abcd-1234", "код выдан по ключу синхронизации")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
