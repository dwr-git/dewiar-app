"""Список заметок на телефоне («Мой день» → «Заметки»), 03.11 — владелец прислал снимки: «одни заметки выглядят хорошо,
другие плохо, особенно с фото»: крупная миниатюра выбивалась из ряда, «•» стоял один на своей строке, пункты списка
были жирными и каждый с новой строки, счётчик 📎 уезжал на отдельную строку, ярлык папки стоял криво.

Проверяем карточку (app.js ntCard, mdPreview flat): у всех миниатюр один размер и они квадратные; 📎 и папка — в одной
мета-строке; заголовок — не больше двух строк, начало текста — не больше трёх; в начале текста нет строки из одного «•»
и нет <b>; пункты идут потоком через « · »; обычный mdPreview (без flat) по-прежнему выделяет заголовок жирным."""
import os, shutil, subprocess, sys, tempfile
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
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
SETUP = r"""(skin) => {
  const wide = 'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="400"><rect width="900" height="400" fill="#f96"/></svg>');
  const tall = 'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="1200"><rect width="300" height="1200" fill="#3a7"/></svg>');
  fileSave('natt-p1', wide); fileSave('natt-p2', tall); fileSave('natt-p3', wide);
  const t = Date.now();
  saveNotes([
    { id: 'n1', title: 'Посмотреть фото', folder: 'Напоминания', time: t, att: [{ id: 'p1', name: 'скрин.png', type: 'image', size: 10 }],
      text: 'Напоминание — 4 ноября в 10:00.\n\n«Лира, напомни завтра в 10 посмотреть эти скрины»' },
    { id: 'n2', title: 'Покупки на неделю', folder: 'Дом', time: t - 1e5, att: [{ id: 'p2', name: 'список.jpg', type: 'image', size: 10 }],
      text: 'Что купить\n\n## Продукты\n\n- **молоко** 2 л\n- хлеб\n•\n-\n- яйца\n- [ ] сыр\n\n## Хозяйство\n\n* порошок' },
    { id: 'n3', title: 'Без фото', time: t - 2e5, text: 'Плед или **сертификат в спа**. Спросить у Оли.' },
    { id: 'n4', title: 'Очень длинное название заметки про ремонт кухни, плитку, свет, розетки и всё, что нужно не забыть сделать до зимы, пока не поздно', folder: 'Работа/Проекты', time: t - 3e5,
      text: 'Сначала замерить стены. '.repeat(30) },
    { id: 'n5', title: 'Чеки', folder: 'Финансы', time: t - 4e5,
      att: [{ id: 'p3', name: 'чек1.jpg', type: 'image', size: 10 }, { id: 'p1', name: 'чек2.jpg', type: 'image', size: 10 }, { id: 'p9', name: 'выписка.pdf', type: 'file', size: 10 }],
      text: '1. Аптека\n2. Продукты' },
  ]);
  S.skin = skin; applyLook();
  openSheet('#sh-day'); dayTab = 'notes'; renderDay();
}"""
MEASURE = r"""() => [...document.querySelectorAll('#day-body .it.note')].map(c => {
  const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; };
  const lh = (el) => parseFloat(getComputedStyle(el).lineHeight);
  const t = c.querySelector('.ntt'), pv = c.querySelector('.ntpv'), m = c.querySelector('.ntm'), clip = c.querySelector('.ntc');
  return { id: c.dataset.id, card: r(c), thumb: r(c.querySelector('.nthumb')), img: r(c.querySelector('.nthumb img')), n: (c.querySelector('.ntn') || {}).textContent || '',
    title: r(t), titleLh: lh(t), pv: pv ? r(pv) : null, pvLh: pv ? lh(pv) : 0, pvHtml: pv ? pv.innerHTML : '', pvText: pv ? pv.innerText : '',
    meta: r(m), metaText: m ? m.innerText : '', clip: r(clip), clipText: clip ? clip.textContent : '', clipInMeta: !!(clip && clip.parentElement === m),
    fold: r(c.querySelector('.ntf')), foldText: (c.querySelector('.ntf') || {}).textContent || '' };
})"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for skin in ("neusky", "graphite"):
        pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        pg.evaluate(SETUP, skin); pg.wait_for_timeout(500)
        cards = {c["id"]: c for c in pg.evaluate(MEASURE)}
        ok(len(cards) == 5, f"[{skin}] в списке пять заметок: {list(cards)}")
        th = [(c["id"], round(c["thumb"]["w"]), round(c["thumb"]["h"])) for c in cards.values() if c["thumb"]]
        ok(len(th) == 3 and len({(w, h) for _, w, h in th}) == 1 and all(w == h and 40 <= w <= 72 for _, w, h in th),
           f"[{skin}] у всех миниатюр один размер, квадрат (широкое и высокое фото одинаково): {th}")
        ok(all(c["img"]["w"] == c["thumb"]["w"] and c["img"]["h"] == c["thumb"]["h"] for c in cards.values() if c["thumb"]),
           f"[{skin}] фото заполняет миниатюру, не растягивает её")
        ok(all(c["card"]["h"] < 150 for c in cards.values() if c["thumb"]), f"[{skin}] фото не растягивает ряд: {[round(c['card']['h']) for c in cards.values()]}")
        ok(all(c["thumb"]["x"] > c["title"]["x"] + c["title"]["w"] - 1 for c in cards.values() if c["thumb"]), f"[{skin}] миниатюра справа от текста, не наезжает")
        ok(cards["n5"]["n"] == "2" and cards["n1"]["n"] == "", f"[{skin}] несколько фото — счётчик на миниатюре ({cards['n5']['n']!r}), одно — без него")
        # 📎 и папка — в мета-строке, в один ряд
        for i in ("n1", "n2", "n5"):
            c = cards[i]
            ok(c["clipInMeta"] and c["clip"]["h"] < 26 and abs((c["clip"]["y"] + c["clip"]["h"] / 2) - (c["fold"]["y"] + c["fold"]["h"] / 2)) < 3
               and c["meta"]["h"] < 30, f"[{skin}] {i}: 📎 и папка — одной строкой мета-части (мета {round(c['meta']['h'])} px)")
            ok(c["clip"]["y"] >= c["title"]["y"] + c["title"]["h"] - 1, f"[{skin}] {i}: 📎 не в заголовке, а под ним")
        ok(cards["n5"]["clipText"].strip() == "3" and cards["n1"]["clipText"].strip() == "1", f"[{skin}] 📎 — число вложений: {cards['n5']['clipText']!r}")
        ok(cards["n4"]["foldText"] == "Проекты" and cards["n3"]["fold"] is None and cards["n3"]["clip"] is None, f"[{skin}] папка — последним словом пути; без папки и вложений — без пилюль")
        # заголовок и начало текста — с многоточием
        ok(cards["n4"]["title"]["h"] <= 2 * cards["n4"]["titleLh"] + 2, f"[{skin}] длинный заголовок — не больше двух строк ({round(cards['n4']['title']['h'])} px)")
        ok(cards["n4"]["pv"]["h"] <= 3 * cards["n4"]["pvLh"] + 2, f"[{skin}] длинное начало текста — не больше трёх строк ({round(cards['n4']['pv']['h'])} px)")
        # начало текста: без одинокого «•», без жирного, пункты потоком
        pv = cards["n2"]
        lines = [l.strip() for l in pv["pvText"].split("\n")]
        ok(not any(l in ("•", "-", "*", "·") for l in lines) and " • " not in pv["pvText"] and "• ·" not in pv["pvText"], f"[{skin}] в превью нет строки из одного «•»: {pv['pvText']!r}")
        ok(all("<b" not in c["pvHtml"] for c in cards.values()), f"[{skin}] в превью нет <b> (пункты и заголовки не жирные)")
        ok("молоко 2 л · хлеб · яйца" in pv["pvText"] and "Продукты:" in pv["pvText"] and "**" not in pv["pvText"], f"[{skin}] пункты списка — потоком через « · »: {pv['pvText']!r}")
        ok("*" not in cards["n3"]["pvText"] and "сертификат в спа" in cards["n3"]["pvText"], f"[{skin}] **жирное** — без звёздочек: {cards['n3']['pvText']!r}")
        ok(pg.evaluate("getComputedStyle(document.querySelector('#day-body .it.note')).contentVisibility") == "auto", f"[{skin}] карточки вне экрана не рисуются (content-visibility)")
        pg.click("#day-body .it.note[data-id='n3']"); pg.wait_for_timeout(300)
        ok(pg.is_visible("#sh-note.on") and pg.inner_text("#nt-h") == "Без фото", f"[{skin}] нажали карточку — открылась заметка")
        pg.close()
    # mdPreview по умолчанию (не flat) — как было: заголовок жирным, пункты «•»; пустой пункт не показывается и там
    pg = b.new_page(); pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(600)
    h = pg.evaluate("mdPreview('## План\\n\\n- раз\\n•\\n- два')")
    ok(h.startswith("<b>План</b>") and "• раз" in h and "• два" in h and "• •" not in h and not h.rstrip().endswith("•"), f"mdPreview без flat — прежний вид: {h!r}")
    f = pg.evaluate("mdPreview('- [ ] сыр\\n- [x] кофе', 220, { flat: true })")
    ok(f == "☐ сыр · ☑ кофе", f"дела — значком, не отрываясь от слова: {f!r}")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
shutil.rmtree(tmp, ignore_errors=True)
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
