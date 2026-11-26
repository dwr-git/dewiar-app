"""Действия модели: деньги — записать, найти, поправить трату, отчёт."""

import re

from tools_base import ToolError


# Бюджет, лимит, «заложим 70 тысяч» — план, а не трата: в расходы не пишем (иначе «потрачено 70 000» в отчёте)
PLAN_RX = re.compile(r"\b(?:бюджет|лимит)\w*\s+(?:на|для)\b|^\s*(?:бюджет|лимит|план)\w*\b|заложи\w*|запланир\w*|планиру\w*|"
                     r"(?:увелич|уменьш|повыш|сниж)\w*\s+(?:с|до)\s+\d", re.I)


SPENT_RX = re.compile(r"из бюджета|потрат|купил|оплат|заплат|получил|пришл|зарплат", re.I)


def is_plan(note):
    return bool(PLAN_RX.search(note or "")) and not SPENT_RX.search(note or "")


def t_money_add(a, ctx):
    m = ctx.get("money")
    if m is None:
        raise ToolError("учёт денег недоступен")
    if is_plan(f"{a.get('category') or ''} {a.get('note') or ''}".strip()) or is_plan(a.get("note") or ""):
        return ("Не записано: это план (бюджет, лимит), а не трата или доход — в расходы не пишу. Запомни его как факт "
                "(remember, например «Бюджет на мебель — 65 тысяч рублей»): новое значение заменит старое и сохранит историю.")
    from money import fmt
    cur = a.get("currency") or None
    # №1101 (26.11): «12 рублей» голосом приходит как «12 ₽», и модель ставит RUB — у кого основная валюта BYN, это просто
    # «рубли»: RUB — только если человек сказал «российских» (или RUB)
    if str(cur or "").upper() == "RUB" and m.currency() == "BYN" and not re.search(r"российск|\brub\b", str((ctx.get("turn_text") or (lambda: ""))() or ""), re.I):
        cur = None
    try:
        it = m.add(a.get("kind") or "expense", a.get("amount") or 0, cur, a.get("category") or "",
                   a.get("note") or "", a.get("date") or None)
    except (TypeError, ValueError) as e:
        raise ToolError(str(e)) from e
    # №382 (28.10): «бот куда-то записал расходы, такого раздела нет, в „Платежах“ нет» — говорим, где их видно
    return (f"Записано: {'доход' if it['kind'] == 'income' else 'расход'} {fmt(it['amount'], it['currency'])}, {it['category']}, {it['date']}. "
            "Если человек спросит, где это смотреть или впервые записывает траты: студия → «Календарь» → вкладка «Деньги» "
            "(«Платежи» — это обязательные счета: свет, газ, интернет). В ответе — коротко.")


def _money_line(x):
    from money import fmt
    return f"{x['date'][8:10]}.{x['date'][5:7]} {'+' if x['kind'] == 'income' else '−'}{fmt(x['amount'], x['currency'])} {x.get('note') or x.get('category') or ''}".strip()


def t_money_find(a, ctx):
    """Идея №75 (30.10): «убрать ошибочную запись или дубль, поменять валюту — голосом нельзя». Сначала найти."""
    m = ctx.get("money")
    if m is None:
        raise ToolError("учёт денег недоступен")
    import datetime as _dt
    end = a.get("to") or a.get("date") or _dt.date.today().isoformat()
    start = a.get("from") or a.get("date") or (_dt.date.today() - _dt.timedelta(days=31)).isoformat()
    found = m.find(start, end, a.get("amount"), a.get("text") or "", a.get("currency") or "", a.get("kind") or "")
    if not found:
        return f"С {start} по {end} таких записей нет. Скажи человеку и спроси, когда это было или на какую сумму."
    return ("Найдено (id — для money_fix):\n" + "\n".join(f"{x['id']}: {_money_line(x)}" for x in found)
            + "\nДальше — money_fix с нужными id (удалить или поправить); подтверждение человек даст сам, переспрашивать не нужно."
            + (" Похожих несколько — уточни у человека, какую, если он не сказал «все»." if len(found) > 1 else ""))


def t_money_fix(a, ctx):
    m = ctx.get("money")
    if m is None:
        raise ToolError("учёт денег недоступен")
    ids = [str(i) for i in (a.get("ids") or []) if str(i).strip()][:50]
    if not ids:
        raise ToolError("нет id — сначала money_find")
    have = {x["id"]: x for x in m.list()}
    miss = [i for i in ids if i not in have]
    if miss:
        raise ToolError("таких записей нет: " + ", ".join(miss) + " — найди заново money_find")
    if (a.get("action") or "delete") == "delete":
        for i in ids:
            m.delete(i)
        return f"Удалено записей: {len(ids)}. Скажи коротко, что убрано."
    patch = {k: a[k] for k in ("amount", "currency", "category", "note", "date", "kind") if a.get(k) not in (None, "")}
    if "currency" in patch:
        patch["currency"] = str(patch["currency"]).upper()[:6]
    if not patch:
        raise ToolError("что поменять? amount, currency, category, note или date")
    for i in ids:
        m.update(i, patch)
    return "Исправлено: " + "; ".join(_money_line(x) for x in m.list() if x["id"] in ids) + ". Скажи коротко."


def t_money_report(a, ctx):
    m = ctx.get("money")
    if m is None:
        raise ToolError("учёт денег недоступен")
    import datetime as _dt
    from money import fmt
    end = a.get("to") or _dt.date.today().isoformat()
    start = a.get("from") or _dt.date.today().replace(day=1).isoformat()
    sm = m.summary(start, end)
    if not sm["count"]:
        return f"С {start} по {end} записей о деньгах нет."
    out = [f"С {start} по {end}, записей: {sm['count']}."]
    for c in sm["by_currency"]:
        out.append(f"{c['currency']}: доходы {fmt(c['income'], c['currency'])}, расходы {fmt(c['expense'], c['currency'])}, "
                   f"остаток {fmt(c['balance'], c['currency'])}. Расходы по категориям: "
                   + ", ".join(f"{x['name']} {fmt(x['sum'], c['currency'])}" for x in c["expense_cats"]) + ".")
    last = m.list(start, end)[:15]
    out.append("Последние: " + "; ".join(f"{x['date']} {'+' if x['kind'] == 'income' else '−'}{x['amount']} "
                                         f"{x['currency']} {x['note'] or x['category']}" for x in last))
    return "\n".join(out)
