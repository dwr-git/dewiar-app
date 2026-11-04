"""Руководство Dewiar для самой помощницы: «как добавить маму в близкие?», «где поменять фон?» — ответ из data/guide.json,
того же текста, что на странице руководства (server/dwrapp/guide.php) и на телефоне (android: guide.js, тот же поиск).
Поиск без словаря: слова запроса по основе (без окончания) сверяются с началом слов раздела; ключевые слова и заголовок
весят больше. -> разделы целиком (что это, как, фразы, советы) и ссылка на раздел на сайте."""
import json
import re

from settings import DATA_DIR

URL = "https://dewiar.pro/dwrapp/guide.php"
STOP = set("как мне мой моя мои что где это для или при на в с и а не по из у о к ли же бы то можно хочу надо нужно сделать чтобы про над под без "
           "dewiar девиар лира приложение".split())
_cache = None


def load():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads((DATA_DIR / "guide.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = []
    return _cache


def _norm(t):
    return str(t or "").lower().replace("ё", "е")


def _stem(w):
    return w[:-2] if len(w) >= 6 else w[:-1] if len(w) >= 4 else w


def _words(t):
    return [w for w in re.split(r"[^a-zа-я0-9]+", _norm(t)) if w]


def search(query, where="", n=2):
    q = [_stem(w) for w in _words(query) if len(w) > 1 and w not in STOP]
    if not q:
        return []
    out = []
    for s in load():
        if where and where not in (s.get("where") or []):
            continue
        kw = _words(" ".join(s.get("keywords") or []) + " " + s.get("title", ""))
        tx = _words(" ".join([s.get("lead", "")] + list(s.get("how") or []) + list(s.get("say") or []) + list(s.get("tips") or [])))
        score = hit = 0
        for w in q:
            a = any(x.startswith(w) for x in kw)
            b = a or any(x.startswith(w) for x in tx)
            hit += b
            score += 3 if a else 1 if b else 0
        if hit:
            out.append((score + hit * 2, s))
    out.sort(key=lambda x: -x[0])
    return [s for _, s in out[:n]]


def hint(query, where=""):
    """Вопрос явно про само приложение («как защищены мои данные?», «что за значки у меня в „Делах“?») — раздел
    руководства сразу в подсказку модели, без вызова app_help (экзамен 25.10: модель не спросила руководство и выдумала).
    Только уверенное попадание: два слова вопроса совпали с ключевыми словами или заголовком раздела. -> текст или ""."""
    q = [_stem(w) for w in _words(query) if len(w) > 2 and w not in STOP]
    best, top = 0, None
    for s in load():
        if where and where not in (s.get("where") or []):
            continue
        kw = _words(" ".join(s.get("keywords") or []) + " " + s.get("title", ""))
        k = sum(1 for w in set(q) if any(x.startswith(w) for x in kw))
        if k > best:
            best, top = k, s
    if best < 2 or top is None:
        return ""
    return ("Вопрос про само приложение — вот раздел руководства (отвечай по нему своими словами, коротко; не выдумывай "
            "того, чего тут нет):\n" + text(top))


# Экзамен ПК 0.81.1 (как appAsk на телефоне, экзамен 0.9.18): «как сделать, чтобы сын мог разговаривать с тобой безопасно?»,
# «есть у тебя видеоуроки?», «как добавить маму?», «как давать задания сотрудникам через Телеграм?» — модель не звала
# app_help и выдумывала («роликов со мной нет», «Рефералы», «заведите общий чат»). Вопрос о самом приложении — руководство
# прикладываем к вопросу сами (engine_answer), а «такого нет» без руководства — переспрос (quality.feature_deny).
APP_Q = re.compile(r"(?:как|где)\s+(?:мне\s+|нам\s+|у\s+тебя\s+|тут\s+|здесь\s+|это\s+|бы\s+|можно\s+)*(?:[а-яё]+\s+){0,2}?"
                   r"(?:сделать|добавить|настроить|включить|подключить|найти|взять|пригласить|вести|поменять|изменить|убрать|связать|"
                   r"открыть|посмотреть|позвать|завести|создать|сменить|выключить|давать|поручать|получить|переписываться)(?![а-яё])"
                   r"|есть\s+(?:ли\s+)?у\s+тебя|у\s+тебя\s+есть|(?:ты\s+)?умеешь\s+ли|так\s+можно|можно\s+ли\s+(?:у\s+тебя|тут|здесь|в\s+приложении)", re.I)
APP_ABOUT = re.compile(r"приложени|dewiar|девиар|дэвиар|у\s+тебя|с\s+тобой|ты\s+умеешь|помощник|близк|семь|бюджет|трат|урок|видео|"
                       r"курс[ыа]?(?![а-яё])|настройк|функци|раздел|кнопк|переписыва|пригласи|связать|устройств|компьютер|телефон|"
                       r"часы|виджет|персонаж|голос|сканер|радар|рядом|сотрудник|задани|поручени|телеграм|telegram|на\s+сайте|"
                       r"консультант|заявк|сын|дочь|дочк|ребён|ребен|детск|код", re.I)


def app_ask(query):
    """Вопрос о самом приложении («как …», «есть у тебя …», «так можно?» + про Dewiar)?"""
    q = str(query or "")
    return bool(APP_Q.search(q) and APP_ABOUT.search(q))


def attach(query, where=""):
    """Вопрос о приложении и в руководстве есть подходящее -> справка к вопросу (до двух разделов) или ""."""
    if not app_ask(query):
        return ""
    found = search(query, where)
    q = {(w, _stem(w)) for w in _words(query) if len(w) > 2 and w not in STOP}
    kw = _words(" ".join(found[0].get("keywords") or []) + " " + found[0].get("title", "")) if found else []
    # короткая основа («брат» → «бра») — только целым словом, иначе «браузер» отвечал бы на «у тебя есть брат?»
    if not found or not any(any(x == w or x == st or (len(st) >= 4 and x.startswith(st)) for x in kw) for w, st in q):
        return ""                                  # совпало только где-то в тексте — не уверены, что это про Dewiar
    return ("Из руководства Dewiar (вопрос о самом приложении — отвечай по нему, своими словами, с точными названиями разделов и "
            "кнопок; не говори «такого нет», если это есть здесь, и не выдумывай того, чего тут нет):\n"
            + "\n\n".join(text(s) for s in found))


def text(s):
    parts = [f"«{s['title']}» ({', '.join({'pc': 'компьютер', 'phone': 'телефон'}.get(w, w) for w in s.get('where') or [])})", s.get("lead", "")]
    parts += ["— " + h for h in s.get("how") or []]
    if s.get("say"):
        parts.append("Фразы: " + "; ".join(f"«{x}»" for x in s["say"][:6]))
    parts += ["Совет: " + t for t in (s.get("tips") or [])[:3]]
    parts.append(f"Подробнее: {URL}#{s['id']}")
    return "\n".join(p for p in parts if p)


def answer(query, where=""):
    found = search(query, where)
    if not found:
        return f"В руководстве такого нет. Не выдумывай кнопки и меню: скажи честно и предложи посмотреть руководство — {URL}"
    return "\n\n".join(text(s) for s in found) + "\n\nОтветь своими словами, коротко, с точными названиями разделов и кнопок; ссылку назови, если просят подробнее."
