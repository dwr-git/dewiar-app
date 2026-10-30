"""Моя музыка голосом и в студии (27.10): «поставь мою музыку», «включи что-нибудь спокойное из моей музыки»,
«поставь Кино» (если Кино есть в папке), «что играет?», «эту — в любимое», «дальше», «предыдущую». Треки играет
радио-проигрыватель (self.radio), перед треком — пара слов ведущего (mymusic.intro) поверх начала песни: музыка в
это время приглушена, как у радио. Говорит не перед каждым треком (music.dj_every), можно выключить (music.dj_talk).
Библиотека и очередь — mymusic.Library / mymusic.Dj; настройки — music.folder, music.favs, music.dj_talk, music.dj_every."""

import logging
import queue
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.engine")
RADIO_HOST_S = 25 * 60                                     # ведущий на радио — раз в 25 минут

MINE_RX = re.compile(r"\b(?:мо[юяиёе]|сво[юяиёе])\s+(?:музык|песн|трек|подборк|плейлист|папк|любим)\w*|из\s+(?:мо|сво)ей\s+"
                     r"(?:папк|музык|коллекц|библиотек)\w*|из\s+папки|мою\s+коллекци\w*|моя\s+музык\w*", re.I)
VERB_RX = re.compile(r"\b(?:включи|поставь|запусти|вруби|играй|сыграй|давай|хочу|поиграй|заведи)", re.I)
NOW_RX = re.compile(r"^\W*(?:а\s+)?(?:что\s+(?:это\s+|сейчас\s+|у\s+нас\s+)?(?:сейчас\s+)?(?:игра\w*|звуч\w*)|что\s+за\s+(?:песн\w*|трек\w*|музык\w*)"
                    r"|кто\s+(?:это\s+)?(?:поёт|поет|исполня\w*)|как\s+называ\w+\s+(?:эта\s+)?(?:песн\w*|трек))", re.I)
FAV_RX = re.compile(r"(?:в|во)\s+(?:любим|избранн)|(?:эта|эту|этот)\s+(?:песн\w*|трек\w*)?\s*(?:мне\s+)?нрав|запомни\s+(?:эту|этот)\s+(?:песн|трек)"
                    r"|отличн\w+\s+(?:песн|трек)|люблю\s+(?:эту|этот)", re.I)
UNFAV_RX = re.compile(r"(?:убери|удали)\s+(?:эту|этот)?\s*(?:песн\w*|трек\w*)?\s*из\s+любим", re.I)
NEXT_RX = re.compile(r"^\W*(?:\w+\W+)?(?:дальше|следующ\w*|другую|другой|переключи|пропусти|следующую)\b", re.I)
COMMON = {"кино", "свет", "радио", "новости", "погода", "телевизор", "тв", "музыка", "звук", "видео", "камера", "фонарик",
          "будильник", "таймер", "игра", "игры", "сон", "утро", "вечер", "любовь", "весна", "лето", "осень", "зима"}
# 0.74 «Ведущий»: включить и выключить голосом
HOST_ON_RX = re.compile(r"(?:веди|вести|ведите)\s+(?:эфир|программу)|будь\s+(?:моим\s+|нашим\s+)?(?:ведущ|диджее?м|dj)\w*"
                        r"|(?:включи|верни)\s+(?:режим\s+)?(?:ведущ\w*|диджея|dj)|говори\s+между\s+(?:песн|трек)\w*", re.I)
HOST_OFF_RX = re.compile(r"хватит\s+(?:болтать|трепаться|комментировать)|не\s+болтай|меньше\s+(?:болтай|говори)|помолчи\s+между"
                         r"|без\s+(?:комментариев|ведущего|болтовни|слов)|(?:выключи|убери)\s+(?:режим\s+)?(?:ведущ\w*|диджея|dj)"
                         r"|не\s+(?:говори|разговаривай)\s+между|только\s+музык\w*\s+без\s+слов", re.I)
PREV_RX = re.compile(r"^\W*(?:\w+\W+)?(?:предыдущ\w*|назад|прошл\w+\s+(?:песн|трек)|верни\s+(?:прошл|предыдущ))", re.I)


class MyMusicMixin:
    def _mine_init(self, state_dir):
        from mymusic import Covers, Dj, Library
        self.mylib = Library(lambda: self.s.get("music", "folder") or "", Path(state_dir) / "mymusic.json")
        self.dj = Dj(self.mylib, lambda: self.s.get("music", "favs") or [])
        self.dj.covers = Covers(Path(state_dir) / "covers")
        # ход чтения папки — в студию полоской (№361); событие то же, что «папка прочитана»
        self.mylib.on_progress = lambda p: self.emit("mymusic", **dict(self.mine_status(), busy=True, progress=p))
        self._dj_track_n = 0
        self._dj_last = {}                                 # когда что говорил ведущий: {вид: unix, "tasks_said": [...]}
        self._dj_facts = {"weather": "", "weather_t": 0.0, "mail": 0, "mail_t": 0.0, "mail_seen": None}
        self._dj_fetching = False
        self.radio.on_end = self._mine_ended
        threading.Thread(target=self._dj_radio_loop, name="dj-radio", daemon=True).start()
        if self.s.get("music", "folder"):
            threading.Thread(target=self.mylib.scan, name="mymusic", daemon=True).start()

    def _mine_playing(self):
        st = self.radio.station or self.radio.paused or {}
        return bool(st.get("_mine"))

    def _mine_play(self, t, say="", said=""):
        """Запустить трек; say — фраза ведущего (с said — как ответ на просьбу, без — сама, поверх начала песни)."""
        try:
            self.radio.play(self.dj.station(t))
        except Exception as e:  # noqa: BLE001
            log.info("Моя музыка: %s", e)
            if said:
                self._say_quick(f"Не получилось включить: {e}", said)
            return False
        self.emit("radio", **self.radio.status())
        if say and said:
            self._say_quick(say, said)
        elif say:
            self._dj_say(say)
        return True

    def _dj_say(self, text):
        """Ведущий говорит сам: только если ассистент сейчас не занят разговором; без сигнала и без ожидания ответа."""
        if getattr(self, "server", False) or getattr(getattr(self, "prompter", None), "on", False):
            return
        if self.turn is not None or self.state in ("thinking", "speaking", "listening"):
            return
        text = self._g(text)
        from engine_base import Turn

        def run():
            with self._turn_lock:
                if self.turn is not None:
                    return
                self.turn_n += 1
                turn = Turn(self.turn_n)
                self.turn = turn
            q = queue.Queue()
            q.put(text)
            q.put(None)
            self.note(text)
            try:
                self._speak_worker(turn, q)
            finally:
                with self._turn_lock:
                    if self.turn is turn:
                        self.turn = None
                        self.set_state("idle")
        threading.Thread(target=run, name="dj-say", daemon=True).start()

    def _mine_ended(self, station):
        """Трек доиграл сам — следующий; ведущий говорит раз в dj_every треков."""
        if not station.get("_mine") or self.stopping.is_set():
            return
        prev = station.get("_track")
        cur = self.dj.current()
        if cur is not prev and cur is not None and prev is not None and cur.get("path") != prev.get("path"):
            return                                       # уже включили другое
        t = self.dj.next()
        if not t:
            return
        self._dj_track_n += 1
        every = max(1, int(self.s.get("music", "dj_every") or 3))
        talk = self.s.get("music", "dj_talk") is not False and self._dj_track_n % every == 0
        self._mine_play(t, self._dj_line(t, prev) if talk else "")

    def _mine_start(self, tracks, what, said, lead=""):
        from mymusic import intro
        if not tracks:
            return False
        t = self.dj.start(tracks, what)
        self._dj_track_n = 0
        w = {"": "музыку из вашей папки", "любимое": "ваше любимое"}.get(what, f"«{what}» из вашей папки")
        talk = self.s.get("music", "dj_talk") is not False
        msg = lead + (intro(t, first=True, what=w) if talk else f"Включаю {w}.")
        log.info("🎵 Моя музыка: %s — %d треков", what or "вся папка", len(tracks))
        return self._mine_play(t, msg, said)

    def _mine_cmd(self, text):
        """Фразы про свою музыку. -> True, если ответили (иначе дальше — радио и модель)."""
        low = (text or "").lower().replace("ё", "е")
        playing = self._mine_playing()
        lib = getattr(self, "mylib", None)
        if lib is None:
            return False
        if self._dj_host_cmd(text, low, playing, lib):
            return True
        if playing and NOW_RX.search(low):
            self._say_quick(self.dj.now_text() or "Сейчас ничего не играет.", text)
            return True
        if playing and UNFAV_RX.search(low):
            return self._mine_fav(text, False)
        if playing and FAV_RX.search(low) and not VERB_RX.search(low):
            return self._mine_fav(text, True)
        if playing and NEXT_RX.search(low) and not MINE_RX.search(low) and len(low.split()) <= 5:
            from mymusic import intro
            prev = self.dj.current()
            t = self.dj.next()
            say = (self._dj_line(t, prev, extra=False) if self.s.get("music", "dj_talk") is not False else "") or "Следующий."
            return bool(t) and self._mine_play(t, say, text)
        if playing and PREV_RX.search(low) and len(low.split()) <= 5:
            t = self.dj.prev()
            return bool(t) and self._mine_play(t, "Возвращаю: " + __import__("mymusic").label(t) + ".", text)
        mine = bool(MINE_RX.search(low))
        if not (mine or VERB_RX.search(low)):
            return False
        if mine and not lib.root():
            self._say_quick("Папка с музыкой ещё не выбрана — откройте студию, раздел «Музыка», и укажите её. "
                            "А пока могу включить радио.", text)
            return True
        if mine and not lib.tracks:
            if lib.busy:
                self._say_quick("Ещё читаю папку с музыкой — минутку.", text)
                return True
            lib.scan()
            if not lib.tracks:
                self._say_quick(f"В папке «{lib.root()}» не нашлось музыки — mp3, flac, ogg, m4a.", text)
                return True
        if not lib.tracks:
            return False
        q = re.sub(MINE_RX, " ", low)
        q = re.sub(VERB_RX, " ", q)
        q = re.sub(r"\b(?:мне|нам|пожалуйста|что-нибудь|что-то|нибудь|какую-нибудь|музыку|музыка|песни|песню|трек|треки|"
                   r"немного|из|моей|моего|мою|мои|свою|свои|папки|коллекции|лира|патрик|ну)\b", " ", q)
        q = " ".join(w for w in re.findall(r"[\w-]+", q) if len(w) > 1)
        if re.search(r"любим|избранн", low):          # «включи моё любимое» — «моё любимое» целиком в MINE_RX
            q = "любимое"
        tracks, what = lib.match(q, self.s.get("music", "favs") or [])
        if mine:
            if not tracks and q:
                if what == "любимое":
                    self._say_quick("В любимом пока пусто. Когда понравится песня — скажите «эту в любимое».", text)
                    return True
                self._say_quick(f"В вашей папке не нашёл «{q}». Включаю всё подряд.", text)
                return self._mine_start(lib.tracks, "", "")
            return self._mine_start(tracks or lib.tracks, what, text)
        # без «моей»: только исполнитель или название, которые точно есть в папке — иначе это радио или модель
        # «включи кино» — может быть и фильм, «включи свет» — свет: исполнитель без «моей» — только если он правда
        # исполнитель папки и просьба про музыку («поставь», «сыграй», «песни…») или имя не похоже на обычное слово
        artist = what and any(what == a for a in lib.artists())
        if tracks and artist and re.match(r"^\W*(?:\w+\W+)?(?:включи|поставь|запусти|вруби|сыграй)\b", low):
            musical = re.search(r"\b(?:поставь|сыграй)\b|песн|музык|трек|альбом|групп", low)
            if musical or what.lower().replace("ё", "е") not in COMMON:
                return self._mine_start(tracks, what, text)
        return False

    def _mine_fav(self, text, on=True):
        t = self.dj.current()
        if not t:
            return False
        favs = list(self.s.get("music", "favs") or [])
        if on and t["path"] not in favs:
            favs.append(t["path"])
        elif not on and t["path"] in favs:
            favs.remove(t["path"])
        self.s.update({"music": {"favs": favs[-2000:]}})
        from mymusic import label
        self._say_quick((f"Добавил {label(t)} в любимое." if on else f"Убрал {label(t)} из любимого."), text)
        self.emit("mymusic", **self.mine_status())
        return True

    def mine_status(self):
        t = self.dj.current() if self._mine_playing() else None
        favs = set(self.s.get("music", "favs") or [])
        art = (self.radio.station or self.radio.paused or {}).get("art") if t else None
        return {"stats": self.mylib.stats(), "busy": self.mylib.busy, "folder": self.s.get("music", "folder") or "",
                "progress": dict(self.mylib.progress or {}),
                "now": dict(t, fav=t["path"] in favs, art=Path(art).as_uri() if art else "") if t else None, "what": self.dj.what if t else "",
                "paused": bool((self.radio.paused or {}).get("_mine")), "live": self._live_now(),
                "mail_on": bool(getattr(self, "mail", None) is not None and self.mail.configured())}

    def _live_now(self):
        """Играет (или на паузе) радиостанция, а не своя музыка -> {name, url, tags, logo, fav, paused} для общего плеера."""
        st = self.radio.station or self.radio.paused
        if not st or st.get("_mine") or not st.get("url"):
            return None
        mine = {x.get("url") for x in (self.s.get("radio_custom") or []) if isinstance(x, dict)}
        logos = getattr(self, "radio_logos", None)
        return {"name": st.get("name", ""), "url": st["url"], "tags": " ".join(str(st.get("tags") or "").replace(",", " ").split()[:4]),
                "logo": st.get("logo") or (logos.get(st.get("name", "")) if logos else ""), "fav": st["url"] in mine,
                "paused": not self.radio.station}

    def mine_command(self, cmd, a):
        """Команды студии «Музыка»: mm_status, mm_list, mm_play, mm_ctl {act: play|pause|next|prev|stop|vol {v}|seek {t}},
        mm_vis, mm_folder, mm_scan, mm_fav."""
        lib, favs = self.mylib, set(self.s.get("music", "favs") or [])
        if cmd == "mm_status":
            return dict(self.mine_status(), artists=lib.artists()[:12], dj_talk=self.s.get("music", "dj_talk") is not False, vis=self._mm_vis())
        if cmd == "mm_list":
            tracks, _ = lib.match(str(a.get("what") or ""), list(favs))
            return [{k: t.get(k, "") for k in ("path", "title", "artist", "album", "year", "genre")} | {"fav": t["path"] in favs}
                    for t in tracks[:1000]]
        if cmd == "mm_folder":
            folder = str(a.get("folder") or "").strip()
            if folder and not Path(folder).expanduser().is_dir():
                raise ValueError("такой папки нет")
            self.s.update({"music": {"folder": folder}})
            threading.Thread(target=self._mine_rescan, name="mymusic", daemon=True).start()
            return True
        if cmd == "mm_scan":
            threading.Thread(target=self._mine_rescan, args=(True,), name="mymusic", daemon=True).start()
            return True
        if cmd == "mm_fav":
            p, on = str(a.get("path") or ""), bool(a.get("on", True))
            fl = [x for x in (self.s.get("music", "favs") or []) if x != p] + ([p] if on else [])
            self.s.update({"music": {"favs": fl[-2000:]}})
            return True
        if cmd == "mm_play":
            what, path = str(a.get("what") or ""), str(a.get("path") or "")
            if not lib.tracks:
                raise ValueError("в папке с музыкой пока нет треков — выберите папку")
            tracks, w = lib.match(what, list(favs))
            tracks = tracks or lib.tracks
            if path:                                       # с этого трека, дальше — подборка по порядку
                i = next((k for k, t in enumerate(tracks) if t["path"] == path), 0)
                self.dj.queue, self.dj.pos, self.dj.what = list(tracks), i, w
                self._dj_track_n = 0
                self._mine_play(tracks[i])
            else:
                from mymusic import intro
                t = self.dj.start(tracks, w)
                self._dj_track_n = 0
                talk = self.s.get("music", "dj_talk") is not False
                self._mine_play(t, intro(t, first=True, what="ваше любимое" if w == "любимое" else f"«{w}» из вашей папки" if w
                                         else "музыку из вашей папки") if talk else "")
            return self.mine_status()
        if cmd == "mm_ctl":
            act = str(a.get("act") or "")
            if act == "pause":
                self.radio.pause()
            elif act == "play":
                if self.radio.paused:                    # своя музыка или станция на паузе — продолжить
                    self.radio.resume()
                elif self.dj.current():
                    self._mine_play(self.dj.current())
                elif lib.tracks:
                    self._mine_play(self.dj.start(lib.tracks, ""))
            elif act == "next" and self.dj.queue:
                self._mine_play(self.dj.next())
            elif act == "prev" and self.dj.queue:
                self._mine_play(self.dj.prev())
            elif act == "stop":
                self.radio.stop()
            elif act == "vol":                           # ползунок громкости в плеере студии (27.10)
                v = self.radio.set_volume(float(a.get("v") or 0.8))
                self.s.update({"audio": {"radio_volume": v}})
                return dict(self.mine_status(), vis=self._mm_vis())
            elif act == "seek":                          # нажали на полосу хода трека — с этого места
                self.radio.seek(float(a.get("t") or 0))
            self.emit("radio", **self.radio.status())
            return dict(self.mine_status(), vis=self._mm_vis())
        if cmd == "mm_vis":                              # плеер студии: ход трека, громкость, спектр (раз в ~0,1 с)
            return self._mm_vis()
        raise ValueError(f"неизвестная команда {cmd}")

    def _mm_vis(self):
        vis = getattr(self.radio, "vis", None)
        return vis() if callable(vis) else None

    def _mine_rescan(self, force=False):
        self.emit("mymusic", **dict(self.mine_status(), busy=True))
        try:
            self.mylib.scan(force)
        finally:
            self.emit("mymusic", **self.mine_status())

    # ---------- 0.74 «Ведущий»: между песнями — время, погода, ближайшее дело, новые письма (по галочкам) ----------

    def _dj_host_cmd(self, text, low, playing, lib):
        """«Лира, веди эфир» — ведущий включён (и, если ничего не играет, — своя музыка); «хватит болтать» — только музыка.
        «Хватит болтать» без музыки — не про ведущего (это разговор), его не трогаем."""
        radio_on = bool(self.radio.station) and not self.radio.paused
        if HOST_OFF_RX.search(low) and (playing or radio_on or re.search(r"ведущ|диджей|между\s+(?:песн|трек)", low)):
            self.s.update({"music": {"dj_talk": False, "dj_radio": False}})
            self._say_quick("Хорошо, дальше — только музыка. Захотите ведущего — скажите «веди эфир».", text)
            return True
        if HOST_ON_RX.search(low):
            self.s.update({"music": {"dj_talk": True}})
            if not playing and not radio_on and lib.tracks:
                return self._mine_start(lib.tracks, "", text, lead="Веду эфир! ")
            if radio_on and not playing:
                self.s.update({"music": {"dj_radio": True}})
                self._say_quick("Веду эфир: раз в полчаса — время и погода, поверх станции.", text)
                return True
            every = max(1, int(self.s.get("music", "dj_every") or 3))
            self._say_quick(f"Веду эфир: раз в {every} {__import__('mymusic')._plural(every, 'песню', 'песни', 'песен')} — пара слов между ними. "
                            "Что рассказывать — галочками в студии, раздел «Музыка».", text)
            return True
        return False

    def _dj_line(self, t, prev=None, extra=True):
        """Что сказать перед треком: полезная фраза по галочкам (одна, самая важная) и название, если оно со смыслом."""
        from mymusic import dj_opts, intro
        o = dj_opts(self.s.get("music") or {})
        parts = []
        if extra:
            kind, x = self._dj_extra(o)
            if x:
                parts.append(x)
        if o["track"]:
            tr = intro(t, prev=prev)
            if tr:
                parts.append(tr)
        return " ".join(parts)

    def _dj_extra(self, o, now_ts=None):
        """Одна фраза из того, что известно сейчас; сеть (погода, почта) — фоном, к следующему разу."""
        from mymusic import dj_extra
        now_ts = time.time() if now_ts is None else now_ts
        facts = dict(self._dj_facts)
        if o.get("tasks"):
            facts["task"] = self._dj_next_task()
        kind, x = dj_extra(o, facts, self._dj_last, now_ts)
        if kind == "tasks":
            self._dj_last["tasks_said"] = (list(self._dj_last.get("tasks_said") or []) + [facts["task"][0]])[-50:]
        elif kind == "mail":
            self._dj_facts["mail"] = 0                     # сказали — до следующего нового
        if kind:
            self._dj_last[kind] = now_ts
        self._dj_fetch(o)
        return kind, x

    def _dj_next_task(self):
        """Ближайшее напоминание или событие календаря в ближайшие два часа -> (ключ, фраза) или None."""
        from datetime import datetime, timedelta
        from mymusic import say_task
        now = datetime.now()
        end = now + timedelta(hours=2)
        best = None
        rem = getattr(self, "reminders", None)
        try:
            for x in (rem.occurrences(days=1, limit=60) if rem is not None else []):
                at = datetime.fromtimestamp(x["at"])
                if now < at <= end and (best is None or at < best[1]):
                    best = ("r:" + str(x["id"]), at, x.get("text") or "напоминание")
        except Exception:  # noqa: BLE001
            log.debug("ведущий: напоминания", exc_info=True)
        cal = getattr(self, "calendars", None)
        try:
            for e in (cal.events(now, end) if cal is not None else []):
                if e.get("allday") or e["start"] <= now:
                    continue
                if best is None or e["start"] < best[1]:
                    best = (f"c:{e.get('cid')}:{e['title']}:{e['start'].isoformat()}", e["start"], e["title"])
        except Exception:  # noqa: BLE001
            log.debug("ведущий: календарь", exc_info=True)
        return (best[0], say_task(best[2], best[1], now)) if best else None

    def _dj_fetch(self, o):
        """Фоном: погода (раз в 30 мин, если знаем город) и новые письма (раз в 5 мин) — к следующей фразе ведущего."""
        f = self._dj_facts
        now = time.time()
        city = (self.s.get("morning") or {}).get("city") or ""
        want_w = o.get("weather") and city and now - f["weather_t"] > 1800
        mail = getattr(self, "mail", None)
        want_m = o.get("mail") and mail is not None and mail.configured() and now - f["mail_t"] > 300
        if not (want_w or want_m) or self._dj_fetching:
            return
        self._dj_fetching = True

        def run():
            try:
                via = (getattr(getattr(self, "toolbox", None), "hooks", None) or {}).get("dewiar_web")
                if want_w:
                    f["weather_t"] = time.time()
                    try:
                        import weatherq
                        from mymusic import say_weather
                        if f.get("city") != city or not f.get("place"):
                            f["place"], f["city"] = weatherq.geocode(city, via), city
                        if f.get("place"):
                            f["weather"] = say_weather(weatherq.forecast(f["place"], via))
                    except Exception as e:  # noqa: BLE001
                        log.debug("ведущий: погода: %s", e)
                if want_m:
                    f["mail_t"] = time.time()
                    try:
                        uids = {str(x.get("uid")) for x in mail.inbox(limit=20, unread=True)}
                        if f["mail_seen"] is None:          # первый раз — что уже лежит непрочитанным, не новость
                            f["mail_seen"] = uids
                        else:
                            new = uids - f["mail_seen"]
                            f["mail"] = int(f.get("mail") or 0) + len(new)
                            f["mail_seen"] |= uids
                    except Exception as e:  # noqa: BLE001
                        log.debug("ведущий: почта: %s", e)
            finally:
                self._dj_fetching = False
        threading.Thread(target=run, name="dj-facts", daemon=True).start()

    def _dj_radio_loop(self):
        """Ведущий на радио (music.dj_radio): станция играет 25 минут подряд — в тихую минуту пара слов поверх неё:
        «Вы слушаете …», время, погода (и дела с письмами, если отмечены)."""
        seen, since = None, 0.0
        while not self.stopping.wait(20):
            try:
                st = self.radio.station or {}
                if not st or st.get("_mine") or self.radio.paused or not self.s.get("music", "dj_radio"):
                    seen = None
                    continue
                key = st.get("url") or st.get("name")
                if key != seen:
                    seen, since = key, time.time()
                    from mymusic import dj_opts
                    self._dj_fetch(dj_opts(self.s.get("music") or {}))
                    continue
                if time.time() - since < RADIO_HOST_S or self.turn is not None or self.state != "idle":
                    continue
                if time.monotonic() - float(getattr(self, "mic_voice_t", 0) or 0) < 30:
                    continue
                from mymusic import dj_opts
                o = dj_opts(self.s.get("music") or {})
                o["time"] = True                            # раз в полчаса время уместно всегда
                _, x = self._dj_extra(o)
                name = str(st.get("name") or "").strip()
                text = (f"Вы слушаете «{name}». " if name and len(name) < 40 else "") + (x or "")
                if text.strip():
                    self._dj_say(text.strip())
                since = time.time()
            except Exception:  # noqa: BLE001
                log.debug("ведущий на радио", exc_info=True)
