"""Дела: «сделано» и достижения (отзыв 13.10: «геймификация — выполнил 3 дела, значки и достижения, в конце дня "ты
сегодня сделал 5–7 дел"»; отчёт №14: «Отметь как исполненное» — нечем было отметить).

Журнал done.json: [{id, title, at (мс), src: pc|voice|tap|alarm, rid — напоминание, если закрыто им}]. Он же уходит в
синхронизацию видом «done» — тот же формат, достижения и рубежи, что «дела» в android/assets/www/app.js (меняешь здесь —
меняй и там). Достижения не хранятся — считаются по журналу (stats): так они одинаковы на телефоне и компьютере. Дневные
рубежи (3, 5, 7, 10 дел за день) поздравляют каждый день; значки (ACHIEVE) — один раз, когда получены впервые."""
import datetime as dt
import json
import logging
import random
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.done")

DONE_MAX = 1500
DAY_MILES = (3, 5, 7, 10)
# id, группа, порог, значок, название, за что — как ACHIEVE в app.js
ACHIEVE = [
    ("d3", "day", 3, "🥉", "Тройка", "3 дела за день"),
    ("d5", "day", 5, "🥈", "Пятёрка", "5 дел за день"),
    ("d10", "day", 10, "🥇", "Десятка", "10 дел за день"),
    ("s3", "streak", 3, "🔥", "Три дня подряд", "дела три дня подряд"),
    ("s7", "streak", 7, "⭐", "Неделя", "дела семь дней подряд"),
    ("s30", "streak", 30, "🏆", "Месяц", "дела тридцать дней подряд"),
    ("t10", "total", 10, "✨", "Первые десять", "10 дел всего"),
    ("t50", "total", 50, "💪", "Полсотни", "50 дел всего"),
    ("t100", "total", 100, "💯", "Сотня", "100 дел всего"),
    ("t500", "total", 500, "👑", "Пятьсот", "500 дел всего"),
]


def _pl(n, one, few, many):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def dela(n):
    return _pl(n, "дело", "дела", "дел")


def dney(n):
    return _pl(n, "день", "дня", "дней")


def day_key(ms):
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def _val(a, s):
    return {"day": s["best_day"], "streak": s["best_streak"], "total": s["total"]}[a[1]]


def stats(items, now=None):
    """-> {today, items (сегодняшние), streak (дни подряд до сегодня; сегодня пусто — до вчера), best_streak, best_day,
    total, earned (полученные значки)}."""
    now = now or time.time() * 1000
    by = {}
    for x in items:
        k = day_key(x["at"])
        by[k] = by.get(k, 0) + 1
    today = day_key(now)
    d = dt.date.fromisoformat(today)
    if today not in by:
        d -= dt.timedelta(days=1)
    streak = 0
    while d.isoformat() in by:
        streak += 1
        d -= dt.timedelta(days=1)
    best = run = 0
    prev = None
    for k in sorted(by):
        cur = dt.date.fromisoformat(k)
        run = run + 1 if prev is not None and (cur - prev).days == 1 else 1
        prev = cur
        best = max(best, run)
    s = {"today": by.get(today, 0), "items": [x for x in items if day_key(x["at"]) == today], "streak": streak,
         "best_streak": best, "best_day": max(by.values(), default=0), "total": len(items), "by_day": by}
    s["earned"] = [a for a in ACHIEVE if _val(a, s) >= a[2]]
    return s


_STOP = re.compile(r"^(это|как|для|что|все|уже|мне|меня|надо|нужно|сделал[аи]?|сделать)$")


def stems(t):
    """Основы слов по 4 буквы: «я позвонила Игорю» ↔ «позвонить Игорю»."""
    w = re.split(r"[^a-zа-я0-9]+", str(t or "").lower().replace("ё", "е"))
    return [x[:4] for x in w if len(x) > 2 and not _STOP.match(x)]


class Done:
    """Журнал сделанного. on_change — после каждой записи (синхронизация с телефоном, sync.py)."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.on_change = None
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [x for x in d if isinstance(x, dict) and x.get("id") and x.get("title") and x.get("at")] if isinstance(d, list) else []
        except (OSError, ValueError):
            self.items = []

    def _save(self):
        self.items.sort(key=lambda x: x["at"])
        del self.items[:-DONE_MAX]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        if self.on_change:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                log.debug("дела: on_change", exc_info=True)

    def stats(self, now=None):
        with self._lock:
            return stats(list(self.items), now)

    def add(self, entries, src="pc", at=None):
        """entries — строки или {title, rid}. -> {items, stats, fresh (новые значки), mile (дневной рубеж или 0)}."""
        at = int(at or time.time() * 1000)
        with self._lock:
            before = stats(self.items, at)
            new = []
            for e in entries if isinstance(entries, (list, tuple)) else [entries]:
                o = {"title": e} if isinstance(e, str) else dict(e or {})
                title = re.sub(r"\s+", " ", str(o.get("title") or "")).strip()[:120]
                if not title:
                    continue
                title = title[0].upper() + title[1:]
                new.append({"id": "d" + _b36(at) + "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(5)),
                            "title": title, "at": int(o.get("at") or at + len(new)), "src": src, "rid": str(o.get("rid") or "")})
            self.items.extend(new)
            if new:
                self._save()
            after = stats(self.items, at)
        fresh = [a for a in ACHIEVE if _val(a, after) >= a[2] > _val(a, before)]
        mile = max([m for m in DAY_MILES if before["today"] < m <= after["today"]], default=0)
        return {"items": new, "stats": after, "fresh": fresh, "mile": mile}

    def undo(self, iid):
        with self._lock:
            x = next((i for i in self.items if i["id"] == iid), None)
            if x is None:
                return None
            self.items = [i for i in self.items if i["id"] != iid]
            self._save()
            return x

    # ---------- синхронизация (sync.py) ----------
    def upsert(self, iid, d):
        with self._lock:
            self.items = [i for i in self.items if i["id"] != iid]
            if d.get("title") and int(d.get("at") or 0):
                self.items.append({"id": iid, "title": str(d["title"])[:120], "at": int(d["at"]), "src": str(d.get("src") or ""),
                                   "rid": str(d.get("rid") or "")})
            self._save()

    def delete(self, iid):
        with self._lock:
            n = len(self.items)
            self.items = [i for i in self.items if i["id"] != iid]
            if len(self.items) != n:
                self._save()

    def public(self):
        """Для студии: {today: [...], stats, achievements: [{id, icon, name, what, got, val, n}]}."""
        s = self.stats()
        ach = [{"id": a[0], "group": a[1], "n": a[2], "icon": a[3], "name": a[4], "what": a[5], "got": _val(a, s) >= a[2],
                "val": _val(a, s)} for a in ACHIEVE]
        week = []
        today = dt.date.today()
        for i in range(6, -1, -1):
            d = (today - dt.timedelta(days=i)).isoformat()
            week.append({"day": d, "n": s["by_day"].get(d, 0)})
        return {"items": s["items"], "today": s["today"], "streak": s["streak"], "best_streak": s["best_streak"],
                "best_day": s["best_day"], "total": s["total"], "achievements": ach, "week": week}


def _b36(n):
    a = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = a[r] + out
    return out or "0"


_VERB = re.compile(r"(?:ть|ться|ти|[аеиоуыяю]л|[аеиоуыяю]л[аи]|лся|лась|лись)$")


def _hit_ok(title_words, said):
    """Совпадение по основам — и хотя бы одно не глаголом («позвонил маме» ≠ «позвонить в банк»: общий только «позв»),
    если в напоминании есть не только глаголы."""
    words = [x for x in re.split(r"[^a-zа-я0-9]+", str(title_words or "").lower().replace("ё", "е")) if len(x) > 2 and not _STOP.match(x)]
    if not words:
        return 0.0
    hits = [x for x in words if x[:4] in said]
    if not hits:
        return 0.0
    nouns = [x for x in words if not _VERB.search(x)]
    if nouns and not any(x in nouns for x in hits):
        return 0.0
    return len(hits) / len(words)


def reminder_match(title, reminders, now=None, ahead=False):
    """Напоминание, которое и есть это дело (не будильник и не таймер): разовое — до конца сегодняшнего дня (поздно
    вечером — и сразу после полуночи), повтор — любое. ahead — не нашлось на сегодня: и разовое на ближайшие 36 часов
    («я позвонил в банк» в 22:40, а план поставлен на завтра в 13 — сделано раньше)."""
    w = stems(title)
    if not w:
        return None
    now = now or dt.datetime.now()
    ends = [max(now.replace(hour=23, minute=59, second=59), now + dt.timedelta(hours=3))]
    if ahead:                                     # и весь завтрашний день (экзамен 25.10: в 00:45 план «на завтра в 16 и 19» не находился)
        ends.append(max(now + dt.timedelta(hours=36), (now + dt.timedelta(days=1)).replace(hour=23, minute=59, second=59)))
    for end in ends:
        best, bs = None, 0.0
        for x in reminders:
            if x.get("kind") in ("alarm", "timer", "job") or x.get("paused"):
                continue
            try:
                at = dt.datetime.fromisoformat(x["at"])
            except (KeyError, ValueError):
                continue
            if not x.get("repeat") and at > end:
                continue
            sc = _hit_ok(x.get("text"), w)
            if sc >= 0.5 and sc > bs:
                best, bs = x, sc
        if best is not None:
            return best
    return None


def say(r, closed=()):
    """Итог для модели после mark_done: что отмечено, сколько сегодня, серия, новое достижение — и «похвали коротко»."""
    s = r["stats"]
    ach = "; ".join(f"{a[3]} «{a[4]}» — {a[5]}" for a in r["fresh"])
    out = "Отмечено сделанным: " + ", ".join(f"«{x['title']}»" for x in r["items"]) + "."
    if closed:
        out += " Напоминание закрыто: " + ", ".join(closed) + "."
    out += f" Сегодня сделано {s['today']} {dela(s['today'])}"
    if s["streak"] >= 2:
        out += f", {s['streak']} {dney(s['streak'])} подряд"
    out += f", всего {s['total']}."
    if ach:
        out += f" Новое достижение: {ach}."
    elif r["mile"]:
        out += f" Рубеж дня: {r['mile']} {dela(r['mile'])}!"
    return out + " Похвали коротко и тепло, одной фразой" + (", назови достижение" if ach else "") + "; не перечисляй дела заново."


def report(done, days=1):
    d = max(1, min(60, int(days or 1)))
    s = done.stats()
    start = dt.datetime.combine(dt.date.today() - dt.timedelta(days=d - 1), dt.time())
    since = start.timestamp() * 1000
    with done._lock:
        it = [x for x in done.items if x["at"] >= since]
    by = {}
    for x in it:
        by.setdefault(day_key(x["at"]), []).append(x["title"])
    if it:
        if d == 1:
            out = f"Сегодня сделано {len(it)} {dela(len(it))}: " + "; ".join(sum(by.values(), []))
        else:
            out = f"За {d} {dney(d)} сделано {len(it)} {dela(len(it))}:\n" + "\n".join(f"{k[8:]}.{k[5:7]}: {'; '.join(v)}" for k, v in by.items())
    else:
        out = "Сегодня пока ничего не отмечено." if d == 1 else f"За {d} {dney(d)} ничего не отмечено."
    out += f"\nСерия: {s['streak']} {dney(s['streak'])} подряд (лучшая — {s['best_streak']}). Всего: {s['total']}. Лучший день: {s['best_day']}."
    out += "\nДостижения: " + (", ".join(f"{a[3]} {a[4]}" for a in s["earned"]) or "пока нет") + "."
    nxt = [next((a for a in ACHIEVE if a[1] == g and _val(a, s) < a[2]), None) for g in ("day", "streak", "total")]
    nxt = [a for a in nxt if a]
    if nxt:
        out += " Следующие: " + "; ".join(f"{a[3]} {a[4]} ({a[5]}, сейчас {_val(a, s)})" for a in nxt) + "."
    return out


def prompt(done):
    s = done.stats()
    out = ("\n\nДЕЛА И ДОСТИЖЕНИЯ. «Запланируй на сегодня…», «план на день», «мои дела на завтра» — это дела, не календарь: "
           "на каждое дело — свой set_reminder с его временем. Встреча, запись к мастеру, дело со временем («запиши встречу с Ирой на "
           "вторник в 12», «завтра в 13 у меня массаж», «в 8:10 встреча с Максимом») — тоже дело: set_reminder на это время, не "
           "заметка; «напомни за день / за час» — ещё один set_reminder на то время. В календарь — только если прямо сказано «в календарь». "
           "Поставил(а) или отметил(а) дело — подтверди одной фразой только его; остальные дела и планы вслух не перечисляй, "
           "пока не спросят: рядом могут быть чужие люди. "
           "Пользователь говорит, что сделал дело («я позвонил Игорю и сделал тренировку», «отметь как "
           "исполненное», «готово, купил хлеб») — вызови mark_done (каждое дело — отдельной строкой, коротко: «Позвонить Игорю», "
           "«Тренировка»), подходящее напоминание закроется само; потом похвали коротко, одной фразой. Отметил по ошибке — "
           "mark_done с undo. «Что я сегодня сделал», «мои достижения» — done_report. "
           f"Сейчас: сегодня сделано {s['today']} {dela(s['today'])}")
    if s["items"]:
        out += " (" + "; ".join(x["title"] for x in s["items"][-6:]) + ")"
    if s["streak"] >= 2:
        out += f", серия {s['streak']} {dney(s['streak'])} подряд"
    return out + f", всего {s['total']}."
