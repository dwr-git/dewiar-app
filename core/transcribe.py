"""«Расшифровка» — плагин (владелец: «ОЧЕНЬ КРУТО, НУЖНО ДЕЛАТЬ»; 18.11: «не должен быть сложным, уже можно закрыть»).

Аудио или видео (созвон, лекция, интервью, голосовое) -> текст с метками времени, субтитры .srt и список всех расшифровок
с поиском по тексту. Распознаёт ядро тем же «слухом», что и голос (engine_brain.transcribe_file: куски по тихим местам,
запасной Vosk), — всё на этом компьютере, в облако звук не уходит (кроме случая, когда сам «слух» — сервер).

Отдельный контур: включается только вместе с плагином «Расшифровка» (data/plugins/transcribe), раздела в меню нет —
вкладка «Расшифровки» на странице плагина (ui/studio/transcribe.js) и два действия модели (modules.py, id «transcribe»):
  transcribe   — начать расшифровку файла; готово — Лира скажет сама;
  transcripts  — список, поиск по тексту («где говорили про сроки») или текст одной записи (для выжимки и вопросов).

Хранение — STATE_DIR/transcripts/<id>.json {id, name, src, at, dur, state, segs: [[начало, конец, текст]], err};
готовый текст и субтитры — ещё и в «Мои файлы» → «Расшифровки» (<имя>.txt и <имя>.srt), чтобы их можно было открыть,
переслать и чтобы Лира находила их обычным поиском по файлам. Одновременно идёт одна расшифровка, остальные ждут
(слух один, и большой файл не должен мешать голосу)."""

import json
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger("dewiar.transcribe")
PLUGIN = "transcribe"
EXT = {".mp3", ".wav", ".m4a", ".ogg", ".oga", ".opus", ".flac", ".aac", ".wma", ".amr", ".webm",
       ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts"}
FOLDER = "Расшифровки"
READ_MAX = 60_000            # текст одной записи модели — до 60 тыс. знаков (дальше — «…» и путь к файлу)


def ts(x, srt=False):
    """секунды -> «мм:сс» / «ч:мм:сс» или «00:00:00,000» для .srt"""
    x = max(0.0, float(x))
    h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return f"{h}:{m:02d}:{int(s):02d}" if h else f"{m:02d}:{int(s):02d}"


def as_text(segs):
    return "\n".join(f"[{ts(a)}] {t}" for a, b, t in segs)


def as_srt(segs):
    return "\n".join(f"{i}\n{ts(a, True)} --> {ts(b, True)}\n{t}\n" for i, (a, b, t) in enumerate(segs, 1))


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").lower().replace("ё", "е")).strip()


def _safe_name(s):
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", str(s or "")).strip(" .")
    return re.sub(r"\s+", " ", s)[:80] or "Запись"


class Transcripts:
    def __init__(self, host, root=None):
        from settings import STATE_DIR
        self.h = host
        self.dir = Path(root or (STATE_DIR / "transcripts"))
        self._lock = threading.Lock()
        self.queue = []                  # id, ждущие очереди
        self.cur = None                  # id идущей
        self.cancel = {}                 # id -> threading.Event
        self.prog = {}                   # id -> (сделано_с, всего_с)
        self._worker = None

    # ---------- плагин включён? ----------
    def on(self):
        p = getattr(self.h, "plugins", None)
        try:
            return bool(p and any(x.get("id") == PLUGIN for x in p.installed()))
        except Exception:  # noqa: BLE001
            return False

    def _need_on(self):
        if not self.on():
            raise ValueError("включите плагин «Расшифровка» — «Плагины» → «Расшифровка»")

    # ---------- хранение ----------
    def _path(self, tid):
        if not re.fullmatch(r"[0-9a-f]{10}", str(tid or "")):
            raise ValueError("нет такой расшифровки")
        return self.dir / f"{tid}.json"

    def _load(self, tid):
        p = self._path(tid)
        if not p.is_file():
            raise ValueError("нет такой расшифровки")
        return json.loads(p.read_text(encoding="utf-8"))

    def _save(self, x):
        import atomicio
        self.dir.mkdir(parents=True, exist_ok=True)
        atomicio.write_text(self._path(x["id"]), json.dumps(x, ensure_ascii=False), mode=0o600)

    def _all(self):
        out = []
        if self.dir.is_dir():
            for p in self.dir.glob("*.json"):
                try:
                    out.append(json.loads(p.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    continue
        return sorted(out, key=lambda x: -float(x.get("at") or 0))

    def _pub(self, x, full=False):
        segs = x.get("segs") or []
        d = {k: x.get(k) for k in ("id", "name", "src", "at", "dur", "state", "err", "files")}
        d["n"] = len(segs)
        d["words"] = sum(len(t.split()) for _, _, t in segs)
        d["preview"] = " ".join(t for _, _, t in segs[:3])[:220]
        if x["id"] == self.cur and x["id"] in self.prog:
            done, total = self.prog[x["id"]]
            d["pct"] = int(min(99, done / total * 100)) if total else 0
        if x.get("state") == "wait" and x["id"] in self.queue:
            d["place"] = self.queue.index(x["id"]) + 1
        if full:
            d["segs"] = segs
        return d

    # ---------- команды ----------
    def start(self, path, name="", voice=False):
        """Поставить файл в очередь (voice — попросили голосом: готово — Лира скажет вслух). -> запись (state wait|run)."""
        self._need_on()
        p = Path(os.path.expanduser(str(path or "").strip().strip('"')))
        if not p.is_file():
            raise ValueError("файл не найден — выберите его ещё раз")
        if p.suffix.lower() not in EXT:
            raise ValueError("это не аудио и не видео: подойдут mp3, wav, m4a, ogg, mp4, mov, mkv и другие")
        x = {"id": uuid.uuid4().hex[:10], "name": _safe_name(name or p.stem), "src": str(p), "at": time.time(), "dur": 0,
             "state": "wait", "segs": [], "err": "", "voice": bool(voice)}
        with self._lock:
            self._save(x)
            self.queue.append(x["id"])
            self.cancel[x["id"]] = threading.Event()
            if not (self._worker and self._worker.is_alive()):
                self._worker = threading.Thread(target=self._run, daemon=True, name="transcribe")
                self._worker.start()
        self._emit(x)
        return self._pub(x)

    def upload(self, name, b64):
        """Небольшой файл со страницы (перетащили; путь страница не знает) -> копия в STATE_DIR/transcripts/files, расшифровка."""
        import base64
        self._need_on()
        nm = _safe_name(Path(str(name or "")).name)
        if Path(nm).suffix.lower() not in EXT:
            raise ValueError("это не аудио и не видео")
        raw = base64.b64decode(str(b64 or "").split(",", 1)[-1] or b"", validate=False)
        if not raw or len(raw) > 40 << 20:
            raise ValueError("файл пустой или слишком большой — выберите его кнопкой «Выбрать файл»")
        d = self.dir / "files"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{uuid.uuid4().hex[:6]}-{nm}"
        p.write_bytes(raw)
        return self.start(p, Path(nm).stem)

    def list(self, q=""):
        """Все расшифровки (новые сверху); q — найти слова в тексте: -> {items, hits: [{id, name, at_s, t, text}]}"""
        items = self._all()
        out = {"items": [self._pub(x) for x in items], "on": self.on()}
        qn = _norm(q)
        if qn:
            words = qn.split()
            hits = []
            for x in items:
                segs = x.get("segs") or []
                for i, (a, b, t) in enumerate(segs):
                    win = _norm(" ".join(s[2] for s in segs[max(0, i - 1):i + 2]))
                    if all(w in win for w in words) and any(w in _norm(t) for w in words):
                        hits.append({"id": x["id"], "name": x["name"], "at_s": a, "t": ts(a), "text": t})
                        if len(hits) >= 60:
                            break
            out["hits"] = hits
            out["items"] = [self._pub(x) for x in items if qn in _norm(x.get("name")) or any(h["id"] == x["id"] for h in hits)]
        return out

    def get(self, tid):
        return self._pub(self._load(tid), full=True)

    def stop(self, tid):
        ev = self.cancel.get(tid)
        if ev:
            ev.set()
        with self._lock:
            if tid in self.queue:
                self.queue.remove(tid)
                x = self._load(tid)
                x.update(state="stop", err="остановлено")
                self._save(x)
                self._emit(x)
        return self.list()

    def delete(self, tid):
        self.stop(tid)
        p = self._path(tid)
        if p.is_file():
            p.unlink()
        self.h.emit("transcribe", id=tid, gone=True)
        return self.list()

    def rename(self, tid, name):
        x = self._load(tid)
        x["name"] = _safe_name(name)
        self._save(x)
        self._emit(x)
        return self._pub(x)

    def text(self, tid, fmt="txt"):
        x = self._load(tid)
        segs = x.get("segs") or []
        return as_srt(segs) if fmt == "srt" else as_text(segs)

    # ---------- работа ----------
    def _emit(self, x):
        try:
            self.h.emit("transcribe", item=self._pub(x))
        except Exception:  # noqa: BLE001
            pass

    def _run(self):
        while True:
            with self._lock:
                if not self.queue:
                    self.cur = None
                    return
                tid = self.queue.pop(0)
                self.cur = tid
            try:
                x = self._load(tid)
            except (ValueError, OSError):
                continue
            ev = self.cancel.get(tid) or threading.Event()
            x["state"] = "run"
            self._save(x)
            self._emit(x)
            last = [0.0]

            def prog(done, total, x=x):
                self.prog[x["id"]] = (done, total)
                x["dur"] = round(total, 1)
                if time.monotonic() - last[0] > 1.5:
                    last[0] = time.monotonic()
                    self._emit(x)
            try:
                segs = self.h.transcribe_file(x["src"], cancel=ev, progress=prog)
                x["segs"] = [[round(a, 2), round(b, 2), t] for a, b, t in segs]
                x["state"] = "stop" if ev.is_set() else "done"
                x["err"] = "остановлено — сохранено, что успела" if ev.is_set() else ("" if segs else "речи в записи не нашлось")
                if segs:
                    x["files"] = self._export(x)
            except Exception as e:  # noqa: BLE001
                log.warning("Расшифровка «%s»: %s", x.get("name"), e)
                x.update(state="err", err=str(e)[:300])
            self.prog.pop(tid, None)
            self.cancel.pop(tid, None)
            self._save(x)
            self._emit(x)
            if x["state"] == "done" and x.get("voice"):
                self._tell(x)                    # просили голосом — Лира скажет сама; из студии — студия покажет сама

    def _export(self, x):
        """Текст и субтитры — в «Мои файлы» → «Расшифровки». -> ["Расшифровки/имя.txt", "…srt"]"""
        ws = getattr(self.h, "workspace", None)
        if ws is None:
            return []
        try:
            d = ws.root / FOLDER
            d.mkdir(parents=True, exist_ok=True)
            stem, n = x["name"], 1
            while (d / f"{stem}.txt").exists() and not self._ours(d / f"{stem}.txt", x["id"]):
                n += 1
                stem = f"{x['name']} ({n})"
            head = f"{x['name']}\nИсточник: {Path(x['src']).name} · Расшифровано Лирой {time.strftime('%d.%m.%Y %H:%M')} · id {x['id']}\n\n"
            (d / f"{stem}.txt").write_text(head + as_text(x["segs"]) + "\n", encoding="utf-8")
            (d / f"{stem}.srt").write_text(as_srt(x["segs"]), encoding="utf-8")
            return [f"{FOLDER}/{stem}.txt", f"{FOLDER}/{stem}.srt"]
        except OSError as e:
            log.warning("Расшифровка: не сохранилось в «Мои файлы»: %s", e)
            return []

    @staticmethod
    def _ours(p, tid):
        try:
            return f"id {tid}" in p.read_text(encoding="utf-8")[:400]
        except OSError:
            return False

    def _tell(self, x):
        mins = max(1, round(float(x.get("dur") or 0) / 60))
        try:
            self.h.announce(f"Расшифровала «{x['name']}» — {mins} мин. Текст и субтитры — в «Мои файлы», папка «{FOLDER}». "
                            "Можно спросить меня, о чём там говорили.", tag="transcribe")
        except Exception:  # noqa: BLE001
            pass

    # ---------- для модели ----------
    def tool_start(self, path, name="", voice=True):
        ws = getattr(self.h, "workspace", None)
        p = Path(os.path.expanduser(str(path or "").strip().strip('"')))
        if not p.is_absolute() and ws is not None:
            for c in (ws.root / p, ws.root / "Входящие" / p):
                if c.is_file():
                    p = c
                    break
        r = self.start(p, name, voice=voice)
        ahead = len(self.queue) - 1 if r["id"] in self.queue else 0
        return (f"Начала расшифровку «{r['name']}»" + (f" (в очереди после ещё {ahead})" if ahead > 0 else "")
                + ". Когда закончу — скажу; текст будет в «Мои файлы» → «Расшифровки» и на странице плагина «Расшифровка».")

    def tool_find(self, q="", tid="", name=""):
        if tid or name:
            x = None
            if tid:
                x = self._load(tid)
            else:
                nn = _norm(name)
                x = next((y for y in self._all() if nn and nn in _norm(y.get("name"))), None)
                if x is None:
                    return json.dumps({"error": f"расшифровки «{name}» нет", "items": [y["name"] for y in self._all()][:20]}, ensure_ascii=False)
            body = as_text(x.get("segs") or [])
            more = len(body) > READ_MAX
            return json.dumps({"name": x["name"], "state": x.get("state"), "dur_min": round(float(x.get("dur") or 0) / 60, 1),
                               "files": x.get("files") or [], "text": body[:READ_MAX] + ("\n…(дальше — в файле)" if more else "")},
                              ensure_ascii=False)
        r = self.list(q)
        if q:
            return json.dumps({"hits": r.get("hits", [])[:40], "items": [{"id": i["id"], "name": i["name"]} for i in r["items"][:20]]},
                              ensure_ascii=False)
        return json.dumps({"items": [{k: i.get(k) for k in ("id", "name", "state", "dur", "n", "pct", "err")} for i in r["items"][:30]]},
                          ensure_ascii=False)


# ---------- команды окон (студия → страница плагина «Расшифровка», вкладка «Расшифровки») ----------
def command(T, cmd, a):
    """transcribe_start {path, name} · transcribe_list {q} · transcribe_get {id} · transcribe_text {id, fmt} ·
    transcribe_stop {id} · transcribe_del {id} · transcribe_rename {id, name}. Не своя — NotImplemented."""
    if cmd == "transcribe_start":
        return T.start(a.get("path", ""), a.get("name", ""))
    if cmd == "transcribe_upload":                          # перетащили небольшой файл (до 11 МБ) — копия у нас
        return T.upload(a.get("name", ""), a.get("b64", ""))
    if cmd == "transcribe_list":
        return T.list(a.get("q", ""))
    if cmd == "transcribe_get":
        return T.get(a.get("id", ""))
    if cmd == "transcribe_text":
        return {"text": T.text(a.get("id", ""), a.get("fmt", "txt"))}
    if cmd == "transcribe_stop":
        return T.stop(a.get("id", ""))
    if cmd == "transcribe_del":
        return T.delete(a.get("id", ""))
    if cmd == "transcribe_rename":
        return T.rename(a.get("id", ""), a.get("name", ""))
    return NotImplemented
