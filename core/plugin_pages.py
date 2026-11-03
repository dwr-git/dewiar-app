"""Страница плагина в студии (владелец 03.11: «плагин включён — появляются команды, а должен быть целый раздел под плагин,
где его можно настраивать и взаимодействовать… Лира что-то начинает делать — и на этом всё, не работает НИЧЕГО»).

Студия → группа «Плагины» в меню → страница плагина (ui/studio/plugpage.js). Здесь — то, что ей нужно от ядра:
  page()      — шапка (значок, название, состояние серверов и причина, если не запустились), действия плагина из MCP
                tools/list с человеческими названиями из блока ui в plugin.json, последние файлы;
  run()       — действие плагина НАПРЯМУЮ, без модели (кнопка «Выполнить» и мост своей страницы ui.html): только среди
                серверов этого плагина (MCPManager.plugin_call) — чужое действие не вызвать; ответ разобран для показа:
                JSON — данными, текст — Markdown, картинки — data:, пути к файлам — кнопками «Открыть»;
  files()     — последние файлы плагина: его папка данных (DEWIAR_PLUGIN_DATA), его папка в папке Dewiar (ui.folder,
                «Рисунки») и папки из его настроек (тип folder: «Папка с резюме»);
  open_path() — открыть файл только внутри этих папок или папки Dewiar;
  ui_html()   — текст своей страницы плагина (ui.html) для фрейма-песочницы.
Ключи облака и чужие настройки сюда не попадают: страница получает только значения настроек своего плагина."""

import base64
import json
import mimetypes
import os
import re
import time
from pathlib import Path

from plugins import data_dir

MAX_TEXT = 400_000
MAX_IMG = 6_000_000
HIDE_EXT = {".part", ".tmp", ".pyc", ".lock"}


class PageError(Exception):
    pass


def human_name(name):
    """art_draw → «Draw», recruit_add → «Add»: если плагин не дал названия — хотя бы без приставки и подчёркиваний."""
    n = re.sub(r"^[a-z]+_", "", str(name or "")) if "_" in str(name or "") else str(name or "")
    n = n.replace("_", " ").replace("-", " ").strip()
    return n[:1].upper() + n[1:]


def human_error(msg):
    """Ошибка сервера или вызова -> понятными словами."""
    t = str(msg or "").strip()
    t = re.sub(r"^(Ошибка|Error)\s*:\s*", "", t)
    low = t.lower()
    if "не ответил вовремя" in low or "timed out" in low or "timeout" in low:
        return "Плагин думал слишком долго и не ответил. Попробуйте ещё раз; если повторится — «Перезапустить» вверху страницы."
    if "сервер mcp завершился" in low or "не отвечает" in low or "broken pipe" in low:
        return "Программа плагина остановилась. Нажмите «Перезапустить» вверху страницы и попробуйте снова."
    if "не найдена программа" in low:
        return "Не хватает программы, которая нужна плагину: " + t
    if "traceback" in low or len(t) > 600:
        line = [x for x in t.splitlines() if x.strip()][-1:] or [t[:200]]
        return "В программе плагина ошибка: " + line[0][:300]
    return (t[:1].upper() + t[1:]) if t else "Плагин не смог это сделать, но не объяснил почему."


def _plugin(P, pid):
    p = P.items.get(str(pid or ""))
    if not p:
        raise PageError("нет такого плагина")
    return p


def roots(P, pid, ws_root):
    """Папки, файлы из которых плагину можно показывать и открывать: [(Path, подпись)]."""
    p = _plugin(P, pid)
    out = [(data_dir(pid), "Данные плагина")]
    ws = Path(ws_root) if ws_root else None
    if ws:
        if p["ui"]["folder"]:
            out.append((ws / p["ui"]["folder"], p["ui"]["folder"]))
        out.append((ws, "Папка Dewiar"))
    vals = P.values(pid)
    for s in p["settings"]:
        v = str(vals.get(s["key"]) or "").strip()
        if s["type"] == "folder" and v:
            out.append((Path(os.path.expandvars(os.path.expanduser(v))), s["label"]))
    return out


def safe_path(P, pid, ws_root, path):
    """Путь внутри папок плагина или папки Dewiar -> Path; иначе PageError. resolve() раскрывает «..» и ссылки до
    проверки. Относительный путь — от папки Dewiar (как у ws_open), затем от папки данных плагина."""
    raw = str(path or "").strip()
    if not raw or "\x00" in raw:
        raise PageError("не указан файл")
    allowed = [r.resolve() for r, _ in roots(P, pid, ws_root) if r]
    cand = Path(os.path.expanduser(raw))
    tries = [cand] if cand.is_absolute() else [Path(ws_root) / raw if ws_root else None, data_dir(pid) / raw]
    for c in tries:
        if c is None:
            continue
        rp = c.resolve()
        if any(rp == a or a in rp.parents for a in allowed):
            if rp.exists():
                return rp
    raise PageError("этот файл вне папок плагина — открыть его отсюда нельзя")


def _kind(f: Path):
    ext = f.suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
        return "image"
    if ext in (".html", ".htm"):
        return "page"
    if ext in (".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md"):
        return "doc"
    if ext in (".mp4", ".webm", ".mp3", ".wav", ".ogg"):
        return "media"
    if ext in (".xlsx", ".xls", ".csv", ".ods"):
        return "table"
    return "file"


def files(P, pid, ws_root, limit=12):
    """Последние файлы плагина (новые сверху): [{path, name, folder, at, size, kind}] и папки, откуда они."""
    _plugin(P, pid)
    seen, items, folders = set(), [], []
    for root, label in roots(P, pid, ws_root):
        if label == "Папка Dewiar" or not root.is_dir():
            continue                                  # вся папка Dewiar — не «файлы плагина»: только его подпапка
        folders.append({"path": str(root), "label": label})
        n = 0
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if not d.startswith(".")]
            for fn in fns:
                n += 1
                if n > 3000:
                    break
                f = Path(dp) / fn
                if fn.startswith((".", "~$")) or f.suffix.lower() in HIDE_EXT:
                    continue
                if label == "Данные плагина" and f.suffix.lower() == ".json":
                    continue                          # внутренний учёт плагина (recruiter.json) — не для людей
                try:
                    st = f.stat()
                except OSError:
                    continue
                k = str(f.resolve())
                if k in seen:
                    continue
                seen.add(k)
                items.append({"path": str(f), "name": f.name, "folder": label, "at": int(st.st_mtime), "size": st.st_size,
                              "kind": _kind(f)})
            if n > 3000:
                break
    items.sort(key=lambda x: -x["at"])
    return {"items": items[:max(1, min(60, int(limit or 12)))], "folders": folders}


def _tool_view(t, ui):
    u = (ui.get("tools") or {}).get(t.get("name")) or {}
    ann = t.get("annotations") or {}
    return {"name": t.get("name"), "title": u.get("title") or ann.get("title") or human_name(t.get("name")),
            "hint": u.get("hint") or "", "description": str(t.get("description") or "")[:600], "button": u.get("button") or "",
            "hidden": bool(u.get("hidden")), "page_only": bool((t.get("_meta") or {}).get("dewiar/page")),
            "schema": t.get("inputSchema") or {"type": "object", "properties": {}}, "fields": u.get("fields") or {},
            "readonly": bool(ann.get("readOnlyHint"))}


def page(P, mcp, pid, ws_root):
    """Всё для страницы плагина одним ответом."""
    p = _plugin(P, pid)
    entry = next((x for x in P.catalog() if x["id"] == p["id"]), None) or {}
    entry.pop("readme", None)
    info = mcp.plugin_info(p["id"]) if p["mcp"] and mcp is not None else {"state": "none", "error": "", "tools": []}
    if p["mcp"] and info["state"] == "off":
        info = dict(info, state="error", error="подключение плагина выключено в списке «MCP-серверы»" if entry.get("installed")
                    else "плагин не установлен")
    tools = [_tool_view(t, p["ui"]) for t in info["tools"]]
    try:
        fl = files(P, p["id"], ws_root)
    except Exception:  # noqa: BLE001
        fl = {"items": [], "folders": []}
    return {"plugin": entry, "state": info["state"], "error": human_error(info["error"]) if info["error"] else "",
            "tools": tools, "files": fl, "data_dir": str(data_dir(p["id"]))}


def _walk_paths(v, out, depth=0):
    if depth > 6 or len(out) > 40:
        return
    if isinstance(v, str):
        if 2 < len(v) < 600 and (v.startswith(("/", "~/")) or re.match(r"^[A-Za-z]:[\\/]", v)) and "\n" not in v:
            out.append(v)
    elif isinstance(v, dict):
        for x in v.values():
            _walk_paths(x, out, depth + 1)
    elif isinstance(v, list):
        for x in v[:200]:
            _walk_paths(x, out, depth + 1)


def shape(r):
    """Ответ сервера MCP -> {is_error, error, parts: [{type: data|text|image, …}]} для показа в студии."""
    parts, err = [], bool(r.get("isError"))
    for c in r.get("content") or []:
        typ = c.get("type")
        if typ == "text":
            t = str(c.get("text") or "")[:MAX_TEXT]
            try:
                d = json.loads(t) if t.strip()[:1] in "{[" else None
            except ValueError:
                d = None
            parts.append({"type": "data", "data": d} if d is not None else {"type": "text", "text": t})
        elif typ == "image" and c.get("data") and len(c["data"]) < MAX_IMG:
            mime = c.get("mimeType") if re.fullmatch(r"image/[\w.+-]+", str(c.get("mimeType") or "")) else "image/png"
            parts.append({"type": "image", "src": f"data:{mime};base64,{c['data']}"})
        elif typ == "resource":
            res = c.get("resource") or {}
            if res.get("text"):
                parts.append({"type": "text", "text": str(res["text"])[:MAX_TEXT]})
        elif typ == "resource_link" and c.get("uri"):
            parts.append({"type": "text", "text": str(c.get("name") or c["uri"])[:300]})
    if not parts and r.get("structuredContent") is not None:
        parts.append({"type": "data", "data": r["structuredContent"]})
    msg = ""
    for x in parts:
        if x["type"] == "data" and isinstance(x["data"], dict) and x["data"].get("error"):
            err, msg = True, str(x["data"]["error"])
    if err and not msg:
        msg = " ".join(x.get("text", "") for x in parts if x["type"] == "text") or "плагин сообщил об ошибке"
    return {"is_error": err, "error": human_error(msg) if err else "", "parts": parts}


def run(P, mcp, pid, tool, args, ws_root):
    """Действие плагина без модели -> {ok, is_error, error, parts, files: [{path, name, kind, preview?}], ms}."""
    p = _plugin(P, pid)
    if not p["mcp"]:
        raise PageError("у этого плагина нет своих действий — он работает через разговор с Лирой")
    if not re.fullmatch(r"[\w.-]{1,64}", str(tool or "")):
        raise PageError("нет такого действия")
    if not isinstance(args, dict):
        args = {}
    t0 = time.time()
    from mcp import MCPError
    try:
        r = mcp.plugin_call(p["id"], str(tool), args)
    except MCPError as e:
        return {"ok": False, "is_error": True, "error": human_error(str(e)), "parts": [], "files": [], "ms": int((time.time() - t0) * 1000)}
    out = shape(r)
    paths = []
    for x in out["parts"]:
        _walk_paths(x.get("data"), paths)
    fl, seen = [], set()
    for raw in paths:
        try:
            f = safe_path(P, p["id"], ws_root, raw)
        except PageError:
            continue
        if str(f) in seen:
            continue
        seen.add(str(f))
        item = {"path": str(f), "name": f.name or str(f), "kind": "folder" if f.is_dir() else _kind(f)}
        if item["kind"] == "image" and len([x for x in fl if x.get("preview")]) < 4:
            try:
                if f.stat().st_size < 3_000_000:
                    mime = "image/svg+xml" if f.suffix.lower() == ".svg" else (mimetypes.guess_type(f.name)[0] or "image/png")
                    item["preview"] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
            except OSError:
                pass
        fl.append(item)
    return dict(out, ok=not out["is_error"], files=fl[:12], ms=int((time.time() - t0) * 1000))


def ui_html(P, pid):
    """Своя страница плагина (ui.html) -> текст; нет — ""."""
    p = _plugin(P, pid)
    f = p["dir"] / "ui.html"
    try:
        if f.is_file() and f.stat().st_size < 1_500_000:
            return f.read_text(encoding="utf-8")
    except OSError:
        pass
    return ""
