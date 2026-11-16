"""Команды окон (студия, виджет, телефон): Telegram, карта памяти, экзамен, память персонажей, «Мои файлы» (mm_), аккаунт dewiar.pro.
Часть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки
проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class AccountCommands:
    def _cmd_account(self, cmd, a):
        if cmd.startswith("tg_"):                # Telegram: подключить бота, код владельца, проверка, отключить
            from telegram import TelegramError
            tg = self.telegram
            try:
                if cmd == "tg_connect":
                    r = tg.connect(a.get("token", ""), a.get("api", ""))
                elif cmd == "tg_connect_shared":            # общий бот Dewiar — через аккаунт сайта
                    # без аккаунта — по ключу этого компьютера; адреса пробуем по очереди: из настроек, с сайта
                    # аккаунта, общий dewiar.pro
                    # Вошли в аккаунт — бот аккаунта (один на все компьютеры и телефон; уже привязан — подхватывается без
                    # кода); сайт аккаунт не принял — по ключу этого компьютера, как раньше
                    from telegram import SHARED_URL, TelegramAuthError
                    urls = [u for u in (self.s.get("telegram_url"), self.account.service_url("tg"), SHARED_URL) if u]
                    acc = self.account.token() if self.account.logged_in() else ""   # бот аккаунта — только у dwrapp/tg.php
                    errs = []
                    for u in dict.fromkeys(urls):
                        try:
                            try:
                                r = tg.connect_shared(u, acc if ".php" in u else "")
                            except TelegramAuthError:
                                if not acc:
                                    raise
                                r = tg.connect_shared(u)
                            break
                        except TelegramError as e:
                            log.warning("Telegram: %s — %s", u, e)
                            errs.append((u, e))
                    else:
                        from urllib.parse import urlparse
                        u, e = errs[-1]                      # общий адрес — последний, его ошибка самая показательная
                        host = urlparse(u).netloc or u
                        hint = ""
                        if "refused" in str(e).lower() or "name or service" in str(e).lower() or "timed out" in str(e).lower():
                            px = [k for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy") if os.environ.get(k)]
                            hint = (f" Компьютер не смог связаться с {host}. Откройте в браузере этого компьютера {u} — если "
                                    "страница не открывается, дело в сети (фильтр, VPN, роутер)" +
                                    (f"; в системе задан прокси ({px[0]}) — возможно, он не работает" if px else "") + ".")
                        raise TelegramError(f"{e}.{hint}")
                elif cmd == "tg_join":                      # бот аккаунта — подхватить на этом компьютере сейчас (иначе — раз в минуту)
                    self._tg_join()
                    r = tg.public()
                elif cmd == "tg_sync":                      # без компьютера: обменяться с сервером сейчас
                    n = self.tg_sync()
                    r = dict(tg.public(), got=n)
                elif cmd == "tg_set":
                    r = tg.set(a.get("patch") or {})
                    self._tg_sync_soon.set()                # сервер сразу узнает новые настройки (например, «отвечать без компьютера»)
                elif cmd == "tg_proxy":                     # Telegram заблокирован — ходить к нему через прокси
                    r = tg.set_proxy(a.get("proxy", ""))
                elif cmd == "tg_new_code":
                    r = tg.new_code()
                elif cmd == "tg_test":
                    tg.test()
                    r = tg.public()
                elif cmd == "tg_forget":
                    r = tg.forget()
                else:
                    r = tg.public()
            except TelegramError as e:
                raise ValueError(str(e)) from e
            if cmd in ("tg_connect", "tg_connect_shared", "tg_forget", "tg_new_code"):
                self.emit("tools", tools=self.toolbox.catalog())
            return r
        if cmd == "memory_graph":                # «Память»: граф заметок, фактов, дневника, документов, навыков
            from graph import build
            try:
                kfiles = [f["path"] for f in self.knowledge.list()]
            except Exception:  # noqa: BLE001
                kfiles = []
            return build(self.workspace.ensure(), skills=self.skills.catalog(), user_name=self.s.get("user_name") or "",
                         knowledge_files=kfiles)
        if cmd in ("exam_traces", "exam_traces_remove"):   # следы экзамена в «Обо мне», заметках, расходах (examtrace.py)
            import examtrace
            if cmd == "exam_traces":
                return examtrace.find(self.workspace, self.money, self.done)
            n = examtrace.remove(self.workspace, self.money, self.done, list(a.get("items") or []))
            log.info("🧹 записи экзамена убраны: %s", n)     # удаление уйдёт ближайшей синхронизацией — и с телефона тоже
            return {"removed": n}
        if cmd == "exam_history" and os.environ.get("DEWIAR_EXAM_LAUNCH"):
            # экзамен (№625–628): разговор до сценария — как его оставило прошлое (например, перебитый вопрос «Выполнить?»).
            # Только в ядре экзамена (DEWIAR_EXAM_LAUNCH ставит exam.py); строки — {role: user|assistant, content}
            items = [{"role": m["role"], "content": str(m["content"])[:2000], "who": self.s.get("persona")}
                     for m in (a.get("items") or [])[:12] if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
            self.history += items
            self.last_turn_time = time.monotonic()
            return {"added": len(items)}
        if cmd == "persona_memory":               # своя память у персонажа (0.56): {name, own}
            self._prof_snaps = {}                   # чья память в справке — другая: снимки справки прочь (0.87)
            return self.persona_memory_set(str(a.get("name") or ""), bool(a.get("own")))
        who = str(a.get("who") or "") if cmd.startswith("memory_") else ""      # студия: «Общая» или своя память персонажа
        if who and who not in self.own_memory():
            who = ""
        if cmd == "memory_get":
            return self.workspace.memory_get(who=who)
        if cmd == "memory_set":
            return self.workspace.memory_set(a.get("text", ""), who=who)
        if cmd in ("memory_view", "memory_find", "memory_add", "memory_forget"):   # Память 2.0: страницы, поиск по смыслу
            import memory as MEM
            if cmd == "memory_view":
                return dict(MEM.view(self.workspace.memory_get(who=who)), last=getattr(self, "_mem_last", None), who=who, own=self.own_memory())
            if cmd == "memory_find":
                return MEM.find(str(a.get("q") or ""), self.workspace.memory_get(who=who))
            if cmd == "memory_add":
                return self.workspace.remember(str(a.get("text") or ""), who=who)
            return self.workspace.memory_set(MEM.forget(self.workspace.memory_get(who=who), int(a.get("i", -1))), who=who)
        if cmd.startswith("mm_"):                  # «Музыка»: своя папка (engine_mymusic.py)
            return self.mine_command(cmd, a)
        if cmd.startswith("account_"):           # аккаунт сайта: вход, выход, проверка
            from account import AccountError
            try:
                if cmd == "account_login":
                    self._net_try = a.get("server") or ""       # свой сайт ещё не сохранён в аккаунте — но тоже через прокси (_net_conf)
                    r = self.account.login(a.get("server"), a.get("login"), a.get("password"))
                    self.telegram.refresh_token(self.account.token())

                    def after_login():                     # модели и речь по аккаунту — сами, без настроек (в фоне: ходит в сеть)
                        self._account_cloud()
                        self._ensure_brain("вход аккаунтом")
                    threading.Thread(target=after_login, daemon=True).start()
                elif cmd == "account_logout":
                    st = self.s.get("stt")
                    if st.get("engine") == "remote" and st.get("remote", {}).get("from_account"):
                        self.s.update({"stt": {"engine": self._stt_local(), "remote": {"from_account": False, "api_key": ""}}})
                        self.apply_engines()               # вышли из аккаунта — распознаём снова у себя
                    tt = self.s.get("tts")
                    if tt.get("engine") == "remote" and tt.get("remote", {}).get("from_account"):
                        self.s.update({"tts": {"engine": self._tts_local(), "remote": {"from_account": False, "api_key": ""}}})
                        self.apply_engines()               # и говорим своим голосом
                    if self.s.get("cloud", "account"):         # модели облака были по аккаунту — убираем вместе с ним
                        self.cloud.forget()
                        if self.s.get("stt", "engine") == "remote" and self.s.get("stt", "remote", "cloud"):
                            self.s.update({"stt": {"engine": self._stt_local(), "remote": {"cloud": False}}})
                            self.apply_engines()
                        if self.s.get("tts", "engine") == "remote" and self.s.get("tts", "remote", "cloud"):
                            self.cloud.set_tts(False, self._tts_local())
                            self.apply_engines()
                        self.emit("settings", settings=self.s.snapshot())
                    if self.telegram.uses_account():           # бот аккаунта: этот компьютер выходит, у аккаунта бот остаётся
                        self.telegram.leave()
                        self.emit("telegram", **self.telegram.public())
                    r = self.account.logout()
                elif cmd == "account_stt":                # «Распознавание на сервере Dewiar» — вкл/выкл
                    self.s.update({"stt": {"auto_from": ""}})   # №513: выбрали сами — это уже не временная замена
                    if a.get("on"):
                        url = self.account.service_url("stt")
                        if not url:
                            raise AccountError("на сайте нет распознавания речи (или не выполнен вход)")
                        self.s.update({"stt": {"engine": "remote", "remote": {"base_url": url, "api_key": self.account.token(),
                                                                              "model": "gigaam-v3", "language": "ru",
                                                                              "from_account": True}}})
                    else:
                        self.s.update({"stt": {"engine": self._stt_local(), "remote": {"from_account": False}}})
                    self.apply_engines()
                    self.emit("settings", settings=self.s.snapshot())
                    r = self.account.status()
                elif cmd == "account_tts":                # «Голос с сервера Dewiar» — вкл/выкл
                    if a.get("on"):
                        url = self.account.service_url("tts")
                        if not url:
                            raise AccountError("на сайте нет синтеза речи (или не выполнен вход)")
                        self.s.update({"tts": {"engine": "remote", "remote": {
                            "base_url": url, "api_key": self.account.token(), "model": a.get("model") or "",
                            "sample_rate": 24000, "from_account": True}}})
                    else:
                        self.s.update({"tts": {"engine": self._tts_local(), "remote": {"from_account": False}}})
                    self.apply_engines()
                    self.emit("settings", settings=self.s.snapshot())
                    r = self.account.status()
                elif cmd == "account_check":
                    r = self.account.check()
                elif cmd == "account_ask":
                    return self.account.ask(a.get("question", ""))
                else:
                    r = self.account.status()
            except AccountError as e:
                raise ValueError(str(e)) from e
            self.emit("account", account=r)
            self.emit("tools", tools=self.toolbox.catalog())
            return r
        return NotImplemented
