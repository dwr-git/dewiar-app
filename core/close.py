"""«Близкие»: переписка между помощниками разных людей через облако Dewiar — со сквозным шифрованием.

«Лира, напиши Андрею, что я задержусь» — у Андрея его помощник покажет сообщение и скажет вслух: «Сообщение от Михаила…».
Близкими становятся по приглашению: ссылка (…/download.php?close=ТОКЕН) или QR с ней; принять — accept(ссылка).
Устройство хранит свою пару ключей X25519 (закрытый — зашифрован ключом этого компьютера, crypt.device_key) и шлёт
серверу только открытый (/close/hello). Сообщение шифруется для всех устройств получателя и для других своих
(closecrypto.encrypt_for); сервер (server/dwrapp/cloud.php, close_handler) видит лишь, кому и когда.
Входящие забирает фоновый поток (loop): раз в 20 с, если есть близкие или висит приглашение, иначе — раз в 10 минут.
Файлы — до 10 МБ, шифруются отдельным ключом и сами сохраняются в папку ассистента «Близкие/<имя>».
Телефон делает то же самое в app.js (раздел «Близкие») — формат общий."""

import base64
import hashlib
import json
import logging
import mimetypes
import os
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

import closecrypto as CC
from settings import CONFIG_DIR, STATE_DIR

log = logging.getLogger("dewiar.close")
HIST_MAX = 300
FILE_MAX = 10 * 1024 * 1024
NATT_WAIT = 7 * 86400                 # вложения заметки с телефона ждут саму заметку (синхронизацию) не дольше недели


def _rx_text(rx, name):
    """Реакции на сообщение — для модели (close_read): « [реакции: Мама ❤️, вы 👍]»."""
    rx = rx or {}
    parts = [f"{name} {rx['them']}" if rx.get("them") else "", f"вы {rx['me']}" if rx.get("me") else ""]
    parts = [x for x in parts if x]
    return f" [реакции: {', '.join(parts)}]" if parts else ""


def _mark_text(m, mk):
    """Моё письмо: дошло ли и прочитано ли — для модели («Андрей прочитал?»). Старые письма без номера — ничего."""
    sid = _int((m or {}).get("sid"))
    if not m.get("out") or not sid or not isinstance(mk, (list, tuple)) or len(mk) != 2:
        return ""
    return " [прочитано]" if _int(mk[1]) >= sid else " [доставлено, ещё не прочитано]" if _int(mk[0]) >= sid else " [ещё не доставлено — его Dewiar не забирал почту]"


def _int(v):
    """Число из чужих данных: не число — 0 (кривое сообщение не должно ронять приём)."""
    try:
        return int(float(v))
    except (TypeError, ValueError, OverflowError):
        return 0


_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def safe_name(s, fallback="без имени", limit=120):
    """Имя папки или файла из чужих данных: без разделителей пути, «..», управляющих символов и имён, запретных в Windows."""
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(s or "")).strip().strip(".").strip()[:limit].strip()
    if not s or s.split(".")[0].lower() in _RESERVED:
        return fallback
    return s


class CloseError(Exception):
    """Ошибка с понятным человеку текстом."""


def token_of(link):
    """Ссылка-приглашение в любом виде (…download.php?close=…, dewiar://close?t=…, сам токен) -> токен."""
    s = (link or "").strip()
    if "://" in s or "?" in s:
        q = parse_qs(urlparse(s).query)
        s = (q.get("close") or q.get("t") or [""])[0]
    s = re.sub(r"[^A-Za-z0-9_-]", "", s)
    return s if 8 <= len(s) <= 64 else ""


def _stem(w):
    w = re.sub(r"[^а-яёa-z]", "", (w or "").lower().replace("ё", "е"))
    return w


# «Люда», «Люде», «Людочке» → Людмила: уменьшительные имена близких (как CL_NICK в app.js)
NICKS = {"люд": "людмила", "тан": "татьяна", "саш": "александр", "шур": "александр", "жен": "евгений", "миш": "михаил", "лен": "елена", "кат": "екатерина", "маш": "мария", "наташ": "наталья", "натах": "наталья", "оль": "ольга", "свет": "светлана", "вов": "владимир", "дим": "дмитрий", "кол": "николай", "сереж": "сергей", "серег": "сергей", "андрюш": "андрей", "ван": "иван", "леш": "алексей", "юл": "юлия", "ир": "ирина", "гал": "галина", "вал": "валентина", "над": "надежда", "люб": "любовь", "ан": "анна", "пет": "петр", "паш": "павел", "кост": "константин", "ген": "геннадий", "тол": "анатолий", "вит": "виктор", "слав": "вячеслав", "гош": "георгий", "лид": "лидия", "том": "тамара", "нин": "нина", "зин": "зинаида", "рит": "маргарита", "вик": "виктория"}
NICK_RX = re.compile(r"^(андрюш|наташ|натах|сереж|серег|свет|кост|слав|люд|тан|саш|шур|жен|миш|лен|кат|маш|оль|вов|дим|кол|ван|леш|гал|вал|над|люб|пет|паш|ген|тол|вит|гош|лид|том|нин|зин|рит|вик|юл|ир|ан)(?:а|я|е|у|ю|ы|и|ой|ей|ою|ею|очк[а-я]*|ечк[а-я]*|оньк[а-я]*|еньк[а-я]*|ик[а-я]*|ок|ул[а-я]*|ус[а-я]*|юш[а-я]*|уш[а-я]*)?$")


def _nick(w):
    m = NICK_RX.match(w)
    return NICKS[m.group(1)] if m else ""


def match_name(name, people):
    """«Андрею», «маме», «Исаевой Людмиле» -> человек из близких (по общему началу слов, порядок любой), иначе None
    (или несколько одинаково подходящих — тоже None)."""
    qs = [w for w in (_stem(x) for x in re.split(r"[\s,]+", str(name or ""))) if w]
    if not qs:
        return None

    def hit(q, n):
        k = 0
        while k < min(len(n), len(q)) and n[k] == q[k]:
            k += 1
        need = min(len(n), 3) if len(n) <= 4 else max(3, len(n) - 2)
        return k + 10 if n == q else (k if k >= need else 0)
    best, score, tie = None, 0, False
    for p in people:
        ws = [w for w in (_stem(x) for x in p.get("name", "").split()) if w]
        if not ws:
            continue
        per = [max(hit(v, n) for v in (q, _nick(q)) if v for n in ws + ["".join(ws)]) for q in qs]
        s = sum(per) - 4 * per.count(0)
        if not any(per) or s <= 0:
            continue
        if s > score:
            best, score, tie = p, s, False
        elif s == score and best is not p:
            tie = True
    return None if tie else best


COLORS = ["#9BD4FF", "#FFB547", "#3DF5C8", "#FF7AB6", "#B78CFF", "#9BE15D", "#7C8CFF", "#FF6B5A"]


def _color_of(pid):
    """Цвет кружка близкого — как в студии и на телефоне (по сумме кодов символов pid)."""
    return COLORS[sum(ord(ch) for ch in str(pid)) % len(COLORS)]


class Close:
    def __init__(self, host, state_path=None, key_path=None):
        """host: credentials() -> (token, link, url), emit(event, **kw), s (настройки), announce(text), push(title, text),
        workspace (root), device_name()."""
        self.host = host
        self.path = Path(state_path or STATE_DIR / "close.json")
        self.key_path = Path(key_path or CONFIG_DIR / "close.key")
        self._lock = threading.RLock()
        self.soon = threading.Event()
        self.error = ""
        self.st = self._load()
        self._priv = None
        self.calls = {}                 # id звонка → {role, pid, name, video, offer, token, at, fast}

    # ---------- состояние ----------
    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        d.setdefault("dev", "pc-" + uuid.uuid4().hex[:10])
        d.setdefault("cursor", 0)
        d.setdefault("people", [])
        d.setdefault("me", {})
        d.setdefault("hist", {})
        d.setdefault("unread", {})
        d.setdefault("seen_mid", [])
        d.setdefault("marks", {})                # pid -> [доставлено до, прочитано до] — номера моих писем в его ящике (sid)
        d.setdefault("read_up", {})              # pid -> до какого номера его письма уже отмечены прочитанными на сервере
        return d

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            log.exception("близкие: сохранить")

    def _keys(self):
        """Своя пара ключей: закрытый — в состоянии, зашифрованный ключом этого компьютера."""
        if self._priv:
            return self._priv, self.st["pub"]
        from crypt import CryptError, device_key, seal, unseal
        dk = device_key(self.key_path)
        if self.st.get("priv"):
            try:
                self._priv = unseal(CC.b64d(self.st["priv"]), dk)
                return self._priv, self.st["pub"]
            except (CryptError, ValueError):
                log.warning("близкие: ключ устройства не открылся — создаю новый")
        priv, pub = CC.keypair()
        self.st.update(priv=CC.b64e(seal(priv, dk)), pub=CC.b64e(pub))
        self._priv = priv
        self._save()
        return priv, self.st["pub"]

    # ---------- сеть ----------
    def _req(self, method, path, body=None, raw=None, params=None, timeout=20):
        token, link, url = self.host.credentials()
        if not token:
            raise CloseError("«Близкие» работают через Dewiar: войдите аккаунтом dewiar.pro или подключите ключ Dewiar.")
        h = {"Authorization": "Bearer " + token}
        params = dict(params or {}, p=path)              # httpx заменяет запрос в адресе целиком — p кладём сюда же
        if link and link != token:
            h["X-Sync-Link"] = link
        try:
            if raw is not None:
                h["Content-Type"] = "application/octet-stream"
                r = httpx.post(url, content=raw, headers=h, params=params, timeout=120)
            elif method == "GET":
                r = httpx.get(url, headers=h, params=params, timeout=timeout)
            else:
                r = httpx.post(url, json=body or {}, headers=h, params=params, timeout=timeout)
        except httpx.HTTPError as e:
            raise CloseError("нет связи с Dewiar — проверьте интернет") from e
        if r.status_code >= 400:
            try:
                msg = r.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                msg = f"облако ответило {r.status_code}"
            raise CloseError(msg)
        return r

    def _people(self, d):
        with self._lock:
            self.st["me"] = d.get("me") or {}
            self.st["people"] = d.get("people") or []
            self.st["offers"] = d.get("offers") or []   # «… зовёт вас в «Близкие»» (из «Рефералов») — ждут ответа
            mine = sorted({x.get("dev") for x in (self.st["me"].get("devs") or []) if x.get("dev") and x.get("dev") != self.st.get("dev")})
            new = set(mine) - set(self.st.get("own_devs") or [])
            self.st["own_devs"] = mine
            self._save()
        self.host.emit("close", state=self.state())
        if new:                                         # появилось ещё одно своё устройство — передать ему общее (умный дом)
            snap = getattr(self.host, "own_snapshot", lambda: None)()   # а у самого нет — попросить у своих
            threading.Thread(target=self._own_quiet, args=(snap or {"want": ["home"]},), daemon=True).start()

    def hello(self):
        """Представиться серверу: открытый ключ этого устройства и имя для близких. -> состояние."""
        _, pub = self._keys()
        name = (self.host.s.get("close", "name") or self.host.s.get("user_name") or "").strip()
        d = self._req("POST", "/close/hello", {"dev": self.st["dev"], "pub": pub, "devname": self.host.device_name(), "name": name}).json()
        self.st["hello_at"] = time.time()
        self._people(d)
        return self.state()

    def state(self):
        with self._lock:
            people = [dict(p, unread=int(self.st["unread"].get(p["pid"], 0)), marks=list((self.st.get("marks") or {}).get(p["pid"]) or [0, 0]),
                           last=(self.st["hist"].get(p["pid"]) or [{}])[-1]) for p in self.st["people"]]
            out = {"me": self.st.get("me") or {}, "people": people, "offers": list(self.st.get("offers") or []),
                   "error": self.error, "invite": self.st.get("invite") or None,
                   "ready": bool(self.st.get("pub"))}
        out["geo"] = self.geo_state()
        return out

    # ---------- радар «Рядом» (на компьютере — только смотреть и махать: место знает телефон) ----------
    def _geo(self, pid, g, mine=False):
        """Место близкого (или моего телефона — mine) для радара. g: {lat, lon, acc, ts, until} или {off}."""
        ok = isinstance(g, dict) and not g.get("off") and isinstance(g.get("lat"), (int, float)) and isinstance(g.get("lon"), (int, float)) \
            and -90 <= g["lat"] <= 90 and -180 <= g["lon"] <= 180
        with self._lock:
            geo = self.st.setdefault("geo", {})
            if mine:
                self.st["mygeo"] = {"lat": float(g["lat"]), "lon": float(g["lon"]), "acc": float(g.get("acc") or 0),
                                    "ts": min(int(time.time() * 1000), int(g.get("ts") or time.time() * 1000))} if ok else None
            elif ok:
                until = g.get("until")
                geo[pid] = {"lat": float(g["lat"]), "lon": float(g["lon"]), "acc": float(g.get("acc") or 0),
                            "ts": min(int(time.time() * 1000), int(g.get("ts") or time.time() * 1000)),
                            "until": -1 if until == -1 else int(until or time.time() * 1000 + 3600e3)}
            else:
                geo.pop(pid, None)
            self._save()
        self.host.emit("close_geo", geo=self.geo_state())

    def geo_state(self):
        """{people: {pid: место}, me: место моего телефона или None} — просроченное убирается."""
        now = int(time.time() * 1000)
        with self._lock:
            pids = {p["pid"] for p in self.st["people"]}
            geo = self.st.get("geo") or {}
            for pid in [k for k, v in geo.items() if k not in pids or (v.get("until") != -1 and v.get("until", 0) < now) or now - v.get("ts", 0) > 7 * 864e5]:
                geo.pop(pid, None)
            me = self.st.get("mygeo")
            return {"people": dict(geo), "me": me if me and now - me.get("ts", 0) < 7 * 864e5 else None}

    MEET = {"/meet/state": "GET", "/meet/rules": "POST", "/meet/here": "POST", "/meet/leave": "POST", "/meet/wave": "POST",
            "/meet/block": "POST", "/meet/report": "POST"}
    MEET_FRESH = 30 * 60 * 1000                   # место телефона свежее — можно отметиться с компьютера

    def meet(self, path, body=None):
        """«Встречи» из студии (22.10, владелец: «добавить и на компе, но чтобы работало с телефона»): то же пространство,
        что у телефона, — его отметка и люди рядом. Отметиться с компьютера — по месту телефона (свежее 30 минут); уже
        отмечены — изменить и продлить можно и без места (сайт берёт прежнее). -> ответ сайта (meet_state)."""
        if path not in self.MEET:
            raise CloseError("такого действия во Встречах нет")
        body = {k: v for k, v in dict(body or {}).items() if k not in ("lat", "lon")}
        if path == "/meet/here" and not body.pop("keep", False):
            g = self.geo_state().get("me")
            if not g or time.time() * 1000 - float(g.get("ts") or 0) > self.MEET_FRESH:
                raise CloseError("Компьютер не знает, где вы: отметьтесь на телефоне («Близкие» → «Встречи») или откройте там "
                                 "«Рядом» — место телефона появится здесь, и можно будет отметиться отсюда.")
            body.update(lat=float(g["lat"]), lon=float(g["lon"]))
        d = self._req(self.MEET[path], path, None if self.MEET[path] == "GET" else body).json()
        if isinstance(d.get("state"), dict):          # помахали друг другу — новый человек в «Близких»
            self._people(d["state"])
        return d

    def wave(self, who):
        """👋 близкому: обычное сообщение {wave: 1, t: "👋"} — у него волны, «… машет вам» и голос."""
        return self.send(who, "👋", payload={"wave": 1})

    def history(self, pid, mark_read=True):
        with self._lock:
            if mark_read and self.st["unread"].pop(pid, None):
                self._save()
                self.host.emit("close", state=self.state())
            h = list(self.st["hist"].get(pid) or [])
        if mark_read:
            self._mark_read(pid, h)
        return h

    def _mark_read(self, pid, h=None):
        """Переписку открыли (или помощница прочитала её вслух) — близкому «прочитано»: его письма до последнего номера
        (24.10, владелец: «не понятно, прочитал ли человек сообщение, дошло ли оно»). Сервер видит только номер."""
        h = h if h is not None else list(self.st["hist"].get(pid) or [])
        top = max([int(m.get("sid") or 0) for m in h if not m.get("out")] or [0])
        if top <= int(self.st.setdefault("read_up", {}).get(pid) or 0):
            return

        def run():
            try:
                self._req("POST", "/close/seen", {"peer": pid, "upto": top})
                with self._lock:
                    self.st["read_up"][pid] = max(top, int(self.st["read_up"].get(pid) or 0))
                    self._save()
            except Exception as e:  # noqa: BLE001 — старый сайт без /close/seen или нет связи: попробуем в следующий раз
                log.debug("близкие: «прочитано» не ушло: %s", e)
        threading.Thread(target=run, daemon=True).start()

    def set_name(self, name):
        self.host.s.update({"close": {"name": (name or "").strip()[:40]}})
        return self.hello()

    # ---------- карточка «Я» (0.45): фото, имя, о себе — для «Близких» и (если разрешено) «Встреч» ----------
    def set_card(self, name=None, about=None, face=None, face_meet=None):
        """Сохранить карточку на сайте. face: base64 / data URI (студия сама сжимает до 256×256 JPEG), "" — убрать фото.
        Фото хранится на dewiar.pro как аватар в мессенджере: видят близкие и — если face_meet — люди рядом во «Встречах»."""
        body = {}
        if name is not None:
            name = str(name).strip()[:40]
            self.host.s.update({"close": {"name": name}})
            body["name"] = name
        if about is not None:
            body["about"] = str(about).strip()[:160]
        if face is not None:
            body["face"] = str(face)
        if face_meet is not None:
            body["face_meet"] = bool(face_meet)
        self._people(self._req("POST", "/close/me", body).json())
        return self.state()

    FACE_DIR = STATE_DIR / "close_faces"

    def face(self, pid, v, meet=False):
        """Фото близкого (pid) или человека во «Встречах» (meet: pid = mid) -> data URI; кэш по номеру версии v."""
        import base64
        import re as _re
        pid, v = _re.sub(r"[^a-z0-9]", "", str(pid or ""))[:40], int(v or 0)
        if not pid or not v:
            return {"data": ""}
        f = self.FACE_DIR / f"{'m' if meet else 'p'}-{pid}-{v}"
        try:
            b = f.read_bytes()
        except OSError:
            r = self._req("GET", "/meet/face" if meet else "/close/face", params={"mid" if meet else "pid": pid})
            b = r.content
            try:
                self.FACE_DIR.mkdir(parents=True, exist_ok=True)
                for old in self.FACE_DIR.glob(f"{'m' if meet else 'p'}-{pid}-*"):   # прежние версии этого фото
                    old.unlink(missing_ok=True)
                f.write_bytes(b)
            except OSError:
                pass
        t = "image/png" if b[:4] == b"\x89PNG" else "image/webp" if b[:4] == b"RIFF" else "image/jpeg"
        return {"data": f"data:{t};base64," + base64.b64encode(b).decode()}

    def invite(self, renew=False):
        d = self._req("POST", "/close/invite", {"renew": bool(renew)}).json()
        self.st["invite"] = {"link": d["link"], "app": d.get("app", ""), "expires": d.get("expires", 0)}
        self._save()
        self.soon.set()
        return self.st["invite"]

    def peek(self, link):
        t = token_of(link)
        if not t:
            raise CloseError("Это не ссылка-приглашение в «Близкие».")
        return self._req("GET", "/close/peek", params={"t": t}).json()

    def accept(self, link):
        t = token_of(link)
        if not t:
            raise CloseError("Это не ссылка-приглашение в «Близкие».")
        self._keys()
        if not self.st["me"]:
            self.hello()
        d = self._req("POST", "/close/accept", {"t": t}).json()
        self._people(d)
        self.soon.set()
        return d.get("person") or {}

    # ---------- свои устройства: общее, что не должно лежать на сервере открытым (ключ умного дома) ----------
    def own_send(self, body):
        """Конверт всем своим устройствам (тот же аккаунт или связанный ключ). Шифруется их открытыми ключами — сервер
        видит только шифротекст. Приходит им в ящик как kind «own» -> host.own_apply(body)."""
        priv, pub = self._keys()
        if not self.st.get("me") or time.time() - float(self.st.get("hello_at") or 0) > 600:
            self.hello()
        targets = {d["dev"]: CC.b64d(d["pub"]) for d in (self.st.get("me") or {}).get("devs") or [] if d.get("pub") and d.get("dev")}
        targets.pop(self.st["dev"], None)
        if not targets:
            return False                                # других своих устройств пока нет
        targets[self.st["dev"]] = CC.b64d(pub)          # и себе — своё эхо из ящика откроется и будет пропущено
        env = CC.encrypt_for(dict(body, ts=int(time.time() * 1000)), priv, self.st["dev"], targets)
        self._req("POST", "/close/self", {"env": env})
        return True

    def _own_quiet(self, body):
        try:
            self.own_send(body)
        except Exception as e:  # noqa: BLE001 — нет связи: дойдёт со следующим изменением или новым устройством
            log.info("свои устройства: не отправилось: %s", e)

    # ---------- вложения заметок со своего телефона ----------
    # Телефон кладёт фото и файлы заметки зашифрованными в /close/file (себе) и шлёт своим устройствам конверт «own»
    # {natt: {note, title, files: [{id, key, name, type, size, aid}]}}. Сама заметка (текст) приходит синхронизацией
    # (sync.py, «note:<id>») — может позже конверта, поэтому вложения ждут её в st["natt"] до NATT_WAIT; файл кладём
    # рядом с заметкой (workspace.note_attach), строку-ссылку — в конец её текста. Уже положенные — по aid в natt_done.
    def _natt_add(self, natt):
        # «pc…» — вложения, которые отправил компьютер (natt_share): они уже лежат у заметки на нём; другому компьютеру
        # их не класть — его копия заметки пришла синхронизацией вместе со строками-ссылками, вышли бы двойники
        files = [f for f in natt.get("files") or [] if isinstance(f, dict) and f.get("id") and f.get("key")
                 and (not str(f.get("aid") or "").startswith("pc") or self._natt_rel(f.get("rel")))][:12]
        if not files or not str(natt.get("note") or ""):
            return
        with self._lock:
            q = self.st.setdefault("natt", [])
            q[:] = [x for x in q if x.get("note") != natt["note"]] + [{"note": str(natt["note"]), "title": str(natt.get("title") or "")[:120],
                                                                          "files": files, "at": time.time()}]
            del q[:-50]
            self._save()
        self._natt_kick()

    def _natt_rel(self, rel):
        """Файл с другого компьютера с путём (блокнот, core/pad.py): кладётся туда же, где лежал там, если его здесь ещё
        нет. -> путь от корня папки ассистента или "" (без пути, не «Заметки/…», или уже есть — не нужен)."""
        rel = str(rel or "")
        if not rel.startswith("Заметки/") or ".." in rel.split("/") or "\\" in rel:
            return ""
        try:
            return "" if self.host.workspace.safe(rel).exists() else rel
        except Exception:  # noqa: BLE001
            return ""

    def _natt_kick(self):
        if not getattr(self, "_natt_busy", False):
            self._natt_busy = True
            threading.Thread(target=self._natt_run, daemon=True).start()

    def _natt_run(self):
        try:
            for job in list(self.st.get("natt") or []):
                try:
                    if self._natt_one(job) or time.time() - float(job.get("at") or 0) > NATT_WAIT:
                        with self._lock:
                            self.st["natt"] = [x for x in self.st.get("natt") or [] if x is not job]
                            self._save()
                except Exception as e:  # noqa: BLE001 — нет связи: попробуем со следующей проверкой ящика
                    log.info("вложения заметки с телефона: пока не получилось: %s", e)
        finally:
            self._natt_busy = False

    def _natt_one(self, job):
        """-> True — всё положено (или класть некуда насовсем); False — заметка ещё не пришла синхронизацией."""
        rel = getattr(self.host, "note_rel_of", lambda nid: None)(job["note"])
        if not rel:
            return False
        ws = self.host.workspace
        p = ws.safe(rel)
        done = self.st.setdefault("natt_done", [])
        lines = []
        for f in job["files"]:
            aid = str(f.get("aid") or f["id"])
            if aid in done:
                continue
            if aid.startswith("pc"):                       # с другого компьютера — на то же место, строк в текст не добавляем
                to = self._natt_rel(f.get("rel"))
                if to:
                    r = self._req("GET", "/close/file", params={"id": f["id"]}, timeout=120)
                    dst = ws.safe(to)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(CC.unseal(CC.b64d(f["key"]), r.content))
                with self._lock:
                    done.append(aid)
                    del done[:-2000]
                    self._save()
                continue
            r = self._req("GET", "/close/file", params={"id": f["id"]}, timeout=120)
            data = CC.unseal(CC.b64d(f["key"]), r.content)
            name = str(f.get("name") or "файл")
            if not Path(name).suffix:                      # «фото» с телефона — без расширения: по типу
                name += mimetypes.guess_extension(str(f.get("type") or "")) or (".jpg" if f.get("type") == "image" else "")
            lines.append(ws.note_attach(rel, name, data)["line"])
            with self._lock:
                done.append(aid)
                del done[:-2000]
                self._save()
        if lines:
            text = p.read_text(encoding="utf-8").rstrip("\n")
            p.write_text(text + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
            log.info("📎 к заметке «%s» с телефона: вложений %d", job.get("title") or p.stem, len(lines))
            sy = getattr(self.host, "sync", None)
            if sy is not None:
                sy.soon.set()
            self.host.emit("notes_changed")
        return True

    def natt_share(self, note, title, files):
        """Фото и файлы заметки этого компьютера — своим телефонам (обратно к _natt_add; на телефоне — ownApply → nattTake):
        каждый файл шифруется своим ключом и кладётся в /close/file себе, ключи — в конверте own {natt}. files — [(путь от
        корня папки ассистента, Path)]; aid «pc» + отпечаток пути: телефон кладёт каждый файл один раз и не шлёт обратно.
        -> сколько отправлено (0 — других своих устройств нет)."""
        self._keys()
        if not self.st.get("me") or time.time() - float(self.st.get("hello_at") or 0) > 600:
            self.hello()
        me = self.st.get("me") or {}
        if not me.get("pid") or not any(d.get("dev") and d.get("dev") != self.st["dev"] for d in me.get("devs") or []):
            return 0
        out = []
        for rel, path in list(files)[:12]:
            data = path.read_bytes()
            if not data or len(data) > FILE_MAX:
                continue
            fk = os.urandom(32)
            d = self._req("POST", "/close/file", raw=CC.seal(fk, data), params={"to": me["pid"]}, timeout=120).json()
            out.append({"id": d["id"], "key": CC.b64e(fk), "name": path.name, "size": len(data), "rel": str(rel),
                        "type": mimetypes.guess_type(path.name)[0] or "", "aid": "pc" + hashlib.sha1(str(rel).encode("utf-8")).hexdigest()[:14]})
        if out:
            self.own_send({"natt": {"note": str(note), "title": str(title or "")[:120], "files": out}})
            log.info("📎 вложения заметки «%s» — своим телефонам: %d", title, len(out))
        return len(out)

    # ---------- «Рефералы»: свой первый уровень — в «Близкие» с согласия ----------
    def ref_map(self, rids):
        """Знаки связи из ref_info -> {rid: {pid} — уже близкий | {offered} — позвали, ждём ответа}."""
        rids = [str(r) for r in (rids or []) if r][:120]
        return self._req("POST", "/close/refs", {"rids": rids}).json().get("map") or {} if rids else {}

    def ref_close(self, rid):
        """«Позвать в Близкие» реферала. -> {person} — уже (или сразу, если он тоже звал) близкий; {offered} — ждём согласия."""
        self._keys()
        if not self.st["me"]:
            self.hello()
        d = self._req("POST", "/close/ref", {"rid": str(rid or "")}).json()
        if d.get("person"):
            self._people(d)
            self.soon.set()
            return {"person": d["person"]}
        return {"offered": True}

    def offer(self, pid, yes):
        """Ответ на «… зовёт вас в «Близкие»»: yes — близкие оба. -> состояние."""
        self._keys()
        if not self.st["me"]:
            self.hello()
        self._people(self._req("POST", "/close/offer", {"pid": pid, "yes": bool(yes)}).json())
        self.soon.set()
        return self.state()

    def remove(self, pid):
        self._people(self._req("POST", "/close/remove", {"pid": pid}).json())
        return self.state()

    def forget(self, pid, mids=None):
        """Убрать сообщения из переписки на этом устройстве (отзыв 17.10: «очистить диалоги с близкими нельзя, или
        выборочно поудалять лишнее» — перед съёмкой). mids — какие (mid), None — всю переписку. У близкого и на других
        ваших устройствах всё остаётся: история хранится на каждом устройстве своя. -> {removed, state}."""
        with self._lock:
            h = self.st["hist"].get(pid) or []
            if mids is None:
                keep = []
            else:
                drop = {str(m) for m in mids}
                keep = [x for x in h if str(x.get("mid") or "") not in drop]
            n = len(h) - len(keep)
            if keep:
                self.st["hist"][pid] = keep
            else:
                self.st["hist"].pop(pid, None)
            if not keep:
                self.st["unread"].pop(pid, None)
            self._save()
        self.host.emit("close", state=self.state())
        return {"removed": n, "state": self.state()}

    def person(self, who):
        """pid или имя («Андрею», «маме») -> запись человека; нет — CloseError с подсказкой."""
        with self._lock:
            people = list(self.st["people"])
        p = next((x for x in people if x["pid"] == who), None) or match_name(who, people)
        if not p:
            names = ", ".join(x["name"] for x in people) or "пока никого"
            raise CloseError(f"Не нашла «{who}» среди близких (сейчас: {names}). Добавить — студия → «Близкие» → «Пригласить».")
        return p

    # ---------- отправка ----------
    def _targets(self, p):
        devs = {d["dev"]: CC.b64d(d["pub"]) for d in p.get("devs") or [] if d.get("pub")}
        devs.update({d["dev"]: CC.b64d(d["pub"]) for d in (self.st.get("me") or {}).get("devs") or [] if d.get("pub")})
        devs[self.st["dev"]] = CC.b64d(self._keys()[1])
        return devs

    def send(self, who, text="", files=None, kind="msg", payload=None):
        """Сообщение близкому (text и/или файлы — список путей). -> запись истории."""
        p = self.person(who)
        priv, _ = self._keys()
        if not self.st.get("me") or time.time() - float(self.st.get("hello_at") or 0) > 600:
            self.hello()
            p = self.person(p["pid"])
        if not p.get("devs"):
            raise CloseError(f"У {p['name']} Dewiar ещё не открывался после приглашения — сообщение дойдёт, когда откроет.")
        fl = []
        for path in files or []:
            fl.append(self._upload(p, Path(path)))
        body = dict(payload or {}, t=(text or "").strip(), ts=int(time.time() * 1000), mid=uuid.uuid4().hex[:16],
                    name=(self.st.get("me") or {}).get("name", ""))
        if fl:
            body["f"] = fl
        if kind == "msg" and not body["t"] and not fl:
            raise CloseError("пустое сообщение")
        env = CC.encrypt_for(body, priv, self.st["dev"], self._targets(p))
        d = self._req("POST", "/close/send", {"to": p["pid"], "env": env, "kind": kind}).json()
        if kind != "msg":
            return d
        item = {"mid": body["mid"], "ts": body["ts"], "out": True, "t": body["t"], "f": [dict(x, path=str(Path(f).resolve())) for x, f in zip(fl, files or [])],
                "sid": _int(d.get("id"))}                 # номер письма у близкого: по нему «доставлено» и «прочитано»
        self._add(p["pid"], item)
        log.info("💌 Близким: %s ← %s", p["name"], f"текст, {len(body['t'])} зн." if body["t"] else "файл")   # содержимое — не в журнал
        return item

    # ---------- реакции (отзыв 13.10: 👍🤝✋😁😊😂😳🤔😱❤️ на сообщения) ----------
    # Реакция — обычное сообщение {re: mid, e, t: e}: новые программы (здесь и app.js на телефоне) ставят её значком на
    # сообщение mid, а старые покажут просто «👍». В истории: item["rx"] = {"me": …, "them": …}.
    def react(self, who, mid, e):
        p = self.person(who)
        e = str(e or "")[:8]
        priv, _ = self._keys()
        if not p.get("devs"):
            raise CloseError(f"У {p['name']} Dewiar ещё не открывался — реакция не дойдёт.")
        was = ((next((x for x in self.st["hist"].get(p["pid"]) or [] if x.get("mid") == mid), None) or {}).get("rx") or {}).get("me", "")
        if not self._react(p["pid"], mid, "me", e):
            raise CloseError("такого сообщения нет")
        body = {"re": mid, "e": e, "t": e, "ts": int(time.time() * 1000), "mid": uuid.uuid4().hex[:16], "name": (self.st.get("me") or {}).get("name", "")}
        try:
            env = CC.encrypt_for(body, priv, self.st["dev"], self._targets(p))
            self._req("POST", "/close/send", {"to": p["pid"], "env": env, "kind": "msg"})
        except Exception:
            self._react(p["pid"], mid, "me", was)
            raise
        return {"ok": True}

    def _react(self, pid, mid, who, e):
        with self._lock:
            m = next((x for x in self.st["hist"].get(pid) or [] if x.get("mid") == mid), None)
            if m is None:
                return False
            rx = dict(m.get("rx") or {})
            if e:
                rx[who] = e
            else:
                rx.pop(who, None)
            m["rx"] = rx
            self._save()
        self.host.emit("close", state=self.state())
        return True

    def _upload(self, p, path):
        data = path.read_bytes()
        if len(data) > FILE_MAX:
            raise CloseError(f"«{path.name}» больше 10 МБ — такие пока не отправить.")
        fk = os.urandom(32)
        d = self._req("POST", "/close/file", raw=CC.seal(fk, data), params={"to": p["pid"]}).json()
        return {"id": d["id"], "name": path.name, "size": len(data), "type": mimetypes.guess_type(path.name)[0] or "", "key": CC.b64e(fk)}

    def _add(self, pid, item):
        with self._lock:
            h = self.st["hist"].setdefault(pid, [])
            if any(x.get("mid") == item.get("mid") for x in h):
                return False
            h.append(item)
            h.sort(key=lambda x: x.get("ts", 0))
            del h[:-HIST_MAX]
            self._save()
        self.host.emit("close", state=self.state())
        return True

    # ---------- приём ----------
    def poll(self):
        """Забрать новое. -> сколько новых входящих сообщений."""
        priv, _ = self._keys()
        d = self._req("GET", "/close/inbox", params={"after": int(self.st["cursor"]), "geo": 1}).json()   # и места для радара
        got, refreshed = 0, False
        for it in d.get("items") or []:
            try:                                   # одно кривое сообщение не должно стопорить весь ящик
                n, refreshed = self._take(it, priv, refreshed)
                got += n
            except Exception:  # noqa: BLE001
                log.exception("близкие: сообщение %s пропущено", it.get("id") if isinstance(it, dict) else "?")
        with self._lock:
            self.st["cursor"] = max(int(self.st["cursor"]), int(d.get("last") or 0))
            self._save()
        if self.st.get("natt"):
            self._natt_kick()
        marks = d.get("marks")
        if isinstance(marks, dict):                  # мои письма у близких: доставлено / прочитано до номера
            mk = {str(k): [_int(v[0]), _int(v[1])] for k, v in marks.items() if isinstance(v, list) and len(v) == 2}
            if mk != self.st.get("marks"):
                with self._lock:
                    self.st["marks"] = mk
                    self._save()
                got = got or -1                      # сообщений нет, а отметки сменились — студии перерисовать
        if got:
            self.host.emit("close", state=self.state())
        return max(got, 0)

    def _take(self, it, priv, refreshed):
        """Одно входящее из ящика. -> (1, если новое сообщение — для счёта, обновлён ли список устройств)."""
        if it.get("kind") == "ring":                    # признак звонка — для телефона в фоне; сам звонок — в «sig»
            return 0, refreshed
        env, peer = it.get("env") or {}, it.get("peer", "")
        pub = self._pub_of(peer, env.get("fd", ""), it.get("out"))
        if pub is None and not refreshed:
            refreshed = True
            try:
                self.hello()
            except CloseError:
                pass
            pub = self._pub_of(peer, env.get("fd", ""), it.get("out"))
        if pub is None:
            log.info("близкие: неизвестное устройство %s — пропускаю", env.get("fd"))
            return 0, refreshed
        try:
            body = CC.decrypt_from(env, priv, self.st["dev"], pub)
        except CC.CloseCryptoError as e:
            log.info("близкие: не открылось (%s)", e)
            return 0, refreshed
        if not isinstance(body, dict):
            return 0, refreshed
        if it.get("kind") == "sig":
            self._sig(peer, it.get("name", ""), body)
            return 0, refreshed
        if it.get("kind") == "geo":                     # место близкого для радара «Рядом» (телефон, app.js radPush)
            if not it.get("out"):
                self._geo(peer, body.get("g"))
            return 0, refreshed
        if it.get("kind") == "own":                     # от своего же устройства (ключ шифрования — из моих устройств)
            if it.get("out") and env.get("fd") != self.st["dev"]:
                if isinstance(body.get("natt"), dict):  # фото и файлы заметки с телефона — к той же заметке здесь
                    self._natt_add(body["natt"])
                if isinstance(body.get("mygeo"), dict):  # где мой телефон — центр радара на компьютере
                    self._geo("", body["mygeo"], mine=True)
                try:
                    getattr(self.host, "own_apply", lambda b: None)(body)
                    snap = body.get("want") and getattr(self.host, "own_snapshot", lambda: None)()
                    if snap:                            # другое моё устройство просит — отдаём, что есть
                        threading.Thread(target=self._own_quiet, args=(snap,), daemon=True).start()
                except Exception:  # noqa: BLE001
                    log.exception("свои устройства: не применилось")
            return 0, refreshed
        if body.get("re"):                              # реакция на сообщение — значком на нём, а не новым сообщением
            if self._react(peer, str(body["re"]), "me" if it.get("out") else "them", str(body.get("e") or "")[:8]) and not it.get("out"):
                self.host.emit("close_react", pid=peer, mid=str(body["re"]), e=str(body.get("e") or "")[:8], name=it.get("name") or "")
            return 0, refreshed
        item = {"mid": body.get("mid") or str(it.get("id")), "ts": _int(body.get("ts")) or _int(it.get("ts")) * 1000, "out": bool(it.get("out")),
                "t": str(body.get("t") or "")[:20000], "f": [x for x in body.get("f") or [] if isinstance(x, dict)][:10],
                "sid": _int(it.get("rid")) if it.get("out") else _int(it.get("id"))}   # номер письма в ящике получателя
        if body.get("wave"):
            item["wave"] = 1
        if not self._add(peer, item) or item["out"]:
            return 0, refreshed
        if body.get("wave"):                            # 👋 с радара — для студии: волны от кружка близкого
            self.host.emit("close_wave", pid=peer, name=it.get("name") or "")
        name = it.get("name") or "близкого"
        with self._lock:
            self.st["unread"][peer] = int(self.st["unread"].get(peer, 0)) + 1
            self._save()
        self.host.emit("close_msg", pid=peer, name=name, text=item["t"], files=[x.get("name") for x in item["f"]])
        if item["f"]:
            threading.Thread(target=self._fetch_files, args=(peer, name, item), daemon=True).start()
        self._tell(name, item)
        return 1, refreshed

    def _pub_of(self, peer, dev, out):
        who = self.st.get("me") if out else next((p for p in self.st["people"] if p["pid"] == peer), None)
        for d in (who or {}).get("devs") or []:
            if d.get("dev") == dev:
                return CC.b64d(d["pub"])
        if out and dev == self.st["dev"]:
            return CC.b64d(self._keys()[1])
        return None

    def _tell(self, name, item):
        """Вслух и в окна: «Сообщение от Михаила: …» (если не выключено в студии)."""
        files = item.get("f") or []
        what = item["t"] or ""
        if files:
            what = (what + " " if what else "") + ("Файл «" + files[0].get("name", "") + "»." if len(files) == 1 else f"Файлов: {len(files)}.")
        text = f"{name} пишет: {what}".strip()              # без склонения имени: «Анна пишет: …»
        if item.get("wave"):                            # 👋 с радара «Рядом» на телефоне — «Анна машет вам»
            what, text = "машет вам 👋", f"{name} машет вам!"
        try:
            self.host.push(f"💌 {name}", what or "сообщение", telegram=False)
        except TypeError:
            self.host.push(f"💌 {name}", what or "сообщение")
        if self.host.s.get("close", "speak") is not False:
            self.host.announce(text[:600])

    def _fetch_files(self, pid, name, item):
        """Скачать и расшифровать файлы в папку ассистента «Близкие/<имя>»."""
        base = (Path(self.host.workspace.root) / "Близкие").resolve()
        root = base / safe_name(name)
        if root.resolve().parent != base:                   # имя придумал собеседник — из «Близких» не выходим
            root = base / "без имени"
        for f in item.get("f") or []:
            try:
                r = self._req("GET", "/close/file", params={"id": f["id"]}, timeout=120)
                data = CC.unseal(CC.b64d(f["key"]), r.content)
                root.mkdir(parents=True, exist_ok=True)
                safe = safe_name(f.get("name"), "файл")
                out = root / safe
                n = 1
                while out.exists() and hashlib.sha1(out.read_bytes()).hexdigest() != hashlib.sha1(data).hexdigest():
                    out = root / f"{Path(safe).stem} ({n}){Path(safe).suffix}"
                    n += 1
                out.write_bytes(data)
                f["path"] = str(out)
            except (CloseError, CC.CloseCryptoError, OSError, KeyError) as e:
                f["error"] = str(e)
                log.info("близкие: файл %s не скачался: %s", f.get("name"), e)
        with self._lock:
            for x in self.st["hist"].get(pid) or []:
                if x.get("mid") == item["mid"]:
                    x["f"] = item["f"]
            self._save()
        self.host.emit("close", state=self.state())

    # ---------- фон ----------
    def active(self):
        return bool(self.st["people"] or (self.st.get("invite") and time.time() < _int(self.st["invite"].get("expires"))))

    def loop(self, stopping):
        time.sleep(8)
        while not stopping.is_set():
            try:
                import egress
                token = self.host.credentials()[0]
                if egress.local_only():                      # стоп-кран: «Близкие» на паузе
                    self.error = "на паузе: включён режим «Ничего не уходит в интернет»"
                    token = ""
                if token:
                    if time.time() - float(self.st.get("hello_at") or 0) > 3600:   # раз в час: новые близкие и «зовут в Близкие»
                        self.hello()
                    self.poll()
                    self.error = ""
            except CloseError as e:
                self.error = str(e)
                log.info("Близкие: %s", e)
            except ValueError as e:      # ответ сайта оборвался или пришла страница ошибки вместо JSON — повторим (пакет 23.10, №209)
                log.info("Близкие: сайт ответил не так, как ждали (%s) — повторю", e)
            except Exception:  # noqa: BLE001
                log.exception("Близкие")
            try:
                wait = 1 if self._fast() else 6 if self.active() else 600
            except Exception:  # noqa: BLE001 — поток опроса не должен умирать
                log.exception("Близкие: пауза")
                wait = 60
            self.soon.wait(wait)
            self.soon.clear()

    # ---------- звонки (страница ui/call.html в браузере, assets/call.js — WebRTC) ----------
    CALL_CMDS = ("call_info", "call_sig", "call_ice", "call_fast", "call_done")

    def _fast(self):
        """Идёт звонок — опрос раз в секунду (сигналы WebRTC не должны ждать)."""
        now = time.time()
        for cid, c in list(self.calls.items()):
            if now - c["at"] > 4 * 3600:
                self.calls.pop(cid, None)
        return any(self._live(c, now) for c in list(self.calls.values()))

    @staticmethod
    def _live(c, now):
        """Звонок идёт: страница звонка жива (напоминает о себе раз в 20 с; закрыли вкладку — через 90 с уже нет)."""
        return bool(c.get("fast")) and not c.get("ended") and now - c.get("seen", c["at"]) < 90 and now - c["at"] < 4 * 3600

    def _open_call(self, c):
        import callpage
        token = "c-" + uuid.uuid4().hex
        self.host.bridge.allow(token, self.CALL_CMDS)
        url = f"{callpage.base()}/call.html?call={c['call']}&token={token}&port={self.host.bridge.port}"
        from tools import launch
        launch(["xdg-open", url])
        return url

    def call(self, who, video=False):
        """Позвонить близкому: открыть страницу звонка в браузере (она сама звонит). -> {call, name}."""
        p = self.person(who)
        if not p.get("devs"):
            raise CloseError(f"У {p['name']} Dewiar ещё не открывался — позвонить пока нельзя.")
        cid = uuid.uuid4().hex[:12]
        c = self.calls[cid] = {"call": cid, "role": "caller", "pid": p["pid"], "name": p["name"], "video": bool(video), "offer": "", "at": time.time(), "fast": True}
        self.soon.set()
        try:                                            # открытый признак «звонят»: у близкого с закрытым приложением
            self._req("POST", "/close/send", {"to": p["pid"], "kind": "ring", "env": {"v": 0, "video": bool(video)}})   # зазвонит телефон
        except CloseError:
            pass
        self._open_call(c)
        return {"call": cid, "name": p["name"]}

    def _sig(self, peer, name, body):
        s = (body or {}).get("s") or {}
        if s.get("type") == "ring":
            if time.time() * 1000 - _int(s.get("ts")) > 60000 or s.get("call") in self.calls:
                return
            if not re.fullmatch(r"[0-9a-z]{6,32}", str(s.get("call") or "")):           # id звонка уходит в адрес страницы
                return
            if any(self._live(c, time.time()) for c in list(self.calls.values())):
                try:                                   # уже идёт звонок — «занято»
                    self.send(peer, kind="sig", payload={"s": {"type": "busy", "call": s.get("call")}})
                except CloseError:
                    pass
                return
            p = next((x for x in self.st["people"] if x["pid"] == peer), None)
            if not p:
                return
            c = self.calls[s["call"]] = {"call": s["call"], "role": "callee", "pid": peer, "name": p["name"], "video": bool(s.get("video")),
                                         "offer": s.get("sdp") or "", "at": time.time(), "fast": True}
            log.info("📞 Звонит %s", p["name"])
            self.soon.set()
            self._open_call(c)
            try:
                self.host.push(f"📞 {p['name']}", "видеозвонок" if c["video"] else "звонит", telegram=False)
            except TypeError:
                self.host.push(f"📞 {p['name']}", "звонит")
            self.host.emit("close_ring", pid=peer, name=p["name"], video=c["video"])
            if self.host.s.get("close", "speak") is not False:     # окно звонка в браузере может не сыграть звонок само
                self.host.announce(f"{p['name']} звонит{' по видео' if c['video'] else ''}. Окно звонка открыто.")
            return
        self.host.emit("close_sig", peer=peer, name=name, sig=body)

    def call_cmd(self, cmd, a):
        """Команды страницы звонка (временный токен — только они)."""
        c = self.calls.get(a.get("call", ""))
        if cmd == "call_ice":
            return self._req("GET", "/close/ice").json().get("iceServers") or []
        if not c:
            raise CloseError("звонок уже закончился")
        c["seen"] = time.time()                              # страница звонка жива
        if cmd == "call_info":
            return {"call": c["call"], "role": c["role"], "video": c["video"], "offer": c["offer"],
                    "peer": {"pid": c["pid"], "name": c["name"], "color": _color_of(c["pid"])}}
        if cmd == "call_sig":
            self.send(c["pid"], kind="sig", payload={"s": dict(a.get("s") or {}, call=c["call"])})
            return {"ok": True}
        if cmd == "call_fast":
            c["fast"] = bool(a.get("on"))
            self.soon.set()
            return {"ok": True}
        if cmd == "call_done":
            c["ended"], c["fast"] = True, False
            secs = int(a.get("secs") or 0)
            t = f"📞 Звонок · {secs // 60:02d}:{secs % 60:02d}" if secs else "📞 " + (a.get("reason") or "Звонок")
            self._add(c["pid"], {"mid": "call" + c["call"] + c["role"], "ts": int(time.time() * 1000), "out": c["role"] == "caller", "t": t, "call": True})
            self.host.emit("call_end", call=c["call"])
            return {"ok": True}
        raise CloseError("неизвестная команда звонка")

    # ---------- для помощницы ----------
    def prompt(self):
        with self._lock:
            names = [p["name"] for p in self.st["people"]]
        if not names:
            return ""
        return ("\n\nБЛИЗКИЕ (переписка с их помощниками Dewiar, сообщения шифруются): " + ", ".join(names)
                + ". «Напиши/передай/скажи Андрею…» кому-то из них — инструмент close_send (дойдёт в его Dewiar, он услышит вслух); "
                  "«что мне писали», «что ответила мама» — close_read; «позвони маме» — close_call (откроется окно звонка; «по видео» — video true). Имя может быть в любой форме "
                  "(«Люде» = Людмила, «Исаевой Людмиле» = Людмила Исаева) — люди из этого списка ВСЕГДА через Dewiar, в первую очередь. "
                  "Другим людям (не из этого списка) — как обычно, мессенджерами.")

    def recent(self, who="", n=8):
        with self._lock:
            people = list(self.st["people"])
        ps = [self.person(who)] if who else people
        out = []
        for p in ps:
            for m in (self.st["hist"].get(p["pid"]) or [])[-n:]:
                out.append((m.get("ts", 0), f"{time.strftime('%d.%m %H:%M', time.localtime(m.get('ts', 0) / 1000))} "
                                            f"{'вы → ' + p['name'] if m.get('out') else p['name']}: {m.get('t') or ''}"
                                            + (f" [файлы: {', '.join(x.get('name', '') for x in m.get('f') or [])}]" if m.get("f") else "")
                                            + _rx_text(m.get("rx"), p["name"]) + _mark_text(m, (self.st.get("marks") or {}).get(p["pid"]))))
            self.st["unread"].pop(p["pid"], None)
            self._mark_read(p["pid"])
        self._save()
        out.sort()
        return "\n".join(x for _, x in out[-n * 2:]) or "Сообщений пока нет."
