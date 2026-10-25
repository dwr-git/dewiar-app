"""Карточка «Я» в студии (0.45, владелец 25.10: «своё фото себе на аватарку, которое увидят близкие и на встречах…
фото, имя и может ещё что»):
- над списком близких — «Близкие видят вас как»: фото (или буква), имя, о себе; нажать — панель карточки;
- фото: выбрать, вставить Ctrl+V или перетащить; сжимается здесь до 256×256 JPEG; «Убрать»;
- о себе до 160 знаков со счётчиком; «Показывать фото во «Встречах»» — по умолчанию выключено; честно сказано, где фото;
- у близких с фото — фото в списке и в шапке переписки, «о себе» — в шапке;
- во «Встречах» у людей рядом с фото — круглое фото на бейдже."""
import base64, io, json, os, re
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def png(color, size=(600, 400)):
    b = io.BytesIO(); Image.new("RGB", size, color).save(b, "PNG"); return base64.b64encode(b.getvalue()).decode()


FACE = "data:image/png;base64," + png((220, 120, 90), (64, 64))
PHOTO = png((40, 160, 200))
FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = [];
  window.ST = { me: { pid: "me1", name: "Миша", about: "", face: 0, face_meet: false }, offers: [], people: [
    { pid: "p1", name: "Людмила", about: "Мама, люблю сад", face: 17, devs: [{ dev: "d1" }], unread: 0, marks: [0, 0], last: null },
    { pid: "p2", name: "Андрей", about: "", face: 0, devs: [{ dev: "d2" }], unread: 0, marks: [0, 0], last: null }] };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "close_state") return JSON.parse(JSON.stringify(ST));
      if (c === "close_history") return [];
      if (c === "close_face") return { data: "FACE" };
      if (c === "close_card") { if ("name" in a) ST.me.name = a.name; if ("about" in a) ST.me.about = a.about;
        if ("face" in a) ST.me.face = a.face ? 99 : 0; if ("face_meet" in a) ST.me.face_meet = a.face_meet; return JSON.parse(JSON.stringify(ST)); }
      if (c === "close_meet") return { ok: true, me: { adult: true, here: { mid: "mme", name: "Миша", about: "", place: "Концерт", since: Date.now() / 1000 - 600, until: Date.now() / 1000 + 3000 } },
        people: [{ mid: "m1", name: "Оля", about: "впервые здесь", place: "Концерт", since: Date.now() / 1000 - 300, face: 5 },
                 { mid: "m2", name: "Пётр", about: "", place: "Концерт", since: Date.now() / 1000 - 200, face: 0 }], radius_m: 700, max_h: 3 };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
""".replace("FACE", FACE)
SHOT = os.environ.get("SHOT_DIR")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"close\"]').click(); loadClose(true)"); pg.wait_for_timeout(700)
    me = pg.evaluate("[document.querySelector('#cl-me-name').textContent, document.querySelector('#cl-me-about').textContent, document.querySelector('#cl-me-ava').textContent]")
    ok(me == ["Миша", "добавьте фото и пару слов о себе", "М"], f"«Близкие видят вас как»: имя, буква и подсказка добавить фото: {me}")
    lst = pg.evaluate("[...document.querySelectorAll('#cl-people .cl-ava')].map(a => [a.classList.contains('has-face'), a.style.backgroundImage.slice(0, 20)])")
    ok(lst[0][0] and lst[0][1].startswith('url("data:image') and not lst[1][0], f"у близкого с фото — фото в списке, без фото — буква: {lst}")
    pg.evaluate("clOpen('p1')"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#cl-ava').classList.contains('has-face')") and "люблю сад" in pg.text_content("#cl-devs"),
       "в шапке переписки — фото и «о себе»")
    ok(pg.evaluate("calls.filter(c => c[0] === 'close_face' && c[1].pid === 'p1').length") == 1, "фото близкого запрашивается один раз (кэш)")
    if SHOT:
        pg.screenshot(path=f"{SHOT}/card_list.png")
    pg.click("#cl-me"); pg.wait_for_timeout(200)
    ok(pg.is_visible("#cl-card") and not pg.is_visible("#cl-chat") and pg.input_value("#cl-myname") == "Миша", "нажали — панель карточки вместо переписки, имя заполнено")
    ok(not pg.is_checked("#cl-face-meet"), "фото во «Встречах» — по умолчанию выключено")
    ok("dewiar.pro" in pg.text_content("#cl-card") and "только ваши близкие" in pg.text_content("#cl-card"), "честно сказано, где хранится фото и кто его видит")
    # фото: выбрать файл — сжимается до 256×256 JPEG
    pg.set_input_files("#cl-face-file", files=[{"name": "me.png", "mimeType": "image/png", "buffer": base64.b64decode(PHOTO)}]); pg.wait_for_timeout(500)
    d = pg.evaluate("CL.cardFace || ''")
    ok(d.startswith("data:image/jpeg;base64,"), "выбрали фото — превью, сжато в JPEG")
    im = Image.open(io.BytesIO(base64.b64decode(d.split(",")[1])))
    ok(im.size == (256, 256) and len(d) < 60000, f"256×256, небольшое: {im.size}, {len(d)} знаков")
    pg.fill("#cl-about", "Люблю горы и джаз"); pg.dispatch_event("#cl-about", "input")
    ok(pg.text_content("#cl-about-n") == "17 / 160", f"счётчик знаков: {pg.text_content('#cl-about-n')}")
    pg.check("#cl-face-meet"); pg.click("#cl-card-save"); pg.wait_for_timeout(300)
    last = pg.evaluate("calls.filter(c => c[0] === 'close_card').pop()[1]")
    ok(last["about"] == "Люблю горы и джаз" and last["face_meet"] is True and last["face"].startswith("data:image/jpeg") and last["name"] == "Миша",
       "«Сохранить» — имя, о себе, фото и «во Встречах» уходят вместе")
    ok(pg.text_content("#cl-card-res") == "Сохранено" and pg.text_content("#cl-me-about") == "Люблю горы и джаз"
       and pg.evaluate("document.querySelector('#cl-me-ava').classList.contains('has-face')"), "сохранено — карточка слева обновилась, с фото")
    if SHOT:
        pg.screenshot(path=f"{SHOT}/card_edit.png")
    # вставка из буфера
    pg.evaluate("""(b64) => { const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0)); const dt = new DataTransfer();
      dt.items.add(new File([bin], 'clip.png', { type: 'image/png' })); const e = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
      document.dispatchEvent(e); }""", png((250, 200, 40)))
    pg.wait_for_timeout(500)
    ok(pg.evaluate("(CL.cardFace || '').startsWith('data:image/jpeg')") and "Сохранить" in pg.text_content("#cl-card-res"), "Ctrl+V с картинкой — новое фото, просит сохранить")
    # перетащить
    pg.evaluate("CL.cardFace = undefined")
    pg.evaluate("""(b64) => { const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0)); const dt = new DataTransfer();
      dt.items.add(new File([bin], 'drop.png', { type: 'image/png' })); const c = document.querySelector('#cl-card');
      c.dispatchEvent(new DragEvent('dragover', { dataTransfer: dt, bubbles: true, cancelable: true }));
      c.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true })); }""", png((90, 200, 90)))
    pg.wait_for_timeout(500)
    ok(pg.evaluate("(CL.cardFace || '').startsWith('data:image/jpeg')") and not pg.evaluate("document.querySelector('#cl-card').classList.contains('drop')"),
       "перетащили картинку — новое фото")
    pg.set_input_files("#cl-face-file", files=[{"name": "a.txt", "mimeType": "text/plain", "buffer": b"hello"}]); pg.wait_for_timeout(200)
    ok("не картинка" in pg.text_content("#cl-card-res"), "не картинка — понятная ошибка")
    pg.click("#cl-face-del"); pg.click("#cl-card-save"); pg.wait_for_timeout(300)
    ok(pg.evaluate("calls.filter(c => c[0] === 'close_card').pop()[1].face") == "" and not pg.evaluate("document.querySelector('#cl-me-ava').classList.contains('has-face')"),
       "«Убрать» и «Сохранить» — фото убрано")
    pg.click("#cl-card-x"); pg.wait_for_timeout(150)
    ok(not pg.is_visible("#cl-card") and pg.is_visible("#cl-chat"), "«Закрыть» — снова переписка")
    # Встречи
    pg.evaluate("ST.me.about = 'Люблю горы и джаз'")
    pg.click("#cl-tabs [data-t='meet']"); pg.wait_for_timeout(800)
    f = pg.evaluate("[...document.querySelectorAll('#cl-meet .mt-tag')].map(t => !!t.querySelector('.mt-face.has-face'))")
    ok(f[:2] == [True, False], f"во «Встречах» — фото у тех, кто разрешил: {f}")
    ok(pg.evaluate("calls.some(c => c[0] === 'close_face' && c[1].meet && c[1].pid === 'm1')"), "фото во «Встречах» — по отметке (mid), не по близким")
    if SHOT:
        pg.screenshot(path=f"{SHOT}/card_meet.png")
    pg.click("#mt-edit"); pg.wait_for_timeout(200)
    ok(pg.input_value("#mt-about") == "", "своя отметка уже есть — её «о себе» не подменяем")
    pg.evaluate("document.documentElement.classList.add('st-light')"); pg.click("#cl-tabs [data-t='chat']"); pg.wait_for_timeout(200)
    if SHOT:
        pg.click("#cl-me"); pg.wait_for_timeout(200); pg.screenshot(path=f"{SHOT}/card_light.png")
    noicon = pg.evaluate("[...document.querySelectorAll('nav button[data-p]')].filter(b => !b.querySelector('svg')).map(b => b.dataset.p)")
    ok(not noicon, f"у каждого пункта меню студии — значок (у «Платежей» его не было): {noicon}")
    ok(not errs, "без ошибок на странице" + (f": {errs}" if errs else ""))
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
raise SystemExit(1 if fails else 0)
