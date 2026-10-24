"""Объявления для всех — телефон (24.10): ?p=/news без ключа; новое — карточка с фото, текстом и кнопкой ссылки, один раз
(S.annSeen); в разговоре, в игре и поверх другого листа — ждёт; уведомление службы (action news) открывает последнее.
Служба «Близких» (CloseLive) берёт объявление из ответа /close/wait и показывает уведомление один раз по номеру."""
import json, os, re, subprocess, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


NEWS = [{"id": 7, "ts": 1761300000, "title": "Новая сказка «Огонёк»", "text": "В «Досуге» — атмосферная сказка.\nПопробуйте!", "level": "info",
         "link": "https://dewiar.pro/", "link_label": "Посмотреть", "until": 0, "img": "/news/img&id=7"},
        {"id": 6, "ts": 1761290000, "title": "Сегодня экзамен", "text": "Ответы медленнее.", "level": "warn", "link": "", "link_label": "", "until": 0, "img": ""}]
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0000003010100c9fe92ef0000000049454e44ae426082")
    pg.route(re.compile(r"news/img"), lambda r: r.fulfill(status=200, content_type="image/png", body=PNG))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("""(n) => { window.NEWS = n; window.opened = []; window.asked = [];
      http = async (m, u) => { asked.push(u); return { status: 200, body: JSON.stringify({ ok: true, items: NEWS }) }; };
      D.openUrl = (u) => { opened.push(u); return true; }; }""", NEWS)
    pg.evaluate("annCheck(false)"); pg.wait_for_timeout(500)
    ok(pg.evaluate("$('#sh-ann').classList.contains('on')") and pg.inner_text("#ann-body h2") == "Новая сказка «Огонёк»", "новое объявление — карточка сама, новое первым")
    ok(pg.evaluate("asked[0]").endswith("cloud.php?p=/news") and pg.evaluate("$('#ann-body .nw-img').getAttribute('src')").endswith("cloud.php?p=/news/img&id=7"),
       "спрашивает ?p=/news без входа; фото — с того же облака")
    ok("Попробуйте!" in pg.inner_text("#ann-body .nw-t") and pg.evaluate("getComputedStyle($('#ann-body .nw-t')).whiteSpace") == "pre-wrap", "текст — с переносами строк")
    pg.click("#an-go"); ok(pg.evaluate("opened") == ["https://dewiar.pro/"], "кнопка ссылки открывает видео или страницу")
    pg.click("#an-ok"); pg.wait_for_timeout(300)
    ok(not pg.evaluate("$('#sh-ann').classList.contains('on')") and pg.evaluate("S.annSeen") == 7, "«Понятно» — закрыто, номер запомнен")
    pg.evaluate("annAt = 0; annCheck(false)"); pg.wait_for_timeout(400)
    ok(not pg.evaluate("$('#sh-ann').classList.contains('on')"), "второй раз то же объявление не всплывает")
    pg.evaluate("NEWS.unshift({ id: 8, ts: 1761310000, title: 'Сервер на обслуживании', text: '10 минут.', level: 'warn', link: '', img: '' })")
    pg.evaluate("openSheet('#sh-play'); annAt = 0; annCheck(false)"); pg.wait_for_timeout(400)
    ok(not pg.evaluate("$('#sh-ann').classList.contains('on')") and pg.evaluate("S.annSeen") == 7, "открыт другой лист — объявление подождёт")
    pg.evaluate("closeSheets(); handleIntent({ action: 'news' })"); pg.wait_for_timeout(500)
    ok(pg.evaluate("$('#sh-ann').classList.contains('on')") and pg.inner_text("#ann-body h2") == "Сервер на обслуживании" and pg.evaluate("$('#ann-body .nw-k').classList.contains('warn')")
       and not pg.query_selector("#an-go"), "уведомление открывает новое; предупреждение — своим цветом, без ссылки — без кнопки")
    # №245: сначала «Что нового» (там своё «Понятно»), потом объявление — его «Понятно» закрывает именно его
    pg.evaluate("closeSheets(); newsShow([{ phone: '0.6.98', items: [{ title: 'Новое', text: 'Текст' }] }]); closeSheets(); annShow(NEWS[0])"); pg.wait_for_timeout(400)
    pg.click("#an-ok"); pg.wait_for_timeout(400)
    ok(not pg.evaluate("$('#sh-ann').classList.contains('on')"), "«Понятно» объявления закрывает его, даже если раньше открывали «Что нового» (№245)")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
import collections
ids = collections.Counter(re.findall(r'\bid="([^"]+)"', (ROOT / "android/assets/www/index.html").read_text(encoding="utf-8")))
ok(not [k for k, v in ids.items() if v > 1], f"в index.html нет повторяющихся id (лист «Что нового» и лист объявления — разные): {[k for k, v in ids.items() if v > 1]}")
cl = (ROOT / "android/src/pro/dewiar/app/CloseLive.java").read_text(encoding="utf-8")
ok('d.optJSONObject("news")' in cl and 'pr.getLong("news_notified", 0)' in cl and '"pro.dewiar.NEWS"' in cl, "служба: уведомление объявления один раз по номеру")
ma = (ROOT / "android/src/pro/dewiar/app/MainActivity.java").read_text(encoding="utf-8")
ok('"pro.dewiar.NEWS".equals(a)' in ma and '.put("action", "news")' in ma, "нажатие уведомления — открывает объявление в приложении")
if fails:
    raise SystemExit(1)
