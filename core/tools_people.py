"""Действия модели: люди — «Близкие», команда, клиенты и сделки."""

from pathlib import Path
from tools_base import ToolError


def t_close_send(a, ctx):
    c = ctx.get("close")
    if c is None:
        raise ToolError("«Близкие» недоступны")
    from close import CloseError
    rw = str(a.get("remind_when") or "").strip()
    try:
        files = [str(Path(x).expanduser()) for x in (a.get("files") or []) if x]
        if rw:                                       # «Лира в группе»: «напомни всем в группе Семья в субботу в 10 про дачу»
            g = c.group_of(a.get("to") or "") or c.group_match(a.get("to") or "")
            if not g:
                raise ToolError("напомнить всем можно только в группе своих — назови группу («в группу Семья»)")
            import when as W
            w = W.parse("напомни " + rw + " " + (a.get("text") or "дело"))
            if not w or not w.get("at"):
                raise ToolError(f"не понял, когда напомнить: «{rw}» — спроси у пользователя день и время")
            it = c.gsend(g["gid"], a.get("text") or "", files, remind_at=w["at"])
            return (f"Отправлено {it['to']}: у каждого участника (и у тебя) встанет напоминание на {w['at'].strftime('%d.%m %H:%M')}."
                    " Скажи коротко, что напомнишь всем.")
        it = c.send(a.get("to") or "", a.get("text") or "", files)
    except CloseError as e:
        msg = str(e)
        if msg.startswith("Не нашла"):
            # экзамен 20.11 (Б12): «Сергею Петрову, почта sp@…» — модель писала через «Близкие» (почта не подключена),
            # получала «не нашла» и не отдавала даже текст. Человек не из «Близких» — письмо или готовый текст
            m = ctx.get("mail")
            msg += (" Если это не человек из «Близких», а адрес почты — отправь письмом (send_email)." if m and m.configured()
                    else " Почта не подключена (подключить — студия → «Подключение» → «Почта»): скажи это одной фразой и "
                         "дай готовый текст целиком в ответе — человек отправит сам.")
        raise ToolError(msg) from e
    except OSError as e:
        raise ToolError(str(e)) from e
    to = it.get("to") or c.person(a.get("to") or "")["name"]          # группа («Группы своих») — «в группу «Семья»»
    return f"Отправлено {to}" + (f" (файлов: {len(it.get('f') or [])})" if it.get("f") else "") + ". Скажи коротко, что отправила."


def t_close_call(a, ctx):
    c = ctx.get("close")
    if c is None:
        raise ToolError("«Близкие» недоступны")
    from close import CloseError
    try:
        r = c.call(a.get("to") or "", bool(a.get("video")))
    except CloseError as e:
        raise ToolError(str(e)) from e
    return f"Открыла окно звонка: звоню {r['name']}. Скажи одной фразой, что звонишь."


def t_close_read(a, ctx):
    c = ctx.get("close")
    if c is None:
        raise ToolError("«Близкие» недоступны")
    from close import CloseError
    try:
        return c.recent(a.get("who") or "")
    except CloseError as e:
        raise ToolError(str(e)) from e


def _team(ctx):
    t = ctx.get("team")
    if t is None or not t.connected():
        raise ToolError("«Поручения» не подключены — студия → «Поручения»")
    return t


def t_team_assign(a, ctx):
    from team import TeamError, due_text
    try:
        r = _team(ctx).assign(a.get("who") or "", a.get("task") or "", a.get("due") or "", a.get("note") or "", via="voice")
    except TeamError as e:
        raise ToolError(str(e)) from e
    if r.get("repeat"):                                # «каждый понедельник к 18» — повторяющееся поручение
        return (f"Буду поручать {r['name_dat']} «{r['title']}» {r['rule']}; первое уйдёт само в день срока ({due_text(r['first'])}). "
                "Скажи это одной фразой.")
    due = due_text(r.get("due"))
    where = "отправила в Telegram" if r.get("sent") else "записала — уйдёт в Telegram, как только сотрудник откроет приглашение"
    return f"Поручила {r['name']}: «{r['title']}»" + (f", срок {due}" if due else "") + f"; {where}. Скажи это одной фразой."


def t_team_message(a, ctx):
    from team import TeamError
    try:
        T = _team(ctx)
        T.message(a.get("who") or "", a.get("text") or "")
    except TeamError as e:
        raise ToolError(str(e)) from e
    return "Отправила сотруднику. Скажи коротко."


def t_team_status(a, ctx):
    from team import TeamError
    try:
        return _team(ctx).summary(a.get("who") or "")
    except TeamError as e:
        raise ToolError(str(e)) from e


def _clients(ctx):
    c = ctx.get("clients")
    if c is None:
        raise ToolError("«Клиенты» выключены — студия → «Возможности» → «Клиенты»")
    return c


def t_client_note(a, ctx):
    """«Запиши: Иванов из „Ромашки“ хочет 200 коробок до пятницы» — в историю клиента (нет — карточка заводится)."""
    from clients import ClientError
    C = _clients(ctx)
    who = " ".join(x for x in (a.get("who") or "", f"«{a['company']}»" if a.get("company") else "") if x)
    try:
        before = set(C.st["clients"])
        cid = C.find(who, create=True)
        c = C.note(cid, a.get("text") or "", a.get("kind") or "note", a.get("phone") or "", a.get("email") or "")
    except ClientError as e:
        raise ToolError(str(e)) from e
    made = cid not in before
    return (f"Записала в карточку {C.title(c)}" + (" (новый клиент — карточка заведена)" if made else "") + f": «{c['log'][-1]['t']}». "
            "Скажи это одной фразой. Если в записи есть срок или «перезвонить» — предложи поставить следующий шаг (client_next).")


def t_client_info(a, ctx):
    from clients import ClientError
    C = _clients(ctx)
    try:
        return C.card_text(C.find(a.get("who") or ""))
    except ClientError as e:
        raise ToolError(str(e)) from e


def t_client_crm(a, ctx):
    """«Передай Иванова в Битрикс» — клиент лидом в CRM (crm.py); уже там — новые записи комментарием."""
    from clients import ClientError
    from crm import CrmError
    C, R = _clients(ctx), ctx.get("crm")
    if not (R and R.connected()):
        raise ToolError("CRM не подключена — студия → «Клиенты» → «CRM»")
    try:
        cid = C.find(a.get("who") or "")
        r = R.send(cid)
    except (ClientError, CrmError) as e:
        raise ToolError(str(e)) from e
    where = R.public()["name"]
    if r["new"]:
        return f"Передала {C.title(C.get(cid))} в {where} новым лидом (№{r['id']}). Скажи это одной фразой."
    return (f"В {where} у этого клиента уже есть лид №{r['id']}: " + (f"добавила новых записей — {r['n']}." if r["n"] else "новых записей нет — всё уже там.")
            + " Скажи это одной фразой.")


def t_client_next(a, ctx):
    """Следующий шаг с клиентом: что и когда; когда — напоминание в «Делах»."""
    from clients import ClientError
    from when import parse
    C = _clients(ctx)
    at = None
    w = (a.get("when") or "").strip()
    if w:
        r = parse("напомни " + w)
        if not r:
            raise ToolError(f"не поняла, когда: «{w}» — уточни день и время")
        at = r["at"]
    try:
        cid = C.find(a.get("who") or "", create=True)
        if a.get("done"):
            c = C.next_done(cid)
            return f"Отметила: следующий шаг с {C.title(c)} сделан, записано в историю."
        c = C.set_next(cid, a.get("what") or "связаться", at)
    except ClientError as e:
        raise ToolError(str(e)) from e
    from clients import _when
    return (f"Следующий шаг с {C.title(c)}: {c['next']['what']}" + (f" — {_when(c['next']['at'])}, напоминание поставлено" if at else "")
            + ". Скажи это одной фразой.")


def t_client_list(a, ctx):
    return _clients(ctx).summary(a.get("query") or "")


def t_client_deal(a, ctx):
    """Сделка: новая или движение по этапам. «Ромашке выставили счёт на 1200 за коробки, оплатить до пятницы» — счёт;
    «Ромашка оплатила» — оплачено (и в доходы, если не выключено); «Иванов отказался» — отказ."""
    from clients import ClientError
    from deals import STAGES, DealError, fmt_amount, human_date, stage_of, to_money
    C = _clients(ctx)
    stage = stage_of(a.get("stage") or "") or ""
    try:
        cid = C.find(a.get("who") or "", create=True)
        did = ""
        if not a.get("new"):
            try:
                did = C.deal_find(cid, a.get("title") or "", strict=bool(a.get("title")) and not stage_of(a.get("title") or ""))
            except DealError:
                did = ""
        if did:
            f = {k: a[k] for k in ("amount", "due") if a.get(k)}
            d = C.deal_set(cid, did, stage=stage or None, **f) if (stage or f) else next(x for x in C.deals(cid=cid) if x["id"] == did)
            made = False
        else:
            d = C.deal_add(cid, a.get("title") or "", a.get("amount") or 0, "", stage or "lead", a.get("due") or "")
            made = True
    except (ClientError, DealError) as e:
        raise ToolError(str(e)) from e
    income = ""
    s = ctx.get("settings")
    if d["stage"] == "paid" and ((s.get("clients") or {}).get("deal_income", True) if s else True) is not False:
        income = to_money(ctx.get("money"), d)
        if income:
            C.deal_set(d["cid"], d["id"], income=income)
    amt = f", {fmt_amount(d['amount'], d['cur'])}" if d.get("amount") else ""
    due = f", оплатить до {human_date(d['due'])}" if d["stage"] == "invoice" and d.get("due") else ""
    return (f"{'Новая сделка' if made else 'Сделка'} с {d['client']}: «{d['title']}» — {STAGES[d['stage']].lower()}{amt}{due}."
            + (" Записала в доходы." if income else "") + " Скажи это одной фразой.")


def t_deal_remind(a, ctx):
    """«Напомни Ромашке об оплате» — вежливое письмо клиенту о счёте (почта) или текст, чтобы отправить самому."""
    from clients import ClientError
    from deals import DealError
    C = _clients(ctx)
    try:
        cid = C.find(a.get("who") or "")
        ds = [d for d in C.deals(stage="invoice", cid=cid)]
        if not ds:
            raise ToolError("у этого клиента нет выставленных неоплаченных счетов")
        if a.get("title"):
            did = C.deal_find(cid, a.get("title") or "")
            ds = [d for d in ds if d["id"] == did] or ds
        d = ds[0]
        s = ctx.get("settings")
        me = ((s.get("close") or {}).get("name") or s.get("user_name") or "") if s else ""
        r = C.deal_remind_text(cid, d["id"], me)
    except (ClientError, DealError) as e:
        raise ToolError(str(e)) from e
    m = ctx.get("mail")
    if r["to"] and m and m.configured() and a.get("send", True) is not False:
        from mail import MailError
        try:
            m.send(r["to"], r["subject"], r["body"])
        except MailError as e:
            raise ToolError(str(e)) from e
        C.deal_reminded(cid, d["id"], "письмом")
        return f"Письмо-напоминание об оплате «{d['title']}» отправлено {r['name']} ({r['to']}). Скажи коротко."
    why = "у клиента не записана почта" if not r["to"] else "почта не подключена (студия → «Подключение» → «Почта»)"
    return (f"Отправить письмом не получилось: {why}. Вот текст — предложи отправить его в мессенджер или записать почту "
            f"клиента, и покажи текст:\n\n{r['body']}")


def t_client_deals(a, ctx):
    return _clients(ctx).deals_summary(a.get("what") or "")
