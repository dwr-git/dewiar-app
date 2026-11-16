"""История и кеш (llm.py): профиль ассистента в подсказке, вопрос без справки (ask_text), учёт токенов, метки кеша
подсказки, история для серверов без инструментов (flat_messages), чистка сообщений, сообщения с картинками и шаг
с результатами действий."""

import json
import re

from llm_base import _llamacpp, _local_base, _no_usage, prompt_tools_mode, _usage


# «Голос без пауз» (идея №5, 04.11): личное — память о человеке, его имя, душа, свежие выводы, счётчики дел, свои
# компьютеры — не в системной подсказке, а справкой в начале первого сообщения разговора. У Qwen (облако Dewiar, vLLM)
# описания инструментов идут в шаблоне сразу ПОСЛЕ подсказки: любая личная мелочь в подсказке ломала кэш начала запроса
# (APC) и для всех ~13 тыс. токенов инструментов, а у разных людей общего начала было ~1,5 тыс. токенов. Теперь подсказка
# и инструменты одинаковы у всех с одним персонажем и настройками — сервер держит их в кэше один раз для всех.
PROFILE_HEAD = "(О пользователе и о тебе — справка от программы, вслух её не упоминай)\n"


PROFILE_END = "\n\n(Дальше — разговор)\n"


def put_profile(messages, text):
    """Личную справку — в начало первого сообщения (не меняя исходный список). Первое — ответ ассистента или вызов —
    отдельным сообщением пользователя перед ним. -> новый список."""
    text = (text or "").strip()
    if not text or not messages:
        return list(messages or [])
    head = PROFILE_HEAD + text + PROFILE_END
    m0 = messages[0]
    if m0.get("role") == "user" and not m0.get("tool_call_id"):
        c = m0.get("content")
        if isinstance(c, list):
            c = [dict(x) for x in c]
            i = next((i for i, x in enumerate(c) if x.get("type") == "text"), None)
            if i is None:
                c.insert(0, {"type": "text", "text": head.rstrip()})
            else:
                c[i]["text"] = head + str(c[i].get("text") or "")
        else:
            c = head + str(c or "")
        return [dict(m0, content=c)] + list(messages[1:])
    return [{"role": "user", "content": head.rstrip()}] + list(messages)


def take_profile(messages):
    """Личная справка из начала первого сообщения (put_profile) -> её текст или ""."""
    if not messages:
        return ""
    c = messages[0].get("content")
    if isinstance(c, list):
        c = next((x.get("text") for x in c if isinstance(x, dict) and x.get("type") == "text"), "")
    c = c if isinstance(c, str) else ""
    if not c.startswith(PROFILE_HEAD):
        return ""
    rest = c[len(PROFILE_HEAD):]
    if PROFILE_END in rest:
        return rest.split(PROFILE_END, 1)[0]
    end = PROFILE_END.rstrip()                         # справка отдельным сообщением — метка в самом конце, без «\n»
    return rest[:-len(end)] if rest.endswith(end) else rest


def drop_profile(messages):
    """Без личной справки (самая короткая подсказка для крошечного окна): отдельное сообщение — прочь, голова первого — прочь."""
    if not messages or not take_profile(messages):
        return list(messages or [])
    m0 = messages[0]
    c = m0.get("content")
    if isinstance(c, list):
        c = [dict(x) for x in c]
        i = next((i for i, x in enumerate(c) if x.get("type") == "text"), None)
        t = str(c[i].get("text") or "")
        c[i]["text"] = t.split(PROFILE_END, 1)[1] if PROFILE_END in t else ""
        return [dict(m0, content=c)] + list(messages[1:])
    if PROFILE_END not in c:                           # отдельным сообщением
        return list(messages[1:])
    return [dict(m0, content=c.split(PROFILE_END, 1)[1])] + list(messages[1:])


def ask_text(t):
    """Сам вопрос человека — без личной справки и справки к вопросу (их вставляет программа)."""
    t = t or ""
    for mark in ("(Сообщение пользователя)\n", PROFILE_END):
        if mark in t:
            return t.rsplit(mark, 1)[1]
    return t


def _ctx_cut(messages):
    """Короткая история: только текущая просьба и то, что модель уже сделала по ней (вызовы и результаты).
    Личная справка (put_profile) из начала разговора переезжает в начало оставшегося — память о человеке не теряется."""
    prof = take_profile(messages)
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if m.get("role") == "user" and isinstance(m.get("content"), (str, list)) and not m.get("tool_call_id"):
            return put_profile(messages[i:], prof) if prof and i > 0 else messages[i:]
    return put_profile(messages[-1:], prof) if prof and len(messages) > 1 else messages[-1:]


def last_usage():
    """Сколько токенов было в подсказке последнего запроса этого потока и сколько из них сервер взял из кэша начала
    запроса: {"prompt": N, "cached": M или None (сервер не сказал)} или None. Читается один раз."""
    u = getattr(_usage, "v", None)
    _usage.v = None
    return u


def take_usage():
    """Для задач: {"prompt", "cached", "out"} последнего запроса этого потока (что сервер сказал; None — не сказал) или
    None, если сервер не посчитал ничего. Читается один раз."""
    u, o = getattr(_usage, "v", None), getattr(_usage, "out", None)
    _usage.v = _usage.out = None
    if not u and not o:
        return None
    return {"prompt": (u or {}).get("prompt"), "cached": (u or {}).get("cached"), "out": o}


def _mark_last_block(m, anth):
    """Сообщение с меткой кэша (cache_control) на последнем непустом блоке; нечего метить — None."""
    c = m.get("content")
    if isinstance(c, str):
        return dict(m, content=[{"type": "text", "text": c, "cache_control": {"type": "ephemeral"}}]) if c else None
    if not isinstance(c, list) or not c:
        return None
    blocks = [dict(b) if isinstance(b, dict) else b for b in c]
    b = blocks[-1]
    if not isinstance(b, dict):
        return None
    kinds = ("text", "tool_result", "tool_use", "image") if anth else ("text",)
    if b.get("type") not in kinds or (b.get("type") == "text" and not b.get("text")):
        return None
    b["cache_control"] = {"type": "ephemeral"}
    return dict(m, content=blocks)


def hist_mark(messages, anth=False):
    """0.87, кэш подсказки у Claude (и у Claude/Gemini через OpenRouter): метка кэша на конце истории — на сообщении
    перед последним (последнее — новый вопрос со справкой к нему, оно всегда своё). Тогда следующий вопрос берёт из
    кэша и разговор, а не только инструменты и подсказку. -> новый список, исходный не тронут."""
    msgs = list(messages or [])
    for i in range(len(msgs) - 2, -1, -1):
        if not anth and (msgs[i].get("role") != "user" or msgs[i].get("tool_call_id")):
            continue                               # OpenRouter: метки — в сообщениях пользователя (как в их примерах)
        m = _mark_last_block(msgs[i], anth)
        if m is not None:
            msgs[i] = m
            break
    return msgs


def cache_key(system):
    """Ключ кэша для OpenAI (prompt_cache_key): одинаковое начало запроса — один ключ, без личного (хэш подсказки)."""
    import hashlib
    return "dewiar-" + hashlib.sha1((system or "")[:8000].encode("utf-8", "replace")).hexdigest()[:16]


def cache_hints(body, base, model):
    """Подсказки серверу про кэш начала запроса (0.87; «⏱ … из кэша 0 (0%)» в журналах людей):
    - llama.cpp (узнали по timings в ответе) — cache_prompt: true (в старых сборках и обёртках по умолчанию выключен);
    - OpenRouter, модели Claude и Gemini — метки cache_control на подсказке и на конце истории (без них Claude там не
      кэширует вовсе — каждый вопрос по полной цене);
    - OpenAI напрямую — prompt_cache_key: запросы с тем же началом попадают на ту же машину с кэшем.
    Незнакомым сервисам ничего не добавляем: лишнее поле там — ошибка 400. -> body (тот же словарь)."""
    host = re.sub(r"^\w+://", "", base or "").split("/")[0].split(":")[0].lower()
    mdl = str(model or "").lower()
    if base in _llamacpp:
        body["cache_prompt"] = True
    elif re.search(r"(^|\.)openrouter\.ai$", host) and re.match(r"(?:~?anthropic/|google/gemini)", mdl):
        msgs = body.get("messages") or []
        if msgs and msgs[0].get("role") == "system" and isinstance(msgs[0].get("content"), str) and msgs[0]["content"]:
            msgs = [dict(msgs[0], content=[{"type": "text", "text": msgs[0]["content"], "cache_control": {"type": "ephemeral"}}])] + msgs[1:]
        if len(msgs) > 2:
            msgs = msgs[:1] + hist_mark(msgs[1:])
        body["messages"] = msgs
    elif re.search(r"(^|\.)openai\.com$", host):
        msgs = body.get("messages") or []
        if msgs and msgs[0].get("role") == "system":
            body["prompt_cache_key"] = cache_key(str(msgs[0].get("content") or ""))
    return body


def with_tail(p, messages, tail):
    """Изменчивое — в конец запроса (выпуск 1 «Больших задач», docs/HARNESS.md): «Состояние задачи» (время, план, блокнот)
    идёт последним, после истории, и в историю не пишется — начало запроса (подсказка, инструменты, история) остаётся
    байт в байт тем же от шага к шагу, и сервер берёт его из кэша. Последнее сообщение пользователя — дописываем к нему
    (две реплики подряд принимают не все шаблоны), иначе — новое сообщение. Claude: метка кэша — на последнем блоке истории
    (до состояния). -> новый список, исходный не тронут."""
    if not tail:
        return messages
    msgs = list(messages)
    anth = p.get("kind") == "anthropic"
    last = msgs[-1] if msgs else None
    if anth:
        if last is not None:
            c = last.get("content")
            blocks = [{"type": "text", "text": c}] if isinstance(c, str) else [dict(b) for b in (c or [])]
            if blocks and blocks[-1].get("type") in ("text", "tool_result", "tool_use", "image") and \
                    (blocks[-1].get("type") != "text" or blocks[-1].get("text")):
                blocks[-1]["cache_control"] = {"type": "ephemeral"}
            if last.get("role") == "user":
                msgs[-1] = dict(last, content=blocks + [{"type": "text", "text": tail}])
                return msgs
            msgs[-1] = dict(last, content=blocks)
        return msgs + [{"role": "user", "content": [{"type": "text", "text": tail}]}]
    if last is not None and last.get("role") == "user" and not last.get("tool_call_id"):
        c = last.get("content")
        if isinstance(c, str):
            msgs[-1] = dict(last, content=c + "\n\n" + tail)
            return msgs
        if isinstance(c, list):
            msgs[-1] = dict(last, content=list(c) + [{"type": "text", "text": tail}])
            return msgs
    return msgs + [{"role": "user", "content": tail}]


def usage_line(u, sec=None):
    """«⏱ модель: 6.1 с, подсказка 12 400 ток., из кэша 11 900» — для журнала."""
    def n(x):
        return f"{int(x):,}".replace(",", " ")
    out = "⏱ модель" + (f": {sec:.1f} с," if sec is not None else ":") + f" подсказка {n(u['prompt'])} ток."
    if u.get("cached") is not None:
        out += f", из кэша {n(u['cached'])}" + (f" ({100 * u['cached'] / u['prompt']:.0f}%)" if u["prompt"] else "")
    else:
        out += ", сколько из кэша — сервер не сообщает"
    return out


def _usage_ok(p, base):
    """Просить ли подсчёт токенов в конце потока (stream_options.include_usage). Только там, где поле точно понимают:
    облако Dewiar, своя модель (vLLM, llama.cpp, LM Studio, Ollama), OpenAI, OpenRouter, DeepSeek. Незнакомое поле
    другим сервисам — ошибка 400, а за ней цепочка упрощений запроса — не рискуем."""
    if p.get("_no_usage") or base in _no_usage or p.get("_whole"):
        return False
    host = re.sub(r"^\w+://", "", base).split("/")[0].split(":")[0].lower()
    return bool(p.get("cloud") or "dewiar" in host or _local_base(base)
                or re.search(r"(^|\.)(openai\.com|openrouter\.ai|deepseek\.com)$", host))


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
    """Пустой текст ассистента — "" а не null: часть серверов отклоняет null. №798 (16.11, шлюз Vercel AI Gateway):
    «user message must have content» — в истории оказалось сообщение человека без текста, и ни один вопрос больше не
    проходил. Пустое сообщение человека — «…» (роль и порядок те же)."""
    out = []
    for m in messages:
        c = m.get("content")
        if c is None and m.get("role") == "assistant":
            m = dict(m, content="")
        elif m.get("role") == "user" and not m.get("tool_call_id") and (c is None or (isinstance(c, str) and not c.strip())):
            m = dict(m, content="…")
        out.append(m)
    return out


# Лимит ответа, если в профиле не задан: при меньшем ответ обрывается, когда модель начинает размышлять,
# а аргументы инструментов (файл, страница) не помещаются целиком.
DEFAULT_MAX_TOKENS = 2048


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
