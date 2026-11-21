"""«Рентген» ответа (план «Качество», владелец 21.11): что увидела Лира, как решила и что сделала — по каждому ходу.

Владелец: «для меня сейчас в Лире всё работает вслепую, какая комбинация промптов уходит на обработку, почему так
непредсказуемо». Рентген записывает ход целиком, ничего не меняя в поведении:
  услышала  — текст вопроса (и откуда: голос, набор, мессенджер, дело по расписанию);
  поняла    — кто ответил: быстрая команда без модели (какая) или модель;
  собрала   — из чего подсказка модели (правила, действия, о человеке, разговор, справка к вопросу) и сколько весит;
  выбрала   — какая модель, окно, сколько действий предложено;
  сделала   — какие действия вызваны и чем кончились;
  проверила — какие проверки ответа сработали и что поправили («✋» в журнале);
  ответила  — итог, время до первого слова и всего.
Плюс строки журнала этого хода (поток вопроса и поток хода) — по ним видно всё остальное.

Хранится: последние 60 ходов — в STATE_DIR/xray.jsonl (без полного текста подсказки), полный текст подсказки — в памяти
для последних 8 ходов (раскрыть «что ушло в модель»). Наружу (отчёт разработчику) — только краткая сводка (`brief`).
Выключатель: llm.xray = false — не записывать."""
import json
import logging
import re
import threading
import time
from collections import deque
from pathlib import Path

log = logging.getLogger("dewiar.xray")

_tl = threading.local()
_lock = threading.RLock()
_mem = deque(maxlen=60)          # последние ходы (словари)
_full = {}                       # id -> {"system": …, "msgs": […], "tools": […]} — последние 8
_FULL_KEEP = 8
_path = None
_on = True
_n = [0]

STAGES = ("heard", "route", "prompt", "model", "acts", "checks", "answer")

# быстрые команды без модели: имя обработчика -> по-человечески
CMD_NAMES = {
    "_music_cmd": "Музыка и радио", "_mine_cmd": "Своя музыка", "_radio_url_cmd": "Радио по ссылке",
    "_weather_cmd": "Погода", "_clock_cmd": "Часы и дата", "_timer_cmd": "Таймер", "_money_cmd": "Деньги",
    "_job_cmd": "Работа", "_vault_cmd": "Сейф", "_home_cmd": "Умный дом", "_pc_cmd": "Компьютер",
    "_window_cmd": "Окна", "_speed_cmd": "Скорость речи", "_bug_cmd": "Сообщить об ошибке", "_draft_cmd": "Черновик книги",
    "_mail_table_cmd": "Таблица по почте", "_youtube_cmd": "YouTube", "_send_cmd": "Сообщение близкому",
    "_call_cmd": "Звонок близкому", "_plan_cmd": "План дня", "_task_del_cmd": "Удалить задачу", "_mark_cmd": "Отметка дела",
    "_direct_call": "Позвать персонажа", "_direct_update": "Обновление", "_direct_look": "Образ персонажа",
}
_CMD_RX = re.compile(r"^_(?:\w+_cmd|direct_\w+)$")

# строки журнала -> этап (по значку в начале — так пишет ядро)
_TAG = [("checks", "✋"), ("model", "🧠"), ("prompt", "📖🧩📚🗂"), ("acts", "🛠🔧⚙📻🎵💽🔔⏰📅📝🌐🔎"),
        ("answer", "⏱💬"), ("heard", "❓🎤👂")]


def enabled():
    return _on


def setup(state_dir, on=True):
    """Один раз при старте ядра: куда писать и перехват журнала."""
    global _path, _on
    _on = bool(on)
    from pathlib import Path
    _path = Path(state_dir) / "xray.jsonl"
    try:
        if _path.exists():
            for line in _path.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]:
                try:
                    _mem.append(json.loads(line))
                except ValueError:
                    pass
            if _mem:
                _n[0] = max(int(str(x.get("id", "0")).split("-")[0] or 0) for x in _mem)
    except Exception:  # noqa: BLE001
        log.debug("рентген: чтение", exc_info=True)
    root = logging.getLogger()
    if not any(isinstance(h, _Cap) for h in root.handlers):
        root.addHandler(_Cap())


class _Cap(logging.Handler):
    """Строки журнала — в рентген того хода, что идёт в этом потоке."""

    def __init__(self):
        super().__init__(level=logging.INFO)

    def emit(self, record):
        xr = getattr(_tl, "xr", None)
        if xr is None or xr.get("_end") or record.name == "dewiar.xray":
            return
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            return
        lines = xr["log"]
        if len(lines) < 300:
            lines.append({"t": round(time.monotonic() - xr["_t0"], 2), "lv": record.levelname[0], "m": msg[:600],
                          "st": stage_of(msg)})


def stage_of(msg):
    s = (msg or "").lstrip()[:2]
    for st, marks in _TAG:
        if s and any(s.startswith(m) for m in marks):
            return st
    return ""


def current():
    return getattr(_tl, "xr", None)


def attach(xr):
    """Поток хода (turn-N) пишет в тот же рентген, что и поток вопроса."""
    _tl.xr = xr
    _tl.depth = 0


def begin(text, via=None, quiet=False, raw=False, typed=False):
    """Новый вопрос — новый рентген (в этом потоке)."""
    if not _on:
        _tl.xr = None
        return None
    with _lock:
        _n[0] += 1
        n = _n[0]
    src = "дело по расписанию" if raw else "служебный" if quiet else \
        ("мессенджер" if via and not (via or {}).get("job") else "по расписанию" if via else "набрано" if typed else "голос")
    xr = {"id": f"{n}-{int(time.time())}", "ts": time.time(), "_t0": time.monotonic(), "q": str(text)[:2000], "src": src,
          "route": None, "path": [], "prompt": None, "model": None, "acts": [], "checks": [], "answer": None, "log": []}
    _tl.xr, _tl.depth = xr, 0
    return xr


def note_route(name):
    xr = current()
    if xr is not None and not xr["route"]:
        xr["route"] = {"kind": "cmd", "name": name, "label": CMD_NAMES.get(name, name.strip("_").replace("_", " "))}


def turned(xr):
    """Вопрос ушёл модели (ход turn-N)."""
    if xr is not None and not xr["route"]:
        xr["route"] = {"kind": "model", "label": "Модель"}


def prompt(system, specs, msgs, parts=None, prof=None, ctx_window=None, extra=None):
    """Что уходит в модель: веса частей, имена действий, модель и окно; полный текст — в память (последние 8)."""
    xr = current()
    if xr is None:
        return
    try:
        names = [str((s.get("function") or s).get("name") or "") for s in (specs or [])]
        p = prof or {}
        xr["prompt"] = {"parts": dict(parts or {}), "chars": len(system or "") + sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs or []),
                        "turns": sum(1 for m in msgs or [] if m.get("role") in ("user", "assistant")), "tools": names[:80],
                        **(extra or {})}
        xr["model"] = {"name": str(p.get("name") or ""), "model": str(p.get("model") or ""), "kind": _kind(p),
                       "window": ctx_window or p.get("ctx") or p.get("num_ctx") or None}
        with _lock:
            _full[xr["id"]] = {"system": str(system or "")[:120000], "msgs": _plain_msgs(msgs), "tools": names}
            for k in list(_full)[:-_FULL_KEEP]:
                _full.pop(k, None)
    except Exception:  # noqa: BLE001
        log.debug("рентген: подсказка", exc_info=True)


def _kind(p):
    try:
        from health import brain_kind
        return brain_kind(p)
    except Exception:  # noqa: BLE001
        return ""


def _plain_msgs(msgs):
    out = []
    for m in msgs or []:
        c = m.get("content")
        if not isinstance(c, str):
            c = " ".join(x.get("text", "") if x.get("type") == "text" else "[картинка]" for x in c or [] if isinstance(x, dict))
        if m.get("tool_calls"):
            c = (c or "") + "\n[вызов: " + ", ".join(str((t.get("function") or {}).get("name")) for t in m["tool_calls"]) + "]"
        out.append({"role": m.get("role"), "text": str(c or "")[:20000]})
    return out[-60:]


def event(type_, kw):
    """Из Engine.emit: действия (tool) и итог (answer done) — в рентген; к итогу — номер рентгена в meta."""
    xr = current()
    if xr is None:
        return
    try:
        if type_ == "tool" and kw.get("args") and kw.get("status") not in ("done", "error", "declined"):
            xr.setdefault("_args", {})[str(kw.get("name") or "")] = kw.get("args")      # с чем вызвано — из начала
        if type_ == "tool" and kw.get("status") in ("done", "error", "declined"):
            if len(xr["acts"]) < 40:
                xr["acts"].append({"name": str(kw.get("name") or ""), "title": str(kw.get("title") or kw.get("name") or "")[:160],
                                   "ok": kw.get("status") == "done",
                                   "args": _short(kw.get("args") or (xr.get("_args") or {}).get(str(kw.get("name") or ""))),
                                   "result": _short(kw.get("result") or kw.get("detail") or kw.get("error")
                                                    or ("человек не разрешил" if kw.get("status") == "declined" else "")),
                                   "t": round(time.monotonic() - xr["_t0"], 2)})
        elif type_ == "answer" and kw.get("done") and kw.get("text"):
            meta = kw.get("meta") or {}
            xr["answer"] = {"text": str(kw["text"])[:4000], "t": round(time.monotonic() - xr["_t0"], 2),
                            "first": meta.get("first"), "tokens": {k: meta[k] for k in ("in", "out", "cached") if k in meta} or None}
            kw["meta"] = dict(meta, xray=xr["id"])
    except Exception:  # noqa: BLE001
        log.debug("рентген: событие", exc_info=True)


def _short(v, n=400):
    if v is None or v == "":
        return ""
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s[:n] + ("…" if len(s) > n else "")


_on_finish = []


def on_finish(cb):
    """Подписка на итог хода (рентген целиком): замер качества по «где думает» (health.qual_note) и др."""
    if cb not in _on_finish:
        _on_finish.append(cb)


def finish(xr=None):
    """Ход окончен: проверки — из журнала («✋»), запись на диск, поток отвязан."""
    xr = xr or current()
    if xr is None or xr.get("_end"):
        return
    xr["_end"] = True
    xr["t"] = round(time.monotonic() - xr["_t0"], 2)
    xr["checks"] = [ln["m"] for ln in xr["log"] if ln["st"] == "checks"][:20]
    if not xr["route"]:                        # ответил путь без модели, не названный обработчиком (дела, заметки…)
        xr["route"] = {"kind": "cmd", "label": "Быстрый ответ без модели"} if xr["answer"] or xr["acts"] \
            else {"kind": "none", "label": "Без ответа"}
    rec = {k: v for k, v in xr.items() if not k.startswith("_")}
    with _lock:
        _mem.append(rec)
        _save(rec)
    for cb in list(_on_finish):
        try:
            cb(rec)
        except Exception:  # noqa: BLE001
            log.debug("рентген: подписчик", exc_info=True)
    if getattr(_tl, "xr", None) is xr:
        _tl.xr = None


def _save(rec):
    if _path is None:
        return
    try:
        with open(_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if _path.stat().st_size > 3_000_000:
            _path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in list(_mem)[-60:]), encoding="utf-8")
    except Exception:  # noqa: BLE001
        log.debug("рентген: запись", exc_info=True)


def get(xid, full=False):
    """Рентген хода по номеру; full — и полный текст подсказки (если он ещё в памяти)."""
    with _lock:
        rec = next((dict(r) for r in reversed(_mem) if r.get("id") == xid), None)
        if rec is not None and full:
            rec["full"] = _full.get(xid)
    return rec


def recent(n=20):
    with _lock:
        return [{"id": r["id"], "ts": r["ts"], "q": r["q"][:120], "route": (r.get("route") or {}).get("label"),
                 "t": r.get("t"), "checks": len(r.get("checks") or [])} for r in list(_mem)[-n:]][::-1]


def brief(n=5):
    """Для отчёта разработчику: последние ходы кратко — путь, модель, веса подсказки, действия, проверки."""
    out = []
    try:
        from engine_base import redact          # пароли, карты, ключи в вопросе — звёздочками (как в журнале)
    except Exception:  # noqa: BLE001
        redact = (lambda t: t)                   # noqa: E731
    with _lock:
        items = list(_mem)[-n:]
    for r in items:
        rt, m, p = r.get("route") or {}, r.get("model") or {}, r.get("prompt") or {}
        acts = ", ".join(f"{a['name']}{'' if a['ok'] else ' ✗'}" for a in r.get("acts") or []) or "—"
        parts = ", ".join(f"{k} {v}" for k, v in (p.get("parts") or {}).items())
        out.append(f"- «{redact(r['q'])[:80]}» → {rt.get('label', '?')}" + (f" · {m.get('model') or m.get('name')} ({m.get('kind')})" if m else "")
                   + (f" · подсказка ≈{sum((p.get('parts') or {}).values())} ток. ({parts}), действий {len(p.get('tools') or [])}" if p else "")
                   + f" · вызвано: {acts}" + (f" · проверки: {len(r.get('checks') or [])}" if r.get("checks") else "")
                   + (f" · {r.get('t')} с" if r.get("t") is not None else ""))
    return "\n".join(out)


def instrument(engine):
    """Быстрые команды без модели (_…_cmd, _direct_…): первая сработавшая — путь хода в рентгене. Поведение не меняется."""
    for name in dir(type(engine)):
        if not _CMD_RX.match(name):
            continue
        fn = getattr(engine, name, None)
        if not callable(fn) or getattr(fn, "_xray", False):
            continue
        try:                                   # только обработчики фразы (text, …), а не команд студии (cmd, a)
            import inspect
            ps = list(inspect.signature(fn).parameters)
        except (TypeError, ValueError):
            continue
        if not ps or ps[0] not in ("text", "t", "q", "phrase"):
            continue
        setattr(engine, name, _wrap(name, fn))


def _wrap(name, fn):
    def w(*a, **k):
        d = getattr(_tl, "depth", 0)
        _tl.depth = d + 1
        try:
            r = fn(*a, **k)
        finally:
            _tl.depth = d
        if r and d == 0:
            note_route(name)
        elif r:
            xr = current()
            if xr is not None and name not in xr["path"]:
                xr["path"].append(name)
        return r
    w._xray = True
    w.__name__ = name
    w.__wrapped__ = fn
    return w


def export(xid, folder, meta=None):
    """Рентген хода — файлом для разработчика (владелец 21.11: «не хватает выгрузки, чтобы показывать результаты не скриншотом,
    а полным файлом со всеми техническими подробностями»). Пишет в folder два файла: .json (всё: путь, подсказка целиком, если
    она ещё в памяти, действия с аргументами и итогом, проверки, журнал хода, кто ответил) и .md (то же для чтения глазами).
    Пароли, ключи и карты — звёздочками (как в журнале). meta — версия, система, настройки ядра без ключей. -> путь к .json"""
    rec = get(xid, full=True)
    if rec is None:
        raise ValueError("рентген этого ответа уже не хранится — он помнит последние 60 ответов")
    try:
        from engine_base import redact
    except Exception:  # noqa: BLE001
        redact = (lambda t: t)                   # noqa: E731

    def clean(v):
        if isinstance(v, str):
            return redact(v)
        if isinstance(v, list):
            return [clean(x) for x in v]
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items() if not str(k).startswith("_")}
        return v
    rec = clean(rec)
    body = {"dewiar_xray": 1, "meta": clean(meta or {}), "turn": rec}
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(rec.get("ts") or time.time()))
    base = folder / f"xray-{stamp}-{re.sub(r'[^0-9a-z-]', '', str(xid))}"
    js = base.with_suffix(".json")
    js.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    m, p = rec.get("model") or {}, rec.get("prompt") or {}
    md = [f"# Рентген ответа · {time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(rec.get('ts') or time.time()))}", "",
          f"Вопрос ({rec.get('src') or ''}): {rec.get('q') or ''}", "",
          "## Кратко", "",
          f"- путь: {(rec.get('route') or {}).get('label') or (rec.get('route') or {}).get('kind') or '?'}"
          + (f"; по пути: {', '.join(rec.get('path') or [])}" if rec.get("path") else ""),
          f"- модель: {m.get('model') or '—'} ({m.get('name') or ''}, {m.get('kind') or ''}); ответил: {m.get('served') or '—'}; окно: {m.get('window') or 'неизвестно'}",
          f"- подсказка: {sum((p.get('parts') or {}).values()) if p else 0} ток. — " + ", ".join(f"{k} {v}" for k, v in (p.get("parts") or {}).items())
          + (f"; действий на выбор {len(p.get('tools') or [])}; реплик {p.get('turns')}" if p else "") + ("; «чистый разговор»" if p.get("lean") else ""),
          f"- действия: " + ("; ".join(f"{a.get('name')} — {'ок' if a.get('ok') else 'НЕ ВЫШЛО'}" for a in rec.get("acts") or []) or "нет"),
          f"- проверки: " + ("; ".join(rec.get("checks") or []) or "ничего не нашли"),
          f"- время: весь ход {rec.get('t')} с; первое слово {((rec.get('answer') or {}).get('first'))} с", "",
          "## Ответ", "", str((rec.get("answer") or {}).get("text") or "—"), "",
          "## Настройки и среда", "", "```json", json.dumps(body["meta"], ensure_ascii=False, indent=1), "```", "",
          "## Журнал хода", "", "```"] + [f"{x.get('t'):>6} {x.get('lv')} {x.get('m')}" for x in rec.get("log") or []] + ["```", ""]
    for a in rec.get("acts") or []:
        md += [f"### Действие {a.get('name')} — {'ок' if a.get('ok') else 'не вышло'}", "", f"аргументы: {a.get('args')}", "", f"итог: {a.get('result')}", ""]
    full = rec.get("full") or {}
    if full:
        md += ["## Что ушло в модель — целиком", "", "### Инструкция", "", "```", str(full.get("system") or ""), "```", ""]
        for mm in full.get("msgs") or []:
            md += [f"### {mm.get('role')}", "", "```", str(mm.get("text") or ""), "```", ""]
        md += [f"### Действия на выбор ({len(full.get('tools') or [])})", "", ", ".join(full.get("tools") or []), ""]
    base.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    return str(js)
