"""№552 и идея №140 (пакет 05.11): «Раздел „Сайты“: добавь поле для вставки ссылки на сайт-референс, по которому
пользователь хочет создать свой сайт». Теперь: поле «Сайт-образец» в «Сайтах» и ref у site_create — Лира читает схему
страницы (заголовок, разделы по порядку, меню, кнопки, цвета — без её текстов) и делает по мотивам: разделы и тон, но
тексты, названия и бренды — свои. Образец не открылся — сайт всё равно делается по описанию."""
import json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_DRY_TOOLS=str(tmp / "dry.txt"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


PAGE = """<!doctype html><html><head><title>Академия Нейро — курсы ИИ</title><style>.x{color:#1a73e8}</style>
<script>var secret = "не брать";</script></head><body style="background:#0b1020">
<nav><a href="#">Курсы</a><a href="#">Преподаватели</a><a href="#">Цены</a><a href="#">Контакты</a></nav>
<h1>Станьте специалистом по ИИ за 3 месяца</h1><p>Уникальная авторская методика Ивана Петрова, только у нас, звоните +7 999 123-45-67.</p>
<h2>Программа курса</h2><h2>Наши выпускники</h2><h2>Тарифы</h2><h3>Частые вопросы</h3>
<button>Записаться на курс</button><button>Скачать программу</button><div style="color:#1a73e8;border-color:#ff6d00"></div></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = PAGE.encode() if self.path == "/" else b"nope"
        self.send_response(200 if self.path == "/" else 404); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/"

import sites  # noqa: E402
import tools as TL  # noqa: E402

o = sites.ref_outline(URL)
ok("Академия Нейро" in o and "H1: Станьте специалистом по ИИ за 3 месяца · H2: Программа курса · H2: Наши выпускники" in o,
   f"схема образца: заголовок и разделы по порядку:\n{o}")
ok("Курсы, Преподаватели, Цены, Контакты" in o and "Записаться на курс" in o and "#1a73e8" in o, "меню, кнопки, цвета")
ok("методика Ивана Петрова" not in o and "+7 999" not in o and "не брать" not in o, "тексты абзацев, телефоны и скрипты образца — не берём")

seen = []


def llm(system, user):
    seen.append(user)
    return json.dumps({"name": "ИИ-школа «Старт»", "tagline": "Профессия в ИИ с нуля"})


W = sites.Sites(tmp / "sites", None, llm=llm)
s = W.create(describe="Онлайн-школа ИИ для новичков, Минск", ref=URL)
u = seen[-1] if seen else ""
ok(s.get("ref") == URL and "САЙТ-ОБРАЗЕЦ" in u and "НЕ копируй его тексты, названия, бренды" in u and "Программа курса" in u,
   "в подсказке модели — схема образца и запрет копировать тексты и бренды")
ok(s["name"] == "ИИ-школа «Старт»", "тексты и название — свои")
seen.clear()
s2 = W.create(describe="Кофейня у дома", ref=URL + "missing")
ok(s2.get("ref") is None and seen and "САЙТ-ОБРАЗЕЦ" not in seen[-1], "образец не открылся — сайт по описанию, без ошибки")
try:
    sites.ref_outline("не адрес")
    ok(False, "не адрес — должна быть ошибка")
except sites.SiteError:
    ok(True, "не адрес — понятный отказ")

# инструмент и студия
spec = TL.TOOLS["site_create"]
ok("ref" in json.dumps(spec[1]) and "сайт-образец" in spec[0], "site_create принимает ref — «сделай как у …»")
cmd = (ROOT / "core" / "engine_commands.py").read_text(encoding="utf-8")
ok('ref=str(a.get("ref") or "")' in cmd, "команда студии передаёт ссылку")
html = (ROOT / "ui" / "settings.html").read_text(encoding="utf-8")
js = (ROOT / "ui" / "studio" / "sites.js").read_text(encoding="utf-8")
ok('id="st-ref"' in html and "Сайт-образец" in html and "ref ? { ref } : {}" in js, "в «Сайтах» — поле «Сайт-образец»")
srv.shutdown()
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
