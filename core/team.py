"""«Поручения» — задания сотрудникам через Telegram (внутри — team; название «Поручения» выбрал владелец 28.10:
«команда» путалась с командами голосом и «командой помощников»). 28.10, по макету «Dewiar — обучение и «Команда»», владелец:
«прекрасны, идеальны»; просьба пользователя: «задачи сотрудникам в Telegram: берут, сделано с фото, перенос с причиной»).

Как устроено. Руководитель создаёт в @BotFather бота компании (это две минуты) и вставляет его токен в студии →
«Поручения». Сотрудники приходят по личной ссылке-приглашению t.me/<бот>?start=<код> — у каждого свой код, бот узнаёт
человека по нему. Dewiar сам опрашивает бота (тот же приём, что у личного Telegram, telegram.py), поэтому сообщения
обрабатываются, пока программа запущена; Telegram хранит их сутки — включили компьютер, и всё догоняется.

Поручение — голосом («Лира, поручи Анне обновить прайс до пятницы»), в студии или моделью (инструмент team_assign).
Сотруднику приходит карточка с кнопками:
  • «Беру» — в работе; кнопки сменяются на «Сделано» и «Перенести…»;
  • «Сделано» — бот просит пару слов и фото (если нужно); отчёт и фото — руководителю (студия, вслух, личный Telegram);
  • «Перенести…» — новый срок и причина одной фразой («на понедельник, клиент заболел»).
Руководитель: «Принять» (сотруднику — «принято») или «Вернуть с замечанием» (снова «в работе», с текстом замечания).
За час до срока сотруднику — напоминание; прошёл срок — карточка в студии красная.

Безопасность: токен бота — CONFIG_DIR/team_bot.json (0600), в студию не отдаётся; бот отвечает только тем, кто пришёл
по действующему приглашению (код — 10 знаков, 14 дней, после входа сгорает); чужим — одна фраза, и всё. Бот работает
только в личных сообщениях. Этот бот — не личный Telegram владельца: тот же токен сюда не принимается.

Состояние — STATE_DIR/team.json: company, members {mid: {name, role, code, code_at, tg}}, tasks {tid: {...}};
фото отчётов — STATE_DIR/team/."""

import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from maxbot import Max
from telegram import Telegram, TelegramError

log = logging.getLogger("dewiar.team")
CODE_DAYS = 14
OPEN = ("new", "work", "moved")                  # ещё не сделано
STATES = {"new": "Новое", "work": "В работе", "done": "Сделано", "moved": "Перенесено", "ok": "Принято"}
COLORS = ["#B9C3EE", "#F2D3A6", "#BFE6D6", "#E6C9F2", "#F5C6D2", "#C9E4F5", "#E8E2B0", "#D4D9E3"]
WD_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WD_GEN = {"понедельника": "понедельник", "вторника": "вторник", "среды": "среду", "четверга": "четверг", "пятницы": "пятницу",
          "субботы": "субботу", "воскресенья": "воскресенье"}
HELP = ("Сюда приходят поручения. Под каждым — кнопки: «Беру», потом «Сделано» (можно приложить фото) или «Перенести…» "
        "(новый срок и причина одной фразой).\n\n/tasks — мои поручения\n/help — эта подсказка")


class TeamError(Exception):
    pass


def due_parse(phrase, now=None):
    """«до четверга 15:00», «на пятницу», «завтра к 12», «27 ноября» -> (datetime | None, остаток текста).
    Разбор — общий с напоминаниями (when.parse); без часа срок — конец рабочего дня, 18:00."""
    from when import parse
    p = re.sub(r"\s+", " ", (phrase or "").strip())
    if not p:
        return None, ""
    q = re.sub(r"(?i)\bдо\s+(" + "|".join(WD_GEN) + r")\b", lambda m: "в " + WD_GEN[m.group(1).lower()], p)
    q = re.sub(r"(?i)\bдо\s+завтра\b", "завтра", q)
    q = re.sub(r"(?i)\bдо\s+(сегодня|послезавтра)\b", r"\1", q)
    q = re.sub(r"(?i)\bдо\s+(\d{1,2}[:.]\d\d)\b", r"в \1", q)
    q = re.sub(r"(?i)\bдо\s+(\d{1,2}\s+[а-яё]+)", r"\1", q)
    q = re.sub(r"(?i)\bк\s+(" + "|".join(WD_GEN.values()) + r"|понедельнику|вторнику|среде|четвергу|пятнице|субботе|воскресенью)\b",
               lambda m: "в " + {"понедельнику": "понедельник", "вторнику": "вторник", "среде": "среду", "четвергу": "четверг",
                                 "пятнице": "пятницу", "субботе": "субботу", "воскресенью": "воскресенье"}.get(m.group(1).lower(), m.group(1)), q)
    q = re.sub(r"(?i)(?<!в )(?<!к )\b(\d{1,2}:\d\d)\b", r"в \1", q)          # «в четверг 15:00» -> «в четверг в 15:00»
    if re.fullmatch(r"(?i)сегодня", q):
        q = "сегодня в 18:00"
    r = parse("напомни " + q)
    if not r:
        return None, p
    at = r["at"]
    hour_said = re.search(r"\d{1,2}[:.]\d\d|\b(?:в|к|до)\s+\d{1,2}\b|\bчерез\b|\bутр|\bвечер|\bдн[её]м\b|\bобед", q, re.I)
    if not hour_said and (at.hour, at.minute) == (9, 0):
        at = at.replace(hour=18, minute=0)
    rest = (r.get("text") or "").strip()
    return at, ("" if rest == "Напоминание" else rest)          # «Напоминание» — текст по умолчанию у when.parse


# Повторяющиеся поручения (28.10, «Поручения дальше»: «каждый понедельник — отчёт»): срок словами с «каждый», «по будням»,
# «ежедневно» — не одно поручение, а правило; в день срока утром (в 9:00, ранний срок — за час) поручение уходит само.
REPEAT_RX = re.compile(r"(?i)(?:^|\s)(кажд\w*|ежедневн\w*|еженедельн\w*|ежемесячн\w*|по\s+(?:будн\w*|выходн\w*|понедельник\w*|вторник\w*|"
                       r"сред\w*|четверг\w*|пятниц\w*|суббот\w*|воскресень\w*))(?=\s|$)")
WD_EACH = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]


def repeat_parse(phrase):
    """«каждый понедельник к 18», «по будням до 10», «каждое 1 число» -> правило повтора when.py ({kind, days|day, time})
    или None (не повтор). Без часа — срок к 18:00, как у обычных поручений."""
    p = re.sub(r"\s+", " ", (phrase or "").strip())
    if not p or not REPEAT_RX.search(p):
        return None
    from when import parse
    q = re.sub(r"(?i)\b(?:к|до)\s+(\d{1,2}(?:[:.]\d\d)?)\b", r"в \1", p)
    q = re.sub(r"(?i)(?<!в )\b(\d{1,2}:\d\d)\b", r"в \1", q)
    r = parse("напомни " + q)
    rep_ = (r or {}).get("repeat")
    if not rep_ or rep_.get("kind") not in ("daily", "weekly", "monthly"):
        return None
    rep_ = dict(rep_)
    if not re.search(r"\d{1,2}[:.]\d\d|\b(?:в|к|до)\s+\d{1,2}\b|утр|вечер|дн[её]м|обед", q, re.I):
        rep_["time"] = "18:00"
    return rep_


def repeat_text(rep_):
    """Правило словами: «каждый понедельник к 18:00», «по будням к 10:00», «каждый день к 18:00», «каждое 1-е число к 12:00»."""
    t = rep_.get("time") or "18:00"
    k = rep_.get("kind")
    if k == "daily":
        return f"каждый день к {t}"
    if k == "monthly":
        return f"каждое {rep_.get('day')}-е число к {t}"
    days = sorted(rep_.get("days") or [])
    if days == [0, 1, 2, 3, 4]:
        return f"по будням к {t}"
    if days == [5, 6]:
        return f"по выходным к {t}"
    names = [("каждое " if d == 6 else "каждую " if d in (2, 4, 5) else "каждый ") + WD_EACH[d] for d in days]
    return (", ".join(names[:-1]) + " и " + names[-1] if len(names) > 1 else names[0]) + f" к {t}"


def post_at(due):
    """Когда отправить повторяющееся поручение: в день срока в 9:00; срок раньше 10:00 — за час."""
    return due.replace(hour=9, minute=0) if due.hour >= 10 else due - timedelta(hours=1)


MALE_A = {"никита", "илья", "кузьма", "фома", "лука", "савва", "данила", "гаврила", "миша", "саша", "женя", "дима", "вова",
          "коля", "петя", "ваня", "лёша", "леша", "серёжа", "сережа", "паша", "гоша", "слава", "валера", "юра", "толя", "витя"}


def is_fem(name):
    """Женское ли имя (по первому слову): «Анна Ким» — да, «Никита», «Иван Сергеевич» — нет."""
    w = (re.findall(r"[А-Яа-яЁё]+", name or "") or [""])[0].lower()
    return w.endswith(("а", "я")) and w not in MALE_A


def name_case(name, case):
    """Имя в родительном («от Михаила») или дательном («Михаилу») падеже — по простым правилам, слово за словом.
    Женская фамилия на согласную («Анна Ким») не склоняется; незнакомое окончание — как есть."""
    fem = is_fem(name)
    out = []
    for i, w in enumerate((name or "").split()):
        lw = w.lower()
        if not re.fullmatch(r"[а-яё-]+", lw):
            out.append(w)
        elif i and re.search(r"(ова|ева|ёва|ина|ына|ская|цкая)$", lw):      # фамилия (не первое слово: «Ирина» — имя)
            out.append(w[:-1] + "ой" if lw.endswith(("ова", "ева", "ёва", "ина", "ына")) else w[:-2] + "ой")
        elif lw.endswith("ия"):
            out.append(w[:-1] + "и")
        elif lw.endswith("а"):
            out.append(w[:-1] + ({"gen": "и" if lw[-2:-1] in "гкхжшщч" else "ы", "dat": "е"}[case]))
        elif lw.endswith("я"):
            out.append(w[:-1] + {"gen": "и", "dat": "е"}[case])
        elif lw.endswith(("й", "ь")):
            out.append(w[:-1] + {"gen": "я", "dat": "ю"}[case])
        elif lw[-1] in "бвгджзклмнпрстфхцчшщ" and not fem:
            out.append(w + {"gen": "а", "dat": "у"}[case])
        else:
            out.append(w)
    return " ".join(out)


def verb(name, male):
    """«сделал» -> «сделала» для женского имени; «подключился» -> «подключилась»."""
    if not is_fem(name):
        return male
    if male.endswith("ел") and male in ("вышел", "ушёл", "ушел", "пришёл", "пришел", "зашёл", "зашел", "нашёл", "нашел"):
        return male[:-2] + "ла"                         # «вышел» -> «вышла», «ушёл» -> «ушла»
    if male.endswith("ёл"):
        return male[:-2] + "ла"
    return male[:-2] + "ась" if male.endswith("ся") else male + "а"


def due_text(iso, now=None):
    """'2026-10-29T15:00' -> «чт 15:00», «сегодня 18:00», «завтра 12:00», «3 ноя»."""
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    now = now or datetime.now()
    hm = d.strftime("%H:%M")
    days = (d.date() - now.date()).days
    if days == 0:
        return f"сегодня {hm}"
    if days == 1:
        return f"завтра {hm}"
    if 1 < days < 7:
        return f"{WD_SHORT[d.weekday()]} {hm}"
    mon = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"][d.month - 1]
    return f"{d.day} {mon} {hm}"


def _stem(w):
    w = w.lower().replace("ё", "е")
    return w[:max(3, len(w) - 2)] if len(w) >= 4 else w


class TeamBot(Telegram):
    """Бот компании в Telegram: приём и отправка — как у личного Telegram, разбор сообщений — у Team.
    Каналы (28.10, владелец: «не только Telegram… чтобы масштабируемо было»): у каждого канала свой бот с тем же видом
    событий (MAX переводит свои в вид Telegram — maxbot.to_tg), Team различает их по CH. Новый мессенджер — ещё один
    такой класс, ссылка-приглашение в LINK и строчка в Team.__init__."""
    TITLE = "Поручения"
    CH, NAME, LINK = "tg", "Telegram", "https://t.me/{bot}?start={code}"

    def __init__(self, team, path):
        super().__init__(on_message=None, path=path)
        self.team = team

    def paired(self):
        return self.connected()

    def _handle(self, u):
        self.team.on_update(u, self.CH)


class TeamMaxBot(Max):
    """Бот компании в MAX (свой бот организации: business.max.ru → Чат-боты → токен; в MAX ботов создают ИП и
    организации — для поручений это как раз так)."""
    TITLE = "Поручения"
    CH, NAME, LINK = "max", "MAX", "https://max.ru/{bot}?start={code}"

    def __init__(self, team, path):
        super().__init__(on_message=None, path=path)
        self.team = team

    def paired(self):
        return self.connected()

    def _handle(self, u):
        self.team.on_update(u, self.CH)


class TeamApp:
    """Канал «Приложение Dewiar» (режим «Сотрудник», 0.55; владелец: «рассчитывать только на мессенджеры не стоит»).
    Сотрудник получает поручения в своей Лире (раздел «Работа» на телефоне), бота нет. Транспорт — close.py ядра:
    связь «работа» на сайте (work_links), конверты kind «work» со сквозным шифрованием. Сотруднику уходит «снимок» —
    его поручения целиком (новые, в работе, перенесённые, недавно сделанные) и текст для уведомления; от него —
    действия {act: take|done|move|msg}. «Подключён» — когда руководитель включил этот способ и на компьютере есть вход
    в Dewiar (аккаунт или ключ)."""
    CH, NAME, LINK = "app", "Приложение Dewiar", ""

    def __init__(self, team):
        self.team, self.data, self.problem, self._thread = team, {"bot": {}}, "", None

    def close(self):
        return getattr(self.team.host, "close", None)

    def ready(self):
        """Есть чем ходить на сайт: вход в Dewiar на этом компьютере."""
        try:
            return self.close() is not None and bool(self.team.host.credentials()[0])
        except Exception:  # noqa: BLE001
            return False

    def connected(self):
        return bool(self.team.st.get("app_on")) and self.ready()

    def start(self):
        pass

    def stop(self):
        pass

    def forget(self):
        self.team.st["app_on"] = False


class Team:
    """host — ядро (emit, push, announce, s); path — team.json; bot_path — team_bot.json с токеном."""

    def __init__(self, host, path, bot_path, files_dir=None, personal=None, max_path=None, personal_max=None):
        self.host, self.path = host, Path(path)
        self.files = Path(files_dir) if files_dir else self.path.parent / "team"
        self.personal = personal                       # личный Telegram (чтобы не принять его токен сюда)
        self.personal_max = personal_max               # личный MAX — то же
        self._lock = threading.RLock()
        try:
            self.st = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.st = {}
        self.st.setdefault("company", "")
        self.st.setdefault("members", {})
        self.st.setdefault("tasks", {})
        self.st.setdefault("repeats", {})               # повторяющиеся: {id: {id, who, title, note, rep, next, created}}
        self.st.setdefault("digest", "18:30")           # итог дня руководителю в это время ("" — не присылать)
        self.bot = TeamBot(self, bot_path)              # Telegram (прежнее имя — для совместимости)
        self.bots = {"tg": self.bot, "max": TeamMaxBot(self, max_path or Path(bot_path).with_name("team_max.json")), "app": TeamApp(self)}
        self._tl = threading.local()                    # канал события, которое сейчас разбирается (у каждого бота свой поток)
        self._waiting = {}                              # (канал, id) -> {"tid", "step": done|move|why} — ждём отчёт или новый срок
        self._strangers = set()
        self._tick_stop = threading.Event()
        self._tick = None

    # ---------- хранение ----------

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.info("Команда: не записалось: %s", e)

    def _changed(self):
        self._save()
        try:
            self.host.emit("team", **self.public())
            cb = getattr(self.host, "team_changed", None)     # свой телефон руководителя — свежую доску (engine_tools)
            if callable(cb):
                cb()
        except Exception:  # noqa: BLE001
            log.debug("Команда: событие", exc_info=True)

    def _tell(self, title, text, speak=True):
        """Руководителю: уведомление (и личный Telegram, если подключён) и, по желанию, вслух."""
        try:
            self.host.push(title, text)
        except Exception:  # noqa: BLE001
            log.debug("Команда: push", exc_info=True)
        if speak and self.st.get("speak", True) is not False:
            try:
                self.host.announce(text[:400])
            except Exception:  # noqa: BLE001
                log.debug("Команда: вслух", exc_info=True)

    def boss(self):
        return (self.st.get("boss") or self.host.s.get("user_name") or "руководитель").strip()

    def company(self):
        names = [(b.data.get("bot") or {}).get("name") for b in self.bots.values() if b.connected()]
        return (self.st.get("company") or next((n for n in names if n), "") or "компании").strip()

    def connected(self):
        return any(b.connected() for b in self.bots.values())

    def _ch(self, ch=None):
        return ch or getattr(self._tl, "ch", None) or "tg"

    @staticmethod
    def _mch(m):
        """Канал сотрудника: где он вошёл по приглашению (прежние записи — Telegram)."""
        return (m.get("tg") or {}).get("ch") or "tg"

    # ---------- бот ----------

    def start(self):
        for b in self.bots.values():
            if b.connected():
                b.start()
        if not (self._tick and self._tick.is_alive()):
            self._tick_stop.clear()
            self._tick = threading.Thread(target=self._ticker, name="team-tick", daemon=True)
            self._tick.start()

    def stop(self):
        for b in self.bots.values():
            b.stop()
        self._tick_stop.set()

    def connect(self, token, ch="tg"):
        """Подключить бота компании в канале ch (tg | max) или способ «Приложение Dewiar» (app — без токена)."""
        if ch not in self.bots:
            raise TeamError("такого мессенджера нет")
        if ch == "app":
            if not self.bots["app"].ready():
                raise TeamError("для приложения Dewiar нужен вход в аккаунт dewiar.pro или ключ Dewiar на этом компьютере — студия → «Мозг»")
            with self._lock:
                self.st["app_on"] = True
            self.start()
            self._changed()
            return self.public()
        token = (token or "").strip()
        mine = self.personal if ch == "tg" else self.personal_max
        own = (getattr(mine, "data", None) or {}).get("token") if mine else None
        if own and token == own:
            raise TeamError("это токен вашего личного бота — для поручений нужен отдельный бот компании"
                            + (" (@BotFather → /newbot)" if ch == "tg" else " (business.max.ru → Чат-боты)"))
        bot = self.bots[ch]
        if ch == "tg":
            px = (getattr(self.personal, "data", None) or {}).get("proxy") if self.personal else ""
            if px and not bot.data.get("proxy"):
                bot.data["proxy"] = px                   # Telegram за прокси (как у личного бота) — и бот компании через него
        try:
            bot.connect(token)
        except TelegramError as e:
            raise TeamError(str(e)) from e
        with self._lock:
            if not self.st.get("company"):
                self.st["company"] = (bot.data.get("bot") or {}).get("name", "")
        self.start()
        self._changed()
        return self.public()

    def forget(self, ch="tg"):
        if ch in self.bots:
            self.bots[ch].forget()
        self._changed()
        return self.public()

    def set(self, a):
        with self._lock:
            if "company" in a:
                self.st["company"] = str(a.get("company") or "").strip()[:60]
            if "boss" in a:
                self.st["boss"] = str(a.get("boss") or "").strip()[:60]
            if "speak" in a:
                self.st["speak"] = bool(a.get("speak"))
            if "digest" in a:                          # «18:30» или "" — итог дня не присылать
                d = str(a.get("digest") or "").strip()
                self.st["digest"] = d if re.fullmatch(r"\d{1,2}:\d\d", d) else ""
        self._changed()
        return self.public()

    def _send(self, chat, text, buttons=None, ch=None):
        """Сообщение сотруднику в канале ch (по умолчанию — канал разбираемого события) -> message_id (или None).
        buttons — [[(текст, data), …], …] рядами."""
        bot = self.bots.get(self._ch(ch))
        if bot is None or not bot.connected():
            return None
        if bot.CH == "app":                              # приложение Dewiar: снимок поручений сотрудника и текст уведомления
            return self._app_push(self._mid_by_tg(chat, "app"), text)
        params = {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
        try:
            r = bot._call("sendMessage", **params)
            return (r or {}).get("message_id") or "sent"
        except TelegramError as e:
            log.info("Поручения: не отправилось (%s): %s", bot.NAME, e)
            bot.problem = str(e)
            return None

    def _rekey(self, t, buttons):
        """Сменить кнопки под карточкой поручения (Беру → Сделано/Перенести; сделано — без кнопок). Не вышло (канал
        не умеет править сообщение) — не страшно: нажатие на старую кнопку бот разберёт по состоянию поручения."""
        m = self.st["members"].get(t.get("who")) or {}
        chat = (m.get("tg") or {}).get("chat")
        if chat and self._mch(m) == "app":               # в приложении кнопки — по состоянию поручения: просто новый снимок
            self._app_push(t.get("who"), "", quiet=True)
            return
        if not (chat and t.get("msg") and t.get("msg") != "sent"):
            return
        kb = {"inline_keyboard": [[{"text": x, "callback_data": d} for x, d in row] for row in buttons]} if buttons else {"inline_keyboard": []}
        try:
            self.bots[self._mch(m)]._call("editMessageReplyMarkup", chat_id=chat, message_id=t["msg"], reply_markup=kb)
        except (TelegramError, KeyError):
            pass

    # ---------- сотрудники ----------

    def _mid_by_tg(self, uid, ch=None):
        ch = self._ch(ch)
        for mid, m in self.st["members"].items():
            if uid and (m.get("tg") or {}).get("id") == uid and self._mch(m) == ch:
                return mid
        return None

    def member_add(self, name, role=""):
        name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
        if not name:
            raise TeamError("впишите имя сотрудника")
        with self._lock:
            if any(m["name"].lower() == name.lower() for m in self.st["members"].values()):
                raise TeamError(f"{name} уже в команде")
            mid = secrets.token_hex(4)
            self.st["members"][mid] = {"name": name, "role": str(role or "").strip()[:60], "code": secrets.token_hex(5),
                                       "code_at": time.time(), "tg": None, "added": time.time(),
                                       "color": COLORS[len(self.st["members"]) % len(COLORS)]}
        self._changed()
        return self.public()

    def member_code(self, mid):
        with self._lock:
            m = self.st["members"].get(mid)
            if not m:
                raise TeamError("нет такого сотрудника")
            m["code"], m["code_at"] = secrets.token_hex(5), time.time()
        self._changed()
        return self.public()

    def member_del(self, mid):
        with self._lock:
            m = self.st["members"].pop(mid, None)
            if not m:
                raise TeamError("нет такого сотрудника")
            for t in self.st["tasks"].values():
                if t.get("who") == mid and t["state"] in OPEN:
                    t["state"], t["gone"] = "ok", True
        chat = (m.get("tg") or {}).get("chat")
        if chat and self._mch(m) == "app" or m.get("app_inv"):    # приложение: связь на сайте — убрать (у сотрудника пропадёт «Работа»)
            self._app_leave(mid)
        elif chat:
            self._send(chat, f"Вы больше не в команде «{self.company()}». Поручения сюда приходить не будут.", ch=self._mch(m))
        self._changed()
        return self.public()

    def _links(self, m):
        """Ссылки-приглашения сотрудника — по одной на каждый подключённый мессенджер (код один и тот же)."""
        if m.get("tg") or not m.get("code") or time.time() - m.get("code_at", 0) > CODE_DAYS * 86400:
            return {}
        out = {}
        for ch, b in self.bots.items():
            name = (b.data.get("bot") or {}).get("username", "")
            if b.connected() and name:
                out[ch] = b.LINK.format(bot=name, code=m["code"])
        return out

    def _link(self, m):
        ls = self._links(m)
        return ls.get("tg") or next(iter(ls.values()), "")

    def find(self, who):
        """«Анне», «Иван Васильевич», «Ивану» -> mid. Двое подходят — TeamError с вопросом «кому?»."""
        words = [w for w in re.findall(r"[а-яёa-z]+", (who or "").lower()) if len(w) > 1]
        if not words:
            raise TeamError("скажите, кому поручить")
        hits = []
        for mid, m in self.st["members"].items():
            nm = [w for w in re.findall(r"[а-яёa-z]+", m["name"].lower())]
            score = sum(1 for w in words if any(_stem(w) == _stem(x) or x.startswith(_stem(w)) or w.startswith(_stem(x)) for x in nm))
            if score:
                hits.append((score, mid))
        if not hits:
            names = ", ".join(m["name"] for m in self.st["members"].values()) or "пока никого"
            raise TeamError(f"в команде нет «{who}». В команде: {names}")
        best = max(s for s, _ in hits)
        top = [mid for s, mid in hits if s == best]
        if len(top) > 1:
            raise TeamError("подходят двое: " + " и ".join(self.st["members"][x]["name"] for x in top) + " — кому именно?")
        return top[0]

    # ---------- поручения ----------

    def _ev(self, t, ev, text=""):
        t.setdefault("log", []).append({"ts": time.time(), "ev": ev, "t": text[:500]})

    def _card(self, t):
        due = due_text(t.get("due"))
        return (f"Новое поручение от {name_case(self.boss(), 'gen')}\n\n{t['title']}" + (f"\n{t['note']}" if t.get("note") else "")
                + (f"\n\nСрок — {due}" if due else ""))

    def assign(self, who, title, due="", note="", via="studio"):
        """Поручить -> задача. who — mid или имя; due — ISO или фраза («до пятницы», «завтра к 12»). Фраза с «каждый»,
        «по будням» — повторяющееся поручение (repeat_add) -> {repeat: True, …}."""
        if due and REPEAT_RX.search(str(due)):
            return self.repeat_add(who, title, str(due), note)
        title = re.sub(r"\s+", " ", str(title or "")).strip()[:300]
        if not title:
            raise TeamError("что поручить?")
        title = title[:1].upper() + title[1:]
        if not self.connected():
            raise TeamError("сначала подключите бота компании — студия → «Поручения»")
        mid = who if who in self.st["members"] else self.find(who)
        m = self.st["members"][mid]
        at = None
        if due:
            try:
                at = datetime.fromisoformat(str(due))
            except ValueError:
                at, _ = due_parse(str(due))
                if at is None:
                    raise TeamError(f"не поняла срок «{due}» — скажите, например: «до пятницы» или «завтра к 12»") from None
        with self._lock:
            tid = secrets.token_hex(4)
            t = {"id": tid, "who": mid, "title": title, "note": str(note or "").strip()[:500],
                 "due": at.strftime("%Y-%m-%dT%H:%M") if at else "", "state": "new", "created": time.time(), "log": []}
            self._ev(t, "assign", "голосом" if via == "voice" else "по расписанию" if via == "repeat" else "с телефона" if via == "phone" else "")
            self.st["tasks"][tid] = t
        chat = (m.get("tg") or {}).get("chat")
        if chat:
            t["msg"] = self._send(chat, self._card(t), [[("Беру", f"tk:{tid}:take"), ("Перенести…", f"tk:{tid}:move")]], ch=self._mch(m))
            if t["msg"]:
                self._ev(t, "sent")
        self._changed()
        return dict(t, name=m["name"], joined=bool(chat), sent=bool(t.get("msg")))

    def repeat_add(self, who, title, every, note=""):
        """Повторяющееся поручение: правило из фразы every; первое уйдёт само в день ближайшего срока."""
        from when import next_time
        title = re.sub(r"\s+", " ", str(title or "")).strip()[:300]
        if not title:
            raise TeamError("что поручать?")
        title = title[:1].upper() + title[1:]
        if not self.connected():
            raise TeamError("сначала подключите бота компании — студия → «Поручения»")
        rule = repeat_parse(every)
        if not rule:
            raise TeamError(f"не поняла, как часто: «{every}» — скажите, например: «каждый понедельник к 18» или «по будням к 10»")
        mid = who if who in self.st["members"] else self.find(who)
        first = next_time(rule, datetime.now())
        with self._lock:
            rid = "r" + secrets.token_hex(3)
            self.st["repeats"][rid] = {"id": rid, "who": mid, "title": title, "note": str(note or "").strip()[:500], "rep": rule,
                                       "next": first.strftime("%Y-%m-%dT%H:%M"), "created": time.time()}
        self._changed()
        self.tick()                                    # срок сегодня, а утро уже прошло — первое уходит сразу
        r = self.st["repeats"][rid]
        nm = self.st["members"][mid]["name"]
        return dict(r, repeat=True, name=nm, name_dat=name_case(nm, "dat"), rule=repeat_text(rule), first=first.strftime("%Y-%m-%dT%H:%M"))

    def repeat_del(self, rid):
        with self._lock:
            if not self.st["repeats"].pop(str(rid), None):
                raise TeamError("такого повтора нет")
        self._changed()
        return self.public()

    def accept(self, tid):
        with self._lock:
            t = self._task(tid)
            t["state"] = "ok"
            self._ev(t, "ok")
        self._to_member(t, f"{self.boss()} {verb(self.boss(), 'принял')}: «{t['title']}». Спасибо!")
        self._changed()
        return self.public()

    def back(self, tid, remark):
        remark = str(remark or "").strip()[:500]
        if not remark:
            raise TeamError("напишите замечание — что поправить")
        with self._lock:
            t = self._task(tid)
            t["state"] = "work"
            t.pop("report", None)
            self._ev(t, "back", remark)
        m = self.st["members"].get(t["who"]) or {}
        chat = (m.get("tg") or {}).get("chat")
        if chat:
            t["msg"] = self._send(chat, f"{self.boss()} {verb(self.boss(), 'вернул')} поручение «{t['title']}» с замечанием:\n{remark}",
                                  [[("Сделано", f"tk:{tid}:done"), ("Перенести…", f"tk:{tid}:move")]], ch=self._mch(m)) or t.get("msg")
        self._changed()
        return self.public()

    def cancel(self, tid):
        with self._lock:
            t = self.st["tasks"].pop(tid, None)
            if not t:
                raise TeamError("нет такого поручения")
        if t["state"] in OPEN:
            self._rekey(t, None)
            self._to_member(t, f"Поручение «{t['title']}» отменено — делать не нужно.")
        self._changed()
        return self.public()

    def remind(self, tid):
        t = self._task(tid)
        due = due_text(t.get("due"))
        btn = [[("Беру", f"tk:{tid}:take"), ("Перенести…", f"tk:{tid}:move")]] if t["state"] == "new" else \
              [[("Сделано", f"tk:{tid}:done"), ("Перенести…", f"tk:{tid}:move")]]
        if not self._to_member(t, f"Напоминаю: «{t['title']}»" + (f" — срок {due}." if due else "."), btn):
            raise TeamError("сотрудник ещё не открыл приглашение")
        with self._lock:
            self._ev(t, "nudge")
        self._changed()
        return self.public()

    def message(self, who, text):
        """Написать сотруднику не по поручению — ответить на его сообщение или сказать что-то (0.56; владелец: «сотрудник может
        написать руководителю, а ответить ему из студии нельзя»). who — id или имя. Уходит туда же, где он получает поручения:
        в Telegram, MAX или приложение Dewiar. В «Сообщения» — со стрелкой «вы → он». -> public()"""
        text = str(text or "").strip()[:1000]
        if not text:
            raise TeamError("что написать?")
        mid = who if who in self.st["members"] else self.find(who)
        m = self.st["members"][mid]
        chat = (m.get("tg") or {}).get("chat")
        if not chat:
            raise TeamError(f"{m['name']} ещё не {verb(m['name'], 'вошёл')} — сообщение не дойдёт; отправьте приглашение")
        if self._send(chat, f"{self.boss()}: {text}", ch=self._mch(m)) is None:
            raise TeamError("не отправилось — проверьте связь и попробуйте ещё раз")
        with self._lock:
            self.st.setdefault("inbox", []).append({"ts": time.time(), "who": mid, "t": text, "out": True})
            self.st["inbox"] = self.st["inbox"][-200:]
        self._changed()
        return self.public()

    def _task(self, tid):
        t = self.st["tasks"].get(tid)
        if not t:
            raise TeamError("нет такого поручения")
        return t

    def _to_member(self, t, text, buttons=None):
        m = self.st["members"].get(t.get("who")) or {}
        chat = (m.get("tg") or {}).get("chat")
        return bool(chat) and self._send(chat, text, buttons, ch=self._mch(m)) is not None

    # ---------- приложение Dewiar (режим «Сотрудник») ----------

    def _app_close(self):
        c = self.bots["app"].close()
        if c is None:
            raise TeamError("на этом компьютере нет связи с Dewiar")
        return c

    def app_invite(self, mid, renew=False):
        """Код для входа сотрудника в приложении: печать Dewiar (ссылка) — 14 дней. Новый телефон или другой аккаунт —
        «Новая ссылка» (renew) тому же сотруднику: история и поручения на месте, прежняя связь заменится."""
        m = self.st["members"].get(mid)
        if not m:
            raise TeamError("нет такого сотрудника")
        if not self.bots["app"].connected():
            raise TeamError("включите способ «Приложение Dewiar» — «Поручения» → «Как это работает»")
        from close import CloseError
        try:
            d = self._app_close().work_invite(mid, team=self.company(), who=m["name"], boss=self.boss(), renew=renew)
        except CloseError as e:
            raise TeamError(str(e)) from e
        with self._lock:
            m["app_inv"] = {"link": d.get("link", ""), "token": d.get("token", ""), "expires": int(d.get("expires") or 0)}
        self._changed()
        return self.public()

    def _app_leave(self, mid):
        from close import CloseError
        try:
            self._app_close().work_leave(mid=mid)
        except (CloseError, TeamError) as e:
            log.info("Поручения: связь с сотрудником в приложении не снялась: %s", e)

    def _app_snapshot(self, mid):
        m = self.st["members"].get(mid) or {}
        now = datetime.now()
        cut = time.time() - 7 * 86400
        tasks = []
        for t in sorted(self.st["tasks"].values(), key=lambda x: (x.get("due") or "9999", x.get("created", 0))):
            if t.get("who") != mid or t.get("gone"):
                continue
            last = (t.get("log") or [{}])[-1].get("ts", t.get("created", 0))
            if t["state"] in ("done", "ok") and last < cut:
                continue
            tasks.append({"id": t["id"], "title": t["title"], "note": t.get("note", ""), "due": t.get("due", ""),
                          "due_text": due_text(t.get("due"), now), "state": t["state"], "reason": t.get("reason", ""),
                          "report": (t.get("report") or {}).get("t", ""), "remark": next((e.get("t", "") for e in reversed(t.get("log") or []) if e.get("ev") == "back"), "") if t["state"] == "work" else "",
                          "late": bool(t["state"] in OPEN and t.get("due") and t["due"] <= now.strftime("%Y-%m-%dT%H:%M"))})
        reps = [{"title": r["title"], "rule": repeat_text(r["rep"])} for r in self.st.get("repeats", {}).values() if r.get("who") == mid]
        return {"team": self.company(), "boss": self.boss(), "who": m.get("name", ""), "tasks": tasks, "repeats": reps}

    def _app_push(self, mid, text="", quiet=False):
        """Снимок поручений сотруднику mid в приложение (и текст для уведомления). -> "app" или None."""
        m = self.st["members"].get(mid) if mid else None
        pid = ((m or {}).get("tg") or {}).get("id") if m and self._mch(m) == "app" else None
        if not pid:
            return None
        from close import CloseError
        try:
            self._app_close().work_send(pid, dict(self._app_snapshot(mid), t="snap", text=str(text or "")[:1000], quiet=bool(quiet)))
            return "app"
        except (CloseError, TeamError) as e:
            log.info("Поручения: в приложение не ушло: %s", e)
            self.bots["app"].problem = str(e)
            return None

    def _mid_by_pid(self, pid):
        for mid, m in self.st["members"].items():
            if pid and (m.get("tg") or {}).get("id") == pid and self._mch(m) == "app":
                return mid
        return None

    def app_event(self, kind, pid, env, name=""):
        """Знак сайта: workin — сотрудник вошёл по коду (env.mid), workx — связь кончилась (ушёл сам или заменили)."""
        if kind == "workin":
            mid = str((env or {}).get("mid") or "")
            m = self.st["members"].get(mid)
            if not m:
                return
            with self._lock:
                was = (m.get("tg") or {}).get("id") if self._mch(m) == "app" else None
                m["tg"] = {"id": pid, "chat": pid, "ch": "app", "name": name or "", "username": ""}
                m["code"], m["joined"] = "", time.time()
                m.pop("app_inv", None)
                m.pop("left", None)
            again = was and was != pid
            self._tell("👥 Поручения", f"{m['name']} {verb(m['name'], 'подключился')} к поручениям в приложении Dewiar"
                       + (" (новый телефон или аккаунт)" if again else "") + ".", speak=False)
            self._app_push(mid, f"Здравствуйте, {m['name']}! Поручения «{self.company()}» теперь приходят сюда, в «Работу».")
            self._changed()
        elif kind == "workx":
            mid = self._mid_by_pid(pid)
            if not mid:
                return
            m = self.st["members"][mid]
            with self._lock:
                m["tg"], m["left"] = None, time.time()
            if (env or {}).get("by") == "emp":
                self._tell("👥 Поручения", f"{m['name']} {verb(m['name'], 'вышел')} из «Поручений» в приложении — новые поручения ему не придут. "
                           "Вернуть — «Новая ссылка» у сотрудника.", speak=False)
            self._changed()

    def app_incoming(self, pid, body, name=""):
        """Действие сотрудника из приложения: take | done (текст и фото) | move (срок и причина) | msg | hello."""
        mid = self._mid_by_pid(pid)
        if not mid or not isinstance(body, dict) or body.get("t") != "act":
            return
        m = self.st["members"][mid]
        act, nm = str(body.get("act") or ""), m["name"]
        if act == "hello":                                 # открыл «Работу» — прислать свежий снимок
            self._app_push(mid, "", quiet=True)
            return
        if act == "msg":
            text = str(body.get("text") or "").strip()[:1000]
            photo = self._app_photo(body.get("photo"), f"msg-{mid}")
            if not text and not photo:
                return
            with self._lock:
                self.st.setdefault("inbox", []).append({"ts": time.time(), "who": mid, "t": text, "photo": photo})
                self.st["inbox"] = self.st["inbox"][-200:]
            self._tell(f"👥 {nm}", text or f"{verb(nm, 'прислал')} фото", speak=True)
            self._changed()
            return
        t = self.st["tasks"].get(str(body.get("tid") or ""))
        if not t or t.get("who") != mid or t["state"] in ("done", "ok") and act != "done":
            self._app_push(mid, "", quiet=True)
            return
        if act == "take" and t["state"] in OPEN:
            with self._lock:
                t["state"] = "work"
                self._ev(t, "take")
            self._tell("👥 Поручения", f"{nm} {verb(nm, 'взял')} в работу: «{t['title']}».", speak=False)
        elif act == "done" and t["state"] in OPEN:
            word = str(body.get("text") or "").strip()[:1000]
            photo = self._app_photo(body.get("photo"), t["id"])
            with self._lock:
                t["state"] = "done"
                t["report"] = {"t": word, "photo": photo, "ts": time.time()}
                self._ev(t, "done", word)
            self._tell("✅ Поручения", f"{nm} {verb(nm, 'сделал')}: «{t['title']}»" + (f" — {word}" if word else "") + (". Есть фото." if photo else "."))
        elif act == "move" and t["state"] in OPEN:
            at = None
            try:
                at = datetime.fromisoformat(str(body.get("due") or ""))
            except ValueError:
                at, _ = due_parse(str(body.get("when") or ""))
            why = str(body.get("why") or "").strip()[:300]
            if at is None or not why:
                self._app_push(mid, "Перенос не записан: нужны новый срок и причина.", quiet=False)
                return
            with self._lock:
                t["state"], t["due"], t["reason"] = "moved", at.strftime("%Y-%m-%dT%H:%M"), why
                t.pop("nudged", None)
                t.pop("late", None)
                self._ev(t, "move", f"на {due_text(t['due'])}: {why}")
            self._tell("↪ Поручения", f"{nm} переносит «{t['title']}» на {due_text(t['due'])}: {why}.")
        else:
            self._app_push(mid, "", quiet=True)
            return
        self._app_push(mid, "", quiet=True)               # снимок — на все устройства сотрудника
        self._changed()

    def _app_photo(self, ph, base):
        """Фото от сотрудника ({id, key} — зашифрованный файл на сайте) -> имя файла в STATE_DIR/team или ""."""
        if not isinstance(ph, dict) or not ph.get("id") or not ph.get("key"):
            return ""
        try:
            data = self._app_close().work_file(str(ph["id"]), str(ph["key"]))
        except Exception as e:  # noqa: BLE001
            log.info("Поручения: фото из приложения не скачалось: %s", e)
            return ""
        if not data or len(data) > 12 * 1024 * 1024:
            return ""
        self.files.mkdir(parents=True, exist_ok=True)
        name = f"{base}-{int(time.time())}.jpg"
        (self.files / name).write_bytes(data)
        return name

    # ---------- сообщения от сотрудников ----------

    def on_update(self, u, ch="tg"):
        """Событие бота канала ch (в виде Telegram). Канал запоминается на время разбора: ответы уходят туда же."""
        self._tl.ch = ch
        try:
            return self._on_update(u)
        finally:
            self._tl.ch = None

    def _wkey(self, uid):
        return (self._ch(), uid)

    def _on_update(self, u):
        if "callback_query" in u:
            return self._on_button(u["callback_query"])
        m = u.get("message")
        if not m or (m.get("chat") or {}).get("type") != "private":
            return
        user, chat = m.get("from") or {}, m["chat"]["id"]
        text = (m.get("text") or m.get("caption") or "").strip()
        mid = self._mid_by_tg(user.get("id"))
        if text.startswith("/start") or (not mid and re.fullmatch(r"[0-9a-f]{10}", text)):
            code = text.split()[-1] if text else ""
            return self._join(user, chat, code, mid)
        if not mid:
            if (self._ch(), chat) not in self._strangers:
                self._strangers.add((self._ch(), chat))
                self._send(chat, f"Это рабочий бот «{self.company()}». Попросите у руководителя личную ссылку-приглашение.")
            return
        cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        if cmd == "/help":
            return self._send(chat, HELP)
        if cmd == "/tasks":
            return self._list(mid, chat)
        w = self._waiting.get(self._wkey(user.get("id")))
        if w and (cmd == "/cancel" or text.lower().strip(" .!") in ("отмена", "отменить", "не надо")):
            self._waiting.pop(self._wkey(user.get("id")), None)
            return self._send(chat, "Хорошо, ничего не меняю.")
        if w and w["step"] == "done":
            return self._done(mid, chat, user.get("id"), w["tid"], text, m)
        if w and w["step"] == "move":
            return self._move(mid, chat, user.get("id"), w["tid"], text)
        if w and w["step"] == "why":
            return self._move(mid, chat, user.get("id"), w["tid"], text, at=datetime.fromisoformat(w["at"]))
        # просто сообщение — руководителю
        name = self.st["members"][mid]["name"]
        files = self._photo(m, f"msg-{mid}")
        with self._lock:
            self.st.setdefault("inbox", []).append({"ts": time.time(), "who": mid, "t": text[:1000], "photo": files})
            self.st["inbox"] = self.st["inbox"][-200:]
        self._tell(f"👥 {name}", text or f"{verb(name, 'прислал')} фото", speak=True)
        self._send(chat, f"Передала {name_case(self.boss(), 'dat')}.")
        self._changed()

    def _join(self, user, chat, code, mid):
        if mid:
            m = self.st["members"][mid]
            return self._send(chat, f"Вы уже в команде «{self.company()}», {m['name']}. " + HELP)
        with self._lock:
            hit = None
            for k, m in self.st["members"].items():
                if code and m.get("code") == code and not m.get("tg") and time.time() - m.get("code_at", 0) <= CODE_DAYS * 86400:
                    hit = k
                    break
            if hit:
                m = self.st["members"][hit]
                m["tg"] = {"id": user.get("id"), "chat": chat, "username": user.get("username", ""), "ch": self._ch(),
                           "name": " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)}
                m["code"] = ""
                m["joined"] = time.time()
        if not hit:
            return self._send(chat, "Приглашение не подошло или устарело — попросите у руководителя новую ссылку.")
        self._send(chat, f"Здравствуйте, {m['name']}! Я — рабочий бот «{self.company()}». " + HELP)
        self._tell("👥 Поручения", f"{m['name']} {verb(m['name'], 'подключился')} к поручениям в {self.bots[self._ch()].NAME}.", speak=False)
        for t in self.st["tasks"].values():                       # поручения, данные до входа, — сразу
            if t["who"] == hit and t["state"] in OPEN and not t.get("msg"):
                t["msg"] = self._send(chat, self._card(t), [[("Беру", f"tk:{t['id']}:take"), ("Перенести…", f"tk:{t['id']}:move")]])
        self._changed()

    def _list(self, mid, chat):
        mine = [t for t in self.st["tasks"].values() if t["who"] == mid and t["state"] in OPEN]
        if not mine:
            return self._send(chat, "Открытых поручений нет 🙌")
        mine.sort(key=lambda t: t.get("due") or "9999")
        for t in mine[:10]:
            due = due_text(t.get("due"))
            btn = [[("Беру", f"tk:{t['id']}:take"), ("Перенести…", f"tk:{t['id']}:move")]] if t["state"] == "new" else \
                  [[("Сделано", f"tk:{t['id']}:done"), ("Перенести…", f"tk:{t['id']}:move")]]
            self._send(chat, f"{t['title']}" + (f"\nСрок — {due}" if due else "") + f"\n{STATES[t['state']]}", btn)

    def _on_button(self, q):
        uid = (q.get("from") or {}).get("id")
        try:
            self.bots[self._ch()]._call("answerCallbackQuery", callback_query_id=q["id"])
        except (TelegramError, KeyError):
            pass
        mid = self._mid_by_tg(uid)
        mm = re.fullmatch(r"tk:([0-9a-f]{8}):(take|done|move)", q.get("data") or "")
        chat = ((q.get("message") or {}).get("chat") or {}).get("id") or \
            ((self.st["members"].get(mid) or {}).get("tg") or {}).get("chat")     # MAX не присылает чат у нажатия
        if not (mid and mm and chat):
            return
        tid, act = mm.groups()
        t = self.st["tasks"].get(tid)
        if not t or t["who"] != mid:
            return self._send(chat, "Это поручение уже снято.")
        if t["state"] in ("done", "ok"):
            return self._send(chat, "Это поручение уже отмечено сделанным.")
        name = self.st["members"][mid]["name"]
        if act == "take":
            with self._lock:
                t["state"] = "work"
                self._ev(t, "take")
            self._rekey(t, [[("Сделано", f"tk:{tid}:done"), ("Перенести…", f"tk:{tid}:move")]])
            self._send(chat, "Записала: в работе. Когда сделаете — нажмите «Сделано» и пришлите фото, если нужно подтверждение.")
            self._tell("👥 Поручения", f"{name} {verb(name, 'взял')} в работу: «{t['title']}».", speak=False)
            self._changed()
        elif act == "done":
            self._waiting[self._wkey(uid)] = {"tid": tid, "step": "done"}
            self._send(chat, f"«{t['title']}» — напишите пару слов, что сделано, и пришлите фото, если нужно. "
                             "Или просто «готово».")
        else:
            self._waiting[self._wkey(uid)] = {"tid": tid, "step": "move"}
            self._send(chat, "На когда переносим и почему? Одной фразой, например: «на понедельник, клиент заболел».")

    def _photo(self, m, base):
        """Фото (или картинка документом) из сообщения -> имя файла в STATE_DIR/team или ""."""
        try:
            files, _voice = self.bots[self._ch()]._attachments(m)
        except TelegramError as e:
            log.info("Команда: фото не скачалось: %s", e)
            return ""
        for f in files:
            if re.search(r"\.(jpe?g|png|webp)$", f["name"], re.I) or m.get("photo"):
                self.files.mkdir(parents=True, exist_ok=True)
                name = f"{base}-{int(time.time())}.jpg"
                (self.files / name).write_bytes(f["data"])
                return name
        return ""

    def _done(self, mid, chat, uid, tid, text, m):
        t = self.st["tasks"].get(tid)
        if not t:
            self._waiting.pop(self._wkey(uid), None)
            return self._send(chat, "Это поручение уже снято.")
        photo = self._photo(m, tid)
        word = text if text and text.lower() not in ("готово", "сделано", "да", "ок", "ok") else ""
        with self._lock:
            t["state"] = "done"
            t["report"] = {"t": word[:1000], "photo": photo, "ts": time.time()}
            self._ev(t, "done", word)
        self._waiting.pop(self._wkey(uid), None)
        self._rekey(t, None)
        self._send(chat, "Отметила сделанным" + (", фото приложила" if photo else "") + f". {self.boss()} увидит это в календаре.")
        name = self.st["members"][mid]["name"]
        self._tell("✅ Поручения", f"{name} {verb(name, 'сделал')}: «{t['title']}»" + (f" — {word}" if word else "") + (". Есть фото." if photo else "."))
        self._changed()

    def _move(self, mid, chat, uid, tid, text, at=None):
        """Новый срок и причина. Срок без причины — спросить причину (шаг why); причина без срока — спросить срок."""
        t = self.st["tasks"].get(tid)
        if not t:
            self._waiting.pop(self._wkey(uid), None)
            return self._send(chat, "Это поручение уже снято.")
        if at is None:
            at, rest = due_parse(text)
            if at is None:
                return self._send(chat, "Не поняла новый срок. Напишите, например: «на пятницу, жду документы» или «завтра к 12, нет пропуска». "
                                        "Передумали — «отмена».")
        else:
            rest = text
        reason = re.sub(r"^[\s,.;:—-]+", "", rest or "").strip()
        k = text.lower().find(reason.lower()) if reason else -1
        if k >= 0:
            reason = text[k:k + len(reason)]               # как написал сотрудник (when.parse делает первую букву заглавной)
        if not reason:
            self._waiting[self._wkey(uid)] = {"tid": tid, "step": "why", "at": at.isoformat()}
            return self._send(chat, f"Перенесу на {due_text(at.strftime('%Y-%m-%dT%H:%M'))}. А почему? Одной фразой — это увидит {self.boss()}.")
        with self._lock:
            t["state"], t["due"], t["reason"] = "moved", at.strftime("%Y-%m-%dT%H:%M"), reason[:300]
            t.pop("nudged", None)
            t.pop("late", None)
            self._ev(t, "move", f"на {due_text(t['due'])}: {reason}")
        self._waiting.pop(self._wkey(uid), None)
        self._rekey(t, [[("Сделано", f"tk:{tid}:done"), ("Перенести…", f"tk:{tid}:move")]])
        self._send(chat, f"Перенесла на {due_text(t['due'])}. {self.boss()} увидит причину.")
        name = self.st["members"][mid]["name"]
        self._tell("↪ Поручения", f"{name} переносит «{t['title']}» на {due_text(t['due'])}: {reason}.")
        self._changed()

    # ---------- сроки ----------

    def _ticker(self):
        while not self._tick_stop.wait(60):
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                log.debug("Команда: сроки", exc_info=True)

    def tick(self, now=None):
        """За час до срока — напомнить сотруднику (один раз); срок прошёл — отметить «просрочено» (студия красит)."""
        now = now or datetime.now()
        changed = False
        for t in list(self.st["tasks"].values()):
            if t["state"] not in OPEN or not t.get("due"):
                continue
            try:
                d = datetime.fromisoformat(t["due"])
            except ValueError:
                continue
            if not t.get("nudged") and timedelta(0) < d - now <= timedelta(hours=1):
                t["nudged"] = True
                changed = True
                btn = [[("Беру", f"tk:{t['id']}:take")]] if t["state"] == "new" else [[("Сделано", f"tk:{t['id']}:done"), ("Перенести…", f"tk:{t['id']}:move")]]
                self._to_member(t, f"Напоминаю: «{t['title']}» — срок {due_text(t['due'], now)}.", btn)
            if not t.get("late") and d <= now:
                t["late"] = True
                changed = True
        # повторяющиеся: пришло время — поручение уходит само, следующий срок — по правилу
        from when import next_time
        for r in list(self.st.get("repeats", {}).values()):
            try:
                due = datetime.fromisoformat(r["next"])
            except (KeyError, ValueError):
                continue
            if now < post_at(due) or r["who"] not in self.st["members"]:
                continue
            nxt = next_time(r["rep"], due)
            r["next"] = nxt.strftime("%Y-%m-%dT%H:%M")
            changed = True
            if due > now - timedelta(hours=12):        # компьютер был выключен давно — старое не шлём, ждём следующего
                try:
                    self.assign(r["who"], r["title"], due.strftime("%Y-%m-%dT%H:%M"), r.get("note", ""), via="repeat")
                except TeamError as e:
                    log.info("Команда: повтор «%s» не ушёл: %s", r["title"], e)
        # итог дня руководителю (раз в день, если за день что-то было)
        dg = self.st.get("digest") or ""
        if re.fullmatch(r"\d{1,2}:\d\d", dg) and now.strftime("%H:%M") >= dg.zfill(5) and self.st.get("digest_day") != now.date().isoformat():
            self.st["digest_day"] = now.date().isoformat()
            changed = True
            text = self.digest(now)
            if text:
                self._tell("Поручения — итог дня", text)
        if changed:
            self._changed()

    def digest(self, now=None):
        """Итог дня: что сделано, что перенесено и почему, что просрочено, на завтра. Ничего не было — ""."""
        now = now or datetime.now()
        day0 = datetime(now.year, now.month, now.day).timestamp()
        name = lambda t: ((self.st["members"].get(t["who"]) or {}).get("name") or "—").split()[0]
        done, moved, late = [], [], []
        for t in self.st["tasks"].values():
            evs = [e["ev"] for e in t.get("log", []) if e.get("ts", 0) >= day0]
            if "done" in evs or ("ok" in evs and t["state"] == "ok"):
                done.append(f"{name(t)} — «{t['title']}»")
            elif "move" in evs and t["state"] == "moved":
                moved.append(f"{name(t)} — «{t['title']}»" + (f" на {due_text(t.get('due'), now)}" if t.get("due") else "") + (f", причина: {t['reason']}" if t.get("reason") else ""))
            if t["state"] in OPEN and t.get("due") and t["due"] <= now.strftime("%Y-%m-%dT%H:%M"):
                late.append(f"{name(t)} — «{t['title']}»")
        tmr = (now + timedelta(days=1)).date().isoformat()
        tomorrow = sum(1 for t in self.st["tasks"].values() if t["state"] in OPEN and (t.get("due") or "").startswith(tmr))
        if not (done or moved or late):
            return ""
        parts = []
        if done:
            parts.append(f"Сделано {len(done)}: " + "; ".join(done[:8]) + ".")
        if moved:
            parts.append(f"Перенесено {len(moved)}: " + "; ".join(moved[:6]) + ".")
        if late:
            parts.append(f"Просрочено {len(late)}: " + "; ".join(late[:6]) + ".")
        if tomorrow:
            parts.append(f"На завтра — {tomorrow} {'поручение' if tomorrow % 10 == 1 and tomorrow % 100 != 11 else 'поручения' if tomorrow % 10 in (2, 3, 4) and tomorrow % 100 not in (12, 13, 14) else 'поручений'}.")
        return "Итог дня по поручениям. " + " ".join(parts)

    # ---------- для студии и модели ----------

    def photo_path(self, name):
        p = (self.files / Path(str(name)).name)
        return p if p.is_file() else None

    def public(self):
        bot = self.bot.data.get("bot") or {}
        now = datetime.now()
        bots = [{"ch": ch, "name": b.NAME, "connected": b.connected(), "bot": (b.data.get("bot") or {}).get("username", ""),
                 "bot_name": (b.data.get("bot") or {}).get("name", ""), "problem": b.problem,
                 "running": bool(b._thread and b._thread.is_alive())} for ch, b in self.bots.items()]
        members = []
        for mid, m in self.st["members"].items():
            mine = [t for t in self.st["tasks"].values() if t["who"] == mid]
            members.append({"id": mid, "name": m["name"], "role": m.get("role", ""), "color": m.get("color", COLORS[0]),
                            "joined": bool(m.get("tg")), "tg": ((m.get("tg") or {}).get("username") or ""), "link": self._link(m),
                            "links": self._links(m), "ch": self.bots[self._mch(m)].NAME if m.get("tg") else "",
                            "chk": self._mch(m) if m.get("tg") else "",
                            "app": ({"link": (m.get("app_inv") or {}).get("link", ""), "expires": (m.get("app_inv") or {}).get("expires", 0)}
                                    if m.get("app_inv") and (m["app_inv"].get("expires") or 0) > time.time() else None),
                            "left": bool(m.get("left") and not m.get("tg")),
                            "expired": not m.get("tg") and bool(m.get("code_at")) and time.time() - m["code_at"] > CODE_DAYS * 86400,
                            "open": sum(1 for t in mine if t["state"] in OPEN)})
        tasks = []
        for t in self.st["tasks"].values():
            m = self.st["members"].get(t["who"]) or {}
            late = bool(t["state"] in OPEN and t.get("due") and t["due"] <= now.strftime("%Y-%m-%dT%H:%M"))
            tasks.append(dict({k: t.get(k) for k in ("id", "title", "note", "due", "state", "created", "reason", "report", "log")},
                         **{"who": t["who"], "name": m.get("name", "—"), "color": m.get("color", COLORS[0]), "due_text": due_text(t.get("due"), now),
                            "late": late, "joined": bool(m.get("tg"))}))
        tasks.sort(key=lambda x: (x.get("due") or "9999", x["created"]))
        ok_cut = time.time() - 14 * 86400
        tasks = [x for x in tasks if x["state"] != "ok" or (x["log"] and x["log"][-1]["ts"] > ok_cut)]
        return {"connected": self.connected(), "bot": bot.get("username", ""), "bot_name": bot.get("name", ""), "bots": bots,
                "problem": "; ".join(f"{b['name']}: {b['problem']}" for b in bots if b["connected"] and b["problem"]),
                "running": any(b["running"] for b in bots),
                "company": self.company() if self.connected() or self.st.get("company") else "", "boss": self.boss(),
                "speak": self.st.get("speak", True) is not False, "members": members, "tasks": tasks, "digest": self.st.get("digest", "18:30"),
                "repeats": [dict(r, name=(self.st["members"].get(r["who"]) or {}).get("name", "—"), rule=repeat_text(r["rep"]),
                                 next_text=due_text(r["next"], now)) for r in sorted(self.st.get("repeats", {}).values(), key=lambda x: x["next"])],
                "inbox": [dict(x, name=(self.st["members"].get(x["who"]) or {}).get("name", "—")) for x in self.st.get("inbox", [])[-20:]],
                "counts": {s: sum(1 for x in tasks if x["state"] == s) for s in STATES}}

    def boss_snap(self):
        """Доска для своего телефона руководителя («Поручения» на телефоне, 0.56): кто, что, сроки, отчёты и переписка —
        без ссылок-приглашений, кодов и путей к фото. Уходит только своим устройствам, зашифрованным (конверт own)."""
        p = self.public()

        def remark(t):
            back = [e for e in t.get("log") or [] if e.get("ev") == "back"]
            return back[-1].get("t", "") if back and t["state"] in OPEN else ""
        tasks = [{"id": t["id"], "title": t["title"], "note": t.get("note") or "", "state": t["state"], "who": t["who"], "name": t["name"],
                  "due": t.get("due") or "", "due_text": t["due_text"], "late": t["late"], "reason": t.get("reason") or "",
                  "report": (t.get("report") or {}).get("t", "") if isinstance(t.get("report"), dict) else "",
                  "photo": bool((t.get("report") or {}).get("photo")) if isinstance(t.get("report"), dict) else False,
                  "remark": remark(t), "ts": (t.get("log") or [{}])[-1].get("ts") or t.get("created") or 0} for t in p["tasks"]]
        return {"company": p["company"], "boss": p["boss"], "at": int(time.time() * 1000),
                "members": [{k: m[k] for k in ("id", "name", "role", "color", "joined", "open", "left")} for m in p["members"]],
                "tasks": tasks[:150], "repeats": [{"title": r["title"], "name": r["name"], "rule": r["rule"]} for r in p["repeats"]][:30],
                "inbox": [{"ts": x["ts"], "who": x["who"], "name": x["name"], "t": x.get("t") or "", "out": bool(x.get("out")),
                           "photo": bool(x.get("photo"))} for x in p["inbox"]]}

    def summary(self, who=""):
        """Для модели и «что с поручениями?»: коротко по открытым и сделанным за неделю."""
        if not self.st["tasks"] and not self.st.get("repeats"):
            return "Поручений пока нет."
        mid = self.find(who) if who else None
        rows = []
        now = datetime.now()
        for t in sorted(self.st["tasks"].values(), key=lambda x: x.get("due") or "9999"):
            if mid and t["who"] != mid:
                continue
            if t["state"] == "ok" and (time.time() - t["log"][-1]["ts"]) > 7 * 86400:
                continue
            m = (self.st["members"].get(t["who"]) or {}).get("name", "—")
            due = due_text(t.get("due"), now)
            late = t["state"] in OPEN and t.get("due") and datetime.fromisoformat(t["due"]) <= now
            extra = (f", причина: {t['reason']}" if t["state"] == "moved" and t.get("reason") else "") + \
                    (f", отчёт: {t['report']['t']}" if t["state"] == "done" and (t.get("report") or {}).get("t") else "")
            rows.append(f"- {m}: «{t['title']}» — {STATES[t['state']].lower()}" + (f", срок {due}" if due else "")
                        + (" (просрочено)" if late else "") + extra)
        for r in self.st.get("repeats", {}).values():
            if not mid or r["who"] == mid:
                rows.append(f"- {(self.st['members'].get(r['who']) or {}).get('name', '—')}: «{r['title']}» — повторяется {repeat_text(r['rep'])}")
        return "\n".join(rows[:40]) or "По этому человеку поручений нет."

    def calendar(self, first, last):
        """Поручения со сроком в месяце — для «Календаря»: [(дата, item)]."""
        out = []
        for t in self.st["tasks"].values():
            if not t.get("due"):
                continue
            try:
                d = datetime.fromisoformat(t["due"])
            except ValueError:
                continue
            if first <= d <= last:
                m = (self.st["members"].get(t["who"]) or {}).get("name", "")
                mark = "✓ " if t["state"] in ("done", "ok") else ""
                out.append((d.date().isoformat(), {"type": "event", "time": d.strftime("%H:%M"), "end": "", "title": f"{mark}{t['title']} — {m}",
                                                   "place": "", "cal": "Поручения", "color": "#B79CFF", "team": t["id"], "state": t["state"]}))
        return out
