"""Ключ сквозного шифрования синхронизации (просьба 19.10 из письма о приватности: «синхронизация — с шифрованием на
устройстве»). Один на все устройства человека, 32 байта; сервер dewiar.pro его не видит никогда.

- Хранится на компьютере зашифрованным ключом этого компьютера (crypt.device_key — Windows DPAPI, Linux файл 0600):
  CONFIG_DIR/sync.key.
- Своим устройствам передаётся конвертом «Близких» (close.own_send — шифруется их открытыми ключами X25519), как ключ
  умного дома: {"sync_key": {"k": base64url, "at": мс}}.
- Записи синхронизации: data = {"e2e": 1, "c": base64url(closecrypto.seal(K, JSON))} — тот же seal, что у телефона
  (ui/assets/closecrypto.js), поэтому компьютер и телефон читают записи друг друга.
"""

import json
import logging
import secrets
import time
from pathlib import Path

import closecrypto as CC
import crypt

log = logging.getLogger("dewiar.sync")
VERSION = 1


class SyncKey:
    def __init__(self, path, device_key_path):
        self.path, self.device_key_path = Path(path), Path(device_key_path)
        self._cache = None

    def _dk(self):
        return crypt.device_key(self.device_key_path, create=True)

    def get(self):
        """-> {"k": 32 байта, "at": мс} или None."""
        if self._cache is not None:
            return self._cache or None
        try:
            d = json.loads(crypt.unseal(self.path.read_bytes(), self._dk()).decode("utf-8"))
            k = CC.b64d(d["k"])
            self._cache = {"k": k, "at": int(d.get("at") or 0)} if len(k) == 32 else {}
        except FileNotFoundError:
            self._cache = {}
        except Exception as e:  # noqa: BLE001 — ключ этого компьютера сменился (перенос папки) — ключ синхронизации придёт заново
            log.warning("Ключ шифрования синхронизации не открылся: %s", e)
            self._cache = {}
        return self._cache or None

    def set(self, k, at=None):
        if not isinstance(k, (bytes, bytearray)) or len(k) != 32:
            raise ValueError("ключ синхронизации — 32 байта")
        at = int(at or time.time() * 1000)
        blob = crypt.seal(json.dumps({"k": CC.b64e(bytes(k)), "at": at, "v": VERSION}).encode("utf-8"), self._dk())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        tmp.replace(self.path)
        self._cache = {"k": bytes(k), "at": at}
        return self._cache

    def create(self):
        return self.set(secrets.token_bytes(32))

    def adopt(self, kb64, at):
        """Ключ пришёл с другого своего устройства. Берём, если своего нет или пришедший новее. -> взяли ли."""
        try:
            k = CC.b64d(str(kb64 or ""))
        except Exception:  # noqa: BLE001
            return False
        if len(k) != 32:
            return False
        cur = self.get()
        if cur and (cur["k"] == k or int(at or 0) <= cur["at"]):
            return False
        self.set(k, int(at or 0) or None)
        return True

    def share(self):
        cur = self.get()
        return {"k": CC.b64e(cur["k"]), "at": cur["at"]} if cur else None


def seal_data(k, data):
    return {"e2e": VERSION, "c": CC.b64e(CC.seal(k, json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))}


def open_data(k, d):
    """Зашифрованная запись -> данные; не тот ключ или испорчена — CloseCryptoError."""
    return json.loads(CC.unseal(k, CC.b64d(d.get("c") or "")).decode("utf-8"))


