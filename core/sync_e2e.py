"""Синхронизация — сквозное шифрование (часть Sync, чистое ядро 1.0.16): ключ на этом устройстве, включить и
выключить, ключ с другого устройства, метка «шифрование включено»."""
from sync_base import E2E_KINDS, E2E_MARK, log


class E2EMixin:
    # ---------- сквозное шифрование (sync.e2e) ----------

    def e2e_key(self):
        """Ключ, если шифрование включено на этом устройстве и ключ есть. -> 32 байта или None."""
        ks = getattr(self.host, "sync_key", None)
        s = getattr(self.host, "s", None)
        try:
            on = bool(s.get("sync", "e2e")) if s is not None else False
        except Exception:  # noqa: BLE001
            on = False
        cur = ks.get() if ks is not None and on else None
        return cur["k"] if cur else None

    def _sealable(self, kind, iid, data):
        key = kind + ":" + iid
        if key == E2E_MARK or kind not in E2E_KINDS or not isinstance(data, dict) or not data:
            return False
        if kind == "taskreq" and data.get("cloud"):     # задачу просили выполнить в облаке — серверу её надо прочитать
            return False
        return True

    def e2e_status(self):
        ks = getattr(self.host, "sync_key", None)
        return {"on": self.e2e_key() is not None, "key": bool(ks is not None and ks.get()),
                "remote": bool(self.state.get("e2e_remote")), "locked": int(self.state.get("e2e_locked") or 0)}

    def e2e_enable(self, on):
        """Включить или выключить шифрование на этом устройстве. Включили — ключ (свой или уже полученный), всё своё
        уходит заново зашифрованным, ключ — своим устройствам конвертом. Выключили — только здесь (шифрование другие
        устройства не выключает: метку в облаке мог бы снять и чужой, завладевший аккаунтом)."""
        ks = getattr(self.host, "sync_key", None)
        if on and ks is not None and not ks.get():
            ks.create()
        self.host.s.update({"sync": {"e2e": bool(on)}})
        with self._lock:
            self.state["reseal_all"] = True
            self.state["e2e_off_here"] = not on       # выключили здесь — метка других устройств сама не включит
            self._save()
        share = getattr(self.host, "own_share", None)
        if on and callable(share):
            share()
        self.soon.set()
        return self.e2e_status()

    def key_arrived(self):
        """Ключ пришёл с другого устройства: включить шифрование и забрать историю заново (зашифрованное, что не
        открылось, — откроется теперь)."""
        if not self.state.get("e2e_off_here"):
            self.host.s.update({"sync": {"e2e": True}})
        with self._lock:
            self.state.update(rev=0, reseal_all=True, e2e_locked=0)
            self._save()
        self.soon.set()

    def _any_key(self):
        """Ключ есть, а шифрование здесь выключено (выключили только здесь) — открыть пришедшее всё равно можно."""
        ks = getattr(self.host, "sync_key", None)
        cur = ks.get() if ks is not None else None
        return cur["k"] if cur else None

    def _apply_mark(self, d, deleted):
        """Метка «шифрование включено» с другого устройства: ключ есть — включаем и здесь; нет — просим его у своих
        устройств (конверт close). Снятую метку не слушаем: выключают шифрование только на самом устройстве."""
        if deleted or not (d or {}).get("on"):
            return False
        ks = getattr(self.host, "sync_key", None)
        s = getattr(self.host, "s", None)
        if ks is not None and ks.get():
            if s is not None and not s.get("sync", "e2e") and not self.state.get("e2e_off_here"):
                s.update({"sync": {"e2e": True}})
                self.state["reseal_all"] = True
                log.info("🔐 Синхронизация зашифрована на другом устройстве — шифрую и здесь")
            return False
        self.state["e2e_remote"] = True
        want = getattr(self.host, "sync_key_wanted", None)
        if callable(want):
            want()
        return False
