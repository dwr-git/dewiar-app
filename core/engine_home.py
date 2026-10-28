"""«Дома по Wi-Fi» в ядре (core/homehub.py — узел и обмен; core/sync.py HomeSync — компьютер со своим узлом).

Настройка sync.home {on}: включили — узел слушает домашнюю сеть, HomeSync меняется с ним по 127.0.0.1. Команды студии:
home_get, home_set {on}, home_pair (новый код на 10 минут: ссылка для QR), home_forget {tid}. Телефон, подключённый так,
синхронизируется с компьютером напрямую — без dewiar.pro; если у компьютера есть и облако, он передаёт правки дальше
(компьютер — мост между телефоном и другими устройствами)."""
import sys
import threading
import time

from engine_base import log
from settings import STATE_DIR


class HomeMixin:
    homehub = None
    home_sync = None

    def home_credentials(self):
        hub = self.homehub
        if hub is None or not hub.running():
            return "", "", ""
        return hub.own_token(), "", f"http://127.0.0.1:{hub.port}/"

    def home_start(self):
        """Включить узел и домашнюю синхронизацию (идемпотентно). -> порт; не вышло — ValueError."""
        from homehub import HomeHub, HubError
        from sync import HomeSync
        if self.homehub is None:
            self.homehub = HomeHub(STATE_DIR / "homehub.sqlite", name=self.device_name)
        try:
            port = self.homehub.start()
        except HubError as e:
            raise ValueError(str(e)) from e
        if self.home_sync is None:
            self.home_sync = HomeSync(self, self.sync)
            self.homehub.on_change = lambda dev: self.home_sync.soon.set()
        if not any(t.name == "sync-home" for t in threading.enumerate()):
            self.home_sync.stopped = False
            threading.Thread(target=self.home_sync.loop, args=(self.stopping,), name="sync-home", daemon=True).start()
        else:
            self.home_sync.soon.set()
        return port

    def home_stop(self):
        if self.home_sync is not None:
            self.home_sync.stopped = True
            self.home_sync.soon.set()
        if self.homehub is not None:
            self.homehub.stop()

    def home_boot(self):
        if (self.s.get("sync") or {}).get("home", {}).get("on") and not self.wav_input:
            try:
                self.home_start()
            except Exception as e:  # noqa: BLE001
                log.info("🏠 Синхронизация по Wi-Fi не запустилась: %s", e)

    def home_public(self, pair=None):
        from homehub import lan_addresses
        on = bool(((self.s.get("sync") or {}).get("home") or {}).get("on"))
        hub = self.homehub
        st = dict(self.home_sync.status) if self.home_sync is not None else {}
        out = {"on": on, "running": bool(hub and hub.running()), "port": hub.port if hub else 0, "ips": lan_addresses(),
               "phones": hub.phones() if hub else [], "ok": st.get("ok"), "at": st.get("at", 0), "error": st.get("error", ""),
               "counts": st.get("counts") or {}, "win": sys.platform.startswith("win")}
        if pair:
            out["pair"] = pair
        return out

    def home_cmd(self, cmd, a):
        if cmd == "home_get":
            return self.home_public()
        if cmd == "home_set":
            on = bool(a.get("on"))
            self.s.update({"sync": {"home": {"on": on}}})
            if on:
                self.home_start()
            else:
                self.home_stop()
            return self.home_public()
        if cmd == "home_pair":
            if not (self.homehub and self.homehub.running()):
                self.s.update({"sync": {"home": {"on": True}}})
                self.home_start()
            from homehub import lan_addresses
            if not lan_addresses():
                raise ValueError("этот компьютер сейчас не в домашней сети (Wi-Fi или кабель) — подключитесь и попробуйте снова")
            p = self.homehub.pair_new()
            return self.home_public(pair={"link": self.homehub.pair_link(p), "until": p["until"], "tid": p["tid"]})
        if cmd == "home_forget":
            if self.homehub:
                self.homehub.forget(str(a.get("tid") or ""))
            return self.home_public()
        raise ValueError("неизвестная команда " + cmd)

    def home_wait_phone(self, tid, timeout=1.0):
        """Для проверок: телефон с этим ключом уже обменялся?"""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if any(p["tid"] == tid for p in (self.homehub.phones() if self.homehub else [])):
                return True
            time.sleep(0.1)
        return False
