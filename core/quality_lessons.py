"""Уроки (quality.py): следы задач -> раз в REFLECT_EVERY модель выводит обобщённые правила в «Память/Уроки задач.md»
(правится в студии) -> они идут в подсказку следующих задач; поправки человека в разговоре -> «Память/Уроки.md»."""

import json
import re
import time

from pathlib import Path
from quality_files import log


LESSONS_FILE = "Память/Уроки задач.md"


TALK_LESSONS_FILE = "Память/Уроки.md"   # чему ассистент научился на поправках пользователя в разговоре (learn_from_correction)


TALK_LESSONS_PROMPT_MAX = 1500


LESSONS_MAX = 30                 # правил в файле — самые старые уходят


LESSONS_PROMPT_MAX = 2500        # символов уроков в подсказку задачи


REFLECT_MIN = 3                  # новых следов задач, чтобы было из чего делать выводы


REFLECT_EVERY = 6 * 3600         # не чаще (секунд); проверяет tasks.py, можно переопределить DEWIAR_REFLECT_EVERY


# ---------------- следы задач и уроки ----------------


def norm_error(text):
    """Подпись ошибки для группировки: без чисел, путей, хешей."""
    t = re.sub(r"(?:[A-Za-z]:)?[\\/][^\s'\"]+", "*", text or "")
    t = re.sub(r"\b[0-9a-f]{8,}\b|\d+", "*", t)
    return re.sub(r"\s+", " ", t).strip()[:120]


def save_trace(traces_dir, trace):
    """Сохранить след задачи (что вызывала, какие ошибки, чем кончилось) для reflect; хранятся последние 300."""
    d = Path(traces_dir)
    try:
        d.mkdir(parents=True, exist_ok=True)
        name = time.strftime("%Y%m%d_%H%M%S") + "_" + re.sub(r"\W+", "_", str(trace.get("id", "")))[:20] + ".json"
        (d / name).write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
        files = sorted(d.glob("*.json"))
        for f in files[:-300]:
            f.unlink(missing_ok=True)
    except OSError as e:
        log.info("след задачи не сохранился: %s", e)


def read_lessons(path):
    """Уроки — строки «- …» файла; остальное (заголовок, пояснения пользователя) пропускается."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    return [ln[2:].strip() for ln in text.splitlines() if ln.startswith("- ") and ln[2:].strip()]


def lessons_block(path, meta_path=None):
    """Блок уроков для подсказки задачи; длинный — обрезается до LESSONS_PROMPT_MAX с начала (свежие уроки в конце).
    HARNESS 8, п.9 (meta_path — проверка уроков): не помогшие (их ошибка повторялась) в подсказку не идут, проверенные —
    в конце с пометкой (обрезка с начала их не теряет)."""
    ls = read_lessons(path)
    if not ls:
        return ""
    if meta_path:
        meta = lessons_meta(meta_path)
        st = {x: lesson_status(meta.get(x)) for x in ls}
        ls = [x for x in ls if st[x] == "new"] + \
             [f"{x} (проверено: {int((meta.get(x) or {}).get('seen', 0))} задач без этой ошибки)" for x in ls if st[x] == "ok"]
        if not ls:
            return ""
    text = "\n".join("- " + x for x in ls)
    if len(text) > LESSONS_PROMPT_MAX:
        text = text[-LESSONS_PROMPT_MAX:].split("\n", 1)[-1]
    return "\n\nВЫУЧЕННЫЕ УРОКИ (выводы из твоих прошлых задач — соблюдай их):\n" + text


REFLECT = (
    "Ты — аналитик качества голосового ассистента, который выполняет долгие задачи инструментами (поиск в интернете, чтение "
    "страниц, Python, файлы, письма, ожидание ответа). Тебе дают дайджест его недавних задач: статистику, повторяющиеся ошибки, "
    "примеры.\n\nИзвлеки ОБОБЩЁННЫЕ выводы, которые предотвратят будущие ошибки:\n«lessons»: 0–6 коротких правил. Каждое: одна "
    "строка до 140 символов, по-русски, повелительное наклонение; ОБОБЩЕНИЕ, а не пересказ случая (плохо: «не качай файл X с "
    "сайта Y», хорошо: «при 403 от сайта добавляй User-Agent»); практичное действие, не банальность («работай аккуратнее» — "
    "мусор); не повторяй уже существующие уроки и не противоречь им. Выводов нет — пустой список: лучше 0 уроков, чем слабые.\n"
    "Если правило против одной из «Частых ошибок» дайджеста — укажи её в «against» дословно, как в дайджесте (по ней "
    "проверим, помогло ли правило). Уроки из «НЕ ПОМОГЛИ» замени лучшей формулировкой или не повторяй.\n\n"
    "Ответь строго JSON: {\"lessons\": [{\"rule\": \"...\", \"against\": \"...\"}]} (against можно пустым).")


def digest(traces):
    """Следы задач -> текстовая сводка для REFLECT: статистика, частые ошибки, до 10 примеров (сначала неудачи)."""
    ok = sum(1 for t in traces if t.get("ok"))
    reasons = {}
    errs = {}
    refusals = loops = critic_n = verify_n = 0
    for t in traces:
        reasons[t.get("reason", "?")] = reasons.get(t.get("reason", "?"), 0) + 1
        for e in t.get("errors") or []:
            k = norm_error(e.get("text", ""))
            if k:
                errs[k] = errs.get(k, 0) + 1
        refusals += 1 if t.get("refusal") else 0
        loops += int(t.get("loop_warns") or 0)
        critic_n += 1 if t.get("critic") else 0
        verify_n += 1 if t.get("verify_fail") else 0
    lines = [f"Задач: {len(traces)}, успешно: {ok}, не получилось: {len(traces) - ok}.",
             "Чем закончились: " + ", ".join(f"{k} — {v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1]))]
    if refusals:
        lines.append(f"ЛОЖНЫХ ОТКАЗОВ («нет доступа», хотя поиск был): {refusals}.")
    if loops:
        lines.append(f"Предупреждений о зацикливании: {loops}.")
    if verify_n:
        lines.append(f"Машинная проверка файлов находила брак в {verify_n} задачах.")
    if critic_n:
        lines.append(f"Самопроверка возвращала итог на доработку в {critic_n} задачах.")
    if errs:
        lines.append("Частые ошибки:\n" + "\n".join(f"- ({n}×) {k}" for k, n in sorted(errs.items(), key=lambda x: -x[1])[:12]))
    ex = [t for t in traces if not t.get("ok")][:6] + [t for t in traces if t.get("ok")][:4]
    for t in ex:
        lines.append(f"\nПример ({'успех' if t.get('ok') else 'неудача'}, {t.get('reason')}, шагов {t.get('steps')}): "
                     f"{str(t.get('goal', ''))[:160]}\n  инструменты: {json.dumps(t.get('tools') or {}, ensure_ascii=False)[:200]}"
                     + "".join(f"\n  ошибка: {str(e.get('text', ''))[:140]}" for e in (t.get("errors") or [])[:3]))
    return "\n".join(lines)


def _words(s):
    return {w for w in re.findall(r"\w+", s.lower()) if len(w) > 3}


def merge_lessons(old, new):
    """Добавить новые уроки к старым: отбрасываются банальности, слишком короткие/длинные и почти повторы
    (больше 60% общих слов). Остаются последние LESSONS_MAX."""
    out = list(old)
    for x in new:
        x = re.sub(r"\s+", " ", str(x)).strip().lstrip("-•* ").strip()
        if not 15 <= len(x) <= 160 or re.match(r"^(работай|будь|старай|думай) ", x.lower()):
            continue
        w = _words(x)
        if any(w and _words(y) and len(w & _words(y)) / min(len(w), len(_words(y))) > 0.6 for y in out):
            continue
        out.append(x)
    return out[-LESSONS_MAX:]


TALK_HEAD = ("# Уроки\n\nЧему ассистент научился на ваших поправках («нет, я же просил…», «не так», «короче»). Он соблюдает "
             "это в разговорах и в задачах. Можно править и удалять строки — ассистент учтёт. Не больше 30, старые уходят.\n\n")


# «нет, не так», «я же просил», «опять», «неправильно», «сколько раз говорить», «в следующий раз…», «не делай так»
_CORRECTION = re.compile(
    r"(^|[\s,.!?])(нет[,.!]?\s+(не\s+так|не\s+то|я\s+же|я\s+просил|я\s+говорил|неправильно)|не\s+так[,.!]|я\s+же\s+(просил|говорил|сказал)|"
    r"(ты\s+)?(опять|снова)\s+(не|забыл|ошиб|перепутал)|неправильно|неверно|ошиб(ся|лась|ка)|сколько\s+(раз\s+)?(можно\s+)?(говорить|повторять)|"
    r"в\s+следующий\s+раз|не\s+делай\s+так|больше\s+так\s+не\s+делай|я\s+(не\s+)?просил|не\s+надо\s+было|зачем\s+ты)", re.I)


LEARN = (
    "Ты помогаешь голосовому ассистенту учиться на ошибках. Пользователь его поправил. Предыдущий ответ ассистента:\n«{prev}»\n"
    "Слова пользователя:\n«{said}»\n\nЕсли это поправка или недовольство тем, КАК ассистент ответил или сделал, — сформулируй ОДНО "
    "короткое общее правило на будущее (до 20 слов, в повелительном наклонении, без имён и дат, полезное и в других разговорах), "
    "например: «Отвечай короче — одной-двумя фразами, если не просят подробно». Если это не поправка (просто ответ, новая "
    "просьба, уточнение факта) или правило было бы бессмысленным — ответь одним словом: НЕТ.\nОтвет — только правило или НЕТ.")


def looks_like_correction(text):
    """Похоже на поправку ассистента («нет, я же просил коротко», «опять не то»)? Только кандидат: решает модель (LEARN)."""
    return bool(_CORRECTION.search(text or "")) and len(text or "") < 600


def learn_from_correction(ask, prev, said, path):
    """Поправка -> правило модели -> строка в «Память/Уроки.md». ask(prompt) -> ответ модели. -> правило или "".
    Такое же правило уже есть (совпадает без учёта регистра и знаков) — не дублируем."""
    rule = (ask(LEARN.format(prev=(prev or "")[-800:], said=(said or "")[:600])) or "").strip().strip("«»\"' ")
    rule = re.sub(r"^(правило|урок)\s*:\s*", "", rule, flags=re.I).strip()
    if not rule or re.fullmatch(r"нет\.?", rule, re.I) or len(rule) > 220 or "\n" in rule:
        return ""
    have = read_lessons(path)
    norm = lambda x: re.sub(r"[\W_]+", " ", x.lower()).strip()   # noqa: E731
    if norm(rule) in {norm(x) for x in have}:
        return ""
    write_lessons(path, (have + [rule])[-LESSONS_MAX:], head=TALK_HEAD)
    return rule


def talk_lessons_block(path):
    """Блок уроков из поправок для подсказки разговора и задач; длинный — свежие важнее."""
    ls = read_lessons(path)
    if not ls:
        return ""
    text = "\n".join("- " + x for x in ls)
    if len(text) > TALK_LESSONS_PROMPT_MAX:
        text = text[-TALK_LESSONS_PROMPT_MAX:].split("\n", 1)[-1]
    return "\n\nЧЕМУ ТЫ НАУЧИЛСЯ У ПОЛЬЗОВАТЕЛЯ (выводы из его поправок, «Память/Уроки.md» — соблюдай всегда):\n" + text


def write_lessons(path, lessons, head=None):
    """Перезаписать файл уроков через временный файл, чтобы сбой посреди записи не стёр уроки."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    head = head or ("# Уроки задач\n\nЭти правила ассистент вывел сам из своих прошлых задач и соблюдает в новых. Можно править и "
                    "удалять строки — ассистент учтёт. Не больше 30, старые уходят.\n\n")
    tmp = p.with_suffix(".tmp")
    tmp.write_text(head + "".join(f"- {x}\n" for x in lessons), encoding="utf-8")
    tmp.replace(p)


# HARNESS 8, п.9 «уроки — проверенные правила» (как CLAUDE.md у Claude, только с проверкой): у урока — против какой
# ошибки он (against, подпись norm_error из дайджеста). После появления урока каждая задача — проверка: ошибка
# повторилась — «hit». LESSON_OK задач без неё — урок проверен; LESSON_WEAK повторов — не помог: из подсказки убирается,
# а при следующих выводах модель его переформулирует (или не повторяет).
LESSONS_META = "lessons.meta"           # не .json: в папке следов *.json — следы задач


LESSON_OK = 4


LESSON_WEAK = 2


def lessons_meta(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_meta(path, meta):
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
    except OSError as e:
        log.info("проверка уроков не сохранилась: %s", e)


def lesson_status(m):
    """-> new (ещё не проверен), ok (LESSON_OK задач — и его ошибки не было), weak (ошибка повторялась)."""
    if not m:
        return "new"
    if int(m.get("hit", 0)) >= LESSON_WEAK:
        return "weak"
    if m.get("against") and int(m.get("seen", 0)) >= LESSON_OK and not int(m.get("hit", 0)):
        return "ok"
    return "new"


def _err_hit(against, errors):
    a = norm_error(against).lower()
    if len(a) < 8:
        return False
    for e in errors or []:
        k = norm_error(e.get("text", "") if isinstance(e, dict) else str(e)).lower()
        if k and (a in k or k in a):
            return True
    return False


def lessons_track(meta_path, trace, lessons_path=None):
    """Задача кончилась (её след) -> счётчики уроков, появившихся до неё. -> {урок: новый статус} для тех, чей статус
    изменился (ok — проверен, weak — не помог)."""
    meta = lessons_meta(meta_path)
    if not meta:
        return {}
    have = set(read_lessons(lessons_path)) if lessons_path else None
    changed = {}
    now = time.time()
    for rule, m in meta.items():
        if have is not None and rule not in have:          # урок удалили в студии — не считаем
            continue
        if float(m.get("t", now)) > now - 1:
            continue
        before = lesson_status(m)
        m["seen"] = int(m.get("seen", 0)) + 1
        if m.get("against") and _err_hit(m["against"], trace.get("errors")):
            m["hit"] = int(m.get("hit", 0)) + 1
        after = lesson_status(m)
        if after != before:
            changed[rule] = after
    _save_meta(meta_path, meta)
    return changed


def reflect(ask, traces_dir, lessons_path, min_traces=REFLECT_MIN):
    """Новые следы -> выводы модели -> «Уроки задач.md». -> сколько уроков добавлено (None — новых следов меньше min_traces).
    Разобранные следы помечаются в .reflected и повторно не используются. Ошибки ask не перехватываются.
    Как часто вызывать (REFLECT_EVERY), решает tasks.py."""
    d = Path(traces_dir)
    done_f = d / ".reflected"
    try:
        done = set(done_f.read_text(encoding="utf-8").split()) if done_f.exists() else set()
    except OSError:
        done = set()
    files = [f for f in sorted(d.glob("*.json")) if f.name not in done][-40:]
    if len(files) < min_traces:
        return None
    traces = []
    for f in files:
        try:
            traces.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    meta_p = d / LESSONS_META
    meta = lessons_meta(meta_p)
    old = read_lessons(lessons_path)
    weak = [x for x in old if lesson_status(meta.get(x)) == "weak"]
    old = [x for x in old if x not in weak]                  # не помогшие — уходят, модель их переформулирует
    msg = ("ТЕКУЩИЕ УРОКИ (не дублируй их):\n" + ("\n".join("- " + x for x in old) or "(пока нет)")
           + ("\n\nНЕ ПОМОГЛИ (их ошибка повторялась и после них):\n" + "\n".join(f"- {x} — против: {meta[x].get('against')}" for x in weak)
              if weak else "") + "\n\n" + digest(traces))
    raw = ask(REFLECT, [{"role": "user", "content": msg}]) or ""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    m = re.search(r"\{.*\}", raw, re.S)
    new, against = [], {}
    if m:
        try:
            for x in (json.loads(m.group(0)).get("lessons") or [])[:6]:
                if isinstance(x, dict) and str(x.get("rule") or "").strip():
                    r = re.sub(r"\s+", " ", str(x["rule"])).strip().lstrip("-•* ").strip()
                    new.append(r)
                    if str(x.get("against") or "").strip():
                        against[r] = norm_error(str(x["against"]))
                elif isinstance(x, str):
                    new.append(x)
        except ValueError:
            new = []
    merged = merge_lessons(old, new)
    if merged != old or weak:
        write_lessons(lessons_path, merged)
    t0 = time.time()
    meta = {k: v for k, v in meta.items() if k in merged}
    for x in merged:
        if x not in meta:
            meta[x] = {"t": t0, "against": against.get(x, ""), "seen": 0, "hit": 0}
    _save_meta(meta_p, meta)
    with open(done_f, "a", encoding="utf-8") as f:
        f.write("".join(x.name + "\n" for x in files))
    added = len([x for x in merged if x not in old])
    log.info("🎓 Уроки задач: из %d задач — новых правил %d (всего %d)", len(traces), added, len(merged))
    return added
