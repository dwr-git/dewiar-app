"""«Дозор» в ядре (core/watch.py — сами дозоры и проверки без модели; здесь — снимок экрана, вопрос модели со зрением,
уведомления и команды студии).

Цикл _watch_loop: раз в 10 с — дозоры, которым пора проверять (по одному, в фоне). Экран: стоп-кран «Ничего не уходит в
интернет» при облачной модели и замок «Экран: нельзя» — дозор за экраном не идёт (сказано почему). Готово — _watch_done:
голос и уведомление на этом компьютере, конверт {ping} своим телефонам (шифр на устройствах), Telegram и MAX, если
подключены. Студии — событие «watch» (то же, что watch_get); виджету — сколько дозоров идёт (значок-глаз)."""
import threading
import time
from pathlib import Path

from engine_base import log, re

# «да», объяснённое окном самой Dewiar (студия, «Дозор», виджет) — модель прочла там текст условия, а не результат
OWN_UI_RX = re.compile(r"дозор|dewiar|студи[ия]|виджет|недавно|правой панели|текст(?:ом)? услови", re.I)


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
        if x.get("wrong"):                               # «Не то — ждать дальше» с телефона: прошлые ошибки — не результат
            q += " Раньше ты ошибочно приняла за результат: " + "; ".join(f"«{w}»" for w in x["wrong"][-3:]) + " — это НЕ оно."
        x["asked"] = int(time.time())
        x["looks"] = int(x.get("looks") or 0) + 1
        try:
            out = "".join(v for k, v in stream_events(dict(prof, temperature=0.1, max_tokens=300), W.VERDICT_SYSTEM,
                                                      [user_message(prof, q, [b64])], tools=None) if k == "text")
        except LLMError as e:
            msg = str(e)
            if any(w in msg.lower() for w in ("image", "vision", "картин", "multimodal", "не умеет")):
                return None, "у этой модели нет зрения — выберите модель со зрением в «Мозге»"
            return False, f"модель не ответила: {msg[:120]}"
        done, why = W.parse_verdict(out)
        # 28.10 (владелец: «хотел, чтобы Лира сказала, когда будет результат, — а она сразу: всё готово»): дозор начали в
        # студии — на экране сама страница «Дозор» с текстом условия, и модель приняла его за результат. Первое «да» сразу
        # после начала не считаем: проверим ещё раз, когда экран сменится (или через ASK_ANYWAY).
        # 28.10, второй раз (у владельца три экрана: Claude, виджет и студия с «Дозором» — она видна всегда): «да», которое
        # модель объясняет панелью самой Dewiar («в блоке „Сейчас в дозоре“…», «в правой панели…»), — не результат
        if done and OWN_UI_RX.search(why or ""):
            log.info("👁 Дозор «%s»: «да» по окну самой Dewiar (%s) — не считаю", x.get("title"), why[:80])
            return False, "вижу только окно Dewiar с текстом дозора — жду настоящего результата"
        if done and x["looks"] == 1:
            x["first_yes"] = why[:160]
            log.info("👁 Дозор «%s»: с первого взгляда «да» (%s) — перепроверю позже", x.get("title"), why[:80])
            return False, "похоже, уже так — проверю ещё раз, чтобы не ошибиться"
        if done:
            self._watch_raw = (x["id"], raw)            # снимок, по которому решили, — телефону вместе с «готово»
        return done, why or ("да" if done else "пока нет")

    # ---------- готово ----------

    def _watch_ping(self, close, x, note, raw=None):
        """«Готово» своим телефонам (28.10, владелец: «на телефоне показать то, что увидел ИИ, — убедиться, что сработка не
        ложная»): к уведомлению — уменьшенный снимок экрана (1600 px, JPEG) файлом «себе» в «Близких»: шифруется на
        устройстве, сайт видит только шифротекст; на телефоне — «Верно» или «Не то — ждать дальше» (own watch_more)."""
        ping = {"title": "👁 Дозор: готово", "text": f"{x['title']} — {note}"[:300], "dev": self.device_name(), "wid": x["id"],
                "what": x.get("what", "")[:200], "note": note[:300]}
        if raw:
            try:
                import io
                import tempfile
                from PIL import Image
                im = Image.open(io.BytesIO(raw)).convert("RGB")
                im.thumbnail((1600, 1600))
                me = ((close.st.get("me") or {}).get("pid")) if hasattr(close, "st") else ""
                if me:
                    with tempfile.TemporaryDirectory() as d:
                        path = Path(d) / "dozor.jpg"
                        im.save(path, "JPEG", quality=72)
                        ping["shot"] = close._upload({"pid": me}, path)
            except Exception as e:  # noqa: BLE001 — снимок не ушёл: «готово» всё равно дойдёт
                log.info("👁 Дозор: снимок телефону не ушёл: %s", e)
        close._own_quiet({"ping": ping})

    def watch_more(self, wid, why=""):
        """С телефона: «Не то — ждать дальше» — дозор снова на посту, а ошибка запоминается (модель её больше не примет)."""
        x = self.watches.get(str(wid or ""))
        if not x or x.get("kind") != "screen":
            return False
        wrong = (list(x.get("wrong") or []) + [str(x.get("note") or why or "")[:120]])[-5:]
        x.update(status="active", wrong=wrong, looks=1, sig=None, note="ошиблась — жду дальше")
        x["until"] = max(int(x.get("until") or 0), int(time.time()) + 3600)
        self.watches._save()
        log.info("👁 Дозор «%s»: с телефона — «не то», жду дальше", x.get("title"))
        self._watch_emit()
        return True

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
            raw = None
            wr = getattr(self, "_watch_raw", None)
            if x.get("kind") == "screen" and wr and wr[0] == x["id"]:
                raw, self._watch_raw = wr[1], None
            threading.Thread(target=self._watch_ping, args=(close, x, note, raw), daemon=True).start()
        chat = getattr(self, "chat", None)
        try:
            if chat is not None and chat.notify_on():
                threading.Thread(target=chat.notify, args=("👁 " + text,), daemon=True).start()
        except Exception:  # noqa: BLE001
            pass
