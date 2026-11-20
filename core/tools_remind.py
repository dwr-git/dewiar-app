"""Напоминания, будильники, таймеры и дела по расписанию: класс Reminders и действия модели над ними."""

import json
import re
import threading
import time
import uuid

from datetime import datetime, timedelta
from settings import STATE_DIR
from tools_base import log, ToolError


class Reminders:
    """Напоминания, будильники, таймеры и дела по расписанию (kind="job", см. jobs.py): разовые и с повтором
    (when.next_time). Файл reminders.json в STATE_DIR; поток _loop раз в секунду вызывает on_fire для наступивших.
    on_change — после каждой записи (синхронизация с телефоном и сервером, sync.py). Изменения — под _lock: зовут из разных потоков."""

    def __init__(self, on_fire):
        self.path = STATE_DIR / "reminders.json"
        self.on_change = None
        self.on_fire = on_fire
        self.skip_late = None          # ("id@время") -> True, если опоздавшее напоминание уже пришло в Telegram с сервера
        self.on_wake = None            # компьютер проснулся или Dewiar запустился — сверить с телефоном (sync), прежде чем звенеть
        self.hold_until = 0.0          # до этого времени опоздавшие ждут: телефон мог уже прозвенеть и удалить их (28.10)
        self._lock = threading.Lock()
        try:
            self.items = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.items = []
        fixed = 0
        # исправление старых записей: «В будни - Обед» с повтором «каждый день» -> только будни (как _fix_days при создании)
        for it in self.items:
            rep = it.get("repeat")
            if isinstance(rep, dict) and rep.get("kind") == "daily":
                rep2, text = _fix_days({}, rep, it.get("text") or "")
                if rep2 is not rep:
                    it["repeat"], it["text"] = rep2, text
                    try:
                        from when import next_time
                        if datetime.fromisoformat(it["at"]).weekday() not in rep2["days"]:
                            it["at"] = next_time(rep2, datetime.now()).replace(microsecond=0).isoformat(timespec="seconds")
                    except (ValueError, KeyError, TypeError):
                        pass
                    fixed += 1
        if fixed:
            log.info("Напоминания: %d повторов «в будни/выходные» исправлено", fixed)
            try:
                self._save()
            except OSError:
                pass
        threading.Thread(target=self._loop, name="reminders", daemon=True).start()

    def _save(self):
        """Записать атомарно (через .tmp) и сообщить on_change. Вызывать под _lock."""
        self.items.sort(key=lambda x: x["at"])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)
        if self.on_change:
            try:
                self.on_change(list(self.items))
            except Exception as e:  # noqa: BLE001
                log.warning("Напоминания: %s", e)

    def add(self, when: datetime, text, repeat=None, kind="reminder", extra=None):
        """-> копия записи. kind: reminder | alarm | timer | job; extra — поля дела по расписанию (deliver, brief, preset)
        и вложения: note — путь заметки с картинками и файлами в папке ассистента, note_id — её id синхронизации
        (заметка пришла с телефона), см. Engine._reminder_note."""
        with self._lock:
            item = {"id": uuid.uuid4().hex[:6], "at": when.replace(microsecond=0).isoformat(timespec="seconds"),
                    "text": (text or "Напоминание").strip(), "repeat": repeat or None, "kind": kind,
                    "created": datetime.now().isoformat(timespec="seconds")}
            item.update({k: v for k, v in (extra or {}).items() if k in ("deliver", "brief", "preset", "note", "note_id", "title",
                         "care", "care_n", "care_of", "care_root", "care_at") and v not in (None, "")})   # care — лекарство (senior.py)
            self.items.append(item)
            self._save()
            return dict(item)

    def get(self, rid):
        return next((dict(x) for x in self.items if x["id"] == rid), None)

    @staticmethod
    def job_sig(x):
        """Чем одно дело по расписанию совпадает с другим: готовое (preset) или текст, повтор, время дня, куда отвечать.
        30.10 (владелец: «Итог дня в 21:00 запустился два раза подряд») — два одинаковых дела в списке выполнялись оба."""
        try:
            hm = datetime.fromisoformat(x["at"]).strftime("%H:%M")
        except (KeyError, ValueError, TypeError):
            hm = ""
        what = (x.get("preset") or "").strip() or re.sub(r"\W+", " ", str(x.get("text") or "").lower().replace("ё", "е")).strip()
        return (what, json.dumps(x.get("repeat") or None, sort_keys=True, ensure_ascii=False), hm, x.get("deliver") or "")

    def job_twin(self, sig):
        with self._lock:
            return next((dict(x) for x in self.items if x.get("kind") == "job" and self.job_sig(x) == sig), None)

    def dedupe_jobs(self):
        """Одинаковые дела по расписанию — оставить первое (раньше созданное). -> сколько убрано."""
        with self._lock:
            seen, keep = set(), []
            for x in sorted(self.items, key=lambda r: str(r.get("created") or "")):
                if x.get("kind") == "job":
                    sig = self.job_sig(x)
                    if sig in seen:
                        continue
                    seen.add(sig)
                keep.append(x)
            n = len(self.items) - len(keep)
            if n:
                ids = {x["id"] for x in keep}
                self.items = [x for x in self.items if x["id"] in ids]
                self._save()
            return n

    def upsert(self, item):
        """Синхронизация (sync.py): напоминание с другого устройства — с тем же id (создать или заменить поля).
        Переносятся только at, text, repeat, kind, paused и note_id (заметка с вложениями; нет ключа — не трогаем)."""
        with self._lock:
            cur = next((x for x in self.items if x["id"] == item["id"]), None)
            if cur is not None and cur.get("kind") == "job":
                return dict(cur)                      # дела по расписанию не синхронизируются — их поля (deliver, brief…) не трогаем
            if cur is None:
                cur = {"id": item["id"], "created": datetime.now().isoformat(timespec="seconds")}
                self.items.append(cur)
            for k in ("at", "text", "repeat", "kind", "paused", "note_id"):
                if k in item:
                    cur[k] = item[k]
            if not cur.get("note_id"):
                cur.pop("note_id", None)
            if not cur.get("paused"):
                cur.pop("paused", None)
            self._save()
            return dict(cur)

    def remove(self, rid):
        """Удалить ровно этот id (без поиска по тексту, как у cancel)."""
        with self._lock:
            n = len(self.items)
            self.items = [x for x in self.items if x["id"] != rid]
            if len(self.items) != n:
                self._save()
                return True
            return False

    def update(self, rid, patch):
        with self._lock:
            for x in self.items:
                if x["id"] == rid:
                    if "text" in patch and patch["text"] != x.get("text") and "title" not in patch:
                        x.pop("title", None)                 # поручение переписали — прежнее короткое имя ему уже не подходит
                    for k in ("text", "at", "repeat", "paused", "kind", "deliver", "last_run", "last_ok", "last_error", "note", "note_id", "title"):
                        if k in patch:
                            x[k] = patch[k]
                    self._save()
                    return dict(x)
        return None

    def done_round(self, rid, now=None):
        """«Сделано» по повторяющемуся напоминанию: звонки этого круга больше не нужны (№927: «каждый месяц с 15 по 19…
        пока не будет выполнено» звенело и после «Готово») — следующее с нового круга (when.after_done). -> новое время
        или None (ничего не меняли)."""
        from when import after_done
        x = self.get(rid)
        if not x or not x.get("repeat"):
            return None
        try:
            nxt = after_done(x["repeat"], datetime.fromisoformat(x["at"]), now or datetime.now())
        except (KeyError, ValueError, TypeError):
            return None
        if nxt:
            self.update(rid, {"at": nxt.isoformat(timespec="seconds")})
        return nxt

    def find(self, query):
        """Записи по id или по тексту: запрос входит в текст или текст — в запрос («отмени напоминание про обед»)."""
        q = re.sub(r"\s+", " ", str(query or "").lower().replace("ё", "е")).strip()
        if not q:
            return []
        exact = [x for x in self.items if x["id"] == q]
        if exact:
            return exact
        texts = ((x, re.sub(r"\s+", " ", str(x.get("text") or "").lower().replace("ё", "е")).strip()) for x in self.items)
        return [x for x, t in texts if q in t or (t and t in q)]     # пустой текст записи совпал бы с любым запросом

    def cancel(self, rid):
        """Удалить все записи, найденные find (по id или тексту) -> найдено ли."""
        with self._lock:
            hit = {x["id"] for x in self.find(rid)}
            if not hit:
                return False
            self.items = [x for x in self.items if x["id"] not in hit]
            self._save()
            return True

    LATE_HOLD = 90                     # с — сколько опоздавшие ждут сверки с телефоном после пробуждения (не дольше)
    hold_from = 0.0

    def release_hold(self, since=None):
        """Сверка прошла (обмен, начатый после пробуждения) или её не будет (синхронизации нет) — опоздавшие звенят сразу."""
        if since is None or since >= self.hold_from:
            self.hold_until = 0.0

    def _loop(self):
        """Раз в секунду: наступившие — разовые удалить, повторяющиеся перенести; on_fire вызывается уже вне _lock.
        28.10 (владелец): компьютер спал всю ночь — утром разом прозвенело вчерашнее «Зарядить часы» (на телефоне оно уже
        прозвенело) и выполнился вчерашний «Итог дня». Теперь после пробуждения (или запуска) опоздавшие ждут LATE_HOLD с:
        on_wake сверяет с телефоном — удалённое там здесь уже не прозвенит; что звенеть — решает ядро (дела с большим
        опозданием пропускаются: _on_reminder)."""
        from when import next_time
        last = 0.0
        while True:
            time.sleep(1)
            mono = time.monotonic()
            if not last or mono - last > 60 or abs(time.time() - getattr(self, "_wall", time.time()) - (mono - last)) > 60:
                self.hold_until, self.hold_from = mono + self.LATE_HOLD, mono   # запустились или проснулись: сначала сверка
                if self.on_wake:
                    try:
                        threading.Thread(target=self.on_wake, daemon=True).start()
                    except Exception:  # noqa: BLE001
                        pass
            last, self._wall = mono, time.time()
            now = datetime.now().replace(microsecond=0)
            due = []
            with self._lock:
                for x in list(self.items):
                    if x.get("paused"):
                        continue
                    at = datetime.fromisoformat(x["at"])
                    if at <= now:
                        late_s = (now - at).total_seconds()
                        if late_s > 300 and mono < self.hold_until:
                            continue                                  # опоздавшее — после сверки с телефоном
                        fired = dict(x, late=late_s > 300, late_s=int(late_s))   # опоздало (компьютер спал или был выключен)
                        due.append(fired)
                        if x.get("repeat"):
                            nxt = next_time(x["repeat"], at)
                            while nxt <= now:                       # компьютер спал — пропущенные повторы не копим
                                nxt = next_time(x["repeat"], nxt)
                            x["at"] = nxt.isoformat(timespec="seconds")
                        else:
                            self.items.remove(x)
                if due:
                    self._save()
            for x in due:
                if x.get("late") and self.skip_late:
                    try:
                        if self.skip_late(f"{x['id']}@{x['at']}"):
                            log.info("Напоминание «%s» уже пришло в Telegram, пока компьютер был выключен", x.get("text"))
                            continue
                    except Exception:  # noqa: BLE001
                        log.debug("проверка напоминания с сервера", exc_info=True)
                try:
                    self.on_fire(x)
                except Exception:  # noqa: BLE001
                    log.exception("напоминание")

    def occurrences(self, days=14, limit=400):
        """Будущие срабатывания на days дней вперёд (с повторами) -> [{"id": "id@время", "at": unix, "text"}] — для сервера,
        который пришлёт их в Telegram, если компьютер выключен. Дела (job) не отдаём: их выполняет только компьютер.
        Не больше 60 повторов одной записи."""
        from when import next_time
        now, end = datetime.now(), datetime.now() + timedelta(days=days)
        out = []
        with self._lock:
            items = [dict(x) for x in self.items]
        for x in items:
            if x.get("paused") or x.get("kind") == "job":
                continue
            try:
                at = datetime.fromisoformat(x["at"])
            except (ValueError, KeyError, TypeError):
                continue
            for _ in range(60):
                if at > end:
                    break
                if at >= now - timedelta(minutes=1):
                    out.append({"id": f"{x['id']}@{at.isoformat(timespec='seconds')}", "at": int(at.timestamp()),
                                "text": x.get("text") or ("Будильник" if x.get("kind") == "alarm" else "Напоминание")})
                if not x.get("repeat"):
                    break
                at = next_time(x["repeat"], at)
        out.sort(key=lambda r: r["at"])
        return out[:limit]

    def done_elsewhere(self, occ):
        """Срабатывание «id@время» уже случилось на сервере: разовое — убрать, с повтором — перейти к следующему."""
        from when import next_time
        rid, _, when = str(occ).partition("@")
        with self._lock:
            for x in list(self.items):
                if x["id"] == rid and x["at"] == when:
                    if x.get("repeat"):
                        nxt = next_time(x["repeat"], datetime.fromisoformat(when))
                        while nxt <= datetime.now():
                            nxt = next_time(x["repeat"], nxt)
                        x["at"] = nxt.isoformat(timespec="seconds")
                    else:
                        self.items.remove(x)
                    self._save()
                    return True
        return False


# значения repeat из схемы set_reminder -> повтор в формате when.py
REPEAT_WORDS = {"daily": {"kind": "daily"}, "weekdays": {"kind": "weekly", "days": [0, 1, 2, 3, 4]},
                "weekends": {"kind": "weekly", "days": [5, 6]}, "weekly": {"kind": "weekly"},
                "monthly": {"kind": "monthly"}, "hourly": {"kind": "interval", "minutes": 60}}


def _when(a):
    """Аргументы set_reminder -> (когда, повтор, текст, вид). Главное — when по-русски («завтра в 9», «каждый день в 8»):
    разбираем сами (when.parse), не полагаясь на модель; запасные пути — in_minutes, at, repeat. Не поняли — ToolError."""
    from when import next_time, parse
    text = (a.get("text") or "").strip()
    phrase = str(a.get("when") or "").strip()
    if phrase:
        r = parse("напомни " + phrase + " " + text)
        # экзамен ПК 0.81.1: when «завтра в 9», text «Встреча с Ирой — послезавтра в 12» — день брался из текста
        # («послезавтра в 9:00»). when — главное: свой день и час есть в нём — берём их, а из текста только вид (будильник…)
        alone = parse("напомни " + phrase) if text else None
        if alone and re.search(r"\d|через|полчаса|час|утр|вечер|дн[её]м|ночь|полдень|полночь|кажд|будн|выходн", phrase, re.I) \
                and (not r or (alone["at"], alone["repeat"]) != (r["at"], r["repeat"])):
            a["_guessed"] = alone.get("guessed")
            return alone["at"], alone["repeat"], text, (r or alone)["kind"]
        if r:
            a["_guessed"] = r.get("guessed")
            return r["at"], r["repeat"], text or r["text"], r["kind"]
    rep = a.get("repeat")
    if isinstance(rep, str):
        rep = dict(REPEAT_WORDS.get(rep.strip().lower(), {})) or None
    if isinstance(rep, dict) and rep.get("kind") == "interval" and a.get("every_minutes"):
        rep["minutes"] = int(float(a["every_minutes"]))
    if a.get("in_minutes") is not None:
        when = datetime.now() + timedelta(minutes=float(a["in_minutes"]))
        return when, rep, text, "reminder"
    at = re.sub(r"\s+", " ", str(a.get("at") or "").replace("\u202f", " ").replace("\xa0", " ")).strip()
    try:                                                 # «2026-10-15 08:00:00», «…T08:00+03:00», «…Z» — тоже дата
        iso = datetime.fromisoformat(at.replace("Z", "+00:00")) if re.match(r"\d{4}-\d\d-\d\d[T ]\d", at) else None
        if iso is not None:
            at = (iso.astimezone().replace(tzinfo=None) if iso.tzinfo else iso).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%H:%M", "%d.%m.%Y %H:%M"):
        try:
            t = datetime.strptime(at, fmt)
            if fmt == "%H:%M":                           # только время — ближайшее: сегодня или завтра
                t = datetime.combine(datetime.now().date(), t.time())
                if t <= datetime.now():
                    t += timedelta(days=1)
            if rep and rep.get("kind") != "interval":
                rep.setdefault("time", f"{t:%H:%M}")
                if rep["kind"] == "weekly" and not rep.get("days"):
                    rep["days"] = [t.weekday()]
                if rep["kind"] == "monthly" and not rep.get("day"):
                    rep["day"] = t.day
            return t, rep, text, "reminder"
        except ValueError:
            continue
    if rep and rep.get("kind") == "interval":
        return next_time(rep, datetime.now()), rep, text, "reminder"
    raise ToolError("скажи, когда напомнить: when («через 10 минут», «завтра в 9», «каждый день в 8») "
                    "или in_minutes, или at (ГГГГ-ММ-ДД ЧЧ:ММ)")


# «в будни» / «по выходным» в тексте или в when
_WEEKDAYS_RX = re.compile(r"(?:^|\s)(?:по\s+будням|в\s+будни|будни|будний\s+день|в\s+рабочие\s+дни|по\s+рабочим\s+дням|рабочие\s+дни)"
                          r"(?=\s|$|[,.:;—-])", re.I)


_WEEKENDS_RX = re.compile(r"(?:^|\s)(?:по\s+выходным|в\s+выходные|выходные(?:\s+дни)?)(?=\s|$|[,.:;—-])", re.I)


def _fix_days(a, rep, text):
    """Модель написала «в будни» в тексте или в when, а повтор поставила «каждый день» — исправляем: только будни
    (или только выходные), а «В будни -» из текста убираем. -> (повтор, текст)."""
    said = f"{a.get('when') or ''} {text}"
    days = [0, 1, 2, 3, 4] if _WEEKDAYS_RX.search(said) else [5, 6] if _WEEKENDS_RX.search(said) else None
    # уже точнее, чем «будни» («по будням, кроме пятницы» -> пн–чт; 30.10: тут пятница возвращалась) — не трогаем
    narrower = rep and rep.get("kind") == "weekly" and rep.get("days") and set(rep["days"]) < set(days or [])
    if days and rep and rep.get("kind") in ("daily", "weekly") and rep.get("days") != days and not narrower:
        rep = dict(rep, kind="weekly", days=days)
    if days:
        text = _WEEKENDS_RX.sub(" ", _WEEKDAYS_RX.sub(" ", text)).strip(" -—–:,.") or text
        text = text[:1].upper() + text[1:]
    return rep, text


def _rings_too(ctx):
    """Где ещё прозвенит (1.0.36, письмо 18.11: «сказал на компьютере — напомни завтра в час… а на телефоне? там тоже
    напомнит?»): свои устройства, бывшие на связи за неделю, — напоминание приходит к ним синхронизацией и звенит там
    само. -> « Прозвенит и на других ваших устройствах: …» или ""."""
    eng = ctx.get("engine")
    sy = getattr(eng, "sync", None)
    if sy is None:
        return ""
    try:
        st = sy.status or {}
        if not st.get("ok"):
            return ""
        week = time.time() - 7 * 86400
        devs = [d for d in st.get("all") or [] if not d.get("me") and int(d.get("seen") or 0) > week and d.get("app") in ("pc", "phone")]
        hs = getattr(eng, "home_sync", None)
        if hs is not None:
            seen = {d.get("id") for d in devs}
            devs += [d for d in hs.status.get("all") or [] if not d.get("me") and d.get("id") not in seen and int(d.get("seen") or 0) > week]
    except Exception:  # noqa: BLE001
        return ""
    phones = [d.get("name") or "телефон" for d in devs if d.get("app") == "phone"]
    pcs = [d.get("name") or "компьютер" for d in devs if d.get("app") != "phone"]
    names = [f"«{n}»" for n in (phones + pcs)[:4]]
    if not names:
        return ""
    return (" Прозвенит и на других устройствах человека: " + ", ".join(names)
            + (" — где он будет, там и напомнит; если человек спросит, так и скажи." if phones else "."))


def t_reminder(a, ctx):
    from when import describe_repeat, human
    when, rep, text, kind = _when(a)
    rep, text = _fix_days(a, rep, text)
    if rep and rep.get("kind") == "weekly" and rep.get("days") and when.weekday() not in rep["days"]:
        from when import next_time
        when = next_time(rep, datetime.now())              # первый раз — в ближайший подходящий день
    moved = ""
    if rep and when < datetime.now() - timedelta(minutes=1):          # «по будням в 17:30», а уже 17:43 — первый раз
        from when import next_time                                    # в следующий подходящий, а не звонок сразу (№56)
        when = next_time(rep, datetime.now())
        moved = f" Сегодня это время уже прошло — первый раз {human(when)}; так и скажи."
    elif not rep and when < datetime.now() - timedelta(minutes=1):     # это время уже прошло («на 17:00», а сейчас 17:26) —
        while when < datetime.now():                                  # ставим на ближайшее такое же время, а не в прошлое
            when += timedelta(days=1)
        moved = " Это время сегодня уже прошло — поэтому на завтра; так и скажи."
    item = ctx["reminders"].add(when, text or "Напоминание", rep, kind)
    from when import guess_note
    return (f"Напоминание «{item['text']}» поставлено: {human(when)}" + (f", {describe_repeat(rep)}" if rep else "") +
            f" (id {item['id']}).{moved}" + (_rings_too(ctx) if kind in (None, "", "reminder") else "") + " Подтверди коротко одной фразой."
            + guess_note({"guessed": a.pop("_guessed", None)}))


def t_schedule_job(a, ctx):
    """Дело по расписанию, которое делает сам ассистент (проверить почту, прислать курс, собрать новости) и сообщает
    итог; в срок не звонит человеку, а выполняет (engine_music._run_job). Отчёт №137, 20.10: «проверяй почту и сообщай
    о важном» становилось напоминанием человеку «проверь почту» каждый час — инструмента для такого дела у модели не было."""
    from when import describe_repeat, human, parse
    task = " ".join(str(a.get("task") or "").split()).strip(" .")
    phrase = str(a.get("when") or "").strip()
    if not task or not phrase:
        raise ToolError("нужны task — что делать тебе, и when — когда, с повтором («каждый день в 9», «по будням с 9 до 18 каждый час»)")
    r = parse("напоминай " + phrase + " " + task) or parse("напоминай " + phrase)
    if not r or not r.get("repeat"):
        raise ToolError("when — с повтором: «каждый день в 9», «по будням с 9 до 18 каждый час», «каждые 2 часа»; разовое дело — "
                        "сделай сейчас или set_reminder")
    deliver = a.get("deliver") if a.get("deliver") in ("telegram", "max", "voice") else "voice"
    title = " ".join(str(a.get("title") or "").split())[:80]           # имя для людей (дело плагина: «Дача: заморозки и полив»)
    item = ctx["reminders"].add(r["at"], task[0].upper() + task[1:], r["repeat"], "job", {"deliver": deliver, "brief": False, "title": title})
    from when import guess_note
    return (f"Дело «{item['text']}» заведено: {describe_repeat(r['repeat'])}, первый раз {human(r['at'])} (id {item['id']}). "
            "В срок его выполнишь ты сам и сообщишь итог"
            + (" в Telegram" if deliver == "telegram" else " в Max" if deliver == "max" else " голосом") + ". Подтверди одной фразой."
            + guess_note(r))


def job_short(text, n=80):
    """Короткое имя дела по расписанию для людей — из поручения модели (№557, 05.11: на «Главной» строкой ехало целиком
    «Посмотри прогноз погоды (weather) для города «Балашов» на 2 дня. Если ночью до 0° …»): первая фраза, без ссылок
    и названий инструментов в скобках («(weather)», «(web_search, read_webpage)»), не длиннее n знаков."""
    t = re.sub(r"https?://\S+", "", str(text or ""))
    t = re.sub(r"\s*\((?:[a-z][a-z0-9_]*(?:\s*[,/]\s*[a-z][a-z0-9_]*)*)\)", "", t)
    t = " ".join(t.split())
    t = re.split(r"(?<=[.!?…;])\s+(?=[А-ЯЁA-Z«\"])|\s*\n", t, maxsplit=1)[0].strip(" .;,")
    if len(t) > n:
        t = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:—–-") + "…"
    return t or "Дело по расписанию"


def t_change_reminder(a, ctx):
    """Изменить напоминание (30.10, владелец: «попросил Лиру — сказала „сейчас внесу“, а ничего не изменилось»: инструмента
    правки не было). id или text — какое; when — новое время и повтор словами; new_text — новый текст."""
    from when import describe_repeat, human, next_time, parse
    rs = ctx["reminders"]
    hit = rs.find(a.get("id") or a.get("text") or "")
    if not hit:
        return "Не нашёл такого напоминания — посмотри list_reminders и возьми id."
    if len(hit) > 1:
        return "Подходит несколько: " + "; ".join(f"{x['id']}: {x['text']}" for x in hit[:6]) + ". Укажи id."
    x, patch = hit[0], {}
    if str(a.get("new_text") or "").strip():
        patch["text"] = str(a["new_text"]).strip()[:300]
    if str(a.get("when") or "").strip():
        r = parse("напомни " + str(a["when"]).strip() + " " + (patch.get("text") or x.get("text") or ""))
        if not r:
            raise ToolError("не понял время — скажи, например: «по будням, кроме пятницы, в 17:50»")
        when, rep = r["at"], r["repeat"]
        if rep and when < datetime.now() - timedelta(minutes=1):
            when = next_time(rep, datetime.now())
        patch.update(at=when.replace(microsecond=0).isoformat(timespec="seconds"), repeat=rep)
    if not patch:
        return "Что изменить? Нужен when (время и повтор) или new_text."
    y = rs.update(x["id"], patch)
    from when import guess_note
    return (f"Изменено: «{y['text']}» — {human(datetime.fromisoformat(y['at']))}" + (f", {describe_repeat(y['repeat'])}" if y.get("repeat") else "")
            + f" (id {y['id']}). Подтверди коротко." + (guess_note(r) if str(a.get("when") or "").strip() else ""))


def t_list_reminders(a, ctx):
    from when import describe_repeat, human
    items = [x for x in ctx["reminders"].items if not x.get("paused")]
    turn = getattr(ctx.get("engine"), "turn", None)
    habit = getattr(turn, "habit", None) if getattr(turn, "no_habits", False) else None
    if habit is not None:                                       # ход-итог (engine_answer): привычки и дела по расписанию — не события
        items = [x for x in items if x.get("kind") not in ("job", "brief") and not habit(x.get("text"), x.get("id"))]
    if not items:
        return "Напоминаний нет."
    return "\n".join(f"{x['id']}: {human(datetime.fromisoformat(x['at']))} — {x['text']}" +
                     (f" ({describe_repeat(x['repeat'])})" if x.get("repeat") else "") for x in items)


def t_cancel_reminder(a, ctx):
    return "Отменил." if ctx["reminders"].cancel(a.get("id") or a.get("text") or "") else "Не нашёл такого напоминания."


def _items_arg(v):
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x or "").strip()][:12]
    return [x.strip() for x in re.split(r"\s*[;\n]\s*", str(v or "")) if x.strip()][:12]


MARK_ASK_RX = re.compile(r"(?i)\?\s*$|^\s*(?:что|какие|какой|сколько|когда|где|есть ли|расскажи|покажи|напомни,? что)\b")


MARK_DONE_RX = re.compile(r"(?i)сделал|сделала|готово|выполн|отмет|закр[ыо]|\b[а-яё]{3,}(?:л|ла|ли)\b")


def t_mark_done(a, ctx):
    """Отметить дела сделанными (done.py): подходящее разовое напоминание на сегодня закрывается, повторяющееся остаётся."""
    import done as D
    dn = ctx.get("done")
    if dn is None:
        raise ToolError("журнал дел недоступен")
    items = _items_arg(a.get("items") or a.get("text"))
    if not items:
        raise ToolError("не понял, какое дело отметить — спроси коротко")
    eng = ctx.get("engine")
    if a.get("undo"):
        today, gone = list(reversed(dn.stats()["items"])), []
        for t in items:
            w = D.stems(t)
            x = next((i for i in today if i not in gone and any(s in w for s in D.stems(i["title"]))), None) \
                or (next((i for i in today if i not in gone), None) if len(items) == 1 else None)
            if x:
                dn.undo(x["id"])
                gone.append(x)
        if eng is not None and gone:
            eng.emit("done", **dn.public())
        return (f"Отметка снята: {', '.join('«' + x['title'] + '»' for x in gone)}. Сегодня сделано {dn.stats()['today']}."
                if gone else "Среди сегодняшних отметок такого нет.")
    # экзамен 1.0.5 (plan_today): «Что у нас по плану?» — модель «закрыла» «Полить цветы» и сказала, что дел нет. Отмечать —
    # только когда человек сам сказал, что сделал; вопрос без «сделал/готово/отметь» и без глагола в прошедшем — не отметка
    said = ""
    try:
        said = str((ctx.get("turn_text") or (lambda: ""))() or "")
    except Exception:  # noqa: BLE001
        said = ""
    if said and MARK_ASK_RX.search(said) and not MARK_DONE_RX.search(said):
        raise ToolError("человек спрашивает о делах, а не говорит, что сделал, — ничего не отмечено. Просто ответь, что "
                        "впереди (list_reminders / план дня), без отметок")
    rem = ctx.get("reminders")
    closed, lst = [], []
    for t in items:
        m = D.reminder_match(t, list(rem.items) if rem is not None else [], ahead=True)
        if m:
            if not m.get("repeat"):
                rem.remove(m["id"])
                closed.append(m.get("text") or "")
            else:
                rem.done_round(m["id"])
            lst.append({"title": m.get("text") or t, "rid": m["id"]})
        else:
            lst.append({"title": t})
    r = dn.add(lst, "pc")
    if eng is not None:
        eng.emit("done", **dn.public(), fresh=[{"icon": x[3], "name": x[4], "what": x[5]} for x in r["fresh"]], mile=r["mile"],
                 added=[x["title"] for x in r["items"]])
    return D.say(r, closed)


def t_done_report(a, ctx):
    import done as D
    dn = ctx.get("done")
    if dn is None:
        raise ToolError("журнал дел недоступен")
    try:
        days = int(float(a.get("days") or 1))
    except (TypeError, ValueError):
        days = 1
    turn = getattr(ctx.get("engine"), "turn", None)
    habit = getattr(turn, "habit", None) if getattr(turn, "no_habits", False) else None
    return D.report(dn, days, skip=habit)                      # ход-итог — без отметок у привычек
