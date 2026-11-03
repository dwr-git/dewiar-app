"""Распознавание текста на картинках и в сканах PDF (идеи людей №68 и №83, 03.11: «ассистенты падают или отвечают
пусто на сканах PDF и фото»; «в блокноте — вырезать кусок экрана и скопировать текст»).

Порядок — от того, что работает без интернета и бесплатно, к тому, что стоит запросов модели:
  1. локальный движок, который читает по-русски: rapidocr (PP-OCRv5 «eslav» — русский, украинский, белорусский и
     латиница; модель ≈ 8 МБ скачивается один раз в STATE_DIR/ocr-models), затем tesseract с языком rus;
  2. текущая модель со зрением (vision — функция ядра: картинка JPEG base64 -> текст);
  3. локальный движок только с английским (rapidocr без русской модели, старый rapidocr_onnxruntime, tesseract без rus):
     лучше, чем ничего, но русский текст он превращает в латинскую кашу — поэтому после модели со зрением;
  4. ничего нет — OCRError с понятным советом, что поставить (INSTALL_HINT).

ocr_image(картинка) -> текст; ocr_pdf(путь, pages) -> текст PDF, где страницы без текстового слоя отрисованы
(pypdfium2 / pymupdf / pdftoppm / картинка, вложенная в страницу, через pypdf) и распознаны.
install() — «Поставить распознавание текста»: rapidocr докачивается тем же путём, что недостающие библиотеки слуха
(pydeps — в свою папку STATE_DIR/pylib), затем скачивается русская модель.

Движки — список ENGINES (проверки подставляют свои). Каждый: have() — установлен ли (дёшево, без загрузки моделей),
run(PIL.Image) -> (текст, читает_ли_по-русски)."""

import base64
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

log = logging.getLogger("dewiar.ocr")
WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if WIN else 0

INSTALL_HINT = ("Поставьте распознавание текста: скажите «поставь распознавание текста» или нажмите «Поставить» в "
                "блокноте (около 70 МБ, один раз). Или выберите в студии → «Мозг» модель, которая видит картинки.")
NO_TEXT = "НЕТ ТЕКСТА"
VISION_PROMPT = ("Перепиши весь текст с этой картинки дословно, на языке оригинала, сохраняя строки и абзацы; таблицу — "
                 "строками через « | ». Только сам текст: без пояснений, без кавычек вокруг и без описания картинки. "
                 f"Если текста на картинке нет — ответь ровно: {NO_TEXT}")
# модель не увидела картинку («не могу открыть изображение», «I can't see the image») — это не текст с картинки
BLIND_RX = re.compile(r"(?:не\s+(?:могу|умею|получается|удаётся|удается|вижу)\s+(?:открыть|прочитать|просмотреть|посмотреть|"
                      r"увидеть|видеть|распознать)?[^.!?]{0,40}(?:изображен|картин|фото|скриншот|снимок|вложен))|"
                      r"(?:нет\s+доступа\s+к\s+(?:файлам\s+)?(?:картин|изображен|фото|вложен))|"
                      r"(?:cannot|can't|unable to)\s+(?:see|view|open|read)\s+(?:the\s+)?(?:image|picture|screenshot)", re.I)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
MIN_PAGE_TEXT = 25            # у страницы PDF меньше букв и цифр — считаем её сканом (номер страницы, колонтитул — не текст)
PDF_PAGES = 20                # сколько страниц-сканов одного PDF распознаём за раз локально (≈1–3 с на страницу)
VISION_PAGES = 5              # …и моделью со зрением (каждая страница — запрос)
PDF_DPI = 200
MAX_SIDE = 3600


class OCRError(Exception):
    """Распознать не получилось — текст ошибки можно показать человеку как есть."""


def models_dir():
    from settings import STATE_DIR
    return STATE_DIR / "ocr-models"


# ---------- картинка ----------

def load(src):
    """Путь, байты, data:-адрес или PIL.Image -> PIL.Image RGB (прозрачное — на белом: текст скриншотов на прозрачном
    фоне иначе становится чёрным по чёрному)."""
    from PIL import Image
    if isinstance(src, Image.Image):
        im = src
    else:
        if isinstance(src, str) and src.startswith("data:"):
            src = base64.b64decode(src.split(",", 1)[1])
        try:
            im = Image.open(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else str(src))
            im.load()
        except Exception as e:  # noqa: BLE001
            raise OCRError("это не картинка") from e
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    return im.convert("RGB")


def prepared(im):
    """Мелкий кусок экрана (строка 400×24) — крупнее: движки плохо читают буквы ниже ~20 px. Огромное — меньше."""
    from PIL import Image
    w, h = im.size
    if min(w, h) < 300:
        k = min(3.0, 300 / max(1, min(w, h)))
        im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    if max(im.size) > MAX_SIDE:
        k = MAX_SIDE / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    return im


def jpeg_b64(im, side=1600):
    from PIL import Image
    if max(im.size) > side:
        k = side / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def lines_from_boxes(items):
    """[(рамка из 4 точек, текст)] -> текст строками: куски, чей центр по высоте рядом, — одна строка, слева направо."""
    rows = []
    for box, txt in items:
        txt = str(txt or "").strip()
        if not txt:
            continue
        ys = [float(p[1]) for p in box]
        xs = [float(p[0]) for p in box]
        cy, hh, x = (min(ys) + max(ys)) / 2, max(4.0, max(ys) - min(ys)), min(xs)
        for r in rows:
            if abs(r["cy"] - cy) < 0.5 * max(hh, r["h"]):
                r["parts"].append((x, txt))
                r["cy"] = (r["cy"] * (len(r["parts"]) - 1) + cy) / len(r["parts"])
                break
        else:
            rows.append({"cy": cy, "h": hh, "parts": [(x, txt)]})
    rows.sort(key=lambda r: r["cy"])
    return "\n".join(" ".join(t for _, t in sorted(r["parts"])) for r in rows)


def tidy(text):
    text = str(text or "").replace("\r\n", "\n").replace("\x0c", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ---------- движки ----------

_lock = threading.Lock()
_cache = {}


def _spec(mod):
    import importlib.util
    try:
        import pydeps
        pydeps.add_path()                       # докачанное «Поставить распознавание» лежит в своей папке
    except Exception:  # noqa: BLE001
        pass
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def _rapid_engine():
    """rapidocr 3.x: сначала с русской моделью (eslav, PP-OCRv5) — скачивается один раз; не скачалась (нет связи) —
    встроенная модель пакета, она читает только латиницу и цифры. -> (движок, читает ли по-русски)."""
    if "rapidocr" in _cache:
        return _cache["rapidocr"]
    import rapidocr
    from rapidocr import RapidOCR
    # Папку моделей называем каждый раз явно: rapidocr держит настройки в общем объекте, и раз заданная папка
    # остаётся и для следующего движка. Встроенные в пакет модели (поиск строк и поворот) берём из пакета —
    # скачивается только русская модель распознавания, в нашу папку (в /opt/dewiar писать нельзя).
    pkg = Path(rapidocr.__file__).parent / "models"
    base = {"Global.log_level": "error", "Global.model_root_dir": str(pkg)}
    eng, ru = None, False
    try:
        from rapidocr import LangRec, ModelType, OCRVersion
        models_dir().mkdir(parents=True, exist_ok=True)
        ru_params = {"Global.log_level": "error", "Global.model_root_dir": str(models_dir()),
                     "Rec.lang_type": LangRec.ESLAV, "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE}
        for key, pat in (("Det", "*det*.onnx"), ("Cls", "*cls*.onnx")):
            f = next(iter(sorted(pkg.glob(pat))), None)
            if f is not None:
                ru_params[f"{key}.model_path"] = str(f)
        eng = RapidOCR(params=ru_params)
        for m in ("_load_det_model", "_load_rec_model"):     # новые rapidocr грузят модели при первом вызове — грузим сейчас:
            if hasattr(eng, m):                               # русская не скачалась — узнать здесь, а не на тексте человека
                getattr(eng, m)()
        ru = True
    except Exception as e:  # noqa: BLE001 — нет связи, старый rapidocr без eslav
        eng = None
        log.info("rapidocr: русская модель не загрузилась (%s)", str(e)[:200])
    if eng is None:
        try:
            eng = RapidOCR(params=base)
        except Exception:  # noqa: BLE001 — старый rapidocr не знает model_root_dir
            eng = RapidOCR()
    _cache["rapidocr"] = (eng, ru)
    return eng, ru


def _rapid_run(im):
    with _lock:
        eng, ru = _rapid_engine()
        r = eng(im)
    boxes, txts = getattr(r, "boxes", None), getattr(r, "txts", None)
    if boxes is None or txts is None:
        return "", ru
    return lines_from_boxes(zip(list(boxes), list(txts))), ru


def _rapid_legacy_run(im):
    import numpy as np
    with _lock:
        eng = _cache.get("rapidocr_onnxruntime")
        if eng is None:
            from rapidocr_onnxruntime import RapidOCR
            eng = _cache["rapidocr_onnxruntime"] = RapidOCR()
        res = eng(np.asarray(im)[:, :, ::-1].copy())       # он ждёт BGR, как cv2.imread
    res = res[0] if isinstance(res, tuple) else res
    return lines_from_boxes((x[0], x[1]) for x in (res or [])), False


def tesseract_cmd():
    c = shutil.which("tesseract")
    if c:
        return c
    if WIN:
        for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            d = os.environ.get(env)
            for sub in (("Tesseract-OCR",), ("Programs", "Tesseract-OCR")):
                p = Path(d, *sub, "tesseract.exe") if d else None
                if p and p.exists():
                    return str(p)
    return None


def tesseract_langs():
    if "tess_langs" in _cache:
        return _cache["tess_langs"]
    langs = set()
    cmd = tesseract_cmd()
    if cmd:
        try:
            r = subprocess.run([cmd, "--list-langs"], capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW)
            langs = {x.strip() for x in (r.stdout + "\n" + r.stderr).splitlines()[1:] if re.fullmatch(r"[a-z_]{3,12}", x.strip())}
        except (OSError, subprocess.SubprocessError):
            pass
    _cache["tess_langs"] = langs
    return langs


def _tess_run(im):
    cmd = tesseract_cmd()
    have = tesseract_langs()
    langs = [x for x in ("rus", "eng") if x in have] or ["eng"]
    lang = "+".join(langs)
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cmd
        return pytesseract.image_to_string(im, lang=lang), "rus" in langs
    except ImportError:
        pass
    buf = io.BytesIO()
    im.save(buf, "PNG")
    r = subprocess.run([cmd, "stdin", "stdout", "-l", lang], input=buf.getvalue(), capture_output=True, timeout=120,
                       creationflags=NO_WINDOW)
    if r.returncode:
        raise OCRError((r.stderr or b"").decode("utf-8", "replace").strip()[-200:] or f"код {r.returncode}")
    return r.stdout.decode("utf-8", "replace"), "rus" in langs


class Engine:
    """may_ru() — может ли прочитать русский (дёшево; True — «не знаю, попробуй»)."""
    def __init__(self, name, have, run, title, may_ru=None):
        self.name, self.have, self.run, self.title = name, have, run, title
        self.may_ru = may_ru or (lambda: True)


ENGINES = [
    Engine("rapidocr", lambda: _spec("rapidocr"), _rapid_run, "RapidOCR",
           lambda: _cache["rapidocr"][1] if "rapidocr" in _cache else True),
    Engine("tesseract", lambda: bool(tesseract_cmd()), _tess_run, "Tesseract", lambda: "rus" in tesseract_langs()),
    Engine("rapidocr_onnxruntime", lambda: _spec("rapidocr_onnxruntime"), _rapid_legacy_run, "RapidOCR", lambda: False),
]


def local_engines():
    return [e for e in ENGINES if _safe_have(e)]


def _safe_have(e):
    try:
        return bool(e.have())
    except Exception:  # noqa: BLE001
        return False


def status():
    """-> {engines: [названия установленных], local: bool, ru: True/False/None (неизвестно до первого запуска rapidocr),
    pdf: чем рисуются страницы PDF или ""}."""
    names = [e.name for e in local_engines()]
    ru = None
    if "tesseract" in names and "rus" in tesseract_langs():
        ru = True
    elif "rapidocr" in _cache:
        ru = _cache["rapidocr"][1]
    elif names and "rapidocr" not in names:
        ru = False
    return {"engines": names, "local": bool(names), "ru": ru, "pdf": pdf_renderer()}


# ---------- распознать картинку ----------

def _vision_run(vision, im):
    out = tidy(vision(jpeg_b64(im)))
    if BLIND_RX.search(out[:300]):
        raise OCRError("модель не видит картинок")
    if re.fullmatch(rf"[«\"']?{NO_TEXT}[.»\"']?", out, re.I):
        return ""
    return out


def recognize(src, vision=None, local=True):
    """Картинка -> (текст, кто распознал: имя движка или "vision"). Пустой текст — на картинке текста нет.
    vision — функция модели со зрением (JPEG base64 -> ответ) или None; local=False — без локальных движков."""
    im = prepared(load(src))
    errors, latin = [], None
    engines = local_engines() if local else []
    for e in engines:
        if latin is not None and not e.may_ru():
            continue                               # латиница уже есть — второй движок без русского не нужен
        try:
            text, ru = e.run(im)
        except Exception as ex:  # noqa: BLE001
            log.info("OCR %s: %s", e.name, ex)
            errors.append(f"{e.title}: {str(ex)[:160]}")
            continue
        text = tidy(text)
        if ru:
            return text, e.name
        if latin is None:
            latin = (text, e.name)               # движок без русского — запасной: сначала спросим модель со зрением
    if vision is not None:
        try:
            return _vision_run(vision, im), "vision"
        except Exception as ex:  # noqa: BLE001
            log.info("OCR моделью со зрением: %s", ex)
            errors.append(f"модель: {str(ex)[:160]}")
    if latin is not None:
        return latin
    if not engines and vision is None:
        raise OCRError("Распознавания текста на этом компьютере нет. " + INSTALL_HINT)
    if not engines:
        raise OCRError("Распознавания текста на этом компьютере нет, а модель с картинкой не справилась"
                       + (f" ({errors[-1]})" if errors else "") + ". " + INSTALL_HINT)
    raise OCRError("Распознать текст не получилось: " + "; ".join(errors[:3]))


def ocr_image(src, vision=None, local=True):
    """Картинка (путь, байты, data:-адрес, PIL.Image) -> распознанный текст ("" — текста нет); OCRError — нечем."""
    return recognize(src, vision=vision, local=local)[0]


def can(vision=None):
    """Есть ли чем распознавать прямо сейчас."""
    return bool(local_engines()) or vision is not None


# ---------- PDF ----------

def pdf_texts(path, limit=500):
    """Текстовый слой PDF постранично (pypdf): [текст страницы, …]."""
    from pypdf import PdfReader
    r = PdfReader(str(path))
    out = []
    for pg in r.pages[:limit]:
        try:
            out.append(pg.extract_text() or "")
        except Exception:  # noqa: BLE001 — битая страница: пусть будет «скан»
            out.append("")
    return out


def is_scan(text):
    return len(re.sub(r"[\W_]", "", str(text or ""))) < MIN_PAGE_TEXT


def pdf_renderer():
    if _spec("pypdfium2"):
        return "pypdfium2"
    if _spec("fitz"):
        return "pymupdf"
    if shutil.which("pdftoppm"):
        return "pdftoppm"
    return "pypdf"


def page_image(path, i, dpi=PDF_DPI):
    """Страница i (с нуля) -> PIL.Image или None. Рисуем, чем есть; нечем — берём самую большую картинку, вложенную в
    страницу (у скана это и есть страница)."""
    from PIL import Image
    if _spec("pypdfium2"):
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(str(path))
            try:
                return doc[i].render(scale=dpi / 72).to_pil().convert("RGB")
            finally:
                doc.close()
        except Exception as e:  # noqa: BLE001
            log.info("pypdfium2: %s", e)
    if _spec("fitz"):
        try:
            import fitz
            with fitz.open(str(path)) as doc:
                pix = doc[i].get_pixmap(dpi=dpi)
                return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        except Exception as e:  # noqa: BLE001
            log.info("pymupdf: %s", e)
    exe = shutil.which("pdftoppm")
    if exe:
        tmp = tempfile.mkdtemp()
        try:
            out = Path(tmp) / "p"
            subprocess.run([exe, "-f", str(i + 1), "-l", str(i + 1), "-r", str(dpi), "-png", "-singlefile", str(path), str(out)],
                           capture_output=True, timeout=60, creationflags=NO_WINDOW)
            f = out.with_suffix(".png")
            if f.exists():
                return load(f.read_bytes())
        except (OSError, subprocess.SubprocessError) as e:
            log.info("pdftoppm: %s", e)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    try:
        from pypdf import PdfReader
        best = None
        for img in PdfReader(str(path)).pages[i].images:
            try:
                im = img.image
            except Exception:  # noqa: BLE001 — кодек, которого Pillow не знает (JBIG2)
                continue
            if im is not None and (best is None or im.width * im.height > best.width * best.height):
                best = im
        return load(best) if best is not None else None
    except Exception as e:  # noqa: BLE001
        log.info("pypdf (картинки страницы): %s", e)
        return None


def parse_pages(spec, n):
    """«1-3, 5» -> [0, 1, 2, 4] (в пределах n страниц); пусто — все."""
    if not str(spec or "").strip():
        return list(range(n))
    out = []
    for part in re.split(r"[,;\s]+", str(spec).strip()):
        m = re.fullmatch(r"(\d+)(?:\s*[-–—]\s*(\d+))?", part)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        out += [k - 1 for k in range(min(a, b), max(a, b) + 1) if 1 <= k <= n]
    return sorted(set(out)) or list(range(n))


def ocr_pdf_ex(path, pages=None, vision=None, local=True, limit=None):
    """PDF -> {text, ocr_pages: [номера с 1], engine, skipped (сканы сверх предела), total, error}. Страницы со своим
    текстом — как есть, без текстового слоя — рисуются и распознаются (не больше limit). error — почему сканы не
    прочитались (тогда в text — только то, что было текстом)."""
    texts = pdf_texts(path)
    want = pages if isinstance(pages, list) else parse_pages(pages, len(texts))
    if limit is None:
        limit = PDF_PAGES if local and local_engines() else VISION_PAGES
    multi = len(want) > 1
    parts, done, skipped, engine, error = [], [], 0, "", ""
    for i in want:
        t = texts[i] if i < len(texts) else ""
        if not is_scan(t):
            parts.append(t.strip())
            continue
        if error or len(done) >= limit:
            skipped += 1
            continue
        im = page_image(path, i)
        if im is None:
            skipped += 1
            continue
        try:
            txt, engine = recognize(im, vision=vision, local=local)
        except OCRError as e:
            error = str(e)
            skipped += 1
            continue
        done.append(i + 1)
        if txt:
            parts.append((f"[стр. {i + 1}]\n" if multi else "") + txt)
    return {"text": tidy("\n\n".join(p for p in parts if p)), "ocr_pages": done, "engine": engine, "skipped": skipped,
            "total": len(texts), "error": error}


def ocr_pdf(path, pages=None, vision=None, local=True):
    """PDF -> текст: свой текстовый слой и распознанные сканы. Ни одна страница-скан не распозналась и текста нет —
    OCRError."""
    r = ocr_pdf_ex(path, pages=pages, vision=vision, local=local)
    if r["error"] and not r["text"]:
        raise OCRError(r["error"])
    return r["text"]


def mostly_scan(texts):
    """Документ — скан: страниц без текста хотя бы половина или текста почти нет. Отдельная пустая страница или схема
    в обычном PDF — не повод распознавать (в «Документах» это часы работы процессора на большой папке)."""
    if not texts:
        return False
    return sum(map(is_scan, texts)) * 2 >= len(texts) or len(re.sub(r"\s", "", "".join(texts))) < 200


def pdf_needs_ocr(path, limit=500, mostly=True):
    """Нужно ли распознавать PDF: mostly — документ в основном из сканов (mostly_scan), иначе — есть хоть одна страница
    без текста."""
    try:
        texts = pdf_texts(path, limit)
        return mostly_scan(texts) if mostly else any(is_scan(t) for t in texts)
    except Exception:  # noqa: BLE001
        return False


# ---------- поставить ----------

def install(on_status=None):
    """«Поставить распознавание текста»: rapidocr с зависимостями — в свою папку (pydeps), затем русская модель.
    -> (получилось, что сказать человеку)."""
    import pydeps
    pydeps._tried.pop("rapidocr", None)          # «Поставить» нажали ещё раз — пробуем снова, а не прошлую причину
    ok, why = pydeps.ensure("rapidocr", on_status=on_status)
    if not ok:
        return False, why
    _cache.pop("rapidocr", None)
    if on_status:
        on_status("Скачиваю русскую модель распознавания (около 8 МБ)…")
    try:
        with _lock:
            _, ru = _rapid_engine()
    except Exception as e:  # noqa: BLE001
        return False, f"распознавание поставилось, но не запускается: {str(e)[:200]}"
    if ru:
        return True, "Распознавание текста готово: русский и английский, без интернета."
    return True, ("Распознавание текста поставлено, но русская модель не скачалась (нет связи с modelscope.cn) — пока "
                  "читает только латиницу. Попробуйте «Поставить» ещё раз позже.")
