"""0.87 (владелец 11.11, Android): «Иногда задачи ко времени приходят в другое время, например на час позже, как будто
телефон спал, и потом что-то произошло и напоминание сработало. Разблокирую экран — и не могу найти это напоминание,
музыка звучит, приходится искать приложение, входить в него и останавливать».

Причины (наши): напоминания и таймеры ставились setExactAndAllowWhileIdle — в глубоком сне Android и оболочки
(Xiaomi, Samsung, Tecno) их придерживают; только «будильник» шёл через setAlarmClock. Пропущенное (телефон выключен,
сигнал сняла «очистка») убиралось молча. Смена пояса сдвигала будильник на разницу. Звук играло окно AlarmActivity даже
невидимым (запущено «за спиной», ушло с экрана после разблокировки) — а его нет в «Недавних», и кнопки уведомления его
не находили (ссылка на окно — только после onResume). Теперь: всё — setAlarmClock; пропущенное показывается с
«(должно было в 14:00)»; смена времени/пояса переставляет; звучит уведомление (повторяется, с «Стоп» и «Отложить на
10 мин», видно на экране блокировки), окно берёт звук, только когда его видно; через 2 минуты смолкает само; в
приложении — «Напоминания вовремя»: что мешает и куда нажать (по марке телефона).

Проверки: исходники Java и манифест — текстом; AlarmTime (опоздание, пропущенное, пояс) — настоящий код на Java;
сборка — android/tools/build_apk.sh --check (без ключа подписи); интерфейс — app.js в Chromium с заглушкой моста."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = os.environ.get("DEWIAR_SHOTS")
SRC = ROOT / "android/src/pro/dewiar/app"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


rd = lambda n: (SRC / n).read_text(encoding="utf-8")
al, rcv, act, boot, cmp, br, main = (rd(n) for n in ("Alarms.java", "AlarmReceiver.java", "AlarmActivity.java", "BootReceiver.java",
                                                       "Compat.java", "Bridge.java", "MainActivity.java"))
man = (ROOT / "android/AndroidManifest.xml").read_text(encoding="utf-8")
sched = re.search(r"static void schedule\(Context c, JSONObject x\).*?\n    \}\n", al, re.S).group(0)

# ---------- 1. опоздание: как ставится сигнал ----------
ok("am.setAlarmClock(new AlarmManager.AlarmClockInfo(at, sp), p)" in sched and '"alarm".equals(x.optString("kind"))' not in sched
   and "setExactAndAllowWhileIdle" not in sched,
   "все напоминания, будильники и таймеры — setAlarmClock (Android не откладывает его во сне), не только «будильник»")
ok("catch (SecurityException e)" in sched and sched.count("setAndAllowWhileIdle") == 2 and '"mode"' in sched,
   "без права на точные — «примерно» (setAndAllowWhileIdle), отозвали право на ходу — не падает; как стоит — в mode")
ok("pi(c, x.getString(\"id\"), x.optString(\"title\"), at)" in sched and '.putExtra("due", due)' in al,
   "сигнал несёт время, на которое поставлен (due): приёмник видит опоздание")
resch = re.search(r"public static synchronized void rescheduleAll\(Context c\).*?\n    \}\n", al, re.S).group(0)
ok("давно прошедшее — убрать" not in resch and "AlarmReceiver.missed(" in resch and "AlarmTime.missed(at, now)" in resch
   and "am.cancel(pi(c, x.getString(\"id\"), \"\"))" in resch,
   "пропущенное (телефон выключен, сигнал сняли) не пропадает молча: показывается; снятое разовое — и из AlarmManager")
ok("AlarmTime.moved(" in resch and "stamp(x)" in resch and 'x.put("tz", tz.getID()).put("wall"' in al and "stamp(item)" in al,
   "пояс сменился — будильник и повторяющееся встают на те же часы на стене")
for a in ("BOOT_COMPLETED", "MY_PACKAGE_REPLACED", "TIME_SET", "TIMEZONE_CHANGED", "QUICKBOOT_POWERON",
          "android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED"):
    ok(f'.{a}"/>' in man or f'"{a}"/>' in man or a in man.split('android:name=".BootReceiver"', 1)[1].split("</receiver>", 1)[0],
       f"манифест: BootReceiver слышит {a}")
ok("Intent.ACTION_TIME_CHANGED" in boot and "Intent.ACTION_TIMEZONE_CHANGED" in boot and "EXACT_CHANGED" in boot and "Alarms.rescheduleAll(c)" in boot,
   "перезагрузка, обновление, смена времени и пояса, разрешили точные — всё переставляется")
ok("cur.optLong(\"at\") - System.currentTimeMillis() > AlarmTime.DUE_SOON_MS" in rcv,
   "сигнал, уже обработанный при запуске (переставлен на завтра), второй раз не звонит")
ok("Alarms.rescheduleAll(this);" in main, "при каждом запуске приложения — тоже переставляется (оболочка могла снять сигналы)")

# ---------- 2. звук: остановить без входа в приложение ----------
post = re.search(r"private static void post\(.*?\n    \}\n", rcv, re.S).group(0)
ok('action(c, DONE, id, title, kind, who, "Стоп")' in post and '"Отложить на 10 мин"' in post and '"Сделано ✓"' in post,
   "в уведомлении — «Стоп» и «Отложить на 10 мин» (у дела — ещё «Сделано ✓»)")
ok("setVisibility(Notification.VISIBILITY_PUBLIC)" in post and "setFullScreenIntent(fp, true)" in post and "CATEGORY_ALARM" in post,
   "уведомление целиком видно на экране блокировки, с полноэкранным окном")
ok("n.flags |= Notification.FLAG_INSISTENT" in post and "setDeleteIntent(broadcast(c, DISMISS" in post and "setAutoCancel(false)" in post,
   "пока окна не видно — звучит само уведомление (повторяется), смахнули — смолкает; уведомление не пропадает от нажатия")
ok("AlarmTime.lateNote(due, now" in post and "+ late +" in post, "опоздавшее — «(должно было в 14:00)» в тексте уведомления")
ok("EXPIRE" in rcv and "fired + AlarmTime.RING_MS" in rcv and "AlarmActivity.silenceIfOpen(id)" in rcv and "RING_MS = 2 * 60000L" in rd("AlarmTime.java"),
   "через 2 минуты звук смолкает сам (сигналом AlarmManager — и у окна), уведомление остаётся тихим с кнопками")
ok("static void reopen(Context c)" in rcv and "AlarmReceiver.reopen(this)" in main.split("protected void onResume()", 1)[1][:400],
   "открыли приложение, пока звенит, — сразу окно со «Стоп»")
start = re.search(r"private void startSound\(\) \{.*?\n    \}\n", act, re.S).group(0)
ok("if (!resumed || !wantSound" in start and "resumed = true" in act and "startSound();" in act.split("protected void onResume()", 1)[1][:600],
   "окно звучит, только когда его видно (запущенное «за спиной» не играет музыку из ниоткуда)")
stop = re.search(r"protected void onStop\(\) \{.*?\n    \}\n", act, re.S).group(0)
ok("isInteractive()" in stop and "AlarmReceiver.handback(" in stop and "isChangingConfigurations()" in stop and "finish();" in stop,
   "окно ушло с экрана при включённом экране (разблокировали, «Домой») — звук уходит к уведомлению с кнопками, окно закрывается")
ok("open = new java.lang.ref.WeakReference<>(this);       // кнопки уведомления найдут окно" in act,
   "кнопки уведомления находят окно сразу (раньше — только после onResume: «Понял» не останавливал звук)")
ok("onNewIntent(Intent in)" in act and "recreate();" in act and "public void onBackPressed() { done(); }" in act,
   "второе напоминание при открытом окне — показывается; «Назад» — как «Стоп»")
ok("AlarmReceiver.stopped(this, id);" in act.split("private void done()", 1)[1][:200] and '"Отложить на 10 мин"' in act and 'button("Стоп"' in act,
   "окно: «Стоп» и «Отложить на 10 мин», закрытие снимает «звенит»")
ok("AlarmTime.lateNote(due, System.currentTimeMillis()" in act and "late.setText(" in act and 'getLongExtra("due", 0)' in act,
   "окно: строка «Должно было в …» у опоздавшего")
ok('"canUseFullScreenIntent"' in cmp and "SDK_INT < 34" in cmp and "USE_FULL_SCREEN_INTENT" in man
   and '"android.settings.MANAGE_APP_USE_FULL_SCREEN_INTENT"' in br and '"fullscreen".equals(what)' in br,
   "Android 14+: разрешение на окно поверх блокировки проверяется, кнопка ведёт на его экран")
ok("public String alarmHealth()" in br and '"autostart".equals(what)' in br and "com.miui.permcenter.autostart" in br
   and "com.transsion.phonemaster" in br and "huawei" in br,
   "мост: alarmHealth (что мешает) и «Автозапуск» у Xiaomi, Huawei/Honor, Tecno/Infinix, OPPO, vivo")

# ---------- 3. AlarmTime — настоящий код на обычной Java ----------
if shutil.which("javac") and shutil.which("java"):
    jd = Path(tempfile.mkdtemp())
    (jd / "pro/dewiar/app").mkdir(parents=True)
    shutil.copy(SRC / "AlarmTime.java", jd / "pro/dewiar/app/AlarmTime.java")
    (jd / "pro/dewiar/app/T.java").write_text("""package pro.dewiar.app;
import java.util.TimeZone;
public class T { public static void main(String[] a) throws Exception {
  String op = a[0];
  if (op.equals("late")) { TimeZone z = TimeZone.getTimeZone(a[3]); System.out.println("[" + AlarmTime.lateNote(Long.parseLong(a[1]), Long.parseLong(a[2]), z) + "]"); }
  if (op.equals("missed")) System.out.println(AlarmTime.missed(Long.parseLong(a[1]), Long.parseLong(a[2])));
  if (op.equals("wall")) System.out.println(AlarmTime.wall(Long.parseLong(a[1]), TimeZone.getTimeZone(a[2])));
  if (op.equals("moved")) System.out.println(AlarmTime.moved(Long.parseLong(a[1]), a[2], a[3], a[4], a[5], TimeZone.getTimeZone(a[6])));
} }""", encoding="utf-8")
    r = subprocess.run(["javac", "-encoding", "UTF-8", "-d", str(jd), str(jd / "pro/dewiar/app/AlarmTime.java"), str(jd / "pro/dewiar/app/T.java")],
                       capture_output=True, text=True)
    ok(r.returncode == 0, f"AlarmTime компилируется отдельно от Android: {r.stderr[:200]}")

    def j(*a):
        return subprocess.run(["java", "-Dfile.encoding=UTF-8", "-cp", str(jd), "pro.dewiar.app.T", *map(str, a)], capture_output=True, text=True,
                              encoding="utf-8").stdout.strip()
    from datetime import datetime
    from zoneinfo import ZoneInfo
    M = ZoneInfo("Europe/Moscow")
    ms = lambda *d, tz=M: int(datetime(*d, tzinfo=tz).timestamp() * 1000)
    due = ms(2026, 11, 11, 14, 0)
    ok(j("late", due, due + 60000, "Europe/Moscow") == "[]", "опоздание меньше 2 минут — без приписки")
    ok(j("late", due, due + 63 * 60000, "Europe/Moscow") == "[ (должно было в 14:00)]", f"на час позже — «(должно было в 14:00)»: {j('late', due, due + 63 * 60000, 'Europe/Moscow')}")
    ok(j("late", ms(2026, 11, 10, 23, 30), ms(2026, 11, 11, 7, 5), "Europe/Moscow") == "[ (должно было вчера в 23:30)]", "вчерашнее — «вчера в 23:30»")
    ok(j("late", ms(2026, 11, 8, 9, 0), ms(2026, 11, 11, 9, 0), "Europe/Moscow") == "[ (должно было 08.11 в 09:00)]", "раньше — с датой")
    pol = [j("missed", due, due + int(d * 60000)) for d in (0.5, 10, 45, 23 * 60, 25 * 60)]
    ok(pol == ["0", "1", "2", "2", "3"], f"пропущенное: до минуты — как обычно, до получаса — звонит, до суток — тихо, старше — в журнал: {pol}")
    seven = ms(2026, 11, 12, 7, 0)
    wall = j("wall", seven, "Europe/Moscow")
    ok(wall == "2026-11-12 07:00:00", f"стенное время будильника запоминается: {wall}")
    nsk = int(j("moved", seven, "alarm", "", "Europe/Moscow", wall, "Asia/Novosibirsk"))
    ok(datetime.fromtimestamp(nsk / 1000, ZoneInfo("Asia/Novosibirsk")).strftime("%H:%M") == "07:00" and nsk != seven,
       "перелёт Москва → Новосибирск: будильник «в 7» звонит в 7 по местному, а не в 11")
    ok(int(j("moved", seven, "reminder", "daily", "Europe/Moscow", wall, "Asia/Novosibirsk")) == nsk, "повторяющееся напоминание — тоже по часам на стене")
    ok(int(j("moved", seven, "reminder", "", "Europe/Moscow", wall, "Asia/Novosibirsk")) == seven
       and int(j("moved", seven, "timer", "", "Europe/Moscow", wall, "Asia/Novosibirsk")) == seven,
       "разовое напоминание и таймер остаются в том же мгновении (созвон в 14:00 по Москве)")
    ok(int(j("moved", seven, "alarm", "", "Europe/Moscow", wall, "Europe/Moscow")) == seven, "пояс тот же — время не трогаем")
    ber = ZoneInfo("Europe/Berlin")
    b7 = ms(2027, 3, 27, 7, 0, tz=ber)                      # суббота перед переходом на летнее время
    bw = j("wall", b7, "Europe/Berlin")
    sun = int(j("moved", b7 + 86400000, "alarm", "", "UTC", bw.replace("27 ", "28 "), "Europe/Berlin"))
    ok(datetime.fromtimestamp(sun / 1000, ber).strftime("%d %H:%M") == "28 07:00", "перевод часов: «в 7» остаётся в 7 (а не в 8)")
else:
    print("нет javac — AlarmTime пропускаю")

# ---------- 4. сборка без ключа подписи ----------
if Path("/usr/lib/android-sdk/build-tools/debian/aapt2").exists() and shutil.which("javac") and shutil.which("dalvik-exchange"):
    r = subprocess.run(["bash", str(ROOT / "android/tools/build_apk.sh"), "--check"], capture_output=True, text=True, timeout=600,
                       env=dict(os.environ, DEWIAR_KEYSTORE="/nonexistent/none.jks", DEWIAR_KEYPASS=""))
    ok(r.returncode == 0 and "сборка проходит" in r.stdout, f"APK собирается (ресурсы, манифест, Java, dex) без ключа: {(r.stdout + r.stderr)[-400:]}")
else:
    print("нет инструментов сборки Android — сборку пропускаю")

# ---------- 5. интерфейс: «Напоминания вовремя» ----------
js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("remHealthCard()" in js and "remHealthBrief()" in js and "remLateWatch(true)" in js and "alarms: remHealth() || undefined" in js,
   "app.js: карточка в «Звуке напоминаний», коротко — в «Дне», после опоздания — на главном, состояние — в отчёте")
from playwright.sync_api import sync_playwright
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
for f in ("skins.css", "skins.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/skins", www / "skins", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
import time
now = int(time.time() * 1000)
BAD = {"exact": False, "fullscreen": False, "notify": True, "battery": False, "sdk": 35, "maker": "xiaomi", "mode": "inexact",
       "late": [{"due": now - 3 * 3600e3, "late": 47 * 60000, "kind": "reminder", "how": "", "mode": "inexact", "time": now - 3 * 3600e3 + 47 * 60000}]}
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 393, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("openSettings('sound')"); pg.wait_for_timeout(300)
    good = pg.evaluate("() => [$('#rem-health .rmst').className, $('#rem-health').textContent, $$('#rem-health [data-remfix]').length]")
    ok("ok" in good[0] and "придут вовремя" in good[1] and "«Стоп»" in good[1], f"всё разрешено — «Напоминания придут вовремя», и как остановить: {good[0]}")
    pg.evaluate(f"window._remHealth = {json.dumps(BAD)}; window._os = []; D.openSettings = (k) => (window._os.push(k), true); window._bat = 0; D.askBattery = () => window._bat++;"
                "closeSheets(); openSettings('menu')")
    pg.wait_for_timeout(300)
    menu = pg.evaluate("() => { const r = $('.setrow[data-st=sound] small'); return [r.textContent, r.className]; }")
    ok(menu == ["напоминания могут опаздывать", "warn"], f"меню настроек: «Звук напоминаний» — предупреждение: {menu}")
    pg.evaluate("setTab = 'sound'; renderSettings()"); pg.wait_for_timeout(300)
    bad = pg.evaluate("() => [$('#rem-health .rmst').className, $('#rem-health .rmst').textContent, $$('#rem-health .rmiss').map(x => x.textContent.trim()),"
                      " $$('#rem-health [data-remfix]').map(x => x.dataset.remfix), $('#rem-health .rmbrand').open, $('#rem-health .rmbrand').textContent]")
    ok("bad" in bad[0] and "47 мин" in bad[1], f"опоздания за две недели — сколько и насколько: {bad[1][:120]}")
    ok(len(bad[2]) == 3 and "Точное время" in bad[2][0] and "поверх блокировки" in bad[2][1] and "батарею" in bad[2][2],
       f"что мешает — по пунктам, важное первым: {[x[:30] for x in bad[2]]}")
    ok(bad[3] == ["exact", "fullscreen", "battery", "autostart", "app"] and bad[4] and "Xiaomi" in bad[5] and "Автозапуск" in bad[5]
       and "Контроль активности" in bad[5] and "Экран блокировки" in bad[5], f"Xiaomi: шаги с подписями как на экране и кнопки: {bad[3]}")
    if SHOTS:
        pg.screenshot(path=str(Path(SHOTS) / "phone-rem-health-neusky.png"), full_page=True)
    for k in ("exact", "fullscreen", "autostart"):
        pg.click(f"#rem-health [data-remfix={k}]"); pg.wait_for_timeout(80)
    pg.click("#rem-health [data-remfix=battery]"); pg.wait_for_timeout(80)
    ok(pg.evaluate("window._os") == ["alarms", "fullscreen", "autostart"] and pg.evaluate("window._bat") == 1,
       f"кнопки открывают нужные экраны Android: {pg.evaluate('window._os')}")
    pg.click("#rem-try"); pg.wait_for_timeout(150)
    tr = pg.evaluate("() => [JSON.parse(D.alarms()).filter(x => /Проверка напоминания/.test(x.title)).map(x => Math.round((x.at - Date.now()) / 1000)), $('#rem-res').textContent]")
    ok(len(tr[0]) == 1 and 50 <= tr[0][0] <= 61 and "«Стоп»" in tr[1], f"«Проверить» — напоминание через минуту: {tr}")
    for skin in ("neudusk", "neusky"):
        pg.evaluate(f"S.skin = '{skin}'; applyLook(); renderSettings()"); pg.wait_for_timeout(250)
        col = pg.evaluate("() => { const s = getComputedStyle($('#rem-health')), t = getComputedStyle($('#rem-health .rmst b')); return [s.backgroundColor, t.color]; }")
        ok(col[0] != col[1], f"тема {skin}: текст читается на фоне карточки: {col}")
        if SHOTS:
            pg.screenshot(path=str(Path(SHOTS) / f"phone-rem-health-{skin}.png"), full_page=True)
    pg.evaluate("closeSheets(); openSheet('#sh-day'); renderDay()"); pg.wait_for_timeout(300)
    day = pg.evaluate("() => { const c = $('.rembrief'); return c ? [c.textContent, !!c.querySelector('button')] : null; }")
    ok(day and "могут опаздывать" in day[0] and "Точное время" in day[0] and day[1], f"«День»: коротко, что мешает, и «Как исправить»: {day}")
    pg.evaluate("closeSheets(); showCard(''); S.remLateSeen = 0; remLateWatch(false)"); pg.wait_for_timeout(200)
    card = pg.evaluate("() => $('#card .remlate') && $('#card .remlate').textContent")
    ok(card and "47 мин" in card and "Исправить" in card, f"после опоздания — один раз на главном экране: {card and card[:90]}")
    pg.evaluate("showCard(''); remLateWatch(false)"); pg.wait_for_timeout(100)
    ok(not pg.evaluate("!!$('#card .remlate')"), "тот же случай второй раз не показывается")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
# рецензия 0.87: QUICKBOOT система не защищает — чужое приложение могло дёргать перестановку; верим лишь сразу после включения
ok('a.endsWith("QUICKBOOT_POWERON") && android.os.SystemClock.elapsedRealtime() > 10 * 60_000L) return;' in boot,
   "QUICKBOOT принимается только в первые 10 минут после включения телефона")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
