"""Общая основа движка: импорты, константы и помощники, которые видят все части Engine (engine_*.py)
через `from engine_base import *` — поэтому всё нужное частям импортируется здесь (см. __all__ в конце).

Устройство движка: состояния idle → listening → thinking → speaking → (listening на время «продолжения
разговора») → idle, плюс muted. Потоки: audio — микрофон кадрами по 32 мс, VAD и слово запуска, нарезка фраз;
stt — очередь фраз → текст (GigaAM / удалённый / Vosk); turn — на каждый вопрос: токены модели → фразы →
синтез → динамик; новый вопрос или «стоп» сразу отменяет текущий ход.
Здесь же: поиск имени в начале фразы (find_name), фразы «замолчи» (is_sleep_phrase), скрытие паролей в журнале."""

import collections
import difflib
import json
import subprocess
import logging
import os
import queue
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

import voicefx
from workspace import Workspace, WorkspaceError
from tasks import TaskManager
from updater import Updater
from version import VERSION
from audio_io import AEC_SINK, AEC_SOURCE, AudioOutError, Capture, EchoCancel, FRAME, RATE, Player, ToneOut, list_devices, tone
from listen import MEDIA_WORDS, STOP_WORDS, SileroVAD, WakeSpotter, ensure_vosk, kaldi_path, missing_words
from llm import (CodeFilter, LLMError, SentenceSplitter, discover_local, list_models, speakable, stream_chat, stream_events,
                 test_profile, tool_turn_messages, user_message, probe_tools)
from personas import PIPER_VOICES, pronounce
from settings import DATA_DIR, LLM_PRESETS, MODELS_DIR, OS_NAME, STATE_DIR
from stt import GigaAMSTT, RemoteSTT, VoskSTT
import provision
from mcp import MCPError, MCPManager
from skills import SkillError, Skills
from plugins import Plugins
from pad import Pad, PadError  # noqa: F401
from tools import Reminders, ToolError, Toolbox, desktop_notify
from tts import ElevenTTS, EspeakTTS, PiperTTS, RemoteTTS, SapiTTS, VoskTTS

log = logging.getLogger("dewiar.engine")
_report_tls = threading.local()

FRAME_S = FRAME / RATE
_WORD = re.compile(r"[\wёЁ]+(?:-[\wёЁ]+)*")
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
          "октября", "ноября", "декабря"]


def _norm(w):
    return w.lower().replace("ё", "е")


INTERJECTIONS = {"эй", "ну", "слушай", "привет", "окей", "ок", "хей", "алло", "так", "а"}


def find_name(text, aliases_by_pid, strict=False):
    """Ищет обращение по имени в начале фразы -> (pid, конец имени в тексте) или (None, 0).

    Обычный режим — имя уже подтвердил Vosk, достаточно похожести (≥ 0.75) среди первых трёх слов.
    Строгий режим — для имён, которых нет в словаре Vosk (например «Девиар»), имя ищется в каждой
    фразе, поэтому: только первое слово (или после «эй», «слушай»…), имена до 4 букв — только точно,
    длинные — очень близко (≥ 0.86). Иначе «игра» будила бы Лиру, а «дева» — Эву.
    Распознаватель рвёт имя («Де Виар») — два соседних слова пробуем и склеенными."""
    words = list(_WORD.finditer(text))
    if strict:
        start = 1 if words and _norm(words[0].group()) in INTERJECTIONS else 0
        positions = range(start, min(start + 1, len(words)))
    else:
        positions = range(min(3, len(words)))
    best = (0.0, None, 0)
    for i in positions:
        cands = [(_norm(words[i].group()), words[i].end(), False)]
        if i + 1 < len(words):                  # «Де виар», «деви ар» — склеиваем
            cands.append((_norm(words[i].group() + words[i + 1].group()), words[i + 1].end(), True))
        for w, end, joined in cands:
            if len(w) < 3:
                continue
            for pid, aliases in aliases_by_pid.items():
                for a in aliases:
                    a = _norm(a).replace(" ", "").replace("-", "")
                    if strict and len(a) <= 4:
                        r = 1.0 if w == a else 0.0
                    elif len(a) <= 4 and w != a and w[:1] != a[:1] and w != a[1:]:
                        # короткое имя: одна буква решает всё — «мира», «пира», «тира» не «Лира» (отчёт 11.10: «открылась
                        # для мира» из видео будила Лиру). Свои формы («лиру», «лирой») и потерянная первая («ира») — можно
                        r = 0.0
                    else:
                        r = difflib.SequenceMatcher(None, w, a).ratio()
                        if joined and r < 0.9 and strict:
                            r = 0.0
                    if r > best[0]:
                        best = (r, pid, end)
    need = 0.86 if strict else 0.75
    return (best[1], best[2]) if best[0] >= need else (None, 0)


def name_inside(text, aliases_by_pid):
    """Имя не в начале, а внутри фразы: «Я так и начал. Лира, расскажи…» (отчёт 18.10 — длинную фразу с именем во
    втором предложении приняли за разговор людей рядом). -> pid или None. Имя в начале каждого предложения (как
    find_name) или само имя и его падежи отдельным словом где угодно («…спроси у Лиры…»)."""
    for part in re.split(r"[.!?;:\n]+", text or "")[1:]:
        pid, _ = find_name(part.strip(" ,—-"), aliases_by_pid)
        if pid:
            return pid
    words = {_norm(w.group()) for w in _WORD.finditer(text or "")}
    for pid, aliases in aliases_by_pid.items():
        for a in aliases:
            a = _norm(a).replace(" ", "").replace("-", "")
            if len(a) < 3:
                continue
            forms = {a}
            if a[-1] in "аяь":
                forms |= {a[:-1] + e for e in ("у", "ы", "е", "ой", "ою", "и", "ю", "ей")}
            elif a[-1] not in "аеёиоуыэюя":
                forms |= {a + e for e in ("а", "у", "ом", "е")}
            if words & forms:
                return pid
    return None


# Просьба к ассистенту в начале фразы: «Хорошо, давай расскажи мне, что…» (отчёт 18.10: длинный вопрос сразу после
# ответа без имени терялся — «засыпает на половине фразы»). Только повелительные формы, обращённые к помощнику.
_TO_ME = re.compile(r"(?<![\w-])(?:расскажи|скажи|подскажи|объясни|покажи|найди|поищи|посмотри|проверь|включи|выключи|"
                    r"поставь|напомни|запиши|запомни|сделай|создай|помоги|посоветуй|придумай|напиши|открой|посчитай|"
                    r"переведи|составь|перескажи|прочитай|прочти|озвучь|сравни|опиши|предложи|подбери|набросай|добавь|сохрани|удали|переключи|запусти|отправь|позвони|узнай)(?![\w-])", re.I)


def to_me(text):
    """Похоже на просьбу ко мне: повелительный глагол среди первых восьми слов."""
    head = " ".join(_WORD.findall(text or "")[:8]).lower().replace("ё", "е")
    return bool(_TO_ME.search(head))


_PW_PIPE = re.compile(r"((?:echo|printf)\s+)(['\"]?)([^'\"|;&\s]+)\2(\s*\|\s*sudo)")
_PW_WORD = re.compile(r"(парол\w*|password|passwd|pass)([^.\n]{0,60})", re.I)


# Что инструменты узнали — коротко в истории разговора (отзывы: «забывает IP» — узнала адрес командой, а на «а какой у
# него провайдер?» искала заново или выдумывала: в истории оставался только её ответ словами, без найденного).
FACT_TOOLS = {"web_search", "weather", "read_webpage", "find_notes", "read_file", "calc", "list_reminders", "calendar_list",
              "money_report", "payments", "read_emails", "read_email", "search_documents", "ask_knowledge", "system_status", "task_status",
              "look_at_screen", "look_through_camera", "app_update", "run_command", "server_run", "world_time", "close_read"}
FACT_LEN, FACTS_PER_TURN, FACT_TURNS = 280, 3, 4


def fact_line(name, args, out):
    """Одна строка «что узнала»: имя(главное из аргументов) → начало результата; пароли — ***."""
    a = ""
    if isinstance(args, dict):
        a = next((str(v) for k, v in args.items() if isinstance(v, (str, int, float)) and str(v).strip()), "")
        a = " ".join(a.split())[:80]
    res = " ".join(str(out or "").split())
    if len(res) > FACT_LEN:
        res = res[:FACT_LEN].rstrip() + "…"
    return redact(f"{name}({a}) → {res}")


# Ключи и токены (отчёт 256, 25.10: токен умного дома, вставленный в команду, попал в журнал и в отчёт целиком).
_TOKENS = [
    (re.compile(r"\beyJ[\w-]{6,}\.[\w-]{6,}\.[\w-]{6,}"), "eyJ***"),                                    # JWT (Home Assistant и др.)
    (re.compile(r"(Bearer\s+)[\w.~+/=-]{8,}", re.I), r"\1***"),
    (re.compile(r"\b(sk-(?:ant-|proj-)?|ghp_|gho_|github_pat_|xox[abpr]-|glpat-|hf_|AIza)[\w-]{12,}"), r"\1***"),
    (re.compile(r"\bbot\d{5,}:[\w-]{20,}"), "bot***"),
    (re.compile(r"\b\d{6,12}:AA[\w-]{30,}"), "***:***"),                                                 # токен Telegram без «bot»
    (re.compile(r"((?:токен\w*|token|api[_ -]?key|ключ\w*(?:\s+api)?|secret|секрет\w*)[\"']?\s*(?:api\s*)?[:=]?\s*[\"'«]?)"
                r"(?=[\w.+/=-]*\d)(?=[\w.+/=-]*[A-Za-z])[\w.+/=-]{20,}", re.I), r"\1***"),
]


def mask_tokens(text):
    """Ключи API, JWT, токены ботов и «токен: <длинная строка>» → ***. Для журнала и отчётов."""
    t = str(text or "")
    for rx, rep in _TOKENS:
        t = rx.sub(rep, t)
    return t


def redact(text):
    """Пароли и токены — не в журнал: «echo 'пароль' | sudo -S», «пароль администратора 1234abcd», JWT, ключи API → ***."""
    t = _PW_PIPE.sub(lambda m: m.group(1) + m.group(2) + "***" + m.group(2) + m.group(4), mask_tokens(text))
    return _PW_WORD.sub(lambda m: m.group(1) + re.sub(r"(?<![\w/])(?=\S*\d)\S{4,}", "***", m.group(2)), t)


def _spoken_question(q):
    """Вопрос «выполнить?» вслух — коротко: длинную команду не диктуем, она показана в виджете целиком."""
    q = (q or "").strip()
    if len(q) <= 90 and not re.search(r"[|;$`{}<>=\\&]|\s-{1,2}\w", q):
        return q
    code = re.compile(r"[|;$`{}<>=\\&/]|\s-{1,2}\w|^\s*(sudo|echo|cd|ls|cat|grep)\b")
    parts = q.split(": ")
    head = parts[0]
    for part in parts[1:]:
        if code.search(part) or len(head) + len(part) > 90:
            break
        head += ": " + part
    head = head.strip().rstrip("?")
    if len(head) > 90:
        head = head[:80].rsplit(" ", 1)[0]
    return f"{head}? Подробности — на экране."


def _tool_detail(name, args):
    """Что именно делает инструмент — одной строкой для «хода работы» (команда, запрос, файл, адрес)."""
    a = args if isinstance(args, dict) else {}
    for k in ("command", "query", "question", "url", "path", "file", "name", "text", "city", "title"):
        v = a.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()[:240]
    for v in a.values():
        if isinstance(v, str) and v.strip():
            return v.strip()[:240]
    return ""


class Turn:
    """Один ход разговора (вопрос → ответ): номер, флаг отмены, сказанные фразы и полный текст ответа."""
    def __init__(self, n):
        self.n = n
        self.t0 = time.monotonic()  # когда начался: спрятали ли виджет в этом ходе (engine_answer: без «Ваша очередь»)
        self.cancel = threading.Event()
        self.spoken = []
        self.full = ""
        self.via = None          # откуда вопрос не голосом (Telegram): {"done": f(text), "confirm": f(q), "speak": bool}
        self.report = None       # f(ok, text) после хода: ok — True/False, None — ход перебили (дела по расписанию)
        self.error = ""


# продолжение разговора без имени — не дольше и не длиннее этого: дальше это разговор людей рядом, не со мной
FOLLOW_MAX_S, FOLLOW_MAX_WORDS = 9.0, 26
PAUSE_EXTRA_MAX = 600       # подстройка паузы конца фразы — не больше +600 мс (№226: при +900 ассистент «всё медленнее»)
SLEEP_STRONG = {"стоп", "stop", "хватит", "замолчи", "замолкни", "стой", "тихо", "тишина", "пауза", "достаточно", "помолчи",
                "прекрати", "прекращай", "остановись", "останови", "перестань", "отмена", "отмени", "отбой", "всё", "все",
                "спасибо", "спасиб", "благодарю", "пока", "стопэ", "стоб"}
SLEEP_SOFT = {"пожалуйста", "уже", "ну", "а", "давай", "же", "так", "на", "этом", "сейчас", "ладно", "хорошо", "окей", "ок",
              "ok", "okay", "it", "please", "молодец", "понял", "поняла", "спать", "пора", "говорить", "болтать"}


def low_priority():
    """Понижает приоритет текущего потока для тяжёлой фоновой работы (загрузка моделей): звук, слух и нажатия
    в виджете не должны ждать, пока грузится GigaAM на слабом компьютере. Linux/macOS — nice 10 для потока."""
    if os.name == "nt":                  # Windows: фоновый режим потока — ниже и процессор, и диск, и память
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.GetCurrentThread.restype = ctypes.c_void_p
            if not k.SetThreadPriority(ctypes.c_void_p(k.GetCurrentThread()), 0x00010000):      # THREAD_MODE_BACKGROUND_BEGIN
                k.SetThreadPriority(ctypes.c_void_p(k.GetCurrentThread()), -2)                 # THREAD_PRIORITY_LOWEST
        except Exception:  # noqa: BLE001
            pass
        return
    try:
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 10)
    except (AttributeError, OSError):
        pass


THANKS = {"спасибо", "спасиб", "благодарю", "благодарствую", "спс", "сенкс", "thanks", "thank"}
THANKS_FILL = {"большое", "огромное", "тебе", "вам", "тебя", "за", "все", "всё", "помощь", "очень", "ну", "ладно", "хорошо",
               "окей", "ок", "понял", "поняла", "отлично", "супер", "you", "much", "так", "уже"}
THANKS_REPLIES = ("Пожалуйста!", "Обращайтесь!", "Пожалуйста, обращайтесь!", "Всегда пожалуйста!")


def thanks_phrase(text):
    """«Спасибо», «спасибо большое», «благодарю тебя», «ладно, спасибо» — только благодарность (без «стоп», «хватит»).
    Отвечаем коротко («Пожалуйста!») и засыпаем до имени: молчаливое засыпание на «спасибо» выглядело так, будто
    помощница не услышала (отчёт 11.10)."""
    t = re.sub(r"[^\w\s]", " ", (text or "").lower().replace("ё", "е"))
    words = t.split()
    if not words or len(words) > 6:
        return False
    return any(w in THANKS for w in words) and all(w in THANKS or w in THANKS_FILL for w in words)


# Распознаватель иногда пишет «стоп» латиницей или с ошибкой («Ctop.», «Сстоп», «Стоб», «Паузу», отзыв 11.10) — и тогда
# помощница не замолкала, а отвечала «Хорошо, я слушаю». Слово приводим к нашему: латинские буквы — двумя способами
# (похожие по виду: C→С, p→р; по звуку: p→п, u→у), затем близость к главным стоп-словам (не меньше 0,8 по правкам).
# Тот же разбор — на телефоне (stopWord в app.js).
_LOOK = str.maketrans("aceopxyktmhb", "асеорхуктмнв")
_PHON = str.maketrans("abcdefghiklmnoprstuvyz", "абсдефгхиклмнопрстувыз")
STOP_CORE = ("стоп", "пауза", "хватит", "замолчи", "помолчи", "прекрати", "остановись")


def _similar(a, b):
    """Похожесть слов по числу правок (Левенштейн): 1 — одинаковые. Так же считает телефон."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1 - prev[-1] / max(len(a), len(b), 1)


def stop_word(w):
    """Слово → стоп-слово из SLEEP_STRONG («Ctop» → «стоп», «паузу» → «пауза», «сстоп» → «стоп») или None."""
    w = (w or "").lower().replace("ё", "е")
    if w in SLEEP_STRONG:
        return w
    cands = [w]
    if re.search(r"[a-z]", w):
        cands += [w.translate(_LOOK), w.translate(_PHON)]
    for c in cands:
        if c in SLEEP_STRONG and c not in {"все", "всё", "пока", "спасибо", "спасиб", "благодарю"}:
            return c
    for c in cands:
        if len(c) >= 4 and not re.search(r"[a-z]", c):
            best = max(STOP_CORE, key=lambda s: _similar(c, s))
            if _similar(c, best) >= 0.8:
                return best
    return None


def is_sleep_phrase(text):
    """«Стоп», «Stop.», «хватит, спасибо», «всё, отбой», «ладно, помолчи» — фраза целиком про «замолчи».
    Такие фразы не идут в модель: ассистент засыпает до следующего имени (как «Алиса, хватит»).
    Ослышки «стопа» («Ctop.», «Сстоп», «Паузу») — тоже (stop_word)."""
    t = re.sub(r"[^\w\s]", " ", (text or "").lower().replace("ё", "е"))
    words = [w if w in SLEEP_SOFT else (stop_word(w) or w) for w in t.split()]
    if not words or len(words) > 5:
        return False
    if " ".join(words) in {"не надо", "не нужно", "ничего", "забудь", "никак", "ничего не надо", "уже не надо", "не надо уже"}:
        return True
    strong = [w for w in words if w in SLEEP_STRONG or w.replace("е", "ё") in SLEEP_STRONG]
    if not strong or not all(w in SLEEP_STRONG or w in SLEEP_SOFT or w.replace("е", "ё") in SLEEP_STRONG for w in words):
        return False
    if set(strong) <= {"все", "всё", "спасибо", "спасиб", "пока"} and len(words) > 2:
        return False                                  # «спасибо, а что ещё…» — не прощание
    return True


# Окно ассистента голосом — фраза целиком (вежливые слова не мешают): «спрячься» — виджет в трей, ассистент слушает;
# «покажись» — вернуть виджет; «отключись» — выйти из Dewiar совсем (ядро тоже: голосом обратно уже не включить).
# Только целиком: «спрячь файл в папку» или «выключи компьютер» — не сюда (компьютер — pc.py).
# в начале может стоять имя («Лира, спрячься» — STT отдаёт его вместе с командой): одно слово, кроме «не»
_WIN_FILL = r"(?:(?!не\s)[a-zа-я]{2,15}\s+(?=(?:ну|а|давай|теперь|пока|уже|пожалуйста|можешь|ка|спря[чк]|скрой|исчезни|сверни|уйди|иди|уходи|убери|покаж|появись|вернись|выйди|верни|отключ|выключ|заверш|закр|хочу|открой|запусти|включи|поиграем|сыграем|поиграть|во)))?" \
            r"(?:(?:ну|а|давай|теперь|пока|уже|пожалуйста|можешь|ка|совсем|полностью|насовсем)\s+)*"
_WIN_TRAY = r"(?:трей|трэй|tray|трея)"
# игры «Досуга» (ui/assets/arcade): «в змейку», «в гонки»… и названием — «змейку», «змейка»
GAME_NAMES = {"snake": r"змейк\w*|змею", "racer": r"гонк\w*", "bricks": r"кирпичик\w*|арканоид\w*",
              "plane": r"пилот\w*|самол[её]т\w*|самолётик\w*|самолетик\w*|небесн\w+\s+пилот\w*", "bip": r"бип\w*|бегалк\w*",
              "blocks": r"блоки|тетрис\w*", "candy": r"конфетк\w*|три\s+в\s+ряд", "merge": r"слияни\w*|2048",
              "sudoku": r"судоку", "fifteen": r"пятнашк\w*", "reversi": r"реверси|отелло",
              "tictac": r"крестик\w*(?:[\s-]+нолик\w*)?|нолик\w*", "crossword": r"кроссворд\w*", "words": r"пять\s+букв|вордл\w*|wordle",
              "glow": r"ог[оа]н[её]к\w*|огоньк\w*|сказк\w*",
              "five": r"пять\s+в\s+(?:ряд|линию)|гомоку", "pairs": r"найди\s+пару|пар[ыу]|мемори",
              # 24.10: пять новых — без «почты» и «фонарика»: «открой почту», «включи фонарик» — не игры
              "farm": r"хутор\w*|ферм\w*", "dark": r"кто\s+боится\s+темноты|темнот\w*", "post": r"колюч\w+\s+почт\w*|почтальон\w*|[её]жик\w*",
              "doodle": r"каляк\w*", "hop": r"выше\s+облаков|прыгалк\w*|попрыгунчик\w*|тимош\w*"}
_GAMES_NOM = "(?:" + "|".join(GAME_NAMES.values()) + ")"
_GAMES = r"в\s+" + _GAMES_NOM


def play_game(text):
    """«Поиграем в змейку» -> "snake"; без названия игры -> ""."""
    t = (text or "").lower().replace("ё", "е")
    return next((k for k, rx in GAME_NAMES.items() if re.search(r"(?<![а-я])(?:" + rx.replace("ё", "е").replace("[её]", "е") + r")", t)), "")
WINDOW_RX = {
    "tray": re.compile(rf"^{_WIN_FILL}(?:(?:спрячься|спрячся|спрякся|спрячтесь|скройся|исчезни|свернись|уйди)(?:\s+в\s+{_WIN_TRAY})?|"
                       rf"(?:спрячь|убери|сверни|скрой)\s+(?:виджет|окно|окошко|себя)(?:\s+в\s+{_WIN_TRAY})?|"
                       rf"(?:иди|уходи)\s+в\s+{_WIN_TRAY})(?:\s+пожалуйста)?$"),
    "show": re.compile(rf"^{_WIN_FILL}(?:покажись|появись|вернись\s+на\s+экран|выйди\s+из\s+{_WIN_TRAY}|"
                       r"(?:покажи|верни)\s+(?:виджет|окно|окошко|себя))(?:\s+пожалуйста)?$"),
    # «Досуг» (24.10): «Лира, давай поиграем», «хочу поиграть», «открой игры», «поиграем в змейку» — полка игр у виджета.
    # Только целиком и только свои игры: «давай сыграем в города» — это разговорная игра, её ведёт модель.
    "play": re.compile(rf"^{_WIN_FILL}(?:(?:поиграем|сыграем|поиграть|поиграй\s+со\s+мной|сыграй\s+со\s+мной)(?:\s+(?:во\s+что\s*-?\s*нибудь|"
                       rf"в\s+игр[уы]|немного|чуть\s*-?\s*чуть|{_GAMES}))*|хочу\s+(?:поиграть|играть|в\s+игр[уы])(?:\s+{_GAMES})?|"
                       rf"(?:открой|запусти|включи|покажи)\s+(?:игры|игру|досуг|аркаду|{_GAMES_NOM})(?:\s+{_GAMES_NOM})?|"
                       r"во\s+что\s+(?:бы\s+)?(?:поиграть|поиграем|сыграть))(?:\s+пожалуйста)?$"),
    "quit": re.compile(rf"^{_WIN_FILL}(?:отключись|выключись|завершись|закройся|выйди\s+из\s+(?:программы|приложения)|"
                       r"(?:закрой|выключи|отключи)\s+(?:программу|приложение|ассистента|себя|dewiar|девиар|дьюар))"
                       r"(?:\s+(?:совсем|полностью|насовсем))?(?:\s+пожалуйста)?$"),
}


def window_phrase(text):
    """«Спрячься», «уйди в трей» -> "tray"; «покажись» -> "show"; «отключись», «закрой программу» -> "quit"; иначе None."""
    t = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower().replace("ё", "е"))).strip()
    return next((k for k, rx in WINDOW_RX.items() if rx.match(t)), None)


MEDIA_STOP = {"пауза", "стоп", "стой", "хватит", "тихо", "тишина", "замолчи"}   # одно слово при музыке — пауза
# «позови Лиру», «дай слово Эве, пусть расскажет…» — передать разговор другому персонажу: группа 1 — имя, 2 — остаток фразы
# «Обновись», «проверь обновления», «есть новая версия?» — сразу, без модели (22.10, владелец: написал «Обновись» — Лира
# ответила «сейчас посмотрю, как обновляется Dewiar» и ничего не сделала).
UPDATE_RX = re.compile(r"^\s*(?:[а-яё]+,\s*)?(?:пожалуйста,?\s*)?(?:обновись|обновляйся|"
                       r"обнови(?:сь)?\s+(?:себя|программу|приложение|dewiar|девиар)|"
                       r"(?:проверь|посмотри|глянь)\s+(?:есть\s+ли\s+)?(?:свои\s+)?обновлени[яе]\w*|"
                       r"есть\s+(?:ли\s+)?(?:обновлени[ея]|нов(?:ая|ые)\s+верси[яи])|"
                       r"обнови(?:сь)?\s+до\s+(?:последней|новой|свежей)\s+версии)"
                       r"(?:\s*,?\s*пожалуйста)?\s*[.!?]*\s*$", re.I)
CALL_RX = re.compile(r"^\s*(?:а\s+|ну\s+|слушай,?\s+)?(?:позови(?:те)?|зови|пригласи|дай(?:те)?\s+слово|передай\s+слово|"
                     r"переключи(?:сь)?\s+на|хочу\s+(?:поговорить|говорить)\s+с|пусть\s+(?:ответит|скажет|расскажет))"
                     r"\s+([\wё-]+)[\s,.!?:;—-]*(.*)$", re.I | re.S)


def _first_then_stream(gen):
    """Дождаться первого события потока (ошибка сервера всплывёт здесь, до первого слова), дальше — потоком."""
    import itertools
    try:
        first = next(gen)
    except StopIteration:
        return iter(())
    return itertools.chain([first], gen)


def _has_images(x):
    if isinstance(x, dict):
        return x.get("type") in ("image", "image_url") or any(_has_images(v) for v in x.values())
    if isinstance(x, list):
        return any(_has_images(v) for v in x)
    return False


def _drop_images(x):
    """Сообщения без картинок: вместо них — пометка, что модель их не видит."""
    if isinstance(x, list):
        out = []
        for v in x:
            if isinstance(v, dict) and v.get("type") in ("image", "image_url"):
                out.append({"type": "text", "text": "(картинка есть, но эта модель не умеет смотреть картинки — "
                                                    "скажи об этом пользователю честно, не выдумывай, что на ней)"})
            else:
                out.append(_drop_images(v))
        return out
    if isinstance(x, dict):
        d = {k: _drop_images(v) for k, v in x.items()}
        c = d.get("content")
        if d.get("role") in ("user", "assistant") and isinstance(c, list) and c and \
                all(isinstance(v, dict) and v.get("type") == "text" for v in c):
            d["content"] = "\n".join(v.get("text", "") for v in c)      # остался только текст — обычной строкой
        return d
    return x


# всё, что ниже, видят части движка (engine_*.py): from engine_base import *
__all__ = [n for n in dict(globals()) if not n.startswith("__")]
