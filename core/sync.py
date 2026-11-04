"""Синхронизация устройств одного человека через облако Dewiar (cloud.php ?p=/sync): компьютер ↔ телефон ↔ другой компьютер.

Что синхронизируется (вид записи → что это): reminder — напоминания и будильники (дела по расписанию — нет, они
выполняются на этом компьютере); note — заметки и списки (папка «Заметки»); money — расходы и доходы; memory — строки
«Обо мне». Дополнительные виды (EXTRA_KINDS) идут, только если их знает сервер: soul/mind — душа персонажей,
конституция и выводы на завтра; diary — последние дни дневника (пишет компьютер, телефон читает); dayturn — разговор
с телефона в дневник дня и taskreq — задача с телефона (компьютер забирает их и тем самым удаляет из облака); task —
ход задач для показа на телефоне; vault — всё хранилище Obsidian между компьютерами (если включено); bill, pay, payfile —
«Платежи» между компьютерами: счета, оплаты и вложения кусками (_apply_pay); safe — «Сейф паролей» между своими
устройствами, только шифром мастер-пароля сейфа (vault.SafeKey, _snap_safe/_apply_safe; 03.11).

Как: каждое устройство раз в минуту (и сразу после своих изменений, событие soon) сравнивает свои данные с тем, что
уже отправляло (отпечатки в STATE_DIR/sync.json), шлёт изменения и удаления и забирает чужие, начиная с номера
последнего полученного изменения (rev). Запись, которой больше нет в снимке, уходит как удаление — поэтому всё, что
выпало из snapshot() (не прочиталось, стало слишком большим), другие устройства тоже удалят. При правке одной записи
на двух устройствах сервер оставляет более позднюю (по часам устройства); для vault — см. _apply_vault.
Формат записей и порядок обмена совпадают с syncSnapshot()/syncRun() в android/assets/www/app.js и с ?p=/sync в cloud.php.

Чьи данные: аккаунт dewiar.pro (если вошли) или ключ Dewiar (dw-…). Если на устройстве есть и то и другое — сервер
связывает их в одно пространство (X-Sync-Link), чтобы телефон с ключом и компьютер с аккаунтом видели одно и то же.
"""

import base64
import datetime as dt
import hashlib
import json
import logging
import os
import re
import shutil
import socket
import threading
import time
import uuid
from pathlib import Path

import httpx

from settings import STATE_DIR

log = logging.getLogger("dewiar.sync")

BASE_KINDS = ("reminder", "note", "money", "memory")          # знает любой сервер
EXTRA_KINDS = ("soul", "mind", "diary", "dayturn", "taskreq", "task", "vault", "done", "persona", "bill", "pay", "payfile", "pmemory", "safe",
               "plugin")                          # тот же список $extra в cloud.php; plugin — только между компьютерами (не по Wi-Fi)
VAULT_MAX = 300_000                               # сервер не принимает запись больше 300 КБ — такие заметки не шлём
VAULT_FILES = 15000
CHUNK = 400                                       # изменений за один запрос (сервер берёт до 2000; первая отправка большого хранилища — частями)
DIARY_DAYS = 30                                   # сколько последних дней дневника видно на телефоне
TASKS_SHOWN = 15
NOTES = "Заметки"
MEMORY = Path("Память") / "Обо мне.md"
NOTE_MAX = 300_000
PAD_DIR = "Блокнот"                     # вкладки блокнота у виджета (core/pad.py) — «Заметки/Блокнот/*.md»
# Душа и конституция идут в системную подсказку каждого разговора: с другого устройства принимаем только похожее на них
# (аудит 19.10: кто завладел ключом аккаунта, мог бы подменить поведение помощника). В подсказку и так уходит
# не больше 1800/1400 знаков (soul.MAX_CONST / MAX_SOUL) — длиннее этого предела запись из облака не принимаем вовсе.
MIND_MAX = 8000
DIARY_MAX = 60_000                                  # день дневника — текст, не архив
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")   # управляющие и «невидимые» знаки
CONST_PREV = "Память/Конституция — прежняя.md"
# Сквозное шифрование (sync.e2e, core/synckey.py): что шифруется на устройстве — всё личное. Открытыми остаются только
# метка «шифрование включено» (mind:e2e), задачи для облака (taskreq с cloud — их выполняет сервер) и удаления (пустые).
E2E_KINDS = ("reminder", "note", "money", "memory", "soul", "mind", "diary", "dayturn", "done", "persona", "vault", "task", "taskreq", "pmemory",
             "bill", "pay", "payfile", "safe", "plugin")          # safe и без того шифр мастер-пароля — с e2e он ещё и в конверте ключа синхронизации
# «Платежи» между компьютерами (27.10, владелец: «платежи дома заполнил… а на работе их нет»): bill — счёт, pay — оплата,
# payfile — вложение (платёжка, скриншот) кусками: облако берёт запись до 300 КБ, а зашифрованная на треть длиннее
PF_CHUNK = 150_000
PF_MAX = 6_000_000                                # больше — файл не синхронизируем (запись счёта его всё равно помнит)
E2E_MARK = "mind:e2e"
SEALED_MAX = 290_000                              # сервер не берёт запись больше 300 КБ — зашифрованная на треть длиннее


def _mind_text(d, limit):
    """Текст души, конституции или дня дневника из облака: строка, без управляющих и невидимых знаков (ими прячут
    команды от глаз человека), не длиннее limit. Не подходит — None (запись не применяется)."""
    t = d.get("text") if isinstance(d, dict) else None
    if not isinstance(t, str) or len(t) > limit:
        return None
    return _CTRL.sub("", t)
_FACT = re.compile(r"^- (.+?)(?: _\(\d\d\.\d\d\.\d{4}\)_)?\s*$")


def _seal(k, data):
    from synckey import seal_data
    return seal_data(k, data)


def _open(k, data):
    from synckey import open_data
    return open_data(k, data)


def _is_sealed(d):
    return isinstance(d, dict) and bool(d.get("e2e")) and isinstance(d.get("c"), str)


def _now_ms():
    return int(time.time() * 1000)


def _h(data):
    """Отпечаток записи «как она лежит у нас». Только локальный: телефон считает свой иначе, сравнивать их нельзя."""
    return hashlib.sha1(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _pmem_id(name, text):
    """id факта своей памяти персонажа: «m<отпечаток имени>-<id факта>» — удаление (без текста) найдёт и файл, и строку.
    Так же считает pmemId() в app.js."""
    return "m" + hashlib.sha1(str(name).strip().lower().encode("utf-8")).hexdigest()[:8] + "-" + (_fact_id(text) if text else "")


_NUM_TAIL = re.compile(r"\s*\(\d{1,3}\)$")


def _base_title(title):
    """Название без хвоста « (2)» — его дописывает компьютер, когда имя файла занято (как noteBase в app.js)."""
    return _NUM_TAIL.sub("", " ".join(str(title or "").split()))


def _note_norm(title, text):
    """Текст заметки для сравнения «та же ли»: без «# Название» в начале (компьютер его дописывает, и там может не быть
    « (2)» из имени файла) и лишних пробелов — как noteNorm в app.js."""
    t = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    first = t.split("\n", 1)[0]
    if first.startswith("# ") and _base_title(first[2:]) == _base_title(title):
        t = t[len(first):].strip()
    return re.sub(r"\s+", " ", t)


def _fact_id(text):
    """id строки памяти — по её тексту; нормализация та же, что у factId() в app.js, иначе телефон и компьютер
    разойдутся в id и удаление строки на одном не найдёт её на другом."""
    return "f" + hashlib.sha1(re.sub(r"\s+", " ", text.strip().lower().rstrip(".")).encode("utf-8")).hexdigest()[:12]


class SyncError(Exception):
    pass


class FanEvent(threading.Event):
    """«Есть свои правки — обменяться скорее»: будит и облачную синхронизацию, и домашнюю (HomeSync), если она есть."""
    def __init__(self):
        super().__init__()
        self.also = []

    def set(self):
        super().set()
        for e in self.also:
            e.set()


class Sync:
    HOME = False

    def _creds(self):
        return self.host.credentials()

    def __init__(self, host):
        """host: reminders, money, workspace, credentials() -> (token, link_token, cloud_url), device_name(), push();
        по желанию soul, diary, tasks, obsidian — без них соответствующие виды просто не собираются."""
        self.host = host
        self.path = STATE_DIR / "sync.json"
        self._lock = threading.Lock()
        self.soon = FanEvent()
        self.on_pass = None                          # (monotonic начала обмена) -> после каждого обмена (engine: напоминания)
        self.state = self._load()
        self.status = {"enabled": False, "ok": None, "at": 0, "error": "", "devices": [], "space": "", "counts": {}}
        self._claims = {}            # задачи с телефона, которые надо занять в облаке, прежде чем браться (см. _claim_tasks)
        self.sibling = None          # облачная ↔ домашняя (HomeSync) того же компьютера: общий id заметок (см. _note_paths)

    # ---------- состояние ----------

    def _load(self):
        """sync.json: rev — номер последнего полученного изменения; device — id этого устройства («pc-…»: по приставке
        сервер отличает компьютеры от телефонов); idx — ключ записи → {h: наш отпечаток, u: время версии, del, skip,
        b: для vault — отпечаток версии, с которой облако согласно}; map — id заметки → путь в «Заметках»; who — чей ключ;
        kinds — какие виды знает сервер; mt/vt/vmap — кэши заметок и хранилища."""
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("idx", {})
                d.setdefault("map", {})
                return d
        except (OSError, ValueError):
            pass
        return {"rev": 0, "device": "pc-" + uuid.uuid4().hex[:10], "idx": {}, "map": {}, "who": ""}

    def _save(self):
        # через временный файл: оборванная запись не испортит sync.json (иначе всё ушло бы заново и с удалениями)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    # ---------- сквозное шифрование (sync.e2e) ----------

    def e2e_key(self):
        """Ключ, если шифрование включено на этом устройстве и ключ есть. -> 32 байта или None."""
        ks = getattr(self.host, "sync_key", None)
        s = getattr(self.host, "s", None)
        try:
            on = bool(s.get("sync", "e2e")) if s is not None else False
        except Exception:  # noqa: BLE001
            on = False
        cur = ks.get() if ks is not None and on else None
        return cur["k"] if cur else None

    def _sealable(self, kind, iid, data):
        key = kind + ":" + iid
        if key == E2E_MARK or kind not in E2E_KINDS or not isinstance(data, dict) or not data:
            return False
        if kind == "taskreq" and data.get("cloud"):     # задачу просили выполнить в облаке — серверу её надо прочитать
            return False
        return True

    def e2e_status(self):
        ks = getattr(self.host, "sync_key", None)
        return {"on": self.e2e_key() is not None, "key": bool(ks is not None and ks.get()),
                "remote": bool(self.state.get("e2e_remote")), "locked": int(self.state.get("e2e_locked") or 0)}

    def e2e_enable(self, on):
        """Включить или выключить шифрование на этом устройстве. Включили — ключ (свой или уже полученный), всё своё
        уходит заново зашифрованным, ключ — своим устройствам конвертом. Выключили — только здесь (шифрование другие
        устройства не выключает: метку в облаке мог бы снять и чужой, завладевший аккаунтом)."""
        ks = getattr(self.host, "sync_key", None)
        if on and ks is not None and not ks.get():
            ks.create()
        self.host.s.update({"sync": {"e2e": bool(on)}})
        with self._lock:
            self.state["reseal_all"] = True
            self.state["e2e_off_here"] = not on       # выключили здесь — метка других устройств сама не включит
            self._save()
        share = getattr(self.host, "own_share", None)
        if on and callable(share):
            share()
        self.soon.set()
        return self.e2e_status()

    def key_arrived(self):
        """Ключ пришёл с другого устройства: включить шифрование и забрать историю заново (зашифрованное, что не
        открылось, — откроется теперь)."""
        if not self.state.get("e2e_off_here"):
            self.host.s.update({"sync": {"e2e": True}})
        with self._lock:
            self.state.update(rev=0, reseal_all=True, e2e_locked=0)
            self._save()
        self.soon.set()

    # ---------- снимок данных этого устройства: ключ → (data, hash) ----------

    def _notes_root(self):
        return self.host.workspace.ensure() / NOTES

    def _note_paths(self):
        """Путь заметки -> id: свой map, а для путей, которых в нём нет, — map соседней синхронизации этого компьютера
        (облачной или «Дома по Wi-Fi»). Телефон с входом и Wi-Fi шлёт одну заметку обоими путями (04.11) — без общего
        id она легла бы здесь двумя файлами («… (2)»), а с компьютера ушла бы под другим id."""
        by_path = {v: k for k, v in self.state["map"].items()}
        sib = getattr(self, "sibling", None)
        if sib is not None:
            for k, v in list((sib.state.get("map") or {}).items()):
                by_path.setdefault(v, k)
        return by_path

    def _sib_rel(self, sid):
        sib = getattr(self, "sibling", None)
        rel = (sib.state.get("map") or {}).get(sid) if sib is not None else None
        return rel if rel and rel not in self.state["map"].values() else None

    def _note_alias(self, sid, d, deleted):
        """Та же заметка под вторым id (рецензия 04.11: до 0.83 мост давал заметке с телефона в облаке id по пути — f…, а на
        узле Wi-Fi у неё оставался id телефона — n…; после входа на телефоне «Покупки» ложились вторым и третьим файлом).
        -> id, под которым этот обмен знает её файл, или None. Второе имя — если соседняя синхронизация этого компьютера
        положила sid в тот же файл, или если это новая заметка, а на её месте уже лежит файл с тем же текстом."""
        m = self.state["map"]
        if sid in m:
            return None
        al = (self.state.get("alias") or {}).get(sid)
        if al and al in m:
            return al
        sib = getattr(self, "sibling", None)
        srel = (sib.state.get("map") or {}).get(sid) if sib is not None else None
        if srel:
            return next((k for k, v in m.items() if v == srel), None)
        if deleted or not isinstance(d, dict):
            return None
        from workspace import _clean_name
        folder = "/".join(_clean_name(x) for x in str(d.get("folder") or "").split("/") if x.strip() and x not in (".", ".."))
        base = _clean_name(_base_title(d.get("title") or "Заметка")) or "Заметка"
        want = _note_norm(d.get("title") or "", d.get("text") or "")
        rel = None
        for n in range(1, 31):                            # «Список.md», «Список (2).md»… — компьютер мог занять имя раньше
            cand = (folder + "/" if folder else "") + (base if n == 1 else f"{base} ({n})") + ".md"
            p = self._notes_root() / cand
            if not p.is_file():
                if n > 2:
                    break
                continue
            try:
                if _note_norm(p.stem, p.read_text(encoding="utf-8")) == want:
                    rel = cand
                    break
            except (OSError, UnicodeDecodeError):
                continue
        if rel is None:
            return None
        own = next((k for k, v in m.items() if v == rel), None)
        if own is None:                                   # файл ещё не в обмене — его id тот же, что даст снимок
            own = self._note_paths().get(rel) or "f" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
            m[own] = rel
            if own == sid:
                return None
        return own

    def note_sid(self, rel):
        """Путь заметки в папке ассистента («Заметки/…») -> её id синхронизации (тот же, что в snapshot: из map или
        отпечаток пути) — им её знает телефон."""
        sub = str(rel)[len(NOTES) + 1:] if str(rel).startswith(NOTES + "/") else str(rel)
        by_path = self._note_paths()
        return by_path.get(sub) or "f" + hashlib.sha1(sub.encode("utf-8")).hexdigest()[:12]

    def snapshot(self):
        """-> {«вид:id»: данные}. Для заметок и хранилища ещё «ключ#t» — время правки файла (мс) и, если файл не менялся
        с прошлого раза, данные None и «ключ#h» — отпечаток из кэша (сам текст читаем, только когда его надо отправить).
        Попутно обновляет map и кэш mt. Чего нет в снимке — уйдёт удалением, см. шапку."""
        out = {}
        root = self._notes_root()
        by_path = self._note_paths()
        sib = getattr(self, "sibling", None)
        sib_by = {v: k for k, v in list(((sib.state.get("map") or {}) if sib is not None else {}).items())}
        for r in list(self.host.reminders.items):
            if r.get("kind") == "job":
                continue
            try:
                at = int(dt.datetime.fromisoformat(r["at"]).timestamp() * 1000)
            except (KeyError, ValueError):
                continue
            d = {"text": r.get("text", ""), "at": at, "kind": r.get("kind") or "reminder",
                 "repeat": r.get("repeat") or None, "paused": bool(r.get("paused"))}
            nid = r.get("note_id") or ""
            if r.get("note") and str(r["note"]).startswith(NOTES + "/"):     # заметка с картинками — её id, как у самой заметки
                rel = str(r["note"])[len(NOTES) + 1:]
                nid = by_path.get(rel) or "f" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
            if nid:
                d["note"] = nid
            out["reminder:" + r["id"]] = d
        for m in list(self.host.money.items):
            d = {k: m.get(k) for k in ("date", "kind", "amount", "currency", "category", "note")}
            out["money:" + m["id"]] = d
        cache = self.state.setdefault("mt", {})
        seen_paths = set()
        if root.is_dir():
            for p in sorted(root.rglob("*.md"))[:3000]:
                rel = p.relative_to(root).as_posix()
                if any(part.startswith(".") for part in p.relative_to(root).parts):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size > NOTE_MAX:
                    continue
                sid = by_path.get(rel) or "f" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
                self.state["map"][sid] = rel
                seen_paths.add(rel)
                key = "note:" + sid
                out[key + "#t"] = st.st_mtime_ns // 1_000_000     # когда правили на самом деле: старая копия не перебьёт новую
                sig = f"{st.st_mtime_ns}:{st.st_size}"
                c = cache.get(rel)
                # другой обмен этого компьютера знает файл под другим id (мост до 0.83) — подсказка телефону: aka, та же заметка
                aka = sib_by.get(rel) if sib_by.get(rel) not in (None, sid) else None
                if aka:
                    cache.pop(rel, None)
                    c = None
                if c and c[0] == sig:                     # файл не менялся — не читаем его каждую минуту
                    out[key] = None
                    out[key + "#h"] = c[1]
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                folder = p.parent.relative_to(root).as_posix()
                d = {"title": p.stem, "text": text, "folder": "" if folder == "." else folder}
                if aka:
                    d["aka"] = aka
                out[key] = d
                if not aka:
                    cache[rel] = [sig, _h(d)]
        for rel in [r for r in cache if r not in seen_paths]:
            cache.pop(rel, None)
        # id пропавшей заметки забываем, только если синхронизация о ней не знает: известному id путь ещё понадобится
        for sid in [s for s, r in self.state["map"].items() if r not in seen_paths and "note:" + s not in self.state["idx"]]:
            self.state["map"].pop(sid, None)
        for fact in self._facts():
            out["memory:" + _fact_id(fact)] = {"text": fact}
        if set(EXTRA_KINDS) & set(self.state.get("kinds") or ()):     # только виды, которые знает сервер
            self.state["_extra_failed"] = False
            try:
                self._snap_extra(out)
            except Exception as e:  # noqa: BLE001 — душа, дневник и задачи не должны ломать напоминания и заметки
                self.state["_extra_failed"] = True
                log.warning("Синхронизация: душа/дневник/задачи не собрались: %s", e)
        return out

    def _snap_extra(self, out):
        h = self.host
        ok = set(self.state.get("kinds") or ())
        if "pmemory" in ok:                         # своя память персонажей (0.56): факты по файлам «Память/Персонажи» и кто со своей
            for name, facts in self._pfacts().items():
                for fact in facts:
                    out["pmemory:" + _pmem_id(name, fact)] = {"who": name, "text": fact}
            own = h.s.get("persona_memory", "own") if getattr(h, "s", None) is not None else None
            if own is not None and int(h.s.get("persona_memory", "at") or 0) > 0:     # меняли хоть раз — иначе не перебивать чужое
                out["pmemory:own"] = {"names": list(own), "at": int(h.s.get("persona_memory", "at") or 0)}
        pers = getattr(h, "personas", None)
        if pers is not None and "persona" in ok and hasattr(pers, "own_ids"):
            # свои персонажи (19.10: создали на телефоне — пусть будет и на компьютере, и наоборот); облик — до 250 КБ
            for p in pers.all():
                if p.get("id") not in pers.own_ids():
                    continue
                av = pers.avatar_data_url(p) if p.get("avatar") else ""
                out["persona:" + p["id"]] = {"name": p.get("name", ""), "gender": p.get("gender") or "female", "role": p.get("role") or "",
                                             "about": p.get("about") or p.get("character") or "", "color": p.get("color") or "",
                                             "avatar": av if len(av) < 250000 else ""}
        soul = getattr(h, "soul", None)
        if soul is not None and "soul" in ok:
            for name in soul.souls():
                text = soul.soul(name)
                if text.strip():
                    out["soul:" + name] = {"text": text}
        if soul is not None and "mind" in ok:
            out["mind:constitution"] = {"text": soul.constitution()}
        if "mind" in ok:                       # дела по расписанию (утренняя сводка, итоги) — телефону только показать: делает компьютер
            from when import describe_repeat
            jobs = []
            for r in list(h.reminders.items):
                if r.get("kind") != "job":
                    continue
                try:
                    at = int(dt.datetime.fromisoformat(r["at"]).timestamp() * 1000)
                except (KeyError, ValueError):
                    continue
                try:
                    rep = describe_repeat(r.get("repeat")) if r.get("repeat") else ""
                except Exception:  # noqa: BLE001
                    rep = ""
                jobs.append({"text": str(r.get("text", ""))[:200], "at": at, "repeat": rep, "paused": bool(r.get("paused"))})
            # своя запись у каждого компьютера (jobs-<устройство>): два компьютера не перетирают друг друга по кругу;
            # без дел — не шлём (а если раньше были — шлём пустой список, чтобы телефон их убрал)
            if jobs or self.state.get("jobs_sent"):
                out["mind:jobs-" + self.state["device"]] = {"items": sorted(jobs, key=lambda j: j["at"])[:30]}
            self.state["jobs_sent"] = bool(jobs)
        diary = getattr(h, "diary", None)
        if diary is not None and "mind" in ok and (diary.data.get("insights") or {}).get("lines"):
            ins = diary.data["insights"]
            out["mind:insights"] = {"day": ins.get("day", ""), "title": ins.get("title", ""), "lines": list(ins.get("lines") or [])}
        if "diary" in ok:
            d = h.workspace.ensure() / "Дневник"
            titles = (diary.data.get("titles") if diary is not None else None) or {}
            for p in sorted(d.glob("*.md"), reverse=True)[:DIARY_DAYS] if d.is_dir() else []:
                try:
                    dt.date.fromisoformat(p.stem)
                    text = p.read_text(encoding="utf-8")
                except (ValueError, OSError):
                    continue
                t = titles.get(p.stem) or {}
                out["diary:" + p.stem] = {"text": text[:NOTE_MAX], "title": t.get("title", ""), "mood": t.get("mood", "")}
        ob = getattr(h, "obsidian", None)
        if ob is not None and "vault" in ok and ob.sync_all():
            self._snap_vault(out, ob)
        pm = getattr(h, "payments", None)
        if pm is not None and "bill" in ok:
            with pm._lock:
                for b in pm.bills:
                    out["bill:" + b["id"]] = dict(b)
                for x in pm.pays:
                    out["pay:" + x["id"]] = dict(x)
        if pm is not None and "payfile" in ok:
            self._snap_payfiles(out, pm)
        if "safe" in ok:
            self._snap_safe(out)
        if "plugin" in ok and not self.HOME and getattr(h, "plugins", None) is not None:
            self._snap_plugins(out)
        dn = getattr(h, "done", None)
        if dn is not None and "done" in ok:            # сделанные дела (done.py) — как doneList() на телефоне
            with dn._lock:
                for x in dn.items:
                    out["done:" + x["id"]] = {"title": x["title"], "at": int(x["at"]), "src": x.get("src") or "", "rid": x.get("rid") or ""}
        tasks = getattr(h, "tasks", None)
        if tasks is not None and "task" in ok:
            for t in sorted(tasks.tasks.values(), key=lambda x: str(x.data.get("updated", "")), reverse=True)[:TASKS_SHOWN]:
                dd = t.data
                out["task:" + t.id] = {"title": dd.get("title", ""), "status": dd.get("status", ""), "goal": str(dd.get("goal", ""))[:400],
                                       "result": str(dd.get("result", ""))[:1200], "error": str(dd.get("error", ""))[:300],
                                       "question": str(dd.get("question", ""))[:400], "activity": str(dd.get("activity", ""))[:200],
                                       "updated": dd.get("updated", ""), "created": dd.get("created", ""),
                                       "outputs": [str(o.get("path", ""))[-80:] for o in (dd.get("outputs") or [])][:8],
                                       "files": dd.get("files") or []}

    def _facts(self):
        try:
            text = (self.host.workspace.ensure() / MEMORY).read_text(encoding="utf-8")
        except OSError:
            return []
        out = []
        for line in text.splitlines():
            m = _FACT.match(line.strip())
            if m:
                out.append(m.group(1).strip())
        return out

    def _pfacts(self):
        """Своя память персонажей: {имя: [факты]} — по файлам «Память/Персонажи/<имя>.md»."""
        out = {}
        try:
            folder = self.host.workspace.ensure() / "Память" / "Персонажи"
            files = sorted(folder.glob("*.md")) if folder.is_dir() else []
        except OSError:
            return out
        for f in files[:40]:
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            facts = [m.group(1).strip() for ln in lines if (m := _FACT.match(ln.strip()))]
            if facts:
                out[f.stem] = facts[-300:]
        return out

    def _apply_pmemory(self, iid, d, deleted):
        h = self.host
        if iid == "own":                                  # у кого своя память — с другого устройства, если новее
            if deleted or not isinstance(d.get("names"), list):
                return None
            if int(d.get("at") or 0) > int(h.s.get("persona_memory", "at") or 0):
                h.s.update({"persona_memory": {"own": [str(x)[:40] for x in d["names"] if x][:40], "at": int(d.get("at") or 0)}})
                try:
                    h.emit("settings", settings=h.s.snapshot())
                except Exception:  # noqa: BLE001
                    pass
            return None
        ws = h.workspace
        if not deleted:
            who, fact = str(d.get("who") or "").strip()[:40], re.sub(r"\s+", " ", str(d.get("text") or "").strip())
            if who and fact and _fact_id(fact) not in {_fact_id(x) for x in self._pfacts().get(who, [])}:
                ws.remember(fact, who=who)
            return None
        pre = iid.split("-", 1)[0]                        # удаление — без текста: файл по отпечатку имени, строку по id факта
        fid = iid.split("-", 1)[1] if "-" in iid else ""
        for name in self._pfacts():
            if _pmem_id(name, "").split("-", 1)[0] != pre:
                continue
            from workspace import persona_mem_rel
            p = ws.ensure() / persona_mem_rel(name)
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            keep = [ln for ln in lines if not ((m := _FACT.match(ln.strip())) and _fact_id(m.group(1)) == fid)]
            if len(keep) != len(lines):
                p.write_text("\n".join(keep) + "\n", encoding="utf-8")
        return None

    def _hash_of(self, snap, key):
        if key + "#h" in snap:
            return snap[key + "#h"]
        return _h(snap[key])

    # ---------- применить чужое изменение ----------

    def _apply(self, it):
        """Применяет запись с другого устройства. -> False, если она осознанно не легла здесь (прошедшее разовое
        напоминание, удаление души или дневника, чужой ход задачи, хранилище выключено): в idx она помечается skip,
        и её отсутствие у нас не уходит в облако удалением. Как в syncApply() в app.js."""
        kind, iid, d = it["kind"], it["id"], it.get("data") or {}
        deleted = it.get("deleted")
        if kind == "reminder":
            if deleted:
                self.host.reminders.remove(iid)
                return
            at = dt.datetime.fromtimestamp(int(d.get("at") or 0) / 1000).replace(microsecond=0)
            if not d.get("repeat") and at < dt.datetime.now() - dt.timedelta(minutes=5) and not self.host.reminders.get(iid):
                return False                               # разовое и уже прошло — звенеть задним числом незачем
            self.host.reminders.upsert({"id": iid, "at": at.isoformat(timespec="seconds"), "text": d.get("text") or "Напоминание",
                                        "repeat": d.get("repeat") or None, "kind": d.get("kind") or "reminder",
                                        "paused": bool(d.get("paused")), **({"note_id": d.get("note") or ""} if "note" in d else {})})
        elif kind == "money":
            if deleted:
                self.host.money.delete(iid)
            elif float(d.get("amount") or 0) > 0:
                self.host.money.upsert(dict(d, id=iid))
        elif kind == "note":
            return self._apply_note(iid, d, deleted, it.get("updated"))
        elif kind == "memory":
            self._apply_fact(iid, d.get("text") or "", deleted)
        elif kind == "pmemory":
            return self._apply_pmemory(iid, d, deleted)
        elif kind == "vault":
            return self._apply_vault(iid, d, deleted, it)
        elif kind == "safe":
            return self._apply_safe(iid, d, deleted, it)
        elif kind in EXTRA_KINDS:
            return self._apply_extra(kind, iid, d, deleted, it.get("updated"))

    # ---------- всё хранилище Obsidian (по желанию): одинаковое на всех компьютерах ----------
    def _vault_files(self, ob):
        """-> (корень хранилища или None, {путь в хранилище: Path}) — тексты .md, кроме папки ассистента (она ходит
        своими видами записей), служебных и скрытых папок (SKIP_DIRS из obsidian.py) и корзины; не больше VAULT_FILES."""
        v = ob.vault()
        mir = ob.mirror()
        if v is None:
            return None, {}
        out = {}
        from obsidian import SKIP_DIRS
        for p in v.rglob("*.md"):
            try:
                rel = p.relative_to(v)
            except ValueError:
                continue
            parts = rel.parts
            if any(x in SKIP_DIRS or x.startswith(".") for x in parts[:-1]) or (mir is not None and parts[0] == mir.name):
                continue
            out[rel.as_posix()] = p
            if len(out) >= VAULT_FILES:
                break
        return v, out

    def _snap_vault(self, out, ob):
        v, files = self._vault_files(ob)
        if v is None:
            return
        vmap = self.state.setdefault("vmap", {})              # id → путь (удаление приходит без пути)
        cache = self.state.setdefault("vt", {})
        for rel, p in files.items():
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size > VAULT_MAX:
                continue
            vid = "v" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:16]     # id из пути: одинаков на всех компьютерах
            vmap[vid] = rel
            key = "vault:" + vid
            out[key + "#t"] = st.st_mtime_ns // 1_000_000
            sig = f"{st.st_mtime_ns}:{st.st_size}"
            c = cache.get(rel)
            if c and c[0] == sig:
                out[key] = None
                out[key + "#h"] = c[1]
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            d = {"path": rel, "text": text}
            out[key] = d
            cache[rel] = [sig, _h(d)]
        for rel in [r for r in cache if r not in files]:
            cache.pop(rel, None)

    def _really_gone(self, key):
        """Запись пропала из снимка — это удаление, только если её источника правда нет. Отключённый диск с хранилищем,
        выключенная галочка «всё хранилище», заметка сверх предела или больше 300 КБ, файл, который сейчас не читается, —
        не удаление: иначе другие устройства отправили бы эти заметки в корзину."""
        kind, iid = key.split(":", 1)
        if kind == "note":
            rel = self.state.get("map", {}).get(iid)
            return not (rel and (self._notes_root() / rel).exists())
        if kind == "vault":
            ob = getattr(self.host, "obsidian", None)
            v = ob.vault() if ob is not None else None
            if v is None or not ob.sync_all():
                return False
            rel = self.state.get("vmap", {}).get(iid)
            return not (rel and (v / rel).exists())
        if kind in ("soul", "mind", "diary", "task", "done", "persona", "bill", "pay", "payfile", "safe", "plugin") and self.state.get("_extra_failed"):
            return False
        if kind == "plugin":                      # удаление — только если плагин был здесь и его папки больше нет (не «не влез»,
            import plugin_sync as PS              # не «не прочитался», не «ещё не собрался из кусков»)
            pid, _, i = iid.partition(".")
            c = (self.state.get("plg") or {}).get(pid)
            P = getattr(self.host, "plugins", None)
            if P is None or pid not in (self.state.get("plg_had") or {}):
                return False
            if not PS.present(P, pid):
                return True
            return bool(i) and c is not None and i.isdigit() and int(i) >= c[2]     # сборка стала короче — лишний кусок
        if kind == "safe":                        # выключили здесь, мастер-пароль сменили, сейф не открылся — не удаление
            vt = getattr(self.host, "vault", None)
            if iid == "key" or vt is None or self._safe_on() is None or self.state.get("_safe_failed"):
                return False
            try:
                return vt.get(iid) is None
            except Exception:  # noqa: BLE001
                return False
        if kind == "payfile":                     # файл ещё не пришёл целиком или не читается — не удаление; удаление — когда
            pm = getattr(self.host, "payments", None)        # ни один счёт и ни одна оплата его больше не помнят
            rel = (self.state.get("pfmap") or {}).get(iid.split(".")[0])
            return pm is None or not rel or rel not in pm.att_paths()
        return True

    def _vault_read(self, vid):
        ob = getattr(self.host, "obsidian", None)
        rel = self.state.get("vmap", {}).get(vid)
        v = ob.vault() if ob is not None else None
        if not rel or v is None:
            return None
        try:
            return {"path": rel, "text": (v / rel).read_text(encoding="utf-8")}
        except (OSError, UnicodeDecodeError):
            return None

    def _apply_vault(self, vid, d, deleted, it):
        """Чужая правка заметки хранилища. Удаление — в корзину Obsidian (.trash), не насовсем. Пришедшая версия
        ложится поверх здешней, но если здесь заметку правили (текст не совпадает с версией b, с которой облако было
        согласно) и это не первая встреча с ней либо здешний файл новее пришедшего, — здешний текст сохраняется рядом
        копией «(конфликт, устройство дата)». Так ничья правка не теряется молча (см. prev/lost в run_once)."""
        ob = getattr(self.host, "obsidian", None)
        v = ob.vault() if ob is not None else None
        if v is None or not ob.sync_all():
            return False
        rel = str(d.get("path") or self.state.get("vmap", {}).get(vid) or "")
        relp = Path(rel)
        # путь пришёл из облака: не даём выйти за пределы хранилища и писать в служебные папки и не-.md файлы
        if not rel or relp.is_absolute() or ".." in relp.parts or relp.suffix.lower() != ".md" or relp.parts[0] in (".obsidian", ".trash"):
            return False
        p = v / relp
        if deleted:
            if p.exists():
                dst = v / ".trash" / relp
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    dst = dst.with_name(f"{dst.stem} {int(time.time())}{dst.suffix}")
                shutil.move(str(p), str(dst))
            self.state.get("vt", {}).pop(rel, None)
            return None
        text = str(d.get("text") or "")
        self.state.setdefault("vmap", {})[vid] = rel
        if p.exists():
            try:
                cur = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                cur = None
            if cur == text:
                return None
            base = (self.state.get("idx", {}).get("vault:" + vid) or {}).get("b")
            local_edit = cur is not None and _h({"path": rel, "text": cur}) != base
            newer_here = p.stat().st_mtime * 1000 > int(it.get("updated") or 0)
            if cur is not None and local_edit and (base is not None or newer_here):
                alt = p.with_name(f"{p.stem} (конфликт, {self.host.device_name()} {dt.datetime.now():%d.%m %H-%M}){p.suffix}")
                alt.write_text(cur, encoding="utf-8")
                log.info("🔄 Хранилище: «%s» правили и здесь, и на другом устройстве — здешняя версия рядом: %s", rel, alt.name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return None

    def _apply_persona(self, iid, d, deleted):
        """Свой персонаж с телефона: создать, обновить (имя, пол, роль, характер, цвет, облик) или удалить. Встроенных и из
        галереи не трогаем. Характер с телефона короткий («весёлая, отвечает коротко») — дописываем «Ты — имя, роль.»"""
        pers = getattr(self.host, "personas", None)
        if pers is None or not hasattr(pers, "own_ids") or not re.fullmatch(r"[\w-]{1,40}", iid or ""):
            return False
        if iid in pers.fixed_ids():
            return False
        cur = next((p for p in pers.all() if p.get("id") == iid), None)
        if deleted:
            if cur is not None:
                pers.delete(iid)
                log.info("🔄 Персонаж «%s» удалён на другом устройстве", cur.get("name"))
            return None
        name = str(d.get("name") or "").strip()[:24]
        if not name:
            return False
        about, role = str(d.get("about") or "").strip()[:4000], str(d.get("role") or "").strip()[:60]
        char = about if re.match(r"\s*Ты\s", about) else f"Ты — {name}{', ' + role if role else ''}. {about}".strip()
        p = {"id": iid, "name": name, "gender": "male" if d.get("gender") == "male" else "female", "role": role, "about": about,
             "color": d.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(d.get("color") or "")) else "#8A9BFF",
             "character": char, "wake": [name.lower()]}
        av = str(d.get("avatar") or "")
        if av.startswith("data:image/") and (cur is None or pers.avatar_data_url(cur) != av):
            p["avatar_data"] = av
        if cur is not None and all(cur.get(k) == p[k] for k in ("name", "gender", "role", "color", "character")) and "avatar_data" not in p:
            return None
        pers.save(p)
        log.info("🔄 Персонаж «%s» — с другого устройства", name)
        return None

    def _any_key(self):
        """Ключ есть, а шифрование здесь выключено (выключили только здесь) — открыть пришедшее всё равно можно."""
        ks = getattr(self.host, "sync_key", None)
        cur = ks.get() if ks is not None else None
        return cur["k"] if cur else None

    def _apply_mark(self, d, deleted):
        """Метка «шифрование включено» с другого устройства: ключ есть — включаем и здесь; нет — просим его у своих
        устройств (конверт close). Снятую метку не слушаем: выключают шифрование только на самом устройстве."""
        if deleted or not (d or {}).get("on"):
            return False
        ks = getattr(self.host, "sync_key", None)
        s = getattr(self.host, "s", None)
        if ks is not None and ks.get():
            if s is not None and not s.get("sync", "e2e") and not self.state.get("e2e_off_here"):
                s.update({"sync": {"e2e": True}})
                self.state["reseal_all"] = True
                log.info("🔐 Синхронизация зашифрована на другом устройстве — шифрую и здесь")
            return False
        self.state["e2e_remote"] = True
        want = getattr(self.host, "sync_key_wanted", None)
        if callable(want):
            want()
        return False

    def _apply_extra(self, kind, iid, d, deleted, it_updated=0):
        """Душа, конституция, выводы, дневник — удалением не стираются: у другого устройства запись могла просто
        выпасть из снимка (дневник там — за DIARY_DAYS дней), а написанное терять нельзя. Разговор (dayturn) и задачу (taskreq)
        с телефона забираем к себе; в следующем снимке их нет — и run_once сам шлёт их удаление, облако их забывает.
        Ход задач другого компьютера (task) — только для телефона: пропускаем."""
        h = self.host
        if kind == "persona":
            return self._apply_persona(iid, d, deleted)
        if kind in ("bill", "pay", "payfile"):
            return self._apply_pay(kind, iid, d, deleted)
        if kind == "plugin":
            return self._apply_plugin(iid, d, deleted, it_updated)
        if kind == "mind" and iid == "e2e":
            return self._apply_mark(d, deleted)
        if kind in ("soul", "mind", "diary", "task") and deleted:
            return False
        if kind == "soul":
            text = _mind_text(d, MIND_MAX)
            if text is None:
                log.warning("🔄 Душа «%s» с другого устройства не принята: не похожа на душу (длиннее %d знаков или не текст)", iid, MIND_MAX)
                return False
            if text.strip() and text.strip() != h.soul.soul(iid).strip():
                h.soul.save_soul(iid, text)
                log.info("🔄 Душа «%s» — правка с другого устройства", iid)
        elif kind == "mind" and iid == "constitution":
            text = _mind_text(d, MIND_MAX)
            if text is None:
                log.warning("🔄 Конституция с другого устройства не принята: длиннее %d знаков или не текст", MIND_MAX)
                return False
            old = h.soul.constitution()
            if text.strip() and text.strip() != old.strip():
                try:
                    h.soul.save_constitution(text)
                except ValueError as e:
                    log.warning("🔄 Конституция с другого устройства не принята: %s", e)
                    return False
                # принципы помощника поменялись не здесь — прежние сохраняем рядом и говорим человеку: если это не он,
                # вернуть их можно одним копированием, а ключ аккаунта — сменить
                try:
                    prev = h.workspace.ensure() / CONST_PREV
                    prev.parent.mkdir(parents=True, exist_ok=True)
                    prev.write_text(old, encoding="utf-8")
                except Exception as e:  # noqa: BLE001
                    log.warning("прежняя конституция не сохранилась: %s", e)
                log.info("🔄 Конституция — правка с другого устройства (прежняя — %s)", CONST_PREV)
                if callable(getattr(h, "push", None)):
                    try:
                        h.push("Конституция изменена на другом устройстве",
                               f"Принципы помощника пришли синхронизацией. Прежние сохранены: «{CONST_PREV}». "
                               "Если меняли не вы — верните их в «Душе» и перевыпустите ключ Dewiar в кабинете.")
                    except Exception:  # noqa: BLE001
                        pass
        elif kind == "mind" and iid == "insights":
            cur = h.diary.data.get("insights") or {}
            if d.get("lines") and str(d.get("day", "")) > str(cur.get("day", "")):
                h.diary.data["insights"] = {"day": d.get("day"), "title": d.get("title", ""), "lines": list(d.get("lines") or [])}
                h.diary._save()
        elif kind == "diary":
            try:
                dt.date.fromisoformat(iid)
            except ValueError:
                return False
            p = h.workspace.ensure() / "Дневник" / f"{iid}.md"
            text = _mind_text(d, DIARY_MAX)
            if text is None:
                return False
            if text.strip() and (not p.exists() or p.read_text(encoding="utf-8").strip() != text.strip()):
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
        elif kind == "dayturn":
            if not deleted and self._q_seen(iid, add=True):
                log.info("🔄 Разговор с телефона %s уже в дневнике (пришёл другим путём) — пропускаю", iid)
            elif not deleted:
                when = None
                try:
                    when = dt.datetime.fromtimestamp(int(d.get("ts") or 0) / 1000)
                except (ValueError, OSError, OverflowError):
                    pass
                h.diary.log.add(str(d.get("you") or ""), str(d.get("bot") or ""), who=str(d.get("who") or ""), via="телефон", when=when)
        elif kind == "taskreq":
            # Два компьютера взялись бы за одну задачу оба: сначала занимаем её в облаке (taken_by, с prev — облако
            # отклонит, если занял другой), и только занявший берётся — _claim_tasks после обмена.
            if deleted:
                return None
            if d.get("taken_by") and d.get("taken_by") != self.state.get("device"):
                return False
            if d.get("to") and d.get("to") != self.state.get("device") and not self.HOME:   # задача другому компьютеру («на рабочем…», 0.56)
                return False                       # (по Wi-Fi её берём — HomeSync перешлёт её тому через облако)
            if str(d.get("goal") or d.get("title") or "").strip() and not d.get("taken_by"):
                self._claims[iid] = (dict(d), int(it_updated or 0))      # взятую уже по Wi-Fi тоже занимаем (другому не взять), но не начинаем
        elif kind == "task" and isinstance(d, dict) and d.get("want") in ("delete", "stop", "answer"):
            self._task_want(iid, d)
            return False
        elif kind == "task" or (kind == "mind" and iid.startswith("jobs")):
            return False                                   # ход задач и дела по расписанию другого компьютера — для телефона
        elif kind == "done":
            dn = getattr(h, "done", None)
            if dn is None:
                return False
            if deleted:
                dn.delete(iid)
            else:
                dn.upsert(iid, d)
            emit = getattr(h, "emit", None)
            if emit is not None:
                try:
                    emit("done", **dn.public())
                except Exception:  # noqa: BLE001
                    log.debug("дела: emit", exc_info=True)
        return None

    def _q_seen(self, iid, add=False):
        """Разговор (dayturn) и задача (taskreq) с телефона, которые этот компьютер уже взял — облачным обменом или по Wi-Fi
        (рецензия 04.11: ответ облака потерялся, телефон отдал то же по Wi-Fi — разговор дважды в дневнике, задача дважды).
        Набор общий у облачной и домашней синхронизации (sibling); add — отметить. -> было ли уже."""
        seen = self.state.setdefault("qseen", {})
        sib = getattr(self, "sibling", None)
        hit = iid in seen or (sib is not None and iid in (sib.state.get("qseen") or {}))
        if add and not hit:
            seen[iid] = int(time.time())
            if len(seen) > 3000:                          # месяц разговоров с запасом; старые id телефон второй раз не пришлёт
                for k in sorted(seen, key=seen.get)[:len(seen) - 2500]:
                    seen.pop(k, None)
        return hit

    # ---------- «Сейф паролей» между своими устройствами (вид safe; core/vault.py — SafeKey и формат) ----------
    def _safe_on(self):
        """Ключ сейфа, которым сейчас синхронизировать ({"k", "meta"}), или None — сейф здесь не синхронизируется."""
        sk, vt = getattr(self.host, "safe_key", None), getattr(self.host, "vault", None)
        return sk.active() if sk is not None and vt is not None else None

    def _snap_safe(self, out):
        """Записи сейфа -> safe:<id> (данные None, отпечаток — HMAC ключом сейфа; шифруем, только когда отправлять —
        _safe_read) и safe:key — открытые параметры. Сейф не открылся — ничего и пометка _safe_failed (не удаления)."""
        self.state["_safe_failed"] = False
        cur = self._safe_on()
        if cur is None:
            return
        from vault import item_ms, safe_hash
        try:
            items = self.host.vault.sync_items()
        except Exception as e:  # noqa: BLE001 — CryptError: ключ компьютера сменился
            self.state["_safe_failed"] = True
            log.warning("Синхронизация: сейф не открылся — его записи сейчас не отправляю: %s", e)
            return
        meta, kid = cur["meta"], cur["meta"]["kid"]
        out["safe:key"] = dict(meta)
        out["safe:key#t"] = int(meta["at"])
        for x in items:
            key = "safe:" + str(x.get("id"))
            out[key] = None
            out[key + "#h"] = safe_hash(cur["k"], kid, x)
            out[key + "#t"] = item_ms(x) or _now_ms()

    def _safe_read(self, iid):
        cur = self._safe_on()
        vt = getattr(self.host, "vault", None)
        if cur is None or vt is None:
            return None
        from vault import safe_seal
        try:
            x = vt.get(iid)
        except Exception:  # noqa: BLE001
            return None
        return safe_seal(cur["k"], cur["meta"]["kid"], x) if x else None

    def _apply_safe(self, iid, d, deleted, it):
        """Запись сейфа с другого устройства. Параметры (safe:key) запоминаем всегда — так здесь узнают, что сейф уже
        синхронизируется (студия спросит мастер-пароль). Записи — только когда здесь есть ключ того же мастер-пароля;
        иначе skip (без удаления своего), а когда ключ появится — safe_refetch() заберёт историю заново.
        Правка здесь новее пришедшей — оставляем свою (False: она уйдёт в облако следующим обменом)."""
        from vault import item_ms, safe_open
        h = self.host
        sk, vt = getattr(h, "safe_key", None), getattr(h, "vault", None)
        if sk is None or vt is None:
            return False
        if iid == "key":
            if deleted or not isinstance(d, dict):
                return False
            if sk.note(d):
                cur = sk.get()
                if cur and cur["meta"]["kid"] != d.get("kid") and sk.active() is None:
                    log.info("🔐 Мастер-пароль сейфа сменили на другом устройстве — сейф здесь ждёт новый")
                    self._safe_event()
            return None
        cur = self._safe_on()
        if cur is None:
            return False
        if deleted:
            if vt.sync_drop(iid):
                log.info("🔐 Сейф: запись удалена на другом устройстве")
                self._safe_event()
            return None
        if not isinstance(d, dict) or d.get("kid") != cur["meta"]["kid"] or not isinstance(d.get("c"), str):
            return False                                   # другим мастер-паролем (ещё не перешифровали) — ждём
        try:
            x = safe_open(cur["k"], d)
        except Exception as e:  # noqa: BLE001
            log.warning("Синхронизация: запись сейфа %s не открылась (%s) — пропускаю", iid, e)
            return False
        if not isinstance(x, dict) or x.get("id") != iid:
            return False
        upd = int(it.get("updated") or 0)
        x["mt"] = upd or int(x.get("mt") or 0)
        mine = vt.get(iid)
        if mine and item_ms(mine) > x["mt"]:
            return False                                   # здесь правили позже — своя уйдёт в облако
        if mine is None:                                   # тот же пароль под другим id (сейф заполняли на двух компьютерах) — одна запись
            for y in vt.sync_items():
                if (y["id"] != iid and y["name"].lower() == str(x.get("name") or "").lower() and y.get("value") == x.get("value")
                        and (y.get("kind") == "page") == (x.get("kind") == "page")):
                    vt.sync_drop(y["id"])
        if not vt.sync_put(x):
            return False
        self._safe_event()
        return None

    def _safe_event(self):
        emit = getattr(self.host, "emit", None)
        if callable(emit):
            try:
                emit("vault_changed")
            except Exception:  # noqa: BLE001
                pass

    def safe_refetch(self):
        """Ключ сейфа появился или сменился: забрать историю заново — записи, пропущенные без ключа, лягут теперь."""
        with self._lock:
            self.state["rev"] = 0
            self._save()
        self.soon.set()

    def safe_status(self):
        sk = getattr(self.host, "safe_key", None)
        cur = sk.get() if sk is not None else None
        rem = sk.remote() if sk is not None else None
        on = self._safe_on() is not None
        return {"on": on, "stale": bool(cur) and not on, "remote": bool(rem) and not on,
               "server": "safe" in (self.state.get("kinds") or ()), "failed": bool(self.state.get("_safe_failed"))}

    # ---------- свои плагины Лиры между компьютерами (вид plugin, core/plugin_sync.py) ----------
    def _snap_plugins(self, out):
        """Плагины Лиры -> plugin:<id> (заголовок) и plugin:<id>.<i> (куски сжатой сборки; данные None + отпечаток, читаем,
        только когда отправлять — _plugin_read). Кэш plg {id: [подпись файлов, sha, кусков, code, name]}; сборка — в памяти."""
        import plugin_sync as PS
        P = self.host.plugins
        cache = self.state.setdefault("plg", {})
        had = self.state.setdefault("plg_had", {})
        mem = self.__dict__.setdefault("_plg_mem", {})
        seen = set()
        for pid, d in PS.made_dirs(P):
            sig = PS.signature(d, pid)
            c = cache.get(pid)
            if not c or c[0] != sig or pid not in mem:
                blob, info = PS.bundle(d, pid)
                if blob is None:
                    if not c:
                        if isinstance(info, str) and info.startswith("больше"):
                            log.info("🔄 Плагин %s не синхронизируется: %s", pid, info)
                        continue
                else:
                    c = [sig, hashlib.sha1(blob).hexdigest(), len(PS.parts(blob)), info["code"], info["name"]]
                    cache[pid] = c
                    mem[pid] = blob
            seen.add(pid)
            had[pid] = int(time.time())
            out["plugin:" + pid] = {"name": c[4], "sha": c[1], "n": c[2], "code": bool(c[3]), "from": str(self.host.device_name())[:40]}
            for i in range(c[2]):
                out[f"plugin:{pid}.{i}"] = None
                out[f"plugin:{pid}.{i}#h"] = f"{c[1]}:{i}:{c[2]}"
        for pid in [p for p in cache if p not in seen]:
            cache.pop(pid, None)
            mem.pop(pid, None)
        self._plg_prune()

    PLG_STALE = 7 * 86400                    # куски сборки, которая так и не собралась (другой компьютер ушёл, сборку сменили)

    def _plg_prune(self):
        now = time.time()
        pin = self.state.get("plg_in") or {}
        for pid in [p for p, h in pin.items() if now - int(h.get("at") or 0) > self.PLG_STALE]:
            pin.pop(pid, None)
        root = self._plg_dir()
        if not root.is_dir():
            return
        for d in root.iterdir():
            try:
                cur = (pin.get(d.name) or {}).get("sha")
                for f in d.iterdir():
                    if not cur or not f.name.startswith(cur + ".") or now - f.stat().st_mtime > self.PLG_STALE:
                        if now - f.stat().st_mtime > 3600:          # кусок не той сборки (или старый) — через час убираем
                            f.unlink()
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    def _plugin_read(self, iid):
        import plugin_sync as PS
        pid, _, i = iid.partition(".")
        c = (self.state.get("plg") or {}).get(pid)
        blob = getattr(self, "_plg_mem", {}).get(pid)
        if not c or blob is None or not i.isdigit() or hashlib.sha1(blob).hexdigest() != c[1]:
            return None
        return PS.part_data(blob, c[1], int(i))

    def _plg_dir(self):
        return self.path.parent / "plugparts"

    def _apply_plugin(self, iid, d, deleted, it_updated=0):
        """Заголовок или кусок плагина с другого компьютера. Плагин ставится, когда пришли заголовок и все куски одной
        сборки и сошёлся отпечаток. Удаление заголовка — удалить плагин и здесь; удаление куска — ничего."""
        import plugin_sync as PS
        pid, _, i = iid.partition(".")
        if not PS.ID_RX.fullmatch(pid) or getattr(self.host, "plugins", None) is None:
            return False
        pdir = self._plg_dir() / pid
        if deleted:
            if not i:
                shutil.rmtree(pdir, ignore_errors=True)
                (self.state.get("plg_in") or {}).pop(pid, None)
                PS.remove(self.host, pid)
                (self.state.get("plg_had") or {}).pop(pid, None)
            return None
        if not isinstance(d, dict):
            return False
        sha = str(d.get("sha") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not isinstance(d.get("n"), int) or not 0 < d["n"] <= -(-PS.MAX // PS.CHUNK) + 1:
            return False
        if i:
            if not i.isdigit() or not 0 <= int(i) < d["n"] or d.get("i") != int(i):
                return False
            try:
                part = base64.b64decode(str(d.get("b64") or ""), validate=True)
            except ValueError:
                return False
            pdir.mkdir(parents=True, exist_ok=True)
            (pdir / f"{sha}.{int(i)}").write_bytes(part)
        else:
            self.state.setdefault("plg_in", {})[pid] = {"sha": sha, "n": d["n"], "from": str(d.get("from") or "")[:40], "at": int(time.time())}
        return self._plugin_try(pid)

    def _plugin_try(self, pid):
        """Все куски сборки на месте — поставить плагин. -> None (легло или ждём кусков), False — не принят."""
        import plugin_sync as PS
        head = (self.state.get("plg_in") or {}).get(pid)
        if not head:
            return None
        c = (self.state.get("plg") or {}).get(pid)
        pdir = self._plg_dir() / pid
        if c and c[1] == head["sha"]:                  # такая сборка здесь уже есть
            self.state["plg_in"].pop(pid, None)
            shutil.rmtree(pdir, ignore_errors=True)
            return None
        ps = [pdir / f"{head['sha']}.{k}" for k in range(head["n"])]
        if not all(p.is_file() for p in ps):
            return None
        blob = b"".join(p.read_bytes() for p in ps)
        self.state["plg_in"].pop(pid, None)
        shutil.rmtree(pdir, ignore_errors=True)
        b = PS.unpack(blob) if hashlib.sha1(blob).hexdigest() == head["sha"] else None
        if b is None:
            log.warning("🔄 Плагин %s с другого компьютера пришёл испорченным — пропускаю", pid)
            return False
        try:
            r = PS.install(self.host, pid, b, head)
            if not r:
                return False
            # здешнее сохранилось рядом (свои версии, правка до синхронизации) — сборку надо отправить, иначе отпечаток
            # «как легло у нас» спрятал бы её от других компьютеров. Только тогда: разница лишь в отброшенной чужой
            # программе старых версий или в обрезке по размеру — не повод (иначе два компьютера пересылали бы её по кругу)
            if r == "more":
                self.__dict__.setdefault("_plg_resend", set()).add(pid)
            return None
        except Exception as e:  # noqa: BLE001
            log.warning("🔄 Плагин %s с другого компьютера не поставился: %s", pid, e)
            return False

    # ---------- «Платежи»: счета, оплаты и вложения между компьютерами ----------
    def _pf_dir(self):
        return self.path.parent / "payparts"

    def _snap_payfiles(self, out, pm):
        """Вложения «Платежей» -> записи payfile:<id пути>.<номер куска> (данные None + отпечаток; читаем, только когда
        отправлять — _payfile_read). Отпечаток — по содержимому: кэш pf {путь: [размер:время, sha1, кусков]}."""
        root = Path(self.host.workspace.ensure())
        cache = self.state.setdefault("pf", {})
        pfmap = self.state.setdefault("pfmap", {})
        seen = set()
        for rel in pm.att_paths():
            p = root / rel
            try:
                st = p.stat()
            except OSError:
                continue
            if not p.is_file() or st.st_size > PF_MAX or st.st_size == 0:
                continue
            sig = f"{st.st_size}:{st.st_mtime_ns}"
            c = cache.get(rel)
            if not c or c[0] != sig:
                try:
                    c = [sig, hashlib.sha1(p.read_bytes()).hexdigest(), -(-st.st_size // PF_CHUNK)]
                except OSError:
                    continue
                cache[rel] = c
            fid = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
            pfmap[fid] = rel
            seen.add(rel)
            for i in range(c[2]):
                out[f"payfile:{fid}.{i}"] = None
                out[f"payfile:{fid}.{i}#h"] = f"{c[1]}:{i}:{c[2]}"
        for rel in [r for r in cache if r not in seen]:
            cache.pop(rel, None)

    def _payfile_read(self, iid):
        fid, _, i = iid.partition(".")
        rel = (self.state.get("pfmap") or {}).get(fid)
        c = (self.state.get("pf") or {}).get(rel or "")
        if not rel or not c or not i.isdigit():
            return None
        try:
            with open(Path(self.host.workspace.ensure()) / rel, "rb") as f:
                f.seek(int(i) * PF_CHUNK)
                part = f.read(PF_CHUNK)
        except OSError:
            return None
        import base64
        return {"path": rel, "i": int(i), "n": c[2], "sha": c[1], "b64": base64.b64encode(part).decode("ascii")}

    def _apply_pay(self, kind, iid, d, deleted):
        """Счёт, оплата или кусок вложения с другого компьютера. Вложение собирается, когда пришли все куски и сошёлся
        отпечаток; пишется только в «Платежи/Вложения/» (payments.att_ok)."""
        import base64
        from payments import att_ok
        h = self.host
        pm = getattr(h, "payments", None)
        if pm is None:
            return False
        if kind in ("bill", "pay"):
            if deleted:
                pm.sync_drop(kind, iid)
            elif pm.sync_put(kind, iid, d) is None:
                return False
            emit = getattr(h, "emit", None)
            if emit is not None:
                try:
                    emit("pay_saved", what="sync")
                except Exception:  # noqa: BLE001
                    log.debug("платежи: emit", exc_info=True)
            return None
        fid, _, i = iid.partition(".")
        if not re.fullmatch(r"[0-9a-f]{12}", fid) or not i.isdigit():
            return False
        root = Path(h.workspace.ensure())
        if deleted:
            rel = (self.state.get("pfmap") or {}).get(fid)
            if rel and att_ok(rel) and rel not in pm.att_paths():
                try:
                    (root / rel).unlink(missing_ok=True)
                except OSError:
                    pass
            shutil.rmtree(self._pf_dir() / fid, ignore_errors=True)
            return None
        rel, n, sha = str(d.get("path") or ""), d.get("n"), str(d.get("sha") or "")
        if not att_ok(rel) or hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12] != fid or not isinstance(n, int) \
                or not 0 <= int(i) < n <= -(-PF_MAX // PF_CHUNK) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            return False
        self.state.setdefault("pfmap", {})[fid] = rel
        dst = root / rel
        try:
            if dst.is_file() and hashlib.sha1(dst.read_bytes()).hexdigest() == sha:
                return None                                   # уже на месте
            part = base64.b64decode(str(d.get("b64") or ""), validate=True)
        except (OSError, ValueError):
            return False
        tmp = self._pf_dir() / fid
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / f"{sha}.{i}").write_bytes(part)
        parts = [tmp / f"{sha}.{k}" for k in range(n)]
        if all(x.is_file() for x in parts):
            blob = b"".join(x.read_bytes() for x in parts)
            if hashlib.sha1(blob).hexdigest() == sha:
                dst.parent.mkdir(parents=True, exist_ok=True)
                tmpf = dst.with_name(dst.name + ".part")
                tmpf.write_bytes(blob)
                tmpf.replace(dst)
                log.info("🔄 Платежи: вложение «%s» — с другого компьютера", dst.name)
            shutil.rmtree(tmp, ignore_errors=True)
        return None

    def _task_want(self, iid, d):
        """С телефона: «Удалить задачу», «Остановить», ответ на её вопрос (24.10, владелец: «Лира замучила напоминанием
        про задачу „Исследование“… попросил удалить — она не умеет, на телефоне не понятно, где удалить»). Телефон кладёт
        в облако запись задачи с want; задача не наша (другого компьютера) — молчим. Удалили — следующий снимок без неё,
        облако её забывает, телефон тоже."""
        tasks = getattr(self.host, "tasks", None)
        if tasks is None or iid not in tasks.tasks:
            return
        want = d.get("want")
        try:
            if want == "delete":
                title = tasks.tasks[iid].title
                tasks.delete(iid)
                log.info("🔄 Задача «%s» удалена с телефона", title)
            elif want == "stop":
                tasks.stop(iid)
            elif want == "answer" and str(d.get("text") or "").strip():
                tasks.answer(iid, str(d.get("text"))[:4000])
        except (KeyError, ValueError) as e:
            log.info("🔄 Задача с телефона (%s): %s", want, e)

    def _upload_outputs(self, url, token):
        """Файлы-результаты законченных задач (показанные show, до 10 МБ) — в облако (?p=/files), один раз каждый:
        телефон открывает и сохраняет их из «Задач» и из разговора. Облако старое (нет /files) — не пробуем сутки."""
        tasks = getattr(self.host, "tasks", None)
        if tasks is None or time.time() < float(self.state.get("files_off_until") or 0):
            return
        for t in list(tasks.tasks.values())[-TASKS_SHOWN * 2:]:
            if t.data.get("status") not in ("done", "failed", "stopped") or not t.data.get("outputs"):
                continue
            sent = t.data.setdefault("cloud_files", {})
            files, changed = [], False
            for o in (t.data.get("outputs") or [])[-8:]:
                p = t.dir / str(o.get("path") or "")
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size > 10 * 1024 * 1024:
                    continue
                key = f"{o.get('path')}|{st.st_size}|{int(st.st_mtime)}"
                if key not in sent:
                    try:
                        r = httpx.post(url, params={"p": "/files", "name": p.name}, content=p.read_bytes(),
                                       headers={"Authorization": "Bearer " + token}, timeout=120)
                    except (httpx.HTTPError, OSError) as e:
                        log.info("Файл задачи не отправлен: %s", e)
                        return
                    if r.status_code == 404:
                        self.state["files_off_until"] = time.time() + 86400
                        return
                    if r.status_code >= 400:
                        continue
                    try:
                        sent[key] = r.json()["id"]
                    except (ValueError, KeyError):
                        continue
                    changed = True
                files.append({"name": p.name, "id": sent[key], "size": st.st_size, "title": str(o.get("title") or p.stem)[:120]})
            if changed or t.data.get("files") != files:
                t.data["files"] = files
                t.save()

    def _claim_tasks(self, url, headers, idx):
        """Задачи с телефона, увиденные в этом обмене: записать в облако taken_by с prev (версия, которую видели).
        Облако приняло — задача наша: создаём; отклонило (lost) — её уже взял другой компьютер. В следующем снимке
        записи нет — run_once пошлёт удаление, как и раньше."""
        claims, self._claims = self._claims, {}
        if not claims:
            return
        h = self.host
        now = int(time.time() * 1000)
        body = {"since": int(self.state.get("rev") or 0), "device": self.state["device"], "name": h.device_name(), "kinds": ["taskreq"],
                "changes": [{"kind": "taskreq", "id": iid, "data": dict(d, taken_by=self.state["device"]), "updated": now, "prev": prev}
                            for iid, (d, prev) in claims.items()]}
        try:
            r = httpx.post(url + "?p=/sync", json=body, headers=headers, timeout=30)
            lost = set(r.json().get("lost") or ()) if r.status_code < 400 else None
        except (httpx.HTTPError, ValueError):
            lost = None
        for iid, (d, prev) in claims.items():
            key = "taskreq:" + iid
            if lost is None:                                  # облако не ответило — попробуем занять в следующий обмен
                self._claims[iid] = (d, prev)
                idx.pop(key, None)
                continue
            if key in lost:                                   # уже взял другой компьютер
                idx[key] = {"h": None, "u": prev, "skip": True}
                self._q_seen(iid, add=True)
                continue
            idx[key] = {"h": None, "u": now}
            if self._q_seen(iid, add=True):                   # эту задачу этот компьютер уже взял по Wi-Fi — второй раз не начинаем
                log.info("🔄 Задача с телефона %s уже взята по Wi-Fi — второй раз не начинаю", iid)
                continue
            self._start_task(d)

    def _start_task(self, d):
        """Задача с телефона (или другого устройства) — в «Задачи» этого компьютера. -> задача или None."""
        h = self.host
        goal = str(d.get("goal") or d.get("title") or "").strip()
        try:
            who = str(d.get("from") or "").strip()[:40]
            t = h.tasks.create(str(d.get("title") or goal[:50]), goal + (f"\n\n(Задачу поставили с устройства «{who}».)" if who else "\n\n(Задачу поставили с телефона — результат он увидит.)"))
        except (OSError, ValueError, AttributeError) as e:     # не роняем весь обмен из-за одной задачи
            log.warning("Задача с телефона не создалась: %s", e)
            return None
        log.info("🔄 Задача с телефона: «%s»", t.title)
        try:
            h.push("Задача с " + (f"«{who}»" if who else "телефона"), f"Взялся: «{t.title}». Ход — в «Задачах», на телефоне тоже.", telegram=False)
        except Exception:  # noqa: BLE001
            pass
        return t

    def send_taskreq(self, data, sender=None, iid=None, updated=None):
        """Задача другому своему устройству («сделай на рабочем компьютере…», 0.56): запись taskreq сразу в облако.
        data — {title, goal, to (id компьютера) или cloud}; от кого — имя этого (или sender — телефон, чью задачу этот
        компьютер пересылает с Wi-Fi). Шифрование включено — запечатана (кроме задачи для облака: её читает сервер).
        iid и updated — повтор той же задачи (ответ облака потерялся): та же запись, с prev — если её уже занял тот
        компьютер, облако её не перепишет (lost), и второй раз он не возьмётся. -> id"""
        token, link, url = self.host.credentials()
        if not token:
            raise SyncError("нет входа в Dewiar — задачу другому устройству не передать")
        iid = iid or "p" + uuid.uuid4().hex[:12]
        upd = int(updated or _now_ms())
        d = dict(data, ts=upd, **{"from": str(sender or self.host.device_name())[:40]})   # sender — пересылаем чужую (телефона по Wi-Fi)
        ek = self.e2e_key()
        body_data = _seal(ek, d) if ek and self._sealable("taskreq", iid, d) else d
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
        if link and link != token:
            headers["X-Sync-Link"] = link
        body = {"since": int(self.state.get("rev") or 0), "device": self.state["device"], "name": self.host.device_name(), "app": "pc", "ver": _version(),
                "kinds": ["taskreq"], "changes": [{"kind": "taskreq", "id": iid, "data": body_data, "updated": upd}]}
        if updated:
            body["changes"][0]["prev"] = upd
        try:
            r = httpx.post(url + "?p=/sync", json=body, headers=headers, timeout=30)
        except httpx.HTTPError as e:
            raise SyncError(f"облако не ответило: {e}") from e
        if r.status_code >= 400:
            raise SyncError(f"облако ответило {r.status_code}")
        with self._lock:                                # своё не забирать обратно как чужую задачу
            self.state.setdefault("idx", {})["taskreq:" + iid] = {"h": None, "u": body["changes"][0]["updated"], "skip": True}
            self._save()
        return iid

    def _apply_note(self, sid, d, deleted, upd=None):
        """Удаление — в корзину Dewiar (workspace.remove). Новая заметка получает свободное имя по заголовку в своей
        папке; известная перезаписывается на месте — смена заголовка или папки на другом устройстве файл не переносит.
        Имена из облака чистит _clean_name, «..» отбрасывается: выйти из «Заметок» нельзя."""
        al = self._note_alias(sid, d, deleted)
        if al is not None:                                 # второе имя заметки: правка — в тот же файл
            self.state.setdefault("alias", {})[sid] = al
            arel = self.state["map"].get(al)
            ah = self.state.setdefault("alias_h", {})
            if deleted:
                # удалили по второму имени (там, где оно главное): файл после склейки здесь не меняли — удаляем и его,
                # наше удаление уйдёт под нашим id; меняли — оставляем (правка дороже удаления)
                if arel and ah.get(sid) and self._file_h(arel) == ah.get(sid):
                    log.info("🔄 Заметка %s удалена на другом устройстве (второе имя %s) — удаляю", arel, sid)
                    self._apply_note(al, {}, True)
                    self.state["alias"].pop(sid, None)
                ah.pop(sid, None)
                return False
            log.info("🔄 Заметка %s — та же, что %s: склеиваю, а не кладу второй", sid, al)
            self._apply_note(al, d, False, upd)
            arel = self.state["map"].get(al)
            if arel:
                ah[sid] = self._file_h(arel)
            return False                                   # skip: удалением второе имя отсюда не уйдёт
        ws = self.host.workspace
        root = self._notes_root()
        rel = self.state["map"].get(sid)
        if not rel and (rel := self._sib_rel(sid)):        # эту заметку уже положила соседняя синхронизация — тот же файл
            self.state["map"][sid] = rel
        if deleted:
            if rel and (root / rel).exists():
                from workspace import _locked
                if _locked(root / rel):                 # заметка с замком: удаление с другого устройства не принимаем —
                    os.utime(root / rel, None)          # она новее удаления и вернётся туда со следующей отправкой
                    return False
                ws.remove(f"{NOTES}/{rel}")
            self.state["map"].pop(sid, None)
            self._pad_event(rel, True)
            return
        if not rel:
            from workspace import _clean_name
            folder = "/".join(_clean_name(x) for x in str(d.get("folder") or "").split("/") if x.strip() and x not in (".", ".."))
            base = _clean_name(d.get("title") or "Заметка") or "Заметка"
            rel = (folder + "/" if folder else "") + base + ".md"
            n = 2
            taken = set(self.state["map"].values())
            while (root / rel).exists() or rel in taken:
                rel = (folder + "/" if folder else "") + f"{base} ({n}).md"
                n += 1
            self.state["map"][sid] = rel
        else:
            if self._note_conflict(sid, rel, d, upd) == "mine":   # до переноса в другую папку: отпечаток — с прежней папкой
                return None                                # здешняя правка позже — она остаётся, пришедшая — копией рядом
            rel = self._move_to_folder(sid, rel, d, root)
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        text = str(d.get("text") or "")
        pad = rel.startswith(PAD_DIR + "/") and rel.count("/") == 1
        from workspace import FRONT_RX
        fm = FRONT_RX.match(text)                         # шапка «---» (Obsidian, Keep) — первой, заголовок — после неё
        front, rest = (text[:fm.end()], text[fm.end():]) if fm and fm.group(2).strip() else ("", text)
        if not rest.lstrip().startswith("#") and not pad:  # заметка с телефона: заголовок — как у заметок компьютера
            text = front + ("\n" if front else "") + f"# {d.get('title') or p.stem}\n\n{rest.lstrip(chr(10))}\n"   # (вкладки блокнота — как есть)
        p.write_text(text, encoding="utf-8")
        try:                                              # время файла — время правки на том устройстве, а не «сейчас»:
            u = int(upd or 0)                             # иначе мост («Дома по Wi-Fi») понесёт старую копию дальше как
            if 0 < u <= _now_ms():                        # свежую, и она перебьёт более позднюю правку (рецензия 04.11, S4)
                os.utime(p, ns=(u * 1_000_000, u * 1_000_000))
        except (OSError, ValueError, OverflowError):
            pass
        self._pad_event(rel, False)

    def _file_h(self, rel):
        try:
            return hashlib.sha1((self._notes_root() / rel).read_bytes()).hexdigest()
        except OSError:
            return None

    def _note_conflict(self, sid, rel, d, upd=None):
        """Заметку правили и здесь (после последнего обмена — отпечаток файла не тот, что в idx), и на другом устройстве, —
        ни одна правка не теряется (рецензия 04.11: две правки одной заметки на двух компьютерах — одна пропадала молча;
        часы одного отстают — пропадала более поздняя). Здешняя позже пришедшей — остаётся (и уходит другим следующим
        обменом), а пришедшая ложится рядом копией «(конфликт с „Устройство“, время)»; раньше — наоборот: рядом копией
        здешняя. -> "mine" (здешняя остаётся, пришедшую не писать) или None."""
        p = self._notes_root() / rel
        base = (self.state.get("idx", {}).get("note:" + sid) or {}).get("h")
        if not isinstance(base, str) or not p.is_file():
            return
        try:
            cur = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        title = str(d.get("title") or p.stem)
        mine = {_note_norm(p.stem, cur), _note_norm(title, cur)}
        if mine & {_note_norm(title, d.get("text") or ""), _note_norm(p.stem, d.get("text") or "")}:
            return                                         # та же правка (с «# Названием» или без, под новым названием) — не конфликт
        folder = p.parent.relative_to(self._notes_root()).as_posix()
        dl = {"title": p.stem, "text": cur, "folder": "" if folder == "." else folder}
        sib = getattr(self, "sibling", None)
        aka = next((k for k, v in ((sib.state.get("map") or {}) if sib is not None else {}).items() if v == rel and k != sid), None)
        if base in (_h(dl), _h(dict(dl, aka=aka)) if aka else None):
            return                                         # здесь с прошлого обмена не правили
        who = self._dev_name(getattr(self, "_cur_dev", "")) or "другим устройством"
        alt = p.with_name(f"{p.stem} (конфликт с «{who}», {dt.datetime.now():%d.%m %H-%M}).md")
        n = 2
        while alt.exists():
            alt = p.with_name(f"{p.stem} (конфликт с «{who}», {dt.datetime.now():%d.%m %H-%M}) {n}.md")
            n += 1
        try:
            mine_later = p.stat().st_mtime_ns // 1_000_000 > int(upd or 0) > 0
        except OSError:
            mine_later = False
        if mine_later:
            t = str(d.get("text") or "")
            alt.write_text(t if t.lstrip().startswith("#") else f"# {title}\n\n{t.lstrip(chr(10))}\n", encoding="utf-8")
            self.__dict__.setdefault("_note_resend", set()).add("note:" + sid)
            log.info("🔄 Заметку «%s» правили и здесь (позже), и на «%s» — та правка рядом: %s", p.stem, who, alt.name)
            return "mine"
        alt.write_text(cur, encoding="utf-8")
        log.info("🔄 Заметку «%s» правили и здесь, и на «%s» — здешняя версия рядом: %s", p.stem, who, alt.name)
        return None

    def _note_change(self, key, ek, idx):
        """Запись обмена для заметки как она сейчас лежит здесь (с prev — версией, которую видели). -> dict или None."""
        sid = key.split(":", 1)[1]
        rel = self.state["map"].get(sid)
        p = self._notes_root() / rel if rel else None
        try:
            text, st = p.read_text(encoding="utf-8"), p.stat()
        except (OSError, UnicodeDecodeError, TypeError):
            return None
        folder = p.parent.relative_to(self._notes_root()).as_posix()
        data = {"title": p.stem, "text": text, "folder": "" if folder == "." else folder}
        h = _h(data)
        if ek is not None and self._sealable("note", sid, data):
            data = _seal(ek, data)
        c = {"kind": "note", "id": sid, "data": data, "updated": min(_now_ms(), st.st_mtime_ns // 1_000_000), "_h": h}
        if (idx.get(key) or {}).get("u") is not None:
            c["prev"] = idx[key]["u"]
        return c

    def _dev_name(self, dev):
        for x in (self.status.get("all") or []):
            if x.get("id") == dev and x.get("name"):
                return str(x["name"])[:40]
        return ""

    def _move_to_folder(self, sid, rel, d, root):
        """Папку заметки сменили на телефоне (№195, 23.10: папки в заметках) — переносим файл в эту папку, имя то же.
        Только в непустую папку: старые телефоны присылают folder "" у любой заметки, и всё уехало бы в корень. -> rel."""
        from workspace import _clean_name
        want = "/".join(_clean_name(x) for x in str(d.get("folder") or "").split("/") if x.strip() and x not in (".", ".."))
        cur = str(Path(rel).parent.as_posix())
        cur = "" if cur == "." else cur
        if not want or want == cur:
            return rel
        src = root / rel
        base = Path(rel).stem
        new = f"{want}/{base}.md"
        n = 2
        taken = set(self.state["map"].values())
        while (root / new).exists() or new in taken:
            new = f"{want}/{base} ({n}).md"
            n += 1
        try:
            (root / new).parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                os.replace(src, root / new)
        except OSError as e:
            log.info("Заметка не перенесена в папку «%s»: %s", want, e)
            return rel
        self.state["map"][sid] = new
        log.info("📁 Заметка перенесена с телефона: %s → %s", rel, new)
        self._pad_event(rel, True)                     # вкладку блокнота унесли в другую папку — блокнот её уберёт
        return new

    def _pad_event(self, rel, deleted):
        """Вкладку блокнота поправили на другом устройстве — открытый блокнот перечитает её (ui/pad.html)."""
        if rel and str(rel).startswith(PAD_DIR + "/") and str(rel).count("/") == 1:
            try:
                self.host.emit("pad_changed", name=Path(rel).stem, deleted=bool(deleted))
            except Exception:  # noqa: BLE001
                pass

    def _apply_fact(self, fid, fact, deleted):
        """Строка «Обо мне»: новую дописываем, если такой (по id) ещё нет. Удаление приходит без текста — ищем строку
        по её id (отпечатку текста, см. _fact_id)."""
        fact = re.sub(r"\s+", " ", fact.strip())
        ws = self.host.workspace
        if not deleted:
            if not fact:
                return
            if _fact_id(fact) not in {_fact_id(x) for x in self._facts()}:
                ws.remember(fact, who="")                 # общая «Обо мне», а не своя память того, кто сейчас отвечает
            return
        p = ws.ensure() / MEMORY
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        keep = [ln for ln in lines if not ((m := _FACT.match(ln.strip())) and _fact_id(m.group(1)) == fid)]
        if len(keep) != len(lines):
            p.write_text("\n".join(keep) + "\n", encoding="utf-8")

    # ---------- обмен ----------

    def run_once(self):
        """Один обмен с облаком: отправить свои изменения и удаления, применить чужие, сохранить sync.json.
        -> True после обмена, False — синхронизация выключена (нет ключа). Ошибки облака — SyncError.
        Под self._lock: обмен из цикла и по кнопке не идут одновременно. Порядок тот же, что у syncRun() в app.js."""
        token, link, url = self._creds()
        if not token:
            self.status.update(enabled=False, ok=None, error="")
            return False
        with self._lock:
            who = hashlib.sha1(token.encode()).hexdigest()[:12]
            if self.state.get("who") and self.state["who"] != who:
                # другой ключ или аккаунт — начинаем с чистого листа: свои данные отправим заново, чужие получим
                # (idx обнуляем, а не сравниваем: удаления из старого пространства в новое уйти не должны)
                self.state.update(rev=0, idx={})
            self.state["who"] = who
            self.status["enabled"] = True
            if not self.HOME:
                self._upload_outputs(url, token)
            snap = self.snapshot()
            ek = self.e2e_key()
            if ek is not None:
                snap[E2E_MARK] = {"on": True}               # другим устройствам: шифрование включено — попросите ключ
            reseal_all = ek is not None and self.state.get("reseal_all")
            idx = self.state["idx"]
            now = _now_ms()
            changes = []
            keys = [k for k in snap if not k.endswith(("#h", "#t"))]
            for key in keys:
                h = self._hash_of(snap, key)
                st = idx.get(key)
                again = (reseal_all or (st or {}).get("reseal")) and ek is not None
                if st and st.get("h") == h and not st.get("del") and not again:
                    continue
                data = snap[key]
                if data is None and key.startswith("vault:"):
                    data = self._vault_read(key.split(":", 1)[1])
                    if data is None:
                        continue
                elif data is None and key.startswith("payfile:"):
                    data = self._payfile_read(key.split(":", 1)[1])
                    if data is None:
                        continue
                elif data is None and key.startswith("safe:"):
                    data = self._safe_read(key.split(":", 1)[1])
                    if data is None:
                        continue
                elif data is None and key.startswith("plugin:"):
                    data = self._plugin_read(key.split(":", 1)[1])
                    if data is None:
                        continue
                elif data is None:                        # файл не менялся (отпечаток из кэша), а отправить надо — читаем
                    rel = self.state["map"].get(key.split(":", 1)[1])
                    root = self._notes_root()
                    try:
                        text = (root / rel).read_text(encoding="utf-8")
                    except (OSError, TypeError, UnicodeDecodeError):
                        continue
                    folder = str(Path(rel).parent.as_posix())
                    data = {"title": Path(rel).stem, "text": text, "folder": "" if folder == "." else folder}
                kind, iid = key.split(":", 1)
                upd = now if again else min(now, int(snap.get(key + "#t") or now))   # перешифровка — новее открытой копии в облаке
                if ek is not None and self._sealable(kind, iid, data):
                    data = sealed = _seal(ek, data)
                    if len(sealed["c"]) > SEALED_MAX:
                        log.info("Синхронизация: %s слишком большая для зашифрованной отправки — пропускаю", key)
                        continue
                changes.append({"kind": kind, "id": iid, "data": data, "updated": upd, "_h": h})
                if kind in ("vault", "note") and st and st.get("u") is not None and not st.get("del"):
                    changes[-1]["prev"] = st["u"]       # от какой версии облака правили (облако отклонит правку поверх устаревшей)
            present = set(keys)
            for key, st in list(idx.items()):
                if key not in present and not st.get("del") and not st.get("skip") and self._really_gone(key):
                    kind, iid = key.split(":", 1)
                    changes.append({"kind": kind, "id": iid, "data": {}, "updated": now, "deleted": True, "_h": None})
            sent = {(c["kind"] + ":" + c["id"]): c for c in changes}
            # хранилище Obsidian сейчас недоступно (диск отключён, галочку сняли) — его записи не берём: иначе они
            # применились бы «в никуда», а номер rev ушёл бы вперёд. Вернулось — забираем историю заново с начала.
            ob = getattr(self.host, "obsidian", None)
            vault_on = ob is not None and ob.sync_all()
            kinds = [k for k in BASE_KINDS + EXTRA_KINDS if (k != "vault" or vault_on) and not (k == "plugin" and self.HOME)]
            if vault_on and self.state.get("vault_paused"):
                self.state["vault_paused"] = False
                self.state["rev"] = 0
            elif not vault_on and "vault" in (self.state.get("kinds") or ()):
                self.state["vault_paused"] = True
            body = {"since": int(self.state.get("rev") or 0), "device": self.state["device"], "name": self.host.device_name(),
                    "app": "pc", "ver": _version(), "kinds": kinds,
                    "changes": []}
            via = self._via()
            if via:                                      # телефоны, что синхронизируются с этим компьютером по Wi-Fi (04.11)
                body["via"] = via
            rest = [{k: v for k, v in c.items() if k != "_h"} for c in changes]
            body["changes"], rest = rest[:CHUNK], rest[CHUNK:]
            headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
            if link and link != token:
                headers["X-Sync-Link"] = link
            got = 0
            for _ in range(400):                         # чужое сервер отдаёт по 1000 («more»), своё шлём по CHUNK; 400 — предохранитель
                try:
                    r = httpx.post(url + "?p=/sync", json=body, headers=headers, timeout=30)
                except httpx.HTTPError as e:
                    raise SyncError(("узел синхронизации по Wi-Fi не ответил: " if self.HOME else "облако Dewiar не ответило: ") + str(e)) from e
                if r.status_code >= 400:
                    try:
                        msg = r.json()["error"]["message"]
                    except (ValueError, KeyError, TypeError):
                        msg = f"облако ответило {r.status_code}"
                    raise SyncError(msg)
                d = r.json()
                srv = tuple(d.get("kinds") or BASE_KINDS)
                lost = set(d.get("lost") or ())
                # запоминаем отпечаток отправленного; если сервер оставил более позднюю чужую версию (lost),
                # она придёт в items и ляжет поверх, обновив запись в idx
                for c in body["changes"]:
                    key = c["kind"] + ":" + c["id"]
                    if c["kind"] not in srv:            # сервер такого вида ещё не знает — отправим, когда узнает
                        continue
                    if key in lost and c["kind"] in ("vault", "note"):   # облако не приняло (у него новее) — придёт свежая;
                        continue                         # прежний отпечаток в idx: заметка увидит, что здесь её правили (конфликт)
                    idx[key] = {"h": sent[key]["_h"], "u": c["updated"], "del": bool(c.get("deleted"))}
                    if c["kind"] == "vault":
                        idx[key]["b"] = sent[key]["_h"]          # с этой версией облако согласно — от неё и считаем «правили здесь»
                if set(srv) - set(self.state.get("kinds") or BASE_KINDS) - ({"vault"} if self.state.get("vault_paused") else set()):
                    # сервер знает виды, которых этот компьютер от него ещё не получал: забираем всю историю с начала
                    self.state["kinds"] = list(srv)
                    self.state["rev"] = 0
                    body["since"] = 0
                    body["changes"] = []
                    continue
                body["changes"], rest = rest[:CHUNK], rest[CHUNK:]
                for it in d.get("items") or []:
                    key = it["kind"] + ":" + it["id"]
                    st = idx.get(key) or {}
                    if it.get("dev") == self.state["device"] and st.get("u") == it.get("updated"):
                        continue                          # своё же изменение вернулось — уже на месте
                    plain_in = False
                    if _is_sealed(it.get("data")):
                        k = ek or self._any_key()
                        if k is None:                     # зашифровано, а ключа нет: ждём его со своего устройства
                            self.state["e2e_locked"] = int(self.state.get("e2e_locked") or 0) + 1
                            self.state["e2e_remote"] = True
                            continue
                        try:
                            it = dict(it, data=_open(k, it["data"]))
                        except Exception as e:  # noqa: BLE001 — другой ключ (сменили) или испорчено
                            log.warning("Синхронизация: %s не расшифровалась (%s) — пропускаю", key, e)
                            continue
                    elif ek is not None and not it.get("deleted") and self._sealable(it["kind"], it["id"], it.get("data") or {}):
                        plain_in = True                   # пришло открытым (Telegram на сервере, старое устройство) — перешифруем
                    self._cur_dev = it.get("dev") or ""
                    try:
                        if self._apply(it) is False:
                            # метка шифрования: у нас она та же — отпечаток сразу, иначе два компьютера с шифрованием
                            # пересылали бы её друг другу каждый обмен
                            idx[key] = {"h": _h({"on": True}) if key == E2E_MARK else None, "u": it.get("updated"), "skip": True}
                            continue
                    except Exception as e:  # noqa: BLE001
                        log.warning("Синхронизация: %s %s не применилось: %s", it.get("kind"), it.get("id"), e)
                        continue
                    got += 1
                    if it.get("deleted"):
                        idx[key] = {"h": None, "u": it.get("updated"), "del": True}
                    else:
                        idx[key] = {"h": None, "u": it.get("updated")}
                        if plain_in:
                            idx[key]["reseal"] = True
                        if it["kind"] == "vault":
                            idx[key]["b"] = _h(it.get("data") or {})
                self.state["rev"] = int(d.get("rev") or self.state.get("rev") or 0)
                body["since"] = self.state["rev"]
                for key in self.__dict__.pop("_note_resend", ()):   # здешняя правка заметки позже пришедшей — сразу туда же
                    c = self._note_change(key, ek, idx)
                    if c is not None:
                        sent[key] = c
                        body["changes"].append({k: v for k, v in c.items() if k != "_h"})
                if not d.get("more") and not body["changes"]:
                    break
            if ek is not None:                            # перешифровали — флаги больше не нужны
                self.state.pop("reseal_all", None)
                for key in sent:
                    if key in idx:
                        idx[key].pop("reseal", None)
            self._claim_tasks(url, headers, idx)          # HomeSync — свой: по Wi-Fi занимать не у кого
            if got:                                       # отпечатки принятого — по тому, как оно легло у нас, иначе ушло бы обратно
                snap2 = self.snapshot()
                for key, st in idx.items():
                    if st.get("h") is None and not st.get("del") and key in snap2:
                        st["h"] = self._hash_of(snap2, key)
            for pid in self.__dict__.pop("_plg_resend", ()):   # плагин собрался здесь с добавками — уйдёт следующим обменом
                for key in [k for k in idx if k == "plugin:" + pid or k.startswith("plugin:" + pid + ".")]:
                    idx[key]["h"] = "merged"
            self._save()
            cl = getattr(self.host, "close", None)           # в ящике своих устройств новое — забрать сразу (просьба «пришли мозги»)
            if cl is not None and int(d.get("box") or 0) > int((getattr(cl, "st", None) or {}).get("cursor") or 0):
                try:
                    cl.soon.set()
                except Exception:  # noqa: BLE001
                    pass
            self.status.update(ok=True, at=int(time.time()), error="", devices=d.get("devices") or [], space=d.get("space", ""), all=d.get("all") or [],
                               counts={"sent": len(changes), "got": got}, e2e=self.e2e_status())
            if changes or got:
                log.info("🔄 Синхронизация: отправлено %d, получено %d", len(changes), got)
            return True

    def _via(self):
        """Телефоны, подключённые к узлу «Дома по Wi-Fi» этого компьютера: [{id, name, app, seen}] — облаку, чтобы и другие
        устройства видели их на связи («через „Домашний“»), а не со временем их последнего захода в облако (04.11,
        жалоба: «второй компьютер видит смарт неактивным, хотя в одной Wi-Fi сети»)."""
        hub = getattr(self.host, "homehub", None)
        if self.HOME or hub is None or not callable(getattr(hub, "local_devices", None)):
            return []
        try:
            return list(hub.local_devices())[:8]
        except Exception:  # noqa: BLE001
            return []

    def loop(self, stopping, interval=60):
        """Фоновый поток: обмен раз в interval секунд или раньше — по self.soon.set() после своих правок."""
        time.sleep(5)
        last = ""                                        # та же ошибка раз за разом — в журнал один раз (19.10: 342 одинаковых за сутки)
        while not stopping.is_set():
            import egress
            if egress.local_only():                          # стоп-кран «Ничего не уходит в интернет» — синхронизация ждёт
                self.status.update(ok=False, error="на паузе: включён режим «Ничего не уходит в интернет»", at=int(time.time()))
                self.soon.wait(interval)
                self.soon.clear()
                continue
            t0 = time.monotonic()
            try:
                self.run_once()
                last = ""
            except SyncError as e:
                self.status.update(ok=False, error=str(e), at=int(time.time()))
                (log.debug if str(e) == last else log.info)("Синхронизация: %s", e)
                last = str(e)
            except Exception as e:  # noqa: BLE001
                self.status.update(ok=False, error=str(e), at=int(time.time()))
                if f"{type(e).__name__}: {e}" == last:
                    log.debug("Синхронизация: та же ошибка — %s", e)
                else:
                    log.exception("Синхронизация")
                last = f"{type(e).__name__}: {e}"
            if self.on_pass:                             # обмен (или попытка) прошёл — напоминаниям можно звенеть (28.10)
                try:
                    self.on_pass(t0)
                except Exception:  # noqa: BLE001
                    pass
            self.soon.wait(interval)
            self.soon.clear()
            time.sleep(2)                                # несколько правок подряд — одним обменом


class HomeSync(Sync):
    """Тот же обмен — со своим узлом «Дома по Wi-Fi» (core/homehub.py) по 127.0.0.1: телефоны без dewiar.pro.
    Своё состояние (sync-home.json), тот же номер устройства, что у облачной; облачная и домашняя не идут одновременно
    (общий замок) — что пришло с телефона, следующим обменом уходит в облако, и наоборот: компьютер — мост.
    Шифрование записей на устройстве здесь не нужно: весь обмен телефона с узлом зашифрован его ключом."""
    HOME = True
    FWD_WAIT = 1800                      # облако не отвечает так долго — задачу другому компьютеру не передать: сказать телефону
    FAIL_KEEP = 3 * 86400                # «не передано» видно на телефоне в «Задачах» трое суток

    def __init__(self, host, cloud_sync):
        super().__init__(host)
        self.path = STATE_DIR / "sync-home.json"
        self.state = self._load()
        self.cloud = cloud_sync
        if cloud_sync is not None:
            self.state["device"] = cloud_sync.state.get("device") or self.state["device"]
            self._lock = cloud_sync._lock
            cloud_sync.soon.also.append(self.soon)
            self.sibling, cloud_sync.sibling = cloud_sync, self

    def _creds(self):
        return self.host.home_credentials()

    def e2e_key(self):
        return None

    # ---------- задачи с телефона по Wi-Fi (04.11: раньше терялись молча) ----------
    # Облачная Sync сначала занимает задачу в облаке (taken_by), потому что взяться могут два компьютера. По Wi-Fi узел —
    # этот компьютер, занимать не у кого: задача без to (или с to = этот) — сразу в «Задачи»; с to другого компьютера —
    # в облако (send_taskreq): этот компьютер — мост. Облака нет — на телефон честное «не передано» (запись task, failed).

    def _apply(self, it):
        if it.get("kind") == "taskreq" and not it.get("deleted"):      # кто записал задачу в узел — по нему и имя (а не «from»)
            self._tdev = getattr(self, "_tdev", {})
            self._tdev[it.get("id")] = str(it.get("dev") or "")
        return super()._apply(it)

    def _phone_of(self, dev):
        """Телефон, связанный с узлом этого компьютера (ключом из кода на экране): {id, name} или None. Имя — из реестра
        узла, а не из записи: «from» телефон пишет сам, и подставить туда можно что угодно (рецензия 04.11)."""
        hub = getattr(self.host, "homehub", None)
        try:
            for x in (hub.local_devices() if hub is not None else []):
                if x.get("id") == dev:
                    return x
        except Exception:  # noqa: BLE001
            pass
        return None

    def tasks_on(self):
        """Переключатель «Принимать задания с телефона по Wi-Fi» (sync.home.tasks, по умолчанию включён)."""
        s = getattr(self.host, "s", None)
        try:
            v = s.get("sync", "home", "tasks") if s is not None else None
        except Exception:  # noqa: BLE001
            v = None
        return v is not False

    def _refuse(self, iid, d, why):
        self.state.setdefault("fwd_fail", {})[iid] = {"title": str(d.get("title") or d.get("goal") or "Задача")[:80], "goal": str(d.get("goal") or "")[:400],
                                                      "error": why, "at": int(time.time())}
        log.info("🔄 Задача с телефона не принята: %s", why)
        self.soon.set()

    def _claim_tasks(self, url, headers, idx):
        claims, self._claims = self._claims, {}
        devs, self._tdev = getattr(self, "_tdev", {}), {}
        me = self.host.device_name()
        for iid, (d, _prev) in claims.items():
            if self._q_seen(iid):                          # уже взята облачным обменом (ответ облака телефону потерялся)
                log.info("🔄 Задача с телефона %s уже взята через облако — по Wi-Fi пропускаю", iid)
                continue
            ph = self._phone_of(devs.get(iid))
            if ph is None:                                 # записал не телефон этого узла — не берём и не пересылаем
                log.info("🔄 Задача по Wi-Fi не от связанного телефона (%s) — пропускаю", devs.get(iid) or "?")
                continue
            if not self.tasks_on():
                self._refuse(iid, d, f"На «{me}» выключено «Принимать задания с телефона по Wi-Fi» (студия → «Устройства» → «Дома по Wi-Fi»). Задание не принято.")
                continue
            d = dict(d, **{"from": str(ph.get("name") or "телефон")[:40]})
            to = str(d.get("to") or "")
            self._q_seen(iid, add=True)
            if not to or to == self.state.get("device"):
                self._start_task(d)
            else:
                # id — тот же, что дал телефон, и время одно на все повторы: если телефон успел отдать задачу и облаком
                # (ответ потерялся), облако пересылку не примет (lost) — у того компьютера не будет второй
                self.state.setdefault("fwd", {})[iid] = {"d": d, "at": int(time.time()), "iid": iid, "ts": _now_ms()}

    def run_once(self):
        r = super().run_once()
        if self.state.get("fwd"):
            self._forward()
        return r

    def _pc_name(self, dev):
        cs = self.cloud
        for d in ((cs.status.get("all") if cs is not None else None) or []) + (self.status.get("all") or []):
            if d.get("id") == dev and d.get("name"):
                return str(d["name"])[:40]
        return "другой компьютер"

    def _forward(self):
        """Задачи другим компьютерам, пришедшие по Wi-Fi, — в облако. Сеть подвела — повтор в следующий обмен, до FWD_WAIT."""
        from_cloud = self.cloud
        with self._lock:
            pend = dict(self.state.get("fwd") or {})
        sent, failed = [], {}
        me = self.host.device_name()
        for iid, x in pend.items():
            d = x.get("d") or {}
            name = self._pc_name(d.get("to"))
            data = {"title": str(d.get("title") or d.get("goal") or "")[:80], "goal": str(d.get("goal") or d.get("title") or "")[:4000], "to": d.get("to")}
            tok = ""
            try:
                tok = from_cloud.host.credentials()[0] if from_cloud is not None else ""
            except Exception:  # noqa: BLE001
                tok = ""
            if not tok:
                failed[iid] = (d, f"«{name}» не на связи с телефоном: телефон подключён по Wi-Fi к «{me}», а «{me}» передаёт задания "
                                  f"другим компьютерам только через dewiar.pro — входа в Dewiar на нём нет. Задание не передано.")
                continue
            try:
                from_cloud.send_taskreq(data, sender=d.get("from") or "телефон", iid=x.get("iid"), updated=x.get("ts"))
                sent.append(iid)
                log.info("🔄 Задача с телефона «%s» передана компьютеру «%s» через облако", data["title"], name)
            except SyncError as e:
                if time.time() - int(x.get("at") or 0) > self.FWD_WAIT:
                    failed[iid] = (d, f"«{name}» не на связи: облако Dewiar не отвечает ({e}) — задание не передано.")
        if not sent and not failed:
            return
        with self._lock:
            fwd = self.state.setdefault("fwd", {})
            ff = self.state.setdefault("fwd_fail", {})
            for iid in sent:
                fwd.pop(iid, None)
            for iid, (d, why) in failed.items():
                fwd.pop(iid, None)
                ff[iid] = {"title": str(d.get("title") or d.get("goal") or "Задача")[:80], "goal": str(d.get("goal") or "")[:400], "error": why, "at": int(time.time())}
                log.info("🔄 Задача с телефона не передана: %s", why)
            self._save()
        if failed:
            self.soon.set()                           # телефону — сразу

    def _task_want(self, iid, d):
        ff = self.state.get("fwd_fail") or {}
        if iid in ff:                                  # «Удалить» у непереданной — убрать и с телефона
            if d.get("want") in ("delete", "stop"):
                ff.pop(iid, None)
            return
        super()._task_want(iid, d)

    def _snap_extra(self, out):
        super()._snap_extra(out)
        ff = self.state.get("fwd_fail") or {}
        if "task" not in (self.state.get("kinds") or ()):
            return
        now = time.time()
        for iid in [i for i, x in ff.items() if now - int(x.get("at") or 0) > self.FAIL_KEEP]:
            ff.pop(iid, None)
        for iid, x in ff.items():
            at = dt.datetime.fromtimestamp(int(x.get("at") or now)).isoformat(timespec="seconds")
            out["task:" + iid] = {"title": x.get("title", ""), "status": "failed", "goal": x.get("goal", ""), "result": "", "error": x.get("error", "")[:300],
                                  "question": "", "activity": "", "updated": at, "created": at, "outputs": [], "files": []}

    def loop(self, stopping, interval=60):
        """Свой цикл (без стоп-крана «Ничего не уходит в интернет»: обмен — в домашней сети)."""
        time.sleep(3)
        last = ""
        while not stopping.is_set() and not getattr(self, "stopped", False):
            try:
                self.run_once()
                last = ""
            except Exception as e:  # noqa: BLE001
                self.status.update(ok=False, error=str(e), at=int(time.time()))
                (log.debug if str(e) == last else log.info)("Синхронизация по Wi-Fi: %s", e)
                last = str(e)
            self.soon.wait(interval)
            self.soon.clear()
            time.sleep(1)


def _version():
    try:
        from version import VERSION
        return VERSION
    except Exception:  # noqa: BLE001
        return ""


def default_device_name():
    try:
        return socket.gethostname()[:40] or "Компьютер"
    except OSError:
        return "Компьютер"
