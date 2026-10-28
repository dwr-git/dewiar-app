"""«Дозор» — Лира присматривает и говорит, когда готово (0.58; владелец 28.10: «хожу по дому и раз в 5–10 минут смотрю,
нет ли ответа, нет ли нового выпуска… вот бы Лира так умела: смотрела на экран по заданию и, если выполнено, сообщала
мне на компьютере и на телефоне»; «режим может получиться действительно крутым — описать везде и показать»).

Три вида дозора:
  • screen — экран: раз в every секунд снимок; если с прошлой проверки экран почти не изменился (отпечаток 48×27 в
    оттенках серого, сравнение на этом компьютере) — модель не спрашиваем; изменился — модель со зрением отвечает
    «ДА — …» или «НЕТ — …» на условие what («Claude закончил и написал ответ»). Снимок никуда не сохраняется.
  • file — папка: появился новый файл (по маске pattern, «*.mp4»), докачанный — размер не меняется между проверками;
    недокачанные (.part, .crdownload, .tmp, .download) не считаются.
  • page — страница: текст страницы (без разметки); what — слово или фраза («Одобрено»): дозор — когда она появилась;
    без what — когда текст страницы изменился.
Каждый дозор кончается сам: условие выполнено, или вышел срок until (по умолчанию 3 часа), или «Стоп».

Состояние — STATE_DIR/watch.json: {"items": [{id, kind, what, title, every, until, created, status: active|done|stopped|
expired|failed, last, note, checks, asked, sig, base, seen, done_at, result}]} — последние 40.
Проверки (check_*) — чистые функции над снимком/папкой/страницей; спрашивать модель и звать уведомления — ядро
(engine_watch.py)."""

import fnmatch
import hashlib
import io
import json
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger("dewiar.watch")
KINDS = ("screen", "file", "page")
EVERY = {"screen": 300, "file": 20, "page": 600}         # по умолчанию: экран — раз в 5 минут, папка — 20 с, страница — 10 минут
MIN_EVERY = {"screen": 60, "file": 5, "page": 60}
HOURS = 3.0
SIG_W, SIG_H = 48, 27
SIG_DIFF = 2.5                                          # средняя разница отпечатков (0–255), ниже — «экран не изменился»
ASK_ANYWAY = 1800                                       # с, раз в столько спрашиваем модель, даже если экран не менялся
PARTIAL = (".part", ".crdownload", ".tmp", ".download", ".partial", ".!ut", ".opdownload")


def screen_sig(data):
    """Снимок экрана (байты картинки) -> отпечаток: список яркостей 48×27."""
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("L").resize((SIG_W, SIG_H), Image.BILINEAR)
    return list(im.getdata())


def sig_diff(a, b):
    if not a or not b or len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def parse_verdict(text):
    """Ответ модели «ДА — …» / «НЕТ — …» -> (выполнено?, пояснение)."""
    t = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.S).strip().strip("*` ")
    m = re.match(r"(?i)(да|нет|yes|no)\b[\s—–:,.-]*(.*)", t)
    if not m:
        return False, t[:160]
    return m.group(1).lower() in ("да", "yes"), m.group(2).strip()[:200]


VERDICT_SYSTEM = ("Ты проверяешь снимок экрана пользователя по одному условию. Экранов может быть несколько. Ответь строго одной "
                  "строкой: «ДА — в каком окне или программе и что именно видно» (если условие выполнено) или «НЕТ — что на экране сейчас, коротко». Виджет ассистента (круглое лицо "
                  "в углу) не учитывай. Окна самой Dewiar (студия «Dewiar», раздел «Дозор», виджет, блокнот) не учитывай: "
                  "текст условия там написал сам пользователь — это не результат, смотри на другие окна. Не выдумывай: "
                  "если не видно — НЕТ.")


def known_folder(name):
    """«Загрузки», «Downloads», «рабочий стол», «Документы» -> путь; иначе — как есть (с ~)."""
    n = str(name or "").strip().strip("«»\"'")
    low = n.lower()
    home = Path.home()
    alias = {"загрузк": "DOWNLOAD", "download": "DOWNLOAD", "рабоч": "DESKTOP", "desktop": "DESKTOP", "документ": "DOCUMENTS",
             "document": "DOCUMENTS", "видео": "VIDEOS", "video": "VIDEOS", "изображен": "PICTURES", "картин": "PICTURES", "pictures": "PICTURES"}
    for k, v in alias.items():
        if low.startswith(k) and "/" not in low and "\\" not in low:
            try:
                import subprocess
                r = subprocess.run(["xdg-user-dir", v], capture_output=True, text=True, timeout=3)
                if r.returncode == 0 and r.stdout.strip() and Path(r.stdout.strip()) != home:
                    return Path(r.stdout.strip())
            except Exception:  # noqa: BLE001
                pass
            for cand in {"DOWNLOAD": ("Загрузки", "Downloads"), "DESKTOP": ("Рабочий стол", "Desktop"), "DOCUMENTS": ("Документы", "Documents"),
                         "VIDEOS": ("Видео", "Videos"), "PICTURES": ("Изображения", "Pictures")}[v]:
                if (home / cand).is_dir():
                    return home / cand
    return Path(os.path.expanduser(n)) if n else home / "Downloads"


def folder_files(folder, pattern="*"):
    """-> {имя: размер} подходящих файлов папки (без скрытых и недокачанных)."""
    out = {}
    try:
        for e in os.scandir(folder):
            if not e.is_file() or e.name.startswith("."):
                continue
            if e.name.lower().endswith(PARTIAL):
                continue
            if pattern and pattern != "*" and not fnmatch.fnmatch(e.name.lower(), pattern.lower()):
                continue
            try:
                out[e.name] = e.stat().st_size
            except OSError:
                continue
    except OSError:
        pass
    return out


def page_text(html_text):
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", str(html_text or ""))
    t = re.sub(r"<[^>]+>", " ", t)
    import html as _h
    return re.sub(r"\s+", " ", _h.unescape(t)).strip()


def title_for(kind, what="", folder="", pattern="", url=""):
    if kind == "screen":
        return what[:80] or "что-то на экране"
    if kind == "file":
        return f"новый файл в «{Path(folder).name or folder}»" + (f" ({pattern})" if pattern and pattern != "*" else "")
    from urllib.parse import urlparse
    host = urlparse(url).netloc.removeprefix("www.")
    return (f"«{what}» на {host}" if what else f"изменения на {host}")[:80]


class Watches:
    def __init__(self, path, now=time.time):
        self.path = Path(path)
        self.now = now
        self._lock = threading.Lock()
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("items", [])
        for it in self.data["items"]:              # перезапуск: дозоры продолжаются, но экран сравниваем заново
            it.pop("sig", None)

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self.data["items"] = self.data["items"][-40:]
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:
            log.info("Дозор: не сохранить: %s", e)

    def add(self, kind, what="", every=None, hours=None, folder="", pattern="", url=""):
        if kind not in KINDS:
            raise ValueError("дозор бывает за экраном, папкой или страницей")
        what = re.sub(r"\s+", " ", str(what or "")).strip()[:200]
        if kind == "screen" and len(what) < 3:
            raise ValueError("скажите, чего ждать на экране — например: «Claude закончил и написал ответ»")
        it = {"id": uuid.uuid4().hex[:6], "kind": kind, "what": what, "created": int(self.now()), "status": "active",
              "every": max(MIN_EVERY[kind], int(every or EVERY[kind])), "until": int(self.now() + 3600 * float(hours or HOURS)),
              "last": 0, "note": "", "checks": 0, "asked": 0}
        if kind == "file":
            f = known_folder(folder or "Загрузки")
            if not f.is_dir():
                raise ValueError(f"нет такой папки: {f}")
            it.update(folder=str(f), pattern=(pattern or "*").strip() or "*", base=sorted(folder_files(f, pattern or "*")))
        if kind == "page":
            url = str(url or "").strip()
            if not re.match(r"https?://\S+$", url):
                raise ValueError("нужен адрес страницы целиком, с https://")
            it["url"] = url
        it["title"] = title_for(kind, what, it.get("folder", ""), it.get("pattern", ""), it.get("url", ""))
        with self._lock:
            self.data["items"].append(it)
        self._save()
        return dict(it)

    def get(self, wid):
        return next((x for x in self.data["items"] if x["id"] == wid), None)

    def active(self):
        return [x for x in self.data["items"] if x["status"] == "active"]

    def stop(self, wid=""):
        n = 0
        for x in self.active():
            if not wid or x["id"] == wid:
                x.update(status="stopped", done_at=int(self.now()))
                n += 1
        self._save()
        return n

    def due(self):
        """Дозоры, которым пора проверять; вышедшие сроком — закрываются (-> (пора, истекли))."""
        now, due, gone = self.now(), [], []
        for x in self.active():
            if now >= x["until"]:
                x.update(status="expired", done_at=int(now))
                gone.append(dict(x))
            elif now - x.get("last", 0) >= x["every"]:
                due.append(x)
        if gone:
            self._save()
        return due, gone

    def mark(self, x, note="", done=False, result="", failed=False):
        x.update(last=int(self.now()), checks=int(x.get("checks", 0)) + 1, note=str(note)[:200])
        if done:
            x.update(status="done", done_at=int(self.now()), result=str(result or note)[:240])
        if failed:
            x.update(status="failed", done_at=int(self.now()), result=str(result or note)[:240])
        self._save()

    # ---------- проверки без модели ----------

    def check_file(self, x):
        """-> (выполнено?, пояснение). Новый файл — когда его размер не менялся с прошлой проверки (докачался)."""
        now = folder_files(x["folder"], x.get("pattern") or "*")
        new = {n: s for n, s in now.items() if n not in set(x.get("base") or [])}
        prev = x.get("seen") or {}
        ready = [n for n, s in new.items() if prev.get(n) == s and s > 0]
        x["seen"] = new
        if ready:
            return True, "появился файл «" + ready[0] + "»" + (f" и ещё {len(ready) - 1}" if len(ready) > 1 else "")
        return False, (f"качается: {', '.join(list(new)[:2])}" if new else "новых файлов нет")

    def check_page(self, x, text):
        t = page_text(text)
        h = hashlib.sha1(t.encode("utf-8", "replace")).hexdigest()
        if x.get("what"):
            if x["what"].lower().replace("ё", "е") in t.lower().replace("ё", "е"):
                return True, f"на странице появилось «{x['what']}»"
            return False, "пока нет"
        if not x.get("base"):
            x["base"] = h
            return False, "запомнила, как страница выглядит сейчас"
        return (True, "страница изменилась") if h != x["base"] else (False, "без изменений")

    def screen_changed(self, x, sig):
        """Экран: стоит ли спрашивать модель (изменился, или первый раз, или давно не спрашивали)."""
        old = x.get("sig")
        x["sig"] = sig
        asked = x.get("asked") or 0
        return old is None or sig_diff(old, sig) >= SIG_DIFF or bool(asked and self.now() - asked >= ASK_ANYWAY)

    def public(self):
        now = self.now()
        items = []
        for x in reversed(self.data["items"][-20:]):
            items.append({k: x.get(k) for k in ("id", "kind", "what", "title", "status", "every", "until", "created", "last", "note",
                                                "checks", "done_at", "result", "folder", "pattern", "url")})
        return {"items": items, "active": len(self.active()), "now": int(now)}
