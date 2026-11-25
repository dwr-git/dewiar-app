"""Команды окон (студия, виджет, телефон): умный дом, Home Assistant, календари, сейф, резервные копии, почта, курс, справка, объявления и
новости, дела и напоминания, «Утро», платежи, деньги, Obsidian, серверы, MAX, письма, посты в каналы.
Часть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки
проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class ServicesCommands:
    def _cmd_services(self, cmd, a):
        if cmd.startswith("home_"):              # умный дом Яндекса
            from smarthome import HomeError
            try:
                if cmd == "home_get":
                    return self.home.public()
                if cmd == "home_connect":
                    from smarthome import CLIENT_ID_RX
                    tok = (a.get("token") or "").strip()
                    if CLIENT_ID_RX.fullmatch(tok.lower()) and tok.lower() != self.home.client_id():
                        # вставили ClientID своего приложения Яндекса — запоминаем его, дальше «Получить ключ» ведёт в него
                        self.s.update({"smarthome": {"client_id": tok.lower()}})
                        return dict(self.home.public(), client_saved=True)
                    r = self.home.connect(tok)
                    self.own_share()                # и на телефоне Лира сможет — ключ уходит зашифрованным
                elif cmd == "home_forget":
                    r = self.home.forget()
                    self.own_share()
                elif cmd == "home_refresh":
                    self.home.info(force=True)
                    r = self.home.public()
                else:
                    raise ValueError("неизвестная команда")
                self.emit("tools", tools=self.toolbox.catalog())
                return r
            except HomeError as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("ha_"):                # Home Assistant: адрес и долгосрочный токен (токен в студию не отдаётся)
            from smarthome import HomeError
            try:
                if cmd == "ha_get":
                    return self.ha.public()
                if cmd == "ha_connect":
                    r = self.ha.connect(a.get("url") or "", a.get("token") or "")
                    self.own_share()                # своим устройствам — конвертом, сервер токена не видит
                elif cmd == "ha_forget":
                    r = self.ha.forget()
                    self.own_share()
                elif cmd == "ha_refresh":
                    self.ha.info(force=True)
                    r = self.ha.public()
                else:
                    raise ValueError("неизвестная команда")
                self.emit("tools", tools=self.toolbox.catalog())
                return r
            except HomeError as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("cal_"):               # календари Google/Яндекс по ссылке iCal
            from calsync import CalError
            try:
                if cmd == "cal_list":
                    return self.calendars.public()
                if cmd == "cal_add":
                    r = self.calendars.add(a.get("url", ""), a.get("name", ""))
                elif cmd == "cal_remove":
                    r = self.calendars.remove(a.get("id", ""))
                elif cmd == "cal_toggle":
                    r = self.calendars.toggle(a.get("id", ""), a.get("on", True))
                elif cmd == "cal_refresh":
                    self.calendars.refresh()
                    r = self.calendars.public()
                else:
                    raise ValueError("неизвестная команда")
                self.emit("calendars", **r)
                return r
            except CalError as e:
                raise ValueError(str(e)) from e
            except Exception as e:  # noqa: BLE001
                raise ValueError(f"календарь не подключился: {e}") from e
        if cmd.startswith("vault_"):             # сейф: список без значений; значение — только по явному vault_reveal
            if cmd == "vault_list":
                return {"items": self.vault.list()}
            if cmd == "vault_reveal":
                x = self.vault.get(a.get("id", ""))
                return {"value": x["value"] if x else ""}
            if cmd == "vault_put":
                val = a.get("value", "")
                if a.get("id") and not val and a.get("kind") != "page":   # правка без нового пароля — пароль прежний
                    old = self.vault.get(a["id"])
                    val = old["value"] if old else ""
                x = self.vault.put(a.get("name", ""), val, a.get("note", ""), a.get("id") or None,
                                   login=a.get("login"), url=a.get("url"), kind=a.get("kind"))
                return {"item": x, "items": self.vault.list()}
            if cmd == "vault_delete":
                self.vault.delete(a.get("id", ""))
                return {"items": self.vault.list()}
            if cmd == "vault_sync":                # сейф между своими устройствами — только шифром мастер-пароля (vault.SafeKey)
                return self.vault_sync(str(a.get("op") or "status"), a)
        if cmd.startswith("backup_"):            # резервная копия
            from backup import BackupError, default_dir
            folder = self.s.get("backup", "dir") or str(default_dir())
            try:
                if cmd == "backup_info":
                    return {"dir": folder, "auto": self.s.get("backup", "auto") is not False, "items": self.backup.list(folder),
                            "host": self.backup.host, "pw": bool(self.backup.pw_get()),
                            "vault": self.vault.count(), "mail": bool(self.mail.configured()) if getattr(self, "mail", None) else False}
                if cmd == "backup_make":               # «Слепок знаний»: fmt dwr (закрытый) / zip (открытый); remember — запомнить пароль
                    fmt = "zip" if a.get("fmt") == "zip" else "dwr"
                    pw = "" if fmt == "zip" else (a.get("password") or (self.backup.pw_get() if a.get("saved") else ""))
                    if fmt == "dwr" and a.get("password") and a.get("remember"):
                        self.backup.pw_set(a["password"])
                    return self.backup.make(folder, password=pw, fmt=fmt)
                if cmd == "backup_forget_pw":          # забыть запомненный пароль слепка на этом компьютере
                    self.backup.pw_set("")
                    return {"pw": False}
                if cmd == "backup_inspect":
                    return self.backup.describe(a.get("path", ""))
                if cmd == "backup_restore":
                    pw = a.get("password") or ""
                    if not pw and a.get("saved"):           # закрытый слепок — запомненным паролем
                        pw = self.backup.pw_get()
                    r = self.backup.restore(a.get("path", ""), pw, mode="merge" if a.get("mode") == "merge" else "replace")
                    self.restart_core(2.0)                # восстановленные настройки читаются только при запуске
                    return r
                if cmd == "backup_open":
                    Path(folder).mkdir(parents=True, exist_ok=True)
                    import tools as _t
                    _t.launch(["xdg-open", folder])
                    return {"ok": True}
            except BackupError as e:
                raise ValueError(str(e)) from e
            except OSError as e:
                raise ValueError(f"не получилось: {e}") from e
        if cmd.startswith("mail_"):              # почта: настройки, проверка, тестовое письмо
            from mail import MailError, guess
            try:
                if cmd == "mail_save":
                    r = self.mail.save(a.get("patch") or {}, int(a.get("box") or 0))
                    self.emit("tools", tools=self.toolbox.catalog())
                    return r
                if cmd == "mail_guess":
                    return guess(a.get("address", ""))
                # «Почта» на главной студии (30.10, владелец: «добавил почту — не могу понять, как увидеть последние письма»)
                if cmd == "mail_inbox":
                    if not any(b.configured() and b.data.get("imap_host") for b in self.mail.boxes):
                        return {"on": False, "items": []}
                    items = self.mail.inbox(max(1, min(int(a.get("limit") or 5), 20)))
                    return {"on": True, "items": [{k: x.get(k) for k in ("uid", "from", "subject", "date", "snippet", "unread", "files", "box")} for x in items]}
                if cmd == "mail_read":
                    return self.mail.read(str(a.get("uid") or ""), mark=a.get("mark", True) is not False, html_view=bool(a.get("html")))
                # №562 (05.11): письмо в студии — «Удалить» (в «Корзину»), «В спам», «Переслать»; вопрос «точно?» задаёт студия
                if cmd == "mail_act":
                    act = str(a.get("action") or "")
                    if act not in ("trash", "junk", "forward"):
                        raise MailError("неизвестное действие с письмом")
                    r = self.mail.manage(str(a.get("uid") or ""), act, str(a.get("to") or ""), str(a.get("note") or ""))
                    log.info("✉ Студия: письмо %s — %s", r.get("uid"), {"trash": "в корзину", "junk": "в спам", "forward": "переслано"}[act])
                    return r
                if cmd == "mail_test":
                    return self.mail.test(int(a.get("box") or 0))
                if cmd == "mail_send_test":
                    return self.mail.box(int(a.get("box") or 0)).send("", "Dewiar: проверка почты",
                                          "Здравствуйте!\n\nЭто проверочное письмо от голосового ассистента Dewiar. "
                                          "Почта подключена: теперь можно сказать «пришли мне это на почту» или "
                                          "«что нового в почте?».\n\n— Dewiar")
                if cmd == "mail_forget":
                    r = self.mail.forget(int(a["box"]) if a.get("box") is not None else None)
                    self.emit("tools", tools=self.toolbox.catalog())
                    return r
                return self.mail.public()
            except MailError as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("course_"):           # курс «Неделя с Лирой» (core/course.py, studio/course.js)
            c = self.course
            if cmd == "course_seen":
                sec = str(a.get("section") or "")
                if re.fullmatch(r"[a-z][a-z0-9_]{0,30}", sec) and hasattr(self, "health_use"):   # «чем пользуются» (13.11): раздел студии открыли — только имя
                    self.health_use("s:" + sec)
                c.seen(sec)
            elif cmd == "course_pick":
                return c.pick(str(a.get("id") or ""))
            elif cmd == "course_ahead":
                return c.ahead()
            elif cmd == "course_offer":
                return c.set_offer(a.get("on", True))
            elif cmd == "course_skip":
                return c.skip_today()
            elif cmd == "course_restart":
                return c.restart(int(a["day"]) if a.get("day") else None)
            return c.public()
        if cmd == "guide":                      # «Вопрос — ответ» (studio/qa.js): всё руководство, статья {id} или поиск {q}
            import guide as G
            if a.get("id"):
                return next((x for x in G.load() if x.get("id") == a["id"]), None)
            if a.get("q"):
                return [x["id"] for x in G.search(str(a["q"]), n=8)]
            return G.load()
        if cmd == "recall":                     # поиск по записям (страница «Память»)
            return self.recall.search(a.get("query", ""), limit=int(a.get("limit") or 10))
        if cmd == "skills_folder":
            self.skills.user_dir.mkdir(parents=True, exist_ok=True)
            return str(self.skills.user_dir)
        if cmd == "js_errors":                        # ошибки страницы студии (core.js) — в журнал, а с ним и в отчёт
            for e in (a.get("errors") or [])[:20]:
                log.warning("студия: ошибка страницы: %s", str(e)[:300])
            return {"ok": True}
        if cmd in ("ann", "ann_seen"):                # объявления для всех (кабинет → «Новости»; news.announcements)
            if cmd == "ann_seen":
                seen = max(int(self.s.get("ui", "ann_seen") or 0), int(a.get("id") or 0))
                self.s.update({"ui": {"ann_seen": seen}})
                self.emit("ann", item=None)           # прочитано в студии — строка у виджета исчезает
                return {"ok": True, "seen": seen}
            if a.get("refresh"):
                self._ann_fetch()
            return {"items": list(getattr(self, "_ann", []) or []), "seen": int(self.s.get("ui", "ann_seen") or 0)}
        if cmd in ("news", "news_seen"):              # «Что нового» после обновления (news.py)
            import news
            seen = self.s.get("ui", "news_seen") or ""
            if cmd == "news_seen":
                self.s.update({"ui": {"news_seen": VERSION}})
                return {"ok": True}
            if a.get("all"):                          # «О программе» → «Что нового» — все выпуски (идея №57, 29.10)
                return {"version": VERSION, "releases": news.releases("", VERSION, limit=500), "all": True}
            if not seen:                              # первый раз с этой функцией: новая установка — молчим, обновились — показываем
                if (self.s.get("ui", "welcome") or "") != "done":
                    self.s.update({"ui": {"news_seen": VERSION}})
                    return {"version": VERSION, "releases": []}
            return {"version": VERSION, "releases": news.releases(seen, VERSION) if seen != VERSION else []}
        if cmd in ("done", "done_add", "done_undo", "done_reminder"):    # «Дела»: сделанное и достижения (студия, done.py)
            return self._done_cmd(cmd, a)
        if cmd in ("reminders", "reminder_add", "reminder_update", "reminder_split", "reminder_cancel", "alarm_ack", "alarm_snooze",
                   "alarm_get", "alarm_test", "reminder_parse", "job_add", "job_run", "reminder_files", "capture_parse", "capture_save"):
            return self._reminder_cmd(cmd, a)
        if cmd in ("morning_get", "morning_set"):                   # «Утро с Лирой» (morning.py): карточка на главной студии
            import morning
            if cmd == "morning_set":
                patch = {}
                if "city" in a:
                    patch["city"] = re.sub(r"\s+", " ", str(a.get("city") or "")).strip()[:60]
                if "mail" in a:
                    patch["mail"] = bool(a.get("mail"))
                if "hide" in a:
                    patch["hide"] = str(a.get("hide") or "")[:10]
                self.s.update({"morning": patch})
            d = morning.public(morning.gather(self, net=True, fresh=bool(a.get("fresh")) or cmd == "morning_set"))
            job = next((x for x in self.reminders.items if x.get("kind") == "job" and (x.get("preset") == "brief" or x.get("brief"))), None)
            return dict(d, settings=dict(self.s.get("morning") or {}), daily=self._reminder_public(job) if job else None,
                        mail_on=bool(getattr(self, "mail", None) and self.mail.configured()))
        if cmd.startswith("pay_"):                                  # «Платежи» (engine_pay.py, payments.py)
            try:
                return self._pay_cmd(cmd, a)
            except (TypeError, KeyError) as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("money_") or cmd == "calendar_month":      # деньги и календарь (студия → «Календарь»)
            m = self.money
            try:
                if cmd == "calendar_month":
                    now = datetime.now()
                    return self.calendar_month(int(a.get("year") or now.year), int(a.get("month") or now.month))
                if cmd == "money_list":
                    return m.list(a.get("from"), a.get("to"))
                if cmd == "money_summary":
                    return m.summary(a.get("from"), a.get("to"))
                if cmd == "money_add":
                    r = m.add(a.get("kind", "expense"), a.get("amount", 0), a.get("currency") or None,
                              a.get("category") or "", a.get("note") or "", a.get("date") or None)
                elif cmd == "money_update":
                    r = m.update(a.get("id", ""), a.get("patch") or {})
                elif cmd == "money_delete":
                    r = m.delete(a.get("id", ""))
                elif cmd == "money_relabel":                   # ошибочная валюта у записей — исправить разом (№422)
                    r = {"changed": m.relabel(a.get("from"), a.get("to"))}
                else:
                    raise ValueError("неизвестная команда")
                self.emit("money_saved", **(r or {}))
                return r
            except (TypeError, ValueError) as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("obsidian_"):          # Obsidian: хранилище заметок — подключить, синхронизировать, отключить
            from obsidian import ObsidianError
            ob = self.obsidian
            try:
                if cmd == "obsidian_connect":
                    return ob.connect(a.get("path", ""), a.get("folder"))
                if cmd == "obsidian_set":
                    return ob.set(a.get("patch") or {})
                if cmd == "obsidian_sync":
                    ob.sync()
                    if ob.last["error"]:
                        raise ObsidianError(ob.last["error"])
                    return ob.public()
                if cmd == "obsidian_forget":
                    return ob.forget()
                return ob.public()
            except ObsidianError as e:
                raise ValueError(str(e)) from e
        if cmd == "rag_scope":                   # базы сайта Dewiar: свои папки и публичная библиотека
            from account import AccountError
            try:
                return self.account.scope(force=bool(a.get("force")))
            except AccountError as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("server_"):            # «Серверы»: SSH-профили, ключ Dewiar, проверка входа
            from servers import ServerError
            sv = self.servers
            try:
                if cmd == "server_add":
                    sv.add(a.get("name", ""), a.get("host", ""), a.get("user", ""), a.get("port") or 22, a.get("password", ""),
                           a.get("keyfile", ""), a.get("aliases") or [], a.get("notes", ""))
                elif cmd == "server_key":
                    sv.ensure_key()
                elif cmd == "server_check":
                    info = sv.check_one(a.get("id", ""))
                    return dict(sv.public(), info=info)
                elif cmd == "server_update":
                    sv.update(a.get("id", ""), a.get("patch") or {})
                elif cmd == "server_remove":
                    sv.remove(a.get("id", ""))
                elif cmd == "server_list":
                    pass
            except ServerError as e:
                raise ValueError(str(e)) from e
            if cmd in ("server_add", "server_remove"):
                self.emit("tools", tools=self.toolbox.catalog())
            return sv.public()
        if cmd == "max_shared":                  # 15.11 (№748): бот Dewiar в MAX настроен на сайте? (раз в 30 минут)
            return self._max_shared_ok()
        if cmd.startswith("max_"):               # MAX: бот Dewiar (через сайт) или свой бот организации
            from telegram import TelegramError
            from maxbot import SHARED_URL as MAX_URL
            mx = self.max
            try:
                if cmd == "max_connect":
                    r = mx.connect(a.get("token", ""), a.get("api", ""))
                elif cmd == "max_connect_shared":
                    urls = [u for u in (self.s.get("max_url"), self.account.service_url("max"), MAX_URL) if u]
                    err = None
                    for u in dict.fromkeys(urls):
                        try:
                            r = mx.connect_shared(u)
                            break
                        except TelegramError as e:
                            log.warning("MAX: %s — %s", u, e)
                            err = e
                    else:
                        raise err or TelegramError("нет адреса сервера MAX")   # без адресов цикл не шёл — err пустой
                elif cmd == "max_set":
                    r = mx.set(a.get("patch") or {})
                elif cmd == "max_new_code":
                    r = mx.new_code()
                elif cmd == "max_test":
                    mx.test()
                    r = mx.public()
                elif cmd == "max_forget":
                    r = mx.forget()
                else:
                    r = mx.public()
            except TelegramError as e:
                raise ValueError(str(e)) from e
            if cmd in ("max_connect", "max_connect_shared", "max_forget", "max_new_code"):
                self.emit("tools", tools=self.toolbox.catalog())
            return r
        if cmd in ("writing_get", "writing_goal"):   # «Пишу» в «Документах»: написано за день, цель, 14 дней
            if cmd == "writing_goal":
                return self.writing.set_goal(a.get("goal") or 0)
            return self.writing.scan() if a.get("fresh") else self.writing.maybe_scan(20)
        if cmd.startswith("pbot_post") or cmd in ("pbot_chat_add", "pbot_chat_del", "pbot_rubric_set", "pbot_rubric_del", "pbot_greet"):
            # «Посты» бота персонажа (pbot_posts.py): в каналы и группы — сейчас, ко времени, с одобрением; рубрики; новички
            from pbot_posts import PostError
            P = self.pbot_posts
            try:
                if cmd == "pbot_posts":
                    return P.public()
                if cmd == "pbot_post_add":
                    P.add(a.get("text") or "", a.get("chats"), a.get("at") or None, a.get("poll"), bool(a.get("approve")), "studio", a.get("topic") or "")
                elif cmd == "pbot_post_edit":
                    P.edit(str(a.get("id") or ""), a.get("text"), a.get("at"), a.get("chats"))
                elif cmd == "pbot_post_ok":
                    P.approve(str(a.get("id") or ""))
                elif cmd == "pbot_post_del":
                    P.delete(str(a.get("id") or ""))
                elif cmd == "pbot_post_retry":              # не ушёл (бот не админ, сеть) — ещё раз
                    P.publish(str(a.get("id") or ""))
                elif cmd == "pbot_post_write":
                    try:
                        return {"text": P.write(str(a.get("topic") or "").strip(), str(a.get("chat_title") or ""))}
                    except PostError:
                        raise
                    except Exception as e:  # noqa: BLE001
                        raise PostError(f"модель не ответила: {e}") from e
                elif cmd == "pbot_chat_add":
                    P.add_chat(str(a.get("ref") or ""))
                elif cmd == "pbot_chat_del":
                    P.forget_chat(str(a.get("id") or ""))
                elif cmd == "pbot_rubric_set":
                    P.rubric_set(a)
                elif cmd == "pbot_rubric_del":
                    P.rubric_del(str(a.get("id") or ""))
                elif cmd == "pbot_greet":
                    P.greet_set(a.get("on"), a.get("text"))
                else:
                    raise ValueError("неизвестная команда постов")
            except (PostError, ValueError) as e:
                raise ValueError(str(e)) from e
            return P.public()
        if cmd.startswith("pbot_"):              # «Бот персонажа» (pbot.py): публичный бот в Telegram от имени персонажа
            from telegram import TelegramError
            pb = self.pbot
            try:
                if cmd == "pbot_connect":
                    r = pb.connect(a.get("token", ""), a.get("api", ""))
                    self._course_did("pbot_connect")
                elif cmd == "pbot_set":
                    r = pb.set(a.get("patch") or {})
                elif cmd == "pbot_forget":
                    r = pb.forget()
                elif cmd == "pbot_check":                   # №643: «Проверить снова» — режим приватности по getMe сейчас
                    pb.privacy(fresh=True)
                    r = pb.public()
                elif cmd == "pbot_try":                     # как персонаж ответит незнакомцу — без Telegram
                    q = str(a.get("text") or "").strip()
                    if len(q) < 2:
                        raise ValueError("напишите вопрос, как его задал бы посетитель")
                    try:
                        r = pb.test(q)
                        self._course_did("pbot_try")
                    except Exception as e:  # noqa: BLE001
                        raise ValueError(f"модель не ответила: {e}") from e
                else:
                    pb.privacy_soon()                        # режим приватности — в фоне, ответ придёт событием «pbot»
                    r = pb.public()
                    r["personas"] = [{"id": x["id"], "name": x.get("name", ""), "color": x.get("color", ""), "style": x.get("style", ""),
                                      "avatar_url": x.get("avatar_url") or "", "kb": len(x.get("knowledge") or [])}
                                     for x in self.personas.public() if not x.get("kids")]
            except TelegramError as e:
                raise ValueError(str(e)) from e
            return r
        return NotImplemented

    def vault_sync(self, op, a):
        """«Синхронизировать сейф между моими устройствами». op: status | on {password} — включить: в облаке сейф уже есть —
        его мастер-паролем (не подошёл — ошибка), нет — новый мастер-пароль | change {old, password} — сменить (все записи
        перешифруются) | reset {password} — забыли мастер-пароль: новый с этого компьютера (записи только с других устройств
        откроются, когда они введут новый) | off — забыть ключ здесь (записи на этом компьютере и в облаке остаются).
        Мастер-пароль и ключ никуда не уходят; в ответе — только состояние."""
        from vault import SAFE_MIN, safe_derive, safe_meta_new, safe_try
        import closecrypto as CC
        sk, sy = self.safe_key, self.sync
        hs = getattr(self, "home_sync", None)
        hs = None if hs is None or getattr(hs, "stopped", False) else hs

        def status():
            tok, _, _ = self.credentials()
            st = sy.safe_status()
            m = sk.remote() or {}
            return dict(st, linked=bool(tok) or hs is not None, sync_on=self.s.get("sync", "enabled") is not False,
                        count=self.vault.count(), since=int(((sk.get() or {}).get("meta") or {}).get("at") or 0), min=SAFE_MIN,
                        phones=sum(1 for d in (sy.status.get("all") or []) if d.get("app") in ("phone", "web")), known=bool(m))

        def refetch():
            for x in (sy, hs):
                if x is not None:
                    x.safe_refetch()
        if op == "status":
            return status()
        pw = str(a.get("password") or "")
        if op == "on":
            tok, _, _ = self.credentials()
            if not tok and hs is None:
                raise ValueError("сначала подключите синхронизацию устройств: «Устройства» → вход или ключ Dewiar")
            if tok:                                      # свежие параметры из облака: сейф могли включить на другом устройстве
                try:
                    sy.run_once()
                except Exception as e:  # noqa: BLE001
                    log.info("Сейф: облако сейчас не ответило (%s) — включаю по тому, что знаю", e)
            rem = sk.remote()
            if rem:
                k = safe_try(pw, rem)
                if k is None:
                    raise ValueError("мастер-пароль не подошёл — это пароль, который вы придумали, когда включали сейф на другом устройстве")
                sk.set(k, rem)
            else:
                k, meta = safe_meta_new(pw)
                sk.set(k, meta)
            log.info("🔐 Сейф: синхронизация между своими устройствами включена")
            refetch()
            return status()
        if op == "reset":                              # забыли мастер-пароль: сейф этого компьютера — общим под новым
            tok, _, _ = self.credentials()
            if not tok and hs is None:
                raise ValueError("сначала подключите синхронизацию устройств: «Устройства» → вход или ключ Dewiar")
            k, meta = safe_meta_new(pw)                  # новые параметры позже прежних — другие устройства попросят новый пароль
            sk.set(k, meta)
            log.info("🔐 Сейф: начат заново с новым мастер-паролем на этом компьютере")
            refetch()
            return status()
        if op == "change":
            cur = sk.active()
            if cur is None:
                raise ValueError("сначала включите синхронизацию сейфа")
            m = cur["meta"]
            if safe_derive(str(a.get("old") or ""), CC.b64d(m["salt"]), int(m["it"])) != cur["k"]:
                raise ValueError("прежний мастер-пароль не подошёл")
            k, meta = safe_meta_new(pw)
            sk.set(k, meta)                              # новый kid — все записи уйдут заново, другим устройствам — спросить новый
            log.info("🔐 Сейф: мастер-пароль сменён — записи перешифровываются")
            for x in (sy, hs):
                if x is not None:
                    x.soon.set()
            return status()
        if op == "off":
            sk.forget()
            log.info("🔐 Сейф: синхронизация выключена на этом компьютере")
            return status()
        raise ValueError("неизвестная команда сейфа")
