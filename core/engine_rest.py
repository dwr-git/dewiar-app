"""«Отдых» (жалоба №540, 04.11: «иногда хочется поработать без неё — предусмотрите полное отключение на время»).

Одна кнопка или фраза «Лира, отдохни час»: на это время ассистент не слушает (микрофон выключен, имя не ловит) и ничего не
говорит сам — напоминания, итоги задач, сообщения «Близких» копятся. Конец — по времени, кнопкой «Вернуть» (виджет, трей),
нажатием на лицо или вопросом, написанным в виджете: тогда — «Я снова с вами» и всё, что накопилось, по одному разу.

Состояние — в STATE_DIR/rest.json: перезапуск программы отдых не прерывает. Ядро: rest_start / rest_end / rest_public,
команды rest, rest_end, rest_state; событие «rest» — виджету и трею. Ловушки: announce (engine_remote.py) и _on_reminder
(engine_tools.py) при отдыхе кладут сказанное в _rest_held и выходят."""
import json
import threading
import time

from engine_base import STATE_DIR, log, re

REST_MIN, REST_MAX, REST_DEFAULT = 5, 12 * 60, 60

_NUM = {"один": 1, "одну": 1, "одна": 1, "два": 2, "две": 2, "пару": 2, "пара": 2, "три": 3, "четыре": 4, "пять": 5,
        "шесть": 6, "семь": 7, "восемь": 8, "десять": 10, "пятнадцать": 15, "двадцать": 20, "тридцать": 30, "сорок": 40,
        "пятьдесят": 50}
_N = r"(\d{1,3}|" + "|".join(_NUM) + r")"
# сам глагол: с ним время можно не называть («отдохни» — час) — или только со временем («помолчи час»: просто «помолчи» —
# это «замолчи до имени», is_sleep_phrase; «отключись» без времени — выход из программы, WINDOW_RX)
_SOFT = r"(?:отдохни|отдыхай|передохни|(?:сделай|возьми)\s+перерыв|не\s+мешай(?:\s+мне)?|дай\s+(?:мне\s+)?(?:спокойно\s+)?поработать|" \
        r"оставь\s+меня(?:\s+в\s+покое)?)"
_TIMED = r"(?:помолчи|замолчи|не\s+слушай(?:\s+меня)?|отключись|выключись|не\s+беспокой(?:\s+меня)?|уйди\s+в\s+отпуск)"
REST_RX = re.compile(r"^(?:[a-zа-я]{2,15}\s+(?=(?:ну|а|давай|пожалуйста|можешь|пока|теперь)\s|" + _SOFT[3:-1] + "|" + _TIMED[3:-1] + r"))?"
                     r"(?:(?:ну|а|давай|пожалуйста|можешь|пока|теперь)\s+)*(?:(?P<soft>" + _SOFT + r")|(?P<timed>" + _TIMED + r"))"
                     r"(?P<rest>(?:\s+\S+){0,5})$")


def _dur(words):
    """«на час», «полчаса», «полтора часа», «2 часа», «минут 20», «на время», «немного» -> минуты; «» -> None; не время -> -1."""
    t = re.sub(r"\b(?:пожалуйста|меня|мне|ещ[её]|хотя\s+бы|где-?то|примерно|около|так|ну)\b", " ", words)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^(?:на|в\s+течение)\s+", "", t)
    if not t:
        return None
    if re.fullmatch(r"(?:один\s+|1\s+)?час(?:ок|ик)?|время|какое-?то\s+время|часик", t):
        return 60
    if re.fullmatch(r"полчаса|пол\s+часа", t):
        return 30
    if re.fullmatch(r"полтора\s+часа", t):
        return 90
    if re.fullmatch(r"немного|немножко|чуть-?чуть|минутку|минуточку", t):
        return 15
    m = re.fullmatch(_N + r"\s+(час|часа|часов|минут|минуту|минуты)", t) or re.fullmatch(r"(минут|часа|часов)\s+" + _N, t)
    if m:
        a, b = m.group(1), m.group(2)
        num, unit = (a, b) if a[0].isdigit() or a in _NUM else (b, a)
        n = int(num) if num.isdigit() else _NUM.get(num, 0)
        return n * 60 if unit.startswith("час") else n
    return -1


def rest_phrase(text):
    """«Лира, отдохни час», «не мешай полчаса», «дай поработать», «помолчи 20 минут» -> минуты отдыха; иначе None."""
    t = re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", (text or "").lower().replace("ё", "е"))).strip()
    m = REST_RX.match(t)
    if not m:
        return None
    d = _dur(m.group("rest") or "")
    if d == -1 or (d is None and m.group("timed")):
        return None
    return max(REST_MIN, min(REST_MAX, d or REST_DEFAULT))


def human_minutes(n):
    n = int(n)
    if n % 60 == 0 and n >= 60:
        h = n // 60
        return "час" if h == 1 else f"{h} " + ("часа" if 2 <= h % 10 <= 4 and not 12 <= h % 100 <= 14 else "часов")
    if n == 30:
        return "полчаса"
    if n == 90:
        return "полтора часа"
    return f"{n} " + ("минуту" if n % 10 == 1 and n % 100 != 11 else "минуты" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "минут")


class RestMixin:
    _rest_until = 0.0
    _rest_was_muted = False
    _rest_lock = None

    def _rest_path(self):
        return STATE_DIR / "rest.json"

    def resting(self):
        return self._rest_until > time.time()

    def rest_public(self):
        on = self.resting()
        return {"on": on, "until": int(self._rest_until) if on else 0,
                "until_text": time.strftime("%H:%M", time.localtime(self._rest_until)) if on else "",
                "held": len(getattr(self, "_rest_held", None) or [])}

    def _rest_emit(self):
        self.emit("rest", **self.rest_public())

    def _rest_save(self):
        try:
            p = self._rest_path()
            if self._rest_until:
                p.write_text(json.dumps({"until": self._rest_until, "was_muted": self._rest_was_muted,
                                         "held": getattr(self, "_rest_held", None) or []}, ensure_ascii=False), encoding="utf-8")
            else:
                p.unlink(missing_ok=True)
        except (OSError, TypeError, ValueError) as e:
            log.info("Отдых: не записал состояние (%s)", e)

    def rest_boot(self):
        """При запуске ядра: отдых ещё идёт — продолжаем (микрофон выключен), кончился, пока программа была закрыта, —
        то, что успело накопиться, скажем как обычно."""
        try:
            d = json.loads(self._rest_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self._rest_held = list(d.get("held") or [])
        self._rest_was_muted = bool(d.get("was_muted"))
        if float(d.get("until") or 0) > time.time() + 5:
            self._rest_until = float(d["until"])
            self.set_mute(True)
            log.info("☕ Отдых продолжается — до %s", self.rest_public()["until_text"])
            self._rest_timer()
        else:
            self._rest_until = 1.0                       # был — rest_end вернёт микрофон и отдаст накопленное
            threading.Timer(15.0, self.rest_end, args=("время",)).start()

    def rest_start(self, minutes=REST_DEFAULT, why="кнопка"):
        """Отдохнуть minutes минут (5…720). Уже отдыхает — новое время конца. -> rest_public()"""
        minutes = max(REST_MIN, min(REST_MAX, int(minutes or REST_DEFAULT)))
        if not self.resting():
            self._rest_was_muted = bool(self.muted)
            self._rest_held = list(getattr(self, "_rest_held", None) or [])
        self._rest_until = time.time() + minutes * 60
        if self.state in ("speaking", "thinking", "listening"):
            try:
                self.interrupt("отдых", follow=False)
            except Exception:  # noqa: BLE001
                log.debug("отдых: перебить", exc_info=True)
        self.follow_up_until = 0.0
        self.set_mute(True)
        self._rest_save()
        log.info("☕ Отдых %s (%s) — до %s: не слушаю и не говорю, напоминания подождут", human_minutes(minutes), why,
                 self.rest_public()["until_text"])
        self._rest_emit()
        self._rest_timer()
        return self.rest_public()

    def _rest_timer(self):
        n = getattr(self, "_rest_gen", 0) + 1
        self._rest_gen = n

        def wait():
            while not self.stopping.is_set() and self._rest_gen == n and self._rest_until:
                left = self._rest_until - time.time()
                if left <= 0:
                    self.rest_end("время")
                    return
                self.stopping.wait(min(left, 30))
        threading.Thread(target=wait, name="rest", daemon=True).start()

    def rest_end(self, why="кнопка"):
        """Вернуться: микрофон — как был до отдыха, «Я снова с вами» и накопленное (напоминания звенят — опоздавшими,
        одним звонком; фразы — одной сводкой). -> rest_public()"""
        if not self._rest_until:
            return self.rest_public()
        self._rest_until = 0.0
        self._rest_gen = getattr(self, "_rest_gen", 0) + 1
        held, self._rest_held = list(getattr(self, "_rest_held", None) or []), []
        self._rest_save()
        self.set_mute(self._rest_was_muted)
        log.info("☕ Отдых закончился (%s); накопилось: %d", why, len(held))
        self._rest_emit()
        rems = [h["item"] for h in held if h.get("kind") == "reminder" and isinstance(h.get("item"), dict)]
        says = [h["text"] for h in held if h.get("kind") == "say" and h.get("text")]
        jobs = [r for r in rems if r.get("kind") == "job"]
        rems = [r for r in rems if r.get("kind") != "job"]
        parts = [] if why in ("вопрос", "лицо") else ["Я снова с вами."]
        if rems:
            names = [str(r.get("text") or "").strip() for r in rems][:3]
            parts.append(("За время отдыха было напоминание: " if len(rems) == 1 else f"За время отдыха было напоминаний: {len(rems)} — ")
                         + "; ".join(f"«{x}»" for x in names if x) + ("…" if len(rems) > 3 else "") + ".")
        if says:
            parts.append(("Ещё: " if rems else "За время отдыха: ") + " ".join(s.rstrip(".") + "." for s in says[:3])
                         + (f" И ещё {len(says) - 3}." if len(says) > 3 else ""))
        if parts:
            self.announce(" ".join(parts))
        if rems:                                          # последнее — окном с «Готово/Отложить», одним звонком
            last = dict(rems[-1], late=True)
            threading.Timer(1.0, self._on_reminder, args=(last,)).start()
        for j in jobs:                                    # дела по расписанию («Итог дня») — выполнить сейчас
            threading.Thread(target=self._on_reminder, args=(j,), daemon=True).start()
        return self.rest_public()

    def _rest_hold(self, kind, **kw):
        """Отдыхаем — придержать: kind "reminder" (item) или "say" (text). -> True, если придержали."""
        if not self.resting():
            return False
        held = getattr(self, "_rest_held", None)
        if held is None:
            held = self._rest_held = []
        held.append(dict(kind=kind, **kw))
        del held[:-30]
        log.info("☕ Отдых — придержала %s: %s", "напоминание" if kind == "reminder" else "фразу",
                 str((kw.get("item") or {}).get("text") if kind == "reminder" else kw.get("text"))[:80])
        self._rest_save()
        self._rest_emit()
        return True

    def _rest_voice(self, text, via=None):
        """«Лира, отдохни час» -> True (сказала и отдыхает)."""
        mins = rest_phrase(text)
        if not mins:
            return False
        r = self.rest_start(mins, why="голосом")
        self._say_quick(f"Хорошо, отдыхаю {human_minutes(mins)} — до {r['until_text']}. Не слушаю и не говорю, напоминания "
                        "подождут. Вернуть раньше — кнопкой в виджете или в значке у часов.", text, via)
        return True

    def rest_cmd(self, cmd, a):
        if cmd == "rest":
            return self.rest_start(int(a.get("minutes") or REST_DEFAULT), why="кнопка")
        if cmd == "rest_end":
            return self.rest_end("кнопка")
        if cmd == "rest_toggle":
            return self.rest_end("кнопка") if self.resting() else self.rest_start(int(a.get("minutes") or REST_DEFAULT), why="кнопка")
        return self.rest_public()
