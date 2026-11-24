"""Движок Dewiar — слух и голос: выбор движков распознавания и речи, скачивание моделей, аудиопоток
(VAD, слово запуска, нарезка фраз, перебивание), распознавание и поиск имени, созвоны, своё эхо.
Часть класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Потоки: audio (_audio_loop → _listen), stt (_stt_worker), name-check (_check_worker) и фоновые циклы.
Числа в кадрах: один кадр — FRAME_S (32 мс), т. е. 31 кадр ≈ 1 с. Готовая фраза уходит в handle_text,
дальше — ask() в engine_answer.py.

Части (чистое ядро, 1.0.16): ears_models — движки и модели, ears_mic — микрофон и поток audio, ears_listen — фразы,
паузы, удержание, распознавание, ears_name — имя и созвоны, ears_echo — «стоп» и своё эхо, ears_base — пороги и
помощники. Здесь — разбор фразы (handle_text), сигналы, перезапуск ядра и фоновые циклы."""
import contextlib

from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from stt import stt_error_text

from ears_base import barge_floor, BARGE_LOUD, LONG_WAKE_S, NO_MIC_ERR, rest_after, stop_mid_phrase, VOSK_RETRY_MIN  # noqa: F401 — прежние имена на месте
from ears_models import ModelsMixin
from ears_mic import MicMixin
from ears_listen import ListenMixin
from ears_name import NameMixin
from ears_echo import EchoMixin



# «не тебе», «это не тебе», «я не с тобой», «не к тебе», «я не тебя звал» — коротко, целиком (не «расскажи, почему не тебе…»)
NOT_ME_RX = re.compile(r"^(?:(?:да|нет|ой|это|я|ну)\s+){0,2}не\s+(?:тебе|к\s+тебе|с\s+тобой|тебя\s+звал[аи]?|тебя)"
                       r"(?:\s+(?:говорю|говорил[аи]?|сказал[аи]?|звал[аи]?|обращаюсь|обращался|обращалась))?[\s.!,]*$")

class AudioMixin(ModelsMixin, MicMixin, ListenMixin, NameMixin, EchoMixin):
    # ---------- перезапуск и фоновые циклы ----------

    def restart_core(self, delay=1.5):
        """Перезапуск ядра через delay секунд (например, после восстановления из копии). Под systemd (есть INVOCATION_ID) —
        выход с кодом 75, служба поднимет заново; иначе — маленький процесс-посредник ждёт (до 30 с), пока освободится
        порт моста, и запускает ядро с теми же аргументами, а этот процесс сразу выходит."""
        import sys as _sys

        def go():
            time.sleep(delay)
            if os.environ.get("INVOCATION_ID"):
                log.info("Перезапуск ядра (служба поднимет заново)")
                os._exit(75)
            code = ("import socket,subprocess,sys,time\n"
                    "for _ in range(60):\n"
                    " s=socket.socket()\n"
                    " try:\n  s.bind(('127.0.0.1', %d)); s.close(); break\n"
                    " except OSError: time.sleep(0.5)\n"
                    "subprocess.Popen(sys.argv[1:], close_fds=True)\n") % self.bridge.port
            # Windows: DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW — посредник переживёт выход ядра
            flags = 0x00000008 | 0x00000200 | 0x08000000 if os.name == "nt" else 0
            subprocess.Popen([_sys.executable, "-c", code, _sys.executable] + _sys.argv, close_fds=True,
                             start_new_session=os.name != "nt", creationflags=flags)
            log.info("Перезапуск ядра")
            os._exit(0)
        threading.Thread(target=go, daemon=True).start()

    def _calendar_loop(self):
        """Календари Google/Яндекс: обновлять раз в 30 минут; за N минут до встречи — напомнить."""
        told, last = set(), 0.0
        tick = float(os.environ.get("DEWIAR_CAL_TICK") or 30)      # шаг проверки, с; тесты ставят меньше
        self.stopping.wait(min(20, tick))
        while not self.stopping.is_set():
            try:
                if self.calendars.items() and time.monotonic() - last > 1800:
                    last = time.monotonic()
                    self.calendars.refresh()
                    self.emit("calendars", **self.calendars.public())
                mins = int(self.s.get("calendars", "remind_minutes") or 0)
                if mins > 0 and self.calendars.items():
                    now = datetime.now()
                    for e in self.calendars.events(now, now + timedelta(minutes=mins + 1)):
                        key = (e["cid"], e["title"], e["start"].isoformat())
                        if e["allday"] or key in told or e["start"] < now:
                            continue
                        told.add(key)
                        left = max(1, round((e["start"] - now).total_seconds() / 60))
                        text = f"{e['title']}" + (f", {e['place']}" if e.get("place") else "")
                        from when import span                # №563: «через 1 ч 27 мин», а не «через 87 минут»
                        self.push(f"📅 Через {span(left)} — {e['start']:%H:%M}", text)
                        if self.state == "idle" and not self.meeting:
                            self.announce(f"Через {span(left, voice=True)}: {e['title']}.")
            except Exception as e:  # noqa: BLE001
                log.warning("Календари: %s", e)
            self.stopping.wait(tick)

    def _task_guard_loop(self):
        """№551: задача, шаг которой молчит вдвое дольше порога, или час без единого пункта плана — на паузу с понятной
        причиной (taskguard.py), а не «висит 2 часа». Раз в 30 с."""
        import taskguard
        tick = float(os.environ.get("DEWIAR_TASK_GUARD_TICK") or 30)
        while not self.stopping.wait(tick):
            try:
                for tid, why in taskguard.check(self):
                    log.info("⏸ Задача %s на паузе: %s", tid, why)
            except Exception:  # noqa: BLE001
                log.warning("сторож задач", exc_info=True)

    def _auto_backup(self):
        """Поток backup: раз в неделю — тихая резервная копия; хранятся 4 последние (backup.py). Пароль слепка
        запомнен на этом компьютере — закрытая и полная (с сейфом), иначе — без сейфа и паролей. Проверяем раз в 6 часов."""
        from backup import default_dir, due
        self.stopping.wait(600)                          # не в момент запуска
        while not self.stopping.is_set():
            try:
                if self.s.get("backup", "auto") is not False:
                    folder = self.s.get("backup", "dir") or str(default_dir())
                    if due(self.backup.last_auto(folder)):
                        low_priority()
                        self.backup.make(folder, password=self.backup.pw_get(), auto=True)
            except Exception as e:  # noqa: BLE001
                log.warning("Автокопия не сделана: %s", e)
            self.stopping.wait(6 * 3600)


    STOP_FORMS = {"перестаньте", "замолчите", "прекратите", "остановитесь", "помолчите", "хватит", "стоп", "stop"}

    def handle_text(self, text, by_wake, follow, forced=None, dur=None):
        """Распознанная фраза → что делать: эхо — пропустить; ответ на «выполнить?» или на вопрос задачи;
        имя + вопрос → ask(); имя + «стоп» → уснуть; продолжение разговора → ask(); иначе ложное срабатывание.
        by_wake — имя слышали по звуку, follow — шло «продолжение разговора», forced — pid, если имя уже отрезано,
        dur — длина фразы, с."""
        if text and not forced and self._is_self_echo(text):
            self._echo_heard(text)
            return
        self._barge_snap = None                            # перебили по-настоящему — прежний ответ не договариваем
        if self._intro_ear is not None and self._intro_take(text, forced):
            return                                         # знакомство проверяет микрофон — фраза ему
        if forced:
            # имя уже узнано по звуку и отрезано; если распознаватель всё же написал его — уберём
            pid, end = find_name(text, self.aliases) if text else (None, 0)
            rest = text[end:].lstrip(" ,.!?:;—-").strip() if pid else text.strip()
            if len(re.sub(r"\W", "", rest)) < 2:
                self.listen_for_command()
            else:
                self.ask(rest)
            return
        if self.pending_confirm and text and self._answer_confirm(text):
            self.set_state("thinking")
            return
        wt = self.tasks.waiting() if text else None        # задача задала вопрос — фраза без имени идёт ей в ответ
        if wt and time.monotonic() < self.task_answer_until and not find_name(text, self.aliases)[0]:
            self.task_answer_until = 0.0
            self.tasks.answer(wt.id, text)
            log.info("Ответ в задачу «%s»: %s", wt.title, text)
            self.emit("heard", text=text)
            self.announce("Передал в задачу.")
            return
        if text and (by_wake or follow) and NOT_ME_RX.search(_norm(text)):
            # «не тебе», «я не с тобой» (владелец 19.11: учиться на «не тебе») — звали не меня: молча засыпаю, в счёт,
            # минуту не откликаюсь на голос
            if getattr(self, "lat", None) is not None:
                self.lat.drop()
            self.follow_up_until = 0.0
            self._wake_was_false("«" + text.strip()[:30] + "»")
            self.set_state("idle")
            self.play_tone("sleep")
            return
        pid, end = find_name(text, self.aliases) if text else (None, 0)
        if pid and by_wake:
            self._voice_turn_t = time.monotonic()           # ответ начат по голосу — «стоп» в первые секунды в счёт
        if not pid and by_wake and dur is not None and dur <= 1.6 and len(text.split()) <= 2 and self._name_like(text):
            # Быстрый слух услышал имя, а точная модель в короткой фразе ослышалась («Игрова», «Элла» вместо «Эва»):
            # это и было имя. Слушаем вопрос, а не гаснем и не отправляем «Эллу» модели как вопрос.
            spotted = self.personas.wake_map(kids=True).get(getattr(self, "_wake_phrase", ""))
            if spotted:
                log.info("🎤 Имя «%s» слышно, распознано как «%s» — слушаю вопрос", self._wake_phrase, text or "—")
                if spotted != self.s.get("persona"):
                    self.switch_persona(spotted)
                self.listen_for_command()
                return
        if not pid and by_wake and text and dur is not None and dur > 1.6:
            pid, end = self._wake_misheard(text, dur)
        if pid:
            if pid != self.s.get("persona"):
                self.switch_persona(pid)
            rest = text[end:].lstrip(" ,.!?:;—-").strip()
            word = _norm(re.sub(r"[^\w ]", "", rest)).strip()
            word = stop_word(word) or word if " " not in word else word      # «Лира, Ctop» → «стоп»
            if thanks_phrase(rest):                          # «Лира, спасибо» — «Пожалуйста!» и сон
                self._thanks(rest)
            elif word in STOP_WORDS or is_sleep_phrase(rest):
                self.go_sleep(word, media=False)
                if word in MEDIA_STOP:
                    threading.Thread(target=self._media_stop_word, args=(word, True), daemon=True).start()
            elif len(re.sub(r"\W", "", rest)) < 2:
                self.listen_for_command()
            else:
                self.ask(rest)
        elif follow and text:
            ws = _norm(re.sub(r"[^\w ]", " ", text)).split()
            last = stop_word(ws[-1]) if ws else None       # «…Пауза.», и ослышанное «…Ctop.»
            if last and last not in {"всё", "все", "пока", "спасибо", "спасиб", "благодарю"}:
                self.go_sleep(last, media=False)       # «…Вроде я её не вызывал. Пауза.» — это «стоп», а не вопрос
                return
            long_ = (dur is not None and dur > FOLLOW_MAX_S) or len(ws) > FOLLOW_MAX_WORDS
            if self.s.get("audio", "follow_long"):      # №226: «рассказ секунд на 10 теряется» — человек сам выбрал: длинное тоже мне
                long_ = False
            named = name_inside(text, self.aliases)
            # позвали по имени и ждём вопрос («Лира» → «Слушаю») — это вопрос мне, какой бы длинный ни был (пакет 22.10,
            # №182/№183: «пропадает, не дослушав вопрос»: 15-секундный вопрос после имени принимался за разговор рядом)
            invited = time.monotonic() < getattr(self, "_invited_until", 0.0)
            self._invited_until = 0.0
            if long_ and not named and not invited and not addressed(text):
                # без имени, долго и много слов — это разговор людей рядом, а не продолжение со мной (отчёт 11.10:
                # «как только кто-то рядом — она сама вклинивается в беседу»). Слушаю дальше только по имени.
                log.info("Продолжение разговора: длинная фраза без имени (%.1f с, %d слов) — похоже, говорят не со мной",
                         dur or 0.0, len(ws))
                self.follow_up_until = 0.0
                self.set_state("idle")
                if not getattr(self, "_long_hint", False):     # человек думает, что ассистент «уснул» (отчёт 18.10)
                    self._long_hint = True
                    self.note("Длинную фразу без имени я приняла за разговор рядом и не ответила. Если это было мне — "
                              "начните с имени или попросите: «расскажи…», «найди…».", ttl=45)   # №981: не висит весь день
                return
            if long_:
                log.info("Продолжение разговора: длинная фраза — %s", "имя внутри фразы" if named else
                         "вопрос после имени" if invited else "просьба ко мне")
            self.ask(text)
        else:
            if getattr(self, "lat", None) is not None:
                self.lat.drop()
            if by_wake:
                log.info("Ложное срабатывание: имени во фразе нет (%d слов)", len(text.split()))
                log.debug("Ложное срабатывание — фраза: «%s»", text)
            back = "listening" if time.monotonic() < self.follow_up_until else "idle"
            self.set_state(back)
            if back == "idle" and time.monotonic() - getattr(self, "_wake_tone_at", 0.0) < 15:
                self.play_tone("sleep")                    # звучало «слушаю», а вопроса не было — так же ясно «не слушаю»

    def play_tone(self, kind):
        """Короткий сигнал состояния. Вывод для сигналов держится открытым (ToneOut): открывать звук каждый раз —
        это заметная задержка, и «слушаю» звучало бы позже, чем человек договорил имя."""
        if not self.s.get("audio", "sounds") or self.player is None or self.state == "speaking":
            return
        out = getattr(self, "_tone_out", None)
        if out is None or out.device != self.player.device:
            out = self._tone_out = ToneOut(self.player.device, null=self.null_player)
        out.play(tone(kind))
