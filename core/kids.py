"""Детский режим (27.10, решение владельца по макету «Dewiar — новые режимы»): профиль ребёнка на этом компьютере.

  • Свой персонаж-друг (по умолчанию — Совёнок Уго из галереи, personas.GALLERY["ugo"]), говорит проще и теплее.
  • Только безопасное: модель получает короткий список умений (KIDS_TOOLS) и правила для разговора с ребёнком
    (prompt); быстрые команды компьютера, сейфа, денег, платежей, умного дома в режиме не работают (engine_answer).
  • Время: минуты за день (будни и выходные — свои), «спать» после заданного часа. Минута считается, если в ней
    был хотя бы один вопрос. Кончилось — персонаж говорит об этом и до завтра не отвечает (родитель — PIN).
  • Отчёт родителю: о чём спрашивал (первые слова вопросов), что было вне правил (купить, удалить, позвонить
    незнакомым…) — в студии «Дети», вне правил — ещё и в Telegram, если бот подключён.
  • Выйти из режима, поменять настройки или персонажа — только с PIN родителя (хранится как хэш с солью).
Файл состояния — STATE_DIR/kids.json: {"days": {"2026-10-27": {"min": [...], "asked": [...], "off": [...]}}} — 30 дней.
Настройки — settings["kids"]: on, child {name, age}, persona, prev_persona, allow [...], min_weekday, min_weekend,
bedtime "20:30", morning "07:00". PIN (хэш с солью) — в kids.json, не в настройках: те уходят в отчёты, копии и на
другие свои компьютеры."""

import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("dewiar.kids")

# что можно (студия — чипсы), ключ → название; от этого зависит, что модель предлагает сама
ALLOW = {"tales": "Сказки и истории", "games": "Загадки и игры", "homework": "Помощь с уроками",
         "why": "Вопросы «почему?»", "music": "Детская музыка", "draw": "Рисунки по описанию"}
DEFAULT_ALLOW = list(ALLOW)
# умения модели в детском режиме: ничего на компьютере, никаких отправок и покупок
KIDS_TOOLS = {"calc", "world_time", "weather", "set_reminder", "list_reminders", "cancel_reminder", "play_radio",
              "media_control", "set_volume", "save_note", "find_notes"}
TOOLS_BY_ALLOW = {"draw": {"show_images"}}
# просьбы вне правил — в отчёт родителю (и в Telegram); сами просьбы модель вежливо не выполняет
OFF_RX = re.compile(
    r"\b(купи|закажи|оплати|заплати|переведи\s+деньг|подписк|пополни|"
    r"удали|сотри|выключи\s+(?:компьютер|ноутбук)|перезагрузи|отформатир|"
    r"позвони|набери|напиши\s+(?:сообщение|в\s+телеграм|в\s+вк|письмо)|отправь|"
    r"пароль|номер\s+карты|адрес\s+(?:наш|мой|дома)|"
    r"убить|убей|оружи|пистолет|кров[ьи]\s|страшн\w+\s+(?:видео|истори)|18\s*\+|секс|голы[ей]|наркот|сигарет|алкогол|пиво|водк)",
    re.I)
PBKDF = 120_000


def _hash(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", str(pin).encode("utf-8"), bytes.fromhex(salt), PBKDF).hex()


class Kids:
    """settings — объект настроек ядра (get/update); state_path — kids.json; now — функция времени (проверки)."""

    def __init__(self, settings, state_path, now=None):
        self.s, self.path = settings, Path(state_path)
        self.now = now or datetime.now
        self._lock = threading.Lock()
        self._unlock_until = 0.0
        self._tries = []                              # неверные PIN: не больше 5 за 5 минут
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {"days": {}}

    # ---------- настройки ----------

    def conf(self):
        c = dict(self.s.get("kids") or {})
        c.setdefault("allow", DEFAULT_ALLOW)
        c.setdefault("min_weekday", 60)
        c.setdefault("min_weekend", 120)
        c.setdefault("bedtime", "20:30")
        c.setdefault("morning", "07:00")
        c.setdefault("child", {})
        c.setdefault("persona", "ugo")
        return c

    def on(self):
        return bool((self.s.get("kids") or {}).get("on"))

    def has_pin(self):
        return bool(self.data.get("pin"))

    def set_pin(self, new, old=""):
        """Первый PIN — без старого; сменить — со старым (или в открытом родителем режиме)."""
        new = str(new or "").strip()
        if not re.fullmatch(r"\d{4,8}", new):
            raise ValueError("PIN — от 4 до 8 цифр")
        if self.has_pin() and not (self.unlocked() or self.check_pin(old)):
            raise ValueError("неверный прежний PIN")
        salt = secrets.token_hex(16)
        self.data["pin"] = salt + ":" + _hash(new, salt)     # не в настройках: те уходят в отчёты, копии и на другие компьютеры
        self._save()

    def check_pin(self, pin):
        stored = self.data.get("pin") or ""
        if ":" not in stored:
            return False
        now = time.time()
        self._tries = [t for t in self._tries if now - t < 300]
        if len(self._tries) >= 5:
            raise ValueError("слишком много попыток — подождите 5 минут")
        salt, h = stored.split(":", 1)
        ok = secrets.compare_digest(_hash(str(pin or "").strip(), salt), h)
        if not ok:
            self._tries.append(now)
        return ok

    def unlock(self, pin, minutes=15):
        """Родитель ввёл PIN — 15 минут можно менять настройки, выключить режим, открыть студию."""
        if not self.check_pin(pin):
            raise ValueError("неверный PIN")
        self._unlock_until = time.time() + minutes * 60
        return True

    def unlocked(self):
        return time.time() < self._unlock_until

    def locked(self):
        """Режим включён, а родитель не вводил PIN — студия и настройки закрыты."""
        return self.on() and not self.unlocked()

    def lock(self):
        self._unlock_until = 0.0

    def set_on(self, on, pin=""):
        """Включить (нужен заданный PIN) или выключить (нужен PIN или открытый режим). Персонаж — детский и обратно."""
        if on:
            if not self.has_pin():
                raise ValueError("сначала задайте PIN родителя")
            if not self.on():
                self.s.update({"kids": {"on": True, "prev_persona": self.s.get("persona") or "lira"}})
            self.lock()
        else:
            if self.on() and not (self.unlocked() or self.check_pin(pin)):
                raise ValueError("неверный PIN")
            prev = (self.s.get("kids") or {}).get("prev_persona") or ""
            self.s.update({"kids": {"on": False}})
            self.lock()
            return prev
        return ""

    # ---------- время ----------

    def _day(self, d=None):
        return (d or self.now()).strftime("%Y-%m-%d")

    def _today(self):
        with self._lock:
            days = self.data.setdefault("days", {})
            d = days.setdefault(self._day(), {"min": [], "asked": [], "off": []})
            for k in [k for k in days if k < self._day(self.now() - timedelta(days=30))]:
                days.pop(k, None)
            return d

    def limit_today(self):
        c = self.conf()
        return int(c["min_weekend"] if self.now().weekday() >= 5 else c["min_weekday"])

    def used_today(self):
        return len(set(self._today()["min"]))

    def left_today(self):
        return max(0, self.limit_today() - self.used_today())

    def allowed_now(self):
        """-> (можно ли разговаривать, почему нет — фраза персонажа)."""
        if not self.on():
            return True, ""
        c, n = self.conf(), self.now()
        hm = n.strftime("%H:%M")
        bed, morn = c.get("bedtime") or "", c.get("morning") or ""
        if bed and morn and (hm >= bed or hm < morn):
            return False, f"Уже пора спать! Я тоже ложусь. Поговорим завтра утром — после {morn}. Спокойной ночи!"
        if self.left_today() <= 0:
            return False, "На сегодня наше время закончилось. Давай отдохнём, поиграем без экрана — а завтра снова поболтаем!"
        return True, ""

    def touch(self, text=""):
        """Был вопрос: минута считается; первые слова вопроса — в отчёт; вне правил — отдельно. -> вне ли правил."""
        d = self._today()
        off = bool(OFF_RX.search(text or ""))
        with self._lock:
            m = self.now().strftime("%H:%M")
            if m not in d["min"]:
                d["min"].append(m)
            if text:
                short = re.sub(r"\s+", " ", text).strip()[:80]
                d["asked"] = (d["asked"] + [{"t": m, "q": short}])[-200:]
                if off:
                    d["off"] = (d["off"] + [{"t": m, "q": short}])[-50:]
        self._save()
        return off

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.info("Детский режим: состояние не записалось: %s", e)

    def report(self, day=None):
        d = (self.data.get("days") or {}).get(day or self._day(), {"min": [], "asked": [], "off": []})
        return {"day": day or self._day(), "used": len(set(d.get("min", []))), "limit": self.limit_today(),
                "asked": d.get("asked", [])[-50:], "off": d.get("off", [])}

    # ---------- модель ----------

    def tools(self):
        allow = set(self.conf().get("allow") or [])
        out = set(KIDS_TOOLS)
        for k, extra in TOOLS_BY_ALLOW.items():
            if k in allow:
                out |= extra
        return out

    def prompt(self):
        """Правила разговора с ребёнком — в системную подсказку, пока режим включён."""
        c = self.conf()
        ch = c.get("child") or {}
        who = (ch.get("name") or "ребёнок") + (f", {ch.get('age')} лет" if ch.get("age") else "")
        allow = [ALLOW[k] for k in (c.get("allow") or []) if k in ALLOW]
        hw = "homework" in (c.get("allow") or [])
        return ("\n\nДЕТСКИЙ РЕЖИМ. С тобой говорит ребёнок: " + who + ". Говори просто, тепло и коротко — две-четыре "
                "фразы, слова, понятные в этом возрасте; хвали за вопросы. Можно: " + (", ".join(allow) or "просто болтать") + ". "
                + ("Уроки — не давай готовый ответ: подскажи шаг и спроси, как ребёнок думает, чтобы он решил сам. " if hw else
                   "С уроками не помогаешь — скажи, что об этом лучше спросить маму или папу. ")
                + "Нельзя: взрослые, страшные, жестокие темы, болезни и смерть в подробностях — мягко переведи разговор на "
                "другое интересное. Не покупаешь, не оплачиваешь, не звонишь и не пишешь незнакомым, ничего не делаешь на "
                "компьютере, не спрашиваешь и не запоминаешь адрес, телефон, пароли — на такую просьбу скажи по-доброму, что "
                "это можно только вместе с мамой или папой. Если ребёнок расстроен, боится или рассказывает, что его обижают, — "
                "поддержи и посоветуй сразу рассказать маме, папе или другому взрослому, которому он доверяет.")
