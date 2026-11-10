"""№561 (05.11, веб-версия 0.9.26 на Mac, голос Safari): «при озвучивании ответов Лиры происходит чтение кавычек в
названиях задачи — это слышится отвратительно. Спецсимволы (кавычки, восклицательный знак, тире…) не нужно озвучивать».
Голос устройства получал текст с «», разметкой и «!!!» как есть. Теперь перед любым голосом — speech_clean
(core/speechnorm.py) и clean (ui/assets/speechnorm.js, телефон и веб; в веб-мосте — последний рубеж перед speechSynthesis):
кавычки и разметка прочь, тире — пауза, «!!!»/«?!» — один знак, скобки — паузы, эмодзи прочь. Числа, время, даты,
«12 - 10 = 2», «XIX–XX вв.» — по-прежнему словами. Обе реализации сверяются на одних фразах."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from speechnorm import speech_clean, speech_norm  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


REPORTED = "Я поставила тебе ежедневное напоминание «Прогулка в парке» на 9:00 утра. Готово, напоминание стоит."
EXPECT = {
    REPORTED: "Я поставила тебе ежедневное напоминание Прогулка в парке на 9:00 утра. Готово, напоминание стоит.",
    "**Готово!!!** Напоминание «Купить хлеб» — на завтра 😊": "Готово! Напоминание Купить хлеб, на завтра",
    "## План\n- Встать в 7:00\n- Зарядка (15 минут)\n- Завтрак": "План. Встать в 7:00. Зарядка, 15 минут. Завтрак",
    "Что?! Правда?..": "Что? Правда?",
    'Он сказал: "Привет" — и ушёл.': "Он сказал: Привет, и ушёл.",
    "Он сказал: „Привет“ и “пока”": "Он сказал: Привет и пока",
    "Смотри [сайт](https://dewiar.pro) и `код`": "Смотри сайт и код",
    "— Привет! — сказала она.": "Привет! сказала она.",
    "Итог: (см. выше).": "Итог: см. выше.",
    "> Цитата\n> вторая строка": "Цитата. вторая строка",
    "#важное | срочно ~ ^_^": "важное срочно",
    "Отлично 👍🏻✨ — всё 🎉 готово ✅": "Отлично, всё готово",
    "don't stop 'em": "don't stop em",
    "Слово—слово и слово - слово": "Слово, слово и слово, слово",
}
KEEP = ["12 - 10 = 2, а 3 * 4 = 12", "1941—1945 годы, XIX–XX вв.", "Температура −5°, ночью -7°", "x86_64 и snake_case",
        "В 16:30 — 45%", "Скорость 10-12 км", "вай-фай и кто-то", "14.10.2026 в 9:05"]
for src, want in EXPECT.items():
    got = speech_clean(src)
    ok(got == want, f"чисто для голоса: {src[:40]!r} → {got!r}")
for src in KEEP:
    ok(speech_clean(src) == src, f"числа и слова через дефис не тронуты: {src!r} → {speech_clean(src)!r}")
for src in list(EXPECT) + KEEP:
    once = speech_clean(src)
    ok(speech_clean(once) == once, f"второй раз ничего не меняет: {src[:30]!r}")
said = speech_norm(REPORTED, latin=False)
ok("«" not in said and "»" not in said and "на девять утра" in said and said.endswith("стоит."), f"PC (Piper, голос Windows, macOS): {said!r}")
said = speech_norm(REPORTED)
ok(not re.search(r"[«»\"'()*#_]", said), f"голос сервера (латиница словами): {said!r}")
ok(speech_norm("12 - 10 = 2", latin=False) == "двенадцать минус десять равно два." and speech_norm("3 * 4 = 12", latin=False) == "три умножить на четыре равно двенадцать.",
   "пример со знаками — по-прежнему словами")
ok("девятнадцатые — двадцатые века" in speech_norm("XIX–XX вв."), "римские века — как раньше")
ok(not re.search(r"[!?]{2}", speech_norm("Ура!!! Правда?!")), "«!!!» и «?!» — один знак")

# ---------- телефон и веб: тот же разбор (JS) ----------
if not shutil.which("node"):
    print("нет node — сверку с телефоном пропускаю")
else:
    tmp = Path(tempfile.mkdtemp())
    js = tmp / "t.js"
    js.write_text("global.window = {};\n" + (ROOT / "ui/assets/speechnorm.js").read_text(encoding="utf-8")
                  + "\nconst P = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
                  + "console.log(JSON.stringify(P.map(t => [window.DewiarSpeech.clean(t), window.DewiarSpeech.norm(t, false), window.DewiarSpeech.norm(t, true)])));\n",
                  encoding="utf-8")
    cases = list(EXPECT) + KEEP + ["Ура!!! Правда?!", "XIX–XX вв.", "Код: ```print(1)``` готово", "Встреча (в 18:00) — «Сбер»"]
    (tmp / "p.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(js), str(tmp / "p.json")], capture_output=True, text=True, check=True).stdout)
    bad = [(c, o, [speech_clean(c), speech_norm(c, latin=False), speech_norm(c)]) for c, o in zip(cases, out)
           if o != [speech_clean(c), speech_norm(c, latin=False), speech_norm(c)]]
    for c, a, b in bad[:5]:
        print(f"   {c!r}\n     js: {a!r}\n     py: {b!r}")
    ok(not bad, f"телефон и компьютер чистят одинаково: {len(cases) - len(bad)} из {len(cases)}")

app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("window.DewiarSpeech.clean(t.replace(EMOJI" in app, "телефон: speechText — через clean (голос устройства и сервера)")
wb = (ROOT / "android/web/webbridge.js").read_text(encoding="utf-8")
ok(re.search(r"function sayLocal\(id, text[^)]*\) \{\n\s*text = forVoice\(text\);", wb) is not None, "веб: перед speechSynthesis — clean, что бы ни пришло")
tts = (ROOT / "core/tts.py").read_text(encoding="utf-8")
ok(tts.count("speech_clean(text)") >= 3, "компьютер: английский Piper, голос сервера без кириллицы и ElevenLabs — тоже без символов")

# ---------- живой путь в браузере: что получает speechSynthesis ----------
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright:
    www = Path(tempfile.mkdtemp()) / "www"
    shutil.copytree(ROOT / "android/assets/www", www)
    for f in ("entities.js", "skins.css", "skins.js", "privacy.js", "speechnorm.js"):
        shutil.copy(ROOT / "ui/assets" / f, www / f)
    shutil.copy(ROOT / "android/web/webbridge.js", www / "webbridge.js")
    (www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                    capture_output=True, text=True, check=True).stdout, encoding="utf-8")
    html = (www / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'<script src="app\.js[^"]*"></script>', '<script src="webbridge.js"></script>\n<script src="app.js"></script>', html)
    (www / "index.html").write_text(html, encoding="utf-8")
    SYN = r"""(() => { window._spoken = []; const fake = { speaking: false, pending: false, paused: false, getVoices: () => [],
      speak(u) { _spoken.push(u.text); setTimeout(() => { u.onstart && u.onstart(); u.onend && u.onend(); }, 5); }, cancel() {}, addEventListener() {} };
      try { Object.defineProperty(window, 'speechSynthesis', { value: fake, configurable: true }); } catch (e) {} })();"""
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 760}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("https://**", lambda r: r.abort()); pg.add_init_script(SYN)
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
        web = pg.evaluate("!!D.web")
        pg.evaluate("(t) => { S.textMode = false; S.tts = Object.assign({}, S.tts, { engine: 'system' }); D.volume = () => 50; D.ttsReady = () => true; say(t); }", REPORTED)
        pg.wait_for_timeout(300)
        spoken = pg.evaluate("_spoken.filter(x => x.trim())")
        ok(web and spoken and all("«" not in s and "»" not in s for s in spoken) and any("Прогулка в парке" in s for s in spoken),
           f"веб: голос Safari получает фразу без кавычек: {spoken}")
        pg.evaluate("() => { _spoken.length = 0; D.speak('x1', '**Ура!!!** «Тест» — да 🎉', 1, 1, '', true); }")
        pg.wait_for_timeout(200)
        ok(pg.evaluate("_spoken.slice()") == ["Ура! Тест, да"], f"веб-мост: и прямой вызов голоса — чистый: {pg.evaluate('_spoken.slice()')}")
        b.close()
    ok(not errs, f"веб-версия без ошибок страницы: {errs[:2]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
