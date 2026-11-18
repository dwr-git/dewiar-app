"""«Взять с сайта» (18.11, «Компания»: «минимум ручных настроек»): знания консультанта — с сайта компании. Главная и до
8 страниц того же сайта, похожих на цены, услуги, контакты, доставку, вопросы; текстом — заголовки и абзацы строками, без
скриптов, меню и повторов (шапка и подвал на каждой странице — один раз); чужие сайты и картинки не трогаем. В студии —
поле и кнопка под «Знаниями»: текст добавляется к знаниям, человек правит сам."""
import http.server, os, re, sys, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


HEAD = '<html><head><title>{t}</title><script>var x = "секрет скрипта";</script></head><body><nav><a href="/">Главная</a> Меню сайта</nav><header>Электро Плюс — электромонтаж</header>'
FOOT = '<footer>© Электро Плюс, все права</footer></body></html>'
PAGES = {
    "/": HEAD.format(t="Электро Плюс") + '<h1>Электромонтаж в Минске</h1><p>Работаем с 9 до 20, без выходных.</p>'
         '<a href="/prices">Цены</a> <a href="/uslugi/">Услуги</a> <a href="/kontakty">Контакты</a> <a href="/blog/news-1">Новость</a>'
         '<a href="https://other.example/prices">Чужие цены</a> <a href="/price.pdf">Прайс PDF</a>' + FOOT,
    "/prices": HEAD.format(t="Цены — Электро Плюс") + '<h2>Цены</h2><ul><li>Замена проводки — от 1200 ₽ за точку</li><li>Розетка — 450 ₽</li></ul>' + FOOT,
    "/uslugi/": HEAD.format(t="Услуги") + '<h2>Услуги</h2><p>Проводка в квартирах и домах, щиты, освещение.</p>' + FOOT,
    "/kontakty": HEAD.format(t="Контакты") + '<p>Телефон: +375 29 000-00-00. Адрес: ул. Примерная, 1.</p>' + FOOT,
}
SEEN = []


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        SEEN.append(self.path)
        b = PAGES.get(self.path)
        if b is None:
            self.send_response(404); self.end_headers(); return
        b = b.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
import sitechat  # noqa: E402

W = sitechat.SiteChat.__new__(sitechat.SiteChat)
d = W.from_site(f"http://127.0.0.1:{srv.server_address[1]}/")
t = d["text"]
ok(len(d["pages"]) == 4 and [p["title"] for p in d["pages"]] == ["Электро Плюс", "Цены — Электро Плюс", "Услуги", "Контакты"],
   f"главная и три страницы — цены, услуги, контакты: {[p['title'] for p in d['pages']]}")
ok("/blog/news-1" not in SEEN and "/price.pdf" not in SEEN, "новость и PDF не читаем: только страницы о ценах, услугах, контактах")
ok("Замена проводки — от 1200 ₽ за точку" in t and "Работаем с 9 до 20" in t and "+375 29 000-00-00" in t, "цены, часы и контакты — в тексте")
ok("секрет скрипта" not in t and "Меню сайта" not in t and t.count("Электро Плюс — электромонтаж") == 1 and t.count("© Электро Плюс") <= 1,
   "без скриптов и меню; шапка и подвал — один раз")
ok("• Розетка — 450 ₽" in t, "пункты списков — строками")
try:
    W.from_site("нет"); ok(False, "кривой адрес — отказ")
except sitechat.SiteChatError as e:
    ok("адрес" in str(e), f"кривой адрес — «{e}»")
srv.shutdown()
js = (ROOT / "ui/studio/sitechat.js").read_text(encoding="utf-8")
ok('core.call("sitechat_from_site", { url })' in js and "kb.value" in js and "scDraft()" in js, "студия: «Взять с сайта» — текст добавляется к знаниям и сохраняется черновиком")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
