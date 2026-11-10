"""Снимки результатов задачи и откат («Большие задачи», выпуск 5, docs/HARNESS.md; как rewind у Claude Code и
checkpoints у Cline). Перед первой записью в outputs/ на шаге N (write_file, file_edit, run_python, run_shell, расшифровка)
Dewiar запоминает outputs/ — «как было перед шагом N». rewind(N) возвращает outputs/ к этому виду (отменяет шаг N и всё
после); текущий вид перед откатом тоже сохраняется — откат можно отменить.

Хранение — в папке задачи, _snap/: objects/<sha256> — содержимое файлов (одинаковое хранится один раз), <seq>.json — снимок
{seq, step, kind, why, time, files: {путь: [sha, размер, mtime_ns]}}, index.json — счётчик и до какого шага снимки уже
удалены. Пределы: не больше SNAP_MAX снимков и OBJ_MAX байт содержимого (старые уходят первыми), outputs/ больше TREE_MAX
или с файлами больше FILE_MAX — снимок не делается (честно говорим об этом в журнале).

kind: "step" — «перед шагом N» (по ним ищет rewind), "undo" — «перед откатом» (вернуть его можно по номеру снимка)."""

import datetime as dt
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

DIR = "_snap"
SNAP_MAX = int(os.environ.get("DEWIAR_SNAP_MAX") or 40)
OBJ_MAX = int(os.environ.get("DEWIAR_SNAP_BYTES") or 256 << 20)
TREE_MAX = 512 << 20                         # outputs/ больше — снимок не делаем (видео, архивы)
FILE_MAX = 200 << 20                         # один файл больше — тоже
FILES_MAX = 3000
SHA_RX = re.compile(r"[0-9a-f]{64}\Z")


class SnapError(ValueError):
    """Откатить нельзя — текст для модели и человека «что случилось — как исправить»."""


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _safe_rel(rel):
    """Путь из снимка -> части пути или None (снимок могли подменить: ни «..», ни полного пути, ни диска)."""
    if not isinstance(rel, str) or not rel or "\0" in rel or "\\" in rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        return None
    parts = rel.split("/")
    if any(x in ("", ".", "..") for x in parts):
        return None
    return parts


class Snapshots:
    def __init__(self, task_dir):
        self.root = Path(task_dir)
        self.out = self.root / "outputs"
        self.dir = self.root / DIR
        self._check()

    def _check(self):
        """_snap — ссылкой (её мог оставить код задачи: снимки писались бы через неё в домашнюю папку) — убрать; папка
        снимков, ведущая из папки задачи, — отказ (B2, рецензия выпуска 5)."""
        if self.dir.is_symlink():
            self.dir.unlink()
        for d in (self.dir, self.dir / "objects"):
            if d.is_symlink():
                d.unlink()
        if self.dir.exists():
            r, root = os.path.realpath(self.dir), os.path.realpath(self.root)
            if not r.startswith(root.rstrip(os.sep) + os.sep):
                raise SnapError("папка снимков ведёт за пределы папки задачи — снимки выключены")

    # ---------- чтение ----------
    def _index(self):
        try:
            d = json.loads((self.dir / "index.json").read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _put_index(self, d):
        tmp = self.dir / "index.json.tmp"
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.dir / "index.json")

    def all(self):
        """Снимки по порядку (старые первыми): [{seq, step, kind, why, time, files}]."""
        out = []
        if not self.dir.is_dir():
            return out
        for f in self.dir.glob("*.json"):
            if not f.stem.isdigit():
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(d, dict) and isinstance(d.get("files"), dict):
                out.append(d)
        return sorted(out, key=lambda d: int(d.get("seq") or 0))

    def listing(self):
        """Для студии и модели: новые первыми — {seq, step, kind, why, time, files: число, bytes}."""
        return [{"seq": d["seq"], "step": d.get("step"), "kind": d.get("kind"), "why": d.get("why", ""), "time": d.get("time", ""),
                 "files": len(d["files"]), "bytes": sum(int(v[1]) for v in d["files"].values())} for d in reversed(self.all())]

    # ---------- снимок ----------
    def _scan(self, prev):
        """outputs/ -> {путь: [sha, размер, mtime_ns]} (без перехода по ссылкам) или текст, почему снимка не будет.
        Хэш считается заново только у изменившихся файлов (размер и время — как в прошлом снимке)."""
        files, total = {}, 0
        if self.out.is_symlink():
            self.out.unlink()                           # outputs/ ссылкой — тоже работа кода задачи
        if not self.out.is_dir():
            return files
        for dp, dns, fns in os.walk(self.out, followlinks=False):
            for fn in fns:
                p = Path(dp) / fn
                if p.is_symlink() or not p.is_file():
                    continue
                rel = p.relative_to(self.out).as_posix()
                st = p.stat()
                if st.st_size > FILE_MAX:
                    return f"файл outputs/{rel} больше {FILE_MAX >> 20} МБ"
                total += st.st_size
                if total > TREE_MAX:
                    return f"outputs/ больше {TREE_MAX >> 20} МБ"
                if len(files) >= FILES_MAX:
                    return f"в outputs/ больше {FILES_MAX} файлов"
                old = prev.get(rel)
                sha = old[0] if old and old[1] == st.st_size and old[2] == st.st_mtime_ns else _sha(p)
                files[rel] = [sha, st.st_size, st.st_mtime_ns]
        return files

    def _store(self, files):
        objs = self.dir / "objects"
        self._check()
        for rel, (sha, _size, _mt) in files.items():
            dst = objs / sha[:2] / sha
            if dst.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(sha + ".tmp")
            shutil.copyfile(self.out / rel, tmp)
            if _sha(tmp) != sha:                        # файл меняли, пока копировали, — возьмём, что скопировалось
                real = _sha(tmp)
                files[rel][0] = real
                dst = objs / real[:2] / real
                dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, dst)

    def has_step(self, step):
        return any(d.get("kind") == "step" and d.get("step") == step for d in self.all())

    def take(self, step, why, kind="step", prune=True):
        """Запомнить outputs/. kind="step" — один раз на шаг (перед первой записью шага). -> (seq | None, текст-причина,
        если снимка нет). prune=False — пределы потом (откат: снимок, к которому идём, не должен уйти раньше времени)."""
        snaps = self.all()
        if kind == "step" and any(d.get("kind") == "step" and d.get("step") == step for d in snaps):
            return None, ""
        prev = snaps[-1]["files"] if snaps else {}
        files = self._scan(prev)
        if isinstance(files, str):
            return None, files
        self.dir.mkdir(parents=True, exist_ok=True)
        self._store(files)
        idx = self._index()
        seq = int(idx.get("seq") or (snaps[-1]["seq"] if snaps else 0)) + 1
        idx["seq"] = seq
        d = {"seq": seq, "step": int(step), "kind": kind, "why": str(why or "")[:200],
             "time": dt.datetime.now().isoformat(timespec="seconds"), "files": files}
        tmp = self.dir / f"{seq}.json.tmp"
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.dir / f"{seq}.json")
        self._put_index(idx)
        if prune:
            self._prune()
        return seq, ""

    def _prune(self):
        """Не больше SNAP_MAX снимков и OBJ_MAX байт содержимого: старые уходят, недостижимое содержимое удаляется."""
        snaps = self.all()
        idx = self._index()
        size = lambda ss: sum(v[1] for v in {v[0]: v for d in ss for v in d["files"].values()}.values())  # noqa: E731
        drop = []
        while len(snaps) > SNAP_MAX or (len(snaps) > 1 and size(snaps) > OBJ_MAX):
            d = snaps.pop(0)
            drop.append(d)
        for d in drop:
            if d.get("kind") == "step":
                idx["pruned"] = max(int(idx.get("pruned") or 0), int(d.get("step") or 0))
            (self.dir / f"{d['seq']}.json").unlink(missing_ok=True)
        if drop:
            self._put_index(idx)
        keep = {v[0] for d in snaps for v in d["files"].values()}
        objs = self.dir / "objects"
        if objs.is_dir():
            for sub in objs.iterdir():
                for f in sub.iterdir() if sub.is_dir() else []:
                    if f.name not in keep:
                        f.unlink(missing_ok=True)

    # ---------- откат ----------
    def find(self, step=None, seq=None):
        """Снимок для отката: seq — по номеру; step — «как перед шагом N»: первый снимок «перед шагом» с шагом ≥ N (шаги
        между ними outputs/ не меняли). Нет — SnapError с объяснением; None — с шага N outputs/ не менялся."""
        snaps = self.all()
        if seq is not None:
            for d in snaps:
                if int(d["seq"]) == int(seq):
                    return d
            raise SnapError(f"снимка №{seq} нет. Как исправить: посмотри список снимков (rewind без step)")
        step = int(step)
        pruned = int(self._index().get("pruned") or 0)
        if step <= pruned:
            first = min((d["step"] for d in snaps if d.get("kind") == "step"), default=None)
            raise SnapError(f"снимок перед шагом {step} уже удалён (снимков храню не больше {SNAP_MAX} и не больше "
                            f"{OBJ_MAX >> 20} МБ)"
                            + (f"; самый ранний — перед шагом {first}" if first else "") + ". Как исправить: откати к более позднему шагу")
        for d in snaps:
            if d.get("kind") == "step" and int(d["step"]) >= step:
                return d
        return None

    def restore(self, d):
        """Вернуть outputs/ к снимку d: лишнее удалить, остальное переписать из _snap/objects. -> (файлов, удалено)."""
        objs = self.dir / "objects"
        plan = {}
        for rel, v in d["files"].items():
            parts = _safe_rel(rel)
            sha = str(v[0]) if isinstance(v, list) and v else ""
            if parts is None or not SHA_RX.match(sha):
                raise SnapError(f"снимок №{d.get('seq')} испорчен ({rel!r}) — откатить по нему нельзя")
            src = objs / sha[:2] / sha
            if not src.is_file():
                raise SnapError(f"в снимке №{d.get('seq')} нет содержимого файла {rel} — откатить по нему нельзя")
            plan["/".join(parts)] = src
        if self.out.is_symlink() or (self.out.exists() and not self.out.is_dir()):
            self.out.unlink()
        self.out.mkdir(exist_ok=True)
        removed = 0
        for dp, dns, fns in os.walk(self.out, topdown=False, followlinks=False):
            for fn in fns + [x for x in dns if (Path(dp) / x).is_symlink()]:
                p = Path(dp) / fn
                rel = p.relative_to(self.out).as_posix()
                if p.is_symlink() or rel not in plan:
                    p.unlink()
                    removed += 1
            for x in dns:
                q = Path(dp) / x
                if q.is_dir() and not q.is_symlink():
                    try:
                        q.rmdir()                       # пустые папки уходят; непустые (там файлы из снимка) остаются
                    except OSError:
                        pass
        base = self.out.resolve()
        for rel, src in plan.items():
            dst = self.out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if base not in dst.parent.resolve().parents and dst.parent.resolve() != base:
                raise SnapError(f"путь {rel} ведёт из outputs/ — откат остановлен")
            if dst.is_file() and not dst.is_symlink() and dst.stat().st_size == src.stat().st_size and _sha(dst) == src.name:
                continue
            tmp = dst.with_name(dst.name + ".rewind.tmp")
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
        return len(plan), removed

    def rewind(self, now_step, step=None, seq=None):
        """Откатить outputs/ (step — «как перед шагом N», seq — к снимку №) и сохранить текущий вид снимком «перед
        откатом» -> текст для журнала и модели. Ничего не менялось — текст «нечего откатывать»."""
        d = self.find(step, seq)
        if d is None:
            return f"С шага {step} outputs/ не менялся — откатывать нечего."
        cur, why = self.take(now_step, f"перед откатом к {'шагу ' + str(d['step']) if seq is None else 'снимку №' + str(d['seq'])}",
                             kind="undo", prune=False)
        try:
            n, removed = self.restore(d)
        finally:
            self._prune()
        what = f"как перед шагом {d['step']}" if d.get("kind") == "step" else f"как в снимке №{d['seq']}"
        return (f"outputs/ — {what}: файлов {n}" + (f", убрано лишних {removed}" if removed else "") + "."
                + (f" Прежний вид сохранён (снимок №{cur}) — откат можно отменить." if cur else f" Прежний вид не сохранён: {why}."))
