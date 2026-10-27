"""Радио внутри ассистента: поиск станций в radio-browser.info (открытый каталог ~50 000 станций) и проигрывание
потока: ffmpeg декодирует в PCM (s16le, моно, 44,1 кГц) → наш проигрыватель (make_player). Поэтому «пауза», «стоп»,
«громче/тише» работают голосом, а пока ассистент говорит — радио приглушается само (duck).
Части: search/pick — каталог, probe/StationHealth — какие станции реально играют в этой сети, diagnose — почему не
играет ни одна, Radio — проигрывание. Упавший ffmpeg помечается через eyes.ffmpeg_broken, чтобы брать другой.
"""

import json
import logging
import re as _re
import os
import random
import subprocess
import threading
import time

import httpx

log = logging.getLogger("dewiar.radio")
API = [s for s in [os.environ.get("DEWIAR_RADIO_API", "")] if s] or [
    "https://de1.api.radio-browser.info", "https://de2.api.radio-browser.info", "https://fi1.api.radio-browser.info",
    "https://all.api.radio-browser.info"]
UA = {"User-Agent": "Dewiar/0.17 (voice assistant)"}           # каталог radio-browser просит честно называть программу
# Потоки: многие станции (101.ru, hostingradio…) не отдают звук «непонятным» программам — представляемся браузером
STREAM_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
RATE = 44100                                                    # Гц; звук моно s16le — 2 байта на отсчёт
# «джаз», «рок» — это жанры (теги), а не названия станций
GENRES = {"джаз": "jazz", "рок": "rock", "классика": "classical", "классическая": "classical", "поп": "pop",
          "шансон": "chanson", "лаунж": "lounge", "релакс": "relax", "чилаут": "chillout", "электронная": "electronic",
          "танцевальная": "dance", "хип-хоп": "hip-hop", "рэп": "rap", "блюз": "blues", "кантри": "country",
          "новости": "news", "детское": "children", "эмбиент": "ambient", "метал": "metal", "диско": "disco",
          "ретро": "retro", "80-е": "80s", "90-е": "90s", "фолк": "folk", "регги": "reggae", "соул": "soul"}


class RadioError(Exception):
    pass


def search(query, limit=8, as_tag=False):
    """-> [{"name", "url", "country", "tags", "bitrate"}] — популярные сверху, нерабочие скрыты.
    as_tag — query уже тег каталога («electronic», «techno»)."""
    q = (query or "").strip().lower()
    for w in ("радио", "радиостанция", "станция", "включи", "поставь", "онлайн"):
        q = q.replace(w, " ")
    q = " ".join(q.split())
    tag = GENRES.get(q) or GENRES.get(q.rstrip("аяуюые")) or (q if q in GENRES.values() or as_tag else "")
    params = {"limit": limit, "hidebroken": "true", "order": "clickcount", "reverse": "true"}
    if tag:
        params["tag"] = tag
    elif q:
        params["name"] = q
    else:
        params["countrycode"] = "RU"
    last = None
    for base in API:
        try:
            r = httpx.get(base + "/json/stations/search", params=params, headers=UA, timeout=8)
            r.raise_for_status()
            out = [{"name": (x.get("name") or "").strip(), "url": x.get("url_resolved") or x.get("url"),
                    "country": x.get("countrycode", ""), "tags": x.get("tags", ""), "bitrate": x.get("bitrate", 0)}
                   for x in r.json() if (x.get("url_resolved") or x.get("url"))]
            if not out and params.get("name") and len(q.split()[0]) >= 4:   # «Европа плюс» vs «Европа Плюс Москва» — ищем шире
                params2 = dict(params, name=q.split()[0])                   # (по слову от 4 букв: «с файла» искало «с» — №359)
                r = httpx.get(base + "/json/stations/search", params=params2, headers=UA, timeout=8)
                out = [{"name": (x.get("name") or "").strip(), "url": x.get("url_resolved") or x.get("url"),
                        "country": x.get("countrycode", ""), "tags": x.get("tags", ""), "bitrate": x.get("bitrate", 0)}
                       for x in r.json() if (x.get("url_resolved") or x.get("url"))]
            return out
        except (httpx.HTTPError, ValueError) as e:
            last = e
            continue
    raise RadioError(f"каталог радиостанций недоступен: {last}")


def diagnose(ff, url, timeout=20):
    """Ни одна станция не играет — дело обычно не в станциях. Проверяем по шагам: запускается ли ffmpeg, выдаёт ли
    он звук, доступна ли станция по сети, читает ли ffmpeg её поток -> (где поломка, что сделать) словами.
    Блокирует до ~1 мин — звать не из потока интерфейса."""
    import re as _re
    from urllib.parse import urlparse
    nw = 0x08000000 if os.name == "nt" else 0       # Windows: CREATE_NO_WINDOW — без мелькающего окна консоли
    last = lambda b: ((b or b"").decode(errors="replace").strip().splitlines() or [""])[-1][:200]  # noqa: E731
    if not ff:
        return "нет ffmpeg — без него радио не играет", "переустановите Dewiar (или: sudo apt install ffmpeg)"
    try:
        r = subprocess.run([ff, "-hide_banner", "-version"], capture_output=True, timeout=15, stdin=subprocess.DEVNULL, creationflags=nw)
        if r.returncode != 0:
            return f"не запускается ffmpeg ({ff}): {last(r.stderr) or 'код ' + str(r.returncode)}", \
                "переустановите ffmpeg: sudo apt install --reinstall ffmpeg (после сбоя обновления это частая причина)"
        r = subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-f", "s16le", "-ac", "1",
                            "-ar", str(RATE), "-"], capture_output=True, timeout=15, stdin=subprocess.DEVNULL, creationflags=nw)
        if len(r.stdout) < RATE:
            return f"ffmpeg запускается, но не выдаёт звук: {last(r.stderr) or 'код ' + str(r.returncode)}", \
                "переустановите ffmpeg: sudo apt install --reinstall ffmpeg"
    except (OSError, subprocess.SubprocessError) as e:
        return f"не запускается ffmpeg ({ff}): {e}", "переустановите ffmpeg: sudo apt install --reinstall ffmpeg"
    host = urlparse(url).hostname or url
    try:
        with httpx.stream("GET", url, headers={"User-Agent": STREAM_UA, "Icy-MetaData": "0"}, timeout=8,
                          follow_redirects=True) as resp:
            ctype = resp.headers.get("content-type", "")
            head = b""
            for chunk in resp.iter_bytes():
                head += chunk
                if len(head) > 4096:
                    break
            if resp.status_code >= 400:
                return f"сервер станции ({host}) ответил {resp.status_code}", \
                    "станции закрыты для вашей сети или страны — попробуйте с VPN или скажите другую станцию"
            if "html" in ctype or _re.search(rb"<html|<!doctype", head[:400], _re.I):
                return f"вместо звука от {host} пришла веб-страница", \
                    "сеть подменяет ответы (вход в Wi-Fi, прокси, блокировка) — проверьте интернет в браузере"
    except httpx.ConnectTimeout:
        return f"нет соединения с {host} (долго не отвечает)", "проверьте интернет, VPN или прокси — станции из этой сети недоступны"
    except httpx.ConnectError as e:
        return f"нет соединения с {host}: {str(e)[:120]}", "проверьте интернет и DNS (сайты открываются?), VPN или прокси"
    except httpx.HTTPError as e:
        return f"станция {host} недоступна: {str(e)[:120]}", "проверьте интернет, VPN или прокси"
    try:
        r = subprocess.run([ff, "-v", "error", "-user_agent", STREAM_UA, "-rw_timeout", "10000000", "-t", "3", "-i", url,
                            "-vn", "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"], capture_output=True, timeout=timeout,
                           stdin=subprocess.DEVNULL, creationflags=nw)
        if len(r.stdout) >= RATE:
            return "станция по сети доступна и ffmpeg её читает — значит, не выводится звук", \
                "проверьте динамики и устройство вывода: студия → «Звук и поведение»"
        return f"ffmpeg не читает поток станции: {last(r.stderr) or 'код ' + str(r.returncode)}", \
            "обновите ffmpeg (sudo apt install --reinstall ffmpeg) или скажите другую станцию"
    except subprocess.TimeoutExpired:
        return "ffmpeg не дождался звука от станции", "медленный интернет или блокировка — попробуйте с VPN"
    except (OSError, subprocess.SubprocessError) as e:
        return f"ffmpeg не запустился: {e}", "переустановите ffmpeg: sudo apt install --reinstall ffmpeg"


def probe(url, timeout=8.0):
    """Станция отвечает звуком? Короткая проверка без ffmpeg: ответ не ошибка, не веб-страница и за timeout пришло
    не меньше 4 КБ -> (ок, почему нет)."""
    try:
        with httpx.stream("GET", url, headers={"User-Agent": STREAM_UA, "Icy-MetaData": "0"}, timeout=timeout,
                          follow_redirects=True) as resp:
            if resp.status_code >= 400:
                return False, f"ответ {resp.status_code}"
            ctype = resp.headers.get("content-type", "").lower()
            head, t0 = b"", time.monotonic()
            for chunk in resp.iter_bytes():
                head += chunk
                if len(head) >= 16384 or time.monotonic() - t0 > timeout:
                    break
            if "html" in ctype or _re.search(rb"<html|<!doctype", head[:400], _re.I):
                return False, "вместо звука — веб-страница"
            if len(head) < 4096:
                return False, "звук не идёт"
            return True, ""
    except httpx.TimeoutException:
        return False, "не отвечает"
    except httpx.HTTPError as e:
        return False, str(e)[:100] or "нет соединения"


class StationHealth:
    """Какие станции реально играют у этого пользователя (зависит от его сети и провайдера). Хранится в path (JSON:
    url -> ok, время, причина); проверка в фоне не чаще раза в 12 часов (TTL) и по факту проигрывания. Молчащие
    станции идут в конец списка, чтобы не ждать на них подключения."""

    TTL = 12 * 3600

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    def mark(self, url, ok, why=""):
        with self._lock:
            self.data[url] = {"ok": bool(ok), "at": int(time.time()), "why": why}
            self._save()

    def dead(self, url):
        d = self.data.get(url)
        return bool(d) and not d["ok"] and time.time() - d["at"] < self.TTL

    def order(self, stations):
        """Живые и непроверенные — как были; известные «молчуны» — в конец."""
        return [s for s in stations if not self.dead(s["url"])] + [s for s in stations if self.dead(s["url"])]

    def check_all(self, stations, workers=4):
        """Проверить (probe) станции, не проверенные за TTL, в workers потоков -> сколько проверено. Блокирует."""
        from concurrent.futures import ThreadPoolExecutor
        todo = [s for s in stations if time.time() - (self.data.get(s["url"]) or {}).get("at", 0) > self.TTL]
        if not todo:
            return 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(lambda s: (s, probe(s["url"])), todo))
        for s, (ok, why) in res:
            self.mark(s["url"], ok, why)
        bad = [s["name"] for s, (ok, _) in res if not ok]
        log.info("📻 Проверка станций: играют %d из %d%s", len(res) - len(bad), len(res),
                 f"; молчат: {', '.join(bad)}" if bad else "")
        return len(res)


class Radio:
    """Одна станция за раз. play() запускает ffmpeg и поток _pump; stop()/pause() — мгновенно; duck() — тише, пока
    ассистент говорит. _gen — номер текущего проигрывания: поток со старым номером молча завершается.
    failed — почему станция не заиграла (для подсказки «скажи другую»)."""

    def __init__(self, make_player, ffmpeg):
        self.make_player, self.ffmpeg = make_player, ffmpeg      # make_player() -> Player; ffmpeg() -> путь
        self.on_end = None                                       # трек из своей папки доиграл сам -> on_end(станция)
        self.station, self.proc, self.player = None, None, None
        self.volume, self._duck = 0.8, 1.0             # _duck — множитель громкости на время разговора
        self._gen = 0
        self._lock = threading.Lock()
        self.paused = None                                        # станция на паузе (для «продолжи»)
        self.failed = None
        self.on_change = None                                     # () -> None: виджету — играет/нет, какая станция
        self.got, self.last = 0, None                             # сколько звука пришло; последняя станция (для «другую»)
        self.last_at = 0.0                                        # когда пришёл последний кусок звука (sounding)

    @property
    def playing(self):
        return self.proc is not None

    @property
    def sounding(self):
        """Правда звучит: ffmpeg жив и звук приходил последние 6 с. «playing» без звука — станция зависла на подключении
        (отзыв 13.10: «включи музыку» — «уже играет», а тишина)."""
        return self.proc is not None and self.got > 0 and time.monotonic() - self.last_at < 6

    def wait_sound(self, secs=6.0):
        """Подождать, пока пойдёт звук (или станция отвалится). -> True — звучит."""
        end = time.monotonic() + secs
        while time.monotonic() < end:
            if self.sounding:
                return True
            if self.proc is None:
                return False
            time.sleep(0.2)
        return self.sounding

    def status(self):
        return {"playing": self.playing, "station": (self.station or {}).get("name", ""),
                "paused": (self.paused or {}).get("name", ""), "volume": round(self.volume, 2),
                "tags": (self.station or self.paused or {}).get("tags", "")}

    def _changed(self):
        if self.on_change:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                log.exception("радио: уведомление")

    def play(self, station):
        """Остановить текущее и запустить station ({"name", "url", …}); RadioError — нет ffmpeg."""
        ff = self.ffmpeg()
        if not ff:
            raise RadioError("для радио нужен ffmpeg, а он не запускается — переустановите ffmpeg (sudo apt install --reinstall ffmpeg) или Dewiar")
        self._ff = ff
        self.stop(keep_pause=False)
        with self._lock:
            self._gen += 1
            gen = self._gen
            self.station, self.paused = station, None
            self.got, self.failed, self.last = 0, None, station
            # Локальному файлу переподключение не нужно. Опции собираем отдельным списком, а не вычищаем из общего:
            # фильтр по значениям «1»/«5» заодно выбрасывал бы «-ac 1» и любое другое совпавшее значение.
            local = station["url"].startswith("file:") or os.path.exists(station["url"])
            # Сетевые опции (user_agent, rw_timeout) файлу тоже нельзя: ffmpeg с ними файл не открывает вовсе («Option
            # user_agent not found») — так «своя музыка» не играла бы ни одного трека. Файл — в темпе звучания (-re).
            net = ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                   "-user_agent", STREAM_UA, "-rw_timeout", "15000000"]
            cmd = [ff, "-loglevel", "error", *(["-re"] if local else net), "-i", station["url"], "-vn", "-f", "s16le", "-ac", "1",
                   "-ar", str(RATE), "-"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                         creationflags=0x08000000 if os.name == "nt" else 0)
            self.player = self.make_player()
            self.player.start(RATE)
        threading.Thread(target=self._pump, args=(gen, self.proc, self.player), name="radio", daemon=True).start()
        log.info("📻 %s — %s", station.get("name"), station.get("url"))
        self._changed()

    def _pump(self, gen, proc, player):
        """Поток: читает PCM из ffmpeg, применяет громкость и duck, пишет в проигрыватель. Сломался вывод — один раз
        открывает проигрыватель заново на устройстве по умолчанию. Поток кончился сам — пишет причину в failed."""
        import numpy as np
        got = 0
        t0 = time.monotonic()
        out_fail = False
        eof = False
        while gen == self._gen:
            chunk = proc.stdout.read(RATE // 10 * 2)             # 0,1 с
            if not chunk:
                eof = True
                break
            got += len(chunk)
            self.got = got
            self.last_at = time.monotonic()
            g = self.volume * self._duck
            if g != 1.0:
                chunk = (np.frombuffer(chunk, dtype=np.int16).astype(np.float32) * g).clip(-32768, 32767).astype(np.int16).tobytes()
            try:
                ok = player.write(chunk)
            except Exception as e:  # noqa: BLE001
                log.warning("Радио: вывод звука: %s", e)
                ok = False
            if not ok:
                if gen == self._gen and not out_fail:            # не перебили, а сломался вывод — откроем заново
                    out_fail = True
                    try:
                        player.stop()
                        player = self.make_player()
                        player.device = ""                        # на устройство по умолчанию
                        player.start(RATE)
                        with self._lock:
                            if gen == self._gen:
                                self.player = player
                        log.info("Радио: вывод звука открыт заново (устройство по умолчанию)")
                        continue
                    except Exception as e:  # noqa: BLE001
                        log.warning("Радио: вывод звука не открылся: %s", e)
                break
        if gen == self._gen:                                      # поток кончился сам (станция отвалилась)
            # Сначала ждём, чем ffmpeg закончил сам (иначе упавший ffmpeg ещё не «прибран» системой — poll() даёт None,
            # а наш же kill выглядел бы как падение -9). Не вышел за 3 с — останавливаем сами: это не падение (rc = None).
            try:
                if not eof:
                    raise subprocess.TimeoutExpired(proc.args, 0)   # вывод звука сломался, ffmpeg жив — ждать нечего
                rc = proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                rc = None
                try:
                    proc.kill(); proc.wait(timeout=3)
                except Exception:  # noqa: BLE001
                    pass
            except Exception:  # noqa: BLE001
                rc = None
            err = ""
            try:
                err = (proc.stderr.read() or b"").decode(errors="replace")[-300:] if proc.stderr else ""
            except Exception:  # noqa: BLE001
                pass
            log.info("Радио остановилось: пришло %d КБ звука за %.1f с, ffmpeg %s%s", got // 1024, time.monotonic() - t0,
                     rc, f", ошибка: {err.strip()}" if err.strip() else "")
            if got == 0 and rc is not None and rc < 0 and not err.strip():   # ffmpeg упал (SIGSEGV…): дело не в станции
                try:
                    from eyes import ffmpeg_broken
                    ffmpeg_broken(proc.args[0])                   # именно тот ffmpeg, что упал
                except Exception:  # noqa: BLE001
                    pass
                log.warning("Радио: ffmpeg %s упал (сигнал %d) — дальше беру другой ffmpeg", proc.args[0], -rc)
            if got == 0 and time.monotonic() - t0 < 30:          # ни байта и быстро — станция не ответила
                self.failed = err.strip().splitlines()[-1][:200] if err.strip() else \
                    ("станция не отвечает" if rc in (0, None) else f"ffmpeg завершился с кодом {rc}")
            elif got < RATE * 2 * 3:                               # меньше 3 секунд звука — не заиграла
                self.failed = "поток оборвался через секунду" + (f": {err.strip().splitlines()[-1][:150]}" if err.strip() else "")
            ended = None
            with self._lock:
                if gen == self._gen:
                    ended = self.station
                    self._close()
                    self.station = None
            self._changed()
            # своя музыка: трек доиграл до конца (а не сломался в первые секунды) — дальше решает очередь (engine_mymusic)
            if ended and ended.get("_mine") and self.on_end and eof and not self.failed and got >= RATE * 2 * 3:
                threading.Thread(target=self.on_end, args=(ended,), name="radio-next", daemon=True).start()

    def _close(self):
        """Убить ffmpeg и закрыть проигрыватель. Звать под self._lock."""
        p, self.proc = self.proc, None
        if p is not None:
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass
        pl, self.player = self.player, None
        if pl is not None:
            pl.stop()

    def stop(self, keep_pause=False):
        """Остановить -> станция, что играла (или None). keep_pause — запомнить её для «продолжи»."""
        with self._lock:
            was = self.station if self.proc is not None else None
            self._gen += 1
            self._close()
            if keep_pause and was:
                self.paused = was
            self.station = None
        if was is not None:
            self._changed()
        return was

    def pause(self):
        """Живое радио нельзя «приостановить» — останавливаем и запоминаем станцию для «продолжи»."""
        return self.stop(keep_pause=True)

    def resume(self):
        if self.paused:
            st = self.paused
            self.play(st)
            return st
        return None

    def duck(self, on):
        """True/0.25 — тише (ассистент говорит поверх), 0 — тишина (слушаем вас: команду слышно и без крика),
        False/1 — как было. Поток при этом продолжает приниматься: после разговора музыка сразу играет дальше."""
        self._duck = 0.25 if on is True else 1.0 if on is False else max(0.0, min(1.0, float(on)))

    def set_volume(self, v):
        self.volume = max(0.1, min(1.0, float(v)))      # не ниже 10%: тише на слух неотличимо от тишины
        return self.volume


def pick(stations, query=""):
    """Лучшая станция: точное совпадение названия, затем название, содержащее запрос, затем самая популярная.
    Без запроса — случайная из трёх самых популярных, чтобы «включи радио» не играло всегда одно и то же."""
    if not stations:
        return None
    q = (query or "").lower().strip()
    exact = [s for s in stations if s["name"].lower() == q]
    if exact:
        return exact[0]
    near = [s for s in stations if q and q in s["name"].lower()]
    if near:
        return near[0]
    qg = " ".join(w for w in q.replace("радиостанция", " ").replace("радио", " ").split() if w not in ("включи", "поставь", "онлайн"))
    if q and (GENRES.get(qg) or GENRES.get(qg.rstrip("аяуюые")) or qg in GENRES.values()):
        return stations[0]                               # жанр («джаз», «рок») — искали по тегу: самая популярная
    if q:
        # №359 (27.10): «включи радио железо фм» играло Groove Salad, «включи радио с файла» — Radio Swiss Pop: по
        # названию без общего слова — не та станция. Берём только ту, где есть слово запроса (от 4 букв, по основе)
        import re as _re
        ws = [w[:5] for w in _re.findall(r"\w+", q) if len(w) >= 4 and w not in ("радио", "radio", "станция", "онлайн")]
        hit = [s for s in stations if any(w in s["name"].lower() for w in ws)]
        return hit[0] if hit else None
    return random.choice(stations[:3]) if len(stations) > 1 else stations[0]
