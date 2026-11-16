"""Ответ, часть «какая модель отвечает» (примесь AnswerMixin, core/engine_answer.py; чистое ядро 1.0.10): модель персонажа,
пробный заряд, запасные пути (облако Dewiar, своя модель), проба действий, медленная своя модель, ожидание и Сеть Лиры."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class ModelsMixin:
    def _slow_local(self, prof, sec):
        """Своя модель на этом компьютере думает больше минуты до первого слова (отчёты №121–124, 19.10: llama3 8B на
        4 ядрах без видеокарты — «думает по 600 секунд»): один раз за запуск сказать, что делать, а не молча ждать."""
        url = str(prof.get("base_url") or "")
        if sec < 60 or getattr(self, "_slow_said", False) or not re.search(r"//(127\.0\.0\.1|localhost|\[::1\])[:/]", url):
            return
        self._slow_said = True
        log.warning("Своя модель %s отвечает медленно: первые слова через %.0f с", prof.get("model") or url, sec)
        self.note(f"Модель на этом компьютере начала отвечать только через {round(sec)} с — ей не хватает мощности (нужна "
                  "видеокарта или модель полегче). Возьмите лёгкую (в Ollama: qwen3:1.7b или qwen2.5:3b) или подключите облако "
                  "Dewiar — студия → «Мозг».")

    def _coder_brain(self, prof):
        """№370 (28.10): «мозг» — модель для программирования (qwen2.5-coder:7b): по-русски отвечает плохо, сбивается на
        английский и печатает JSON вместо ответа. Один раз за запуск сказать, какую взять для разговора."""
        name = str((prof or {}).get("model") or "")
        if getattr(self, "_coder_said", False) or not self.CODER_RX.search(name):
            return False
        try:
            if self.s.get("persona") == "agent":           # Кодер со своей моделью для кода — так и задумано
                return False
        except Exception:  # noqa: BLE001
            pass
        self._coder_said = True
        log.warning("Мозг — модель для кода (%s): для разговора не годится", name)
        self.note(f"Сейчас «мозг» — модель для программирования ({name}): по-русски она говорит плохо и сбивается на английский. "
                  "Для разговора возьмите обычную — в Ollama qwen2.5:7b или qwen3:8b — или облако Dewiar: студия → «Мозг». "
                  "Модель для кода пригодится Кодеру.")
        return True

    def persona_llm(self, pid=None):
        """Модель, которой думает персонаж: своя (llm.persona = {pid: id профиля} — студия → «Персонажи» → «Мозг»),
        иначе общая (llm.active). Пакет 27.10, №346 и отзывы с YouTube: «разным персонажам — разных ИИ: один на GPT,
        второй на Gemini, третий на Claude» — раньше мозг был один на всех и его надо было переключать вручную."""
        pid = pid or self.s.get("persona")
        own = ((self.s.get("llm", "persona") or {}).get(pid) or "") if pid else ""
        profs = self.s.get("llm", "profiles") or {}
        if own and own in profs:
            # №403 (29.10): у одного сервера (Ollama) много моделей — персонажу своя модель того же профиля
            # (llm.persona_model[id]); раньше выбор модели менял профиль у всех, «слетало к последнему»
            m = ((self.s.get("llm", "persona_model") or {}).get(pid) or "").strip()
            return dict(profs[own], model=m) if m and not profs[own].get("cloud") else dict(profs[own])
        return self.s.active_llm()

    def _contact_maybe(self):
        """Автоподключение (0.69): после пяти удачных ответов — один раз (и ещё раз через три дня, если отложили) попросить
        контакт: «если что-то сломается — разработчик сможет ответить». Только по желанию; оставили — больше не спрашиваем."""
        c = self.s.get("cloud") or {}
        if not c.get("auto") or c.get("contact_done") or not c.get("key"):
            return
        n = int(c.get("auto_turns") or 0) + 1
        upd = {"auto_turns": n}
        asks = int(c.get("contact_asks") or 0)
        if n >= 5 and asks < 2 and time.time() - float(c.get("contact_asked") or 0) > 3 * 86400:
            upd.update(contact_asked=time.time(), contact_asks=asks + 1)
            self.s.update({"cloud": upd})
            threading.Timer(6, lambda: self.emit("contact_ask")).start()     # после ответа, не поверх него
            return
        self.s.update({"cloud": upd})

    def _trial_llm(self):
        """Пробный разговор сайта (cloud.php ?p=/trial/chat/completions) — мозг на первые минуты, пока свой не подключён:
        без ключа и настройки, без действий (напоминания, поиск — после «Подключить мозг Dewiar»), с пределами сайта (12 ответов
        в час с адреса). Выключатель — llm.trial: false. При вводе из wav (проверки) — только с DEWIAR_TRIAL. -> профиль или None."""
        if self.s.get("llm", "trial") is False or (self.wav_input and not os.environ.get("DEWIAR_TRIAL")):
            return None
        import cloud as C
        url = self.s.get("cloud", "url") or C.DEFAULT_URL
        if not getattr(self, "_trial_said", False):
            self._trial_said = True
            log.info("🧠 Мозг не подключён — отвечаю пробным разговором Dewiar (без действий)")
            self.emit("trial", on=True)
        self.health_use("trial")
        return {"name": "Пробный разговор Dewiar", "kind": "openai", "base_url": C.api_base(url) + "/trial", "api_key": "",
                "model": "trial", "trial": True, "max_tokens": 450}

    def llm_profile(self):
        """Модель для фоновых задач: своя из настроек задач, иначе активная."""
        pid = self.s.get("tasks", "llm") or ""
        profs = self.s.get("llm", "profiles") or {}
        return dict(profs[pid], id=pid) if pid in profs else self.s.active_llm()

    def max_steps(self):
        return int(self.s.get("tasks", "max_steps") or 80)

    def code_auto_run(self):
        return bool(self.s.get("tasks", "auto_run"))

    @staticmethod
    def _cloud_said(prof, e):
        """Ошибка, которую облако Dewiar объяснило само («заряд закончился», «лимит на сегодня») -> True.
        Такую ошибку говорим как есть и не повторяем запрос без инструментов. Тексты — от сервера облака (cloud.php)."""
        from cloud import is_cloud
        return is_cloud(prof) and bool(re.match(r"(Заряд|Ключ) Dewiar|Талер|На счёте dewiar\.pro|На сегодня лимит|Слишком много|Сейчас у Dewiar много людей", str(e)))

    def _cloud_fallback(self, prof, e):
        """Запасной мозг для облака: «Мозг» → карточка облака → «Если облако не отвечает» -> профиль или None
        (не облако, запасного нет или он тоже облачный). Показывает заметку на 15 с; режим инструментов — свой у запасного."""
        from cloud import is_cloud
        if not is_cloud(prof):
            return None
        fid = self.s.get("llm", "fallback") or ""
        fb = (self.s.get("llm", "profiles") or {}).get(fid)
        if not fb or is_cloud(fb):
            return None
        log.warning("☁ Облако: %s — отвечает запасной мозг «%s»", e, fb.get("name") or fid)
        self.note(f"Облако не ответило ({str(e)[:60]}) — ответил запасной мозг «{fb.get('name') or fid}»")
        threading.Timer(15, lambda: self.note("")).start()
        mode = (self.s.get("llm", "tools_modes") or {}).get(self._tools_key(fb))
        return dict(fb, tools_mode=mode) if mode in ("native", "prompt") else dict(fb)

    def _own_fallback(self, prof, e):
        """Своя модель (LM Studio, Ollama, свой сервер) не отвечает — не включена или сервер выключен (29.10, пакет:
        «своя модель · нет связи» — 107 за неделю; у 270 компьютеров из 820 мозг есть, а ответа не было ни разу).
        Включено «Мозг» → «Если своя модель не отвечает — отвечать через Dewiar» и мозг Dewiar подключён ->
        его профиль; выключено — один раз за запуск подсказка, что сделать. Без согласия вопрос в облако не уходит:
        свою модель часто выбирают ради приватности."""
        from cloud import PROFILE_ID, is_cloud
        from health import brain_kind, why_kind
        fb = (self.s.get("llm", "profiles") or {}).get(PROFILE_ID)
        # 15.11 (владелец: «вставить ключ Gemini, потом Kimi или GLM… пусть Лира поработает на нём»): сервис по ключу не
        # ответил — нет связи, кончились деньги, ключ отозван, сервис лёг — отвечает мозг Dewiar, и одной фразой — почему.
        # Вопрос и так уходил в интернет чужому сервису; выключить — «Кто чем думает» → «Подстраховка» (llm.key_fallback)
        why = why_kind(e)
        if not is_cloud(prof) and fb and brain_kind(prof) == "cloud" and why in ("connect", "timeout", "key", "balance", "server", "busy") \
                and self.s.get("llm", "key_fallback") is not False:
            svc = str(prof.get("name") or prof.get("model") or "сервис").split(" — ")[0]
            what = {"connect": "нет связи", "timeout": "не ответил вовремя", "key": "ключ не подошёл", "balance": "кончились деньги на ключе",
                    "server": "сбой у сервиса", "busy": "сервис перегружен"}[why]
            log.warning("Сервис по ключу «%s» не ответил (%s) — отвечает мозг Dewiar", svc, e)
            self.note(f"«{svc}» не ответил ({what}) — ответила через Dewiar.")
            threading.Timer(20, lambda: self.note("")).start()
            mode = (self.s.get("llm", "tools_modes") or {}).get(self._tools_key(fb))
            return dict(fb, tools_mode=mode) if mode in ("native", "prompt") else dict(fb)
        if is_cloud(prof) or brain_kind(prof) not in ("local", "server") or why != "connect":
            return None
        if self.s.get("llm", "own_fallback") and fb:
            log.warning("Своя модель не отвечает (%s) — отвечает мозг Dewiar", e)
            self.note("Своя модель не отвечает — ответила через Dewiar. Запустите LM Studio или Ollama, и я вернусь к ней.")
            threading.Timer(20, lambda: self.note("")).start()
            mode = (self.s.get("llm", "tools_modes") or {}).get(self._tools_key(fb))
            return dict(fb, tools_mode=mode) if mode in ("native", "prompt") else dict(fb)
        if not getattr(self, "_own_fb_hinted", False):
            self._own_fb_hinted = True
            self.note("Своя модель не отвечает: запустите LM Studio или Ollama (модель должна быть загружена). Чтобы в такие "
                      "минуты отвечал мозг Dewiar — студия → «Мозг» → «Если своя модель не отвечает».")
        return None

    def _tools_key(self, prof):
        """Ключ, под которым запоминается режим инструментов модели (llm.tools_modes): «адрес|модель»."""
        return f"{(prof or {}).get('base_url', '').rstrip('/')}|{(prof or {}).get('model', '')}"

    def probe_tools_bg(self, force=False):
        """Узнать в фоне (поток probe-tools), умеет ли активная модель вызывать инструменты и как: native, prompt
        или none. Один раз на «адрес|модель»; force — проверить заново."""
        prof = self.s.active_llm()
        if not prof:
            return
        key = self._tools_key(prof)
        modes = self.s.get("llm", "tools_modes") or {}
        # tools_probe_v 2: проверка первой версии ошибочно записывала «думающие» модели в «не умеет» (none);
        # v3 (22.10): облако Dewiar отклоняло проверку из-за chat_template_kwargs, и модель записывалась в «описанием
        # в тексте» (prompt) — такие записи один раз сбрасываем, чтобы проверить заново; найденные native остаются
        # v4 (22.10, вечер): настоящая причина — сайт превращал пустой объект {} в схеме функции в [] (cloud.php
        # chat_schema_fix); после обновления сайта — проверить ещё раз
        # v5 (23.10): «none» больше не выводится из проверки — прежние записи «none» сбрасываем
        if self.s.get("llm", "tools_probe_v") != 5:
            keep = ("native",) if self.s.get("llm", "tools_probe_v") != 4 else ("native", "prompt")
            stale = {k: v for k, v in modes.items() if v in keep}
            with self.s._lock:
                self.s.data.setdefault("llm", {})["tools_modes"] = stale
            self.s.update({"llm": {"tools_probe_v": 5}})
            modes = stale
        if key in self._probing or (not force and key in modes):
            return
        self._probing.add(key)

        def run():
            try:
                mode = probe_tools(prof)
                if mode is None:                      # сервер не ответил — не запоминаем, спросим в следующий раз
                    return
                self.s.update({"llm": {"tools_modes": {key: mode}}})
                if mode == "none":
                    self.note("Эта модель не умеет выполнять действия (музыка, скриншоты, программы) — только отвечать")
            except Exception as e:  # noqa: BLE001
                log.info("Проверка инструментов не удалась: %s", e)
            finally:
                self._probing.discard(key)
        threading.Thread(target=run, name="probe-tools", daemon=True).start()

    def _wait_watch(self, turn):
        """№446 (ПК 0.76, 31.10: «неимоверно долго отвечает, устал ждать, непонятно, что не так»): «Думаю…» висело 5 минут,
        а виджет говорил только «Модель отвечает долго — 307 с». Пока у хода нет ни слова, через WAIT_NOTE_SEC в строке
        состояния — чего ждём (сервер не ответил / модель размышляет / готовит действие / медленная модель) и что можно
        сделать (llm.wait_hint); обновляется раз в 5 с, с первым словом или концом хода убирается. Приветствие, на которое
        модель не ответила за GREET_LATE_SEC, отменяется: человек уже за компьютером, «с возвращением» через 5 минут ни к чему."""
        from llm import wait_hint, wait_info
        t0, shown, last = time.monotonic(), "", 0.0
        try:
            while not turn.cancel.wait(1.0):
                sec = time.monotonic() - t0
                if getattr(turn, "ended", False) or self.turn is not turn or turn.full.strip() or sec > 1800:
                    break
                if getattr(turn, "greet", False) and sec >= self.GREET_LATE_SEC:
                    with self._turn_lock:
                        if self.turn is turn:
                            self._cancel_locked()
                            self.set_state("idle")
                    log.info("👋 Приветствие опоздало (%.0f с без ответа модели) — молчу", sec)
                    break
                if sec < self.WAIT_NOTE_SEC or turn.via or getattr(turn, "via_job", False) or time.monotonic() - last < 5:
                    continue
                info = wait_info(turn.cancel)
                self.note(wait_hint(sec, info, getattr(turn, "think_auto", False)))
                shown, last = self.status.get("note") or "", time.monotonic()
                if sec < self.WAIT_NOTE_SEC + 2:
                    log.info("⏳ Модель молчит %.0f с: %s", sec, (info or {}).get("phase", "действие") +
                             (f", размышлений {info['reasoning']} симв." if info and info.get("reasoning") else ""))
        except Exception:  # noqa: BLE001 — строка ожидания не должна ронять ход
            log.debug("ожидание ответа", exc_info=True)
        finally:
            if shown and self.status.get("note") == shown:
                self.note("")

    def _net_closed(self):
        """«Сеть Лиры» не для этого разговора: детский режим или «Для старших» — только главный мозг Dewiar."""
        try:
            kids = getattr(self, "kids", None)
            if kids and kids.on():
                return True
            senior = getattr(self, "senior", None)
            return bool(senior is not None and senior.on())
        except Exception:  # noqa: BLE001
            return True

    def _net_rules_ok(self):
        """Правила сети проверены подписью и сеть включена (liranet.rules_ok — в фоне, раз в час)."""
        try:
            import liranet
            return liranet.rules_ok(self)
        except Exception:  # noqa: BLE001
            return False
