"""Телефон, «Близкие» (29.10, владелец, снимки): «Рефералы — в совсем другом стиле, тёмный; надписи вкладок обрезаны — может
иконками»; «Семья — без структуры, форма не в стиле, всё в кучу»; «фото пользователя, если загрузил себе на аватарку».
Вкладки — значок и подпись; созвездие в светлой теме — светлое; фото — в звёздах и в списке; «Семья» — карточками,
платёж — «что · до когда · кто», кнопки под ним, просрочен — фоном, без рамок; «+ Платёж» — форма, кто платит — чипами;
позвать — нажатием на имя."""
import os, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


w = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
D = {"code": "K7QX2M", "link": "https://dewiar.pro/r/K7QX2M", "bonus": 3, "bonus_new": 1, "days": 3, "earned": 6, "opened": 5, "can_use": True,
     "by": {"rid": "r0", "name": "Сергей", "paid": 1},
     "invited": [{"rid": "r1", "name": "Анна", "paid": 1, "days": 3, "need": 3}, {"rid": "r2", "name": "Олег", "why": "topup"}]}
PEOPLE = [{"pid": "pA", "name": "Анна", "devs": ["d1"], "face": 2}, {"pid": "pL", "name": "Людмила Исаева", "devs": [], "face": 1}, {"pid": "pK", "name": "Костя", "devs": []}]
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.route("https://**", lambda r: r.abort())
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("""([d, pe]) => { S.llm = Object.assign({}, S.llm, { cloud: true, api_key: 'dw-x' }); S.user_name = 'Михаил';
      S.features = Object.assign({}, S.features, { family: true, near: true, meet: true, close: true });
      cloudGet = async () => d; syncCred = () => ({ token: 'dw-x', base: 'https://x/cloud.php' }); clKeys = () => ({ dev: 'd', pub: 'p' });
      clReq = async (m, path) => path === '/close/refs' ? { map: { r1: { pid: 'pA' } } } : {};
      clHello = async () => ({}); window._faces = [];
      const ph = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="#c06"/></svg>');
      clFace = async (id, v) => { _faces.push(id); return ph; };
      const st = clLoad(); st.me = { pid: 'me', name: 'Михаил', face: 3 }; st.people = pe; document.body.classList.add('light'); }""", [D, PEOPLE])
    pg.evaluate("openRefs()"); pg.wait_for_timeout(1500)
    r = pg.evaluate("""() => [[...document.querySelectorAll('#cl-tabs button')].map(b => [b.textContent.trim(), !!b.querySelector('svg')]),
      [...document.querySelectorAll('#cl-tabs button span')].every(s => s.scrollWidth <= s.clientWidth + 1),
      document.querySelector('#rf-net .rn').classList.contains('light'), getComputedStyle(document.querySelector('#rf-net .rn')).backgroundImage.includes('255, 255, 255'),
      document.querySelectorAll('#rf-net svg image').length, !!document.querySelector('#rf-body .rfp .clava.has-face')]""")
    ok([t for t, _ in r[0]] == ["Близкие", "Семья", "Рядом", "Встречи", "Рефералы"] and all(i for _, i in r[0]) and r[1], f"вкладки — значок и подпись, подписи не обрезаны: {r[0]}")
    ok(r[2] and r[3], "светлая тема — созвездие светлое, не тёмный космос")
    ok(r[4] >= 2 and r[5], f"фото: своё и друга из «Близких» — в звёздах ({r[4]}) и в списке")
    if SHOTS: pg.screenshot(path=f"{SHOTS}/phone-refs-light.png")
    today = time.strftime("%Y-%m-%d")
    pg.evaluate("""(today) => { const F = famLoad(); F.members = { pL: { name: 'Людмила Исаева', st: 'joined' } };
      const ts = Date.now(); F.ledger = [{ id: 'a', who: '', name: 'Михаил', amount: 46.2, note: 'продукты', date: today, ts: ts - 3600e3 }];
      F.bills = { e: { id: 'e', name: 'Интернет', amount: 25, due: '2020-01-02', payer: 'Людмила Исаева' } }; F.limit = { v: 500, at: 1 }; famSave(); clTab = 'fam'; clRender(); }""", today)
    pg.wait_for_timeout(500)
    r = pg.evaluate("""() => { const bill = document.querySelector('#fam-body .fmbill'), cs = getComputedStyle(bill);
      return [document.querySelectorAll('#fam-body section.card').length, bill.className, cs.boxShadow, cs.backgroundColor, bill.querySelector('small').textContent,
        !!bill.querySelector('.fmbact [data-paid]') && !!bill.querySelector('.fmbact [data-rem]'), bill.querySelector('.fmbt').getBoundingClientRect().height,
        document.querySelector('#fam-body').innerText.includes('из 500 на месяц'), !!document.querySelector('#fam-body select'), document.querySelectorAll('#fam-body [data-inv]').length,
        !!document.querySelector('#fam-body .fmava.has-face')]; }""")
    ok(r[0] == 4, f"«Семья» — четыре карточки: месяц, платежи, траты, кто в семье ({r[0]})")
    ok("late" in r[1] and r[2] in ("none", "") and r[3] != "rgba(0, 0, 0, 0)" and r[4].startswith("просрочен") and "платит Людмила" in r[4],
       f"просроченный платёж — фоном, без рамки; «просрочен · платит Людмила»: {r[1:5]}")
    ok(r[5] and r[6] < 50, f"«Оплачено» и «Напомнить» — под строкой, текст не сжат в столбик (высота {r[6]:.0f})")
    ok(r[7] and not r[8] and r[9] == 2, f"лимит на месте; выпадающих списков нет; позвать — нажатием на имя (Анна, Костя): {r[7:10]}")
    ok(r[10], "фото в «Семье» — как в «Близких»")
    pg.click("#fm-addb"); pg.wait_for_timeout(200)
    pg.fill("#fm-bn", "Свет"); pg.fill("#fm-ba", "54,3".replace(",", ".")); pg.click('#fam-body [data-payer="Людмила Исаева"]'); pg.click("#fm-bgo"); pg.wait_for_timeout(300)
    bl = pg.evaluate("Object.values(famLoad().bills).find(b => b.name === 'Свет')")
    ok(bl and bl["payer"] == "Людмила Исаева" and bl["amount"] == 54.3 and not pg.evaluate("!!document.querySelector('#fm-bn')"), f"«+ Платёж» — кто платит чипом, форма закрылась: {bl}")
    if SHOTS: pg.screenshot(path=f"{SHOTS}/phone-family.png", full_page=True)
    sw = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(sw <= 0, f"без прокрутки вбок ({sw})")
    b.close()
ok(not errs, f"без ошибок: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
