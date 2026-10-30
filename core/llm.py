"""«Мозг»: разговор с моделью — любой OpenAI-совместимый сервер (vLLM, Ollama, llama.cpp, LM Studio, OpenRouter,
OpenAI…), родной API Ollama (/api/chat) или Anthropic Claude.

stream_events() — поток ("text", кусок) и ("tools", вызовы). Сам подстраивается под сервер: что тот не принимает
(поле tools, роль tool, chat_template_kwargs, /chat/completions), запоминается по адресу в _no_tools, _flat, _native
до перезапуска. Здесь же: вырезание «размышлений» (ThinkStripper), вызовы функций из текста (ToolTagStripper,
parse_tool_call), проверка и поиск серверов (test_profile, probe_tools, probe_server, discover_local), подготовка
текста к озвучке (CodeFilter, SentenceSplitter, speakable). Способ вызова инструментов хранит engine_answer.py.
"""

import contextlib
import os
import json
import logging
import re
import sys
import time

import httpx

from settings import LLM_PRESETS

log = logging.getLogger("dewiar.llm")


class LLMError(Exception):
    """Ошибка с понятным человеку текстом."""


# Модели не хватило окна контекста: LM Studio «Context size has been exceeded», llama.cpp «exceeds the available context
# size», vLLM «maximum context length», OpenAI «context_length_exceeded» (19.10: LM Studio с окном 4096 — три сбоя за ночь)
CTX_RX = re.compile(r"context (?:size|length|window)[^.]{0,40}(?:exceed|too)|exceeds? (?:the )?(?:available |maximum )?context|"
                    r"maximum context length|context_length_exceeded|n_ctx|prompt is too long|too many tokens|"
                    r"превыш\w* (?:размер|длин)\w* контекст|не хватило окна контекста", re.I)
# деньги на ключе сервиса кончились — повтор через 5 минут не поможет (пакет 30.10: дело по расписанию — 16 неудач за день)
NO_MONEY_TEXT = "на ключе нет оплаченного пакета или закончились деньги — пополните баланс у сервиса"
CTX_TEXT = ("модели не хватило окна контекста — разговор и подсказка не помещаются. В LM Studio или Ollama увеличьте "
            "длину контекста (Context Length) до 8192 или больше")


# LM Studio сам выгружает модель по таймеру простоя (19.10: «Model is unloaded.») — следующий запрос её загрузит: один повтор
UNLOADED_RX = re.compile(r"model (?:is |was |has been )?unloaded|no models? (?:is )?loaded|model (?:is )?not loaded", re.I)


def ctx_full(e):
    """Ошибка — «не хватило контекста»?"""
    return bool(CTX_RX.search(str(e) or ""))


def _base(p):
    """Адрес сервера профиля. Пусто (профиль из старой копии настроек, студия до связи с ядром) — понятная ошибка, а не
    KeyError в журнале (пакет 22.10: «Команда llm_test упала: 'base_url'», «'NoneType' object has no attribute 'rstrip'»)."""
    b = str((p or {}).get("base_url") or "").strip().rstrip("/")
    if not b:
        raise LLMError("не указан адрес сервера модели — «Мозг» → профиль → «Адрес сервера»")
    return b


# Денег на ключе нет, а сервис отвечает 429 (Z.ai: «Insufficient balance or no resource package») — ждать и повторять
# бессмысленно: пакет 22.10 — по 3 повтора с ожиданием до минуты на каждый вопрос, человек минутами ждал тишину.
NO_MONEY_RX = re.compile(r"insufficient (balance|quota|funds)|no resource package|exceeded your current quota|"
                         r"credit balance is too low|payment required|недостаточно средств|"
                         r"no credits remaining|insufficient credits|can only afford|add (more )?credits|out of credits", re.I)   # №324, OpenRouter
LOCATION_RX = re.compile(r"location is not supported|unsupported_country|not available in your (country|region)", re.I)


LOCAL_HOST_RX = re.compile(r"^(localhost|127\.|0\.0\.0\.0|\[?::1)")
LAN_HOST_RX = re.compile(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)|\.local$")
LOCAL_APPS = (("Ollama", 11434), ("LM Studio", 1234), ("vLLM", 8000), ("llama.cpp", 8080))
# модели с таким именем у сервиса нет (OpenRouter: «… is not a valid model ID», Ollama: «model "x" not found»)
NO_MODEL_RX = re.compile(r"not a valid model|model\b[^\n]{0,80}?\b(not found|does not exist|not exist)|unknown model|invalid model|"
                         r"no such model|model_not_found", re.I)


_LOCAL_HOST = re.compile(r"^(?:localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|\[?::1)|\.local$|\.lan$")


def _local_base(base):
    """Адрес модели — этот компьютер или своя сеть (Ollama, LM Studio, llama.cpp, свой vLLM)."""
    host = (re.match(r"^\w+://\[?([^/:?#\]]+)", str(base or "")) or [None, ""])[1]
    return bool(host) and bool(_LOCAL_HOST.search(host))


def _port_open(host, port, timeout=0.35):
    import socket
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def ollama_installed():
    """Стоит ли Ollama на этом компьютере (запущена или нет)."""
    import shutil
    from pathlib import Path
    if shutil.which("ollama"):
        return True
    # №380 (28.10): Ollama 0.4 стояла не в %LOCALAPPDATA%\Programs — «Ollama не найдена, хотя установлена»
    cands = [Path(os.environ[v]) / sub for v, sub in (("LOCALAPPDATA", "Programs/Ollama"), ("LOCALAPPDATA", "Ollama"),
             ("ProgramFiles", "Ollama"), ("USERPROFILE", "scoop/apps/ollama")) if os.environ.get(v)]
    return any(c.is_dir() for c in cands)


def connect_hint(base_url):
    """Не подключились к своей модели — что именно не так и что сделать (отзыв 19.10: «сервер добавлен, проверен,
    доступен, но ассистент не хочет» — в ответ было только «сервер запущен и адрес верный?»). -> текст или ""."""
    from urllib.parse import urlparse
    u = urlparse(str(base_url or ""))
    host, port = (u.hostname or ""), (u.port or (443 if u.scheme == "https" else 80))
    if LOCAL_HOST_RX.match(host):
        other = [(n, pt) for n, pt in LOCAL_APPS if pt != port and _port_open("127.0.0.1", pt)]
        if other:
            n, pt = other[0]
            return (f"по адресу {base_url} никто не отвечает, а на этом компьютере работает {n} (порт {pt}) — в «Мозге» нажмите "
                    "«Найти»: адрес подставится сам")
        if port == 11434 and ollama_installed():
            return ("Ollama установлена, но не запущена — откройте её (меню приложений; в Windows — значок у часов) и "
                    "нажмите «Проверить» ещё раз")
        if port in (1234, 1235) and lmstudio_installed():
            return LMSTUDIO_HOW.rstrip(".").replace("«Найти»", "«Проверить»")
        return ("на этом компьютере не запущена программа с моделью (Ollama или LM Studio). Если модель на другом компьютере "
                "или сервере — впишите в «Мозге» его адрес (например 192.168.1.5:11434): 127.0.0.1 — это сам этот компьютер")
    if LAN_HOST_RX.search(host):
        return (f"компьютер {host} не отвечает на порту {port}. На нём должна быть запущена программа с моделью и открыт "
                "доступ из сети: в Ollama — переменная OLLAMA_HOST=0.0.0.0, в LM Studio — «Serve on Local Network». "
                "Ещё порт может закрывать брандмауэр того компьютера")
    return ""


def _humanize(e, base_url, model=""):
    """Ошибка сети или HTTP → короткое объяснение по-русски для окна и голоса."""
    if "Ничего не уходит в интернет" in str(e):           # стоп-кран (core/egress.py): модель в интернете — на паузе
        host = (re.match(r"^\w+://([^/:?#]+)", str(base_url or "")) or [None, "сервис"])[1]
        return (f"включён режим «Ничего не уходит в интернет», а модель ({host}) — в интернете. Подключите свою модель "
                "(Ollama, LM Studio) в «Мозге» или выключите режим: студия → «Безопасность»")
    if isinstance(e, httpx.ConnectError):
        host = (re.match(r"^\w+://([^/:?#]+)", str(base_url or "")) or [None, ""])[1]
        if host and not re.match(r"^(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[?::1)|\.local$", host):
            # облачный сервис (пакет 20.10, №140: «openrouter.ai — сервер запущен?» — человеку непонятно, что делать)
            return (f"не могу подключиться к {host} — нет интернета или сайт недоступен из вашей сети (провайдер бывает, что "
                    "блокирует). Помогут прокси («Подключение» → «Прокси») или облако Dewiar («Мозг» → «Dewiar Облако»)")
        try:
            hint = connect_hint(base_url)
        except Exception:  # noqa: BLE001 — подсказка не главное: без неё — как раньше
            hint = ""
        return f"не могу подключиться к {base_url}: {hint}" if hint else f"не могу подключиться к {base_url} — сервер запущен и адрес верный?"
    if isinstance(e, (httpx.RemoteProtocolError, httpx.ReadError)):
        # пакет 27.10: «Server disconnected without sending a response» показывали по-английски (перегрузка сервера)
        host = (re.match(r"^\w+://([^/:?#]+)", str(base_url or "")) or [None, "сервер модели"])[1]
        return f"{host} оборвал связь, не ответив, — он перегружен или перезапускается. Повторите через минуту"
    if isinstance(e, httpx.TimeoutException):
        return "сервер модели не ответил вовремя"
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        body = ""
        try:
            body = e.response.text[:200]
        except Exception:  # noqa: BLE001
            pass
        try:                                          # облако Dewiar и др. объясняют сами: «заряд закончился…»
            j = e.response.json()
            j = j[0] if isinstance(j, list) and j else j   # Gemini отдаёт ошибку списком: [{"error": …}]
            msg = ((j or {}).get("error") or {}).get("message", "") if isinstance(j, dict) else ""
        except Exception:  # noqa: BLE001
            msg = ""
        if LOCATION_RX.search(body + " " + msg):
            return ("Gemini недоступен из вашей страны — Google не пускает к API отсюда. Включите VPN или прокси "
                    "(«Подключение» → «Прокси»), подключите Gemini через OpenRouter или выберите другой сервис")
        if NO_MONEY_RX.search(body + " " + msg) and "Dewiar" not in msg:
            zai = "z.ai" in str(base_url or "")
            return (NO_MONEY_TEXT
                    + (". Подписка GLM Coding Plan работает по своему адресу (…/api/coding/paas/v4), и по правилам Z.ai — "
                       "только в программах для кода" if zai else ""))
        if msg and (code in (402, 429) or "Dewiar" in msg or "dw-" in msg):
            return msg.rstrip(".")
        if code == 402:
            return "на ключе закончились средства — пополните баланс"
        if code == 400 and re.search(r"does not support (chat|completion|generate)", body + " " + msg, re.I):
            # пакет 23.10: в Ollama выбрали x/flux2-klein — модель для картинок
            t = ((f"«{model}»" if model else "эта модель") + " не умеет разговаривать — это модель для картинок или поиска. ")
            try:
                ms = list_models({"base_url": base_url}, timeout=3) if base_url else None
            except Exception:  # noqa: BLE001 — список не получили (нужен ключ и т. п.) — обычный совет
                ms = None
            if ms is not None and not chat_models(ms):   # №258: выбрать было не из чего — говорим, где взять модель
                return t + no_chat_help(base_url, ms)
            return t + "В «Мозге» нажмите «Список моделей» и выберите модель для разговора"
        if code in (400, 404) and NO_MODEL_RX.search(body + " " + msg):
            name = f"«{model}»" if model else "с таким именем"
            if ":11434" in str(base_url or "") or "pulling" in body + msg:
                # №211, 23.10: Ollama работала, а llama3.2 в ней не скачана — человек час слышал «проверьте адрес»
                return (f"в Ollama нет модели {name} — её нужно сначала скачать: откройте приложение Ollama, выберите модель "
                        "внизу окна и напишите ей что-нибудь — она скачается. Уже скачанные — в «Мозге» → «Список моделей»")
            return f"у сервиса нет модели {name} — в «Мозге» нажмите «Список моделей» и выберите из списка"
        if code == 413 or re.search(r"request too large|tokens per minute|\bTPM\b", body + " " + msg, re.I):
            # пакет 28.10: «[groq/openai/gpt-oss-120b] [413]: Request too large… tokens per minute (TPM): Limit 8000» — у
            # бесплатного тарифа сервиса предел запроса меньше, чем нужно задаче или длинному разговору
            lim = re.search(r"Limit\s+(\d+)", body + " " + msg)
            return ("запрос не помещается в лимит этого сервиса" + (f" ({lim.group(1)} токенов в минуту)" if lim else "")
                    + " — у бесплатных тарифов он маленький. Для задач и длинных разговоров выберите в «Мозге» другую модель "
                    "или сервис с бо́льшим лимитом")
        if code in (503, 529) or (code >= 500 and BUSY_RX.search(body + " " + msg)):
            # пакет 24.10: «503 … This model is currently experiencing high demand» (Gemini) — 7 раз сырым JSON
            return ("сервис модели сейчас перегружен — это у него, не у вас. Повторите через минуту или выберите в «Мозге» "
                    "другую модель")
        if code in (401, 403):
            # пакет 27.10 (1437): «Задача: сервер отклонил ключ доступа» 8 раз — облако Dewiar объясняет причину словами
            # («Ключ Dewiar приостановлен…», «Пробный разговор выключен…») — её и показываем, а не общий совет про API-ключ
            if re.search(r"[а-яё]{4}", msg, re.I):
                return msg.strip().rstrip(".")
            return "сервер отклонил ключ доступа (проверьте API-ключ)"
        if code == 404:
            return "не найдено: проверьте адрес (обычно оканчивается на /v1) и имя модели"
        if CTX_RX.search(body) or CTX_RX.search(msg):
            return CTX_TEXT
        if re.search(r"jinja|No user query found|prompt template|chat template", body + " " + msg, re.I):
            # №281 (пакет 27.10): LM Studio «Error rendering prompt with jinja template: No user query found in messages»
            return ("у модели неисправный шаблон разговора (Prompt Template) — так бывает у некоторых сборок в LM Studio. "
                    "Возьмите ту же модель от lmstudio-community или в LM Studio → модель → «Prompt Template» верните шаблон по умолчанию")
        return f"сервер ответил ошибкой {code}: {body}"
    return str(e)


# Начало «размышлений вслух» без тегов: модель рассуждает про себя (часто по-английски), а потом пишет </think>
# (тег <think> уже стоит в шаблоне сервера) или «assistantfinal» (gpt-oss). Такое начало придерживаем, пока не станет ясно.
_REASON_START = re.compile(
    r"^\s*(okay|ok,|alright|so,|hmm|well,|let me|let's|let us|i need|i should|i'll|i will|i must|first,|we need|we have|we should|"
    r"the user|user (asks|wants|is|said)|looking at|analy[sz]|thinking|reasoning|"
    r"хорошо, пользовател[ьяю](?![а-яё])|итак, пользовател[ьяю](?![а-яё])|пользователь (спрашивает|просит|хочет|сказал|написал|пишет)|"
    r"мне нужно (понять|разобраться|ответить|вызвать|сначала)|так, пользовател[ьяю](?![а-яё]))", re.I)   # «Итак, пользовательские данные…» — это ответ, не рассуждение
_REASON_WORDS = {"okay", "ok", "alright", "so", "hmm", "well", "let", "i", "first", "we", "the", "user", "looking",
                 "analysis", "analyzing", "analysing", "analyze", "thinking", "reasoning", "хорошо", "итак", "пользователь",
                 "мне", "так"}
_FINAL_MARK = re.compile(r"</think>|<\|channel\|>final<\|message\|>|(?<![a-z])assistantfinal", re.I)
_HARMONY = re.compile(r"<\|[a-z_]+\|>")


class ThinkStripper:
    """Вырезает размышления «думающих» моделей прямо из потока: <think>…</think>, а также рассуждение без
    открывающего тега (…</think> ответ) и формат gpt-oss (analysis… assistantfinal ответ).
    Начало ответа придерживается, пока не ясно, рассуждение это или ответ (обычно — первые ~60 символов)."""

    GATE = 60            # столько символов начала смотрим, прежде чем отдавать текст
    CAP = 20000          # дальше не ждём конца рассуждения

    def __init__(self):
        self.buf, self.inside = "", False
        self.gate = True     # начало ответа ещё не отдано
        self.dropped = 0     # сколько символов рассуждений выброшено (для «модель только думала»)

    def _gate(self):
        """Решить судьбу начала ответа. -> "" — ещё не ясно, ждём; None — решено (рассуждение срезано
        или его нет), буфер разбирает основной цикл feed()."""
        b = self.buf
        m = _FINAL_MARK.search(b)
        if m:                                             # всё до метки — рассуждение
            self.dropped += m.start()
            self.buf, self.gate, self.inside = b[m.end():].lstrip(), False, False
            return None
        i = b.find("<think>")
        if i >= 0 and not b[:i].strip():
            self.gate = False                             # обычный <think>…</think> — разберёт основной цикл
            return None
        lead = b.lstrip()
        if _REASON_START.match(lead) or lead.lower().startswith(("analysis", "<|start|>", "<|channel|>")):
            if len(b) < self.CAP:
                return ""                                 # похоже на рассуждение — ждём метку конца
            self.gate = False                             # слишком долго — отдаём как есть
            return None
        w = re.match(r"([^\W\d_]+)[\W\d_]", lead)
        if w and w.group(1).lower() not in _REASON_WORDS:  # первое слово — не начало рассуждения: отдаём сразу
            self.gate = False
            return None
        if len(lead) < self.GATE and "\n" not in lead.strip():
            return ""
        self.gate = False
        return None

    def feed(self, s):
        """Очередной кусок потока -> текст, который уже можно отдать (может быть пустым)."""
        self.buf += s
        if self.gate:
            if self._gate() == "":
                return ""
        out = ""
        while True:
            if self.inside:
                i = self.buf.find("</think>")
                if i < 0:
                    self.dropped += max(0, len(self.buf) - 8)
                    self.buf = self.buf[-8:]
                    return self._clean(out)
                self.dropped += i
                self.buf, self.inside = self.buf[i + 8:], False
            else:
                i = self.buf.find("<think>")
                if i < 0:
                    keep = 0
                    for k in range(1, 9):                       # возможно, тег разрезан на куски
                        if self.buf.endswith("</think>"[:k]) or self.buf.endswith("<think>"[:k]):
                            keep = max(keep, k)
                    out += self.buf[:len(self.buf) - keep]
                    self.buf = self.buf[len(self.buf) - keep:]
                    return self._clean(out)
                out += self.buf[:i]
                self.buf, self.inside = self.buf[i + 7:], True

    @staticmethod
    def _clean(t):
        return _HARMONY.sub("", t.replace("</think>", ""))

    def finish(self):
        """Конец ответа: что осталось в запасе. Начало так и не прояснилось и похоже на рассуждение без ответа — ""."""
        b, self.buf = self.buf, ""
        if self.inside:
            self.dropped += len(b)
            return ""
        if self.gate:
            self.gate = False
            m = _FINAL_MARK.search(b)
            if m:
                self.dropped += m.start()
                return self._clean(b[m.end():].strip())
            letters = re.findall(r"[A-Za-zА-Яа-яЁё]", b[:1500])
            latin = sum(c.isascii() for c in letters) / max(1, len(letters))
            if _REASON_START.match(b.lstrip()) and len(b) > 400 and (latin > 0.5 or re.search(r"пользовател[ьяю](?![а-яё])", b[:300], re.I)):
                self.dropped += len(b)                    # длинное рассуждение без ответа (по-английски или «пользователь …»)
                return ""
        return self._clean(b)


def _headers(p):
    key = (p.get("api_key") or "").strip()
    if key and not key.isascii():
        raise LLMError("в ключе API есть русские буквы или лишние символы — скопируйте ключ заново (раздел «Мозг»)")
    p = dict(p, api_key=key)
    h = {"Content-Type": "application/json"}
    if p.get("kind") == "anthropic":
        h["x-api-key"] = p.get("api_key", "")
        h["anthropic-version"] = "2023-06-01"
    elif p.get("api_key"):
        h["Authorization"] = f"Bearer {p['api_key']}"
    return h


_NOT_CHAT = re.compile(r"embed|rerank|ocr|whisper|tts|asr|speech|stt|clip|bge|e5-|guard|moderat", re.I)


def pick_model(models):
    """Из списка сервера выбрать модель для разговора: не эмбеддинги, не реранкер, не речь.
    Предпочтение — псевдонимы chat/llm/default, затем названия с chat/instruct, затем известные семейства
    (qwen, llama, mistral…), затем первая подходящая."""
    ok = [m for m in models if not _NOT_CHAT.search(m)]
    if not ok:
        return models[0] if models else ""
    for pref in ("chat", "llm", "default"):
        if pref in ok:
            return pref
    for rx in (r"chat|instruct", r"qwen|llama|mistral|gemma|glm|deepseek|phi"):
        hit = [m for m in ok if re.search(rx, m, re.I)]
        if hit:
            return hit[0]
    return ok[0]


def chat_models(models):
    """Из списка — только модели для разговора (без эмбеддингов, реранкеров, речи)."""
    return [m for m in (models or []) if m and not _NOT_CHAT.search(m)]


def no_chat_help(base_url, models=None):
    """Пакет 25.10, №258: «загрузил qwen3:4b и qwen3:8b, а в списке только модель, которая не умеет разговаривать».
    В Ollama была скачана лишь nomic-embed-text (для поиска по смыслу), а qwen3 — в LM Studio. Объясняем, где модели
    и что сделать; если LM Studio на этом компьютере отвечает и в ней есть модели для разговора — называем их."""
    base = str(base_url or "")
    side = [m for m in (models or []) if m and _NOT_CHAT.search(m)]
    what = (f"есть только {', '.join('«' + m + '»' for m in side[:2])} — это модель для поиска по смыслу, разговаривать она не умеет"
            if side else "нет ни одной модели")
    ollama = ":11434" in base or base in _native
    lms = []
    if ":1234" not in base:
        try:
            r = httpx.get("http://127.0.0.1:1234/v1/models", timeout=1.0)
            if r.status_code == 200:
                lms = chat_models([m.get("id") for m in r.json().get("data", []) if isinstance(m, dict)])
        except Exception:  # noqa: BLE001 — LM Studio нет или выключена
            lms = []
    if ollama:
        t = (f"В Ollama {what}. Скачайте модель для разговора: «Пуск» → «Командная строка» → ollama pull qwen3:4b "
             "(≈2,5 ГБ; для мощного компьютера — qwen3:8b), затем снова «Список моделей»")
    else:
        t = f"На этом сервере {what}. Загрузите в нём модель для разговора (например, Qwen3) и нажмите «Список моделей» снова"
    if lms:
        names = ", ".join("«" + m + "»" for m in lms[:3])
        t += (f". А в LM Studio на этом компьютере модели для разговора уже есть: {names} — в «Мозге» нажмите «Добавить» → "
              "«LM Studio», и Dewiar будет думать ими")
    return t


def _root(base):
    """Адрес без /v1 — для родного API Ollama (/api/tags, /api/chat)."""
    return re.sub(r"/v1/?$", "", base.rstrip("/"))


_native = set()       # адреса, где работает только родной API Ollama (/api/chat)


def _anth_root(base):
    """Адрес Anthropic-совместимого сервиса без хвоста /v1: путь /v1/messages дописываем сами. Вписали «…/v1» (так у
    агрегаторов в документации) — раньше выходило …/v1/v1/messages и «не найдено» (пакет 20.10)."""
    base = str(base or "").rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


_ctx_cache = {}


def context_window(p, model=None, timeout=3):
    """Окно контекста загруженной модели своего сервера -> число токенов или None (не узнать: облако, старый сервер).
    LM Studio: /api/v0/models (loaded_context_length — как модель загружена сейчас); Ollama: /api/ps (context_length
    запущенной модели); vLLM: /models (max_model_len). Помним 10 минут на (адрес, модель): спрашиваем перед вопросом без задержки.
    Зачем (29.10, пакет: «не влезло в окно модели» — 102 за неделю; Ollama с окном 4096 молча отрезает начало подсказки —
    характер и инструменты — и отвечает «не тем»): знать окно заранее и сразу говорить коротко, а не падать."""
    try:
        base = _base(p)
    except LLMError:
        return None
    model = model or p.get("model") or ""
    key = (base, model)
    hit = _ctx_cache.get(key)
    if hit and time.monotonic() - hit[1] < 600:
        return hit[0]
    n = None
    root = _root(base)
    try:
        r = httpx.get(root + "/api/v0/models", headers=_headers(p), timeout=timeout)          # LM Studio
        if r.status_code == 200 and isinstance(r.json().get("data"), list):
            data = r.json()["data"]
            m = next((x for x in data if x.get("id") == model), None) or next((x for x in data if x.get("state") == "loaded"), None)
            if m:
                n = m.get("loaded_context_length") or m.get("max_context_length")
        if n is None:
            r = httpx.get(root + "/api/ps", headers=_headers(p), timeout=timeout)              # Ollama
            if r.status_code == 200 and isinstance(r.json().get("models"), list):
                ms = r.json()["models"]
                m = next((x for x in ms if model and (x.get("name") == model or x.get("model") == model)), None) or (ms[0] if ms else None)
                if m:
                    n = m.get("context_length")
        if n is None:
            r = httpx.get(base + "/models", headers=_headers(p), timeout=timeout)                # vLLM: max_model_len
            if r.status_code == 200 and isinstance(r.json().get("data"), list):
                data = r.json()["data"]
                m = next((x for x in data if x.get("id") == model), None) or (data[0] if len(data) == 1 else None)
                if m:
                    n = m.get("max_model_len") or m.get("context_length")
    except Exception:  # noqa: BLE001 — не узнали — не страшно
        n = None
    try:
        n = int(n) if n else None
    except (TypeError, ValueError):
        n = None
    _ctx_cache[key] = (n, time.monotonic())
    return n


def est_tokens(text):
    """Грубо, с запасом: сколько токенов займёт текст (русский — около 3 знаков на токен у Qwen/Llama)."""
    return len(text or "") // 3 + 1


def list_models(p, timeout=6):
    """-> имена моделей на сервере профиля p. Если /models нет (404), а /api/tags есть — это Ollama без
    OpenAI-совместимого API: адрес запоминается в _native. Ошибки — LLMError с понятным текстом."""
    base = _base(p)
    try:
        if p.get("kind") == "ollama" or base in _native:
            r = httpx.get(_root(base) + "/api/tags", headers=_headers(p), timeout=timeout)
            r.raise_for_status()
            return [m.get("name") or m.get("model") for m in r.json().get("models", [])]
        url = (_anth_root(base) + "/v1/models") if p.get("kind") == "anthropic" else base + "/models"
        r = httpx.get(url, headers=_headers(p), timeout=timeout)
        if r.status_code == 404 and p.get("kind") != "anthropic":
            r2 = httpx.get(_root(base) + "/api/tags", headers=_headers(p), timeout=timeout)
            if r2.status_code == 200:
                _native.add(base)
                return [m.get("name") or m.get("model") for m in r2.json().get("models", [])]
        r.raise_for_status()
        data = r.json().get("data", [])
        ids = [m.get("id") for m in data if m.get("id")]
        ids = [x[7:] if x.startswith("models/") else x for x in ids]      # Gemini: «models/gemini-…» — в ответах без «models/»
        # не для разговора: голос, распознавание, картинки, видео, модерация — их выбирали «первой по алфавиту»
        ids = [x for x in ids if not re.search(r"(^|[-_/])(tts|whisper|transcribe|dall-e|imagen|veo|moderation|aqa)([-_.]|$)|image-|-image\b|audio|"
                                                r"(^|[-_/:])(flux\d*|sdxl|stable-diffusion)", x, re.I)] or ids
        # модели для поиска по смыслу (эмбеддинги, реранкеры) разговаривать не умеют — в конец списка, отдельно (№144:
        # LM Studio отдаёт и их; выбрали text-embedding-nomic… как модель разговора)
        side = [x for x in ids if re.search(r"embed|rerank", x, re.I)]
        return [x for x in ids if x not in side] + side
    except LLMError:
        raise
    except Exception as e:  # noqa: BLE001
        raise LLMError(_humanize(e, base)) from e


def _ctx_cut(messages):
    """Короткая история: только текущая просьба и то, что модель уже сделала по ней (вызовы и результаты)."""
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if m.get("role") == "user" and isinstance(m.get("content"), (str, list)) and not m.get("tool_call_id"):
            return messages[i:]
    return messages[-1:]


def _ctx_retry(p, system, messages, cancel, tools, _retry, e):
    """Не хватило окна контекста — один раз повторить с короткой историей; снова мало — понятная ошибка с советом."""
    short = _ctx_cut(messages)
    if p.get("_ctx") or len(short) >= len(messages):
        raise LLMError(CTX_TEXT) from e
    log.warning("Модели %s не хватило окна контекста (%s) — повторяю с короткой историей: %d → %d сообщений",
                p.get("model"), str(e)[:120], len(messages), len(short))
    yield from stream_events(dict(p, _ctx=True), system, short, cancel, tools, _retry)


_model_cache = {}


def resolve_model(p):
    """Модель из профиля, а если не указана — выбранная pick_model (запоминается по адресу до перезапуска)."""
    if p.get("model"):
        return p["model"]
    key = _base(p)
    if key not in _model_cache:
        models = list_models(p)
        if not models:
            raise LLMError("сервер не отдал ни одной модели — укажите модель вручную")
        _model_cache[key] = pick_model(models)
        log.info("Модель не указана — из %s выбрал «%s»", models[:12], _model_cache[key])
    return _model_cache[key]


# Признаки того, что сервер отклонил сам запрос (формат, роли, функции), а не упал: тогда упрощаем и повторяем.
_REJECT = re.compile(r"\b4(00|22)\b|invalid|unsupported|roles must alternate|cannot parse|bad request|tool|function", re.I)
_no_tools = set()          # серверы, которые отказались принимать инструменты (vLLM без --enable-auto-tool-choice)
_flat = set()              # серверы, которые не принимают историю вызовов (роль tool, tool_calls) — пишем её текстом
_no_kw = set()             # серверы, которые отклоняют запрос с chat_template_kwargs (облако Ollama: «upstream returned HTTP 400»)


def _has_tool_history(messages):
    return any(m.get("role") == "tool" or m.get("tool_calls") for m in messages)


def flat_messages(messages):
    """История вызовов инструментов — текстом (<tool_call>/<tool_response>), без ролей tool и полей tool_calls.
    Так её принимает любой сервер: Ollama с облачными моделями («upstream returned HTTP 400»), шлюзы, старый vLLM."""
    out = []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if role == "assistant" and m.get("tool_calls"):
            calls = ""
            for c in m["tool_calls"]:
                f = c.get("function") or {}
                args = f.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args or "{}")
                    except ValueError:
                        args = {"raw": args}
                calls += "<tool_call>\n" + json.dumps({"name": f.get("name"), "arguments": args}, ensure_ascii=False) + "\n</tool_call>"
            text = content if isinstance(content, str) else ""
            out.append({"role": "assistant", "content": (text.strip() + "\n" if text.strip() else "") + calls})
            continue
        if role == "tool":
            t = f"<tool_response>\n{content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)}\n</tool_response>"
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], str) and out[-1]["content"].startswith("<tool_response>"):
                out[-1] = {"role": "user", "content": out[-1]["content"] + "\n" + t}
            else:
                out.append({"role": "user", "content": t})
            continue
        m = {k: v for k, v in m.items() if k in ("role", "content")}
        if m.get("content") is None:
            m["content"] = ""
        if out and out[-1]["role"] == m["role"] == "user" and isinstance(out[-1]["content"], str) and isinstance(m["content"], str):
            out[-1] = {"role": "user", "content": out[-1]["content"] + "\n\n" + m["content"]}
        else:
            out.append(m)
    return out


def _clean_messages(messages):
    """Пустой текст ассистента — "" а не null: часть серверов отклоняет null."""
    return [dict(m, content="") if m.get("content") is None and m.get("role") == "assistant" else m for m in messages]
# Лимит ответа, если в профиле не задан: при меньшем ответ обрывается, когда модель начинает размышлять,
# а аргументы инструментов (файл, страница) не помещаются целиком.
DEFAULT_MAX_TOKENS = 2048



def stream_chat(p, system, messages, cancel=None):
    """Только текст (для проверки соединения и простых ответов)."""
    for kind, val in stream_events(p, system, messages, cancel):
        if kind == "text":
            yield val


def _to_ollama(messages):
    """Сообщения в формате OpenAI → родной формат Ollama (картинки отдельным списком base64)."""
    out = []
    for m in messages:
        m = dict(m)
        c = m.get("content")
        if isinstance(c, list):
            m["content"] = " ".join(x.get("text", "") for x in c if x.get("type") == "text")
            imgs = [x["image_url"]["url"].split(",", 1)[-1] for x in c if x.get("type") == "image_url"]
            if imgs:
                m["images"] = imgs
        if m.get("tool_calls"):
            m["tool_calls"] = [{"function": {"name": t["function"]["name"],
                                             "arguments": json.loads(t["function"].get("arguments") or "{}")}}
                               for t in m["tool_calls"]]
        m["content"] = m.get("content") or ""
        m.pop("tool_call_id", None)
        out.append(m)
    return out


# вызов голым JSON прямо в тексте: {"name": "money_report", "arguments": {…}} — часто с одиноким «</tool_call>» после
# (модель забыла открывающий тег). Узнаём по имени-идентификатору и ключу аргументов сразу за ним — обычный JSON для
# человека («{"name": "Иван", "age": 30}») так не выглядит.
_BARE_CALL = re.compile(r'\{\s*"(?:name|tool_name|function_name|tool)"\s*:\s*"[A-Za-z_][\w.-]*"\s*,\s*'
                        r'"(?:arguments|args|parameters|params|input)"\s*:')


# DeepSeek (V3.2+) пишет вызовы своим языком DSML, а не <tool_call> (пакет 27.10, №301: в ответе было видно
# «<｜DSML｜invoke name="weather">…», вызов не выполнялся, а температура дальше была выдуманной):
#   <｜DSML｜function_calls><｜DSML｜invoke name="weather"><｜DSML｜parameter name="city" string="true">Москва</｜DSML｜parameter>
#   </｜DSML｜invoke></｜DSML｜function_calls>
# Переводим в привычный <tool_call>{json}</tool_call> ещё в потоке — дальше всё как у Qwen.
# №348 (пакет 27.10, DeepSeek v4.1 через polza.ai): «<DSML calls><DSML invoke name="lab_write"><DSML parameter name="arguments"
# string="false">{json}» — без «｜», «calls» вместо «function_calls», все аргументы одним JSON — модель читала это вслух.
_DO = r"<\s*[｜|]?\s*DSML\s*[｜|]?\s*"
_DC = r"</\s*[｜|]?\s*DSML\s*[｜|]?\s*"
_DSML_OPEN = re.compile(_DO + r"(?:function_calls|tool_calls|calls|invoke)\b")
_DSML_END = re.compile(_DC + r"(?:function_calls|tool_calls|calls)\s*>|" + _DC + r"invoke\s*>(?![\s\S]*" + _DO + r"invoke)")
_DSML_INVOKE = re.compile(_DO + r"invoke\s+name=\"([^\"]+)\"\s*>([\s\S]*?)(?:" + _DC + r"invoke\s*>|$)")
_DSML_STRAY = re.compile(_DC + r"(?:function_calls|tool_calls|calls)\s*>")     # внешний «</DSML calls>» после invoke
_DSML_PARAM = re.compile(_DO + r"parameter\s+name=\"([^\"]+)\"(?:\s+string=\"(true|false)\")?\s*>([\s\S]*?)" + _DC + r"parameter\s*>")
_DSML_HEAD = "<｜DSML｜function_calls>"


def dsml_calls(text):
    """Текст с DSML -> строка из <tool_call>{json}</tool_call> (пустая — вызовов нет)."""
    out = []
    for name, body in _DSML_INVOKE.findall(text or ""):
        args = {}
        for k, is_str, v in _DSML_PARAM.findall(body):
            v = v.strip()
            if is_str == "false":
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
            args[k] = v
        if list(args) == ["arguments"] and isinstance(args["arguments"], dict):    # все аргументы одним JSON (№348)
            args = args["arguments"]
        out.append("<tool_call>" + json.dumps({"name": name, "arguments": args}, ensure_ascii=False) + "</tool_call>")
    return "".join(out)


class DSMLFilter:
    """Поток текста -> тот же поток, где блоки DSML заменены на <tool_call>. Начало «<｜DSML…», разрезанное между
    кусками, придерживается."""

    def __init__(self):
        self.buf, self.inside = "", False

    def feed(self, s):
        self.buf += s
        out = ""
        while True:
            if self.inside:
                m = _DSML_END.search(self.buf)
                if not m:
                    return out
                out += dsml_calls(self.buf[:m.end()])
                self.buf, self.inside = self.buf[m.end():], False
                continue
            m = _DSML_OPEN.search(self.buf)
            st = _DSML_STRAY.search(self.buf)
            if st and (not m or st.start() < m.start()):          # хвост «</DSML calls>» — убрать
                out += self.buf[:st.start()]
                self.buf = self.buf[st.end():]
                continue
            if m:
                out += self.buf[:m.start()]
                self.buf, self.inside = self.buf[m.start():], True
                continue
            keep = 0
            for tag in (_DSML_HEAD, "<｜DSML｜invoke", "<|DSML|invoke", "<|DSML|function_calls", "<DSML calls", "<DSML invoke", "</DSML calls>", "</DSML function_calls>", "</｜DSML｜function_calls>", "</|DSML|function_calls>"):
                for k in range(1, len(tag)):
                    if self.buf.endswith(tag[:k]):
                        keep = max(keep, k)
            out += self.buf[:len(self.buf) - keep]
            self.buf = self.buf[len(self.buf) - keep:]
            return out

    def tail(self):
        t, self.buf = self.buf, ""
        if self.inside:
            self.inside = False
            return dsml_calls(t) or t
        return t


class ToolTagStripper:
    """Вызовы функций прямо в тексте ответа — <tool_call>{json}</tool_call> (родной формат Qwen/Hermes).
    Нужен, когда сервер сам их не разбирает (vLLM без --tool-call-parser) или функции описаны в тексте
    (tools_prompt). Такие куски вырезаются из текста и не озвучиваются; calls() -> разобранные вызовы.
    Так же — вызов голым JSON посреди текста ({"name": …, "arguments": …}) и одинокий «</tool_call>» без открывающего.
    Текст после вызова не отдаётся: результата функции ещё нет — дальше модель сочиняет его сама (настоящий ответ
    будет следующим ходом, с результатом)."""

    OPEN, CLOSE = "<tool_call>", "</tool_call>"

    def __init__(self):
        self.buf, self.inside, self.found, self.after, self.dropped = "", False, [], False, ""
        self.known = set()          # имена функций этого запроса: голый JSON с другим именем (или без функций) — текст
        self.dsml = DSMLFilter()    # вызовы DeepSeek (DSML) — сначала в <tool_call>

    def _bare_end(self):
        """inside == "bare": конец JSON вызова в buf -> индекс после него или -1 (ещё не пришёл целиком)."""
        try:
            _, end = json.JSONDecoder().raw_decode(self.buf)
            return end
        except ValueError:
            return -1

    def feed(self, s):
        self.buf += self.dsml.feed(s)
        out = ""
        while True:
            if self.inside == "bare":
                end = self._bare_end()
                if end < 0:
                    return out
                try:
                    name = _call_parts(json.loads(self.buf[:end]))[0]
                except (ValueError, TypeError, AttributeError):
                    name = None
                if name not in self.known:                 # не наша функция — это просто текст с JSON
                    if self.after:
                        self.dropped += self.buf[:end]
                    else:
                        out += self.buf[:end]
                    self.buf, self.inside = self.buf[end:], False
                    continue
                self.found.append(self.buf[:end])
                rest = self.buf[end:].lstrip()
                if rest.startswith(self.CLOSE):
                    rest = rest[len(self.CLOSE):]
                elif self.CLOSE.startswith(rest) and rest:
                    self.buf, self.after = rest, True       # «</tool_» — дождёмся конца тега
                    self.inside = "close"
                    return out
                self.buf, self.inside, self.after = rest, False, True
            elif self.inside == "close":
                if self.buf.startswith(self.CLOSE):
                    self.buf = self.buf[len(self.CLOSE):]
                elif self.CLOSE.startswith(self.buf):
                    return out
                self.inside = False
            elif self.inside:
                i = self.buf.find(self.CLOSE)
                if i < 0:
                    return out
                self.found.append(self.buf[:i])
                self.buf, self.inside, self.after = self.buf[i + len(self.CLOSE):], False, True
            else:
                cands = [(k, kind) for k, kind in ((self.buf.find(self.OPEN), "open"), (self.buf.find(self.CLOSE), "stray"))
                         if k >= 0]
                m = _BARE_CALL.search(self.buf) if self.known else None
                if m:
                    cands.append((m.start(), "bare"))
                if not cands:
                    keep = 0
                    for tag in (self.OPEN, self.CLOSE):
                        for k in range(1, len(tag)):
                            if self.buf.endswith(tag[:k]):
                                keep = max(keep, k)
                    b = self.buf.rfind("{") if self.known else -1   # «{"name": "mo…» — может оказаться вызовом, придержим
                    if b >= 0 and "}" not in self.buf[b:] and len(self.buf) - b < 160:
                        keep = max(keep, len(self.buf) - b)
                    if not self.after:
                        out += self.buf[:len(self.buf) - keep]
                    else:
                        self.dropped += self.buf[:len(self.buf) - keep]
                    self.buf = self.buf[len(self.buf) - keep:]
                    return out
                k, kind = min(cands)
                if not self.after:
                    out += self.buf[:k]
                else:
                    self.dropped += self.buf[:k]
                if kind == "open":
                    self.buf, self.inside = self.buf[k + len(self.OPEN):], True
                elif kind == "stray":                       # «</tool_call>» без открывающего: JSON перед ним уже
                    self.buf = self.buf[k + len(self.CLOSE):]   # разобран как голый вызов или был текстом — тег не читаем
                else:
                    self.buf, self.inside = self.buf[k:], "bare"

    def tail(self):
        """Конец потока: придержанное на случай разрезанного «<tool_call>» — оказалось обычным текстом."""
        rest = self.dsml.tail()
        if rest:
            out = self.feed("")
            self.buf += rest
            out2 = self.feed("")
            if out + out2:
                return out + out2 + (self.tail() or "")
        if self.inside:
            return ""
        t, self.buf = self.buf, ""
        if self.after:                                  # текст после вызова — только если вызов так и не разобрался
            return "" if any(parse_tool_call(r) for r in self.found) else self.dropped + t
        return t

    def calls(self):
        if self.inside in (True, "bare") and self.buf.strip():   # модель не закрыла тег или JSON — берём как есть
            self.found.append(self.buf)
            self.buf, self.inside = "", False
        out = []
        for raw in self.found:
            c = parse_tool_call(raw)
            if c:
                out.append(c)
            else:
                log.warning("Вызов функции в тексте не разобран: %r", raw[:300])
        return out


def _arg_value(v):
    v = v.strip()
    try:
        return json.loads(v)                            # числа, true/false, списки, объекты
    except ValueError:
        return v


_NAME_KEYS = ("name", "tool_name", "tool", "function_name")
_ARGS_KEYS = ("arguments", "args", "parameters", "params", "input", "tool_input", "action_input")


def _call_parts(obj):
    """{"name"|"tool_name"|"tool"|"function": …, "arguments"|"args"|"parameters"|"input": …} -> (имя, аргументы).
    Модели без родных функций пишут вызов кто как (Ollama с «chat»: {"tool_name": …, "arguments": …})."""
    fn = obj.get("function")
    if isinstance(fn, dict):
        return fn.get("name"), fn.get("arguments", next((obj[k] for k in _ARGS_KEYS if k in obj), {}))
    name = next((obj[k] for k in _NAME_KEYS if isinstance(obj.get(k), str) and obj[k].strip()), None) \
        or (fn if isinstance(fn, str) else None)
    return name, next((obj[k] for k in _ARGS_KEYS if k in obj), {})


class BareCallCatcher:
    """Вызов функции голым JSON без тегов: модель в режиме «функции текстом» пишет весь ответ как
    {"tool_name": "write_file", "arguments": {...}} (или ```json …```, или несколько таких подряд).
    Ответ, который начинается с «{» или «`», придерживаем до конца: если это вызовы известных функций — это действия,
    а не текст (его не озвучиваем и не считаем «рассуждением»); иначе отдаём текст как был."""

    def __init__(self, known):
        self.known, self.mode, self.buf = set(known or ()), None, ""

    def feed(self, s):
        if not self.known or self.mode == "pass":
            return s
        self.buf += s
        if self.mode is None:
            head = self.buf.lstrip()
            if not head:
                return ""
            self.mode = "hold" if head[0] in "{`" else "pass"
            if self.mode == "pass":
                out, self.buf = self.buf, ""
                return out
        return ""

    def finish(self):
        """-> (текст, вызовы)."""
        buf, self.buf = self.buf, ""
        if self.mode != "hold":
            return buf, []
        calls = self.parse(buf, self.known)
        return ("", calls) if calls else (buf, [])

    @staticmethod
    def parse(text, known):
        t = re.sub(r"```[a-zA-Z]*|</?tool_call>", " ", text).strip()
        dec, i, out = json.JSONDecoder(), 0, []
        while i < len(t):
            if t[i].isspace() or t[i] in ",;":
                i += 1
                continue
            try:
                obj, i = dec.raw_decode(t, i)
            except ValueError:
                obj = repair_json(t[i:])                 # ответ оборвался по длине посреди аргументов
                if not isinstance(obj, dict):
                    return []
                name, args = _call_parts(obj)
                if isinstance(args, dict):
                    obj = dict(obj, **{k: dict(args, _truncated=True) for k in _ARGS_KEYS if k in obj})
                i = len(t)
            for o in (obj if isinstance(obj, list) else [obj]):
                name, args = _call_parts(o) if isinstance(o, dict) else (None, None)
                if name not in known:
                    return []
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {"_raw": args}
                out.append({"name": name, "args": args if isinstance(args, dict) else {}})
        return out


# путь Windows в тексте вызова: «D:\…» или «\\сервер\…» после кавычки, пробела или скобки (GitHub №29)
WIN_PATH_RX = re.compile(r"""((?:^|(?<=[\s"'(=:,\[{]))(?:[A-Za-z]:|\\\\(?=\w)))((?:\\+[^\\"\s<>|*?]+)+\\*)""")


def _loads_loose(s):
    """json.loads, а не вышло — мягче (№390, 28.10: «Вызов функции в тексте не разобран» — run_python с кодом, где модель
    написала настоящие переводы строк внутри строки и «\\'» — JSON их не принимает, задача «застряла»): переводы строк и
    табы внутри строк (strict=False), «\\'» → «'», чужие экранирования «\\в» → «\\\\в». -> объект или None."""
    try:
        return json.loads(s)
    except ValueError:
        pass
    # GitHub №29 (29.10): «D:\\Demo\\new\\test.txt» без экранирования — «\\n» и «\\t» в пути становились переводом строки и
    # табуляцией. Путь Windows (буква диска или \\\\сервер) — обратные слеши в нём буквальные: удваиваем до разбора
    s = WIN_PATH_RX.sub(lambda m: m.group(1) + re.sub(r"\\+", lambda b: "\\\\", m.group(2)), s)
    t = re.sub(r"\\(.)", lambda m: m.group(0) if m.group(1) in '"\\/bfnrtu' else ("'" if m.group(1) == "'" else "\\\\" + m.group(1)), s, flags=re.S)
    try:
        return json.loads(t, strict=False)
    except ValueError:
        return None


def parse_tool_call(raw):
    """Вызов функции из текста ответа → {"name", "args"} или None. Модели пишут его по-разному:
      Qwen/Hermes:   {"name": "f", "arguments": {...}}
      GLM-4.5/5:     f<arg_key>k</arg_key><arg_value>v</arg_value>…
      Qwen3-Coder:   <function=f><parameter=k>v</parameter>…</function>
      и просто:      f {"k": "v"}   или   f"""
    raw = (raw or "").strip()
    if not raw:
        return None
    if "<tool_call>" in raw:                           # 0.38.49: первый вызов оборван, следом второй в своём <tool_call>
        for part in reversed([x for x in raw.split("<tool_call>") if x.strip()]):
            c = parse_tool_call(part)
            if c:
                return c
        return None
    # экзамен 0.38.46 (Qwen): «<\n\nfunction=code_list>» — переводы строк внутри тега
    raw = re.sub(r"<\s*(function|parameter)\s*=\s*", r"<\1=", raw)
    raw = re.sub(r'^<\s*(function|name|tool)"\s*:', r'{"\1":', raw)       # 0.38.48: «<function": "web_search", "arguments": {…}}»
    m = re.search(r"<function=([\w.\-]+)>(.*?)(?:</function>|$)", raw, re.S)
    if m:
        args = {k: _arg_value(v) for k, v in re.findall(r"<parameter=([\w.\-]+)>(.*?)(?:</parameter>|(?=<parameter=)|$)", m.group(2), re.S)}
        if not args:                                   # <function=code_read><path>a.py</path></function> — ключи тегами
            args = {k: _arg_value(v) for k, v in re.findall(r"<([A-Za-z_][\w\-]*)>(.*?)</\1>", m.group(2), re.S)}
        return {"name": m.group(1), "args": args}
    m = re.match(r"([A-Za-z_][\w.\-]*)\s*(.*)$", raw, re.S)
    nm = re.match(r'^\{?\s*"?(?:function\s+name|function_name|name)\s*=\s*"?([A-Za-z_][\w.\-]*)"?\s*\}?\s*$', raw)
    if nm:                                             # 0.38.49: {"function name="set_reminder"} — одно имя, без аргументов
        return {"name": nm.group(1), "args": {}}
    if m and "<arg_key>" in m.group(2):
        pairs = re.findall(r"<arg_key>\s*(.*?)\s*</arg_key>\s*<arg_value>(.*?)</arg_value>", m.group(2), re.S)
        return {"name": m.group(1), "args": {k: _arg_value(v) for k, v in pairs}}
    # экзамен 14.10 (Qwen): перевод строки внутри ключа — {"\n\nname": …}; имя функции первой строкой — {"use_skill", "name": …}
    raw = re.sub(r'"\s+(name|arguments|parameters|function)"(\s*:)', r'"\1"\2', raw)
    bare = re.match(r'\{\s*"([A-Za-z_][\w.\-]*)"\s*,\s*(.*)\}\s*$', raw, re.S)
    if bare:
        try:
            rest = json.loads("{" + bare.group(2) + "}")
            if isinstance(rest, dict):
                return {"name": bare.group(1), "args": rest}
        except ValueError:
            pass
    # экзамен 0.38.46: имя отдельным объектом, аргументы — следующим: {"function": "show_images"}\n{"query": …}
    two = re.match(r'\{\s*"(?:function|name|tool|tool_name)"\s*:\s*"([A-Za-z_][\w.\-]*)"\s*\}\s*(\{.*\})', raw, re.S)
    if two:
        try:
            rest = json.loads(two.group(2))
            if isinstance(rest, dict):
                return {"name": two.group(1), "args": rest}
        except ValueError:
            pass
    j = re.search(r"\{.*\}", raw, re.S)
    obj = _loads_loose(j.group(0)) if j else None
    if isinstance(obj, dict):
        if m and j.start() > 0 and re.fullmatch(r"[A-Za-z_][\w.\-]*\s*", raw[:j.start()]):
            return {"name": m.group(1), "args": obj}       # f {"k": "v"} — имя впереди важнее ключей внутри
        name, args = _call_parts(obj)
        if name:
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"_raw": args}
            return {"name": name, "args": args if isinstance(args, dict) else {}}
        if m and j.start() > 0 and re.fullmatch(r"[A-Za-z_][\w.\-]*\s*", raw[:j.start()]):
            return {"name": m.group(1), "args": obj}       # f {"k": "v"}
    if m and re.fullmatch(r"[A-Za-z_][\w.\-]*", raw):
        return {"name": raw, "args": {}}                   # просто имя функции без аргументов
    return None


def tools_prompt(tools):
    """Описание функций для системного запроса — в формате шаблона Qwen/Hermes, который многие модели знают."""
    lines = "\n".join(json.dumps({"type": "function", "function": t}, ensure_ascii=False) for t in tools)
    return ("\n\n# Инструменты\nТы можешь вызывать функции. Их описания — внутри <tools></tools>:\n<tools>\n"
            + lines + "\n</tools>\n\nЧтобы вызвать функцию, выведи ровно так и больше ничего:\n<tool_call>\n"
            '{"name": "<имя функции>", "arguments": {<аргументы>}}\n</tool_call>\n'
            "Результат придёт в <tool_response></tool_response>. Если функция не нужна — просто отвечай.")


def prompt_tools_mode(p):
    """Описывать инструменты текстом: так задано в профиле (tools_mode) или сервер уже отказался от поля tools.
    Для Anthropic и явного "native" — никогда."""
    if p.get("kind") == "anthropic" or p.get("tools_mode") == "native":
        return False
    return p.get("tools_mode") == "prompt" or str(p.get("base_url") or "").rstrip("/") in _no_tools


PROBE_TOOL = {"name": "get_time", "description": "Узнать точное текущее время", "parameters": {"type": "object", "properties": {}}}


def probe_tools(p):
    """Умеет ли модель вызывать инструменты и как: "native" (полем tools), "prompt" (описанием в тексте) или "none".
    Некоторые шлюзы молча выбрасывают поле tools — модель тогда отвечает «не могу». Проверяем на простом вопросе.
    -> None — ничего не решено (сервер недоступен или молчал), проверить позже."""
    sysmsg = "Ты помощник. На вопрос о времени обязательно вызови функцию get_time, не отвечай сам."
    msgs = [{"role": "user", "content": "Который сейчас час?"}]
    answered = 0                                   # сколько раз модель ответила (текстом, без вызова)
    for mode in ("native", "prompt"):
        try:
            # «думающей» модели нужно место порассуждать, прежде чем вызвать функцию: при малом лимите рассуждение
            # обрывается до вызова, и проверка ошибочно решает «не умеет»
            for kind, val in stream_events(dict(p, tools_mode=mode, max_tokens=max(2048, int(p.get("max_tokens") or 0))),
                                           sysmsg, msgs, tools=[PROBE_TOOL]):
                if kind == "tools" and any(c["name"] == "get_time" for c in val):
                    log.info("Инструменты у модели %s: %s", p.get("model") or p.get("base_url"),
                             "полем tools" if mode == "native" else "описанием в тексте")
                    return mode
                if kind == "text" and val.strip():
                    answered += 1
        except LLMError as e:
            log.info("Проверка инструментов (%s): %s", mode, e)
            # тексты — из _humanize: «не могу подключиться…», «сервер модели не ответил вовремя»
            if "подключ" in str(e) or "не ответил вовремя" in str(e) or "connect" in str(e).lower():
                return None                        # сервер недоступен или молчит — ничего не решаем, проверим позже
    if not answered:
        return None
    # Модель ответила словами и так, и так («Который час?» — «Не знаю точного времени»). Это не значит, что действий нет:
    # сервер функции принял. Раньше здесь было "none" — и программа переставала давать модели действия вовсе, а в виджете
    # висело «Эта модель не умеет выполнять действия» (23.10, владелец: «что это за бред»). Теперь — функции полем, как есть.
    log.info("Модель %s на проверке ответила словами, без вызова — функции оставляю полем", p.get("model") or p.get("base_url"))
    return "native"


_LMS_WOKE = [0.0]


def _lmstudio_wake(url):
    """№344 (пакет 27.10): сервер LM Studio выключен (по умолчанию он выключен), а Dewiar включал его только кнопкой
    «Найти». Своя модель на этом компьютере не на порту Ollama и LM Studio установлена — `lms server start` (не чаще
    раза в 10 минут)."""
    try:
        from urllib.parse import urlparse
        u = urlparse(str(url))
        if not LOCAL_HOST_RX.match(u.hostname or "") or u.port == 11434 or time.time() - _LMS_WOKE[0] < 600:
            return
        if not lmstudio_installed():
            return
        _LMS_WOKE[0] = time.time()
        got, started = lmstudio_start()
        if started:
            log.info("LM Studio: сервер был выключен — включил (%s)", got)
    except Exception as e:  # noqa: BLE001
        log.info("LM Studio: включить сервер не вышло: %s", e)


@contextlib.contextmanager
def _stream_retry(method, url, tries=2, **kw):
    """httpx.stream, но соединение не установилось (сеть моргнула, сервер не принял подключение) — ещё раз: запрос
    ещё не ушёл, повторять безопасно. Отчёт №69: «сервер модели не ответил вовремя» через 5 с, а следующий вопрос —
    ответ за 9 с. Ошибки после подключения не повторяем.
    30.10 (пакет: «не могу подключиться к dewiar.pro» — 25 раз у 15 компьютеров, по одному-два: связь моргнула, ноутбук
    проснулся и сеть ещё поднимается): облачной модели при отказе соединения даём ещё ≈ 9 с — повтор через 1, 2,5 и 5 с.
    Ожидание соединения (таймаут) так не тянем — каждое и так долгое; своя модель на компьютере и в сети — как было."""
    host = (re.match(r"^\w+://\[?([^/\]:?#]+)", str(url)) or [None, ""])[1]
    cloud = bool(host) and not LOCAL_HOST_RX.match(host) and not LAN_HOST_RX.search(host)
    waits = [1.0, 2.5, 5.0] if cloud else [0.8] * (tries - 1)
    for i in range(len(waits) + 1):
        cm = httpx.stream(method, url, **kw)
        try:
            r = cm.__enter__()
        except (httpx.ConnectTimeout, httpx.ConnectError) as e:
            if i >= len(waits) or (isinstance(e, httpx.ConnectTimeout) and i >= tries - 1):
                raise
            log.info("Сервер модели: соединение не установилось (%s) — пробую ещё раз через %.1f с", type(e).__name__, waits[i])
            _lmstudio_wake(url)
            time.sleep(waits[i])
            continue
        exc = (None, None, None)
        try:
            yield r
        except BaseException:
            exc = sys.exc_info()
            raise
        finally:
            cm.__exit__(*exc)
        return


# Иероглифы посреди русского ответа (пакет 25.10, №251: qwen2.5:7b в Ollama — «…похвало тебя за работу 今天的任务已经完成了…»):
# слабые модели соскальзывают в китайский. Если человек сам не писал иероглифами и не просил китайский, японский или
# корейский — такие куски из ответа убираем (с их знаками препинания), чтобы на экране и в голосе не было каши.
_CJK = re.compile(r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uff60]+")
_CJK_ASK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]|китай|япон|корей|иероглиф|chinese|japanese|korean|mandarin|kanji|hanzi", re.I)


def wants_cjk(messages):
    """Последний вопрос человека — с иероглифами или про эти языки? (тогда иероглифы в ответе нужны)"""
    for m in reversed(messages or []):
        if m.get("role") == "user":
            c = m.get("content")
            t = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else ""
            return bool(_CJK_ASK.search(t or ""))
    return False


def drop_cjk(t):
    return _CJK.sub("", t) if t else t


class _Collector:
    """Разбор ответа любого из форматов: поток OpenAI (SSE), один JSON целиком, поток Ollama (NDJSON),
    события Anthropic. Текст ответа отдельно от «размышлений» (их только считает — reasoning, в символах)
    и от вызовов функций (поле tool_calls и теги в тексте). fmt, finish, raw_head — для журнала при пустом ответе."""

    def __init__(self, anthropic=False):
        self.anthropic = anthropic
        self.strip = ThinkStripper()
        self.tags = ToolTagStripper()
        self.calls = {}
        self.reasoning = 0
        self.finish = ""
        self.fmt = ""
        self.raw_head = ""
        self.pending = ""
        self.no_cjk = False

    def _call(self, idx, cid="", name="", args=""):
        c = self.calls.setdefault(idx, {"id": "", "name": "", "args": ""})
        c["id"] = cid or c["id"]
        c["name"] = name or c["name"]
        c["args"] += args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)

    def feed_obj(self, obj):
        """-> кусок текста ответа (может быть пустым)."""
        if not isinstance(obj, dict):
            return ""
        if obj.get("error") and not obj.get("choices"):
            e = obj["error"]
            raise LLMError(e.get("message", str(e)) if isinstance(e, dict) else str(e))
        piece = ""
        if self.anthropic:
            typ = obj.get("type")
            if typ == "content_block_start" and obj.get("content_block", {}).get("type") == "tool_use":
                cb = obj["content_block"]
                self._call(obj.get("index", len(self.calls)), cb.get("id"), cb.get("name"))
            elif typ == "content_block_delta":
                d = obj.get("delta", {})
                if d.get("type") == "input_json_delta":
                    self._call(obj.get("index", 0), args=d.get("partial_json", ""))
                elif d.get("type") == "thinking_delta":
                    self.reasoning += len(d.get("thinking", ""))
                else:
                    piece = d.get("text", "")
            elif typ == "message_delta":
                self.finish = obj.get("delta", {}).get("stop_reason") or self.finish
        elif "choices" in obj:
            ch = (obj.get("choices") or [{}])[0]
            self.finish = ch.get("finish_reason") or self.finish
            d = ch.get("delta") or ch.get("message") or {}
            self.fmt = self.fmt or ("openai-stream" if "delta" in ch else "openai-json")
            piece = d.get("content") or ""
            self.reasoning += len(d.get("reasoning_content") or d.get("reasoning") or "")
            for i, tc in enumerate(d.get("tool_calls") or []):
                fn = tc.get("function") or {}
                self._call(tc.get("index", i), tc.get("id", ""), fn.get("name", ""), fn.get("arguments") or "")
        elif "message" in obj or "done" in obj:                    # родной формат Ollama
            self.fmt = self.fmt or "ollama"
            m = obj.get("message") or {}
            piece = m.get("content") or ""
            self.reasoning += len(m.get("thinking") or "")
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                self._call(len(self.calls), "", fn.get("name", ""), fn.get("arguments") or {})
            if obj.get("done"):
                self.finish = obj.get("done_reason") or "stop"
        d0 = self.strip.dropped
        piece = self.strip.feed(piece)
        self.reasoning += self.strip.dropped - d0
        out = self.tags.feed(piece)
        return drop_cjk(out) if self.no_cjk else out

    def flush(self):
        """Конец потока: придержанное начало ответа."""
        d0 = self.strip.dropped
        piece = self.strip.finish()
        self.reasoning += self.strip.dropped - d0
        out = (self.tags.feed(piece) if piece else "") + self.tags.tail()
        return drop_cjk(out) if self.no_cjk else out

    def feed_line(self, line):
        """Строка ответа сервера (SSE «data: …» или строка JSON) -> кусок текста ответа."""
        if len(self.raw_head) < 600:
            self.raw_head += line[:600] + "\n"
        s = line.strip()
        if not s or s.startswith("event:") or s.startswith(":"):
            return ""
        if s.startswith("data:"):
            s = s[5:].strip()
            if s == "[DONE]":
                return ""
        try:
            obj = json.loads(self.pending + s)
            self.pending = ""
        except ValueError:
            self.pending += s                                  # JSON целиком, разбитый на строки
            return ""
        return self.feed_obj(obj)

    def tool_calls(self):
        """-> [{"id", "name", "args"}] — из поля tool_calls и из тегов в тексте (им — номера с 1000, после родных).
        Нечитаемые аргументы — {"_raw": текст}; спасённые repair_json помечены "_truncated"."""
        for i, c in enumerate(self.tags.calls()):
            self.calls[1000 + i] = {"id": f"call_t{i}", "name": c["name"], "args": json.dumps(c["args"], ensure_ascii=False)}
        out = []
        for i in sorted(self.calls):
            c = self.calls[i]
            if not c["name"]:
                continue
            try:
                args = json.loads(c["args"]) if c["args"].strip() else {}
            except ValueError:
                args = repair_json(c["args"])
                if args is None:
                    args = {"_raw": c["args"]}
                else:
                    args["_truncated"] = True              # ответ оборвался по длине — аргументы закрыли сами
            out.append({"id": c["id"] or f"call_{i}", "name": c["name"], "args": args})
        return out


def repair_json(raw):
    """Оборванный по лимиту длины JSON аргументов ({"path": "a.html", "content": "<html>… — без конца) — закрываем
    строку и скобки, чтобы спасти уже написанное. -> dict или None."""
    t = (raw or "").strip()
    if not t.startswith("{"):
        return None
    stack, in_str, esc = [], False, False
    for ch in t:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    tail = t
    if in_str:
        tail = tail[:-1] if esc else tail
        tail += '"'
    tail = re.sub(r",\s*$", "", tail)
    for _ in range(3):
        try:
            d = json.loads(tail + "".join(reversed(stack)))
            return d if isinstance(d, dict) else None
        except ValueError:
            tail = re.sub(r',\s*"[^"]*"\s*:?\s*$', "", tail)     # оборвалось на имени поля — отрежем его
    return None


BUSY_RX = re.compile(r"high demand|overloaded|over capacity|temporarily unavailable|\bUNAVAILABLE\b|try again later", re.I)
RATE_WAIT = [float(x) for x in (os.environ.get("DEWIAR_RATE_WAIT") or "15,30,60").split(",")]   # 429: пауза перед повтором, с


# Сложная просьба — пусть модель подумает перед ответом (размышления в остальном выключены ради скорости). Отзыв 10.10:
# стих «без рифмы и со смешными сравнениями» — модель 27B без размышлений. Стихи и песни, задачи и расчёты со
# смыслом, анализ и сравнение, планы и стратегии, код, длинные просьбы. «Почему небо голубое» — сразу, без них.
HARD_ASK = re.compile(
    r"стих|стишок|поэм|сонет|рифм|частушк|четверостиш|(?:напиши|придумай) песн|текст песни|сочини|напиши (?:рассказ|сказку|историю|эссе|"
    r"сочинение|поздравлени|речь|тост)|поздрав\S* в стихах|реши(?:ть)? задач|задач[уаи] (?:по|на)|головоломк|докажи|"
    r"выведи формул|вероятност|проанализируй|анализ\w* (?:рынк|ситуац|данн|текст)|разбери (?:по пунктам|подробно|ситуацию|ошибк)|"
    r"сравни|стратеги|бизнес-план|составь план|план (?:обучения|тренировок|питания|поездки|развития|проекта)|"
    r"напиши (?:код|программ|функци|скрипт)|торгов\w* (?:на|крипт|акци)|инвестиц|криптовалют|трейдинг|пошагово|"
    r"взвесь|за и против|плюсы и минусы", re.I)


# Творческая просьба (отзыв 17.10: «креатив в модели не высокий, а в такого рода задачах он должен быть выше»): стихи,
# песни, сказки, поздравления, тосты, шутки, названия, идеи — температура не ниже CREATIVE_TEMP (обычно 0.7: для дел и
# фактов нужна точность, для стиха — свежесть образов). Стихам — ещё и ремесло (POEM_NOTE): рифмы подбираются заранее.
CREATIVE_ASK = re.compile(
    r"стих|стишок|поэм|сонет|рифм|частушк|четверостиш|(?:напиши|придумай|сочини) песн|текст песни|сказк|сочини|поздрав|тост|шутк|анекдот|каламбур|слоган|"
    r"придумай|выдумай|нафантазируй|(?:напиши|расскажи) (?:рассказ|историю|сказку|сценарий)|креатив|оригинальн", re.I)
POEM_ASK = re.compile(r"стих|стишок|поэм|сонет|рифм|частушк|четверостиш|в стихах|текст песни|(?:напиши|придумай|сочини) песн", re.I)
CREATIVE_TEMP = 0.95
# советы фильмов, книг и песен (экзамен 25.10: выдуманные фильмы «Ghost Trail», песни у реальных исполнителей) — только
# существующее; RECO_ASK / RECO_NOTE — так же на телефоне (app.js)
RECO_ASK = re.compile(r"(?:посоветуй|порекомендуй|подбери|что посмотреть|что почитать|что послушать|составь)\b[^.?!]{0,60}?"
                      r"(?:фильм|сериал|кино|посмотреть|книг|почитать|песн|музык|послушать|плейлист|трек|альбом)|плейлист", re.I)
RECO_NOTE = "\n\nСейчас просят посоветовать фильмы, сериалы, книги, песни или плейлист. Называй только то, что точно существует и что ты точно знаешь: название, автор или исполнитель, год — без догадок; из результатов поиска бери названия ровно как там. Нет уверенности, что у исполнителя есть такая песня, — не называй её (лучше три верных, чем пять с выдуманными). 1–3 пункта с одной живой фразой «почему именно это», а не справочный список."
POEM_NOTE = ("\n\nСейчас просят стихи. Ремесло: сначала про себя выбери размер (например, хорей или ямб) и подбери пары рифм "
             "по ударному слогу — совпадают ударная гласная и всё после неё (осень — просинь, листва — синева, дождя — шутя); "
             "глагольные рифмы («шла — пришла») и «рифмы» без совпадения ударения не годятся. Образы — простые, точные и "
             "живые, без нелепых сравнений. Количество строк — ровно как просили. Перед ответом проверь каждую пару рифм.")


def creative_temp(text, temp=None):
    """Температура для этой просьбы: творческая — не ниже CREATIVE_TEMP, иначе — как в профиле. Температуру вписали
    в профиль сами (не пусто и не 0,7 по умолчанию) — она главнее (пакет 27.10, №311: «задал 0,3, а на просьбу о стихе
    стало 0,95»). Так же на телефоне (app.js llmTemp)."""
    if temp not in (None, "") and float(temp) != 0.7:
        return float(temp)
    return CREATIVE_TEMP if CREATIVE_ASK.search(str(text or "")) else 0.7


def wants_think(text, mode=None):
    """Думать ли модели над этой просьбой: mode "on"/"off" — как сказано; иначе (auto) — сложная просьба (HARD_ASK)
    или длинная (больше 280 знаков)."""
    if mode in ("on", "off"):
        return mode == "on"
    t = str(text or "")
    return bool(HARD_ASK.search(t)) or len(t) > 280


def stream_events(p, system, messages, cancel=None, tools=None, _retry=0):
    """Поток событий: ("text", кусок) и в конце, если модель решила действовать,
    ("tools", [{"id", "name", "args"}]). cancel — threading.Event для мгновенной остановки. Ошибки — LLMError.

    Пока модель не сказала ни слова, отказы сервера чинит сама и повторяет запрос: история вызовов текстом,
    функции текстом, без chat_template_kwargs, родной API Ollama, короче (_lite). Если всё время ушло на
    «размышления» и текста нет — повторит с выключенными размышлениями и вчетверо большим лимитом.
    Служебные ключи профиля с «_» (_flat, _lite, _no_kwargs, _empty_retry) ставит только сама при повторах."""
    base = _base(p)
    tools_all = tools
    if tools and prompt_tools_mode(p):
        system = system + tools_prompt(tools)            # сервер не принимает функции полем — описываем текстом
        tools = None
    native = p.get("kind") == "ollama" or base in _native
    max_tokens = int(p.get("max_tokens") or DEFAULT_MAX_TOKENS)
    # Размышления выключены по умолчанию: качество ответов помощника почти не растёт, а ответ заметно медленнее.
    # Включить — только явно, "think": "on" в профиле; при повторе после пустого ответа — выключены всегда.
    no_think = p.get("think") != "on" or _retry > 0
    try:
        model = resolve_model(p)
        native = p.get("kind") == "ollama" or base in _native    # ещё раз: resolve_model мог узнать, что тут только Ollama
        # своя модель на этом компьютере или в сети (YouTube 26.10: llama.cpp, 27B на встроенной графике — «долгий префил,
        # Dewiar прерывал генерацию и не отвечал на часть вопросов»): первое слово ждём до 10 минут, облако — 3
        timeout = httpx.Timeout(5, read=float(p.get("timeout") or (600 if _local_base(base) else 180)))
        if p.get("kind") == "anthropic":
            url = _anth_root(base) + "/v1/messages"
            # кэш подсказки (GitHub PR №24, maghelp, 26.10): инструменты (≈13 тыс. токенов) и характер уходят с каждым
            # шагом — с cache_control Claude берёт их из кэша в ~10 раз дешевле. Метки — на последнем инструменте и на
            # подсказке (порядок кэша: инструменты → system → сообщения)
            body = {"model": model, "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}] if system else system,
                    "messages": messages, "stream": True,
                    "max_tokens": max_tokens, "temperature": float(p.get("temperature", 0.7))}
            if tools:
                body["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                                 for t in tools]
                body["tools"][-1] = dict(body["tools"][-1], cache_control={"type": "ephemeral"})
        elif native:
            url = _root(base) + "/api/chat"
            body = {"model": model, "stream": True, "messages": _to_ollama([{"role": "system", "content": system}] + messages),
                    "options": {"num_predict": max_tokens, "temperature": float(p.get("temperature", 0.7))}}
            if no_think:
                body["think"] = False
            if tools:
                body["tools"] = [{"type": "function", "function": t} for t in tools]
        else:
            url = base + "/chat/completions"
            hist = flat_messages(messages) if (p.get("_flat") or base in _flat or prompt_tools_mode(p) or not tools) \
                and _has_tool_history(messages) else _clean_messages(messages)
            if p.get("_lite"):                         # последняя попытка: короче — начало задачи и последние шаги
                hist = (hist[:1] + [{"role": "assistant", "content": "…"}] + hist[-10:]) if len(hist) > 12 else hist
                system = system[:14000]
            body = {"model": model, "stream": True,
                    "messages": [{"role": "system", "content": system}] + hist,
                    "max_tokens": max_tokens, "temperature": float(p.get("temperature", 0.7))}
            # №226 (24.10): OpenAI напрямую, GPT-5 и o-модели — ошибка 400: им нужен max_completion_tokens, а temperature
            # они не принимают (только 1). Через OpenRouter работало — там поле переводят сами.
            if p.get("_mct") or (re.search(r"api\.openai\.com", base) and re.match(r"(?:gpt-5|o\d)", str(model).lower())):
                body["max_completion_tokens"] = body.pop("max_tokens")
                body.pop("temperature", None)
            # chat_template_kwargs понимают vLLM/SGLang (Qwen3 и др.); облачные API на незнакомое поле отвечают ошибкой
            if no_think and not p.get("_no_kwargs") and base not in _no_kw and not re.search(r"openai\.com|openrouter|deepseek\.com|anthropic|googleapis", base):
                body["chat_template_kwargs"] = {"enable_thinking": False}
            if tools:
                body["tools"] = [{"type": "function", "function": t} for t in tools]
                body["tool_choice"] = "auto"
        col = _Collector(anthropic=p.get("kind") == "anthropic")
        col.tags.known = {x["name"] for x in (tools_all or [])}   # голый JSON в тексте — вызов, только если такая функция есть
        col.no_cjk = not wants_cjk(messages)
        bare = BareCallCatcher([x["name"] for x in (tools_all or [])] if prompt_tools_mode(p) or native else [])
        got_text = False
        with _stream_retry("POST", url, json=body, headers=_headers(p), timeout=timeout) as r:
            if r.status_code >= 400:
                r.read()
                err = r.text.lower()
                n = int(p.get("_rl") or 0)
                if r.status_code in (503, 529) and not p.get("_busy") and (cancel is None or not cancel.is_set()):
                    # перегружен (Gemini «high demand») — часто проходит через пару секунд: один тихий повтор
                    log.info("Сервер %s перегружен (%s) — повторяю через 3 с", base, r.status_code)
                    end = time.monotonic() + float(os.environ.get("DEWIAR_BUSY_WAIT") or 3)
                    while time.monotonic() < end:
                        if cancel is not None and cancel.is_set():
                            return
                        time.sleep(0.2)
                    yield from stream_events(dict(p, _busy=True), system, messages, cancel, tools, _retry)
                    return
                if r.status_code == 429 and n < len(RATE_WAIT) and not NO_MONEY_RX.search(err):   # «много запросов» — подождать (денег нет — не ждать)
                    try:
                        wait = min(90.0, float(r.headers.get("retry-after") or RATE_WAIT[n]))
                    except ValueError:
                        wait = RATE_WAIT[n]
                    log.info("Сервер %s: слишком много запросов — жду %.0f с и повторяю (%d из %d)", base, wait, n + 1, len(RATE_WAIT))
                    end = time.monotonic() + wait
                    while time.monotonic() < end:
                        if cancel is not None and cancel.is_set():
                            return
                        time.sleep(0.5)
                    yield from stream_events(dict(p, _rl=n + 1), system, messages, cancel, tools, _retry)
                    return
                if r.status_code == 400 and not p.get("_mct") and ("max_completion_tokens" in err or
                                                                 ("temperature" in err and re.search(r"unsupported|only 1 is allowed|invalid temperature|does not support", err))):
                    log.info("Сервер %s просит max_completion_tokens и температуру по умолчанию — повторяю так", base)
                    yield from stream_events(dict(p, _mct=True), system, messages, cancel, tools, _retry)
                    return
                if "image" in err and any(isinstance(m.get("content"), list) for m in messages):
                    raise LLMError("эта модель не принимает изображения — выберите в «Мозге» модель со зрением")
                if r.status_code in (400, 422) and _has_tool_history(messages) and not p.get("_flat") \
                        and base not in _flat and p.get("kind") != "anthropic" and not native:
                    log.info("Сервер %s не принял историю вызовов (%s) — пишу её текстом", base, r.status_code)
                    _flat.add(base)
                    yield from stream_events(dict(p, _flat=True), system, messages, cancel, tools, _retry)
                    return
                if tools and r.status_code in (400, 422, 500) and ("tool" in err or "function" in err) \
                        and p.get("tools_mode") != "native":
                    log.info("Сервер %s не принимает функции полем — описываю их в тексте запроса", base)
                    _no_tools.add(base)
                    yield from stream_events(p, system, messages, cancel, tools, _retry)
                    return
                if "chat_template_kwargs" in body and r.status_code in (400, 422):
                    log.info("Сервер не понимает chat_template_kwargs — повторяю без него")
                    yield from stream_events(dict(p, _no_kwargs=True), system, messages, cancel, tools, _retry)
                    return
                if r.status_code == 404 and not native and p.get("kind") != "anthropic":
                    probe = httpx.get(_root(base) + "/api/tags", timeout=5)
                    if probe.status_code == 200:
                        log.info("На %s нет /chat/completions, но есть API Ollama — перехожу на него", base)
                        _native.add(base)
                        yield from stream_events(p, system, messages, cancel, tools, _retry)
                        return
                r.raise_for_status()
            for line in r.iter_lines():
                if cancel is not None and cancel.is_set():
                    return
                piece = bare.feed(col.feed_line(line))
                if piece:
                    got_text = True
                    yield "text", piece
            if col.pending:
                try:
                    piece = bare.feed(col.feed_obj(json.loads(col.pending)))
                    if piece:
                        got_text = True
                        yield "text", piece
                except ValueError:
                    pass
            if not (cancel is not None and cancel.is_set()):
                piece = bare.feed(col.flush())
                if piece:
                    got_text = True
                    yield "text", piece
        calls = col.tool_calls()
        held, bare_calls = bare.finish()
        if not calls and bare_calls:
            log.info("Вызов без тегов, голым JSON: %s", ", ".join(c["name"] for c in bare_calls))
            calls = [{"id": f"call_b{i}", "name": c["name"], "args": c["args"]} for i, c in enumerate(bare_calls)]
        elif held:
            got_text = True
            yield "text", held
        if calls and not (cancel is not None and cancel.is_set()):
            yield "tools", calls
            return
        if not got_text and not (cancel is not None and cancel.is_set()):
            log.warning("Пустой ответ: модель %s, формат %s, причина %s, размышлений %d симв., начало ответа: %r",
                        model, col.fmt or "?", col.finish or "?", col.reasoning, col.raw_head[:300])
            if _retry == 0 and (col.reasoning or col.finish in ("length", "max_tokens")):
                log.info("Модель ушла в размышления — повторяю без них и с лимитом %d", max(4 * max_tokens, 4096))
                yield from stream_events(dict(p, max_tokens=max(4 * max_tokens, 4096)), system, messages, cancel,
                                         tools, _retry + 1)
                return
            if not col.raw_head.strip():
                if not p.get("_empty_retry"):            # сервер прислал «ничего» (занят, грузит модель) — ещё раз
                    log.info("Сервер %s прислал пустой ответ — повторяю через 2 с", base)
                    time.sleep(2)
                    yield from stream_events(dict(p, _empty_retry=True), system, messages, cancel, tools, _retry)
                    return
                raise LLMError("сервер модели прислал пустой ответ (дважды) — он занят, перезапускается или такой модели "
                               f"«{model}» на нём нет; проверьте в «Мозге» кнопкой «Проверить»")
            if tools and base not in _no_tools and p.get("kind") != "anthropic" and not col.reasoning \
                    and p.get("tools_mode") != "native":
                # сервер молча не понял инструменты полем (так делают некоторые шлюзы) — описываем их текстом
                log.info("Сервер %s ответил пустотой на запрос с инструментами — описываю их в тексте запроса", base)
                _no_tools.add(base)
                yield from stream_events(p, system, messages, cancel, tools, _retry)
                return
            if col.reasoning:
                raise LLMError("модель думала, но так и не ответила — выберите в «Мозге» модель без размышлений "
                               "или увеличьте лимит ответа")
            if not p.get("_blank_retry"):              # случайный пустой ответ (бывает у облачных моделей) — ещё раз
                log.info("Сервер %s ответил без текста и действий — повторяю через 2 с", base)
                time.sleep(2)
                yield from stream_events(dict(p, _blank_retry=True), system, messages, cancel, tools, _retry)
                return
            raise LLMError(f"сервер вернул ответ без текста (модель «{model}»). Отчёт для разработчика: студия → «О программе» → «Сохранить отчёт»")
    except LLMError as e:
        if not locals().get("got_text") and ctx_full(e):
            yield from _ctx_retry(p, system, messages, cancel, tools, _retry, e)
            return
        if not locals().get("got_text") and UNLOADED_RX.search(str(e)) and not p.get("_reload"):
            log.info("Сервер %s выгрузил модель (%s) — повторяю: загрузит снова", base, e)
            time.sleep(1.5)
            yield from stream_events(dict(p, _reload=True), system, messages, cancel, tools, _retry)
            return
        # Отказ пришёл строкой «error» уже внутри потока (HTTP 200): так отвечают Ollama с облачными моделями и шлюзы —
        # «upstream returned HTTP 400». Пока модель ничего не сказала, упрощаем запрос по шагам:
        # 1) история вызовов — текстом; 2) и сами функции — текстом; 3) короче: начало и последние шаги.
        rejected = not locals().get("got_text") and p.get("kind") != "anthropic" and _REJECT.search(str(e))
        # Сначала — без chat_template_kwargs: облако Ollama за шлюзом отклоняет незнакомое поле, а функции полем tools
        # принимает. Раньше сразу переходили на функции текстом — хуже для всех на облаке Dewiar (пакеты 21–22.10:
        # «Проверка инструментов (native): upstream returned HTTP 400» в каждом журнале).
        if rejected and "chat_template_kwargs" in (locals().get("body") or {}) and base not in _no_kw:
            log.info("Сервер %s отклонил запрос (%s) — повторяю без chat_template_kwargs", base, e)
            _no_kw.add(base)
            yield from stream_events(dict(p, _no_kwargs=True), system, messages, cancel, tools, _retry)
            return
        if rejected and _has_tool_history(messages) and not p.get("_flat") and base not in _flat and not native:
            log.info("Сервер %s отклонил запрос (%s) — пишу историю вызовов текстом", base, e)
            _flat.add(base)
            yield from stream_events(dict(p, _flat=True), system, messages, cancel, tools, _retry)
            return
        if rejected and tools and p.get("tools_mode") != "native" and base not in _no_tools:
            log.info("Сервер %s отклонил запрос с инструментами (%s) — описываю их в тексте запроса", base, e)
            _no_tools.add(base)
            yield from stream_events(dict(p, _flat=True), system, messages, cancel, tools, _retry)
            return
        if rejected and not p.get("_lite") and not native and (len(messages) > 12 or len(system) > 14000):
            log.info("Сервер %s снова отклонил запрос (%s) — пробую короче: начало и последние шаги", base, e)
            yield from stream_events(dict(p, _flat=True, _lite=True), system, messages, cancel, tools, _retry)
            return
        if rejected and "сервер модели отклонил" not in str(e):
            log.warning("Отказ сервера %s (модель %s): %s; запрос: system %d симв., функций %d, сообщения: %s", base, p.get("model"), e,
                        len(system), len(tools or []), " ".join(m.get("role", "?")[0] + ("*" if m.get("tool_calls") else "") +
                                                                 str(len(str(m.get("content") or ""))) for m in messages)[:800])
            raise LLMError(f"сервер модели отклонил запрос ({e}) — и в упрощённом виде тоже. Попробуйте другую модель в «Мозге»; "
                           "отчёт для разработчика: студия → «О программе» → «Сохранить отчёт»") from e
        raise
    except Exception as e:  # noqa: BLE001
        msg = _humanize(e, base, p.get("model") or "")
        if msg == CTX_TEXT and not locals().get("got_text"):
            yield from _ctx_retry(p, system, messages, cancel, tools, _retry, e)
            return
        if UNLOADED_RX.search(msg) and not locals().get("got_text") and not p.get("_reload"):
            log.info("Сервер %s выгрузил модель (%s) — повторяю: загрузит снова", base, msg[:120])
            time.sleep(1.5)
            yield from stream_events(dict(p, _reload=True), system, messages, cancel, tools, _retry)
            return
        raise LLMError(msg) from e


def image_block(p, b64):
    """Картинка (JPEG в base64) в формате протокола профиля: Anthropic или OpenAI (data: URL)."""
    if p.get("kind") == "anthropic":
        return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}


def user_message(p, text, images=()):
    if not images:
        return {"role": "user", "content": text}
    return {"role": "user", "content": [image_block(p, b) for b in images] + [{"type": "text", "text": text}]}


def tool_turn_messages(p, text, calls, results):
    """Сообщения после вызова инструментов (формат зависит от протокола).
    Результат — строка или {"text", "image"}: картинку Claude получает внутри tool_result,
    а OpenAI-совместимые серверы (vLLM) — следующим сообщением пользователя."""
    texts = [r["text"] if isinstance(r, dict) else r for r in results]
    images = [r.get("image") if isinstance(r, dict) else None for r in results]
    if p.get("kind") == "anthropic":
        content = ([{"type": "text", "text": text}] if text.strip() else []) + \
                  [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]} for c in calls]
        res = []
        for c, t, im in zip(calls, texts, images):
            res.append({"type": "tool_result", "tool_use_id": c["id"],
                        "content": [{"type": "text", "text": t}] + ([image_block(p, im)] if im else [])})
        return [{"role": "assistant", "content": content}, {"role": "user", "content": res}]
    if prompt_tools_mode(p):
        call_txt = "".join("<tool_call>\n" + json.dumps({"name": c["name"], "arguments": c["args"]}, ensure_ascii=False)
                           + "\n</tool_call>" for c in calls)
        resp = "\n".join(f"<tool_response>\n{t}\n</tool_response>" for t in texts)
        msgs = [{"role": "assistant", "content": (text + "\n" if text.strip() else "") + call_txt},
                {"role": "user", "content": resp}]
        pics = [im for im in images if im]
        if pics:
            msgs.append(user_message(p, "Картинка из инструмента выше.", pics))
        return msgs
    results = texts
    msgs = [{"role": "assistant", "content": text or None,
             "tool_calls": [{"id": c["id"], "type": "function",
                             "function": {"name": c["name"], "arguments": json.dumps(c["args"], ensure_ascii=False)}}
                            for c in calls]}]
    msgs += [{"role": "tool", "tool_call_id": c["id"], "content": r} for c, r in zip(calls, results)]
    pics = [im for im in images if im]
    if pics:
        msgs.append(user_message(p, "Картинка из инструмента выше.", pics))
    return msgs


def test_profile(p):
    """Проверка для кнопки «Проверить» в «Мозге»: какие модели есть, какая выбрана, отвечает ли она текстом
    и как быстро, как вызывает инструменты. -> {"ok", "models", "model", "api", "tools_mode", "first_token_ms",
    "total_ms", "reply", "error"}; ошибка соединения при выборе модели — {"ok": False, "error"}."""
    t0 = time.monotonic()
    models = []
    try:
        _base(p)
    except LLMError as e:
        return {"ok": False, "error": str(e)}
    try:
        models = list_models(p)
    except LLMError as e:
        if not p.get("model"):
            return {"ok": False, "error": str(e)}
    if models and not chat_models(models) and (not p.get("model") or _NOT_CHAT.search(p.get("model") or "")):
        return {"ok": False, "models": models, "error": no_chat_help(p.get("base_url"), models)}      # №258
    model = p.get("model") or pick_model(models)
    first, text = None, ""
    for piece in stream_chat(dict(p, model=model), "Ты помощник. Отвечай очень коротко, по-русски.",
                             [{"role": "user", "content": "Скажи одно слово: готово."}]):
        if first is None:
            first = time.monotonic() - t0
        text += piece
    base = _base(p)
    tools_mode = (probe_tools(dict(p, model=model)) or "") if text.strip() else ""
    win = context_window(dict(p, model=model)) if text.strip() else None
    return {"ok": bool(text.strip()), "models": models, "model": model, "api": "ollama" if base in _native else p.get("kind", "openai"),
            "tools_mode": tools_mode, "ctx": win or 0,
            "ctx_note": (f"окно контекста {win} — мало: Лира ответит коротко" + (" и без действий" if win < 12000 else " и только с главными действиями")
                         + ". Поставьте 32768 или больше (LM Studio — Context Length, Ollama — OLLAMA_CONTEXT_LENGTH)") if win and win < 24000 else "",
            "first_token_ms": int((first or 0) * 1000), "total_ms": int((time.monotonic() - t0) * 1000),
            "reply": text.strip()[:80], "error": "" if text.strip() else "модель не ответила текстом"}


def probe_server(address, port=""):
    """«Адрес и порт» → рабочий профиль. Сам перебирает протокол, путь и тип сервера.
    Порт не указан — пробует обычные: vLLM 8000, Ollama 11434, llama.cpp 8080, LM Studio 1234, 443/80."""
    from urllib.parse import urlparse
    addr = (address or "").strip().rstrip("/")
    if not addr:
        raise LLMError("укажите адрес сервера")
    u = urlparse(addr if "://" in addr else "//" + addr)
    host = u.hostname or addr
    port = str(port or u.port or "").strip()
    schemes = [u.scheme] if u.scheme in ("http", "https") else ["http", "https"]
    ports = [port] if port else ["8000", "11434", "8080", "1234", ""]
    tried = []
    for pt in ports:
        for sc in (schemes if pt else ["https", "http"]):
            root = f"{sc}://{host}" + (f":{pt}" if pt else "")
            tried.append(root)
            try:
                r = httpx.get(root + "/v1/models", timeout=2.0)
                if r.status_code == 200 and "data" in r.json():
                    models = [m.get("id") for m in r.json()["data"] if m.get("id")]
                    return {"ok": True, "base_url": root + "/v1", "kind": "openai", "models": models,
                            "model": pick_model(models), "server": "OpenAI-совместимый (vLLM, llama.cpp, LM Studio…)"}
                r = httpx.get(root + "/api/tags", timeout=2.0)
                if r.status_code == 200 and "models" in r.json():
                    models = [m.get("name") or m.get("model") for m in r.json()["models"]]
                    return {"ok": True, "base_url": root, "kind": "ollama", "models": models,
                            "model": pick_model(models), "server": "Ollama"}
            except (httpx.HTTPError, ValueError):
                continue
    raise LLMError(f"на {host} не нашёл сервера моделей (пробовал {', '.join(tried[:6])}{'…' if len(tried) > 6 else ''}) — "
                   "проверьте адрес и порт, и что сервер доступен из этой сети")


def _models_at(url, timeout=0.6):
    """Список моделей сервера по адресу …/v1 или None, если там никто не отвечает."""
    try:
        r = httpx.get(url + "/models", timeout=timeout)
        if r.status_code == 200:
            return [m.get("id") for m in r.json().get("data", []) if m.get("id")]
    except Exception:  # noqa: BLE001
        pass
    return None


def lmstudio_cli():
    """Командная строка LM Studio (lms) — она ставится вместе с программой: ~/.lmstudio/bin (новые версии) или
    ~/.cache/lm-studio/bin (старые). -> путь или None."""
    from pathlib import Path
    import shutil
    home = Path.home()
    for d in (home / ".lmstudio" / "bin", home / ".cache" / "lm-studio" / "bin"):
        for n in ("lms.exe", "lms"):
            if (d / n).is_file():
                return d / n
    w = shutil.which("lms")
    return Path(w) if w else None


def lmstudio_installed():
    """Стоит ли LM Studio на этом компьютере (запущен его сервер или нет)."""
    from pathlib import Path
    home = Path.home()
    if lmstudio_cli() or (home / ".lmstudio").is_dir() or (home / ".cache" / "lm-studio").is_dir():
        return True
    la = os.environ.get("LOCALAPPDATA")
    return bool(la) and any((Path(la) / "Programs" / d).is_dir() for d in ("LM Studio", "LM-Studio", "lm-studio"))


def lmstudio_start():
    """Сервер LM Studio выключен (по умолчанию он выключен — отчёт №118, 19.10: «Не видит LM Studio, хотя установлено»)
    или слушает не обычный порт: узнать у `lms server status`, при нужде включить `lms server start`.
    -> (адрес …/v1, включили ли сейчас) или (None, False)."""
    import subprocess
    cli = lmstudio_cli()
    if not cli:
        return None, False
    kw = dict(capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
              creationflags=0x08000000 if os.name == "nt" else 0)

    def status():
        try:
            st = subprocess.run([str(cli), "server", "status"], timeout=20, **kw)
        except Exception as e:  # noqa: BLE001
            log.info("LM Studio: lms server status: %s", e)
            return None
        out = (st.stdout or "") + (st.stderr or "")
        m = re.search(r"port\D{0,12}(\d{2,5})", out, re.I)
        if not m or re.search(r"not running", out, re.I):
            return None
        url = f"http://127.0.0.1:{m.group(1)}/v1"
        for _ in range(16):
            if _models_at(url, 1.0) is not None:
                return url
            time.sleep(0.5)
        return None
    url = status()
    if url:
        return url, False
    try:
        r = subprocess.run([str(cli), "server", "start"], timeout=40, **kw)
        log.info("LM Studio: lms server start → %s", ((r.stdout or "") + (r.stderr or "")).strip()[-200:])
    except Exception as e:  # noqa: BLE001
        log.info("LM Studio: сервер не включился: %s", e)
        return None, False
    url = status()
    return url, bool(url)


LMSTUDIO_HOW = ("LM Studio установлен, но его сервер выключен. В LM Studio откройте слева «Developer» (значок </>) и включите "
                "переключатель «Status: Running», там же загрузите модель — и снова нажмите «Найти».")


def discover_local(start=False):
    """Какие локальные серверы моделей уже запущены на этом компьютере (обычные порты, /v1/models).
    start — LM Studio стоит, а сервер выключен: включить его (lms server start); не вышло — LLMError с подсказкой.
    -> профили на основе LLM_PRESETS (settings.py) с base_url и списком моделей."""
    found = []
    for pid, port in (("vllm", 8000), ("ollama", 11434), ("llamacpp", 8080), ("lmstudio", 1234)):
        url = f"http://127.0.0.1:{port}/v1"
        ids = _models_at(url)
        if ids is not None:
            found.append(dict(LLM_PRESETS[pid], preset=pid, base_url=url, models=ids))
    if start and not any(f["preset"] == "lmstudio" for f in found) and lmstudio_installed():
        url, started = lmstudio_start()
        if url:
            found.append(dict(LLM_PRESETS["lmstudio"], preset="lmstudio", base_url=url, models=_models_at(url, 3.0) or [], started=started))
        elif not found:
            raise LLMError(LMSTUDIO_HOW)
    return found


# ---------- текст для озвучки ----------

_SENT_END = re.compile(r"([.!?…]+[»\")]?)(\s+)")


class SentenceSplitter:
    """Режет поток текста на фразы для озвучки. Законченное предложение (знак конца и пробел за ним) отдаёт сразу,
    даже короткое («Да.»); первую фразу без знака конца — как можно раньше (можно по запятой, после 60 символов),
    чтобы голос зазвучал через доли секунды; дальше режет по запятой только очень длинные (220+). Кусок без букв
    («1.» в нумерованном списке) концом предложения не считается — ждёт продолжения."""

    def __init__(self):
        self.buf = ""
        self.first = True

    def feed(self, s):
        self.buf += s
        out = []
        while True:
            # ищем первый конец предложения, перед которым есть буквы: search() на одном и том же коротком
            # совпадении в начале буфера останавливал бы деление на фразы до конца ответа
            m = next((m for m in _SENT_END.finditer(self.buf) if re.search(r"[^\W\d_]", self.buf[:m.start()])), None)
            if m:
                out.append(self.buf[:m.end(1)].strip())
                self.buf = self.buf[m.end():]
                self.first = False
                continue
            nl = self.buf.find("\n")
            if nl >= 0:
                piece = self.buf[:nl].strip()
                self.buf = self.buf[nl + 1:]
                if piece:
                    out.append(piece)
                    self.first = False
                continue
            limit = 60 if self.first else 220
            if len(self.buf) > limit:
                cut = max(self.buf.rfind(", ", 0, limit + 40), self.buf.rfind(" — ", 0, limit + 40))
                if cut > 25:
                    out.append(self.buf[:cut + 1].strip())
                    self.buf = self.buf[cut + 2:]
                    self.first = False
                    continue
            break
        return [x for x in out if x]

    def flush(self):
        rest, self.buf = self.buf.strip(), ""
        return [rest] if rest else []


class CodeFilter:
    """Код вслух не читаем: блоки ```…``` и строки-команды (sudo …, $ …, >>> …) заменяем фразой NOTE —
    один раз за ответ. Работает на потоке, до деления на фразы; обычный текст проходит без задержки,
    придерживается только начало строки, пока не ясно, команда ли это."""

    NOTE = "Команды и код — на экране. "
    _CMD = re.compile(r"^\s*(\$ |sudo |>>> |#!/)")
    # строка разметки: <div…, </p>, <!DOCTYPE — не вслух; строчные теги в начале фразы (<b>, <i>, <a>) — текст, теги снимет speakable
    _TAG = re.compile(r"^\s*<(?:[!?]|/?(?!(?:b|i|u|s|em|strong|a|span|br|mark|small|sup|sub|code)\b)[A-Za-z])")
    _HTML_ON = re.compile(r"^\s*<(?:!doctype|html|style|script|head|body)\b", re.I)
    _HTML_OFF = re.compile(r"</(?:html|style|script|head|body)\s*>\s*$", re.I)
    _ACTS = ("[в этом ответе выполнено", "[узнано инструментами")   # пометки истории (engine_answer.team_window)

    def __init__(self):
        self.pend, self.code, self.told, self.skip, self.start = "", False, False, False, True
        self.want, self.lang = False, ""                 # открыли ```: язык ещё читается; схема (mermaid) — молча
        self.html = False                                # внутри HTML-документа или <style>/<script> — молчим до закрытия

    def _note(self):
        if self.told:
            return ""
        self.told = True
        return self.NOTE

    def feed(self, s):
        out = ""
        for ch in s:
            if self.start:                                # начало строки: решаем, код это или текст
                self.pend += ch
                lead = self.pend.lstrip(" \t")
                if ch == "\n":
                    if not self.code and not self.skip:
                        out += self.pend
                    self.pend, self.skip = "", False
                    continue
                if lead.startswith("```"):
                    self.code, self.start, self.skip, self.pend = not self.code, False, True, ""
                    if self.code:
                        self.want, self.lang = True, ""   # «Команды и код — на экране» — когда станет ясен язык блока
                    continue
                if self.code:
                    if len(lead) >= 3 or (lead and not "```".startswith(lead)):
                        self.start, self.skip, self.pend = False, True, ""
                    continue
                if lead.startswith(self._ACTS):           # пометка истории «[в этом ответе выполнено…]» — вслух не читаем
                    self.start, self.skip, self.pend = False, True, ""
                    continue
                if lead and ("```".startswith(lead) or "$ ".startswith(lead) or "sudo ".startswith(lead)
                             or ">>> ".startswith(lead) or "#!/".startswith(lead) or any(a.startswith(lead) for a in self._ACTS)):
                    continue                              # ещё не ясно — ждём пару символов
                if self._CMD.match(self.pend):
                    out += self._note()
                    self.start, self.skip, self.pend = False, True, ""
                    continue
                if re.match(r"<[!/?]?[A-Za-z]{0,10}$", lead):
                    continue                              # «<», «<di», «</bo» — тег это или «< 5»: ждём конца имени
                if self.html or self._TAG.match(self.pend):   # разметка — вся строка мимо голоса
                    out += self._note()
                    self.line, self.start, self.skip, self.pend = self.pend, False, True, ""
                    continue
                if lead:
                    out += self.pend
                    self.pend, self.start = "", False
                continue
            if ch == "\n":
                ln = getattr(self, "line", "")
                if self._HTML_ON.match(ln):
                    self.html = True                      # <!DOCTYPE, <html, <style, <script — молчим до закрытия
                if self.html and self._HTML_OFF.search(ln):
                    self.html = False                     # </html>, </style>, </script> — дальше снова обычный текст
                self.line = ""
                if self.want:
                    out += self._lang_note()
                if not self.skip and not self.code:
                    out += ch
                self.start, self.skip = True, False
                continue
            if not self.skip and not self.code:
                out += ch
            elif self.want:
                self.lang += ch
            elif self.skip:
                self.line = getattr(self, "line", "") + ch
        return out

    def _lang_note(self):
        """Строка открытия блока прочитана: схема (```mermaid) — на экране картинкой, о ней молчим; код — одна фраза."""
        self.want = False
        return "" if self.lang.strip().lower() == "mermaid" else self._note()

    def flush(self):
        p, self.pend = self.pend, ""
        return "" if self.code or self.skip or self._CMD.match(p) or p.lstrip().startswith("```") else p


# вслух не читаем то, что на слух бессмысленно: ссылки, пути к файлам (outputs/news.html), расширения файлов; сокращения —
# полными словами (иначе голос читает «т ч», «т е»). «км/ч», «и/или», «6/10» и имена сайтов (dewiar.pro) остаются.
_FILE_EXT = r"(?:html?|pdf|pptx?|docx?|xlsx?|csv|json|md|txt|py|js|css|zip|png|jpe?g|svg|mp3|wav|mp4)"
_SPEAK = [(r"(?:https?://|www\.)\S+", ""),
          (r"(?<![\w.])(?:[~/]?[\w.-]+/)+[\w-]+\." + _FILE_EXT + r"\b", ""),
          (r"(?<![\w.])(?:/?[A-Za-z0-9_.~-]+/){2,}[A-Za-z0-9_.-]*", ""),
          (r"(?<![\w.])([\w-]+)\." + _FILE_EXT + r"\b", r"\1"),
          (r"\bв т\.\s?ч\.", "в том числе"), (r"\bт\.\s?е\.", "то есть"), (r"\bи т\.\s?д\.", "и так далее"),
          (r"\bи т\.\s?п\.", "и тому подобное"), (r"\bт\.\s?к\.", "так как"), (r"\bнапр\.", "например"),
          (r":\s*[—–-]\s+", ": "),                                         # «Файл: — …» после вырезанного пути
          (r"\s+(?:и|или|в|на|по|из)\s*(?=[.,;:!?]|$)", ""),                # «… в report и .»
          (r"\s+([:,;—–-])\s*(?=[:,;.!?—–]|$)", ""), (r"\(\s*\)", "")]
_MD = [(re.compile(r"```.*?```", re.S), " "), (re.compile(r"`([^`]*)`"), r"\1"),
       (re.compile(r"<(script|style)\b.*?</\1\s*>", re.S | re.I), " "),          # HTML вслух не читаем (28.10: «зачитывала
       (re.compile(r"<!--.*?-->|<!doctype[^>]*>|</?[A-Za-z][\w:-]*(?:\s[^<>]*)?/?>", re.S | re.I), " "),   # все теги»)
       (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"), *[(re.compile(a, re.I), b) for a, b in _SPEAK],
       (re.compile(r"[*_#>|~]+"), ""), (re.compile(r"^\s*[-•]\s+", re.M), ""),
       (re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"), ""), (re.compile(r"\s+"), " ")]


def speakable(text):
    """Текст для голоса: без разметки Markdown, кода, эмодзи, ссылок и путей к файлам; сокращения — полными словами."""
    for rx, rep in _MD:
        text = rx.sub(rep, text)
    return text.strip()
