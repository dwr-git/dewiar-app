"""Телефон, «Близкие»: файл в переписку (30.10, Валера: «прикрепил фото, но вижу — не отправилось»; «PNG непонятно,
загрузились или нет»). Большое фото сжимается до 2560 px JPEG (снимок 8 МБ в base64 — запрос ~11 МБ, сайт его не примет);
отправка с файлом — сразу пузырь «Отправляю…» с именем файла; не ушло — файлы и текст возвращаются в поле, понятная причина;
картинка узнаётся и по image/x-png, image/pjpeg."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "closecrypto.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/skins", www / "skins", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    ok(pg.evaluate("[clIsImg({ type: 'image/x-png', name: 'a' }), clIsImg({ type: 'image/pjpeg', name: 'b' }), clIsImg({ type: '', name: 'c.PNG' }), clIsImg({ type: 'application/pdf', name: 'd.pdf' })]")
       == [True, True, True, False], "картинка — и по image/x-png, image/pjpeg, и по имени; PDF — не картинка")
    big = pg.evaluate("""async () => { const c = document.createElement('canvas'); c.width = 4000; c.height = 3000; const x = c.getContext('2d');
        for (let i = 0; i < 4000; i += 7) { x.fillStyle = `hsl(${i % 360},70%,${30 + (i * 13) % 50}%)`; x.fillRect(i, 0, 7, 3000); }
        for (let j = 0; j < 3000; j += 5) { x.fillStyle = `rgba(${j % 255},${(j * 7) % 255},90,.35)`; x.fillRect(0, j, 4000, 3); }
        const blob = await new Promise(r => c.toBlob(r, 'image/png')); const f = new File([blob], 'IMG_2024.png', { type: 'image/png' });
        clFiles = []; await new Promise(r => clFileTake(f, r)); return [f.size, clFiles.map(x => [x.name, x.type, x.bytes.length])]; }""")
    ok(big[0] > 1.5e6 and big[1] and big[1][0][0] == "IMG_2024.jpg" and big[1][0][1] == "image/jpeg" and big[1][0][2] < big[0],
       f"большое фото ({big[0] // 1024} КБ) — сжато в JPEG: {big[1]}")
    r = pg.evaluate("""async () => { const st = clLoad(); st.people = [{ pid: 'p1', name: 'Валера', devs: [] }]; clSave();
        clFiles = [{ name: 'фото.jpg', type: 'image/jpeg', bytes: new Uint8Array([1, 2, 3]) }];
        const t = document.createElement('textarea'); t.id = 'cl-text'; document.body.appendChild(t);
        let mid = null;
        window.clSend = async () => { const h = clLoad().hist.p1 || []; mid = h.length ? [h[h.length - 1].pend, (h[h.length - 1].f || []).map(f => f.name)] : null;
          throw new Error('облако ответило 413'); };
        await clSendFiles('p1', 'смотри');
        return [mid, (clLoad().hist.p1 || []).length, clFiles.map(f => f.name), t.value]; }""")
    ok(r[0] == [True, ["фото.jpg"]], f"с файлом — сразу пузырь «Отправляю…» с именем файла: {r[0]}")
    ok(r[1] == 0 and r[2] == ["фото.jpg"] and r[3] == "смотри", f"не ушло — пузырь убран, файл и текст вернулись в поле: {r[1:]}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
