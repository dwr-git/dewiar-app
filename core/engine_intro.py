"""Знакомство при первом запуске: персонаж (по умолчанию Лира) сам представляется голосом, проверяет микрофон,
показывает кнопки виджета и предлагает фразы попробовать. Без модели — текст готовый, говорит голос персонажа.

Запуск: сам — при первом запуске (настройка ui.intro == "", у прежних пользователей при обновлении ставится "done"),
когда виджет на связи и слух поднялся; заново — кнопкой «Познакомиться» (команда intro_start). Шаги идут событием
«intro» {step, …}: виджет подсвечивает кнопки и показывает фразы-кнопки, студия — ход знакомства.
Проверка микрофона: на время ожидания следующая распознанная фраза (с именем или без) не идёт модели, а достаётся
знакомству (handle_text → _intro_take); громкость с микрофона копится в пик (_level)."""
import os
import threading
import time

from engine_base import Turn, log
import re

YES_RX = re.compile(r"\b(да|давай|хочу|конечно|можно|ага|угу|хорошо|ладно|окей|ок)\b", re.I)
NO_RX = re.compile(r"\b(нет|не\s+надо|не\s+нужно|не\s+хочу|потом|не\s+сейчас)\b", re.I)
_NOT_NAME = {"привет", "здравствуй", "здравствуйте", "алло", "да", "нет", "лира", "патрик", "ок", "хорошо", "слышишь", "спасибо",
             "меня", "зовут", "я", "это", "микрофон", "проверка", "раз", "два", "три"}


def intro_name(text):
    """«Меня зовут Михаил», «Миша», «я Ольга», «зови меня Саша» -> «Михаил»; не похоже на имя — ""."""
    t = re.sub(r"[^\w\s-]", " ", str(text or "")).strip()
    m = re.search(r"(?:меня\s+зовут|зови(?:те)?\s+меня|можно\s+просто|я\s*[-—]?\s*это|^я)\s+([А-Яа-яЁё][А-Яа-яЁё-]{1,20})(?:\s+([А-Яа-яЁё][А-Яа-яЁё-]{2,20}))?", t, re.I)
    if m:
        w = [m.group(1)] + ([m.group(2)] if m.group(2) and not re.match(r"(?i)и|а|да|вот|ну", m.group(2)) else [])
    else:
        words = t.split()
        w = words if 1 <= len(words) <= 2 and all(re.match(r"[А-Яа-яЁё-]{2,20}$", x) for x in words) else []
    w = [x for x in w if x.lower() not in _NOT_NAME]
    return " ".join(x[:1].upper() + x[1:].lower() for x in w)[:40] if w else ""


def intro_city(text):
    """«В Минске», «Минск», «живу в Гродно» -> (город, как сказать в ответ: «в Минске» / «Минск»); не похоже — ("", "")."""
    t = re.sub(r"[^\w\s-]", " ", str(text or "")).strip()
    m = re.match(r"(?i)^(?:я\s+)?(?:живу\s+|сейчас\s+)?(в|во)\s+", t)
    t = re.sub(r"(?i)^(?:я\s+)?(?:живу\s+|сейчас\s+)?(?:в|во|из)\s+", "", t).strip()
    t = re.sub(r"(?i)^(?:город|г)\s+", "", t).strip()
    if not t or len(t) > 40 or len(t.split()) > 3 or NO_RX.search(t) or t.lower() in _NOT_NAME:
        return "", ""
    city = " ".join(x[:1].upper() + x[1:].lower() if i == 0 else x.lower() for i, x in enumerate(t.split()))
    return city, (f"{m.group(1).lower()} {city}" if m else city)


class IntroMixin:
    _intro_ear = None             # {"ev", "text", "peak"} — пока знакомство ждёт фразу
    _intro_probe = None           # {"n", "peak"} — уровень микрофона, пока знакомство говорит (есть ли микрофон вообще)
    _intro_running = False
    _intro_wait_s = 12.0          # сколько ждать фразу при проверке микрофона, с

    # ---------- запуск ----------

    def intro_auto(self):
        """Фоновый поток при старте: первый запуск — дождаться виджета и слуха (до 3 минут) и познакомиться."""
        if self.wav_input or getattr(self, "server", False):
            return
        if (self.s.get("ui", "intro") or "") != "":
            self._first_nudge_start()                     # познакомились, а спросить так и не спросили — мягко напомнить
            return
        end = time.monotonic() + 180
        while time.monotonic() < end and not self.stopping.is_set():
            ui_on = bool(getattr(getattr(self, "bridge", None), "clients", None))
            if ui_on and getattr(self, "_audio_thread", None) is not None:
                break
            time.sleep(1.0)
        if self.stopping.is_set() or (self.s.get("ui", "intro") or "") != "":
            return
        self.stopping.wait(2.5)                       # окна успели открыться и отрисоваться
        self.intro_start()

    def intro_start(self):
        """Начать знакомство (повторный вызов во время знакомства ничего не делает). -> True, если началось."""
        if self._intro_running:
            return False
        self._intro_running = True
        threading.Thread(target=self._intro_run, name="intro", daemon=True).start()
        return True

    def intro_stop(self):
        """«Пропустить»: замолчать, знакомство закончено."""
        if not self._intro_running:
            return False
        self._intro_stop = True
        ear = self._intro_ear
        if ear:
            ear["ev"].set()
        self.cancel_turn()
        return True

    # ---------- перехват фразы и громкости ----------

    def _intro_take(self, text, forced=None):
        """Из handle_text: знакомство ждёт фразу — забираем её себе. -> True, если забрали."""
        ear = self._intro_ear
        if ear is None or ear["ev"].is_set():
            return False
        if forced and not (text or "").strip():
            text = self.personas.get(forced)["name"]  # сказали только имя
        if not (text or "").strip():
            return False
        ear["text"] = text.strip()
        ear["ev"].set()
        self.emit("heard", text=ear["text"])
        return True

    def _intro_level(self, v, src):
        if src != "mic":
            return
        ear = self._intro_ear
        if ear is not None and v > ear["peak"]:
            ear["peak"] = v
        pr = self._intro_probe                          # пока знакомство говорит — есть ли у микрофона хоть какой-то шум
        if pr is not None:
            pr["n"] += 1
            pr["peak"] = max(pr["peak"], v)

    def _mic_absent(self):
        """Микрофона нет: ни одного входного устройства — или уровень всё время ровно ноль (у живого микрофона всегда есть
        шум; «цифровая тишина» — устройство есть, но в нём ничего нет, как «штатный» вход без подключённого микрофона)."""
        try:
            from audio_io import list_devices
            devs = list_devices()
            if devs and not any(d.get("kind") == "source" for d in devs):
                return True
        except Exception:  # noqa: BLE001
            pass
        pr = self._intro_probe or {}
        return pr.get("n", 0) >= 10 and pr.get("peak", 0.0) <= 0.0015

    # ---------- сам сценарий ----------

    def _intro_say(self, text, step, **extra):
        """Сказать фразу голосом персонажа и дождаться конца. -> False, если знакомство прервали."""
        if getattr(self, "_intro_stop", False):
            return False
        text = self._g(text)
        self.emit("intro", step=step, text=text, **extra)
        with self._turn_lock:
            self._cancel_locked()
            self.turn_n += 1
            turn = Turn(self.turn_n)
            self.turn = turn
        import queue
        q = queue.Queue()
        q.put(text)
        q.put(None)
        self.emit("answer", text=text, done=True)
        try:
            self._speak_worker(turn, q)
        except Exception as e:  # noqa: BLE001
            log.warning("знакомство: не сказала «%s»: %s", text[:40], e)
        with self._turn_lock:
            if self.turn is turn:
                self.turn = None
        if self.state == "speaking":
            self.set_state("idle")
        return not getattr(self, "_intro_stop", False) and not turn.cancel.is_set()

    def _intro_listen(self, seconds=None):
        """Ждать фразу без имени seconds секунд. -> (текст или "", пик громкости)."""
        seconds = seconds or self._intro_wait_s
        ear = {"ev": threading.Event(), "text": "", "peak": 0.0}
        self._intro_ear = ear
        self.follow_up_until = time.monotonic() + seconds
        self.set_state("listening")
        self.play_tone("wake")
        ear["ev"].wait(seconds)
        if not ear["text"] and ear["peak"] > 0.04 and not getattr(self, "_intro_stop", False):
            ear["ev"].wait(min(4.0, seconds))         # голос был — дадим распознавателю договорить
        self._intro_ear = None
        self.follow_up_until = 0.0
        if self.state == "listening":
            self.set_state("idle")
        return ear["text"], ear["peak"]

    def _intro_run(self):
        self._intro_stop = False
        if self.s.get("ui", "first_ask") is None:          # новенький: до первого вопроса — подсказки в виджете (0.74)
            self.s.update({"ui": {"first_ask": False}})
        try:
            self._intro_script()
        except Exception as e:  # noqa: BLE001
            log.warning("знакомство прервалось: %s", e)
        finally:
            self._intro_ear = None
            self._intro_probe = None
            self._intro_running = False
            if (self.s.get("ui", "intro") or "") != "done":
                self.s.update({"ui": {"intro": "done"}})
            self.emit("intro", step="done")
            self._first_nudge_start()

    # ---------- первый вопрос (0.74; воронка 30.10: 63 из 70 новых компьютеров без ответа ни разу ничего не спросили) ----------
    # Пока человек не спросил ни разу (ui.first_ask == False — ставится только новичкам, у прежних None), виджет держит
    # под портретом три фразы-кнопки (FIRST_TRY), а через FIRST_NUDGE_S тишины после знакомства персонаж один раз
    # мягко напомнит о себе голосом (ui.first_nudged). Первый вопрос — голосом, текстом или кнопкой — всё убирает.
    FIRST_NUDGE_S = 150

    def first_try(self):
        return ["Какая завтра погода?", "Напомни через 5 минут проверить чайник", "Что ты умеешь?"]

    def first_asked(self):
        """Человек спросил — подсказки больше не нужны."""
        if self.s.get("ui", "first_ask") is False:
            self.s.update({"ui": {"first_ask": True}})
            self.emit("first_ask", on=False)
            log.info("👋 Первый вопрос задан")

    def _first_nudge_start(self):
        if self.s.get("ui", "first_ask") is not False or self.s.get("ui", "first_nudged") or getattr(self, "_first_nudging", False):
            return
        self._first_nudging = True
        threading.Thread(target=self._first_nudge, name="first-nudge", daemon=True).start()

    def _first_nudge(self):
        try:
            quiet_since = time.monotonic()
            while not self.stopping.wait(5):
                if self.s.get("ui", "first_ask") is not False:
                    return
                busy = self.turn is not None or self.state not in ("idle",) or getattr(self, "_intro_running", False) \
                    or getattr(getattr(self, "prompter", None), "on", False) or getattr(self, "meeting", None) \
                    or time.monotonic() - float(getattr(self, "mic_voice_t", 0) or 0) < 20
                if busy:
                    quiet_since = time.monotonic()
                    continue
                if time.monotonic() - quiet_since < self.FIRST_NUDGE_S:
                    continue
                name = ""
                try:
                    name = self.personas.get(self.s.get("persona"))["name"]
                except Exception:  # noqa: BLE001
                    pass
                self.s.update({"ui": {"first_nudged": True}})
                tries = self.first_try()
                self.emit("first_ask", on=True, phrases=tries)
                self._dj_say(f"Я здесь, если что. Спросите что угодно — например, «{tries[0].rstrip('?')}?» — голосом"
                             + (f", позвав меня по имени — «{name}»," if name else ",") + " или нажмите на подсказку под портретом.")
                return
        finally:
            self._first_nudging = False

    def _intro_more(self, hearing):
        """Город (для погоды и «Утра с Лирой») и утро по расписанию. -> False, если знакомство прервали."""
        if (self.s.get("morning") or {}).get("city"):
            city = (self.s.get("morning") or {}).get("city")
        else:
            if not self._intro_say("В каком ты городе? Утром буду рассказывать погоду.", "city", phrase="В Минске"):
                return False
            text, _ = self._intro_listen()
            if getattr(self, "_intro_stop", False):
                return False
            city, said = intro_city(text)
            if city:
                try:                                   # «в Минске» → «Минск»: так город и покажется в «Утре с Лирой»
                    import weatherq
                    g = weatherq.geocode(city, via=(getattr(getattr(self, "toolbox", None), "hooks", None) or {}).get("dewiar_web"))
                    if g and g.get("name"):
                        city = g["name"]
                except Exception:  # noqa: BLE001
                    pass
                self.s.update({"morning": {"city": city}})
                if not self._intro_say(f"Запомнила: {said}.", "city_ok", city=city):
                    return False
        rem = getattr(self, "reminders", None)
        has_job = rem is None or any(x.get("kind") == "job" and (x.get("preset") == "brief" or x.get("brief")) for x in rem.items)
        if not has_job:
            if not self._intro_say("Хочешь, каждое утро в восемь я буду коротко рассказывать погоду и дела на день? Скажи «да» или «нет».",
                                   "morning", phrases=["Да", "Нет"]):
                return False
            text, _ = self._intro_listen()
            if getattr(self, "_intro_stop", False):
                return False
            if YES_RX.search(text or "") and not NO_RX.search(text or ""):
                try:
                    from jobs import parse as parse_job
                    c = parse_job("каждый день в 08:00 делай утренняя сводка")
                    self.reminders.add(c["at"], "Утренняя сводка", c["repeat"], "job", {"deliver": "voice", "brief": True, "preset": "brief"})
                    if not self._intro_say("Договорились: завтра в восемь расскажу утро — погоду и дела.", "morning_ok"):
                        return False
                except Exception as e:  # noqa: BLE001
                    log.info("знакомство: утро не добавилось: %s", e)
        return True

    def _intro_script(self):
        pid = self.s.get("persona")
        p = self.personas.get(pid)
        name = p["name"]
        log.info("👋 Знакомство: %s", name)
        self.emit("intro", step="start", name=name)
        try:
            self.ensure_voice(pid)                    # голос скачивается при первом запуске — до первой фразы
        except Exception as e:  # noqa: BLE001
            log.debug("знакомство: голос: %s", e)
        self._intro_probe = {"n": 0, "peak": 0.0}
        if not self._intro_say(f"Привет! Я {name}. Я живу вот в этом окошке: слышу тебя, говорю с тобой и помогаю "
                               "с делами — от напоминаний до презентаций.", "hello"):
            return
        # --- микрофон ---
        hearing = getattr(self, "_audio_thread", None) is not None and not self.muted
        no_mic = hearing and self._mic_absent()
        self._intro_probe = None
        if no_mic:                                       # говорить некуда — не просим, а показываем, как писать
            if not self._intro_say("Микрофона я не слышу совсем — похоже, он не подключён. Ничего страшного: мне можно "
                                   "писать — кнопка с клавиатурой внизу окошка. Подключишь микрофон — просто позови меня по имени.",
                                   "mic_none", buttons=["b-type"]):
                return
        elif hearing:
            # 0.58, «первые пять минут»: знакомимся по-настоящему — имя (заодно проверка микрофона), город для погоды,
            # утро по расписанию. Каждый вопрос можно пропустить: молчание — идём дальше.
            if not self._intro_say("Давай познакомимся — заодно проверю микрофон. Как тебя зовут?", "mic",
                                   phrase="Меня зовут …"):
                return
            text, peak = self._intro_listen()
            if getattr(self, "_intro_stop", False):
                return
            who = intro_name(text)
            if who:
                self.s.update({"user_name": who})
                log.info("👋 Знакомство: имя записано")
                ok = self._intro_say(f"Очень приятно, {who}! Слышу тебя отлично.", "mic_ok", heard=text, name_set=who)
                if ok:
                    ok = self._intro_more(hearing=True)
            elif text:
                ok = self._intro_say(f"Слышу тебя отлично: «{text.rstrip('.!?')}». Микрофон в порядке.", "mic_ok", heard=text)
                if ok:
                    ok = self._intro_more(hearing=True)
            elif peak > 0.04:
                ok = self._intro_say("Голос слышу, но слов не разобрать. Говори чуть ближе к микрофону или громче — "
                                     "настроить можно в студии, в разделе «Слух».", "mic_weak")
            else:
                ok = self._intro_say("Тебя пока не слышно. Проверь, тот ли микрофон выбран: студия, раздел «Звук и поведение». "
                                     "А пока можно писать — кнопка с клавиатурой внизу.", "mic_fail")
            if not ok:
                return
        else:
            if not self._intro_say("Микрофон сейчас выключен — включишь кнопкой с микрофоном внизу окошка.", "mic_off"):
                return
        # --- кнопки виджета ---
        # 0.74: короче — новички слушали длинный рассказ и так и не спрашивали ни о чём (воронка 30.10)
        if not self._intro_say("Внизу — кнопки: микрофон, динамик и клавиатура, чтобы писать. Окошко можно перетащить.", "buttons",
                               buttons=["b-mic", "b-voice", "b-type"]):
            return
        # --- мозг и что попробовать ---
        auto_ok = self.s.get("llm", "trial") is not False and (not getattr(self, "wav_input", None) or bool(os.environ.get("DEWIAR_TRIAL")))
        if not self.s.active_llm() and not auto_ok:
            self._intro_say("Чтобы думать и отвечать, мне нужен мозг. Выбери любой: модель на этом компьютере, ключ "
                            "любимого сервиса — OpenAI или Claude — или подключи Dewiar бесплатно. Раздел «Мозг» в студии я открыл.",
                            "brain", page="brain")
            return
        if not self.s.active_llm():                # 0.69: мозг Dewiar подключается сам, а пока — пробный разговор
            if not self._intro_say("Мой бесплатный мозг Dewiar подключается сам, а отвечать я могу уже сейчас. Захочешь свою "
                                   "модель или ключ сервиса — раздел «Мозг» в студии.", "brain_auto"):
                return
        tries = [f"{name}, который час?", "Напомни через пять минут проверить чайник", f"{name}, что ты умеешь?"]
        self._intro_say(f"Попробуй сказать: «{tries[0]}», «{tries[1]}» или «{tries[2]}». Зови меня по имени — "
                        "и я отвечу.", "try", phrases=tries)
