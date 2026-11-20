"""Быстрые пути ответа без модели (примесь AnswerMixin, core/engine_answer.py; чистое ядро 1.0.10): напоминание с файлами,
вложения к вопросу, «спасибо», «спи», музыка и радио словами, темп речи, «обновись», звонок, передача персонажу,
«запомни, что…»."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from answer_rules import ATT_DEFAULT_Q, ATT_REF_RX, REF_RX, SPEED_RX, _thumb


class DirectMixin:
    def _reminder_with_files(self, text, files, via=None):
        """«Напомни завтра в 10» + снимки или файлы (вставлены из буфера, перетащены) — заметка с ними в «Заметки/
        Напоминания» и напоминание со ссылкой на неё (note): в срок окно-будильник покажет картинки, а телефон откроет
        заметку. Без модели — сразу. -> True, если это было такое напоминание."""
        import base64
        from when import parse as parse_when
        r = parse_when(text)
        if not r:
            return False
        data = []
        for f in files[:12]:
            raw = str(f.get("b64") or "")
            try:
                b = base64.b64decode(raw.split(",", 1)[1] if raw.startswith("data:") else raw)
            except ValueError:
                continue
            if b:
                data.append((Path(str(f.get("name") or "файл")).name or "файл", b))
        if not data:
            return False
        self._reminder_note_from(r, text, data)
        r["said"] = text + "\n\nВложения:\n" + "\n".join(f"[{n}]" for n, _ in data)
        self._set_reminder_fast(r, via)
        return True

    def _reminder_note_from(self, r, said, data, chat=True):
        """Напоминание r (when.parse) и вложения [(имя, байты)] -> заметка; r дополняется note (путь), text (если
        «напомни завтра в 10» без слов — «Посмотреть картинки») и att; лента «Чата» получает миниатюры."""
        from workspace import NOTE_IMG
        pics = sum(1 for n, _ in data if Path(n).suffix.lower() in NOTE_IMG)
        title = (r.get("text") or "").strip()
        if not title or title in ("Напоминание", "Будильник", "Таймер") or REF_RX.match(title) or ATT_REF_RX.match(title):
            title = "Посмотреть картинки" if pics == len(data) else "Посмотреть файлы" if not pics else "Посмотреть вложения"
        at = r["at"]
        months = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")
        said0 = said.split("\n\nВложения:")[0].strip()
        body = f"Напоминание — {at.day} {months[at.month - 1]} в {at:%H:%M}." + (f"\n\n«{said0}»" if said0 else "")
        note = self.workspace.note_with_files(title, body, data)
        saved = []
        for f in note["att"]:
            x = dict(f)
            if f["kind"] == "image":
                try:
                    x["thumb"] = _thumb(self.workspace.safe(f["path"]).read_bytes())
                except OSError:
                    pass
            saved.append(x)
        if chat:
            self._chat_att = (time.monotonic(), saved)
        r.update(text=title, note=note["path"], att=note["att"])
        self.note_files_out(note["path"], [f["path"] for f in note["att"]])       # и на свой телефон — там та же заметка
        log.info("📎 Напоминание с вложениями (%d) → %s", len(note["att"]), note["path"])
        return note

    def _attach_files(self, text, files, images):
        """Файлы к вопросу: сохраняем во «Входящие» папки ассистента, текст документов — в вопрос модели,
        картинки — картинками (дописываются в images). -> текст вопроса с «\\n\\nВложения:». Не больше 10 файлов;
        текста документов всего ~24 000 символов (каждому не меньше 2000), остальное модель дочитает read_file."""
        import base64
        from eyes import prepare
        from knowledge import extract
        inbox = self.workspace.ensure() / "Входящие"
        inbox.mkdir(exist_ok=True)
        parts, budget = [], 24000
        saved = []                                         # для «Чата» студии: что приложено (имя, путь, миниатюра картинки)
        for f in files[:10]:
            name = Path(str(f.get("name") or "файл")).name or "файл"
            raw = f.get("b64", "")
            data = base64.b64decode(raw.split(",", 1)[1] if raw.startswith("data:") else raw)
            dst, n = inbox / name, 2
            while dst.exists():
                dst, n = inbox / f"{Path(name).stem} ({n}){Path(name).suffix}", n + 1
            dst.write_bytes(data)
            rel = dst.relative_to(self.workspace.root).as_posix()
            if Path(name).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
                try:
                    images.append(prepare(data)[0])
                    parts.append(f"[Картинка «{name}» — приложена ниже, сохранена: {rel}]")
                    saved.append({"kind": "image", "name": dst.name, "path": rel, "thumb": _thumb(data)})
                    continue
                except Exception:  # noqa: BLE001
                    pass
            saved.append({"kind": "file", "name": dst.name, "path": rel, "size": len(data)})
            info = {}
            try:
                # скан PDF (идея №68) — страницы без текста распознаёт локальный движок, если он есть (ocr.py)
                from knowledge import EXTS as KX                  # №892: и Excel, LibreOffice, PowerPoint — текстом
                body = extract(dst, ocr="local", info=info) if dst.suffix.lower() in KX | {".xls"} \
                    else (data.decode("utf-8") if len(data) < 400_000 else "")
            except Exception as e:  # noqa: BLE001
                body = ""
                log.info("Вложение %s: текст не извлечён (%s)", name, e)
                if isinstance(e, ValueError) and not isinstance(e, UnicodeDecodeError):   # понятная причина (sheets: «.xls — сохраните как .xlsx»)
                    info["why"] = str(e)
            body = (body or "").strip()
            if not body and info.get("scan"):
                # распознать нечем — первые страницы картинками: модель со зрением прочитает их сама (без зрения —
                # _drop_images оставит пометку, и модель честно скажет, что ей нужно), а не «текста в нём нет»
                pics = self._scan_pages(dst)
                if pics:
                    images.extend(pics)
                    parts.append(f"[Скан «{name}» без текстового слоя, сохранён: {rel} — первые {len(pics)} стр. приложены "
                                 "картинками ниже: прочитай текст с них]")
                    log.info("📎 %s → %s (скан, %d стр. картинками)", name, rel, len(pics))
                    continue
            if body and info.get("ocr_pages"):
                body = f"(скан: текст распознан, возможны опечатки)\n{body}"
            if body:
                cut = body[:max(2000, budget)]
                budget -= len(cut)
                parts.append(f"[Файл «{name}», сохранён в папке ассистента: {rel}]\n{cut}" +
                             ("\n…(дальше файл обрезан — целиком его можно прочитать инструментом read_file)" if len(cut) < len(body) else ""))
            else:
                parts.append(f"[Файл «{name}» ({len(data) // 1024} КБ) сохранён в папке ассистента: {rel}; " +
                             (f"прочитать не удалось: {info['why']}]" if info.get("why") else "текста в нём нет]"))
            log.info("📎 %s → %s", name, rel)
        self._chat_att = (time.monotonic(), saved)
        q = text.strip() or ATT_DEFAULT_Q
        return q + "\n\nВложения:\n" + "\n\n".join(parts)

    @staticmethod
    def _scan_pages(path, n=3):
        """Первые n страниц скана PDF -> [JPEG base64] для модели со зрением."""
        try:
            import ocr
            out = []
            for i in range(n):
                im = ocr.page_image(path, i)
                if im is None:
                    break
                out.append(ocr.jpeg_b64(im))
            return out
        except Exception as e:  # noqa: BLE001
            log.info("Скан %s картинками: %s", path, e)
            return []

    def _thanks(self, text):
        """«Спасибо» — коротко ответить и уснуть до имени (без окна «можно без имени» и без модели)."""
        import random
        self.follow_up_until = 0.0
        log.info("🙏 «%s» — отвечаю и сплю до имени", text)
        self._say_quick(random.choice(THANKS_REPLIES), text, then=lambda: (setattr(self, "follow_up_until", 0.0), self.play_tone("sleep")))

    def go_sleep(self, word="", media=True):
        """Замолчать и уснуть до следующего имени: без «слушаю», без продолжения разговора. Звенит будильник —
        выключить; media и слово-«стоп» — ещё и поставить музыку на паузу."""
        if self.alarm:
            self.alarm_finish("ack")
        self.cancel_turn()
        self.follow_up_until = 0.0
        self.set_state("idle")
        log.info("💤 «%s» — сплю до имени", word or "стоп")
        self.emit("sleep", word=word)
        self.play_tone("sleep")
        w = re.sub(r"[^\w]", "", (word or "").lower())
        if media and w in MEDIA_STOP | {"stop", "останови"}:
            threading.Thread(target=self._media_stop_word, args=(w, False), daemon=True).start()

    MEDIA_STOP_LONE_S = 1.6           # «стоп» командой — короткая фраза с тишиной вокруг, а не слово посреди разговора

    def _media_stop_heard(self, word, now, in_speech):
        """Быстрый слух (Vosk) услышал одно слово-стоп без имени, пока Лира ждёт. Своё радио — на паузу сразу, как
        раньше. Чужую музыку (плеер в другой программе) — только если и точная проверка согласна: 20.11 (владелец:
        «ложное "стой"… всегда ставит музыку на паузу… пару раз за рабочий день») Vosk с грамматикой из одних команд
        натягивал на «стой» обрывок разговора рядом. Решаем по самой фразе — когда она закончится (_media_stop_utt)."""
        if self.radio.playing:
            threading.Thread(target=self._media_stop_word, args=(word,), daemon=True).start()
            return
        uid = getattr(self, "utt_id", 0)
        last = getattr(self, "_idle_utt_last", None)
        if not in_speech and last and last[2] == uid and now - last[1] < 2.5:
            self._media_stop_check(word, last[0])        # фраза уже кончилась — звук есть
        else:
            self._media_stop_cand = (word, now, uid)     # ещё звучит — проверим, когда кончится

    def _media_stop_utt(self, pcm, now):
        """Конец любой фразы: запомнить её (для «стоп», которое быстрый слух дослышит чуть позже) и, если по ней ждёт
        решение «стоп» для чужой музыки, — отдать на проверку."""
        uid = getattr(self, "utt_id", 0)
        self._idle_utt_last = (pcm, now, uid)
        cand = getattr(self, "_media_stop_cand", None)
        if cand and cand[2] == uid and now - cand[1] < 4:
            self._media_stop_cand = None
            self._media_stop_check(cand[0], pcm)

    def _media_stop_check(self, word, pcm):
        """Чужая музыка и «стоп» без имени: фраза длиннее ~1,6 с — это разговор, в котором мелькнуло слово, не команда.
        Короткую — перепроверяет точная модель (GigaAM, если стоит; в потоке проверок), её нет — верим короткой фразе."""
        dur = len(pcm) / 2 / RATE
        if dur > self.MEDIA_STOP_LONE_S:
            log.info("«%s» внутри разговора (%.1f с) — музыку не трогаю", word, dur)
            return
        if self._stop_checker() is None:
            threading.Thread(target=self._media_stop_word, args=(word,), daemon=True).start()
            return
        if self.check_q.qsize() < 3:
            self.check_q.put(("media_stop", pcm, word))

    def _media_stop_verify(self, pcm, word):
        """Поток проверок: точная модель слышит в короткой фразе только слово-стоп (одно-два слова) — пауза; слышит
        другое («с той стороны», «постой-ка, Вань») — нет. Не проверилось — верим быстрому слуху, как раньше."""
        text = None
        try:
            text = self._stop_checker().transcribe(pcm).strip()
        except Exception as e:  # noqa: BLE001
            log.debug("проверка «%s» для музыки не удалась: %s", word, e)
        if text is not None:
            ws = re.findall(r"[\wё]+", _norm(text))
            if not ws or len(ws) > 2 or not self._stop_hit(text):
                log.info("«%s» — точная проверка слышит «%s»: музыку не трогаю", word, text[:60])
                return
        self._media_stop_word(word)

    def _media_stop_word(self, word, force=False):
        """«Пауза» / «стоп» без имени, пока играет музыка — ставим её на паузу -> True, если поставили. Если ничего
        не играет — молчим (слово могли сказать не ассистенту). force — после имени: если узнать, играет ли что-то,
        нельзя (media_playing() → None, Windows), всё равно жмём «играть/пауза»."""
        from tools import media_playing, t_media
        if self.radio.playing:                          # своё радио — сразу, без MPRIS
            st = self.radio.pause()
            log.info("⏸ «%s» — радио «%s» на паузе", word, (st or {}).get("name", ""))
            self.emit("heard", text=word.capitalize())
            self.emit("answer", text=f"На паузе. Продолжить — «{self.persona_name()}, продолжи».", done=True)
            return True
        playing = media_playing()
        if not (playing or (force and playing is None)):
            return False
        try:
            t_media({"action": "pause" if playing else "play_pause"}, {})
            log.info("⏸ «%s» — музыка на паузе", word)
            self.emit("heard", text=word.capitalize())
            self.emit("answer", text="Пауза.", done=True)
            return True
        except Exception as e:  # noqa: BLE001
            log.info("Пауза не получилась: %s", e)
            return False

    def _speed_cmd(self, text, via=None):
        """«Говори помедленнее», «быстрее», «не так быстро» -> True (темп сменён и сказано), иначе False."""
        m = SPEED_RX.match((text or "").strip().replace("ё", "е").replace("Ё", "Е"))
        if not m:
            return False
        who = (m.group("who") or "").lower()
        if who and not m.group("sep") and who not in ("говори", "говорите", "можно", "пожалуйста", "читай", "разговаривай"):
            names = set()                                # «Лира медленнее» — да; «машина быстрее» — не просьба о темпе
            try:
                for p in self.personas.all():
                    names |= {str(x).lower() for x in [p.get("name")] + list(p.get("aliases") or p.get("wake") or [])}
            except Exception:  # noqa: BLE001
                pass
            if who not in names:
                return False
        slower = (m.group("how") or "").lower() == "медленнее" or bool(m.group("notfast"))
        if not slower and not re.search(r"(?i)говори|разговаривай|читай", text):
            return False                                 # «быстрее!» без «говори» — скорее «поторопись», чем о темпе голоса
        v = float(self.s.get("tts", "speed") or 1.25)
        nv = round(min(1.4, max(0.7, v + (-0.15 if slower else 0.15))), 2)
        if nv == round(v, 2):
            self._say_quick("Медленнее уже некуда — это самый спокойный темп." if slower else "Быстрее уже некуда — это самый быстрый темп.", text, via)
            return True
        self.s.update({"tts": {"speed": nv}})
        log.info("🗣 Темп речи: %.2f → %.2f («%s»)", v, nv, text)
        self.emit("settings", settings=self.s.snapshot())    # студия: ползунок «Темп речи» — на новом месте
        self._say_quick("Хорошо, говорю медленнее." if slower else "Хорошо, говорю быстрее.", text, via)
        return True

    def _media_word(self, word):
        """Пока играет радио — одно слово без имени, как у колонки: «дальше», «громче», «тише»."""
        if not self.radio.playing:
            return
        log.info("📻 «%s» без имени — радио", word)
        if word in ("громче", "погромче", "тише", "потише"):
            self._radio_step(word in ("громче", "погромче"), word.capitalize())
        else:
            self._music_cmd("дальше")

    def _radio_step(self, up, said):
        """Громче / тише своего радио (шаг 20%). Уже на максимуме или минимуме — False: дальше решит громкость системы."""
        v = self.radio.volume
        if (up and v >= 0.99) or (not up and v <= 0.11):
            return False
        nv = self.radio.set_volume(round(v + (0.2 if up else -0.2), 2))
        self.s.update({"audio": {"radio_volume": nv}})
        log.info("📻 Громкость радио: %d%% → %d%%", round(v * 100), round(nv * 100))
        self.emit("heard", text=said)
        self.emit("answer", text=f"Радио {'громче' if up else 'тише'}: {round(nv * 100)}%.", done=True)
        self.emit("radio", **self.radio.status())
        self.set_state("idle")
        return True

    def _direct_update(self, text, via=None):
        """«Обновись», «проверь обновления» — проверить сайт сейчас же и сказать итог, без модели (модель обещала «сейчас
        посмотрю» и не вызывала app_update). Новое скачивается и проверяется, в виджете — плашка «Доступна версия …»:
        ставит человек одним нажатием. -> True, если это была такая просьба."""
        from engine_base import UPDATE_RX
        up = getattr(self, "updater", None)
        if up is None or not UPDATE_RX.match(text or ""):
            return False

        def run():
            try:
                info = up.check(wait=False)      # 0.82.2: скачивание — в фоне, с ходом в виджете
                st = up.public()
            except Exception as e:  # noqa: BLE001
                info, st = None, {"error": str(e)}
            cur = st.get("current") or ""
            if info and not info.get("path"):
                msg = (f"Есть новая версия — {info['version']}. Скачиваю — ход видно в виджете; когда скачается, нажмите на плашку "
                       "«Доступна версия» — обновление встанет за минуту, разговор и настройки сохранятся.")
            elif info:
                msg = (f"Есть новая версия — {info['version']}, она уже скачана. Нажмите на плашку «Доступна версия» в виджете — "
                       "обновление встанет за минуту, разговор и настройки сохранятся.")
            elif st.get("error"):
                msg = "Сейчас не получилось проверить обновления — сайт не ответил. Проверю позже ещё раз; можно и в студии: «О программе» → «Проверить обновления»."
            else:
                msg = f"Обновлений нет — у вас последняя версия{(' ' + cur) if cur else ''}."
            self._say_quick(msg, text, via)
        threading.Thread(target=run, name="update-now", daemon=True).start()
        return True

    def _direct_call(self, text):
        """«Позови Лиру», «дай слово Эве», «переключись на Кодера, …» — сразу, без языковой модели."""
        m = CALL_RX.match(text)
        if not m:
            return False
        pid = self.find_persona(m.group(1))
        if not pid or pid == self.s.get("persona"):
            return False
        prev = self.personas.get(self.s.get("persona"))["name"]
        log.info("👥 %s → %s (без модели)", prev, self.personas.get(pid)["name"])
        last = next((m for m in reversed(self.history) if m.get("role") == "assistant"), None)
        if last is not None and last.get("who") == self.s.get("persona"):
            last["handoff"] = pid                     # «позови Лиру» — человек сам передаёт слово: ей — разговор справкой
        self.emit("heard", text=text)
        with self._turn_lock:
            self._cancel_locked()
        self.switch_persona(pid)
        rest = m.group(2).strip(" ,.!?:;—-")
        if len(re.sub(r"\W", "", rest)) >= 2:
            self.ask(rest)
        else:
            self.ask(f"({prev} позвал(а) тебя в разговор. Поздоровайся одной короткой фразой от себя и спроси, "
                     f"чем помочь.)", quiet=True)
        return True

    def _tool_call_persona(self, name, task=""):
        """Инструмент «позвать персонажа»: сама передача — после ответа (turn.switch_to, конец _run_turn).
        task — поручение (идея №137, Gray: «передать задачу, а не только слово — второй начинает с чистого листа»):
        уходит новому персонажу явной вводной. -> текст для модели: что сказать сейчас."""
        pid = self.find_persona(name)
        added = ""
        if not pid:
            # №715 (14.11: «попросила подключить Гастона — Лира пишет, что не понимает, о ком речь»): готовый персонаж,
            # которого ещё нет в команде, — добавить в команду и позвать
            try:
                gal = [g for g in self.personas.gallery() if not g.get("installed")]
                gid = self._match_persona(name, gal)
                if gid:
                    pid = self.personas.gallery_add(gid)
                    added = self.personas.get(pid)["name"]
                    log.info("👥 «%s» добавлен(а) в команду из готовых по просьбе", added)
                    self.emit("personas", personas=self.personas.public())
            except Exception as e:  # noqa: BLE001
                log.warning("Готовый персонаж «%s» не добавился: %s", name, e)
        if not pid:
            names = ", ".join(p["name"] for p in self.personas.all())
            ready = ", ".join(g["name"] for g in self.personas.gallery() if not g.get("installed"))
            raise ToolError(f"нет персонажа «{name}». В команде: {names}" + (f". Готовые (добавятся сами, если позвать): {ready}" if ready else ""))
        if pid == self.s.get("persona"):
            return "Это ты сам(а). Просто продолжай разговор."
        t = self.turn
        if t is not None:
            t.switch_to = pid
            t.switch_task = str(task or "").strip()[:1500]
        who = self.personas.get(pid)["name"]
        return ((f"{who} добавлен(а) в команду (студия → «Персонажи»). " if added else "")
                + f"Готово: как только ты договоришь, {who} откликнется сам(а) своим голосом" + (" и возьмётся за поручение" if task else "")
                + f". Скажи одну короткую фразу, что передаёшь слово, и не отвечай за {who}.")

    def _maybe_learn(self, said, prof):
        """Учиться на ошибках: человек поправил ассистента («нет, я же просил коротко», «опять не то») — в фоне модель выводит
        общее правило из прошлого ответа и поправки, оно ложится в «Память/Уроки.md» и дальше идёт в подсказку разговоров и
        задач (quality.learn_from_correction). Не поправка — модель отвечает НЕТ, ничего не пишется."""
        import quality as Q
        if not Q.looks_like_correction(said) or not prof:
            return
        prev = next((m.get("content") for m in reversed(self.history[:-1]) if m.get("role") == "assistant" and m.get("content")), "")
        if not prev:
            return
        if hasattr(self, "day_miss"):
            self.day_miss("correction", said, prev)         # «Ум Лиры», шаг 3 — замер: человек поправил

        def run():
            from llm import stream_chat
            ask = lambda q: "".join(stream_chat(dict(prof, max_tokens=120, temperature=0.2), "Отвечай кратко.",   # noqa: E731
                                                [{"role": "user", "content": q}]))
            try:
                rule = Q.learn_from_correction(ask, prev, said, self.workspace.root / Q.TALK_LESSONS_FILE)
            except Exception as e:  # noqa: BLE001
                log.info("📘 Урок из поправки не получился: %s", e)
                return
            if rule:
                log.info("📘 Урок из поправки: %s", rule)
                self.emit("lesson", text=rule)
        threading.Thread(target=run, name="learn", daemon=True).start()


# «Лира, смени образ», «надень зимний», «образ „Весна“», «выбирай образ сама», «верни обычный образ» (1.0.55)
LOOK_RX = re.compile(r"(?i)^(?:[а-яё]+,?\s+)?(?:(?P<next>смени|поменяй|другой|новый|следующий)\s+(?:свой\s+)?образ"
                     r"|(?P<auto>(?:выбирай|меняй|подбирай)\s+образ\w*\s+(?:сама?|по\s+(?:сезону|погоде|времени))"
                     r"|образ\w*\s+(?:сама?|по\s+сезону))"
                     r"|(?P<plain>(?:верни|сними)\s+(?:обычн\w+\s+образ|образ)|обычн\w+\s+образ)"
                     r"|(?:надень|переоденься\s+в|образ)\s+[«\"]?(?P<name>[а-яё]+))[»\".!? ]*$")


class LookMixin:
    def set_look(self, pid, look=None, auto=None):
        """Образ персонажа: look — id или "" (обычный), "next" — следующий по кругу; auto — «Сама — по времени и сезону».
        Хранится в настройках (looks: {pid: {look, auto}}), персонажи заново — окнам. -> public-персонаж или None."""
        p = self.personas.get(pid)
        cur = next((x for x in self.personas.public() if x["id"] == p["id"]), None)
        if not cur or not cur.get("looks"):
            return None
        all_ = self.s.get("looks") or {}
        pref = dict(all_.get(p["id"]) or {})
        ids = [x["id"] for x in cur["looks"]]
        if look == "next":
            look = ids[(ids.index(cur.get("look") or "") + 1) % len(ids)]
            auto = False
        if look is not None and look in ids:
            pref["look"] = look
            if auto is None:
                pref["auto"] = False
        if auto is not None:
            pref["auto"] = bool(auto)
        self.s.update({"looks": {**all_, p["id"]: pref}})
        pub = self.personas.public()
        self.emit("personas", personas=pub)
        return next((x for x in pub if x["id"] == p["id"]), None)

    def _direct_look(self, text, via=None):
        """Смена образа словами — сразу, без модели. -> True, если это была такая просьба."""
        m = LOOK_RX.match((text or "").strip())
        if not m:
            return False
        pid = self.s.get("persona")
        cur = next((x for x in self.personas.public() if x["id"] == pid), None)
        if not cur or not cur.get("looks"):
            return False
        names = {x["name"].lower(): x["id"] for x in cur["looks"]}
        if m.group("next"):
            q = self.set_look(pid, "next")
        elif m.group("auto"):
            q = self.set_look(pid, auto=True)
        elif m.group("plain"):
            q = self.set_look(pid, "")
        else:
            w = m.group("name").lower().replace("ё", "е")         # «зимний» — «Зима», «шелковый» — «Шёлк», «домашний» — «Дома»
            hit = next((i for n, i in names.items() if n.replace("ё", "е")[:3] == w[:3]), None)
            if hit is None:
                return False
            q = self.set_look(pid, hit)
        if not q:
            return False
        name = next((x["name"] for x in q["looks"] if x["id"] == q.get("look")), "Обычная")
        msg = ("Хорошо, образ буду выбирать сама — по времени и сезону. Сегодня — «" + name + "».") if q.get("look_auto") \
            else ("Вернула обычный образ." if not q.get("look") else f"Готово — образ «{name}».")
        self._say_quick(msg, text, via)
        return True
