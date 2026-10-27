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
        self.radio.on_end = self._mine_ended
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
        from mymusic import intro
        self._mine_play(t, intro(t, prev=prev) if talk else "")

    def _mine_start(self, tracks, what, said):
        from mymusic import intro
        if not tracks:
            return False
        t = self.dj.start(tracks, what)
        self._dj_track_n = 0
        w = {"": "музыку из вашей папки", "любимое": "ваше любимое"}.get(what, f"«{what}» из вашей папки")
        talk = self.s.get("music", "dj_talk") is not False
        msg = intro(t, first=True, what=w) if talk else f"Включаю {w}."
        log.info("🎵 Моя музыка: %s — %d треков", what or "вся папка", len(tracks))
        return self._mine_play(t, msg, said)

    def _mine_cmd(self, text):
        """Фразы про свою музыку. -> True, если ответили (иначе дальше — радио и модель)."""
        low = (text or "").lower().replace("ё", "е")
        playing = self._mine_playing()
        lib = getattr(self, "mylib", None)
        if lib is None:
            return False
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
            return bool(t) and self._mine_play(t, intro(t, prev=prev) if self.s.get("music", "dj_talk") is not False
                                               else "Следующий.", text)
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
                "paused": bool((self.radio.paused or {}).get("_mine"))}

    def mine_command(self, cmd, a):
        """Команды студии «Музыка»: mm_status, mm_list, mm_play, mm_ctl, mm_folder, mm_scan, mm_fav."""
        lib, favs = self.mylib, set(self.s.get("music", "favs") or [])
        if cmd == "mm_status":
            return dict(self.mine_status(), artists=lib.artists()[:12], dj_talk=self.s.get("music", "dj_talk") is not False)
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
                if (self.radio.paused or {}).get("_mine"):
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
            self.emit("radio", **self.radio.status())
            return self.mine_status()
        raise ValueError(f"неизвестная команда {cmd}")

    def _mine_rescan(self, force=False):
        self.emit("mymusic", **dict(self.mine_status(), busy=True))
        try:
            self.mylib.scan(force)
        finally:
            self.emit("mymusic", **self.mine_status())

