"""«Радар» в движке (docs/RADAR.md): сеть, модель, расписание, команды студии и инструмент модели insight_ask.
Чистая часть — core/insight.py. Один объект на движок: eng.insight (Radar), поток — eng.insight.loop()."""
import logging
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import insight as I

log = logging.getLogger("dewiar.engine")

DEFAULTS = {"on": True, "mission": "", "daily_max": I.DAILY_MAX, "urgent_min": I.URGENT_MIN, "mode": "always",
            "night": [1, 7], "tick_day": 20, "tick_night": 5, "per_tick_day": 5, "per_tick_night": 25, "day_long": False,
            "every_day": 180, "every_night": 60, "brief_hour": 7}


class Radar:
    def __init__(self, eng, root=None):
        from settings import STATE_DIR
        self.e = eng
        self.st = I.Store(root or STATE_DIR / "insight")
        self.lock = threading.Lock()                 # один такт за раз
        self.running = None                          # что делается сейчас ({k, x} — студия переводит)
        self.fetch = self._http                     # подменяют проверки
        self._reads = {}                            # «читалка»: прочитанные целиком — до 30 последних

    # ---------- настройки ----------
    def conf(self):
        c = dict(DEFAULTS)
        c.update(self.e.s.get("insight") or {})
        return c

    def set_conf(self, patch):
        allowed = {k: v for k, v in (patch or {}).items() if k in DEFAULTS}
        self.e.s.update({"insight": allowed})
        return self.conf()

    def lang(self):
        try:
            import i18n
            return i18n.resolve((self.e.s.get("ui") or {}).get("lang"))
        except Exception:  # noqa: BLE001
            return "ru"

    def night(self, now=None):
        h = (now or datetime.now()).hour
        a, b = (self.conf().get("night") or [1, 7])[:2]
        return a <= h < b if a < b else (h >= a or h < b)

    # ---------- сеть ----------
    def _http(self, url):
        import httpx
        try:
            with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=True, headers=I.UA) as c:
                r = c.get(url)
                r.raise_for_status()
                return r.text[:3_000_000]
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            # №690: у провайдера не открывается t.me (timed out) — та же страница через сервер Dewiar, если есть вход
            html = self._via_dewiar(url)
            if html is None:
                raise
            log.info("📡 Радар: %s — напрямую не открылся (%s), прочитан через сервер Dewiar", url, type(e).__name__)
            return html

    def _cloud(self, params):
        """GET к cloud.php с входом человека -> JSON или None (нет входа, запасной путь выключен, сервер не ответил)."""
        import httpx
        if self.e.s.get("net", "web_via") is False:
            return None
        try:
            token, _, url = self.e.credentials()
        except Exception:  # noqa: BLE001
            return None
        if not token or not url:
            return None
        try:
            r = httpx.get(url, params=params, headers={"Authorization": "Bearer " + token}, timeout=40)
            d = r.json()
        except Exception:  # noqa: BLE001
            return None
        return d if r.status_code == 200 else {"_err": (d.get("error") or {}).get("code") or str(r.status_code)}

    def _via_dewiar(self, url):
        d = self._cloud({"p": "/fetch", "url": url, "raw": "1"})
        return d.get("html") if d and d.get("html") else None

    def read_vk(self, src):
        """Сообщество VK: читаем только открытую мобильную страницу (m.vk.com — посты в самой разметке). Ключей VK и
        запросов к VK через сервер Dewiar нет (владелец 13.11: «держаться от этого сервиса подальше»). Пусто — VK прячет
        записи от тех, кто не вошёл: понятное объяснение. -> материалы или ValueError("@vk_…")."""
        name = I.vk_name(src.get("url") or "")
        if not name:
            raise ValueError("@vk_link")
        found = I.parse_vk(self.fetch(f"https://m.vk.com/{name}"), name)
        if not found:
            raise ValueError("@vk_need")
        return found

    def crawl_source(self, src):
        """Один источник -> сколько новых материалов. Лента — сразу; сайт и YouTube — найти ленту на странице, нет ленты —
        ссылки на свои статьи; одна статья — она сама."""
        d = I.detect(src.get("url") or "")
        if d and d.get("bad"):
            raise ValueError("@" + d["bad"])                     # код — студия покажет понятное объяснение
        if d and int(src.get("v") or 0) < I.DETECT_V:            # добавлен старым detect(): тип и лента — заново
            fix = {"v": I.DETECT_V}
            if d["kind"] != src.get("kind") or d.get("feed"):
                fix.update(kind=d["kind"], feed=d.get("feed") or src.get("feed") or "")
                if src.get("name") == urlparse(src.get("url") or "").netloc.lower().removeprefix("www.").removeprefix("m."):
                    fix["name"] = d["name"]
            self.st.update_source(src["id"], **fix)
            src = dict(src, **fix)
        kind, feed = src.get("kind"), src.get("feed") or ""
        found = []
        if kind == "telegram":
            found = I.parse_telegram(self.fetch(feed), src.get("name", ""))
        elif kind == "vk":
            found = self.read_vk(src)
        elif kind == "article":
            if src.get("last"):
                return 0                                         # одна статья читается один раз
            title, text = I.article_text(self.fetch(src["url"]))
            found = [{"title": title or src["url"], "url": src["url"], "ts": int(time.time()), "text": text}]
        else:
            if not feed:
                page = self.fetch(src["url"])
                feed = I.find_feed(page, src["url"])
                if feed:
                    self.st.update_source(src["id"], feed=feed)
                else:
                    found = I.parse_page_links(page, src["url"])
            if feed:
                text = self.fetch(feed)
                found = I.parse_feed(text, feed)
                if not found and I.looks_html(text):              # «лента» оказалась страницей — ищем ленту в ней
                    alt = I.find_feed(text, feed)
                    if alt and alt != feed:
                        self.st.update_source(src["id"], feed=alt)
                        found = I.parse_feed(self.fetch(alt), alt)
                    else:
                        found = I.parse_page_links(text, src["url"])
        week = [x for x in found if (x.get("ts") or time.time()) >= time.time() - 8 * 86400]
        n = self.st.add_items(src, week[:40])
        self.st.update_source(src["id"], found=len(found))     # 0 — студия скажет «ничего не нашлось»
        return n

    def crawl(self, force=False):
        night = self.night()
        every = (self.conf()["every_night"] if night else self.conf()["every_day"]) * 60
        new = 0
        for s in self.st.sources():
            if not s.get("on", True) or (not force and time.time() - float(s.get("last") or 0) < every):
                continue
            self.running = {"k": "read", "x": s.get("name") or ""}
            try:
                n = self.crawl_source(s)
                new += n
                self.st.update_source(s["id"], last=int(time.time()), err="", last_new=n)
            except Exception as e:  # noqa: BLE001
                self.st.update_source(s["id"], last=int(time.time()), err=str(e)[:160])
                log.info("📡 Радар: %s не прочитался: %s", s.get("name"), e)
        return new

    # ---------- модель ----------
    def _ask(self, system, user, max_tokens=700):
        from llm import stream_chat
        prof = self.e.s.active_llm()
        if not prof:
            raise RuntimeError("нет модели — подключите «Мозг»")
        return "".join(stream_chat(dict(prof, max_tokens=max_tokens, disable_thinking=True), system, [{"role": "user", "content": user}]))

    def used_today(self):
        day = datetime.now().strftime("%Y-%m-%d")
        return int((self.st.load("log", {}).get("days") or {}).get(day, 0))

    def _count(self, n):
        lg = self.st.load("log", {})
        day = datetime.now().strftime("%Y-%m-%d")
        days = lg.get("days") or {}
        days[day] = int(days.get(day, 0)) + n
        lg["days"] = dict(sorted(days.items())[-30:])
        self.st.save("log", lg)

    def analyze(self, limit):
        left = max(0, int(self.conf()["daily_max"]) - self.used_today())
        n = 0
        for x in self.st.queue(min(limit, left), long_ok=self.night() or self.conf().get("day_long")):
            self.running = {"k": "analyze", "x": x["title"][:50]}
            try:
                a = I.parse_analysis(self._ask(*I.analyze_prompt(self.conf()["mission"], x, self.lang())))
            except Exception as e:  # noqa: BLE001
                log.info("📡 Радар: разбор не удался: %s", e)
                if "модел" in str(e):
                    break
                a = None
            self.st.set_analysis(x["id"], a, fail="" if a else "модель не ответила по форме")
            n += 1
        if n:
            self._count(n)
        return n

    def analyzed(self, hours=None):
        now = time.time()
        return [x for x in self.st.items() if x.get("a") and (hours is None or (x.get("ts") or x.get("seen") or 0) >= now - hours * 3600)]

    def make_brief(self, force=False):
        b = self.st.load("brief", {})
        today = datetime.now().strftime("%Y-%m-%d")
        if not force and b.get("day") == today:
            return b
        items = self.analyzed(30)
        if len(items) < 3:
            return b
        self.running = {"k": "brief", "x": ""}
        tr = I.trends(self.analyzed(), time.time())
        nb = I.parse_brief(self._ask(*I.brief_prompt(self.conf()["mission"], items, tr, self.lang()), max_tokens=1400), items)
        if nb:
            nb["day"] = today
            self.st.save("brief", nb)
            self.e.emit("insight", what="brief")
            return nb
        return b

    def evolve(self):
        mind, _ = I.clean_hyps(self.st.load("mind", {}))      # «прогнозы в прошлое» до 0.92.2 — прочь
        items = self.analyzed(36)
        if len(items) < 3:
            return mind
        self.running = {"k": "evolve", "x": ""}
        nm = I.apply_evolve(mind, self._ask(*I.evolve_prompt(self.conf()["mission"], mind, items, self.lang()), max_tokens=1800), items)
        if nm:
            nm["day"] = datetime.now().strftime("%Y-%m-%d")
            self.st.save("mind", nm)
            return nm
        return mind

    def urgent(self):
        lg = self.st.load("log", {})
        if time.time() - float(lg.get("urgent_at") or 0) < I.URGENT_GAP:
            return []
        sent = set(lg.get("urgent_sent") or [])
        u = I.urgent(self.analyzed(8), I.trends(self.analyzed(), time.time()), sent, min_signal=float(self.conf()["urgent_min"]))
        if not u:
            return []
        top = u[0]
        en = self.lang().startswith("en")
        if top["kind"] == "item":
            title = ("⚡ Radar: important" if en else "⚡ Радар: важное")
            text = f"{top['title']} — {top['text']}"
        else:
            title = ("⚡ Radar: topic surging" if en else "⚡ Радар: тема резко растёт")
            text = (f"«{top['title']}»: {top['day']} materials in 24h" if en else f"«{top['title']}»: {top['day']} материалов за сутки")
        quiet = self.night()
        try:
            self.e.push(title, text[:400], quiet=quiet, open="insight:" + top["id"] if top["kind"] == "item" else "insight", head=str(top["title"])[:200],
                        body=str(top.get("text") or (f"{top['day']} materials in 24h" if en else f"{top['day']} материалов за сутки"))[:400])
        except Exception:  # noqa: BLE001
            log.debug("радар: весточка", exc_info=True)
        lg["urgent_at"] = time.time()
        lg["urgent_sent"] = (list(sent) + [x["id"] for x in u])[-300:]
        self.st.save("log", lg)
        return u

    # ---------- такт ----------
    def tick(self, manual=False):
        if not self.lock.acquire(blocking=False):
            return {"busy": True}
        t0, night = time.time(), self.night()
        prof = "manual" if manual else ("night" if night else "day")
        rec = {"at": int(t0), "profile": prof, "new": 0, "done": 0}
        try:
            c = self.conf()
            rec["new"] = self.crawl(force=manual)
            rec["done"] = self.analyze(c["per_tick_night"] if night or manual else c["per_tick_day"])
            if datetime.now().hour >= int(c.get("brief_hour") or 7) or manual:
                self.make_brief()
            if night and self.st.load("mind", {}).get("day") != datetime.now().strftime("%Y-%m-%d"):
                self.evolve()
            self.urgent()
        except Exception as e:  # noqa: BLE001
            rec["err"] = str(e)[:160]
            log.info("📡 Радар: такт не удался: %s", e)
        finally:
            self.running = None
            rec["dur"] = round(time.time() - t0, 1)
            lg = self.st.load("log", {})
            lg["ticks"] = ([rec] + list(lg.get("ticks") or []))[:30]
            lg["last_tick"] = int(t0)
            self.st.save("log", lg)
            self.lock.release()
            if rec["new"] or rec["done"]:
                self.e.emit("insight", what="tick")
        return rec

    def loop(self, stopping):
        if stopping.wait(120):
            return
        while not stopping.is_set():
            c = self.conf()
            gap = (c["tick_night"] if self.night() else c["tick_day"]) * 60
            mode = c.get("mode") or "always"
            run = c.get("on", True) and self.st.sources() and mode != "pause" and (mode == "always" or self.night())
            if run and time.time() - float(self.st.load("log", {}).get("last_tick") or 0) >= gap:
                self.tick()
            if stopping.wait(60):
                return

    # ---------- для студии ----------
    def stats(self):
        items = self.st.items()
        src = self.st.sources()
        lg = self.st.load("log", {})
        day = [x for x in items if x.get("a") and (x.get("ts") or x.get("seen") or 0) >= time.time() - 86400]
        return {"sources": len([s for s in src if s.get("on", True)]), "sources_all": len(src), "day": len(day),
                "queue": len([x for x in items if not x.get("a") and not x.get("fail")]), "last_tick": lg.get("last_tick") or 0,
                "used_today": self.used_today(), "daily_max": self.conf()["daily_max"], "running": self.running,
                "night": self.conf()["night"], "mode": self.conf()["mode"], "total": len(items)}

    def sources_view(self):
        items = self.st.items()
        week = time.time() - 7 * 86400
        out = []
        for s in self.st.sources():
            mine = [x for x in items if x.get("src") == s["id"] and x.get("a") and (x.get("seen") or 0) >= week]
            avg = round(sum(x["a"]["signal"] for x in mine) / len(mine), 1) if mine else None
            out.append(dict(s, week=len(mine), avg=avg))
        return out

    def item_view(self, x):
        a = x.get("a") or {}
        return {"id": x["id"], "title": x["title"], "url": x.get("url"), "src": x.get("src_name"), "kind": x.get("kind"), "ts": x.get("ts") or x.get("seen"),
                "summary": a.get("summary", ""), "why": a.get("why", ""), "type": a.get("type", ""), "tags": a.get("tags") or [],
                "entities": a.get("entities") or [], "signal": a.get("signal"), "fb": x.get("fb", 0), "watch": bool(x.get("watch")),
                "fail": x.get("fail", "")}

    def feed(self, q="", typ="", min_s=0, sort="new", watch=False, limit=150):
        rows = []
        words = [w for w in (q or "").lower().split() if len(w) > 1]
        for x in self.st.items():
            a = x.get("a")
            if not a:
                continue
            if typ and a.get("type") != typ or (a.get("signal") or 0) < float(min_s or 0) or (watch and not x.get("watch")):
                continue
            if words and not all(w in (x["title"] + " " + a.get("summary", "") + " " + " ".join(a.get("tags") or [])).lower() for w in words):
                continue
            rows.append(x)
        key = (lambda x: -(x["a"]["signal"])) if sort == "signal" else (lambda x: -(x.get("ts") or x.get("seen") or 0))
        return [self.item_view(x) for x in sorted(rows, key=key)[:limit]]

    def pulse(self):
        items = self.analyzed()
        tr = I.trends(items, time.time())
        b = self.st.load("brief", {})
        byid = {x["id"]: x for x in items}
        main = [dict(self.item_view(byid[m["id"]]), why_brief=m["why"]) for m in b.get("main") or [] if m["id"] in byid]
        return {"stats": self.stats(), "brief": dict(b, main=main) if b else None, "field": I.field(items, time.time()),
                "trends": tr[:10], "week": len([x for x in items if (x.get("ts") or 0) >= time.time() - 7 * 86400]),
                "mission": self.conf()["mission"]}

    def mind_view(self):
        m, gone = I.clean_hyps(self.st.load("mind", {}))
        if gone:                                         # 12.11: гипотезы со сроком в прошлом — сохранить уже без них
            self.st.save("mind", m)
        byid = {x["id"]: x for x in self.analyzed()}
        th = [dict(t, refs=[{"id": r, "title": byid[r]["title"], "url": byid[r].get("url")} for r in t.get("refs") or [] if r in byid])
              for t in m.get("theses") or []]
        watch = [self.item_view(x) for x in self.st.items() if x.get("watch")][:20]
        return {"mission": self.conf()["mission"], "v": m.get("v", 0), "theses": th, "hyps": m.get("hyps") or [],
                "diary": list(reversed(m.get("diary") or []))[:20], "accuracy": I.accuracy(m), "watch": watch}

    def read(self, iid):
        """«Читалка» (владелец 12.11: «статья интересная, а не сразу удаётся её найти»): материал и его текст целиком —
        страница читается сейчас (полный текст), не прочиталась — что сохранено при обходе. Пост Telegram — он сам."""
        x = next((y for y in self.st.items() if y["id"] == iid), None)
        if not x:
            raise ValueError("материала уже нет в Радаре")
        cached = self._reads.get(iid)
        if cached:
            return cached
        text, full = x.get("text") or "", False
        if x.get("kind") != "telegram" and x.get("url"):
            try:
                _, t = I.article_text(self.fetch(x["url"]), I.READ_MAX)
                if len(t) > len(text):
                    text, full = t, True
            except Exception as e:  # noqa: BLE001
                log.info("📡 Радар: читалка — страница не открылась: %s", e)
        elif x.get("kind") == "telegram":
            full = True
        out = dict(self.item_view(x), text=text, full=full)
        if full:
            self._reads[iid] = out
            if len(self._reads) > 30:
                self._reads.pop(next(iter(self._reads)))
        return out

    def one(self, url):
        """«Разобрать одну ссылку» — прочитать и разобрать сейчас."""
        d = I.detect(url)
        if not d:
            raise ValueError("это не похоже на ссылку")
        title, text = I.article_text(self.fetch(d["url"]))
        src = {"id": "one", "name": d.get("name") or "ссылка", "kind": "article"}
        self.st.add_items(src, [{"title": title or d["url"], "url": d["url"], "ts": int(time.time()), "text": text}])
        x = next((y for y in self.st.items() if I.norm_link(y.get("url")) == I.norm_link(d["url"])), None)
        if x and not x.get("a"):
            a = I.parse_analysis(self._ask(*I.analyze_prompt(self.conf()["mission"], x, self.lang())))
            self.st.set_analysis(x["id"], a, fail="" if a else "модель не ответила по форме")
            self._count(1)
            x = next((y for y in self.st.items() if y["id"] == x["id"]), x)
        return self.item_view(x) if x else None


def radar(eng):
    r = getattr(eng, "insight", None)
    if r is None:
        r = eng.insight = Radar(eng)
    return r


def _bg(fn, *a):
    threading.Thread(target=fn, args=a, daemon=True).start()


def command(eng, cmd, a):
    """Команды студии «Радар» (insight_*). -> данные для окна; ValueError — понятная ошибка."""
    r = radar(eng)
    if cmd == "insight_pulse":
        return r.pulse()
    if cmd == "insight_feed":
        return {"items": r.feed(str(a.get("q") or ""), str(a.get("type") or ""), a.get("min") or 0, str(a.get("sort") or "new"),
                                bool(a.get("watch"))), "stats": r.stats()}
    if cmd == "insight_trends":
        return {"trends": I.trends(r.analyzed(), time.time())[:60], "stats": r.stats()}
    if cmd == "insight_sources":
        return {"sources": r.sources_view(), "stats": r.stats()}
    if cmd == "insight_add":
        added, bad, why = r.st.add_sources(str(a.get("text") or ""))
        if added:
            _bg(r.tick, True)
        return {"added": [s["name"] for s in added], "bad": bad, "why": why, "sources": r.sources_view()}
    if cmd == "insight_src":
        sid = str(a.get("id") or "")
        if a.get("del"):
            r.st.remove_source(sid)
        elif "on" in a:
            r.st.update_source(sid, on=bool(a["on"]))
        elif a.get("crawl"):
            src = next((s for s in r.st.sources() if s["id"] == sid), None)
            if not src:
                raise ValueError("нет такого источника")
            try:
                n = r.crawl_source(src)
                r.st.update_source(sid, last=int(time.time()), err="", last_new=n)
            except Exception as e:  # noqa: BLE001
                r.st.update_source(sid, last=int(time.time()), err=str(e)[:160])
                if str(e).startswith("@"):
                    return {"sources": r.sources_view(), "err": str(e)}
                raise ValueError(f"не прочитался: {str(e)[:160]}") from e
            s = next((x for x in r.st.sources() if x["id"] == sid), {})
            return {"sources": r.sources_view(), "found": int(s.get("found") or 0), "new": n}
        return {"sources": r.sources_view()}
    if cmd == "insight_question":
        return question(eng, a.get("q"))
    if cmd == "insight_read":
        return {"item": r.read(str(a.get("id") or ""))}
    if cmd == "insight_one":
        return {"item": r.one(str(a.get("url") or "").strip())}
    if cmd == "insight_refresh":
        _bg(r.tick, True)
        return {"started": True}
    if cmd == "insight_mind":
        return r.mind_view()
    if cmd == "insight_mission":
        r.set_conf({"mission": str(a.get("text") or "").strip()[:600]})
        return r.mind_view()
    if cmd == "insight_evolve":
        _bg(r.evolve)
        return {"started": True}
    if cmd == "insight_galaxy":
        return I.galaxy(r.analyzed(24 * 30))
    if cmd == "insight_mark":
        iid = str(a.get("id") or "")
        kw = {}
        if "fb" in a:
            kw["fb"] = max(-1, min(1, int(a["fb"])))
        if "watch" in a:
            kw["watch"] = bool(a["watch"])
        r.st.mark(iid, **kw)
        return {"ok": True}
    if cmd == "insight_conf":
        return {"conf": r.set_conf(a.get("conf") or {}), "log": (r.st.load("log", {}).get("ticks") or [])[:15], "stats": r.stats()}
    if cmd == "insight_control":
        return {"conf": r.conf(), "log": (r.st.load("log", {}).get("ticks") or [])[:15], "stats": r.stats()}
    if cmd == "insight_brief":
        _bg(r.make_brief, True)
        return {"started": True}
    raise ValueError("неизвестная команда радара")


def question(eng, q):
    """«Спросите Лиру о теме» в самом «Радаре»: ответ по разобранному (по словам вопроса, иначе — самое сильное) со ссылками."""
    r = radar(eng)
    q = str(q or "").strip()[:500]
    if not q:
        raise ValueError("пустой вопрос")
    ctx = ask_tool(eng, q)
    if ctx.get("empty"):
        return {"text": ctx["empty"], "refs": []}
    if not ctx["items"]:                               # слов вопроса в материалах нет — отвечаем по самому сильному
        ctx = ask_tool(eng, "")
    if not ctx["items"] and not ctx.get("brief"):
        raise ValueError("Радар ещё ничего не разобрал — загляните после первого обхода")
    raw = r._ask(*I.question_prompt(q, ctx, r.conf()["mission"], r.lang()), max_tokens=700)
    out = I.parse_answer(raw, ctx)
    if not out["text"]:
        raise ValueError("модель не ответила — попробуйте ещё раз")
    return out


def ask_tool(eng, query=""):
    """Инструмент модели insight_ask: что важного в нише, почему растёт тема, что писали про X."""
    r = radar(eng)
    items = r.analyzed(24 * 14)
    if not r.st.sources():
        return {"empty": "Радар ещё не настроен: студия → «Работа» → «Радар» → «Источники» — добавьте сайты и каналы своей темы."}
    return I.ask_context(items, I.trends(r.analyzed(), time.time()), r.st.load("brief", {}), r.st.load("mind", {}), query)
