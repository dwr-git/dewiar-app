"""Движок Dewiar — ответ: ask() (быстрые пути без модели, передача специалисту), ход разговора с моделью
(_run_turn: поток событий модели → фразы → озвучка, вызовы инструментов, запасные пути при ошибках), история
и системная подсказка, «Проверить всё», отчёты разработчику, связь с фоновыми задачами (TaskManager.host).
Часть класса Engine (core/engine.py): методы смешиваются в него, self — это Engine.
Озвучка фраз — _speak_worker (engine_remote.py), инструменты — _use_tool (engine_tools.py).
Текст с «\\n\\nВложения:» — вопрос с файлами (см. _attach_files): быстрые пути его не перехватывают."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка

# инструменты «узнать» (не «сделать»): после них ответ без слов — не ответ, «Готово.» вместо сути не подставляем
# вопрос про даты и сроки — тогда к нему справка «ближайшие дни» и «считай calc» (_turn_context)
DATE_ASK_RX = re.compile(r"дн(я|ей|и|ём)\b|недел|понедельник|вторник|сред[уыа]|четверг|пятниц|суббот|воскресен|завтра|послезавтра|"
                         r"числ[оа]|дат[аыуе]|когда|сколько.{0,20}(дн|недел|месяц|осталось)|через\s+\d|рождени|праздник|"
                         r"январ|феврал|март|апрел|ма[йя]\b|июн|июл|август|сентябр|октябр|ноябр|декабр|\d{1,2}[./]\d{1,2}", re.I)
# №390: вопрос про фоновые задачи («задача работает?», «почему не запущена», «что с заданием») — к нему их настоящее состояние
TASK_ASK_RX = re.compile(r"задач|задани|фонов|застрял|выполня(?:ется|ешь|ет)|запущ|работает ли|что с (?:ней|ним)", re.I)
INFO_TOOLS = {"web_search", "weather", "read_webpage", "find_notes", "read_file", "calc", "list_reminders", "calendar_list", "money_report",
              "read_emails", "read_email", "search_documents", "ask_knowledge", "system_status", "task_status", "look_at_screen",
              "look_through_camera", "app_update"}



def team_window(hist, me, name_of):
    """Реплики для модели персонажа me: у каждого персонажа свой разговор (письмо пользователя 23.10: «при переключении
    они нередко продолжали чужую тему — хочется, чтобы мой персонаж помнил разговор со мной, Лира — с Лирой; передавать
    беседу другому — по моей просьбе»). Разговор пользователя с другим персонажем в окно не попадает вовсе. Исключение —
    передали слово явно («позови Патрика», инструмент call_persona): ответ коллеги помечен handoff=me, тогда его разговор —
    одной справкой «для справки, не продолжай их тему». Реплика человека относится к тому, кто на неё ответил; последняя
    (без ответа) — к me. Общее (память о человеке, заметки, календарь) — в подсказке, у всех. -> [{role, content[, team]}]"""
    msgs = [m for m in hist if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]
    owner, nxt = [None] * len(msgs), me
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i]["role"] == "assistant":
            nxt = msgs[i].get("who") or me
        owner[i] = nxt
    from engine_base import FACT_TURNS
    with_facts = [k for k, m in enumerate(msgs) if m["role"] == "assistant" and m.get("facts") and owner[k] == me][-FACT_TURNS:]
    out, i = [], 0
    while i < len(msgs):
        if owner[i] == me:
            c = msgs[i]["content"]
            if msgs[i]["role"] == "assistant" and msgs[i].get("acts"):
                # что было сделано за этим ответом (съёмка 17.10: в истории оставались одни слова «Звоню», «Включаю»,
                # «Отправила» — и модель решала, что достаточно сказать их ещё раз, не вызывая действие)
                c += "\n[в этом ответе выполнено инструментами: " + ", ".join(msgs[i]["acts"]) + "]"
            if i in with_facts:
                # и что они узнали — коротко («забывает IP»: на уточнение искала заново или выдумывала); последние ответы
                c += "\n[узнано инструментами — опирайся на это, не ищи заново: " + "; ".join(msgs[i]["facts"]) + "]"
            out.append({"role": msgs[i]["role"], "content": c})
            i += 1
            continue
        j, who = i, owner[i]
        while j < len(msgs) and owner[j] == who:
            j += 1
        last = next((m for m in reversed(msgs[i:j]) if m["role"] == "assistant"), {})
        if last.get("handoff") == me:                  # коллега сам передал слово — его разговор справкой
            name = name_of(who)
            lines = [("Пользователь: " if m["role"] == "user" else f"{name}: ") + " ".join(m["content"].split())[:400] for m in msgs[i:j]][-8:]
            out.append({"role": "user", "team": True,
                        "content": f"[До этого пользователь говорил не с тобой, а с коллегой по имени {name} — и {name} передал(а) "
                                   "слово тебе. Это для справки: не отвечай за коллегу, продолжай то, о чём тебя просят.]\n" + "\n".join(lines)})
        i = j
    return out

ATT_DEFAULT_Q = "Посмотри вложения и коротко скажи, что в них."
ACTS_RX = re.compile(r"\s*\[(?:в этом ответе выполнено|узнано инструментами)[^\]]*\]?")       # пометка в истории (team_window) — не для человека


def _norm_answer(t):
    """Ответ без регистра, знаков и пробелов — сравнить с прошлыми («Я Лира.» == «я лира»)."""
    return re.sub(r"[\W_]+", " ", str(t or "").lower()).strip()


def _thumb(data, side=320):
    """Миниатюра картинки для ленты «Чата» (data:URL, JPEG ~10–25 КБ) или "" — если не картинка."""
    try:
        import base64
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        im.thumbnail((side, side))
        out = io.BytesIO()
        im.convert("RGB").save(out, "JPEG", quality=72)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()
    except Exception:  # noqa: BLE001
        return ""


# «об этом», «о ней», «о последней заметке», «это» — напоминание о сказанном раньше, а не текст напоминания
# «запиши на послезавтра в 12 к Юле на массаж», «запиши меня на завтра в 15 к стоматологу» — дело со временем, а не заметка
# (экзамен 25.10: «Записал: «На послезавтра в 12 к Юле на…»» — записалось заметкой, в «Делах» пусто)
APPT_RX = re.compile(r"^(?:[\w-]+,\s*)?(?:запиши|запишите|записать|занеси|внеси|поставь|добавь)\s+(?:мне\s+|меня\s+)?"
                     r"(?:в\s+(?:дела|планы|список\s+дел)\s+)?(?P<rest>(?:на\s+)?(?:сегодня|завтра|послезавтра|понедельник|вторник|сред[уа]|четверг|"
                     r"пятниц[уа]|суббот[уа]|воскресенье|\d{1,2}(?:\s+[а-я]+|\.\d{1,2}))\b.*)$", re.I)
APPT_TIME_RX = re.compile(r"\bв\s+\d{1,2}(?:[:.]\d\d)?\b|\b\d{1,2}:\d\d\b|\bутр|\bвечер|\bдн[её]м\b|\bв\s+обед", re.I)
REF_RX = re.compile(r"^\s*(?:об?\s+)?(?:этом|это|этой|этого|ней|нем|нём|том|последн\w*\s+заметк\w*|заметк\w*|сказанном)\s*[.!]?\s*$", re.I)


# «напомни завтра про это / про них / про эти скрины» с картинками — название напоминания придумаем сами
ATT_REF_RX = re.compile(r"^\s*(?:про|насч[её]т|о|об)\s+(?:это|этом|них|неё|нее|него|эт\w+(?:\s+(?:скрин\w*|картинк\w*|снимк\w*|фот\w*))?|"
                        r"скрин\w*|картинк\w*|снимк\w*)\s*[.!]?\s*$", re.I)
# вложения вопроса в тексте для модели (_attach_files): «… сохранена: Входящие/…]» / «… сохранён в папке ассистента: …]»
ATT_PATH_RX = re.compile(r"сохран[её]на?(?: в папке ассистента)?:\s*(Входящие/[^\]\n;]+?)\s*(?=\]|;)")



def _put_context(msgs, ctx):
    """Справку к вопросу (время, найденное в записях, план дня, знания персонажа) — в начало последнего сообщения
    пользователя, а не в системную подсказку: подсказка и описание инструментов остаются теми же от вопроса к вопросу,
    и свой сервер модели (llama.cpp, LM Studio, Ollama) берёт их из кэша, а не перечитывает (отзыв 19.10).
    В историю разговора справка не попадает — меняется только копия сообщений для этого запроса."""
    if not ctx or not msgs or msgs[-1].get("role") != "user":
        return msgs
    head = "(Справка к этому сообщению — для тебя, вслух её не упоминай)\n" + ctx + "\n\n(Сообщение пользователя)\n"
    c = msgs[-1].get("content")
    if isinstance(c, list):
        c = [dict(x) for x in c]
        i = next((i for i, x in enumerate(c) if x.get("type") == "text"), None)
        if i is None:
            c.insert(0, {"type": "text", "text": head.rstrip()})
        else:
            c[i]["text"] = head + str(c[i].get("text") or "")
    else:
        c = head + str(c or "")
    return msgs[:-1] + [dict(msgs[-1], content=c)]


# идеи пользователей 24.10: «перевод текста с фото или скриншота», «пришла повестка — что делать?» (по фото документа),
# «подсчёт калорий по фото еды». Справка к вопросу с картинкой — как отвечать на такие просьбы (сама просьба — у человека)
VISION_HINT = ("К сообщению приложено фото. Если просят перевести — переведи весь текст на фото дословно и естественно "
               "(на русский, если язык не назван), сохрани строки и порядок; ничего не додумывай там, где не видно. "
               "Если на фото документ, письмо или повестка и спрашивают, что это или что делать, — простыми словами: что это "
               "за документ и от кого, главное (даты, сроки, суммы, адрес, куда и с чем прийти), что сделать по шагам; "
               "если дело серьёзное (суд, долги, штраф, полиция, военкомат) — посоветуй уточнить у юриста; не пугай и не "
               "выдумывай того, чего на фото нет. Если спрашивают про калории еды — назови, что видишь на тарелке, и "
               "примерную калорийность диапазоном (например, «примерно 450–600 ккал»), одной-двумя фразами, без советов есть "
               "меньше и без оценок; записать — только если человек сам попросил.")

REPEAT_RX = re.compile(r"^\W*(?:\w+,\s*)?(?:ну\s+)?(?:а\s+)?(?:теперь|сейчас|ещё\s+раз|еще\s+раз|снова|опять|повтори|попробуй\s+(?:ещё|еще)\s+раз|"
                       r"проверь\s+(?:ещё|еще)\s+раз|(?:а\s+)?теперь\s+(?:как|что)|ну\s+что|и\s+как\s+теперь)\W*$", re.I)

# «урок дня», «давай урок», «следующий урок» — курс «Неделя с Лирой» без модели (core/course.py)
# Урок 12 «Утро с Лирой» обещает: «Скажите „Расскажи утро“» (30.10: голосом это уходило модели как обычный вопрос —
# без данных «Утра», и она могла сочинить). Теперь — та же сводка, что кнопка «Расскажи утро» на «Главной» (_job_prompt brief).
MORNING_RX = re.compile(r"^\W*(?:\w+[,!]\s*)?(?:ну\s+|а\s+)?(?:расскажи|давай|скажи|сделай|дай|прочитай|озвучь)\s+(?:мне\s+|нам\s+)?(?:(?:моё|мое|своё|свое)\s+)?"
                        r"(?:утро|утреннюю\s+сводку|сводку\s+(?:на\s+)?(?:дня|день|утро|сегодня)|сводку)\W*$", re.I)
COURSE_RX = re.compile(r"^(?:лира[, ]+)?(?:давай |начн[её]м |покажи |какой |открой )?(?:урок(?: дня| курса)?|следующий урок|курс(?: неделя с лирой)?)$")

IDEA_RULE = ("\n\nЧего-то не умеешь и инструмента для этого нет — честно скажи и предложи одной фразой: «Хотите, предложу это "
             "разработчику как идею?». Согласятся или сами скажут «предложи идею: …» — suggest_idea (там же найдётся похожая: тогда "
             "голос за неё). Без согласия не вызывай.")


# Главные действия на каждый день — для модели с окном поменьше (_fit_window): весь набор — около 13 тысяч токенов
CORE_TOOLS = {"web_search", "weather", "open_url", "open_app", "play_music", "play_radio", "media_control", "set_volume",
              "set_reminder", "list_reminders", "cancel_reminder", "change_reminder", "calc", "world_time", "mark_done", "save_note", "find_notes",
              "remember", "money_add", "money_report", "calendar_list", "smart_home", "read_emails", "send_email",
              "search_documents"}


class AnswerMixin:
    # ---------- ответ ----------

    def _slow_local(self, prof, sec):
        """Своя модель на этом компьютере думает больше минуты до первого слова (отчёты №121–124, 19.10: llama3 8B на
        4 ядрах без видеокарты — «думает по 600 секунд»): один раз за запуск сказать, что делать, а не молча ждать."""
        url = str(prof.get("base_url") or "")
        if sec < 60 or getattr(self, "_slow_said", False) or not re.search(r"//(127\.0\.0\.1|localhost|\[::1\])[:/]", url):
            return
        self._slow_said = True
        log.warning("Своя модель %s отвечает медленно: первые слова через %.0f с", prof.get("model") or url, sec)
        self.note(f"Модель на этом компьютере начала отвечать только через {round(sec)} с — ей не хватает мощности (нужна "
                  "видеокарта или модель полегче). Возьмите лёгкую (в Ollama: qwen3:1.7b или qwen2.5:3b) или подключите облако "
                  "Dewiar — студия → «Мозг».")

    CODER_RX = re.compile(r"coder|codellama|codegemma|starcoder|codestral|devstral|sqlcoder|code-?llama|wizardcoder", re.I)

    def _coder_brain(self, prof):
        """№370 (28.10): «мозг» — модель для программирования (qwen2.5-coder:7b): по-русски отвечает плохо, сбивается на
        английский и печатает JSON вместо ответа. Один раз за запуск сказать, какую взять для разговора."""
        name = str((prof or {}).get("model") or "")
        if getattr(self, "_coder_said", False) or not self.CODER_RX.search(name):
            return False
        try:
            if self.s.get("persona") == "agent":           # Кодер со своей моделью для кода — так и задумано
                return False
        except Exception:  # noqa: BLE001
            pass
        self._coder_said = True
        log.warning("Мозг — модель для кода (%s): для разговора не годится", name)
        self.note(f"Сейчас «мозг» — модель для программирования ({name}): по-русски она говорит плохо и сбивается на английский. "
                  "Для разговора возьмите обычную — в Ollama qwen2.5:7b или qwen3:8b — или облако Dewiar: студия → «Мозг». "
                  "Модель для кода пригодится Кодеру.")
        return True

    def ask(self, text, images=None, quiet=False, via=None, raw=False, shown=None, report=None):
        """Вопрос → ответ. Сначала быстрые пути без модели (будильник, «спрячься»/«отключись», команды компьютера, сейф, умный дом, деньги,
        дела, заметки, напоминания, «замолчи», новый разговор, позвать персонажа, радио, музыка), затем, возможно,
        передача специалисту (_route) и ход разговора в потоке turn-N; прежний ход отменяется.
        images — картинки; quiet — служебный вопрос: не показываем «услышал», без быстрых путей; via — вопрос
        не голосом (Telegram/MAX, см. Turn.via); raw — без быстрых путей и передачи специалисту (дела по расписанию);
        shown — что показать вместо текста; report(ok, text) — чем кончился ход (дела по расписанию: повтор при сбое)."""
        text = text.strip()
        if not text and images:
            text = "Что на этой картинке?"
        if not text:
            return
        if via:
            quiet = False
        if not quiet and not raw and hasattr(type(self), "first_asked"):
            type(self).first_asked(self)                   # первый вопрос новичка — подсказки в виджете больше не нужны
        # 24.10 (владелец: «попросил обновиться — нет; „а теперь“ — она что-то не связанное»): короткое «а теперь?»,
        # «ещё раз», «проверь ещё раз» сразу после быстрой команды без модели — та же команда ещё раз
        lq = getattr(self, "_last_quick", None)
        if not raw and not quiet and not images and lq and time.monotonic() - lq[1] < 600 and REPEAT_RX.match(text):
            log.info("🔁 «%s» — повторяю «%s»", text, lq[0])
            text = lq[0]
        if not raw and not quiet and not images and self.alarm and not via and self._alarm_voice(text):
            return
        # Детский режим (kids.py): время и «спать» — до всего; вопрос — в отчёт родителю; вне правил — ещё и сигнал.
        # K — режим включён: опасные быстрые пути (компьютер, сейф, деньги, платежи, дом, звонки, YouTube, выход,
        # обновление, передача другому персонажу) не работают — отвечает модель по детским правилам.
        kids = getattr(self, "kids", None)
        K = bool(kids and kids.on() and not raw and not quiet)
        if K:
            ok_k, why_k = kids.allowed_now()
            if not ok_k:
                self._say_quick(why_k, text, via)
                return
            if kids.touch(text.split("\n\nВложения:")[0]):
                self._kids_alert(text)
            self.emit("kids", **self.kids_public(light=True))   # виджет: сколько минут осталось
        sen = getattr(self, "senior", None)              # «Для старших» (senior.py): говорила сегодня; мошенники — сразу «стоп»
        if sen is not None and not K and not raw and not quiet and sen.on():
            body_s = text.split("\n\nВложения:")[0]
            sen.touch()
            if not images and sen.scam(body_s):
                self._senior_scam(body_s, text, via)
                return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and self._bug_cmd(text, via):
            return                                       # «сообщи об ошибке: …» — жалоба разработчику (core/health.py)
        if not raw and not quiet and not via and not images and not K and re.match(
                r"^(?:\w+,\s*)?(?:включи|запусти|открой|начни|позови)\s+(?:режим\s+)?суфл[её]р\w*|^(?:\w+,\s*)?режим\s+суфл[её]ра", text.strip(), re.I):
            self.emit("prompter", kind="open")             # суфлёр — окно ui/prompter.html (core/prompter.py)
            self._say_quick("Открываю суфлёр. На встрече я молчу и подсказываю на экране.", text)
            return
        if not raw and not quiet and not via and not images and self._game_voice(text):
            return                                       # «Морской бой» открыт: «бэ пять» — ход в игре (engine_commands)
        if not raw and not quiet and not via and not images and not K and self._window_cmd(text):
            return
        if not raw and not quiet and not images and not K and getattr(self, "course", None) is not None:
            try:                                         # курс «Неделя с Лирой»: сказали фразу урока — шаг засчитан
                self.course.heard(text)
            except Exception:  # noqa: BLE001
                log.debug("курс", exc_info=True)
            if not via and COURSE_RX.match(text.lower().strip(" .!?")) and self._course_say(text):
                return
        if not raw and not quiet and not via and not images and not K and self._pc_cmd(text):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._vault_cmd(text, via):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._home_cmd(text, via):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and self._weather_cmd(text, via):
            return                                       # «какая погода?» — настоящие числа сразу (weatherq.py, №373)
        if not raw and not quiet and not images and not K and MORNING_RX.match(text) and hasattr(self, "_job_prompt"):
            log.info("🌅 «%s» — утренняя сводка по данным «Утра»", text)
            self.ask(self._job_prompt({"brief": True}), via=via, raw=True, shown=text)
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._pay_voice(text, via):
            return                                       # «оплатил газ 47,84, показания 28135», «что не оплачено?» — «Платежи»
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._money_cmd(text, via):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._job_cmd(text, via):
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text:
            from quickmath import parse as parse_math      # «сколько будет 17% от 2350» — точно и сразу (tools.calc_eval)
            qm = parse_math(text)
            if qm:
                self._say_quick(qm["say"], text, via, note=qm.get("how"))
                return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._draft_cmd(text, via):
            return                                       # «запиши в книгу: …» — дословно в черновик автора
        if not raw and not quiet and not images and "\n\nВложения:" not in text:
            ma = APPT_RX.match(text.strip())
            if ma and APPT_TIME_RX.search(ma.group("rest")):
                from when import parse as parse_when
                r = parse_when("напомни " + ma.group("rest"))
                if r and r.get("text") and not r.get("repeat"):
                    r["said"] = text
                    self._set_reminder_fast(r, via)        # дело в «Делах» со временем (как «напомни …»)
                    return
        if not raw and not quiet and not images and "\n\nВложения:" not in text:
            from capture import parse as parse_capture
            c = parse_capture(text)
            if c and self._capture(c, text, via):
                return
        if not raw and not quiet and not images and "\n\nВложения:" not in text and self._clock_cmd(text, via):
            return                                       # «сколько времени?», «какое сегодня число?» — по часам, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._youtube_cmd(text, via):
            return                                       # «включи смешное видео на YouTube» — сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._send_cmd(text, via):
            return                                       # «напиши Андрею: привет» — человеку из «Близких» сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._call_cmd(text, via):
            return                                       # «позвони Людмиле по видео» — человеку из «Близких» сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._plan_cmd(text, via):
            return                                       # «запланируй на сегодня: в 13 …, в 16 …» — дела дня, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._task_del_cmd(text, via):
            return                                       # «удали задачу „Исследование“» — сразу, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and not K and self._mark_cmd(text, via):
            return                                       # «я позвонил в банк», «готово, купил хлеб» — отметка, без модели
        if not raw and not quiet and not images and "\n\nВложения:" not in text and self._timer_cmd(text, via):
            return                                       # «сколько осталось?», «добавь минуту», «отмени таймер»
        if not raw and not quiet and not images:
            from when import parse as parse_when
            r = parse_when(text)
            if r and REF_RX.match(r.get("text") or ""):
                # «напомни об этом / о ней / о последней заметке завтра в 10» (отчёт №66: вышло напоминание «Об этом»):
                # только что записанная заметка — она; иначе — модели, она видит разговор
                note = self._fresh_note()
                r = dict(r, text=note) if note else None
            if r:
                r["said"] = text
                self._set_reminder_fast(r, via)
                return
        if not raw and not quiet and not via and not images and thanks_phrase(text):
            self._thanks(text)
            return
        if not raw and not quiet and not via and not images and is_sleep_phrase(text):
            self.emit("heard", text=text)
            self.go_sleep(text)
            return
        if not raw and not quiet and not images and "\n\nВложения:" not in text:
            from conversation import is_new_conversation
            if is_new_conversation(text):
                self.new_conversation()
                self._say_quick("Хорошо, начинаем с чистого листа.", text, via)
                return
        if not raw and not quiet and not via and not images and not K and self._direct_call(text):
            return
        if not raw and not quiet and not images and not K and self._direct_update(text, via):
            return
        if not raw and not quiet and not via and not images and self.radio.paused and \
                re.sub(r"[^\w ]", "", text.lower()).strip() in {"продолжи", "продолжай", "включи обратно", "верни радио",
                                                                "включи радио", "играй", "продолжи радио"}:
            st = self.radio.resume()
            self.emit("heard", text=text)
            self.emit("answer", text=f"Снова играет «{st['name']}».", done=True)
            self.set_state("idle")
            return
        if not raw and not quiet and not via and not images and (not K or "music" in (kids.conf().get("allow") or [])) and self._music_cmd(text):
            return
        with self._turn_lock:
            self._cancel_locked()      # прежний ход — до выбора специалиста: перебитый специалист возвращает слово главному, и вопрос распределяет уже он
        handoff = None if quiet or images or raw or K else self._route(text)
        if handoff:
            prev = self.s.get("persona")
            log.info("👥 %s передаёт вопрос: %s", self.personas.get(prev)["name"], self.personas.get(handoff)["name"])
            self.switch_persona(handoff)
        log.info("❓ %s", redact(text))
        if not quiet and not (via or {}).get("job"):   # дело по расписанию — показываем, только когда есть что сказать
            self.emit("heard", text=shown or (("✉ " + text.split("\n\nВложения:")[0]) if via else text))
        if handoff:
            self.emit("handoff", **{"from": prev, "to": handoff, "name": self.personas.get(handoff)["name"],
                                    "role": self.personas.get(handoff).get("role", "")})
        with self._turn_lock:
            self._cancel_locked()
            self.turn_n += 1
            turn = Turn(self.turn_n)
            turn.via = via
            turn.via_job = bool((via or {}).get("job"))  # дело по расписанию: в окна — только итог (_run_job решает, говорить ли)
            turn.asked = text                         # о чём просили (save_note без просьбы записать — не пишем)
            turn.report = report
            turn.back_to = prev if handoff and self.s.get("team", "back") is not False else None
            turn.persona = self.s.get("persona")      # кто отвечает; по нему _cancel_locked решает, возвращать ли слово главному
            self.turn = turn
        threading.Thread(target=self._run_turn, args=(turn, text, images or []), name=f"turn-{turn.n}", daemon=True).start()

    def _messages(self, text, images=(), prof=None):
        """История (последние history_turns реплик) + вопрос -> сообщения для модели. Соседние сообщения user
        склеиваются в одно: многие шаблоны чата требуют чередования ролей."""
        if self.conv.expired(float(self.s.get("llm", "history_reset_seconds") or 28800)):
            self.history = []                          # долгая тишина — новый разговор
            self.conv.reset()
        turns = int(self.s.get("llm", "history_turns") or 0)
        me = self.s.get("persona")
        out = []
        # своё окно у каждого персонажа: сначала его разговор из общей истории, потом окно (раньше окно резалось по общей
        # истории, и после долгого разговора с Патриком Лира не помнила свой)
        mine = team_window(self.history, me, lambda pid: (self.personas.get(pid) or {}).get("name") or "коллега")
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

    def new_conversation(self):
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

    def _fit_window(self, prof, system, specs, msgs):
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
            core = [x for x in specs if (x.get("name") or (x.get("function") or {}).get("name")) in CORE_TOOLS]
            sys_lean = self._system(True, lean=True)
            if core and need(sys_lean, core, msgs) <= win:
                system, specs = sys_lean, core
                steps.append("главные действия")
        if specs and need(system, specs, msgs) > win:
            specs = []
            system = self._system(False) + ("\n\nСейчас действия (музыка, скриншоты, программы) недоступны: у модели "
                                            "маленькое окно контекста. Если просят действие — честно скажи это одной фразой.")
            steps.append("без действий")
        if need(system, specs, msgs) > win:
            system = self._system_min()
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

    def _system(self, with_tools=False, lean=None):
        """Системная подсказка: персонаж, память о пользователе, душа, содержание разговора, выводы из дневника;
        with_tools — ещё навыки и правила действий (инструменты, музыка, компьютер, серверы).
        Она не меняется от вопроса к вопросу: время, найденное в записях, план дня — в справке к самому вопросу
        (_turn_context, _put_context). Отзыв 19.10: время с минутами в подсказке не давало своему серверу модели
        переиспользовать прочитанное (кэш начала запроса) — он перечитывал тысячи слов на каждый вопрос."""
        base = self.personas.system_prompt(self.s.get("persona"), self.s.get("user_name") or "", "")
        base += ("\n\nТекущие дата и время — в справке в начале последнего сообщения пользователя; они верные, а время и даты "
                 "из прошлых реплик разговора устарели — не повторяй их.")
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
            base += self.soul.prompt(self.persona_name())   # конституция и душа персонажа
        except Exception:  # noqa: BLE001
            log.debug("душа: подсказка", exc_info=True)
        base += self.conv.prompt()                     # долгий разговор: что было раньше, был ли перерыв
        base += self.diary.prompt()                    # выводы, которые ассистент записал ночью в дневник
        from boundaries import RULE, OWN_MATERIAL
        base += "\n\n" + RULE + "\n\n" + OWN_MATERIAL
        kids = getattr(self, "kids", None)
        if kids and kids.on():
            base += kids.prompt()                      # детский режим: правила разговора с ребёнком (kids.py)
        elif getattr(self, "senior", None) is not None and self.senior.on():
            base += self.senior.prompt()               # «Для старших»: просто, тепло, неторопливо; осторожно с деньгами                          # границы: достоинство без обидчивости (boundaries.py)
        try:                                           # «Ваши данные»: что хранится и куда уходит (privacy.py)
            import privacy
            base += "\n\n" + privacy.rule((self.s.active_llm() or {}).get("base_url", ""),
                                           bool(getattr(self, "_sync_on", lambda: False)()))
        except Exception:  # noqa: BLE001
            log.debug("конфиденциальность: подсказка", exc_info=True)
        # сами фразы ловит _window_cmd без модели; это — чтобы ассистент мог подсказать их, если спросят
        base += ("\n\nЕсли спросят, как тебя спрятать или выключить: «спрячься» — виджет уходит в трей, а ты слушаешь и "
                 "появляешься на имя; «покажись» — вернуть виджет; «отключись» — выйти из Dewiar совсем (включить снова — "
                 "Dewiar в меню приложений).")
        if with_tools:
            lean = self.s.get("llm", "lean_prompt") if lean is None else lean
            base += self.skills.prompt_lean() if lean else self.skills.prompt()
            base += self.toolbox.off_note()            # выключенные человеком умения — «выключено», а не «не умею»
            base += IDEA_RULE                          # «Идеи Лиры» (0.61): чего не умеешь — предложить разработчику
            try:
                import done as _done
                base += _done.prompt(self.done)        # «Дела»: отметить сделанное, сколько сегодня (done.py)
            except Exception:  # noqa: BLE001
                log.debug("дела: подсказка", exc_info=True)
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
                     f"\n\nУ тебя есть своя папка «{self.workspace.root}» — пользователь видит её в студии. Просят записать, "
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
                       "конкретные песни (исполнитель — название), сколько просили: только известные песни, в которых ты уверен — "
                       "и в названии, и в исполнителе (не придумывай и не приписывай песню чужому исполнителю); включай, "
                       "только если просят включить. "
                       "Никогда не говори, что что-то открыл или включил, если инструмент этого не сделал.")
            base += f"\n\nКомпьютер пользователя: {OS_NAME}."
            base += (" Просят разобраться с компьютером (тормозит, не работает, настроить) — сначала посмотри "
                     "командами, которые ничего не меняют (run_command), объясни, что нашёл, и предложи исправление; "
                     "каждую команду пользователь подтверждает."
                     # OS_NAME на Windows — «Windows 10»/«Windows 11», поэтому систему узнаём по os.name, не по строке
                     + (" Нужны права администратора — пиши sudo как обычно: Dewiar сам покажет окно для пароля. Никогда "
                        "не проси пароль в разговоре и не вставляй его в команды (echo … | sudo -S)." if os.name != "nt" else ""))
            if self.servers.items:
                base += ("\n\nСЕРВЕРЫ пользователя (команды — server_run, по SSH): " + self.servers.names() +
                         ". Сначала диагностика (место, память, службы, логи), потом исправление; объясняй простыми "
                         "словами, что нашёл и что сделал.")
        return base

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
        try:
            note = self.conv.turn_note()
        except Exception:  # noqa: BLE001
            note = ""
        if self.s.get("llm", "lean_prompt") and text:      # короткая инструкция: описания навыков — к подходящему вопросу
            try:
                hint = self.skills.hint_for(text)
            except Exception:  # noqa: BLE001
                hint = ""
            if hint:
                out += " " + hint
        if TASK_ASK_RX.search(text or ""):              # №390: «задача работает?» — ответ по настоящему состоянию, не по памяти
            out += " " + self._tasks_now()
        from lang2 import en_hint
        en = en_hint(text)                                 # спросили по-английски — ответ по-английски (второй язык)
        if en:
            out += " " + en
        return out + (" " + note if note else "")

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
                + ". Остановилась — так и скажи и предложи перезапустить (start_task заново или resume_task).")

    # ---------- для фоновых задач (TaskManager.host) ----------

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

    def persona_llm(self, pid=None):
        """Модель, которой думает персонаж: своя (llm.persona = {pid: id профиля} — студия → «Персонажи» → «Мозг»),
        иначе общая (llm.active). Пакет 27.10, №346 и отзывы с YouTube: «разным персонажам — разных ИИ: один на GPT,
        второй на Gemini, третий на Claude» — раньше мозг был один на всех и его надо было переключать вручную."""
        pid = pid or self.s.get("persona")
        own = ((self.s.get("llm", "persona") or {}).get(pid) or "") if pid else ""
        profs = self.s.get("llm", "profiles") or {}
        if own and own in profs:
            # №403 (29.10): у одного сервера (Ollama) много моделей — персонажу своя модель того же профиля
            # (llm.persona_model[id]); раньше выбор модели менял профиль у всех, «слетало к последнему»
            m = ((self.s.get("llm", "persona_model") or {}).get(pid) or "").strip()
            return dict(profs[own], model=m) if m and not profs[own].get("cloud") else dict(profs[own])
        return self.s.active_llm()

    def _contact_maybe(self):
        """Автоподключение (0.69): после пяти удачных ответов — один раз (и ещё раз через три дня, если отложили) попросить
        контакт: «если что-то сломается — разработчик сможет ответить». Только по желанию; оставили — больше не спрашиваем."""
        c = self.s.get("cloud") or {}
        if not c.get("auto") or c.get("contact_done") or not c.get("key"):
            return
        n = int(c.get("auto_turns") or 0) + 1
        upd = {"auto_turns": n}
        asks = int(c.get("contact_asks") or 0)
        if n >= 5 and asks < 2 and time.time() - float(c.get("contact_asked") or 0) > 3 * 86400:
            upd.update(contact_asked=time.time(), contact_asks=asks + 1)
            self.s.update({"cloud": upd})
            threading.Timer(6, lambda: self.emit("contact_ask")).start()     # после ответа, не поверх него
            return
        self.s.update({"cloud": upd})

    def _trial_llm(self):
        """Пробный разговор сайта (cloud.php ?p=/trial/chat/completions) — мозг на первые минуты, пока свой не подключён:
        без ключа и настройки, без действий (напоминания, поиск — после «Подключить бесплатно»), с пределами сайта (12 ответов
        в час с адреса). Выключатель — llm.trial: false. При вводе из wav (проверки) — только с DEWIAR_TRIAL. -> профиль или None."""
        if self.s.get("llm", "trial") is False or (self.wav_input and not os.environ.get("DEWIAR_TRIAL")):
            return None
        import cloud as C
        url = self.s.get("cloud", "url") or C.DEFAULT_URL
        if not getattr(self, "_trial_said", False):
            self._trial_said = True
            log.info("🧠 Мозг не подключён — отвечаю пробным разговором Dewiar (без действий)")
            self.emit("trial", on=True)
        self.health_use("trial")
        return {"name": "Пробный разговор Dewiar", "kind": "openai", "base_url": C.api_base(url) + "/trial", "api_key": "",
                "model": "trial", "trial": True, "max_tokens": 450}

    def llm_profile(self):
        """Модель для фоновых задач: своя из настроек задач, иначе активная."""
        pid = self.s.get("tasks", "llm") or ""
        profs = self.s.get("llm", "profiles") or {}
        return dict(profs[pid], id=pid) if pid in profs else self.s.active_llm()

    def max_steps(self):
        return int(self.s.get("tasks", "max_steps") or 80)

    def code_auto_run(self):
        return bool(self.s.get("tasks", "auto_run"))

    def confirm(self, question, timeout=120, cancel=None):
        """Спросить «да/нет» вне разговора (для фоновой задачи): голосом и кнопками в виджете.
        Блокирует вызывающий поток до ответа, timeout секунд или cancel (Event задачи: «останови задачу» не ждёт
        двух минут, №54) -> True при «да», False при «нет», None — никто не ответил или задачу остановили."""
        for _ in range(240):                                   # один вопрос за раз: ждём до 2 мин, пока ответят на прежний
            if self.pending_confirm is None or (cancel is not None and cancel.is_set()):
                break
            time.sleep(0.5)
        if cancel is not None and cancel.is_set():
            return None
        box = {"event": threading.Event(), "answer": False}
        self.pending_confirm = box
        self.emit("confirm", text=question)
        self.announce(_spoken_question(question) + " Скажите «да» или «нет».")
        end = time.monotonic() + timeout
        while not box["event"].wait(min(0.5, max(0.0, end - time.monotonic()))):
            if time.monotonic() >= end or (cancel is not None and cancel.is_set()):
                break
        answered = box["event"].is_set()
        if self.pending_confirm is box:
            self.pending_confirm = None
        self.emit("confirm_done", ok=box["answer"])
        log.info("Подтверждение (задача): %s", ("да" if box["answer"] else "нет") if answered else "без ответа")
        return box["answer"] if answered else None

    def ask_user(self, task, question):
        """Задача спрашивает: говорим вопрос; следующая фраза пользователя без имени в течение 2 минут — ответ
        (см. handle_text в engine_audio.py)."""
        self.task_answer_until = time.monotonic() + 120
        self.tg_task_until = time.monotonic() + 6 * 3600     # из Telegram ответить можно и позже (вопрос пришёл туда)
        self.announce(f"Вопрос по задаче «{task.title}»: {question}")

    def find_persona(self, name):
        """«Лиру», «Патрика», «эва» → id персонажа или None. Сравниваем имя, слова вызова, другие написания и id
        без последней буквы (грубо отбрасываем падежное окончание); точное совпадение важнее."""
        q = re.sub(r"[^\wё]", "", (name or "").lower().replace("ё", "е"))
        if not q:
            return None
        best = None
        for p in self.personas.all():
            names = {p["name"].lower().replace("ё", "е")} | {w.lower().replace("ё", "е") for w in (p.get("wake") or [])} \
                | {w.lower() for w in (p.get("aliases") or [])} | {p["id"].lower()}
            for n in names:
                n = re.sub(r"[^\wё]", "", n)
                if not n:
                    continue
                if q == n:
                    return p["id"]
                stem = n[:-1] if len(n) > 3 else n
                if (q.startswith(stem) or n.startswith(q[:-1] if len(q) > 3 else q)
                        or (len(q) >= 3 and len(n) >= 3 and q[:-1] == n[:-1])):
                    best = best or p["id"]
        return best

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

    @staticmethod
    def _cloud_said(prof, e):
        """Ошибка, которую облако Dewiar объяснило само («заряд закончился», «лимит на сегодня») -> True.
        Такую ошибку говорим как есть и не повторяем запрос без инструментов. Тексты — от сервера облака (cloud.php)."""
        from cloud import is_cloud
        return is_cloud(prof) and bool(re.match(r"(Заряд|Ключ) Dewiar|На сегодня лимит|Слишком много|Сейчас у Dewiar много людей", str(e)))

    def _cloud_fallback(self, prof, e):
        """Запасной мозг для облака: «Мозг» → карточка облака → «Если облако не отвечает» -> профиль или None
        (не облако, запасного нет или он тоже облачный). Показывает заметку на 15 с; режим инструментов — свой у запасного."""
        from cloud import is_cloud
        if not is_cloud(prof):
            return None
        fid = self.s.get("llm", "fallback") or ""
        fb = (self.s.get("llm", "profiles") or {}).get(fid)
        if not fb or is_cloud(fb):
            return None
        log.warning("☁ Облако: %s — отвечает запасной мозг «%s»", e, fb.get("name") or fid)
        self.note(f"Облако не ответило ({str(e)[:60]}) — ответил запасной мозг «{fb.get('name') or fid}»")
        threading.Timer(15, lambda: self.note("")).start()
        mode = (self.s.get("llm", "tools_modes") or {}).get(self._tools_key(fb))
        return dict(fb, tools_mode=mode) if mode in ("native", "prompt") else dict(fb)

    def _own_fallback(self, prof, e):
        """Своя модель (LM Studio, Ollama, свой сервер) не отвечает — не включена или сервер выключен (29.10, пакет:
        «своя модель · нет связи» — 107 за неделю; у 270 компьютеров из 820 мозг есть, а ответа не было ни разу).
        Включено «Мозг» → «Если своя модель не отвечает — отвечать через Dewiar» и бесплатный мозг подключён ->
        его профиль; выключено — один раз за запуск подсказка, что сделать. Без согласия вопрос в облако не уходит:
        свою модель часто выбирают ради приватности."""
        from cloud import PROFILE_ID, is_cloud
        from health import brain_kind, why_kind
        if is_cloud(prof) or brain_kind(prof) not in ("local", "server") or why_kind(e) != "connect":
            return None
        fb = (self.s.get("llm", "profiles") or {}).get(PROFILE_ID)
        if self.s.get("llm", "own_fallback") and fb:
            log.warning("Своя модель не отвечает (%s) — отвечает мозг Dewiar", e)
            self.note("Своя модель не отвечает — ответила через Dewiar. Запустите LM Studio или Ollama, и я вернусь к ней.")
            threading.Timer(20, lambda: self.note("")).start()
            mode = (self.s.get("llm", "tools_modes") or {}).get(self._tools_key(fb))
            return dict(fb, tools_mode=mode) if mode in ("native", "prompt") else dict(fb)
        if not getattr(self, "_own_fb_hinted", False):
            self._own_fb_hinted = True
            self.note("Своя модель не отвечает: запустите LM Studio или Ollama (модель должна быть загружена). Чтобы в такие "
                      "минуты отвечал бесплатный мозг Dewiar — студия → «Мозг» → «Если своя модель не отвечает».")
        return None

    def self_check(self):
        """«Проверить всё» (студия → «О программе»): по пунктам — работает ли, а если нет — что сделать и где.
        -> список {name, ok, warn, detail, fix, page}; page — раздел студии для кнопки перехода. Делает сетевые
        запросы (модель, облако, сайт) — вызывать не из потока интерфейса."""
        import shutil as _sh
        import httpx
        out = []

        def add(name, ok, detail, fix="", page="", warn=False):
            out.append({"name": name, "ok": bool(ok), "warn": bool(warn) and not ok, "detail": detail, "fix": "" if ok else fix, "page": page})
        st = self.status
        dv = self.device_status()
        add("Мощность компьютера", dv["level"] == "ok" or dv["stt_server"],
            f"{dv['ram']} ГБ памяти, {dv['cores']} ядер" + ("" if dv["level"] == "ok" else f" — мало ({'лёгкий режим' if dv['light'] else 'может тормозить'})"),
            dv["advice"], "dw", warn=True)
        add("Микрофон", st.get("input"), st.get("input") or "не найден",
            "Подключите микрофон и выберите его в «Звук и поведение».", "sound")
        prof = self.s.active_llm()
        if not prof:
            add("Мозг", False, "модель не подключена", "Выберите в «Мозге», где будет думать ассистент.", "brain")
        else:
            try:
                t0 = time.monotonic()
                list_models(prof, timeout=8)
                add("Мозг", True, f"{prof.get('name') or prof.get('base_url')} — отвечает за {int((time.monotonic() - t0) * 1000)} мс")
            except LLMError as e:
                add("Мозг", False, f"{prof.get('name') or ''}: {e}", "Проверьте адрес и ключ в «Мозге» (кнопка «Проверить» у модели).", "brain")
        if self.cloud.key:
            c = self.cloud.refresh()
            if c.get("error") and c.get("percent") is None:
                add("Заряд Dewiar Облака", False, c["error"], "Проверьте интернет или ключ в «Мозге».", "brain")
            else:
                add("Заряд Dewiar Облака", not c.get("low") and not c.get("empty") and not c.get("frozen"),
                    f"{c.get('percent', 0)}% · хватит примерно на {c.get('turns', 0)} ответов", c.get("topup") or "Пополните заряд.", "brain",
                    warn=not c.get("empty") and not c.get("frozen"))
        add("Распознавание речи", st.get("stt_ready"), (st.get("stt") or "—") + ("" if st.get("stt_ready") else " — ещё загружается"),
            "Подождите, пока скачается модель (видно в виджете), или выберите другое распознавание в «Слухе».", "ears", warn=True)
        add("Голос", st.get("tts") and st.get("tts") != "Выключен", st.get("tts") or "—", "Включите голос в разделе «Голос».", "voice")
        try:
            t0 = time.monotonic()
            r = httpx.get(self.updater.url, timeout=6)
            add("Интернет и сайт Dewiar", r.status_code < 500, f"на связи, {int((time.monotonic() - t0) * 1000)} мс")
        except Exception as e:  # noqa: BLE001
            add("Интернет и сайт Dewiar", False, f"нет связи ({type(e).__name__})",
                "Без интернета работают локальные модели; обновления и облако — нет.", "", warn=True)
        try:
            free = _sh.disk_usage(str(STATE_DIR)).free / 2 ** 30
            add("Место на диске", free >= 1.5, f"свободно {free:.1f} ГБ", "Освободите место: моделям и голосам нужно около 1 ГБ.", "", warn=free >= 0.5)
        except OSError:
            pass
        u = self.updater.public()
        add("Версия", not u.get("available"), f"Dewiar {VERSION}" + (f" — есть {u['available']}" if u.get("available") else " — последняя"),
            "Обновите: «О программе» → «Обновить».", "about", warn=True)
        if st.get("meeting"):
            add("Созвон", False, "идёт созвон: " + ", ".join(st["meeting"].get("apps") or []), "Пока идёт созвон, ассистент слушает тише — так задумано.",
                "sound", warn=True)
        return out

    def build_report(self, note="", tail_lines=1500, fresh=False):
        """Отчёт для разработчика: версия, система, состояние, настройки без ключей, звуковые устройства, следы задач и журнал.
        fresh — только то, что случилось после прошлого отправленного отчёта (журнал, ошибки, задачи, ui.log): иначе
        давно исправленная ошибка тянется из отчёта в отчёт и мешает увидеть новую. Отметка — report_mark.json."""
        import platform
        # в настройках скрываем всё, чьё имя похоже на секрет (ключи, заголовки и переменные окружения MCP-программ)
        # №311 (пакет 27.10): «max_tokens» в отчёте был «***» — числа и флаги вида *_tokens, keys_* не секрет
        secret = re.compile(r"^(?!max_tokens$|.*_tokens$|tokens$|token_count$)(?:.*(api_key|token|password|key|secret|headers|auth|cookie|env))", re.I)

        def clean(x):
            if isinstance(x, dict):
                return {k: ("***" if secret.search(k) and v else clean(v)) for k, v in x.items()}
            if isinstance(x, list):
                return [clean(v) for v in x]
            return x
        lines = [f"Dewiar {VERSION} — отчёт {datetime.now():%Y-%m-%d %H:%M}", f"Система: {OS_NAME}; Python {platform.python_version()}; "
                 f"{platform.machine()}; ядер: {os.cpu_count()}", ""]
        if note:
            lines += ["== Со слов человека", note, ""]
        lines += ["== Состояние", json.dumps(self.status, ensure_ascii=False, indent=1, default=str), ""]
        lines += ["== Настройки (без ключей)", json.dumps(clean(self.s.snapshot()), ensure_ascii=False, indent=1), ""]
        try:
            lines += ["== Звуковые устройства", json.dumps(list_devices(), ensure_ascii=False, indent=1), ""]
        except Exception as e:  # noqa: BLE001
            lines += [f"== Звуковые устройства: {e}", ""]
        mark = self._report_mark() if fresh else {}
        since = float(mark.get("ts") or 0)
        if since:
            lines += [f"(всё ниже — после прошлого отчёта{(' №' + str(mark['id'])) if mark.get('id') else ''}, "
                      f"{datetime.fromtimestamp(since):%Y-%m-%d %H:%M})", ""]
        try:                                    # долгие задачи: чем закончились, ход последних (журнал), следы ошибок
            ts = [f for f in sorted((STATE_DIR / "task_traces").glob("*.json"))[-15:] if f.stat().st_mtime >= since]
            if ts:
                lines += ["== Задачи: следы последних"] + [f.read_text(encoding="utf-8", errors="replace")[:1500] for f in ts] + [""]
            recent = [x for x in self.tasks.tasks.values() if not since or (x.dir / "задача.json").exists()
                      and (x.dir / "задача.json").stat().st_mtime >= since]
            for t in sorted(recent, key=lambda x: str(x.data.get("created", "")))[-3:]:
                j = (t.dir / "журнал.md").read_text(encoding="utf-8", errors="replace").splitlines() if (t.dir / "журнал.md").exists() else []
                lines += [f"== Задача «{t.title}»: {t.status} {t.data.get('error', '')}", "-- План:",
                          t.plan()[:2000], "-- Журнал (конец):"] + j[-120:] + [""]
        except Exception as e:  # noqa: BLE001
            lines += [f"== Задачи: {e}", ""]
        tail = self._log_tail(mark if since else None)
        errs = [ln for ln in tail if re.match(r"\d\d:\d\d:\d\d (ERROR|CRITICAL)", ln)]
        if errs:
            lines += ["== Ошибки (последние)"] + errs[-40:] + [""]
        lines += ["== Журнал (последние строки)"] + tail[-tail_lines:]
        try:                                    # ядро падало в библиотеке (faulthandler в main.py) — где именно
            cr = (STATE_DIR / "logs" / "core.crash").read_text(encoding="utf-8", errors="replace")
            blocks = [b for b in cr.split("\n--- запуск ") if "Fatal Python error" in b or "access violation" in b or "stack overflow" in b]   # 0xe06d7363 (пойманное C++) — шум
            if blocks:
                lines += ["", "== Падения ядра (core.crash)"] + ("--- запуск " + blocks[-1]).splitlines()[:80]
        except OSError:
            pass
        try:                                    # интерфейс: замирания окон (сторож главного цикла) и ошибки окон
            ui = (STATE_DIR / "logs" / "ui.log").read_text(encoding="utf-8", errors="replace").splitlines()
            if since:
                cut = f"{datetime.fromtimestamp(since):%Y-%m-%d %H:%M:%S}"
                ui = [ln for ln in ui if ln[:19] >= cut]
            if ui:
                lines += ["", "== Интерфейс (ui.log)"] + ui[-300:]
        except OSError:
            pass
        return self._redact("\n".join(lines))

    @staticmethod
    def _redact(text):
        """Последняя страховка перед отправкой: секреты, которые могли попасть в журнал, — ключи Bearer и dw-,
        токены Telegram, пароли в адресах."""
        text = re.sub(r"(Bearer\s+)[\w.-]+", r"\1***", text)
        text = re.sub(r"\bdw-[a-z0-9]{4,}(?:-[a-z0-9]{2,})+", "dw-***", text, flags=re.I)
        text = re.sub(r"\bbot\d{5,}:[\w-]{20,}", "bot***", text)                     # токен Telegram в адресах API
        text = re.sub(r"(://[^/\s:@]+:)[^@\s/]+@", r"\1***@", text)                    # пароль в адресе (прокси и т. п.)
        return mask_tokens(text)                                                       # JWT, ключи API, «токен: …»

    @staticmethod
    def _log_tail(mark=None):
        """Строки журнала ядра: прошлый файл после ротации (core.log.1), затем текущий. mark — отметка прошлого отчёта
        ({"ino", "size"} файла core.log тогда): только строки после неё (файл с тех пор повернули — с того места в .1)."""
        logf = STATE_DIR / "logs" / "core.log"
        tail = []
        for f in (logf.with_name("core.log.1"), logf):
            try:
                st = f.stat()
                start = 0
                if mark:
                    if st.st_ino == mark.get("ino"):
                        start = int(mark.get("size") or 0) if st.st_size >= int(mark.get("size") or 0) else 0
                    elif f.name == "core.log.1" or mark.get("ino") is None:
                        start = st.st_size                 # всё это было до прошлого отчёта
                with open(f, "rb") as fh:
                    fh.seek(start)
                    tail += fh.read().decode("utf-8", errors="replace").splitlines()
            except OSError:
                pass
        return tail

    @staticmethod
    def _report_mark():
        try:
            return json.loads((STATE_DIR / "report_mark.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _report_mark_set(rid):
        """Отчёт ушёл — следующий начнётся отсюда: где кончался core.log (inode и размер) и когда."""
        import time as _t
        logf = STATE_DIR / "logs" / "core.log"
        try:
            st = logf.stat()
            m = {"ino": st.st_ino, "size": st.st_size}
        except OSError:
            m = {}
        m.update(ts=_t.time(), id=rid)
        try:
            (STATE_DIR / "report_mark.json").write_text(json.dumps(m), encoding="utf-8")
        except OSError:
            pass

    def save_report(self):
        """Отчёт одним файлом на рабочем столе (если отправить не получается — его можно переслать) -> путь к файлу.
        Рабочий стол: Windows — известная папка, Linux — xdg-user-dir (папка бывает названа по-русски), иначе домашняя."""
        text = self.build_report()
        if os.name == "nt":
            import winsys
            desk = winsys.known_folder("Desktop")
        else:
            desk = Path.home() / "Desktop"
            try:
                d = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=3).stdout.strip()
                if d:
                    desk = Path(d)
            except (OSError, subprocess.SubprocessError):
                pass
        if not desk.is_dir():
            desk = Path.home()
        out = desk / f"Dewiar — отчёт {datetime.now():%Y-%m-%d %H-%M}.txt"
        out.write_text(text, encoding="utf-8")
        log.info("Отчёт сохранён: %s", out)
        return str(out)

    def _report_summary(self):
        """Кратко для списка отчётов: последние разные ошибки из журнала, без времени и уровня."""
        errs = [re.sub(r"^\d\d:\d\d:\d\d \w+\s+", "", ln) for ln in self._log_tail(self._report_mark() or None)[-3000:]
                if re.match(r"\d\d:\d\d:\d\d (ERROR|CRITICAL)", ln)]
        return "; ".join(dict.fromkeys(errs[-6:]))[:480]

    def report_send(self, note="", auto=False, summary="", shot=None, who="", plain=False):
        """«Отправить отчёт разработчику»: отчёт сразу появляется в управлении облаком (cloud.php → «Здоровье»).
        Ключ Dewiar — если есть (по нему видно, чей отчёт); без него тоже принимается. shot — снимок экрана (JPEG) и
        who — подпись автора: это жалоба (core/health.py). plain — только note и сведения о программе, без журнала
        (ночной разбор, night.py: в журнале есть реплики человека). DEWIAR_REPORT_URL — адрес для тестов.
        -> {"id", "secret"}; ошибка связи или отказ сервера — ValueError с понятным текстом."""
        import platform
        import httpx
        from cloud import DEFAULT_URL, base_of, norm_key
        note = (note or "").strip()[:2000]
        text = (f"Dewiar {VERSION} — {OS_NAME} {platform.machine()}\n\n{note}" if plain
                else self.build_report(note, tail_lines=600 if auto else 1500, fresh=not shot and not who))
        url = os.environ.get("DEWIAR_REPORT_URL") or base_of(self.s.get("cloud", "url") or DEFAULT_URL)
        key = (self.s.get("cloud", "key") or "").strip()
        body = {"kind": "auto" if auto else "manual", "app": "desktop", "version": VERSION, "os": f"{OS_NAME} {platform.machine()}",
                "device": platform.node()[:60], "summary": (summary or self._report_summary())[:500], "note": note, "text": text}
        if shot:
            import base64
            body["shot"] = "data:image/jpeg;base64," + base64.b64encode(shot).decode()
        if who:
            body["who"] = who
        h = {"Authorization": f"Bearer {norm_key(key)}"} if key else {}
        try:
            r = httpx.post(url.split("?", 1)[0] + "?p=/report", json=body, headers=h, timeout=60 if shot else 40)
            d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        except (httpx.HTTPError, ValueError) as e:
            from net import blocked_hint
            raise ValueError("не удалось отправить отчёт: нет связи с dewiar.pro." + blocked_hint()
                             + " Можно «Сохранить в файл» и прислать его.") from e
        if r.status_code >= 400 or not d.get("ok"):
            msg = ((d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else "") or f"сервер ответил {r.status_code}"
            raise ValueError("отчёт не принят: " + msg)
        log.info("🧾 Отчёт №%s отправлен разработчику (%s)", d.get("id"), "сам, при сбое" if auto else "кнопкой")
        self._report_mark_set(d.get("id"))
        return {"id": d.get("id"), "secret": d.get("secret", "")}

    # ---------- отчёты сами при сбое (с согласия) ----------
    def report_problem(self, sig, summary):
        """Сбой: если человек разрешил — отчёт уходит сам (одна и та же беда — не чаще раза в 12 ч, не больше 4 в сутки,
        несколько сбоев подряд — одним отчётом через 20 с); не спрашивали — один раз за запуск предлагаем.
        sig — подпись беды: цифры в ней заменяются на #, чтобы одна ошибка с разными числами считалась одной.
        Учёт отправленного — report_sent.json в STATE_DIR (переживает перезапуск)."""
        if self.wav_input and not os.environ.get("DEWIAR_REPORT_URL"):
            return                                       # прогон тестов по wav-файлу — отчёты только на тестовый адрес
        auto = self.s.get("report", "auto")             # True — согласие, False — отказ, None — ещё не спрашивали
        if auto is False:
            return
        if auto is None:
            if not getattr(self, "_report_offered", False):
                self._report_offered = True
                self.emit("report_offer", summary=summary[:200])
            return
        sig = re.sub(r"\d+", "#", sig)[:160]
        with self._report_lock:
            f = STATE_DIR / "report_sent.json"
            try:
                sent = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                sent = {}
            now = time.time()
            sent = {k: v for k, v in sent.items() if now - v < 86400}
            if now - sent.get(sig, 0) < 12 * 3600 or len(sent) >= 4 or sig in self._report_pending:
                return
            sent[sig] = now
            try:
                f.write_text(json.dumps(sent), encoding="utf-8")
            except OSError:
                pass
            self._report_pending[sig] = summary
            if len(self._report_pending) > 1:
                return                                   # уже ждём — уйдёт одним отчётом

        def later():
            time.sleep(float(os.environ.get("DEWIAR_REPORT_WAIT", "20")))   # дать журналу дописать, что было после сбоя
            with self._report_lock:
                items = dict(self._report_pending)
                self._report_pending.clear()
            try:
                self.report_send(auto=True, summary=" | ".join(items.values())[:500])
            except Exception as e:  # noqa: BLE001
                log.info("🧾 Отчёт о сбое не отправлен: %s", e)
        threading.Thread(target=later, daemon=True, name="report").start()

    def _install_report_hook(self):
        """Обработчик корневого журнала: каждая запись ERROR и выше → report_problem. Записи самой отправки
        (логгер *report) и повторный вход из того же потока пропускаем — иначе сбой отправки порождал бы
        новый отчёт без конца."""
        eng = self

        class Hook(logging.Handler):
            def emit(self, rec):
                if rec.name.endswith("report") or getattr(_report_tls, "busy", False):
                    return
                _report_tls.busy = True
                try:
                    exc = rec.exc_info[0].__name__ if rec.exc_info and rec.exc_info[0] else ""
                    msg = rec.getMessage()
                    if rec.exc_info and rec.exc_info[1]:
                        msg += f" — {exc}: {rec.exc_info[1]}"
                    eng.health_problem(f"{rec.name}: {msg}")                 # в пульс — всегда (без журнала и личного)
                    eng.report_problem(f"{rec.name}|{rec.msg}|{exc}", f"{rec.name}: {msg}"[:300])
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    _report_tls.busy = False
        h = Hook(level=logging.ERROR)
        logging.getLogger().addHandler(h)
        return h

    def _tools_key(self, prof):
        """Ключ, под которым запоминается режим инструментов модели (llm.tools_modes): «адрес|модель»."""
        return f"{(prof or {}).get('base_url', '').rstrip('/')}|{(prof or {}).get('model', '')}"

    def probe_tools_bg(self, force=False):
        """Узнать в фоне (поток probe-tools), умеет ли активная модель вызывать инструменты и как: native, prompt
        или none. Один раз на «адрес|модель»; force — проверить заново."""
        prof = self.s.active_llm()
        if not prof:
            return
        key = self._tools_key(prof)
        modes = self.s.get("llm", "tools_modes") or {}
        # tools_probe_v 2: проверка первой версии ошибочно записывала «думающие» модели в «не умеет» (none);
        # v3 (22.10): облако Dewiar отклоняло проверку из-за chat_template_kwargs, и модель записывалась в «описанием
        # в тексте» (prompt) — такие записи один раз сбрасываем, чтобы проверить заново; найденные native остаются
        # v4 (22.10, вечер): настоящая причина — сайт превращал пустой объект {} в схеме функции в [] (cloud.php
        # chat_schema_fix); после обновления сайта — проверить ещё раз
        # v5 (23.10): «none» больше не выводится из проверки — прежние записи «none» сбрасываем
        if self.s.get("llm", "tools_probe_v") != 5:
            keep = ("native",) if self.s.get("llm", "tools_probe_v") != 4 else ("native", "prompt")
            stale = {k: v for k, v in modes.items() if v in keep}
            with self.s._lock:
                self.s.data.setdefault("llm", {})["tools_modes"] = stale
            self.s.update({"llm": {"tools_probe_v": 5}})
            modes = stale
        if key in self._probing or (not force and key in modes):
            return
        self._probing.add(key)

        def run():
            try:
                mode = probe_tools(prof)
                if mode is None:                      # сервер не ответил — не запоминаем, спросим в следующий раз
                    return
                self.s.update({"llm": {"tools_modes": {key: mode}}})
                if mode == "none":
                    self.note("Эта модель не умеет выполнять действия (музыка, скриншоты, программы) — только отвечать")
            except Exception as e:  # noqa: BLE001
                log.info("Проверка инструментов не удалась: %s", e)
            finally:
                self._probing.discard(key)
        threading.Thread(target=run, name="probe-tools", daemon=True).start()

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
            try:
                body = extract(dst) if dst.suffix.lower() in (".md", ".txt", ".csv", ".html", ".htm", ".pdf", ".docx", ".odt") \
                    else (data.decode("utf-8") if len(data) < 400_000 else "")
            except Exception as e:  # noqa: BLE001
                body = ""
                log.info("Вложение %s: текст не извлечён (%s)", name, e)
            body = (body or "").strip()
            if body:
                cut = body[:max(2000, budget)]
                budget -= len(cut)
                parts.append(f"[Файл «{name}», сохранён в папке ассистента: {rel}]\n{cut}" +
                             ("\n…(дальше файл обрезан — целиком его можно прочитать инструментом read_file)" if len(cut) < len(body) else ""))
            else:
                parts.append(f"[Файл «{name}» ({len(data) // 1024} КБ) сохранён в папке ассистента: {rel}; текста в нём нет]")
            log.info("📎 %s → %s", name, rel)
        self._chat_att = (time.monotonic(), saved)
        q = text.strip() or ATT_DEFAULT_Q
        return q + "\n\nВложения:\n" + "\n\n".join(parts)

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

    def _media_stop_word(self, word, force=False):
        """«Пауза» / «стоп» без имени, пока играет музыка — ставим её на паузу -> True, если поставили. Если ничего
        не играет — молчим (слово могли сказать не ассистенту). force — после имени: если узнать, играет ли что-то,
        нельзя (media_playing() → None, Windows), всё равно жмём «играть/пауза»."""
        from tools import media_playing, t_media
        if self.radio.playing:                          # своё радио — сразу, без MPRIS
            st = self.radio.pause()
            log.info("⏸ «%s» — радио «%s» на паузе", word, (st or {}).get("name", ""))
            self.emit("heard", text=word.capitalize())
            self.emit("answer", text=f"Радио на паузе. Продолжить — «{self.persona_name()}, продолжи».", done=True)
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
                info = up.check()
                st = up.public()
            except Exception as e:  # noqa: BLE001
                info, st = None, {"error": str(e)}
            cur = st.get("current") or ""
            if info:
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

    def _tool_call_persona(self, name):
        """Инструмент «позвать персонажа»: сама передача — после ответа (turn.switch_to, конец _run_turn).
        -> текст для модели: что сказать сейчас."""
        pid = self.find_persona(name)
        if not pid:
            names = ", ".join(p["name"] for p in self.personas.all())
            raise ToolError(f"нет персонажа «{name}». Есть: {names}")
        if pid == self.s.get("persona"):
            return "Это ты сам(а). Просто продолжай разговор."
        t = self.turn
        if t is not None:
            t.switch_to = pid
        who = self.personas.get(pid)["name"]
        return (f"Готово: как только ты договоришь, {who} откликнется сам(а) своим голосом. Скажи одну короткую фразу, "
                f"что передаёшь слово, и не отвечай за {who}.")

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

    def _run_turn(self, turn, text, images=()):
        """Поток turn-N: один ход разговора. Фразы ответа идут в очередь sentences — их озвучивает отдельный поток
        (_speak_worker; для сообщений без голоса — _drain_worker), None в очереди — конец. До 6 шагов
        «модель → инструменты → результаты → модель». Запасные пути: облако не ответило — запасной мозг;
        модель не справилась с инструментами — без них; не приняла картинку — без неё (модель запоминается в _blind).
        В конце: ответ в мессенджер (turn.via["done"]), история, «продолжение разговора», возврат к главному
        персонажу после специалиста и передача слова, если её попросил инструмент. Отменённый ход в историю не идёт."""
        prof = self.persona_llm()
        self._turn_text = text                       # read_webpage: длинная страница — куски по словам вопроса
        sentences = queue.Queue()
        silent = bool(turn.via) and not turn.via.get("speak")
        speaker = threading.Thread(target=self._drain_worker if silent else self._speak_worker, args=(turn, sentences),
                                   daemon=True)
        speaker.start()
        self.set_state("thinking")
        try:
            if not prof and (self.account.logged_in() or self.s.get("cloud", "key")):
                try:                                   # модели нет, а вход dewiar.pro (или ключ) есть — подключаем модели Dewiar сами
                    self._cloud_use()
                    prof = self.persona_llm()
                except Exception as e:  # noqa: BLE001
                    log.info("🧠 Модели Dewiar сами не подключились: %s", e)
            if not prof:                               # 29.10 (пакет: 28% компьютеров так и не подключили мозг и молчат)
                threading.Thread(target=self.auto_join, args=("вопрос без мозга",), daemon=True).start()   # подключится — дальше полный
                prof = self._trial_llm()               # а этот ответ — сразу, пробным разговором сайта, без настройки
            if not prof:
                raise LLMError("я пока не подключён к языковой модели — откройте настройки, раздел «Мозг»"
                               + (": войдите в аккаунт dewiar.pro — модели Dewiar подключатся сами" if not self.account.logged_in() else ""))
            msgs = self._messages(text, images, prof)
            from llm import wants_think
            if prof.get("think") not in ("on", "off") and self.s.get("llm", "think_auto") is not False and wants_think(text):
                # сложная просьба — модель думает (дольше, но стих с рифмой, а расчёт со смыслом); лимит — с запасом на размышления
                prof = dict(prof, think="on", max_tokens=max(6144, int(prof.get("max_tokens") or 0)))
                log.info("🧠 Сложная просьба — модель подумает перед ответом")
            econ_main = None                            # экономный режим (economy.py): простое — дешёвой модели, основная — запасом
            try:
                import economy
                cheap = economy.model_for(prof, text, self.history, bool(images), think=prof.get("think") == "on")
            except Exception:  # noqa: BLE001
                cheap = ""
            if cheap:
                econ_main = prof
                prof = dict(prof, model=cheap)
                self.health_count("econ")
                log.info("💸 Простой вопрос — отвечает недорогая модель «%s»", cheap)
            from llm import creative_temp
            ask0 = text.split("\n\nВложения:")[0]
            temp = creative_temp(ask0, prof.get("temperature"))
            if temp != float(prof.get("temperature") or 0.7):
                prof = dict(prof, temperature=temp)       # творческая просьба — смелее (отзыв 17.10 про креатив)
                log.info("🎨 Творческая просьба — температура %.2f", temp)
            specs = self.toolbox.specs() if self.s.get("tools", "enabled_all") is not False else []
            mode = (self.s.get("llm", "tools_modes") or {}).get(self._tools_key(prof))
            if mode in ("native", "prompt"):
                prof = dict(prof, tools_mode=mode)
            elif mode is None and specs:
                self.probe_tools_bg()                  # ещё не проверяли — проверим в фоне, этот ответ — в режиме по умолчанию
            system = self._system(bool(specs))
            import boundaries
            from llm import POEM_ASK, POEM_NOTE, RECO_ASK, RECO_NOTE
            if POEM_ASK.search(text.split("\n\nВложения:")[0]):
                system += POEM_NOTE                     # стихи — рифмы по ударению подбираются заранее
            elif RECO_ASK.search(text.split("\n\nВложения:")[0]):
                system += RECO_NOTE                     # советы фильмов и песен — только существующее
            if boundaries.rude(text):                  # грубят самому помощнику — спокойная граница в этом ходе, счётчик в пульс
                system += boundaries.NOTE
                self.health_count("rude")
                log.info("🛡 грубость в адрес помощника — отвечу спокойно, с границей")
            recalled = ""
            try:
                recalled = self.recall.context(text.split("\n\nВложения:")[0])
            except Exception as e:  # noqa: BLE001
                log.info("Поиск по записям: %s", e)
            ctx = [self._turn_context(text)]           # меняющееся — в справку к вопросу, подсказка остаётся прежней
            mlines, mpages = self.memory_for(text.split("\n\nВложения:")[0])
            if mlines:                                 # Память 2.0: старое о человеке не теряется — приходит к вопросу
                log.info("🧠 Из памяти к вопросу: %s", ", ".join(mpages))
                ctx.append("Из памяти о пользователе (подобрано к этому вопросу из «Обо мне» — используй, если к месту, "
                           "не пересказывай всё):\n" + mlines)
            if recalled:
                log.info("📎 Вспомнил из записей: %s", ", ".join(re.findall(r"^\[([^\]]+)\]", recalled, re.M)))
                ctx.append("Из записей пользователя в твоей папке (нашлось по словам вопроса). Если это отвечает на "
                           "вопрос — ответь по ним и коротко скажи, откуда («в заметке …»). Если не относится — не "
                           "упоминай:\n" + recalled)
            try:
                ag = self.agenda_context(text)             # «что у нас по плану» — дела и календарь сразу перед моделью
                if ag.strip():
                    ctx.append(ag.strip())
                cr = self.care_context(text, turn)         # «Заботливая память»: прошло важное — спросить, как прошло
                if cr:
                    ctx.append(cr)
                from quality import DIAGRAM_ASK, PAGE_ASK
                if PAGE_ASK.search(text):                     # 28.10: HTML писала в чат и читала теги вслух
                    system += ("\n\nСЕЙЧАС ПРОСЯТ СТРАНИЦУ В БРАУЗЕРЕ: собери данные (find_notes, read_file, web_search) и одним "
                               "вызовом show_page передай html содержимого — разделы <section> с <h2>, списки, таблицы; оформление "
                               "добавится само, страница откроется в браузере. HTML в ответе не пиши, скрипты для этого не пиши; "
                               "после — одна фраза, что открыла.")
                if DIAGRAM_ASK.search(text):                  # экзамен 15.10: «Схема готова и уже на экране» — а схемы нет
                    system += ("\n\nСЕЙЧАС ПРОСЯТ СХЕМУ: в этом ответе обязательно блок ```mermaid (flowchart LR или TD, подписи "
                               "узлов по-русски в кавычках) — только он и рисует схему на экране. Без блока схемы нет: не пиши "
                               "«схема готова» или «на экране», не нарисовав её. Сначала блок, потом одна-две фразы о главном.")
            except Exception as e:  # noqa: BLE001
                log.info("План на день: %s", e)
            if turn.via and not turn.via_job:
                src = turn.via.get("from") or "Telegram"
                system += (f"\n\nСейчас пользователь пишет тебе из {src} (не голосом): ответ уйдёт ему сообщением. Можно "
                           "чуть подробнее и со списками; файлы из папки ассистента — инструментом send_telegram"
                           + (" (to: max)." if src == "MAX" else "."))
            if mode == "none" and specs:
                specs = []
                system = self._system(False) + ("\n\nЭта модель не умеет выполнять действия (музыка, скриншоты, "
                                                "программы). Если просят действие — честно скажи одной фразой, что с этой "
                                                "моделью действия недоступны, и предложи выбрать другую модель в «Мозге».")
            slow_at = (getattr(self, "_tools_slow", None) or {}).get(self._tools_key(prof))
            if specs and slow_at is not None and time.monotonic() - slow_at < 1200:
                # своя модель только что не дождалась ответа с инструментами (180 с) — 20 минут спрашиваем без них, а не
                # ждём те же 180 с на каждом вопросе и потом ещё ответ без них (№133, 20.10: 4 ядра, Ollama, «вечно в думках»)
                specs = []
                system = self._system(False) + ("\n\nСейчас действия (музыка, скриншоты, программы) недоступны: модель на "
                                                "этом компьютере не успевает с ними. Если просят действие — честно скажи "
                                                "это одной фразой.")
            kb = self._persona_knowledge(text, turn)
            if kb:
                ctx.append(kb.strip())
            if images:
                ctx.append(VISION_HINT)                      # фото: перевод, документ, еда (идеи пользователей 24.10)
            elif len(text) < 400:
                try:
                    import guide
                    gh = guide.hint(text, "pc")                  # «как защищены мои данные?» — раздел руководства сразу
                    if gh:
                        ctx.append(gh)
                except Exception:  # noqa: BLE001
                    pass
            msgs = _put_context(msgs, "\n\n".join(c for c in ctx if c))
            system, specs, msgs = self._fit_window(prof, system, specs, msgs)
            split, last, codef = SentenceSplitter(), 0.0, CodeFilter()
            # вслух — не больше ~900 символов (около минуты): длинный ответ дальше только на экране («Открыть целиком»);
            # сказки, истории и чтение вслух — целиком
            # №377: «хотелось бы прослушивать всё до конца» — студия → «Голос» → «Читать длинные ответы вслух целиком»
            voice_cap = 10 ** 9 if (self.s.get("tts", "read_all") or re.search(r"сказк|истори|расскаж|прочитай|прочти|читай|стих|подробно|целиком|полностью|до конца", text.lower())) else 900
            spoken = [0, False]                         # сколько символов отдано в озвучку; предел уже достигнут

            from gender import for_persona
            gnd = self.persona_gender()
            fem = lambda t: for_persona(t, gnd)        # noqa: E731 — героиня, а модель сбилась на «рад», «понял»: правим сами

            def speak(s_):
                s_ = fem(s_)
                if spoken[1]:
                    return
                if spoken[0] + len(s_) > voice_cap and spoken[0] > 0:
                    spoken[1] = True
                    sentences.put("Дальше не читаю вслух — всё на экране." + ("" if getattr(self, "_cap_said", False) else " Читать целиком — студия, «Голос»."))
                    self._cap_said = True
                    log.info("🔇 Ответ длинный — вслух прочитано %d симв., остальное на экране", spoken[0])
                    return
                spoken[0] += len(s_)
                if getattr(self, "lat", None) is not None:
                    self.lat.mark("say")
                sentences.put(s_)
            blind_key = f"{prof.get('base_url')}|{prof.get('model')}"
            t_start = time.monotonic()
            if getattr(self, "lat", None) is not None:
                self.lat.mark("req", t_start)
            from quality import DELIVERABLE, REFUSAL_NUDGE, REMIND_NOT_SET, action_claim, bare_done, diagram_missing, reminder_missing, remind_claim, saved_claim, money_claim, looks_like_promise, looks_like_refusal, number_mismatch, promise_nudge, task_claim
            called, nudged = set(), 0                    # какие действия уже были; сколько раз просили «сделай, а не обещай»
            deliver = bool(DELIVERABLE.search(text)) and any(x.get("name") == "start_task" for x in specs or [])
            # отговорку «нет доступа к интернету» на шаге 0 (когда есть поиск) просим переделать (ниже) — значит, первую
            # фразу с отговоркой и всё после неё в озвучку не отдаём, пока шаг не кончится: иначе отказ прозвучит, а потом
            # его заменит ответ по поиску. Обычная первая фраза идёт в голос сразу — задержки для неё нет
            held, hold = [], [False]

            def say(s_):
                if hold[0] and (held or looks_like_refusal(s_)):
                    held.append(s_)
                    return
                hold[0] = False
                speak(s_)
            seen_calls = {}                              # одинаковый вызов в одном ходе — не повторяем (результат уже есть)
            done_calls, checked = [], False                  # что вызвано с результатами — сверить числа ответа (number_mismatch)
            drew = 0                                         # просили схему, а её нет — попросили нарисовать (до двух раз за ход)
            saved_checked = False                            # «записала» без единого действия — попросили записать (раз за ход)
            remind_asked = False                             # пообещала напомнить без set_reminder — попросили поставить (раз за ход)
            repeat_checked = False                           # ответ слово в слово как недавний — попросили ответить по существу (раз за ход)
            prev_said = {_norm_answer(m.get("content")) for m in self.history[-8:] if m.get("role") == "assistant" and m.get("content")}
            for step in range(6):                       # модель → действия → результаты → модель…
                calls, step_text = [], ""
                if step == 5 and specs:                  # последний шаг — только слова: ответить тем, что уже узнал
                    specs = []
                    system += ("\n\nДействий больше не будет: прямо сейчас ответь пользователю словами по тому, что уже "
                               "узнал и сделал. Не пиши «готово» без сути.")
                hold[0] = step == 0 and any(x.get("name") == "web_search" for x in specs or [])
                if blind_key in self._blind and _has_images(msgs):
                    msgs = _drop_images(msgs)
                if step and econ_main is not None:       # после действий продолжает основная модель
                    prof = dict(econ_main, temperature=prof.get("temperature"), think=prof.get("think")) if prof.get("temperature") is not None else econ_main
                    econ_main = None
                try:
                    # с картинкой ответ сначала собираем целиком: если модель её не примет — повторим без неё;
                    # без картинки ждём только первое событие — ошибка сервера всплывёт здесь, до первого слова
                    try:
                        events = list(stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None)) \
                            if _has_images(msgs) else _first_then_stream(
                                stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None))
                    except LLMError as e0:
                        if econ_main is None or step or turn.full or turn.cancel.is_set():
                            raise
                        log.warning("💸 Недорогая модель «%s» не ответила (%s) — отвечает основная", prof.get("model"), e0)
                        prof = dict(econ_main, temperature=prof.get("temperature")) if prof.get("temperature") is not None else econ_main
                        econ_main = None
                        events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None))
                except LLMError as e:
                    fb = self._cloud_fallback(prof, e) if step == 0 and not turn.full and not turn.cancel.is_set() else None
                    if not fb and step == 0 and not turn.full and not turn.cancel.is_set():
                        fb = self._own_fallback(prof, e)    # своя модель выключена — мозг Dewiar (если человек согласился)
                    if fb:                                  # облако не ответило / заряд кончился — отвечает запасной мозг
                        prof = fb
                        events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None))
                    elif not _has_images(msgs):
                        if "без текста" in str(e) and specs and not turn.cancel.is_set() and not getattr(turn, "blank_nudged", False):
                            # пустой ответ — сбой, а не «модель не умеет действия»: ещё раз с инструментами и подсказкой
                            turn.blank_nudged = True
                            log.warning("Модель ответила пустотой (%s) — повторяю с подсказкой", e)
                            msgs = msgs + [{"role": "user", "content": "Ответь на мой вопрос: вызови нужный инструмент или ответь словами."}]
                            events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None))
                        elif specs and step == 0 and not turn.full and not turn.cancel.is_set() and not self._cloud_said(prof, e) \
                                and "без текста" not in str(e):
                            # с инструментами модель не отвечает — ответим хотя бы без них
                            log.warning("Модель не справилась с инструментами (%s) — отвечаю без действий", e)
                            from health import brain_kind, why_kind
                            if why_kind(e) == "timeout" and brain_kind(prof) in ("local", "server"):
                                slow_key = self._tools_key(prof)
                                if not hasattr(self, "_tools_slow"):
                                    self._tools_slow = {}
                                self._tools_slow[slow_key] = time.monotonic()
                                self.note("Модель на этом компьютере не успевает отвечать с действиями — 20 минут отвечаю без "
                                          "них, так быстрее. Действия (музыка, программы, напоминания) — с моделью полегче "
                                          "или облаком Dewiar (студия → «Мозг»).")
                            from llm import CTX_TEXT, _ctx_cut, ctx_full
                            if ctx_full(e) or CTX_TEXT in str(e):  # окно контекста мало (LM Studio 4096): короче и без функций
                                msgs = _ctx_cut(msgs)
                                if not getattr(self, "_ctx_noted", False):
                                    self._ctx_noted = True
                                    self.note("У модели маленькое окно контекста — отвечаю без действий и почти без памяти "
                                              "разговора. В LM Studio или Ollama поставьте длину контекста 8192 или больше.")
                            specs = []
                            system = self._system(False) + ("\n\nСейчас действия (музыка, скриншоты, программы) "
                                                            "недоступны: эта модель не умеет вызывать инструменты. Если "
                                                            "просят действие — честно скажи это одной фразой.")
                            try:
                                events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=None))
                            except LLMError as e2:
                                if not (ctx_full(e2) or CTX_TEXT in str(e2)):
                                    raise
                                # и без действий не влезло (окно 2048–4096, а память и душа длинные) — самое короткое:
                                # кто ты и вопрос; лучше простой ответ, чем «модели не хватило окна» на каждый вопрос
                                log.warning("Окно модели мало и без действий — отвечаю с самой короткой подсказкой")
                                system, msgs = self._system_min(), msgs[-1:]
                                events = _first_then_stream(stream_events(prof, system, msgs, cancel=turn.cancel, tools=None))
                        else:
                            raise
                    else:
                        log.info("Модель %s не приняла картинку (%s) — отвечаю без неё", prof.get("model"), e)
                        self._blind.add(blind_key)
                        msgs = _drop_images(msgs)
                        events = stream_events(prof, system, msgs, cancel=turn.cancel, tools=specs or None)
                for kind, val in events:
                    if turn.cancel.is_set():
                        break
                    if kind == "tools":
                        calls = val
                        continue
                    if not turn.full:
                        log.info("⏱ первые слова модели через %.1f с", time.monotonic() - t_start)
                        if getattr(self, "lat", None) is not None:
                            self.lat.mark("tok")
                        self._slow_local(prof, time.monotonic() - t_start)
                        self._coder_brain(prof)
                    turn.full += val
                    step_text += val
                    if time.monotonic() - last > 0.08 and not turn.via_job:     # текст в виджет — не чаще ~12 раз в секунду
                        self.emit("answer", text=fem(turn.full), done=False, model=True)
                        last = time.monotonic()
                    for s_ in split.feed(codef.feed(val)):         # код и команды вслух не читаем
                        say(s_)
                for s_ in split.feed(codef.flush()) + split.flush():
                    say(s_)
                if not calls and step == 0 and not turn.cancel.is_set() and any(x.get("name") == "web_search" for x in specs or []):
                    if looks_like_refusal(step_text):      # «нет доступа к интернету», а поиск есть — просим поискать (только на шаге 0)
                        log.info("✋ Модель отказалась («нет доступа»), не попробовав поиск — прошу поискать")
                        held.clear()                           # отговорка так и не прозвучала
                        sentences.put("Секунду — посмотрю в интернете.")
                        msgs = msgs + [{"role": "assistant", "content": step_text}, {"role": "user", "content": REFUSAL_NUDGE}]
                        turn.full = ""
                        self.set_state("thinking")
                        continue
                for s_ in held:                               # не отказ (длинный ответ с оговоркой или вызвала инструменты) — озвучить
                    speak(s_)
                held.clear()
                called |= {c.get("name") for c in calls}
                if not calls and not turn.cancel.is_set() and specs and step < 5:
                    # «сейчас посмотрю и расскажу» — и ни одного действия; или просили презентацию, а задача не запущена
                    want_task = deliver and "start_task" not in called and not step_text.strip().endswith("?") and nudged < 2
                    if want_task or (nudged < 1 and looks_like_promise(step_text)):
                        nudged += 1
                        log.info("✋ Модель %s — прошу сделать, а не обещать", "не запустила задачу" if want_task else "только пообещала")
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": promise_nudge(want_task)}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                    fix = "" if checked else number_mismatch(step_text, done_calls)
                    if fix:                                 # «таймер на 79 минут», а поставлено 59 (экзамен 14.10)
                        checked = True
                        log.info("✋ Число в ответе не совпадает с поставленным — прошу исправить")
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not turn.cancel.is_set() and step < 5 and specs and not remind_asked:
                    fix = remind_claim(step_text, called)
                    if fix:                                  # «напомню тебе в понедельник в 9» — а напоминания нет (19.10)
                        remind_asked = True
                        log.info("✋ Пообещала напомнить, а напоминание не поставлено — прошу поставить")
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not turn.cancel.is_set() and step < 5 and specs and not saved_checked:
                    fix = reminder_missing(text, turn.full, called) or money_claim(text, step_text, called) \
                        or saved_claim(text, step_text, called) \
                        or action_claim(text, step_text, called) or bare_done(text, step_text, called) \
                        or (task_claim(step_text, called) if any(x.get("name") == "start_task" for x in specs or []) else "")
                    if fix:
                        saved_checked = True
                        log.info("✋ Сказала «готово/записала» или не поставила просимое напоминание — прошу сделать")
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if not calls and not called and not turn.cancel.is_set() and step < 6 and not repeat_checked \
                        and 0 < len(turn.full.strip()) < 160 and _norm_answer(turn.full) in prev_said:
                    # отзыв 17.10 (съёмка): на «расскажи о себе», «подробнее», «что ты умеешь» Лира раз за разом отвечала
                    # «Я Лира.» — модель копировала свои прошлые реплики из разговора. Повтор — просим ответить по существу
                    repeat_checked = True
                    log.info("✋ Ответ слово в слово как недавний («%s») — прошу ответить по существу", turn.full.strip()[:40])
                    fix = (f"Ты слово в слово повторил(а) свой прошлый ответ «{turn.full.strip()[:80]}». Человек спрашивает снова — "
                           "значит, тот ответ его не устроил. Ответь сейчас по существу на его последний вопрос, развёрнуто и "
                           "живо, своими словами; прошлый ответ не повторяй.")
                    msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                    if turn.full.strip() and not turn.full.endswith(" "):
                        turn.full += " "
                    self.set_state("thinking")
                    continue
                if not calls and "show_page" not in called and not turn.cancel.is_set():
                    from quality import page_html_in
                    doc = page_html_in(step_text)
                    if doc and len(doc) > 200:                # страницу написали в ответе — откроем её сами, вслух не читаем
                        try:
                            m_ = re.search(r"<title>(.*?)</title>|<h1[^>]*>(.*?)</h1>", doc, re.S | re.I)
                            ttl = re.sub(r"<[^>]+>", "", (m_.group(1) or m_.group(2)) if m_ else "").strip()[:60] or "Страница"
                            self.toolbox.run("show_page", {"title": ttl, "html": doc})
                            called.add("show_page")
                            log.info("🌐 HTML в ответе — сохранила страницей «%s» и открыла", ttl)
                            note = f" Страница «{ttl}» открыта в браузере."
                            turn.full += note
                        except Exception as e:  # noqa: BLE001
                            log.info("Страница из ответа не открылась: %s", e)
                if not calls and not turn.cancel.is_set() and step < 6 and drew < 2:
                    fix = diagram_missing(text, turn.full + step_text, called)
                    if fix and drew:                 # экзамен 17.10: и после просьбы — «Схема готова.»; второй раз — жёстче
                        fix = ("Схемы в ответе по-прежнему нет. Ответь сейчас ТОЛЬКО блоком ```mermaid\nflowchart LR\n…\n``` — "
                               "без слов до и после.")
                    if fix:
                        drew += 1
                        log.info("✋ Просили схему, а её нет — прошу нарисовать (mermaid)")
                        msgs = msgs + [{"role": "assistant", "content": step_text or "…"}, {"role": "user", "content": fix}]
                        if turn.full.strip() and not turn.full.endswith(" "):
                            turn.full += " "
                        self.set_state("thinking")
                        continue
                if turn.cancel.is_set() or not calls:
                    break
                results = []
                for c in calls:
                    key = json.dumps([c.get("name"), c.get("args")], ensure_ascii=False, sort_keys=True)
                    if key in seen_calls:
                        log.info("↺ %s с теми же параметрами уже был в этом ходе — не повторяю", c.get("name"))
                        results.append("Этот вызов с теми же параметрами уже был — его результат выше. Не повторяй: "
                                       "используй его или попробуй иначе, а если сведений хватает — отвечай.")
                        continue
                    r_ = self._use_tool(turn, c, sentences)
                    seen_calls[key] = True
                    results.append(r_)
                    done_calls.append({"name": c.get("name"), "args": c.get("args") or {}, "result": str(r_)[:300]})
                if turn.cancel.is_set():
                    break
                if any(c.get("name") == "start_task" and not str(r).startswith(("Ошибка", "Инструмент")) for c, r in zip(calls, results)):
                    specs = []                          # задача запущена — делает она; в разговоре только сказать, что взялся
                    log.info("🧵 Задача запущена — в разговоре дальше без действий")
                msgs = msgs + tool_turn_messages(prof, step_text, calls, results)
                if turn.full.strip() and not turn.full.endswith(" "):
                    turn.full += " "
                self.set_state("thinking")
            if not turn.cancel.is_set() and not turn.full.strip() and done_calls and not (set(getattr(turn, "tools_ok", None) or []) - INFO_TOOLS):
                # отчёт №69: прочитала страницу трижды, поискала — и вернула пустоту («Не получилось: пустой ответ»).
                # Сведения уже есть — просим ответить по ним словами, без новых действий (один раз)
                log.warning("Модель замолчала после поиска и чтения — прошу ответить по найденному")
                ask_ = [{"role": "user", "content": "Ответь мне сейчас словами по тому, что уже нашлось выше (страницы, поиск). "
                                                    "Новых действий не будет. Чего-то не хватило — так и скажи и предложи, "
                                                    "что сделать дальше (например, какие разделы сайта открыть)."}]
                try:
                    for kind, val in stream_events(prof, system, msgs + ask_, cancel=turn.cancel, tools=None):
                        if kind == "tools" or turn.cancel.is_set():
                            continue
                        turn.full += val
                        for s_ in split.feed(codef.feed(val)):
                            speak(s_)
                    for s_ in split.feed(codef.flush()) + split.flush():
                        speak(s_)
                except LLMError as e:
                    log.info("И по найденному ответа нет: %s", e)
                if not turn.full.strip() and not turn.cancel.is_set():
                    # и так ничего — не «Не получилось: пустой ответ», а честно: что сделано и что дальше
                    seen = [c["args"].get("url") or c["args"].get("query") for c in done_calls if c["name"] in ("read_webpage", "web_search")]
                    turn.full = ("Я прочитал " + ("страницу " + str(seen[0]) if seen and str(seen[0]).startswith("http") else "найденное")
                                 + ", но ответ не сложился. Спросите точнее — например, какой раздел разобрать или что именно собрать.")
                    turn.full = self._g(turn.full) if hasattr(self, "_g") else turn.full
                    sentences.put(turn.full)
            if remind_asked and "set_reminder" not in called and not turn.cancel.is_set() and not turn.full.rstrip().endswith("?"):
                # попросили поставить — и всё равно нет: человек должен знать, что напоминания нет (а не ждать утром)
                log.warning("Обещала напомнить, но напоминание так и не поставлено — говорю об этом прямо")
                turn.full = (turn.full.rstrip() + " " + REMIND_NOT_SET).strip()
                sentences.put(REMIND_NOT_SET)
            if not turn.cancel.is_set():
                if not turn.full.strip() and getattr(turn, "tools_ok", None) and not (set(turn.tools_ok) & INFO_TOOLS):
                    # действие сделано, а слов модель не добавила; фоновая задача только началась — не «Готово» (отзыв 13.10)
                    turn.full = "Задача запущена — сообщу, когда будет готово." if "start_task" in turn.tools_ok else "Готово."
                    sentences.put(turn.full)
                if not turn.full.strip():
                    raise LLMError("модель вернула пустой ответ")
                log.info("⏱ ответ целиком за %.1f с (%s, %d симв.)", time.monotonic() - t_start, prof.get("model") or "?",
                         len(turn.full))
                early = self._early_done(turn)
                if early:                                 # «Готово!» сразу после start_task — поправиться вслух и в тексте
                    turn.full = turn.full.rstrip() + " " + early
                    sentences.put(early)
                fake = self._fake_reminder(text, turn)
                if fake:
                    turn.full = turn.full.rstrip() + " " + fake
                    self.note(fake)
                turn.full = fem(ACTS_RX.sub("", turn.full)).strip()   # пометку «выполнено инструментами» модель могла повторить
                try:
                    import boundaries
                    if boundaries.refused(turn.full):
                        self.health_count("refused")
                except Exception:  # noqa: BLE001
                    pass
                turn.src_done = self._sources_done(turn, turn.full)
                if not turn.via_job:
                    self.emit("answer", text=turn.full, done=True, model=True, sources=turn.src_done)
                self.health_count("turns")
                self.health_count("net_ok")
                self._contact_maybe()
                self._maybe_learn(text, prof)
        except LLMError as e:
            log.warning("Модель: %s", e)
            self.health_count("net_fail")
            self.health_why(prof, e)
            self.health_problem(f"Модель ({(prof or {}).get('kind') or 'openai'}): {e}")
            msg = f"{e}." if self._cloud_said(prof, e) else f"Не получилось: {e}."   # облако объясняет само
            from cloud import is_cloud, key_gone
            if is_cloud(prof) and key_gone(e) and self._cloud_key_gone():
                msg = "Ключ Dewiar удалён на сайте — теперь думаю по аккаунту dewiar.pro. Повторите, пожалуйста, вопрос."
            turn.error = msg
            self.emit("error", text=msg)
            self.emit("answer", text=msg, done=True)
            turn.full = ""
            sentences.put(msg)
        sentences.put(None)
        speaker.join()
        self.cloud.after_turn(prof)                    # облако по ключу — узнать новый заряд
        if turn.via and turn.via.get("done"):
            try:
                turn.via["done"]("(ответ остановлен)" if turn.cancel.is_set() and not turn.full.strip()
                                 else (turn.full.strip() or getattr(turn, "error", "") or "Не получилось ответить."))
            except Exception:  # noqa: BLE001
                log.exception("отправка ответа в Telegram")
        if turn.report:
            try:
                turn.report(None if turn.cancel.is_set() else bool(turn.full.strip()) and not turn.error,
                            turn.full.strip() or turn.error)
            except Exception:  # noqa: BLE001
                log.exception("итог хода")
        if turn.cancel.is_set():
            return
        if turn.full.strip():
            said = text + (" [к сообщению была приложена картинка]" if images else "")
            acts = list(dict.fromkeys(getattr(turn, "tools_ok", None) or []))
            facts = list(getattr(turn, "facts", None) or [])
            # передал слово явно (call_persona) или специалист, позванный на вопрос, возвращает слово главному — тому
            # его разговор справкой; просто переключились — нет
            hand = getattr(turn, "switch_to", None) or getattr(turn, "back_to", None)
            self.history += [{"role": "user", "content": said},
                             {"role": "assistant", "content": turn.full.strip(), "who": self.s.get("persona"),
                              **({"acts": acts} if acts else {}), **({"facts": facts} if facts else {}), **({"handoff": hand} if hand else {})}]
            self.last_turn_time = time.monotonic()
            self._conv_after()
            if not turn.via:
                self._pause_ok()                           # голосом и без обрыва — добавка к паузе понемногу тает
        follow = 0.0 if turn.via or time.monotonic() < self._echo_until else float(self.s.get("audio", "follow_up_seconds") or 0)
        if getattr(self, "_tray_at", 0) >= getattr(turn, "t0", time.monotonic()):
            # в этом ходе виджет спрятали («Спрякся» — модель поняла и спрятала): не ждать ответа — иначе «Ваша очередь»
            # возвращала виджет на экран (20.10, 22:41: «4 раза просил спрятаться — исчезала и появлялась»)
            follow = 0.0
        self.follow_up_until = time.monotonic() + follow
        opened = False
        with self._turn_lock:
            if self.turn is turn:
                self.turn = None
                self.set_state("listening" if follow > 0 else "idle")
                opened = follow > 0
        if opened and not getattr(turn, "switch_to", None):
            # ход передан человеку: можно отвечать без имени. Окна показывают «Ваша очередь» и сколько осталось,
            # а на слух — мягкий сигнал (истечёт окно — прозвучит «не слушаю», см. engine_audio)
            self.emit("turn", seconds=round(follow, 1))
            if self.s.get("audio", "turn_tone") is not False:
                self.play_tone("turn")
        back = getattr(turn, "back_to", None)
        if back and self.s.get("persona") != back:
            self.switch_persona(back)                 # специалист ответил — снова главный
        pid = getattr(turn, "switch_to", None)
        if pid and not turn.cancel.is_set():
            prev = self.personas.get(self.s.get("persona"))["name"]
            self.switch_persona(pid)
            # новый персонаж откликается сам — своим голосом, зная весь разговор
            self.ask(f"({prev} позвал(а) тебя в разговор. Откликнись одной-двумя короткими фразами от себя и "
                     f"продолжи то, о чём просил пользователь.)", quiet=True)
