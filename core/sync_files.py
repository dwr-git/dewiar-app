"""Синхронизация — файлы (часть Sync, чистое ядро 1.0.16): хранилище Obsidian, «Клиенты», «Мои файлы» на телефоне
(текст — только со сквозным шифрованием)."""
import base64
import datetime as dt
import hashlib
import json
import shutil
import time
from pathlib import Path
from sync_base import DOC_PART, DOC_TOTAL, _h, log, VAULT_FILES, VAULT_MAX


class FilesMixin:
    # ---------- всё хранилище Obsidian (по желанию): одинаковое на всех компьютерах ----------

    def _vault_files(self, ob):
        """-> (корень хранилища или None, {путь в хранилище: Path}) — тексты .md, кроме папки ассистента (она ходит
        своими видами записей), служебных и скрытых папок (SKIP_DIRS из obsidian.py) и корзины; не больше VAULT_FILES."""
        v = ob.vault()
        mir = ob.mirror()
        if v is None:
            return None, {}
        out = {}
        from obsidian import SKIP_DIRS
        for p in v.rglob("*.md"):
            try:
                rel = p.relative_to(v)
            except ValueError:
                continue
            parts = rel.parts
            if any(x in SKIP_DIRS or x.startswith(".") for x in parts[:-1]) or (mir is not None and parts[0] == mir.name):
                continue
            out[rel.as_posix()] = p
            if len(out) >= VAULT_FILES:
                break
        return v, out

    def _snap_vault(self, out, ob):
        v, files = self._vault_files(ob)
        if v is None:
            return
        vmap = self.state.setdefault("vmap", {})              # id → путь (удаление приходит без пути)
        cache = self.state.setdefault("vt", {})
        for rel, p in files.items():
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size > VAULT_MAX:
                continue
            vid = "v" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:16]     # id из пути: одинаков на всех компьютерах
            vmap[vid] = rel
            key = "vault:" + vid
            out[key + "#t"] = st.st_mtime_ns // 1_000_000
            sig = f"{st.st_mtime_ns}:{st.st_size}"
            c = cache.get(rel)
            if c and c[0] == sig:
                out[key] = None
                out[key + "#h"] = c[1]
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            d = {"path": rel, "text": text}
            out[key] = d
            cache[rel] = [sig, _h(d)]
        for rel in [r for r in cache if r not in files]:
            cache.pop(rel, None)

    def _clients_ok(self):
        """«Клиенты» между устройствами (0.89, отчёты 657 и 658: планшет без бизнес-инструментов) — это чужие телефоны и
        почты, поэтому только со сквозным шифрованием (облако их не прочтёт) или по домашнему Wi-Fi (облака нет вовсе)."""
        return bool(self.HOME) or self.e2e_key() is not None

    def _apply_client(self, iid, d, deleted, it):
        cl = getattr(self.host, "clients", None)
        if cl is None:
            return False
        if deleted:
            return cl.remove_remote(iid) or None
        if not self._clients_ok():
            return False                          # шифрование здесь выключено — карточки не принимаем (и не шлём)
        cl.merge_remote(iid, d)

    # ---------- «Мои файлы» на телефоне (doc) ----------

    def _docs_ok(self):
        """Текст файлов — личное: только со сквозным шифрованием (облако его не прочтёт) или по домашнему Wi-Fi."""
        return getattr(self.host, "knowledge", None) is not None and (bool(self.HOME) or self.e2e_key() is not None)

    @staticmethod
    def _doc_parts(chunks):
        """Отрывки файла -> куски не длиннее DOC_PART знаков (отрывок не режется)."""
        parts, cur, n = [], [], 0
        for c in chunks:
            if cur and n + len(c) > DOC_PART:
                parts.append(cur)
                cur, n = [], 0
            cur.append(c[:DOC_PART])
            n += len(cur[-1])
        if cur:
            parts.append(cur)
        return parts

    def _snap_docs(self, out):
        """Файлы -> записи doc:<id>.<номер> (данные None + отпечаток; текст собираем, только когда отправлять — _doc_read)."""
        dm = {}
        for f in self.host.knowledge.shared(DOC_TOTAL):
            fid = hashlib.sha1(f["key"].encode("utf-8")).hexdigest()[:12]
            n = len(self._doc_parts(f["chunks"]))
            sig = hashlib.sha1(("\n".join(f["chunks"]) + f["path"]).encode("utf-8")).hexdigest()[:16]
            dm[fid] = {"key": f["key"], "sig": sig, "n": n, "name": f["name"], "path": f["path"], "mtime": f["mtime"], "size": f["size"]}
            for i in range(n):
                out[f"doc:{fid}.{i}"] = None
                out[f"doc:{fid}.{i}#h"] = f"{sig}:{i}:{n}"
        self.state["dmap"] = dm

    def _doc_read(self, iid):
        import zlib
        fid, _, i = iid.partition(".")
        m = (self.state.get("dmap") or {}).get(fid)
        kn = getattr(self.host, "knowledge", None)
        e = kn.index.get(m["key"]) if m and kn is not None else None
        if not m or not e or not i.isdigit():
            return None
        parts = self._doc_parts(e.get("chunks") or [])
        if len(parts) != m["n"] or int(i) >= len(parts):
            return None                                   # файл успели перечитать — уйдёт следующим обменом
        z = base64.b64encode(zlib.compress(json.dumps(parts[int(i)], ensure_ascii=False).encode("utf-8"), 6)).decode("ascii")
        return {"f": fid, "name": m["name"], "path": m["path"], "mtime": m["mtime"], "size": m["size"], "i": int(i), "n": m["n"], "z": z}

    def doc_status(self):
        """Для «Моих файлов» в студии: сколько файлов видно с телефона и почему, если нисколько."""
        dm = self.state.get("dmap") or {}
        kinds = set(self.state.get("kinds") or ())
        return {"files": len(dm) if self._docs_ok() else 0, "e2e": self.e2e_key() is not None, "server": "doc" in kinds,
                "enabled": bool(self.status.get("enabled"))}

    def _vault_read(self, vid):
        ob = getattr(self.host, "obsidian", None)
        rel = self.state.get("vmap", {}).get(vid)
        v = ob.vault() if ob is not None else None
        if not rel or v is None:
            return None
        try:
            return {"path": rel, "text": (v / rel).read_text(encoding="utf-8")}
        except (OSError, UnicodeDecodeError):
            return None

    def _apply_vault(self, vid, d, deleted, it):
        """Чужая правка заметки хранилища. Удаление — в корзину Obsidian (.trash), не насовсем. Пришедшая версия
        ложится поверх здешней, но если здесь заметку правили (текст не совпадает с версией b, с которой облако было
        согласно) и это не первая встреча с ней либо здешний файл новее пришедшего, — здешний текст сохраняется рядом
        копией «(конфликт, устройство дата)». Так ничья правка не теряется молча (см. prev/lost в run_once)."""
        ob = getattr(self.host, "obsidian", None)
        v = ob.vault() if ob is not None else None
        if v is None or not ob.sync_all():
            return False
        rel = str(d.get("path") or self.state.get("vmap", {}).get(vid) or "")
        relp = Path(rel)
        # путь пришёл из облака: не даём выйти за пределы хранилища и писать в служебные папки и не-.md файлы
        if not rel or relp.is_absolute() or ".." in relp.parts or relp.suffix.lower() != ".md" or relp.parts[0] in (".obsidian", ".trash"):
            return False
        p = v / relp
        if deleted:
            if p.exists():
                dst = v / ".trash" / relp
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    dst = dst.with_name(f"{dst.stem} {int(time.time())}{dst.suffix}")
                shutil.move(str(p), str(dst))
            self.state.get("vt", {}).pop(rel, None)
            return None
        text = str(d.get("text") or "")
        self.state.setdefault("vmap", {})[vid] = rel
        if p.exists():
            try:
                cur = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                cur = None
            if cur == text:
                return None
            base = (self.state.get("idx", {}).get("vault:" + vid) or {}).get("b")
            local_edit = cur is not None and _h({"path": rel, "text": cur}) != base
            newer_here = p.stat().st_mtime * 1000 > int(it.get("updated") or 0)
            if cur is not None and local_edit and (base is not None or newer_here):
                alt = p.with_name(f"{p.stem} (конфликт, {self.host.device_name()} {dt.datetime.now():%d.%m %H-%M}){p.suffix}")
                alt.write_text(cur, encoding="utf-8")
                log.info("🔄 Хранилище: «%s» правили и здесь, и на другом устройстве — здешняя версия рядом: %s", rel, alt.name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return None
