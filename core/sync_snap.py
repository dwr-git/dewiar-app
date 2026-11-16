"""Синхронизация — снимок этого устройства (часть Sync, чистое ядро 1.0.16): заметки и их id (в том числе вторые id
до 0.83), напоминания, деньги, память, душа и дневник, своя память персонажей."""
import datetime as dt
import hashlib
import re
from sync_base import (
    _base_title, DIARY_DAYS, EXTRA_KINDS, _FACT, _fact_id, _h, log, MEMORY, NOTE_MAX, _note_norm, NOTES, _pmem_id,
    TASKS_SHOWN)
import sync_base as SB  # подменяемые в проверках имена — через основу


class SnapMixin:
    # ---------- снимок данных этого устройства: ключ → (data, hash) ----------

    def _notes_root(self):
        return self.host.workspace.ensure() / NOTES

    def _note_paths(self):
        """Путь заметки -> id: свой map, а для путей, которых в нём нет, — map соседней синхронизации этого компьютера
        (облачной или «Дома по Wi-Fi»). Телефон с входом и Wi-Fi шлёт одну заметку обоими путями (04.11) — без общего
        id она легла бы здесь двумя файлами («… (2)»), а с компьютера ушла бы под другим id."""
        by_path = {v: k for k, v in self.state["map"].items()}
        sib = getattr(self, "sibling", None)
        if sib is not None:
            for k, v in list((sib.state.get("map") or {}).items()):
                by_path.setdefault(v, k)
        return by_path

    def _sib_rel(self, sid):
        sib = getattr(self, "sibling", None)
        rel = (sib.state.get("map") or {}).get(sid) if sib is not None else None
        return rel if rel and rel not in self.state["map"].values() else None

    def _note_alias(self, sid, d, deleted):
        """Та же заметка под вторым id (рецензия 04.11: до 0.83 мост давал заметке с телефона в облаке id по пути — f…, а на
        узле Wi-Fi у неё оставался id телефона — n…; после входа на телефоне «Покупки» ложились вторым и третьим файлом).
        -> id, под которым этот обмен знает её файл, или None. Второе имя — если соседняя синхронизация этого компьютера
        положила sid в тот же файл, или если это новая заметка, а на её месте уже лежит файл с тем же текстом."""
        m = self.state["map"]
        if sid in m:
            return None
        al = (self.state.get("alias") or {}).get(sid)
        if al and al in m:
            return al
        sib = getattr(self, "sibling", None)
        srel = (sib.state.get("map") or {}).get(sid) if sib is not None else None
        if srel:
            return next((k for k, v in m.items() if v == srel), None)
        if deleted or not isinstance(d, dict):
            return None
        from workspace import _clean_name
        folder = "/".join(_clean_name(x) for x in str(d.get("folder") or "").split("/") if x.strip() and x not in (".", ".."))
        base = _clean_name(_base_title(d.get("title") or "Заметка")) or "Заметка"
        want = _note_norm(d.get("title") or "", d.get("text") or "")
        rel = None
        for n in range(1, 31):                            # «Список.md», «Список (2).md»… — компьютер мог занять имя раньше
            cand = (folder + "/" if folder else "") + (base if n == 1 else f"{base} ({n})") + ".md"
            p = self._notes_root() / cand
            if not p.is_file():
                if n > 2:
                    break
                continue
            try:
                if _note_norm(p.stem, p.read_text(encoding="utf-8")) == want:
                    rel = cand
                    break
            except (OSError, UnicodeDecodeError):
                continue
        if rel is None:
            return None
        own = next((k for k, v in m.items() if v == rel), None)
        if own is None:                                   # файл ещё не в обмене — его id тот же, что даст снимок
            own = self._note_paths().get(rel) or "f" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
            m[own] = rel
            if own == sid:
                return None
        return own

    def note_sid(self, rel):
        """Путь заметки в папке ассистента («Заметки/…») -> её id синхронизации (тот же, что в snapshot: из map или
        отпечаток пути) — им её знает телефон."""
        sub = str(rel)[len(NOTES) + 1:] if str(rel).startswith(NOTES + "/") else str(rel)
        by_path = self._note_paths()
        return by_path.get(sub) or "f" + hashlib.sha1(sub.encode("utf-8")).hexdigest()[:12]

    def snapshot(self):
        """-> {«вид:id»: данные}. Для заметок и хранилища ещё «ключ#t» — время правки файла (мс) и, если файл не менялся
        с прошлого раза, данные None и «ключ#h» — отпечаток из кэша (сам текст читаем, только когда его надо отправить).
        Попутно обновляет map и кэш mt. Чего нет в снимке — уйдёт удалением, см. шапку."""
        out = {}
        root = self._notes_root()
        by_path = self._note_paths()
        sib = getattr(self, "sibling", None)
        sib_by = {v: k for k, v in list(((sib.state.get("map") or {}) if sib is not None else {}).items())}
        for r in list(self.host.reminders.items):
            if r.get("kind") == "job":
                continue
            try:
                at = int(dt.datetime.fromisoformat(r["at"]).timestamp() * 1000)
            except (KeyError, ValueError):
                continue
            d = {"text": r.get("text", ""), "at": at, "kind": r.get("kind") or "reminder",
                 "repeat": r.get("repeat") or None, "paused": bool(r.get("paused"))}
            nid = r.get("note_id") or ""
            if r.get("note") and str(r["note"]).startswith(NOTES + "/"):     # заметка с картинками — её id, как у самой заметки
                rel = str(r["note"])[len(NOTES) + 1:]
                nid = by_path.get(rel) or "f" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
            if nid:
                d["note"] = nid
            out["reminder:" + r["id"]] = d
        for m in list(self.host.money.items):
            d = {k: m.get(k) for k in ("date", "kind", "amount", "currency", "category", "note")}
            out["money:" + m["id"]] = d
        cache = self.state.setdefault("mt", {})
        seen_paths = set()
        if root.is_dir():
            for p in sorted(root.rglob("*.md"))[:3000]:
                rel = p.relative_to(root).as_posix()
                if any(part.startswith(".") for part in p.relative_to(root).parts):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size > NOTE_MAX:
                    continue
                sid = by_path.get(rel) or "f" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
                self.state["map"][sid] = rel
                seen_paths.add(rel)
                key = "note:" + sid
                out[key + "#t"] = st.st_mtime_ns // 1_000_000     # когда правили на самом деле: старая копия не перебьёт новую
                sig = f"{st.st_mtime_ns}:{st.st_size}"
                c = cache.get(rel)
                # другой обмен этого компьютера знает файл под другим id (мост до 0.83) — подсказка телефону: aka, та же заметка
                aka = sib_by.get(rel) if sib_by.get(rel) not in (None, sid) else None
                if aka:
                    cache.pop(rel, None)
                    c = None
                if c and c[0] == sig:                     # файл не менялся — не читаем его каждую минуту
                    out[key] = None
                    out[key + "#h"] = c[1]
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                folder = p.parent.relative_to(root).as_posix()
                d = {"title": p.stem, "text": text, "folder": "" if folder == "." else folder}
                if aka:
                    d["aka"] = aka
                out[key] = d
                if not aka:
                    cache[rel] = [sig, _h(d)]
        for rel in [r for r in cache if r not in seen_paths]:
            cache.pop(rel, None)
        # id пропавшей заметки забываем, только если синхронизация о ней не знает: известному id путь ещё понадобится
        for sid in [s for s, r in self.state["map"].items() if r not in seen_paths and "note:" + s not in self.state["idx"]]:
            self.state["map"].pop(sid, None)
        for fact in self._facts():
            out["memory:" + _fact_id(fact)] = {"text": fact}
        if set(EXTRA_KINDS) & set(self.state.get("kinds") or ()):     # только виды, которые знает сервер
            self.state["_extra_failed"] = False
            try:
                self._snap_extra(out)
            except Exception as e:  # noqa: BLE001 — душа, дневник и задачи не должны ломать напоминания и заметки
                self.state["_extra_failed"] = True
                log.warning("Синхронизация: душа/дневник/задачи не собрались: %s", e)
        return out

    def _snap_extra(self, out):
        h = self.host
        ok = set(self.state.get("kinds") or ())
        self.state["_doc_failed"] = False
        if "doc" in ok and self._docs_ok():
            try:
                self._snap_docs(out)
            except Exception as e:  # noqa: BLE001 — файлы не должны мешать остальному обмену
                self.state["_doc_failed"] = True
                log.warning("Синхронизация: «Мои файлы» не собрались: %s", e)
        if "pmemory" in ok:                         # своя память персонажей (0.56): факты по файлам «Память/Персонажи» и кто со своей
            for name, facts in self._pfacts().items():
                for fact in facts:
                    out["pmemory:" + _pmem_id(name, fact)] = {"who": name, "text": fact}
            own = h.s.get("persona_memory", "own") if getattr(h, "s", None) is not None else None
            if own is not None and int(h.s.get("persona_memory", "at") or 0) > 0:     # меняли хоть раз — иначе не перебивать чужое
                out["pmemory:own"] = {"names": list(own), "at": int(h.s.get("persona_memory", "at") or 0)}
        pers = getattr(h, "personas", None)
        if pers is not None and "persona" in ok and hasattr(pers, "own_ids"):
            # свои персонажи (19.10: создали на телефоне — пусть будет и на компьютере, и наоборот); облик — до 250 КБ
            for p in pers.all():
                if p.get("id") not in pers.own_ids():
                    continue
                av = pers.avatar_data_url(p) if p.get("avatar") else ""
                out["persona:" + p["id"]] = {"name": p.get("name", ""), "gender": p.get("gender") or "female", "role": p.get("role") or "",
                                             "about": p.get("about") or p.get("character") or "", "color": p.get("color") or "",
                                             "avatar": av if len(av) < 250000 else ""}
        soul = getattr(h, "soul", None)
        if soul is not None and "soul" in ok:
            for name in soul.souls():
                text = soul.soul(name)
                if text.strip():
                    out["soul:" + name] = {"text": text}
        if soul is not None and "mind" in ok:
            out["mind:constitution"] = {"text": soul.constitution()}
        if "mind" in ok:                       # дела по расписанию (утренняя сводка, итоги) — телефону только показать: делает компьютер
            from when import describe_repeat
            jobs = []
            for r in list(h.reminders.items):
                if r.get("kind") != "job":
                    continue
                try:
                    at = int(dt.datetime.fromisoformat(r["at"]).timestamp() * 1000)
                except (KeyError, ValueError):
                    continue
                try:
                    rep = describe_repeat(r.get("repeat")) if r.get("repeat") else ""
                except Exception:  # noqa: BLE001
                    rep = ""
                try:                           # имя для людей (№557): на телефоне — «Дача: заморозки и полив», а не поручение модели
                    title = str(h.job_label(r))[:80] if hasattr(h, "job_label") else ""
                except Exception:  # noqa: BLE001
                    title = ""
                jobs.append({"text": str(r.get("text", ""))[:200], "title": title, "at": at, "repeat": rep, "paused": bool(r.get("paused"))})
            # своя запись у каждого компьютера (jobs-<устройство>): два компьютера не перетирают друг друга по кругу;
            # без дел — не шлём (а если раньше были — шлём пустой список, чтобы телефон их убрал)
            if jobs or self.state.get("jobs_sent"):
                out["mind:jobs-" + self.state["device"]] = {"items": sorted(jobs, key=lambda j: j["at"])[:30]}
            self.state["jobs_sent"] = bool(jobs)
        diary = getattr(h, "diary", None)
        if diary is not None and "mind" in ok and (diary.data.get("insights") or {}).get("lines"):
            ins = diary.data["insights"]
            out["mind:insights"] = {"day": ins.get("day", ""), "title": ins.get("title", ""), "lines": list(ins.get("lines") or [])}
        if "diary" in ok:
            d = h.workspace.ensure() / "Дневник"
            titles = (diary.data.get("titles") if diary is not None else None) or {}
            for p in sorted(d.glob("*.md"), reverse=True)[:DIARY_DAYS] if d.is_dir() else []:
                try:
                    dt.date.fromisoformat(p.stem)
                    text = p.read_text(encoding="utf-8")
                except (ValueError, OSError):
                    continue
                t = titles.get(p.stem) or {}
                out["diary:" + p.stem] = {"text": text[:NOTE_MAX], "title": t.get("title", ""), "mood": t.get("mood", "")}
        ob = getattr(h, "obsidian", None)
        if ob is not None and "vault" in ok and ob.sync_all():
            self._snap_vault(out, ob)
        pm = getattr(h, "payments", None)
        if pm is not None and "bill" in ok:
            with pm._lock:
                for b in pm.bills:
                    out["bill:" + b["id"]] = dict(b)
                for x in pm.pays:
                    out["pay:" + x["id"]] = dict(x)
        if pm is not None and "payfile" in ok:
            self._snap_payfiles(out, pm)
        if "safe" in ok:
            self._snap_safe(out)
        cl = getattr(h, "clients", None)
        if cl is not None and "client" in ok and self._clients_ok():
            for cid, c in cl.sync_items().items():
                out["client:" + cid] = c
                out["client:" + cid + "#t"] = int(float(c.get("updated") or 0) * 1000) or SB._now_ms()
        if "plugin" in ok and not self.HOME and getattr(h, "plugins", None) is not None:
            self._snap_plugins(out)
        dn = getattr(h, "done", None)
        if dn is not None and "done" in ok:            # сделанные дела (done.py) — как doneList() на телефоне
            with dn._lock:
                for x in dn.items:
                    out["done:" + x["id"]] = {"title": x["title"], "at": int(x["at"]), "src": x.get("src") or "", "rid": x.get("rid") or ""}
        tasks = getattr(h, "tasks", None)
        if tasks is not None and "task" in ok:
            for t in sorted(tasks.tasks.values(), key=lambda x: str(x.data.get("updated", "")), reverse=True)[:TASKS_SHOWN]:
                dd = t.data
                out["task:" + t.id] = {"title": dd.get("title", ""), "status": dd.get("status", ""), "goal": str(dd.get("goal", ""))[:400],
                                       "result": str(dd.get("result", ""))[:1200], "error": str(dd.get("error", ""))[:300],
                                       "question": str(dd.get("question", ""))[:400], "activity": str(dd.get("activity", ""))[:200],
                                       "updated": dd.get("updated", ""), "created": dd.get("created", ""),
                                       "outputs": [str(o.get("path", ""))[-80:] for o in (dd.get("outputs") or [])][:8],
                                       "files": dd.get("files") or []}

    def _facts(self):
        try:
            text = (self.host.workspace.ensure() / MEMORY).read_text(encoding="utf-8")
        except OSError:
            return []
        out = []
        for line in text.splitlines():
            m = _FACT.match(line.strip())
            if m:
                out.append(m.group(1).strip())
        return out

    def _pfacts(self):
        """Своя память персонажей: {имя: [факты]} — по файлам «Память/Персонажи/<имя>.md»."""
        out = {}
        try:
            folder = self.host.workspace.ensure() / "Память" / "Персонажи"
            files = sorted(folder.glob("*.md")) if folder.is_dir() else []
        except OSError:
            return out
        for f in files[:40]:
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            facts = [m.group(1).strip() for ln in lines if (m := _FACT.match(ln.strip()))]
            if facts:
                out[f.stem] = facts[-300:]
        return out

    def _apply_pmemory(self, iid, d, deleted):
        h = self.host
        if iid == "own":                                  # у кого своя память — с другого устройства, если новее
            if deleted or not isinstance(d.get("names"), list):
                return None
            if int(d.get("at") or 0) > int(h.s.get("persona_memory", "at") or 0):
                h.s.update({"persona_memory": {"own": [str(x)[:40] for x in d["names"] if x][:40], "at": int(d.get("at") or 0)}})
                try:
                    h.emit("settings", settings=h.s.snapshot())
                except Exception:  # noqa: BLE001
                    pass
            return None
        ws = h.workspace
        if not deleted:
            who, fact = str(d.get("who") or "").strip()[:40], re.sub(r"\s+", " ", str(d.get("text") or "").strip())
            if who and fact and _fact_id(fact) not in {_fact_id(x) for x in self._pfacts().get(who, [])}:
                ws.remember(fact, who=who)
            return None
        pre = iid.split("-", 1)[0]                        # удаление — без текста: файл по отпечатку имени, строку по id факта
        fid = iid.split("-", 1)[1] if "-" in iid else ""
        for name in self._pfacts():
            if _pmem_id(name, "").split("-", 1)[0] != pre:
                continue
            from workspace import persona_mem_rel
            p = ws.ensure() / persona_mem_rel(name)
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            keep = [ln for ln in lines if not ((m := _FACT.match(ln.strip())) and _fact_id(m.group(1)) == fid)]
            if len(keep) != len(lines):
                p.write_text("\n".join(keep) + "\n", encoding="utf-8")
        return None

    def _hash_of(self, snap, key):
        if key + "#h" in snap:
            return snap[key + "#h"]
        return _h(snap[key])
