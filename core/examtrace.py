"""Следы экзамена в данных человека (16.10: в «Обо мне» — «Бюджет Миши на мебель… менялось 13 раз», «Дни рождения:
Аня, Петя, мама»). До 0.38.61 ядро экзамена применяло provision.json, лежащий рядом с программой (у владельца — личный,
с его именем и ключом), и синхронизировало проверочные записи в настоящий аккаунт; оттуда они пришли на компьютер.
Причина закрыта в exam.py; здесь — найти похожее на фразы экзамена (память, заметки, расходы, сделанное) и показать
человеку в студии («Обо мне»): он отмечает и убирает сам — ничего не удаляем без него. Как examTraces в exam.js.

Похожесть: основы слов (длинные — первые 4 буквы, короткие — без последней) записи и одного сценария экзамена: общих
не про месяцы ≥ 4 и это ≥ 60 % слов записи (или ≥ 3 и ≥ 75 %). Приписки памяти («раньше: …», «_(16.10.2026)_», «(на 21.10.2026, среда)») не считаются."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONTHS = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря"
STOP = {"запо", "пожа", "запи", "сохр", "лира", "помо", "поль", "напо", "этог", "чтоб", "меня", "хотя", "дава", "ладн",
        "скол", "како", "сейч", "есть", "если", "очен", "мне", "так", "все", "что", "как", "для", "это", "или", "уже"}
_MON = None                                                # основы названий месяцев — после stems()


def stems(text):
    t = str(text or "")
    t = re.sub(r"\(раньше:[^)]*\)", " ", t)
    t = re.sub(r"_?\(\d{1,2}\.\d{1,2}\.\d{2,4}\)_?|\(на \d{1,2}\.\d{1,2}\.\d{2,4}[^)]*\)", " ", t)
    t = re.sub(r"^со слов пользователя:\s*", "", t.strip(), flags=re.I)
    words = re.findall(r"[a-zа-я]+", t.lower().replace("ё", "е"))
    # длинные слова — по первым 4 буквам, короткие — без последней («Аня» и «Ани», «мама» и «мамы» — одно)
    st = (w[:4] if len(w) >= 5 else w[:-1] for w in words if len(w) >= 3)
    return list(dict.fromkeys(x for x in st if x not in STOP))


def _phrases():
    """Наборы слов по сценариям экзамена компьютера и телефона (фразы, заготовленные заметки и напоминания)."""
    out = []
    try:
        for sc in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8")).get("scenarios", []):
            texts = [st if isinstance(st, str) else (st or {}).get("say", "") for st in sc.get("steps") or []]
            seed = sc.get("seed") or {}
            texts += [f"{n.get('title', '')} {n.get('text', '')}" for n in seed.get("notes") or [] if isinstance(n, dict)]
            texts += [a.get("text", "") or a.get("title", "") for a in seed.get("reminders") or seed.get("alarms") or [] if isinstance(a, dict)]
            out.append(" ".join(t for t in texts if t))
    except (OSError, ValueError):
        pass
    try:                                                   # телефонный экзамен: шаги — строки say: "…" и steps: ["…"]
        js = (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8")
        for block in re.split(r"\n\s*\{\s*id:\s*\"", js)[1:]:
            block = re.sub(r"seed:\s*\{[^}]*\}", " ", block.split("judge:")[0])     # имена «Близких» из заготовок — не фразы
            out.append(" ".join(re.findall(r"(?:say:\s*|steps:\s*\[\s*|,\s*)\"([^\"]{8,})\"", block)))
    except OSError:
        pass
    return [set(stems(re.sub(r"\{date[^}]*\}", " " + MONTHS + " ", t))) for t in out if t.strip()]


def like(text, sets=None):
    global _MON
    if _MON is None:
        _MON = set(stems(MONTHS)) | set(stems("январь февраль март апрель май июнь июль август сентябрь октябрь ноябрь декабрь мае"))
    f = stems(text)
    if len(f) < 2:
        return False
    for e in sets if sets is not None else _phrases():
        common = [w for w in f if w in e]
        nm, share = len([w for w in common if w not in _MON]), len(common) / len(f)
        if (nm >= 4 and share >= 0.6) or (nm >= 3 and share >= 0.75):
            return True
    return False


def find(ws, money=None, done=None):
    """-> [{kind: memory|note|money|done, id, text}] — похожее на записи экзамена."""
    sets, out = _phrases(), []
    for line in (ws.memory_get(who="") or "").splitlines():
        if line.startswith("- ") and like(line[2:], sets):
            out.append({"kind": "memory", "id": line, "text": re.sub(r"\s*_\(\d.*?\)_\s*$", "", line[2:]).strip()})
    for n in ws.notes(limit=2000):
        if n.get("path", "").startswith("Заметки/") and like(f"{n.get('title', '')} {n.get('snippet', '')}", sets):
            out.append({"kind": "note", "id": n["path"], "text": n.get("title") or n["path"]})
    for m in (money.list() if money else []):
        if like(f"{m.get('category', '')} {m.get('note', '')} {m.get('said', '')}", sets):
            out.append({"kind": "money", "id": m["id"], "text": f"{m.get('amount')} {m.get('currency', '')} · {m.get('category', '')}"
                        + (f" · {m['note']}" if m.get("note") else "") + f" · {m.get('date', '')}"})
    for d in (list(done.items) if done else []):
        if like(d.get("title", ""), sets):
            out.append({"kind": "done", "id": d["id"], "text": d.get("title", "")})
    return out


def remove(ws, money, done, items):
    """Убрать отмеченное: строки памяти, заметки (в корзину), расходы, сделанное. -> сколько убрано."""
    n = 0
    mem = {x["id"] for x in items if x.get("kind") == "memory"}
    if mem:
        lines = (ws.memory_get(who="") or "").splitlines()
        keep = [ln for ln in lines if ln not in mem]
        n += len(lines) - len(keep)
        ws.memory_set("\n".join(keep), who="")
    for x in items:
        try:
            if x.get("kind") == "note":
                ws.remove(x["id"])
                n += 1
            elif x.get("kind") == "money" and money:
                money.delete(x["id"])
                n += 1
            elif x.get("kind") == "done" and done:
                done.delete(x["id"])
                n += 1
        except Exception:  # noqa: BLE001
            continue
    return n
