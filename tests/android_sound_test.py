"""Звук напоминаний на телефоне: свои мягкие мелодии вместо системного «подъёма на работу», выбор и проба в «Ещё»,
свой файл; окно будильника звучит выбранным звуком по кругу и нарастает, уведомление не звучит вторым голосом.
Java проверяется по исходникам (сборка — android/tools/build_apk.sh), интерфейс — в Chromium с заглушкой моста."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


SRC = ROOT / "android/src/pro/dewiar/app"
raw = ROOT / "android/res/raw"
# 28.10: пять звонков, выбрал владелец (звуки Android Open Source Project, Apache 2.0 — NOTICE); фирменный — «Пульс»
names = ["signature", "noon", "night", "wave", "sparks"]
ok(all((raw / f"alarm_{n}.ogg").stat().st_size > 10000 for n in names) and sorted(x.name for x in raw.glob("alarm_*.ogg")) == sorted(f"alarm_{n}.ogg" for n in names),
   "пять звонков в res/raw, прежних нет (фирменный «Пульс» — первый)")
ok("Android Open Source Project" in (ROOT / "NOTICE").read_text(encoding="utf-8") and "Apache" in (ROOT / "NOTICE").read_text(encoding="utf-8"),
   "откуда звуки и лицензия — в NOTICE")
if shutil.which("ffprobe"):
    durs = [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw / f"alarm_{n}.ogg")],
                                 capture_output=True, text=True).stdout or 0) for n in names]
    ok(all(4 <= d <= 15.5 for d in durs), f"каждая — от 4 до 15 секунд (повторяется по кругу): {durs}")
snd = (SRC / "Sounds.java").read_text(encoding="utf-8")
ok(all(f"R.raw.alarm_{n}" in snd for n in names) and '"system"' in snd and '"custom"' in snd, "Sounds: свои мелодии, системный звук и свой файл")
ok('pre = soft ? "rem_" : "alarm_"' in snd and 'pre + sound' in snd and "deleteNotificationChannel" in snd and "USAGE_ALARM" in snd, "у каждого звука свой канал уведомлений, прежний убирается")
ok('"/raw/" + c.getResources().getResourceEntryName(res(id))' in snd and ': "_3")' in snd,
   "звук канала — по имени ресурса (числа R.raw меняются при новых звуках), каналы пересоздаются под новые звонки")
ok('case "chasha"' not in snd and "res(s) != 0" in snd, "прежний выбор (chasha, kolodec…) — снова фирменный")
act = (SRC / "AlarmActivity.java").read_text(encoding="utf-8")
ok("Sounds.play(this, Sounds.current(this), true, vol, soft)" in act and "vol + 0.0375f" in act and "AlarmReceiver.quiet(" in act,
   "окно будильника: выбранный звук по кругу, громкость нарастает, уведомление смолкает")
rcv = (SRC / "AlarmReceiver.java").read_text(encoding="utf-8")
ok("Sounds.channel(c, soft)" in rcv and "Sounds.quietChannel(c)" in rcv and "Compat.CH_ALARM" not in rcv, "уведомление — в канал выбранного звука")
ok("addAction(action(c, DONE" in rcv and "SNOOZE" in rcv and "AlarmActivity.closeIfOpen(id)" in rcv and "4 /* IMPORTANCE_HIGH */" in snd and "QUIET = \"alarm_watch\"" in snd,
   "напоминание видно на часах: тихое уведомление остаётся важным, кнопки «Понял» и «Через 10 минут» работают и с часов")
ok("SOUND_DELAY_MS" in act and "postDelayed" in act and "nm.cancel(id.hashCode());            // снятое" not in rcv and '.putExtra("fired"' in rcv,
   "первые секунды звучит само уведомление (его видят часы), окно берёт звук потом; уведомление не снимается, а обновляется")
man = (ROOT / "android/AndroidManifest.xml").read_text(encoding="utf-8")
prov = (SRC / "SoundProvider.java").read_text(encoding="utf-8")
ok('android:name=".SoundProvider"' in man and '"/custom".equals(uri.getPath())' in prov and "MODE_READ_ONLY" in prov,
   "свой файл системе — только чтение и только он")
br = (SRC / "Bridge.java").read_text(encoding="utf-8")
# идея №72 (30.10): «в гарнитуре напоминание орёт в ухо, будильник на максимуме — убавлю, просплю работу»
ok("boolean soft(Context c, String kind)" in snd and '!"alarm".equals(kind) && !"timer".equals(kind)' in snd
   and "USAGE_NOTIFICATION_EVENT : AudioAttributes.USAGE_ALARM" in snd and 'getBoolean("rem_soft", false)' in snd,
   "№72: напоминание о деле — потоком уведомлений (своя громкость), будильник и таймер — громкостью будильника; по умолчанию как было")
ok("boolean soft = Sounds.soft(c, kind)" in rcv and "Sounds.attrs(soft)" in rcv and "Sounds.attrs(soft)" in act
   and "boolean soft = Sounds.soft(this, kind)" in act, "№72: и уведомление, и окно — одним потоком (иначе первые секунды — громко)")
ok("public boolean alarmSoundSoft(boolean on)" in br and '.put("soft", Sounds.softOn(a))' in br, "№72: мост — переключатель и его состояние")
ok(all(f"public String {m}(" in br or f"boolean {m}(" in br for m in ("alarmSound", "alarmSoundSet", "alarmSoundTry", "alarmSoundCustom")),
   "мост: выбор, проба и свой файл")

www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
for f in ("skins.css", "skins.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/skins", www / "skins", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
audio = Path(tempfile.mkdtemp()) / "моя мелодия.ogg"
shutil.copy(raw / "alarm_wave.ogg", audio)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("openSettings('sound')"); pg.wait_for_timeout(400)
    rows = pg.evaluate("() => [$$('.snd').map(x => x.dataset.snd), $('.snd.on').dataset.snd, $('.snd[data-snd=custom]').classList.contains('nofile')]")
    ok(rows[0] == names + ["system", "custom"] and rows[1] == "signature" and rows[2],
       f"«Звук напоминаний»: все звуки и свой, по умолчанию — фирменный «Пульс»: {rows}")
    pg.click('.snd[data-snd="night"]'); pg.wait_for_timeout(150)
    st = pg.evaluate("() => [$('.snd.on').dataset.snd, $('.snd.play') && $('.snd.play').dataset.snd, JSON.parse(D.alarmSound()).id]")
    ok(st == ["night", "night", "night"], f"нажатие — выбрано и звучит проба: {st}")
    pg.click('.snd[data-snd="night"]'); pg.wait_for_timeout(150)
    ok(not pg.evaluate("!!$('.snd.play')"), "ещё раз — проба смолкла")
    pg.set_input_files("#snd-file", str(audio)); pg.wait_for_timeout(500)
    cu = pg.evaluate("() => [$('.snd.on').dataset.snd, $('#snd-name').textContent, $('#snd-res').textContent, JSON.parse(D.alarmSound())]")
    ok(cu[0] == "custom" and cu[1] == "моя мелодия" and "выбран" in cu[2] and cu[3] == {"id": "custom", "custom": "моя мелодия", "soft": False},
       f"свой файл: сохранён и выбран: {cu}")
    sw = pg.evaluate("() => [!!$('#snd-soft'), $('#snd-soft') && $('#snd-soft').checked, $('#snd-soft') && $('#snd-soft').closest('.sw').textContent]")
    ok(sw[0] and sw[1] is False and "громкостью уведомлений" in sw[2] and "Будильник и таймер остаются громкими" in sw[2],
       f"№72: в «Звуке напоминаний» — «Напоминания — громкостью уведомлений», выключено: {sw[:2]}")
    pg.click("label:has(#snd-soft)"); pg.wait_for_timeout(150)
    ok(pg.evaluate("JSON.parse(D.alarmSound()).soft") is True, "№72: включили — телефон запомнил")
    pg.evaluate("closeSheets(); openSettings('sound')"); pg.wait_for_timeout(300)
    ok(pg.evaluate("$('#snd-soft').checked") is True, "№72: открыли снова — включено")
    pg.evaluate("closeSheets()"); pg.wait_for_timeout(100)
    ok(not pg.evaluate("window._trying"), "лист закрыли — проба смолкла")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
