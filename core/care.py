"""«Заботливая память» (0.61; план «Лира — любимица всех»: «сама вспоминает, что вам важно — „как прошёл врач?“»).

Человек между делом говорит о предстоящем важном для него событии: «завтра иду к врачу», «в пятницу собеседование»,
«мама приезжает в субботу», «сдаю экзамен 3 ноября». Лира запоминает это с датой (STATE_DIR/care.json), а когда событие
прошло — один раз, тепло и к месту спрашивает: «Как прошёл приём у врача?» — в приветствии, когда человек вернулся
к компьютеру (presence), или в конце ближайшего ответа. Спросила — больше не спрашивает; старше 5 дней — забывает.

Только о самом человеке (я, у меня, мы, мама…), только будущие даты; без модели — по словам и календарю (when.py).
Список виден и правится в студии («Обо мне» → «Лира спросит потом»); выключить — care.on = false."""
import datetime as dt
import hashlib
import json
import re
import threading
from pathlib import Path

EVENT_RX = re.compile(
    r"(?<![а-яё])(?:врач\w*|доктор\w*|стоматолог\w*|зубн\w+|терапевт\w*|больниц\w*|поликлиник\w*|анализ\w*|обследовани\w*|"
    r"операци\w*|узи|мрт|приём\w*|прием\w*|собеседовани\w*|интервью|экзамен\w*|зач[её]т\w*|сесси\w*|защит\w*|диплом\w*|"
    r"выступлени\w*|доклад\w*|презентаци\w*|концерт\w*|соревновани\w*|турнир\w*|матч\w*|переезд\w*|свадьб\w*|"
    r"день рождени\w*|юбиле\w*|поездк\w*|отпуск\w*|командировк\w*|лечу|улетаю|уезжаю|еду|поеду|поезд\w*|самол[её]т\w*|рейс\w*|"
    r"приезжа\w*|прилета\w*|в гости|свидани\w*|сдаю|сдать|суд\w*|нотариус\w*|первый рабочий|выхожу на работу|роды|рожать)"
    r"(?![а-яё])", re.I)
ABOUT_ME = re.compile(r"(?<![а-яё])(?:я|у меня|у нас|мне|нам|мы|мой|моя|моё|мое|мои|моего|моей|моему|наш\w*|мам\w*|пап\w*|"
                      r"сын\w*|доч\w*|муж\w*|жен\w*|бабушк\w*|дедушк\w*|брат\w*|сестр\w*|ребён\w*|ребен\w*|"
                      r"иду|пойду|еду|поеду|лечу|полечу|улетаю|уезжаю|сдаю|выступаю|записал\w*|переезжаем|женюсь|выхожу)(?![а-яё])", re.I)
NOT_EVENT = re.compile(r"(?<![а-яё])(?:напомни|поставь|будильник|запиши в календарь|таймер|какая погода|погода)(?![а-яё])", re.I)
KEEP_DAYS = 5


def _id(what, day):
    return hashlib.sha1(f"{what.lower()}|{day}".encode()).hexdigest()[:10]


def detect(text, now=None):
    """Фраза человека -> {"what", "day"} (событие в будущем о нём самом) или None."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(t) < 8 or len(t) > 400 or t.endswith("?") or NOT_EVENT.search(t):
        return None
    if not EVENT_RX.search(t) or not ABOUT_ME.search(t):
        return None
    from capture import plan_day
    now = now or dt.datetime.now()
    day = plan_day(t, now)
    if not day:
        return None
    what = re.sub(r"^(?:слушай|кстати|знаешь|а|ну|вот|лира|патрик)[,\s]+", "", t, flags=re.I).rstrip(".!… ")
    return {"what": what[:160], "day": day}


def when_word(day, today):
    d = (today - day).days
    return "сегодня" if d == 0 else "вчера" if d == 1 else "позавчера" if d == 2 else f"{d} дня назад" if d < 5 else f"{d} дней назад"


class Care:
    def __init__(self, path, now=dt.datetime.now):
        self.path = Path(path)
        self.now = now
        self._lock = threading.Lock()
        try:
            self.items = json.loads(self.path.read_text(encoding="utf-8")).get("items") or []
        except (OSError, ValueError, AttributeError):
            self.items = []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"items": self.items[-60:]}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    def note(self, text):
        """Сказанное человеком: событие — запомнить (один раз). -> запись или None."""
        e = detect(text, self.now())
        if not e:
            return None
        iid = _id(e["what"], e["day"])
        with self._lock:
            if any(x["id"] == iid or (x["day"] == e["day"].isoformat() and x["what"].lower() == e["what"].lower()) for x in self.items):
                return None
            it = {"id": iid, "what": e["what"], "day": e["day"].isoformat(), "said": self.now().isoformat(timespec="minutes"), "asked": ""}
            self.items.append(it)
        self._save()
        return it

    def due(self):
        """Прошедшие события, о которых ещё не спросили: вчера и раньше (до 5 дней), или сегодня — с 18:00."""
        now = self.now()
        today = now.date()
        out = []
        for x in self.items:
            if x.get("asked"):
                continue
            day = dt.date.fromisoformat(x["day"])
            if (today - day).days > KEEP_DAYS:
                continue
            if day < today or (day == today and now.hour >= 18):
                out.append(x)
        return out

    def mark(self, ids):
        with self._lock:
            for x in self.items:
                if x["id"] in ids:
                    x["asked"] = self.now().isoformat(timespec="minutes")
            cut = (self.now().date() - dt.timedelta(days=30)).isoformat()
            self.items = [x for x in self.items if x["day"] >= cut]
        self._save()

    def remove(self, iid):
        with self._lock:
            self.items = [x for x in self.items if x["id"] != iid]
        self._save()

    def public(self):
        today = self.now().date()
        return [dict(x, ago=when_word(dt.date.fromisoformat(x["day"]), today) if dt.date.fromisoformat(x["day"]) <= today else "")
                for x in sorted(self.items, key=lambda x: x["day"]) if not x.get("asked")]

    def context(self):
        """Строка для подсказки модели (одно событие за раз) и его id -> (текст, [id]) или ("", [])."""
        due = self.due()
        if not due:
            return "", []
        x = due[0]
        word = when_word(dt.date.fromisoformat(x["day"]), self.now().date())
        return (f"[Заботливая память] Пользователь заранее говорил: «{x['what']}» — это было {word}. Если к месту, в конце ответа "
                "одной тёплой фразой спроси, как прошло (без нравоучений и без списка). Если он сам уже рассказал — не спрашивай.",
                [x["id"]])
