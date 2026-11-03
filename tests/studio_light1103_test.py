"""Лёгкая студия (группа Telegram 03.11, идея №60: «программа становится перегруженной… скрывать ненужный функционал…
полная оболочка Dewiar подтормаживает»).
1. Разделы ленивые: «Персонажи» (карточки, галерея с обликами), «Подключение» (календари, умный дом), голоса Vosk — не
   грузятся при запуске, а при первом открытии раздела.
2. Облики в закрытых разделах не крутят кадры: в простое на «Главной» — единицы кадров requestAnimationFrame в секунду,
   а не сотни.
3. Опрос ядра — только у видимого раздела и при видимом окне («Безопасность»: журнал раз в 10 с).
4. «Оформление» → «Что показывать»: группа «Работа» скрывается из меню и с «Главной»; набор «Минимум»; поиск находит
   скрытое («раздел скрыт — показать?») и возвращает раздел; «Всё» — всё на месте; переживает перезапуск окна.
5. «Облегчённый вид» убирает размытие и «стекло» с неподвижным фоном, облики — реже.
SHOW_SHOTS=<папка> — снимки экрана «Что показывать» (studio-show-*.png)."""
import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("SHOW_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "dewiar", "audio": {"sounds": False},
    "ui": {"news_seen": "99.0.0", "welcome": "done", "memory_motion": "off", "studio_lite": "off"},
    "features": {"clients": True, "team": True}, "stt": {"engine": "vosk"}, "tts": {"engine": "off"},
    "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
# счётчики: какие команды ушли в ядро и сколько кадров requestAnimationFrame
INIT = r"""
window.__calls = [];
const _send = WebSocket.prototype.send;
WebSocket.prototype.send = function (d) { try { __calls.push(JSON.parse(d).cmd); } catch (e) {} return _send.call(this, d); };
window.__raf = 0;
const _raf = window.requestAnimationFrame.bind(window);
window.requestAnimationFrame = (f) => _raf((t) => { __raf++; f(t); });
"""
NAVVIS = "[...document.querySelectorAll('nav button[data-p]')].filter(b => b.offsetParent !== null).map(b => b.dataset.p)"
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.add_init_script(INIT)
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text
              and "net::" not in m.text else None)
        url = (ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"
        pg.goto(url); pg.wait_for_selector("#conn.ok", timeout=30000); time.sleep(3)
        calls = lambda: pg.evaluate("__calls")
        nav = lambda pid: pg.evaluate("(p) => document.querySelector(`nav button[data-p=\"${p}\"]`).click()", pid)

        # 1. ленивые разделы
        c0 = calls()
        # kids_get при запуске — нужен: включённый детский режим закрывает студию заслонкой с PIN (kids1027)
        ok(not any(x in c0 for x in ("gallery", "cal_list", "ha_get", "home_get", "vosk_voices", "phone_config", "sshlink")),
           "при запуске не грузятся «Персонажи», «Подключение», голоса, запасной вход: " + ", ".join(x for x in ("gallery", "cal_list", "ha_get", "home_get", "vosk_voices", "phone_config", "sshlink") if x in c0))
        ok(pg.evaluate("document.querySelectorAll('#pgrid .card').length") == 0 and pg.evaluate("studioSec.seen()") == ["home"],
           "карточки персонажей не построены, открывалась только «Главная»: " + str(pg.evaluate("studioSec.seen()")))
        nav("personas"); time.sleep(1.2)
        ok(pg.evaluate("document.querySelectorAll('#pgrid .card:not(.new)').length") >= 1 and "gallery" in calls() and "vosk_voices" in calls(),
           "первое открытие «Персонажей» — карточки, галерея и голоса для редактора")
        nav("connect"); time.sleep(1)
        ok(all(x in calls() for x in ("cal_list", "ha_get", "home_get", "phone_config")), "первое открытие «Подключения» — календари, умный дом, код для телефона")
        nav("home"); time.sleep(1.5)

        # 2. облики в закрытых разделах не крутят кадры (до 03.11 — около тысячи кадров в секунду)
        r0 = pg.evaluate("__raf"); time.sleep(2); fr = pg.evaluate("__raf") - r0
        ok(fr < 260, f"в простое на «Главной» — {fr} кадров requestAnimationFrame за 2 с (только логотип)")

        # 3. опрос — только у видимого раздела
        nav("safety"); time.sleep(0.8)
        ok("safety" in pg.evaluate("studioSec.polls()"), "«Безопасность» открыта — журнал опрашивается")
        pg.evaluate("Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange'))")
        ok(pg.evaluate("studioSec.polls()") == [], "окно свёрнуто — опросов нет")
        pg.evaluate("delete document.hidden; document.dispatchEvent(new Event('visibilitychange'))")
        ok("safety" in pg.evaluate("studioSec.polls()"), "окно снова на экране — опрос продолжается")
        nav("home"); time.sleep(0.5)
        n0 = calls().count("security_state"); time.sleep(11)
        ok(pg.evaluate("studioSec.polls()") == [] and calls().count("security_state") == n0, "раздел закрыт — за 11 с ни одного security_state")

        # 4. «Что показывать»
        nav("look"); time.sleep(0.8)
        groups = pg.evaluate("[...document.querySelectorAll('#sh-groups .sh-g')].map(g => g.querySelector('.sh-gh b').textContent)")
        ok(all(g in groups for g in ("Для себя", "Семья и близкие", "Режимы Лиры", "Работа", "Обучение", "Знания", "Настройка")),
           "«Оформление» → «Что показывать»: группы меню — " + ", ".join(groups))
        ok(pg.evaluate("document.querySelectorAll('#sh-sets .sh-set').length") == 3 and pg.evaluate("document.querySelector('#sh-sets [aria-pressed=true]')?.dataset.set") == "all",
           "три готовых набора, сейчас — «Всё»")
        ok(pg.evaluate("!document.querySelector('.sh-g.lock input') && document.querySelector('.sh-g.lock')?.textContent.includes('Оформление')"),
           "«Настройка» — всегда в меню, без переключателей (иначе не вернуть)")
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            pg.evaluate("(() => { const h = document.getElementById('sh-h'); h.scrollIntoView({ block: 'start' }); let m = h.parentElement; while (m && m.scrollHeight <= m.clientHeight) m = m.parentElement; if (m) m.scrollTop -= 28; })()"); time.sleep(0.4)
            pg.screenshot(path=str(Path(SHOTS) / "studio-show-all.png"))
        pg.evaluate("document.querySelector('#sh-groups [data-sg=\"Работа\"]').click()"); time.sleep(1.2)
        vis = pg.evaluate(NAVVIS)
        ok(not any(x in vis for x in ("sites", "pbot", "prompter", "clients", "team", "mailing", "sitechat")), "группа «Работа» скрыта из меню: " + ", ".join(x for x in vis if x in ("sites", "pbot", "prompter", "clients", "team", "mailing", "sitechat")))
        ok(pg.evaluate("[...document.querySelectorAll('nav .ng')].filter(g => g.offsetParent).every(g => !g.textContent.includes('Работа'))"), "заголовок «Работа» в меню тоже пропал")
        s = json.loads((cfg / "settings.json").read_text())
        ok(not any(x in (s["ui"].get("home_apps") or []) for x in ("sites", "pbot", "clients", "team")) and "mailing" in (s["ui"].get("nav_hide") or []),
           "сохранено: значков работы нет на «Главной», «Рассылка» — в ui.nav_hide")
        nav("home"); time.sleep(1)
        apps = pg.evaluate("[...document.querySelectorAll('#hm-apps .hm-app')].map(a => a.dataset.app)")
        ok(not any(x in apps for x in ("sites", "pbot", "clients", "team")) and "chat" in apps, "и с «Главной» тоже: " + ", ".join(apps))
        # поиск находит скрытое
        pg.fill("#fd-q", "сайты"); time.sleep(0.6)
        hid = pg.evaluate("[...document.querySelectorAll('#fd-res .fd-row')].filter(r => r.querySelector('.fd-hid')).map(r => r.querySelector('b').textContent)")
        ok(any("Сайты" in h for h in hid), "поиск «сайты» находит скрытый раздел с подсказкой «раздел скрыт — показать?»: " + str(hid))
        pg.evaluate("[...document.querySelectorAll('#fd-res .fd-row')].find(r => r.querySelector('.fd-hid') && r.querySelector('b').textContent.includes('Сайты')).click()"); time.sleep(1.2)
        ok(pg.evaluate("document.querySelector('#p-sites').classList.contains('cur')") and "sites" in pg.evaluate(NAVVIS), "нажали — «Сайты» снова в меню и открыты")
        # набор «Минимум»
        nav("look"); time.sleep(0.6)
        pg.evaluate("document.querySelector('#sh-sets [data-set=\"min\"]').click()"); time.sleep(1.2)
        vis = set(pg.evaluate(NAVVIS))
        want = {"home", "chat", "calendar", "reminders", "notes", "close", "memory", "qa", "dw", "personas", "brain", "ears", "voice", "look", "sound", "hands", "skills", "features", "about"}
        ok(vis - {"soul", "const", "me"} == want, "«Минимум»: в меню только главное и настройки; лишнее: " + ", ".join(sorted(vis - want - {"soul", "const", "me"})) + "; нет: " + ", ".join(sorted(want - vis)))
        ok(pg.evaluate("document.querySelector('#sh-sets [aria-pressed=true]')?.dataset.set") == "min", "набор «Минимум» отмечен")
        if SHOTS:
            pg.evaluate("(() => { const h = document.getElementById('sh-h'); h.scrollIntoView({ block: 'start' }); let m = h.parentElement; while (m && m.scrollHeight <= m.clientHeight) m = m.parentElement; if (m) m.scrollTop -= 28; })()"); time.sleep(0.4)
            pg.screenshot(path=str(Path(SHOTS) / "studio-show-min.png"))
        nav("home"); time.sleep(1)
        apps = set(pg.evaluate("[...document.querySelectorAll('#hm-apps .hm-app')].map(a => a.dataset.app)"))
        ok(apps <= {"chat", "calendar", "reminders", "notes", "close", "memory", "qa"} and {"chat", "notes"} <= apps, "на «Главной» — только их значки: " + ", ".join(sorted(apps)))
        # переживает перезапуск окна
        pg.goto(url); pg.wait_for_selector("#conn.ok", timeout=30000); time.sleep(2.5)
        vis2 = set(pg.evaluate(NAVVIS)) - {"soul", "const", "me"}
        ok(vis2 == want, "после перезапуска студии меню то же: " + ", ".join(sorted(vis2 ^ want)))
        ok("pay_overview" not in calls() and "watch_get" not in calls() and "tasks_list" not in calls(),
           "скрытое не грузится: «Главная» не спрашивает платежи, дозор и задачи")
        # «Всё» — вернуть
        nav("look"); time.sleep(0.6)
        pg.evaluate("document.querySelector('#sh-sets [data-set=\"all\"]').click()"); time.sleep(1.2)
        vis = set(pg.evaluate(NAVVIS))
        ok({"sites", "pbot", "pay", "kids", "senior", "tasks", "council", "folder", "course", "servers"} <= vis, "«Всё» — всё снова в меню")

        # 5. «Облегчённый вид»
        blur = "[...document.querySelectorAll('*')].filter(e => { const c = getComputedStyle(e); return c.backdropFilter && c.backdropFilter !== 'none'; }).length"
        b0 = pg.evaluate(blur)
        pg.evaluate("document.querySelector('#lite-seg [data-v=\"on\"]').click()"); time.sleep(0.8)
        ok(pg.evaluate("document.documentElement.classList.contains('st-lite') && DewiarEntity.lite"), "«Облегчённый вид» включён — класс st-lite, облики реже")
        b1 = pg.evaluate(blur)
        ok(b0 > 0 and b1 == 0, f"размытие (backdrop-filter): было {b0} элементов — стало {b1}")
        ok("fixed" not in pg.evaluate("getComputedStyle(document.querySelector('nav')).backgroundAttachment") and
           "gradient" not in pg.evaluate("getComputedStyle(document.querySelector('.sh-g')).backgroundImage"),
           "«стекло» — без второй копии фона с background-attachment: fixed")
        ok(json.loads((cfg / "settings.json").read_text())["ui"].get("studio_lite") == "on", "выбор сохранён (ui.studio_lite)")
        pg.evaluate("document.querySelector('#lite-seg [data-v=\"off\"]').click()"); time.sleep(0.6)
        ok(not pg.evaluate("document.documentElement.classList.contains('st-lite')") and pg.evaluate(blur) > 0, "выключили — полный вид")
        ok(not errs, "без ошибок JavaScript: " + ("; ".join(errs[:5]) if errs else "нет"))
        b.close()
finally:
    core.terminate(); mock.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
