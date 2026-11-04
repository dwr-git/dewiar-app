"""Свои плагины на всех компьютерах (0.83; пользователь 04.11: «свои исправления плагинов или новые свои — синхронизируются
между компами?»). Вид синхронизации «plugin» — только между компьютерами (телефон его не просит, узел «Дома по Wi-Fi» не
знает), см. core/sync.py: _snap_plugins, _apply_plugin.

Что переносится: плагины, сделанные Лирой («Сделай плагин», правки словами, плагины из готовых шаблонов — у них в
plugin.json есть made, core/plugin_maker.py), — plugin.json, ui.html, skill.md, своя программа server.py, если есть, и
версии (.versions/, последние 10). Не переносятся: данные страницы (dewiar.store — в папке данных плагина), разрешения
(settings.plugins.grants), установлен ли плагин, его настройки и дела по расписанию — это у каждого компьютера своё.
Плагины из zip и встроенные — нет: в zip может лежать что угодно, а встроенные и так одинаковые.

Плагин — одна «сборка»: JSON всех файлов, сжатый zlib, отпечаток sha1. Облако берёт запись до 300 КБ — сборка идёт
кусками: plugin:<id> — заголовок {name, sha, n, code, from}, plugin:<id>.<i> — кусок {sha, i, n, b64}. Предел — MAX
(512 КБ несжатого): не влезает — сначала без старых версий, совсем не влезает — не синхронизируется (и не удаляется у других).

Своя программа (server.py — MCP-сервер плагина) на другом компьютере сама не запускается: плагин с новой или изменённой
программой ставится выключенным с пометкой settings.plugins.arrived[id] = {from, code} — в студии «пришёл с „Рабочего“ —
включить?»; включает человек («Включить» — это и есть разрешение). Без программы — ставится включённым.
Удалили плагин на одном компьютере («Удалить файлы плагина») — удаляется и на других."""

import base64
import hashlib
import json
import logging
import re
import shutil
import time
import zlib
from pathlib import Path

log = logging.getLogger("dewiar.plugsync")
MAX = 512 * 1024                      # несжатая сборка плагина
CHUNK = 140_000                       # байт сжатой сборки в куске (запечатанный — меньше 290 КБ, предел облака 300 КБ)
FILES = (("plugin.json", "plugin.json"), ("ui.html", "ui.html"), ("server.py", "server.py"), ("skill.md", "skills/{id}/SKILL.md"))
KEEP = 10
ID_RX = re.compile(r"[a-z0-9-]{1,40}")


def user_dir(P):
    from plugins import USER_DIR
    return Path(getattr(P, "user_dir", None) or USER_DIR)


def _made(d: Path):
    """plugin.json папки -> словарь, если это плагин Лиры (made), иначе None."""
    try:
        m = json.loads((d / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return m if isinstance(m, dict) and isinstance(m.get("made"), dict) else None


def made_dirs(P):
    """[(id, папка)] своих плагинов Лиры. Встроенный с тем же id — не наш (свой его и не перекрывает)."""
    root, out = user_dir(P), []
    if not root.is_dir():
        return out
    items = getattr(P, "items", {}) or {}
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not ID_RX.fullmatch(d.name) or (items.get(d.name) or {}).get("builtin"):
            continue
        if (d / "plugin.json").is_file():
            out.append((d.name, d))
    return out


def present(P, pid):
    return bool(ID_RX.fullmatch(pid or "")) and (user_dir(P) / pid / "plugin.json").is_file()


def signature(d: Path, pid):
    """Время и размер файлов сборки — пересобирать, только если что-то поменялось."""
    parts = []
    for _, rel in FILES:
        p = d / rel.format(id=pid)
        try:
            st = p.stat()
            parts.append(f"{rel}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            pass
    vd = d / ".versions"
    if vd.is_dir():
        for p in sorted(vd.rglob("*")):
            try:
                if p.is_file():
                    st = p.stat()
                    parts.append(f"{p.relative_to(vd).as_posix()}:{st.st_mtime_ns}:{st.st_size}")
            except OSError:
                pass
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _read(p: Path):
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def bundle(d: Path, pid):
    """Папка плагина -> (сжатая сборка, {name, code}) или (None, причина)."""
    man = _made(d)
    if man is None:
        return None, "не плагин Лиры"
    if man.get("id") not in (None, pid):               # папка одного плагина, а в plugin.json — другой: такой не шлём
        return None, "id в plugin.json не совпадает с папкой"
    files = {}
    for name, rel in FILES:
        t = _read(d / rel.format(id=pid))
        if t is not None:
            files[name] = t
    if not files.get("ui.html"):
        return None, "нет ui.html"
    vers = []
    try:
        idx = json.loads((d / ".versions" / "index.json").read_text(encoding="utf-8"))
        idx = [x for x in idx if isinstance(x, dict) and isinstance(x.get("v"), int)][-KEEP:] if isinstance(idx, list) else []
    except (OSError, ValueError):
        idx = []
    for e in idx:
        vd = d / ".versions" / str(e["v"])
        vf = {name: t for name, _ in FILES if (t := _read(vd / name)) is not None}
        vers.append({"e": e, "files": vf})
    while True:
        raw = json.dumps({"id": pid, "files": files, "versions": vers}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(raw) <= MAX:
            break
        if not vers:
            return None, f"больше {MAX // 1024} КБ"
        vers.pop(0)                                    # сначала — без самых старых версий
    code = bool(files.get("server.py")) or bool(man.get("mcp"))
    return zlib.compress(raw, 9), {"name": str(man.get("name") or pid)[:60], "code": code}


def parts(blob):
    return [blob[i:i + CHUNK] for i in range(0, len(blob), CHUNK)] or [b""]


def part_data(blob, sha, i):
    ps = parts(blob)
    if not 0 <= i < len(ps):
        return None
    return {"sha": sha, "i": i, "n": len(ps), "b64": base64.b64encode(ps[i]).decode("ascii")}


def unpack(blob):
    """Сжатая сборка -> словарь или None (испорчена, больше предела)."""
    try:
        d = zlib.decompressobj()
        raw = d.decompress(blob, MAX + 1)
        if len(raw) > MAX or d.unconsumed_tail:
            return None
        b = json.loads(raw.decode("utf-8"))
    except (zlib.error, ValueError, UnicodeDecodeError):
        return None
    return b if isinstance(b, dict) and isinstance(b.get("files"), dict) else None


def _write(p: Path, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


def _arrived(s, pid, val):
    allp = dict(s.get("plugins", "arrived") or {})
    if val is None and pid not in allp:
        return
    if val is None:
        allp.pop(pid, None)
    else:
        allp[pid] = val
    s.update({"plugins": {"arrived": None}})
    s.update({"plugins": {"arrived": allp}})


def _vkey(files):
    """Содержимое версии для сравнения — без server.py: программу версии с другого компьютера сюда не берём (см. install)."""
    return hashlib.sha1(json.dumps({k: v.strip() for k, v in sorted(files.items()) if k != "server.py" and v and v.strip()}, ensure_ascii=False).encode("utf-8")).hexdigest()


def _local(d: Path, pid):
    """(текущие файлы, версии [{e, files}]) плагина здесь."""
    cur = {name: t for name, rel in FILES if (t := _read(d / rel.format(id=pid))) is not None}
    try:
        idx = json.loads((d / ".versions" / "index.json").read_text(encoding="utf-8"))
        idx = [x for x in idx if isinstance(x, dict) and isinstance(x.get("v"), int)] if isinstance(idx, list) else []
    except (OSError, ValueError):
        idx = []
    vers = [{"e": e, "files": {name: t for name, _ in FILES if (t := _read(d / ".versions" / str(e["v"]) / name)) is not None}} for e in idx]
    return cur, vers


def _merge(inc, loc, cur_here, cur_new):
    """Версии: пришедшие + здешние, которых там нет (плагин с тем же id делали и здесь, или правили одновременно — рецензия
    04.11: чужая сборка стирала здешние версии), + здешние текущие файлы, если их нет ни в одной версии, — отдельной версией
    «С этого компьютера до синхронизации». Здешние идут раньше пришедших (последняя — текущая, от неё считает «верни как
    было»); номера — подряд, «to» (запись-откат) — по новым номерам. Совпавшую версию берём здешней копией (с её программой)."""
    by_key = {}
    for x in loc:
        by_key.setdefault(_vkey(x["files"]), x)
    inc_keys = set()
    merged_inc = []
    for x in inc:
        k = _vkey(x["files"])
        inc_keys.add(k)
        merged_inc.append({"e": x["e"], "files": (by_key.get(k) or x)["files"], "old": x["e"]["v"]})
    extra, seen = [], set(inc_keys)
    for x in loc:
        k = _vkey(x["files"])
        if k not in seen:
            seen.add(k)
            extra.append({"e": {kk: vv for kk, vv in x["e"].items() if kk != "to"}, "files": x["files"]})
    if cur_here and _vkey(cur_here) != _vkey(cur_new) and _vkey(cur_here) not in seen:
        try:
            nm = (json.loads(cur_here.get("plugin.json") or "{}") or {}).get("name")
        except ValueError:
            nm = None
        extra.append({"e": {"at": int(time.time()), "label": "С этого компьютера до синхронизации", "code": bool(cur_here.get("server.py")), "name": nm},
                      "files": cur_here})
    extra = extra[-5:]
    while len(extra) + len(merged_inc) > KEEP and len(merged_inc) > 1:
        merged_inc.pop(0)
    out, renum = [], {}
    out_more = bool(extra)
    for i, x in enumerate(extra + merged_inc, 1):
        if "old" in x:
            renum[x["old"]] = i
        out.append({"e": dict(x["e"], v=i), "files": x["files"], "old": x.get("old")})
    for x in out:
        if "to" in x["e"]:
            if x["old"] is not None and x["e"]["to"] in renum:
                x["e"]["to"] = renum[x["e"]["to"]]
            else:
                x["e"].pop("to")
    return out, out_more


def install(host, pid, b, head):
    """Сборка с другого компьютера -> папка плагина здесь. -> "more" (легла, и здесь добавились свои версии — сборку надо
    отправить другим), True (легла), False (не легла: чужое имя, не прошла проверку)."""
    P = getattr(host, "plugins", None)
    if P is None or not ID_RX.fullmatch(pid) or b.get("id") != pid:
        return False
    cur = (getattr(P, "items", {}) or {}).get(pid)
    d = user_dir(P) / pid
    if (cur and cur.get("builtin")) or ((d / "plugin.json").is_file() and _made(d) is None):
        log.info("🔄 Плагин «%s» с другого компьютера не принят: здесь есть свой с тем же id", pid)
        return False
    files = {k: str(v) for k, v in b["files"].items() if k in dict(FILES) and isinstance(v, str)}
    try:
        man = json.loads(files.get("plugin.json") or "")
    except ValueError:
        man = None
    if not isinstance(man, dict) or not isinstance(man.get("made"), dict) or not files.get("ui.html"):
        return False
    if man.get("id") not in (None, pid):               # id в plugin.json — чужого плагина: подмена (рецензия 04.11, P2)
        log.warning("🔄 Плагин %s с другого компьютера не принят: в plugin.json id «%s»", pid, man.get("id"))
        return False
    from plugin_maker import check                    # та же проверка, что у сделанного здесь, — и на диск то, что она вернула
    code = bool(files.get("server.py")) or bool(man.get("mcp"))
    files, man, probs = check(dict(files), code, pid)
    if probs or not isinstance(man, dict) or man.get("id") != pid:
        log.warning("🔄 Плагин «%s» с другого компьютера не принят: %s", pid, "; ".join(probs[:3]))
        return False
    files = {name: files[name] for name, _ in FILES if files.get(name)}
    code = bool(files.get("server.py")) or bool(man.get("mcp"))
    here, loc = _local(d, pid) if d.is_dir() else ({}, [])
    old_code = (here.get("server.py") or "", json.dumps((_made(d) or {}).get("mcp") or {}, sort_keys=True)) if d.is_dir() else None
    new_code = (files.get("server.py") or "", json.dumps(man.get("mcp") or {}, sort_keys=True))
    fresh = not (d / "plugin.json").is_file()
    s = getattr(P, "s", None) or getattr(host, "s", None)
    on = dict((s.get("plugins", "on") or {}) if s is not None else {})
    ask = code and new_code != old_code                 # программа новая или другая — запускать только с разрешения
    inc = []
    for x in (b.get("versions") or [])[-KEEP:]:
        e = x.get("e") if isinstance(x, dict) else None
        if not isinstance(e, dict) or not isinstance(e.get("v"), int):
            continue
        vf = {name: t for name, _ in FILES if isinstance(t := (x.get("files") or {}).get(name), str) and t}
        if vf.get("server.py") and vf["server.py"] != files.get("server.py"):
            vf.pop("server.py")                         # чужая программа в старой версии — не берём (рецензия 04.11, P1)
        inc.append({"e": {k: e[k] for k in ("v", "at", "label", "code", "name", "to") if k in e}, "files": vf})
    vers, more = _merge(inc, loc, here, files)
    if ask and pid in on:
        P.remove(pid)                                   # выключить до «Включить»: прежние дела по расписанию остаются у человека
    try:
        for name, rel in FILES:
            p = d / rel.format(id=pid)
            if files.get(name):
                _write(p, files[name])
            elif p.exists():
                p.unlink()
        if not files.get("skill.md"):
            shutil.rmtree(d / "skills", ignore_errors=True)
        vn = d / ".versions.new"
        shutil.rmtree(vn, ignore_errors=True)
        for x in vers:
            for name, t in x["files"].items():
                if t:
                    _write(vn / str(x["e"]["v"]) / name, t)
        if vers:
            _write(vn / "index.json", json.dumps([x["e"] for x in vers], ensure_ascii=False, indent=1))
        shutil.rmtree(d / ".versions", ignore_errors=True)
        if vers:
            vn.rename(d / ".versions")
    except OSError as e:
        log.warning("🔄 Плагин %s с другого компьютера не записался: %s", pid, e)
        if fresh:
            shutil.rmtree(d, ignore_errors=True)
        return False
    P.reload()
    frm = str(head.get("from") or "другой компьютер")[:40]
    if pid not in P.items or (P.items[pid].get("dir") and Path(P.items[pid]["dir"]) != d):
        if fresh:                                       # не встал — его папки здесь не остаётся
            shutil.rmtree(d, ignore_errors=True)
            P.reload()
        return False
    if ask:
        _arrived(s, pid, {"from": frm, "code": True, "at": int(time.time())})
        log.info("🔄 Плагин «%s» пришёл с «%s» со своей программой — выключен, пока его не включат", man.get("name"), frm)
    elif fresh:
        P.install(pid, {})
        log.info("🔄 Плагин «%s» пришёл с «%s»", man.get("name"), frm)
    else:
        log.info("🔄 Плагин «%s» — правка с «%s»", man.get("name"), frm)
    _changed(host, pid, code and not ask and pid in ((s.get("plugins", "on") or {}) if s is not None else {}))
    return "more" if more else True


def _trash(P, d: Path):
    """Папку плагина — в корзину системы (как всё удаление в Dewiar); не вышло — в «.trash» рядом со своими плагинами."""
    try:
        import guard
        files = [x for x in d.rglob("*") if x.is_file()]
        guard.trash([{"path": str(d), "dir": True, "files": len(files), "size": sum(x.stat().st_size for x in files)}])
        return
    except Exception as e:  # noqa: BLE001
        log.info("🔄 Плагин %s — в корзину системы не вышло (%s), кладу в .trash", d.name, e)
    dst = user_dir(P) / ".trash" / f"{d.name}-{time.strftime('%Y%m%d-%H%M%S')}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), str(dst))


def remove(host, pid):
    """Плагин удалили на другом компьютере — удалить и здесь (только свой плагин Лиры)."""
    P = getattr(host, "plugins", None)
    if P is None or not present(P, pid) or _made(user_dir(P) / pid) is None:
        return
    p = (getattr(P, "items", {}) or {}).get(pid)
    if p and p.get("builtin"):
        return
    try:
        P.remove(pid)
    except Exception:  # noqa: BLE001
        pass
    try:
        _trash(P, user_dir(P) / pid)                   # в корзину: удаление с другого компьютера можно вернуть (рецензия 04.11)
    except OSError as e:
        log.warning("🔄 Плагин %s не удалён: %s", pid, e)
        return
    P.reload()
    s = getattr(P, "s", None) or getattr(host, "s", None)
    if s is not None:
        _arrived(s, pid, None)
        try:
            import plugin_bridge as B
            B.forget(s, pid)
        except Exception:  # noqa: BLE001
            pass
    log.info("🔄 Плагин %s удалён на другом компьютере — удалён и здесь", pid)
    _changed(host, pid, True)


def _changed(host, pid, code):
    """Навыки, серверы и меню студии — сразу (как после правки словами)."""
    for f in (lambda: host.skills.reload(), lambda: host.mcp.reconcile() if code else None,
              lambda: host.emit("plugin_made", id=pid, name="", icon="", open=False)):
        try:
            f()
        except Exception:  # noqa: BLE001 — у ядра без студии (проверки) этого нет
            pass
