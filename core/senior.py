"""Режим «Для старших» (0.58; владелец 28.10: «быстрые режимы — детский, для пожилых и обычный… понятно, что для детей и
пожилых работа и клиенты не нужны… чтобы это легко делалось, понятно, чётко»; из разговора о том, чего не хватает Лире:
«забота, которую видно» — Лира для мамы, а дети спокойны).

Что делает режим (включает его обычно сын или дочь — в студии, «Лира: для меня ▾» → «Для старших»):
  • Просто: на «Главной» и в меню — только нужное (Близкие, Дела, Календарь, Заметки, Музыка, Досуг, Вопрос — ответ),
    крупнее текст и интерфейс, голос чуть медленнее; Лира говорит простыми короткими фразами, терпеливо (prompt).
  • Лекарства: напоминание о таблетках (флаг care или слова «таблетк/лекарств/капл/давлен/инсулин…») — со звонком и
    вопросом «выпили?». «Выпила» голосом или «Готово» — отмечено. Не ответили — ещё раз через CARE_AGAIN минут; снова
    нет — тихое сообщение «присматривающим» близким (через «Близкие», шифр на устройствах).
  • «Всё хорошо»: вечером (checkin, 20:00) присматривающим — короткая сводка дня: говорила ли с Лирой, что с лекарствами.
    Днём (noon, 12:00), если с утра ни слова и ни одного ответа про лекарства, — «может, позвоните?».
  • Защита от мошенников: «мне позвонили из банка, просят код из СМС», «внук попал в аварию, нужны деньги» — Лира сразу,
    без модели, твёрдо говорит «стоп, это мошенники» и сообщает присматривающим.

Настройки — settings["senior"]: on, name (как обращаться), watchers [pid близких], checkin "20:00", noon True, scam True,
prev {…} — что было до включения (вернуть при выходе). Состояние — STATE_DIR/senior.json:
{"days": {"2026-10-28": {"talk": [первое, последнее] (unix), "meds": [{id, text, at, res, ts}], "sent": ["noon", "eve"],
"alerts": [{ts, kind, text}]}}} — 30 дней."""

import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("dewiar.senior")

# что видно на «Главной» и в меню (ui.home_apps); остальное прячется, функции работают как прежде
HOME_APPS = ["close", "reminders", "calendar", "notes", "music", "play", "qa", "chat"]
FEATURES_OFF = ["team", "clients", "prompter", "family"]      # разделы «по желанию» — выключены
ZOOM, TEXT, SPEED = 1.15, 1.2, 1.05                           # крупнее; голос чуть медленнее (обычный — 1.25)
CARE_AGAIN = 15                                               # мин — второй раз спросить про лекарство

MED_RX = re.compile(r"таблет|лекарств|капл[иею]|капсул|укол|инсулин|давлени|сироп|мазь|витамин|пилюл|\bприн[яи]ть\b|"
                    r"\bвыпить\s+(?:таблет|лекарств|капл)", re.I)
TAKEN_RX = re.compile(r"\b(выпил[аи]?|выпью|приняла?|принял[аи]|пью|уже\s+пила?|да\b)", re.I)

# мошенники: человек РАССКАЗЫВАЕТ о звонке или просьбе (а не спрашивает «что такое мошенники»)
SCAM_RX = [re.compile(p, re.I) for p in (
    r"(?:позвонил\w*|звон(?:ят|ил\w*|ок)|пишут|написал\w*|прислал\w*|сообщени\w*).{0,70}?"
    r"(?:банк|служб\w*\s+безопасност|полици|следовател|прокурат|фсб|мвд|центробанк|госуслуг|пенсионн\w*\s+фонд|сотовый\s+оператор|оператор\s+связи)",
    r"\bкод\w*\s+из\s+(?:смс|сообщени|sms)",
    r"(?:назвать|назови|продиктова\w*|сказать|сообщить)\s+(?:им\s+)?(?:код|пароль|номер\s+карт|данные\s+карт|cvv|cvc)",
    r"(?:безопасн\w+|резервн\w+|защищ[её]нн\w+)\s+сч[её]т",
    r"(?:сын|дочь|дочка|внук|внучк\w*|племянни\w*|муж|жена).{0,50}?(?:попал\w*\s+(?:в\s+)?(?:авари|дтп|беду|полици|больниц)|сбил\w*|задержал\w*)",
    r"(?:просят|просил\w*|требу\w+|сказали|велели)\s.{0,40}?(?:перевест\w*|перевод|отправить\s+деньг|снять\s+деньг|деньги|код|номер\s+карт|данные\s+карт|оформить\s+кредит)",
    r"(?:выигр\w+|приз\w*|компенсаци\w*|выплат\w*).{0,50}?(?:оплат\w*|перевест\w*|комисси\w*|налог)",
)]
SCAM_NOT = re.compile(r"\b(что\s+такое|расскажи\s+(?:про|о)|как\s+(?:не\s+)?(?:попасть|распознать|защитить)|бывают\s+ли|почему)\b", re.I)


def _hm(s, default):
    m = re.match(r"^\s*(\d{1,2})[:.](\d{2})\s*$", str(s or ""))
    return (int(m.group(1)), int(m.group(2))) if m and int(m.group(1)) < 24 and int(m.group(2)) < 60 else default


class Senior:
    """settings — объект настроек ядра (get/update); state_path — senior.json; now — функция времени (для проверок)."""

    def __init__(self, settings, state_path, now=None):
        self.s = settings
        self.path = Path(state_path)
        self.now = now or datetime.now
        self._lock = threading.Lock()
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("days", {})

    # ---------- настройки ----------

    def conf(self):
        c = dict(self.s.get("senior") or {})
        c.setdefault("name", "")
        c.setdefault("watchers", [])
        c.setdefault("checkin", "20:00")
        c.setdefault("noon", True)
        c.setdefault("scam", True)
        c.setdefault("gender", "f")              # f — она (мама, бабушка), m — он: в сообщениях близким
        return c

    def _g(self, f, m):
        return m if self.conf().get("gender") == "m" else f

    def on(self):
        return bool((self.s.get("senior") or {}).get("on"))

    def who(self):
        """Как называть человека в сообщениях близким: имя из режима, иначе имя пользователя, иначе «мама/папа» нельзя знать."""
        return (self.conf().get("name") or self.s.get("user_name") or "").strip() or "ваш близкий"

    # ---------- день ----------

    def _day(self, d=None):
        return (d or self.now()).strftime("%Y-%m-%d")

    def _today(self):
        with self._lock:
            days = self.data["days"]
            d = days.setdefault(self._day(), {"talk": [], "meds": [], "sent": [], "alerts": []})
            for k in list(days)[:-30]:
                days.pop(k, None)
            return d

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with self._lock:
                tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:
            log.info("Для старших: не сохранить состояние: %s", e)

    def touch(self):
        """Человек что-то сказал Лире — для «всё хорошо» и полуденной проверки."""
        d = self._today()
        t = int(self.now().timestamp())
        d["talk"] = [d["talk"][0] if d.get("talk") else t, t]
        self._save()

    # ---------- лекарства ----------

    def is_med(self, item):
        """Напоминание о лекарстве: помечено care или похоже по словам (только в режиме)."""
        if item.get("kind") not in (None, "", "reminder"):
            return False
        return bool(item.get("care")) or (self.on() and bool(MED_RX.search(str(item.get("text") or ""))))

    def med_log(self, item, res):
        """res: taken | missed | snooze | again (спросили второй раз)."""
        d = self._today()
        at = str(item.get("at") or "")[11:16] or self.now().strftime("%H:%M")
        text = str(item.get("care_of") or item.get("text") or "")
        rid = item.get("care_root") or item.get("id")
        row = next((m for m in d["meds"] if m.get("id") == rid), None)
        if row is None:
            row = {"id": rid, "text": text, "at": at}
            d["meds"].append(row)
        row.update(res=res, ts=int(self.now().timestamp()))
        self._save()
        return row

    def again_item(self, item):
        """Не ответили на первое напоминание — каким будет второе (через CARE_AGAIN минут)."""
        text = str(item.get("care_of") or item.get("text") or "лекарство")
        return {"when": self.now() + timedelta(minutes=CARE_AGAIN), "text": f"Вы выпили лекарство? {text}",
                "extra": {"care": True, "care_n": int(item.get("care_n") or 0) + 1, "care_of": text,
                          "care_root": item.get("care_root") or item.get("id"), "care_at": str(item.get("at") or "")[11:16]}}

    def missed_text(self, item):
        text = str(item.get("care_of") or item.get("text") or "лекарство")
        at = item.get("care_at") or str(item.get("at") or "")[11:16]
        return (f"Это Лира, помощница: {self.who()} {self._g('не ответила', 'не ответил')} про «{text}»" + (f" в {at}" if at else "")
                + f" — я напомнила дважды. Может, позвоните?")

    # ---------- «всё хорошо» ----------

    def due_checks(self):
        """Какие сообщения присматривающим пора отправить сейчас: [(ключ, текст)] — каждое раз в день."""
        if not self.on() or not self.conf().get("watchers"):
            return []
        c, now, d = self.conf(), self.now(), self._today()
        out = []
        if c.get("noon") and (now.hour, now.minute) >= (12, 0) and "noon" not in d["sent"] and now.hour < 18:
            taken = any(m.get("res") == "taken" for m in d["meds"])
            if not d.get("talk") and not taken:
                out.append(("noon", f"Это Лира, помощница: {self.who()} сегодня ещё не {self._g('говорила', 'говорил')} со мной. Может, позвоните?"))
            else:
                d["sent"].append("noon")            # всё в порядке — днём не беспокоим
        if (now.hour, now.minute) >= _hm(c.get("checkin"), (20, 0)) and "eve" not in d["sent"]:
            out.append(("eve", self.summary(d)))
        return out

    def sent(self, key):
        d = self._today()
        if key not in d["sent"]:
            d["sent"].append(key)
        self._save()

    def summary(self, d=None):
        d = d or self._today()
        who = self.who()
        talk = d.get("talk") or []
        if talk:
            t0 = datetime.fromtimestamp(talk[0]).strftime("%H:%M")
            t1 = datetime.fromtimestamp(talk[-1]).strftime("%H:%M")
            line = f"{who} сегодня {self._g('говорила', 'говорил')} со мной" + (f" — с {t0} до {t1}" if t0 != t1 else f" в {t0}")
        else:
            line = f"{who} сегодня со мной не {self._g('говорила', 'говорил')}"
        meds = d.get("meds") or []
        word = {"taken": self._g("выпила", "выпил"), "missed": self._g("не ответила", "не ответил"),
                "snooze": self._g("отложила", "отложил"), "again": "ждём ответа"}
        med = "; ".join(f"{m.get('at', '')} {m.get('text', '')} — {word.get(m.get('res'), '?')}" for m in meds)
        ok = talk and all(m.get("res") == "taken" for m in meds)
        return ("Это Лира, помощница. " + ("Всё хорошо. " if ok else "") + line + "."
                + (f" Лекарства: {med}." if med else "") + ("" if ok else " Может, позвоните?"))

    # ---------- мошенники ----------

    def scam(self, text):
        """Похоже, человек рассказывает о мошенниках (звонок «из банка», «код из СМС», «внук в беде»)? -> True."""
        if not self.on() or not self.conf().get("scam"):
            return False
        t = str(text or "")
        if SCAM_NOT.search(t):
            return False
        return any(rx.search(t) for rx in SCAM_RX)

    def scam_reply(self, watchers_names):
        n = (self.conf().get("name") or "").strip()
        lead = f"{n}, стоп." if n else "Стоп."
        tail = (f" Я уже написала {watchers_names} — вам перезвонят." if watchers_names else
                " Позвоните сейчас сыну или дочери и расскажите.")
        return (f"{lead} Это очень похоже на мошенников. Никому не называйте коды из СМС и данные карты и никуда не "
                "переводите деньги. Банк, полиция и врачи так не звонят. Если торопят и пугают — просто положите трубку."
                + tail)

    def scam_alert(self, text):
        d = self._today()
        d["alerts"].append({"ts": int(self.now().timestamp()), "kind": "scam", "text": str(text)[:200]})
        self._save()
        return (f"⚠️ Это Лира, помощница. {self.who()} {self._g('рассказала', 'рассказал')}: «{str(text).strip()[:160]}». "
                f"Похоже на мошенников — я сказала ничего не переводить и не называть коды. Позвоните {self._g('ей', 'ему')}, пожалуйста.")

    # ---------- модель ----------

    def prompt(self):
        n = (self.conf().get("name") or "").strip()
        return ("\n\nРЕЖИМ «ДЛЯ СТАРШИХ». С тобой говорит пожилой человек" + (f": {n}, обращайся так" if n else "") + ". "
                "Говори просто, тепло и неторопливо: короткие фразы, обычные слова — без иностранных и технических терминов, "
                "без списков и значков. Числа, время и даты называй ясно. Если просят повторить или не поняли — терпеливо "
                "повтори другими словами. Перед любым действием (звонок, сообщение, покупка, удаление) переспроси. "
                "Никогда не советуй переводить деньги, называть коды из СМС, данные карты или пароли — если о таком "
                "просят по телефону, это мошенники: скажи об этом прямо и предложи позвонить детям. "
                "Если человек грустит или одинок — поддержи и предложи позвонить близким («позвони дочке»).")

    def public(self):
        d = self._today()
        return dict(self.conf(), on=self.on(), today={"talk": d.get("talk") or [], "meds": d.get("meds") or [],
                                                      "alerts": d.get("alerts") or []})
