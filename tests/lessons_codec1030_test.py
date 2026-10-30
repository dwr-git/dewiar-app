"""Видеоуроки на Ubuntu (30.10, владелец, 0.70: «на убунте не открывается видео, только в браузере»): окну программы
(WebKitGTK) для MP4 нужен gstreamer1.0-libav — при обновлении поверх старой версии его не ставят.
Кодека нет — окно знает сразу (canPlayType пустой): без 8 секунд чёрного экрана — «Установить видеокодек» и «Смотреть
в браузере»; кнопка ставит пакет через pkexec apt-get (система спросит пароль), затем «Перезапустить Dewiar».
На Windows и в браузере кнопки кодека нет. Ядро окна: install_codec — только этот пакет, ошибки понятным языком."""
import json, os, re, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('["pkexec", "apt-get", "install", "-y", "gstreamer1.0-libav"]' in src and "def install_codec(self)" in src, "окно: install_codec ставит только gstreamer1.0-libav через pkexec")
ok("gstreamer1.0-libav" in (ROOT / "packaging/DEBIAN/control").read_text(), "пакет по-прежнему рекомендует кодек")

# install_codec без окна: подменяем команду
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
try:
    import app as A  # noqa: E402
    api = A.Api.__new__(A.Api)
    os.environ["DEWIAR_CODEC_CMD"] = "true"
    ok(A.Api.install_codec(api) == {"ok": True}, "команда прошла — {ok: true}")
    os.environ["DEWIAR_CODEC_CMD"] = "false"
    r = A.Api.install_codec(api)
    ok(r["ok"] is False and "apt не поставил" in r["error"], f"не вышло — понятная ошибка: {r}")
    os.environ.pop("DEWIAR_CODEC_CMD")
except ImportError as e:
    print(f"окно (pywebview) не импортируется здесь — пропускаю: {e}")

ITEMS = [{"id": "02-watch", "n": 2, "title": "Дозор", "about": "", "sec": 60, "video": "https://x.test/a.mp4", "poster": "", "youtube": ""}]
CORE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); if (c === "academy_list") return { ok: true, items: ITEMS }; return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("ITEMS", json.dumps(ITEMS))
NOCODEC = "HTMLMediaElement.prototype.canPlayType = () => '';"
API = """window.pywebview = { api: new Proxy({}, { get: (_, k) => k === 'install_codec' ? (() => { window.inst = (window.inst || 0) + 1; return new Promise(r => setTimeout(() => r(window.INST || { ok: true }), 300)); })
  : k === 'restart' ? ((n) => { window.restarted = n; return Promise.resolve(true); }) : () => Promise.resolve(true) }) };"""
SHOT = os.environ.get("DEWIAR_SHOTS")
LINUX = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
WINUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 Edg/130.0"


def page(b, ua, *scripts):
    ctx = b.new_context(viewport={"width": 1300, "height": 900}, user_agent=ua)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    for s in scripts:
        pg.add_init_script(s)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1300)
    pg.evaluate("document.querySelector('nav button[data-p=\"lessons\"]').click()"); pg.wait_for_timeout(400)
    pg.locator("#ls-grid .ls-card").nth(0).click()
    return pg


with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = page(b, LINUX, API, NOCODEC, CORE); pg.wait_for_timeout(400)
    ok(pg.is_visible("#ls-fail") and pg.is_visible("#ls-codec") and "одной кнопкой" in pg.inner_text("#ls-fail-why"),
       "Ubuntu без кодека — сразу, без 8 секунд чёрного экрана: «Установить видеокодек» и «Смотреть в браузере»")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "lessons-codec.png"))
    pg.click("#ls-codec"); pg.wait_for_timeout(100)
    ok("пароль" in pg.inner_text("#ls-codec") and pg.is_disabled("#ls-codec"), "ставим — «введите пароль в окне системы», кнопка ждёт")
    pg.wait_for_timeout(500)
    ok(pg.evaluate("window.inst") == 1 and pg.inner_text("#ls-codec") == "Перезапустить Dewiar" and "установлен" in pg.inner_text("#ls-fail-why"),
       "поставили — «Перезапустить Dewiar»")
    pg.click("#ls-codec"); pg.wait_for_timeout(200)
    ok("Видеокодек установлен" in (pg.evaluate("window.restarted") or ""), "перезапуск — с понятной заметкой")
    pg.close()
    pg = page(b, LINUX, API, NOCODEC, CORE, "window.INST = { ok: false, error: 'окно пароля закрыли — нажмите ещё раз и введите пароль от компьютера' };"); pg.wait_for_timeout(400)
    pg.click("#ls-codec"); pg.wait_for_timeout(600)
    ok(pg.inner_text("#ls-codec") == "Установить видеокодек" and "окно пароля закрыли" in pg.inner_text("#ls-fail-why"), "закрыли окно пароля — можно ещё раз, причина видна")
    pg.close()
    pg = page(b, WINUA, API, NOCODEC, CORE); pg.wait_for_timeout(400)
    ok(pg.is_visible("#ls-fail") and not pg.is_visible("#ls-codec") and "одной кнопкой" not in pg.inner_text("#ls-fail-why"),
       "Windows: видео не пошло — только «Смотреть в браузере», без кнопки кодека")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
