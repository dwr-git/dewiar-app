"""Мелочи студии по отзыву 11.10 (Ubuntu, три монитора):
— Суфлёр перетаскивает оконный менеджер (begin_move_drag), а не pywebview по screenX — окно не уезжает на другой экран;
— «Мозг» → «Пополнить»: текст выделяется (pywebview запрещает выделение на body), ссылка на донат открывается в браузере;
— плитки «где думать» без размытия и сдвига при наведении (подтормаживали) и ровной сеткой во всю ширину."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
op = app[app.index("def open_prompter"):app.index("def close_prompter")]
ok("def _wm_drag(" in app and "begin_move_drag" in app[app.index("def _wm_drag("):app.index("# ---------- своя рамка студии")]
   and "self._wm_drag(gw" in op, "Суфлёр: заголовок двигает оконный менеджер")
css = (ROOT / "ui/prompter.html").read_text(encoding="utf-8")
m = re.search(r"PROMPTER_BAR, PROMPTER_BTNS = (\d+), (\d+)", app)
ok(m and int(m.group(1)) >= 14 + 32 + 10 and "header { display: flex; align-items: center; gap: 10px; padding: 14px 14px 10px 20px;" in css,
   "зона перетаскивания совпадает с заголовком суфлёра (14 + кнопка 32 + 10)")
TXT = "Перевод по реквизитам: IBAN BY00TEST0000000000000000\nДонат: https://donate.example/dewiar_test.\n<b>не тег</b>"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1500, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: (t, k) => k === 'open_url' ? ((u) => { window._opened = u; return Promise.resolve(true); }) : () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.add_style_tag(content="body{-webkit-user-select:none;user-select:none}")        # так делает pywebview (text_select=False)
    pg.evaluate("(t) => { $('nav button[data-p=\"brain\"]').click(); $('#cc-pay').style.display = ''; topupText(t); }", TXT)
    pg.wait_for_timeout(300)
    r = pg.evaluate("""() => { const el = $('#cc-topup'); const a = el.querySelector('a[data-ext]'); a.click();
      return [getComputedStyle(el).userSelect, a.textContent, window._opened, el.querySelectorAll('b').length, el.textContent.includes('<b>не тег</b>')]; }""")
    ok(r == ["text", "https://donate.example/dewiar_test", "https://donate.example/dewiar_test", 0, True],
       f"как пополнить: выделяется, ссылка (без точки в конце) открывается в браузере, чужой HTML — просто текст: {r}")
    r = pg.evaluate("""() => { const t = [...document.querySelectorAll('#wz .wtile')], cs = getComputedStyle(t[1]);
      const rows = new Set(t.map(x => Math.round(x.getBoundingClientRect().top))), wz = $('#wz').getBoundingClientRect(), last = t[t.length - 1].getBoundingClientRect();
      return [cs.backdropFilter, cs.transitionProperty, rows.size, Math.abs(wz.right - last.right) < 2]; }""")
    ok(r[0] in ("none", "") and "transform" not in r[1] and r[2] == 1 and r[3], f"плитки «Мозга»: без размытия и сдвига, одним рядом во всю ширину: {r}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
ph = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok('data-ext="$1"' in ph[ph.index("function clTopFill"):ph.index("function clTopFill") + 800] and "#cl-top { -webkit-user-select: text"
   in (ROOT / "android/assets/www/app.css").read_text(encoding="utf-8"), "телефон: как пополнить — тоже выделяется, ссылки открываются")
# слух и голоса грузятся по очереди (отзыв 11.10: GigaAM + Vosk TTS вместе — компьютер завис)
import threading  # noqa: E402
sys.path.insert(0, str(ROOT / "core"))
import ortcfg  # noqa: E402
stt_src, tts_src = (ROOT / "core/stt.py").read_text(encoding="utf-8"), (ROOT / "core/tts.py").read_text(encoding="utf-8")
ok(isinstance(ortcfg.HEAVY, type(threading.Lock())) and stt_src.count("with _heavy():") == 2 and "with heavy:" in tts_src[tts_src.index("class VoskProc"):tts_src.index("class VoskTTS")],
   "GigaAM и голоса Vosk грузятся по очереди, а не вместе")
br = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok('<i class="fxp"></i>' in br and "previewVoice(b" in br[br.index("function renderFx"):], "у каждого варианта обработки голоса — ▶: выбрать и послушать")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
