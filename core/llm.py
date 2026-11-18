"""«Мозг»: разговор с моделью — любой OpenAI-совместимый сервер (vLLM, Ollama, llama.cpp, LM Studio, OpenRouter,
OpenAI…), родной API Ollama (/api/chat) или Anthropic Claude.

stream_events() — поток ("text", кусок) и ("tools", вызовы). Сам подстраивается под сервер: что тот не принимает
(поле tools, роль tool, chat_template_kwargs, /chat/completions), запоминается по адресу в _no_tools, _flat, _native
до перезапуска. Здесь же: вырезание «размышлений» (ThinkStripper), вызовы функций из текста (ToolTagStripper,
parse_tool_call), проверка и поиск серверов (test_profile, probe_tools, probe_server, discover_local), подготовка
текста к озвучке (CodeFilter, SentenceSplitter, speakable). Способ вызова инструментов хранит engine_answer.py.

Части (чистое ядро, 1.0.15): llm_base — общее (журнал, что сервер отверг, «своя ли модель»); llm_text — ответ как текст
(размышления, вызовы не по протоколу, разбор вызова); llm_messages — история, кеш подсказки, учёт токенов; llm_hints —
как отвечать на вопрос (думать, температура, чтение, ожидание, иероглифы); llm_net — «Сеть Лиры»; llm_speech — текст
для озвучки. Здесь — соединение: поток stream_events, повторы, ошибки для человека, свои серверы. Проверки подменяют
llm.stream_events, llm.stream_chat, llm._port_open… — поэтому они и их вызывающие остаются в этом файле.
"""

import contextlib
import os
import json
import logging
import re
from html import unescape as html_unescape
import sys
import threading
import time

import httpx

from settings import LLM_PRESETS

# разбор и подготовка разложены по модулям (чистое ядро, 1.0.15 — docs/CORE_PLAN.md): общее — llm_base, ответ модели как текст — llm_text,
# история и кеш — llm_messages, поток ответа (SSE, сборка) — llm_sse, подсказки к вопросу — llm_hints, «Сеть Лиры» — llm_net, текст для голоса — llm_speech.
# Здесь — соединение с моделями: поток, повторы, свои серверы. Все прежние имена — по-прежнему llm.<имя>
from llm_base import (  # noqa: F401,E402 — прежние имена llm.* на месте
    LLMError, _flat, _llamacpp, _local_base, _LOCAL_HOST, log, _no_kw, _no_tools, _no_usage, prompt_tools_mode, _REJECT,
    _usage)
from llm_text import (  # noqa: F401,E402 — прежние имена llm.* на месте
    _arg_value, _ARGS_KEYS, _BARE_CALL, BareCallCatcher, _BR_CALL, BR_MAX, _BR_OPEN, _br_place_ok, _BR_POS,
    _BR_WORDS, bracket_call, BracketCallFilter, _call_parts, _DB, _DC, _DO, dsml_calls, _DSML_END, _DSML_INVOKE,
    _DSML_OPEN, _DSML_PARAM, _dsml_part, _DSML_STRAY, _DSML_WORDS, DSMLFilter, _FINAL_MARK, _HARMONY, _loads_loose,
    _NAME_KEYS, parse_tool_call, _REASON_START, _REASON_WORDS, repair_json, ThinkStripper, tools_prompt,
    ToolTagStripper, WIN_PATH_RX)
from llm_messages import (  # noqa: F401,E402 — прежние имена llm.* на месте
    ask_text, cache_hints, cache_key, _clean_messages, _ctx_cut, DEFAULT_MAX_TOKENS, drop_profile, flat_messages,
    _has_tool_history, hist_mark, image_block, last_usage, _mark_last_block, PROFILE_END, PROFILE_HEAD, put_profile,
    take_profile, take_usage, tool_turn_messages, usage_line, _usage_ok, user_message, with_tail)
from llm_hints import (  # noqa: F401,E402 — прежние имена llm.* на месте
    BUSY_RX, _CJK, _CJK_ASK, CREATIVE_ASK, CREATIVE_TEMP, creative_temp, drop_cjk, HARD_ASK, POEM_ASK, POEM_NOTE,
    prof_temp, RATE_WAIT, READ_ASK, READ_AUTHORS, READ_NOTE, reading, RECO_ASK, RECO_NOTE, _WAIT, wait_hint,
    wait_info, _wait_track, _wait_untrack, wants_cjk, wants_think, WRITE_ASK)
from llm_net import (  # noqa: F401,E402 — прежние имена llm.* на месте
    last_net, _net, _NET_ADDR_RX, net_args_bad, _NET_BRACKET_RX, net_calls_filter, net_enums, _NET_INSTR_RX,
    _NET_MARK_RX, _NET_MATH_RX, NET_SAFE_TOOLS, NET_SERVER_RX, net_suspect, NET_WRAP)
from llm_speech import (  # noqa: F401,E402 — прежние имена llm.* на месте
    CodeFilter, _FILE_EXT, _MD, _SENT_END, SentenceSplitter, _SPEAK, speakable)
from llm_sse import (  # noqa: F401,E402 — прежние имена llm.* на месте
    _Collector, _DONE_RX, _EOL_RX, _json_dict, _SSE_FIELD_RX, SSE_LINE_MAX, sse_lines, _stream_lines,
    turn_read_outside)


class HumanText(str):
    """Текст ошибки для экрана + короткая фраза для голоса и признак «нужна кнопка Пополнить»."""
    say = ""
    topup = False


# Модели не хватило окна контекста: LM Studio «Context size has been exceeded», llama.cpp «exceeds the available context
# size», vLLM «maximum context length», OpenAI «context_length_exceeded» (19.10: LM Studio с окном 4096 — три сбоя за ночь)
CTX_RX = re.compile(r"context (?:size|length|window)[^.]{0,40}(?:exceed|too)|exceeds? (?:the )?(?:available |maximum )?context|"
                    r"maximum context length|context_length_exceeded|n_ctx|prompt is too long|too many tokens|"
                    r"превыш\w* (?:размер|длин)\w* контекст|не хватило окна контекста", re.I)
# деньги на ключе сервиса кончились — повтор через 5 минут не поможет (пакет 30.10: дело по расписанию — 16 неудач за день)
NO_MONEY_TEXT = "на ключе нет оплаченного пакета или закончились деньги — пополните баланс у сервиса"
# Сбой 04.11 (27 раз, 8 компьютеров): «пополните баланс у сервиса» — у какого и где? Название и страница пополнения по адресу
# сервиса, и выход без своего ключа — облако Dewiar
TOPUP_PAGES = (("openrouter.ai", "OpenRouter", "https://openrouter.ai/settings/credits"),
               ("openai.com", "OpenAI", "https://platform.openai.com/settings/organization/billing"),
               ("deepseek.com", "DeepSeek", "https://platform.deepseek.com/top_up"),
               ("anthropic.com", "Anthropic", "https://console.anthropic.com/settings/billing"),
               ("mistral.ai", "Mistral", "https://console.mistral.ai/billing"),
               ("groq.com", "Groq", "https://console.groq.com/settings/billing"),
               ("x.ai", "xAI", "https://console.x.ai"),
               ("z.ai", "Z.ai", "https://z.ai"), ("bigmodel.cn", "Zhipu", "https://bigmodel.cn"),
               ("moonshot", "Moonshot", "https://platform.moonshot.ai"),
               ("googleapis.com", "Google AI Studio", "https://aistudio.google.com"),
               ("together", "Together AI", "https://api.together.ai"), ("fireworks.ai", "Fireworks", "https://fireworks.ai/account/billing"),
               ("perplexity.ai", "Perplexity", "https://www.perplexity.ai/settings/api"),
               ("yandex", "Yandex Cloud", "https://console.yandex.cloud"), ("sber", "GigaChat", "https://developers.sber.ru/studio"))
NO_MONEY_DEWIAR = "Без своего ключа — в «Мозге» выберите «Dewiar Облако»"


def topup_page(base_url):
    """Адрес сервиса -> (название, страница пополнения) или (адрес, "")."""
    host = (re.match(r"^\w+://([^/:?#]+)", str(base_url or "")) or [None, ""])[1].lower()
    for key, name, url in TOPUP_PAGES:
        if key in host:
            return name, url
    return host, ""


CTX_TEXT = ("модели не хватило окна контекста — разговор и подсказка не помещаются. В LM Studio или Ollama увеличьте "
            "длину контекста (Context Length) до 16384 или больше (с действиями нужно около 12–16 тыс.)")


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
                         r"no credits remaining|insufficient credits|can only afford|add (more )?credits|out of credits|"
                         # OpenRouter без денег: «Prompt tokens limit exceeded: 17987 > 17725 … upgrade to a paid account» —
                         # это не окно модели, а предел бесплатного ключа (сбои 18.11: тот же компьютер, тот же час)
                         r"prompt tokens limit exceeded", re.I)   # №324, OpenRouter
LOCATION_RX = re.compile(r"location is not supported|unsupported_country|not available in your (country|region)", re.I)


LOCAL_HOST_RX = re.compile(r"^(localhost|127\.|0\.0\.0\.0|\[?::1)")
LAN_HOST_RX = re.compile(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)|\.local$")
LOCAL_APPS = (("Ollama", 11434), ("LM Studio", 1234), ("vLLM", 8000), ("llama.cpp", 8080))
# модели с таким именем у сервиса нет (OpenRouter: «… is not a valid model ID», Ollama: «model "x" not found»)
NO_MODEL_RX = re.compile(r"not a valid model|model\b[^\n]{0,80}?\b(not found|does not exist|not exist)|unknown model|invalid model|"
                         r"no such model|model_not_found", re.I)


def _ip_base(base):
    """Модель по голому IP-адресу («прямое подключение»: свой сервер, Tailscale 100.x, VPS) — это свой сервер, а не облако:
    паузы между словами у него бывают долгими (длинная подсказка, размышления без потока) — ждём, как свою (идея №171)."""
    host = (re.match(r"^\w+://\[?([^/?#\]]+?)\]?(?::\d+)?(?:[/?#]|$)", str(base or "")) or [None, ""])[1]
    return bool(re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host) or (":" in host and re.fullmatch(r"[0-9a-fA-F:]+", host)))


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
    if LAN_HOST_RX.search(host) and u.scheme == "https" and _port_open(host, port):
        # №741 (15.11): «192.168.1.106:5000/v1» (OmniRoute) записалось как https:// — порт открыт, а сертификата у
        # своего сервера в сети нет
        return (f"{host}:{port} отвечает, но без https — у своих серверов в домашней сети его обычно нет. Впишите адрес "
                f"с http://, например http://{host}:{port}{u.path or '/v1'}")
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
    if isinstance(e, httpx.ProxyError) and "407" in str(e):
        # владелец 12.11: «Не получилось: 407 Proxy Authentication Required» — по-английски и непонятно, что делать
        return ("прокси не пустил: просит логин и пароль (407). Если это прокси Dewiar — я уже беру свежий, повторите через "
                "минуту; если свой — проверьте логин в студии → «Dewiar.pro» → «Сеть»")
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
            ej = ((j or {}).get("error") or {}) if isinstance(j, dict) else {}
            ej = ej if isinstance(ej, dict) else {}
            msg = ej.get("message", "")
        except Exception:  # noqa: BLE001
            msg, ej = "", {}
        if LOCATION_RX.search(body + " " + msg):
            return ("Gemini недоступен из вашей страны — Google не пускает к API отсюда. Включите VPN или прокси "
                    "(«Подключение» → «Прокси»), подключите Gemini через OpenRouter или выберите другой сервис")
        if NO_MONEY_RX.search(body + " " + msg) and "Dewiar" not in msg:
            zai = "z.ai" in str(base_url or "")
            name, page = topup_page(base_url)
            return (NO_MONEY_TEXT + (f" {name}" if name else "") + (f": {page}" if page else "")
                    + (". Подписка GLM Coding Plan работает по своему адресу (…/api/coding/paas/v4), и по правилам Z.ai — "
                       "только в программах для кода" if zai else "") + ". " + NO_MONEY_DEWIAR)
        if msg and code == 402 and (ej.get("topup") or "Dewiar" in msg or "Талер" in msg):
            # облако Dewiar: талеры кончились (0.82.1) — на экран полный текст с номером DW-…, голосом — коротко, без ссылки
            t = HumanText(msg.rstrip("."))
            t.say, t.topup = str(ej.get("say") or "Талеры закончились. Пополнить — кнопкой на экране."), True
            return t
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
        if re.search(r"<(?:!doctype|html|body|pre|title)\b", body, re.I):
            # №652 (ночной разбор 11.11): «сервер ответил ошибкой 500: <!DOCTYPE html> <html lang="en"> <head>…» — страница
            # ошибки сервера модели; человеку — её текст без разметки и что делать
            try:
                raw = e.response.text[:4000]
            except Exception:  # noqa: BLE001
                raw = body
            txt = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", raw)
            txt = re.sub(r"\s+", " ", html_unescape(re.sub(r"(?s)<[^>]+>", " ", txt))).strip()[:160]
            return (f"сервер модели ответил ошибкой {code}" + (f" («{txt}»)" if txt else "")
                    + (" — это сбой у сервера модели, не у вас: повторите через минуту; повторяется — перезапустите сервер "
                       "модели или выберите в «Мозге» другую" if code >= 500 else ""))
        return f"сервер ответил ошибкой {code}: {body}"
    return str(e)


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
    if p.get("cloud"):
        h["X-Dewiar-Pay"] = "2"          # облако Dewiar (0.82.1): умеем кнопку «Пополнить» — 402 с номером DW-… и короткой фразой
    if "opencode.ai" in str(p.get("base_url") or "").lower():
        # №524 (04.11): OpenCode Go без заголовка сессии отвечает 400 MissingSessionID («cannot be routed efficiently»).
        # Постоянный id этой установки — один и тот же между запусками (сервис держит кэш разговора по сессии)
        h["x-opencode-session"] = opencode_session()
    # «Сеть Лиры»: человек разрешил общие вопросы на узлы людей (liranet.py) — и только основной ход разговора: флаг _net_turn
    # ставит engine_answer._run_turn (не в детском режиме и не «Для старших»); служебные вызовы (плагины, уроки из поправок,
    # перевод итога задачи, бот персонажа, экзамен) идут тем же профилем, но без флага — в сеть никогда (рецензия 04.11)
    if p.get("cloud") and p.get("net") and p.get("_net_turn"):
        h["X-Dewiar-Net"] = "1"
    return h


_OC_SESSION = []


def opencode_session(path=None):
    """Постоянный id сессии для OpenCode (x-opencode-session): случайный, хранится в STATE_DIR/opencode.session;
    не записался — свой на время работы программы."""
    if _OC_SESSION and path is None:
        return _OC_SESSION[0]
    import uuid
    try:
        if path is None:
            from settings import STATE_DIR
            path = STATE_DIR / "opencode.session"
        sid = path.read_text(encoding="ascii").strip() if path.exists() else ""
        if not re.fullmatch(r"[0-9a-f-]{16,64}", sid):
            sid = str(uuid.uuid4())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(sid, encoding="ascii")
    except (OSError, UnicodeError):
        sid = str(uuid.uuid4())
    _OC_SESSION[:] = [sid]
    return sid


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


def stream_events(p, system, messages, cancel=None, tools=None, _retry=0):
    """Поток событий: ("text", кусок) и в конце, если модель решила действовать,
    ("tools", [{"id", "name", "args"}]). cancel — threading.Event для мгновенной остановки. Ошибки — LLMError.

    Пока модель не сказала ни слова, отказы сервера чинит сама и повторяет запрос: история вызовов текстом,
    функции текстом, без chat_template_kwargs, родной API Ollama, короче (_lite). Если всё время ушло на
    «размышления» и текста нет — повторит с выключенными размышлениями и вчетверо большим лимитом.
    Служебные ключи профиля с «_» (_flat, _lite, _no_kwargs, _empty_retry) ставит только сама при повторах."""
    base = _base(p)
    tools_all = tools
    turn_read = turn_read_outside(messages)
    _usage.v = _usage.out = None
    if tools and prompt_tools_mode(p):
        system = system + tools_prompt(tools)            # сервер не принимает функции полем — описываем текстом
        tools = None
    native = p.get("kind") == "ollama" or base in _native
    max_tokens = int(p.get("max_tokens") or DEFAULT_MAX_TOKENS)
    # Размышления выключены по умолчанию: качество ответов помощника почти не растёт, а ответ заметно медленнее.
    # Включить — только явно, "think": "on" в профиле; при повторе после пустого ответа — выключены всегда.
    no_think = p.get("think") != "on" or _retry > 0
    st = _wait_track(cancel, base, p, no_think)                 # чего ждём (wait_info) — для «модель отвечает медленно»
    try:
        model = resolve_model(p)
        native = p.get("kind") == "ollama" or base in _native    # ещё раз: resolve_model мог узнать, что тут только Ollama
        # своя модель на этом компьютере или в сети (YouTube 26.10: llama.cpp, 27B на встроенной графике — «долгий префил,
        # Dewiar прерывал генерацию и не отвечал на часть вопросов»): первое слово ждём до 10 минут, облако — 3
        # соединение: своя модель — 5 с; облако — 10 с (1.0 «без ответа»: «сервер модели не ответил вовремя» — 406 раз у 119
        # компьютеров за 30 дней, отчёт №69 — через 5 с; рукопожатие TLS через прокси, VPN, телефон-модем дольше 5 с)
        near = _local_base(base) or _ip_base(base)
        timeout = httpx.Timeout(5 if near else 10, read=float(p.get("timeout") or (600 if near else 180)))
        if p.get("kind") == "anthropic":
            url = _anth_root(base) + "/v1/messages"
            # кэш подсказки (GitHub PR №24, maghelp, 26.10): инструменты (≈13 тыс. токенов) и характер уходят с каждым
            # шагом — с cache_control Claude берёт их из кэша в ~10 раз дешевле. Метки — на последнем инструменте и на
            # подсказке (порядок кэша: инструменты → system → сообщения)
            body = {"model": model, "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}] if system else system,
                    "messages": with_tail(p, messages, p.get("_tail")) if p.get("_tail") else hist_mark(messages, True), "stream": True,
                    "max_tokens": max_tokens, "temperature": prof_temp(p)}
            if tools:
                body["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                                 for t in tools]
                body["tools"][-1] = dict(body["tools"][-1], cache_control={"type": "ephemeral"})
        elif native:
            url = _root(base) + "/api/chat"
            body = {"model": model, "stream": True, "messages": with_tail(p, _to_ollama([{"role": "system", "content": system}] + messages), p.get("_tail")),
                    "options": {"num_predict": max_tokens, "temperature": prof_temp(p)}}
            if no_think:
                body["think"] = False
            if tools:
                body["tools"] = [{"type": "function", "function": t} for t in tools]
        else:
            url = base + "/chat/completions"
            hist = _clean_messages(flat_messages(messages) if (p.get("_flat") or base in _flat or prompt_tools_mode(p) or not tools)
                                   and _has_tool_history(messages) else messages)
            if p.get("_lite"):                         # последняя попытка: короче — начало задачи и последние шаги
                hist = (hist[:1] + [{"role": "assistant", "content": "…"}] + hist[-10:]) if len(hist) > 12 else hist
                system = system[:14000]
            hist = with_tail(p, hist, p.get("_tail"))   # задача: «Состояние задачи» — последним, после истории
            body = {"model": model, "stream": not p.get("_whole"),     # «целиком» — последняя попытка после пустого потока
                    "messages": [{"role": "system", "content": system}] + hist,
                    "max_tokens": max_tokens, "temperature": prof_temp(p)}
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
            # «Голос без пауз»: сколько токенов в подсказке и сколько сервер взял из кэша — в журнал и в пульс
            if body["stream"] and _usage_ok(p, base):
                body["stream_options"] = {"include_usage": True}
            cache_hints(body, base, model)          # 0.87: кэш начала запроса — llama.cpp, OpenRouter (Claude, Gemini), OpenAI
        col = _Collector(anthropic=p.get("kind") == "anthropic")
        col.cancel = cancel                                      # «Стоп» — и посреди длинной строки потока (sse_lines)
        # голый JSON в тексте — вызов, только если такая функция есть (или её зовут по имени — _known: задача, совместимость)
        known_names = [x["name"] for x in (tools_all or [])] + ([n for n in p.get("_known") or ()] if tools_all else [])
        col.tags.known = set(known_names)
        col.tags.no_bracket = turn_read                     # рецензия 0.86: в ходе уже читали внешнее — «[Вызов…]» не вызов
        col.no_cjk = not wants_cjk(messages)
        net_buf = []
        _net.v = False
        if p.get("cloud"):                       # «Сеть Лиры»: что спрашивал человек — для проверки вызовов от узла
            last_u = next((m for m in reversed(messages) if m.get("role") == "user"), {})
            lc = last_u.get("content")
            col.net_q = ask_text(lc if isinstance(lc, str) else " ".join(str(x.get("text") or "") for x in lc or [] if isinstance(x, dict)))
            col.net_enums = frozenset(net_enums([t.get("parameters") for t in tools_all or []]))
        bare = BareCallCatcher(known_names if prompt_tools_mode(p) or native else [])
        got_text = False
        with _stream_retry("POST", url, json=body, headers=_headers(p), timeout=timeout) as r:
            if r.status_code >= 400:
                r.read()
                err = r.text.lower()
                n = int(p.get("_rl") or 0)
                if r.status_code in (400, 413, 422) and CTX_RX.search(err):
                    # не хватило окна — это не отказ формата: не упрощать историю вызовов (_flat запоминается для сервера
                    # навсегда), а сразу к короткой истории (_ctx_retry) или к сжатию задачи (tasks: _ctx в профиле)
                    raise LLMError(CTX_TEXT)
                if r.status_code == 407:
                    # владелец 12.11: прокси между компьютером и моделью просит логин — понятным текстом; прокси Dewiar —
                    # сразу свежий логин (net.on_proxy_auth)
                    import net as net407
                    if net407.on_proxy_auth:
                        try:
                            net407.on_proxy_auth()
                        except Exception:  # noqa: BLE001
                            pass
                    raise LLMError(_humanize(httpx.ProxyError("407 Proxy Authentication Required"), base))
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
                # «много запросов» — подождать (денег нет — не ждать; свой лимит дня или месяца облака Dewiar — тоже: до завтра)
                if r.status_code == 429 and n < len(RATE_WAIT) and not NO_MONEY_RX.search(err) and not re.search(r'"(?:user_limit|day_limit)"', err):
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
                usage_err = bool(re.search(r"stream_options|include_usage|extra (?:fields|inputs)|unrecognized|unknown (?:field|param)", err))
                # отказ назвал другую причину (функции полем, картинки, max_completion_tokens, chat_template_kwargs) — дело
                # не в подсчёте токенов: сразу к нужному упрощению, без лишнего запроса (prompt_tools_test: vLLM без
                # --enable-auto-tool-choice — было три запроса вместо двух)
                other_err = not usage_err and bool((tools and ("tool" in err or "function" in err)) or "image" in err
                                                   or "max_completion_tokens" in err or "chat_template_kwargs" in err)
                if "stream_options" in body and r.status_code in (400, 422) and not other_err:
                    # сказал, что не понимает поле, — больше не просим; отказ без объяснений — один повтор без него (этот
                    # запрос), дальше — обычные упрощения
                    if usage_err:
                        _no_usage.add(base)
                    log.info("Сервер %s отклонил запрос (%s) — повторяю без подсчёта токенов (stream_options)", base, r.status_code)
                    yield from stream_events(dict(p, _no_usage=True), system, messages, cancel, tools, _retry)
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
            if str(r.headers.get("x-dewiar-server") or "").startswith("n"):
                col.net = True                                   # ответил узел «Сети Лиры» (не потоком — по заголовку)
            if st is not None:
                st["phase"] = "stream"                           # сервер ответил — дальше ждём слов модели
            for line in _stream_lines(r, col):
                if cancel is not None and cancel.is_set():
                    return
                if _DONE_RX.match(line):
                    # 04.11: «data: [DONE]» — конец ответа; не ждём, пока сервер закроет соединение (шлюз мог держать его
                    # открытым, а облако — слать «: keepalive»: ход ждал минутами)
                    break
                piece = bare.feed(col.feed_line(line))
                if st is not None:
                    st.update(reasoning=col.reasoning, calls=bool(col.calls), last=time.monotonic())
                if piece and col.net:
                    net_buf.append(piece)                    # узел сети: придерживаем до конца (net_suspect)
                elif piece:
                    got_text = True
                    if st is not None:
                        st["text"] = True
                    yield "text", piece
            if col.pending:
                try:
                    piece = bare.feed(col.feed_obj(json.loads(col.pending)))
                    col.pending = ""
                    if piece and col.net:
                        net_buf.append(piece)
                    elif piece:
                        got_text = True
                        yield "text", piece
                except ValueError:
                    pass
            if not (cancel is not None and cancel.is_set()):
                piece = bare.feed(col.flush())
                if piece and col.net:
                    net_buf.append(piece)
                elif piece:
                    got_text = True
                    yield "text", piece
        if col.usage:
            _usage.v = col.usage
        _usage.out = col.out
        if col.llamacpp and base not in _llamacpp:
            _llamacpp.add(base)
        calls = col.tool_calls()
        held, bare_calls = bare.finish()
        if col.net and bare_calls:                               # узел сети: голый JSON — не вызов, просто текст
            log.warning("🌐 Сеть Лиры: узел прислал вызов голым JSON — не выполняю")
            bare_calls = []
        if col.net:
            ntext = "".join(net_buf) + (held or "")
            held = ""
            why = "текст узла с вызовами" if col.tags.calls() else net_suspect(ntext, [x["name"] for x in tools_all or []], col.net_q)
            if why and not (cancel is not None and cancel.is_set()):
                log.warning("🌐 Сеть Лиры: ответ узла не показываю (%s) — спрашиваю главный мозг", why)
                _net.v = False
                yield from stream_events(dict(p, _net_turn=False), system, messages, cancel, tools, _retry)
                return
            _net.v = True
            if ntext:
                got_text = True
                yield "text", ntext
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
            if not p.get("_whole") and p.get("kind") not in ("anthropic", "ollama"):
                # пакет 30.10: «сервер вернул ответ без текста» (qwen3.8-omni-flash у стороннего сервиса, 27 раз) — облако Dewiar
                # спасает такие ответы, переспрашивая «целиком», без потока; так и здесь, последней попыткой
                log.info("Сервер %s дважды пусто в потоке — спрашиваю целиком, без потока", base)
                yield from stream_events(dict(p, _whole=True), system, messages, cancel, tools, _retry)
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
    finally:
        _wait_untrack(cancel, st)


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


def _models_at(url, timeout=0.6, key="", known=""):
    """Список моделей сервера по адресу …/v1 или None, если там никто не отвечает. key — ключ своего профиля (№821, 17.11:
    Strata на 127.0.0.1 отвечает на /models только с ключом — «Нода Лиры» её не видела); known — модель профиля: сервер
    отвечает, а списка моделей не даёт (нет /models) — значит, есть та, которой уже думаем."""
    try:
        r = httpx.get(url + "/models", timeout=timeout, headers={"Authorization": f"Bearer {key}"} if key else None)
        if r.status_code == 200:
            ids = [m.get("id") for m in (r.json().get("data") or []) if isinstance(m, dict) and m.get("id")]
            return ids or ([known] if known else ids)
        if known and r.status_code in (404, 405):
            return [known]
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
    if not url:
        # №496 (03.11): «Success! Server is now running on port 1234», а status() не узнал — порт из ответа start и
        # подольше (сервер поднимается дольше 8 с), и на localhost тоже (иногда слушает только ::1)
        m = re.search(r"port\D{0,12}(\d{2,5})", (r.stdout or "") + (r.stderr or ""), re.I)
        if m and re.search(r"success|running", (r.stdout or "") + (r.stderr or ""), re.I):
            for _ in range(30):
                for host in ("127.0.0.1", "localhost"):
                    u = f"http://{host}:{m.group(1)}/v1"
                    if _models_at(u, 1.0) is not None:
                        return u, True
                time.sleep(0.5)
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


