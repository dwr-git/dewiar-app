"""Команды окон (студия, виджет, телефон): блокнот, «Ножницы», распознавание текста, заметки, вложения, «Мои файлы», рисунки, «Душа»,
дневник, экспорт и перенос папки, обновления.
Часть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки
проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class FilesCommands:
    def _cmd_files(self, cmd, a):
        if cmd.startswith("transcribe_") and getattr(self, "transcripts", None) is not None:   # плагин «Расшифровка» (1.0.33)
            import transcribe
            return transcribe.command(self.transcripts, cmd, a)
        if cmd.startswith("pad_"):                              # блокнот у виджета (ui/pad.html, core/pad.py)
            return self._pad_cmd(cmd, a)
        if cmd.startswith("snip_"):                             # «Вырезать кусок экрана» (ui/snip.html → блокнот)
            return self._snip_cmd(cmd, a)
        if cmd == "ocr_status":                                 # есть ли чем распознавать текст (core/ocr.py)
            import ocr
            return dict(ocr.status(), installing=bool(getattr(self, "_ocr_installing", False)))
        if cmd == "ocr_install":                                # «Поставить распознавание текста»
            return {"text": self.ocr_install_start()}
        if cmd == "notes_list":                                 # «Заметки»: все заметки и поиск
            return self.workspace.notes(a.get("q", ""))
        if cmd == "note_meta":                                  # метки, цвет, «закрепить», «в архив» — в шапку заметки (0.58)
            return self.workspace.note_meta(a.get("path", ""), a.get("patch") or {})
        if cmd == "notes_import_keep":                          # перенос из Google Keep (архив Takeout или папка)
            import keep_import
            path = str(a.get("path") or "").strip()
            if not path or not Path(os.path.expanduser(path)).exists():
                raise ValueError("выберите архив Google Takeout (.zip) или распакованную папку")
            r = keep_import.import_keep(self.workspace, os.path.expanduser(path),
                                        progress=lambda i, n: self.emit("keep_import", i=i, n=n) if i % 20 == 0 else None)
            self.emit("notes_changed")
            return r
        if cmd == "link_meta":                                  # ссылка в заметке — карточкой: название, картинка, сайт
            lm = getattr(self, "_linkmeta", None)
            if lm is None:
                from linkmeta import LinkMeta
                lm = self._linkmeta = LinkMeta(STATE_DIR / "links.json")
            return lm.get(a.get("url", ""))
        if cmd in ("note_attach", "note_file"):                 # «Заметки»: фото и файлы к заметке, картинка для показа
            import base64
            try:
                if cmd == "note_file":
                    return self.workspace.note_file(a.get("path", ""))
                r = self.workspace.note_attach(a.get("path", ""), a.get("name", ""), base64.b64decode(a.get("b64", "") or ""))
                self.note_files_out(a.get("path", ""), [r["path"]])           # фото заметки — и на свой телефон
                return r
            except (WorkspaceError, OSError, ValueError) as e:
                raise ValueError(str(e)) from e
        if cmd == "xray_get":                                   # «Рентген» ответа (core/xray.py)
            import xray
            r = xray.get(str(a.get("id") or ""), full=bool(a.get("full")))
            if r is None:
                raise ValueError("рентген этого ответа уже не хранится — он помнит последние 60 ответов")
            return r
        if cmd == "xray_list":
            import xray
            return {"items": xray.recent(int(a.get("n") or 20))}
        if cmd == "ws_read":
            try:
                return self.workspace.read(a.get("path", ""))
            except WorkspaceError as e:
                raise ValueError(str(e)) from e
        if cmd in ("ws_write", "ws_new_note", "ws_rename", "ws_delete"):      # «Память»: редактор заметок
            try:
                if cmd == "ws_write":
                    r = self.workspace.write(a.get("path", ""), a.get("text", ""))
                elif cmd == "ws_new_note":
                    r = {"path": self.workspace.new_note(a.get("title", ""), a.get("folder") or "Заметки", a.get("text", ""))}
                elif cmd == "ws_rename":
                    r = {"path": self.workspace.rename(a.get("path", ""), a.get("title", ""))}
                else:
                    r = self.workspace.remove(a.get("path", ""))
            except (WorkspaceError, OSError) as e:
                raise ValueError(str(e)) from e
            except Exception as e:  # noqa: BLE001 — защита корзины и т. п.
                raise ValueError(str(e)) from e
            try:
                self.recall.invalidate()
            except Exception:  # noqa: BLE001
                pass
            return r
        if cmd == "art_list":                       # студия → «Рисунки»: работы «Художника» (папка Dewiar → «Рисунки»)
            import base64
            d = self.workspace.ensure() / "Рисунки"
            try:
                works = json.loads((d / ".gallery.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                works = []
            out = []
            for w in sorted((x for x in works if isinstance(x, dict) and (d / str(x.get("page", ""))).is_file()),
                            key=lambda x: x.get("at", ""), reverse=True)[:int(a.get("limit") or 60)]:
                f, prev = d / str(w.get("file", "")), ""
                try:
                    if f.suffix == ".svg" and f.stat().st_size < 400_000:
                        prev = "data:image/svg+xml;base64," + base64.b64encode(f.read_bytes()).decode()
                    elif f.suffix == ".png" and f.stat().st_size < 3_000_000:
                        prev = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()
                except OSError:
                    prev = ""
                out.append({"title": str(w.get("title", "")), "kind": w.get("kind", "picture"), "at": str(w.get("at", "")),
                            "page": "Рисунки/" + str(w.get("page")), "preview": prev})
            return {"items": out, "folder": str(d)}
        if cmd == "ws_open":
            from tools import launch
            import export as X
            p = self.workspace.safe(a.get("path", "")) if a.get("path") else self.workspace.ensure()
            if not X.safe_to_open(p):               # .desktop, .sh, .jar… (мог написать код задачи) — только показать в папке
                launch(["xdg-open", str(p.parent)])
                return str(p)
            launch(["xdg-open", str(p)])
            return str(p)
        if cmd in ("soul_get", "soul_save", "soul_update", "soul_delete", "const_get", "const_save", "const_reset"):
            name = (a.get("persona") or "").strip() or self.persona_name()
            if cmd == "soul_delete":
                self.soul.delete_soul(name)
            elif cmd == "soul_save":
                self.soul.save_soul(name, a.get("text", ""))
            elif cmd == "soul_update":
                if not self.s.active_llm():
                    raise ValueError("нет модели — подключите её в «Мозге»")
                if not self.soul.update(name, force=True):
                    raise ValueError("душа уже обновляется — минутку")
                self.emit("soul", name=name)
            elif cmd == "const_save":
                self.soul.save_constitution(a.get("text", ""))
            elif cmd == "const_reset":
                self.soul.reset_constitution()
            if cmd.startswith("const_"):
                return {"text": self.soul.constitution(), "path": "Память/Конституция.md", "on": self.s.get("soul", "constitution") is not False}
            return self.soul.public(name)
        if cmd == "diary_list":
            return self.diary.entries()
        if cmd == "ctx_view":                                   # «О программе» → «Для отладки: что Лира сейчас учитывает»
            return self.ctx_view()
        if cmd in ("diary_entry_save", "diary_entry_delete"):     # «Дневник»: поправить или удалить запись (28.10)
            if cmd == "diary_entry_save":
                return self.diary.entry_save(a.get("day"), a.get("i", -1), a.get("text", ""), a.get("title"))
            return self.diary.entry_delete(a.get("day"), a.get("i", -1))
        if cmd == "diary_insight_drop":                         # «Дневник»: вывод ночи — не учитывать в разговоре
            return self.diary.drop_insight(a.get("i"))
        if cmd == "diary_write_now":                           # «Записать сейчас»: запись о сегодняшнем (или указанном) дне
            got = self.diary.write(a.get("day") or None, force=True)
            if not got:
                raise ValueError("запись уже пишется — минутку")
            self.emit("diary", **got)
            return got
        if cmd == "ws_export":                               # «Папка»: копия файла в «Загрузки» (страницу — и в PDF)
            import export as X
            try:
                src = self.workspace.safe(a.get("path", ""))
                out = X.export(src, X.page_title(src), a.get("fmt") or "file")
            except (WorkspaceError, X.ExportError) as e:
                raise ValueError(str(e)) from e
            if a.get("reveal", True) and not os.environ.get("DEWIAR_DRY_TOOLS"):
                X.reveal(out)
            return {"path": str(out), "name": out.name, "dir": str(out.parent)}
        if cmd == "ws_move":                              # №538: перенести папку ассистента (с копированием) и переключиться
            r = self.workspace.move_to(a.get("path") or "")
            a = {"path": r["path"]}
            cmd = "ws_set_path"
            self._ws_moved = r
        if cmd == "ws_set_path":
            path = (a.get("path") or "").strip()
            self.s.update({"workspace": {"path": path}})
            self.workspace.ensure()
            self.skills.set_folder(self.workspace.root / "Навыки")
            self.workspace.sync_reminders(self.reminders.items)
            moved, self._ws_moved = getattr(self, "_ws_moved", None), None
            return dict(moved, path=str(self.workspace.root)) if moved else str(self.workspace.root)
        if cmd == "update_status":
            return self.updater.public()
        if cmd == "self_check":
            return self.self_check()
        if cmd == "update_check":
            # 0.82.2 (04.11: «Занят: проверяет обновления — 200 с»): проверка — секунды; новая версия качается в фоне,
            # ход — в public()["downloading"] и событиях "update" («Скачиваю 0.82.2 — 45 % (с dewiar.pro)»)
            self.updater.check(wait=False)
            return self.updater.public()
        return NotImplemented

    def ocr_vision(self, b64):
        """Модель со зрением распознаёт текст на картинке (JPEG base64) -> ответ модели. LLMError — модели нет или она
        не видит картинок (тогда запоминаем: _blind, как в разговоре)."""
        import ocr
        from llm import LLMError, stream_events, user_message
        prof = self.persona_llm()
        if not prof:
            raise LLMError("модель не подключена")
        key = f"{prof.get('base_url')}|{prof.get('model')}"
        if key in self._blind:
            raise LLMError("модель не видит картинок")
        prof = dict(prof, temperature=0, think="off", max_tokens=max(2048, int(prof.get("max_tokens") or 0)))
        out = ""
        try:
            for kind, val in stream_events(prof, "Ты точно переписываешь текст с картинок.", [user_message(prof, ocr.VISION_PROMPT, [b64])], tools=None):
                if kind == "text":
                    out += val
        except LLMError as e:
            if re.search(r"image|vision|multimodal|картин|изображ", str(e), re.I):
                self._blind.add(key)
            raise
        return out

    def ocr_install_start(self):
        """«Поставить распознавание текста» — в фоне (ocr.install). -> что сказать сейчас."""
        if getattr(self, "_ocr_installing", False):
            return "Распознавание текста уже ставится — скажу, когда будет готово."
        self._ocr_installing = True

        def run():
            import ocr
            try:
                ok, msg = ocr.install(on_status=lambda t: self.emit("ocr_install", state="busy", text=t))
            except Exception as e:  # noqa: BLE001
                ok, msg = False, f"не получилось: {str(e)[:200]}"
            self._ocr_installing = False
            if not ok:
                msg = "Распознавание текста не поставилось: " + msg
            log.info("🔤 %s", msg)
            self.emit("ocr_install", state="done" if ok else "fail", text=msg)
            self.note(msg)
        threading.Thread(target=run, name="ocr-install", daemon=True).start()
        return "Ставлю распознавание текста (около 70 МБ, пару минут) — напишу, когда будет готово."

    def _snip_cmd(self, cmd, a):
        import base64
        import io
        import uuid
        shots = self.__dict__.setdefault("_snip_shots", {})
        items = self.__dict__.setdefault("_snips", {})
        now = time.monotonic()
        for k in [k for k, v in shots.items() if now - v["t"] > 300]:
            shots.pop(k, None)                                  # снимок экрана в памяти — не дольше 5 минут
        for k in [k for k, v in items.items() if now - v["t"] > 600]:
            items.pop(k, None)
        if cmd == "snip_shot":
            from eyes import EyesError, capture_screen
            from PIL import Image
            from tools import desktop_env
            try:
                data = capture_screen(desktop_env())
                im = Image.open(io.BytesIO(data))
                im.load()
            except (EyesError, OSError) as e:
                raise ValueError(str(e)) from e
            except Exception as e:  # noqa: BLE001
                raise ValueError(f"снимок экрана не прочитался: {e}") from e
            shots.clear()                                       # одно выделение за раз
            sid = uuid.uuid4().hex[:12]
            shots[sid] = {"im": im.convert("RGB"), "t": now}
            buf = io.BytesIO()
            shots[sid]["im"].save(buf, "JPEG", quality=90)
            return {"id": sid, "url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(),
                    "w": im.width, "h": im.height}
        if cmd == "snip_cancel":
            shots.pop(str(a.get("id") or ""), None)
            return True
        if cmd == "snip_done":
            shot = shots.pop(str(a.get("id") or ""), None)
            if shot is None:
                raise ValueError("снимок экрана устарел — вырежьте ещё раз")
            im = shot["im"]
            try:
                x, y, w, h = [int(round(float(v))) for v in (a.get("rect") or [])][:4]
            except (TypeError, ValueError) as e:
                raise ValueError("не понял рамку") from e
            x, y = max(0, min(x, im.width - 1)), max(0, min(y, im.height - 1))
            w, h = max(1, min(w, im.width - x)), max(1, min(h, im.height - y))
            if w < 4 or h < 4:
                raise ValueError("выделен слишком маленький кусок")
            crop = im.crop((x, y, x + w, y + h))
            buf = io.BytesIO()
            crop.save(buf, "PNG")
            try:
                tab = self.pad.tabs()["active"]
                att = self.pad.attach(tab, time.strftime("Вырезано %d.%m %H-%M-%S") + ".png", base64.b64encode(buf.getvalue()).decode())
            except Exception as e:  # noqa: BLE001
                raise ValueError(f"в блокнот не легло: {e}") from e
            sid = str(a.get("id"))
            it = {"id": sid, "tab": tab, "line": att["line"], "state": "image", "text": "", "engine": "", "error": "",
                  "install": False, "t": now, "acked": []}
            items[sid] = it
            self.emit("snip", **{k: v for k, v in it.items() if k not in ("t", "acked")})
            threading.Thread(target=self._snip_ocr, args=(it, crop), name="snip-ocr", daemon=True).start()
            log.info("✂ Вырезан кусок экрана %d×%d → блокнот «%s»", w, h, tab)
            return {"id": sid, "tab": tab, "line": att["line"]}
        if cmd == "snip_take":                                  # блокнот открылся — что вырезано и ещё не вставлено
            return [{k: v for k, v in it.items() if k not in ("t",)} for it in items.values()
                    if "text" not in it["acked"] and now - it["t"] < 120]
        if cmd == "snip_ack":                                   # блокнот вставил: stage — image или text
            it = items.get(str(a.get("id") or ""))
            if it is not None and a.get("stage") in ("image", "text") and a["stage"] not in it["acked"]:
                it["acked"].append(a["stage"])
            return True
        raise ValueError(f"неизвестная команда {cmd}")

    def _snip_ocr(self, it, crop):
        import ocr
        try:
            text, engine = ocr.recognize(crop, vision=self.ocr_vision)
            it.update(text=text, engine=engine)
            log.info("✂ Распознано %d знаков (%s)", len(text), engine)
        except ocr.OCRError as e:
            it.update(error=str(e), install=not ocr.local_engines())
            log.info("✂ Текст не распознан: %s", e)
        except Exception as e:  # noqa: BLE001
            it.update(error=f"не получилось распознать: {str(e)[:200]}")
            log.warning("✂ Распознавание: %s", e)
        it["state"] = "text"
        self.emit("snip", **{k: v for k, v in it.items() if k not in ("t", "acked")})
        threading.Timer(self.SNIP_KEEP, self._snip_fallback, args=(it,)).start()

    def _snip_fallback(self, it):
        """Блокнот так и не вставил вырезанное (не открылся) — дописать во вкладку самим."""
        add = ([it["line"]] if "image" not in it["acked"] else []) + ([it["text"]] if it["text"] and "text" not in it["acked"] else [])
        if not add:
            return
        it["acked"] += ["image", "text"]
        try:
            p = self.pad._path(it["tab"])
            old = p.read_text(encoding="utf-8") if p.is_file() else ""
            self.pad.write(it["tab"], old.rstrip("\n") + ("\n\n" if old.strip() else "") + "\n\n".join(add) + "\n")
            self.emit("pad_changed", name=p.stem, deleted=False)
            if it["text"]:
                self.note("Текст с экрана — в блокноте и в буфере обмена.")
        except Exception as e:  # noqa: BLE001
            log.warning("✂ Во вкладку не дописалось: %s", e)

    def _pad_cmd(self, cmd, a):
        """pad_tabs / pad_read {name} / pad_write {name, text, base} / pad_new {name} / pad_rename {name, to} /
        pad_delete {name} / pad_order {names} / pad_attach {name, filename, b64} / pad_file {link}."""
        P = self.pad
        if cmd in ("pad_ai", "pad_ai_stop"):                    # ИИ-правка в блокноте (core/padai.py, ui/padai.js)
            if getattr(self, "padai", None) is None:
                from padai import PadAI
                self.padai = PadAI(self)
            return self.padai.start(a) if cmd == "pad_ai" else self.padai.stop(a.get("id", ""))
        try:
            if cmd == "pad_tabs":
                return P.tabs()
            if cmd == "pad_read":
                return P.read(a.get("name", ""))
            if cmd == "pad_write":
                r = P.write(a.get("name", ""), a.get("text", ""), a.get("base"))
                sy = getattr(self, "sync", None)
                if sy is not None:
                    sy.soon.set() if hasattr(sy, "soon") else None   # дома поправили — на работе уже через минуту
                return r
            if cmd == "pad_new":
                return P.new(a.get("name", ""))
            if cmd == "pad_rename":
                return P.rename(a.get("name", ""), a.get("to", ""))
            if cmd == "pad_delete":
                return P.delete(a.get("name", ""))
            if cmd == "pad_order":
                return P.order(a.get("names") or [])
            if cmd == "pad_lock":                       # 05.11: 🔒 — запереть / открыть вкладку (только руками)
                r = P.lock(a.get("name", ""), bool(a.get("on")))
                sy = getattr(self, "sync", None)
                if sy is not None and hasattr(sy, "soon"):
                    sy.soon.set()                       # замок — и на другие устройства
                return r
            if cmd == "pad_attach":
                return P.attach(a.get("name", ""), a.get("filename", ""), a.get("b64", ""))
            if cmd == "pad_file":
                return P.file(a.get("link", ""))
        except (PadError, WorkspaceError, OSError) as e:
            raise ValueError(str(e)) from e
        raise ValueError(f"неизвестная команда {cmd}")
