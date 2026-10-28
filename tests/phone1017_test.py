"""Телефон, отзывы и экзамен 17.10:
- «Напоминания нужно сделать редактируемыми по клику руками — сейчас только голосом»: нажали на напоминание в «Мой день» —
  правка текста, даты, времени и повтора; «Сохранить» — то же напоминание (тот же id); «Удалить»;
- «В окне „Сообщить о проблеме“ непонятно, как добавить фото»: кнопка «Добавить фото или скриншот», фото уходит с
  жалобой; со снимком экрана — обе картинки одной;
- экзамен телефона 0.6.54: ответ целиком «[Действие: calendar_list]» — теперь это вызов функции, а не текст человеку;
- на грубость — граница всегда, своей фразой, и помощь по просьбе;
- «Записывать не нужно» вместо «Не записано» — модель больше не говорит «система не дала сохранить»."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from playwright.sync_api import sync_playwright  # noqa: E402
from PIL import Image  # noqa: E402
tmp = Path(tempfile.mkdtemp())
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
Image.new("RGB", (300, 600), (40, 120, 200)).save(tmp / "shot.png")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)

    # ---------- правка напоминания руками ----------
    pg.evaluate("""() => { S.onboarded = true; const at = new Date(Date.now() + 2 * 864e5); at.setHours(11, 0, 0, 0);
        window._x = addAlarm("Пора попить горячего чая", at, "reminder", ""); openSheet("#sh-day"); dayTab = "rem"; renderDay(); }""")
    pg.wait_for_timeout(300)
    pg.click(f".it[data-edit] .bd"); pg.wait_for_timeout(300)
    shown = pg.evaluate("() => [$('#sh-rem').classList.contains('on'), $('#rm-text').value, $('#rm-time').value]")
    ok(shown == [True, "Пора попить горячего чая", "11:00"], f"нажали на напоминание — окно правки с текстом и временем: {shown}")
    pg.fill("#rm-text", "Пора пить горячий чай с лимоном"); pg.fill("#rm-time", "11:30"); pg.select_option("#rm-rep", "weekdays")
    pg.click("#rm-save"); pg.wait_for_timeout(300)
    r = pg.evaluate("() => { const l = JSON.parse(D.alarms()); const x = l.find(a => a.id === _x.id); const d = new Date(x.at); return [l.length, x.title, d.getHours() + ':' + d.getMinutes(), x.repeat, $('#sh-day').classList.contains('on')]; }")
    ok(r[:4] == [1, "Пора пить горячий чай с лимоном", "11:30", "weekdays"] and r[4], f"«Сохранить» — то же напоминание с новым текстом, временем и повтором, назад к списку: {r}")
    pg.click(f".it[data-edit] .bd"); pg.wait_for_timeout(200)
    pg.fill("#rm-date", "2020-01-01"); pg.select_option("#rm-rep", ""); pg.click("#rm-save"); pg.wait_for_timeout(200)
    ok("уже прошло" in pg.inner_text("#rm-res"), "прошедшее время без повтора — понятная подсказка, а не напоминание в прошлом")
    pg.click("#rm-del"); pg.wait_for_timeout(200)
    ok(pg.evaluate("() => JSON.parse(D.alarms()).length") == 0, "«Удалить» — напоминания нет")

    # ---------- фото к жалобе ----------
    pg.evaluate("() => { bugSnap = null; openSettings('bug'); }"); pg.wait_for_timeout(400)
    has = pg.evaluate("() => !!document.querySelector('#bug-file') && document.querySelector('#bug-pickbox').textContent.includes('Добавить фото или скриншот')")
    ok(has, "в «Сообщить о проблеме» — понятная кнопка «Добавить фото или скриншот»")
    pg.set_input_files("#bug-file", str(tmp / "shot.png")); pg.wait_for_timeout(600)
    ok(pg.evaluate("() => !!document.querySelector('#bug-pickimg') && bugPick.startsWith('data:image/jpeg')"), "выбрали фото — оно видно в форме")
    sent = pg.evaluate("""async () => { window._sent = null; window.reportSend = async (note, a, via, o) => { _sent = o; return { id: 7, secret: 's', base: 'x' }; };
        const d = await complaintSend('Не видно кнопку', '', false, 'кнопкой'); return [d.id, (_sent.shot || '').slice(0, 22), bugPick]; }""")
    ok(sent[0] == 7 and sent[1] == "data:image/jpeg;base64" and sent[2] == "", f"жалоба уходит с фото, после отправки фото снято: {sent[:2]}")
    both = pg.evaluate("""async () => { const c = document.createElement('canvas'); c.width = 200; c.height = 400; bugSnap = { ts: Date.now(), b64: c.toDataURL('image/jpeg').split(',')[1] };
        bugPick = c.toDataURL('image/jpeg'); await complaintSend('Две картинки', '', true, 'кнопкой');
        const im = new Image(); await new Promise(r => { im.onload = r; im.src = _sent.shot; }); return [im.width > im.height, bugSnap === null]; }""")
    ok(both == [True, True], f"фото и снимок экрана — одной картинкой рядом: {both}")

    # ---------- «[Действие: calendar_list]» — вызов, а не текст ----------
    c = pg.evaluate("() => [bareCalls('[Действие: calendar_list]', new Set(['calendar_list'])), bareCalls('[Действие: launch_rocket]', new Set(['calendar_list'])), bareCalls('[Action: weather {\"city\": \"Минск\"}]', new Set(['weather']))]")
    ok(c[0] == [{"name": "calendar_list", "args": {}}] and c[1] == [] and c[2] == [{"name": "weather", "args": {"city": "Минск"}}],
       f"ответ «[Действие: calendar_list]» — вызов функции (незнакомая — нет): {c}")
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
    b.close()

app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok('sink.push("Мне неприятно, когда со мной так разговаривают, но помогу. ")' in app, "грубость — граница своей фразой всегда, модель только помогает")
eng = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("Записывать не нужно" in app and "Записывать не нужно" in eng and "Не записано: пользователь" not in app + eng,
   "save_note без просьбы — «Записывать не нужно… это не ошибка», а не «Не записано» (модель говорила «система не дала»)")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
