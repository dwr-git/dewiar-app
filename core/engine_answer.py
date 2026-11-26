"""Движок Dewiar — ответ: ask() (быстрые пути без модели, передача специалисту), ход разговора с моделью
(_run_turn: поток событий модели → фразы → озвучка, вызовы инструментов, запасные пути при ошибках), история
и системная подсказка, «Проверить всё», отчёты разработчику, связь с фоновыми задачами (TaskManager.host).
Часть класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Озвучка фраз — _speak_worker (engine_remote.py), инструменты — _use_tool (engine_tools.py).
Текст с «\\n\\nВложения:» — вопрос с файлами (см. _attach_files): быстрые пути его не перехватывают."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка

from answer_rules import (
    ACTS_RX, APPT_RX, APPT_TIME_RX, ATT_DEFAULT_Q, ATT_PATH_RX, ATT_REF_RX, BIG_PC_RX, CORE_TOOLS, COURSE_RX,
    crash_blocks, _CRASH_RX, DATE_ASK_RX, device_os, DISK_ASK_RX, facts_shown, honest_rest, IDEA_RULE, INFO_TOOLS, told,
    JOB_ASK_RX, LAW_CODE_RX, LAW_REF_RX, law_unsourced, model_label, _MONTH_NOM, _MONTH_RX, month_year_wrong,
    month_years, MORNING_RX, _no_money, _norm_answer, _plural, POEM_READ_RX, poem_unsourced, PRIVACY_ASK_RX,
    PROFILE_COUNTERS, profile_delta, _put_context, REF_RX, _rep_norm, repeat_head, ack_again, REPEAT_RX, shown_q, SONGS_ASK_RX,
    SPEED_RX, TALER_RX, TASK_ASK_RX, TASK_GIVE_RX, team_window, think_ask, _thumb, turn_hints, VISION_HINT, hist_calls)  # noqa: F401 — прежние имена на месте
from answer_prompt import PromptMixin, prompt_parts, spec_names
from xray import current as xray_current, turned as xray_turned
from answer_models import ModelsMixin
from answer_report import ReportMixin
from answer_direct import DirectMixin, LookMixin



# ход-итог: дело по расписанию «итог / подведи / сводка / что сделано» или такая просьба человека
HABIT_TURN_RX = re.compile(r"\[Дело по расписанию\][^«]*«[^»]*(?:итог|подвед|сводк|что сделано)|^\W*(?:[а-яё]+,\s*)?(?:итог(?:и)? (?:дня|недели)|"
                           r"подвед[её]?\w* итог|что я (?:сегодня|за день) сделал)", re.I)

class AnswerMixin(PromptMixin, ModelsMixin, ReportMixin, DirectMixin, LookMixin):
    # ---------- ответ ----------
    CODER_RX = re.compile(r"coder|codellama|codegemma|starcoder|codestral|devstral|sqlcoder|code-?llama|wizardcoder", re.I)

    def ask(self, text, images=None, quiet=False, via=None, raw=False, shown=None, report=None):
        """Вопрос → ответ (_ask) под «Рентгеном» (core/xray.py): путь хода, подсказка, действия, проверки — по ходу целиком.
        Вопрос, ушедший модели, рентген закрывает ход (_run_turn); быструю команду — здесь."""
        import xray
        if not str(text or "").strip() and not images:
            return self._ask(text, images, quiet, via, raw, shown, report)
        xr = xray.begin(str(text or "").strip() or "Что на этой картинке?", via=via, quiet=quiet, raw=raw,
                        typed=time.monotonic() - getattr(self, "_typed_t", 0.0) < 2)
        try:
            return self._ask(text, images, quiet, via, raw, shown, report)
        finally:
            if xr is not None and (xr.get("route") or {}).get("kind") != "model":
                xray.finish(xr)                        # быстрая команда (или ничего) — ход кончился здесь
            else:
                xray.attach(None)                      # ушло модели — дальше пишет поток хода, а этот поток свободен

    def _ask(self, text, images=None, quiet=False, via=None, raw=False, shown=None, report=None):
        """Вопрос → ответ. Сначала быстрые пути без модели (будильник, «спрячься»/«отключись», команды компьютера, сейф, умный дом, деньги,
        дела, заметки, напоминания, «замолчи», новый разговор, позвать персонажа, радио, музыка), затем, возможно,
        передача специалисту (_route) и ход разговора в потоке turn-N; прежний ход отменяется.
        images — картинки; quiet — служебный вопрос: не показываем «услышал», без быстрых путей; via — вопрос
        не голосом (Telegram/MAX, см. Turn.via); raw — без быстрых путей и передачи специалисту (дела по расписанию);
        shown — что показать вместо текста; report(ok, text) — чем кончился ход (дела по расписанию: повтор при сбое)."""
        text = text.strip()
        if not text and images:
            text = "Что на этой картинке?"
        if not text:
            return
        if via:
            quiet = False
        if not quiet and not raw and hasattr(type(self), "first_asked"):
            type(self).first_asked(self, text)             # первый вопрос новичка — подсказки в виджете больше не нужны
        # 24.10 (владелец: «попросил обновиться — нет; „а теперь“ — она что-то не связанное»): короткое «а теперь?»,
        # «ещё раз», «проверь ещё раз» сразу после быстрой команды без модели — та же команда ещё раз
        lq = getattr(self, "_last_quick", None)
        if not raw and not quiet and not images and lq and time.monotonic() - lq[1] < 600 and REPEAT_RX.match(text):
            log.info("🔁 «%s» — повторяю «%s»", text, lq[0])
            text = lq[0]
        if not raw and not quiet and not images and self.alarm and not via and self._alarm_voice(text):
            return
        # Детский режим (kids.py): время и «спать» — до всего; вопрос — в отчёт родителю; вне правил — ещё и сигнал.
        # K — режим включён: опасные быстрые пути (компьютер, сейф, деньги, платежи, дом, звонки, YouTube, выход,
        # обновление, передача другому персонажу) не работают — отвечает модель по детским правилам.
        kids = getattr(self, "kids", None)
        K = bool(kids and kids.on() and not raw and not quiet)
        if K:
            ok_k, why_k = kids.allowed_now()
            if not ok_k:
                self._say_quick(why_k, text, via)
                return
            if kids.touch(text.split("\n\nВложения:")[0]):
                self._kids_alert(text)
            self.emit("kids", **self.kids_public(light=True))   # виджет: сколько минут осталось
        sen = getattr(self, "senior", None)              # «Для старших» (senior.py): говорила сегодня; мошенники — сразу «стоп»
        if sen is not None and not K and not raw and not quiet and sen.on():
            body_s = text.split("\n\nВложения:")[0]
            sen.touch()
            if not images and sen.scam(body_s):
                self._senior_scam(body_s, text, via)
                return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and self._bug_cmd(text, via):
            return                                       # «сообщи об ошибке: …» — жалоба разработчику (core/health.py)
        if not raw and not quiet and not via and not images and not K and re.match(
                r"^(?:\w+,\s*)?(?:включи|запусти|открой|начни|позови)\s+(?:режим\s+)?суфл[её]р\w*|^(?:\w+,\s*)?режим\s+суфл[её]ра", text.strip(), re.I):
            self.emit("prompter", kind="open")             # суфлёр — окно ui/prompter.html (core/prompter.py)
            self._say_quick("Открываю суфлёр. На встрече я молчу и подсказываю на экране.", text)
            return
        if not raw and not quiet and not via and not images and not K and self._rest_voice(text):
            return                                       # «Лира, отдохни час» — не слушает и не говорит (engine_rest.py, №540)
        if not raw and not quiet and not via and not images and getattr(self, "resting", lambda: False)():
            self.rest_end("вопрос")                      # написали сами во время отдыха — вернулась
        if not raw and not quiet and not via and not images and self._game_voice(text):
            return                                       # «Морской бой» открыт: «бэ пять» — ход в игре (engine_commands)
        if not raw and not quiet and not via and not images and not K and self._window_cmd(text):
            return
        if not raw and not quiet and not images and not K and getattr(self, "course", None) is not None:
            try:                                         # курс «Неделя с Лирой»: сказали фразу урока — шаг засчитан
                self.course.heard(text)
            except Exception:  # noqa: BLE001
                log.debug("курс", exc_info=True)
            if not via and COURSE_RX.match(text.lower().strip(" .!?")) and self._course_say(text):
                return
        if not raw and not quiet and not via and not images and not K and self._pc_cmd(text):
            return
        if not raw and not quiet and not images and not K and self._speed_cmd(text, via):
            return
        if not raw and not quiet and not images and not K and DISK_ASK_RX.match((text or "").strip()):
            import shutil
            try:
                du = shutil.disk_usage(str(Path.home()))
                free, total = du.free / 1e9, du.total / 1e9
                msg = (f"На диске свободно {free:.0f} ГБ из {total:.0f}." + (" Маловато — могу помочь найти, что занимает место."
                                                                            if free < max(10, total * 0.08) else ""))
                log.info("💽 «%s» → %s", text, msg)
                self._say_quick(msg, text, via)
                return
            except Exception:  # noqa: BLE001
                log.debug("диск: быстрый ответ не вышел", exc_info=True)
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._vault_cmd(text, via):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._home_cmd(text, via):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and self._weather_cmd(text, via):
            return                                       # «какая погода?» — настоящие числа сразу (weatherq.py, №373)
        if not raw and not quiet and not images and not K and MORNING_RX.match(text) and hasattr(self, "_job_prompt"):
            log.info("🌅 «%s» — утренняя сводка по данным «Утра»", text)
            self.ask(self._job_prompt({"brief": True}), via=via, raw=True, shown=text)
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._pay_voice(text, via):
            return                                       # «оплатил газ 47,84, показания 28135», «что не оплачено?» — «Платежи»
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._money_cmd(text, via):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._job_cmd(text, via):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text:
            from quickmath import parse as parse_math      # «сколько будет 17% от 2350» — точно и сразу (tools.calc_eval)
            qm = parse_math(text)
            if qm:
                self._say_quick(qm["say"], text, via, note=qm.get("how"))
                return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._draft_cmd(text, via):
            return                                       # «запиши в книгу: …» — дословно в черновик автора
        if not raw and not quiet and not images and not K and self._mail_table_cmd(text, via):
            return                                       # №541: «Excel по почте» — таблица сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text:
            ma = APPT_RX.match(text.strip())
            if ma and APPT_TIME_RX.search(ma.group("rest")):
                from when import parse as parse_when
                r = parse_when("напомни " + ma.group("rest"))
                if r and r.get("text") and not r.get("repeat"):
                    r["said"] = text
                    self._set_reminder_fast(r, via)        # дело в «Делах» со временем (как «напомни …»)
                    return
        if not raw and not quiet and not images and "\n\nВложения:" not in text:
            from capture import parse as parse_capture
            c = parse_capture(text)
            if c and self._capture(c, text, via):
                return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and self._clock_cmd(text, via):
            return                                       # «сколько времени?», «какое сегодня число?» — по часам, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._open_link_cmd(text, via):
            return                                       # «открой в браузере» сразу после ответа с одной ссылкой — её и открываем
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._youtube_cmd(text, via):
            return                                       # «включи смешное видео на YouTube» — сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._send_cmd(text, via):
            return                                       # «напиши Андрею: привет» — человеку из «Близких» сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._call_cmd(text, via):
            return                                       # «позвони Людмиле по видео» — человеку из «Близких» сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._plan_cmd(text, via):
            return                                       # «запланируй на сегодня: в 13 …, в 16 …» — дела дня, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._task_del_cmd(text, via):
            return                                       # «удали задачу „Исследование“» — сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._mark_cmd(text, via):
            return                                       # «я позвонил в банк», «готово, купил хлеб» — отметка, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and self._timer_cmd(text, via):
            return                                       # «сколько осталось?», «добавь минуту», «отмени таймер»
        if not raw and not quiet and not images:
            from when import parse as parse_when
            r = parse_when(text)
            if r and REF_RX.match(r.get("text") or ""):
                # «напомни об этом / о ней / о последней заметке завтра в 10» (отчёт №66: вышло напоминание «Об этом»):
                # только что записанная заметка — она; иначе — модели, она видит разговор
                note = self._fresh_note()
                r = dict(r, text=note) if note else None
            if r:
                r["said"] = text
                self._set_reminder_fast(r, via)
                return
        if not raw and not quiet and not via and not images and thanks_phrase(text):
            self._thanks(text)
            return
        if not raw and not quiet and not via and not images and is_sleep_phrase(text):
            self.emit("heard", text=text)
            self.go_sleep(text)
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text:
            from conversation import is_new_conversation
            if is_new_conversation(text):
                self.new_conversation()
                self._say_quick("Хорошо, начинаем с чистого листа.", text, via)
                return
        if not raw and not quiet and not via and not images and not K and self._direct_call(text):
            return
        if not raw and not quiet and not images and not K and self._direct_update(text, via):
            return
        if not raw and not quiet and not images and not K and self._direct_look(text, via):
            return
        if not raw and not quiet and not via and not images and self.radio.paused and \
                re.sub(r"[^\w ]", "", text.lower()).strip() in {"продолжи", "продолжай", "включи обратно", "верни радио",
                                                                "включи радио", "играй", "продолжи радио"}:
            st = self.radio.resume()
            self.emit("heard", text=text)
            self.emit("answer", text=f"Снова играет «{st['name']}».", done=True)
            self.set_state("idle")
            return
        if not raw and not quiet and not via and not images and (not K or "music" in (kids.conf().get("allow") or [])) and self._music_cmd(text):
            return
        with self._turn_lock:
            self._cancel_locked()      # прежний ход — до выбора специалиста: перебитый специалист возвращает слово главному, и вопрос распределяет уже он
        handoff = None if quiet or images or raw or K else self._route(text)
        if handoff:
            prev = self.s.get("persona")
            log.info("👥 %s передаёт вопрос: %s", self.personas.get(prev)["name"], self.personas.get(handoff)["name"])
            self.switch_persona(handoff)
        log.info("❓ %s", redact(text))
        if not quiet and not (via or {}).get("job"):   # дело по расписанию — показываем, только когда есть что сказать
            self.emit("heard", text=shown or (("✉ " + text.split("\n\nВложения:")[0]) if via else text))
        if handoff:
            self.emit("handoff", **{"from": prev, "to": handoff, "name": self.personas.get(handoff)["name"],
                                    "role": self.personas.get(handoff).get("role", "")})
        with self._turn_lock:
            self._cancel_locked()
            self.turn_n += 1
            turn = Turn(self.turn_n)
            turn.xr = xray_current()                  # рентген хода — и в поток turn-N
            xray_turned(turn.xr)
            turn.via = via
            # набрали текстом (виджет, «Чат» студии) — после ответа не слушаем фон: человек пишет, а голоса рядом —
            # не ему (владелец 20.11: после набранного вопроса Лира ответила на разговор в комнате)
            turn.typed = time.monotonic() - getattr(self, "_typed_t", 0.0) < 2
            self._typed_t = 0.0
            turn.via_job = bool((via or {}).get("job"))  # дело по расписанию: в окна — только итог (_run_job решает, говорить ли)
            turn.asked = text                         # о чём просили (save_note без просьбы записать — не пишем)
            rp = getattr(self, "_chat_replay", 0)      # «Ещё раз»/«Изменить» в «Чате» — повтор, а не новое «да» (_just_agreed)
            turn.replay = bool(rp and time.monotonic() - rp < 60)
            self._chat_replay = 0
            turn.report = report
            turn.back_to = prev if handoff and self.s.get("team", "back") is not False else None
            turn.persona = self.s.get("persona")      # кто отвечает; по нему _cancel_locked решает, возвращать ли слово главному
            turn.raw = raw                            # служебное поручение (приветствие, дело по расписанию) — не вопрос человека
            # итог («Итог дня» по расписанию, «подведи итоги») — без привычек В САМИХ ДАННЫХ (владелец 17.11, в четвёртый раз:
            # «Сегодня сделано: обед с картой (отмечено)» — «Обед — не забудь взять карту» каждый будний день; просьба «не
            # называй» в поручении не помогала: календарь отдавал модели «сделано: Обед…»). Календарь и список напоминаний
            # в этот ход отдают всё, кроме привычек; назвала всё же — переделать (quality.habit_said)
            turn.no_habits = bool(HABIT_TURN_RX.search(text.split("»", 1)[0] if raw else text.split("\n\n", 1)[0]))
            turn.habit = None
            if turn.no_habits and hasattr(self, "_habit_pred"):
                try:
                    turn.habit = self._habit_pred(weekly=bool(re.search(r"(?<![а-яё])недел", text.split("»", 1)[0], re.I)))
                except Exception:  # noqa: BLE001
                    log.debug("привычки", exc_info=True)
            turn.greet = bool(raw and str(shown or "").startswith("👋"))   # приветствие «С возвращением»: опоздало — не нужно
            self.turn = turn
        threading.Thread(target=self._run_turn, args=(turn, text, images or []), name=f"turn-{turn.n}", daemon=True).start()


    # ---------- для фоновых задач (TaskManager.host) ----------

    def _mail_on(self):
        """Почта подключена? Не узнать (нет почты в сборке, сбой) — считаем, что да: проверка «с почтой не работаю» молчит."""
        try:
            m = getattr(self, "mail", None)
            return True if m is None else bool(m.configured())
        except Exception:  # noqa: BLE001
            return True

    def confirm(self, question, timeout=120, cancel=None, always=False, quiet=False):
        """Спросить «да/нет» вне разговора (для фоновой задачи): голосом и кнопками в виджете.
        Блокирует вызывающий поток до ответа, timeout секунд или cancel (Event задачи: «останови задачу» не ждёт
        двух минут, №54) -> True при «да», False при «нет», None — никто не ответил или задачу остановили; «always» —
        кнопка «Всегда» (always=True: «для этой задачи больше не спрашивать»).
        16.11 (Кодер: «каждую секунду просил подтверждения вслух одной и той же фразой; жмёшь — всё равно договаривает»):
        quiet — только на экране, без голоса; ответили кнопкой — недосказанный вопрос замолкает сразу."""
        for _ in range(240):                                   # один вопрос за раз: ждём до 2 мин, пока ответят на прежний
            if self.pending_confirm is None or (cancel is not None and cancel.is_set()):
                break
            time.sleep(0.5)
        if cancel is not None and cancel.is_set():
            return None
        box = {"event": threading.Event(), "answer": False, "always": False}
        self.pending_confirm = box
        self.emit("confirm", text=question, always=bool(always), always_title="Для этой задачи больше не спрашивать")
        if quiet:
            self.play_tone("wake") if hasattr(self, "play_tone") else None
        else:
            say = _spoken_question(question) + " Скажите «да» или «нет»" + (" — или «всегда», и в этой задаче больше не спрошу." if always else ".")
            try:
                self.announce(say, tag="confirm")
            except TypeError:                              # announce без пометки (облачный исполнитель, заглушки)
                self.announce(say)
        end = time.monotonic() + timeout
        while not box["event"].wait(min(0.5, max(0.0, end - time.monotonic()))):
            if time.monotonic() >= end or (cancel is not None and cancel.is_set()):
                break
        answered = box["event"].is_set()
        if self.pending_confirm is box:
            self.pending_confirm = None
        self.emit("confirm_done", ok=box["answer"])
        if answered and getattr(self, "_turn_lock", None) is not None:   # ответили кнопкой посреди вопроса — не договаривать
            with self._turn_lock:
                t = self.turn
                if t is not None and getattr(t, "tag", "") == "confirm":
                    t.cancel.set()
                    if getattr(self, "player", None):
                        self.player.stop()
        log.info("Подтверждение (задача): %s", (("всегда" if box.get("always") else "да") if box["answer"] else "нет") if answered else "без ответа")
        if not answered:
            return None
        return "always" if box["answer"] and box.get("always") and always else box["answer"]

    def ask_user(self, task, question):
        """Задача спрашивает: говорим вопрос; следующая фраза пользователя без имени в течение 2 минут — ответ
        (см. handle_text в engine_audio.py)."""
        self.task_answer_until = time.monotonic() + 120
        self.tg_task_until = time.monotonic() + 6 * 3600     # из Telegram ответить можно и позже (вопрос пришёл туда)
        self.announce(f"Вопрос по задаче «{task.title}»: {question}")

    def find_persona(self, name):
        """«Лиру», «Патрика», «эва» → id персонажа или None. Сравниваем имя, слова вызова, другие написания и id
        без последней буквы (грубо отбрасываем падежное окончание); точное совпадение важнее."""
        return self._match_persona(name, self.personas.all())

    @staticmethod
    def _match_persona(name, items):
        q = re.sub(r"[^\wё]", "", (name or "").lower().replace("ё", "е"))
        if not q:
            return None
        best = None
        for p in items:
            names = {p["name"].lower().replace("ё", "е")} | {w.lower().replace("ё", "е") for w in (p.get("wake") or [])} \
                | {w.lower() for w in (p.get("aliases") or [])} | {p["id"].lower()}
            for n in names:
                n = re.sub(r"[^\wё]", "", n)
                if not n:
                    continue
                if q == n:
                    return p["id"]
                stem = n[:-1] if len(n) > 3 else n
                if (q.startswith(stem) or n.startswith(q[:-1] if len(q) > 3 else q)
                        or (len(q) >= 3 and len(n) >= 3 and q[:-1] == n[:-1])):
                    best = best or p["id"]
        return best


    WAIT_NOTE_SEC = 20          # модель молчит дольше — в виджете строка, чего ждём и что можно сделать (№446)
    GREET_LATE_SEC = 60         # приветствие «С возвращением» без единого слова дольше — уже не к месту: молчим

    def _turn_prepare(self, turn, text, images, prof):
        """Ход разговора, шаг «подготовить запрос» (из _run_turn, чистое ядро 1.0.12): модель (облако, пробная, думать ли,
        экономный режим), действия к вопросу и их режим, системная подсказка, справка к ходу (подсказки к просьбе, память,
        знания персонажа, картинки), окно контекста. Ошибка (нет модели) — LLMError, как и раньше.
        -> (prof, msgs, specs, system, ask0, ctx, econ_main, pmsg, slim_text)."""
        try:
            if not prof and (self.account.logged_in() or self.s.get("cloud", "key")):
                try:                                   # модели нет, а вход dewiar.pro (или ключ) есть — подключаем модели Dewiar сами
                    self._cloud_use()
                    prof = self.persona_llm()
                except Exception as e:  # noqa: BLE001
                    log.info("🧠 Модели Dewiar сами не подключились: %s", e)
            if not prof:                               # 29.10 (пакет: 28% компьютеров так и не подключили мозг и молчат)
                threading.Thread(target=self.auto_join, args=("вопрос без мозга",), daemon=True).start()   # подключится — дальше полный
                prof = self._trial_llm()               # а этот ответ — сразу, пробным разговором сайта, без настройки
            if not prof:
                raise LLMError("я пока не подключён к языковой модели — откройте настройки, раздел «Мозг»"
                               + (": войдите в аккаунт dewiar.pro — модели Dewiar подключатся сами" if not self.account.logged_in() else ""))
            msgs = self._messages(text, images, prof)
            if prof.get("cloud") and prof.get("net") and not images and not self._net_closed() and self._net_rules_ok():
                prof = dict(prof, _net_turn=True)       # «Сеть Лиры»: заголовок — только к основному ходу разговора (llm._headers)
            if prof.get("cloud") and not images and not getattr(turn, "typed", False) and not getattr(turn, "raw", False) and not getattr(turn, "via", None):
                # сказано голосом (владелец 20.11, скорость голоса): облако отдаёт простой вопрос лёгкому мозгу целиком —
                # первое слово ~0,5 с вместо ~7 с у главного; сложное и поручения решает сайт (lite_simple) — как раньше
                prof = dict(prof, _voice=True)
            from llm import wants_think
            if prof.get("think") not in ("on", "off") and self.s.get("llm", "think_auto") is not False and wants_think(think_ask(text, getattr(turn, "raw", False))):
                # сложная просьба — модель думает (дольше, но стих с рифмой, а расчёт со смыслом); лимит — с запасом на размышления
                prof = dict(prof, think="on", max_tokens=max(6144, int(prof.get("max_tokens") or 0)))
                turn.think_auto = True
                log.info("🧠 Сложная просьба — модель подумает перед ответом")
            econ_main = None                            # экономный режим (economy.py): простое — дешёвой модели, основная — запасом
            try:
                import economy
                cheap = economy.model_for(prof, text, self.history, bool(images), think=prof.get("think") == "on")
            except Exception:  # noqa: BLE001
                cheap = ""
            if cheap:
                econ_main = prof
                prof = dict(prof, model=cheap)
                self.health_count("econ")
                log.info("💸 Простой вопрос — отвечает недорогая модель «%s»", cheap)
            from llm import creative_temp, prof_temp
            ask0 = text.split("\n\nВложения:")[0]
            temp = creative_temp(ask0, prof.get("temperature"))
            if temp != prof_temp(prof):
                prof = dict(prof, temperature=temp)       # творческая просьба — смелее (отзыв 17.10 про креатив)
                log.info("🎨 Творческая просьба — температура %.2f", temp)
            # харнесс, шаг 1 (15.11): к вопросу — ядро действий и только нужные модули (Toolbox.specs(text)); прочее модель
            # попросит сама (more_tools) — вопрос легче вдвое: окно своей модели, свой ключ, очередь облака
            slim_text = ask_core(text) + "\n" + "\n".join(
                str(m.get("content") or "")[:300] for m in self.history[-4:] if m.get("role") == "user" and isinstance(m.get("content"), str))
            specs = self.toolbox.specs(slim_text) if self.s.get("tools", "enabled_all") is not False else []
            if specs and getattr(turn, "via_job", False) and "[Дело по расписанию]" in text:
                from engine_music import SUMMARY_JOB_RX
                if SUMMARY_JOB_RX.search(text.split("»", 1)[0]):
                    # владелец 11.11, 21:00: «Итог дня» — «Дела: итог», «Деньги: отчёт», а потом навык «Проверка договора»
                    # (contract-check) — и ни слова итога. Итогу навыки плагинов не нужны
                    specs = [x for x in specs if x.get("name") != "use_skill"]
            if getattr(turn, "greet", False):
                # «С возвращением» — по готовым фактам, без инструментов (владелец 20.11: вечером позвала done_report — и в итог
                # попали «обед с картой», «серия» и «всего 65 дел»; поручение «без инструментов» модель не держала)
                specs = []
            turn.lean = False
            # переключатель — llm.talk_lean (стенд: llm.talk_lean=false — как раньше)
            tl_ = self.s.get("llm", "talk_lean")
            # не задан (None) — включён: у обновившихся с 1.0.59 в настройках сохранилось прежнее «null», и оно перебивало новое
            # «включено для всех» (отчёт №959, 22.11); выключает только явное False
            if specs and tl_ is not False and not getattr(turn, "via_job", False) and not getattr(turn, "raw", False) \
                    and not images:
                # «Чистый разговор» (владелец 21.11: «через Лиру — как у 4B»): просто беседа — характер, разговор и главное, без
                # правил действий и почти без самих действий; понадобилось дело — модель попросит (more_tools, core/talk_lean.py)
                import modules as _mods
                import talk_lean
                # просьба к плагину (№507: «Когда ближайшее полнолуние?» — плагин «Луна») — дело, не беседа
                if talk_lean.talk_turn(ask_core(text), self.history, _mods.wanted(ask_core(text))) and not self._plugin_hint(text):
                    specs, turn.lean = talk_lean.lean_specs(specs), True
                    log.info("🍃 Просто разговор — подсказка без правил действий (%d действия)", len(specs))
            mode = (self.s.get("llm", "tools_modes") or {}).get(self._tools_key(prof))
            if mode in ("native", "prompt"):
                prof = dict(prof, tools_mode=mode)
            elif mode is None and specs:
                self.probe_tools_bg()                  # ещё не проверяли — проверим в фоне, этот ответ — в режиме по умолчанию
            # «Голос без пауз» (04.11): подсказка — общая для всех и неизменная; личное (имя, память, душа, дела сегодня) —
            # справкой в начале разговора, подсказки к роду просьбы (стихи, советы, схема, грубость) — в справке к вопросу.
            # Иначе каждая такая добавка ломала кэш начала запроса и для всех инструментов после подсказки (tools/prefix_audit.py)
            pmsg = self._profile_in_msgs(prof)
            full_ = bool(specs) and not turn.lean       # «Чистый разговор» — подсказка как без действий, плюс короткое правило
            self._rule_names = spec_names(specs)        # Опыт 2 (llm.rules_with_tools): правила — только к действиям этого хода
            system = self._system(full_, personal=not pmsg, talk=turn.lean)
            if turn.lean:
                import talk_lean
                system += talk_lean.LEAN_RULE
            # «Чистый разговор»: справка о человеке — как при деле (с папкой и прочим): снимок на начало разговора, а разговор
            # часто начинается с «привет» — иначе и дела потом шли бы без папки (полный прогон 22.11, prefix_cache1104)
            personal = self._personal(full_ or turn.lean).strip() if pmsg else ""
            pdelta = ""
            if personal:                               # 0.87: справка в начале разговора — снимок, изменения — к вопросу
                personal, pdelta = self._profile_snap(personal, msgs)
            notes = []                                 # подсказки к этой просьбе — в справку к вопросу
            import boundaries
            from llm import POEM_ASK, POEM_NOTE, READ_NOTE, RECO_ASK, RECO_NOTE, reading
            if reading(text.split("\n\nВложения:")[0]):
                notes.append(READ_NOTE)                 # прочитать готовое — точный текст целиком (№668)
            elif POEM_ASK.search(text.split("\n\nВложения:")[0]):
                notes.append(POEM_NOTE)                 # стихи — рифмы по ударению подбираются заранее
            elif RECO_ASK.search(text.split("\n\nВложения:")[0]):
                notes.append(RECO_NOTE)                 # советы фильмов и песен — только существующее
            if boundaries.rude(text):                  # грубят самому помощнику — спокойная граница в этом ходе, счётчик в пульс
                notes.append(boundaries.NOTE)
                self.health_count("rude")
                log.info("🛡 грубость в адрес помощника — отвечу спокойно, с границей")
            recalled = ""
            try:
                if not self._kb_persona_quiet(text):     # отзыв 19.11: у «знатока книги» заметки человека не подмешиваем
                    recalled = self.recall.context(text.split("\n\nВложения:")[0])
            except Exception as e:  # noqa: BLE001
                log.info("Поиск по записям: %s", e)
            ctx = [self._turn_context(text)] + ([pdelta] if pdelta else []) + [n.strip() for n in notes]   # меняющееся — в справку к вопросу, подсказка остаётся прежней
            turn.read = read_mode(text, getattr(turn, "typed", False))
            if turn.read:
                ctx.append(READ_HINT)                  # длинный разбор — для чтения: подзаголовки, жирное, списки
                log.info("📖 Ответ для чтения с экрана — вслух только суть")
            mlines, mpages = self.memory_for(text.split("\n\nВложения:")[0])
            if mlines:                                 # Память 2.0: старое о человеке не теряется — приходит к вопросу
                log.info("🧠 Из памяти к вопросу: %s", ", ".join(mpages))
                ctx.append("Из памяти о пользователе (подобрано к этому вопросу из «Обо мне» — используй, если к месту, "
                           "не пересказывай всё):\n" + mlines)
            try:                                         # «Пульт Лиры» (16.11): что подняла к вопросу — светится в окне заметок
                self.emit("recall", q=shown_q(text), notes=re.findall(r"^\[([^\]]+)\]", recalled or "", re.M)[:6], memory=list(mpages or [])[:4])
            except Exception:  # noqa: BLE001
                pass
            if recalled:
                log.info("📎 Вспомнил из записей: %s", ", ".join(re.findall(r"^\[([^\]]+)\]", recalled, re.M)))
                ctx.append("Из записей пользователя в твоей папке (нашлось по словам вопроса). Если это отвечает на "
                           "вопрос — ответь по ним и коротко скажи, откуда («в заметке …»). Если не относится — не "
                           "упоминай:\n" + recalled)
            try:
                ag = self.agenda_context(text)             # «что у нас по плану» — дела и календарь сразу перед моделью
                if ag.strip():
                    ctx.append(ag.strip())
                cr = self.care_context(text, turn)         # «Заботливая память»: прошло важное — спросить, как прошло
                if cr:
                    ctx.append(cr)
                ask0, hints, hint_sys = turn_hints(text, specs)
                ctx += hints
                system += hint_sys
                turn.agenda = ag
            except Exception as e:  # noqa: BLE001
                log.info("План на день: %s", e)
            if turn.via and not turn.via_job:
                src = turn.via.get("from") or "Telegram"
                ctx.append(f"Сейчас пользователь пишет тебе из {src} (не голосом): ответ уйдёт ему сообщением. Можно "
                           "чуть подробнее и со списками; файлы из папки ассистента — инструментом send_telegram"
                           + (" (to: max)." if src == "MAX" else "."))
            if mode == "none" and specs:
                specs = []
                turn.lean = False
                system = self._system(False, personal=not pmsg) + ("\n\nЭта модель не умеет выполнять действия (музыка, скриншоты, "
                                                "программы). Если просят действие — честно скажи одной фразой, что с этой "
                                                "моделью действия недоступны, и предложи выбрать другую модель в «Мозге».")
            slow_at = (getattr(self, "_tools_slow", None) or {}).get(self._tools_key(prof))
            if specs and slow_at is not None and time.monotonic() - slow_at < 1200:
                # своя модель только что не дождалась ответа с инструментами (180 с) — 20 минут спрашиваем без них, а не
                # ждём те же 180 с на каждом вопросе и потом ещё ответ без них (№133, 20.10: 4 ядра, Ollama, «вечно в думках»)
                specs = []
                turn.lean = False                      # действий нет совсем — и переделка по проверке их не вернёт
                system = self._system(False, personal=not pmsg) + ("\n\nСейчас действия (музыка, скриншоты, программы) недоступны: модель на "
                                                "этом компьютере не успевает с ними. Если просят действие — честно скажи "
                                                "это одной фразой.")
            turn.plugin_hint = self._plugin_hint(text) if specs else ""
            turn.plugin_acts = self._plugin_acts(text) if turn.plugin_hint else ("", [])
            if turn.plugin_hint:                       # №461/463/483: просьба к плагину — сразу его навык и действия
                log.info("🧩 %s", turn.plugin_hint.split(":")[0].split(" — ")[0])
                ctx.append(turn.plugin_hint)
            kb = self._persona_knowledge(text, turn)
            if kb:
                ctx.append(kb.strip())
            if images:
                ctx.append(VISION_HINT)                      # фото: перевод, документ, еда (идеи пользователей 24.10)
            elif len(text) < 400:
                try:
                    import guide
                    # экзамен ПК 0.81.1 (как appGuideFor на телефоне): «как сделать, чтобы сын говорил с тобой безопасно?»,
                    # «есть видеоуроки?», «как добавить маму?» — вопрос о самом приложении: руководство прикладываем сами
                    # (как вызов app_help — и в событиях хода, и для экзамена)
                    gh = guide.attach(text.split("\n\nВложения:")[0], "pc")
                    if gh:
                        turn.guided = True
                        log.info("📖 Вопрос о приложении — руководство приложено к вопросу")
                        self.emit("tool", name="app_help", title="Руководство", status="done", args={"query": text[:200]},
                                  detail="руководство приложено к вопросу", result="руководство приложено к вопросу приложением")
                    else:
                        gh = guide.hint(text, "pc")              # «как защищены мои данные?» — раздел руководства сразу
                        if gh:                                   # экзамен 1.0.5 (help_ubuntu_cmd): ответ по руководству — и
                            turn.guided = True                   # в событиях хода так и видно (как с attach)
                            self.emit("tool", name="app_help", title="Руководство", status="done", args={"query": text[:200]},
                                      detail="раздел руководства приложен к вопросу", result="раздел руководства приложен к вопросу приложением")
                    if gh:
                        ctx.append(gh)
                except Exception:  # noqa: BLE001
                    pass
            msgs = _put_context(msgs, "\n\n".join(c for c in ctx if c))
            if personal:
                from llm import put_profile
                msgs = put_profile(msgs, personal)
            system, specs, msgs = self._fit_window(prof, system, specs, msgs, keep=self._plugin_keep(text), personal=not pmsg)
            self._pparts = prompt_parts(system, specs, msgs, personal if personal else "", "\n\n".join(c for c in ctx if c))
            try:
                import xray
                from llm import context_window
                xray.prompt(system, specs, msgs, parts=self._pparts, prof=prof, ctx_window=context_window(prof),
                            extra={"ctx": [c.split("\n", 1)[0][:120] for c in ctx if c], "lean": bool(getattr(turn, "lean", False))})
            except Exception:  # noqa: BLE001
                log.debug("рентген", exc_info=True)
        except LLMError as e:
            e.turn_prof = prof                         # сбой при подготовке — какой моделью шёл ход
            raise
        return prof, msgs, specs, system, ask0, ctx, econ_main, pmsg, slim_text

    def _act_cue_arm(self, turn, name, sentences):
        """Первое действие хода — через ACT_CUE_S проверить, не тишина ли до сих пор (act_cue.py)."""
        if getattr(turn, "_cue_armed", False):
            return
        turn._cue_armed = True
        from act_cue import ACT_CUE_S
        t = threading.Timer(ACT_CUE_S, self._act_cue_fire, args=(turn, name, sentences))
        t.daemon = True
        t.start()

    def _act_cue_fire(self, turn, name, sentences):
        """Действие идёт, а Лира ещё ничего не сказала: одна короткая фраза о том, что она делает. Молчим, если ход
        кончился или отменён, модель уже начала отвечать, вопрос не голосом (мессенджер, дело по расписанию) или
        «Отвечать текстом»."""
        from act_cue import cue_text
        phrase = cue_text(name)
        if (not phrase or turn.cancel.is_set() or getattr(turn, "ended", False) or self.turn is not turn
                or turn.full.strip() or turn.spoken or turn.via or getattr(turn, "via_job", False)
                or getattr(turn, "_cue_said", False) or self.s.get("tts", "text_only")):
            return
        turn._cue_said = True
        phrase = self._g(phrase) if hasattr(self, "_g") else phrase      # программа по-английски — по-английски
        self.__dict__.setdefault("_cue_set", set()).add(phrase)          # синтез запомнит (engine_remote._synth_mixed)
        log.info("🗣 «%s» идёт дольше %.1f с — говорю «%s»", name, time.monotonic() - turn.t0, phrase)
        sentences.put(phrase)

    def _turn_steps(self, turn, text, images, sentences, prof, msgs, specs, system, ask0, ctx, econ_main, pmsg, slim_text):
        """Ход разговора, середина (из _run_turn, чистое ядро 1.0.13): фразы в озвучку (что придержать до проверки), до 6
        шагов «модель → действия → результаты», запасные модели, проверки «сказала, но не сделала» и итог ответа.
        -> prof (модель могла смениться: экономный режим, запасная). LLMError уходит наверх с e.turn_prof — какой моделью
        шёл ход в момент сбоя (_run_turn сообщает о сбое по ней)."""
        try:
            split, last, codef = SentenceSplitter(), 0.0, CodeFilter()
            # вслух — не больше ~900 символов (около минуты): длинный ответ дальше только на экране («Открыть целиком»);
            # сказки, истории и чтение вслух — целиком
            # №377: «хотелось бы прослушивать всё до конца» — студия → «Голос» → «Читать длинные ответы вслух целиком»
            voice_cap = 10 ** 9 if (self.s.get("tts", "read_all") or re.search(r"сказк|истори|расскаж|прочитай|прочти|читай|стих|подробно|целиком|полностью|до конца", text.lower())) else 900
            if getattr(turn, "read", False) and not self.s.get("tts", "read_all"):
                voice_cap = READ_VOICE                  # ответ для чтения — вслух только суть
            spoken = [0, False]                         # сколько символов отдано в озвучку; предел уже достигнут

            from gender import for_persona
            gnd = self.persona_gender()
            fem = lambda t: for_persona(t, gnd)        # noqa: E731 — героиня, а модель сбилась на «рад», «понял»: правим сами

            def speak(s_):
                s_ = fem(s_)
                if spoken[1]:
                    return
                if spoken[0] + len(s_) > voice_cap and spoken[0] > 0:
                    spoken[1] = True
                    if getattr(turn, "read", False):
                        sentences.put(self._g("Подробно — на экране, так удобнее читать.") if hasattr(self, "_g") else "Подробно — на экране, так удобнее читать.")
                        self.emit("read_open")             # виджет открывает «Ответ целиком»
                    else:
                        sentences.put("Дальше не читаю вслух — всё на экране." + ("" if getattr(self, "_cap_said", False) else " Читать целиком — студия, «Голос»."))
                    self._cap_said = True
                    log.info("🔇 Ответ длинный — вслух прочитано %d симв., остальное на экране", spoken[0])
                    return
                spoken[0] += len(s_)
                if getattr(self, "lat", None) is not None:
                    self.lat.mark("say")
                sentences.put(s_)
            blind_key = f"{prof.get('base_url')}|{prof.get('model')}"
            t_start = time.monotonic()
            if getattr(self, "lat", None) is not None:
                self.lat.mark("req", t_start)
            from quality import DELIVERABLE, FAKE_NUDGE, REFUSAL_NUDGE, REMIND_NOT_SET, WATCH_ASK_RX, WATCH_NUDGE, action_claim, call_claim, mail_claim, found_pics_claim, fake_call, bare_done, diagram_missing, reminder_missing, remind_claim, saved_claim, note_claim, money_claim, looks_like_promise, looks_like_refusal, number_mismatch, promise_nudge, task_claim
            called, nudged = set(), 0                    # какие действия уже были; сколько раз просили «сделай, а не обещай»
            deliver = bool(DELIVERABLE.search(text)) and any(x.get("name") == "start_task" for x in specs or [])
            # отговорку «нет доступа к интернету» на шаге 0 (когда есть поиск) просим переделать (ниже) — значит, первую
            # фразу с отговоркой и всё после неё в озвучку не отдаём, пока шаг не кончится: иначе отказ прозвучит, а потом
            # его заменит ответ по поиску. Обычная первая фраза идёт в голос сразу — задержки для неё нет
            held, hold = [], [False]
            # Экзамен ПК 0.81.1: проверки «сказала, но не сделала» срабатывают после шага, а ответ к тому времени уже прозвучал
            # и остался в тексте («Сейчас открою. Готово, Википедия открыта…», «в Минске около +4»). Рецензия 0.82 («Голос без
            # пауз»): придерживаем не весь ответ, а только пока проверка не прошла — с фразы, на которой она сработает
            # (quality.hold_sentence: «открыла» без открытия, выдуманные градусы, дело не из планов, «записала» без money_add),
            # или весь шаг, если нужный инструмент ещё не вызывался (quality.hold_step: ссылка, «сколько написал», совет).
            # После вызова нужного инструмента фразы идут сразу; стихи и вопросы о приложении не придерживаются — проверка после.
            from quality import COUNCIL_ASK as _CA, hold_sentence as _hold_s, hold_step as _hold_step, failed_claim as _failed_c, habit_said as _habit_s
            names0 = {x.get("name") for x in specs or []}
            known0 = text + "\n" + "\n".join(c for c in ctx if c)
            strict, gate = [False], [True]           # gate: на последнем шаге (только слова) проверок нет — не придерживаем

            def say(s_):
                if gate[0] and not strict[0] and not turn.cancel.is_set():
                    try:
                        strict[0] = _hold_s(ask0, text, s_, called, names0, known0, getattr(turn, "agenda", "")) \
                            or bool(getattr(turn, "tools_err", None) and _failed_c(s_, turn.tools_err, getattr(turn, "tools_ok", None) or [])) \
                            or bool(getattr(turn, "no_habits", False) and _habit_s(s_, getattr(turn, "habit", None)))   # итог: привычка — не вслух
                    except Exception:  # noqa: BLE001
                        strict[0] = False
                if strict[0] or (hold[0] and (held or looks_like_refusal(s_))):
                    held.append(s_)
                    return
                hold[0] = False
                speak(s_)

            def retract(drop=False):
                """Проверка попросила переделать шаг: придержанное не звучит и уходит из текста ответа. drop — неверный шаг
                уходит из текста, даже если часть его уже прозвучала (ответ дадут заново)."""
                if (strict[0] and held) or drop:
                    held.clear()
                    if step_text and turn.full.endswith(step_text):
                        turn.full = turn.full[:-len(step_text)]
            seen_calls = {}                              # одинаковый вызов в одном ходе — не повторяем (результат уже есть)
            done_calls, checked = [], False                  # что вызвано с результатами — сверить числа ответа (number_mismatch)
            import ledger as _ledger
            # Опыт 4 (аудит Fable 25.11, llm.gate_only): при «Каркасе хода» — одни ворота по журналу вместо каскада проверок
            # «сказала сделано без действия» (*_claim) и их честных замен после хода: журнал сверяет ответ один раз, в конце
            gate_only = self.s.get("llm", "gate_only") is True and _ledger.on(self.s.get("llm", "ledger"), prof)
            turn.done_calls = done_calls                     # и в историю — родным форматом (Опыт 1, llm.history_native)
            drew = 0                                         # просили схему, а её нет — попросили нарисовать (до двух раз за ход)
            saved_checked = False                            # «записала» без единого действия — попросили записать (раз за ход)
            style_saved = False                              # №651: просьба о том, как говорить, — правило записано программой (раз за ход)
            import quality as Q
            failed_checked = False                           # №573: действие с ошибкой выдано за сделанное — переспросили (раз за ход)
            remind_asked = False                             # пообещала напомнить без set_reminder — попросили поставить (раз за ход)
            repeat_checked = False                           # ответ слово в слово как недавний — попросили ответить по существу (раз за ход)
            place_checked = False                            # №510: в запросе поиска нет места из вопроса — попросили искать заново (раз за ход)
            plug_checked = False                             # №507: ответила фактами по памяти, не вызвав подходящий плагин (раз за ход)
            deed_checked = False                             # экзамен ПК 0.81.1: «открыла» без open_url, погода без weather… (раз за ход)
            prev_said = {_norm_answer(m.get("content")) for m in self.history[-8:] if m.get("role") == "assistant" and m.get("content")}
            prev_asked = {_norm_answer(m.get("content")) for m in self.history[-9:-1] if m.get("role") == "user" and isinstance(m.get("content"), str)}
            for step in range(6):                       # модель → действия → результаты → модель…
                calls, step_text = [], ""
                t_step, t_ev = time.monotonic(), None     # «⏱ модель: …» — от запроса до первого события этого шага
                if step and getattr(turn, "lean", False) and msgs and msgs[-1].get("role") == "user":
                    # «Чистый разговор», а проверка ответа попросила переделать (вызвать плагин, действие, поиск…) — переделывать
                    # уже с полной подсказкой и всеми действиями: налегке их нет (полный прогон 22.11: «полнолуние» — плагин «Луна»)
                    turn.lean = False
                    specs = self.toolbox.specs(slim_text, keep=set(getattr(turn, "packs", None) or ()))
                    self._rule_names = spec_names(specs)
                    system = self._system(True, personal=not pmsg)
                    log.info("🧰 Проверка просит переделать — дальше с полной подсказкой и действиями")
                if step == 5 and specs:                  # последний шаг — только слова: ответить тем, что уже узнал
                    can_task = any(x.get("name") == "start_task" for x in specs) and "start_task" not in called
                    specs = []
                    system += ("\n\nДействий больше не будет: прямо сейчас ответь пользователю словами по тому, что уже "
                               "узнал и сделал. Не пиши «готово» без сути.")
                    if can_task:                          # HARNESS 7: большая просьба не влезла в разговор — предложить задачу
                        system += (" Если просьба сделана не до конца — так и скажи, что успел, и предложи одной фразой "
                                   "довести её большой задачей в фоне («Сделать это задачей? Доведу до конца и сообщу»).")
                hold[0] = step == 0 and any(x.get("name") == "web_search" for x in specs or [])
                gate[0] = step < 5 and bool(specs) and not deed_checked
                strict[0] = gate[0] and _hold_step(ask0, called, names0)    # весь шаг — только пока нужный инструмент не вызван
                if blind_key in self._blind and _has_images(msgs):
                    msgs = _drop_images(msgs)
                if step and econ_main is not None:       # после действий продолжает основная модель
                    prof = dict(econ_main, temperature=prof.get("temperature"), think=prof.get("think")) if prof.get("temperature") is not None else econ_main
                    econ_main = None
                try:
                    # с картинкой ответ сначала собираем целиком: если модель её не примет — повторим без неё;
                    # без картинки ждём только первое событие — ошибка сервера всплывёт здесь, до первого слова
                    # Опыт 9 (llm.force_call): после просьбы «сделай, а не обещай» этот шаг — только действием (tool_choice)
                    sprof = dict(prof, _force_call=True) if getattr(turn, "force_call", False) and specs else prof
                    turn.force_call = False
                    try:
                        events = list(stream_events(sprof, system, msgs, cancel=turn.cancel, tools=specs or None)) \
                            if _has_images(msgs) else _first_then_stream(
                                stream_events(sprof, system, msgs, cancel=turn.cancel, tools=specs or None))
                    except LLMError as e0:
                        if econ_main is None or step or turn.full or turn.cancel.is_set():
                            raise
                        log.warning("💸 Недорогая модель «%s» не ответила (%s) — отвечает основная", prof.get("model"), e0)
                        prof = dict(econ_main, temperature=prof.get("temperature")) if prof.get("temperature") is not None else econ_main
                        econ_main = None
                        events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None))
                except LLMError as e:
                    # №805 (пакет 17.11): действия уже сделаны (ответ MCP-программы, поиск), а модель вернула пустоту — не
                    # «Не получилось: ответ без текста» и не молчание, а ниже, после цикла: «ответь словами по сделанному»
                    quiet = bool(step and done_calls and "без текста" in str(e) and not turn.cancel.is_set() and not turn.full.strip()
                                 and getattr(turn, "blank_nudged", False))
                    fb = self._cloud_fallback(prof, e) if step == 0 and not turn.full and not turn.cancel.is_set() else None
                    if not fb and step == 0 and not turn.full and not turn.cancel.is_set():
                        fb = self._own_fallback(prof, e)    # своя модель выключена — мозг Dewiar (если человек согласился)
                    if quiet:
                        log.warning("Модель замолчала после действий (%s) — попрошу ответить по сделанному", e)
                        events = iter(())
                    elif fb:                                # облако не ответило / заряд кончился — отвечает запасной мозг
                        prof = fb
                        events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None))
                    elif not _has_images(msgs):
                        if "без текста" in str(e) and specs and not turn.cancel.is_set() and not getattr(turn, "blank_nudged", False):
                            # пустой ответ — сбой, а не «модель не умеет действия»: ещё раз с инструментами и подсказкой
                            turn.blank_nudged = True
                            log.warning("Модель ответила пустотой (%s) — повторяю с подсказкой", e)
                            msgs = msgs + [{"role": "user", "content": "Ответь на мой вопрос: вызови нужный инструмент или ответь словами."}]
                            try:
                                events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None))
                            except LLMError as e3:
                                if not (step and done_calls and "без текста" in str(e3)):
                                    raise
                                log.warning("Модель замолчала после действий (%s) — попрошу ответить по сделанному", e3)
                                events = iter(())
                        elif specs and step == 0 and not turn.full and not turn.cancel.is_set() and not self._cloud_said(prof, e) \
                                and "без текста" not in str(e) and not _no_money(e):     # деньги на ключе кончились — без действий не поможет
                            # с инструментами модель не отвечает — ответим хотя бы без них
                            log.warning("Модель не справилась с инструментами (%s) — отвечаю без действий", e)
                            from health import brain_kind, why_kind
                            if why_kind(e) == "timeout" and brain_kind(prof) in ("local", "server"):
                                slow_key = self._tools_key(prof)
                                if not hasattr(self, "_tools_slow"):
                                    self._tools_slow = {}
                                self._tools_slow[slow_key] = time.monotonic()
                                self.note("Модель на этом компьютере не успевает отвечать с действиями — 20 минут отвечаю без "
                                          "них, так быстрее. Действия (музыка, программы, напоминания) — с моделью полегче "
                                          "или облаком Dewiar (студия → «Мозг»).")
                            from llm import CTX_TEXT, _ctx_cut, ctx_full
                            if ctx_full(e) or CTX_TEXT in str(e):  # окно контекста мало (LM Studio 4096): короче и без функций
                                msgs = _ctx_cut(msgs)
                                if not getattr(self, "_ctx_noted", False):
                                    self._ctx_noted = True
                                    self.note("У модели маленькое окно контекста — отвечаю без действий и почти без памяти "
                                              "разговора. В LM Studio или Ollama поставьте длину контекста 16384 или больше: "
                                              "с действиями нужно около 12–16 тыс.")
                            specs = []
                            turn.no_tools = "ctx" if (ctx_full(e) or CTX_TEXT in str(e)) else "tools"   # №944 — для честного итога
                            # №760 (15.11, своя qwen3-4b, окно мало): без действий модель называла курс евро «по памяти»
                            # и выдумывала, что взяла его с cbr.ru. Без инструментов свежих данных нет — так и сказать
                            system = self._system(False, personal=not pmsg) + ("\n\nСейчас действия (поиск в интернете, открыть "
                                                            "ссылку, музыка, программы) недоступны. Свежие данные — курсы валют, "
                                                            "цены, погоду, новости, что написано по ссылке — ты сейчас проверить "
                                                            "НЕ можешь: не называй таких цифр и не говори, что где-то их посмотрела. "
                                                            "Если просят действие или свежие данные — честно скажи одной фразой, что "
                                                            "сейчас не можешь это проверить.")
                            try:
                                events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=None))
                            except LLMError as e2:
                                if not (ctx_full(e2) or CTX_TEXT in str(e2)):
                                    raise
                                # и без действий не влезло (окно 2048–4096, а память и душа длинные) — самое короткое:
                                # кто ты и вопрос; лучше простой ответ, чем «модели не хватило окна» на каждый вопрос
                                log.warning("Окно модели мало и без действий — отвечаю с самой короткой подсказкой")
                                system, msgs = self._system_min(), drop_profile(msgs[-1:])
                                events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=None))
                        else:
                            raise
                    else:
                        log.info("Модель %s не приняла картинку (%s) — отвечаю без неё", prof.get("model"), e)
                        from health import why_kind
                        if why_kind(e) != "timeout":         # не дождались — не значит «не видит» (№885: сервер был медленным)
                            self._blind.add(blind_key)
                        msgs = _drop_images(msgs)
                        events = stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None)
                # №435 (31.10, на телефоне и так же здесь): итог сказан до действия и повторён после — начало следующего
                # шага придерживаем, пока не ясно, не повтор ли это сказанного (repeat_head); повтор не говорим и не пишем
                probe, probing, muted = "", bool(step and _rep_norm(turn.full)), False
                ack_seen = not probing
                for kind, val in events:
                    if t_ev is None:
                        t_ev = time.monotonic()
                        if getattr(self, "lat", None) is not None:
                            self.lat.mark("ev", t_ev)          # сервер ответил хоть чем-то (первый шаг хода)
                            # 21.11: где теряются секунды между «сайт: первое слово за 1,2 с» и «у людей — 5,6 с»: заголовки
                            # ответа и первая строка потока (сеть и посредники) отдельно от первого события (модель)
                            from llm_hints import wait_info
                            wi = wait_info(turn.cancel) or {}
                            for k_ in ("t_conn", "t_tls", "t_sent", "t_hdr", "t_line"):   # 1.0.70: и дорога по шагам
                                if wi.get(k_):
                                    self.lat.mark(k_[2:], wi[k_])
                    if turn.cancel.is_set():
                        break
                    if kind == "tools":
                        calls = val
                        if calls and getattr(self, "lat", None) is not None:
                            self.lat.act()
                        continue
                    if muted:
                        step_text += val
                        continue
                    if probing:
                        probe += val
                        if not ack_seen:                # второе «Записала.» после действия — срезать, остальное сказать
                            cut = ack_again(turn.full, probe)
                            if cut is None:
                                continue
                            ack_seen = True
                            if cut:
                                log.info("🔁 Второе подтверждение после действия — не повторяю: %s", probe[:cut].strip())
                                probe = probe[cut:]
                                if not probe:
                                    continue
                        rep = repeat_head(turn.full, probe)
                        if rep is None:
                            continue
                        probing = False
                        if rep:
                            muted = True
                            step_text += probe
                            log.info("🔁 Повтор сказанного после действия — не повторяю")
                            continue
                        val, probe = probe, ""
                    if not turn.full:
                        turn.t_first = time.monotonic() - t_start      # «Подробности» ответа: до первого слова
                        log.info("⏱ первые слова модели через %.1f с", time.monotonic() - t_start)
                        if getattr(self, "lat", None) is not None:
                            self.lat.mark("tok")
                        self._slow_local(prof, time.monotonic() - t_start)
                        self._coder_brain(prof)
                    turn.full += val
                    step_text += val
                    if time.monotonic() - last > 0.08 and not turn.via_job:     # текст в виджет — не чаще ~12 раз в секунду
                        self.emit("answer", text=fem(turn.full), done=False, model=True)
                        last = time.monotonic()
                    for s_ in split.feed(codef.feed(val)):         # код и команды вслух не читаем
                        say(s_)
                self._usage_note(prof, (t_ev or time.monotonic()) - t_step, turn)
                from llm import last_served, served_label
                sv_ = served_label(last_served())
                if sv_ and sv_ not in turn.__dict__.setdefault("brains", []):
                    turn.brains.append(sv_)                  # кто ответил на этом шаге на самом деле (облако Dewiar)
                    log.info("🧠 Ответил %s", sv_)
                    xr_m = (xray_current() or {}).get("model")
                    if isinstance(xr_m, dict):
                        xr_m["served"] = " → ".join(turn.brains)
                        xr_m["srv"] = re.sub(r"[^a-z0-9]", "", str((last_served() or {}).get("srv") or ""))[:8]   # для замера по мозгам
                if probing and probe and not ack_seen and ack_again(turn.full, probe, fin=True):
                    probe = probe[ack_again(turn.full, probe, fin=True):]       # «Записала.» и всё — уже сказано
                if probing and probe and not repeat_head(turn.full, probe, fin=True):   # короткий новый хвост — не терять
                    turn.full += probe
                    step_text += probe
                    for s_ in split.feed(codef.feed(probe)):
                        say(s_)
                for s_ in split.feed(codef.flush()) + split.flush():
                    say(s_)
                if not calls and step == 0 and not turn.cancel.is_set() and any(x.get("name") == "web_search" for x in specs or []):
                    if looks_like_refusal(step_text):      # «нет доступа к интернету», а поиск есть — просим поискать (только на шаге 0)
                        watch = WATCH_ASK_RX.search(turn.asked or "") and any(x.get("name") == "schedule_job" for x in specs or [])
                        log.info("✋ Модель отказалась («нет доступа»), не попробовав %s", "дело по расписанию — прошу завести"
                                 if watch else "поиск — прошу поискать")
                        held.clear()                           # отговорка так и не прозвучала
                        self.day_miss("refusal", turn.asked or text, step_text)
                        sentences.put("Секунду — настрою." if watch else "Секунду — посмотрю в интернете.")
                        msgs = msgs + [{"role": "assistant", "content": step_text}, {"role": "user", "content": WATCH_NUDGE if watch else REFUSAL_NUDGE}]
                        turn.full = ""
                        self.set_state("thinking")
                        continue
                if not strict[0]:
                    for s_ in held:                           # не отказ (длинный ответ с оговоркой или вызвала инструменты) — озвучить
                        speak(s_)
                    held.clear()
                called |= {c.get("name") for c in calls}
                from llm import last_net
                if last_net():
                    turn.net = True                     # ответ этого шага дал узел «Сети Лиры» — пометка в истории
                if not calls and not turn.cancel.is_set() and specs and step < 5:
                    # «сейчас посмотрю и расскажу» — и ни одного действия; или просили презентацию, а задача не запущена
                    want_task = deliver and "start_task" not in called and not step_text.strip().endswith("?") and nudged < 2
                    # №461 (ПК 0.76): «сейчас посмотрю» — просьба — и снова «сейчас посмотрю», и ход кончился: просим дважды,
                    # второй раз жёстче и с действиями плагина; не взялась и тогда — честно говорим это (ниже, PROMISE_GIVEUP)
                    faked = "" if want_task else fake_call(step_text, names0)       # №522: «[run_command: …] Жду вывод»
                    promised = not want_task and (bool(faked) or looks_like_promise(step_text, text))
                    if (faked or promised) and last_net() and not getattr(turn, "net_redo", False):
                        # рецензия 04.11, третья: ответ узла сети — не FAKE_NUDGE главному мозгу с текстом узла, а тот же
                        # вопрос главному мозгу заново, без текста узла и без заголовка сети
                        log.warning("🌐 Ответ узла Сети Лиры похож на вызов текстом или обещание — спрашиваю главный мозг заново")
                        turn.net_redo, turn.net = True, False
                        retract(drop=True)
                        prof = dict(prof, _net_turn=False)
                        self.set_state("thinking")
                        continue
                    if want_task or (nudged < 2 and promised):
                        nudged += 1
                        if nudged == 1:
                            self.day_miss("task" if want_task else "fake_call" if faked else "promise", turn.asked or text, step_text)
                        log.info("✋ Модель %s — прошу сделать, а не обещать%s", "не запустила задачу" if want_task else
                                 f"написала вызов «{faked}» текстом" if faked else "только пообещала", " (ещё раз)" if nudged > 1 else "")
                        retract(drop=bool(faked))                    # текст с выдуманным вызовом — не в ответ
                        turn.force_call = self.s.get("llm", "force_call") is True
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"},
                                       {"role": "user", "content": FAKE_NUDGE if faked else promise_nudge(want_task, again=nudged > 1,
                                                                                 hint=getattr(turn, "plugin_hint", ""))}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                    fix = "" if checked else number_mismatch(step_text, done_calls)
                    if fix:                                 # «таймер на 79 минут», а поставлено 59 (экзамен 14.10)
                        checked = True
                        log.info("✋ Число в ответе не совпадает с поставленным — прошу исправить")
                        retract()
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not turn.cancel.is_set() and step < 5 and specs and not remind_asked and not getattr(turn, "greet", False):
                    fix = remind_claim(step_text, called, self._reminder_times())   # приветствие — не просьба: не проверяем
                    if fix:                                  # «напомню тебе в понедельник в 9» — а напоминания нет (19.10)
                        remind_asked = True
                        log.info("✋ Пообещала напомнить, а напоминание не поставлено — прошу поставить")
                        retract()
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not turn.cancel.is_set() and not style_saved and "remember" not in called:
                    style_saved = True
                    rule = Q.style_rule(text)
                    if rule:                                 # №651: «убери вопросы в конце» — правило пишет программа, не модель
                        try:
                            Q.add_style_rule(self.workspace.root / Q.TALK_LESSONS_FILE, rule)
                            called.add("remember")             # «записала» теперь правда: проверки «сделала без действия» молчат
                            log.info("💬 Правило, как говорить, — записала сама: «%s»", rule[:80])
                        except Exception:  # noqa: BLE001
                            log.debug("правило общения", exc_info=True)
                if not calls and not turn.cancel.is_set() and step < 5 and specs and not saved_checked and not gate_only:
                    fix = reminder_missing(text, turn.full, called) or money_claim(text, step_text, called) \
                        or saved_claim(text, step_text, called) \
                        or (note_claim(text, step_text, called) if "save_note" in {x.get("name") for x in specs or []} else "") \
                        or call_claim(text, step_text, called) \
                        or mail_claim(text, step_text, self._mail_on(), called) \
                        or found_pics_claim(text, step_text, called) \
                        or action_claim(text, step_text, called) or bare_done(text, step_text, called) \
                        or (task_claim(step_text, called) if any(x.get("name") == "start_task" for x in specs or []) else "")
                    if fix:
                        saved_checked = True
                        log.info("✋ Сказала «готово/записала» или не поставила просимое напоминание — прошу сделать")
                        retract()
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not turn.cancel.is_set() and step < 6 and specs and not failed_checked and getattr(turn, "tools_err", None) \
                        and not gate_only:
                    from quality import failed_claim
                    fix = failed_claim(step_text, turn.tools_err, getattr(turn, "tools_ok", None) or [])
                    if fix:                                  # №573: «нет такого пути», а ответ — «открыла папку»
                        failed_checked = True
                        log.info("✋ Действие вернуло ошибку, а ответ говорит «сделано» — прошу сделать правильно или сказать честно")
                        retract(drop=True)                   # неправда в итог не идёт
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not turn.cancel.is_set() and step < 6 and specs and not plug_checked:
                    from quality import plugin_skipped
                    pn, pa = getattr(turn, "plugin_acts", None) or ("", [])
                    fix = plugin_skipped(step_text, called, pa, pn, getattr(turn, "plugin_hint", ""))
                    if fix:                                  # №507: «полнолуние 5 ноября» по памяти, а плагин «Луна» есть
                        plug_checked = True
                        log.info("✋ Ответила по памяти, не вызвав плагин «%s», — прошу вызвать", pn)
                        retract()
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if step_text and turn.full.endswith(step_text):     # неверный ответ по памяти в итог не идёт
                            turn.full = turn.full[:-len(step_text)]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not called and not turn.cancel.is_set() and step < 6 and not repeat_checked \
                        and 0 < len(turn.full.strip()) and _norm_answer(turn.full) in prev_said \
                        and (len(turn.full.strip()) < 160 or _norm_answer(ask0) in prev_asked):
                    # экзамен 0.84.1: «расскажи о себе» дважды — длинный ответ слово в слово; длинный повтор ловим, когда и
                    # вопрос повторён (человек спрашивает снова — прошлый ответ его не устроил)
                    # отзыв 17.10 (съёмка): на «расскажи о себе», «подробнее», «что ты умеешь» Лира раз за разом отвечала
                    # «Я Лира.» — модель копировала свои прошлые реплики из разговора. Повтор — просим ответить по существу
                    repeat_checked = True
                    log.info("✋ Ответ слово в слово как недавний («%s») — прошу ответить по существу", turn.full.strip()[:40])
                    fix = (f"Ты слово в слово повторил(а) свой прошлый ответ «{turn.full.strip()[:80]}». Человек спрашивает снова — "
                           "значит, тот ответ его не устроил. Ответь сейчас по существу на его последний вопрос, развёрнуто и "
                           "живо, своими словами; прошлый ответ не повторяй.")
                    retract()
                    msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                    if turn.full.strip() and not turn.full.endswith(" "):
                        turn.full += " "
                    self.set_state("thinking")
                    continue
                if not calls and "show_page" not in called and not turn.cancel.is_set():
                    from quality import page_html_in
                    doc = page_html_in(step_text)
                    if doc and len(doc) > 200:                # страницу написали в ответе — откроем её сами, вслух не читаем
                        try:
                            m_ = re.search(r"<title>(.*?)</title>|<h1[^>]*>(.*?)</h1>", doc, re.S | re.I)
                            ttl = re.sub(r"<[^>]+>", "", (m_.group(1) or m_.group(2)) if m_ else "").strip()[:60] or "Страница"
                            self.toolbox.run("show_page", {"title": ttl, "html": doc})
                            called.add("show_page")
                            log.info("🌐 HTML в ответе — сохранила страницей «%s» и открыла", ttl)
                            note = f" Страница «{ttl}» открыта в браузере."
                            turn.full += note
                        except Exception as e:  # noqa: BLE001
                            log.info("Страница из ответа не открылась: %s", e)
                if not calls and not turn.cancel.is_set() and step < 6 and drew < 2:
                    fix = diagram_missing(text, turn.full + step_text, called)
                    if fix and drew:                 # экзамен 17.10: и после просьбы — «Схема готова.»; второй раз — жёстче
                        fix = ("Схемы в ответе по-прежнему нет. Ответь сейчас ТОЛЬКО блоком ```mermaid\nflowchart LR\n…\n``` — "
                               "без слов до и после.")
                    if fix:
                        drew += 1
                        log.info("✋ Просили схему, а её нет — прошу нарисовать (mermaid)")
                        retract()
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not turn.cancel.is_set() and step < 5 and specs and not deed_checked:
                    from quality import agenda_invented, council_missing, feature_deny, invented_numbers, open_claim, poem_check, \
                        songs_count, url_unread, writing_missing, agenda_missed, weather_invented, system_invented, plugin_offer_missed, habit_said
                    names_ = {x.get("name") for x in specs or []}
                    fix = (open_claim(ask0, step_text, called) if "open_url" in names_ else "") \
                        or (url_unread(ask0, step_text, called) if "read_webpage" in names_ else "") \
                        or (invented_numbers(text, step_text, called, known=text + "\n" + "\n".join(c for c in ctx if c))
                            if names_ & {"weather", "web_search"} else "") \
                        or (writing_missing(ask0, step_text, called) if "writing_today" in names_ else "") \
                        or (system_invented(ask0, step_text, called) if "system_status" in names_ else "") \
                        or (council_missing(ask0, step_text, called) if "council" in names_ else "") \
                        or feature_deny(ask0, step_text, called, getattr(turn, "guided", False)) \
                        or agenda_invented(step_text, getattr(turn, "agenda", "")) \
                        or agenda_missed(text, step_text, getattr(turn, "agenda", "")) \
                        or weather_invented(text, step_text, called) \
                        or poem_check(ask0, step_text) \
                        or (habit_said(step_text, getattr(turn, "habit", None)) if getattr(turn, "no_habits", False) else "") \
                        or plugin_offer_missed(getattr(turn, "plugin_hint", ""), step_text, called) \
                        or songs_count(ask0, step_text) \
                        or month_year_wrong(ask0, step_text) \
                        or (poem_unsourced(ask0, step_text, called) if "web_search" in names_ else "") \
                        or (law_unsourced(ask0, step_text, called) if "web_search" in names_ else "")
                    if fix:                                  # экзамен ПК 0.81.1: сказала, но не сделала; числа без инструмента
                        deed_checked = True
                        log.info("✋ %s — прошу переделать", fix.split(" — ")[0].split(":", 1)[-1].strip()[:90])
                        retract(drop=True)                   # ответ дадут заново — неверный в тексте не остаётся
                        # 13.11, итог недели: «Извини, я ошиблась — 17:50 … это я подтянула» — человек прошлого ответа не видел
                        fix += (" Прошлый ответ человек не видел: не извиняйся и не говори об ошибке или проверке — просто дай "
                                "верный ответ.")
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                for s_ in held:                               # придержанное (strict) — проверки прошли: теперь вслух
                    speak(s_)
                held.clear()
                if turn.cancel.is_set() or not calls:
                    break
                results = []
                for c in calls:
                    if c.get("name") == "call_persona" and _CA.search(ask0) and any(x.get("name") == "council" for x in specs or []):
                        log.info("✋ «Собери совет» — call_persona вместо council: прошу council")
                        results.append("Не передано: это просьба собрать совет — вызови council (question — вопрос человека "
                                       "целиком), а не call_persona.")
                        continue
                    if c.get("name") == "web_search" and not place_checked:
                        from quality import search_place_fix
                        fix = search_place_fix(text.split("\n\nВложения:")[0], (c.get("args") or {}).get("query"))
                        if fix:                              # №510: спросили про Прагу — искала «Протвин гостиница»
                            place_checked = True
                            log.info("✋ В запросе поиска нет места из вопроса — прошу искать заново")
                            results.append(fix)
                            continue
                    key = json.dumps([c.get("name"), c.get("args")], ensure_ascii=False, sort_keys=True)
                    if key in seen_calls:
                        log.info("↺ %s с теми же параметрами уже был в этом ходе — не повторяю", c.get("name"))
                        results.append("Этот вызов с теми же параметрами уже был — его результат выше. Не повторяй: "
                                       "используй его или попробуй иначе, а если сведений хватает — отвечай.")
                        continue
                    self._act_cue_arm(turn, c.get("name"), sentences)
                    r_ = self._use_tool(turn, c, sentences)
                    seen_calls[key] = True
                    results.append(r_)
                    done_calls.append({"name": c.get("name"), "args": c.get("args") or {}, "result": __import__("outside_guard").plain(r_)[:300]})
                if turn.cancel.is_set():
                    break
                more = [str(g) for c, r in zip(calls, results) if c.get("name") == "more_tools" and str(r).startswith("Добавлены")
                        for g in (c.get("args") or {}).get("packs") or []]
                if more and getattr(turn, "lean", False):   # из беседы — к делу: полная подсказка и нужные действия
                    turn.lean = False
                    turn.packs = set(getattr(turn, "packs", None) or ()) | (set(more) - {"core"})
                    specs = self.toolbox.specs(slim_text, keep=turn.packs)
                    self._rule_names = spec_names(specs)
                    system = self._system(True, personal=not pmsg)
                    log.info("🧰 Из разговора — к делу: полная подсказка и действия (%s)", ", ".join(sorted(more)))
                elif more and specs:                    # модель попросила группу действий — следующий шаг уже с ними
                    turn.packs = set(getattr(turn, "packs", None) or ()) | set(more)
                    specs = self.toolbox.specs(slim_text, keep=turn.packs)
                    if self.s.get("llm", "rules_with_tools") is True:   # Опыт 2: пришла группа — с ней её правила (на месте прежних)
                        old_r = self._tool_rules()
                        self._rule_names = spec_names(specs)
                        new_r = self._tool_rules()
                        if new_r != old_r and old_r in system:
                            system = system.replace(old_r, new_r, 1)
                    log.info("🧰 Модель попросила действия: %s", ", ".join(sorted(turn.packs)))
                if any(c.get("name") == "start_task" and not str(r).startswith(("Ошибка", "Инструмент")) for c, r in zip(calls, results)):
                    specs = []                          # задача запущена — делает она; в разговоре только сказать, что взялся
                    log.info("🧵 Задача запущена — в разговоре дальше без действий")
                msgs = msgs + tool_turn_messages(prof, step_text, calls, results)
                if turn.full.strip() and not turn.full.endswith(" "):
                    turn.full += " "
                self.set_state("thinking")
            ok_tools = set(getattr(turn, "tools_ok", None) or [])
            if not turn.cancel.is_set() and not turn.full.strip() and done_calls and (not ok_tools or told(ok_tools)):
                # отчёт №69: прочитала страницу трижды, поискала — и вернула пустоту («Не получилось: пустой ответ»).
                # Сведения уже есть — просим ответить по ним словами, без новых действий (один раз).
                # №524 (04.11, разобрал сам человек): справочное ВМЕСТЕ с действием (calc + world_time, web_search +
                # set_reminder) не попадало ни сюда (было: только справочные), ни в «Готово.» (только действия) — и выходило
                # «модель вернула пустой ответ». Теперь — сюда: есть что сказать по найденному и сделанному
                log.warning("Модель замолчала после поиска и чтения — прошу ответить по найденному")
                ask_ = [{"role": "user", "content": "Ответь мне сейчас словами по тому, что уже нашлось и сделано выше (страницы, поиск, действия). "
                                                    "Новых действий не будет. Чего-то не хватило — так и скажи и предложи, "
                                                    "что сделать дальше (например, какие разделы сайта открыть)."}]
                try:
                    for kind, val in stream_events(prof, system, msgs + ask_, cancel=turn.cancel, tools=None):
                        if kind == "tools" or turn.cancel.is_set():
                            continue
                        turn.full += val
                        for s_ in split.feed(codef.feed(val)):
                            speak(s_)
                    for s_ in split.feed(codef.flush()) + split.flush():
                        speak(s_)
                except LLMError as e:
                    log.info("И по найденному ответа нет: %s", e)
                if not turn.full.strip() and not turn.cancel.is_set() and ok_tools - told(ok_tools):
                    # и так ничего, но действие сделано (№524) — как у одних действий: «Готово.» / «Задача запущена…»
                    turn.full = "Задача запущена — сообщу, когда будет готово." if "start_task" in ok_tools else "Готово."
                    sentences.put(turn.full)
                if not turn.full.strip() and not turn.cancel.is_set():
                    # и так ничего — не «Не получилось: пустой ответ», а честно: что сделано и что дальше
                    seen = [c["args"].get("url") or c["args"].get("query") for c in done_calls if c["name"] in ("read_webpage", "web_search")]
                    turn.full = ("Я прочитал " + ("страницу " + str(seen[0]) if seen and str(seen[0]).startswith("http") else "найденное")
                                 + ", но ответ не сложился. Спросите точнее — например, какой раздел разобрать или что именно собрать.")
                    turn.full = self._g(turn.full) if hasattr(self, "_g") else turn.full
                    sentences.put(turn.full)
            if nudged and not called and not turn.cancel.is_set() and (looks_like_promise(step_text or turn.full, text)
                                                                       or fake_call(step_text or turn.full, names0)):
                # №463 (ПК 0.76): «Лира говорит, что сейчас всё сделает, и больше ничего не происходит. Ни статуса, ни ответа» —
                # просили сделать, а она так и не взялась: человек не должен ждать впустую — говорим прямо
                from quality import FAKE_GIVEUP, PROMISE_GIVEUP
                log.warning("✋ Модель так и не взялась за дело после просьб — говорю об этом прямо")
                faked = fake_call(step_text or turn.full, names0)
                if faked:                                # №522: выдуманный вызов («жду вывод») не показываем; честно — почему не сделано
                    turn.full = turn.full[:-len(step_text)] if step_text and turn.full.endswith(step_text) else \
                        re.sub(r"\[[^\]\n]{0,400}\]", "", turn.full)
                giveup = FAKE_GIVEUP if faked else PROMISE_GIVEUP
                turn.full = turn.full.replace(PROMISE_GIVEUP, "").strip()   # №782: модель переписала прошлый отказ из разговора
                turn.full = (turn.full.rstrip() + " " + giveup).strip()
                sentences.put(giveup)
            if saved_checked and not called and not turn.cancel.is_set() and not nudged \
                    and (action_claim(text, turn.full, called) or saved_claim(text, turn.full, called)):
                # №573: «открой эту папку» — «открыла», проверка попросила сделать, а модель снова «открыла» без действия
                from quality import PROMISE_GIVEUP, self_fact
                fact = self_fact(text, turn.full)
                saved_fact = False
                if fact:                                 # №675/677/678: человек учил — факт в память кладёт программа
                    try:
                        self.workspace.remember(fact)
                        saved_fact = True
                        called.add("remember")
                        log.info("🧠 Модель «запомнила» без памяти — записала сама: «%s»", fact[:80])
                    except Exception:  # noqa: BLE001
                        log.debug("сам факт в память", exc_info=True)
                if saved_fact and not turn.full.strip():
                    note = "Записано в память: «" + (fact if len(fact) <= 160 else fact[:157] + "…") + "»."
                    turn.full = note
                    sentences.put(note)
                elif not saved_fact:
                    log.warning("✋ И после просьбы — «сделала» без единого действия — говорю правду")
                    if step_text and len(turn.full) > len(step_text) and turn.full.endswith(step_text):
                        turn.full = turn.full[:-len(step_text)]   # №651: тот же «записала» второй раз — в тексте не повторяем
                    # №782 (16.11): «Готово, навык обновлён… Простите, до дела так и не дошло» — длинное «готово» без единого
                    # действия оставалось в ответе рядом с отказом. Неправду не храним: из длинного ответа уходят фразы
                    # «сделала / вызываю / обновлён», короткий — заменяется честной фразой
                    rest = honest_rest(text, turn.full) if len(turn.full) >= 300 else ""
                    whole = len(turn.full.replace(PROMISE_GIVEUP, "").strip())
                    # остались полезные сведения (≥ 60 % и 120 знаков) — с ними; почти всё было «сделала» — только честная фраза
                    turn.full = (rest + " " + PROMISE_GIVEUP).strip() if len(rest) >= max(120, 0.6 * whole) else PROMISE_GIVEUP
                    sentences.put(PROMISE_GIVEUP)
            if getattr(turn, "no_tools", "") and not called and not turn.cancel.is_set():
                # №944 (21.11, своя модель, окно контекста мало): действия отключены, а модель переписала из разговора
                # «Включила радио «Groove Salad»» — тишина, человек трижды просил и не понимал почему. Без действий ничего
                # не включено, не поставлено и не отправлено — так и говорим, с причиной и что сделать
                from quality import NO_TOOLS_GIVEUP, no_tools_claim
                if no_tools_claim(text, turn.full):
                    honest = NO_TOOLS_GIVEUP[turn.no_tools]
                    log.warning("✋ Действия недоступны, а ответ говорит «включила / поставила» — говорю правду")
                    turn.full = honest
                    sentences.put(honest)
            if failed_checked and not turn.cancel.is_set():
                from quality import failed_claim, failed_note
                if failed_claim(turn.full, getattr(turn, "tools_err", None), getattr(turn, "tools_ok", None) or []):
                    # №573: и после просьбы — «сделала», а действие с ошибкой: человек должен знать правду
                    note = failed_note(turn.tools_err, getattr(turn, "tools_ok", None) or [])
                    log.warning("Действие с ошибкой так и выдано за сделанное — говорю правду")
                    turn.full = (turn.full.rstrip() + " " + note).strip()
                    sentences.put(note)
            import ledger
            if ledger.on(self.s.get("llm", "ledger"), prof) and not turn.cancel.is_set() and turn.full.strip():
                # «Каркас хода» (план «Качество», шаг 3; отзыв Alex 21.11: «сказала, что сделала, а на самом деле нет»): ответ
                # сверяется с журналом хода — что программа сделала на самом деле (рентген: действия и итог); утверждает
                # сделанное без основания — правдой из журнала. Решает модель коротким вопросом, не словарь фраз (core/ledger.py)
                xr_ = xray_current()
                acts_ = list((xr_ or {}).get("acts") or [])

                def _ask_(sys_, user_):
                    out_ = ""
                    for kind_, val_ in stream_events(prof, sys_, [{"role": "user", "content": user_}], cancel=turn.cancel, tools=None):
                        if kind_ == "text":
                            out_ += val_
                    return out_
                bad_ = ledger.check(text, turn.full, acts_, _ask_)
                if bad_ and not turn.cancel.is_set():
                    fix_ = ledger.honest(bad_, acts_)
                    log.warning("✋ Ответ утверждает сделанное, которого нет в журнале хода (%s) — говорю правду", "; ".join(bad_))
                    turn.full = (turn.full.rstrip() + " " + fix_).strip()
                    sentences.put(fix_)
            if remind_asked and "set_reminder" not in called and not turn.cancel.is_set() and not turn.full.rstrip().endswith("?"):
                # попросили поставить — и всё равно нет: человек должен знать, что напоминания нет (а не ждать утром)
                log.warning("Обещала напомнить, но напоминание так и не поставлено — говорю об этом прямо")
                turn.full = (turn.full.rstrip() + " " + REMIND_NOT_SET).strip()
                sentences.put(REMIND_NOT_SET)
            if not turn.cancel.is_set():
                if not turn.full.strip() and getattr(turn, "tools_ok", None) and not told(turn.tools_ok):
                    # действие сделано, а слов модель не добавила; фоновая задача только началась — не «Готово» (отзыв 13.10)
                    turn.full = "Задача запущена — сообщу, когда будет готово." if "start_task" in turn.tools_ok else "Готово."
                    sentences.put(turn.full)
                if not turn.full.strip():
                    raise LLMError("модель вернула пустой ответ")
                log.info("⏱ ответ целиком за %.1f с (%s, %d симв.)", time.monotonic() - t_start, prof.get("model") or "?",
                         len(turn.full))
                turn.gen_done = True                      # №543: ответ сложился — после ложного перебивания его договорим
                turn.model = model_label(prof)            # №515: какой моделью ответил — в историю (пометка о смене модели)
                early = self._early_done(turn)
                if early:                                 # «Готово!» сразу после start_task — поправиться вслух и в тексте
                    turn.full = turn.full.rstrip() + " " + early
                    sentences.put(early)
                fake = self._fake_reminder(text, turn)
                if fake:
                    turn.full = turn.full.rstrip() + " " + fake
                    self.note(fake)
                turn.full = fem(ACTS_RX.sub("", turn.full)).strip()   # пометку «выполнено инструментами» модель могла повторить
                try:
                    import boundaries
                    if boundaries.refused(turn.full):
                        self.health_count("refused")
                except Exception:  # noqa: BLE001
                    pass
                turn.src_done = self._sources_done(turn, turn.full)
                if not turn.via_job:
                    # «Подробности» под ответом в «Чате» (0.86): модель, время до первого слова и всего, токены (если сервер сказал)
                    meta = {"model": turn.model, "first": getattr(turn, "t_first", None), "total": time.monotonic() - t_start,
                            **(getattr(turn, "tok", None) or {})}
                    if getattr(turn, "brains", None):
                        meta["brain"] = " → ".join(turn.brains)   # владелец 21.11: профиль «DWR Chat» — а ответил кто?
                    self.emit("answer", text=turn.full, done=True, model=True, sources=turn.src_done, meta=meta)
                self.health_count("turns")
                self.health_count("net_ok")
                self._contact_maybe()
                self._maybe_learn(text, prof)
        except LLMError as e:
            e.turn_prof = prof
            raise
        return prof

    def _run_turn(self, turn, text, images=()):
        """Поток turn-N под «Рентгеном»: тот же рентген, что у вопроса; кончился ход (или отменён) — рентген закрыт."""
        import xray
        xray.attach(getattr(turn, "xr", None))
        try:
            return self._run_turn_body(turn, text, images)
        finally:
            xr = getattr(turn, "xr", None)
            if xr is not None:
                if turn.cancel.is_set():
                    xr["cancelled"] = True
                xray.finish(xr)

    def _run_turn_body(self, turn, text, images=()):
        """Поток turn-N: один ход разговора. Фразы ответа идут в очередь sentences — их озвучивает отдельный поток
        (_speak_worker; для сообщений без голоса — _drain_worker), None в очереди — конец. До 6 шагов
        «модель → инструменты → результаты → модель». Запасные пути: облако не ответило — запасной мозг;
        модель не справилась с инструментами — без них; не приняла картинку — без неё (модель запоминается в _blind).
        В конце: ответ в мессенджер (turn.via["done"]), история, «продолжение разговора», возврат к главному
        персонажу после специалиста и передача слова, если её попросил инструмент. Отменённый ход в историю не идёт."""
        prof = self.persona_llm()
        self._turn_text = text                       # read_webpage: длинная страница — куски по словам вопроса
        turn.q, turn.images = text, list(images or ())   # №543: перебило эхо — задать тот же вопрос заново
        sentences = queue.Queue()
        silent = bool(turn.via) and not turn.via.get("speak")
        speaker = threading.Thread(target=self._drain_worker if silent else self._speak_worker, args=(turn, sentences),
                                   daemon=True)
        speaker.start()
        self.set_state("thinking")
        threading.Thread(target=self._wait_watch, args=(turn,), name=f"wait-{turn.n}", daemon=True).start()
        try:
            prof, msgs, specs, system, ask0, ctx, econ_main, pmsg, slim_text = self._turn_prepare(turn, text, images, prof)
            prof = self._turn_steps(turn, text, images, sentences, prof, msgs, specs, system, ask0, ctx, econ_main, pmsg, slim_text)
        except LLMError as e:
            prof = getattr(e, "turn_prof", prof)       # середина хода могла сменить модель
            log.warning("Модель: %s", e)
            self.health_count("net_fail")
            self.health_why(prof, e)
            self.health_problem(f"Модель ({(prof or {}).get('kind') or 'openai'}): {e}")
            msg = f"{e}." if self._cloud_said(prof, e) else f"Не получилось: {e}."   # облако объясняет само
            from cloud import is_cloud, key_gone
            if is_cloud(prof) and key_gone(e) and self._cloud_key_gone():
                msg = "Ключ Dewiar удалён на сайте — теперь думаю по аккаунту dewiar.pro. Повторите, пожалуйста, вопрос."
            turn.error = msg
            from health import why_kind
            if getattr(turn, "greet", False) and why_kind(e) in ("connect", "timeout"):
                # 15.11 (владелец: после сна вместо «С возвращением» — «не могу подключиться к dewiar.pro»): приветствие
                # человек не просил — сеть ещё не поднялась, значит, просто молчим; спросит сам — ответим или скажем почему
                log.info("👋 приветствие не вышло — сеть ещё не готова (%s): молчу", e)
                turn.full, turn.error = "", ""
            elif getattr(e, "topup", False):
                # 0.82.1: талеры кончились — на экран полный текст (номер DW-…, как пополнить), голосом — коротко и без
                # ссылки; виджет и студия показывают кнопку «Пополнить» (topup)
                self.emit("error", text=msg, topup=True)
                self.emit("answer", text=msg, done=True, topup=True)
                turn.full = ""
                sentences.put(getattr(e, "say", "") or "Талеры закончились. Пополнить — кнопкой на экране.")
            else:
                self.emit("error", text=msg)
                self.emit("answer", text=msg, done=True)
                turn.full = ""
                sentences.put(msg)
        sentences.put(None)
        speaker.join()
        turn.ended = True                              # _wait_watch: ход кончился — строку ожидания убрать
        self.cloud.after_turn(prof)                    # облако по ключу — узнать новый заряд
        if turn.via and turn.via.get("done"):
            try:
                turn.via["done"]("(ответ остановлен)" if turn.cancel.is_set() and not turn.full.strip()
                                 else (turn.full.strip() or getattr(turn, "error", "") or "Не получилось ответить."))
            except Exception:  # noqa: BLE001
                log.exception("отправка ответа в Telegram")
        if turn.report:
            try:
                turn.report(None if turn.cancel.is_set() else bool(turn.full.strip()) and not turn.error,
                            turn.full.strip() or turn.error)
            except Exception:  # noqa: BLE001
                log.exception("итог хода")
        if turn.cancel.is_set():
            return
        self._turn_finish(turn, text, images)

    def _turn_finish(self, turn, text, images=()):
        """Ход разговора, шаг «после ответа» (из _run_turn, чистое ядро 1.0.12): ответ — в историю (с действиями, фактами,
        передачей слова), «Ваша очередь» (окно продолжения разговора), возврат к главному персонажу после специалиста и
        передача слова, если её попросил инструмент. Отменённый ход сюда не доходит."""
        if turn.full.strip():
            said = text + (" [к сообщению была приложена картинка]" if images else "")
            acts = list(dict.fromkeys(getattr(turn, "tools_ok", None) or []))
            facts = list(getattr(turn, "facts", None) or [])
            calls = hist_calls(getattr(turn, "done_calls", None)) if self.s.get("llm", "history_native") is True else []
            # передал слово явно (call_persona) или специалист, позванный на вопрос, возвращает слово главному — тому
            # его разговор справкой; просто переключились — нет
            hand = getattr(turn, "switch_to", None) or getattr(turn, "back_to", None)
            self.history += [{"role": "user", "content": said},
                             {"role": "assistant", "content": turn.full.strip(), "who": self.s.get("persona"),
                              **({"acts": acts} if acts else {}), **({"facts": facts} if facts else {}), **({"handoff": hand} if hand else {}),
                              **({"calls": calls} if calls else {}),
                              **({"model": turn.model} if getattr(turn, "model", "") else {}),
                              **({"net": True} if getattr(turn, "net", False) else {})}]
            self.last_turn_time = time.monotonic()
            if not turn.via:
                self.local_act = time.time()               # человек говорил с этим компьютером сам — бот Telegram отвечает отсюда
            self._conv_after()
            if not turn.via:
                self._pause_ok()                           # голосом и без обрыва — добавка к паузе понемногу тает
        follow = 0.0 if turn.via or time.monotonic() < self._echo_until else float(self.s.get("audio", "follow_up_seconds") or 0)
        if getattr(self, "muted", False) or getattr(self, "_mic_pause", 0) or getattr(turn, "typed", False):
            follow = 0.0                                   # микрофон выключен или вопрос набран — «ваша очередь» не открываем
        if getattr(self, "_tray_at", 0) >= getattr(turn, "t0", time.monotonic()):
            # в этом ходе виджет спрятали («Спрякся» — модель поняла и спрятала): не ждать ответа — иначе «Ваша очередь»
            # возвращала виджет на экран (20.10, 22:41: «4 раза просил спрятаться — исчезала и появлялась»)
            follow = 0.0
        self.follow_up_until = time.monotonic() + follow
        opened = False
        with self._turn_lock:
            if self.turn is turn:
                self.turn = None
                self.set_state("listening" if follow > 0 else "idle")
                opened = follow > 0
        if opened and not getattr(turn, "switch_to", None):
            # ход передан человеку: можно отвечать без имени. Окна показывают «Ваша очередь» и сколько осталось,
            # а на слух — мягкий сигнал (истечёт окно — прозвучит «не слушаю», см. engine_audio)
            self.emit("turn", seconds=round(follow, 1))
            if self.s.get("audio", "turn_tone") is not False:
                self.play_tone("turn")
        back = getattr(turn, "back_to", None)
        if back and self.s.get("persona") != back:
            self.switch_persona(back)                 # специалист ответил — снова главный
        pid = getattr(turn, "switch_to", None)
        if pid and not turn.cancel.is_set():
            prev = self.personas.get(self.s.get("persona"))["name"]
            self.switch_persona(pid)
            # новый персонаж откликается сам — своим голосом, зная весь разговор
            task = getattr(turn, "switch_task", "")
            if task:                                   # №137: поручение — явной вводной, итог — в общую заметку
                self.ask(f"({prev} передал(а) тебе поручение пользователя: «{task}». Это твоя задача сейчас — сделай её "
                         "сам(а), нужными инструментами (данные — в разговоре выше, в заметках и файлах). Итог скажи коротко; если он "
                         "больше пары фраз — запиши в заметку «Команда: <о чём>» (save_note) и скажи, где он.)", quiet=True)
            else:
                self.ask(f"({prev} позвал(а) тебя в разговор. Откликнись одной-двумя короткими фразами от себя и "
                         f"продолжи то, о чём просил пользователь.)", quiet=True)
