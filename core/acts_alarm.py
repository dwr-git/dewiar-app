"""Напоминания и будильник (часть Engine, чистое ядро 1.0.16): окно-будильник, звонок и голосовые «отложи/понял»,
команды студии для напоминаний и дел, вложения напоминаний, журнал сработавших, имена дел по расписанию."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from acts_base import _att_word, CAPTURE_FOLDER


class AlarmMixin:
    # ---------- напоминания и будильник ----------

    def _reminder_public(self, x):
        """Напоминание для окна: добавляет when (словами), repeat_text и at_hm («ЧЧ:ММ»)."""
        from when import describe_repeat, human
        try:
            at = datetime.fromisoformat(x["at"])
            when = human(at)
        except (KeyError, ValueError):
            at, when = None, x.get("at", "")
        out = dict(x, when=when, repeat_text=describe_repeat(x.get("repeat")), at_hm=f"{at:%H:%M}" if at else "")
        if x.get("note") or x.get("note_id"):
            rel = self._reminder_note(x)
            out.update(note=rel, att=len(self.workspace.note_atts(rel)) if rel else 0)
        return out

    def _reminder_note(self, x):
        """Заметка с картинками и файлами напоминания -> путь в папке ассистента или "". note — путь (поставлено здесь),
        note_id — id синхронизации (поставлено на телефоне: его заметка приходит в «Заметки» под своим путём)."""
        rel = x.get("note")
        try:
            if rel and self.workspace.safe(rel).is_file():
                return rel
        except Exception:  # noqa: BLE001
            pass
        try:
            return (self.note_rel_of(x["note_id"]) or "") if x.get("note_id") and getattr(self, "sync", None) is not None else ""
        except Exception:  # noqa: BLE001
            return ""

    def _reminder_files(self, rid):
        """Вложения напоминания для окна-будильника: [{kind, name, path, thumb}] — миниатюры картинок data:URL."""
        from engine_answer import _thumb
        x = (getattr(self, "_fired", None) or {}).get(rid) or self.reminders.get(rid) if rid else None
        if not x:
            return {"note": "", "files": []}
        rel = self._reminder_note(x)
        out = []
        for f in (self.workspace.note_atts(rel) if rel else [])[:12]:
            if f["kind"] == "image":
                try:
                    f = dict(f, thumb=_thumb(self.workspace.safe(f["path"]).read_bytes(), 360))
                except OSError:
                    continue
            out.append(f)
        return {"note": rel, "files": out}

    def reminders_list(self):
        return [self._reminder_public(x) for x in self.reminders.items]

    # ---------- синхронизация устройств (core/sync.py) ----------

    def _reminders_wake(self):
        """Компьютер проснулся или Dewiar запустился: синхронизация есть — обменяться сейчас (опоздавшие ждут её, см.
        Reminders._loop); синхронизации нет или облако выключено стоп-краном — ждать нечего, звенеть сразу (late_alarm1027:
        без синхронизации пропущенное при запуске звенело только через 90 с)."""
        try:                                             # 13.11: пути к серверам Dewiar — заново, логин прокси — свежий
            import net
            net.wake_reset()
            self._px_auth_at = 0
            if getattr(self, "_px_stale", False):
                threading.Timer(20, self._dewiar_proxy_fetch, kwargs={"force": True}).start()
        except Exception:  # noqa: BLE001
            log.debug("wake: net", exc_info=True)
        try:
            import egress
            on = (self.s.get("sync", "enabled") is not False and not getattr(self, "wav_input", None)
                  and not egress.local_only() and bool(self.credentials()[0]))
        except Exception:  # noqa: BLE001
            on = False
        if on:
            self.sync.soon.set()
        else:
            self.reminders.release_hold()

    def _on_reminders_changed(self, items):
        """Список напоминаний изменился: поторопить синхронизацию, обновить файл в папке ассистента и окно."""
        sy = getattr(self, "sync", None)
        if sy is not None:
            sy.soon.set()                                         # телефону и другим компьютерам — сразу
        ev = getattr(self, "_tg_sync_soon", None)
        if ev is not None:
            ev.set()                                              # серверу Telegram — чтобы напомнил, даже если компьютер выключен
        self.workspace.sync_reminders(items)
        self.emit("reminders", items=[self._reminder_public(x) for x in items])

    def _on_reminder(self, item):
        """Сработало: окно-будильник по центру, звонок до «Готово»/«Отложить», голос, уведомление, Telegram."""
        text = item["text"]
        if hasattr(self, "_rest_hold") and self._rest_hold("reminder", item=dict(item)):
            return                                       # «Отдых» (№540): напоминание подождёт конца отдыха
        if item.get("kind") == "job" and int(item.get("late_s") or 0) > self.JOB_LATE_MAX:
            # 28.10 (владелец): компьютер был выключен — утром выполнился вчерашний «Итог дня» в 8:56. Дело, опоздавшее больше
            # чем на JOB_LATE_MAX, не выполняем: в календаре оно на своём месте с пометкой «пропущено»
            log.info("🗓 Пропущено (компьютер был выключен, опоздание %d мин): %s", int(item["late_s"]) // 60, text)
            self._log_reminder(item, skipped=True)
            return
        if item.get("kind") == "job":
            from tools import Reminders as _R
            sig, now_m = _R.job_sig(item), time.monotonic()
            title = ("t", self.job_title(item).strip().lower()) if hasattr(self, "job_title") else sig
            seen = getattr(self, "_job_fired", None) or {}
            if now_m - max(seen.get(sig, -1e9), seen.get(title, -1e9)) < 600:   # такое же дело только что выполнялось — второй раз не надо
                log.info("🗓 «%s» уже выполнялось только что — двойник, пропускаю", text)
                return
            seen[sig] = seen[title] = now_m
            self._job_fired = seen
        log.info("⏰ %s", text)
        self._log_reminder(item)
        fired = getattr(self, "_fired", None) or {}           # сработавшие (разовые уже убраны из списка) — окну за вложениями
        fired[item["id"]] = item
        self._fired = dict(list(fired.items())[-20:])
        if item.get("kind") == "job":                     # дело по расписанию: не звоним, а выполняем
            threading.Thread(target=self._run_job, args=(item,), name="job", daemon=True).start()
            return
        with self._alarm_lock:
            old = self.alarm
            if old:                                       # уже звенит другое — глушим его, оно станет «пропущенным»
                old["done"].set()
            a = {"item": item, "done": threading.Event(), "since": time.monotonic(), "result": ""}
            self.alarm = a
        from when import describe_repeat
        kind = item.get("kind") or "reminder"
        title = {"alarm": "Будильник", "timer": "Таймер"}.get(kind, "Напоминание")
        rel = self._reminder_note(item) if item.get("note") or item.get("note_id") else ""
        att = self.workspace.note_atts(rel) if rel else []
        pics = sum(1 for f in att if f["kind"] == "image")
        clip = f" (📎 {_att_word(att)})" if att else ""
        desktop_notify(f"⏰ {title}: {text}{clip}", critical=True)
        self.emit("alarm", id=item["id"], text=text, kind=kind, title=title, late=bool(item.get("late")),
                  at=item.get("at", ""), repeat_text=describe_repeat(item.get("repeat")),
                  window=self.s.get("reminders", "window") is not False, note=rel, att=len(att), pics=pics)
        self.emit("reminder", text=text)
        if self.chat.notify_on():
            threading.Thread(target=self.chat.notify, args=(f"⏰ {title}: {text}" + (f"\n📎 {_att_word(att)} — на компьютере" if att else ""),),
                             kwargs={"buttons": [("Готово", f"alarm:ack:{item['id']}"), ("Через 10 мин", f"alarm:snooze:{item['id']}:10"),
                                                 ("Через час", f"alarm:snooze:{item['id']}:60")]}, daemon=True).start()
        threading.Thread(target=self._alarm_loop, args=(a,), name="alarm", daemon=True).start()

    def _alarm_loop(self, a):
        """Поток звонка: звенит и иногда проговаривает текст, пока не ответят или не выйдет reminders.ring_minutes.
        Без ответа — результат «missed». a — общий с alarm_finish словарь (done, result)."""
        from audio_io import alarm_tone
        item = a["item"]
        kind = item.get("kind") or "reminder"
        limit = max(0.25, float(self.s.get("reminders", "ring_minutes") or 2)) * 60
        pcm = alarm_tone(self.s.get("reminders", "sound") or "signature")
        say = self.s.get("reminders", "speak") is not False
        phrase = ({"alarm": "Пора вставать! ", "timer": "Время вышло! "}.get(kind, "Напоминание: ") +
                  (item["text"] if item["text"] not in ("Будильник", "Таймер", "Напоминание") else "")).strip()
        if item.get("late"):
            phrase = "Пропущенное напоминание: " + item["text"]
            # №327 (пакет 27.10): включили компьютер — пропущенные звенели и проговаривались по 2 минуты каждое, «выключить
            # нельзя». Опоздавшее — один звонок и одна фраза; окно с ним остаётся, пока его не закроют
            limit = min(limit, 12)
        if item.get("note") or item.get("note_id"):
            att = self.workspace.note_atts(self._reminder_note(item))
            if att:
                phrase = phrase.rstrip(".") + ". " + ("Картинки — на экране, в окне напоминания." if any(f["kind"] == "image" for f in att)
                                                      else "Файлы — на экране, в окне напоминания.")
        n = 0
        while not a["done"].is_set() and not self.stopping.is_set() and time.monotonic() - a["since"] < limit:
            for _ in range(60):                                # не перебиваем разговор: ждём конца ответа, но не дольше 15 с
                if self.state not in ("speaking", "thinking") or a["done"].is_set():
                    break
                time.sleep(0.25)
            if a["done"].is_set():
                break
            self._ring(pcm, a)
            if a["done"].is_set():
                break
            if say and n in (0, 3, 8):
                self._say_now(phrase, a)
                self.follow_up_until = time.monotonic() + 7    # «отложи на 10 минут» — можно без имени
                self.set_state("listening")
            if item.get("late"):                      # дальше — тихо: окно ждёт ответа до 10 минут (и откроется у виджета,
                a["done"].wait(600)                       # который подключился позже, — «hello» берёт его из self.alarm)
                break
            a["done"].wait(1.2 if n < 3 else 3.0)
            n += 1
        with self._alarm_lock:
            if self.alarm is a:
                self.alarm = None
        if not a["result"]:
            a["result"] = "missed"
            log.info("⏰ Никто не ответил — «%s» отмечено пропущенным", item["text"])
            self.emit("alarm_done", id=item["id"], result="missed")
            self._care_after(item, "missed")
            if self.state == "listening" and self.turn is None:
                self.set_state("idle")

    def _ring(self, pcm, a):
        """Проиграть звонок один раз отдельным плеером (PCM 16 бит, audio_io.ALARM_RATE) — чтобы не мешать очереди речи."""
        from audio_io import ALARM_RATE
        if self.player is None:
            time.sleep(2.4)
            return
        pl = Player(device=self.player.device, null=self.null_player)
        try:
            pl.start(ALARM_RATE)
            step = ALARM_RATE * 2 // 10                          # по 0,1 с — чтобы «Готово» обрывало звонок сразу
            for i in range(0, len(pcm), step):
                if a["done"].is_set():
                    break
                pl.write(pcm[i:i + step])
            pl.finish()
        except Exception as e:  # noqa: BLE001
            log.info("Звонок не прозвучал: %s", e)
            time.sleep(1)

    def _say_now(self, text, a=None):
        """Сказать сразу и дождаться конца (из потока будильника)."""
        with self._turn_lock:
            self.turn_n += 1
            turn = Turn(self.turn_n)
            self.turn = turn
        q = queue.Queue()
        q.put(text)
        q.put(None)
        self.emit("answer", text=text, done=True)
        try:
            self._speak_worker(turn, q)
        finally:
            with self._turn_lock:
                if self.turn is turn:
                    self.turn = None
                    self.set_state("idle")

    def alarm_finish(self, result="ack", minutes=0, rid=None):
        """«Готово» или «Отложить на N минут» — кнопкой, голосом, из Telegram."""
        with self._alarm_lock:
            a = self.alarm
            if a is None or (rid and a["item"]["id"] != rid):
                return None
            self.alarm = None
        a["result"] = result
        a["done"].set()
        self.cancel_turn()
        item = a["item"]
        out = {"id": item["id"], "result": result}
        if result == "snooze":
            from when import human
            minutes = max(1, int(minutes or 10))
            when = datetime.now() + timedelta(minutes=minutes)
            new = self.reminders.add(when, item["text"], None, item.get("kind") or "reminder",
                                     extra={k: item.get(k) for k in ("note", "note_id", "care", "care_n", "care_of", "care_root", "care_at")})   # картинки и «лекарство» — и при отложенном
            out.update(snooze_id=new["id"], when=human(when))
            log.info("⏰ Отложено на %d мин: %s", minutes, item["text"])
        else:
            log.info("⏰ Готово: %s", item["text"])
        self._care_after(item, result)                     # лекарство в режиме «Для старших» (engine_senior.py)
        self.emit("alarm_done", **out)
        if self.state == "listening" and self.turn is None:
            self.set_state("idle")
        return out

    def _alarm_voice(self, text):
        """Пока звенит: «отложи на 10 минут» — отложить; «понял/хватит/спасибо» — выключить. True — фраза разобрана."""
        if not self.alarm:
            return False
        low = _norm(text)
        if self.SNOOZE_RX.search(low):
            from when import _num_words
            m = re.search(r"(\d+)\s*(час|мин)?", _num_words(low))
            mins = 10
            if "полчаса" in low:
                mins = 30
            elif m:
                mins = int(m.group(1)) * (60 if (m.group(2) or "").startswith("час") else 1)
            elif re.search(r"\bчас\b", low):
                mins = 60
            r = self.alarm_finish("snooze", mins)
            if r:
                self.emit("heard", text=text)
                self.announce(f"Хорошо, напомню {r['when']}.")
            return True
        words = set(re.findall(r"[\wё]+", low))
        med = self._care_item(self.alarm["item"]) if self.alarm else False
        if is_sleep_phrase(text) or words & self.ACK_WORDS:
            if med and re.search(r"\b(?:нет|не\s+(?:пила|пил|выпила|выпил|приняла|принял)|забыла?|потом)\b", low):
                self.alarm_finish("seen")                  # «нет, не пила» — не отмечаем выпитым: спросим ещё раз
                self.emit("heard", text=text)
                self.announce("Хорошо, напомню ещё раз через пятнадцать минут.")
                return True
            if self.alarm_finish("ack"):
                self.emit("heard", text=text)
                self.play_tone("done")
                if med:
                    self.announce("Отлично, отметила.")
            return True
        # заговорили о другом — значит, увидели; продолжаем разговор (лекарство — не «выпито»: спросим ещё раз)
        self.alarm_finish("seen" if med else "ack")
        return False

    def _alarm_public(self):
        """Что звенит сейчас — для окна-будильника, открытого позже звонка. -> словарь или None."""
        a = self.alarm
        if not a:
            return None
        from when import describe_repeat
        it = a["item"]
        kind = it.get("kind") or "reminder"
        return {"id": it["id"], "text": it["text"], "kind": kind, "late": bool(it.get("late")), "at": it.get("at", ""),
                "title": {"alarm": "Будильник", "timer": "Таймер"}.get(kind, "Напоминание"),
                "repeat_text": describe_repeat(it.get("repeat")), "note": self._reminder_note(it) if it.get("note") or it.get("note_id") else ""}

    def _done_cmd(self, cmd, a):
        """Студия → «Дела»: список и достижения, отметить сделанное (в том числе напоминание), снять отметку."""
        dn = self.done
        if cmd == "done":
            return dn.public()
        r = None
        if cmd == "done_add":
            title = str(a.get("title") or "").strip()
            if not title:
                raise ValueError("напишите, что сделано")
            import done as D
            m = D.reminder_match(title, list(self.reminders.items), ahead=True)
            if m and not m.get("repeat"):
                self.reminders.remove(m["id"])
            r = dn.add([{"title": m.get("text"), "rid": m["id"]} if m else title], "pc")
        elif cmd == "done_reminder":
            x = self.reminders.get(a.get("id") or "")
            if not x:
                raise ValueError("такого напоминания уже нет")
            if not x.get("repeat"):
                self.reminders.remove(x["id"])
            r = dn.add([{"title": x.get("text") or "Дело", "rid": x["id"]}], "pc")
        elif cmd == "done_undo":
            if not dn.undo(a.get("id") or ""):
                raise ValueError("такой отметки уже нет")
        pub = dn.public()
        extra = {}
        if r:
            extra = {"fresh": [{"icon": x[3], "name": x[4], "what": x[5]} for x in r["fresh"]], "mile": r["mile"],
                     "added": [x["title"] for x in r["items"]]}
        self.emit("done", **pub, **extra)
        return dict(pub, **extra)

    def _reminder_cmd(self, cmd, a):
        """Студия и окно-будильник: список, добавить (словами или датой), изменить, удалить, «Готово», «Отложить»."""
        from tools import ToolError, _when
        from when import parse as parse_when
        if cmd == "reminders":
            return self.reminders_list()
        if cmd == "alarm_get":
            return self._alarm_public()
        if cmd == "alarm_ack":
            return self.alarm_finish("ack", rid=a.get("id"))
        if cmd == "alarm_snooze":
            return self.alarm_finish("snooze", int(a.get("minutes") or 10), rid=a.get("id"))
        if cmd == "alarm_test":                       # «Послушать звонок» в студии
            from audio_io import alarm_tone
            box = {"done": threading.Event()}
            pcm = alarm_tone(a.get("sound") or self.s.get("reminders", "sound") or "signature")
            threading.Thread(target=self._ring, args=(pcm, box), daemon=True).start()
            return True
        if cmd == "reminder_parse":                   # подсказка под полем ввода: как поняли фразу
            r = parse_when("напомни " + (a.get("phrase") or ""))
            if not r:
                return None
            from when import describe_repeat, human
            return {"text": r["text"], "when": human(r["at"]), "repeat_text": describe_repeat(r["repeat"]), "kind": r["kind"]}
        if cmd == "reminder_add":
            phrase = (a.get("phrase") or "").strip()
            if phrase:
                r = parse_when(phrase if re.match(r"(?i)\s*(напомни|напоминай|разбуди|будильник|таймер|засеки)", phrase)
                               else "напомни " + phrase)
                if not r:
                    raise ValueError("не понял, когда напомнить — например: «завтра в 9 позвонить маме»")
                item = self.reminders.add(r["at"], (a.get("text") or r["text"]), r["repeat"], r["kind"])
            else:
                try:
                    when, rep, text, kind = _when(a)
                except ToolError as e:
                    raise ValueError(str(e)) from e
                src = (getattr(self, "_fired", None) or {}).get(a.get("from") or "") or {}    # пропущенное из окна — с теми же картинками
                item = self.reminders.add(when, text or "Напоминание", rep, a.get("kind") or kind,
                                          extra={k: src.get(k) for k in ("note", "note_id")})
            return self._reminder_public(item)
        if cmd == "reminder_files":                   # окно-будильник: картинки и файлы напоминания
            return self._reminder_files(a.get("id") or "")
        if cmd == "capture_parse":                    # окно «Закинуть идею»: что будет с этим текстом
            r = parse_when(a.get("text") or "") if re.match(r"(?i)\s*(напомни|напоминай|разбуди|будильник|таймер|засеки)", a.get("text") or "") else None
            if not r:
                return {"kind": "note", "folder": CAPTURE_FOLDER}
            from when import describe_repeat, human
            return {"kind": "reminder", "text": r["text"], "when": human(r["at"]), "repeat_text": describe_repeat(r["repeat"])}
        if cmd == "capture_save":
            return self.capture_save(a.get("text") or "", list(a.get("files") or []), list(a.get("images") or []))
        if cmd == "job_add":                          # «Готовые дела» в студии: фраза с расписанием + точный текст дела
            from jobs import parse as parse_job
            c = parse_job(a.get("phrase") or "")
            if not c or c.get("op") != "job":
                raise ValueError("не понял расписание — например: «каждый день в 8:00»")
            deliver = a.get("deliver") if a.get("deliver") in ("telegram", "max", "voice") else c["deliver"]
            bot = self._bot_for(deliver)
            if bot is not None and not bot.paired():
                raise ValueError(f"{bot.TITLE} ещё не подключён — подключите в «Подключение» или выберите «голосом»")
            task = (a.get("task") or c["task"]).strip()
            brief = bool(a["brief"]) if "brief" in a else c["brief"]
            twin = self.reminders.job_twin(self.reminders.job_sig({"at": c["at"].isoformat(timespec="seconds"), "text": task,
                                                                    "repeat": c["repeat"], "deliver": deliver, "preset": a.get("preset") or ""}))
            if twin:                                  # такое дело уже есть — второе не заводим (иначе выполнятся оба)
                return dict(self._reminder_public(twin), already=True)
            item = self.reminders.add(c["at"], task, c["repeat"], "job", {"deliver": deliver, "brief": brief,
                                                                         "preset": a.get("preset") or ""})
            self.emit("reminder_set", item=self._reminder_public(item))
            return self._reminder_public(item)
        if cmd == "job_run":                          # «Попробовать сейчас» — выполнить дело один раз, не трогая расписание
            task = (a.get("task") or "").strip()
            if not task:
                raise ValueError("пустое дело")
            bot = self._bot_for(a.get("deliver"))
            deliver = a.get("deliver") if bot is not None and bot.paired() else "voice"
            threading.Thread(target=self._run_job, args=({"text": task, "brief": bool(a.get("brief")), "deliver": deliver},),
                             daemon=True).start()
            return {"ok": True, "deliver": deliver}
        if cmd == "reminder_split":
            # 30.10 (владелец: «по будням 17:50, а в пятницу — 16:40»): один день недели повтора — отдельно, своё время.
            # У исходного этот день убирается (каждый день → дни недели без него), новое — тот же текст по этому дню.
            from when import next_time
            cur = next((x for x in self.reminders.items if x["id"] == a.get("id")), None)
            rep = (cur or {}).get("repeat") or {}
            day, tm = int(a.get("day", -1)), str(a.get("time") or "")
            if not cur or rep.get("kind") not in ("daily", "weekly") or not re.match(r"^\d{1,2}:\d{2}$", tm) or not 0 <= day <= 6:
                raise ValueError("так можно только с повтором по дням")
            days = [d for d in (rep.get("days") or range(7)) if d != day]
            if not days:                                   # повтор и был только в этот день — просто новое время
                return self._reminder_cmd("reminder_update", {"id": cur["id"], "patch": {"at": f"{datetime.now():%Y-%m-%d}T{tm}:00"}})
            left = dict(rep, kind="weekly", days=days)
            self.reminders.update(cur["id"], {"repeat": left, "at": next_time(left, datetime.now()).replace(microsecond=0).isoformat(timespec="seconds")})
            one = {"kind": "weekly", "days": [day], "time": f"{int(tm.split(':')[0]):02d}:{tm.split(':')[1]}"}
            item = self.reminders.add(next_time(one, datetime.now()), cur.get("text") or "Напоминание", one, cur.get("kind") or "reminder")
            for x in (next(y for y in self.reminders.items if y["id"] == cur["id"]), item):
                self.emit("reminder_set", item=self._reminder_public(x), text="")
            return {"kept": self._reminder_public(next(y for y in self.reminders.items if y["id"] == cur["id"])), "new": self._reminder_public(item)}
        if cmd == "reminder_update":
            patch = dict(a.get("patch") or {})
            if isinstance(patch.get("days"), list):      # дни недели повтора (календарь: «Пн Вт Ср Чт Пт Сб Вс», 30.10)
                from when import next_time
                cur = next((x for x in self.reminders.items if x["id"] == a.get("id")), None)
                rep = (cur or {}).get("repeat") or {}
                days = sorted({int(d) for d in patch.pop("days") if str(d).isdigit() and 0 <= int(d) <= 6})
                if not days:
                    raise ValueError("оставьте хотя бы один день")
                if rep.get("kind") not in ("daily", "weekly"):
                    raise ValueError("дни можно выбрать только у повтора по дням")
                rep = dict(rep, kind="daily") if len(days) == 7 else dict({k: v for k, v in rep.items() if k != "days"}, kind="weekly", days=days)
                if len(days) == 7:
                    rep.pop("days", None)
                patch["repeat"] = rep
                patch.setdefault("at", next_time(rep, datetime.now()).replace(microsecond=0).isoformat(timespec="seconds"))
            if patch.get("when"):
                r = parse_when("напомни " + patch.pop("when"))
                if not r:
                    raise ValueError("не понял время")
                patch.update(at=r["at"].isoformat(timespec="seconds"), repeat=r["repeat"])
            if patch.get("at") and "when" not in (a.get("patch") or {}):   # календарь: новое время из поля «чч:мм»
                from when import next_time
                cur = next((x for x in self.reminders.items if x["id"] == a.get("id")), None)
                try:
                    at = datetime.fromisoformat(str(patch["at"]))
                except ValueError as e:
                    raise ValueError("не понял время") from e
                rep = (patch.get("repeat") if "repeat" in patch else (cur or {}).get("repeat"))
                if rep:                                  # повтор: новое время — для всех повторов, ближайший — в будущем
                    if isinstance(rep, dict) and rep.get("kind") != "interval":
                        rep = dict(rep, time=at.strftime("%H:%M"))
                        patch["repeat"] = rep
                    if at <= datetime.now():
                        at = next_time(rep, datetime.now())
                elif at <= datetime.now():
                    raise ValueError("это время уже прошло — выберите позже")
                patch["at"] = at.replace(microsecond=0).isoformat(timespec="seconds")
            r = self.reminders.update(a.get("id"), patch)
            if not r:
                raise ValueError("нет такого напоминания")
            self.emit("reminder_set", item=self._reminder_public(r), text="")
            return self._reminder_public(r)
        if cmd == "reminder_cancel":
            return self.reminders.cancel(a.get("id", ""))
        return None

    def _reminder_log(self):
        """Журнал сработавших напоминаний (reminders-log.json, последние 2000): [{at, text, kind, id}]."""
        try:
            return json.loads((STATE_DIR / "reminders-log.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def job_title(self, item):
        """Имя дела для двойников (_on_reminder): готовое — по названию карточки («Итог дня»), своё — его текст."""
        return self.JOB_TITLES.get(item.get("preset") or "") or ("Утренняя сводка" if item.get("brief") else item.get("text", ""))

    def job_label(self, item):
        """Имя дела по расписанию для людей — календарь, «Утро с Лирой», «Дальше сегодня», телефон (№557, 05.11: вместо
        «Дача: заморозки и полив» строкой ехало всё поручение модели «Посмотри прогноз погоды (weather) …»). Готовое —
        название карточки; своё имя дела (title) → дело плагина (его short или имя плагина) → первая фраза поручения."""
        if item.get("brief") or self.JOB_TITLES.get(item.get("preset") or ""):
            return self.job_title(item)
        if item.get("title"):
            return str(item["title"])
        P = getattr(self, "plugins", None)
        try:
            t = P.job_label_by_rid(item.get("id")) if P is not None else ""
        except Exception:  # noqa: BLE001 — плагины не загрузились: имя — из поручения
            t = ""
        from tools import job_short
        return t or job_short(item.get("text", ""))

    def _log_reminder(self, item, skipped=False):
        """Что сработало — в журнал (календарь: «прозвенело»). Опоздавшее — с назначенным временем (due): в календаре оно
        на своём месте, «прозвенело позже, в 08:56»; пропущенное дело — skipped."""
        log_ = self._reminder_log()[-1999:]
        e = {"at": datetime.now().isoformat(timespec="seconds"), "text": item.get("text", ""),
             "kind": item.get("kind") or "reminder", "id": item.get("id")}
        if item.get("kind") == "job":
            e["title"] = self.job_label(item)
        if item.get("late") and item.get("at"):
            e["due"] = str(item["at"])[:19]
        if skipped:
            e["skipped"] = True
        log_.append(e)
        try:
            p = STATE_DIR / "reminders-log.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(log_, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
