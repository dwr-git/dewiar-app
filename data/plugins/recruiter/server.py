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
    res = {"added": [brief(c) | {k: c[k] for k in ("phone", "email", "telegram", "city", "age", "salary") if c.get(k)} for c in added[:30]],
           "already_known": skipped, "problems": bad[:10]}
    if len(added) == 1:
        res["text"] = added[0]["text"][:6000]
        res["flags"] = added[0]["flags"]
    return res


def get(cid):
    c = load()["cands"].get(str(cid))
    if not c:
        return {"error": "нет такого кандидата"}
    out = {k: v for k, v in c.items() if k not in ("text", "path") and v not in ("", None, [], {})}
    out["text"] = c["text"][:12000]
    return out


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
            "items": [brief(c) | {"words_match": pct, "has": got[:10], "missing": miss[:10]} for pct, c, got, miss in rows[:max(1, min(30, int(limit or 10)))]],
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

def T(name, title, desc, props=None, req=None):
    return {"name": name, "description": desc, "annotations": {"readOnlyHint": True, "title": title},
            "inputSchema": {"type": "object", "properties": props or {}, **({"required": req} if req else {})}}


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
