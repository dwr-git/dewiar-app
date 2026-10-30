"""Напоминания по дням недели на телефоне (30.10, владелец: «просил по будням, кроме пятницы — поставила и на пятницу…
это супер важно»). На компьютере сделано в 0.71; телефон такой повтор не понимал: из синхронизации — «звонит раз и ждёт
следующий срок от компьютера» (выключен компьютер — тишина), голосом — ставил «по будням».
Теперь: строка повтора «d:0123» (понедельник = 0, как на компьютере); фразы «по будням, кроме пятницы», «с понедельника
по четверг», «пн-чт», «по понедельникам и средам», «по выходным»; «кроме» не путается со словами («кроме всего»);
следующий раз считает и Alarms.java (приложение закрыто); синхронизация туда и обратно; модель передала repeat: weekdays —
дни берутся из слов человека; в правке — «по дням недели…» кнопками."""
import json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- Alarms.next (Java): компилируем настоящий метод с маленькой заменой org.json ----------
if shutil.which("javac") and shutil.which("java"):
    src = (ROOT / "android/src/pro/dewiar/app/Alarms.java").read_text(encoding="utf-8")
    meth = re.search(r"    static long next\(JSONObject x\) throws Exception \{.*?\n    \}\n", src, re.S).group(0)
    jd = Path(tempfile.mkdtemp()); (jd / "org/json").mkdir(parents=True)
    (jd / "org/json/JSONObject.java").write_text("""package org.json;
public class JSONObject { long at; String rep; public JSONObject(long a, String r) { at = a; rep = r; }
  public long getLong(String k) { return at; } public String optString(String k) { return rep; } }""")
    (jd / "T.java").write_text("import org.json.JSONObject;\npublic class T {\n" + meth + """
  public static void main(String[] a) throws Exception { java.util.TimeZone.setDefault(java.util.TimeZone.getTimeZone("Europe/Minsk"));
    long t = Long.parseLong(a[0]); for (int i = 0; i < 6; i++) { t = next(new JSONObject(t, a[1])); System.out.println(t); } } }""")
    r = subprocess.run(["javac", "-d", str(jd), str(jd / "org/json/JSONObject.java"), str(jd / "T.java")], capture_output=True, text=True)
    ok(r.returncode == 0, f"Alarms.next компилируется: {r.stderr[:200]}")

    def jnext(start, rep):
        out = subprocess.run(["java", "-cp", str(jd), "T", str(int(start.timestamp() * 1000)), rep], capture_output=True, text=True).stdout.split()
        return [datetime.fromtimestamp(int(x) / 1000) for x in out]
    os.environ["TZ"] = "Europe/Minsk"
    import time; time.tzset()
    mon = datetime(2026, 11, 2, 17, 50)                           # понедельник
    seq = jnext(mon, "d:0123")
    ok([d.weekday() for d in seq] == [1, 2, 3, 0, 1, 2] and all((d.hour, d.minute) == (17, 50) for d in seq),
       f"«пн–чт»: после понедельника — вт, ср, чт, затем снова пн; пятницы нет; время то же: {[d.strftime('%a %H:%M') for d in seq]}")
    fri = jnext(datetime(2026, 11, 6, 16, 40), "weekly")
    ok([d.weekday() for d in fri[:2]] == [4, 4] and (fri[0] - datetime(2026, 11, 6, 16, 40)).days == 7, "раз в неделю — как было")
    wd = jnext(datetime(2026, 11, 6, 7, 0), "weekdays")
    ok([d.weekday() for d in wd[:2]] == [0, 1], "будни — как было (после пятницы — понедельник)")
    sa = jnext(datetime(2026, 11, 7, 10, 0), "d:56")
    ok([d.weekday() for d in sa[:3]] == [6, 5, 6], f"по выходным: {[d.weekday() for d in sa[:3]]}")
    dst = jnext(datetime(2027, 3, 25, 7, 0), "d:024")             # переход на летнее время (в Минске его нет, но проверим, что не съезжает)
    ok(all((d.hour, d.minute) == (7, 0) for d in dst), "время звонка не съезжает")
else:
    print("нет javac — Alarms.next пропускаю")

# ---------- app.js ----------
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
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 400, "height": 820}, timezone_id="Europe/Minsk")
    pg = ctx.new_page(); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    # фразы (сейчас — пятница 30.10 12:00)
    NOW = "new Date(2026, 9, 30, 12, 0)"
    def pw(t):
        again = t.startswith("напоминай ")                     # как quick(): слово «напоминай» снято, остаток — в parseWhen
        if again:
            t = t[len("напоминай "):]
        return pg.evaluate(f"""() => {{ const w = parseWhen({json.dumps(t)}, {NOW}, {json.dumps(again)}); return w && {{ rep: w.repeat, day: (w.at.getDay() + 6) % 7, h: w.at.getHours(), mi: w.at.getMinutes(), rest: remindWhat(w.rest), ru: repRu(w.repeat) }}; }}""")
    cases = [
        ("напоминай по будням, кроме пятницы, в 17:50 пора выключать компьютер", "d:0123", "по будням, кроме пятницы", "пора выключать компьютер"),
        ("напоминай с понедельника по четверг в 17:50 пора выключать компьютер", "d:0123", "по будням, кроме пятницы", "пора выключать компьютер"),
        ("напоминай пн-чт в 17:50 выключить компьютер", "d:0123", "по будням, кроме пятницы", "выключить компьютер"),
        ("напоминай по понедельникам и средам в 9 тренировка", "d:02", "по понедельникам и средам", "тренировка"),
        ("напоминай по выходным в 10 полить цветы", "d:56", "по выходным", "полить цветы"),
        ("напоминай кроме пятницы в 9 полить цветы", "d:012356", "каждый день, кроме пятницы", "полить цветы"),
        ("напоминай каждый день, но не в среду, в 8 витамины", "d:013456", "каждый день, кроме среды", "витамины"),
        ("напоминай по будням в 7 зарядка", "weekdays", "по будням", "зарядка"),
        ("напоминай по пятницам в 16:40 пора выключать компьютер", "weekly", "каждую неделю", "пора выключать компьютер"),
        ("напоминай со вторника по субботу в 8 открыть магазин", "d:12345", "со вторника по субботу", "открыть магазин"),
    ]
    for t, rp, ru, what in cases:
        w = pw(t)
        ok(w and w["rep"] == rp and (not ru or w["ru"] == ru) and w["rest"] == what, f"«{t}» → {rp} «{w and w['ru']}», о чём: «{w and w['rest']}»")
    w = pw("напоминай по будням, кроме пятницы, в 17:50 пора выключать компьютер")
    ok(w["day"] == 0 and (w["h"], w["mi"]) == (17, 50), f"сказано в пятницу — первый раз в понедельник 17:50: {w}")
    w = pw("напомни завтра в 9 купить всё, кроме хлеба")
    ok(w["rep"] == "" and "кроме хлеба" in w["rest"], f"«кроме хлеба» без дней — не повтор: {w}")
    w = pw("каждый день в 9 кроме всего прочего пить воду")
    ok(w["rep"] == "daily", f"«кроме всего» — не воскресенье: {w}")
    ok(pg.evaluate("repRu('d:024')") == "по понедельникам, средам и пятницам" and pg.evaluate("repRu('d:12345')") == "со вторника по субботу",
       f"названия: {pg.evaluate('repRu(\"d:024\")')} / {pg.evaluate('repRu(\"d:12345\")')}")
    # синхронизация с компьютером
    r = pg.evaluate("""() => [repFromDict({ kind: 'weekly', days: [0, 1, 2, 3], time: '17:50' }), repFromDict({ kind: 'weekly', days: [0, 1, 2, 3, 4] }),
      repFromDict({ kind: 'weekly', days: [4] }), repFromDict({ kind: 'daily' }), JSON.stringify(repToDict('d:0123', new Date(2026, 10, 2, 17, 50).getTime()))]""")
    ok(r[:4] == ["d:0123", "weekdays", "weekly", "daily"] and json.loads(r[4]) == {"kind": "weekly", "days": [0, 1, 2, 3], "time": "17:50"},
       f"с компьютера «пн–чт» — d:0123 (а не «звонок один раз»), обратно — те же дни: {r}")
    # инструмент: модель передала repeat: weekdays, а человек сказал «кроме пятницы»
    r = pg.evaluate("""async () => { turnAsk = 'напоминай по будням, кроме пятницы, в 17:50 пора выключать компьютер';
      const t = await runTool('set_reminder', { text: 'Пора выключать компьютер', when: 'по будням в 17:50', repeat: 'weekdays' });
      const l = JSON.parse(D.alarms() || '[]'); const x = l.find(y => y.title === 'Пора выключать компьютер'); return [t, x.repeat, new Date(x.at).getDay()]; }""")
    ok(r[1] == "d:0123" and r[2] != 5 and "кроме пятницы" in r[0], f"модель дала weekdays — берём «кроме пятницы» из слов человека: {r}")
    # правка руками
    rid = pg.evaluate("JSON.parse(D.alarms()).find(y => y.title === 'Пора выключать компьютер').id")
    pg.evaluate(f"remEdit('{rid}')"); pg.wait_for_timeout(300)
    ok(pg.input_value("#rm-rep") == "d" and pg.is_visible("#rm-days") and pg.evaluate("[...document.querySelectorAll('#rm-days .rmd.on')].map(b => +b.dataset.d)") == [0, 1, 2, 3],
       "правка: «по дням недели…», включены пн–чт")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "phone-remind-days.png"))
    pg.click("#rm-days .rmd[data-d='2']"); pg.click("#rm-save"); pg.wait_for_timeout(300)
    ok(pg.evaluate(f"JSON.parse(D.alarms()).find(y => y.id === '{rid}').repeat") == "d:013", "сняли среду — d:013")
    pg.evaluate(f"remEdit('{rid}')"); pg.wait_for_timeout(200)
    pg.select_option("#rm-rep", "weekdays"); pg.wait_for_timeout(100)
    ok(pg.is_hidden("#rm-days"), "«по будням» — кнопки дней спрятаны")
    pg.select_option("#rm-rep", "d"); pg.evaluate("document.querySelectorAll('#rm-days .rmd.on').forEach(b => b.click())"); pg.click("#rm-save"); pg.wait_for_timeout(200)
    ok("хотя бы один день" in pg.inner_text("#rm-res"), "ни одного дня — подсказка, не сохраняем")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
