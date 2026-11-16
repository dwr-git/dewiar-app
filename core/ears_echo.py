"""Слух — «стоп» и своё эхо (часть Engine, чистое ядро 1.0.16): проверка слова-стоп точной моделью, свой голос из
колонок, ложное перебивание — договорить ответ."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка
from ears_base import rest_after


class EchoMixin:
    def _stop_verify(self, w, pcm, now):
        """№564, идея №143 (05.11, Windows, ноутбук без эхоподавления): «голос обрывается посреди фразы, и виджет уходит
        в трей». В журнале — «✋ «перестань» — замолкаю (без эхоподавления)» трижды за три минуты, хотя человек молчал:
        быстрый слух (Vosk с грамматикой из стоп-слов) принимал голос Лиры из колонок за «перестань» / «достаточно», ответ
        обрывался, Лира засыпала, а виджет, показавшийся из трея на имя, через 9 с прятался обратно. Теперь в полудуплексе
        слово-стоп перепроверяет точная модель (свой GigaAM) по последним ~2 с микрофона; пока она
        думает (доли секунды), голос приглушён. -> True — проверка запущена (решит _stop_check); False — проверить нечем
        (audio.stop_check = false или нет точной модели), останавливаемся сразу, как раньше."""
        if self.s.get("audio", "stop_check") is False or not pcm:
            return False
        checker = self._stop_checker()
        if checker is None:
            return False
        if getattr(self, "_stop_checking", False):
            return True                                  # уже проверяем — второе «стоп» той же фразы ждёт её решения
        self._stop_checking = True
        if self.player is not None:
            self.player.gain = 0.35                      # «слышу» — тише, пока проверяем
        self.check_q.put(("stop", pcm, (w, now)))
        return True

    def _stop_checker(self):
        """Чем перепроверить «стоп»: только своим GigaAM (доли секунды, без сети). Распознаёт сервер — решает быстрый
        слух, как раньше: круг по сети на каждое «стоп» — это и задержка, и лишние запросы."""
        g = getattr(self, "gigaam", None)
        return g if g is not None and getattr(g, "ready", False) else None

    def _stop_hit(self, text):
        """Слово-стоп в тексте точной модели -> само слово или None («стоп», «хватит», «перестань(те)»…)."""
        forms = set(STOP_WORDS) | self.STOP_FORMS
        for x in re.findall(r"[\wё]+", _norm(text or "")):
            if x in forms:
                return x
        return None

    def _stop_check(self, pcm, info):
        """Поток name-check: точная модель решает, было ли слово-стоп поверх ответа (_stop_verify). Было и это не моё же
        слово в ответе — замолкаю, как раньше; не было — эхо: голос снова в полную силу, ответ договаривается."""
        w, at = info
        text = None
        try:
            checker = self._stop_checker()
            if checker is not None:
                t0 = time.monotonic()
                text = checker.transcribe(pcm).strip()
                log.debug("👂 проверка «%s»: «%s» (%d мс)", w, text, int((time.monotonic() - t0) * 1000))
        except Exception as e:  # noqa: BLE001 — не проверилось: верим быстрому слуху, как раньше
            log.debug("проверка слова-стоп не удалась: %s", e)
        finally:
            self._stop_checking = False
        hit = w if text is None else self._stop_hit(text)
        if hit and text is not None and self._own_word(hit):
            hit = None
        if self.state != "speaking":
            if self.player is not None:
                self.player.gain = 1.0
            return
        if hit:
            log.info("✋ «%s» — замолкаю (без эхоподавления%s)", w, f"; точная модель: «{text[:60]}»" if text else "")
            self.stop_utt, self.stop_time, self._stop_sleep = True, at, True
            self.interrupt(w, follow=False)
            return
        if self.player is not None:
            self.player.gain = 1.0
        log.info("🔁 «%s» от быстрого слуха — эхо моего голоса (точная модель: «%s»), договариваю", w, (text or "")[:80])

    def _own_word(self, w):
        """Слово-команда («пауза», «стоп») есть в том, что ассистент сам говорит сейчас (или только что) — это эхо."""
        stem = _norm(w or "").strip()
        stem = stem[:max(4, len(stem) - 1)]
        now = time.monotonic()
        said = _norm(" ".join([self._now_saying or ""] + [t for at, t in list(self._said) if now - at < 8]))
        return bool(stem) and stem in said

    def _is_self_echo(self, text, barge=False):
        """Микрофон услышал наш же голос из колонок (эхоподавление не справилось): фраза почти целиком — из того,
        что ассистент сказал за последние 25 секунд. barge — фраза, которой меня только что перебили (№543): тогда
        хватает двух слов («Сергей, вот что.») и окна в 20 с от перебивания — распознавание идёт уже после него."""
        norm = lambda t: (t or "").lower().replace("ё", "е")  # noqa: E731
        words = re.findall(r"\w{3,}", norm(text))
        now = time.monotonic()
        snap = getattr(self, "_barge_snap", None)
        fresh = barge or bool(snap and now - snap["at"] < 20)
        if len(words) < (2 if fresh else 4):
            return False
        if not fresh and self.state != "speaking" and now - self._spoke_until > 3.5:
            return False                                  # эхо бывает, пока говорим, и сразу после
        said = set(re.findall(r"\w{3,}", norm(" ".join(t for at, t in list(self._said) if now - at < 25))))
        if not said:
            return False
        stems = {w[:5] for w in said if len(w) >= 5}
        hit = sum(1 for w in words if w in said or (len(w) >= 5 and w[:5] in stems))
        return hit / len(words) >= 0.75

    def _barge_keep(self, reason):
        """Перебили голосом (речь, имя) во время ответа — запомнить ход: если окажется, что «перебила» я сама себя
        (эхо из колонок), _echo_resume договорит ответ, а не бросит его (№543: «сам себя перебил и перестал работать»)."""
        t = self.turn
        if t is None or reason not in ("речь", "имя") or getattr(t, "via", None):
            return
        self._barge_snap = {"at": time.monotonic(), "turn": t, "persona": self.s.get("persona"),
                            "said": " ".join(t.spoken).strip()}

    def _echo_resume(self):
        """Фраза, которой меня перебили, — моё же эхо: договорить. Ответ уже готов (gen_done) — досказать то, что не
        прозвучало; модель ещё думала (поиск, чтение страниц) — задать тот же вопрос заново. -> взялись ли."""
        snap, self._barge_snap = getattr(self, "_barge_snap", None), None
        now = time.monotonic()
        if not snap or now - snap["at"] > 30 or self.turn is not None:
            return False
        t = snap["turn"]
        q = getattr(t, "q", "") or ""
        mark = (snap["said"] + " …(меня перебили)").strip()
        for i in range(len(self.history) - 1, max(-1, len(self.history) - 4), -1):
            m = self.history[i]
            if m.get("role") == "assistant" and (m.get("content") or "").strip() == mark:
                del self.history[i]                       # «перебили» не было — запись хода будет целой
                break
        full = (t.full or "").strip()
        if getattr(t, "gen_done", False) and full:
            rest = rest_after(full, list(t.spoken))
            log.info("🔁 Это был мой же голос — договариваю ответ (%d симв.)", len(rest))
            threading.Thread(target=self._resume_say, args=(snap, q, full, rest), name="echo-resume", daemon=True).start()
            return True
        if q:
            log.info("🔁 Это был мой же голос — ответ не успел сложиться, спрашиваю заново: «%s»", q[:80])
            if snap["persona"] != self.s.get("persona"):
                self.switch_persona(snap["persona"])
            self.ask(q, images=list(getattr(t, "images", None) or []) or None, quiet=True)
            return True
        return False

    def _resume_say(self, snap, q, full, rest):
        """Договорить ответ после ложного перебивания: остаток — вслух, весь ответ — в историю, как будто не перебивали."""
        with self._turn_lock:
            self.turn_n += 1
            turn = Turn(self.turn_n)
            turn.full = full
            self.turn = turn
        sq = queue.Queue()
        if rest:
            sp = SentenceSplitter()
            for x in sp.feed(rest + " ") + sp.flush():
                sq.put(x)
        sq.put(None)
        self.set_state("speaking" if rest else "idle")
        try:
            self._speak_worker(turn, sq)
        finally:
            with self._turn_lock:
                mine = self.turn is turn
                if mine:
                    self.turn = None
            if not turn.cancel.is_set() and q:
                self.history += [{"role": "user", "content": q},
                                 {"role": "assistant", "content": full, "who": snap["persona"]}]
            if mine:
                self.set_state("idle")

    def _echo_heard(self, text):
        """Фраза оказалась нашим эхом: пропускаем. Второй раз за 3 минуты — на 10 минут отключаем «продолжение
        разговора» без имени (_echo_until, см. конец хода в engine_answer.py) и подсказываем про наушники."""
        now = time.monotonic()
        log.info("🔁 Услышал свой же голос — пропускаю: «%s»", text[:120])
        self._echo_hits = [t for t in self._echo_hits if now - t < 180] + [now]
        self.follow_up_until = 0.0
        # №543: эхо прорвалось — 10 минут перебить ответ можно только именем или «стоп», не просто речью
        first = now >= self._barge_name_until
        self._barge_name_until = now + 600
        hp = bool(self.status.get("headphones"))
        if first and hp:
            self.note("Похоже, звук идёт в колонки, хотя включено «Я в наушниках»: я слышу свой голос. Пока говорю, "
                      "перебить меня можно именем или словом «стоп». Без наушников выключите «Я в наушниках» "
                      "(студия → «Звук и поведение»).")
        if len(self._echo_hits) >= 2 and now > self._echo_until:
            self._echo_until = now + 600                  # 10 минут слушаем только по имени
            if not hp:
                self.note("Я слышу сам себя: звук из колонок попадает в микрофон. Наденьте наушники или включите "
                          "эхоподавление (студия → «Звук и поведение»). Пока отвечаю только когда зовут по имени.")
        if self._echo_resume():
            return
        self.set_state("idle")
