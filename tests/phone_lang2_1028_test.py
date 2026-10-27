"""Телефон: второй язык — английский (28.10, №365: «Патрик не понимает английскую речь»). «Слух и голос» → «Понимать
английскую речь» → распознавателю телефона (D.sttLang2 → Speech.java: язык фразы узнаёт сам, Android 14+); вопрос
по-английски — подсказка модели ответить по-английски; английская фраза ответа — голосом телефона на английском
(D.speakLang, en-US), голосу сервера — без русской «нормализации» чисел."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "rich.js", "skins.js", "skins.css", "speechnorm.js"):
    if (ROOT / "ui/assets" / f).exists():
        shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 860})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.__lang = []; window.__spk = [];")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("""() => { S.llm.base_url = 'http://127.0.0.1:9/v1'; S.llm.model = 'm'; S.welcome = { on: false }; S.course = { offered: lnToday() }; saveS();
      D.sttLang2 = (l) => __lang.push(l); D.ttsReady = () => true;
      D.speak = (id, t) => __spk.push(['ru', t]); D.speakLang = (id, t, r, p, v, add, lang) => __spk.push([lang, t]); }""")
    r = pg.evaluate("""() => [isEnglish("What's the weather tomorrow?"), isEnglish('tell me a joke'), isEnglish('Какая погода?'), isEnglish('PDF'),
        isEnglish('Открой Telegram'), isEnglish('Patrick, how are you')]""")
    ok(r == [True, True, False, False, False, True], f"английская фраза узнаётся, русская и названия — нет: {r}")
    r = pg.evaluate("() => [turnContext('How are you today?').includes('ответь по-английски'), turnContext('Как дела?').includes('по-английски')]")
    ok(r == [True, False], f"вопрос по-английски — модели подсказка «ответь по-английски»: {r}")
    pg.evaluate("() => { S.tts.engine = 'system'; S.textMode = false; say('Sure! The weather tomorrow will be sunny.'); say('Завтра будет солнечно.'); }")
    pg.wait_for_timeout(300)
    spk = pg.evaluate("__spk")
    ok(["en-US", "Sure! The weather tomorrow will be sunny."] in spk and any(x[0] == "ru" and "солнечно" in x[1] for x in spk),
       f"английская фраза — английским голосом телефона, русская — как раньше: {spk}")
    # переключатель
    pg.evaluate("() => openSettings('voice')"); pg.wait_for_timeout(500)
    ok(pg.evaluate("() => !!document.querySelector('#lang2-en')"), "«Слух и голос» → «Понимать английскую речь»")
    pg.evaluate("() => document.querySelector('#lang2-en').click()"); pg.wait_for_timeout(200)
    ok(pg.evaluate("() => [S.lang2, __lang[__lang.length - 1]]") == ["en", "en"], "включили — распознаватель телефона узнаёт язык сам")
    pg.evaluate("() => document.querySelector('#lang2-en').click()"); pg.wait_for_timeout(200)
    ok(pg.evaluate("() => [S.lang2, __lang[__lang.length - 1]]") == ["", ""], "выключили — снова только русский")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
# нативная часть
sp = (ROOT / "android/src/pro/dewiar/app/Speech.java").read_text(encoding="utf-8")
ok("ENABLE_LANGUAGE_DETECTION" in sp and "LANGUAGE_SWITCH_ALLOWED_LANGUAGES" in sp and re.search(r'"en"\.equals\(lang2\)', sp),
   "Speech.java: второй язык — определение языка и переключение (Android 14+)")
tts = (ROOT / "android/src/pro/dewiar/app/Tts.java").read_text(encoding="utf-8")
br = (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8")
ok("isLanguageAvailable" in tts and "speakLang" in br and "sttLang2" in br, "Tts.java — фраза на другом языке, мост — speakLang и sttLang2")
wb = (ROOT / "android/web/webbridge.js").read_text(encoding="utf-8")
ok("speakLang(" in wb and "sttLang2()" in wb, "веб-версия: английская фраза — английским голосом браузера")
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
