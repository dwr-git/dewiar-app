"""ИИ-правка в блокноте (24.10, владелец: «выделяю фрагмент, правой клавишей — и там „перевести“, „переформулировать“,
„проверить орфографию“, „написать текст на тему…“, „упростить“, „саммари“, „структурировать“, „красиво отформатировать“,
„показать в виде mermaid-диаграммы“… переформулируется выделенное с учётом содержимого всей вкладки… некоторые функции
больше подходят для всей страницы, а некоторые — для выделенного»).

Страница (ui/padai.js) шлёт pad_ai {act, text, doc, lang, ask, scope}: text — что править (выделенное или вся вкладка),
doc — вся вкладка для контекста. Ответ модели (тот же «мозг», что у ассистента) идёт событиями pad_ai {id, text, done,
error} по мере написания; заменяет текст только человек — кнопкой «Заменить» (и Ctrl+Z после неё работает)."""
import logging
import re
import threading
import time

log = logging.getLogger("dewiar.padai")

DOC_MAX = 24_000           # вкладка для контекста — не больше (≈ 8 тыс. токенов); длиннее — середину опускаем
TEXT_MAX = 16_000          # сам текст на правку: больше — просим выделить часть

LANGS = {"en": "английский", "ru": "русский", "de": "немецкий", "fr": "французский", "es": "испанский", "it": "итальянский",
         "zh": "китайский (упрощённые иероглифы)", "ja": "японский", "uk": "украинский", "be": "белорусский", "tr": "турецкий",
         "pt": "португальский", "pl": "польский", "kk": "казахский", "ar": "арабский"}

# действие -> (что сделать, температура, на выделенном / на всей вкладке)
ACTS = {
    "rephrase": ("Перепиши фрагмент другими словами: тот же смысл, факты, имена и термины, естественный живой язык. "
                 "Длина — примерно та же.", 0.6),
    "simplify": ("Упрости фрагмент: короткие фразы, простые слова, без канцелярита; смысл и все факты — сохранить.", 0.4),
    "shorter": ("Сократи фрагмент примерно вдвое: оставь главное, убери воду и повторы; факты и цифры не теряй.", 0.3),
    "longer": ("Раскрой фрагмент подробнее: поясни, добавь уместные детали и примеры, опираясь на остальной документ; "
               "ничего не выдумывай про факты, которых нет.", 0.6),
    "fix": ("Исправь орфографию, пунктуацию, опечатки и явные грамматические ошибки. Больше НИЧЕГО не меняй: ни слова, "
            "ни порядок, ни стиль, ни разметку. Если ошибок нет — верни текст как есть.", 0.1),
    "retell": ("Перескажи фрагмент своими словами — связно и понятно, как объяснил бы умный друг; без потери смысла.", 0.6),
    "translate": ("Переведи на {lang}. Естественно, как написал бы носитель языка; сохрани разметку Markdown, имена, "
                  "ссылки, числа и код. Ничего не добавляй от себя.", 0.2),
    "ask": ("Сделай с фрагментом вот что: {ask}", 0.6),
    "structure": ("Структурируй документ: логичные заголовки (## ...), короткие абзацы, списки там, где перечисления, "
                  "задачи — пунктами «- [ ]». Сохрани ВЕСЬ смысл и все факты, ссылки и картинки (строки ![...](...)) "
                  "на своих местах; ничего не выдумывай и не удаляй содержательного.", 0.3),
    "beautify": ("Красиво оформи документ в Markdown: заголовок, подзаголовки, выделение главного **жирным**, списки, "
                 "таблица там, где данные просятся в таблицу, цитата для важной мысли, черта --- между крупными "
                 "частями. Текст по смыслу не меняй, ссылки и картинки сохрани.", 0.3),
    "summary": ("Напиши краткое содержание документа: одна фраза — о чём он, затем 3–7 пунктов с главным (цифры, "
                "решения, сроки, кто что делает). Начни строкой «## Кратко».", 0.3),
    "diagram": ("Нарисуй по тексту схему Mermaid, которая лучше всего его показывает: flowchart для шагов и связей, "
                "sequenceDiagram для общения сторон, mindmap для идей, timeline для дат, gantt для плана. Подписи — "
                "по-русски, коротко; узлы с пробелами — в кавычках. Верни ТОЛЬКО блок ```mermaid … ``` без пояснений.", 0.2),
    "write": ("Напиши текст на тему: {ask}. Опирайся на документ, если он по теме; пиши живо, по делу, с заголовком "
              "и абзацами в Markdown. Длина — по теме, обычно 150–400 слов.", 0.7),
    "continue": ("Продолжи документ с того места, где он обрывается: тем же стилем и голосом, 1–3 абзаца. Верни только "
                 "продолжение, без повтора уже написанного.", 0.7),
}
WHOLE = {"structure", "beautify", "summary", "diagram", "write", "continue"}

SYSTEM = ("Ты — редактор текста в блокноте пользователя. Отвечай ТОЛЬКО готовым результатом в Markdown — без вступлений "
          "(«Вот…», «Конечно…»), без пояснений, без кавычек вокруг и без ```markdown```-обёртки. Язык результата — язык "
          "исходного текста, если не просили перевод. Разметку (заголовки, списки, ссылки, картинки) сохраняй.")

_PREAMBLE = re.compile(r"^\s*(?:вот|конечно|хорошо|готово|ниже|here is|here's|sure)[^\n]{0,80}:\s*\n+", re.I)
_FENCE = re.compile(r"^\s*```(?:markdown|md|text)?\s*\n([\s\S]*?)\n```\s*$", re.I)


def clean(act, text):
    """Ответ модели -> чистый Markdown: без «Вот переформулированный текст:» и обёртки ```markdown."""
    t = (text or "").strip()
    t = _PREAMBLE.sub("", t, count=1)
    m = _FENCE.match(t)
    if m and act != "diagram":
        t = m.group(1).strip()
    if act == "diagram":
        if "```mermaid" not in t:
            m2 = re.search(r"```\w*\s*\n([\s\S]*?)\n```", t)
            body = (m2.group(1) if m2 else t).strip()
            t = "```mermaid\n" + body + "\n```"
        else:
            t = t[t.index("```mermaid"):]
            end = t.find("```", 10)
            t = t[:end + 3] if end > 0 else t + "\n```"
    return t.strip()


def _doc_ctx(doc):
    doc = doc or ""
    if len(doc) <= DOC_MAX:
        return doc
    half = DOC_MAX // 2
    return doc[:half] + "\n\n[…середина документа опущена…]\n\n" + doc[-half:]


def prompt(act, text, doc="", lang="en", ask="", scope="sel"):
    """-> (system, user, temperature, max_tokens). ValueError — нечего делать / слишком много."""
    if act not in ACTS:
        raise ValueError("неизвестное действие")
    what, temp = ACTS[act]
    text, doc, ask = str(text or "").strip(), str(doc or ""), str(ask or "").strip()[:500]
    if act in ("ask", "write") and not ask:
        raise ValueError("напишите, что сделать")
    if act not in ("write",) and not text:
        raise ValueError("выделите текст или напишите что-нибудь во вкладке")
    if len(text) > TEXT_MAX:
        raise ValueError("слишком много текста за раз — выделите часть (до 16 тысяч знаков)")
    what = what.format(lang=LANGS.get(lang, lang or "английский"), ask=ask)
    whole = scope == "doc" or act in WHOLE
    parts = []
    if act in ("write", "continue"):
        parts.append(f"ЗАДАЧА: {what}")
        if doc.strip():
            parts.append("ДОКУМЕНТ:\n" + _doc_ctx(doc))
    elif whole:
        parts.append(f"ЗАДАЧА: {what}\n\nДОКУМЕНТ:\n{text}")
    else:
        if doc.strip() and doc.strip() != text:
            parts.append("ВЕСЬ ДОКУМЕНТ (только для контекста — его НЕ переписывай):\n" + _doc_ctx(doc))
        parts.append(f"ЗАДАЧА: {what}\nВерни только новый вариант ФРАГМЕНТА — он встанет на место выделенного.\n\nФРАГМЕНТ:\n{text}")
    n = len(text) if act not in ("write", "continue") else 1200
    mult = {"summary": 0.4, "shorter": 0.7, "diagram": 0.5, "longer": 2.2, "write": 1.5, "continue": 1.0}.get(act, 1.3)
    max_tokens = int(min(6000, max(500, n / 2.5 * mult + 300)))
    return SYSTEM, "\n\n".join(parts), temp, max_tokens


class PadAI:
    """Один запрос за раз на блокнот: новый — останавливает прежний."""

    def __init__(self, eng):
        self.eng = eng
        self._cur = None          # (id, cancel Event)
        self._n = 0
        self._lock = threading.Lock()

    def start(self, a):
        prof = self.eng.s.active_llm()
        if not prof:
            raise ValueError("мозг не подключён — студия → «Мозг»")
        system, user, temp, mx = prompt(a.get("act", ""), a.get("text", ""), a.get("doc", ""), a.get("lang", "en"),
                                        a.get("ask", ""), a.get("scope", "sel"))
        with self._lock:
            if self._cur:
                self._cur[1].set()
            self._n += 1
            rid, cancel = f"ai{self._n}", threading.Event()
            self._cur = (rid, cancel)
        prof = dict(prof, temperature=temp, max_tokens=mx)
        threading.Thread(target=self._run, args=(rid, cancel, a.get("act", ""), prof, system, user), name="padai", daemon=True).start()
        return {"id": rid}

    def stop(self, rid=""):
        with self._lock:
            if self._cur and (not rid or self._cur[0] == rid):
                self._cur[1].set()
                self._cur = None
        return {"ok": True}

    def _run(self, rid, cancel, act, prof, system, user):
        from llm import LLMError, stream_events
        text, last, t0 = "", 0.0, time.monotonic()
        emit = lambda **kw: self.eng.emit("pad_ai", id=rid, **kw)   # noqa: E731
        try:
            for kind, val in stream_events(prof, system, [{"role": "user", "content": user}], cancel=cancel, tools=None):
                if cancel.is_set():
                    return
                if kind != "text":
                    continue
                text += val
                if time.monotonic() - last > 0.12:
                    emit(text=clean(act, text) if act != "diagram" else text, done=False)
                    last = time.monotonic()
        except LLMError as e:
            if not cancel.is_set():
                emit(text="", done=True, error=str(e)[:300])
            return
        except Exception as e:  # noqa: BLE001
            log.warning("ИИ-правка: %s", e)
            if not cancel.is_set():
                emit(text="", done=True, error="не получилось — попробуйте ещё раз")
            return
        if cancel.is_set():
            return
        out = clean(act, text)
        log.info("✨ Блокнот: «%s» за %.1f с, %d знаков", act, time.monotonic() - t0, len(out))
        emit(text=out, done=True, error="" if out else "модель ничего не ответила — попробуйте ещё раз")
        with self._lock:
            if self._cur and self._cur[0] == rid:
                self._cur = None
