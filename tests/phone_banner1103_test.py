"""№454 (01.11, телефон 0.9.16): «В текстовом диалоге ИИ пишет ответ; когда дописывает — ответ закрывается баннером
„Готово, всё подключено. Нажмите на микрофон…“, прочитать невозможно; перезагрузка помогает, потом снова».
startCardCheck искал в карточке любую .start — так же сделаны «Звук на нуле — включить и прочитать ответ» и «В коде
ссылка»; после ответа saveS() звал проверку, и она затирала ответ. Теперь — только карточка первого запуска (data-first)."""
import os, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


w = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
ANSWER = "Хорошо, вот система тайм-менеджмента: 1) утром — три главных дела; 2) днём — блоки по 50 минут; 3) вечером — разбор."
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    # мозг подключён (облако), звук на нуле: ответ показан, под ним — «Звук на нуле — включить и прочитать ответ»
    pg.evaluate("""(a) => { S.llm = Object.assign({}, S.llm, { base_url: 'https://dewiar.pro/dwrapp/cloud.php?p=', api_key: 'k', cloud: true, trial: false });
      busy = false; setState('idle'); showCard(''); showBot(a); volMuted = a; volCard(); saveS(); }""", ANSWER)
    pg.wait_for_timeout(300)
    ok(pg.inner_text("#bot") == ANSWER, f"после сохранения настроек ответ на месте, не «Готово, всё подключено»: {pg.inner_text('#bot')[:60]!r}")
    ok(pg.evaluate("!!document.querySelector('#vol-up')"), "карточка «Звук на нуле» осталась")
    # «В коде ссылка» — тоже .start
    pg.evaluate("() => { showCard(''); scanResult('https://example.org/page', 'qr'); saveS(); }")
    pg.wait_for_timeout(300)
    ok("example.org" in pg.inner_text("#bot") and pg.evaluate("!!document.querySelector('#sc-open')"), "результат сканирования не затирается")
    # карточка первого запуска — по-прежнему уходит, и Лира говорит, что готова
    pg.evaluate("""() => { showBot('Привет! Я Лира. Чтобы мы могли поговорить, меня нужно один раз подключить.');
      showCard(`<div class="start" data-first="1"><button class="btn p w" onclick="openBrain('join')">Подключить бесплатно</button></div>`); saveS(); }""")
    pg.wait_for_timeout(300)
    ok(pg.inner_text("#card").strip() == "" and "Готово, всё подключено" in pg.inner_text("#bot"), "подключились с первого запуска — карточка ушла, «Готово»")
    src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
    ok(src.count('<div class="start" data-first="1">') == 3, "все три карточки первого запуска помечены data-first")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
