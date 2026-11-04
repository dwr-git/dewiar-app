"""Глаза: снимок экрана, кадр с камеры, подготовка картинок для модели со зрением; и выбор рабочего ffmpeg
(ffmpeg_path — им пользуются и радио, и инструменты, и задачи).

Экран на Windows — Pillow ImageGrab (все мониторы); на Linux — по очереди, пока не получится:
  1. xdg-desktop-portal Screenshot (GNOME/KDE на Wayland и X11; система сама спросит разрешение);
  2. gnome-screenshot, spectacle (KDE), grim (Sway/Hyprland);
  3. ffmpeg x11grab — только в сеансе X11 (на Wayland дал бы чёрный кадр).
Камера — ffmpeg (Linux v4l2, Windows DirectShow), первые 8 кадров пропускаются: камера «просыпается», они тёмные.
Картинка ужимается до 1600 px по длинной стороне, JPEG ~85 — модели этого хватает с запасом.
"""

import base64
import io
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

log = logging.getLogger("dewiar.eyes")
MAX_SIDE = 1600


class EyesError(Exception):
    pass


_FF = {}                 # проверенный ffmpeg: {"path"} и сломанные (не прошли проверку или упали на деле): {"bad": {путь}}


def _bundled_ffmpeg():
    """ffmpeg из пакета imageio-ffmpeg (едет с Dewiar) или None."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def ffmpeg_works(path):
    """ffmpeg запускается и выдаёт звук (после сбоя обновления системный ffmpeg бывает сломан — падает сразу).
    Две пробы: -version и 0,3 с синуса из lavfi; до 40 с в худшем случае."""
    import subprocess
    nw = 0x08000000 if os.name == "nt" else 0
    try:
        r = subprocess.run([path, "-hide_banner", "-version"], capture_output=True, timeout=20, stdin=subprocess.DEVNULL,
                           creationflags=nw)
        if r.returncode != 0:
            return False
        r = subprocess.run([path, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3", "-f", "s16le",
                            "-ac", "1", "-ar", "16000", "-"], capture_output=True, timeout=20, stdin=subprocess.DEVNULL,
                           creationflags=nw)
        if r.returncode == 0:
            return len(r.stdout) > 4000
        return r.returncode > 0 and b"lavfi" in (r.stderr or b"")   # сборка без lavfi — проверить звуком нельзя, но запускается
    except (OSError, subprocess.SubprocessError):
        return False


def ffmpeg_broken(path):
    """Этот ffmpeg упал на деле (радио) — до перезапуска программы берём другой."""
    if path:
        _FF.setdefault("bad", set()).add(path)
        _FF.pop("path", None)


def ffmpeg_path():
    """Рабочий ffmpeg: системный, а если его нет или он сломан (падает) — свой, из пакета imageio-ffmpeg; нет
    ни одного — None. Выбор запоминается, поэтому проверка (ffmpeg_works) идёт один раз."""
    p = _FF.get("path")
    if p and os.path.exists(p):
        return p
    bad = _FF.get("bad", set())
    for cand in (shutil.which("ffmpeg"), _bundled_ffmpeg()):
        if not cand or cand in bad:
            continue
        if ffmpeg_works(cand):
            if cand != shutil.which("ffmpeg"):
                log.warning("Системный ffmpeg не работает — беру встроенный: %s", cand)
            _FF["path"] = cand
            return cand
        log.warning("ffmpeg %s не работает (падает или не выдаёт звук) — пробую другой", cand)
        bad.add(cand)
        _FF["bad"] = bad
    return None


def prepare(data: bytes):
    """Любая картинка -> (JPEG base64, ширина, высота); EyesError — не картинка."""
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:  # noqa: BLE001
        raise EyesError("это не картинка") from e
    im = im.convert("RGB")
    side = MAX_SIDE
    if im.width >= 2.2 * im.height:                      # несколько мониторов в ряд: иначе всё сожмётся в полоску 1600×400;
                                                         # даём ~2,6 Мпикс и до 3200 px по ширине
        side = min(3200, int((2_600_000 * im.width / im.height) ** 0.5))
    if max(im.size) > side:
        k = side / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return base64.b64encode(out.getvalue()).decode(), im.width, im.height


def _portal_screenshot(env, timeout=30):
    """org.freedesktop.portal.Screenshot через Gio: запрос → сигнал Response с адресом файла -> байты PNG.
    Подписка — на заранее известный путь запроса (handle_token), иначе быстрый ответ портала можно пропустить.
    Свой MainContext — функция зовётся не из главного потока. env — окружение сеанса (DBUS_SESSION_BUS_ADDRESS)."""
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    ctx = GLib.MainContext.new()
    ctx.push_thread_default()
    try:
        addr = env.get("DBUS_SESSION_BUS_ADDRESS")
        bus = (Gio.DBusConnection.new_for_address_sync(addr, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
                                                       Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
               if addr else Gio.bus_get_sync(Gio.BusType.SESSION, None))
        token = "dewiar" + uuid.uuid4().hex[:8]
        sender = bus.get_unique_name()[1:].replace(".", "_")
        req_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        box = {}
        loop = GLib.MainLoop.new(ctx, False)

        def on_response(_c, _s, _p, _i, _sig, params):
            code, results = params.unpack()
            box["code"], box["uri"] = code, results.get("uri", "")
            loop.quit()
        sub = bus.signal_subscribe("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request", "Response",
                                   req_path, None, Gio.DBusSignalFlags.NO_MATCH_RULE, on_response)
        bus.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                      "org.freedesktop.portal.Screenshot", "Screenshot",
                      GLib.Variant("(sa{sv})", ("", {"handle_token": GLib.Variant("s", token),
                                                     "interactive": GLib.Variant("b", False)})),
                      None, Gio.DBusCallFlags.NONE, 10000, None)
        GLib.timeout_add_seconds(timeout, loop.quit)
        loop.run()
        bus.signal_unsubscribe(sub)
    finally:
        ctx.pop_thread_default()
    if box.get("code") != 0 or not box.get("uri"):
        raise EyesError("снимок экрана отклонён" if box.get("code") == 1 else "портал не ответил")
    path = Path(unquote(urlparse(box["uri"]).path))
    data = path.read_bytes()
    try:
        path.unlink()                    # портал кладёт снимок в «Изображения» — убираем за собой
    except OSError:
        pass
    return data


WIN = os.name == "nt"
MAC = __import__("sys").platform == "darwin"
NO_WINDOW = 0x08000000 if WIN else 0


def _win_screen():
    """Windows: весь рабочий стол (все мониторы) через Pillow."""
    from PIL import ImageGrab
    im = ImageGrab.grab(all_screens=True)
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def capture_screen(env):
    """Снимок всего экрана -> байты PNG; EyesError со списком неудавшихся способов. env — окружение графического
    сеанса пользователя (DISPLAY, WAYLAND_DISPLAY, DBUS_SESSION_BUS_ADDRESS); DEWIAR_NO_PORTAL — без портала;
    DEWIAR_FAKE_SCREEN — файл-картинка вместо экрана (проверки без графического сеанса)."""
    if os.environ.get("DEWIAR_FAKE_SCREEN"):
        return Path(os.environ["DEWIAR_FAKE_SCREEN"]).read_bytes()
    if WIN:
        try:
            return _win_screen()
        except Exception as e:  # noqa: BLE001
            raise EyesError(f"не получилось сделать снимок экрана: {e}") from e
    if MAC:                                           # screencapture; без разрешения «Запись экрана» — подсказка, где его дать
        import macsys
        try:
            return macsys.screenshot()
        except Exception as e:  # noqa: BLE001
            raise EyesError(f"не получилось сделать снимок экрана: {e}") from e
    tmpdir = tempfile.mkdtemp()
    tmp = Path(tmpdir) / "screen.png"
    wayland = bool(env.get("WAYLAND_DISPLAY")) or env.get("XDG_SESSION_TYPE") == "wayland"
    errors = []
    attempts = []
    if not os.environ.get("DEWIAR_NO_PORTAL"):
        attempts.append(("портал", lambda: _portal_screenshot(env)))
    for name, cmd in (("gnome-screenshot", ["gnome-screenshot", "-f", str(tmp)]),
                      ("spectacle", ["spectacle", "-b", "-n", "-f", "-o", str(tmp)]),
                      ("grim", ["grim", str(tmp)])):
        if shutil.which(cmd[0]):
            attempts.append((name, lambda c=cmd: (subprocess.run(c, env=env, capture_output=True, timeout=15), tmp.read_bytes())[1]))
    ff = ffmpeg_path()
    if env.get("DISPLAY") and not wayland and ff:
        attempts.append(("x11grab", lambda: subprocess.run(
            [ff, "-loglevel", "error", "-f", "x11grab", "-i", env["DISPLAY"], "-frames:v", "1", "-f", "image2",
             "-vcodec", "png", "-"], env=env, capture_output=True, timeout=15, check=True).stdout))
    try:
        for name, fn in attempts:
            try:
                data = fn()
                if data:
                    log.info("Снимок экрана: %s", name)
                    return data
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {e}")
        raise EyesError("не получилось сделать снимок экрана (" + "; ".join(errors or ["нет подходящего способа"]) + ")")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)       # снимок экрана не должен оставаться во временной папке


def capture_camera(device="/dev/video0"):
    """Один кадр с камеры -> байты JPEG. На Windows device — имя устройства DirectShow (путь /dev/… — значит первая
    камера). DEWIAR_FAKE_CAMERA — тестовая картинка ffmpeg вместо камеры (для проверок)."""
    if os.environ.get("DEWIAR_FAKE_CAMERA"):
        src = ["-f", "lavfi", "-i", "testsrc=size=1280x720:rate=10"]
    elif WIN:
        name = device if device and not device.startswith("/dev/") else (list_cameras() or [""])[0]
        if not name:
            raise EyesError("камера не найдена")
        src = ["-f", "dshow", "-i", f"video={name}"]
    elif MAC:                                         # AVFoundation: первая камера (встроенная FaceTime), без звука
        src = ["-f", "avfoundation", "-framerate", "30", "-i", "0:none"]
    else:
        if not Path(device).exists():
            raise EyesError(f"камера {device} не найдена")
        src = ["-f", "v4l2", "-i", device]
    ff = ffmpeg_path()
    if not ff:
        raise EyesError("для камеры нужен ffmpeg — переустановите Dewiar или поставьте: sudo apt install ffmpeg")
    r = subprocess.run([ff, "-loglevel", "error"] + src + ["-vf", "select=gte(n\\,8)", "-frames:v", "1",
                                                                 "-f", "image2", "-vcodec", "mjpeg", "-"],
                       capture_output=True, timeout=20, creationflags=NO_WINDOW)
    if r.returncode or not r.stdout:
        raise EyesError("камера не отдала кадр: " + r.stderr.decode(errors="replace")[-200:])
    return r.stdout


def list_cameras():
    """Камеры: на Windows — имена DirectShow, на Linux — /dev/video* (у одной камеры их бывает несколько)."""
    if WIN:                          # имена устройств DirectShow: ffmpeg -list_devices true -f dshow -i dummy (список — в stderr)
        ff = ffmpeg_path()
        if not ff:
            return []
        try:
            r = subprocess.run([ff, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                               capture_output=True, timeout=15, creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            return []
        import re
        text = r.stderr.decode("utf-8", errors="replace")
        return [m.group(1) for m in re.finditer(r'"([^"]+)"\s*\(video\)', text)]
    if MAC:
        return ["0"]                                 # первая камера AVFoundation; выбор камеры на Mac — позже
    return sorted(str(p) for p in Path("/dev").glob("video*"))
