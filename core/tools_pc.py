"""Действия модели: компьютер — программы, папки, команды и серверы, звук, система, снимок экрана и камера,
уведомления, питание, умный дом, виджет, удаление файлов."""

import os
import re
import shutil
import subprocess
import time

from datetime import datetime
from pathlib import Path
from tools_base import desktop_env, log, ToolError
import tools_base as base          # DRY, EXAM_LAUNCH, MAC, WIN, launch, macsys, winsys — через основу: проверки подменяют их там


def t_app_update(a, ctx):
    """«Проверь свои обновления» (жалоба №147, 20.10: «сам не проверяет и по просьбе не может»). Проверяет сайт сейчас же;
    новое скачивается и проверяется, в виджете появляется «Доступна версия … — нажмите, чтобы обновить"."""
    eng = ctx.get("engine")
    up = getattr(eng, "updater", None)
    if up is None:
        raise ToolError("обновления отсюда не проверить")
    info = up.check(wait=False)              # 0.82.2: не ждём скачивания — оно идёт в фоне, ход виден в виджете
    st = up.public()
    cur = st.get("current") or ""
    if info and not info.get("path"):
        return (f"Есть новая версия Dewiar {info['version']} (сейчас {cur}); она скачивается — ход виден в виджете. Когда "
                f"скачается, появится плашка «Доступна версия {info['version']} — нажмите, чтобы обновить»: обновление ставит "
                "человек одним нажатием, разговор и настройки сохранятся. Скажи это коротко; сама не ставь.")
    if info:
        return (f"Есть новая версия Dewiar {info['version']} (сейчас {cur}); она уже скачана и проверена. В виджете — плашка "
                f"«Доступна версия {info['version']} — нажмите, чтобы обновить»: обновление ставит человек одним нажатием, "
                "разговор и настройки сохранятся. Скажи это коротко; сама не ставь.")
    if st.get("error"):
        return (f"Проверить обновления сейчас не получилось ({str(st['error'])[:160]}). Установлена {cur}. Скажи коротко и "
                "предложи попробовать позже; в студии — «О программе» → «Проверить обновления».")
    return f"Обновлений нет: установлена последняя версия Dewiar {cur}. Скажи это одной фразой."


def desktop_apps():
    """Все программы из меню -> [{name, ru, keywords, id, path}]. Linux — по файлам .desktop (системные, свои, snap,
    flatpak), Windows — winsys.apps(). DEWIAR_APPS_DIR — тесты: только эта папка .desktop."""
    if base.WIN and not os.environ.get("DEWIAR_APPS_DIR"):
        return base.winsys.apps()
    if base.MAC and not os.environ.get("DEWIAR_APPS_DIR"):
        return base.macsys.apps()
    dirs = [Path("/usr/share/applications"), Path("/usr/local/share/applications"),
            Path.home() / ".local/share/applications", Path("/var/lib/snapd/desktop/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications"]
    extra = os.environ.get("DEWIAR_APPS_DIR")
    if extra:
        dirs = [Path(extra)]
    apps, seen = [], set()
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.desktop")):
            if f.name in seen:
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            sec = txt.split("[Desktop Action")[0]
            if re.search(r"(?m)^(NoDisplay|Hidden)=true", sec) or not re.search(r"(?m)^Type=Application", sec):
                continue
            name = re.search(r"(?m)^Name=(.+)$", sec)
            ru = re.search(r"(?m)^Name\[ru\]=(.+)$", sec)
            kw = re.search(r"(?m)^Keywords(?:\[ru\])?=(.+)$", sec)
            if name:
                seen.add(f.name)
                apps.append({"name": name.group(1).strip(), "ru": ru.group(1).strip() if ru else "",
                             "keywords": kw.group(1).strip() if kw else "", "id": f.stem, "path": str(f)})
    return apps


# как программы называют вслух -> слово из их английского названия
APP_ALIASES = {"телеграм": "telegram", "телеграмм": "telegram", "хром": "chrome", "гугл хром": "chrome",
               "фаерфокс": "firefox", "файрфокс": "firefox", "мозилла": "firefox", "терминал": "terminal",
               "консоль": "terminal", "вскод": "code", "вс код": "code", "визуал студио": "code", "стим": "steam",
               "дискорд": "discord", "спотифай": "spotify", "зум": "zoom", "обс": "obs", "вайбер": "viber",
               "ватсап": "whatsapp", "либреофис": "libreoffice", "ворд": "writer", "эксель": "calc",
               "настройки": "settings", "файлы": "files", "яндекс музыка": "yandex music", "яндекс музыку": "yandex music",
               "яндекс.музыка": "yandex music", "проводник": "files", "гимп": "gimp", "блендер": "blender"}


# транслитерация: «телеграм» -> «telegram», чтобы находить программы без русского названия
_TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m",
               "n", "o", "p", "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def find_app(query, apps):
    """Программа по словам пользователя -> элемент apps | None. Сравниваем с названием, русским названием, id
    и ключевыми словами (как есть, через APP_ALIASES и транслитерацию); ниже похожести 0.72 — не угадываем."""
    import difflib
    q = query.lower().strip()
    variants = {q, APP_ALIASES.get(q, q), "".join(_TR.get(ch, ch) for ch in q)}
    best, score = None, 0.0
    for a in apps:
        names = [a["name"], a["ru"], a["id"].split(".")[-1]] + [k for k in a["keywords"].split(";") if k]
        for n in names:
            n = n.lower().strip()
            if not n:
                continue
            for v in variants:
                s = 1.0 if n == v else 0.9 if (v in n or n in v) and len(v) >= 3 else difflib.SequenceMatcher(None, v, n).ratio()
                if s > score:
                    best, score = a, s
    return best if score >= 0.72 else None


def t_open_app(a, ctx):
    q = (a.get("name") or "").strip()
    apps = desktop_apps()
    app = find_app(q, apps)
    if not app:
        sample = ", ".join(sorted({x["ru"] or x["name"] for x in apps})[:40])
        raise ToolError(f"не нашёл программу «{q}». Установлены, например: {sample}")
    base.launch(["gio", "launch", app["path"]] if shutil.which("gio") or base.DRY or base.MAC else ["gtk-launch", app["id"]])
    if ctx.get("music_app") and re.search(r"yandex.?music|яндекс.?музык", f"{app.get('id', '')} {app['name']} {app['ru']}".lower()):
        ctx["music_app"]("yandex")                  # запомнить: следующие «включи электронную», «играй» — в ней
    return f"Запустил {app['ru'] or app['name']}"


OPEN_ALIASES = {"загрузки": "Downloads", "документы": "Documents", "рабочий стол": "Desktop", "музыка": "Music",
                "изображения": "Pictures", "картинки": "Pictures", "видео": "Videos", "downloads": "Downloads",
                "documents": "Documents", "desktop": "Desktop", "music": "Music", "pictures": "Pictures", "videos": "Videos"}


def _known_dir(name):
    """«Изображения» / Pictures -> папка этого компьютера (на Windows — настоящая, в том числе перенесённая)."""
    if base.WIN:
        cand = [base.winsys.known_folder(name)]
    elif base.MAC:
        cand = [base.macsys.known_folder(name)]
    else:
        ru = {v: k for k, v in OPEN_ALIASES.items() if not k.isascii()}
        cand = [Path.home() / name, Path.home() / ru.get(name, name).capitalize()]
    return next((c for c in cand if c and c.exists()), cand[0])


_LAST_SAVED = {"path": "", "at": 0.0}             # что Лира только что сохранила (снимок) — «открой эту папку»


def t_open_path(a, ctx):
    # экзамен 1.0.5 (open_folder_after_shot573): «сделай снимок» → «открой эту папку» → модель открыла «/». Корень, «~»,
    # «.» или пусто сразу после сохранения — это папка только что сохранённого
    want = str(a.get("path") or "").strip()
    if want in ("", "/", "\\", ".", "~", "./") and _LAST_SAVED["path"] and time.time() - _LAST_SAVED["at"] < 900:
        a = dict(a, path=str(Path(_LAST_SAVED["path"]).parent))
    p = Path(os.path.expanduser((a.get("path") or "~").strip()))
    # №573 (05.11): «сделай снимок» → «сохранил в „Изображения/Снимки экрана“», «открой эту папку» → open_path с тем же
    # «Изображения/Снимки экрана» — «нет такого пути», а модель сказала, что открыла. Первая часть пути — имя папки
    # системы по-русски или по-английски — это она, остальное — внутри неё
    raw = str(a.get("path", "")).strip().strip("/\\")
    raw = re.sub(r"^~[/\\]", "", raw)
    parts = [x for x in re.split(r"[/\\]+", raw) if x]
    if parts and parts[0].lower() in OPEN_ALIASES and not p.exists():
        p = _known_dir(OPEN_ALIASES[parts[0].lower()]).joinpath(*parts[1:])
    if not p.exists() and not base.DRY:
        raise ToolError(f"нет такого пути: {p}")
    base.launch(["xdg-open", str(p)])
    return f"Открыл {p}"


def desktop_notify(text, critical=False, env=None):
    """Всплывающее уведомление: notify-send, а если его нет — напрямую через D-Bus (gdbus из GLib есть почти всегда).
    -> показано ли."""
    if base.WIN:
        return base.winsys.notify(text)
    if base.MAC:
        return base.macsys.notify(text)
    env = env or desktop_env()
    try:
        if shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "-a", "Dewiar"] + (["-u", "critical"] if critical else []) + ["Dewiar", text],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            return True
        if shutil.which("gdbus"):
            hints = "{'urgency': <byte 2>}" if critical else "{}"
            subprocess.Popen(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                              "--object-path", "/org/freedesktop/Notifications",
                              "--method", "org.freedesktop.Notifications.Notify",
                              "Dewiar", "0", "dewiar-assistant", "Dewiar", text, "[]", hints, "-1"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            return True
    except OSError as e:
        log.info("Уведомление не показано: %s", e)
    return False


def human_error(e):
    """Техническая ошибка -> понятная человеку причина (сырые «No module named …», «[Errno 2]» — только в журнал)."""
    t = str(e)
    if isinstance(e, ImportError) or "No module named" in t or "cannot import" in t:
        return "на этом устройстве нет нужной части программы"
    if isinstance(e, PermissionError) or "Permission denied" in t:
        return "нет прав"
    if isinstance(e, FileNotFoundError) or "No such file" in t:
        return "не нашёл нужный файл или программу"
    if isinstance(e, TimeoutError) or "timed out" in t.lower():
        return "не дождался ответа"
    if re.search(r"[A-Za-z]{4,}", t) and not re.search(r"[А-Яа-яЁё]", t):
        return "сбой в системе (подробности — в журнале)"
    return re.sub(r"^(?:не получилось [^:]+:\s*)+", "", t, flags=re.I)


def t_volume(a, ctx):
    """Громкость: percent (0–150, выше 100 — усиление PulseAudio), change (±), mute."""
    if base.DRY:
        base.launch(["volume", a])
        return "Готово"
    if base.WIN:
        if a.get("mute") is None and a.get("percent") is None and a.get("change") is None:
            raise ToolError("укажите percent, change или mute")
        v = base.winsys.volume(percent=a.get("percent"), change=a.get("change"), mute=a.get("mute"))
        if a.get("mute") is not None and a.get("percent") is None and a.get("change") is None:
            return "Звук выключен" if a["mute"] else "Звук включён"
        return f"Громкость {v}%" if v is not None else "Готово"
    if base.MAC:
        if a.get("mute") is None and a.get("percent") is None and a.get("change") is None:
            raise ToolError("укажите percent, change или mute")
        v = base.macsys.volume(percent=a.get("percent"), change=a.get("change"), mute=a.get("mute"))
        if a.get("mute") is not None and a.get("percent") is None and a.get("change") is None:
            return "Звук выключен" if a["mute"] else "Звук включён"
        return f"Громкость {v}%" if v is not None else "Готово"
    if not shutil.which("pactl"):                          # нет pactl — через libpulse напрямую (pulse.py)
        import pulse
        try:
            pulse.volume(percent=None if a.get("percent") is None else int(a["percent"]),
                         change=None if a.get("change") is None else int(a["change"]), mute=a.get("mute"))
        except Exception as e:  # noqa: BLE001
            raise ToolError(human_error(e)) from e
        if a.get("mute") is not None:
            return "Звук выключен" if a["mute"] else "Звук включён"
        if a.get("percent") is not None:
            return f"Громкость {max(0, min(150, int(a['percent'])))}%"
        if a.get("change") is not None:
            return f"Громкость {'+' if int(a['change']) >= 0 else ''}{int(a['change'])}%"
        raise ToolError("укажите percent, change или mute")
    if a.get("mute") is not None:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if a["mute"] else "0"], timeout=4)
        return "Звук выключен" if a["mute"] else "Звук включён"
    if a.get("percent") is not None:
        v = max(0, min(150, int(a["percent"])))
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{v}%"], timeout=4)
        return f"Громкость {v}%"
    if a.get("change") is not None:
        d = int(a["change"])
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{'+' if d >= 0 else '-'}{abs(d)}%"], timeout=4)
        return f"Громкость {'+' if d >= 0 else ''}{d}%"
    raise ToolError("укажите percent, change или mute")


def t_system(a, ctx):
    if base.WIN or base.MAC:
        du = shutil.disk_usage(str(Path.home()))
        return "; ".join((base.winsys if base.WIN else base.macsys).system_parts() + [f"диск: свободно {du.free / 1e9:.0f} из {du.total / 1e9:.0f} ГБ"])
    parts = []
    bats = list(Path("/sys/class/power_supply").glob("BAT*"))
    for b in bats:
        try:
            cap = (b / "capacity").read_text().strip()
            st = (b / "status").read_text().strip()
            parts.append(f"батарея {cap}% ({ {'Charging': 'заряжается', 'Discharging': 'разряжается', 'Full': 'заряжена'}.get(st, st)})")
        except OSError:
            pass
    try:
        load = os.getloadavg()[0]
        parts.append(f"нагрузка процессора {load:.1f} на {os.cpu_count()} ядер")
    except OSError:
        pass
    try:
        mem = dict(re.findall(r"(\w+):\s+(\d+)", Path("/proc/meminfo").read_text()))
        tot, av = int(mem["MemTotal"]) / 1048576, int(mem["MemAvailable"]) / 1048576
        parts.append(f"память: свободно {av:.1f} из {tot:.1f} ГБ")
    except (OSError, KeyError):
        pass
    du = shutil.disk_usage(str(Path.home()))
    parts.append(f"диск: свободно {du.free / 1e9:.0f} из {du.total / 1e9:.0f} ГБ")
    try:                                   # кто занимает память — чтобы можно было предложить закрыть лишнее
        from device import top_memory
        from memcap import dewiar_memory
        top = top_memory(4)
        if top:
            parts.append("больше всего памяти занимают: " + ", ".join(f"{k} {v} ГБ" for k, v in top))
        own = dewiar_memory()
        if own["core"] >= 0.1:
            parts.append(f"сам Dewiar: {own['core'] + own['ui']:.1f} ГБ (ядро {own['core']:.1f}, окна {own['ui']:.1f})")
    except Exception:  # noqa: BLE001
        pass
    return "; ".join(parts)


def t_run_command(a, ctx):
    """Команда терминала в домашней папке (30 с, с sudo — 180 с). Безопасность: guard.check_command отсекает опасное,
    пароль sudo в команде запрещён — sudo переписывается в sudo -A, и пароль спрашивает системное окно (askpass),
    мимо ассистента и журналов."""
    cmd = (a.get("command") or "").strip()
    if not cmd:
        raise ToolError("пустая команда")
    import guard
    v = guard.check_command(cmd)
    if v["level"] == "block":
        raise ToolError(f"защита Dewiar не выполнит это: {v['reason']}. Объясни пользователю, что такое действие опасно "
                        "для компьютера и ассистент его не делает; предложи безопасный вариант (например, удалить "
                        "конкретные файлы в корзину)")
    if PASS_IN_CMD.search(cmd):
        raise ToolError("пароль в команду не вставляю — он остался бы в истории и журналах. Выполни ту же команду с обычным "
                        "sudo (без -S и echo): Dewiar сам покажет пользователю окно для пароля. И не проси пароль в разговоре")
    if base.DRY:
        base.launch(["bash", "-lc", cmd])
        return "выполнено (тест)"
    if base.WIN:
        try:
            r = base.winsys.shell(cmd, timeout=30, cwd=str(Path.home()))
        except subprocess.TimeoutExpired:                  # №267, №302 (пакет 27.10): было необработанное исключение и автоотчёт
            return ("команда не закончилась за 30 с — остановил. Если она долгая (обход сетевого диска, поиск по всему "
                    "диску), сузь её или запусти в фоне: Start-Job { … }")
        out = ((r.stdout or "") + ("\n" + r.stderr if r.stderr else "")).strip()
        return f"код выхода {r.returncode}\n{out[-3000:]}"
    env, timeout = desktop_env(), 30
    if SUDO_AT.search(cmd):                                # пароль — в окне системы, не через ассистента
        cmd = SUDO_AT.sub(r"\1sudo -A ", cmd)
        env = dict(env, SUDO_ASKPASS=askpass_path())
        timeout = 180                                      # человеку нужно время ввести пароль
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=timeout, env=env,
                           cwd=str(Path.home()))
    except subprocess.TimeoutExpired:
        return f"команда не закончилась за {timeout} с — остановил. Если она долгая, запусти её в фоне или раздели на части"
    out = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip()
    # «no askpass program» печатает наш ASKPASS, когда нет ни zenity, ни kdialog, ни ssh-askpass
    if not base.MAC and ("no askpass program" in out or "askpass" in out and r.returncode != 0 and "incorrect password" not in out):
        out += ("\n(Окно для пароля не открылось — нет программы zenity. Попроси пользователя выполнить эту команду в "
                "терминале самому или установить zenity: sudo apt install zenity.)")
    return f"код выхода {r.returncode}\n{out[-3000:]}"


# sudo там, где начинается команда (не внутри аргументов); sudo -A/-S/-n уже со своим способом пароля — не трогаем
SUDO_AT = re.compile(r"(^\s*|[;&|(]\s*|\b(?:then|do|else)\s+)sudo\s+(?!-[ASn]\b)")


# безопасность: пароль в самой команде (echo … | sudo -S, sudo -S <<< …) остался бы в истории и журналах
PASS_IN_CMD = re.compile(r"(echo|printf)\s+[^|;&]*\|\s*sudo\s+(-\w*\s+)*-S\b|sudo\s+(-\w*\s+)*-S\b[^|;&]*<<<", re.S)


# скрипт для SUDO_ASKPASS: системное окно пароля; пароль идёт прямо в sudo, ассистент его не видит
ASKPASS = """#!/bin/sh
# Dewiar: окно пароля администратора для «sudo -A» (пароль идёт прямо в sudo, ассистент его не видит)
T="Dewiar — пароль администратора"
M="Ассистент выполняет команду с правами администратора. Введите пароль вашей учётной записи:"
if command -v zenity >/dev/null 2>&1; then exec zenity --password --title="$T" 2>/dev/null; fi
if command -v kdialog >/dev/null 2>&1; then exec kdialog --title "$T" --password "$M"; fi
if command -v ssh-askpass >/dev/null 2>&1; then exec ssh-askpass "$M"; fi
echo "no askpass program" >&2
exit 1
"""


def askpass_path():
    """Путь к скрипту окна пароля для sudo -A в STATE_DIR: перезаписывается, если отличается, и всегда исполняемый
    (0o700 — только владельцу)."""
    from settings import STATE_DIR
    p = STATE_DIR / "askpass.sh"
    text = base.macsys.ASKPASS if base.MAC else ASKPASS             # Mac: окно пароля — AppleScript (zenity там нет)
    try:
        if not p.exists() or p.read_text() != text:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        os.chmod(p, 0o700)
    except OSError as e:
        log.warning("Окно пароля sudo: %s", e)
    return str(p)


def t_server_run(a, ctx):
    from servers import ServerError
    sv = ctx.get("servers")
    if not (sv and sv.items):
        raise ToolError("серверов нет — добавьте в студии: «Подключение» → «Серверы»")
    try:
        r = sv.run(a.get("server", ""), a.get("command", ""), a.get("timeout") or 60)
    except ServerError as e:
        raise ToolError(str(e)) from e
    return f"Сервер «{r['server']}», код выхода {r['code']}\n{r['output'] or '(вывода нет)'}"


def pictures_dir():
    """Папка «Изображения» пользователя (на Linux — по xdg-user-dir, она может называться по-русски)."""
    if base.WIN:
        return base.winsys.known_folder("Pictures")
    if base.MAC:
        return base.macsys.known_folder("Pictures")
    try:
        d = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=3).stdout.strip()
        if d and Path(d) != Path.home():
            return Path(d)
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.home() / "Pictures"


# 4×3 PNG: экзамен (ядро --server, экрана нет) — снимок «понарошку», чтобы «сделай снимок → открой эту папку» проверялось
_EXAM_PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000040000000308020000003b963991000000144944415478da63d4d03161"
                          "800126062480c201001438008e8d99edf60000000049454e44ae426082")


def t_save_screenshot(a, ctx):
    from eyes import EyesError, capture_screen
    if base.EXAM_LAUNCH:                                   # экзамен 12.11 (open_folder_after_shot573): «инструмента снимка нет»
        base.launch(["screenshot"])
        data = _EXAM_PNG
    else:
        try:
            data = capture_screen(desktop_env())
        except EyesError as e:
            raise ToolError(str(e)) from e
    d = pictures_dir() / "Снимки экрана"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"Снимок экрана {datetime.now():%Y-%m-%d %H-%M-%S}.png"
    if data[:8] != b"\x89PNG\r\n\x1a\n":                   # снимок мог прийти в JPEG (портал, Windows) — сохраним как PNG
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.open(io.BytesIO(data)).save(buf, "PNG")
        data = buf.getvalue()
    f.write_bytes(data)
    _LAST_SAVED.update(path=str(f), at=time.time())
    return f"Снимок экрана сохранён: {f}. Скажи пользователю коротко, что сохранил в «Изображения/Снимки экрана»."


def t_look_screen(a, ctx):
    """-> {"text", "image"}: картинка уходит модели вложением (нужна модель со зрением)."""
    from eyes import EyesError, capture_screen, prepare
    try:
        b64, w, h = prepare(capture_screen(desktop_env()))
    except EyesError as e:
        raise ToolError(str(e)) from e
    return {"text": f"Снимок экрана {w}×{h} приложен. Виджет ассистента на нём не учитывай.", "image": b64}


def _camera_mic_lock(ctx, dev):
    """Идея №165 (08.11): камера и микрофон — одно USB-устройство — на время кадра закрыть поток микрофона (общий
    драйвер иначе «вешает» микрофон до перезапуска), после кадра он откроется сам (Engine.mic_paused)."""
    import contextlib
    eng = ctx.get("engine")
    if eng is None or not hasattr(eng, "mic_paused") or getattr(eng, "muted", False):
        return contextlib.nullcontext()
    try:
        from audio_io import mic_shares_camera, win_default_input
        from eyes import camera_label
        mic = ctx["settings"].get("audio", "input") or ((win_default_input() or (0, ""))[1]) or \
            str((getattr(eng, "status", None) or {}).get("input") or "")
        cam = camera_label(dev)
        if mic_shares_camera(mic, cam):
            log.info("📷 Камера «%s» и микрофон «%s» — одно устройство: микрофон закрываю на время кадра", cam, mic)
            return eng.mic_paused("камера")
    except Exception:  # noqa: BLE001 — сравнение имён не должно мешать снимку
        log.debug("камера и микрофон", exc_info=True)
    return contextlib.nullcontext()


def t_look_camera(a, ctx):
    from eyes import EyesError, capture_camera, prepare
    dev = ctx["settings"].get("eyes", "camera") or ("" if base.WIN else "/dev/video0")
    try:
        with _camera_mic_lock(ctx, dev):
            raw = capture_camera(dev)
        b64, w, h = prepare(raw)
    except EyesError as e:
        raise ToolError(str(e)) from e
    return {"text": f"Кадр с камеры {w}×{h} приложен.", "image": b64}


NOW_PLAYING = "@now_playing"


def _del_paths(a, hooks):
    """Пути delete_files; «@now_playing» — файл песни, что играет из «Моей музыки», из библиотеки (идея №169, рецензия
    0.87: путь не из текста модели)."""
    out = []
    for x in (a or {}).get("paths") or []:
        x = str(x).strip()
        if x == NOW_PLAYING:
            mm = (hooks or {}).get("mymusic")
            p = mm.mine_current_path() if mm is not None else ""
            if not p:
                raise ToolError("сейчас ничего не играет из «Моей музыки» — удалять нечего, так и скажи")
            out.append(p)
        elif x:
            out.append(x)
    return out


def t_delete_files(a, ctx):
    """Удаление только в корзину и только того, что разрешил guard.plan_delete (системное и главные папки — нельзя)."""
    import guard
    from workspace import _locked, LOCKED_MSG
    try:
        plan = guard.plan_delete(_del_paths(a, ctx))
        for it in plan:                              # 05.11: запертые заметки (и папки с ними) — не удаляем
            p = Path(it["path"])
            held = [x for x in ([p] if p.is_file() else p.rglob("*.md") if p.is_dir() else []) if x.suffix.lower() == ".md" and _locked(x)]
            if held:
                raise ToolError(f"«{held[0].stem}» — {LOCKED_MSG}. Снять замок может только человек (значок 🔒 у заметки); "
                                "ничего не удалено — так и скажи")
        mm = ctx.get("mymusic")                      # идея №169: играющая песня — сначала следующая (файл занят)
        if base.DRY:
            base.launch(["trash"] + [x["path"] for x in plan])
            return "В корзине (тест)"
        if mm is not None:
            try:
                mm.mine_release([x["path"] for x in plan])
            except Exception:  # noqa: BLE001
                pass
        done = guard.trash(plan)
        if mm is not None:
            try:
                mm.mine_forget([x["path"] for x in plan])
            except Exception:  # noqa: BLE001
                pass
    except guard.Blocked as e:
        raise ToolError(f"защита Dewiar: {e}. Это удалять нельзя — объясни пользователю почему") from e
    except OSError as e:
        raise ToolError(f"не получилось удалить: {e}") from e
    return "Перемещено в корзину: " + ", ".join(done) + ". Восстановить можно из корзины."


def t_smart_home(a, ctx):
    h = ctx.get("home")                          # homeassistant.Homes: Яндекс и Home Assistant как один дом
    if h is None or not h.connected():
        raise ToolError("умный дом не подключён — студия → «Подключение» → «Умный дом» или «Home Assistant»")
    from smarthome import HomeError
    act, target = a.get("action") or "list", (a.get("target") or "").strip()
    try:
        if act == "list":
            return h.summary()
        if act == "scenario":
            sc = h.scenario(target)
            if not sc:
                raise ToolError(f"нет сценария «{target}». " + h.summary())
            return f"Запущен сценарий «{h.run_scenario(sc)}»"
        devs = h.match(target)
        if not devs:
            raise ToolError(f"не нашёл «{target}». " + h.summary())
        n = h.act(devs, act, a.get("value"))
        return f"Готово: {', '.join(d['name'] for d in devs)} ({n} из {len(devs)} ответили)"
    except HomeError as e:
        raise ToolError(str(e)) from e


# №406 (29.10): «выключи сет в зале» (распознало «сет» вместо «свет») — модель позвала power {"action": "off", "target": "сет в
# зале»}: спросила, выключать ли компьютер, а свет так и горел. Цель — свет, комната, устройство -> не компьютер.
_NOT_PC = re.compile(r"(?<![а-яё])(?:свет|сет|ламп|люстр|торшер|бра|подсветк|гирлянд|розетк|телевизор|тв|кондиционер|обогревател|"
                     r"чайник|пылесос|колонк|штор|жалюз|вентилятор|в\s+(?!компьютер|систем)[а-яё]+е(?![а-яё])|на\s+кухн)", re.I)


def t_power(a, ctx):
    pw = ctx.get("power")
    if pw is None:
        raise ToolError("управление питанием недоступно")
    tgt = " ".join(str(a.get(k) or "") for k in ("target", "device", "what", "room"))
    if tgt.strip() and _NOT_PC.search(tgt):
        raise ToolError("power выключает только этот компьютер, а просят про свет или устройство в комнате — это умный дом: "
                        "вызови smart_home (выключить свет в нужной комнате). Компьютер не трогай.")
    act = a.get("action") or ""
    if act == "cancel":
        was = pw.cancel()
        if ctx.get("engine"):
            ctx["engine"].emit("power", cancelled=True)
        return "Выключение отменено." if was else "Ничего не было запланировано."
    try:
        msg = pw.schedule(act)
    except ValueError as e:
        raise ToolError(str(e)) from e
    if ctx.get("engine"):
        # виджету: показать отсчёт с кнопкой «Отменить»
        ctx["engine"].emit("power", action=act, seconds=60 if act in ("shutdown", "reboot", "logout") else 0)
    return msg


def t_widget(a, ctx):
    """Виджет — в трей или обратно. Обычно «спрячься» ловит _window_cmd без модели; это — когда фраза расслышана
    неточно и её поняла модель (иначе она обещала «ухожу в трей» и оставалась на экране)."""
    eng = ctx.get("engine")
    if eng is None or not getattr(getattr(eng, "bridge", None), "clients", None):
        raise ToolError("виджета на экране нет")
    act = "show" if a.get("action") == "show" else "tray"
    if act == "tray":
        eng._tray_at = __import__("time").monotonic()    # спрятали — не заговаривать первой (Engine._welcome_back)
    eng.emit("window", do=act)
    return "Виджет спрятан в трей: позовут по имени — появлюсь." if act == "tray" else "Виджет снова на экране."
