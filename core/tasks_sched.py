"""Фоновые задачи, часть «расписание» (примесь TaskManager, core/tasks.py; чистое ядро 1.0.10 — docs/CORE_PLAN.md):
оценка, «разбудить по событию» (файл, письмо, событие календаря), планировщик и сторож, напоминание о вопросе."""
import threading
from pathlib import Path
from tasks_base import (
    ASK_REMIND_SEC, EST_MIN_SAMPLES, HANG_SEC, HANG_TOOL_SEC, log, MAIL_WAKE_SEC, _now, PROGRESS_EVERY,
    PROGRESS_FIRST, RESUME_SEC, task_kind, task_spent)
import tasks_base as TB  # подменяемые в проверках имена — через основу


class SchedMixin:
    # ---------- оценка до старта (HARNESS, выпуск 7 «Бюджет и голос») ----------
    def estimate(self, goal):
        """Сколько обычно занимает такая задача у этого человека -> {kind, tokens, minutes, n} по завершённым задачам того
        же вида (медиана); похожих меньше EST_MIN_SAMPLES — {kind, n, tokens: 0, minutes: 0} (оценки нет, не спрашиваем)."""
        kind = task_kind(goal)
        toks, mins = [], []
        for x in list(self.tasks.values()):
            d = x.data
            if d.get("status") != "done" or d.get("parent") or task_kind(d.get("goal") or "") != kind:
                continue
            sp = task_spent(d)
            try:
                m = (TB.dt.datetime.fromisoformat(str(d.get("updated"))) - TB.dt.datetime.fromisoformat(str(d.get("created")))).total_seconds() / 60
            except (TypeError, ValueError):
                m = 0
            if sp > 0 and 0 < m < 60 * 24:                 # «ждали ответа три дня» — не мерило длительности работы
                toks.append(sp)
                mins.append(m)
        n = len(toks)
        if n < EST_MIN_SAMPLES:
            return {"kind": kind, "n": n, "tokens": 0, "minutes": 0}
        med = lambda xs: sorted(xs)[len(xs) // 2]   # noqa: E731
        return {"kind": kind, "n": n, "tokens": int(med(toks)), "minutes": int(round(med(mins)))}

    def _wake_on(self, t, args):
        """wait по событию (выпуск 8, п.7): {file, sig} — файл (в папке задачи или папке человека) появился или изменился;
        {mail, seen} — пришло новое письмо от кого-то или о чём-то (почта подключена). -> словарь, {} или текст ошибки."""
        on = {}
        fp = str(args.get("on_file") or "").strip()
        if fp:
            try:
                p, _ = self._area(t, fp)
            except Exception as e:  # noqa: BLE001
                return f"Путь не подходит: {e}"
            on["file"] = str(p)
            on["sig"] = self._file_sig(p)
        q = str(args.get("on_mail") or "").strip()
        if q:
            mail = getattr(self.host, "mail", None)
            if mail is None or not mail.configured():
                return "Почта не подключена — ждать письма нечем. Подожди по времени (minutes) и проверь сама."
            on["mail"] = q[:120]
            on["mail_since"] = _now()
        return on

    @staticmethod
    def _file_sig(p):
        try:
            st = Path(p).stat()
            return [int(st.st_mtime), int(st.st_size)]
        except OSError:
            return None

    def _event_due(self, t):
        """Наступило ли событие, которого ждёт спящая задача -> текст «что случилось» или "". Почта — не чаще раза в 5 мин
        и в своём потоке (будильник не ждёт сервер почты)."""
        on = t.data.get("wake_on") or {}
        if on.get("file"):
            sig = self._file_sig(on["file"])
            if sig is not None and sig != on.get("sig"):
                return f"файл «{Path(on['file']).name}» {'появился' if on.get('sig') is None else 'изменился'}"
        if on.get("mail"):
            got = on.get("mail_got")
            if got:
                return f"пришло письмо: {got}"
            import time as _t
            if _t.time() - float(on.get("mail_checked") or 0) >= MAIL_WAKE_SEC and not on.get("mail_busy"):
                on["mail_checked"], on["mail_busy"] = _t.time(), True
                threading.Thread(target=self._mail_check, args=(t, on), name="task-mail", daemon=True).start()
        return ""

    def _mail_check(self, t, on):
        try:
            since = TB.dt.datetime.fromisoformat(str(on.get("mail_since") or _now()))
            from email.utils import parsedate_to_datetime
            for x in self.host.mail.inbox(limit=15, unread=True, query=on["mail"]) or []:
                try:
                    d = parsedate_to_datetime(x.get("date") or "")
                    d = d.astimezone().replace(tzinfo=None) if d and d.tzinfo else d
                except (TypeError, ValueError):
                    d = None
                if d is None or d >= since - TB.dt.timedelta(minutes=1):
                    on["mail_got"] = f"{x.get('from', '')} — «{x.get('subject', '')}»"[:200]
                    break
        except Exception as e:  # noqa: BLE001
            log.info("Задача %s: почта для ожидания не проверилась: %s", t.id, e)
        finally:
            on["mail_busy"] = False

    def _scheduler(self):
        """Поток-будильник (раз в 2 с): будит спящие задачи к сроку или по новому сообщению; через RESUME_SEC после
        запуска программы продолжает задачи, прерванные выключением (auto_resume)."""
        import time as _t
        stop = getattr(self.host, "stopping", None)
        while not (stop is not None and stop.is_set()):
            _t.sleep(2)
            now = TB.dt.datetime.now()
            for t in list(self.tasks.values()):
                try:
                    alive = t.thread is not None and t.thread.is_alive()
                    if t.status == "sleeping" and t.data.get("inbox") and not alive:
                        self.start(t.id)                     # написали, пока поток засыпал, — не ждём срока
                    elif t.status == "sleeping" and t.data.get("wake_at") and TB.dt.datetime.fromisoformat(t.data["wake_at"]) <= now:
                        self.start(t.id, wake=t.data.get("wait_reason") or "время пришло")
                    elif t.status == "sleeping" and t.data.get("wake_on") and not alive:
                        ev = self._event_due(t)
                        if ev:
                            t.journal(f"🔔 Дождалась: {ev}")
                            t.data["wake_on"] = None
                            self.start(t.id, wake=f"{ev} ({t.data.get('wait_reason') or 'ждала этого'})")
                    elif t.data.get("auto_resume") and t.status == "paused" and (now - self._started_at).total_seconds() > RESUME_SEC:
                        t.data.pop("auto_resume", None)
                        t.journal("▶ Компьютер включили — продолжаю, где остановился.")
                        t.data["resume_why"] = "после перезапуска программы"
                        self.start(t.id)
                    elif t.status == "running" and alive:
                        self._watch(t)
                    elif t.status == "waiting":
                        self._ask_remind(t)
                except Exception:  # noqa: BLE001
                    log.exception("будильник задачи %s", t.id)

    def _watch(self, t):
        """Работающая задача (раз в 2 с из _scheduler): завис ли шаг; пора ли весточкой сказать, как идёт."""
        import time as _t
        now = _t.monotonic()
        limit = HANG_TOOL_SEC if t.beat_tool else HANG_SEC
        if t.beat and now - t.beat > limit and not t.data.get("hung_told"):
            what = f"инструмент «{t.beat_tool}»" if t.beat_tool else "модель"
            mins = round((now - t.beat) / 60)
            t.data["hung_told"] = True
            t.journal(f"⏳ Шаг не отвечает {mins} мин ({what}). Жду ещё; если не оживёт — остановите задачу и запустите снова.")
            self._problem(f"Задача: шаг завис — {what} молчит {mins} мин")
            self._push(f"⏳ Задача не отвечает: {t.title}", f"{what.capitalize()} молчит {mins} мин. Если не оживёт — остановите и "
                       "запустите снова.", critical=True)
            self._emit(t)
        if t.data.get("parent") or not t.run_t0:
            return
        last = float(t.data.get("progress_told_at") or 0)
        due = PROGRESS_FIRST if not last else PROGRESS_EVERY
        if now - (last or t.run_t0) < due:
            return
        sig = self._progress_sig(t)
        if last and sig == t.data.get("progress_told_sig"):
            t.data["progress_told_at"] = now                  # сдвига нет — молчим до следующего срока
            return
        t.data.update(progress_told_at=now, progress_told_sig=sig)
        done, total = (t.data.get("progress") or [0, 0])[:2]
        mins = round((now - t.run_t0) / 60)
        where = f"сделано {done} из {total} по плану" if total else f"шагов: {t.data.get('steps', 0)}"
        act = (t.data.get("activity") or "").strip()
        self._push(f"⏱ Работаю над «{t.title}»", f"{mins} мин, {where}." + (f" Сейчас: {act[:120]}" if act else ""))
        t.journal(f"⏱ Весточка: {mins} мин, {where}.")

    def _ask_remind(self, t):
        """Задача спросила и ждёт ответа дольше ASK_REMIND_SEC — напомнить один раз (вопрос мог потеряться)."""
        if t.data.get("ask_reminded") or not t.data.get("asked_at"):
            return
        try:
            asked = TB.dt.datetime.fromisoformat(t.data["asked_at"])
        except ValueError:
            return
        if (TB.dt.datetime.now() - asked).total_seconds() >= ASK_REMIND_SEC:
            t.data["ask_reminded"] = True
            t.save()
            self._push(f"❓ Задача ждёт ответа: {t.title}", (t.data.get("question") or "")[:200] or "Ответьте в карточке задачи.",
                       critical=True)
            t.journal("❓ Напомнил о вопросе — ответа пока нет.")

    def _problem(self, text):
        """Сбой задачи — в пульс «Здоровья» и журнал сбоев для ночного разбора (host.health_problem, health.py)."""
        fn = getattr(self.host, "health_problem", None)
        if fn:
            try:
                fn(text, kind="task")
            except Exception:  # noqa: BLE001
                pass
