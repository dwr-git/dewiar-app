"""«Облако Лиры» (1.0.23; владелец 17.11: «сетевая флешка — закидываешь, и открывается с любого устройства; Лира знает,
что там, и отвечает по этому; можно ограничить размер и форматы») — сами файлы «Моих файлов» на всех устройствах.

Устроено просто: «Мои файлы» — это папка «Знания» (core/knowledge.py; «Добавить файлы» кладёт туда копию). Каждый файл её
верхнего уровня подходящего вида уходит в облако Dewiar (server/dwrapp/cloud/drive.php), а файлы, добавленные на других
устройствах, приходят сюда же — и Лира читает их как свои. Сервер видит только шифр: куски и описание (имя, вид, отпечаток)
шифруются ключом синхронизации (sync.e2e, как заметки и пароли; без него облако не работает — включается одной кнопкой).

Правила обмена (tick, раз в несколько минут и сразу после правки):
- новый или изменившийся файл здесь — в облако (изменился — новым, старый удаляется);
- файл из облака, которого здесь нет, — скачать (имя занято другим файлом — «имя (2).pdf»);
- файла больше нет в облаке (удалили на другом устройстве) — здесь в корзину;
- «Убрать» в «Моих файлах» — из облака и отсюда. Файл, пропавший из папки сам (перенесли в Проводнике), возвращается:
  облако — главная копия.
Подключённые папки («Подключить папку…») остаются на своём компьютере — в облако не уходят."""
import hashlib
import json
import logging
import secrets
import threading
import time
from pathlib import Path

import httpx

log = logging.getLogger("dewiar.drive")

FILE_MAX = 25 * 1024 * 1024
PART = 2 * 1024 * 1024
EXTS = {".pdf", ".docx", ".odt", ".xlsx", ".pptx", ".txt", ".md", ".csv", ".html", ".htm", ".jpg", ".jpeg", ".png", ".webp"}
EVERY = 300                      # обычный обмен — раз в 5 минут


def kind_of(name):
    """Вид файла для плитки: pdf, doc, sheet, slides, text, image."""
    e = Path(name).suffix.lower()
    return {".pdf": "pdf", ".docx": "doc", ".odt": "doc", ".xlsx": "sheet", ".csv": "sheet", ".pptx": "slides",
            ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image"}.get(e, "text")


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:32]


class DriveError(Exception):
    pass


class Drive:
    def __init__(self, host, state_path):
        """host: knowledge (root — папка «Знания»), sync (облачная синхронизация: e2e_key(), state["device"]),
        credentials() -> (токен, токен связи, адрес облака), emit(...)."""
        self.host = host
        self.path = Path(state_path)
        self.lock = threading.Lock()
        self.kick = threading.Event()
        self.st = self._load()
        self.last = {"used": 0, "quota": 0, "files": [], "error": "", "at": 0}
        self.busy = ""

    # ---------- состояние ----------
    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:
            log.warning("Облако Лиры: состояние не сохранилось: %s", e)

    @property
    def files(self):
        """id в облаке -> {name, sha, size} — что из облака лежит здесь (и что отсюда ушло туда)."""
        return self.st.setdefault("files", {})

    # ---------- связь ----------
    def key(self):
        s = getattr(self.host, "sync", None)
        try:
            return s.e2e_key() if s is not None else None
        except Exception:  # noqa: BLE001
            return None

    def _creds(self):
        try:
            token, link, url = self.host.credentials()
        except Exception:  # noqa: BLE001
            token, link, url = "", "", ""
        return token, link, url

    def ready(self):
        """-> "" (можно) или почему нельзя: нет входа/ключа Dewiar, выключено шифрование."""
        token, _, url = self._creds()
        if not token or not url:
            return "nokey"
        if self.key() is None:
            return "e2e"
        return ""

    def _req(self, method, path, params=None, content=None, headers=None, json_body=None, timeout=60):
        token, link, url = self._creds()
        h = {"Authorization": "Bearer " + token}
        if link and link != token:
            h["X-Sync-Link"] = link
        s = getattr(self.host, "sync", None)
        if s is not None:
            h["X-Drive-Dev"] = str(s.state.get("device") or "")
        h.update(headers or {})
        q = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        try:
            r = httpx.request(method, url + "?p=" + path + ("&" + q if q else ""), headers=h, content=content, json=json_body, timeout=timeout)
        except httpx.HTTPError as e:
            raise DriveError("облако Dewiar не ответило") from e
        if r.status_code >= 400:
            try:
                msg = r.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                msg = f"облако ответило {r.status_code}"
            raise DriveError(msg)
        return r

    # ---------- шифр ----------
    def _seal(self, b):
        import closecrypto as CC
        return CC.seal(self.key(), b)

    def _open(self, b):
        import closecrypto as CC
        return CC.unseal(self.key(), b)

    def _meta_open(self, m):
        import closecrypto as CC
        try:
            return json.loads(self._open(CC.b64d(m)).decode("utf-8"))
        except Exception:  # noqa: BLE001 — чужой ключ, испорченная запись
            return None

    # ---------- облако ----------
    def remote(self):
        """-> {id: {name, kind, size, sha, mtime, created, dev}} и сведения о месте; описания расшифрованы."""
        d = self._req("GET", "/drive").json()
        out = {}
        for f in d.get("files") or []:
            m = self._meta_open(f.get("meta") or "")
            if not m or not m.get("name"):
                continue
            out[f["id"]] = {"name": Path(str(m["name"])).name, "sha": m.get("sha") or "", "mtime": m.get("mtime") or 0,
                            "size": int(f.get("size") or 0), "parts": int(f.get("parts") or 1), "created": int(f.get("created") or 0),
                            "dev": f.get("dev") or ""}
        return out, {"used": int(d.get("used") or 0), "quota": int(d.get("quota") or 0)}

    def upload(self, p):
        """Файл -> облако. -> id."""
        data = p.read_bytes()
        if len(data) > FILE_MAX:
            raise DriveError(f"«{p.name}» больше 25 МБ — в облако Лиры такой не помещается")
        fid = secrets.token_hex(12)
        parts = [data[i:i + PART] for i in range(0, len(data), PART)] or [b""]
        import closecrypto as CC                     # base64 как у телефона (DewiarCrypto.b64e): описание открывают все устройства
        meta = CC.b64e(self._seal(json.dumps({"name": p.name, "sha": _sha(p), "mtime": int(p.stat().st_mtime)},
                                             ensure_ascii=False).encode("utf-8")))
        for n, part in enumerate(parts):
            self.busy = f"up:{p.name}:{n + 1}:{len(parts)}"
            self._req("POST", "/drive/put", {"id": fid, "n": n, "of": len(parts)}, content=self._seal(part),
                      headers={"X-Drive-Meta": meta, "X-Drive-Size": str(len(data)), "Content-Type": "application/octet-stream"} if n == 0
                      else {"Content-Type": "application/octet-stream"})
        log.info("☁️ Облако Лиры: «%s» отправлен (%d КБ)", p.name, len(data) // 1024)
        return fid

    def download(self, fid, info):
        """Файл облака -> байты (расшифрованы, отпечаток сверен)."""
        out = b""
        for n in range(int(info.get("parts") or 1)):
            self.busy = f"down:{info['name']}:{n + 1}:{info.get('parts') or 1}"
            out += self._open(self._req("GET", "/drive/get", {"id": fid, "n": n}).content)
        if info.get("sha") and hashlib.sha256(out).hexdigest()[:32] != info["sha"]:
            raise DriveError(f"«{info['name']}» пришёл испорченным — попробую ещё раз позже")
        return out

    # ---------- здесь ----------
    def root(self):
        return self.host.knowledge.root

    def local(self):
        """Файлы «Моих файлов», которые ходят в облако: верхний уровень папки, подходящие виды, до 25 МБ."""
        out = {}
        try:
            for p in sorted(self.root().iterdir()):
                if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith(".") and p.name != "О папке.md":
                    out[p.name] = p
        except OSError:
            pass
        return out

    def _free(self, name):
        root, n = self.root(), 2
        dst = root / name
        while dst.exists():
            dst = root / f"{Path(name).stem} ({n}){Path(name).suffix}"
            n += 1
        return dst

    def _trash(self, p):
        try:
            import guard
            guard.trash([{"path": str(p), "dir": False, "files": 1, "size": p.stat().st_size}])
        except Exception as e:  # noqa: BLE001
            log.warning("Облако Лиры: «%s» не убрался в корзину: %s", p.name, e)

    # ---------- обмен ----------
    def tick(self):
        """Один обмен. -> сводка для студии (status)."""
        why = self.ready()
        if why:
            self.last.update(error="", at=time.time(), why=why)
            return self.status()
        with self.lock:
            try:
                self._tick()
                self.last["error"] = ""
            except DriveError as e:
                self.last["error"] = str(e)
                log.warning("☁️ Облако Лиры: %s", e)
            finally:
                self.busy = ""
                self.last["at"] = time.time()
                self.last["why"] = ""
                self._save()
        try:
            self.host.emit("drive", **self.status())
        except Exception:  # noqa: BLE001
            pass
        return self.status()

    def _tick(self):
        for fid in list(self.st.get("del") or []):     # убрали здесь, пока облако было недоступно
            try:
                self._req("POST", "/drive/del", json_body={"id": fid})
            except DriveError:
                break
            self.st["del"].remove(fid)
            self.files.pop(fid, None)
        rem, space = self.remote()
        here = self.local()
        by_name = {v["name"]: k for k, v in self.files.items()}
        changed = False
        # 1. удалили на другом устройстве — здесь в корзину
        for fid in [k for k in self.files if k not in rem]:
            name = self.files[fid]["name"]
            p = here.get(name)
            if p is not None and (not self.files[fid].get("sha") or _sha(p) == self.files[fid]["sha"]):
                self._trash(p)
                here.pop(name, None)
                log.info("☁️ Облако Лиры: «%s» удалён на другом устройстве — убран и здесь", name)
                changed = True
            del self.files[fid]
        by_name = {v["name"]: k for k, v in self.files.items()}
        # 2. здесь новое или изменилось — в облако
        sent = False
        for name, p in here.items():
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size > FILE_MAX or size == 0:
                continue
            fid = by_name.get(name)
            if fid and self.files[fid].get("size") == size and self.files[fid].get("mtime") == int(p.stat().st_mtime):
                continue                                   # не менялся — отпечаток не считаем
            sha = _sha(p)
            if fid and self.files[fid].get("sha") == sha:
                self.files[fid].update(mtime=int(p.stat().st_mtime), size=size)
                continue
            if space["quota"] and space["used"] + size > space["quota"]:
                self.last["full"] = name
                continue
            new = self.upload(p)
            space["used"] += size
            if fid:
                try:
                    self._req("POST", "/drive/del", json_body={"id": fid})
                    space["used"] -= int(rem.get(fid, {}).get("size") or 0)
                except DriveError:
                    pass
                self.files.pop(fid, None)
            self.files[new] = {"name": name, "sha": sha, "size": size, "mtime": int(p.stat().st_mtime)}
            self._save()
            sent = True
        if sent:                                           # список облака после своих отправок: новые id, без старых версий
            rem, space = self.remote()
        # 3. в облаке есть, здесь нет — скачать (пропал из папки сам — вернуть: облако — главная копия)
        for fid, info in rem.items():
            mine = self.files.get(fid)
            if mine and mine["name"] in here:
                continue
            if not mine and any(v.get("sha") == info["sha"] for v in self.files.values()):
                continue                                   # тот же файл уже есть под другим id (отправили только что)
            data = self.download(fid, info)
            dst = here.get(info["name"]) if mine else None
            if dst is None:
                dst = self.root() / info["name"]
                if dst.exists() and _sha(dst) != info["sha"]:
                    dst = self._free(info["name"])
            tmp = dst.with_name("." + dst.name + ".part")
            tmp.write_bytes(data)
            tmp.replace(dst)
            self.files[fid] = {"name": dst.name, "sha": info["sha"], "size": len(data), "mtime": int(dst.stat().st_mtime)}
            here[dst.name] = dst
            changed = True
            self._save()
            log.info("☁️ Облако Лиры: «%s» пришёл с другого устройства", dst.name)
        self.last.update(used=space["used"], quota=space["quota"], files=self._view(rem))
        if changed:
            try:
                self.host.knowledge.refresh()
            except Exception:  # noqa: BLE001
                pass

    def _view(self, rem):
        here = self.local()
        own = str((getattr(self.host, "sync", None) and self.host.sync.state.get("device")) or "")
        out = []
        for fid, info in rem.items():
            name = (self.files.get(fid) or {}).get("name") or info["name"]
            out.append({"id": fid, "name": name, "kind": kind_of(name), "size": info["size"], "created": info["created"],
                        "here": name in here, "mine": info.get("dev") == own})
        return sorted(out, key=lambda x: -x["created"])

    def devices(self):
        """Свои устройства для карточки облака: этот, другие компьютеры, телефоны (были за 30 дней)."""
        s = getattr(self.host, "sync", None)
        now, out = time.time(), []
        for d in ((s.status.get("all") if s is not None else None) or []):
            if d.get("me") or now - float(d.get("seen") or 0) < 30 * 86400:
                out.append({"name": str(d.get("name") or "")[:40], "app": d.get("app") or "pc", "me": bool(d.get("me"))})
        return sorted(out, key=lambda x: (not x["me"], x["app"] != "pc", x["name"]))[:6]

    def status(self):
        try:
            root = str(self.root())
        except Exception:  # noqa: BLE001
            root = ""
        return {"why": self.ready(), "devices": self.devices(), "root": root, "error": self.last.get("error", ""), "used": self.last.get("used", 0),
                "quota": self.last.get("quota", 0), "files": self.last.get("files", []), "busy": self.busy,
                "at": self.last.get("at", 0), "full": self.last.get("full", ""), "max_mb": FILE_MAX // (1024 * 1024),
                "exts": sorted(EXTS)}

    def remove(self, name):
        """«Убрать» в «Моих файлах»: из облака (у всех) и отсюда — в корзину."""
        fid = next((k for k, v in self.files.items() if v["name"] == name), None)
        if fid:
            with self.lock:
                try:
                    if self.ready():
                        raise DriveError("облако недоступно")
                    self._req("POST", "/drive/del", json_body={"id": fid})
                    self.files.pop(fid, None)
                except DriveError:                     # удалим из облака при следующем обмене — а не скачаем обратно
                    self.st.setdefault("del", []).append(fid)
                self._save()
        p = self.local().get(name)
        if p is not None:
            self._trash(p)
        self.kick.set()
        return True

    def run(self, stop):
        """Фоновый обмен: раз в EVERY секунд и сразу по kick (добавили или убрали файл, пришёл ключ)."""
        time.sleep(20)
        while not stop.is_set():
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                log.warning("☁️ Облако Лиры: сбой обмена: %s", e)
            self.kick.wait(EVERY)
            self.kick.clear()
