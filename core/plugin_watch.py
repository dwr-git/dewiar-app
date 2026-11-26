"""События плагинов на «Пульте» (26.11, владелец про «Jira команды»: «события Лира может показывать в своём Пульте и если
что-то важное, даже произносить… Кто в какой доске что добавил, закрыл»).

Плагин объявляет в plugin.json "watch": {"tool": "jira_watch", "every": 5}. Пока Dewiar запущен, ядро само, без модели,
раз в every минут зовёт это действие у установленного плагина; оно отвечает {"events": [{"id", "ts", "t", "important"}]} —
что случилось с прошлого раза. События ложатся на круг «Пульта» (сутки вокруг «сейчас») точками с именем плагина и
открывают его страницу; важные Лира говорит сама, если в настройках плагина включено «Говорить о важном» (say_important).
Не установлен, не настроен, ошибка — тихо: следующая попытка по расписанию. Ничего не хранит на диске: после перезапуска
плагин сам знает, что уже отдавал (у Jira — отметка в своём учёте)."""
import logging
import threading
import time

log = logging.getLogger("dewiar.plugwatch")

KEEP_SEC = 12 * 3600          # на круге «Пульта» — 12 часов назад
MAX_KEEP = 80                 # событий одного плагина в памяти
MAX_SAY = 2                   # важных вслух за раз; остальные — числом
FIRST_DELAY = 30              # после запуска — дать подняться серверам плагинов


class Watch:
    """plugins — core/plugins.Plugins, call(pid, tool, args) -> данные ответа (dict), announce(text) — сказать самой."""

    def __init__(self, plugins, call, announce=None, on_new=None):
        self.P, self.call, self.announce, self.on_new = plugins, call, announce, on_new
        self.events = {}
        self.seen = {}
        self.next = {}
        self._stop = threading.Event()
        self._t = None

    def start(self):
        if self._t is None:
            self._t = threading.Thread(target=self._loop, name="plugin-watch", daemon=True)
            self._t.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        if self._stop.wait(FIRST_DELAY):
            return
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001 — фон не должен падать
                log.debug("события плагинов", exc_info=True)
            self._stop.wait(30)

    def tick(self, now=None):
        """Позвать тех, кому пора. -> сколько новых событий."""
        now = now or time.time()
        n = 0
        for p in self.P.installed():
            w = p.get("watch")
            if not w or now < self.next.get(p["id"], 0):
                continue
            self.next[p["id"]] = now + w["every"] * 60
            try:
                r = self.call(p["id"], w["tool"], {})
            except Exception as e:  # noqa: BLE001 — не настроен, сервер не поднялся, сеть
                log.debug("плагин %s: события не получены: %s", p["id"], e)
                continue
            n += self.take(p, r, now)
        return n

    def take(self, p, r, now=None):
        """Ответ действия -> новые события в память; важные — вслух (если включено). -> сколько новых."""
        now = now or time.time()
        evs = r.get("events") if isinstance(r, dict) else None
        if not isinstance(evs, list):
            return 0
        pid = p["id"]
        seen = self.seen.setdefault(pid, {})
        new = []
        for e in evs[:60]:
            if not isinstance(e, dict) or not str(e.get("t") or "").strip():
                continue
            key = str(e.get("id") or f"{e.get('ts')}|{e.get('t')}")[:160]
            if key in seen:
                continue
            seen[key] = now
            try:
                ts = int(e.get("ts") or now)
            except (TypeError, ValueError):
                ts = int(now)
            new.append({"k": "plugin", "ts": ts, "t": " ".join(str(e["t"]).split())[:220], "src": p["name"],
                        "go": "plg:" + pid, "imp": bool(e.get("important"))})
        if len(seen) > 2000:                              # память об отданном — не бесконечная
            for k in sorted(seen, key=seen.get)[:1000]:
                seen.pop(k, None)
        if not new:
            return 0
        keep = [x for x in self.events.get(pid, []) + new if now - x["ts"] <= KEEP_SEC]
        self.events[pid] = sorted(keep, key=lambda x: x["ts"])[-MAX_KEEP:]
        log.info("🧩 %s: событий %d (важных %d)", p["name"], len(new), sum(x["imp"] for x in new))
        if self.on_new:                                   # открытый «Пульт» перерисуется сразу, а не через минуту
            try:
                self.on_new(pid, new)
            except Exception:  # noqa: BLE001
                log.debug("события плагинов: оповещение", exc_info=True)
        imp = [x for x in new if x["imp"]]
        if imp and self.announce and _on(self.P.values(pid).get("say_important")):
            text = "; ".join(x["t"] for x in imp[:MAX_SAY])
            more = len(imp) - MAX_SAY
            self.announce(f"{p['name']}: {text}." + (f" И ещё {more} — на «Пульте»." if more > 0 else ""))
        return len(new)

    def day(self, now=None):
        """События всех плагинов за 12 часов — для круга «Пульта» (commands_tasks._pult_data)."""
        now = now or time.time()
        return [dict(x) for xs in self.events.values() for x in xs if abs(x["ts"] - now) <= KEEP_SEC]


def _on(v):
    return v is True or str(v).strip().lower() in ("true", "1", "да", "yes", "on")
