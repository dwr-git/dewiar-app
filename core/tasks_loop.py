"""Фоновые задачи, часть «ход работы» (примесь TaskManager, core/tasks.py; чистое ядро 1.0.10 — docs/CORE_PLAN.md):
опрос и застревание, сверка, уроки, вопросы человеку, интернет и лаборатория, след и размышление."""
import json
import os
import re
import threading
import time

import quality as Q
from llm import stream_chat
from tasks_base import log, _now, TINY_WIN, WIN_DEFAULT
import tasks_base as TB  # подменяемые в проверках имена — через основу


class LoopMixin:
    def _poll(self, t, recent):
        """Короткий опрос хода раз в POLL_EVERY шагов (Magentic-One): сделано? петля? есть ход? что дальше? -> dict или None.
        Окно меньше TINY_WIN — не спрашиваем (только машинные признаки); лёгкий режим — короче."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        if win < TINY_WIN or not recent:
            return None
        light = bool(t.data.get("light"))
        per = 90 if light else 220
        acts = "\n".join(f"{i}. {n} {a[:80]} → {r[:per]}" for i, (n, a, r) in enumerate(recent[-(5 if light else TB.POLL_EVERY):], 1))
        todo = self._todo_text(t.todos()) if t.todos() else t.plan()
        msg = (f"ЦЕЛЬ: {t.goal[:400 if light else 900]}\n\nСПИСОК ДЕЛ:\n{todo[:600 if light else 1600] or '(нет)'}\n\n"
               f"ПОСЛЕДНИЕ ШАГИ:\n{acts}\n\nОтветь одним JSON.")
        try:
            prof = self.host.llm_profile()
            raw = "".join(stream_chat(dict(prof, max_tokens=160, temperature=0.1), self.POLL_SYS, [{"role": "user", "content": msg}],
                                      cancel=t.cancel))
        except Exception as e:  # noqa: BLE001 — опрос хода — подсказка, его сбой задачу не останавливает
            log.info("Опрос хода не удался: %s", e)
            return None
        raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S)
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            d = json.loads(m.group(0)) if m else None
        except ValueError:
            d = None
        if not isinstance(d, dict) or not any(k in d for k in ("done", "loop", "progress")):
            return None
        b = lambda v: v is True or str(v).strip().lower() in ("true", "да", "yes")  # noqa: E731
        return {"done": b(d.get("done")), "loop": b(d.get("loop")), "progress": None if d.get("progress") is None else b(d.get("progress")),
                "next": str(d.get("next") or "").strip()[:240]}

    @staticmethod
    def _poll_every(prof):
        """Свой сервер модели (llama.cpp, LM Studio, Ollama — адрес на этом компьютере или в домашней сети) держит кэш одного
        разговора: каждый опрос хода вытесняет его, и следующий шаг считает запрос заново. Там — втрое реже."""
        from urllib.parse import urlparse
        host = (urlparse(str(prof.get("base_url") or "")).hostname or "").lower()
        local = (host in ("localhost", "0.0.0.0", "::1") or host.startswith(("127.", "192.168.", "10.")) or host.endswith(".local")
                 or re.match(r"172\.(1[6-9]|2\d|3[01])\.", host) or str(prof.get("kind") or "").lower() in ("ollama", "lmstudio", "llamacpp")
                 or prof.get("tools_mode") == "prompt")
        return TB.POLL_LOCAL if local else TB.POLL_EVERY

    def _work_sig(self, t):
        """Отпечаток работы: файлы (кроме плана и списков), блокнот, число сделанных пунктов. Смена плана сама по себе — не работа."""
        import hashlib
        try:
            files = sorted(f"{p.relative_to(t.dir)}:{p.stat().st_size}" for p in t.dir.rglob("*") if p.is_file() and not p.is_symlink()
                           and p.relative_to(t.dir).parts[0] not in Q.SERVICE and "рабочая копия" not in p.parts and not p.name.endswith(".tmp"))
        except OSError:
            files = []
        done = sum(1 for x in t.todos() if x.get("status") == "done")
        return hashlib.sha1("\n".join([t.notebook(), str(done), *files[:2000]]).encode()).hexdigest()[:16]

    def _stall(self, t, msgs, why, can_pause=True):
        """Застой (выпуск 4): первый — новый план с записью в журнал, а не пауза; второй подряд без работы между ними — пауза."""
        sig = self._work_sig(t)
        steps = int(t.data.get("steps") or 0)
        if int(t.data.get("stalls") or 0) >= 1 and can_pause and t.data.get("replan_sig") == sig:
            t.data["pause_now"] = (f"{why}: шагов подряд без продвижения и после смены плана — ни новых файлов, ни записей в "
                                   "блокноте, ни сделанных пунктов. Остановился, чтобы не тратить время и токены впустую. Напишите "
                                   "задаче, что делать, или скажите «продолжи задачу».")
            t.data["stuck"] = True
            return
        t.data.update(stalls=int(t.data.get("stalls") or 0) + 1, replan_sig=sig, replan_step=steps)
        d = t._json("задачи.json", {})
        d["replans"] = (d.get("replans") or []) + [{"at": _now(), "step": steps, "why": why}]
        if d.get("items") or d.get("replans"):
            t.put_json("задачи.json", d)
        t.journal(f"🔄 Застой ({why}) — прошу новый план, а не паузу.")
        self._add_user(msgs, self.REPLAN.format(why=why))

    def _reconcile(self, t, why):
        """Сверка при каждом продолжении после сна, передышки или перезапуска (Anthropic harness): что сделано по списку
        дел, какие файлы есть, что с критериями; «сделано», доказательства которого больше нет, — снова в работу."""
        items = t.todos()
        lost = []
        for x in items:
            if x.get("status") == "done" and str(x.get("evidence") or "") != "отмечено в план.md":
                bad = self._proof_bad(t, x.get("evidence"))
                if bad.startswith("файла"):
                    x.update(status="pending", evidence="", at=_now())
                    lost.append(f"{x.get('id')}. {x.get('text')}")
        if lost:
            self._save_todos(t, items, source=t._json("задачи.json", {}).get("source") or "json",
                             render=t._json("задачи.json", {}).get("source") != "md")
        light = bool(t.data.get("light"))
        outs = sorted(p for p in (t.dir / "outputs").rglob("*") if p.is_file() and not p.is_symlink()) if (t.dir / "outputs").is_dir() else []
        files = ", ".join(f"{p.relative_to(t.dir).as_posix()} ({p.stat().st_size} байт)" for p in outs[:8 if light else 20])
        done = sum(1 for x in items if x.get("status") == "done")
        nxt = next((x for x in items if x.get("status") == "in_progress"), None) or next((x for x in items if x.get("status") == "pending"), None)
        lines = [f"СВЕРКА ПЕРЕД ПРОДОЛЖЕНИЕМ ({why}). Прежде чем действовать, сверься с тем, что уже сделано:"]
        if items:
            lines.append(f"- список дел: сделано {done} из {len(items)}" + (f"; дальше — {nxt.get('id')}. {nxt.get('text')}" if nxt else ""))
        lines.append("- файлы результатов: " + (files + (f" и ещё {len(outs) - 20}" if len(outs) > 20 else "") if outs else "пока нет"))
        res = self._check_criteria(t, quick=True) if t.criteria().get("items") else []
        if res:
            lines.append("- критерии: " + "; ".join(("✓ " if r.get("ok") else "✗ " if r.get("ok") is False else "? ") + Q.crit_label(r) for r in res)[:600])
        if lost:
            lines.append("- ВНИМАНИЕ: отмечены сделанными, но доказательства больше нет — снова в работе: " + "; ".join(lost)[:400])
        lines.append("Проверь главное (file_glob, file_read), продолжай с первого несделанного пункта. Не начинай заново и не "
                     "переделывай сделанное.")
        t.journal(f"🔎 Сверка перед продолжением ({why}): сделано {done} из {len(items)}, файлов {len(outs)}"
                  + (f"; пропало: {'; '.join(lost)[:200]}" if lost else "") + ".")
        return "\n".join(lines)

    # ---------- качество (quality.py): проверка кодом, самопроверка, уроки ----------
    def _opt(self, key):
        """Настройка tasks.<key> (self_check, learn — см. settings.py); None — не задана, считается включённой."""
        try:
            return self.host.s.get("tasks", key)
        except Exception:  # noqa: BLE001
            return None

    def lessons_path(self):
        """Файл уроков в папке ассистента — его видно и можно править в студии."""
        return self.host.workspace.root / Q.LESSONS_FILE

    @staticmethod
    def _q(t):
        """Счётчики качества задачи в data["quality"]: хранятся в задача.json, поэтому переживают передышки и перезапуск.
        Идут в след задачи (_trace) для уроков."""
        return t.data.setdefault("quality", {"tools": {}, "errors": [], "loop_warns": 0, "refusal": 0, "verify_fail": 0, "critic": 0})

    def _ask(self, system, messages):
        """Короткий служебный запрос к модели (самопроверка, уроки): низкая температура, ответ до 900 токенов."""
        prof = self.host.llm_profile()
        if not prof:
            return ""
        return "".join(stream_chat(dict(prof, max_tokens=900, temperature=0.1), system, messages))

    def _web_used(self, t):
        """Пользовалась ли задача интернетом — без этого отказ «нет доступа» считается ложным."""
        used = self._q(t)["tools"]
        return any(used.get(k) for k in ("web_search", "read_webpage", "read_page", "download"))

    def _web_available(self, t):
        return any(x["name"] == "web_search" for x in self._specs(t))

    def _lab_files(self, t):
        """Файлы «Лаборатории» (lab_write, lab_run), созданные или изменённые во время задачи: она пишет туда, а не в
        папку задачи (№368: «list_files и самопроверка должны видеть ту же папку, куда пишет lab_write»)."""
        lab = self.host.workspace.root / "Лаборатория"
        try:
            since = TB.dt.datetime.fromisoformat(str(t.data.get("created") or "")).timestamp() - 5
        except ValueError:
            since = 0
        out = []
        if lab.is_dir():
            for p in sorted(lab.rglob("*")):
                try:
                    if p.is_file() and p.stat().st_mtime >= since:
                        out.append(p)
                except OSError:
                    continue
        return out[:200]

    def _clean(self, t, names=("_run", "_out", "_src", "_explore")):
        """По готовности удалить служебное: скрипты шагов (_run), длинные выводы (_out), опору проверки (_src). Остаётся то,
        что нужно человеку. Не выполнена или остановлена — без _out: продолжение читает длинные выводы оттуда."""
        import shutil
        for name in names:
            d = t.dir / name
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

    def _trace(self, t, reason):
        """Сохранить след законченной задачи (вне папки ассистента, в STATE_DIR) и, если пора, запустить уроки.
        reason: "final" | "failed" | "loop_detected"."""
        q = self._q(t)
        try:
            from settings import STATE_DIR
        except Exception:  # noqa: BLE001
            return
        Q.save_trace(STATE_DIR / "task_traces", {
            "id": t.id, "goal": f"{t.title}: {t.goal}"[:400], "ok": reason == "final", "reason": reason,
            "steps": t.data.get("steps", 0), "tools": q["tools"], "errors": q["errors"][-10:], "loop_warns": q["loop_warns"],
            "refusal": q["refusal"], "verify_fail": q["verify_fail"], "critic": q["critic"], "usage": q.get("usage") or {},
            "time": _now()})
        try:                                                 # HARNESS 8, п.9: уроки проверяются следующими задачами
            ch = Q.lessons_track(STATE_DIR / "task_traces" / Q.LESSONS_META, {"errors": q["errors"][-10:]}, self.lessons_path())
            for rule, st in ch.items():
                log.info("🎓 Урок %s: %s", "проверен" if st == "ok" else "не помог — уберу при следующих выводах", rule[:90])
        except Exception:  # noqa: BLE001
            log.debug("проверка уроков", exc_info=True)
        self._maybe_reflect(STATE_DIR / "task_traces")

    def _maybe_reflect(self, traces):
        """Не чаще REFLECT_EVERY (время прошлого раза — в файле .last) вывести уроки в отдельном потоке."""
        if self._opt("learn") is False:
            return
        last = traces / ".last"
        try:
            ago = time.time() - float(last.read_text())
        except (OSError, ValueError):
            ago = 1e12
        if ago < float(os.environ.get("DEWIAR_REFLECT_EVERY") or Q.REFLECT_EVERY):
            return

        def run():
            try:
                last.write_text(str(time.time()))            # сразу: даже при ошибке модели не повторять каждую задачу
                n = Q.reflect(self._ask, traces, self.lessons_path())
                if n:
                    self.host.announce(f"Я сделал выводы из прошлых задач: новых правил — {n}. Они в «Память/Уроки задач».")
            except Exception as e:  # noqa: BLE001
                log.info("Уроки задач не получились: %s", e)
        threading.Thread(target=run, name="task-reflect", daemon=True).start()
