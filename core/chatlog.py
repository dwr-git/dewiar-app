"""Переписка с персонажами для студии («Чат»): что сказал или написал человек и что ответил ассистент — голосом, текстом,
из Telegram. Отдельно от памяти модели (conversation.json сворачивается и сбрасывается через 8 часов тишины) — здесь
просто лента, как в мессенджере, только на этом компьютере (state/chat.jsonl, до 5000 последних реплик).

Записи: {"id", "ts", "role": "user"|"assistant", "text", "who"?: pid персонажа, "via"?: "message", "att"?: вложения
[{kind: image|file, name, path (во «Входящих» папки ассистента), thumb (миниатюра картинки, data:URL)}]}.
Ответ модели в одном ходе приходит одной репликой; если подряд пришло продолжение того же ответа (текст начинается с
прежнего) — запись обновляется, а не дублируется. Продиктованные для сейфа секреты маскируются, как в журнале."""
import json
import threading
import time
from pathlib import Path

KEEP = 5000


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

    def add(self, role, text, who=None, via=None, att=None, steps=None):
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
