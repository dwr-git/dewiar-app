"""«Мой месяц с Лирой» (0.61; план «Лира — любимица всех»: «итоги месяца: что сделали, сколько дел и напоминаний, траты по
категориям, лучшие моменты»). Всё считается здесь, на компьютере, из того, что уже есть: «Дела» (done.json), напоминания
(журнал «прозвенело»), «Деньги», заметки, дневник, «Дозор», «Заботливая память». В интернет ничего не уходит.

gather(eng, ym) -> {ym, title («октябрь»), done {n, best_day, best_n, streak, top}, rem {n}, money {cur, expense, income,
cats}, notes {n}, diary {days}, watch {n}, care {n}, empty}. context(d) — строки для модели («расскажи мой месяц»).
Студия: карточка на «Главной» в первые 7 дней месяца — о прошлом; голосом — «как прошёл мой месяц?» (инструмент month)."""
import datetime as dt
import json
from pathlib import Path

MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
MONTHS_IN = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре", "октябре", "ноябре", "декабре"]


def bounds(ym):
    y, m = (int(x) for x in ym.split("-"))
    start = dt.date(y, m, 1)
    end = dt.date(y + (m == 12), m % 12 + 1, 1)
    return start, end


def prev_ym(today=None):
    d = (today or dt.date.today()).replace(day=1) - dt.timedelta(days=1)
    return f"{d.year}-{d.month:02d}"


def _in(d, start, end):
    return start <= d < end


def gather(eng, ym=None, today=None):
    ym = ym or f"{(today or dt.date.today()).year}-{(today or dt.date.today()).month:02d}"
    start, end = bounds(ym)
    out = {"ym": ym, "title": MONTHS[start.month - 1], "in": MONTHS_IN[start.month - 1], "in_gen": MONTHS_GEN[start.month - 1], "year": start.year}
    # дела
    try:
        items = sorted((x for x in (eng.done.items or []) if _in(dt.datetime.fromtimestamp(x["at"] / 1000).date(), start, end)), key=lambda x: x["at"])
        by = {}
        for x in items:
            k = dt.datetime.fromtimestamp(x["at"] / 1000).date()
            by[k] = by.get(k, 0) + 1
        best = max(by.items(), key=lambda kv: kv[1], default=(None, 0))
        run = streak = 0
        prev = None
        for k in sorted(by):
            run = run + 1 if prev is not None and (k - prev).days == 1 else 1
            prev = k
            streak = max(streak, run)
        out["done"] = {"n": len(items), "best_day": best[0].isoformat() if best[0] else "", "best_n": best[1], "streak": streak,
                       "days": len(by), "top": [x["title"] for x in items[-5:]],
                       "by_day": [by.get(start + dt.timedelta(days=i), 0) for i in range((end - start).days)]}
    except Exception:  # noqa: BLE001
        out["done"] = {"n": 0}
    # напоминания (прозвенело)
    try:
        log_ = eng._reminder_log()
        out["rem"] = {"n": sum(1 for e in log_ if not e.get("skipped") and e.get("kind") != "job" and _in(dt.date.fromisoformat(str(e.get("at", ""))[:10]), start, end))}
    except Exception:  # noqa: BLE001
        out["rem"] = {"n": 0}
    # деньги
    try:
        s = eng.money.summary(start.isoformat(), (end - dt.timedelta(days=1)).isoformat())
        c = max(s.get("by_currency") or [{}], key=lambda x: x.get("expense", 0))   # главная валюта — где больше трат
        out["money"] = {"cur": c.get("currency", ""), "expense": c.get("expense", 0), "income": c.get("income", 0),
                        "cats": (c.get("expense_cats") or [])[:3], "n": s.get("count", 0)}
    except Exception:  # noqa: BLE001
        out["money"] = {"n": 0}
    # заметки — новые и изменённые за месяц
    try:
        root = Path(eng.workspace.ensure()) / "Заметки"
        out["notes"] = {"n": sum(1 for f in root.rglob("*.md") if _in(dt.date.fromtimestamp(f.stat().st_mtime), start, end))}
    except Exception:  # noqa: BLE001
        out["notes"] = {"n": 0}
    # дневник — сколько дней Лира писала
    try:
        root = Path(eng.workspace.ensure()) / "Дневник"
        days = 0
        for f in root.rglob("*.md"):
            try:
                if _in(dt.date.fromisoformat(f.stem[:10]), start, end):
                    days += 1
            except ValueError:
                continue
        out["diary"] = {"days": days}
    except Exception:  # noqa: BLE001
        out["diary"] = {"days": 0}
    try:
        out["watch"] = {"n": sum(1 for x in eng.watches.data["items"] if x.get("status") == "done"
                                 and _in(dt.date.fromtimestamp(x.get("done_at") or 0), start, end))}
    except Exception:  # noqa: BLE001
        out["watch"] = {"n": 0}
    try:
        out["care"] = {"n": sum(1 for x in eng.care.items if x.get("asked") and _in(dt.date.fromisoformat(x["day"]), start, end))}
    except Exception:  # noqa: BLE001
        out["care"] = {"n": 0}
    out["empty"] = not any((out["done"].get("n"), out["rem"].get("n"), out["money"].get("n"), out["notes"].get("n"), out["diary"].get("days")))
    return out


def context(d):
    """Строки для модели: «[Мой месяц с Лирой] …»."""
    if d.get("empty"):
        return f"[Мой месяц с Лирой — {d['title']} {d['year']}] Записей за этот месяц почти нет: дел, трат и заметок не было."
    L = [f"[Мой месяц с Лирой — {d['title']} {d['year']}]"]
    dn = d.get("done") or {}
    if dn.get("n"):
        L.append(f"Сделано дел: {dn['n']} (дней с делами — {dn.get('days', 0)}, лучшая серия — {dn.get('streak', 0)} дн. подряд, "
                 f"лучший день — {dn.get('best_day', '')}: {dn.get('best_n', 0)}). Последние: " + "; ".join(f"«{t}»" for t in dn.get("top", [])) + ".")
    if (d.get("rem") or {}).get("n"):
        L.append(f"Напоминаний прозвенело: {d['rem']['n']}.")
    m = d.get("money") or {}
    if m.get("n"):
        L.append(f"Деньги: расходы {m['expense']} {m['cur']}, доходы {m['income']} {m['cur']}; больше всего — "
                 + ", ".join(f"{c['name'] or 'без категории'} {c['sum']}" for c in m.get("cats", [])) + ".")
    if (d.get("notes") or {}).get("n"):
        L.append(f"Заметок новых и изменённых: {d['notes']['n']}.")
    if (d.get("diary") or {}).get("days"):
        L.append(f"Дней в дневнике: {d['diary']['days']}.")
    if (d.get("watch") or {}).get("n"):
        L.append(f"«Дозор» дождался: {d['watch']['n']} раз.")
    if (d.get("care") or {}).get("n"):
        L.append(f"Лира спросила, как прошли важные события: {d['care']['n']}.")
    return "\n".join(L)


PROMPT = ("Расскажи пользователю его месяц тепло и живо, своими словами, 4–6 предложений: главное число дел и чем он может "
          "гордиться (назови одно-два дела), куда ушли деньги (одной фразой, без нравоучений), что ещё было. В конце — одно "
          "доброе пожелание на следующий месяц. Без списков и без цифр подряд.")


def as_json(d):
    return json.dumps(d, ensure_ascii=False, default=str)
