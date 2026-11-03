"""Плагин «Рекрутер» — MCP-сервер (stdio). Суть модуля владельца AI Recruiter (PHP, 30.10) на Python без своих библиотек:

  • резюме из файла или папки (PDF, Word, ODT, текст) — текст через knowledge.extract ядра Dewiar; одно резюме дважды
    не заводится (по содержимому);
  • без модели достаются ФИО, телефон, почта, Telegram, город, возраст, стаж, желаемая должность и зарплата (форматы
    rabota.by / hh и свободные) и «сигналы честности»: стаж больше возможного по возрасту, senior при малом стаже;
  • вакансии; предварительный отбор кандидатов под вакансию по словам (основы слов, технологии весят больше);
  • оценку по пяти критериям ставит Лира (она читает резюме), а итог считается здесь по весам — воспроизводимо и
    одинаково для всех кандидатов, как в модуле владельца (навыки 40, опыт 30, формат 13, образование 10, языки 7);
  • воронка: новый → интересен → собеседование → оффер → принят / отказ, заметки с датой.

Все данные — в DEWIAR_PLUGIN_DATA на этом компьютере. Настройки — DEWIAR_PLUGIN_SETTINGS."""

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

DATA = Path(os.environ.get("DEWIAR_PLUGIN_DATA") or Path.home() / ".dewiar-recruiter")
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "recruiter.json"
EXTS = {".pdf", ".docx", ".odt", ".txt", ".md", ".rtf", ".html", ".htm"}
STAGES = ["новый", "интересен", "собеседование", "оффер", "принят", "отказ"]
WEIGHTS = {"hard_skills": 0.40, "experience": 0.30, "format_match": 0.13, "education": 0.10, "languages": 0.07}
CRIT = {"hard_skills": "навыки", "experience": "опыт", "format_match": "формат и условия", "education": "образование", "languages": "языки"}


def settings():
    out = {}
    try:
        for f in json.loads(Path(__file__).with_name("plugin.json").read_text(encoding="utf-8")).get("settings") or []:
            if "default" in f:
                out[f["key"]] = f["default"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        s = json.loads(os.environ.get("DEWIAR_PLUGIN_SETTINGS") or "{}")
    except ValueError:
        s = {}
    out.update(s if isinstance(s, dict) else {})
    return out


def load():
    try:
        d = json.loads(DB.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d.setdefault("cands", {})
    d.setdefault("vacs", {})
    return d


def save(d):
    tmp = DB.with_suffix(".part")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DB)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def sid(prefix, text):
    return prefix + hashlib.md5(text.encode("utf-8", "replace")).hexdigest()[:8]


# ---------------- текст резюме ----------------

def extract(p: Path) -> str:
    ext = p.suffix.lower()
    if ext == ".rtf":
        t = p.read_text(encoding="cp1251", errors="replace")
        t = re.sub(r"\\'([0-9a-f]{2})", lambda m: bytes([int(m[1], 16)]).decode("cp1251", "replace"), t)
        t = re.sub(r"\\par[d]?\b", "\n", t)
        return re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", t)
    try:
        import knowledge
        return knowledge.extract(p)
    except ImportError:
        return p.read_text(encoding="utf-8", errors="replace") if ext in (".txt", ".md") else ""


def norm_text(t):
    t = t.replace("\xa0", " ").replace("\r", "")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


NUMW = {"год": 12, "года": 12, "лет": 12, "месяц": 1, "месяца": 1, "месяцев": 1, "year": 12, "years": 12, "month": 1, "months": 1}


def months_in(s):
    return sum(int(n) * NUMW[u.lower()] for n, u in re.findall(r"(\d{1,2})\s*(год|года|лет|месяц|месяца|месяцев|years?|months?)\b", s, re.I))


def facts(text):
    """Что достаётся из резюме без модели (как salvageCVFromText в модуле владельца, плюс формат rabota.by / hh)."""
    lines = [x.strip() for x in text.split("\n") if x.strip()]
    name = ""
    for ln in lines[:8]:
        if re.fullmatch(r"[А-ЯЁA-Z][\w’'.\-]+(?:\s+[А-ЯЁA-Z][\w’'.\-]+){1,3}", ln) and not re.search(r"\d|@|резюме|resume|cv\b", ln, re.I):
            name = ln
            break
    out = {"name": name}
    m = re.search(r"(?:\+?375|\+?7|8)[\s(-]*\d{2,3}[\s)-]*\d{3}[\s-]?\d{2}[\s-]?\d{2}|\+\d[\d\s()-]{8,}\d", text)
    out["phone"] = re.sub(r"\s+", " ", m[0]).strip() if m else ""
    m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", text, re.I)
    out["email"] = m[0] if m else ""
    m = re.search(r"t\.me/([A-Za-z0-9_]{4,})", text) or re.search(r"(?:telegram|tg|телеграм)\s*[:\-]?\s*@?([A-Za-z0-9_]{4,})", text, re.I)
    out["telegram"] = "@" + m[1] if m else ""
    m = re.search(r"(?:Проживает|Город|Местонахождение|Location)\s*[:\-]?\s*([А-ЯЁA-Z][\w\- ]{2,30})", text)
    out["city"] = m[1].strip() if m else ""
    m = re.search(r"(?:Мужчина|Женщина)\s*,\s*(\d{2})\s*(?:год|года|лет)", text) or re.search(r"(?:Возраст|Age)\s*[:\-]?\s*(\d{2})", text, re.I) \
        or re.search(r"\b(\d{2})\s*(?:год|года|лет),?\s*(?:родил|дата рождения)", text)
    out["age"] = int(m[1]) if m and 16 <= int(m[1]) <= 80 else None
    m = re.search(r"Опыт работы\s*[:\-—–]?\s*((?:\d{1,2}\s*(?:года|год|лет|месяцев|месяца|месяц)\s*){1,2})", text, re.I) \
        or re.search(r"(?:Общий стаж|Стаж)\s*[:\-—–]?\s*((?:\d{1,2}\s*(?:года|год|лет|месяцев|месяца|месяц)\s*){1,2})", text, re.I) \
        or re.search(r"(?:Work experience|Experience)\s*[:\-—–]?\s*((?:\d{1,2}\s*(?:years?|months?)\s*){1,2})", text, re.I)
    out["exp_months"] = months_in(m[1]) if m else None
    m = re.search(r"(?:Желаемая должность(?: и зарплата)?|Должность|Позиция|Position)\s*[:\-]?\s*\n?\s*([^\n]{3,90})", text, re.I)
    out["position"] = m[1].strip() if m else ""
    m = re.search(r"(\d[\d ]{2,8}\s*(?:BYN|руб\.?|бел\.?\s*руб\.?|USD|\$|EUR|€)(?: на руки| net| gross)?)", text) or \
        re.search(r"(?:Зарплата|Желаемая зарплата|Ожидания)\s*[:\-]\s*([^\n]*\d[^\n]{0,30})", text, re.I)
    out["salary"] = m[1].strip() if m else ""
    langs = re.findall(r"(Английский|Немецкий|Польский|Французский|Китайский|Испанский|English|German|Polish)\s*[—\-–(:]\s*"
                       r"(A1|A2|B1|B2|C1|C2|[Нн]ачальный|[Бб]азовый|[Сс]редний|[Пп]родвинутый|[Сс]вободн\w*|[Рр]одной|native|fluent)", text)
    out["languages"] = [f"{a} — {b}" for a, b in langs][:6]
    return out


SENIOR = re.compile(r"\b(senior|lead|principal|head of|tech lead|тимлид|руководитель отдела|архитектор)\b", re.I)


def flags(f, text):
    """Сигналы, которые стоит уточнить на собеседовании (не приговор)."""
    out = []
    exp, age = f.get("exp_months"), f.get("age")
    if exp and age and exp / 12 > max(0, age - 16) + 1:
        out.append(f"стаж {round(exp / 12, 1)} лет при возрасте {age} — не сходится")
    if exp is not None and exp < 48 and SENIOR.search(text):
        out.append("senior / lead / руководитель при стаже меньше 4 лет")
    if not (f.get("phone") or f.get("email") or f.get("telegram")):
        out.append("нет контактов в резюме")
    jobs = re.findall(r"(?:^|\n)\s*(?:\d{1,2}\s*(?:месяц|месяца|месяцев))\s*(?:\n|$)", text)
    if len(jobs) >= 3:
        out.append(f"{len(jobs)} мест работы меньше года — частая смена работы")
    return out


# ---------------- слова: отбор под вакансию ----------------

STOP = set("и в во на по для с со к ко о об от до из за или а не же что как это при без над под через лет год года опыт работы работа "
           "умение знание знания навыки навык требования требуется будет будем нужно нужен нужна желательно плюсом обязанности условия "
           "компания команда кандидат хороший хорошее хорошие уверенный уверенное высокий высокая".split())
ENDS = sorted("ированного ированной ирование ирования ениями ениях ностью ности ость остей ового ыми ими ого его ому ему ая яя ое ее ые "
              "ие ый ий ой ей ую юю ых их ам ям ах ях ами ями ов ев ом ем ию ия ии ье ья ью ы и а я о е у ю ь й".split(), key=len, reverse=True)


def stem(w):
    w = w.lower().replace("ё", "е")
    if len(w) <= 4 or not re.search(r"[а-я]", w):
        return w
    for e in ENDS:
        if len(w) - len(e) >= 4 and w.endswith(e):
            return w[:-len(e)]
    return w


def terms(text):
    """Значимые слова вакансии: технологии (латиница, C++, 1С) и русские основы; без общих слов."""
    out = {}
    for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]|[A-Za-z]|1[СC]|[А-Яа-яЁё]{4,}", text):
        lw = w.lower()
        if lw in STOP or (re.fullmatch(r"[a-z]", lw) and lw not in ("c", "r")):
            continue
        tech = bool(re.match(r"[a-z0-9]", lw))
        k = lw if tech else stem(lw)
        out.setdefault(k, {"w": w, "tech": tech})
    return out


def match(vac_text, cand_text):
    need = terms(vac_text)
    have = set(stem(w) for w in re.findall(r"[А-Яа-яЁё]{4,}", cand_text)) | set(
        w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]|1[СC]", cand_text))
    tot = hit = 0
    got, miss = [], []
    for k, v in need.items():
        wt = 2 if v["tech"] else 1
        tot += wt
        if k in have:
            hit += wt
            got.append(v["w"])
        else:
            miss.append(v["w"])
    return (round(100 * hit / tot) if tot else 0), got, miss


# ---------------- действия ----------------

def brief(c):
    sc = max((x["total"] for x in (c.get("scores") or {}).values()), default=None)
    out = {"id": c["id"], "name": c.get("name") or c.get("file"), "position": c.get("position") or "", "stage": c.get("stage")}
    if c.get("exp_months"):
        out["experience"] = f"{c['exp_months'] // 12} г. {c['exp_months'] % 12} мес."
    if sc is not None:
        out["best_score"] = sc
    if c.get("flags"):
        out["flags"] = len(c["flags"])
    return out


def add(path):
    raw = str(path or settings().get("folder") or "").strip()
    if not raw:
        return {"error": "Какой файл или папку разобрать? Можно указать папку с резюме в настройках плагина «Рекрутер»."}
    p = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not p.exists():
        return {"error": f"Не нашла «{raw}». Проверьте путь."}
    files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in EXTS and not x.name.startswith(("~$", ".")))
    return add_files(files)


def add_files(files):
    """Разобрать файлы резюме -> {added, already_known, problems} (повтор по содержимому не заводится)."""
    d, added, skipped, bad = load(), [], 0, []
    for f in files[:300]:
        try:
            text = norm_text(extract(f))
        except Exception as e:  # noqa: BLE001
            bad.append(f"{f.name}: {str(e)[:80]}")
            continue
        if len(text) < 80:
            bad.append(f"{f.name}: нет текста (скан? — попросите прислать в PDF с текстом)")
            continue
        cid = sid("c", re.sub(r"\s+", " ", text.lower()))
        if cid in d["cands"]:
            skipped += 1
            continue
        fx = facts(text)
        c = dict(fx, id=cid, file=f.name, path=str(f), text=text[:60000], added=now(), stage="новый", notes=[], scores={}, flags=flags(fx, text))
        d["cands"][cid] = c
        added.append(c)
    save(d)
    res = {"added": [brief(c) | {k: c[k] for k in ("phone", "email", "telegram", "city", "age", "salary", "file") if c.get(k)} for c in added[:30]],
           "already_known": skipped, "problems": bad[:10]}
    if len(added) == 1:
        res["text"] = added[0]["text"][:6000]
        res["flags"] = added[0]["flags"]
    return res


# ---------------- своя страница плагина: загрузка, правка, подбор и сравнение без модели ----------------

MAX_FILE = 15 * 1024 * 1024


def inbox():
    """Куда класть резюме, закинутые на странице: папка из настроек (если есть), иначе «Резюме» в папке данных плагина."""
    raw = str(settings().get("folder") or "").strip()
    p = Path(os.path.expandvars(os.path.expanduser(raw))) if raw else None
    if p and p.is_dir():
        return p
    p = DATA / "Резюме"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _free_name(folder, name, data):
    """Имя файла в папке резюме: такой же файл уже лежит — он и есть; иначе «имя (2).pdf»."""
    stem, ext = Path(name).stem[:80] or "резюме", Path(name).suffix.lower()
    f, i = folder / f"{stem}{ext}", 2
    while f.exists():
        try:
            if f.read_bytes() == data:
                return f, False
        except OSError:
            pass
        f, i = folder / f"{stem} ({i}){ext}", i + 1
    return f, True


def import_files(files):
    """Резюме, закинутые на странице плагина (перетащили или выбрали): [{name, b64}] -> копии в папку резюме и разбор.
    ZIP распаковывается (только файлы резюме, без путей). Имя — только последняя часть, без «..»."""
    import base64
    import io
    import zipfile
    folder, saved, bad = inbox(), [], []
    def put(name, data):
        name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", Path(str(name)).name).strip(" .")
        if not name or Path(name).suffix.lower() not in EXTS:
            bad.append(f"{name or 'файл'}: такой формат не читаю (нужен PDF, Word, ODT, RTF, текст или HTML)")
            return
        if len(data) > MAX_FILE:
            bad.append(f"{name}: больше 15 МБ")
            return
        f, new = _free_name(folder, name, data)
        if new:
            f.write_bytes(data)
        saved.append(f)
    for x in (files or [])[:100]:
        if not isinstance(x, dict):
            continue
        try:
            data = base64.b64decode(str(x.get("b64") or ""), validate=False)
        except (ValueError, TypeError):
            bad.append(f"{x.get('name')}: файл не прочитался")
            continue
        name = str(x.get("name") or "")
        if name.lower().endswith(".zip"):
            try:
                z = zipfile.ZipFile(io.BytesIO(data))
                for n in z.namelist()[:300]:
                    if not n.endswith("/") and not Path(n).name.startswith(("~$", ".")) and Path(n).suffix.lower() in EXTS:
                        put(Path(n).name, z.read(n))
            except zipfile.BadZipFile:
                bad.append(f"{name}: архив повреждён")
            continue
        put(name, data)
    res = add_files(saved) if saved else {"added": [], "already_known": 0, "problems": []}
    res["problems"] = (bad + res.get("problems", []))[:20]
    res["folder"] = str(folder)
    return res


EDIT = {"name": 120, "position": 120, "phone": 60, "email": 120, "telegram": 60, "city": 60, "salary": 60}


def edit(cid, fields=None, reparse=False):
    """Правка карточки руками (как «Редактировать» в модуле владельца) или «Переразобрать» — заново из текста резюме.
    Сигналы «уточнить» пересчитываются."""
    d = load()
    c = d["cands"].get(str(cid))
    if not c:
        return {"error": "нет такого кандидата"}
    if reparse:
        c.update(facts(c["text"]))
    for k, v in (fields or {}).items():
        if k in EDIT:
            c[k] = " ".join(str(v or "").split())[:EDIT[k]]
        elif k == "age":
            try:
                c["age"] = int(v) if str(v).strip() else None
            except ValueError:
                return {"error": "возраст — числом"}
        elif k == "exp_years":
            try:
                c["exp_months"] = round(float(str(v).replace(",", ".")) * 12) if str(v).strip() else None
            except ValueError:
                return {"error": "стаж — числом лет, например 3,5"}
        elif k == "languages":
            c["languages"] = [x.strip()[:60] for x in re.split(r"[;,\n]+", str(v or "")) if x.strip()][:8]
    c["flags"] = flags(c, c["text"])
    c.setdefault("notes", []).append({"at": now(), "text": "переразобрано из текста" if reparse else "карточка поправлена"})
    save(d)
    return get(cid)


NUMWORD = {"одного": 1, "один": 1, "года": 1, "двух": 2, "два": 2, "трёх": 3, "трех": 3, "три": 3, "четырёх": 4, "четырех": 4, "четыре": 4,
           "пяти": 5, "пять": 5, "шести": 6, "шесть": 6, "семи": 7, "семь": 7, "восьми": 8, "десяти": 10, "десять": 10}
LEVELS = ["a1", "a2", "b1", "b2", "c1", "c2"]
LEVEL_WORDS = {"upper": "b2", "начальн": "a2", "базов": "a2", "средн": "b1", "intermediate": "b1", "продвинут": "c1", "advanced": "c1",
               "свободн": "c1", "fluent": "c1", "родн": "c2", "native": "c2"}
EDU = re.compile(r"высшее|университет|институт|академи|бгу|бгэу|бнту|бгуир|мгу|university|bachelor|master|магистр|бакалавр|специалитет", re.I)
LANG_NAMES = {"англ": "english", "english": "english", "нем": "german", "german": "german", "польск": "polish", "polish": "polish",
              "франц": "french", "french": "french", "китай": "chinese", "испан": "spanish"}


def need_years(text):
    t = text.lower().replace("ё", "е")
    m = re.search(r"(?:опыт|стаж|experience)[^.\n]{0,40}?(?:от|не менее|более|больше|from|at least)?\s*(\d{1,2})\s*\+?\s*(?:лет|года|год|years?)", t) \
        or re.search(r"\bот\s+(\d{1,2})\s*(?:лет|года|год)", t) or re.search(r"(\d{1,2})\+?\s*years", t)
    if m:
        return int(m[1])
    m = re.search(r"(?:от|не менее|более)\s+(" + "|".join(NUMWORD) + r")\s+(?:лет|года|год)", t)
    return NUMWORD[m[1]] if m else None


def _langs(text):
    """{язык: уровень a1..c2} из текста (резюме или вакансии)."""
    out = {}
    low = text.lower()
    for m in re.finditer(r"(англ\w*|english|нем\w*|german|польск\w*|polish|франц\w*|french|китай\w*|испан\w*)[^\n.;]{0,25}", low):
        name = next((v for k, v in LANG_NAMES.items() if m[1].startswith(k)), None)
        if not name:
            continue
        frag = m[0]
        lv = re.search(r"\b([abc][12])\b", frag)
        level = lv[1] if lv else next((v for k, v in LEVEL_WORDS.items() if k in frag), "b1")
        out[name] = max(out.get(name, "a1"), level)
    return out


def assess(c, v, d=None):
    """Оценка кандидата под вакансию БЕЗ модели (воспроизводимо): пять критериев 0–100, итог по WEIGHTS, честность анкеты,
    что есть из требований и чего нет. Модель потом может оценить точнее (recruit_score) — её оценка показывается рядом."""
    vt = (v.get("title", "") + "\n" + v.get("text", ""))
    pct, got, miss = match(vt, c["text"])
    bd = {"hard_skills": pct}
    need, yrs = need_years(vt), (c.get("exp_months") or 0) / 12
    if not c.get("exp_months"):
        bd["experience"] = 35
    elif need:
        bd["experience"] = round(min(100, 100 * yrs / need)) if yrs < need else min(100, 85 + round((yrs - need) * 3))
    else:
        bd["experience"] = min(100, 40 + round(yrs * 8))
    low = vt.lower()
    city = (c.get("city") or "").lower()
    if re.search(r"удал[её]н|remote|из дома", low):
        bd["format_match"] = 100
    elif city and stem(city) in " ".join(stem(w) for w in re.findall(r"[а-яёa-z-]{3,}", low)):
        bd["format_match"] = 100
    elif re.search(r"\b(минск|москв|гродн|брест|гомел|могил|витеб|санкт|петербург|киев|алмат|ташкент|варшав)", low):
        bd["format_match"] = 60 if not city else 30
    else:
        bd["format_match"] = 75
    has_edu = bool(EDU.search(c["text"]))
    bd["education"] = (100 if has_edu else 40) if re.search(r"высшее|образовани|degree", low) else (85 if has_edu else 65)
    want, have = _langs(vt), _langs(c["text"] + "\n" + " ".join(c.get("languages") or []))
    if want:
        parts = []
        for lang, lv in want.items():
            if lang not in have:
                parts.append(15)
            else:
                gap = LEVELS.index(lv) - LEVELS.index(have[lang])
                parts.append(100 if gap <= 0 else max(20, 100 - gap * 25))
        bd["languages"] = round(sum(parts) / len(parts))
    else:
        bd["languages"] = 80 if have else 65
    total = round(sum(bd[k] * WEIGHTS[k] for k in WEIGHTS))
    honesty = max(0, 100 - 25 * len(c.get("flags") or []))
    out = {"id": c["id"], "name": c.get("name") or c.get("file"), "position": c.get("position") or "", "stage": c.get("stage"),
           "total": total, "breakdown": bd, "honesty": honesty, "has": got[:12], "missing": miss[:12], "need_years": need,
           "years": round(yrs, 1) if c.get("exp_months") else None, "city": c.get("city") or "", "salary": c.get("salary") or "",
           "languages": c.get("languages") or [], "flags": c.get("flags") or [], "education": has_edu}
    lira = (c.get("scores") or {}).get(v.get("id"))
    if lira:
        out["lira"] = lira["total"]
    return out


def rank(ref):
    d = load()
    v = find_vac(d, ref)
    if not v:
        return None, []
    rows = [assess(c, v) for c in d["cands"].values() if c.get("stage") != "отказ"]
    rows.sort(key=lambda r: (-r["total"], -r["honesty"], -(r["years"] or 0)))
    return v, rows


def versus(a, b, need=None):
    """Двое под одну вакансию -> параметры с победителем по каждому, кто сильнее и почему (без модели)."""
    yrs = lambda r: "нет данных" if r["years"] is None else f"{r['years']:g}".replace(".", ",") + " г."   # noqa: E731
    P = []
    def row(name, av, bv, sa, sb, comment=""):
        w = "A" if sa > sb else "B" if sb > sa else "="
        P.append({"name": name, "a_value": av, "b_value": bv, "winner": w, "comment": comment, "gap": abs(sa - sb)})
    row("Совпадение с требованиями", f"{a['breakdown']['hard_skills']}%", f"{b['breakdown']['hard_skills']}%",
        a["breakdown"]["hard_skills"], b["breakdown"]["hard_skills"],
        f"нужно: {', '.join((a['has'] + a['missing'])[:6])}" if (a["has"] or a["missing"]) else "")
    row("Стаж", yrs(a), yrs(b), a["breakdown"]["experience"], b["breakdown"]["experience"], f"в вакансии — от {need} лет" if need else "")
    row("Город и формат", a["city"] or "—", b["city"] or "—", a["breakdown"]["format_match"], b["breakdown"]["format_match"])
    row("Образование", "высшее" if a["education"] else "не видно", "высшее" if b["education"] else "не видно",
        a["breakdown"]["education"], b["breakdown"]["education"])
    row("Языки", ", ".join(a["languages"]) or "—", ", ".join(b["languages"]) or "—", a["breakdown"]["languages"], b["breakdown"]["languages"])
    row("Честность анкеты", f"{a['honesty']}" + (f" · {len(a['flags'])} уточнить" if a["flags"] else ""),
        f"{b['honesty']}" + (f" · {len(b['flags'])} уточнить" if b["flags"] else ""), a["honesty"], b["honesty"])
    P.append({"name": "Ожидания", "a_value": a["salary"] or "—", "b_value": b["salary"] or "—", "winner": "", "comment": "сравните с бюджетом", "gap": 0})
    wt = {"Совпадение с требованиями": WEIGHTS["hard_skills"], "Стаж": WEIGHTS["experience"], "Город и формат": WEIGHTS["format_match"],
          "Образование": WEIGHTS["education"], "Языки": WEIGHTS["languages"], "Честность анкеты": 0.2}
    key = max((p for p in P if p["winner"] in ("A", "B")), key=lambda p: p["gap"] * wt.get(p["name"], 0), default=None)   # что весит больше в итоге
    if a["total"] != b["total"]:
        win = "A" if a["total"] > b["total"] else "B"
    else:
        win = "A" if (a["honesty"], a["years"] or 0) >= (b["honesty"], b["years"] or 0) else "B"
    W, L = (a, b) if win == "A" else (b, a)
    adv = lambda side: [f"{p['name'].lower()}: {p['a_value' if side == 'A' else 'b_value']}" for p in P if p["winner"] == side]   # noqa: E731
    close = abs(a["total"] - b["total"]) < 4
    kf = (key or {}).get("name", "общий балл")
    reason = (f"{W['name']} — {W['total']} против {L['total']}" + (", почти вровень" if close else "")
              + (f"; решило: {kf.lower()}" if key else ""))
    for p in P:
        p.pop("gap", None)
    return {"winner": win, "winner_id": W["id"], "loser_id": L["id"], "close": close, "key_factor": kf, "reason": reason,
            "parameters": P, "a_advantages": adv("A"), "b_advantages": adv("B")}


def compare(a_id, b_id, ref=""):
    d = load()
    v = find_vac(d, ref) if (ref or d["vacs"]) else None
    ca, cb = d["cands"].get(str(a_id)), d["cands"].get(str(b_id))
    if not ca or not cb:
        return {"error": "нет такого кандидата"}
    v = v or {"id": "", "title": "без вакансии", "text": (ca.get("position") or "") + " " + (cb.get("position") or "")}
    A, B = assess(ca, v), assess(cb, v)
    out = versus(A, B, need_years(v.get("title", "") + " " + v.get("text", "")))
    return out | {"vacancy": {"id": v.get("id"), "title": v.get("title")}, "a": A, "b": B}


def tournament(ref="", size=8):
    """«Турнир» как в модуле владельца: все кандидаты оцениваются под вакансию, лучшие (до 8) — в сетку 1–8, 2–7…, пары
    решаются сравнением (versus), подиум — тройка по баллу (одно правило победителя, как у владельца)."""
    v, rows = rank(ref)
    if not v:
        return {"error": "Нет такой вакансии — сначала опишите её."}
    if not rows:
        return {"error": "Кандидатов пока нет — закиньте резюме."}
    n = max(2, min(16, int(size or 8)))
    top = rows[:n]
    need = need_years(v.get("title", "") + " " + v.get("text", ""))
    pow2 = 1
    while pow2 < len(top):
        pow2 *= 2
    pad = top + [None] * (pow2 - len(top))
    pairs = [(pad[i], pad[pow2 - 1 - i]) for i in range(pow2 // 2)]
    rounds = []
    while pairs:
        name = "Финал" if len(pairs) == 1 else "Полуфинал" if len(pairs) == 2 else "Четвертьфинал" if len(pairs) == 4 else f"Раунд {len(pairs)} пар"
        battles, winners = [], []
        for a, b in pairs:
            if not a or not b:
                w = a or b
                if w:
                    battles.append({"a": w["id"], "b": None, "winner": w["id"], "bye": True, "reason": "проходит без пары"})
                    winners.append(w)
                continue
            r = versus(a, b, need)
            w = a if r["winner"] == "A" else b
            battles.append({"a": a["id"], "b": b["id"], "winner": w["id"], "reason": r["reason"], "key_factor": r["key_factor"], "close": r["close"]})
            winners.append(w)
        rounds.append({"name": name, "battles": battles})
        if len(winners) <= 1:
            break
        pairs = [(winners[i], winners[i + 1] if i + 1 < len(winners) else None) for i in range(0, len(winners), 2)]
    d = load()
    v2 = d["vacs"].get(v["id"])
    if v2 is not None:
        v2["last"] = {"at": now(), "top": [r["id"] for r in rows[:3]]}
        save(d)
    return {"vacancy": {"id": v["id"], "title": v["title"], "need_years": need, "key_terms": [x["w"] for x in terms(v["title"] + " " + v.get("text", "")).values()][:20]},
            "ranking": rows, "in_bracket": [r["id"] for r in top], "rounds": rounds,
            "champion": rounds[-1]["battles"][0]["winner"] if rounds and rounds[-1]["battles"] else (top[0]["id"] if top else None),
            "podium": [r["id"] for r in rows[:3]], "criteria": CRIT, "weights": WEIGHTS}


def tech(text):
    """Ключевые технологии и инструменты из резюме (латиница, 1С) — плашки на карточке кандидата."""
    cnt = {}
    text = re.sub(r"\S+@\S+|https?://\S+|www\.\S+|t\.me/\S+|@\w+", " ", text)     # почта, ссылки, ники — не навыки
    for w in re.findall(r"\b(?:1[СC](?::[\w ]{0,20})?|[A-Za-z][A-Za-z0-9+#.]{1,20}[A-Za-z0-9+#])", text):
        k = w.strip().rstrip(".")
        if k.lower() in TECH_STOP or len(k) < 2:
            continue
        cnt[k] = cnt.get(k, 0) + 1
    return [k for k, _ in sorted(cnt.items(), key=lambda x: -x[1])][:8]


TECH_STOP = set("the and of in on to for with at by from an as is are be or we you it our your this that work experience years year months "
                "month skills education phone email mail com ru by org net www http https gmail yandex tut senior junior middle lead cv "
                "resume developer engineer manager ltd llc byn usd eur rub telegram skype linkedin viber whatsapp script alert img src "
                "onerror male female mr ms".split())


def get(cid):
    c = load()["cands"].get(str(cid))
    if not c:
        return {"error": "нет такого кандидата"}
    out = {k: v for k, v in c.items() if k not in ("text", "path") and v not in ("", None, [], {})}
    out["text"] = c["text"][:12000]
    out["flags"] = c.get("flags") or []
    if c.get("path") and Path(c["path"]).exists():
        out["path"] = c["path"]                       # исходный файл — «Открыть резюме» на странице плагина
    return out


def board():
    """Всё для своей страницы плагина (ui.html) одним ответом: кандидаты с фактами и оценками, вакансии, этапы.
    Только для страницы — помощнице не показывается (_meta dewiar/page)."""
    d = load()
    vac = {v["id"]: v["title"] for v in d["vacs"].values()}
    cands = []
    for c in sorted(d["cands"].values(), key=lambda c: c.get("added", ""), reverse=True)[:500]:
        x = brief(c) | {k: c[k] for k in ("city", "age", "salary", "phone", "email", "telegram", "file", "added", "languages") if c.get(k)}
        x["flags"] = c.get("flags") or []
        x["scores"] = {vid: {"total": s["total"], "vacancy": vac.get(vid, "")} for vid, s in (c.get("scores") or {}).items()}
        x["notes"] = len(c.get("notes") or [])
        x["tech"] = tech(c.get("text", ""))
        x["honesty"] = max(0, 100 - 25 * len(x["flags"]))
        cands.append(x)
    return {"stages": STAGES, "criteria": CRIT, "folder": str(settings().get("folder") or ""), "inbox": str(inbox()),
            "vacancies": [{"id": v["id"], "title": v["title"], "text": v.get("text", "")[:3000], "at": v.get("at", ""), "last": v.get("last")}
                          for v in sorted(d["vacs"].values(), key=lambda v: v.get("at", ""), reverse=True)],
            "cands": cands}


def lst(stage="", q="", vacancy="", limit=20):
    d = load()
    cs = list(d["cands"].values())
    if stage:
        cs = [c for c in cs if c.get("stage") == stage]
    if q:
        qs = [stem(w) for w in re.findall(r"\w{3,}", q)]
        cs = [c for c in cs if all(s in (c.get("name", "") + " " + c.get("position", "") + " " + c["text"]).lower() for s in qs)]
    if vacancy:
        cs = [c for c in cs if vacancy in (c.get("scores") or {})]
        cs.sort(key=lambda c: -c["scores"][vacancy]["total"])
    else:
        cs.sort(key=lambda c: c.get("added", ""), reverse=True)
    by = {s: sum(1 for c in d["cands"].values() if c.get("stage") == s) for s in STAGES}
    return {"total": len(cs), "stages": {k: v for k, v in by.items() if v}, "items": [brief(c) for c in cs[:max(1, min(50, int(limit or 20)))]]}


def vacancy(title="", text="", vid=""):
    d = load()
    if not (title or text):
        return {"vacancies": [{"id": v["id"], "title": v["title"], "at": v["at"]} for v in d["vacs"].values()]}
    vid = vid if vid in d["vacs"] else sid("v", (title or text[:60]) + now())
    v = d["vacs"].get(vid) or {"id": vid, "at": now()}
    v.update(title=title or v.get("title") or text[:60], text=text or v.get("text", ""))
    d["vacs"][vid] = v
    save(d)
    return {"id": vid, "title": v["title"], "key_terms": [x["w"] for x in terms(v["text"] + " " + v["title"]).values()][:25]}


def find_vac(d, ref):
    if ref in d["vacs"]:
        return d["vacs"][ref]
    ref_l = str(ref or "").lower()
    hit = [v for v in d["vacs"].values() if ref_l and ref_l in v["title"].lower()]
    return hit[0] if hit else (list(d["vacs"].values())[-1] if d["vacs"] and not ref else None)


def shortlist(ref="", limit=10, stage=""):
    d = load()
    v = find_vac(d, ref)
    if not v:
        return {"error": "Нет такой вакансии — сначала опишите её (recruit_vacancy)."}
    rows = []
    for c in d["cands"].values():
        if stage and c.get("stage") != stage or c.get("stage") == "отказ":
            continue
        pct, got, miss = match(v["title"] + "\n" + v["text"], c["text"])
        rows.append((pct, c, got, miss))
    rows.sort(key=lambda r: -r[0])
    return {"vacancy": {"id": v["id"], "title": v["title"]},
            "items": [brief(c) | {"words_match": pct, "has": got[:10], "missing": miss[:10]} for pct, c, got, miss in rows[:max(1, min(100, int(limit or 10)))]],
            "note": "Это отбор по словам. Лучших прочитайте (recruit_get) и оцените (recruit_score)."}


def score(cid, vac, breakdown, matches=None, gaps=None, summary=""):
    d = load()
    c, v = d["cands"].get(str(cid)), find_vac(d, vac)
    if not c or not v:
        return {"error": "нет такого кандидата или вакансии"}
    bd = {}
    for k in WEIGHTS:
        try:
            bd[k] = max(0, min(100, float((breakdown or {})[k])))
        except (KeyError, TypeError, ValueError):
            pass
    if not bd:
        return {"error": "нужна оценка хотя бы по одному критерию: " + ", ".join(WEIGHTS)}
    total = round(sum(bd[k] * WEIGHTS[k] for k in bd) / sum(WEIGHTS[k] for k in bd))
    c.setdefault("scores", {})[v["id"]] = {"total": total, "breakdown": bd, "matches": [str(x)[:120] for x in (matches or [])][:10],
                                           "gaps": [str(x)[:120] for x in (gaps or [])][:10], "summary": str(summary or "")[:500], "at": now()}
    save(d)
    rank = sorted(((x["scores"][v["id"]]["total"], x["id"]) for x in d["cands"].values() if v["id"] in (x.get("scores") or {})), reverse=True)
    return {"total": total, "by": {CRIT[k]: round(bd[k]) for k in bd}, "place": [i for _, i in rank].index(c["id"]) + 1, "of": len(rank),
            "vacancy": v["title"]}


def update(cid, stage="", note="", remove=False):
    d = load()
    ids = list(d["cands"]) if cid == "all" else [str(cid)]
    if any(i not in d["cands"] for i in ids):
        return {"error": "нет такого кандидата"}
    if stage and stage not in STAGES:
        return {"error": "этап — один из: " + ", ".join(STAGES)}
    for i in ids:
        if remove:
            d["cands"].pop(i)
            continue
        c = d["cands"][i]
        if stage:
            c["stage"] = stage
            c["notes"].append({"at": now(), "text": f"этап: {stage}"})
        if note:
            c["notes"].append({"at": now(), "text": str(note)[:1000]})
    save(d)
    return {"ok": True, "changed": len(ids)}


# ---------------- MCP ----------------

def T(name, title, desc, props=None, req=None, page=False):
    return {"name": name, "description": desc, "annotations": {"readOnlyHint": True, "title": title},
            "inputSchema": {"type": "object", "properties": props or {}, **({"required": req} if req else {})},
            **({"_meta": {"dewiar/page": True}} if page else {})}


S_ = {"type": "string"}
TOOLS = [
    T("recruit_add", "Разобрать резюме", "Добавить резюме из файла или папки (PDF, Word, ODT, текст); без path — папка из настроек. "
      "Повторы пропускаются. Для одного файла возвращает и текст.", {"path": S_}),
    T("recruit_list", "Кандидаты", "Кандидаты: по этапу (stage), словам (q) или с оценкой под вакансию (vacancy — id), лучшие первыми.",
      {"stage": {"type": "string", "enum": STAGES}, "q": S_, "vacancy": S_, "limit": {"type": "integer"}}),
    T("recruit_get", "Резюме кандидата", "Резюме кандидата целиком: факты, сигналы для уточнения, оценки, заметки, текст.", {"id": S_}, ["id"]),
    T("recruit_vacancy", "Вакансия", "Сохранить вакансию (title и text — требования) или, без них, показать список вакансий.",
      {"title": S_, "text": S_, "id": S_}),
    T("recruit_match", "Отбор под вакансию", "Предварительный отбор под вакансию по словам: у кого больше совпадений, чего не хватает.",
      {"vacancy": {"type": "string", "description": "id или часть названия; пусто — последняя"}, "limit": {"type": "integer"}}),
    T("recruit_score", "Оценка кандидата", "Записать твою оценку кандидата под вакансию по критериям 0–100 (hard_skills, experience, "
      "format_match, education, languages); итог считается по весам.",
      {"id": S_, "vacancy": S_, "breakdown": {"type": "object", "properties": {k: {"type": "number"} for k in WEIGHTS}},
       "matches": {"type": "array", "items": S_}, "gaps": {"type": "array", "items": S_}, "summary": S_}, ["id", "vacancy", "breakdown"]),
    T("recruit_update", "Этап и заметка", "Перевести кандидата на этап воронки, добавить заметку или удалить (remove).",
      {"id": S_, "stage": {"type": "string", "enum": STAGES}, "note": S_, "remove": {"type": "boolean"}}, ["id"]),
    T("recruit_board", "Сводка", "Кандидаты, вакансии и этапы — для страницы плагина в студии.", page=True),
    T("recruit_import", "Закинуть резюме", "Файлы резюме со страницы (имя и содержимое base64; ZIP распаковывается) — в папку резюме и разбор.",
      {"files": {"type": "array", "items": {"type": "object", "properties": {"name": S_, "b64": S_}}}}, ["files"], page=True),
    T("recruit_edit", "Поправить карточку", "Правка карточки кандидата руками или «переразобрать» из текста.",
      {"id": S_, "fields": {"type": "object"}, "reparse": {"type": "boolean"}}, ["id"], page=True),
    T("recruit_compare", "Сравнить двоих", "Сравнение двух кандидатов под вакансию по параметрам — кто сильнее и почему (без модели).",
      {"a": S_, "b": S_, "vacancy": S_}, ["a", "b"]),
    T("recruit_tournament", "Подбор лучших", "Подбор под вакансию без модели: оценка всех по пяти критериям, турнир лучших попарно, тройка лидеров.",
      {"vacancy": {"type": "string", "description": "id или часть названия; пусто — последняя"}, "size": {"type": "integer"}}),
]


def call(name, a):
    if name == "recruit_add":
        return add(a.get("path"))
    if name == "recruit_list":
        return lst(a.get("stage") or "", a.get("q") or "", a.get("vacancy") or "", a.get("limit") or 20)
    if name == "recruit_get":
        return get(a.get("id"))
    if name == "recruit_vacancy":
        return vacancy(a.get("title") or "", a.get("text") or "", a.get("id") or "")
    if name == "recruit_match":
        return shortlist(a.get("vacancy") or "", a.get("limit") or 10)
    if name == "recruit_score":
        return score(a.get("id"), a.get("vacancy"), a.get("breakdown"), a.get("matches"), a.get("gaps"), a.get("summary") or "")
    if name == "recruit_board":
        return board()
    if name == "recruit_import":
        return import_files(a.get("files") or [])
    if name == "recruit_edit":
        return edit(a.get("id"), a.get("fields") or {}, bool(a.get("reparse")))
    if name == "recruit_compare":
        return compare(a.get("a"), a.get("b"), a.get("vacancy") or "")
    if name == "recruit_tournament":
        return tournament(a.get("vacancy") or "", a.get("size") or 8)
    if name == "recruit_update":
        return update(a.get("id"), a.get("stage") or "", a.get("note") or "", bool(a.get("remove")))
    raise ValueError("нет такого действия")


def handle(msg):
    m, i = msg.get("method"), msg.get("id")
    if i is None:
        return None
    if m == "initialize":
        return {"jsonrpc": "2.0", "id": i, "result": {"protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2024-11-05"),
                                                       "capabilities": {"tools": {}}, "serverInfo": {"name": "dewiar-recruiter", "version": "1.0"}}}
    if m == "tools/list":
        return {"jsonrpc": "2.0", "id": i, "result": {"tools": TOOLS}}
    if m == "tools/call":
        p = msg.get("params") or {}
        try:
            res = call(p.get("name"), p.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": i, "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}],
                                                           **({"isError": True} if isinstance(res, dict) and res.get("error") else {})}}
        except Exception as e:  # noqa: BLE001
            return {"jsonrpc": "2.0", "id": i, "result": {"isError": True, "content": [{"type": "text", "text": f"Ошибка: {e}"}]}}
    if m == "ping":
        return {"jsonrpc": "2.0", "id": i, "result": {}}
    return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": "нет такого метода"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            r = handle(json.loads(line))
        except ValueError:
            continue
        if r is not None:
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
