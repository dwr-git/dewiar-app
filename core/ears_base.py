"""Слух — основа (чистое ядро 1.0.16 — docs/CORE_PLAN.md): пороги перебивания и сбоев микрофона, помощники
(barge_floor, rest_after, stop_mid_phrase). Слух и голос — core/engine_audio.py (AudioMixin), его части — ears_*.py;
прежние имена engine_audio.X на месте. Подменять в проверках — здесь (ears_base.list_devices): части читают через основу."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка

VOSK_RETRY_MIN = float(os.environ.get("DEWIAR_VOSK_RETRY_MIN") or 30)   # голоса Vosk не скачались — повтор через столько минут


# сбои открытия микрофона, которые значат «его нет или он отключён» (а не поломку): ждём и переподключаемся без отчёта
# о сбое. MME 2 «device ID out of range», MME 1 «Undefined external error», -9986 — отчёты 21.10
NO_MIC_ERR = ("device -1", "No Default Input", "Invalid device", "out of range for your system", "Undefined external error",
              "PaErrorCode -9986", "PaErrorCode -9999")


BARGE_LOUD = 1.8           # №543: без настоящего AEC перебить речью — во столько раз громче, чем микрофон слышит мой голос


def barge_floor(levels, recent=30):
    """№543 (04.11, Windows без эхоподавления, включено «Я в наушниках», а звук — в колонки MacBook): ответ «перебивал»
    сам себя — эхо в микрофоне проходило как речь человека. levels — громкость микрофона по кадрам, пока ассистент
    говорит; последние recent кадров (≈1 с) — возможно, уже голос человека — в основу не берём. Порог — BARGE_LOUD ×
    медиана. В наушниках микрофон пока молчит — порог низкий; в колонках эхо громкое — перебить можно только громче его
    или именем. Первые полторы секунды ответа данных мало — тогда по всему, что есть (строже), а без данных — нельзя."""
    lv = sorted(levels[:-recent] if len(levels) >= recent + 20 else levels)
    if len(lv) < 10:
        return float("inf")
    return BARGE_LOUD * float(lv[len(lv) // 2])


def rest_after(full, spoken):
    """Что из ответа full ещё не прозвучало: всё после последней целиком сказанной фразы (spoken — фразы по порядку).
    Фраза, на которой перебили, в spoken не попала — её повторим целиком. Не нашли сказанное — весь ответ."""
    pos = 0
    for s_ in spoken:
        s_ = (s_ or "").strip()
        i = full.find(s_, pos) if s_ else -1
        if i < 0:
            return full[pos:].strip() if pos else full
        pos = i + len(s_)
    return full[pos:].strip()


LONG_WAKE_S = 6.0            # №717: имя посреди сплошной речи дольше — сначала проверка точной моделью (видео, разговор рядом)


def stop_mid_phrase(in_speech, utt_s):
    """Слово-стоп от быстрого слуха посреди длинной фразы (дольше 1,5 с) — не команда: «схватит» ≈ «хватит» (№404)."""
    return bool(in_speech) and utt_s > 1.5
