"""№93 (идея: «Прокрутка плавная нужна, как будто телефон тупит»), 03.11.

Статически: все обработчики scroll / touchstart / touchmove в коде телефона (android/assets/www и общие файлы, которые
кладёт в APK android/tools/www_assemble.sh) — пассивные ({passive: true}), нет onscroll/ontouchmove= (они не бывают
пассивными явно); у фона нет background-attachment: fixed; столбики радио анимируются transform, а не height; у листа
неоморфизма (тема по умолчанию) нет размытия фона — фон и так непрозрачный; карточки заметок — content-visibility.
Вживую: пока лист прокручивают, на body класс scrolling и портрет не рисуется (orb.paused), после — снова рисуется;
в лёгком режиме у листа нет размытия фона."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# --- статически ---
files = sorted((ROOT / "android/assets/www").glob("*.js"))
asm = (ROOT / "android/tools/www_assemble.sh").read_text(encoding="utf-8")
files += [ROOT / "ui/assets" / n for n in sorted(set(re.findall(r'"\$ROOT/ui/assets/([\w.-]+\.js)"', asm)))]
ok(len(files) > 10 and any(f.name == "entities.js" for f in files), f"проверяем файлы телефона и общие из www_assemble.sh ({len(files)})")


def call_args(src, i):
    """Текст вызова addEventListener(...) с позиции «(» — по скобкам, строки и шаблоны пропускаем."""
    depth, j, q = 0, i, None
    while j < len(src):
        ch = src[j]
        if q:
            if ch == "\\":
                j += 2; continue
            if ch == q:
                q = None
        elif ch in "\"'`":
            q = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return src[i:]


bad, seen = [], 0
for f in files:
    src = f.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"addEventListener\(\s*([\"'])(scroll|touchstart|touchmove)\1", src):
        seen += 1
        args = call_args(src, m.end() - len(m.group(0)) + len("addEventListener"))
        if not re.search(r"passive\s*:\s*true", args):
            bad.append(f"{f.name}:{src.count(chr(10), 0, m.start()) + 1} {m.group(2)}")
    for m in re.finditer(r"\.on(scroll|touchmove|touchstart)\s*=", src):
        bad.append(f"{f.name}:{src.count(chr(10), 0, m.start()) + 1} on{m.group(1)}=")
ok(seen >= 4 and not bad, f"обработчики scroll/touchstart/touchmove пассивные ({seen} шт.): {bad}")
css = (ROOT / "android/assets/www/app.css").read_text(encoding="utf-8")
css_rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
ok("background-attachment: fixed" not in css_rules and "background-attachment:fixed" not in css_rules, "у фона нет background-attachment: fixed")
ok(not re.search(r"@keyframes eq\s*\{[^}]*height", css_rules), "столбики радио — transform, а не height")
ok(re.search(r"body\.neu \.sheet \{[^}]*backdrop-filter: none", css_rules) is not None, "неоморфизм: у непрозрачного листа нет размытия фона")
ok(re.search(r"body\.lite-ui \.sheet \{[^}]*backdrop-filter: none", css_rules) is not None, "лёгкий режим: лист без размытия фона")
ok(re.search(r"\.it\.note \{[^}]*content-visibility: auto[^}]*contain-intrinsic-size", css_rules) is not None, "карточки заметок: content-visibility с запасной высотой")

# --- вживую ---
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
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 700})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("""() => { const l = []; for (let i = 0; i < 80; i++) l.push({ id: 'n' + i, title: 'Заметка ' + i, text: 'текст '.repeat(30), time: Date.now() - i * 1e5 });
      saveNotes(l); S.skin = 'graphite'; applyLook(); openSheet('#sh-day'); dayTab = 'notes'; renderDay(); }""")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("getComputedStyle(document.querySelector('#sh-day')).backdropFilter") != "none", "тёмная тема: размытие под листом на месте (без прокрутки)")
    pg.evaluate("document.querySelector('#sh-day').scrollTop = 600"); pg.wait_for_timeout(60)
    st = pg.evaluate("[document.body.classList.contains('scrolling'), !!orb.paused]")
    ok(st == [True, True], f"листают — body.scrolling и портрет не рисуется: {st}")
    pg.wait_for_timeout(450)
    st = pg.evaluate("[document.body.classList.contains('scrolling'), !!orb.paused]")
    ok(st == [False, False], f"перестали листать — всё как было: {st}")
    pg.evaluate("document.querySelector('#talk') && (document.querySelector('#talk').scrollTop = 5)"); pg.wait_for_timeout(30)
    ok(not pg.evaluate("document.body.classList.contains('scrolling')"), "прокрутка вне листа портрет не останавливает")
    pg.evaluate("S.lite = 'on'; liteApply()"); pg.wait_for_timeout(100)
    ok(pg.evaluate("document.body.classList.contains('lite-ui') && getComputedStyle(document.querySelector('#sh-day')).backdropFilter === 'none'"),
       "лёгкий режим — лист без размытия фона")
    pg.evaluate("S.lite = 'off'; liteApply(); S.skin = 'neusky'; applyLook()"); pg.wait_for_timeout(100)
    ok(pg.evaluate("getComputedStyle(document.querySelector('#sh-day')).backdropFilter") == "none", "«Небесный» (по умолчанию) — лист без размытия: фон непрозрачный")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
shutil.rmtree(tmp, ignore_errors=True)
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
