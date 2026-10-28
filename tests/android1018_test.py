"""Телефон, просьбы 18.10 (ранний пользователь: «последние дни подтормаживает телефон»; «скачивая новые версии, в
Загрузках много этих версий»; «чтобы Лира умела чистить мусор»):
- лёгкий режим: сам на слабом телефоне (≤ 3 ГБ, «маломощный» по Android), при экономии батареи и медленных кадрах;
  вручную — «всегда»/«никогда». Портрет неподвижен в покое, ~20 кадров/с в разговоре, наклон не следим, синхронизация
  реже, «Близкие» без постоянной связи (проверка раз в 15 минут);
- обновление внутри приложения: качает само в свою папку (sha256), открывает установщик, файл потом удаляет; старые
  apk из «Загрузок» — кнопкой «Открыть Загрузки»;
- «освободи место» — без модели: свой кэш, размер Dewiar и системное «Хранилище»; «очисти память» — не сюда."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


man = (ROOT / "android/AndroidManifest.xml").read_text(encoding="utf-8")
ok("android.permission.REQUEST_INSTALL_PACKAGES" in man and re.search(r'\.UpdateProvider"[^>]*exported="false"[^>]*grantUriPermissions="true"', man),
   "манифест: разрешение ставить обновления, файл — установщику только по выданному разрешению")
upd = (ROOT / "android/src/pro/dewiar/app/Update.java").read_text(encoding="utf-8")
ok("SHA-256" in upd and "getCacheDir()" in upd and "FLAG_GRANT_READ_URI_PERMISSION" in upd and "versionCode <= cur.versionCode" in upd,
   "Update.java: в свою папку, проверка sha256, установщику с разрешением, после установки файл удаляется")
main = (ROOT / "android/src/pro/dewiar/app/MainActivity.java").read_text(encoding="utf-8")
ok("Update.cleanup(app)" in main, "при запуске: обновление уже стоит — файл удаляем")
br = (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8")
ok(all(f"public {t} {n}(" in br for t, n in (("String", "deviceClass"), ("void", "updateGet"), ("String", "updateInstall"),
                                               ("boolean", "openDownloads"), ("String", "appSize"), ("long", "clearOwnCache"), ("boolean", "openStorage"))),
   "мост: сила телефона, обновление, «Загрузки», размер и кэш, «Хранилище»")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("(!liteOn() || ++syncTick % 3 === 0)" in app and "(!liteOn() || ++joinTick % 3 === 0)" in app, "лёгкий режим: синхронизация и проверки — втрое реже")
ent = (ROOT / "ui/assets/entities.js").read_text(encoding="utf-8")
ok("if (this.lite) minDt = Math.max(minDt, 50);" in ent, "облик: в лёгком режиме не чаще ~20 кадров/с")

from playwright.sync_api import sync_playwright  # noqa: E402
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js", "skins.css", "skins.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 412, "height": 880}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
    # ---------- лёгкий режим ----------
    r = pg.evaluate("""() => { const out = {}; S.tilt = true; S.close = { live: true };
      const snap = () => [liteOn(), !!orb.still, !!orb.lite, clLiveOn(), clLiveWanted(), tiltWanted(), liteWhyNow];
      liteApply(); out.strong = snap();
      window._dev = { ram_mb: 2048, low_ram: false, cores: 4, power_save: false }; liteApply(); out.weak = snap();
      S.lite = "off"; liteApply(); out.weakOff = snap();
      window._dev = { ram_mb: 8192, low_ram: false, cores: 8, power_save: true }; S.lite = "auto"; liteApply(); out.saver = snap();
      window._dev = { ram_mb: 8192, low_ram: false, cores: 8, power_save: false }; S.lite = "on"; liteApply(); out.manual = snap();
      S.lite = "auto"; liteApply(); out.back = snap();
      return out; }""")
    ok(r["strong"][:4] == [False, False, False, True], f"сильный телефон — обычный режим, «Близкие» на связи: {r['strong']}")
    ok(r["weak"][:6] == [True, True, True, False, True, False] and "2 ГБ" in r["weak"][6],
       f"2 ГБ памяти — лёгкий режим сам: портрет неподвижен, «Близкие» раз в 15 минут (настройка цела), наклон выключен: {r['weak']}")
    ok(r["weakOff"][0] is False and r["saver"][0] is True and "экономия батареи" in r["saver"][6] and r["manual"][0] is True
       and "вручную" in r["manual"][6] and r["back"][0] is False,
       f"«никогда» — выключен даже на слабом; экономия батареи — включён; «всегда» — включён: {r['weakOff'][0]}, {r['saver']}, {r['manual']}")
    r = pg.evaluate("""() => { window._dev = { ram_mb: 2048 }; S.lite = "auto"; openSettings("lite"); const sel = document.getElementById("ap-lite");
      const out = [sel && sel.value, (document.getElementById("lite-now") || {}).textContent || ""];
      sel.value = "off"; sel.onchange(); out.push(S.lite, liteOn(), document.getElementById("lite-now").textContent); closeSheets(true); return out; }""")
    ok(r[0] == "auto" and "Сейчас включён: памяти 2 ГБ" in r[1] and r[2:4] == ["off", False] and "Сейчас выключен" in r[4],
       f"«Ещё»: «Лёгкий режим» — сам/всегда/никогда и почему сейчас включён: {r}")
    # ---------- обновление ----------
    r = pg.evaluate("""async () => { const out = {}; let box = document.getElementById("upd-res"); if (!box) { box = document.createElement("div"); box.id = "upd-res"; document.body.appendChild(box); }
      window.http = async () => ({ body: JSON.stringify({ android: { version: "9.9.9", apk: "Dewiar-9.9.9.apk", sha256: "ab12" } }) });
      await checkUpdate(true); out.offer = box.textContent; out.btn = !!document.getElementById("upd-go");
      document.getElementById("upd-go").click(); await new Promise(r => setTimeout(r, 300));
      out.got = window._upd; out.inst = window._updInst || 0; out.after = box.textContent;
      window._updPerm = true; updInstall(); out.perm = box.textContent;
      window._updPerm = false; document.dispatchEvent(new Event("visibilitychange")); out.inst2 = window._updInst || 0; out.after2 = box.textContent;
      window.http = async () => ({ body: JSON.stringify({ android: { version: "0.0.1", apk: "x.apk" } }) });
      await checkUpdate(true); out.latest = box.textContent; document.getElementById("upd-dl").click(); out.dls = window._dls || 0;
      return out; }""")
    ok("Есть Dewiar 9.9.9" in r["offer"] and r["btn"] and r["got"] and r["got"][0].endswith("/Dewiar-9.9.9.apk") and r["got"][1] == "ab12"
       and r["inst"] == 1 and "Открылась установка" in r["after"], f"«Обновить» — Dewiar сам качает (с sha256) и открывает установку: {r}")
    ok("Разрешите Dewiar устанавливать" in r["perm"] and r["inst2"] == 2 and "Открылась установка" in r["after2"],
       "нужно разрешение — объясняем; вернулись из настроек — установка начинается сама")
    ok("последняя версия" in r["latest"] and "Открыть Загрузки" in r["latest"] and r["dls"] == 1, "старые apk из «Загрузок» — кнопкой «Открыть Загрузки»")
    # ---------- «освободи место» ----------
    r = pg.evaluate("""async () => { const out = {};
      out.free = (await quick("Освободи место на телефоне")).say; out.cleared = window._cleared || 0;
      await new Promise(r => setTimeout(r, 2700)); out.storage = window._storage || 0;
      out.size = (await quick("Сколько места занимает Dewiar?".replace("?", ""))).say;
      out.mem = freeSpaceQuick("очисти память"); out.forget = freeSpaceQuick("очисти историю");
      return out; }""")
    ok("освободилось 47 МБ" in r["free"] and "Хранилище" in r["free"] and r["cleared"] == 1 and r["storage"] == 1,
       f"«освободи место» — свой кэш почищен, открыто «Хранилище», честно про чужие приложения: {r['free']}")
    ok("60 МБ" in r["size"] and r["mem"] is None and r["forget"] is None, f"«сколько места занимает Dewiar» — размер; «очисти память» — не сюда: {r['size']}")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
shutil.rmtree(www.parent, ignore_errors=True)                # не оставлять копии страниц в /tmp
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
