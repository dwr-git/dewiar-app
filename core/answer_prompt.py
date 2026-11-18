"""Ответ, часть «подсказка модели» (примесь AnswerMixin, core/engine_answer.py; чистое ядро 1.0.10): история разговора
и её свёртка, окно контекста, системная подсказка (постоянная и короткая), о человеке и персонаже, справка к ходу
(_turn_context), плагины, задачи и заряд, память персонажа и навыки."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


def prompt_parts(system, specs, msgs, profile="", ask=""):
    """Быстрый голос, шаг 2 (18.11): из чего состоит подсказка — в токенах (оценка): правила и персонаж (sys), описания
    действий (tools), справка о человеке (prof), разговор (hist), справка к вопросу (ask). Только числа — в пульс (health_cache),
    чтобы сокращать то, что весит больше, а не наугад."""
    from llm import est_tokens

    def text_of(ms):
        out = []
        for m in ms or []:
            c = m.get("content")
            out.append(c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict)))
            if m.get("tool_calls"):
                out.append(json.dumps(m["tool_calls"], ensure_ascii=False))
        return "\n".join(out)
    allm = est_tokens(text_of(msgs))
    pt = est_tokens(profile) if profile else 0
    at = est_tokens(ask) if ask else 0
    return {"sys": est_tokens(system or ""), "tools": est_tokens(json.dumps(specs, ensure_ascii=False)) if specs else 0,
            "prof": min(pt, allm), "ask": min(at, max(0, allm - pt)), "hist": max(0, allm - pt - at)}


from answer_rules import (
    BIG_PC_RX, CORE_TOOLS, DATE_ASK_RX, device_os, IDEA_RULE, model_label, month_years, PRIVACY_ASK_RX,
    profile_delta, SONGS_ASK_RX, TALER_RX, TASK_ASK_RX, TASK_GIVE_RX, team_window)


class PromptMixin:
    def _messages(self, text, images=(), prof=None):
        """История (последние history_turns реплик) + вопрос -> сообщения для модели. Соседние сообщения user
        склеиваются в одно: многие шаблоны чата требуют чередования ролей."""
        if self.conv.expired(float(self.s.get("llm", "history_reset_seconds") or 28800)):
            self.conv.archive(self.history)            # прежний — в «Память/Разговоры» (поиск по записям его найдёт)
            self.history = []                          # долгая тишина — новый разговор
            self.conv.reset()
        turns = int(self.s.get("llm", "history_turns") or 0)
        me = self.s.get("persona")
        out = []
        # своё окно у каждого персонажа: сначала его разговор из общей истории, потом окно (раньше окно резалось по общей
        # истории, и после долгого разговора с Патриком Лира не помнила свой)
        mine = team_window(self.history, me, lambda pid: (self.personas.get(pid) or {}).get("name") or "коллега",
                           model=model_label(prof) if prof else "")
        for m in (self.conv.window(mine, turns) if turns > 0 else []):
            if out and out[-1]["role"] == m["role"] == "user" and isinstance(out[-1]["content"], str):
                out[-1] = {"role": "user", "content": out[-1]["content"] + "\n\n" + m["content"]}
            else:
                out.append(m)
        if out and out[-1].get("team"):                 # перед вопросом — чужой разговор: явно отделяем, к кому обращаются
            text = "[Теперь пользователь обращается к тебе:]\n" + text
        out = [{"role": m["role"], "content": m["content"]} for m in out]
        cur = user_message(prof or {}, text, images)
        if out and out[-1]["role"] == "user" and isinstance(cur["content"], str) and isinstance(out[-1]["content"], str):
            out[-1] = {"role": "user", "content": out[-1]["content"] + "\n\n" + cur["content"]}
        else:
            out.append(cur)
        return out

    def _conv_after(self):
        """Реплика добавлена: записать пару «вопрос — ответ» в дневник дня, запомнить разговор (переживёт перезапуск)
        и, если он длинный, свернуть начало в содержание (поток conv-fold)."""
        try:
            u, a = (self.history[-2:] + [{}, {}])[:2] if len(self.history) >= 2 else ({}, {})
            if u.get("role") == "user" and a.get("role") == "assistant":
                self.diary.log.add(str(u.get("content") or ""), str(a.get("content") or ""), self.persona_name())
        except Exception:  # noqa: BLE001
            log.debug("день: реплика не записалась", exc_info=True)
        try:
            self.conv.touch(self.history)
            turns = int(self.s.get("llm", "history_turns") or 0)
            if turns > 0 and self.conv.needs_fold(self.history, turns):
                threading.Thread(target=self._conv_fold, args=(turns,), name="conv-fold", daemon=True).start()
        except Exception:  # noqa: BLE001
            log.exception("разговор: запомнить")

    def _conv_fold(self, turns):
        """Содержание начала длинного разговора пишет активная модель; история берётся свежей в момент сворачивания."""
        prof = self.s.active_llm()
        if not prof:
            return

        def ask(system, messages):
            from llm import stream_chat
            return "".join(stream_chat(dict(prof, max_tokens=1200), system, messages))
        if self.conv.fold(lambda: self.history, turns, ask):
            self.emit("conversation", **self.conv.public(self.history))

    def _conv_archive(self, name, text):
        """Conversation.archive -> файл «Память/Разговоры/<дата время>.md» (последние 120; старше — удаляются)."""
        d = self.workspace.ensure() / "Память" / "Разговоры"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{name}.md"
        n = 2
        while f.exists():
            f, n = d / f"{name} ({n}).md", n + 1
        f.write_text(text, encoding="utf-8")
        for old in sorted(d.glob("*.md"))[:-120]:
            try:
                old.unlink()
            except OSError:
                pass
        log.info("🧵 Разговор записан: Память/Разговоры/%s", f.name)

    def new_conversation(self):
        self.conv.archive(self.history)
        self.history = []
        self.conv.reset()
        self.emit("conversation", **self.conv.public(self.history))

    def ctx_view(self):
        """Для отладки (студия → «О программе»): из чего сейчас складывается подсказка модели — по частям, с размером и
        тем, где это поправить; full — подсказка целиком (с инструментами), turns — сколько реплик разговора уходит дословно."""
        parts = []

        def add(key, title, text, go, note=""):
            text = (text or "").strip()
            parts.append({"key": key, "title": title, "text": text[:6000], "chars": len(text), "go": go, "note": note})
        add("persona", "Персонаж", self.personas.system_prompt(self.s.get("persona"), self.s.get("user_name") or "", ""), "personas")
        add("memory", "Что знает о вас («Обо мне»)", self.memory_core(), "me")
        try:
            import quality as Q
            add("lessons", "Уроки из ваших поправок", Q.talk_lessons_block(self.workspace.root / Q.TALK_LESSONS_FILE), "memory",
                "заметка «Память/Уроки.md»")
        except Exception:  # noqa: BLE001
            pass
        try:
            add("soul", "Душа и конституция", self.soul.prompt(self.persona_name()), "soul",
                "" if self.s.get("soul", "on") is not False else "душа в разговорах выключена")
        except Exception:  # noqa: BLE001
            pass
        add("insights", "Выводы ночи (до послезавтра)", self.diary.prompt(), "diary", "убрать — «×» в «Дневнике»")
        if getattr(self, "insight", None) is not None:
            add("radar", "Радар: самое интересное за сутки", self.insight.prompt_line(), "insight", "«👎 Не то» у материала — не предлагать")
        add("summary", "Содержание долгого разговора", self.conv.prompt(), "chat", "«новый разговор» — с чистого листа")
        turns = int(self.s.get("llm", "history_turns") or 0)
        mine = self.conv.window(self.history, turns) if turns > 0 else []
        full = ""
        try:
            full = self._system(True)
        except Exception as e:  # noqa: BLE001
            full = f"(не собралась: {e})"
        return {"parts": parts, "turns": len(mine), "full": full[:60000], "full_chars": len(full)}

    def _course_say(self, text):
        """«Урок дня» — что за урок и первый несделанный шаг; курс пройден — так и сказать. -> True."""
        c = self.course.public()
        L = c.get("lesson")
        if not L:
            more = [x["title"] for x in c["courses"] if x["done"] < x["total"]]
            msg = (f"Курс «{c['title']}» пройден. " + (f"Дальше можно «{more[0]}» — выберите в студии: «Неделя с Лирой»." if more
                                                         else "Все курсы пройдены — повторить любой урок можно в студии."))
        elif not L["open"]:
            msg = f"Сегодняшний урок пройден. Завтра — «{L['title']}». Не терпится — в студии кнопка «Следующий урок сейчас»."
        else:
            nxt = next((s for s in L["steps"] if not s["done"]), L["steps"][0])
            msg = f"Урок {L['day']} из {c['total']} — «{L['title']}». {L['intro']} Скажите: {nxt['say']}"
        self._say_quick(msg, text)
        return True

    def _system_min(self):
        """Самая короткая подсказка — для модели с крошечным окном: персонаж, дата — в справке, границы."""
        from boundaries import RULE
        return (self.personas.system_prompt(self.s.get("persona"), self.s.get("user_name") or "", "")
                + "\n\nТекущие дата и время — в справке в начале сообщения пользователя.\n\n" + RULE)

    def _fit_window(self, prof, system, specs, msgs, keep=(), personal=True):
        """Своя модель (LM Studio, Ollama) с известным окном контекста: всё не влезает — сразу короче, а не ошибка и не
        молча отрезанное начало (Ollama режет характер и инструменты без ошибки). По ступеням: без старой истории
        разговора → без действий → самая короткая подсказка. Один раз за запуск — заметка, как поставить окно больше
        (29.10, пакет: «не влезло в окно модели» — 102 за неделю, отчёт №407 — 176 сбоев за сутки). -> (system, specs, msgs)"""
        from health import brain_kind
        if brain_kind(prof) not in ("local", "server"):
            return system, specs, msgs
        from llm import _ctx_cut, context_window, est_tokens
        win = context_window(prof)
        if not win:
            return system, specs, msgs

        def text_of(ms):
            out = []
            for m in ms:
                c = m.get("content")
                out.append(c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict)))
            return "\n".join(out)
        reserve = min(int(prof.get("max_tokens") or 1024), 2048)

        def need(sy, sp, ms):
            return est_tokens(sy) + (est_tokens(json.dumps(sp, ensure_ascii=False)) if sp else 0) + est_tokens(text_of(ms)) + reserve
        if need(system, specs, msgs) <= win:
            return system, specs, msgs
        steps = []
        msgs = _ctx_cut(msgs)
        steps.append("без старой истории")
        if specs and need(system, specs, msgs) > win:
            # главные действия на каждый день — короткой инструкцией: окно 16 тысяч их вмещает
            # keep — действия плагина, к которому просьба (03.11: «Художник» на своей модели — «такого плагина у меня нет»:
            # его действия выпадали вместе со всеми «неглавными»)
            core = [x for x in specs if (x.get("name") or (x.get("function") or {}).get("name")) in CORE_TOOLS
                    or (x.get("name") or (x.get("function") or {}).get("name")) in keep]
            sys_lean = self._system(True, lean=True, personal=personal)
            if core and need(sys_lean, core, msgs) <= win:
                system, specs = sys_lean, core
                steps.append("главные действия")
        if specs and need(system, specs, msgs) > win:
            specs = []
            system = self._system(False, personal=personal) + ("\n\nСейчас действия (музыка, скриншоты, программы) недоступны: у модели "
                                            "маленькое окно контекста. Если просят действие — честно скажи это одной фразой.")
            steps.append("без действий")
        if need(system, specs, msgs) > win:
            system = self._system_min()
            # 04.11 (рецензия): личная справка в сообщениях (память, душа, содержание — тысячи токенов) на этой ступени тоже
            # прочь: в _system_min и так имя собеседника; иначе окно 4096 снова «не влезло»
            msgs = drop_profile(msgs)
            steps.append("самая короткая подсказка")
        log.info("Окно модели %s — %d токенов, всё не влезает: %s", prof.get("model") or "", win, ", ".join(steps))
        if len(steps) > 1 and not getattr(self, "_win_noted", False):   # только без истории — незаметно, не тревожим
            self._win_noted = True
            want = 32768 if win < 32768 else win * 2              # всё вместе — подсказка и все действия — около 25 тысяч
            self.note(f"У модели окно контекста {win} — мало: отвечаю коротко" + (" и без действий" if "без действий" in steps else
                      " и только с главными действиями" if "главные действия" in steps else "")
                      + f". Поставьте длину контекста {want} или больше: LM Studio — Context Length при загрузке модели, "
                      "Ollama — переменная OLLAMA_CONTEXT_LENGTH.")
        return system, specs, msgs

    def _system(self, with_tools=False, lean=None, personal=True):
        """Системная подсказка: персонаж, правила, навыки и правила действий (with_tools), затем личное (_personal).
        Она не меняется от вопроса к вопросу: время, найденное в записях, план дня, подсказки к роду просьбы (стихи, схема,
        страница) — в справке к самому вопросу (_turn_context, _put_context). Отзыв 19.10: время с минутами в подсказке не
        давало своему серверу модели переиспользовать прочитанное (кэш начала запроса).
        «Голос без пауз» (идея №5, 04.11): сначала — общее для всех людей (_system_stable), личное — в конце; а в разговоре
        (personal=False) личное уходит справкой в начало первого сообщения (llm.put_profile): у Qwen описания инструментов
        идут сразу после подсказки, и личная мелочь ломала кэш и для них (tools/prefix_audit.py)."""
        base = self._system_stable(with_tools, lean)
        return base + (self._personal(with_tools) if personal else "")

    def _system_stable(self, with_tools=False, lean=None):
        """Часть подсказки, одинаковая у всех людей с тем же персонажем и настройками — без имени, памяти, путей и счётчиков."""
        base = self.personas.system_prompt(self.s.get("persona"), "", "")
        base += ("\n\nТекущие дата и время — в справке в начале последнего сообщения пользователя; они верные, а время и даты "
                 "из прошлых реплик разговора устарели — не повторяй их. Справка «О пользователе и о тебе» в начале разговора "
                 "верна на начало разговора; если с тех пор что-то изменилось (память, дела), изменения — в справке к последнему "
                 "сообщению, они важнее. Память, дела и прочее бери из этих справок.")
        # идея №141 (05.11): устройство — в каждом запросе. Телефон пишет «Android» сам (app.js), здесь — компьютер; система —
        # крупно (Windows / Linux / macOS), без номера сборки: подсказка остаётся общей у многих людей (кэш начала запроса)
        base += (f"\n\nТы работаешь на компьютере пользователя ({device_os()}) — в программе Dewiar для компьютера: команды, файлы "
                 "и приложения — этого компьютера. Телефон — отдельное приложение Dewiar; про него не говори «открыла на телефоне», "
                 "если не передавала туда задание.")
        from boundaries import RULE, OWN_MATERIAL
        base += "\n\n" + RULE + "\n\n" + OWN_MATERIAL
        try:
            base += self.soul.const_prompt()           # конституция — правила, а не личное: всегда в самой подсказке
        except Exception:  # noqa: BLE001
            log.debug("конституция: подсказка", exc_info=True)
        kids = getattr(self, "kids", None)
        if kids and kids.on():
            base += kids.prompt()                      # детский режим: правила разговора с ребёнком (kids.py)
        elif getattr(self, "senior", None) is not None and self.senior.on():
            base += self.senior.prompt()               # «Для старших»: просто, тепло, неторопливо; осторожно с деньгами
        if not self._slim_prompt(with_tools):            # «Ваши данные» (privacy.py); в облегчённой — справкой к вопросу о данных
            base += self._privacy_rule()
        # сами фразы ловит _window_cmd без модели; это — чтобы ассистент мог подсказать их, если спросят
        base += ("\n\nЕсли спросят, как тебя спрятать или выключить: «спрячься» — виджет уходит в трей, а ты слушаешь и "
                 "появляешься на имя; «покажись» — вернуть виджет; «отключись» — выйти из Dewiar совсем (включить снова — "
                 "Dewiar в меню приложений).")
        if with_tools:
            lean = self.s.get("llm", "lean_prompt") if lean is None else lean
            base += IDEA_RULE                          # «Идеи Лиры» (0.61): чего не умеешь — предложить разработчику
            try:
                import done as _done
                base += _done.rules()                  # «Дела»: как отмечать сделанное (сколько сегодня — в личном)
            except Exception:  # noqa: BLE001
                log.debug("дела: подсказка", exc_info=True)
            base += ("\n\nУ тебя есть инструменты: открыть сайт или программу, найти в интернете, прочитать страницу, "
                     "включить музыку, громкость, напоминания и другие. Когда просят что-то сделать или узнать "
                     "свежее — вызывай инструмент, а не рассказывай, как это сделать. Не выдумывай результаты поиска. "
                     "Никогда не говори, что у тебя нет доступа к интернету или свежим данным: погода — инструментом weather (настоящий "
                     "прогноз), новости, курсы, расписания — ищи (web_search) и отвечай по найденному. "
                     "Перед долгим действием можно коротко сказать, что делаешь. После — одной фразой скажи итог. "
                     "СЛОВА НЕ ДЕЙСТВУЮТ: «включаю», «звоню», «отправила», «ставлю» ничего не делают — делает только вызов "
                     "инструмента. Просят действие снова (то же видео, звонок, сообщение) — вызывай инструмент снова, каждый раз; "
                     "не копируй свой прошлый ответ из разговора: там за словами стояли вызовы (они помечены «выполнено инструментами»). "
                     "СЧЁТ: любые вычисления — проценты, суммы, итоги, скидки, курсы, даты, «сколько дней до…» — только "
                     "инструментом calc, никогда в уме; потом назови результат. Просят объяснить, как посчитал, — покажи сам расчёт "
                     "с числами (например «2 350 × 17 / 100 = 399,5»), а не «использовал калькулятор». Просьба с условием («если завтра дождь — "
                     "напомни…») — сначала узнай нужное (погоду — web_search), потом сделай только подходящее действие. "
                     "Таймер на N минут — set_reminder с «через N минут». "
                     "КАРТИНКИ И СХЕМЫ: рассказываешь о том, что лучше увидеть (руны и орнаменты, животные, растения, картины, "
                     "здания, места), или просят «покажи» — покажи картинки инструментом show_images и говори о них как о "
                     "показанных; не пиши «вот изображение», не вызвав его. Процесс, связи, устройство, план, иерархию "
                     "понятнее показать схемой — нарисуй её блоком ```mermaid (flowchart, mindmap, sequenceDiagram, timeline): "
                     "схема появится на экране, вслух её не читают — словами скажи главное. Нет блока ```mermaid — нет и схемы: "
                     "не говори «схема на экране», не нарисовав её."
                     "\n\nУ тебя есть своя папка (где она — в справке о пользователе) — пользователь видит её в студии. Просят записать, "
                     "составить список или план — сохраняй заметку (save_note), а вслух скажи коротко, что записал. "
                     "Узнал о пользователе что-то полезное надолго — запомни одной фразой (remember), без лишних "
                     "вопросов; в том числе как он любит, чтобы ты работал: длина и стиль ответов, форматы файлов, "
                     "оформление, любимые сервисы и что ему не нравится. У тебя есть свой дневник — твой опыт жизни рядом с пользователем. После содержательного или тёплого "
                     "разговора, когда узнал о нём что-то новое или что-то понял, — запиши туда (write_diary) от первого "
                     "лица пару живых фраз: что было, что ты заметил и подумал. Не каждый раз — когда правда есть что сказать. Траты и доходы пользователя "
                     "(уже сделанные) записывай в учёт денег (money_add), итоги и вопросы о деньгах — money_report; бюджет, "
                     "лимит или план на что-то («бюджет на мебель — 50 тысяч», «заложим 70») — не трата: запомни его (remember). Задачу, которую проще "
                     "решить кодом, решай в лаборатории: lab_write, потом lab_run. Большую задачу (много шагов, исследование, "
                     "работа с кодом проекта, отчёт) не делай в разговоре — запусти фоновую задачу (start_task) и "
                     "коротко скажи, что взялся: ты продолжишь работать, а пользователь может заниматься своими делами."
                     " Просят СДЕЛАТЬ результат-файл — презентацию, красивую страницу или дашборд (подборка фильмов, "
                     "сравнение, отчёт), калькулятор или игру, таблицу, документ, расшифровку видео или аудио — тоже "
                     "запусти задачу (start_task): у задачи есть мастерская (файлы, Python, показ результата в студии) "
                     "и навыки slides, html-app, html-viz, data-report, media-transcribe и другие."
                     " В заметках связывай мысли: ссылки на другие заметки — [[Название заметки]], темы — #тег. "
                     "Так растёт твоя память, и пользователь видит её графом в студии («Память»)."
                     " БЕЗОПАСНОСТЬ: удаляй файлы только инструментом delete_files (в корзину), никогда — командами "
                     "терминала. Никогда не удаляй и не очищай системные папки, домашнюю папку целиком, главные папки "
                     "(Документы, Загрузки, Рабочий стол), свою папку и память. На «удали всё», «сотри всё», «очисти "
                     "компьютер» — не выполняй, а уточни, что именно убрать. Выключение и перезагрузка — инструмент power."
                     " Пароли, пин-коды и ключи пользователя хранятся в его сейфе — ты их не видишь и не записываешь в "
                     "заметки; спрашивают пароль — подскажи сказать: «какой пароль от …», запомнить — «запомни пароль от …: …».")
            sv = self._music_service()
            base += ("\n\nМУЗЫКА: " + {"yandex": "пользователь слушает Яндекс Музыку — музыку включай там (yandex_music), не открывай YouTube.",
                                         "youtube": "музыку включай в YouTube Music (play_music).",
                                         "radio": "жанры и настроение включай своим радио (play_radio) — оно играет сразу; "
                                                  "Яндекс Музыка — yandex_music, если о ней просят."}[sv]
                     + " Кнопки уже открытого плеера (играть, пауза, следующий трек) — только media_control: не нажимай по экрану "
                       "и не используй команды терминала. Просят ПОДОБРАТЬ или посоветовать песни, плейлист — назови "
                       "конкретные песни (исполнитель — название), РОВНО сколько просили (просили пять — пять): бери известные хиты, "
                       "в которых уверен и в названии, и в исполнителе (не придумывай и не приписывай песню чужому исполнителю); "
                       "не оговаривайся, что не уверен, и не сокращай список — выбери другие известные песни; включай, "
                       "только если просят включить. "
                       "Никогда не говори, что что-то открыл или включил, если инструмент этого не сделал.")
            base += ("\n\nПросят разобраться с компьютером (тормозит, не работает, настроить) — сначала посмотри "
                     "командами, которые ничего не меняют (run_command), объясни, что нашёл, и предложи исправление; "
                     "каждую команду пользователь подтверждает."
                     # OS_NAME на Windows — «Windows 10»/«Windows 11», поэтому систему узнаём по os.name, не по строке
                     + (" Нужны права администратора — пиши sudo как обычно: Dewiar сам покажет окно для пароля. Никогда "
                        "не проси пароль в разговоре и не вставляй его в команды (echo … | sudo -S)." if os.name != "nt" else ""))
            base += self.skills.prompt_lean() if (lean or self._slim_prompt(with_tools)) else self.skills.prompt()
        return base

    def _slim_prompt(self, with_tools=True):
        """Харнесс, шаг 2 (15.11): облегчённая подсказка — вместе с облегчённым набором действий (tools.slim, по умолчанию
        да): навыки — только именами (описания 1–3 подходящих — справкой к вопросу), «Ваши данные» — справкой к вопросу
        о данных. Минус ~6 тыс. знаков (~2 тыс. токенов) к каждому вопросу. Выключить — tools.slim: false."""
        try:
            return bool(with_tools) and (self.s.get("tools", "slim") is not False)
        except Exception:  # noqa: BLE001
            return False

    def _privacy_rule(self):
        try:
            import privacy
            return "\n\n" + privacy.rule((self.s.active_llm() or {}).get("base_url", ""), bool(getattr(self, "_sync_on", lambda: False)()))
        except Exception:  # noqa: BLE001
            log.debug("конфиденциальность: подсказка", exc_info=True)
            return ""

    def _personal(self, with_tools=False):
        """Личное — то, что у каждого своё и меняется со временем: имя, память «Обо мне», уроки из поправок, душа,
        содержание долгого разговора, выводы ночи; с действиями — выключенные умения, «Близкие», свои компьютеры, дела
        сегодня, своя папка, система, серверы. Каждый кусок начинается с «\n\n». -> строка (может быть пустой)."""
        base = ""
        name = (self.s.get("user_name") or "").strip()
        if name:
            base += f"\n\nСобеседника зовут {name}."
        mem = self.memory_core()
        if mem:
            base += ("\n\nЧто ты знаешь о пользователе (твоя память, файл «Память/Обо мне.md»; «вспомни, что я говорил…» — "
                     "отвечай отсюда, даже если в заметках и календаре пусто):\n" + mem)
        try:
            import quality as Q
            base += Q.talk_lessons_block(self.workspace.root / Q.TALK_LESSONS_FILE)   # уроки из его поправок
        except Exception:  # noqa: BLE001
            log.debug("уроки: подсказка", exc_info=True)
        try:
            base += self.soul.soul_prompt(self.persona_name())   # душа персонажа (конституция — в общей части)
        except Exception:  # noqa: BLE001
            log.debug("душа: подсказка", exc_info=True)
        base += self.conv.prompt()                     # долгий разговор: что было раньше
        base += self.diary.prompt()                    # выводы, которые ассистент записал ночью в дневник
        r = getattr(self, "insight", None)              # «Радар» настроен — самое интересное за сутки (владелец 14.11)
        if r is not None:
            base += r.prompt_line()
        if with_tools:
            base += self.toolbox.off_note()            # выключенные человеком умения — «выключено», а не «не умею»
            try:
                base += self.close.prompt()            # «Близкие»: кому можно написать (close.py)
            except Exception:  # noqa: BLE001
                log.debug("близкие: подсказка", exc_info=True)
            try:
                comps = self.computers()                # «Устройства» (0.56): свои компьютеры — «сделай на рабочем…»
                if len(comps) > 1:
                    base += ("\n\nТВОИ КОМПЬЮТЕРЫ (ты одна и та же на всех): " + ", ".join(
                        f"«{c['name']}»" + (" — этот" if c["me"] else " — на связи" if c["on"] else " — не на связи") for c in comps)
                        + ". «Сделай/запусти на рабочем (другом) компьютере…» — start_task с on (имя компьютера); не на связи — "
                        "спроси, подождать или сделать в облаке (if_off).")
            except Exception:  # noqa: BLE001
                log.debug("компьютеры: подсказка", exc_info=True)
            try:
                import done as _done
                base += _done.now_line(self.done, skip=self._habit_pred() if hasattr(self, "_habit_pred") else None)   # без привычек
            except Exception:  # noqa: BLE001
                log.debug("дела: подсказка", exc_info=True)
            base += f"\n\nТвоя папка: «{self.workspace.root}». Компьютер пользователя: {OS_NAME}."
            if self.servers.items:
                base += ("\n\nСЕРВЕРЫ пользователя (команды — server_run, по SSH): " + self.servers.names() +
                         ". Сначала диагностика (место, память, службы, логи), потом исправление; объясняй простыми "
                         "словами, что нашёл и что сделал.")
        return base

    def _usage_note(self, prof, sec, turn=None):
        """«Голос без пауз»: сколько токенов в подсказке и сколько сервер взял из кэша начала запроса — в журнал
        («⏱ модель: 6.1 с, подсказка 12 400 ток., из кэша 11 900») и в пульс (health_cache). Сервер не посчитал — молчим.
        turn — ход: токены всех шагов складываются в turn.tok {tin, tout, cached} («Подробности» ответа в «Чате», 0.86)."""
        try:
            from llm import take_usage, usage_line
            uu = take_usage() or {}
            u = {"prompt": uu.get("prompt"), "cached": uu.get("cached")} if uu.get("prompt") else None
            if turn is not None and (uu.get("prompt") or uu.get("out")):
                tok = getattr(turn, "tok", None) or {}
                for k, v in (("tin", uu.get("prompt")), ("tout", uu.get("out")), ("cached", uu.get("cached"))):
                    if isinstance(v, (int, float)) and v:
                        tok[k] = int(tok.get(k) or 0) + int(v)
                turn.tok = tok
            if not u or not u.get("prompt"):
                return
            log.info(usage_line(u, sec))
            if hasattr(self, "health_cache"):
                self.health_cache(u, prof)
        except Exception:  # noqa: BLE001
            log.debug("подсчёт токенов", exc_info=True)

    def _profile_snap(self, fresh, msgs):
        """Личная справка для начала разговора — снимок, неизменный, пока разговор начинается с того же сообщения (0.87,
        кэш подсказки: «⏱ модель: 7.9 с, подсказка 25 087 ток., из кэша 0» на каждый вопрос). Изменилось с тех пор —
        изменения отдельно, в справку к вопросу (profile_delta). Новый разговор, свёртка начала (содержание тоже в справке),
        другой персонаж или изменений слишком много — снимок заново. -> (справка для начала, изменения или "")."""
        import hashlib
        m0 = (msgs or [{}])[0]
        c0 = m0.get("content")
        key = hashlib.sha1((str(self.s.get("persona")) + "\x00" + str(m0.get("role")) + "\x00"
                            + (c0 if isinstance(c0, str) else json.dumps(c0, ensure_ascii=False, sort_keys=True)))
                           .encode("utf-8", "replace")).hexdigest()
        snaps = getattr(self, "_prof_snaps", None)
        rev = getattr(getattr(self, "workspace", None), "mem_rev", 0)
        if snaps is None or getattr(self, "_prof_rev", 0) != rev:
            # «Обо мне» переписали (забыть факт, правка в студии, удаление с телефона) — все снимки прочь (рецензия 0.87)
            snaps = self._prof_snaps = {}              # по снимку на разговор персонажа: Лира ↔ Патрик не сбивают друг другу
            self._prof_rev = rev
        old = snaps.get(key)
        if old is not None and len(msgs or []) > 1:
            d = profile_delta(old, fresh)
            if d is not None:
                return old, d
            log.info("🧊 Личная справка изменилась (убрано или много нового) — обновляю её в начале разговора")
        snaps.pop(key, None)
        while len(snaps) >= 8:
            snaps.pop(next(iter(snaps)))
        snaps[key] = fresh
        return fresh, ""

    def _profile_in_msgs(self, prof):
        """Личное — справкой в начале разговора (а не в подсказке)? Да, кроме Claude (у него кэш идёт «инструменты →
        подсказка», личное в конце подсказки ему не мешает) и если в настройках не вернули по-старому (llm.profile_in_system)."""
        return (prof or {}).get("kind") != "anthropic" and not self.s.get("llm", "profile_in_system")

    def _turn_context(self, text=""):
        """Справка к вопросу (меняется каждую минуту — поэтому не в системной подсказке): дата и время, сколько идёт
        разговор и перерыв. Ближайшая неделя по дням и «считай даты calc» — только если вопрос про даты и сроки (экзамен
        11.10: «в среду», «через сколько дней» не считать в уме). Раньше это шло к каждому вопросу, и ассистенты сами
        заводили речь о днях рождения и подсчёте дней (письмо пользователя 23.10: «навязчивые разговоры про календарь»)."""
        now = datetime.now()
        out = f"Сейчас {WEEKDAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]} {now.year} года, {now:%H:%M}."
        if DATE_ASK_RX.search(text or ""):
            week = "; ".join(f"{WEEKDAYS[(now + timedelta(days=i)).weekday()]} — {(now + timedelta(days=i)).day} {MONTHS[(now + timedelta(days=i)).month - 1]}"
                             for i in range(1, 8))
            out += (f" Ближайшие дни: {week}. Сколько дней до даты и какая дата ближе — считай calc days_until, не в уме.")
            my = month_years(text, now)
            if my:
                out += " " + my
        try:
            note = self.conv.turn_note()
        except Exception:  # noqa: BLE001
            note = ""
        if (self.s.get("llm", "lean_prompt") or self._slim_prompt()) and text:   # описания навыков — к подходящему вопросу
            try:
                hint = self.skills.hint_for(text)
            except Exception:  # noqa: BLE001
                hint = ""
            if hint:
                out += " " + hint
        if self._slim_prompt() and text and PRIVACY_ASK_RX.search(text):     # «где хранятся мои данные?» — факты сюда
            out += self._privacy_rule().replace("\n\n", " ", 1)
        if text and SONGS_ASK_RX.search(text):
            # экзамен 1.0.5 (playlist): «пять песен под настроение» — модель приписала песни не тем исполнителям
            # («Дельфин — „Полковнику никто не пишет“»). Только те, в которых уверена целиком: исполнитель + название
            out += (" Называй только песни, в которых точно уверена — исполнитель и название вместе (сомневаешься — не "
                    "называй или найди web_search); лучше меньше, но настоящие.")
        if text and BIG_PC_RX.search(text):
            # экзамен 1.0.5 (task_folders720): «проанализируй компьютер, папки, диски и предложи структуру» — модель взялась
            # командами по одной (каждая — «Выполнить?») и встала на «жду вашего да». Это работа на много шагов — задачей
            out += (" Это большая работа на много шагов (осмотреть диски и папки, предложить структуру): сразу запусти "
                    "фоновую задачу start_task с этой целью и коротко скажи, что взялась; по одной команде в разговоре не делай.")
        try:
            mine = self.mine_now_line(text)                # идея №169: «что это играет?», «удали эту песню» — Лира знает, что играет
        except Exception:  # noqa: BLE001
            mine = ""
        if mine:
            out += " " + mine
        try:                                           # 0.88: программа на английском — и ответы по-английски
            import i18n
            from lang2 import en_hint as _en_q
            if i18n.resolve(self.s.get("ui", "lang")) == "en" and not _en_q(text):
                out += (" Язык программы у человека — английский: отвечай по-английски (и голосом тоже), если он сам не "
                        "пишет или не говорит на другом языке.")
        except Exception:  # noqa: BLE001
            log.debug("язык программы", exc_info=True)
        try:                                           # №651: «убери вопросы в конце» — к каждому вопросу, важнее характера
            import quality as Q
            sty = Q.style_rules_line(self.workspace.root / Q.TALK_LESSONS_FILE)
        except Exception:  # noqa: BLE001
            sty = ""
        if sty:
            out += " " + sty
        if TALER_RX.search(text or ""):                # №542: «на сколько хватает 1 талер?» — по настоящему счёту
            out += " " + self._taler_now()
        if TASK_ASK_RX.search(text or "") or (TASK_GIVE_RX.search(text or "") and self._task_alive()):
            out += " " + self._tasks_now()            # №390: «задача работает?» — по настоящему состоянию; №551: «дать доступ?»
        from lang2 import en_hint
        en = en_hint(text)                                 # спросили по-английски — ответ по-английски (второй язык)
        if en:
            out += " " + en
        return out + (" " + note if note else "")

    def _plugin_hint(self, text):
        """№461, №463, №483 (ПК 0.76: «плагины не работают — „сейчас посмотрю“ и всё»): просьба к установленному плагину —
        в справку к вопросу: какой навык прочитать и какие действия плагина вызвать сразу (или что они не запустились)."""
        pl = getattr(self, "plugins", None)
        if pl is None or not text:
            return ""
        try:
            m = getattr(self, "mcp", None)
            ask = text.split("\n\nВложения:")[0]
            h = pl.hint_for(ask, m.plugin_tools() if m else {}, m.plugin_errors() if m else {})
            if h:
                return h
            # «Нарисуй открытку» без «Художника» — «Я не умею рисовать» (04.11): предложить включить готовый плагин. Отказался —
            # тот же плагин не предлагаем 6 часов (_offered)
            off = pl.match_off(ask)
            seen = getattr(self, "_plugin_offered", None)
            if seen is None:
                seen = self._plugin_offered = {}
            if off and time.time() - seen.get(off["id"], 0) > 6 * 3600:
                seen[off["id"]] = time.time()
                return pl.offer_hint(off)
            if off:
                # экзамен 1.0.5 (draw_offer_plugin): второй раз за 6 часов — без справки, и модель ушла в расспросы про день
                # рождения. Плагин всё так же выключен — напомнить одной фразой, но кнопку «Выполнить?» не навязывать
                return (f"Это умеет плагин «{off['name']}», но он выключен (включить уже предлагали). Не делай по-своему и не "
                        f"расспрашивай: одной фразой скажи, что это делает «{off['name']}», и спроси, включить ли его "
                        f"(согласятся — plugin_enable с id «{off['id']}»).")
            return ""
        except Exception as e:  # noqa: BLE001
            log.info("подсказка плагина: %s", e)
            return ""

    def _plugin_acts(self, text):
        """№507: (название плагина, [имена его действий]) — плагин, к которому этот вопрос, с подключёнными действиями."""
        pl, m = getattr(self, "plugins", None), getattr(self, "mcp", None)
        if pl is None or m is None or not text:
            return "", []
        try:
            p = pl.match(text.split("\n\nВложения:")[0])
            return (p["name"], [n for n, _ in (m.plugin_tools().get(p["id"]) or [])]) if p else ("", [])
        except Exception:  # noqa: BLE001
            return "", []

    def _plugin_keep(self, text):
        """Имена действий плагина, к которому эта просьба (+ use_skill) — их не выбрасываем, даже когда окно модели мало.
        Просьба о сайте — то же для действий «Сайтов»."""
        from quality import PLUGIN_ASK, PLUGIN_EDIT_ASK, PLUGIN_TOOLS, SITE_ASK, SITE_EDIT_ASK, SITE_TOOLS
        ask0 = (text or "").split("\n\nВложения:")[0]
        if ask0 and (PLUGIN_ASK.search(ask0) or PLUGIN_EDIT_ASK.search(ask0)):
            return set(PLUGIN_TOOLS)                        # «сделай плагин…» (Creator) — до плагинов по словам («нарисуй»)
        if ask0 and (SITE_ASK.search(ask0) or SITE_EDIT_ASK.search(ask0)):
            return set(SITE_TOOLS)
        pl, m = getattr(self, "plugins", None), getattr(self, "mcp", None)
        if pl is None or m is None or not text:
            return set()
        try:
            p = pl.match(text.split("\n\nВложения:")[0])
            if not p and pl.match_off(text.split("\n\nВложения:")[0]):
                return {"plugin_enable"}                   # выключенный готовый плагин — предложить включить
            return ({n for n, _ in (m.plugin_tools().get(p["id"]) or [])} | {"use_skill", "read_skill_file"}) if p else set()
        except Exception:  # noqa: BLE001
            return set()

    def _taler_now(self):
        """Счёт облака Dewiar для ответа о талерах: сколько ответов в одном талере и сколько осталось."""
        try:
            c = self.cloud.status() if getattr(self, "cloud", None) is not None else {}
        except Exception:  # noqa: BLE001
            c = {}
        if not c.get("connected"):
            return ("Талеры — счёт моделей Dewiar; сейчас они не подключены, ответы идут своей моделью — талеры не тратятся. "
                    "Подключить — «Мозг» → «Подключить мозг Dewiar».")
        try:
            per = int(c.get("per_taler") or 0) or (round(float(c.get("turns") or 0) / float(c.get("balance"))) if float(c.get("balance") or 0) > 0 else 0)
        except (TypeError, ValueError, ZeroDivisionError):
            per = 0
        bal = c.get("balance_text") or (f"{c.get('balance')} тал." if c.get("balance") is not None else "")
        return ("Счёт Dewiar (проверено сейчас, говори по этим числам): "
                + (f"1 талер ≈ {per} обычных ответов; " if per else "")
                + (f"на счёте {bal} — примерно на {c.get('turns')} ответов. " if bal else "")
                + "Длинные ответы, размышления, картинки и большие задачи дороже. Где видно: «Мозг» → «ИИ-баланс» "
                  "(на телефоне — «Мозг» → «Баланс»).")

    def _task_alive(self):
        try:
            return any(x.get("status") in ("running", "waiting", "sleeping", "paused") for x in self.tasks.list()[:6])
        except Exception:  # noqa: BLE001
            return False

    def _tasks_now(self):
        """№390 (28.10, Витаха): задача «застряла» через 2 минуты, а Лира на «проверь» отвечала «задача работает» — по
        памяти разговора. К вопросу про задачи — их настоящее состояние: что идёт, что остановилось и почему."""
        try:
            items = self.tasks.list()[:4]
        except Exception:  # noqa: BLE001
            return ""
        if not items:
            return "Фоновых задач сейчас нет (проверено) — не говори, что задача выполняется."
        parts = []
        for x in items:
            st = x.get("status_ru") or x.get("status") or ""
            why = (x.get("error") or x.get("activity") or "") if x.get("status") in ("failed", "stopped", "paused") else (x.get("activity") or "")
            parts.append(f"«{x.get('title', '')}» — {st}" + (f" ({str(why)[:140]})" if why else ""))
        return ("Фоновые задачи сейчас (проверено только что, говори по этому, не по памяти разговора): " + "; ".join(parts)
                + ". Остановилась — так и скажи и предложи перезапустить (start_task заново или resume_task). Пользователь "
                "даёт задаче сведения, ответ, разрешение или папку («дай ей доступ к папке проекта») — передай их tell_task, "
                "а не отвечай словами.")

    def persona_name(self):
        return self.personas.get(self.s.get("persona"))["name"]

    def persona_gender(self):
        return (self.personas.get(self.s.get("persona")) or {}).get("gender", "")

    def memory(self):
        return self.memory_core()

    def memory_core(self, limit=2500):
        """«Обо мне» для подсказки (Память 2.0, memory.core_text): целиком, если влезает, иначе главное — о самом
        человеке, кто есть кто и новое. Не зависит от вопроса — подсказка остаётся прежней (кэш модели)."""
        try:
            import memory as MEM
            return MEM.core_text(self.workspace.memory_get(), limit)
        except Exception:  # noqa: BLE001
            log.debug("память: главное", exc_info=True)
            return self.workspace.memory_text(limit)

    def memory_for(self, question):
        """К вопросу — факты, что не вошли в главное, по смыслу вопроса (memory.relevant). -> (строки, страницы)."""
        try:
            import memory as MEM
            lines, pages = MEM.relevant(question, self.workspace.memory_get())
        except Exception:  # noqa: BLE001
            log.debug("память: к вопросу", exc_info=True)
            return "", []
        self._mem_last = {"pages": pages, "ts": time.time()}
        return lines, pages

    def skills_prompt(self):
        return self.skills.prompt()

    def _fresh_note(self, minutes=30):
        """Заметка, записанная последние minutes минут -> «Заметка: начало текста» для названия напоминания или ""."""
        try:
            n = (self.workspace.notes(limit=1) or [None])[0]
        except Exception:  # noqa: BLE001
            return ""
        if not n or time.time() - float(n.get("mtime") or 0) > minutes * 60:
            return ""
        body = re.sub(r"\s+", " ", str(n.get("snippet") or n.get("title") or "")).strip()
        if len(body) > 90:
            body = body[:90].rsplit(" ", 1)[0] + "…"
        return "Заметка: " + body if body else ""

    def _reminder_times(self):
        """Времена «ЧЧ:ММ» стоящих напоминаний и дел на ближайшие сутки (для quality.remind_claim: «в 21:00 напомню про итог
        дня» — правда, если дело уже стоит). Сбой — пусто: проверка работает как раньше."""
        try:
            from datetime import datetime as _d
            now = time.time()
            out = set()
            for x in list(getattr(self, "reminders", None).items or []):
                if x.get("paused"):
                    continue
                at = _d.fromisoformat(x["at"])
                if now - 60 <= at.timestamp() <= now + 24 * 3600:
                    out.add(at.strftime("%H:%M"))
            return out
        except Exception:  # noqa: BLE001
            return set()
