"""Переписка с персонажами для студии («Чат»): что сказал или написал человек и что ответил ассистент — голосом, текстом,
из Telegram. Отдельно от памяти модели (conversation.json сворачивается и сбрасывается через 8 часов тишины) — здесь
просто лента, как в мессенджере, только на этом компьютере (state/chat.jsonl, до 5000 последних реплик).

Записи: {"id", "ts", "role": "user"|"assistant", "text", "who"?: pid персонажа, "via"?: "message", "att"?: вложения
[{kind: image|file, name, path (во «Входящих» папки ассистента), thumb (миниатюра картинки, data:URL)}]}.
Ответ модели в одном ходе приходит одной репликой; если подряд пришло продолжение того же ответа (текст начинается с
прежнего) — запись обновляется, а не дублируется. Продиктованные для сейфа секреты маскируются, как в журнале.

0.86 (пользователь: «стандартные для всех чатов вещи — остановка, перегенерация, исправление и метрики»):
— у ответа модели — meta {model, first: с до первого слова, total: с всего, tin/tout: токены, если сервер посчитал};
— «Ещё раз» (variant): новый ответ становится текущим, прежние — в vars [{text, ts, meta?, steps?}] (листать 1/2…, до 6);
— «Изменить» (edit_user): последний вопрос получает новый текст (edited: время), всё после него убирается.
Беседы (идея №145): лента state/chat.jsonl — всегда ТЕКУЩАЯ беседа (как раньше: на неё смотрят инструменты, плагины,
проверки), а отложенные — в state/chats/<id>.jsonl с памятью модели <id>.conv.json (копия conversation.json той беседы);
state/chats/index.json — {"active": {id, title, ts}, "list": [{id, title, ts, last, n}]}. Открыть беседу — файлы меняются
местами (switch), ядро перечитывает память (Conversation.reload). Переписка по-прежнему только на этом компьютере."""
import json
import re
import shutil
import threading
import time
from pathlib import Path

KEEP = 5000
VARS_MAX = 5              # прежних вариантов ответа («Ещё раз») — не больше
THREADS_MAX = 200         # отложенных бесед — не больше (самые старые уходят)
META_KEYS = ("model", "first", "total", "tin", "tout", "cached", "stopped")


def _meta(meta):
    """Метрики ответа — только известные поля и только числа/строки (в ленту и на экран)."""
    out = {}
    for k in META_KEYS:
        v = (meta or {}).get(k)
        if v is None or v == "":
            continue
        if k == "model":
            out[k] = str(v)[:80]
        elif isinstance(v, (int, float)) and v >= 0:
            out[k] = round(float(v), 2) if k in ("first", "total") else int(v)
    return out


def thread_title(items):
    """Название беседы по первому вопросу: «Как настроить почту на телефоне» (до 48 символов, по границе слова)."""
    for x in items:
        if x.get("role") == "user" and (x.get("text") or "").strip():
            t = " ".join(str(x["text"]).split())
            if len(t) > 48:
                t = t[:48].rsplit(" ", 1)[0].rstrip(",.;:—-") + "…"
            return t
    return ""


class ChatLog:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.items = []
        self._load()

    def _load(self):
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    x = json.loads(line)
                except ValueError:
                    continue
                if isinstance(x, dict) and (x.get("text") or x.get("att")) and x.get("role") in ("user", "assistant"):
                    self.items.append(x)
        except OSError:
            pass
        self.items = self.items[-KEEP:]

    def _write_all(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in self.items), encoding="utf-8")
        tmp.replace(self.path)

    def add(self, role, text, who=None, via=None, att=None, steps=None, meta=None):
        """-> запись (новая или обновлённая) или None, если писать нечего. att — вложения: [{kind, name, path, thumb?}];
        steps — что сделано за ход: [{t: что, s: done|error|yes|no|ask, e?: ошибка}] (показ в «Чате» студии)."""
        text = (text or "").strip()
        if (not text and not att) or role not in ("user", "assistant"):
            return None
        try:
            from vault import mask
            text = mask(text) if role == "user" else text
        except Exception:  # noqa: BLE001
            pass
        now = time.time()
        with self._lock:
            last = self.items[-1] if self.items else None
            # тот же ответ дописался (или повторился) — обновляем запись, а не плодим одинаковые
            if not att and last and last["role"] == role and now - last["ts"] < 180 and last.get("who") == who and \
                    (text == last["text"] or (role == "assistant" and text.startswith(last["text"]))):
                last["text"], last["ts"] = text, now
                if steps:
                    last["steps"] = steps[:12]
                if _meta(meta):
                    last["meta"] = _meta(meta)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._write_all()
                return dict(last, updated=True)
            item = {"id": f"{int(now * 1000):x}{len(self.items) % 1000:03d}", "ts": now, "role": role, "text": text[:20000]}
            if who:
                item["who"] = who
            if via:
                item["via"] = via
            if att:
                item["att"] = att[:10]
            if steps:
                item["steps"] = steps[:12]
            if role == "assistant" and _meta(meta):
                item["meta"] = _meta(meta)
            self.items.append(item)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if len(self.items) > KEEP + 500:
                self.items = self.items[-KEEP:]
                self._write_all()
            else:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            return dict(item)

    def page(self, before=None, limit=80, q=""):
        """Последние limit реплик (до записи before, если задана) — по времени, старые сверху; q — поиск по словам."""
        with self._lock:
            items = list(self.items)
        if before:
            i = next((k for k, x in enumerate(items) if x["id"] == before), len(items))
            items = items[:i]
        if q:
            ql = q.lower()
            items = [x for x in items if ql in x["text"].lower()]
        limit = max(1, min(500, int(limit or 80)))
        return {"items": items[-limit:], "more": len(items) > limit, "total": len(self.items)}

    def clear(self):
        with self._lock:
            self.items = []
            try:
                self.path.unlink()
            except OSError:
                pass

    # ---------- «Ещё раз» и «Изменить» ----------
    def get(self, item_id):
        with self._lock:
            return next((dict(x) for x in self.items if x.get("id") == item_id), None)

    def last_pair(self):
        """Последний вопрос человека и ответ на него (если уже есть): (user, assistant | None) — копии; нет вопроса — (None, None)."""
        with self._lock:
            for i in range(len(self.items) - 1, -1, -1):
                if self.items[i]["role"] == "user":
                    a = next((x for x in self.items[i + 1:] if x["role"] == "assistant"), None)
                    return dict(self.items[i]), (dict(a) if a else None)
        return None, None

    def variant(self, item_id, text, meta=None, steps=None, att=None, who=None):
        """«Ещё раз»: новый ответ — текущим в той же записи, прежний — в vars. -> запись или None (записи нет)."""
        text = (text or "").strip()
        if not text:
            return None
        with self._lock:
            x = next((y for y in self.items if y.get("id") == item_id and y["role"] == "assistant"), None)
            if x is None:
                return None
            old = {k: x[k] for k in ("text", "ts", "meta", "steps", "att", "who") if x.get(k)}
            x["vars"] = (list(x.get("vars") or []) + [old])[-VARS_MAX:]
            x["text"], x["ts"] = text[:20000], time.time()
            if who:
                x["who"] = who
            for k, v in (("meta", _meta(meta)), ("steps", (steps or [])[:12]), ("att", (att or [])[:10])):
                if v:
                    x[k] = v
                else:
                    x.pop(k, None)
            self._write_all()
            return dict(x)

    def edit_user(self, item_id, text):
        """«Изменить»: вопрос item_id — новым текстом, всё после него (ответы) — убрать. -> (запись, сколько убрано) или (None, 0)."""
        text = (text or "").strip()
        if not text:
            return None, 0
        with self._lock:
            i = next((k for k, y in enumerate(self.items) if y.get("id") == item_id and y["role"] == "user"), -1)
            if i < 0:
                return None, 0
            x = self.items[i]
            try:
                from vault import mask
                text = mask(text)
            except Exception:  # noqa: BLE001
                pass
            cut = len(self.items) - i - 1
            x["text"], x["edited"] = text[:20000], time.time()
            del self.items[i + 1:]
            self._write_all()
            return dict(x), cut

    # ---------- беседы (идея №145) ----------
    @property
    def dir(self):
        return self.path.parent / "chats"

    def _conv_path(self):
        return self.path.parent / "conversation.json"

    def _index(self):
        try:
            d = json.loads((self.dir / "index.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        act = d.get("active") if isinstance(d.get("active"), dict) else {}
        lst = [t for t in d.get("list") or [] if isinstance(t, dict) and re.fullmatch(r"c[0-9a-f]{6,20}", str(t.get("id") or ""))]
        if not act.get("id"):                            # первый раз (или файл испорчен) — у текущей беседы появляется имя-номер
            first = self.items[0]["ts"] if self.items else time.time()
            act = {"id": self._new_id(first), "title": "", "ts": first}
            try:
                self._save_index({"active": act, "list": lst})
            except OSError:
                pass
        return {"active": act, "list": lst}

    def _save_index(self, d):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / "index.tmp"
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.dir / "index.json")

    @staticmethod
    def _new_id(ts=None):
        return "c%x" % int((ts or time.time()) * 1000)

    def _valid(self, tid):
        return bool(re.fullmatch(r"c[0-9a-f]{6,20}", str(tid or "")))

    def threads(self):
        """Список бесед: текущая первой, дальше — по последней реплике. [{id, title, ts, last, n, active}]"""
        with self._lock:
            d = self._index()
            items = list(self.items)
        a = d["active"]
        cur = {"id": a["id"], "title": a.get("title") or thread_title(items) or "Новая беседа", "ts": a.get("ts") or time.time(),
               "last": items[-1]["ts"] if items else a.get("ts") or time.time(), "n": len(items), "active": True,
               "named": bool(a.get("title"))}
        rest = sorted(({**t, "active": False, "named": bool(t.get("named"))} for t in d["list"]), key=lambda t: -float(t.get("last") or 0))
        return [cur] + rest

    def _read_items(self, path):
        out = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    x = json.loads(line)
                except ValueError:
                    continue
                if isinstance(x, dict) and x.get("role") in ("user", "assistant"):
                    out.append(x)
        except OSError:
            pass
        return out

    def thread_items(self, tid):
        """Реплики беседы tid (текущей или отложенной) — для выгрузки."""
        with self._lock:
            if tid in ("", None) or tid == self._index()["active"]["id"]:
                return list(self.items)
        if not self._valid(tid):
            return []
        return self._read_items(self.dir / f"{tid}.jsonl")

    def _shelve(self, d):
        """Текущую беседу — на полку (под self._lock): лента и память модели — в chats/<id>.*. Пустую — не храним."""
        a = d["active"]
        if not self.items:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        self._write_all()
        shutil.move(str(self.path), str(self.dir / f"{a['id']}.jsonl"))
        cp = self._conv_path()
        if cp.exists():
            shutil.move(str(cp), str(self.dir / f"{a['id']}.conv.json"))
        d["list"] = [t for t in d["list"] if t.get("id") != a["id"]]
        d["list"].append({"id": a["id"], "title": a.get("title") or thread_title(self.items) or "Беседа", "named": bool(a.get("title")),
                          "ts": a.get("ts") or self.items[0]["ts"], "last": self.items[-1]["ts"], "n": len(self.items)})
        if len(d["list"]) > THREADS_MAX:                 # самые давние — прочь вместе с файлами
            d["list"].sort(key=lambda t: float(t.get("last") or 0))
            for t in d["list"][:-THREADS_MAX]:
                for f in (self.dir / f"{t['id']}.jsonl", self.dir / f"{t['id']}.conv.json"):
                    try:
                        f.unlink()
                    except OSError:
                        pass
            d["list"] = d["list"][-THREADS_MAX:]
        self.items = []

    def thread_new(self):
        """«Новая беседа»: текущую — на полку (читать и продолжить можно из списка), лента и память — с чистого листа.
        -> id новой беседы. Текущая пуста — она и остаётся (не плодим пустые)."""
        with self._lock:
            d = self._index()
            if not self.items:
                self._save_index(d)
                return d["active"]["id"]
            self._shelve(d)
            try:
                self._conv_path().unlink()
            except OSError:
                pass
            d["active"] = {"id": self._new_id(), "title": "", "ts": time.time()}
            self._save_index(d)
            return d["active"]["id"]

    def thread_open(self, tid):
        """Открыть отложенную беседу: она становится текущей (лента и память модели — её), текущая — на полку.
        -> True; нет такой — ValueError."""
        with self._lock:
            d = self._index()
            if tid == d["active"]["id"]:
                return True
            t = next((x for x in d["list"] if x.get("id") == tid), None)
            if t is None or not self._valid(tid):
                raise ValueError("Такой беседы нет — возможно, её удалили")
            src = self.dir / f"{tid}.jsonl"
            if not src.exists():
                raise ValueError("Файл беседы не найден")
            self._shelve(d)
            cp = self._conv_path()
            try:
                cp.unlink()
            except OSError:
                pass
            shutil.move(str(src), str(self.path))
            if (self.dir / f"{tid}.conv.json").exists():
                shutil.move(str(self.dir / f"{tid}.conv.json"), str(cp))
            d["list"] = [x for x in d["list"] if x.get("id") != tid]
            d["active"] = {"id": tid, "title": t.get("title") if t.get("named") else "", "ts": t.get("ts") or time.time()}
            self._save_index(d)
            self.items = []
        self._load()
        return True

    def thread_rename(self, tid, title):
        title = " ".join(str(title or "").split())[:80]
        with self._lock:
            d = self._index()
            if tid in ("", None) or tid == d["active"]["id"]:
                d["active"]["title"] = title
            else:
                t = next((x for x in d["list"] if x.get("id") == tid), None)
                if t is None:
                    raise ValueError("Такой беседы нет")
                t["title"], t["named"] = title or thread_title(self._read_items(self.dir / f"{tid}.jsonl")) or "Беседа", bool(title)
            self._save_index(d)
        return True

    def thread_delete(self, tid):
        """Удалить беседу. Текущую — значит очистить ленту (память модели сбрасывает ядро). -> была ли текущей."""
        with self._lock:
            d = self._index()
            if tid in ("", None) or tid == d["active"]["id"]:
                active = True
            else:
                active = False
                if not self._valid(tid):
                    raise ValueError("Такой беседы нет")
                d["list"] = [x for x in d["list"] if x.get("id") != tid]
                for f in (self.dir / f"{tid}.jsonl", self.dir / f"{tid}.conv.json"):
                    try:
                        f.unlink()
                    except OSError:
                        pass
                self._save_index(d)
        if active:
            self.clear()
            with self._lock:
                d = self._index()
                d["active"] = {"id": self._new_id(), "title": "", "ts": time.time()}
                self._save_index(d)
        return active

    def recent(self, since):
        """Реплики всех бесед с времени since (текущая и отложенные) — «что я говорил раньше» не теряется из-за новой беседы."""
        with self._lock:
            out = [x for x in self.items if x.get("ts", 0) >= since]
            lst = list(self._index()["list"])
        for t in lst:
            if float(t.get("last") or 0) >= since:
                out += [x for x in self._read_items(self.dir / f"{t['id']}.jsonl") if x.get("ts", 0) >= since]
        return sorted(out, key=lambda x: x.get("ts", 0))

    def export(self, tid, fmt="md", names=None):
        """Беседа текстом: fmt md — Markdown (заголовок, дни, кто сказал), txt — простой текст. names — {pid: имя}.
        -> {"name": имя файла, "text": содержимое}."""
        items = self.thread_items(tid)
        th = next((t for t in self.threads() if t["id"] == (tid or self.threads()[0]["id"])), None) or {}
        title = th.get("title") or thread_title(items) or "Беседа"
        names = names or {}
        md = fmt != "txt"
        out, day = [], ""
        out.append(f"# {title}" if md else title)
        if items:
            a, b = time.localtime(items[0]["ts"]), time.localtime(items[-1]["ts"])
            out.append(("_" if md else "") + time.strftime("%d.%m.%Y %H:%M", a) + " — " + time.strftime("%d.%m.%Y %H:%M", b)
                       + ("_" if md else ""))
        for x in items:
            d = time.strftime("%d.%m.%Y", time.localtime(x["ts"]))
            if d != day:
                day = d
                out.append(f"\n## {d}" if md else f"\n— {d} —")
            who = "Вы" if x["role"] == "user" else names.get(x.get("who") or "", "") or "Ассистент"
            hm = time.strftime("%H:%M", time.localtime(x["ts"]))
            text = str(x.get("text") or "").strip()
            files = [a.get("name") for a in x.get("att") or [] if a.get("name")]
            if files:
                text += ("\n" if text else "") + "Вложения: " + ", ".join(files)
            if md:
                out.append(f"\n**{who}** · {hm}\n\n{text}")
            else:
                out.append(f"\n[{hm}] {who}:\n{text}")
        safe = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", title).strip(" .")[:60] or "Беседа"
        return {"name": f"{safe}.{'md' if md else 'txt'}", "text": "\n".join(out).strip() + "\n"}
