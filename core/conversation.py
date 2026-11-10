"""Длинный разговор: о чём говорили час назад, ассистент не забывает.

Последние реплики (llm.history_turns, по умолчанию 8 пар) уходят модели дословно. Всё, что раньше, сама модель в фоне
сворачивает в краткое содержание разговора — темы, факты и числа, решения и договорённости, что просили и что сделано,
открытые вопросы, на чём остановились. Содержание идёт в системную подсказку, поэтому подсказка не растёт с длиной
разговора, а важное из начала не теряется. Разговор переживает перезапуск программы (STATE_DIR/conversation.json) и
заканчивается после долгой тишины (llm.history_reset_seconds, по умолчанию 8 часов) или словами «начнём новый разговор».
Перерыв дольше 20 минут модель видит («перерыв 45 мин») — новая просьба не путается с прежней темой.
"""
import json
import logging
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.conversation")
SUMMARY_MAX = 3000            # символов: содержание — сжатое, не стенограмма
PAUSE = 20 * 60               # перерыв, о котором стоит сказать модели
MARGIN = 4                    # сворачиваем, когда сверх окна накопилось столько пар реплик

SUMMARIZE = (
    "Ты ведёшь краткое содержание долгого разговора голосового ассистента с пользователем — чтобы ассистент не забыл "
    "важное из начала. Обнови содержание по новым репликам: о чём говорили; факты, имена, числа, даты; решения и "
    "договорённости; что пользователь просил и что сделано; открытые вопросы; на чём остановились. Пиши по-русски, "
    "коротко, пунктами, от третьего лица («Пользователь…», «Ассистент…»). Ничего не выдумывай и не добавляй советов. "
    "Не больше 18 пунктов, самое старое и мелкое — сокращай. Верни только содержание, без вступлений.")

NEW_RX = re.compile(r"^(?:давай(?:те)?\s+)?(?:начн(?:ем|ём|и)|начать)\s+(?:новый\s+разговор|разговор\s+заново|сначала|заново|с\s+чистого\s+листа)$|"
                    r"^(?:забудь|сотри|очисти)\s+(?:наш\s+|этот\s+|весь\s+)?разговор$|^новый\s+разговор$|^новая\s+тема$")


def is_new_conversation(text):
    """«Начнём новый разговор», «забудь разговор», «Лира, новая тема»."""
    t = " ".join(re.sub(r"[^\w\s-]", " ", (text or "").lower().replace("ё", "е")).split())
    t = re.sub(r"\s+пожалуйста$", "", t)
    return bool(NEW_RX.match(t) or NEW_RX.match(re.sub(r"^\S+\s+", "", t)))


class Conversation:
    def __init__(self, path):
        self.path = Path(path)
        self.summary = ""
        self.turns = 0                 # сколько пар реплик было в этом разговоре (вместе со свёрнутыми)
        self.folded = 0                # сколько из них — в содержании
        self.started = 0.0
        self.last = 0.0                # время последней реплики (по часам, переживает перезапуск)
        self._lock = threading.Lock()
        self._busy = False
        self._restored = []
        self._load()

    # ---------- хранение ----------
    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.summary = str(d.get("summary") or "")
        self.turns, self.folded = int(d.get("turns") or 0), int(d.get("folded") or 0)
        self.started, self.last = float(d.get("started") or 0), float(d.get("last") or 0)
        self._restored = [m for m in d.get("history") or [] if isinstance(m, dict) and m.get("role") in ("user", "assistant")
                          and isinstance(m.get("content"), str)]

    def restored(self, max_age):
        """История с прошлого запуска, если разговор ещё не закончился (тишина не дольше max_age секунд); отдаётся
        один раз. Закончился — состояние сбрасывается, файл перезапишет первое сохранение."""
        if not self.last or time.time() - self.last > max_age:
            self.reset(save=False)
            return []
        h, self._restored = self._restored, []
        return h

    def reload(self):
        """Беседа «Чата» сменилась (chatlog.thread_open/thread_new): conversation.json уже другой — прочитать его и
        продолжить ту беседу. -> её история (дословные реплики). Открыли — значит, разговор идёт: «долгую тишину» не
        считаем (иначе старая беседа обнулилась бы на первом же вопросе)."""
        with self._lock:
            self.summary, self.turns, self.folded, self.started, self.last = "", 0, 0, 0.0, 0.0
        self._restored = []
        self._load()
        h, self._restored = self._restored, []
        if self.last:
            self.last = time.time()
        return h

    def save(self, history):
        """conversation.json: содержание, счётчики и до 80 последних текстовых сообщений (role, content, who, model)."""
        d = {"summary": self.summary, "turns": self.turns, "folded": self.folded, "started": self.started, "last": self.last,
             "history": [{k: v for k, v in m.items() if k in ("role", "content", "who", "model")} for m in history
                         if isinstance(m.get("content"), str)][-80:]}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:
            log.info("Разговор не сохранился: %s", e)

    def reset(self, save=True):
        with self._lock:
            self.summary, self.turns, self.folded, self.started, self.last = "", 0, 0, 0.0, 0.0
        if save:
            self.save([])

    # ---------- ход разговора ----------
    def expired(self, max_age):
        return bool(self.last) and time.time() - self.last > max_age

    def touch(self, history, pairs=1):
        """Отметить новые реплики (pairs пар) и сохранить разговор."""
        now = time.time()
        if not self.started:
            self.started = now
        self.last = now
        self.turns += pairs
        self.save(history)

    def prompt(self):
        """Кусок системной подсказки: содержание раньше сказанного. Только то, что меняется редко (при свёртке), — без
        минут и счётчиков: подсказка должна оставаться той же от вопроса к вопросу, иначе свой сервер модели не может
        переиспользовать уже прочитанное и перечитывает её целиком (отзыв 19.10: «на своём сервере долго отвечает»).
        Сколько идёт разговор и был ли перерыв — turn_note(), в справке к самому вопросу."""
        if not self.summary:
            return ""
        return ("\n\nЭто продолжение долгого разговора. Раньше в нём было (кратко):\n" + self.summary.strip()
                + "\nОпирайся на это, если пользователь возвращается к прежнему, — не переспрашивай то, что уже известно. "
                "Последние реплики — ниже, дословно.")

    def turn_note(self):
        """Меняющееся о разговоре — в справку к вопросу: сколько идёт и был ли перерыв перед этим сообщением."""
        out = []
        if self.summary:
            mins = int((time.time() - self.started) / 60) if self.started else 0
            out.append("Разговор идёт " + (f"{mins // 60} ч {mins % 60} мин" if mins >= 60 else f"{mins} мин") + f", {self.turns} реплик.")
        if self.last:
            gap = time.time() - self.last
            if gap > PAUSE:
                g = int(gap / 60)
                out.append((f"Перед этим сообщением в разговоре был перерыв {g // 60} ч {g % 60} мин" if g >= 60 else
                            f"Перед этим сообщением в разговоре был перерыв {g} мин")
                           + ". Если новая просьба не связана с прежней темой — просто выполни её, не возвращаясь к старому.")
        return " ".join(out)

    def window(self, history, turns):
        """Что отдать модели дословно: всё ещё не свёрнутое, но не больше окна с запасом (если свернуть не вышло)."""
        return history[-2 * (turns + 2 * MARGIN):]

    def needs_fold(self, history, turns):
        """Сверх окна накопилось MARGIN пар — пора сворачивать (сворачиваем пачкой, а не после каждой реплики)."""
        return len(history) > 2 * (turns + MARGIN) and not self._busy

    def fold(self, history_ref, turns, ask_model):
        """Свернуть старые реплики в содержание. history_ref() -> текущий список (общий с ядром);
        ask_model(system, messages) -> текст. Вызывать в фоне. -> сколько реплик свернули.
        Свёрнутые реплики удаляются из того же списка (del cur[...]), только если пока шёл запрос модели его начало
        не изменилось; при любой неудаче реплики остаются как были."""
        with self._lock:
            if self._busy:
                return 0
            self._busy = True
        try:
            h = history_ref()
            keep = 2 * turns
            old = h[:-keep] if keep else list(h)
            if len(old) < 2:
                return 0
            lines = []
            for m in old:
                who = "Пользователь" if m.get("role") == "user" else "Ассистент"
                lines.append(f"{who}: {str(m.get('content', ''))[:1500]}")
            msg = (("Содержание разговора до сих пор:\n" + self.summary.strip() + "\n\n") if self.summary else "") + \
                "Новые реплики:\n" + "\n".join(lines)
            text = (ask_model(SUMMARIZE, [{"role": "user", "content": msg[-24000:]}]) or "").strip()
            text = re.sub(r"^\s*(?:Краткое\s+)?содержание[^\n:]*:\s*", "", text, flags=re.I).strip()   # модели любят «Содержание:»
            if len(text) < 20:
                log.info("Разговор: модель не вернула содержание — оставляю реплики как есть")
                return 0
            cur = history_ref()
            if len(cur) < len(old) or any(a is not b for a, b in zip(cur, old)):
                return 0                                   # пока сворачивали, разговор начали заново
            with self._lock:
                self.summary = text[:SUMMARY_MAX]
                self.folded += len(old) // 2
            del cur[:len(old)]
            self.save(cur)
            log.info("🧵 Разговор: %d реплик свёрнуто в содержание (%d символов), дословно — %d", len(old), len(self.summary), len(cur))
            return len(old)
        except Exception as e:  # noqa: BLE001
            log.info("Разговор: свернуть не вышло (%s) — оставляю реплики как есть", e)
            return 0
        finally:
            self._busy = False

    def public(self, history):
        return {"turns": self.turns, "folded": self.folded, "verbatim": len(history) // 2, "summary": self.summary,
                "started": int(self.started), "last": int(self.last)}
