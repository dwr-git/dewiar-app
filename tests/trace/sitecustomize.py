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

if _FILE and _ROOT:
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

# прежний sitecustomize (у системы он может быть свой) — выполнить, как будто нас нет
_here = os.path.dirname(os.path.abspath(__file__))
for _d in sys.path:
    try:
        _p = os.path.join(_d or os.getcwd(), "sitecustomize.py")
        if os.path.abspath(_d or os.getcwd()) != _here and os.path.isfile(_p):
            with open(_p, encoding="utf-8") as _fh:
                exec(compile(_fh.read(), _p, "exec"), {"__file__": _p, "__name__": "sitecustomize", "__builtins__": __builtins__})
            break
    except Exception:  # noqa: BLE001
        break
