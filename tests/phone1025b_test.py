"""Телефон, пакет здоровья 25.10:
— №253 «телефон без русской прошивки, Dewiar настойчиво пытается распознать английский и китайский»: распознаватель
  просят «только русский» (EXTRA_LANGUAGE_PREFERENCE), а если он всё равно вернул иероглифы или латиницу без русских
  букв — Лире это не уходит: первый раз переспрашиваем и слушает сервер Dewiar, второй раз подряд — сервер насовсем;
  сервера нет — честно сказано, что делать; русское — счётчик сбрасывается;
— «Каляка» на телефоне (владелец: «экран моргает вспышками») — на полке телефона её нет, голосом — объяснение;
  на компьютере — есть."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sp = (ROOT / "android/src/pro/dewiar/app/Speech.java").read_text(encoding="utf-8")
ok("EXTRA_LANGUAGE_PREFERENCE, \"ru-RU\"" in sp and "EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, true" in sp, "распознаватель телефона просят «только русский»")
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
STUB = """(say) => { window._sys = []; window._srv = 0; window._asked = [];
  D.recognizer = () => true;
  D.listen = (g) => { window._sys.push(g); setTimeout(() => { N.ev(JSON.stringify({ type: 'stt_start', g }));
      N.ev(JSON.stringify({ type: 'stt_result', g, text: say.shift() || '' })); }, 30); };
  D.listenServer = (g) => { window._srv++; setTimeout(() => N.ev(JSON.stringify({ type: 'stt_result', g, text: say.shift() || '' })), 30); };
  window.ask = (t) => { _asked.push(t); setState('idle'); return Promise.resolve(); };
}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.toasts = [];")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { const t = window.toast; window.toast = (m, ms) => { toasts.push(m); return t(m, ms); }; }")
    pg.evaluate("() => { S.stt = { engine: 'system' }; S.llm = Object.assign({}, S.llm, { cloud: true, stt: true, api_key: 'k', base_url: 'https://dewiar.pro/dwrapp/cloud.php?p=' }); saveS(); }")
    pg.evaluate(STUB, ["你好今天天气", "напомни купить хлеб"])
    pg.evaluate("() => listen()"); pg.wait_for_timeout(1500)
    R = pg.evaluate("() => ({ asked: _asked, srv: _srv, sys: _sys.length, eng: S.stt.engine, n: S.stt.notRu || 0, toasts })")
    ok("你好今天天气" not in R["asked"] and R["asked"] == ["напомни купить хлеб"], f"иероглифы Лире не ушли, переспросили — второй раз уже по-русски: {R['asked']}")
    ok(R["srv"] == 1 and R["eng"] == "system", f"переспрос слушал сервер Dewiar, насовсем пока не переключили: сервер {R['srv']}, {R['eng']}")
    ok(any("по-русски" in t for t in R["toasts"]) and R["n"] == 0, f"сказали «не разобрала по-русски»; русское — счётчик к нулю: {R['n']}")
    # два раза подряд — сервер насовсем
    pg.evaluate(STUB, ["hello how are you", "", "what is the weather", "какая погода"])
    pg.evaluate("() => listen()"); pg.wait_for_timeout(1200)
    pg.evaluate("() => { if (state !== 'idle') setState('idle'); }")
    pg.evaluate("() => { S.stt.engine === 'system' && listen(); }"); pg.wait_for_timeout(1500)
    R = pg.evaluate("() => ({ asked: _asked, eng: S.stt.engine, url: S.stt.url || '', toasts })")
    ok(R["eng"] == "server" and "cloud.php" in R["url"], f"второй раз подряд не по-русски — слушает сервер Dewiar насовсем: {R['eng']}")
    ok(any("теперь слушает сервер Dewiar" in t for t in R["toasts"]), "и сказано почему")
    ok(all(not a.startswith(("hello", "what")) for a in R["asked"]), f"латиница без русских букв Лире не ушла: {R['asked']}")
    # одно английское слово — не трогаем
    pg.evaluate("() => { S.stt = { engine: 'system' }; saveS(); }")
    pg.evaluate(STUB, ["YouTube"])
    pg.evaluate("() => listen()"); pg.wait_for_timeout(800)
    ok(pg.evaluate("_asked") == ["YouTube"], "одно латинское слово («YouTube») — обычный вопрос")
    # сервера нет — честно
    pg.evaluate("() => { S.stt = { engine: 'system' }; S.llm = Object.assign({}, S.llm, { cloud: false, stt: false }); saveS(); }")
    pg.evaluate(STUB, ["谢谢"])
    pg.evaluate("() => listen()"); pg.wait_for_timeout(800)
    ok("слышит не по-русски" in pg.text_content("#bot") and "Мозге" in pg.text_content("#bot"), "сервера нет — сказано, что делать")
    # Каляка
    pg.evaluate("() => playOpen('')"); pg.wait_for_timeout(300)
    games = pg.evaluate("[...document.querySelectorAll('#play-body .ag')].map(b => b.dataset.game)")
    ok("doodle" not in games and "post" in games and len(games) >= 10, f"на полке телефона «Каляки» нет, остальные есть: {len(games)}")
    pg.evaluate("() => playOpen('doodle')"); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#gameov').hidden") and any("только на компьютере" in t for t in pg.evaluate("toasts")),
       "«давай поиграем в каляку» на телефоне — объяснение вместо игры")
    pg.evaluate("() => { document.body.innerHTML += '<div id=pcs></div>'; document.querySelector('#pcs').innerHTML = DewiarArcade.html('arcade/'); }")
    ok(pg.evaluate("!!document.querySelector('#pcs [data-game=\"doodle\"]')"), "на компьютере (полка без «phone») «Каляка» есть")
    b.close()
gj = (ROOT / "ui/assets/arcade/doodle/game.js").read_text(encoding="utf-8")
cfg = next(l for l in gj.splitlines() if "id: 'doodle'" in l)
ok("//" not in cfg and "orientation:" in cfg and "tone: 'light'" in cfg and "music: 'garden'" in cfg,
   "«Каляка»: настройки игры не закомментированы (в 0.45.0 комментарий съел ориентацию, светлый тон и музыку)")
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
