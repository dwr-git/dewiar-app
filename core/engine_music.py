"""Движок Dewiar: быстрые команды без модели — дела по расписанию и утренняя сводка, музыка и радио, умный дом,
сейф, громкость и питание компьютера; плюс фоновые циклы ночного дневника и проверки радиостанций.
Примесь класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Команды *_cmd(text) разбирают фразу своим парсером (jobs.py, music.py, smarthome.py, vault.py, pc.py) и возвращают
True, если ответили сами; False — фразу получит модель. Ответ одной фразой — через _say_quick (engine_tools.py)."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class MusicMixin:
    # ---------- дела по расписанию и утренняя сводка ----------

    def _job_cmd(self, text, via=None):
        """«Каждое утро присылай в Telegram …» — завести дело по расписанию; «сводку сейчас» — выполнить сразу.
        Бот не подключён — дело всё равно заводится, но с ответом голосом."""
        from jobs import parse
        from when import describe_repeat, human
        c = parse(text)
        if not c:
            return False
        if c["op"] == "brief_now":
            if via:
                return False                              # из Telegram — обычным ответом модели (там же и сводка)
            self.emit("heard", text=text)
            threading.Thread(target=self._run_job, args=({"text": "Утренняя сводка", "brief": True, "deliver": "voice"},),
                             daemon=True).start()
            return True
        deliver = c["deliver"]
        note = ""
        bot = self._bot_for(deliver)
        if bot is not None and not bot.paired():
            deliver, note = "voice", f" {bot.TITLE} пока не подключён — пока буду говорить голосом (подключить: студия → «Подключение»)."
        item = self.reminders.add(c["at"], c["task"], c["repeat"], "job", {"deliver": deliver, "brief": c["brief"]})
        # подтверждение — что это делает помощник сам, а не напоминание человеку (экзамен 25.10: «каждый час буду говорить
        # голосом — „Проверяй почту…“» судья принял за напоминание «проверь почту» — так и человек мог понять)
        tell = f"пришлю в {bot.TITLE}" if bot is not None and deliver != "voice" else "скажу голосом и покажу в виджете"
        msg = (f"Хорошо, беру это на себя: {describe_repeat(c['repeat'])} — «{item['text']}». Что получится — {tell}. "
               f"Первый раз — {human(c['at'])}.{note} Отменить — в студии, «Напоминания».")
        self.emit("reminder_set", item=self._reminder_public(item))
        self._say_quick(msg, text, via)
        return True

    def _bot_for(self, deliver):
        """Куда присылать дело: telegram / max → бот; голосом — None."""
        return {"telegram": self.telegram, "max": self.max}.get(deliver or "")

    def _brief_context(self):
        """Данные для утренней сводки текстом: дата, дела и события на сегодня, деньги, фоновые задачи.
        Погоду здесь не берём — её ищет модель по городу из памяти (см. _job_prompt)."""
        from money import fmt
        now = datetime.now()
        today = now.date().isoformat()
        cal = self.calendar_month(now.year, now.month)
        items = cal["days"].get(today, [])
        todo = [f"{x.get('time', '')} {x['title']}".strip() for x in items if x["type"] == "reminder" and not x.get("done")]
        meet = [f"{x.get('time') or 'весь день'} {x['title']}" + (f" ({x['place']})" if x.get("place") else "") for x in items if x["type"] == "event"]
        lines = [f"Сегодня {now:%d.%m.%Y}, {['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'][now.weekday()]}, сейчас {now:%H:%M}."]
        lines.append("Дела и напоминания на сегодня: " + ("; ".join(todo) if todo else "нет") + ".")
        if meet:
            lines.append("Встречи и события из календаря: " + "; ".join(meet) + ".")
        y = (now.date() - timedelta(days=1)).isoformat()
        sy = self.money.summary(y, y)
        sm = self.money.summary(now.date().replace(day=1).isoformat(), today)
        for c in sm["by_currency"][:1]:
            cy = next((x for x in sy["by_currency"] if x["currency"] == c["currency"]), None)
            lines.append(f"Деньги: вчера потрачено {fmt(cy['expense'] if cy else 0, c['currency'])}; с начала месяца доходы "
                         f"{fmt(c['income'], c['currency'])}, расходы {fmt(c['expense'], c['currency'])}.")
        try:
            tasks = [t for t in self.tasks.list() if t.get("status") in ("running", "waiting", "sleeping")]
            if tasks:
                lines.append("Фоновые задачи в работе: " + "; ".join(t.get("title", "") for t in tasks[:3]) + ".")
            wait = [t for t in tasks if t.get("status") == "waiting" and t.get("question")]
            if wait:
                lines.append("Задача ждёт ответа пользователя: " + "; ".join(f"«{t.get('title', '')}» — {t.get('question', '')[:120]}" for t in wait[:2]) + ".")
        except Exception:  # noqa: BLE001
            pass
        try:
            night = self.night.morning_note()             # один раз: что было ночью (night.py)
            if night:
                lines.append("Ночной обход (скажи одной спокойной фразой, без технических слов): " + night)
        except Exception:  # noqa: BLE001
            pass
        return "\n".join(lines)

    def _job_prompt(self, item):
        """Поручение модели для дела по расписанию (или утренней сводки) — модель выполняет его сама, без вопросов."""
        if item.get("brief"):
            return (self._brief_context() + "\n\n"
                    "[Утренняя сводка] Составь по этим данным короткую утреннюю сводку для пользователя: поздоровайся по "
                    "имени, если знаешь; погода на сегодня в его городе (город — из памяти о нём; узнай инструментом "
                    "поиска; не знаешь города — пропусти погоду); дела и напоминания на сегодня; коротко про деньги; "
                    "одна добрая фраза на день. 4–7 коротких предложений, без списков с символами, без вопросов. Если "
                    "есть навык morning-brief — следуй его указаниям (use_skill).")
        return (f"[Дело по расписанию] Поручение пользователя: «{item.get('text', '')}». Выполни его сам прямо сейчас — "
                "используй инструменты (поиск в интернете, чтение страниц, заметки, календарь calendar_list, бюджет "
                "money_report). Ответь готовым коротким сообщением с результатом: без вопросов, без «я могу…», без "
                f"пересказа поручения. Сейчас {datetime.now():%d.%m.%Y %H:%M}.")

    JOB_RETRY_MIN = (5, 15)            # дело не удалось (модель или сеть) — ещё попытки через столько минут

    def _run_job(self, item, attempt=0):
        """Выполнить дело (в своём потоке): подождать до 3 минут, пока ассистент свободен (не перебивать разговор
        и будильник), и ответить туда, куда просили; бот не подключён — голосом. Не удалось — повтор через
        JOB_RETRY_MIN; все попытки мимо — уведомление и запись в журнал сбоев. Итог — в самом деле (last_run,
        last_ok, last_error: студия, «Напоминания», и ночной разбор)."""
        end = time.monotonic() + 180
        while time.monotonic() < end and (self.turn is not None or self.state in ("speaking", "thinking") or self.alarm):
            time.sleep(1.0)
        title = "Утренняя сводка" if item.get("brief") else item.get("text", "Дело по расписанию")
        prompt = self._job_prompt(item)
        log.info("🗓 По расписанию: %s%s", title, f" (попытка {attempt + 1})" if attempt else "")
        bot = self._bot_for(item.get("deliver"))
        to_bot = bot is not None and bot.paired()
        res, ev = {}, threading.Event()

        def report(ok, text):
            res.update(ok=ok, text=text)
            ev.set()
        if to_bot:
            self.ask(prompt, via={"done": lambda _a: None, "speak": False}, raw=True, shown=f"🗓 {title}", report=report)
        else:
            self.ask(prompt, raw=True, shown=f"🗓 {title}", report=report)
        ev.wait(900)
        ok, text = res.get("ok"), res.get("text") or "нет ответа за 15 минут"
        if ok and to_bot:
            bot.send(f"🗓 {title}\n\n{text}")
            self.emit("push", title=f"🗓 {title}", text=text[:300], critical=False)
        if ok is None and ev.is_set():
            return                                       # ход перебили (человек заговорил) — не сбой и не повтор
        try:
            self.reminders.update(item.get("id"), {"last_run": datetime.now().isoformat(timespec="seconds"), "last_ok": bool(ok),
                                                   "last_error": "" if ok else text[:200]})
        except Exception:  # noqa: BLE001
            pass
        if ok:
            return
        self.health_problem(f"Дело по расписанию: {text[:200]}", kind="job")
        if attempt < len(self.JOB_RETRY_MIN):
            log.info("🗓 «%s» не удалось (%s) — повторю через %d мин", title, text[:120], self.JOB_RETRY_MIN[attempt])
            if not self.stopping.wait(self.JOB_RETRY_MIN[attempt] * 60 * float(os.environ.get("DEWIAR_JOB_RETRY_SCALE", "1"))):
                self._run_job(item, attempt + 1)
            return
        msg = f"Не получилось выполнить «{title}»: {text[:200]}. Попробую в следующий раз по расписанию."
        if to_bot:
            bot.send(f"⚠ {msg}")
        self.emit("push", title="⚠ Дело по расписанию не выполнено", text=msg[:300], critical=True)

    # ---------- музыка: свой список радиостанций, без модели ----------

    def _music_service(self):
        """Где включать музыку: выбор в «Руках»; «сам выберу» — в Яндекс Музыке, если её открывали за последние полчаса."""
        sv = self.s.get("music", "service") or "auto"
        if sv in ("radio", "yandex", "youtube"):
            return sv
        name, at = getattr(self, "_music_app", ("", 0.0))
        return name if name and time.monotonic() - at < 1800 else "radio"

    def _player_cmd(self, act, text):
        """Кнопки открытого плеера (Яндекс Музыка, браузер): «играй», «пауза», «следующий трек» — без модели и без кликов."""
        import tools as _tools
        try:
            msg = _tools.t_media({"action": act}, self.toolbox.hooks)
        except _tools.ToolError as e:
            msg = str(e)[:1].upper() + str(e)[1:]
        msg = self._g(msg)
        log.info("🎛 %s → %s", text, msg)
        self.emit("heard", text=text)
        self.emit("answer", text=msg + ".", done=True)          # без голоса — музыку и так слышно
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": msg + ".", "who": self.s.get("persona")}]
        self.set_state("idle")
        return True

    def _yandex_cmd(self, query, text):
        """Открыть поиск в Яндекс Музыке (приложение или сайт) и ответить без модели. Пустой query — просто открыть.
        Из запроса убираются лишние слова, а «электронную музыку» превращаем в «электронная музыка» — как жанр."""
        import tools as _tools
        words = query.split()
        q = " ".join(re.sub(r"(\w{3,})ую$", r"\1ая", w) for w in words       # «электронную» → «электронная»
                     if w not in ("музыку", "музыка", "музычку", "мне", "пожалуйста", "что-нибудь", "какую-нибудь", "*"))
        if q and any(w.startswith("музык") for w in words) and re.search(r"ая$", q):
            q += " музыка"
        _tools.t_yandex_music({"query": q}, self.toolbox.hooks)
        app = _tools.yandex_music_installed()
        msg = (f"Открываю в Яндекс Музыке: «{q}». Нажмите на трек — или скажите «играй»." if q else
               "Открываю Яндекс Музыку." if app else "Открываю Яндекс Музыку на сайте.")
        self._say_quick(msg, text)
        return True

    def _music_cmd(self, text):
        """«Включи музыку» → спросим жанр; «поставь джаз», «что-нибудь спокойное», «дальше», «выключи музыку».
        «Играй», «пауза», «следующий трек» — кнопки открытого плеера; «… в Яндекс Музыке» — там."""
        from music import control, genre_tag, parse
        act = control(text)
        if act == "play" and self.radio.playing and not self.radio.sounding and time.monotonic() - self.radio.last_at > 8:
            last = self.radio.station or self.radio.last         # «играет», а звука нет — станция зависла: включаем заново
            log.info("📻 «%s» — радио молчит (звук не приходит), перезапускаю", text)
            self.radio.stop()
            if last:
                rest = [x for x in self.music.stations() if x["url"] != last.get("url")]
                self._play_station([last] + rest[:3], text, "Радио молчало — включаю заново: «{}».")
                return True
        if act == "play" and self.radio.playing:          # «играй», а радио уже играет — скажем что и как громко
            st, v = self.radio.station or {}, round(self.radio.volume * 100)
            msg = f"Уже играет «{st.get('name', 'радио')}»" + (f", но тихо — громкость радио {v}%. Скажите «громче»." if v <= 20
                                                                else f", громкость радио {v}%.")
            log.info("📻 %s → %s", text, msg)
            self._say_quick(msg, text)
            return True
        if act and not (self.radio.playing or self.radio.paused):
            import tools as _tools
            explicit = re.search(r"нажми|жми|кнопк|play|плей|трек|песн|воспроизвед|проигрыв|пауз", text.lower())
            if explicit or (_tools.media_players() or 0) > 0 or self._music_service() == "yandex":
                return self._player_cmd(act, text)
            if act == "play":                             # ни радио, ни открытого плеера: снова последняя станция
                last = self.radio.last
                if last:
                    tags = set(last.get("tags", "").split())
                    rest = [x for x in self.music.stations() if x["url"] != last.get("url")]
                    rest.sort(key=lambda x: not (tags & set(x["tags"].split())))
                    log.info("📻 «%s» — плеера нет, включаю последнюю станцию «%s»", text, last.get("name"))
                    self._play_station([last] + rest[:3], text, "Включаю «{}».")
                    return True
                g = self.music.genres()[:6]                # ничего ещё не играло — спросим, что включить
                self._music_asked = time.monotonic() + 45
                self._say_quick("Что включить? Например: " + ", ".join(g) + " — или скажите название станции.", text)
                return True
        asked = time.monotonic() < self._music_asked
        failed_recently = time.monotonic() - getattr(self, "_music_failed", -1e9) < 120     # «другую» после неудачи — тоже про радио
        c = parse(text, active=self.radio.playing or bool(self.radio.paused) or failed_recently, asked=asked)
        if not c:
            return False
        op = c["op"]
        if op == "app":
            return self._yandex_cmd("", text)
        if op == "play" and not self.radio.playing and (c.get("service") or self._music_service()) in ("yandex", "youtube"):
            sv = c.get("service") or self._music_service()
            if sv == "yandex":
                return self._yandex_cmd(c["query"], text)
            if not c["strict"] and not re.search(r"радио|станц|волн", text.lower()):
                import tools as _tools
                q = " ".join(w for w in c["query"].split() if w not in ("музыку", "музыка", "музычку"))
                _tools.t_play_music({"query": q}, self.toolbox.hooks)
                self._say_quick(f"Открываю YouTube Music{': «' + q + '»' if q else ''}.", text)
                return True
        if op == "ask" and self._music_service() == "yandex":
            return self._yandex_cmd("", text)
        if op == "stop":
            if not (self.radio.playing or self.radio.paused):
                return False                              # играет что-то другое (браузер, плеер) — решит модель
            self.radio.stop()
            self.radio.paused = None
            self._say_quick("Выключил музыку.", text)
            self.emit("radio", **self.radio.status())
            return True
        if op == "ask":
            g = self.music.genres()[:6]
            self._music_asked = time.monotonic() + 45
            self._say_quick("Какую музыку включить? Например: " + ", ".join(g) + " — или скажите название станции.", text)
            return True
        if op == "next":
            cur = self.radio.station or self.radio.paused or self.radio.last
            nxt = self.music.next_after(cur)
            if not nxt:
                return False
            tags = set((cur or {}).get("tags", "").split())
            rest = [x for x in self.music.stations() if x["url"] not in (nxt["url"], (cur or {}).get("url"))]
            rest.sort(key=lambda x: not (tags & set(x["tags"].split())))        # сначала тот же жанр
            self._play_station([nxt] + rest[:3], text, "Переключаю: «{}».")
            return True
        q = c["query"]
        if re.search(r"ютуб|youtube|spotify|спотиф|яндекс|\bвк\b|вконтакт|песн|трек|клип|альбом|видео|фильм|сериал", q):
            return False                                  # конкретная песня или сервис — это к модели (YouTube и т. п.)
        found = self.music.match(q)
        tag = "" if c["strict"] else genre_tag(q)
        if not found:
            if c["strict"] or not (re.search(r"радио|станц|волн|\bфм\b|\bfm\b", text.lower()) or tag):
                return False
            try:                                          # «включи радио Европа плюс», «включи электронную музыку» — каталог
                from radio import pick, search
                found = search(tag, as_tag=True) if tag and not re.search(r"радио|станц|волн|\bфм\b|\bfm\b", text.lower()) else search(q)
                best = pick(found, q)
                found = [best] + [x for x in found if x is not best] if best else []
            except Exception as e:  # noqa: BLE001
                log.info("Радио: каталог недоступен: %s", e)
                found = []
            if not found:
                return False
        self._music_asked = 0.0
        self._play_station(found[:4], text, "Включаю «{}».")
        return True

    def _home_cmd(self, text, via=None):
        """Умный дом Яндекса без модели: «включи свет в спальне», «весь свет на 30 процентов», «кондиционер на 22»,
        «запусти сценарий Спокойной ночи». Только если такое устройство (или сценарий) правда есть."""
        if not self.home.connected():
            return False
        from smarthome import HomeError, parse
        c = parse(text)
        if not c:
            return False
        try:
            info = self.home.info()
            if c["op"] == "scenario":
                sc = self.home.scenario(c["target"], info)
                if not sc:
                    return False
                self.home.run_scenario(sc)
                msg = f"Запустил сценарий «{sc['name']}»."
            else:
                devs = self.home.match(c["target"], info)
                if not devs:
                    return False
                n = self.home.act(devs, c["op"], c.get("value"))
                rooms = sorted({d.get("room_name") for d in devs if d.get("room_name")})
                what = (devs[0]["name"] if len(devs) == 1 else
                        ("свет" if all(str(d.get("type", "")).startswith("devices.types.light") for d in devs) else f"{len(devs)} устройства"))
                where = f" ({', '.join(rooms)})" if rooms and len(devs) > 1 else ""
                verb = {"on": "Включил", "off": "Выключил", "brighter": "Сделал ярче", "dimmer": "Приглушил",
                        "warm": "Сделал теплее" if (c.get("value") or 0) < 0 else "Сделал холоднее"}.get(c["op"])
                if c["op"] == "brightness":
                    msg = f"{what[:1].upper() + what[1:]}{where} — яркость {c['value']}%."
                elif c["op"] == "temperature":
                    msg = f"{what[:1].upper() + what[1:]} — {c['value']}°."
                else:
                    msg = f"{verb}: {what}{where}." if n == len(devs) else f"{verb}: {what}{where} — ответили {n} из {len(devs)}."
        except HomeError as e:
            msg = f"Умный дом: {e}."
        log.info("🏠 %s → %s", text, msg)
        self._say_quick(msg, text, via)
        return True

    def _vault_cmd(self, text, via=None):
        """Сейф: «запомни пароль от вайфая: кот123», «какой пароль от вайфая?». Безопасность: значение не читается
        вслух, не пишется в журнал и не попадает в историю разговора (а значит — и в модель); на экране ответ помечен
        secret. Из мессенджеров (via: Telegram, MAX) значение НЕ отдаём: переписка хранится у мессенджера и на его
        серверах, телефон с открытым чатом видят другие — только «есть в сейфе, посмотрите на экране компьютера»
        (аудит 19.10, SECURITY.md «Ключи и пароли»). Положить в сейф оттуда можно — с советом удалить сообщение."""
        from vault import parse
        c = parse(text)
        if not c:
            return False
        try:
            if c["op"] == "save":
                self.vault.put(c["name"], c["value"])
                log.info("🔐 В сейф: «%s»", c["name"])
                said = f"{c['name']}: •••"
                msg = f"Положил в сейф: «{c['name']}». Это видно только вам — студия, «Сейф паролей»."
                if via:
                    msg += " Сообщение с паролем осталось в переписке — удалите его там."
                spoken = f"Положил в сейф: {c['name'].lower()}."
            else:
                gen = re.sub(r"[^\wё ]", "", c["name"].lower()).strip() in ("пароль", "пароли", "пин", "пин-код", "пинкод", "коды", "логин")
                x = None if gen else self.vault.find(c["name"])
                said = text
                names = [i["name"] for i in self.vault.list()]
                if x is None and (not gen or not names):
                    return False                         # в сейфе нет — пусть ответит модель (может, это в заметках)
                if x is None:
                    msg = ("В сейфе: " + ", ".join(f"«{n}»" for n in names[:8]) + (" и другие" if len(names) > 8 else "") +
                           ". Какой нужен?") if names else "В сейфе пока пусто. Скажите, например: «запомни пароль от вайфая: …»."
                    spoken = msg
                else:
                    log.info("🔐 Из сейфа: «%s»%s", x["name"], " — в мессенджер не отдаю" if via else "")
                    if via:
                        msg = spoken = (f"🔐 «{x['name']}» есть в сейфе, но в переписку пароли не отправляю — их видно другим и они "
                                        f"хранятся у мессенджера. Посмотрите на экране компьютера: студия → «Сейф паролей».")
                    else:
                        msg = f"🔐 {x['name']}: {x['value']}"
                        spoken = f"{x['name']} — на экране."
        except Exception as e:  # noqa: BLE001
            log.warning("Сейф: %s", e)
            msg = spoken = f"Сейф не открылся: {e}"
            said = f"{c['name']}: •••" if c["op"] == "save" else text     # и при ошибке пароль на экран не выводим
        msg, spoken = self._g(msg), self._g(spoken)
        if via:
            via["done"](msg)
            return True
        self.emit("heard", text=said if c["op"] == "save" else text)
        self.emit("answer", text=msg, done=True, secret=True)
        q = queue.Queue()
        q.put(spoken)
        q.put(None)
        with self._turn_lock:
            self._cancel_locked()
            self.turn_n += 1
            turn = Turn(self.turn_n)
            self.turn = turn

        def run():
            self._speak_worker(turn, q)
            with self._turn_lock:
                if self.turn is turn:
                    self.turn = None
                    self.set_state("idle")
        threading.Thread(target=run, daemon=True).start()
        return True

    def _pc_cmd(self, text):
        """«Громче», «тише», «громкость 40», «выключи звук», «выключи компьютер», «отмени выключение» — без модели."""
        from pc import parse
        import tools as _tools
        c = parse(text)
        if not c:
            return False
        if c["op"] == "volume" and c.get("change") and self.radio.playing \
                and self._radio_step(c["change"] > 0, text):
            return True                                        # играет радио — громче/тише само радио, как у колонки
        if c["op"] == "volume":
            if getattr(self, "server", False):             # сервер: своего звука нет — честно и с уточнением
                self._say_quick("Здесь, на сервере, у меня нет звука — делать тише нечего. Что именно сделать тише: "
                                "музыку или звук на телефоне, компьютере?", text)
                return True
            on, _conf = self.toolbox.policy("set_volume")
            if not on:
                return False
            args = {k: v for k, v in c.items() if k != "op"}
            try:
                msg = _tools.t_volume(args, {})
            except Exception as e:  # noqa: BLE001
                log.warning("громкость: %s", e)
                msg = "Не получилось изменить громкость: " + _tools.human_error(e)
            log.info("🔊 %s → %s", text, msg)
            self.emit("heard", text=text)
            self.emit("answer", text=msg + ".", done=True)          # без голоса — громкость слышно и так
            self.set_state("idle")
            return True
        on, _conf = self.toolbox.policy("power")
        if not on:
            return False
        if c["op"] == "power_cancel":
            was = self.power.cancel()
            self.emit("power", cancelled=True)
            self._say_quick("Отменил, компьютер не выключаю." if was else "Выключение и так не запланировано.", text)
            return True
        act = c["action"]
        msg = self.power.schedule(act, on_error=lambda m: self.note(m))
        self.emit("power", action=act, seconds=60 if act in ("shutdown", "reboot", "logout") else 0)
        log.info("⏻ %s → %s", text, act)
        self._say_quick(msg, text)
        return True

    def _obsidian_index_info(self):
        """Данные для оглавления DEWIAR.md в хранилище Obsidian: имя персонажа и последние 7 дней дневника."""
        from diary import human_date
        titles = (getattr(self, "diary", None) and self.diary.data.get("titles")) or {}
        days = []
        for p in sorted((self.workspace.root / "Дневник").glob("*.md"), reverse=True)[:7]:
            t = titles.get(p.stem) or {}
            try:
                days.append({"day": p.stem, "label": human_date(p.stem), "title": t.get("title", ""), "mood": t.get("mood", "")})
            except ValueError:
                continue
        return {"name": self.persona_name(), "days": days}

    def diary_ask(self, instruction, material):
        """Ночная запись: модель пишет голосом текущего персонажа (его подсказка и «Обо мне»), без инструментов."""
        prof = self.s.active_llm()
        if not prof:
            raise ValueError("нет модели — подключите её в «Мозге»")
        return "".join(stream_chat(dict(prof, max_tokens=1600), self._system(False),
                                   [{"role": "user", "content": instruction + "\n\n---\n\n" + material}]))

    def _diary_loop(self):
        """Фоновый поток: ночью (после diary.hour, по умолчанию 3:00) — или утром, как только компьютер проснулся, —
        запись о прожитом дне; раз в неделю по дневнику обновляется «душа» персонажа. Пишем, только когда
        с ассистентом не говорили 10 минут. Проверка — раз в 10 минут; первая — через 90 с после запуска
        (DEWIAR_DIARY_WAIT — для проверок; при вводе из wav-файла, т. е. в тестах, цикл фактически не работает)."""
        first = float(os.environ.get("DEWIAR_DIARY_WAIT") or (90 if not self.wav_input else 3600 * 24))
        if self.stopping.wait(first):
            return
        try:
            self.diary.log.prune()
        except Exception:  # noqa: BLE001
            pass
        while not self.stopping.is_set():
            try:
                on = self.s.get("diary", "night")
                quiet = self.turn is None and (not self.last_turn_time or time.monotonic() - self.last_turn_time > 600)
                hour = self.s.get("diary", "hour")
                day = self.diary.pending(hour=3 if hour in (None, "") else int(hour)) if on is not False and quiet else None
                if day and self.s.active_llm():
                    got = self.diary.write(day)
                    if got:
                        self.emit("diary", **got)
                        name = self.persona_name()
                        if self.soul.due(name) and self.soul.update(name):     # раз в неделю — и душа по дневнику
                            self.emit("soul", name=name)
            except Exception as e:  # noqa: BLE001
                log.warning("🌙 дневник: ночная запись не получилась: %s", e)
            try:                                         # ночной обход — в то же тихое время (night.py)
                hour = self.s.get("diary", "hour")
                if quiet and self.night.due(hour=3 if hour in (None, "") else int(hour)):
                    got = self.night.run()
                    self.emit("night", **{k: got[k] for k in ("day", "note", "path", "repaired", "left")})
            except Exception as e:  # noqa: BLE001
                log.warning("🌙 ночной обход не получился: %s", e)
            if self.stopping.wait(min(600, first)):
                return

    # ---------- «сам замечает и сам начинает»: вернулись к компьютеру — коротко о главном ----------

    def _welcome_loop(self):
        """Фоновый поток: раз в 5 с — сколько не трогали мышь и клавиатуру (presence.idle_seconds). Отошли дольше
        welcome.away_min минут и вернулись — _welcome_back. При вводе из wav-файла (тесты) не работает."""
        if self.wav_input or self.stopping.wait(30):
            return
        import presence
        self._away = presence.Away()
        while not self.stopping.is_set():
            try:
                self._away.away_after = max(5, int(self.s.get("welcome", "away_min") or 20)) * 60
                gone = self._away.feed(presence.idle_seconds())
                if gone:
                    self._welcome_back(gone)
            except Exception as e:  # noqa: BLE001
                log.debug("приветствие: %s", e)
            if self.stopping.wait(5):
                return

    def _upcoming(self, hours=2):
        """Дела и встречи сегодня в ближайшие hours часов -> [("HH:MM", что)]."""
        now = datetime.now()
        items = self.calendar_month(now.year, now.month)["days"].get(now.date().isoformat(), [])
        lo, hi = f"{now:%H:%M}", f"{now + timedelta(hours=hours):%H:%M}" if (now + timedelta(hours=hours)).date() == now.date() else "23:59"
        out = [(x["time"], x["title"]) for x in items if x.get("type") in ("reminder", "event") and x.get("time")
               and lo <= x["time"] <= hi and not x.get("done")]
        return sorted(out)

    def _welcome_back(self, gone, wait=3.0):
        """Человек вернулся после gone секунд. Молчим, если: выключено, микрофон выключен, созвон, звенит будильник,
        идёт разговор, виджет спрятали и с тех пор не звали, нет модели. Иначе — presence.plan решает, есть ли что
        сказать, и модель говорит это голосом персонажа (1–4 фразы). -> True, если заговорили."""
        import presence
        if self.s.get("welcome", "on") is False or self.muted or self.meeting or self.alarm or self._intro_running:
            return False
        if self.stopping.wait(wait):                     # дать человеку сесть; заговорил сам — не перебиваем
            return False
        if self.turn is not None or self.state not in ("idle", "listening") or not self.s.active_llm():
            return False
        if getattr(self, "_tray_at", 0) > (self.last_turn_time or 0):
            return False                                 # «спрячься» — значит, просили не мешать
        try:
            tasks = self.tasks.list()
        except Exception:  # noqa: BLE001
            tasks = []
        try:
            upcoming = self._upcoming()
        except Exception:  # noqa: BLE001
            upcoming = []
        last = getattr(self, "_welcome_at", None)
        try:
            done = self.done.stats()
        except Exception:  # noqa: BLE001
            done = None
        news_fact = ""
        try:                                             # обновились, а студию с «Что нового» не открывали — скажет сама
            import news as _news
            ui = self.s.get("ui") or {}
            if ui.get("welcome") == "done" and ui.get("news_said") != VERSION and ui.get("news_seen") != VERSION:
                news_fact = _news.say_fact(_news.releases(ui.get("news_seen") or ui.get("news_said") or "", VERSION, "pc", 3))
        except Exception:  # noqa: BLE001
            news_fact = ""
        p = presence.plan(gone, datetime.now() - timedelta(seconds=gone), tasks, upcoming, last, dstat=done,
                          eve_said=getattr(self, "_eve_said", None), news=news_fact)
        if not p:
            log.info("👋 вернулись через %s — сказать нечего, молчим", presence._hm(gone))
            return False
        self._welcome_at = datetime.now()
        if news_fact and news_fact in p["facts"]:
            self.s.update({"ui": {"news_said": VERSION}})
        if p["kind"] == "eve":
            self._eve_said = self._welcome_at.date()
        ctx = ""
        if p["kind"] == "day":
            try:
                ctx = self._brief_context()
            except Exception:  # noqa: BLE001
                ctx = ""
        log.info("👋 вернулись через %s — %s", p["gone"], "сводка дня" if p["kind"] == "day" else "итог дня" if p["kind"] == "eve" else "; ".join(p["facts"]))
        self.ask(presence.prompt(p, ctx), raw=True, shown="👋 С возвращением")
        return True

    def _radio_check_loop(self):
        """Фоновый поток: через 40 с после запуска и затем раз в 6 часов — какие станции списка играют в этой сети
        (результат использует _play_station, чтобы не ждать на молчащих)."""
        if self.stopping.wait(40 if not self.wav_input else 3600 * 24):
            return
        while not self.stopping.is_set():
            try:
                self.radio_health.check_all(self.music.stations())
            except Exception as e:  # noqa: BLE001
                log.debug("проверка станций: %s", e)
            if self.stopping.wait(6 * 3600):
                return

    def _play_station(self, cands, said, phrase):
        """Сказать «Включаю …» и запустить станцию в фоновом потоке; нет 2 секунд звука за 11 с — следующая из cands.
        Станции, которые в этой сети молчат (фоновая проверка), — в конце: не ждём на них. Свой список кончился —
        пробуем каталог radio-browser; молчат две и больше — диагностика (ffmpeg, сеть) и сообщение пользователю."""
        first0 = cands[0]
        cands = self.radio_health.order(cands)
        if cands[0] is not first0:
            log.info("📻 «%s» сейчас не отвечает (проверка) — сначала «%s»", first0.get("name"), cands[0].get("name"))
            phrase = "«" + first0.get("name", "") + "» сейчас не отвечает — включаю «{}»."
        st = cands[0]
        self._say_quick(phrase.format(st["name"]), said)

        def run():
            why = ""
            alts = list(cands)
            first = cands[0]
            tried = set()
            i = -1
            while alts:
                s = alts.pop(0)
                if s["url"] in tried:
                    continue
                tried.add(s["url"])
                i += 1
                try:
                    self.radio.play(s)
                except Exception as e:  # noqa: BLE001
                    log.info("Радио: %s", e)
                    self.note(f"Радио: {e}")
                    return
                gen = self.radio._gen
                from radio import RATE as _R
                end = time.monotonic() + 11.0             # успех — 2 секунды звука подряд (https-поток стартует не сразу)
                while time.monotonic() < end and self.radio.playing and self.radio.got < _R * 2 * 2:
                    if self.radio._gen != gen:
                        return
                    time.sleep(0.25)
                if self.radio._gen != gen or self.radio.paused:   # пользователь сказал «стоп»/«пауза» или включил другое
                    return
                if self.radio.playing and self.radio.got >= _R * 2 * 2:
                    self.radio_health.mark(s["url"], True)
                    v = round(self.radio.volume * 100)
                    quiet = f" Громкость радио всего {v}% — скажите «громче»." if v <= 20 else ""
                    if i:
                        self.note(f"«{first['name']}» не ответила — играет «{s['name']}».{quiet}")
                    elif quiet:
                        self.note(quiet.strip())
                    return
                why = self.radio.failed or why
                log.warning("Радио: станция «%s» не играет: %s", s["name"], self.radio.failed or "нет звука")
                if not (self.radio.failed or "").startswith("ffmpeg"):    # сломан ffmpeg — дело не в станции
                    self.radio_health.mark(s["url"], False, self.radio.failed or "нет звука")
                if self.radio.playing:
                    self.radio.stop()
                if not alts and not s.get("_cat"):                 # свой список молчит — открытый каталог radio-browser
                    try:
                        from radio import search
                        q = (first.get("tags") or "").split()[0:1] or [first.get("name", "")]
                        found = [dict(x, _cat=True) for x in (search(first.get("name", "")) or []) + (search(q[0]) or [])]
                        alts = [x for x in found if x["url"] not in tried][:4]
                        if alts:
                            log.info("Радио: пробую каталог — %s", ", ".join(x["name"] for x in alts))
                    except Exception as e:  # noqa: BLE001
                        log.info("Радио: каталог недоступен: %s", e)
            self._music_failed = time.monotonic()
            if len(tried) >= 2:                               # молчат все — дело не в станциях: где поломка?
                from eyes import ffmpeg_path
                from radio import diagnose
                where, fix = diagnose(ffmpeg_path(), first["url"])
                log.warning("Радио: проверка — %s; %s", where, fix)
                self.note(f"Радио не играет: {where}. {fix[0].upper() + fix[1:]}.")
                self.announce(f"Радио не играет, и дело не в станциях: {where}. {fix[0].upper() + fix[1:]}.")
                return
            self.note("Радиостанции не отвечают" + (f" ({why})" if why else "") + ". Проверьте интернет или скажите другую станцию.")
        threading.Thread(target=run, name="music", daemon=True).start()
