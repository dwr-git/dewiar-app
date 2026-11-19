"""Слух и голос — движки и модели (часть Engine, чистое ядро 1.0.16): слух имён (Vosk), точное распознавание
(GigaAM, сервер), выбор движков, скачивание моделей и голосов (Vosk TTS, Piper), ход загрузки."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from ears_base import VOSK_RETRY_MIN


class ModelsMixin:
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
            self._all_aliases(kids)
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
        self._all_aliases(kids)
        log.info("Имена (мгновенно): %s; через точное распознавание: %s",
                 ", ".join(sorted(fast)) or "—", ", ".join(self.asr_names) or "—")
        self._names_note()

    def _all_aliases(self, kids):
        """Имена всех персонажей — для явной речи (удержание кнопки): «Патрик, …» переключает и тогда, когда слух по имени —
        только на активного (19.11: ложные срабатывания). Детский режим — только друг ребёнка."""
        if kids and kids.on():
            self.held_aliases = dict(self.aliases)
            return
        self.held_aliases = {p["id"]: p.get("aliases") or p.get("wake") or [p["name"]] for p in self.personas.all() if not p.get("kids")}

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

    def _ui_en(self):
        """Программа по-английски (0.96)?"""
        try:
            import i18n
            return i18n.resolve(self.s.get("ui", "lang")) == "en"
        except Exception:  # noqa: BLE001
            return False

    def _asr_name(self):
        """Модель точного распознавания на этом компьютере: GigaAM (русский); программа по-английски — Parakeet (0.96)."""
        from stt import EN_ASR
        if self._ui_en():
            return self.s.get("stt", "en_model") or EN_ASR
        return self.s.get("stt", "gigaam_model") or "gigaam-v3-e2e-rnnt"

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
            g = GigaAMSTT(self._asr_name())
            if g.cached():
                if not self.gigaam or self.gigaam.model_name != g.model_name:
                    self.gigaam = g
                self.stt = self.gigaam
            else:
                self.stt = self.vosk_stt
        elif st["engine"] == "remote" and st["remote"].get("base_url"):
            rc = dict(st["remote"])
            if self._ui_en() and str(rc.get("language") or "ru") == "ru":
                rc["language"] = "en"                     # 0.96: программа по-английски — сервер слушает английскую речь
            self.stt = RemoteSTT(rc)
        elif st["engine"] == "gigaam":
            if not self.gigaam or self.gigaam.model_name != self._asr_name():
                self.gigaam = GigaAMSTT(self._asr_name())
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
                                "remote": "Голос Dewiar" if (tt.get("remote") or {}).get("cloud") else "Удалённый голос", "elevenlabs": "ElevenLabs", "espeak": "Голос Windows" if os.name == "nt" else "Голос Mac" if sys.platform == "darwin" else "eSpeak", "off": "Выключен"}.get(tt["engine"], tt["engine"]),
                           llm=(prof or {}).get("name", ""))
        self.emit("status", status=self.status)

    def _background_loads(self):
        """Поток loader: загрузка GigaAM (до готовности распознаёт Vosk, см. current_stt) и голоса персонажа."""
        low_priority()
        self._names_note()
        text_only = bool(self.s.get("ui", "text_mode"))         # №876: микрофона нет — распознавание не нужно, запуск быстрее
        if text_only and isinstance(self.stt, GigaAMSTT) and not self.stt.ready:
            log.info("⌨ Текстовый режим — точное распознавание не загружаю (включится вместе с голосом)")
        if not text_only and isinstance(self.stt, GigaAMSTT) and not self.stt.ready:
            self.note("Загружаю GigaAM (при первом запуске ~250 МБ) — пока распознаю запасной моделью")
            self._load("stt", "Точное распознавание речи" if self.stt.cached() else "Скачиваю точное распознавание речи (~250 МБ)")
            if not self.stt.cached():
                m = self._mirror("gigaam")
                if m and m.get("name", self.stt.model_name) == self.stt.model_name:
                    self.stt.mirror = m
            ok = self.stt.load(on_progress=lambda f: self._dl("stt", f))
            self._loaded("stt")
            self.status["stt_ready"] = ok
            self.note("" if ok else self._gigaam_fail_text(self.stt.error))
            if not ok:
                self._names_note()
                try:
                    if self._stt_temp_server():                # №513: временно — сервер Dewiar, выбор человека помним
                        self.note("")
                except Exception:  # noqa: BLE001
                    log.exception("распознавание: временная замена")
        self.ensure_voice(self.s.get("persona"))
        self.health_mark("full")                               # загрузилось всё: распознавание и голос персонажа

    @staticmethod
    def _gigaam_fail_text(err):
        """Почему точное распознавание не запустилось и что делать — словами (№455/№464: раньше человек видел только
        «No module named 'onnx_asr'», а распознавание тихо становилось хуже)."""
        err = str(err or "")
        if "библиотеки" in err:
            import pydeps
            return (f"Точное распознавание речи (GigaAM) не запустилось: {err}. Пока слушаю запасной моделью — она ошибается "
                    f"чаще. Починить: {pydeps.fix_hint()}. Или распознавание через облако: студия → «Слух» → «Dewiar Облако».")
        return f"GigaAM не загрузился: {err}. Работаю на Vosk."

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
        gm = self._asr_name()
        g = self.gigaam if self.gigaam is not None and self.gigaam.model_name == gm else GigaAMSTT(gm)
        gok = g.cached()
        items.append({"key": "gigaam", "group": "ears",
                      "title": "Parakeet v3 — точное распознавание речи" if g.title == "Parakeet" else "GigaAM v3 — точное распознавание речи",
                      "about": "Английский и ещё 24 европейских языка, на процессоре, без интернета." if g.title == "Parakeet"
                      else "Лучшее качество для русского, на процессоре, без интернета.", "installed": gok,
                      "mb": self._dir_mb(g.local_dir, MODELS_DIR / "hf" / "hub") if gok else g.mb, "used": st.get("engine") == "gigaam"})
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
                    gm = self._asr_name()
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
