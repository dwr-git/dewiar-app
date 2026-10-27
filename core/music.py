"""Музыка голосом: свой список радиостанций (radio.json на сайте Dewiar — его правит администратор) и разбор фраз
«включи музыку», «поставь джаз», «что-нибудь спокойное», «дальше», «выключи музыку» — без языковой модели.

Список (Catalog): сразу — копия на диске или встроенный data/radio.json, а свежий с сайта (адрес из настроек, иначе
DEFAULT_URL) подтягивается в фоне, не чаще раза в 6 часов; неудача не мешает играть. Формат (общий с сайтом):
    {"genres": ["поп", "рок", …], "stations": [{"name", "url", "tags": "жанры через пробел", "aliases": [...]}, …]}
(можно и просто список станций). Не нашли в своём списке — играет каталог radio-browser (radio.search).
Ещё здесь: control() — кнопки уже открытого плеера, genre_tag() — жанр для каталога, «… в Яндекс Музыке»."""
import json
import logging
import random
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.music")
DEFAULT_URL = "https://dewiar.pro/dwrapp/radio.json"
REFRESH = 6 * 3600

# Как люди называют настроение и жанр (начало слова) → слова из тегов станций в radio.json
SYN = {
    "спокойн": "релакс спокойно", "расслаб": "релакс", "отдох": "релакс", "чилаут": "релакс", "чил": "релакс",
    "тих": "релакс спокойно", "сон": "релакс", "медитац": "релакс", "фонов": "релакс джаз",
    "танц": "танцевальная клубная", "клуб": "клубная", "бодр": "энерджи танцевальная", "энерг": "энерджи",
    "драйв": "рок энерджи", "весел": "поп хиты", "попс": "поп", "хит": "хиты поп",
    "русск": "русское русские", "наш": "русское русские", "отечеств": "русское русские",
    "стар": "ретро", "ретро": "ретро", "80": "ретро 80", "90": "ретро 90", "восьмидесят": "ретро 80",
    "девяност": "ретро 90", "диско": "ретро", "советск": "ссср ретро", "ссср": "ссср",
    "хаус": "дип хаус", "электрон": "клубная дип", "дип": "дип", "ремикс": "ремиксы",
    "новост": "новости", "поговор": "разговорное", "разговор": "разговорное", "ток": "разговорное",
    "джаз": "джаз", "блюз": "джаз", "рок": "рок", "альтернатив": "альтернатива", "метал": "рок",
    "поп": "поп", "класси": "классика", "шансон": "шансон",
    "легк": "релакс спокойно поп", "приятн": "релакс спокойно", "вечер": "релакс джаз спокойно", "медлен": "релакс спокойно",
    "романт": "релакс джаз", "инструмент": "джаз эмбиент классика", "утр": "поп хиты", "бодрящ": "энерджи танцевальная",
}
# FILLER — слова, которые не говорят, что играть: их выбрасываем из запроса перед поиском по жанрам
VERBS = r"(?:включи(?:те)?|поставь(?:те)?|запусти(?:те)?|врубай|вруби|давай|хочу|можно|сыграй|играй|поиграй)"
FILLER = {"мне", "нам", "пожалуйста", "немного", "немножко", "какую", "какую-нибудь", "какую-то", "что-нибудь",
          "что-то", "нибудь", "музыку", "музыка", "музыки", "музычку", "песни", "песню", "радио", "радиостанцию",
          "станцию", "волну", "послушать", "для", "под", "в", "стиле", "жанре", "жанр", "из", "типа", "вроде",
          "что", "бы", "лучше", "а", "и", "тогда", "можно", "давай", "хочу", "включи", "поставь", "запусти", "эфир"}
ASK_RX = re.compile(rf"^(?:{VERBS}\s+)?(?:мне\s+)?(?:какую-нибудь\s+|какую-то\s+|немного\s+)?(?:музыку|музычку|радио|"
                    rf"что-нибудь\s+послушать|музыка)(?:\s+пожалуйста)?$")
PLAY_RX = re.compile(rf"^{VERBS}\s+(.+)$|^(?:музыку|радио)\s+(.+)$")
NEXT_RX = re.compile(r"^(?:(?:а|ну|давай|включи|поставь|можно|еще)\s+)*"
                     r"(?:дальше|следующ\w*|другую|другое|другая|переключи(?:сь)?(?:\s+на\s+(?:следующ\w*|друг\w*))?|"
                     r"смени|поменяй|не нравится|не то|некст)"
                     r"(?:\s+(?:станци\w*|радио|песн\w*|музык\w*|трек|волн\w*))?(?:\s+(?:пожалуйста|давай))*$")
# №315 (пакет 27.10): «выключить радио», «выключи, пожалуйста, радио», «выключи это радио» — модель вместо этого включала
# новую станцию и уверяла, что выключила; теперь без модели
STOP_RX = re.compile(r"^(?:(?:ну|да|давай|а)\s+)?(?:выключи(?:ть|те)?|останови(?:ть|те)?|убери|отключи(?:ть|те)?|заглуши|хватит|выруби(?:ть)?|прекрати)"
                     r"(?:\s+(?:пожалуйста|уже|это|эту|мне|нам|наконец))*\s+(?:музыку|радио|музычку|музыка|станцию|эфир)(?:\s+(?:пожалуйста|уже))*$")
# Где играть: «… в Яндекс Музыке» / «открой Яндекс Музыку»
YANDEX_RX = re.compile(r"\s*\b(?:(?:в|на|через|из)\s+)?(?:приложени\w+\s+)?яндекс[\s-]*музык\w*\b\s*")
APP_RX = re.compile(r"^(?:открой|включи|запусти|вруби)\s+(?:приложение\s+)?яндекс[\s-]*музык\w*(?:\s+пожалуйста)?$")
# Кнопки уже открытого плеера (Яндекс Музыка, браузер): узнаём без модели и без поиска кнопки на экране
# (что с ними делать — engine_music.py, _player_cmd)
_BTN = r"(?:нажми|жми|ткни|кликни)\s+(?:на\s+)?(?:кнопку\s+)?"
CONTROL = [
    (re.compile(rf"^(?:{_BTN})?(?:play|плей|плэй|играть|воспроизведени\w*|проигрывани\w*|старт)$|^(?:играй|воспроизведи|поехали)"
                r"(?:\s+(?:музыку|трек|песню|пожалуйста))?$|^(?:запусти|включи|начни)\s+(?:воспроизведение|проигрывание)$|"
                r"^продолжи\s+(?:музыку|воспроизведение|играть|трек)$|^сними\s+с\s+паузы$"), "play"),
    (re.compile(rf"^(?:{_BTN})?паузу?$|^поставь\s+(?:музыку\s+|трек\s+)?на\s+паузу$|^приостанови(?:\s+музыку)?$"), "pause"),
    (re.compile(r"^(?:следующ\w+\s+(?:трек|песн\w+|композици\w+)|переключи\s+(?:трек|песню)|другой\s+трек|другую\s+песню|"
                r"следующ\w+|некст|дальше)(?:\s+пожалуйста)?$"), "next"),
    (re.compile(r"^(?:предыдущ\w+(?:\s+(?:трек|песн\w+))?|верни\s+(?:предыдущ\w+|прошл\w+)\s+(?:трек|песню)|прошл\w+\s+(?:трек|песню)|"
                r"назад\s+трек)(?:\s+пожалуйста)?$"), "previous"),
]
# Жанр по-русски → тег каталога радио (radio-browser): «включи электронную музыку» сразу играет, без браузера
GENRE_EN = {"электрон": "electronic", "техно": "techno", "хаус": "house", "транс": "trance", "рок": "rock", "джаз": "jazz",
            "класси": "classical", "поп": "pop", "хип": "hiphop", "рэп": "rap", "реп": "rap", "лаунж": "lounge", "чилаут": "chillout",
            "чил": "chillout", "амбиент": "ambient", "эмбиент": "ambient", "метал": "metal", "блюз": "blues", "кантри": "country",
            "регги": "reggae", "диско": "disco", "шансон": "chanson", "лоуфай": "lofi", "лофай": "lofi", "фолк": "folk", "соул": "soul",
            "фанк": "funk", "дабстеп": "dubstep", "драм": "drum and bass", "инди": "indie", "панк": "punk", "ретро": "oldies",
            "релакс": "relax", "спокойн": "relax", "медитац": "meditation", "детск": "children"}


def genre_tag(query):
    """«электронную музыку» → «electronic» (или пусто)."""
    for w in _words(query):
        for k, v in GENRE_EN.items():
            if w.startswith(k):
                return v
    return ""


def control(text):
    """«нажми play», «играй», «пауза», «следующий трек», «предыдущий трек» → play/pause/next/previous или None."""
    t = " ".join(re.sub(r"[^\w\s-]", " ", (text or "").lower().replace("ё", "е")).split())
    for rx, act in CONTROL:
        if rx.match(t):
            return act
    return None


def _words(text):
    return re.findall(r"[a-zа-яё0-9-]+", (text or "").lower().replace("ё", "е"))


def _stem(w):
    """Грубая основа: у слов длиннее 4 букв — без двух последних, чтобы «спокойную» и «спокойное» совпали."""
    return w[:max(3, len(w) - 2)] if len(w) > 4 else w


class Catalog:
    """Список станций Dewiar: url_fn() — адрес из настроек (пусто — DEFAULT_URL), cache_path — копия с сайта,
    bundled_path — встроенный список. Потокобезопасен; обновление с сайта — в фоновом потоке."""

    def __init__(self, url_fn, cache_path, bundled_path):
        self.url_fn = url_fn
        self.cache = Path(cache_path)
        self.bundled = Path(bundled_path)
        self._data, self._loaded_at, self._fetching = None, 0.0, False
        self._lock = threading.Lock()

    def url(self):
        return (self.url_fn() or "").strip() or DEFAULT_URL

    @staticmethod
    def _norm(d):
        """radio.json (словарь или просто список) -> {"stations", "genres"}; станции без name или url отбрасываются."""
        st = d if isinstance(d, list) else (d or {}).get("stations") or []
        out = []
        for s in st:
            if isinstance(s, dict) and s.get("name") and s.get("url"):
                al = s.get("aliases") or []
                out.append({"name": str(s["name"]).strip(), "url": str(s["url"]).strip(),
                            "tags": str(s.get("tags") or "").strip().lower(),
                            "aliases": [str(a).lower() for a in (al if isinstance(al, list) else [al])]})
        genres = (d.get("genres") if isinstance(d, dict) else None) or []
        return {"stations": out, "genres": [str(g) for g in genres]}

    def _read(self, p):
        try:
            return self._norm(json.loads(Path(p).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None

    def data(self):
        """Текущий список, без ожидания сети. Первый раз читает копию (возраст — по времени файла) или встроенный;
        устарел — запускает refresh() в фоне."""
        with self._lock:
            if self._data is None:
                self._data = self._read(self.cache) or self._read(self.bundled) or {"stations": [], "genres": []}
                try:
                    self._loaded_at = self.cache.stat().st_mtime
                except OSError:
                    self._loaded_at = 0.0
            stale = time.time() - self._loaded_at > REFRESH and not self._fetching
            if stale:
                self._fetching = True
        if stale:
            threading.Thread(target=self.refresh, name="radio-list", daemon=True).start()
        return self._data

    def refresh(self):
        """Свежий список с сайта; сохраняется в копию, только если в нём есть станции. Неудача — работаем с тем,
        что есть, и пробуем снова через REFRESH."""
        try:
            import httpx
            r = httpx.get(self.url(), timeout=10, follow_redirects=True, headers={"Cache-Control": "no-cache"})
            r.raise_for_status()
            raw = r.json()
            d = self._norm(raw)
            if d["stations"]:
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.cache.with_suffix(".tmp")
                tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                tmp.replace(self.cache)
                with self._lock:
                    self._data = d
                log.info("Радио: список с сайта — %d станций", len(d["stations"]))
        except Exception as e:  # noqa: BLE001
            log.info("Радио: список с сайта недоступен (%s) — играю по сохранённому", e)
        finally:
            with self._lock:
                self._loaded_at, self._fetching = time.time(), False

    def stations(self):
        return self.data()["stations"]

    def genres(self):
        """Жанры для вопроса «что включить?»: из списка, иначе первые 8 тегов станций."""
        d = self.data()
        if d["genres"]:
            return d["genres"]
        seen = []
        for s in d["stations"]:
            for t in s["tags"].split():
                if t not in seen:
                    seen.append(t)
        return seen[:8]

    def match(self, query):
        """Станции под запрос -> [станция], лучшие первыми. Точное название (или alias) — она и станции с общими
        тегами; иначе очки: слово в названии 3, в тегах 2 (с синонимами из SYN), равные — вперемешку.
        "*" — все станции в случайном порядке («на твой вкус»)."""
        stations = self.stations()
        if query == "*":                                 # «на твой вкус»
            return random.sample(stations, len(stations))
        q = " ".join(_words(query))
        if not q:
            return []
        for s in stations:                               # точное название — сразу
            names = [s["name"].lower().replace("ё", "е")] + s["aliases"]
            if q in names or q.replace("радио ", "") in names:
                return [s] + [x for x in stations if x is not s and set(x["tags"].split()) & set(s["tags"].split())]
        words = [w for w in _words(query) if w not in FILLER]
        if not words:
            return []
        want = []
        for w in words:
            want.append(_stem(w))
            for k, v in SYN.items():
                if w.startswith(k):
                    want += [_stem(x) for x in v.split()]
        scored = []
        for i, s in enumerate(stations):
            name_w = [_stem(x) for x in _words(s["name"]) + [a for al in s["aliases"] for a in _words(al)]]
            tag_w = [_stem(x) for x in _words(s["tags"])]
            sc = sum(3 for w in want if w in name_w) + sum(2 for w in want if w in tag_w)
            if sc:
                scored.append((sc, random.random(), s))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [s for _, _, s in scored]

    def next_after(self, current):
        """«Дальше»: другая станция того же жанра, если есть, иначе следующая по списку."""
        st = self.stations()
        if not st:
            return None
        tags = set((current or {}).get("tags", "").split())
        same = [s for s in st if s["url"] != (current or {}).get("url") and tags & set(s["tags"].split())]
        if same:
            return random.choice(same)
        urls = [s["url"] for s in st]
        i = urls.index(current["url"]) if current and current.get("url") in urls else -1
        return st[(i + 1) % len(st)]


def parse(text, active=False, asked=False):
    """-> {"op": "ask"} | {"op": "play", "query", "strict", ["service"]} | {"op": "next"} | {"op": "stop"}
    | {"op": "app", "service"} | None. strict — играть, только если такое нашлось в своём списке («включи джаз»),
    иначе можно и каталог. active — радио играет или на паузе (только тогда «дальше» — команда);
    asked — только что спросили «какую музыку?», и это ответ (тогда хватает и короткого «джаз»)."""
    t = re.sub(r"[^\w\s-]", " ", (text or "").lower().replace("ё", "е"))
    t = " ".join(t.split())
    if not t:
        return None
    if STOP_RX.match(t):
        return {"op": "stop"}
    if APP_RX.match(t):
        return {"op": "app", "service": "yandex"}
    service = ""
    if YANDEX_RX.search(t) and re.match(rf"^{VERBS}\s", t):            # «включи электронную музыку в Яндекс Музыке»
        service, t = "yandex", " ".join(YANDEX_RX.sub(" ", t).split())
        m = PLAY_RX.match(t)
        rest = (m.group(1) or m.group(2) or "").strip() if m else ""
        return {"op": "play", "query": rest, "strict": False, "service": service}
    if active and NEXT_RX.match(t):
        return {"op": "next"}
    if ASK_RX.match(t):
        return {"op": "ask"}
    m = PLAY_RX.match(t)
    if m:
        rest = (m.group(1) or m.group(2) or "").strip()
        if re.match(r"^(?:музыку|радио|музычку|песни|что-нибудь|что-то|станцию)\b", rest) or \
                re.search(r"\b(?:музыку|музычку|радио)\b", t):
            return {"op": "play", "query": rest, "strict": False}
        return {"op": "play", "query": rest, "strict": True}       # «включи джаз» — только если такое есть в списке
    if asked and re.search(r"любую|любое|на твой вкус|все равно|сам выбери|выбери сам|без разницы|удиви|неважно|что хочешь", t):
        return {"op": "play", "query": "*", "strict": False}
    if asked and len(t.split()) <= 6:
        return {"op": "play", "query": t, "strict": True}
    return None
