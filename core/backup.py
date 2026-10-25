"""Резервная копия всего, что ассистент знает и умеет: папка настроек (персонажи с фото, навыки, календарь, Telegram…),
часть STATE_DIR (напоминания, знания, отпечатки голоса) и рабочая папка (заметки, дневник, «Обо мне», финансы,
результаты задач). Модели и голоса не входят — они скачаются заново.

Файл «Dewiar — копия ГГГГ-ММ-ДД ЧЧ-ММ.dwbak»: строка HEAD, описание (JSON в одну строку) и zip — открытый или
зашифрованный паролем (crypt.seal_pw). Без пароля в копию не попадают сейф, ключи серверов (ssh/) и никакие ключи,
токены и пароли из JSON-настроек (scrub) — открыто их хранить нельзя; при восстановлении остаются те, что уже есть
на компьютере (keep_secrets). С паролем попадает всё, кроме CONFIG_SKIP (ключ сейфа и токен — привязаны к компьютеру).
Восстановление ничего не удаляет: файлы из копии заменяют одноимённые, а перед этим делается копия текущего состояния.

«Слепок знаний» (0.45.2, владелец: «одним нажатием выгрузить всё одним файлом… чтобы я был уверен, что у меня лежат
бэкапы и можно восстановить без перетирания данных»): закрытый — тот же формат, расширение «.dwr» (старые «.dwbak»
читаются как прежде); открытый — обычный «.zip» без шапки: заметки Markdown, данные JSON, README.txt и manifest.json —
откроется любой программой и через 20 лет; ключей и паролей в нём нет. Восстановление — два способа: replace (как было
всегда) и merge — «Добавить недостающее»: своего не трогаем, чего нет — добавляем, списки с id в JSON дополняем,
заметки, что отличаются, кладём рядом копией «(из слепка ДД.ММ)». Пароль закрытого слепка можно запомнить на этом
компьютере (snapshot.pw — запечатан ключом компьютера, в слепок не попадает); тогда и автокопия — закрытая, с сейфом."""

import io
import json
import logging
import os
import re
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from crypt import CryptError, seal_pw, unseal_pw

log = logging.getLogger("dewiar.backup")
HEAD = b"DEWIAR-BACKUP 1\n"            # 1 — версия формата файла копии
EXT = ".dwbak"                       # старые копии (до 0.45.2) — только читаем
EXT_DWR = ".dwr"                     # закрытый слепок
EXTS = (".dwr", ".dwbak", ".zip")
README = """Слепок знаний Dewiar — открытый формат ({time}, Dewiar {version})

Это обычный zip-архив. Его можно открыть любой программой, даже если Dewiar больше нет.

  workspace/   — заметки (Markdown, .md: их читают Obsidian, Typora, любой текстовый редактор), дневник, файлы
  config/      — платежи (payments.json), персонажи (personas/), календарь, настройки — в формате JSON
  state/       — напоминания (reminders.json) и прочее — JSON
  manifest.json — что это за слепок

Паролей, ключей и сейфа паролей здесь нет — они только в закрытом слепке (.dwr) под паролем.
Восстановить: Dewiar → «Главная» → «Слепок знаний» → «Восстановить…» и выберите этот файл.
"""
STATE_FILES = ["reminders.json", "reminders-log.json", "knowledge.json", "radio.json"]
STATE_DIRS = ["voiceprints"]
CONFIG_SKIP = {"token", "vault.key", "vault.bin", "snapshot.pw"}   # не копируем и не восстанавливаем: сейф идёт отдельно (vault.json)
WS_SKIP_DIRS = {"рабочая копия", "_run", "_guard", ".git", "__pycache__", "node_modules", ".venv", "venv", ".trash", ".obsidian"}
BIG = 100 << 20                     # файлы больше 100 МБ (видео в задачах) не копируем
SECRET_DIRS = ("ssh/",)             # ключи серверов — только в копию с паролем
SECRET_RX = re.compile(r"(?:^|_)(?:api_?key|key|token|secret|password|passwd|pass|pwd|cookie|session|authorization|"
                       r"private_?key|access_?token|refresh_?token|client_?secret|bearer|proxy)$", re.I)


def scrub(obj):
    """Копия без пароля: убрать из настроек ключи, токены и пароли (в любом JSON-файле, на любой глубине).
    Секрет узнаётся по имени поля (SECRET_RX) и непустому строковому значению."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if not (isinstance(v, str) and v and SECRET_RX.search(str(k)))}
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    return obj


def keep_secrets(new, old):
    """Восстановили копию без ключей — ключи этого компьютера остаются на месте (там, где в копии пусто).
    Списки сопоставляются по позициям, только если длина совпала: иначе не понять, чей ключ чей."""
    if isinstance(new, dict) and isinstance(old, dict):
        out = dict(new)
        for k, ov in old.items():
            nv = new.get(k)
            if isinstance(ov, str) and ov and SECRET_RX.search(str(k)) and not nv:
                out[k] = ov
            elif k in new and isinstance(nv, (dict, list)):
                out[k] = keep_secrets(nv, ov)
        return out
    if isinstance(new, list) and isinstance(old, list) and len(new) == len(old):
        return [keep_secrets(a, b) for a, b in zip(new, old)]
    return new


class BackupError(Exception):
    pass


def documents_dir():
    """Папка «Документы»: в Windows — известная папка (бывает перенесена в OneDrive), в Linux — по xdg-user-dir."""
    if os.name == "nt":
        try:
            import winsys
            return winsys.known_folder("Documents")
        except Exception:  # noqa: BLE001
            return Path.home() / "Documents"
    try:
        d = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True, timeout=3).stdout.strip()
        if d and Path(d).is_dir() and Path(d) != Path.home():
            return Path(d)
    except (OSError, subprocess.SubprocessError):
        pass
    for n in ("Документы", "Documents"):
        if (Path.home() / n).is_dir():
            return Path.home() / n
    return Path.home()


def default_dir():
    return documents_dir() / "Dewiar — копии"


def _walk(root, skip_dirs=()):
    """Файлы для копии: без skip_dirs и служебных «.dewiar…», временных и замков, ссылок и файлов больше BIG."""
    root = Path(root)
    if not root.is_dir():
        return
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".dewiar")]
        for f in files:
            p = Path(dp) / f
            if f.endswith((".tmp", ".lock", ".pid")):
                continue
            try:
                if p.is_symlink() or p.stat().st_size > BIG:
                    continue
            except OSError:
                continue
            yield p


def _human(b):
    for unit, k in (("ГБ", 1 << 30), ("МБ", 1 << 20), ("КБ", 1 << 10)):
        if b >= k:
            return f"{b / k:.1f} {unit}".replace(".", ",")
    return f"{b} байт"


class Backup:
    def __init__(self, config_dir, state_dir, workspace_root, vault=None, version=""):
        self.cfg, self.state, self.ws = Path(config_dir), Path(state_dir), Path(workspace_root)
        self.vault, self.version = vault, version
        self.host = os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "")

    # ---------- пароль закрытого слепка — запомнить на этом компьютере ----------
    # Запечатан ключом этого компьютера (как сейф), в слепок не попадает (CONFIG_SKIP): на другом компьютере его надо ввести.

    def pw_get(self):
        from crypt import device_key, unseal
        f = self.cfg / "snapshot.pw"
        try:
            return unseal(f.read_bytes(), device_key(self.cfg / "vault.key", create=False)).decode("utf-8") if f.is_file() else ""
        except (CryptError, OSError, ValueError, TypeError):
            return ""

    def pw_set(self, pw):
        from crypt import device_key, seal
        f = self.cfg / "snapshot.pw"
        if not pw:
            f.unlink(missing_ok=True)
            return
        self.cfg.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_bytes(seal(pw.encode("utf-8"), device_key(self.cfg / "vault.key", create=True)))
        os.replace(tmp, f)

    # ---------- сделать ----------

    def _fill(self, z, password=""):
        """Кладёт в zip всё, что знает ассистент. -> (counts, size, vault_n, stats — для окна восстановления)."""
        counts = {"config": 0, "state": 0, "workspace": 0}
        size = 0
        stats = {"notes": 0}
        for p in _walk(self.cfg, {"logs", "backups"}):
            rel = p.relative_to(self.cfg).as_posix()
            if rel in CONFIG_SKIP or rel.startswith(("models/", "voices/")):
                continue
            data = p.read_bytes()
            if not password:                       # без пароля — никаких ключей, токенов и паролей в открытом виде
                if rel.startswith(SECRET_DIRS):
                    continue
                if rel.endswith(".json"):
                    try:
                        data = json.dumps(scrub(json.loads(data.decode("utf-8"))), ensure_ascii=False,
                                          indent=2).encode("utf-8")
                    except ValueError:
                        continue                   # нечитаемый JSON не очистить — лучше не класть совсем
            z.writestr("config/" + rel, data)
            counts["config"] += 1
            size += len(data)
            if rel == "payments.json":
                try:
                    pj = json.loads(data.decode("utf-8"))
                    stats["bills"], stats["pays"] = len(pj.get("bills") or []), len(pj.get("pays") or [])
                except (ValueError, AttributeError):
                    pass
            elif rel.startswith("personas/") and rel.endswith(".json"):
                stats["personas"] = stats.get("personas", 0) + 1
        for name in STATE_FILES:
            p = self.state / name
            if p.is_file():
                z.write(p, "state/" + name)
                counts["state"] += 1
                if name == "reminders.json":
                    try:
                        stats["reminders"] = len(json.loads(p.read_text(encoding="utf-8")) or [])
                    except (OSError, ValueError, TypeError):
                        pass
        for d in STATE_DIRS:
            for p in _walk(self.state / d):
                z.write(p, "state/" + p.relative_to(self.state).as_posix())
                counts["state"] += 1
        for p in _walk(self.ws, WS_SKIP_DIRS):
            rel = p.relative_to(self.ws).as_posix()
            if "/downloads/" in "/" + rel and p.stat().st_size > (20 << 20):
                continue                           # скачанное в задачах можно скачать снова — крупное не берём
            z.write(p, "workspace/" + rel)
            counts["workspace"] += 1
            size += p.stat().st_size
            if rel.lower().endswith(".md"):
                stats["notes"] += 1
        vault_n = 0
        # сейф — открытым текстом внутри зашифрованного zip; в копию без пароля не попадает
        if password and self.vault is not None and self.vault.count():
            z.writestr("vault.json", self.vault.export_plain())
            vault_n = self.vault.count()
        return counts, size, vault_n, stats

    @staticmethod
    def _name(folder, auto, label, ext, tail=""):
        stamp = datetime.now().strftime("%Y-%m-%d %H-%M")
        name = f"Dewiar — {'авто' if auto else label or 'слепок'} {stamp}{tail}{ext}"
        out, k = folder / name, 2
        while out.exists():
            out = folder / name.replace(ext, f" ({k}){ext}")
            k += 1
        return out

    def make(self, folder=None, password="", auto=False, label="", fmt="dwr"):
        """Собирает слепок и пишет файл через «.part» (недописанный не выглядит готовым). fmt: "dwr" — закрытый (с
        паролем — зашифрован, со всем; без пароля — без ключей и сейфа), "zip" — открытый архив (без ключей, паролей
        и сейфа). Автокопии сверх четырёх последних удаляются. -> describe() нового файла."""
        folder = Path(folder) if folder else default_dir()
        folder.mkdir(parents=True, exist_ok=True)
        man = {"app": "Dewiar", "version": self.version, "time": datetime.now().isoformat(timespec="seconds"),
               "host": self.host, "os": "windows" if os.name == "nt" else "linux", "auto": bool(auto), "label": label}
        if fmt == "zip":
            out = self._name(folder, auto, label, ".zip", " (открытый)")
            tmp = out.with_name(out.name + ".part")
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                counts, size, _, stats = self._fill(z, "")
                man.update(format="zip", encrypted=False, secrets=False, counts=counts, vault=0, size=size, stats=stats)
                z.writestr("manifest.json", json.dumps(man, ensure_ascii=False, indent=2))
                z.writestr("README.txt", README.format(time=man["time"], version=self.version))
            tmp.replace(out)
            log.info("💾 Открытый слепок: %s (%s)", out, _human(out.stat().st_size))
            if auto:
                self._prune(folder)
            return self.describe(out)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            counts, size, vault_n, stats = self._fill(z, password)
        payload = buf.getvalue()
        man.update(format="dwr", encrypted=bool(password), counts=counts, vault=vault_n, size=size, secrets=bool(password), stats=stats)
        if password:
            payload = seal_pw(payload, password)
        out = self._name(folder, auto, label, EXT_DWR)
        tmp = out.with_name(out.name + ".part")
        with open(tmp, "wb") as f:
            f.write(HEAD)
            f.write(json.dumps(man, ensure_ascii=False).encode("utf-8") + b"\n")
            f.write(payload)
        tmp.replace(out)
        log.info("💾 Слепок: %s (%s; заметок и файлов %d)", out, _human(out.stat().st_size), counts["workspace"])
        if auto:
            self._prune(folder)
        return self.describe(out)

    def _prune(self, folder, keep=4):
        """Удаляет старые автокопии, оставляя keep последних; копии, сделанные вручную, не трогает."""
        autos = sorted((p for e in EXTS for p in Path(folder).glob(f"Dewiar — авто *{e}")), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in autos[keep:]:
            try:
                p.unlink()
            except OSError:
                pass

    # ---------- посмотреть ----------

    @staticmethod
    def read_head(path):
        """-> (описание копии, смещение начала zip). Пароль не нужен: описание лежит открыто."""
        p = Path(path)
        with open(p, "rb") as f:
            first = f.read(len(HEAD))
            if first[:2] == b"PK":                         # открытый слепок — обычный zip, описание внутри
                try:
                    with zipfile.ZipFile(p) as z:
                        man = json.loads(z.read("manifest.json").decode("utf-8"))
                except (KeyError, zipfile.BadZipFile, ValueError) as e:
                    raise BackupError("это не слепок Dewiar (в архиве нет manifest.json)") from e
                if not isinstance(man, dict) or man.get("app") != "Dewiar":
                    raise BackupError("это не слепок Dewiar")
                return dict(man, format="zip"), None
            if first != HEAD:
                raise BackupError("это не резервная копия Dewiar")
            man = json.loads(f.readline().decode("utf-8"))
            off = f.tell()
        return man, off

    def describe(self, path):
        p = Path(path)
        man, _ = self.read_head(p)
        return {"path": str(p), "name": p.name, "size": p.stat().st_size, "size_text": _human(p.stat().st_size), **man}

    def list(self, folder=None):
        folder = Path(folder) if folder else default_dir()
        out = []
        for p in sorted((q for e in EXTS for q in folder.glob(f"*{e}")), key=lambda x: x.stat().st_mtime, reverse=True)[:30]:
            try:
                out.append(self.describe(p))
            except (BackupError, OSError, ValueError):
                continue
        return out

    def last_auto(self, folder=None):
        xs = [x for x in self.list(folder) if x.get("auto")]
        return xs[0]["time"] if xs else ""

    # ---------- восстановить ----------

    def open(self, path, password=""):
        """-> (описание, ZipFile в памяти); расшифровывает, если копия с паролем."""
        man, off = self.read_head(path)
        if off is None:                                   # открытый .zip
            try:
                return man, zipfile.ZipFile(io.BytesIO(Path(path).read_bytes()))
            except zipfile.BadZipFile as e:
                raise BackupError("файл слепка повреждён") from e
        data = Path(path).read_bytes()[off:]
        if man.get("encrypted"):
            if not password:
                raise BackupError("копия защищена паролем — введите его")
            try:
                data = unseal_pw(data, password)
            except CryptError as e:
                raise BackupError("пароль не подходит") from e
        try:
            return man, zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise BackupError("файл копии повреждён") from e

    @staticmethod
    def _safe(base, rel):
        """Путь из копии — только внутрь base: копию могли подменить, и «../» или «C:» записали бы файл куда угодно."""
        rel = rel.replace("\\", "/")
        if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or ".." in rel.split("/"):
            raise BackupError(f"подозрительный путь в копии: {rel}")
        return Path(base) / rel

    def restore(self, path, password="", mode="replace"):
        """-> {"files": n, "vault": n, "before": путь копии «до», "time"}. Файлов не удаляет, одноимённые заменяет;
        сейф из копии с паролем сливается со здешним по названиям (Vault.import_plain). Копия «до» делается с тем же
        паролем, что у восстанавливаемой: только так в неё попадает сейф, и к нему потом можно вернуться."""
        man, z = self.open(path, password)
        before = None
        try:
            before = self.make(Path(path).parent, password=password if man.get("encrypted") else "",
                               auto=False, label="до восстановления")["path"]
        except Exception as e:  # noqa: BLE001
            log.warning("копия «до восстановления» не сделана: %s", e)
        if mode == "merge":
            return self._merge(path, man, z, before)
        n = 0
        try:                                           # то, что относится к этому компьютеру, а не к человеку (см. _fix_paths)
            here = json.loads((self.cfg / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            here = {}
        olds = {}                                      # настройки этого компьютера до замены — чтобы вернуть из них ключи
        if not man.get("secrets"):
            for info in z.infolist():
                top, _, rel = info.filename.partition("/")
                if top == "config" and rel.endswith(".json"):
                    try:
                        olds[rel] = json.loads(self._safe(self.cfg, rel).read_text(encoding="utf-8"))
                    except (OSError, ValueError, BackupError):
                        pass
        vault_n = 0
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if name == "vault.json":
                if self.vault is not None:
                    vault_n = self.vault.import_plain(z.read(info))
                continue
            top, _, rel = name.partition("/")
            base = {"config": self.cfg, "state": self.state, "workspace": self.ws}.get(top)
            if base is None or not rel:
                continue
            if top == "config" and rel in CONFIG_SKIP:
                continue
            dst = self._safe(base, rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".restore")     # через временный файл: оборванное восстановление не оставит половину файла
            with z.open(info) as src, open(tmp, "wb") as f:
                shutil.copyfileobj(src, f)
            os.replace(tmp, dst)
            n += 1
        # копия без пароля: ключей и паролей в ней нет — оставляем те, что уже есть на этом компьютере
        for rel, old in olds.items():
            p = self._safe(self.cfg, rel)
            try:
                cur = json.loads(p.read_text(encoding="utf-8"))
                fixed = keep_secrets(cur, old)
                if fixed != cur:
                    p.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding="utf-8")
            except (OSError, ValueError):
                pass
        self._fix_paths(other=man.get("host") != self.host, here=here)
        log.info("♻ Восстановлено из копии %s: %d файлов, сейф %d", Path(path).name, n, vault_n)
        return {"files": n, "vault": vault_n, "before": before, "time": man.get("time", "")}

    # «Добавить недостающее»: своё не трогаем. Настройки и служебное (индекс поиска) — не из слепка вовсе.
    MERGE_KEEP = {"config/settings.json", "state/knowledge.json", "state/radio.json"}

    def _merge(self, path, man, z, before):
        """-> {"files": добавлено, "merged": дополнено JSON, "beside": рядом копией, "kept": оставлено своё, "vault",
        "before", "time", "mode"}. Ничего своего не удаляет и не заменяет."""
        try:
            day = datetime.fromisoformat(man.get("time", "")).strftime("%d.%m")
        except ValueError:
            day = "слепка"
        got = {"files": 0, "merged": 0, "beside": 0, "kept": 0}
        vault_n = 0
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if name == "vault.json":
                if self.vault is not None:
                    vault_n = self.vault.import_plain(z.read(info), only_new=True)
                continue
            top, _, rel = name.partition("/")
            base = {"config": self.cfg, "state": self.state, "workspace": self.ws}.get(top)
            if base is None or not rel or (top == "config" and rel in CONFIG_SKIP):
                continue
            dst = self._safe(base, rel)
            data = z.read(info)
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                self._put(dst, data)
                got["files"] += 1
                continue
            try:
                cur = dst.read_bytes()
            except OSError:
                got["kept"] += 1
                continue
            if cur == data or name in self.MERGE_KEEP:
                got["kept"] += cur != data
                continue
            if rel.endswith(".json"):
                try:
                    a, b = json.loads(cur.decode("utf-8")), json.loads(data.decode("utf-8"))
                    m = merge_json(a, b)
                except ValueError:
                    got["kept"] += 1
                    continue
                if m != a:
                    self._put(dst, json.dumps(m, ensure_ascii=False, indent=2).encode("utf-8"))
                    got["merged"] += 1
                else:
                    got["kept"] += 1
                continue
            if top == "workspace":                      # заметка или файл отличаются — рядом копией, своё — как есть
                side = dst.with_name(f"{dst.stem} (из слепка {day}){dst.suffix}")
                if not side.exists():
                    self._put(side, data)
                    got["beside"] += 1
                else:
                    got["kept"] += 1
                continue
            got["kept"] += 1                            # фото персонажей и прочее своё — оставляем
        log.info("♻ Из слепка %s добавлено: %s, сейф %d", Path(path).name, got, vault_n)
        return dict(got, vault=vault_n, before=before, time=man.get("time", ""), mode="merge")

    @staticmethod
    def _put(dst, data):
        tmp = dst.with_name(dst.name + ".restore")      # через временный файл: оборванное не оставит половину файла
        tmp.write_bytes(data)
        os.replace(tmp, dst)

    def _fix_paths(self, other=False, here=None):
        """Правит восстановленный settings.json под этот компьютер: несуществующие здесь папки (рабочая, Obsidian)
        и, если копия с другого компьютера (other), микрофон и динамики — по умолчанию. Описание железа (device, лёгкий
        режим) — от этого компьютера (here — его настройки до восстановления), на слабом не включаем тяжёлые голос и
        распознавание. Ключ облака и профиль «dewiar-cloud» в «Мозге» приводятся в согласие."""
        sp = self.cfg / "settings.json"
        try:
            s = json.loads(sp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        ch = False
        here = here or {}
        dev = here.get("device")
        if isinstance(dev, dict) and dev.get("sig") and s.get("device") != dev:
            s["device"] = dev
            ch = True
        if (dev or {}).get("light"):                       # слабый компьютер: тяжёлый голос и распознавание из копии не берём
            if (s.get("tts") or {}).get("engine") == "vosk":
                s.setdefault("tts", {})["engine"] = "piper"
                ch = True
            if (s.get("stt") or {}).get("engine") == "gigaam":
                s.setdefault("stt", {})["engine"] = (here.get("stt") or {}).get("engine") or "vosk"
                ch = True
        cl = s.get("cloud") or {}
        key = str(cl.get("key") or "")
        if key and not key.lower().startswith("dw-") and not cl.get("account"):
            s["cloud"]["account"] = True                   # токен входа аккаунта, а не ключ dw-
            ch = True
        hp = ((here.get("llm") or {}).get("profiles") or {}).get("dewiar-cloud")
        llm = s.setdefault("llm", {})
        if key and hp and "dewiar-cloud" not in (llm.get("profiles") or {}) and str(hp.get("api_key") or "") == key:
            llm.setdefault("profiles", {})["dewiar-cloud"] = hp     # модели Dewiar этого компьютера — к его ключу
            if not llm.get("active"):
                llm["active"] = "dewiar-cloud"
            ch = True
        wp = (s.get("workspace") or {}).get("path")
        if wp and not Path(os.path.expanduser(wp)).is_dir():
            s["workspace"]["path"] = ""
            ch = True
        ov = (s.get("obsidian") or {}).get("vault")
        if ov and not Path(os.path.expanduser(ov)).is_dir():
            s["obsidian"]["vault"] = ""
            ch = True
        for k in ("input", "output"):                     # микрофон и динамики с другого компьютера — по умолчанию
            if other and (s.get("audio") or {}).get(k):
                s["audio"][k] = ""
                ch = True
        if ch:
            sp.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_json(cur, new):
    """Дополнить своё (cur) из слепка (new), ничего не заменяя: в списках записей с «id» — добавить записи с новыми id,
    в списках простых значений — недостающие значения, в словарях — недостающие ключи (и так же вглубь). Значения,
    которые есть у обоих, остаются свои."""
    if isinstance(cur, dict) and isinstance(new, dict):
        out = dict(cur)
        for k, v in new.items():
            out[k] = merge_json(cur[k], v) if k in cur else v
        return out
    if isinstance(cur, list) and isinstance(new, list):
        if all(isinstance(x, dict) and "id" in x for x in cur + new) and (cur or new):
            have = {str(x["id"]) for x in cur}
            return cur + [x for x in new if str(x["id"]) not in have]
        if all(not isinstance(x, (dict, list)) for x in cur + new):
            return cur + [x for x in new if x not in cur]
        return cur
    return cur


def due(last_iso, days=7):
    """Пора ли автокопии. Час запаса: копия, сделанная чуть позже в прошлый раз, не сдвигает следующую на сутки."""
    if not last_iso:
        return True
    try:
        return (datetime.now() - datetime.fromisoformat(last_iso)).total_seconds() > days * 86400 - 3600
    except ValueError:
        return True

