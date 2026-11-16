"""Действия модели: музыка и видео — радио, YouTube, Яндекс Музыка, управление проигрывателем, телевизор."""

import os
import re
import shutil
import subprocess
import time
import urllib.parse

from tools_base import browser_cmd, desktop_env, log, RADIO, ToolError
from tools_pc import desktop_apps
import tools_base as base          # DRY, MAC, WIN, launch, macsys, winsys — через основу: проверки подменяют их там


def _mpris_status(env, player):
    """PlaybackStatus плеера MPRIS: Playing / Paused / Stopped или ""."""
    try:
        out = subprocess.run(["gdbus", "call", "--session", "--dest", player, "--object-path", "/org/mpris/MediaPlayer2",
                              "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player",
                              "PlaybackStatus"], capture_output=True, text=True, env=env, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"(Playing|Paused|Stopped)", out)
    return m.group(1) if m else ""


def _mpris_players(env, prefer=""):
    """Плееры MPRIS (браузер, Яндекс Музыка, Spotify…). prefer — «yandex»: такой плеер (по имени или подписи) первым."""
    out = subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path",
                          "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListNames"],
                         capture_output=True, text=True, env=env, timeout=4).stdout
    players = re.findall(r"'(org\.mpris\.MediaPlayer2\.[^']+)'", out)
    if prefer and len(players) > 1:
        def who(pl):
            try:
                r = subprocess.run(["gdbus", "call", "--session", "--dest", pl, "--object-path", "/org/mpris/MediaPlayer2",
                                    "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2", "Identity"],
                                   capture_output=True, text=True, env=env, timeout=3).stdout
            except (OSError, subprocess.SubprocessError):
                r = ""
            return (pl + " " + r).lower()
        players.sort(key=lambda pl: 0 if any(w in who(pl) for w in MUSIC_APPS.get(prefer, {}).get("words", (prefer,))) else 1)
    return players


# Музыкальные приложения, которыми ассистент умеет управлять: поиск по ссылке приложения и кнопки плеера (MPRIS).
# words — как узнать плеер среди MPRIS по имени на шине или Identity
MUSIC_APPS = {"yandex": {"name": "Яндекс Музыка", "words": ("yandex", "яндекс"), "scheme": "yandexmusic",
                         "web": "https://music.yandex.ru"}}


def yandex_music_installed():
    """Стоит ли приложение Яндекс Музыки (оно открывает ссылки yandexmusic://)."""
    if base.DRY:
        return bool(os.environ.get("DEWIAR_FAKE_YANDEX_APP"))
    if base.WIN:
        try:
            import winreg
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "yandexmusic"))
            return True
        except OSError:
            return False
    if base.MAC:
        return any("yandex" in (x.get("id") or "").lower() and "music" in (x.get("id") or "").lower() for x in desktop_apps())
    try:
        r = subprocess.run(["xdg-mime", "query", "default", "x-scheme-handler/yandexmusic"], capture_output=True, text=True,
                           env=desktop_env(), timeout=4)
        if r.stdout.strip():
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return any("yandex" in (x.get("id") or "").lower() and "music" in (x.get("id") or "").lower() for x in desktop_apps())


def t_yandex_music(a, ctx):
    """Открыть в Яндекс Музыке поиск (жанр, исполнитель, песня) — в приложении, если оно стоит, иначе на сайте."""
    q = (a.get("query") or "").strip()
    path = "search?text=" + urllib.parse.quote(q) if q else ""
    app = yandex_music_installed()
    url = ("yandexmusic://" + path) if app else (MUSIC_APPS["yandex"]["web"] + "/" + path)
    base.launch(browser_cmd(url))
    hook = ctx.get("music_app")
    if hook:
        hook("yandex")
    where = "в приложении Яндекс Музыки" if app else "на сайте Яндекс Музыки"
    return (f"Открыл {where}" + (f" поиск «{q}»" if q else "") + ". Чтобы заиграло, нажмите на трек или плейлист — "
            "или скажите «играй», и я нажму воспроизведение.")


def t_play_radio(a, ctx):
    from radio import RadioError, pick, search
    r = ctx.get("radio")
    if not r:
        raise ToolError("радио недоступно")
    q = (a.get("query") or "").strip()
    url = (a.get("url") or "").strip()
    eng = ctx.get("engine")
    if url.startswith(("http://", "https://")):          # №359: ссылка на поток — играем её и запоминаем своей станцией
        st = eng.radio_custom_save(q, url) if eng is not None and hasattr(eng, "radio_custom_save") else {"name": q or "Своя станция", "url": url}
        found, mine = [dict(st, tags="своя", own=True)], True
    else:
        mine = ctx.get("music").match(q or "*") if ctx.get("music") else []     # сначала свой список станций (с сайта Dewiar)
    if url.startswith(("http://", "https://")):
        st = found[0]
    elif mine:
        found = mine[:6]
        st = found[0]
    else:
        try:
            found = search(q)
        except RadioError as e:
            raise ToolError(str(e)) from e
        st = pick(found, q)
    if not st:
        raise ToolError(f"не нашёл радиостанцию «{q}»")
    from radio import RadioError as RE
    try:
        r.play(st)
    except RE as e:
        raise ToolError(str(e)) from e
    # станция могла не ответить или зависнуть на подключении (ffmpeg жив, а звука нет) — ждём звук и пробуем другую
    if not r.wait_sound(6):
        r.stop()
        alt = next((x for x in found if x is not st), None)
        if alt:
            r.play(alt)
            if r.wait_sound(6):
                st = alt
            else:
                r.stop()
        if not r.sounding:
            why = r.failed or "не отвечает"
            fails = ctx.setdefault("radio_fails", [])
            fails.append(time.time())
            fails[:] = [x for x in fails if time.time() - x < 600]
            if len(fails) >= 2:                          # вторая неудача за 10 минут — дело не в станции: ищем, где поломка
                from radio import diagnose
                from eyes import ffmpeg_path
                where, fix = diagnose(ffmpeg_path(), st["url"])
                log.warning("Радио: проверка — %s; %s", where, fix)
                raise ToolError(f"радио не играет, и дело не в станции: {where}. Что сделать: {fix}. "
                                "Перескажи это пользователю простыми словами и не пробуй другие станции.")
            raise ToolError(f"станция «{st['name']}» не играет ({why}) — можно попробовать другую")
    others = ", ".join(x["name"] for x in found if x is not st)[:200]
    return (f"Играет радио «{st['name']}». Остановить — «стоп» или «пауза», продолжить — «продолжи»."
            + (f" Другие станции по запросу: {others}." if others else "") + " Скажи коротко, что включил, одной фразой.")


def t_play_youtube(a, ctx):
    """Ролик на YouTube: найти первый через yt_dlp и открыть в браузере (сразу воспроизводится).
    Нет yt_dlp или он не справился — открываем страницу поиска."""
    q = (a.get("query") or "").strip()
    if not q:
        raise ToolError("что найти на YouTube?")
    url = None
    if not base.DRY:
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as y:
                info = y.extract_info(f"ytsearch1:{q}", download=False)
            e = (info.get("entries") or [None])[0]
            if e:
                url = f"https://www.youtube.com/watch?v={e['id']}"
                title = e.get("title") or q
        except Exception as ex:  # noqa: BLE001
            log.info("Поиск на YouTube: %s", ex)
    if not url:
        url, title = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q), None
    base.launch(browser_cmd(url))
    return f"Открыл на YouTube: «{title}»." if title else f"Открыл поиск на YouTube: {q}."


def media_players():
    """Сколько открыто плееров (MPRIS); None — узнать нельзя (Windows, Mac)."""
    if base.WIN or base.MAC:
        return None
    if base.DRY:
        return 1 if os.environ.get("DEWIAR_FAKE_PLAYING") or os.environ.get("DEWIAR_FAKE_PLAYER") else 0
    try:
        return len(_mpris_players(desktop_env())) if shutil.which("gdbus") else None
    except (OSError, subprocess.SubprocessError):
        return None


def media_playing():
    """Играет ли сейчас музыка/видео (MPRIS: браузер, плеер). True/False; None — узнать нельзя (Windows)."""
    r = RADIO[0] if RADIO else None
    if r is not None and r.playing:
        return True
    if base.MAC and not base.DRY:             # спросить «Музыку» можно только с разрешением на управление — не дёргаем его без просьбы
        return None
    if base.WIN or base.DRY:
        return None if base.WIN else bool(os.environ.get("DEWIAR_FAKE_PLAYING"))
    env = desktop_env()
    try:
        if shutil.which("playerctl"):
            out = subprocess.run(["playerctl", "-a", "status"], capture_output=True, text=True, env=env, timeout=3).stdout
            return "Playing" in out
        for pl in _mpris_players(env) if shutil.which("gdbus") else []:
            out = subprocess.run(["gdbus", "call", "--session", "--dest", pl, "--object-path", "/org/mpris/MediaPlayer2",
                                  "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player",
                                  "PlaybackStatus"], capture_output=True, text=True, env=env, timeout=3).stdout
            if "Playing" in out:
                return True
    except (OSError, subprocess.SubprocessError):
        return None
    return False


def t_media(a, ctx):
    action = a.get("action", "play_pause")
    r = ctx.get("radio")
    prefer = (ctx.get("music_pref") or (lambda: ""))()          # недавно открыта Яндекс Музыка — управляем ею
    # своё радио ядра — не MPRIS-плеер: кнопки для него обрабатываем сами
    if r and (r.playing or r.paused) and action in ("play", "pause", "play_pause", "stop", "next"):
        if action in ("pause", "stop") or (action == "play_pause" and r.playing):
            st = r.pause()
            return f"На паузе: «{(st or {}).get('name', '')}»"
        if action == "next" and r.station:
            from radio import search
            cur = r.station
            alts = [x for x in search(" ".join((cur.get("tags") or "").split(",")[:1]) or "") if x["url"] != cur["url"]]
            if alts:
                r.play(alts[0])
                return f"Следующая станция: «{alts[0]['name']}»"
        st = r.resume()
        if st:
            return f"Снова играет «{st['name']}»"
    methods = {"play": "Play", "pause": "Pause", "play_pause": "PlayPause", "next": "Next", "previous": "Previous",
               "stop": "Stop"}
    if action not in methods:
        raise ToolError("неизвестное действие")
    if base.DRY:
        base.launch(["media", action, prefer])
        return "Готово"
    if base.WIN:
        base.winsys.media(action)
        return "Готово"
    if base.MAC:
        who = base.macsys.media(action, prefer)
        if not who:
            raise ToolError("на Mac я управляю «Музыкой» и Spotify, а они не открыты. Музыку в браузере (YouTube, "
                            "Яндекс Музыка) поставь на паузу в самой вкладке")
        return {"play": "Включил воспроизведение", "pause": "Поставил на паузу", "play_pause": "Нажал «играть/пауза»",
                "next": "Следующий трек", "previous": "Предыдущий трек", "stop": "Остановил"}[action] + f" — {who}"
    env = desktop_env()
    done = {"play": "Включил воспроизведение", "pause": "Поставил на паузу", "play_pause": "Нажал «играть/пауза»",
            "next": "Следующий трек", "previous": "Предыдущий трек", "stop": "Остановил"}[action]
    app = MUSIC_APPS.get(prefer, {}).get("name", "")
    players = _mpris_players(env, prefer) if shutil.which("gdbus") else []
    if len(players) > 1 and not prefer:                    # «пауза» — тому, кто играет; «играй» — тому, кто на паузе
        want = {"pause": "Playing", "stop": "Playing", "play": "Paused"}.get(action)
        if want:
            def status(pl):
                try:
                    return subprocess.run(["gdbus", "call", "--session", "--dest", pl, "--object-path", "/org/mpris/MediaPlayer2",
                                           "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player",
                                           "PlaybackStatus"], capture_output=True, text=True, env=env, timeout=3).stdout
                except (OSError, subprocess.SubprocessError):
                    return ""
            players.sort(key=lambda pl: 0 if want in status(pl) else 1)
    if players:
        r = subprocess.run(["gdbus", "call", "--session", "--dest", players[0], "--object-path", "/org/mpris/MediaPlayer2",
                            "--method", f"org.mpris.MediaPlayer2.Player.{methods[action]}"], capture_output=True, env=env,
                           timeout=5)
        if r.returncode == 0:
            hit = app and any(w in players[0].lower() for w in MUSIC_APPS[prefer]["words"])
            want = {"play": "Playing", "pause": "Paused", "stop": "Stopped"}.get(action)
            if want:                                       # проверим, что плеер правда послушался, а не просто принял команду
                time.sleep(1.2)
                st = _mpris_status(env, players[0])
                if st and st != want and not (want == "Paused" and st == "Stopped"):
                    log.info("MPRIS %s: после %s состояние %s", players[0], methods[action], st)
                    return ("Нажал «играть», но плеер так и не заиграл — нажмите воспроизведение в самом приложении"
                            if want == "Playing" else "Нажал «пауза», но плеер продолжает играть")
            return done + (f" — {app}" if hit else "")
    if shutil.which("playerctl"):
        cmd = {"play_pause": "play-pause"}.get(action, action)
        r = subprocess.run(["playerctl", cmd], capture_output=True, text=True, env=env, timeout=5)
        if r.returncode == 0:
            return done
    raise ToolError("не вижу запущенного плеера — откройте музыку в браузере или в приложении (например, Яндекс Музыке)")


def t_play_music(a, ctx):
    q = (a.get("query") or "").strip()
    url = "https://music.youtube.com/search?q=" + urllib.parse.quote(q) if q else "https://music.youtube.com/"
    base.launch(browser_cmd(url))
    return f"Открыл YouTube Music{': ' + q if q else ''}. Пользователь нажмёт воспроизведение."


def _catt(args, timeout=40, device=""):
    """Запустить catt (трансляция на Chromecast) -> (код выхода, вывод). Берём catt рядом с нашим Python (venv)."""
    import sys as _sys
    from pathlib import Path as _P
    exe = _P(_sys.executable).with_name("catt")
    cmd = [str(exe) if exe.exists() else "catt"] + (["-d", device] if device else []) + args
    if base.DRY:
        base.launch(cmd)
        return 0, "ok"
    if base.WIN:                                 # в Windows нет отдельной команды catt — запускаем модуль
        py = _sys.executable
        if py.lower().endswith("pythonw.exe"):          # pythonw не даёт вывода — нужен консольный python.exe
            py = py[:-len("pythonw.exe")] + "python.exe"
        cmd = [py, "-X", "utf8", "-c", "from catt.cli import main; main()"] + cmd[1:]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                           creationflags=0x08000000 if base.WIN else 0)
    except FileNotFoundError as e:
        raise ToolError("не установлен модуль трансляции (catt) — переустановите Dewiar") from e
    except subprocess.TimeoutExpired as e:
        raise ToolError("телевизор не ответил вовремя") from e
    return r.returncode, (r.stdout + r.stderr).strip()


def _tv_device(a, ctx):
    """Имя телевизора: из аргумента, иначе из настроек tools.tv_device, иначе "" (catt выберет сам)."""
    return (a.get("device") or (ctx["settings"].get("tools", "tv_device") or "") if ctx.get("settings") else a.get("device") or "").strip()


def t_tv(a, ctx):
    action = a.get("action", "play")
    dev = _tv_device(a, ctx)
    if action == "devices":
        code, out = _catt(["scan"], timeout=25)
        if code or "No devices" in out:
            return ("Телевизоров с Chromecast в сети не нашёл. Подходят Chromecast, Google TV, Android TV и телевизоры "
                    "со встроенным Chromecast (Sony, Philips, Xiaomi, TCL…), в той же сети Wi-Fi, что и компьютер.")
        return out
    if action == "play":
        what = (a.get("url") or a.get("query") or "").strip()
        if not what:
            raise ToolError("что показать? нужна ссылка или что найти на YouTube")
        if not re.match(r"^https?://", what):               # «включи на телевизоре клип …» — ищем на YouTube
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as y:
                    info = y.extract_info(f"ytsearch1:{what}", download=False)
                e = (info.get("entries") or [None])[0]
                if not e:
                    raise ToolError(f"на YouTube не нашлось «{what}»")
                what = e.get("url") or f"https://www.youtube.com/watch?v={e['id']}"
            except ToolError:
                raise
            except Exception as ex:  # noqa: BLE001
                raise ToolError(f"не получилось найти на YouTube: {ex}") from ex
        code, out = _catt(["cast", what], timeout=60, device=dev)
        if code:
            raise ToolError(out[-300:] or "не получилось включить на телевизоре")
        return f"Включил на телевизоре: {what}"
    if action == "site":
        url = (a.get("url") or "").strip()
        if not re.match(r"^https?://", url):
            raise ToolError("нужен адрес сайта")
        code, out = _catt(["cast_site", url], device=dev)
        if code:
            raise ToolError(out[-300:] or "не получилось показать сайт на телевизоре")
        return f"Сайт {url} открыт на телевизоре."
    cmds = {"pause": ["pause"], "resume": ["play"], "stop": ["stop"], "status": ["status"]}
    if action == "volume":
        v = max(0, min(100, int(a.get("level", 30))))
        cmds["volume"] = ["volume", str(v)]
    if action not in cmds:
        raise ToolError("неизвестное действие")
    code, out = _catt(cmds[action], device=dev)
    if code:
        raise ToolError(out[-300:] or "телевизор не ответил")
    return out or "Готово"
