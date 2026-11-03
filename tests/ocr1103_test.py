"""Идеи людей №68 и №83 (03.11): распознавание текста и «Вырезать кусок экрана».
— №68: «ассистенты падают или отвечают пусто на сканах PDF и фото». core/ocr.py: локальный движок (rapidocr, tesseract),
  иначе модель со зрением, иначе — понятно, что поставить; PDF без текстового слоя рисуется и распознаётся. Подключено к
  read_file, новому инструменту ocr, вложениям к вопросу и «Документам» (сканы распознаются в фоне).
— №83: «в блокноте — вырезать с экрана и скопировать в текст». Кнопка ✂ в блокноте и «вырежи кусок экрана» голосом:
  окно выделения (ui/snip.html) → кусок картинкой в блокнот, текст — под ней и в буфер обмена, тост «Текст скопирован».
Настоящего распознавания в окружении не нужно: движки подставные. Живая проверка — если rapidocr или tesseract стоят."""
import base64, io, json, os, sys, tempfile, threading, time, urllib.parse
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from PIL import Image, ImageDraw, ImageFont  # noqa: E402
import ocr  # noqa: E402

REAL = list(ocr.ENGINES)


def text_png(lines=("Hello world 42",), size=(900, 200)):
    try:
        f = ImageFont.truetype("DejaVuSans.ttf", 40)
    except OSError:
        try:
            f = ImageFont.load_default(size=40)
        except TypeError:
            f = ImageFont.load_default()
    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    for i, t in enumerate(lines):
        d.text((20, 30 + 80 * i), t, fill="black", font=f)
    return im


seen = []


def fake(name, text, ru=True):
    def run(im):
        seen.append((name, im.size))
        return text, ru
    return ocr.Engine(name, lambda: True, run, name.title(), lambda: ru)


# ---------- ocr_image: подставной движок ----------
ocr.ENGINES = [fake("ru", "Счёт № 15\nИтого 1 200 ₽")]
ok(ocr.ocr_image(text_png()) == "Счёт № 15\nИтого 1 200 ₽", "ocr_image: текст от локального движка")
ok(ocr.recognize(text_png())[1] == "ru", "recognize: известно, кто распознал")
buf = io.BytesIO(); text_png().save(buf, "PNG")
ok(ocr.ocr_image(buf.getvalue()) and ocr.ocr_image("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()),
   "картинка — байтами и data:-адресом")
p_img = tmp / "фото.png"; p_img.write_bytes(buf.getvalue())
ok(ocr.ocr_image(p_img).startswith("Счёт"), "…и путём к файлу")
seen.clear(); ocr.ocr_image(Image.new("RGB", (400, 24), "white"))
ok(seen and seen[-1][1][1] >= 72, f"строка 400×24 увеличена для движка: {seen[-1:]}")
ok(ocr.lines_from_boxes([([[200, 10], [300, 10], [300, 30], [200, 30]], "мир"), ([[10, 12], [90, 12], [90, 31], [10, 31]], "Привет,"),
                         ([[10, 60], [90, 60], [90, 80], [10, 80]], "дальше")]) == "Привет, мир\nдальше", "куски рамок — в строки слева направо")
try:
    ocr.load(b"not an image"); ok(False, "не картинка — ошибка")
except ocr.OCRError as e:
    ok("не картинка" in str(e), "не картинка — понятная ошибка")

# ---------- откат на модель со зрением ----------
asked = []


def vision(b64):
    asked.append(len(b64))
    return "Распознала моделью"


ocr.ENGINES = []
ok(ocr.recognize(text_png(), vision=vision) == ("Распознала моделью", "vision") and asked, "движка нет — текст читает модель со зрением")
ok(ocr.ocr_image(text_png(), vision=lambda b: "НЕТ ТЕКСТА") == "", "модель: «НЕТ ТЕКСТА» — пустой текст, не слова «нет текста»")
try:
    ocr.ocr_image(text_png(), vision=lambda b: "Извините, я не могу открыть изображение, приложенное к сообщению.")
    ok(False, "модель без зрения — не текст")
except ocr.OCRError as e:
    ok("Поставьте распознавание" in str(e), f"модель без зрения ответила словами — это не текст, а совет поставить: {e}")
ocr.ENGINES = [fake("latin", "Npuset, mup!", ru=False)]
ok(ocr.recognize(text_png(), vision=vision)[1] == "vision", "движок без русского — сначала модель со зрением (он делает кашу из кириллицы)")
ok(ocr.recognize(text_png()) == ("Npuset, mup!", "latin"), "…а без модели — хоть латиницей")
ocr.ENGINES = [fake("latin", "x", ru=False), fake("ru", "Привет")]
ok(ocr.recognize(text_png())[1] == "ru", "движок с русским важнее движка без него")

# ---------- нечем — понятное сообщение ----------
ocr.ENGINES = []
try:
    ocr.ocr_image(text_png()); ok(False, "нечем распознавать — ошибка")
except ocr.OCRError as e:
    ok("распознавания текста" in str(e).lower() and "Поставить" in str(e) and "«Мозг»" in str(e), f"нечем — что поставить словами: {e}")
broken = ocr.Engine("tesseract", lambda: True, lambda im: (_ for _ in ()).throw(RuntimeError("rus.traineddata не найден")), "Tesseract")
ocr.ENGINES = [broken]
try:
    ocr.ocr_image(text_png()); ok(False, "движок упал — ошибка")
except ocr.OCRError as e:
    ok("Tesseract" in str(e) and "traineddata" in str(e), f"движок упал — причина в сообщении: {e}")
ocr.ENGINES = [ocr.Engine("x", lambda: (_ for _ in ()).throw(ImportError("сломан")), lambda im: ("", True), "X")]
ok(ocr.local_engines() == [] and ocr.status()["local"] is False, "сломанная проверка движка — просто «нет движка»")

# ---------- PDF без текстового слоя идёт в распознавание ----------
scan = tmp / "Скан договора.pdf"
pg1 = text_png(("Договор поставки",), (1240, 1754))
pg2 = text_png(("Приложение 1",), (1240, 1754))
pg1.save(scan, "PDF", save_all=True, append_images=[pg2], resolution=150)
ok(ocr.pdf_texts(scan) == ["", ""] or all(ocr.is_scan(t) for t in ocr.pdf_texts(scan)), "в скане нет текстового слоя")
ok(ocr.pdf_needs_ocr(scan), "pdf_needs_ocr видит сканы")
pages = []


def page_eng(im):
    pages.append(im.size)
    return f"Текст страницы {len(pages)}", True


ocr.ENGINES = [ocr.Engine("ru", lambda: True, page_eng, "Ru")]
r = ocr.ocr_pdf_ex(scan)
ok(r["ocr_pages"] == [1, 2] and "[стр. 1]\nТекст страницы 1" in r["text"] and "[стр. 2]" in r["text"],
   f"обе страницы-скана нарисованы ({ocr.pdf_renderer()}) и распознаны: {r}")
ok(min(pages[0]) > 600, f"страница нарисована крупно для распознавания: {pages[0]}")
pages.clear()
ok(ocr.ocr_pdf(scan, pages="2") == "Текст страницы 1" and len(pages) == 1, "pages=«2» — только вторая страница")
ok(ocr.parse_pages("1-3, 5", 4) == [0, 1, 2] and ocr.parse_pages("", 2) == [0, 1], "номера страниц: «1-3, 5» в пределах документа")
# обычный PDF с одной пустой страницей — не скан: не гоняем распознавание по большим папкам «Документов»
from pypdf import PdfWriter  # noqa: E402
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject  # noqa: E402


def text_pdf(path, texts):
    w = PdfWriter()
    for t in texts:
        pg = w.add_blank_page(612, 792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        pg[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})})
        st = DecodedStreamObject()
        st.set_data(f"BT /F1 9 Tf 40 700 Td ({t}) Tj ET".encode() if t else b"")
        pg.replace_contents(st)
    w.write(path)


mix = tmp / "mix.pdf"
text_pdf(mix, ["Payment terms are ten banking days after delivery of the goods " * 2, "", "The second page has plenty of text as well " * 3])
ok(not ocr.pdf_needs_ocr(mix) and ocr.pdf_needs_ocr(mix, mostly=False), "PDF с текстом и одной пустой страницей — не скан")
info, n0 = {}, len(pages)
import knowledge as _kn  # noqa: E402
ok("Payment terms" in _kn.extract(mix, ocr="local", info=info) and not info.get("scan") and len(pages) == n0,
   "его текст — как есть, распознавание не запускалось")
# нечем нарисовать (нет pypdfium2/pymupdf/pdftoppm) — берём картинку, вложенную в страницу
spec0, which0 = ocr._spec, ocr.shutil.which
ocr._spec = lambda m: False
ocr.shutil.which = lambda x: None
try:
    im = ocr.page_image(scan, 0)
    ok(im is not None and im.size[0] > 600, f"без отрисовки — картинка страницы из PDF (pypdf): {im and im.size}")
finally:
    ocr._spec, ocr.shutil.which = spec0, which0
ocr.ENGINES = []
try:
    ocr.ocr_pdf(scan); ok(False, "скан без распознавания — ошибка")
except ocr.OCRError as e:
    ok("Поставьте распознавание" in str(e), "скан, распознавать нечем — понятное сообщение, а не пустой ответ")

# ---------- «Документы» и вложения: extract ----------
import knowledge  # noqa: E402
info = {}
ok(knowledge.extract(scan, info=info).strip() == "" and info.get("scan") is True, "extract без распознавания — как раньше, но с пометкой «скан»")
pages.clear()
ocr.ENGINES = [ocr.Engine("ru", lambda: True, page_eng, "Ru")]
info = {}
t = knowledge.extract(scan, ocr="local", info=info)
ok("Текст страницы 1" in t and info.get("scan") == "done" and info.get("ocr_pages") == [1, 2], f"extract(ocr=«local») — распознанный текст: {t[:60]}")
ocr.ENGINES = []
ok(knowledge.extract(scan, ocr=lambda b: "Текст моделью").count("Текст моделью") == 2, "extract с моделью со зрением — страницы читает модель")


class WS:
    root = tmp / "kn"


(WS.root / "Знания").mkdir(parents=True)
(WS.root / "Знания" / "Скан договора.pdf").write_bytes(scan.read_bytes())
kn = knowledge.Knowledge(WS(), tmp / "kn.json")
kn.refresh()
e = kn.index["Скан договора.pdf"]
ok(e.get("scan") is True and not e["chunks"] and "распознается" in e.get("error", ""), f"«Документы»: скан помечен, ждёт распознавания: {e.get('error')}")
ok(kn.ocr_scans() == 0 and kn.index["Скан договора.pdf"].get("scan") is True, "движка нет — скан ждёт (поставят — распознается)")
ocr.ENGINES = [ocr.Engine("ru", lambda: True, lambda im: ("Срок оплаты — десять банковских дней", True), "Ru")]
ok(kn.ocr_scans() == 1, "фоновый проход распознал скан")
e = kn.index["Скан договора.pdf"]
ok(e.get("scan") == "done" and e["chunks"] and not e.get("error"), "в индексе — распознанный текст, ошибки нет")
res = kn.search("срок оплаты")
ok(res and "банковских" in res[0]["text"], f"поиск по документам находит текст скана: {res[:1]}")
kn.refresh()
ok(kn.index["Скан договора.pdf"].get("scan") == "done", "сверка не сбрасывает распознанное (файл не менялся)")

# ---------- инструменты: read_file и ocr ----------
import tools as T  # noqa: E402
from settings import Settings  # noqa: E402
from workspace import Workspace  # noqa: E402
S = Settings(tmp / "cfg" / "settings.json")
ws = Workspace(S)
(ws.ensure() / "Входящие").mkdir(exist_ok=True)
(ws.ensure() / "Входящие" / "скан.pdf").write_bytes(scan.read_bytes())
(ws.ensure() / "Входящие" / "чек.png").write_bytes(buf.getvalue())


class Eng:
    def __init__(self, v=None):
        self.v = v
        self.installs = 0

    def ocr_vision(self, b64):
        if self.v is None:
            raise RuntimeError("модель не видит картинок")
        return self.v

    def ocr_install_start(self):
        self.installs += 1
        return "Ставлю распознавание текста"


ctx = {"workspace": ws, "engine": Eng()}
ok("ocr" in T.TOOLS and "ocr" in T.SAFE_CORE and T.TOOLS["ocr"][2] == "safe", "инструмент ocr есть и безопасен (только читает)")
ocr.ENGINES = [ocr.Engine("ru", lambda: True, lambda im: ("ДОГОВОР № 7", True), "Ru")]
out = T.t_read_file({"path": "Входящие/скан.pdf"}, ctx)
ok(out.startswith("В скане распознан текст") and "ДОГОВОР № 7" in out, f"read_file: скан PDF — не пусто, а распознанный текст: {out[:80]}")
out = T.t_read_file({"path": "Входящие/чек.png"}, ctx)
ok("На картинке распознан текст" in out and "ДОГОВОР" in out, "read_file: картинка — распознанный текст, а не «не текстовый файл»")
out = T.t_ocr({"path": "чек.png"}, dict(ctx, workspace=ws))
ok("ДОГОВОР" in out, "ocr: файл по имени ищется сам (папка ассистента, «Загрузки»…)")
out = T.t_ocr({"path": str(ws.ensure() / "Входящие" / "скан.pdf"), "pages": "1"}, ctx)
ok("ДОГОВОР" in out and "страницы 1" in out, f"ocr: полный путь и страницы: {out[:70]}")
(ws.ensure() / "x.txt").write_text("hi")
for bad, want in (({"path": "x.txt"}, "не картинка"), ({"path": "нет-такого.png"}, "не нашлось"), ({}, "назови файл")):
    try:
        T.t_ocr(bad, ctx); ok(False, f"ocr {bad} — ошибка")
    except T.ToolError as e:
        ok(want in str(e), f"ocr {bad} — {e}")
ocr.ENGINES = []
try:
    T.t_read_file({"path": "Входящие/скан.pdf"}, ctx); ok(False, "скан без распознавания — ошибка")
except T.ToolError as e:
    ok("Поставьте распознавание" in str(e), "read_file: скан, распознавать нечем — модель узнаёт, что поставить")
out = T.t_read_file({"path": "Входящие/скан.pdf"}, {"workspace": ws, "engine": Eng("Договор моделью")})
ok("Договор моделью" in out, "read_file: нет движка — читает модель со зрением")
e2 = Eng()
ok(T.t_ocr({"install": True}, {"workspace": ws, "engine": e2}) == "Ставлю распознавание текста" and e2.installs == 1,
   "ocr install — «Поставить распознавание текста»")

# ---------- «Поставить распознавание»: pydeps с зависимостями ----------
import pydeps  # noqa: E402
cmds = pydeps._installers(*pydeps._spec("rapidocr")[:1], tmp / "t", pydeps._spec("rapidocr")[1])
ok(all("--no-deps" not in c for c in cmds) and any(any(x.startswith("rapidocr") for x in c) for c in cmds)
   and any(any(x.startswith("opencv-python-headless") for x in c) for c in cmds), "rapidocr ставится с зависимостями, opencv — без окна и до 4.12")
ok("--no-deps" in pydeps._installers("onnx-asr>=0.12", tmp / "t")[0], "слух (onnx_asr) — как раньше, без зависимостей")
st = []
real_ensure = pydeps.ensure
pydeps.ensure = lambda m, on_status=None, run=None: (False, "нет связи с pypi.org (интернет или прокси)")
ok(ocr.install(st.append) == (False, "нет связи с pypi.org (интернет или прокси)"), "не поставилось — причина словами")
pydeps.ensure = real_ensure

# ---------- голосом: «вырежи кусок экрана» ----------
from engine_base import window_phrase  # noqa: E402
for ph in ("Лира, вырежи кусок экрана", "скопируй текст с экрана", "распознай текст на экране", "вырежи часть экрана пожалуйста"):
    ok(window_phrase(ph) == "snip", f"«{ph}» — окно выделения без модели")
for ph in ("вырежи этот абзац", "скопируй текст", "сделай скриншот", "давай поиграем"):
    ok(window_phrase(ph) != "snip", f"«{ph}» — не вырезание")

# ---------- ядро: снимок, вырезка в блокнот, текст событием ----------
from engine_commands import CommandsMixin  # noqa: E402
from pad import Pad  # noqa: E402
screen = text_png(("Привет из окна",), (1600, 900))
fake_screen = tmp / "screen.png"; screen.save(fake_screen)
os.environ["DEWIAR_FAKE_SCREEN"] = str(fake_screen)
events = []


class Core(CommandsMixin):
    SNIP_KEEP = 0.6

    def __init__(self):
        self.pad = Pad(ws, S, emit=self.emit)
        self._blind = set()
        self.notes = []

    def emit(self, type_, **kw):
        events.append(dict(kw, type=type_))

    def note(self, t):
        self.notes.append(t)

    def persona_llm(self):
        return None


eng = Core()
ocr.ENGINES = [ocr.Engine("ru", lambda: True, lambda im: (f"Текст {im.size[0]}", True), "Ru")]
shot = eng._snip_cmd("snip_shot", {})
ok(shot["w"] == 1600 and shot["h"] == 900 and shot["url"].startswith("data:image/jpeg;base64,"), "snip_shot: снимок экрана для окна выделения")
r = eng._snip_cmd("snip_done", {"id": shot["id"], "rect": [100, 40, 500, 60]})
att = list((ws.ensure() / "Заметки/Блокнот/Вложения").glob("Вырезано*.png"))
ok(r["line"].startswith("![Вырезано") and len(att) == 1 and Image.open(att[0]).size == (500, 60), f"кусок 500×60 — картинкой во «Вложения» блокнота: {r}")
ok(any(e["type"] == "snip" and e["state"] == "image" for e in events), "событие snip: картинка")
for _ in range(50):
    if any(e["type"] == "snip" and e["state"] == "text" for e in events):
        break
    time.sleep(0.05)
ev = next((e for e in events if e["type"] == "snip" and e["state"] == "text"), {})
ok(ev.get("text", "").startswith("Текст") and ev.get("engine") == "ru", f"событие snip: распознанный текст: {ev}")
ok(eng._snip_cmd("snip_take", {}) and eng._snip_cmd("snip_take", {})[0]["text"] == ev.get("text"), "snip_take — блокнот, открывшийся позже, заберёт вырезанное")
try:
    eng._snip_cmd("snip_done", {"id": shot["id"], "rect": [0, 0, 10, 10]}); ok(False, "второй раз тот же снимок — ошибка")
except ValueError as e:
    ok("устарел" in str(e), "снимок используется один раз (в памяти не копится)")
time.sleep(0.9)
tab = (ws.ensure() / "Заметки/Блокнот" / f"{eng.pad.tabs()['active']}.md").read_text(encoding="utf-8")
ok("![Вырезано" in tab and ev.get("text", "#") in tab, f"блокнот не открылся — ядро само дописало картинку и текст во вкладку: {tab[-80:]!r}")
ok(any(e["type"] == "pad_changed" for e in events) and eng.notes, "открытый лист перечитает вкладку; в виджете — заметка")
# блокнот вставил сам — ядро не дублирует
events.clear()
shot = eng._snip_cmd("snip_shot", {})
eng._snip_cmd("snip_done", {"id": shot["id"], "rect": [0, 0, 300, 100]})
for _ in range(50):
    if any(e["type"] == "snip" and e["state"] == "text" for e in events):
        break
    time.sleep(0.05)
sid = shot["id"]
eng._snip_cmd("snip_ack", {"id": sid, "stage": "image"}); eng._snip_cmd("snip_ack", {"id": sid, "stage": "text"})
before = (ws.ensure() / "Заметки/Блокнот" / f"{eng.pad.tabs()['active']}.md").read_text(encoding="utf-8")
time.sleep(0.9)
ok((ws.ensure() / "Заметки/Блокнот" / f"{eng.pad.tabs()['active']}.md").read_text(encoding="utf-8") == before and not eng._snip_cmd("snip_take", {}),
   "блокнот вставил (snip_ack) — ядро ничего не дописывает второй раз")
ocr.ENGINES = []
events.clear()
shot = eng._snip_cmd("snip_shot", {})
eng._snip_cmd("snip_done", {"id": shot["id"], "rect": [0, 0, 300, 100]})
for _ in range(50):
    if any(e["type"] == "snip" and e["state"] == "text" for e in events):
        break
    time.sleep(0.05)
ev = next((e for e in events if e["type"] == "snip" and e["state"] == "text"), {})
ok(ev.get("error") and ev.get("install") is True, f"нечем распознать — ошибка и кнопка «Поставить»: {ev.get('error', '')[:60]}")
time.sleep(0.8)
del os.environ["DEWIAR_FAKE_SCREEN"]

# ---------- страницы: кнопка в блокноте, окно выделения ----------
src_pad = (ROOT / "ui/pad.html").read_text(encoding="utf-8")
ok('id="b-snip"' in src_pad and "Вырезать кусок экрана" in src_pad and 'id="toast"' in src_pad, "в блокноте есть кнопка «Вырезать кусок экрана» и тост")
src_app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok(all(f"def {m}(" in src_app for m in ("snip_open", "snip_show", "snip_close", "clip_text")) and '"snip.html"' in src_app,
   "окно программы: snip_open / snip_show / snip_close, буфер обмена — clip_text")
ok('e.do === "snip" && a.snip_open' in (ROOT / "ui/hud.html").read_text(encoding="utf-8"), "виджет открывает окно выделения по голосу")
guide = json.loads((ROOT / "data/guide.json").read_text(encoding="utf-8"))
ok(any(a["id"] == "ocr" and "вырежи кусок экрана" in json.dumps(a, ensure_ascii=False).lower() for a in guide), "статья в руководстве")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
    print("— playwright нет: страницы не проверены")

CORE = r"""
(() => { window.calls = []; window.apiCalls = [];
  window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { apiCalls.push([k, ...a]); return Promise.resolve(k === "clip_text" ? true : true); } }) };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: "Было\n", mtime: 1 };
      if (c === "pad_write") return { mtime: 2 };
      if (c === "pad_file") return { url: window.PNG };
      if (c === "snip_take") return [];
      if (c === "snip_shot") return { id: "s1", url: window.PNG, w: 1600, h: 900 };
      if (c === "snip_done") return { id: "s1" };
      return {}; }; };
  ready(); })();
"""
if sync_playwright:
    png = "data:image/png;base64," + base64.b64encode(fake_screen.read_bytes()).decode()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 520, "height": 640})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script(f"window.PNG = {json.dumps(png)};"); pg.add_init_script(CORE)
        pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=brand&cfg=" + urllib.parse.quote(json.dumps({"side": "left", "gap": 14, "clips": []})))
        pg.wait_for_timeout(1300)
        ok(pg.is_visible("#b-snip"), "кнопка ✂ видна на панели блокнота (окно Dewiar)")
        pg.click("#b-snip"); pg.wait_for_timeout(200)
        ok(any(c[0] == "snip_open" and c[1] == "pad" for c in pg.evaluate("apiCalls")), "кнопка открывает окно выделения")
        pg.evaluate("""core.emit("snip", {id: "s1", tab: "Главное", state: "image", line: "![Вырезано](Вложения/Вырезано%201.png)"})""")
        pg.wait_for_timeout(250)
        ok(pg.evaluate("!!document.querySelector('#ed img[data-src=\"Вложения/Вырезано%201.png\"]')"), "вырезанное — картинкой в конец вкладки")
        pg.evaluate("""core.emit("snip", {id: "s1", tab: "Главное", state: "text", line: "![Вырезано](Вложения/Вырезано%201.png)", text: "Строка <один>\\nстрока два\\n\\nАбзац"})""")
        pg.wait_for_timeout(400)
        html = pg.inner_html("#ed").replace(' class="snip-new"', "")
        ok("Строка &lt;один&gt;<br>строка два" in html and "<p>Абзац</p>" in html, f"текст — под картинкой, абзацами, без разметки из текста: {html[-160:]}")
        ok(pg.evaluate("apiCalls.some(c => c[0] === 'clip_text' && c[1].includes('строка два'))"), "текст — в буфер обмена (clip_text)")
        ok(pg.is_visible("#toast") and pg.inner_text("#toast-t") == "Текст скопирован", "тост «Текст скопирован»")
        pg.wait_for_timeout(1800)
        md = pg.evaluate("PadMD.html2md(document.querySelector('#ed').innerHTML)")
        ok("![" in md and "Вложения/Вырезано%201.png" in md and "строка два" in md and "snip-new" not in md, f"во вкладку (Markdown) — картинка и текст: {md[-90:]!r}")
        acks = [c[1]["stage"] for c in pg.evaluate("calls") if c[0] == "snip_ack"]
        ok(acks == ["image", "text"], f"блокнот сказал ядру, что вставил: {acks}")
        pg.evaluate("""core.emit("snip", {id: "s1", tab: "Главное", state: "text", line: "![Вырезано](Вложения/Вырезано%201.png)", text: "Абзац"})""")
        pg.wait_for_timeout(200)
        ok(pg.evaluate("document.querySelectorAll('#ed img').length") == 1 and pg.inner_html("#ed").count("Абзац") == 1, "повтор события не дублирует")
        pg.evaluate("""core.emit("snip", {id: "s2", tab: "Главное", state: "text", line: "![В](Вложения/В2.png)", error: "нечем", install: true})""")
        pg.wait_for_timeout(300)
        ok(pg.is_visible("#toast-b") and "распознать текст нечем" in pg.inner_text("#toast-t"), "нечем распознать — тост с кнопкой «Поставить»")
        pg.click("#toast-b"); pg.wait_for_timeout(150)
        ok(any(c[0] == "ocr_install" for c in pg.evaluate("calls")), "«Поставить» — ocr_install")
        ok(not errs, f"блокнот без ошибок: {errs}")

        # окно выделения
        pg = b.new_page(viewport={"width": 1200, "height": 800})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script(f"window.PNG = {json.dumps(png)};"); pg.add_init_script(CORE)
        pg.goto((ROOT / "ui/snip.html").as_uri())
        pg.wait_for_timeout(1900)
        ok(pg.evaluate("apiCalls.some(c => c[0] === 'snip_show')"), "снимок нарисован — окно показывается (snip_show)")
        box = pg.evaluate("(() => { const r = document.querySelector('#shot').getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; })()")
        ok(abs(box[2] - 1200) < 1 and abs(box[3] - 675) < 1 and abs(box[1] - 62.5) < 1, f"снимок 1600×900 вписан в окно 1200×800: {box}")
        pg.mouse.move(300, 162.5); pg.mouse.down(); pg.mouse.move(450, 200, steps=4)
        ok(pg.is_visible("#box") and "200 × 50" in pg.inner_text("#size"), f"рамка и размер в пикселях снимка: {pg.inner_text('#size')}")
        pg.mouse.move(600, 237.5, steps=3); pg.mouse.up(); pg.wait_for_timeout(300)
        done = [c[1] for c in pg.evaluate("calls") if c[0] == "snip_done"]
        ok(done and [round(v) for v in done[0]["rect"]] == [400, 133, 400, 100], f"рамка — в пикселях снимка экрана: {done}")
        ok(pg.evaluate("apiCalls.some(c => c[0] === 'snip_close' && c[1] === true)"), "вырезали — окно закрывается, блокнот откроется")
        pg.reload(); pg.wait_for_timeout(1900)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        ok(any(c[0] == "snip_cancel" for c in pg.evaluate("calls")) and pg.evaluate("apiCalls.some(c => c[0] === 'snip_close' && c[1] === false)"),
           "Esc — отмена: снимок забыт, окно закрыто")
        pg.reload(); pg.wait_for_timeout(1900)
        pg.mouse.click(500, 400); pg.wait_for_timeout(200)
        ok(not any(c[0] == "snip_done" for c in pg.evaluate("calls")), "щелчок без рамки ничего не вырезает")
        ok(not errs, f"окно выделения без ошибок: {errs}")
        if os.environ.get("OCR_SHOTS"):
            pg.screenshot(path=os.path.join(os.environ["OCR_SHOTS"], "snip-idle.png"))
            pg.mouse.move(300, 200); pg.mouse.down(); pg.mouse.move(700, 330, steps=4)
            pg.screenshot(path=os.path.join(os.environ["OCR_SHOTS"], "snip.png"))
            pg.mouse.up()
        b.close()

# ---------- живая проверка (если распознавание стоит) ----------
ocr.ENGINES = REAL
ocr._cache.clear()
live = ocr.local_engines()
if live:
    try:
        txt, who = ocr.recognize(text_png(("Hello world 42",)))
        ok("hello" in txt.lower() and "42" in txt, f"живое распознавание ({who}): {txt!r}")
    except ocr.OCRError as e:
        ok(False, f"живое распознавание упало: {e}")
else:
    print("— rapidocr / tesseract не установлены: живая проверка пропущена")

print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}: {fails}")
sys.exit(1 if fails else 0)
