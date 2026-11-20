"""Слух — фразы (часть Engine, чистое ядро 1.0.16): главный цикл _listen (кадр за кадром), конец фразы и выученная
пауза, удержание «говорить», длинная запись, поток stt и запасной распознаватель, второй язык, диктовка удержанием."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from stt import stt_error_text
from ears_base import barge_floor, LONG_WAKE_S, stop_mid_phrase


class ListenMixin:
    def _listen(self):
        """Главный цикл слуха, кадр за кадром: проверка «микрофон молчит», полудуплекс во время ответа,
        слово запуска и «стоп» (быстрый слух Vosk), VAD — начало и конец фразы, перебивание речью поверх ответа.
        Готовая фраза → _on_utterance. Выход — конец потока или restart_audio."""
        self._pause_apply()                             # пауза конца фразы — своя у человека (_pause_*), меняется на ходу
        preroll = collections.deque(maxlen=12)          # ~0,4 с до срабатывания VAD — чтобы не терять начало слова
        in_speech, utt, silence, starts, speech_frames, t0 = False, [], 0, 0, 0, 0.0
        was_speaking, in_hold = False, False
        bs, quiet, ducked = 0, 0, False                 # перебивание речью: кадры речи, тишины, приглушили ли
        echo = collections.deque(maxlen=90)             # громкость остаточного эха своего голоса (~3 с)
        half_echo = collections.deque(maxlen=100)       # полудуплекс: громкость своего голоса в микрофоне (~3 с)
        half_pcm = collections.deque(maxlen=70)         # №564: полудуплекс — последние ~2,2 с микрофона (проверить «стоп»)
        spk_all = collections.deque(maxlen=160)         # №543: громкость микрофона, пока говорим (~5 с), — все кадры
        zst = {"since": None, "told": False, "all": True}      # поток идёт, а в нём нули или почти нули (_mic_zero_step)
        sleep_chk = defmic_chk = time.monotonic()
        while not self.stopping.is_set() and not self.restart_audio.is_set():
            frame = self.capture.read()
            if not frame:
                return
            now = time.monotonic()
            sa = getattr(self, "soft_aec", None)
            if sa is not None:
                frame = sa.near(frame, now)                 # своё эхоподавление (проба): свой голос — из микрофона
            if now - sleep_chk > 10 and os.name == "nt" and not self.wav_input:
                sleep_chk = now
                if self._sleep_due():
                    self._mic_asleep = True            # отпустить микрофон: компьютер может уснуть (_audio_loop ждёт мышь)
                    return
            if now - defmic_chk > 3:
                defmic_chk = now
                if self._default_mic_moved():
                    self.restart_audio.set()           # №134: Windows сменила микрофон по умолчанию — переоткрыть на новый
                    return
            self._mic_ring.append(frame)                # 0,4 с в памяти — удержание не теряет начало фразы (не распознаётся)
            if (self.muted and self.hold is None and not self._mute_pass) or getattr(self, "_mic_pause", 0):
                if self._mic_rest_due():
                    self._mic_off = True               # №622: выключен — закрыть поток совсем (_audio_loop ждёт включения)
                    return
                continue                                 # микрофон выключен: слушаем только удержание и одну фразу по нажатию
            hold = self.hold
            if hold is not None:
                # диктовка удержанием: пишем всё подряд, без поиска конца фразы и имени, — пока не отпустят
                hold["pcm"].append(frame)
                a = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
                self._level(min(1.0, float(np.sqrt(np.mean(a * a))) / 3000.0), "mic")
                if len(hold["pcm"]) * FRAME_S >= hold["max"]:
                    log.info("🎙 Удержание длиннее %d с — отправляю, что есть", hold["max"])
                    threading.Thread(target=self.hold_end, kwargs={"why": "limit"}, daemon=True).start()
                in_hold = True
                continue
            if in_hold:                                     # отпустили — слух начинает с чистого листа
                in_hold = False
                self.vad.reset()
                self.spotter.rec.Reset()
                in_speech, utt, silence, starts, preroll = False, [], 0, 0, collections.deque(maxlen=12)
            if not self.wav_input and self._mic_zero_step(zst, frame, now) == "heal":
                return
            self._listen_live = now                        # слух обрабатывает звук: окно «ваша очередь» закроет он сам
            lm = getattr(self, "_listen_min_t", None)          # минуты слушания — знаменатель для «ложных за 10 ч»
            if lm is None or now - lm > 120:
                self._listen_min_t = now
            elif now - lm >= 60:
                self._listen_min_t = lm + 60
                self._wake_count("listen_min")
            speaking = self.state == "speaking"
            if speaking and not self.status["aec"]:
                # полудуплекс: себя не слушаем — кроме короткого «стоп / хватит / пауза / отмена»
                if not was_speaking:
                    self.spotter.rec.Reset()
                    half_echo.clear()
                    half_pcm.clear()
                was_speaking = True
                half_pcm.append(frame)
                a = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
                rms = float(np.sqrt(np.mean(a * a)))
                half_echo.append(rms)
                w = self.spotter.feed_stop_only(frame) if self.s.get("audio", "barge_in") != "off" else None
                if w:
                    loud = sorted(half_echo)[len(half_echo) // 2] if half_echo else 0.0
                    if self._own_word(w):
                        log.info("«%s» — это моё же слово во фразе, не останавливаюсь", w)
                    elif max(list(half_echo)[-15:] or [0]) < 1.4 * loud:
                        log.info("«%s» тише моего голоса — похоже на эхо, не останавливаюсь", w)
                    elif self._stop_verify(w, b"".join(half_pcm), now):
                        pass                                   # №564: решит точная модель (_stop_check), голос пока тише
                    else:
                        log.info("✋ «%s» — замолкаю (без эхоподавления)", w)
                        self._wake_stop_early()
                        self.stop_utt, self.stop_time, self._stop_sleep = True, now, True
                        self.interrupt(w, follow=False)
                continue
            if was_speaking and not speaking:
                was_speaking = False
                self.vad.reset()
                self.spotter.rec.Reset()
                in_speech, utt, preroll = False, [], collections.deque(maxlen=12)

            barge = self.s.get("audio", "barge_in")
            for kind, phrase in self.spotter.feed(frame):
                if kind == "wake" and self.state == "idle" and now < self._quiet_until:
                    # только что остановили кнопкой ответ, начатый по голосу, — это было ложное срабатывание (видео, ТВ):
                    # минуту не откликаемся на голос, нажатие на лицо работает как обычно (отзыв 14.10)
                    log.info("🤫 Имя «%s» — пропускаю: недавно остановили ложное срабатывание (ещё %.0f с)", phrase, self._quiet_until - now)
                    continue
                if kind == "wake" and self._meeting_ignores(phrase):
                    log.info("🎧 Созвон — имя «%s» пропускаю (%s)", phrase, ", ".join(self.meeting) or "")
                    continue
                if kind == "wake" and self.state == "idle":
                    self._wake_count("wake_spot")
                if kind == "wake" and self.state == "speaking" and not self.status.get("aec_real") and self._own_word(phrase):
                    # №543: без настоящего эхоподавления быстрый слух слышит имя в моём же ответе («…Джарвис расскажет»)
                    log.info("🎤 «%s» — имя в моей же речи (эхо), не перебиваю", phrase)
                    continue
                if kind == "wake":
                    log.info("🎤 Имя «%s» услышано", phrase)
                    self.wake_time, self._wake_phrase = now, phrase
                    if in_speech and len(utt) * FRAME_S > 2.5:
                        # имя посреди долгой «фразы» (играет музыка, вокруг говорят): иначе команда утонет в 20 секундах
                        # звука. Фраза начинается заново за 1,6 с до срабатывания — с самого имени.
                        keep = int(1.6 / FRAME_S)
                        long_s = len(utt) * FRAME_S
                        log.info("🎤 Имя посреди долгого звука (%.1f с) — начинаю фразу с имени", long_s)
                        utt = utt[-keep:]
                        t0, silence, speech_frames = now - len(utt) * FRAME_S, 0, len(utt)
                        if long_s > LONG_WAKE_S and self.state == "idle" and self.wake_checker() is not None:
                            # №717 (14.11: «смотрю видео на YouTube — он включается, записывает часть голосового от видео»):
                            # имя посреди долгой сплошной речи — почти всегда видео или разговор рядом («агент», «Оскар»
                            # в ролике). Не откликаемся сразу: точная модель проверит, звучит ли имя обращением в начале
                            log.info("🎧 «%s» посреди %.0f с сплошной речи — похоже на видео, проверю точной моделью", phrase, long_s)
                            self.vosk_wake_check, self._vosk_wake_word = self.utt_id, phrase
                            continue
                    if (self.state == "idle" and self.wake_checker() is not None
                            and (self._noisy() or self.s.get("audio", "wake_verify") is not False)):
                        # Быстрый слух только предлагает, решает точная модель (владелец 19.11: «держу микрофон выключенным —
                        # за день почти десяток ложных срабатываний, колонка Алиса — ни одного»). Раньше проверка была
                        # лишь когда вокруг много говорят; теперь — каждый раз: не подтвердилось — молча ждём дальше, без
                        # виджета и сигнала. Цена — доля секунды до «слушаю».
                        log.info("🎤 «%s»? Проверю точной моделью%s", phrase, " — вокруг разговор" if self._noisy() else "")
                        self.vosk_wake_check, self._vosk_wake_word = (self.utt_id if in_speech else self.utt_id + 1), phrase
                        continue
                    self.emit("wake", phrase=phrase)
                    if self.state in ("speaking", "thinking") and barge != "off":
                        self.interrupt("имя")
                    elif self.state == "idle":
                        self.set_state("listening")
                        # звук «слушаю» — как только после имени пауза (≈0,25 с), а не поверх речи: звонок посреди
                        # «Лира, кратко как дела» попадал в микрофон и мешал распознать вопрос (отчёт 11.10)
                        self._wake_tone_at, self._wake_tone_due = now, now
                elif kind == "stop" and self.alarm:
                    log.info("✋ «%s» — выключаю будильник", phrase)
                    self.stop_utt, self.stop_time = True, now
                    self.alarm_finish("ack")
                elif kind == "stop" and self.state == "listening" and not self.meeting and stop_mid_phrase(in_speech, len(utt) * FRAME_S):
                    # жалоба №404 (29.10: «засыпает, прерывая разговор»): посреди длинной фразы быстрый слух принял
                    # «схватит» за «хватит» — и Лира уснула. Слово-стоп посреди речи — не команда: решит точное
                    # распознавание в конце фразы (стоп последним словом — сон, ветка follow в _handle)
                    log.info("«%s» посреди фразы (%.1f с) — не засыпаю, дослушаю", phrase, len(utt) * FRAME_S)
                elif kind == "stop" and self.state == "listening" and not self.meeting:
                    # ждём ответа («Ваша очередь») или вопроса после имени — «стоп», «хватит»: спим сразу (и музыку на
                    # паузу, если это «пауза»/«стоп»). Раньше «стоп» здесь уходил в ветку музыки и не усыплял (отчёт 11.10)
                    self.stop_utt, self.stop_time = True, now
                    self.go_sleep(phrase)
                elif kind == "stop" and self.state == "idle" and phrase in MEDIA_STOP and not self.meeting:
                    self._pending_media_stop = now            # решим, когда Vosk закончит фразу: одно слово — пауза
                elif kind == "stop" and self.state == "speaking" and self._own_word(phrase):
                    log.info("«%s» — это моё же слово во фразе (эхо), не останавливаюсь", phrase)
                elif kind == "stop" and self.state in ("speaking", "thinking") and barge != "off":
                    log.info("✋ «%s» — замолкаю", phrase)
                    self._wake_stop_early()
                    self.stop_utt = now - self.wake_time > 3     # одно «стоп» — не вопрос; «стоп, лучше …» — вопрос
                    self.stop_time, self._stop_sleep = now, self.stop_utt
                    self.interrupt(phrase, follow=False)
                    self.follow_up_until = now + 3.0             # «стоп, лучше расскажи…» — договорить успеете

            fin = getattr(self.spotter, "last_final", None)
            if fin is not None:
                self.spotter.last_final = None
                if self._pending_media_stop and now - self._pending_media_stop < 4 and fin.strip() in MEDIA_STOP \
                        and self.state in ("idle", "listening"):
                    self._media_stop_heard(fin.strip(), now, in_speech)
                elif fin.strip() in MEDIA_WORDS and self.radio.playing and self.state == "idle" and not self.meeting \
                        and not self.alarm:
                    threading.Thread(target=self._media_word, args=(fin.strip(),), daemon=True).start()
                self._pending_media_stop = 0.0

            p = self.vad.prob(frame)
            due = getattr(self, "_wake_tone_due", 0.0)
            if due and ((not in_speech and p < 0.5) or silence >= 8 or now - due > 6):
                self._wake_tone_due = 0.0                      # после имени замолчали — теперь «слушаю»
                if self.state in ("listening", "thinking") and now - due <= 6:
                    self.play_tone("wake")
            a = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(a * a)))
            if self.state == "listening":                  # для журнала: насколько громко было, пока ждали вопрос
                self._listen_peak = max(self._listen_peak, rms)
                self._listen_vad = max(self._listen_vad, p)
            if self.state in ("idle", "listening") or not speaking:
                self._level(min(1.0, rms / 3000.0), "mic")
            if speaking and p < 0.6:
                echo.append(rms)                            # что остаётся от своего голоса после эхоподавления
            if speaking:
                spk_all.append(rms)
            elif spk_all:
                spk_all.clear()
            if not in_speech:
                preroll.append(frame)
                starts = starts + 1 if p > 0.5 else 0
                if starts >= 2:
                    in_speech, utt, silence, speech_frames = True, list(preroll), 0, 0
                    t0 = now - len(preroll) * FRAME_S
                    self.utt_id += 1
                    bs, quiet = 0, 0
                    self._pause_check(t0)
                    log.debug("речь началась (фраза %d, состояние %s)", self.utt_id, self.state)
            else:
                utt.append(frame)
                speech_frames += 1 if p > 0.5 else 0
                if p > 0.5:
                    self.mic_voice_t = now                    # суфлёр: «человек говорит» — для «замешкались» и пауз
                silence = silence + 1 if p < 0.35 else 0
                if speaking and barge in ("smart", "any_speech") and self.status["aec"] and now >= self._barge_name_until:
                    # Перебить можно просто начав говорить: через ~0,25 с речи ответ приглушается («слышу вас»),
                    # через ~0,8 с (any_speech — ~0,4 с) замолкает, а сказанное идёт как новый вопрос, без имени.
                    # Свой голос, просочившийся через эхоподавление, тише живой речи — порог считаем от него.
                    # №543: без настоящего AEC («Я в наушниках», а звук в колонках) своё эхо — тоже «речь»: порог —
                    # заметно громче того, что микрофон слышал, пока я говорила (до последней секунды — без вашей речи)
                    floor = max(220.0, 2.6 * float(np.median(echo)) if len(echo) > 10 else 400.0)
                    if not self.status.get("aec_real"):
                        floor = max(floor, barge_floor(list(spk_all)))
                    if p > 0.6 and rms > floor:
                        bs, quiet = bs + 1, 0
                    else:
                        quiet += 1
                        if quiet > 8:
                            bs = max(0, bs - 1)
                    if bs >= 8 and not ducked and self.player:
                        self.player.gain, ducked = 0.3, True
                        log.debug("слышу речь поверх ответа — приглушаю")
                    if bs >= (12 if barge == "any_speech" else 25):
                        self.barge_hit = self.utt_id           # эта фраза — новый вопрос
                        self.barge_speech = self.utt_id        # …возможно, с именем другого персонажа
                        bs, ducked = 0, False
                        self.interrupt("речь")
                if (speaking and barge != "off" and self.status["aec"] and speech_frames == 47
                        and now - self.wake_time > 3 and self.s.get("audio", "asr_wake")
                        and (self.wake_checker() or self.voiceprints.items)):
                    self.barge_sent = self.utt_id                 # 1.5 с речи поверх ответа — не имя ли это?
                    self.check_q.put(("barge", b"".join(utt), self.utt_id))
                if silence >= self._end_need(len(utt) * FRAME_S) or len(utt) * FRAME_S > 25:  # фраза длиннее 25 с — режем принудительно
                    log.debug("речь кончилась (фраза %d, %.1f с)", self.utt_id, len(utt) * FRAME_S)
                    in_speech, starts = False, 0
                    if ducked and self.player:                  # кашлянули, «угу» — продолжаем как было
                        self.player.gain, ducked = 1.0, False
                    self._on_utterance(b"".join(utt[:len(utt) - max(0, silence - 6)]), t0, now)   # хвост тишины — не больше 6 кадров
                    utt = []

            # ждали вопрос, окно истекло, а фразы нет — засыпаем и пишем в журнал, почему могли не услышать
            if (self.state == "listening" and now > self.follow_up_until and not in_speech
                    and now - self.wake_time > 4 and self.stt_q.empty()):
                sound = self._listen_peak >= 500 and self._listen_vad >= 0.6
                if sound:
                    log.info("🎤 Ждал вопрос — звук был (громкость %.0f, «это речь» %.2f), но фраза не сложилась: "
                             "вероятно, вокруг музыка или разговор", self._listen_peak, self._listen_vad)
                else:
                    log.info("🎤 Ждал вопрос — речи не услышал (громче всего: %.0f, уверенность «это речь»: %.2f; "
                             "обычный голос — от 500 и 0.6). Если вы говорили — микрофон слишком тихий или не тот",
                             self._listen_peak, self._listen_vad)
                self.set_state("idle")
                if self._listen_peak > 30:                  # №178: что-то было, но не вопрос — виджет скажет почему (тишину не трогаем)
                    self.emit("listen_none", sound=bool(sound), peak=round(self._listen_peak), speech=round(self._listen_vad, 2))
                self.play_tone("sleep")                    # «больше не слушаю» — ниже, чем «слушаю»: понятно без взгляда на экран

    def _on_utterance(self, pcm, t0, now):
        """Фраза закончилась (pcm — 16 бит моно, t0/now — её начало и конец по monotonic). Решаем, куда её:
        в распознавание как вопрос (stt_q), в проверку имени точной моделью или отпечатком (check_q),
        ранней проверке, которая уже идёт, — или отбросить (короткий звук, «стоп», чужой разговор, своё эхо)."""
        dur = len(pcm) / 2 / RATE
        self._media_stop_utt(pcm, now)
        if self.stop_utt:
            self.stop_utt = False
            if dur < 1.6:                                  # было только «стоп»/«хватит» — замолчали и спим до имени
                if getattr(self, "_stop_sleep", False):    # (иначе разговор рядом, начатый в те 3 с, ушёл бы в вопрос)
                    self._stop_sleep = False
                    self.go_sleep("стоп", media=False)
                return
            self._stop_sleep = False
            self.barge_hit = self.utt_id                   # «стоп, расскажи лучше…» — это новый вопрос
        if dur < 0.35:                                     # щелчок, кашель — не речь
            return
        pr = getattr(self, "prompter", None)
        if pr is not None and (pr.on or pr.enrolling is not None):   # суфлёр: фразы — во встречу или в запись голоса
            pr.feed_me(pcm)
            return
        if self.calib is not None:
            threading.Thread(target=self._calib_sample, args=(pcm,), daemon=True).start()
            return
        uid = self.utt_id
        if self.vosk_wake_check == uid:                   # имя от быстрого слуха под сомнением — решит точная модель
            if self.check_q.qsize() < 3:
                self.check_q.put(("utt", pcm, uid))
            else:
                self.vosk_wake_check = -1
            return
        if self.barge_sent == uid and self.barge_hit != uid:
            # по этой фразе уже идёт ранняя проверка — решит она; звук оставляем ей
            self.barge_done[uid] = pcm
            return
        if self.barge_hit == uid and getattr(self, "barge_cut", None):
            (pid, cut), self.barge_cut = self.barge_cut, None
            self._after_name(pid, pcm, cut)
            return
        if self.barge_speech == uid:
            self.barge_speech = -1
            if self.voiceprints.items:                     # перебили речью — а не позвали ли другого по имени?
                pid, end, _ = self.voiceprints.match(pcm, allowed=set(self.aliases))
                if pid:
                    self.emit("wake", phrase=pid)
                    self._after_name(pid, pcm, end)
                    return
        by_wake = self.wake_time >= t0 - 1.5 or self.barge_hit == uid      # имя прозвучало в этой фразе или прямо перед ней
        follow = now < self.follow_up_until + dur                          # фраза началась, пока ждали продолжения
        lf = getattr(self, "_last_final", None)
        if lf and lf.get("cut") == uid and self.state == "thinking":
            # человек договаривал: первая часть ещё у модели — склеиваем обе в один вопрос (первая отменится, в историю не попадёт)
            gap = np.zeros(int(RATE * 0.25), dtype=np.int16).tobytes()
            # «продолжение разговора» — только если оно было и у первой части: иначе склейка превращала отклонённую
            # фразу без имени (разговор людей рядом) в вопрос, и Лира отвечала сама (отчёт 11.10)
            pcm, by_wake, follow = lf["pcm"] + gap + pcm, lf["by_wake"], bool(lf.get("follow"))
            self.cancel_turn()
            log.info("⏸ Фраза продолжилась после паузы — склеиваю в один вопрос (%.1f с)", len(pcm) / 2 / RATE)
        own_tail = not by_wake and (self.state == "speaking" or t0 < self.last_speak_end + 0.1)
        if not (by_wake or follow) and self.meeting and self._meeting_mode() == "pause":
            return                                         # созвон: фразы коллег не проверяем (и не грузим процессор)
        if own_tail or not (by_wake or follow):
            # Явного имени Vosk не слышал. Возможно, это имя, которого нет в его словаре
            # («Девиар») — проверяем точной моделью, спокойно, без смены состояния.
            may_barge = self.status["aec"] and self.s.get("audio", "barge_in") != "off"
            if (self.s.get("audio", "asr_wake") and (self.wake_checker() or self.voiceprints.items)
                    and (not own_tail or may_barge)):
                if self.check_q.qsize() < 2:
                    self.check_q.put(("utt", pcm, uid))
            return
        if by_wake:
            # где в фразе прозвучало имя (с начала фразы, с): точная модель может его ослышать — тогда решаем по месту
            self._wake_off = (self.wake_time - t0) if self.wake_time else None
            self.wake_time = 0.0
        log.info("Фраза %.1f с → распознаю (%s)", dur, "по имени" if by_wake else "продолжение разговора")
        self._last_final = {"t": now, "uid": uid, "pcm": pcm, "by_wake": by_wake, "follow": follow}
        if getattr(self, "lat", None) is not None:
            self.lat.start(now)                            # «Голос без пауз»: отсюда меряем до первого звука
        self.stt_q.put((pcm, by_wake, follow))
        self.set_state("thinking")

    # ---------- пауза конца фразы под манеру речи ----------

    def _pause_apply(self):
        """Сколько кадров тишины — конец фразы: end_silence_ms плюс выученная добавка (если подстройка включена)."""
        ms = int(self.s.get("audio", "end_silence_ms") or 650)
        if self.s.get("audio", "end_silence_auto") is not False:
            ms += min(PAUSE_EXTRA_MAX, int(self.s.get("audio", "end_silence_extra") or 0))   # выученное раньше +900 — тоже до потолка
        self._end_frames = max(8, int(ms / 1000 / FRAME_S))
        return ms

    def _end_need(self, said_s):
        """Сколько кадров тишины — конец фразы, если человек говорит уже said_s секунд. №514 (04.11): «не успеваешь сказать
        больше трёх предложений — она отключается»: в долгой речи пауза между предложениями длиннее, чем после короткой
        команды. Короткие фразы — как раньше (быстрый ответ), после 4 с речи ждём на 0,35 с дольше, после 10 с — на 0,6 с."""
        base = getattr(self, "_end_frames", 20)
        for at, add in LONG_SPEECH:
            if said_s >= at:
                return base + int(add / FRAME_S)
        return base

    def _pause_check(self, t0):
        """Началась речь. Если прошлую фразу сочли законченной меньше 0,8 с назад, а ответа ещё нет (модель думает), —
        человек не договорил: ждать паузу дольше (+150 мс, до +600) и склеить обе части (_on_utterance).
        №226 (24.10): «после нескольких „перебил“ добавка дошла до 900 мс и сама не уменьшается — ассистент всё медленнее»:
        потолок +600 (вся пауза ~1,25 с), а тает она вдвое быстрее (_pause_ok); в студии — «вернуть обычную»."""
        lf = getattr(self, "_last_final", None)
        gap = 1.5 if lf and len(lf.get("pcm") or b"") / 2 / RATE >= LONG_SPEECH[-1][0] else 0.8   # №514: после долгой речи — до 1,5 с
        if not lf or lf.get("cut") or self.state != "thinking" or t0 - lf["t"] > gap or t0 < lf["t"] - 0.5:
            return
        lf["cut"] = self.utt_id
        if self.s.get("audio", "end_silence_auto") is False:
            return
        extra = min(PAUSE_EXTRA_MAX, int(self.s.get("audio", "end_silence_extra") or 0) + 150)
        self.s.update({"audio": {"end_silence_extra": extra}})
        ms = self._pause_apply()
        self._pause_debt = 0
        log.info("⏸ Похоже, перебил: вы продолжили через %.1f с — теперь жду конца фразы дольше: %d мс", max(0.0, t0 - lf["t"]), ms)
        self.emit("pause_learned", ms=ms, extra=extra)

    def _pause_ok(self):
        """Ответ на голосовой вопрос прошёл без обрыва — добавка понемногу тает: −20 мс за ответ (в настройки — по 50)."""
        lf = getattr(self, "_last_final", None)
        if not lf or lf.get("cut") or lf.get("ok") or time.monotonic() - lf["t"] > 180:
            return
        lf["ok"] = True
        extra = int(self.s.get("audio", "end_silence_extra") or 0)
        if extra <= 0 or self.s.get("audio", "end_silence_auto") is False:
            return
        self._pause_debt = getattr(self, "_pause_debt", 0) + 20
        if self._pause_debt >= min(50, extra):
            self.s.update({"audio": {"end_silence_extra": max(0, extra - self._pause_debt)}})
            self._pause_debt = 0
            self._pause_apply()

    # ---------- диктовка удержанием ----------

    def hold_start(self, back_ms=400, max_s=600):
        """Нажали и держат (кнопка-облик в виджете, пробел): всё, что звучит, — один вопрос, сколько бы ни длилось и какие бы
        паузы ни были; конец — когда отпустят (hold_end). Ответ, если звучал, замолкает. back_ms — сколько звука до
        вызова взять из кольца: интерфейс зовёт после ~0,3 с удержания, а говорить человек мог начать сразу."""
        # микрофон выключен — удержание разовое: эту фразу слушаем, а микрофон остаётся выключенным (отзыв 14.10:
        # «удерживаю аватарку, говорю, отпускаю — а микрофон включился, и приходится снова выключать»)
        if self.state in ("speaking", "thinking"):
            self.interrupt("удержание", follow=False)
        self.follow_up_until = 0.0
        n = max(0, min(len(self._mic_ring), int(back_ms / 1000 / FRAME_S)))
        self.hold = {"pcm": list(self._mic_ring)[len(self._mic_ring) - n:] if n else [], "t0": time.monotonic(), "max": max(5, int(max_s))}
        self._mic_kick_now()                           # №622: микрофон выключен и закрыт — открыть сейчас же
        log.info("🎙 Диктовка удержанием — говорите, отпустите — отправлю")
        self.set_state("listening")
        self.emit("hold", on=True)
        return True

    def hold_end(self, cancel=False, why=""):
        """Отпустили: звук целиком — в распознавание длинной записи и как вопрос (без имени). cancel — увели палец или
        Esc: ничего не отправляем."""
        h, self.hold = self.hold, None
        if h is None:
            return {"ok": False, "sec": 0}
        pcm = b"".join(h["pcm"])
        sec = round(len(pcm) / 2 / RATE, 1)
        self.emit("hold", on=False, sec=sec, cancel=bool(cancel))
        if cancel or sec < 0.4:
            log.info("🎙 Удержание %s (%.1f с)", "отменено" if cancel else "слишком короткое", sec)
            self.set_state("idle")
            self.play_tone("sleep")
            return {"ok": False, "sec": sec, "cancel": bool(cancel)}
        log.info("🎙 Удержание %.1f с → распознаю целиком%s", sec, " (предел длины)" if why == "limit" else "")
        self.set_state("thinking")
        self.stt_q.put((pcm, True, False, None, "hold"))
        return {"ok": True, "sec": sec}

    def _transcribe_long(self, stt, pcm):
        """Длинная запись (диктовка удержанием): распознаватели рассчитаны на фразы до ~20 с — режем по самым тихим
        местам на куски до 20 с и склеиваем текст. Кусок не распознался основным — им займётся Vosk."""
        a = np.frombuffer(pcm, dtype=np.int16)
        step = int(0.03 * RATE)                                  # окна по 30 мс
        n = len(a) // step
        if n * 0.03 <= 22:
            parts = [pcm]
        else:
            rms = np.sqrt(np.mean(a[:n * step].astype(np.float32).reshape(n, step) ** 2, axis=1))
            parts, start = [], 0
            while (n - start) * 0.03 > 20:
                lo, hi = start + int(12 / 0.03), start + int(20 / 0.03)   # режем между 12-й и 20-й секундой куска
                cut = lo + int(np.argmin(rms[lo:hi]))
                parts.append(a[start * step:cut * step].tobytes())
                start = cut
            parts.append(a[start * step:].tobytes())
        out = []
        for part in parts:
            try:
                t = stt.transcribe(part).strip()
            except Exception as e:  # noqa: BLE001
                spare = self._stt_spare(stt, e, "кусок диктовки")
                if spare is None:
                    continue
                t = spare.transcribe(part).strip()
            if t:
                out.append(t)
        return " ".join(out)

    # ---------- распознавание ----------

    def _stt_spare(self, stt, e, what=""):
        """Основной распознаватель не справился -> чем распознать эту фразу (или None) и, раз в 10 минут, — что случилось
        словами. №455 (01.11): свой сервер распознавания после переустановки отвечал 500 (на нём не хватало onnx_asr),
        а Лира молча переходила на маленький Vosk — «эйра сколько время» вместо «Лира, сколько время», и человек не
        понимал почему. Теперь запасной — точный GigaAM на этом компьютере, если он уже загружен, иначе Vosk; и
        подсказка: сервер ответил ошибкой — проверьте его или выберите другое распознавание."""
        g = getattr(self, "gigaam", None)
        spare = g if g is not None and g is not stt and getattr(g, "ready", False) else self.vosk_stt
        spare = None if spare is stt else spare
        log.warning("%s не распознал%s: %s%s", stt.name, " " + what if what else "", e,
                    f" — пробую {getattr(spare, 'name', 'запасной')}" if spare is not None else "")
        now = time.monotonic()
        if now - getattr(self, "_stt_err_at", -1e9) >= 600 or spare is None:
            self._stt_err_at = now
            self.note(stt_error_text(stt, e, spare))
        return spare

    def _stt_worker(self):
        """Поток stt: фразы из stt_q → текст → handle_text. Элемент очереди: (pcm, by_wake, follow[, pid]) —
        pid, если имя уже узнано по звуку и отрезано. Сбой основного распознавателя — повтор на Vosk."""
        while not self.stopping.is_set():
            item = self.stt_q.get()
            pcm, by_wake, follow = item[:3]
            forced = item[3] if len(item) > 3 else None
            held = len(item) > 4 and item[4] == "hold"
            stt = self.current_stt()
            t0 = time.monotonic()
            if held:
                text = self._transcribe_long(stt, pcm)
            else:
                try:
                    text = stt.transcribe(pcm).strip()
                except Exception as e:  # noqa: BLE001
                    spare = self._stt_spare(stt, e)
                    text = spare.transcribe(pcm).strip() if spare is not None else ""
            text = self._lang2(pcm, text)
            if getattr(self, "lat", None) is not None:
                self.lat.mark("stt")
            from vault import mask as _mask                # продиктованный для сейфа секрет — не в журнал
            log.info("📝 %s (%s, %d мс)", _mask(text) or "—", stt.name, (time.monotonic() - t0) * 1000)
            if not held and stt is not self.vosk_stt:
                try:
                    self._stt_timing(stt, (time.monotonic() - t0) * 1000)
                except Exception as e:  # noqa: BLE001
                    log.debug("скорость распознавания: %s", e)
            self.emit("hearing", text=text, by=stt.name, name="", ms=int((time.monotonic() - t0) * 1000), full=True)
            if held:
                self.handle_held(text)
            else:
                self.handle_text(text, by_wake, follow, forced, dur=len(pcm) / 2 / RATE)

    def _lang2(self, pcm, text):
        """Второй язык (lang2.py): «Понимать английскую речь» включено — английская ли это фраза? Решают две маленькие
        модели Vosk по уверенности; английская — текст у неё, а имя в начале («Патрик, …») — из русского текста.
        Модель ещё не скачана — запускаем скачивание и пока слышим только русский."""
        eng = getattr(self, "english", None)
        if eng is None or not self.s.get("stt", "english"):
            return text
        if not eng.ready:
            if eng.can_start():
                m = self._mirror("vosk_en") or {}
                eng.ensure(on_status=self.note, mirror=m.get("url"), mirror_sha=m.get("sha256"))
            return text
        try:
            lang, en_text, sc = eng.pick(pcm, self.vosk_model)
        except Exception as e:  # noqa: BLE001
            log.info("🌐 язык фразы не определился: %s", e)
            return text
        if sc:
            log.info("🌐 язык фразы: %s (английская %.2f×%d, русская %.2f×%d)", lang, sc[0][0], sc[0][1], sc[1][0], sc[1][1])
        if lang != "en" or not en_text.strip():
            return text
        from lang2 import strip_name
        pid, end = find_name(text, self.aliases) if text else (None, 0)
        if pid:
            names = list(self.aliases.get(pid, [])) + [self.personas.get(pid).get("name", "")]
            rest = strip_name(en_text, names)
            return (text[:end].rstrip(" ,.!?:;—-") + ", " + rest).strip(" ,") if rest else text[:end]
        return en_text

    def handle_held(self, text):
        """Текст диктовки удержанием: это точно вопрос ко мне — без проверки имени и «разговора не со мной». Ответ на
        «выполнить?» и на вопрос задачи — как обычно; имя в начале («Патрик, …») — переключает персонажа."""
        if not text:
            log.info("🎙 В удержании речи не расслышал")
            self.note("Речи не слышно — держите и говорите чуть громче или ближе к микрофону")
            self.set_state("idle")
            self.play_tone("sleep")
            return
        if self.pending_confirm and self._answer_confirm(text):
            return
        wt = self.tasks.waiting()
        if wt and time.monotonic() < self.task_answer_until:
            self.task_answer_until = 0.0
            self.tasks.answer(wt.id, text)
            self.emit("heard", text=text)
            self.announce("Передал в задачу.")
            return
        pid, end = find_name(text, getattr(self, "held_aliases", None) or self.aliases, strict=True)
        if pid:                                                # имя — первым словом: «Патрик, …» (любого персонажа)
            if pid != self.s.get("persona"):
                self.switch_persona(pid)
            rest = text[end:].lstrip(" ,.!?:;—-").strip()
            text = rest or text
        self.ask(text)
