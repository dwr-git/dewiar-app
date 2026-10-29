"""Движок Dewiar: слушает, думает, говорит, действует. Класс Engine собран из частей-примесей по темам:
  engine_base.py — общие импорты и помощники; engine_audio.py — слух и голос; engine_answer.py — ответ и отчёты;
  engine_tools.py — инструменты, напоминания, синхронизация, деньги; engine_music.py — дела и музыка;
  engine_brain.py — лёгкий режим, сеть, облако, «мозг»; engine_remote.py — Telegram и MAX без компьютера;
  engine_commands.py — команды интерфейса. Здесь — создание движка и всех его служб, жизненный цикл (потоки),
  подключение по манифесту (provision), обучение произношению имени и события в интерфейс (emit → bridge).
  Части обращаются к полям друг друга через self: новое поле заводите в __init__ здесь."""
from engine_base import *  # noqa: F401,F403 — помощники доступны и снаружи: from engine import Engine, find_name, …
from engine_audio import AudioMixin  # noqa: E402
from engine_answer import AnswerMixin  # noqa: E402
from engine_tools import ToolsMixin  # noqa: E402
from engine_music import MusicMixin  # noqa: E402
from engine_brain import BrainMixin  # noqa: E402
from engine_remote import RemoteMixin  # noqa: E402
from engine_commands import CommandsMixin  # noqa: E402
from engine_intro import IntroMixin  # noqa: E402
from health import HealthMixin  # noqa: E402
from engine_pay import PayMixin  # noqa: E402
from engine_senior import SeniorMixin  # noqa: E402  режимы Лиры и «Для старших» (senior.py)
from engine_watch import WatchMixin  # noqa: E402  «Дозор»: присмотреть и сказать, когда готово (watch.py)
from engine_home import HomeMixin  # noqa: E402  «Дома по Wi-Fi»: синхронизация без dewiar.pro (homehub.py)
from engine_mymusic import MyMusicMixin  # noqa: E402


class Engine(AudioMixin, AnswerMixin, ToolsMixin, MusicMixin, MyMusicMixin, BrainMixin, RemoteMixin, CommandsMixin, IntroMixin, HealthMixin,
             PayMixin, SeniorMixin, WatchMixin, HomeMixin):
    def __init__(self, settings, personas, bridge, wav_input=None, null_player=False, server=False):
        self.s, self.personas, self.bridge = settings, personas, bridge
        if self.s.get("persona") not in {p["id"] for p in personas.all()}:   # выбранного больше нет (стал шаблоном и т. п.)
            from personas import DEFAULT
            self.s.update({"persona": DEFAULT})
        self.wav_input, self.null_player = wav_input, null_player
        self.server = server              # режим сервера (main.py --server): без микрофона и звука, ответы — текстом
        self.state = "idle"
        self.muted = (settings.get("privacy", "mic") == "button"   # замок «Микрофон: только кнопка» (студия → «Безопасность»)
                      or bool(settings.get("ui", "text_mode")))      # текстовый режим (студия → «Чат», 27.10)
        self._mute_pass = False                          # микрофон выключен, но нажали «говорить» — слушаем одну фразу
        self.stopping = threading.Event()
        self.aec = EchoCancel()
        self.capture = None
        self.player = None
        from conversation import Conversation
        self.conv = Conversation(STATE_DIR / "conversation.json")     # длинный разговор: содержание раньше сказанного
        from chatlog import ChatLog
        self.chatlog = ChatLog(STATE_DIR / "chat.jsonl")               # переписка для студии («Чат»): вся лента, как в мессенджере
        self.history = self.conv.restored(float(settings.get("llm", "history_reset_seconds") or 28800))
        from diary import Diary
        from night import NightWatch
        self.night = NightWatch(self)                                 # ночной обход: сбои за сутки, починка, утром — фраза (night.py)
        self.diary = Diary(self, STATE_DIR)                           # дневник: реплики дня → ночная запись и выводы на завтра
        self._brain_lock = threading.Lock()
        self._report_lock, self._report_pending = threading.Lock(), {}
        if not wav_input or os.environ.get("DEWIAR_REPORT_URL"):
            self._install_report_hook()                               # ошибки в журнале → отчёт разработчику (с согласия)
        from soul import Soul
        self.soul = Soul(self, STATE_DIR)                             # душа персонажа (растёт из дневника) и конституция
        self.last_turn_time = 0.0
        self.follow_up_until = 0.0
        self._said = collections.deque(maxlen=40)       # что ассистент сказал вслух (время, текст) — узнать своё эхо
        self._echo_hits, self._echo_until, self._spoke_until = [], 0.0, 0.0
        self._quiet_until = 0.0                          # после «ложного срабатывания» (остановили кнопкой) — не откликаться на голос
        self.wake_time, self._wake_phrase = 0.0, ""
        self.stop_utt = False
        self.stop_time = 0.0
        self.last_speak_end = 0.0
        self.turn = None
        self.turn_n = 0
        self._turn_lock = threading.Lock()
        self._level_t = 0.0
        self.stt_q = queue.Queue()
        self.check_q = queue.Queue()          # фразы без явного имени — ищем в них имя точной моделью
        self._vocab = {}                      # слово -> есть ли в словаре Vosk
        self.utt_id = 0                       # номер текущей фразы (для ранней проверки поверх речи)
        self.barge_sent = -1                  # для какой фразы ушла ранняя проверка
        self.barge_hit = -1                   # в какой фразе ранняя проверка нашла имя
        self.barge_speech = -1                # какую фразу перебили просто речью
        self.barge_done = {}                  # фраза закончилась раньше проверки: id -> звук
        self.hold = None                      # диктовка удержанием (hold_start … hold_end): {"pcm": [кадры], "t0", "max"}
        self._mic_ring = collections.deque(maxlen=40)   # последние ~1,2 с микрофона: удержание начинается с самого нажатия
        self.asr_names = []
        self.status = {"aec": False, "stt": "", "stt_ready": False, "tts": "", "llm": "", "note": "",
                       "input": "", "downloads": {}, "loading": {}}
        self.piper = PiperTTS()
        self.vosk_tts = VoskTTS(MODELS_DIR)
        self._vosk_loading = False
        self.espeak = SapiTTS() if os.name == "nt" else EspeakTTS()      # аварийный голос без скачивания
        self.gigaam = None
        self.vosk_model = None
        self.names_off = False           # модель имён не скачалась — слух работает без имён (кнопка), см. _start_hearing
        self._hearing_started = False
        self.vad = None
        self.vosk_dir = None                  # папка модели Vosk — когда слух поднялся (до того «сохранить персонажа» не падает, №58)
        self.vosk_stt = None
        from lang2 import English
        self.english = English(MODELS_DIR, DATA_DIR)  # второй язык: английская речь (stt.english)
        self.stt = None                  # распознаватель — появится, когда загрузится модель (до этого настройки сохраняются без него)
        self.decoys = []
        self.restart_audio = threading.Event()
        self.pending_confirm = None
        self.meeting = []                                  # программы, которые сейчас слушают микрофон (созвон)
        self._chatter = collections.deque(maxlen=20)        # когда слышали фразы «не мне» — вокруг разговор
        self.vosk_wake_check, self._vosk_wake_word = -1, ""
        self.reminders = Reminders(self._on_reminder)
        self.alarm = None                 # звенящее напоминание: {"item", "done": Event, "since"}
        self._alarm_lock = threading.Lock()
        self.skills = Skills(settings)
        self.plugins = Plugins(settings)                   # плагины: навыки + MCP + настройки + дела (core/plugins.py)
        self.skills.plugins = self.plugins
        self.skills.reload()
        self.mcp = MCPManager(settings, on_change=lambda: self.emit("mcp", status=self.mcp.status()))
        self.toolbox = Toolbox(settings, self.reminders, self.skills, self.mcp)
        from kids import Kids
        self.kids = Kids(settings, STATE_DIR / "kids.json")          # детский режим: время, отчёт, PIN родителя
        self.toolbox.hooks["kids"] = self.kids
        from linkmeta import LinkMeta
        self._linkmeta = LinkMeta(STATE_DIR / "links.json")         # ссылки в заметках — карточками (save_link, link_meta)
        self.toolbox.hooks["linkmeta"] = self._linkmeta
        from senior import Senior
        self.senior = Senior(settings, STATE_DIR / "senior.json")    # режим «Для старших»: лекарства, «всё хорошо», мошенники
        from watch import Watches
        self.watches = Watches(STATE_DIR / "watch.json")             # «Дозор»: экран, папка, страница — сказать, когда готово
        self.toolbox.hooks["watch"] = self
        if self.s.get("tts", "engine") == "piper" and not self.s.get("tts", "v2"):
            # разовый перенос старых настроек: русские голоса Vosk TTS заметно лучше Piper (Piper остаётся запасным);
            # метка v2 — чтобы не перебить выбор Piper, сделанный позже вручную. №226 (24.10): на слабом компьютере
            # (лёгкий режим) Vosk TTS синтезирует фразу 17–36 с — там Piper оставляем
            self.s.update({"tts": {"engine": "piper" if self.s.get("device", "light") else "vosk", "v2": True}})
        if self.s.get("audio", "barge_in") == "wakeword" and not self.s.get("audio", "barge_v2"):
            # разовый перенос: перебивать можно просто речью, а не только именем; метка barge_v2 — сделано один раз
            self.s.update({"audio": {"barge_in": "smart", "barge_v2": True}})
        self.toolbox.hooks["call_persona"] = self._tool_call_persona
        self.workspace = Workspace(settings)
        self.pad = Pad(self.workspace, settings, emit=self.emit, share=lambda rel, paths: self.note_files_out(rel, paths))   # блокнот у виджета
        self.toolbox.hooks["workspace"] = self.workspace
        self.workspace.mem_owner = self.mem_owner          # своя память у персонажа (0.56): чья память сейчас
        self.toolbox.hooks["server"] = bool(server)         # сервер: без экрана и звука — экранные инструменты выключены
        self.skills.set_folder(self.workspace.root / "Навыки")    # свои навыки — видны в папке ассистента
        self.toolbox.hooks["persona_name"] = lambda: self.personas.get(self.s.get("persona"))["name"]
        self.reminders.on_change = self._on_reminders_changed
        self.updater = Updater(settings, VERSION, STATE_DIR, emit=self.emit)
        self.on_quit = None
        self._blind = set()                         # модели, которые не видят картинок (узнаём по первой ошибке)
        self._listen_peak, self._listen_vad = 0.0, 0.0
        self._probing = set()
        self._now_saying = ""
        self._pending_media_stop = 0.0
        self.task_answer_until = 0.0
        self.tasks = TaskManager(self)
        self.toolbox.hooks["tasks"] = self.tasks
        self.toolbox.hooks["remote_task"] = lambda on, title, goal, if_off="": self.remote_task(on, title, goal, if_off)   # «на рабочем компьютере…»
        from account import Account
        self.account = Account()
        self.toolbox.hooks["account"] = self.account
        from knowledge import Knowledge
        self.knowledge = Knowledge(self.workspace, STATE_DIR / "knowledge.json", folders=lambda: self.s.get("knowledge", "folders") or [],
                                   extra=self._persona_folders)
        self.toolbox.hooks["knowledge"] = self.knowledge
        self.toolbox.hooks["sources"] = self._turn_sources          # найденные документы — источниками под ответом
        threading.Thread(target=self.knowledge.watch, name="knowledge-folders", daemon=True).start()
        from writing import Writing
        import knowledge as _kn
        self.writing = Writing(lambda: self.s.get("knowledge", "folders") or [], STATE_DIR / "writing.json",
                               extract=_kn.extract, walk=self.knowledge._walk)   # «Пишу»: сколько написано за день (0.68)
        self.toolbox.hooks["writing"] = self.writing
        threading.Thread(target=self._writing_loop, name="writing", daemon=True).start()
        from prompter import Prompter
        self.mic_voice_t = 0.0                             # когда микрофон последний раз слышал речь (monotonic)
        self.prompter = Prompter(self)                     # суфлёр на встречах (core/prompter.py, окно ui/prompter.html)
        from mail import Mail
        self.mail = Mail(workspace=self.workspace)
        self.toolbox.hooks["mail"] = self.mail
        from recall import Recall
        from obsidian import Obsidian
        self.obsidian = Obsidian(settings, self.workspace, STATE_DIR, emit=self.emit)
        self.workspace.vault_fn = self.obsidian.vault
        self.obsidian.index_info = self._obsidian_index_info      # оглавление «DEWIAR.md»: имя, дни дневника
        self.recall = Recall(lambda: self.workspace.root, self.obsidian.search_root)
        self.toolbox.hooks["recall"] = self.recall
        self.toolbox.hooks["chatlog"] = self.chatlog              # «вспомни, что я говорил…» — и по прошлым разговорам
        from telegram import Telegram
        from maxbot import Max, Messengers
        self.telegram = Telegram(on_message=lambda k, d: self._on_messenger(self.telegram, k, d))
        self.max = Max(on_message=lambda k, d: self._on_messenger(self.max, k, d))
        self.chat = Messengers(self.telegram, self.max)        # Telegram и MAX вместе: уведомления — во все подключённые
        self.toolbox.hooks["telegram"] = self.chat
        from pbot import PersonaBot
        self.pbot = PersonaBot(self)                            # «Бот персонажа»: публичный бот, отвечает всем (0.67)
        from servers import Servers
        self.servers = Servers()
        self.toolbox.hooks["servers"] = self.servers
        from radio import Radio
        from eyes import ffmpeg_path
        import tools as _tools
        self.radio = Radio(lambda: Player(device=self.player.device if self.player else "", null=self.null_player), ffmpeg_path)
        try:
            self.radio.set_volume(self.s.get("audio", "radio_volume", default=0.8))
        except (TypeError, ValueError):
            pass
        self.toolbox.hooks["radio"] = self.radio
        _tools.RADIO[:] = [self.radio]
        from money import Money
        from settings import CONFIG_DIR as _CFG
        self.money = Money(_CFG / "money.json", self.workspace, self._default_currency)
        self.toolbox.hooks["money"] = self.money
        from care import Care
        self.care = Care(STATE_DIR / "care.json")        # «Заботливая память»: прошло важное — спросить, как прошло (care.py)
        from sync import Sync
        self.sync = Sync(self)                         # телефон ↔ компьютер через облако Dewiar
        from close import Close
        self.close = Close(self)                       # «Близкие»: переписка с помощниками других людей (сквозное шифрование)
        from family import Family
        self.family = Family(self, STATE_DIR / "family.json")   # семейный бюджет: траты и общие платежи с близкими
        from team import Team
        self.team = Team(self, STATE_DIR / "team.json", _CFG / "team_bot.json", personal=self.telegram, personal_max=self.max)   # «Поручения» сотрудникам в Telegram
        self.toolbox.hooks["team"] = self.team
        from clients import Clients
        self.clients = Clients(STATE_DIR / "clients.json", self.reminders, emit=lambda *a, **k: self.emit("clients"))   # «Клиенты» — личная CRM
        self.clients.currency = self._default_currency           # сделки — в валюте «Денег»
        self.toolbox.hooks["clients"] = self.clients
        from course import Course
        self.course = Course(STATE_DIR / "course.json", self.emit)   # курс «Неделя с Лирой»: шаги засчитываются сами
        self.money.on_change = self.sync.soon.set
        self.money.on_add = self.family.share_spend    # расход — в общий семейный бюджет (если семья есть и делимся)
        self.money.on_delete = self.family.delete_spend
        from payments import Payments
        self.payments = Payments(_CFG / "payments.json", self.workspace)   # «Платежи»: счета, оплаты, сроки (payments.py)
        self.payments.on_change = self.sync.soon.set     # и между компьютерами (виды bill, pay, payfile в sync.py; 27.10)
        from done import Done
        self.done = Done(_CFG / "done.json")             # «Дела»: сделанное и достижения (done.py), синхронизация — вид «done»
        self.done.on_change = self.sync.soon.set
        self.toolbox.hooks["done"] = self.done
        self.toolbox.hooks["engine"] = self
        self.toolbox.hooks["close"] = self.close
        import guard
        from pc import Power
        guard.WORKSPACE[:] = [self.workspace.root]
        self.power = Power(env=_tools.desktop_env)
        self.toolbox.hooks["power"] = self.power
        from vault import Vault
        self.vault = Vault(_CFG / "vault.bin", _CFG / "vault.key")
        from synckey import SyncKey
        self.sync_key = SyncKey(_CFG / "sync.key", _CFG / "vault.key")     # сквозное шифрование синхронизации (sync.e2e)
        from smarthome import CLIENT_ID as _YCID, Home
        self.home = Home(_CFG / "smarthome.json", lambda: (self.s.get("smarthome", "client_id") or _YCID).strip())
        from homeassistant import HAHome, Homes
        self.ha = HAHome(_CFG / "homeassistant.json")          # Home Assistant — второй дом (адрес и токен, файл 0600)
        self.homes = Homes(self.ha, self.home)                 # оба как один: быстрые команды и инструмент smart_home
        self.toolbox.hooks["home"] = self.homes
        from calsync import Calendars
        self.calendars = Calendars(self.s, STATE_DIR / "calendars")
        from cloud import Cloud
        self.cloud = Cloud(self.s, self.emit)
        self._net_try = ""                         # сайт, на который сейчас входим (ещё не сохранён в аккаунте)
        self._tg_sync_soon = threading.Event()     # напоминания изменились — сразу сообщить серверу Telegram
        self._key_gone_lock = threading.Lock()     # ключ dw- удалён — на аккаунт переходим один раз
        import net
        net.bind(self._net_conf)
        # запасной путь сработал (dewiar.pro напрямую не открылся) — сказать один раз, в чат: что случилось и что делать
        net.on_reserve = lambda h: self.chat.notify(
            f"{h} сейчас не открывается напрямую — похоже, его не пускает провайдер или сеть. Я перешёл на запасной путь "
            "(прокси Dewiar): облако, вход и обновления работают как обычно. Выключить: студия → «Dewiar.pro» → «Сеть».")
        lan = self.s.get("net", "lan") or {}
        net.set_lan(lan.get("public", ""), lan.get("base", ""), lan.get("id", ""))   # дома — напрямую с первого запроса
        self.cloud.on_low = lambda c: self.chat.notify(
            ("Заряд Dewiar Облака закончился — ассистент не сможет отвечать, пока вы не пополните. " if c.get("empty") else
             f"Заряд Dewiar Облака: {c.get('percent')}% — хватит примерно на {c.get('turns')} ответов. ")
            + (c.get("topup") or "") + "\nПополнить: студия → «Мозг» → «Пополнить».")
        self.cloud.on_key_gone = self._cloud_key_gone
        self.toolbox.hooks["calendars"] = self.calendars
        self.toolbox.hooks["dewiar_web"] = self._dewiar_web          # поиск и страницы через сервер Dewiar, если сеть режет
        from backup import Backup
        from version import VERSION as _V
        self.backup = Backup(_CFG, STATE_DIR, self.workspace.root, self.vault, _V)
        from music import Catalog
        self.music = Catalog(lambda: self.s.get("radio_url") or "", STATE_DIR / "radio.json", DATA_DIR / "radio.json",
                             custom_fn=lambda: self.s.get("radio_custom") or [])
        from radio import Logos, StationHealth
        self.radio_health = StationHealth(STATE_DIR / "radio_health.json")      # какие станции у вас реально играют
        self.radio_logos = Logos(STATE_DIR / "radio_logos.json")              # значки станций для вкладки «Радио»
        from latency import Latency
        self.lat = Latency()                                                  # «Голос без пауз»: от конца фразы до звука
        from council import Council
        self.council = Council(self)                                          # «Совет ИИ»: персонажи обсуждают вопрос
        self.toolbox.hooks["music"] = self.music
        self.music.data()                                 # свежий список станций с сайта — в фоне, сразу при запуске
        self._music_app = ("", 0.0)                       # какое музыкальное приложение открывали последним и когда
        self.toolbox.hooks["music_app"] = lambda name: setattr(self, "_music_app", (name, time.monotonic()))
        self.toolbox.hooks["music_pref"] = lambda: self._music_service() if self._music_service() == "yandex" else ""
        self._music_asked = 0.0
        self._mine_init(STATE_DIR)                        # своя папка с музыкой и ведущий (engine_mymusic.py)
        self.radio.on_change = lambda: self.emit("radio", **self.radio.status())
        try:
            self.workspace.ensure()
            self.workspace.sync_reminders(self.reminders.items)
        except OSError as e:
            log.warning("Папка ассистента недоступна: %s", e)
        self.pending_import = None
        self.calib = None
        from voiceprint import Voiceprints
        self.voiceprints = Voiceprints()
        self.voiceprints.sensitivity = float(self.s.get("audio", "name_sensitivity") or 1.0)

    # ---------- жизненный цикл ----------

    def start(self):
        """Студия и настройки доступны сразу; слух запускается, как только готова модель Vosk."""
        if self.server:
            log.info("Режим сервера: без микрофона и звука — задачи, синхронизация, Telegram и напоминания работают")
            self.status["note"] = "Режим сервера: без микрофона и звука"
            self._start_background()
        self.health_begin()                                    # «Здоровье»: время запуска, нагрузка, пульс (core/health.py)
        self._auto_provision()
        self._device_check()
        if not self.wav_input and not getattr(self, "server", False):
            threading.Thread(target=self._memory_watch, name="memory", daemon=True).start()
        self.mcp.reconcile()
        threading.Thread(target=self.updater.loop, args=(self.stopping,), name="updates", daemon=True).start()
        threading.Thread(target=self.obsidian.loop, args=(self.stopping,), name="obsidian", daemon=True).start()
        if self.s.get("sync", "enabled") is not False and not self.wav_input:
            threading.Thread(target=self.sync.loop, args=(self.stopping,), name="sync", daemon=True).start()
        if not self.wav_input:
            threading.Thread(target=self.close.loop, args=(self.stopping,), name="close", daemon=True).start()
        self.home_boot()                                   # «Дома по Wi-Fi» — если включён (engine_home.py)
        threading.Thread(target=self._start_hearing, name="hearing-init", daemon=True).start()
        threading.Timer(4.0, self.probe_tools_bg).start()     # умеет ли модель действия — узнаём заранее
        self.telegram.start()
        if (self.s.get("features") or {}).get("team") and self.team.connected():
            self.team.start()                                  # «Команда»: бот компании — только если раздел включён
            threading.Timer(30.0, self.team_changed).start()   # свежая доска своему телефону руководителя
        self.reminders.skip_late = self._tg_fired_elsewhere            # не повторять напоминание, пришедшее с сервера
        self.reminders.on_wake = self._reminders_wake                  # проснулись — сначала сверка с телефоном (28.10)
        self.sync.on_pass = self.reminders.release_hold                 # сверка прошла — опоздавшие звенят сразу, не через 90 с
        threading.Thread(target=self._tg_sync_loop, name="tg-sync", daemon=True).start()
        threading.Thread(target=self._morning_loop, name="morning", daemon=True).start()
        threading.Thread(target=self._senior_loop, name="senior", daemon=True).start()   # «Для старших»: сводка близким
        threading.Thread(target=self._watch_loop, name="watch", daemon=True).start()     # «Дозор»   # «Утро с Лирой» — своему телефону
        threading.Thread(target=self._radio_check_loop, name="radio-check", daemon=True).start()
        threading.Thread(target=self._diary_loop, name="diary", daemon=True).start()
        threading.Thread(target=self._pay_loop, name="payments", daemon=True).start()
        threading.Thread(target=self._welcome_loop, name="welcome", daemon=True).start()
        threading.Thread(target=self.intro_auto, name="intro-wait", daemon=True).start()
        threading.Thread(target=self._join_loop, name="join", daemon=True).start()
        threading.Thread(target=lambda: self.stopping.wait(2) or self.auto_join(), name="auto-join", daemon=True).start()
        threading.Thread(target=self._brain_watch, name="brain", daemon=True).start()
        if not self.wav_input:
            threading.Thread(target=self._ann_loop, name="announcements", daemon=True).start()
        self.max.start()
        self.pbot.start()

    def _writing_loop(self):
        """«Пишу»: раз в 10 минут пересчитать прирост слов в своих текстах (дёшево: только изменившиеся файлы)."""
        time.sleep(40)
        while True:
            try:
                if self.s.get("knowledge", "folders"):
                    self.writing.scan()
            except Exception:  # noqa: BLE001
                log.exception("«Пишу»: подсчёт")
            time.sleep(600)

    def _ann_fetch(self):
        """Объявления для всех с облака (news.announcements); новое (номер больше ui.ann_seen и ещё не объявленное) —
        событие ann: виджет показывает строку «📣 …», студия — окно с фото, текстом и ссылкой (один раз)."""
        import news
        try:
            self._ann = news.announcements(self.s.get("cloud", "url") or "")
        except Exception as e:  # noqa: BLE001 — нет связи: в следующий раз
            log.debug("объявления: %s", e)
            return
        fresh = [i for i in self._ann if i["id"] > int(self.s.get("ui", "ann_seen") or 0)]
        if fresh and fresh[0]["id"] > getattr(self, "_ann_told", 0):
            self._ann_told = fresh[0]["id"]
            self.emit("ann", item=fresh[0])

    def _ann_loop(self):
        if self.stopping.wait(25):
            return
        import news
        while not self.stopping.is_set():
            self._ann_fetch()
            if self.stopping.wait(news.ANN_EVERY):
                return

    def _start_hearing(self):
        """Поток hearing-init: ждёт модель Vosk (без неё нет слова запуска; повтор раз в минуту), затем
        поднимает слух и запускает потоки audio, stt, name-check и фоновые службы."""
        from vosk import Model, SetLogLevel
        SetLogLevel(-1)
        self._load("hear", "Готовлю слух")
        from listen import VOSK_NAME
        if not ((MODELS_DIR / VOSK_NAME / "am").exists() or (DATA_DIR / f"{VOSK_NAME}.zip").exists()):
            # модель имён ещё качать (первый запуск, 45 МБ): микрофон по кнопке — сразу, имя — когда докачается
            # (на медленном интернете ждать её, чтобы просто нажать на микрофон, — минуты; CI 19.10)
            self.names_off = True
            self._hearing_up()
        repaired = False
        while not self.stopping.is_set():
            try:
                vosk_dir = ensure_vosk(DATA_DIR, MODELS_DIR, on_status=self.note, mirror=self._mirror_url("vosk_small"))
            except Exception as e:  # noqa: BLE001
                log.warning("Модель имён (Vosk) пока не скачалась: %s", e)
                self._load("hear", "Модель имён не скачалась — имя пока не слышу, микрофон по кнопке работает")
                if not self.names_off:
                    # без модели имён микрофон всё равно работает: кнопка, удержание, выбранный распознаватель
                    # (CI и отчёты 19.10: без неё не работала даже кнопка). Имена включатся, когда модель докачается
                    self.names_off = True
                    self._hearing_up()
                self.note("Имя пока не слышу — не скачалась модель распознавания имён (проверьте интернет). "
                          "Нажмите на микрофон и говорите — это работает. Повторю скачивание через минуту.")
                self.stopping.wait(60)
                continue
            try:
                self.vosk_model = Model(str(kaldi_path(vosk_dir)))
                break
            except Exception as e:  # noqa: BLE001
                # модель на месте, а Kaldi её не открыл: распакована не до конца (раз — распакуем заново) или путь,
                # который он не может прочесть. Раньше исключение убивало поток слуха без следа в журнале — «Готовлю
                # слух» навсегда, не работала даже кнопка микрофона (отчёты №120–125, 19.10: «глухой»)
                log.warning("Модель имён (Vosk) не загрузилась из %s: %s", vosk_dir, e)
                if not repaired:
                    repaired = True
                    import shutil
                    shutil.rmtree(vosk_dir, ignore_errors=True)
                    continue
                self._load("hear", "Модель имён не загрузилась — имя пока не слышу, микрофон по кнопке работает")
                self.note("Имя пока не слышу — не загрузилась модель распознавания имён. Нажмите на микрофон и говорите — это работает.")
                if not self.names_off:
                    self.names_off = True
                    self._hearing_up()
                return
        else:
            return
        self.note("")
        self.vosk_dir = vosk_dir
        self.vosk_stt = VoskSTT(self.vosk_model)
        if self.names_off:
            log.info("🎤 Модель имён докачалась — снова слышу имя")
        self.names_off = False
        self._hearing_up()

    def _hearing_up(self):
        """Поднять слух (один раз: аудиопоток, распознавание, проверка имён, фоновые службы), а при повторном вызове —
        только пересобрать поиск имён и движки (докачалась модель Vosk)."""
        if not self.decoys:
            self.decoys = (DATA_DIR / "decoys.txt").read_text(encoding="utf-8").split()
        if self.vad is None:
            self.vad = SileroVAD(DATA_DIR / "silero_vad.onnx")
        self.build_spotter()                 # без модели имён — NoSpotter и имена по распознанной фразе
        if self.vosk_model is not None:
            self._loaded("hear")
        self.apply_engines()
        if self._hearing_started:
            return
        self._hearing_started = True
        if not self.server:          # сервер: распознавание (голосовые из Telegram) и голос есть, микрофона и динамика нет
            self._audio_thread = threading.Thread(target=self._audio_loop, name="audio", daemon=True)
            self._audio_thread.start()
            threading.Thread(target=self._stt_worker, name="stt", daemon=True).start()
            threading.Thread(target=self._check_worker, name="name-check", daemon=True).start()
            threading.Thread(target=self._meeting_watch, name="meeting", daemon=True).start()
        self.health_mark("ready")                              # слух работает — можно звать по имени
        if not self.server:          # сервер запустил их сразу (start): календари и копии не ждут модель слуха
            self._start_background()
        threading.Thread(target=self._background_loads, name="loader", daemon=True).start()

    def _start_background(self):
        """Фоновые службы: резервная копия, календари, облако."""
        threading.Thread(target=self._auto_backup, name="backup", daemon=True).start()
        threading.Thread(target=self._calendar_loop, name="calendars", daemon=True).start()
        threading.Thread(target=self.cloud.loop, name="cloud", daemon=True).start()

    def shutdown(self):
        self.stopping.set()
        self.telegram.stop()
        self.team.stop()
        self.max.stop()
        self.mcp.close()
        self.cancel_turn()
        if self.capture:
            self.capture.close()
        t = getattr(self, "_audio_thread", None)
        if t and t.is_alive():
            t.join(timeout=4)      # дать аудиопотоку выйти до завершения интерпретатора (иначе падает onnxruntime)
        self.aec.teardown()

    # ---------- подключение и настройки ----------

    def _auto_provision(self):
        """Первый запуск: настройки из пакета. Каждый запуск: тихо обновиться с сервера, откуда подключались."""
        snap = self.s.snapshot()
        m = provision.packaged_manifest()
        rev = int((m or {}).get("revision") or 0)
        done_rev = int((snap.get("provision") or {}).get("packaged_rev") or 0)
        if m and not provision.is_fresh(snap) and m.get("apply_on_upgrade") and rev > done_rev:
            # Обновление пакета принесло сервер Dewiar. Уже настроенному пользователю включаем его,
            # только если сервер реально отвечает, — иначе рабочая модель сменилась бы на недоступную.
            self.s.update({"provision": {"packaged_rev": rev}})
            threading.Thread(target=self._upgrade_provision, args=(m,), daemon=True).start()
        elif rev and rev > done_rev:
            self.s.update({"provision": {"packaged_rev": rev}})
        if provision.is_fresh(snap):
            if m:
                try:
                    patch, skills = provision.to_patch(m)
                    provision.apply_patch(self.s, patch)
                    self._install_skills(skills)
                    log.info("Применены настройки из пакета: %s", m.get("name", ""))
                except provision.ProvisionError as e:
                    self.status["note"] = f"{m.get('name', 'Сервер')}: введите код доступа в студии → «Подключение»"
                    self.pending_import = m
                    log.info("Настройки из пакета ждут код доступа: %s", e)
        src = self.s.get("provision") or {}
        if src.get("url") and not src.get("url", "").startswith("file:"):
            threading.Thread(target=self._refresh_provision, args=(src,), daemon=True).start()

    def _upgrade_provision(self, m):
        try:
            patch, skills = provision.to_patch(m)
        except provision.ProvisionError as e:
            log.info("Настройки из пакета не применены: %s", e)
            return
        new_active = (patch.get("llm") or {}).get("active")
        prof = (patch.get("_llm_profiles") or {}).get(new_active)
        reachable = False
        if prof:
            try:
                list_models(prof, timeout=3)
                reachable = True
            except LLMError as e:
                log.info("Сервер из обновления сейчас не отвечает (%s) — добавляю, но не включаю", e)
        if not reachable:
            patch.get("llm", {}).pop("active", None)
            patch.pop("persona", None)
        provision.apply_patch(self.s, patch)
        self._install_skills(skills)
        name = m.get("name", "сервер Dewiar")
        self.note(f"Подключён {name}. Прежние модели — в студии, раздел «Мозг»." if reachable else
                  f"{name} сейчас недоступен — он добавлен в студию, раздел «Мозг»; включите, когда будет связь.")
        log.info("Обновление: %s %s", name, "подключён" if reachable else "добавлен, но не включён (не отвечает)")
        self.apply_engines()
        self.emit("settings", settings=self.s.snapshot())

    def _refresh_provision(self, src):
        """Сервер мог сменить адреса или модель — подхватываем мозг, слух, голос и навыки.
        MCP-программы и разрешения автоматически не меняем: для них нужно явное согласие."""
        try:
            m = provision.fetch_manifest(src["url"])
        except provision.ProvisionError as e:
            log.info("Обновление настроек с сервера не удалось: %s", e)
            return
        safe = {k: v for k, v in m.items() if k in ("dewiar", "name", "url", "key", "llm", "stt", "tts", "skills")}
        try:
            patch, skills = provision.to_patch(safe, src.get("key", ""))
        except provision.ProvisionError:
            return
        before = json.dumps({k: self.s.get(k) for k in ("llm", "stt", "tts")}, sort_keys=True)
        provision.apply_patch(self.s, patch)
        after = json.dumps({k: self.s.get(k) for k in ("llm", "stt", "tts")}, sort_keys=True)
        self._install_skills(skills, only_new=True)
        if before != after:
            log.info("Настройки обновлены с сервера %s", m.get("name", ""))
            self.apply_engines()
            self.emit("settings", settings=self.s.snapshot())

    def _install_skills(self, skills, only_new=False):
        for sk in skills or []:
            name = sk.get("name")
            if only_new and name in self.skills.items:
                continue
            try:
                self.skills.install_url(sk["url"])
            except (SkillError, KeyError) as e:
                log.warning("Навык %s не установлен: %s", name or sk, e)

    def _import(self, a):
        """Источник импорта: data (разобранный JSON), path (файл) или address (сервер/ссылка)."""
        if a.get("address"):
            m = provision.fetch_manifest(a["address"])
        elif a.get("path"):
            from pathlib import Path
            m = json.loads(Path(a["path"]).expanduser().read_text(encoding="utf-8"))
            m.setdefault("url", "")
        else:
            m = a.get("data")
        provision.validate(m)
        self.pending_import = m
        return provision.preview(m, self.s.snapshot())

    def _apply_import(self, a):
        m = self.pending_import
        if not m:
            raise ValueError("сначала выберите, что импортировать")
        patch, skills = provision.to_patch(m, a.get("key", ""))
        mcp_new = (patch.pop("mcp", {}) or {}).get("servers") or {}
        provision.apply_patch(self.s, patch)
        if mcp_new:
            cur = self.s.get("mcp", "servers") or {}
            cur.update(mcp_new)
            self.s.update({"mcp": {"servers": cur}})
        self._install_skills(skills)
        self.pending_import = None
        self.note("")
        self.apply_engines()
        self.build_spotter()
        self.mcp.reconcile()
        if isinstance(self.stt, GigaAMSTT) and not self.stt.ready and not self.stt.loading:
            threading.Thread(target=self._background_loads, daemon=True).start()
        snap = self.s.snapshot()
        self.emit("settings", settings=snap)
        self.emit("personas", personas=self.personas.public())
        self.emit("persona", persona=snap["persona"])
        return snap

    def _draft_skill(self, idea):
        """Черновик навыка по описанию словами — пишет активная модель."""
        prof = self.s.active_llm()
        if not prof:
            raise ValueError("сначала подключите модель")
        if len(idea.strip()) < 8:
            raise ValueError("опишите подробнее, что должен уметь навык")
        tools = ", ".join(f"{t['name']} ({t['description'][:60]})" for t in self.toolbox.specs() if not t["name"].startswith("mcp_"))
        system = ("Ты составляешь навык для голосового ассистента Dewiar в формате Agent Skills (SKILL.md). "
                  "Ответь ТОЛЬКО JSON-объектом без пояснений: {\"name\": \"латиница-через-дефис\", "
                  "\"description\": \"одна-две фразы: что делает и КОГДА применять (какими словами просят)\", "
                  "\"body\": \"пошаговые инструкции ассистенту на русском, markdown\"}. "
                  "Инструкции пиши для самого ассистента: какие шаги, какие инструменты вызывать, как коротко "
                  "ответить голосом. Доступные инструменты: " + tools)
        text = "".join(stream_chat(dict(prof, max_tokens=1500, disable_thinking=True), system,
                                   [{"role": "user", "content": idea}]))
        m = re.search(r"\{.*\}", text, re.S)
        try:
            d = json.loads(m.group(0)) if m else {}
        except ValueError:
            d = {}
        if not d.get("body"):
            raise ValueError("модель не смогла составить навык — попробуйте описать иначе")
        return {"name": d.get("name", ""), "description": d.get("description", ""), "body": d.get("body", "")}

    # ---------- «Научить произношению» ----------

    def _first_name_token(self, text):
        """Первое слово фразы (после «эй» и т.п.); если оно частое или короткое — склейка двух слов."""
        words = [_norm(w) for w in _WORD.findall(text)]
        if words and words[0] in INTERJECTIONS:
            words = words[1:]
        if not words:
            return ""
        common = set(self.decoys) | set(STOP_WORDS) | INTERJECTIONS
        w = words[0]
        if (w in common or len(w) < 4) and len(words) > 1:
            w = words[0] + words[1]
        return "" if (w in common or len(w) < 4) else w

    def _calib_sample(self, pcm):
        """Один образец имени для «Научить произношению»: распознаём его GigaAM и/или удалённым распознавателем.
        Набрав c["need"] образцов, сохраняем в персонаже написания, повторившиеся хотя бы дважды (вместе
        с прежними, не больше 6 на распознаватель), и обучаем отпечаток голоса; итог — событие «calib»."""
        c = self.calib
        if c is None:
            return
        idx = len(c["samples"]) + 1
        if idx > c["need"]:
            return
        c["samples"].append(pcm)
        got = {}
        recs = []
        if self.gigaam is not None and self.gigaam.ready:
            recs.append(("gigaam", self.gigaam))
        if isinstance(self.stt, RemoteSTT):
            recs.append(("remote", self.stt))
        for key, rec in recs:
            try:
                got[key] = rec.transcribe(pcm[:int(3.0 * RATE) * 2]).strip()
            except Exception as e:  # noqa: BLE001
                got[key] = ""
                log.warning("Калибровка: %s не распознал: %s", key, e)
        c.setdefault("texts", []).append(got)
        log.info("🎓 Образец %d: %s", idx, got)
        self.emit("calib", step="sample", n=idx, need=c["need"], heard=got, name=c["name"])
        if idx < c["need"]:
            return
        self.calib = None
        heard, skipped = {}, []
        for key in {k for t in c["texts"] for k in t}:
            toks = [self._first_name_token(t.get(key, "")) for t in c["texts"]]
            raw = [t.get(key, "") for t in c["texts"]]
            ok = sorted({t for t in toks if t and toks.count(t) >= 2})     # только устойчивое написание
            if ok:
                heard[key] = ok
            elif any(raw):
                skipped.append(f"{key}: «{raw[0]}» — слишком частое или короткое слово")
        prev = self.personas.get(c["pid"]).get("heard") or {}
        for k, v in prev.items():
            heard[k] = sorted(set(heard.get(k, [])) | set(v))[-6:]
        self.personas.set_heard(c["pid"], heard)
        try:
            vp = self.voiceprints.train(c["pid"], c["samples"])
        except ValueError as e:
            self.calib = None
            self.emit("calib", step="error", error=str(e), name=c["name"])
            self.set_state("idle")
            return
        self.build_spotter()
        self.note("")
        self._names_note()
        self.emit("personas", personas=self.personas.public())
        self.emit("calib", step="done", heard=heard, skipped=skipped, name=c["name"], voiceprint=vp)
        self.set_state("idle")
        log.info("🎓 %s теперь узнаётся как: %s", c["name"], heard)

    # ---------- события наружу ----------

    def emit(self, type_, **kw):
        if type_ == "wake":
            self._ui_wake()                                # имя услышано, а виджета нет (закрыт, упал) — открыть
        if type_ == "answer" and not kw.pop("model", False) and kw.get("text"):
            kw["text"] = self._g(kw["text"])               # быстрые ответы без модели — в роде персонажа
        self.bridge.broadcast(dict(kw, type=type_))
        self._turn_step(type_, kw)
        if (type_ == "heard" or (type_ == "answer" and kw.get("done"))) and kw.get("text") and getattr(self, "chatlog", None) is not None:
            self._chat_add(type_, kw)

    def _turn_step(self, type_, kw):
        """Что сделано за ход — к ответу в ленту «Чата» (YouTube 26.10: «в чате не было информации о выполнении команды»):
        готовые и неудачные действия (событие tool) и вопросы «выполнить?» с ответом. Новый вопрос человека — с чистого листа."""
        try:
            if type_ == "heard":
                self._turn_tools = []
                return
            tl = getattr(self, "_turn_tools", None)
            if tl is None:
                tl = self._turn_tools = []
            if type_ == "tool" and kw.get("status") in ("done", "error") and kw.get("title"):
                st = {"t": str(kw["title"])[:140], "s": kw["status"]}
                if kw.get("error"):
                    st["e"] = str(kw["error"])[:200]
                tl.append(st)
            elif type_ == "confirm":
                tl.append({"t": "Разрешение на «" + str(kw.get("text") or "действие").strip().rstrip("?")[:160] + "»", "s": "ask"})
            elif type_ == "confirm_done" and tl and tl[-1].get("s") == "ask":
                tl[-1]["s"] = "yes" if kw.get("ok") else "no"
            del tl[:-12]
        except Exception:  # noqa: BLE001
            pass

    def show_media(self, items, caption=""):
        """Картинки к рассказу (show_images): сразу в виджет и окно чата (событие media), а к готовому ответу — в ленту
        «Чата» (миниатюры со ссылкой на источник)."""
        self.emit("media", items=items, caption=caption, source="pics")
        prev = getattr(self, "_turn_media", None)
        keep = prev[1] if prev and time.monotonic() - prev[0] < 300 else []
        self._turn_media = (time.monotonic(), (keep + list(items))[:12])

    def _chat_add(self, type_, kw):
        """Реплика — в ленту «Чата» студии (chatlog.py) и сразу в открытое окно чата (событие chat)."""
        try:
            text, via, att = str(kw["text"]), None, None
            if type_ == "heard" and text.startswith("✉ "):
                text, via = text[2:], "message"
            if type_ == "heard" and "\n\nВложения:" in text:      # вложения — карточками в ленте, а не текстом файлов
                text = text.split("\n\nВложения:")[0]
                at, saved = getattr(self, "_chat_att", None) or (0, [])
                if saved and time.monotonic() - at < 120:
                    att, self._chat_att = saved, None
                from engine_answer import ATT_DEFAULT_Q
                if text.strip() == ATT_DEFAULT_Q:
                    text = ""
            if type_ == "answer" and kw.get("sources"):    # документы, по которым ответ, — к нему в ленту (открыть)
                att = list(kw["sources"])
            if type_ == "answer" and not att:              # картинки, показанные в этом ответе, — к нему в ленту
                at, media = getattr(self, "_turn_media", None) or (0, [])
                if media and time.monotonic() - at < 300:
                    att, self._turn_media = [{"kind": "image", "name": m.get("title", ""), "thumb": m.get("src", ""), "url": m.get("page", ""),
                                              "full": m.get("full", ""), "author": m.get("author", ""), "license": m.get("license", ""),
                                              "site": m.get("site", ""), "source": m.get("source", "")}
                                             for m in media], None
            steps = None
            if type_ == "answer":
                steps, self._turn_tools = list(getattr(self, "_turn_tools", None) or []), []
            item = self.chatlog.add("user" if type_ == "heard" else "assistant", text,
                                    who=None if type_ == "heard" else self.s.get("persona"), via=via, att=att, steps=steps)
            if item:
                self.bridge.broadcast({"type": "chat", "item": item})
        except Exception as e:  # noqa: BLE001
            log.debug("чат: %s", e)

    def _g(self, text):
        """«Выключил музыку» → «Выключила музыку» у Лиры, Эвы и других героинь (только речь самого ассистента)."""
        try:
            from gender import for_persona
            return for_persona(text, (self.personas.get(self.s.get("persona")) or {}).get("gender"))
        except Exception:  # noqa: BLE001
            return text

    def set_state(self, st):
        if st != "listening":
            self._mute_pass = False                        # разовая фраза при выключенном микрофоне — услышана или не сложилась
        if self.muted and st in ("listening", "idle") and not (st == "listening" and (getattr(self, "hold", None) is not None or self._mute_pass)):
            st = "muted"                                   # микрофон выключили — не «слушаю», пока не включат сами
        if st != self.state:
            if self.state == "speaking":
                self._spoke_until = time.monotonic()      # для узнавания своего эха сразу после ответа
            self.state = st
            log.debug("состояние: %s", st)
        radio = getattr(self, "radio", None)
        if radio is not None:
            # слушаем и думаем — радио молчит (команду слышно без крика, фраза кончается вовремя);
            # говорим — тихо под голосом; потом — как было
            radio.duck(0.0 if st in ("listening", "thinking") else 0.25 if st == "speaking" else 1.0)
        self.emit("state", state=st, persona=self.s.get("persona"))

    def note(self, text):
        self.status["note"] = self._g(text)
        self.emit("status", status=self.status)

    def _level(self, v, src):
        if self._intro_ear is not None or self._intro_probe is not None:
            self._intro_level(v, src)                 # знакомство проверяет микрофон
        now = time.monotonic()
        if now - self._level_t >= 0.066:          # уровень звука в интерфейс — не чаще ~15 раз в секунду
            # в тишине уровень почти не меняется — 15 сообщений в секунду всем окнам впустую (отзыв 23.10: «в простое
            # жрёт процессор»): шлём, когда заметно изменился, и раз в секунду для порядка
            last = getattr(self, "_level_v", (None, ""))
            if last[1] == src and last[0] is not None and abs(v - last[0]) < 0.02 and v < 0.05 and now - self._level_t < 1.0:
                return
            self._level_t, self._level_v = now, (v, src)
            self.emit("level", v=round(v, 3), src=src)
