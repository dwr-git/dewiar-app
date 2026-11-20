"""Образы на телефоне (1.0.55): в листе «Кто отвечает» — кружки образов Лиры и Патрика и «Сама — по времени и сезону»;
выбор меняет живое лицо (live/<live>-<образ>.webp); голосом — «смени образ», «надень зимний», «выбирай образ сама».
Правило «Сама» — то же, что на компьютере (core/personas.look_auto)."""
import datetime as dt, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import personas as P  # noqa: E402
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 852}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1500)
        L = pg.evaluate("() => PERSONAS.find(p => p.id === 'lira').looks.map(x => x.id)")
        ok(L == [x["id"] for x in P.LOOKS["lira"]], f"образы Лиры — те же, что на компьютере: {L}")
        # «Сама»: то же правило, что core/personas.look_auto
        days = [dt.datetime(2026, m, d, h) for m in (1, 4, 7, 10) for d in (1, 2, 3, 17) for h in (9, 21)]
        js = pg.evaluate("ds => ds.map(d => lookAuto(PERSONAS.find(p => p.id === 'lira').looks, new Date(d[0], d[1] - 1, d[2], d[3])))",
                         [[d.year, d.month, d.day, d.hour] for d in days])
        py = [P.look_auto(P.LOOKS["lira"], d) for d in days]
        ok(js == py, f"«Сама» — как на компьютере ({sum(a == b for a, b in zip(js, py))} из {len(py)})")
        pg.evaluate("() => { S.persona = 'lira'; saveS(); applyPersona(); }")
        pg.click("#who"); pg.wait_for_timeout(500)
        n = pg.evaluate("() => document.querySelectorAll('#plook .plg button').length")
        ok(n == len(L) + 1, f"лист «Кто отвечает»: кружки образов и «Обычная»: {n}")
        pg.click("#plook .plg button:nth-child(2)"); pg.wait_for_timeout(300)
        r = pg.evaluate("() => [S.looks.lira.look, persona().live, orb.live]")
        ok(r == ["spring", "lira-spring", "lira-spring"], f"выбрали «Весна» — живое лицо образа: {r}")
        pg.check("#plook-auto", force=True); pg.wait_for_timeout(200)
        ok(pg.evaluate("S.looks.lira.auto") is True, "«Сама — по времени и сезону» включается")
        pg.evaluate("closeSheets()")
        for say, want in (("Лира, смени образ", "next"), ("надень зимний", "winter"), ("верни обычный образ", "")):
            out = pg.evaluate("async t => { const before = lookOf(personaBase()); const r = await quick(t); return [r && r.say, lookOf(personaBase()), before]; }", say)
            good = out[0] and (out[1] == want if want != "next" else out[1] != out[2])
            ok(good, f"«{say}» без модели: {out}")
        ok(pg.evaluate("async () => { const r = await quick('надень куртку'); return r === null || !/образ/.test((r || {}).say || ''); }"), "не образ — дальше")
        pg.evaluate("() => { S.persona = 'patrik'; saveS(); applyPersona(); }")
        ok(pg.evaluate("personaBase().looks.length") == len(P.LOOKS["patrik"]), "у Патрика — свои образы")
        ok(not errs, f"без ошибок: {errs[:2]}")
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
