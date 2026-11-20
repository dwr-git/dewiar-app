"""Запись «какие файлы проекта трогает проверка» (15.11, владелец: «выпуски стали очень долгими» — карта для выбора
проверок по изменению, tools/test_impact.py).

Подключается только при прогоне с записью: run_quick.sh кладёт эту папку в PYTHONPATH и задаёт DEWIAR_TRACE_FILE (куда
писать) и DEWIAR_TRACE_ROOT (корень проекта). Тогда каждый процесс Python этой проверки — и она сама, и ядро, и всё,
что она запустит, — дописывает в файл пути открытых файлов проекта (чтение, импорт модулей) и просмотренных папок
(«dir:ui/studio»). Без этих переменных ничего не делает. В конце передаёт управление прежнему sitecustomize, если он есть."""
import os
import sys

_FILE = os.environ.get("DEWIAR_TRACE_FILE")
_ROOT = os.environ.get("DEWIAR_TRACE_ROOT")
# вторая копия записи в том же процессе (проверка записи запускает её внутри прогона с записью: две папки tests/trace в
# PYTHONPATH) — ничего не ставит и никого не зовёт: иначе копии бесконечно вызывали бы друг друга как «прежний sitecustomize»
_AGAIN = bool(getattr(sys, "_dewiar_trace", False))
sys._dewiar_trace = True

if _FILE and _ROOT and not _AGAIN:
    _root = os.path.realpath(_ROOT) + os.sep
    _seen = set()
    _busy = [False]

    def _note(rel):
        if rel in _seen:
            return
        _seen.add(rel)
        _busy[0] = True
        try:
            fd = os.open(_FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                os.write(fd, (rel + "\n").encode("utf-8", "replace"))
            finally:
                os.close(fd)
        except OSError:
            pass
        finally:
            _busy[0] = False

    def _hook(ev, args):
        if _busy[0] or ev not in ("open", "os.listdir", "os.scandir"):
            return
        try:
            p = args[0] if args else None
            if isinstance(p, bytes):
                p = p.decode("utf-8", "replace")
            if not isinstance(p, str) or not p:
                return
            if ev != "open":                        # папку смотрит сам импорт (поиск модулей) — это не зависимость
                f = sys._getframe(1)
                for _ in range(6):
                    if f is None:
                        break
                    if str(f.f_globals.get("__name__", "")).startswith(("importlib", "_frozen_importlib", "pkgutil", "zipimport", "site")):
                        return
                    f = f.f_back
            if not os.path.isabs(p):
                p = os.path.join(os.getcwd(), p)
            p = os.path.normpath(p)
            if not p.startswith(_root) and p + os.sep != _root:
                if os.path.realpath(p).startswith(_root):
                    p = os.path.realpath(p)
                else:
                    return
            rel = os.path.relpath(p, _root).replace(os.sep, "/")
            if rel.startswith(".."):
                return
            if "/__pycache__/" in "/" + rel:              # модуль из кэша: core/__pycache__/llm.cpython-313.pyc -> core/llm.py
                if not rel.endswith(".pyc"):
                    return
                d, f = rel.rsplit("__pycache__/", 1)
                rel = d + f.split(".")[0] + ".py"
            _note(("dir:" + rel) if ev != "open" else rel)
        except Exception:  # noqa: BLE001 — запись не должна ронять проверку
            pass

    sys.addaudithook(_hook)

    # Какие функции проекта выполнились (17.11, владелец: «код модульный… значительно сократить количество проверок»):
    # «fn:core/llm.py::Llm.chat» — по разу на функцию (DISABLE после первого входа: почти без замедления). Вложенные
    # функции и lambda — на счёт внешней («f.<locals>.g» → «f»). Тексты проверок (tests/) — не пишем.
    _mon = getattr(sys, "monitoring", None)
    if _mon is not None:
        _tool = None
        for _id in (_mon.COVERAGE_ID, _mon.PROFILER_ID, 4):
            try:
                _mon.use_tool_id(_id, "dewiar-trace")
                _tool = _id
                break
            except ValueError:
                continue
        if _tool is not None:
            _DIS = _mon.DISABLE
            _fseen = {}

            def _start(code, _off):
                fn = code.co_filename
                rel = _fseen.get(fn)
                if rel is None:
                    rel = ""
                    try:
                        if fn.endswith(".py"):
                            q = os.path.normpath(fn if os.path.isabs(fn) else os.path.join(os.getcwd(), fn))
                            if not q.startswith(_root) and os.path.realpath(q).startswith(_root):
                                q = os.path.realpath(q)
                            if q.startswith(_root):
                                r = os.path.relpath(q, _root).replace(os.sep, "/")
                                if not r.startswith(("tests/", "..")):
                                    rel = r
                    except Exception:  # noqa: BLE001
                        rel = ""
                    _fseen[fn] = rel
                if rel and code.co_name != "<module>":
                    q = code.co_qualname.split(".<locals>", 1)[0]
                    if not q.startswith("<"):
                        _note(f"fn:{rel}::{q}")
                return _DIS

            try:
                _mon.register_callback(_tool, _mon.events.PY_START, _start)
                _mon.set_events(_tool, _mon.events.PY_START)
            except Exception:  # noqa: BLE001
                pass

    # исходник .py, прочитанный как ТЕКСТ (а не импортом), — «src:…»: такой проверке важен весь файл, а не функции
    def _src_hook(ev, args):
        if _busy[0] or ev != "open":
            return
        try:
            p = args[0] if args else None
            if not isinstance(p, str) or not p.endswith(".py"):
                return
            f = sys._getframe(1)
            for _ in range(8):
                if f is None:
                    break
                if str(f.f_globals.get("__name__", "")).startswith(("importlib", "_frozen_importlib", "pkgutil", "zipimport", "site",
                                                                       "linecache", "traceback", "inspect", "tokenize")):
                    return
                f = f.f_back
            q = os.path.normpath(p if os.path.isabs(p) else os.path.join(os.getcwd(), p))
            if q.startswith(_root):
                _note("src:" + os.path.relpath(q, _root).replace(os.sep, "/"))
        except Exception:  # noqa: BLE001
            pass

    sys.addaudithook(_src_hook)

    # Какие функции JS выполнились (20.11, владелец: «телефон — по функциям… да, давай сделаем»): телефон (app.js),
    # виджет (hud.html), студия — в браузере проверки (Chromium через Playwright: точное покрытие V8 по CDP) и в node
    # (NODE_V8_COVERAGE). «jsfn:android/assets/www/app.js::notesRender» — функция с именем выполнилась; «jscov:<файл>» —
    # покрытие этого файла снято целиком (без этой метки выбор по файлу — по-старому, все проверки, что его грузят).
    def _js_tail(parts):
        """Хвост пути -> единственный файл проекта (.js, .html) с самым длинным совпадающим хвостом или ""."""
        parts = [x for x in parts if x]
        if not parts:
            return ""
        idx = _js_tail.__dict__.setdefault("idx", {})
        if not idx:
            _busy[0] = True                                   # свой обход — не зависимость проверки
            try:
                for dp, dn, fn in os.walk(_root):
                    dn[:] = [d for d in dn if d not in (".git", "node_modules", "tests", "__pycache__", "build")]
                    for f in fn:
                        if f.endswith((".js", ".html")):
                            idx.setdefault(f, []).append(os.path.relpath(os.path.join(dp, f), _root).replace(os.sep, "/"))
            finally:
                _busy[0] = False
        cands = idx.get(parts[-1], [])
        for k in range(len(parts), 0, -1):
            tail = "/".join(parts[-k:])
            m = [c for c in cands if c == tail or c.endswith("/" + tail)]
            if len(m) == 1:
                return m[0]
        return ""

    def _js_rel(url):
        """file:///…/ui/hud.html или http://127.0.0.1:8123/assets/www/app.js -> путь в проекте или ""."""
        try:
            from urllib.parse import unquote, urlparse
            u = urlparse(url or "")
            if u.scheme == "file":
                q = os.path.normpath(unquote(u.path))
                if not q.startswith(_root) and os.path.realpath(q).startswith(_root):
                    q = os.path.realpath(q)
                if q.startswith(_root):
                    r = os.path.relpath(q, _root).replace(os.sep, "/")
                    return "" if r.startswith(("tests/", "..")) else r
                same = _js_rel.__dict__.setdefault("same", {})   # копия файла проекта (телефон собирается во временную
                if q not in same:                                # папку: www_assemble.sh) — тот же файл, байт в байт
                    same[q] = ""
                    tail = _js_tail(q.split(os.sep))
                    if tail:
                        try:
                            _busy[0] = True
                            with open(q, "rb") as a, open(os.path.join(_root, tail), "rb") as b:
                                if a.read() == b.read():
                                    same[q] = tail
                        except OSError:
                            pass
                        finally:
                            _busy[0] = False
                return same[q]
            if u.scheme in ("http", "https") and u.hostname in ("127.0.0.1", "localhost") and u.path.endswith((".js", ".html", "/")):
                parts = [x for x in unquote(u.path).split("/") if x] or ["index.html"]
                if u.path.endswith("/"):
                    parts.append("index.html")
                return _js_tail(parts)
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _js_note(result):
        """Ответ V8 (Profiler.takePreciseCoverage или файл NODE_V8_COVERAGE) -> записи jsfn:/jscov:."""
        for sc in result or ():
            rel = _js_rel(sc.get("url", ""))
            if not rel:
                continue
            _note("jscov:" + rel)
            for fn in sc.get("functions", ()):
                nm = fn.get("functionName") or ""
                rg = fn.get("ranges") or ()
                if nm and rg and rg[0].get("count", 0) > 0:
                    _note(f"jsfn:{rel}::{nm}")

    _pages = []

    def _cov_start(page):
        try:
            if page.context.browser and page.context.browser.browser_type.name != "chromium":
                return page
            s = page.context.new_cdp_session(page)
            s.send("Profiler.enable")
            s.send("Profiler.startPreciseCoverage", {"callCount": False, "detailed": False})
            _pages.append((page, s))
        except Exception:  # noqa: BLE001
            pass
        return page

    def _cov_take(page=None):
        for pg, s in list(_pages):
            if page is not None and pg is not page:
                continue
            try:
                _js_note(s.send("Profiler.takePreciseCoverage").get("result"))
            except Exception:  # noqa: BLE001 — страница уже закрыта: что успели снять раньше — то и есть
                pass
            if page is None:
                _pages.remove((pg, s))

    def _patch_playwright(g=None, cm=None):
        if g is not None and not getattr(g, "_dw_cov", False):
            g._dw_cov = True
            for cls in (g.Browser, g.BrowserContext):
                _orig = cls.new_page
                def _np(self, *a, _o=_orig, **k):
                    return _cov_start(_o(self, *a, **k))
                cls.new_page = _np
            for name in ("goto", "reload", "set_content", "close"):           # перед уходом со страницы — снять
                _orig = getattr(g.Page, name)
                def _pm(self, *a, _o=_orig, **k):
                    _cov_take(self)
                    return _o(self, *a, **k)
                setattr(g.Page, name, _pm)
            for cls in (g.Browser, g.BrowserContext):
                _orig = cls.close
                def _cl(self, *a, _o=_orig, **k):
                    _cov_take()
                    return _o(self, *a, **k)
                cls.close = _cl
        if cm is not None and not getattr(cm, "_dw_cov", False):
            cm._dw_cov = True
            _orig = cm.PlaywrightContextManager.__exit__
            def _ex(self, *a, _o=_orig):
                _cov_take()
                return _o(self, *a)
            cm.PlaywrightContextManager.__exit__ = _ex

    class _PwFinder:
        """После загрузки модулей Playwright — подменить создание и закрытие страниц (сама проверка не меняется)."""
        WANT = ("playwright.sync_api._generated", "playwright.sync_api._context_manager")

        def find_spec(self, name, path=None, target=None):
            if name not in self.WANT:
                return None
            import importlib.machinery
            spec = importlib.machinery.PathFinder.find_spec(name, path)
            if spec is None or spec.loader is None:
                return spec
            inner = spec.loader

            class _L:
                def __getattr__(self, k):                   # get_source и прочее — как у настоящего загрузчика
                    return getattr(inner, k)

                def create_module(self, s):
                    return inner.create_module(s)

                def exec_module(self, m):
                    inner.exec_module(m)
                    try:
                        _patch_playwright(m if name.endswith("_generated") else None, m if name.endswith("_context_manager") else None)
                    except Exception:  # noqa: BLE001
                        pass
            spec.loader = _L()
            return spec

    sys.meta_path.insert(0, _PwFinder())

    # node: каждый запуск node из этой проверки пишет покрытие в свою папку; разбирает её процесс, который её завёл
    if not os.environ.get("NODE_V8_COVERAGE"):
        import atexit
        import tempfile
        _ncov = tempfile.mkdtemp(prefix="dw-nodecov-")
        os.environ["NODE_V8_COVERAGE"] = _ncov
        _owner = os.getpid()

        def _node_cov():
            if os.getpid() != _owner:
                return
            import json
            import shutil
            try:
                for f in os.listdir(_ncov):
                    if f.endswith(".json"):
                        try:
                            with open(os.path.join(_ncov, f), encoding="utf-8") as fh:
                                _js_note(json.load(fh).get("result"))
                        except (OSError, ValueError):
                            pass
            finally:
                shutil.rmtree(_ncov, ignore_errors=True)
        atexit.register(_node_cov)

# прежний sitecustomize (у системы он может быть свой) — выполнить, как будто нас нет; другие копии записи — пропустить
_here = os.path.dirname(os.path.abspath(__file__))
for _d in ([] if _AGAIN else sys.path):
    try:
        _p = os.path.join(_d or os.getcwd(), "sitecustomize.py")
        if os.path.abspath(_d or os.getcwd()) != _here and os.path.isfile(_p):
            with open(_p, encoding="utf-8") as _fh:
                if "_dewiar_trace" in (_src := _fh.read()):
                    continue                        # такая же запись из другой папки — уже стоим мы
                exec(compile(_src, _p, "exec"), {"__file__": _p, "__name__": "sitecustomize", "__builtins__": __builtins__})
            break
    except Exception:  # noqa: BLE001
        break
