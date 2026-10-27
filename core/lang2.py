"""Второй язык — английский, первая ступень (28.10; владелец: «сделать Лиру многоязычной, хотя бы английский»;
отчёты №365 — «Патрик не понимает английскую речь», №367 — «немецкий голосом — коряво»).

Слух («Слух» → «Понимать английскую речь», stt.english): главный распознаватель (GigaAM) — только русский, английскую
фразу он пишет русскими буквами («вотс зе уэзер»). Поэтому каждую фразу слушают ещё две маленькие модели Vosk —
русская (модель имён, она уже есть) и английская (vosk-model-small-en-us, ~40 МБ, скачивается один раз при включении).
У каждой — уверенность в словах; английская заметно увереннее — фраза английская, и текст берём у неё. Имя в начале
(«Патрик, what's the weather») — из русского текста: имена персонажей русские.

Ответ: вопрос по-английски — модель отвечает по-английски (en_hint к вопросу), голос — английский (tts.split_lang;
немецкие обороты — немецким голосом Piper)."""

import json
import logging
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.lang2")

EN_MODEL = "vosk-model-small-en-us-0.15"
EN_URLS = ["https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"]

# английский текст: латиница, без кириллицы, и хотя бы одно частое английское слово (или три слова латиницей)
_EN_COMMON = set("""the a an is are was were be been am i you he she it we they me my your his her our their what what's whats
how why when where who which can could would should will do does did don't dont not no yes please thanks thank hello hi hey
tell me about this that these those there here and or but with for from to of in on at by is it's its let's lets
weather time today tomorrow good morning evening night play music turn set remind reminder call open stop""".split())
_LAT = re.compile(r"[A-Za-z][A-Za-z'’]*")
_CYR = re.compile(r"[А-Яа-яЁё]")


def is_english(text):
    """Фраза написана по-английски: нет кириллицы, есть английские слова (частые или хотя бы три слова латиницей)."""
    t = str(text or "")
    if not t.strip() or _CYR.search(t):
        return False
    words = [w.lower().replace("’", "'") for w in _LAT.findall(t)]
    if not words:
        return False
    common = sum(1 for w in words if w in _EN_COMMON)
    return common >= 1 and len(words) >= 2 or len(words) >= 3


EN_HINT = ("Собеседник говорит по-английски — ответь по-английски, простым разговорным языком (если он сам не просит "
           "по-русски).")


def en_hint(text):
    """Подсказка к вопросу: спросили по-английски — отвечать по-английски. Иначе ""."""
    return EN_HINT if is_english(text) else ""


def decide(en, ru, margin=0.08, floor=0.72):
    """Чья фраза: en, ru — (средняя уверенность, число слов) у английской и русской моделей Vosk. -> "en" | "ru".
    Английская должна быть увереннее русской на margin и не ниже floor; одно слово — только очень уверенно."""
    (ec, en_n), (rc, ru_n) = en, ru
    if en_n == 0:
        return "ru"
    if en_n == 1:
        return "en" if ec >= 0.93 and ec > rc + 0.2 else "ru"
    return "en" if ec >= floor and ec > rc + margin else "ru"


def _vosk(model, pcm):
    """(текст, средняя уверенность, число слов) у модели Vosk."""
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(model, 16000)
    rec.SetWords(True)
    rec.AcceptWaveform(pcm)
    r = json.loads(rec.FinalResult())
    ws = [w.get("conf", 0.0) for w in (r.get("result") or [])]
    return r.get("text", ""), (sum(ws) / len(ws) if ws else 0.0), len(ws)


_LAT_OF = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
                         "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
                         "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
                         "э": "e", "ю": "yu", "я": "ya"})


def strip_name(en_text, names):
    """«patrick what's the weather» → «what's the weather»: английская модель тоже слышит имя — латиницей и с ошибками.
    names — имена (кириллицей); первое слово похоже на имя латиницей (≥ 0,6) — убираем."""
    import difflib
    words = (en_text or "").split()
    if not words:
        return ""
    lat = [n.lower().translate(_LAT_OF) for n in names if n]
    w0 = words[0].lower()
    if any(difflib.SequenceMatcher(None, w0, n).ratio() >= 0.6 for n in lat):
        return " ".join(words[1:])
    return en_text


class English:
    """Английская модель Vosk: скачать в фоне, загрузить, решить «чья фраза»."""

    def __init__(self, models_dir, data_dir):
        self.models_dir, self.data_dir = Path(models_dir), Path(data_dir)
        self.model = None
        self.loading = False
        self.error = ""
        self._retry_at = 0.0

    @property
    def ready(self):
        return self.model is not None

    def installed(self):
        from listen import vosk_complete
        return vosk_complete(self.models_dir / EN_MODEL)

    def can_start(self):
        """Можно начинать скачивание: модели нет, не качается и не ждём повтора."""
        return self.model is None and not self.loading and time.monotonic() >= self._retry_at

    def ensure(self, on_status=None, mirror=None, mirror_sha=None):
        """Скачать (один раз) и загрузить в фоне. Не скачалось — повтор через 30 минут."""
        if not self.can_start():
            return
        self.loading = True

        def run():
            try:
                from listen import ensure_model, kaldi_path
                d = ensure_model(EN_MODEL, EN_URLS, mirror_sha, self.data_dir, self.models_dir,
                                 on_status=on_status, mirror=mirror, label="английской речи (40 МБ, один раз)")
                from vosk import Model
                self.model = Model(str(kaldi_path(d)))
                self.error = ""
                log.info("🌐 Английская речь: модель %s готова", EN_MODEL)
                if on_status:
                    on_status("")
            except Exception as e:  # noqa: BLE001
                self.error = str(e)
                self._retry_at = time.monotonic() + 1800
                log.warning("🌐 Модель английской речи не загрузилась: %s", e)
                if on_status:
                    on_status("Модель английской речи не скачалась — попробую позже. Русскую речь слышу как обычно.")
            finally:
                self.loading = False
        threading.Thread(target=run, name="lang2-en", daemon=True).start()

    def pick(self, pcm, ru_model):
        """-> ("en", текст, оценки) | ("ru", "", оценки). Без модели — ("ru", "", None)."""
        if self.model is None or ru_model is None or not pcm:
            return "ru", "", None
        head = pcm[:16000 * 2 * 30]                        # решаем по первым 30 секундам
        et, ec, en_n = _vosk(self.model, head)
        if not en_n:
            return "ru", "", ((0.0, 0), (0.0, 0))
        _rt, rc, ru_n = _vosk(ru_model, head)
        sc = ((round(ec, 2), en_n), (round(rc, 2), ru_n))
        if decide((ec, en_n), (rc, ru_n)) != "en":
            return "ru", "", sc
        return "en", (et if len(head) == len(pcm) else self.transcribe(pcm)), sc

    def transcribe(self, pcm):
        """Целиком английской моделью (для длинной диктовки, когда первые 30 с — английские)."""
        return _vosk(self.model, pcm)[0] if self.model is not None else ""
