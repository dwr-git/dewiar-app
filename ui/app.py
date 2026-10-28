#!/usr/bin/env python3
"""Интерфейс Dewiar: плавающий виджет (hud.html), студия (settings.html), окно напоминания (alarm.html), трей.

    python3 ui/app.py              # виджет
    python3 ui/app.py --settings   # сразу открыть студию
    python3 ui/app.py ФАЙЛ.dewiar | dewiar://connect?…   # студия с импортом настроек / подключением

Отдельный процесс от ядра: если окно на каком-то рабочем столе поведёт себя странно, слушать и отвечать
ассистент всё равно продолжит. Страницы говорят с ядром сами (WebSocket, токен и порт — в адресе страницы,
см. assets/dewiar.js), а с окнами — через класс Api (window.pywebview.api). Окна — pywebview: на Linux GTK +
WebKitGTK (форма окна — X Shape, см. shape_window), на Windows WebView2 (Win32 — в winshell.py).
Здесь же сторожа: версия на диске, главный цикл окон (Linux), запуск ядра и загрузка виджета (Windows).
"""

import argparse
import json
import os
import re
import socket
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "core"))
from settings import SETTINGS_PATH, WS_PORT, ensure_token, migrate_from_cortex  # noqa: E402
from version import VERSION as UI_VERSION  # noqa: E402 — версия, с которой запущен этот процесс

WIN = os.name == "nt"
if WIN:
    import winshell  # noqa: E402
else:
    import fcntl  # noqa: E402

# Два непрозрачных окна: карточка и значок (переключение — set_mode). Скругление — формой окна (X Shape на Linux,
# SetWindowRgn на Windows), тень рисует сама система (GNOME даёт тень непрозрачным окнам без рамки). Прозрачное
# окно не годится: на части систем его полупрозрачные пиксели накапливаются между кадрами.
# Значок-шарик убран (отзыв 17.10: «шарик мелкий, часто не понятно, слушает она или нет… может этот кружочек вообще
# убрать?») — окно одно, карточка; «Спрячься» и «—» прячут в трей. Код формы "mini" и hud.html?mode=mini остаются
# безвредными, но окно значка не создаётся (минус один WebKit — быстрее запуск и меньше памяти).
BASE_SIZES = {"card": (300, 420)}
SIZES = dict(BASE_SIZES)                # под масштаб интерфейса (ui.zoom) — set_zoom_sizes; меняется на месте
TITLES = {"card": "Dewiar", "mini": "Dewiar — значок"}
CARD_RADIUS = 28
ZOOM = [1.0]                            # масштаб интерфейса: студия «Оформление» → «Масштаб», Ctrl + / Ctrl −
CARD_DEFAULT = (300, 420)               # карточка виджета по умолчанию (логические px при масштабе 100 %)
CARD_MIN, CARD_MAX = (280, 360), (640, 1000)   # её можно растянуть за угол (отзыв 19.10) — в этих пределах
TRANSPARENT = [False]                   # Linux с композитором: окно прозрачное, углы скругляет страница — гладко


ABOVE_TITLES = None          # заголовки окон, которые должны быть «поверх всех» (виджет, значок, блокнот) — см. keep_above_guard


def keep_above_guard():
    """Linux, раз в 3 с (GLib): виджет и блокнот — оба «поверх окон». Владелец 24.10: «открыл папку — она перекрыла
    Лиру, но не блокнот; они должны быть на одном уровне». Окно, у которого оконный менеджер снял «поверх» (бывает после
    скрытия в трей и показа, смены вида), поднимаем обратно: снять и снова поставить keep_above — GTK иначе считает,
    что флаг и так стоит, и ничего не шлёт. Фокус не трогаем. -> True (GLib повторит)."""
    global ABOVE_TITLES
    try:
        from gi.repository import Gdk, Gtk
        try:
            from gi.repository import GdkX11
        except Exception:  # noqa: BLE001 — без X11 (чистый Wayland) «поверх» решает композитор: не трогаем
            return False
        if ABOVE_TITLES is None:
            ABOVE_TITLES = {TITLES["card"], TITLES["mini"], PAD_TITLE}
        for gw in Gtk.Window.list_toplevels():
            if gw.get_title() not in ABOVE_TITLES or not gw.get_visible():
                continue
            gdw = gw.get_window()
            if gdw is None or not gw.get_mapped() or not isinstance(gdw, GdkX11.X11Window):
                continue
            if not gdw.get_state() & Gdk.WindowState.ABOVE:
                gw.set_keep_above(False)
                gw.set_keep_above(True)
    except Exception as e:  # noqa: BLE001 — сторож не должен ронять интерфейс
        print(f"поверх окон: {e}", file=sys.stderr, flush=True)
    return True


def relaunch_script(installer_pid, wait_s=10):
    """Сторож обновления (cmd): дождаться конца установщика, подождать wait_s и, если Dewiar так и не запущен заново
    (номер в ui.pid не сменился), запустить его. Установщик сам запускает новую версию (NSIS LaunchApp), но у тестировщика
    14.10 после «Обновить» программа не открылась — сторож страхует. Раньше это был скрытый PowerShell с
    -EncodedCommand — антивирусы (Kaspersky, PDM:Trojan.Win32.Generic) видели в нём вирус и убирали Dewiar (20.10).
    №225 (24.10): и tasklist.exe Kaspersky останавливал вопросом «пытается прочитать защищённый файл»; откажи человек —
    сторож считал установщик законченным и запускал старую версию посреди установки. Теперь без списка процессов:
    перед установщиком программа кладёт метку DW_FLAG (update.run рядом с ui.pid), установщик убирает её в конце
    (dewiar.nsi, «-Завершение» и .onInstFailed). Ждём, пока метка есть, но не дольше ~10 минут.
    Пути — в переменных окружения DW_EXE, DW_APP, DW_PID, DW_FLAG (кириллица и пробелы в имени пользователя не мешают,
    сам сценарий — только латиница). installer_pid — только для имени файла. -> текст сценария."""
    w = int(wait_s) + 1
    return ("@echo off\r\n"
            "set P0=\r\n"
            'if exist "%DW_PID%" set /p P0=<"%DW_PID%"\r\n'
            "set N=0\r\n"
            ":wait\r\n"
            "set /a N+=1\r\n"
            "if %N% GEQ 200 goto done\r\n"
            "ping -n 4 127.0.0.1 >nul\r\n"
            'if exist "%DW_FLAG%" goto wait\r\n'
            ":done\r\n"
            f"ping -n {w} 127.0.0.1 >nul\r\n"
            "set P=\r\n"
            'if exist "%DW_PID%" set /p P=<"%DW_PID%"\r\n'
            'if defined P if not "%P%"=="%P0%" goto end\r\n'
            'start "" "%DW_EXE%" -X utf8 "%DW_APP%"\r\n'
            ":end\r\n"
            '(goto) 2>nul & del "%~f0"\r\n')


def _update_cmd(p, here=None):
    r"""Командная строка тихого обновления Windows. №226 (24.10): «Обновить» ставил новую версию в
    %LOCALAPPDATA%\Programs\Dewiar, даже если Dewiar стоит в другой папке, — передаём установщику ту папку, где
    работаем сейчас (/D=…: у NSIS это последний ключ и без кавычек, даже с пробелами; поэтому строка, а не список)."""
    try:
        here = Path(here) if here else Path(winshell.pythonw()).resolve().parent.parent
    except Exception:  # noqa: BLE001
        here = None
    if here and (here / "app" / "ui" / "app.py").is_file() and '"' not in str(here):
        return f'"{p}" /S /UPDATE /D={here}'
    return [str(p), "/S", "/UPDATE"]


def relaunch_after(installer_pid, inst_dir, exe, app):
    """Запустить сторожа отдельным процессом cmd без окна; сценарий — во временной папке, удаляет себя сам."""
    import tempfile
    from settings import STATE_DIR
    f = Path(tempfile.gettempdir()) / f"dewiar-relaunch-{int(installer_pid)}.cmd"
    f.write_text(relaunch_script(installer_pid), encoding="ascii")
    env = dict(os.environ, DW_EXE=str(exe), DW_APP=str(app), DW_PID=str(STATE_DIR / "ui.pid"), DW_FLAG=str(STATE_DIR / "update.run"))
    subprocess.Popen(["cmd.exe", "/d", "/c", str(f)], env=env, close_fds=True,
                     creationflags=winshell.NO_WINDOW | 0x00000200)       # без окна; своя группа — живёт без нас


def uptime_s():
    """Сколько секунд работает система (Windows — GetTickCount64, Linux — /proc/uptime); не узнали — None."""
    try:
        if WIN:
            import ctypes
            f = ctypes.windll.kernel32.GetTickCount64
            f.restype = ctypes.c_ulonglong
            return f() / 1000.0
        return float(Path("/proc/uptime").read_text().split()[0])
    except Exception:  # noqa: BLE001
        return None


def start_in_tray(uis, args, uptime=None):
    """Начать в трее? Только если человек сам убрал виджет в трей (ui.hud_tray) И программу запустил автозапуск —
    флаг --autostart (Run в реестре Windows, /etc/xdg/autostart в Linux) или запуск в первые 3 минуты после включения
    (старые установки без флага). Запустил сам — значит, хочет видеть виджет (тестировщик 14.10: «после перезагрузки
    без автозапуска открывается свёрнутой»)."""
    if not uis.get("hud_tray") or getattr(args, "settings", False):
        return False
    if getattr(args, "autostart", False):
        return True
    up = uptime_s() if uptime is None else uptime
    return up is not None and up < 180


def zoom_of(v):
    """ui.zoom из настроек -> число 0.7…1.5 (как ui/assets/zoom.js)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 1.0
    return round(min(1.5, max(0.7, v)), 2) if v > 0 else 1.0


def set_card_base(w, h):
    """Свой размер карточки (ui.hud_w, ui.hud_h — логические px при масштабе 100 %) -> BASE_SIZES["card"] в пределах.
    Пусто или мусор — размер по умолчанию. -> (w, h)."""
    try:
        w, h = int(round(float(w))), int(round(float(h)))
    except (TypeError, ValueError):
        w, h = CARD_DEFAULT
    w = max(CARD_MIN[0], min(CARD_MAX[0], w))
    h = max(CARD_MIN[1], min(CARD_MAX[1], h))
    BASE_SIZES["card"] = (w, h)
    return w, h


NVIDIA_PROC = "/proc/driver/nvidia/version"


def nvidia_driver():
    """Загружен ли собственный драйвер NVIDIA (и при гибридной графике тоже)."""
    return os.path.exists(NVIDIA_PROC)


def composited_x11():
    """Можно ли сделать виджет прозрачным окном (гладкие скругления вместо ступенек формы X Shape): X11 с
    композитором (GNOME, KDE, Xfce с compositing). Выключить — ui.hud_smooth: false (студия → «Оформление») или
    DEWIAR_HUD_SOLID=1. №234 (24.10, Альт 11.2, гибридная графика NVIDIA): «GUI вокруг аватара проявляется на долю
    секунды раз в 20–30 секунд… при наведении элементы вспыхивают на один кадр и пропадают» — прозрачное окно на
    драйвере NVIDIA показывало только что перерисованное (портрет), фон и кнопки — лишь при полной перерисовке.
    С драйвером NVIDIA — сплошное окно с формой X Shape, как до прозрачности (углы чуть ступенькой, зато всё видно)."""
    if os.environ.get("DEWIAR_HUD_SOLID") == "1" or ui_settings().get("hud_smooth") is False or nvidia_driver():
        return False
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk
        Gtk.init_check([])
        scr = Gdk.Screen.get_default()
        return bool(scr is not None and scr.is_composited() and scr.get_rgba_visual() is not None)
    except Exception:  # noqa: BLE001
        return False


def set_zoom_sizes(z):
    """Размеры окон виджета под масштаб z (SIZES меняется на месте: на него ссылаются все места). -> менялись ли."""
    ZOOM[0] = zoom_of(z)
    new = {m: (int(round(w * ZOOM[0])), int(round(h * ZOOM[0]))) for m, (w, h) in BASE_SIZES.items()}
    changed = new != SIZES
    SIZES.update(new)
    return changed


def card_r():
    """Скругление карточки под масштаб — как в странице (border-radius × zoom)."""
    return int(round(CARD_RADIUS * ZOOM[0]))
ALARM_TITLE = "Dewiar — напоминание"
CAPTURE_TITLE = "Dewiar — закинуть идею"
CAPTURE_RADIUS = 24
CAPTURE_BAR, CAPTURE_BTNS = 58, 60       # заголовок окна идеи (capture.html, header): высота и место под крестик справа
ALARM_RADIUS = 26
PAD_TITLE = "Dewiar — блокнот"
PAD_W, PAD_MIN_H, PAD_GAP, PAD_RADIUS = 440, 520, 14, 22   # блокнот у виджета (pad.html): ширина, высота не меньше, зазор
PAD_W_MIN, PAD_W_MAX, PAD_H_MIN = 320, 1100, 300   # пределы своего размера листа (растягивают за нижний уголок), px при 100 %
PAD_CLIP = 16                           # «крепления» блокнота к виджету (просьба 20.10: «соединить условными крепежами»): высота


def pad_rects(side, w, h, gap, clips, radius):
    """Форма окна блокнота (физические px): скруглённый лист + два «крепления» поперёк зазора к виджету.
    side "left" — лист слева, крепления справа (к карточке), "right" — наоборот. clips — [(y, высота)]."""
    x0 = 0 if side == "left" else gap
    out = [(x + x0, y, ww, hh) for x, y, ww, hh in _shape_rects("pad", w, h, radius, exact=True)]
    cx = w if side == "left" else 0
    return out + [(cx, int(y), gap, int(ch)) for y, ch in clips]
PROMPTER_TITLE = "Dewiar — суфлёр"
PROMPTER_RADIUS = 24
PROMPTER_BAR, PROMPTER_BTNS = 56, 180   # заголовок суфлёра (prompter.html, header): высота и место под кнопки справа
STUDIO_TITLE = "Dewiar — студия"
STUDIO_RADIUS = 12              # скругление углов студии (своя рамка в Linux)
STUDIO_BAR = 38                 # высота своей полосы заголовка, px — как в settings.html
STUDIO_BTNS = 132               # ширина кнопок «свернуть/развернуть/закрыть» справа на полосе
STUDIO_EDGE = 6                 # толщина края, за который тянут размер
MARGIN = 24                     # отступ виджета от края экрана при первом запуске


def blank_image(img):
    """Снимок окна — ровная тёмная заливка без содержимого? (Windows: WebView2 не отрисовал страницу — комментарии 19.10:
    «оба окна просто чёрные».) img — картинка PIL: почти один цвет (разброс яркости < 1,5) и тёмная."""
    from PIL import ImageStat
    st = ImageStat.Stat(img.convert("L"))
    return st.stddev[0] < 1.5 and st.mean[0] < 60


SOFT_ARGS = "--disable-gpu --disable-gpu-compositing"


def soft_render_env(on):
    """Простая отрисовка окон WebView2 (без видеокарты): чёрные окна на части видеодрайверов, удалённом столе,
    гибридной графике. Включается флагом ui.soft_render — сам (виджет не отрисовался) или из меню значка у часов."""
    cur = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "").replace(SOFT_ARGS, "").strip()
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (cur + " " + SOFT_ARGS).strip() if on else cur
    if not os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"]:
        del os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"]


def ui_settings():
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8")).get("ui", {})
    except (OSError, ValueError):
        return {}


def ui_skin():
    """Тема студии и виджета, как её видит ядро (core/settings.py: «Фирменная» без отметки skin_v2 — это прежнее
    значение по умолчанию, теперь вместо неё «Небесный»), и светлая ли она — для фона окна до загрузки страницы."""
    ui = ui_settings()
    sk = str(ui.get("skin") or "brand")
    if sk == "brand" and not ui.get("skin_v2"):
        sk = "neusky"
    try:
        light = re.search(r'id:\s*"' + re.escape(sk) + r'"[^}]*light:\s*true', (HERE / "assets/skins.js").read_text(encoding="utf-8")) is not None
    except OSError:
        light = False
    return sk, light


def core_alive():
    try:
        with socket.create_connection(("127.0.0.1", WS_PORT), timeout=0.3):
            return True
    except OSError:
        return False


def ensure_core():
    """Поднять ядро, если оно не отвечает на своём порту. Linux: служба systemd dewiar-core; её нет (запуск из
    исходников) — свой процесс с журналом в $XDG_RUNTIME_DIR/dewiar-core.log. Windows: служб нет — отдельный
    процесс без окна (запомнен в CORE_PROC). Ждёт ядро несколько секунд, но не дольше."""
    if core_alive():
        return
    if WIN:
        start_core_win()
        for _ in range(40):                    # первый запуск на Windows — несколько секунд (импорт библиотек)
            if core_alive():
                return
            time.sleep(0.25)
        return
    subprocess.run(["systemctl", "--user", "start", "dewiar-core.service"], capture_output=True)
    for _ in range(10):
        if core_alive():
            return
        time.sleep(0.3)
    if subprocess.run(["systemctl", "--user", "cat", "dewiar-core.service"], capture_output=True).returncode != 0:
        # без службы — те же предосторожности, что у службы: потолок памяти (memcap) и уступчивость (nice 5)
        import memcap
        log = open(Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "dewiar-core.log", "a")
        subprocess.Popen(memcap.scope_cmd([sys.executable, str(ROOT / "core/main.py")], "core", "Dewiar — ядро"),
                         stdout=log, stderr=log, start_new_session=True, preexec_fn=lambda: os.nice(5),
                         env={k: v for k, v in os.environ.items() if k != "DEWIAR_BOX"})


def _core_call(token, cmd, timeout=4):
    """Одна команда ядру по WebSocket (Linux; на Windows — winshell.core_call): hello с токеном, затем {id, cmd}."""
    from websockets.sync.client import connect
    with connect(f"ws://127.0.0.1:{WS_PORT}", open_timeout=timeout, close_timeout=1) as ws:
        ws.send(json.dumps({"cmd": "hello", "token": token}))
        ws.recv(timeout=timeout)
        ws.send(json.dumps({"id": 1, "cmd": cmd, "args": {}}))
        ws.recv(timeout=timeout)


CORE_PROC = []          # Windows: процесс ядра, запущенный этим интерфейсом (сторож видит, если он упал)
CORE_LOG_AT = [0, 0.0]  # Windows: с какого места core.log и с какого времени (time.time) пишет последний запуск ядра
CORE_ERR_RX = re.compile(r"\b(ERROR|CRITICAL)\b|Traceback|\b\w+(Error|Exception):|Ошибка")


def start_core_win():
    """Windows: запустить ядро и запомнить, где в core.log начинаются его строки: объясняя сбой, сторож берёт только
    их (пакет 22.10, №188: после обновления показал «Ядро не запустилось: … explain-error …» — строку списка навыков
    из прошлого запуска, двадцатиминутной давности)."""
    try:
        CORE_LOG_AT[0] = (winshell.log_dir() / "core.log").stat().st_size
    except OSError:
        CORE_LOG_AT[0] = 0
    CORE_LOG_AT[1] = time.time()
    CORE_PROC[:] = [winshell.start_core(ROOT)]
    return CORE_PROC[0]


def core_log_new():
    """Строки core.log, написанные с последнего запуска ядра (журнал успел смениться — весь новый файл)."""
    f = winshell.log_dir() / "core.log"
    try:
        size = f.stat().st_size
        with open(f, "rb") as fh:
            if size >= CORE_LOG_AT[0]:
                fh.seek(CORE_LOG_AT[0])
            return fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def core_fail_reason(lines, fail_path):
    """Почему ядро не поднялось: core.fail этого запуска (не старый), иначе — последняя строка с ошибкой среди новых
    строк журнала (уровень ERROR, Traceback, «…Error:»), а не любое слово error (навык «explain-error»)."""
    try:
        d = json.loads(fail_path.read_text(encoding="utf-8"))
        if float(d.get("time") or 0) >= CORE_LOG_AT[1] - 5 and d.get("error"):
            return str(d["error"])
    except (OSError, ValueError, TypeError):
        pass
    return next((x for x in reversed(lines[-60:]) if CORE_ERR_RX.search(x)), "")


def core_watch(api=None, limit=240, tries=2):
    """Windows: ядро не вышло на связь (упало при запуске или так и не поднялось) — запустить ещё раз, а не вышло —
    понять почему и объяснить по-человечески. Чаще всего это антивирус: убрал файлы в карантин или не даёт загрузить
    библиотеку. Причину берём из core.fail этого запуска, иначе — из новых строк core.log; разбор — core/winav.py.
    Ещё раз (tries раз) — если процесса ядра нет или он завершился, и если он молчит: за 150 с ни строки в журнале
    (№188: после обновления 14 минут не было ни ядра, ни новой попытки — помогла только кнопка «Перезапустить»).
    Блокирует (запускать в потоке): limit — сколько секунд ждать, -> True, если ядро на связи."""
    from settings import STATE_DIR
    t0 = time.monotonic()
    while True:
        if core_alive():
            return True
        proc, waited = (CORE_PROC[0] if CORE_PROC else None), time.monotonic() - t0
        gone = proc is None or proc.poll() is not None
        silent = not gone and waited > 150 and not core_log_new()
        if (gone and waited > 3 or silent) and tries > 0:
            tries -= 1
            print("Ядро " + ("молчит" if silent else "не отвечает") + " — запускаю ещё раз", file=sys.stderr)
            if silent:
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(1)
            start_core_win()
            t0 = time.monotonic()
            continue
        if gone and waited > 3:
            break                                       # ядро завершилось само, и попытки кончились — ждать нечего
        if waited > limit and not (not gone and waited < 600):
            break                                       # процесс жив — грузится (медленный диск, проверка антивирусом): ждём до 10 минут
        time.sleep(2)
    if core_alive():
        return True
    error = core_fail_reason(core_log_new(), STATE_DIR / "core.fail")
    print(f"Ядро не запустилось: {error or 'без ошибки в журнале'}", file=sys.stderr)
    try:
        import winav
        st = winav.status(ROOT)
    except Exception as e:  # noqa: BLE001
        print(f"Проверка антивируса не удалась: {e}", file=sys.stderr)
        st = {}
    if st and winav.looks_blocked(error, st.get("missing")):
        winav.copy_text(st["paths"][0])
        text = "Dewiar не смог запуститься.\n\n" + winav.message(st, error)
        if (st.get("main") or {}).get("kind") == "defender":
            if winshell.ask_yes_no(text + "\n\nДобавить Dewiar в исключения Защитника Windows сейчас?"):
                winav.defender_exclude(st["paths"])
                time.sleep(8)
                if st.get("missing"):
                    winshell.message_box("Готово. Теперь запустите установщик Dewiar ещё раз — он вернёт убранные файлы.")
                else:
                    start_core_win()
                    return core_watch(api, 120, 0) if limit > 120 else False
        else:
            winshell.message_box(text + "\n\nПотом запустите Dewiar снова.", wait=True)
        return False
    winshell.message_box("Ядро Dewiar не запустилось" + (f": {error[:300]}" if error else "") + ".\n\nСделайте, пожалуйста: "
                         "меню «Пуск» → «Dewiar — диагностика» — на рабочем столе появится файл отчёта, пришлите его разработчику.")
    return False


def lock(name):
    """Замок «один экземпляр»: -> держать, пока работаем (Linux — flock на файле, отпускается вместе с процессом;
    Windows — именованный мьютекс в winshell), или None, если экземпляр уже запущен."""
    if WIN:
        return True if winshell.single_instance(name) else None
    path = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / f"dewiar-{name}-{os.getuid()}.lock"
    fh = open(path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None


_UI_HTTP = []


def ui_http_base():
    """http://127.0.0.1:<порт>/ — страницы интерфейса (папка ui) для окон и браузера. Слушает только этот компьютер,
    порт — любой свободный; запускается один раз (поток ui-http), списка файлов папки не отдаёт.
    Типы файлов заданы явно: на Windows mimetypes берёт их из реестра, а там .js бывает text/plain.
    no-store — после обновления окна не должны показывать старые страницы из кэша."""
    if _UI_HTTP:
        return _UI_HTTP[0]
    import functools
    import http.server
    import threading

    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map, **{
            ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
            ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp",
            ".woff2": "font/woff2", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"})

        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def list_directory(self, path):
            self.send_error(404)
            return None

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(HERE)))
    threading.Thread(target=srv.serve_forever, name="ui-http", daemon=True).start()
    _UI_HTTP.append(f"http://127.0.0.1:{srv.server_address[1]}/")
    return _UI_HTTP[0]


def _shape_rects(kind, w, h, radius=None, exact=False):
    """Форма окна прямоугольниками -> [(x, y, ш, в)]: kind "rect" — без скругления, "mini" — круг (полоска в 1 px
    на каждую строку), иначе скруглённый прямоугольник (карточка, напоминание, студия): полоски углов + середина.
    Размеры — в физических пикселях окна."""
    import math
    out = []
    if kind == "rect":
        return [(0, 0, w, h)]
    if kind == "mini":
        r = w / 2
        for y in range(h):
            dy = y + 0.5 - r
            x0 = int(round(r - math.sqrt(max(0.0, r * r - dy * dy))))
            out.append((x0, y, w - 2 * x0, 1))
        return out
    r = radius or card_r()
    if TRANSPARENT[0] and kind != "rect" and not exact:
        # окно прозрачное: углы рисует страница (сглаженно), форма — только чтобы клики в углах шли мимо; её скругление
        # чуть меньше, иначе она срезала бы сглаженный край
        r = max(0, int(r * 0.55))
    for y in range(r):
        dy = r - y - 0.5
        inset = int(round(r - math.sqrt(max(0.0, r * r - dy * dy))))
        out += [(inset, y, w - 2 * inset, 1), (inset, h - 1 - y, w - 2 * inset, 1)]
    out.append((0, r, w, h - 2 * r))
    return out


_XDPY = []


def shape_window(gw, kind, size=None, radius=None, rects=None):
    """Форма окна через расширение SHAPE (libXext, ctypes). Задаётся до показа окна — так её видит GNOME.
    Если окно не X11 (чистый Wayland) — просто остаётся прямоугольным (-> False). size — физические пиксели
    (по умолчанию SIZES[kind]). Своё соединение с X-сервером открываем один раз и держим (_XDPY).
    Вызывать в главном потоке GTK."""
    import ctypes
    import ctypes.util
    import gi
    gi.require_version("GdkX11", "3.0")
    from gi.repository import GdkX11
    gdkw = gw.get_window()
    if not isinstance(gdkw, GdkX11.X11Window):
        return False

    class XRect(ctypes.Structure):
        _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short), ("width", ctypes.c_ushort), ("height", ctypes.c_ushort)]
    x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
    xext = ctypes.CDLL(ctypes.util.find_library("Xext") or "libXext.so.6")
    if not _XDPY:
        x11.XOpenDisplay.restype, x11.XOpenDisplay.argtypes = ctypes.c_void_p, [ctypes.c_char_p]
        d = x11.XOpenDisplay(None)
        if not d:
            return False
        _XDPY.append(d)
    if not rects:
        w, h = size or SIZES[kind]
        rects = _shape_rects(kind, w, h, radius)
    arr = (XRect * len(rects))(*[XRect(*r) for r in rects])
    xext.XShapeCombineRectangles.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                             ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    xext.XShapeCombineRectangles(_XDPY[0], gdkw.get_xid(), 0, 0, 0, arr, len(rects), 0, 0)   # ShapeBounding, ShapeSet
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XFlush(_XDPY[0])
    return True


def _win_clip_set(text):
    """Windows: текст в буфер + пометки для пароля (журнал Win+V и облачный буфер его не сохраняют)."""
    import ctypes
    from ctypes import wintypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    # 64-битные дескрипторы: без argtypes ctypes передаёт их как int — «int too long» (пакет 27.10: копирование в
    # сейфе молча не удавалось, страница копировала сама и через 30 с спрашивала WebView2 «разрешить читать буфер?»)
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.SetClipboardData.restype = wintypes.HANDLE
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u32.OpenClipboard.argtypes = [wintypes.HWND]

    def blob(data):
        h = k32.GlobalAlloc(0x0002, len(data))              # GMEM_MOVEABLE
        ctypes.memmove(k32.GlobalLock(h), data, len(data))
        k32.GlobalUnlock(h)
        return h
    for _ in range(10):
        if u32.OpenClipboard(0):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        u32.EmptyClipboard()
        u32.SetClipboardData(13, blob((text + "\0").encode("utf-16-le")))   # CF_UNICODETEXT
        for fmt, data in (("ExcludeClipboardContentFromMonitorProcessing", b"\0"), ("CanIncludeInClipboardHistory", b"\0\0\0\0"),
                          ("CanUploadToCloudClipboard", b"\0\0\0\0")):
            f = u32.RegisterClipboardFormatW(fmt)
            if f:
                u32.SetClipboardData(f, blob(data))
        return True
    finally:
        u32.CloseClipboard()


def _win_clip_clear_if(text):
    """Windows: в буфере всё ещё этот пароль — стереть; уже другое — не трогать."""
    import ctypes
    from ctypes import wintypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    u32.GetClipboardData.restype = wintypes.HANDLE
    u32.GetClipboardData.argtypes = [wintypes.UINT]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.OpenClipboard.argtypes = [wintypes.HWND]
    if not u32.OpenClipboard(0):
        return
    try:
        h = u32.GetClipboardData(13)
        if h:
            cur = ctypes.wstring_at(k32.GlobalLock(h))
            k32.GlobalUnlock(h)
            if cur == text:
                u32.EmptyClipboard()
    finally:
        u32.CloseClipboard()


class Api:
    """Окна интерфейса и то, что страницам нужно от программы. Методы без «_» страницы вызывают как
    window.pywebview.api.<имя>(…) (hud.html, settings.html, alarm.html) — переименование ломает кнопки там.
    Вызовы приходят из потоков pywebview, поэтому с окнами GTK работаем только через _gtk() / GLib.idle_add."""

    def __init__(self, token):
        self.token = token
        self._hud = None
        self._studio = None
        self.wins = {}
        self.mode = "card"
        self.auto = False
        self.in_tray = False          # виджет убран в трей: появляется сам на имя, напоминание, уведомление
        self.popped = False           # показан ненадолго из трея — после разговора спрячется обратно
        self._tray = None

    def _url(self, page, extra=""):
        # Windows: окно (WebView2 через .NET Uri) и браузер через «открыть файл» теряют «?token=…» у адресов file://
        # и показывают «Файл не найден» — поэтому там страницы отдаёт маленький локальный веб-сервер (только папка ui).
        base = ui_http_base() if WIN or os.environ.get("DEWIAR_UI_HTTP") else None
        return (base + page if base else (HERE / page).as_uri()) + f"?token={self.token}&port={WS_PORT}{extra}"

    # ---------- окна виджета: карточка и значок ----------

    def _gw(self, mode):
        from gi.repository import Gtk
        return next((w for w in Gtk.Window.list_toplevels() if w.get_title() == TITLES[mode]), None)

    def _gtk(self, fn, timeout=3):
        """Выполнить fn() в главном потоке GTK и дождаться результата (не дольше timeout; не успели или ошибка — None)."""
        import threading
        from gi.repository import GLib
        box, done = {}, threading.Event()

        def run():
            try:
                box["r"] = fn()
            except Exception as e:  # noqa: BLE001
                print(f"окно виджета: {e}", file=sys.stderr, flush=True)
            finally:
                done.set()
            return False
        GLib.idle_add(run, priority=GLib.PRIORITY_HIGH_IDLE)
        done.wait(timeout)
        return box.get("r")

    def clip_secret(self, text, sec=30):
        """«Сейф паролей» (0.45): скопировать пароль в буфер обмена и через sec секунд стереть — только если там всё ещё
        он (успели скопировать другое — не трогаем). Windows: пометки «не в журнал буфера» (Win+V) и «не для облачного
        буфера». -> True; не вышло — False (страница скопирует сама и честно скажет, что стирать придётся вручную)."""
        import threading
        text, sec = str(text or ""), max(5, min(300, int(sec or 30)))
        if not text:
            return False
        try:
            if WIN:
                if not _win_clip_set(text):
                    return False
                threading.Timer(sec, lambda: _win_clip_clear_if(text)).start()
                return True

            def put():
                from gi.repository import Gdk, Gtk
                Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
                return True

            def wipe():
                from gi.repository import Gdk, Gtk
                cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                if cb.wait_for_text() == text:
                    cb.set_text("", -1)
                return True
            if not self._gtk(put, timeout=3):
                return False
            threading.Timer(sec, lambda: self._gtk(wipe, timeout=3)).start()
            return True
        except Exception as e:  # noqa: BLE001
            print(f"буфер обмена (сейф): {e}", file=sys.stderr)
            return False

    def clipboard_image(self):
        """Картинка из буфера обмена (скопировали снимок экрана или фото) -> data:image/…;base64 или "" — нет картинки.
        Страница сама не всегда получает картинку при вставке (WebKitGTK отдаёт только текст), поэтому — через окно:
        Linux — буфер GTK, Windows — Pillow ImageGrab. Кнопка «из буфера» и Ctrl+V в виджете."""
        import base64
        try:
            if WIN:
                import io
                from PIL import ImageGrab
                im = ImageGrab.grabclipboard()
                if im is None or isinstance(im, list):
                    return ""
                buf = io.BytesIO()
                im.convert("RGB").save(buf, "JPEG", quality=88)
                return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

            def get():
                from gi.repository import Gdk, Gtk
                pb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_image()
                if pb is None:
                    return ""
                ok, data = pb.save_to_bufferv("png", [], [])
                return "data:image/png;base64," + base64.b64encode(data).decode() if ok else ""
            return self._gtk(get, timeout=4) or ""
        except Exception as e:  # noqa: BLE001
            print(f"буфер обмена: {e}", file=sys.stderr)
            return ""

    @staticmethod
    def _offset(mode):
        """Сдвиг окна режима относительно карточки: правые нижние углы совпадают."""
        (cw, ch), (w, h) = SIZES["card"], SIZES[mode]
        return cw - w, ch - h

    def _clamp(self, mode, x, y):
        from gi.repository import Gdk
        w, h = SIZES[mode]
        try:
            disp = Gdk.Display.get_default()
            g = disp.get_monitor_at_point(int(x) + w // 2, int(y) + h // 2).get_geometry()
            return (max(g.x, min(int(x), g.x + g.width - w)), max(g.y, min(int(y), g.y + g.height - h)))
        except Exception:  # noqa: BLE001
            return max(0, int(x)), max(0, int(y))

    def _hwnd(self, mode):
        """Windows: дескриптор окна режима (у pywebview — Form.Handle; запасной путь — по заголовку)."""
        try:
            return int(self.wins[mode].native.Handle.ToInt64())
        except Exception:  # noqa: BLE001
            return winshell.hwnd(TITLES[mode])

    def get_pos(self, mode="card"):
        if WIN:
            h = self._hwnd(mode)
            return winshell.get_pos(h) if h else [0, 0]
        return self._gtk(lambda: list(self._gw(mode).get_position())) or [0, 0]

    def drag_begin(self, mode="card"):
        """Windows: начали тащить виджет — запомнить, где курсор относительно окна (drag_step ведёт окно за курсором)."""
        if not WIN:
            return False
        h = self._hwnd(mode)
        if not h:
            return False
        cx, cy = winshell.cursor(h)
        x, y = winshell.get_pos(h)
        self._drag = (mode, cx - x, cy - y)
        return True

    def drag_step(self, mode="card"):
        """Windows: окно — туда, где сейчас курсор (минус точка захвата). Порядок вызовов не важен: каждый берёт курсор
        сейчас, а не координаты из страницы (21.10, №169: «стрелка убегает быстрей, чем окно»)."""
        d = getattr(self, "_drag", None)
        h = self._hwnd(mode) if WIN else None
        if not d or d[0] != mode or not h:
            return False
        cx, cy = winshell.cursor(h)
        self.move_to(mode, round(cx - d[1]), round(cy - d[2]))
        return True

    def move_to(self, mode, x, y):
        if mode == "card" and getattr(self, "_pad_on", False):     # блокнот едет вместе с карточкой
            self._pad_follow_at(x, y)
        if WIN:
            h = self._hwnd(mode)
            if h:
                winshell.move(h, x, y)
            return
        from gi.repository import GLib

        def mv():
            gw = self._gw(mode)
            if gw is not None and gw.get_window() is not None:
                gw.get_window().move(int(x), int(y))      # напрямую окну: mutter не всегда слушает gtk_window_move
            return False
        GLib.idle_add(mv, priority=GLib.PRIORITY_HIGH_IDLE)

    def save_pos(self, mode="card"):
        """Положение в «координатах карточки» — его и храним в настройках."""
        x, y = self.get_pos(mode)
        dx, dy = self._offset(mode)
        return [x - dx, y - dy]

    def _place(self, mode, cx, cy):
        """Поставить окно режима так, как если бы карточка стояла в (cx, cy), и показать (Linux — в главном потоке
        GTK). Окно не выходит за край экрана -> итоговое положение в «координатах карточки»."""
        dx, dy = self._offset(mode)
        if WIN:
            h = self._hwnd(mode)
            w, hh = SIZES[mode]
            x, y = winshell.clamp(h, cx + dx, cy + dy, w, hh) if h else (cx + dx, cy + dy)
            if h:
                winshell.move(h, x, y)
            self.wins[mode].show()
            if h:                              # и после показа: показ скрытой формы может вернуть её на прежнее место
                winshell.move(h, x, y)
            self._win_shape(mode)
            return [x - dx, y - dy]
        x, y = self._clamp(mode, cx + dx, cy + dy)
        gw = self._gw(mode)
        gw.move(x, y)
        gw.realize()
        try:
            shape_window(gw, mode)             # перед каждым показом: GNOME читает форму окна при появлении
        except Exception as e:  # noqa: BLE001
            print(f"Форма окна не задана: {e}", file=sys.stderr)
        gw.show_all()
        gw.get_window().move(x, y)
        return [x - dx, y - dy]

    def _win_shape(self, mode, delays=(0, 0.4, 1.2, 3.0)):
        """Windows: скруглённая карточка и круглый значок. Форму окна сбрасывают показ окна, смена масштаба и
        пересоздание окна WinForms (тогда у него новый дескриптор) — поэтому ставим её после каждого показа, по
        событиям окна и ещё несколько раз с задержкой; каждый раз по свежему дескриптору."""
        import threading

        def run():
            for d in delays:
                time.sleep(d)
                h = self._hwnd(mode)
                if h:
                    try:
                        winshell.shape(h, mode, card_r())
                    except Exception as e:  # noqa: BLE001
                        print(f"Форма окна не задана: {e}", file=sys.stderr)
        threading.Thread(target=run, daemon=True).start()

    def _win_shape_keeper(self):
        """Windows: раз в 3 с проверить, что у видимого виджета есть форма, — слетела (тема, масштаб, пересоздание окна
        мимо событий) — поставить заново. 28.10, владелец: «на Windows виджет с прямыми углами, нет скруглений»."""
        import threading

        def run():
            said = False
            while True:
                time.sleep(3)
                try:
                    h = self._hwnd(self.mode) if self.mode in SIZES else None
                    if h and winshell.visible(h) and not winshell.has_shape(h):
                        winshell.shape(h, self.mode, card_r())
                        if not said:
                            said = True
                            _ui_log(f"виджет: форма окна слетела ({self.mode}) — поставлена заново")
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=run, name="win-shape", daemon=True).start()

    def _win_shape_events(self, mode):
        """Подписка на события формы WinForms: показали, поменяли размер, пересоздали — форма заново."""
        try:
            form = self.wins[mode].native
            hook = lambda *_a: self._win_shape(mode, delays=(0, 0.5))  # noqa: E731
            for ev in ("SizeChanged", "VisibleChanged", "HandleCreated", "DpiChanged", "Shown"):
                if hasattr(form, ev):
                    getattr(form, ev).__iadd__(hook)
        except Exception as e:  # noqa: BLE001
            print(f"События окна для формы: {e}", file=sys.stderr)

    def start_hud(self, mode, cx, cy):
        """Первый показ виджета (из on_start). Оба окна убираем с панели задач и из Alt+Tab, задаём им форму —
        до показа, иначе GNOME её не заметит, — и следим, чтобы форма не слетала (Windows — по событиям формы
        WinForms, Linux — _keep_shape)."""
        if WIN:
            for m in SIZES:
                h = self._hwnd(m)
                if h:
                    try:
                        winshell.tool_window(h)
                        winshell.set_icon(h, ROOT / "icons" / "dewiar.ico")      # №260: и в Alt+Tab, если покажется
                        winshell.shape(h, m, card_r())
                    except Exception as e:  # noqa: BLE001
                        print(f"Форма окна не задана: {e}", file=sys.stderr)
                self._win_shape_events(m)
            self.mode = mode
            self._place(mode, cx, cy)
            self._activate()
            self._win_shape_keeper()
            return

        # pywebview создаёт окна по очереди, а on_start может прийти раньше, чем готово второе окно: тогда у него нет
        # формы (квадратный значок до первого сворачивания). Ждём до 10 с, пока появятся оба окна.
        for _ in range(100):
            if self._gtk(lambda: all(self._gw(m) is not None and self._gw(m).get_child() is not None for m in SIZES)):
                break
            time.sleep(0.1)

        def run():
            for m in SIZES:
                gw = self._gw(m)
                if gw is None:
                    continue
                gw.set_skip_taskbar_hint(True)         # виджет — не окно приложения: в доке и Alt+Tab его нет
                gw.set_skip_pager_hint(True)
                gw.realize()
                # Фон прозрачного окна здесь НЕ трогать: 0.38.95 (clear_window_bg — CSS «прозрачно» окну и всему внутри,
                # и странице WebKit, + свой draw) на Ubuntu сломал виджет: застывший кадр без глаз, не тянется, студия
                # висит (20.10, 21:36; откат на 0.38.94 помог). Проверка hud_window1020_test.
                try:
                    shape_window(gw, m)
                except Exception as e:  # noqa: BLE001
                    print(f"Форма окна не задана: {e}", file=sys.stderr)
                self._keep_shape(gw, m)
            self.mode = mode
            return self._place(mode, cx, cy)
        self._gtk(run, timeout=10)
        self._activate()

    @staticmethod
    def _keep_shape(gw, mode):
        """pywebview/GTK может поменять размер окна уже после того, как задана форма, — и виджет остаётся квадратным
        до сворачивания. Поэтому форму ставим заново по настоящему размеру (с учётом масштаба экрана) при каждом
        изменении размера и ещё трижды после показа окна."""
        from gi.repository import GLib
        st = {"key": None}

        def reshape(*_a, force=False):
            gdkw = gw.get_window()
            if gdkw is None:
                return False
            w, h, k = gdkw.get_width(), gdkw.get_height(), gdkw.get_scale_factor()
            if w < 8 or h < 8 or (st["key"] == (w, h, k) and not force):
                return False
            st["key"] = (w, h, k)
            try:
                shape_window(gw, mode, (w * k, h * k), card_r() * k)
            except Exception as e:  # noqa: BLE001
                print(f"Форма окна не задана: {e}", file=sys.stderr)
            return False

        def on_map(*_a):
            for ms in (60, 400, 1500):
                GLib.timeout_add(ms, lambda: reshape(force=True))
            return False
        gw.connect("size-allocate", reshape)
        gw.connect("map", on_map)

    def _activate(self):
        """Сказать страницам, какое окно сейчас на виду (hudActive в hud.html): спрятанное не анимирует облик —
        не тратим процессор."""
        import threading

        def run():
            for m, win in self.wins.items():
                try:
                    win.evaluate_js(f"window.hudActive && hudActive({'true' if m == self.mode else 'false'})")
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def _studio_size():
        """Студия: 1120×760 × масштаб интерфейса, но не больше экрана (ноутбук 1366×768 — с запасом под панель)."""
        z = zoom_of(ui_settings().get("zoom"))
        w, h = int(1120 * z), int(760 * z)
        saved = ui_settings().get("studio_size")             # №262 (25.10): «открывается во весь экран — запоминайте размер»
        if isinstance(saved, list) and len(saved) == 2 and all(isinstance(v, (int, float)) for v in saved):
            w, h = int(saved[0]), int(saved[1])
        try:
            import webview
            scr = webview.screens[0]
            w, h = min(w, int(scr.width * 0.92)), min(h, int(scr.height * 0.86))
        except Exception:  # noqa: BLE001
            pass
        return max(640, w), max(460, h)

    def set_zoom(self, z):
        """Масштаб интерфейса поменяли (студия «Оформление» или Ctrl + / Ctrl − в виджете): окна виджета — под него,
        правый нижний угол карточки остаётся на месте. Страница уже уменьшилась сама (CSS zoom). Виджет в трее —
        только размер, без показа. -> новое положение карточки (страница сохраняет его) или None."""
        old_card = SIZES["card"]
        try:
            cx, cy = self.save_pos(self.mode)
        except Exception:  # noqa: BLE001
            cx = cy = None
        if not set_zoom_sizes(z):
            return None
        if cx is not None:
            cx, cy = cx + old_card[0] - SIZES["card"][0], cy + old_card[1] - SIZES["card"][1]
        if WIN:
            for m, (w, h) in SIZES.items():
                try:
                    form = self.wins[m].native
                    from System import Action
                    from System.Drawing import Size
                    form.Invoke(Action(lambda f=form: setattr(f, "MinimumSize", Size(1, 1))))   # иначе не уменьшится
                except Exception as e:  # noqa: BLE001
                    print(f"Масштаб: наименьший размер окна: {e}", file=sys.stderr)
                try:
                    self.wins[m].resize(w, h)
                except Exception as e:  # noqa: BLE001
                    print(f"Масштаб: размер окна: {e}", file=sys.stderr)
            if cx is not None and not self.in_tray:
                return self._place(self.mode, cx, cy)
            return None

        def run():
            for m, (w, h) in SIZES.items():
                gw = self._gw(m)
                if gw is None:
                    continue
                gw.set_size_request(w, h)          # pywebview задаёт min_size так же — иначе окно не уменьшится
                gw.resize(w, h)
            gw = self._gw(self.mode)
            if cx is not None and not self.in_tray and gw is not None and gw.get_visible():
                return self._place(self.mode, cx, cy)
            return None
        try:
            return self._gtk(run, timeout=5)
        except Exception as e:  # noqa: BLE001
            print(f"Масштаб: окна виджета: {e}", file=sys.stderr)
            return None

    def card_size(self):
        """Текущий размер карточки (логические px окна) — для растягивания за угол (hud.html)."""
        return list(SIZES["card"])

    def resize_card(self, w, h, final=False):
        """Растянули карточку за угол (отзыв 19.10: «растягивать ввысь или вширь с запоминанием»). w, h — желаемый
        размер окна сейчас (с масштабом); левый верхний угол остаётся на месте. -> [ш, в] при 100 % — их страница
        сохраняет (ui.hud_w, ui.hud_h), или None. w или h = 0 — вернуть размер по умолчанию."""
        z = ZOOM[0] or 1.0
        if not w or not h:
            set_card_base(*CARD_DEFAULT)
        else:
            set_card_base(float(w) / z, float(h) / z)
        set_zoom_sizes(z)
        W, H = SIZES["card"]
        if final and getattr(self, "_pad_on", False):     # блокнот открыт — крепления под новый размер виджета
            import threading
            ps, zz = list(getattr(self, "_pad_size", None) or [None, None]), ZOOM[0] or 1.0
            threading.Timer(0.4, lambda: self.pad_resize(ps[0] * zz if ps[0] else 0, ps[1] * zz if ps[1] else 0, True)).start()
        if WIN:
            try:
                form = self.wins["card"].native
                from System import Action
                from System.Drawing import Size
                form.Invoke(Action(lambda f=form: setattr(f, "MinimumSize", Size(1, 1))))
            except Exception as e:  # noqa: BLE001
                print(f"Размер виджета: {e}", file=sys.stderr)
            try:
                self.wins["card"].resize(W, H)
            except Exception as e:  # noqa: BLE001
                print(f"Размер виджета: {e}", file=sys.stderr)
            try:                                  # форма (скругление) — под новый размер сразу, а не после отпускания
                hw = self._hwnd("card")
                if hw:
                    winshell.shape(hw, "card", card_r())
            except Exception:  # noqa: BLE001
                pass
            if final:
                self._win_shape("card")
            return list(BASE_SIZES["card"])

        def run():
            gw = self._gw("card")
            if gw is not None:
                gw.set_size_request(W, H)
                gw.resize(W, H)
            return True
        try:
            self._gtk(run, timeout=5)
        except Exception as e:  # noqa: BLE001
            print(f"Размер виджета: {e}", file=sys.stderr)
            return None
        return list(BASE_SIZES["card"])

    def set_mode(self, mode, auto=False):
        """Карточка ↔ значок. Правый нижний угол остаётся на месте — виджет обычно стоит в углу экрана.
        auto — раскрыли сами ради вопроса «Да/Нет» (auto_back потом вернёт значок).
        -> положение в «координатах карточки» (страница сохраняет его в настройки) или None."""
        if mode not in SIZES:
            return None
        self.auto = bool(auto)
        if mode == self.mode:
            return self.save_pos(mode)
        if mode != "card" and getattr(self, "_pad_on", False):     # свернули в значок — блокнот прячется
            self.pad_hide()
        src = self.mode
        if WIN:
            x, y = self.get_pos(src)
            dx, dy = self._offset(src)
            p = self._place(mode, x - dx, y - dy)
            self.wins[src].hide()
            self.mode = mode
            self._activate()
            return p

        def run():
            x, y = self._gw(src).get_position()
            dx, dy = self._offset(src)
            p = self._place(mode, x - dx, y - dy)
            self._gw(src).hide()
            self.mode = mode
            return p
        p = self._gtk(run)
        self._activate()
        return p

    def auto_back(self):
        """Карточку раскрыли ради «Да/Нет» — через 2,5 с вернуться в значок. Пришёл следующий вопрос раньше — остаёмся
        (cancel_back; отчёт 11.10: задача спросила второй раз, а виджет свернулся в шарик посреди вопроса)."""
        if self.auto:
            import threading
            t = getattr(self, "_back_t", None)
            if t:
                t.cancel()

            def back():
                if self.auto and getattr(self, "_back_t", None) is me:
                    self.auto = False
                    self.set_mode("mini")
            me = self._back_t = threading.Timer(2.5, back)
            me.start()

    def cancel_back(self):
        """Новый вопрос «Да/Нет», пока карточка ещё раскрыта ради прошлого, — не сворачиваться."""
        t = getattr(self, "_back_t", None)
        if t:
            t.cancel()
        self._back_t = None

    def show(self):
        """Показать виджет. Если он в трее — ненадолго: после разговора спрячется обратно (tray_back)."""
        if self.in_tray:
            self.popped = True
        if WIN:
            self.wins[self.mode].show()
            self._win_shape(self.mode)
            return
        self._gtk(lambda: self._gw(self.mode).show_all())

    # ---------- трей ----------

    def _hide_now(self):
        if WIN:
            self.wins[self.mode].hide()
            return
        self._gtk(lambda: self._gw(self.mode).hide())

    def to_tray(self, quiet=False):
        """Кнопка «В трей»: виджет прячется, ассистент слушает. Вернётся сам — на имя, напоминание, уведомление."""
        if getattr(self, "_pad_on", False):
            self.pad_hide()
            self._pad_back = True                     # вернём блокнот вместе с виджетом (from_tray)
        elif not self.in_tray:
            self._pad_back = False
        first = not self.in_tray
        self.in_tray, self.popped = True, False
        self._hide_now()
        if first and not quiet:
            where = "значок Dewiar возле часов" if WIN or self._tray else "«Dewiar» в меню приложений"
            _notify(f"Dewiar в трее и слушает. Появится сам, когда позовёте по имени или придёт напоминание. "
                    f"Вернуть — {where} или скажите «покажись»; выключить совсем — «Выйти из Dewiar» там же.")
        return True

    def tray_back(self):
        """Поговорили — спрятаться обратно (только если показались сами, а не по кнопке).
        23.10, владелец: «ложная сработка — виджет исчез, остался только блокнот, смотрится странно»: виджет показался
        из трея на имя, а блокнот рядом открыт — человек работает. Остаёмся на экране и выходим из трея насовсем."""
        if self.in_tray and getattr(self, "_pad_on", False):
            self._stay()
            return True
        if self.in_tray and self.popped:
            self.popped = False
            self._hide_now()
        return True

    def _stay(self):
        """Виджет показался из трея сам, а человек начал с ним работать (открыл блокнот) — он больше не «в трее»:
        после разговора не прячется, и при следующем запуске начинает на экране."""
        if self.in_tray:
            self.in_tray, self.popped = False, False
            self._js("window.trayLeft && trayLeft()")

    def from_tray(self):
        """Значок в трее / меню приложений: вернуть виджет насовсем."""
        was = self.in_tray
        self.in_tray, self.popped = False, False
        self.show()
        if was:
            self._js("window.trayLeft && trayLeft()")
        if was and getattr(self, "_pad_back", False):
            # 22.10, владелец: «свернул блокнот с виджетом — вернул, а блокнот приходится открывать заново»: был открыт —
            # открываем снова (в фоне: из меню трея мы в главном потоке GTK, а pad_open ждёт его)
            self._pad_back = False
            import threading
            threading.Timer(0.35, self.pad_open).start()
        return True

    def bring_back(self):
        """Linux: Dewiar запустили ещё раз (меню приложений, `dewiar`) — виджет поверх и целиком на экране этого
        монитора. GitHub #7 (Kubuntu, KDE): «после того как закрыл окно, больше никакими способами не появилось» —
        повторный запуск только «будил» уже запущенный интерфейс, а виджет мог остаться за краем экрана."""
        if WIN:
            return False

        def run():
            gw = self._gw(self.mode)
            if gw is None:
                return False
            gw.show_all()
            gw.present()
            _keep_on_screen(gw)
            return True
        return bool(self._gtk(run))

    def tray_state(self):
        # icon — есть ли значок в трее (на Linux без AppIndicator вернуть виджет можно только из меню приложений)
        return {"in_tray": self.in_tray, "icon": bool(WIN or self._tray)}

    def _js(self, code):
        """Выполнить код во всех окнах виджета — в фоне: evaluate_js ждёт ответа страницы."""
        import threading

        def run():
            for win in self.wins.values():
                try:
                    win.evaluate_js(code)
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=run, daemon=True).start()

    def open_url(self, url):
        """Ссылка наружу: сайт, Telegram (tg://), Obsidian (obsidian://) — системой. Только эти схемы: страница не
        должна суметь открыть через систему файл или запустить программу (file:, ms-…: и подобные)."""
        url = str(url or "")
        if not url.split(":", 1)[0].lower() in ("http", "https", "obsidian", "tg"):
            return False
        if WIN:
            os.startfile(url)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def pick_folder(self):
        """Выбор папки проекта (для задач по коду). -> путь или "" (отказались)."""
        import webview
        # новые pywebview — webview.FileDialog.*, старые — webview.*_DIALOG (так же в pick_file и save_file*)
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        res = (self._studio or self._hud).create_file_dialog(kind, directory=str(Path.home()))
        if not res:
            return ""
        return res if isinstance(res, str) else res[0]

    def pick_file(self, kind=""):
        """Выбор файла (например, резервной копии): kind — «Описание (*.ext)». Начинаем с папки резервных копий."""
        import webview
        k = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        types = (kind, "Все файлы (*.*)") if kind else ("Все файлы (*.*)",)
        try:
            from backup import default_dir
            start = str(default_dir()) if default_dir().is_dir() else str(Path.home())
        except Exception:  # noqa: BLE001
            start = str(Path.home())
        res = (self._studio or self._hud).create_file_dialog(k, directory=start, file_types=types)
        if not res:
            return ""
        return res if isinstance(res, str) else res[0]

    def install_update(self, path):
        """Поставить обновление, которое ядро скачало и проверило. Путь приходит со страницы, поэтому принимаем
        только файл из STATE_DIR/updates. Linux: pkexec apt-get (GNOME спросит пароль) в фоне — ход в
        update_progress(); после установки интерфейс перезапускается сам, ядро перезапускает установщик пакета.
        DEWIAR_UPDATE_CMD — команда вместо pkexec apt-get, для проверок без root."""
        p = Path(path or "").resolve()
        from settings import STATE_DIR
        allowed = STATE_DIR.resolve() / "updates"
        if WIN:
            return self._install_update_win(p, allowed)
        if allowed not in p.parents or p.suffix != ".deb" or not p.is_file():
            return {"ok": False, "error": "это не скачанное обновление Dewiar"}
        cmd = os.environ.get("DEWIAR_UPDATE_CMD")
        # APT::Status-Fd=1 — apt пишет в вывод строки «pmstatus:…:процент:…», по ним _run_update считает ход
        if cmd:
            cmd = cmd.split() + [str(p)]
        elif not shutil.which("dpkg") and Path("/opt/dewiar/install.sh").is_file():
            # не Debian/Ubuntu (Arch, Fedora, openSUSE…): поставили install.sh — им же и обновляемся (файлы пакета без dpkg)
            cmd = ["pkexec", "bash", "/opt/dewiar/install.sh", "--yes", "--no-deps", "--deb", str(p)]
        else:
            cmd = ["pkexec", "apt-get", "install", "-y", "--allow-downgrades", "-o", "APT::Status-Fd=1", str(p)]
        if getattr(self, "_upd", {}).get("stage") in ("auth", "install"):
            return {"ok": True, "started": True}                  # уже ставится — студия просто покажет ход
        self._upd = {"stage": "auth", "pct": 0, "line": "", "error": "", "t0": time.time()}
        import threading
        threading.Thread(target=self._run_update, args=(cmd,), name="update", daemon=True).start()
        return {"ok": True, "started": True}

    def _run_update(self, cmd):
        """Ставим пакет (поток update) и рассказываем студии, что происходит (update_progress):
        auth (ждём пароль) → install → restart или error. Проценты грубые: dpkg — до 60 %, шаги установщика
        пакета (строки «Dewiar: …») — 62 и 85 %."""
        u = self._upd
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                    env=dict(os.environ, LC_ALL="C.UTF-8"))
        except FileNotFoundError:
            u.update(stage="error", error="нет pkexec — установите вручную: sudo apt install " + cmd[-1])
            return
        tail = []
        for raw in proc.stdout:
            ln = raw.strip()
            if not ln:
                continue
            tail = (tail + [ln])[-60:]
            if u["stage"] == "auth":
                u["stage"] = "install"                        # пароль принят — пошёл вывод установки
            m = re.match(r"pmstatus:[^:]*:([\d.]+):(.*)", ln)
            if m:                                            # прогресс dpkg: распаковка → настройка
                u["pct"] = max(u["pct"], min(95, int(float(m.group(1)) * 0.6)))
                continue
            if ln.startswith("Dewiar:"):                     # шаги нашего установщика (библиотеки, модель)
                u["line"] = ln[7:].strip()
                u["pct"] = max(u["pct"], 62 if "готовлю" in ln else 85 if "установлены" in ln or "модель" in ln else u["pct"])
            elif ln.startswith(("Unpacking", "Распаковывается", "Preparing", "Подготовка")):
                u["line"], u["pct"] = "распаковываю новую версию…", max(u["pct"], 25)
            elif ln.startswith(("Setting up", "Настраивается")):
                u["line"], u["pct"] = "настраиваю…", max(u["pct"], 55)
        rc = proc.wait()
        if rc and not WIN:
            # apt мог «упасть» из-за чужого сломанного пакета (например, драйвер NVIDIA под новое ядро), а Dewiar
            # при этом поставился. Проверяем сам пакет: стоит нужная версия — значит, обновление удалось.
            m = re.search(r"_(\d+(?:\.\d+)+)_all\.deb$", cmd[-1])
            try:
                q = subprocess.run(["dpkg-query", "-W", "-f=${Status}|${Version}", "dewiar-assistant"],
                                   capture_output=True, text=True, timeout=10).stdout
            except (OSError, subprocess.SubprocessError):
                q = ""
            if m and q.startswith("install ok installed|") and q.split("|", 1)[1].strip() == m.group(1):
                others = sorted({mm.group(1) for x in tail for mm in [re.search(r"dpkg: (?:ошибка при обработке пакета|error processing package) (\S+)", x)] if mm} - {"dewiar-assistant"})
                u["note"] = ("Dewiar обновлён. В системе есть другие недонастроенные пакеты"
                             + (f" ({', '.join(others[:3])})" if others else "") + " — это не мешает Dewiar.")
                rc = 0
        if rc:
            # настоящая причина — строки dpkg/E:, а не предупреждение dpkg-preconfigure про stdin
            # pkexec: 126 — окно пароля закрыли, 127 — не разрешили
            why = [x for x in tail if re.search(r"dpkg:|error|ошибк|E:|не удалось|failed", x, re.I) and "preconfigure" not in x]
            err = "установка отменена (пароль не введён)" if rc in (126, 127) else (" ".join((why or tail)[-4:]) or f"код {rc}")[-600:]
            try:
                (Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / "dewiar-update.log").write_text("\n".join(tail), encoding="utf-8")
            except OSError:
                pass
            u.update(stage="error", error=err)
            try:                                          # установщик успел остановить ядро — поднимем прежнее
                ensure_core()
            except Exception:  # noqa: BLE001
                pass
            return
        u.update(stage="restart", pct=100, line=u.get("note") or "перезапускаюсь новой версией…")
        import threading
        threading.Timer(1.5, self.restart).start()

    def update_progress(self):
        """Ход установки для студии: stage, pct, line, error, note и secs — сколько секунд идёт."""
        u = dict(getattr(self, "_upd", None) or {"stage": ""})
        if u.get("t0"):
            u["secs"] = int(time.time() - u.pop("t0"))
        return u

    def _install_update_win(self, p, allowed):
        """Windows: остановить ядро (иначе его файлы заняты), запустить установщик тихо (/S /UPDATE) и выйти —
        установщик заменит файлы и сам запустит новую версию. Права администратора не нужны (установка в профиль)."""
        if allowed not in p.parents or p.suffix.lower() != ".exe" or not p.is_file():
            return {"ok": False, "error": "это не скачанное обновление Dewiar"}
        try:
            winshell.core_call(WS_PORT, self.token, "quit")
        except Exception:  # noqa: BLE001
            pass
        _notify("Dewiar обновляется — через минуту-две откроется сам.")
        try:                                     # метка: после перезапуска ядро сверит версию (updater._check_pending)
            (allowed / "pending.json").write_text(json.dumps({"file": p.name, "ts": time.time()}), encoding="utf-8")
        except OSError:
            pass
        try:                                     # метка «идёт установка» для сторожа; убирает её сам установщик
            from settings import STATE_DIR
            (STATE_DIR / "update.run").write_text(p.name, encoding="utf-8")
        except OSError:
            pass
        try:
            inst = subprocess.Popen(_update_cmd(p), creationflags=winshell.DETACHED, close_fds=True)
        except OSError as e:
            return {"ok": False, "error": f"установщик не запустился: {e}"}
        try:                                     # страховка: установщик не запустил новую версию — запустит сторож
            exe = winshell.pythonw()
            relaunch_after(inst.pid, Path(exe).resolve().parent.parent, exe, Path(__file__).resolve())
        except Exception as e:  # noqa: BLE001
            _ui_log(f"сторож обновления не запущен: {e}")
        import threading
        threading.Timer(1.0, lambda: os._exit(0)).start()
        return {"ok": True}

    def run_installer(self, path):
        """Тихое обновление не встало — открыть скачанный установщик обычным окном (Windows): он сам остановит Dewiar,
        покажет ход и ошибку, если что-то мешает, и запустит новую версию. Только файл из STATE_DIR/updates."""
        p = Path(path or "").resolve()
        from settings import STATE_DIR
        allowed = STATE_DIR.resolve() / "updates"
        if not WIN or allowed not in p.parents or p.suffix.lower() != ".exe" or not p.is_file():
            return {"ok": False, "error": "это не скачанное обновление Dewiar"}
        try:
            os.startfile(str(p))  # noqa: S606 — проверенный (sha256) установщик из своей папки обновлений
        except OSError as e:
            return {"ok": False, "error": f"установщик не открылся: {e}"}
        return {"ok": True}

    def restart_core(self):
        """Кнопка в виджете, когда ядро не отвечает: перезапустить только ядро (окна остаются, разговор начнётся
        заново). Работает в фоне: зависшее ядро может не завершиться сразу. Windows — номер из core.pid и свой
        процесс; Linux — служба, а без неё (из исходников) — pkill по core/main.py."""
        import threading

        def run():
            from settings import STATE_DIR
            try:
                if WIN:
                    try:
                        winshell.kill_pid((STATE_DIR / "core.pid").read_text(encoding="ascii").strip())
                    except OSError:
                        pass
                    for p in CORE_PROC:
                        try:
                            p.kill()
                        except Exception:  # noqa: BLE001
                            pass
                    time.sleep(1.5)
                    start_core_win()
                elif subprocess.run(["systemctl", "--user", "cat", "dewiar-core.service"], capture_output=True).returncode == 0:
                    subprocess.run(["systemctl", "--user", "restart", "dewiar-core.service"], capture_output=True, timeout=30)
                else:                                      # из исходников: ядро — просто процесс на нашем порту
                    subprocess.run(["pkill", "-f", "core/main.py"], capture_output=True)
                    time.sleep(1.5)
                    ensure_core()
                _ui_log("ядро перезапущено по кнопке в виджете")
            except Exception as e:  # noqa: BLE001
                _ui_log(f"перезапуск ядра не удался: {e}")
        threading.Thread(target=run, daemon=True).start()
        return True

    def quit_all(self):
        """«Выход» из трея, голосом («отключись») или конец главного цикла окон (Windows) — завершить ядро и
        интерфейс. Linux: ядро — служба systemd --user; stop не отключает её автозапуск, так что при следующем
        входе в систему или запуске Dewiar из меню всё снова работает. Без службы (из исходников) — команда quit."""
        _ui_log("выход: ядро и интерфейс завершаются")
        if WIN:
            try:
                winshell.core_call(WS_PORT, self.token, "quit")
            except Exception:  # noqa: BLE001
                pass
        elif subprocess.run(["systemctl", "--user", "cat", "dewiar-core.service"], capture_output=True).returncode == 0:
            subprocess.run(["systemctl", "--user", "stop", "--no-block", "dewiar-core.service"], capture_output=True, timeout=10)
        else:
            try:
                _core_call(self.token, "quit")
            except Exception:  # noqa: BLE001
                subprocess.run(["pkill", "-f", "core/main.py"], capture_output=True)
        if getattr(self, "_tray", None) and hasattr(self._tray, "stop"):
            self._tray.stop()
        os._exit(0)

    def restart(self, note="Dewiar обновлён."):
        """Перезапустить интерфейс новой версией (после обновления) или с другой отрисовкой окон (note — что сказать)."""
        _notify(note)
        if WIN:
            subprocess.Popen([winshell.pythonw(), "-X", "utf8", str(Path(__file__).resolve()), "--autostart"],   # убранный в трей — остаётся в трее
                             creationflags=winshell.DETACHED, close_fds=True)
            os._exit(0)
        launcher = ROOT / "dewiar"               # /opt/dewiar/dewiar: донастроит службу ядра и откроет виджет
        try:                                     # DEWIAR_UPDATE_CMD — проверка: перезапускаем этот же файл, без пускача
            if launcher.is_file() and not os.environ.get("DEWIAR_UPDATE_CMD"):
                os.execv("/bin/sh", ["/bin/sh", str(launcher), "--autostart"])
            os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve()), "--autostart"])
        except OSError as e:
            print(f"Перезапуск не удался: {e}", file=sys.stderr)

    def hide(self):
        if WIN:
            self.wins[self.mode].hide()
            _notify("Dewiar продолжает слушать. Вернуть виджет — значок Dewiar возле часов.")
            return
        self._gtk(lambda: self._gw(self.mode).hide())
        _notify("Dewiar продолжает слушать. Вернуть виджет — «Dewiar» в меню приложений.")

    def save_file(self, content, filename):
        """Сохранение через системный диалог (в окне pywebview обычные загрузки не работают)."""
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        res = (self._studio or self._hud).create_file_dialog(kind, directory=str(Path.home()), save_filename=filename,
                                                            file_types=("Настройки Dewiar (*.dewiar)", "Все файлы (*.*)"))
        if not res:
            return ""
        path = res if isinstance(res, str) else res[0]
        Path(path).write_text(content, encoding="utf-8")
        os.chmod(path, 0o600)                    # в выгрузке настроек бывают ключи — читать только владельцу
        return path

    def save_file_b64(self, b64, filename):
        """То же для двоичного файла: страница передаёт содержимое в base64. -> путь или ""."""
        import base64
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        res = (self._studio or self._hud).create_file_dialog(kind, directory=str(Path.home()), save_filename=filename)
        if not res:
            return ""
        path = res if isinstance(res, str) else res[0]
        Path(path).write_bytes(base64.b64decode(b64))
        return path

    def open_skills_folder(self, path=""):
        """Папка навыков — внутри папки ассистента («Навыки»); путь подсказывает студия."""
        d = Path(path) if path else SETTINGS_PATH.parent / "skills"
        d.mkdir(parents=True, exist_ok=True)
        if WIN:
            os.startfile(str(d))  # noqa: S606
            return
        subprocess.Popen(["xdg-open", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def open_note(self, path=""):
        """Открыть заметку в студии («Заметки»): из окна напоминания с картинками — «Открыть все в заметке»."""
        import json as _json
        from urllib.parse import quote
        path = str(path or "")
        if not path.startswith("Заметки/"):
            return self.open_settings("notes")
        if self._studio is not None:
            self.open_settings("notes")
            try:
                if self._studio is not None:
                    self._studio.evaluate_js(f"window.ntGoto && ntGoto({_json.dumps(path)})")
                    return
            except Exception:  # noqa: BLE001
                self._studio = None
        self.open_settings("notes", "&note=" + quote(path))

    def open_settings(self, page="", query=""):
        """Открыть студию на разделе page. Окно одно: уже открыто — показываем его; с query (импорт файла,
        ссылка подключения) окно создаётся заново, чтобы страница получила новые параметры адреса."""
        import webview
        _ui_log(f"студия: открыть {page or ''}{' (с параметрами)' if query else ''}")
        if self._studio is not None and not WIN and self._gtk(lambda: self._studio_gw() is not None) is False:
            self._studio = None                         # окна уже нет (закрыто мимо нас) — откроем новое
        if self._studio is not None and not query and not self._studio.events.loaded.is_set() and time.monotonic() - getattr(self, "_studio_born", 0) > 15:
            _ui_log("студия: страница не поднялась — окно заново")      # №375: WebView2 не создал страницу — пустое окно
            try:
                self._studio.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._studio = None
        if self._studio is not None and not query:
            try:
                self._studio.show()
                self._raise_studio()
                if ui_settings().get("studio_max", True):
                    self._studio.maximize()             # как оставили в прошлый раз (по умолчанию — во весь экран)
                else:
                    self._studio.restore()
                if page:
                    self._studio.evaluate_js(f"(document.querySelector('nav button[data-p=\"{page}\"]') || {{click(){{}}}}).click()")
                return
            except Exception:  # noqa: BLE001
                self._studio = None
        if self._studio is not None:
            try:
                self._studio.destroy()
            except Exception:  # noqa: BLE001
                pass
        # Linux: своя рамка — чёрная полоса заголовка и скруглённые углы со всех сторон (системная рамка GNOME
        # светлая и снизу квадратная). Перетаскивание и размер — через сам оконный менеджер (прилипание к краям
        # работает). Вернуть системную рамку: settings.ui.studio_frame = "native".
        own = not WIN and ui_settings().get("studio_frame", "custom") != "native"
        sw, sh = self._studio_size()
        skin, light = ui_skin()                     # тема — сразу в адресе: студия открывается в своём стиле, без вспышки
        self._studio = webview.create_window(STUDIO_TITLE, self._url("settings.html", ("&frame=1" if own else "") + "&skin=" + urllib.parse.quote(skin) + query + ("#" + page if page else "")),
                                            width=sw, height=sh, min_size=(min(820, sw), min(560, sh)), background_color="#e3eaf4" if light else "#0a0a0f",
                                            maximized=bool(ui_settings().get("studio_max", True)),
                                            frameless=own, easy_drag=False,
                                            text_select=True,    # текст студии можно выделять и копировать (pywebview по умолчанию запрещает; пакет 23.10, №202)
                                            js_api=self)     # без этого в студии нет «Обновить», выбора папки, сохранения
        win, self._studio_born = self._studio, time.monotonic()
        win.events.closed += lambda *a: self._studio_closed(win)
        if not WIN:
            win.events.shown += lambda *a: __import__("threading").Thread(target=self._raise_studio, daemon=True).start()
        if own:
            import threading
            hook = lambda *a: threading.Thread(target=self._gtk, args=(self._studio_frame,), daemon=True).start()  # noqa: E731
            win.events.shown += hook
            win.events.loaded += hook
        elif WIN:
            def dark():
                try:
                    winshell.dark_title(int(win.native.Handle.ToInt64()))
                except Exception as e:  # noqa: BLE001
                    print(f"Тёмный заголовок: {e}", file=sys.stderr)
            win.events.shown += lambda *a: __import__("threading").Thread(target=dark, daemon=True).start()

            def remember(m):                           # развернули / вернули размер — так и открывать в следующий раз
                try:
                    winshell.core_call(WS_PORT, self.token, "settings_save", {"patch": {"ui": {"studio_max": m}}})
                except Exception:  # noqa: BLE001
                    pass
            for ev, m in (("maximized", True), ("restored", False)):
                if hasattr(win.events, ev):
                    getattr(win.events, ev).__iadd__(lambda *a, m=m: __import__("threading").Thread(target=remember, args=(m,), daemon=True).start())

            def icon():                                 # №260: на панели задач — знак Dewiar, а не значок Python
                try:
                    winshell.set_icon(int(win.native.Handle.ToInt64()), ROOT / "icons" / "dewiar.ico")
                except Exception as e:  # noqa: BLE001
                    print(f"Значок окна: {e}", file=sys.stderr)
            win.events.shown += lambda *a: __import__("threading").Thread(target=icon, daemon=True).start()
        if hasattr(win.events, "resized"):              # №262: размер, который человек оставил, — и в следующий раз
            win.events.resized += lambda *a: self._studio_resized(win, *a[:2])

    # ---------- перетаскивание окна без рамки (Linux) ----------

    @staticmethod
    def _wm_drag(gw, zone):
        """Нажали в zone(x, y, ширина) окна gw — двигает оконный менеджер (begin_move_drag), а не страница.
        Перетаскивание силами pywebview (pywebview-drag-region) считает по screenX/screenY — при нескольких мониторах
        (и разном масштабе) окно уезжало на другой экран и шло за мышью там (отзыв 11.10, Суфлёр на трёх мониторах).
        Главный поток GTK; подключается один раз."""
        from gi.repository import Gdk, Gtk
        if gw is None or getattr(gw, "_dw_drag", False):
            return
        gw._dw_drag = True
        view = [gw]
        while not type(view[-1]).__name__ == "WebView" and isinstance(view[-1], Gtk.Bin) and view[-1].get_child():
            view.append(view[-1].get_child())
        wv, st = view[-1], {"press": None}

        def on_press(_w, ev):
            if ev.button == 1 and ev.type == Gdk.EventType.BUTTON_PRESS and zone(ev.x, ev.y, wv.get_allocated_width()):
                st["press"] = (ev.x_root, ev.y_root)
                return True
            return False

        def on_motion(_w, ev):
            p0 = st.get("press")
            if p0 and abs(ev.x_root - p0[0]) + abs(ev.y_root - p0[1]) > 3:
                st["press"] = None
                gw.begin_move_drag(1, int(ev.x_root), int(ev.y_root), ev.time)
                return True
            return False

        def on_release(_w, ev):
            st["press"] = None
            return False

        wv.connect("button-press-event", on_press)
        wv.connect("motion-notify-event", on_motion)
        wv.connect("button-release-event", on_release)

    # ---------- своя рамка студии (Linux) ----------

    def _studio_frame(self):
        """Окно студии без системной рамки: форма со скруглёнными углами (меняется вместе с размером), нажатия
        на полосе заголовка и по краям передаём оконному менеджеру — он двигает и тянет окно сам.
        Развёрнутое или прижатое к краю окно — без скругления и без краёв; об этом говорим странице (frameState
        в settings.html). Главный поток GTK; подключается к окну один раз (_dw_frame)."""
        from gi.repository import Gdk, Gtk
        gw = next((g for g in Gtk.Window.list_toplevels() if g.get_title() == STUDIO_TITLE), None)
        if gw is None or getattr(gw, "_dw_frame", False):
            return
        gw._dw_frame = True
        view = [gw]                             # нажатия ловим у самого WebView: он занимает всё окно
        while not type(view[-1]).__name__ == "WebView" and isinstance(view[-1], Gtk.Bin) and view[-1].get_child():
            view.append(view[-1].get_child())
        wv = view[-1]
        st = {"key": None, "max": False}

        def reshape(*a):
            gdkw = gw.get_window()
            if gdkw is None:
                return
            w, h, k = gdkw.get_width(), gdkw.get_height(), gdkw.get_scale_factor()
            key = (w, h, k, st["max"])
            if key == st["key"]:
                return
            st["key"] = key
            try:
                shape_window(gw, "rect" if st["max"] else "alarm", (w * k, h * k), STUDIO_RADIUS * k)
            except Exception as e:  # noqa: BLE001
                print(f"Форма студии: {e}", file=sys.stderr)

        def tell_page():
            import threading
            js = f"window.frameState && frameState({'true' if st['max'] else 'false'})"
            threading.Thread(target=lambda: self._studio and self._studio.evaluate_js(js), daemon=True).start()

        def on_state(_w, ev):
            m = bool(ev.new_window_state & (Gdk.WindowState.MAXIMIZED | Gdk.WindowState.FULLSCREEN | Gdk.WindowState.TILED))
            if m != st["max"]:
                st["max"] = m
                reshape()
                tell_page()
            return False

        def on_press(_w, ev):
            if ev.button != 1:
                return False
            w, h = wv.get_allocated_width(), wv.get_allocated_height()
            x, y = ev.x, ev.y
            e = STUDIO_EDGE
            if not st["max"]:
                edge = None
                left, right, top, bottom = x < e, x > w - e, y < e, y > h - e
                if top and left: edge = Gdk.WindowEdge.NORTH_WEST
                elif top and right: edge = Gdk.WindowEdge.NORTH_EAST
                elif bottom and left: edge = Gdk.WindowEdge.SOUTH_WEST
                elif bottom and right: edge = Gdk.WindowEdge.SOUTH_EAST
                elif left: edge = Gdk.WindowEdge.WEST
                elif right: edge = Gdk.WindowEdge.EAST
                elif top: edge = Gdk.WindowEdge.NORTH
                elif bottom: edge = Gdk.WindowEdge.SOUTH
                if edge is not None and ev.type == Gdk.EventType.BUTTON_PRESS:
                    gw.begin_resize_drag(edge, ev.button, int(ev.x_root), int(ev.y_root), ev.time)
                    return True
            if y < STUDIO_BAR and x < w - STUDIO_BTNS:
                st["press"] = None
                if ev.type == Gdk.EventType._2BUTTON_PRESS:          # двойной щелчок по заголовку — развернуть
                    import threading
                    threading.Thread(target=self.studio_max, daemon=True).start()
                elif ev.type == Gdk.EventType.BUTTON_PRESS:          # двигать начнём, когда мышь сдвинется (иначе нет двойного щелчка)
                    st["press"] = (ev.x_root, ev.y_root)
                return True
            return False

        def on_motion(_w, ev):
            p0 = st.get("press")
            if p0 and abs(ev.x_root - p0[0]) + abs(ev.y_root - p0[1]) > 3:
                st["press"] = None
                gw.begin_move_drag(1, int(ev.x_root), int(ev.y_root), ev.time)
                return True
            return False

        def on_release(_w, ev):
            st["press"] = None
            return False

        gw.connect("size-allocate", reshape)
        gw.connect("window-state-event", on_state)
        wv.connect("button-press-event", on_press)
        wv.connect("motion-notify-event", on_motion)
        wv.connect("button-release-event", on_release)
        reshape()

    def _studio_gw(self):
        from gi.repository import Gtk
        return next((g for g in Gtk.Window.list_toplevels() if g.get_title() == STUDIO_TITLE), None)

    def _raise_studio(self):
        """Linux: поднять студию наверх и дать ей фокус. GNOME не пускает вперёд окна фоновой программы (защита от
        кражи фокуса): со второго раза студия открывалась ЗА другими окнами — казалось, что кнопки «Настройки»,
        «Календарь», «Память» ничего не делают. Свёрнутую — развернуть; на миг «поверх всех» и present с временем
        X-сервера (его GNOME считает действием пользователя)."""
        if WIN:
            return

        def run():
            from gi.repository import GLib, Gdk
            gw = self._studio_gw()
            if gw is None:
                return False
            gw.deiconify()
            gw.set_keep_above(True)
            ts = Gdk.CURRENT_TIME
            try:
                gi_win = gw.get_window()
                from gi.repository import GdkX11
                if gi_win is not None and isinstance(gi_win, GdkX11.X11Window):
                    ts = GdkX11.x11_get_server_time(gi_win)
            except Exception:  # noqa: BLE001 — не X11 (Wayland без XWayland)
                pass
            gw.present_with_time(ts)
            GLib.timeout_add(700, lambda: (gw.set_keep_above(False), False)[1])
            return True
        try:
            self._gtk(run)
        except Exception as e:  # noqa: BLE001
            print(f"Студия наверх: {e}", file=sys.stderr)

    def _studio_resized(self, win, w=None, h=None):
        """Студию потянули за край (№262, 25.10: «открывается всегда во весь экран — неудобно, запоминайте размер»):
        через секунду после последнего изменения — если окно не развёрнуто, запомнить ui.studio_size и studio_max=False."""
        import threading
        self._st_rs = getattr(self, "_st_rs", 0) + 1
        n = self._st_rs

        def later():
            if n != self._st_rs or self._studio is not win:
                return
            try:
                if WIN:
                    if "Maximized" in str(win.native.WindowState) or "Minimized" in str(win.native.WindowState):
                        return
                else:
                    gw = self._studio_gw()
                    if gw is None or self._gtk(lambda: gw.is_maximized() or not gw.is_visible()):
                        return
                ww, hh = int(w or win.width), int(h or win.height)
                if ww < 400 or hh < 300:
                    return
                patch = {"studio_size": [ww, hh], "studio_max": False}
                if WIN:
                    winshell.core_call(WS_PORT, self.token, "settings_save", {"patch": {"ui": patch}})
                else:
                    _core_save_ui(self.token, patch)
            except Exception as e:  # noqa: BLE001
                print(f"Размер студии не запомнил: {e}", file=sys.stderr)
        t = threading.Timer(1.0, later); t.daemon = True; t.start()

    def studio_min(self):
        if self._studio is not None:
            self._studio.minimize()

    def studio_max(self):
        """Развернуть/вернуть. -> развёрнуто ли теперь."""
        def run():
            gw = self._studio_gw()
            if gw is None:
                return False
            if gw.is_maximized():
                gw.unmaximize()
                return False
            gw.maximize()
            return True
        return bool(self._gtk(run))

    def studio_close(self):
        st, self._studio = self._studio, None          # следующее «открыть» создаст окно заново, даже если closed не придёт
        if st is not None:
            st.destroy()

    def _studio_closed(self, win=None):
        if win is None or self._studio is win:         # закрылось старое окно, а новое уже открыто — его не забываем
            self._studio = None
        _ui_log("студия: закрыта")

    # ---------- окно-будильник ----------

    def show_alarm(self, payload=None):
        """Напоминание сработало: окно alarm.html чуть выше центра экрана, поверх всех. Одно на напоминание: повторный
        вызов с тем же id только показывает его, новое напоминание заменяет старое окно. Окно создаётся скрытым и
        показывается после загрузки страницы (не позже чем через 4 с) — уже скруглённым."""
        import webview
        from urllib.parse import urlencode
        p = payload if isinstance(payload, dict) else {}
        rid = str(p.get("id") or "")
        old = getattr(self, "_alarm", None)
        if old is not None:
            if getattr(self, "_alarm_id", "") == rid:
                try:
                    old.show()
                    old.restore()
                except Exception:  # noqa: BLE001
                    pass
                return
            try:
                old.destroy()
            except Exception:  # noqa: BLE001
                pass
        w, h = 520, (556 if int(p.get("att") or 0) else 440)       # с картинками напоминания — выше, под их ряд
        if len(str(p.get("text") or "")) > 30:                     # №383: длинный текст — две-три строки, окну выше
            h += 36 if len(str(p.get("text") or "")) <= 60 else 68
        try:
            if WIN:
                l, t_, r, b = winshell.work_area()
                sw, sh, ox, oy = r - l, b - t_, l, t_
            else:
                scr = webview.screens[0]
                sw, sh, ox, oy = scr.width, scr.height, getattr(scr, "x", 0), getattr(scr, "y", 0)
            x, y = int(ox + (sw - w) / 2), int(oy + (sh - h) / 2.4)
        except Exception:  # noqa: BLE001
            x = y = None
        q = "&" + urlencode({"id": rid, "text": p.get("text", ""), "title": p.get("title", ""), "rep": p.get("repeat_text", ""),
                             "late": "1" if p.get("late") else "", "at": p.get("at", ""), "att": int(p.get("att") or 0)})
        self._alarm_id = rid
        win = webview.create_window(ALARM_TITLE, self._url("alarm.html", q), width=w, height=h, x=x, y=y,
                                    resizable=False, frameless=True, easy_drag=True, on_top=True, focus=True, hidden=True,
                                    background_color="#0c0a12", js_api=self, **_no_shadow())
        self._alarm = win
        win.events.closed += self._alarm_closed
        done = []

        def reveal():
            """Скругляем углы до показа (как у виджета), потом показываем — иначе система запомнит квадрат."""
            if done:
                return
            done.append(1)
            try:
                if WIN:
                    hwnd = int(win.native.Handle.ToInt64())
                    winshell.shape(hwnd, "alarm", ALARM_RADIUS)
                    win.show()
                    self._alarm_keep_top(win)
                    return

                def run():
                    from gi.repository import Gtk
                    gw = next((g for g in Gtk.Window.list_toplevels() if g.get_title() == ALARM_TITLE), None)
                    if gw is None:
                        return False
                    gw.set_skip_taskbar_hint(True)
                    gw.realize()
                    shape_window(gw, "alarm", (w, h), ALARM_RADIUS)
                    gw.show_all()
                    if x is not None:
                        gw.get_window().move(x, y)
                    gw.present()
                    return True
                if not self._gtk(run, timeout=5):
                    win.show()
                self._alarm_keep_top(win)
            except Exception as e:  # noqa: BLE001 — не удалось скруглить: покажем как есть
                print(f"Окно напоминания: {e}", file=sys.stderr)
                try:
                    win.show()
                except Exception:  # noqa: BLE001
                    pass
        import threading
        lock = threading.Lock()

        def reveal_once():
            with lock:
                reveal()
        win.events.loaded += lambda *a: threading.Thread(target=reveal_once, daemon=True).start()
        threading.Timer(4.0, reveal_once).start()       # страница грузилась долго — всё равно показать

    def _alarm_keep_top(self, win):
        """Окно напоминания — всегда над своими окнами (25.10, владелец: при включении компьютера напоминание пряталось
        под виджетом и блокнотом, звук играл, а окна не видно). Виджет, блокнот и «Досуг» тоже «поверх всех» и, появившись
        позже, вставали выше; поэтому, пока напоминание открыто, раз в 1,5 с поднимаем его наверх — без фокуса, чтобы не
        перебивать набор текста. Закрыли или заменили новым — перестаём."""
        import threading

        def lift():
            if WIN:
                winshell.raise_top(int(win.native.Handle.ToInt64()))
                return

            def run():
                from gi.repository import Gtk
                gw = next((g for g in Gtk.Window.list_toplevels() if g.get_title() == ALARM_TITLE and g.get_visible()), None)
                if gw is not None and gw.get_window() is not None:
                    gw.set_keep_above(True)
                    gw.get_window().raise_()
                return True
            self._gtk(run, timeout=2)

        def loop():
            while getattr(self, "_alarm", None) is win:
                try:
                    lift()
                except Exception:  # noqa: BLE001 — окно закрылось между проверкой и подъёмом
                    pass
                time.sleep(1.5)
        threading.Thread(target=loop, daemon=True, name="alarm-top").start()

    def close_alarm(self, rid=""):
        win = getattr(self, "_alarm", None)
        if win is not None and (not rid or rid == getattr(self, "_alarm_id", "")):
            self._alarm = None
            try:
                win.destroy()
            except Exception:  # noqa: BLE001
                pass

    def _alarm_closed(self):
        self._alarm = None

    # ---------- «Закинуть идею»: окно capture.html по одной клавише (ui/hotkey.py) ----------

    def show_capture(self):
        """Окно «Закинуть идею» по центру, поверх всех и в фокусе: картинка из буфера уже приложена, пиши и Enter.
        Одно: открыто — показать и дать фокус. Скругляем до показа, как окно напоминания."""
        import threading
        import webview
        old = getattr(self, "_capture", None)
        if old is not None and getattr(self, "_capture_shown", False):
            # окно уже на экране — то же сочетание прячет его (отзыв 17.10: окно уехало за край экрана, и закрыть его было
            # нечем — крестик оказался за пределами экрана)
            self.close_capture()
            return True
        if old is not None:                            # окно не закрываем, а прячем — второй раз оно появляется сразу
            try:
                self._capture_shown = True
                old.show()
                if not WIN:
                    def place():
                        from gi.repository import Gtk
                        _keep_on_screen(next((g for g in Gtk.Window.list_toplevels() if g.get_title() == CAPTURE_TITLE), None), True)
                        return True
                    self._gtk(place)                       # снова там, где мышь, и целиком на экране
                old.evaluate_js("window.capOpen && capOpen()")
                self._focus_title(CAPTURE_TITLE)
                return True
            except Exception:  # noqa: BLE001
                self._capture = None
        w, h = 600, 440
        try:
            if WIN:
                l, t_, r, b = winshell.work_area()
                sw, sh, ox, oy = r - l, b - t_, l, t_
            else:
                scr = webview.screens[0]
                sw, sh, ox, oy = scr.width, scr.height, getattr(scr, "x", 0), getattr(scr, "y", 0)
            x, y = int(ox + (sw - w) / 2), int(oy + (sh - h) / 2.6)
        except Exception:  # noqa: BLE001
            x = y = None
        self._capture_shown = True
        win = webview.create_window(CAPTURE_TITLE, self._url("capture.html"), width=w, height=h, x=x, y=y,
                                    resizable=False, frameless=True, easy_drag=False, on_top=True, focus=True, hidden=True,
                                    background_color="#0d0b14", js_api=self, **_no_shadow())   # тянуть — за заголовок: в поле выделяют текст
        self._capture = win
        win.events.closed += lambda *a: setattr(self, "_capture", None) if self._capture is win else None
        done, lock = [], threading.Lock()

        def reveal():
            with lock:
                if done:
                    return
                done.append(1)
            try:
                if WIN:
                    winshell.shape(int(win.native.Handle.ToInt64()), "alarm", CAPTURE_RADIUS)
                    win.show()
                    return

                def run():
                    from gi.repository import Gtk
                    gw = next((g for g in Gtk.Window.list_toplevels() if g.get_title() == CAPTURE_TITLE), None)
                    if gw is None:
                        return False
                    gw.set_skip_taskbar_hint(True)
                    gw.realize()
                    shape_window(gw, "alarm", (w, h), CAPTURE_RADIUS)
                    # заголовок двигает оконный менеджер, как у суфлёра: на трёх мониторах окно не прыгает на другой экран
                    self._wm_drag(gw, lambda px, py, ww: py < CAPTURE_BAR and px < ww - CAPTURE_BTNS)
                    gw.show_all()
                    _keep_on_screen(gw, True)              # на том мониторе, где мышь, и целиком на экране
                    _present(gw)
                    return True
                if not self._gtk(run, timeout=5):
                    win.show()
            except Exception as e:  # noqa: BLE001
                print(f"Окно «Закинуть идею»: {e}", file=sys.stderr)
                try:
                    win.show()
                except Exception:  # noqa: BLE001
                    pass
        win.events.loaded += lambda *a: threading.Thread(target=reveal, daemon=True).start()
        threading.Timer(4.0, reveal).start()
        return True

    def _focus_title(self, title):
        """Linux: окно с этим заголовком — вперёд и в фокус (сочетание клавиш нажато в чужой программе)."""
        if WIN:
            return

        def run():
            from gi.repository import Gtk
            gw = next((g for g in Gtk.Window.list_toplevels() if g.get_title() == title), None)
            if gw is not None:
                _present(gw)
            return True
        self._gtk(run)

    def close_capture(self):
        win = getattr(self, "_capture", None)
        self._capture_shown = False
        if win is not None:
            try:
                win.hide()
            except Exception:  # noqa: BLE001
                self._capture = None
                try:
                    win.destroy()
                except Exception:  # noqa: BLE001
                    pass

    def capture_status(self):
        """Студия: включено ли сочетание и работает ли оно на этом рабочем столе. -> {on, key, works, how, command}."""
        import hotkey
        uis = ui_settings()
        key = uis.get("capture_key") or hotkey.DEFAULT
        on = uis.get("capture", True) is not False
        out = {"on": on, "key": key, "works": False, "how": "", "command": hotkey.command(ROOT)}
        if WIN:
            out.update(works=bool(on and getattr(self, "_hk_ok", False)),
                       how="работает в любой программе" if getattr(self, "_hk_ok", False) else
                       ("Windows не дала это сочетание — его заняла другая программа; выберите другое" if on else ""))
            return out
        try:
            if not hotkey.gnome_available():
                out["how"] = "на этом рабочем столе назначьте сочетание сами — командой ниже (Настройки → Клавиатура)"
                return out
            st = hotkey.gnome_state(key)
            out.update(works=bool(on and st["on"] and st["binding"]), conflict=st["conflict"],
                       how="работает в любой программе (это сочетание — в настройках клавиатуры GNOME)" if st["on"] else
                       (f"{key} занято сочетанием «{st['conflict']}»" if st["conflict"] else ""))
        except Exception as e:  # noqa: BLE001
            out["how"] = f"не получилось проверить: {e}"
        return out

    def capture_set(self, on=True, key=""):
        """Студия: включить/выключить «Закинуть идею» одной клавишей, сменить сочетание. -> capture_status()."""
        import hotkey
        key = (key or ui_settings().get("capture_key") or hotkey.DEFAULT).strip()
        if not hotkey.parse(key):
            return dict(self.capture_status(), error=f"не понял «{key}» — нужно с Ctrl, Alt или Win и буквой, например Ctrl+Alt+N")
        try:
            if WIN:
                winshell.core_call(WS_PORT, self.token, "settings_save", {"patch": {"ui": {"capture": bool(on), "capture_key": key}}})
            else:
                _core_save_ui(self.token, {"capture": bool(on), "capture_key": key})
        except Exception as e:  # noqa: BLE001
            print(f"Настройка «Закинуть идею» не сохранилась: {e}", file=sys.stderr)
        err = capture_apply(self, bool(on), key)
        return dict(self.capture_status(), **({"error": err} if err else {}))

    # ---------- суфлёр: окно-карточка у правого края, поверх всех окон ----------

    def open_prompter(self):
        """Окно суфлёра (prompter.html): одно; уже открыто — показать. У правого края рабочей области, сверху; скругляем
        до показа (как напоминание). Windows: окно не попадает в показ экрана и запись (SetWindowDisplayAffinity) —
        собеседник в Zoom, Teams, Телемосте его не увидит."""
        import threading
        import webview
        old = getattr(self, "_prompter", None)
        if old is not None:
            try:
                old.show()
                old.restore()
                return True
            except Exception:  # noqa: BLE001
                self._prompter = None
        w, h = 440, 680
        try:
            if WIN:
                l, t_, r, b = winshell.work_area()
                sw, sh, ox, oy = r - l, b - t_, l, t_
            else:
                scr = webview.screens[0]
                sw, sh, ox, oy = scr.width, scr.height, getattr(scr, "x", 0), getattr(scr, "y", 0)
            h = min(h, int(sh) - 60)
            x, y = int(ox + sw - w - 28), int(oy + 40)
        except Exception:  # noqa: BLE001
            x = y = None
        win = webview.create_window(PROMPTER_TITLE, self._url("prompter.html"), width=w, height=h, x=x, y=y,
                                    resizable=False, frameless=True, easy_drag=False, on_top=True, hidden=True,
                                    background_color="#16131d", js_api=self, **_no_shadow())
        self._prompter = win
        win.events.closed += lambda *a: setattr(self, "_prompter", None)
        done, lock = [], threading.Lock()

        def reveal():
            with lock:
                if done:
                    return
                done.append(1)
            try:
                if WIN:
                    hwnd = int(win.native.Handle.ToInt64())
                    winshell.shape(hwnd, "prompter", PROMPTER_RADIUS)
                    winshell.no_capture(hwnd)
                    win.show()
                    return

                def run():
                    from gi.repository import Gtk
                    gw = next((g for g in Gtk.Window.list_toplevels() if g.get_title() == PROMPTER_TITLE), None)
                    if gw is None:
                        return False
                    gw.set_skip_taskbar_hint(False)
                    gw.realize()
                    shape_window(gw, "prompter", (w, h), PROMPTER_RADIUS)
                    # заголовок (кроме кнопок справа) двигает оконный менеджер — верно на любом из мониторов
                    self._wm_drag(gw, lambda px, py, ww: py < PROMPTER_BAR and px < ww - PROMPTER_BTNS)
                    gw.show_all()
                    if x is not None:
                        gw.get_window().move(x, y)
                    gw.present()
                    return True
                if not self._gtk(run, timeout=5):
                    win.show()
            except Exception as e:  # noqa: BLE001 — не удалось скруглить: покажем как есть
                print(f"Окно суфлёра: {e}", file=sys.stderr)
                try:
                    win.show()
                except Exception:  # noqa: BLE001
                    pass
        win.events.loaded += lambda *a: threading.Thread(target=reveal, daemon=True).start()
        threading.Timer(4.0, reveal).start()
        return True

    # ---------- блокнот: окно рядом с карточкой виджета, ездит вместе с ней ----------
    # Окно = лист (PAD_W) + зазор до карточки (PAD_GAP), в зазоре — два «крепления» (форма окна: pad_rects; рисует их
    # pad.html). Окно сплошное, как суфлёр: прозрачность окна на Ubuntu не трогаем (урок 0.38.95).

    def _pad_geom(self):
        """-> dict(x, y, w, h, side, gap, clips, dy): окно блокнота у карточки — с той стороны, где больше места
        (к середине экрана), той же верхней кромкой; не выходит за экран. w — ширина листа, окно шире на gap;
        clips — [(y, высота)] креплений в окне (логические px), на высоте карточки; dy — сдвиг окна от верха карточки."""
        z = ZOOM[0] or 1.0
        bw, bh = self._pad_base()                         # свой размер листа (растянули за уголок) — ui.pad_w, ui.pad_h
        w = int(round(max(PAD_W_MIN, min(PAD_W_MAX, float(bw) if bw else PAD_W)) * z))
        gap, clip = int(round(PAD_GAP * z)), int(round(PAD_CLIP * z))
        cw, ch = SIZES["card"]
        h = int(round(max(PAD_H_MIN, float(bh)) * z)) if bh else max(ch, int(round(PAD_MIN_H * z)))
        real = self._card_h()                              # настоящая высота окна виджета: крепления — только на нём
        if real and 0 < real < ch:
            ch = real
        cx, cy = self.get_pos("card")
        mx, my, mw, mh = 0, 0, 1 << 15, 1 << 15
        try:
            if WIN:
                l, t_, r, b = winshell.work_area(self._hwnd("card"))     # монитор виджета, а не основной (№161)
                mx, my, mw, mh = l, t_, r - l, b - t_
            else:
                from gi.repository import Gdk
                g = Gdk.Display.get_default().get_monitor_at_point(int(cx) + cw // 2, int(cy) + ch // 2).get_workarea()
                mx, my, mw, mh = g.x, g.y, g.width, g.height
        except Exception:  # noqa: BLE001
            pass
        pref = self._pad_pref_side()
        side = pref if pref in ("left", "right") else ("left" if cx + cw / 2 > mx + mw / 2 else "right")
        x = cx - gap - w if side == "left" else cx + cw
        if x < mx or x + w + gap > mx + mw:                # с этой стороны не помещается — с другой
            side = "right" if side == "left" else "left"
            x = cx - gap - w if side == "left" else cx + cw
        h = min(h, mh - 16)
        y = max(my + 8, min(int(cy), my + mh - h - 8))
        dy = y - int(cy)
        # крепления — там, где лист и виджет рядом (22.10, владелец: «лист растянул — нижний крепёж смотрится оторванным»):
        # на 20 % и 80 % высоты виджета, но не ниже его края и не ниже края листа
        top = int(cy) - y
        lo, hi = max(0, top) + 6, min(h, top + ch) - clip - 6
        clips = [(min(hi, max(lo, top + int(ch * k) - clip // 2)), clip) for k in (0.2, 0.8)] if hi > lo else []
        clips = [c for i, c in enumerate(clips) if not i or c[0] - clips[i - 1][0] >= 2 * clip]
        return {"x": int(x), "y": int(y), "w": w, "h": h, "side": side, "gap": gap, "clips": clips, "dy": dy}

    def _pad_pref_side(self):
        """Сторона блокнота, выбранная кнопкой ⇄ на его панели (ui.pad_side: "left" | "right"), или "auto" — к середине
        экрана. Владелец 24.10: «редактор стал справа от Лиры, раньше был слева — можно переключать?» Не помещается
        с выбранной стороны — встаёт с другой (_pad_geom)."""
        s = getattr(self, "_pad_side_pref", None)
        if s is None:
            try:
                s = ui_settings().get("pad_side") or "auto"
            except Exception:  # noqa: BLE001
                s = "auto"
            self._pad_side_pref = s
        return s

    def _pad_base(self):
        """Свой размер листа при масштабе 100 % ([ш, в] или [None, None] — как задумано). Читается из настроек один раз."""
        s = getattr(self, "_pad_size", None)
        if s is None:
            u = ui_settings()
            s = self._pad_size = [u.get("pad_w"), u.get("pad_h")]
        return s

    def _card_h(self):
        """Высота окна виджета сейчас (логические px) или 0 — не узнали. По ней — крепления блокнота: размер в SIZES бывает
        больше видимого (растягивали карточку, окно не дошло до размера)."""
        try:
            if WIN:
                hw = self._hwnd("card")
                if hw:
                    return int(round(winshell.rect(hw)[3] / winshell.scale(hw)))
                return 0
            gw = self._gw("card")
            return int(self._gtk(lambda: gw.get_size()[1]) or 0) if gw is not None else 0
        except Exception:  # noqa: BLE001
            return 0

    def pad_size(self):
        """Текущий размер листа в px окна (без зазора) — для растягивания за уголок (pad.js)."""
        g = getattr(self, "_pad_g", None) or self._pad_geom()
        return [g["w"], g["h"]]

    def pad_resize(self, w, h, final=False):
        """Растянули блокнот за нижний уголок (22.10: «чтобы, как виджет, можно было менять размер»). w, h — желаемый
        размер листа сейчас (px окна); лист остаётся прижат к виджету, верх — на месте. w или h = 0 — как задумано.
        -> [ш, в] при 100 % (pad.js сохраняет в ui.pad_w / ui.pad_h) или [None, None]."""
        z = ZOOM[0] or 1.0
        self._pad_size = [None, None] if not w or not h else \
            [round(max(PAD_W_MIN, min(PAD_W_MAX, float(w) / z))), round(max(PAD_H_MIN, float(h) / z))]
        g = self._pad_geom()
        self._pad_g, self._pad_side = g, g["side"]
        self._pad_apply(g, final)
        return list(self._pad_size)

    def pad_flip(self):
        """Кнопка ⇄ на панели блокнота: лист — на другую сторону от виджета, и так впредь (pad.js сохраняет ui.pad_side).
        -> сторона, где лист оказался (если с той стороны не поместился — прежняя)."""
        cur = getattr(self, "_pad_side", None) or self._pad_geom()["side"]
        self._pad_side_pref = "right" if cur == "left" else "left"
        g = self._pad_geom()
        self._pad_g, self._pad_side = g, g["side"]
        self._pad_apply(g, True)
        return g["side"]

    def _pad_apply(self, g, final=False):
        """Окно блокнота — по геометрии g: размер, место у виджета, форма; final — и страница (стороной и креплениями)."""
        z = ZOOM[0] or 1.0
        W, H = g["w"] + g["gap"], g["h"]
        try:
            if WIN:
                hw = winshell.hwnd(PAD_TITLE)
                win = getattr(self, "_pad", None)
                if win is not None:
                    try:
                        form = win.native
                        from System import Action
                        from System.Drawing import Size
                        form.Invoke(Action(lambda f=form: setattr(f, "MinimumSize", Size(1, 1))))
                    except Exception:  # noqa: BLE001
                        pass
                    win.resize(W, H)
                if hw:
                    winshell.move(hw, g["x"], g["y"])
                self._pad_shape(g)
            else:
                r = int(round(PAD_RADIUS * z))

                def run():
                    from gi.repository import Gtk
                    gw = next((x for x in Gtk.Window.list_toplevels() if x.get_title() == PAD_TITLE), None)
                    if gw is None:
                        return False
                    gw.set_size_request(W, H)
                    gw.resize(W, H)
                    if gw.get_window() is not None:
                        gw.get_window().move(g["x"], g["y"])
                        k = gw.get_window().get_scale_factor()
                        shape_window(gw, "pad", rects=pad_rects(g["side"], g["w"] * k, g["h"] * k, g["gap"] * k,
                                                                [(y * k, c * k) for y, c in g["clips"]], r * k))
                    return True
                self._gtk(run, timeout=5)
            if final:
                self._pad_js(self._pad_cfg_js(g))
        except Exception as e:  # noqa: BLE001
            print(f"Размер блокнота: {e}", file=sys.stderr)

    def pad_state(self):
        win = getattr(self, "_pad", None)
        return {"open": bool(win is not None and getattr(self, "_pad_on", False)), "side": getattr(self, "_pad_side", "left")}

    def pad_toggle(self, mode="notes"):
        """Кнопка блокнота (или «Досуга», mode="play") в углу виджета: открыть / закрыть (страница сама «въезжает» и
        «уезжает»). Лист открыт в другом режиме — не закрываем, а переключаем: блокнот ↔ игры."""
        mode = "play" if mode == "play" else "notes"
        if getattr(self, "_pad_on", False) and self._pad_dead():    # №375: окно есть, а страницы в нём нет — заново
            self._pad_reset("нажали кнопку")
        if getattr(self, "_pad_on", False):
            if not self._pad_ready():                              # ещё грузится — второй клик не закрывает пустое окно
                return True
            if getattr(self, "_pad_mode", "notes") != mode:
                self._pad_mode = mode
                self._pad_js(f"window.padMode && padMode('{mode}')")
                self._js(f"window.padMark && padMark(true, '{mode}')")
                return True
            self._pad_js("window.padClose && padClose()")
            return False
        return self.pad_open(mode)

    def play_open(self, game=""):
        """«Досуг»: «Лира, давай поиграем» (ядро — событие window: play) — лист у виджета с полкой игр;
        game — сразу эта игра («поиграем в змейку» -> "snake")."""
        game = game if re.fullmatch(r"[a-z]{2,12}", str(game or "")) else ""
        if getattr(self, "_pad_on", False):
            self._pad_mode = "play"
            self._pad_js(f"window.padGame && padGame('{game}')")
            self._js("window.padMark && padMark(true, 'play')")
            return True
        self._pad_game = game
        return self.pad_open("play")

    # №375 (28.10, Windows): WebView2 не создал страницу («Класс не зарегистрирован») — окно блокнота пустое, а кнопка
    # больше ничего не делает: «закрыть» уходило странице, которой нет. Страница поднялась — events.loaded; нет её
    # через PAD_WAIT с — окно убираем и создаём заново (один раз), не вышло — говорим у виджета, кнопка снова работает.
    PAD_WAIT = 12.0

    def _pad_ready(self):
        win = getattr(self, "_pad", None)
        try:
            return win is not None and win.events.loaded.is_set()
        except Exception:  # noqa: BLE001
            return False

    def _pad_dead(self):
        return getattr(self, "_pad", None) is not None and not self._pad_ready() and \
            time.monotonic() - getattr(self, "_pad_born", 0) > self.PAD_WAIT

    def _pad_reset(self, why=""):
        win, self._pad, self._pad_on = getattr(self, "_pad", None), None, False
        print(f"Окно блокнота: страница не поднялась ({why}) — убираю окно", file=sys.stderr)
        _ui_log(f"блокнот: страница не поднялась ({why})")
        if win is not None:
            try:
                win.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._js("window.padMark && padMark(false)")

    def _pad_watch(self, win, mode):
        """Через PAD_WAIT с после создания: страница не поднялась — убрать окно; первый раз — создать заново."""
        if getattr(self, "_pad", None) is not win or self._pad_ready():
            return
        self._pad_reset(f"ждал {self.PAD_WAIT:g} с")
        tries = getattr(self, "_pad_tries", 0)
        if tries < 1 and self.mode == "card":
            self._pad_tries = tries + 1
            self.pad_open(mode)
        else:
            self._pad_tries = 0
            self._js("window.padFail && padFail('Блокнот не открылся: окно Windows не создало страницу. Нажмите ещё раз; "
                     "не поможет — перезапустите Dewiar из трея')")

    def pad_mode_mark(self, mode):
        """Страница блокнота сама сменила режим (кнопки 🎮 и «к блокноту» на листе) — отметить у виджета."""
        self._pad_mode = "play" if mode == "play" else "notes"
        self._js(f"window.padMark && padMark(true, '{self._pad_mode}')")
        return True

    def _pad_cfg_js(self, g):
        import json
        return f"window.padCfg && padCfg({json.dumps({'side': g['side'], 'gap': g['gap'], 'clips': g['clips']})})"

    def _pad_shape(self, g):
        """Форма окна под геометрию g: лист + крепления (Linux — SHAPE, Windows — регион окна)."""
        r = int(round(PAD_RADIUS * (ZOOM[0] or 1.0)))
        if WIN:
            hw = winshell.hwnd(PAD_TITLE)
            if hw:
                k = winshell.scale(hw)
                winshell.shape_rects(hw, pad_rects(g["side"], int(g["w"] * k), int(g["h"] * k), int(g["gap"] * k),
                                                   [(y * k, c * k) for y, c in g["clips"]], int(r * k)))
            return

        def run():
            from gi.repository import Gtk
            gw = next((x for x in Gtk.Window.list_toplevels() if x.get_title() == PAD_TITLE), None)
            if gw is None or gw.get_window() is None:
                return False
            k = gw.get_window().get_scale_factor()
            shape_window(gw, "pad", rects=pad_rects(g["side"], g["w"] * k, g["h"] * k, g["gap"] * k, [(y * k, c * k) for y, c in g["clips"]], r * k))
            return True
        self._gtk(run, timeout=3)

    def pad_open(self, mode="notes"):
        """Окно блокнота (pad.html): одно на всё время; открыть — поставить у карточки и показать.
        mode="play" — сразу «Досуг» (полка игр в том же листе)."""
        mode = "play" if mode == "play" else "notes"
        self._pad_mode = mode
        import threading
        import webview
        if self.mode != "card":
            return False
        self._stay()                                 # открыл блокнот у показавшегося из трея виджета — он остаётся
        g = self._pad_geom()
        self._pad_g, self._pad_side, self._pad_on = g, g["side"], True
        W = g["w"] + g["gap"]
        win = getattr(self, "_pad", None)
        if win is not None and self._pad_dead():
            self._pad_reset("открыть снова")
            win = None
        if win is not None:
            try:
                if WIN:
                    win.show()
                    self._pad_place(g["x"], g["y"])          # после показа: скрытая форма возвращается на прежнее место
                    self._pad_shape(g)
                else:
                    self._pad_shape(g)
                    # 21.10, Ubuntu: «первый раз открылся, после скрытия виджета — сколько ни нажимаю, не открывается»:
                    # win.show() pywebview окно, спрятанное вместе с виджетом, не возвращал. Показываем так же, как в первый
                    # раз, — сами, через GTK (show_all, поверх, на место)
                    def run():
                        from gi.repository import Gtk
                        gw = next((x for x in Gtk.Window.list_toplevels() if x.get_title() == PAD_TITLE), None)
                        if gw is None:
                            return False
                        gw.show_all()
                        gw.present()
                        if gw.get_window() is not None:
                            gw.get_window().move(g["x"], g["y"])
                        return True
                    if not self._gtk(run, timeout=5):
                        raise RuntimeError("окна блокнота нет")
                game, self._pad_game = getattr(self, "_pad_game", ""), ""
                self._pad_js(self._pad_cfg_js(g) + f"; window.padShown && padShown('{g['side']}'); window.padMode && padMode('{mode}')"
                             + (f"; window.padGame && padGame('{game}')" if mode == "play" and game else ""))
                self._js(f"window.padMark && padMark(true, '{mode}')")
                return True
            except Exception as e:  # noqa: BLE001
                print(f"Окно блокнота: открыть снова не вышло ({e}) — создаю заново", file=sys.stderr)
                self._pad = None
        skin, light = ui_skin()
        import json
        q = "&cfg=" + urllib.parse.quote(json.dumps({"side": g["side"], "gap": g["gap"], "clips": g["clips"]})) + "&skin=" + urllib.parse.quote(skin) \
            + ("&mode=play" if mode == "play" else "") + ("&game=" + getattr(self, "_pad_game", "") if mode == "play" and getattr(self, "_pad_game", "") else "")
        self._pad_game = ""
        win = webview.create_window(PAD_TITLE, self._url("pad.html", q), width=W, height=g["h"], x=g["x"], y=g["y"],
                                    resizable=False, frameless=True, easy_drag=False, on_top=True, hidden=True,
                                    background_color="#dbe5f1" if light else "#12131b", js_api=self, **_no_shadow())
        self._pad, self._pad_born = win, time.monotonic()
        win.events.closed += lambda *a: (setattr(self, "_pad", None), setattr(self, "_pad_on", False)) if getattr(self, "_pad", None) is win else None
        win.events.loaded += lambda *a: setattr(self, "_pad_tries", 0)
        threading.Timer(self.PAD_WAIT, self._pad_watch, args=(win, mode)).start()
        done, lock = [], threading.Lock()

        def reveal():
            with lock:
                if done:
                    return
                done.append(1)
            try:
                if WIN:
                    win.show()
                    self._pad_place(g["x"], g["y"])          # на свой монитор — и после показа (№161)
                    self._pad_shape(g)
                else:
                    def run():
                        from gi.repository import Gtk
                        gw = next((x for x in Gtk.Window.list_toplevels() if x.get_title() == PAD_TITLE), None)
                        if gw is None:
                            return False
                        gw.set_skip_taskbar_hint(True)
                        gw.set_skip_pager_hint(True)
                        gw.realize()
                        k = gw.get_window().get_scale_factor() if gw.get_window() else 1
                        r = int(round(PAD_RADIUS * (ZOOM[0] or 1.0)))
                        shape_window(gw, "pad", rects=pad_rects(g["side"], g["w"] * k, g["h"] * k, g["gap"] * k,
                                                                [(y * k, c * k) for y, c in g["clips"]], r * k))
                        gw.show_all()
                        gw.get_window().move(g["x"], g["y"])
                        return True
                    if not self._gtk(run, timeout=5):
                        win.show()
                self._js("window.padMark && padMark(true, '" + mode + "')")
            except Exception as e:  # noqa: BLE001 — не скруглилось: покажем как есть
                print(f"Окно блокнота: {e}", file=sys.stderr)
                try:
                    win.show()
                except Exception:  # noqa: BLE001
                    pass
        win.events.loaded += lambda *a: threading.Thread(target=reveal, daemon=True).start()
        threading.Timer(4.0, reveal).start()
        return True

    def pad_full(self, on):
        """Игра в листе «Досуг» — на весь экран (кнопка в игре; 24.10, владелец: «в играх на компьютере открыть на весь экран»).
        Выключили — лист снова у виджета, с формой, креплениями и прежним размером (_pad_apply)."""
        on, prev = bool(on), bool(getattr(self, "_pad_full", False))
        self._pad_full = on
        if on == prev:
            return on
        try:
            if WIN:
                # 25.10, владелец: «во весь экран — просто убирает скругления, и всё»: toggle_fullscreen у окна без рамки
                # (WinForms) ничего не делает — растягиваем сами на весь монитор, где лист, и снимаем форму
                win, hw = getattr(self, "_pad", None), winshell.hwnd(PAD_TITLE)
                if on and win is not None and hw:
                    mon = winshell.monitor_area(hw)
                    if mon:
                        l, t, r, b = mon
                        try:
                            form = win.native
                            from System import Action
                            from System.Drawing import Size
                            form.Invoke(Action(lambda f=form: (setattr(f, "MinimumSize", Size(1, 1)), setattr(f, "MaximumSize", Size(0, 0)))))
                        except Exception:  # noqa: BLE001
                            pass
                        win.resize(int(round(r - l)), int(round(b - t)))
                        winshell.move(hw, l, t)
                    import threading
                    threading.Timer(0.35, lambda: winshell.shape_rects(hw, [(0, 0, 20000, 20000)])).start()
            else:
                from gi.repository import GLib

                def run():
                    from gi.repository import Gtk
                    gw = next((x for x in Gtk.Window.list_toplevels() if x.get_title() == PAD_TITLE), None)
                    if gw is None:
                        return False
                    if on:
                        gw.fullscreen()

                        def flat():
                            gdkw = gw.get_window()
                            if gdkw is not None:
                                k = gdkw.get_scale_factor()
                                shape_window(gw, "rect", (gdkw.get_width() * k, gdkw.get_height() * k))
                            return False
                        GLib.timeout_add(350, flat)
                    else:
                        gw.unfullscreen()
                    return True
                self._gtk(run, timeout=5)
            if on:
                self._pad_js("window.padCfg && padCfg({side: 'left', gap: 0, clips: []})")
            else:
                import threading
                g = self._pad_geom()
                self._pad_g, self._pad_side = g, g["side"]
                threading.Timer(0.35, lambda: self._pad_apply(g, True)).start()
        except Exception as e:  # noqa: BLE001
            print(f"Лист на весь экран: {e}", file=sys.stderr)
        return on

    def pad_hide(self):
        """Страница доиграла «уезжание» — спрятать окно (не закрывать: следующее открытие мгновенное)."""
        if getattr(self, "_pad_full", False):
            self.pad_full(False)
        self._pad_on = False
        win = getattr(self, "_pad", None)
        if win is not None:
            try:
                if WIN:
                    win.hide()
                else:                                       # прячем тем же путём, каким показываем (GTK) — см. pad_open
                    def run():
                        from gi.repository import Gtk
                        gw = next((x for x in Gtk.Window.list_toplevels() if x.get_title() == PAD_TITLE), None)
                        if gw is not None:
                            gw.hide()
                        return True
                    self._gtk(run, timeout=3)
            except Exception:  # noqa: BLE001
                pass
        self._js("window.padMark && padMark(false)")
        return True

    def _pad_place(self, x, y):
        if WIN:
            hw = winshell.hwnd(PAD_TITLE)
            if hw:
                winshell.move(hw, x, y)
            return
        from gi.repository import GLib

        def mv():
            from gi.repository import Gtk
            gw = next((g for g in Gtk.Window.list_toplevels() if g.get_title() == PAD_TITLE), None)
            if gw is not None and gw.get_window() is not None:
                gw.get_window().move(int(x), int(y))
            return False
        GLib.idle_add(mv, priority=GLib.PRIORITY_HIGH_IDLE)

    def _pad_follow_at(self, x, y):
        """Во время перетаскивания: карточка будет в (x, y) — блокнот рядом, той же стороной и тем же сдвигом."""
        g = getattr(self, "_pad_g", None)
        if not g or getattr(self, "_pad_full", False):        # игра на весь экран — лист не ездит за виджетом
            return
        try:
            px = x - g["gap"] - g["w"] if g["side"] == "left" else x + SIZES["card"][0]
            self._pad_place(int(px), int(y) + g["dy"])
        except Exception:  # noqa: BLE001
            pass

    def _pad_js(self, code):
        import threading
        win = getattr(self, "_pad", None)
        if win is not None:
            def run():
                try:
                    win.evaluate_js(code)
                except Exception as e:  # noqa: BLE001 — страницы нет (№375): не висим, следующий клик создаст окно заново
                    print(f"Окно блокнота: {e}", file=sys.stderr)
            threading.Thread(target=run, daemon=True).start()

    def close_prompter(self):
        win = getattr(self, "_prompter", None)
        self._prompter = None
        if win is not None:
            try:
                win.destroy()
            except Exception:  # noqa: BLE001
                pass
        return True


def _raise_idle_priority():
    """Linux: pywebview выполняет всё с окнами (показать, спрятать, открыть студию, ответить странице) через
    GLib.idle_add — с самым низким приоритетом главного цикла, «когда больше нечего делать». Пока облик анимируется
    с программной отрисовкой, а то и в трёх окнах сразу, цикл может так и не освободиться — и кнопки «Память»,
    «Календарь», «Настройки», пункты меню в трее молча не работают до перезапуска интерфейса. Ставим эти вызовы
    выше перерисовки (HIGH_IDLE): они короткие. Подменяем glib внутри webview.platforms.gtk — это устройство
    pywebview; если оно другое, ничего не трогаем. Вызывать до webview.start."""
    try:
        from gi.repository import GLib
        import webview.platforms.gtk as G

        class _GLib:
            def __getattr__(self, k):
                return getattr(GLib, k)

            @staticmethod
            def idle_add(fn, *a, **kw):
                kw.setdefault("priority", GLib.PRIORITY_HIGH_IDLE)
                return GLib.idle_add(fn, *a, **kw)
        if getattr(G, "glib", None) is GLib:
            G.glib = _GLib()
    except Exception as e:  # noqa: BLE001
        print(f"Приоритет окон не поднят: {e}", file=sys.stderr)


def _ui_log(text):
    """Строка в журнал интерфейса STATE_DIR/logs/ui.log (он попадает в отчёт разработчику). -> путь или None."""
    try:
        from settings import STATE_DIR
        d = STATE_DIR / "logs"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "ui.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
        return d / "ui.log"
    except OSError:
        return None


def _loop_watchdog(api):
    """Linux: сторож главного цикла окон (поток ui-watchdog). Каждые 5 с ставит в цикл две отметки: обычного
    приоритета и самого низкого. Обычная не выполнилась 40 с — виджет «замёрз» (кнопки и трей не работают):
    пишем в ui.log, где застряли потоки, и перезапускаем интерфейс (ядро и разговор не прерываются; код выхода 3).
    Низкая не выполняется 60 с — цикл занят перерисовкой: только запись в журнал.
    DEWIAR_UI_NO_RESTART — только журнал, без перезапуска."""
    import faulthandler
    from gi.repository import GLib
    beat = {"t": time.monotonic(), "idle": time.monotonic()}

    def tick():
        beat["t"] = time.monotonic()
        return False

    def idle_tick():
        beat["idle"] = time.monotonic()
        return False
    warned, n, big = False, 0, [0]
    while True:
        GLib.idle_add(tick, priority=GLib.PRIORITY_DEFAULT)
        GLib.idle_add(idle_tick)                          # самый низкий приоритет: проверяем, бывает ли цикл свободен
        time.sleep(5)
        now = time.monotonic()
        if now - beat["idle"] > 60 and not warned:
            warned = True
            _ui_log(f"главный цикл окон занят перерисовкой уже {now - beat['idle']:.0f} с (вызовы окон подняты в приоритете)")
        elif now - beat["idle"] < 10:
            warned = False
        if now - beat["t"] > 40:
            f = _ui_log(f"главный цикл окон не отвечает {now - beat['t']:.0f} с — перезапускаю интерфейс. Потоки:")
            try:
                if f:
                    with open(f, "a", encoding="utf-8") as fh:
                        faulthandler.dump_traceback(file=fh, all_threads=True)
            except (OSError, ValueError):
                pass
            if os.environ.get("DEWIAR_UI_NO_RESTART"):
                beat["t"] = time.monotonic()
                continue
            _respawn()
        n += 1
        if n % 12 == 0 and _ui_too_big(api, big):            # раз в минуту: окна не разрослись ли (утечка WebKit)
            _respawn()


def _ui_too_big(api, big):
    """Окна Dewiar (этот процесс и его WebKit) заняли больше мягкого потолка (memcap.caps("ui")) две минуты подряд —
    значит, память утекает: перезапустить окна (ядро и разговор не прерываются), пока не замедлился весь компьютер.
    Студия открыта — не трогаем (там может быть несохранённое), только запись в журнал."""
    try:
        import memcap
        gb = memcap.tree_gb(os.getpid())
        soft = memcap.caps("ui")[0]
    except Exception:  # noqa: BLE001
        return False
    big[0] = big[0] + 1 if gb > soft else 0
    if big[0] < 2:
        return False
    if api._studio is not None or os.environ.get("DEWIAR_UI_NO_RESTART"):
        if big[0] == 2:
            _ui_log(f"окна занимают {gb:.1f} ГБ (больше {soft:.1f}) — открыта студия, перезапуск окон отложен")
        return False
    _ui_log(f"окна занимают {gb:.1f} ГБ (больше {soft:.1f}) — перезапускаю окна, чтобы не тормозил компьютер")
    return True


def _respawn():
    """Перезапуск интерфейса: новый процесс — через 2 с, когда этот уже отпустит замок экземпляра; код выхода 3."""
    launcher = ROOT / "dewiar"
    cmd = ["/bin/sh", str(launcher)] if launcher.is_file() else [sys.executable, str(Path(__file__).resolve())]
    env = {k: v for k, v in os.environ.items() if k != "DEWIAR_BOX"}     # новые окна — в новую коробку (_own_box)
    try:
        subprocess.Popen(["/bin/sh", "-c", 'sleep 2; exec "$@"', "dewiar-ui"] + cmd, start_new_session=True, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        os._exit(3)


class LinuxTray:
    """Значок в области уведомлений Ubuntu (AppIndicator; Ayatana или старый). Нет библиотеки — значка нет, всё
    остальное работает. Создавать в главном потоке GTK; пункты меню выполняются в отдельных потоках.
    «Убрать в трей» — виджет спрятан, ассистент слушает; «Выйти из Dewiar» — завершает и ядро (Api.quit_all),
    иначе служба ядра продолжала бы слушать и отвечать без окна."""

    def __init__(self, api):
        import gi
        try:
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AI
        except (ValueError, ImportError):
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3 as AI
        from gi.repository import Gtk
        icon = ROOT / "icons" / "dewiar-tray.png"           # белый знак — панель Ubuntu тёмная
        if not icon.exists():
            icon = ROOT / "icons" / "dewiar-64.png"
        self.ind = AI.Indicator.new("dewiar", str(icon), AI.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_title("Dewiar")
        menu = Gtk.Menu()
        for title, fn in (("Показать Dewiar", api.from_tray), ("Закинуть идею", api.show_capture), ("Убрать в трей", api.to_tray),
                          ("Студия", lambda: api.open_settings()), (None, None), ("Выйти из Dewiar", api.quit_all)):
            if title is None:
                menu.append(Gtk.SeparatorMenuItem())
                continue
            it = Gtk.MenuItem(label=title)
            it.connect("activate", lambda _w, f=fn: __import__("threading").Thread(target=f, daemon=True).start())
            menu.append(it)
            if title == "Показать Dewiar":
                self.ind.set_secondary_activate_target(it)        # щелчок колёсиком/средней — сразу показать
        menu.show_all()
        self.ind.set_menu(menu)
        self.ind.set_status(AI.IndicatorStatus.ACTIVE)


_TRAY = []


def _keep_on_screen(gw, center=False):
    """Окно целиком на экране (отзыв 17.10: окно «Закинуть идею» уехало на другой монитор, верх — за краем экрана,
    крестик недоступен). center — поставить по центру монитора, где сейчас мышь (там, где человек работает). Ещё раз
    проверяем после того, как оконный менеджер расставит окно (через 150 и 600 мс). Главный поток GTK."""
    if gw is None:
        return
    from gi.repository import Gdk, GLib

    def fit(first):
        try:
            gdkw = gw.get_window()
            if gdkw is None:
                return False
            disp = Gdk.Display.get_default()
            w, h = gw.get_size()
            if first and center:
                _, px, py = disp.get_default_seat().get_pointer().get_position()
                mon = disp.get_monitor_at_point(px, py)
            else:
                x0, y0 = gdkw.get_root_origin()
                mon = disp.get_monitor_at_point(x0 + w // 2, max(y0, 0) + h // 2)
            g = mon.get_workarea()
            if first and center:
                x, y = g.x + (g.width - w) // 2, g.y + int((g.height - h) / 2.6)
            else:
                x, y = gdkw.get_root_origin()
            nx = max(g.x, min(x, g.x + g.width - w))
            ny = max(g.y, min(y, g.y + g.height - h))
            if (nx, ny) != (x, y) or (first and center):
                gw.move(nx, ny)
                gdkw.move(nx, ny)
        except Exception as e:  # noqa: BLE001
            print(f"Окно на экране: {e}", file=sys.stderr)
        return False
    fit(True)
    GLib.timeout_add(150, lambda: fit(False))
    GLib.timeout_add(600, lambda: fit(False))


def _present(gw):
    """Окно — вперёд и в фокус. Сочетание клавиш нажато в чужой программе — GNOME не даёт фокус «просто так»: время
    события берём у X-сервера (present_with_time), иначе окно лишь мигнёт «Dewiar готов»."""
    try:
        import gi
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11
        gdkw = gw.get_window()
        if isinstance(gdkw, GdkX11.X11Window):
            gw.present_with_time(GdkX11.x11_get_server_time(gdkw))
            return
    except Exception:  # noqa: BLE001
        pass
    gw.present()


def _core_save_ui(token, patch):
    """Сохранить ui.* в настройках ядра (Linux: тот же WebSocket, что у страниц)."""
    from websockets.sync.client import connect
    with connect(f"ws://127.0.0.1:{WS_PORT}", open_timeout=3, close_timeout=1) as ws:
        ws.send(json.dumps({"cmd": "hello", "token": token}))
        ws.recv(timeout=3)
        ws.send(json.dumps({"id": 1, "cmd": "settings_save", "args": {"patch": {"ui": patch}}}))
        ws.recv(timeout=3)


def capture_boot(api, uis):
    """При запуске: сочетание «Закинуть идею» включено — назначить. GNOME: уже назначено нами с той же клавишей и
    командой — не трогаем; Windows — регистрируем каждый запуск (живёт, пока жив процесс)."""
    import hotkey
    key = uis.get("capture_key") or hotkey.DEFAULT
    try:
        if not WIN and hotkey.gnome_available():
            st = hotkey.gnome_state(key)
            if st["on"] and st["binding"] == hotkey.to_gnome(key) and st["command"] == hotkey.command(ROOT):
                return
        err = capture_apply(api, True, key)
        if err:
            print(f"«Закинуть идею»: {err}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"«Закинуть идею»: {e}", file=sys.stderr)


def capture_apply(api, on, key):
    """Назначить (или снять) сочетание «Закинуть идею»: Windows — RegisterHotKey значка в трее, Linux/GNOME — своё
    сочетание GNOME с командой «dewiar --capture». -> текст ошибки или ""."""
    import hotkey
    try:
        if WIN:
            tray = getattr(api, "_tray", None)
            if tray is None or not hasattr(tray, "hotkey"):
                return "нет значка в трее — сочетание не назначить"
            spec = hotkey.to_win(key) if on else None
            api._hk_ok = bool(tray.hotkey(spec[0] if spec else None, spec[1] if spec else 0, api.show_capture)) and on
            return "" if api._hk_ok or not on else f"{key} уже занято другой программой — выберите другое сочетание"
        if not hotkey.gnome_available():
            return ""
        ok, msg = hotkey.gnome_set(on, key, hotkey.command(ROOT))
        return "" if ok else msg
    except Exception as e:  # noqa: BLE001 — сочетание не главное: программа работает и без него
        print(f"Сочетание «Закинуть идею»: {e}", file=sys.stderr)
        return str(e)


def _no_shadow():
    """Окна без рамки режем по форме (скруглённая карточка, круг) — им не нужна тень DWM: с ней pywebview 6 включает
    рамку DWM, и Windows перестаёт резать окно по форме. У старых pywebview параметра нет — тогда ничего не передаём."""
    import inspect
    import webview
    try:
        return {"shadow": False} if "shadow" in inspect.signature(webview.create_window).parameters else {}
    except (TypeError, ValueError):
        return {}


def _notify(text):
    """Уведомление системы: Windows — сообщение от значка в трее (значка нет — молча), Linux — notify-send,
    а без него — тот же вызов напрямую по D-Bus (gdbus)."""
    if WIN:
        if _TRAY:
            _TRAY[0].notify(text)
        return
    try:
        if shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "-a", "Dewiar", "Dewiar", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("gdbus"):
            subprocess.Popen(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications", "--object-path",
                              "/org/freedesktop/Notifications", "--method", "org.freedesktop.Notifications.Notify",
                              "Dewiar", "0", "dewiar-assistant", "Dewiar", text, "[]", "{}", "-1"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def _disk_version():
    """Версия, которая сейчас лежит на диске (core/version.py), — после обновления она новее UI_VERSION."""
    try:
        import re
        return re.search(r'^VERSION = "([^"]+)"', (ROOT / "core" / "version.py").read_text(encoding="utf-8"), re.M).group(1)
    except (OSError, AttributeError):
        return ""


def watch_version(api):
    """Linux: пакет обновили мимо студии (например, из терминала), а интерфейс ещё старый (новые страницы + старая
    программа = сломанные кнопки). Раз в 15 с сверяем версию на диске; она сменилась — перезапускаемся новой.
    Предохранитель от круга перезапусков: только настоящий номер (цифры через точки) и не больше раза на версию —
    метка restart.ver в папке состояния; новый процесс с той же версией на диске второй раз не перезапускается."""
    import re
    from settings import STATE_DIR
    mark = STATE_DIR / "restart.ver"
    mine = UI_VERSION
    while True:
        time.sleep(15)
        v = _disk_version()
        if v and v != mine and re.fullmatch(r"\d+(\.\d+)+", v):
            try:
                if mark.read_text(encoding="utf-8").strip() == f"{mine}>{v}":
                    print(f"Версия на диске {v}, у окна {mine}, перезапуск уже был — не повторяю", file=sys.stderr)
                    return
            except OSError:
                pass
            try:
                mark.write_text(f"{mine}>{v}", encoding="utf-8")
            except OSError:
                pass
            time.sleep(5)                       # установщик мог ещё не дописать файлы
            print(f"Dewiar обновлён до {v} — перезапускаю интерфейс", file=sys.stderr)
            api.restart()
            return


def _own_box():
    """Linux: окна — в свою коробку systemd с потолком памяти (memcap): если WebKit начнёт разрастаться, замедлятся
    или перезапустятся только окна Dewiar, а не весь рабочий стол. Запуск из меню, из ядра или после обновления —
    один раз перезапускаем себя через systemd-run (метка DEWIAR_BOX); нельзя — работаем как раньше."""
    if os.environ.get("DEWIAR_BOX"):
        return
    os.environ["DEWIAR_BOX"] = "ui"
    try:
        import memcap
        cmd = memcap.scope_cmd([sys.executable, str(Path(__file__).resolve())] + sys.argv[1:], "ui", "Dewiar — окна")
        if cmd[0] == "systemd-run":
            sys.stdout.flush()
            sys.stderr.flush()
            os.execvp(cmd[0], cmd)
    except Exception as e:  # noqa: BLE001
        print(f"Окна без потолка памяти: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", action="store_true")
    ap.add_argument("--autostart", action="store_true", help="запуск вместе с системой: убранный в трей виджет остаётся в трее")
    ap.add_argument("--capture", action="store_true", help="окно «Закинуть идею» (сочетание клавиш, ui/hotkey.py)")
    ap.add_argument("target", nargs="?", help="файл .dewiar или ссылка dewiar://connect?server=…")
    args = ap.parse_args()
    from urllib.parse import quote
    extra = ""
    if args.target:
        t = args.target
        if t.startswith("file://"):
            from urllib.parse import unquote, urlparse
            t = unquote(urlparse(t).path)
        extra = ("&address=" + quote(t, safe="")) if t.startswith("dewiar:") else ("&import=" + quote(str(Path(t).resolve()), safe=""))
        args.settings = True

    if WIN:
        return main_win(args, extra)
    if args.capture:                           # сочетание клавиш: программа работает — сразу сигнал, без коробки systemd
        fh = lock("ui")
        if fh is None:
            (Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / f"dewiar-show-{os.getuid()}").write_text("capture")
            return
        fh.close()                             # не запущена — запускаемся как обычно, окно идеи откроется после старта
    _own_box()
    migrate_from_cortex()
    fresh = not SETTINGS_PATH.exists() or ui_settings().get("welcome") == ""   # первый запуск — откроем «Первые шаги»
    uis = ui_settings()
    if uis.get("force_x11", True) and os.environ.get("WAYLAND_DISPLAY"):
        # На Wayland окно не может само держаться поверх других и двигаться — работаем через XWayland.
        os.environ.setdefault("GDK_BACKEND", "x11")
    os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")     # частая причина белых/чёрных окон на NVIDIA
    if not uis.get("gpu", False):
        # Программная отрисовка: ускоренный WebKitGTK на части систем неверно смешивает полупрозрачные
        # пиксели — отсюда «пересвеченные» пятна и рваный текст. Виджет маленький, процессору это почти
        # ничего не стоит (но см. _raise_idle_priority). Включить ускорение: settings.ui.gpu = true.
        os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")

    held = lock("ui")
    if held is None:
        # Интерфейс уже запущен — просим его показаться и выходим. Сигнал-файл: «hud» или «settings» + параметры
        # студии (&import=…, &address=…); его ждёт watch() в on_start, на Windows — то же в main_win.
        (Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / f"dewiar-show-{os.getuid()}").write_text(
            "capture" if args.capture else ("settings" + extra) if args.settings else "hud")
        return

    ensure_core()
    try:                                       # окна — «Dewiar» с нашим значком (а не «app.py» с шестерёнкой в доке)
        import gi
        from gi.repository import GLib                 # имя программы — до запуска GTK (иначе окно-лидер «app.py»)
        GLib.set_prgname("dewiar")
        GLib.set_application_name("Dewiar")
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk
        Gdk.set_program_class("Dewiar")
        Gtk.Window.set_default_icon_from_file(str(ROOT / "icons" / "dewiar-256.png"))
    except Exception as e:  # noqa: BLE001
        print(f"Значок окна не задан: {e}", file=sys.stderr)
    import webview
    token = ensure_token()
    api = Api(token)

    set_card_base(uis.get("hud_w") or CARD_DEFAULT[0], uis.get("hud_h") or CARD_DEFAULT[1])   # свой размер карточки
    set_zoom_sizes(uis.get("zoom"))                          # окна виджета — под масштаб интерфейса
    TRANSPARENT[0] = composited_x11()                        # гладкие скругления, если есть композитор
    if not TRANSPARENT[0] and nvidia_driver():
        _ui_log("виджет: сплошное окно (драйвер NVIDIA — прозрачное мигало, №234)")
    mode = "card"                                            # шарика больше нет: сохранённый hud_mode «mini» — тоже карточка
    x, y = uis.get("hud_x"), uis.get("hud_y")                 # положение карточки
    if x is None or y is None:
        try:
            scr = webview.screens[0]
            x, y = scr.width - SIZES["card"][0] - MARGIN, scr.height - SIZES["card"][1] - MARGIN - 40
        except Exception:  # noqa: BLE001
            x, y = 100, 100
    for m in ("card",):
        w, h = SIZES[m]
        api.wins[m] = webview.create_window(TITLES[m], api._url("hud.html", "&mode=" + m + ("&tw=1" if TRANSPARENT[0] else "")),
                                            width=w, height=h, resizable=False, min_size=(w, h), frameless=True, easy_drag=False,
                                            on_top=True, hidden=True, background_color="#0b0b0e", js_api=api,
                                            transparent=TRANSPARENT[0])
    api._hud = api.wins["card"]

    def on_start():
        api.start_hud(mode, x, y)

        def make_tray():
            try:
                api._tray = LinuxTray(api)
            except Exception as e:  # noqa: BLE001 — нет AppIndicator (не Ubuntu) — без значка
                print(f"Значок в трее недоступен: {e}", file=sys.stderr)
            return False
        from gi.repository import GLib
        GLib.idle_add(make_tray)
        if start_in_tray(uis, args):
            api.to_tray(quiet=True)
        if args.settings:
            api.open_settings("connect" if extra else "", extra)
        elif fresh:
            api.open_settings("")
        elif args.capture:
            api.show_capture()
        import threading
        sig = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / f"dewiar-show-{os.getuid()}"
        if uis.get("capture", True) is not False:          # «Закинуть идею» одной клавишей — назначить (GNOME), если ещё нет
            threading.Thread(target=capture_boot, args=(api, uis), daemon=True).start()

        def watch():
            while True:
                time.sleep(0.2)                    # сочетание «Закинуть идею» — окно должно появиться сразу
                if sig.exists():
                    what = sig.read_text().strip()
                    sig.unlink()
                    if what == "capture":                  # сочетание клавиш: только окно идеи, виджет не трогаем
                        api.show_capture()
                        continue
                    api.from_tray()
                    api.bring_back()
                    if what.startswith("settings"):
                        q = what[len("settings"):]
                        api.open_settings("connect" if q else "", q)
        threading.Thread(target=watch, daemon=True).start()
        threading.Thread(target=watch_version, args=(api,), daemon=True).start()
        threading.Thread(target=_loop_watchdog, args=(api,), name="ui-watchdog", daemon=True).start()
        try:
            from gi.repository import GLib
            GLib.timeout_add_seconds(3, keep_above_guard)
        except Exception as e:  # noqa: BLE001
            _ui_log(f"сторож «поверх окон» не запущен: {e}")

    _raise_idle_priority()
    webview.start(on_start, gui="gtk", debug=bool(os.environ.get("DEWIAR_UI_DEBUG")))
    del held


def main_win(args, extra):
    """Windows: один экземпляр, ядро отдельным процессом (и его сторож core_watch), значок в трее, окна на WebView2.
    Свой номер процесса и «версия|папка» — в ui.pid / ui.ver: по ним следующий запуск решает, показать нас или
    сменить устаревший интерфейс, их же собирает диагностика (doctor.py). Нет WebView2 или виджет дважды не
    загрузился — работаем без окон: значок в трее + студия в браузере."""
    sig = winshell.signal_path()
    from settings import STATE_DIR
    me = f"{UI_VERSION}|{ROOT}"
    if lock("ui") is None:
        # Уже запущен. Та же версия — просим показаться и выходим. Другая версия (старый интерфейс остался после
        # обновления, может быть, с ошибкой в окне) — завершаем его и запускаемся сами.
        try:
            other = (STATE_DIR / "ui.ver").read_text(encoding="utf-8").strip()
        except OSError:
            other = ""
        if other == me:
            sig.write_text("capture" if args.capture else ("settings" + extra) if args.settings else "hud", encoding="utf-8")
            return
        print(f"Запущен другой интерфейс ({other or 'старая версия'}) — завершаю его", file=sys.stderr)
        for name in ("ui.pid", "core.pid"):
            try:
                winshell.kill_pid((STATE_DIR / name).read_text(encoding="ascii").strip())
            except OSError:
                pass
        for _ in range(30):
            time.sleep(0.3)
            if lock("ui") is not None:
                break
        else:
            sig.write_text(("settings" + extra) if args.settings else "hud", encoding="utf-8")
            return
    try:     # номер — сразу, до ожидания ядра: по нему сторож обновления видит, что мы уже запущены (иначе второй запуск)
        (STATE_DIR / "ui.pid").write_text(str(os.getpid()), encoding="ascii")
        (STATE_DIR / "ui.ver").write_text(me, encoding="utf-8")
        import atexit
        atexit.register(lambda: [(STATE_DIR / n).unlink(missing_ok=True) for n in ("ui.pid", "ui.ver")])
    except OSError:
        pass
    ensure_core()
    import threading as _th
    _th.Thread(target=core_watch, name="core-watch", daemon=True).start()
    token = ensure_token()
    api = Api(token)
    fresh = not SETTINGS_PATH.exists() or ui_settings().get("welcome") == ""   # первый запуск — откроем «Первые шаги»
    uis = ui_settings()
    icon = ROOT / "icons" / "dewiar.ico"
    winshell.app_id()                                      # №260: окна на панели задач — под знаком Dewiar, а не Python

    def studio_in_browser():
        os.startfile(api._url("settings.html"))  # noqa: S606 — адрес http://127.0.0.1:… открывает браузер по умолчанию

    import threading
    started = threading.Event()
    soft = bool(uis.get("soft_render"))
    soft_render_env(soft)

    def soft_switch(on, note):
        """Включить / выключить простую отрисовку и перезапустить окна (ядро не трогаем — ассистент слушает дальше)."""
        try:
            winshell.core_call(WS_PORT, token, "settings_save", {"patch": {"ui": {"soft_render": on}}})
        except Exception:  # noqa: BLE001 — ядро не отвечает: правим файл настроек сами
            try:
                d = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                d.setdefault("ui", {})["soft_render"] = on
                SETTINGS_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            except (OSError, ValueError) as e:
                print(f"Не сохранил отрисовку окон: {e}", file=sys.stderr)
        api.restart(note)
    fix = ("Вернуть обычную отрисовку окон", lambda: soft_switch(False, "Dewiar: обычная отрисовка окон.")) if soft else \
        ("Окна чёрные? Перерисовать проще", lambda: soft_switch(True, "Dewiar: окна перерисовываются попроще — через секунду."))
    api._tray = winshell.Tray(icon, on_show=lambda: api.from_tray() if started.is_set() else studio_in_browser(),
                             on_studio=lambda: api.open_settings() if started.is_set() else studio_in_browser(),
                             on_quit=api.quit_all, on_capture=lambda: api.show_capture() if started.is_set() else None, fix=fix)
    _TRAY.append(api._tray)
    try:
        if os.environ.get("DEWIAR_NO_WEBVIEW"):        # проверка запасного пути (как без WebView2)
            raise ImportError("DEWIAR_NO_WEBVIEW")
        if int(uis.get("widget_fail2") or 0) >= 2:      # виджет дважды не загрузился — работаем без окна
            raise ImportError("виджет дважды не загрузился — включить снова: студия → «Звук и поведение»")
        import webview
    except Exception as e:  # noqa: BLE001
        print(f"Окна недоступны ({e}) — студия откроется в браузере", file=sys.stderr)
        if "дважды" in str(e):
            _notify("Dewiar работает без окна виджета (оно не загружалось). Ассистент слушает; студия — значок в трее.")
            if fresh or args.settings:
                studio_in_browser()
        else:
            _notify("Окно виджета недоступно (нет Microsoft Edge WebView2). Ассистент слушает, настройки — в браузере.")
            studio_in_browser()
        threading.Event().wait()
        return

    set_card_base(uis.get("hud_w") or CARD_DEFAULT[0], uis.get("hud_h") or CARD_DEFAULT[1])   # свой размер карточки
    set_zoom_sizes(uis.get("zoom"))                          # окна виджета — под масштаб интерфейса
    mode = "card"                                            # шарика больше нет: сохранённый hud_mode «mini» — тоже карточка
    x, y = uis.get("hud_x"), uis.get("hud_y")
    if x is None or y is None:
        l, t_, r, b = winshell.work_area()
        x, y = int(r - SIZES["card"][0] - MARGIN), int(b - SIZES["card"][1] - MARGIN)
    for m in ("card",):
        w, h = SIZES[m]
        # shadow=False (_no_shadow): pywebview 6 для окон «с тенью» включает рамку DWM (DwmExtendFrameIntoClientArea +
        # NCRENDERING_POLICY) — с ней Windows перестаёт резать окно по форме SetWindowRgn: углы остаются острыми,
        # значок — квадратным.
        api.wins[m] = webview.create_window(TITLES[m], api._url("hud.html", "&mode=" + m), width=w, height=h,
                                            resizable=False, min_size=(w, h), frameless=True, easy_drag=False,
                                            on_top=True, hidden=True, background_color="#0b0b0e", js_api=api, **_no_shadow())
    api._hud = api.wins["card"]

    def on_start():
        started.set()
        try:
            api.start_hud(mode, x, y)
            if start_in_tray(uis, args):
                api.to_tray(quiet=True)
        except Exception as e:  # noqa: BLE001
            print(f"Виджет не показан: {e}", file=sys.stderr)
        if args.settings:
            api.open_settings("connect" if extra else "", extra)
        elif fresh:
            api.open_settings("")
        elif args.capture:
            api.show_capture()
        if uis.get("capture", True) is not False:
            threading.Thread(target=capture_boot, args=(api, uis), daemon=True).start()

        def watch():
            while True:
                time.sleep(0.2)                    # сочетание «Закинуть идею» — окно должно появиться сразу
                if sig.exists():
                    what = sig.read_text(encoding="utf-8").strip()
                    sig.unlink()
                    if what == "capture":
                        api.show_capture()
                        continue
                    api.from_tray()
                    if what.startswith("settings"):
                        q = what[len("settings"):]
                        api.open_settings("connect" if q else "", q)
        threading.Thread(target=watch, daemon=True).start()
        threading.Thread(target=page_guard, daemon=True).start()

    def remember_fail(n):
        """Сколько запусков подряд виджет не загрузился: после двух — запускаемся без окна (значок в трее + студия
        в браузере), чтобы не держать зависшие окна WebView2. Вернуть: студия → «Звук и поведение»."""
        try:
            winshell.core_call(WS_PORT, token, "settings_save", {"patch": {"ui": {"widget_fail2": n}}})
        except Exception as e:  # noqa: BLE001
            print(f"Не сохранил счётчик сбоев виджета: {e}", file=sys.stderr)

    def page_guard():
        """Сторож загрузки виджета. Окно без рамки: если страница не загрузилась (ошибка вместо виджета), закрыть
        его нечем. Примерно через 10, 25 и 50 с спрашиваем страницу, на месте ли карточка, облик и связь (window.core).
        Видно, что в окне не наша страница, — убираем окна, объясняем по-человечески, открываем студию в браузере
        (ассистент работает) и считаем сбой (remember_fail); загрузилась — счётчик сбоев обнуляем."""
        res = ""
        for pause in (10, 15, 25):
            time.sleep(pause)
            box = {}

            def probe():
                try:
                    box["r"] = api._hud.evaluate_js("(document.getElementById('card') && document.getElementById('orb') && window.core ? 'ok ' : 'bad ') + location.href")
                except Exception as e:  # noqa: BLE001
                    box["r"] = f"ошибка проверки: {e}"
            t = threading.Thread(target=probe, daemon=True)
            t.start()
            t.join(10)
            res = str(box.get("r", "нет ответа от окна"))
            if res.startswith("ok "):
                print(f"Виджет загружен: {res[3:].split('?')[0]}", file=sys.stderr)
                if uis.get("widget_fail2"):
                    remember_fail(0)
                if not soft:                           # страница на месте, а окно — ровная чёрная заливка: не отрисовалось
                    time.sleep(1.5)
                    img = winshell.window_shot(TITLES["card"])
                    try:
                        blank = img is not None and blank_image(img)
                    except Exception:  # noqa: BLE001
                        blank = False
                    if blank:
                        print("Виджет загружен, но окно пустое (чёрное) — включаю простую отрисовку", file=sys.stderr)
                        soft_switch(True, "Окна Dewiar не отрисовались — перезапускаю их попроще. Ассистент слушает.")
                return
            print(f"Проверка виджета: {res[:200]}", file=sys.stderr)
        if not res.startswith("bad "):
            # окно не ответило на проверку — это ещё не значит, что оно сломано (не прячем рабочий виджет);
            # прячем только когда точно видно: в окне не наша страница (ошибка загрузки)
            print("Виджет: проверить не удалось — оставляю как есть", file=sys.stderr)
            return
        print(f"Виджет не загрузился ({res}) — окна скрыты, студия в браузере", file=sys.stderr)
        remember_fail(int(uis.get("widget_fail2") or 0) + 1)
        for w in api.wins.values():
            try:
                w.hide()
            except Exception:  # noqa: BLE001
                pass
        winshell.message_box("Окно виджета Dewiar не загрузилось, поэтому оно скрыто. Ассистент работает и слушает; "
                             "настройки открываются в браузере.\n\nЕсли так повторяется — меню «Пуск» → «Dewiar — диагностика» "
                             "и пришлите снимок отчёта. Выйти из Dewiar — значок в трее (возле часов) → «Выход».")
        studio_in_browser()

    print(f"Виджет: {api._url('hud.html').split('?')[0]}", file=sys.stderr)
    try:
        webview.start(on_start, gui="edgechromium", debug=bool(os.environ.get("DEWIAR_UI_DEBUG")))
    except Exception as e:  # noqa: BLE001 — нет WebView2: ассистент работает, студия — в браузере
        print(f"WebView2 недоступен ({e}) — студия откроется в браузере", file=sys.stderr)
        _notify("Окно виджета не открылось (нет Microsoft Edge WebView2). Ассистент слушает, студия — в браузере.")
        studio_in_browser()
        threading.Event().wait()
    api.quit_all()


if __name__ == "__main__":
    if WIN and sys.stderr is None:              # pythonw: без консоли — ошибки интерфейса в файл журнала
        try:
            sys.stderr = sys.stdout = open(winshell.log_dir() / "ui.log", "a", encoding="utf-8", buffering=1)
        except OSError:
            pass
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"Интерфейс не запустился: {e}", file=sys.stderr)
        if WIN:
            import traceback
            traceback.print_exc()
        else:
            print("Ядро продолжает работать. Проверьте: sudo apt install python3-gi gir1.2-webkit2-4.1", file=sys.stderr)
        sys.exit(1)
