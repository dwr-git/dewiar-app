"""Действия без модели (часть Engine, чистое ядро 1.0.16): «сколько времени», план дня, «удали задачу», «я позвонил
в банк», звонок и сообщение близким, YouTube, черновик книги, таблица почты, таймеры, заметка или факт сразу
(_capture), ответ одной фразой (_say_quick)."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from acts_base import DRAFT_KINDS, DRAFT_RX


class QuickMixin:
    def _reminder_time_guard(self, asked, args):
        """«Через 20 минут / через полчаса / через 2 часа» — время считаем сами от часов компьютера, а не берём у модели:
        модель могла посчитать от старого времени из разговора (16.10: «сколько времени» — «14:17» в 15:57). Остальное
        (when словами) и так разбирает when.parse по настоящим часам. -> аргументы (исправленные или те же)."""
        said = asked.split("\n\nВложения:", 1)[0]
        if not re.search(r"(?<![а-яё])через\s+(?:\S+\s+){0,3}?(?:секунд|минут|час|полчаса|полтора)", said, re.I) or re.search(r"кажд", said, re.I):
            return args
        from when import parse
        r = parse(said) or parse("напомни " + said)
        if not r or r.get("repeat") or not r.get("at"):
            return args
        mine = r["at"]
        theirs = None
        try:
            from tools import _when
            theirs = _when(args)[0]
        except Exception:  # noqa: BLE001
            pass
        if theirs is not None and abs((theirs - mine).total_seconds()) <= 90:
            return args
        log.warning("🕒 Напоминание: модель поставила %s, а «%s» — это %s; ставлю по часам",
                    theirs and f"{theirs:%d.%m %H:%M}", said[:60], f"{mine:%d.%m %H:%M}")
        out = {k: v for k, v in args.items() if k not in ("when", "in_minutes", "at")}
        out["at"] = f"{mine:%Y-%m-%d %H:%M}"
        return out

    def _clock_cmd(self, text, via=None):
        """«Сколько времени?», «который час?», «какое сегодня число?» — по часам компьютера, без модели (16.10: модель
        ответила «14:17», когда было 15:57 — повторила время из своего прошлого ответа в разговоре). На телефоне — quick()."""
        from engine_base import MONTHS, WEEKDAYS
        t = re.sub(r"[?!.,]+", " ", (text or "").lower().replace("ё", "е"))
        t = re.sub(r"\s+", " ", t).strip()
        t = re.sub(r"^[а-я]+ (?=(?:а |скажи |подскажи )?(?:сколько|который|какое|какой|какая|время)\b)", "", t)   # «Лира, …»
        t = re.sub(r"^(?:а |скажи |подскажи )+|(?: (?:пожалуйста|подскажи|скажи))+$", "", t).strip()
        now = datetime.now()
        if re.fullmatch(r"(?:сколько (?:сейчас )?(?:времени|время)|который (?:сейчас )?час|сколько (?:сейчас )?на часах|время|"
                        r"(?:сколько|который) (?:сейчас )?(?:времени|час) (?:сейчас|у нас))", t):
            self._say_quick(f"Сейчас {now:%H:%M}.", text, via)
            return True
        if re.fullmatch(r"(?:какое|какой|какая) (?:сегодня|сейчас) (?:число|день(?: недели)?|дата)|(?:какое|какая) (?:число|дата) (?:сегодня|сейчас)|"
                        r"какой (?:сегодня )?день недели", t):
            self._say_quick(f"Сегодня {WEEKDAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]}.", text, via)
            return True
        # «сколько сейчас времени в Омске» — по часовому поясу, а не модель «в уме» (№131: вычла 3 часа вместо прибавления)
        m = re.fullmatch(r"(?:сколько (?:сейчас )?(?:времени|время)|который (?:сейчас )?час|какое (?:сейчас )?время)(?: сейчас)? (в|во) "
                         r"([а-я][а-я -]{1,30}?)(?: сейчас)?", t)
        if m:
            from tools import world_time
            city = re.sub(r"(^|[ -])([а-я])", lambda x: x.group(1) + x.group(2).upper(), m.group(2))
            said = world_time(city, geocode=False, prep=m.group(1)) or world_time(city, prep=m.group(1))
            if said:
                self._say_quick(said, text, via)
                return True
        return False

    def _plan_cmd(self, text, via=None):
        """План дня без модели (отзыв 17.10: «Запланируй на сегодня: в 13 позвонить в банк, в 16 тренировка…» — модель
        отвечала «записала» и писала в календарь, а в «Делах» пусто): на каждое дело — напоминание (dayplan.parse_plan)."""
        import dayplan
        p = dayplan.parse_plan(text)
        if not p:
            return False
        acts = []
        for x in p["items"]:
            item = self.reminders.add(x["at"], x["text"], None, "reminder")
            self.emit("reminder_set", item=self._reminder_public(item), text="")
            self.emit("tool", name="set_reminder", title="Напоминание", status="done", args={"text": x["text"], "at": f"{x['at']:%Y-%m-%dT%H:%M}"},
                      detail=x["text"], result=f"{x['at']:%d.%m %H:%M} — {x['text']}")
            acts.append("set_reminder")
        log.info("🗓 План дня (без модели): %s", "; ".join(f"{x['at']:%d.%m %H:%M} {x['text']}" for x in p["items"]))
        self._say_quick(dayplan.plan_say(p), text, via, acts=acts)
        return True

    def _task_del_cmd(self, text, via=None):
        """«Удали задачу „Исследование“» — сразу, без модели (экзамен 25.10: модель искала заметки и стёрла файлы,
        а задача осталась; ответила «Удалил»). Нашлась ровно одна задача и у неё нет готовых файлов — удаляем; есть
        файлы или не нашлась — решает модель (спросит, сохранить ли результат)."""
        m = self.TASK_DEL_RX.match((text or "").strip())
        tm = getattr(self, "tasks", None)
        if not m or tm is None:
            return False
        name = m.group("name").strip()
        found = [t for t in tm.tasks.values() if name.lower() in t.title.lower()]
        if len(found) != 1 or found[0].data.get("outputs"):
            return False
        t = found[0]
        title = t.title
        tm.delete(t.id)
        res = f"Задача «{title}» удалена — напоминаний о ней больше не будет."
        self.emit("tool", name="remove_task", title="Задачи: удалить", status="done", args={"name": name}, detail=title, result=res)
        log.info("🗑 Задача удалена (без модели): %s", title)
        self._say_quick(f"Удалил задачу «{title}».", text, via, acts=["remove_task"])
        return True

    def _mark_cmd(self, text, via=None):
        """«Я позвонил в банк», «готово, купил подарок маме», «отметь тренировку» — отметка без модели (отзыв 17.10: для
        съёмки геймификации). Без «отметь / готово» — только если каждое дело совпало с напоминанием из плана."""
        import dayplan
        import done as D
        d = dayplan.parse_done(text)
        if not d:
            return False
        rem = list(self.reminders.items)
        hits = [D.reminder_match(t, rem, ahead=True) for t in d["items"]]
        if not d["explicit"] and not all(hits):
            return False
        lst, closed = [], []
        for t, m in zip(d["items"], hits):
            if m:
                if not m.get("repeat"):
                    self.reminders.remove(m["id"])
                    closed.append(m.get("text") or "")
                else:
                    self.reminders.done_round(m["id"])
                lst.append({"title": m.get("text") or t, "rid": m["id"]})
            else:
                lst.append({"title": t})
        r = self.done.add(lst, "voice")
        self.emit("tool", name="mark_done", title="Дела: сделано", status="done", args={"items": [x["title"] for x in lst]},
                  detail=", ".join(x["title"] for x in lst), result=f"сегодня сделано {r['stats']['today']}")
        self.emit("done", **self.done.public(), fresh=[{"icon": x[3], "name": x[4], "what": x[5]} for x in r["fresh"]], mile=r["mile"],
                  added=[x["title"] for x in r["items"]])
        log.info("✓ Сделано (без модели): %s", "; ".join(x["title"] for x in r["items"]))
        self._say_quick(dayplan.done_say(r, closed), text, via, acts=["mark_done"])
        return True

    def _call_cmd(self, text, via=None):
        """«Позвони Людмиле (по видео)», «набери маме» — человеку из «Близких» звоним сразу, без модели (съёмка 17.10:
        раз позвонила, потом раз за разом «Звоню Людмиле.» — и ничего: модель повторяла прошлый ответ, не вызывая звонка).
        Нет такого человека в «Близких» — решает модель (телефонная книга, мессенджеры). -> обработано ли."""
        t = re.sub(r"[?!.,]+", " ", (text or "").lower().replace("ё", "е"))
        t = re.sub(r"\s+", " ", t).strip()
        m = re.fullmatch(r"(?:[а-я]+ )?(?:пожалуйста )?(?:позвони|набери|звякни|сделай (?:видео)?звонок|видеозвонок)(?: мне)?"
                         r" (?P<who>.+?)(?P<video> (?:по )?(?:видео(?:связи|звонку)?|видеосвязи))?(?: пожалуйста)?", t)
        if not m or getattr(self, "close", None) is None or len(m.group("who").split()) > 3:
            return False
        from close import CloseError
        try:
            p = self.close.person(m.group("who"))
        except CloseError:
            return False
        video = bool(m.group("video"))
        tool_ev = self.emit
        args = {"to": p["name"], "video": video}
        tool_ev("tool", name="close_call", title="Близкие: позвонить", status="run", args=args, detail=p["name"])   # видно в виджете и экзамене
        log.info("🛠  close_call %s (быстро, без модели)", json.dumps(args, ensure_ascii=False))
        try:
            r = self.close.call(p["pid"], video)
        except CloseError as e:
            tool_ev("tool", name="close_call", title="Близкие: позвонить", status="error", error=str(e))
            self._say_quick(f"Не получилось позвонить: {e}", text, via)
            return True
        tool_ev("tool", name="close_call", title="Близкие: позвонить", status="done", detail=p["name"], result=f"звоню {r.get('name')}")
        orig = re.search(r"\s+".join(map(re.escape, m.group("who").split())), (text or "").replace("ё", "е").replace("Ё", "Е"), re.I)
        who = orig.group(0) if orig else m.group("who")                          # как сказал человек: «Людмиле», «маме»
        self._say_quick(f"Звоню {who}" + (" по видео." if video else "."), text, via, acts=["close_call"])
        return True

    def _youtube_cmd(self, text, via=None):
        """«Включи смешное видео на YouTube», «найди на ютубе лекцию про …» — сразу play_youtube, без модели (съёмка 17.10:
        раз сработало, потом раз за разом «Включаю.» — и ничего: модель повторяла прошлый ответ, не вызывая действие)."""
        t = re.sub(r"[?!.,«»\"]+", " ", (text or "").lower().replace("ё", "е"))
        t = re.sub(r"\s+", " ", t).strip()
        yt = r"(?:ютуб[еау]?|ютьюб[еау]?|youtube|you tube)"
        m = (re.fullmatch(rf"(?:[а-я]+ )?(?:пожалуйста )?(?:включи|поставь|найди|открой|покажи)(?: мне)? (?P<q>.+?) (?:на|в|с|из) {yt}(?: пожалуйста)?", t)
             or re.fullmatch(rf"(?:[а-я]+ )?(?:пожалуйста )?(?:включи|поставь|найди|открой|покажи)(?: мне)? (?:на|в) {yt} (?P<q>.+?)(?: пожалуйста)?", t))
        if not m:
            return False
        q = re.sub(r"\b(?:какое-нибудь|какой-нибудь|какую-нибудь|что-нибудь|какое-то|какой-то|мне|нам)\b", " ", m.group("q"))
        q = re.sub(r"^\s*(?:еще|ещё)\s+(?:одно|один|одну|какое|какой|какую)?\s*|^\s*(?:другое|другой|другую|новое|новый|новую)\s+", "", q)   # «ещё одно смешное видео» — ищем «смешное видео»
        q = re.sub(r"\s+", " ", q).strip()
        if not q or len(q) > 120:
            return False
        import tools as T
        self.emit("tool", name="play_youtube", title="YouTube: включить", status="run", args={"query": q}, detail=q)
        log.info("🛠  play_youtube %s (быстро, без модели)", q)
        try:
            res = T.t_play_youtube({"query": q}, {})
        except Exception as e:  # noqa: BLE001
            self.emit("tool", name="play_youtube", title="YouTube: включить", status="error", error=str(e))
            self._say_quick(f"Не получилось открыть YouTube: {e}", text, via)
            return True
        self.emit("tool", name="play_youtube", title="YouTube: включить", status="done", detail=q, result=str(res)[:300])
        say = str(res).replace("Открыл поиск", "Открываю поиск").replace("Открыл на", "Включаю на")
        self._say_quick(say, text, via, acts=["play_youtube"])
        return True

    def _open_link_cmd(self, text, via=None):
        """«Открой в браузере», «открой ссылку», «открой её» — сразу после ответа со ссылкой: открываем ЭТУ ссылку, без модели
        (26.11, владелец: Лира нашла в заметке ссылку на оплату, «Открой в браузере» — модель вызвала show_page, сделала
        страницу-файл, и та открылась в редакторе кода, а не в браузере). Ссылок в ответе нет или их несколько — к модели."""
        t = re.sub(r"[?!.,«»\"]+", " ", (text or "").lower().replace("ё", "е"))
        t = re.sub(r"\s+", " ", t).strip()
        if not re.fullmatch(r"(?:да |давай |ага |пожалуйста )?(?:открой|открывай|открыть|перейди)(?: (?:ее|его|ссылку|эту ссылку|страницу|"
                            r"эту страницу|ее в браузере|его в браузере|это|в браузере|по ссылке))*(?: пожалуйста)?", t):
            return False
        last = next((m.get("content") for m in reversed(self.history[-4:]) if m.get("role") == "assistant" and isinstance(m.get("content"), str)), "")
        urls = list(dict.fromkeys(u.rstrip(".,;:!?)»") for u in re.findall(r"https?://[^\s<>«»\"'`]+", last or "")))
        if len(urls) != 1:
            return False
        import tools as T
        url = urls[0]
        self.emit("tool", name="open_url", title="Открыть ссылку", status="run", args={"url": url}, detail=url)
        log.info("🛠  open_url %s (ссылка из прошлого ответа, без модели)", url[:120])
        try:
            T.t_open_url({"url": url}, {})
        except Exception as e:  # noqa: BLE001
            self.emit("tool", name="open_url", title="Открыть ссылку", status="error", error=str(e))
            self._say_quick(f"Не получилось открыть ссылку: {e}", text, via)
            return True
        self.emit("tool", name="open_url", title="Открыть ссылку", status="done", detail=url)
        host = re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0]
        self._say_quick(f"Открываю в браузере: {host}.", text, via, acts=["open_url"])
        return True

    def _send_cmd(self, text, via=None):
        """«Отправь Людмиле сообщение: «Привет»», «Напиши Андрею: …», «Отправь сообщение Лёхе. Лёха, привет!» — человеку из
        «Близких» отправляем сразу, без модели (съёмка 17.10: «каждый раз говорит, что отправила, — и ничего»: модель
        повторяла «Отправила …» из разговора, не вызывая отправку). Каждое слово адресата должно указывать на этого
        человека (иначе «письмо Андрею» ушло бы в «Близкие»); почта, Telegram, WhatsApp, SMS — решает модель."""
        m = self._SEND_RX.match(text or "")
        if not m and getattr(self, "close", None) is not None:
            m = self._send_loose(text or "")             # как пишет распознавание: без двоеточия, имя впереди
        if not m or getattr(self, "close", None) is None or re.search(r"почт|письм|e-?mail|телеграм|telegram|whatsapp|вотсап|ватсап|"
                                                                      r"вайбер|viber|смс|sms|эсэмэс|max\b|макс\b", text or "", re.I):
            return False
        from close import CloseError, match_name
        who = (m.group("who") if hasattr(m, "group") else m["who"]).strip()
        try:
            p = self.close.person(who)
        except CloseError:
            g = self.close.group_match(who) if re.match(r"(?:в\s+)?(?:групп|чат)", who, re.I) else None   # «напиши в группу Семья: …»
            if not g:
                return False
            p = {"pid": g["gid"], "name": f"группу «{g['name']}»"}
            who = "в " + p["name"]
        if not p["pid"].startswith("g") and any(match_name(w, [p]) is not p for w in who.split()):
            return False
        msg = (m.group("msg") if hasattr(m, "group") else m["msg"]).strip().strip("«»\"„“ ").strip()
        msg = re.sub(r"[»\"“]\s*\.?$", "", msg).strip()
        if not msg or len(msg) > 2000:
            return False
        msg = msg[:1].upper() + msg[1:]
        tool_ev = self.emit
        args = {"to": p["name"], "text": msg}
        tool_ev("tool", name="close_send", title="Близкие: написать", status="run", args=args, detail=p["name"])
        log.info("🛠  close_send %s (быстро, без модели)", p["name"])                       # текст сообщения — не в журнал
        try:
            self.close.send(p["pid"], msg)
        except CloseError as e:
            tool_ev("tool", name="close_send", title="Близкие: написать", status="error", error=str(e))
            self._say_quick(f"Не получилось отправить: {e}", text, via)
            return True
        tool_ev("tool", name="close_send", title="Близкие: написать", status="done", detail=p["name"], result=f"отправлено {p['name']}")
        self._say_quick(f"Отправил {who}.", text, via, acts=["close_send"])        # в роде персонажа — _g
        return True

    def _send_loose(self, text):
        """«отправь сообщение андрею привет как дела», «а теперь лёхе напиши во сколько встречаемся» — распознавание речи
        не ставит двоеточий (экзамен «как в жизни», 18.10). Адресат — первые 1–3 слова, если это человек из «Близких»
        (каждое слово — про него); остальное — текст. -> {"who", "msg"} или None."""
        from close import CloseError, match_name
        t = re.sub(r"\s+", " ", text).strip()
        cand = []
        m = re.match(r"^(?:[А-ЯЁа-яё]+\s*,\s*)?(?:(?:а|и)\s+)?(?:теперь\s+)?(?:пожалуйста\s+)?(?:отправь|напиши|передай|скинь)(?:\s+пожалуйста)?"
                     r"(?:\s+сообщение)?\s+(?P<rest>.+)$", t, re.I)
        if m:
            w = m.group("rest").split(" ")
            cand += [(" ".join(w[:k]), " ".join(w[k:])) for k in (3, 2, 1) if len(w) > k]
        m = re.match(r"^(?:(?:а|и)\s+)?(?:теперь\s+)?(?P<who>[А-ЯЁа-яё-]+(?:\s+[А-ЯЁа-яё-]+)?)\s+(?:напиши|отправь|передай)\s+(?P<msg>.+)$", t, re.I)
        if m and re.search(r"[еюиу]$", m.group("who").lower()):       # «лёхе напиши» — кому (дательный), а не «Андрей, напиши стих»
            cand.append((m.group("who"), m.group("msg")))
        for who, msg in cand:
            try:
                p = self.close.person(who)
            except CloseError:
                continue
            if all(match_name(x, [p]) is p for x in who.split()) and msg.strip():
                return {"who": who, "msg": msg}
        return None

    def _draft_cmd(self, text, via=None):
        """«Лира, запиши в книгу: герой проснулся рано утром…» — дословно, без модели, в конец заметки «Заметки/Черновики/Книга»
        со временем (идеи пользователей 24.10: «отдельная папка для голосовых — пишу книгу, статью, стихи»). Модель не
        переписывает слова автора; разбирать и собирать черновик потом — в блокноте ИИ-правкой. -> True, если это оно."""
        m = DRAFT_RX.match((text or "").strip())
        if not m:
            return False
        kind = m.group("kind").lower().replace("ё", "е")
        title = (m.group("name") or "").strip() or next(v for k, v in DRAFT_KINDS if kind.startswith(k))
        body = m.group("body").strip()
        body = body[:1].upper() + body[1:]
        if body[-1:] not in ".!?…»\"":
            body += "."
        try:
            self.workspace.save_note(title, body, folder="Черновики", append=True)
        except Exception as e:  # noqa: BLE001
            if "заперта" in str(e):                   # 05.11: черновик заперт — так и говорим, модель не зовём
                self._say_quick(f"Заметка «{title}» заперта — сначала откройте замок.", text, via)
                return True
            log.warning("черновик: %s", e)
            return False
        n = len(body.split())
        w = "слово" if n % 10 == 1 and n % 100 != 11 else "слова" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "слов"
        acc = {"Книга": "Книгу", "Статья": "Статью", "Песня": "Песню", "Сказка": "Сказку"}.get(title, title)   # «в «Книгу»»
        self._say_quick(f"Записала в «{acc}» — {n} {w}.", text, via)
        return True

    def _mail_table_cmd(self, text, via=None):
        """№541 (04.11): «подготовь Excel с содержимым почтового ящика: отправитель, дата, тема, с вложением или нет,
        статистика по адресам». Своя модель отвечала по 200 с и вместо файла выдала скрипт на Python. Просьба ясная —
        делаем без модели (mail_table): таблица в «Загрузках» и короткий ответ. -> True, если это оно."""
        t = (text or "").strip()
        if len(t) > 400 or not self.MAIL_TABLE_RX.search(t) or re.search(r"отправ\w*\s+(?:по\s+почте|письм)|рассыл", t, re.I):
            return False
        m = getattr(self, "mail", None)
        if m is None or not m.configured():
            return False                                   # почты нет — пусть модель объяснит, как подключить
        days = None
        md = re.search(r"за\s+(?:последн\w+\s+)?(\d+)\s*(дн|день|недел|месяц)", t, re.I)
        if md:
            days = int(md.group(1)) * {"дн": 1, "ден": 1, "нед": 7, "мес": 30}[md.group(2)[:3].lower()]
        elif re.search(r"за\s+(?:последн\w+\s+)?(?:недел)", t, re.I):
            days = 7
        elif re.search(r"за\s+(?:последн\w+\s+)?месяц", t, re.I):
            days = 30
        self.emit("heard", text=t)
        self.set_state("thinking")

        def run():
            from tools import mail_table_make
            try:
                r = mail_table_make(m, days)
                if not r["path"]:
                    msg = "В ящике писем не нашлось — таблицу не делала."
                else:
                    msg = (f"Готово: таблица «{r['path'].name}» в «Загрузках». Писем — {r['n']}"
                           + (" (первые тысяча — скажите, если нужно больше)" if r["n"] >= r["limit"] else "")
                           + f", с вложениями — {r['att']}, отправителей — {r['senders']}. Второй лист — сколько писем с какого адреса.")
                    try:
                        import export as X
                        if not os.environ.get("DEWIAR_DRY_TOOLS"):
                            X.reveal(r["path"])          # показать файл в папке — искать не придётся
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as e:  # noqa: BLE001
                msg = f"Таблицу по почте сделать не получилось: {e}."
            self._say_quick(msg, t, via)
        threading.Thread(target=run, name="mail-table", daemon=True).start()
        return True

    def _timer_cmd(self, text, via=None):
        """Таймеры голосом, без модели: «сколько осталось (на таймере)?», «добавь минуту / ещё 5 минут к таймеру»,
        «отмени / выключи таймер». Таймеров нет — False (решает модель: «сколько осталось до Нового года» — не сюда)."""
        t = re.sub(r"[?!.,]+", " ", (text or "").lower().replace("ё", "е"))
        t = re.sub(r"^\s*[а-я]+\s+(?=(?:сколько|добав|продли|отмени|выключи|останови|убери|сбрось|еще)\b)", "", t.strip())   # «Лира, …»
        t = re.sub(r"\s+", " ", t).strip()
        timers = sorted((x for x in self.reminders.items if x.get("kind") == "timer" and not x.get("paused")), key=lambda x: x["at"])
        if not timers:
            return False
        now = datetime.now()
        left = lambda x: max(0, int((datetime.fromisoformat(x["at"]) - now).total_seconds()))   # noqa: E731

        def dur(sec, acc=False):
            """-> «4 минуты 29 секунд»; acc — винительный («добавил минуту»)."""
            m, s_ = divmod(sec, 60)
            h, m = divmod(m, 60)
            w = lambda n, a, b, c: f"{n} " + (a if n % 10 == 1 and n % 100 != 11 else b if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else c)  # noqa: E731
            parts = ([w(h, "час", "часа", "часов")] if h else []) + ([w(m, "минуту" if acc else "минута", "минуты", "минут")] if m else []) + \
                    ([w(s_, "секунду" if acc else "секунда", "секунды", "секунд")] if s_ and not h and m < 10 else [])
            out = " ".join(parts) or "меньше секунды"
            return re.sub(r"^1 (минуту|секунду|час)$", r"\1", out) if acc else out
        if re.fullmatch(r"(?:а )?(?:сколько (?:еще |там )?(?:осталось|остается|времени осталось|минут осталось)(?: (?:на|до|у) таймер[а-я]*)?"
                        r"|сколько (?:там )?на таймере|сколько (?:еще|там)|что (?:там )?с таймером|таймер сколько)", t) \
                or (re.search(r"таймер", t) and re.search(r"сколько|осталось", t)):
            if len(timers) == 1:
                msg = f"Осталось {dur(left(timers[0]))}."
            else:
                msg = "Осталось: " + "; ".join(f"{(x.get('text') or 'таймер')[:1].lower()}{(x.get('text') or 'таймер')[1:]} — {dur(left(x))}" for x in timers[:3]) + "."
            self._say_quick(msg, text, via)
            return True
        m = re.fullmatch(r"(?:добавь|прибавь|продли(?: таймер)?(?: на)?|накинь|еще)(?: еще)? (\d+|одну|минуту|две|три|пять|десять|полминуты)?\s*"
                         r"(минут[уы]?|секунд[уы]?)?(?: (?:к|на|в) таймер[а-я]*| таймер[а-я]*)?", t)
        if m and (m.group(1) or m.group(2)) and ("таймер" in t or re.match(r"(?:добавь|прибавь|накинь)", t) or (t.startswith("еще") and (m.group(2) or m.group(1) in ("минуту", "полминуты")))):
            words = {"одну": 1, "минуту": 1, "две": 2, "три": 3, "пять": 5, "десять": 10}
            n = 30 if m.group(1) == "полминуты" else int(m.group(1)) if (m.group(1) or "").isdigit() else words.get(m.group(1) or "минуту", 1)
            sec = n if (m.group(2) or "").startswith("секунд") else n * 60
            x = timers[0]
            new_at = datetime.fromisoformat(x["at"]) + timedelta(seconds=sec)
            self.reminders.update(x["id"], {"at": new_at.replace(microsecond=0).isoformat(timespec="seconds")})
            self._say_quick(f"Добавил {dur(sec, True)}. Теперь осталось {dur(left(dict(x, at=new_at.isoformat())))}.", text, via)
            return True
        if re.fullmatch(r"(?:отмени|выключи|останови|убери|сбрось|удали)(?: все)? таймер[а-я]*", t):
            gone = timers if " все " in f" {t} " or len(timers) == 1 else timers[:1]
            for x in gone:
                self.reminders.remove(x["id"])
            self._say_quick("Таймер отменён." if len(gone) == 1 else f"Отменил таймеры: {len(gone)}.", text, via)
            return True
        return False

    def _capture(self, c, said, via=None):
        """Заметка, пункт списка или факт о пользователе — сразу в папку ассистента, без модели."""
        try:
            if c["op"] == "note":
                rel = self.workspace.save_note(c["title"], c["text"])
                msg = f"Записал: «{c['title']}»."
                card = {"kind": "note", "title": c["title"], "path": rel, "text": c["text"]}
            elif c["op"] == "list":
                rel, new = self.workspace.list_add(c["name"], c["items"])
                msg = (f"Добавил в «{c['name']}»: {', '.join(new)}." if new else f"Это уже есть в «{c['name']}».")
                card = {"kind": "list", "title": c["name"], "path": rel, "text": ", ".join(c["items"])}
            else:
                msg = self.workspace.remember(c["fact"])
                if c.get("day") and msg != "Это я уже знаю.":     # план с датой — назвать её: человек сразу слышит, как поняли
                    from when import human
                    day = re.sub(r",?\s+в\s+\d{1,2}:\d\d$", "", human(datetime.combine(c["day"], datetime.min.time())))
                    msg = f"Запомнил — {day}."
                rel = "Память/Обо мне.md"
                card = {"kind": "fact", "title": "Память о вас", "path": rel, "text": c["fact"]}
        except WorkspaceError as e:
            if "заперта" in str(e):                   # 05.11: список заперт — честно, без модели
                self._say_quick(f"Заметка «{c.get('name') or c.get('title')}» заперта — сначала откройте замок.", said, via)
                return True
            log.info("Быстрая заметка не записалась (%s) — спрошу модель", e)
            return False
        log.info("📝 %s → %s", c["op"], rel)
        self.emit("note_saved", **card)
        self._say_quick(msg, said, via)
        return True

    def _say_quick(self, msg, said, via=None, then=None, note=None, acts=None, keep=True):
        """Ответить одной фразой без модели (поставил напоминание, записал заметку) и запомнить в разговоре.
        then() — когда фраза сказана (и если её не перебили): «спрячься» прячет виджет уже после «Прячусь».
        note — как получен ответ (расчёт с числами): только в историю, чтобы на «как ты посчитал?» модель знала."""
        msg = self._g(msg)                                  # в роде персонажа: «Выключила музыку»
        log.info("⚡ %s → %s", redact(said), redact(msg))      # быстрый ответ без модели — тоже в журнал
        self._last_quick = (said, time.monotonic())          # «а теперь?» / «ещё раз» сразу после — повторить (engine_answer.ask)
        if via:
            via["done"](msg)
            # из мессенджера — тоже в разговор: иначе на «а теперь?» модель не знает, о чём речь (24.10)
            self.history += [{"role": "user", "content": said}, {"role": "assistant", "content": msg, "who": self.s.get("persona")}]
            self._conv_after()
            return
        self.emit("heard", text=said)
        self.emit("answer", text=msg, done=True)
        q = queue.Queue()
        q.put(msg)
        q.put(None)
        with self._turn_lock:
            self._cancel_locked()
            self.turn_n += 1
            turn = Turn(self.turn_n)
            self.turn = turn
        if keep:                                         # keep=False — ход игры («Морской бой»): в разговор не пишем
            # в разговор — сразу, а не после озвучки (экзамен ПК 0.81.1: «17% от 2350 — 399,5», следующий вопрос «объясни, как
            # посчитал» пришёл раньше, чем фраза договорилась, — и модель ответила «я ничего не считал, мы только начали»)
            self.history += [{"role": "user", "content": said}, {"role": "assistant", "content": msg + (f" (Расчёт: {note}.)" if note else ""),
                                                             "who": self.s.get("persona"), **({"acts": list(acts)} if acts else {})}]
            self._conv_after()

        def run():
            self._speak_worker(turn, q)
            with self._turn_lock:
                if self.turn is turn:
                    self.turn = None
                    self.set_state("idle")
            if then and not turn.cancel.is_set():
                then()
        threading.Thread(target=run, daemon=True).start()
