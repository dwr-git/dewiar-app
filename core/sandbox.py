"""Песочница для кода задач («Большие задачи», выпуск 5, docs/HARNESS.md): run_python и run_shell задачи пишут только в
папку задачи и во временную папку, личные данные человека вне папки задачи не видят, сеть — по настройке задачи (по
умолчанию выключена), по таймауту гибнет всё дерево процессов. В настоящей песочнице (bwrap, landlock) код задачи идёт
без вопросов человеку — задачи не встают на паузу, когда его нет рядом; под охраной (guard) — с его разрешения (tasks.py).

Режимы (mode()):
- «bwrap» (Linux, есть bubblewrap) — НАСТОЯЩАЯ изоляция: свои пространства имён (пользователь, процессы, сеть, IPC), без
  новых пространств пользователя внутри (--disable-userns), без возможностей ядра. Корень — белый список: /usr, /lib*, /bin,
  /etc (без ключей сети), /opt, /sys — только чтение; своя /dev, /proc, /tmp, пустая /run. Домашней папки, /media, /mnt,
  /srv, чужих домов и сокетов системы (/run/docker.sock…) в песочнице нет вовсе; обратно — только сам Python (чтение),
  данные человеком папки (чтение; личное внутри них — ~/.ssh, папки Dewiar… — закрыто поверх) и папка задачи (запись).
  Сеть — только если задаче её дали: через slirp4netns (своя сеть, без 127.0.0.1 компьютера), а без него — сеть компьютера
  целиком (так и говорим человеку). strict=True (облачный исполнитель): из /etc — только нужное (ETC_KEEP), без /opt и /sys.
- «landlock» (Linux 5.13+ без bubblewrap) — тоже настоящая: перед запуском кода процесс сам себя запирает Landlock
  (ctypes, landlock_create_ruleset / add_rule / restrict_self после PR_SET_NO_NEW_PRIVS): читать — система, Python, папка
  задачи, данные папки (без личного внутри); писать — папка задачи и временная папка. ABI ≥ 4 — без сети TCP запрещён
  целиком, ABI ≥ 6 — закрыты абстрактные сокеты и сигналы чужим процессам; чужие процессы (их /proc/<pid>/environ) Landlock
  закрывает сам. Поверх — та же охрана Python, что в guard (без запрета программ). Не закрывает: именованные сокеты системы
  (/run/docker.sock — если человек в группе docker), UDP при выключенной сети (DNS-запросы) — их держит unshare, если он есть.
- «guard» (Windows; Linux без bwrap и Landlock) — ОХРАНА, А НЕ ТЮРЬМА: защищает от случайных ошибок кода, но не от
  нарочного взлома (ctypes, замыкания, C-библиотеки — обходы в несколько строк; проверка sandbox_test показывает, какие
  именно уже закрыты). Поэтому под охраной код задачи — только с разрешения человека. Держит: текущая папка — папка
  задачи; очищенное окружение; ограничения памяти, размера файлов и числа процессов (setrlimit; в Windows — Job Object,
  назначенный до первой инструкции кода: процесс создаётся приостановленным); своя группа процессов и добивание по метке;
  крючок аудита Python (sys.addaudithook): запись — только в папку задачи и временную, чтение — не из личного и не из
  домашней папки вне папки задачи, сеть — по настройке (без адресов этого компьютера и домашней сети), программы — только
  тот же Python с той же охраной и конвертеры с файлами задачи; unshare (если пускает) держит сеть и дерево процессов ядром.
- «off» — без песочницы (DEWIAR_SANDBOX=off): как до выпуска 5.

После каждого запуска (во всех режимах) — ссылки, которые код оставил в папке задачи и которые ведут наружу, удаляются
(purge_links): иначе Dewiar (вне песочницы) писал бы через них в домашнюю папку.

DEWIAR_SANDBOX=auto|bwrap|landlock|guard|off (по умолчанию auto: bwrap → landlock → guard), DEWIAR_SANDBOX_UNSHARE=0 —
без unshare, DEWIAR_SANDBOX_SLIRP=0 — без slirp4netns, DEWIAR_SANDBOX_MEM_MB — потолок памяти кода задачи.
"""

import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

WIN = os.name == "nt"
TIMEOUT_MAX = 600                         # секунд на один запуск кода задачи
OUT_CAP = 1 << 20                         # вывод (stdout, stderr) в ответе — не больше (начало и конец)
FSIZE = 4 << 30                           # самый большой файл, который код задачи может записать
NPROC_EXTRA = int(os.environ.get("DEWIAR_SANDBOX_NPROC") or 512)   # процессов сверх тех, что у человека уже есть
                                          # (RLIMIT_NPROC — по пользователю; облако — меньше, см. install-runner.sh)
FILES_MAX = 200000                        # с потолком папки (облако): и файлов не больше
SYSTEM_TOP = {"/", "/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32", "/etc", "/proc", "/sys", "/dev", "/run",
              "/var", "/opt", "/tmp", "/home", "/root", "/srv", "/mnt", "/media", "/boot", "/snap"}
SYS_DIRS = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32")
# личное в домашней папке (Linux, macOS, Windows): закрыто, даже если человек дал задаче папку выше (всю ~ или ~/.config) —
# открыто, только если он дал саму эту папку (или папку внутри неё)
PRIVATE_HOME = (
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".password-store", ".local/share/keyrings", ".pki",
    ".mozilla", ".thunderbird", ".config/google-chrome", ".config/chromium", ".config/BraveSoftware", ".config/microsoft-edge",
    ".config/opera", ".config/vivaldi", ".config/yandex-browser", ".config/gh", ".config/rclone", ".config/dewiar",
    ".local/share/dewiar", ".local/share/TelegramDesktop", ".var/app", "snap/firefox", "snap/chromium", ".netrc",
    ".git-credentials", ".pgpass", ".npmrc", ".pypirc", ".bash_history", ".zsh_history", ".python_history",
    "Library/Keychains", "Library/Cookies",
    "Library/Application Support/Google/Chrome", "Library/Application Support/Firefox", "Library/Application Support/Dewiar",
    "AppData/Roaming/Mozilla", "AppData/Local/Google/Chrome/User Data", "AppData/Local/Microsoft/Edge/User Data",
    "AppData/Roaming/Opera Software", "AppData/Local/BraveSoftware", "AppData/Local/Yandex", "AppData/Roaming/Telegram Desktop",
    "AppData/Roaming/Microsoft/Credentials", "AppData/Local/Microsoft/Credentials", "AppData/Roaming/Microsoft/Protect",
    "AppData/Roaming/Dewiar", "AppData/Local/Dewiar")
SECRET_NAMES = ("credentials.json", "provision.json", "config.php", "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")
# strict (облако): из /etc — только нужное программам; ни .env сайта, ни /etc/dewiar-runner.env с ключом исполнителя
ETC_KEEP = ("/etc/ssl", "/etc/ca-certificates", "/etc/pki", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf",
            "/etc/host.conf", "/etc/gai.conf", "/etc/localtime", "/etc/timezone", "/etc/ld.so.cache", "/etc/ld.so.conf",
            "/etc/ld.so.conf.d", "/etc/fonts", "/etc/alternatives", "/etc/mime.types", "/etc/passwd", "/etc/group",
            "/etc/matplotlibrc", "/etc/ImageMagick-6", "/etc/ImageMagick-7")
# компьютер: /etc целиком (программам нужно много разного), но без ключей сетей и служб
ETC_HIDE = ("/etc/NetworkManager/system-connections", "/etc/wpa_supplicant", "/etc/ssh", "/etc/wireguard", "/etc/openvpn",
            "/etc/ppp", "/etc/dewiar-runner.env", "/etc/dewiar-site.conf", "/etc/docker", "/etc/sudoers.d", "/etc/cups")
# окружение кода задачи — белый список: всё остальное (ключи моделей, DEWIAR_RUNNER_KEY, токены, SSH_AUTH_SOCK,
# DBUS_SESSION_BUS_ADDRESS, DISPLAY…) не передаётся
ENV_KEEP = {"PATH", "LANG", "LANGUAGE", "TZ", "TERM", "USER", "LOGNAME", "USERNAME", "SYSTEMROOT", "WINDIR", "COMSPEC",
            "PATHEXT", "SYSTEMDRIVE", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "COMMONPROGRAMFILES",
            "COMMONPROGRAMFILES(X86)", "PROGRAMDATA", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
            "PROCESSOR_IDENTIFIER", "OS", "PSMODULEPATH"}
# настоящая изоляция: код задачи — без вопросов человеку. Только bwrap: Landlock (вторая рецензия) не закрывает именованные
# сокеты (сессионная D-Bus → systemd-run --user = запуск чего угодно вне песочницы) и при ABI < 4 — сеть; он — защита
# вдобавок, а код под ним — с разрешения человека, как под охраной
REAL = ("bwrap",)


class SandboxError(Exception):
    """Песочница недоступна (например, в облаке нет bubblewrap) — код не запускается."""


def real_sandbox(m):
    """Режим — настоящая изоляция (а не охрана): код задачи можно запускать без вопроса человеку."""
    return m in REAL


# ---------- какой режим доступен ----------

_probe = {}
_probe_lock = threading.Lock()


def _bwrap_bin():
    """bwrap: свой экземпляр исполнителя облака (DEWIAR_BWRAP — копия, которой AppArmor разрешает пространства имён только
    для пользователя исполнителя) или из PATH."""
    if WIN:
        return None
    own = os.environ.get("DEWIAR_BWRAP")
    if own:
        return own if os.access(own, os.X_OK) else None
    return shutil.which("bwrap")


def _bwrap_try(extra):
    b = _bwrap_bin()
    if not b:
        return False
    try:
        r = subprocess.run([b, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL", *extra,
                            "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--",
                            sys.executable, "-I", "-S", "-c", "pass"],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=15)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def bwrap_ok():
    """bubblewrap есть и действительно запускает Python в своих пространствах имён (бывает, что они запрещены ядром или
    AppArmor) — проверяется один раз за жизнь процесса."""
    with _probe_lock:
        if "bwrap" not in _probe:
            _probe["bwrap"] = _bwrap_try([])
            # --disable-userns (bubblewrap 0.8+): внутри песочницы — без новых пространств пользователя (к ним сводится
            # большинство дыр ядра, доступных без прав)
            _probe["bwrap_nouserns"] = _probe["bwrap"] and _bwrap_try(["--unshare-user", "--disable-userns"])
        return _probe["bwrap"]


def _unshare_flags():
    """Флаги unshare для guard и landlock: своё пространство пользователя и процессов (и сети — если она выключена), чтобы
    «убить всё дерево» и «нет сети» держало ядро. Не работает (нет unshare, запрещено) — None."""
    if WIN or os.environ.get("DEWIAR_SANDBOX_UNSHARE", "1") == "0":
        return None
    with _probe_lock:
        if "unshare" not in _probe:
            u, got = shutil.which("unshare"), None
            if u:
                for who in ("--map-current-user", "--map-root-user"):
                    fl = ["--user", who, "--pid", "--fork", "--kill-child"]
                    try:
                        r = subprocess.run([u, *fl, "--net", "--", sys.executable, "-I", "-S", "-c", "pass"],
                                           stdin=subprocess.DEVNULL, capture_output=True, timeout=15)
                    except (OSError, subprocess.SubprocessError):
                        continue
                    if r.returncode == 0:
                        got = [u, *fl]
                        break
            _probe["unshare"] = got
        return _probe["unshare"]


def slirp_bin():
    """slirp4netns: своя сеть песочницы bwrap без 127.0.0.1 компьютера (--disable-host-loopback). Нет — None."""
    if WIN or os.environ.get("DEWIAR_SANDBOX_SLIRP", "1") == "0":
        return None
    return shutil.which("slirp4netns")


def landlock_abi():
    """Версия Landlock в ядре (0 — нет). Только Linux x86_64 и aarch64: там номера вызовов 444–446."""
    if WIN or sys.platform != "linux" or platform.machine().lower() not in ("x86_64", "amd64", "aarch64", "arm64"):
        return 0
    with _probe_lock:
        if "ll_abi" not in _probe:
            try:
                import ctypes
                libc = ctypes.CDLL(None, use_errno=True)
                libc.syscall.restype = ctypes.c_long
                v = int(libc.syscall(444, None, 0, 1))         # LANDLOCK_CREATE_RULESET_VERSION
            except Exception:  # noqa: BLE001
                v = 0
            _probe["ll_abi"] = max(0, v)
        return _probe["ll_abi"]


def landlock_ok():
    """Landlock не только есть, но и запирает: Python под ним запускается, а домашняя папка ему не видна (раз за жизнь)."""
    if not landlock_abi():
        return False
    with _probe_lock:
        if "landlock" in _probe:
            return _probe["landlock"]
    ok = False
    try:
        base = Path(tempfile.mkdtemp(prefix="dewiar-ll-"))
        spec = json.dumps(_ll_spec(policy(base, python=sys.executable), base, False))
        probe = "import os,sys\ntry:\n os.listdir(sys.argv[1]); print('open')\nexcept PermissionError: print('shut')"
        r = subprocess.run([sys.executable, "-I", "-S", "-c", LAUNCH, "0", "0", "0", spec, sys.executable, "-I", "-S", "-c",
                            probe, str(home())], capture_output=True, text=True, timeout=20, cwd=str(base))
        ok = r.returncode == 0 and r.stdout.strip() == "shut"
        shutil.rmtree(base, ignore_errors=True)
    except (OSError, subprocess.SubprocessError, ValueError):
        ok = False
    with _probe_lock:
        _probe["landlock"] = ok
    return ok


def mode(strict=False):
    """Режим песочницы: "bwrap" | "landlock" | "guard" | "off"; strict (облако) — только "bwrap", иначе "" (кода нет)."""
    want = (os.environ.get("DEWIAR_SANDBOX") or "auto").strip().lower()
    if want == "off" and not strict:
        return "off"
    if want in ("auto", "bwrap") and bwrap_ok():
        return "bwrap"
    if strict or want == "bwrap":
        return ""                      # просили bwrap, а он не работает — кода нет (громко), а не тихо слабее
    if want in ("auto", "landlock") and landlock_ok():
        return "landlock"
    if want == "landlock":
        return ""
    return "guard"


def net_isolated(m):
    """Сеть, данная задаче, — своя (без служб этого компьютера на 127.0.0.1) или сеть компьютера целиком."""
    return m == "bwrap" and bool(slirp_bin())


def net_note(m):
    """Что именно получит код задачи, если дать ему сеть, — для вопроса человеку и студии (честно)."""
    if net_isolated(m):
        return ("интернет и домашнюю сеть (роутер, принтеры, другие компьютеры, службы этого компьютера, открытые в сеть); "
                "только 127.0.0.1 этого компьютера коду не виден")
    if m == "bwrap":
        return "сеть этого компьютера, включая локальные службы (127.0.0.1)"
    return "интернет; адреса этого компьютера и домашней сети закрыты только для Python, другие программы их видят"


def describe(m, net=False):
    """Одной строкой для подсказки задачи и журнала."""
    net_s = "сеть для кода включена" if net else "сеть для кода выключена (сведения — web_search, read_webpage, download)"
    if m in REAL:
        return f"код задачи (run_python, run_shell) работает в песочнице: пишет только в папку задачи, {net_s}"
    if m == "landlock":
        weak = "" if net or landlock_abi() >= 4 or _unshare_flags() else " (сеть закрыта только для Python)"
        return (f"код задачи (run_python, run_shell) запускается с разрешения человека, под защитой ядра (Landlock): пишет "
                f"только в папку задачи, {net_s}{weak}")
    if m == "guard":
        return f"код задачи (run_python, run_shell) запускается с разрешения человека, под охраной: пишет только в папку задачи, {net_s}"
    return "код задачи работает без песочницы"


# ---------- что можно ----------

def _real(p):
    try:
        return Path(os.path.realpath(os.path.expanduser(str(p))))
    except (OSError, ValueError):
        return Path(os.path.abspath(str(p)))


def _under(p, root):
    return p == root or root in p.parents


def home():
    return _real("~")


def private_paths():
    """Личное, что код задачи читать не должен, даже вне домашней папки: папки Dewiar (настройки, состояние), ключи,
    профили браузеров, связки ключей."""
    h = home()
    out = [h / x for x in PRIVATE_HOME]
    try:
        from settings import CONFIG_DIR, STATE_DIR
        out += [_real(CONFIG_DIR), _real(STATE_DIR)]
    except Exception:  # noqa: BLE001 — песочница работает и без настроек (облако, проверки)
        for k in ("DEWIAR_CONFIG_DIR", "DEWIAR_STATE_DIR"):
            if os.environ.get(k):
                out.append(_real(os.environ[k]))
    # ~/.ssh — ссылка на /data/ssh (вторая рецензия): личное — и сама ссылка, и то, куда она ведёт
    for x in list(out):
        try:
            if os.path.islink(x):
                out.append(_real(x))
        except OSError:
            pass
    return list(dict.fromkeys(out))


def is_private(p, grants=(), hide=(), root=None):
    """Путь — личное человека, которое задаче не дано, даже если лежит в данной ей папке (S1: дали всю ~ — ~/.ssh и
    папки Dewiar всё равно закрыты; открыты, только если дали саму эту папку). Папка задачи root — всегда своя."""
    p = _real(p)
    if root is not None and _under(p, _real(root)):
        return False
    b = p.name
    if b == ".env" or b.startswith(".env.") or b in SECRET_NAMES:
        return True
    gs = [_real(g) for g in grants]
    for q in private_paths() + [_real(z) for z in hide if z]:
        if _under(p, q) and not any(_under(g, q) and _under(p, g) for g in gs):
            return True
    return False


_roots_cache = {}
PY_INFO = ("import sys,site,os,json\nu=site.getusersitepackages() if site.ENABLE_USER_SITE else ''\n"
           "p=[sys.prefix,sys.base_prefix,sys.exec_prefix,os.path.dirname(os.path.realpath(sys.executable))]"
           "+list(site.getsitepackages())+[x for x in sys.path if x.endswith(('site-packages','dist-packages','.zip'))]\n"
           "print(json.dumps([p,u,site.getuserbase() if u else '']))")


def _py_info_here():
    import site
    u = site.getusersitepackages() if site.ENABLE_USER_SITE else ""
    p = [sys.prefix, sys.base_prefix, sys.exec_prefix, os.path.dirname(os.path.realpath(sys.executable))]
    p += list(site.getsitepackages()) + [x for x in sys.path if x.endswith(("site-packages", "dist-packages", ".zip"))]
    return [p, u, site.getuserbase() if u else ""]


def python_roots(py=None):
    """Папки самого Python (prefix, site-packages, пользовательские пакеты, папка программы) -> (список, PYTHONUSERBASE).
    Их коду задачи можно читать, даже если они в домашней папке; про чужой Python спрашиваем его самого (один раз)."""
    py = str(py or sys.executable)
    if py in _roots_cache:
        return _roots_cache[py]
    try:
        if os.path.realpath(py) == os.path.realpath(sys.executable):
            got = _py_info_here()
        else:
            r = subprocess.run([py, "-I", "-c", PY_INFO], capture_output=True, text=True, timeout=30)
            got = json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        got = [[sys.prefix, sys.base_prefix, sys.exec_prefix], "", ""]
    paths, usite, ubase = got
    if usite and os.path.isdir(usite):
        paths.append(usite)
    else:
        ubase = ""
    h, priv = home(), private_paths()
    out = []
    for x in paths:
        if not x:
            continue
        p = _real(x)
        # слишком широкое (сама домашняя папка, корень, папка, внутри которой личное) — не открываем
        if (str(p) in SYSTEM_TOP and str(p) not in ("/usr", "/opt")) or _under(h, p) or any(_under(q, p) for q in priv):
            continue
        if p.exists() and p not in out:
            out.append(p)
    _roots_cache[py] = (out, ubase)
    return _roots_cache[py]


def policy(root, grants=(), hide=(), protect=(), net=False, python=None, extra_tmp=None, tools=()):
    """Правила для охраны, Landlock и bwrap: w — запись, r — данные человеком папки (чтение), c — Python и программы
    (чтение), p — личное, h — «личные зоны» (домашняя папка, папка ассистента): в них читать только w/r/c, nw — служебные
    файлы задачи (их ведёт Dewiar; писать нельзя), x — личное и зоны внутри данных папок (закрыть поверх них, S1)."""
    root = _real(root)
    w = [root] + ([_real(extra_tmp)] if extra_tmp else [])
    croots, ubase = python_roots(python)
    c = list(croots) + [_real(x) for x in tools if x]
    zones = [home()] + [_real(x) for x in hide if x]
    # зона не может быть системной папкой (/, /usr…), но домашняя папка /root или /home/… — зона (у root HOME=/root)
    zones = [z for z in dict.fromkeys(zones) if str(z) not in SYSTEM_TOP or str(z) in ("/root", "/home")]
    gs = [_real(g) for g in grants]
    priv = private_paths()
    # личное и зоны (папка ассистента), лежащие внутри данных папок, — закрываются поверх них; папка задачи (даже если она
    # внутри закрытой зоны) открывается после
    inside = [q for q in dict.fromkeys(priv + zones) if any(_under(q, g) and not _under(g, q) for g in gs) and not _under(q, root)]
    return {"w": [str(x) for x in w], "r": [str(g) for g in gs], "c": [str(x) for x in dict.fromkeys(c)],
            "p": [str(x) for x in priv], "h": [str(z) for z in zones], "x": [str(x) for x in inside],
            "nw": [str(root / n) for n in protect], "net": bool(net), "ubase": ubase}


# ---------- охрана внутри Python (guard; в landlock — вдобавок) ----------
# sitecustomize.py во временной папке Dewiar (вне папки задачи — код задачи её не перепишет). Python сам загружает его при
# старте (PYTHONPATH), до кода задачи. Крючок аудита снять нельзя; дочерние Python получают ту же охрану (то же окружение).
# Правила — неизменяемые кортежи, флага «внутри крючка» нет вовсе (крючок не порождает событий, кроме чтения /proc — оно
# проверяется им же и не зацикливается), dir_fd и ATTACH в SQLite закрыты. Это затрудняет простые обходы, но Python —
# не песочница: охрана — от ошибок, не от взлома.

GUARD = r'''
import json as _j, os as _o, re as _re, shutil as _sh, socket as _sk, sys as _s, ipaddress as _ip


def _dewiar_guard():
    raw = _o.environ.get("DEWIAR_SBX") or ""
    try:
        C = _j.loads(raw)
    except Exception:
        return
    sep, nc = _o.sep, _o.path.normcase
    alt = _o.altsep or ""

    def real(p):
        return nc(_o.path.realpath(p))

    gdir = real(_o.path.dirname(_o.path.abspath(__file__)))
    W, R, K, P, H, NW, X = (tuple(real(x) for x in C.get(k) or ()) for k in ("w", "r", "c", "p", "h", "nw", "x"))
    NET, PROCS, ME = bool(C.get("net")), bool(C.get("procs")), _o.getpid()
    # у каждой программы — свои ключи, которые запускают другое, пишут куда угодно или читают список путей из файла
    # (сравнение — с учётом регистра: у ffmpeg -i — вход, у tar -I — запуск программы)
    BAD = {"tar": ("-P", "--absolute-names", "-T", "--files-from", "-I", "--use-compress-program", "--to-command",
                   "--checkpoint-action", "--info-script", "-F", "--new-volume-script", "--rmt-command", "--rsh-command"),
           "pandoc": ("-F", "--filter", "-L", "--lua-filter"),
           "zip": ("-TT", "--unzip-command", "-@"),
           "gs": ("-dNOSAFER", "-dDELAYSAFER", "-dNOSAFETY"), "gswin64c": ("-dNOSAFER", "-dDELAYSAFER", "-dNOSAFETY")}
    BAD_PFX = ("macro:", "vnd.sun.star.script:", "msl:", "ephemeral:", "@", "|")
    TOOLS = frozenset({"ffmpeg", "ffprobe", "soffice", "libreoffice", "pandoc", "magick", "convert", "pdftotext", "pdftoppm",
                       "pdfinfo", "pdfimages", "tesseract", "gs", "gswin64c", "unzip", "zip", "7z", "7za", "tar", "gzip",
                       "gunzip", "xz", "qpdf", "mutool", "wkhtmltopdf", "rsvg-convert", "cwebp", "optipng", "lame", "sox"})
    BAD_SYMS = frozenset({"open", "open64", "openat", "openat64", "openat2", "creat", "creat64", "fopen", "fopen64", "freopen",
                          "system", "popen", "execve", "execv", "execvp", "execvpe", "execl", "execlp", "execle", "fexecve",
                          "posix_spawn", "posix_spawnp", "fork", "vfork", "clone", "clone3", "syscall", "socket", "connect",
                          "unlink", "unlinkat", "rename", "renameat", "renameat2", "rmdir", "mkdir", "mkdirat", "chmod",
                          "fchmodat", "symlink", "symlinkat", "link", "linkat", "truncate", "ptrace", "dlopen", "prctl",
                          "CreateFileW", "CreateFileA", "CreateProcessW", "CreateProcessA", "ShellExecuteW", "ShellExecuteA",
                          "WinExec", "DeleteFileW", "MoveFileExW", "CopyFileW", "NtCreateFile", "LoadLibraryW", "LoadLibraryA",
                          "LoadLibraryExW"})
    SECRET = ("credentials.json", "provision.json", "config.php", "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")
    PROC_RX = _re.compile(r"/proc/(\d+)(?:/|$)")
    def under(p, roots):
        for r in roots:
            if p == r or p.startswith(r.rstrip(sep) + sep):
                return True
        return False

    SID = _o.getsid(0) if hasattr(_o, "getsid") else None

    def mine(pid):
        """Свой процесс: этот же или из той же сессии (сессию заводит Dewiar на каждый запуск). Без чтения файлов —
        крючок не порождает своих событий."""
        try:
            return int(pid) == ME or (SID is not None and _o.getsid(int(pid)) == SID)
        except Exception:
            return False

    def can_read(p):
        if under(p, W):
            return True
        b = _o.path.basename(p)
        if b == ".env" or b.startswith(".env.") or b in SECRET:
            return False
        m = PROC_RX.match(p)
        if m and not mine(m.group(1)):        # окружение и память чужих процессов (в том числе самого Dewiar)
            return False
        if under(p, X):                       # личное и папка ассистента внутри данных папок (S1)
            return False
        if under(p, P):                       # личное: только если человек дал задаче саму эту папку (или внутри)
            return under(p, tuple(g for g in R + K if under(g, P)))
        if under(p, R) or under(p, K) or p == gdir or p.startswith(gdir + sep):
            return True
        return not under(p, H)

    def can_write(p):
        return under(p, W) and not under(p, NW)

    def deny(msg):
        raise PermissionError("Dewiar (песочница задачи): " + msg)

    def path_of(x, base=None):
        if isinstance(x, int) or x is None:
            return None
        try:
            x = _o.fsdecode(x)
        except Exception:
            return None
        if base and not _o.path.isabs(x):
            x = _o.path.join(base, x)
        return real(x)

    def chk_r(x, base=None):
        p = path_of(x, base)
        if p is not None and not can_read(p):
            deny(f"нет доступа к «{x}» — это личные данные человека вне папки задачи. Как исправить: работай с файлами "
                 "в папке задачи; если нужна папка человека — попроси его дать её задаче")

    def chk_w(x, base=None):
        p = path_of(x, base)
        if p is not None and not can_write(p):
            if under(p, NW):
                deny(f"«{x}» — служебный файл задачи, его ведёт Dewiar. Результаты — в outputs/")
            deny(f"писать можно только в папку задачи и во временную папку, а не в «{x}». Как исправить: сохрани в "
                 "outputs/ (относительный путь)")

    def fd_dir(fd):
        """Путь папки по её дескриптору (dir_fd) — чтобы относительный путь проверялся от неё, а не от текущей папки."""
        if fd is None or fd == -1:
            return None
        try:
            return _o.readlink(f"/proc/self/fd/{int(fd)}")
        except Exception:
            deny("dir_fd без известной папки закрыт для кода задачи")

    def resolve(exe, env):
        exe = str(exe)
        if sep in exe or (alt and alt in exe):
            return real(exe)
        w = _sh.which(exe, path=env.get("PATH") if isinstance(env, dict) else None)
        return real(w) if w else None

    ABS = _re.compile(r"(?:^|[\s:=,;'\"(|])((?:/|~|[A-Za-z]:[\\/]|\\\\)[^\s'\",;|)]*)")

    def paths_in(a):
        """Пути в аргументе программы: сам аргумент, части после «=», значение ключа слитно («-C/путь», «-o/путь») и любой
        полный путь внутри строки (concat:/…, movie=/…, file:///…)."""
        cand = [a] + a.split("=")
        if len(a) > 2 and a[0] == "-" and a[1] != "-":
            cand.append(a[2:])
        out = [x for x in cand if sep in x or (alt and alt in x) or x.startswith("~")]
        out += [m.group(1) for m in ABS.finditer(a)]
        return list(dict.fromkeys(out))

    def chk_proc(exe, args, cwd, env):
        if isinstance(args, (str, bytes)):
            args = [args]
        args = [_o.fsdecode(a) if isinstance(a, bytes) else str(a) for a in (args or [])]
        exe = _o.fsdecode(exe) if isinstance(exe, bytes) else (exe or (args[0] if args else ""))
        name = _o.path.basename(str(exe)).lower()
        name = name[:-4] if name.endswith(".exe") else name
        cwd = _o.fsdecode(cwd) if cwd else _o.getcwd()
        e = _o.environ if env is None else env
        if isinstance(e, (list, tuple)):
            e = dict(_o.fsdecode(x).split("=", 1) for x in e if "=" in _o.fsdecode(x))
        e = {(_o.fsdecode(k) if isinstance(k, bytes) else k): (_o.fsdecode(v) if isinstance(v, bytes) else v)
             for k, v in dict(e).items()}
        if not PROCS:                          # landlock: программы заперты ядром, крючок их не перебирает
            return
        where = resolve(exe, e)
        # программа — настоящая, из системы или папок Python, а не переименованная копия в папке задачи
        if where is None or under(where, W):
            deny(f"«{name}» из папки задачи не запускается. Команды — инструментом run_shell")
        if _re.fullmatch(r"python(\d+(\.\d+)?)?w?", name):
            if not (under(where, K) or where == real(_s.executable)):
                deny(f"«{exe}» — не тот Python, что у задачи")
            for a in args[1:]:
                if a in ("-c", "-m") or not a.startswith("-"):
                    break
                if not a.startswith("--") and any(ch in a[1:] for ch in "IES"):
                    deny("Python без охраны (-I, -E, -S) из кода задачи не запускается")
            if e.get("DEWIAR_SBX") != raw or not nc(str(e.get("PYTHONPATH") or "")).startswith(gdir):
                deny("Python с другим окружением из кода задачи не запускается (охрана песочницы)")
            return
        if name in TOOLS:
            bad = BAD.get(name, ())
            for i, a in enumerate(args[1:]):
                a = str(a)
                key = a.split("=", 1)[0]
                cl = _re.match(r"-?([A-Za-z]+)", a) if name == "tar" and (a[:1] == "-" and a[1:2] != "-" or i == 0) else None
                if key in bad or a.lower().startswith(BAD_PFX) \
                        or (cl and any(ch in cl.group(1) for ch in "PTIF")) \
                        or (name == "pandoc" and a[:2] in ("-F", "-L")):
                    deny(f"ключ «{a[:40]}» у {name} пишет или читает вне папки задачи или запускает другие программы — "
                         "из кода задачи так нельзя")
                if not NET and _re.search(r"(?:^|[^a-z])(?:https?|ftps?|rtmps?|rtsp|tcp|udp|tls|srt|sftp|smb)://", a.lower()):
                    deny("сеть для кода этой задачи выключена — адреса в интернете программам не передаются")
                for part in paths_in(a):
                    p = path_of(part, cwd)
                    if p is None:
                        continue
                    if under(p, W) or (can_read(p) and not under(p, R) and not _o.access(p if _o.path.isdir(p) else _o.path.dirname(p) or ".", _o.W_OK)):
                        continue
                    deny(f"программе {name} можно давать только файлы из папки задачи, а не «{part}». Как исправить: "
                         "сначала скопируй нужный файл в папку задачи (Python), потом обрабатывай копию")
            return
        deny(f"«{name}» из кода задачи не запускается: здесь можно запускать только Python и программы-конвертеры "
             "(ffmpeg, pandoc, LibreOffice, ImageMagick, tesseract…). Команды — инструментом run_shell")

    def chk_addr(addr):
        """Сеть дали: не к этому компьютеру и не в домашнюю сеть (там — мост Dewiar, роутер, принтеры)."""
        try:
            ip = _ip.ip_address(str(addr[0]).split("%")[0])
        except Exception:
            return
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified or ip.is_multicast or ip.is_reserved:
            deny("адреса этого компьютера и домашней сети закрыты для кода задачи")

    def deny_ll(code, *a):                     # SQLite: ATTACH открыл бы любой файл в обход охраны
        return 1 if code == 24 else 0

    def dirfd_of(a, i):
        return a[i] if len(a) > i and isinstance(a[i], int) and a[i] not in (-1,) else None

    def hook(ev, a):
        if ev == "open":
            path, mode, flags = a
            if isinstance(path, int):
                return
            wr = (isinstance(mode, str) and any(ch in mode for ch in "wax+")) or (
                isinstance(flags, int) and flags & (_o.O_WRONLY | _o.O_RDWR | _o.O_CREAT | _o.O_TRUNC | _o.O_APPEND))
            (chk_w if wr else chk_r)(path)
        elif ev in ("os.listdir", "os.scandir", "os.listxattr", "os.getxattr", "glob.glob", "glob.glob/2"):
            if a and isinstance(a[0], int):
                return
            chk_r(a[0] if a and a[0] is not None else ".")
        elif ev in ("os.remove", "os.rmdir"):
            chk_w(a[0], fd_dir(dirfd_of(a, 1)))
        elif ev == "os.mkdir":
            chk_w(a[0], fd_dir(dirfd_of(a, 2)))
        elif ev in ("os.chmod", "os.utime", "os.chown"):
            if not isinstance(a[0], int):
                chk_w(a[0], fd_dir(dirfd_of(a, len(a) - 1)))
        elif ev in ("os.truncate", "os.chflags", "os.lchflags", "os.lchmod", "os.mkfifo", "os.mknod", "os.setxattr",
                    "os.removexattr", "shutil.rmtree", "shutil.chown", "tempfile.mkdtemp", "tempfile.mkstemp"):
            if not isinstance(a[0], int):
                chk_w(a[0])
        elif ev in ("os.rename", "os.link"):
            chk_w(a[0], fd_dir(dirfd_of(a, 2)))
            chk_w(a[1], fd_dir(dirfd_of(a, 3)))
        elif ev == "os.symlink":
            chk_w(a[1], fd_dir(dirfd_of(a, 2)))
        elif ev == "sqlite3.connect":
            db = _o.fsdecode(a[0]) if a and isinstance(a[0], (str, bytes)) else ""
            if db.startswith("file:"):
                path = db[5:].split("?", 1)[0]
                if path and path != ":memory:":
                    (chk_r if "mode=ro" in db else chk_w)(path)
            elif db and db != ":memory:":
                chk_w(db)
        elif ev in ("socket.connect", "socket.sendto", "socket.sendmsg", "socket.bind"):
            sock, addr = a[0], a[1] if len(a) > 1 else None
            fam = getattr(sock, "family", None)
            if fam == getattr(_sk, "AF_UNIX", -1):
                if addr is None:
                    return
                s_ = _o.fsdecode(addr) if isinstance(addr, (bytes, str)) else ""
                if not s_ or s_.startswith("\0"):
                    deny("системные сокеты закрыты для кода задачи")
                if ev == "socket.bind":
                    chk_w(s_)
                elif not under(real(s_), W):
                    deny("системные сокеты закрыты для кода задачи")
            elif ev != "socket.bind" and addr is not None:
                if not NET:
                    deny("сеть для кода этой задачи выключена. Как исправить: скачай нужное инструментом download или "
                         "прочитай read_webpage, а код пусть работает с файлами в папке задачи")
                if isinstance(addr, tuple):
                    chk_addr(addr)
        elif ev in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex", "socket.gethostbyaddr",
                    "socket.getnameinfo"):
            if not NET:
                deny("сеть для кода этой задачи выключена")
        elif ev == "subprocess.Popen":
            chk_proc(a[0], a[1], a[2], a[3])
        elif ev == "os.posix_spawn":
            chk_proc(a[0], a[1], None, a[2])
        elif ev == "os.exec":
            chk_proc(a[0], a[1], None, a[2])
        elif ev == "os.spawn":
            chk_proc(a[1], a[2], None, a[3] if len(a) > 3 else None)
        elif ev in ("os.system", "os.startfile", "os.startfile/2", "webbrowser.open"):
            if PROCS:
                deny("командная оболочка и открытие программ из кода задачи закрыты. Команды — инструментом run_shell")
        elif ev in ("os.kill", "os.killpg"):
            pid = a[0]
            if pid not in (ME, 0) and not mine(pid):
                deny("можно останавливать только свои процессы")
        elif ev == "ctypes.dlsym":
            if str(a[1]) in BAD_SYMS:
                deny("прямые вызовы системы через ctypes закрыты для кода задачи")
        elif ev.startswith("winreg.") and ev.split(".", 1)[1] in ("CreateKey", "CreateKeyEx", "DeleteKey", "DeleteKeyEx",
                                                               "DeleteValue", "SetValue", "SetValueEx", "SaveKey",
                                                               "LoadKey", "ConnectRegistry"):
            deny("реестр Windows из кода задачи не меняется")

    # os.open(…, dir_fd=…): событие «open» не говорит, от какой папки путь, — проверяем сами, от папки дескриптора
    try:
        import posix as _px
    except ImportError:
        import nt as _px
    _open = _px.open

    def _guarded_open(path, flags, mode=0o777, *, dir_fd=None):
        if dir_fd is not None and not isinstance(path, int) and not _o.path.isabs(_o.fsdecode(path)):
            base = fd_dir(dir_fd)
            wr = flags & (_o.O_WRONLY | _o.O_RDWR | _o.O_CREAT | _o.O_TRUNC | _o.O_APPEND)
            (chk_w if wr else chk_r)(path, base)
        return _open(path, flags, mode, dir_fd=dir_fd)
    _o.open = _px.open = _guarded_open

    # SQLite: ATTACH открывает файлы мимо событий аудита — у каждого соединения запрещаем его (sqlite3.connect обёрнут,
    # когда модуль загрузится)
    import importlib.machinery as _im

    class _SqlFinder:
        @staticmethod
        def find_spec(name, path=None, target=None):
            if name != "sqlite3":
                return None
            spec = _im.PathFinder.find_spec(name, path)
            if spec is None or spec.loader is None:
                return spec
            ex = spec.loader.exec_module

            def exec_module(mod):
                ex(mod)
                for holder in (mod, getattr(mod, "dbapi2", None)):
                    c = getattr(holder, "connect", None)
                    if c is None:
                        continue

                    def connect(*a, _c=c, **k):
                        con = _c(*a, **k)
                        con.set_authorizer(deny_ll)
                        return con
                    holder.connect = connect
            spec.loader.exec_module = exec_module
            return spec
    _s.meta_path.insert(0, _SqlFinder)

    # прямой fork_exec (multiprocessing, обход subprocess) — та же проверка, что у subprocess.Popen
    try:
        import _posixsubprocess as _ps
        import subprocess as _sp
        _fe = _ps.fork_exec

        def fork_exec(*a, **k):
            chk_proc((a[1] or [None])[0] if len(a) > 1 and a[1] else None, a[0], a[4] if len(a) > 4 else None,
                     a[5] if len(a) > 5 else None)
            return _fe(*a, **k)
        _ps.fork_exec = fork_exec
        if hasattr(_sp, "_fork_exec"):
            _sp._fork_exec = fork_exec
    except ImportError:
        pass
    _s.addaudithook(hook)


_dewiar_guard()
del _dewiar_guard
'''


# ---------- запуск ----------

# первый процесс (вне песочницы): ограничения памяти, размера файлов и числа процессов, затем (landlock) — Landlock, и exec
# в саму команду. Через него, а не preexec_fn: задачи работают в потоках, а preexec_fn в многопоточной программе может
# зависнуть. Аргументы: память, размер файла, процессов, правила Landlock (JSON или «-»), команда.
LAUNCH = r'''
import os, sys, json, resource as r
a = sys.argv
m, f, n, spec, argv = int(a[1]), int(a[2]), int(a[3]), a[4], a[5:]
def lim(k, v):
    try:
        h = r.getrlimit(k)[1]
        v = v if h == r.RLIM_INFINITY else min(v, h)
        r.setrlimit(k, (v, v))
    except (ValueError, OSError):
        pass
lim(r.RLIMIT_CORE, 0)
if f > 0: lim(r.RLIMIT_FSIZE, f)
if m > 0 and hasattr(r, "RLIMIT_DATA"): lim(r.RLIMIT_DATA, m)
if n > 0 and hasattr(r, "RLIMIT_NPROC"): lim(r.RLIMIT_NPROC, n)
if spec != "-":
    import ctypes
    s = json.loads(spec)
    L = ctypes.CDLL(None, use_errno=True)
    L.syscall.restype = ctypes.c_long
    abi = L.syscall(444, None, 0, 1)
    def die(msg):
        sys.stderr.write("Dewiar: песочница Landlock не встала (" + msg + ")\n"); os._exit(126)
    if abi < 1:
        die("нет в ядре")
    fs = (1 << 13) - 1
    if abi >= 2: fs |= 1 << 13
    if abi >= 3: fs |= 1 << 14
    if abi >= 5: fs |= 1 << 15
    FILE = 1 | 2 | 4 | (1 << 14 if abi >= 3 else 0) | (1 << 15 if abi >= 5 else 0)
    RX, RO = 1 | 4 | 8, 4 | 8
    DEV = 2 | 4 | (1 << 14 if abi >= 3 else 0)
    net = 3 if abi >= 4 and not s.get("net") else 0
    scoped = 3 if abi >= 6 else 0
    class Attr(ctypes.Structure):
        _fields_ = [("fs", ctypes.c_uint64), ("net", ctypes.c_uint64), ("scoped", ctypes.c_uint64)]
    class PB(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed", ctypes.c_uint64), ("fd", ctypes.c_int32)]
    at = Attr(fs, net, scoped)
    size = 8 if abi < 4 else (16 if abi < 6 else 24)
    rs = L.syscall(444, ctypes.byref(at), size, 0)
    if rs < 0:
        die("create_ruleset: " + os.strerror(ctypes.get_errno()))
    for kind, rights in (("rx", RX), ("ro", RO), ("rw", fs), ("dev", DEV)):
        for p in s.get(kind) or []:
            try:
                fd = os.open(p, os.O_PATH | os.O_CLOEXEC)
            except OSError:
                continue
            isdir = os.path.isdir(p)
            pb = PB(rights if isdir else rights & FILE, fd)
            if pb.allowed and L.syscall(445, rs, 1, ctypes.byref(pb), 0) < 0:
                die("add_rule " + p + ": " + os.strerror(ctypes.get_errno()))
            os.close(fd)
    if L.prctl(38, 1, 0, 0, 0) != 0:
        die("no_new_privs")
    if L.syscall(446, rs, 0) < 0:
        die("restrict_self: " + os.strerror(ctypes.get_errno()))
    os.close(rs)
# запускатель остаётся родителем кода и «приёмным отцом» (PR_SET_CHILD_SUBREAPER) всего, что код оставит, — в том числе
# ушедшего в свою сессию с чистым окружением: кончилась команда или пришёл SIGTERM — добивает всех потомков и выходит
import ctypes, signal
try:
    ctypes.CDLL(None).prctl(36, 1, 0, 0, 0)
except Exception:
    pass
def kids():
    if os.getpid() == 1:               # первый процесс своего пространства процессов: с ним ядро убьёт всех само
        return set()
    out, todo = set(), ["self"]
    while todo:
        q = todo.pop()
        try:
            tids = os.listdir(f"/proc/{q}/task")
        except OSError:
            continue
        for t in tids:
            try:
                with open(f"/proc/{q}/task/{t}/children") as fh:
                    for c in fh.read().split():
                        if int(c) not in out:
                            out.add(int(c)); todo.append(int(c))
            except OSError:
                pass
    return out
def sweep():
    for _ in range(50):
        ks = kids()
        if not ks:
            break
        for k in ks:
            try: os.kill(k, signal.SIGKILL)
            except OSError: pass
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG)[0] == 0: break
            except ChildProcessError:
                break
class Stop(Exception): pass
def stop(*_): raise Stop()
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
pid = os.fork()
if pid == 0:
    signal.signal(signal.SIGTERM, signal.SIG_DFL); signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        os.execvp(argv[0], argv)
    except OSError as e:
        sys.stderr.write(f"{argv[0]}: {e}\n"); os._exit(127)
code = 1
try:
    while True:
        try:
            got, st = os.waitpid(-1, 0)
        except ChildProcessError:
            break
        if got == pid:
            code = os.waitstatus_to_exitcode(st)
            break
except Stop:
    code = -15
signal.signal(signal.SIGTERM, signal.SIG_IGN)
sweep()
os._exit(code & 0xFF if code >= 0 else 128 - code)
'''


def _split_around(root, holes):
    """Папку root без «дыр» внутри (личное в данной папке) -> список путей, которые можно открыть целиком (Landlock умеет
    только разрешать — поэтому разрешаем всё вокруг дыр, по уровням)."""
    root = Path(root)
    hs = [h for h in holes if _under(h, root)]
    if not hs:
        return [root]
    if any(h == root for h in hs):
        return []
    out = []
    try:
        kids = list(root.iterdir())
    except OSError:
        return []
    for k in kids:
        if k.is_symlink():
            continue
        out += _split_around(k, [h for h in hs if _under(h, k)])
    return out


def _ll_spec(pol, tmp, procs_net):
    """Правила Landlock: система и Python — чтение и запуск; данные папки — чтение (кроме личного внутри); папка задачи
    и временная — всё; /dev — только нужные устройства."""
    rx = [d for d in SYS_DIRS + ("/etc", "/opt", "/sys", "/proc", "/var/cache", "/var/lib/fontconfig", "/run/systemd/resolve")
          if os.path.exists(d)] + list(pol["c"])
    if WIN:
        rx = []
    holes = [Path(x) for x in pol["x"]]
    ro = []
    for g in pol["r"]:
        ro += [str(x) for x in _split_around(Path(g), holes)]
    gd = str(Path(tmp).parent / "guard")
    rx.append(gd)
    rw = list(pol["w"]) + ([str(tmp)] if str(tmp) not in pol["w"] else []) + (["/dev/shm"] if os.path.isdir("/dev/shm") else [])
    dev = [d for d in ("/dev/null", "/dev/zero", "/dev/full", "/dev/random", "/dev/urandom", "/dev/tty") if os.path.exists(d)]
    return {"rx": rx, "ro": ro, "rw": rw, "dev": dev, "net": bool(pol["net"])}


def mem_limit():
    """Потолок памяти кода задачи (байт): DEWIAR_SANDBOX_MEM_MB или 3/4 памяти компьютера, не больше 16 ГБ."""
    v = os.environ.get("DEWIAR_SANDBOX_MEM_MB")
    if v:
        try:
            return max(64, int(v)) << 20
        except ValueError:
            pass
    total = 0
    try:
        if not WIN:
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        total = 0
    if not total:
        return 8 << 30
    return int(min(total * 0.75, 16 << 30))


def nproc_limit():
    """Потолок процессов: RLIMIT_NPROC считает все процессы пользователя — сколько у него уже есть + NPROC_EXTRA."""
    if WIN or not os.path.isdir("/proc"):
        return 0
    uid, n = os.getuid(), 0
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if os.stat(f"/proc/{d}").st_uid == uid:
                    n += 1
            except OSError:
                pass
    return n + NPROC_EXTRA


def child_env(m, tmp, marker, extra=None, ubase=""):
    """Окружение кода задачи: белый список системных переменных + свои (временная папка вместо домашней)."""
    e = {k: v for k, v in os.environ.items() if k.upper() in ENV_KEEP or k.upper().startswith("LC_")}
    t = "/tmp" if m == "bwrap" else str(tmp)
    hm = t + ("/" if m == "bwrap" or not WIN else "\\") + "home"
    e.update(HOME=hm, TMPDIR=t, TEMP=t, TMP=t, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
             MPLBACKEND="Agg", DEWIAR_SBX_RUN=marker, DEWIAR_SANDBOX_MODE=m)
    if WIN:
        e.update(USERPROFILE=hm, APPDATA=os.path.join(hm, "AppData", "Roaming"), LOCALAPPDATA=os.path.join(hm, "AppData", "Local"))
    if ubase:
        e["PYTHONUSERBASE"] = ubase                    # пакеты, поставленные pip --user, остаются видны
    if "PATH" not in e:
        e["PATH"] = os.defpath
    e.update({k: str(v) for k, v in (extra or {}).items() if v is not None})
    return e


def _hide_args(p):
    """Закрыть путь поверх: папку — пустой tmpfs, файл — /dev/null. Ссылку — нельзя (bwrap: «Can't create file»): закрываем
    то, куда она ведёт (если это видно в песочнице, оно в private_paths и придёт сюда само), саму ссылку пропускаем."""
    p = str(p)
    if os.path.islink(p):
        return []
    if os.path.isdir(p):
        return ["--tmpfs", p]
    if os.path.isfile(p):
        return ["--ro-bind", "/dev/null", p]
    return []


def _bwrap_argv(pol, base, root, strict, slirp):
    """Аргументы bwrap. Корень — белый список (S2): ни домашней папки, ни /media, /mnt, /srv, ни сокетов /run."""
    tmp = base / "tmp"
    a = [_bwrap_bin(), "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL"]
    if _probe.get("bwrap_nouserns"):
        a += ["--unshare-user", "--disable-userns"]
    if pol["net"] and not slirp:
        a.append("--share-net")                        # без slirp4netns — сеть компьютера (так и сказано человеку)
    for d in SYS_DIRS:
        if os.path.islink(d):
            a += ["--symlink", os.readlink(d), d]
        elif os.path.isdir(d):
            a += ["--ro-bind", d, d]
    if strict:
        for f in ETC_KEEP:
            a += ["--ro-bind-try", f, f]
    else:
        a += ["--ro-bind", "/etc", "/etc"]
        for f in ETC_HIDE:
            a += _hide_args(f)
        for d in ("/opt", "/sys", "/var/cache/fontconfig", "/var/lib/fontconfig"):
            a += ["--ro-bind-try", d, d]
    a += ["--dev", "/dev", "--tmpfs", "/dev/shm", "--proc", "/proc", "--tmpfs", "/run", "--bind", str(tmp), "/tmp"]
    rc = os.path.realpath("/etc/resolv.conf")
    if pol["net"] and slirp:
        (base / "resolv.conf").write_text("nameserver 10.0.2.3\n", encoding="utf-8")
        a += ["--ro-bind", str(base / "resolv.conf"), "/etc/resolv.conf"]
    elif rc.startswith("/run/") and os.path.exists(rc):
        a += ["--ro-bind", rc, rc]                     # systemd-resolved: файл resolv.conf живёт в /run
    for g in pol["r"]:
        if os.path.isdir(g):
            a += ["--ro-bind", g, g]
    for x in pol["x"]:                                 # S1: личное и папка ассистента внутри данных папок — закрыты поверх
        a += _hide_args(x)
    for c in pol["c"]:
        if os.path.exists(c):
            a += ["--ro-bind", c, c]
    a += ["--bind", str(root), str(root)]
    for n in pol["nw"]:
        if os.path.exists(n) or os.path.islink(n):
            a += ["--ro-bind", n, n] if not os.path.islink(n) else []
    return a + ["--chdir", str(root)]


class Result:
    """Итог запуска: code — код выхода, out/err — вывод (обрезанный), timed_out, cancelled, oversize (папка задачи выросла
    сверх предела), links (удалённые ссылки наружу), mode."""

    def __init__(self, code, out, err, timed_out=False, cancelled=False, m="", oversize=False, links=()):
        self.code, self.out, self.err, self.timed_out, self.cancelled, self.mode = code, out, err, timed_out, cancelled, m
        self.oversize, self.links = oversize, list(links)


def _read_cap(p):
    try:
        size = p.stat().st_size
        with open(p, "rb") as f:
            if size <= OUT_CAP:
                data = f.read()
            else:
                head = f.read(OUT_CAP // 2)
                f.seek(size - OUT_CAP // 2)
                data = head + f"\n…[вывод обрезан: всего {size} байт]…\n".encode() + f.read()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _reap(marker):
    """Linux: добить всё, что вышло из группы процессов (setsid, двойной fork), — по метке запуска в окружении."""
    if WIN or not os.path.isdir("/proc"):
        return 0
    mark, me, n = f"DEWIAR_SBX_RUN={marker}".encode(), os.getpid(), 0
    for _ in range(3):
        hit = 0
        for d in os.listdir("/proc"):
            if not d.isdigit() or int(d) == me:
                continue
            try:
                with open(f"/proc/{d}/environ", "rb") as f:
                    if mark not in f.read():
                        continue
                os.kill(int(d), signal.SIGKILL)
                hit += 1
            except (OSError, ValueError):
                continue
        n += hit
        if not hit:
            break
        time.sleep(0.05)
    return n


def purge_links(root):
    """Ссылки в папке задачи, ведущие наружу (их мог оставить код задачи), — удалить (B2): Dewiar пишет в папку задачи
    вне песочницы и иначе писал бы через них в ~/.bashrc или автозапуск. И особые файлы (FIFO, сокеты, устройства) —
    тоже: чтение такого «файла» вешает Dewiar. -> [удалённые относительные пути]."""
    root = _real(root)
    out = []
    import stat as _st
    for dp, dns, fns in os.walk(root, followlinks=False):
        for n in list(dns) + fns:
            p = Path(dp) / n
            try:
                m = os.lstat(p).st_mode
            except OSError:
                continue
            if not _st.S_ISLNK(m) and not _st.S_ISDIR(m) and not _st.S_ISREG(m):
                # FIFO, сокет, устройство (вторая рецензия): чтение служебного файла-FIFO вешало карточку задачи
                try:
                    os.unlink(p)
                    out.append(str(p.relative_to(root)))
                except OSError:
                    pass
                continue
            if not _st.S_ISLNK(m):
                continue
            try:
                tgt = Path(os.path.realpath(p))
            except (OSError, ValueError):
                tgt = None
            if tgt is None or not _under(tgt, root):
                try:
                    os.unlink(p)
                    out.append(str(p.relative_to(root)))
                except OSError:
                    pass
    return out


def tree_size(root, cap=None, files=None):
    """Размер папки (байт, без перехода по ссылкам); cap — хватит считать, как только больше. files — список из одного числа:
    сюда прибавляется число файлов (и папок)."""
    n = 0
    for dp, dns, fns in os.walk(root, followlinks=False):
        if files is not None:
            files[0] += len(fns) + len(dns)
        for f in fns:
            try:
                n += os.lstat(os.path.join(dp, f)).st_size
            except OSError:
                pass
            if cap is not None and n > cap:
                return n
    return n


def _over(root, tmp, max_bytes):
    """Папка задачи и временная папка запуска вместе — больше max_bytes байт или FILES_MAX файлов (вторая рецензия: /tmp
    песочницы — на диске, и его тоже надо считать)."""
    cnt = [0]
    used = tree_size(root, max_bytes, cnt)
    if used <= max_bytes:
        used += tree_size(tmp, max_bytes - used, cnt)
    return used > max_bytes or cnt[0] > FILES_MAX


# ---------- Windows: Job Object ----------

def _win_job(mem):
    """Задание Windows: убить все процессы при закрытии, потолок памяти, без буфера обмена и чужих окон. -> handle | None."""
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rt", "wt", "ot")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class EXT(ctypes.Structure):
        _fields_ = [("Basic", BASIC), ("Io", IO), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class UI(ctypes.Structure):
        _fields_ = [("UIRestrictionsClass", wintypes.DWORD)]

    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    h = k32.CreateJobObjectW(None, None)
    if not h:
        return None
    info = EXT()
    # KILL_ON_JOB_CLOSE | DIE_ON_UNHANDLED_EXCEPTION | JOB_MEMORY | ACTIVE_PROCESS
    info.Basic.LimitFlags = 0x2000 | 0x400 | (0x200 if mem else 0) | 0x8
    info.Basic.ActiveProcessLimit = 256
    info.JobMemoryLimit = int(mem or 0)
    k32.SetInformationJobObject(h, 9, ctypes.byref(info), ctypes.sizeof(info))      # JobObjectExtendedLimitInformation
    ui = UI(0xFF)                                    # HANDLES|READ/WRITECLIPBOARD|SYSTEMPARAMETERS|DISPLAYSETTINGS|ATOMS|DESKTOP|EXITWINDOWS
    k32.SetInformationJobObject(h, 4, ctypes.byref(ui), ctypes.sizeof(ui))          # JobObjectBasicUIRestrictions
    return h


def _win_assign(job, proc):
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    return bool(k32.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle))))


def _win_resume(pid):
    """Процесс создан приостановленным (CREATE_SUSPENDED) — subprocess закрыл дескриптор его потока, поэтому поток находим
    снимком потоков (CreateToolhelp32Snapshot, документированный путь) и возобновляем. -> сколько потоков возобновили."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class TE32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ThreadID", wintypes.DWORD),
                    ("th32OwnerProcessID", wintypes.DWORD), ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD)]

    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Thread32First.argtypes = k32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(TE32)]
    k32.OpenThread.restype = wintypes.HANDLE
    k32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.ResumeThread.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    snap = k32.CreateToolhelp32Snapshot(0x4, 0)          # TH32CS_SNAPTHREAD
    n = 0
    te = TE32()
    te.dwSize = ctypes.sizeof(TE32)
    ok = k32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            th = k32.OpenThread(0x0002, False, te.th32ThreadID)   # THREAD_SUSPEND_RESUME
            if th:
                k32.ResumeThread(th)
                k32.CloseHandle(th)
                n += 1
        ok = k32.Thread32Next(snap, ctypes.byref(te))
    k32.CloseHandle(snap)
    return n


def _win_close(job, kill=True):
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    if kill:
        k32.TerminateJobObject(job, 1)
    k32.CloseHandle(job)


def _slirp_start(info_r, block_w, base):
    """bwrap сообщил номер процесса песочницы (--info-fd) — подключаем slirp4netns к её сети, ждём «готово» и отпускаем
    песочницу (--block-fd). -> процесс slirp4netns | None."""
    buf = b""
    while b"}" not in buf:
        chunk = os.read(info_r, 4096)
        if not chunk:
            return None
        buf += chunk
    pid = json.loads(buf.decode().split("}")[0] + "}")["child-pid"]
    ready_r, ready_w = os.pipe()
    # --enable-sandbox / --enable-seccomp: сам slirp4netns (он вне песочницы и разбирает пакеты кода) — в своей клетке
    args = [slirp_bin(), "--configure", "--mtu=65520", "--disable-host-loopback", "--enable-sandbox", "--enable-seccomp",
            "--ready-fd", str(ready_w)]
    if os.path.exists(f"/proc/{pid}/ns/user"):
        args.append(f"--userns-path=/proc/{pid}/ns/user")
    sl = subprocess.Popen(args + [str(pid), "tap0"], pass_fds=(ready_w,), stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=open(base / "slirp.log", "wb"))
    os.close(ready_w)
    try:
        import select
        if select.select([ready_r], [], [], 10)[0]:
            os.read(ready_r, 1)
    finally:
        os.close(ready_r)
    os.write(block_w, b"1")
    return sl


def run(argv, root, *, grants=(), net=False, timeout=180, env=None, hide=(), protect=(), strict=False, m=None,
        python=None, cancel=None, tools=(), max_bytes=None):
    """Запустить команду argv в песочнице с текущей папкой root (папка задачи) -> Result. grants — папки, данные человеком
    (только чтение), hide — ещё «личные зоны» (папка ассистента, папки людей в облаке), protect — служебные имена в root
    (только чтение), python — каким Python (для его папок), cancel — threading.Event (остановили задачу — всё гибнет),
    tools — ещё программы (ffmpeg из папки Dewiar), которые можно читать, max_bytes — потолок папки задачи (облако: выросла
    больше — всё останавливается). Нет нужного режима — SandboxError."""
    m = m or mode(strict)
    if not m or (strict and m != "bwrap"):
        raise SandboxError("песочница недоступна (нужен bubblewrap)")
    if m == "bwrap" and not bwrap_ok():
        raise SandboxError("bubblewrap не запускается")
    root = _real(root)
    timeout = max(1, min(TIMEOUT_MAX, int(timeout or 180)))
    base = Path(tempfile.mkdtemp(prefix="dewiar-sbx-"))
    tmp = base / "tmp"
    (tmp / "home").mkdir(parents=True)
    marker = uuid.uuid4().hex
    py = python or sys.executable
    pol = policy(root, grants, hide, protect, net, py, extra_tmp=tmp if m != "bwrap" else None, tools=tools)
    e = child_env(m, tmp, marker, env, pol["ubase"])
    cmd = list(argv)
    spec = "-"
    slirp = bool(m == "bwrap" and net and slirp_bin())
    pass_fds, info_r, block_w = (), None, None
    if m in ("guard", "landlock"):
        g = base / "guard"
        g.mkdir()
        (g / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
        e["PYTHONPATH"] = str(g)
        e["DEWIAR_SBX"] = json.dumps(dict({k: pol[k] for k in ("w", "r", "c", "p", "h", "nw", "x", "net")}, procs=m == "guard"))
        if m == "landlock":
            spec = json.dumps(_ll_spec(pol, tmp, net))
        uf = _unshare_flags()
        if uf:
            # unshare — до Landlock (ему нужна запись в /proc/self/uid_map): внешний запускатель → unshare → внутренний
            # запускатель с Landlock → команда
            inner = [sys.executable, "-I", "-S", "-c", LAUNCH, "0", "0", "0", spec] if spec != "-" else []
            cmd = uf + ([] if net else ["--net"]) + ["--"] + inner + cmd
            spec = "-"
    elif m == "bwrap":
        fdargs = []
        if slirp:
            info_r, info_w = os.pipe()
            block_r, block_w = os.pipe()
            pass_fds = (info_w, block_r)
            fdargs = ["--info-fd", str(info_w), "--block-fd", str(block_r)]
        cmd = _bwrap_argv(pol, base, root, strict, slirp) + fdargs + ["--"] + cmd
    elif m == "off":
        e = dict(os.environ, **{k: str(v) for k, v in (env or {}).items()}, DEWIAR_SBX_RUN=marker)
    if not WIN:
        cmd = [sys.executable, "-I", "-S", "-c", LAUNCH, str(mem_limit() if m != "off" else 0), str(FSIZE if m != "off" else 0),
               str(nproc_limit() if m != "off" else 0), spec] + cmd
    out_f, err_f = open(base / "out", "wb"), open(base / "err", "wb")
    job = sl = None
    timed = stopped = big = False
    p = None
    try:
        if WIN:
            job = _win_job(mem_limit()) if m != "off" else None
            # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED: задание назначается до первой инструкции кода
            p = subprocess.Popen(cmd, cwd=str(root), env=e, stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f,
                                 creationflags=0x08000000 | 0x00000200 | (0x4 if job else 0))
            if job:
                if not _win_assign(job, p):
                    p.kill()
                    raise SandboxError("не вышло поместить код в задание Windows")
                _win_resume(p.pid)
        else:
            p = subprocess.Popen(cmd, cwd=str(root), env=e, stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f,
                                 start_new_session=True, pass_fds=pass_fds)
            if slirp:
                for fd in pass_fds:                         # номера те же в песочнице (pass_fds); у нас — закрыть свои копии
                    os.close(fd)
                try:
                    sl = _slirp_start(info_r, block_w, base)
                finally:
                    os.close(info_r)
                    os.close(block_w)
        end = time.monotonic() + timeout
        next_size = time.monotonic() + 3
        while True:
            try:
                p.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                if cancel is not None and cancel.is_set():
                    stopped = True
                    break
                if time.monotonic() >= end:
                    timed = True
                    break
                if max_bytes and time.monotonic() >= next_size:
                    next_size = time.monotonic() + 3
                    if _over(root, tmp, max_bytes):
                        big = True
                        break
    finally:
        if p is not None:
            if WIN:
                if job:
                    _win_close(job)
                if p.poll() is None:
                    p.kill()
            else:
                if p.poll() is None:                       # запускатель сам добьёт всех потомков (он их «приёмный отец»)
                    try:
                        os.kill(p.pid, signal.SIGTERM)
                        p.wait(timeout=3)
                    except (ProcessLookupError, subprocess.TimeoutExpired):
                        pass
                try:
                    os.killpg(p.pid, signal.SIGKILL)       # вся группа: и то, что код оставил работать в фоне
                except (ProcessLookupError, PermissionError):
                    pass
                _reap(marker)
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        if sl is not None:
            sl.kill()
            sl.wait(timeout=5)
        out_f.close()
        err_f.close()
    if max_bytes and not big and _over(root, tmp, max_bytes):
        big = True
    links = purge_links(root)
    res = Result(p.returncode if p is not None else -1, _read_cap(base / "out"), _read_cap(base / "err"), timed, stopped, m,
                 big, links)
    shutil.rmtree(base, ignore_errors=True)
    return res


def shell_argv(cmd):
    """Команда run_shell -> argv: bash (или sh) в Linux и macOS, PowerShell в Windows."""
    if WIN:
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd]
    sh = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
    return [sh, "-c", cmd]
