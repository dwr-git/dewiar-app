"""Движок Dewiar: команды из интерфейса (студия, виджет, телефон).
Примесь класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
command(cmd, a) — единый разбор: bridge.py вызывает его по WebSocket в пуле потоков (одновременно может идти
несколько команд); ответ уходит окну как данные, ValueError — как текст ошибки для человека. Имена команд
совпадают с вызовами в ui/ (студия, виджет); новую команду добавляйте и сюда, и туда.
Многие команды лишь передают работу службам (reminders, money, telegram, cloud…) и шлют событие для обновления окна."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from engine_chat import CHAT_CMDS  # noqa: F401
from commands_work import WorkCommands
from commands_sync import SyncCommands
from commands_services import ServicesCommands
from commands_account import AccountCommands
from commands_talk import TalkCommands
from commands_brain import BrainCommands
from commands_files import FilesCommands
from commands_tasks import TasksCommands


# Детский режим (kids.py): пока родитель не ввёл PIN, окна не могут менять настройки и делать взрослое
_KIDS_LOCKED = ("lnet_share", "lnet_invite", "lnet_pause", "lnode_join", "lnode_set", "lnode_leave", "lnode_check", "council_", "podcast_", "pbot_", "mailing_", "crm_", "sitechat_", "sites_", "account_", "backup_", "mode_set", "senior_", "notes_import", "watch_add", "homelan_set", "ideas_new", "homelan_pair", "homelan_forget", "home_forget", "cal_add", "cal_remove", "cloud_connect", "own_fallback", "cloud_forget", "cloud_model", "cloud_topup",
                "config_", "const_", "gallery_add", "ha_connect", "ha_forget", "home_connect", "home_forget", "job_", "knowledge_add",
                "knowledge_remove", "knowledge_folder", "llm_", "mail_", "max_", "memory_forget", "memory_set", "money_",
                "net_dewiar", "net_proxy", "net_reserve", "sshlink_", "obsidian_", "pay_", "persona_", "plugin", "prompter_", "quit",
                "security_set", "server_", "skill_", "soul_save", "soul_update", "soul_delete", "sync_set", "sync_e2e", "tg_", "tools",
                "vault_", "ws_delete", "ws_set_path", "ws_move", "text_mode", "mm_folder", "radio_custom_add", "radio_custom_del",
                "report_auto", "power_cancel", "fam_", "join_", "ref_use", "exam_traces_remove", "chat_clear", "chat_thread", "chat_export", "chat_regen", "chat_edit", "diary_", "update_install", "team_", "client", "device_", "pair_", "brains_pull", "morning_", "month_", "ocr_install")


def _kids_blocked(cmd, a):
    """Можно ли это окнам в детском режиме без PIN: настройки — только положение и вид окон (ui) и «отвечать текстом»."""
    if cmd == "settings_save":
        patch = (a or {}).get("patch") or {}
        return not all(k == "ui" or (k == "tts" and set(v or {}) <= {"text_only"}) for k, v in patch.items())
    if cmd == "lnet_info" and (a or {}).get("trust_new"):
        return True                                    # «Доверять новому ключу» Сети Лиры — только взрослому
    return cmd.startswith(_KIDS_LOCKED)


# порядок разбора — как был в одном command(): первая тема, знающая команду, и отвечает
_PARTS = (WorkCommands._cmd_work, SyncCommands._cmd_sync, ServicesCommands._cmd_services, AccountCommands._cmd_account,
          TalkCommands._cmd_talk, BrainCommands._cmd_brain, FilesCommands._cmd_files, TasksCommands._cmd_tasks)


class CommandsMixin(WorkCommands, SyncCommands, ServicesCommands, AccountCommands, TalkCommands, BrainCommands, FilesCommands, TasksCommands):




    PTT_CALM = 2.5                     # с: нажатие на лицо сразу после «стоп» — тоже «стоп» (судорожные нажатия, 28.10)

    # ---------- команды из интерфейса ----------

    def switch_persona(self, pid):
        if pid not in {p["id"] for p in self.personas.all()}:
            raise ValueError("нет такого персонажа")
        kids = getattr(self, "kids", None)
        if kids and kids.on() and pid != kids.conf().get("persona"):
            log.info("Детский режим: переход к «%s» не делаю — отвечает только друг ребёнка", pid)
            return
        self.s.update({"persona": pid})               # разговор общий: новый персонаж знает, что было
        if not self.s.get("all_names"):
            self.build_spotter()
        self.emit("persona", persona=pid)
        self.set_state(self.state)                    # событие «state» несёт и персонажа — окна обновятся
        threading.Thread(target=self.ensure_voice, args=(pid,), daemon=True).start()

    # ---------- детский режим (kids.py) ----------

    def kids_public(self, light=False):
        """Состояние для окон; light — без портрета друга (событие после каждого вопроса)."""
        k = self.kids
        c = k.conf()
        ok, why = k.allowed_now()
        from kids import ALLOW
        from personas import GALLERY
        return {"on": k.on(), "has_pin": k.has_pin(), "locked": k.locked(), "unlocked": k.unlocked(),
                "child": c.get("child") or {}, "persona": c.get("persona"), "allow": c.get("allow"), "allow_names": ALLOW,
                "min_weekday": c.get("min_weekday"), "min_weekend": c.get("min_weekend"), "bedtime": c.get("bedtime"),
                "morning": c.get("morning"), "used": k.used_today(), "limit": k.limit_today(), "left": k.left_today(),
                "can_talk": ok, "why": why} | ({} if light else {"friend": self.personas.avatar_data_url({"id": c.get("persona") or "ugo"}),
                "friend_name": (self.personas.items.get(c.get("persona")) or GALLERY.get(c.get("persona") or "") or {}).get("name") or "Совёнок Уго"})

    def kids_cmd(self, cmd, a):
        """kids_get — состояние и отчёт; kids_pin {pin, old}; kids_unlock {pin}; kids_lock; kids_on {on, pin};
        kids_set {child, allow, min_weekday, min_weekend, bedtime, morning} — настройки (режим выключен или открыт PIN)."""
        k = self.kids
        if cmd == "kids_get":
            return dict(self.kids_public(), report=k.report() if (not k.on() or k.unlocked()) else None)
        if cmd == "kids_unlock":
            k.unlock(a.get("pin"))
        elif cmd == "kids_lock":
            k.lock()
        elif cmd == "kids_pin":
            k.set_pin(a.get("pin"), a.get("old", ""))
        elif cmd == "kids_on":
            if a.get("on"):
                pid = k.conf().get("persona") or "ugo"
                if pid not in {p["id"] for p in self.personas.all()}:
                    self.personas.gallery_add(pid)          # друг ребёнка ставится сам, в общей галерее его нет
                    self.emit("personas", personas=self.personas.public())
                k.set_on(True)
                self.switch_persona(pid)
                self.build_spotter()                        # слушаем только его имя
                log.info("🧸 Детский режим включён")
            else:
                prev = k.set_on(False, a.get("pin", ""))
                if prev and prev in {p["id"] for p in self.personas.all()}:
                    self.switch_persona(prev)
                self.build_spotter()
                log.info("🧸 Детский режим выключен")
        elif cmd == "kids_set":
            if k.locked():
                raise ValueError("Детский режим: сначала PIN родителя")
            from kids import ALLOW
            patch = {}
            if "child" in a:
                ch = a.get("child") or {}
                patch["child"] = {"name": str(ch.get("name") or "")[:40], "age": int(ch.get("age") or 0) or None}
            if "allow" in a:
                patch["allow"] = [x for x in (a.get("allow") or []) if x in ALLOW]
            for f, lo, hi in (("min_weekday", 0, 600), ("min_weekend", 0, 600)):
                if f in a:
                    patch[f] = max(lo, min(hi, int(a.get(f) or 0)))
            for f in ("bedtime", "morning"):
                if f in a:
                    v = str(a.get(f) or "")
                    if v and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
                        raise ValueError("время — в виде 20:30")
                    patch[f] = v
            self.s.update({"kids": patch})
        else:
            raise ValueError(f"неизвестная команда {cmd}")
        st = self.kids_public()
        self.emit("kids", **st)
        return st

    def _kids_alert(self, text):
        """Просьба вне правил в детском режиме — родителю в Telegram (если бот подключён); в отчёте она уже есть."""
        tg = getattr(self, "telegram", None)
        name = ((self.kids.conf().get("child") or {}).get("name") or "Ребёнок")
        log.info("🧸 Вне правил: %s", redact(text[:80]))
        if tg is not None and getattr(tg, "paired", lambda: False)():
            try:
                tg.send(f"🧸 Детский режим: {name} попросил(а) то, что нельзя: «{text[:120]}». Совёнок отказал и "
                        "предложил спросить вас. Весь разговор — студия → «Дети».")
            except Exception:  # noqa: BLE001
                log.debug("детский режим: Telegram", exc_info=True)

    # ---------- семейный бюджет (family.py) ----------

    def family_cmd(self, cmd, a):
        """fam_get — всё для раздела «Семья» и кого можно позвать (из «Близких»); fam_invite/fam_accept/fam_leave {pid};
        fam_bill {id?, name, amount, due, payer}; fam_paid {id, paid}; fam_bill_del {id}; fam_remind {id};
        fam_limit {v}; fam_share {on}."""
        from close import CloseError
        from family import FamilyError
        F = self.family
        try:
            if cmd == "fam_get":
                people = []
                try:
                    people = [{"pid": p["pid"], "name": p["name"]} for p in (self.close.state().get("people") or [])]
                except Exception:  # noqa: BLE001 — «Близкие» без входа или без связи: список пуст
                    pass
                return dict(F.public(a.get("month")), people=people)
            if cmd == "fam_invite":
                return F.invite(str(a.get("pid") or ""))
            if cmd == "fam_accept":
                return F.accept(str(a.get("pid") or ""))
            if cmd == "fam_leave":
                return F.leave(str(a.get("pid") or ""))
            if cmd == "fam_bill":
                F.bill_save(a)
            elif cmd == "fam_paid":
                F.bill_paid(str(a.get("id") or ""), a.get("paid", True) is not False)
            elif cmd == "fam_bill_del":
                F.bill_delete(str(a.get("id") or ""))
            elif cmd == "fam_remind":
                F.remind(str(a.get("id") or ""))
            elif cmd == "fam_limit":
                F.set_limit(a.get("v"))
            elif cmd == "fam_share":
                F.set_share(a.get("on"))
            else:
                raise ValueError(f"неизвестная команда {cmd}")
        except (FamilyError, CloseError) as e:
            raise ValueError(str(e)) from e
        return F.public()

    # ---------- «Команда»: поручения сотрудникам в Telegram (team.py) ----------




    # ---------- окно голосом: «спрячься», «покажись», «отключись» ----------







    # ---------- «Вырезать кусок экрана» и распознавание текста (идеи №83 и №68, 03.11) ----------
    # Окно выделения (ui/snip.html, ui/app.py snip_open) берёт снимок экрана здесь (snip_shot) и присылает рамку
    # (snip_done): вырезанное ложится картинкой во вкладку блокнота, текст распознаётся (core/ocr.py) в фоне и приходит
    # событием «snip»: блокнот вставляет его под картинкой, виджет кладёт в буфер обмена. Блокнот не открылся (виджет в
    # трее) — через SNIP_KEEP с ядро допишет картинку и текст во вкладку само.
    SNIP_KEEP = 25.0







    # «Морской бой» голосом (0.63; план «Идей Лиры»: «„Б пять!“ — Лира ставит выстрел сама и отвечает голосом»): пока игра
    # открыта в «Досуге» (pad.js шлёт game_mark), короткая фраза с клеткой («бэ пять», «Д7», «стреляю в ка десять») или
    # словом игры («сдаюсь», «ещё партию») — не вопрос модели, а ход: событие game -> игра; итог она скажет через game_say.
    SEA_CELL_RX = re.compile(r"(?:^|[^а-я])(?:а|бэ?|бе|вэ?|ве|гэ?|ге|дэ?|де|е|жэ?|же|зэ?|зе|и|ка?|й)\s*-?\s*(?:10|[1-9]|один|одна|раз|два|две|три|"
                             r"четыре|пять|шесть|семь|восемь|девять|десять)(?![а-я0-9])")
    SEA_CMD_RX = re.compile(r"^(?:\w+,\s*)?(?:сдаюсь|сколько(?:\s+у\s+(?:тебя|нас|меня))?\s+(?:кораблей|осталось)|играем|давай\s+ещ[её]|ещ[её]\s+(?:партию|раз(?:ок)?)|"
                            r"новая\s+(?:партия|игра)|сыграем\s+ещ[её]|начинаем|поехали|(?:давай\s+)?полегче|в\s+полную\s+силу)$")

    def _game_voice(self, text):
        g = getattr(self, "_game_on", None)
        if not g or g[0] != "sea" or time.monotonic() - g[1] > 3 * 3600:
            return False
        t = text.lower().replace("ё", "е").strip(" .!?…")
        if len(t.split()) > 7 or not (self.SEA_CELL_RX.search(t) or self.SEA_CMD_RX.match(t)):
            return False
        log.info("🎮 «Морской бой»: %s", text)
        self._game_said = text
        self.emit("game", game="sea", text=text)
        return True

    def _window_cmd(self, text):
        """Фраза про само окно (window_phrase) -> True, если это она. Прячет и показывает виджет интерфейс
        (событие «window» ловит ui/hud.html); «отключись» — интерфейс завершает и себя, и ядро (Api.quit_all в
        ui/app.py). Интерфейса нет — «покажись» его открывает, «отключись» завершает только ядро."""
        kind = window_phrase(text)
        if not kind:
            return False
        ui = bool(self.bridge.clients)
        if kind == "tray":
            if not ui:
                self._say_quick("Виджета на экране и так нет. Я слушаю — позовите по имени.", text)
                return True
            self._tray_at = time.monotonic()            # спрятали — не заговаривать первой (_welcome_back)
            self._say_quick("Прячусь. Позовёте по имени — появлюсь.", text, then=lambda: self.emit("window", do="tray"))
        elif kind == "play":                             # «Досуг» (24.10): полка игр в листе у виджета
            if (self.s.get("features") or {}).get("games") is False:
                self._say_quick("Игры сейчас выключены. Включить — в студии, раздел «Возможности» → «Досуг».", text)
            elif not ui:
                self._say_quick("Игры открываются в окне Dewiar, а его сейчас нет на экране. Скажите «покажись» — и снова «давай поиграем».", text)
            else:
                game = play_game(text)
                names = {"snake": "Змейку", "racer": "Гонку", "bricks": "Кирпичики", "plane": "Небесного пилота", "bip": "Бипа",
                         "blocks": "Тетрис", "candy": "Конфетки", "merge": "Слияние", "sudoku": "Судоку", "fifteen": "Пятнашки", "reversi": "Реверси", "sea": "«Морской бой»",
                         "tictac": "Крестики-нолики", "crossword": "Кроссворд", "words": "«Пять букв»", "glow": "«Огонька»", "five": "«Пять в ряд»", "pairs": "«Найди пару»",
                         "farm": "«Хутор Одуванчик»", "dark": "«Кто боится темноты»", "post": "«Колючую почту»", "pinball": "«Звёздный пинбол»", "doodle": "«Каляку»", "hop": "«Выше облаков»", "basket": "«Лукошко»"}
                say = f"Открываю {names[game]}." if game else "Давайте! Выбирайте игру."
                self.emit("window", do="play", game=game)  # сразу: игра — это и есть ответ (экзамен 25.10 не видел, что она открылась)
                self._say_quick(say, text)
        elif kind == "snip":                             # «вырежи кусок экрана» (идея №83) — окно выделения у интерфейса
            if not ui:
                self._say_quick("Вырезать кусок экрана можно, когда Dewiar на экране. Скажите «покажись» — и ещё раз.", text)
            else:
                self.emit("window", do="snip")
                self._say_quick("Выделите мышкой нужный кусок экрана.", text)
        elif kind == "show":
            if ui:
                self._say_quick("Я здесь.", text, then=lambda: self.emit("window", do="show"))
            else:
                self._say_quick("Открываю.", text, then=self._ui_launch)
        else:
            where = "значок Dewiar в меню «Пуск»" if os.name == "nt" else "Dewiar в меню приложений"
            log.info("⏻ «%s» — выхожу из Dewiar", redact(text))
            self._say_quick(f"Отключаюсь. Включить снова — {where}.", text, then=self._voice_quit)
        return True

    def _voice_quit(self):
        """«Отключись» сказано: интерфейс получает «window: quit» и завершает всё сам. Интерфейса нет или он не
        справился за 4 с — ядро завершается само (служба systemd с Restart=on-failure после обычного выхода не
        поднимается; при следующем входе в систему или запуске Dewiar из меню — снова работает)."""
        self.emit("window", do="quit")
        if self.on_quit:
            threading.Timer(0.3 if not self.bridge.clients else 4.0, self.on_quit).start()

    def _ui_wake(self):
        """Имя услышано, а окна нет: интерфейс завершился (упал, его закрыли извне) — открыть его,
        чтобы ответ было видно. Только если интерфейс в этом запуске уже был (ядро без окон, например на сервере,
        окна не открывает) и не чаще раза в 30 с."""
        b = getattr(self, "bridge", None)
        if b is None or b.clients or not getattr(b, "seen", False):
            return
        now = time.monotonic()
        if now - getattr(self, "_ui_launched", -1e9) < 30:
            return
        self._ui_launched = now
        threading.Thread(target=self._ui_launch, daemon=True).start()

    def _ui_launch(self):
        """Открыть интерфейс (виджет) отдельным процессом -> True, если запущен. Linux: пускач /opt/dewiar/dewiar
        (он же донастроит службу), из исходников — ui/app.py. Служба systemd --user может не знать DISPLAY —
        тогда берём его из окружения пользовательского systemd (GNOME передаёт его туда при входе).
        Windows: интерфейс сам запускает ядро и следит за ним — отсюда не открываем."""
        if os.name == "nt":
            return False
        import sys
        root = Path(__file__).resolve().parent.parent
        env = dict(os.environ)
        if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
            try:
                out = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True, timeout=5).stdout
                for line in out.splitlines():
                    k, _, v = line.partition("=")
                    if k in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_CURRENT_DESKTOP"):
                        env.setdefault(k, v)
            except (OSError, subprocess.SubprocessError):
                pass
        if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
            log.info("Окно не открыть: нет экрана (DISPLAY)")
            return False
        launcher = root / "dewiar"
        cmd = ["/bin/sh", str(launcher)] if launcher.is_file() else [sys.executable, str(root / "ui" / "app.py")]
        env.pop("DEWIAR_BOX", None)                  # окна сами уйдут в свою коробку с потолком памяти (ui/app.py)
        try:
            import memcap                           # и не в коробке ядра: перезапуск ядра не должен закрывать окна
            subprocess.Popen(memcap.scope_cmd(cmd), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            log.info("Открываю виджет: окна не было")
            return True
        except OSError as e:
            log.warning("Окно не открылось: %s", e)
            return False

    def _mute_keep(self, muted):
        """№649 (ПК 0.84.2, 11.11: «забывает, что микрофон выключен, при перезагрузке компьютера»): выключили кнопкой (или
        сочетанием) — помним и после перезапуска (ui.mic_off; engine.py поднимает с ним). Отдых и текстовый режим — свои."""
        try:
            if bool(self.s.get("ui", "mic_off")) != bool(muted):
                self.s.update({"ui": {"mic_off": bool(muted)}})
        except Exception:  # noqa: BLE001
            log.debug("микрофон: запомнить", exc_info=True)
        return muted

    def set_mute(self, on):
        """Микрофон выключен (кнопка в виджете или замок «Только кнопка» в «Безопасности»): имя не слушается, «говорить» —
        одна фраза."""
        self.muted = bool(on)
        # №410 (29.10): «нажал „заглушить микрофон“, пока ассистент говорит, — озвучка оборвалась». Кнопка — про микрофон:
        # ответ, который уже говорится или думается, договаривается (остановить — кнопка «Стоп»); обрывается только
        # слушание — недоговорённый вопрос
        busy = self.state in ("speaking", "thinking")
        if self.muted and not busy:
            self.cancel_turn()
        self.follow_up_until = 0.0
        if not busy:
            self.set_state("muted" if self.muted else "idle")
        self.emit("muted", on=self.muted)
        if not self.muted and hasattr(self, "_mic_kick_now"):
            self._mic_kick_now()                     # №622: микрофон был закрыт — открыть сразу
        return self.muted

    def snapshot(self):
        """Всё состояние для окна, только что подключившегося к ядру (ответ на «hello»)."""
        try:
            import i18n
            sys_lang = i18n.system_lang()               # «как в системе» для окон (assets/i18n.js; 0.88)
        except Exception:  # noqa: BLE001
            sys_lang = "ru"
        return {"state": self.state, "persona": self.s.get("persona"), "personas": self.personas.public(), "sys_lang": sys_lang,
                "settings": self.s.snapshot(), "status": self.status, "muted": self.muted,
                "presets": LLM_PRESETS, "piper_voices": PIPER_VOICES, "voice_fx": voicefx.catalog(), "workspace": str(self.workspace.root), "tools": self.toolbox.catalog(),
                "version": VERSION, "update": self.updater.public(), "tasks": self.tasks.list(),
                "skills": self.skills.catalog(), "mcp": self.mcp.status(), "account": self.account.status(), "mail": self.mail.public(), "telegram": self.telegram.public(), "max": self.max.public(), "obsidian": self.obsidian.public(),
                "reminders": self.reminders_list(), "alarm": self._alarm_public(),
                "radio": self.radio.status(), "kids": self.kids_public(), "watch": self.watch_public(), "rest": self.rest_public(),
                "pending_import": provision.preview(self.pending_import, self.s.snapshot()) if self.pending_import else None}

    def command(self, cmd, a):
        """Выполнить команду окна cmd с аргументами a. -> данные для ответа; ValueError — понятная ошибка."""
        if cmd.startswith("kids_"):
            return self.kids_cmd(cmd, a)
        if cmd.startswith("fam_") and not (getattr(self, "kids", None) and self.kids.locked()):
            return self.family_cmd(cmd, a)
        kids = getattr(self, "kids", None)
        if kids and kids.locked() and _kids_blocked(cmd, a):
            raise ValueError("Детский режим: это может только взрослый — студия → «Дети», PIN родителя")
        for part in _PARTS:                    # ветки по темам — в модулях commands_*: та же очередь проверок, что была
            r = part(self, cmd, a)             # функцией класса: проверки зовут Engine.command с подставным движком
            if r is not NotImplemented:
                return r
        raise ValueError(f"неизвестная команда {cmd}")
