"""Интерфейс Dewiar на Mac: окна pywebview на Cocoa (WKWebView), значок в строке меню, ядро своим процессом, обновление
приложения на месте.

Общая логика окон — в ui/app.py (класс Api). Там, где Linux работает с окнами через GTK, а Windows — через winshell,
здесь — методы самих окон pywebview (move, resize, show, hide) и немного AppKit (pyobjc: поднять окно без фокуса,
виджет на всех рабочих столах, рабочая область экрана). MacWindows подмешивается к Api (MacApi в main_mac), app.py
передаёт сюда себя (bind) — его SIZES, ZOOM, заголовки окон и помощники общие.

Чего на Mac пока нет: «Закинуть идею» одной клавишей из любой программы (окно открывается из значка в строке меню),
форма окна вырезом (виджет скругляет сама страница на прозрачном окне) и звук компьютера для суфлёра.
"""
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

A = None                      # модуль ui/app.py (bind)
STATUS = []                   # значок в строке меню: держим ссылки, иначе Objective-C его отпустит
KEEP = []                     # прочие объекты Cocoa, которые должны жить, пока живёт программа
SMOKE = os.environ.get("DEWIAR_UI_SMOKE", "")     # проверка сборки (packaging/macos/smoke.py): файл-метка «виджет загрузился»


def bind(mod):
    """app.py передаёт себя: дальше общие помощники (ensure_core, _notify) на Mac — свои."""
    global A
    A = mod
    mod.ensure_core = ensure_core
    mod._notify = notify


def bundle_path(root=None):
    """Dewiar.app, из которого запущены (пускач кладёт путь в DEWIAR_APP_BUNDLE), или None — запуск из исходников."""
    b = os.environ.get("DEWIAR_APP_BUNDLE")
    if b and b.endswith(".app"):
        return Path(b)
    root = Path(root or Path(__file__).resolve().parent.parent)     # …/Dewiar.app/Contents/Resources/app
    try:
        cand = root.parents[2]
        return cand if cand.suffix == ".app" else None
    except IndexError:
        return None


def log(text):
    print(f"{time.strftime('%H:%M:%S')} {text}", file=sys.stderr, flush=True)


def notify(text):
    """Уведомление Центра уведомлений (osascript; в Windows — сообщение от значка в трее)."""
    try:
        subprocess.Popen(["osascript", "-e", "on run argv\n display notification (item 1 of argv) with title \"Dewiar\"\nend run",
                          str(text)[:400]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


# ---------- ядро ----------

def log_dir():
    from settings import STATE_DIR
    d = STATE_DIR / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def start_core():
    """Ядро — отдельный процесс (своя сессия: переживает перезапуск окон), журнал — STATE_DIR/logs/core.log."""
    root = A.ROOT
    try:
        A.CORE_LOG_AT[0] = (log_dir() / "core.log").stat().st_size
    except OSError:
        A.CORE_LOG_AT[0] = 0
    A.CORE_LOG_AT[1] = time.time()
    p = subprocess.Popen([sys.executable, "-X", "utf8", str(root / "core" / "main.py"), "--log", str(log_dir() / "core.log")],
                         cwd=str(root), start_new_session=True, close_fds=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    A.CORE_PROC[:] = [p]
    return p


def ensure_core():
    """Ядро не отвечает на своём порту — запустить и подождать (первый запуск — несколько секунд)."""
    if A.core_alive():
        return
    start_core()
    for _ in range(60):
        if A.core_alive():
            return
        time.sleep(0.25)


def core_watch(limit=240, tries=2):
    """Ядро не вышло на связь — запустить ещё раз (tries раз); не вышло — уведомление с причиной (core.fail или
    последняя ошибка журнала). Блокирует — запускать в потоке."""
    from settings import STATE_DIR
    t0 = time.monotonic()
    while True:
        if A.core_alive():
            return True
        proc = A.CORE_PROC[0] if A.CORE_PROC else None
        gone, waited = proc is None or proc.poll() is not None, time.monotonic() - t0
        if gone and waited > 3 and tries > 0:
            tries -= 1
            log("ядро не отвечает — запускаю ещё раз")
            start_core()
            t0 = time.monotonic()
            continue
        if (gone and waited > 3) or waited > limit:
            break
        time.sleep(2)
    if A.core_alive():
        return True
    lines = []
    try:
        lines = (log_dir() / "core.log").read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    except OSError:
        pass
    why = A.core_fail_reason(lines, STATE_DIR / "core.fail")
    log(f"ядро не запустилось: {why or 'без ошибки в журнале'}")
    notify("Ядро Dewiar не запустилось" + (f": {why[:160]}" if why else "") + ". Значок Dewiar в строке меню → «Перезапустить ядро».")
    return False


# ---------- окна ----------

def _main(fn):
    """Выполнить в главном потоке Cocoa (окна AppKit трогать можно только оттуда)."""
    from PyObjCTools import AppHelper
    AppHelper.callAfter(fn)


def front(win, activate=False):
    """Показать окно поверх: activate — ещё и в фокус (студия); без него — не перебивая набор в другой программе
    (виджет появился на имя, напоминание)."""
    def run():
        nw = getattr(win, "native", None)
        if nw is None:
            return
        if activate:
            import AppKit
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            nw.makeKeyAndOrderFront_(None)
        else:
            nw.orderFrontRegardless()
    _main(run)


def everywhere(win):
    """Виджет — на всех рабочих столах (Spaces) и поверх программ во весь экран, без места в «Окне» и Cmd+`."""
    def run():
        nw = getattr(win, "native", None)
        if nw is not None:
            # CanJoinAllSpaces | IgnoresCycle | FullScreenAuxiliary
            nw.setCollectionBehavior_((1 << 0) | (1 << 6) | (1 << 8))
            nw.setExcludedFromWindowsMenu_(True)
    _main(run)


def work_area(x=None, y=None):
    """Рабочая область экрана (без строки меню и Дока), где точка (x, y) в координатах окон pywebview (от левого
    верхнего угла главного экрана). -> (x, y, ш, в); не узнали — экран pywebview или очень большая область."""
    try:
        import AppKit
        scr = list(AppKit.NSScreen.screens())
        main_h = scr[0].frame().size.height
        best = None
        for s in scr:
            f, v = s.frame(), s.visibleFrame()
            fx, fy = f.origin.x, main_h - (f.origin.y + f.size.height)
            if best is None:
                best = v
            if x is not None and fx <= x < fx + f.size.width and fy <= y < fy + f.size.height:
                best = v
                break
        return (int(best.origin.x), int(main_h - (best.origin.y + best.size.height)),
                int(best.size.width), int(best.size.height))
    except Exception:  # noqa: BLE001
        try:
            import webview
            s = webview.screens[0]
            return 0, 25, int(s.width), int(s.height) - 25
        except Exception:  # noqa: BLE001
            return 0, 0, 1 << 15, 1 << 15


def by_title(title):
    import webview
    return next((w for w in webview.windows if getattr(w, "title", "") == title), None)


class MacWindows:
    """Методы Api с окнами на Mac (подмешивается перед Api: MacApi(MacWindows, Api))."""

    # GTK на Mac нет: общие места, которые пробуют GTK и при неудаче показывают окно сами, получают None
    def _gtk(self, fn, timeout=3):
        return None

    def _gw(self, mode):
        return None

    def _studio_gw(self):
        return None

    def _work_area(self, x, y):
        return work_area(x, y)

    def _clamp(self, mode, x, y):
        w, h = A.SIZES[mode]
        mx, my, mw, mh = work_area(int(x) + w // 2, int(y) + h // 2)
        return max(mx, min(int(x), mx + mw - w)), max(my, min(int(y), my + mh - h))

    def get_pos(self, mode="card"):
        win = self.wins.get(mode)
        try:
            return [int(win.x), int(win.y)]
        except Exception:  # noqa: BLE001
            return [0, 0]

    def drag_begin(self, mode="card"):
        return False

    def native_drag(self):
        return False

    def drag_native(self, mode="card"):
        return False

    def move_to(self, mode, x, y):
        if mode == "card" and getattr(self, "_pad_on", False):
            self._pad_follow_at(x, y)
        win = self.wins.get(mode)
        if win is not None:
            win.move(int(x), int(y))

    def _place(self, mode, cx, cy):
        dx, dy = self._offset(mode)
        x, y = self._clamp(mode, cx + dx, cy + dy)
        win = self.wins[mode]
        win.move(x, y)
        front(win)
        return [x - dx, y - dy]

    def start_hud(self, mode, cx, cy):
        for m in A.SIZES:
            if m in self.wins:
                everywhere(self.wins[m])
        self.mode = mode
        self._place(mode, cx, cy)
        self._activate()

    def set_zoom(self, z):
        old = A.SIZES["card"]
        try:
            cx, cy = self.save_pos(self.mode)
        except Exception:  # noqa: BLE001
            cx = cy = None
        if not A.set_zoom_sizes(z):
            return None
        if cx is not None:
            cx, cy = cx + old[0] - A.SIZES["card"][0], cy + old[1] - A.SIZES["card"][1]
        for m, (w, h) in A.SIZES.items():
            if m in self.wins:
                self.wins[m].resize(w, h)
        if cx is not None and not self.in_tray:
            return self._place(self.mode, cx, cy)
        return None

    def resize_card(self, w, h, final=False):
        z = A.ZOOM[0] or 1.0
        if not w or not h:
            A.set_card_base(*A.CARD_DEFAULT)
        else:
            A.set_card_base(float(w) / z, float(h) / z)
        A.set_zoom_sizes(z)
        W, H = A.SIZES["card"]
        if final and getattr(self, "_pad_on", False):
            ps = list(getattr(self, "_pad_size", None) or [None, None])
            threading.Timer(0.4, lambda: self.pad_resize(ps[0] * z if ps[0] else 0, ps[1] * z if ps[1] else 0, True)).start()
        try:
            self.wins["card"].resize(W, H)
        except Exception as e:  # noqa: BLE001
            log(f"размер виджета: {e}")
            return None
        return list(A.BASE_SIZES["card"])

    def set_mode(self, mode, auto=False):
        if mode not in A.SIZES:
            return None
        self.auto = bool(auto)
        if mode == self.mode:
            return self.save_pos(mode)
        src = self.mode
        x, y = self.get_pos(src)
        dx, dy = self._offset(src)
        p = self._place(mode, x - dx, y - dy)
        self.wins[src].hide()
        self.mode = mode
        self._activate()
        return p

    def show(self):
        if self.in_tray:
            self.popped = True
        front(self.wins[self.mode])

    def _hide_now(self):
        self.wins[self.mode].hide()

    def bring_back(self):
        x, y = self.get_pos(self.mode)
        self._place(self.mode, x - self._offset(self.mode)[0], y - self._offset(self.mode)[1])
        front(self.wins[self.mode], activate=True)
        return True

    def hide(self):
        self.wins[self.mode].hide()
        notify("Dewiar продолжает слушать. Вернуть виджет — значок Dewiar в строке меню.")

    def tray_state(self):
        return {"in_tray": self.in_tray, "icon": bool(STATUS)}

    def _card_h(self):
        try:
            return int(self.wins["card"].height)
        except Exception:  # noqa: BLE001
            return 0

    def _focus_title(self, title):
        win = by_title(title)
        if win is not None:
            front(win, activate=True)

    # ---------- буфер обмена (AppKit NSPasteboard) ----------

    def clip_text(self, text):
        text = str(text or "")
        if not text:
            return False
        try:
            import AppKit
            pb = AppKit.NSPasteboard.generalPasteboard()
            pb.clearContents()
            return bool(pb.setString_forType_(text, AppKit.NSPasteboardTypeString))
        except Exception as e:  # noqa: BLE001
            log(f"буфер обмена: {e}")
            return False

    def clip_secret(self, text, sec=30):
        """Пароль из сейфа: в буфер с пометкой «скрытое» (менеджеры буфера её уважают) и через sec секунд стереть, если
        там всё ещё он."""
        text, sec = str(text or ""), max(5, min(300, int(sec or 30)))
        if not text:
            return False
        try:
            import AppKit
            pb = AppKit.NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, AppKit.NSPasteboardTypeString)
            pb.setString_forType_("", "org.nspasteboard.ConcealedType")
            n = pb.changeCount()

            def wipe():
                try:
                    if pb.changeCount() == n and pb.stringForType_(AppKit.NSPasteboardTypeString) == text:
                        pb.clearContents()
                except Exception:  # noqa: BLE001
                    pass
            threading.Timer(sec, wipe).start()
            return True
        except Exception as e:  # noqa: BLE001
            log(f"буфер обмена (сейф): {e}")
            return False

    def clipboard_image(self):
        import base64
        import io
        try:
            from PIL import ImageGrab
            im = ImageGrab.grabclipboard()
            if im is None or isinstance(im, list):
                return ""
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=88)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception as e:  # noqa: BLE001
            log(f"буфер обмена: {e}")
            return ""

    # ---------- ссылки, папки ----------

    def open_url(self, url):
        url = str(url or "")
        if url.split(":", 1)[0].lower() not in ("http", "https", "obsidian", "tg", "ton"):
            return False
        subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def open_skills_folder(self, path=""):
        d = Path(path) if path else A.SETTINGS_PATH.parent / "skills"
        d.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def install_codec(self):
        return {"ok": False, "error": "на Mac видео уже играет — кодек не нужен"}

    def capture_status(self):
        import hotkey
        uis = A.ui_settings()
        return {"on": uis.get("capture", True) is not False, "key": uis.get("capture_key") or hotkey.DEFAULT, "works": False,
                "how": "на Mac одной клавишей пока нет — окно «Закинуть идею» открывается из значка Dewiar в строке меню",
                "command": ""}

    def capture_set(self, on=True, key=""):
        try:
            A._core_save_ui(self.token, {"capture": bool(on)})
        except Exception:  # noqa: BLE001
            pass
        return self.capture_status()

    # ---------- студия ----------

    def open_settings(self, page="", query=""):
        """Студия в обычном окне Mac (системная рамка: перетаскивание, «светофор», полноэкранный режим)."""
        import urllib.parse
        import webview
        log(f"студия: открыть {page or ''}{' (с параметрами)' if query else ''}")
        st = self._studio
        if st is not None and not query:
            try:
                front(st, activate=True)
                if page:
                    st.evaluate_js(f"(document.querySelector('nav button[data-p=\"{page}\"]') || {{click(){{}}}}).click()")
                return
            except Exception:  # noqa: BLE001
                self._studio = None
        if self._studio is not None:
            try:
                self._studio.destroy()
            except Exception:  # noqa: BLE001
                pass
        sw, sh = self._studio_size()
        skin, light = A.ui_skin()
        url = self._url("settings.html", "&skin=" + urllib.parse.quote(skin) + query + ("#" + page if page else ""))
        win = webview.create_window(A.STUDIO_TITLE, url, width=sw, height=sh, min_size=(min(820, sw), min(560, sh)),
                                    background_color="#e3eaf4" if light else "#0a0a0f", text_select=True, js_api=self)
        self._studio, self._studio_born = win, time.monotonic()
        win.events.closed += lambda *a: self._studio_closed(win)
        win.events.shown += lambda *a: front(win, activate=True)
        if hasattr(win.events, "resized"):
            win.events.resized += lambda *a: self._studio_resized(win, *a[:2])

    def _raise_studio(self):
        if self._studio is not None:
            front(self._studio, activate=True)

    def _studio_resized(self, win, w=None, h=None):
        self._st_rs = getattr(self, "_st_rs", 0) + 1
        n = self._st_rs

        def later():
            if n != self._st_rs or self._studio is not win:
                return
            try:
                ww, hh = int(w or win.width), int(h or win.height)
                if ww >= 400 and hh >= 300:
                    A._core_save_ui(self.token, {"studio_size": [ww, hh], "studio_max": False})
            except Exception as e:  # noqa: BLE001
                log(f"размер студии не запомнил: {e}")
        t = threading.Timer(1.0, later)
        t.daemon = True
        t.start()

    def studio_max(self):
        st = self._studio
        if st is None:
            return False
        box = {}
        done = threading.Event()

        def run():
            try:
                nw = st.native
                nw.zoom_(None)
                box["z"] = bool(nw.isZoomed())
            finally:
                done.set()
        _main(run)
        done.wait(2)
        return box.get("z", False)

    # ---------- блокнот, «вырезать с экрана» ----------

    def _pad_shape(self, g):
        return None                    # формы окна на Mac нет: лист рисует страница

    def _pad_place(self, x, y):
        win = getattr(self, "_pad", None)
        if win is not None:
            win.move(int(x), int(y))

    def _pad_apply(self, g, final=False):
        win = getattr(self, "_pad", None)
        try:
            if win is not None:
                win.resize(g["w"] + g["gap"], g["h"])
                win.move(g["x"], g["y"])
            if final:
                self._pad_js(self._pad_cfg_js(g))
        except Exception as e:  # noqa: BLE001
            log(f"размер блокнота: {e}")

    def pad_open(self, mode="notes"):
        win = getattr(self, "_pad", None)
        if win is None or self.mode != "card" or self._pad_dead():
            return super().pad_open(mode)              # первый раз (или окно умерло) — общий путь создаёт окно
        mode = "play" if mode == "play" else "notes"
        self._pad_mode = mode
        self._stay()
        g = self._pad_geom()
        self._pad_g, self._pad_side, self._pad_on = g, g["side"], True
        self._pad_apply(g)
        front(win)
        game, self._pad_game = getattr(self, "_pad_game", ""), ""
        self._pad_js(self._pad_cfg_js(g) + f"; window.padShown && padShown('{g['side']}'); window.padMode && padMode('{mode}')"
                     + (f"; window.padGame && padGame('{game}')" if mode == "play" and game else ""))
        self._js(f"window.padMark && padMark(true, '{mode}')")
        return True

    def _pad_hide_now(self):
        win = getattr(self, "_pad", None)
        if win is not None:
            try:
                win.hide()
            except Exception:  # noqa: BLE001
                pass
        self._js("window.padMark && padMark(false)")

    def pad_hide(self):
        if getattr(self, "_pad_full", False):
            self.pad_full(False)
        self._pad_on = False
        win = getattr(self, "_pad", None)
        if win is not None:
            try:
                win.hide()
            except Exception:  # noqa: BLE001
                pass
        self._js("window.padMark && padMark(false)")
        return True

    def pad_full(self, on):
        on, prev = bool(on), bool(getattr(self, "_pad_full", False))
        self._pad_full = on
        if on == prev:
            return on
        win = getattr(self, "_pad", None)
        try:
            if on and win is not None:
                x, y, w, h = work_area(*self.get_pos("card"))
                win.resize(w, h)
                win.move(x, y)
                self._pad_js("window.padCfg && padCfg({side: 'left', gap: 0, clips: []})")
            elif not on:
                g = self._pad_geom()
                self._pad_g, self._pad_side = g, g["side"]
                threading.Timer(0.35, lambda: self._pad_apply(g, True)).start()
        except Exception as e:  # noqa: BLE001
            log(f"лист на весь экран: {e}")
        return on

    def snip_show(self):
        win = getattr(self, "_snip", None)
        if win is None or win == "opening":
            return False
        self._snip_shown = True
        try:
            import webview
            s = webview.screens[0]
            win.resize(int(s.width), int(s.height))
            win.move(0, 0)
            front(win, activate=True)
            return True
        except Exception as e:  # noqa: BLE001
            log(f"окно «Вырезать с экрана»: {e}")
            return False

    # ---------- ядро, выход, перезапуск, обновление ----------

    def restart_core(self):
        def run():
            from settings import STATE_DIR
            try:
                try:
                    A._core_call(self.token, "quit")
                except Exception:  # noqa: BLE001
                    pass
                for p in A.CORE_PROC:
                    try:
                        p.terminate()
                        p.wait(8)
                    except Exception:  # noqa: BLE001
                        try:
                            p.kill()
                        except Exception:  # noqa: BLE001
                            pass
                try:
                    os.kill(int((STATE_DIR / "core.pid").read_text().strip()), 15)
                except (OSError, ValueError):
                    pass
                time.sleep(1.5)
                ensure_core()
                log("ядро перезапущено по кнопке")
            except Exception as e:  # noqa: BLE001
                log(f"перезапуск ядра не удался: {e}")
        threading.Thread(target=run, daemon=True).start()
        return True

    def quit_all(self):
        log("выход: ядро и интерфейс завершаются")
        try:
            A._core_call(self.token, "quit")
        except Exception:  # noqa: BLE001
            for p in A.CORE_PROC:
                try:
                    p.terminate()
                except Exception:  # noqa: BLE001
                    pass
        os._exit(0)

    def restart(self, note="Dewiar обновлён."):
        notify(note)
        b = bundle_path(A.ROOT)
        if b is not None:
            relaunch(b, wait_pid=os.getpid())
            os._exit(0)
        try:
            os.execv(sys.executable, [sys.executable, str(Path(A.__file__).resolve()), "--autostart"])
        except OSError as e:
            log(f"перезапуск не удался: {e}")

    def install_update(self, path):
        """«Обновить»: скачанный и проверенный (sha256) образ Dewiar-…-mac.dmg из STATE_DIR/updates — открыть, новое
        приложение скопировать рядом с нынешним, затем (отдельным сценарием, когда мы вышли) подменить и запустить.
        Ход — в update_progress, как на Linux."""
        from settings import STATE_DIR
        p = Path(path or "").resolve()
        allowed = STATE_DIR.resolve() / "updates"
        if allowed not in p.parents or p.suffix.lower() != ".dmg" or not p.is_file():
            return {"ok": False, "error": "это не скачанное обновление Dewiar"}
        b = bundle_path(A.ROOT)
        why = update_blocker(b)
        if why:
            return {"ok": False, "error": why}
        if getattr(self, "_upd", {}).get("stage") in ("install", "restart"):
            return {"ok": True, "started": True}
        self._upd = {"stage": "install", "pct": 5, "line": "открываю образ…", "error": "", "t0": time.time()}
        threading.Thread(target=self._run_update_mac, args=(p, b, allowed), name="update", daemon=True).start()
        return {"ok": True, "started": True}

    def _run_update_mac(self, dmg, bundle, allowed):
        u = self._upd
        try:
            new = stage_update(dmg, bundle, lambda pct, line: u.update(pct=pct, line=line))
        except Exception as e:  # noqa: BLE001
            u.update(stage="error", error=str(e)[:400])
            return
        try:                                       # после перезапуска ядро сверит версию (updater._check_pending)
            (allowed / "pending.json").write_text(json.dumps({"file": dmg.name, "ts": time.time()}), encoding="utf-8")
        except OSError:
            pass
        u.update(stage="restart", pct=100, line="перезапускаюсь новой версией…")
        try:
            A._core_call(self.token, "quit")
        except Exception:  # noqa: BLE001
            pass
        swap_and_relaunch(bundle, new, our_pids(), [p.pid for p in A.CORE_PROC if p.poll() is None])
        threading.Timer(1.0, lambda: os._exit(0)).start()


# ---------- обновление приложения ----------

def update_blocker(bundle):
    """Почему обновить на месте нельзя (словами) или ""."""
    if bundle is None:
        return "Dewiar запущен из исходников — обновите их (git pull), а приложение для Mac — с dewiar.pro"
    if str(bundle).startswith("/Volumes/"):
        return ("Dewiar запущен прямо из образа диска. Перетащите Dewiar в «Программы», откройте оттуда — "
                "и обновления будут ставиться сами")
    if "/AppTranslocation/" in str(bundle):
        return ("macOS запустила Dewiar из временной папки (так бывает с приложениями из «Загрузок»). Перетащите Dewiar "
                "в «Программы» и откройте оттуда — тогда обновления будут ставиться сами")
    if not os.access(bundle.parent, os.W_OK):
        return (f"нет прав на папку «{bundle.parent}» — скачайте Dewiar-mac.dmg с dewiar.pro и перетащите Dewiar "
                "в «Программы» заново (Mac спросит пароль администратора)")
    return ""


def stage_update(dmg, bundle, progress=lambda pct, line: None, run=subprocess.run):
    """Открыть образ (без окна Finder, только чтение), скопировать оттуда Dewiar.app рядом с нынешним
    («.Dewiar-new.app» — та же папка, значит, подмена потом — мгновенное переименование) и закрыть образ.
    -> путь к новой копии. Ошибки — RuntimeError словами."""
    import tempfile
    mnt = Path(tempfile.mkdtemp(prefix="dewiar-dmg-"))
    new = bundle.parent / ".Dewiar-new.app"
    r = run(["hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen", "-mountpoint", str(mnt), str(dmg)],
            capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError("образ не открылся: " + ((r.stderr or r.stdout or "").strip()[-200:] or f"код {r.returncode}"))
    try:
        src = mnt / "Dewiar.app"
        if not (src / "Contents" / "MacOS" / "Dewiar").exists():
            raise RuntimeError("в образе нет Dewiar.app")
        progress(30, "копирую новую версию…")
        if new.exists():
            run(["rm", "-rf", str(new)], capture_output=True, timeout=120)
        r = run(["ditto", str(src), str(new)], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError("не скопировалось: " + (r.stderr or "").strip()[-200:])
        progress(80, "проверяю подпись…")
        r = run(["codesign", "--verify", "--deep", "--strict", str(new)], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            run(["rm", "-rf", str(new)], capture_output=True, timeout=120)
            raise RuntimeError("подпись новой версии не сошлась — скачайте Dewiar-mac.dmg с dewiar.pro заново")
        run(["xattr", "-dr", "com.apple.quarantine", str(new)], capture_output=True, timeout=60)
    finally:
        run(["hdiutil", "detach", str(mnt), "-force"], capture_output=True, timeout=60)
        try:
            mnt.rmdir()
        except OSError:
            pass
    progress(90, "готово, перезапуск…")
    return new


def swap_script(bundle, new, pids):
    """Сценарий подмены (sh): дождаться, пока окна и ядро выйдут (до ~60 с), прежнее приложение — в сторону, новое — на
    его место, прежнее удалить, открыть новое. Не встало (переименование не удалось) — вернуть прежнее и открыть его."""
    q = shlex.quote
    old = bundle.parent / ".Dewiar-old.app"
    waits = "".join(f"  kill -0 {int(p)} 2>/dev/null && alive=1\n" for p in pids)
    return ("#!/bin/sh\n"
            "# Dewiar: подмена приложения новой версией (ui/macui.py swap_script)\n"
            "i=0\n"
            "while [ $i -lt 120 ]; do\n"
            "  alive=0\n" + waits +
            "  [ $alive = 0 ] && break\n"
            "  i=$((i+1)); sleep 0.5\n"
            "done\n"
            f"rm -rf {q(str(old))}\n"
            f"if mv {q(str(bundle))} {q(str(old))}; then\n"
            f"  if mv {q(str(new))} {q(str(bundle))}; then\n"
            f"    rm -rf {q(str(old))}\n"
            "  else\n"
            f"    mv {q(str(old))} {q(str(bundle))}\n"
            "  fi\n"
            "fi\n"
            f"/usr/bin/open -a {q(str(bundle))} --args --autostart\n"
            'rm -f "$0"\n')


def swap_and_relaunch(bundle, new, *pid_lists):
    import tempfile
    pids = []
    for x in pid_lists:
        pids += list(x) if isinstance(x, (list, tuple)) else [x]
    f = Path(tempfile.gettempdir()) / f"dewiar-swap-{os.getpid()}.sh"
    f.write_text(swap_script(bundle, new, pids), encoding="utf-8")
    os.chmod(f, 0o700)
    subprocess.Popen(["/bin/sh", str(f)], start_new_session=True, close_fds=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def our_pids():
    """Кого ждать перед новым запуском: этот процесс и пускач (родитель — Dewiar.app/Contents/MacOS/Dewiar): пока пускач
    жив, macOS на `open` просто «будит» его, а не запускает приложение заново."""
    pids = [os.getpid()]
    try:
        pp = os.getppid()
        r = subprocess.run(["ps", "-o", "comm=", "-p", str(pp)], capture_output=True, text=True, timeout=3)
        if r.stdout.strip().endswith("/Contents/MacOS/Dewiar"):
            pids.append(pp)
    except (OSError, subprocess.SubprocessError):
        pass
    return pids


def relaunch(bundle, wait_pid):
    """Открыть приложение заново, когда этот процесс (и его пускач) выйдут (перезапуск окон)."""
    waits = " || ".join(f"kill -0 {int(p)} 2>/dev/null" for p in sorted(set([int(wait_pid)] + our_pids())))
    script = (f"i=0; while [ $i -lt 100 ] && ( {waits} ); do i=$((i+1)); sleep 0.3; done; "
              f"/usr/bin/open -a {shlex.quote(str(bundle))} --args --autostart")
    subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True, close_fds=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------- значок в строке меню ----------

def status_item(api, items):
    """Значок Dewiar в строке меню (справа, у часов) с меню; пункты выполняются в своих потоках. Вызывать в главном
    потоке Cocoa. Шаблонная картинка: macOS сама красит её под светлую и тёмную строку меню."""
    import AppKit
    import objc
    from Foundation import NSObject

    acts = [fn for _t, fn in items]

    class DewiarStatusTarget(NSObject):
        @objc.typedSelector(b"v@:@")
        def act_(self, sender):
            fn = acts[int(sender.tag())]
            threading.Thread(target=fn, daemon=True).start()

    bar = AppKit.NSStatusBar.systemStatusBar()
    item = bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)
    icon = A.ROOT / "icons" / "dewiar-tray.png"
    img = AppKit.NSImage.alloc().initWithContentsOfFile_(str(icon))
    if img is not None:
        img.setSize_((18, 18))
        img.setTemplate_(True)
        item.button().setImage_(img)
    else:
        item.button().setTitle_("Dewiar")
    item.button().setToolTip_("Dewiar — голосовой ассистент")
    target = DewiarStatusTarget.alloc().init()
    menu = AppKit.NSMenu.alloc().init()
    for i, (title, fn) in enumerate(items):
        if title is None:
            menu.addItem_(AppKit.NSMenuItem.separatorItem())
            continue
        mi = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "act:", "")
        mi.setTarget_(target)
        mi.setTag_(i)
        menu.addItem_(mi)
    item.setMenu_(menu)
    STATUS[:] = [item, target, menu]
    return item


# ---------- запуск ----------

def autostart(uis):
    """Запуск вместе с Mac: включён по умолчанию (как галочка в установщике Windows); ui.autostart = false — выключен.
    Путь к приложению в LaunchAgent поправляется при каждом запуске (Dewiar могли перенести)."""
    b = bundle_path(A.ROOT)
    if b is None or str(b).startswith("/Volumes/") or "/AppTranslocation/" in str(b) or SMOKE:
        return
    sys.path.insert(0, str(A.ROOT / "core"))
    import macsys
    macsys.autostart_set(uis.get("autostart", True) is not False, b)


def main_mac(args, extra):
    """Mac: один экземпляр (flock), ядро — свой процесс и его сторож, виджет на прозрачном окне без рамки (углы скругляет
    страница), студия — обычное окно, значок в строке меню."""
    os.environ.setdefault("DEWIAR_UI_HTTP", "1")        # страницы — с локального веб-сервера (адрес с ?token=… не теряется)
    import webview
    from settings import STATE_DIR
    A.migrate_from_cortex()
    held = A.lock("ui")
    sig = STATE_DIR / "ui.signal"
    if held is None:                                     # уже запущен — попросить показаться (или открыть студию)
        try:
            sig.parent.mkdir(parents=True, exist_ok=True)
            sig.write_text("capture" if args.capture else ("settings" + extra) if args.settings else "hud", encoding="utf-8")
        except OSError:
            pass
        return
    try:
        (STATE_DIR / "ui.pid").write_text(str(os.getpid()), encoding="ascii")
    except OSError:
        pass
    fresh = not A.SETTINGS_PATH.exists() or A.ui_settings().get("welcome") == ""
    ensure_core()
    threading.Thread(target=core_watch, name="core-watch", daemon=True).start()
    uis = A.ui_settings()
    threading.Thread(target=autostart, args=(uis,), daemon=True).start()

    class MacApi(MacWindows, A.Api):
        pass

    api = MacApi(A.ensure_token())
    A.TRANSPARENT[0] = True                              # окно прозрачное, углы и тень рисует страница (&tw=1)
    A.set_card_base(uis.get("hud_w") or A.CARD_DEFAULT[0], uis.get("hud_h") or A.CARD_DEFAULT[1])
    A.set_zoom_sizes(uis.get("zoom"))
    mode = "card"
    x, y = uis.get("hud_x"), uis.get("hud_y")
    if x is None or y is None:
        mx, my, mw, mh = work_area()
        x, y = mx + mw - A.SIZES["card"][0] - A.MARGIN, my + mh - A.SIZES["card"][1] - A.MARGIN
    w, h = A.SIZES["card"]
    api.wins["card"] = webview.create_window(A.TITLES["card"], api._url("hud.html", "&mode=card&tw=1"), width=w, height=h,
                                             resizable=False, min_size=(w, h), frameless=True, easy_drag=False,
                                             on_top=A.ON_TOP[0], hidden=True, transparent=True,
                                             background_color="#0b0b0e", js_api=api)
    api._hud = api.wins["card"]
    if SMOKE:
        def smoke_ok(*_a):
            for _ in range(120):
                if A.core_alive():
                    break
                time.sleep(0.5)
            Path(SMOKE).write_text(json.dumps({"widget": "loaded", "core": A.core_alive(), "studio": api._studio is not None}),
                                   encoding="utf-8")
            time.sleep(1.5)
            api.quit_all()
        api._hud.events.loaded += lambda *a: threading.Thread(target=smoke_ok, daemon=True).start()

    def on_start():
        try:
            api.start_hud(mode, x, y)
            if A.start_in_tray(uis, args):
                api.to_tray(quiet=True)
        except Exception as e:  # noqa: BLE001
            log(f"виджет не показан: {e}")
        items = [("Показать Dewiar", api.from_tray), ("Студия", lambda: api.open_settings()),
                 ("Закинуть идею", api.show_capture), ("Убрать в трей", api.to_tray), (None, None),
                 ("Перезапустить ядро", api.restart_core), (None, None), ("Выйти из Dewiar", api.quit_all)]
        _main(lambda: _status(api, items))
        _main(lambda: _on_terminate(api))
        if args.settings:
            api.open_settings("connect" if extra else "", extra)
        elif fresh and not SMOKE:
            api.open_settings("")
        elif args.capture:
            api.show_capture()

        def watch():
            while True:
                time.sleep(0.3)
                for line in launcher_lines():
                    try:
                        launcher_do(api, line)
                    except Exception as e:  # noqa: BLE001
                        log(f"пускач ({line[:60]}): {e}")
                try:
                    if not sig.exists():
                        continue
                    what = sig.read_text(encoding="utf-8").strip()
                    sig.unlink()
                except OSError:
                    time.sleep(2)
                    continue
                try:
                    if what == "capture":
                        api.show_capture()
                        continue
                    api.from_tray()
                    api.bring_back()
                    if what.startswith("settings"):
                        q = what[len("settings"):]
                        api.open_settings("connect" if q else "", q)
                except Exception as e:  # noqa: BLE001
                    log(f"сигнал «покажись» ({what}): {e}")
        threading.Thread(target=watch, name="show-signal", daemon=True).start()

    icon = A.ROOT / "icons" / "dewiar-512.png"
    webview.start(on_start, debug=bool(os.environ.get("DEWIAR_UI_DEBUG")), icon=str(icon) if icon.exists() else None)
    # окна закрыты (выход из меню программы, Cmd+Q) — завершаем и ядро, как «Выйти из Dewiar»
    api.quit_all()
    del held


LAUNCHER_SIGNAL = Path.home() / "Library" / "Caches" / "Dewiar" / "launcher.signal"


def launcher_lines(path=None):
    """Строки от пускача (packaging/macos/launcher.m): «hud» — Dewiar открыли ещё раз; «open <ссылка или файл>»."""
    f = Path(path or LAUNCHER_SIGNAL)
    try:
        if not f.exists():
            return []
        text = f.read_text(encoding="utf-8")
        f.unlink()
    except OSError:
        return []
    return [x.strip() for x in text.splitlines() if x.strip()]


def launcher_action(line):
    """Строка пускача -> (что сделать, параметры студии): ("hud", "") | ("settings", "&address=…") | ("settings",
    "&import=…") | (None, "") — не наше."""
    from urllib.parse import quote, unquote, urlparse
    if line == "hud":
        return "hud", ""
    if not line.startswith("open "):
        return None, ""
    t = line[5:].strip()
    if t.startswith("dewiar:"):
        return "settings", "&address=" + quote(t, safe="")
    if t.startswith("file://"):
        t = unquote(urlparse(t).path)
    if t.lower().endswith(".dewiar"):
        return "settings", "&import=" + quote(str(Path(t).resolve()), safe="")
    return None, ""


def launcher_do(api, line):
    what, q = launcher_action(line)
    if what is None:
        return
    api.from_tray()
    api.bring_back()
    if what == "settings":
        api.open_settings("connect", q)


def _on_terminate(api):
    """Cmd+Q, «Завершить» в Доке, выход из системы: Cocoa завершает процесс сама (exit), до конца main_mac дело не
    доходит — ядро просим выйти здесь, иначе оно слушало бы и отвечало без окон."""
    try:
        import AppKit

        def bye(_note):
            try:
                A._core_call(api.token, "quit", timeout=2)
            except Exception:  # noqa: BLE001
                for p in A.CORE_PROC:
                    try:
                        p.terminate()
                    except Exception:  # noqa: BLE001
                        pass
        KEEP.append(AppKit.NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
            AppKit.NSApplicationWillTerminateNotification, None, None, bye))
    except Exception as e:  # noqa: BLE001
        log(f"выход по Cmd+Q: {e}")


def _status(api, items):
    try:
        api._tray = status_item(api, items)          # «убрать в трей» тогда говорит про значок, а не про меню программ
    except Exception as e:  # noqa: BLE001 — без значка всё остальное работает
        log(f"значок в строке меню: {e}")
