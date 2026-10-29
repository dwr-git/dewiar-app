"""«Посты» бота персонажа (0.69; запрос бизнеса 29.10: «чтобы Лира писала в группы Telegram — посты по расписанию»;
владелец: «все пункты делаем»). Честно: пишет сам канал или бот компании, от своего имени, — никаких выдуманных
собеседников, отзывов и «живых» диалогов (такой «прогрев» мы не делаем: это обман подписчиков).

Где: группы, куда добавлен бот персонажа, и каналы, где он администратор (Telegram присылает my_chat_member, когда бота
назначили; можно и вписать @канал — проверим, что бот там админ с правом публикации).
Что: пост (текст до 4096) или опрос (вопрос и 2–10 вариантов). Когда: сейчас или ко времени. Одобрение: пост может
ждать «Опубликовать» владельца — так по умолчанию у всего, что пишет модель сама (рубрики, «Придумать»).
Рубрики: «по будням в 10:00 — совет дня о чае»: в срок персонаж пишет пост своим характером, по «О чём бот» и своим
знаниям; с одобрением — пост ждёт и приходит уведомление, без — уходит сразу.
Новички в группах: «приветствовать новичков» — одно сообщение с именами, кто пришёл за последние секунды.

Работает, пока включён компьютер с Dewiar. Состояние — CONFIG_DIR/pbot_posts.json:
{posts: {id: {...}}, rubrics: {id: {...}}, greet: {on, text}}."""

import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from settings import CONFIG_DIR

log = logging.getLogger("dewiar.pbot")
PATH = CONFIG_DIR / "pbot_posts.json"
DAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
GREET = "{имя}, добро пожаловать! Я — {бот}. Спрашивайте — отвечу, когда упомянете меня или ответите на моё сообщение."
WRITE = ("Ты — {name}. Твой характер: {char}\n\nТы ведёшь {where} от имени владельца. Напиши ОДИН пост для Telegram: {how}. "
         "Пиши от своего имени (имени канала или компании) — не выдумывай собеседников, отзывы, цифры, цены, скидки и "
         "события: факты — только из того, что дано ниже. Обычный текст без Markdown (без звёздочек и решёток), 1–3 "
         "эмодзи можно. В конце — вопрос к читателям или простой призыв. Только текст поста, без пояснений.")


class PostError(Exception):
    pass


def _clean(t):
    t = re.sub(r"<think>.*?</think>", "", str(t or ""), flags=re.S)
    t = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"`{1,3}", "", t).strip().strip('"«»').strip()
    return re.sub(r"\n{3,}", "\n\n", t)


class Posts:
    def __init__(self, host, bot, path=PATH, now=None):
        self.host, self.bot, self.path = host, bot, Path(path)
        self.now = now or datetime.now
        self._lock = threading.RLock()
        self.st = {"posts": {}, "rubrics": {}, "greet": {"on": False, "text": ""}}
        try:
            self.st.update(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        self._stop = threading.Event()
        self._thread = None
        self._pending = {}                       # чат -> [имена новичков] (приветствие одним сообщением)
        bot.posts = self

    # ---------- хранение ----------
    def _save(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)

    def _emit(self):
        try:
            self.host.emit("pbot_posts", **self.public())
        except Exception:  # noqa: BLE001
            pass

    # ---------- где публиковать ----------
    def chats(self):
        """Группы и каналы бота: [{id, title, type, username, can}] — can: можно публиковать."""
        out = []
        for cid, c in (self.bot.data.get("chats") or {}).items():
            out.append({"id": cid, "title": c.get("title") or "группа", "type": c.get("type") or "group",
                        "username": c.get("username") or "", "can": c.get("can", True)})
        return sorted(out, key=lambda x: (x["type"] != "channel", x["title"].lower()))

    def add_chat(self, ref):
        """«@канал» или ссылка t.me/канал: бот должен быть там админом (канал) или участником (группа)."""
        ref = (ref or "").strip()
        m = re.search(r"(?:t\.me/|telegram\.me/|@)([A-Za-z0-9_]{4,})", ref) or re.fullmatch(r"([A-Za-z][A-Za-z0-9_]{3,})", ref)
        if not m and not re.fullmatch(r"-?\d{5,}", ref):
            raise PostError("впишите @адрес канала или группы, например @chaidvor")
        cid = ref if not m else "@" + m.group(1)
        if not self.bot.connected():
            raise PostError("сначала подключите бота")
        from telegram import TelegramError
        try:
            chat = self.bot._call("getChat", chat_id=cid)
            me = (self.bot.data.get("bot") or {}).get("id")
            mem = self.bot._call("getChatMember", chat_id=chat["id"], user_id=me)
        except TelegramError as e:
            raise PostError(f"Telegram не пускает: {e}. Добавьте бота в канал администратором с правом публиковать") from e
        st = mem.get("status")
        if chat.get("type") == "channel" and not (st == "creator" or (st == "administrator" and mem.get("can_post_messages", True))):
            raise PostError("бот в канале не администратор — в настройках канала: «Администраторы» → добавьте бота с правом публиковать сообщения")
        if st in ("left", "kicked"):
            raise PostError("бота нет в этой группе — сначала добавьте его туда")
        self.bot.remember_chat(chat, can=True)
        return self.chats()

    def forget_chat(self, cid):
        with self.bot._lock:
            (self.bot.data.get("chats") or {}).pop(str(cid), None)
            self.bot._save()
        return self.chats()

    def on_member(self, upd):
        """my_chat_member: бота назначили в канале или группе (запомнить) или убрали (забыть)."""
        chat, new = upd.get("chat") or {}, upd.get("new_chat_member") or {}
        st = new.get("status")
        if st in ("left", "kicked"):
            self.forget_chat(chat.get("id"))
            return
        can = chat.get("type") != "channel" or st == "creator" or (st == "administrator" and new.get("can_post_messages", True))
        self.bot.remember_chat(chat, can=can)
        self._emit()

    # ---------- посты ----------
    def public(self):
        posts = sorted(self.st["posts"].values(), key=lambda p: (p["status"] not in ("wait", "plan"), p.get("at") or "", -p["created"]))
        return {"posts": posts[:60], "rubrics": list(self.st["rubrics"].values()), "chats": self.chats(), "greet": self.st["greet"],
                "wait": sum(1 for p in self.st["posts"].values() if p["status"] == "wait")}

    def _targets(self, chats):
        have = {c["id"]: c for c in self.chats()}
        ids = [str(c) for c in (chats or []) if str(c) in have] or [c["id"] for c in self.chats() if c["can"]][:1]
        if not ids:
            raise PostError("бот ещё не в канале или группе — добавьте его туда (в канал — администратором)")
        return ids

    def add(self, text="", chats=None, at=None, poll=None, approve=False, source="studio", topic=""):
        """Новый пост. at — datetime или ISO «ГГГГ-ММ-ДДTЧЧ:ММ» (пусто — сейчас); poll — {question, options}.
        approve — ждать «Опубликовать». -> пост."""
        text = str(text or "").strip()[:4096]
        if poll:
            q = str(poll.get("question") or "").strip()[:300]
            opts = [str(o).strip()[:100] for o in poll.get("options") or [] if str(o).strip()][:10]
            if not q or len(opts) < 2:
                raise PostError("в опросе нужны вопрос и хотя бы два варианта")
            poll = {"question": q, "options": opts}
        elif not text:
            raise PostError("пустой пост — напишите текст")
        if isinstance(at, str):
            at = datetime.fromisoformat(at) if at.strip() else None
        pid = uuid.uuid4().hex[:8]
        p = {"id": pid, "text": text, "poll": poll, "chats": self._targets(chats), "at": at.isoformat(timespec="minutes") if at else "",
             "status": "wait" if approve else "plan", "source": source, "topic": topic, "created": time.time(), "sent": [], "err": ""}
        with self._lock:
            self.st["posts"][pid] = p
            done = sorted((x for x in self.st["posts"].values() if x["status"] in ("sent", "failed")), key=lambda x: x["created"])
            for old in done[:-100]:
                self.st["posts"].pop(old["id"], None)
            self._save()
        if p["status"] == "plan" and not p["at"]:
            self.publish(pid)
        self._emit()
        return self.st["posts"][pid]

    def edit(self, pid, text=None, at=None, chats=None):
        with self._lock:
            p = self._get(pid)
            if p["status"] == "sent":
                raise PostError("пост уже опубликован")
            if text is not None:
                if not p.get("poll") and not str(text).strip():
                    raise PostError("пустой пост")
                p["text"] = str(text).strip()[:4096]
            if at is not None:
                p["at"] = datetime.fromisoformat(at).isoformat(timespec="minutes") if at else ""
            if chats is not None:
                p["chats"] = self._targets(chats)
            self._save()
        self._emit()
        return p

    def approve(self, pid):
        """«Опубликовать»: ко времени, если оно впереди, иначе — сейчас."""
        with self._lock:
            p = self._get(pid)
            if p["status"] != "wait":
                return p
            p["status"] = "plan"
            self._save()
        if not p["at"] or datetime.fromisoformat(p["at"]) <= self.now():
            self.publish(pid)
        self._emit()
        return self.st["posts"][pid]

    def delete(self, pid):
        with self._lock:
            self.st["posts"].pop(pid, None)
            self._save()
        self._emit()
        return True

    def _get(self, pid):
        p = self.st["posts"].get(pid)
        if not p:
            raise PostError("такого поста нет")
        return p

    def publish(self, pid):
        """Отправить во все выбранные чаты; ссылка на пост — у публичных каналов и групп."""
        from telegram import TelegramError, chunks
        p = self._get(pid)
        have = {c["id"]: c for c in self.chats()}
        sent, errs = [], []
        for cid in p["chats"]:
            try:
                if p.get("poll"):
                    if p["text"]:
                        self.bot._call("sendMessage", chat_id=cid, text=p["text"][:4096])
                    r = self.bot._call("sendPoll", chat_id=cid, question=p["poll"]["question"], options=p["poll"]["options"], is_anonymous=True)
                else:
                    r = None
                    for part in chunks(p["text"]):
                        x = self.bot._call("sendMessage", chat_id=cid, text=part, disable_web_page_preview=False)
                        r = r or x                                       # ссылка — на первую часть
                u = (have.get(cid) or {}).get("username")
                sent.append({"chat": cid, "title": (have.get(cid) or {}).get("title", ""), "mid": (r or {}).get("message_id"),
                             "link": f"https://t.me/{u}/{(r or {}).get('message_id')}" if u and r else ""})
            except TelegramError as e:
                errs.append(f"{(have.get(cid) or {}).get('title', cid)}: {e}")
        with self._lock:
            p["sent"], p["err"] = sent, "; ".join(errs)[:300]
            p["status"] = "sent" if sent else "failed"
            p["at_sent"] = time.time()
            self._save()
        log.info("📣 Пост %s: %s", pid, "опубликован" if sent else "не ушёл — " + p["err"])
        if errs:
            try:
                self.host.push("Пост не опубликован" if not sent else "Пост ушёл не везде", p["err"], telegram=False)
            except Exception:  # noqa: BLE001
                pass
        self._emit()
        return p

    # ---------- персонаж пишет пост ----------
    def write(self, topic, chat_title="", poll=False):
        """Пост по теме — характером персонажа бота, по «О чём бот» и его знаниям. -> текст."""
        from llm import stream_chat
        p = self.bot.persona()
        name = p.get("name") or "Ассистент"
        char = re.sub(r"\s+", " ", str(p.get("character") or "")).strip()[:700]
        where = f"канал «{chat_title}»" if chat_title else "Telegram-канал"
        how = f"на тему «{topic}», 400–900 знаков" if topic else "полезный и живой, 400–900 знаков"
        system = WRITE.format(name=name, char=char or "доброжелательный и толковый.", where=where, how=how)
        brief = self.bot.opt("brief")
        if brief:
            system += "\n\nО ЧЁМ КАНАЛ И КОМПАНИЯ (от владельца): " + brief
        try:
            kb = self.host._persona_knowledge(topic or brief or name, None, p=p, quiet=True, hist=[])
        except Exception:  # noqa: BLE001
            kb = ""
        if kb:
            system += kb
        prof = self.host.persona_llm(p.get("id")) if p.get("id") else self.host.s.active_llm()
        if not (prof or {}).get("base_url") and (prof or {}).get("kind") != "ollama":
            raise PostError("у персонажа нет мозга — выберите модель в «Персонажах»")
        out = _clean("".join(stream_chat(dict(prof, max_tokens=900, temperature=0.8), system,
                                         [{"role": "user", "content": f"Тема: {topic or 'на твой выбор, по делу канала'}"}])))
        if not out:
            raise PostError("модель ответила пустотой — попробуйте ещё раз")
        return out[:4096]

    # ---------- рубрики ----------
    def rubric_set(self, r):
        """{id?, topic, days: [0..6], time: «ЧЧ:ММ», chats, approve} -> рубрика."""
        topic = str(r.get("topic") or "").strip()[:300]
        if not topic:
            raise PostError("о чём рубрика? Например: «совет дня о чае»")
        tm = str(r.get("time") or "10:00").strip()
        if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", tm):
            raise PostError("время — как 10:00")
        days = sorted({int(d) for d in (r.get("days") or range(7)) if 0 <= int(d) <= 6})
        if not days:
            raise PostError("выберите хотя бы один день")
        rid = r.get("id") or uuid.uuid4().hex[:8]
        old = self.st["rubrics"].get(rid) or {}
        ru = {"id": rid, "topic": topic, "days": days, "time": tm.zfill(5), "chats": self._targets(r.get("chats")),
              "approve": r.get("approve", True) is not False, "on": r.get("on", True) is not False, "last": old.get("last", "")}
        with self._lock:
            self.st["rubrics"][rid] = ru
            self._save()
        self._emit()
        return ru

    def rubric_del(self, rid):
        with self._lock:
            self.st["rubrics"].pop(rid, None)
            self._save()
        self._emit()
        return True

    def when_text(self, ru):
        d = ru["days"]
        when = "каждый день" if len(d) == 7 else "по будням" if d == [0, 1, 2, 3, 4] else "по выходным" if d == [5, 6] else ", ".join(DAYS[i] for i in d)
        return f"{when} в {ru['time']}"

    def _rubric_due(self, now):
        for ru in list(self.st["rubrics"].values()):
            if not ru.get("on", True) or now.weekday() not in ru["days"] or ru.get("last") == now.date().isoformat():
                continue
            h, m = map(int, ru["time"].split(":"))
            if (now.hour, now.minute) < (h, m) or now - now.replace(hour=h, minute=m, second=0, microsecond=0) > timedelta(hours=2):
                continue
            with self._lock:
                ru["last"] = now.date().isoformat()
                self._save()
            yield ru

    def _make(self, ru):
        title = next((c["title"] for c in self.chats() if c["id"] in ru["chats"]), "")
        try:
            text = self.write(ru["topic"], title)
        except Exception as e:  # noqa: BLE001
            log.info("📣 Рубрика «%s»: пост не написался: %s", ru["topic"], e)
            self.host.push("Рубрика не вышла", f"«{ru['topic']}»: {e}", telegram=False)
            return
        p = self.add(text, ru["chats"], None, approve=ru["approve"], source="rubric", topic=ru["topic"])
        if ru["approve"]:
            self.host.push("Пост ждёт одобрения", f"Рубрика «{ru['topic']}» — студия → «Бот в Telegram» → «Посты»", telegram=True)
        return p

    # ---------- новички ----------
    def greet_set(self, on=None, text=None):
        with self._lock:
            g = self.st["greet"]
            if on is not None:
                g["on"] = bool(on)
            if text is not None:
                g["text"] = str(text or "").strip()[:600]
            self._save()
        self._emit()
        return g

    def newcomers(self, chat, users):
        """Новички в группе — одним сообщением через несколько секунд (пришли трое — одно приветствие)."""
        if not self.st["greet"].get("on"):
            return
        names = [" ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or u.get("username") or "друг"
                 for u in users if not u.get("is_bot")]
        if not names:
            return
        cid = chat["id"]
        with self._lock:
            first = cid not in self._pending
            self._pending.setdefault(cid, []).extend(names)
        if first:
            threading.Timer(self.greet_delay, self._greet, args=(cid,)).start()

    greet_delay = 8.0

    def _greet(self, cid):
        with self._lock:
            names = self._pending.pop(cid, [])
        if not names:
            return
        who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " и " + names[-1]
        bot = self.bot.persona().get("name") or (self.bot.data.get("bot") or {}).get("name") or "бот"
        text = (self.st["greet"].get("text") or GREET).replace("{имя}", who).replace("{бот}", bot)
        self.bot._send(cid, text)

    # ---------- часы ----------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="pbot-posts", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def tick(self):
        """Раз в 20 с: посты, которым пора, и рубрики, у которых сегодня срок."""
        if not self.bot.connected():
            return
        now = self.now()
        for p in list(self.st["posts"].values()):
            if p["status"] == "plan" and p["at"] and datetime.fromisoformat(p["at"]) <= now:
                self.publish(p["id"])
        for ru in self._rubric_due(now):
            self._make(ru)

    def _loop(self):
        while not self._stop.wait(20):
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                log.exception("Посты: часы")
