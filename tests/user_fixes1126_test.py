"""Жалобы 26.11 (утро):
- №1106 «самопроверка Excel: проверяющая модель говорит, что формул нет» — выдержка .xlsx брала только значения (data_only),
  а у свежего файла клетки с формулами пусты: теперь «=ФОРМУЛА» (и «→ значение», если оно посчитано);
- №1103 «в 1.0.79 для Windows нет openpyxl, python-docx, python-pptx, а навыки пишут, что есть» — теперь в поставке
  (requirements-win.txt и .lock, и requirements.txt для Linux и macOS);
- №1101 «Беларусь: „12 рублей“ голосом записываются в российских» — распознавание пишет «12 ₽»; у кого основная валюта
  BYN, ₽ без «российских» — это просто рубли (и в разборе фразы, и когда валюту передала модель);
- №1100 «в конструкторе сайта нужен модуль с 3 галочками: согласие, политика, оферта» — с 01.09.2025 согласие на
  обработку ПД — отдельно от других документов: своя галочка на согласие, на политику и на оферту (если она есть);
- №1105 (телефон без своего распознавания): подсказка «войдите аккаунтом» говорит, что своя модель останется."""
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- №1106 ----------
import openpyxl  # noqa: E402
from quality_files import file_text  # noqa: E402
d = Path(tempfile.mkdtemp())
f = d / "смета.xlsx"
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Работа", "Цена"])
ws.append(["Окраска", 120])
ws.append(["Шпаклёвка", 80])
ws.append(["Итого", "=SUM(B2:B3)"])
wb.create_sheet("Сводка").append(["НДС", "=B4*0.2"])
wb.save(f)
t = file_text(f)
ok("=SUM(B2:B3)" in t and "Окраска\t120" in t, f"формулы видны проверяющей модели (файл ещё не открывали в Excel): {t!r}")
ok("# лист Сводка" in t and "=B4*0.2" in t, "несколько листов — с названиями")
# посчитанное значение (как после Excel) — рядом с формулой
import zipfile  # noqa: E402
g = d / "посчитан.xlsx"
with zipfile.ZipFile(f) as zi, zipfile.ZipFile(g, "w") as zo:
    for it in zi.infolist():
        b = zi.read(it.filename)
        if it.filename == "xl/worksheets/sheet1.xml":
            b = re.sub(rb"<f>SUM\(B2:B3\)</f><v\s*/>|<f>SUM\(B2:B3\)</f><v></v>|<f>SUM\(B2:B3\)</f>", b"<f>SUM(B2:B3)</f><v>200</v>", b)
        zo.writestr(it, b)
ok("=SUM(B2:B3) → 200" in file_text(g), f"посчитано Excel — формула и значение: {file_text(g)[:80]!r}")

# ---------- №1103 ----------
for fn in ("requirements.txt", "requirements-win.txt"):
    s = (ROOT / fn).read_text(encoding="utf-8")
    ok(all(re.search(rf"^{p}>=", s, re.M) for p in ("openpyxl", "python-docx", "python-pptx")), f"{fn}: openpyxl, python-docx, python-pptx")
lock = (ROOT / "requirements-win.lock").read_text(encoding="utf-8")
ok(all(re.search(rf"^{p}==", lock, re.M) for p in ("openpyxl", "python-docx", "python-pptx", "lxml", "et-xmlfile", "xlsxwriter", "socksio")),
   "requirements-win.lock: они и их зависимости закреплены (установщик ставит по нему)")
ok(re.search(r"^numpy==1\.26\.4$", lock, re.M), "остальное не сдвинулось (numpy 1.26.4, проверенный под Wine)")

# ---------- №1101 ----------
import money as M  # noqa: E402
ok(M._currency("12 ₽ на транспорт", "BYN") == "BYN", "BYN по умолчанию: «12 ₽» из распознавания — белорусские")
ok(M._currency("12 российских рублей на такси", "BYN") == "RUB", "«российских» — российские")
ok(M._currency("12 ₽", "RUB") == "RUB" and M._currency("12 $", "BYN") == "USD", "у кого RUB — как было; другие валюты — как названы")
import tools_money as TM  # noqa: E402


class FakeMoney:
    def __init__(self):
        self.got = None

    def currency(self):
        return "BYN"

    def add(self, kind, amount, cur, cat, note, date):
        self.got = cur
        return {"kind": kind, "amount": amount, "currency": cur or "BYN", "category": cat or "Транспорт", "date": "2026-11-26"}


fm = FakeMoney()
TM.t_money_add({"kind": "expense", "amount": 12, "currency": "RUB", "category": "Транспорт"}, {"money": fm, "turn_text": lambda: "12 ₽ на транспорт"})
ok(fm.got is None, "модель поставила RUB по знаку ₽ — записано в основной (BYN)")
TM.t_money_add({"kind": "expense", "amount": 12, "currency": "RUB"}, {"money": fm, "turn_text": lambda: "12 российских рублей"})
ok(fm.got == "RUB", "сказали «российских» — RUB")

# ---------- №1100 ----------
from sites_blocks import pd_consent  # noqa: E402


class C:
    def __init__(self, docs):
        self.site = {"legal": {"docs": docs}}


link = lambda u: {"mode": "link", "url": u}
h = pd_consent(C({"privacy": link("https://disk.yandex.ru/p"), "consent": link("https://disk.yandex.ru/c"), "oferta": link("https://disk.yandex.ru/o")}))
boxes = re.findall(r'<input type="checkbox" name="(\w+)" value="1" required>', h)
ok(boxes == ["pd_ok", "pd_pol", "pd_of"], f"три отдельные обязательные галочки — согласие, политика, оферта: {boxes}")
ok('href="https://disk.yandex.ru/c"' in h and 'href="https://disk.yandex.ru/p"' in h and 'href="https://disk.yandex.ru/o"' in h,
   "у каждой — ссылка на свой документ (хоть на диск в облаке)")
h2 = pd_consent(C({"privacy": link("https://disk.yandex.ru/p")}))
ok(re.findall(r'name="(pd_\w+)" value="1" required', h2) == ["pd_ok", "pd_pol"], "оферты нет — две галочки")
ok(pd_consent(C({})) == "", "политики нет — галочек нет (как было)")
ok('name="pd_need" value="1"' in h, "серверу — как раньше: без согласия заявку не принять")

# ---------- №1105 ----------
js = (ROOT / "android/www-src/app/06-ears-voice.js").read_text(encoding="utf-8")
ok(js.count("слушать будет сервер Dewiar, а ваша модель останется") == 2, "подсказка про вход: своя модель останется")

# ---------- №1110: рамка вокруг ползунка громкости после щелчка ----------
from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p_:
    b_ = p_.chromium.launch()
    pg = b_.new_page()
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1")
    pg.wait_for_timeout(1200)
    res = []
    for cls in ("", "st-light st-neu st-skin"):
        pg.evaluate(f"""() => {{ document.documentElement.className = {cls!r}; let r = document.getElementById('t-rng');
            if (!r) {{ r = document.createElement('input'); r.type = 'range'; r.id = 't-rng'; document.body.prepend(r); }} r.focus(); }}""")
        res.append(pg.evaluate("() => { const c = getComputedStyle(document.getElementById('t-rng')); return [c.boxShadow, c.backgroundColor]; }"))
    b_.close()
ok(all(x[0] == "none" and x[1] in ("rgba(0, 0, 0, 0)", "transparent") for x in res), f"№1110: ползунок в фокусе — без рамки и подложки (тёмная и светлая тема): {res}")

# ---------- №1111: английское название станции вслух ----------
from speechnorm import speech_norm  # noqa: E402
ok("дип спейс уан" in speech_norm("Включаю Deep Space One.", latin=True).lower(), "№1111: «Deep Space One» — «дип спейс уан»")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
