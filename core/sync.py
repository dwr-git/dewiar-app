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

Части (чистое ядро, 1.0.16): sync_base — виды записей, пределы, шифрование записи, id; sync_e2e — сквозное шифрование;
sync_snap — снимок этого устройства; sync_apply — чужие изменения; sync_files — хранилище, «Клиенты», «Мои файлы»;
sync_safe — сейф; sync_plugins — свои плагины; sync_pay — «Платежи»; sync_tasks — задачи между устройствами. Здесь —
состояние, обмен (run_once, loop) и «Дома по Wi-Fi» (HomeSync). Подменять в проверках — sync_base (sync.SB).
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

from sync_base import (
    BASE_KINDS, _base_title, CHUNK, CONST_PREV, _CTRL, default_device_name, DIARY_DAYS, DIARY_MAX, DOC_PART,
    DOC_TOTAL, E2E_KINDS, E2E_MARK, EXTRA_KINDS, _FACT, _fact_id, FanEvent, _h, _is_sealed, log, MEMORY, MIND_MAX,
    _mind_text, NOTE_MAX, _note_norm, NOTES, _now_ms, _NUM_TAIL, _open, PAD_DIR, PF_CHUNK, PF_MAX, _pmem_id, _seal,
    SEALED_MAX, SyncError, TASKS_SHOWN, VAULT_FILES, VAULT_MAX, _version)  # noqa: F401 — прежние имена на месте
import sync_base as SB  # подменяемые в проверках имена — через основу
from sync_e2e import E2EMixin
from sync_snap import SnapMixin
from sync_apply import ApplyMixin
from sync_files import FilesMixin
from sync_safe import SafeMixin
from sync_plugins import PluginsMixin
from sync_pay import PayMixin
from sync_tasks import TasksMixin


class Sync(E2EMixin, SnapMixin, ApplyMixin, FilesMixin, SafeMixin, PluginsMixin, PayMixin, TasksMixin):
    HOME = False

    def _creds(self):
        return self.host.credentials()

    def __init__(self, host):
        """host: reminders, money, workspace, credentials() -> (token, link_token, cloud_url), device_name(), push();
        по желанию soul, diary, tasks, obsidian — без них соответствующие виды просто не собираются."""
        self.host = host
        self.path = SB.STATE_DIR / "sync.json"
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
        why = None
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("idx", {})
                d.setdefault("map", {})
                if not str(d.get("device") or "").startswith("pc-"):
                    d["device"] = self._kept_device() or "pc-" + uuid.uuid4().hex[:10]
                return d
            why = "не словарь"
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            why = e
        # №851 (18.11): «при каждом запуске клонируется подключённое устройство» — пять «DESKTOP-…» в «Устройствах»: если
        # sync.json не прочитался (или пропал), компьютер заводил себе новый id и выходил на связь новым устройством. id
        # хранится ещё и рядом с настройками (sync_device) — компьютер остаётся собой; почему не прочиталось — в журнал
        dev = self._kept_device()
        if why is not None:
            log.warning("Синхронизация: sync.json не прочитался (%s) — %s", why, f"устройство прежнее ({dev})" if dev else "новое устройство")
        return {"rev": 0, "device": dev or "pc-" + uuid.uuid4().hex[:10], "idx": {}, "map": {}, "who": ""}

    def _kept_device(self):
        """id этого компьютера из CONFIG_DIR/sync_device (копия на случай, если sync.json пропадёт) или ""."""
        try:
            v = (SB.CONFIG_DIR / "sync_device").read_text(encoding="utf-8").strip()
            return v if re.fullmatch(r"pc-[0-9a-f]{6,32}", v) else ""
        except OSError:
            return ""

    def _keep_device(self):
        dev = str(self.state.get("device") or "")
        if dev.startswith("pc-") and self._kept_device() != dev:
            try:
                (SB.CONFIG_DIR / "sync_device").write_text(dev, encoding="utf-8")
            except OSError as e:
                log.debug("sync_device: %s", e)

    def _save(self):
        # через временный файл: оборванная запись не испортит sync.json (иначе всё ушло бы заново и с удалениями)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        self._keep_device()


    PLG_STALE = 7 * 86400                    # куски сборки, которая так и не собралась (другой компьютер ушёл, сборку сменили)

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
            try:                                            # 1.0.26: копии «(копия с …)», совпавшие со своей заметкой, — прочь
                self._copies_tidy()
            except Exception as e:  # noqa: BLE001
                log.warning("Синхронизация: уборка копий не удалась: %s", e)
            snap = self.snapshot()
            ek = self.e2e_key()
            if ek is not None:
                snap[E2E_MARK] = {"on": True}               # другим устройствам: шифрование включено — попросите ключ
            reseal_all = ek is not None and self.state.get("reseal_all")
            idx = self.state["idx"]
            now = SB._now_ms()
            changes = []
            keys = [k for k in snap if not k.endswith(("#h", "#t"))]
            for key in keys:
                h = self._hash_of(snap, key)
                st = idx.get(key)
                again = (reseal_all or (st or {}).get("reseal")) and ek is not None
                if st and st.get("h") == h and not st.get("del") and not again:
                    continue
                big = self.__dict__.setdefault("_too_big", {})
                if big.get(key) == h:                     # не влезла шифром и не менялась — не шифруем каждую минуту заново
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
                elif data is None and key.startswith("doc:"):
                    data = self._doc_read(key.split(":", 1)[1])
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
                    data = sealed = SB._seal(ek, data)
                    if len(sealed["c"]) > SEALED_MAX:
                        big[key] = h                      # отчёт №720: 4 записи сейфа писались в журнал каждую минуту
                        log.info("Синхронизация: %s слишком большая для зашифрованной отправки — пропускаю (до изменения)", key)
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
        self.path = SB.STATE_DIR / "sync-home.json"
        self.state = self._load()
        self.cloud = cloud_sync
        if cloud_sync is not None:
            self.state["device"] = cloud_sync.state.get("device") or self.state["device"]
            self._lock = cloud_sync._lock
            cloud_sync.soon.also.append(self.soon)
            self.sibling, cloud_sync.sibling = cloud_sync, self

    def _creds(self):
        return self.host.home_credentials()

    # ---------- сквозное шифрование (sync.e2e) ----------

    def e2e_key(self):
        return None

    # ---------- задачи с телефона по Wi-Fi (04.11: раньше терялись молча) ----------
    # Облачная Sync сначала занимает задачу в облаке (taken_by), потому что взяться могут два компьютера. По Wi-Fi узел —
    # этот компьютер, занимать не у кого: задача без to (или с to = этот) — сразу в «Задачи»; с to другого компьютера —
    # в облако (send_taskreq): этот компьютер — мост. Облака нет — на телефон честное «не передано» (запись task, failed).

    # ---------- применить чужое изменение ----------

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
                self.state.setdefault("fwd", {})[iid] = {"d": d, "at": int(time.time()), "iid": iid, "ts": SB._now_ms()}

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
