"""Слух — имя (часть Engine, чистое ядро 1.0.16): поток name-check, созвоны (кто слушает микрофон, «только главный»),
имя по звучанию, ослышанное имя, ожидание вопроса после имени."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class NameMixin:
    def _check_worker(self):
        """Поток name-check: ищет имя во фразах из check_q — ("utt", pcm, uid) без явного имени и ("barge", …)
        поверх ответа. Сначала отпечаток голоса, затем точная модель + строгий find_name. Нашли — перебиваем ответ
        и отправляем фразу как вопрос; не нашли — это разговор «не мне» (учитывается в _noisy)."""
        head_bytes = int(2.2 * RATE) * 2                   # имя — в начале фразы («Девиар, …» — меньше секунды)
        if hasattr(os, "setpriority") and hasattr(threading, "get_native_id"):     # в Windows setpriority нет
            try:                                           # фоновая проверка имени уступает созвону и другим программам
                os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 5)
            except OSError:
                pass
        while not self.stopping.is_set():
            kind, pcm, uid = self.check_q.get()
            if kind == "stop":
                self._stop_check(pcm, uid)
                continue
            if self._check_voiceprint(kind, pcm, uid):
                continue
            checker = self.wake_checker()
            if checker is None:
                self.barge_done.pop(uid, None)
                continue
            try:
                t0 = time.monotonic()
                # короткую фразу — целиком (тогда текст сразу и вопрос); длинную — только начало, где имя
                chunk = pcm if len(pcm) <= int(3.0 * RATE) * 2 else pcm[:head_bytes]
                text = checker.transcribe(chunk).strip()
            except Exception as e:  # noqa: BLE001
                log.debug("проверка имени не удалась: %s", e)
                continue
            pid, _ = find_name(text, self._wake_aliases(), strict=True)
            short = len(pcm) / 2 / RATE <= 1.6 and len(text.split()) <= 2
            if not pid and self.vosk_wake_check == uid and text and (
                    (short and self._name_like(text)) or self._name_like(text, 0.7)):
                # «Лира» одна, с паузой: точная модель ослышала короткое имя («Лиру», «Ира») — это и было имя.
                # 20.11 (владелец: «приходится по 5 раз звать»): и в начале фразы — «Лера, какая погода» — если быстрый
                # слух слышал имя, а первое слово точной модели на него похоже заметно (≥ 0,7): два слуха сходятся — зов
                pid = self.personas.wake_map(kids=True).get(getattr(self, "_vosk_wake_word", "")) or None
            if pid and kind == "barge" and not self.status.get("aec_real") and self._is_self_echo(text, barge=True):
                log.info("🔁 Имя поверх ответа — в моей же фразе из колонок, не перебиваю: «%s»", text[:80])
                pid = None                                 # №543: «…Джарвис» в ответе — не зов
            ms = int((time.monotonic() - t0) * 1000)
            if pid:
                log.info("👂 %s: «%s» → %s (%d мс)", checker.name, text, pid, ms)
            else:                                      # чужие разговоры в журнал не пишем (только в подробном режиме)
                log.debug("👂 %s: «%s» → имени нет (%d мс)", checker.name, text, ms)
            self.emit("hearing", text=text, by=checker.name, name=pid or "", ms=ms)
            if not pid:
                self.barge_done.pop(uid, None)
                if len(text) > 12:
                    self._chatter.append(time.monotonic())     # вокруг разговаривают — не со мной
                if self.vosk_wake_check == uid:
                    self.vosk_wake_check = -1
                    self._wake_count("wake_no")
                    self.wake_time = 0.0                            # следующая фраза — не «по имени»
                    log.info("🎧 «%s» от быстрого слуха не подтвердилось — это не обращение, молча жду дальше", self._vosk_wake_word)
                    self.set_state("idle")
                continue
            if self.vosk_wake_check == uid:
                self.vosk_wake_check = -1
                self._wake_count("wake_ok")
                self._voice_turn_t = time.monotonic()
            log.info("🎤 Имя распознано точной моделью: «%s»", text)
            self.emit("wake", phrase=pid)
            if kind == "barge":
                self.barge_hit = uid                        # фраза, когда закончится, пойдёт как вопрос
                self.interrupt("имя")
                ended = self.barge_done.pop(uid, None)
                if ended is not None:                       # …а если уже закончилась — отправляем сейчас
                    self.stt_q.put((ended, True, False))
                    self.set_state("thinking")
                continue
            if self.state in ("speaking", "thinking"):
                self.interrupt("имя")
            # распознали только начало или не тем распознавателем, что для вопросов, — фразу целиком распознаем заново
            if len(pcm) > len(chunk) or checker is not self.current_stt():
                self.stt_q.put((pcm, True, False))
                self.set_state("thinking")
            else:
                self.set_state("thinking")
                self.handle_text(text, True, False, dur=len(pcm) / 2 / RATE)

    # ---------- ложные срабатывания: счёт и «не тебе» ----------

    def _wake_count(self, what):
        """Счёт слуха по имени для «Здоровья» (только числа): wake_spot — быстрый слух услышал имя, wake_ok — точная
        модель подтвердила, wake_no — не подтвердила (молча ждём дальше), wake_false — «не тебе» или стоп кнопкой сразу
        после отклика по голосу, wake_stop — «стоп / хватит» в первые секунды ответа на голос."""
        try:
            if hasattr(self, "health_use"):
                self.health_use(what)
        except Exception:  # noqa: BLE001
            pass

    def _wake_was_false(self, why):
        """Человек сказал, что это было не ему («не тебе», «я не с тобой»), или остановил кнопкой ответ, начатый голосом:
        счёт, минуту не откликаемся на голос (кнопка работает) и считаем, что вокруг разговор — проверка строже."""
        now = time.monotonic()
        self._wake_count("wake_false")
        self._quiet_until = now + 60
        ch = getattr(self, "_chatter", None)
        if ch is not None:
            ch.extend([now] * 4)                           # _noisy(): ближайшие полторы минуты — разговор рядом
        log.info("🙊 Ложное срабатывание (%s) — минуту не откликаюсь на голос", why)

    def _wake_stop_early(self):
        """«Стоп / хватит / замолчи» в первые секунды ответа, начатого по голосу, — возможно, звали не меня: в счёт."""
        if time.monotonic() - getattr(self, "_voice_turn_t", -99.0) < 12:
            self._wake_count("wake_stop")

    # ---------- созвон ----------

    def _noisy(self):
        """Вокруг идёт разговор: за последние полторы минуты не меньше четырёх фраз «не мне»."""
        now = time.monotonic()
        return sum(1 for t in self._chatter if now - t < 90) >= 4

    def _meeting_mode(self):
        return self.s.get("audio", "meeting") or "pause"

    def _wake_aliases(self):
        """На созвоне в режиме «только главный» — откликаемся только на имя активного персонажа."""
        if self.meeting and self._meeting_mode() == "main":
            me = self.s.get("persona")
            return {me: self.aliases[me]} if me in self.aliases else self.aliases
        return self.aliases

    def _meeting_ignores(self, phrase):
        """Пропустить ли имя от быстрого слуха из-за созвона (только в покое): режим pause — любое,
        main — кроме имени активного персонажа. Включён суфлёр — любое и всегда: на встрече ассистент молчит."""
        pr = getattr(self, "prompter", None)
        if pr is not None and (pr.on or pr.enrolling is not None):
            return True
        if not self.meeting or self.state != "idle":
            return False
        mode = self._meeting_mode()
        if mode == "pause":
            return True
        if mode == "main":
            try:
                return self.personas.wake_map(kids=True).get(phrase) not in (None, self.s.get("persona"))
            except Exception:  # noqa: BLE001
                return False
        return False

    def _meeting_watch(self):
        """Поток meeting: раз в 3 секунды — не слушает ли микрофон другая программа (созвон); итог — self.meeting
        и status["meeting"]. В режиме normal созвон не отслеживается."""
        from meeting import mic_users
        while not self.stopping.is_set():
            apps = mic_users() if self._meeting_mode() != "normal" else []
            if apps != self.meeting:
                was = bool(self.meeting)
                self.meeting = apps
                if bool(apps) != was:
                    log.info("🎧 %s", f"Созвон ({', '.join(apps)}): " + {"pause": "имя не слушаю — говорите со мной по кнопке",
                                                                          "main": "слушаю только главное имя"}.get(self._meeting_mode(), "")
                             if apps else "Созвон закончился — слушаю как обычно")
                self.status["meeting"] = {"apps": apps, "mode": self._meeting_mode()} if apps else None
                self.emit("status", status=self.status)
                if apps and not was and not self.prompter.on and self.s.get("ui", "prompter_offer") is not False \
                        and (self.s.get("features") or {}).get("prompter") is not False:      # «Возможности»: суфлёр выключен — не предлагаем
                    self.emit("prompter_offer", apps=apps)     # созвон начался — виджет предложит суфлёр
            self.stopping.wait(3.0)

    # ---------- имя по голосу, своё эхо, разбор распознанной фразы ----------

    def _check_voiceprint(self, kind, pcm, uid):
        """Имя по звучанию (голосовой отпечаток) -> True, если имя найдено и фраза обработана.
        Для ранней проверки поверх ответа ("barge") фраза может ещё не кончиться — тогда место разреза
        запоминается в barge_cut, и её подхватит _on_utterance."""
        if not self.voiceprints.items:
            return False
        t0 = time.monotonic()
        pid, end, dist = self.voiceprints.match(pcm, allowed=set(self._wake_aliases()))
        ms = int((time.monotonic() - t0) * 1000)
        if not pid:
            log.debug("отпечаток: имени нет (%.3f, %d мс)", dist, ms)
            if self.wake_checker() is None:
                self.emit("hearing", text="", by="отпечаток голоса", name="", ms=ms, dist=round(dist, 3))
            return False
        name = self.personas.get(pid)["name"]
        log.info("🎤 Имя «%s» узнано по голосу (%.3f, %d мс)", name, dist, ms)
        self.emit("hearing", text=f"«{name}» — по голосу", by="отпечаток голоса", name=pid, ms=ms)
        self.emit("wake", phrase=pid)
        if kind == "barge":
            self.barge_hit = uid
            self.interrupt("имя")
            ended = self.barge_done.pop(uid, None)
            if ended is not None:
                self._after_name(pid, ended, end)
            else:
                self.barge_cut = (pid, end)
            return True
        if self.state in ("speaking", "thinking"):
            self.interrupt("имя")
        self._after_name(pid, pcm, end)
        return True

    def _after_name(self, pid, pcm, end_sec):
        """Имя найдено по звуку: остаток фразы — вопрос."""
        if pid != self.s.get("persona"):
            self.switch_persona(pid)
        rest = pcm[int(end_sec * RATE) * 2:]
        if len(rest) / 2 / RATE < 0.45:
            self.listen_for_command()
            return
        self.set_state("thinking")
        self.stt_q.put((rest, True, False, pid))

    def _wake_misheard(self, text, dur):
        """Быстрый слух услышал имя В НАЧАЛЕ фразы, а точная модель его ослышала или потеряла: «Мира, включи музыку»,
        «Нина, какая погода», «включи музыку» (имя срезано). Отзыв 28.10: «зову „Лира“, начинаю говорить — а она через
        пару секунд молча отключается, примерно в 30 % случаев»: фраза считалась ложным срабатыванием. Теперь: имя в
        первых 2 с фразы и первое слово похоже на имя — это обращение; имени в тексте нет вовсе, но имя было в первые
        1,2 с, фраза до 8 с и это просьба («включи», «какая…») — тоже. Вокруг разговор (_noisy) — не гадаем: там имя
        и так проверяет точная модель. -> (pid, конец имени в тексте) или (None, 0)."""
        off = getattr(self, "_wake_off", None)
        self._wake_off = None
        spotted = self.personas.wake_map(kids=True).get(getattr(self, "_wake_phrase", ""))
        if not spotted or off is None or off > 2.0 or getattr(self, "_noisy", lambda: False)():
            return None, 0
        m = re.match(r"\s*([\w-]+)", text)
        if m and len(text.split()) >= 2 and self._name_like(m.group(1)):
            log.info("🎤 Имя «%s» слышно в начале, распознано как «%s» — это обращение", self._wake_phrase, m.group(1))
            return spotted, m.end()
        if off <= 1.2 and dur <= 8 and to_me(text):
            log.info("🎤 Имя «%s» слышно в начале, в распознанном его нет — просьба, это обращение", self._wake_phrase)
            return spotted, 0
        return None, 0

    def _name_like(self, text, need=0.55):
        """Похоже ли короткое распознанное на ослышанное имя («Игрова», «Элла» вместо «Эва»), а не на ответ человека.
        Отчёт 11.10: «Лира» → «Слушаю…», затем быстрое «спасибо» / «как дела» принимались за ослышанное имя — фраза
        терялась, и снова «Слушаю…». Пусто или первое слово хоть немного похоже на имя (≥ 0,55) — имя; иначе — фраза."""
        import difflib
        w = _norm(re.sub(r"[^\w ]", " ", text or "")).split()
        if not w:
            return True
        names = [_norm(a).replace(" ", "") for al in self.aliases.values() for a in al]
        return any(difflib.SequenceMatcher(None, w[0], a).ratio() >= need for a in names)

    def listen_for_command(self, seconds=None):
        """Имя услышали без вопроса: ждём вопрос seconds секунд (без имени) и даём короткий сигнал. По умолчанию —
        «Сколько ждать, пока я молчу» из «Слуха» (audio.follow_up_seconds, не меньше 8 с; №514)."""
        if seconds is None:
            seconds = max(8.0, float(self.s.get("audio", "follow_up_seconds") or 0))
        self._listen_peak, self._listen_vad = 0.0, 0.0
        log.info("🎤 Слушаю вопрос (%d с)", seconds)
        self.follow_up_until = time.monotonic() + seconds
        self._invited_until = self.follow_up_until + 30     # начатая в эти секунды фраза — вопрос мне, даже длинная
        self.set_state("listening")
        self.emit("heard", text="")
        if time.monotonic() - getattr(self, "_wake_tone_at", 0.0) > 4:   # уже прозвучал на само имя — второй раз не нужен
            self.play_tone("wake")
