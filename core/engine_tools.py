"""Движок Dewiar: вызов инструментов с подтверждением, напоминания и будильник, синхронизация устройств, деньги.
Примесь класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Состав: _use_tool/_confirm (политика, защита и вопрос «да/нет» голосом или кнопками Telegram); звонок будильника
(_on_reminder → _alarm_loop → alarm_finish) и голосовые «отложи/понял»; команды студии для напоминаний и дел;
быстрые ответы без модели (_capture, _say_quick, _money_cmd); сводка месяца для календаря (calendar_month).
Связи: разбор времени — when.py, расписание дел — jobs.py, деньги — money.py, синхронизация — sync.py и cloud.php."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


# просьба записать: «запиши», «сохрани», «в заметки», «запомни списком», «зафиксируй», «в файл»
NOTE_ASK_RX = re.compile(r"заметк|запиш|запис|сохран|запомн|занеси|зафиксир|в\s+файл|в\s+папк|конспект", re.I)

# «сгенерируй / нарисуй картинку …» — просьба нарисовать, а не найти (отчёт 70); слово «картинку» — часть просьбы
_PIC = r"(?:картинк|изображени|рисун|арт|аватар|логотип|постер|обо[ий])\w*"
GEN_IMG_RX = re.compile(r"(?<![а-яё])(?:(?:с?генерир\w*|сгенер\w*|сгень\w*|нарису\w*|изобраз\w*)(?:\s+(?:мне\s+|нам\s+)?" + _PIC + r")?"
                        r"|(?:создай|сделай|придумай)\w*\s+(?:мне\s+|нам\s+)?" + _PIC + ")", re.I)
QUERY_TOOLS = ("find_notes", "web_search", "show_images")     # без query — бессмысленны: тему берём из просьбы


CAPTURE_FOLDER = "Идеи"            # «Закинуть идею» (capture_save) — заметки сюда: «Заметки/Идеи/…»


def _att_word(att):
    """[{kind…}] -> «2 картинки», «картинка и файл» — для уведомлений."""
    def plural(n, one, few, many):
        return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many
    pics = sum(1 for f in att if f["kind"] == "image")
    files = len(att) - pics
    parts = []
    if pics:
        parts.append(f"{pics} " + plural(pics, "картинка", "картинки", "картинок"))
    if files:
        parts.append(f"{files} " + plural(files, "файл", "файла", "файлов"))
    return " и ".join(parts)



# «запиши в книгу / статью / стихи…: текст» — черновики автора (_draft_cmd)
DRAFT_KINDS = [("книг", "Книга"), ("стат", "Статья"), ("стих", "Стихи"), ("рассказ", "Рассказ"), ("роман", "Роман"),
               ("сценари", "Сценарий"), ("черновик", "Черновик"), ("песн", "Песня"), ("пост", "Пост"), ("сказк", "Сказка"),
               ("мемуар", "Мемуары")]
DRAFT_RX = re.compile(r"^(?:[А-ЯЁа-яёA-Za-z]+,\s*)?(?:запиши|допиши|добавь|занеси)\s+(?:в|во)\s+(?:мо[юйеи]\s+|наш[уеи]?\s+)?"
                      r"(?P<kind>книг[уеи]|стать[юи]|стих[иа]?|рассказ|роман|сценари[йи]|черновик|песн[юи]|пост|сказк[уи]|мемуары)"
                      r"(?:\s+[«\"](?P<name>[^»\"]{2,40})[»\"])?\s*(?:[:,—–-]\s*|\s+)(?:что\s+)?(?P<body>\S.{2,})$", re.I | re.S)

class ToolsMixin:
    # ---------- инструменты ----------

    def _use_tool(self, turn, call, sentences):  # noqa: C901
        """Выполнить вызов инструмента от модели: политика (выключен / спросить), защита от опасного, подтверждение,
        запуск. Шлёт события «tool» в окно. -> результат инструмента или текст для модели (отказ, ошибка, защита)."""
        name, args = call["name"], call["args"]
        on, need_confirm = self.toolbox.policy(name)
        title = self.toolbox.title(name)
        log.info("🛠  %s %s", name, redact(json.dumps(args, ensure_ascii=False))[:200])
        if not on:
            return f"Инструмент {name} выключен пользователем."
        asked = getattr(turn, "asked", None)
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
        if name == "save_note" and asked is not None and not NOTE_ASK_RX.search(asked):
            # стихи, список идей, ответ на вопрос — в чат, а не в заметки без спроса (экзамен 11.10: «записала это в
            # заметку», хотя просили просто четверостишие)
            log.info("📝 save_note без просьбы записать — не пишу")
            # экзамен 17.10: на «Не записано» модель сказала человеку «Не вышло, система не дала сохранить» — это не сбой
            return ("Записывать не нужно: пользователь не просил сохранять. Это не ошибка — ничего о записи и сбоях не "
                    "говори, просто ответь на вопрос прямо в чате (список — пунктами в самом ответе).")
        if name == "set_reminder" and asked and isinstance(args, dict):
            args = self._reminder_time_guard(asked, args)
        blocked, force, warn_q = self.toolbox.guard(name, args)
        if blocked:
            log.warning("🛡 Защита: %s %s — %s", name, json.dumps(args, ensure_ascii=False)[:200], blocked)
            self.emit("tool", name=name, title=title, status="error", error="защита: " + blocked)
            return (f"Защита Dewiar не дала это сделать: {blocked}. Объясни пользователю коротко и спокойно, что такое "
                    "ассистент не удаляет и не делает (это может сломать компьютер или стереть важное), и предложи "
                    "безопасный вариант — например, назвать конкретные файлы, которые убрать в корзину.")
        if need_confirm and not force and self.toolbox.auto_ok(name, args):
            need_confirm = False                       # команды «только посмотреть» (напр. на сервере) — без вопроса, если так настроено
        if need_confirm or force:
            question = warn_q or self.toolbox.describe(name, args)
            ok = self._confirm(turn, question, sentences)
            if not ok:
                self.emit("tool", name=name, title=title, status="declined")
                return "Пользователь отказался. Ничего не делай и коротко подтверди отказ."
        detail = _tool_detail(name, args)
        self.emit("tool", name=name, title=title, status="run", args=args, detail=detail)
        try:
            res = self.toolbox.run(name, args)
            turn.tools_ok = getattr(turn, "tools_ok", []) + [name]
            if name == "show_images" and asked and GEN_IMG_RX.search(asked):
                # отчёт 70: «сгенерь картинку „Жека-пулемёт“» — показали найденные в интернете и выдали за ответ; рисовать
                # картинки Dewiar не умеет — пусть модель скажет это честно
                note = ("\n\nВАЖНО: это картинки, найденные в интернете, а не нарисованные. Рисовать (генерировать) картинки "
                        "Dewiar пока не умеет — скажи об этом честно одной фразой и предложи найденные как похожие. "
                        "Не говори «нарисовала» и «сгенерировала».")
                res = dict(res, text=str(res.get("text", "")) + note) if isinstance(res, dict) else str(res) + note
            if name == "set_reminder" and asked and "\n\nВложения:" in asked and isinstance(res, str):
                res = self._reminder_link_files(turn, res)
            out = res["text"] if isinstance(res, dict) else str(res)
            if name in FACT_TOOLS and out.strip():          # что узнала — коротко в историю разговора (engine_answer)
                turn.facts = (getattr(turn, "facts", []) + [fact_line(name, args, out)])[-FACTS_PER_TURN:]
            self.emit("tool", name=name, title=title, status="done", detail=detail, result=out[:1500])
            log.info("   ↳ %s", (res["text"] if isinstance(res, dict) else res)[:160].replace("\n", " "))
            return res
        except (ToolError, SkillError, MCPError) as e:
            self.emit("tool", name=name, title=title, status="error", error=str(e))
            return f"Ошибка: {e}"
        except Exception as e:  # noqa: BLE001
            log.exception("инструмент %s", name)
            self.emit("tool", name=name, title=title, status="error", error=str(e))
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

    def _confirm(self, turn, question, sentences, timeout=15):
        """Спросить голосом и кнопками, дождаться «да»/«нет». -> True, если согласились.
        Ответ приходит из другого потока через pending_confirm (_answer_confirm или кнопка). Голосом — сперва ждём,
        пока договорится уже начатый ответ, затем слушаем timeout секунд; молчание — это «нет»."""
        if turn.via and turn.via.get("confirm"):             # вопрос из Telegram — и подтверждение там же, кнопками
            box = {"event": threading.Event(), "answer": False}
            self.pending_confirm = box
            self.emit("confirm", text=question)
            turn.via["confirm"](question)
            box["event"].wait(300)
            self.pending_confirm = None
            self.emit("confirm_done", ok=box["answer"])
            log.info("Подтверждение (Telegram): %s", "да" if box["answer"] else "нет")
            return box["answer"] and not turn.cancel.is_set()
        sentences.put(_spoken_question(question) + " Скажите «да» или «нет».")
        drained = threading.Event()
        sentences.put(("sync", drained))
        drained.wait(30)
        if turn.cancel.is_set():
            return False
        box = {"event": threading.Event(), "answer": False}
        self.pending_confirm = box
        self.emit("confirm", text=question)
        self.follow_up_until = time.monotonic() + timeout
        self.set_state("listening")
        box["event"].wait(timeout)
        self.pending_confirm = None
        self.emit("confirm_done", ok=box["answer"])
        log.info("Подтверждение: %s", "да" if box["answer"] else "нет")
        self.set_state("thinking")
        return box["answer"]

    def _answer_confirm(self, text):
        """Разобрать услышанное как ответ на вопрос _confirm. -> True, если фраза была ответом и вопрос закрыт."""
        box = self.pending_confirm
        if not box:
            return False
        w = set(re.findall(r"[\wё]+", _norm(text)))
        if w & {"да", "давай", "выполняй", "подтверждаю", "конечно", "ага", "угу", "можно", "делай", "yes", "ок", "окей"}:
            box["answer"] = True
        elif not (w & {"нет", "не", "отмена", "отмени", "стоп", "no", "не надо"}):
            return False                       # непонятный ответ — ждём дальше
        box["event"].set()
        return True

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

    TASK_DEL_RX = re.compile(r"^(?:[\w-]+,\s*)?(?:удали|удалите|убери|уберите|сотри)\s+(?:фонов\w+\s+)?задач[уи]\s+"
                             r"[«\"“„']?(?P<name>[^»\"”'.,!?]{2,60}?)[»\"”']?\s*(?:[,.!—–-].*)?$", re.I)

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

    _SEND_RX = re.compile(r"^\s*(?:[А-ЯЁ][а-яё]+\s*,\s*)?(?:пожалуйста,?\s*)?(?:отправь|напиши|передай|скинь)(?:\s+пожалуйста)?"
                          r"(?:\s+сообщение)?\s+(?P<who>[А-ЯЁа-яё-]+(?:\s+[А-ЯЁа-яё-]+){0,2}?)(?:\s+сообщение)?"
                          r"\s*(?:[:.,—–-]\s*(?:что\s+)?|\s+что\s+|\s*(?=[«\"„]))(?P<msg>\S.*)$", re.I | re.S)

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
            return False
        if any(match_name(w, [p]) is not p for w in who.split()):
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
            log.warning("черновик: %s", e)
            return False
        n = len(body.split())
        w = "слово" if n % 10 == 1 and n % 100 != 11 else "слова" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "слов"
        acc = {"Книга": "Книгу", "Статья": "Статью", "Песня": "Песню", "Сказка": "Сказку"}.get(title, title)   # «в «Книгу»»
        self._say_quick(f"Записала в «{acc}» — {n} {w}.", text, via)
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

    def credentials(self):
        """Чем входить в облако. -> (токен, ключ_для_связки, базовый адрес cloud.php).
        Токен — вход в аккаунт dewiar.pro, иначе ключ Dewiar. Если есть и то и другое, ключ отдаётся вторым, чтобы
        сервер связал его с аккаунтом. Адрес — из настроек, иначе из данных аккаунта (services.cloud)."""
        from cloud import base_of
        acc = self.account.token() if self.account.logged_in() else ""
        key = self.s.get("cloud", "key") or ""
        url = self.s.get("cloud", "url") or ""
        if not url and acc:
            svc = (self.account.data.get("services") or {}).get("cloud") or "/dwrapp/cloud.php"
            url = svc if svc.startswith("http") else (self.account.data.get("server") or "https://dewiar.pro").rstrip("/") + "/" + svc.lstrip("/")
        token = acc or key
        return token, (key if acc else ""), base_of(url)

    def _dewiar_web(self, kind, value):
        """Поиск (kind="search"), картинки (kind="images") или текст страницы (kind="fetch") через cloud.php — когда провайдер режет поисковик или сайт.
        Нужен вход в аккаунт dewiar.pro или ключ Dewiar, иначе RuntimeError. -> список результатов / текст."""
        import httpx
        if self.s.get("net", "web_via") is False:      # человек выключил запасной путь (письмо 19.10: рабочие данные — только напрямую)
            raise RuntimeError("запасной путь через сервер Dewiar выключен в настройках")
        token, _, url = self.credentials()
        if not token:
            raise RuntimeError("нет входа в аккаунт dewiar.pro и ключа Dewiar")
        p = {"p": "/" + kind, "q": value} if kind in ("search", "images") else {"p": "/fetch", "url": value}
        r = httpx.get(url, params=p, headers={"Authorization": "Bearer " + token}, timeout=40)
        try:
            d = r.json()
        except ValueError:
            d = {}
        if r.status_code != 200:
            raise RuntimeError((d.get("error") or {}).get("message") or f"сервер ответил {r.status_code}")
        return (d.get("results") or []) if kind in ("search", "images") else str(d.get("text") or "")

    # ---------- общее для своих устройств (close.own_send, сквозное шифрование): ключ умного дома ----------
    def own_snapshot(self):
        out = {}
        h = self.home.share()
        if h:
            out["home"] = h
        k = self.sync_key.share() if getattr(self, "sync_key", None) else None
        if k:
            out["sync_key"] = k                    # ключ шифрования синхронизации — только своим устройствам, конвертом
        return out or None

    def own_apply(self, body):
        h = (body or {}).get("home")
        if isinstance(h, dict) and self.home.adopt(h.get("token"), h.get("at")):
            self.emit("tools", tools=self.toolbox.catalog())
        k = (body or {}).get("sync_key")
        if isinstance(k, dict) and getattr(self, "sync_key", None) and self.sync_key.adopt(k.get("k"), k.get("at")):
            log.info("🔐 Ключ шифрования синхронизации получен со своего устройства")
            self.sync.key_arrived()

    def sync_key_wanted(self):
        """В облаке зашифрованное, а ключа здесь нет — попросить у своих устройств (не чаще раза в 10 минут)."""
        import time as _t
        if _t.time() - getattr(self, "_key_asked", 0) < 600 or not getattr(self, "close", None):
            return
        self._key_asked = _t.time()
        import threading
        threading.Thread(target=self.close._own_quiet, args=({"want": ["sync_key"]},), daemon=True).start()

    def note_rel_of(self, nid):
        """Заметка, пришедшая синхронизацией с id другого устройства, -> её путь в папке ассистента («Заметки/…») или None."""
        from sync import NOTES
        rel = (self.sync.state.get("map") or {}).get(str(nid))
        if rel and (self.workspace.ensure() / NOTES / rel).is_file():
            return f"{NOTES}/{rel}"
        return None

    def own_share(self):
        """Умный дом поменяли здесь — отправить своим устройствам (в фоне; нет связи — дойдёт со следующим изменением)."""
        snap = self.own_snapshot()
        if snap and self.credentials()[0]:
            import threading
            threading.Thread(target=self.close._own_quiet, args=(snap,), daemon=True).start()

    def device_name(self):
        from sync import default_device_name
        return default_device_name()

    def sync_public(self):
        st = dict(self.sync.status)
        tok, _, _ = self.credentials()
        st["available"] = bool(tok)
        st["on"] = self.s.get("sync", "enabled") is not False
        st["e2e"] = self.sync.e2e_status()
        st["via"] = "аккаунту dewiar.pro" if self.account.logged_in() else ("ключу Dewiar …" + (self.s.get("cloud", "key") or "")[-4:] if tok else "")
        return st

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
        pcm = alarm_tone(self.s.get("reminders", "sound") or "bells")
        say = self.s.get("reminders", "speak") is not False
        phrase = ({"alarm": "Пора вставать! ", "timer": "Время вышло! "}.get(kind, "Напоминание: ") +
                  (item["text"] if item["text"] not in ("Будильник", "Таймер", "Напоминание") else "")).strip()
        if item.get("late"):
            phrase = "Пропущенное напоминание: " + item["text"]
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
            a["done"].wait(1.2 if n < 3 else 3.0)
            n += 1
        with self._alarm_lock:
            if self.alarm is a:
                self.alarm = None
        if not a["result"]:
            a["result"] = "missed"
            log.info("⏰ Никто не ответил — «%s» отмечено пропущенным", item["text"])
            self.emit("alarm_done", id=item["id"], result="missed")
            if self.state == "listening" and self.turn is None:
                self.set_state("idle")

    def _ring(self, pcm, a):
        """Проиграть звонок один раз отдельным плеером (PCM 16 бит, 22050 Гц) — чтобы не мешать очереди речи."""
        if self.player is None:
            time.sleep(2.4)
            return
        pl = Player(device=self.player.device, null=self.null_player)
        try:
            pl.start(22050)
            step = 22050 * 2 // 10                               # по 0,1 с — чтобы «Готово» обрывало звонок сразу
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
                                     extra={k: item.get(k) for k in ("note", "note_id")})     # картинки — и при отложенном
            out.update(snooze_id=new["id"], when=human(when))
            log.info("⏰ Отложено на %d мин: %s", minutes, item["text"])
        else:
            log.info("⏰ Готово: %s", item["text"])
        self.emit("alarm_done", **out)
        if self.state == "listening" and self.turn is None:
            self.set_state("idle")
        return out

    SNOOZE_RX = re.compile(r"\b(отлож\w*|позже|потом|ещ[её]\s+\d+|через\s+\d+|через\s+(?:минуту|полчаса|час)|дай\s+поспать|не\s+сейчас)\b")
    ACK_WORDS = {"понял", "поняла", "понятно", "хорошо", "ок", "окей", "ладно", "готово", "сделал", "сделала", "выключи",
                 "выключай", "отключи", "спасибо", "да", "встаю", "встал", "встала", "иду", "всё", "все"}

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
        if is_sleep_phrase(text) or words & self.ACK_WORDS:
            if self.alarm_finish("ack"):
                self.emit("heard", text=text)
                self.play_tone("done")
            return True
        self.alarm_finish("ack")                       # заговорили о другом — значит, увидели; продолжаем разговор
        return False

    def _route(self, text):
        """Главный помощник передаёт вопрос специалисту команды (код — Кодеру, письмо — Лире, «включи» — Джарвису…).
        Только если сейчас говорит главный и в студии включено «Команда специалистов». → id или None."""
        if self.s.get("team", "route") is False:
            return None
        cur = self.personas.get(self.s.get("persona"))
        if not cur.get("main"):
            return None
        low = _norm(text)
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
            pcm = alarm_tone(a.get("sound") or self.s.get("reminders", "sound") or "bells")
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
        if cmd == "reminder_update":
            patch = dict(a.get("patch") or {})
            if patch.get("when"):
                r = parse_when("напомни " + patch.pop("when"))
                if not r:
                    raise ValueError("не понял время")
                patch.update(at=r["at"].isoformat(timespec="seconds"), repeat=r["repeat"])
            r = self.reminders.update(a.get("id"), patch)
            if not r:
                raise ValueError("нет такого напоминания")
            return self._reminder_public(r)
        if cmd == "reminder_cancel":
            return self.reminders.cancel(a.get("id", ""))
        return None

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
            log.info("Быстрая заметка не записалась (%s) — спрошу модель", e)
            return False
        log.info("📝 %s → %s", c["op"], rel)
        self.emit("note_saved", **card)
        self._say_quick(msg, said, via)
        return True

    def _say_quick(self, msg, said, via=None, then=None, note=None, acts=None):
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

        def run():
            self._speak_worker(turn, q)
            self.history += [{"role": "user", "content": said}, {"role": "assistant", "content": msg + (f" (Расчёт: {note}.)" if note else ""),
                                                                 "who": self.s.get("persona"), **({"acts": list(acts)} if acts else {})}]
            self._conv_after()
            with self._turn_lock:
                if self.turn is turn:
                    self.turn = None
                    self.set_state("idle")
            if then and not turn.cancel.is_set():
                then()
        threading.Thread(target=run, daemon=True).start()

    # ---------- деньги: «купил … за …», «получил зарплату …», «сколько я потратил …» ----------

    def _default_currency(self):
        """Валюта из настроек, иначе догадка по часовому поясу системы (Минск, Киев, Алматы), по умолчанию RUB."""
        c = (self.s.get("money", "currency") or "").strip().upper()
        if c:
            return c
        try:
            tz = Path("/etc/timezone").read_text().strip() if Path("/etc/timezone").exists() else os.path.realpath("/etc/localtime")
        except OSError:
            tz = ""
        tz = tz or time.tzname[0]
        return "BYN" if "Minsk" in tz else "UAH" if "Kiev" in tz or "Kyiv" in tz else "KZT" if "Almaty" in tz else "RUB"

    def _money_cmd(self, text, via=None):
        """Записать доход/расход, отменить последнюю запись (не старше 3 дней) или ответить «сколько потратил».
        -> True, если фраза разобрана и ответ дан без модели."""
        from money import fmt, parse
        c = parse(text, self._default_currency())
        if not c:
            return False
        if c["op"] == "add":
            it = self.money.add(c["kind"], c["amount"], c["currency"], c["category"], c["note"], c["date"], said=text)
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

    AGENDA_Q = re.compile(r"по\s+плану|\bплан(?:ы|ов)?\s+(?:на|у\s+(?:нас|меня))|как(?:ие|ой)\s+(?:у\s+(?:нас|меня)\s+)?(?:сегодня\s+|завтра\s+)?(?:план|дела)"
                          r"|что\s+(?:у\s+(?:нас|меня)\s+)?(?:на\s+|в\s+)?(?:сегодня|завтра|послезавтра|эт\w+\s+недел\w+)(?:\s*\?|\s*$|\s+(?:по\s+плану|запланирован|в\s+календаре))"
                          r"|расписани\w+|что\s+(?:у\s+(?:нас|меня)\s+)?запланирован|мои\s+дела|чем\s+(?:я\s+)?занят|повестк\w+\s+дня"
                          r"|что\s+мне\s+(?:сегодня\s+|завтра\s+)?(?:надо|нужно)\s+(?:сделать|успеть)"
                          # экзамен 14.10: «что у меня в среду?» — день недели (и память «встреча в среду» тоже)
                          r"|(?:что|какие\s+планы|как\w*\s+дела)\s+(?:у\s+(?:нас|меня)\s+)?(?:на\s+|в\s+|во\s+)"
                          r"(?:понедельник|вторник|сред\w|четверг|пятниц\w|суббот\w|воскресень\w)", re.I)
    WEEKDAY_Q = (("понедельник", 0), ("вторник", 1), ("сред", 2), ("четверг", 3), ("пятниц", 4), ("суббот", 5), ("воскресен", 6))

    def agenda_context(self, text):
        """Вопрос о планах («что у нас по плану», «какие дела на завтра», «расписание на неделю») — дела, напоминания и
        встречи календаря на эти дни сразу в подсказку модели. Раньше модель отвечала «достаю календарь — одну секунду»
        и не вызывала инструменты (отчёт 14.10): данные уже перед ней — отвечать есть чем. -> текст для системной подсказки или ""."""
        t = (text or "").split("\n\nВложения:")[0]
        if not self.AGENDA_Q.search(t):
            return ""
        today = datetime.now().date()
        low = t.lower()
        if "послезавтра" in low:
            days = [today + timedelta(days=2)]
        elif "завтра" in low:
            days = [today + timedelta(days=1)]
        elif re.search(r"(?<![а-яё])недел", low):          # «на неделю», но не «на понедельник» (в нём тоже «недел»)
            days = [today + timedelta(days=i) for i in range(7)]
        elif any(w in low for w, _ in self.WEEKDAY_Q):
            wd = next(n for w, n in self.WEEKDAY_Q if w in low)
            first = today + timedelta(days=(wd - today.weekday()) % 7)
            days = [first] + ([first + timedelta(days=7)] if first == today else [])   # в саму среду «в среду» — и сегодня, и через неделю
        else:
            days = [today] + ([today + timedelta(days=1)] if datetime.now().hour >= 18 else [])
        names = {today: "сегодня", today + timedelta(days=1): "завтра", today + timedelta(days=2): "послезавтра"}
        months, lines = {}, []
        now_hm = datetime.now().strftime("%H:%M")
        try:                                             # память: «в среду в 15:00 встреча» записана с датой «(на 14.10.2026, среда)»
            mem = [x.strip(" -*\t") for x in (self.workspace.memory_text() or "").splitlines() if x.strip()]
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
                lines.append(f"{head} {tm} {kind}: {x.get('title', '')}" + (f", {x['place']}" if x.get("place") else "")
                             + (" — уже прошло" if past else "") + (", повторяется" if x.get("repeat") else ""))
        log.info("📅 Вопрос о планах — даю модели дела и календарь (%d стр.)", len(lines))
        return ("\n\nПЛАНЫ ПОЛЬЗОВАТЕЛЯ (напоминания, дела по расписанию и встречи календаря — уже получены, это свежие данные): "
                "отвечай по ним сразу, без вызова инструментов и без «сейчас посмотрю». Записанное в твоей памяти — тоже планы, называй их. "
                "Сначала то, что впереди, по времени; "
                "прошедшее — одной фразой или не упоминай; ничего нет — так и скажи. Ничего не выдумывай.\n" + "\n".join(lines))

    def calendar_month(self, year, month):
        """Всё по дням месяца: напоминания (будущие и сработавшие), деньги, заметки, дневник, задачи."""
        import calendar as _cal
        from when import next_time
        first = datetime(year, month, 1)
        last = datetime(year, month, _cal.monthrange(year, month)[1], 23, 59, 59)
        days = {}

        def put(day, item):
            days.setdefault(day, []).append(item)
        for r in self.reminders.items:                          # будущие (с повторами — все случаи в месяце)
            try:
                at = datetime.fromisoformat(r["at"])
            except (KeyError, ValueError):
                continue
            n = 0
            while at <= last and n < 400:                        # предел — чтобы частый повтор не раздул месяц и не зациклил
                if at >= first:
                    put(at.date().isoformat(), {"type": "reminder", "id": r["id"], "time": at.strftime("%H:%M"),
                                                "title": r["text"], "kind": r.get("kind") or "reminder",
                                                "repeat": bool(r.get("repeat")), "paused": bool(r.get("paused"))})
                if not r.get("repeat"):
                    break
                at = next_time(r["repeat"], at)
                n += 1
        for h in self._reminder_log():                          # что уже звенело
            d = h.get("at", "")[:10]
            if first.date().isoformat() <= d <= last.date().isoformat():
                put(d, {"type": "reminder", "time": h["at"][11:16], "title": h.get("text", ""), "done": True,
                        "kind": h.get("kind") or "reminder"})
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
                "currency": self._default_currency()}

    def _reminder_log(self):
        """Журнал сработавших напоминаний (reminders-log.json, последние 2000): [{at, text, kind, id}]."""
        try:
            return json.loads((STATE_DIR / "reminders-log.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _log_reminder(self, item):
        log_ = self._reminder_log()[-1999:]
        log_.append({"at": datetime.now().isoformat(timespec="seconds"), "text": item.get("text", ""),
                     "kind": item.get("kind") or "reminder", "id": item.get("id")})
        try:
            p = STATE_DIR / "reminders-log.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(log_, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
