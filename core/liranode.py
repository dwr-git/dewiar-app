"""«Нода Лиры» (0.87, владелец 11.11: «децентрализация спрятана далеко — нужен простой отдельный раздел»): компьютер
человека сам отвечает на часть общих вопросов Сети Лиры своей моделью (Ollama, LM Studio, llama.cpp) — прямо внутри
Dewiar, без lira-node.py, sudo и Ubuntu. За принятые ответы — талеры на ИИ-баланс (правила — в подписанных правилах сети,
блок pay; считает только сайт, net_settle).

Как работает: «Стать нодой» → приглашение (/net/invite, ключ человека) → /net/register {kind: app} — сайт выдаёт ключ ноды
(nk-…, хранится только здесь, в STATE_DIR/liranode.json с правами 600, не в настройках — их видят окна) → поток «lira-node»:
проверяет подпись правил (liranet.check, ключ сети — тот же запомненный cloud.net_pub), условия (ниже), держит короткий
длинный опрос /net/pull (10 с), задание — в свою модель (только известные поля, model — своя, без потока, не дольше, чем
ждёт сайт), ответ — /net/done. Ушли условия — /net/away (её ещё не взятые обычные задания сразу уходят главному, без
штрафа); задание пришло в ту же секунду, что сел за игру, — /net/done {away: true}. «Выключить» — /net/away и поток стоит;
«Перестать быть нодой» — /net/leave и ключ стирается.

Условия (ничего без кнопки человека; нагрузка — только когда можно):
• «Когда работать»: idle — компьютер простаивает (мышь и клавиатура не тронуты IDLE_AFTER с), night — с 0 до 7, always;
• никогда: от батареи, в игре и полноэкранном режиме (Windows — SHQueryUserNotificationState; X11 — _NET_WM_STATE_FULLSCREEN),
  пока человек говорит с Лирой (и 90 с после), видеокарта горячая (≥ GPU_HOT °C) или занята не нами (≥ GPU_BUSY %),
  процессор занят (≥ CPU_BUSY %), сеть выключена владельцем Dewiar или правила не подписаны;
• «Сколько отдавать»: SHARE — не больше N ответов в час и отдых между ответами.

Узел видит только текст общего вопроса (сайт отрезает историю, память, справки; имена и телефоны — метками). Журнал
честный, но без чужих текстов: время, сколько знаков пришло и ушло, сколько секунд, итог — текст чужого вопроса не
сохраняется и не показывается."""
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time

log = logging.getLogger("dewiar.liranode")

IDLE_AFTER = 300            # «простаивает» — 5 минут без мыши и клавиатуры
NIGHT = (0, 7)              # «ночью» — с 0:00 до 7:00 по часам компьютера
GPU_HOT = 80                # °C — выше: пауза, видеокарта остывает
GPU_BUSY = 50               # % загрузки видеокарты не нами — игра, видео, рендер
CPU_BUSY = 80               # % процессора
TALK_REST = 90              # с после разговора с Лирой — модель нужна ей
POLL_WAIT = 10              # длинный опрос — 10 с: ушли условия — узнаём быстро
JOURNAL_MAX = 80
WHEN = {"idle": "пока компьютер простаивает", "night": "ночью, с 0 до 7", "always": "всегда, пока Dewiar открыт"}
# сколько отдавать: (ответов в час, отдых между ответами, с)
SHARE = {"low": (20, 20), "half": (60, 5), "all": (0, 0)}
SHARE_TEXT = {"low": "немного — до 20 ответов в час", "half": "побольше — до 60 в час", "all": "сколько попросят"}
JOB_CHARS = 8000          # всё задание (все тексты) — не больше 8 тыс. знаков: общий вопрос и короткий системный текст
JOB_MSGS = 6
PULL_MAX = 262_144        # ответ сайта на опрос больше 256 КБ — не читаем (задание и так ≤ JOB_CHARS)
LOCAL_HOSTS = ("127.0.0.1", "::1", "localhost")


def _private(host):
    import ipaddress
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def relay_url_ok(u, me, pub):
    """Ретранслятор (urlsplit-ы): u — его адрес, me — куда нода ходит сейчас (дома — адрес сайта в сети), pub — адрес сайта
    из настроек. wss — того же сайта (или его публичного имени); ws (без шифрования) — только тот же адрес в домашней сети
    или на этой машине: так же, как нода дома и так ходит на сайт (12.11: дома нода ходила на 192.168.1.46, а ей
    предлагали wss://dewiar.pro — имена не совпали, и она молча оставалась на опросе)."""
    h = u.hostname or ""
    if not h or u.scheme not in ("wss", "ws"):
        return False
    if u.scheme == "wss":
        return h in (me.hostname, pub.hostname)
    return h == me.hostname and (h in LOCAL_HOSTS or _private(h))
THINK_RX = re.compile(r"<think>.*?(?:</think>|$)", re.S)


class NodeError(Exception):
    pass


# --------------------------------------------------- компьютер: можно ли сейчас ---------------------------------------------------
class Sys:
    """Замеры компьютера. Каждый — None, если не узнать (тогда это условие не мешает работать, кроме «простаивает»).
    В проверках подменяются (liranode.SYS.on_battery = lambda: True)."""

    def __init__(self):
        self._gpu = (0.0, None)
        self._cpu_primed = False

    def idle_s(self):
        try:
            import presence
            return presence.idle_seconds()
        except Exception:  # noqa: BLE001
            return None

    def on_battery(self):
        """True — работает от батареи (ноутбук без зарядки)."""
        try:
            if os.name == "nt":
                import sleepguard
                return not sleepguard._on_ac()
            if sys.platform == "darwin":
                out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3).stdout
                return "Battery Power" in out
            from pathlib import Path
            ps = Path("/sys/class/power_supply")
            if not ps.is_dir():
                return None
            mains, bat = None, False
            for d in ps.iterdir():
                t = (d / "type").read_text().strip() if (d / "type").exists() else ""
                if t == "Mains" and (d / "online").exists():
                    mains = (d / "online").read_text().strip() == "1" or bool(mains)
                if t == "Battery" and (d / "status").exists() and (d / "status").read_text().strip() == "Discharging":
                    bat = True
            return bat if mains is None else (not mains)
        except Exception:  # noqa: BLE001
            return None

    def fullscreen(self):
        """True — игра, фильм или презентация на весь экран."""
        try:
            if os.name == "nt":
                import ctypes
                st = ctypes.c_int(0)
                if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(st)) == 0:
                    # 2 — полноэкранное окно, 3 — Direct3D на весь экран (игра), 4 — презентация, 7 — приложение на весь экран
                    return st.value in (2, 3, 4, 7)
                return None
            import shutil
            if sys.platform.startswith("linux") and os.environ.get("DISPLAY") and shutil.which("xprop"):
                a = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"], capture_output=True, text=True, timeout=2).stdout
                m = re.search(r"0x[0-9a-f]+", a)
                if not m or m.group(0) == "0x0":
                    return False
                w = subprocess.run(["xprop", "-id", m.group(0), "_NET_WM_STATE"], capture_output=True, text=True, timeout=2).stdout
                return "_NET_WM_STATE_FULLSCREEN" in w
        except Exception:  # noqa: BLE001
            pass
        return None

    def cpu(self):
        """Загрузка процессора, %."""
        try:
            import psutil
            if not self._cpu_primed:
                psutil.cpu_percent(None)
                self._cpu_primed = True
                time.sleep(0.3)
            return psutil.cpu_percent(None)
        except Exception:  # noqa: BLE001
            pass
        try:
            return min(100.0, os.getloadavg()[0] / max(1, os.cpu_count() or 1) * 100)
        except (AttributeError, OSError):
            return None

    def gpu(self, fresh=False):
        """NVIDIA: {name, mem_gb, temp, util} (nvidia-smi, раз в 15 с) или None."""
        at, v = self._gpu
        if not fresh and time.time() - at < 15:
            return v
        v = None
        try:
            kw = {"creationflags": 0x08000000} if os.name == "nt" else {}      # CREATE_NO_WINDOW — без окна консоли
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5, **kw).stdout
            best = None
            for ln in out.splitlines():
                p = [x.strip() for x in ln.split(",")]
                if len(p) >= 4:
                    g = {"name": p[0], "mem_gb": round(float(p[1]) / 1024, 1), "temp": _num(p[2]), "util": _num(p[3])}
                    if not best or g["mem_gb"] > best["mem_gb"]:
                        best = g
            v = best
        except (OSError, ValueError, subprocess.SubprocessError):
            v = None
        if v is None and sys.platform == "darwin":
            try:
                chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=3).stdout.strip()
                if "Apple" in chip:
                    import device
                    v = {"name": chip + " (общая память)", "mem_gb": round(device.ram_gb()[0], 1), "temp": None, "util": None, "apple": True}
            except (OSError, subprocess.SubprocessError):
                pass
        self._gpu = (time.time(), v)
        return v


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


SYS = Sys()


def blocked(cfg, engine=None, now=None, me_busy=False):
    """Почему ноде сейчас нельзя работать (словами для человека) или "" — можно. cfg — состояние ноды (when, share)."""
    now = time.time() if now is None else now
    if SYS.on_battery():
        return "компьютер работает от батареи"
    if SYS.fullscreen():
        return "игра или фильм на весь экран"
    if engine is not None:
        st = getattr(engine, "state", "idle")
        last = getattr(engine, "last_turn_time", 0.0) or 0.0
        if st in ("thinking", "speaking") or (last and time.monotonic() - last < TALK_REST):
            return "вы говорите с Лирой — модель нужна ей"
    when = cfg.get("when") or "idle"
    if when == "idle":
        idle = SYS.idle_s()
        if idle is None:
            return "не узнать, простаивает ли компьютер, — выберите «ночью» или «всегда»"
        if idle < IDLE_AFTER:
            return "вы за компьютером — начну, когда он простоит " + str(IDLE_AFTER // 60) + " минут"
    elif when == "night":
        h = time.localtime(now).tm_hour
        if not (NIGHT[0] <= h < NIGHT[1]):
            return "сейчас не ночь — работаю с 0 до 7"
    if is_lan(cfg.get("base") or ""):
        return ""                                      # модель на сервере в сети — своя видеокарта и процессор ни при чём
    g = SYS.gpu()
    if g and g.get("temp") is not None and g["temp"] >= GPU_HOT:
        return f"видеокарта горячая ({int(g['temp'])} °C) — остывает"
    if g and g.get("util") is not None and g["util"] >= GPU_BUSY and not me_busy:
        return f"видеокарта занята другой программой ({int(g['util'])} %)"
    c = SYS.cpu()
    if c is not None and c >= CPU_BUSY and not me_busy:
        return f"процессор занят ({int(c)} %)"
    per_hour = SHARE.get(cfg.get("share") or "low", SHARE["low"])[0]
    if per_hour:
        hour = [x for x in cfg.get("done_ts") or [] if x > now - 3600]
        if len(hour) >= per_hour:
            return f"в этот час уже {len(hour)} ответов — столько вы разрешили"
    return ""


# ------------------------------------------------------------- модель -------------------------------------------------------------
def models_here(engine=None):
    """Свои модели: запущенные на этом компьютере Ollama, LM Studio, llama.cpp, vLLM (обычные порты) и свои профили «Мозга»
    с адресом 127.0.0.1 или своего сервера в домашней сети (is_lan). -> [{name, base_url, models, lan?}]."""
    import llm
    out, seen = [], set()
    try:
        for f in llm.discover_local(start=False):
            out.append({"name": f.get("name") or f.get("preset"), "base_url": f["base_url"], "models": f.get("models") or []})
            seen.add(f["base_url"].rstrip("/"))
    except Exception:  # noqa: BLE001
        pass
    if engine is not None:
        for p in (engine.s.get("llm", "profiles") or {}).values():
            b = str(p.get("base_url") or "").rstrip("/")
            if not is_own(b):
                continue
            if p.get("kind") == "ollama" and not b.endswith("/v1"):
                b += "/v1"
            if b in seen:
                continue
            ids = llm._models_at(b, 1.5)
            if ids is not None:
                out.append({"name": p.get("name") or "своя модель", "base_url": b, "models": ids, **({"lan": True} if is_lan(b) else {})})
                seen.add(b)
    return out


def is_local(base):
    """Адрес своей модели — только этот компьютер: хост целиком 127.0.0.1, ::1 или localhost, без имени и пароля в адресе
    (рецензия 0.87, М1: регулярка пропускала «http://127.0.0.1@evil.example» и «localhost.evil.example»)."""
    from urllib.parse import urlsplit
    try:
        u = urlsplit(str(base or ""))
        return u.scheme in ("http", "https") and u.username is None and u.password is None and (u.hostname or "") in LOCAL_HOSTS \
            and (u.port is None or 0 < u.port < 65536)
    except ValueError:
        return False


def is_lan(base):
    """Своя модель на сервере в домашней сети (№669, 12.11: «Ollama и мои серверы крутятся на другом железе»): адрес —
    частный IPv4 цифрами (10.x, 172.16–31.x, 192.168.x), без имени и пароля. Берётся только из своих профилей «Мозга» —
    сайт адрес модели не задаёт."""
    from urllib.parse import urlsplit
    import ipaddress
    try:
        u = urlsplit(str(base or ""))
        ip = ipaddress.IPv4Address(u.hostname or "")
        return u.scheme in ("http", "https") and u.username is None and u.password is None and ip.is_private \
            and not ip.is_loopback and not ip.is_link_local and (u.port is None or 0 < u.port < 65536)
    except ValueError:
        return False


def is_own(base):
    """Своя модель: на этом компьютере или на своём сервере в домашней сети."""
    return is_local(base) or is_lan(base)


def job_clean(body):
    """Задание сайта — что можно отдать своей модели (рецензия 0.87, С4: при взломе сайта нода не должна выполнять что
    угодно). Только строковые тексты; роли system и user (assistant — только текстом, без вызовов); все тексты вместе ≤
    JOB_CHARS; chat_template_kwargs — только {enable_thinking: bool}; действий (tools) нода не делает. -> (тело, "") или
    (None, почему)."""
    if not isinstance(body, dict):
        return None, "задание не по образцу"
    ms = body.get("messages")
    if not isinstance(ms, list) or not ms or len(ms) > JOB_MSGS:
        return None, "задание без вопроса или слишком длинное"
    out, chars = [], 0
    for m in ms:
        if not isinstance(m, dict) or set(m) - {"role", "content"} or m.get("role") not in ("system", "user", "assistant") \
                or not isinstance(m.get("content"), str):
            return None, "задание не по образцу"
        chars += len(m["content"])
        out.append({"role": m["role"], "content": m["content"]})
    if chars > JOB_CHARS or out[-1]["role"] != "user":
        return None, "задание слишком длинное или не вопрос"
    b = {"messages": out}
    try:
        b["max_tokens"] = max(1, min(1024, int(body.get("max_tokens") or 512)))
        b["temperature"] = max(0.0, min(2.0, float(body.get("temperature", 0.7))))
    except (TypeError, ValueError):
        return None, "задание с испорченными полями"
    k = body.get("chat_template_kwargs")
    if isinstance(k, dict) and set(k) <= {"enable_thinking"} and isinstance(k.get("enable_thinking", False), bool):
        b["chat_template_kwargs"] = dict(k)
    return b, ""


def ask_model(base, model, body, timeout):
    """Задание — своей модели (OpenAI-совместимый /chat/completions, без потока). -> (код, ответ сайту: чистый JSON или,
    если не вышло, причина — её сайту не отправляем, только код)."""
    import httpx
    if not is_own(base):
        return 0, "своя модель — только на этом компьютере или своём сервере в домашней сети"
    b, why = job_clean(body)
    if b is None:
        return 0, why
    b.update(model=model, stream=False)
    try:
        r = httpx.post(base.rstrip("/") + "/chat/completions", json=b, timeout=timeout)
    except httpx.HTTPError as e:
        return 0, "своя модель не ответила: " + str(e)[:120]
    if r.status_code != 200:
        return r.status_code, r.text[:300]
    try:
        j = r.json()
        m = j["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        return 0, "своя модель ответила не по образцу"
    text = THINK_RX.sub("", m.get("content") if isinstance(m.get("content"), str) else "").strip()   # размышления сайту не нужны
    msg = {"role": "assistant", "content": text[:6000]}                # действий нода не делает — только текст
    u = j.get("usage") or {}
    return 200, json.dumps({"choices": [{"message": msg, "finish_reason": "stop"}],
                            "usage": {"prompt_tokens": int(u.get("prompt_tokens") or 0), "completion_tokens": int(u.get("completion_tokens") or 0)}},
                           ensure_ascii=False)


def speed_test(base, model, timeout=30):
    """Замер: обычный общий вопрос, как пришёл бы от сети. -> {ok, s, chars, tps, text, error}."""
    body = {"messages": [{"role": "system", "content": "Ты — Лира, голосовой помощник. Отвечай коротко и по-русски."},
                         {"role": "user", "content": "Почему небо голубое? Ответь в двух-трёх предложениях."}],
            "max_tokens": 300, "temperature": 0.3, "chat_template_kwargs": {"enable_thinking": False}}
    t0 = time.monotonic()
    code, raw = ask_model(base, model, body, timeout)
    s = time.monotonic() - t0
    if code != 200:
        return {"ok": False, "s": round(s, 1), "error": raw[:200] if isinstance(raw, str) else "нет ответа"}
    j = json.loads(raw)
    text = j["choices"][0]["message"]["content"]
    toks = j["usage"]["completion_tokens"] or max(1, len(text) // 3)
    return {"ok": bool(text), "s": round(s, 1), "chars": len(text), "tps": round(toks / max(0.05, s), 1), "text": text[:160],
            "cyr": bool(re.search(r"[а-яё]", text, re.I)), "error": "" if text else "модель ответила пусто"}


# ------------------------------------------------------------- нода -------------------------------------------------------------
class Node:
    """Состояние (STATE_DIR/liranode.json, права 600) и поток ноды. Один объект на программу — engine.lnode."""

    def __init__(self, engine, path=None):
        from settings import STATE_DIR
        self.e = engine
        self.path = path or (STATE_DIR / "liranode.json")
        self.lock = threading.RLock()
        self.st = self._read()
        self.status = {"state": "off", "why": ""}       # off | wait | work | ready | error
        self.thread = None
        self.stop_ev = threading.Event()
        self.wake = threading.Event()
        self._me = (0.0, None)
        self._away_sent = True
        self._last_check = None
        # 0.92: ретранслятор — одно соединение WebSocket вместо опросов PHP (адрес даёт сам сайт в ответе опроса)
        self._ws = None
        self._ws_url = ""
        self._ws_next = 0.0
        self._ws_fails = 0
        self._ws_why = ""
        self._ws_ready = False

    # --- файл состояния
    def _read(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self):
        """Через временный файл, созданный сразу с правами 600 (рецензия 0.87, М2: без окна, когда ключ ноды виден всем)."""
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            data = json.dumps(self.st, ensure_ascii=False, indent=1).encode("utf-8")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
            for i in range(5):                          # Windows: антивирус на миг держит файл
                try:
                    os.replace(tmp, self.path)
                    break
                except PermissionError:
                    if i == 4:
                        raise
                    time.sleep(0.1 * (i + 1))

    def cfg(self):
        with self.lock:
            return {"when": self.st.get("when") or "idle", "share": self.st.get("share") or "low", "done_ts": list(self.st.get("done_ts") or []),
                    "base": self.st.get("base") or ""}

    def note(self, kind, text):
        """Запись в журнал: ok — ответила, skip — пауза/пропуск, err — ошибка, info — прочее. Без чужих текстов."""
        with self.lock:
            j = self.st.setdefault("journal", [])
            if j and j[-1].get("text") == text and kind in ("skip", "info"):
                j[-1]["t"] = int(time.time())               # то же самое — не плодить строки, только время
            else:
                j.append({"t": int(time.time()), "kind": kind, "text": text})
                del j[:-JOURNAL_MAX]
        self.save()

    def _count(self, chars_in, chars_out, ms):
        with self.lock:
            day = time.strftime("%Y-%m-%d")
            c = self.st.setdefault("count", {"day": day, "n": 0, "total": 0})
            if c.get("day") != day:
                c.update(day=day, n=0)
            c["n"] = c.get("n", 0) + 1
            c["total"] = c.get("total", 0) + 1
            ts = [x for x in self.st.get("done_ts") or [] if x > time.time() - 3600] + [int(time.time())]
            self.st["done_ts"] = ts
        self.note("ok", f"ответила на общий вопрос: пришло {chars_in} зн., ушло {chars_out} зн., {ms / 1000:.1f} с".replace(".", ","))

    def _set(self, state, why=""):
        if self.status.get("state") != state or self.status.get("why") != why:
            self.status = {"state": state, "why": why, "at": int(time.time())}
            try:
                self.e.emit("lnode", **self.public())
            except Exception:  # noqa: BLE001
                pass

    # --- сайт
    def _url(self):
        return self.st.get("url") or self.e.cloud.url

    def _fetch(self, path, body=None, timeout=20, limit=PULL_MAX):
        """Запрос ноды к сайту её ключом; ответ больше limit — не читаем (рецензия 0.87, С4). Ошибка — CloudError."""
        import httpx
        from cloud import api_base, CloudError
        try:
            with httpx.stream("POST", api_base(self._url()) + path, json=body if body is not None else {}, timeout=timeout,
                              headers={"Authorization": "Bearer " + (self.st.get("key") or "")}) as r:
                raw = b""
                for ch in r.iter_bytes():
                    raw += ch
                    if len(raw) > limit:
                        raise CloudError("сайт прислал слишком большой ответ — не читаю")
                code = r.status_code
        except httpx.HTTPError as e:
            raise CloudError("нет связи с dewiar.pro") from e
        try:
            d = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            d = {}
        if code >= 400 or not isinstance(d, dict):
            err = d.get("error") if isinstance(d, dict) else None
            raise CloudError((err.get("message") if isinstance(err, dict) else "") or f"сайт ответил {code}")
        return d

    def rules(self):
        """Правила сети с проверенной подписью (liranet.rules: тот же запомненный ключ сети) -> (правила, ошибка)."""
        import liranet
        r = liranet.rules(self.e)
        return (r.get("rules") or {}, "") if r.get("ok") else ({}, r.get("error") or "правила сети не получены")

    # --- проверка «подходит ли мой компьютер»
    def check(self, base="", model=""):
        """-> {ok, items: [{k, ok (True/False/None), title, text}], models, pick: {base, model}, speed}."""
        items, ok_all = [], True

        def add(k, ok, title, text):
            nonlocal ok_all
            items.append({"k": k, "ok": ok, "title": title, "text": text})
            if ok is False:
                ok_all = False
        acc = bool(self.e.cloud.key)
        add("account", acc, "Аккаунт dewiar.pro", "есть — талеры придут на ваш ИИ-баланс" if acc else "нужен вход: «Dewiar.pro» → войти или ключ")
        rr, err = self.rules()
        app = (rr.get("app") or {}) if rr else {}
        if err:
            add("rules", False, "Правила сети", err)
        elif not rr.get("on"):
            add("rules", False, "Правила сети", "подписаны, но сеть пока закрыта владельцем Dewiar")
        elif app and app.get("on") is False:
            add("rules", False, "Правила сети", "ноды в программе пока закрыты владельцем Dewiar")
        else:
            add("rules", True, "Правила сети", "подписаны ключом Dewiar, сеть открыта")
        found = models_here(self.e)
        pick = None
        for f in found:
            if base and f["base_url"].rstrip("/") != base.rstrip("/"):
                continue
            ms = [m for m in f["models"] if not re.search(r"embed|whisper|rerank|tts|vision-only", m, re.I)]
            if model and model in f["models"]:
                pick = {"base": f["base_url"], "model": model, "app": f["name"], "lan": bool(f.get("lan"))}
            elif ms and not pick:
                import llm
                pick = {"base": f["base_url"], "model": llm.pick_model(ms) or ms[0], "app": f["name"], "lan": bool(f.get("lan"))}
        if pick:
            add("model", True, "Своя модель", f"{pick['app']}: {pick['model']}")
        else:
            add("model", False, "Своя модель", "не нашла запущенной Ollama, LM Studio или llama.cpp — поставьте Ollama и модель (например, qwen3:8b), "
                "запустите и проверьте снова. Модель на своём сервере в домашней сети — подключите его в «Мозге» (адрес вида "
                "http://192.168.1.10:11434) и проверьте снова")
        g = SYS.gpu(fresh=True)
        if pick and pick.get("lan"):
            add("gpu", None, "Видеокарта", "у сервера в сети — решит замер скорости")
        elif g:
            enough = g["mem_gb"] >= 8 or g.get("apple")
            add("gpu", True if enough else False, "Видеокарта", f"{g['name']}, {str(g['mem_gb']).replace('.', ',')} ГБ" + ("" if enough else " — мало, нужно от 8 ГБ"))
        else:
            add("gpu", None, "Видеокарта", "не узнала (не NVIDIA?) — решит замер скорости")
        try:
            import device
            ram = device.ram_gb()[0]
            add("ram", None if not ram or 7 <= ram < 15 else ram >= 15, "Память", (f"{round(ram)} ГБ" + ("" if ram >= 15 else " — хватит, если модель целиком на видеокарте"
                                                                                                if ram >= 7 else " — мало")) if ram else "не узнала")
        except Exception:  # noqa: BLE001
            pass
        bat = SYS.on_battery()
        add("power", None if bat is None else (not bat), "Питание", "от сети" if bat is False else "от батареи — нода ждёт зарядку" if bat else "не узнала")
        speed = None
        if pick:
            speed = speed_test(pick["base"], pick["model"])
            lim = float(app.get("max_answer_s") or 6)
            if not speed["ok"]:
                add("speed", False, "Скорость", "модель не ответила: " + (speed.get("error") or ""))
            elif speed["s"] > lim * 1.6:
                add("speed", False, "Скорость", f"ответ за {speed['s']:.1f} с — медленно: сеть ждёт не дольше {lim:.0f} с".replace(".", ","))
            elif speed["s"] > lim:
                add("speed", None, "Скорость", f"ответ за {speed['s']:.1f} с — впритык (лучше быстрее {lim:.0f} с); на коротких вопросах успеет".replace(".", ","))
            elif not speed.get("cyr"):
                add("speed", False, "Скорость", "ответила не по-русски — нужна модель, которая говорит по-русски (qwen3, gemma3)")
            else:
                add("speed", True, "Скорость", f"ответ за {speed['s']:.1f} с, {speed['tps']:.0f} токенов в секунду".replace(".", ","))
        self._last_check = {"ok": ok_all, "at": time.time(), "pick": pick}
        return {"ok": ok_all, "items": items, "models": found, "pick": pick, "speed": speed}

    # --- стать нодой / выключить / уйти
    def join(self, base, model, when="idle", share="low"):
        """«Стать нодой»: приглашение и регистрация (kind app), ключ ноды — в файл, поток — в работу."""
        from cloud import fetch, public, CloudError
        if when not in WHEN or share not in SHARE:
            raise NodeError("не тот режим")
        if not self.e.cloud.key:
            raise NodeError("сначала войдите в Dewiar.pro: аккаунт или ключ")
        if not base or not model:
            raise NodeError("сначала нажмите «Подходит ли мой компьютер» — выберу модель")
        if not is_own(base):
            raise NodeError("нода работает только со своей моделью — на этом компьютере или своём сервере в домашней сети")
        rr, err = self.rules()
        if err:
            raise NodeError(err)
        if not rr.get("on") or (rr.get("app") or {}).get("on") is False:
            raise NodeError("сеть пока закрыта владельцем Dewiar")
        port = int((re.search(r":(\d+)", base.split("//", 1)[-1]) or [0, 80])[1])
        g = {} if is_lan(base) else (SYS.gpu() or {})          # модель на сервере в сети — не своя видеокарта
        reg = {"name": "Нода в Dewiar" + (" · " + g["name"][:40] if g.get("name") else ""), "kind": "app", "link": "pull",
               "ports": [{"port": port, "model": model[:160], "gpu_name": (g.get("name") or "")[:120]}]}
        try:
            if self.st.get("key"):                       # уже нода — только сменить модель (своим ключом ноды)
                import httpx
                from cloud import api_base
                r = httpx.post(api_base(self._url()) + "/net/register", json=reg, headers={"Authorization": "Bearer " + self.st["key"]}, timeout=20)
                d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                if r.status_code >= 400:
                    raise CloudError(((d.get("error") or {}).get("message")) or f"сайт ответил {r.status_code}")
            else:
                inv = fetch(self.e.cloud.url, self.e.cloud.key, "/net/invite", timeout=20, body={})
                d = public(self.e.cloud.url, "/net/register", dict(reg, invite=inv["token"]), timeout=30)
                if not re.fullmatch(r"nk-[0-9a-f]{48}", d.get("node_key") or ""):
                    raise NodeError("сайт не выдал ключ ноды")
                with self.lock:
                    self.st.update(key=d["node_key"], url=self.e.cloud.url, since=int(time.time()))
        except CloudError as e:
            raise NodeError(str(e)) from e
        with self.lock:
            self.st.update(on=True, base=base, model=model, when=when, share=share, node_id=((d.get("nodes") or [{}])[0]).get("id"))
        self.note("info", f"стала нодой: модель {model}, {WHEN[when]}, {SHARE_TEXT[share]}")
        self.start()
        return self.public()

    def set(self, when=None, share=None, on=None):
        with self.lock:
            if when in WHEN:
                self.st["when"] = when
            if share in SHARE:
                self.st["share"] = share
        if on is not None:
            if on and not self.st.get("key"):
                raise NodeError("сначала «Стать нодой»")
            with self.lock:
                self.st["on"] = bool(on)
            self.note("info", "включена" if on else "выключена кнопкой")
            if on:
                self.start()
            else:
                self.stop()
        else:
            self.save()
        self.wake.set()
        return self.public()

    def leave(self):
        """«Перестать быть нодой»: сайт убирает ноду, ключ стирается здесь."""
        from cloud import CloudError
        self.stop()
        if self.st.get("key"):
            try:
                self._fetch("/net/leave", {}, timeout=20)
            except CloudError as e:
                if not re.search(r"нет|не найден|invalid", str(e), re.I):
                    raise NodeError(str(e)) from e
        with self.lock:
            for k in ("key", "node_id", "since"):
                self.st.pop(k, None)
            self.st["on"] = False
        self.note("info", "больше не нода — ключ ноды стёрт")
        self._set("off")
        return self.public()

    # --- поток
    def start(self):
        if self.thread and self.thread.is_alive():
            self.wake.set()
            return
        self.stop_ev.clear()
        self.thread = threading.Thread(target=self._loop, name="lira-node", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_ev.set()
        self.wake.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=POLL_WAIT + 15)
        self._go_away()
        if self.status.get("state") != "off":
            self._set("off")

    def halt(self):
        """Выход из программы: поток стоит, сайту — «ушла»; включённой нода остаётся (следующий запуск — снова в работу)."""
        self.stop_ev.set()
        self.wake.set()
        self._go_away()

    def _go_away(self):
        self._ws_drop("", backoff=0)
        if self._away_sent or not self.st.get("key"):
            return
        try:
            self._fetch("/net/away", {}, timeout=10)
        except Exception:  # noqa: BLE001
            pass
        self._away_sent = True

    def _sleep(self, s):
        self.wake.clear()
        self.wake.wait(s)

    def _loop(self):
        pause = 5
        while not self.stop_ev.is_set() and self.st.get("on") and self.st.get("key"):
            try:
                self.cycle()
                pause = 5
            except NodeError as e:
                self._set("error", str(e))
                self.note("err", str(e))
                if "убрана" in str(e) or "отключена" in str(e):
                    with self.lock:
                        self.st["on"] = False
                    self.save()
                    break
                self._sleep(pause)
                pause = min(300, pause * 2)
            except Exception as e:  # noqa: BLE001
                log.warning("нода: %s", e)
                self._set("error", "нет связи с dewiar.pro")
                self.note("err", "нет связи с dewiar.pro — попробую через " + str(pause) + " с")
                self._sleep(pause)
                pause = min(300, pause * 2)
        self._go_away()
        if self.status.get("state") != "error":
            self._set("off")

    def cycle(self, wait=POLL_WAIT):
        """Один шаг: условия → опрос → задание. -> 'job' | 'idle' | 'blocked'."""
        from cloud import CloudError
        kids = getattr(self.e, "kids", None)
        if not self.e.cloud.key or (kids is not None and callable(getattr(kids, "on", None)) and kids.on()):
            self._set("wait", "детский режим или нет входа в Dewiar.pro")
            self._go_away()
            self._sleep(30)
            return "blocked"
        rr, err = self._rules_cached()
        why = err or ("сеть сейчас закрыта владельцем Dewiar" if not rr.get("on") else "") or \
            ("ноды в программе закрыты владельцем Dewiar" if (rr.get("app") or {}).get("on") is False else "") or blocked(self.cfg(), self.e)
        if why:
            self._set("wait", why)
            self.note("skip", "пауза: " + why)
            self._go_away()
            self._sleep(20)
            return "blocked"
        self._set("ready", "")
        try:
            d = self._pull(wait)
        except CloudError as e:
            if re.search(r"узла в Сети Лиры нет|Нужен ключ узла|отключ", str(e)):
                raise NodeError("нода убрана или отключена на сайте: " + str(e)) from e
            raise
        self._away_sent = False
        if int(d.get("rules_ver") or 0) > int((rr or {}).get("ver") or 0):
            self._rules_at = 0                            # владелец поменял правила — перечитать с подписью
        job = d.get("job")
        if not job:
            if d.get("state"):
                self._set("wait", d["state"])
            if d.get("wait") and not self.stop_ev.is_set():
                # «ждёт допуска» — сайт просит 30 с; проверки после допуска приходят сразу — заглядываем раз в 10 с
                self._sleep(min(10, int(d["wait"])))
            return "idle"
        self._job(job, rr, ws=d.get("via") == "ws")
        rest = SHARE.get(self.cfg()["share"], SHARE["low"])[1]
        if rest:
            self._sleep(rest)
        return "job"

    _rules = ({}, "не проверены")
    _rules_at = 0.0

    def _rules_cached(self):
        if time.time() - self._rules_at > 3600 or self._rules[1]:
            if time.time() - self._rules_at > 60 or not self._rules[1]:
                self._rules = self.rules()
                self._rules_at = time.time()
        return self._rules

    # --- ретранслятор (0.92)
    def _relay_ok(self, url):
        """Адрес ретранслятора — только на том же сайте (ключ ноды чужому серверу не отдаём): см. relay_url_ok."""
        from urllib.parse import urlsplit
        try:
            from cloud import api_base
            u, me = urlsplit(url), urlsplit(api_base(self._url()))
        except ValueError:
            return False
        return relay_url_ok(u, me, urlsplit(self._url()))

    def _ws_open(self):
        if self._ws is not None:
            return self._ws
        if not self._ws_url or time.time() < self._ws_next or not self._relay_ok(self._ws_url):
            return None
        import ssl
        import wsmini
        ctx = None
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # noqa: BLE001
            ctx = None
        try:
            ws = wsmini.Client(self._ws_url, {"Authorization": "Bearer " + (self.st.get("key") or ""), "User-Agent": "Dewiar-node"}, timeout=10, ctx=ctx)
            hello = (ws.recv(15) or {}).get("hello") or {}
        except wsmini.WSError as e:
            self._ws_fail(str(e))
            return None
        if not hello.get("ok"):
            ws.close()
            self._ws_fail(hello.get("error") or "ретранслятор не принял ноду")
            return None
        self._ws, self._ws_fails, self._ws_ready, self._ws_why = ws, 0, False, ""
        self.note("info", "на связи через ретранслятор — одно постоянное соединение вместо опросов")
        return ws

    def _ws_note(self):
        """Для кабинета («Сеть» → «Ретранслятор»): почему опросом. none — сайт ретранслятор не предложил; other — адрес
        не этого сайта; fail: … — не дошла; wait — пробует снова."""
        if not self._ws_url:
            return "none"
        if not self._relay_ok(self._ws_url):
            return "other"
        return ("fail: " + self._ws_why) if getattr(self, "_ws_why", "") else "wait"

    def _ws_fail(self, why):
        self._ws_why = str(why)[:100]
        self._ws_fails += 1
        self._ws_next = time.time() + min(600, 30 * 2 ** min(5, self._ws_fails - 1))
        log.info("нода: ретранслятор недоступен (%s) — пока опросом", why)

    def _ws_drop(self, why="", backoff=30):
        ws, self._ws, self._ws_ready = self._ws, None, False
        if ws is not None:
            ws.close()
            if why:
                log.info("нода: связь с ретранслятором прервалась (%s) — пока опросом", why)
            self._ws_next = time.time() + backoff

    def _pull(self, wait):
        """Ждать задание: через ретранслятор (если он есть и доступен) или опросом сайта. -> ответ как у /net/pull."""
        import wsmini
        ws = self._ws_open()
        if ws is not None:
            try:
                if not self._ws_ready:
                    ws.send({"ready": True})
                    self._ws_ready = True
                m = ws.recv(wait) or {}
                if m.get("job"):
                    self._ws_ready = False
                    return {"job": m["job"], "rules_ver": m.get("rules_ver"), "via": "ws"}
                if m.get("bye"):
                    raise wsmini.WSError(str(m["bye"]))
                if "on" in m and not m["on"]:
                    return {"state": m.get("state") or "", "via": "ws"}
                return {"via": "ws"}
            except wsmini.WSError as e:
                self._ws_drop(str(e))
        d = self._fetch("/net/pull", {"wait": wait, "ws": self._ws_note()}, timeout=wait + 20)
        r = str(d.get("relay") or "")
        if r and r != self._ws_url:
            self._ws_url, self._ws_next, self._ws_fails = r, 0.0, 0
        return d

    def _done(self, body, ws):
        """Ответ сайту: через ретранслятор (там же, где пришло задание) или прямо /net/done."""
        if ws and self._ws is not None:
            import wsmini
            try:
                self._ws.send({"done": body})
                end = time.monotonic() + 25
                while time.monotonic() < end:
                    m = self._ws.recv(end - time.monotonic())
                    if m and "ack" in m:
                        return
                return
            except wsmini.WSError as e:
                self._ws_drop(str(e))
        self._fetch("/net/done", body, timeout=20)

    def _job(self, job, rr, ws=False):
        jid = str(job.get("id") or "")
        body = job.get("body") if isinstance(job.get("body"), dict) else {}
        # пришло в ту же секунду, когда человек сел за игру или выдернул зарядку, — отдать назад без штрафа
        why = blocked(dict(self.cfg(), done_ts=[]), self.e, me_busy=True)
        if why or self.stop_ev.is_set():
            self._done({"id": jid, "code": 0, "body": "", "away": True}, ws)
            self._away_sent = False
            self._go_away()                               # отдала — значит, ушла (рецензия 0.87, С2): сайт не ждёт её минуту
            self.note("skip", "вопрос отдан назад: " + (why or "выключена"))
            return
        app = rr.get("app") or {}
        limit = max(3.0, float(app.get("wait_s") or 12) - float(app.get("take_s") or 1.5) - 1.0)
        q = ""
        try:
            q = str((body.get("messages") or [{}])[-1].get("content") or "")
        except (AttributeError, IndexError):
            pass
        self._set("work", "")
        t0 = time.monotonic()
        code, raw = ask_model(self.st.get("base") or "", self.st.get("model") or "", body, limit)
        ms = int((time.monotonic() - t0) * 1000)
        # не вышло — сайту только код (рецензия 0.87, М4: текст ошибки своей модели — адреса, пути — ему ни к чему)
        self._done({"id": jid, "code": code if code == 200 else (code or 0), "body": raw if code == 200 else ""}, ws)
        if code == 200:
            try:
                out = json.loads(raw)["choices"][0]["message"].get("content") or ""
            except (ValueError, KeyError, IndexError):
                out = ""
            self._count(len(q), len(out), ms)
        else:
            self.note("err", (f"вопрос не взят: {raw}" if code == 0 and not raw.startswith("своя модель") else
                              f"своя модель не ответила за {ms / 1000:.1f} с — вопрос ответил сервер Dewiar".replace(".", ","))[:200])
        self._set("ready", "")

    # --- для студии
    def me(self, fresh=False):
        """«Мой узел» с сайта (кэш 30 с)."""
        from cloud import fetch, CloudError
        at, v = self._me
        if not fresh and v is not None and time.time() - at < 30:
            return v
        if not self.e.cloud.key:
            return None
        try:
            v = fetch(self.e.cloud.url, self.e.cloud.key, "/net/me", timeout=15)
        except CloudError as e:
            v = {"ok": False, "error": str(e)}
        self._me = (time.time(), v)
        return v

    def public(self):
        with self.lock:
            c = self.st.get("count") or {}
            today = c.get("n", 0) if c.get("day") == time.strftime("%Y-%m-%d") else 0
            return {"joined": bool(self.st.get("key")), "on": bool(self.st.get("on")), "node_id": self.st.get("node_id"),
                    "model": self.st.get("model") or "", "base": self.st.get("base") or "", "when": self.st.get("when") or "idle",
                    "share": self.st.get("share") or "low", "status": dict(self.status), "today": today, "total": c.get("total", 0),
                    "journal": list(reversed(self.st.get("journal") or []))[:40], "since": self.st.get("since") or 0,
                    "when_text": WHEN, "share_text": SHARE_TEXT}

    def info(self, fresh=False):
        out = self.public()
        rr, err = self.rules() if fresh else self._rules_cached()
        out["rules"] = {"ok": not err, "error": err, "on": bool(rr.get("on")), "share": (rr.get("pay") or {}).get("share"), "pay": rr.get("pay") or {},
                        "app": rr.get("app") or {}, "admit": rr.get("admit"), "expires": rr.get("expires")}
        try:
            import liranet, base64
            pub = self.e.s.get("cloud", "net_pub") or ""
            out["rules"]["fp"] = liranet.fingerprint(base64.b64decode(pub)) if pub else ""
        except Exception:  # noqa: BLE001
            out["rules"]["fp"] = ""
        me = self.me(fresh)
        if me and me.get("ok"):
            mine = [n for n in me.get("nodes") or [] if n.get("id") == self.st.get("node_id")] or \
                [n for n in me.get("nodes") or [] if n.get("kind") == "app"]
            if mine:                                    # 0.87.1: честно — сколько принятых сегодня без оплаты
                up, day = int(mine[0].get("unpaid_day") or 0), time.strftime("%Y-%m-%d")
                seen = self.st.get("unpaid_seen") or {}
                was = int(seen.get("n") or 0) if seen.get("day") == day else 0
                if up > was:
                    with self.lock:
                        self.st["unpaid_seen"] = {"day": day, "n": up}
                    self.note("info", f"без оплаты: ещё {up - was} из принятых сегодня — спрашивающий платил подарочными "
                                      "или пробными талерами (или касса ничего не списала); в «сегодня» они не входят")
            out["site"] = {"node": mine[0] if mine else None, "paid_total": me.get("paid_total"), "waiting": me.get("waiting"),
                           "est_day": (mine[0] if mine else {}).get("est_day", 0), "share": me.get("pay_share"), "others": len(me.get("nodes") or []) - (1 if mine else 0)}
        elif me:
            out["site"] = {"error": me.get("error")}
        with self.lock:
            out["journal"] = list(reversed(self.st.get("journal") or []))[:40]
        out["account"] = bool(self.e.cloud.key)
        return out


def get(engine):
    n = getattr(engine, "lnode", None)
    if n is None:
        n = Node(engine)
        engine.lnode = n
    return n


def autostart(engine):
    """При запуске программы: нода была включена — снова в работу (условия проверит сама)."""
    try:
        n = get(engine)
        if n.st.get("on") and n.st.get("key"):
            n.start()
    except Exception as e:  # noqa: BLE001
        log.warning("нода не запустилась: %s", e)


def command(engine, cmd, a):
    n = get(engine)
    try:
        if cmd == "lnode_info":
            return n.public() if a.get("lite") else n.info(bool(a.get("fresh")))      # lite — точка в меню, без сайта
        if cmd == "lnode_check":
            return n.check(a.get("base") or "", a.get("model") or "")
        if cmd == "lnode_join":
            return n.join(a.get("base") or "", a.get("model") or "", a.get("when") or "idle", a.get("share") or "low")
        if cmd == "lnode_set":
            return n.set(a.get("when"), a.get("share"), a.get("on"))
        if cmd == "lnode_stop":                          # «Выключить» — можно всегда (и в детском режиме)
            return n.set(on=False)
        if cmd == "lnode_leave":
            return n.leave()
    except NodeError as e:
        raise ValueError(str(e)) from e
    raise ValueError("нет такой команды: " + cmd)
