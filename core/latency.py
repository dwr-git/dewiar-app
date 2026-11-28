"""«Голос без пауз» (0.66; №5 в «Идеях Лиры» — первое по голосам): сколько человек ждёт от конца своей фразы до первого
звука ответа — и на чём именно. Каждый голосовой ход размечается метками (monotonic, секунды):

  end  — фраза кончилась (пауза тишины после речи)        stt   — распознавание готово
  req  — вопрос ушёл к модели (после справки и подготовки) tok   — первые слова модели
  say  — первая фраза ответа отдана голосу                audio — первый звук пошёл в динамик

Отсюда этапы: распознавание (stt−end), подготовка (req−stt), модель (tok−req), первая фраза (say−tok), голос (audio−say)
и итог (audio−end). 20.11 (разбор: облако отвечает первым байтом за 1,1 с, а первые слова у людей — через 6,7 с): ещё
srv — сервер ответил хоть чем-то (req→ev); 21.11 — hdr (заголовки ответа) и line (первая строка потока): сеть и
посредники отдельно от модели; acts — сколько действий модель сделала до первых слов; в сводке — модель
отдельно для ответов без действий и с действиями. Ответ без модели (погода, радио, «который час») — без req/tok: только итог. Ход в журнал одной строкой,
в пульс — медианы и 90-й процентиль за срок (только числа, без слов). Текстовые вопросы (набрали в чате) не меряются."""

import threading
import time

ORDER = ("end", "stt", "req", "tok", "say", "audio")
# «Рентген дороги» (1.0.70): от «вопрос ушёл» — соединение, шифрование, запрос отправлен, заголовки ответа, первая строка
ROAD = ("conn", "tls", "sent", "hdr", "line")
STAGES = (("stt", "end", "stt"), ("prep", "stt", "req"), ("model", "req", "tok"), ("text", "tok", "say"), ("voice", "say", "audio"))


def _pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(len(xs) - 1, int(k) + 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 2)


class Latency:
    def __init__(self, keep=300):
        self._lock = threading.Lock()
        self.cur = None
        self.samples = []
        self.keep = keep

    def start(self, t_end=None):
        """Голосовая фраза кончилась и ушла в распознавание."""
        with self._lock:
            self.cur = {"end": t_end if t_end is not None else time.monotonic()}

    def drop(self):
        """Фраза оказалась не вопросом (ложное имя, разговор рядом) — не меряем."""
        with self._lock:
            self.cur = None

    def act(self):
        """Модель вызвала действие до первых слов (погода, напоминание…) — в счёт хода."""
        with self._lock:
            if self.cur is not None and "tok" not in self.cur:
                self.cur["acts"] = self.cur.get("acts", 0) + 1

    def mark(self, k, t=None):
        with self._lock:
            if self.cur is not None and k not in self.cur:
                self.cur[k] = t if t is not None else time.monotonic()

    def info(self, k, v):
        """Не время, а число хода (1.0.93: «kb» — сколько килобайт ушло к облаку, сжатым)."""
        with self._lock:
            if self.cur is not None:
                self.cur.setdefault("i_" + k, v)

    def done(self, how=""):
        """Первый звук пошёл: записать ход. -> {этап: секунды, total} или None (не голосовой ход)."""
        with self._lock:
            c, self.cur = self.cur, None
            if c is None:
                return None
            c.setdefault("audio", time.monotonic())
            rec = {"total": round(c["audio"] - c["end"], 2)}
            for name, a, b in STAGES:
                if a in c and b in c and c[b] >= c[a]:
                    rec[name] = round(c[b] - c[a], 2)
            if "req" in c and "ev" in c and c["ev"] >= c["req"]:
                rec["srv"] = round(c["ev"] - c["req"], 2)
            for k in ROAD:                               # 21.11: заголовки ответа и первая строка потока — от запроса; 1.0.70: и шаги до них
                if "req" in c and k in c and c[k] >= c["req"]:
                    rec[k] = round(c[k] - c["req"], 2)
            if "model" in rec:
                rec["acts"] = int(c.get("acts", 0))
            if "i_kb" in c:
                rec["kb"] = c["i_kb"]
            if how:
                rec["how"] = how
            if 0 <= rec["total"] < 120:
                self.samples = (self.samples + [rec])[-self.keep:]
            return rec

    @staticmethod
    def line(rec):
        names = {"stt": "распознавание", "prep": "подготовка", "model": "модель", "text": "первая фраза", "voice": "голос"}
        parts = [f"{names[k]} {rec[k]:.1f}" for k, _, _ in STAGES if k in rec]
        return f"⏱ от конца фразы до звука {rec['total']:.1f} с" + (f" ({', '.join(parts)})" if parts else " (без модели)")

    def take(self):
        """Сводка для пульса (и забыть отправленное): {n, total: [p50, p90], stt, prep, model, text, voice: p50}."""
        with self._lock:
            xs, self.samples = self.samples, []
        return self.summary(xs)


    @staticmethod
    def summary(xs):
        if not xs:
            return {}
        out = {"n": len(xs), "total": [_pct([x["total"] for x in xs], .5), _pct([x["total"] for x in xs], .9)]}
        for name, _, _ in STAGES:
            v = [x[name] for x in xs if name in x]
            if v:
                out[name] = _pct(v, .5)
        model = [x["total"] for x in xs if "model" in x]
        if model:
            out["with_model"] = _pct(model, .5)
        srv = [x["srv"] for x in xs if "srv" in x]
        if srv:
            out["srv"] = _pct(srv, .5)
        for k in ROAD:
            v = [x[k] for x in xs if k in x]
            if v:
                out[k] = _pct(v, .5)
        plain = [x["model"] for x in xs if "model" in x and not x.get("acts")]
        acts = [x["model"] for x in xs if "model" in x and x.get("acts")]
        if plain:
            out["model_plain"] = _pct(plain, .5)
        if acts:
            out["model_acts"], out["acts_n"] = _pct(acts, .5), len(acts)
        return out
