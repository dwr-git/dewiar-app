"""Движок Dewiar: команды из интерфейса (студия, виджет, телефон).
Примесь класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
command(cmd, a) — единый разбор: bridge.py вызывает его по WebSocket в пуле потоков (одновременно может идти
несколько команд); ответ уходит окну как данные, ValueError — как текст ошибки для человека. Имена команд
совпадают с вызовами в ui/ (студия, виджет); новую команду добавляйте и сюда, и туда.
Многие команды лишь передают работу службам (reminders, money, telegram, cloud…) и шлют событие для обновления окна."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


# Детский режим (kids.py): пока родитель не ввёл PIN, окна не могут менять настройки и делать взрослое
_KIDS_LOCKED = ("council_", "pbot_", "account_", "backup_", "mode_set", "senior_", "notes_import", "watch_add", "home_set", "ideas_new", "home_pair", "home_forget", "cal_add", "cal_remove", "cloud_connect", "cloud_forget", "cloud_model", "cloud_topup",
                "config_", "const_", "gallery_add", "ha_connect", "ha_forget", "home_connect", "home_forget", "job_", "knowledge_add",
                "knowledge_remove", "knowledge_folder", "llm_", "mail_", "max_", "memory_forget", "memory_set", "money_",
                "net_dewiar", "net_proxy", "net_reserve", "obsidian_", "pay_", "persona_", "plugin", "prompter_", "quit",
                "security_set", "server_", "skill_", "soul_save", "soul_update", "soul_delete", "sync_set", "sync_e2e", "tg_", "tools",
                "vault_", "ws_delete", "ws_set_path", "text_mode", "mm_folder", "radio_custom_add", "radio_custom_del",
                "report_auto", "power_cancel", "fam_", "join_", "ref_use", "exam_traces_remove", "chat_clear", "diary_", "update_install", "team_", "client", "device_", "pair_", "brains_pull", "morning_", "month_")


def _kids_blocked(cmd, a):
    """Можно ли это окнам в детском режиме без PIN: настройки — только положение и вид окон (ui) и «отвечать текстом»."""
    if cmd == "settings_save":
        patch = (a or {}).get("patch") or {}
        return not all(k == "ui" or (k == "tts" and set(v or {}) <= {"text_only"}) for k, v in patch.items())
    return cmd.startswith(_KIDS_LOCKED)


class CommandsMixin:
    def _course_did(self, key):
        """Шаг урока «сделайте в студии…» (course.did) — без ошибок, если курса нет."""
        try:
            c = getattr(self, "course", None)
            if c is not None:
                c.did(key)
        except Exception:  # noqa: BLE001
            log.debug("курс: шаг %s", key, exc_info=True)

    PTT_CALM = 2.5                     # с: нажатие на лицо сразу после «стоп» — тоже «стоп» (судорожные нажатия, 28.10)

    # ---------- команды из интерфейса ----------

    def switch_persona(self, pid):
        if pid not in {p["id"] for p in self.personas.all()}:
            raise ValueError("нет такого персонажа")
        kids = getattr(self, "kids", None)
        if kids and kids.on() and pid != kids.conf().get("persona"):
            log.info("Детский режим: переход к «%s» не делаю — отвечает только друг ребёнка", pid)
            return
        self.s.update({"persona": pid})               # разговор общий: новый персонаж знает, что было
        if not self.s.get("all_names"):
            self.build_spotter()
        self.emit("persona", persona=pid)
        self.set_state(self.state)                    # событие «state» несёт и персонажа — окна обновятся
        threading.Thread(target=self.ensure_voice, args=(pid,), daemon=True).start()

    # ---------- детский режим (kids.py) ----------

    def kids_public(self, light=False):
        """Состояние для окон; light — без портрета друга (событие после каждого вопроса)."""
        k = self.kids
        c = k.conf()
        ok, why = k.allowed_now()
        from kids import ALLOW
        from personas import GALLERY
        return {"on": k.on(), "has_pin": k.has_pin(), "locked": k.locked(), "unlocked": k.unlocked(),
                "child": c.get("child") or {}, "persona": c.get("persona"), "allow": c.get("allow"), "allow_names": ALLOW,
                "min_weekday": c.get("min_weekday"), "min_weekend": c.get("min_weekend"), "bedtime": c.get("bedtime"),
                "morning": c.get("morning"), "used": k.used_today(), "limit": k.limit_today(), "left": k.left_today(),
                "can_talk": ok, "why": why} | ({} if light else {"friend": self.personas.avatar_data_url({"id": c.get("persona") or "ugo"}),
                "friend_name": (self.personas.items.get(c.get("persona")) or GALLERY.get(c.get("persona") or "") or {}).get("name") or "Совёнок Уго"})

    def kids_cmd(self, cmd, a):
        """kids_get — состояние и отчёт; kids_pin {pin, old}; kids_unlock {pin}; kids_lock; kids_on {on, pin};
        kids_set {child, allow, min_weekday, min_weekend, bedtime, morning} — настройки (режим выключен или открыт PIN)."""
        k = self.kids
        if cmd == "kids_get":
            return dict(self.kids_public(), report=k.report() if (not k.on() or k.unlocked()) else None)
        if cmd == "kids_unlock":
            k.unlock(a.get("pin"))
        elif cmd == "kids_lock":
            k.lock()
        elif cmd == "kids_pin":
            k.set_pin(a.get("pin"), a.get("old", ""))
        elif cmd == "kids_on":
            if a.get("on"):
                pid = k.conf().get("persona") or "ugo"
                if pid not in {p["id"] for p in self.personas.all()}:
                    self.personas.gallery_add(pid)          # друг ребёнка ставится сам, в общей галерее его нет
                    self.emit("personas", personas=self.personas.public())
                k.set_on(True)
                self.switch_persona(pid)
                self.build_spotter()                        # слушаем только его имя
                log.info("🧸 Детский режим включён")
            else:
                prev = k.set_on(False, a.get("pin", ""))
                if prev and prev in {p["id"] for p in self.personas.all()}:
                    self.switch_persona(prev)
                self.build_spotter()
                log.info("🧸 Детский режим выключен")
        elif cmd == "kids_set":
            if k.locked():
                raise ValueError("Детский режим: сначала PIN родителя")
            from kids import ALLOW
            patch = {}
            if "child" in a:
                ch = a.get("child") or {}
                patch["child"] = {"name": str(ch.get("name") or "")[:40], "age": int(ch.get("age") or 0) or None}
            if "allow" in a:
                patch["allow"] = [x for x in (a.get("allow") or []) if x in ALLOW]
            for f, lo, hi in (("min_weekday", 0, 600), ("min_weekend", 0, 600)):
                if f in a:
                    patch[f] = max(lo, min(hi, int(a.get(f) or 0)))
            for f in ("bedtime", "morning"):
                if f in a:
                    v = str(a.get(f) or "")
                    if v and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
                        raise ValueError("время — в виде 20:30")
                    patch[f] = v
            self.s.update({"kids": patch})
        else:
            raise ValueError(f"неизвестная команда {cmd}")
        st = self.kids_public()
        self.emit("kids", **st)
        return st

    def _kids_alert(self, text):
        """Просьба вне правил в детском режиме — родителю в Telegram (если бот подключён); в отчёте она уже есть."""
        tg = getattr(self, "telegram", None)
        name = ((self.kids.conf().get("child") or {}).get("name") or "Ребёнок")
        log.info("🧸 Вне правил: %s", redact(text[:80]))
        if tg is not None and getattr(tg, "paired", lambda: False)():
            try:
                tg.send(f"🧸 Детский режим: {name} попросил(а) то, что нельзя: «{text[:120]}». Совёнок отказал и "
                        "предложил спросить вас. Весь разговор — студия → «Дети».")
            except Exception:  # noqa: BLE001
                log.debug("детский режим: Telegram", exc_info=True)

    # ---------- семейный бюджет (family.py) ----------

    def family_cmd(self, cmd, a):
        """fam_get — всё для раздела «Семья» и кого можно позвать (из «Близких»); fam_invite/fam_accept/fam_leave {pid};
        fam_bill {id?, name, amount, due, payer}; fam_paid {id, paid}; fam_bill_del {id}; fam_remind {id};
        fam_limit {v}; fam_share {on}."""
        from close import CloseError
        from family import FamilyError
        F = self.family
        try:
            if cmd == "fam_get":
                people = []
                try:
                    people = [{"pid": p["pid"], "name": p["name"]} for p in (self.close.state().get("people") or [])]
                except Exception:  # noqa: BLE001 — «Близкие» без входа или без связи: список пуст
                    pass
                return dict(F.public(a.get("month")), people=people)
            if cmd == "fam_invite":
                return F.invite(str(a.get("pid") or ""))
            if cmd == "fam_accept":
                return F.accept(str(a.get("pid") or ""))
            if cmd == "fam_leave":
                return F.leave(str(a.get("pid") or ""))
            if cmd == "fam_bill":
                F.bill_save(a)
            elif cmd == "fam_paid":
                F.bill_paid(str(a.get("id") or ""), a.get("paid", True) is not False)
            elif cmd == "fam_bill_del":
                F.bill_delete(str(a.get("id") or ""))
            elif cmd == "fam_remind":
                F.remind(str(a.get("id") or ""))
            elif cmd == "fam_limit":
                F.set_limit(a.get("v"))
            elif cmd == "fam_share":
                F.set_share(a.get("on"))
            else:
                raise ValueError(f"неизвестная команда {cmd}")
        except (FamilyError, CloseError) as e:
            raise ValueError(str(e)) from e
        return F.public()

    # ---------- «Команда»: поручения сотрудникам в Telegram (team.py) ----------

    def clients_cmd(self, cmd, a):
        """«Клиенты» (clients.py): clients_list {q}; client_get {id}; client_add {name, company, phone, email}; client_save {id, …};
        client_note {id, text, kind}; client_note_del {id, nid}; client_next {id, what, at (ГГГГ-ММ-ДДTЧЧ:ММ) | when (словами)};
        client_next_done {id}; client_del {id}."""
        from clients import ClientError
        from deals import DealError
        C = self.clients
        cid = str(a.get("id") or "")
        try:
            if cmd == "clients_list":
                return C.list(str(a.get("q") or ""))
            if cmd == "client_get":
                return C.get(cid)
            if cmd == "client_add":
                return C.add(a.get("name") or "", a.get("company") or "", a.get("phone") or "", a.get("email") or "", a.get("note") or "")
            if cmd == "client_save":
                return C.save(cid, {k: a[k] for k in ("name", "company", "phone", "email", "note", "tags") if k in a})
            if cmd == "client_note":
                return C.note(cid, a.get("text") or "", a.get("kind") or "note")
            if cmd == "client_note_del":
                return C.note_del(cid, str(a.get("nid") or ""))
            if cmd == "client_next":
                at = None
                if a.get("at"):
                    at = datetime.fromisoformat(str(a["at"]))
                elif a.get("when"):
                    from when import parse
                    r = parse("напомни " + str(a["when"]))
                    if not r:
                        raise ClientError("не понял, когда — например: «завтра в 11», «в четверг»")
                    at = r["at"]
                return C.set_next(cid, a.get("what") or "", at)
            if cmd == "client_next_done":
                return C.next_done(cid)
            if cmd == "client_del":
                return C.delete(cid)
            # сделки (deals.py): clients_deals — доска; client_deal_add {id, title, amount, stage, due}; client_deal_set
            # {id, did, title?, amount?, stage?, due?, note?}; client_deal_del {id, did}; clients_deal_income {on}
            if cmd == "clients_deals":
                return dict(C.deals_board(), income=(self.s.get("clients") or {}).get("deal_income", True) is not False)
            if cmd == "clients_deal_income":
                self.s.update({"clients": {"deal_income": bool(a.get("on"))}})
                return dict(C.deals_board(), income=bool(a.get("on")))
            if cmd == "client_deal_add":
                d = C.deal_add(cid, a.get("title") or "", a.get("amount") or 0, a.get("cur") or "", a.get("stage") or "lead", a.get("due") or "")
                self._deal_income(d)
                return C.get(cid)
            if cmd == "client_deal_set":
                d = C.deal_set(cid, str(a.get("did") or ""), **{k: a[k] for k in ("title", "amount", "cur", "stage", "due", "note") if k in a})
                self._deal_income(d)
                return C.get(cid)
            if cmd == "client_deal_del":
                C.deal_del(cid, str(a.get("did") or ""))
                return C.get(cid)
            # «Напомнить об оплате» (0.62): черновик письма — потом отправить почтой или скопировать в мессенджер
            if cmd == "client_deal_remind":
                me = (self.s.get("close") or {}).get("name") or self.s.get("user_name") or ""
                m = getattr(self, "mail", None)
                return dict(C.deal_remind_text(cid, str(a.get("did") or ""), me), mail=bool(m and m.configured()))
            if cmd == "client_deal_remind_send":
                did = str(a.get("did") or "")
                if a.get("how") == "copy":            # скопировали текст — отметить в истории, что напомнили
                    C.deal_reminded(cid, did, "сообщением")
                    return C.get(cid)
                m = getattr(self, "mail", None)
                if not (m and m.configured()):
                    raise ValueError("почта не подключена — студия → «Подключение» → «Почта»; или скопируйте текст")
                to = str(a.get("to") or "").strip()
                if not re.match(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$", to):
                    raise ValueError("укажите почту клиента — например client@mail.ru")
                from mail import MailError
                try:
                    m.send(to, str(a.get("subject") or "Напоминание об оплате"), str(a.get("body") or ""))
                except MailError as e:
                    raise ValueError(str(e)) from e
                if not (C.get(cid) or {}).get("email"):
                    C.save(cid, {"email": to})
                C.deal_reminded(cid, did, "письмом")
                return C.get(cid)
            if cmd == "clients_deals_export":         # выгрузка сделок таблицей: «Клиенты/Сделки ГГГГ-ММ-ДД.csv» в папке ассистента
                rel = f"Клиенты/Сделки {time.strftime('%Y-%m-%d')}.csv"
                p = Path(self.workspace.ensure()) / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(C.deals_csv(), encoding="utf-8")
                return {"path": rel, "n": len(C.deals())}
            raise ValueError(f"неизвестная команда {cmd}")
        except (ClientError, DealError) as e:
            raise ValueError(str(e)) from e

    def _deal_income(self, d):
        """Сделка оплачена — в доходы «Денег» (если не выключено: «Клиенты» → «Сделки» → «Оплаченное — в доходы»)."""
        from deals import to_money
        if (self.s.get("clients") or {}).get("deal_income", True) is False:
            return ""
        iid = to_money(getattr(self, "money", None), d)
        if iid:
            self.clients.deal_set(d["cid"], d["id"], income=iid)
        return iid

    def team_cmd(self, cmd, a):
        """team_get; team_connect {token}; team_forget; team_set {company?, boss?, speak?}; team_member_add {name, role};
        team_member_del {id}; team_member_code {id}; team_assign {who, title, due, note}; team_accept {id};
        team_back {id, remark}; team_cancel {id}; team_remind {id}; team_photo {name} -> data:-ссылка."""
        from team import TeamError
        T = self.team
        try:
            if cmd == "team_get":
                if (self.s.get("features") or {}).get("team") and T.connected():
                    T.start()
                return T.public()
            if cmd == "team_connect":
                return T.connect(str(a.get("token") or ""), str(a.get("ch") or "tg"))
            if cmd == "team_forget":
                return T.forget(str(a.get("ch") or "tg"))
            if cmd == "team_set":
                return T.set(a or {})
            if cmd == "team_member_add":
                return T.member_add(a.get("name"), a.get("role") or "")
            if cmd == "team_member_del":
                return T.member_del(str(a.get("id") or ""))
            if cmd == "team_member_code":
                return T.member_code(str(a.get("id") or ""))
            if cmd == "team_assign":
                r = T.assign(str(a.get("who") or ""), a.get("title"), a.get("due") or "", a.get("note") or "")
                return dict(T.public(), made=({"repeat": True, "rule": r["rule"], "name": r["name_dat"]} if r.get("repeat") else {}))
            if cmd == "team_message":                   # написать сотруднику: ответ на сообщение или просто слово
                return T.message(str(a.get("id") or a.get("who") or ""), str(a.get("text") or ""))
            if cmd == "team_app_invite":                # приложение Dewiar: печать и ссылка сотруднику (renew — новые)
                return T.app_invite(str(a.get("id") or ""), bool(a.get("renew")))
            if cmd == "team_repeat_del":
                return T.repeat_del(str(a.get("id") or ""))
            if cmd == "team_accept":
                return T.accept(str(a.get("id") or ""))
            if cmd == "team_back":
                return T.back(str(a.get("id") or ""), a.get("remark"))
            if cmd == "team_cancel":
                return T.cancel(str(a.get("id") or ""))
            if cmd == "team_remind":
                return T.remind(str(a.get("id") or ""))
            if cmd == "team_photo":
                import base64
                p = T.photo_path(str(a.get("name") or ""))
                if not p:
                    raise TeamError("фото не найдено")
                return {"url": "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()}
            raise ValueError(f"неизвестная команда {cmd}")
        except TeamError as e:
            raise ValueError(str(e)) from e

    # ---------- окно голосом: «спрячься», «покажись», «отключись» ----------

    def _plugin_cmd(self, cmd, a):
        """plugins — каталог; plugin_install {id, values} / plugin_remove {id, jobs: снимать ли его дела} / plugin_values {id, values} /
        plugin_job {id, job, on} — дело плагина по расписанию / plugin_zip {zip_b64} — свой плагин / plugin_delete {id}."""
        from plugins import PluginError
        from tools import ToolError, t_schedule_job
        P = self.plugins
        try:
            if cmd == "plugin_install":
                P.install(a["id"], a.get("values"))
            elif cmd == "plugin_remove":
                for rid in P.remove(a["id"]):
                    if a.get("jobs", True):
                        try:
                            self.reminders.cancel(rid)
                        except Exception:  # noqa: BLE001 — дело уже сняли руками
                            pass
            elif cmd == "plugin_values":
                P.set_values(a["id"], a.get("values") or {})
            elif cmd == "plugin_job":
                pid, jid = a["id"], a["job"]
                old = (((self.s.get("plugins", "on") or {}).get(pid) or {}).get("jobs") or {}).get(jid)
                if old:
                    try:
                        self.reminders.cancel(old)
                    except Exception:  # noqa: BLE001
                        pass
                rid = ""
                if a.get("on"):
                    task, when = P.job_text(pid, jid)
                    out = t_schedule_job({"task": task, "when": when}, {"reminders": self.reminders})
                    m = re.search(r"\(id ([^)]+)\)", out)
                    rid = m.group(1) if m else ""
                P.job_mark(pid, jid, rid)
            elif cmd == "plugin_zip":
                import base64
                P.install(P.install_zip(base64.b64decode(a.get("zip_b64") or "")))
            elif cmd == "plugin_delete":
                P.delete(a["id"])
            elif cmd != "plugins":
                raise ValueError(f"неизвестная команда {cmd}")
        except (PluginError, ToolError, KeyError) as e:
            raise ValueError(str(e)) from e
        self.skills.reload()
        if cmd in ("plugin_install", "plugin_remove", "plugin_zip", "plugin_delete"):
            self.mcp.reconcile()
        out = {"plugins": P.catalog(), "skills": self.skills.catalog()}
        if cmd == "plugins":
            out["guide"] = P.guide()
        return out

    def _pad_cmd(self, cmd, a):
        """pad_tabs / pad_read {name} / pad_write {name, text, base} / pad_new {name} / pad_rename {name, to} /
        pad_delete {name} / pad_order {names} / pad_attach {name, filename, b64} / pad_file {link}."""
        P = self.pad
        if cmd in ("pad_ai", "pad_ai_stop"):                    # ИИ-правка в блокноте (core/padai.py, ui/padai.js)
            if getattr(self, "padai", None) is None:
                from padai import PadAI
                self.padai = PadAI(self)
            return self.padai.start(a) if cmd == "pad_ai" else self.padai.stop(a.get("id", ""))
        try:
            if cmd == "pad_tabs":
                return P.tabs()
            if cmd == "pad_read":
                return P.read(a.get("name", ""))
            if cmd == "pad_write":
                r = P.write(a.get("name", ""), a.get("text", ""), a.get("base"))
                sy = getattr(self, "sync", None)
                if sy is not None:
                    sy.soon.set() if hasattr(sy, "soon") else None   # дома поправили — на работе уже через минуту
                return r
            if cmd == "pad_new":
                return P.new(a.get("name", ""))
            if cmd == "pad_rename":
                return P.rename(a.get("name", ""), a.get("to", ""))
            if cmd == "pad_delete":
                return P.delete(a.get("name", ""))
            if cmd == "pad_order":
                return P.order(a.get("names") or [])
            if cmd == "pad_attach":
                return P.attach(a.get("name", ""), a.get("filename", ""), a.get("b64", ""))
            if cmd == "pad_file":
                return P.file(a.get("link", ""))
        except (PadError, WorkspaceError, OSError) as e:
            raise ValueError(str(e)) from e
        raise ValueError(f"неизвестная команда {cmd}")

    # «Морской бой» голосом (0.63; план «Идей Лиры»: «„Б пять!“ — Лира ставит выстрел сама и отвечает голосом»): пока игра
    # открыта в «Досуге» (pad.js шлёт game_mark), короткая фраза с клеткой («бэ пять», «Д7», «стреляю в ка десять») или
    # словом игры («сдаюсь», «ещё партию») — не вопрос модели, а ход: событие game -> игра; итог она скажет через game_say.
    SEA_CELL_RX = re.compile(r"(?:^|[^а-я])(?:а|бэ?|бе|вэ?|ве|гэ?|ге|дэ?|де|е|жэ?|же|зэ?|зе|и|ка?|й)\s*-?\s*(?:10|[1-9]|один|одна|раз|два|две|три|"
                             r"четыре|пять|шесть|семь|восемь|девять|десять)(?![а-я0-9])")
    SEA_CMD_RX = re.compile(r"^(?:\w+,\s*)?(?:сдаюсь|сколько(?:\s+у\s+(?:тебя|нас|меня))?\s+(?:кораблей|осталось)|играем|давай\s+ещ[её]|ещ[её]\s+(?:партию|раз(?:ок)?)|"
                            r"новая\s+(?:партия|игра)|сыграем\s+ещ[её]|начинаем|поехали|(?:давай\s+)?полегче|в\s+полную\s+силу)$")

    def _game_voice(self, text):
        g = getattr(self, "_game_on", None)
        if not g or g[0] != "sea" or time.monotonic() - g[1] > 3 * 3600:
            return False
        t = text.lower().replace("ё", "е").strip(" .!?…")
        if len(t.split()) > 7 or not (self.SEA_CELL_RX.search(t) or self.SEA_CMD_RX.match(t)):
            return False
        log.info("🎮 «Морской бой»: %s", text)
        self._game_said = text
        self.emit("game", game="sea", text=text)
        return True

    def _window_cmd(self, text):
        """Фраза про само окно (window_phrase) -> True, если это она. Прячет и показывает виджет интерфейс
        (событие «window» ловит ui/hud.html); «отключись» — интерфейс завершает и себя, и ядро (Api.quit_all в
        ui/app.py). Интерфейса нет — «покажись» его открывает, «отключись» завершает только ядро."""
        kind = window_phrase(text)
        if not kind:
            return False
        ui = bool(self.bridge.clients)
        if kind == "tray":
            if not ui:
                self._say_quick("Виджета на экране и так нет. Я слушаю — позовите по имени.", text)
                return True
            self._tray_at = time.monotonic()            # спрятали — не заговаривать первой (_welcome_back)
            self._say_quick("Прячусь. Позовёте по имени — появлюсь.", text, then=lambda: self.emit("window", do="tray"))
        elif kind == "play":                             # «Досуг» (24.10): полка игр в листе у виджета
            if (self.s.get("features") or {}).get("games") is False:
                self._say_quick("Игры сейчас выключены. Включить — в студии, раздел «Возможности» → «Досуг».", text)
            elif not ui:
                self._say_quick("Игры открываются в окне Dewiar, а его сейчас нет на экране. Скажите «покажись» — и снова «давай поиграем».", text)
            else:
                game = play_game(text)
                names = {"snake": "Змейку", "racer": "Гонку", "bricks": "Кирпичики", "plane": "Небесного пилота", "bip": "Бипа",
                         "blocks": "Тетрис", "candy": "Конфетки", "merge": "Слияние", "sudoku": "Судоку", "fifteen": "Пятнашки", "reversi": "Реверси", "sea": "«Морской бой»",
                         "tictac": "Крестики-нолики", "crossword": "Кроссворд", "words": "«Пять букв»", "glow": "«Огонька»", "five": "«Пять в ряд»", "pairs": "«Найди пару»",
                         "farm": "«Хутор Одуванчик»", "dark": "«Кто боится темноты»", "post": "«Колючую почту»", "pinball": "«Звёздный пинбол»", "doodle": "«Каляку»", "hop": "«Выше облаков»", "basket": "«Лукошко»"}
                say = f"Открываю {names[game]}." if game else "Давайте! Выбирайте игру."
                self.emit("window", do="play", game=game)  # сразу: игра — это и есть ответ (экзамен 25.10 не видел, что она открылась)
                self._say_quick(say, text)
        elif kind == "show":
            if ui:
                self._say_quick("Я здесь.", text, then=lambda: self.emit("window", do="show"))
            else:
                self._say_quick("Открываю.", text, then=self._ui_launch)
        else:
            where = "значок Dewiar в меню «Пуск»" if os.name == "nt" else "Dewiar в меню приложений"
            log.info("⏻ «%s» — выхожу из Dewiar", redact(text))
            self._say_quick(f"Отключаюсь. Включить снова — {where}.", text, then=self._voice_quit)
        return True

    def _voice_quit(self):
        """«Отключись» сказано: интерфейс получает «window: quit» и завершает всё сам. Интерфейса нет или он не
        справился за 4 с — ядро завершается само (служба systemd с Restart=on-failure после обычного выхода не
        поднимается; при следующем входе в систему или запуске Dewiar из меню — снова работает)."""
        self.emit("window", do="quit")
        if self.on_quit:
            threading.Timer(0.3 if not self.bridge.clients else 4.0, self.on_quit).start()

    def _ui_wake(self):
        """Имя услышано, а окна нет: интерфейс завершился (упал, его закрыли извне) — открыть его,
        чтобы ответ было видно. Только если интерфейс в этом запуске уже был (ядро без окон, например на сервере,
        окна не открывает) и не чаще раза в 30 с."""
        b = getattr(self, "bridge", None)
        if b is None or b.clients or not getattr(b, "seen", False):
            return
        now = time.monotonic()
        if now - getattr(self, "_ui_launched", -1e9) < 30:
            return
        self._ui_launched = now
        threading.Thread(target=self._ui_launch, daemon=True).start()

    def _ui_launch(self):
        """Открыть интерфейс (виджет) отдельным процессом -> True, если запущен. Linux: пускач /opt/dewiar/dewiar
        (он же донастроит службу), из исходников — ui/app.py. Служба systemd --user может не знать DISPLAY —
        тогда берём его из окружения пользовательского systemd (GNOME передаёт его туда при входе).
        Windows: интерфейс сам запускает ядро и следит за ним — отсюда не открываем."""
        if os.name == "nt":
            return False
        import sys
        root = Path(__file__).resolve().parent.parent
        env = dict(os.environ)
        if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
            try:
                out = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True, timeout=5).stdout
                for line in out.splitlines():
                    k, _, v = line.partition("=")
                    if k in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_CURRENT_DESKTOP"):
                        env.setdefault(k, v)
            except (OSError, subprocess.SubprocessError):
                pass
        if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
            log.info("Окно не открыть: нет экрана (DISPLAY)")
            return False
        launcher = root / "dewiar"
        cmd = ["/bin/sh", str(launcher)] if launcher.is_file() else [sys.executable, str(root / "ui" / "app.py")]
        env.pop("DEWIAR_BOX", None)                  # окна сами уйдут в свою коробку с потолком памяти (ui/app.py)
        try:
            import memcap                           # и не в коробке ядра: перезапуск ядра не должен закрывать окна
            subprocess.Popen(memcap.scope_cmd(cmd), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            log.info("Открываю виджет: окна не было")
            return True
        except OSError as e:
            log.warning("Окно не открылось: %s", e)
            return False

    def set_mute(self, on):
        """Микрофон выключен (кнопка в виджете или замок «Только кнопка» в «Безопасности»): имя не слушается, «говорить» —
        одна фраза."""
        self.muted = bool(on)
        if self.muted:
            self.cancel_turn()
        self.follow_up_until = 0.0
        self.set_state("muted" if self.muted else "idle")
        self.emit("muted", on=self.muted)
        return self.muted

    def snapshot(self):
        """Всё состояние для окна, только что подключившегося к ядру (ответ на «hello»)."""
        return {"state": self.state, "persona": self.s.get("persona"), "personas": self.personas.public(),
                "settings": self.s.snapshot(), "status": self.status, "muted": self.muted,
                "presets": LLM_PRESETS, "piper_voices": PIPER_VOICES, "voice_fx": voicefx.catalog(), "workspace": str(self.workspace.root), "tools": self.toolbox.catalog(),
                "version": VERSION, "update": self.updater.public(), "tasks": self.tasks.list(),
                "skills": self.skills.catalog(), "mcp": self.mcp.status(), "account": self.account.status(), "mail": self.mail.public(), "telegram": self.telegram.public(), "max": self.max.public(), "obsidian": self.obsidian.public(),
                "reminders": self.reminders_list(), "alarm": self._alarm_public(),
                "radio": self.radio.status(), "kids": self.kids_public(), "watch": self.watch_public(),
                "pending_import": provision.preview(self.pending_import, self.s.snapshot()) if self.pending_import else None}

    def command(self, cmd, a):
        """Выполнить команду окна cmd с аргументами a. -> данные для ответа; ValueError — понятная ошибка."""
        if cmd.startswith("kids_"):
            return self.kids_cmd(cmd, a)
        if cmd.startswith("fam_") and not (getattr(self, "kids", None) and self.kids.locked()):
            return self.family_cmd(cmd, a)
        kids = getattr(self, "kids", None)
        if kids and kids.locked() and _kids_blocked(cmd, a):
            raise ValueError("Детский режим: это может только взрослый — студия → «Дети», PIN родителя")
        if cmd in ("month_get", "month_say", "month_hide"):   # «Мой месяц с Лирой» (month.py)
            import month as M
            ym = str(a.get("ym") or "") or M.prev_ym()
            if cmd == "month_hide":
                self.s.update({"ui": {"month_hide": ym}})
                return {"ok": True}
            d = M.gather(self, ym)
            if cmd == "month_say":
                threading.Thread(target=self.ask, args=(M.context(d) + "\n\n" + M.PROMPT,), kwargs={"raw": True, "shown": f"📅 Мой {d['title']} с Лирой"},
                                 daemon=True).start()
            return dict(d, hidden=(self.s.get("ui") or {}).get("month_hide") == ym)
        if cmd in ("care_get", "care_remove", "care_set"):   # «Лира спросит потом» (care.py)
            if cmd == "care_remove":
                self.care.remove(str(a.get("id") or ""))
            if cmd == "care_set":
                self.s.update({"care": {"on": bool(a.get("on"))}})
            return {"on": (self.s.get("care") or {}).get("on", True) is not False, "items": self.care.public()}
        if cmd.startswith("ideas_"):             # «Идеи Лиры»: список, голос, своя идея (ideas.py → сайт)
            import ideas
            return ideas.command(self, cmd, a)
        if cmd.startswith("home_"):              # «Дома по Wi-Fi» (engine_home.py)
            return self.home_cmd(cmd, a)
        if cmd == "watch_get":                   # «Дозор» (engine_watch.py)
            return self.watch_public()
        if cmd == "watch_add":
            self.watch_add(a)
            return self.watch_public()
        if cmd == "watch_stop":
            self.watch_stop(str(a.get("id") or ""))
            return self.watch_public()
        if cmd == "mode_get":                    # режим Лиры: для меня, ребёнка, старших (engine_senior.py)
            return self.mode_public()
        if cmd == "mode_set":
            return self.mode_set(str(a.get("mode") or ""))
        if cmd == "senior_set":
            return self.senior_set(a)
        if cmd == "senior_med_add":
            return {"added": self.senior_med_add(a.get("text"), a.get("times") or []), **self.mode_public()}
        if cmd == "senior_test":                 # «Проверить» — присматривающим приходит пробное сообщение
            n = self._senior_send(f"Это Лира, помощница. {self.senior.who()} включила режим «Для старших» — сюда я буду "
                                  "писать, если что-то не так, и вечером — как прошёл день.")
            if not n:
                raise ValueError("не отправилось — у выбранных близких Dewiar ещё не открывался после приглашения")
            return {"sent": n}
        if cmd.startswith("team_"):
            return self.team_cmd(cmd, a)
        if cmd.startswith("client"):
            return self.clients_cmd(cmd, a)
        if cmd == "hello":
            return self.snapshot()
        if cmd == "sync_status":
            return self.sync_public()
        if cmd == "devices_get":                  # «Устройства» (0.56): все мои устройства и синхронизация
            return self.devices_public(fresh=a.get("fresh", True) is not False)
        if cmd == "device_rename":                # своё имя этого компьютера: «Рабочий», «Домашний»
            self.s.update({"sync": {"name": str(a.get("name") or "").strip()[:40]}})
            self.sync.soon.set()
            return self.devices_public(fresh=False)
        if cmd == "device_forget":                # убрать из списка (снова выйдет на связь — появится)
            import httpx
            tok, link, url = self.credentials()
            if not tok:
                raise ValueError("здесь нет входа в Dewiar")
            h = {"Authorization": "Bearer " + tok}
            if link and link != tok:
                h["X-Sync-Link"] = link
            r = httpx.post(url, params={"p": "/sync/forget", "device": self.sync.state.get("device", "")}, json={"id": str(a.get("id") or "")}, headers=h, timeout=15)
            if r.status_code != 200:
                raise ValueError(((r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("error") or {}).get("message") or f"сайт ответил {r.status_code}")
            return self.devices_public(fresh=True)
        if cmd == "brains_pull":                  # «Взять мозги с другого устройства» (конвертом своим устройствам)
            return self.brains_pull()
        if cmd == "brains_status":
            return self.brains_status()
        if cmd == "pair_claim":                   # «Ввести код»: это устройство — та же Лира
            from cloud import CloudError
            try:
                return self.pair_claim(str(a.get("code") or ""), a.get("url", ""))
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd == "sync_now":
            from sync import SyncError
            try:
                self.sync.run_once()
            except SyncError as e:
                self.sync.status.update(ok=False, error=str(e), at=int(time.time()))
            if getattr(self, "home_sync", None) is not None and self.homehub and self.homehub.running():
                self.home_sync.soon.set()                # и телефонам по Wi-Fi (engine_home.py)
            return self.sync_public()
        if cmd == "sync_set":
            on = bool(a.get("on"))
            self.s.update({"sync": {"enabled": on}})
            if on and not any(t.name == "sync" for t in threading.enumerate()):     # поток синхронизации — один на ядро
                threading.Thread(target=self.sync.loop, args=(self.stopping,), name="sync", daemon=True).start()
            return self.sync_public()
        if cmd == "models_status":                # «Слух» и «Голос»: что скачано на этом компьютере
            return self.models_status()
        if cmd == "models_get":
            return self.models_get(str(a.get("key") or ""))
        if cmd == "sync_e2e":                     # шифрование синхронизации на устройстве (core/synckey.py)
            self.sync.e2e_enable(bool(a.get("on")))
            return self.sync_public()
        if cmd.startswith("knowledge_"):         # «Знания» на этом компьютере
            kn = self.knowledge
            if cmd == "knowledge_add":
                import base64
                raw = a.get("b64", "")
                raw = raw.split(",", 1)[1] if raw.startswith("data:") else raw
                rel = kn.add(a.get("name", ""), base64.b64decode(raw))
                self.emit("tools", tools=self.toolbox.catalog())
                return {"added": rel, "files": kn.list()}
            if cmd == "knowledge_remove":
                kn.remove(a.get("path", ""))
                self.emit("tools", tools=self.toolbox.catalog())
                return kn.list()
            if cmd == "knowledge_search":
                return kn.search(a.get("query", ""))
            if cmd == "knowledge_open":
                from tools import launch
                launch(["xdg-open", str(kn.root)])
                return str(kn.root)
            if cmd == "knowledge_open_file":           # источник под ответом: открыть файл (только из индекса поиска)
                p = kn.file_path(a.get("key", ""))
                if p is None:
                    raise ValueError("этого файла больше нет")
                from tools import launch
                launch(["xdg-open", str(p)])
                return str(p)
            if cmd in ("knowledge_folders", "knowledge_folder_add", "knowledge_folder_remove"):   # свои папки для поиска
                cur = [str(x) for x in (self.s.get("knowledge", "folders") or [])]
                if cmd != "knowledge_folders":
                    path = str(Path(os.path.expanduser(str(a.get("path") or "").strip())).resolve()) if a.get("path") else ""
                    if cmd == "knowledge_folder_add":
                        if not path or not Path(path).is_dir():
                            raise ValueError("такой папки нет")
                        if Path(path) in (Path.home(), Path(Path.home().anchor)) or len(Path(path).parts) <= 1:
                            raise ValueError("весь диск или домашнюю папку целиком не берём — выберите папку с документами")
                        cur = cur + [path] if path not in cur else cur
                    else:
                        cur = [x for x in cur if x != path and str(Path(x).resolve()) != path]
                    self.s.update({"knowledge": {"folders": cur}})
                    kn.kick.set()
                    self.emit("tools", tools=self.toolbox.catalog())
                return kn.folders_state()
            return {"folder": str(kn.root), "files": kn.list()}
        if cmd == "report":
            return self.save_report()
        if cmd == "report_send":
            return self.report_send(a.get("note", ""))
        if cmd == "report_auto":                               # согласие на отчёты при сбое (из предложения в виджете/студии)
            self.s.update({"report": {"auto": bool(a.get("on"))}})
            return {"auto": bool(a.get("on"))}
        # жалобы (core/health.py): снимок экрана до открытия студии, отправка, мои жалобы и помощники проекта
        if cmd == "bug_shot":
            return self.bug_shot(a.get("image"))
        if cmd == "bug_state":
            return self.bug_state()
        if cmd == "complaint_send":
            return self.complaint_send(a.get("note", ""), a.get("who", ""), bool(a.get("shot", True)))
        # суфлёр (core/prompter.py): окно ui/prompter.html
        if cmd.startswith("prompter_"):
            pr = self.prompter
            if cmd == "prompter_state":
                return pr.public()
            if cmd == "prompter_start":
                return pr.start(a.get("title", ""), a.get("goal", ""), a.get("mode", "auto"), a.get("them", True), a.get("me", True),
                                a.get("knowledge", False), a.get("keep_text", False), a.get("place", "online"), a.get("nudge", True))
            if cmd == "prompter_voice":                    # голос владельца: start — записать, stop — сохранить, forget
                act = a.get("action", "start")
                if act == "start":
                    return pr.enroll_start()
                if act == "forget":
                    return pr.enroll_forget()
                return pr.enroll_stop(save=act != "cancel")
            if cmd == "prompter_stop":
                return pr.stop(summary=a.get("summary", True))
            if cmd == "prompter_pause":
                return pr.pause(a.get("on", True))
            if cmd == "prompter_hint":
                return pr.hint(a.get("q", ""), "button")
            if cmd == "prompter_file":
                import base64
                raw = a.get("data") or ""
                data = base64.b64decode(raw.split(",", 1)[1] if raw.startswith("data:") else raw) if raw else None
                return pr.add_file(a.get("name", ""), data=data, path=a.get("path", ""))
            if cmd == "prompter_file_remove":
                return pr.remove_file(a.get("name", ""))
            if cmd == "prompter_meetings":                 # итоги прошлых встреч — студия, «Суфлёр»
                d = self.workspace.ensure() / "Встречи"
                fs = sorted(d.glob("*.md"), reverse=True)[:40] if d.is_dir() else []
                return [{"name": f.stem, "path": f"Встречи/{f.name}", "size": f.stat().st_size} for f in fs]
            if cmd == "prompter_meeting_remove":           # студия, «Прошлые встречи» → корзина (отзыв 17.10: «как удалить прошлую встречу?»)
                rel = str(a.get("path") or "")
                if not rel.startswith("Встречи/") or "/" in rel[len("Встречи/"):] or not rel.endswith(".md"):
                    raise ValueError("это не итог встречи")
                return self.workspace.remove(rel)
            if cmd == "prompter_open":
                self.emit("prompter", kind="open")
                return True
            raise ValueError("неизвестная команда суфлёра")
        if cmd == "complaints_seen":
            return self.complaints_seen()
        if cmd == "complaints":
            if a.get("check"):
                try:
                    self.complaints_check()
                except Exception as e:  # noqa: BLE001
                    log.info("🐞 ответы на жалобы: %s", e)
            return self.complaints_view(fresh=bool(a.get("check")))
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
                if a.get("id") and not val:             # правка без нового пароля — пароль прежний
                    old = self.vault.get(a["id"])
                    val = old["value"] if old else ""
                x = self.vault.put(a.get("name", ""), val, a.get("note", ""), a.get("id") or None,
                                   login=a.get("login"), url=a.get("url"))
                return {"item": x, "items": self.vault.list()}
            if cmd == "vault_delete":
                self.vault.delete(a.get("id", ""))
                return {"items": self.vault.list()}
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
                c.seen(str(a.get("section") or ""))
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
            if a.get("all"):
                return {"version": VERSION, "releases": news.releases("", VERSION)}
            if not seen:                              # первый раз с этой функцией: новая установка — молчим, обновились — показываем
                if (self.s.get("ui", "welcome") or "") != "done":
                    self.s.update({"ui": {"news_seen": VERSION}})
                    return {"version": VERSION, "releases": []}
            return {"version": VERSION, "releases": news.releases(seen, VERSION) if seen != VERSION else []}
        if cmd in ("done", "done_add", "done_undo", "done_reminder"):    # «Дела»: сделанное и достижения (студия, done.py)
            return self._done_cmd(cmd, a)
        if cmd in ("reminders", "reminder_add", "reminder_update", "reminder_cancel", "alarm_ack", "alarm_snooze",
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
                elif cmd == "pbot_try":                     # как персонаж ответит незнакомцу — без Telegram
                    q = str(a.get("text") or "").strip()
                    if len(q) < 2:
                        raise ValueError("напишите вопрос, как его задал бы посетитель")
                    try:
                        r = {"answer": pb.test_answer(q)}
                        self._course_did("pbot_try")
                    except Exception as e:  # noqa: BLE001
                        raise ValueError(f"модель не ответила: {e}") from e
                else:
                    r = pb.public()
                    r["personas"] = [{"id": x["id"], "name": x.get("name", ""), "color": x.get("color", ""), "style": x.get("style", ""),
                                      "avatar_url": x.get("avatar_url") or "", "kb": len(x.get("knowledge") or [])}
                                     for x in self.personas.public() if not x.get("kids")]
            except TelegramError as e:
                raise ValueError(str(e)) from e
            return r
        if cmd.startswith("tg_"):                # Telegram: подключить бота, код владельца, проверка, отключить
            from telegram import TelegramError
            tg = self.telegram
            try:
                if cmd == "tg_connect":
                    r = tg.connect(a.get("token", ""), a.get("api", ""))
                elif cmd == "tg_connect_shared":            # общий бот Dewiar — через аккаунт сайта
                    # без аккаунта — по ключу этого компьютера; адреса пробуем по очереди: из настроек, с сайта
                    # аккаунта, общий dewiar.pro
                    from telegram import SHARED_URL
                    urls = [u for u in (self.s.get("telegram_url"), self.account.service_url("tg"), SHARED_URL) if u]
                    errs = []
                    for u in dict.fromkeys(urls):
                        try:
                            r = tg.connect_shared(u)
                            break
                        except TelegramError as e:
                            log.warning("Telegram: %s — %s", u, e)
                            errs.append((u, e))
                    else:
                        from urllib.parse import urlparse
                        u, e = errs[-1]                      # общий адрес — последний, его ошибка самая показательная
                        host = urlparse(u).netloc or u
                        hint = ""
                        if "refused" in str(e).lower() or "name or service" in str(e).lower() or "timed out" in str(e).lower():
                            px = [k for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy") if os.environ.get(k)]
                            hint = (f" Компьютер не смог связаться с {host}. Откройте в браузере этого компьютера {u} — если "
                                    "страница не открывается, дело в сети (фильтр, VPN, роутер)" +
                                    (f"; в системе задан прокси ({px[0]}) — возможно, он не работает" if px else "") + ".")
                        raise TelegramError(f"{e}.{hint}")
                elif cmd == "tg_sync":                      # без компьютера: обменяться с сервером сейчас
                    n = self.tg_sync()
                    r = dict(tg.public(), got=n)
                elif cmd == "tg_set":
                    r = tg.set(a.get("patch") or {})
                    self._tg_sync_soon.set()                # сервер сразу узнает новые настройки (например, «отвечать без компьютера»)
                elif cmd == "tg_proxy":                     # Telegram заблокирован — ходить к нему через прокси
                    r = tg.set_proxy(a.get("proxy", ""))
                elif cmd == "tg_new_code":
                    r = tg.new_code()
                elif cmd == "tg_test":
                    tg.test()
                    r = tg.public()
                elif cmd == "tg_forget":
                    r = tg.forget()
                else:
                    r = tg.public()
            except TelegramError as e:
                raise ValueError(str(e)) from e
            if cmd in ("tg_connect", "tg_connect_shared", "tg_forget", "tg_new_code"):
                self.emit("tools", tools=self.toolbox.catalog())
            return r
        if cmd == "memory_graph":                # «Память»: граф заметок, фактов, дневника, документов, навыков
            from graph import build
            try:
                kfiles = [f["path"] for f in self.knowledge.list()]
            except Exception:  # noqa: BLE001
                kfiles = []
            return build(self.workspace.ensure(), skills=self.skills.catalog(), user_name=self.s.get("user_name") or "",
                         knowledge_files=kfiles)
        if cmd in ("exam_traces", "exam_traces_remove"):   # следы экзамена в «Обо мне», заметках, расходах (examtrace.py)
            import examtrace
            if cmd == "exam_traces":
                return examtrace.find(self.workspace, self.money, self.done)
            n = examtrace.remove(self.workspace, self.money, self.done, list(a.get("items") or []))
            log.info("🧹 записи экзамена убраны: %s", n)     # удаление уйдёт ближайшей синхронизацией — и с телефона тоже
            return {"removed": n}
        if cmd == "persona_memory":               # своя память у персонажа (0.56): {name, own}
            return self.persona_memory_set(str(a.get("name") or ""), bool(a.get("own")))
        who = str(a.get("who") or "") if cmd.startswith("memory_") else ""      # студия: «Общая» или своя память персонажа
        if who and who not in self.own_memory():
            who = ""
        if cmd == "memory_get":
            return self.workspace.memory_get(who=who)
        if cmd == "memory_set":
            return self.workspace.memory_set(a.get("text", ""), who=who)
        if cmd in ("memory_view", "memory_find", "memory_add", "memory_forget"):   # Память 2.0: страницы, поиск по смыслу
            import memory as MEM
            if cmd == "memory_view":
                return dict(MEM.view(self.workspace.memory_get(who=who)), last=getattr(self, "_mem_last", None), who=who, own=self.own_memory())
            if cmd == "memory_find":
                return MEM.find(str(a.get("q") or ""), self.workspace.memory_get(who=who))
            if cmd == "memory_add":
                return self.workspace.remember(str(a.get("text") or ""), who=who)
            return self.workspace.memory_set(MEM.forget(self.workspace.memory_get(who=who), int(a.get("i", -1))), who=who)
        if cmd.startswith("mm_"):                  # «Музыка»: своя папка (engine_mymusic.py)
            return self.mine_command(cmd, a)
        if cmd.startswith("account_"):           # аккаунт сайта: вход, выход, проверка
            from account import AccountError
            try:
                if cmd == "account_login":
                    self._net_try = a.get("server") or ""       # свой сайт ещё не сохранён в аккаунте — но тоже через прокси (_net_conf)
                    r = self.account.login(a.get("server"), a.get("login"), a.get("password"))
                    self.telegram.refresh_token(self.account.token())

                    def after_login():                     # модели и речь по аккаунту — сами, без настроек (в фоне: ходит в сеть)
                        self._account_cloud()
                        self._ensure_brain("вход аккаунтом")
                    threading.Thread(target=after_login, daemon=True).start()
                elif cmd == "account_logout":
                    st = self.s.get("stt")
                    if st.get("engine") == "remote" and st.get("remote", {}).get("from_account"):
                        self.s.update({"stt": {"engine": self._stt_local(), "remote": {"from_account": False, "api_key": ""}}})
                        self.apply_engines()               # вышли из аккаунта — распознаём снова у себя
                    tt = self.s.get("tts")
                    if tt.get("engine") == "remote" and tt.get("remote", {}).get("from_account"):
                        self.s.update({"tts": {"engine": self._tts_local(), "remote": {"from_account": False, "api_key": ""}}})
                        self.apply_engines()               # и говорим своим голосом
                    if self.s.get("cloud", "account"):         # модели облака были по аккаунту — убираем вместе с ним
                        self.cloud.forget()
                        if self.s.get("stt", "engine") == "remote" and self.s.get("stt", "remote", "cloud"):
                            self.s.update({"stt": {"engine": self._stt_local(), "remote": {"cloud": False}}})
                            self.apply_engines()
                        if self.s.get("tts", "engine") == "remote" and self.s.get("tts", "remote", "cloud"):
                            self.cloud.set_tts(False, self._tts_local())
                            self.apply_engines()
                        self.emit("settings", settings=self.s.snapshot())
                    if self.telegram.uses_account():           # общий бот через аккаунт — отключаем (по ключу — остаётся)
                        self.telegram.forget()
                        self.emit("telegram", **self.telegram.public())
                    r = self.account.logout()
                elif cmd == "account_stt":                # «Распознавание на сервере Dewiar» — вкл/выкл
                    if a.get("on"):
                        url = self.account.service_url("stt")
                        if not url:
                            raise AccountError("на сайте нет распознавания речи (или не выполнен вход)")
                        self.s.update({"stt": {"engine": "remote", "remote": {"base_url": url, "api_key": self.account.token(),
                                                                              "model": "gigaam-v3", "language": "ru",
                                                                              "from_account": True}}})
                    else:
                        self.s.update({"stt": {"engine": self._stt_local(), "remote": {"from_account": False}}})
                    self.apply_engines()
                    self.emit("settings", settings=self.s.snapshot())
                    r = self.account.status()
                elif cmd == "account_tts":                # «Голос с сервера Dewiar» — вкл/выкл
                    if a.get("on"):
                        url = self.account.service_url("tts")
                        if not url:
                            raise AccountError("на сайте нет синтеза речи (или не выполнен вход)")
                        self.s.update({"tts": {"engine": "remote", "remote": {
                            "base_url": url, "api_key": self.account.token(), "model": a.get("model") or "",
                            "sample_rate": 24000, "from_account": True}}})
                    else:
                        self.s.update({"tts": {"engine": self._tts_local(), "remote": {"from_account": False}}})
                    self.apply_engines()
                    self.emit("settings", settings=self.s.snapshot())
                    r = self.account.status()
                elif cmd == "account_check":
                    r = self.account.check()
                elif cmd == "account_ask":
                    return self.account.ask(a.get("question", ""))
                else:
                    r = self.account.status()
            except AccountError as e:
                raise ValueError(str(e)) from e
            self.emit("account", account=r)
            self.emit("tools", tools=self.toolbox.catalog())
            return r
        if cmd == "quit":                       # «Выход» из значка в трее (Windows): ядро завершается само, чуть позже — чтобы успеть ответить
            if self.on_quit:
                threading.Timer(0.2, self.on_quit).start()
            return True
        if cmd == "say":
            if getattr(self, "lat", None) is not None:
                self.lat.drop()                  # набранный вопрос — не голосовой: задержку голоса не меряем
            # картинки (вставленные, снимок экрана) — как файлы: сохраняются во «Входящие» и видны в ленте «Чата»
            images = []
            files = list(a.get("files") or [])
            for k, im in enumerate(([a["image"]] if a.get("image") else []) + list(a.get("images") or [])):
                mime = im[5:im.index(";")] if im.startswith("data:") and ";" in im[:40] else "image/jpeg"
                ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(mime, ".jpg")
                files.append({"name": time.strftime("Картинка %d.%m %H-%M-%S") + (f" ({k + 1})" if k else "") + ext, "b64": im})
            text = a.get("text", "")
            if files and text.strip() and self._reminder_with_files(text, files):
                return True                      # «напомни завтра в 10» + снимки — напоминание с картинками, без модели
            if files:
                text = self._attach_files(text, files, images)
            self.ask(text, images)
            return True
        if cmd == "screenshot_attach":               # кнопка «снимок экрана» в поле вопроса
            from eyes import EyesError, capture_screen, prepare
            from tools import desktop_env
            try:
                b64, _, _ = prepare(capture_screen(desktop_env()))
            except EyesError as e:
                raise ValueError(str(e)) from e
            return "data:image/jpeg;base64," + b64
        if cmd == "calib_start":
            pid = a.get("persona") or self.s.get("persona")
            p = self.personas.get(pid)
            self.cancel_turn()
            self.calib = {"pid": pid, "name": p["name"], "samples": [], "need": int(a.get("n", 3))}
            self.follow_up_until = 0
            self.set_state("listening")
            self.emit("calib", step="listen", n=0, need=self.calib["need"], name=p["name"])
            return True
        if cmd == "calib_cancel":
            self.calib = None
            self.set_state("idle")
            return True
        if cmd == "calib_reset":
            self.personas.set_heard(a.get("persona") or self.s.get("persona"), {})
            self.voiceprints.forget(a.get("persona") or self.s.get("persona"))
            self.build_spotter()
            self.emit("personas", personas=self.personas.public())
            return True
        if cmd == "cameras":
            from eyes import list_cameras
            return list_cameras()
        if cmd == "game_mark":                          # «Досуг» открыл игру (pad.js gameOpen) или закрыл её (game: "")
            gm = str(a.get("game") or "")[:20]
            self._game_on = (gm, time.monotonic()) if gm else None
            return {"game": gm}
        if cmd == "game_say":                           # игра сказала итог хода («Бэ пять — мимо. Стреляю: …») — вслух, без модели
            said = getattr(self, "_game_said", "") or "«Морской бой»"
            self._game_said = ""
            self._say_quick(str(a.get("text") or "")[:400], said, keep=False)
            return True
        if cmd == "ptt":
            # 28.10 (владелец, Ubuntu): «сработала сама, я быстро жму на аватарку, а она ещё 1–2 раза пытается слушать».
            # Судорожные нажатия: первое останавливало, а следующее попадало в «тишину» и снова включало слушание; голос из
            # того же разговора будил её опять. Теперь: нажатие в течение PTT_CALM с после остановки — тоже «стоп»; слушание
            # или ответ, начатые голосом, остановили кнопкой — минуту не откликаемся на голос (кнопка работает всегда).
            now = time.monotonic()
            if now - getattr(self, "_ptt_stop_at", 0.0) < self.PTT_CALM and self.state not in ("speaking", "thinking", "listening"):
                self._ptt_stop_at = now
                return "sleep"
            if self.muted and self.state not in ("speaking", "thinking"):
                self._mute_pass = True                      # нажали «говорить» при выключенном микрофоне — одна фраза, и снова тихо
            if self.state in ("speaking", "thinking", "listening"):
                self._ptt_stop_at = now
                by_voice = now - (getattr(self, "wake_time", 0.0) or 0.0) < 25   # начато голосом, а не кнопкой
                if self.state == "listening":
                    self.go_sleep("кнопка", media=False)     # второе нажатие — перестать слушать
                else:
                    self.interrupt("кнопка", follow=False)   # быстро нажал — замолчал и уснул
                    self.follow_up_until = 0.0
                    self.play_tone("sleep")
                if by_voice:
                    # почти наверняка ложное срабатывание (фон, разговор рядом, видео): минуту не просыпаемся от голоса,
                    # иначе тут же «опять начинает» (отзывы 14.10 и 28.10). Кнопка — работает.
                    self._quiet_until = now + 60
                    self.wake_time = 0.0
                    log.info("🤫 Остановили кнопкой то, что началось по голосу, — минуту не откликаюсь на голос")
                    quiet = "Минуту не откликаюсь на голос — позвать можно нажатием на лицо."
                    self.note(quiet)

                    def unquiet():
                        if self.status.get("note") == self._g(quiet):
                            self.note("")
                    threading.Timer(60, unquiet).start()
                return "sleep"
            self.listen_for_command(8)
            return "listening"
        if cmd == "chat_list":                            # «Чат» студии: лента переписки, старые сверху; before — подгрузить раньше
            return self.chatlog.page(a.get("before"), int(a.get("limit") or 80), str(a.get("q") or ""))
        if cmd == "chat_clear":
            self.chatlog.clear()
            return True
        if cmd == "hold_start":                           # диктовка удержанием: держат кнопку или пробел — говорят сколько нужно
            return self.hold_start(int(a.get("back_ms") or 400), int(a.get("max_s") or 600))
        if cmd == "hold_end":
            return self.hold_end(bool(a.get("cancel")))
        if cmd == "stop":
            self.interrupt("кнопка", follow=False)
            return True
        if cmd == "mute":
            return self.set_mute(bool(a.get("on")))
        if cmd == "text_mode":
            # YouTube 26.10: «выключил микрофон и синтез речи… для чисто текстового режима не очень удобно — добавить
            # переключение в текстовый режим (без распознавания, без синтеза, с инструментами в чате)». Включили —
            # микрофон и голос выключены (прежний голос запомнен), вопросы «выполнить?» и шаги — в «Чате» студии.
            on = bool(a.get("on"))
            ui = self.s.get("ui") or {}
            if on:
                prev = self.s.get("tts", "engine")
                self.s.update({"ui": {"text_mode": True, "text_prev": prev if prev and prev != "off" else (ui.get("text_prev") or "")},
                               "tts": {"engine": "off"}})
                self.set_mute(True)
            else:
                self.s.update({"ui": {"text_mode": False}, "tts": {"engine": ui.get("text_prev") or self._tts_local()}})
                if self.s.get("privacy", "mic") != "button":
                    self.set_mute(False)
            try:
                self.apply_engines()
            except Exception as e:  # noqa: BLE001
                log.info("Движки после текстового режима: %s", e)
            self.emit("settings", settings=self.s.snapshot())
            return {"on": on, "tts": self.s.get("tts", "engine")}
        if cmd == "security_state":                       # студия → «Безопасность»: стоп-кран, схема, замки, журнал (security.py)
            import security
            return security.state(self)
        if cmd == "security_set":
            import security
            r = security.set_(self, a)
            self.apply_engines()
            self.emit("settings", settings=self.s.snapshot())
            self.emit("security", local_only=r["state"]["local_only"])
            return r
        if cmd == "persona_set":
            self.switch_persona(a["id"])
            return True
        if cmd == "persona_save":
            pid = self.personas.save(a["persona"])
            p = self.personas.get(pid)
            miss = missing_words(self.vosk_dir, p.get("wake", [])) if self.vosk_dir else []   # слух ещё не готов — проверим потом
            self.build_spotter()
            self.emit("personas", personas=self.personas.public())
            if any(b.get("kind") == "folder" for b in p.get("knowledge") or []) and getattr(self, "knowledge", None) is not None:
                self.knowledge.kick.set()                  # папку со знаниями персонажа — прочитать сразу
            return {"id": pid, "missing": miss}
        if cmd == "gallery":
            return self.personas.gallery()
        if cmd == "gallery_add":
            pid = self.personas.gallery_add(a.get("id", ""))
            self.build_spotter()
            self.emit("personas", personas=self.personas.public())
            threading.Thread(target=self.ensure_voice, args=(pid,), daemon=True).start()
            return {"id": pid, "gallery": self.personas.gallery()}
        if cmd == "persona_delete":
            self.personas.delete(a["id"])
            # разговор удалённого — в архив: новый персонаж с тем же именем (и тем же id) начнёт с чистого листа
            for m in self.history:
                if m.get("who") == a["id"]:
                    m["who"] = a["id"] + "~удалён"
            try:
                self.conv.save(self.history)
            except Exception:  # noqa: BLE001
                pass
            if self.s.get("persona") not in {p["id"] for p in self.personas.all()}:
                from personas import DEFAULT
                self.switch_persona(DEFAULT)
            self.build_spotter()
            self.emit("personas", personas=self.personas.public())
            return True
        if cmd == "settings_save":
            before = self.s.snapshot()
            self.s.update(a["patch"])
            after = self.s.snapshot()
            if "audio" in a["patch"] and hasattr(self, "_end_frames"):
                self._pause_apply()                              # пауза конца фразы — сразу, без перезапуска слуха
            if before["llm"].get("active") != after["llm"].get("active") or \
                    before["llm"].get("profiles") != after["llm"].get("profiles"):
                self.probe_tools_bg()
            if before["llm"].get("active") != after["llm"].get("active"):
                self._brain_manual = time.monotonic()           # модель выбрали сами — автоматика час её не трогает
                if after["llm"].get("auto_from"):
                    self.s.update({"llm": {"auto_from": ""}})
            if before["tts"].get("engine") != after["tts"].get("engine") and "engine" in (a["patch"].get("tts") or {}) \
                    and "auto_piper" not in (a["patch"].get("tts") or {}) and after["tts"].get("auto_piper"):
                self.s.update({"tts": {"auto_piper": 0}})       # голос выбрали сами — автоматика больше не решает
            if before["all_names"] != after["all_names"]:
                self.build_spotter()
            if before["audio"]["input"] != after["audio"]["input"] or \
               before["audio"]["output"] != after["audio"]["output"] or \
               before["audio"]["echo_cancel"] != after["audio"]["echo_cancel"] or \
               before["audio"].get("headphones") != after["audio"].get("headphones"):
                self.restart_audio.set()                         # устройства звука меняются только перезапуском потока звука
            self.apply_engines()
            self.voiceprints.sensitivity = float(self.s.get("audio", "name_sensitivity") or 1.0)
            self.mcp.reconcile()
            if isinstance(self.stt, GigaAMSTT) and not self.stt.ready and not self.stt.loading:
                threading.Thread(target=self._background_loads, daemon=True).start()
            elif after["tts"]["engine"] == "piper":
                threading.Thread(target=self.ensure_voice, args=(after["persona"],), daemon=True).start()
            self.emit("settings", settings=after)
            return after
        if cmd == "llm_test":
            prof = a.get("profile") or {}
            r = test_profile(prof)
            if r.get("tools_mode"):
                key = self._tools_key(dict(prof, model=prof.get("model") or ""))
                # проверка заодно узнала, как этот сервер принимает инструменты, — запомним, чтобы не проверять снова
                self.s.update({"llm": {"tools_modes": {key: r["tools_mode"]}}})
            return r
        if cmd == "llm_models":
            return list_models(a.get("profile") or {})
        if cmd == "llm_economy_suggest":                  # экономный режим: недорогая модель того же сервиса (economy.py)
            import economy
            pr = a.get("profile") or {}
            try:
                ms = list_models(pr)
            except Exception as e:  # noqa: BLE001
                return {"model": "", "error": str(e)[:200]}
            return {"model": economy.suggest(ms, pr.get("model") or ""), "count": len(ms)}
        if cmd == "llm_no_chat":                          # №258: в списке нет ни одной модели для разговора — что делать
            from llm import no_chat_help
            return no_chat_help((a.get("profile") or {}).get("base_url", ""), a.get("models") or [])
        if cmd in ("cloud_usage", "cloud_topup", "cloud_topup_send", "cloud_models", "cloud_model", "cloud_stt", "cloud_tts", "cloud_fallback"):
            from cloud import CloudError
            try:
                if cmd == "cloud_usage":
                    return self.cloud.usage()
                if cmd == "cloud_topup":
                    return self.cloud.topup_info()
                if cmd == "cloud_topup_send":
                    return self.cloud.topup_request(a.get("amount") or 0, a.get("note", ""), a.get("image", ""))
                if cmd == "cloud_models":
                    return self.cloud.models()
                if cmd == "cloud_model":
                    r = self.cloud.set_model(a.get("id", ""))
                elif cmd == "cloud_stt":
                    r = self.cloud.set_stt(bool(a.get("on")))
                    if not a.get("on") and self._stt_local() != "gigaam":
                        self.s.update({"stt": {"engine": self._stt_local()}})
                        r = self.s.get("stt")
                    self.apply_engines()
                elif cmd == "cloud_tts":                  # «Голос Dewiar» — тот же, что на телефоне
                    r = self.cloud.set_tts(bool(a.get("on")), self._tts_local())
                    self.apply_engines()
                else:
                    self.s.update({"llm": {"fallback": a.get("id") or ""}})
                    r = {"fallback": a.get("id") or ""}
                self.emit("settings", settings=self.s.snapshot())
                return r
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd in ("call_info", "call_sig", "call_ice", "call_fast", "call_done"):    # страница звонка (ui/call.html)
            from close import CloseError
            try:
                return self.close.call_cmd(cmd, a)
            except CloseError as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("close_"):                   # «Близкие» (close.py): студия
            from close import CloseError
            c = self.close
            try:
                if cmd == "close_state":
                    if a.get("hello") or not c.st.get("me"):
                        try:
                            c.hello()
                        except CloseError as e:
                            c.error = str(e)
                    return c.state()
                if cmd == "close_invite":
                    return c.invite(bool(a.get("renew")))
                if cmd == "close_peek":
                    return c.peek(a.get("link", ""))
                if cmd == "close_accept":
                    return c.accept(a.get("link", ""))
                if cmd == "close_refs":
                    return c.ref_map(a.get("rids") or [])
                if cmd == "close_ref":
                    return c.ref_close(a.get("rid", ""))
                if cmd == "close_offer":
                    return c.offer(a.get("pid", ""), a.get("yes"))
                if cmd == "close_remove":
                    return c.remove(a.get("pid", ""))
                if cmd == "close_forget":           # убрать сообщения у себя: mids — выбранные, без mids — всю переписку
                    mids = a.get("mids")
                    return c.forget(a.get("pid", ""), None if mids is None else list(mids))
                if cmd == "close_history":           # read: false — окно студии скрыто, «прочитано» не ставим
                    return c.history(a.get("pid", ""), mark_read=a.get("read", True) is not False)
                if cmd == "close_send":
                    files = list(a.get("files") or [])
                    if a.get("files_b64"):                # студия: файл, выбранный в окне, — во временную папку и отправить
                        import base64 as _b64
                        import re as _re
                        # 28.10 (владелец: «отправил фото в группу — не отображается»): файл лежал во временной папке
                        # программы, а студия показывает фото только из «Близких» — теперь отправленное хранится там же
                        out = Path(self.workspace.ensure()) / "Близкие" / "Отправленные" / time.strftime("%Y-%m-%d %H-%M-%S")
                        out.mkdir(parents=True, exist_ok=True)
                        for f in a["files_b64"][:5]:
                            name = _re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(f.get("name") or "файл"))[:120] or "файл"
                            (out / name).write_bytes(_b64.b64decode(f.get("b64") or ""))
                            files.append(str(out / name))
                    return c.send(a.get("pid", ""), a.get("text", ""), files)
                if cmd == "close_meet":             # «Встречи» в студии (studio/meet.js) — через то же пространство, что телефон
                    return c.meet(a.get("path", ""), a.get("body") or {})
                if cmd == "close_forward":          # «Переслать» (0.62): {pid — откуда, mid, to — кому: pid или gid}
                    return c.forward(a.get("pid", ""), a.get("mid", ""), a.get("to", ""))
                if cmd == "close_group":            # «Группы своих»: create / rename / icon / add / drop / leave / delete
                    return c.group(str(a.get("op") or ""), **{k: a[k] for k in ("gid", "name", "pids", "pid", "icon") if k in a})
                if cmd == "close_thumb":            # фото из переписки — картинкой в студии (0.61): только скачанное в «Близкие», до 6 МБ
                    import base64 as _b64
                    import mimetypes as _mt
                    bases = ((Path(self.workspace.root) / "Близкие").resolve(), (STATE_DIR / "close_out").resolve())   # и отправленное до 0.66
                    p = Path(str(a.get("path") or "")).resolve()
                    t = _mt.guess_type(p.name)[0] or ""
                    if not any(b in p.parents for b in bases) or not t.startswith("image/") or not p.is_file() or p.stat().st_size > 6 * 1024 * 1024:
                        return {"data": ""}
                    return {"data": f"data:{t};base64," + _b64.b64encode(p.read_bytes()).decode()}
                if cmd == "close_wave":             # 👋 с радара «Рядом»
                    return c.wave(a.get("pid", ""))
                if cmd == "close_react":            # реакция на сообщение (👍 ❤️ …)
                    return c.react(a.get("pid", ""), a.get("mid", ""), a.get("e", ""))
                if cmd == "close_call":
                    return c.call(a.get("pid", ""), bool(a.get("video")))
                if cmd == "close_name":
                    return c.set_name(a.get("name", ""))
                if cmd == "close_card":             # карточка «Я»: имя, о себе, фото, фото во «Встречах»
                    return c.set_card(**{k: a[k] for k in ("name", "about", "face", "face_meet") if k in a})
                if cmd == "close_face":             # фото близкого (или во «Встречах»: meet) -> data URI
                    return c.face(a.get("pid", ""), a.get("v", 0), meet=bool(a.get("meet")))
                if cmd == "close_speak":
                    self.s.update({"close": {"speak": bool(a.get("on"))}})
                    return {"speak": bool(a.get("on"))}
                if cmd == "close_poll":
                    c.soon.set()
                    return {"ok": True}
            except CloseError as e:
                raise ValueError(str(e)) from e
            raise ValueError("неизвестная команда «Близких»")
        if cmd in ("ref_info", "ref_use"):              # приглашения друзей (cloud.php ?p=/ref): мой код, кто пришёл, чужой код
            from cloud import CloudError, fetch
            token, _, base = self.credentials()
            if not token:
                raise ValueError("сначала подключите Dewiar: вход аккаунтом dewiar.pro или ключ")
            try:
                if cmd == "ref_info":
                    return fetch(base, token, "/ref")
                code = "".join(ch for ch in str(a.get("code", "")).upper() if ch.isalnum())
                if len(code) < 4:
                    raise ValueError("введите код из приглашения — 6 букв и цифр")
                r = fetch(base, token, "/ref/use", body={"code": code})
                try:
                    self.cloud.refresh()
                except Exception:  # noqa: BLE001
                    pass
                return r
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd in ("join_send", "join_check", "join_forget", "pair_new", "contact_get", "contact_set", "auto_join"):   # Dewiar по заявке и перенос кодом
            from cloud import CloudError
            try:
                if cmd == "contact_get":            # автоподключение (0.69): как к вам обращаться и как связаться — дополнить позже
                    return self.contact_get()
                if cmd == "contact_set":
                    return self.contact_set(a.get("name", ""), a.get("contact", ""))
                if cmd == "auto_join":
                    self.s.update({"cloud": {"auto_tried": 0}})
                    return {"ok": self.auto_join("кнопкой"), "llm": bool(self.s.get("llm", "active"))}
                if cmd == "join_send":
                    return self.join_send(a.get("name", ""), a.get("contact", ""), a.get("note", ""))
                if cmd == "join_check":
                    return self.join_check()
                if cmd == "join_forget":
                    self.s.update({"cloud": {"join": {"id": 0, "secret": "", "url": ""}}})
                    return True
                return self.pair_new()
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd in ("cloud_connect", "cloud_status", "cloud_forget"):
            from cloud import CloudError
            try:
                if cmd == "cloud_connect" and (a.get("use") or not (a.get("key") or "").strip()):
                    return self._cloud_use()             # «Отвечать моделями Dewiar»: своим ключом или по аккаунту
                if cmd == "cloud_connect":
                    key = (a.get("key") or "").strip()
                    if re.fullmatch(r"\d[\d\s-]{4,8}\d", key):          # 6 цифр — код с другого устройства
                        return self.pair_claim(key, a.get("url", ""))
                    r = self.cloud.connect(key, a.get("url", ""))
                    return self._cloud_connected(r, "ключ Dewiar")      # студия сразу видит новый профиль
                if cmd == "cloud_forget":
                    own_key = not self.s.get("cloud", "account")
                    was_active = self.s.get("llm", "active") == "dewiar-cloud"
                    r = self.cloud.forget()
                    if own_key and self.account.logged_in():   # убрали свой ключ, а вход аккаунтом есть — модели Dewiar по аккаунту
                        self._account_cloud(force_active=was_active, quiet=True)
                        r = self.cloud.status()
                    if self.s.get("stt", "engine") == "remote" and self.s.get("stt", "remote", "cloud"):
                        self.s.update({"stt": {"engine": self._stt_local(), "remote": {"cloud": False}}})
                        self.apply_engines()                 # ключа больше нет — распознаём у себя
                    if self.s.get("tts", "engine") == "remote" and self.s.get("tts", "remote", "cloud") and not self.s.get("cloud", "key"):
                        self.cloud.set_tts(False, self._tts_local())
                        self.apply_engines()                 # и говорим своим голосом
                    elif self.s.get("tts", "engine") == "remote" and self.s.get("tts", "remote", "cloud"):
                        self.cloud.set_tts(True)
                        self.apply_engines()                 # ключ сменился на вход аккаунтом — голос по нему
                    self.emit("settings", settings=self.s.snapshot())
                    return r
                return self.cloud.status(refresh=bool(a.get("refresh")))
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd in ("net", "net_proxy", "net_check", "net_dewiar", "net_reserve"):   # dewiar.pro заблокирован провайдером — прокси
            return self.net_cmd(cmd, a)
        if cmd == "device":
            if a.get("fresh"):                         # раздел «Голос» открыт — что умеет облако сейчас (озвучку могли включить)
                self._cloud_caps()
            return self.device_status()
        if cmd in ("av_status", "av_exclude", "av_copy"):     # Windows: антивирус и исключения для Dewiar
            import winav
            root = Path(__file__).resolve().parent.parent
            if cmd == "av_status":
                return winav.status(root)
            if cmd == "av_copy":
                return {"ok": winav.copy_text(winav.install_paths(root)[0])}
            return {"ok": winav.defender_exclude(winav.install_paths(root))}
        if cmd == "device_light":
            if not a.get("on"):                        # выключили сами — сам больше не включаю (тесно — только совет)
                self.s.update({"device": {"auto_light": False}})
            done = self.set_light(bool(a.get("on")))
            return dict(self.device_status(), done=done)
        if cmd == "probe_server":
            from llm import probe_server
            return probe_server(a.get("address", ""), a.get("port", ""))
        if cmd == "discover":                                   # «Найти Ollama или LM Studio»: выключенный сервер LM Studio — включить
            return discover_local(start=True)
        if cmd == "ws_tree":
            t = self.workspace.tree()
            o = self.obsidian.public()
            t["obsidian"] = {k: o.get(k) for k in ("connected", "name", "folder", "open", "last")}
            t["obsidian"]["folders"] = ["Заметки", "Дневник", "Память"] if o.get("connected") else []
            return t
        if cmd == "ws_delete_dir":                              # «Папка»: подпапку целиком — в корзину
            try:
                return self.workspace.remove_dir(a.get("path", ""))
            except (WorkspaceError, OSError) as e:
                raise ValueError(str(e)) from e
            except Exception as e:  # noqa: BLE001 — защита корзины
                raise ValueError(str(e)) from e
        if cmd.startswith("pad_"):                              # блокнот у виджета (ui/pad.html, core/pad.py)
            return self._pad_cmd(cmd, a)
        if cmd == "notes_list":                                 # «Заметки»: все заметки и поиск
            return self.workspace.notes(a.get("q", ""))
        if cmd == "note_meta":                                  # метки, цвет, «закрепить», «в архив» — в шапку заметки (0.58)
            return self.workspace.note_meta(a.get("path", ""), a.get("patch") or {})
        if cmd == "notes_import_keep":                          # перенос из Google Keep (архив Takeout или папка)
            import keep_import
            path = str(a.get("path") or "").strip()
            if not path or not Path(os.path.expanduser(path)).exists():
                raise ValueError("выберите архив Google Takeout (.zip) или распакованную папку")
            r = keep_import.import_keep(self.workspace, os.path.expanduser(path),
                                        progress=lambda i, n: self.emit("keep_import", i=i, n=n) if i % 20 == 0 else None)
            self.emit("notes_changed")
            return r
        if cmd == "link_meta":                                  # ссылка в заметке — карточкой: название, картинка, сайт
            lm = getattr(self, "_linkmeta", None)
            if lm is None:
                from linkmeta import LinkMeta
                lm = self._linkmeta = LinkMeta(STATE_DIR / "links.json")
            return lm.get(a.get("url", ""))
        if cmd in ("note_attach", "note_file"):                 # «Заметки»: фото и файлы к заметке, картинка для показа
            import base64
            try:
                if cmd == "note_file":
                    return self.workspace.note_file(a.get("path", ""))
                r = self.workspace.note_attach(a.get("path", ""), a.get("name", ""), base64.b64decode(a.get("b64", "") or ""))
                self.note_files_out(a.get("path", ""), [r["path"]])           # фото заметки — и на свой телефон
                return r
            except (WorkspaceError, OSError, ValueError) as e:
                raise ValueError(str(e)) from e
        if cmd == "ws_read":
            try:
                return self.workspace.read(a.get("path", ""))
            except WorkspaceError as e:
                raise ValueError(str(e)) from e
        if cmd in ("ws_write", "ws_new_note", "ws_rename", "ws_delete"):      # «Память»: редактор заметок
            try:
                if cmd == "ws_write":
                    r = self.workspace.write(a.get("path", ""), a.get("text", ""))
                elif cmd == "ws_new_note":
                    r = {"path": self.workspace.new_note(a.get("title", ""), a.get("folder") or "Заметки", a.get("text", ""))}
                elif cmd == "ws_rename":
                    r = {"path": self.workspace.rename(a.get("path", ""), a.get("title", ""))}
                else:
                    r = self.workspace.remove(a.get("path", ""))
            except (WorkspaceError, OSError) as e:
                raise ValueError(str(e)) from e
            except Exception as e:  # noqa: BLE001 — защита корзины и т. п.
                raise ValueError(str(e)) from e
            try:
                self.recall.invalidate()
            except Exception:  # noqa: BLE001
                pass
            return r
        if cmd == "ws_open":
            from tools import launch
            p = self.workspace.safe(a.get("path", "")) if a.get("path") else self.workspace.ensure()
            launch(["xdg-open", str(p)])
            return str(p)
        if cmd in ("soul_get", "soul_save", "soul_update", "soul_delete", "const_get", "const_save", "const_reset"):
            name = (a.get("persona") or "").strip() or self.persona_name()
            if cmd == "soul_delete":
                self.soul.delete_soul(name)
            elif cmd == "soul_save":
                self.soul.save_soul(name, a.get("text", ""))
            elif cmd == "soul_update":
                if not self.s.active_llm():
                    raise ValueError("нет модели — подключите её в «Мозге»")
                if not self.soul.update(name, force=True):
                    raise ValueError("душа уже обновляется — минутку")
                self.emit("soul", name=name)
            elif cmd == "const_save":
                self.soul.save_constitution(a.get("text", ""))
            elif cmd == "const_reset":
                self.soul.reset_constitution()
            if cmd.startswith("const_"):
                return {"text": self.soul.constitution(), "path": "Память/Конституция.md", "on": self.s.get("soul", "constitution") is not False}
            return self.soul.public(name)
        if cmd == "diary_list":
            return self.diary.entries()
        if cmd == "ctx_view":                                   # «О программе» → «Для отладки: что Лира сейчас учитывает»
            return self.ctx_view()
        if cmd in ("diary_entry_save", "diary_entry_delete"):     # «Дневник»: поправить или удалить запись (28.10)
            if cmd == "diary_entry_save":
                return self.diary.entry_save(a.get("day"), a.get("i", -1), a.get("text", ""), a.get("title"))
            return self.diary.entry_delete(a.get("day"), a.get("i", -1))
        if cmd == "diary_insight_drop":                         # «Дневник»: вывод ночи — не учитывать в разговоре
            return self.diary.drop_insight(a.get("i"))
        if cmd == "diary_write_now":                           # «Записать сейчас»: запись о сегодняшнем (или указанном) дне
            got = self.diary.write(a.get("day") or None, force=True)
            if not got:
                raise ValueError("запись уже пишется — минутку")
            self.emit("diary", **got)
            return got
        if cmd == "ws_export":                               # «Папка»: копия файла в «Загрузки» (страницу — и в PDF)
            import export as X
            try:
                src = self.workspace.safe(a.get("path", ""))
                out = X.export(src, X.page_title(src), a.get("fmt") or "file")
            except (WorkspaceError, X.ExportError) as e:
                raise ValueError(str(e)) from e
            if a.get("reveal", True) and not os.environ.get("DEWIAR_DRY_TOOLS"):
                X.reveal(out)
            return {"path": str(out), "name": out.name, "dir": str(out.parent)}
        if cmd == "ws_set_path":
            path = (a.get("path") or "").strip()
            self.s.update({"workspace": {"path": path}})
            self.workspace.ensure()
            self.skills.set_folder(self.workspace.root / "Навыки")
            self.workspace.sync_reminders(self.reminders.items)
            return str(self.workspace.root)
        if cmd == "update_status":
            return self.updater.public()
        if cmd == "self_check":
            return self.self_check()
        if cmd == "update_check":
            self.updater.check()
            return self.updater.public()
        if cmd == "tasks_list":
            return self.tasks.list()
        if cmd == "task_get":
            try:
                return self.tasks.detail(a.get("id"))
            except KeyError as e:                       # пакет 28.10: задачу уже удалили, а студия просит её — не сбой программы
                raise ValueError(str(e).strip("'\"")) from None
        if cmd == "task_create":
            t = self.tasks.create(a.get("title", ""), a.get("goal", ""), a.get("project", ""), start=a.get("start", True))
            return t.public()
        if cmd in ("task_export", "task_open_result"):        # результат задачи: скачать (HTML/PDF/как есть) или открыть
            import export as X
            t = self.tasks.get(a.get("id"))
            rel = str(a.get("path") or "")
            src = (t.dir / rel).resolve()
            if not rel or t.dir.resolve() not in src.parents:     # безопасность: только файлы внутри папки задачи (не «../»)
                raise ValueError("такого результата у задачи нет")
            if cmd == "task_open_result":
                if os.environ.get("DEWIAR_DRY_TOOLS"):
                    return {"opened": str(src)}
                X.open_file(src)
                return {"opened": str(src)}
            title = next((o.get("title") for o in t.data.get("outputs") or [] if o.get("path") == rel), "") or t.title
            try:
                out = X.export(src, title, a.get("fmt") or "file")
            except X.ExportError as e:
                raise ValueError(str(e)) from e
            if a.get("reveal", True) and not os.environ.get("DEWIAR_DRY_TOOLS"):
                X.reveal(out)
            return {"path": str(out), "name": out.name, "dir": str(out.parent)}
        if cmd in ("task_stop", "task_resume", "task_answer", "task_tell", "task_accept", "task_discard", "task_delete"):
            tid = a.get("id")
            if cmd == "task_tell":
                return self.tasks.tell(tid, a.get("text", "")).public()
            if cmd == "task_stop":
                return self.tasks.stop(tid).public()
            if cmd == "task_resume":
                return self.tasks.start(tid).public()
            if cmd == "task_answer":
                return self.tasks.answer(tid, a.get("text", "")).public()
            if cmd == "task_accept":
                return self.tasks.accept(tid)
            if cmd == "task_discard":
                return self.tasks.discard(tid)
            self.tasks.delete(tid)
            return True
        if cmd == "vosk_voices":
            if self.s.get("tts", "engine") == "vosk":
                self.ensure_vosk_tts()
            return {"ready": self.vosk_tts.ready, "loading": self._vosk_loading, "error": self.vosk_tts.error,
                    "speakers": self.vosk_tts.speakers}
        if cmd == "intro_start":                      # «Познакомиться» — знакомство голосом заново
            return self.intro_start()
        if cmd == "intro_stop":
            return self.intro_stop()
        if cmd == "voice_test":
            pid = a.get("persona") or self.s.get("persona")
            if pid != self.s.get("persona"):
                self.switch_persona(pid)
            p = self.personas.get(pid)
            text = a.get("text") or f"Привет! Я {p['name']}. {p.get('tagline', '')}."
            with self._turn_lock:
                self._cancel_locked()
                self.turn_n += 1
                turn = Turn(self.turn_n)
                self.turn = turn
            q = queue.Queue()
            q.put(text)
            q.put(None)

            def run():
                self.ensure_voice(pid)                 # скачать голос — уже не в обработчике нажатия
                vid = (a.get("voice") or {}).get("piper")
                if vid in PIPER_VOICES and not self.piper.has(vid):   # «Послушать» до сохранения: выбранный, а не прежний
                    try:
                        self.note(f"Скачиваю голос {PIPER_VOICES[vid]}…")
                        self.piper.mirror = self._mirror("piper")
                        self.piper.ensure(vid)
                        self.note("")
                    except Exception as e:  # noqa: BLE001
                        log.warning("Голос не скачался: %s", e)
                self._speak_worker(turn, q, fx_override=a.get("fx"), voice_override=a.get("voice"))
                with self._turn_lock:
                    if self.turn is turn:
                        self.turn = None
                        self.set_state("idle")
            threading.Thread(target=run, daemon=True).start()
            return True
        if cmd == "power_cancel":
            was = self.power.cancel()
            self.emit("power", cancelled=True)
            return {"cancelled": bool(was)}
        if cmd == "radio_status":
            return self.radio.status()
        if cmd == "radio_list":                   # свой список станций (с сайта или встроенный)
            return {"stations": self.music.stations(), "genres": self.music.genres(), "url": self.music.url()}
        if cmd == "radio_custom_list":                # свои радиостанции (№359): студия → «Музыка»
            return [x for x in (self.s.get("radio_custom") or []) if isinstance(x, dict)]
        if cmd == "radio_custom_add":
            try:
                st = self.radio_custom_save(a.get("name"), a.get("url"))
            except ValueError as e:
                raise ValueError(str(e)) from e
            if a.get("play"):
                self._play_station([dict(st, tags="своя", own=True)], "", "Включаю «{}».")
            return st
        if cmd.startswith("council_"):               # «Совет ИИ» (0.67, council.py)
            from council import CouncilError
            try:
                if cmd == "council_members":
                    return {"members": self.council.members(), "pick": self.council.default_pick(), "state": self.council.state(),
                            "history": self.council.history()}
                if cmd == "council_start":
                    return self.council.start(a.get("q"), a.get("pids"))
                if cmd == "council_stop":
                    return self.council.stop()
                if cmd == "council_state":
                    return self.council.state()
                if cmd == "council_history":
                    return self.council.history()
            except CouncilError as e:
                raise ValueError(str(e)) from e
        if cmd == "radio_home":                       # вкладка «Радио» в студии (0.64)
            return self.radio_home()
        if cmd == "radio_search":
            return self.radio_find(a.get("q"))
        if cmd == "radio_play":
            return self.radio_play_one(a)
        if cmd == "radio_fav":                        # ♥ на станции: в «Мои станции» (и голосом — «включи …»)
            if a.get("on", True):
                return self.radio_custom_save(a.get("name"), a.get("url"), a.get("logo"), a.get("tags"))
            self.s.update({"radio_custom": [x for x in (self.s.get("radio_custom") or []) if isinstance(x, dict) and x.get("url") != a.get("url")]})
            return True
        if cmd == "radio_custom_del":
            self.s.update({"radio_custom": [x for x in (self.s.get("radio_custom") or []) if isinstance(x, dict) and x.get("url") != a.get("url")]})
            return True
        if cmd == "radio_custom_play":
            st = next((x for x in (self.s.get("radio_custom") or []) if isinstance(x, dict) and x.get("url") == a.get("url")), None)
            if not st:
                raise ValueError("такой станции нет в списке")
            self._play_station([dict(st, tags="своя", own=True)], "", "Включаю «{}».")
            return True
        if cmd == "radio_stop":
            self.radio.stop()
            return self.radio.status()
        if cmd == "voices_warm":                       # открыли «Голос» — загрузить голоса заранее
            if self.s.get("tts", "engine") == "vosk" and not self.vosk_tts.ready:
                self.ensure_vosk_tts()
            return {"ready": self.vosk_tts.ready}
        if cmd == "devices":
            return list_devices()
        if cmd == "tools":
            return self.toolbox.catalog()
        if cmd == "confirm_answer":
            box = self.pending_confirm
            if box:
                box["answer"] = bool(a.get("ok"))
                box["always"] = bool(a.get("always"))         # кнопка «Всегда» (команды «только посмотреть» на сервере)
                box["event"].set()
            return True
        if cmd == "phone_home":                   # только умный дом — на телефон (QR в студии; ключ не уходит на сервер)
            import base64
            if not self.home.connected():
                raise ValueError("умный дом не подключён")
            raw = json.dumps({"dewiar": 1, "home": {"token": self.home.data.get("token", "")}}, separators=(",", ":")).encode("utf-8")
            return {"url": "dewiar://import?c=" + base64.urlsafe_b64encode(raw).decode().rstrip("=")}
        if cmd == "phone_config":                 # QR для телефона: мозг, слух, голос, умный дом — одним снимком камеры
            # безопасность: в ссылке открытым текстом ключи API и токен умного дома — QR показывать только владельцу;
            # формат dewiar://import?c=<base64url JSON без «=»> разбирает приложение (android/: MainActivity.java, app.js)
            import base64
            snap = self.s.snapshot()
            llm = snap.get("llm") or {}
            prof = (llm.get("profiles") or {}).get(llm.get("active")) or {}
            keep = {k: prof[k] for k in ("name", "kind", "base_url", "api_key", "model", "economy", "disable_thinking", "temperature", "cloud", "title") if prof.get(k) not in (None, "")}
            import net as _net
            keep["base_url"], was_local = _net.lan_url(keep.get("base_url", ""))   # 127.0.0.1 на телефоне — сам телефон (19.10)
            local_note = ""
            if was_local:
                local_note = ("Модель на этом компьютере. Чтобы телефон до неё дотянулся: в LM Studio — Developer → «Serve on Local "
                              "Network», в Ollama — переменная OLLAMA_HOST=0.0.0.0; телефон — в той же сети Wi-Fi."
                              if not re.search(r"//(127\.|localhost|0\.0\.0\.0)", keep["base_url"]) else
                              "Модель на этом компьютере, а адреса в домашней сети у него нет — телефон до неё не дотянется. Подключите в приложении облако или сервер.")
            out = {"dewiar": 1, "llm": {"active": "p", "profiles": {"p": keep}}, "persona": snap.get("persona", "lira")}
            if snap.get("user_name"):
                out["user_name"] = snap["user_name"]
            for sec in ("stt", "tts"):
                x = snap.get(sec) or {}
                if x.get("engine") == "remote" and (x.get("remote") or {}).get("base_url"):
                    r = x["remote"]
                    out[sec] = {"engine": "remote", "remote": {k: r[k] for k in ("base_url", "api_key", "model", "voice") if r.get(k)}}
            if self.home.connected():
                out["home"] = {"token": self.home.data.get("token", "")}
            raw = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return {"url": "dewiar://import?c=" + base64.urlsafe_b64encode(raw).decode().rstrip("="),
                    "apk": (self.s.get("updates", "url") or "https://dewiar.pro/dwrapp/latest.json").rsplit("/", 1)[0] + "/Dewiar.apk",
                    "brain": keep.get("name") or keep.get("base_url", ""), "local_note": local_note, "lan": was_local or bool(re.match(r"https?://(192\.168|10\.|172\.(1[6-9]|2\d|3[01])|localhost|127\.)", keep.get("base_url", "")))}
        if cmd == "config_export":
            return provision.export_settings(self.s.snapshot(), bool(a.get("secrets")),
                                             {"skills_note": [s["name"] for s in self.skills.catalog() if not s["builtin"]]})
        if cmd == "config_preview":
            return self._import(a)
        if cmd == "config_apply":
            return self._apply_import(a)
        if cmd == "config_pending":
            m = self.pending_import
            return provision.preview(m, self.s.snapshot()) if m else None
        if cmd == "tricks":                       # «Что я умею» в студии — data/tricks.json (тот же список, что на телефоне)
            return json.loads((Path(__file__).resolve().parent.parent / "data/tricks.json").read_text(encoding="utf-8"))
        if cmd == "skills":
            return self.skills.catalog()
        if cmd == "skill_install":
            if a.get("zip_b64"):
                import base64
                name = self.skills.install_zip(base64.b64decode(a["zip_b64"]), a.get("name", ""))
            elif a.get("text"):
                name = self.skills.install_text(a["text"])
            else:
                name = self.skills.install_url(a["url"])
            return {"name": name, "skills": self.skills.catalog()}
        if cmd == "skill_get":
            return self.skills.get(a["name"])
        if cmd == "skill_save":
            name = self.skills.save(a.get("name"), a.get("description"), a.get("body"), a.get("files"), a.get("old_name", ""))
            return {"name": name, "skills": self.skills.catalog()}
        if cmd == "skill_export":
            import base64
            return {"name": a["name"], "zip_b64": base64.b64encode(self.skills.export_zip(a["name"])).decode()}
        if cmd == "skill_draft":
            return self._draft_skill(a.get("idea", ""))
        if cmd == "skills_catalog":
            url = a.get("url") or self.s.get("skills", "catalog_url")
            if not url:
                raise ValueError("адрес каталога не указан")
            if a.get("url"):
                self.s.update({"skills": {"catalog_url": url}})
            return self.skills.catalog_fetch(url)
        if cmd == "skill_remove":
            self.skills.remove(a["name"])
            return self.skills.catalog()
        if cmd == "skill_toggle":
            off = set(self.s.get("skills", "disabled") or [])
            (off.discard if a.get("on") else off.add)(a["name"])
            self.s.update({"skills": {"disabled": sorted(off)}})
            return self.skills.catalog()
        if cmd == "skills_reload":
            self.skills.reload()
            return self.skills.catalog()
        if cmd.startswith("plugin"):                # «Плагины» в студии (core/plugins.py)
            return self._plugin_cmd(cmd, a)
        if cmd == "mcp_status":
            return self.mcp.status()
        if cmd == "status":
            return self.status
        raise ValueError(f"неизвестная команда {cmd}")
