"""Синхронизация — свои плагины Лиры между компьютерами (часть Sync, чистое ядро 1.0.16): заголовок и куски,
сборка и установка, старые куски."""
import base64
import hashlib
import re
import shutil
import time
from sync_base import log


class PluginsMixin:
    # ---------- свои плагины Лиры между компьютерами (вид plugin, core/plugin_sync.py) ----------

    def _snap_plugins(self, out):
        """Плагины Лиры -> plugin:<id> (заголовок) и plugin:<id>.<i> (куски сжатой сборки; данные None + отпечаток, читаем,
        только когда отправлять — _plugin_read). Кэш plg {id: [подпись файлов, sha, кусков, code, name]}; сборка — в памяти."""
        import plugin_sync as PS
        P = self.host.plugins
        cache = self.state.setdefault("plg", {})
        had = self.state.setdefault("plg_had", {})
        mem = self.__dict__.setdefault("_plg_mem", {})
        seen = set()
        for pid, d in PS.made_dirs(P):
            sig = PS.signature(d, pid)
            c = cache.get(pid)
            if not c or c[0] != sig or pid not in mem:
                blob, info = PS.bundle(d, pid)
                if blob is None:
                    if not c:
                        if isinstance(info, str) and info.startswith("больше"):
                            log.info("🔄 Плагин %s не синхронизируется: %s", pid, info)
                        continue
                else:
                    c = [sig, hashlib.sha1(blob).hexdigest(), len(PS.parts(blob)), info["code"], info["name"]]
                    cache[pid] = c
                    mem[pid] = blob
            seen.add(pid)
            had[pid] = int(time.time())
            out["plugin:" + pid] = {"name": c[4], "sha": c[1], "n": c[2], "code": bool(c[3]), "from": str(self.host.device_name())[:40]}
            for i in range(c[2]):
                out[f"plugin:{pid}.{i}"] = None
                out[f"plugin:{pid}.{i}#h"] = f"{c[1]}:{i}:{c[2]}"
        for pid in [p for p in cache if p not in seen]:
            cache.pop(pid, None)
            mem.pop(pid, None)
        self._plg_prune()

    def _plg_prune(self):
        now = time.time()
        pin = self.state.get("plg_in") or {}
        for pid in [p for p, h in pin.items() if now - int(h.get("at") or 0) > self.PLG_STALE]:
            pin.pop(pid, None)
        root = self._plg_dir()
        if not root.is_dir():
            return
        for d in root.iterdir():
            try:
                cur = (pin.get(d.name) or {}).get("sha")
                for f in d.iterdir():
                    if not cur or not f.name.startswith(cur + ".") or now - f.stat().st_mtime > self.PLG_STALE:
                        if now - f.stat().st_mtime > 3600:          # кусок не той сборки (или старый) — через час убираем
                            f.unlink()
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    def _plugin_read(self, iid):
        import plugin_sync as PS
        pid, _, i = iid.partition(".")
        c = (self.state.get("plg") or {}).get(pid)
        blob = getattr(self, "_plg_mem", {}).get(pid)
        if not c or blob is None or not i.isdigit() or hashlib.sha1(blob).hexdigest() != c[1]:
            return None
        return PS.part_data(blob, c[1], int(i))

    def _plg_dir(self):
        return self.path.parent / "plugparts"

    def _apply_plugin(self, iid, d, deleted, it_updated=0):
        """Заголовок или кусок плагина с другого компьютера. Плагин ставится, когда пришли заголовок и все куски одной
        сборки и сошёлся отпечаток. Удаление заголовка — удалить плагин и здесь; удаление куска — ничего."""
        import plugin_sync as PS
        pid, _, i = iid.partition(".")
        if not PS.ID_RX.fullmatch(pid) or getattr(self.host, "plugins", None) is None:
            return False
        pdir = self._plg_dir() / pid
        if deleted:
            if not i:
                shutil.rmtree(pdir, ignore_errors=True)
                (self.state.get("plg_in") or {}).pop(pid, None)
                PS.remove(self.host, pid)
                (self.state.get("plg_had") or {}).pop(pid, None)
            return None
        if not isinstance(d, dict):
            return False
        sha = str(d.get("sha") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not isinstance(d.get("n"), int) or not 0 < d["n"] <= -(-PS.MAX // PS.CHUNK) + 1:
            return False
        if i:
            if not i.isdigit() or not 0 <= int(i) < d["n"] or d.get("i") != int(i):
                return False
            try:
                part = base64.b64decode(str(d.get("b64") or ""), validate=True)
            except ValueError:
                return False
            pdir.mkdir(parents=True, exist_ok=True)
            (pdir / f"{sha}.{int(i)}").write_bytes(part)
        else:
            self.state.setdefault("plg_in", {})[pid] = {"sha": sha, "n": d["n"], "from": str(d.get("from") or "")[:40], "at": int(time.time())}
        return self._plugin_try(pid)

    def _plugin_try(self, pid):
        """Все куски сборки на месте — поставить плагин. -> None (легло или ждём кусков), False — не принят."""
        import plugin_sync as PS
        head = (self.state.get("plg_in") or {}).get(pid)
        if not head:
            return None
        c = (self.state.get("plg") or {}).get(pid)
        pdir = self._plg_dir() / pid
        if c and c[1] == head["sha"]:                  # такая сборка здесь уже есть
            self.state["plg_in"].pop(pid, None)
            shutil.rmtree(pdir, ignore_errors=True)
            return None
        ps = [pdir / f"{head['sha']}.{k}" for k in range(head["n"])]
        if not all(p.is_file() for p in ps):
            return None
        blob = b"".join(p.read_bytes() for p in ps)
        self.state["plg_in"].pop(pid, None)
        shutil.rmtree(pdir, ignore_errors=True)
        b = PS.unpack(blob) if hashlib.sha1(blob).hexdigest() == head["sha"] else None
        if b is None:
            log.warning("🔄 Плагин %s с другого компьютера пришёл испорченным — пропускаю", pid)
            return False
        try:
            r = PS.install(self.host, pid, b, head)
            if not r:
                return False
            # здешнее сохранилось рядом (свои версии, правка до синхронизации) — сборку надо отправить, иначе отпечаток
            # «как легло у нас» спрятал бы её от других компьютеров. Только тогда: разница лишь в отброшенной чужой
            # программе старых версий или в обрезке по размеру — не повод (иначе два компьютера пересылали бы её по кругу)
            if r == "more":
                self.__dict__.setdefault("_plg_resend", set()).add(pid)
            return None
        except Exception as e:  # noqa: BLE001
            log.warning("🔄 Плагин %s с другого компьютера не поставился: %s", pid, e)
            return False
