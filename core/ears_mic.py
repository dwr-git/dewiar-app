"""Слух — микрофон (часть Engine, чистое ядро 1.0.16): открыть микрофон и динамик (эхоподавление), поток audio с
переоткрытием после сбоя, микрофон выключен или занят камерой, сон Windows, «микрофон молчит», Bluetooth-гарнитура."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
import contextlib
from ears_base import NO_MIC_ERR
import ears_base as EB  # подменяемые в проверках имена — через основу


class MicMixin:
    # ---------- аудиопоток ----------

    def _open_audio(self):
        """Открывает микрофон и динамик. С эхоподавлением (AEC) слушаем его источник и играем в его приёмник,
        иначе — выбранные устройства напрямую. status["aec"] — можно ли слушать во время своего ответа."""
        if not getattr(self, "_out_checked", False):
            self._out_checked = True
            try:
                self._out_crash_check()
            except Exception:  # noqa: BLE001 — проверка не должна мешать слуху
                log.debug("проверка вывода звука", exc_info=True)
        a = self.s.get("audio")
        if self.wav_input:
            use_aec = os.environ.get("DEWIAR_ASSUME_AEC") == "1"      # тесты: в файле нет эха
        else:
            # №370 (28.10, Linux Mint, веб-камера C920): эхоподавление отдавало одни нули и после переоткрытия — тогда до
            # перезапуска программы слушаем микрофон напрямую (_aec_bypass ставит _mic_zero_step)
            use_aec = a["echo_cancel"] and not getattr(self, "_aec_bypass", False) and self.aec.setup(a["input"], a["output"])
        # №339: Bluetooth-наушники (EchoCancel.bt) — как «Я в наушниках»: эха нет, перебивать можно
        headphones = (bool(a.get("headphones")) or bool(getattr(self.aec, "bt", False) and not self.wav_input)) and not use_aec
        self.status["aec"] = bool(use_aec) or headphones        # «можно слушать во время ответа»: в наушниках эха нет
        self.status["headphones"] = headphones
        # №543: «наушники» — это слово человека, а не проверенное эхоподавление (Windows, звук шёл в колонки
        # MacBook). Без настоящего AEC перебить речью можно только заметно громче своего голоса в микрофоне
        self.status["aec_real"] = bool(use_aec)
        self.capture = Capture(device=AEC_SOURCE if use_aec else a["input"], wav_path=self.wav_input,
                               realtime=True)
        if self.player is None:                  # голос — и без микрофона: напечатанный вопрос получит ответ вслух
            self.player = Player(device=a["output"], on_level=lambda v: self._level(v, "voice"), null=self.null_player)
        self.status["input"] = self.capture.open()
        dev = AEC_SINK if use_aec else a["output"]
        if self.player is None or self.player.device != dev:
            self.player = Player(device=dev, on_level=lambda v: self._level(v, "voice"), null=self.null_player)
        log.info("Микрофон: %s; эхоподавление: %s", self.status["input"], "да" if use_aec else "нет")
        self.emit("status", status=self.status)

    def _out_crash_check(self, mark=None):
        """№521, №523 (04.11): ядро обрывалось, как только начинал звучать голос (вывод — HDMI монитора), без строчки в
        журнале. Метка audio_io._mark_out осталась от прошлого запуска — значит, он оборвался посреди звука: пишем это в
        журнал (видно в отчёте), а второй раз подряд через одно и то же выбранное устройство — переключаем звук на
        устройство по умолчанию и говорим об этом. Нормальный запуск (метки нет) сбрасывает счёт."""
        import audio_io
        mark = mark or (STATE_DIR / "audio_out.live")
        dev = audio_io.out_crash_marker(mark)
        if not getattr(self, "null_player", False) and not getattr(self, "wav_input", None):
            audio_io.OUT_MARK[0] = mark
        n = int(self.s.get("audio", "out_crash") or 0)
        if dev is None:
            if n:
                self.s.update({"audio": {"out_crash": 0}})
            return None
        cur = self.s.get("audio", "output") or ""
        n += 1
        log.warning("🔊 Прошлый запуск ядра оборвался, пока звучал голос (вывод: %s) — %d-й раз подряд", dev or "по умолчанию", n)
        if n >= 2 and cur and dev == cur:
            self.s.update({"audio": {"output": "", "out_crash": 0, "out_crash_dev": cur}})
            log.warning("🔊 Звук — на устройство по умолчанию вместо «%s»", cur)
            self.note(f"Программа дважды закрылась, пока звучал голос через «{cur}», — переключила звук на устройство по "
                      "умолчанию. Вернуть можно в студии → «Звук и поведение» → «Динамики».")
            return "switched"
        self.s.update({"audio": {"out_crash": n}})
        return "counted"

    def _audio_loop(self):
        """Поток audio: держит микрофон открытым и переоткрывает его после сбоя или restart_audio;
        нет микрофона — ждём подключения, отвечать можно по написанному. Для wav-файла (тесты) — один проход и «eof»."""
        last_err = None
        while not self.stopping.is_set():
            if self._mic_rest_due():
                self._mic_rest()                     # №622: выключен ещё до открытия (замок «только кнопка», текстовый режим)
                continue
            try:
                self._open_audio()
                last_err = None
                self._listen()
            except Exception as e:  # noqa: BLE001
                no_mic = any(s in str(e) for s in NO_MIC_ERR)
                if str(e) != last_err:              # подробно — один раз; повторы (нет микрофона) — строкой
                    if no_mic:
                        log.warning("Микрофон не найден (%s) — жду, пока его подключат", e)
                    elif isinstance(e, ImportError) and "sounddevice" in str(e):
                        # пакет 24.10: «No module named 'sounddevice'» на 2 компьютерах. На Linux это значит: нет ни libpulse,
                        # ни parec/pacat (звук без PulseAudio/PipeWire-Pulse); на Windows — файлы звука убрал антивирус
                        why = ("установите звуковую прослойку: sudo apt install pipewire-pulse (или pulseaudio-utils) и перезапустите Dewiar"
                               if os.name != "nt" else
                               "часть файлов Dewiar убрал антивирус — запустите установщик Dewiar ещё раз (он вернёт их)")
                        log.warning("Нет доступа к звуку: %s — %s", e, why)
                        self.note("Не слышу микрофон и не могу говорить: " + why + ". Писать мне можно и сейчас.")
                    elif disk_full(e):
                        log.warning("Нет места на диске (%s) — звук и настройки не работают", e)
                    else:
                        log.exception("Сбой аудиопотока")
                    last_err = str(e)
                else:
                    log.debug("Сбой аудиопотока (повтор): %s", e)
            if self.capture:
                self.capture.close()
            if self.wav_input:
                self.emit("eof")
                return
            if not self.stopping.is_set():
                if getattr(self, "_mic_off", False):
                    self._mic_off = False
                    self._mic_rest()                 # №622: микрофон выключили — устройство свободно до включения
                elif getattr(self, "_mic_asleep", False):
                    log.info("💤 Отпускаю микрофон — компьютер может уснуть; тронут мышь или клавиатуру — снова слушаю")
                    from sleepguard import idle_seconds
                    while not self.stopping.is_set():
                        i = idle_seconds()
                        if i is None or i < 5:
                            break
                        self.stopping.wait(2)
                    self._mic_asleep = False
                    log.info("💤 Снова слушаю микрофон")
                elif self.restart_audio.is_set():
                    self.restart_audio.clear()
                    self.aec.teardown()
                elif last_err and any(s in last_err for s in NO_MIC_ERR):
                    if os.name == "nt":             # подключат микрофон — увидим его без перезапуска (№165)
                        try:
                            from audio_io import sd_refresh
                            sd_refresh()
                        except Exception:  # noqa: BLE001
                            pass
                    self.note("Микрофон не найден — подключите его или выберите в студии («Звук и поведение» → «Микрофон»)"
                              + ("; в Windows проверьте «Параметры → Конфиденциальность → Микрофон» — доступ для приложений"
                                 if os.name == "nt" else "") + ". Пока можно писать в виджете.")
                    self.stopping.wait(5)
                elif last_err and disk_full(last_err):
                    # отчёт №395 (29.10): диск заполнен — Python не может создать даже временный файл, а человек видел
                    # «Микрофон недоступен» и думал про микрофон. Говорим как есть и ждём, пока место освободят
                    self.note(disk_full_note())
                    self.stopping.wait(10)
                else:
                    self.note("Микрофон недоступен — переподключаюсь…")
                    time.sleep(2)

    def _mic_rest_due(self):
        """№622, идея №151 (07–08.11): «микрофон выключен кнопкой, а Windows показывает значок микрофона, и мессенджеры
        пишут „занят другой программой“». Раньше выключенный микрофон только глушили — поток оставался открытым. Теперь
        выключен (кнопка, «Отдых», текстовый режим, замок «только кнопка») и не держат «говорить» — поток закрываем совсем.
        audio.mic_release = false — по-старому (держать открытым). Файл вместо микрофона (проверки) — не трогаем."""
        if self.wav_input:
            return False
        if getattr(self, "_mic_pause", 0):
            return True                             # идея №165: камера снимает (mic_paused)
        if not self.muted or self.hold is not None or self._mute_pass:
            return False
        return self.s.get("audio", "mic_release") is not False

    def _mic_kick_now(self):
        """Включили микрофон, нажали «говорить» или начали удержание — открыть микрофон сразу, не дожидаясь опроса."""
        ev = getattr(self, "_mic_kick", None)
        if ev is not None:
            ev.set()

    def _mic_rest(self):
        """Микрофон закрыт: ждём, пока его включат (или держат «говорить», или нажали «говорить» для одной фразы), —
        тогда _audio_loop откроет его заново (доли секунды). Кольцо последних кадров очищаем: удержание после включения
        не должно начаться со звука минутной давности. Смена устройства в студии, пока микрофон выключен, — просто
        примется при открытии."""
        self._mic_ring.clear()
        paused = bool(getattr(self, "_mic_pause", 0))
        log.info("🎤 %s — отпускаю микрофон: другие программы могут им пользоваться",
                 "Снимок с камеры" if paused else "Микрофон выключен")
        self.status["mic_free"] = True
        self.emit("status", status=self.status)
        ev = getattr(self, "_mic_kick", None) or threading.Event()
        while not self.stopping.is_set() and self._mic_rest_due():
            ev.wait(0.5)
            ev.clear()
            if self.restart_audio.is_set():
                self.restart_audio.clear()          # устройства сменили, пока выключен, — откроем уже новое
                self.aec.teardown()
        self.status["mic_free"] = False
        if not self.stopping.is_set():
            log.info("🎤 Открываю микрофон снова")

    @contextlib.contextmanager
    def mic_paused(self, why="камера", wait=2.0):
        """Идея №165 (08.11): веб-камера с микрофоном на одном USB — пока камера снимает, общий драйвер «вешает» поток
        микрофона, и он отваливается до перезапуска драйвера. На время снимка микрофон закрываем (как выключенный) и
        открываем после — только если это и правда одно устройство (mic_shares_camera). wait — сколько ждать, пока поток
        закроется (один кадр — 32 мс; чтение из драйвера — до 2 с)."""
        self._mic_pause = getattr(self, "_mic_pause", 0) + 1
        try:
            end = time.monotonic() + wait
            while time.monotonic() < end and self.capture is not None and not self.status.get("mic_free"):
                time.sleep(0.03)
            yield
        finally:
            self._mic_pause = max(0, getattr(self, "_mic_pause", 1) - 1)
            self._mic_kick_now()

    def _sleep_due(self):
        """Отпустить ли микрофон, чтобы Windows могла уснуть (идея №70; sleepguard.py). Настройка audio.let_sleep."""
        if self.s.get("audio", "let_sleep") is False:
            return False
        from sleepguard import idle_seconds, release_due, standby_seconds
        radio = getattr(self, "radio", None)
        busy = (self.turn is not None or self.state != "idle" or bool(getattr(self, "alarm", None)) or self.hold is not None
                or bool(radio is not None and radio.playing) or bool(getattr(getattr(self, "prompter", None), "on", False))
                or bool(getattr(self, "meeting", None)))
        return release_due(idle_seconds(), standby_seconds(), time.monotonic() - float(getattr(self, "mic_voice_t", 0) or 0), busy)

    def _mic_silent(self, exact=True):
        """Микрофон открыт, а звука нет: ровные нули (exact) — в Windows так выглядит запрет доступа к микрофону;
        почти нули — выбран виртуальный микрофон (HitPaw, VB-Cable, Voicemod…) или громкость записи на нуле.
        Подбирает подсказку по списку устройств и показывает её (заметка, уведомление, отчёт о проблеме);
        в Windows при запрете доступа сразу открывает нужную страницу параметров."""
        from audio_io import MAPPER_RX as mapper, VIRTUAL_MIC_RX as virt     # №520: и Steam Streaming Microphone
        try:
            srcs = [d for d in EB.list_devices() if d.get("kind") == "source"]
        except Exception:  # noqa: BLE001
            srcs = []
        cur = self.s.get("audio", "input") or ""
        names = [(d.get("description") or d.get("name") or "") for d in srcs if not mapper.search(d.get("description") or d.get("name") or "")]
        fake = [n for n in names if virt.search(n)]
        real = [n for n in names if not virt.search(n)]
        rdp = re.compile(r"удал[её]нн\w* аудио|remote audio", re.I)
        if os.name == "nt" and (rdp.search(cur) or (real and all(rdp.search(n) for n in real))):
            # №780 (16.11): «через удалённый рабочий стол не могу поднять громкость микрофона больше 1 — ползунок не двигается»:
            # «Удалённое аудио» — микрофон того компьютера, с которого подключились; уровень Windows здесь не поднимет
            text = ("Микрофон молчит: вы подключены через удалённый рабочий стол, и «Удалённое аудио» — это микрофон того "
                    "компьютера, с которого вы подключились. Громкость здесь не меняется — нужно разрешить запись при "
                    "подключении: «Подключение к удалённому рабочему столу» → «Показать параметры» → «Локальные ресурсы» → "
                    "«Удалённый звук: Параметры» → «Запись с этого компьютера», и переподключиться. Уровень микрофона — на "
                    "своём компьютере.")
        elif fake and not real:
            text = (f"Микрофон молчит: Windows видит только виртуальный микрофон «{fake[0]}» — настоящего нет. Подключите микрофон "
                    "(или включите его в «Параметры → Система → Звук»), затем выберите его в студии → «Звук и поведение» → «Микрофон»." if os.name == "nt" else
                    f"Микрофон молчит: есть только виртуальный «{fake[0]}». Подключите настоящий и выберите его в студии → «Звук и поведение» → «Микрофон».")
        elif virt.search(cur) or (not cur and fake and os.name == "nt"):
            text = (f"Микрофон почти ничего не слышит — похоже, слушаю виртуальный «{cur or fake[0]}». "
                    f"Выберите настоящий микрофон{' («' + real[0] + '»)' if real else ''} в студии → «Звук и поведение» → «Микрофон».")
        elif exact and os.name == "nt":
            text = ("Микрофон молчит: Windows не даёт программам его слушать. Откройте «Параметры → Конфиденциальность и защита → "
                    "Микрофон» и включите «Доступ к микрофону» и «Разрешить классическим приложениям доступ к микрофону». "
                    "Или выберите другой микрофон в студии → «Звук и поведение» → «Микрофон».")
        elif exact and sys.platform == "darwin":
            text = ("Микрофон молчит: Mac не даёт Dewiar его слушать. Откройте «Системные настройки → Конфиденциальность и "
                    "безопасность → Микрофон» и включите Dewiar, затем перезапустите Dewiar (значок в строке меню → «Выйти», "
                    "и откройте снова).")
        elif exact:
            text = "Микрофон молчит — проверьте, что он включён и не выключен звук записи, или выберите другой в студии → «Звук и поведение» → «Микрофон»."
        else:
            text = ("Микрофон почти ничего не слышит: громкость записи на нуле или выбран не тот микрофон. Проверьте уровень "
                    "микрофона в настройках звука системы или выберите другой в студии → «Звук и поведение» → «Микрофон».")
            # отчёт №400 (29.10): два микрофона (HyperX QuadCast S и встроенный Realtek), слушаем «по умолчанию» — почти
            # тишина. Называем, какие есть, и у USB-микрофонов с кнопкой выключения на корпусе — про неё
            if not cur and len(real) > 1:
                text = (f"Микрофон почти ничего не слышит. Слушаю микрофон по умолчанию, а их у вас {len(real)}: "
                        + ", ".join(f"«{n}»" for n in real[:3]) + ". Выберите тот, в который говорите, в студии → «Звук и "
                        "поведение» → «Микрофон» — или проверьте уровень записи в настройках звука системы.")
            # №520 (04.11): выбран «Graphite 2 Wireless» — беспроводная гарнитура выключена или спит, а рядом USB-микрофон.
            # Называем выбранный и другие настоящие; у беспроводных — про питание и сопряжение
            elif cur and [n for n in real if n != cur]:
                others = [n for n in real if n != cur]
                wl = re.search(r"wireless|bluetooth|hands-?free|headset|гарнитур|airpods|buds|беспровод", cur, re.I)
                text = (f"Микрофон почти ничего не слышит: выбран «{cur}»" +
                        (" — если это беспроводная гарнитура, проверьте, что она включена, заряжена и подключена." if wl else ".") +
                        " Говорите в другой? У вас есть ещё: " + ", ".join(f"«{n}»" for n in others[:3]) +
                        " — выберите его в студии → «Звук и поведение» → «Микрофон».")
            # №527 (04.11): один микрофон — гарнитура, звук то есть, то нет: выключен кнопкой на ней
            elif len(real) == 1:
                text += (f" Если «{real[0]}» — гарнитура или веб-камера, проверьте, не выключен ли микрофон на ней самой "
                         "(кнопка на проводе или чашке, поднятая штанга).")
            mute = next((n for n in real if re.search(r"quadcast|yeti|fifine|seiren|elgato wave|nt-usb|podmic|maono|samson", n, re.I)), "")
            if mute:
                text += (f" У «{mute}» есть кнопка выключения на корпусе (у QuadCast — сенсор сверху): если он светится "
                         "красным или не светится — коснитесь её.")
        if not exact:
            # «почти тишина» бывает и в очень тихой комнате (массивы микрофонов с шумоподавлением AMD/Realtek отдают почти
            # цифровую тишину — №136, 20.10: тревога и автоотчёт после каждого перезапуска, а микрофон работал). Не чаще раза
            # в полчаса и после перезапуска тоже (время — в настройках)
            try:
                last = float(self.s.get("audio", "mic_hint_at") or 0)
            except (TypeError, ValueError):
                last = 0.0
            if time.time() - last < 1800:
                return
            try:
                self.s.update({"audio": {"mic_hint_at": int(time.time())}})
            except Exception:  # noqa: BLE001
                pass
        if not real or (fake and not real):                 # №876: настоящего микрофона нет — может, он и не нужен
            text += (" Микрофона нет и не будет? Включите «Текстовый режим» (студия → «Чат», внизу): Лира не будет его слушать "
                     "и не станет загружать распознавание — запуск быстрее.")
        self._mic_hint_at = time.monotonic()
        log.warning("🎤 %s от микрофона %s — %s (микрофоны: %s)", "15 с" if exact else "Минута", "полная тишина (нули)" if exact else "почти тишина (пик ≤ 3)",
                    text[:80], ", ".join(names) or "—")
        self.note(text)
        if not exact and getattr(self, "_mic_alive", False):
            return                                       # микрофон в этом запуске уже слышал — просто тихо: подсказка, без тревоги
        body = re.sub(r"^Микрофон молчит\s*[—:]\s*", "", text)          # заголовок уже «Микрофон молчит» — без повтора
        self.push("Микрофон молчит", body[:1].upper() + body[1:], telegram=False)
        self.report_problem("mic_silent", "микрофон молчит: " + ("нули" if exact else "почти тишина") + f"; устройства: {', '.join(names)[:200]}")
        if exact and os.name == "nt" and not fake:
            try:
                os.startfile("ms-settings:privacy-microphone")  # noqa: S606 — сразу открыть нужную страницу настроек
            except OSError:
                pass
        if exact and sys.platform == "darwin" and not fake and not os.environ.get("DEWIAR_FAKE_MIC"):
            try:                                          # сразу нужная страница настроек Mac
                subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def _mic_zero_step(self, st, frame, now):
        """Кадр микрофона — не тишина ли подряд. Ровные нули (Windows запретил доступ, или поток застрял — после OBS) или
        «почти ничего» — пик ≤ 3 из 32767 (виртуальный микрофон, громкость записи на нуле): живой микрофон даже в тихой
        комнате шумит сильнее. Нули 5 с — сами переоткрываем микрофон и эхоподавление (отзыв 17.10: «OBS уже выключил,
        но она меня не слышит»), не чаще раза в 2 минуты; тишина 15 с — подсказка человеку (_mic_silent).
        st — {"since", "told", "all"} этого потока. -> "heal" (переоткрыть) или None."""
        zeros = not frame.strip(b"\x00")
        peak = 0 if zeros else int(np.abs(np.frombuffer(frame, dtype=np.int16).astype(np.int32)).max())
        if peak > 3:
            self._mic_alive = True                      # микрофон живой — «почти тишина» потом значит просто тихую комнату
            if st["told"]:
                self.note("")
                log.info("🎤 Микрофон снова слышно")
            st.update(since=None, told=False, all=True)
            return None
        if st["since"] is None:
            st.update(since=now, all=zeros)
            return None
        st["all"] = st["all"] and zeros
        # только в покое: во время ответа переоткрытие сняло бы эхоподавление вместе с её голосом, а в разговоре — оборвало бы его
        if st["all"] and not st["told"] and now - st["since"] > 5 and now - getattr(self, "_zero_heal_at", -1e9) > 120 \
                and getattr(self, "state", "idle") == "idle" and getattr(self, "hold", None) is None:
            healed = getattr(self, "_zero_heals", 0)
            self._zero_heal_at, self._zero_heals = now, healed + 1
            stt_ = getattr(self, "status", None) or {}
            if healed and stt_.get("aec") and not stt_.get("headphones") and not getattr(self, "_aec_bypass", False):
                # переоткрывали, а нули снова — виновато эхоподавление (№370): дальше слушаем микрофон напрямую
                self._aec_bypass = True
                log.warning("🎤 Нули и после переоткрытия — слушаю микрофон напрямую, без эхоподавления")
                self.note("Эхоподавление отдавало тишину — слушаю микрофон напрямую. Пока я говорю, лучше подождать конца "
                          "ответа (или наденьте наушники).")
            else:
                log.warning("🎤 Из микрофона идут одни нули — переоткрываю микрофон и эхоподавление")
            self.restart_audio.set()
            return "heal"
        if not st["told"] and now - st["since"] > (15 if st["all"] else 60):   # почти тишина — минута, а не 15 с (№136)
            st["told"] = True
            self._mic_silent(exact=st["all"])
        return None

    def _default_mic_moved(self):
        """Идея №134 (04.11): выбрано «Системный по умолчанию», Bluetooth-гарнитуру переподключили — Windows снова сделала её
        главной, а слух остался на прежнем микрофоне («не слышит, пока не поменяешь туда-обратно»). Раз в 3 с сверяем, какой
        микрофон сейчас по умолчанию и сколько их; сменился — переоткрываем слух (только в покое: ответ не обрываем).
        -> True, если пора переоткрыть."""
        cap = getattr(self, "capture", None)
        if cap is None or getattr(cap, "device", "") or getattr(cap, "wav_path", None) or getattr(cap, "def_sig", None) is None:
            return False
        if getattr(self, "state", "idle") in ("speaking", "thinking", "listening") or getattr(self, "hold", None) is not None:
            return False
        from audio_io import win_default_input
        now_sig = win_default_input()
        if now_sig is None or now_sig == cap.def_sig:
            return False
        log.info("🎧 Микрофон Windows по умолчанию сменился: %s → %s — слушаю новый", cap.def_sig[1] or "?", now_sig[1] or "?")
        cap.def_sig = now_sig
        return True
