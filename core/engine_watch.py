"""«Дозор» в ядре (core/watch.py — сами дозоры и проверки без модели; здесь — снимок экрана, вопрос модели со зрением,
уведомления и команды студии).

Цикл _watch_loop: раз в 10 с — дозоры, которым пора проверять (по одному, в фоне). Экран: стоп-кран «Ничего не уходит в
интернет» при облачной модели и замок «Экран: нельзя» — дозор за экраном не идёт (сказано почему). Готово — _watch_done:
голос и уведомление на этом компьютере, конверт {ping} своим телефонам (шифр на устройствах), Telegram и MAX, если
подключены. Студии — событие «watch» (то же, что watch_get); виджету — сколько дозоров идёт (значок-глаз)."""
import threading
import time

from engine_base import log


class WatchMixin:
    _watch_busy = False

    def watch_public(self):
        w = getattr(self, "watches", None)
        return w.public() if w else {"items": [], "active": 0}

    def _watch_emit(self):
        self.emit("watch", **self.watch_public())

    def watch_add(self, a):
        """Новый дозор: kind screen|file|page, what, every_minutes, hours, folder, pattern, url. -> запись."""
        kind = str(a.get("kind") or "screen")
        if kind == "screen":
            import security
            if security.locks(self.s.snapshot() if hasattr(self.s, "snapshot") else {})["screen"] == "off":
                raise ValueError("смотреть на экран запрещено в «Безопасности» (замок «Экран»). Разрешите — и я присмотрю.")
        every = a.get("every_minutes")
        it = self.watches.add(kind, a.get("what") or "", every=float(every) * 60 if every else None, hours=a.get("hours"),
                              folder=a.get("folder") or "", pattern=a.get("pattern") or "", url=a.get("url") or "")
        log.info("👁 Дозор: %s (%s, раз в %d с)", it["title"], kind, it["every"])
        self._watch_emit()
        threading.Thread(target=self._watch_check, args=(self.watches.get(it["id"]),), name="watch-first", daemon=True).start()
        return it

    def watch_stop(self, wid=""):
        n = self.watches.stop(wid)
        self._watch_emit()
        return n

    # ---------- проверки ----------

    def _watch_loop(self):
        while not self.stopping.wait(10):
            w = getattr(self, "watches", None)
            if w is None or not w.active() or self._watch_busy:
                continue
            try:
                due, gone = w.due()
                for x in gone:
                    log.info("👁 Дозор закончился по сроку: %s", x.get("title"))
                    self.emit("toast", text=f"Дозор «{x.get('title')}» закончился: срок вышел, условие так и не выполнилось")
                if gone:
                    self._watch_emit()
                for x in due:
                    self._watch_check(x)
            except Exception:  # noqa: BLE001
                log.exception("Дозор")

    def _watch_check(self, x):
        if x is None or x.get("status") != "active" or self._watch_busy:
            return
        self._watch_busy = True
        try:
            if x["kind"] == "file":
                ok, note = self.watches.check_file(x)
            elif x["kind"] == "page":
                ok, note = self._watch_page(x)
            else:
                ok, note = self._watch_screen(x)
            if ok is None:                                     # проверить нельзя совсем (нет модели со зрением и т. п.)
                self.watches.mark(x, note, failed=True, result=note)
                self.emit("toast", text=f"Дозор «{x['title']}» остановлен: {note}")
            elif ok:
                self.watches.mark(x, note, done=True, result=note)
                self._watch_done(x, note)
            else:
                self.watches.mark(x, note)
            self._watch_emit()
        except Exception as e:  # noqa: BLE001
            log.info("👁 Дозор «%s»: проверка не удалась: %s", x.get("title"), e)
            self.watches.mark(x, f"не удалось проверить: {e}")
        finally:
            self._watch_busy = False

    def _watch_page(self, x):
        import egress
        import httpx
        if egress.local_only():
            return False, "на паузе: включён режим «Ничего не уходит в интернет»"
        r = httpx.get(x["url"], timeout=15, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Dewiar", "Accept-Language": "ru,en;q=0.8"})
        if r.status_code >= 400:
            return False, f"страница ответила {r.status_code}"
        return self.watches.check_page(x, r.text[:2_000_000])

    def _watch_screen(self, x):
        from eyes import EyesError, capture_screen, prepare
        from tools import desktop_env
        import watch as W
        try:
            raw = capture_screen(desktop_env())
        except EyesError as e:
            return False, str(e)[:160]
        sig = W.screen_sig(raw)
        if not self.watches.screen_changed(x, sig):
            return False, "экран не изменился"
        prof = self.s.active_llm()
        if not prof:
            return None, "нет мозга: подключите модель в «Мозге»"
        import egress
        import security
        if egress.local_only() and security._where(prof.get("base_url", ""), bool(prof.get("cloud"))) not in ("here", "home"):
            return False, "на паузе: включён режим «Ничего не уходит в интернет», а модель — в интернете"
        b64, _, _ = prepare(raw)
        from llm import LLMError, stream_events, user_message
        q = f"Условие: {x['what']}. Выполнено ли оно на этом снимке экрана?"
        x["asked"] = int(time.time())
        try:
            out = "".join(v for k, v in stream_events(dict(prof, temperature=0.1, max_tokens=300), W.VERDICT_SYSTEM,
                                                      [user_message(prof, q, [b64])], tools=None) if k == "text")
        except LLMError as e:
            msg = str(e)
            if any(w in msg.lower() for w in ("image", "vision", "картин", "multimodal", "не умеет")):
                return None, "у этой модели нет зрения — выберите модель со зрением в «Мозге»"
            return False, f"модель не ответила: {msg[:120]}"
        done, why = W.parse_verdict(out)
        return done, why or ("да" if done else "пока нет")

    # ---------- готово ----------

    def _watch_done(self, x, note):
        text = f"Дозор: {x['title']} — готово. {note[:1].upper() + note[1:] if note else ''}".strip()
        log.info("👁 Дозор сработал: %s — %s", x.get("title"), note)
        try:
            from tools import desktop_notify
            desktop_notify("👁 " + text, critical=True)
        except Exception:  # noqa: BLE001
            pass
        self.emit("watch_done", id=x["id"], title=x["title"], note=note)
        threading.Thread(target=self.announce, args=(f"Готово: {x['title']}. {note}",), name="watch-say", daemon=True).start()
        close = getattr(self, "close", None)                 # свои телефоны — уведомлением (конверт своим устройствам)
        if close is not None:
            threading.Thread(target=close._own_quiet, args=({"ping": {"title": "👁 Дозор: готово", "text": f"{x['title']} — {note}"[:300],
                                                                      "dev": self.device_name()}},), daemon=True).start()
        chat = getattr(self, "chat", None)
        try:
            if chat is not None and chat.notify_on():
                threading.Thread(target=chat.notify, args=("👁 " + text,), daemon=True).start()
        except Exception:  # noqa: BLE001
            pass
