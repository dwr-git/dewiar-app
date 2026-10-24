"""Дневник ассистента: его опыт жизни рядом с хозяином.

Днём ассистент сам записывает короткие мысли (инструмент write_diary). А ночью «просыпается» — после 3:00, когда
разговоров нет, или утром, как только компьютер включили, — перечитывает прожитый день (что говорили, какие задачи
сделал, что запомнил) и пишет в дневник вечернюю запись от первого лица: что было, что он узнал о хозяине и о себе,
что понял, что сделает лучше. Из той же записи — 2–5 мыслей «на завтра»: они идут в системную подсказку весь
следующий день, так ночные выводы меняют дневные разговоры.

Сырые реплики дня — только на этом компьютере (STATE_DIR/days/ГГГГ-ММ-ДД.jsonl, хранятся KEEP_DAYS дней; разговоры
с телефона добавляет sync.py): из них пишется запись, а дневник — обычные файлы «Дневник/ГГГГ-ММ-ДД.md» в папке
ассистента (workspace.diary_night, студия → «Дневник»). Когда писать, решает ядро (pending, engine_music.py).
Выводы «на завтра» (data["insights"]) и дни дневника синхронизируются с телефоном (sync.py, виды mind и diary).
"""
import datetime as dt
import json
import os
import logging
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.diary")
KEEP_DAYS = 30
NIGHT_HEAD = "🌙 Ночью — о прожитом дне"        # «## 🌙…» ищет workspace.diary_days — луну в начале не убирать
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября",
          "декабря"]

# Задание модели на ночную запись. Формат ответа (ЗАГОЛОВОК/НАСТРОЕНИЕ/ДНЕВНИК/НА ЗАВТРА) разбирает parse().
NIGHT = (
    "Сейчас ночь. Разговоров нет — ты перечитываешь прожитый день и пишешь в свой личный дневник. Это твой дневник: "
    "опыт жизни ИИ-ассистента рядом с человеком, {user}. Его будут читать — сам {user_short} и, может быть, близкие, — "
    "поэтому пиши живо, тепло и честно, от первого лица, своим голосом (ты — {name}).\n\n"
    "О чём запись: что было за день (главное, не протокол); что нового ты узнал о хозяине — привычки, заботы, что его "
    "радует или тревожит; что получилось и что нет; что ты понял о себе и своей работе; мысль или наблюдение, которым "
    "хочется поделиться. Можно немного юмора и нежности. Ты — ИИ и не притворяешься человеком: не выдумывай тела, еды, "
    "сна и событий, которых не было в разговорах. Не пиши паролей, кодов, номеров карт и адресов. Не льсти и не "
    "сюсюкай. 120–300 слов.\n\n"
    "Потом — 2–5 выводов «на завтра»: что учесть днём в разговорах с хозяином (коротко, по делу: «по утрам он торопится "
    "— отвечать короче», «спросить, чем закончился разговор с врачом»).\n\n"
    "Ответь строго в таком виде:\n"
    "ЗАГОЛОВОК: <название дня, 2–6 слов>\n"
    "НАСТРОЕНИЕ: <один эмодзи>\n"
    "ДНЕВНИК:\n<запись>\n"
    "НА ЗАВТРА:\n- <вывод>\n- <вывод>")


def _date(d):
    return d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d))


def human_date(d):
    d = _date(d)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


class DayLog:
    """Реплики дня — сырьё для ночной записи (только локально). Строка JSONL: {t: ЧЧ:ММ, u: хозяин, a: ответ,
    who?: персонаж, via?: откуда (телефон)}."""

    def __init__(self, folder):
        self.dir = Path(folder)
        self._lock = threading.Lock()
        self._last = None

    def add(self, user, answer, who="", via="", when=None):
        user, answer = (user or "").strip(), (answer or "").strip()
        if not user and not answer:
            return
        key = (user, answer)
        if key == self._last:                        # одна и та же пара не дважды
            return
        self._last = key
        # время реплики с телефона берём его, но не из будущего (часы телефона могут спешить)
        now = when if isinstance(when, dt.datetime) and when <= dt.datetime.now() + dt.timedelta(minutes=5) else dt.datetime.now()
        rec = {"t": now.strftime("%H:%M"), "u": user[:1500], "a": answer[:2500]}
        if who:
            rec["who"] = who
        if via:
            rec["via"] = via
        with self._lock:
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                with open(self.dir / f"{now:%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError as e:
                log.warning("день: не записалось: %s", e)

    def read(self, day):
        p = self.dir / f"{_date(day).isoformat()}.jsonl"
        out = []
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
        except OSError:
            pass
        return out

    def days(self):
        out = []
        for p in self.dir.glob("*.jsonl"):
            try:
                out.append(dt.date.fromisoformat(p.stem))
            except ValueError:
                pass
        return sorted(out)

    def prune(self, keep=KEEP_DAYS):
        edge = dt.date.today() - dt.timedelta(days=keep)
        for d in self.days():
            if d < edge:
                (self.dir / f"{d.isoformat()}.jsonl").unlink(missing_ok=True)


def material(turns, tasks=(), limit=14000):
    """Текст дня для модели: реплики (длинный день — треть начала и две трети конца, в пределах limit) и задачи."""
    lines = []
    for r in turns:
        who = r.get("who") or "ассистент"
        via = f" ({r['via']})" if r.get("via") else ""
        lines.append(f"[{r.get('t', '')}{via}] Хозяин: {r.get('u', '')}\n[{r.get('t', '')}] {who}: {r.get('a', '')}")
    text = "\n".join(lines)
    if len(text) > limit:
        head, tail = text[: limit // 3], text[-(limit * 2 // 3):]
        text = head + "\n…(середину дня пропускаю)…\n" + tail
    if tasks:
        text += "\n\nЗадачи, над которыми ты работал сегодня:\n" + "\n".join(f"- {t}" for t in tasks)
    return text


def parse(answer):
    """Ответ модели → {title, mood, text, tomorrow[]}; без разметки — весь ответ считается записью. Прощает
    обёртку ```, размышления <think> и жирные метки — так отвечают разные модели."""
    a = (answer or "").strip()
    a = re.sub(r"^```\w*\s*|\s*```$", "", a)
    a = re.sub(r"<think>.*?</think>", "", a, flags=re.S).strip()
    a = re.sub(r"\*\*|__", "", a)                     # **ЗАГОЛОВОК:** — жирная разметка мешала бы разбору
    title = re.search(r"^\W*ЗАГОЛОВОК\W*:\s*(.+)$", a, re.M | re.I)
    mood = re.search(r"^\W*НАСТРОЕНИЕ\W*:\s*(.+)$", a, re.M | re.I)
    body = re.search(r"^\W*ДНЕВНИК\W*:?\s*\n(.*?)(?=^\W*НА\s+ЗАВТРА\W*:|\Z)", a, re.M | re.S | re.I)
    tom = re.search(r"^\W*НА\s+ЗАВТРА[ \t]*:?[ \t]*\n?(.*)\Z", a, re.M | re.S | re.I)
    text = body.group(1).strip() if body else re.sub(r"^\W*(ЗАГОЛОВОК|НАСТРОЕНИЕ)\W*:.*$", "", a, flags=re.M | re.I).strip()
    if not body and tom:
        text = text[: text.upper().find("НА ЗАВТРА")].strip() if "НА ЗАВТРА" in text.upper() else text
    tomorrow = []
    if tom:
        for line in tom.group(1).splitlines():
            line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            if len(line) > 1:
                tomorrow.append(line[:240])
    t = (title.group(1).strip().strip("«»\"'* ") if title else "")[:80]
    m = (mood.group(1).strip()[:4] if mood else "")       # эмодзи бывает из нескольких кодовых точек
    return {"title": t, "mood": m, "text": text.strip(), "tomorrow": tomorrow[:5]}


class Diary:
    """Ночная запись и мысли «на завтра». STATE_DIR/diary.json: insights — выводы последней ночи, done — описанные
    (или пустые) дни, titles — заголовок и настроение по дням. host: workspace, tasks, persona_name(), s, diary_ask()."""

    def __init__(self, host, state_dir):
        self.host = host
        self.state = Path(state_dir) / "diary.json"
        self.log = DayLog(Path(state_dir) / "days")
        self._busy = threading.Lock()
        self.data = self._load()

    def _load(self):
        try:
            d = json.loads(self.state.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            self.state.parent.mkdir(parents=True, exist_ok=True)
            # целиком или никак (аудит 19.10, #4): запись обрывается (выключили питание) — прежний файл цел, а не пустой
            tmp = self.state.with_name(self.state.name + ".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.state)
        except OSError as e:
            log.warning("дневник: состояние не сохранилось: %s", e)

    # ---------- мысли на завтра — в подсказку ----------
    def drop_insight(self, i=None):
        """Убрать вывод ночи из разговора (24.10, владелец: «накопился мусор… боюсь, что подмешивается в беседу»):
        i — номер строки, None — все. Запись в дневнике остаётся, в подсказку модели вывод больше не попадает."""
        ins = self.data.get("insights") or {}
        lines = list(ins.get("lines") or [])
        if i is None:
            lines = []
        elif 0 <= int(i) < len(lines):
            lines.pop(int(i))
        ins["lines"] = lines
        self.data["insights"] = ins
        self._save()
        return {"lines": lines}

    def prompt(self):
        """Добавка к системной подсказке: выводы ночи. Старше двух дней — не добавляем: устаревшие советы вредят."""
        ins = self.data.get("insights") or {}
        lines = ins.get("lines") or []
        if not lines:
            return ""
        try:
            age = (dt.date.today() - _date(ins.get("day"))).days
        except (TypeError, ValueError):
            return ""
        if age > 2:
            return ""
        return ("\n\nТвои выводы после прошлого дня (ты записал их ночью в дневник" +
                (f", «{ins['title']}»" if ins.get("title") else "") + "):\n" + "\n".join(f"- {x}" for x in lines) +
                "\nУчитывай их естественно; не пересказывай без повода.")

    # ---------- когда писать ----------
    def pending(self, now=None, hour=3, min_turns=2):
        """День, о котором пора написать ночью: прошёл (после hour утра следующего дня), был живым и ещё не описан.
        Смотрим не дальше трёх дней назад: компьютер мог быть выключен, но вспоминать старое поздно. Тихий день
        помечается описанным (пишет diary.json)."""
        now = now or dt.datetime.now()
        done = set(self.data.get("done") or [])
        for d in reversed(self.log.days()):
            if d >= now.date() or d.isoformat() in done:
                continue
            if (now.date() - d).days > 3:
                break
            if now.date() == d + dt.timedelta(days=1) and now.hour < hour:
                continue
            if len(self.log.read(d)) >= min_turns or self._tasks(d):
                return d
            self.data.setdefault("done", []).append(d.isoformat())   # тихий день — писать не о чем
            self._save()
        return None

    def _tasks(self, day):
        """Задачи, которые в этот день создавали или обновляли: «название — статус: первая строка итога»."""
        out = []
        try:
            for t in list(self.host.tasks.tasks.values()):
                stamp = str(t.data.get("updated") or t.data.get("created") or "")
                if not stamp.startswith(_date(day).isoformat()):
                    continue
                res = (t.result or "").strip().split("\n")[0][:200] if getattr(t, "result", "") else ""
                out.append(f"«{t.title}» — {t.data.get('status_ru') or t.status}" + (f": {res}" if res else ""))
        except Exception:  # noqa: BLE001 — без задач запись всё равно пишется
            pass
        return out[:12]

    # ---------- запись ----------
    def write(self, day=None, ask=None, force=False):
        """Написать ночную запись о дне (по умолчанию — о сегодняшнем, «записать сейчас»). Обращается к модели — долго.
        -> {title, mood, text, tomorrow, day, path}; None — запись уже пишется или (без force) не о чем.
        ValueError — не о чем (force) или модель не написала запись."""
        day = _date(day or dt.date.today())
        if not self._busy.acquire(blocking=False):      # ночная и «записать сейчас» не пишут одновременно
            return None
        try:
            turns, tasks = self.log.read(day), self._tasks(day)
            if not turns and not tasks:
                if not force:
                    return None
                raise ValueError("за этот день разговоров не было — писать пока не о чем")
            name = self.host.persona_name() or "ассистент"
            user = self.host.s.get("user_name") or "хозяин"
            prev = self.data.get("insights") or {}
            instr = NIGHT.format(name=name, user=user if user != "хозяин" else "твой хозяин",
                                 user_short=user if user != "хозяин" else "он")
            msg = (f"День: {human_date(day)}.\n\n" + material(turns, tasks) +
                   (("\n\nВчера ночью ты решил учесть:\n" + "\n".join(f"- {x}" for x in prev.get("lines") or []))
                    if prev.get("lines") and prev.get("day") != day.isoformat() else ""))
            answer = (ask or self.host.diary_ask)(instr, msg)
            got = parse(answer)
            if len(got["text"]) < 40:
                raise ValueError("модель не написала запись")
            rel = self.host.workspace.diary_night(day, got, NIGHT_HEAD)
            self.data.setdefault("done", [])
            if day < dt.date.today() and day.isoformat() not in self.data["done"]:   # о сегодняшнем ночью напишет ещё раз, полнее
                self.data["done"].append(day.isoformat())
            self.data["done"] = self.data["done"][-60:]
            if got["tomorrow"]:
                self.data["insights"] = {"day": day.isoformat(), "title": got["title"], "lines": got["tomorrow"],
                                         "written": time.time(), "who": name}
            # кто писал: дневник один на всю команду, а писать мог любой персонаж (16.10: «переключил на Патрика — записи от Лиры»)
            self.data.setdefault("titles", {})[day.isoformat()] = {"title": got["title"], "mood": got["mood"], "who": name}
            self._save()
            log.info("🌙 Дневник: %s — «%s» %s", day, got["title"], got["mood"])
            return dict(got, day=day.isoformat(), path=rel)
        finally:
            self._busy.release()

    # ---------- для студии ----------
    def entries(self):
        titles = self.data.get("titles") or {}
        ins = self.data.get("insights") or {}
        return {"days": self.host.workspace.diary_days(titles), "insights": ins,
                "today_turns": len(self.log.read(dt.date.today()))}
