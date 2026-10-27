"""Созвон: другая программа (Zoom, Teams, Telegram, Meet в браузере…) сейчас пишет с микрофона.

Во время созвона ассистент по умолчанию не слушает имя (не откликается на разговор коллег и не грузит процессор
проверками каждой фразы) — говорить с ним можно по кнопке в виджете. В «Звук и поведение» можно выбрать: только имя
главного персонажа или как обычно (настройка audio.meeting). Здесь — только «кто сейчас пишет с микрофона»:
Linux — потоки записи PulseAudio/PipeWire (pulsectl), Windows — учёт доступа к микрофону в реестре."""

import logging
import os
import re
import time

log = logging.getLogger("dewiar.meeting")
WIN = os.name == "nt"

# Записывают звук, но это не созвон: регуляторы громкости, индикаторы уровня, эхоподавление, сами звуковые службы,
# а также сам Dewiar и любые программы на Python (его вспомогательные процессы)
IGNORE = re.compile(r"pavucontrol|volume control|gnome-shell|gnome-control-center|settings|cinnamon|plasma|kmix|"
                    r"pipewire|wireplumber|pulseaudio|easyeffects|pulseeffects|speech-dispatcher|dewiar|python|"
                    r"echo-cancel|loopback|xdg-desktop-portal|peak|parec|pacat|arecord", re.I)
# Запись видео и звука — тоже не созвон (отзыв 17.10: «включил OBS для записи видео, и Лира стала глухой и беззвучной» —
# OBS пишет с микрофона, Dewiar решал «созвон» и слушал только по кнопке). Программы записи экрана и звука.
RECORDERS = re.compile(r"^obs(?:64|32)?(?:\.exe)?$|obs-studio|obsproject|simplescreenrecorder|kazam|vokoscreen|kooha|"
                       r"gpu-screen-recorder|screen ?recorder|screencast|audacity|bandicam|camtasia|sharex|"
                       r"nvidia share|nvcontainer|xbox ?game ?bar|gamebar", re.I)
# Часть имени программы → как назвать её человеку (созвон в браузере — просто «браузер»)
NICE = {"zoom": "Zoom", "teams": "Teams", "telegram": "Telegram", "skype": "Skype", "discord": "Discord", "slack": "Slack",
        "chrome": "браузер", "chromium": "браузер", "firefox": "браузер", "yandex": "браузер", "opera": "браузер",
        "brave": "браузер", "vivaldi": "браузер", "msedge": "браузер", "edge": "браузер", "whatsapp": "WhatsApp",
        "viber": "Viber", "webex": "Webex", "jitsi": "Jitsi", "mattermost": "Mattermost", "element": "Element"}


# Windows: не созвон — «Параметры» (проверка микрофона) и т. п.
WIN_IGNORE = re.compile(r"immersivecontrolpanel|systemsettings|soundrecorder|voicerecorder", re.I)
# держат микрофон для голосовой активации («Слушай, Алиса»): дольше LONG_HOLD секунд подряд — фон, а не созвон
BACKGROUND_MIC = re.compile(r"yandex", re.I)
# Голосовые команды, диктовка и обработка микрофона — держат микрофон всё время, это не созвон (пакет 25.10, №261:
# «пишет, что идёт созвон VoiceAttack», а VoiceAttack и диктовка Handy просто ждут команд)
VOICE_TOOLS = re.compile(r"voiceattack|^handy(?:\.exe)?$|voicemeeter|nvidia ?broadcast|krisp|steelseries ?sonar|"
                         r"sonar|equalizerapo|wo ?mic|vb-?audio|talon|dragon|natspeak", re.I)


def _running(exe):
    """Запущена ли сейчас программа exe (Windows). Реестр «кто держит микрофон» иногда не сбрасывается после
    падения программы — тогда она «держит» его вечно (№261: VoiceAttack не запущен, а Dewiar видел созвон).
    Не узнали (нет psutil) — считаем, что запущена."""
    try:
        import psutil
    except ImportError:
        return True
    want = exe.lower()
    try:
        return any((p.info.get("name") or "").lower() == want for p in psutil.process_iter(["name"]))
    except Exception:  # noqa: BLE001
        return True
LONG_HOLD = 15 * 60
_told = set()


def _nice(name):
    low = (name or "").lower()
    for k, v in NICE.items():
        if k in low:
            return v
    return name or "программа"


def _linux():
    """Программы с активными потоками записи. Не считаем: свой процесс, запись с мониторов (это звук динамиков)
    и с наших источников dewiar_*, индикаторы уровня, IGNORE и потоки на паузе."""
    import pulsectl
    out = []
    me = os.getpid()
    with pulsectl.Pulse("dewiar-meeting") as p:
        monitors = {s.index for s in p.source_list() if s.name.endswith(".monitor") or s.name.startswith("dewiar_")}
        for so in p.source_output_list():
            pl = so.proplist or {}
            try:
                pid = int(pl.get("application.process.id") or 0)
            except ValueError:
                pid = 0
            name = pl.get("application.name") or pl.get("application.process.binary") or ""
            binary = pl.get("application.process.binary") or ""
            if pid == me or not pid or so.source in monitors:
                continue
            if pl.get("stream.monitor") or "peak" in (pl.get("media.name") or "").lower():
                continue
            if IGNORE.search(name) or IGNORE.search(binary) or RECORDERS.search(name) or RECORDERS.search(binary):
                continue
            if so.corked:                                  # поток есть, но микрофон на паузе (выключен в созвоне)
                continue
            out.append(_nice(binary or name))
    return sorted(set(out))


def _windows():
    """Windows 10/11 ведёт учёт, кто сейчас пользуется микрофоном (HKCU\\…\\ConsentStore\\microphone):
    LastUsedTimeStop == 0 при ненулевом LastUsedTimeStart — пользуется сейчас. Подразделы — приложения из Store
    (имя пакета «Издатель.Программа_хеш»), в NonPackaged — обычные программы (путь к exe, «\\» заменены на «#»).
    Свою папку программы и python пропускаем."""
    import winreg
    out = []
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
    mine = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).lower()

    def scan(path, packaged):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            return
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(k, i)
            except OSError:
                break
            i += 1
            if sub == "NonPackaged":                        # обходится отдельным вызовом scan
                continue
            try:
                sk = winreg.OpenKey(k, sub)
                stop = winreg.QueryValueEx(sk, "LastUsedTimeStop")[0]
                start = winreg.QueryValueEx(sk, "LastUsedTimeStart")[0]
            except OSError:
                continue
            if stop == 0 and start > 0:
                app = sub.replace("#", "\\")
                if mine and mine in app.lower() or "python" in app.lower():
                    continue
                exe = app.rsplit("\\", 1)[-1].split("_")[0]
                if RECORDERS.search(exe) or RECORDERS.search(app):   # OBS и другие программы записи — не созвон
                    continue
                if VOICE_TOOLS.search(exe):                           # голосовые команды и диктовка — не созвон (№261)
                    continue
                # «Параметры» Windows (страница микрофона) — не созвон (пакет 22.10, №165)
                if WIN_IGNORE.search(app):
                    continue
                # Яндекс Браузер с «Слушай, Алиса» держит микрофон всё время — это не созвон (пакет 22.10, №170: «в трее
                # не слышит меня»: Dewiar считал это созвоном часами). Держит дольше LONG_HOLD — фон, а не звонок
                age = time.time() - (start / 1e7 - 11644473600)              # FILETIME → секунды Unix
                if BACKGROUND_MIC.search(app) and age > LONG_HOLD:
                    if app not in _told:
                        _told.add(app)
                        log.info("Микрофон держит %s уже %d мин — похоже на голосовую активацию (Алиса), не созвон", exe, age // 60)
                    continue
                if not packaged and exe.lower().endswith(".exe") and not _running(exe):   # запись в реестре осталась
                    continue                                                     # от закрытой программы (№261)
                out.append(_nice(app.rsplit("\\", 1)[-1].split("_")[0]))
        winreg.CloseKey(k)
    scan(base, True)
    scan(base + r"\NonPackaged", False)
    return sorted(set(out))


def mic_users():
    """-> [названия программ, которые сейчас слушают микрофон] (пусто — созвона нет или узнать нельзя)."""
    try:
        return _windows() if WIN else _linux()
    except Exception as e:  # noqa: BLE001
        log.debug("кто слушает микрофон — не узнать: %s", e)
        return []
