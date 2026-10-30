"""Суфлёр: беззвучные подсказки на встрече (окно ui/prompter.html, открывает ui/app.py → open_prompter).

Как работает:
  • Онлайн-встреча — два источника речи. Собеседник — звук компьютера (audio_io.LoopbackCapture → свой VAD → фразы),
    вы — обычный микрофон ядра: пока суфлёр включён, Engine._on_utterance отдаёт фразы сюда (feed_me), ассистент
    молчит и на имя не откликается (_meeting_ignores). Если голос владельца запомнен — фразы микрофона с чужим голосом
    (собеседник из колонок просочился в микрофон) отбрасываем: их уже слышно по звуку компьютера.
  • Очная встреча — один микрофон на всех: кто говорит, решает голос (speaker.py: вектор голоса фразы против
    отпечатка владельца; голоса собеседников копятся по ходу встречи). Отпечаток — один раз, «Запомнить мой голос»:
    четыре фразы вслух (enroll_*), звук не хранится.
  • Каждая фраза → распознавание тем же движком, что у ассистента (current_stt) → строка расшифровки в окно.
  • Подсказка — когда собеседник спросил или возразил (wants_hint), когда вы сами тянете время («хороший вопрос»,
    «сейчас уточню», «э-э, ну, как бы»), или по кнопке «Подсказать» в окне. Новая подсказка отменяет недописанную.
  • «Замешкались» (поток prompter-watch): собеседник спросил, а вы молчите дольше STUCK_S — подсказка к вопросу
    выделяется («Начните так»), а если её не было — пишется. Молчат оба дольше PAUSE_S — тихая подсказка «что сказать
    дальше» к цели встречи (не чаще раза в полторы минуты). Только в режиме «на вопросы и возражения».
  • Ответ модели (активный «Мозг», потоком, без действий) — короткой карточкой: первая строка — главное, 2–4 пункта,
    «Источник: файл». Материалы встречи (файлы, которые положили в окно) режутся на отрывки и ищутся по словам
    (BM25 из knowledge.py); по желанию — ещё и в «Знаниях». Пока модель пишет, мгновенно показываем ответ из
    шпаргалки, если вопрос на неё похож.
  • Шпаргалка (вероятные вопросы и ответы) готовится в фоне сразу после старта, если есть цель или материалы.
  • Стоп → итог встречи (договорились, кто что делает, открытые вопросы) — в окно и файлом в «Встречи/».
Звук не сохраняется никогда; расшифровка — только в итоге и только если отмечено «сохранить расшифровку».
Событие окну одно — «prompter» {kind: state | line | hint | sheet | summary | open | note, …}."""
import math
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from engine_base import DATA_DIR, FRAME_S, STATE_DIR, log

# вопрос или возражение собеседника — повод подсказать
Q_RX = re.compile(r"\?\s*$|^(?:ну\s+|а\s+|и\s+|так\s+)?(?:как|что|сколько|почему|зачем|когда|где|куда|откуда|какой|какая|какое|какие|каким|"
                  r"какую|кто|чей|чем|можно ли|можете|могли бы|расскажите|объясните|поясните|уточните|а если|правда ли|"
                  r"есть ли|будет ли|насколько|в чём|в чем)\b", re.I)
OBJ_RX = re.compile(r"\b(?:дорого\w*|не уверен\w*|сомнева\w*|у других|у конкурент\w*|конкурент\w*|подума(?:ем|ть|ю)|"
                    r"не (?:нужно|интересно|подходит|готовы|потянем)|скидк\w*|гаранти\w*|риск\w*|сроки|бюджет\w*|слишком)\b", re.I)
# вы сами тянете время — тоже повод
STALL_RX = re.compile(r"\b(?:хороший вопрос|дайте подумать|сейчас уточню|надо уточнить|секундочку|минуточку|"
                      r"как бы (?:это|вам) сказать|не готов сразу|сложно сказать|затрудняюсь)\b", re.I)
# слова-паразиты: много их в одной фразе — человек подбирает слова
FILLERS = {"э", "ээ", "эээ", "эм", "эмм", "мм", "ммм", "м", "ну", "короче", "типа", "вот", "значит", "получается",
           "собственно", "какбы", "вобщем", "таксказать"}
HINT_WAIT_S = 35.0              # первое слово подсказки не пришло за столько секунд — честно «модель не отвечает»
STUCK_S = 5.0                   # собеседник спросил, вы молчите — столько секунд, и подсказка выделяется
PAUSE_S = 10.0                  # молчат оба — столько секунд, и тихая подсказка «что сказать дальше»
PAUSE_AFTER = 60.0              # …но не в первую минуту встречи (знакомятся, настраивают звук)
ENROLL_PHRASES = ["Добрый день! Сегодня у меня рабочее настроение.", "Давайте обсудим условия, сроки и стоимость проекта.",
                  "Я предлагаю начать с короткого пилота на месяц.", "Если появятся вопросы, пишите мне в любое время."]

HINT_SYSTEM = (
    "Ты — незаметный суфлёр на деловой встрече. Человек сейчас разговаривает с собеседником и одним взглядом читает "
    "твою подсказку на экране. Подскажи ЕМУ, что ответить или на что опереться.\n"
    "Формат строго:\n"
    "1-я строка — главное, что сказать: до 14 слов, без вступлений, без «Вы можете сказать».\n"
    "Затем 2–4 строки, каждая начинается с «• », по 3–12 слов: цифры, факты, аргументы, встречный вопрос.\n"
    "Последняя строка — «Источник: <имя файла>», если опирался на МАТЕРИАЛЫ.\n"
    "Цифры, цены, сроки и условия — только из МАТЕРИАЛОВ. Нет ответа в материалах — опирайся на общие знания и начни "
    "первую строку с «≈ ». Не выдумывай имён и цен. Если подсказывать нечего (реплика — не вопрос и не возражение) — "
    "ответь одним символом «—». Пиши по-русски.")
SHEET_SYSTEM = (
    "Подготовь шпаргалку к деловой встрече: 6–10 вопросов или возражений, которые вероятнее всего прозвучат от "
    "собеседника, и короткий ответ на каждый — по материалам и цели. Строго парами строк:\n"
    "В: вопрос собеседника\nО: что ответить, до 25 слов\nЦифры — только из материалов. Без вступлений и заключений.")
SUMMARY_SYSTEM = (
    "Ты пишешь итог деловой встречи по расшифровке (реплики «Собеседник» и «Вы»). Markdown, без вступлений:\n"
    "## Коротко — 2–3 предложения.\n## Договорились — пункты.\n## Кто что делает — пункты (сроки, если звучали).\n"
    "## Открытые вопросы — пункты.\nТолько то, что было сказано. Раздела нет по сути — напиши «нет».")

MAX_FILE = 30 * 1024 * 1024
TEXT_EXTS = {".md", ".txt", ".html", ".htm", ".pdf", ".docx", ".odt", ".csv"}


def wants_hint(text, who="them"):
    """Повод подсказать: вопрос или возражение собеседника; у вас — «хороший вопрос», «сейчас уточню»."""
    t = (text or "").strip()
    if len(t.split()) < (2 if who == "me" else 3):
        return False
    if who == "me":
        return bool(STALL_RX.search(t)) or stalling(t)
    return bool(Q_RX.search(t) or OBJ_RX.search(t))


def stalling(text):
    """Фраза из слов-паразитов: «ну, э-э, как бы, вот…» — не меньше трёх и не меньше половины слов."""
    t = re.sub(r"\b(как) (бы)\b|\b(в) (общем)\b|\b(так) (сказать)\b", lambda m: "".join(g for g in m.groups() if g), (text or "").lower())
    ws = re.findall(r"[а-яё]+", t)
    n = sum(1 for w in ws if w in FILLERS)
    return n >= 3 and n / max(1, len(ws)) >= 0.5


def parse_sheet(text):
    """«В: …» / «О: …» -> [{q, a}]."""
    out, q = [], None
    for ln in (text or "").splitlines():
        ln = ln.strip().lstrip("-•* ").strip()
        m = re.match(r"^(?:В|Вопрос)\s*[:.)]\s*(.+)$", ln)
        if m:
            q = m.group(1).strip()
            continue
        m = re.match(r"^(?:О|Ответ)\s*[:.)]\s*(.+)$", ln)
        if m and q:
            out.append({"q": q, "a": m.group(1).strip()})
            q = None
    return out[:14]


class Prompter:
    def __init__(self, eng):
        self.eng = eng
        self.on = False
        self.paused = False
        self.meeting = {}
        self.files = []          # [{name, chars, chunks}]
        self.lines = []          # [{who, text, t}]
        self.hints = []          # [{id, q, text, done, instant, src, ts, why}]
        self.sheet = []
        self.summary = ""
        self.status = ""         # что слушаем / почему не слышим собеседника
        self._lock = threading.RLock()
        self._q = None
        self._stop = threading.Event()
        self._hint_cancel = None
        self._n = 0
        self.enrolling = None    # запись голоса: [pcm, …] или None
        self._speaker = None
        self._diar = None
        self._await = None       # вопрос собеседника, на который ждём ответа: {t, q, hint}
        self._them_voice_t = 0.0
        self._pause_hint_t = 0.0
        self._t0 = 0.0
        self._stt_err = ""       # распознавание не ответило — почему (показываем в окне)
        self._stt_busy = 0       # фраз в распознавании сейчас

    @property
    def speaker(self):
        if self._speaker is None:
            from speaker import Speaker
            self._speaker = Speaker()
        return self._speaker

    def voice_info(self):
        sp = self.speaker
        return {"has": sp.owner is not None, "n": sp.owner_n, "model": sp.ready(), "enrolling": self.enrolling is not None}

    # ---------- состояние для окна ----------

    def public(self):
        with self._lock:
            return {"on": self.on, "paused": self.paused, "meeting": dict(self.meeting), "status": self.status,
                    "files": [{"name": f["name"], "chars": f["chars"]} for f in self.files], "lines": self.lines[-30:],
                    "hints": [h for h in self.hints if not h.get("dropped")][-20:], "sheet": self.sheet, "summary": self.summary,
                    "brain": bool(self.eng.s.active_llm()), "loopback": True, "voice": self.voice_info(), "hear": self.hearing()}

    def hearing(self):
        """30.10 (владелец: «запись идёт, ничего не пишет и не отвечает — непонятно»): что суфлёр слышит прямо сейчас —
        для двух огоньков окна. them/me: «talk» — звучит речь, «quiet» — тишина, «off» — не слушаем; stt — фраз в
        распознавании; err — распознавание не ответило."""
        now = time.monotonic()
        m = self.meeting or {}
        mic = getattr(self.eng, "mic_voice_t", 0.0) or 0.0
        them = ("off" if not m.get("them") or self.status.startswith("звук компьютера не слышу") else
                "talk" if now - self._them_voice_t < 1.5 else "quiet")
        me = "off" if not m.get("me") else "talk" if now - mic < 1.5 else "quiet"
        return {"them": them, "me": me, "stt": self._stt_busy, "err": self._stt_err, "lines": len(self.lines)}

    def _emit(self, kind, **kw):
        self.eng.emit("prompter", kind=kind, **kw)

    def _state(self):
        self._emit("state", state=self.public())

    # ---------- материалы ----------

    @property
    def _dir(self):
        d = STATE_DIR / "prompter"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def add_file(self, name="", data=None, path=""):
        """Файл встречи (из окна — данные, из диалога — путь): текст и отрывки для поиска. -> {name, chars}."""
        from knowledge import chunks, extract
        src = Path(path) if path else None
        name = Path(str(name or (src.name if src else ""))).name.strip()
        if not name or Path(name).suffix.lower() not in TEXT_EXTS:
            raise ValueError("подходят PDF, Word, ODT, текст, Markdown, HTML и CSV")
        dst = self._dir / name
        if src is not None:
            if not src.is_file():
                raise ValueError("файл не найден")
            if src.stat().st_size > MAX_FILE:
                raise ValueError("файл больше 30 МБ")
            shutil.copyfile(src, dst)
        else:
            if data is None or len(data) > MAX_FILE:
                raise ValueError("файл пустой или больше 30 МБ")
            dst.write_bytes(data)
        try:
            text = extract(dst)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"не прочитался: {e}") from e
        if not text.strip():
            raise ValueError("в файле нет текста (скан без распознавания?)")
        with self._lock:
            self.files = [f for f in self.files if f["name"] != name] + [{"name": name, "chars": len(text), "chunks": chunks(text)}]
        log.info("🎬 Суфлёр: материал «%s» — %d знаков", name, len(text))
        self._state()
        return {"name": name, "chars": len(text)}

    def remove_file(self, name):
        with self._lock:
            self.files = [f for f in self.files if f["name"] != name]
        try:
            (self._dir / Path(name).name).unlink(missing_ok=True)
        except OSError:
            pass
        self._state()
        return True

    def _materials(self, query, limit=4, budget=3600):
        """Отрывки материалов к вопросу: все, если их мало; иначе лучшие по словам (BM25, как в «Знаниях»)."""
        from knowledge import words
        with self._lock:
            docs = [(f["name"], c) for f in self.files for c in f["chunks"]]
        if not docs:
            return []
        if sum(len(c) for _, c in docs) <= budget:
            return docs
        q = [w for w in words(query) if len(w) > 2]
        if not q:
            return docs[:limit]
        toks = [words(n + " " + c) for n, c in docs]
        n, avg = len(docs), sum(len(t) for t in toks) / len(docs) or 1
        df = {w: sum(1 for t in toks if w in t) for w in set(q)}
        scored = []
        for (name, c), t in zip(docs, toks):
            s = 0.0
            for w in set(q):
                f = t.count(w)
                if f:
                    s += math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5)) * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(t) / avg))
            if s > 0:
                scored.append((s, name, c))
        scored.sort(key=lambda x: -x[0])
        out, size = [], 0
        for _, name, c in scored[:limit]:
            if size + len(c) > budget and out:
                break
            out.append((name, c))
            size += len(c)
        return out or docs[:2]

    # ---------- включить / выключить ----------

    def start(self, title="", goal="", mode="auto", them=True, me=True, knowledge=False, keep_text=False, place="online", nudge=True):
        """Начать встречу. place: online — собеседник по звуку компьютера, вы — микрофон; live — очная встреча,
        один микрофон, кто говорит — по голосу (нужен запомненный голос владельца)."""
        live = place == "live"
        if live and self.speaker.owner is None:
            raise ValueError("для очной встречи сначала запомните свой голос — «Запомнить мой голос»")
        if self.enrolling is not None:
            self.enroll_stop(save=False)
        if self.on:
            self.stop(summary=False)
        with self._lock:
            self.meeting = {"title": (title or "").strip()[:120] or "Встреча", "goal": (goal or "").strip()[:2000],
                            "mode": "manual" if mode == "manual" else "auto", "them": bool(them) and not live, "me": bool(me) or live,
                            "place": "live" if live else "online", "nudge": bool(nudge),
                            "knowledge": bool(knowledge), "keep_text": bool(keep_text), "started": time.time()}
            self.lines, self.hints, self.sheet, self.summary, self.paused = [], [], [], "", False
            self.on = True
        self._stop = threading.Event()
        self._await, self._pause_hint_t, self._them_voice_t, self._t0 = None, 0.0, 0.0, time.monotonic()
        self._diar = self.speaker.diarizer() if self.speaker.owner is not None else None
        import queue
        self._q = queue.Queue(maxsize=40)
        threading.Thread(target=self._stt_loop, name="prompter-stt", daemon=True).start()
        threading.Thread(target=self._watch, name="prompter-watch", daemon=True).start()
        if live:
            self.status = "слушаю микрофон — вас и собеседника различаю по голосу"
        elif self.meeting["them"]:
            threading.Thread(target=self._them_loop, name="prompter-them", daemon=True).start()
        else:
            self.status = "собеседника не слушаю — подсказки по кнопке и на ваши фразы"
        if self.meeting["goal"] or self.files:
            threading.Thread(target=self._prepare_sheet, name="prompter-sheet", daemon=True).start()
        log.info("🎬 Суфлёр включён: «%s» (%s, %s; собеседник: %s, я: %s)", self.meeting["title"], "вживую" if live else "онлайн",
                 "подсказки на вопросы" if self.meeting["mode"] == "auto" else "по кнопке",
                 "по голосу" if live else ("да" if self.meeting["them"] else "нет"), "да" if self.meeting["me"] else "нет")
        self.eng.set_state("idle")
        self._state()
        return self.public()

    def pause(self, on=True):
        self.paused = bool(on)
        self._state()
        return self.public()

    def stop(self, summary=True):
        """Закончить встречу; summary — подвести итог (в фоне, событие summary)."""
        if not self.on:
            return self.public()
        self.on = False
        self._stop.set()
        if self._hint_cancel:
            self._hint_cancel.set()
        log.info("🎬 Суфлёр выключен: реплик %d, подсказок %d", len(self.lines), len(self.hints))
        if summary and self.lines:
            threading.Thread(target=self._summarize, name="prompter-summary", daemon=True).start()
        self._state()
        return self.public()

    def feed_me(self, pcm):
        """Фраза с микрофона (Engine._on_utterance) — пока суфлёр включён или записывается голос."""
        if self.enrolling is not None:
            self._enroll_feed(pcm)
            return
        if self.on and not self.paused and self.meeting.get("me") and self._q is not None:
            try:
                self._q.put_nowait(("mic", pcm))
            except Exception:  # noqa: BLE001 — очередь полна: распознавание не успевает, старое важнее не терять
                pass

    # ---------- голос владельца ----------

    def enroll_start(self):
        """Запомнить голос: окно показывает фразы, человек читает их вслух; модель качается, если её нет."""
        if self.on:
            raise ValueError("сначала закончите встречу")
        self.enrolling = []
        self._emit("voice", step="model" if not self.speaker.ready() else "listen", n=0, need=len(ENROLL_PHRASES),
                   phrases=ENROLL_PHRASES)
        threading.Thread(target=self._enroll_model, name="prompter-voice", daemon=True).start()
        return {"phrases": ENROLL_PHRASES}

    def _enroll_model(self):
        sp = self.speaker
        if sp.ready():
            return
        try:
            m = self.eng._mirror("speaker") if hasattr(self.eng, "_mirror") else None
            sp.mirror = m
            last = [0.0]

            def prog(frac):
                if time.monotonic() - last[0] > 0.3:
                    last[0] = time.monotonic()
                    self._emit("voice", step="model", pct=round(100 * frac))
            sp.ensure(prog)
            sp._session()
        except Exception as e:  # noqa: BLE001
            self.enrolling = None
            log.warning("🎬 Модель голоса: %s", e)
            self._emit("voice", step="error", error=str(e)[:200])
            return
        if self.enrolling is not None:
            self._emit("voice", step="listen", n=len(self.enrolling), need=len(ENROLL_PHRASES), phrases=ENROLL_PHRASES)

    def _enroll_feed(self, pcm):
        if len(pcm) / 2 / 16000 < 1.0 or self.enrolling is None:
            return                                         # «ага», кашель — не образец
        self.enrolling.append(pcm)
        n = len(self.enrolling)
        log.info("🎬 Голос: образец %d из %d", n, len(ENROLL_PHRASES))
        if n >= len(ENROLL_PHRASES):
            threading.Thread(target=self.enroll_stop, name="prompter-voice", daemon=True).start()
        else:
            self._emit("voice", step="listen", n=n, need=len(ENROLL_PHRASES), phrases=ENROLL_PHRASES)

    def enroll_stop(self, save=True):
        """Закончить запись: save — запомнить по тому, что успели сказать (нужно хотя бы две фразы)."""
        pcms, self.enrolling = self.enrolling or [], None
        if not save:
            self._emit("voice", step="cancel")
            return self.voice_info()
        self._emit("voice", step="saving")
        try:
            r = self.speaker.enroll(pcms)
        except Exception as e:  # noqa: BLE001
            self._emit("voice", step="error", error=str(e)[:200])
            return self.voice_info()
        self._emit("voice", step="done", **r)
        self._state()
        return self.voice_info()

    def enroll_forget(self):
        self.speaker.forget()
        self._state()
        return self.voice_info()

    # ---------- звук собеседника ----------

    def _them_loop(self):
        """Поток prompter-them: звук компьютера → фразы по VAD (как в _listen: начало — 2 кадра речи, конец — 0,6 с
        тишины, не длиннее 20 с) → очередь распознавания."""
        import os
        from audio_io import LoopbackCapture
        from listen import SileroVAD
        cap = LoopbackCapture(wav_path=os.environ.get("DEWIAR_PROMPTER_WAV") or None)
        try:
            self.status = "слушаю: " + cap.open()
        except Exception as e:  # noqa: BLE001
            self.status = f"звук компьютера не слышу ({e}) — подсказки по кнопке и на ваши фразы"
            log.warning("🎬 Суфлёр: %s", self.status)
            self._state()
            return
        self._state()
        vad = SileroVAD(DATA_DIR / "silero_vad.onnx")
        end_frames = int(0.6 / FRAME_S)
        pre, utt, in_speech, starts, silence = [], [], False, 0, 0
        try:
            while not self._stop.is_set():
                frame = cap.read()
                if not frame:
                    if os.environ.get("DEWIAR_PROMPTER_WAV"):
                        break
                    time.sleep(0.2)
                    continue
                if self.paused:
                    continue
                p = vad.prob(frame)
                if p > 0.5:
                    self._them_voice_t = time.monotonic()
                if not in_speech:
                    pre = (pre + [frame])[-10:]
                    starts = starts + 1 if p > 0.5 else 0
                    if starts >= 2:
                        in_speech, utt, silence = True, list(pre), 0
                    continue
                utt.append(frame)
                silence = silence + 1 if p < 0.35 else 0
                if silence >= end_frames or len(utt) * FRAME_S > 20:
                    in_speech, starts = False, 0
                    pcm = b"".join(utt[:len(utt) - max(0, silence - 10)])  # хвост слова тихий — оставляем 0,3 с
                    if len(pcm) / 2 / 16000 >= 0.5:
                        try:
                            self._q.put_nowait(("them", pcm))
                        except Exception:  # noqa: BLE001
                            pass
                    utt = []
        finally:
            cap.close()

    def _stt_loop(self):
        while not self._stop.is_set():
            try:
                who, pcm = self._q.get(timeout=0.5)
            except Exception:  # noqa: BLE001 — пусто
                continue
            if who == "mic":
                who = self._whose(pcm)
                if who is None:
                    continue
            self._stt_busy += 1
            try:
                text = (self.eng.current_stt().transcribe(pcm) or "").strip()
                self._stt_err = ""
            except Exception as e:  # noqa: BLE001
                log.info("🎬 Суфлёр: не распознал фразу: %s", e)
                self._stt_err = str(e)[:160] or "распознавание не ответило"
                continue
            finally:
                self._stt_busy = max(0, self._stt_busy - 1)
            if text:
                self.add_line(who, text)

    def _whose(self, pcm):
        """Фраза микрофона: чья? Очная встреча — по голосу; онлайн — ваша, а явно чужой голос (собеседник из колонок
        в микрофоне) — None: его слышно по звуку компьютера (а если звук компьютера выключен — это собеседник).
        Голос не запомнен — всегда ваша."""
        if self._diar is None:
            return "me"
        try:
            if self.meeting.get("place") == "live":
                who, s = self._diar.who(pcm)
                log.debug("🎬 голос: %s (%.2f)", who, s)
                return who
            from speaker import OTHER, cos
            v = self.speaker.embed(pcm)
            if v is not None and cos(v, self.speaker.owner) < OTHER:
                if not self.meeting.get("them"):
                    return "them"                          # звук компьютера не слушаем — собеседник только из микрофона
                log.info("🎬 Суфлёр: чужой голос в микрофоне — пропускаю (его слышно по звуку компьютера)")
                return None
        except Exception as e:  # noqa: BLE001 — модель голоса не загрузилась: считаем, что говорите вы
            log.info("🎬 Суфлёр: голос не определил: %s", e)
            return "them" if self.meeting.get("place") == "live" else "me"
        return "me"

    # ---------- расшифровка и поводы ----------

    def add_line(self, who, text):
        line = {"who": who, "text": text, "t": round(time.time() - self.meeting.get("started", time.time()), 1)}
        with self._lock:
            self.lines.append(line)
            self.lines = self.lines[-400:]
        self._emit("line", line=line)
        log.info("🎬 %s: %s", "Собеседник" if who == "them" else "Я", text[:120])
        if not (self.on and not self.paused and self.meeting.get("mode") == "auto"):
            return
        if who == "me":
            self._await = None                             # вы заговорили — значит, отвечаете
        if wants_hint(text, who):
            r = self.hint(q=text if who == "them" else self._last_them_q(), why="them" if who == "them" else "me")
            if who == "them" and Q_RX.search(text):
                self._await = {"t": time.monotonic(), "q": text, "id": r["id"]}

    def _last_them_q(self):
        with self._lock:
            for x in reversed(self.lines[-6:]):
                if x["who"] == "them":
                    return x["text"]
        return ""

    def _voice_t(self):
        """Когда последний раз кто-то говорил (monotonic): звук компьютера, микрофон."""
        return max(self._them_voice_t, getattr(self.eng, "mic_voice_t", 0.0) or 0.0)

    def _watch(self):
        """Поток prompter-watch: «замешкались» после вопроса и долгая пауза в разговоре."""
        hear_t = 0.0
        while not self._stop.wait(0.5):
            if time.monotonic() - hear_t >= 1.0:              # огоньки «слышу / тишина» в окне — раз в секунду
                hear_t = time.monotonic()
                self._emit("hear", hear=self.hearing())
            m = self.meeting
            if self.paused or m.get("mode") != "auto" or not m.get("nudge", True):
                continue
            now = time.monotonic()
            a = self._await
            if a:
                mic = getattr(self.eng, "mic_voice_t", 0.0) or 0.0
                if mic > a["t"] + 0.3:
                    self._await = None                     # микрофон слышит речь — человек отвечает
                elif now - a["t"] > STUCK_S:
                    self._await = None
                    self._stuck(a)
                continue
            last_hint = self.hints[-1] if self.hints else None
            busy = last_hint is not None and not last_hint.get("done")
            if (self.lines and not busy and now - self._t0 > PAUSE_AFTER and now - self._voice_t() > PAUSE_S
                    and now - self._pause_hint_t > 90 and (last_hint is None or time.time() - last_hint["ts"] > 20)):
                self._pause_hint_t = now
                log.info("🎬 Суфлёр: пауза в разговоре — подсказываю, что сказать дальше")
                try:
                    self.hint(why="pause")
                except ValueError:
                    pass

    def _stuck(self, a):
        """Собеседник спросил, вы молчите: выделить подсказку к вопросу или написать её."""
        log.info("🎬 Суфлёр: на вопрос молчат %.0f с — выделяю подсказку", STUCK_S)
        with self._lock:
            h = next((x for x in self.hints if x["id"] == a["id"]), None)
        if h is not None and not h.get("empty") and not h.get("error"):
            h["stuck"] = True
            self._emit("hint", hint=dict(h))
            return
        try:
            self.hint(q=a["q"], why="stuck")
        except ValueError:
            pass


    def hint(self, q="", why="button"):
        """Подсказка: на реплику q (или по кнопке — по последним репликам). Новая отменяет недописанную."""
        if not self.on and why != "test":
            raise ValueError("суфлёр выключен — начните встречу")
        if not self.eng.s.active_llm():
            raise ValueError("нужен «Мозг» — выберите модель в студии")
        with self._lock:
            cur = next((x for x in reversed(self.hints) if not x.get("dropped")), None)
        if why == "button" and cur is not None and not cur.get("done") and time.time() - cur["ts"] < HINT_WAIT_S + 5:
            return {"id": cur["id"], "busy": True}            # 30.10: «20 из 20» пустых — пока пишется, новую не начинаем
        if self._hint_cancel:
            self._hint_cancel.set()
        cancel = threading.Event()
        self._hint_cancel = cancel
        self._n += 1
        h = {"id": self._n, "q": q, "text": "", "done": False, "instant": False, "why": why, "ts": time.time(), "lines_at": len(self.lines)}
        with self._lock:
            self.hints.append(h)
            self.hints = self.hints[-60:]
        threading.Thread(target=self._hint_run, args=(h, cancel), name="prompter-hint", daemon=True).start()
        return {"id": h["id"]}

    def _transcript(self, n=14):
        with self._lock:
            ls = self.lines[-n:]
        return "\n".join(("Собеседник: " if x["who"] == "them" else "Вы: ") + x["text"] for x in ls)

    def _sheet_match(self, q):
        """Готовый ответ из шпаргалки, если вопрос похож. Основы сравниваем по началу («стои» и «сто» — одно слово):
        устная речь и написанное заранее редко совпадают буква в букву."""
        from knowledge import words
        qs = {w for w in words(q) if len(w) > 2}
        best, score = None, 0.0
        for it in self.sheet:
            ws = {w for w in words(it["q"]) if len(w) > 2}
            if not ws or not qs:
                continue
            same = sum(1 for w in qs if any(w.startswith(v) or v.startswith(w) for v in ws))
            s = same / max(3, min(len(qs), len(ws)))
            if s > score:
                best, score = it, s
        return best if score >= 0.5 else None

    @staticmethod
    def _ask_line(why, q):
        if why == "pause":
            return ("В разговоре повисла пауза. Что человеку сказать или спросить сейчас, чтобы продвинуться к цели? "
                    "Первая строка — готовая фраза, которую можно произнести.")
        if why in ("me", "stuck"):
            return ((f"Собеседник спросил: «{q}». " if q else "") + "Человек замешкался с ответом. Первая строка — "
                    "готовая фраза, с которой начать ответ; дальше — опоры.")
        if q:
            return f"ПОДСКАЖИ, что ответить на: «{q}»"
        return "Человек нажал «Подсказать»: что ему сказать или спросить дальше?"

    def _hint_run(self, h, cancel):
        from llm import LLMError, stream_events
        def drop():                                    # отменили (пришла новая) — пустую карточку не оставляем
            h["dropped"] = True
            self._emit("hint", hint=dict(h))
        if h["why"] == "them":                         # собеседник мог договорить следующей фразой — подождём чуть-чуть
            cancel.wait(0.5)
            if cancel.is_set():
                return drop()
            with self._lock:
                more = [x["text"] for x in self.lines[h["lines_at"]:] if x["who"] == "them"]
            if more:
                h["q"] = (h["q"] + " " + " ".join(more)).strip()
        q = h["q"]
        hit = self._sheet_match(q) if q and self.sheet else None
        if hit:                                        # из шпаргалки — сразу, пока модель пишет
            h.update(text=hit["a"], instant=True)
            self._emit("hint", hint=dict(h))
        mats = self._materials(q + " " + self._transcript(4))
        kn = []
        if self.meeting.get("knowledge"):
            try:
                kn = [(f"Знания/{r['path']}", r["text"]) for r in self.eng.knowledge.search(q or self._transcript(4), limit=2)]
            except Exception:  # noqa: BLE001
                kn = []
        m = self.meeting
        ctx = (f"ВСТРЕЧА: {m.get('title', '')}\nЦЕЛЬ ЧЕЛОВЕКА: {m.get('goal') or 'не указана'}\n\n"
               + ("МАТЕРИАЛЫ:\n" + "\n\n".join(f"[{n}]\n{c}" for n, c in mats + kn) + "\n\n" if mats or kn else "МАТЕРИАЛОВ НЕТ.\n\n")
               + ("ШПАРГАЛКА:\n" + "\n".join(f"В: {x['q']} — О: {x['a']}" for x in self.sheet[:10]) + "\n\n" if self.sheet else "")
               + "РАЗГОВОР (последние реплики):\n" + (self._transcript() or "(пока тихо)") + "\n\n"
               + self._ask_line(h["why"], q))
        prof = dict(self.eng.s.active_llm(), temperature=0.3, max_tokens=500)
        text, last, t0 = "", 0.0, time.monotonic()
        slow = threading.Event()

        def watchdog():                                # модель молчит — не держим пустую карточку бесконечно
            if not cancel.wait(HINT_WAIT_S) and not text and not h.get("done"):
                slow.set()
                cancel.set()
        threading.Thread(target=watchdog, name="prompter-hint-wait", daemon=True).start()
        try:
            for kind, val in stream_events(prof, HINT_SYSTEM, [{"role": "user", "content": ctx}], cancel=cancel, tools=None):
                if cancel.is_set():
                    break
                if kind != "text":
                    continue
                if not text:
                    log.info("🎬 Подсказка: первые слова через %.1f с", time.monotonic() - t0)
                text += val
                if time.monotonic() - last > 0.08:
                    h.update(text=text.strip(), instant=False)
                    self._emit("hint", hint=dict(h))
                    last = time.monotonic()
        except LLMError as e:
            if not cancel.is_set() or slow.is_set():
                h.update(text=h["text"] if h["instant"] else "", done=True, error=str(e)[:200])
                self._emit("hint", hint=dict(h))
            elif not h["instant"]:
                drop()
            return
        if slow.is_set():
            h.update(done=True, error=f"модель не ответила за {HINT_WAIT_S:.0f} с — «Мозг» занят или нет связи. Нажмите «Подсказать» ещё раз")
            self._emit("hint", hint=dict(h))
            log.info("🎬 Подсказка №%d: модель молчит %.0f с", h["id"], HINT_WAIT_S)
            return
        if cancel.is_set():
            if not h["instant"]:
                drop()
            return
        cancel.set()                                   # сторожу больше нечего ждать
        text = text.strip()
        if (text in ("—", "-", "–") or not text) and h["why"] == "button" and not h["instant"]:
            # по кнопке человек ждёт ответа — пустую карточку не прячем молча, а говорим почему
            h.update(done=True, note=("Разговора пока не слышно — подсказать нечего. Как только собеседник заговорит, "
                                      "подсказки пойдут сами." if not self.lines else
                                      "Сейчас подсказывать нечего — последняя реплика не вопрос. Нажмите, когда понадобится."))
        elif text in ("—", "-", "–") or not text:
            h.update(done=True, empty=not h["instant"], text=h["text"] if h["instant"] else "")
        else:
            h.update(text=text, done=True, instant=False)
        src = re.search(r"(?im)^\s*источник\s*:\s*(.+)$", h["text"])
        h["src"] = src.group(1).strip() if src else ""
        self._emit("hint", hint=dict(h))
        log.info("🎬 Подсказка №%d за %.1f с%s", h["id"], time.monotonic() - t0, " (пусто)" if h.get("empty") else "")

    # ---------- шпаргалка и итог ----------

    def _ask_model(self, system, content, max_tokens=900):
        from llm import stream_events
        prof = self.eng.s.active_llm()
        if not prof:
            return ""
        prof = dict(prof, temperature=0.3, max_tokens=max_tokens)
        return "".join(v for k, v in stream_events(prof, system, [{"role": "user", "content": content}], tools=None) if k == "text").strip()

    def _prepare_sheet(self):
        m = self.meeting
        mats = self._materials(m.get("goal", "") + " " + m.get("title", ""), limit=6, budget=6000)
        content = (f"ВСТРЕЧА: {m.get('title', '')}\nЦЕЛЬ: {m.get('goal') or 'не указана'}\n\n"
                   + ("МАТЕРИАЛЫ:\n" + "\n\n".join(f"[{n}]\n{c}" for n, c in mats) if mats else "МАТЕРИАЛОВ НЕТ."))
        try:
            sheet = parse_sheet(self._ask_model(SHEET_SYSTEM, content))
        except Exception as e:  # noqa: BLE001
            log.info("🎬 Шпаргалка не собралась: %s", e)
            return
        if not self.on:
            return
        self.sheet = sheet
        log.info("🎬 Шпаргалка готова: %d вопросов", len(sheet))
        self._emit("sheet", sheet=sheet)

    def _summarize(self):
        m = dict(self.meeting)
        with self._lock:
            lines = list(self.lines)
        talk = "\n".join(("Собеседник: " if x["who"] == "them" else "Вы: ") + x["text"] for x in lines)
        self._emit("summary", summary="", busy=True)
        try:
            text = self._ask_model(SUMMARY_SYSTEM, f"ВСТРЕЧА: {m.get('title', '')}\nЦЕЛЬ: {m.get('goal') or '—'}\n\nРАСШИФРОВКА:\n{talk[-24000:]}",
                                   max_tokens=1200)
        except Exception as e:  # noqa: BLE001
            text = ""
            log.info("🎬 Итог встречи не получился: %s", e)
        started = datetime.fromtimestamp(m.get("started") or time.time())
        mins = max(1, round(((lines[-1]["t"] if lines else 60)) / 60))
        body = (f"# {m.get('title', 'Встреча')}\n\n*{started:%d.%m.%Y %H:%M} · {mins} мин · суфлёр Dewiar*\n\n"
                + (f"**Цель:** {m['goal']}\n\n" if m.get("goal") else "")
                + (text or "_Итог не получился — модель не ответила._")
                + ("\n\n## Материалы\n" + "\n".join(f"- {f['name']}" for f in self.files) if self.files else "")
                + ("\n\n## Расшифровка\n" + "\n".join(("**Собеседник:** " if x["who"] == "them" else "**Вы:** ") + x["text"] for x in lines)
                   if m.get("keep_text") else ""))
        path = ""
        try:
            d = self.eng.workspace.ensure() / "Встречи"
            d.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r'[\\/:*?"<>|]+', " ", m.get("title", "Встреча")).strip()[:60] or "Встреча"
            f = d / f"{started:%Y-%m-%d %H%M} {safe}.md"
            f.write_text(body, encoding="utf-8")
            path = str(f)
        except OSError as e:
            log.warning("🎬 Итог встречи не сохранён: %s", e)
        self.summary = body
        log.info("🎬 Итог встречи: %s", path or "(не сохранён)")
        self._emit("summary", summary=body, path=path, busy=False)

