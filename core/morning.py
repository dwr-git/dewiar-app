"""«Утро с Лирой» (0.57; согласовано с владельцем 28.10: одна утренняя сводка — погода, день, дела, сотрудники, клиенты,
которые ждут, важная почта; на компьютере и на телефоне).

gather(eng) собирает утро из того, что уже есть в Dewiar, — без модели и без выдумок:
  weather  — Open-Meteo по городу из настроек («Утро» → город; tools.t_weather), одной строкой и числами;
  today    — встречи календаря и дела на сегодня;
  team     — «Поручения»: просрочено, ждут вашей проверки, что сотрудники написали за ночь;
  clients  — «Клиенты»: чей следующий шаг просрочен или сегодня;
  mail     — непрочитанные письма (от людей — первыми; рассылки — только числом);
  tasks    — фоновые задачи: что готово за ночь, что ждёт ответа.
context(d) — те же данные строками для модели: из них она говорит сводку голосом персонажа (engine_music._brief_context:
утренняя сводка по расписанию и «сводка дня», когда утром сели за компьютер). public(d) — для карточки «Утро» на главной
студии и для своего телефона (конверт own {morning}, шифр на устройствах): там сводка дня дополняется клиентами и почтой.
Погода и почта ходят в сеть — их держим в кэше 20 минут; сломалась сеть — раздела просто нет."""
import logging
import re
import threading
import time
from datetime import datetime, timedelta

log = logging.getLogger("dewiar.morning")
WD = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
CACHE_S = 20 * 60
BULK_RX = re.compile(r"no-?reply|noreply|news(?:letter)?|mailer|notif|рассылк|digest|promo|marketing|bounce|support@|info@|hello@", re.I)
_cache = {}
_lock = threading.Lock()


def _cached(key, fn, fresh=False):
    with _lock:
        hit = _cache.get(key)
        if hit and not fresh and time.time() - hit[0] < CACHE_S:
            return hit[1]
    try:
        v = fn()
    except Exception as e:  # noqa: BLE001 — сеть, почта: раздела просто не будет
        log.info("утро: %s — %s", key, e)
        v = None
    with _lock:
        _cache[key] = (time.time(), v)
    return v


def weather(city, eng=None):
    """-> {city, now, feels, sky, wind, min, max, sky_day, rain, line} или None (weatherq: тот же поиск города с областью)."""
    if not city:
        return None
    import weatherq as W

    def get():
        via = (getattr(getattr(eng, "toolbox", None), "hooks", None) or {}).get("dewiar_web") if eng else None
        place = W.geocode(city, via)
        if not place:
            return None
        f = W.forecast(place, via)
        w = {"city": place["name"], "now": f["now"], "feels": f["feels"], "sky": f["sky"], "wind": f["wind"]}
        if f["days"]:
            x = f["days"][0]
            w.update(min=x["min"], max=x["max"], sky_day=x["sky"], rain=x["rain"])
        sg = lambda t: f"{t:+d}°".replace("+0°", "0°")  # noqa: E731
        w["line"] = (f"{w['city']}: сейчас {sg(w['now'])}, {w['sky']}" + (f"; днём {sg(w['min'])}…{sg(w['max'])}" if "min" in w else "")
                     + (f", осадки {w['rain']}%" if w.get("rain") is not None else ""))
        return w
    return _cached("w:" + city.lower(), get)


def _hm(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


def _today(eng, now):
    key = now.date().isoformat()
    cal = eng.calendar_month(now.year, now.month)
    items = cal["days"].get(key, [])
    meet = [{"time": x.get("time") or "", "title": x["title"], "place": x.get("place") or ""} for x in items if x["type"] == "event"]
    todo = [{"time": x.get("time") or "", "title": x["title"]} for x in items if x["type"] == "reminder" and not x.get("done")]
    return {"meet": sorted(meet, key=lambda x: x["time"] or "99"), "todo": sorted(todo, key=lambda x: x["time"] or "99")}


def _team(eng):
    T = getattr(eng, "team", None)
    if not T or not ((eng.s.get("features") or {}).get("team")) or not T.st.get("members"):
        return None
    p = T.public()
    since = time.time() - 16 * 3600
    late = [{"title": t["title"], "name": t["name"], "due": t["due_text"]} for t in p["tasks"] if t["late"]]
    check = [{"title": t["title"], "name": t["name"]} for t in p["tasks"] if t["state"] == "done"]
    msgs = [{"name": x["name"], "t": (x.get("t") or "фото")[:200]} for x in p["inbox"] if not x.get("out") and x["ts"] > since]
    opened = sum(1 for t in p["tasks"] if t["state"] in ("new", "work", "moved"))
    return {"late": late[:8], "check": check[:8], "msgs": msgs[-5:], "open": opened, "company": p.get("company") or ""}


def _clients(eng, now):
    C = getattr(eng, "clients", None)
    if not C or not ((eng.s.get("features") or {}).get("clients")):
        return None
    over, today = [], []
    for x in C.list():
        n = x.get("next") or {}
        if not n.get("at"):
            continue
        it = {"name": x["name"] + (f" («{x['company']}»)" if x.get("company") and x["company"] != x["name"] else ""), "what": n.get("what", ""), "time": _hm(n["at"])}
        if x["overdue"]:
            over.append(it)
        elif n["at"][:10] == now.date().isoformat():
            today.append(it)
    owed, stuck = [], 0                                  # сделки (deals.py): просроченная оплата — «кто должен», и что зависло
    try:
        from deals import fmt_amount
        for d in C.deals():
            if d["overdue"]:
                owed.append({"name": d["client"], "what": f"«{d['title']}»" + (f" — {fmt_amount(d['amount'], d['cur'])}" if d.get("amount") else ""), "time": ""})
            elif d["stuck"]:
                stuck += 1
    except Exception:  # noqa: BLE001
        log.debug("утро: сделки", exc_info=True)
    return {"over": over[:6], "today": today[:6], "owed": owed[:6], "stuck": stuck} if over or today or owed or stuck else None


def _mail(eng, fresh=False):
    M = getattr(eng, "mail", None)
    if not M or not M.configured() or (eng.s.get("morning") or {}).get("mail") is False:
        return None

    def get():
        items = M.inbox(limit=12, unread=True)
        people = [x for x in items if not BULK_RX.search(x.get("from") or "")]
        who = lambda f: re.sub(r"\s*<[^>]+>", "", f or "").strip(' "') or re.sub(r".*<|>.*", "", f or "")
        return {"unread": len(items), "more": len(items) >= 12, "people": [{"from": who(x["from"]), "subject": x["subject"][:120]} for x in people[:4]],
                "bulk": len(items) - len(people)}
    return _cached("mail", get, fresh)


def _tasks(eng):
    try:
        ts = eng.tasks.list()
    except Exception:  # noqa: BLE001
        return None
    since = (datetime.now() - timedelta(hours=14)).isoformat(timespec="seconds")
    done = [t.get("title", "") for t in ts if t.get("status") == "done" and str(t.get("updated") or "") >= since]
    wait = [{"title": t.get("title", ""), "q": (t.get("question") or "")[:160]} for t in ts if t.get("status") == "waiting"]
    return {"done": done[:4], "wait": wait[:3]} if done or wait else None


def city(eng):
    return str((eng.s.get("morning") or {}).get("city") or "").strip()


def gather(eng, net=True, fresh=False):
    """Всё утро одним словарём (разделы, которых нет, — None). net=False — без погоды и почты (быстро, без сети)."""
    now = datetime.now()
    d = {"date": now.strftime("%Y-%m-%d"), "weekday": WD[now.weekday()], "time": now.strftime("%H:%M"), "city": city(eng),
         "weather": None, "today": None, "team": None, "clients": None, "mail": None, "tasks": None}
    for k, fn in (("today", lambda: _today(eng, now)), ("team", lambda: _team(eng)), ("clients", lambda: _clients(eng, now)), ("tasks", lambda: _tasks(eng))):
        try:
            d[k] = fn()
        except Exception:  # noqa: BLE001
            log.debug("утро: %s", k, exc_info=True)
    if net:
        if d["city"]:
            d["weather"] = weather(d["city"], eng) if not fresh else (_cache.pop("w:" + d["city"].lower(), None), weather(d["city"], eng))[1]
        d["mail"] = _mail(eng, fresh)
    return d


def context(d):
    """Строки для модели (утренняя сводка, «сводка дня»): только то, что есть; погода — уже числами."""
    out = []
    w = d.get("weather")
    if w:
        out.append("Погода (уже узнана, искать не нужно): " + w["line"] + ".")
    t = d.get("today") or {}
    if t.get("meet"):
        out.append("Встречи сегодня: " + "; ".join(f"{x['time'] or 'весь день'} {x['title']}" + (f" ({x['place']})" if x["place"] else "") for x in t["meet"]) + ".")
    if t.get("todo"):
        out.append("Дела на сегодня: " + "; ".join(f"{x['time']} {x['title']}".strip() for x in t["todo"][:8]) + ".")
    tm = d.get("team")
    if tm:
        parts = []
        if tm["late"]:
            parts.append("просрочено — " + "; ".join(f"{x['name']}: «{x['title']}»" for x in tm["late"]))
        if tm["check"]:
            parts.append("ждут вашей проверки — " + "; ".join(f"{x['name']}: «{x['title']}»" for x in tm["check"]))
        if tm["msgs"]:
            parts.append("написали — " + "; ".join(f"{x['name']}: «{x['t'].rstrip('.')}»" for x in tm["msgs"]))
        if parts:
            out.append("Сотрудники («Поручения»): " + "; ".join(parts) + ".")
    c = d.get("clients")
    if c:
        if c["over"]:
            out.append("Клиенты ждут (срок шага прошёл): " + "; ".join(f"{x['name']} — {x['what']}" for x in c["over"]) + ".")
        if c["today"]:
            out.append("Клиенты сегодня: " + "; ".join(f"{x['time']} {x['name']} — {x['what']}".strip() for x in c["today"]) + ".")
        if c.get("owed"):
            out.append("Должны, срок оплаты прошёл: " + "; ".join(f"{x['name']} — {x['what']}" for x in c["owed"]) + ".")
        if c.get("stuck"):
            out.append(f"Сделок без движения неделю и дольше: {c['stuck']}.")
    m = d.get("mail")
    if m and m["unread"]:
        out.append(f"Почта: непрочитанных {m['unread']}{'+' if m['more'] else ''}"
                   + (". От людей: " + "; ".join(f"{x['from']} — «{x['subject']}»" for x in m["people"]) if m["people"] else ", всё — рассылки") + ".")
    tk = d.get("tasks")
    if tk:
        if tk["done"]:
            out.append("Готово за ночь (фоновые задачи): " + "; ".join(f"«{x}»" for x in tk["done"]) + ".")
        if tk["wait"]:
            out.append("Задача ждёт ответа пользователя: " + "; ".join(f"«{x['title']}» — {x['q']}" for x in tk["wait"]) + ".")
    return "\n".join(out)


def public(d):
    """Для студии и своего телефона — как есть, с отметкой времени."""
    return dict(d, at=int(time.time() * 1000))
