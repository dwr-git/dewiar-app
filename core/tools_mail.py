"""Действия модели: почта и сообщения — письма, Telegram, рассылка, посты в каналы."""

import re

from datetime import datetime, timedelta
from pathlib import Path
from tools_base import ToolError


def _mail(ctx):
    """Подключённая почта из ctx, иначе ToolError с подсказкой, где подключить."""
    m = ctx.get("mail")
    if not m or not m.configured():
        raise ToolError("почта не подключена — студия → «Подключение» → «Почта»")
    return m


def t_send_email(a, ctx):
    from mail import MailError
    files = a.get("attachments") or []
    if isinstance(files, str):
        files = [x.strip() for x in files.split(",") if x.strip()]
    try:
        if str(a.get("reply_to") or "").strip():          # ответ на письмо: кому, тема и цитата — сами (03.11)
            r = _mail(ctx).reply(a["reply_to"], a.get("body", ""), files)
            return f"Ответ на письмо «{r['replied']}» отправлен: {', '.join(r['to'])}" + (f"; вложения: {', '.join(r['attachments'])}" if r["attachments"] else "") + _refused(r)
        if not str(a.get("subject") or "").strip():
            raise ToolError("нужна тема письма (subject) — или reply_to, если это ответ на письмо")
        r = _mail(ctx).send(a.get("to", ""), a.get("subject", ""), a.get("body", ""), files, box=a.get("from") or None)
    except MailError as e:
        raise ToolError(str(e)) from e
    return f"Письмо «{r['subject']}» отправлено: {', '.join(r['to'])}" + (f"; вложения: {', '.join(r['attachments'])}" if r["attachments"] else "") + _refused(r)


def _refused(r):
    """№1157: адресаты, которых почта отклонила, — названы (им письмо НЕ ушло)."""
    return f". Почта отклонила: {', '.join(r['refused'])} — им письмо не ушло" if r.get("refused") else ""


def t_send_telegram(a, ctx):
    from telegram import TelegramError
    tg = ctx.get("telegram")
    if not (tg and tg.paired()):
        raise ToolError("Telegram и MAX не подключены — студия → «Подключение»")
    to = str(a.get("to") or "").lower()
    if to and hasattr(tg, "bots"):                       # назвали мессенджер — туда; не подключён — так и говорим
        # №1157 (28.11): «напиши в Telegram» при подключённом только MAX уходило в MAX — молча, не туда, куда просили
        named = [b for b in tg.bots if b.TITLE.lower() == to]
        live = next((b for b in named if b.paired()), None)
        if named and not live:
            raise ToolError(f"{named[0].TITLE} не подключён — студия → «Подключение»; отправлять в другой мессенджер не стала")
        tg = live or tg
    files = a.get("files") or []
    if isinstance(files, str):
        files = [x.strip() for x in files.split(",") if x.strip()]
    ws = ctx.get("workspace")
    sent = []
    text = (a.get("text") or "").strip()
    if text and not tg.send(text):
        raise ToolError(tg.problem or "сообщение не отправилось")
    for f in files[:10]:
        try:                                             # безопасность: отправлять можно только файлы папки ассистента
            p = ws.safe(f) if ws else Path(f)
        except Exception as e:  # noqa: BLE001
            raise ToolError(f"{f}: {e}") from e
        if not p.is_file():
            raise ToolError(f"нет файла {f} в папке ассистента")
        try:
            sent.append(tg.send_file(p))
        except TelegramError as e:
            raise ToolError(str(e)) from e
    if not text and not sent:
        raise ToolError("нечего отправлять: нужен text или files")
    where = getattr(tg, "title", None) or getattr(tg, "TITLE", "Telegram")
    return f"Отправлено в {where}" + (f": {', '.join(sent)}" if sent else "") + "."


def t_read_emails(a, ctx):
    from mail import MailError
    m = _mail(ctx)
    m.last_errs = []
    try:
        items = m.inbox(limit=max(1, min(20, int(a.get("limit") or 8))), unread=bool(a.get("unread_only")),
                        query=a.get("query", ""), box=a.get("box") or None)
    except MailError as e:
        raise ToolError(str(e)) from e
    # №1142 (28.11): ящиков несколько, один не ответил — письма второго не выдаём за «все», а говорим, какой молчит
    warn = ("Не ответил ящик " + "; ".join(getattr(m, "last_errs", None) or []) + " — его письма не видны.\n\n") if getattr(m, "last_errs", None) else ""
    if not items:
        return warn + "Писем не нашлось."
    many = len({x.get("box") for x in items}) > 1                 # несколько ящиков — у письма видно, в каком оно
    return warn + "\n".join(f"[{x['uid']}] {'● ' if x['unread'] else ''}{x['date'][:22]} · " + (f"в {x['box']} · " if many else "")
                     + f"{x['from']} · «{x['subject']}» — {x['snippet'][:160]}"
                     + (f" (вложения: {', '.join(x['files'])})" if x["files"] else "") for x in items) + \
        "\n\nЦеликом письмо — read_email с номером в скобках; ответить — send_email с reply_to=номер и текстом ответа."


def mail_table_make(mail, days=None, limit=1000, box=None, title=""):
    """Таблица .xlsx по почте -> {path, n, att, senders, top: [(адрес, писем)], limit}. Ошибки почты — MailError."""
    import email.utils as eu
    import export as X
    import xlsx_lite
    since = (datetime.now() - timedelta(days=max(1, int(days)))).date() if days else None
    limit = max(1, min(5000, int(limit or 1000)))
    items = mail.headers(limit=limit, box=box or None, since=since)
    if not items:
        return {"path": None, "n": 0, "att": 0, "senders": 0, "top": [], "limit": limit}
    many = len({x.get("box") for x in items}) > 1
    rows = [(["Ящик"] if many else []) + ["Дата", "Отправитель", "Адрес", "Тема", "Вложение", "Прочитано"]]
    stat = {}
    for x in items:
        name, addr = eu.parseaddr(x.get("from") or "")
        addr = (addr or x.get("from") or "").strip().lower()
        try:
            when = eu.parsedate_to_datetime(x.get("date") or "").strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError, IndexError, OverflowError):
            when = (x.get("date") or "")[:25]
        rows.append(([x.get("box", "")] if many else []) + [when, name or addr, addr, x.get("subject", ""), bool(x.get("attach")), not x.get("unread")])
        s_ = stat.setdefault(addr, {"name": name, "n": 0, "att": 0, "last": ""})
        s_["n"] += 1
        s_["att"] += 1 if x.get("attach") else 0
        s_["name"] = s_["name"] or name
        s_["last"] = max(s_["last"], when)
    top = sorted(stat.items(), key=lambda kv: (-kv[1]["n"], kv[0]))
    rows2 = [["Адрес", "Отправитель", "Писем", "С вложениями", "Последнее"]] + [[k, v["name"], v["n"], v["att"], v["last"]] for k, v in top]
    out = X.unique(X.downloads_dir() / X.safe_name((title or "").strip() or f"Почта {datetime.now():%d.%m.%Y}", ".xlsx"))
    xlsx_lite.write(out, [("Письма", rows), ("По отправителям", rows2)])
    return {"path": out, "n": len(items), "att": sum(1 for x in items if x.get("attach")), "senders": len(stat),
            "top": [(k, v["n"]) for k, v in top[:3]], "limit": limit}


def t_mail_table(a, ctx):
    """№541 (04.11, ПК, своя модель в LM Studio): «подготовь Excel с содержимым почтового ящика: адрес отправителя, дата,
    тема, с вложением или нет, и статистика, с какого адреса сколько писем». read_emails отдаёт до 20 писем и без поля
    «вложение», файла Excel сделать было нечем — модель выдала скрипт на Python. Теперь — одним действием: таблица .xlsx
    в «Загрузках» (лист «Письма» и лист «По отправителям»)."""
    from mail import MailError
    try:
        r = mail_table_make(_mail(ctx), a.get("days") or None, a.get("limit") or 1000, a.get("box") or None, a.get("title") or "")
    except MailError as e:
        raise ToolError(str(e)) from e
    except (TypeError, ValueError) as e:
        raise ToolError(f"неверные параметры: {e}") from e
    except OSError as e:
        raise ToolError(f"не получилось записать файл: {e}") from e
    if not r["path"]:
        return "В ящике писем не нашлось — таблицу не делаю."
    if ctx.get("made"):
        try:
            ctx["made"](str(r["path"]))
        except Exception:  # noqa: BLE001
            pass
    return (f"Готово: таблица Excel «{r['path'].name}» в папке «Загрузки» ({r['path'].parent}). Писем: {r['n']}"
            + (" (это предел — скажи, если нужно больше)" if r["n"] >= r["limit"] else "")
            + f", с вложениями: {r['att']}, отправителей: {r['senders']}. Чаще всего пишут: "
            + "; ".join(f"{k} — {n}" for k, n in r["top"]) + ". Лист «Письма» — дата, отправитель, адрес, тема, есть ли вложение, "
            "прочитано; лист «По отправителям» — сколько писем с какого адреса. Скажи это человеку коротко и назови, где файл.")


def t_read_email(a, ctx):
    from mail import MailError
    try:
        m = _mail(ctx).read(a.get("uid", ""), mark=True)    # прочитали человеку — и на почте «прочитано»
    except MailError as e:
        raise ToolError(str(e)) from e
    return (f"От: {m['from']}\nКому: {m['to']}\nТема: {m['subject']}\nДата: {m['date']}\n"
            + (f"Вложения: {', '.join(m['files'])}\n" if m["files"] else "") + "\n" + m["text"][:8000])


def t_manage_email(a, ctx):
    """№562 (05.11, Serge: «минимальное управление почтой: Удалить, В спам, Переслать»): «удали это письмо», «отправь
    в спам», «перешли Андрею». Письмо — номер из read_emails или от кого оно; удалить — в «Корзину» почты (как на сайте
    почты), в спам — в её «Спам»; переслать — целиком, с вложениями (исходное письмо — вложением .eml)."""
    from mail import MailError
    act = {"delete": "trash", "trash": "trash", "spam": "junk", "junk": "junk", "forward": "forward"}.get(str(a.get("action") or "").lower())
    if not act:
        raise ToolError("action: delete, spam или forward")
    if act == "forward" and not str(a.get("to") or "").strip():
        raise ToolError("кому переслать? Нужен адрес (to); по имени — из памяти о пользователе, а нет его там — спроси")
    try:
        r = _mail(ctx).manage(a.get("uid", ""), act, a.get("to", ""), a.get("note", ""))
    except MailError as e:
        raise ToolError(str(e)) from e
    if act == "forward":
        return f"Письмо «{r['forwarded']}» переслано: {', '.join(r['to'])} (целиком, с вложениями)."
    if act == "junk":
        return f"Письмо убрано в «{r['folder']}». Скажи коротко, что оно в спаме."
    return ("Письмо удалено совсем: корзины в этой почте нет." if r["permanent"]
            else f"Письмо убрано в «{r['folder']}» — его можно вернуть оттуда на сайте почты. Скажи коротко.")


def _mailing(ctx):
    m = ctx.get("mailing")
    if m is None:
        raise ToolError("рассылка недоступна")
    return m


def t_mailing(a, ctx):
    """«Разошли всем клиентам…», «напиши всем сотрудникам письмо…» — каждому своё письмо (mailing.py)."""
    from mailing import MailingError
    m = _mailing(ctx)
    try:
        d = m.draft(a.get("subject") or "", a.get("body") or "", a.get("recipients") or "list", a.get("list") or "",
                    a.get("tag") or "", a.get("kind") or "work")
        m.start(d["id"])
    except MailingError as e:
        raise ToolError(str(e)) from e
    sk = d.get("skipped") or {}
    extra = (f"; отписавшихся пропускаю: {sk['stop']}" if sk.get("stop") else "") + (f"; повторы убрала: {sk['dup']}" if sk.get("dup") else "")
    from mailing import plain
    return (f"Рассылка «{plain(d['subject'])}» пошла: {d['total']} писем, каждому своё, по одному с паузой{extra}. Итог пришлю, "
            "ход — в студии → «Рассылка». Скажи это одной фразой.")


def t_mailing_status(a, ctx):
    ls = _mailing(ctx).list()
    if not ls:
        return "Рассылок ещё не было."
    st = {"draft": "черновик", "sending": "идёт", "waiting": "ждёт завтра (дневной предел почты)", "done": "закончена",
          "stopped": "остановлена", "paused": "на паузе"}
    from mailing import plain
    return "\n".join(f"«{plain(c['subject'])}»: {st.get(c['status'], c['status'])}, ушло {c['sent']} из {c['total']}"
                     + (f", не дошло {c['failed']}" if c["failed"] else "") for c in ls[:5])


def _post_target(P, name):
    """«в канал Чайный двор» -> id чата бота; пусто — первый, где можно публиковать."""
    cs = [c for c in P.chats() if c["can"]]
    n = (name or "").strip().lower().lstrip("@")
    if not n:
        return [cs[0]["id"]] if cs else []
    hit = [c["id"] for c in cs if n in c["title"].lower() or (c["username"] and n == c["username"].lower())]
    if not hit:
        raise ToolError("бот не состоит в «" + name + "». Есть: " + (", ".join(c["title"] for c in cs) or "ничего — добавьте бота в канал"))
    return hit[:1]


def t_channel_post(a, ctx):
    """«Опубликуй в канале…», «запланируй пост на завтра в 10», «сделай опрос в группе» — от имени бота персонажа."""
    from pbot_posts import PostError
    from when import parse
    P = ctx.get("pbot_posts")
    if P is None or not P.bot.connected():
        raise ToolError("бот персонажа не подключён — студия → «Бот в Telegram»")
    at = None
    w = (a.get("when") or "").strip()
    if w and not re.search(r"^(сейчас|сразу)$", w, re.I):
        r = parse("напомни " + w)
        if not r:
            raise ToolError(f"не поняла, когда: «{w}» — уточни день и время")
        at = r["at"]
    poll = {"question": a.get("poll_question"), "options": a.get("poll_options") or []} if a.get("poll_question") else None
    try:
        p = P.add(a.get("text") or "", _post_target(P, a.get("chat") or ""), at, poll, source="voice")
    except PostError as e:
        raise ToolError(str(e)) from e
    where = ", ".join(c["title"] for c in P.chats() if c["id"] in p["chats"])
    if p["status"] == "sent":
        return f"Опубликовала в «{where}»." + (" Ссылка: " + p["sent"][0]["link"] if p["sent"] and p["sent"][0]["link"] else "") + " Скажи коротко."
    if p["status"] == "failed":
        raise ToolError("Telegram не принял пост: " + p["err"])
    from clients import _when
    return f"Запланировала пост в «{where}» — {_when(p['at'])}. Скажи это одной фразой."
