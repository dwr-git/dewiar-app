"""Windows: то, что в Linux делают xdg-open, gio, playerctl, pactl, notify-send и /proc.

Только стандартная библиотека и ctypes; громкость — через pycaw (Core Audio), если он есть,
иначе клавишами громкости. Импортируется лишь на Windows (os.name == "nt").
"""

import ctypes
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger("dewiar.win")

NO_WINDOW = 0x08000000                     # CREATE_NO_WINDOW: консольные программы без чёрного окна
DETACHED = 0x00000008 | 0x00000200         # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: запущенная программа живёт дальше без нас


def startfile(target):
    """Открыть ссылку, файл, папку или ярлык программой по умолчанию."""
    os.startfile(str(target))              # noqa: S606 — это и есть «открыть как двойным щелчком»


def default_browser():
    """Программа браузера по умолчанию (тот, кто открывает https) -> путь к .exe или None. Нужна для своих .html (26.11:
    страница «Страниц» открылась «двойным щелчком» — в редакторе кода, которому Windows отдала .html, а не в браузере)."""
    import re
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice") as k:
            prog = winreg.QueryValueEx(k, "ProgId")[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog + r"\shell\open\command") as k:
            cmd = str(winreg.QueryValueEx(k, "")[0])
    except OSError:
        return None
    m = re.match(r'\s*"([^"]+)"|\s*(\S+)', cmd)
    exe = (m.group(1) or m.group(2)) if m else ""
    return exe if exe.lower().endswith(".exe") and os.path.isfile(exe) else None


def open_in_browser(target):
    """Открыть адрес или свой .html именно в браузере по умолчанию; не нашли его — как двойным щелчком."""
    exe = default_browser()
    if exe:
        subprocess.Popen([exe, str(target)], creationflags=NO_WINDOW)   # noqa: S603
        return
    startfile(target)


def run_hidden(cmd, **kw):
    """subprocess.run без окна консоли (из pythonw иначе мелькает чёрное окно)."""
    return subprocess.run(cmd, creationflags=NO_WINDOW, **kw)


def popen_hidden(cmd, **kw):
    return subprocess.Popen(cmd, creationflags=NO_WINDOW, **kw)


# ---------- программы из меню «Пуск» ----------

def start_menu_dirs():
    """Папки меню «Пуск»: свои ярлыки пользователя (APPDATA) и общие для всех (PROGRAMDATA)."""
    out = []
    for base in (os.environ.get("APPDATA"), os.environ.get("PROGRAMDATA")):
        if base:
            out.append(Path(base) / "Microsoft/Windows/Start Menu/Programs")
    return out


def apps():
    """Ярлыки меню «Пуск»: [{"name", "ru", "keywords", "id", "path"}] — тот же формат, что у списка .desktop в Linux.
    Деинсталляторы и справка пропускаются; keywords — имя папки ярлыка (обычно производитель)."""
    res, seen = [], set()
    skip = ("uninstall", "удалить", "удаление", "readme", "help", "справка", "documentation", "license")
    for d in start_menu_dirs():
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.lnk")) + sorted(d.rglob("*.url")):
            name = f.stem
            low = name.lower()
            if low in seen or any(s in low for s in skip):
                continue
            seen.add(low)
            res.append({"name": name, "ru": "", "keywords": f.parent.name if f.parent != d else "", "id": name,
                        "path": str(f)})
    # встроенные, у которых нет ярлыка в меню
    for name, exe, kw in [("Калькулятор", "calc.exe", "calculator;calc"), ("Блокнот", "notepad.exe", "notepad"),
                          ("Проводник", "explorer.exe", "explorer;files;файлы"), ("Параметры", "ms-settings:", "settings;настройки"),
                          ("Диспетчер задач", "taskmgr.exe", "task manager"), ("Paint", "mspaint.exe", "paint;пейнт"),
                          ("Командная строка", "cmd.exe", "terminal;терминал;консоль"),
                          ("PowerShell", "powershell.exe", "terminal;терминал")]:
        if name.lower() not in seen:
            res.append({"name": name, "ru": name, "keywords": kw, "id": exe, "path": exe})
    return res


def known_folder(alias):
    """Загрузки, Документы, Рабочий стол… (alias — английское имя: "Downloads") -> путь с учётом переноса папки
    в OneDrive или на другой диск (SHGetKnownFolderPath); не вышло — ~/alias."""
    guids = {"Downloads": "{374DE290-123F-4565-9164-39C4925E467B}", "Documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
             "Desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "Music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
             "Pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}", "Videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}"}
    g = guids.get(alias)
    if g:
        try:
            class GUID(ctypes.Structure):
                _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort), ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]
            guid = GUID()
            ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(g), ctypes.byref(guid))
            p = ctypes.c_wchar_p()
            ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(p))
            path = p.value
            ctypes.windll.ole32.CoTaskMemFree(p)
            if path:
                return Path(path)
        except Exception as e:  # noqa: BLE001
            log.debug("SHGetKnownFolderPath: %s", e)
    return Path.home() / alias


# ---------- клавиши мультимедиа ----------

# Виртуальные коды клавиш. Отдельных «играть» и «пауза» в Windows нет — обе команды жмут «играть/пауза»
VK = {"play_pause": 0xB3, "play": 0xB3, "pause": 0xB3,"next": 0xB0, "previous": 0xB1, "stop": 0xB2,
      "vol_up": 0xAF, "vol_down": 0xAE, "mute": 0xAD}


def press(vk, times=1):
    """Нажать и отпустить клавишу times раз — система передаёт её активному плееру или регулятору громкости."""
    u =ctypes.windll.user32
    for _ in range(times):
        u.keybd_event(vk, 0, 1, 0)             # KEYEVENTF_EXTENDEDKEY
        u.keybd_event(vk, 0, 1 | 2, 0)         # …| KEYEVENTF_KEYUP


def media(action):
    press(VK[action])


# ---------- громкость ----------

def _endpoint():
    """IAudioEndpointVolume динамиков по умолчанию (pycaw); нет pycaw или COM — исключение."""
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    dev = AudioUtilities.GetSpeakers()
    if hasattr(dev, "EndpointVolume"):         # pycaw ≥ 2024: готовый объект
        return dev.EndpointVolume
    iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))


def volume(percent=None, change=None, mute=None):
    """Громкость динамиков по умолчанию, %: percent — поставить, change — изменить на ±N, mute — выключить/включить звук.
    -> новое значение (или None, если узнать нельзя). Без Core Audio — клавишами: шаг 2 %, «поставить N%» = 50 раз
    вниз до нуля и N/2 раз вверх."""
    try:
        ev = _endpoint()
        if mute is not None:
            ev.SetMute(1 if mute else 0, None)
        cur = round(ev.GetMasterVolumeLevelScalar() * 100)
        if percent is not None:
            cur = max(0, min(100, int(percent)))
            ev.SetMasterVolumeLevelScalar(cur / 100, None)
        elif change is not None:
            cur = max(0, min(100, cur + int(change)))
            ev.SetMasterVolumeLevelScalar(cur / 100, None)
        return cur
    except Exception as e:  # noqa: BLE001 — нет pycaw/COM: клавишами (шаг 2 %)
        log.info("Громкость через Core Audio недоступна (%s) — клавишами", e)
        if mute is not None:
            # Клавиша «без звука» только переключает: «выключи звук» при уже выключенном включил бы его. Поэтому
            # состояние ставим явно через Core Audio из PowerShell (без pycaw); не вышло — исключение, а не щелчок.
            _set_mute(bool(mute))
            return None
        if percent is not None:
            press(VK["vol_down"], 50)
            press(VK["vol_up"], max(0, min(100, int(percent))) // 2)
            return int(percent)
        if change is not None:
            press(VK["vol_up" if int(change) >= 0 else "vol_down"], max(1, abs(int(change)) // 2))
        return None


# IAudioEndpointVolume.SetMute через COM из PowerShell — для Windows без pycaw. Порядок методов в интерфейсах —
# как в заголовках Windows SDK (endpointvolume.h, mmdeviceapi.h): переставить нельзя, вызовется чужой метод.
_MUTE_PS = r"""
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
  int RegisterControlChangeNotify(IntPtr p); int UnregisterControlChangeNotify(IntPtr p); int GetChannelCount(out int n);
  int SetMasterVolumeLevel(float l, Guid c); int SetMasterVolumeLevelScalar(float l, Guid c);
  int GetMasterVolumeLevel(out float l); int GetMasterVolumeLevelScalar(out float l);
  int SetChannelVolumeLevel(uint n, float l, Guid c); int SetChannelVolumeLevelScalar(uint n, float l, Guid c);
  int GetChannelVolumeLevel(uint n, out float l); int GetChannelVolumeLevelScalar(uint n, out float l);
  int SetMute([MarshalAs(UnmanagedType.Bool)] bool m, Guid c); int GetMute(out bool m); }
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice { int Activate(ref Guid id, int ctx, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object o); }
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator { int EnumAudioEndpoints(int f, int s, out IntPtr c);
  int GetDefaultAudioEndpoint(int flow, int role, out IMMDevice d); }
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumerator {}
public class DewiarAudio { public static void SetMute(bool m) {
  var en = (IMMDeviceEnumerator)(new MMDeviceEnumerator()); IMMDevice d;
  Marshal.ThrowExceptionForHR(en.GetDefaultAudioEndpoint(0, 1, out d));
  var iid = typeof(IAudioEndpointVolume).GUID; object o;
  Marshal.ThrowExceptionForHR(d.Activate(ref iid, 23, IntPtr.Zero, out o));
  Marshal.ThrowExceptionForHR(((IAudioEndpointVolume)o).SetMute(m, Guid.Empty)); } }
"@
[DewiarAudio]::SetMute($env:DEWIAR_MUTE -eq '1')
"""


def _set_mute(on):
    """Выключить (on) или включить звук явно; OSError — PowerShell не справился."""
    r = run_hidden(["powershell", "-NoProfile", "-NonInteractive", "-Command", _MUTE_PS], capture_output=True,
                   text=True, timeout=30, stdin=subprocess.DEVNULL, env=dict(os.environ, DEWIAR_MUTE="1" if on else "0"))
    if r.returncode != 0:
        raise OSError("не удалось " + ("выключить" if on else "включить") + " звук: " + (r.stderr or r.stdout).strip()[-200:])


# ---------- уведомления ----------

# Уведомление Windows показывается от имени зарегистрированного приложения (AppUserModelID) — берём PowerShell,
# он есть на любой Windows. Текст передаётся через переменные окружения DEWIAR_T/DEWIAR_B, а не в коде скрипта:
# кавычки и $ в тексте не станут командами.
_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$n = $t.GetElementsByTagName('text')
$n.Item(0).AppendChild($t.CreateTextNode($env:DEWIAR_T)) > $null
$n.Item(1).AppendChild($t.CreateTextNode($env:DEWIAR_B)) > $null
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($t))
"""


def notify(text, title="Dewiar"):
    """Всплывающее уведомление Windows 10/11 (без сторонних библиотек). Не ждёт PowerShell: True — только что
    процесс запущен."""
    try:
        env = dict(os.environ, DEWIAR_T=title, DEWIAR_B=text)
        popen_hidden(["powershell", "-NoProfile", "-NonInteractive", "-Command", _TOAST],          # без окна — флагом процесса
                     env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError as e:
        log.info("Уведомление не показано: %s", e)
        return False


# ---------- состояние компьютера ----------

def system_parts():
    """Состояние компьютера фразами для ответа: батарея (если есть), свободная память, нагрузка процессора (если
    есть psutil; ждёт 0,3 с)."""
    parts = []

    class SPS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
                    ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    s = SPS()
    # BatteryFlag 128 — батареи нет; процент 255 — неизвестен
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)) and s.BatteryFlag != 128 and s.BatteryLifePercent <= 100:
        parts.append(f"батарея {s.BatteryLifePercent}% ({'заряжается' if s.ACLineStatus == 1 else 'разряжается'})")

    class MEM(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEM()
    m.dwLength = ctypes.sizeof(MEM)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        parts.append(f"память: свободно {m.ullAvailPhys / 2**30:.1f} из {m.ullTotalPhys / 2**30:.1f} ГБ")
    try:
        import psutil
        parts.append(f"нагрузка процессора {psutil.cpu_percent(interval=0.3):.0f}% на {os.cpu_count()} ядер")
    except Exception:  # noqa: BLE001
        pass
    return parts


def shell(cmd, timeout=30, cwd=None):
    """Команда в PowerShell (аналог bash -lc в Linux) -> CompletedProcess с текстом stdout/stderr."""
    cmd = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + cmd     # кириллица без «кракозябр»
    return run_hidden(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True,
                      timeout=timeout, cwd=cwd, stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
