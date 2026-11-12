"""Обновления и модели с вашего сайта (по умолчанию https://dewiar.pro/dwrapp/latest.json).

latest.json (его делает tools/publish_update.py):
{
  "name": "Dewiar", "version": "0.10.11", "date": "2026-10-01",
  "deb": "dewiar-assistant_0.10.11_all.deb", "sha256": "…", "size": 2200000,
  "notes": "Что нового — коротко, Markdown",
  "mirrors": {"vosk_tts": "models/vosk-model-tts-ru-0.9-multi.zip"},  # упрощённый вид (только строки) — для старых версий
  "models": {                                                            # все модели со своего сайта
    "vosk_small": {"url": "models/vosk-model-small-ru-0.22.zip", "sha256": "…", "size": 45000000},
    "gigaam":     {"url": "models/gigaam-v3-e2e-rnnt-int8.zip", "sha256": "…", "name": "gigaam-v3-e2e-rnnt"},
    "vosk_tts":   {"url": "models/vosk-model-tts-ru-0.9-multi.zip", "sha256": "…", "name": "vosk-model-tts-ru-0.9-multi"},
    "piper":      {"url": "models/piper/", "files": {"ru_RU-denis-medium.onnx": "sha256…", …}}
  },
  "windows": {"version": "…", "exe": "Dewiar-Setup-….exe", "sha256": "…"},              # свой раздел для Windows
  "mac": {"version": "…", "arm64": {"dmg": "…", "sha256": "…"}, "x86_64": {…}}           # Mac — по желанию (зеркало)
}
Пути — относительно latest.json (или полные адреса). Всё это делает tools/publish_update.py (--models); формат менять
вместе с ним. Модели скачиваются с проверкой sha256; нет сайта или нет модели на нём — берём с исходного места.

Ядро проверяет адрес через минуту после запуска и раз в 6 часов, новую версию скачивает само и сверяет sha256
(без sha256 не ставим).

Скачивание (0.82.2, владелец 04.11: «то нормально, то по 5 минут открывает сайт» — сотни компьютеров качали новый выпуск
с сайта разом и забивали его канал):
- фоновая проверка качает новую версию не сразу, а через случайную задержку 0–6 ч (своя на каждом компьютере, помнится
  в updates/spread.json); «Проверить обновления» — сразу;
- основной источник — сайт (dewiar.pro); оборвалось — докачиваем с места обрыва (Range);
- GitHub — только запасной путь и только если в разделе latest.json есть поле "github" (адрес того же файла в выпуске
  открытой копии; кабинет и publish_update.py пишут его, только когда sha256 файла на GitHub совпал с опубликованным)
  и не выключена настройка updates.mirror_github. Идём туда, когда сайт не ответил, ответил «занят» (503) или отдаёт
  медленнее ~100 КБ/с дольше минуты. sha256 сверяется всегда;
- сайт занят или медленный, а запасного пути нет — откладываем на час (не долбим повторами), .part остаётся для докачки;
- ручная проверка не ждёт скачивания: ответ за секунды, ход — в public()["downloading"] и событии "update"
  («Скачиваю 0.82.2 — 45 % (с dewiar.pro)»). Устанавливает интерфейс (ui/app.py, он в сеансе рабочего стола): на Linux — pkexec apt-get
install, GNOME спросит пароль.

Mac: раздела "mac" в latest.json нет — сведения с GitHub: Dewiar-mac.json последнего выпуска открытой копии (его кладёт
задание mac в .github/workflows/mac.yml — версия, имя образа и sha256 для Apple Silicon и Intel); образ — с того же
выпуска. Ставит ui/macui.py (подмена Dewiar.app на месте).
"""

import hashlib
import os
import json
import logging
import platform
import random
import re
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

WIN = os.name == "nt"
MAC = sys.platform == "darwin"
MAC_JSON = "https://github.com/dwr-git/dewiar-app/releases/latest/download/Dewiar-mac.json"
MAC_DL = "https://github.com/dwr-git/dewiar-app/releases/download/"

log = logging.getLogger("dewiar.update")

DEFAULT_URL = "https://dewiar.pro/dwrapp/latest.json"
OLD_URLS = {"https://dewiar.pro/dwr/latest.json"}          # прежний адрес latest.json — вместо него берём DEFAULT_URL


# Блокировка на каждый файл назначения (два потока не качают одно и то же) и когда файл последний раз докачан.
_dl_locks, _dl_guard, _dl_done = {}, threading.Lock(), {}


def _replace(tmp, dst):
    """.part → файл. В Windows файл бывает занят антивирусом или другим скачиванием (WinError 32) — подождать и повторить."""
    for i in range(20):
        try:
            tmp.replace(dst)
            return
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.5)


def download(url, dst, sha256=None, on_progress=None, tries=6):
    """Скачать в dst через .part; при sha256 — сверить (не совпало — файла нет, исключение).
    Обрыв связи — докачиваем с того же места (Range), до tries попыток; одно и то же место одновременно не качаем
    (вторая просьба ждёт первую и берёт её результат)."""
    import httpx
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with _dl_guard:
        lock = _dl_locks.setdefault(str(dst), threading.Lock())
    with lock:
        if dst.exists() and time.monotonic() - _dl_done.get(str(dst), -1e9) < 120 and (not sha256 or _sha(dst) == sha256.lower()):
            return dst                                     # только что скачал другой поток
        tmp = dst.with_name(dst.name + ".part")
        last = None
        for attempt in range(tries):
            have = tmp.stat().st_size if tmp.exists() and attempt else 0     # первая попытка — с нуля (старый .part мог быть чужим)
            try:
                hdr = {"Range": f"bytes={have}-"} if have else {}
                with httpx.stream("GET", url, timeout=httpx.Timeout(20, read=120), follow_redirects=True, headers=hdr) as r:
                    if r.status_code == 416 and have:          # уже всё скачано
                        last = None                            # ошибка прошлой попытки больше не в счёт
                        break
                    r.raise_for_status()
                    if have and r.status_code != 206:          # сервер не умеет докачку — сначала
                        have = 0
                    size = int(r.headers.get("content-length") or 0)
                    total, done = (have + size if size else 0), have
                    with open(tmp, "ab" if have else "wb") as f:
                        for b in r.iter_bytes(1 << 16):
                            f.write(b)
                            done += len(b)
                            if on_progress and total:
                                on_progress(done / total)
                    if total and done < total:
                        raise httpx.RemoteProtocolError(f"оборвалось на {done} из {total} байт")
                last = None
                break
            except httpx.HTTPStatusError as e:
                last = e
                if e.response.status_code < 500:
                    break
            except httpx.TransportError as e:
                last = e
            if attempt < tries - 1:
                log.info("Скачивание %s оборвалось (%s) — докачиваю, попытка %d", dst.name, last, attempt + 2)
                time.sleep(min(2 ** attempt, 15))
        if last is not None:
            raise last
        if sha256 and _sha(tmp) != sha256.lower():
            tmp.unlink(missing_ok=True)
            raise RuntimeError("контрольная сумма не совпала")
        _replace(tmp, dst)
        _dl_done[str(dst)] = time.monotonic()
    return dst


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


CHECK_EVERY = 6 * 3600
SPREAD = 6 * 3600            # фоновое скачивание новой версии — через случайные 0…6 ч: компьютеры не качают с сайта разом
DEFER = 3600                 # сайт занят (503) или медленный, а запасного пути нет — следующая попытка через час
SLOW_SPEED = 100 * 1024      # медленнее этого (байт/с) …
SLOW_FOR = 60                # … дольше стольких секунд — сайт «медленный»: берём с GitHub (если можно) или откладываем
WAIT = 30                    # сайт молчит дольше (при слежке за скоростью) — «не ответил»


class _Busy(Exception):
    """Источник занят (503/502/504/429) или медленный — не повторять тут же."""


def _src_name(url, info=None):
    """Подпись источника для людей: «GitHub» (запасной путь из поля "github" или адрес GitHub) или имя сайта (dewiar.pro)."""
    if info and url == info.get("mirror"):
        return "GitHub"
    host = (urlparse(url).hostname or "").lower()
    if host == "github.com" or host.endswith((".github.com", ".githubusercontent.com")):
        return "GitHub"
    return host.removeprefix("www.") or "сайт"


def mac_arch():
    """Какой образ нужен этому Mac: arm64 (Apple Silicon) или x86_64 (Intel; и Intel-сборка под Rosetta — та же)."""
    return "x86_64" if platform.machine() == "x86_64" else "arm64"


def mac_info(d, base, arch):
    """Сведения о Mac-версии ({version, tag?, date?, arm64: {dmg, sha256, size}, x86_64: {…}}) -> {version, url, sha256,
    size, date, notes} для этого Mac или None (нет версии, образа для этой архитектуры или sha256). base — откуда считать
    путь к образу: адрес latest.json или папка выпусков GitHub (тогда …/v<версия>/<образ>)."""
    if not isinstance(d, dict):
        return None
    ver = str(d.get("version") or "")
    one = d.get(arch)
    if not ver or not isinstance(one, dict) or not one.get("dmg") or not one.get("sha256"):
        return None
    dmg = str(one["dmg"])
    if base == MAC_DL:
        url = dmg if dmg.startswith("https://") else f"{MAC_DL}{d.get('tag') or 'v' + ver}/{dmg}"
    else:
        url = urljoin(base, dmg)
    return {"version": ver, "url": url, "sha256": str(one["sha256"]).lower(), "size": one.get("size"),
            "date": d.get("date", ""), "notes": d.get("notes", "")}


# 12.11 (пакет 11.11: 262 компьютера из 541 — на 0.84.2): вопрос «Обновить сейчас?» виджет задаёт только развёрнутым
# (а с автозапуском он в трее) и раз в 20 часов на минуту — его просто не видят. Windows ставит обновление без вопросов
# системы (тихий установщик), поэтому скачанное ставим сами, когда человека нет за компьютером: AUTO_IDLE без мыши и
# клавиатуры, разговора нет, будильник не звенит; идёт фоновая задача — ждём втрое дольше (она продолжится после
# перезапуска, но зачем её прерывать). Linux спрашивает пароль (pkexec) — там только по нажатию.
AUTO_IDLE = 10 * 60


def auto_due(s, available, idle, state="idle", busy=False, tasks_running=False, win=None):
    """Пора поставить скачанное обновление самим? -> True/False (решает ядро, ставит интерфейс — событие update_auto)."""
    if not (WIN if win is None else win) or not available or not available.get("path"):
        return False
    if s is not None and s.get("updates", "auto_install") is False:
        return False
    if idle is None or idle < AUTO_IDLE or busy or state not in ("idle", "listening"):
        return False
    return not tasks_running or idle >= 3 * AUTO_IDLE


def vtuple(v):
    """«0.10.11» -> (0, 10, 11): версии сравниваем числами, а не строками («0.9» < «0.10»)."""
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0")))


class Updater:
    """Проверка и скачивание новой версии программы (STATE_DIR/updates) и адреса моделей со своего сайта.
    Последний полученный latest.json хранится в updates/manifest.json — модели можно найти и без сети."""

    def __init__(self, settings, version, state_dir, emit=None):
        self.s = settings
        self.version = version
        self.dir = Path(state_dir) / "updates"
        self.emit = emit or (lambda *a, **k: None)
        self.available = None           # {"version", "notes", "path", …} — скачано и проверено
        self.last = {"checked": 0, "error": "", "remote": ""}
        self.mirrors = {}
        self.models = {}                # ключ → {"url" (полный), "sha256", …} — см. model()
        self._fetched = False
        self._lock = threading.Lock()
        self.failed = None              # {"version", "path"} — нажали «обновить», а после перезапуска версия прежняя
        self.dl = None                  # идёт скачивание: {"version", "pct", "from", "manual"} — для подписи «Скачиваю … — 45 %»
        self._dl_lock = threading.Lock()
        self._dl_thread = None
        self._emit_at = 0.0
        self._check_pending()
        try:                            # последний известный список моделей — на случай, если сайт сейчас недоступен
            m = json.loads((self.dir / "manifest.json").read_text(encoding="utf-8"))
            self._parse(m, m.get("_base", ""))
        except (OSError, ValueError):
            pass

    def _check_pending(self):
        """Окно перед тихой установкой (ui/app.py, Windows) пишет updates/pending.json. Новая версия запустилась —
        хорошо; запустилась прежняя — установка не встала (скриншот 15.10: «не обновляется у него», нажимает —
        и ничего): виджет предложит открыть установщик обычным окном — там видно, что мешает."""
        f = self.dir / "pending.json"
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        f.unlink(missing_ok=True)
        m = re.search(r"(\d+\.\d+\.\d+)", str(d.get("file") or ""))
        if not m or time.time() - float(d.get("ts") or 0) > 7 * 86400:
            return
        if vtuple(m.group(1)) <= vtuple(self.version):
            log.info("Обновление до %s встало", m.group(1))
            return
        exe = self.dir / Path(str(d["file"])).name
        log.warning("Обновление до %s не установилось — запущена %s", m.group(1), self.version)
        self.failed = {"version": m.group(1), "path": str(exe) if exe.is_file() else ""}

    @property
    def url(self):
        u = ((self.s.get("updates", "url") if self.s else "") or "").strip()
        return DEFAULT_URL if not u or u in OLD_URLS else u

    def _parse(self, m, base):
        """mirrors и models из latest.json -> полные адреса (относительные пути — от адреса latest.json).
        Модель может быть записана просто строкой-адресом."""
        self.mirrors = {k: urljoin(base, v) for k, v in (m.get("mirrors") or {}).items() if isinstance(v, str) and v}
        models = {}
        for k, v in (m.get("models") or {}).items():
            if isinstance(v, str):
                v = {"url": v}
            if isinstance(v, dict) and v.get("url"):
                models[k] = dict(v, url=urljoin(base, v["url"]))
        self.models = models

    def _fetch(self, timeout=12):
        """Скачать latest.json -> (данные, его итоговый адрес после перенаправлений — от него считаются пути)."""
        import httpx
        r = httpx.get(self.url, timeout=timeout, follow_redirects=True, headers={"Cache-Control": "no-cache"})
        r.raise_for_status()
        m = r.json()
        base = str(r.url)
        self._parse(m, base)
        self._fetched = True
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / "manifest.json").write_text(json.dumps(dict(m, _base=base), ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return m, base

    def model(self, key):
        """Где взять модель на своём сайте: {"url", "sha256", …} или None. Сайт спрашиваем один раз за запуск
        (быстро, до скачивания моделей); недоступен — последний сохранённый список."""
        with self._lock:
            if not self._fetched:
                try:
                    self._fetch(timeout=8)
                except Exception as e:  # noqa: BLE001
                    self._fetched = True          # не дёргаем сайт перед каждой моделью
                    log.info("Список моделей с сайта недоступен: %s", e)
        return self.models.get(key)

    def check(self, download=True, manual=True, wait=True):
        """-> словарь о доступном обновлении ({version, notes, date, url, sha256, size, path}) или None.
        Ошибки сети — не страшно, попробуем позже (текст — в last["error"]). На Windows смотрим раздел "windows".
        manual=False — фоновая проверка: новую версию качаем после случайной задержки (SPREAD), до неё — None.
        wait=False — не ждать скачивания: вернуть сведения сразу (без "path", с "downloading": True), качать в фоне;
        скачалось — self.available и событие "update". Само скачивание — вне self._lock: пока фоновая проверка качает,
        ручная проверка отвечает сразу (не «занят: проверяет обновления» минутами, как 04.11)."""
        r = self._check(download, manual, wait)
        if not (isinstance(r, tuple) and r and r[0] == "download"):
            return r
        info = r[1]
        try:
            info["path"] = str(self._download(info, manual))
        except Exception as e:  # noqa: BLE001
            self._failed(info["version"], e)
            self.emit("update", update=self.public())
            return None
        self.available = info
        self.last["error"] = ""
        log.info("Доступно обновление %s", info["version"])
        self.emit("update", update=self.public())
        return info

    def _check(self, download, manual, wait):
        with self._lock:
            self.last["checked"] = time.time()
            try:
                m, base = self._fetch()
            except Exception as e:  # noqa: BLE001
                self.last["error"] = f"{self.url}: {e}"
                log.info("Обновления: %s", self.last["error"])
                return None
            self.last["error"] = ""
            if MAC:
                return self._check_mac(m, base, download, manual, wait)
            if WIN:                     # Windows: свой раздел в том же latest.json — {"windows": {"version", "exe", "sha256", …}}
                m, key = (m.get("windows") or {}), "exe"
            else:
                key = "deb"
            ver = str(m.get("version") or "")
            self.last["remote"] = ver
            if not ver or vtuple(ver) <= vtuple(self.version) or not m.get(key):
                self.available = None
                return None
            url = urljoin(base, m[key])
            mirror = self._mirror(m, base, url)
            info = {"version": ver, "notes": m.get("notes", ""), "date": m.get("date", ""),
                    "url": url, "sha256": (m.get("sha256") or "").lower(), "size": m.get("size"),
                    "sources": [url] + mirror, "mirror": mirror[0] if mirror else ""}
            return self._deliver(info, download, manual, wait)

    def _mirror(self, sec, base, url):
        """Запасной адрес того же файла (поле "github" раздела latest.json) — [адрес] или []. Нет поля, пустое или
        выключено настройкой updates.mirror_github — GitHub не трогаем."""
        gh = sec.get("github") if isinstance(sec, dict) else None
        if not isinstance(gh, str) or not gh.strip():
            return []
        if self.s and self.s.get("updates", "mirror_github") is False:
            return []
        gh = urljoin(base, gh.strip())
        return [gh] if gh != url and gh.startswith(("https://", "http://")) else []

    def _deliver(self, info, download, manual, wait):
        """Найдена новая версия: скачать (сразу, после случайной задержки или в фоне) -> info, None или ("download", info)
        — тогда check() скачает сам, отпустив self._lock."""
        ver = info["version"]
        if not download:
            self.available = info
            self.emit("update", update=self.public())
            return info
        ready = self._ready(info)
        if ready is None and not manual:
            at = self._spread_at(ver)
            nxt = max(at, float(self.last.get("defer") or 0))
            if time.time() < nxt:
                self.last["next"] = nxt
                log.info("Новая версия %s — скачаю примерно через %d мин (скачивания разнесены по времени)",
                         ver, max(1, int((nxt - time.time()) / 60)))
                return None
        self.last.pop("next", None)
        if ready is not None:
            info["path"] = str(ready)
        elif not wait:
            # фоновое скачивание уже идёт — его ход и покажем (теперь и в виджете); нет — начинаем
            self.dl = dict(self.dl or {"version": ver, "pct": 0, "from": _src_name(info["sources"][0], info)}, manual=True)
            if not (self._dl_thread and self._dl_thread.is_alive()):
                self._dl_thread = threading.Thread(target=self._bg, args=(dict(info),), name="update-download", daemon=True)
                self._dl_thread.start()
            self.emit("update", update=self.public())
            return dict(info, downloading=True)
        else:
            return ("download", info)            # check() скачает уже без self._lock
        self.available = info
        self.last["error"] = ""
        log.info("Доступно обновление %s", ver)
        self.emit("update", update=self.public())
        return info

    def _bg(self, info):
        """Скачивание по ручной проверке — в своём потоке: проверка ответила за секунды, ход виден в подписи."""
        try:
            info["path"] = str(self._download(info, True))
        except Exception as e:  # noqa: BLE001
            self._failed(info["version"], e)
            self.emit("update", update=self.public())
            return
        self.available = info
        self.last["error"] = ""
        log.info("Доступно обновление %s", info["version"])
        self.emit("update", update=self.public())

    def _failed(self, ver, e):
        if isinstance(e, _Busy):
            self.last["defer"] = time.time() + DEFER
            self.last["next"] = self.last["defer"]
            self.last["error"] = f"сейчас не скачать: {e} — докачаю сама примерно через час"
        else:
            self.last["error"] = f"не скачалось: {e}"
        log.warning("Обновление %s не скачалось: %s", ver, e)

    def _spread_at(self, ver):
        """Когда фоновой проверке можно качать версию ver: случайно в ближайшие SPREAD секунд, своё время у каждого
        компьютера; помнится в updates/spread.json — перезапуск программы не перебрасывает жребий."""
        f = self.dir / "spread.json"
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("version") == ver:
                return float(d.get("at") or 0)
        except (OSError, ValueError, TypeError):
            pass
        at = time.time() + random.uniform(0, SPREAD)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({"version": ver, "at": at}), encoding="utf-8")
        except OSError:
            pass
        return at

    def _check_mac(self, m, base, download=True, manual=True, wait=True):
        """Mac: раздел "mac" latest.json (если сайт его публикует) или Dewiar-mac.json с GitHub -> как check()."""
        try:
            info = mac_info(m.get("mac") or {}, base, mac_arch())
            if info is None:
                import httpx
                r = httpx.get(MAC_JSON, timeout=15, follow_redirects=True, headers={"Cache-Control": "no-cache"})
                r.raise_for_status()
                info = mac_info(r.json(), MAC_DL, mac_arch())
        except Exception as e:  # noqa: BLE001
            self.last["error"] = f"{MAC_JSON}: {e}"
            log.info("Обновления (Mac): %s", self.last["error"])
            return None
        if info is None:
            self.available = None
            return None
        self.last["remote"] = info["version"]
        if vtuple(info["version"]) <= vtuple(self.version):
            self.available = None
            return None
        if info["version"] == str(m.get("version") or ""):
            info.update(notes=m.get("notes", ""), date=info.get("date") or m.get("date", ""))
        info["sources"] = [info["url"]]
        return self._deliver(info, download, manual, wait)

    def _dst(self, info):
        name = info["url"].rsplit("/", 1)[-1].split("?")[0] or f"dewiar-{info['version']}.{'exe' if WIN else 'dmg' if MAC else 'deb'}"
        return self.dir / name

    def _ready(self, info):
        """Уже скачанный и проверенный пакет этой версии -> путь или None."""
        dst = self._dst(info)
        try:
            return dst if info.get("sha256") and dst.is_file() and self._sha(dst) == info["sha256"] else None
        except OSError:
            return None

    def _progress(self, info, src, done, total, manual):
        pct = int(done * 100 / total) if total else 0
        self.dl = {"version": info["version"], "pct": min(100, pct), "from": _src_name(src, info),
                   "manual": bool(manual or (self.dl or {}).get("manual"))}
        now = time.monotonic()
        if now - self._emit_at >= 0.7 or done == 0:
            self._emit_at = now
            self.emit("update", update=self.public())

    def _get(self, url, tmp, info, guard, manual):
        """Один заход скачивания url в tmp, с места обрыва (Range), если .part уже есть и сервер умеет докачку.
        guard — следить за скоростью: медленнее SLOW_SPEED дольше SLOW_FOR — _Busy. Ответ 503/502/504/429 — _Busy."""
        import httpx
        have = tmp.stat().st_size if tmp.exists() else 0
        hdr = {"Range": f"bytes={have}-"} if have else {}
        with httpx.stream("GET", url, timeout=httpx.Timeout(20, read=WAIT if guard else 120), follow_redirects=True,
                          headers=hdr) as r:
            if r.status_code == 416 and have:              # уже всё скачано
                return
            if r.status_code in (429, 502, 503, 504):
                raise _Busy(f"{_src_name(url, info)} ответил {r.status_code}")
            r.raise_for_status()
            if have and r.status_code != 206:              # сервер не умеет докачку — сначала
                have = 0
            size = int(r.headers.get("content-length") or 0)
            total = have + size if size else int(info.get("size") or 0)
            done = have
            mark_t, mark_done = time.monotonic(), done
            with open(tmp, "ab" if have else "wb") as f:
                for b in r.iter_bytes(1 << 16):
                    f.write(b)
                    done += len(b)
                    now = time.monotonic()
                    if now - mark_t >= SLOW_FOR:
                        speed = (done - mark_done) / (now - mark_t)
                        if guard and speed < SLOW_SPEED:
                            raise _Busy(f"{_src_name(url, info)} отдаёт медленно — {speed / 1024:.0f} КБ/с")
                        mark_t, mark_done = now, done
                    self._progress(info, url, done, total, manual)
            if total and done < total:
                raise httpx.RemoteProtocolError(f"оборвалось на {done} из {total} байт")

    def _fetch_from(self, url, tmp, info, guard, manual, tries=4):
        """Скачать url в tmp, докачивая обрывы (до tries заходов). Занят/медленный — _Busy сразу, без повторов."""
        import httpx
        last = None
        for attempt in range(tries):
            try:
                self._get(url, tmp, info, guard, manual)
                return
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"{_src_name(url, info)} ответил {e.response.status_code}") from None
            except httpx.TimeoutException as e:
                if guard:
                    raise _Busy(f"{_src_name(url, info)} не ответил вовремя") from e
                last = e
            except httpx.TransportError as e:
                last = e
            if attempt < tries - 1:
                log.info("Скачивание %s оборвалось (%s) — докачиваю, попытка %d", tmp.name, last, attempt + 2)
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"{_src_name(url, info)}: {last}")

    def _download(self, info, manual=False):
        """Скачать пакет обновления -> путь. Без sha256 в latest.json или при несовпадении — не сохраняем:
        пакет ставится с правами администратора, непроверенный файл ставить нельзя. Уже скачанный и проверенный —
        не качаем заново. Сначала сайт (с докачкой), запасной путь (GitHub) — если он есть и сайт не ответил,
        занят или медленный; без запасного — _Busy (ядро отложит на час). Ручная проверка без запасного пути не
        прерывается из-за медленной скорости — человек видит ход сам."""
        with self._dl_lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            dst = self._dst(info)
            if self._ready(info):
                return dst
            if not info.get("sha256"):
                raise RuntimeError("в latest.json нет sha256 — не ставлю непроверенный пакет")
            sources = info.get("sources") or [info["url"]]
            try:
                for i, url in enumerate(sources):
                    spare = i < len(sources) - 1                 # есть куда отступить
                    tmp = dst.with_suffix(".part" if i == 0 else f".{i}.part")
                    self._progress(info, url, 0, info.get("size"), manual)
                    try:
                        self._fetch_from(url, tmp, info, guard=spare or not manual, manual=manual)
                    except Exception as e:  # noqa: BLE001
                        if not spare:
                            raise
                        log.warning("Обновление %s: %s — беру с %s", info["version"], e, _src_name(sources[i + 1], info))
                        continue
                    got = self._sha(tmp)
                    if got != info["sha256"]:
                        tmp_size = tmp.stat().st_size
                        tmp.unlink(missing_ok=True)
                        if spare:
                            log.warning("Обновление %s: с %s пришёл другой файл (sha256 %s…) — беру с %s", info["version"],
                                        _src_name(url, info), got[:12], _src_name(sources[i + 1], info))
                            continue
                        if url == info.get("mirror"):
                            raise RuntimeError(f"с GitHub пришёл другой файл (sha256 {got[:12]}…) — не принят")
                        raise RuntimeError(f"контрольная сумма не совпала — sha256 в latest.json не от этого файла "
                                           f"(у файла {got[:12]}…, размер {tmp_size} байт). Опубликуйте заново через publish_update.py")
                    try:
                        tmp.replace(dst)
                    except PermissionError:      # Windows: прежний файл занят (антивирус проверяет, установщик открыт) — WinError 32,
                        dst = dst.with_name(f"{dst.stem}-{int(time.time())}{dst.suffix}")   # пакет 20.10, №153: «не скачалось»
                        tmp.replace(dst)
                    info["from"] = _src_name(url, info)
                    log.info("Обновление %s скачано с %s", info["version"], info["from"])
                    self.last.pop("defer", None)
                    for old in list(self.dir.glob("*.exe" if WIN else "*.dmg" if MAC else "*.deb")) + list(self.dir.glob("*.part")):
                        if old != dst and not old.name.startswith(dst.stem + "."):   # старые версии и чужие .part не копим
                            try:
                                old.unlink(missing_ok=True)
                            except OSError:      # занят — уберём в другой раз
                                pass
                    for p in self.dir.glob(dst.stem + ".*part"):
                        p.unlink(missing_ok=True)
                    return dst
                raise RuntimeError("не скачалось ни с одного адреса")
            finally:
                self.dl = None

    @staticmethod
    def _sha(p):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()

    def public(self):
        """Для студии: текущая версия, доступное обновление, время и ошибка последней проверки."""
        return {"current": self.version, "url": self.url, "available": self.available, "failed": self.failed,
                "checked": self.last["checked"], "error": self.last["error"], "remote": self.last.get("remote", ""),
                "downloading": dict(self.dl) if self.dl else None, "next": self.last.get("next") or 0}

    def loop(self, stopping):
        """Фоновая проверка: через минуту после запуска и дальше раз в 6 часов (если не выключена updates.auto_check).
        Минута — чтобы проверка не мешала запуску. Новая версия скачивается в своё (случайное) время — loop просыпается
        к нему (last["next"]), как и через час после «сайт занят»."""
        if stopping.wait(60):
            return
        while True:
            import egress
            if (self.s.get("updates", "auto_check") if self.s else True) is not False and not egress.local_only():
                try:
                    self.check(manual=False)
                except Exception as e:  # noqa: BLE001
                    log.warning("Проверка обновлений: %s", e)
            pause = CHECK_EVERY
            nxt = float(self.last.get("next") or 0)          # время скачать (случайная задержка) или «сайт занят — через час»
            if nxt > time.time():
                pause = min(pause, max(5, nxt - time.time() + 1))
            if stopping.wait(pause):
                return
