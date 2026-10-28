"""«Здоровье» и жалобы: как программа живёт у людей и что им мешает (сервер — cloud.php, вкладка «Здоровье»).

Пульс (/pulse): через ~2,5 минуты после запуска и раз в 6 часов — случайный номер установки (report.dev), версия,
система, железо, где думает (local | server | cloud | dewiar | none — без адресов и ключей), запуски (за сколько
секунд слух готов, когда загрузилось всё, пик нагрузки процессора на старте, первый ли запуск), счётчики ответов и
неудачных запросов к модели, сбои по подписям (ERROR в журнале и ошибки модели). Ни разговоров, ни файлов, ни ключей.
Выключается настройкой report.pulse. Что не ушло (нет связи) — копится в STATE_DIR/health.json.

Жалоба (кнопка «Сообщить о проблеме» в виджете и студии, или голосом «сообщи об ошибке: …»): слова человека, снимок
экрана (по желанию — снимается до открытия студии, виден перед отправкой), подпись для «Помощников проекта»
(report.who) и отчёт как у «Отправить отчёт». Номер и секрет жалобы — в STATE_DIR/complaints.json: раз в 6 часов
программа спрашивает /report/status и, когда разработчик ответил или исправил, говорит человеку спасибо."""
import base64
import io
import json
import os
import platform
import re
import secrets
import threading
import time

from engine_base import STATE_DIR, VERSION, log

PULSE_EVERY = 6 * 3600
# «сообщи об ошибке: …», «передай разработчику, что …», «пожалуйся разработчику: …», «отправь жалобу …»
BUG_RX = re.compile(r"^(?:(?:сообщи|передай|напиши|отправь|скажи)\s+(?:разработчик\w*\s+)?(?:об?\s+)?(?:ошибк\w*|проблем\w*|баг\w*|сбо\w*)"
                    r"|отправь\s+жалобу(?:\s+разработчик\w*)?|пожалуйся(?:\s+разработчик\w*)?|(?:передай|скажи|напиши)\s+разработчик\w*)"
                    r"(?:\s*[:,.—-]\s*|\s+)?(?:что\s+)?(.*)$", re.I | re.S)


# Жалоба оборвалась на паузе (отчёт №90, 19.10: «передай разработчику приложения что» — распознавание закончило фразу
# на вдохе, и «приложения что» ушло разработчику; человек: «меня до конца дослушай»). Хвост — служебное слово или
# суть короче двух слов — не отправляем, а переспрашиваем и следующую фразу дописываем к началу.
BUG_LEAD = re.compile(r"^(?:(?:этого\s+|этой\s+)?(?:приложени\w*|программ\w*|dewiar\w*|девиар\w*|деви\s+ар\w*|лиры|ассистент\w*)\s*[,:]?\s*)?(?:что\s+|о\s+том,?\s+что\s+)?", re.I)
BUG_TAIL = {"что", "чтобы", "и", "а", "но", "или", "в", "во", "на", "про", "о", "об", "у", "с", "со", "к", "ко", "по", "за",
            "для", "из", "от", "до", "когда", "если", "потому", "как", "где", "это", "вот", "ну", "типа", "не", "очень",
            "приложения", "программы", "мне", "меня", "там", "тут", "так"}


def bug_note(raw):
    """-> (суть жалобы, оборвалась ли). «приложения что» → ("", True); «радио молчит» → ("радио молчит", False)."""
    s = (raw or "").strip().strip(" .,:;—-")
    s = BUG_LEAD.sub("", s, count=1).strip(" .,:;—-")
    words = re.findall(r"[\w-]+", s.lower().replace("ё", "е"))
    if len(s) < 4 or not words:
        return "", True
    if words[-1] in BUG_TAIL:
        return (s if len(words) > 2 else ""), True
    return s, False


def _proc_start():
    """Когда запустился процесс (секунды эпохи): psutil, иначе /proc (Linux), иначе — сейчас."""
    try:
        import psutil
        return psutil.Process().create_time()
    except Exception:  # noqa: BLE001
        pass
    try:
        ticks = os.sysconf("SC_CLK_TCK")
        start = int(open("/proc/self/stat").read().rsplit(")", 1)[1].split()[19]) / ticks
        btime = next(int(ln.split()[1]) for ln in open("/proc/stat") if ln.startswith("btime"))
        return btime + start
    except Exception:  # noqa: BLE001
        return time.time()


def _cpu_total():
    """(занято, всего) тиков процессора всей машины — для доли нагрузки между двумя замерами; нет данных — None."""
    try:
        import psutil
        t = psutil.cpu_times()
        busy = sum(getattr(t, f, 0.0) for f in ("user", "nice", "system", "irq", "softirq", "steal"))
        return busy, busy + t.idle + getattr(t, "iowait", 0.0)
    except Exception:  # noqa: BLE001
        pass
    try:
        v = [int(x) for x in open("/proc/stat").readline().split()[1:]]
        idle = v[3] + (v[4] if len(v) > 4 else 0)
        return sum(v) - idle, sum(v)
    except Exception:  # noqa: BLE001
        return None


def brain_kind(prof):
    """Где думает ассистент — словом, без адреса: dewiar | local | server | cloud | none."""
    if not prof:
        return "none"
    url = str(prof.get("base_url") or "").lower()
    host = re.sub(r"^\w+://", "", url).split("/")[0].split(":")[0]
    if "dewiar" in host or prof.get("cloud"):
        return "dewiar"
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or not host:
        return "local"
    if re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", host) or host.endswith(".local") or "." not in host:
        return "server"
    return "cloud"


WHY_RX = (("timeout", r"не ответил вовремя|timed? ?out|таймаут"), ("connect", r"подключ|connect|resolve|сеть|network|refused"),
          ("context", r"окна контекста|context"), ("busy", r"много людей|занят|429|503|busy"), ("balance", r"заряд|талер|402|quota"),
          ("key", r"ключ|401|403|forbidden"), ("rejected", r"отклонил|400|422|413"), ("server", r"\b5\d\d\b|недоступн"))


def why_kind(err):
    """Почему не ответила модель — одним словом для «Здоровья» (пакет 20.10: «запросов в сеть неудачных 10,7 %» — а каких?)."""
    t = str(err).lower()
    return next((k for k, rx in WHY_RX if re.search(rx, t)), "other")


def clean_text(s, n=300):
    """Текст сбоя без личного: домашняя папка, адреса, ключи — заменены."""
    s = str(s)
    home = os.path.expanduser("~")
    if home and home != "~":
        s = s.replace(home, "~")
    s = re.sub(r"(Bearer\s+)[\w.-]+", r"\1***", s)
    s = re.sub(r"\bdw-[a-z0-9-]{6,}", "dw-***", s, flags=re.I)
    s = re.sub(r"(://[^/\s:@]+:)[^@\s/]+@", r"\1***@", s)
    s = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "<почта>", s)
    s = re.sub(r"\b(?!127\.0\.0\.1\b)\d{1,3}(?:\.\d{1,3}){3}\b", "<ip>", s)      # адреса машин — нет; «этот компьютер» — пусть видно
    return s.strip()[:n]


class HealthMixin:
    _health_lock = None

    # ---------- учёт ----------

    def health_begin(self):
        """Из start(): запомнить начало, следить за нагрузкой процессора первые 2 минуты, запустить пульс и проверку жалоб."""
        self._health_lock = threading.Lock()
        self._h = self._health_load()
        self._h_t0 = _proc_start()
        # первый запуск после обновления — отдельно: новые файлы (сотни МБ) проверяет антивирус, Python заново собирает
        # байткод — такой запуск медленный не из-за программы (пакет 20.10: «0.38.90 — 37 с», а это были обновления)
        upd = False
        try:
            lv = STATE_DIR / "last_version"
            prev = lv.read_text(encoding="utf-8").strip() if lv.exists() else ""
            upd = bool(prev) and prev != VERSION
            if prev != VERSION:
                lv.write_text(VERSION, encoding="utf-8")
        except OSError:
            pass
        self._h_start = {"ts": int(time.time()), "first": (self.s.get("ui", "intro") or "") == "", "v": VERSION, "upd": upd}
        self._h_marks = {}
        if self.wav_input and not os.environ.get("DEWIAR_PULSE_URL"):
            return                                       # прогон по wav-файлу — не пульс человека
        threading.Thread(target=self._cpu_watch, name="health-cpu", daemon=True).start()
        threading.Thread(target=self._pulse_loop, name="pulse", daemon=True).start()

    def health_mark(self, stage):
        """Этап запуска: «ready» — слух работает (можно звать по имени), «full» — загрузилось всё (GigaAM, голос)."""
        if getattr(self, "_h_marks", None) is None or stage in self._h_marks:
            return
        sec = round(time.time() - self._h_t0, 1)
        self._h_marks[stage] = sec
        log.info("⏱ Запуск: %s за %.1f с", {"ready": "слух готов", "full": "всё загружено"}.get(stage, stage), sec)
        self._start_done()

    def _cpu_watch(self):
        """Пик нагрузки процессора всей машины (окна по 5 с) первые 2 минуты после запуска."""
        peak, prev = 0, _cpu_total()
        end = time.monotonic() + float(os.environ.get("DEWIAR_CPU_WATCH", "120"))
        while prev and time.monotonic() < end and not self.stopping.wait(5.0):
            cur = _cpu_total()
            if cur and cur[1] > prev[1]:
                peak = max(peak, round(100 * (cur[0] - prev[0]) / (cur[1] - prev[1])))
            prev = cur
        self._h_marks["cpu"] = peak
        self._start_done()

    def _start_done(self):
        """Запуск записан, когда есть и «слух готов» (или 10 минут прошло), и пик процессора."""
        m = self._h_marks
        if "saved" in m or "cpu" not in m or ("ready" not in m and time.time() - self._h_t0 < 600):
            return
        m["saved"] = True
        st = dict(self._h_start, ready_s=m.get("ready", 0.0), full_s=m.get("full", 0.0), cpu=m.get("cpu", 0))
        with self._health_lock:
            self._h["starts"] = (self._h.get("starts") or [])[-9:] + [st]
            self._health_save()

    def health_count(self, what, n=1):
        """Счётчик для пульса: turns — ответы, net_ok / net_fail — удачные и неудачные запросы к модели, rude / refused —
        грубость к помощнику и его отказы (boundaries.py; только числа)."""
        if self._health_lock is None:
            return
        with self._health_lock:
            self._h[what] = int(self._h.get(what, 0)) + n

    def health_why(self, prof, err):
        """Сбой ответа модели — в разбивку «где думает : почему» (dewiar:timeout, local:connect…), только числа."""
        if self._health_lock is None:
            return
        k = f"{brain_kind(prof)}:{why_kind(err)}"
        with self._health_lock:
            w = self._h.setdefault("net_why", {})
            if k in w or len(w) < 40:
                w[k] = int(w.get(k, 0)) + 1

    def health_problem(self, text, kind="error"):
        """Сбой в пульс: одна подпись (числа и пути — одинаковые) — один счётчик. И в журнал сбоев (incident) —
        с временем, для ночного разбора."""
        if self._health_lock is None:
            return
        text = clean_text(text)
        self.incident(kind, text)
        sig = re.sub(r"\d+", "#", re.sub(r"(?:[A-Za-z]:)?[\\/][^\s:;,]+", "PATH", text))[:160]
        with self._health_lock:
            pr = self._h.setdefault("problems", {})
            if sig not in pr and len(pr) >= 30:
                return
            p = pr.setdefault(sig, {"text": text, "n": 0})
            p["n"] += 1
            p["text"] = text
            self._h["errors"] = int(self._h.get("errors", 0)) + 1

    def incident(self, kind, text):
        """Журнал сбоев STATE_DIR/incidents.jsonl: {ts, kind, text, v} — строка на сбой, без разговоров и файлов
        (text уже прошёл clean_text). Больше 512 КБ — старая половина отрезается. Читает night.py."""
        rec = json.dumps({"ts": int(time.time()), "kind": kind, "text": clean_text(text, 300), "v": VERSION}, ensure_ascii=False)
        f = STATE_DIR / "incidents.jsonl"
        try:
            with self._health_lock or threading.Lock():
                with open(f, "a", encoding="utf-8") as fh:
                    fh.write(rec + "\n")
                if f.stat().st_size > 512 * 1024:
                    lines = f.read_text(encoding="utf-8").splitlines()
                    f.write_text("\n".join(lines[len(lines) // 2:]) + "\n", encoding="utf-8")
        except OSError:
            pass

    def incidents(self, since=0):
        """Сбои из журнала новее since (секунды эпохи)."""
        out = []
        try:
            for ln in (STATE_DIR / "incidents.jsonl").read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if r.get("ts", 0) > since:
                    out.append(r)
        except OSError:
            pass
        return out

    def _health_load(self):
        try:
            return json.loads((STATE_DIR / "health.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _health_save(self):
        try:
            (STATE_DIR / "health.json").write_text(json.dumps(self._h, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    # ---------- пульс ----------

    def health_dev(self):
        """Случайный номер этой установки (не имя компьютера) — чтобы сервер считал устройства, а не людей."""
        dev = self.s.get("report", "dev") or ""
        if not re.match(r"^[a-z]{2}-[a-z0-9]{8,40}$", dev):
            dev = ("sv-" if getattr(self, "server", False) else "pc-") + secrets.token_hex(8)
            self.s.update({"report": {"dev": dev}})
        return dev

    def _cloud_base(self):
        from cloud import DEFAULT_URL, base_of
        return (os.environ.get("DEWIAR_REPORT_URL") or base_of(self.s.get("cloud", "url") or DEFAULT_URL)).split("?", 1)[0]

    def pulse_payload(self):
        from device import cores, ram_gb
        from engine_base import OS_NAME
        with self._health_lock:
            h = json.loads(json.dumps(self._h))
        try:
            hw = {"cores": cores(), "ram_gb": round(ram_gb(), 1), "arch": platform.machine()}
        except Exception:  # noqa: BLE001
            hw = {}
        return {"dev": self.health_dev(), "app": "server" if getattr(self, "server", False) else "desktop", "version": VERSION,
                "os": f"{OS_NAME} {platform.machine()}", "hw": hw, "brain": brain_kind(self.s.active_llm()),
                "uptime_h": round((time.time() - self._h_t0) / 3600, 1), "starts": h.get("starts") or [],
                "turns": h.get("turns", 0), "net_ok": h.get("net_ok", 0), "net_fail": h.get("net_fail", 0), "errors": h.get("errors", 0),
                "rude": h.get("rude", 0), "refused": h.get("refused", 0), "net_why": h.get("net_why") or {},
                "problems": [{"sig": k, "text": v["text"], "n": v["n"]} for k, v in (h.get("problems") or {}).items()]}

    def pulse_send(self):
        """Отправить пульс; ушёл — счётчики с нуля. -> True, если сервер принял."""
        import egress
        if self.s.get("report", "pulse") is False or egress.local_only():   # стоп-кран — пульс ждёт
            return False
        import httpx
        body = self.pulse_payload()
        try:
            r = httpx.post(os.environ.get("DEWIAR_PULSE_URL") or self._cloud_base() + "?p=/pulse", json=body, timeout=20)
            if r.status_code >= 400:
                log.info("💓 Пульс не принят: %s", r.status_code)
                return False
        except httpx.HTTPError as e:
            log.info("💓 Пульс не ушёл: %s", e)
            return False
        with self._health_lock:                          # вычесть отправленное (пока шёл запрос, могло прибавиться)
            for k in ("turns", "net_ok", "net_fail", "errors", "rude", "refused"):
                self._h[k] = max(0, int(self._h.get(k, 0)) - int(body.get(k, 0)))
            w = self._h.get("net_why") or {}
            for k, n in body["net_why"].items():
                if k in w:
                    w[k] = int(w[k]) - int(n)
                    if w[k] <= 0:
                        del w[k]
            sent = {p["sig"]: p["n"] for p in body["problems"]}
            pr = self._h.get("problems") or {}
            for sig, n in sent.items():
                if sig in pr:
                    pr[sig]["n"] -= n
                    if pr[sig]["n"] <= 0:
                        del pr[sig]
            self._h["starts"] = (self._h.get("starts") or [])[len(body["starts"]):]
            self._health_save()
        log.info("💓 Пульс отправлен: запусков %d, ответов %d, сбоев %d", len(body["starts"]), body["turns"], len(body["problems"]))
        return True

    def _pulse_loop(self):
        """Поток pulse: первый — через 2,5 минуты (запуск уже измерен), дальше раз в 6 часов; там же — ответы на жалобы."""
        wait = float(os.environ.get("DEWIAR_PULSE_WAIT", "150"))
        while not self.stopping.wait(wait):
            try:
                self.pulse_send()
            except Exception as e:  # noqa: BLE001
                log.info("💓 пульс: %s", e)
            try:
                self.complaints_check()
            except Exception as e:  # noqa: BLE001
                log.info("🐞 ответы на жалобы: %s", e)
            wait = float(os.environ.get("DEWIAR_PULSE_EVERY", PULSE_EVERY))

    # ---------- жалобы ----------

    def _bug_cmd(self, text, via=None):
        """Голосом или сообщением: «сообщи об ошибке: радио не включается» — жалоба без снимка экрана (журнал — да).
        Сказали только «сообщи об ошибке» — переспросить и следующую фразу (40 с) считать жалобой. -> True, если это было оно."""
        t = text.strip()
        m0 = re.match(r"^([\w-]+)\s*,\s*(.+)$", t, re.S)          # написали с обращением: «Лира, сообщи об ошибке…»
        if m0:
            try:
                names = {str(p.get("name", "")).lower() for p in self.personas.all()}
            except Exception:  # noqa: BLE001
                names = set()
            if m0.group(1).lower() in names:
                t = m0.group(2).strip()
        wait = getattr(self, "_bug_wait", 0)
        if wait and time.monotonic() - wait < 40:
            self._bug_wait = 0
            if re.fullmatch(r"(?i)\s*(отмена|отмени|не надо|ничего|передумал\w*|забудь)\W*", t):
                self._say_quick("Хорошо, не отправляю.", text, via)
                return True
            note = (getattr(self, "_bug_prefix", "") + " " + t).strip()
            self._bug_prefix = ""
        else:
            m = BUG_RX.match(t)
            if not m:
                return False
            note, cut = bug_note(m.group(1))
            if cut:
                self._bug_wait, self._bug_prefix = time.monotonic(), note

                def listen():
                    self.follow_up_until = time.monotonic() + 15
                    self.set_state("listening")
                ask = "Слушаю — договорите, что передать разработчику." if note else \
                    "Что случилось? Расскажите одной-двумя фразами — передам разработчику."
                self._say_quick(ask, text, via, then=None if via else listen)
                return True

        def send():
            try:
                r = self.complaint_send(note, self.s.get("report", "who") or "", shot=False, via="сообщением" if via else "голосом")
                msg = f"Передал разработчику — жалоба №{r['id']}. Когда ответят или исправят, скажу. Спасибо, что помогаете!"
            except Exception as e:  # noqa: BLE001
                msg = f"Не получилось отправить: {e}. Можно в студии: «О программе» → «Сообщить о проблеме»."
            self._say_quick(msg, text, via)
        threading.Thread(target=send, name="complaint", daemon=True).start()
        return True

    def bug_shot(self, image=None):
        """Снимок экрана для жалобы — до того, как откроется студия (виден человеку перед отправкой, можно не прикладывать).
        image — своя картинка (data:-адрес): вставили из буфера (Ctrl+V) или перетащили в форму (№139, 20.10: «нельзя
        скриншот из буфера к отчёту приложить»). -> {"ok", "preview": data:-адрес уменьшенной копии} или {"ok": False, "error"}."""
        from eyes import EyesError, capture_screen
        from tools import desktop_env
        from PIL import Image, UnidentifiedImageError
        if image:
            try:
                raw = base64.b64decode(str(image).split(",", 1)[-1], validate=False)
                if len(raw) > 25 * 1024 * 1024:
                    return {"ok": False, "error": "картинка больше 25 МБ"}
                Image.open(io.BytesIO(raw)).verify()
            except (ValueError, UnidentifiedImageError, OSError):
                return {"ok": False, "error": "это не картинка"}
        else:
            try:
                raw = capture_screen(desktop_env())
            except (EyesError, OSError) as e:
                self._bug = None
                return {"ok": False, "error": str(e)}
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80, optimize=True)
        small = im.copy()
        small.thumbnail((960, 960))                  # №387 (28.10): «сильно сжимаются скриншоты» — превью чётче; уходит полный (1600)
        sb = io.BytesIO()
        small.save(sb, "JPEG", quality=84)
        prev = "data:image/jpeg;base64," + base64.b64encode(sb.getvalue()).decode()
        self._bug = {"ts": time.time(), "jpeg": buf.getvalue(), "preview": prev, "seen": False}
        self.emit("bug_shot", preview=prev)
        return {"ok": True, "preview": prev}

    def bug_state(self):
        """Студия при открытии: свежий (до 5 минут) снимок для жалобы, ещё не показанный, — {preview} или {}."""
        b = getattr(self, "_bug", None)
        if not b or time.time() - b["ts"] > 300 or b["seen"]:
            return {}
        b["seen"] = True
        return {"preview": b["preview"]}

    def complaint_send(self, note, who="", shot=True, via="кнопкой"):
        """Жалоба разработчику: слова человека (обязательно), снимок экрана (если снят и shot), подпись для «Помощников»,
        отчёт с журналом. -> {"id"}; ошибка — ValueError с понятным текстом."""
        note = (note or "").strip()
        if len(note) < 3:
            raise ValueError("напишите хотя бы пару слов — что пошло не так")
        who = re.sub(r"[<>\"]", "", (who or "").strip())[:40]
        self.s.update({"report": {"who": who}})
        b = getattr(self, "_bug", None)
        jpeg = b["jpeg"] if shot and b and time.time() - b["ts"] < 1800 else None
        r = self.report_send(note, shot=jpeg, who=who, summary=f"жалоба ({via})")
        self._bug = None
        self._complaints_add({"id": r["id"], "s": r.get("secret", ""), "note": note[:2000], "ts": int(time.time()), "status": "new",
                              "reply": "", "fixed": "", "shot": bool(jpeg)})
        log.info("🐞 Жалоба №%s отправлена (%s)%s", r["id"], via, " со снимком" if jpeg else "")
        return {"id": r["id"], "shot": bool(jpeg)}

    def _complaints(self):
        try:
            return json.loads((STATE_DIR / "complaints.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _complaints_add(self, c):
        lst = [x for x in self._complaints() if time.time() - x.get("ts", 0) < 180 * 86400][-49:] + [c]
        self._complaints_save(lst)

    @staticmethod
    def _complaints_save(lst):
        try:
            (STATE_DIR / "complaints.json").write_text(json.dumps(lst, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def complaints_view(self, fresh=False):
        """Для студии: мои жалобы (новые сверху) и помощники проекта (с сервера, раз в час)."""
        th = getattr(self, "_thanks_list", None)          # не «_thanks»: так называется ответ на «спасибо» (engine_answer)
        if fresh or not th or time.time() - th[0] > 3600:
            try:
                import httpx
                r = httpx.get(self._cloud_base() + "?p=/thanks", timeout=10)
                self._thanks_list = th = (time.time(), (r.json() or {}).get("people") or [])
            except Exception:  # noqa: BLE001
                th = th or (0, [])
        return {"mine": [{k: v for k, v in c.items() if k != "s"} for c in reversed(self._complaints())], "thanks": th[1],
                "who": self.s.get("report", "who") or "", "pulse": self.s.get("report", "pulse") is not False}

    def complaints_check(self):
        """Спросить, что с жалобами (ещё не закрытыми или за последний месяц); ответили — сказать спасибо уведомлением."""
        lst = self._complaints()
        ask = [c for c in lst if c.get("s") and (c.get("status") not in ("fixed", "no") or time.time() - c.get("ts", 0) < 30 * 86400)]
        if not ask:
            return []
        import httpx
        r = httpx.post(self._cloud_base() + "?p=/report/status", json={"items": [{"id": c["id"], "s": c["s"]} for c in ask]}, timeout=15)
        got = {int(x["id"]): x for x in (r.json() or {}).get("items") or []}
        news = []
        for c in lst:
            x = got.get(int(c["id"]))
            if not x:
                continue
            changed = x["status"] != c.get("status") or x.get("reply", "") != c.get("reply", "")
            c.update(status=x["status"], reply=x.get("reply", ""), fixed=x.get("fixed", ""), reward=x.get("reward", 0))
            if changed and x["status"] in ("work", "fixed", "no") or (changed and x.get("reply")):
                news.append(c)
        self._complaints_save(lst)
        for c in news:
            title, text = self.complaint_message(c)
            self.push(title, text, telegram=False)
            # 24.10 (владелец: «присылал жалобы и ни разу не получил ответ»): всплывающее окно легко пропустить — ответ ещё и
            # в «Чат» студии, с пометкой «ответ разработчика»; там он останется
            try:
                if getattr(self, "chatlog", None) is not None:
                    item = self.chatlog.add("assistant", f"{title}. {text}", who=self.s.get("persona"), via="dev")
                    if item:
                        self.bridge.broadcast({"type": "chat", "item": item})
            except Exception as e:  # noqa: BLE001
                log.info("🐞 ответ на жалобу в чат: %s", e)
        if news:
            self.emit("complaints", **self.complaints_view())
        return news

    @staticmethod
    def complaint_message(c):
        """Заголовок и текст уведомления об ответе на жалобу."""
        what = f"«{c.get('note', '')[:60]}»"
        reply = (" " + c["reply"].strip()) if c.get("reply") else ""
        reward = f" В благодарность — {c['reward']:g} тал. на ваш ключ." if c.get("reward") else ""
        if c["status"] == "fixed":
            return (f"Ваша жалоба №{c['id']} исправлена",
                    f"{what} — исправлено{(' в версии ' + c['fixed']) if c.get('fixed') else ''}.{reply}{reward} "
                    "Спасибо, что помогаете делать Dewiar лучше!")
        if c["status"] == "work":
            return f"Жалоба №{c['id']} — в работе", f"{what}: разработчик подтвердил и чинит.{reply}{reward} Спасибо!"
        if c["status"] == "no":
            return f"Ответ на жалобу №{c['id']}", f"{what}.{reply or ' Разработчик не нашёл тут ошибки.'} Спасибо, что написали!"
        return f"Ответ на жалобу №{c['id']}", f"{what}.{reply}"
