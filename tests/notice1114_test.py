"""«Лира заметила» (0.97, владелец 14.11: «если бы Лира сама иногда делала что-то полезное — напоминала бы о себе и
показывала пользу без отторжения… предупредила о дожде… а не так, что каждое утро будет злить»). Телефон удерживает хуже
всего: через 7 дней возвращаются 19 % новых против 36 % у компьютера (аналитика 14.11).

Телефон сам (Notice.java, раз в ~3 часа) смотрит, есть ли повод: дождь, снег, гроза, жара, мороз, сильный ветер на
остаток дня, день рождения близкого сегодня (или завтра — вечером). Есть — одно уведомление, не чаще раза в день, не до 8
и не после 21; нет — тишина. Включается одним касанием (предложение один раз, на следующий день после установки) или в
«Настройках» → «Звук»."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


java = (ROOT / "android/src/pro/dewiar/app/Notice.java").read_text(encoding="utf-8")
ok("setPeriodic(3 * 60 * 60 * 1000L)" in java, "фоновая проверка — раз в ~3 часа")
ok("h < 8 || h >= 21" in java and 'today.equals(sp.getString("notice_day"' in java, "тихие часы и не чаще раза в день")
ok("if (why.isEmpty()) return \"\";" in java, "нет повода — тишина")
ok(all(k in java for k in ("prob >= 60", "code >= 95", "tmax >= 30", "tmin <= -15", "gust >= 15")), "поводы погоды: осадки от 60 %, гроза, жара, мороз, ветер")
man = (ROOT / "android/AndroidManifest.xml").read_text(encoding="utf-8")
ok('android:name=".Notice"' in man and "BIND_JOB_SERVICE" in man, "служба объявлена")
ok("public void notice(String json)" in (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8"), "мост: Bridge.notice")

www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.DW_SYS_LANG = 'ru';")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
    r = pg.evaluate("""async () => {
      closeSheets(); const sent = []; D.notice = (j) => sent.push(j);
      S.memory = ['У мамы день рождения 14 ноября', 'Живу в Минске', 'Люблю чай'];
      const days = noticeDays(new Date(2026, 10, 13, 18));
      window.wqGeocode = async (c) => ({ name: c, lat: 53.9, lon: 27.56 });
      S.notice = { on: true, asked: true }; noticeSync.last = undefined; await noticeSync();
      const on = JSON.parse(sent[sent.length - 1] || '{}');
      noticeSet(false); await new Promise(r => setTimeout(r, 50));
      return { days, on, off: sent[sent.length - 1], asked: S.notice.asked };
    }""")
    ok(any(d["date"] == "2026-11-14" and "мамы" in d["text"] for d in r["days"]), f"день рождения из памяти — завтра: {r['days']}")
    ok(r["on"].get("on") and abs(r["on"].get("lat", 0) - 53.9) < .01 and r["on"].get("place") == "Минске" and r["on"].get("who"),
       f"в фон уходят координаты города из памяти и имя персонажа: {r['on']}")
    ok(r["off"] == "" and r["asked"], "выключили — фон выключен, больше не предлагаем")
    # предложение — один раз, не в первый день
    r2 = pg.evaluate("""() => {
      D.notice = () => {}; D.mock = false; S.notice = {}; S.firstRun = Date.now(); noticeOffer(); const a = !!document.querySelector('#nt-offer');
      S.firstRun = Date.now() - 2 * 864e5; noticeOffer(); const el = document.querySelector('#nt-offer');
      return { firstDay: a, later: !!el, text: el ? el.innerText : '' };
    }""")
    ok(not r2["firstDay"] and r2["later"] and "не чаще раза в день" in r2["text"] and "молчу" in r2["text"],
       f"предлагаем один раз, не в первый день, честно — когда и сколько: {r2}")
    pg.click("#nt-no"); pg.wait_for_timeout(200)
    ok(pg.evaluate("!document.querySelector('#nt-offer') && S.notice.asked && !S.notice.on"), "«Не надо» — убрали и больше не спрашиваем")
    pg.evaluate("() => { noticeOffer(); }")
    ok(not pg.evaluate("!!document.querySelector('#nt-offer')"), "второй раз не предлагаем")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
