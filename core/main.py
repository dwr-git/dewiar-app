#!/usr/bin/env python3
"""Ядро Dewiar: настройки, персонажи, Engine (слух, мозг, голос) и Bridge — WebSocket для интерфейса на 127.0.0.1.
Linux: служба пользователя (systemd --user); Windows: ядро запускает интерфейс (ui/app.py), без консоли.

    python3 core/main.py              # обычный запуск
    python3 core/main.py --debug      # подробный лог
    python3 core/main.py --devices    # список микрофонов и динамиков

Для интерфейса оставляет файлы в STATE_DIR: logs/core.log (журнал), core.fail (почему не запустилось — ui/app.py
объясняет человеку, разбор — winav.py), на Windows core.pid (по нему ядро останавливают интерфейс и установщик).
"""

import argparse
import logging
import os
import signal
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # модули ядра импортируются по имени: import settings

from settings import WS_PORT, Settings, ensure_token, migrate_from_cortex  # noqa: E402

from version import VERSION  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--devices", action="store_true")
    ap.add_argument("--wav", help="вместо микрофона — WAV 16 кГц mono (для тестов)")
    ap.add_argument("--null-audio", action="store_true", help="не воспроизводить звук (для тестов)")
    ap.add_argument("--log", help="писать журнал в файл (Windows: без консоли)")
    ap.add_argument("--server", action="store_true",
                    help="режим сервера: без микрофона и звука — задачи с телефона, синхронизация, Telegram, напоминания "
                         "круглосуточно (packaging/dewiar-server.service)")
    args = ap.parse_args()

    if os.name == "nt":                         # Windows: вывод в UTF-8, даже если запустили без -X utf8
        for s in (sys.stdout, sys.stderr):
            try:
                s.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
    # Журнал — всегда в файл (по 2 МБ, 3 штуки): кнопка «Сохранить отчёт» берёт его оттуда.
    # Без --log — ещё и в консоль (на Linux её собирает журнал systemd); с --log — только в указанный файл.
    from logging.handlers import RotatingFileHandler
    from settings import STATE_DIR
    log_file = Path(args.log) if args.log else STATE_DIR / "logs" / "core.log"
    handlers = []
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"))
    except OSError:
        pass
    if not args.log:
        handlers.append(logging.StreamHandler())
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for h in handlers:
        h.setFormatter(fmt)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, handlers=handlers)
    for noisy in ("httpx", "httpcore", "websockets", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    log = logging.getLogger("dewiar")

    if args.devices:
        from audio_io import list_devices
        for d in list_devices():
            print(f"{d['kind']:6}  {d['name']}\n        {d['description']}")
        return

    try:   # падение в библиотеке (звук, голоса, onnxruntime) убивает процесс без строчки в журнале — пусть останется след
        # (пакет 23.10, №200: «постоянно теряется связь с ядром», а в журнале ядро просто обрывается). Отчёт берёт его отсюда.
        import faulthandler
        crash = (Path(args.log).parent if args.log else STATE_DIR / "logs") / "core.crash"
        if crash.exists() and crash.stat().st_size > 200_000:
            crash.unlink()
        _crash_fh = open(crash, "a", encoding="utf-8")
        _crash_fh.write(f"\n--- запуск {__import__('time').strftime('%Y-%m-%d %H:%M:%S')} · {VERSION}\n")
        _crash_fh.flush()
        faulthandler.enable(file=_crash_fh, all_threads=True)
    except Exception:  # noqa: BLE001
        pass
    import ortcfg
    ortcfg.limit()                             # DEWIAR_ORT_THREADS — своё число потоков ONNX (голоса), иначе как есть
    fail = STATE_DIR / "core.fail"            # почему ядро не запустилось — интерфейс прочтёт и объяснит (антивирус?); удачный запуск его стирает
    try:
        import net
        net.install()                          # прокси для серверов Dewiar — во всех запросах программы
        from bridge import Bridge
        from engine import Engine
        from personas import Personas

        log.info("Dewiar %s — запуск ядра", VERSION)
        try:                                   # №521, №523: прошлый запуск упал посреди работы — сторож окна (ui/app.py core_guard)
            import json as _json               # записал код выхода: оставим его в журнале — он уходит в отчёт
            ex = STATE_DIR / "core.exit"
            d = _json.loads(ex.read_text(encoding="utf-8"))
            ex.unlink(missing_ok=True)
            log.warning("Прошлый запуск ядра упал: %s", d.get("why") or d.get("code"))
        except (OSError, ValueError, AttributeError):
            pass
        migrate_from_cortex()
        settings = Settings()
        import egress                                       # стоп-кран и журнал «что уходило наружу» — до первых соединений
        egress.install(settings, STATE_DIR / "egress.json")
        egress.set_local_only(bool(settings.get("privacy", "local_only")))
        bridge = Bridge(ensure_token(), port=WS_PORT)
        server = args.server or os.environ.get("DEWIAR_SERVER") == "1"
        engine = Engine(settings, Personas(), bridge, wav_input=args.wav, null_player=args.null_audio or server, server=server)
        bridge.handler = engine.command
        bridge.start()
        engine.start()
    except BaseException as e:
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        import json
        import time
        import traceback
        log.exception("Ядро не запустилось")
        try:
            fail.parent.mkdir(parents=True, exist_ok=True)
            fail.write_text(json.dumps({"time": int(time.time()), "version": VERSION, "error": f"{type(e).__name__}: {e}",
                                        "trace": traceback.format_exc()[-3000:]}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        raise
    try:
        fail.unlink(missing_ok=True)
    except OSError:
        pass

    done = threading.Event()

    def stop(*_):
        log.info("Останавливаюсь…")
        done.set()
    engine.on_quit = stop
    if os.name == "nt":                         # интерфейс и установщик останавливают ядро по этому номеру (taskkill /PID)
        try:
            from settings import STATE_DIR
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            (STATE_DIR / "core.pid").write_text(str(os.getpid()), encoding="ascii")
            import atexit
            atexit.register(lambda: (STATE_DIR / "core.pid").unlink(missing_ok=True))
        except OSError:
            pass
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while not done.wait(0.5):                   # ждём по 0,5 с, а не бесконечно: так Python успевает обработать Ctrl+C
        pass
    engine.shutdown()

    def hard_exit():                            # не-фоновый поток (скачивание, ответ) держит процесс — а с ним порт и файлы,
        log.info("Завершаюсь принудительно: фоновые дела не закончились за 5 с")    # которые заменяет установщик
        if os.name == "nt":
            try:
                (STATE_DIR / "core.pid").unlink(missing_ok=True)
            except OSError:
                pass
        logging.shutdown()
        os._exit(0)
    t = threading.Timer(5, hard_exit)
    t.daemon = True
    t.start()


if __name__ == "__main__":
    main()
