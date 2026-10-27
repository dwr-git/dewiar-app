"""Движок Dewiar: лёгкий режим для слабого компьютера, прокси к серверам Dewiar, облако Dewiar и автоматический выбор
«мозга», базы знаний персонажа, распознавание аудиофайлов и голосовых из Telegram, голосовой ответ в Telegram.
Примесь класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Связи: net.py (прокси), cloud.py и cloud.php (облако, /netcfg, /models), device.py (мощность, план лёгкого режима),
account.py (вход dewiar.pro, базы знаний). _ensure_brain и _account_cloud сами меняют настройки «Мозга»;
ручной выбор модели (_brain_manual, ставит engine_commands.py) _ensure_brain час не перебивает."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка

# «готово» — о результате фоновой задачи, которой ещё нет; «сообщу, когда будет готово» — честно (Engine._early_done)
EARLY_DONE_RX = re.compile(r"(?<![а-яё])(готово|готова|готов|сделал[аи]?|сделано|закончил[аи]?|вот\s+(?:она|он|ваш[аи]?|тво[яй]|"
                           r"презентаци|отч[её]т|документ))(?![а-яё])")
LATER_RX = re.compile(r"сообщ|когда\s+(?:будет|закончу|всё)|как\s+только|в\s+фоне|займ[её]т|начал|взял|приступ|уже\s+работа|работаю")


class BrainMixin:
    # ---------- слабый компьютер: лёгкий режим ----------

    def _stt_local(self):
        """Своё распознавание: на слабом компьютере — лёгкий Vosk, иначе GigaAM."""
        return "vosk" if self.s.get("device", "light") else "gigaam"

    def _tts_local(self):
        """Свой синтез речи: на слабом компьютере — Piper, иначе Vosk."""
        return "piper" if self.s.get("device", "light") else "vosk"

    def _cloud_stt_ok(self):
        """Есть ключ Dewiar и облако умеет распознавать речь (stt_ok узнаём в _ensure_brain по /models)."""
        return bool(self.s.get("cloud", "key") and self.s.get("cloud", "stt_ok"))

    def _net_conf(self):
        """Для net.py: -> (прокси, [адреса серверов Dewiar]). Прокси — свой из настроек, иначе выданный Dewiar
        (если включён). Адреса — сайт аккаунта, облако, обновления, преднастройка и сайт, на который входим сейчас:
        через прокси ходят только к ним."""
        acc = getattr(self, "account", None)
        extra = [(acc.data.get("server") if acc else "") or "", self.s.get("cloud", "url") or "", self.s.get("updates", "url") or "",
                 (self.s.get("provision") or {}).get("url", "") or "", self._net_try]
        own = self.s.get("net", "proxy") or ""
        dw = self.s.get("net", "dewiar_secret") or "" if self.s.get("net", "dewiar") else ""
        return own or dw, extra

    def _lan_fetch(self):
        """Дома — напрямую: спросить у сайта его адрес в домашней сети (cloud.php ?p=/lan, со входом или ключом) и
        передать net.set_lan; сохраняется в net.lan — после перезапуска действует сразу. Раз в 10 минут (_brain_watch)."""
        from cloud import CloudError, fetch
        key = (self.s.get("cloud", "key") or "").strip() or (self.account.token() if self.account.logged_in() else "")
        if not key:
            return
        server = (self.account.data.get("server") or "").rstrip("/")
        url = self.s.get("cloud", "url") or self.account.service_url("cloud") or (server + "/dwrapp/cloud.php" if server else "")
        if not url.endswith("cloud.php"):
            return
        try:
            d = fetch(url, key, "/lan", timeout=20)
        except CloudError as e:
            log.debug("Адрес сайта в домашней сети не узнал: %s", e)
            return
        lan = {"public": url[:-len("cloud.php")], "base": d.get("base") or "", "id": d.get("id") or ""} if d.get("base") else {}
        if lan != (self.s.get("net", "lan") or {}):
            self.s.update({"net": {"lan": lan}})
        import net
        net.set_lan(lan.get("public", ""), lan.get("base", ""), lan.get("id", ""))

    def _dewiar_proxy_fetch(self, force=False):
        """«Использовать прокси Dewiar»: прокси выдаёт cloud.php (/netcfg) тем, у кого есть ключ или вход аккаунтом.
        Получаем и сохраняем заранее, пока сайт открывается: если провайдер потом закроет сайт, прокси уже будет.
        Обновляем не чаще раза в 6 часов (force — сейчас). -> текст ошибки или ""."""
        if not self.s.get("net", "dewiar"):
            return ""
        if not force and time.time() - float(self.s.get("net", "dewiar_at") or 0) < 6 * 3600 and self.s.get("net", "dewiar_secret"):
            return ""
        from cloud import CloudError, fetch
        key = (self.s.get("cloud", "key") or "").strip() or (self.account.token() if self.account.logged_in() else "")
        if not key:
            return "прокси Dewiar выдаётся тем, кто вошёл аккаунтом dewiar.pro или подключил ключ Dewiar"
        server = (self.account.data.get("server") or "").rstrip("/")
        url = self.s.get("cloud", "url") or self.account.service_url("cloud") or (server + "/dwrapp/cloud.php" if server else "")
        try:
            d = fetch(url, key, "/netcfg", timeout=15)
        except CloudError as e:
            log.info("🌐 Прокси Dewiar не получен: %s", e)
            return str(e)
        import net
        try:
            px = net.normalize_proxy(d.get("proxy") or "")
        except net.NetError as e:
            return str(e)
        self.s.update({"net": {"dewiar_secret": px, "dewiar_at": time.time()}})
        log.info("🌐 Прокси Dewiar получен: %s", net.hide(px))
        return ""

    def net_cmd(self, cmd, a):
        """Команды студии «Сеть»: net (состояние), net_proxy (свой прокси — сохраняем, только если через него открывается
        сервер обновлений), net_dewiar (галочка прокси Dewiar). -> состояние для окна, с проверкой связи."""
        import net
        from updater import DEFAULT_URL
        url = self.s.get("updates", "url") or DEFAULT_URL           # latest.json — лёгкий публичный файл на сервере Dewiar
        cur = self.s.get("net", "proxy") or ""
        if cmd == "net_proxy":
            try:
                px = net.normalize_proxy(a.get("proxy", ""))
            except net.NetError as e:
                raise ValueError(str(e)) from e
            if px == "" or a.get("proxy", "").strip() == net.hide(cur):   # выключить / не трогать скрытый пароль
                px = "" if px == "" else cur
            if px:
                r = net.check(url, px)
                if not r["proxy"][0]:
                    raise ValueError(f"через этот прокси {net.host_of(url)} не открывается ({r['proxy'][1]}) — не сохраняю")
            self.s.update({"net": {"proxy": px}})
            log.info("🌐 Прокси для серверов Dewiar: %s", net.hide(px) or "выключен")
            self.emit("settings", settings=self.s.snapshot())
            cur = px
        err = ""
        if cmd == "net_dewiar":                                  # галочка «Использовать прокси Dewiar»
            on = bool(a.get("on"))
            self.s.update({"net": {"dewiar": on}})
            err = self._dewiar_proxy_fetch(force=True) if on else ""
            log.info("🌐 Прокси Dewiar: %s", ("включён" if not err else f"включён, но не получен: {err}") if on else "выключен")
            self.emit("settings", settings=self.s.snapshot())
        eff = self._net_conf()[0]
        r = {"proxy": net.hide(cur), "on": bool(eff), "hosts": list(net.current()[1]), "check_url": url,
             "dewiar": bool(self.s.get("net", "dewiar")), "dewiar_ready": bool(self.s.get("net", "dewiar_secret")), "dewiar_error": err,
             "via": "own" if cur else ("dewiar" if eff else "")}
        if cmd not in ("net", "net_dewiar") or (cmd == "net_dewiar" and a.get("on")):
            r["check"] = net.check(url, eff)
        return r

    def _cloud_caps(self):
        """Умеет ли облако распознавание и озвучку — спросить сервер сейчас (/models). Без ключа или связи — как было."""
        if not self.s.get("cloud", "key"):
            return
        from cloud import fetch
        try:
            md = fetch(self.cloud.url, self.cloud.key, "/models")
        except Exception as e:  # noqa: BLE001 — нет связи: остаётся прежнее
            log.info("☁ Что умеет облако — не узнал: %s", e)
            return
        if bool(md.get("stt")) != bool(self.s.get("cloud", "stt_ok")) or bool(md.get("tts")) != bool(self.s.get("cloud", "tts_ok")):
            self.s.update({"cloud": {"stt_ok": bool(md.get("stt")), "tts_ok": bool(md.get("tts"))}})
            self.emit("settings", settings=self.s.snapshot())

    def device_status(self):
        """Мощность компьютера, лёгкий режим, кто распознаёт речь и совет для окна."""
        from device import measure
        d = dict(getattr(self, "device", None) or measure())
        stt, tts = self.s.get("stt") or {}, self.s.get("tts") or {}
        remote = stt.get("engine") == "remote" and (stt.get("remote") or {}).get("base_url")
        d.update(light=bool(self.s.get("device", "light")), stt=stt.get("engine"), tts=tts.get("engine"),
                 stt_server=bool(remote), logged_in=self.account.logged_in(), cloud=bool(self.s.get("cloud", "key")),
                 cloud_stt=self._cloud_stt_ok(), account_stt=bool(self.account.service_url("stt")),
                 cloud_tts=bool(self.s.get("cloud", "key") and self.s.get("cloud", "tts_ok")), account_tts=bool(self.account.service_url("tts")))
        d["advice"] = self._device_advice(d)
        m = getattr(self, "mem", None) or {}
        d["mem"] = {"tight": bool(m.get("tight")), "free": m.get("free"), "total": m.get("total"), "swap": m.get("swap"),
                    "text": m.get("text", "") if m.get("tight") else ""}
        return d

    def _device_advice(self, d):
        """Совет слабому компьютеру: как переложить распознавание речи на сервер Dewiar. Мощности хватает — ""."""
        if d["level"] == "ok":
            return ""
        if d["stt_server"]:
            return "Речь распознаёт сервер Dewiar — компьютеру легко."
        if d["logged_in"] or d["cloud"]:
            return "Включите «Распознавать речь на сервере Dewiar» — компьютеру станет совсем легко."
        return ("Совет: войдите аккаунтом dewiar.pro (студия → «Dewiar» → «Войти») — думать и распознавать речь "
                "будет сервер Dewiar, а компьютеру останутся только микрофон и динамики.")

    def _device_check(self):
        """При запуске: слабый компьютер, а лёгкий режим ещё не решали для этого «железа» (device.sig — отпечаток
        железа) — включаем и объясняем уведомлением."""
        from device import measure
        try:
            d = self.device = measure()
        except Exception as e:  # noqa: BLE001
            log.info("Мощность компьютера не узнал: %s", e)
            self.device = {"ram": 0, "free": 0, "cores": 0, "level": "ok", "why": "", "sig": ""}
            return
        log.info("Компьютер: %.1f ГБ памяти (свободно %.1f), ядер %s — %s", d["ram"], d["free"], d["cores"],
                 {"ok": "мощности хватает", "weak": "слабый", "very_weak": "очень слабый"}[d["level"]])
        if d["level"] == "ok" or self.s.get("device", "sig") == d["sig"]:
            return
        done = self.set_light(True)
        st = self.device_status()
        text = (f"На этом компьютере мало мощности ({d['why']}) — включил лёгкий режим"
                + (": " + ", ".join(done) if done else "") + ". " + st["advice"])
        self.s.update({"device": {"notice": text}})
        threading.Timer(12.0, lambda: self._push_quiet("Компьютеру тяжело — включил лёгкий режим", text)).start()

    def _push_quiet(self, title, text):
        """Уведомление, но не поверх знакомства: идёт знакомство — дождаться его конца (до 5 минут)."""
        for _ in range(300):
            if not getattr(self, "_intro_running", False):
                break
            time.sleep(1.0)
        self.push(title, text, telegram=False)

    # ---------- памяти не хватает прямо сейчас (открыто много других программ) ----------

    def _memory_watch(self):
        """Фоновый поток: раз в минуту — хватает ли памяти (device.pressure). Тесно две проверки подряд — один раз
        объяснить, кто занимает память и что сделать (не чаще раза в 6 часов; выключается настройкой device.mem_warn).
        Состояние — в self.mem (для студии). Опасно (critical: ещё чуть-чуть, и рабочий стол замрёт) — разгружаемся
        сразу, без второй проверки, а пока тесно, проверяем каждые 10 с. Сколько занимает сам Dewiar (ядро и окна,
        memcap.dewiar_memory) — в self.mem["dewiar"] и в журнале при заметном росте: отчёты несут цифры."""
        from device import pressure, pressure_text, top_memory
        from memcap import dewiar_memory
        if self.stopping.wait(float(os.environ.get("DEWIAR_MEM_WAIT") or 120)):
            return
        streak, told, calm, said = 0, 0.0, 0, (0.0, 0.0, 0.0)
        while not self.stopping.is_set():
            p = {}
            try:
                p = pressure()
                streak = streak + 1 if p["tight"] else 0
                if p.get("critical"):
                    streak = max(streak, 2)
                own = dewiar_memory()
                if (abs(own["core"] - said[0]) >= 0.5 or abs(own["ui"] - said[1]) >= 0.5
                        or time.monotonic() - said[2] > 3600):
                    said = (own["core"], own["ui"], time.monotonic())
                    log.info("🧠 Dewiar занимает: ядро %.1f ГБ, окна %.1f ГБ (больше всех — %s, %.1f ГБ); свободно %.1f ГБ из %.1f",
                             own["core"], own["ui"], own["biggest"][0] or "—", own["biggest"][1], p["free"], p["total"])
                prev = getattr(self, "mem", None) or {}
                self.mem = dict(p, streak=streak, dewiar=own,
                                text=prev.get("text", "") if p["tight"] else "")   # совет живёт, пока тесно
                tight = streak >= 2
                if bool(self.status.get("tight")) != tight:   # окна берегут ресурсы: облик почти неподвижен, лишнее не рисуется
                    self.status["tight"] = tight
                    log.info("🧠 Память %s — анимации окон %s", "на пределе" if tight else "снова есть", "на минимуме" if tight else "как обычно")
                    self.emit("status", status=self.status)
                calm = 0 if p["tight"] else calm + 1
                if self.s.get("device", "light_auto") and calm >= 30:
                    # лёгкий режим включался сам из-за памяти, а полчаса уже свободно — возвращаем точное распознавание
                    self.s.update({"device": {"light_auto": False}})
                    log.info("🧠 Памяти снова хватает полчаса — выключаю лёгкий режим, который включала сама")
                    self.set_light(False)
                if streak >= 2 and self.s.get("device", "mem_warn") is not False and (not told or time.monotonic() - told > 6 * 3600):
                    told = time.monotonic()
                    top = top_memory(3, skip=())
                    st = self.device_status()
                    auto = ""
                    if not st["light"] and self.s.get("device", "auto_light") is not False:
                        # компьютер уже ждёт память — не только советуем, а сами разгружаемся (это обратимо)
                        self.s.update({"device": {"light_auto": True}})
                        done = self.set_light(True)
                        st = self.device_status()
                        auto = ("Перехожу в лёгкий режим" + (": " + ", ".join(done) if done else "") + " — освободится "
                                "память. Когда станет свободнее, верну как было; вернуть сразу — студия → «Dewiar.pro» → «Лёгкий режим». ")
                    text = auto + pressure_text(p, top, light=st["light"], advice=st.get("advice", ""))
                    self.mem["text"] = text
                    log.warning("🧠 Памяти мало: свободно %.2f ГБ из %.1f, подкачка %s%%, PSI %s; больше всех: %s", p["free"], p["total"],
                                p["swap"], p["psi"], ", ".join(f"{k} {v} ГБ" for k, v in top) or "—")
                    self._push_quiet("Компьютеру не хватает памяти", text)
            except Exception as e:  # noqa: BLE001
                log.debug("проверка памяти: %s", e)
            every = float(os.environ.get("DEWIAR_MEM_EVERY") or 60)
            if p.get("tight") or (p.get("psi10") or 0) >= 10:
                every = min(every, 10.0)                  # тесно — следим чаще, чтобы успеть до «замирания»
            if self.stopping.wait(every):
                return

    def set_light(self, on):
        """Лёгкий режим вкл/выкл -> [что сделано, словами]. Запоминает отпечаток железа: выключили сами — для этого
        компьютера _device_check больше не включает. Перестраивает движки речи; при выключении догружает GigaAM."""
        from device import light_plan
        sig = (getattr(self, "device", None) or {}).get("sig", "")
        done = []
        if on:
            plan, done = light_plan(self.s.get("stt"), self.s.get("tts"), cloud_stt=self._cloud_stt_ok(),
                                    account_stt=self.account.service_url("stt"))
            self.s.update({"device": {"light": True, "sig": sig}})
            self._apply_light_stt(plan.get("stt"))
            if plan.get("tts") == "piper":
                self.s.update({"tts": {"engine": "piper"}})
        else:
            self.s.update({"device": {"light": False, "sig": sig, "notice": ""}})
            st = self.s.get("stt") or {}
            if st.get("engine") == "vosk":
                self.s.update({"stt": {"engine": "gigaam"}})
                done.append("распознавание — снова точный GigaAM")
            # голос Piper, потому что Vosk на этом компьютере не успевал за речью (engine_remote._vosk_slow, auto_piper), —
            # остаётся Piper: иначе после лёгкого режима снова минуты на загрузку и секунды на фразу (пакет 22.10, №185)
            if self.s.get("tts", "engine") == "piper" and not self.s.get("tts", "auto_piper"):
                self.s.update({"tts": {"engine": "vosk"}})
                done.append("голос — снова Vosk")
        log.info("Лёгкий режим %s: %s", "включён" if on else "выключен", ", ".join(done) or "без изменений")
        self.apply_engines()
        if not on and isinstance(self.stt, GigaAMSTT) and not self.stt.ready:
            threading.Thread(target=self._background_loads, daemon=True).start()
        elif not on:
            self.ensure_voice(self.s.get("persona"))
        self.emit("settings", settings=self.s.snapshot())
        self.emit("device", **self.device_status())
        return done

    def _apply_light_stt(self, how):
        """Куда отдать распознавание: cloud — облако по ключу, account — сервер распознавания аккаунта, vosk — свой Vosk."""
        if how == "cloud":
            self.cloud.set_stt(True)
        elif how == "account":
            self.s.update({"stt": {"engine": "remote", "remote": {"base_url": self.account.service_url("stt"),
                                                                  "api_key": self.account.token(), "model": "gigaam-v3",
                                                                  "language": "ru", "from_account": True}}})
        elif how == "vosk":
            self.s.update({"stt": {"engine": "vosk"}})

    def _light_upgrade(self):
        """Слабый компьютер распознаёт речь лёгким Vosk, а появился вход или ключ Dewiar — отдаём речь серверу."""
        if not self.s.get("device", "light") or self.s.get("stt", "engine") != "vosk":
            return
        if time.time() - float(self.s.get("device", "stt_slow_at") or 0) < 86400:
            return                                        # сервер недавно был медленным — сутки не переключаем (№331)
        how = "cloud" if self._cloud_stt_ok() else "account" if self.account.service_url("stt") else ""
        if not how:
            return
        self._apply_light_stt(how)
        self.apply_engines()
        self.s.update({"device": {"notice": "", "stt_auto": True}})
        self.emit("settings", settings=self.s.snapshot())
        self.emit("device", **self.device_status())
        self.push("Речь распознаёт сервер Dewiar", "Компьютер слабый — теперь распознаёт сервер: быстрее и точнее.", telegram=False)

    def _stt_timing(self, stt, ms):
        """№331 (пакет 27.10): слабый компьютер сам отдал речь серверу («быстрее и точнее»), а сервер распознавал по
        21–25 с на фразу (вечер, нагрузка, VPN). Три медленные фразы подряд (> 8 с) — возвращаем свой Vosk и сутки
        не переключаем. Только если на сервер переключили мы сами, а не человек."""
        if not self.s.get("device", "stt_auto"):
            return
        slow = getattr(self, "_stt_slow_n", 0)
        self._stt_slow_n = slow + 1 if ms > 8000 else 0
        if self._stt_slow_n < 3:
            return
        self._stt_slow_n = 0
        log.info("Речь на сервере распознаётся медленно (%d мс) — возвращаю распознавание на этот компьютер (Vosk)", ms)
        if self.s.get("cloud", "stt"):
            try:
                self.cloud.set_stt(False)
            except Exception:  # noqa: BLE001
                pass
        self._apply_light_stt("vosk")
        self.s.update({"device": {"stt_auto": False, "stt_slow_at": time.time()}})
        self.apply_engines()
        self.emit("settings", settings=self.s.snapshot())
        self.push("Речь снова распознаёт этот компьютер", "Сервер Dewiar сейчас распознаёт медленно — вернул распознавание сюда, так быстрее.", telegram=False)

    def _cloud_key_gone(self):
        """Ключ dw- удалили или перевыпустили на сайте. Вошли аккаунтом — переходим на облако по аккаунту (один раз,
        под _key_gone_lock: ошибку ключа ловят несколько потоков сразу). -> True, если думаем по аккаунту."""
        if not self.account.logged_in() or self.s.get("cloud", "account"):
            return False
        with self._key_gone_lock:
            if self.s.get("cloud", "account"):
                return True
            was_active = self.s.get("llm", "active") == "dewiar-cloud"
            old = (self.s.get("cloud", "key") or "")[-4:]
            self.s.update({"cloud": {"key": "", "account": False}})
            self._account_cloud(force_active=was_active, quiet=True)
            if not self.s.get("cloud", "account"):
                return False
        log.info("☁ Ключ Dewiar …%s больше не действует — думаю по аккаунту dewiar.pro", old)
        self.push("Ключ Dewiar больше не действует", "Его удалили на сайте — теперь думаю по аккаунту dewiar.pro, ничего делать не нужно.",
                  telegram=False)
        return True

    def _ensure_brain(self, why="start"):
        """Рабочий «мозг» сам, без настроек. Есть вход dewiar.pro или ключ Dewiar, а модель не выбрана или не отвечает
        (например, домашний сервер из преднастроенной сборки вне дома) — переключаемся на модели Dewiar и помним
        прежнюю в llm.auto_from; она снова ответила — возвращаемся к ней. Ручной выбор за последний час не трогаем.
        Речь: свой GigaAM не загрузился, а облако умеет распознавать — отдаём речь серверу Dewiar (тот же GigaAM).
        Вызывается при запуске, после входа, после подключения ключа и раз в 10 минут (_brain_watch). Ходит в сеть."""
        from cloud import CloudError, PROFILE_ID, fetch
        import egress
        if egress.local_only():                                # стоп-кран: в модели Dewiar сами не переключаемся
            return
        if not (self.account.logged_in() or self.s.get("cloud", "key")):
            return
        with self._brain_lock:
            active = self.s.get("llm", "active") or ""
            profiles = self.s.get("llm", "profiles") or {}
            back = self.s.get("llm", "auto_from") or ""
            if active and active not in profiles:
                # активная модель указывает на удалённый профиль (например, профиль облака убрали, а выбор остался) —
                # это «модель не выбрана», а не выбор человека
                log.info("🧠 Активной модели «%s» нет в «Мозге» — считаю, что модель не выбрана", active)
                self.s.update({"llm": {"active": ""}})
                active = ""

            def alive(pid):
                """Отвечает ли модель профиля: две попытки списка моделей — сервер мог моргнуть."""
                prof = profiles.get(pid)
                if not prof:
                    return False
                for i in range(2):
                    try:
                        list_models(prof, timeout=4)
                        return True
                    except LLMError:
                        if i == 0:
                            self.stopping.wait(2)
                    except Exception:  # noqa: BLE001
                        return False
                return False
            if active == PROFILE_ID and back and back in profiles and alive(back):
                self.s.update({"llm": {"active": back, "auto_from": ""}})        # свой сервер снова отвечает — к нему
                log.info("🧠 «%s» снова отвечает — думаю им", profiles[back].get("name", back))
                self.push("Ваша модель снова на связи", f"Думаю моделью «{profiles[back].get('name', back)}».", telegram=False)
                self.emit("settings", settings=self.s.snapshot())
                return
            # ручной выбор модели час не перебиваем; но «никакой модели» человек не выбирает — её чиним всегда
            manual = bool(active) and time.monotonic() - getattr(self, "_brain_manual", -1e9) < 3600
            if active != PROFILE_ID and not manual and not (active and alive(active)):
                was = profiles.get(active, {}).get("name", active) if active else ""
                if (self.s.get("llm", "active") or "") != active or \
                        (active and time.monotonic() - getattr(self, "_brain_manual", -1e9) < 3600):
                    return                                     # пока проверяли, модель выбрали сами — не спорим
                if self.account.logged_in() and (not self.s.get("cloud", "key") or self.s.get("cloud", "account")):
                    self._account_cloud(force_active=True, quiet=True)
                elif self.s.get("cloud", "key") and PROFILE_ID in profiles:
                    self.s.update({"llm": {"active": PROFILE_ID}})
                elif self.s.get("cloud", "key"):
                    # ключ есть, а моделей Dewiar в «Мозге» нет (например, восстановили копию настроек, сделанную до
                    # подключения: ключ остался, список моделей старый) — подключаем заново тем же ключом
                    key = self.s.get("cloud", "key")
                    try:
                        self.cloud.connect(key, self.cloud.url, account=bool(self.s.get("cloud", "account")) or not key.lower().startswith("dw-"))
                        log.info("☁ Ключ Dewiar был, а моделей в «Мозге» не было — подключил заново")
                    except CloudError as e:
                        log.info("☁ Ключ Dewiar есть, моделей нет, подключить не вышло: %s", e)
                if self.s.get("llm", "active") == PROFILE_ID:
                    if active:
                        self.s.update({"llm": {"auto_from": active}})
                    log.info("🧠 %s — думают модели Dewiar (%s)", f"«{was}» не отвечает" if was else "модель не выбрана", why)
                    self.push("Думают модели Dewiar", (f"«{was}» сейчас не отвечает — " if was else "") + "подключил модели Dewiar"
                              + (" по вашему аккаунту." if self.s.get("cloud", "account") else " по ключу.")
                              + (" Когда ваш сервер ответит, вернусь к нему сам." if was else ""), telegram=False)
                    self.probe_tools_bg()
                    self.emit("settings", settings=self.s.snapshot())
                    self.emit("cloud", **self.cloud.status())
            # подключено (ключ или вход аккаунтом), а моделей Dewiar в «Мозге» нет, хотя думает своя модель — возвращаем их
            # в список запасным вариантом, не перебивая выбор
            if self.s.get("cloud", "key") and PROFILE_ID not in (self.s.get("llm", "profiles") or {}):
                key = self.s.get("cloud", "key")
                try:
                    self.cloud.connect(key, self.cloud.url, account=bool(self.s.get("cloud", "account")) or not key.lower().startswith("dw-"),
                                       activate=not self.s.get("llm", "active"))
                    log.info("☁ Модели Dewiar вернулись в «Мозг» (%s)", "по аккаунту" if self.s.get("cloud", "account") else "по ключу")
                    self.emit("settings", settings=self.s.snapshot())
                except CloudError as e:
                    log.info("☁ Вернуть модели Dewiar в «Мозг» не вышло: %s", e)
            # распознавание: умеет ли облако речь — спрашиваем у сервера каждый раз; свой GigaAM не загрузился — речь серверу
            self._cloud_caps()
            st = self.s.get("stt") or {}
            if st.get("engine") in ("gigaam", "vosk") and self.status.get("stt_ready") is False and self._cloud_stt_ok():
                self._apply_light_stt("cloud")
                self.apply_engines()
                log.info("🎤 Свой GigaAM не загрузился — речь распознаёт сервер Dewiar")
                self.push("Речь распознаёт сервер Dewiar", "Своя модель распознавания не загрузилась — теперь речь распознаёт "
                          "сервер Dewiar (тот же GigaAM). Вернуть — в «Слухе».", telegram=False)
                self.emit("settings", settings=self.s.snapshot())

    def _brain_watch(self):
        """Фоновый поток: через 20 с после запуска (сеть и вход уже есть) и затем раз в 10 минут — проверить «мозг»
        и освежить прокси Dewiar. Сроки меняются переменными DEWIAR_BRAIN_WAIT/DEWIAR_BRAIN_EVERY (для проверок)."""
        if self.stopping.wait(20 if not self.wav_input else float(os.environ.get("DEWIAR_BRAIN_WAIT") or 86400)):
            return
        why = "запуск"                                         # причина в журнале: первый раз — запуск, дальше — проверка раз в 10 минут
        while not self.stopping.is_set():
            try:
                self._lan_fetch()                              # дома — к сайту напрямую, без прокси (до остального: оно ходит туда же)
            except Exception:  # noqa: BLE001
                log.exception("адрес сайта в домашней сети")
            try:
                self._ensure_brain(why)
            except Exception:  # noqa: BLE001
                log.exception("мозг: проверка")
            why = "проверка"
            try:
                self._dewiar_proxy_fetch()                     # прокси Dewiar (если включён) — свежий, пока сайт открывается
            except Exception:  # noqa: BLE001
                log.exception("прокси Dewiar")

            if self.stopping.wait(float(os.environ.get("DEWIAR_BRAIN_EVERY") or 600)):
                return

    # ---------- заявка на Dewiar из программы и перенос кодом ----------

    def _cloud_connected(self, r, why):
        """После подключения ключа: студия видит профиль, модель проверяется на инструменты, мозг — в порядке."""
        self.s.update({"llm": {"auto_from": ""}})
        self.emit("settings", settings=self.s.snapshot())
        self.probe_tools_bg()
        self._light_upgrade()
        threading.Thread(target=self._ensure_brain, args=(why,), daemon=True).start()
        return r

    def join_send(self, name, contact, note=""):
        """Заявка на модели Dewiar: одобрят (или само) — ключ подключится сам (_join_loop). -> ответ облака без секрета."""
        import cloud as C
        url = self.s.get("cloud", "url") or C.DEFAULT_URL
        d = C.join_send(url, (name or "").strip(), (contact or "").strip(), (note or "").strip())
        self.s.update({"cloud": {"join": {"id": d.get("id"), "secret": d.get("secret"), "url": url}}})
        if d.get("key"):
            self._join_done(d["key"], d)
        return {k: v for k, v in d.items() if k not in ("secret", "key")}

    def join_check(self):
        """Заявку одобрили? -> {status, text} (ключ — сразу подключается)."""
        import cloud as C
        j = self.s.get("cloud", "join") or {}
        if not j.get("id"):
            return {"status": ""}
        try:
            d = C.join_status(j.get("url") or C.DEFAULT_URL, j["id"], j.get("secret", ""))
        except C.CloudError as e:
            if "не найдена" in str(e):
                self.s.update({"cloud": {"join": {"id": 0, "secret": "", "url": ""}}})
                return {"status": "gone", "text": "Заявка не нашлась — отправьте новую."}
            raise
        if d.get("status") == "ok" and d.get("key"):
            self._join_done(d["key"], d)
        elif d.get("status") == "no":
            self.s.update({"cloud": {"join": {"id": 0, "secret": "", "url": ""}}})
            self.emit("settings", settings=self.s.snapshot())
        return {k: v for k, v in d.items() if k != "key"}

    def _join_done(self, key, d):
        j = self.s.get("cloud", "join") or {}
        r = self.cloud.connect(key, j.get("url", ""))
        self.s.update({"cloud": {"join": {"id": 0, "secret": "", "url": ""}}})
        self._cloud_connected(r, "заявка одобрена")
        text = "Готово — Dewiar подключён" + (f" («{d.get('reply')}»)" if d.get("reply") else "") + ". Спроси меня что-нибудь!"
        log.info("☁ Заявка на Dewiar одобрена — ключ подключён")
        self.emit("cloud", **self.cloud.status())
        self.push("Dewiar подключён", "Заявку одобрили — модели Dewiar работают.", telegram=False)
        try:
            self.announce(text)
        except Exception:  # noqa: BLE001
            pass

    def _join_loop(self):
        """Фоновый поток: пока ждём заявку — раз в минуту спрашиваем, не одобрили ли (при вводе из wav — не работает)."""
        every = os.environ.get("DEWIAR_JOIN_EVERY")                  # для проверок: опрос и при вводе из wav, чаще
        if (self.wav_input and not every) or self.stopping.wait(1 if every else 15):
            return
        while not self.stopping.is_set():
            if (self.s.get("cloud", "join") or {}).get("id"):
                try:
                    self.join_check()
                except Exception as e:  # noqa: BLE001
                    log.debug("заявка на Dewiar: %s", e)
            if self.stopping.wait(float(os.environ.get("DEWIAR_JOIN_EVERY") or 60)):
                return

    def pair_new(self):
        """«Добавить устройство»: код из 6 цифр на 10 минут для этого ключа dw-."""
        import cloud as C
        key = self.cloud.key
        if not key:
            raise C.CloudError("ключа Dewiar здесь нет — на другом устройстве войдите тем же аккаунтом dewiar.pro")
        return C.fetch(self.cloud.url, key, "/pair/new", body={})

    def pair_claim(self, code, url=""):
        """Код с другого устройства -> тот же ключ на этом компьютере."""
        import cloud as C
        u = (url or "").strip() or self.cloud.url
        key = C.pair_claim(u, code)
        if not key:
            raise C.CloudError("код не подошёл")
        r = self.cloud.connect(key, u)
        return self._cloud_connected(r, "код другого устройства")

    def _cloud_use(self):
        """«Отвечать моделями Dewiar» (студия, телефон, первый ответ без модели): сделать модели Dewiar активными тем,
        что есть, — своим ключом dw-… или входом аккаунтом dewiar.pro. Ключа нет и вход не выполнен — понятная ошибка.
        -> cloud.status() + profile."""
        from cloud import CloudError, PROFILE_ID, key_gone
        key, acc = self.s.get("cloud", "key") or "", bool(self.s.get("cloud", "account"))
        if key and not acc:
            try:
                self.cloud.connect(key, self.cloud.url)
            except CloudError as e:
                if not (key_gone(e) and self.account.logged_in()):
                    raise
                self.s.update({"cloud": {"key": "", "account": False}})       # свой ключ удалён на сайте — дальше по аккаунту
                key = ""
        if not key or acc:
            if not self.account.logged_in():
                raise CloudError("войдите в аккаунт dewiar.pro (раздел «Dewiar.pro») или вставьте ключ Dewiar")
            self._account_cloud(force_active=True, quiet=True, strict=True)
        self.s.update({"llm": {"active": PROFILE_ID, "auto_from": ""}})
        self.emit("settings", settings=self.s.snapshot())
        self.emit("cloud", **self.cloud.status())
        self.probe_tools_bg()
        return dict(self.cloud.status(), profile=PROFILE_ID)

    def _account_cloud(self, force_active=False, quiet=False, strict=False):
        """Вошли аккаунтом dewiar.pro — модели Dewiar Облака по тому же входу: без ключа, со своим зарядом в талерах.
        Своя модель уже выбрана — облако добавляется в «Мозг» запасным вариантом и не перебивает её (force_active —
        сделать облако активным). Действующий свой ключ dw-… не трогаем. quiet — без уведомления."""
        from cloud import CloudError
        if self.s.get("cloud", "key") and not self.s.get("cloud", "account"):
            try:                                       # у человека свой ключ dw-… — не трогаем, если он ещё действует
                from cloud import fetch, key_gone
                fetch(self.cloud.url, self.cloud.key, "/balance")
                return
            except CloudError as e:
                if not key_gone(e):
                    return
                force_active = force_active or self.s.get("llm", "active") == "dewiar-cloud"
                log.info("☁ Свой ключ Dewiar удалён на сайте — облако по аккаунту")
        server = (self.account.data.get("server") or "").rstrip("/")
        url = self.account.service_url("cloud") or (server + "/dwrapp/cloud.php" if server else "")
        active = self.s.get("llm", "active")
        profiles = self.s.get("llm", "profiles") or {}
        mine = bool(active and active in profiles and active != "dewiar-cloud") and not force_active
        try:
            r = self.cloud.connect(self.account.token(), url, account=True, activate=not mine)
        except CloudError as e:
            log.info("☁ Облако по аккаунту недоступно: %s", e)
            if strict:
                raise
            return
        self.emit("settings", settings=self.s.snapshot())
        self.emit("cloud", **self.cloud.status())
        if not mine:
            self.probe_tools_bg()
        self._light_upgrade()
        if not quiet:
            self.push("Модели Dewiar подключены", f"По вашему аккаунту: заряд {r.get('percent', '?')}%"
                      + ("" if not mine else " — выбрать их можно в «Мозге»"), telegram=False)

    def _persona_knowledge(self, text, turn):
        """У персонажа подключены базы сайта Dewiar (например, «Библия» из публичной библиотеки): перед ответом
        ищем во всех параллельно по вопросу и даём модели найденное — персонаж отвечает по источнику, своим голосом.
        Нужен вход аккаунтом. -> добавка к системной подсказке ("" — баз нет или ход отменён); картинки к найденному
        показываются в фоне."""
        try:
            p = self.personas.get(self.s.get("persona")) or {}
        except Exception:  # noqa: BLE001
            return ""
        bases = p.get("knowledge") or []
        q = (text or "").split("\n\nВложения:")[0].strip()
        if not bases or len(q) < 3 or not self.account.logged_in():
            return ""
        from concurrent.futures import ThreadPoolExecutor
        from account import AccountError
        labels = ", ".join(f"«{b.get('label')}»" for b in bases)
        self.emit("tool", name="knowledge", title=f"Ищу в {labels}", status="run")
        hist = [{"role": m["role"], "content": m["content"]} for m in self.history[-4:]
                if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]

        def one(b):
            try:
                return b, self.account.retrieve(q, b, hist), ""
            except AccountError as e:
                return b, None, str(e)
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=min(4, len(bases))) as ex:
            got = list(ex.map(one, bases))
        if turn.cancel.is_set():
            return ""
        parts, empty, errs, images, srcs = [], [], [], [], []
        per = max(1500, 7000 // max(1, len(bases)))           # ~7000 знаков на все базы, но не меньше 1500 на каждую
        for b, r, err in got:
            if err:
                errs.append(f"«{b.get('label')}»: {err}")
            elif r and r["found"]:
                parts.append(f"### Из «{b.get('label')}»\n{r['context'][:per]}")
                images += r["images"]
                srcs += r["sources"]
            else:
                empty.append(f"«{b.get('label')}»")
        log.info("📚 Базы персонажа (%s): найдено в %d из %d за %.1f с%s", labels, len(parts), len(bases),
                 time.monotonic() - t0, ("; ошибки: " + "; ".join(errs)) if errs else "")
        self.emit("tool", name="knowledge", title=f"Ищу в {labels}", status="error" if errs and not parts else "done",
                  **({"error": errs[0]} if errs and not parts else {}))
        if images:
            threading.Thread(target=self._show_rag_images, args=(images,), daemon=True).start()
        out = ""
        if parts:
            out = ("\n\nТВОЯ БАЗА ЗНАНИЙ (сайт Dewiar) — найдено по вопросу пользователя. Отвечай, опираясь на это: "
                   "где уместно, приводи дословные цитаты и называй источник (книга, глава и стих — или документ и "
                   "страница). Не выдумывай того, чего в найденном нет; если найденное не отвечает на вопрос — скажи "
                   "об этом честно и бережно ответь от себя.\n\n" + "\n\n".join(parts))
            if srcs:
                out += "\n\nИсточники: " + "; ".join(dict.fromkeys(srcs))
        elif empty:
            out = (f"\n\nВ твоей базе знаний ({', '.join(empty)}) по этому вопросу ничего не нашлось. Если отвечаешь "
                   "от себя — так и скажи одной фразой.")
        if errs and not parts:
            out += f"\n\nБаза знаний сейчас недоступна ({errs[0]}). Ответь от себя и коротко скажи, что база не ответила."
        return out

    def _show_rag_images(self, images):
        """Картинки к найденному (гравюры, схемы) — в виджет: скачиваем с сайта с токеном входа (до трёх, каждая
        меньше 3 МБ) и отдаём окну как data:-адреса."""
        import base64
        import httpx
        out = []
        for im in images[:3]:
            try:
                r = httpx.get(im["url"], timeout=20, follow_redirects=True,
                              headers={"Authorization": "Bearer " + self.account.token()})
                ct = r.headers.get("content-type", "")
                if r.status_code == 200 and ct.startswith("image/") and len(r.content) < 3_000_000:
                    out.append({"src": f"data:{ct.split(';')[0]};base64," + base64.b64encode(r.content).decode(),
                                "title": im.get("title") or ""})
            except Exception as e:  # noqa: BLE001
                log.info("Картинка из базы не скачалась (%s): %s", im.get("url"), e)
        if out:
            self.emit("media", items=out)

    def _early_done(self, turn):
        """Фоновую задачу только запустили (start_task), а модель уже говорит «Готово», «Сделал», «Вот презентация» —
        результата ещё нет (отзыв 13.10: «говорит "Сделала!", а результат через 20–60 минут или нет»). -> поправка или ""."""
        if "start_task" not in (getattr(turn, "tools_ok", None) or []):
            return ""
        t = (turn.full or "").lower()
        if not EARLY_DONE_RX.search(t) or LATER_RX.search(t):
            return ""
        log.warning("⚠ Модель сказала «готово» сразу после запуска задачи: %s", turn.full[:120])
        return "Поправлюсь: задача только началась — результат появится позже, я сообщу, когда всё будет готово."

    def _fake_reminder(self, said, turn):
        """Модель сказала «поставила напоминание», а инструмент не вызывала (бывает у небольших моделей) — честно
        предупредить, а не оставить человека с несуществующим напоминанием. -> текст предупреждения или ""."""
        if not re.search(r"\bнапомни|\bнапоминай|\bразбуди|будильник на|таймер на|засеки|"
                         r"(?:поставь|сделай|заведи)\s+(?:мне\s+)?(?:будильник|таймер|напоминание)", (said or "").lower()):
            return ""
        if any(n in ("set_reminder", "cancel_reminder", "list_reminders") for n in getattr(turn, "tools_ok", [])):
            return ""
        if not re.search(r"напомн|постав|установ|готово|сделано|добавил|запланир|будильник|таймер", turn.full.lower()):
            return ""
        log.warning("⚠ Модель сказала, что поставила напоминание, но инструмент не вызвала: %s", said[:120])
        return ("⚠ На самом деле напоминание не поставлено — модель не вызвала инструмент. Скажите так: «напомни "
                "в пятницу в 16:30 сделать бэкап» или добавьте в студии, «Напоминания».")

    def _set_reminder_fast(self, r, via=None):
        """«Напомни…» разобрали сами — ставим без модели и подтверждаем одной фразой."""
        from when import describe_repeat, human
        item = self.reminders.add(r["at"], r["text"], r["repeat"], r["kind"], extra={"note": r.get("note")})
        rep = describe_repeat(r["repeat"])
        if r["kind"] == "timer":
            msg = f"Таймер — {human(r['at'])}."
        elif r["kind"] == "alarm":
            msg = f"Будильник — {human(r['at'])}" + (f", {rep}" if rep else "") + "."
        else:
            msg = (f"Хорошо, буду напоминать {rep}: {r['text'].rstrip('.')}. Первый раз — {human(r['at'])}." if rep else
                   f"Хорошо, напомню {human(r['at'])}: {r['text'].rstrip('.')}.")
        if r.get("att"):                                  # напоминание с картинками (engine_answer._reminder_with_files)
            pics = all(f["kind"] == "image" for f in r["att"])
            many = len(r["att"]) > 1
            msg += (" Картинки будут прямо в напоминании." if pics and many else " Картинка будет прямо в напоминании." if pics
                    else " Файлы будут прямо в напоминании." if many else " Файл будет прямо в напоминании.")
        log.info("⏰ Поставлено (без модели): %s — %s %s", r["text"], r["at"], rep)
        self.emit("reminder_set", item=self._reminder_public(item), text=msg)
        self._say_quick(msg, r.get("said", r["text"]), via)

    def _drain_worker(self, turn, sentences):
        """Вместо озвучки для ответа в Telegram: дома не говорим, только вычитываем очередь фраз и отпускаем метки
        ("sync", Event) — их ждёт, например, _confirm, пока договорится сказанное."""
        while True:
            s = sentences.get()
            if s is None:
                break
            if isinstance(s, tuple):
                s[1].set()

    def _tg_transcribe(self, ogg):
        """Голосовое из Telegram (OGG/Opus) → текст тем же слухом, что дома."""
        from eyes import ffmpeg_path
        exe = ffmpeg_path()
        if not exe:
            raise RuntimeError("нет ffmpeg, чтобы прочитать голосовое")
        kw = {"creationflags": 0x08000000} if os.name == "nt" else {}     # Windows: CREATE_NO_WINDOW — без окна консоли
        r = subprocess.run([exe, "-loglevel", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
                           input=ogg, capture_output=True, timeout=120, **kw)
        if r.returncode or not r.stdout:
            raise RuntimeError("голосовое не прочиталось")
        for _ in range(180):                     # программа только запустилась — подождём слух (до 90 с)
            if getattr(self, "vosk_stt", None) is not None or getattr(self, "names_off", False) or self.stopping.is_set():
                break
            time.sleep(0.5)
        stt = self.current_stt()
        if stt is None:
            raise RuntimeError("слух ещё загружается — попробуйте через минуту")
        try:
            return stt.transcribe(r.stdout).strip()
        except Exception as e:  # noqa: BLE001
            if getattr(self, "vosk_stt", None) and stt is not self.vosk_stt:
                log.warning("%s не распознал голосовое (%s) — Vosk", getattr(stt, "name", "?"), e)
                return self.vosk_stt.transcribe(r.stdout).strip()
            raise

    def transcribe_file(self, path, cancel=None, chunk=22.0):
        """Аудио или видео любой длины -> [(начало_с, конец_с, текст)]: режем по тихим местам на куски до chunk секунд
        (~22 с уверенно слышит GigaAM) и распознаём тем же слухом, что дома; не вышло — запасным Vosk.
        Работает долго (на чтение файла ffmpeg даётся до 30 мин); cancel прерывает между кусками."""
        import numpy as np
        from eyes import ffmpeg_path
        exe = ffmpeg_path()
        if not exe:
            raise RuntimeError("нет ffmpeg")
        kw = {"creationflags": 0x08000000} if os.name == "nt" else {}
        r = subprocess.run([exe, "-loglevel", "error", "-i", str(path), "-vn", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
                           capture_output=True, timeout=1800, **kw)
        if r.returncode or not r.stdout:
            raise RuntimeError("не получилось прочитать звук из файла: " + (r.stderr or b"").decode(errors="replace")[-200:])
        for _ in range(180):                          # программа только запустилась — подождём слух (до 90 с)
            if getattr(self, "vosk_stt", None) is not None or getattr(self, "names_off", False) or self.stopping.is_set():
                break
            time.sleep(0.5)
        stt = self.current_stt()
        if stt is None:
            raise RuntimeError("слух ещё загружается — попробуйте через минуту")
        a = np.frombuffer(r.stdout, dtype=np.int16)
        sr, n = 16000, len(a)
        win = int(0.03 * sr)
        energy = np.sqrt(np.convolve(a.astype(np.float32) ** 2, np.ones(win) / win, mode="same")) if n else np.array([])
        out, start = [], 0
        while start < n:
            if cancel is not None and cancel.is_set():
                break
            end = min(n, start + int(chunk * sr))
            if end < n:                                   # конец куска — в самом тихом месте последних 6 с (кусок не короче 8 с)
                lo = max(start + int(8 * sr), end - int(6 * sr))
                seg = energy[lo:end]
                if len(seg):
                    end = lo + int(np.argmin(seg))
            pcm = a[start:end]
            if len(pcm) > sr // 4 and float(np.abs(pcm).max()) > 300:      # тишину и обрывки короче 0,25 с не распознаём
                try:
                    txt = stt.transcribe(pcm.tobytes()).strip()
                except Exception as e:  # noqa: BLE001
                    if getattr(self, "vosk_stt", None) and stt is not self.vosk_stt:
                        txt = self.vosk_stt.transcribe(pcm.tobytes()).strip()
                    else:
                        raise RuntimeError(f"распознавание: {e}") from e
                if txt:
                    out.append((start / sr, end / sr, txt))
            start = end
        return out

    def _tg_voice_reply(self, answer, bot=None):
        """На голосовое — ещё и голосом: тем же голосом персонажа, файлом OGG/Opus (как голосовые в Telegram)."""
        from eyes import ffmpeg_path
        text = speakable(answer)[:1500]
        exe = ffmpeg_path()
        if not text or not exe:
            return
        voice = self._voice_cfg()
        for eng in self._engines_for_speech(voice):
            try:
                rate, buf = None, bytearray()
                for r_, pcm in eng.synth(pronounce(text, remote=isinstance(eng, RemoteTTS)), voice, 1.0):
                    rate = rate or r_
                    buf += pcm
                if not buf:
                    continue
                kw = {"creationflags": 0x08000000} if os.name == "nt" else {}
                r = subprocess.run([exe, "-loglevel", "error", "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                                    "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1"],
                                   input=bytes(buf), capture_output=True, timeout=120, **kw)
                if r.returncode == 0 and r.stdout:
                    (bot or self.telegram).send_voice(r.stdout)
                    return
            except Exception as e:  # noqa: BLE001
                log.info("Голосовой ответ в Telegram (%s): %s", type(eng).__name__, e)
