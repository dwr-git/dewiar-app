"""Движок Dewiar: вызов инструментов с подтверждением, напоминания и будильник, синхронизация устройств, деньги.
Примесь класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Состав: _use_tool/_confirm (политика, защита и вопрос «да/нет» голосом или кнопками Telegram); звонок будильника
(_on_reminder → _alarm_loop → alarm_finish) и голосовые «отложи/понял»; команды студии для напоминаний и дел;
быстрые ответы без модели (_capture, _say_quick, _money_cmd); сводка месяца для календаря (calendar_month).
Связи: разбор времени — when.py, расписание дел — jobs.py, деньги — money.py, синхронизация — sync.py и cloud.php.

Части (чистое ядро, 1.0.16): acts_confirm — «да/нет»; acts_quick — команды без модели; acts_alarm — напоминания и
будильник; acts_devices — свои устройства; acts_day — деньги и календарь; acts_base — слова просьб и помощники. Здесь —
_use_tool (политика, защита, вызов) и то, что рядом с ним: файлы напоминаний, источники ответа, передача специалисту."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
import modules


from acts_base import (
    art_page, _att_word, BRACKET_READ, CAPTURE_FOLDER, CONFIRM_NO, confirm_word, CONFIRM_YES, _CONFIRM_YES_RX,
    DRAFT_KINDS, DRAFT_RX, GEN_IMG_RX, NOTE_ASK_RX, NOTE_TOOLS, _PIC, QUERY_TOOLS, ROUTE_MAX, ROUTINE_HEAD,
    UPDATE_ASK_RX)  # noqa: F401 — прежние имена на месте
from acts_confirm import ConfirmMixin
from acts_quick import QuickMixin
from acts_alarm import AlarmMixin
from acts_devices import DevicesMixin
from acts_day import DayMixin


class ToolsMixin(ConfirmMixin, QuickMixin, AlarmMixin, DevicesMixin, DayMixin):
    # ---------- инструменты ----------

    def _use_tool(self, turn, call, sentences):  # noqa: C901
        """Выполнить вызов инструмента от модели: политика (выключен / спросить), защита от опасного, подтверждение,
        запуск. Шлёт события «tool» в окно. -> результат инструмента или текст для модели (отказ, ошибка, защита)."""
        name, args = call["name"], call["args"]
        on, need_confirm = self.toolbox.policy(name)
        title = self.toolbox.title(name)
        log.info("🛠  %s %s", name, redact(json.dumps(args, ensure_ascii=False))[:200])
        if not on:
            m = modules.of(name)
            if m is not None and self.toolbox.fuse.tripped(m["id"]):    # предохранитель (1.0): не «выключен пользователем»
                return (f"«{m['title']}» сейчас на паузе после сбоя и вернётся сама через несколько минут — скажи это человеку "
                        "одной фразой; остальное работает.")
            return f"Инструмент {name} выключен пользователем."
        from tools import TOOLS as _BUILTIN
        if name in _BUILTIN and hasattr(self, "health_use"):   # «чем пользуются» (13.11): какие встроенные умения зовёт модель —
            self.health_use("t:" + name)                   # только имя (плагины и MCP — свои имена людей, их не считаем)
        asked = getattr(turn, "asked", None)
        # дело по расписанию (via_job): его шаги в окнах не показываем — человеку только итог или ничего (владелец 11.11:
        # «запустились какие-то процессы — „Навык — готово“, а результата нет, непонятно, что это и зачем»)
        _temit = (lambda **kw: None) if getattr(turn, "via_job", False) else (lambda **kw: self.emit("tool", **kw))
        if name == "start_task" and isinstance(args, dict) and getattr(turn, "via_job", False):
            args = dict(args, _unattended=True)           # дело по расписанию: спросить «начинаю?» некого (HARNESS 7)
        if name in QUERY_TOOLS and isinstance(args, dict) and not str(args.get("query") or "").strip() and asked:
            # экзамен 0.38.49: find_notes({}) — модель потеряла аргументы, и «вспомни, что я говорил про работу» искало
            # «ничего»; тема — из самой просьбы («…про работу» → «работу»), иначе просьба целиком
            m = re.search(r"(?<![а-яё])(?:про|насч[её]т|об?|по поводу)\s+([^\s,.?!]+(?:\s+[^\s,.?!]+)?)", asked, re.I)
            args["query"] = (m.group(1) if m else asked).strip()[:200]
            if name == "show_images":                  # «сгенерь картинку …» — искать само «…», без просьбы
                args["query"] = GEN_IMG_RX.sub(" ", args["query"]).strip(" \t\"«»") or args["query"]
            log.info("🛠  %s без запроса — беру из просьбы: %s", name, redact(args["query"]))
        if name == "save_note" and asked:
            from quality import APPT_NOTE, appt_ask
            if appt_ask(asked):                        # дело со временем — в «Дела», а не в заметки (отчёт №94, 19.10)
                log.info("📝 дело со временем — не в заметки, а напоминанием")
                return APPT_NOTE
        if name in ("save_note", "update_note") and asked is not None and not NOTE_ASK_RX.search(asked) \
                and not (name == "update_note" and UPDATE_ASK_RX.search(asked)):
            # стихи, список идей, ответ на вопрос — в чат, а не в заметки без спроса (экзамен 11.10: «записала это в
            # заметку», хотя просили просто четверостишие)
            log.info("📝 save_note без просьбы записать — не пишу")
            # экзамен 17.10: на «Не записано» модель сказала человеку «Не вышло, система не дала сохранить» — это не сбой
            return ("Записывать не нужно: пользователь не просил сохранять. Это не ошибка — ничего о записи и сбоях не "
                    "говори, просто ответь на вопрос прямо в чате (список — пунктами в самом ответе).")
        if name == "set_reminder" and asked and isinstance(args, dict):
            args = self._reminder_time_guard(asked, args)
        if name in ("run_command", "server_run") and not str((args or {}).get("command") or "").strip():
            # экзамен 0.99 (15.11): run_command {} — пустой вызов, а человеку «Выполнить?» с пустой командой и «жду вашего
            # да»; «сколько места на диске» так и не узнали. Пустой вызов — не вопрос человеку, а подсказка модели
            log.info("🛠 %s без команды — не спрашиваю «Выполнить?»", name)
            _temit(name=name, title=title, status="error", error="без команды")
            return ("Команда пустая — ничего не выполнено, человека не спрашивай. Место на диске, память, нагрузка — "
                    "system_status (сразу, без вопроса). Разобрать папки и предложить структуру — start_task. Иначе вызови "
                    "run_command снова, с самой командой в поле command.")
        blocked, force, warn_q = self.toolbox.guard(name, args)
        if blocked:
            log.warning("🛡 Защита: %s %s — %s", name, json.dumps(args, ensure_ascii=False)[:200], blocked)
            _temit(name=name, title=title, status="error", error="защита: " + blocked)
            return (f"Защита Dewiar не дала это сделать: {blocked}. Объясни пользователю коротко и спокойно, что такое "
                    "ассистент не удаляет и не делает (это может сломать компьютер или стереть важное), и предложи "
                    "безопасный вариант — например, назвать конкретные файлы, которые убрать в корзину.")
        if need_confirm and not force and self.toolbox.auto_ok(name, args):
            need_confirm = False                       # команды «только посмотреть» (напр. на сервере) — без вопроса, если так настроено
        # рецензия 0.86 (№603): вызов, записанный текстом «[Вызов инструмента: …]», — не настоящий вызов модели; его можно
        # подсунуть. Только чтение — сразу, всё, что пишет людям, меняет данные или дом, — через «Выполнить?», всегда
        br_strict = bool(call.get("bracket")) and name not in BRACKET_READ
        if br_strict:
            log.info("🛠 %s записан текстом — спрашиваю «Выполнить?»", name)
            need_confirm = True
        if need_confirm or force:
            question = warn_q or self.toolbox.describe(name, args)
            # №353 (пакет 27.10 12:22): разбор сервера — двадцать команд подряд, и каждая — «На сервере … выполнить?
            # Подробности — на экране. Скажите «да» или «нет»» целиком, в ответе это читалось как «зациклился». Вторая и
            # дальше за ход — коротко; команда «только посмотреть» — можно ответить «всегда»: такие на этом сервере
            # дальше без вопроса (тот же выбор, что в студии → «Серверы» → «спрашивать только изменения»).
            ro = name == "server_run" and not force and self.toolbox.server_readonly(args)
            n_conf = getattr(turn, "confirms", 0)
            turn.confirms = n_conf + 1
            if not force and not n_conf and not br_strict and self._just_agreed(turn):
                # №478 (ПК 0.76): модель спросила словами «запустить?», человек ответил «да» — и тут же второй вопрос
                # «Выполнить?», который никто не ждал: 15 с тишины — и «отказ». Только что согласились — это и есть ответ
                log.info("Подтверждение: да (только что ответили «%s» на вопрос)", (turn.asked or "")[:20])
                ok = True
            else:
                turn.asking = title or name                 # №625–628: что ждёт разрешения (если перебьют на вопросе)
                ok = self._confirm(turn, question, sentences, always=ro, again=n_conf)
                turn.asking = ""
            if ok == "always":
                try:
                    srv = self.toolbox.hooks["servers"]
                    s_ = srv.find(str(args.get("server") or ""))
                    srv.update(s_["id"], {"ask": "changes"})
                    log.info("🖥 «%s»: команды «только посмотреть» — дальше без вопроса", s_.get("name"))
                except Exception as e:  # noqa: BLE001
                    log.info("сервер: «всегда» не сохранилось: %s", e)
            if ok is None:                             # промолчали — это не «нет» (№478: «отвечаю „да“ — считает отказом»)
                _temit(name=name, title=title, status="error", error="ответа не было — спрошу ещё раз")
                # экзамен 1.0.22 (skill_create_782): «Выполнить?» без ответа — а в ответе «Создала навык». Не сделано — записываем,
                # чтобы проверка «сказала, что сделала» (failed_claim) это поймала
                turn.tools_err = getattr(turn, "tools_err", []) + [(name, "не выполнено: человек ещё не ответил «да» на «Выполнить?»")]
                return ("Пользователь не ответил на вопрос «Выполнить?» — ответа не дождалась, это НЕ отказ. Ничего не делай; "
                        "одной фразой скажи, что ждёшь его «да» (кнопкой «Выполнить» или словами), и спроси ещё раз. "
                        "Не говори, что он отказался.")
            if not ok:
                _temit(name=name, title=title, status="declined")
                return "Пользователь отказался. Ничего не делай и коротко подтверди отказ."
        detail = _tool_detail(name, args)
        _temit(name=name, title=title, status="run", args=args, detail=detail)
        try:
            res = self.toolbox.run(name, args)
            turn.tools_ok = getattr(turn, "tools_ok", []) + [name]
            if name == "show_images" and asked and GEN_IMG_RX.search(asked):
                # отчёт 70: «сгенерь картинку „Жека-пулемёт“» — показали найденные в интернете и выдали за ответ; рисовать
                # картинки Dewiar не умеет — пусть модель скажет это честно
                art = next((n for n in (self.mcp.status().get("artist-main") or {}).get("tools") or [] if n == "art_draw"), "") \
                    if getattr(self, "mcp", None) else ""
                note = ("\n\nВАЖНО: это картинки, найденные в интернете, а не нарисованные. Рисовать ты умеешь сама — плагином "
                        "«Художник» (действие …art_draw): нарисуй то, что просили, а найденное покажи только как примеры."
                        if art else
                        "\n\nВАЖНО: это картинки, найденные в интернете, а не нарисованные. Рисовать (генерировать) картинки "
                        "Dewiar пока не умеет — скажи об этом честно одной фразой и предложи найденные как похожие; "
                        "нарисовать сама сможешь, если включить плагин «Художник» (студия → «Плагины») — предложи. "
                        "Не говори «нарисовала» и «сгенерировала».")
                res = dict(res, text=str(res.get("text", "")) + note) if isinstance(res, dict) else str(res) + note
            if name == "set_reminder" and asked and "\n\nВложения:" in asked and isinstance(res, str):
                res = self._reminder_link_files(turn, res)
            if re.search(r"art_(?:draw|animate)$", name):     # «Художник»: посмотреть на рисунок глазами (владелец 12.11)
                bad = self.eyes_page(art_page(res["text"] if isinstance(res, dict) else str(res)), str(args.get("title") or asked or ""))
                if bad:
                    note = (f"\n\nПОСМОТРЕЛА НА РИСУНОК (снимок экрана): {bad}. Поправь рисунок (тот же title, replace=true) — "
                            "это недоработка, а не вкус.")
                    res = dict(res, text=str(res.get("text", "")) + note) if isinstance(res, dict) else str(res) + note
            out = res["text"] if isinstance(res, dict) else str(res)
            if name in FACT_TOOLS and out.strip():          # что узнала — коротко в историю разговора (engine_answer)
                turn.facts = (getattr(turn, "facts", []) + [fact_line(name, args, out)])[-FACTS_PER_TURN:]
            _temit(name=name, title=title, status="done", detail=detail, result=out[:1500])
            if name in NOTE_TOOLS:                          # №633: удалила или поправила заметку — открытый список «Заметок» освежается
                self.emit("notes_changed")
            log.info("   ↳ %s", (res["text"] if isinstance(res, dict) else res)[:160].replace("\n", " "))
            return res
        except (ToolError, SkillError, MCPError) as e:
            log.info("   ↳ Ошибка: %s", redact(str(e))[:200].replace("\n", " "))    # №316 (пакет 27.10): в журнале не было видно, чем кончилось
            _temit(name=name, title=title, status="error", error=str(e))
            turn.tools_err = getattr(turn, "tools_err", []) + [(name, redact(str(e))[:300])]   # №573: не выдавать за сделанное
            return f"Ошибка: {e}"
        except Exception as e:  # noqa: BLE001
            log.exception("инструмент %s", name)
            _temit(name=name, title=title, status="error", error=str(e))
            turn.tools_err = getattr(turn, "tools_err", []) + [(name, redact(str(e))[:300])]
            return f"Ошибка: {e}"

    def _reminder_link_files(self, turn, res):
        """Модель поставила напоминание в ответ на сообщение с картинками или файлами («вот скрины, напомни завтра
        обсудить их с Сашей») — те же вложения кладём в заметку и привязываем к напоминанию: в срок они в окне.
        -> результат инструмента с пометкой для модели."""
        from engine_answer import ATT_PATH_RX, REF_RX
        m = re.search(r"\(id ([0-9a-f]+)\)", res)
        item = self.reminders.get(m.group(1)) if m else None
        if not item:
            return res
        note = getattr(turn, "att_note", None)
        if note is None:
            data = []
            for rel in dict.fromkeys(ATT_PATH_RX.findall(turn.asked.split("\n\nВложения:", 1)[1])):
                try:
                    data.append((Path(rel).name, self.workspace.safe(rel).read_bytes()))
                except Exception:  # noqa: BLE001
                    continue
            if not data:
                return res
            r = {"text": item["text"], "at": datetime.fromisoformat(item["at"])}
            try:
                note = self._reminder_note_from(r, turn.asked, data, chat=False)
            except Exception as e:  # noqa: BLE001
                log.info("Вложения к напоминанию не легли: %s", e)
                return res
            turn.att_note = note
        patch = {"note": note["path"]}
        if item["text"] in ("Напоминание", "") or REF_RX.match(item["text"]):
            patch["text"] = note["path"].rsplit("/", 1)[-1][:-3]          # «напомни об этом» — название по вложениям
        self.reminders.update(item["id"], patch)
        n = len(note["att"])
        log.info("📎 К напоминанию «%s» — вложения сообщения (%d)", item["text"], n)
        return res + f" Вложения из сообщения ({n}) приложены к напоминанию — в срок они будут прямо в окне напоминания; можно так и сказать."


    TASK_REPLY_RX = re.compile(r"разреш|дай|даю|доступ|права?\b|папк|можно|нельзя|не надо|не нужно|путь|лежит|находится|"
                               r"[a-z]:\\|/home/|~/", re.I)

    def note_files_out(self, rel, paths):
        """Фото и файлы заметки отсюда — своим телефонам (E2E, Close.natt_share), чтобы напоминание с картинками открывалось
        и там. Через 5 с одним конвертом: студия кладёт файлы по одному, а конвертов в час у облака немного."""
        if getattr(self, "close", None) is None or not paths:
            return
        with self._natt_lock():
            q = self.__dict__.setdefault("_natt_out", {})
            q.setdefault(rel, []).extend(p for p in paths if p not in q.get(rel, []))
            t = self.__dict__.get("_natt_t")
            if t is not None:
                t.cancel()
            self._natt_t = threading.Timer(5, self._natt_out_run)
            self._natt_t.daemon = True
            self._natt_t.start()

    def _natt_lock(self):
        return self.__dict__.setdefault("_natt_lk", threading.Lock())

    def _natt_out_run(self):
        with self._natt_lock():
            q, self._natt_out = dict(self.__dict__.get("_natt_out") or {}), {}
        for rel, paths in q.items():
            try:
                files = [(p, self.workspace.safe(p)) for p in paths]
                files = [(r, f) for r, f in files if f.is_file()]
                sy = getattr(self, "sync", None)
                sid = sy.note_sid(rel) if sy is not None else ""
                if files and sid:
                    self.close.natt_share(sid, rel.rsplit("/", 1)[-1][:-3], files)
            except Exception as e:  # noqa: BLE001 — нет связи или входа: на телефоне останется заметка без картинок
                log.info("вложения заметки — телефону: не отправились: %s", e)

    def capture_save(self, text, files, images):
        """«Закинуть идею» (окно capture.html по Ctrl+Alt+N): без модели и без голоса. «Напомни завтра в 10 …» —
        напоминание (с картинками — в их заметке, как _reminder_with_files), остальное — заметка в «Заметки/Идеи»
        с картинками и файлами. -> {kind, title, when?, path?, att}."""
        import base64
        from when import parse as parse_when
        data = []
        for k, im in enumerate(images[:12]):
            mime = im[5:im.index(";")] if im.startswith("data:") and ";" in im[:40] else "image/jpeg"
            ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(mime, ".jpg")
            files.append({"name": time.strftime("Снимок %d.%m %H-%M-%S") + (f" ({k + 1})" if k else "") + ext, "b64": im})
        for f in files[:12]:
            raw = str(f.get("b64") or "")
            try:
                b = base64.b64decode(raw.split(",", 1)[1] if raw.startswith("data:") else raw)
            except ValueError:
                continue
            if b:
                data.append((Path(str(f.get("name") or "файл")).name or "файл", b))
        text = re.sub(r"[ \t]+\n", "\n", str(text or "")).strip()
        if not text and not data:
            raise ValueError("пусто — напишите мысль или вставьте картинку")
        r = parse_when(text) if re.match(r"(?i)\s*(напомни|напоминай|разбуди|будильник|таймер|засеки)", text) else None
        if r:
            from when import human
            if data:
                self._reminder_note_from(r, text, data, chat=False)
            item = self.reminders.add(r["at"], r["text"], r["repeat"], r["kind"], extra={"note": r.get("note")})
            pub = self._reminder_public(item)
            self.emit("reminder_set", item=pub, text="")
            log.info("💡 Идея → напоминание %s: %s (вложений %d)", human(r["at"]), r["text"], len(data))
            return {"kind": "reminder", "title": item["text"], "when": pub["when"], "id": item["id"], "att": pub.get("att", 0)}
        first = text.split("\n", 1)[0].strip()
        words = re.sub(r"[.!?…:;—].*$", "", first).split()          # название — до первой точки, двоеточия, тире
        title = (" ".join(words[:7]) + ("…" if len(words) > 7 else "")).strip(" ,:;—-") if words else time.strftime("Идея %d.%m %H-%M")
        note = self.workspace.note_with_files(title, text, data, folder=CAPTURE_FOLDER)
        if note["att"]:
            self.note_files_out(note["path"], [x["path"] for x in note["att"]])
        sy = getattr(self, "sync", None)
        if sy is not None:
            sy.soon.set()
        self.emit("note_saved", kind="note", title=note["path"].rsplit("/", 1)[-1][:-3], path=note["path"], text=text[:200])
        self.emit("notes_changed")
        log.info("💡 Идея → %s (вложений %d)", note["path"], len(note["att"]))
        return {"kind": "note", "title": note["path"].rsplit("/", 1)[-1][:-3], "path": note["path"], "att": len(note["att"])}

    def _turn_sources(self, items):
        """search_documents нашёл файлы — запомнить их у текущего хода; после ответа под ним — источники (_sources_done)."""
        turn = getattr(self, "turn", None)
        if turn is None:
            return
        have = {x["key"] for x in getattr(turn, "sources", [])}
        turn.sources = getattr(turn, "sources", []) + [x for x in items if x["key"] not in have]

    def _sources_done(self, turn, answer):
        """Источники ответа: файлы из поиска по документам, которые ответ называет (имя или его начало); не назвал ни
        одного, а файл один — он. -> [{kind: file, name, key, label}] (их показывают виджет и «Чат»: нажать — открыть)."""
        src = getattr(turn, "sources", None) or []
        if not src or not (answer or "").strip():
            return []
        low = answer.lower().replace("ё", "е")

        def named(x):
            stem = Path(x["name"]).stem.lower().replace("ё", "е")
            return stem and (stem in low or (len(stem) > 12 and stem[:12] in low) or x["name"].lower() in low)
        hit = [x for x in src if named(x)]
        if not hit and len({x["key"] for x in src}) == 1:
            hit = src[:1]
        return [{"kind": "file", "name": x["name"], "key": x["key"], "label": x["label"]} for x in hit[:4]]


    TASK_DEL_RX = re.compile(r"^(?:[\w-]+,\s*)?(?:удали|удалите|убери|уберите|сотри)\s+(?:фонов\w+\s+)?задач[уи]\s+"
                             r"[«\"“„']?(?P<name>[^»\"”'.,!?]{2,60}?)[»\"”']?\s*(?:[,.!—–-].*)?$", re.I)


    _SEND_RX = re.compile(r"^\s*(?:[А-ЯЁ][а-яё]+\s*,\s*)?(?:пожалуйста,?\s*)?(?:отправь|напиши|передай|скинь)(?:\s+пожалуйста)?"
                          r"(?:\s+сообщение)?\s+(?P<who>[А-ЯЁа-яё-]+(?:\s+[А-ЯЁа-яё-]+){0,2}?)(?:\s+сообщение)?"
                          r"\s*(?:[:.,—–-]\s*(?:что\s+)?|\s+что\s+|\s*(?=[«\"„]))(?P<msg>\S.*)$", re.I | re.S)


    MAIL_TABLE_RX = re.compile(r"(?=.*(?:excel|эксел|ексел|xlsx|таблиц))(?=.*(?:почт|письм|ящик|inbox))"
                               r"(?=.*(?:подготов|сдела|выгруз|созда|состав|сформир|собер|собери|экспорт|нужн))", re.I | re.S)

    # ---------- «Поручения» с телефона руководителя (0.56) ----------

    TEAM_CMDS = ("assign", "accept", "back", "cancel", "remind", "message")


    SNOOZE_RX = re.compile(r"\b(отлож\w*|позже|потом|ещ[её]\s+\d+|через\s+\d+|через\s+(?:минуту|полчаса|час)|дай\s+поспать|не\s+сейчас)\b")
    ACK_WORDS = {"выпил", "выпила", "выпью", "принял", "приняла", "пью",          # лекарство (режим «Для старших»)
                 "понял", "поняла", "понятно", "хорошо", "ок", "окей", "ладно", "готово", "сделал", "сделала", "выключи",
                 "выключай", "отключи", "спасибо", "да", "встаю", "встал", "встала", "иду", "всё", "все"}

    def _route(self, text):
        """Главный помощник передаёт вопрос специалисту команды (код — Кодеру, письмо — Лире, «включи» — Джарвису…).
        Только если сейчас говорит главный и в студии включено «Команда специалистов». → id или None."""
        if self.s.get("team", "route") is False:
            return None
        cur = self.personas.get(self.s.get("persona"))
        if not cur.get("main"):
            return None
        # №566: «прикрепил .md с задачей — вверху Лира, а отвечает Ирис»: в тексте приложенного файла нашлось «книгу» — и вопрос
        # ушёл библиотекарю. Специалиста выбираем по словам самого человека: без вложений и не по длинной вставке (документ,
        # промпт, письмо целиком — это не короткая просьба к специалисту, отвечает тот, с кем говорят)
        own = str(text or "").split("\n\nВложения:", 1)[0].strip()
        if not own or len(own) > ROUTE_MAX or own.count("\n") > 6:
            return None
        low = _norm(own)
        order = ["agent", "lira", "jarvis", "eva", "patrik"]
        others = sorted((p for p in self.personas.all() if p.get("route") and p["id"] != cur["id"]),
                        key=lambda p: order.index(p["id"]) if p["id"] in order else -1)   # свои и из галереи — первыми
        for p in others:
            try:
                if re.search(p["route"], low):
                    return p["id"]
            except re.error:
                continue
        return None


    AGENDA_Q = re.compile(r"по\s+плану|\bплан(?:ы|ов)?\s+(?:на|у\s+(?:нас|меня))|как(?:ие|ой)\s+(?:у\s+(?:нас|меня)\s+)?(?:сегодня\s+|завтра\s+)?(?:план|дела)"
                          r"|что\s+(?:у\s+(?:нас|меня)\s+)?(?:на\s+|в\s+)?(?:сегодня|завтра|послезавтра|эт\w+\s+недел\w+)(?:\s*\?|\s*$|\s+(?:по\s+плану|запланирован|в\s+календаре))"
                          r"|расписани\w+|что\s+(?:у\s+(?:нас|меня)\s+)?запланирован|мои\s+дела|чем\s+(?:я\s+)?занят|повестк\w+\s+дня"
                          r"|что\s+мне\s+(?:сегодня\s+|завтра\s+)?(?:надо|нужно)\s+(?:сделать|успеть)"
                          # экзамен 14.10: «что у меня в среду?» — день недели (и память «встреча в среду» тоже)
                          r"|(?:что|какие\s+планы|как\w*\s+дела)\s+(?:у\s+(?:нас|меня)\s+)?(?:на\s+|в\s+|во\s+)"
                          r"(?:понедельник|вторник|сред\w|четверг|пятниц\w|суббот\w|воскресень\w)", re.I)
    WEEKDAY_Q = (("понедельник", 0), ("вторник", 1), ("сред", 2), ("четверг", 3), ("пятниц", 4), ("суббот", 5), ("воскресен", 6))


    JOB_LATE_MAX = 2 * 3600            # с: дело по расписанию, опоздавшее больше, — пропускаем (вчерашний итог дня утром не нужен)
    JOB_TITLES = {"brief": "Утренняя сводка", "fx": "Курс валют", "evening": "Итог дня", "week": "Итоги недели",
                  "news": "Главные новости", "weather": "Погода и что надеть"}
