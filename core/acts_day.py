"""Деньги и календарь (часть Engine, чистое ядро 1.0.16): «купил … за …», валюта, «Заботливая память», вопросы о планах
(agenda_context), всё по дням месяца (calendar_month)."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from acts_base import ROUTINE_HEAD


class DayMixin:
    # ---------- деньги: «купил … за …», «получил зарплату …», «сколько я потратил …» ----------

    def _default_currency(self):
        """Валюта из настроек («Календарь» → «Деньги» → «Валюта»), иначе — страна из настроек системы."""
        c = (self.s.get("money", "currency") or "").strip().upper()
        return c or self._auto_currency()

    def _auto_currency(self):
        """Догадка по системе (регион Windows, язык и формат, часовой пояс; №422: на Windows раньше всегда выходили рубли
        — пояс искался только как на Linux). Считается раз за запуск."""
        if getattr(self, "_auto_cur", None) is None:
            from money import region_currency
            self._auto_cur = region_currency("RUB")
        return self._auto_cur

    def _money_cmd(self, text, via=None):
        """Записать доход/расход, отменить последнюю запись (не старше 3 дней) или ответить «сколько потратил».
        -> True, если фраза разобрана и ответ дан без модели."""
        from money import fmt, parse, parse_more
        c = parse(text, self._default_currency())
        last = getattr(self, "_money_last", None)
        if not c and last and time.time() - last["ts"] < 15 * 60:
            c = parse_more(text, last, self._default_currency())      # «И ещё 1250 на кафе» — следом за записью
        if not c:
            return False
        if c["op"] == "add":
            it = self.money.add(c["kind"], c["amount"], c["currency"], c["category"], c["note"], c["date"], said=text)
            self._money_last = {"ts": time.time(), "kind": it["kind"], "currency": it["currency"], "category": it["category"]}
            what = "доход" if it["kind"] == "income" else "расход"
            today = datetime.now().date()
            d = datetime.fromisoformat(it["date"]).date()
            # пометку даты — по самой дате записи, не по «не сегодня»: иначе любой другой день назывался бы «вчера»
            day = "" if d == today else " (вчера)" if d == today - timedelta(days=1) else f" ({d:%d.%m})"
            msg = f"Записал {what}{day}: {fmt(it['amount'], it['currency'])} — {it['category'].lower()}" + \
                  (f", {it['note']}" if it["note"] and it["note"].lower() not in it["category"].lower() else "") + "."
            self.emit("money_saved", **it)
            self._say_quick(msg, text, via)
            return True
        if c["op"] == "undo":
            last = self.money.last()
            if not last or time.time() - last.get("created", 0) > 3 * 86400:
                return False
            self.money.delete(last["id"])
            self.emit("money_saved", deleted=last["id"])
            self._say_quick(f"Удалил запись: {fmt(last['amount'], last['currency'])} — {last['category'].lower()}.", text, via)
            return True
        if c["op"] == "query":
            s, e = c["period"]
            if not self.money.summary(s.isoformat(), e.isoformat())["count"]:
                return False                     # записей нет — пусть ответит модель: о деньгах могли говорить в разговоре
            self._say_quick(self.money.answer(c), text, via)
            return True
        return False

    def care_on(self):
        """«Заботливая память» (care.py) включена? (настройка care.on, по умолчанию — да; в детском режиме — нет)"""
        kids = getattr(self, "kids", None)
        return (self.s.get("care") or {}).get("on", True) is not False and not (kids and kids.on())

    def care_context(self, text, turn=None):
        """Сказанное — событие на будущее? Запомнить. Прошло важное — строка для модели «спроси, как прошло» (один раз)."""
        care = getattr(self, "care", None)
        if care is None or not self.care_on():
            return ""
        q = (text or "").split("\n\nВложения:")[0]
        try:
            it = care.note(q)
            if it:
                log.info("💛 Заботливая память: «%s» (%s) — спрошу потом, как прошло", it["what"][:60], it["day"])
            if turn is not None and getattr(turn, "via_job", False):
                return ""
            line, ids = care.context()
            if line:
                care.mark(ids)
                log.info("💛 Заботливая память: спрошу, как прошло")
            return line
        except Exception:  # noqa: BLE001
            log.debug("заботливая память", exc_info=True)
            return ""

    def agenda_context(self, text):
        """Вопрос о планах («что у нас по плану», «какие дела на завтра», «расписание на неделю») — дела, напоминания и
        встречи календаря на эти дни сразу в подсказку модели. Раньше модель отвечала «достаю календарь — одну секунду»
        и не вызывала инструменты (отчёт 14.10): данные уже перед ней — отвечать есть чем. -> текст для системной подсказки или ""."""
        t = (text or "").split("\n\nВложения:")[0]
        if not self.AGENDA_Q.search(t) or "[Утро с Лирой]" in t:
            # утренняя сводка несёт свои данные «Утра» (экзамен 0.99, 15.11: справка о планах взяла «завтра» из наших же
            # слов «ни в планах на завтра» и показала только завтрашний пустой день — сводка сказала «дел нет», а в 23:58 «мама»)
            return ""
        today = datetime.now().date()
        # дни — по словам человека, а не по нашим же пояснениям к поручению (там «в планах на завтра», «на следующую неделю»)
        low = re.split(r"\n\n(?:Повторяющиеся кажд(?:ый|ую)|ПРОВЕРКА:)", t)[0].lower()
        if "послезавтра" in low:
            days = [today + timedelta(days=2)]
        elif "завтра" in low:
            days = [today + timedelta(days=1)]
        elif re.search(r"следующ\w*\s+недел", low):        # «на следующую неделю» — с понедельника по воскресенье
            mon = today + timedelta(days=7 - today.weekday())
            days = [mon + timedelta(days=i) for i in range(7)]
        elif re.search(r"(?<![а-яё])недел", low):          # «на неделю», но не «на понедельник» (в нём тоже «недел»)
            days = [today + timedelta(days=i) for i in range(7)]
        elif any(w in low for w, _ in self.WEEKDAY_Q):
            wd = next(n for w, n in self.WEEKDAY_Q if w in low)
            first = today + timedelta(days=(wd - today.weekday()) % 7)
            days = [first] + ([first + timedelta(days=7)] if first == today else [])   # в саму среду «в среду» — и сегодня, и через неделю
        else:
            days = [today] + ([today + timedelta(days=1)] if datetime.now().hour >= 18 else [])
        names = {today: "сегодня", today + timedelta(days=1): "завтра", today + timedelta(days=2): "послезавтра"}
        months, lines, routine = {}, [], []
        # итог по расписанию («Итог дня», «Итоги недели»): привычки и дела по расписанию — отдельно, с пометкой «не называй»
        # (13.11, владелец: итог недели перечислил еженедельные виклик, бэкап и выключение компьютера). Время их остаётся в
        # справке — проверка «время выдумано» их узнает, а «дел нет» их не считает.
        rids = set()
        if "[Дело по расписанию]" in t and re.search(r"итог|подвед|сводк|что сделано", t, re.I) and hasattr(self, "_habits"):
            try:
                rids = self._habits(weekly=bool(re.search(r"(?<![а-яё])недел", low)))[0]
            except Exception:  # noqa: BLE001
                rids = set()
            rids = rids or {"—"}
        now_hm = datetime.now().strftime("%H:%M")
        try:                                             # память: «в среду в 15:00 встреча» записана с датой «(на 14.10.2026, среда)»
            mem = [x.strip(" -*\t") for x in (self.workspace.memory_get() or "").splitlines() if x.strip()]
        except Exception:  # noqa: BLE001
            mem = []
        for d in days:
            head0 = f"{d.strftime('%d.%m')} ({names.get(d) or ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'][d.weekday()]})"
            remembered = [x for x in mem if d.strftime("%d.%m.%Y") in x]
            for x in remembered[:6]:
                lines.append(f"{head0} из твоей памяти: {x[:200]}")
            key = (d.year, d.month)
            if key not in months:
                try:
                    months[key] = self.calendar_month(d.year, d.month)["days"]
                except Exception as e:  # noqa: BLE001
                    log.info("План на день: календарь не прочитался: %s", e)
                    months[key] = {}
            items = [x for x in months[key].get(d.isoformat(), []) if x.get("type") in ("reminder", "event", "task") and not x.get("paused")]
            items.sort(key=lambda x: x.get("time") or "")
            head = f"{d.strftime('%d.%m')} ({names.get(d) or ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'][d.weekday()]})"
            if not items:
                if not remembered:
                    lines.append(f"{head}: ничего не запланировано")
                continue
            for x in items:
                kind = {"event": "встреча" + (f" ({x['cal']})" if x.get("cal") else ""), "task": "задача"}.get(x["type"]) or \
                    ("дело по расписанию (выполнится само)" if x.get("kind") in ("job", "brief") else "напоминание")
                tm = (x.get("time") or "") + (f"–{x['end']}" if x.get("end") else "")
                past = d == today and (x.get("done") or (x.get("time") and x["time"] < now_hm))
                if rids and x.get("type") == "reminder" and (str(x.get("id") or "") in rids or x.get("kind") in ("job", "brief")):
                    routine.append(f"{head} {tm} {x.get('title', '')}")
                    continue
                lines.append(f"{head} {tm} {kind}: {x.get('title', '')}" + (f", {x['place']}" if x.get("place") else "")
                             + (" — уже прошло" if past else "") + (", повторяется" if x.get("repeat") else ""))
        log.info("📅 Вопрос о планах — даю модели дела и календарь (%d стр.)", len(lines))
        return ("\n\nПЛАНЫ ПОЛЬЗОВАТЕЛЯ (напоминания, дела по расписанию и встречи календаря — уже получены, это свежие данные): "
                "отвечай по ним сразу, без вызова инструментов и без «сейчас посмотрю». Записанное в твоей памяти — тоже планы, называй их. "
                "Сначала то, что впереди, по времени; "
                "прошедшее — одной фразой или не упоминай; ничего нет — так и скажи. Ничего не выдумывай.\n" + "\n".join(lines)
                + (f"\n{ROUTINE_HEAD}: " + "; ".join(routine[:40]) if routine else ""))

    def calendar_month(self, year, month):
        """Всё по дням месяца: напоминания (будущие и сработавшие), деньги, заметки, дневник, задачи."""
        import calendar as _cal
        from when import next_time
        first = datetime(year, month, 1)
        last = datetime(year, month, _cal.monthrange(year, month)[1], 23, 59, 59)
        days = {}

        def put(day, item):
            days.setdefault(day, []).append(item)
        from when import describe_repeat
        for r in self.reminders.items:                          # будущие (с повторами — все случаи в месяце)
            try:
                at = datetime.fromisoformat(r["at"])
            except (KeyError, ValueError):
                continue
            n = 0
            job = r.get("kind") == "job"
            title = self.job_label(r) if job else r["text"]
            while at <= last and n < 400:                        # предел — чтобы частый повтор не раздул месяц и не зациклил
                if at >= first:
                    put(at.date().isoformat(), {"type": "reminder", "id": r["id"], "time": at.strftime("%H:%M"),
                                                "title": title, "text": r["text"],
                                                "kind": r.get("kind") or "reminder", "repeat": bool(r.get("repeat")),
                                                "repeat_text": describe_repeat(r.get("repeat")) if r.get("repeat") else "",
                                                "paused": bool(r.get("paused")), "deliver": r.get("deliver") or "",
                                                # дни недели повтора (0 — пн) — календарь даёт их поменять (30.10)
                                                "rdays": list(range(7)) if (r.get("repeat") or {}).get("kind") == "daily"
                                                else list((r.get("repeat") or {}).get("days") or []) if (r.get("repeat") or {}).get("kind") == "weekly" else []})
                if not r.get("repeat"):
                    break
                at = next_time(r["repeat"], at)
                n += 1
        # сделанные дела (done.py; идея №41: «дела и напоминания — в календаре, выполненные — со статусом „выполнено“»):
        # закрытое напоминание — его же прозвеневшая строка с пометкой closed, остальное — отдельной строкой «выполнено»
        closed = {}
        try:
            for x in list(getattr(self, "done", None).items if getattr(self, "done", None) else []):
                t = datetime.fromtimestamp(int(x["at"]) / 1000)
                if first <= t <= last:
                    closed.setdefault((x.get("rid") or "", t.date().isoformat()), []).append((x, t))
        except Exception:  # noqa: BLE001
            log.debug("календарь: сделанное", exc_info=True)
        for h in self._reminder_log():                          # что уже звенело — в назначенное время (опоздавшее тоже)
            when = h.get("due") or h.get("at", "")
            d = when[:10]
            if first.date().isoformat() <= d <= last.date().isoformat():
                same = closed.get((h["id"], d)) if h.get("id") else None
                it = {"type": "reminder", "time": when[11:16], "title": h.get("title") or h.get("text", ""), "done": True,
                      "kind": h.get("kind") or "reminder", "skipped": bool(h.get("skipped")),
                      "fired": h["at"][:16] if h.get("due") and not h.get("skipped") else ""}
                if same:                                        # закрыли «сделано» в тот же день
                    x, t = same.pop(0)
                    it.update(closed=True, closed_at=t.strftime("%H:%M"), did=x["id"], skipped=False)
                put(d, it)
        for (_rid, d), xs in closed.items():
            for x, t in xs:
                put(d, {"type": "reminder", "kind": "done", "time": t.strftime("%H:%M"), "title": x.get("title") or "Дело",
                        "done": True, "closed": True, "closed_at": t.strftime("%H:%M"), "did": x["id"]})
        for m in self.money.list(first.date().isoformat(), last.date().isoformat()):
            put(m["date"], {"type": "money", "id": m["id"], "kind": m["kind"], "amount": m["amount"],
                            "currency": m["currency"], "title": m["note"] or m["category"], "category": m["category"]})
        root = self.workspace.root
        for folder, typ in (("Заметки", "note"), ("Дневник", "diary")):
            base = root / folder
            if not base.is_dir():
                continue
            for p in base.rglob("*.md"):
                try:
                    mt = datetime.fromtimestamp(p.stat().st_mtime)
                except OSError:
                    continue
                if typ == "diary":
                    try:
                        mt = datetime.fromisoformat(p.stem[:10])
                    except ValueError:
                        pass
                if first <= mt <= last:
                    put(mt.date().isoformat(), {"type": typ, "title": p.stem if typ == "note" else "Дневник",
                                                "path": p.relative_to(root).as_posix(), "time": mt.strftime("%H:%M")})
        try:
            for e in self.calendars.events(first, last + timedelta(seconds=1)):
                d = e["start"]
                while d.date() <= min(e["end"] - timedelta(seconds=1), last).date():   # многодневные — на каждый день
                    if d >= first:
                        put(d.date().isoformat(), {"type": "event", "time": "" if e["allday"] else e["start"].strftime("%H:%M"),
                                                   "end": "" if e["allday"] else e["end"].strftime("%H:%M"), "title": e["title"],
                                                   "place": e.get("place", ""), "cal": e["cal"], "color": e["color"]})
                    d = datetime.combine(d.date() + timedelta(days=1), datetime.min.time())
                    if not e["allday"] and d >= e["end"]:
                        break
        except Exception as e:  # noqa: BLE001
            log.debug("календари: %s", e)
        try:                                                   # «Команда»: сроки поручений, сделанное — с «✓»
            if (self.s.get("features") or {}).get("team"):
                for d, it in self.team.calendar(first, last):
                    put(d, it)
        except Exception:  # noqa: BLE001
            log.debug("календарь: команда", exc_info=True)
        try:                                                   # планы из памяти с датой: «встреча в среду» (capture.plan_day)
            from capture import PLAN_DAY
            for line in self.workspace.memory_get().splitlines():
                m = PLAN_DAY.search(line)
                if not m:
                    continue
                d = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                if first.date().isoformat() <= d <= last.date().isoformat():
                    t = re.sub(r"^\s*-\s*(?:Со слов пользователя:\s*)?", "", line[:m.start()]).strip(" .")
                    hm = re.search(r"\b(?:в|к)\s+(\d{1,2})[:.](\d\d)\b", t)
                    put(d, {"type": "event", "time": f"{int(hm.group(1)):02d}:{hm.group(2)}" if hm else "", "end": "",
                            "title": t[:1].upper() + t[1:], "place": "", "cal": "Память", "color": ""})
        except Exception:  # noqa: BLE001
            log.debug("календарь: планы из памяти", exc_info=True)
        try:
            for t in self.tasks.list():
                d = (t.get("created") or "")[:10]
                if first.date().isoformat() <= d <= last.date().isoformat():
                    put(d, {"type": "task", "id": t.get("id"), "title": t.get("title", ""), "status": t.get("status_ru", "")})
        except Exception:  # noqa: BLE001
            pass
        for v in days.values():
            v.sort(key=lambda x: (x.get("time") or "99", x["type"]))
        return {"year": year, "month": month, "days": days,
                "money": self.money.summary(first.date().isoformat(), last.date().isoformat()),
                "currency": self._default_currency(), "currency_auto": self._auto_currency(),
                "currency_set": (self.s.get("money", "currency") or "").strip().upper()}
