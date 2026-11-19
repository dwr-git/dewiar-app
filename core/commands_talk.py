"""Команды окон (студия, виджет, телефон): разговор и голос: выход, «скажи», снимок экрана в разговор, обучение имени, камеры, игры, кнопка
микрофона, «Чат», стоп и тишина, отдых, «отвечать текстом», безопасность, персонажи, галерея.
Часть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки
проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from engine_chat import CHAT_CMDS


class TalkCommands:
    def _cmd_talk(self, cmd, a):
        if cmd == "quit":                       # «Выход» из значка в трее (Windows): ядро завершается само, чуть позже — чтобы успеть ответить
            if self.on_quit:
                threading.Timer(0.2, self.on_quit).start()
            return True
        if cmd == "say":
            if getattr(self, "lat", None) is not None:
                self.lat.drop()                  # набранный вопрос — не голосовой: задержку голоса не меряем
            # картинки (вставленные, снимок экрана) — как файлы: сохраняются во «Входящие» и видны в ленте «Чата»
            images = []
            files = list(a.get("files") or [])
            for k, im in enumerate(([a["image"]] if a.get("image") else []) + list(a.get("images") or [])):
                mime = im[5:im.index(";")] if im.startswith("data:") and ";" in im[:40] else "image/jpeg"
                ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(mime, ".jpg")
                files.append({"name": time.strftime("Картинка %d.%m %H-%M-%S") + (f" ({k + 1})" if k else "") + ext, "b64": im})
            text = a.get("text", "")
            # №491 (ПК 0.76): на «Выполнить?» набрали «давай» — это ушло новым вопросом, ход с вопросом отменился, а
            # подтверждение засчиталось как «нет». Короткий набранный ответ, пока ждём «да/нет», — ответ на вопрос
            if self.pending_confirm and not files and text.strip() and len(re.findall(r"[\wё]+", text)) <= 8 \
                    and self._answer_confirm(text):
                log.info("Подтверждение набрано: «%s»", text.strip()[:30])
                return True
            if not files and self._task_reply(text):
                return True                      # №551: задача спросила — набранный ответ уходит ей
            if files and text.strip() and self._reminder_with_files(text, files):
                return True                      # «напомни завтра в 10» + снимки — напоминание с картинками, без модели
            if files:
                text = self._attach_files(text, files, images)
            if text.strip() or images:
                self._chat_keep_partial(self.turn)        # новый вопрос посреди ответа — написанное остаётся в ленте
            self.ask(text, images)
            return True
        if cmd == "screenshot_attach":               # кнопка «снимок экрана» в поле вопроса
            from eyes import EyesError, capture_screen, prepare
            from tools import desktop_env
            try:
                b64, _, _ = prepare(capture_screen(desktop_env()))
            except EyesError as e:
                raise ValueError(str(e)) from e
            return "data:image/jpeg;base64," + b64
        if cmd == "calib_start":
            pid = a.get("persona") or self.s.get("persona")
            p = self.personas.get(pid)
            self.cancel_turn()
            self.calib = {"pid": pid, "name": p["name"], "samples": [], "need": int(a.get("n", 3))}
            self.follow_up_until = 0
            self.set_state("listening")
            self.emit("calib", step="listen", n=0, need=self.calib["need"], name=p["name"])
            return True
        if cmd == "calib_cancel":
            self.calib = None
            self.set_state("idle")
            return True
        if cmd == "calib_reset":
            self.personas.set_heard(a.get("persona") or self.s.get("persona"), {})
            self.voiceprints.forget(a.get("persona") or self.s.get("persona"))
            self.build_spotter()
            self.emit("personas", personas=self.personas.public())
            return True
        if cmd == "cameras":
            from eyes import list_cameras
            return list_cameras()
        if cmd == "game_mark":                          # «Досуг» открыл игру (pad.js gameOpen) или закрыл её (game: "")
            gm = str(a.get("game") or "")[:20]
            self._game_on = (gm, time.monotonic()) if gm else None
            return {"game": gm}
        if cmd == "game_say":                           # игра сказала итог хода («Бэ пять — мимо. Стреляю: …») — вслух, без модели
            said = getattr(self, "_game_said", "") or "«Морской бой»"
            self._game_said = ""
            self._say_quick(str(a.get("text") or "")[:400], said, keep=False)
            return True
        if cmd == "ptt":
            # 28.10 (владелец, Ubuntu): «сработала сама, я быстро жму на аватарку, а она ещё 1–2 раза пытается слушать».
            # Судорожные нажатия: первое останавливало, а следующее попадало в «тишину» и снова включало слушание; голос из
            # того же разговора будил её опять. Теперь: нажатие в течение PTT_CALM с после остановки — тоже «стоп»; слушание
            # или ответ, начатые голосом, остановили кнопкой — минуту не откликаемся на голос (кнопка работает всегда).
            now = time.monotonic()
            if now - getattr(self, "_ptt_stop_at", 0.0) < self.PTT_CALM and self.state not in ("speaking", "thinking", "listening"):
                self._ptt_stop_at = now
                return "sleep"
            if getattr(self, "resting", lambda: False)():    # «Отдых»: нажали на лицо — вернулась и слушаю (№540)
                self.rest_end("лицо")
            if self.muted and self.state not in ("speaking", "thinking"):
                self._mute_pass = True                      # нажали «говорить» при выключенном микрофоне — одна фраза, и снова тихо
                self._mic_kick_now()                        # №622: микрофон закрыт — открыть для этой фразы
            if self.state in ("speaking", "thinking", "listening"):
                self._ptt_stop_at = now
                by_voice = now - (getattr(self, "wake_time", 0.0) or 0.0) < 25   # начато голосом, а не кнопкой
                if self.state == "listening":
                    self.go_sleep("кнопка", media=False)     # второе нажатие — перестать слушать
                else:
                    self.interrupt("кнопка", follow=False)   # быстро нажал — замолчал и уснул
                    self.follow_up_until = 0.0
                    self.play_tone("sleep")
                if by_voice:
                    # почти наверняка ложное срабатывание (фон, разговор рядом, видео): минуту не просыпаемся от голоса,
                    # иначе тут же «опять начинает» (отзывы 14.10 и 28.10). Кнопка — работает.
                    self._quiet_until = now + 60
                    if hasattr(self, "_wake_was_false"):
                        self._wake_was_false("остановили кнопкой")
                    self.wake_time = 0.0
                    log.info("🤫 Остановили кнопкой то, что началось по голосу, — минуту не откликаюсь на голос")
                    quiet = "Минуту не откликаюсь на голос — позвать можно нажатием на лицо."
                    self.note(quiet)

                    def unquiet():
                        if self.status.get("note") == self._g(quiet):
                            self.note("")
                    threading.Timer(60, unquiet).start()
                return "sleep"
            self.listen_for_command()                    # №514: сколько ждать — как выбрано в «Слухе»
            return "listening"
        if cmd == "chat_list":                            # «Чат» студии: лента переписки, старые сверху; before — подгрузить раньше
            return self.chatlog.page(a.get("before"), int(a.get("limit") or 80), str(a.get("q") or ""))
        if cmd == "chat_clear":
            self.chatlog.clear()
            return True
        if cmd.startswith("chat_") and cmd in CHAT_CMDS:   # «Ещё раз», «Изменить», беседы, выгрузка (engine_chat.py)
            return self.chat_cmd(cmd, a)
        if cmd == "hold_start":                           # диктовка удержанием: держат кнопку или пробел — говорят сколько нужно
            return self.hold_start(int(a.get("back_ms") or 400), int(a.get("max_s") or 600))
        if cmd == "hold_end":
            return self.hold_end(bool(a.get("cancel")))
        if cmd == "stop":
            self._chat_keep_partial(self.turn)            # написанное до «Стоп» — в ленту «Чата» с пометкой «остановлено»
            self.interrupt("кнопка", follow=False)
            return True
        if cmd == "mute":
            if not a.get("on") and getattr(self, "resting", lambda: False)():          # «Отдых»: включили микрофон — значит, вернулись (№540)
                self.rest_end("кнопка")
                return self.muted
            return self._mute_keep(self.set_mute(bool(a.get("on"))))
        if cmd == "mute_toggle":                          # сочетание «Позвать Лиру» в режиме «микрофон вкл/выкл» (идея №154)
            if self.muted and getattr(self, "resting", lambda: False)():
                self.rest_end("кнопка")
                return self.muted
            return self._mute_keep(self.set_mute(not self.muted))
        if cmd in ("rest", "rest_end", "rest_toggle", "rest_state"):   # «Отдых» (engine_rest.py, №540)
            return self.rest_cmd(cmd, a)
        if cmd == "text_mode":
            # YouTube 26.10: «выключил микрофон и синтез речи… для чисто текстового режима не очень удобно — добавить
            # переключение в текстовый режим (без распознавания, без синтеза, с инструментами в чате)». Включили —
            # микрофон и голос выключены (прежний голос запомнен), вопросы «выполнить?» и шаги — в «Чате» студии.
            on = bool(a.get("on"))
            ui = self.s.get("ui") or {}
            if on:
                prev = self.s.get("tts", "engine")
                self.s.update({"ui": {"text_mode": True, "text_prev": prev if prev and prev != "off" else (ui.get("text_prev") or "")},
                               "tts": {"engine": "off"}})
                self.set_mute(True)
                log.info("⌨ Текстовый режим включён — голос и микрофон выключены (прежний голос: %s)", prev or "—")
            else:
                log.info("🔊 Текстовый режим выключен — голос (%s) и микрофон снова включены", ui.get("text_prev") or self._tts_local())
                self.s.update({"ui": {"text_mode": False}, "tts": {"engine": ui.get("text_prev") or self._tts_local()}})
                if self.s.get("privacy", "mic") != "button":
                    self._mute_keep(self.set_mute(False))
                if not getattr(self.stt, "ready", True):        # распознавание в текстовом режиме не грузили (№876) — теперь
                    threading.Thread(target=self._background_loads, name="loader", daemon=True).start()
            try:
                self.apply_engines()
            except Exception as e:  # noqa: BLE001
                log.info("Движки после текстового режима: %s", e)
            self.emit("settings", settings=self.s.snapshot())
            return {"on": on, "tts": self.s.get("tts", "engine")}
        if cmd == "security_state":                       # студия → «Безопасность»: стоп-кран, схема, замки, журнал (security.py)
            import security
            return security.state(self)
        if cmd == "security_set":
            import security
            r = security.set_(self, a)
            self.apply_engines()
            self.emit("settings", settings=self.s.snapshot())
            self.emit("security", local_only=r["state"]["local_only"])
            return r
        if cmd == "persona_set":
            self.switch_persona(a["id"])
            return True
        if cmd == "persona_save":
            pid = self.personas.save(a["persona"])
            p = self.personas.get(pid)
            miss = missing_words(self.vosk_dir, p.get("wake", [])) if self.vosk_dir else []   # слух ещё не готов — проверим потом
            self.build_spotter()
            self.emit("personas", personas=self.personas.public())
            if any(b.get("kind") == "folder" for b in p.get("knowledge") or []) and getattr(self, "knowledge", None) is not None:
                self.knowledge.kick.set()                  # папку со знаниями персонажа — прочитать сразу
            return {"id": pid, "missing": miss}
        if cmd == "gallery":
            return self.personas.gallery()
        if cmd == "gallery_add":
            pid = self.personas.gallery_add(a.get("id", ""))
            self.build_spotter()
            self.emit("personas", personas=self.personas.public())
            threading.Thread(target=self.ensure_voice, args=(pid,), daemon=True).start()
            return {"id": pid, "gallery": self.personas.gallery()}
        if cmd == "persona_delete":
            self.personas.delete(a["id"])
            # разговор удалённого — в архив: новый персонаж с тем же именем (и тем же id) начнёт с чистого листа
            for m in self.history:
                if m.get("who") == a["id"]:
                    m["who"] = a["id"] + "~удалён"
            try:
                self.conv.save(self.history)
            except Exception:  # noqa: BLE001
                pass
            if self.s.get("persona") not in {p["id"] for p in self.personas.all()}:
                from personas import DEFAULT
                self.switch_persona(DEFAULT)
            self.build_spotter()
            self.emit("personas", personas=self.personas.public())
            return True
        return NotImplemented
