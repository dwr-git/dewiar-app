"""Синхронизация — «Платежи» (часть Sync, чистое ядро 1.0.16): счета, оплаты и вложения кусками."""
import hashlib
import re
import shutil
from pathlib import Path
from sync_base import log, PF_CHUNK, PF_MAX


class PayMixin:
    # ---------- «Платежи»: счета, оплаты и вложения между компьютерами ----------

    def _pf_dir(self):
        return self.path.parent / "payparts"

    def _snap_payfiles(self, out, pm):
        """Вложения «Платежей» -> записи payfile:<id пути>.<номер куска> (данные None + отпечаток; читаем, только когда
        отправлять — _payfile_read). Отпечаток — по содержимому: кэш pf {путь: [размер:время, sha1, кусков]}."""
        root = Path(self.host.workspace.ensure())
        cache = self.state.setdefault("pf", {})
        pfmap = self.state.setdefault("pfmap", {})
        seen = set()
        for rel in pm.att_paths():
            p = root / rel
            try:
                st = p.stat()
            except OSError:
                continue
            if not p.is_file() or st.st_size > PF_MAX or st.st_size == 0:
                continue
            sig = f"{st.st_size}:{st.st_mtime_ns}"
            c = cache.get(rel)
            if not c or c[0] != sig:
                try:
                    c = [sig, hashlib.sha1(p.read_bytes()).hexdigest(), -(-st.st_size // PF_CHUNK)]
                except OSError:
                    continue
                cache[rel] = c
            fid = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
            pfmap[fid] = rel
            seen.add(rel)
            for i in range(c[2]):
                out[f"payfile:{fid}.{i}"] = None
                out[f"payfile:{fid}.{i}#h"] = f"{c[1]}:{i}:{c[2]}"
        for rel in [r for r in cache if r not in seen]:
            cache.pop(rel, None)

    def _payfile_read(self, iid):
        fid, _, i = iid.partition(".")
        rel = (self.state.get("pfmap") or {}).get(fid)
        c = (self.state.get("pf") or {}).get(rel or "")
        if not rel or not c or not i.isdigit():
            return None
        try:
            with open(Path(self.host.workspace.ensure()) / rel, "rb") as f:
                f.seek(int(i) * PF_CHUNK)
                part = f.read(PF_CHUNK)
        except OSError:
            return None
        import base64
        return {"path": rel, "i": int(i), "n": c[2], "sha": c[1], "b64": base64.b64encode(part).decode("ascii")}

    def _apply_pay(self, kind, iid, d, deleted):
        """Счёт, оплата или кусок вложения с другого компьютера. Вложение собирается, когда пришли все куски и сошёлся
        отпечаток; пишется только в «Платежи/Вложения/» (payments.att_ok)."""
        import base64
        from payments import att_ok
        h = self.host
        pm = getattr(h, "payments", None)
        if pm is None:
            return False
        if kind in ("bill", "pay"):
            if deleted:
                pm.sync_drop(kind, iid)
            elif pm.sync_put(kind, iid, d) is None:
                return False
            emit = getattr(h, "emit", None)
            if emit is not None:
                try:
                    emit("pay_saved", what="sync")
                except Exception:  # noqa: BLE001
                    log.debug("платежи: emit", exc_info=True)
            return None
        fid, _, i = iid.partition(".")
        if not re.fullmatch(r"[0-9a-f]{12}", fid) or not i.isdigit():
            return False
        root = Path(h.workspace.ensure())
        if deleted:
            rel = (self.state.get("pfmap") or {}).get(fid)
            if rel and att_ok(rel) and rel not in pm.att_paths():
                try:
                    (root / rel).unlink(missing_ok=True)
                except OSError:
                    pass
            shutil.rmtree(self._pf_dir() / fid, ignore_errors=True)
            return None
        rel, n, sha = str(d.get("path") or ""), d.get("n"), str(d.get("sha") or "")
        if not att_ok(rel) or hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12] != fid or not isinstance(n, int) \
                or not 0 <= int(i) < n <= -(-PF_MAX // PF_CHUNK) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            return False
        self.state.setdefault("pfmap", {})[fid] = rel
        dst = root / rel
        try:
            if dst.is_file() and hashlib.sha1(dst.read_bytes()).hexdigest() == sha:
                return None                                   # уже на месте
            part = base64.b64decode(str(d.get("b64") or ""), validate=True)
        except (OSError, ValueError):
            return False
        tmp = self._pf_dir() / fid
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / f"{sha}.{i}").write_bytes(part)
        parts = [tmp / f"{sha}.{k}" for k in range(n)]
        if all(x.is_file() for x in parts):
            blob = b"".join(x.read_bytes() for x in parts)
            if hashlib.sha1(blob).hexdigest() == sha:
                dst.parent.mkdir(parents=True, exist_ok=True)
                tmpf = dst.with_name(dst.name + ".part")
                tmpf.write_bytes(blob)
                tmpf.replace(dst)
                log.info("🔄 Платежи: вложение «%s» — с другого компьютера", dst.name)
            shutil.rmtree(tmp, ignore_errors=True)
        return None
