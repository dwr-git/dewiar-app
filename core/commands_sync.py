"""Команды окон (студия, виджет, телефон): приветствие окна, синхронизация и устройства, мозги других устройств, «Знания», отчёты и жалобы,
суфлёр.
Часть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки
проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class SyncCommands:
    def _cmd_sync(self, cmd, a):
        if cmd == "hello":
            return self.snapshot()
        if cmd == "sync_status":
            return self.sync_public()
        if cmd == "devices_get":                  # «Устройства» (0.56): все мои устройства и синхронизация
            return self.devices_public(fresh=a.get("fresh", True) is not False)
        if cmd == "device_rename":                # своё имя этого компьютера: «Рабочий», «Домашний»
            self.s.update({"sync": {"name": str(a.get("name") or "").strip()[:40]}})
            self.sync.soon.set()
            return self.devices_public(fresh=False)
        if cmd == "device_forget":                # убрать из списка (снова выйдет на связь — появится)
            import httpx
            tok, link, url = self.credentials()
            if not tok:
                raise ValueError("здесь нет входа в Dewiar")
            h = {"Authorization": "Bearer " + tok}
            if link and link != tok:
                h["X-Sync-Link"] = link
            r = httpx.post(url, params={"p": "/sync/forget", "device": self.sync.state.get("device", "")}, json={"id": str(a.get("id") or "")}, headers=h, timeout=15)
            if r.status_code != 200:
                raise ValueError(((r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("error") or {}).get("message") or f"сайт ответил {r.status_code}")
            return self.devices_public(fresh=True)
        if cmd == "near_ask":                     # «Рядом — ещё одна Лира» → «Сделать одной Лирой» (1.0.36)
            return self.near_ask(str(a.get("to") or ""))
        if cmd == "near_answer":                  # то устройство предложило — «Да, одна Лира» / «Нет»
            return self.near_answer(str(a.get("id") or ""), bool(a.get("yes")))
        if cmd == "near_hide":                    # «Это не моё» — это устройство здесь больше не предлагать
            hid = dict(self.s.get("sync", "near_hide") or {})
            hid[str(a.get("id") or "")] = int(time.time())
            self.s.update({"sync": {"near_hide": dict(sorted(hid.items(), key=lambda kv: kv[1])[-50:])}})
            return self.devices_public(fresh=False)
        if cmd == "brains_pull":                  # «Взять мозги с другого устройства» (конвертом своим устройствам)
            return self.brains_pull()
        if cmd == "brains_status":
            return self.brains_status()
        if cmd == "pair_claim":                   # «Ввести код»: это устройство — та же Лира
            from cloud import CloudError
            try:
                return self.pair_claim(str(a.get("code") or ""), a.get("url", ""))
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd == "sync_now":
            from sync import SyncError
            try:
                self.sync.run_once()
            except SyncError as e:
                self.sync.status.update(ok=False, error=str(e), at=int(time.time()))
            if getattr(self, "home_sync", None) is not None and self.homehub and self.homehub.running():
                self.home_sync.soon.set()                # и телефонам по Wi-Fi (engine_home.py)
            return self.sync_public()
        if cmd == "sync_set":
            on = bool(a.get("on"))
            self.s.update({"sync": {"enabled": on}})
            if on and not any(t.name == "sync" for t in threading.enumerate()):     # поток синхронизации — один на ядро
                threading.Thread(target=self.sync.loop, args=(self.stopping,), name="sync", daemon=True).start()
            return self.sync_public()
        if cmd == "models_status":                # «Слух» и «Голос»: что скачано на этом компьютере
            return self.models_status()
        if cmd == "models_get":
            return self.models_get(str(a.get("key") or ""))
        if cmd == "sync_e2e":                     # шифрование синхронизации на устройстве (core/synckey.py)
            self.sync.e2e_enable(bool(a.get("on")))
            self.drive.kick.set()                 # «Облако Лиры» работает только шифром — включили: сразу обмен
            return self.sync_public()
        if cmd.startswith("drive_"):              # «Облако Лиры» (core/drive.py)
            dv = self.drive
            if cmd == "drive_status":
                if a.get("fresh") or time.time() - (dv.last.get("at") or 0) > 60:
                    dv.kick.set()
                return dv.status()
            if cmd == "drive_sync":
                return dv.tick()
            if cmd == "drive_remove":
                dv.remove(str(a.get("name") or ""))
                self.emit("tools", tools=self.toolbox.catalog())
                return dv.status()
            if cmd == "drive_open":
                p = dv.local().get(str(a.get("name") or ""))
                if p is None:
                    raise ValueError("этот файл ещё не пришёл на этот компьютер — подождите минуту")
                from tools import launch
                launch(["xdg-open", str(p)])
                return True
            if cmd == "drive_add_path":           # «Добавить файлы…» окном выбора: путь, без пересылки содержимого (до 25 МБ)
                from drive import EXTS as DX, FILE_MAX
                src = Path(str(a.get("path") or ""))
                if not src.is_file():
                    raise ValueError("такого файла нет")
                if src.suffix.lower() not in DX:
                    raise ValueError("такие файлы облако не берёт: PDF, Word, Excel, PowerPoint, текст и картинки")
                if src.stat().st_size > FILE_MAX:
                    raise ValueError(f"«{src.name}» больше 25 МБ")
                rel = self.knowledge.add(src.name, src.read_bytes())
                dv.kick.set()
                self.emit("tools", tools=self.toolbox.catalog())
                return {"added": rel, "files": self.knowledge.list(), "drive": dv.status()}
        if cmd.startswith("knowledge_"):         # «Знания» на этом компьютере
            kn = self.knowledge
            if cmd == "knowledge_add":
                import base64
                raw = a.get("b64", "")
                raw = raw.split(",", 1)[1] if raw.startswith("data:") else raw
                rel = kn.add(a.get("name", ""), base64.b64decode(raw))
                self.drive.kick.set()                  # «Облако Лиры»: новый файл — сразу на другие устройства
                self.emit("tools", tools=self.toolbox.catalog())
                return {"added": rel, "files": kn.list()}
            if cmd == "knowledge_remove":
                rel = str(a.get("path", ""))
                if "/" not in rel and "\\" not in rel:      # файл «Моих файлов» верхнего уровня — он и в «Облаке Лиры»: убрать везде
                    self.drive.remove(rel)
                    kn.refresh()
                else:
                    kn.remove(rel)
                self.emit("tools", tools=self.toolbox.catalog())
                return kn.list()
            if cmd == "knowledge_search":
                return kn.search(a.get("query", ""))
            if cmd == "knowledge_phone":               # «Мои файлы» на телефоне (0.98): сколько видно оттуда и почему, если нисколько
                st = self.sync.doc_status()
                st["phones"] = sum(1 for d in (self.sync.status.get("all") or []) if d.get("app") in ("phone", "web") and not d.get("me"))
                return st
            if cmd == "knowledge_open":
                from tools import launch
                launch(["xdg-open", str(kn.root)])
                return str(kn.root)
            if cmd == "knowledge_open_file":           # источник под ответом: открыть файл (только из индекса поиска)
                p = kn.file_path(a.get("key", ""))
                if p is None:
                    raise ValueError("этого файла больше нет")
                from tools import launch
                launch(["xdg-open", str(p)])
                return str(p)
            if cmd in ("knowledge_folders", "knowledge_folder_add", "knowledge_folder_remove"):   # свои папки для поиска
                cur = [str(x) for x in (self.s.get("knowledge", "folders") or [])]
                if cmd != "knowledge_folders":
                    from workspace import user_dir     # №821: кавычки, %USERPROFILE%, «С:», рабочий стол в OneDrive
                    raw = str(a.get("path") or "").strip()
                    got = user_dir(raw) if cmd == "knowledge_folder_add" else None
                    path = str((got or Path(os.path.expanduser(raw))).resolve()) if raw else ""
                    if cmd == "knowledge_folder_add":
                        if not path or not Path(path).is_dir():
                            raise ValueError("такой папки нет")
                        if Path(path) in (Path.home(), Path(Path.home().anchor)) or len(Path(path).parts) <= 1:
                            raise ValueError("весь диск или домашнюю папку целиком не берём — выберите папку с документами")
                        cur = cur + [path] if path not in cur else cur
                    else:
                        cur = [x for x in cur if x != path and str(Path(x).resolve()) != path]
                    self.s.update({"knowledge": {"folders": cur}})
                    kn.kick.set()
                    self.emit("tools", tools=self.toolbox.catalog())
                elif time.time() - getattr(kn, "folders_t", 0) > 20:
                    kn.kick.set()                    # открыли «Документы» — свою папку сверить сейчас (№428), студия спросит снова
                return kn.folders_state()
            return {"folder": str(kn.root), "files": kn.list()}
        if cmd == "report":
            return self.save_report()
        if cmd == "report_send":
            return self.report_send(a.get("note", ""))
        if cmd == "report_auto":                               # согласие на отчёты при сбое (из предложения в виджете/студии)
            self.s.update({"report": {"auto": bool(a.get("on"))}})
            return {"auto": bool(a.get("on"))}
        # жалобы (core/health.py): снимок экрана до открытия студии, отправка, мои жалобы и помощники проекта
        if cmd == "bug_shot":
            return self.bug_shot(a.get("image"), add=bool(a.get("add")))
        if cmd == "bug_shot_drop":                            # №546: × на одном из снимков жалобы
            return self.bug_shot_drop(str(a.get("id") or ""))
        if cmd == "bug_state":
            return self.bug_state()
        if cmd == "complaint_send":
            return self.complaint_send(a.get("note", ""), a.get("who", ""), bool(a.get("shot", True)), talk=a.get("talk", True) is not False)
        # суфлёр (core/prompter.py): окно ui/prompter.html
        if cmd.startswith("prompter_"):
            pr = self.prompter
            if cmd == "prompter_state":
                return pr.public()
            if cmd == "prompter_start":
                return pr.start(a.get("title", ""), a.get("goal", ""), a.get("mode", "auto"), a.get("them", True), a.get("me", True),
                                a.get("knowledge", False), a.get("keep_text", False), a.get("place", "online"), a.get("nudge", True))
            if cmd == "prompter_voice":                    # голос владельца: start — записать, stop — сохранить, forget
                act = a.get("action", "start")
                if act == "start":
                    return pr.enroll_start()
                if act == "forget":
                    return pr.enroll_forget()
                return pr.enroll_stop(save=act != "cancel")
            if cmd == "prompter_stop":
                return pr.stop(summary=a.get("summary", True))
            if cmd == "prompter_pause":
                return pr.pause(a.get("on", True))
            if cmd == "prompter_hint":
                return pr.hint(a.get("q", ""), "button")
            if cmd == "prompter_file":
                import base64
                raw = a.get("data") or ""
                data = base64.b64decode(raw.split(",", 1)[1] if raw.startswith("data:") else raw) if raw else None
                return pr.add_file(a.get("name", ""), data=data, path=a.get("path", ""))
            if cmd == "prompter_file_remove":
                return pr.remove_file(a.get("name", ""))
            if cmd == "prompter_meetings":                 # итоги прошлых встреч — студия, «Суфлёр»
                d = self.workspace.ensure() / "Встречи"
                fs = sorted(d.glob("*.md"), reverse=True)[:40] if d.is_dir() else []
                return [{"name": f.stem, "path": f"Встречи/{f.name}", "size": f.stat().st_size} for f in fs]
            if cmd == "prompter_meeting_remove":           # студия, «Прошлые встречи» → корзина (отзыв 17.10: «как удалить прошлую встречу?»)
                rel = str(a.get("path") or "")
                if not rel.startswith("Встречи/") or "/" in rel[len("Встречи/"):] or not rel.endswith(".md"):
                    raise ValueError("это не итог встречи")
                return self.workspace.remove(rel)
            if cmd == "prompter_open":
                self.emit("prompter", kind="open")
                return True
            raise ValueError("неизвестная команда суфлёра")
        if cmd == "complaints_seen":
            return self.complaints_seen()
        if cmd == "complaints":
            if a.get("check"):
                try:
                    self.complaints_check()
                except Exception as e:  # noqa: BLE001
                    log.info("🐞 ответы на жалобы: %s", e)
            return self.complaints_view(fresh=bool(a.get("check")))
        return NotImplemented
