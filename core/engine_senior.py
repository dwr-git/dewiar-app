"""Режимы Лиры и режим «Для старших» в ядре (0.58; core/senior.py — сам режим, здесь — связь с остальным).

Режим — один из трёх: me («Для меня», как всегда), kid (детский — kids.py, с PIN родителя), senior («Для старших»).
mode_set senior запоминает, как было (что на «Главной», размер, скорость голоса, разделы «по желанию»), и ставит своё;
mode_set me возвращает как было. Детский режим включается в «Детях» (нужен PIN) — здесь только узнаётся.

Лекарства: _care_after(item, result) — после звонка напоминания (alarm_finish и «никто не ответил»): выпила — отмечено;
не ответили или заговорили о другом — ещё раз через senior.CARE_AGAIN минут; снова нет — присматривающим.
«Всё хорошо» и полуденная проверка — _senior_loop раз в минуту. Мошенники — _senior_scam из handle_text (engine_answer)."""
import threading
import time

from engine_base import log


class SeniorMixin:

    # ---------- режим ----------

    def mode(self):
        k = getattr(self, "kids", None)
        if k is not None and k.on():
            return "kid"
        s = getattr(self, "senior", None)
        return "senior" if s is not None and s.on() else "me"

    def mode_public(self):
        sen = getattr(self, "senior", None)
        people = []
        try:
            for p in (self.close.state() or {}).get("people") or []:
                people.append({"pid": p.get("pid"), "name": p.get("name"), "ready": bool(p.get("devs"))})
        except Exception:  # noqa: BLE001
            log.debug("режим: близкие", exc_info=True)
        ui = self.s.get("ui") or {}
        first = not getattr(self, "wav_input", None) and (ui.get("intro") or "") != "done" and not ui.get("mode_seen")
        return {"mode": self.mode(), "senior": sen.public() if sen else None, "people": people, "first": bool(first),
                "kids_pin": bool(getattr(self, "kids", None) and self.kids.has_pin())}

    def mode_set(self, mode):
        """me | senior. Детский — в «Детях» (PIN). -> mode_public()."""
        import senior as SN
        cur = self.mode()
        if mode == cur:
            return self.mode_public()
        if cur == "kid":
            raise ValueError("сначала выключите детский режим — в «Детях», с PIN родителя")
        if mode == "senior":
            ui = self.s.get("ui") or {}
            feats = self.s.get("features") or {}
            prev = {"home_apps": ui.get("home_apps"), "home_known": ui.get("home_known"), "zoom": ui.get("zoom", 1.0),
                    "text": ui.get("text", 1.0), "speed": self.s.get("tts", "speed"),
                    "features": {k: feats.get(k) for k in SN.FEATURES_OFF}}
            self.s.update({"senior": {"on": True, "prev": prev},
                           "ui": {"home_apps": list(SN.HOME_APPS), "home_known": sorted(set((ui.get("home_known") or []) + list(SN.HOME_APPS))),
                                  "zoom": max(float(ui.get("zoom") or 1.0), SN.ZOOM), "text": max(float(ui.get("text") or 1.0), SN.TEXT)},
                           "tts": {"speed": min(float(self.s.get("tts", "speed") or 1.25), SN.SPEED)},
                           "features": {k: False for k in SN.FEATURES_OFF}})
            log.info("👵 Режим «Для старших» включён")
        elif mode == "me":
            prev = (self.s.get("senior") or {}).get("prev") or {}
            patch = {"senior": {"on": False, "prev": {}}}
            ui = {k: prev[k] for k in ("home_apps", "home_known", "zoom", "text") if k in prev}
            if ui:
                patch["ui"] = ui
            if prev.get("speed"):
                patch["tts"] = {"speed": prev["speed"]}
            if prev.get("features"):
                patch["features"] = {k: v for k, v in prev["features"].items() if v is not None}
            self.s.update(patch)
            log.info("Режим «Для меня»")
        else:
            raise ValueError("нет такого режима")
        self.emit("settings", settings=self.s.snapshot())
        self.emit("mode", **self.mode_public())
        return self.mode_public()

    def senior_set(self, a):
        """Настройки режима: name, gender (f|m), watchers [pid], checkin «20:00», noon, scam."""
        import senior as SN
        patch = {}
        if "name" in a:
            patch["name"] = str(a.get("name") or "").strip()[:60]
        if a.get("gender") in ("f", "m"):
            patch["gender"] = a["gender"]
        if "watchers" in a:
            patch["watchers"] = [str(x) for x in (a.get("watchers") or [])][:6]
        if "checkin" in a:
            h, m = SN._hm(a.get("checkin"), (20, 0))
            patch["checkin"] = f"{h:02d}:{m:02d}"
        for k in ("noon", "scam"):
            if k in a:
                patch[k] = bool(a.get(k))
        if patch:
            self.s.update({"senior": patch})
        return self.mode_public()

    def senior_med_add(self, text, times):
        """Лекарство по расписанию: каждый день в каждое время из times («09:00», «21:00») — напоминание с вопросом «выпили?»."""
        import senior as SN
        from datetime import datetime, timedelta
        text = str(text or "").strip()[:120]
        if not text:
            raise ValueError("напишите, какое лекарство")
        out = []
        for t in times or []:
            h, m = SN._hm(t, (-1, -1))
            if h < 0:
                raise ValueError(f"не понял время «{t}» — например, 09:00")
            now = datetime.now()
            at = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if at <= now:
                at += timedelta(days=1)
            out.append(self.reminders.add(at, text, {"kind": "daily", "time": f"{h:02d}:{m:02d}"}, "reminder", extra={"care": True}))
        if not out:
            raise ValueError("укажите хотя бы одно время")
        return out

    # ---------- лекарства ----------

    def _care_item(self, item):
        sen = getattr(self, "senior", None)
        return bool(sen is not None and item and sen.is_med(item))

    def _care_after(self, item, result):
        """После звонка напоминания о лекарстве: ack — выпито; snooze — отложено; missed/seen — ещё раз или близким."""
        if not self._care_item(item):
            return
        sen = self.senior
        try:
            if result == "ack":
                sen.med_log(item, "taken")
            elif result == "snooze":
                sen.med_log(item, "snooze")
            elif int(item.get("care_n") or 0) < 1:
                nxt = sen.again_item(item)
                self.reminders.add(nxt["when"], nxt["text"], None, "reminder", extra=nxt["extra"])
                sen.med_log(item, "again")
            else:
                sen.med_log(item, "missed")
                if sen.on():
                    threading.Thread(target=self._senior_send, args=(sen.missed_text(item),), name="senior-care", daemon=True).start()
        except Exception:  # noqa: BLE001
            log.exception("Для старших: лекарство")

    # ---------- близким ----------

    def _senior_watchers(self):
        sen = getattr(self, "senior", None)
        if sen is None:
            return []
        out = []
        for pid in sen.conf().get("watchers") or []:
            try:
                out.append(self.close.person(pid))
            except Exception:  # noqa: BLE001
                continue
        return out

    def _senior_send(self, text):
        """Сообщение присматривающим близким (через «Близкие»). -> сколько ушло."""
        n = 0
        for p in self._senior_watchers():
            try:
                self.close.send(p["pid"], text)
                n += 1
            except Exception as e:  # noqa: BLE001
                log.info("Для старших: %s — не отправлено: %s", p.get("name"), e)
        return n

    def _senior_scam(self, body, text, via=None):
        """Похоже на мошенников: сразу твёрдый ответ (без модели) и сообщение присматривающим."""
        sen = self.senior
        names = ", ".join(p["name"] for p in self._senior_watchers())
        log.info("🛡 Для старших: похоже на мошенников — предупредила%s", " и написала близким" if names else "")
        self.emit("senior", kind="scam")
        if names:
            threading.Thread(target=self._senior_send, args=(sen.scam_alert(body),), name="senior-scam", daemon=True).start()
        else:
            sen.scam_alert(body)
        self._say_quick(sen.scam_reply(names), text, via)

    def _senior_loop(self):
        """Раз в минуту: «всё хорошо» вечером и полуденная проверка — присматривающим."""
        while not self.stopping.wait(60):
            sen = getattr(self, "senior", None)
            if sen is None or not sen.on():
                continue
            try:
                for key, text in sen.due_checks():
                    if self._senior_send(text):
                        log.info("💛 Для старших: близким — %s", "вечерняя сводка" if key == "eve" else "днём ни слова")
                    sen.sent(key)
            except Exception:  # noqa: BLE001
                log.exception("Для старших: сводка")
            time.sleep(0)
