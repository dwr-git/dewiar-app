"""Mac: то, что в Linux делают xdg-open, gio, playerctl, pactl, notify-send и /proc, а в Windows — winsys.py.

Только стандартная библиотека и программы, которые есть в любой macOS: open, osascript, say, screencapture, pmset,
ioreg, launchctl. Импортируется лишь на Mac (sys.platform == "darwin"); функции без побочных действий (пути, разбор
вывода, текст plist) проверяются и на Linux — tests/mac1104_test.py.
"""

import logging
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("dewiar.mac")

AGENT_ID = "pro.dewiar.app"                                   # LaunchAgent автозапуска (~/Library/LaunchAgents)
APP_DIRS = ("/Applications", "/Applications/Utilities", "/System/Applications", "/System/Applications/Utilities",
            "~/Applications")
FOLDERS = {"Downloads": "Downloads", "Documents": "Documents", "Desktop": "Desktop", "Music": "Music",
           "Pictures": "Pictures", "Videos": "Movies", "Movies": "Movies"}
SCREEN_HELP = ("на Mac нужно разрешение «Запись экрана»: Системные настройки → Конфиденциальность и безопасность → "
               "Запись экрана и системного аудио → включите Dewiar, затем перезапустите Dewiar")


def osa(script, *args, timeout=8):
    """AppleScript -> (код выхода, вывод). Аргументы — через argv скрипта (никакого склеивания строк в код)."""
    try:
        r = subprocess.run(["osascript", "-e", script, *[str(a) for a in args]], capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)


def startfile(target):
    """Открыть ссылку, файл, папку или программу (.app) тем, чем открывает Finder."""
    subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def translate(cmd):
    """Команда в терминах Linux (xdg-open, gio launch/open, gtk-launch) -> команда Mac (open …) или None."""
    if not cmd:
        return None
    if cmd[0] in ("xdg-open", "gio", "gtk-launch") and len(cmd) >= 2:
        return ["open", str(cmd[-1])]
    if cmd[0] == "open":
        return list(cmd)
    return None


# ---------- программы ----------

def _bundle_name(app):
    """Название программы из её Info.plist и русское — из локализации (InfoPlist.loctable или ru.lproj). -> (имя, ru)."""
    name, ru = app.stem, ""
    try:
        info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
        name = str(info.get("CFBundleDisplayName") or info.get("CFBundleName") or name)
    except Exception:  # noqa: BLE001 — нет или битый Info.plist: имя папки
        info = {}
    res = app / "Contents" / "Resources"
    try:
        lt = res / "InfoPlist.loctable"
        if lt.is_file():
            d = plistlib.loads(lt.read_bytes()).get("ru") or {}
            ru = str(d.get("CFBundleDisplayName") or d.get("CFBundleName") or "")
        if not ru:
            f = res / "ru.lproj" / "InfoPlist.strings"
            if f.is_file():
                raw = f.read_bytes()
                try:
                    d = plistlib.loads(raw)
                    ru = str(d.get("CFBundleDisplayName") or d.get("CFBundleName") or "")
                except Exception:  # noqa: BLE001 — старый текстовый формат "ключ" = "значение";
                    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")
                    m = re.search(r'"?CFBundle(?:Display)?Name"?\s*=\s*"([^"]+)"', text)
                    ru = m.group(1) if m else ""
    except Exception:  # noqa: BLE001
        pass
    return name, ru if ru != name else ""


def apps(dirs=APP_DIRS):
    """Программы из «Программ» (свои, системные, «Утилиты»): [{"name", "ru", "keywords", "id", "path"}] — тот же
    формат, что у списка .desktop в Linux. id — идентификатор пакета (com.apple.Notes) или имя."""
    out, seen = [], set()
    for d in dirs:
        root = Path(os.path.expanduser(d))
        if not root.is_dir():
            continue
        for app in sorted(root.glob("*.app")):
            if app.name in seen:
                continue
            seen.add(app.name)
            name, ru = _bundle_name(app)
            try:
                bid = str(plistlib.loads((app / "Contents" / "Info.plist").read_bytes()).get("CFBundleIdentifier") or "")
            except Exception:  # noqa: BLE001
                bid = ""
            out.append({"name": name, "ru": ru, "keywords": app.stem if app.stem != name else "", "id": bid or app.stem,
                        "path": str(app)})
    return out


def known_folder(alias):
    """Загрузки, Документы, Рабочий стол… -> папка (на Mac названия папок английские, Finder показывает их по-русски)."""
    return Path.home() / FOLDERS.get(alias, alias)


# ---------- звук и музыка ----------

def volume(percent=None, change=None, mute=None):
    """Громкость системы (0–100) через AppleScript. -> новая громкость или None."""
    if mute is not None:
        osa(f"set volume output muted {'true' if mute else 'false'}")
    if percent is not None:
        v = max(0, min(100, int(percent)))
        osa(f"set volume output volume {v}")
        return v
    if change is not None:
        rc, out = osa("output volume of (get volume settings)")
        cur = int(out) if rc == 0 and out.isdigit() else 50
        v = max(0, min(100, cur + int(change)))
        osa(f"set volume output volume {v}")
        return v
    return None


MEDIA_VERBS = {"play": "play", "pause": "pause", "play_pause": "playpause", "next": "next track",
               "previous": "previous track", "stop": "pause"}


def media_script(app, action):
    """AppleScript: команда плееру app (Music, Spotify), только если он уже запущен (иначе — пустой ответ)."""
    verb = MEDIA_VERBS[action]
    return (f'if application "{app}" is running then\n'
            f'  tell application "{app}" to {verb}\n'
            f'  return "{app}"\n'
            f'end if\nreturn ""')


def media(action, prefer=""):
    """Играть, пауза, следующий трек — тому плееру, что открыт: Spotify, «Музыка» (Apple Music). -> имя плеера или ""
    (ни один не открыт: браузеру с YouTube команды на Mac не отдать)."""
    order = ["Spotify", "Music"]
    if prefer == "spotify":
        order = ["Spotify", "Music"]
    for app in order:
        rc, out = osa(media_script(app, action), timeout=6)
        if rc == 0 and out:
            return out
    return ""


# ---------- уведомления, система ----------

def notify(text, title="Dewiar"):
    """Всплывающее уведомление (Центр уведомлений). -> показано ли."""
    rc, _ = osa("on run argv\n display notification (item 1 of argv) with title (item 2 of argv)\nend run",
                str(text)[:400], title, timeout=5)
    return rc == 0


def parse_batt(out):
    """Вывод `pmset -g batt` -> «батарея 84% (заряжается)» или ""."""
    m = re.search(r"(\d+)%;\s*([a-zA-Z ]+);", out or "")
    if not m:
        return ""
    st = m.group(2).strip().lower()
    word = {"charging": "заряжается", "discharging": "разряжается", "charged": "заряжена", "finishing charge": "заряжается",
            "ac attached": "от сети"}.get(st, st)
    return f"батарея {m.group(1)}% ({word})"


def system_parts():
    """Батарея, нагрузка, память — словами, как t_system в Linux."""
    parts = []
    try:
        b = parse_batt(subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=4).stdout)
        if b:
            parts.append(b)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        parts.append(f"нагрузка процессора {os.getloadavg()[0]:.1f} на {os.cpu_count()} ядер")
    except OSError:
        pass
    try:
        import psutil
        vm = psutil.virtual_memory()
        parts.append(f"память: свободно {vm.available / 2 ** 30:.1f} из {vm.total / 2 ** 30:.1f} ГБ")
    except Exception:  # noqa: BLE001
        pass
    return parts


def idle_seconds():
    """Сколько секунд не трогали мышь и клавиатуру (HIDIdleTime из ioreg). None — не узнали."""
    try:
        out = subprocess.run(["ioreg", "-c", "IOHIDSystem", "-d", "4"], capture_output=True, text=True, timeout=4).stdout
        m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
        return int(m.group(1)) / 1e9 if m else None
    except (OSError, subprocess.SubprocessError):
        return None


# ---------- экран ----------

def screen_allowed(ask=True):
    """Разрешена ли «Запись экрана» (без неё screencapture снимает только обои). ask — попросить разрешение (macOS
    покажет окно один раз). None — не узнать (нет Quartz)."""
    try:
        import Quartz
        if Quartz.CGPreflightScreenCaptureAccess():
            return True
        if ask:
            Quartz.CGRequestScreenCaptureAccess()
        return False
    except Exception:  # noqa: BLE001
        return None


def screenshot():
    """Снимок всего экрана -> байты PNG (screencapture -x: без звука затвора). Нет разрешения — RuntimeError со словами,
    где его включить."""
    if screen_allowed() is False:
        raise RuntimeError(SCREEN_HELP)
    d = tempfile.mkdtemp()
    f = Path(d) / "screen.png"
    try:
        r = subprocess.run(["screencapture", "-x", "-t", "png", str(f)], capture_output=True, text=True, timeout=20)
        if r.returncode != 0 or not f.is_file():
            raise RuntimeError("screencapture: " + ((r.stderr or "").strip() or f"код {r.returncode}"))
        return f.read_bytes()
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------- голос системы ----------

_SAY_VOICES = None


def say_voices():
    """Русские голоса системы (`say -v ?`): [(имя, язык)] — Milena, Yuri… Пусто — не установлены."""
    global _SAY_VOICES
    if _SAY_VOICES is None:
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        _SAY_VOICES = parse_voices(out)
    return _SAY_VOICES


def parse_voices(out):
    """Вывод `say -v ?` -> [(имя, язык)] только русских голосов («Milena (Enhanced)  ru_RU  # Здравствуйте…»)."""
    res = []
    for line in (out or "").splitlines():
        m = re.match(r"^(.+?)\s{2,}(ru[_-][A-Z]{2})\b", line)
        if m:
            res.append((m.group(1).strip(), m.group(2)))
    return res


MALE = ("yuri", "юрий", "dmitr", "дмитр", "pavel")


def say_cmd(text, out, gender="", speed=1.0):
    """Команда `say` для русского голоса в WAV 22 кГц. -> список аргументов или None (русского голоса нет)."""
    vs = [v for v, _ in say_voices()]
    if not vs:
        return None
    male = [v for v in vs if any(w in v.lower() for w in MALE)]
    female = [v for v in vs if v not in male]
    pick = (male or vs) if gender == "male" else (female or vs)
    return ["say", "-v", pick[0], "-r", str(int(185 * float(speed or 1.0))), "-o", str(out),
            "--file-format=WAVE", "--data-format=LEI16@22050", text]


# ---------- автозапуск ----------

def agent_path(home=None):
    return Path(home or Path.home()) / "Library" / "LaunchAgents" / f"{AGENT_ID}.plist"


def agent_plist(bundle):
    """LaunchAgent: при входе в систему открыть Dewiar.app с --autostart (убранный в трей — останется в трее).
    Через `open -a`: macOS запускает приложение как приложение — разрешения микрофона и экрана остаются его."""
    return plistlib.dumps({"Label": AGENT_ID, "ProgramArguments": ["/usr/bin/open", "-g", "-a", str(bundle), "--args", "--autostart"],
                           "RunAtLoad": True, "ProcessType": "Interactive", "LimitLoadToSessionType": "Aqua"})


def autostart_on(home=None):
    return agent_path(home).is_file()


def autostart_set(on, bundle, home=None):
    """Включить / выключить запуск вместе с Mac (файл в ~/Library/LaunchAgents). -> True, если получилось.
    Приложение переместили — тот же вызов поправит путь в файле."""
    p = agent_path(home)
    try:
        if not on:
            p.unlink(missing_ok=True)
            return True
        data = agent_plist(bundle)
        if p.is_file() and p.read_bytes() == data:
            return True
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return True
    except OSError as e:
        log.warning("Автозапуск на Mac: %s", e)
        return False


# ---------- пароль администратора для sudo ----------

ASKPASS = """#!/bin/sh
# Dewiar: окно пароля администратора для «sudo -A» на Mac (пароль идёт прямо в sudo, ассистент его не видит)
exec /usr/bin/osascript -e 'display dialog "Команде нужен пароль администратора этого Mac." default answer "" with hidden answer with title "Dewiar — пароль администратора" with icon caution' -e 'text returned of result'
"""
