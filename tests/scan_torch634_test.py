"""№634 (телефон 0.9.26, 09.11): «в тёмном помещении сканер QR запущен, но нет кнопки включить фонарик — или пусть Лира
сама включает фонарик». Теперь у сканера (ui/assets/codes.js — общий для телефона и компьютера) кнопка фонарика, если камера
его умеет; в темноте (~1,5 с) фонарик включается сам; закрыли сканер — камера и фонарик выключены."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = """(o) => { window._torch = []; window._stopped = 0;
  if (!navigator.mediaDevices) Object.defineProperty(navigator, 'mediaDevices', { value: {} });
  navigator.mediaDevices.getUserMedia = async () => {
    const c = document.createElement('canvas'); c.width = 640; c.height = 480; const g = c.getContext('2d');
    const paint = () => { g.fillStyle = o.dark ? '#0b0b0d' : '#c8c8c8'; g.fillRect(0, 0, 640, 480); };
    paint(); setInterval(paint, 50);
    const st = c.captureStream(15), tr = st.getVideoTracks()[0];
    tr.getCapabilities = () => (o.torch ? { torch: true } : {});
    tr.applyConstraints = async (k) => { _torch.push(!!(k.advanced && k.advanced[0].torch)); };
    const stop = tr.stop.bind(tr); tr.stop = () => { _stopped++; stop(); };
    return st; }; }"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for case in ({"torch": True, "dark": True}, {"torch": True, "dark": False}, {"torch": False, "dark": True}):
        pg = b.new_page(viewport={"width": 412, "height": 860}); pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.set_content("<html><body></body></html>")
        pg.add_script_tag(path=str(ROOT / "ui/assets/vendor/zxing.min.js")); pg.add_script_tag(path=str(ROOT / "ui/assets/codes.js"))
        pg.evaluate(FAKE, case)
        pg.evaluate("() => { window._close = DewiarCodes.scan({ onResult: () => {}, onError: (m) => { window._err = m; } }); }")
        pg.wait_for_timeout(2600)
        r = pg.evaluate("() => { const t = document.querySelector('.dwq .tl'); return { shown: !!t && !t.hidden, on: !!t && t.classList.contains('on'), torch: _torch.slice() }; }")
        name = ("фонарик есть" if case["torch"] else "фонарика нет") + (", темно" if case["dark"] else ", светло")
        if case["torch"] and case["dark"]:
            ok(r["shown"] and r["on"] and r["torch"] == [True], f"{name}: кнопка есть, фонарик включился сам: {r}")
            if os.environ.get("DEWIAR_SHOTS"):
                pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "scan-torch634.png"))
            pg.click(".dwq .tl"); pg.wait_for_timeout(200)
            r2 = pg.evaluate("() => [document.querySelector('.dwq .tl').classList.contains('on'), _torch.slice()]")
            ok(r2 == [False, [True, False]], f"{name}: нажали — выключился и сам больше не включается: {r2}")
            pg.wait_for_timeout(1500)
            ok(pg.evaluate("_torch.length") == 2, "человек выключил — не спорим")
        elif case["torch"]:
            ok(r["shown"] and not r["on"] and not r["torch"], f"{name}: кнопка есть, фонарик не включается зря: {r}")
            pg.click(".dwq .tl"); pg.wait_for_timeout(200)
            ok(pg.evaluate("_torch.slice()") == [True], "нажали — фонарик включён")
        else:
            ok(not r["shown"] and not r["torch"], f"{name}: кнопки нет: {r}")
        pg.evaluate("() => _close()"); pg.wait_for_timeout(200)
        ok(pg.evaluate("_stopped") >= 1 and not pg.evaluate("!!document.querySelector('.dwq')"), f"{name}: закрыли — камера (и фонарик) выключены")
        pg.close()
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
