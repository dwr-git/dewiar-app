"""Раздел «Рефералы» (отзыв 11.10: «созвездие выпадает и мелко; ссылка и созвездие — в одном месте; писать и звонить
приглашённым»). Большое созвездие (refnet.js, big): имена под звёздами, сверху — кто позвал вас, звезду можно нажать.
Студия: раздел рядом с «Близкими» — код, печать, правила, друзья; «Позвать в Близкие» → ждём ответа; «Написать» ведёт в
переписку; в «Близких» — «… зовёт вас» с «Принять». Телефон: вкладки «Близкие» | «Рефералы» в одном листе. Ядро — close.py.
Сервер — tests/close_server_test.py."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def fr(i, paid, name=None):
    return {"name": name or f"Друг №{i}", "days": 3 if paid else 1, "need": 3, "paid": paid, "sub": 0, "since": 100 + i, "rid": f"r{i}"}


D = {"ok": True, "code": "K7M2QX", "link": "https://dewiar.pro/dwrapp/download.php?ref=K7M2QX", "bonus": 1, "bonus_new": .5, "days": 3,
     "earned": 2, "can_use": True, "by": {"name": "Ан…", "rid": "rb"}, "invited": [fr(1, True, "Ол…"), fr(2, True), fr(3, False)]}
MAP = {"r1": {"pid": "pOla"}, "rb": {"pid": "pAnna"}}
PEOPLE = [{"pid": "pOla", "name": "Оля", "devs": [{"dev": "x", "pub": "A" * 43}]}, {"pid": "pAnna", "name": "Анна", "devs": []}]

# ядро: «Позвать», ответ на «зовёт вас», знаки связи
import close as CLM  # noqa: E402


class Host:
    s = None

    def emit(self, *a, **k):
        pass


c = CLM.Close.__new__(CLM.Close)
c.host = Host(); c.st = {"me": {"pid": "me"}, "people": [], "dev": "d", "hist": {}, "unread": {}}; c.error = ""
c._lock = __import__("threading").RLock(); c._save = lambda: None; c._keys = lambda: (None, "pub")
import threading  # noqa: E402
c.soon = threading.Event()
calls = []


class R:
    def __init__(self, d):
        self.d = d

    def json(self):
        return self.d


def fake(method, path, body=None, **k):
    calls.append((path, body))
    if path == "/close/refs":
        return R({"ok": True, "map": {"r1": {"pid": "pOla"}}})
    if path == "/close/ref":
        return R({"ok": True, "offered": True} if body["rid"] == "r2" else {"ok": True, "person": {"pid": "pX", "name": "Гоша"}, "me": {"pid": "me"}, "people": [{"pid": "pX", "name": "Гоша"}]})
    if path == "/close/offer":
        return R({"ok": True, "me": {"pid": "me"}, "people": [{"pid": "pV", "name": "Вера"}] if body["yes"] else [], "offers": []})
    return R({})


c._req = fake
ok(c.ref_map(["r1", "", None]) == {"r1": {"pid": "pOla"}} and calls[-1] == ("/close/refs", {"rids": ["r1"]}), "ядро: кто из рефералов уже в близких")
ok(c.ref_close("r2") == {"offered": True} and c.ref_close("r3")["person"]["name"] == "Гоша" and c.st["people"][0]["name"] == "Гоша",
   "ядро: «Позвать в Близкие» — ждём ответа или сразу близкий (если он тоже звал)")
c.st["offers"] = [{"pid": "pV", "name": "Вера"}]
st = c.offer("pV", True)
ok([p["name"] for p in st["people"]] == ["Вера"] and st["offers"] == [] and calls[-1] == ("/close/offer", {"pid": "pV", "yes": True}), "ядро: «Принять» — близкий, предложение убрано")
cmds = (ROOT / "core/engine_commands.py").read_text()
ok(all(f'cmd == "{x}"' in cmds for x in ("close_refs", "close_ref", "close_offer")), "команды студии: close_refs, close_ref, close_offer")

tmp = Path(tempfile.mkdtemp())
(tmp / "p.html").write_text(f'<!doctype html><meta charset=utf-8><body><div id=a style="width:700px"></div><script src="{(ROOT / "ui/assets/refnet.js").as_uri()}"></script>', encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((tmp / "p.html").as_uri())
    r = pg.evaluate("""(d) => { const a = document.getElementById('a'), picked = [];
      d.invited[0].label = 'Оля'; d.invited[0].close = 'pOla';
      DewiarRefNet.render(a, d, { big: true, me: 'Миша', by: 'Анна', sel: 1, onPick: (i) => picked.push(i) });
      a.querySelector('.hit[data-i="2"]').dispatchEvent(new MouseEvent('click', { bubbles: true }));
      a.querySelector('.hit[data-i="by"]').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      const txt = [...a.querySelectorAll('text')].map(t => t.textContent);
      return [!!a.querySelector('.rn.big'), txt.includes('Оля'), txt.includes('Друг №2'), txt.some(t => t.startsWith('Вас позвал(а) Анна')), picked,
              a.querySelectorAll('circle[fill="#FF7FB6"]').length, a.querySelectorAll('.hit').length, a.querySelectorAll('.tw').length > 5]; }""", D)
    ok(r == [True, True, True, True, [2, "by"], 1, 4, True], f"большое созвездие: имена, «Вас позвал(а)», метка «в Близких», звёзды нажимаются (и с клавиатуры): {r}")
    r = pg.evaluate("(d) => { DewiarRefNet.render(document.getElementById('a'), d, { big: true, calm: true }); return !!document.querySelector('#a .rn.calm'); }", D)
    ok(r, "перерисовка по выбору — без повторного появления звёзд")
    pg.close()

    # студия
    pg = b.new_page(viewport={"width": 1360, "height": 900}); pg.on("pageerror", lambda e: errs.append("студия: " + str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""([d, m, pe]) => { localStorage.clear(); window._calls = []; window._st = { me: { pid: 'me', name: 'Миша' }, people: pe, offers: [{ pid: 'pV', name: 'Вера', ts: 1 }] };
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'ref_info') return Promise.resolve(d); if (c === 'close_refs') return Promise.resolve(m);
        if (c === 'close_state') return Promise.resolve(_st); if (c === 'close_history') return Promise.resolve([]);
        if (c === 'close_ref') return Promise.resolve({ offered: true });
        if (c === 'close_offer') { _st = Object.assign({}, _st, { offers: [], people: _st.people.concat(a.yes ? [{ pid: 'pV', name: 'Вера', devs: [] }] : []) }); return Promise.resolve(_st); }
        return Promise.resolve({}); };
      $('nav button[data-p="ref"]').click(); }""", [D, MAP, PEOPLE])
    pg.wait_for_timeout(1500)
    nav = pg.evaluate("() => [...document.querySelectorAll('nav button[data-p]')].map(b => b.dataset.p)")
    ok(nav[nav.index("close"):nav.index("ref") + 1] == ["close", "family", "kids", "ref"],
       "группа «Семья и близкие» (28.10): «Близкие», «Семья», «Дети», «Рефералы»")
    groups = pg.evaluate("() => [...document.querySelectorAll('nav .ng')].map(g => g.textContent.trim())")
    ok(groups[:3] == ["Для себя", "Семья и близкие", "Работа"], f"меню студии — по смыслу: {groups[:3]}")
    r = pg.evaluate("""() => [!!$('#rf-net .rn.big'), $('#rf-code').textContent, !!$('#rf-qr svg'), $('#rf-rules').textContent.includes('+1'), $('#rf-use').style.display,
      [...document.querySelectorAll('#rf-list .rf-p b')].map(b => b.textContent), $('#rf-by').textContent.includes('Анна'),
      [...document.querySelectorAll('#rf-list .rf-p')].map(r => [...r.querySelectorAll('button')].map(b => b.textContent).join('+'))]""")
    ok(r[:5] == [True, "K7M2QX", True, True, ""] and r[5] == ["Оля", "Друг №2", "Друг №3"] and r[6]
       and r[7] == ["Написать+Позвонить", "Позвать в Близкие", "Позвать в Близкие"],
       f"раздел: созвездие, код, печать, правила, «Есть код?»; друзья — имя из «Близких», «Написать»/«Позвонить» или «Позвать»: {r}")
    pg.click("#rf-list .rf-p:nth-child(2) [data-o]"); pg.wait_for_timeout(300)
    r = pg.evaluate("() => [_calls.filter(c => c[0] === 'close_ref').map(c => c[1].rid), document.querySelector('#rf-list .rf-p:nth-child(2)').textContent.includes('ждём ответа')]")
    ok(r == [["r2"], True], f"«Позвать в Близкие» — предложение ушло, у друга «ждём ответа»: {r}")
    pg.evaluate("document.querySelector('#rf-net .hit[data-i=\"2\"]').dispatchEvent(new MouseEvent('click', { bubbles: true }))"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#rf-list .rf-p:nth-child(3)').classList.contains('cur') && !!document.querySelector('#rf-net .rn.calm')"),
       "нажали звезду — друг выделен в списке, небо не мигает")
    pg.click("#rf-list .rf-p:nth-child(1) [data-w]"); pg.wait_for_timeout(500)
    pg.evaluate("loadClose()"); pg.wait_for_timeout(300)         # в студии «Близкие» грузятся при открытии (здесь нет настроек — зовём сами)
    r = pg.evaluate("() => [$('#p-close').classList.contains('cur'), CL.cur, $('#cl-offers').textContent.includes('Вера зовёт вас')]")
    ok(r == [True, "pOla", True], f"«Написать» — переписка с другом; в «Близких» — «Вера зовёт вас»: {r}")
    pg.click("#cl-offers [data-y]"); pg.wait_for_timeout(500)
    r = pg.evaluate("() => [_calls.filter(c => c[0] === 'close_offer').map(c => c[1]), $('#cl-offers').textContent, CL.cur]")
    ok(r == [[{"pid": "pV", "yes": True}], "", "pV"], f"«Принять» — Вера в близких, открыта переписка: {r}")
    r = pg.evaluate("""(d) => { RF.d = Object.assign({}, d, { invited: [], by: null, opened: 1 }); rfRender(); return $('#rf-list').textContent; }""", D)
    ok("Ссылку открыли 1 человек" in r and "появится здесь сам" in r, f"студия: «ссылку открыли» в пустом списке: {r}")
    pg.evaluate("$('nav button[data-p=\"dw\"]').click(); dwRef()"); pg.wait_for_timeout(500)
    pg.evaluate("$('#dw-ref-open').click()"); pg.wait_for_timeout(300)
    ok(pg.evaluate("$('#p-ref').classList.contains('cur')") and "K7M2QX" in pg.inner_text("#dw-ref-text"), "«Dewiar.pro» → карточка «Рефералы» ведёт в раздел")
    pg.close()

    # телефон
    www = tmp / "www"
    shutil.copytree(ROOT / "android/assets/www", www)
    for f in ("entities.js", "skins.css", "skins.js", "privacy.js", "refnet.js", "closecrypto.js", "call.js"):
        shutil.copy(ROOT / "ui/assets" / f, www / f)
    (www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                    capture_output=True, text=True, check=True).stdout, encoding="utf-8")
    ph = b.new_page(viewport={"width": 393, "height": 852}); ph.on("pageerror", lambda e: errs.append("телефон: " + str(e)))
    ph.route("https://**", lambda r: r.abort())
    ph.goto((www / "index.html").as_uri()); ph.wait_for_timeout(900)
    ph.evaluate("""([d, m, pe]) => { localStorage.clear(); S.llm = Object.assign({}, S.llm, { cloud: true, api_key: 'dw-x' }); S.user_name = 'Миша';
      window._req = []; cloudGet = async () => d; syncCred = () => ({ token: 'dw-x', base: 'https://x/cloud.php' }); clKeys = () => ({ dev: 'd', pub: 'p' });
      window._st = { me: { pid: 'me', name: 'Миша' }, people: pe, offers: [{ pid: 'pV', name: 'Вера', ts: 1 }] };
      clReq = async (mm, path, body) => { _req.push([path, body]);
        if (path === '/close/refs') return { map: m }; if (path === '/close/hello') return _st;
        if (path === '/close/ref') return { offered: true };
        if (path === '/close/offer') { _st = Object.assign({}, _st, { offers: [], people: _st.people.concat([{ pid: 'pV', name: 'Вера', devs: [] }]) }); return Object.assign({ person: { pid: 'pV', name: 'Вера' } }, _st); }
        return {}; };
      const st = clLoad(); st.me = _st.me; st.people = pe; st.offers = _st.offers; clBadge(); openRefs(); }""", [D, MAP, PEOPLE])
    ph.wait_for_timeout(1500)
    r = ph.evaluate("""() => [$('#b-close').classList.contains('has'), $('#cl-h').firstChild.textContent, $('#cl-tabs .on').textContent, !!$('#rf-net .rn.big'),
      [...document.querySelectorAll('#rf-body .rfp b')].map(b => b.textContent), !!$('#rf-body .rfp [data-c]'), !!$('#ref-code')]""")
    ok(r == [True, "Рефералы", "Рефералы", True, ["Анна", "Оля", "Друг №2", "Друг №3"], True, True],
       f"телефон: «Близкие» | «Рефералы» в одном листе, большое созвездие, кто позвал и кого позвали, «Позвонить» близкому: {r}")
    ph.evaluate("document.querySelectorAll('#rf-body [data-o]')[0].click()"); ph.wait_for_timeout(300)
    r = ph.evaluate("() => [_req.filter(x => x[0] === '/close/ref').map(x => x[1].rid), document.querySelectorAll('#rf-body .rfw').length]")
    ok(r == [["r2"], 1], f"телефон: «Позвать в Близкие» — ждём ответа: {r}")
    ph.evaluate("document.querySelector('#rf-body [data-w]').click()"); ph.wait_for_timeout(300)
    ok(ph.evaluate("clCur") == "pAnna" and ph.evaluate("!!document.querySelector('#cl-text')"), "телефон: «Написать» открывает переписку")
    ph.evaluate("() => { clCur = ''; clTab = 'close'; clRender(); }"); ph.wait_for_timeout(200)
    ok("Вера зовёт вас" in ph.inner_text("#close-body"), "телефон: «Вера зовёт вас в «Близкие»» — на вкладке «Близкие»")
    ph.evaluate("document.querySelector('.clof [data-y]').click()"); ph.wait_for_timeout(500)
    r = ph.evaluate("() => [_req.filter(x => x[0] === '/close/offer').map(x => x[1]), clCur, clLoad().offers.length]")
    ok(r == [[{"pid": "pV", "yes": True}], "pV", 0], f"телефон: «Принять» — близкий, открыта переписка: {r}")
    # отзыв 16.10: «давала ссылку, а в кабинете пусто» — видно, сколько людей открыли ссылку, и как друг засчитается
    ph.evaluate("() => { clCur = ''; clTab = 'ref'; clRender(); }"); ph.wait_for_timeout(400)
    r = ph.evaluate("""(d) => { refInfo = Object.assign({}, d, { invited: [], by: null, opened: 3 }); refDraw(); return $('#rf-body').textContent; }""", D)
    ok("Ссылку открыли 3 человека" in r and "появится здесь сам" in r and "K7M2QX" in r, f"телефон: «ссылку открыли 3 человека» и как друг засчитается: {r[-200:]}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
