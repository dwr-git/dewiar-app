"""Команды окон (студия, виджет, телефон): фоновые задачи, голоса, знакомство, проба голоса, питание, радио, «Совет ИИ», подкасты, устройства,
действия, «Пульт», «Выполнить?», телефон и перенос настроек, советы, навыки, плагины, MCP, состояние.
Часть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки
проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class TasksCommands:
    def _cmd_tasks(self, cmd, a):
        if cmd == "tasks_list":
            return self.tasks.list()
        if cmd == "task_get":
            try:
                return self.tasks.detail(a.get("id"))
            except KeyError as e:                       # пакет 28.10: задачу уже удалили, а студия просит её — не сбой программы
                raise ValueError(str(e).strip("'\"")) from None
        if cmd == "task_create":
            t = self.tasks.create(a.get("title", ""), a.get("goal", ""), a.get("project", ""), start=a.get("start", True),
                                  folders=a.get("folders") or (), search_url=a.get("search_url") or "", net=bool(a.get("net")),
                                  files=a.get("files") or ())
            return t.public()
        if cmd == "task_rewind":                               # выпуск 5: «Откатить к шагу N» / вернуть снимок (отменить откат)
            st, sq = a.get("step"), a.get("seq")
            return self.tasks.rewind(a.get("id"), step=int(st) if st not in (None, "") else None,
                                     seq=int(sq) if sq not in (None, "") else None)
        if cmd == "task_net":                                  # сеть для кода задачи (песочница) — даёт человек
            return self.tasks.set_net(a.get("id"), bool(a.get("on"))).public()
        if cmd in ("task_export", "task_open_result"):        # результат задачи: скачать (HTML/PDF/как есть) или открыть
            import export as X
            t = self.tasks.get(a.get("id"))
            rel = str(a.get("path") or "")
            src = (t.dir / rel).resolve()
            if not rel or t.dir.resolve() not in src.parents:     # безопасность: только файлы внутри папки задачи (не «../»)
                raise ValueError("такого результата у задачи нет")
            if cmd == "task_open_result":
                if os.environ.get("DEWIAR_DRY_TOOLS"):
                    return {"opened": str(src)}
                X.open_file(src)
                return {"opened": str(src)}
            title = next((o.get("title") for o in t.data.get("outputs") or [] if o.get("path") == rel), "") or t.title
            try:
                out = X.export(src, title, a.get("fmt") or "file", root=t.dir)
            except X.ExportError as e:
                raise ValueError(str(e)) from e
            if a.get("reveal", True) and not os.environ.get("DEWIAR_DRY_TOOLS"):
                X.reveal(out)
            return {"path": str(out), "name": out.name, "dir": str(out.parent)}
        if cmd in ("task_stop", "task_resume", "task_answer", "task_tell", "task_accept", "task_discard", "task_delete"):
            tid = a.get("id")
            if cmd == "task_tell":
                return self.tasks.tell(tid, a.get("text", "")).public()
            if cmd == "task_stop":
                return self.tasks.stop(tid).public()
            if cmd == "task_resume":
                return self.tasks.start(tid).public()
            if cmd == "task_answer":
                return self.tasks.answer(tid, a.get("text", "")).public()
            if cmd == "task_accept":
                return self.tasks.accept(tid)
            if cmd == "task_discard":
                return self.tasks.discard(tid)
            self.tasks.delete(tid)
            return True
        if cmd == "vosk_voices":
            if self.s.get("tts", "engine") == "vosk":
                self.ensure_vosk_tts()
            return {"ready": self.vosk_tts.ready, "loading": self._vosk_loading, "error": self.vosk_tts.error,
                    "speakers": self.vosk_tts.speakers}
        if cmd == "intro_start":                      # «Познакомиться» — знакомство голосом заново
            return self.intro_start()
        if cmd == "intro_stop":
            return self.intro_stop()
        if cmd == "voice_test":
            pid = a.get("persona") or self.s.get("persona")
            listen = bool(a.get("listen"))             # «Прослушать» ответ (идея №58): голосом того, кто отвечал, без смены персонажа
            if pid != self.s.get("persona") and not listen:
                self.switch_persona(pid)
            if listen and pid != self.s.get("persona") and self.personas.get(pid):
                a = dict(a, voice=dict(self._voice_cfg(pid), **(a.get("voice") or {})))
            p = self.personas.get(pid)
            text = a.get("text") or f"Привет! Я {p['name']}. {p.get('tagline', '')}."
            if listen:                                 # ответ из «Чата» — с разметкой Markdown: вслух — без звёздочек и решёток
                from llm import speakable
                text = speakable(text) or text
            with self._turn_lock:
                self._cancel_locked()
                self.turn_n += 1
                turn = Turn(self.turn_n)
                self.turn = turn
            q = queue.Queue()
            q.put(text)
            q.put(None)

            def run():
                self.ensure_voice(pid)                 # скачать голос — уже не в обработчике нажатия
                vid = (a.get("voice") or {}).get("piper")
                if vid in PIPER_VOICES and not self.piper.has(vid):   # «Послушать» до сохранения: выбранный, а не прежний
                    try:
                        self.note(f"Скачиваю голос {PIPER_VOICES[vid]}…")
                        self.piper.mirror = self._mirror("piper")
                        self.piper.ensure(vid)
                        self.note("")
                    except Exception as e:  # noqa: BLE001
                        log.warning("Голос не скачался: %s", e)
                self._speak_worker(turn, q, fx_override=a.get("fx"), voice_override=a.get("voice"), force=listen)
                with self._turn_lock:
                    if self.turn is turn:
                        self.turn = None
                        self.set_state("idle")
            threading.Thread(target=run, daemon=True).start()
            return True
        if cmd == "power_cancel":
            was = self.power.cancel()
            self.emit("power", cancelled=True)
            return {"cancelled": bool(was)}
        if cmd == "radio_status":
            return self.radio.status()
        if cmd == "radio_list":                   # свой список станций (с сайта или встроенный)
            return {"stations": self.music.stations(), "genres": self.music.genres(), "url": self.music.url()}
        if cmd == "radio_custom_list":                # свои радиостанции (№359): студия → «Музыка»
            return [x for x in (self.s.get("radio_custom") or []) if isinstance(x, dict)]
        if cmd == "radio_custom_add":
            try:
                st = self.radio_custom_save(a.get("name"), a.get("url"))
            except ValueError as e:
                raise ValueError(str(e)) from e
            if a.get("play"):
                self._play_station([dict(st, tags="своя", own=True)], "", "Включаю «{}».")
            return st
        if cmd.startswith("council_"):               # «Совет ИИ» (0.67, council.py)
            from council import CouncilError
            try:
                if cmd == "council_members":
                    return {"members": self.council.members(), "pick": self.council.default_pick(), "state": self.council.state(),
                            "history": self.council.history()}
                if cmd == "council_start":
                    return self.council.start(a.get("q"), a.get("pids"))
                if cmd == "council_stop":
                    return self.council.stop()
                if cmd == "council_state":
                    return self.council.state()
                if cmd == "council_history":
                    return self.council.history()
            except CouncilError as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("podcast_"):               # «Подкасты» (0.87, podcast.py)
            from podcast import PodcastError
            P = self.podcasts
            try:
                if cmd == "podcast_list":
                    return {"items": P.list(), "state": P.state(), "hosts": self.council.members(), "pick": [h["id"] for h in P.hosts()]}
                if cmd == "podcast_get":
                    return P.get(a.get("id"))
                if cmd == "podcast_estimate":
                    return P.estimate(a.get("minutes") or 10, a.get("chars") or 0, a.get("files") or (), a.get("urls") or 0, a.get("topic") or "")
                if cmd == "podcast_start":
                    return P.start({"topic": a.get("topic"), "urls": a.get("urls") or [], "files": a.get("files") or []},
                                   {"minutes": a.get("minutes"), "style": a.get("style"), "hosts": a.get("hosts"), "lang": a.get("lang"),
                                    "intro": a.get("intro", True)})
                if cmd == "podcast_resume":
                    return P.start(resume=str(a.get("id") or ""))
                if cmd == "podcast_stop":
                    return P.stop()
                if cmd == "podcast_delete":
                    return P.delete(a.get("id"))
                if cmd == "podcast_send":
                    return P.send(a.get("id"))
            except PodcastError as e:
                raise ValueError(str(e)) from e
            except WorkspaceError as e:
                raise ValueError(str(e)) from e
        if cmd == "radio_home":                       # вкладка «Радио» в студии (0.64)
            return self.radio_home()
        if cmd == "radio_search":
            return self.radio_find(a.get("q"))
        if cmd == "radio_play":
            return self.radio_play_one(a)
        if cmd == "radio_fav":                        # ♥ на станции: в «Мои станции» (и голосом — «включи …»)
            if a.get("on", True):
                return self.radio_custom_save(a.get("name"), a.get("url"), a.get("logo"), a.get("tags"))
            self.s.update({"radio_custom": [x for x in (self.s.get("radio_custom") or []) if isinstance(x, dict) and x.get("url") != a.get("url")]})
            return True
        if cmd == "radio_custom_del":
            self.s.update({"radio_custom": [x for x in (self.s.get("radio_custom") or []) if isinstance(x, dict) and x.get("url") != a.get("url")]})
            return True
        if cmd == "radio_custom_play":
            st = next((x for x in (self.s.get("radio_custom") or []) if isinstance(x, dict) and x.get("url") == a.get("url")), None)
            if not st:
                raise ValueError("такой станции нет в списке")
            self._play_station([dict(st, tags="своя", own=True)], "", "Включаю «{}».")
            return True
        if cmd == "radio_stop":
            self.radio.stop()
            return self.radio.status()
        if cmd == "voices_warm":                       # открыли «Голос» — загрузить голоса заранее
            if self.s.get("tts", "engine") == "vosk" and not self.vosk_tts.ready:
                self.ensure_vosk_tts()
            return {"ready": self.vosk_tts.ready}
        if cmd == "devices":
            return list_devices()
        if cmd == "tools":
            return self.toolbox.catalog()
        if cmd == "pult_data":                         # «Пульт Лиры» в окне заметок (16.11)
            return self._pult_data()
        if cmd == "confirm_answer":
            box = self.pending_confirm
            if box:
                box["answer"] = bool(a.get("ok"))
                box["always"] = bool(a.get("always"))         # кнопка «Всегда» (команды «только посмотреть» на сервере)
                box["event"].set()
            return True
        if cmd == "phone_home":                   # только умный дом — на телефон (QR в студии; ключ не уходит на сервер)
            import base64
            if not self.home.connected():
                raise ValueError("умный дом не подключён")
            raw = json.dumps({"dewiar": 1, "home": {"token": self.home.data.get("token", "")}}, separators=(",", ":")).encode("utf-8")
            return {"url": "dewiar://import?c=" + base64.urlsafe_b64encode(raw).decode().rstrip("=")}
        if cmd == "phone_config":                 # QR для телефона: мозг, слух, голос, умный дом — одним снимком камеры
            # безопасность: в ссылке открытым текстом ключи API и токен умного дома — QR показывать только владельцу;
            # формат dewiar://import?c=<base64url JSON без «=»> разбирает приложение (android/: MainActivity.java, app.js)
            import base64
            snap = self.s.snapshot()
            llm = snap.get("llm") or {}
            prof = (llm.get("profiles") or {}).get(llm.get("active")) or {}
            keep = {k: prof[k] for k in ("name", "kind", "base_url", "api_key", "model", "economy", "disable_thinking", "temperature", "cloud", "title") if prof.get(k) not in (None, "")}
            import net as _net
            keep["base_url"], was_local = _net.lan_url(keep.get("base_url", ""))   # 127.0.0.1 на телефоне — сам телефон (19.10)
            local_note = ""
            if was_local:
                local_note = ("Модель на этом компьютере. Чтобы телефон до неё дотянулся: в LM Studio — Developer → «Serve on Local "
                              "Network», в Ollama — переменная OLLAMA_HOST=0.0.0.0; телефон — в той же сети Wi-Fi."
                              if not re.search(r"//(127\.|localhost|0\.0\.0\.0)", keep["base_url"]) else
                              "Модель на этом компьютере, а адреса в домашней сети у него нет — телефон до неё не дотянется. Подключите в приложении облако или сервер.")
            out = {"dewiar": 1, "llm": {"active": "p", "profiles": {"p": keep}}, "persona": snap.get("persona", "lira")}
            if snap.get("user_name"):
                out["user_name"] = snap["user_name"]
            for sec in ("stt", "tts"):
                x = snap.get(sec) or {}
                if x.get("engine") == "remote" and (x.get("remote") or {}).get("base_url"):
                    r = x["remote"]
                    out[sec] = {"engine": "remote", "remote": {k: r[k] for k in ("base_url", "api_key", "model", "voice") if r.get(k)}}
            if self.home.connected():
                out["home"] = {"token": self.home.data.get("token", "")}
            raw = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return {"url": "dewiar://import?c=" + base64.urlsafe_b64encode(raw).decode().rstrip("="),
                    "apk": (self.s.get("updates", "url") or "https://dewiar.pro/dwrapp/latest.json").rsplit("/", 1)[0] + "/Dewiar.apk",
                    "brain": keep.get("name") or keep.get("base_url", ""), "local_note": local_note, "lan": was_local or bool(re.match(r"https?://(192\.168|10\.|172\.(1[6-9]|2\d|3[01])|localhost|127\.)", keep.get("base_url", "")))}
        if cmd == "config_export":
            return provision.export_settings(self.s.snapshot(), bool(a.get("secrets")),
                                             {"skills_note": [s["name"] for s in self.skills.catalog() if not s["builtin"]]})
        if cmd == "config_preview":
            return self._import(a)
        if cmd == "config_apply":
            return self._apply_import(a)
        if cmd == "config_pending":
            m = self.pending_import
            return provision.preview(m, self.s.snapshot()) if m else None
        if cmd == "tricks":                       # «Что я умею» в студии — data/tricks.json (тот же список, что на телефоне)
            return json.loads((Path(__file__).resolve().parent.parent / "data/tricks.json").read_text(encoding="utf-8"))
        if cmd == "skills":
            return self.skills.catalog()
        if cmd == "skill_install":
            if a.get("zip_b64"):
                import base64
                name = self.skills.install_zip(base64.b64decode(a["zip_b64"]), a.get("name", ""))
            elif a.get("text"):
                name = self.skills.install_text(a["text"])
            else:
                name = self.skills.install_url(a["url"])
            return {"name": name, "skills": self.skills.catalog()}
        if cmd == "skill_get":
            return self.skills.get(a["name"])
        if cmd == "skill_save":
            name = self.skills.save(a.get("name"), a.get("description"), a.get("body"), a.get("files"), a.get("old_name", ""))
            return {"name": name, "skills": self.skills.catalog()}
        if cmd == "skill_export":
            import base64
            return {"name": a["name"], "zip_b64": base64.b64encode(self.skills.export_zip(a["name"])).decode()}
        if cmd == "skill_draft":
            return self._draft_skill(a.get("idea", ""))
        if cmd == "skills_catalog":
            url = a.get("url") or self.s.get("skills", "catalog_url")
            if not url:
                raise ValueError("адрес каталога не указан")
            if a.get("url"):
                self.s.update({"skills": {"catalog_url": url}})
            return self.skills.catalog_fetch(url)
        if cmd == "skill_remove":
            self.skills.remove(a["name"])
            return self.skills.catalog()
        if cmd == "skill_toggle":
            off = set(self.s.get("skills", "disabled") or [])
            (off.discard if a.get("on") else off.add)(a["name"])
            self.s.update({"skills": {"disabled": sorted(off)}})
            return self.skills.catalog()
        if cmd == "skills_reload":
            self.skills.reload()
            return self.skills.catalog()
        if cmd.startswith("plugin"):                # «Плагины» в студии (core/plugins.py)
            return self._plugin_cmd(cmd, a)
        if cmd == "mcp_status":
            return self.mcp.status()
        if cmd == "status":
            return self.status
        return NotImplemented

    def _pult_data(self):
        """«Пульт Лиры» (16.11, макеты владельца): чем она занята в фоне и что в тишине — одним ответом для окна заметок.
        Только то, что уже есть: заметки (созвездие), дневник сегодня, Радар (свежее и растущая тема), что дальше по
        напоминаниям и делам, заявки с сайтов за сутки. Ничего не придумывает и не грузит модель."""
        now = time.time()
        out = {"notes": [], "counts": {}, "diary": None, "radar": None, "next": [], "leads": [], "who": "", "day": []}
        try:
            out["who"] = self.persona_name()
        except Exception:  # noqa: BLE001
            pass
        try:
            ns = self.workspace.notes(limit=160)
            out["notes"] = [{"t": (n.get("title") or "")[:60], "f": (n.get("folder") or "").split("/")[0][:30], "m": n.get("mtime") or 0,
                             "p": n.get("path") or ""} for n in ns]
            out["counts"]["notes"] = len(ns)
        except Exception:  # noqa: BLE001
            pass
        try:
            mem = self.workspace.memory_get() or ""
            out["counts"]["memory"] = sum(1 for ln in str(mem).splitlines() if ln.strip().startswith(("-", "*")))
        except Exception:  # noqa: BLE001
            pass
        try:
            import datetime as _dt
            p = self.workspace.root / "Дневник" / f"{_dt.date.today():%Y-%m-%d}.md"
            if p.is_file():
                txt = p.read_text(encoding="utf-8", errors="replace")
                parts = re.split(r"\n### ", txt)
                last = parts[-1] if len(parts) > 1 else ""
                head, _, body = last.partition("\n")
                out["diary"] = {"at": head.strip()[:40], "text": " ".join(body.split())[:420], "mtime": p.stat().st_mtime}
                # «Циферблат дня» (16.11, владелец: созвездие «выглядит странно и бесполезно») — все записи сегодня по времени
                day0 = _dt.datetime.combine(_dt.date.today(), _dt.time())
                for part in parts[1:]:
                    hd, _, bd = part.partition("\n")
                    m = re.match(r"\s*(\d{1,2}):(\d{2})", hd)
                    ts = int((day0 + _dt.timedelta(hours=int(m.group(1)), minutes=int(m.group(2)))).timestamp()) if m and int(m.group(1)) < 24 else 0
                    if ts and ts <= now + 60:                  # запись «из будущего» (часы, правка руками) — не на круг
                        out["day"].append({"k": "diary", "ts": ts, "t": " ".join(bd.split())[:220]})
        except Exception:  # noqa: BLE001
            pass
        ins = getattr(self, "insight", None)
        if ins is not None:
            try:
                fresh = sorted(ins.analyzed(24), key=lambda x: -(x.get("ts") or x.get("seen") or 0))[:3]
                # id — чтобы из «Пульта» открывалась сама статья в «читалке» Радара, а не весь Радар (владелец 17.11)
                out["radar"] = {"items": [{"id": x.get("id") or "", "title": (x.get("title") or "")[:140], "src": x.get("src_name") or "",
                                           "signal": float((x.get("a") or {}).get("signal") or 0), "ts": x.get("ts") or x.get("seen") or 0}
                                          for x in fresh],
                                "trend": ins.day_trend(), "n": len(ins.analyzed(24))}
                # тихий «Пульт» (владелец 16.11: «в моменты, когда тихо, — что-то из новых трендов»): сильнейшее за сутки
                # с «Сутью от Лиры» — одна карточка «Из Радара» вместо пустой ленты «Сегодня»
                best = max(ins.analyzed(24), key=lambda x: float((x.get("a") or {}).get("signal") or 0), default=None)
                if best and str((best.get("a") or {}).get("summary") or "").strip():
                    gist = " ".join(str(best["a"]["summary"]).split())
                    cut = re.search(r"^.{40,240}?[.!?…](?=\s|$)", gist)
                    out["radar"]["pick"] = {"id": best.get("id") or "", "title": (best.get("title") or "")[:140], "src": best.get("src_name") or "",
                                            "gist": cut.group(0) if cut else gist[:240]}
                for x in ins.analyzed(24):
                    ts = x.get("ts") or x.get("seen") or 0
                    if ts and now - ts < 12 * 3600:
                        out["day"].append({"k": "radar", "ts": int(ts), "t": (x.get("title") or "")[:160], "src": x.get("src_name") or "",
                                           "id": x.get("id") or ""})
                if not out["radar"]["items"]:
                    out["radar"] = None
            except Exception:  # noqa: BLE001
                out["radar"] = None
        try:
            from datetime import datetime as _d
            soon = []
            for x in list(self.reminders.items):
                if x.get("paused"):
                    continue
                try:
                    at = _d.fromisoformat(x["at"]).timestamp()
                except (KeyError, TypeError, ValueError):
                    continue
                if now - 60 <= at <= now + 36 * 3600:
                    soon.append({"at": int(at), "text": (x.get("text") or ("Будильник" if x.get("kind") == "alarm" else "Напоминание"))[:80],
                                 "job": x.get("kind") == "job"})
            soon.sort(key=lambda r: r["at"])
            out["next"] = soon[:3]
            out["day"] += [{"k": "job" if r["job"] else "remind", "ts": r["at"], "t": r["text"]} for r in soon if r["at"] <= now + 12 * 3600][:12]
        except Exception:  # noqa: BLE001
            pass
        sc = getattr(self, "sitechat", None)
        if sc is not None:
            try:
                for r in (sc.recent or [])[-5:][::-1]:
                    ts = r.get("ts") or 0
                    ts = ts / 1000 if ts > 1e12 else ts
                    if ts and now - ts < 24 * 3600:
                        out["leads"].append({"ts": int(ts), "name": (r.get("name") or "")[:60], "cid": r.get("cid") or ""})
                    if ts and now - ts < 12 * 3600:
                        out["day"].append({"k": "lead", "ts": int(ts), "t": (r.get("name") or "Посетитель сайта")[:60]})
            except Exception:  # noqa: BLE001
                pass
        out["day"] = sorted((x for x in out["day"] if abs(x["ts"] - now) <= 12 * 3600), key=lambda x: x["ts"])[-40:]
        return out

    def _plugin_cmd(self, cmd, a):
        """plugins — каталог; plugin_install {id, values} / plugin_remove {id, jobs: снимать ли его дела} / plugin_values {id, values} /
        plugin_job {id, job, on} — дело плагина по расписанию / plugin_zip {zip_b64} — свой плагин / plugin_delete {id}."""
        from plugins import PluginError
        from tools import ToolError, t_schedule_job
        P = self.plugins
        if cmd in ("plugin_page", "plugin_run", "plugin_restart", "plugin_files", "plugin_open", "plugin_ui"):
            return self._plugin_page_cmd(cmd, a)
        if cmd in ("plugin_make", "plugin_change", "plugin_versions", "plugin_restore", "plugin_undo", "plugin_templates",
                   "plugin_store", "plugin_data", "plugin_grant", "plugin_theme", "plugin_fetch"):
            return self._plugin_make_cmd(cmd, a)
        try:
            if cmd == "plugin_install":
                P.install(a["id"], a.get("values"))
            elif cmd == "plugin_remove":
                for rid in P.remove(a["id"]):
                    if a.get("jobs", True):
                        try:
                            self.reminders.cancel(rid)
                        except Exception:  # noqa: BLE001 — дело уже сняли руками
                            pass
            elif cmd == "plugin_values":
                P.set_values(a["id"], a.get("values") or {})
            elif cmd == "plugin_job":
                pid, jid = a["id"], a["job"]
                old = (((self.s.get("plugins", "on") or {}).get(pid) or {}).get("jobs") or {}).get(jid)
                if old:
                    try:
                        self.reminders.cancel(old)
                    except Exception:  # noqa: BLE001
                        pass
                rid = ""
                if a.get("on"):
                    from tools import home_city
                    task, when = P.job_text(pid, jid, fallback={"city": home_city(self)[0]})   # «Где дача» пусто — город из «Утра» или памяти
                    out = t_schedule_job({"task": task, "when": when, "title": P.job_label(pid, jid)}, {"reminders": self.reminders})
                    m = re.search(r"\(id ([^)]+)\)", out)
                    rid = m.group(1) if m else ""
                P.job_mark(pid, jid, rid)
            elif cmd == "plugin_zip":
                import base64
                P.install(P.install_zip(base64.b64decode(a.get("zip_b64") or "")))
            elif cmd == "plugin_delete":
                P.delete(a["id"])
                import plugin_bridge as B
                B.forget(self.s, a["id"])
                if ((self.s.get("ui", "plugin_theme") or {}).get("id")) == a["id"]:
                    self.s.update({"ui": {"plugin_theme": None}})
                    self.emit("plugin_theme", theme=None)
            elif cmd != "plugins":
                raise ValueError(f"неизвестная команда {cmd}")
        except (PluginError, ToolError, KeyError) as e:
            raise ValueError(str(e)) from e
        self.skills.reload()
        # plugin_values — тоже: сервер плагина получает настройки при запуске (DEWIAR_PLUGIN_SETTINGS), без перезапуска
        # новая «Папка с резюме» не доходила до него до перезапуска программы (03.11)
        if cmd in ("plugin_install", "plugin_remove", "plugin_zip", "plugin_delete", "plugin_values"):
            self.mcp.reconcile()
        out = {"plugins": P.catalog(), "skills": self.skills.catalog()}
        if cmd == "plugins":
            out["guide"] = P.guide()
        return out

    def plugins_changed(self, pid="", code=False, open_=False):
        """Плагин сделан или изменён Лирой: навыки, серверы (если есть код), меню студии и страница — сразу."""
        self.skills.reload()
        if code:
            self.mcp.reconcile()
            if pid:
                try:
                    self.mcp.plugin_restart(pid)
                except Exception:  # noqa: BLE001 — сервер ещё не поднялся: reconcile поднимет
                    pass
        p = self.plugins.items.get(pid) or {}
        self.emit("plugin_made", id=pid, name=p.get("name", ""), icon=p.get("icon", ""), open=bool(open_))

    def _plugin_make_cmd(self, cmd, a):
        """Лира делает плагин по описанию (core/plugin_maker.py) и расширенный мост страницы (core/plugin_bridge.py):
        plugin_make {describe, code, template} / plugin_change {id, request, code} / plugin_versions {id} /
        plugin_restore {id, v} / plugin_undo {id} / plugin_templates / plugin_store {id, op: get|set, key, value} /
        plugin_data {id, scope} — только с разрешения / plugin_grant {id, scope, on: true|false|null} /
        plugin_theme {id, vars | reset} / plugin_fetch {id, url} — текст статьи (читалка)."""
        import plugin_bridge as B
        from plugin_maker import MakerError
        M, P, pid = self.maker, self.plugins, str(a.get("id") or "")
        try:
            if cmd == "plugin_templates":
                return {"items": M.templates()}
            if cmd == "plugin_make":
                code = bool(a.get("code"))
                with M.using(str(a.get("by") or "") or None):          # «Кто делает» в студии — модель этого персонажа
                    r = M.from_template(a["template"]) if a.get("template") else M.create(a.get("describe") or "", code=code, name=a.get("name") or "")
                self.plugins_changed(r["id"], code=code)
                return dict(r, plugins=P.catalog())
            if cmd in ("plugin_change", "plugin_restore", "plugin_undo"):
                code = bool(a.get("code"))
                with M.using(str(a.get("by") or "") or None):
                    r0 = M.change(pid, a.get("request") or "", code=code) if cmd == "plugin_change" else None
                r = (r0 if cmd == "plugin_change" else
                     M.restore(pid, int(a.get("v") or 0), code=code) if cmd == "plugin_restore" else M.undo(pid, code=code))
                self.plugins_changed(pid, code=code or bool(r.get("code")))
                return dict(r, plugins=P.catalog(), versions=M.versions(pid))
            if cmd == "plugin_versions":
                M._made(pid)
                return M.versions(pid)
            if cmd == "plugin_theme" and a.get("reset"):        # «Оформление» → «Сбросить тему» — даже если плагина уже нет
                self.s.update({"ui": {"plugin_theme": None}})
                self.emit("plugin_theme", theme=None)
                return {"theme": None}
            if pid not in P.items:
                raise ValueError("нет такого плагина")
            if cmd == "plugin_store":
                if a.get("op") == "set":
                    return B.store_set(pid, a.get("key"), a.get("value"))
                return {"value": B.store_get(pid, a.get("key"))}
            if cmd == "plugin_grant":
                return {"grants": B.grant(self.s, P, pid, str(a.get("scope") or ""), a.get("on"))}
            if cmd == "plugin_data":
                return B.data(self.s, P, self, pid, str(a.get("scope") or ""))
            if cmd == "plugin_theme":
                t = B.set_theme(self.s, P, pid, a.get("vars"))
                self.emit("plugin_theme", theme=t)
                return {"theme": t}
            if cmd == "plugin_fetch":
                return B.read_url(self.s, a.get("url"))
        except (MakerError, B.BridgeError, KeyError) as e:
            raise ValueError(str(e).strip("'")) from e
        raise ValueError(f"неизвестная команда {cmd}")

    def _plugin_page_cmd(self, cmd, a):
        """Страница плагина в студии (core/plugin_pages.py, ui/studio/plugpage.js): plugin_page {id} — всё для страницы;
        plugin_run {id, tool, args} — действие плагина напрямую, без модели (только свои действия плагина);
        plugin_restart {id}; plugin_files {id}; plugin_open {id, path} — только внутри папок плагина и папки Dewiar;
        plugin_ui {id} — своя страница плагина (ui.html) для фрейма-песочницы."""
        import plugin_pages as PP
        from tools import ToolError
        P, pid = self.plugins, str(a.get("id") or "")
        try:
            ws = self.workspace.ensure()
        except Exception:  # noqa: BLE001
            ws = None
        try:
            if cmd == "plugin_page":
                import plugin_bridge as B
                pg = PP.page(P, self.mcp, pid, ws)
                pg["grants"] = B.grants(self.s, pid)
                if P.items[pid].get("made"):
                    pg["versions"] = self.maker.versions(pid)
                return pg
            if cmd == "plugin_run":
                if pid not in (self.s.get("plugins", "on") or {}):
                    raise PP.PageError("плагин не установлен — сначала «Установить»")
                return PP.run(P, self.mcp, pid, a.get("tool"), a.get("args") or {}, ws)
            if cmd == "plugin_restart":
                if P.items.get(pid, {}).get("mcp"):
                    self.mcp.plugin_restart(pid)
                return PP.page(P, self.mcp, pid, ws)
            if cmd == "plugin_files":
                return PP.files(P, pid, ws, a.get("limit") or 12)
            if cmd == "plugin_open":
                from tools import launch
                f = PP.safe_path(P, pid, ws, a.get("path"))
                launch(["xdg-open", str(f)])
                return str(f)
            if cmd == "plugin_ui":
                return {"html": PP.ui_html(P, pid)}
        except (PP.PageError, ToolError) as e:
            raise ValueError(str(e)) from e
        raise ValueError(f"неизвестная команда {cmd}")

    def _course_did(self, key):
        """Шаг урока «сделайте в студии…» (course.did) — без ошибок, если курса нет."""
        try:
            c = getattr(self, "course", None)
            if c is not None:
                c.did(key)
        except Exception:  # noqa: BLE001
            log.debug("курс: шаг %s", key, exc_info=True)
