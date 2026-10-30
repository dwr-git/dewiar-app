"""Движок Dewiar — слух и голос: выбор движков распознавания и речи, скачивание моделей, аудиопоток
(VAD, слово запуска, нарезка фраз, перебивание), распознавание и поиск имени, созвоны, своё эхо.
Часть класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Потоки: audio (_audio_loop → _listen), stt (_stt_worker), name-check (_check_worker) и фоновые циклы.
Числа в кадрах: один кадр — FRAME_S (32 мс), т. е. 31 кадр ≈ 1 с. Готовая фраза уходит в handle_text,
дальше — ask() в engine_answer.py."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка

VOSK_RETRY_MIN = float(os.environ.get("DEWIAR_VOSK_RETRY_MIN") or 30)   # голоса Vosk не скачались — повтор через столько минут


# сбои открытия микрофона, которые значат «его нет или он отключён» (а не поломку): ждём и переподключаемся без отчёта
# о сбое. MME 2 «device ID out of range», MME 1 «Undefined external error», -9986 — отчёты 21.10
NO_MIC_ERR = ("device -1", "No Default Input", "Invalid device", "out of range for your system", "Undefined external error",
              "PaErrorCode -9986", "PaErrorCode -9999")



def stop_mid_phrase(in_speech, utt_s):
    """Слово-стоп от быстрого слуха посреди длинной фразы (дольше 1,5 с) — не команда: «схватит» ≈ «хватит» (№404)."""
    return bool(in_speech) and utt_s > 1.5

class AudioMixin:
    # ---------- настройка движков ----------

    def build_spotter(self):
        """Пересобирает слух имён. Имена, все слова которых есть в словаре Vosk, ловит быстрый WakeSpotter
        мгновенно; остальные (self.asr_names, например «Девиар») — только точной моделью в каждой фразе
        (_check_worker) или по отпечатку голоса. Обновляет и self.aliases — имена для find_name."""
        only = None if self.s.get("all_names") else self.s.get("persona")
        kids = getattr(self, "kids", None)
        if kids and kids.on():
            only = kids.conf().get("persona") or only        # детский режим: откликается только друг ребёнка
        if self.vosk_model is None:
            if not self.names_off:            # слух ещё запускается — соберём, когда будет модель
                return
            # модели имён нет (не скачалась): быстрого слуха нет, имена — только в распознанной фразе («Патрик, …»)
            from listen import NoSpotter
            self.spotter = NoSpotter()
            self.asr_names = sorted(self.personas.wake_map(only=only))
            self.aliases = {p["id"]: p.get("aliases") or p.get("wake") or [p["name"]]
                            for p in self.personas.all() if (not only or p["id"] == only) and (not p.get("kids") or only == p["id"])}
            return
        wm = self.personas.wake_map(only=only)
        words = {w for phrase in wm for w in phrase.split()}
        vf = STATE_DIR / "vocab.json"                   # есть ли слово в словаре Vosk — помним между запусками: проверка
        if not self._vocab:                             # грузит модель ещё раз в отдельном процессе (секунды процессора)
            try:
                d = json.loads(vf.read_text(encoding="utf-8"))
                if d.get("model") == Path(self.vosk_dir).name:
                    self._vocab.update({k: bool(v) for k, v in (d.get("words") or {}).items()})
            except (OSError, ValueError, AttributeError):
                pass
        unknown = [w for w in words if w not in self._vocab]
        if unknown:
            miss = set(missing_words(self.vosk_dir, unknown))
            self._vocab.update({w: w not in miss for w in unknown})
            try:
                vf.write_text(json.dumps({"model": Path(self.vosk_dir).name, "words": self._vocab}, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        fast = [p for p in wm if all(self._vocab.get(w) for w in p.split())]
        self.asr_names = sorted(p for p in wm if p not in fast)
        self.spotter = WakeSpotter(self.vosk_model, fast, self.decoys)
        self.aliases = {p["id"]: p.get("aliases") or p.get("wake") or [p["name"]]
                        for p in self.personas.all() if (not only or p["id"] == only) and (not p.get("kids") or only == p["id"])}
        log.info("Имена (мгновенно): %s; через точное распознавание: %s",
                 ", ".join(sorted(fast)) or "—", ", ".join(self.asr_names) or "—")
        self._names_note()

    def wake_checker(self):
        """Чем искать имя в произвольной фразе: локальный GigaAM, иначе ваш сервер распознавания."""
        if self.gigaam is not None and self.gigaam.ready:
            return self.gigaam
        if isinstance(getattr(self, "stt", None), RemoteSTT):
            return self.stt
        return None

    def _names_note(self):
        """Подсказка, если имя персонажа пока нечем надёжно услышать."""
        if not self.asr_names or not self.s.get("audio", "asr_wake") or self.wake_checker() is not None:
            return
        kids = getattr(self, "kids", None)
        wm = self.personas.wake_map(kids=bool(kids and kids.on()))
        untaught = sorted({n.capitalize() for n in self.asr_names if n in wm and not self.voiceprints.has(wm.get(n, ""))})
        if not untaught:
            return
        names = ", ".join(untaught)
        if (self.s.get("ui", "names_note") or "") == names:     # тот же совет — один раз, а не при каждом запуске
            return
        self.s.update({"ui": {"names_note": names}})
        self.note(f"Научите меня имени «{names}»: студия → «Слух» → «Научить имени» (три раза сказать имя).")

    def apply_engines(self):
        """Выставляет распознаватель и удалённый голос по настройкам и сообщает статус в интерфейс.
        GigaAM пересоздаётся только при смене модели — загрузка тяжёлая (её делает _background_loads)."""
        if self.vosk_model is None and not self.names_off:   # слух ещё запускается — движки выставит _start_hearing
            return
        st = self.s.get("stt")
        import egress                                         # «Безопасность»: стоп-кран и журнал знают, где модели
        lo = bool(self.s.get("privacy", "local_only"))
        egress.set_local_only(lo)
        egress.llm_hosts([p.get("base_url", "") for p in (self.s.get("llm", "profiles") or {}).values()])
        far = lambda u: not egress.local_host((__import__("urllib.parse").parse.urlparse(u if "://" in u else "http://" + u).hostname or ""))
        if lo and st["engine"] == "remote" and far(st["remote"].get("base_url") or ""):
            # стоп-кран: распознавание в интернете — на паузе, слушаем здесь (GigaAM, если скачан, иначе Vosk)
            g = GigaAMSTT(st.get("gigaam_model") or "gigaam-v3-e2e-rnnt")
            if g.cached():
                if not self.gigaam or self.gigaam.model_name != g.model_name:
                    self.gigaam = g
                self.stt = self.gigaam
            else:
                self.stt = self.vosk_stt
        elif st["engine"] == "remote" and st["remote"].get("base_url"):
            self.stt = RemoteSTT(st["remote"])
        elif st["engine"] == "gigaam":
            if not self.gigaam or self.gigaam.model_name != st["gigaam_model"]:
                self.gigaam = GigaAMSTT(st["gigaam_model"])
            self.stt = self.gigaam
        else:
            self.stt = self.vosk_stt
        if self.stt is None:                  # Vosk выбран, а модели ещё нет — честная ошибка, а не падение
            from listen import NoSTT
            self.stt = NoSTT()
        tt = self.s.get("tts")
        self.tts_remote = RemoteTTS(tt["remote"]) if tt["engine"] == "remote" and tt["remote"].get("base_url") else \
            ElevenTTS(tt.get("eleven") or {}) if tt["engine"] == "elevenlabs" and (tt.get("eleven") or {}).get("api_key") else None
        if lo and self.tts_remote is not None and (tt["engine"] == "elevenlabs" or far(tt["remote"].get("base_url") or "")):
            self.tts_remote = None                            # стоп-кран: голос в интернете — на паузе, говорит голос этого компьютера
        prof = self.s.active_llm()
        self.status.update(stt=self.stt.name, stt_ready=getattr(self.stt, "ready", True),
                           tts={"piper": "Piper", "vosk": "Vosk TTS" + ("" if self.vosk_tts.ready else " (загружается, пока Piper)"),
                                "remote": "Голос Dewiar" if (tt.get("remote") or {}).get("cloud") else "Удалённый голос", "elevenlabs": "ElevenLabs", "espeak": "Голос Windows" if os.name == "nt" else "eSpeak", "off": "Выключен"}.get(tt["engine"], tt["engine"]),
                           llm=(prof or {}).get("name", ""))
        self.emit("status", status=self.status)

    def _background_loads(self):
        """Поток loader: загрузка GigaAM (до готовности распознаёт Vosk, см. current_stt) и голоса персонажа."""
        low_priority()
        self._names_note()
        if isinstance(self.stt, GigaAMSTT) and not self.stt.ready:
            self.note("Загружаю GigaAM (при первом запуске ~250 МБ) — пока распознаю запасной моделью")
            self._load("stt", "Точное распознавание речи" if self.stt.cached() else "Скачиваю точное распознавание речи (~250 МБ)")
            if not self.stt.cached():
                m = self._mirror("gigaam")
                if m and m.get("name", self.stt.model_name) == self.stt.model_name:
                    self.stt.mirror = m
            ok = self.stt.load(on_progress=lambda f: self._dl("stt", f))
            self._loaded("stt")
            self.status["stt_ready"] = ok
            self.note("" if ok else f"GigaAM не загрузился: {self.gigaam.error}. Работаю на Vosk.")
            if not ok:
                self._names_note()
        self.ensure_voice(self.s.get("persona"))
        self.health_mark("full")                               # загрузилось всё: распознавание и голос персонажа

    # ---------- модели на этом компьютере: что скачано и кнопка «Скачать» (студия «Слух» и «Голос») ----------
    # Отзыв 19.10: в «Слухе и голосе» непонятно, что уже скачано и что ещё будет качаться. Каждая модель — строкой:
    # скачана (сколько занимает) / не скачана (сколько весит) / скачивается (%), и «Скачать» заранее, не переключаясь.

    @staticmethod
    def _dir_mb(*paths):
        total = 0
        for p in paths:
            try:
                p = Path(p)
                if p.is_file():
                    total += p.stat().st_size
                elif p.is_dir():
                    total += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            except OSError:
                pass
        return round(total / 1048576)

    def models_status(self):
        """-> {"items": [{key, group (ears|voice), title, about, installed, mb, used, pct}], "dir"}."""
        from listen import VOSK_NAME
        from personas import PIPER_VOICES
        dl = self.status.get("downloads") or {}
        st, tt = self.s.get("stt") or {}, self.s.get("tts") or {}
        busy = getattr(self, "_model_busy", set())
        items = []
        vdir = MODELS_DIR / VOSK_NAME
        have = (vdir / "am").exists() or (DATA_DIR / f"{VOSK_NAME}.zip").exists()
        items.append({"key": "names", "group": "ears", "title": "Слух имени — Vosk, маленькая модель",
                      "about": "Чтобы отзываться на имя без кнопки. Работает без интернета.", "installed": have,
                      "mb": (self._dir_mb(vdir) if (vdir / "am").exists() else self._dir_mb(DATA_DIR / f"{VOSK_NAME}.zip")) if have else 45, "used": True})
        gm = st.get("gigaam_model") or "gigaam-v3-e2e-rnnt"
        g = self.gigaam if self.gigaam is not None and self.gigaam.model_name == gm else GigaAMSTT(gm)
        gok = g.cached()
        items.append({"key": "gigaam", "group": "ears", "title": "GigaAM v3 — точное распознавание речи",
                      "about": "Лучшее качество для русского, на процессоре, без интернета.", "installed": gok,
                      "mb": self._dir_mb(g.local_dir, MODELS_DIR / "hf" / "hub") if gok else 250, "used": st.get("engine") == "gigaam"})
        eng = getattr(self, "english", None)
        if eng is not None and (st.get("english") or eng.installed()):
            from lang2 import EN_MODEL
            eok = eng.installed()
            items.append({"key": "english", "group": "ears", "title": "Английская речь — Vosk, маленькая модель",
                          "about": "Второй язык: понимать фразы по-английски («Слух» → «Понимать английскую речь»).", "installed": eok,
                          "mb": self._dir_mb(MODELS_DIR / EN_MODEL) if eok else 40, "used": bool(st.get("english"))})
        vk = self.vosk_tts.installed()
        items.append({"key": "vosk_tts", "group": "voice", "title": "Vosk TTS — русские голоса",
                      "about": "Чистое произношение и ударения, несколько голосов, без интернета.", "installed": vk is not None,
                      "mb": self._dir_mb(vk) if vk else 200, "used": tt.get("engine") == "vosk"})
        mine = {(p.get("voice") or {}).get("piper") for p in self.personas.all()}
        for vid, name in PIPER_VOICES.items():
            ok_ = self.piper.has(vid)
            items.append({"key": "piper:" + vid, "group": "voice", "title": "Piper — " + name,
                          "about": "Запасной голос (и основной, если выбран Piper).", "installed": ok_,
                          "mb": self._dir_mb(*self.piper.paths(vid)) if ok_ else 63,
                          "used": tt.get("engine") in ("piper", "vosk") and vid in mine})
        for it in items:
            k = "m:" + it["key"]
            it["pct"] = int(round(dl[k] * 100)) if k in dl and dl[k] < 1 else (0 if k in busy else None)
        return {"items": items, "dir": str(MODELS_DIR)}

    def models_get(self, key):
        """«Скачать» модель заранее (в фоне), не меняя выбранного. -> {"started": bool}."""
        from personas import PIPER_VOICES
        if not hasattr(self, "_model_busy"):
            self._model_busy = set()
        if key in self._model_busy:
            return {"started": False}
        if key not in ("names", "gigaam", "vosk_tts", "english") and not (key.startswith("piper:") and key[6:] in PIPER_VOICES):
            raise ValueError("нет такой модели")
        self._model_busy.add(key)
        prog = (lambda f: self._dl("m:" + key, f))

        def run():
            try:
                if key == "names":
                    from listen import ensure_vosk
                    ensure_vosk(DATA_DIR, MODELS_DIR, on_status=self.note, mirror=self._mirror_url("vosk_small"))
                elif key == "gigaam":
                    gm = self.s.get("stt", "gigaam_model") or "gigaam-v3-e2e-rnnt"
                    g = self.gigaam if self.gigaam is not None and self.gigaam.model_name == gm else GigaAMSTT(gm)
                    m = self._mirror("gigaam")
                    if m and m.get("name", gm) == gm:
                        g.mirror = m
                    if not g.load(on_progress=prog):
                        raise RuntimeError(g.error or "не загрузился")
                    if self.s.get("stt", "engine") != "gigaam" and g is not self.gigaam:
                        g.model = None                    # скачали заранее — в памяти держать незачем
                elif key == "english":
                    from lang2 import EN_MODEL, EN_URLS
                    from listen import ensure_model
                    m = self._mirror("vosk_en") or {}
                    ensure_model(EN_MODEL, EN_URLS, m.get("sha256"), DATA_DIR, MODELS_DIR, on_status=self.note, mirror=m.get("url"),
                                 label="английской речи (40 МБ, один раз)")
                elif key == "vosk_tts":
                    m = self._mirror("vosk_tts")
                    self.vosk_tts.mirror = self.s.get("tts", "vosk_url") or (m or {}).get("url") or self.updater.mirrors.get("vosk_tts") or ""
                    self.vosk_tts.mirror_sha = (m or {}).get("sha256", "")
                    self.vosk_tts.ensure(on_progress=prog)
                else:
                    self.piper.mirror = self._mirror("piper")
                    self.piper.ensure(key[6:], on_progress=prog)
                log.info("⬇️ Модель «%s» скачана", key)
            except Exception as e:  # noqa: BLE001
                log.warning("Модель «%s» не скачалась: %s", key, e)
                self.note(f"Не скачалось: {e}")
            finally:
                self._model_busy.discard(key)
                self.status.get("downloads", {}).pop("m:" + key, None)
                self.emit("models", **self.models_status())
        threading.Thread(target=run, name="model-get", daemon=True).start()
        return {"started": True}

    def _mirror(self, key):
        """Модель на своём сайте (dewiar.pro/dwrapp): {"url", "sha256", …} или None."""
        try:
            return self.updater.model(key) if self.updater else None
        except Exception as e:  # noqa: BLE001
            log.info("Зеркало моделей: %s", e)
            return None

    def _mirror_url(self, key):
        """Адрес зеркала для малой модели Vosk — только если её ещё нет ни распакованной, ни архивом
        (проверка пути — именно vosk-model-small-ru-0.22, вызывается с key="vosk_small")."""
        have = (MODELS_DIR / "vosk-model-small-ru-0.22" / "am").exists() or (DATA_DIR / "vosk-model-small-ru-0.22.zip").exists()
        m = None if have else self._mirror(key)
        return (m or {}).get("url")

    def ensure_vosk_tts(self):
        """Голоса Vosk TTS: скачать (один раз) и загрузить в потоке vosk-tts; до готовности говорим Piper."""
        if self.vosk_tts.ready or self._vosk_loading:
            return
        if time.monotonic() < getattr(self, "_vosk_retry_at", 0.0):   # не скачалось — следующая попытка позже, а не
            return                                                    # каждые 2 минуты весь день (№58: сеть до сайта плохая)
        self._vosk_loading = True
        # откуда качать: адрес из настроек → зеркало модели с сайта (с sha256) → зеркало из манифеста обновлений
        m = None if self.s.get("tts", "vosk_url") or self.vosk_tts.installed() else self._mirror("vosk_tts")
        self.vosk_tts.mirror = self.s.get("tts", "vosk_url") or (m or {}).get("url") or self.updater.mirrors.get("vosk_tts") or ""
        self.vosk_tts.mirror_sha = (m or {}).get("sha256") or ""

        def run():
            low_priority()
            self._load("voices", "Голоса персонажей" if self.vosk_tts.installed() else "Скачиваю голоса персонажей (~200 МБ)")
            try:
                self.vosk_tts.ensure(on_progress=lambda f: self._dl("voices", f), on_status=self.note)
                self.note("")
                log.info("Vosk TTS готов: %s", self.vosk_tts.speakers)
                self._vosk_fails = 0
                self.emit("voices", speakers=self.vosk_tts.speakers)
            except Exception as e:  # noqa: BLE001
                err = str(e)
                if isinstance(e, ImportError):
                    err = "не установлена библиотека vosk-tts — выполните в терминале: sudo /opt/dewiar/dewiar-env"
                self.vosk_tts.error = err
                n = self._vosk_fails = getattr(self, "_vosk_fails", 0) + 1
                wait = VOSK_RETRY_MIN * 60 * min(2 ** (n - 1), 12)      # 30 мин, час, 2, 4, 6 часов
                self._vosk_retry_at = time.monotonic() + wait
                log.warning("Vosk TTS не загрузился (%d-й раз, снова через %d мин): %s", n, wait // 60, e)
                if n == 1:                                              # сказать один раз, не каждые полчаса
                    self.note(f"Новые голоса не загрузились ({err[:120]}) — говорю голосами Piper, попробую позже")
            finally:
                self._vosk_loading = False
                self._loaded("voices")
                self.apply_engines()
        threading.Thread(target=run, name="vosk-tts", daemon=True).start()

    def ensure_voice(self, pid):
        """Готовит голос персонажа: Vosk TTS (в фоне) и голос Piper — он нужен и как запасной для Vosk.
        Piper качается синхронно, в вызывающем потоке."""
        if self.s.get("tts", "engine") == "vosk":
            self.ensure_vosk_tts()
        if self.s.get("tts", "engine") not in ("piper", "vosk"):
            return
        vid = self.personas.get(pid)["voice"].get("piper", "ru_RU-denis-medium")
        if self.piper.has(vid):
            return
        try:
            self.note(f"Скачиваю голос {PIPER_VOICES.get(vid, vid)}…")
            self._load("voice", f"Скачиваю голос {PIPER_VOICES.get(vid, vid)}")
            self.piper.mirror = self._mirror("piper")
            self.piper.ensure(vid, on_progress=lambda f: self._dl("voice", f))
            self.note("")
        except Exception as e:  # noqa: BLE001
            log.warning("Голос не скачался: %s", e)
            self.note("Голос не скачался — пока говорю аварийным голосом eSpeak")
        finally:
            self._loaded("voice")

    def _dl(self, what, frac):
        """Ход скачивания: окнам — не на каждый кусок (их тысячи), а когда доля сдвинулась на 2%."""
        prev = self.status["downloads"].get(what)
        self.status["downloads"][what] = round(frac, 2)
        ld = self.status.setdefault("loading", {}).get(what)
        if ld is not None:
            ld["f"] = round(frac, 2)
        if prev is None or int(frac * 50) != int(prev * 50) or frac >= 1:
            self.emit("status", status=self.status)

    # ---------- первая загрузка: что готовится сейчас (виджет и студия показывают с долей) ----------

    def _load(self, key, label):
        """Этап загрузки начался: status.loading[key] = {t: что делаю, f: доля скачивания или None}."""
        self.status.setdefault("loading", {})[key] = {"t": label, "f": None, "ts": int(time.time())}
        self.emit("status", status=self.status)

    def _loaded(self, key):
        """Этап закончился (удачно или нет) — убрать из списка и из скачиваний."""
        changed = self.status.setdefault("loading", {}).pop(key, None) is not None
        changed = self.status["downloads"].pop(key, None) is not None or changed
        if changed:
            self.emit("status", status=self.status)

    def current_stt(self):
        """Выбранный распознаватель, а пока он не загрузился (GigaAM) — Vosk."""
        stt = getattr(self, "stt", None)
        if stt is None or not getattr(stt, "ready", True):
            return self.vosk_stt or stt       # без модели имён Vosk нет — тогда сам выбранный (скажет, что не готов)
        return stt

    # ---------- аудиопоток ----------

    def _open_audio(self):
        """Открывает микрофон и динамик. С эхоподавлением (AEC) слушаем его источник и играем в его приёмник,
        иначе — выбранные устройства напрямую. status["aec"] — можно ли слушать во время своего ответа."""
        a = self.s.get("audio")
        if self.wav_input:
            use_aec = os.environ.get("DEWIAR_ASSUME_AEC") == "1"      # тесты: в файле нет эха
        else:
            # №370 (28.10, Linux Mint, веб-камера C920): эхоподавление отдавало одни нули и после переоткрытия — тогда до
            # перезапуска программы слушаем микрофон напрямую (_aec_bypass ставит _mic_zero_step)
            use_aec = a["echo_cancel"] and not getattr(self, "_aec_bypass", False) and self.aec.setup(a["input"], a["output"])
        headphones = bool(a.get("headphones")) and not use_aec
        self.status["aec"] = bool(use_aec) or headphones        # «можно слушать во время ответа»: в наушниках эха нет
        self.status["headphones"] = headphones
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

    def _audio_loop(self):
        """Поток audio: держит микрофон открытым и переоткрывает его после сбоя или restart_audio;
        нет микрофона — ждём подключения, отвечать можно по написанному. Для wav-файла (тесты) — один проход и «eof»."""
        last_err = None
        while not self.stopping.is_set():
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
                if self.restart_audio.is_set():
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

    def _mic_silent(self, exact=True):
        """Микрофон открыт, а звука нет: ровные нули (exact) — в Windows так выглядит запрет доступа к микрофону;
        почти нули — выбран виртуальный микрофон (HitPaw, VB-Cable, Voicemod…) или громкость записи на нуле.
        Подбирает подсказку по списку устройств и показывает её (заметка, уведомление, отчёт о проблеме);
        в Windows при запрете доступа сразу открывает нужную страницу параметров."""
        virt = re.compile(r"virtual|vb-audio|cable output|voicemod|hitpaw|stereo mix|стерео ?микшер|what u hear|loopback", re.I)
        mapper = re.compile(r"sound mapper|переназначение звук|первичный драйвер", re.I)
        try:
            srcs = [d for d in list_devices() if d.get("kind") == "source"]
        except Exception:  # noqa: BLE001
            srcs = []
        cur = self.s.get("audio", "input") or ""
        names = [(d.get("description") or d.get("name") or "") for d in srcs if not mapper.search(d.get("description") or d.get("name") or "")]
        fake = [n for n in names if virt.search(n)]
        real = [n for n in names if not virt.search(n)]
        if fake and not real:
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
        zst = {"since": None, "told": False, "all": True}      # поток идёт, а в нём нули или почти нули (_mic_zero_step)
        while not self.stopping.is_set() and not self.restart_audio.is_set():
            frame = self.capture.read()
            if not frame:
                return
            now = time.monotonic()
            self._mic_ring.append(frame)                # 0,4 с в памяти — удержание не теряет начало фразы (не распознаётся)
            if self.muted and self.hold is None and not self._mute_pass:
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
            speaking = self.state == "speaking"
            if speaking and not self.status["aec"]:
                # полудуплекс: себя не слушаем — кроме короткого «стоп / хватит / пауза / отмена»
                if not was_speaking:
                    self.spotter.rec.Reset()
                    half_echo.clear()
                was_speaking = True
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
                    else:
                        log.info("✋ «%s» — замолкаю (без эхоподавления)", w)
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
                if kind == "wake" and self._noisy() and self.state == "idle" and self.wake_checker() is not None:
                    # вокруг много говорят (созвон, видео, гости): быстрый слух часто ошибается — сначала проверим
                    # фразу точной моделью и только потом откликнемся
                    log.info("🎤 «%s»? Вокруг разговор — проверю точной моделью", phrase)
                    self.vosk_wake_check, self._vosk_wake_word = self.utt_id, phrase
                    continue
                if kind == "wake":
                    log.info("🎤 Имя «%s» услышано", phrase)
                    self.wake_time, self._wake_phrase = now, phrase
                    if in_speech and len(utt) * FRAME_S > 2.5:
                        # имя посреди долгой «фразы» (играет музыка, вокруг говорят): иначе команда утонет в 20 секундах
                        # звука. Фраза начинается заново за 1,6 с до срабатывания — с самого имени.
                        keep = int(1.6 / FRAME_S)
                        log.info("🎤 Имя посреди долгого звука (%.1f с) — начинаю фразу с имени", len(utt) * FRAME_S)
                        utt = utt[-keep:]
                        t0, silence, speech_frames = now - len(utt) * FRAME_S, 0, len(utt)
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
                    self.stop_utt = now - self.wake_time > 3     # одно «стоп» — не вопрос; «стоп, лучше …» — вопрос
                    self.stop_time, self._stop_sleep = now, self.stop_utt
                    self.interrupt(phrase, follow=False)
                    self.follow_up_until = now + 3.0             # «стоп, лучше расскажи…» — договорить успеете

            fin = getattr(self.spotter, "last_final", None)
            if fin is not None:
                self.spotter.last_final = None
                if self._pending_media_stop and now - self._pending_media_stop < 4 and fin.strip() in MEDIA_STOP \
                        and self.state in ("idle", "listening"):
                    threading.Thread(target=self._media_stop_word, args=(fin.strip(),), daemon=True).start()
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
                if speaking and barge in ("smart", "any_speech") and self.status["aec"]:
                    # Перебить можно просто начав говорить: через ~0,25 с речи ответ приглушается («слышу вас»),
                    # через ~0,8 с (any_speech — ~0,4 с) замолкает, а сказанное идёт как новый вопрос, без имени.
                    # Свой голос, просочившийся через эхоподавление, тише живой речи — порог считаем от него.
                    floor = max(220.0, 2.6 * float(np.median(echo)) if len(echo) > 10 else 400.0)
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
                if silence >= self._end_frames or len(utt) * FRAME_S > 25:  # фраза длиннее 25 с — режем принудительно
                    log.debug("речь кончилась (фраза %d, %.1f с)", self.utt_id, len(utt) * FRAME_S)
                    in_speech, starts = False, 0
                    if ducked and self.player:                  # кашлянули, «угу» — продолжаем как было
                        self.player.gain, ducked = 1.0, False
                    self._on_utterance(b"".join(utt[:len(utt) - max(0, silence - 6)]), t0, now)   # хвост тишины — не больше 6 кадров
                    utt = []

            # ждали вопрос, окно истекло, а фразы нет — засыпаем и пишем в журнал, почему могли не услышать
            if (self.state == "listening" and now > self.follow_up_until and not in_speech
                    and now - self.wake_time > 4 and self.stt_q.empty()):
                if self._listen_peak >= 500 and self._listen_vad >= 0.6:
                    log.info("🎤 Ждал вопрос — звук был (громкость %.0f, «это речь» %.2f), но фраза не сложилась: "
                             "вероятно, вокруг музыка или разговор", self._listen_peak, self._listen_vad)
                else:
                    log.info("🎤 Ждал вопрос — речи не услышал (громче всего: %.0f, уверенность «это речь»: %.2f; "
                             "обычный голос — от 500 и 0.6). Если вы говорили — микрофон слишком тихий или не тот",
                             self._listen_peak, self._listen_vad)
                self.set_state("idle")
                self.play_tone("sleep")                    # «больше не слушаю» — ниже, чем «слушаю»: понятно без взгляда на экран

    def _on_utterance(self, pcm, t0, now):
        """Фраза закончилась (pcm — 16 бит моно, t0/now — её начало и конец по monotonic). Решаем, куда её:
        в распознавание как вопрос (stt_q), в проверку имени точной моделью или отпечатком (check_q),
        ранней проверке, которая уже идёт, — или отбросить (короткий звук, «стоп», чужой разговор, своё эхо)."""
        dur = len(pcm) / 2 / RATE
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

    def _pause_check(self, t0):
        """Началась речь. Если прошлую фразу сочли законченной меньше 0,8 с назад, а ответа ещё нет (модель думает), —
        человек не договорил: ждать паузу дольше (+150 мс, до +600) и склеить обе части (_on_utterance).
        №226 (24.10): «после нескольких „перебил“ добавка дошла до 900 мс и сама не уменьшается — ассистент всё медленнее»:
        потолок +600 (вся пауза ~1,25 с), а тает она вдвое быстрее (_pause_ok); в студии — «вернуть обычную»."""
        lf = getattr(self, "_last_final", None)
        if not lf or lf.get("cut") or self.state != "thinking" or t0 - lf["t"] > 0.8 or t0 < lf["t"] - 0.5:
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
                if self.vosk_stt is None:
                    log.warning("%s не распознал кусок диктовки: %s", stt.name, e)
                    self.note(f"Не распознал: {e}")
                    continue
                log.warning("%s не распознал кусок диктовки: %s — пробую Vosk", stt.name, e)
                t = self.vosk_stt.transcribe(part).strip()
            if t:
                out.append(t)
        return " ".join(out)

    # ---------- распознавание ----------

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
                    if self.vosk_stt is None:
                        log.warning("%s не распознал: %s", stt.name, e)
                        self.note(f"Не распознал: {e}")
                        text = ""
                    else:
                        log.warning("%s не распознал: %s — пробую Vosk", stt.name, e)
                        text = self.vosk_stt.transcribe(pcm).strip()
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
        pid, end = find_name(text, self.aliases, strict=True)
        if pid:                                                # имя — первым словом: «Патрик, …»
            if pid != self.s.get("persona"):
                self.switch_persona(pid)
            rest = text[end:].lstrip(" ,.!?:;—-").strip()
            text = rest or text
        self.ask(text)

    def _check_worker(self):
        """Поток name-check: ищет имя во фразах из check_q — ("utt", pcm, uid) без явного имени и ("barge", …)
        поверх ответа. Сначала отпечаток голоса, затем точная модель + строгий find_name. Нашли — перебиваем ответ
        и отправляем фразу как вопрос; не нашли — это разговор «не мне» (учитывается в _noisy)."""
        head_bytes = int(2.2 * RATE) * 2                   # имя — в начале фразы («Девиар, …» — меньше секунды)
        if hasattr(os, "setpriority") and hasattr(threading, "get_native_id"):     # в Windows setpriority нет
            try:                                           # фоновая проверка имени уступает созвону и другим программам
                os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 5)
            except OSError:
                pass
        while not self.stopping.is_set():
            kind, pcm, uid = self.check_q.get()
            if self._check_voiceprint(kind, pcm, uid):
                continue
            checker = self.wake_checker()
            if checker is None:
                self.barge_done.pop(uid, None)
                continue
            try:
                t0 = time.monotonic()
                # короткую фразу — целиком (тогда текст сразу и вопрос); длинную — только начало, где имя
                chunk = pcm if len(pcm) <= int(3.0 * RATE) * 2 else pcm[:head_bytes]
                text = checker.transcribe(chunk).strip()
            except Exception as e:  # noqa: BLE001
                log.debug("проверка имени не удалась: %s", e)
                continue
            pid, _ = find_name(text, self._wake_aliases(), strict=True)
            ms = int((time.monotonic() - t0) * 1000)
            if pid:
                log.info("👂 %s: «%s» → %s (%d мс)", checker.name, text, pid, ms)
            else:                                      # чужие разговоры в журнал не пишем (только в подробном режиме)
                log.debug("👂 %s: «%s» → имени нет (%d мс)", checker.name, text, ms)
            self.emit("hearing", text=text, by=checker.name, name=pid or "", ms=ms)
            if not pid:
                self.barge_done.pop(uid, None)
                if len(text) > 12:
                    self._chatter.append(time.monotonic())     # вокруг разговаривают — не со мной
                if self.vosk_wake_check == uid:
                    self.vosk_wake_check = -1
                    log.info("🎧 «%s» от быстрого слуха не подтвердилось — вокруг разговор, пропускаю", self._vosk_wake_word)
                    self.set_state("idle")
                continue
            if self.vosk_wake_check == uid:
                self.vosk_wake_check = -1
            log.info("🎤 Имя распознано точной моделью: «%s»", text)
            self.emit("wake", phrase=pid)
            if kind == "barge":
                self.barge_hit = uid                        # фраза, когда закончится, пойдёт как вопрос
                self.interrupt("имя")
                ended = self.barge_done.pop(uid, None)
                if ended is not None:                       # …а если уже закончилась — отправляем сейчас
                    self.stt_q.put((ended, True, False))
                    self.set_state("thinking")
                continue
            if self.state in ("speaking", "thinking"):
                self.interrupt("имя")
            # распознали только начало или не тем распознавателем, что для вопросов, — фразу целиком распознаем заново
            if len(pcm) > len(chunk) or checker is not self.current_stt():
                self.stt_q.put((pcm, True, False))
                self.set_state("thinking")
            else:
                self.set_state("thinking")
                self.handle_text(text, True, False)

    # ---------- созвон ----------

    def _noisy(self):
        """Вокруг идёт разговор: за последние полторы минуты не меньше четырёх фраз «не мне»."""
        now = time.monotonic()
        return sum(1 for t in self._chatter if now - t < 90) >= 4

    def _meeting_mode(self):
        return self.s.get("audio", "meeting") or "pause"

    def _wake_aliases(self):
        """На созвоне в режиме «только главный» — откликаемся только на имя активного персонажа."""
        if self.meeting and self._meeting_mode() == "main":
            me = self.s.get("persona")
            return {me: self.aliases[me]} if me in self.aliases else self.aliases
        return self.aliases

    def _meeting_ignores(self, phrase):
        """Пропустить ли имя от быстрого слуха из-за созвона (только в покое): режим pause — любое,
        main — кроме имени активного персонажа. Включён суфлёр — любое и всегда: на встрече ассистент молчит."""
        pr = getattr(self, "prompter", None)
        if pr is not None and (pr.on or pr.enrolling is not None):
            return True
        if not self.meeting or self.state != "idle":
            return False
        mode = self._meeting_mode()
        if mode == "pause":
            return True
        if mode == "main":
            try:
                return self.personas.wake_map(kids=True).get(phrase) not in (None, self.s.get("persona"))
            except Exception:  # noqa: BLE001
                return False
        return False

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
                        self.push(f"📅 Через {left} мин — {e['start']:%H:%M}", text)
                        if self.state == "idle" and not self.meeting:
                            self.announce(f"Через {left} минут: {e['title']}.")
            except Exception as e:  # noqa: BLE001
                log.warning("Календари: %s", e)
            self.stopping.wait(tick)

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

    def _meeting_watch(self):
        """Поток meeting: раз в 3 секунды — не слушает ли микрофон другая программа (созвон); итог — self.meeting
        и status["meeting"]. В режиме normal созвон не отслеживается."""
        from meeting import mic_users
        while not self.stopping.is_set():
            apps = mic_users() if self._meeting_mode() != "normal" else []
            if apps != self.meeting:
                was = bool(self.meeting)
                self.meeting = apps
                if bool(apps) != was:
                    log.info("🎧 %s", f"Созвон ({', '.join(apps)}): " + {"pause": "имя не слушаю — говорите со мной по кнопке",
                                                                          "main": "слушаю только главное имя"}.get(self._meeting_mode(), "")
                             if apps else "Созвон закончился — слушаю как обычно")
                self.status["meeting"] = {"apps": apps, "mode": self._meeting_mode()} if apps else None
                self.emit("status", status=self.status)
                if apps and not was and not self.prompter.on and self.s.get("ui", "prompter_offer") is not False \
                        and (self.s.get("features") or {}).get("prompter") is not False:      # «Возможности»: суфлёр выключен — не предлагаем
                    self.emit("prompter_offer", apps=apps)     # созвон начался — виджет предложит суфлёр
            self.stopping.wait(3.0)

    # ---------- имя по голосу, своё эхо, разбор распознанной фразы ----------

    def _check_voiceprint(self, kind, pcm, uid):
        """Имя по звучанию (голосовой отпечаток) -> True, если имя найдено и фраза обработана.
        Для ранней проверки поверх ответа ("barge") фраза может ещё не кончиться — тогда место разреза
        запоминается в barge_cut, и её подхватит _on_utterance."""
        if not self.voiceprints.items:
            return False
        t0 = time.monotonic()
        pid, end, dist = self.voiceprints.match(pcm, allowed=set(self._wake_aliases()))
        ms = int((time.monotonic() - t0) * 1000)
        if not pid:
            log.debug("отпечаток: имени нет (%.3f, %d мс)", dist, ms)
            if self.wake_checker() is None:
                self.emit("hearing", text="", by="отпечаток голоса", name="", ms=ms, dist=round(dist, 3))
            return False
        name = self.personas.get(pid)["name"]
        log.info("🎤 Имя «%s» узнано по голосу (%.3f, %d мс)", name, dist, ms)
        self.emit("hearing", text=f"«{name}» — по голосу", by="отпечаток голоса", name=pid, ms=ms)
        self.emit("wake", phrase=pid)
        if kind == "barge":
            self.barge_hit = uid
            self.interrupt("имя")
            ended = self.barge_done.pop(uid, None)
            if ended is not None:
                self._after_name(pid, ended, end)
            else:
                self.barge_cut = (pid, end)
            return True
        if self.state in ("speaking", "thinking"):
            self.interrupt("имя")
        self._after_name(pid, pcm, end)
        return True

    def _after_name(self, pid, pcm, end_sec):
        """Имя найдено по звуку: остаток фразы — вопрос."""
        if pid != self.s.get("persona"):
            self.switch_persona(pid)
        rest = pcm[int(end_sec * RATE) * 2:]
        if len(rest) / 2 / RATE < 0.45:
            self.listen_for_command()
            return
        self.set_state("thinking")
        self.stt_q.put((rest, True, False, pid))

    def _own_word(self, w):
        """Слово-команда («пауза», «стоп») есть в том, что ассистент сам говорит сейчас (или только что) — это эхо."""
        stem = _norm(w or "").strip()
        stem = stem[:max(4, len(stem) - 1)]
        now = time.monotonic()
        said = _norm(" ".join([self._now_saying or ""] + [t for at, t in list(self._said) if now - at < 8]))
        return bool(stem) and stem in said

    def _is_self_echo(self, text):
        """Микрофон услышал наш же голос из колонок (эхоподавление не справилось): фраза почти целиком — из того,
        что ассистент сказал за последние 25 секунд."""
        norm = lambda t: (t or "").lower().replace("ё", "е")  # noqa: E731
        words = re.findall(r"\w{3,}", norm(text))
        now = time.monotonic()
        if len(words) < 4 or (self.state != "speaking" and now - self._spoke_until > 3.5):
            return False                                  # эхо бывает, пока говорим, и сразу после
        said = set(re.findall(r"\w{3,}", norm(" ".join(t for at, t in list(self._said) if now - at < 25))))
        if not said:
            return False
        stems = {w[:5] for w in said if len(w) >= 5}
        hit = sum(1 for w in words if w in said or (len(w) >= 5 and w[:5] in stems))
        return hit / len(words) >= 0.75

    def _echo_heard(self, text):
        """Фраза оказалась нашим эхом: пропускаем. Второй раз за 3 минуты — на 10 минут отключаем «продолжение
        разговора» без имени (_echo_until, см. конец хода в engine_answer.py) и подсказываем про наушники."""
        now = time.monotonic()
        log.info("🔁 Услышал свой же голос — пропускаю: «%s»", text[:120])
        self._echo_hits = [t for t in self._echo_hits if now - t < 180] + [now]
        self.follow_up_until = 0.0
        if len(self._echo_hits) >= 2 and now > self._echo_until:
            self._echo_until = now + 600                  # 10 минут слушаем только по имени
            self.note("Я слышу сам себя: звук из колонок попадает в микрофон. Наденьте наушники или включите "
                      "эхоподавление (студия → «Звук и поведение»). Пока отвечаю только когда зовут по имени.")
        self.set_state("idle")

    def handle_text(self, text, by_wake, follow, forced=None, dur=None):
        """Распознанная фраза → что делать: эхо — пропустить; ответ на «выполнить?» или на вопрос задачи;
        имя + вопрос → ask(); имя + «стоп» → уснуть; продолжение разговора → ask(); иначе ложное срабатывание.
        by_wake — имя слышали по звуку, follow — шло «продолжение разговора», forced — pid, если имя уже отрезано,
        dur — длина фразы, с."""
        if text and not forced and self._is_self_echo(text):
            self._echo_heard(text)
            return
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
        pid, end = find_name(text, self.aliases) if text else (None, 0)
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
            if long_ and not named and not invited and not to_me(text):
                # без имени, долго и много слов — это разговор людей рядом, а не продолжение со мной (отчёт 11.10:
                # «как только кто-то рядом — она сама вклинивается в беседу»). Слушаю дальше только по имени.
                log.info("Продолжение разговора: длинная фраза без имени (%.1f с, %d слов) — похоже, говорят не со мной",
                         dur or 0.0, len(ws))
                self.follow_up_until = 0.0
                self.set_state("idle")
                if not getattr(self, "_long_hint", False):     # человек думает, что ассистент «уснул» (отчёт 18.10)
                    self._long_hint = True
                    self.note("Длинную фразу без имени я приняла за разговор рядом и не ответила. Если это было мне — "
                              "начните с имени или попросите: «расскажи…», «найди…».")
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

    def _wake_misheard(self, text, dur):
        """Быстрый слух услышал имя В НАЧАЛЕ фразы, а точная модель его ослышала или потеряла: «Мира, включи музыку»,
        «Нина, какая погода», «включи музыку» (имя срезано). Отзыв 28.10: «зову „Лира“, начинаю говорить — а она через
        пару секунд молча отключается, примерно в 30 % случаев»: фраза считалась ложным срабатыванием. Теперь: имя в
        первых 2 с фразы и первое слово похоже на имя — это обращение; имени в тексте нет вовсе, но имя было в первые
        1,2 с, фраза до 8 с и это просьба («включи», «какая…») — тоже. Вокруг разговор (_noisy) — не гадаем: там имя
        и так проверяет точная модель. -> (pid, конец имени в тексте) или (None, 0)."""
        off = getattr(self, "_wake_off", None)
        self._wake_off = None
        spotted = self.personas.wake_map(kids=True).get(getattr(self, "_wake_phrase", ""))
        if not spotted or off is None or off > 2.0 or getattr(self, "_noisy", lambda: False)():
            return None, 0
        m = re.match(r"\s*([\w-]+)", text)
        if m and len(text.split()) >= 2 and self._name_like(m.group(1)):
            log.info("🎤 Имя «%s» слышно в начале, распознано как «%s» — это обращение", self._wake_phrase, m.group(1))
            return spotted, m.end()
        if off <= 1.2 and dur <= 8 and to_me(text):
            log.info("🎤 Имя «%s» слышно в начале, в распознанном его нет — просьба, это обращение", self._wake_phrase)
            return spotted, 0
        return None, 0

    def _name_like(self, text):
        """Похоже ли короткое распознанное на ослышанное имя («Игрова», «Элла» вместо «Эва»), а не на ответ человека.
        Отчёт 11.10: «Лира» → «Слушаю…», затем быстрое «спасибо» / «как дела» принимались за ослышанное имя — фраза
        терялась, и снова «Слушаю…». Пусто или первое слово хоть немного похоже на имя (≥ 0,55) — имя; иначе — фраза."""
        import difflib
        w = _norm(re.sub(r"[^\w ]", " ", text or "")).split()
        if not w:
            return True
        names = [_norm(a).replace(" ", "") for al in self.aliases.values() for a in al]
        return any(difflib.SequenceMatcher(None, w[0], a).ratio() >= 0.55 for a in names)

    def listen_for_command(self, seconds=8):
        """Имя услышали без вопроса: ждём вопрос seconds секунд (без имени) и даём короткий сигнал."""
        self._listen_peak, self._listen_vad = 0.0, 0.0
        log.info("🎤 Слушаю вопрос (%d с)", seconds)
        self.follow_up_until = time.monotonic() + seconds
        self._invited_until = self.follow_up_until + 30     # начатая в эти секунды фраза — вопрос мне, даже длинная
        self.set_state("listening")
        self.emit("heard", text="")
        if time.monotonic() - getattr(self, "_wake_tone_at", 0.0) > 4:   # уже прозвучал на само имя — второй раз не нужен
            self.play_tone("wake")

    def play_tone(self, kind):
        """Короткий сигнал состояния. Вывод для сигналов держится открытым (ToneOut): открывать звук каждый раз —
        это заметная задержка, и «слушаю» звучало бы позже, чем человек договорил имя."""
        if not self.s.get("audio", "sounds") or self.player is None or self.state == "speaking":
            return
        out = getattr(self, "_tone_out", None)
        if out is None or out.device != self.player.device:
            out = self._tone_out = ToneOut(self.player.device, null=self.null_player)
        out.play(tone(kind))
