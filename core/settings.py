"""Пути и настройки. Настройки — один JSON: CONFIG_DIR/settings.json (Linux ~/.config/dewiar, Windows %APPDATA%\\Dewiar);
модели, голоса и прочие данные — STATE_DIR. Оба пути можно переопределить DEWIAR_CONFIG_DIR / DEWIAR_STATE_DIR.

Файл пишет только ядро (окно настроек присылает изменения через WebSocket), поэтому гонок нет. Ключи API лежат там же,
права 600. DEFAULTS — все ключи со значениями по умолчанию: сохранённый файл накладывается поверх (_merge), так что
новый ключ достаточно добавить сюда. ensure_token() — секрет локального WebSocket.
"""

import copy
import json
import logging
import os
import secrets
import threading
from pathlib import Path

log = logging.getLogger("dewiar.settings")

APP_DIR = Path(__file__).resolve().parent.parent            # /opt/dewiar или папка исходников
DATA_DIR = APP_DIR / "data"                                  # то, что едет в пакете
WIN = os.name == "nt"
# HOME — буквально «~» или относительный путь (так бывает при запуске из некоторых ярлыков и служб): Path.home() тогда
# «~», и всё пишется в папку «~» там, где запустили (выгрузка 25.10: «близкие: сохранить — Permission denied: '~/.local'»).
# Берём настоящую домашнюю папку из учётной записи — один раз здесь, до всех Path.home() в ядре.
if not WIN and not os.path.isabs(os.environ.get("HOME") or "/"):
    try:
        import pwd
        os.environ["HOME"] = pwd.getpwuid(os.getuid()).pw_dir
    except (ImportError, KeyError, OSError):
        pass
if WIN:     # Windows: настройки — %APPDATA%\Dewiar, модели и голоса — %LOCALAPPDATA%\Dewiar
    _cfg = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming") / "Dewiar"
    _state = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "Dewiar"
else:
    _cfg, _state = Path.home() / ".config/dewiar", Path.home() / ".local/share/dewiar"


def _os_name():
    """Название системы для подсказки модели: «Windows 11» (по номеру сборки — platform.release() у 11 говорит «10»)
    или «Linux, <PRETTY_NAME из /etc/os-release>»."""
    import platform
    if WIN:
        try:
            build = int(platform.version().split(".")[-1])
        except ValueError:
            build = 0
        return "Windows 11" if build >= 22000 else "Windows 10" if build else "Windows"
    import sys
    if sys.platform == "darwin":                          # №332 (пакет 27.10): на Mac модель думала, что она в Linux
        return ("macOS " + (platform.mac_ver()[0] or "")).strip()
    try:
        info = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
        return "Linux, " + info.get("PRETTY_NAME", "").strip('"')
    except OSError:
        return "Linux"


OS_NAME = _os_name()
CONFIG_DIR = Path(os.environ.get("DEWIAR_CONFIG_DIR", _cfg))
STATE_DIR = Path(os.environ.get("DEWIAR_STATE_DIR", _state))
MODELS_DIR = STATE_DIR / "models"
VOICES_DIR = STATE_DIR / "voices"
PERSONAS_DIR = CONFIG_DIR / "personas"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
TOKEN_PATH = CONFIG_DIR / "token"
WS_PORT = int(os.environ.get("DEWIAR_PORT", "8765"))

# Готовые профили «мозга». Все, кроме Anthropic, говорят на OpenAI-совместимом API.
LLM_PRESETS = {
    "vllm":      {"name": "vLLM (мой сервер)", "kind": "openai", "base_url": "http://127.0.0.1:8000/v1", "disable_thinking": True},
    "ollama":    {"name": "Ollama",            "kind": "openai", "base_url": "http://127.0.0.1:11434/v1"},
    "llamacpp":  {"name": "llama.cpp server",  "kind": "openai", "base_url": "http://127.0.0.1:8080/v1"},
    "lmstudio":  {"name": "LM Studio",         "kind": "openai", "base_url": "http://127.0.0.1:1234/v1"},
    "openrouter": {"name": "OpenRouter",       "kind": "openai", "base_url": "https://openrouter.ai/api/v1"},
    "openai":    {"name": "OpenAI",            "kind": "openai", "base_url": "https://api.openai.com/v1"},
    "anthropic": {"name": "Anthropic Claude",  "kind": "anthropic", "base_url": "https://api.anthropic.com"},
    "deepseek":  {"name": "DeepSeek",          "kind": "openai", "base_url": "https://api.deepseek.com/v1"},
    # признанные поставщики напрямую (20.10: «обязательно все оригинальные — Gemini, DeepSeek, Claude, Kimi, GLM, Qwen»):
    # у всех — официальный OpenAI-совместимый адрес
    "gemini":    {"name": "Google Gemini",     "kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    "kimi":      {"name": "Kimi (Moonshot)",   "kind": "openai", "base_url": "https://api.moonshot.ai/v1"},
    "glm":       {"name": "GLM (Z.ai)",        "kind": "openai", "base_url": "https://api.z.ai/api/paas/v4"},
    "qwen":      {"name": "Qwen (Alibaba)",    "kind": "openai", "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"},
    "mistral":   {"name": "Mistral",           "kind": "openai", "base_url": "https://api.mistral.ai/v1"},
    "xai":       {"name": "Grok (xAI)",        "kind": "openai", "base_url": "https://api.x.ai/v1"},
    # GitHub #8 (24.10): «не подключается opencode» — у OpenCode Go свой OpenAI-совместимый адрес (не …/inference/…)
    "opencode":  {"name": "OpenCode Go",       "kind": "openai", "base_url": "https://opencode.ai/zen/go/v1"},
    # российские агрегаторы — оплата картой РФ (№141). Только давно работающие: ProxyAPI и VseGPT (с 2023 г.); AITunnel и
    # Polza.ai убраны 20.10 по решению владельца — у кого подключены, работают как прежде (адрес хранится в профиле)
    "proxyapi":  {"name": "ProxyAPI",          "kind": "openai", "base_url": "https://api.proxyapi.ru/openai/v1"},
    "vsegpt":    {"name": "VseGPT",            "kind": "openai", "base_url": "https://api.vsegpt.ru/v1"},
}

DEFAULTS = {
    "version": 1,
    "persona": "lira",
    "all_names": True,              # отзываться на имя любого персонажа и переключаться на него
    "team": {"route": True,         # главный (Агент) сам передаёт вопрос специалисту: код — Кодеру, письмо — Лире…
             "back": True},         # после ответа специалиста — снова главный
    "user_name": "",
    "llm": {
        "active": "",
        "profiles": {},             # id -> {name, kind, base_url, api_key, model, disable_thinking, temperature, max_tokens}
        "persona": {},              # id персонажа -> id профиля: свой мозг у персонажа («» — общий, active). 27.10
        "history_turns": 8,
        "lean_prompt": False,       # проба: короткая инструкция — навыки только именами, описания — к подходящему вопросу
        "think_auto": True,         # сложная просьба (стих, расчёт, анализ, план, код) — модель думает перед ответом (llm.wants_think)
        "tools_modes": {},          # «адрес|модель» → native | prompt | none: как модель вызывает инструменты (проверяется само)
        "history_reset_seconds": 28800,   # новый разговор — после 8 часов тишины; длинный сворачивается в содержание (conversation.py)
        "fallback": "",             # запасной мозг, если облако Dewiar не ответило или заряд кончился (id профиля)
        "auto_from": "",            # id своей модели, которая не отвечала: пока думают модели Dewiar; ответит — вернёмся к ней
    },
    "stt": {
        "engine": "gigaam",         # gigaam | remote | vosk
        "english": False,           # понимать и английскую речь (lang2.py: английская модель Vosk ~40 МБ, выбор по уверенности)
        "gigaam_model": "gigaam-v3-e2e-rnnt",
        "remote": {"base_url": "", "api_key": "", "model": "gigaam-v3", "language": "ru"},
    },
    "tts": {
        "engine": "vosk",           # vosk | piper | remote | elevenlabs | espeak | off
        "v2": False,                # метка разового перевода с Piper на Vosk TTS (engine.py): после неё выбор Piper не трогаем
        "text_only": False,         # отвечать только текстом (кнопка-динамик в виджете): голос молчит, ответы — в виджете
        "speed": 1.25,              # как на телефоне: 1.0 звучало медленно и устало (0.33.1; прежние 1.0 переводятся в load)
        "fx": "persona",            # обработка голоса: persona (у каждого своя) | off | clear | warm | deep | cinema | ai | space
        "remote": {"base_url": "", "api_key": "", "model": "", "sample_rate": 24000,
                   "extra": {"language": "Russian"},
                   "voice_f": "", "voice_m": ""},   # голос сервера для героинь и героев; пусто — свой у персонажа (voice.remote)
        # ElevenLabs своим ключом (elevenlabs.io → API Keys; платит человек сам): голоса героинь и героев — ID из «Voices»
        "eleven": {"api_key": "", "model": "eleven_flash_v2_5", "voice_f": "", "voice_m": ""},
    },
    "audio": {
        "input": "",                # пусто = системный микрофон по умолчанию
        "output": "",
        "echo_cancel": True,
        "headphones": False,        # в наушниках эха нет — можно слушать во время ответа и без эхоподавления
        "barge_in": "smart",        # smart (речью ~0,8 с, сначала приглушает) | any_speech | wakeword | off
        "barge_v2": False,          # метка разового перевода barge_in с wakeword на smart (engine.py)
        "follow_up_seconds": 8,     # после ответа можно говорить без имени
        "end_silence_ms": 650,      # столько тишины — конец фразы
        # подстройка под манеру речи (engine_audio._pause_*): человек продолжил сразу после того, как фразу сочли законченной, —
        # ждать дольше (+150 мс, до +600); обычные разговоры понемногу возвращают к end_silence_ms
        "end_silence_auto": True, "end_silence_extra": 0,
        # длинная фраза без имени после ответа (дольше 9 с или 26 слов) — обычно разговор людей рядом; True — это тоже мне (№226)
        "follow_long": False,
        "sounds": True,
        "turn_tone": True,          # ответ закончен и можно говорить без имени — мягкий сигнал «ваша очередь» (нужно и sounds)
        "asr_wake": True,           # искать имя точным распознавателем в каждой короткой фразе (любые имена)
        "meeting": "pause",         # созвон (другая программа слушает микрофон): pause — не слушать имя | main — только главного | normal
        "name_sensitivity": 1.0,    # голосовой отпечаток имени: 0.7 строже … 1.4 мягче
    },
    "device": {"light": False,    # лёгкий режим для слабого компьютера: распознавание на сервере или Vosk, голос Piper
               "sig": "",         # для какого «железа» (память/ядра) уже решали — если пользователь выключил, сами не включаем
               "told": False,
               "mem_warn": True},  # предупреждать, когда памяти не хватает (открыто много других программ) — engine_brain._memory_watch
    "ui": {"hud_x": None, "hud_y": None, "subtitles": True, "force_x11": True,
           "hud_w": None, "hud_h": None,    # свой размер карточки виджета (растянули за угол), px при масштабе 100 %
           "hud_smooth": True,              # Linux с композитором: прозрачное окно и гладкие скругления (ui/app.py)
           "skin": "neusky",                # тема (фон) виджета и телефона — список в ui/assets/skins.js; по умолчанию «Небесный» (20.10)
           "voice_fx": "bars",              # когда говорит: bars (лучи вокруг портрета) | pulse (расходящиеся круги) | wave (волна)
           "zoom": 1.0,                     # масштаб интерфейса 0.7–1.5 (студия «Оформление» → «Размер», Ctrl + / Ctrl −)
           "text": 1.0,                     # размер текста ответов, «Чата», заметок 0.85–1.4 (ui/assets/zoom.js)
           "cursor_look": False,            # портрет смотрит на курсор над виджетом (hud.html lookAt) — по желанию, выключено
           "memory_motion": "auto",         # «Память»: анимация карты — auto (на слабом компьютере выкл) | on | off
           "welcome": "",                   # «Первые шаги»: "" — показать, "later" — кнопкой в меню, "done" — всё
           "intro": "",                     # знакомство голосом (engine_intro.py): "" — ещё не было, "done" — было
           "pad_w": None, "pad_h": None,    # свой размер блокнота у виджета (растянули за уголок), px при 100 % (ui/app.py pad_resize)
           "pad_text": None,                # размер текста в блокноте, 0.8–1.7 (ui/pad.js textSize); пусто — как задумано
           "pad_colors": None,              # цвета текста в блокноте: forest/sea/dusk/theme/plain (ui/pad.js colorScheme); пусто — «Чернила»
           "pad_side": "auto",              # блокнот у виджета: "auto" (к середине экрана), "left", "right" — кнопка ⇄ (pad.js)
           "home_apps": None,               # студия → «Главная»: какие значки и в каком порядке (home.js); пусто — как задумано
           "home_known": None,              # какие значки «Главной» человек уже видел, когда настраивал (новые после выпуска — сами в конце)
           "nav_fold": None},               # студия: свёрнутые группы меню («Знания», «Настройка»…) — home.js
    "reminders": {"ring_minutes": 2,    # сколько звенит, если никто не ответил (потом — «пропущено» в окне)
                  "sound": "signature",  # signature («Пульс») | noon | night | wave | sparks (audio_io.BRAND_SOUNDS; 0.52)
                  "window": True,       # окно-будильник по центру экрана
                  "speak": True},       # произнести текст напоминания голосом
    # «Безопасность» (core/security.py): стоп-кран «Ничего не уходит в интернет» (core/egress.py) и модель, к которой вернуться
    # после него; замки: files — all | folder (удалять и отправлять только из папки ассистента), mic — name | button
    "privacy": {"local_only": False, "prev_llm": "", "files": "all", "mic": "name"},
    # «Возможности» (24.10, владелец: «много всего появилось — люди пугаются; сделать опциональное включение части
    # функций»): необязательное прячется из меню, пока его не включат. У новых — «Встречи», «Рядом» (радар) и «Суфлёр»
    # выключены, «Досуг» (игры) включён; у тех, кто уже пользуется Dewiar, всё остаётся как было (Settings.load).
    "features": {"meet": False, "near": False, "prompter": False, "games": True, "family": False, "team": False, "clients": False},
    "tools": {"enabled": {}, "confirm": {}, "search_url": ""},   # пусто = как задумано по умолчанию
    "skills": {"disabled": [], "catalog_url": ""},   # каталог навыков с сайта (JSON)
    "plugins": {"on": {}},              # установленные плагины (core/plugins.py): id -> {at, values, jobs}
    "mcp": {"servers": {}},             # имя -> {type: stdio|http, command, args, env, url, headers, enabled, trust}
    "eyes": {"camera": "/dev/video0"},
    "workspace": {"path": ""},          # папка ассистента; пусто = ~/Dewiar
    "money": {"currency": ""},          # валюта по умолчанию для «купил … за 8 рублей»; пусто — по часовому поясу
    "close": {"name": "", "speak": True},  # «Близкие» (close.py): как подписываться для близких (пусто — имя пользователя), читать ли вслух
    "persona_memory": {"own": [], "at": 0},           # своя память у персонажа (0.56): имена; общая «Обо мне» — у остальных
    "sync": {"enabled": True, "e2e": False},   # e2e — шифровать на устройстве (core/synckey.py)      # телефон ↔ компьютер через облако Dewiar: напоминания, заметки, расходы, память
    "knowledge": {"folders": []},       # свои папки для поиска по документам (кроме «Знаний»), core/knowledge.py
    "obsidian": {"vault": "",           # хранилище Obsidian; пусто = не подключено
                 "folder": "Dewiar",    # папка в хранилище, куда ассистент кладёт заметки, дневник, «Обо мне»
                 "search": True,        # искать ответы во всём хранилище
                 "sync_all": False},    # всё хранилище (тексты .md) — одинаковое на всех компьютерах через облако Dewiar
    "calendars": {"items": [], "remind_minutes": 10},   # календари по ссылке iCal (Google, Яндекс…), напомнить за N минут
    "cloud": {"key": "", "url": "", "account": False, "stt_ok": False, "tts_ok": False,
              "join": {}},      # заявка на Dewiar из программы: {id, secret, url} — ждём ключ (engine_brain._join_loop)   # ключ Dewiar Облака (dw-…): модели сервера Dewiar с зарядом в талерах
    "kids": {"on": False},   # детский режим (kids.py): ребёнок, время, что можно; PIN — в STATE_DIR/kids.json
    "net": {"proxy": "", "dewiar": False, "web_via": True,   # прокси для серверов Dewiar, если провайдер блокирует dewiar.pro: свой (socks5://… или http://…) или «Использовать прокси Dewiar»
            "dewiar_secret": "", "dewiar_at": 0,                # прокси, выданный dewiar.pro, и когда получен (обновляется раз в 6 часов, engine_brain.py)
            "reserve": True, "dewiar_try": 0,                   # запасной путь: напрямую не открылось — тем же прокси Dewiar (net._DirectFirst)
            "lan": {}},         # дома — напрямую: {"public", "base", "id"} — папка сайта по имени и в домашней сети (engine_brain._lan_fetch)
    "music": {"service": "auto",        # где включать музыку: auto (недавно открыта Яндекс Музыка — в ней, иначе радио) | radio | yandex | youtube
              # своя папка с музыкой (27.10, engine_mymusic.py): папка («» — не выбрана), «в любимое» — пути треков,
              # ведущий говорит пару слов перед треком — раз в dj_every треков
              "folder": "", "favs": [], "dj_talk": True, "dj_every": 3},
    "smarthome": {"client_id": ""},     # ID приложения Яндекс OAuth (iot:view, iot:control) для кнопки «Получить ключ»
    "backup": {"dir": "", "auto": True},  # резервные копии: папка (пусто — «Документы/Dewiar — копии»), раз в неделю сама
    "updates": {"url": "", "auto_check": True},       # пусто = https://dewiar.pro/dwrapp/latest.json
    "tasks": {"llm": "", "max_steps": 80, "cycles": 15, "auto_run": False,   # модель задач (пусто = активная); шагов за круг и кругов подряд; команды без вопроса
              "self_check": True, "learn": True},              # самопроверка итога и уроки из прошлых задач (quality.py)
    "welcome": {"on": True, "away_min": 20},   # вернулись к компьютеру после away_min минут — коротко сказать главное (presence.py)
    "diary": {"night": True, "hour": 3},   # дневник ассистента: ночью (после hour:00) — запись о прожитом дне и выводы на завтра
    "night": {"on": True},                 # ночной обход (night.py): сбои за сутки, повтор задач, утром — фраза, отчёт — с согласия
    "soul": {"on": True, "constitution": True, "auto": True},   # душа персонажа (растёт из дневника) и конституция — в подсказку
    # отчёты разработчику при сбое: auto None — ещё не спрашивали, True — отправлять самому, False — нет; pulse — анонимный
    # пульс для «Здоровья» (core/health.py); who — как подписать в «Помощниках проекта»; dev — случайный номер установки
    "report": {"auto": None, "pulse": True, "who": "", "dev": ""},
    "provision": {},                    # откуда пришли настройки: {url, name, key, applied}
}


def _merge(base, over):
    """Глубокое наложение over на копию base. profiles, extra и servers заменяются целиком: это словари «id ->
    запись», и удалённый пользователем профиль или сервер не должен вернуться из base."""
    out =copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in ("profiles", "extra", "servers"):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def system_dark():
    """Тёмная ли тема у системы: Windows — «AppsUseLightTheme» = 0; Linux — GNOME color-scheme «prefer-dark» или тема
    GTK с «dark» в имени. Не узнали — False (светлая тема по умолчанию)."""
    import os
    import subprocess
    import sys
    if os.environ.get("DEWIAR_SYSTEM_DARK") in ("0", "1"):                 # для проверок
        return os.environ["DEWIAR_SYSTEM_DARK"] == "1"
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        if sys.platform.startswith("linux"):
            for key in ("color-scheme", "gtk-theme"):
                r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", key], capture_output=True, text=True, timeout=2)
                if r.returncode == 0 and "dark" in r.stdout.lower():
                    return True
    except Exception:  # noqa: BLE001 — нет реестра, нет gsettings — значит, светлая по умолчанию
        pass
    return False


class Settings:
    def __init__(self, path: Path = SETTINGS_PATH):
        self.path = path
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self.data = _merge(DEFAULTS, raw)
                if "welcome" not in (raw.get("ui") or {}):
                    self.data["ui"]["welcome"] = "done"      # уже пользуются — «Первые шаги» не показываем
                if "intro" not in (raw.get("ui") or {}):
                    self.data["ui"]["intro"] = "done"        # и знакомство само не начинается (кнопкой — можно)
                if (raw.get("tts") or {}).get("speed", 1.0) == 1.0 and not (raw.get("tts") or {}).get("speed_v2"):
                    self.data["tts"]["speed"] = 1.25                     # 1.0 — прежнее значение по умолчанию, не выбор пользователя
                self.data["tts"]["speed_v2"] = True                       # перевод один раз: выбранные потом 1.0 не трогаем
                ui = raw.get("ui") or {}
                if ui.get("skin", "brand") == "brand" and not ui.get("skin_v2"):
                    self.data["ui"]["skin"] = "neusky"                   # 20.10: «Небесный» — новый стиль по умолчанию (один раз;
                self.data["ui"]["skin_v2"] = True                         # выбранную потом «Фирменную» больше не трогаем)
                if "features" not in raw:                                # уже пользуются — ничего не прячем (24.10)
                    self.data["features"] = {"meet": True, "near": True, "prompter": True, "games": True, "family": False, "team": False, "clients": False}
                if (raw.get("llm") or {}).get("history_reset_seconds") in (300, 1200):
                    self.data["llm"]["history_reset_seconds"] = 28800    # 300 и 1200 — прежние значения по умолчанию, не выбор пользователя
            except FileNotFoundError:
                self.data = copy.deepcopy(DEFAULTS)
                if system_dark():                                         # №259 (25.10): тёмная система — с первого запуска
                    self.data["ui"]["skin"] = "neudark"                   # «Графитовый», а не светлый «Небесный» «режет глаз»
            except (OSError, json.JSONDecodeError) as e:
                log.error("Настройки повреждены (%s) — беру значения по умолчанию, старый файл сохраню как .bak", e)
                try:
                    self.path.replace(self.path.with_name("settings.json.bak"))
                except OSError:
                    pass
                self.data = copy.deepcopy(DEFAULTS)

    def save(self):
        """Через .tmp с правами 600 (в файле ключи API): файл не останется недописанным и не будет виден другим."""
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name("settings.json.tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.chmod(tmp, 0o600)
            # №269 (пакет 27.10): антивирус (Касперский) на миг держит файл — WinError 5, и настройки не сохранялись.
            # Пять попыток с растущей паузой; не вышло — исключение, как раньше
            import time as _t
            for i in range(5):
                try:
                    tmp.replace(self.path)
                    break
                except PermissionError:
                    if i == 4:
                        raise
                    _t.sleep(0.1 * (i + 1))

    def get(self, *keys, default=None):
        """get("llm", "active") — копия значения по пути ключей; нет такого — default."""
        with self._lock:
            cur = self.data
            for k in keys:
                if not isinstance(cur, dict) or k not in cur:
                    return default
                cur = cur[k]
            return copy.deepcopy(cur)

    def update(self, patch: dict):
        """Наложить patch (как _merge) и сразу сохранить на диск."""
        with self._lock:
            self.data = _merge(self.data, patch)
            self.save()

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self.data)

    def active_llm(self):
        with self._lock:
            llm = self.data["llm"]
            return copy.deepcopy(llm["profiles"].get(llm["active"]))


def migrate_from_cortex():
    """Cortex (прежнее имя программы) → Dewiar: копируем настройки и персонажей (без токена), переносим скачанные
    модели, чтобы не качать заново ~300 МБ; главный помощник становится активным. Только на Linux-путях и только
    при первом запуске — когда CONFIG_DIR ещё нет. -> True, если перенесли."""
    if os.environ.get("DEWIAR_CONFIG_DIR") or CONFIG_DIR.exists():
        return False
    old_cfg, old_state = Path.home() / ".config/cortex", Path.home() / ".local/share/cortex"
    if not old_cfg.exists() and not old_state.exists():
        return False
    import shutil
    try:
        if old_cfg.exists():
            shutil.copytree(old_cfg, CONFIG_DIR, ignore=shutil.ignore_patterns("token"))
        if old_state.exists() and not STATE_DIR.exists():
            STATE_DIR.parent.mkdir(parents=True, exist_ok=True)
            old_state.rename(STATE_DIR)
    except OSError as e:                      # ядро и интерфейс стартуют одновременно — второй просто пропускает
        log.info("Перенос из Cortex пропущен: %s", e)
        return False
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        data["persona"] = "lira"
        data.get("ui", {}).pop("hud_x", None)
        data.get("ui", {}).pop("hud_y", None)
        data.get("ui", {}).pop("hud_w", None)             # размер виджета — под экран этого компьютера
        data.get("ui", {}).pop("hud_h", None)
        SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError):
        pass
    log.info("Перенёс настройки и модели из Cortex")
    return True


def ensure_token() -> str:
    """Секрет для локального WebSocket (CONFIG_DIR/token, права 600; создаётся один раз): без него чужой сайт
    в браузере мог бы подключиться к 127.0.0.1 и поменять настройки."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if TOKEN_PATH.exists():
        t = TOKEN_PATH.read_text().strip()
        if t:
            return t
    t = secrets.token_urlsafe(24)
    TOKEN_PATH.write_text(t)
    os.chmod(TOKEN_PATH, 0o600)
    return t
