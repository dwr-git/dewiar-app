"""Синхронизация — задачи между устройствами (часть Sync, чистое ядро 1.0.16): просьбы с телефона, файлы-результаты,
задача другому своему устройству."""
import httpx
import time
import uuid
from sync_base import log, SyncError, TASKS_SHOWN, _version
import sync_base as SB  # подменяемые в проверках имена — через основу


class TasksMixin:
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
        upd = int(updated or SB._now_ms())
        d = dict(data, ts=upd, **{"from": str(sender or self.host.device_name())[:40]})   # sender — пересылаем чужую (телефона по Wi-Fi)
        ek = self.e2e_key()
        body_data = SB._seal(ek, d) if ek and self._sealable("taskreq", iid, d) else d
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
