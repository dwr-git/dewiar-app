"""Синхронизация — «Сейф паролей» (часть Sync, чистое ядро 1.0.16): только своим устройствам и только зашифрованным."""
from sync_base import log
import sync_base as SB  # подменяемые в проверках имена — через основу


class SafeMixin:
    # ---------- «Сейф паролей» между своими устройствами (вид safe; core/vault.py — SafeKey и формат) ----------

    def _safe_on(self):
        """Ключ сейфа, которым сейчас синхронизировать ({"k", "meta"}), или None — сейф здесь не синхронизируется."""
        sk, vt = getattr(self.host, "safe_key", None), getattr(self.host, "vault", None)
        return sk.active() if sk is not None and vt is not None else None

    def _snap_safe(self, out):
        """Записи сейфа -> safe:<id> (данные None, отпечаток — HMAC ключом сейфа; шифруем, только когда отправлять —
        _safe_read) и safe:key — открытые параметры. Сейф не открылся — ничего и пометка _safe_failed (не удаления)."""
        self.state["_safe_failed"] = False
        cur = self._safe_on()
        if cur is None:
            return
        from vault import item_ms, safe_hash
        try:
            items = self.host.vault.sync_items()
        except Exception as e:  # noqa: BLE001 — CryptError: ключ компьютера сменился
            self.state["_safe_failed"] = True
            log.warning("Синхронизация: сейф не открылся — его записи сейчас не отправляю: %s", e)
            return
        meta, kid = cur["meta"], cur["meta"]["kid"]
        out["safe:key"] = dict(meta)
        out["safe:key#t"] = int(meta["at"])
        for x in items:
            key = "safe:" + str(x.get("id"))
            out[key] = None
            out[key + "#h"] = safe_hash(cur["k"], kid, x)
            out[key + "#t"] = item_ms(x) or SB._now_ms()

    def _safe_read(self, iid):
        cur = self._safe_on()
        vt = getattr(self.host, "vault", None)
        if cur is None or vt is None:
            return None
        from vault import safe_seal
        try:
            x = vt.get(iid)
        except Exception:  # noqa: BLE001
            return None
        return safe_seal(cur["k"], cur["meta"]["kid"], x) if x else None

    def _apply_safe(self, iid, d, deleted, it):
        """Запись сейфа с другого устройства. Параметры (safe:key) запоминаем всегда — так здесь узнают, что сейф уже
        синхронизируется (студия спросит мастер-пароль). Записи — только когда здесь есть ключ того же мастер-пароля;
        иначе skip (без удаления своего), а когда ключ появится — safe_refetch() заберёт историю заново.
        Правка здесь новее пришедшей — оставляем свою (False: она уйдёт в облако следующим обменом)."""
        from vault import item_ms, safe_open
        h = self.host
        sk, vt = getattr(h, "safe_key", None), getattr(h, "vault", None)
        if sk is None or vt is None:
            return False
        if iid == "key":
            if deleted or not isinstance(d, dict):
                return False
            if sk.note(d):
                cur = sk.get()
                if cur and cur["meta"]["kid"] != d.get("kid") and sk.active() is None:
                    log.info("🔐 Мастер-пароль сейфа сменили на другом устройстве — сейф здесь ждёт новый")
                    self._safe_event()
            return None
        cur = self._safe_on()
        if cur is None:
            return False
        if deleted:
            if vt.sync_drop(iid):
                log.info("🔐 Сейф: запись удалена на другом устройстве")
                self._safe_event()
            return None
        if not isinstance(d, dict) or d.get("kid") != cur["meta"]["kid"] or not isinstance(d.get("c"), str):
            return False                                   # другим мастер-паролем (ещё не перешифровали) — ждём
        try:
            x = safe_open(cur["k"], d)
        except Exception as e:  # noqa: BLE001
            log.warning("Синхронизация: запись сейфа %s не открылась (%s) — пропускаю", iid, e)
            return False
        if not isinstance(x, dict) or x.get("id") != iid:
            return False
        upd = int(it.get("updated") or 0)
        x["mt"] = upd or int(x.get("mt") or 0)
        mine = vt.get(iid)
        if mine and item_ms(mine) > x["mt"]:
            return False                                   # здесь правили позже — своя уйдёт в облако
        if mine is None:                                   # тот же пароль под другим id (сейф заполняли на двух компьютерах) — одна запись
            for y in vt.sync_items():
                if (y["id"] != iid and y["name"].lower() == str(x.get("name") or "").lower() and y.get("value") == x.get("value")
                        and (y.get("kind") == "page") == (x.get("kind") == "page")):
                    vt.sync_drop(y["id"])
        if not vt.sync_put(x):
            return False
        self._safe_event()
        return None

    def _safe_event(self):
        emit = getattr(self.host, "emit", None)
        if callable(emit):
            try:
                emit("vault_changed")
            except Exception:  # noqa: BLE001
                pass

    def safe_refetch(self):
        """Ключ сейфа появился или сменился: забрать историю заново — записи, пропущенные без ключа, лягут теперь."""
        with self._lock:
            self.state["rev"] = 0
            self._save()
        self.soon.set()

    def safe_status(self):
        sk = getattr(self.host, "safe_key", None)
        cur = sk.get() if sk is not None else None
        rem = sk.remote() if sk is not None else None
        on = self._safe_on() is not None
        return {"on": on, "stale": bool(cur) and not on, "remote": bool(rem) and not on,
               "server": "safe" in (self.state.get("kinds") or ()), "failed": bool(self.state.get("_safe_failed"))}
