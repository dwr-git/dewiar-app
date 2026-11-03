"""«Сайты» (03.11): Лира делает и переделывает сайт одной фразой. Инструменты модели site_create / site_edit / site_show /
site_publish (с «Выполнить?» и адресом) / site_review; «сделай сайт для моей кофейни…» узнаётся (SITE_ASK) — подсказка
модели и действия «Сайтов» не выбрасываются даже на маленькой модели; создание — шаблон по делу, тексты моделью под
человека (без выдуманных отзывов и людей), сразу открыт в браузере; правка — быстрыми правилами («тёмная шапка», «строгий
шрифт», «меню бургером», «другой дизайн целиком» — тексты остаются) или моделью (операции JSON); каждая правка — версия,
«верни как было» — откат по шагам; оценка продвижения — понятными пунктами с фразой «исправь»; в детском режиме команд нет."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ.setdefault("DEWIAR_HOME", tempfile.mkdtemp())
DRY = Path(tempfile.mkdtemp()) / "dry.txt"
os.environ["DEWIAR_DRY_TOOLS"] = str(DRY)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import sites, sites_kit as K, tools as T  # noqa: E402
from quality import SITE_ASK, SITE_EDIT_ASK, SITE_TOOLS, SITE_NOTE  # noqa: E402

CALLS = []


def fake_llm(system, user):
    CALLS.append((system, user))
    if "копирайтер" in system:                      # заполнение шаблона под дело человека
        uids = {}
        for line in user.splitlines():
            if line.strip().startswith("["):
                uid, rest = line.strip()[1:].split("]", 1)
                uids[rest.split("/")[0].strip()] = uid
        return json.dumps({"name": "Кофейня «Зерно»", "tagline": "кофе и завтраки на Садовой", "description": "Кофе и завтраки на Садовой, 5: свежая обжарка, своя выпечка, столики у окна.",
                           "contacts": {"phone": "+7 912 000-11-22"},
                           "blocks": {uids["hero"]: {"title": "Кофе на Садовой с восьми утра", "text": "Обжариваем сами."},
                                      uids["prices"]: {"items": [{"group": "Кофе", "title": "Капучино", "price": "250 ₽"}, {"title": "Раф", "price": ""}]}}},
                          ensure_ascii=False)
    # правка фразой — операции
    uid = next(l.strip()[1:].split("]")[0] for l in user.splitlines() if "] about/" in l)
    return json.dumps({"ops": [{"op": "add_block", "type": "reviews", "data": {"items": [{"text": "Лучший кофе в городе!", "name": "Ирина"}]}},
                               {"op": "add_block", "type": "faq", "after": uid, "data": {"title": "Вопросы", "items": [{"q": "Есть ли веганское молоко?", "a": "Да, овсяное и миндальное."}]}}],
                       "say": "Добавила вопросы и раздел для отзывов."}, ensure_ascii=False)


class Sett:
    def __init__(self, f=None):
        self.f = f if f is not None else {}

    def get(self, a, b=None):
        return {"features": self.f, "tools": {}, "privacy": {}}.get(a, {})


# узнаём просьбы о сайте
for t in ("сделай сайт для моей кофейни на Садовой, 5", "Лира, создай мне сайт-визитку", "нужен лендинг для онлайн-курса", "хочу сайт для салона красоты",
          "можешь сделать сайт моей клиники?", "сделай простой сайт для юриста"):
    ok(bool(SITE_ASK.search(t)), f"«{t}» — просьба сделать сайт")
for t in ("сделай шапку сайта тёмной", "на моём сайте поменяй телефон", "опубликуй мой сайт", "оцени мой сайт", "как продвигать мой сайт"):
    ok(bool(SITE_ASK.search(t) or SITE_EDIT_ASK.search(t)), f"«{t}» — о своём сайте")
for t in ("открой сайт яндекса", "какая погода", "что у вас на сайте", "сделай страницу с рецептами", "на сайте госуслуг"):
    ok(not SITE_ASK.search(t) and not SITE_EDIT_ASK.search(t), f"«{t}» — не про сайты Лиры")
ok("site_create" in SITE_NOTE and "НЕ пиши HTML" in SITE_NOTE and "show_page" in SITE_NOTE, "подсказка модели: инструментом, не HTML и не show_page")
import engine_answer  # noqa: E402
keep = engine_answer.AnswerMixin._plugin_keep(type("X", (), {})(), "сделай сайт для моей кофейни") if hasattr(engine_answer, "AnswerMixin") else None
if keep is None:
    cls = next(v for v in vars(engine_answer).values() if isinstance(v, type) and hasattr(v, "_plugin_keep"))
    keep = cls._plugin_keep(type("X", (), {})(), "сделай сайт для моей кофейни")
ok(keep == SITE_TOOLS, f"маленькое окно модели: действия «Сайтов» не выбрасываются ({sorted(keep)})")

S = sites.Sites(Path(tempfile.mkdtemp()) / "sites", None, llm=fake_llm)
tb = T.Toolbox(Sett(), None)
tb.hooks["sites"] = S
names = {x["name"] for x in tb.specs()}
ok(SITE_TOOLS <= names, "инструменты «Сайтов» у модели есть")
ok(tb.policy("site_publish") == (True, True) and tb.policy("site_create") == (True, False), "опубликовать — с «Выполнить?», сделать и править — сразу")
tb.s = Sett({"sites": False})
ok(not any(tb.policy(n)[0] for n in SITE_TOOLS), "выключены в «Возможностях» — модель о них не знает")
tb.s = Sett()

r = tb.run("site_create", {"describe": "кофейня Зерно на Садовой, 5, работаем с 8 до 22, капучино 250", "name": "Зерно", "address": "ул. Садовая, 5", "hours": "8:00–22:00"})
sid = S.find("")
s = S.get(sid)
ok(s["template"] == "coffee" and "готов" in r and "открыт в браузере" in r, f"site_create: шаблон кофейни, ответ модели: {r[:90]}")
ok(s["name"] == "Кофейня «Зерно»" and s["contacts"]["address"] == "ул. Садовая, 5" and s["contacts"]["phone"] == "+7 912 000-11-22",
   "тексты и контакты — из слов человека (модель)")
hero = next(b for b in s["pages"][0]["blocks"] if b["type"] == "hero")
ok(hero["title"] == "Кофе на Садовой с восьми утра", "заголовок обложки переписан под дело")
ok(DRY.exists() and "xdg-open" in DRY.read_text() and "index.html" in DRY.read_text(), "сайт сразу открыт в браузере (собран в папку)")
ok(not any(b["type"] == "reviews" for b in s["pages"][0]["blocks"]), "отзывов не появилось")

r = tb.run("site_edit", {"request": "сделай шапку тёмной"})
ok(S.get(sid)["theme"]["header"] == "dark" and "шапка тёмная" in r, f"«сделай шапку тёмной» — без модели: {r[:60]}")
n0 = len(CALLS)
tb.run("site_edit", {"request": "поменяй шрифт на строгий"})
tb.run("site_edit", {"request": "меню спрячь в бургер"})
ok(S.get(sid)["theme"]["fonts"] == "strict" and S.get(sid)["menu"]["style"] == "burger" and len(CALLS) == n0, "шрифт и меню — быстрыми правилами, модель не нужна")
texts = json.dumps(S.get(sid)["pages"], ensure_ascii=False)
tb.run("site_edit", {"request": "другой дизайн целиком"})
s2 = S.get(sid)
ok(s2["template"] != "coffee" and s2["theme"]["palette"] != "pistachio", f"«другой дизайн целиком» — {s2['template']}, палитра {s2['theme']['palette']}")
ok(all(b.get("title") in texts for b in s2["pages"][0]["blocks"] if b.get("title")), "тексты остались те же")
r = tb.run("site_edit", {"request": "добавь вопросы о молоке после раздела о нас и место для отзывов"})
bl = S.get(sid)["pages"][0]["blocks"]
types = [b["type"] for b in bl]
ok("faq" in types and types.index("faq") == types.index("about") + 1, f"сложная правка — моделью, операциями: faq после «О нас» ({types})")
rv = next(b for b in bl if b["type"] == "reviews")
ok(rv.get("items") == [{"text": "Лучший кофе в городе!", "name": "Ирина"}] or rv.get("items") == [], "отзывы: только те, что дали (модель здесь «дала» один — он с текстом)")
ok("Добавила вопросы" in r, "ответ модели — что сделала")
hist = S.history(sid)
ok(len(hist) >= 6 and hist[0]["label"].startswith("«добавь вопросы"), f"каждая правка — версия ({len(hist)}): {hist[0]['label'][:40]}")
tb.run("site_edit", {"request": "верни как было"})
ok("faq" not in [b["type"] for b in S.get(sid)["pages"][0]["blocks"]], "«верни как было» — вопросов нет")
tb.run("site_edit", {"request": "верни как было"})
ok(S.get(sid)["template"] == "coffee", "ещё раз — и дизайн кофейни вернулся")

r = tb.run("site_review", {})
ok("из 100" in r and "Что улучшить" in r and "не опубликован" in r and "советов" in r, f"site_review: проверка и просьба дать советы ({r[:80]})")
au = S.audit(sid)
bad = [x for x in au["items"] if not x["ok"]]
ok(all(x["fix"] for x in bad) and any(x["title"] == "Цены" for x in bad), f"у каждого «что улучшить» — фраза для Лиры; пустая цена замечена ({[x['title'] for x in bad]})")
q = tb.describe("site_publish", {"name": "zerno"})
ok("zerno.dewiar.pro" in q and "виден всем" in q, f"«Выполнить?» с адресом: {q}")
try:
    tb.run("site_publish", {"name": "www"})
    ok(False, "служебное имя — отказ")
except T.ToolError as e:
    ok("не подходит" in str(e) and "предложи" in str(e).lower(), f"служебное имя — Лира предложит другие: {str(e)[:70]}")
r = tb.run("site_show", {})
ok("ещё не опубликован" in r, "site_show — открыть и сказать, что не опубликован")

import engine_commands  # noqa: E402
ok("sites_" in engine_commands._KIDS_LOCKED, "в детском режиме команд «Сайтов» нет")
ok((ROOT / "data/skills/site-builder/SKILL.md").read_text().startswith("---\nname: site-builder"), "навык site-builder")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
