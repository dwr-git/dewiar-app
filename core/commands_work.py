"""Команды окон (студия, виджет, телефон): «Мой месяц», «Спросит потом», Радар, идеи, дом по Wi-Fi, «Дозор», режимы «Для старших», команда,
клиенты, видеоуроки, чат для сайта, «Сайты», CRM, рассылка.
Часть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки
проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class WorkCommands:
    def _cmd_work(self, cmd, a):
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
        if cmd.startswith("insight_"):           # «Радар» — аналитик ниши (engine_insight.py, docs/RADAR.md)
            import engine_insight
            return engine_insight.command(self, cmd, a)
        if cmd.startswith("ideas_"):             # «Идеи Лиры»: список, голос, своя идея (ideas.py → сайт)
            import ideas
            return ideas.command(self, cmd, a)
        if cmd.startswith("homelan_"):           # «Дома по Wi-Fi» (engine_home.py)
            # 04.11 (smarthome_test): были home_get/home_forget — те же имена, что у умного дома Яндекса ниже, и
            # перехватывали их: «Подключить» Яндекс отвечал «неизвестная команда home_connect», «Отключить» не отключал
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
        if cmd == "academy_list":                 # «Видеоуроки» (0.69): уроки ИИ Академии с сайта (cloud.php ?p=/academy)
            from cloud import CloudError, base_of, public
            try:
                en = hasattr(self, "_ui_en") and self._ui_en()   # 14.11: программа по-английски — английские ролики
                d = public(self.cloud.url, "/academy" + ("&lang=en" if en else ""), timeout=12)
            except CloudError as e:
                raise ValueError(str(e)) from e
            # дома запрос ушёл на сайт напрямую (net._LanFirst) — и ссылки сайт собрал с домашним адресом
            # (http://192.168.…:9099/dwrapp/academy/…); окно студии грузит их само, мимо ядра, — обложек нет, плеер чёрный
            # (владелец 29.10). Ссылки на файлы уроков — всегда публичные, как в браузере.
            pub = base_of(self.cloud.url).rsplit("/", 1)[0] + "/academy/"
            for it in d.get("items") or []:
                for k in ("video", "webm", "poster"):
                    u = str(it.get(k) or "")
                    if "/academy/" in u and not u.startswith(pub):
                        it[k] = pub + u.rsplit("/academy/", 1)[1]
            return d
        if cmd == "academy_file":                 # файл урока — через ядро на диск (academy_cache: изнутри сети сайта домен не открывается)
            import academy_cache
            try:
                f = academy_cache.fetch(str(a.get("url") or ""), self.cloud.url, STATE_DIR / "academy",
                                        timeout=60.0 if str(a.get("url") or "").lower().endswith((".mp4", ".webm")) else 15.0)
            except ValueError:
                raise
            except Exception as e:  # noqa: BLE001
                code = getattr(getattr(e, "response", None), "status_code", 0)
                raise ValueError(f"урок не скачался: сайт ответил {code}" if code else f"урок не скачался: {e}") from e
            # №575 (Windows): студия открыта с http://127.0.0.1 (№442), а Chromium с http-страницы file:// не грузит — обложки
            # пропадали. Картинки — data:URL (как close_thumb, art_url №511); видео велико для data: — его отдаёт сам
            # ui-http по имени из кэша (/academy-cache/<name>, ui/app.py), file:// — для окон, открытых с диска
            size = f.stat().st_size
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and size <= 6 * 1024 * 1024:
                import base64
                mime = {".png": "image/png", ".webp": "image/webp"}.get(f.suffix.lower(), "image/jpeg")
                return {"uri": f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode(), "size": size, "name": f.name}
            return {"uri": f.as_uri(), "size": size, "name": f.name}
        if cmd.startswith("sitechat_"):           # «Чат для сайта» (0.69, sitechat.py): опубликовать, отключить, заявки
            from sitechat import SiteChatError
            W = self.sitechat
            try:
                site = str(a.get("site") or "")       # свой консультант сайта (14.11); '' — общий
                if cmd == "sitechat_get":
                    return W.public(fresh=bool(a.get("fresh")), site=site)
                if cmd == "sitechat_publish":
                    return W.publish(a.get("patch") or {}, site=site)
                if cmd == "sitechat_save":             # только настройки, без отправки (черновик)
                    patch = {k: v for k, v in (a.get("patch") or {}).items() if k in __import__("sitechat").DEF and k != "on"}
                    W._store({**W.cfg(site), **patch}, site) if site else self.s.update({"sitechat": patch})
                    return W.public(site=site)
                if cmd == "sitechat_forget":
                    return W.forget(site=site)
                if cmd == "sitechat_tg":               # свой бот компании в Telegram — тот же консультант (18.11)
                    return W.tg(a.get("token") or "", site=site)
                if cmd == "sitechat_poll":
                    n = W.poll()
                    return dict(W.public(), took=n)
            except SiteChatError as e:
                raise ValueError(str(e)) from e
            raise ValueError("неизвестная команда чата для сайта")
        if cmd.startswith("sites_"):              # «Сайты» (03.11, sites.py): список, редактор, версии, публикация, аналитика
            return self.sites_cmd(cmd, a)
        if cmd.startswith("crm_"):                # «CRM» (0.69, crm.py): Битрикс24 или свой вебхук; клиент — лидом
            from crm import CrmError
            R = self.crm
            try:
                if cmd == "crm_get":
                    return R.public()
                if cmd == "crm_connect":
                    return R.connect(str(a.get("kind") or ""), str(a.get("url") or ""))
                if cmd == "crm_forget":
                    return R.forget()
                if cmd == "crm_auto":
                    return R.set_auto(bool(a.get("on")))
                if cmd == "crm_test":
                    return {"ok": R.test()}
                if cmd == "crm_send":
                    r = R.send(str(a.get("id") or ""))
                    return dict(r, client=self.clients.get(str(a.get("id") or "")))
            except CrmError as e:
                raise ValueError(str(e)) from e
            raise ValueError("неизвестная команда CRM")
        if cmd.startswith("mailing_"):            # «Рассылка» (0.69, mailing.py): черновик, пример, отправка, стоп, отписки
            from mailing import MailingError
            M = self.mailing
            try:
                if cmd == "mailing_get":
                    return {"sources": M.sources(), "list": M.list(), "stop": M.stop_list()}
                if cmd == "mailing_preview":            # сколько получателей и кто — до черновика (студия, на лету)
                    return M.preview(a.get("subject") or "", a.get("body") or "", a.get("source") or "list", a.get("text") or "",
                                     a.get("tag") or "", a.get("kind") or "work", a.get("box"))
                if cmd == "mailing_draft":
                    return M.draft(a.get("subject", ""), a.get("body", ""), a.get("source") or "list", a.get("text") or "",
                                   a.get("tag") or "", a.get("kind") or "work", a.get("box"))
                if cmd == "mailing_start":
                    return M.start(a.get("id", ""))
                if cmd == "mailing_stop":
                    return M.stop(a.get("id", ""))
                if cmd == "mailing_forget":
                    return M.forget(a.get("id", ""))
                if cmd == "mailing_one":
                    return M.get(a.get("id", ""))
                if cmd == "mailing_stopset":
                    return M.stop_set(a.get("emails") or [])
            except MailingError as e:
                raise ValueError(str(e)) from e
            raise ValueError("неизвестная команда рассылки")
        return NotImplemented

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
        """team_get; team_connect {token}; team_forget; team_set {company?, boss?, speak?}; team_member_add {name, role, email}; team_member_set {id, email?, role?};
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
                return T.member_add(a.get("name"), a.get("role") or "", a.get("email") or "")
            if cmd == "team_member_set":
                return T.member_set(str(a.get("id") or ""), a.get("email"), a.get("role"))
            if cmd == "team_member_del":
                return T.member_del(str(a.get("id") or ""))
            if cmd == "team_member_code":
                return T.member_code(str(a.get("id") or ""))
            if cmd == "team_assign":
                r = T.assign(str(a.get("who") or ""), a.get("title"), a.get("due") or "", a.get("note") or "")
                return dict(T.public(), made=({"repeat": True, "rule": r["rule"], "name": r["name_dat"]} if r.get("repeat") else {}))
            if cmd == "team_message":                   # написать сотруднику: ответ на сообщение или просто слово
                return T.message(str(a.get("id") or a.get("who") or ""), str(a.get("text") or ""))
            if cmd == "team_hire":                      # «Компания»: одно приглашение — «Поручения» в приложении и место в компании
                return T.hire(a.get("name"), a.get("role") or "")
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

    def sites_cmd(self, cmd, a):
        """«Сайты» (03.11, sites.py) для студии: список, шаблоны, предпросмотр, правки и «Сказать Лире», версии, фото,
        публикация на имя.dewiar.pro, посещения, проверка продвижения, заявки."""
        from sites import SiteError
        from sites_blog import BlogError as B_ERR
        W = self.sites
        sid = str(a.get("id") or "")
        try:
            if cmd == "sites_list":
                return {"items": W.list(), "signed": bool(W._key()), "error": W.error}
            if cmd == "sites_meta":
                return W.meta()
            if cmd == "sites_get":
                return W.public(sid)
            if cmd == "sites_render":                   # предпросмотр страницы
                return {"html": W.render(sid, a.get("page") or 0)}       # номер страницы или «doc:privacy» — документ
            if cmd == "sites_legal_draft":              # 0.87: «Составить черновик политики ПД по моим данным»
                r = W.legal_draft(sid, str(a.get("doc") or "privacy"))
                return dict(W.public(sid), text=r["text"])
            if cmd == "sites_template":
                return {"html": W.template_preview(str(a.get("template") or ""))}
            if cmd == "sites_create":
                s = W.create(str(a.get("template") or ""), str(a.get("describe") or ""), str(a.get("name") or ""), "",
                             a.get("contacts") or {}, fill=bool(a.get("describe") or a.get("ref")), ref=str(a.get("ref") or ""))
                return W.public(s["id"])
            if cmd == "sites_apply":
                W.apply(sid, a.get("ops") or [], str(a.get("label") or ""), merge=bool(a.get("merge")))
                return W.public(sid)
            if cmd == "sites_say":
                r = W.say(sid, str(a.get("text") or ""))
                return dict(W.public(sid), said=r["said"])
            if cmd == "sites_undo":
                W.undo(sid)
                return W.public(sid)
            if cmd == "sites_restore":
                W.restore(sid, int(a.get("v") or 0))
                return W.public(sid)
            if cmd == "sites_image":
                return {"image": W.image_add(sid, a.get("data") or "", a.get("alt") or "")}
            if cmd == "sites_delete":
                return W.delete(sid)
            if cmd == "sites_open":
                import tools as _t
                _t.launch(["xdg-open", str(W.export(sid))])
                return {"ok": True}
            if cmd == "sites_zip":                       # 15.11: сайт архивом — на свой сервер и домен
                out = W.export_zip(sid)
                if a.get("reveal", True) and not os.environ.get("DEWIAR_DRY_TOOLS"):
                    import export as X
                    X.reveal(out)
                return {"path": str(out), "name": out.name}
            if cmd == "sites_check":
                return W.check_name(str(a.get("name") or ""), sid)
            if cmd == "sites_suggest":
                return {"name": W.suggest_name(sid)}
            if cmd == "sites_publish":
                W.publish(sid, str(a.get("name") or ""))
                return W.public(sid)
            if cmd == "sites_reach":                     # №549: «Проверить адрес» — открывается ли сайт
                W.recheck(sid)
                return W.public(sid)
            if cmd == "sites_unpublish":
                W.unpublish(sid)
                return W.public(sid)
            if cmd == "sites_stats":
                return W.stats(sid, int(a.get("days") or 30), bool(a.get("prev")))
            if cmd == "sites_audit":
                return W.audit(sid)
            if cmd == "sites_leads":
                W.poll()
                return {"items": W.leads(sid)}
            if cmd == "sites_logos":
                return {"items": W.artist_logos()}
            if cmd == "sites_chat":                      # 05.11: «Чат Лиры на сайте» — состояние и «Включить» прямо из «Сайтов»
                return self._sites_chat(sid, bool(a.get("on")))
            # «Статьи» (0.93, sites_blog): настройки, план, черновик сейчас, правка, «Опубликовать»
            import sites_blog as B
            if cmd == "sites_blog":
                return W.blog_get(sid)
            if cmd == "sites_blog_set":
                return W.blog_set(sid, a.get("patch") or {})
            if cmd == "sites_blog_plan":
                B.make_plan(W, sid, more=bool(a.get("more")))
                return W.blog_get(sid, fresh=False)
            if cmd == "sites_blog_write":
                art = B.write(W, sid, str(a.get("topic") or "").strip()[:200])
                return dict(W.blog_get(sid), written=art)
            if cmd == "sites_blog_article":
                return {"article": W._fetch("/sites/article", {"id": int(a.get("aid") or 0)}).get("article")}
            if cmd == "sites_blog_save":
                f = {k: a.get(k) for k in ("title", "descr", "body") if a.get(k) is not None}
                d = W._fetch("/sites/article/save", dict(f, id=int(a.get("aid") or 0)))
                return {"article": d.get("article")}
            if cmd == "sites_blog_fix":                 # «Попросить Лиру поправить»: просьба своими словами
                return {"article": B.fix(W, int(a.get("aid") or 0), str(a.get("text") or "").strip()[:500])}
            if cmd == "sites_blog_status":
                return {"article": B.set_status(W, sid, int(a.get("aid") or 0), str(a.get("status") or "")), **W.blog_get(sid)}
        except B_ERR as e:
            raise ValueError(str(e)) from e
        except SiteError as e:
            raise ValueError(str(e)) from e
        raise ValueError("неизвестная команда сайтов")

    def _sites_chat(self, sid, on):
        """«Чат для сайта» на опубликованных сайтах: sites.php сам ставит кнопку чата на каждый сайт аккаунта, когда чат
        включён. Здесь — честное состояние для «Сайтов» и «Включить»: нет знаний у консультанта — берём их с сайта sid
        (sites.chat_knowledge), прежние настройки «Чата для сайта» не трогаем. -> {available, on, signed, name, color, knows, link}"""
        SC = getattr(self, "sitechat", None)
        if SC is None:
            return {"available": False}
        from sitechat import SiteChatError, readable
        seeded = False
        if on:
            c = SC.cfg()
            patch = {}
            if sid and not (str(c.get("kb") or "").strip() or str(c.get("brief") or "").strip()):
                from sites import chat_knowledge
                patch = {k: v for k, v in chat_knowledge(self.sites.get(sid)).items() if v and not str(c.get(k) or "").strip()}
                seeded = bool(patch.get("kb") or patch.get("brief"))
            try:
                SC.publish(patch)
            except SiteChatError as e:
                raise ValueError(str(e)) from e
        name = ""
        try:
            name = ((self.sites.get(sid).get("published") or {}).get("name") or "") if sid else ""
        except Exception:  # noqa: BLE001
            name = ""
        try:
            own = bool(name and SC.cfg(name).get("on"))       # у сайта свой консультант (14.11)
        except TypeError:                                      # прежний SiteChat без сайтов
            own = False
        c = SC.cfg(name) if own else SC.cfg()
        p = SC._persona(c.get("persona"))
        col = str(p.get("color") or "")
        rem = (getattr(SC, "remotes", None) or {}).get(name if own else "") if own else SC.remote
        r = rem if rem and not rem.get("none") else {}
        return {"available": True, "on": bool(c.get("on")), "signed": bool(SC._key()), "name": p.get("name") or "Лира",
                "color": readable(col) if re.fullmatch(r"#[0-9a-fA-F]{6}", col) else "#6a5cf0",
                "knows": bool(str(c.get("kb") or "").strip() or str(c.get("brief") or "").strip()), "link": (r or {}).get("link", ""), "seeded": seeded,
                "own": own, "site": name}
