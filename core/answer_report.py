"""«Проверить всё» и отчёты разработчику (примесь AnswerMixin, core/engine_answer.py; чистое ядро 1.0.10): самопроверка,
сборка отчёта без ключей, хвост журнала, отправка и «сообщить о проблеме», ловушка падений, «диск полон»."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from answer_rules import crash_blocks


class ReportMixin:
    def self_check(self):
        """«Проверить всё» (студия → «О программе»): по пунктам — работает ли, а если нет — что сделать и где.
        -> список {name, ok, warn, detail, fix, page}; page — раздел студии для кнопки перехода. Делает сетевые
        запросы (модель, облако, сайт) — вызывать не из потока интерфейса."""
        import shutil as _sh
        import httpx
        out = []

        def add(name, ok, detail, fix="", page="", warn=False):
            out.append({"name": name, "ok": bool(ok), "warn": bool(warn) and not ok, "detail": detail, "fix": "" if ok else fix, "page": page})
        st = self.status
        dv = self.device_status()
        add("Мощность компьютера", dv["level"] == "ok" or dv["stt_server"],
            f"{dv['ram']} ГБ памяти, {dv['cores']} ядер" + ("" if dv["level"] == "ok" else f" — мало ({'лёгкий режим' if dv['light'] else 'может тормозить'})"),
            dv["advice"], "dw", warn=True)
        add("Микрофон", st.get("input"), st.get("input") or "не найден",
            "Подключите микрофон и выберите его в «Звук и поведение».", "sound")
        prof = self.s.active_llm()
        if not prof:
            add("Мозг", False, "модель не подключена", "Выберите в «Мозге», где будет думать ассистент.", "brain")
        else:
            try:
                t0 = time.monotonic()
                list_models(prof, timeout=8)
                add("Мозг", True, f"{prof.get('name') or prof.get('base_url')} — отвечает за {int((time.monotonic() - t0) * 1000)} мс")
            except LLMError as e:
                add("Мозг", False, f"{prof.get('name') or ''}: {e}", "Проверьте адрес и ключ в «Мозге» (кнопка «Проверить» у модели).", "brain")
        if self.cloud.key:
            c = self.cloud.refresh()
            if c.get("error") and c.get("percent") is None:
                add("Заряд Dewiar Облака", False, c["error"], "Проверьте интернет или ключ в «Мозге».", "brain")
            else:
                add("Заряд Dewiar Облака", not c.get("low") and not c.get("empty") and not c.get("frozen"),
                    f"{c.get('percent', 0)}% · хватит примерно на {c.get('turns', 0)} ответов", c.get("topup") or "Пополните заряд.", "brain",
                    warn=not c.get("empty") and not c.get("frozen"))
        add("Распознавание речи", st.get("stt_ready"), (st.get("stt") or "—") + ("" if st.get("stt_ready") else " — ещё загружается"),
            "Подождите, пока скачается модель (видно в виджете), или выберите другое распознавание в «Слухе».", "ears", warn=True)
        add("Голос", st.get("tts") and st.get("tts") != "Выключен", st.get("tts") or "—", "Включите голос в разделе «Голос».", "voice")
        try:
            t0 = time.monotonic()
            r = httpx.get(self.updater.url, timeout=6)
            add("Интернет и сайт Dewiar", r.status_code < 500, f"на связи, {int((time.monotonic() - t0) * 1000)} мс")
        except Exception as e:  # noqa: BLE001
            add("Интернет и сайт Dewiar", False, f"нет связи ({type(e).__name__})",
                "Без интернета работают локальные модели; обновления и облако — нет.", "", warn=True)
        try:
            free = _sh.disk_usage(str(STATE_DIR)).free / 2 ** 30
            add("Место на диске", free >= 1.5, f"свободно {free:.1f} ГБ", "Освободите место: моделям и голосам нужно около 1 ГБ.", "", warn=free >= 0.5)
        except OSError:
            pass
        u = self.updater.public()
        add("Версия", not u.get("available"), f"Dewiar {VERSION}" + (f" — есть {u['available']}" if u.get("available") else " — последняя"),
            "Обновите: «О программе» → «Обновить».", "about", warn=True)
        if st.get("meeting"):
            add("Созвон", False, "идёт созвон: " + ", ".join(st["meeting"].get("apps") or []), "Пока идёт созвон, ассистент слушает тише — так задумано.",
                "sound", warn=True)
        return out

    def build_report(self, note="", tail_lines=1500, fresh=False, talk=True):
        """Отчёт для разработчика: версия, система, состояние, настройки без ключей, звуковые устройства, следы задач и журнал.
        fresh — только то, что случилось после прошлого отправленного отчёта (журнал, ошибки, задачи, ui.log): иначе
        давно исправленная ошибка тянется из отчёта в отчёт и мешает увидеть новую. Отметка — report_mark.json."""
        import platform
        # в настройках скрываем всё, чьё имя похоже на секрет (ключи, заголовки и переменные окружения MCP-программ)
        # №311 (пакет 27.10): «max_tokens» в отчёте был «***» — числа и флаги вида *_tokens, keys_* не секрет
        # 0.82.1: и номера установки (cloud.dev — по нему сайт отдаёт прежний ключ) и пульса (report.dev)
        secret = re.compile(r"^(?!max_tokens$|.*_tokens$|tokens$|token_count$)(?:.*(api_key|token|password|key|secret|headers|auth|cookie|env)|dev$|inst$)", re.I)

        def clean(x):
            if isinstance(x, dict):
                return {k: ("***" if secret.search(k) and v else clean(v)) for k, v in x.items()}
            if isinstance(x, list):
                return [clean(v) for v in x]
            return x
        lines = [f"Dewiar {VERSION} — отчёт {datetime.now():%Y-%m-%d %H:%M}", f"Система: {OS_NAME}; Python {platform.python_version()}; "
                 f"{platform.machine()}; ядер: {os.cpu_count()}", ""]
        if note:
            lines += ["== Со слов человека", note, ""]
        lines += ["== Состояние", json.dumps(self.status, ensure_ascii=False, indent=1, default=str), ""]
        lines += ["== Настройки (без ключей)", json.dumps(clean(self.s.snapshot()), ensure_ascii=False, indent=1), ""]
        try:
            lines += ["== Звуковые устройства", json.dumps(list_devices(), ensure_ascii=False, indent=1), ""]
        except Exception as e:  # noqa: BLE001
            lines += [f"== Звуковые устройства: {e}", ""]
        mark = self._report_mark() if fresh else {}
        since = float(mark.get("ts") or 0)
        if since:
            lines += [f"(всё ниже — после прошлого отчёта{(' №' + str(mark['id'])) if mark.get('id') else ''}, "
                      f"{datetime.fromtimestamp(since):%Y-%m-%d %H:%M})", ""]
        try:                                    # долгие задачи: чем закончились, ход последних (журнал), следы ошибок
            ts = [f for f in sorted((STATE_DIR / "task_traces").glob("*.json"))[-15:] if f.stat().st_mtime >= since]
            if ts:
                lines += ["== Задачи: следы последних"] + [f.read_text(encoding="utf-8", errors="replace")[:1500] for f in ts] + [""]
            recent = [x for x in self.tasks.tasks.values() if not since or (x.dir / "задача.json").exists()
                      and (x.dir / "задача.json").stat().st_mtime >= since]
            for t in (sorted(recent, key=lambda x: str(x.data.get("created", "")))[-3:] if talk else []):   # план и журнал — тексты человека
                j = (t.dir / "журнал.md").read_text(encoding="utf-8", errors="replace").splitlines() if (t.dir / "журнал.md").exists() else []
                lines += [f"== Задача «{t.title}»: {t.status} {t.data.get('error', '')}", "-- План:",
                          t.plan()[:2000], "-- Журнал (конец):"] + j[-120:] + [""]
        except Exception as e:  # noqa: BLE001
            lines += [f"== Задачи: {e}", ""]
        tail = self._log_tail(mark if since else None)
        if not talk:                                    # 1.0.29: «без фраз разговора» — строки с текстом человека и ответов
            tail = [ln for ln in tail if not TALK_LINE_RX.search(ln)]
        errs = [ln for ln in tail if re.match(r"\d\d:\d\d:\d\d (ERROR|CRITICAL)", ln)]
        if errs:
            lines += ["== Ошибки (последние)"] + errs[-40:] + [""]
        lines += ["== Журнал (последние строки)"] + tail[-tail_lines:]
        try:                                    # ядро падало в библиотеке (faulthandler в main.py) — где именно
            cr = (STATE_DIR / "logs" / "core.crash").read_text(encoding="utf-8", errors="replace")
            blocks = crash_blocks(cr)
            if blocks:
                lines += ["", "== Падения ядра (core.crash)"] + ("--- запуск " + blocks[-1]).splitlines()[:80]
        except OSError:
            pass
        try:                                    # интерфейс: замирания окон (сторож главного цикла) и ошибки окон
            ui = (STATE_DIR / "logs" / "ui.log").read_text(encoding="utf-8", errors="replace").splitlines()
            if since:
                cut = f"{datetime.fromtimestamp(since):%Y-%m-%d %H:%M:%S}"
                ui = [ln for ln in ui if ln[:19] >= cut]
            if ui:
                lines += ["", "== Интерфейс (ui.log)"] + ui[-300:]
        except OSError:
            pass
        return self._redact("\n".join(lines))

    @staticmethod
    def _redact(text):
        """Последняя страховка перед отправкой: секреты, которые могли попасть в журнал, — ключи Bearer и dw-,
        токены Telegram, пароли в адресах."""
        text = re.sub(r"(Bearer\s+)[\w.-]+", r"\1***", text)
        text = re.sub(r"\bdw-[a-z0-9]{4,}(?:-[a-z0-9]{2,})+", "dw-***", text, flags=re.I)
        text = re.sub(r"\bbot\d{5,}:[\w-]{20,}", "bot***", text)                     # токен Telegram в адресах API
        text = re.sub(r"(://[^/\s:@]+:)[^@\s/]+@", r"\1***@", text)                    # пароль в адресе (прокси и т. п.)
        return mask_personal(mask_tokens(text))                                        # JWT, ключи API, «токен: …»; почта, телефоны

    @staticmethod
    def _log_tail(mark=None):
        """Строки журнала ядра: прошлый файл после ротации (core.log.1), затем текущий. mark — отметка прошлого отчёта
        ({"ino", "size"} файла core.log тогда): только строки после неё (файл с тех пор повернули — с того места в .1)."""
        logf = STATE_DIR / "logs" / "core.log"
        tail = []
        for f in (logf.with_name("core.log.1"), logf):
            try:
                st = f.stat()
                start = 0
                if mark:
                    if st.st_ino == mark.get("ino"):
                        start = int(mark.get("size") or 0) if st.st_size >= int(mark.get("size") or 0) else 0
                    elif f.name == "core.log.1" or mark.get("ino") is None:
                        start = st.st_size                 # всё это было до прошлого отчёта
                with open(f, "rb") as fh:
                    fh.seek(start)
                    tail += fh.read().decode("utf-8", errors="replace").splitlines()
            except OSError:
                pass
        return tail

    @staticmethod
    def _report_mark():
        try:
            return json.loads((STATE_DIR / "report_mark.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _report_mark_set(rid):
        """Отчёт ушёл — следующий начнётся отсюда: где кончался core.log (inode и размер) и когда."""
        import time as _t
        logf = STATE_DIR / "logs" / "core.log"
        try:
            st = logf.stat()
            m = {"ino": st.st_ino, "size": st.st_size}
        except OSError:
            m = {}
        m.update(ts=_t.time(), id=rid)
        try:
            (STATE_DIR / "report_mark.json").write_text(json.dumps(m), encoding="utf-8")
        except OSError:
            pass

    def save_report(self):
        """Отчёт одним файлом на рабочем столе (если отправить не получается — его можно переслать) -> путь к файлу.
        Рабочий стол: Windows — известная папка, Linux — xdg-user-dir (папка бывает названа по-русски), иначе домашняя."""
        text = self.build_report()
        if os.name == "nt":
            import winsys
            desk = winsys.known_folder("Desktop")
        else:
            desk = Path.home() / "Desktop"
            try:
                d = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=3).stdout.strip()
                if d:
                    desk = Path(d)
            except (OSError, subprocess.SubprocessError):
                pass
        if not desk.is_dir():
            desk = Path.home()
        out = desk / f"Dewiar — отчёт {datetime.now():%Y-%m-%d %H-%M}.txt"
        out.write_text(text, encoding="utf-8")
        log.info("Отчёт сохранён: %s", out)
        return str(out)

    def _report_summary(self):
        """Кратко для списка отчётов: последние разные ошибки из журнала, без времени и уровня."""
        errs = [re.sub(r"^\d\d:\d\d:\d\d \w+\s+", "", ln) for ln in self._log_tail(self._report_mark() or None)[-3000:]
                if re.match(r"\d\d:\d\d:\d\d (ERROR|CRITICAL)", ln)]
        return "; ".join(dict.fromkeys(errs[-6:]))[:480]

    def report_send(self, note="", auto=False, summary="", shot=None, who="", plain=False, talk=True):
        """«Отправить отчёт разработчику»: отчёт сразу появляется в управлении облаком (cloud.php → «Здоровье»).
        Ключ Dewiar — если есть (по нему видно, чей отчёт); без него тоже принимается. shot — снимок экрана (JPEG) и
        who — подпись автора: это жалоба (core/health.py). plain — только note и сведения о программе, без журнала
        (ночной разбор, night.py: в журнале есть реплики человека). DEWIAR_REPORT_URL — адрес для тестов.
        -> {"id", "secret"}; ошибка связи или отказ сервера — ValueError с понятным текстом."""
        import platform
        import httpx
        from cloud import DEFAULT_URL, base_of, norm_key
        note = (note or "").strip()[:2000]
        text = (f"Dewiar {VERSION} — {OS_NAME} {platform.machine()}\n\n{note}" if plain
                else self.build_report(note, tail_lines=600 if auto else 1500, fresh=not shot and not who, **({} if talk else {"talk": False})))
        url = os.environ.get("DEWIAR_REPORT_URL") or base_of(self.s.get("cloud", "url") or DEFAULT_URL)
        key = (self.s.get("cloud", "key") or "").strip()
        body = {"kind": "auto" if auto else "manual", "app": "desktop", "version": VERSION, "os": f"{OS_NAME} {platform.machine()}",
                "device": platform.node()[:60], "summary": (summary or self._report_summary())[:500], "note": note, "text": text}
        if shot:
            import base64
            shots = list(shot) if isinstance(shot, (list, tuple)) else [shot]          # №546: до 5 снимков к жалобе
            body["shot"] = "data:image/jpeg;base64," + base64.b64encode(shots[0]).decode()
            if len(shots) > 1:
                body["shots"] = ["data:image/jpeg;base64," + base64.b64encode(x).decode() for x in shots[1:5]]
        if who:
            body["who"] = who
        h = {"Authorization": f"Bearer {norm_key(key)}"} if key else {}
        try:
            r = httpx.post(url.split("?", 1)[0] + "?p=/report", json=body, headers=h, timeout=(60 + 20 * len(body.get("shots") or [])) if shot else 40)
            d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        except (httpx.HTTPError, ValueError) as e:
            from net import blocked_hint
            raise ValueError("не удалось отправить отчёт: нет связи с dewiar.pro." + blocked_hint()
                             + " Можно «Сохранить в файл» и прислать его.") from e
        if r.status_code >= 400 or not d.get("ok"):
            msg = ((d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else "") or f"сервер ответил {r.status_code}"
            raise ValueError("отчёт не принят: " + msg)
        log.info("🧾 Отчёт №%s отправлен разработчику (%s)", d.get("id"), "сам, при сбое" if auto else "кнопкой")
        self._report_mark_set(d.get("id"))
        return {"id": d.get("id"), "secret": d.get("secret", "")}

    # ---------- отчёты сами при сбое (с согласия) ----------
    def report_problem(self, sig, summary):
        """Сбой: если человек разрешил — отчёт уходит сам (одна и та же беда — не чаще раза в 12 ч, не больше 4 в сутки,
        несколько сбоев подряд — одним отчётом через 20 с); не спрашивали — один раз за запуск предлагаем.
        sig — подпись беды: цифры в ней заменяются на #, чтобы одна ошибка с разными числами считалась одной.
        Учёт отправленного — report_sent.json в STATE_DIR (переживает перезапуск)."""
        if self.wav_input and not os.environ.get("DEWIAR_REPORT_URL"):
            return                                       # прогон тестов по wav-файлу — отчёты только на тестовый адрес
        auto = self.s.get("report", "auto")             # True — согласие, False — отказ, None — ещё не спрашивали
        if auto is False:
            return
        if auto is None:
            if not getattr(self, "_report_offered", False):
                self._report_offered = True
                self.emit("report_offer", summary=summary[:200])
            return
        sig = re.sub(r"\d+", "#", sig)[:160]
        with self._report_lock:
            f = STATE_DIR / "report_sent.json"
            try:
                sent = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                sent = {}
            now = time.time()
            sent = {k: v for k, v in sent.items() if now - v < 86400}
            if now - sent.get(sig, 0) < 12 * 3600 or len(sent) >= 4 or sig in self._report_pending:
                return
            sent[sig] = now
            try:
                f.write_text(json.dumps(sent), encoding="utf-8")
            except OSError:
                pass
            self._report_pending[sig] = summary
            if len(self._report_pending) > 1:
                return                                   # уже ждём — уйдёт одним отчётом

        def later():
            time.sleep(float(os.environ.get("DEWIAR_REPORT_WAIT", "20")))   # дать журналу дописать, что было после сбоя
            with self._report_lock:
                items = dict(self._report_pending)
                self._report_pending.clear()
            try:
                self.report_send(auto=True, summary=" | ".join(items.values())[:500])
            except Exception as e:  # noqa: BLE001
                log.info("🧾 Отчёт о сбое не отправлен: %s", e)
        threading.Thread(target=later, daemon=True, name="report").start()

    def _install_report_hook(self):
        """Обработчик корневого журнала: каждая запись ERROR и выше → report_problem. Записи самой отправки
        (логгер *report) и повторный вход из того же потока пропускаем — иначе сбой отправки порождал бы
        новый отчёт без конца."""
        eng = self

        class Hook(logging.Handler):
            def emit(self, rec):
                if rec.name.endswith("report") or getattr(_report_tls, "busy", False):
                    return
                # пакет 04.11 («dewiar.sync: OSError: [Errno 28] No space left on device»): диск заполнен — не ошибка программы,
                # отчёт разработчику не нужен; человеку — честно «на диске нет места» (раз в 10 минут), остальное ждёт места
                err = rec.exc_info[1] if rec.exc_info else None
                if (err is not None and disk_full(err)) or disk_full(rec.getMessage()):
                    eng._disk_full_seen(rec.name)
                    return
                _report_tls.busy = True
                try:
                    exc = rec.exc_info[0].__name__ if rec.exc_info and rec.exc_info[0] else ""
                    msg = rec.getMessage()
                    if rec.exc_info and rec.exc_info[1]:
                        msg += f" — {exc}: {rec.exc_info[1]}"
                    eng.health_problem(f"{rec.name}: {msg}")                 # в пульс — всегда (без журнала и личного)
                    eng.report_problem(f"{rec.name}|{rec.msg}|{exc}", f"{rec.name}: {msg}"[:300])
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    _report_tls.busy = False
        h = Hook(level=logging.ERROR)
        logging.getLogger().addHandler(h)
        return h

    def _disk_full_seen(self, where=""):
        """Где-то в ядре кончилось место на диске (синхронизация, заметки, журнал): сказать человеку — не чаще раза в 10 минут."""
        now = time.monotonic()
        if now - getattr(self, "_disk_full_at", -1e9) < 600:
            return False
        self._disk_full_at = now
        try:
            self.note(disk_full_note())
            self.push("На диске нет места", disk_full_note(), critical=False, telegram=False)
        except Exception:  # noqa: BLE001
            pass
        return True
