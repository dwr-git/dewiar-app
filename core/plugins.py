"""Плагины: навыки + MCP-серверы + свои настройки + примеры фраз + дела по расписанию — одним пакетом, одной кнопкой
(решение владельца 20.10: «скилы отдельно, mcp отдельно — красиво скомпоновать и приправить возможностями»).

Папка плагина:
    <id>/plugin.json        — {id, name, icon, color, category, tagline, description, version, author,
                               skills: [имена папок в skills/], phrases: [...], uses: [инструменты — для подписи],
                               settings: [{key, label, type: text|select|number|toggle, options, default, placeholder}],
                               jobs: [{id, title, when, task}]  — дела по расписанию, включаются по желанию; {key} в task —
                                                                  значение настройки плагина,
                               mcp: {имя: {type: stdio|http, command, args, env, url, headers}} — необязательно}
    <id>/skills/<имя>/SKILL.md — обычные навыки (core/skills.py), видны модели, пока плагин установлен
    <id>/README.md          — для людей

Встроенные — DATA_DIR/plugins (каталог в студии сразу, без скачивания); свои — CONFIG_DIR/plugins (из zip).
Установлен ли и с какими настройками — settings.plugins.on = {id: {"at": unix, "values": {...}, "jobs": {jid: id напоминания}}}.
MCP-серверы плагина кладутся в settings.mcp.servers под именем «<id>-<имя>» с пометкой plugin (их видно и в списке MCP);
удаление плагина убирает и их. Чужой плагин запускает программы только через MCP-сервер, который человек видит и может
выключить, — а скрипты навыков, как и раньше, только через run_command с подтверждением."""

import io
import json
import logging
import re
import shutil
import time
import zipfile
from pathlib import Path

from settings import CONFIG_DIR, DATA_DIR

log = logging.getLogger("dewiar.plugins")
BUILTIN_DIR = DATA_DIR / "plugins"
USER_DIR = CONFIG_DIR / "plugins"
MAX_ZIP = 20 * 1024 * 1024
SET_TYPES = ("text", "select", "number", "toggle")


class PluginError(Exception):
    pass


def _id(x):
    return re.sub(r"[^a-z0-9-]+", "-", str(x or "").lower()).strip("-")[:40]


def parse_plugin(d: Path, builtin: bool):
    """plugin.json -> словарь плагина (проверенный и с безопасными значениями) или исключение PluginError."""
    try:
        m = json.loads((d / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PluginError(f"plugin.json не читается: {e}") from e
    if not isinstance(m, dict):
        raise PluginError("plugin.json — не объект")
    pid = _id(m.get("id") or d.name)
    if not pid or not str(m.get("name") or "").strip():
        raise PluginError("у плагина должны быть id и name")
    skills = []
    for s in m.get("skills") or []:
        sd = d / "skills" / str(s)
        if re.fullmatch(r"[\w.-]+", str(s)) and (sd / "SKILL.md").is_file():
            skills.append(sd)
    if not skills:                                   # skills не перечислены — все папки с SKILL.md
        skills = sorted(p.parent for p in (d / "skills").glob("*/SKILL.md")) if (d / "skills").is_dir() else []
    sets = []
    for s in m.get("settings") or []:
        if not isinstance(s, dict) or not _id(s.get("key")).replace("-", "_") or s.get("type", "text") not in SET_TYPES:
            continue
        sets.append({"key": re.sub(r"[^\w]", "_", str(s["key"]))[:40], "label": str(s.get("label") or s["key"])[:80],
                     "type": s.get("type", "text"), "options": [str(o)[:60] for o in (s.get("options") or [])][:12],
                     "default": s.get("default", ""), "placeholder": str(s.get("placeholder") or "")[:120],
                     "hint": str(s.get("hint") or "")[:200], "required": bool(s.get("required"))})
    jobs = [{"id": _id(j.get("id") or f"j{i}"), "title": str(j.get("title") or "")[:120], "when": str(j.get("when") or "")[:80],
             "task": str(j.get("task") or "")[:600]}
            for i, j in enumerate(m.get("jobs") or []) if isinstance(j, dict) and j.get("when") and j.get("task")]
    mcp = {}
    for n, c in (m.get("mcp") or {}).items() if isinstance(m.get("mcp"), dict) else []:
        if not isinstance(c, dict) or c.get("type", "stdio") not in ("stdio", "http"):
            continue
        cfg = {"type": c.get("type", "stdio")}
        if cfg["type"] == "http":
            if not re.match(r"^https?://", str(c.get("url") or "")):
                continue
            cfg["url"] = str(c["url"])
            if isinstance(c.get("headers"), dict):
                cfg["headers"] = {str(k): str(v) for k, v in c["headers"].items()}
        else:
            if not c.get("command"):
                continue
            cfg.update(command=str(c["command"]), args=[str(a) for a in c.get("args") or []],
                       env={str(k): str(v) for k, v in (c.get("env") or {}).items()})
        mcp[re.sub(r"[^\w-]+", "_", str(n))[:30]] = cfg
    return {"id": pid, "name": str(m["name"]).strip()[:60], "icon": str(m.get("icon") or "🧩")[:4],
            "color": m.get("color") if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(m.get("color") or "")) else "#8B8CF7",
            "category": str(m.get("category") or "Разное")[:30], "tagline": str(m.get("tagline") or "")[:160],
            "description": str(m.get("description") or "")[:1200], "version": str(m.get("version") or "1.0")[:20],
            "author": str(m.get("author") or "")[:60], "phrases": [str(x)[:120] for x in (m.get("phrases") or [])][:10],
            "uses": [str(x)[:40] for x in (m.get("uses") or [])][:12], "settings": sets, "jobs": jobs, "mcp": mcp,
            "skill_dirs": skills, "dir": d, "builtin": builtin,
            # витрина на «Главной» (31.10): фраза «попробуйте сразу» и ролик — id урока Академии («15-plugins») или адрес
            "try": str(m.get("try") or (m.get("phrases") or [""])[0])[:120],
            # ссылки панели плагина на его файлы в папке Dewiar: [{"label": "Открыть галерею", "path": "Рисунки/Галерея.html"}]
            "links": [{"label": str(x.get("label"))[:40], "path": str(x.get("path"))[:120]} for x in (m.get("links") or [])
                      if isinstance(x, dict) and x.get("label") and x.get("path") and ".." not in str(x.get("path"))
                      and not str(x.get("path")).startswith(("/", "\\")) and ":" not in str(x.get("path"))][:3],
            "video": str(m.get("video") or "") if re.fullmatch(r"[\w-]{1,40}|https://[^\s\"'<>]{8,300}", str(m.get("video") or "")) else ""}


class Plugins:
    def __init__(self, settings):
        self.s = settings
        self.items = {}
        self.reload()

    def reload(self):
        items = {}
        for root, builtin in ((BUILTIN_DIR, True), (USER_DIR, False)):
            if not root.is_dir():
                continue
            for f in sorted(root.glob("*/plugin.json")):
                try:
                    p = parse_plugin(f.parent, builtin)
                except PluginError as e:
                    log.warning("плагин %s пропущен: %s", f.parent.name, e)
                    continue
                if not builtin and p["id"] in items and items[p["id"]]["builtin"]:
                    continue                         # свой не перекрывает встроенный с тем же id
                items[p["id"]] = p
        self.items = items

    # ---- состояние ----
    def _on(self):
        return dict(self.s.get("plugins", "on") or {})

    def installed(self):
        on = self._on()
        return [p for pid, p in self.items.items() if pid in on]

    def values(self, pid):
        p, on = self.items.get(pid), self._on().get(pid) or {}
        if not p:
            return {}
        v = dict(on.get("values") or {})
        return {s["key"]: v.get(s["key"], s["default"]) for s in p["settings"]}

    def skill_roots(self):
        """[(папка навыка, id плагина)] — для core/skills.py: навыки установленных плагинов."""
        return [(d, p["id"]) for p in self.installed() for d in p["skill_dirs"]]

    def note(self, pid):
        """Настройки плагина словами — к тексту его навыка (use_skill)."""
        p = self.items.get(pid)
        if not p:
            return ""
        vals = self.values(pid)
        parts = [f"{s['label']} — {('да' if vals.get(s['key']) else 'нет') if s['type'] == 'toggle' else vals.get(s['key'])}"
                 for s in p["settings"] if vals.get(s["key"]) not in ("", None) or s["type"] == "toggle"]
        return f"\n\nНастройки плагина «{p['name']}»: " + "; ".join(parts) + "." if parts else ""

    def catalog(self):
        on, out = self._on(), []
        for pid, p in sorted(self.items.items(), key=lambda x: (not x[1]["builtin"], x[1]["category"], x[1]["name"])):
            st = on.get(pid) or {}
            out.append({k: p[k] for k in ("id", "name", "icon", "color", "category", "tagline", "description", "version", "author",
                                          "phrases", "uses", "settings", "builtin", "try", "video", "links")}
                       | {"installed": pid in on, "values": self.values(pid), "skills": [d.name for d in p["skill_dirs"]],
                          "mcp": [f"{pid}-{n}" for n in p["mcp"]],
                          "jobs": [dict(j, on=bool((st.get("jobs") or {}).get(j["id"]))) for j in p["jobs"]],
                          "readme": self._readme(p)})
        return out

    @staticmethod
    def _readme(p):
        try:
            return (p["dir"] / "README.md").read_text(encoding="utf-8")[:8000]
        except OSError:
            return ""

    @staticmethod
    def guide():
        """«Как сделать свой плагин» — для студии."""
        try:
            return (BUILTIN_DIR / "README.md").read_text(encoding="utf-8")
        except OSError:
            return ""

    # ---- установка ----
    def install(self, pid, values=None):
        p = self.items.get(pid)
        if not p:
            raise PluginError(f"нет плагина {pid}")
        on = self._on()
        cur = dict(on.get(pid) or {"at": int(time.time()), "values": {}, "jobs": {}})
        if values is not None:
            cur["values"] = self._clean(p, values)
        on[pid] = cur
        servers = dict(self.s.get("mcp", "servers") or {})
        for n, c in p["mcp"].items():
            servers.setdefault(f"{pid}-{n}", dict(c, plugin=pid, enabled=True))
        self.s.update({"plugins": {"on": on}, "mcp": {"servers": servers}})
        return cur

    def set_values(self, pid, values):
        p, on = self.items.get(pid), self._on()
        if not p or pid not in on:
            raise PluginError("плагин не установлен")
        on[pid] = dict(on[pid], values=self._clean(p, values))
        self.s.update({"plugins": {"on": on}})
        return self.values(pid)

    @staticmethod
    def _clean(p, values):
        out = {}
        for s in p["settings"]:
            v = (values or {}).get(s["key"])
            if v is None:
                continue
            if s["type"] == "toggle":
                out[s["key"]] = bool(v)
            elif s["type"] == "number":
                try:
                    out[s["key"]] = float(v) if "." in str(v) else int(v)
                except ValueError:
                    continue
            elif s["type"] == "select" and s["options"] and str(v) not in s["options"]:
                continue
            else:
                out[s["key"]] = " ".join(str(v).split())[:200]
        return out

    def remove(self, pid):
        """Удалить плагин: его навыки больше не видны модели, его MCP-серверы убираются. -> id дел, которые он завёл
        (снимать ли их — решает вызывающий: они в напоминаниях человека)."""
        on = self._on()
        st = on.pop(pid, None) or {}
        servers = {n: c for n, c in (self.s.get("mcp", "servers") or {}).items() if c.get("plugin") != pid}
        # mcp.servers и plugins.on заменяем целиком (как студия): _merge не умеет удалять ключи
        self.s.update({"plugins": {"on": None}, "mcp": {"servers": None}})
        self.s.update({"plugins": {"on": on}, "mcp": {"servers": servers}})
        return [x for x in (st.get("jobs") or {}).values() if x]

    def job_text(self, pid, jid):
        p = self.items.get(pid)
        j = next((x for x in (p or {}).get("jobs") or [] if x["id"] == jid), None)
        if not j:
            raise PluginError("нет такого дела у плагина")
        vals = self.values(pid)
        task = re.sub(r"\{(\w+)\}", lambda m: str(vals.get(m.group(1)) or "…"), j["task"])
        return task, j["when"]

    def job_mark(self, pid, jid, rid):
        on = self._on()
        if pid not in on:
            raise PluginError("плагин не установлен")
        jobs = dict(on[pid].get("jobs") or {})
        jobs[jid] = rid
        on[pid] = dict(on[pid], jobs=jobs)
        self.s.update({"plugins": {"on": None}})
        self.s.update({"plugins": {"on": on}})

    # ---- свои плагины (zip) ----
    def install_zip(self, data: bytes):
        """Плагин из zip -> id. Папка с самым верхним plugin.json; пути с .. и абсолютные отвергаются; распаковка во
        временную папку и проверка до замены прежней версии. Встроенный плагин своим не перекрыть."""
        if len(data) > MAX_ZIP:
            raise PluginError("архив плагина больше 20 МБ")
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise PluginError("это не zip-архив") from e
        names = [n for n in z.namelist() if not n.endswith("/")]
        top = sorted((n for n in names if n.split("/")[-1] == "plugin.json"), key=lambda n: n.count("/"))
        if not top:
            raise PluginError("в архиве нет plugin.json")
        prefix = top[0][:-len("plugin.json")]
        USER_DIR.mkdir(parents=True, exist_ok=True)
        tmp = USER_DIR / ".new"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            for n in names:
                if not n.startswith(prefix):
                    continue
                rel = Path(n[len(prefix):])
                if rel.is_absolute() or ".." in rel.parts or n.startswith("/"):
                    raise PluginError("в архиве опасные пути")
                out = tmp / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(n))
            p = parse_plugin(tmp, False)
            if p["id"] in self.items and self.items[p["id"]]["builtin"]:
                raise PluginError(f"«{p['id']}» — имя встроенного плагина, выберите другое id")
            target = USER_DIR / p["id"]
            shutil.rmtree(target, ignore_errors=True)
            tmp.rename(target)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.reload()
        return p["id"]

    def delete(self, pid):
        p = self.items.get(pid)
        if not p or p["builtin"]:
            raise PluginError("встроенный плагин можно только удалить из установленных")
        self.remove(pid)
        shutil.rmtree(p["dir"], ignore_errors=True)
        self.reload()
