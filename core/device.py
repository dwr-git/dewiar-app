"""Мощность этого компьютера: хватит ли её на распознавание речи и голос «у себя».

Думает модель на сервере (облако Dewiar или свой сервер), а на компьютере — слух (GigaAM ≈ 0,5–0,8 ГБ памяти),
голос (Vosk TTS ≈ 0,3–0,6 ГБ) и окна. На слабом компьютере (мало памяти или 2 ядра) включаем «лёгкий режим»:
распознавание — на сервере Dewiar (если есть вход или ключ) или лёгкой моделью Vosk, голос — лёгкий Piper.
Решение и его применение — у вызывающего кода; здесь только замер (measure) и план (light_plan). Чтобы не включать
режим снова после того, как его выключили, запоминается sig — «железо», для которого уже решали (settings device.sig).
Для проверки: DEWIAR_FAKE_RAM_GB, DEWIAR_FAKE_CORES.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

WEAK_RAM_GB = 7.0        # «8 ГБ» Windows показывает как 7,8 — это уже нормально; 6 ГБ и меньше — тяжело
VERY_WEAK_RAM_GB = 3.6   # 4 ГБ и меньше — даже лёгкий режим впритык
WEAK_CORES = 2


def ram_gb():
    """(всего, свободно) в ГБ или (0, 0), если узнать нельзя (на macOS «свободно» — 0)."""
    fake = os.environ.get("DEWIAR_FAKE_RAM_GB")
    if fake:
        return float(fake), float(fake) / 2
    if os.name == "nt":
        try:
            import ctypes

            class M(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            m = M()
            m.len = ctypes.sizeof(M)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return m.total / 2**30, m.avail / 2**30
        except Exception:  # noqa: BLE001
            pass
        return 0.0, 0.0
    try:
        mem = dict(re.findall(r"(\w+):\s+(\d+)", Path("/proc/meminfo").read_text()))
        return int(mem["MemTotal"]) / 1048576, int(mem.get("MemAvailable", 0)) / 1048576
    except (OSError, KeyError, ValueError):
        pass
    try:                                              # macOS: psutil (есть в Dewiar.app) знает и свободную память
        import psutil
        vm = psutil.virtual_memory()
        return vm.total / 2**30, vm.available / 2**30
    except Exception:  # noqa: BLE001
        pass
    try:                                              # macOS без psutil (из исходников) — только объём
        out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3).stdout
        return int(out.strip()) / 2**30, 0.0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0, 0.0


def cores():
    """Логических ядер (с учётом гиперпоточности); 0 — неизвестно."""
    fake = os.environ.get("DEWIAR_FAKE_CORES")
    if fake:
        return int(fake)
    return os.cpu_count() or 0


def measure():
    """{"ram", "free", "cores", "level": ok|weak|very_weak, "why": "…", "sig"} — sig меняется, если поменяли «железо».
    weak — меньше WEAK_RAM_GB памяти или не больше 2 ядер; very_weak — к тому же памяти меньше VERY_WEAK_RAM_GB.
    Неизвестные значения (0) слабостью не считаются."""
    total, free = ram_gb()
    n = cores()
    why = []
    if total and total < WEAK_RAM_GB:
        why.append(f"{total:.0f} ГБ памяти" if total >= 1 else f"{total * 1024:.0f} МБ памяти")
    if n and n <= WEAK_CORES:
        why.append(f"{n} {'ядро' if n == 1 else 'ядра'} процессора")
    level = "ok"
    if why:
        level = "very_weak" if total and total < VERY_WEAK_RAM_GB else "weak"
    return {"ram": round(total, 1), "free": round(free, 1), "cores": n, "level": level, "why": ", ".join(why),
            "sig": f"{round(total)}/{n}"}


def light_plan(stt, tts, cloud_stt=False, account_stt=""):
    """Что поменять для лёгкого режима -> (план, [что сделано словами]). План — не патч настроек, а выбор:
    {"stt": "cloud" (ключ Облака) | "account" (вход в аккаунт) | "vosk", "tts": "piper"}; применяет вызывающий код.
    Трогаем только то, что стоит «по умолчанию» (GigaAM, Vosk TTS): свой сервер распознавания или голоса — не трогаем."""
    patch, done = {}, []
    if (stt or {}).get("engine") == "gigaam":
        if cloud_stt:
            patch["stt"] = "cloud"
            done.append("речь распознаёт сервер Dewiar")
        elif account_stt:
            patch["stt"] = "account"
            done.append("речь распознаёт сервер Dewiar")
        else:
            patch["stt"] = "vosk"
            done.append("распознавание — лёгкой моделью (чуть менее точно)")
    if (tts or {}).get("engine") == "vosk":
        patch["tts"] = "piper"
        done.append("голос — лёгкий Piper")
    return patch, done


# ---------- нехватка памяти прямо сейчас (не «железо», а что открыто) ----------
# Компьютер может быть и мощным, но память занята другими программами (браузер, Java, базы данных): тогда система
# уходит в подкачку, окна Dewiar открываются чёрными и долго, голос запаздывает. pressure() — замер, top_memory() —
# кто больше всех занимает, pressure_text() — понятный совет. Для проверки: DEWIAR_FAKE_PRESSURE="свободно,всего,подкачка%".

NAMES = {"chrome": "Chrome", "chromium": "Chromium", "chromium-browser": "Chromium", "msedge": "Edge", "firefox": "Firefox",
         "isolated web co": "Firefox", "web content": "Firefox", "java": "Java", "javaw": "Java", "milvus": "Milvus", "code": "VS Code",
         "telegram": "Telegram", "telegram-deskto": "Telegram", "slack": "Slack", "discord": "Discord", "zoom": "Zoom",
         "teams": "Teams", "ms-teams": "Teams", "docker": "Docker", "dockerd": "Docker", "containerd": "Docker",
         "postgres": "PostgreSQL", "mysqld": "MySQL", "ollama": "Ollama", "steam": "Steam", "obs": "OBS",
         "gnome-shell": "рабочий стол GNOME", "plasmashell": "рабочий стол KDE", "explorer": "Проводник"}


# Java — это не одна программа: в её командной строке видно, какая (отзыв 11.10: «Java 1,7 ГБ — это наш Dewiar?» — нет,
# Dewiar на Python; чаще это среда разработки, сборка Gradle, игра или сервер).
JAVA_APPS = [(r"android-studio|android studio", "Android Studio"), (r"pycharm", "PyCharm"), (r"idea|intellij", "IntelliJ IDEA"),
             (r"webstorm", "WebStorm"), (r"clion", "CLion"), (r"goland", "GoLand"), (r"rider", "Rider"), (r"datagrip", "DataGrip"),
             (r"jetbrains-toolbox|toolbox", "JetBrains Toolbox"), (r"kotlin.*daemon|kotlincompiledaemon", "сборка Kotlin"),
             (r"gradle", "сборка Gradle"), (r"maven|plexus-classworlds", "сборка Maven"), (r"minecraft|tlauncher|\.minecraft", "Minecraft"),
             (r"elasticsearch", "Elasticsearch"), (r"opensearch", "OpenSearch"), (r"dbeaver", "DBeaver"), (r"eclipse", "Eclipse"),
             (r"netbeans", "NetBeans"), (r"jenkins", "Jenkins"), (r"kafka", "Kafka"), (r"zookeeper", "ZooKeeper"),
             (r"languagetool", "LanguageTool"), (r"libreoffice|soffice", "LibreOffice"), (r"freeplane|freemind", "Freeplane"),
             (r"jdownloader", "JDownloader"), (r"burp", "Burp Suite"), (r"ghidra", "Ghidra"), (r"sonar", "SonarQube"), (r"tomcat|catalina", "Tomcat")]


def java_name(cmdline):
    """Командная строка процесса Java (байты с \\0 или текст) -> «Java (IntelliJ IDEA)», «Java (app.jar)» или «Java»."""
    c = cmdline.decode("utf-8", "replace") if isinstance(cmdline, (bytes, bytearray)) else str(cmdline or "")
    c = c.replace("\0", " ")
    low = c.lower()
    for rx, nm in JAVA_APPS:
        if re.search(rx, low):
            return f"Java ({nm})"
    m = re.search(r"-jar\s+(\S+\.jar)", c)
    if m:
        return f"Java ({Path(m.group(1)).name})"
    return "Java"


def _nice(name):
    n = re.sub(r"\.exe$", "", (name or "").strip(), flags=re.I)
    return NAMES.get(n.lower(), n)


def pressure():
    """-> {"total", "free" (ГБ), "swap" (% занятой подкачки или None — её нет/не узнать), "psi" (доля времени, когда
    программы ждали память, % за минуту, Linux; иначе None), "tight": памяти не хватает}."""
    fake = os.environ.get("DEWIAR_FAKE_PRESSURE")
    if fake:
        free, total, swap, *psi10 = (float(x) for x in fake.split(","))
        return _judge(total, free, swap, None, psi10[0] if psi10 else None)
    if os.name == "nt":
        try:
            import ctypes

            class M(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            m = M()
            m.len = ctypes.sizeof(M)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                commit = 100.0 * (m.tp - m.ap) / m.tp if m.tp else None    # выделено из «память + файл подкачки»
                return _judge(m.total / 2**30, m.avail / 2**30, commit, None)
        except Exception:  # noqa: BLE001
            pass
        return {"total": 0, "free": 0, "swap": None, "psi": None, "psi10": None, "tight": False, "critical": False}
    if sys.platform == "darwin":                      # Mac: psutil (память и подкачка), PSI нет
        try:
            import psutil
            vm, sw = psutil.virtual_memory(), psutil.swap_memory()
            return _judge(vm.total / 2**30, vm.available / 2**30, sw.percent if sw.total else None, None)
        except Exception:  # noqa: BLE001
            return {"total": 0, "free": 0, "swap": None, "psi": None, "psi10": None, "tight": False, "critical": False}
    try:
        mem = {k: int(v) for k, v in re.findall(r"(\w+):\s+(\d+)", Path("/proc/meminfo").read_text())}
    except (OSError, ValueError):
        return {"total": 0, "free": 0, "swap": None, "psi": None, "psi10": None, "tight": False, "critical": False}
    st, sf = mem.get("SwapTotal", 0), mem.get("SwapFree", 0)
    psi = psi10 = None
    try:
        m = re.search(r"^some avg10=([\d.]+) avg60=([\d.]+)", Path("/proc/pressure/memory").read_text(), re.M)
        psi10, psi = (float(m.group(1)), float(m.group(2))) if m else (None, None)
    except (OSError, ValueError):
        pass
    return _judge(mem.get("MemTotal", 0) / 1048576, mem.get("MemAvailable", 0) / 1048576,
                  100.0 * (st - sf) / st if st else None, psi, psi10)


def _judge(total, free, swap, psi, psi10=None):
    """Тесно: свободной памяти меньше 0,7 ГБ (или 7 %) и подкачка почти полна (или её нет) — либо программы заметную
    долю времени ждут память (PSI ≥ 20 % за минуту). Опасно (critical) — ещё чуть-чуть, и рабочий стол замрёт:
    свободно меньше 0,4 ГБ (или 4 %) при почти полной подкачке либо последние 10 с программы ждали память ≥ 40 %
    времени. Тогда разгружаться надо сразу, а не через две проверки."""
    low = total > 0 and free < max(0.7, total * 0.07)
    tight = bool((low and (swap is None or swap >= 50)) or (psi is not None and psi >= 20))
    crit = bool((total > 0 and free < max(0.4, total * 0.04) and (swap is None or swap >= 80))
                or (psi10 is not None and psi10 >= 40))
    return {"total": round(total, 1), "free": round(free, 2), "swap": None if swap is None else round(swap),
            "psi": psi, "psi10": psi10, "tight": tight or crit, "critical": crit}


def top_memory(n=3, skip=()):
    """Кто больше всех занимает память -> [(название, ГБ)], по программам (все окна Chrome — одной строкой)."""
    sums = {}
    if os.name == "nt":
        try:
            import psutil
            for p in psutil.process_iter(["pid", "name", "memory_info"]):
                if p.info["pid"] in skip or not p.info.get("memory_info"):
                    continue
                k = _nice(p.info["name"])
                if k in ("Java", "javaw"):
                    try:
                        k = java_name(" ".join(p.cmdline()))
                    except Exception:  # noqa: BLE001
                        k = "Java"
                if k.lower().startswith("python"):
                    try:
                        k = "Dewiar" if "dewiar" in " ".join(p.cmdline()).lower() else k
                    except Exception:  # noqa: BLE001
                        pass
                sums[k] = sums.get(k, 0) + p.info["memory_info"].rss
        except Exception:  # noqa: BLE001
            return []
    else:
        for d in Path("/proc").iterdir():
            if not d.name.isdigit() or int(d.name) in skip:
                continue
            try:
                txt = (d / "status").read_text()
            except OSError:
                continue
            nm = re.search(r"^Name:\s+(.+)$", txt, re.M)
            rss = re.search(r"^VmRSS:\s+(\d+)", txt, re.M)
            if nm and rss:
                k = _nice(nm.group(1))
                if k == "Java":                              # какая именно программа на Java
                    try:
                        k = java_name((d / "cmdline").read_bytes())
                    except OSError:
                        pass
                if k.lower().startswith("python"):           # сам Dewiar — тоже Python: называем его по имени
                    try:
                        k = "Dewiar" if b"dewiar" in (d / "cmdline").read_bytes().lower() else k
                    except OSError:
                        pass
                sums[k] = sums.get(k, 0) + int(rss.group(1)) * 1024
    top = sorted(sums.items(), key=lambda x: -x[1])[:n]
    return [(k, round(v / 2**30, 1)) for k, v in top if v >= 0.3 * 2**30]


def pressure_text(p, top, light=False, advice=""):
    """Совет человеку: сколько свободно, кто занимает, что сделать."""
    gb = lambda x: f"{x:.1f}".replace(".", ",")     # noqa: E731
    head = f"Свободно {gb(p['free'])} ГБ памяти из {p['total']:.0f}"
    if p.get("swap") is not None and p["swap"] >= 50:
        head += f", подкачка заполнена на {p['swap']}%"
    out = [head + " — поэтому окна открываются медленно, а голос запаздывает."]
    if top:
        out.append("Больше всего занимают: " + ", ".join(f"{k} ({gb(v)} ГБ)" for k, v in top) + ".")
    tips = ["закройте то, чем сейчас не пользуетесь"]
    if not light:
        tips.append("включите лёгкий режим (студия → «Dewiar.pro»)")
    out.append("Что сделать: " + ", или ".join(tips) + ".")
    if advice and "сервер" in advice and not advice.startswith("Речь распознаёт"):
        out.append(advice)
    return " ".join(out)
