"""Запасной вход через SSH — только для владельца сервера Dewiar (29.10, владелец: «после пропадания света не удаётся
восстановить домен… сервер Лиры по SSH виден, а сервер с доменом — нет; можно ли, чтобы Лира работала через SSH?»;
«только для меня нужно»).

Сайт (папка dwrapp с cloud.php) живёт на сервере Лиры, а домен dewiar.pro — на другом сервере. Упал тот — встало всё,
хотя сам сайт жив. Здесь: раз в CHECK_SEC проверяем, открывается ли dewiar.pro; не открывается — поднимаем туннель
`ssh -N -L 127.0.0.1:<свой порт>:<адрес сайта на сервере>` тем же ключом, которым владелец заходит из терминала
(BatchMode: пароля не спрашиваем и не храним), и net.set_ssh направляет запросы к папке сайта в туннель. Наш ли это
сайт — проверяется подписью метки сайта (net._lan_ok, как «дома — напрямую»): метку сайт выдаёт вошедшим (net.lan).
Домен вернулся — туннель закрывается сам.

Настройка (settings «sshlink»): on, host, port (22), user, target («127.0.0.1:9099» — сайт в Docker на сервере), key
(путь к ключу, необязательно). Только компьютер; телефон — нет."""
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time

import httpx

log = logging.getLogger("dewiar.sshlink")

CHECK_SEC = 30                 # как часто проверять домен
DOWN_AFTER = 2                 # столько неудачных проверок подряд — домен «лёг», поднимаем туннель
UP_TIMEOUT = 15                # ждать, пока туннель откроет порт
DEFAULT_TARGET = "127.0.0.1:9099"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _port_open(port, timeout=0.5):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def clean(cfg):
    """Настройка из студии -> проверенный словарь (ошибка — ValueError с понятным текстом)."""
    host = str(cfg.get("host") or "").strip()
    user = str(cfg.get("user") or "").strip()
    if "@" in host and not user:
        user, host = host.split("@", 1)
    try:
        port = int(cfg.get("port") or 22)
    except (TypeError, ValueError):
        raise ValueError("порт SSH — число, обычно 22") from None
    target = str(cfg.get("target") or DEFAULT_TARGET).strip()
    bad = lambda x: not x or any(c in x for c in " \t\n'\"`;|&$<>\\")   # noqa: E731 — в командную строку ssh
    if bad(host):
        raise ValueError("впишите адрес сервера Лиры — как в терминале: 178.124.…, или имя")
    if bad(user):
        raise ValueError("впишите имя пользователя на сервере — как в ssh имя@сервер")
    if bad(target) or ":" not in target:
        raise ValueError("адрес сайта на сервере — вида 127.0.0.1:9099")
    if not 0 < port < 65536:
        raise ValueError("порт SSH — от 1 до 65535")
    key = str(cfg.get("key") or "").strip()
    if key and not os.path.isfile(os.path.expanduser(key)):
        raise ValueError("файла ключа нет — оставьте поле пустым, если в терминале заходите без -i")
    return {"on": bool(cfg.get("on")), "host": host, "port": port, "user": user, "target": target, "key": key}


class SshLink:
    def __init__(self, engine):
        self.e = engine
        self.proc = None
        self.lport = 0
        self.fails = 0
        self.state = "off"           # off | watching | up | error
        self.error = ""
        self.since = 0.0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._t = None

    # ---------- настройка ----------
    def cfg(self):
        return dict(self.e.s.get("sshlink") or {})

    def public(self):
        c = self.cfg()
        import net
        return {"on": bool(c.get("on")), "host": c.get("host", ""), "port": c.get("port", 22), "user": c.get("user", ""),
                "target": c.get("target") or DEFAULT_TARGET, "key": c.get("key", ""), "state": self.state, "error": self.error,
                "since": self.since, "ssh": bool(shutil.which("ssh")), "tunnel": net.ssh_status(),
                "visible": bool(c.get("host")) or bool(self.e.s.get("net", "lan_seen"))}

    def save(self, a):
        c = clean(dict(self.cfg(), **{k: a[k] for k in ("on", "host", "port", "user", "target", "key") if k in a}))
        self.e.s.update({"sshlink": c})
        self.fails = 0
        if c["on"]:
            self.start()
        else:
            self.stop()
        return self.public()

    # ---------- туннель ----------
    def _cmd(self, c, lport):
        ssh = shutil.which("ssh")
        if not ssh:
            raise RuntimeError("на этом компьютере нет программы ssh (в Windows 10/11 — «Клиент OpenSSH» в дополнительных компонентах)")
        cmd = [ssh, "-N", "-T", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=15",
               "-o", "ServerAliveCountMax=3", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new",
               "-L", f"127.0.0.1:{lport}:{c['target']}", "-p", str(c["port"])]
        if c.get("key"):
            cmd += ["-i", os.path.expanduser(c["key"])]
        return cmd + [f"{c['user']}@{c['host']}"]

    def _lan(self):
        lan = self.e.s.get("net", "lan") or {}
        return lan.get("public", ""), lan.get("id", "")

    def up(self, c=None):
        """Поднять туннель (если ещё нет) и направить в него папку сайта. -> True/False; причина — в self.error."""
        c = clean(c or self.cfg())
        import net
        with self._lock:
            if self.proc and self.proc.poll() is None and _port_open(self.lport):
                return True
            self._kill()
            public, lid = self._lan()
            if not public or not lid:
                self.error = "сайт ещё не выдал свою метку — один раз войдите аккаунтом, пока dewiar.pro открывается"
                self.state = "error"
                return False
            self.lport = _free_port()
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                self._err = tempfile.TemporaryFile()              # не труба: долгий туннель не встанет на переполненном выводе
                self.proc = subprocess.Popen(self._cmd(c, self.lport), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=self._err, creationflags=flags)
            except (OSError, RuntimeError) as e:
                self.error, self.state = str(e), "error"
                return False
            t0 = time.time()
            while time.time() - t0 < UP_TIMEOUT:
                if self.proc.poll() is not None:
                    self._err.seek(0)
                    err = self._err.read().decode("utf-8", "replace").strip().splitlines()
                    self.error = _why(err[-1] if err else f"ssh завершился (код {self.proc.returncode})")
                    self.state, self.proc = "error", None
                    return False
                if _port_open(self.lport):
                    break
                time.sleep(0.3)
            else:
                self._kill()
                self.error, self.state = "сервер не ответил по SSH за 15 секунд", "error"
                return False
            net.set_ssh(public, f"http://127.0.0.1:{self.lport}/" + public.split("/", 3)[-1], lid)
            self.error, self.state, self.since = "", "up", time.time()
            log.info("🔐 Запасной вход через SSH поднят: %s@%s → %s", c["user"], c["host"], c["target"])
            return True

    def down(self):
        import net
        with self._lock:
            was = self.proc is not None
            self._kill()
            net.set_ssh()
            if was:
                log.info("🔐 Домен снова отвечает — запасной вход через SSH закрыт")
            self.state = "watching" if self.cfg().get("on") else "off"

    def _kill(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()

    # ---------- проверка домена ----------
    def domain_ok(self):
        """Открывается ли сайт по имени — напрямую, мимо туннеля и «дома» (иначе он «открылся» бы через туннель)."""
        public, _ = self._lan()
        url = (public or "https://dewiar.pro/dwrapp/") + "cloud.php?p=/ping"
        try:
            with httpx.HTTPTransport(retries=0) as t:
                r = t.handle_request(httpx.Request("GET", url, extensions={"timeout": {"connect": 6, "read": 8, "write": 6, "pool": 6}}))
                r.read()
            return r.status_code < 500
        except Exception:  # noqa: BLE001 — домен не открылся
            return False

    def test(self, a=None):
        """«Проверить» в студии: поднять туннель и убедиться подписью, что за ним наш сайт; домен работает — туннель закрыть."""
        import net
        c = clean(dict(self.cfg(), **(a or {})))
        if not self.up(c):
            return {"ok": False, "error": self.error}
        ok = net._lan_ok(net._ssh)
        res = {"ok": ok, "error": "" if ok else "туннель поднялся, но сайт за ним не ответил — проверьте адрес сайта на сервере"}
        if not ok:
            self.down()
        elif self.domain_ok() or not c["on"]:
            self.down()                      # домен жив — туннель не держим; проверка показала, что он работает
        return res

    def start(self):
        if self._t and self._t.is_alive():
            return
        self._stop.clear()
        self.state = "watching"
        self._t = threading.Thread(target=self._loop, name="sshlink", daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()
        self.down()
        self.state = "off"

    def _loop(self):
        while not self._stop.is_set():
            try:
                if not self.cfg().get("on"):
                    self.down()
                    return
                if self.domain_ok():
                    self.fails = 0
                    if self.proc:
                        self.down()
                else:
                    self.fails += 1
                    if self.fails >= DOWN_AFTER:
                        if not self.up() and self.fails == DOWN_AFTER:
                            log.warning("Запасной вход через SSH не поднялся: %s", self.error)
            except Exception:  # noqa: BLE001
                log.exception("запасной вход через SSH")
            if self._stop.wait(CHECK_SEC):
                break


def _why(line):
    """Строка ошибки ssh -> по-человечески."""
    s = line.lower()
    if "permission denied" in s:
        return "сервер не пустил по ключу: в терминале вы заходите по паролю? Нужен вход по ключу (ssh-copy-id), пароль здесь не хранится"
    if "could not resolve" in s or "name or service not known" in s:
        return "не найден такой сервер — проверьте адрес"
    if "connection refused" in s:
        return "сервер отказал в подключении — проверьте порт SSH"
    if "timed out" in s or "no route" in s:
        return "сервер не отвечает — проверьте адрес и что он включён"
    if "host key verification failed" in s or "remote host identification has changed" in s:
        return "ключ сервера изменился — зайдите один раз из терминала и подтвердите"
    if "address already in use" in s or "forwarding failed" in s:
        return "не открылся порт туннеля — попробуйте ещё раз"
    return "ssh: " + line[:160]
