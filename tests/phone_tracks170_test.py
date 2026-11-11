"""Идея №170 (09.11): «на телефоне — переключать треки в проигрывателе». Радио над Лирой: ⏮ «предыдущая» (та, что играла до
этой) и ⏭ «следующая», голосом — «назад», «предыдущая станция», модели — radio_control prev. Плеер другого приложения
(Яндекс Музыка, Spotify): «следующий трек», «предыдущая песня», «пауза» — медиа-клавишей, когда наше радио молчит и
в телефоне играет музыка (или прямо сказали «трек»); модели — media_control. В браузере (веб-версия) — только радио."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = os.environ.get("DEWIAR_SHOTS", "")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
radio = json.loads((ROOT / "data/radio.json").read_text(encoding="utf-8"))
(www / "radio.js").write_text("window.RADIO_LIST = " + json.dumps(radio, ensure_ascii=False) + ";", encoding="utf-8")
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 393, "height": 852}, device_scale_factor=2); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("https://**", lambda r: r.abort())
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        names = pg.evaluate("""async () => { const out = [];
            let r = await radio.play("*"); out.push(r.station && r.station.name);
            r = await radio.next(); out.push(r.station && r.station.name);
            r = await radio.next(); out.push(r.station && r.station.name);
            return out; }""")
        ok(all(names) and len(set(names)) == 3, f"три станции подряд: {names}")
        r = pg.evaluate("async () => { const r = await radio.prev(); return r.station && r.station.name; }")
        ok(r == names[1], f"⏮ «предыдущая» — та, что играла до этой: {r}")
        r = pg.evaluate("async () => { const r = await radio.prev(); return r.station && r.station.name; }")
        ok(r == names[0], f"ещё раз — ещё на одну назад: {r}")
        pg.wait_for_timeout(200)
        ok(pg.is_visible("#r-prev") and pg.is_visible("#r-next") and pg.is_visible("#r-pp"), "у радио над Лирой — ⏮ ⏯ ⏭")
        cur = pg.evaluate("radio.state().name")
        pg.click("#r-next"); pg.wait_for_timeout(400)
        after = pg.evaluate("radio.state().name")
        ok(after != cur, f"⏭ — другая станция: {cur} → {after}")
        pg.click("#r-prev"); pg.wait_for_timeout(400)
        ok(pg.evaluate("radio.state().name") == cur, "⏮ — вернулась прежняя")
        if SHOTS:
            for skin in ("light", "dark"):
                pg.evaluate(f"document.body.classList.toggle('light', {str(skin == 'light').lower()})"); pg.wait_for_timeout(200)
                pg.locator("#radiobox").screenshot(path=f"{SHOTS}/phone_radio_{skin}.png")
        pg.click("#r-next"); pg.wait_for_timeout(400)
        q = pg.evaluate("async () => { const before = radio.state().name; const r = await radioQuick('предыдущая станция'); return [before, r && r.say, radio.state().name]; }")
        ok(q[1] and "Играет" in q[1] and q[2] != q[0], f"голосом «предыдущая станция»: {q}")
        t = pg.evaluate("async () => { await radio.next(); return await runTool('radio_control', { action: 'prev' }); }")
        ok(str(t).startswith("Играет"), f"модели — radio_control prev: {t}")
        # плеер другого приложения
        pg.evaluate("radio.stop()"); pg.wait_for_timeout(150)
        m = pg.evaluate("""async () => { window._media = []; window._musicOn = true;
            const a = await radioQuick('следующий трек'), b = await radioQuick('назад'), c = await radioQuick('пауза');
            window._musicOn = false; const d = await radioQuick('дальше'); radio.stop(); await new Promise(r => setTimeout(r, 50)); const e = await radioQuick('следующая песня');
            return { a: a && a.say, b: b && b.say, c: c && c.say, d: d && d.say, media: window._media.slice() }; }""")
        ok(m["media"][:3] == ["next", "prev", "pause"] and m["a"] == "Следующий трек.", f"Яндекс Музыка играет: «следующий трек», «назад», «пауза» — медиа-клавишей: {m}")
        ok(m["media"][3:] == ["next"], f"музыка не играет: «дальше» — не чужой плеер (наше радио), «следующая песня» — нажимаем: {m['media']}")
        t = pg.evaluate("async () => { window._media = []; window._musicOn = true; const r = await runTool('media_control', { action: 'prev' }); return [r, window._media.slice()]; }")
        ok(t[1] == ["prev"] and "предыдущий трек" in t[0], f"модели — media_control: {t}")
        ok(pg.evaluate("toolSpecs().some(x => x.name === 'media_control')"), "media_control есть в действиях телефона")
        pg.evaluate("D.web = true")
        ok(not pg.evaluate("toolSpecs().some(x => x.name === 'media_control')") and pg.evaluate("mediaQuick('следующий трек')") is None,
           "веб-версия: чужими приложениями не управляем — только радио")
        pg.evaluate("D.web = false")
        ok(not errs, f"без ошибок: {errs[:2]}")
        b.close()
    wb = (ROOT / "android/web/webbridge.js").read_text(encoding="utf-8")
    jv = (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8")
    ok("mediaKey:" in wb and "musicActive:" in wb and "public String mediaKey" in jv and "public boolean musicActive" in jv,
       "мост: mediaKey и musicActive — и в Java, и в браузере")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
