"""Образы (1.0.55, владелец 20.11: «человек любит разнообразие… Лира может оставаться, а просто кнопочка „смени образ“»).
Тот же персонаж — то же лицо, мимика, голос и характер; другие причёска и наряд. Выбор — в настройках (looks), живое лицо
и портрет в окнах — выбранного образа; «Сама — по времени дня»: вечером — домашний, днём — образ дня (сезонных нет: владелец 21.11).
Голосом — «смени образ», «надень локоны», «выбирай образ сама», «верни обычный образ». В виджете — стрелка у имени и
кружки под ним. Слои образа — свои глаза и губы с картинки (tools/live_looks.py), фон без чёрной каймы."""
import datetime as dt, json, os, re, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import personas as P  # noqa: E402
import settings as ST  # noqa: E402
import answer_direct as AD  # noqa: E402

# слои на месте: портрет 512, живой портрет, радужки, рот 0..3, улыбка; в entities.js — своя геометрия
ent = (ROOT / "ui/assets/entities.js").read_text(encoding="utf-8")
for who, looks in P.LOOKS.items():
    for x in looks:
        n = f"{who}-{x['id']}"
        files = [ROOT / f"data/avatars/{n}.webp", ROOT / f"ui/assets/live/thumbs/{n}.webp", ROOT / f"ui/assets/live/{n}.webp", ROOT / f"ui/assets/live/{n}-smile.webp"] + \
                [ROOT / f"ui/assets/live/{n}-mouth-{i}.webp" for i in range(4)] + [ROOT / f"ui/assets/live/{n}-iris-{s}.png" for s in "lr"]
        miss = [f.name for f in files if not f.exists()]
        ok(not miss and f'"{n}": {{"own": true' in ent, f"{n}: слои и геометрия на месте {miss}")
from PIL import Image  # noqa: E402
sizes = {Image.open(f).size for f in (ROOT / "ui/assets/live/thumbs").glob("*.webp")}
ok(len(sizes) == 1, f"владелец 21.11: «миниатюры единообразно, не как первое слишком крупное» — один размер и кадр у всех: {sizes}")
# 21.11 (владелец: «оригинальная Лира смотрит в разные стороны, моргает… на новых образах — статичность»; «еле заметная
# круглая полоска внутри»): под радужкой — пустой глаз (иначе взгляд и моргание не видны), взгляд ходит как у обычной
# Лиры, край портрета в светлом неоморфизме стирается кольцом
import numpy as _np  # noqa: E402
for n in ("lira-tails", "patrik-suit"):
    base = _np.asarray(Image.open(ROOT / f"ui/assets/live/{n}.webp").convert("RGB")).astype(float)
    iris = Image.open(ROOT / f"ui/assets/live/{n}-iris-l.png").convert("RGBA")
    m = re.search(r'"' + n + r'": (\{.*\}),$', ent, re.M)
    conf = json.loads(m.group(1)) if m else {}
    x, y = conf.get("geo", {}).get("eyes", [[0, 0]])[0]
    D = conf.get("geo", {}).get("iris", 16)
    under = base[int(y + D * .35):int(y + D * .65), int(x + D * .35):int(x + D * .65)].mean((0, 1))
    top = _np.asarray(iris.resize((int(D), int(D))).convert("RGB")).astype(float)[int(D * .35):int(D * .65), int(D * .35):int(D * .65)].mean((0, 1))
    ok(conf.get("soft") and conf["geo"]["moveX"] >= 2 and abs(under - top).sum() > 20,
       f"{n}: под радужкой пустой глаз, взгляд ходит ({conf.get('geo', {}).get('moveX')} px), край — мягкий")
ok("R + lw / 2 - 1" in ent and "L.soft ?" in ent, "неоморфизм: край портрета стирается кольцом, у образов растворяется раньше")
im = Image.open(ROOT / "ui/assets/live/lira-home.webp").convert("RGBA")
ok(im.getpixel((5, 5))[3] == 0 and im.getpixel((180, 180))[3] == 255, "фон образа прозрачный, лицо — нет")

# выбор и «Сама»
s = ST.Settings(tmp / "s.json")
ps = P.Personas()
ps.look_pref = lambda: s.get("looks") or {}
pub = {x["id"]: x for x in ps.public()}
L = pub["lira"]
ok([x["name"] for x in L["looks"]][:2] == ["Обычная", "Коса"] and L["look"] == "" and L["live"] == "lira",
   f"Лира: образы с «Обычной» первой, по умолчанию — обычная: {[x['name'] for x in L['looks']]}")
ok(L["looks"][0]["img"] == "assets/live/thumbs/lira.webp" and all(x["img"] == f"assets/live/thumbs/lira-{x['id']}.webp" for x in L["looks"][1:])
   and all((ROOT / "ui" / x["img"]).exists() for x in L["looks"])
   and len(json.dumps(L["looks"])) < 12000, f"кружки образов — ссылками на файлы окна, «hello» не тяжелеет ({len(json.dumps(L['looks'])) // 1024} КБ)")
ok("looks" not in pub.get("jarvis", {}) and "patrik" in pub and len(pub["patrik"]["looks"]) == len(P.LOOKS["patrik"]) + 1, "образы только у Лиры и Патрика")
s.update({"looks": {"lira": {"look": "silk"}}})
L = {x["id"]: x for x in ps.public()}["lira"]
ok(L["live"] == "lira-silk" and L["look"] == "silk" and L["avatar_url"].startswith("data:image/"), "выбран «Шёлк» — живое лицо и портрет образа")
s.update({"looks": {"lira": {"look": "нет-такого"}}})
ok({x["id"]: x for x in ps.public()}["lira"]["live"] == "lira", "неизвестный образ — обычный облик, без ошибок")
A = lambda m, d, h=12: P.look_auto(P.LOOKS["lira"], dt.datetime(2026, m, d, h))
ok(A(7, 4, 21) == "home" and A(1, 2, 23) == "home", "«Сама»: вечером — домашний")
days = {A(7, d) for d in range(1, 31)} | {A(1, d) for d in range(1, 31)}
ok("home" not in days and len(days) >= 5, f"днём — образ дня по кругу, каждый день другой: {sorted(days)}")
ok({x["id"] for x in P.LOOKS["lira"]}.isdisjoint({"spring", "winter", "loose", "gamer"}) and not any(set(x.get("when") or []) - {"evening"} for x in P.LOOKS["lira"]),
   "владелец 21.11: «Весна», «Зима», «Волны», «Геймер» убраны, выбора по сезону нет")
ok(A(3, 10) == A(3, 10, 15), "в течение дня образ не мелькает")

# голосом и командой
for t, want in (("Лира, смени образ", "next"), ("надень локоны", "name"), ("образ «Шёлк»", "name"), ("выбирай образ сама", "auto"),
                ("верни обычный образ", "plain"), ("смени тему", None), ("надень куртку потеплее", None),
                # 21.11, первая проба владельца: «Смени облик» — ушло модели, та ответила «не могу сменить облик» и позвала персонажа
                ("Смени облик.", "next"), ("поменяй внешность", "next"), ("переоденься", "next"), ("верни обычный облик", "plain"),
                ("смени голос", None), ("смени стиль", None)):
    m = AD.LOOK_RX.match(t)
    ok((m and next(k for k, v in m.groupdict().items() if v)) == want, f"«{t}» → {want}")


class Eng(AD.DirectMixin, AD.LookMixin):
    def __init__(self):
        self.s, self.personas, self.said, self.ev = s, ps, [], []

    def emit(self, ev, **kw):
        self.ev.append(ev)

    def _say_quick(self, msg, said, via=None, **kw):
        self.said.append(msg)


s.update({"looks": {}, "persona": "lira"})
E = Eng()
ok(E._direct_look("Лира, смени образ") and s.get("looks")["lira"]["look"] == "braid" and "«Коса»" in E.said[-1] and "personas" in E.ev,
   f"«смени образ» — следующий, сказала какой, окна узнали: {E.said[-1:]}")
ok(E._direct_look("надень локоны") and s.get("looks")["lira"]["look"] == "curls", "«надень локоны» — «Локоны»")
ok(E._direct_look("надень шелковый") and s.get("looks")["lira"]["look"] == "silk", "«надень шелковый» — «Шёлк» (ё и е)")
ok(E._direct_look("выбирай образ сама") and s.get("looks")["lira"]["auto"] is True and "сама" in E.said[-1], "«выбирай образ сама» — «Сама» включена")
ok(E._direct_look("смени образ") and s.get("looks")["lira"]["auto"] is False, "выбрала сама человек — «Сама» выключается")
ok(E._direct_look("верни обычный образ") and s.get("looks")["lira"]["look"] == "" and "обычный" in E.said[-1], "«верни обычный образ»")
ok(not E._direct_look("надень куртку потеплее"), "не образ — дальше модели")
s.update({"persona": "jarvis"})
ok(not E._direct_look("смени образ"), "у персонажа без образов — дальше модели (не «готово»)")
ct = (ROOT / "core/commands_talk.py").read_text(encoding="utf-8")
ok('cmd == "persona_look"' in ct and "self.set_look(" in ct, "команда окон persona_look")

# лица — только у Лиры и Патрика: Эва, Ника, Оскар, добавленные теперь, — абстракция; добавленные раньше — с лицом
ps.gallery_add("nika"); ps.gallery_add("eva")
q = {x["id"]: x for x in ps.public()}
ok(q["nika"]["avatar_url"] == "" and "live" not in q["nika"] and q["eva"]["avatar_url"] == "" and "live" not in q["eva"],
   "Ника и Эва, добавленные теперь, — абстракция без лица")
(P.PERSONAS_DIR / "oskar.json").write_text(json.dumps(dict(P.GALLERY["oskar"], gallery=True), ensure_ascii=False), encoding="utf-8")
ps.reload()
ok({x["id"]: x for x in ps.public()}["oskar"]["avatar_url"].startswith("data:image/"), "Оскар, добавленный раньше, — с лицом, как был")
ps.save(dict(ps.get("nika"), tagline="Бодро"))
ok({x["id"]: x for x in ps.public()}["nika"]["avatar_url"] == "", "правка в студии абстракцию не сбрасывает")
g = {x["id"]: x for x in ps.gallery()}
ok(all(g[k]["avatar_url"] == "" and "live" not in g[k] for k in P.NO_FACE), "в «Готовых» у Эвы, Ники и Оскара — абстракции")
for k in ("nika", "eva", "oskar"):
    ps.delete(k) if k in {x["id"] for x in ps.all()} and k != "eva" else None

# виджет: стрелка у имени, кружки, выбор и «Сама»
from playwright.sync_api import sync_playwright  # noqa: E402
s.update({"persona": "lira", "looks": {}})
PS = json.dumps(ps.public(), ensure_ascii=False)
CORE = r"""(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  window.CALLS = []; core.call = async (c, a) => { CALLS.push([c, a]); return {}; };
  setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neu" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira", personas: __PS__, reminders: [], state: "idle" }); }, 150); }; ready(); })();""".replace("__PS__", PS)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 300, "height": 560}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1300)
    pg.evaluate("() => core.emit('state', { state: 'idle' })"); pg.wait_for_timeout(150)
    ok(pg.evaluate("document.getElementById('bubble').classList.contains('looks') && !!document.querySelector('#say .lkc')"), "у имени — стрелка образов")
    pg.click("#bubble"); pg.wait_for_timeout(600)
    n = pg.evaluate("() => document.getElementById('looks').hidden ? -1 : document.querySelectorAll('#looks-g button').length")
    ok(n == len(P.LOOKS["lira"]) + 1, f"нажали на имя — кружки образов под ним: {n}")
    top = pg.evaluate("() => [document.getElementById('looks').getBoundingClientRect().top, document.getElementById('bubble').getBoundingClientRect().bottom]")
    ok(top[0] >= top[1] + 6, f"кружки не примыкают к имени: {top}")
    pg.click("#looks-g button:nth-child(2)"); pg.wait_for_timeout(100)
    ok(pg.evaluate("CALLS.filter(c => c[0] === 'persona_look').slice(-1)[0]") == ["persona_look", {"id": "lira", "look": "braid"}], f"выбор образа — в ядро: {pg.evaluate('CALLS.slice(-1)[0]')}")
    pg.click("#looks .la"); pg.wait_for_timeout(100)
    ok(pg.evaluate("CALLS.filter(c => c[0] === 'persona_look').slice(-1)[0]") == ["persona_look", {"id": "lira", "auto": True}],
       "«Сама — по времени дня» — в ядро (фоновые вызовы окна, например complaints, не в счёт)")
    s.update({"looks": {"lira": {"look": "braid"}}})
    pg.evaluate("ps => core.emit('personas', { personas: ps })", ps.public()); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#looks-g button.cur span').textContent") == "Коса" and "Коса" in pg.evaluate("document.getElementById('say').textContent"),
       "выбранный образ отмечен и назван у имени")
    pg.mouse.click(150, 40); pg.wait_for_timeout(100)
    ok(pg.evaluate("document.getElementById('looks').hidden"), "щелчок мимо — кружки прячутся")
    # 21.11 (владелец: «как менять облик вручную я не понял»): и в меню персонажа — строка «Образ»
    pg.evaluate("() => core.emit('state', { state: 'thinking' })"); pg.wait_for_timeout(100)
    pg.click("#b-team"); pg.wait_for_timeout(200)
    row = pg.evaluate("() => { const r = document.querySelector('#team button.lkrow'); return r ? r.textContent : ''; }")
    ok("Образ" in row and "коса — сменить" in row, f"меню персонажа: строка «Образ» с текущим: {row!r}")
    pg.click("#team button.lkrow"); pg.wait_for_timeout(500)
    ok(not pg.evaluate("document.getElementById('looks').hidden") and not pg.evaluate("document.getElementById('team').classList.contains('show')"),
       "из меню персонажа — кружки образов открылись (и когда Лира думает)")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
