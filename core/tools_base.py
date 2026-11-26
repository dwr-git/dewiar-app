"""Основа действий модели: окружение рабочего стола (запуск программ, браузер), общие флаги и ошибка инструмента.
Проверки подменяют здесь launch, DRY, EXAM_LAUNCH, WIN, MAC — остальные модули tools_* читают их отсюда (base.X)."""

import json
import logging
import os
import re
import shlex
import subprocess

from pathlib import Path
from settings import MAC, WIN


if WIN:
    import winsys


if MAC:
    import macsys


log = logging.getLogger("dewiar.tools")


DRY = os.environ.get("DEWIAR_DRY_TOOLS")          # тесты: путь к файлу, куда пишутся команды вместо запуска программ


EXAM_LAUNCH = os.environ.get("DEWIAR_EXAM_LAUNCH")   # экзамен: программы и браузер не запускаем, а записываем (core/exam.py)


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Dewiar/0.12" if WIN else
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Dewiar/0.81" if MAC else "Mozilla/5.0 (X11; Linux x86_64) Dewiar/0.8"}


class ToolError(Exception):
    """Ожидаемый отказ инструмента: текст уходит модели результатом («Ошибка: …»), и она пересказывает его человеку.
    Поэтому тексты часто содержат и указание модели, что делать дальше."""
    pass


RADIO = []          # проигрыватель радио ядра (кладёт engine.py) — media_playing() учитывает и своё радио


def desktop_env():
    """Окружение для запуска программ на рабочем столе. Linux: служба systemd --user может стартовать раньше
    графического сеанса и не знать DISPLAY/WAYLAND_DISPLAY и шины D-Bus — берём их у systemctl --user show-environment."""
    env = dict(os.environ)
    env.pop("DEWIAR_BOX", None)
    if WIN or MAC:
        return env
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        try:
            out = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True,
                                 timeout=3).stdout
            for line in out.splitlines():
                k, _, v = line.partition("=")
                if k in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_CURRENT_DESKTOP", "DBUS_SESSION_BUS_ADDRESS"):
                    env.setdefault(k, v)
        except (OSError, subprocess.SubprocessError):
            pass
    return env


def launch(cmd):
    """Запустить программу отсоединённо (она переживёт ассистента). Команды — в терминах Linux (xdg-open, gio launch,
    gtk-launch); на Windows из них берётся последний аргумент и открывается «как двойным щелчком», прочее — ToolError.
    В тестах (DRY) команда только записывается в файл."""
    if DRY or EXAM_LAUNCH:
        with open(DRY or EXAM_LAUNCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(cmd, ensure_ascii=False) + "\n")
        return
    if WIN:
        target = cmd[-1] if cmd[0] in ("xdg-open", "gio", "gtk-launch") else None
        if target is None:
            raise ToolError("это действие недоступно в Windows")
        try:
            winsys.startfile(target)
        except OSError as e:
            raise ToolError(f"не открылось: {e}") from e
        return
    if MAC:                             # xdg-open, gio launch → open; прочие команды Linux на Mac не работают
        mc = macsys.translate(cmd)
        if mc is None:
            raise ToolError("это действие на Mac пока недоступно")
        try:
            subprocess.Popen(mc, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            raise ToolError(f"не открылось: {e}") from e
        return
    import memcap                       # своя коробка systemd: программа не закроется при перезапуске ядра
    subprocess.Popen(memcap.scope_cmd(cmd), env=desktop_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


_BROWSER_NEW_WINDOW = re.compile(r"chrome|chromium|firefox|yandex|brave|opera|vivaldi|edge|librewolf|floorp|waterfox", re.I)


def launch_browser(target):
    """Открыть в БРАУЗЕРЕ адрес или свой .html-файл. Windows: браузер по умолчанию (а не программа, которой отдан .html —
    26.11 это был редактор кода); Linux — browser_cmd (новое окно); Mac — open. Проверки (DRY) — как launch."""
    t = str(target)
    url = t if re.match(r"^[a-z][a-z0-9+.-]*:", t, re.I) and not re.match(r"^[a-z]:[\\/]", t, re.I) else Path(t).resolve().as_uri()
    if DRY or EXAM_LAUNCH or MAC:
        return launch(["xdg-open", t if DRY or EXAM_LAUNCH else url])
    if WIN:
        try:
            winsys.open_in_browser(t)
        except OSError as e:
            raise ToolError(f"не открылось: {e}") from e
        return
    launch(browser_cmd(url))


def browser_cmd(url):
    """Команда открыть адрес в браузере — в НОВОМ окне (отзыв 17.10: «включи смешное видео на YouTube» раз сработало, потом
    «включаю» — и ничего: ролик открывался новой вкладкой в окне браузера, которое было свёрнуто или на другом мониторе).
    Браузер по умолчанию (xdg-settings) из семейства Chrome/Firefox — с --new-window; иначе и в тестах — xdg-open."""
    if DRY or WIN or MAC:
        return ["xdg-open", url]
    try:
        desk = subprocess.run(["xdg-settings", "get", "default-web-browser"], capture_output=True, text=True, timeout=3,
                              env=desktop_env()).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        desk = ""
    if not desk.endswith(".desktop") or not _BROWSER_NEW_WINDOW.search(desk):
        return ["xdg-open", url]
    dirs = [Path.home() / ".local/share/applications", Path("/usr/share/applications"), Path("/usr/local/share/applications"),
            Path("/var/lib/snapd/desktop/applications"), Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications"]
    for d in dirs:
        f = d / desk
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"^Exec=(.+)$", text.split("[Desktop Action", 1)[0], re.M)
        if not m:
            break
        try:
            parts = [x for x in shlex.split(m.group(1)) if not x.startswith("%")]
        except ValueError:
            break
        if parts and not any(x in ("--new-window", "-new-window") for x in parts):
            return parts + ["--new-window", url]
        break
    return ["xdg-open", url]
