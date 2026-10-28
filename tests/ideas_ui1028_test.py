"""«Идеи Лиры» в программе (0.59): студия — раздел в меню, «Опишите идею» ищет похожие (поддержать голосом) или
«Предложить идею»; вкладки «Будем делать» / «Сделано» / «Мои», поиск, страницы, голос (снять), «новое» с прошлого раза;
виджет — лампочка у жучка; телефон — лист «Идеи» из «Сообщить о проблеме»."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = Path(os.environ.get("DEWIAR_SHOTS") or "/tmp")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


MOCK = """() => {
  const now = Math.floor(Date.now() / 1000);
  window._ideas = [
    { id: 7, title: 'Мультфильмы-уроки по возможностям Лиры', body: 'Короткие ролики: что умеет Лира и как попросить — внутри Лиры и на YouTube.', status: 'doing', votes: 41, voted: true, mine: false, plan_ts: now - 99999, ts: now - 99999, reply: '', ver: '' },
    { id: 3, title: 'Тёмная тема в «Календаре»', body: 'Ночью глаза устают.', status: 'plan', votes: 17, voted: false, mine: true, plan_ts: now - 10, ts: now - 900000, reply: 'Возьмём в 0.60', ver: '' },
    { id: 9, title: 'Голосовые заметки на часах', body: '', status: 'plan', votes: 6, voted: false, mine: false, plan_ts: now - 5, ts: now - 5, reply: '', ver: '' }];
  window._done = [{ id: 2, title: 'Синхронизация телефона по Wi-Fi без интернета', body: '', status: 'done', votes: 58, voted: true, mine: false, plan_ts: 1, done_ts: now, ts: 1, reply: '', ver: '0.59' }];
  window._calls = [];
  core.call = (c, a) => { _calls.push([c, a]);
    if (c === 'ideas_list') {
      let items = a.tab === 'done' ? _done : a.tab === 'mine' ? _ideas.filter(x => x.mine) : _ideas;
      if (a.q) items = items.filter(x => (x.title + x.body).toLowerCase().includes(a.q.toLowerCase()));
      return Promise.resolve({ items, total: items.length, pages: a.tab === 'plan' && !a.q ? 2 : 1, page: a.page || 1, counts: { plan: 3, done: 1, mine: 1 }, now }); }
    if (c === 'ideas_similar') return Promise.resolve({ items: /темн|тём/i.test(a.q) ? [_ideas[1]] : [] });
    if (c === 'ideas_vote') { const x = _ideas.find(y => y.id === a.id); x.voted = a.on; x.votes += a.on ? 1 : -1; return Promise.resolve({ id: a.id, votes: x.votes, voted: a.on }); }
    if (c === 'ideas_new') return Promise.resolve({ item: { id: 11, title: a.title, status: 'new' }, text: 'Спасибо! Идея на рассмотрении — когда её возьмут в план, за неё смогут голосовать все.' });
    return Promise.resolve({}); };
  try { localStorage.setItem('id_seen', String(now - 60)); } catch (e) { }
  ID.seen = now - 60;
  document.querySelector('nav button[data-p=ideas]').click(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1300, "height": 1100}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate(MOCK); pg.wait_for_timeout(600)
    ok(pg.is_visible("#p-ideas") and pg.inner_text("#p-ideas h1").startswith("Идеи Лиры"), "в меню — «Идеи Лиры», раздел открывается")
    items = pg.locator("#id-list .id-it")
    ok(items.count() == 3 and "делаем" in items.nth(0).inner_text() and "41" in items.nth(0).inner_text(), "«Будем делать»: по голосам, «делаем» — пометкой")
    ok(pg.get_attribute("#id-list [data-id='7'] .id-vote", "aria-pressed") == "true", "свой голос — отмечен")
    t3 = pg.inner_text("#id-list [data-id='3']")
    ok("ваша" in t3 and "новое" in t3 and "Ответ разработчика: Возьмём в 0.60" in t3, f"своя идея — «ваша», свежая в плане — «новое», ответ разработчика: {t3!r}")
    ok(pg.inner_text("#id-n-plan") == "3" and pg.inner_text("#id-n-done") == "1", "на вкладках — сколько")
    ok(pg.locator("#id-pager button").count() == 2, "страницы")
    pg.screenshot(path=str(SHOTS / "ideas-studio.png"))
    # голос
    pg.click("#id-list [data-id='9'] .id-vote"); pg.wait_for_timeout(300)
    ok(pg.inner_text("#id-list [data-id='9'] .id-vote b") == "7" and pg.get_attribute("#id-list [data-id='9'] .id-vote", "aria-pressed") == "true",
       "поддержать — голос засчитан, число выросло")
    pg.click("#id-list [data-id='9'] .id-vote"); pg.wait_for_timeout(300)
    ok(pg.inner_text("#id-list [data-id='9'] .id-vote b") == "6", "нажать ещё раз — голос снят")
    # похожие
    pg.fill("#id-q", "Тёмная тема для календаря"); pg.wait_for_timeout(700)
    ok(pg.is_visible("#id-sim") and "уже есть" in pg.inner_text("#id-sim") and "Тёмная тема" in pg.inner_text("#id-sim")
       and pg.inner_text("#id-send") == "Моя — другая, предложить", "пишу идею — похожая уже есть: поддержать голосом или «моя — другая»")
    pg.locator("#p-ideas .id-compose").screenshot(path=str(SHOTS / "ideas-similar.png"))
    pg.fill("#id-q", "Будильник с плавным светом экрана"); pg.wait_for_timeout(700)
    ok(pg.is_hidden("#id-sim") and pg.inner_text("#id-send") == "Предложить идею" and "первой" in pg.inner_text("#id-send-h"),
       "похожих нет — «Предложить идею», ваша будет первой")
    pg.click("#id-send"); pg.wait_for_timeout(500)
    ok("на рассмотрении" in pg.inner_text("#id-res") and pg.get_attribute("#p-ideas [data-tab=mine]", "aria-selected") == "true",
       "предложил — спасибо, на рассмотрении; открыта вкладка «Мои»")
    # сделано и поиск
    pg.click("#p-ideas [data-tab=done]"); pg.wait_for_timeout(400)
    ok("сделано в 0.59" in pg.inner_text("#id-list") and pg.is_disabled("#id-list [data-id='2'] .id-vote"), "«Сделано» — с версией, голос уже не нужен")
    pg.click("#p-ideas [data-tab=plan]"); pg.fill("#id-find", "мульт"); pg.wait_for_timeout(700)
    ok(pg.locator("#id-list .id-it").count() == 1 and pg.locator("#id-pager button").count() == 0, "поиск по идеям")
    ok(not errs, f"без ошибок: {errs[:3]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
