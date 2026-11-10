"""«Чат» студии, 0.86: «Ещё раз», «Изменить», беседы и выгрузка (лента — core/chatlog.py).
Примесь класса Engine (core/engine.py): self — это Engine.

Пользователь (0.85): «нельзя ли в чат добавить стандартные для всех чатов вещи — кнопки остановки, перегенерации,
исправления и метрики? Без этого неуютно». «Стоп» — уже есть (команда stop), метрики приходят с ответом (meta в событии
answer → запись ленты). Здесь:
— chat_regen: переспросить модель тем же последним вопросом; новый ответ — вариант той же записи (листать 1/2);
— chat_edit: поправить последний вопрос и спросить заново; ответы после него убираются из ленты;
— chat_threads / chat_thread_new / _open / _rename / _delete: беседы (идея №145) — у каждой своя лента и своя память
  модели (содержание и дословные реплики), открыть старую — продолжить её;
— chat_export: беседа в .md или .txt.
Память модели при «Ещё раз» и «Изменить» откатывается на один ход (_chat_rewind): иначе модель видела бы прежний ответ
и повторяла его. Окна узнают о переменах событиями: chat (запись), chat_cut (вопрос исправлен — всё после него убрать),
chat_threads (список бесед и какая открыта) — все открытые студии (и удалённые, по мосту) остаются в согласии."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка

CHAT_CMDS = ("chat_regen", "chat_edit", "chat_threads", "chat_thread_new", "chat_thread_open", "chat_thread_rename",
             "chat_thread_delete", "chat_export")
IMG_NOTE = " [к сообщению была приложена картинка]"
PEND_TTL = 900            # с: «Ещё раз»/«Изменить» ждут свой ответ не дольше (дольше — это уже другой разговор)


def _norm(t):
    return " ".join(str(t or "").split())


class ChatMixin:
    def chat_cmd(self, cmd, a):
        if cmd == "chat_regen":
            return self._chat_regen(a)
        if cmd == "chat_edit":
            return self._chat_edit(a)
        if cmd == "chat_threads":
            return {"threads": self.chatlog.threads()}
        if cmd == "chat_thread_new":
            return self._chat_switch(lambda: self.chatlog.thread_new(), fresh=True)
        if cmd == "chat_thread_open":
            return self._chat_switch(lambda: self.chatlog.thread_open(str(a.get("id") or "")))
        if cmd == "chat_thread_rename":
            self.chatlog.thread_rename(str(a.get("id") or ""), str(a.get("title") or ""))
            return self._chat_threads_emit()
        if cmd == "chat_thread_delete":
            tid = str(a.get("id") or "")
            if tid in ("", self.chatlog.threads()[0]["id"]):
                return self._chat_switch(lambda: self.chatlog.thread_delete(tid), fresh=True)
            self.chatlog.thread_delete(tid)
            return self._chat_threads_emit()
        if cmd == "chat_export":
            fmt = "txt" if str(a.get("fmt") or "") == "txt" else "md"
            names = {p["id"]: p.get("name") or "" for p in self.personas.all()}
            return self.chatlog.export(str(a.get("id") or ""), fmt, names)
        raise ValueError(f"неизвестная команда: {cmd}")

    # ---------- «Ещё раз» и «Изменить» ----------
    def _chat_rewind(self, u, ans):
        """Отменить идущий ход и откатить память модели на последний вопрос u (запись ленты) с ответом ans.
        -> полный текст вопроса, как его видела модель (с описанием вложений), или текст из ленты."""
        self.cancel_turn()
        # рецензия 0.86: переспрашиваем «да» — это не новое согласие. Ход, начатый «Ещё раз»/«Изменить», не считается
        # ответом на вопрос модели (_just_agreed), и «Выполнить?» спрашивается заново (ask переносит метку в turn.replay)
        self._chat_replay = time.monotonic()
        h = self.history
        want_a = _norm((ans or {}).get("text"))
        want_q = _norm(u.get("text"))
        q_full = None
        for i in range(len(h) - 1, max(-1, len(h) - 9), -1):
            m = h[i]
            if m.get("role") != "user" or not isinstance(m.get("content"), str):
                continue
            tail = h[i + 1:]
            a_ok = bool(want_a) and any(_norm(t.get("content")) == want_a for t in tail if t.get("role") == "assistant")
            q_ok = bool(want_q) and _norm(m["content"]).startswith(want_q[:200])
            if a_ok or q_ok:
                q_full = m["content"]
                del h[i:]
            break
        else:
            i = None
        if q_full is None:                     # ответа в памяти нет (перебили, не сложился) — убрать «…(меня перебили)»
            while h and h[-1].get("role") == "assistant" and str(h[-1].get("content") or "").endswith("(меня перебили)"):
                h.pop()
        try:
            self.conv.save(self.history)
        except Exception:  # noqa: BLE001
            pass
        q = q_full if q_full is not None else u.get("text") or ""
        if q.endswith(IMG_NOTE):
            q = q[:-len(IMG_NOTE)]
        return q

    def _chat_regen(self, a):
        u, ans = self.chatlog.last_pair()
        if not u:
            raise ValueError("Переспрашивать пока нечего — в беседе нет вопросов")
        if a.get("id") and ans and a["id"] != ans["id"]:
            raise ValueError("«Ещё раз» — только для последнего ответа")
        q = self._chat_rewind(u, ans)
        if not q.strip():
            raise ValueError("У вопроса нет текста — спросите заново")
        self._chat_pending = {"kind": "regen", "item": (ans or {}).get("id"), "q": _norm(q.split("\n\nВложения:")[0]),
                              "at": time.monotonic()}
        log.info("🔁 «Ещё раз» в «Чате»: %s", redact(q[:80]))
        self.ask(q)
        return {"id": (ans or {}).get("id")}

    def _chat_edit(self, a):
        u, ans = self.chatlog.last_pair()
        text = str(a.get("text") or "").strip()
        if not u or a.get("id") != u["id"]:
            raise ValueError("Изменить можно только последний вопрос")
        if not text:
            raise ValueError("Вопрос пустой — напишите, что спросить")
        q = self._chat_rewind(u, ans)
        att = q.split("\n\nВложения:", 1)[1] if "\n\nВложения:" in q else ""
        item, _ = self.chatlog.edit_user(u["id"], text)
        if item:
            self.bridge.broadcast({"type": "chat_cut", "item": item})
        full = text + ("\n\nВложения:" + att if att else "")
        self._chat_pending = {"kind": "edit", "item": None, "q": _norm(text), "at": time.monotonic()}
        log.info("✏ Вопрос в «Чате» исправлен: %s", redact(text[:80]))
        self.ask(full)
        return {"id": u["id"]}

    def _chat_pend(self, type_, text):
        """Реплика для ленты при «Ещё раз»/«Изменить»: -> "skip" (вопрос уже в ленте), id записи (ответ — её новый
        вариант) или None (обычная запись)."""
        p = getattr(self, "_chat_pending", None)
        if not p:
            return None
        if time.monotonic() - p["at"] > PEND_TTL:
            self._chat_pending = None
            return None
        if type_ == "heard":
            if not p.get("heard") and _norm(text) == p["q"]:
                p["heard"] = True
                return "skip"
            self._chat_pending = None           # спросили уже другое — прежняя просьба больше не ждёт ответа
            return None
        self._chat_pending = None
        return p.get("item") if p["kind"] == "regen" else None

    def _chat_keep_partial(self, t):
        """«Стоп» (или новый набранный вопрос) посреди ответа: то, что модель уже написала и что было видно на экране,
        остаётся в ленте с пометкой «остановлено» (как в других чатах), а не пропадает. Ответ уже сложился (gen_done) —
        он и так попадёт в ленту; Telegram, дела по расписанию и служебные ходы — не трогаем."""
        try:
            if t is None or getattr(t, "gen_done", False) or t.via or getattr(t, "raw", False) or t.cancel.is_set():
                return
            text = (t.full or "").strip()
            if text:
                self._chat_add("answer", {"text": text, "meta": {"stopped": 1}})
        except Exception:  # noqa: BLE001
            log.debug("чат: остановленный ответ", exc_info=True)

    # ---------- беседы ----------
    def _chat_threads_emit(self):
        th = self.chatlog.threads()
        self.bridge.broadcast({"type": "chat_threads", "threads": th})
        return {"threads": th}

    def _chat_switch(self, fn, fresh=False):
        """Сменить беседу: память модели текущей — к её ленте (conversation.json уходит вместе с ней), затем память
        открытой. Память пуста (старая беседа без файла памяти) — последние реплики её ленты дословно."""
        self.cancel_turn()
        self._chat_pending = None
        try:
            self.conv.save(self.history)
        except Exception:  # noqa: BLE001
            pass
        fn()
        if fresh:
            self.new_conversation()
        else:
            self.history = self.conv.reload()
            if not self.history:
                turns = int(self.s.get("llm", "history_turns") or 8)
                items = [x for x in self.chatlog.items if (x.get("text") or "").strip()][-2 * turns:]
                while items and items[0]["role"] != "user":
                    items.pop(0)
                self.history = [{"role": x["role"], "content": x["text"], **({"who": x["who"]} if x.get("who") else {})} for x in items]
                if self.history:
                    self.conv.touch(self.history, pairs=0)
            self.emit("conversation", **self.conv.public(self.history))
        self.set_state("idle")
        return self._chat_threads_emit()
