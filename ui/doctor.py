"""Диагностика Dewiar для Windows: «Пуск» → «Dewiar — диагностика».

Работает, даже если сам Dewiar не запускается: только стандартная библиотека Python (и core/winsys.py, core/winav.py,
написанные так же). Собирает систему, библиотеки (каждую — в отдельном процессе, чтобы ошибка загрузки DLL не уронила
проверку), WebView2, антивирус и целость файлов, core.fail, доступ к сайту и источникам моделей, процессы,
ui.pid/core.pid и хвосты журналов. Итог — текстовый файл на рабочем столе (ключи и токены скрыты), он сразу
открывается — его присылают разработчику. Строка «ИТОГ» вставляется третьей, чтобы её было видно без прокрутки."""
import ctypes
import datetime as dt
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent                      # …\Programs\Dewiar\app
LOCAL = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "Dewiar"
ROAM = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming") / "Dewiar"
MODS = ["numpy", "onnxruntime", "vosk", "sounddevice", "webview", "websockets", "onnx_asr", "vosk_tts", "clr", "pulsectl"]
NO_WIN = {"pulsectl"}                                            # нужен только на Linux (PulseAudio)
# ключ, токен, пароль в журналах и настройках: имя оставляем, значение заменяем на *** перед записью отчёта;
# «Authorization: Bearer …» — прячем сам токен, а не слово Bearer
SECRET = re.compile(r"((?:api_key|token|password|secret|authorization|bearer)[\"']?\s*[:=]?\s*[\"']?(?:bearer\s+)?)([\w.\-]{6,})", re.I)
CREATE_NO_WINDOW = 0x08000000


def ram_gb():
    try:
        class M(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        m = M(); m.len = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return f"{m.total / 2**30:.1f} ГБ, свободно {m.avail / 2**30:.1f} ГБ"
    except Exception as e:  # noqa: BLE001
        return f"? ({e})"


def cpu_avx():
    try:                                                    # PF_AVX_INSTRUCTIONS_AVAILABLE = 39, AVX2 = 40
        f = ctypes.windll.kernel32.IsProcessorFeaturePresent
        return f"AVX {'да' if f(39) else 'НЕТ'}, AVX2 {'да' if f(40) else 'нет'}"
    except Exception:  # noqa: BLE001
        return "?"


def webview2():
    """Версия среды WebView2 из реестра (ключ клиента EdgeUpdate, значение pv) или «НЕТ».
    Ищем в трёх местах: 64-битная Windows (WOW6432Node), 32-битная, установка только для пользователя;
    0.0.0.0 — среду удалили, а ключ остался."""
    try:
        import winreg
        key = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        for root, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node" + key[8:]), (winreg.HKEY_LOCAL_MACHINE, key),
                          (winreg.HKEY_CURRENT_USER, key)):
            try:
                with winreg.OpenKey(root, sub) as k:
                    v = winreg.QueryValueEx(k, "pv")[0]
                    if v and v != "0.0.0.0":
                        return v
            except OSError:
                continue
    except Exception as e:  # noqa: BLE001
        return f"? ({e})"
    return "НЕТ"


def check_module(name):
    """Импортирует библиотеку в отдельном процессе -> (загрузилась ли, версия или хвост ошибки).
    Берём консольный python.exe рядом с pythonw.exe: так в выводе есть полный текст ошибки импорта."""
    py = Path(sys.executable).with_name("python.exe") if os.name == "nt" else Path(sys.executable)
    if not py.exists():
        py = Path(sys.executable)
    try:
        r = subprocess.run([str(py), "-X", "utf8", "-c", f"import {name}; print(getattr({name}, '__version__', 'ok'))"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
                           stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    if r.returncode == 0:
        return True, (r.stdout.strip().splitlines() or ["ok"])[-1]
    err = [x for x in (r.stderr or "").strip().splitlines() if x.strip()]
    return False, " | ".join(err[-3:]) or f"код {r.returncode}"


def reach(host, port=443):
    try:
        with socket.create_connection((host, port), timeout=6):
            return "доступен"
    except OSError as e:
        return f"НЕДОСТУПЕН ({e})"


def tail(p, n):
    try:
        return p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def desktop():
    try:
        sys.path.insert(0, str(APP / "core"))
        import winsys                                      # noqa: PLC0415 — без сторонних библиотек
        d = Path(winsys.known_folder("Desktop"))
        if d.is_dir():
            return d
    except Exception:  # noqa: BLE001
        pass
    d = Path.home() / "Desktop"
    return d if d.is_dir() else Path.home()


def main():
    ver = "?"
    try:
        ver = re.search(r'^VERSION = "([^"]+)"', (APP / "core" / "version.py").read_text(encoding="utf-8"), re.M).group(1)
    except (OSError, AttributeError):
        pass
    L = [f"Dewiar {ver} — диагностика {dt.datetime.now():%Y-%m-%d %H:%M}", ""]
    L.append(f"Система: {platform.platform()} ({platform.version()}); {platform.machine()}")
    L.append(f"Процессор: {platform.processor() or '?'}; ядер: {os.cpu_count()}; {cpu_avx()}")
    L.append(f"Память: {ram_gb()}")
    try:
        du = shutil.disk_usage(str(LOCAL.parent))
        L.append(f"Диск: свободно {du.free / 2**30:.1f} ГБ из {du.total / 2**30:.0f} ГБ")
    except OSError:
        pass
    L.append(f"Python: {sys.version.split()[0]} — {sys.executable}")
    L.append(f"Программа: {APP}")
    L.append(f"WebView2 (окно виджета): {webview2()}")
    py_dir = Path(sys.executable).parent
    dlls = ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll"]
    L.append("Библиотеки Visual C++ рядом с Python: " + ", ".join(f"{d} {'есть' if (py_dir / d).exists() else 'НЕТ'}" for d in dlls))
    L += ["", "== Библиотеки Python"]
    bad = []
    for m in MODS:
        if os.name == "nt" and m in NO_WIN:
            continue
        good, info = check_module(m)
        L.append(f"{'ok ' if good else 'ОШИБКА'} {m}: {info}")
        if not good:
            bad.append(m)
    L += ["", "== Антивирус"]
    av_note = ""
    try:
        sys.path.insert(0, str(APP / "core"))
        import winav                                       # noqa: PLC0415
        prods = winav.products()
        L += [f"{p['name']} ({'включён' if p['on'] else 'выключен'})" for p in prods] or ["не определён"]
        miss = winav.missing(APP)
        L.append("Файлы программы: " + ("на месте" if not miss else "НЕТ: " + ", ".join(miss)))
        if miss or bad:
            av_note = " — возможно, мешает антивирус: " + (winav.main_av(prods) or {}).get("name", "?")
    except Exception as e:  # noqa: BLE001
        L.append(f"не удалось проверить: {e}")
    try:
        L.append("Последняя ошибка запуска ядра: " + (LOCAL / "core.fail").read_text(encoding="utf-8")[:1500])
    except OSError:
        pass
    L += ["", "== Интернет"]
    for h in ("dewiar.pro", "pypi.org", "files.pythonhosted.org", "huggingface.co", "alphacephei.com"):
        L.append(f"{h}: {reach(h)}")
    L += ["", "== Папки"]
    for name, p in (("модели и журналы", LOCAL), ("настройки", ROAM)):
        try:
            files = [f for f in p.rglob("*") if f.is_file()]
            L.append(f"{name}: {p} — файлов {len(files)}, {sum(f.stat().st_size for f in files) / 2**20:.0f} МБ")
        except OSError as e:
            L.append(f"{name}: {p} — {e}")
    models = LOCAL / "models"
    if models.is_dir():
        L.append("модели: " + ", ".join(sorted(x.name for x in models.iterdir())))
    L += ["", "== Запущенный Dewiar (процессы Python)"]
    if os.name == "nt":
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                "Get-Process pythonw,python -ErrorAction SilentlyContinue | ForEach-Object { \"$($_.Id)  $($_.StartTime)  $($_.Path)\" }"],
                               capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
            L += [x for x in (r.stdout or "").splitlines() if x.strip()] or ["не запущен"]
        except (OSError, subprocess.SubprocessError) as e:
            L.append(f"не удалось узнать: {e}")
    for f in ("ui.ver", "ui.pid", "core.pid"):
        try:
            L.append(f"{f}: {(LOCAL / f).read_text(encoding='utf-8').strip()}")
        except OSError:
            L.append(f"{f}: нет")
    for name in ("ui.log", "core.log"):
        L += ["", f"== {name} (последние строки)"] + tail(LOCAL / "logs" / name, 400 if name == "core.log" else 150)
    L.insert(2, (("ИТОГ: не загружаются: " + ", ".join(bad)) if bad else "ИТОГ: библиотеки в порядке") + av_note)
    text = SECRET.sub(lambda m: m.group(1) + "***", "\n".join(L))
    out = desktop() / f"Dewiar — диагностика {dt.datetime.now():%Y-%m-%d %H-%M}.txt"
    out.write_text(text, encoding="utf-8-sig")                 # с BOM: старый Блокнот иначе читает как ANSI
    sent = offer_send(text, ver, bad)
    if sent:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"\n\n== Отправлено разработчику: {sent}\n")
    if os.name == "nt":
        os.startfile(str(out))                             # noqa: S606 — открыть в Блокноте
    else:
        print(out)


def send_report(text, ver, note, url="https://dewiar.pro/dwrapp/cloud.php"):
    """Отчёт — разработчику, как кнопка «Сообщить о проблеме» в самой программе (?p=/report). -> «жалоба №…» или ошибка."""
    import json
    import urllib.request
    body = json.dumps({"kind": "manual", "app": "pc", "version": ver, "os": platform.platform()[:80],
                       "summary": "Диагностика: Dewiar не запускается", "note": note, "text": text[-900_000:]}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url + "?p=/report", data=body, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        d = json.loads(r.read().decode("utf-8") or "{}")
    return f"№{d.get('id')}" if d.get("id") else "отправлено"


def offer_send(text, ver, bad):
    """Спросить: отправить отчёт разработчику? (отзыв 28.10, №384: «так и не запускается на ноуте» — человек прислал
    фото экрана с телефона; диагностика сама отправит журналы — ключи и токены в них уже скрыты). -> номер или ""."""
    if os.name != "nt":
        return ""
    try:
        MB_YESNO, MB_ICONQ, IDYES = 0x4, 0x20, 6
        ask = ("Отчёт сохранён на рабочем столе.\n\nОтправить его разработчику Dewiar? Он увидит систему, видеокарту и журналы "
               "(ключи и пароли в них скрыты) и ответит в программе, когда починит.")
        if ctypes.windll.user32.MessageBoxW(0, ask, "Dewiar — диагностика", MB_YESNO | MB_ICONQ) != IDYES:
            return ""
        n = send_report(text, ver, "Dewiar не запускается (диагностика)" + (": не загружаются " + ", ".join(bad) if bad else ""))
        ctypes.windll.user32.MessageBoxW(0, f"Отправлено разработчику — отчёт {n}. Спасибо!", "Dewiar — диагностика", 0x40)
        return n
    except Exception as e:  # noqa: BLE001 — нет сети и т. п.: отчёт остаётся на рабочем столе
        try:
            ctypes.windll.user32.MessageBoxW(0, f"Не отправилось: {e}\n\nПришлите файл с рабочего стола разработчику любым способом.",
                                             "Dewiar — диагностика", 0x30)
        except Exception:  # noqa: BLE001
            pass
        return ""


if __name__ == "__main__":
    main()
