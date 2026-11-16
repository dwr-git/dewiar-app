"""Действия — вопрос «да/нет» (часть Engine, чистое ядро 1.0.16): спросить голосом и кнопками, разобрать ответ,
короткое «да» в ответ на вопрос, ответ задаче в чате."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from acts_base import confirm_word


class ConfirmMixin:
    def _just_agreed(self, turn):
        """Этот ход — короткое «да / давай / запускай» в ответ на вопрос ассистента (его прошлая реплика кончилась «?»,
        не раньше 5 минут назад)? Тогда первое «Выполнить?» за ход уже отвечено (№478). Опасное (защита просит
        подтверждения сама) — спрашиваем всё равно; вызывающий это проверяет."""
        # «Ещё раз»/«Изменить» в «Чате» (рецензия 0.86): переспрошенное «да» — не согласие на новое действие
        if getattr(turn, "replay", False) or time.monotonic() - float(getattr(self, "_chat_replay", 0) or 0) < 60:
            return False
        said = (getattr(turn, "asked", None) or "").strip()
        if not said or "\n\nВложения:" in said or len(said) > 60 or len(re.findall(r"[\wё]+", said)) > 6:
            return False
        if confirm_word(said) is not True:
            return False
        cut = getattr(self, "_confirm_cut", None)
        if cut and time.monotonic() - cut[0] < 180 and getattr(turn, "n", 0) == cut[2] + 1:   # только следующий ход
            # №625–628: перебили, пока я спрашивала «выполнить?», и человек тут же ответил «да» — это и есть ответ
            self._confirm_cut = None
            return True
        last = next((m for m in reversed(getattr(self, "history", None) or []) if m.get("role") == "assistant"), None)
        if not last or not str(last.get("content") or "").rstrip().endswith("?"):
            return False
        return time.monotonic() - float(getattr(self, "last_turn_time", 0) or 0) < 300

    def _confirm(self, turn, question, sentences, timeout=None, always=False, again=0):
        """Спросить голосом и кнопками, дождаться «да»/«нет». -> True — согласились («always» — «всегда»), False — «нет»,
        None — ответа не дождались (молчание — не отказ: №478).
        Ответ приходит из другого потока через pending_confirm (_answer_confirm или кнопка). Голосом — сперва ждём,
        пока договорится уже начатый ответ, затем ждём timeout секунд: 30, а в текстовом режиме (читают и жмут кнопку,
        №478: 15 с не хватало) — 90."""
        if timeout is None:
            timeout = 90 if (getattr(self, "s", None) is not None and self.s.get("ui", "text_mode")) else 30
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
        if again:                                            # не первый вопрос за ход — коротко (полный — на экране)
            ask_ = "Ещё команда — выполнить?" if always or "сервер" in question else "Выполнить и это?"
        else:
            ask_ = _spoken_question(question) + (" Скажите «да», «нет» или «всегда» — тогда команды, которые только "
                                                 "смотрят, на этом сервере больше не буду спрашивать." if always
                                                 else " Скажите «да» или «нет».")
        # №625–628: вопрос — слова программы, не модели: при перебивании он не должен попасть в историю её словами
        turn.sys_said = list(getattr(turn, "sys_said", None) or []) + [ask_]
        sentences.put(ask_)
        drained = threading.Event()
        sentences.put(("sync", drained))
        drained.wait(30)
        if turn.cancel.is_set():
            return False
        box = {"event": threading.Event(), "answer": False, "always": False}
        self.pending_confirm = box
        self.emit("confirm", text=question, always=bool(always))
        self.follow_up_until = time.monotonic() + timeout
        self.set_state("listening")
        answered = box["event"].wait(timeout)
        self.pending_confirm = None
        self.emit("confirm_done", ok=box["answer"])
        log.info("Подтверждение: %s", ("всегда" if box.get("always") else "да") if box["answer"] else "нет" if answered or turn.cancel.is_set() else "без ответа")
        self.set_state("thinking")
        if not answered and not turn.cancel.is_set():
            return None
        return "always" if box["answer"] and box.get("always") and always else box["answer"]

    def _task_reply(self, text, how="chat"):
        """№551: задача спросила, а человек ответил в чате («разрешаю», «дай права», «папка — D:\\Bot») — ответ уходит ей,
        а не новым вопросом в разговор. В первые 2 минуты после вопроса — любой короткий ответ без имени персонажа, потом —
        похожий на ответ (да/нет, разрешение, папка, путь). -> True, если передали."""
        tm = getattr(self, "tasks", None)
        wt = tm.waiting() if tm is not None and (text or "").strip() else None
        if wt is None or len(re.findall(r"[\wё]+", text)) > 40:
            return False
        if find_name(text, self.aliases, strict=True)[0]:
            return False                                   # «Патрик, …» — это разговор с персонажем
        fresh = time.monotonic() < getattr(self, "task_answer_until", 0.0)
        if not (fresh or confirm_word(text) is not None or self.TASK_REPLY_RX.search(text)):
            return False
        self.task_answer_until = 0.0
        try:
            self.tasks.answer(wt.id, text.strip())
        except ValueError:
            return False
        log.info("Ответ в задачу «%s» (%s): %s", wt.title, how, text.strip()[:80])
        self.emit("answer", text=self._g(f"Передала в задачу «{wt.title}»."), done=True)
        return True

    def _answer_confirm(self, text):
        """Разобрать услышанное как ответ на вопрос _confirm. -> True, если фраза была ответом и вопрос закрыт."""
        box = self.pending_confirm
        if not box:
            return False
        if re.search(r"больше не спрашива|без вопрос|не спрашивай", _norm(text)) or "всегда" in set(re.findall(r"[\wё]+", _norm(text))):
            box["answer"] = box["always"] = True
        else:
            v = confirm_word(text)
            if v is None:
                return False                   # непонятный ответ — ждём дальше
            box["answer"] = v
        box["event"].set()
        return True
