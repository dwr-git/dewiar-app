"""Движок Dewiar: Telegram и MAX (в том числе обмен с сервером, который отвечает, пока компьютер выключен),
уведомления и речь — озвучка ответа (_speak_worker), выбор голоса, перебивание.
Примесь класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Связи: telegram.py (бот и обмен с сервером), server/dwrapp/tg.php (поля _tg_sync_payload и ответа tg_sync —
общий формат), движки синтеза (Vosk TTS, Piper, eSpeak, удалённый), voicefx.py (эффекты голоса).
Очередь фраз для _speak_worker: строки, None — конец, ("sync", Event) — договорить и отметить событие."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


# Windows: выключен ли системный звук (Core Audio: IMMDeviceEnumerator → вывод по умолчанию → IAudioEndpointVolume) ->
# печатает 1 или 0. Запускается отдельным процессом (_win_muted): ошибка в описании COM не уронит ядро. comtypes — уже
# в сборке Windows (им говорит голос Windows, SAPI).
WIN_MUTE_PY = r"""
import ctypes, comtypes
from comtypes import GUID, COMMETHOD, HRESULT, IUnknown, CLSCTX_ALL
from ctypes import POINTER, c_float, c_uint, c_int, c_void_p
from ctypes.wintypes import BOOL, DWORD
class IAudioEndpointVolume(IUnknown):
    _iid_ = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'RegisterControlChangeNotify', (['in'], c_void_p, 'p')),
        COMMETHOD([], HRESULT, 'UnregisterControlChangeNotify', (['in'], c_void_p, 'p')),
        COMMETHOD([], HRESULT, 'GetChannelCount', (['out'], POINTER(c_uint), 'n')),
        COMMETHOD([], HRESULT, 'SetMasterVolumeLevel', (['in'], c_float, 'l'), (['in'], POINTER(GUID), 'g')),
        COMMETHOD([], HRESULT, 'SetMasterVolumeLevelScalar', (['in'], c_float, 'l'), (['in'], POINTER(GUID), 'g')),
        COMMETHOD([], HRESULT, 'GetMasterVolumeLevel', (['out'], POINTER(c_float), 'l')),
        COMMETHOD([], HRESULT, 'GetMasterVolumeLevelScalar', (['out'], POINTER(c_float), 'l')),
        COMMETHOD([], HRESULT, 'SetChannelVolumeLevel', (['in'], c_uint, 'c'), (['in'], c_float, 'l'), (['in'], POINTER(GUID), 'g')),
        COMMETHOD([], HRESULT, 'SetChannelVolumeLevelScalar', (['in'], c_uint, 'c'), (['in'], c_float, 'l'), (['in'], POINTER(GUID), 'g')),
        COMMETHOD([], HRESULT, 'GetChannelVolumeLevel', (['in'], c_uint, 'c'), (['out'], POINTER(c_float), 'l')),
        COMMETHOD([], HRESULT, 'GetChannelVolumeLevelScalar', (['in'], c_uint, 'c'), (['out'], POINTER(c_float), 'l')),
        COMMETHOD([], HRESULT, 'SetMute', (['in'], BOOL, 'm'), (['in'], POINTER(GUID), 'g')),
        COMMETHOD([], HRESULT, 'GetMute', (['out'], POINTER(BOOL), 'm')),
    ]
class IMMDevice(IUnknown):
    _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
    _methods_ = [COMMETHOD([], HRESULT, 'Activate', (['in'], POINTER(GUID), 'iid'), (['in'], DWORD, 'ctx'),
                           (['in'], c_void_p, 'params'), (['out'], POINTER(POINTER(IUnknown)), 'iface'))]
class IMMDeviceEnumerator(IUnknown):
    _iid_ = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'EnumAudioEndpoints', (['in'], c_int, 'flow'), (['in'], DWORD, 'mask'), (['out'], POINTER(c_void_p), 'devs')),
        COMMETHOD([], HRESULT, 'GetDefaultAudioEndpoint', (['in'], c_int, 'flow'), (['in'], c_int, 'role'), (['out'], POINTER(POINTER(IMMDevice)), 'dev')),
    ]
comtypes.CoInitialize()
en = comtypes.CoCreateInstance(GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}'), IMMDeviceEnumerator, CLSCTX_ALL)
dev = en.GetDefaultAudioEndpoint(0, 1)
vol = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume)
print(1 if vol.GetMute() or vol.GetMasterVolumeLevelScalar() < 0.005 else 0)
"""


class RemoteMixin:
    # ---------- Telegram без компьютера: сервер отвечает сам, напоминания приходят с сервера ----------

    def _tg_sync_payload(self):
        """Что нужно серверу (tg.php), чтобы отвечать, пока компьютер выключен: вход в облако, модель и голос,
        персонаж, часовой пояс, будущие напоминания, списки из «Заметок», последние реплики разговора, ack входящих."""
        from cloud import DEFAULT_URL as CLOUD_URL
        acc_on = self.account.logged_in()
        key = (self.account.token() if acc_on else "") or self.s.get("cloud", "key") or ""
        cloud = self.s.get("cloud", "url") or ""
        if not cloud and acc_on:
            svc = (self.account.data.get("services") or {}).get("cloud") or "/dwrapp/cloud.php"
            cloud = svc if svc.startswith("http") else (self.account.data.get("server") or "https://dewiar.pro").rstrip("/") + "/" + svc.lstrip("/")
        prof = self.s.active_llm() or {}
        model = prof.get("model", "") if (prof.get("cloud") or "cloud.php" in str(prof.get("base_url", ""))) else ""
        p = self.personas.get(self.s.get("persona")) or {}
        off = datetime.now().astimezone().strftime("%z") or "+0300"
        lists = {}
        try:
            for f in sorted((self.workspace.root / "Заметки").glob("[Сс]писок*.md"))[:20]:
                lists[f.stem] = [ln[2:].strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.startswith("- ")][:200]
        except Exception:  # noqa: BLE001
            pass
        hist = [{"role": h["role"], "content": str(h.get("content", ""))[:1500]} for h in self.history[-6:]
                if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str)]
        return {"key": key, "cloud": cloud or (CLOUD_URL if key.startswith("dw-") else ""), "model": model,
                "voice": (p.get("voice") or {}).get("remote", ""), "tz": off[:3] + ":" + off[3:],
                "persona": {"name": p.get("name", ""), "gender": p.get("gender", "male"), "character": p.get("character", "")},
                "offline": self.telegram.data.get("offline", True), "voice_reply": self.telegram.data.get("voice_reply", True),
                "reminders": self.reminders.occurrences(), "lists": lists, "hist": hist,
                "ack": int(self.telegram.data.get("inbox_ack", 0)), "sync_on": self._sync_on()}

    def _sync_on(self):
        """Синхронизация устройств включена и есть чем войти в облако — Telegram кладёт сделанное сразу туда."""
        try:
            return self.s.get("sync", "enabled") is not False and bool(self.credentials()[0])
        except Exception:  # noqa: BLE001
            return False

    def tg_sync(self):
        """Обмен с сервером: отдать напоминания и ключ, забрать сделанное без компьютера. -> сколько пришло.
        Входящие применяются по порядку n и подтверждаются ack; то, что сервер уже положил в синхронизацию
        устройств (synced), не дублируем — оно придёт через sync.py. fired — напоминания, уже присланные сервером."""
        tg = self.telegram
        if not tg.can_sync():
            return 0
        r = tg.sync(self._tg_sync_payload()) or {}
        self._tg_last_sync = time.monotonic()
        self._tg_fired = set(r.get("fired") or [])
        for occ in self._tg_fired:                               # пришли с сервера — сами не повторяем
            self.reminders.done_elsewhere(occ)
        got, ack = collections.Counter(), int(tg.data.get("inbox_ack", 0))
        sync_on, pull = self._sync_on(), False
        for it in sorted(r.get("inbox") or [], key=lambda x: x.get("n", 0)):
            try:
                k = it.get("kind")
                if it.get("synced") and k != "chat" and sync_on:
                    pull = True                                  # уже в синхронизации — придёт оттуда, без дублей
                    got[k] += 1
                elif k == "note":
                    from capture import _title
                    self.workspace.save_note(it.get("title") or _title(it.get("text", "")), it.get("text", ""))
                elif k == "list":
                    self.workspace.list_add(it.get("name") or "список покупок", it.get("items") or [])
                elif k == "reminder":
                    if it.get("id") not in self._tg_fired:              # уже пришло с сервера — не повторяем
                        self.reminders.add(datetime.fromisoformat(it["at"]), it.get("text") or "Напоминание")
                elif k == "cancel":
                    self.reminders.cancel(it.get("id", ""))
                elif k == "chat":
                    self.history += [{"role": "user", "content": it.get("user", "")},
                                     {"role": "assistant", "content": it.get("answer", ""), "who": self.s.get("persona")}]
                if not it.get("synced") or k == "chat" or not sync_on:
                    got[k] += 1
            except Exception as e:  # noqa: BLE001
                log.warning("Telegram, без компьютера: %s не перенёсся: %s", it.get("kind"), e)
            ack = max(ack, int(it.get("n", 0)))
        if pull:
            self.sync.soon.set()
        if ack != int(tg.data.get("inbox_ack", 0)):
            with tg._lock:
                tg.data["inbox_ack"] = ack
                tg._save()
            tg.sync({"ack": ack})                               # забрали — сервер может убрать
        tick = int(r.get("tick_age", -1))                       # сколько секунд назад был ?tick (cron сервера); < 5 мин — напоминания без компьютера идут
        tg.offline_state = {"ok": bool(self._tg_sync_payload()["key"]), "tick": 0 <= tick < 300, "synced": int(time.time())}
        if got:
            what = {"note": "заметки", "list": "списки", "reminder": "напоминания", "chat": "сообщения", "cancel": "отмены"}
            msg = "Пока компьютер был выключен, в Telegram: " + ", ".join(f"{what.get(k, k)} — {n}" for k, n in got.items())
            log.info("✉ %s", msg)
            self.note(msg)
            self.emit("telegram", **tg.public())
        return sum(got.values())

    def _tg_sync_loop(self):
        """Фоновый поток: обмен с сервером раз в минуту или сразу по _tg_sync_soon (изменились напоминания, настройки)."""
        while not self.stopping.is_set():
            try:
                self.tg_sync()
            except Exception as e:  # noqa: BLE001
                log.debug("Telegram: обмен с сервером: %s", e)
            self._tg_sync_soon.wait(60)
            self._tg_sync_soon.clear()
            time.sleep(2)                                        # несколько изменений подряд — одним обменом

    def _tg_fired_elsewhere(self, occ):
        """Опоздавшее напоминание: не прислал ли его уже сервер, пока компьютер был выключен? Если обмена не было
        последние 20 с — обменивается сейчас (сетевой запрос)."""
        if not self.telegram.can_sync():
            return False
        if time.monotonic() - getattr(self, "_tg_last_sync", -1e9) > 20:
            try:
                self.tg_sync()
            except Exception as e:  # noqa: BLE001
                log.debug("Telegram: проверка напоминаний: %s", e)
        return occ in getattr(self, "_tg_fired", set())

    def _on_telegram(self, kind, d):
        self._on_messenger(self.telegram, kind, d)

    def _on_messenger(self, tg, kind, d):
        """События бота Telegram или MAX: подключение, кнопки подтверждения и будильника, «стоп», «статус» и
        сообщение владельца (kind="ask") — оно идёт в тот же разговор, что голосом дома (история общая).
        Голосовое распознаётся здесь же; ответ на голосовое — ещё и голосом, если так настроено."""
        ev = "max" if tg is getattr(self, "max", None) else "telegram"
        if kind == "paired":
            self.emit(ev, **tg.public())
            self.push(f"{tg.TITLE} подключён", f"Пишите ассистенту: {'@' if ev == 'telegram' else ''}{tg.public()['bot']}", telegram=False)
            return
        if kind == "confirm":
            box = self.pending_confirm
            if box:
                box["answer"] = bool(d.get("ok"))
                box["event"].set()
            return
        if kind == "alarm_cb":                       # кнопки под напоминанием: alarm:ack:<id> / alarm:snooze:<id>:<мин>, см. _on_reminder
            parts = d.get("data", "").split(":")
            if len(parts) >= 3:
                if parts[1] == "snooze":
                    r = self.alarm_finish("snooze", int(parts[3]) if len(parts) > 3 else 10, rid=parts[2])
                    tg.send(f"Хорошо, напомню {r['when']}." if r else "Это напоминание уже выключено.")
                else:
                    r = self.alarm_finish("ack", rid=parts[2])
                    tg.send("Готово 👍" if r else "Уже выключено.")
            return
        if kind == "stop":
            self.cancel_turn()
            self.set_state("idle")
            tg.send(self._g("Остановился."))
            return
        if kind == "status":
            prof = self.s.active_llm() or {}
            busy = self.turn is not None
            running = [t for t in self.tasks.list() if t.get("status") in ("running", "waiting", "sleeping")] \
                if hasattr(self, "tasks") and hasattr(self.tasks, "list") else []
            lines = [f"{self.persona_name()} на связи.", f"Мозг: {prof.get('name') or prof.get('model') or 'не подключён'}.",
                     "Сейчас отвечаю на вопрос." if busy else "Сейчас свободен."]
            for t in running[:5]:
                pr = t.get("progress") or [0, 0]
                lines.append(f"• {t.get('title')}: {t.get('status_ru') or t.get('status')}" + (f" ({pr[0]}/{pr[1]})" if pr and pr[1] else ""))
            tg.send(self._g("\n".join(lines)))
            return
        if kind != "ask":
            return
        text = (d.get("text") or "").strip()
        try:
            if d.get("voice"):
                tg.typing()
                heard = self._tg_transcribe(d["voice"])
                if not heard:
                    tg.send(self._g("Не разобрал голосовое — повторите, пожалуйста, или напишите текстом."))
                    return
                tg.send(f"🎙 {heard}")
                text = (text + " " + heard).strip()
        except Exception as e:  # noqa: BLE001
            tg.send(self._g(f"Голосовое не получилось распознать: {e}."))
            return
        if self.pending_confirm and text and self._answer_confirm(text):
            return
        wt = self.tasks.waiting() if text else None
        if wt and time.monotonic() < getattr(self, "tg_task_until", 0):     # фоновая задача спросила в Telegram (ждёт до 6 ч) — это ответ ей
            self.tg_task_until = 0.0
            self.task_answer_until = 0.0
            self.tasks.answer(wt.id, text)
            tg.send(self._g(f"Передал в задачу «{wt.title}»."))
            return
        if text and not d.get("files") and is_sleep_phrase(text):
            if self.alarm:
                self.alarm_finish("ack")
            self.cancel_turn()
            self.set_state("idle")
            tg.send(self._g("Хорошо, молчу."))
            return
        images = []
        if d.get("files"):
            import base64
            files = [{"name": f["name"], "b64": base64.b64encode(f["data"]).decode()} for f in d["files"]]
            text = self._attach_files(text, files, images)
        log.info("✉ %s: %s", tg.TITLE, text[:200])
        tg.typing()

        by_voice = bool(d.get("voice"))

        def done(answer):
            tg.send(answer)
            if by_voice and tg.data.get("voice_reply", True) and not answer.startswith("Не получилось"):
                threading.Thread(target=self._tg_voice_reply, args=(answer, tg), daemon=True).start()
        self.ask(text, images, via={"done": done, "confirm": tg.ask_confirm, "speak": bool(tg.data.get("voice_home")) and not self.server,
                                    "from": tg.TITLE})

    def push(self, title, text="", critical=False, file=None, telegram=True):
        """Уведомление о важном: всплывающее окно системы + событие для виджета и студии + Telegram (с файлом итога)."""
        desktop_notify(f"{title}\n{text}".strip(), critical=critical)
        self.emit("push", title=title, text=text, critical=critical)
        if telegram and self.chat.notify_on():
            threading.Thread(target=self.chat.notify, args=(f"🔔 {title}" + (f"\n{text}" if text else ""),),
                             kwargs={"file": file}, daemon=True).start()
        log.info("🔔 %s — %s", title, text)

    def announce(self, text):
        """Сказать что-то по своей инициативе (напоминание, итог задачи) в фоновом потоке: дождаться (до 60 с),
        пока текущий ответ закончится, сыграть сигнал, сказать и послушать ответ follow_up_seconds."""
        text = self._g(text)
        if getattr(self, "server", False) or getattr(getattr(self, "prompter", None), "on", False):
            # сервер: сказать некому; идёт встреча с суфлёром — вслух нельзя: текстом в окна, телефон и Telegram
            self.emit("answer", text=text, done=True)
            self.push("Dewiar", text)
            return
        def run():
            for _ in range(120):
                if self.turn is None and self.state not in ("thinking", "speaking"):
                    break
                time.sleep(0.5)
            with self._turn_lock:
                self.turn_n += 1
                turn = Turn(self.turn_n)
                self.turn = turn
            q = queue.Queue()
            q.put(text)
            q.put(None)
            self.emit("answer", text=text, done=True)
            self.play_tone("wake")
            time.sleep(0.4)
            self._speak_worker(turn, q)
            self.follow_up_until = time.monotonic() + float(self.s.get("audio", "follow_up_seconds") or 0)
            with self._turn_lock:
                if self.turn is turn:
                    self.turn = None
                    self.set_state("listening")
        threading.Thread(target=run, daemon=True).start()

    def _voice_cfg(self, pid=None):
        """Голос текущего персонажа (или pid) + служебные _gender, _pid и _slot (номер среди персонажей того же пола)."""
        p = self.personas.get(pid or self.s.get("persona"))
        same = [x["id"] for x in self.personas.all() if x.get("gender") == p.get("gender")
                and (x.get("voice") or {}).get("prefer") != "piper"]
        slot = same.index(p["id"]) if p.get("id") in same else 0      # по порядку — разным персонажам разные голоса
        return dict(p.get("voice") or {}, _gender=p.get("gender"), _pid=p.get("id"), _slot=slot)

    def _wait_vosk_tts(self, voice, limit=20.0):
        """Перед первой фразой ответа: если основной голос (Vosk TTS) уже скачан, но ещё загружается — подождать его
        (не меньше 40 с), а не начинать голосом Piper (иначе один ответ одним голосом, следующий — другим)."""
        if self.s.get("tts", "engine") != "vosk" or self.vosk_tts.ready or voice.get("prefer") == "piper":
            return
        if not self.vosk_tts.installed() or self.vosk_tts.error:
            return                                       # ещё не скачан или сломан — говорим Piper
        if not self._vosk_loading:
            self.ensure_vosk_tts()                       # скачан, но ещё не загружали — загрузим сейчас и подождём
        limit = max(limit, 40.0)
        end = time.monotonic() + limit
        while self._vosk_loading and not self.vosk_tts.ready and time.monotonic() < end:
            time.sleep(0.1)

    def _vosk_slow(self, chars, sec):
        """Vosk TTS не успевает за речью (отчёты №121–125, 20.10: 4 ядра и своя модель на процессоре — голоса грузились
        7 минут, фраза из 40 знаков — 5 с, из 120 — 18 с; человек ждёт каждую фразу). Три такие фразы за запуск (или
        одна, если и загрузка шла дольше 4 минут) — переключиться на Piper (он в несколько раз легче) и сказать об этом;
        вернуть — студия → «Голос»."""
        if sec < 4 or sec < 0.08 * chars or self.s.get("tts", "engine") != "vosk":
            return
        n = self._vosk_slow_n = getattr(self, "_vosk_slow_n", 0) + 1
        if n < (1 if getattr(self.vosk_tts, "load_s", 0) > 240 else 3):
            return
        self.s.update({"tts": {"engine": "piper", "auto_piper": int(time.time())}})
        log.warning("Vosk TTS не успевает за речью (фраза из %d симв. — %.1f с, загрузка %.0f с) — голос Piper", chars, sec,
                    getattr(self.vosk_tts, "load_s", 0))
        self.note("Голоса Vosk TTS на этом компьютере не успевают за речью — переключила на Piper: он легче и отвечает сразу. "
                  "Вернуть — студия → «Голос».")
        try:
            self.apply_engines()
            threading.Thread(target=self.ensure_voice, args=(self.s.get("persona"),), name="piper-voice", daemon=True).start()
        except Exception as e:  # noqa: BLE001
            log.info("Движки после смены голоса: %s", e)

    def _engines_for_speech(self, voice=None, force=False):
        """Цепочка синтезаторов по порядку попыток: выбранный → Piper (если голос скачан) → eSpeak. Готовый Vosk TTS —
        единственный: голос персонажа не подменяем. -> [] — речь выключена.
        force — «Прослушать» под ответом: в «Текстовом режиме» (голос выключен, прежний запомнен в ui.text_prev) читаем
        прежним голосом — человек сам попросил вслух (30.10, владелец: «„Прослушать“ тоже не работает»)."""
        eng = self.s.get("tts", "engine")
        remote = self.tts_remote
        if eng == "off":
            prev = ((self.s.get("ui") or {}).get("text_prev") or "") if force else ""
            if not prev or prev == "off":
                return []
            eng = prev
            remote = remote or self._listen_remote(prev)
        chain = []
        voice = voice or self._voice_cfg()
        if eng in ("remote", "elevenlabs") and remote:
            chain.append(remote)
        if eng == "vosk" and self.vosk_tts.ready and not self.vosk_tts.error and voice.get("prefer") != "piper":
            return [self.vosk_tts]                 # голос персонажа один: Vosk не справился с фразой — пропуск, не Piper
        vid = voice.get("piper", "ru_RU-denis-medium")
        if eng in ("piper", "remote", "elevenlabs", "vosk") and self.piper.has(vid):
            chain.append(self.piper)
        if self.espeak.available():
            chain.append(self.espeak)
        return chain

    def _listen_remote(self, eng):
        """Голос сервера или ElevenLabs для «Прослушать», пока сам голос выключен «Текстовым режимом» (держим один)."""
        key = (eng, str(self.s.get("tts", "remote")), str(self.s.get("tts", "eleven")))
        got = getattr(self, "_listen_tts", None)
        if got and got[0] == key:
            return got[1]
        from tts import ElevenTTS, RemoteTTS
        tt = self.s.get("tts") or {}
        t = RemoteTTS(tt["remote"]) if eng == "remote" and (tt.get("remote") or {}).get("base_url") else \
            ElevenTTS(tt.get("eleven") or {}) if eng == "elevenlabs" and (tt.get("eleven") or {}).get("api_key") else None
        self._listen_tts = (key, t)
        return t

    def _remote_voice_down(self, eng, e):
        """Голос сервера не ответил, и фраза ушла запасному голосу. 23.10, владелец: «голос ужасен, что случилось?» —
        служба голосов на сервере молчала полдня, а программа меняла голос молча: человек думал, что сломал что-то у себя.
        Теперь один раз в 2 часа — строка в виджете: голос сервера недоступен, вернётся сам. «Заняты, много людей» —
        дело минут, о нём не пишем."""
        if eng is not getattr(self, "tts_remote", None) or "заняты" in str(e):
            return
        now = time.monotonic()
        if now - getattr(self, "_remote_down_note", -1e9) < 7200:
            return
        self._remote_down_note = now
        self.note("Голос сервера сейчас не отвечает — говорю запасным голосом. Ваш голос вернётся сам, как только сервер "
                  "снова ответит; ничего переключать не нужно.")

    def _synth_mixed(self, eng, text, voice, sp):
        """Синтез фразы: английские обороты и слова — английским голосом Piper, остальное — голосом персонажа (пакет 22.10,
        №194: «произношение фраз на английском — жесть»: русский голос читал их русскими звуками). Голос сервера и
        ElevenLabs многоязычные — им как раньше. Английского голоса ещё нет — один раз скачиваем в фоне, а пока читаем
        по-русски. Частота — как у первого куска (иначе плеер перезапускался бы между кусками)."""
        from tts import LANG_VOICES, resample, split_lang
        parts = split_lang(text) if not isinstance(eng, RemoteTTS) and self.s.get("tts", "english") is not False else [("ru", text)]
        g = "male" if voice.get("_gender") == "male" else "female"
        vid = {lang: LANG_VOICES[lang][g] for lang in LANG_VOICES}
        missing = {lang for lang, _ in parts if lang != "ru" and not self.piper.has(vid[lang])}
        for lang in missing:
            self._en_voice_fetch(vid[lang])
        if all(lang == "ru" or lang in missing for lang, _ in parts):
            yield from eng.synth(pronounce(text, remote=isinstance(eng, RemoteTTS)), voice, sp)
            return
        target = None
        for lang, seg in parts:
            gen = (self.piper.synth(seg.strip(), dict(voice, piper=vid[lang], length_scale=1.0), sp, norm=False)
                   if lang != "ru" and lang not in missing else eng.synth(pronounce(seg), voice, sp))
            for rate, pcm in gen:
                target = target or rate
                yield target, resample(pcm, rate, target)

    def _en_voice_fetch(self, en_id):
        """Скачать голос Piper второго языка (английский, немецкий; ~60 МБ) в фоне — один раз за запуск; стоп-кран «ничего
        в интернет» — не качаем."""
        if not isinstance(getattr(self, "_en_fetching", None), set):
            self._en_fetching = set()
        if en_id in self._en_fetching:
            return
        self._en_fetching.add(en_id)
        import egress

        def run():
            if egress.local_only():
                return
            try:
                if getattr(self.piper, "mirror", None) is None and hasattr(self, "_mirror"):
                    self.piper.mirror = self._mirror("piper")     # со своего сайта, если голос там есть; иначе Hugging Face
                self.piper.ensure(en_id)
                log.info("🗣 Английский голос %s скачан — английские фразы теперь читает он", en_id)
            except Exception as e:  # noqa: BLE001
                log.info("🗣 Английский голос %s не скачался: %s", en_id, e)
        threading.Thread(target=run, name="en-voice", daemon=True).start()

    def _fx_name(self, voice):
        """Обработка голоса: общая настройка «Голос → Эффекты» или своя у персонажа."""
        mode = self.s.get("tts", "fx") or "persona"
        if mode == "persona":
            return voice.get("fx") or "clear"
        return mode

    def _output_muted(self):
        """Звук компьютера выключен или на нуле -> True: синтез (и сервер голосов) не тратим впустую (идея 15.10).
        Linux — PulseAudio/PipeWire (pactl), раз в 5 с. Windows — громкость и «выключено» системного вывода (Core Audio)
        в отдельном процессе раз в 15 с, в фоне: ответ не ждёт проверки, а ошибка или падение COM не трогают ядро.
        Не узнали — False (говорим как обычно). DEWIAR_FAKE_OUTPUT_MUTED=1 — для проверок."""
        if os.environ.get("DEWIAR_FAKE_OUTPUT_MUTED"):
            return os.environ["DEWIAR_FAKE_OUTPUT_MUTED"] == "1"
        if os.name == "nt":
            return self._win_muted()
        now = time.monotonic()
        at, val = getattr(self, "_mute_cache", (-1e9, False))
        if now - at < 5:
            return val
        import shutil
        import sys
        muted = False
        if sys.platform.startswith("linux") and not getattr(self, "server", False) and shutil.which("pactl"):
            try:
                r = subprocess.run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], capture_output=True, text=True, timeout=1.5)
                muted = bool(re.search(r":\s*(yes|да)\b", r.stdout, re.I))
                if not muted:
                    r = subprocess.run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture_output=True, text=True, timeout=1.5)
                    vols = [int(x) for x in re.findall(r"(\d+)%", r.stdout)]
                    muted = bool(vols) and max(vols) == 0
            except (OSError, subprocess.SubprocessError, ValueError):
                muted = False
        self._mute_cache = (now, muted)
        return muted

    def _win_muted(self):
        """Windows: последнее известное состояние звука; устарело (15 с) — обновить в фоне (WIN_MUTE_PY в своём процессе)."""
        at, val = getattr(self, "_mute_cache", (-1e9, False))
        if time.monotonic() - at > 15 and not getattr(self, "_mute_busy", False) and not getattr(self, "server", False):
            self._mute_busy = True

            def check():
                import subprocess
                import sys
                muted = val
                try:
                    exe = sys.executable.replace("pythonw.exe", "python.exe")
                    r = subprocess.run([exe, "-c", WIN_MUTE_PY], capture_output=True, text=True, timeout=8,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
                    out = (r.stdout or "").strip()
                    muted = out == "1" if out in ("0", "1") else False
                except (OSError, subprocess.SubprocessError):
                    muted = False
                self._mute_cache = (time.monotonic(), muted)
                self._mute_busy = False
            threading.Thread(target=check, name="mute-check", daemon=True).start()
        return val

    def _speak_worker(self, turn, sentences, fx_override=None, voice_override=None, force=False):
        """Озвучить фразы из очереди sentences до None или отмены хода (блокирует, зовётся из потока ответа).
        Синтез и звук — в два потока: пока звучит фраза, следующая уже синтезируется (поток speak-synth, опережение —
        до двух фраз). Раньше следующую фразу начинали синтезировать, только когда прошлая доиграла, — на медленном
        компьютере между фразами были паузы в несколько секунд. Весь ответ — одним движком (первым, что справился);
        сказанное копится в turn.spoken — по нему _cancel_locked запоминает, на чём перебили. Ставит состояние «speaking».
        «Отвечать текстом» (tts.text_only, кнопка-динамик в виджете) — молчим: очередь только вычитывается."""
        if self.s.get("tts", "text_only") and not force:     # force — «Прослушать» под ответом: человек сам попросил вслух
            return self._drain_worker(turn, sentences)
        if self._output_muted():                        # звук компьютера выключен — голос не услышат: не синтезируем
            log.info("🔇 Звук компьютера выключен (или на нуле) — отвечаю текстом, голос не синтезирую")
            return self._drain_worker(turn, sentences)
        speed = float(self.s.get("tts", "speed") or 1.0)
        voice = self._voice_cfg()
        if voice_override:
            voice.update(voice_override)
        fx_name = fx_override or self._fx_name(voice)
        pitch = voicefx.pitch_of(fx_name)
        ready = queue.Queue(maxsize=2)                  # готовящиеся фразы: ("say", s, text, chunks) | ("skip", s) | ("sync", ev) | None
        done = threading.Event()                        # звук закончил (отмена или конец) — синтезу больше не ждать

        def put(item):
            while not done.is_set() and not turn.cancel.is_set():
                try:
                    ready.put(item, timeout=0.3)
                    return True
                except queue.Full:
                    continue
            return False

        def synth_all():
            """Поток speak-synth: фразы из sentences → куски звука (rate, pcm) в очередь фразы; None в конце фразы,
            исключение — вместо None, если фраза так и не прозвучала."""
            locked = None                               # движок, которым начали говорить (весь ответ — им)
            try:
                while True:
                    s = sentences.get()
                    if s is None or turn.cancel.is_set() or done.is_set():
                        return
                    if isinstance(s, tuple):            # ("sync", event): договорить и отдать микрофон
                        if not put(("sync", s[1])):
                            return
                        continue
                    text = speakable(s)
                    if not text:
                        continue
                    if time.monotonic() - getattr(self, "_out_fail_at", 0.0) < 30:     # звук только что не открылся — не синтезируем зря
                        if not put(("skip", s)):
                            return
                        continue
                    if locked is None:
                        self._wait_vosk_tts(voice)
                    chunks = queue.Queue()
                    if not put(("say", s, text, chunks)):
                        return
                    for eng in ([locked] if locked is not None else self._engines_for_speech(voice, force)):
                        sent = False
                        try:
                            # высота голоса без отдельной обработки: синтезируем в 1/pitch раз быстрее, а играем с частотой
                            # rate*pitch — темп прежний, голос ниже (pitch < 1) или выше
                            t_syn = time.monotonic()
                            for rate, pcm in self._synth_mixed(eng, text, voice, speed / pitch):
                                if not sent and time.monotonic() - t_syn > 3:   # синтез не успевает за речью (для отчётов)
                                    log.info("🗣 %s: фраза из %d симв. синтезировалась %.1f с", getattr(eng, "name", "голос"), len(text),
                                             time.monotonic() - t_syn)
                                    if eng is self.vosk_tts:
                                        self._vosk_slow(len(text), time.monotonic() - t_syn)
                                sent = True
                                chunks.put((rate, pcm))
                                if turn.cancel.is_set() or done.is_set():
                                    break
                            if eng is self.vosk_tts:
                                self._vosk_fails = 0
                            locked = eng                # весь ответ — одним голосом
                            break
                        except Exception as e:  # noqa: BLE001
                            if locked is not None or sent:      # посреди ответа голос не меняем: пробуем упростить фразу
                                simple = re.sub(r"[^А-Яа-яЁё0-9 ,.!?-]+", " ", text).strip()
                                try:
                                    if simple and simple != text and not sent:
                                        for rate, pcm in eng.synth(pronounce(simple), voice, speed / pitch):
                                            chunks.put((rate, pcm))
                                except Exception as e2:  # noqa: BLE001
                                    log.warning("Синтез %s не справился с фразой, пропускаю её: %s", getattr(eng, "name", eng), e2)
                                locked = eng
                                break
                            if eng is self.vosk_tts:              # основной голос — другим не подменяем
                                log.warning("Vosk TTS не прочитал фразу «%s»: %s — пропускаю её", text[:60], e)
                                self._vosk_fails = getattr(self, "_vosk_fails", 0) + 1
                                if self._vosk_fails >= 4:          # не одна фраза, а голос сломался — дальше говорим Piper
                                    self.vosk_tts.error = str(e)[:200]
                                    self.note("Голоса Vosk TTS не работают — говорю голосами Piper (подробности в журнале)")
                                locked = eng
                                break
                            log.warning("Синтез %s не удался: %s — пробую следующий", getattr(eng, "name", eng), e)
                            self._remote_voice_down(eng, e)
                    chunks.put(None)
                    if turn.cancel.is_set():
                        return
            finally:
                put(None) if not done.is_set() else None

        threading.Thread(target=synth_all, name="speak-synth", daemon=True).start()
        started, fx = False, None

        def flush_fx():
            if fx is not None:
                tail = fx.flush()
                if tail:
                    self.player.write(tail)
        try:
            while True:
                try:
                    item = ready.get(timeout=0.3)
                except queue.Empty:
                    if turn.cancel.is_set():
                        break
                    continue
                if item is None or turn.cancel.is_set():
                    break
                if item[0] == "sync":
                    if started:
                        flush_fx()
                        self.player.finish()
                        started = False
                        self.last_speak_end = time.monotonic()
                    item[1].set()
                    continue
                if item[0] == "skip":
                    turn.spoken.append(item[1])
                    continue
                _, s, text, chunks = item
                self._now_saying = text
                log.debug("🗣 %s", text)
                if self.player is None:                  # микрофон ещё не открылся (или его нет) — голос всё равно нужен
                    self.player = Player(device=self.s.get("audio", "output") or "", on_level=lambda v: self._level(v, "voice"),
                                         null=self.null_player)
                said_mark = False
                try:
                    while True:
                        try:
                            c = chunks.get(timeout=0.3)
                        except queue.Empty:
                            if turn.cancel.is_set():
                                break
                            continue
                        if c is None or turn.cancel.is_set():
                            break
                        rate, pcm = c
                        if not said_mark:
                            self._said.append((time.monotonic(), text))   # для узнавания своего эха — когда фраза зазвучала
                            said_mark = True
                        play_rate = int(round(rate * pitch))
                        if not started:
                            lat = getattr(self, "lat", None)
                            if lat is not None:                  # «Голос без пауз»: первый звук ответа
                                lat.mark("say")
                                rec = lat.done(self._lat_how() if hasattr(self, "_lat_how") else "")
                                if rec:
                                    log.info(lat.line(rec))
                            self.player.start(play_rate)
                            fx = voicefx.VoiceFX(fx_name, rate)
                            started = True
                            self.set_state("speaking")
                        elif play_rate != self.player.rate:
                            flush_fx()
                            self.player.finish()
                            self.player.start(play_rate)
                            fx = voicefx.VoiceFX(fx_name, rate)
                        if not self.player.write(fx.process(pcm) if fx else pcm):
                            break
                    turn.spoken.append(s)
                except AudioOutError as e:            # звук не вывести — дело не в голосе, другие движки не помогут
                    self._out_fail_at = time.monotonic()
                    if time.monotonic() - getattr(self, "_out_note_at", 0.0) > 300:
                        self._out_note_at = time.monotonic()
                        log.warning("Вывод звука не открылся: %s", e)
                        self.note("Звук не выводится: нет устройства вывода или оно занято. Проверьте динамики и выбор "
                                  "устройства в студии («Голос»)" + (" и доступ к звуку в Windows" if os.name == "nt" else "") + ".")
                    turn.spoken.append(s)             # текст на экране остаётся; дальше не пытаемся на каждой фразе
                if turn.cancel.is_set():
                    break
        finally:
            done.set()
        if started and not turn.cancel.is_set():
            flush_fx()
            self.player.finish()
        if started:
            self.last_speak_end = time.monotonic()

    def _cancel_locked(self):
        """Отменить текущий ход (вызывать под _turn_lock): остановить звук, закрыть вопрос «выполнить?» как «нет»,
        сказанное до перебивания — в историю с пометкой; перебили специалиста (Turn.back_to) — слово сразу
        возвращается главному: конец _run_turn при отмене до возврата не доходит. -> был ли ход."""
        t = self.turn
        box = self.pending_confirm
        if box:                                   # перебили во время вопроса «выполнить?» — считаем «нет»
            box["event"].set()
        if t is not None:
            t.cancel.set()
            if self.player:
                self.player.stop()
            said = " ".join(t.spoken).strip()
            if said:
                self.history.append({"role": "assistant", "content": said + " …(меня перебили)", "who": self.s.get("persona")})
            self.turn = None
            back = getattr(t, "back_to", None)
            # персонажа уже сменили (новая передача, «позови …») — не спорим с новым выбором
            if back and back != self.s.get("persona") and self.s.get("persona") == getattr(t, "persona", None):
                self.switch_persona(back)
        return t is not None

    def cancel_turn(self):
        with self._turn_lock:
            return self._cancel_locked()

    def interrupt(self, reason, follow=True):
        """Перебили (кнопкой, голосом, по имени): остановить ответ; follow — сразу слушать 7 с без имени.
        Звонящий будильник глушится всем, кроме имени: на имя дальше разбирается фраза (_alarm_voice)."""
        if self.alarm and reason != "имя":
            self.alarm_finish("ack")
        if self.cancel_turn():
            log.info("⏹ Перебили (%s)", reason)
            self.emit("interrupted", reason=reason)
        if follow:
            self.follow_up_until = time.monotonic() + 7
            self.set_state("listening")
        else:
            self.set_state("idle")
