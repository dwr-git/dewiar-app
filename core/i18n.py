"""Языки программы (0.88; владелец 11.11: «нужно, чтобы в отдельных файлах ru.json, en.json всё содержалось — удобно на
будущее; если у пользователя нет русского в системе — сразу английский, в настройках переключение»).

Словари — data/i18n/<язык>.json (новый язык — новый файл, код не трогаем: langs(), окна и переключатель находят его сами): {"ключ": "текст"} или для чисел {"ключ": {"one": …, "few": …, "many": …, "other": …}}
(формы — по правилам CLDR языка; «{n}» и «{имя}» — подстановки). Один словарь на студию, виджет, телефон и сайт: окна
берут его из ui/assets/i18n.data.js (собирает tools/i18n_build.py, проверка — tests/i18n_test.py).

Язык — settings ui.lang: "auto" (по системе: русский — если система на русском, украинском или белорусском или на
Windows есть такая раскладка, иначе английский), "ru", "en"; позже "ar". У тех, кто пользовался до 0.88, — "ru"
(settings.py), «как в системе» — только у новых установок. Нет строки в выбранном языке — русская (исходная), нет и её — сам ключ.
Комментарии для программистов и журнал остаются русскими (владелец 11.11)."""

import json
import locale
import logging
import os
import re
import sys
from pathlib import Path

log = logging.getLogger("dewiar.i18n")
ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "i18n"
SOURCE = "ru"
FALLBACK = "en"                           # нет строки в немецком, иврите… — английская (её поймут скорее), затем русская
RTL = ("ar", "he", "fa", "ur")            # письмо справа налево — вёрстка зеркалится сама (dir="rtl")


def langs():
    """Языки = словари в data/i18n (владелец 11.11, 21:10: «легко добавлять любой язык — иврит, немецкий, французский,
    китайский»): новый язык — новый файл <код>.json (и строка "lang.name" — имя языка на нём самом), без правки кода."""
    try:
        found = sorted(p.stem for p in DIR.glob("*.json") if re.fullmatch(r"[a-z]{2,3}(?:-[A-Z][a-z]{3})?", p.stem))
    except OSError:
        found = []
    return tuple([SOURCE] + [x for x in found if x != SOURCE]) if found else (SOURCE,)


LANGS = langs()
RU_LIKE = ("ru", "uk", "be", "kk")        # системы, где человек скорее всего читает по-русски
_cache = {}


def catalog(lang):
    """data/i18n/<lang>.json -> словарь (кешируется; битый или нет файла — пустой)."""
    if lang not in _cache:
        try:
            _cache[lang] = json.loads((DIR / f"{lang}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("Словарь %s не прочитан: %s", lang, e)
            _cache[lang] = {}
    return _cache[lang]


def system_lang():
    """Язык системы -> "ru" | "en" (Windows — язык интерфейса, Linux и Mac — LANG/LC_*). DEWIAR_SYS_LANG — задать явно
    (проверки: LANG=ru_RU без установленной локали ломает Chromium на русских именах файлов)."""
    forced = os.environ.get("DEWIAR_SYS_LANG", "").strip().lower()
    if forced:
        return "ru" if forced[:2] in RU_LIKE else "en"
    code = ""
    if sys.platform == "win32":
        try:
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            code = locale.windows_locale.get(lcid, "")
            if code[:2] not in RU_LIKE and _win_ru_keyboard():
                code = "ru_RU"                       # английская Windows, но есть русская раскладка — человек читает по-русски
        except Exception:  # noqa: BLE001
            code = ""
    if not code:
        for k in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
            v = os.environ.get(k, "")
            if v and v not in ("C", "POSIX", "C.UTF-8"):
                code = v
                break
    if not code:
        try:
            code = locale.getlocale()[0] or ""
        except (ValueError, TypeError):
            code = ""
    code = code.split(":")[0].replace("-", "_").lower()
    if not code:
        return SOURCE
    if code[:2] in RU_LIKE:
        return "ru"
    have = langs()
    if code[:2] in have:                          # есть словарь языка системы (немецкий, иврит…) — он
        return code[:2]
    return FALLBACK if FALLBACK in have else SOURCE


def _win_ru_keyboard():
    """Windows: установлена ли русская (украинская, белорусская, казахская) раскладка клавиатуры."""
    import ctypes
    n = ctypes.windll.user32.GetKeyboardLayoutList(0, None)
    arr = (ctypes.c_void_p * max(1, n))()
    n = ctypes.windll.user32.GetKeyboardLayoutList(n, arr)
    langs = {(int(h or 0) & 0xFFFF) for h in arr[:n]}
    return bool(langs & {0x0419, 0x0422, 0x0423, 0x043F})   # ru-RU, uk-UA, be-BY, kk-KZ


def resolve(value):
    """ui.lang из настроек -> язык, который показывать: "auto" и неизвестное — по системе."""
    v = str(value or "auto")
    return v if v in langs() else system_lang()


def plural_form(lang, n):
    """Форма числа по CLDR (основные языки; окна берут любые — Intl.PluralRules): ru/uk/be и pl — one/few/many/other,
    en/de/es/it… — one/other, fr/pt — 0 и 1 как one, he — one/two/other, zh/ja/ko — other, ar — все шесть форм."""
    try:
        n = abs(float(n))
    except (TypeError, ValueError):
        return "other"
    i = int(n)
    whole = n == i
    if lang == "ru":
        if not whole:
            return "other"
        if i % 10 == 1 and i % 100 != 11:
            return "one"
        if 2 <= i % 10 <= 4 and not 12 <= i % 100 <= 14:
            return "few"
        return "many"
    if lang in ("uk", "be"):
        return plural_form("ru", n)
    if lang == "pl":
        if not whole:
            return "other"
        if i == 1:
            return "one"
        if 2 <= i % 10 <= 4 and not 12 <= i % 100 <= 14:
            return "few"
        return "many"
    if lang == "he":
        if whole and i == 1:
            return "one"
        if whole and i == 2:
            return "two"
        return "other"
    if lang in ("fr", "pt"):
        return "one" if int(n) in (0, 1) else "other"
    if lang in ("zh", "ja", "ko", "vi", "th", "id", "ms", "tr", "fa"):
        return "other"
    if lang == "ar":
        if not whole:
            return "other"
        if i == 0:
            return "zero"
        if i == 1:
            return "one"
        if i == 2:
            return "two"
        if 3 <= i % 100 <= 10:
            return "few"
        if 11 <= i % 100 <= 99:
            return "many"
        return "other"
    return "one" if whole and i == 1 else "other"


_PH = re.compile(r"\{(\w+)\}")


def t(key, lang=SOURCE, **params):
    """Строка по ключу на языке lang; числа — по форме params["n"]; {имя} — подстановки. Нет перевода — английская, затем
    русская, затем сам ключ."""
    v = None
    for l in dict.fromkeys((lang, FALLBACK, SOURCE)):          # язык → английский → русский
        v = catalog(l).get(key)
        if v is not None:
            lang = l
            break
    if v is None:
        return key
    if isinstance(v, dict):
        v = v.get(plural_form(lang, params.get("n", 0))) or v.get("other") or next(iter(v.values()), key)
    return _PH.sub(lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0), str(v))


# ---------- перевод по тексту (0.96): тот же словарь, что у окон (data/i18n/text/<язык>.json, ui/assets/i18n.js) ----------
# Ключ — сама русская строка; «{1}» — подстановка. Быстрые ответы без модели («Ставлю будильник на 7:00.»), напоминания
# и сообщения ядра на языке программы: engine._g() пропускает их через tx(). Правила — как у txOf в i18n.js (кроме дат).
TEXT_DIR = ROOT / "data" / "i18n" / "text"
_CYR = re.compile(r"[А-Яа-яЁё]")
_TX = {}


def _tx_load(lang):
    if lang in _TX:
        return _TX[lang]
    exact, pats = {}, {}
    try:
        d = json.loads((TEXT_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    for k, v in d.items():
        if not v or not isinstance(v, str):
            continue
        k = re.sub(r"\s+", " ", k).strip()
        if not re.search(r"\{\d\}", k):
            exact[k] = v
            continue
        parts = re.split(r"(\{\d\})", k)
        rx = re.compile("^" + "".join("(.*?)" if re.fullmatch(r"\{\d\}", p) else re.escape(p) for p in parts) + "$", re.S)
        order = [x[1] for x in re.findall(r"\{\d\}", k)]
        own = len(re.sub(r"[^A-Za-zА-Яа-яЁё]", "", re.sub(r"\{\d\}", "", k)))
        quoted = {x[2] for x in re.findall(r"[«“\"„]\{\d\}[»”\"“]", k)}
        glued = {re.search(r"\d", x).group(0) for x in re.findall(r"[A-Za-zА-Яа-яЁё]\{\d\}|\{\d\}[A-Za-zА-Яа-яЁё]", k)}
        weak = {n for n in order if n in glued or (own < 10 and n not in quoted)}
        head = k.split("{")[0]
        pats.setdefault(head[:3] if len(head) >= 3 else "", []).append((rx, order, v, weak, len(re.sub(r"\{\d\}", "", k))))
    for lst in pats.values():
        lst.sort(key=lambda x: -x[4])
    _TX[lang] = (exact, pats)
    return _TX[lang]


def _tx_of(s, lang, inner=False, depth=0):
    k = re.sub(r"\s+", " ", s).strip()
    if not k or not _CYR.search(k) or depth > 4:
        return None
    exact, pats = _tx_load(lang)
    if k in exact:
        return exact[k]
    for b in (k[:3], ""):
        for rx, order, tr, weak, _n in pats.get(b, ()):
            m = rx.match(k)
            if not m:
                continue
            got, good = {}, True
            for i, n in enumerate(order):
                c = m.group(i + 1)
                if _CYR.search(c):
                    t_ = _tx_of(c, lang, False, depth + 1)
                    if t_ is not None:
                        c = t_
                    elif n in weak:
                        good = False
                        break
                got[n] = c
            if good:
                return re.sub(r"\{(\d)\}", lambda x: got.get(x.group(1), x.group(0)), tr)
    if inner:
        return None
    sub = lambda x: _tx_of(x, lang, True, depth + 1)  # noqa: E731
    m = re.match(r"^[«“\"„](.+)[»”\"“]([.,:;!?…]*)$", k)
    if m and sub(m.group(1)) is not None:
        return "“" + sub(m.group(1)) + "”" + m.group(2)
    m = re.match(r"^([→—–·•]\s*)(.+)$", k)
    if m and sub(m.group(2)) is not None:
        return m.group(1) + sub(m.group(2))
    m = re.match(r"^(.+?)\s*([.:;,!?…]+)$", k)
    if m and sub(m.group(1)) is not None:
        return re.sub(r"[.:;,!?…]+$", "", sub(m.group(1))) + m.group(2)
    m = re.match(r"^([\d][\d\s.,:]*)\s+([А-Яа-яЁё].*)$", k)
    if m and sub(m.group(2)) is not None:
        return m.group(1) + " " + sub(m.group(2))
    for sep in (" — ", " · "):
        ps = k.split(sep)
        if 1 < len(ps) < 6:
            t_ = [(_tx_of(p, lang, False, depth + 1) if _CYR.search(p) else p) for p in ps]
            if all(x is not None for x in t_):
                return sep.join(t_)
    ss = re.split(r"(?<=[.!?…])\s+(?=[А-ЯЁA-Z«“\"(])", k)
    if 1 < len(ss) < 9 and len(k) < 900:
        out, i = [], 0
        while i < len(ss):
            hit, j = None, len(ss)
            while j > i:
                if j - i != len(ss):
                    hit = _tx_of(" ".join(ss[i:j]), lang, False, depth + 1)
                    if hit is not None:
                        break
                j -= 1
            if hit is None:
                return None
            out.append(hit)
            i = j
        return " ".join(out)
    return None


def tx(text, lang):
    """Русская строка → на языке lang по словарю перевода по тексту; нет перевода (или язык русский) — как есть.
    Текст без кириллицы (ответ модели по-английски) не трогается."""
    if not text or lang in (SOURCE, None, "") or not _CYR.search(str(text)):
        return text
    try:
        v = _tx_of(str(text), lang)
        if v is None and lang != FALLBACK:
            v = _tx_of(str(text), FALLBACK)
    except Exception:  # noqa: BLE001
        log.debug("перевод по тексту", exc_info=True)
        v = None
    return text if v is None else v
