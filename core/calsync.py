"""Календари Google, Яндекс, Outlook, iCloud — по секретной ссылке iCal (.ics), только чтение.

Google: Настройки календаря → «Интеграция календаря» → «Секретный адрес в формате iCal».
Яндекс: Календарь → ⋯ у календаря → «Настроить» → «Экспорт» → ссылка iCal.
События видны в календаре студии, в утренней сводке и в ответах; за N минут до встречи ассистент напоминает.
Секретная ссылка открывает календарь любому — в студию отдаётся только её домен (Calendars.public).

Разбор ICS — свой, небольшой: VEVENT (DTSTART/DTEND/DURATION с TZID, UTC или датой), SUMMARY, LOCATION, RRULE (DAILY,
WEEKLY с BYDAY, MONTHLY, YEARLY; INTERVAL, COUNT, UNTIL), EXDATE, RECURRENCE-ID (перенесённые повторы), STATUS:CANCELLED.
Чего нет: BYDAY у MONTHLY/YEARLY («второй вторник»), BYMONTHDAY, BYSETPOS — такие правила повторяются по дате начала.
Все времена приводятся к местному времени компьютера без пояса."""

import hashlib
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("dewiar.calsync")
WD = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
COLORS = ["#4FC3FF", "#FF9E5E", "#B78CFF", "#5EE0B5", "#FF7AB6", "#F5E663"]


class CalError(Exception):
    pass


def _unfold(text):
    """Склеить перенесённые строки ICS: по RFC 5545 продолжение строки начинается с пробела или табуляции."""
    return re.sub(r"\r?\n[ \t]", "", text.replace("\r\n", "\n"))


def _unescape(v):
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def _tz(name):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 — нет базы часовых поясов (Windows без tzdata) — считаем местным
        return None


def _dt(value, params):
    """Значение DTSTART/DTEND/EXDATE… -> (datetime в местном времени без пояса, весь_день).
    UTC (…Z) и TZID переводятся в местное время; неизвестный пояс или время без пояса — берётся как есть."""
    v = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", v):
        d = datetime.strptime(v[:8], "%Y%m%d")
        return d, True
    utc = v.endswith("Z")
    d = datetime.strptime(v.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if utc:
        return d.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None), False
    tzid = params.get("TZID")
    if tzid:
        z = _tz(tzid.strip('"'))
        if z is not None:
            return d.replace(tzinfo=z).astimezone().replace(tzinfo=None), False
    return d, False


def _prop(line):
    """«ИМЯ;ПАРАМ=знач:значение» -> (ИМЯ, {ПАРАМ: знач}, значение). Делим по первому двоеточию, поэтому
    двоеточие внутри параметра в кавычках (TZID="…:…") разбор сломает."""
    name, _, value = line.partition(":")
    parts = name.split(";")
    params = {}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        params[k.upper()] = v
    return parts[0].upper(), params, value


def parse_ics(text):
    """-> список событий-«шаблонов»: {uid, title, place, start, end, allday, rrule, exdates, rid, cancelled}.
    Непонятное значение пропускается, а не роняет весь календарь. Нет DTEND — конец по DURATION, иначе +1 день
    (событие на весь день) или +1 час."""
    events, cur = [], None
    for line in _unfold(text).split("\n"):
        if line == "BEGIN:VEVENT":
            cur = {"exdates": set()}
            continue
        if line == "END:VEVENT":
            if cur and cur.get("start"):
                events.append(cur)
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        name, params, value = _prop(line)
        try:
            if name == "DTSTART":
                cur["start"], cur["allday"] = _dt(value, params)
            elif name == "DTEND":
                cur["end"], _ = _dt(value, params)
            elif name == "DURATION":
                m = re.fullmatch(r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value.strip())
                if m:
                    w, d, h, mi, s = (int(x or 0) for x in m.groups())
                    cur["duration"] = timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)
            elif name == "SUMMARY":
                cur["title"] = _unescape(value)
            elif name == "LOCATION":
                cur["place"] = _unescape(value)
            elif name == "UID":
                cur["uid"] = value.strip()
            elif name == "RRULE":
                cur["rrule"] = dict(p.split("=", 1) for p in value.strip().split(";") if "=" in p)
            elif name == "EXDATE":
                for v in value.split(","):
                    cur["exdates"].add(_dt(v, params)[0])
            elif name == "RECURRENCE-ID":
                cur["rid"] = _dt(value, params)[0]
            elif name == "STATUS":
                cur["cancelled"] = value.strip().upper() == "CANCELLED"
        except ValueError:
            continue
    for e in events:
        if "end" not in e:
            e["end"] = e["start"] + e.pop("duration", timedelta(days=1) if e.get("allday") else timedelta(hours=1))
        e.pop("duration", None)
    return events


def _add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    import calendar
    day = d.day
    if day > calendar.monthrange(y, m + 1)[1]:
        return None                                      # 31-е в коротком месяце — повтора нет (как в RFC 5545)
    return d.replace(year=y, month=m + 1, day=day)


def expand(ev, start, end, limit=1000):
    """Начала всех случаев события, пересекающихся с [start, end) (не больше limit).
    Повторы перебираются не больше limit×5 шагов — с COUNT от первого случая, иначе от периода перед окном.
    COUNT учитывает и исключённые EXDATE — так в RFC 5545.
    UNTIL датой без времени включает весь этот день. Неизвестная частота — как разовое событие."""
    s0, dur = ev["start"], ev["end"] - ev["start"]
    rr = ev.get("rrule")
    if not rr:
        return [s0] if s0 < end and s0 + dur > start else []
    freq, interval = rr.get("FREQ", ""), max(1, int(rr.get("INTERVAL", "1") or 1))
    count = int(rr["COUNT"]) if rr.get("COUNT", "").isdigit() else None
    until = None
    if rr.get("UNTIL"):
        try:
            until, _ = _dt(rr["UNTIL"], {})
            if len(rr["UNTIL"]) == 8:
                until = until + timedelta(days=1) - timedelta(seconds=1)
        except ValueError:
            until = None
    days = [WD[x[-2:]] for x in rr.get("BYDAY", "").split(",") if x[-2:] in WD] if freq == "WEEKLY" else []
    out, n, k = [], 0, 0
    if count is None:
        # Без COUNT считать случаи от первого не нужно — перескакиваем к периоду перед окном (с запасом на
        # длительность: случай, начавшийся до окна, может в него заходить). Иначе ежедневное событие старше
        # limit×5 дней (~14 лет) упиралось бы в предел шагов и пропадало из календаря.
        edge = start - dur
        if freq == "DAILY":
            k = (edge - s0).days // interval - 1
        elif freq == "WEEKLY":
            k = (edge - s0).days // (7 * interval) - 1
        elif freq == "MONTHLY":
            k = ((edge.year - s0.year) * 12 + edge.month - s0.month) // interval - 1
        elif freq == "YEARLY":
            k = (edge.year - s0.year) // interval - 1
        k = max(0, k)
    cur, k_max = s0, k + limit * 5
    while k < k_max:
        k += 1
        if freq == "DAILY":
            cands = [s0 + timedelta(days=interval * (k - 1))]
        elif freq == "WEEKLY":
            week0 = s0 - timedelta(days=s0.weekday()) + timedelta(weeks=interval * (k - 1))
            cands = sorted(week0 + timedelta(days=d) for d in (days or [s0.weekday()]))
            cands = [c.replace(hour=s0.hour, minute=s0.minute, second=s0.second) for c in cands if c >= s0]
        elif freq == "MONTHLY":
            c = _add_months(s0, interval * (k - 1))
            cands = [c] if c else []
        elif freq == "YEARLY":
            c = _add_months(s0, 12 * interval * (k - 1))
            cands = [c] if c else []
        else:
            return [s0] if s0 < end and s0 + dur > start else []
        stop = False
        for c in cands:
            cur = c
            if (until and c > until) or (count is not None and n >= count):
                stop = True
                break
            n += 1
            if c in ev["exdates"]:
                continue
            if c >= end:
                stop = True
                break
            if c + dur > start:
                out.append(c)
                if len(out) >= limit:
                    return out
        if stop or (cur and cur >= end):
            break
    return out


def occurrences(events, start, end):
    """Шаблоны → конкретные события в окне; перенесённые повторы (RECURRENCE-ID) заменяют исходные."""
    moved = {}
    for e in events:
        if e.get("rid"):
            moved.setdefault(e.get("uid"), {})[e["rid"]] = e
    out = []
    for e in events:
        if e.get("rid"):
            continue
        ch = moved.get(e.get("uid"), {})
        dur = e["end"] - e["start"]
        for s in expand(e, start, end):
            x = ch.get(s)
            if x is not None:
                continue                              # этот случай перенесли — его покажет отдельное событие
            if not e.get("cancelled"):
                out.append({"title": e.get("title") or "(без названия)", "place": e.get("place", ""), "start": s,
                            "end": s + dur, "allday": bool(e.get("allday"))})
    for e in (x for d in moved.values() for x in d.values()):
        if not e.get("cancelled") and e["start"] < end and e["end"] > start:
            out.append({"title": e.get("title") or "(без названия)", "place": e.get("place", ""), "start": e["start"],
                        "end": e["end"], "allday": bool(e.get("allday"))})
    out.sort(key=lambda x: x["start"])
    return out


def norm_url(u):
    """Ссылка из студии -> https-адрес. webcal:// — та же ссылка, его выдают Apple и Outlook."""
    u = (u or "").strip()
    if u.startswith("webcal://"):
        u = "https://" + u[len("webcal://"):]
    if not re.match(r"^https?://", u):
        raise CalError("нужна ссылка вида https://… (секретный адрес iCal)")
    return u


def guess_name(u):
    if "google.com" in u:
        return "Google Календарь"
    if "yandex" in u:
        return "Яндекс Календарь"
    if "outlook" in u or "office365" in u or "live.com" in u:
        return "Outlook"
    if "icloud" in u:
        return "iCloud"
    return "Календарь"


class Calendars:
    """Подписки (в настройках: calendars.items — {id, url, name, color, enabled}) + кэш (STATE_DIR/calendars/<id>.ics).
    id — начало sha1 от ссылки: одна ссылка не подключится дважды. Кэш нужен, чтобы события были видны сразу
    после запуска и без сети. fetch подменяется в тестах."""

    def __init__(self, settings, cache_dir, fetch=None):
        self.s, self.dir = settings, Path(cache_dir)
        self._lock = threading.RLock()
        self._events = {}                                  # id -> шаблоны событий
        self.status = {}                                   # id -> {"ok", "time", "error", "count"}
        self.fetch = fetch or self._fetch
        self._load_cache()

    def items(self):
        return list(self.s.get("calendars", "items") or [])

    def _fetch(self, url):
        """Скачать календарь -> текст ICS. 401/403/404 и «не VCALENDAR» обычно значат, что скопирована не та ссылка
        (публичная или ссылка на страницу) — об этом и говорим."""
        import httpx
        r = httpx.get(url, follow_redirects=True, timeout=25, headers={"User-Agent": "Dewiar calendar"})
        if r.status_code in (401, 403, 404):
            raise CalError("календарь не открылся по ссылке — нужна именно секретная ссылка iCal (ответ сервера "
                           f"{r.status_code})")
        r.raise_for_status()
        if "BEGIN:VCALENDAR" not in r.text[:2000]:
            raise CalError("по ссылке не календарь iCal — проверьте, что скопирован «секретный адрес в формате iCal»")
        return r.text

    def _load_cache(self):
        for it in self.items():
            p = self.dir / f"{it['id']}.ics"
            if p.exists():
                try:
                    self._events[it["id"]] = parse_ics(p.read_text(encoding="utf-8", errors="replace"))
                    self.status[it["id"]] = {"ok": True, "time": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes"),
                                             "count": len(self._events[it["id"]]), "cached": True}
                except OSError:
                    pass

    def add(self, url, name=""):
        """Подключить календарь (сразу скачав его) -> public(). Имя — данное человеком, иначе X-WR-CALNAME
        из файла, иначе по адресу. Повторное добавление той же ссылки заменяет запись."""
        url = norm_url(url)
        text = self.fetch(url)
        evs = parse_ics(text)
        cid = hashlib.sha1(url.encode()).hexdigest()[:10]
        items = [x for x in self.items() if x["id"] != cid]
        m = re.search(r"^X-WR-CALNAME:(.+)$", _unfold(text), re.M)
        item = {"id": cid, "url": url, "name": (name or (_unescape(m.group(1)) if m else "") or guess_name(url))[:60],
                "color": COLORS[len(items) % len(COLORS)], "enabled": True}
        items.append(item)
        self.s.update({"calendars": {"items": items}})
        self._store(cid, text, evs)
        log.info("📅 Календарь подключён: %s (%d событий)", item["name"], len(evs))
        return self.public()

    def remove(self, cid):
        self.s.update({"calendars": {"items": [x for x in self.items() if x["id"] != cid]}})
        with self._lock:
            self._events.pop(cid, None)
            self.status.pop(cid, None)
        try:
            (self.dir / f"{cid}.ics").unlink()
        except OSError:
            pass
        return self.public()

    def toggle(self, cid, on):
        items = self.items()
        for x in items:
            if x["id"] == cid:
                x["enabled"] = bool(on)
        self.s.update({"calendars": {"items": items}})
        return self.public()

    def _store(self, cid, text, evs):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{cid}.ics").write_text(text, encoding="utf-8")
        with self._lock:
            self._events[cid] = evs
            self.status[cid] = {"ok": True, "time": datetime.now().isoformat(timespec="minutes"), "count": len(evs)}

    def refresh(self):
        """Скачать заново все включённые календари. Ошибка одного не мешает остальным; его прежние события остаются."""
        for it in self.items():
            if not it.get("enabled", True):
                continue
            try:
                text = self.fetch(it["url"])
                self._store(it["id"], text, parse_ics(text))
            except Exception as e:  # noqa: BLE001
                log.info("📅 %s не обновился: %s", it.get("name"), e)
                st = self.status.setdefault(it["id"], {})
                st.update(ok=False, error=str(e)[:200])

    def events(self, start, end):
        """События всех включённых календарей в окне -> [{"title","place","start","end","allday","cal","color","cid"}]."""
        out = []
        with self._lock:
            for it in self.items():
                if not it.get("enabled", True):
                    continue
                for e in occurrences(self._events.get(it["id"], []), start, end):
                    out.append(dict(e, cal=it["name"], color=it.get("color", COLORS[0]), cid=it["id"]))
        out.sort(key=lambda x: x["start"])
        return out

    def public(self):
        """Для студии. Секретную ссылку целиком не отдаём — только домен: по ней календарь читает кто угодно."""
        from urllib.parse import urlparse
        return {"items": [dict(x, url=(urlparse(x["url"]).netloc or "") + "/…", status=self.status.get(x["id"], {}))
                          for x in self.items()],
                "remind": int(self.s.get("calendars", "remind_minutes") or 0)}


