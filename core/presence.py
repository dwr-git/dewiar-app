"""«Сам замечает и сам начинает»: человек вернулся к компьютеру — ассистент коротко здоровается и говорит главное, что
случилось без него (готовые задачи, задача ждёт ответа, скоро встреча); первый раз за день — короткая сводка дня.

idle_seconds() — сколько секунд не трогали мышь и клавиатуру (Windows, GNOME на X11 и Wayland, другие X11, macOS;
не узнать — None). Away — отслеживает «ушёл» (простой дольше away_after или компьютер спал) и «вернулся».
plan() — решает, говорить ли и что передать модели. Говорим один раз за отлучку и только если есть что сказать,
не ночью и не чаще раза в 40 минут — чтобы не надоедать."""
import ctypes
import datetime as dt
import re
import shutil
import subprocess
import sys
import time

_method = None          # какой способ узнать простой сработал (чтобы не перебирать каждый раз)


def _win():
    class LII(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    lii = LII(); lii.cbSize = ctypes.sizeof(LII)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        return None
    return ((ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0


def _mutter():
    """GNOME (Ubuntu) — и на X11, и на Wayland: org.gnome.Mutter.IdleMonitor, ответ «(uint64 12345,)» в миллисекундах."""
    if not shutil.which("gdbus"):
        return None
    out = subprocess.run(["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor", "--object-path",
                          "/org/gnome/Mutter/IdleMonitor/Core", "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"],
                         capture_output=True, text=True, timeout=3)
    m = re.search(r"uint64\s+(\d+)", out.stdout or "")
    return int(m.group(1)) / 1000.0 if m else None


_xss = None


def _x11():
    """Другие X11-окружения: XScreenSaverQueryInfo из libXss (без сторонних программ)."""
    global _xss
    if _xss is None:
        import ctypes.util

        class Info(ctypes.Structure):
            _fields_ = [("window", ctypes.c_ulong), ("state", ctypes.c_int), ("kind", ctypes.c_int),
                        ("til_or_since", ctypes.c_ulong), ("idle", ctypes.c_ulong), ("eventMask", ctypes.c_ulong)]
        xlib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "libX11.so.6")
        xss = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Xss") or "libXss.so.1")
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]; xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(Info)
        xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Info)]
        dpy = xlib.XOpenDisplay(None)
        if not dpy:
            raise OSError("нет X-дисплея")
        _xss = (xss, dpy, xlib.XDefaultRootWindow(dpy), xss.XScreenSaverAllocInfo())
    xss, dpy, root, info = _xss
    if not xss.XScreenSaverQueryInfo(dpy, root, info):
        return None
    return info.contents.idle / 1000.0


def _mac():
    out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=3).stdout
    m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out or "")
    return int(m.group(1)) / 1e9 if m else None


def idle_seconds():
    """Секунд без мыши и клавиатуры или None (не умеем узнать в этой системе)."""
    global _method
    ways = [_win] if sys.platform == "win32" else [_mac] if sys.platform == "darwin" else [_mutter, _x11]
    for f in ([_method] if _method else ways):
        try:
            v = f()
        except Exception:  # noqa: BLE001
            v = None
        if v is not None:
            _method = f
            return v
    _method = None
    return None


class Away:
    """«Ушёл» — простой дольше away_after секунд (или компьютер спал: часы прыгнули вперёд). «Вернулся» — снова трогают
    мышь/клавиатуру (простой меньше 10 с). feed(idle, now) -> None или секунды отлучки (один раз на возвращение)."""

    def __init__(self, away_after=1200):
        self.away_after = away_after
        self.since = None            # когда ушёл (wall-clock, секунды)
        self.last = None

    def feed(self, idle, now=None):
        now = time.time() if now is None else now
        if self.last is not None and now - self.last > self.away_after and self.since is None:
            self.since = self.last                       # компьютер спал / был выключен — это тоже отлучка
        self.last = now
        if idle is None:                                 # простой не узнать — возвращение после сна считаем сразу
            if self.since is not None:
                gone, self.since = now - self.since, None
                return gone
            return None
        if self.since is None and idle >= self.away_after:
            self.since = now - idle
        elif self.since is not None and idle < 10:
            gone, self.since = now - self.since, None
            return gone
        return None


def _hm(sec):
    m = int(sec // 60)
    if m < 60:
        return f"{m} мин"
    h, m = divmod(m, 60)
    return f"{h} ч" + (f" {m} мин" if m else "")


def plan(gone, since, tasks, upcoming, last_greet, now=None, night=(23, 7), day_brief=True, dstat=None, eve_said=None, news="", care=""):
    """Что сказать вернувшемуся. gone — секунд отлучки, since — datetime ухода; tasks — список задач (public());
    upcoming — [(время «HH:MM», что)] на ближайшие 2 часа; last_greet — datetime прошлого приветствия или None.
    dstat — done.stats() (сделанные дела), eve_said — дата прошлого итога дня: вечером (с 19:00), если сегодня есть сделанное,
    один раз — итог дня (отзыв 13.10: «в конце дня — ты сегодня сделал 5–7 дел»).
    -> None (молчим) или {"kind": "day" | "back" | "eve", "facts": [...], "gone": "1 ч 20 мин"}."""
    now = now or dt.datetime.now()
    if night and (now.hour >= night[0] or now.hour < night[1]):
        return None                                      # ночью не заговариваем
    if last_greet and (now - last_greet).total_seconds() < 40 * 60:
        return None
    facts = []
    s_iso = since.isoformat(timespec="seconds")
    done = [t for t in tasks if t.get("status") == "done" and (t.get("updated") or "") >= s_iso]
    wait = [t for t in tasks if t.get("status") == "waiting"]
    if done:
        facts.append("Пока пользователя не было, готовы задачи: " + "; ".join(f"«{t.get('title', '')}»" for t in done[:3]) + ".")
    if wait:
        facts.append("Ждёт ответа пользователя задача: " + "; ".join(f"«{t.get('title', '')}»" for t in wait[:2]) + ".")
    if upcoming:
        facts.append("Скоро: " + "; ".join(f"в {a} — {b}" for a, b in upcoming[:3]) + ".")
    if news:                                             # обновились — сказать, что нового (news.say_fact), один раз
        facts.append(news)
    if care:                                             # «Заботливая память» (0.61): событие прошло — спросить, как прошло
        facts.append(care)
    if dstat and dstat.get("today") and now.hour >= 19 and eve_said != now.date():
        from done import dela, dney
        f = (f"Сегодня пользователь отметил сделанными {dstat['today']} {dela(dstat['today'])}: "
             + ", ".join(f"«{x['title']}»" for x in dstat.get("items", [])[-7:]) + ".")
        if dstat.get("streak", 0) >= 2:
            f += f" Серия: {dstat['streak']} {dney(dstat['streak'])} подряд."
        return {"kind": "eve", "facts": [f] + facts, "gone": _hm(gone)}
    first_today = day_brief and (last_greet is None or last_greet.date() < now.date()) and gone >= 3 * 3600
    if first_today:
        return {"kind": "day", "facts": facts, "gone": _hm(gone)}
    if not facts:
        return None                                      # сказать нечего — не отвлекаем
    return {"kind": "back", "facts": facts, "gone": _hm(gone)}


def prompt(p, brief_context=""):
    """Поручение модели для приветствия (её голосом и характером). Есть «Заботливая память» — в конце можно один тёплый вопрос."""
    t = _prompt(p, brief_context)
    if any(str(f).startswith("[Заботливая память]") for f in p.get("facts") or []):
        t = t.replace("без вопросов в конце", "в конце — один тёплый вопрос, как прошло (из «Заботливой памяти»)")
    return t


def _prompt(p, brief_context=""):
    if p["kind"] == "day":
        return ((brief_context + "\n\n" if brief_context else "") + "\n".join(p["facts"]) +
                f"\n\n[Пользователь вернулся к компьютеру — первый раз за день, не было {p['gone']}] Поздоровайся первым (в своём роде), "
                "по имени, если знаешь, и коротко скажи главное на сегодня из этих данных: погода (если есть), встречи и дела, "
                "что ждёт от сотрудников и клиентов, важные письма от людей, что готово. Не всё подряд — самое нужное. "
                "2–5 коротких предложений, живо и тепло, без списков, без вопросов в конце, без инструментов.")
    if p["kind"] == "eve":
        return ("\n".join(p["facts"]) +
                f"\n\n[Вечер, пользователь вернулся к компьютеру, не было {p['gone']}] Подведи итог дня: скажи, сколько дел он "
                "сегодня сделал, похвали тепло и конкретно (назови одно-два дела своими словами); если есть другие новости отсюда — "
                "одной фразой. 2–3 коротких предложения, без списков, без вопросов в конце, без инструментов.")
    return ("\n".join(p["facts"]) +
            f"\n\n[Пользователь вернулся к компьютеру, не было {p['gone']}] Коротко поприветствуй его и скажи главное из "
            "этого — 1–2 коротких предложения, живо, без списков и без вопросов в конце, без инструментов. Названия задач "
            "передавай своими словами, без путей и ссылок.")
