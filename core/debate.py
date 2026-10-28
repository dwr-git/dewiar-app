"""«Спор моделей» (0.62; план «Идей Лиры»: «две модели обсуждают трудный вопрос, а Лира подводит итог: где они согласны и
в чём разошлись»). Голосом: «пусть модели поспорят: стоит ли переходить на четырёхдневку?» — инструмент debate.

Кто спорит: основной мозг (активный профиль) и второй — другой профиль из «Мозга» с другой моделью; если второго нет, а
основной — облако Dewiar или сервис со списком моделей, — другая модель того же сервиса. Нет второй модели — честно
сказать, где её добавить. Два круга: каждая отвечает сама (одновременно), потом каждая видит ответ другой и коротко
возражает или соглашается. Итог подводит Лира (модель разговора) по тексту, который возвращает инструмент."""
import threading

from llm import chat_models, list_models, stream_chat

FIRST = ("Ты участвуешь в споре двух моделей ИИ. Ответь на вопрос по существу и со своей позицией: 5–7 предложений, "
         "главные доводы, без воды и без списков. Не пиши, что ты модель.")
SECOND = ("Ты участвуешь в споре двух моделей ИИ. Вот вопрос, твой первый ответ и ответ другой модели. Коротко, 3–4 "
          "предложения: в чём ты согласна, с чем не согласна и почему; можешь уточнить свою позицию.")


class DebateError(Exception):
    pass


def _label(p):
    m = str(p.get("model") or "").split("/")[-1]
    return m or p.get("name") or "модель"


def pick_pair(settings):
    """-> (основной профиль, второй профиль). Второй — другая модель; нет — DebateError с подсказкой."""
    llm = settings.get("llm") or {}
    profs = llm.get("profiles") or {}
    a = dict(profs.get(llm.get("active")) or {})
    if not a.get("base_url"):
        raise DebateError("сначала подключите мозг — студия → «Мозг»")
    for pid, p in profs.items():
        if pid != llm.get("active") and p.get("base_url") and p.get("model") and p.get("model") != a.get("model"):
            return a, dict(p)
    try:                                              # тот же сервис, другая модель (облако Dewiar, OpenRouter, Ollama)
        ms = [m for m in chat_models(list_models(a)) if m != a.get("model")]
    except Exception:  # noqa: BLE001
        ms = []
    if ms:
        pref = [m for m in ms if not any(w in m.lower() for w in ("embed", "whisper", "tts", "rerank", "vision"))] or ms
        return a, dict(a, model=pref[0])
    raise DebateError("для спора нужна вторая модель: добавьте её в студии → «Мозг» → «Добавить» (другой сервис или модель)")


def _ask(p, system, text, out, key, cancel=None):
    try:
        out[key] = "".join(stream_chat(dict(p, max_tokens=700, temperature=0.7), system, [{"role": "user", "content": text}], cancel)).strip()
    except Exception as e:  # noqa: BLE001
        out[key] = ""
        out[key + "_err"] = str(e)[:200]


def run(question, a, b, cancel=None):
    """Два круга -> {a: {name, first, reply}, b: {…}}."""
    q = str(question or "").strip()
    if len(q) < 5:
        raise DebateError("о чём спорить? скажите вопрос целиком")
    out = {}
    ts = [threading.Thread(target=_ask, args=(p, FIRST, q, out, k, cancel), daemon=True) for k, p in (("a1", a), ("b1", b))]
    [t.start() for t in ts]
    [t.join(120) for t in ts]
    if not out.get("a1") or not out.get("b1"):
        bad = _label(a) if not out.get("a1") else _label(b)
        raise DebateError(f"модель {bad} не ответила" + (f": {out.get('a1_err') or out.get('b1_err')}" if out.get("a1_err") or out.get("b1_err") else ""))
    r2 = lambda mine, other: f"Вопрос: {q}\n\nТвой первый ответ:\n{mine}\n\nОтвет другой модели:\n{other}"   # noqa: E731
    ts = [threading.Thread(target=_ask, args=(a, SECOND, r2(out["a1"], out["b1"]), out, "a2", cancel), daemon=True),
          threading.Thread(target=_ask, args=(b, SECOND, r2(out["b1"], out["a1"]), out, "b2", cancel), daemon=True)]
    [t.start() for t in ts]
    [t.join(120) for t in ts]
    return {"q": q, "a": {"name": _label(a), "first": out["a1"], "reply": out.get("a2", "")},
            "b": {"name": _label(b), "first": out["b1"], "reply": out.get("b2", "")}}


def context(d):
    """Текст для модели разговора: что сказали обе, — и как подвести итог."""
    a, b = d["a"], d["b"]
    return (f"[Спор моделей] Вопрос: {d['q']}\n\n{a['name']} (первый ответ): {a['first']}\n\n{b['name']} (первый ответ): {b['first']}\n\n"
            + (f"{a['name']} отвечает на доводы {b['name']}: {a['reply']}\n\n" if a["reply"] else "")
            + (f"{b['name']} отвечает на доводы {a['name']}: {b['reply']}\n\n" if b["reply"] else "")
            + "Подведи итог для пользователя своими словами, 4–6 предложений: в чём модели согласны, в чём разошлись и "
              "какой довод кажется сильнее; назови модели по именам. Без списков. Решение оставь пользователю.")
