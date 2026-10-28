"""«Пишу» (0.68; отзыв писателя 28.10 и план владельца: «Документы» — и для своих текстов): сколько человек написал
сегодня, за неделю и подряд дней — по его же файлам в папках «Документов» (то, что он пишет в своём редакторе: .md, .txt,
.docx, .odt, .html). PDF и таблицы не считаются: их не пишут, а читают.

Как считаем: раз в 10 минут (и когда открыли студию или спросили голосом) проходим по папкам, у изменившихся файлов (по
времени и размеру) пересчитываем слова. В начале дня запоминаем, сколько слов было в каждом файле, — «написано сегодня» =
сумма приростов по файлам (стёрли больше, чем дописали, — у этого файла ноль, а не минус). Новый файл, созданный сегодня, —
с нуля; файл, который мы видим впервые, но он старый, — не прибавка. Сам текст никуда не уходит и не хранится: только
числа слов. Состояние — STATE_DIR/writing.json.
"""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("dewiar.writing")
EXTS = {".md", ".txt", ".docx", ".odt", ".html", ".htm"}
MAX_FILES, MAX_SIZE = 3000, 8 * 1024 * 1024
WORD = re.compile(r"[^\W\d_](?:[\w’'-]*\w)?", re.U)
STREAK_MIN = 50                     # слов за день, чтобы день считался «писал»


def count_words(text):
    t = re.sub(r"(?s)^---\n.*?\n---\n", "", text or "")            # заголовок Obsidian / Jekyll — не текст
    t = re.sub(r"!?\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", t)          # [[ссылка|подпись]] — только подпись
    t = re.sub(r"\]\([^)]*\)", "]", t)                              # [текст](адрес) — без адреса
    return len(WORD.findall(t))


def _plural(n, one, few, many):
    n = abs(int(n))
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def words_ru(n):
    return f"{n:,}".replace(",", " ") + " " + _plural(n, "слово", "слова", "слов")


class Writing:
    def __init__(self, folders, path, extract=None, walk=None):
        """folders() -> список папок «Документов»; extract(Path) -> текст (knowledge.extract); walk(folder) -> ([Path], урезано)."""
        self.folders, self.path = folders, Path(path)
        self._extract = extract
        self._walk = walk
        self._lock = threading.Lock()
        self.last = 0.0
        try:
            self.d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.d = {}
        for k, v in (("files", {}), ("base", {}), ("days", {}), ("touched", {}), ("goal", 0)):
            self.d.setdefault(k, v)

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.d, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:
            log.info("«Пишу»: не сохранилось: %s", e)

    def _files(self):
        """-> [(папка, файл)]."""
        out = []
        for f in self.folders() or []:
            p = Path(os.path.expanduser(str(f)))
            if not p.is_dir():
                continue
            if self._walk:
                got, _ = self._walk(p)
            else:
                got = [Path(dp) / n for dp, dn, fn in os.walk(p) for n in fn]
            out += [(str(p), x) for x in got if x.suffix.lower() in EXTS and not x.name.startswith((".", "~$"))]
            if len(out) >= MAX_FILES:
                break
        return out[:MAX_FILES]

    def _words(self, p):
        if self._extract:
            return count_words(self._extract(p))
        return count_words(p.read_text(encoding="utf-8", errors="replace"))

    def scan(self, now=None):
        """Пройти по папкам и пересчитать сегодняшнее. -> summary()."""
        now = now or time.time()
        today = datetime.fromtimestamp(now).date().isoformat()
        day0 = datetime.combine(datetime.fromtimestamp(now).date(), datetime.min.time()).timestamp()
        with self._lock:
            files = self.d["files"]
            got = self._files()
            known = set(self.d.get("roots") or [])        # папку только что добавили — её файлы не «написаны сегодня»
            seen = {}
            for root, p in got:
                k = str(p)
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size > MAX_SIZE:
                    continue
                old = files.get(k)
                if old and old.get("m") == st.st_mtime and old.get("s") == st.st_size:
                    seen[k] = old
                    continue
                try:
                    w = self._words(p)
                except Exception as e:  # noqa: BLE001 — битый docx и т.п.: пропускаем файл, а не весь подсчёт
                    log.debug("«Пишу»: %s — %s", p.name, e)
                    continue
                seen[k] = {"m": st.st_mtime, "s": st.st_size, "w": w,
                           "new": (old is None and root in known and getattr(st, "st_birthtime", st.st_ctime) >= day0)}
            self.d["files"] = seen
            self.d["roots"] = sorted({r for r, _ in got} | {str(Path(os.path.expanduser(str(f)))) for f in self.folders() or []})
            base = self.d["base"]
            if base.get("d") != today:                          # новый день: точка отсчёта — то, что есть сейчас
                base = self.d["base"] = {"d": today, "w": {k: v["w"] for k, v in seen.items()}}
            for k, v in seen.items():
                if k not in base["w"]:                         # файл появился за день: созданный сегодня — с нуля
                    base["w"][k] = 0 if v.get("new") else v["w"]
            gain = {k: v["w"] - base["w"].get(k, v["w"]) for k, v in seen.items()}
            touched = {Path(k).name: n for k, n in gain.items() if n > 0}
            self.d["days"][today] = sum(touched.values())
            self.d["touched"] = {today: dict(sorted(touched.items(), key=lambda x: -x[1])[:8])}
            cut = (datetime.fromtimestamp(now).date() - timedelta(days=400)).isoformat()
            self.d["days"] = {k: v for k, v in self.d["days"].items() if k >= cut}
            self.last = time.monotonic()
            self._save()
        return self.summary(now)

    def maybe_scan(self, every=60):
        if time.monotonic() - self.last > every:
            try:
                return self.scan()
            except Exception:  # noqa: BLE001
                log.exception("«Пишу»: подсчёт")
        return self.summary()

    def set_goal(self, n):
        with self._lock:
            self.d["goal"] = max(0, min(100000, int(n or 0)))
            self._save()
        return self.summary()

    def summary(self, now=None):
        dt = datetime.fromtimestamp(now or time.time()).date()
        days = self.d["days"]
        last14 = [{"d": (dt - timedelta(days=i)).isoformat(), "n": int(days.get((dt - timedelta(days=i)).isoformat(), 0))} for i in range(13, -1, -1)]
        week = sum(x["n"] for x in last14[-7:])
        streak, i = 0, 0 if days.get(dt.isoformat(), 0) >= STREAK_MIN else 1
        while days.get((dt - timedelta(days=i)).isoformat(), 0) >= STREAK_MIN:
            streak += 1
            i += 1
        return {"today": int(days.get(dt.isoformat(), 0)), "goal": int(self.d.get("goal") or 0), "week": week, "streak": streak,
                "days": last14, "files": len(self.d["files"]), "total": sum(v["w"] for v in self.d["files"].values()),
                "touched": [{"name": k, "n": v} for k, v in (self.d["touched"].get(dt.isoformat()) or {}).items()],
                "best": max(days.values()) if days else 0}

    def text(self):
        """Для модели — сводка словами."""
        s = self.maybe_scan(30)
        if not s["files"]:
            return ("Своих текстов в папках «Документов» не нашлось. Скажи: пусть добавит папку с рукописью в студии → «Документы» "
                    "(считаются .md, .txt, .docx, .odt, .html) — тогда Лира будет считать, сколько написано за день.")
        parts = [f"Сегодня написано {words_ru(s['today'])}" + (f" из цели {words_ru(s['goal'])}" if s["goal"] else "") + "."]
        if s["touched"]:
            parts.append("Больше всего — в " + ", ".join(f"«{t['name']}» (+{t['n']})" for t in s["touched"][:3]) + ".")
        parts.append(f"За 7 дней — {words_ru(s['week'])}.")
        if s["streak"] >= 2:
            parts.append(f"Пишет {s['streak']} {_plural(s['streak'], 'день', 'дня', 'дней')} подряд.")
        parts.append(f"Всего в своих текстах — {words_ru(s['total'])} в {s['files']} файлах.")
        return " ".join(parts) + " Скажи это коротко и тепло, без списка; если до цели немного — подбодри."

