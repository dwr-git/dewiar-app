"""Синхронизация — чужие изменения (часть Sync, чистое ядро 1.0.16): применить запись, удаление только доказанное,
персонаж с телефона, душа и дневник, заметки (замок, конфликт правок, смена папки), вкладки блокнота, «Обо мне»."""
import datetime as dt
import hashlib
import os
import re
import time
from pathlib import Path
from sync_base import (
    CONST_PREV, DIARY_MAX, EXTRA_KINDS, _FACT, _fact_id, _h, log, MEMORY, MIND_MAX, _mind_text, _note_norm, NOTES,
    PAD_DIR)
import sync_base as SB  # подменяемые в проверках имена — через основу


class ApplyMixin:
    # ---------- задачи с телефона по Wi-Fi (04.11: раньше терялись молча) ----------
    # Облачная Sync сначала занимает задачу в облаке (taken_by), потому что взяться могут два компьютера. По Wi-Fi узел —
    # этот компьютер, занимать не у кого: задача без to (или с to = этот) — сразу в «Задачи»; с to другого компьютера —
    # в облако (send_taskreq): этот компьютер — мост. Облака нет — на телефон честное «не передано» (запись task, failed).

    # ---------- применить чужое изменение ----------

    def _apply(self, it):
        """Применяет запись с другого устройства. -> False, если она осознанно не легла здесь (прошедшее разовое
        напоминание, удаление души или дневника, чужой ход задачи, хранилище выключено): в idx она помечается skip,
        и её отсутствие у нас не уходит в облако удалением. Как в syncApply() в app.js."""
        kind, iid, d = it["kind"], it["id"], it.get("data") or {}
        deleted = it.get("deleted")
        if kind == "reminder":
            if deleted:
                self.host.reminders.remove(iid)
                return
            at = dt.datetime.fromtimestamp(int(d.get("at") or 0) / 1000).replace(microsecond=0)
            if not d.get("repeat") and at < dt.datetime.now() - dt.timedelta(minutes=5) and not self.host.reminders.get(iid):
                return False                               # разовое и уже прошло — звенеть задним числом незачем
            self.host.reminders.upsert({"id": iid, "at": at.isoformat(timespec="seconds"), "text": d.get("text") or "Напоминание",
                                        "repeat": d.get("repeat") or None, "kind": d.get("kind") or "reminder",
                                        "paused": bool(d.get("paused")), **({"note_id": d.get("note") or ""} if "note" in d else {}),
                                        **({"who": str(d["who"])[:40]} if d.get("who") else {})})
        elif kind == "money":
            if deleted:
                self.host.money.delete(iid)
            elif float(d.get("amount") or 0) > 0:
                self.host.money.upsert(dict(d, id=iid))
        elif kind == "note":
            return self._apply_note(iid, d, deleted, it.get("updated"))
        elif kind == "memory":
            self._apply_fact(iid, d.get("text") or "", deleted)
        elif kind == "pmemory":
            return self._apply_pmemory(iid, d, deleted)
        elif kind == "vault":
            return self._apply_vault(iid, d, deleted, it)
        elif kind == "safe":
            return self._apply_safe(iid, d, deleted, it)
        elif kind == "client":
            return self._apply_client(iid, d, deleted, it)
        elif kind == "doc":
            return False                                  # файлы другого компьютера здесь не нужны: у него свои «Мои файлы»
        elif kind in EXTRA_KINDS:
            return self._apply_extra(kind, iid, d, deleted, it.get("updated"))

    def _really_gone(self, key):
        """Запись пропала из снимка — это удаление, только если её источника правда нет. Отключённый диск с хранилищем,
        выключенная галочка «всё хранилище», заметка сверх предела или больше 300 КБ, файл, который сейчас не читается, —
        не удаление: иначе другие устройства отправили бы эти заметки в корзину."""
        kind, iid = key.split(":", 1)
        if kind == "note":
            rel = self.state.get("map", {}).get(iid)
            return not (rel and (self._notes_root() / rel).exists())
        if kind == "vault":
            ob = getattr(self.host, "obsidian", None)
            v = ob.vault() if ob is not None else None
            if v is None or not ob.sync_all():
                return False
            rel = self.state.get("vmap", {}).get(iid)
            return not (rel and (v / rel).exists())
        if kind in ("soul", "mind", "diary", "task", "done", "persona", "bill", "pay", "payfile", "safe", "plugin") and self.state.get("_extra_failed"):
            return False
        if kind == "plugin":                      # удаление — только если плагин был здесь и его папки больше нет (не «не влез»,
            import plugin_sync as PS              # не «не прочитался», не «ещё не собрался из кусков»)
            pid, _, i = iid.partition(".")
            c = (self.state.get("plg") or {}).get(pid)
            P = getattr(self.host, "plugins", None)
            if P is None or pid not in (self.state.get("plg_had") or {}):
                return False
            if not PS.present(P, pid):
                return True
            return bool(i) and c is not None and i.isdigit() and int(i) >= c[2]     # сборка стала короче — лишний кусок
        if kind == "doc":                         # шифрование выключили, собрать не вышло — не удаление; файл пропал или
            return self._docs_ok() and not self.state.get("_doc_failed") and not self.state.get("_extra_failed")   # выпал из предела — удаление
        if kind == "client":                      # шифрование выключили — карточки остаются, это не удаление
            cl = getattr(self.host, "clients", None)
            return self._clients_ok() and cl is not None and iid not in cl.st["clients"]
        if kind == "safe":                        # выключили здесь, мастер-пароль сменили, сейф не открылся — не удаление
            vt = getattr(self.host, "vault", None)
            if iid == "key" or vt is None or self._safe_on() is None or self.state.get("_safe_failed"):
                return False
            try:
                return vt.get(iid) is None
            except Exception:  # noqa: BLE001
                return False
        if kind == "payfile":                     # файл ещё не пришёл целиком или не читается — не удаление; удаление — когда
            pm = getattr(self.host, "payments", None)        # ни один счёт и ни одна оплата его больше не помнят
            rel = (self.state.get("pfmap") or {}).get(iid.split(".")[0])
            return pm is None or not rel or rel not in pm.att_paths()
        return True

    def _apply_persona(self, iid, d, deleted):
        """Свой персонаж с телефона: создать, обновить (имя, пол, роль, характер, цвет, облик) или удалить. Встроенных и из
        галереи не трогаем. Характер с телефона короткий («весёлая, отвечает коротко») — дописываем «Ты — имя, роль.»"""
        pers = getattr(self.host, "personas", None)
        if pers is None or not hasattr(pers, "own_ids") or not re.fullmatch(r"[\w-]{1,40}", iid or ""):
            return False
        if iid in pers.fixed_ids():
            return False
        cur = next((p for p in pers.all() if p.get("id") == iid), None)
        if deleted:
            if cur is not None:
                pers.delete(iid)
                log.info("🔄 Персонаж «%s» удалён на другом устройстве", cur.get("name"))
            return None
        name = str(d.get("name") or "").strip()[:24]
        if not name:
            return False
        about, role = str(d.get("about") or "").strip()[:4000], str(d.get("role") or "").strip()[:60]
        char = about if re.match(r"\s*Ты\s", about) else f"Ты — {name}{', ' + role if role else ''}. {about}".strip()
        p = {"id": iid, "name": name, "gender": "male" if d.get("gender") == "male" else "female", "role": role, "about": about,
             "color": d.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(d.get("color") or "")) else "#8A9BFF",
             "character": char, "wake": [name.lower()]}
        av = str(d.get("avatar") or "")
        if av.startswith("data:image/") and (cur is None or pers.avatar_data_url(cur) != av):
            p["avatar_data"] = av
        if cur is not None and all(cur.get(k) == p[k] for k in ("name", "gender", "role", "color", "character")) and "avatar_data" not in p:
            return None
        pers.save(p)
        log.info("🔄 Персонаж «%s» — с другого устройства", name)
        return None

    def _apply_extra(self, kind, iid, d, deleted, it_updated=0):
        """Душа, конституция, выводы, дневник — удалением не стираются: у другого устройства запись могла просто
        выпасть из снимка (дневник там — за DIARY_DAYS дней), а написанное терять нельзя. Разговор (dayturn) и задачу (taskreq)
        с телефона забираем к себе; в следующем снимке их нет — и run_once сам шлёт их удаление, облако их забывает.
        Ход задач другого компьютера (task) — только для телефона: пропускаем."""
        h = self.host
        if kind == "persona":
            return self._apply_persona(iid, d, deleted)
        if kind in ("bill", "pay", "payfile"):
            return self._apply_pay(kind, iid, d, deleted)
        if kind == "plugin":
            return self._apply_plugin(iid, d, deleted, it_updated)
        if kind == "mind" and iid == "e2e":
            return self._apply_mark(d, deleted)
        if kind in ("soul", "mind", "diary", "task") and deleted:
            return False
        if kind == "soul":
            text = _mind_text(d, MIND_MAX)
            if text is None:
                log.warning("🔄 Душа «%s» с другого устройства не принята: не похожа на душу (длиннее %d знаков или не текст)", iid, MIND_MAX)
                return False
            if text.strip() and text.strip() != h.soul.soul(iid).strip():
                h.soul.save_soul(iid, text)
                log.info("🔄 Душа «%s» — правка с другого устройства", iid)
        elif kind == "mind" and iid == "constitution":
            text = _mind_text(d, MIND_MAX)
            if text is None:
                log.warning("🔄 Конституция с другого устройства не принята: длиннее %d знаков или не текст", MIND_MAX)
                return False
            old = h.soul.constitution()
            if text.strip() and text.strip() != old.strip():
                try:
                    h.soul.save_constitution(text)
                except ValueError as e:
                    log.warning("🔄 Конституция с другого устройства не принята: %s", e)
                    return False
                # принципы помощника поменялись не здесь — прежние сохраняем рядом и говорим человеку: если это не он,
                # вернуть их можно одним копированием, а ключ аккаунта — сменить
                try:
                    prev = h.workspace.ensure() / CONST_PREV
                    prev.parent.mkdir(parents=True, exist_ok=True)
                    prev.write_text(old, encoding="utf-8")
                except Exception as e:  # noqa: BLE001
                    log.warning("прежняя конституция не сохранилась: %s", e)
                log.info("🔄 Конституция — правка с другого устройства (прежняя — %s)", CONST_PREV)
                if callable(getattr(h, "push", None)):
                    try:
                        h.push("Конституция изменена на другом устройстве",
                               f"Принципы помощника пришли синхронизацией. Прежние сохранены: «{CONST_PREV}». "
                               "Если меняли не вы — верните их в «Душе» и перевыпустите ключ Dewiar в кабинете.")
                    except Exception:  # noqa: BLE001
                        pass
        elif kind == "mind" and iid == "radar":
            try:
                from engine_insight import radar as _radar
                moved = _radar(h).setup_apply(d)
            except Exception as e:  # noqa: BLE001
                log.warning("Радар с другого компьютера: %s", e)
                moved = False
            if moved:
                log.info("🔄 Радар: источники и задача — с другого компьютера")
        elif kind == "mind" and iid == "insights":
            cur = h.diary.data.get("insights") or {}
            if d.get("lines") and str(d.get("day", "")) > str(cur.get("day", "")):
                h.diary.data["insights"] = {"day": d.get("day"), "title": d.get("title", ""), "lines": list(d.get("lines") or [])}
                h.diary._save()
        elif kind == "diary":
            try:
                dt.date.fromisoformat(iid)
            except ValueError:
                return False
            p = h.workspace.ensure() / "Дневник" / f"{iid}.md"
            text = _mind_text(d, DIARY_MAX)
            if text is None:
                return False
            if text.strip() and (not p.exists() or p.read_text(encoding="utf-8").strip() != text.strip()):
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
        elif kind == "dayturn":
            if not deleted and self._q_seen(iid, add=True):
                log.info("🔄 Разговор с телефона %s уже в дневнике (пришёл другим путём) — пропускаю", iid)
            elif not deleted:
                when = None
                try:
                    when = dt.datetime.fromtimestamp(int(d.get("ts") or 0) / 1000)
                except (ValueError, OSError, OverflowError):
                    pass
                h.diary.log.add(str(d.get("you") or ""), str(d.get("bot") or ""), who=str(d.get("who") or ""), via="телефон", when=when)
        elif kind == "taskreq":
            # Два компьютера взялись бы за одну задачу оба: сначала занимаем её в облаке (taken_by, с prev — облако
            # отклонит, если занял другой), и только занявший берётся — _claim_tasks после обмена.
            if deleted:
                return None
            if d.get("taken_by") and d.get("taken_by") != self.state.get("device"):
                return False
            if d.get("to") and d.get("to") != self.state.get("device") and not self.HOME:   # задача другому компьютеру («на рабочем…», 0.56)
                return False                       # (по Wi-Fi её берём — HomeSync перешлёт её тому через облако)
            if str(d.get("goal") or d.get("title") or "").strip() and not d.get("taken_by"):
                self._claims[iid] = (dict(d), int(it_updated or 0))      # взятую уже по Wi-Fi тоже занимаем (другому не взять), но не начинаем
        elif kind == "task" and isinstance(d, dict) and d.get("want") in ("delete", "stop", "answer"):
            self._task_want(iid, d)
            return False
        elif kind == "task" or (kind == "mind" and iid.startswith("jobs")):
            return False                                   # ход задач и дела по расписанию другого компьютера — для телефона
        elif kind == "done":
            dn = getattr(h, "done", None)
            if dn is None:
                return False
            if deleted:
                dn.delete(iid)
            else:
                dn.upsert(iid, d)
            emit = getattr(h, "emit", None)
            if emit is not None:
                try:
                    emit("done", **dn.public())
                except Exception:  # noqa: BLE001
                    log.debug("дела: emit", exc_info=True)
        return None

    def _q_seen(self, iid, add=False):
        """Разговор (dayturn) и задача (taskreq) с телефона, которые этот компьютер уже взял — облачным обменом или по Wi-Fi
        (рецензия 04.11: ответ облака потерялся, телефон отдал то же по Wi-Fi — разговор дважды в дневнике, задача дважды).
        Набор общий у облачной и домашней синхронизации (sibling); add — отметить. -> было ли уже."""
        seen = self.state.setdefault("qseen", {})
        sib = getattr(self, "sibling", None)
        hit = iid in seen or (sib is not None and iid in (sib.state.get("qseen") or {}))
        if add and not hit:
            seen[iid] = int(time.time())
            if len(seen) > 3000:                          # месяц разговоров с запасом; старые id телефон второй раз не пришлёт
                for k in sorted(seen, key=seen.get)[:len(seen) - 2500]:
                    seen.pop(k, None)
        return hit

    def _apply_note(self, sid, d, deleted, upd=None):
        """Удаление — в корзину Dewiar (workspace.remove). Новая заметка получает свободное имя по заголовку в своей
        папке; известная перезаписывается на месте — смена заголовка или папки на другом устройстве файл не переносит.
        Имена из облака чистит _clean_name, «..» отбрасывается: выйти из «Заметок» нельзя."""
        al = self._note_alias(sid, d, deleted)
        if al is not None:                                 # второе имя заметки: правка — в тот же файл
            self.state.setdefault("alias", {})[sid] = al
            arel = self.state["map"].get(al)
            ah = self.state.setdefault("alias_h", {})
            if deleted:
                # удалили по второму имени (там, где оно главное): файл после склейки здесь не меняли — удаляем и его,
                # наше удаление уйдёт под нашим id; меняли — оставляем (правка дороже удаления)
                if arel and ah.get(sid) and self._file_h(arel) == ah.get(sid):
                    log.info("🔄 Заметка %s удалена на другом устройстве (второе имя %s) — удаляю", arel, sid)
                    self._apply_note(al, {}, True)
                    self.state["alias"].pop(sid, None)
                ah.pop(sid, None)
                return False
            log.info("🔄 Заметка %s — та же, что %s: склеиваю, а не кладу второй", sid, al)
            self._apply_note(al, d, False, upd)
            arel = self.state["map"].get(al)
            if arel:
                ah[sid] = self._file_h(arel)
            return False                                   # skip: удалением второе имя отсюда не уйдёт
        ws = self.host.workspace
        root = self._notes_root()
        rel = self.state["map"].get(sid)
        if not rel and (rel := self._sib_rel(sid)):        # эту заметку уже положила соседняя синхронизация — тот же файл
            self.state["map"][sid] = rel
        if deleted:
            if rel and (root / rel).exists():
                from workspace import _locked
                if _locked(root / rel):                 # заметка с замком: удаление с другого устройства не принимаем —
                    os.utime(root / rel, None)          # она новее удаления и вернётся туда со следующей отправкой
                    return False
                ws.remove(f"{NOTES}/{rel}")
            self.state["map"].pop(sid, None)
            self._pad_event(rel, True)
            return
        if not rel:
            from workspace import _clean_name
            folder = "/".join(_clean_name(x) for x in str(d.get("folder") or "").split("/") if x.strip() and x not in (".", ".."))
            base = _clean_name(d.get("title") or "Заметка") or "Заметка"
            rel = (folder + "/" if folder else "") + base + ".md"
            n = 2
            taken = set(self.state["map"].values())
            while (root / rel).exists() or rel in taken:
                rel = (folder + "/" if folder else "") + f"{base} ({n}).md"
                n += 1
            self.state["map"][sid] = rel
        else:
            if self._note_conflict(sid, rel, d, upd) == "mine":   # до переноса в другую папку: отпечаток — с прежней папкой
                return None                                # здешняя правка позже — она остаётся, пришедшая — копией рядом
            rel = self._move_to_folder(sid, rel, d, root)
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        text = str(d.get("text") or "")
        pad = rel.startswith(PAD_DIR + "/") and rel.count("/") == 1
        from workspace import FRONT_RX
        fm = FRONT_RX.match(text)                         # шапка «---» (Obsidian, Keep) — первой, заголовок — после неё
        front, rest = (text[:fm.end()], text[fm.end():]) if fm and fm.group(2).strip() else ("", text)
        if not rest.lstrip().startswith("#") and not pad:  # заметка с телефона: заголовок — как у заметок компьютера
            text = front + ("\n" if front else "") + f"# {d.get('title') or p.stem}\n\n{rest.lstrip(chr(10))}\n"   # (вкладки блокнота — как есть)
        p.write_text(text, encoding="utf-8")
        try:                                              # время файла — время правки на том устройстве, а не «сейчас»:
            u = int(upd or 0)                             # иначе мост («Дома по Wi-Fi») понесёт старую копию дальше как
            if 0 < u <= SB._now_ms():                        # свежую, и она перебьёт более позднюю правку (рецензия 04.11, S4)
                os.utime(p, ns=(u * 1_000_000, u * 1_000_000))
        except (OSError, ValueError, OverflowError):
            pass
        self._pad_event(rel, False)

    COPY_RX = re.compile(r"^(?P<base>.+?) \((?:копия с [^)]*|правка с [^)]*|конфликт с [^)]*)\)(?: \d+)?$")

    def _copies_tidy(self):
        """Владелец 17.11: «замучился с вкладками: правлю на работе, а дома вместо поправленной — старая и поправленная
        по отдельности; удаляю — опять». До 1.0.26 запертая заметка (замок 05.11) не принимала правку со своих же
        устройств и клала её рядом копией «(копия с …)» — теперь правка со своих устройств обычная (новее побеждает), а
        копии, которые совпадают со своей заметкой слово в слово (без замка и заголовка), убираются здесь — удаление
        уходит обычным обменом. Копии с другим текстом не трогаем: в них может быть нужное. -> сколько убрано."""
        from workspace import note_front
        root = self._notes_root()
        if not root.is_dir():
            return 0

        def body(f, title):
            try:
                t = note_front(f.read_text(encoding="utf-8"))[1]
            except (OSError, UnicodeDecodeError):
                return None
            t = t.replace("\r\n", "\n").strip()
            first = t.split("\n", 1)[0]
            if first.startswith("# ") and first[2:].strip().startswith(title):
                t = t[len(first):].strip()
            return re.sub(r"\s+", " ", t)

        gone = 0
        for f in list(root.rglob("*(*).md")):
            m = self.COPY_RX.match(f.stem)
            orig = f.with_name(m.group("base") + ".md") if m else None
            if orig is None or not orig.is_file() or not f.is_file():
                continue
            a, b = body(f, m.group("base")), body(orig, m.group("base"))
            if a is not None and a == b:
                try:
                    f.unlink()
                except OSError:
                    continue
                gone += 1
                log.info("🧹 Копия «%s» совпадает с «%s» — убрана", f.stem, orig.stem)
                rel = f.relative_to(root).as_posix()
                if rel.startswith(PAD_DIR + "/") and rel.count("/") == 1:
                    self._pad_event(rel, True)
        return gone

    def _file_h(self, rel):
        try:
            return hashlib.sha1((self._notes_root() / rel).read_bytes()).hexdigest()
        except OSError:
            return None

    def _note_conflict(self, sid, rel, d, upd=None):
        """Заметку правили и здесь (после последнего обмена — отпечаток файла не тот, что в idx), и на другом устройстве, —
        ни одна правка не теряется (рецензия 04.11: две правки одной заметки на двух компьютерах — одна пропадала молча;
        часы одного отстают — пропадала более поздняя). Здешняя позже пришедшей — остаётся (и уходит другим следующим
        обменом), а пришедшая ложится рядом копией «(конфликт с „Устройство“, время)»; раньше — наоборот: рядом копией
        здешняя. -> "mine" (здешняя остаётся, пришедшую не писать) или None."""
        p = self._notes_root() / rel
        base = (self.state.get("idx", {}).get("note:" + sid) or {}).get("h")
        if not isinstance(base, str) or not p.is_file():
            return
        try:
            cur = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        title = str(d.get("title") or p.stem)
        mine = {_note_norm(p.stem, cur), _note_norm(title, cur)}
        if mine & {_note_norm(title, d.get("text") or ""), _note_norm(p.stem, d.get("text") or "")}:
            return                                         # та же правка (с «# Названием» или без, под новым названием) — не конфликт
        folder = p.parent.relative_to(self._notes_root()).as_posix()
        dl = {"title": p.stem, "text": cur, "folder": "" if folder == "." else folder}
        sib = getattr(self, "sibling", None)
        aka = next((k for k, v in ((sib.state.get("map") or {}) if sib is not None else {}).items() if v == rel and k != sid), None)
        if base in (_h(dl), _h(dict(dl, aka=aka)) if aka else None):
            return                                         # здесь с прошлого обмена не правили
        who = self._dev_name(getattr(self, "_cur_dev", "")) or "другим устройством"
        alt = p.with_name(f"{p.stem} (конфликт с «{who}», {dt.datetime.now():%d.%m %H-%M}).md")
        n = 2
        while alt.exists():
            alt = p.with_name(f"{p.stem} (конфликт с «{who}», {dt.datetime.now():%d.%m %H-%M}) {n}.md")
            n += 1
        try:
            mine_later = p.stat().st_mtime_ns // 1_000_000 > int(upd or 0) > 0
        except OSError:
            mine_later = False
        if mine_later:
            t = str(d.get("text") or "")
            alt.write_text(t if t.lstrip().startswith("#") else f"# {title}\n\n{t.lstrip(chr(10))}\n", encoding="utf-8")
            self.__dict__.setdefault("_note_resend", set()).add("note:" + sid)
            log.info("🔄 Заметку «%s» правили и здесь (позже), и на «%s» — та правка рядом: %s", p.stem, who, alt.name)
            return "mine"
        alt.write_text(cur, encoding="utf-8")
        log.info("🔄 Заметку «%s» правили и здесь, и на «%s» — здешняя версия рядом: %s", p.stem, who, alt.name)
        return None

    def _note_change(self, key, ek, idx):
        """Запись обмена для заметки как она сейчас лежит здесь (с prev — версией, которую видели). -> dict или None."""
        sid = key.split(":", 1)[1]
        rel = self.state["map"].get(sid)
        p = self._notes_root() / rel if rel else None
        try:
            text, st = p.read_text(encoding="utf-8"), p.stat()
        except (OSError, UnicodeDecodeError, TypeError):
            return None
        folder = p.parent.relative_to(self._notes_root()).as_posix()
        data = {"title": p.stem, "text": text, "folder": "" if folder == "." else folder}
        h = _h(data)
        if ek is not None and self._sealable("note", sid, data):
            data = SB._seal(ek, data)
        c = {"kind": "note", "id": sid, "data": data, "updated": min(SB._now_ms(), st.st_mtime_ns // 1_000_000), "_h": h}
        if (idx.get(key) or {}).get("u") is not None:
            c["prev"] = idx[key]["u"]
        return c

    def _dev_name(self, dev):
        for x in (self.status.get("all") or []):
            if x.get("id") == dev and x.get("name"):
                return str(x["name"])[:40]
        return ""

    def _move_to_folder(self, sid, rel, d, root):
        """Папку заметки сменили на телефоне (№195, 23.10: папки в заметках) — переносим файл в эту папку, имя то же.
        Только в непустую папку: старые телефоны присылают folder "" у любой заметки, и всё уехало бы в корень. -> rel."""
        from workspace import _clean_name
        want = "/".join(_clean_name(x) for x in str(d.get("folder") or "").split("/") if x.strip() and x not in (".", ".."))
        cur = str(Path(rel).parent.as_posix())
        cur = "" if cur == "." else cur
        if not want or want == cur:
            return rel
        src = root / rel
        base = Path(rel).stem
        new = f"{want}/{base}.md"
        n = 2
        taken = set(self.state["map"].values())
        while (root / new).exists() or new in taken:
            new = f"{want}/{base} ({n}).md"
            n += 1
        try:
            (root / new).parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                os.replace(src, root / new)
        except OSError as e:
            log.info("Заметка не перенесена в папку «%s»: %s", want, e)
            return rel
        self.state["map"][sid] = new
        log.info("📁 Заметка перенесена с телефона: %s → %s", rel, new)
        self._pad_event(rel, True)                     # вкладку блокнота унесли в другую папку — блокнот её уберёт
        return new

    def _pad_event(self, rel, deleted):
        """Вкладку блокнота поправили на другом устройстве — открытый блокнот перечитает её (ui/pad.html)."""
        if rel and str(rel).startswith(PAD_DIR + "/") and str(rel).count("/") == 1:
            try:
                self.host.emit("pad_changed", name=Path(rel).stem, deleted=bool(deleted))
            except Exception:  # noqa: BLE001
                pass

    def _apply_fact(self, fid, fact, deleted):
        """Строка «Обо мне»: новую дописываем, если такой (по id) ещё нет. Удаление приходит без текста — ищем строку
        по её id (отпечатку текста, см. _fact_id)."""
        fact = re.sub(r"\s+", " ", fact.strip())
        ws = self.host.workspace
        if not deleted:
            if not fact:
                return
            if _fact_id(fact) not in {_fact_id(x) for x in self._facts()}:
                ws.remember(fact, who="")                 # общая «Обо мне», а не своя память того, кто сейчас отвечает
            return
        p = ws.ensure() / MEMORY
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        keep = [ln for ln in lines if not ((m := _FACT.match(ln.strip())) and _fact_id(m.group(1)) == fid)]
        if len(keep) != len(lines):
            p.write_text("\n".join(keep) + "\n", encoding="utf-8")
            if hasattr(ws, "mem_changed"):
                ws.mem_changed()                          # удалили на телефоне — снимок справки в разговоре прочь (0.87)
