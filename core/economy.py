"""Экономный режим (0.63; план «Идей Лиры»: «простые вопросы — недорогой модели, трудные — сильной: тот же ответ
дешевле»). Для своего ключа сервиса (OpenRouter, OpenAI, Claude, DeepSeek…): в профиле «Мозга» поле economy — модель того
же сервиса для простого. Простое — короткая разговорная реплика человека без поручений, картинок и вложений, не середина
цепочки действий и не «сложная просьба» (над ней модель думает). Остальное — основной модели; дешёвая не ответила — тот
же вопрос основной, человек не замечает. Облако Dewiar делит вопросы само (cloud.php, «лёгкий мозг»), ему поле не нужно.
То же правило — на телефоне (android/assets/www/app.js, econSimple); слова поручений — как LITE_HARD в cloud.php."""
import re

HARD = re.compile(
    r"(?:включи|выключи|поставь|напомни|напоминай|открой|запусти|закрой|позвони|набери|отправь|пошли|напиши|найди|поищи|ищи|покажи|"
    r"сделай|создай|удали|запиши|запомни|добавь|перенеси|скачай|сохрани|распечатай|переведи|перевод|сочини|составь|придумай|нарисуй|схем|"
    r"посчитай|рассчитай|вычисли|реши|задач|код|программ|скрипт|сайт|приложен|таблиц|документ|файл|папк|письм|отчёт|отчет|презентац|"
    r"резюме|стать|эсс|стих|рассказ|сказк|объясни|почему|зачем|сравни|анализ|разбер|план|подробн|детальн|по шагам|пошагов|исследу|"
    r"интернет|новост|погод|курс|цен|сколько стоит|фото|камер|экран|скриншот|музык|песн|радио|видео|ютуб|youtube|почт|календар|"
    r"задани|сводк|купи|закаж|заказ|оплат|счёт|счет|баланс|умн\w* дом|свет|розетк|термостат|https?:|www\.|\.ru|\.com)", re.I)

# недорогие модели известных сервисов — подсказка в студии и на телефоне (первое совпадение со списком сервиса)
CHEAP = ("gpt-4.1-nano", "gpt-4o-mini", "gpt-4.1-mini", "gpt-5-nano", "gpt-5-mini", "claude-haiku", "claude-3-5-haiku", "claude-3-haiku",
         "gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash", "deepseek-chat",
         "mistral-small", "ministral", "llama-3.1-8b", "qwen3-8b", "qwen3-4b", "qwen2.5-7b", "qwen-turbo", "yandexgpt-lite", "gigachat-lite")


def simple(text, history=(), images=False):
    """Простая ли реплика для дешёвой модели."""
    t = str(text or "")
    if images or "\n\nВложения:" in t:
        return False
    t = t.strip()
    for m in list(history or [])[-4:]:                  # только что были действия — идёт работа, не болтовня
        if m.get("role") == "tool" or m.get("tool_calls") or m.get("acts"):
            return False
    return bool(t) and len(t) <= 160 and len(t.split()) <= 25 and not HARD.search(t)


def model_for(prof, text, history=(), images=False, think=False):
    """-> дешёвая модель для этого вопроса или "" (выключено, облако, сложное, та же модель)."""
    cheap = str((prof or {}).get("economy") or "").strip()
    if not cheap or (prof or {}).get("cloud") or think or cheap == (prof or {}).get("model"):
        return ""
    return cheap if simple(text, history, images) else ""


# не нашлась известная — по примете в имени: mini, nano, haiku, flash, lite, small, 7–9b
CHEAP_RX = re.compile(r"(?:^|[-_/:.])(?:mini|nano|haiku|flash|lite|small|turbo|[789]b)(?:$|[-_/:.])", re.I)
SIDE_RX = re.compile(r"embed|rerank|vision|whisper|tts|audio|image|guard|moderat", re.I)


def suggest(models, current=""):
    """Из списка моделей сервиса -> недорогая для простых вопросов или "" (не нашлась)."""
    ms = [m for m in (models or []) if m and m != current and not SIDE_RX.search(m)]
    for c in CHEAP:
        for m in ms:
            if c in m.lower():
                return m
    return next((m for m in ms if CHEAP_RX.search(m)), "")
