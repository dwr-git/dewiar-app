"""Вспомнить из записей: поиск по заметкам, памяти, дневнику, «Входящим», итогам задач (SOURCES) и, если подключено,
по хранилищу Obsidian (пути «obsidian:…») — без модели и без интернета.

Записи режутся на куски (абзацы/пункты списков), слова сводятся к основе (грубый русский стеммер), ранжирование —
BM25. Индекс держится в памяти и обновляется по времени изменения файлов, так что поиск — миллисекунды даже на
сотнях заметок. Используется:
  • перед каждым ответом (context) — если в записях есть что-то явно по теме вопроса, это идёт модели в подсказку
    («Когда у Маши день рождения?» → заметка «Маша — 12 марта»); работает даже с моделью без инструментов;
  • инструментом find_notes и поиском на странице «Память» в студии.
Сейф (vault.py) сюда не входит: секреты не должны попадать в подсказку модели.
"""

import math
import re
import threading
import time
from collections import Counter
from pathlib import Path

SOURCES = (("Заметки", "заметка"), ("Память", "память"), ("Дневник", "дневник"), ("Входящие", "входящие"),
           ("Задачи", "задача"))
TEXT_EXT = {".md", ".txt"}
SKIP = {"Память/Конституция.md", "Память/Уроки задач.md", "Память/Уроки.md"}     # служебное: конституция и уроки задач (quality.py) идут модели своим путём
# стоп-слова: служебные и слова самих просьб («напомни, что я записывал…») — по ним искать бессмысленно
STOP = set("""а без бы был была были было быть в вам вас весь во вот все всё всего всех вы где да даже для до его ее её
ей ему если есть еще ещё же за здесь и из или им их к как какая какие какой когда кто ли либо мне меня мной мы на над
надо наш не него нее неё нет ни них но ну о об однако он она они оно от очень по под после при про с со так также там
те тем то того тоже той только том ты у уже хотя чего чей чем что чтобы чтоб эта эти это этот я мой моя мои моё мое мою
мне свой своя свои себе себя сказать скажи подскажи напомни расскажи покажи найди помнишь помню знаешь какой какая
какое какие сколько где когда записал записала записывал записывали записано заметка заметки заметку заметке сохранял
сохранил сохранила говорил говорила был была было это вообще можешь можно пожалуйста там тут""".split())


# общие слова просьб и разговора — тему не задают: одни они записи к вопросу не тянут (context); основы, как у words()
GENERIC_WORDS = """задача задачи задачу задаче задачей задач файл файла файлы файлов папка папки папку папке работа работы работу
работе сделать сделай делать интересует интересно интересна вопрос вопросы тема темы текст информация нужно нужна нужен хочу
хотел хотела сегодня вчера завтра сейчас теперь потом новый новая новое новые старый старая результат итог итоги посмотри
посмотреть проверь проверить почему зачем сделано готово дела дело""".split()


# слова с чередованием в основе — формы одного слова к одной основе («день рождения» ↔ «дни рождения»)
IRREG = {**{f: "дн" for f in ("день", "дня", "дню", "днем", "дни", "дней", "дням", "днями", "днях")},
         **{f: "год" for f in ("год", "года", "году", "годом", "годе", "годы", "годов", "лет")},
         **{f: "мать" for f in ("мать", "матери", "матерью", "мама", "мамы", "маме", "маму", "мамой")},
         **{f: "ребен" for f in ("ребенок", "ребенка", "ребенку", "ребенком", "дети", "детей", "детям", "детьми", "детях")},
         **{f: "человек" for f in ("человек", "человека", "человеку", "люди", "людей", "людям", "людьми")}}


def stem(w):
    """Грубая основа русского слова: срезаем одно окончание (основа не короче 3 букв), затем ещё гласную у длинных
    и беглую гласную. Ошибки допустимы — важно лишь, чтобы формы одного слова сходились к одной основе."""
    w = w.lower().replace("ё", "е")
    if w in IRREG:
        return IRREG[w]
    if len(w) <= 3:
        return w
    for suf in ("ться", "тся", "ить", "ать", "ять", "еть", "ила", "ала", "яла", "или", "али", "яли", "ил", "ал", "ял", "иями", "ями", "ами", "ией", "иям", "ием", "иях", "ого", "его", "ому", "ему", "ыми", "ими", "ых", "их",
                "ой", "ей", "ий", "ый", "ая", "яя", "ое", "ее", "ую", "юю", "ом", "ем", "ам", "ям", "ах", "ях", "ов", "ев",
                "ия", "ие", "ию", "ии", "а", "я", "о", "е", "у", "ю", "ы", "и", "ь", "й"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[:-len(suf)]
            break
    if len(w) >= 5 and w[-1] in "аяоеуюыи":                  # «вайфай» → «вайфа» → «вайф» = «вайфая»
        w = w[:-1]
    if (len(w) >= 5 and w[-2:] in ("ок", "ек")) or (len(w) >= 4 and w.endswith("ец")):          # беглая гласная: список/списка, покупок/покупки
        w = w[:-2] + w[-1]
    return w


def words(text):
    return [stem(w) for w in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", text) if w.lower() not in STOP and len(w) > 1]


GENERIC = {stem(w) for w in GENERIC_WORDS}


def _chunks(text, limit=600):
    """Куски до ~limit знаков: короткие абзацы склеиваются, длинный режется по строкам.
    Заголовок файла к каждому куску добавляет вызывающий (в слова для поиска, не в текст куска)."""
    out, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) < limit:
            buf = (buf + "\n\n" + para).strip()
            continue
        if buf:
            out.append(buf)
        if len(para) > limit:
            lines, cur = para.splitlines(), ""
            for ln in lines:
                if len(cur) + len(ln) > limit and cur:
                    out.append(cur)
                    cur = ""
                cur = (cur + "\n" + ln).strip()
            buf = cur
        else:
            buf = para
    if buf:
        out.append(buf)
    return out


class Recall:
    def __init__(self, root_fn, extra_fn=None):
        self.root_fn = root_fn                   # → Path папки ассистента (может смениться)
        self.extra_fn = extra_fn                 # → (хранилище Obsidian, папка ассистента в нём) или None
        self._vault_seen, self._vault_at, self._vault_key = set(), 0.0, None
        self._lock = threading.Lock()
        self._files = {}                         # путь → (mtime, [(текст куска, Counter слов, длина)], заголовок)
        self._root = None

    def _refresh(self):
        """Переиндексирует изменившиеся файлы и забывает исчезнувшие. Вызывать под self._lock."""
        root = Path(self.root_fn())
        if root != self._root:
            self._files, self._root = {}, root
        seen = set()
        for folder, _ in SOURCES:
            base = root / folder
            if not base.is_dir():
                continue
            for p in base.rglob("*"):
                if p.suffix.lower() not in TEXT_EXT or not p.is_file() or any(x.startswith(".") for x in p.parts):
                    continue
                if folder == "Задачи" and p.name not in ("итог.md", "план.md"):
                    continue                           # из задачи — только суть; журналы и черновики засоряют поиск
                if "рабочая копия" in p.parts:
                    continue
                rel = p.relative_to(root).as_posix()
                if rel in SKIP or rel.startswith("Память/Душа/"):     # конституция и душа и так в каждой подсказке
                    continue
                seen.add(rel)
                try:
                    mt = p.stat().st_mtime
                except OSError:
                    continue
                if rel in self._files and self._files[rel][0] == mt:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")[:400_000]
                except OSError:
                    continue
                title = p.stem if folder != "Задачи" else p.parent.name
                chunks = []
                for c in _chunks(text):
                    ws = words(title + " " + c)
                    chunks.append((c, Counter(ws), len(ws)))
                self._files[rel] = (mt, chunks, title)
        seen |= self._refresh_vault()
        for rel in list(self._files):
            if rel not in seen:
                del self._files[rel]

    def _refresh_vault(self):
        """Заметки Obsidian — в поиск (пути «obsidian:…», их открывает workspace.read). Папку ассистента в хранилище
        пропускаем — она уже проиндексирована как своя. Хранилище обходим не чаще раза в 15 секунд: оно бывает
        большим, а поиск идёт перед каждым ответом. -> множество путей хранилища."""
        x = self.extra_fn() if self.extra_fn else None
        if not x:
            self._vault_seen, self._vault_key = set(), None
            return set()
        vault, skip = x
        key = (str(vault), skip)
        if key == self._vault_key and time.time() - self._vault_at < 15:
            return self._vault_seen
        from obsidian import vault_files
        seen = set()
        for p in vault_files(vault, skip):
            rel = "obsidian:" + p.relative_to(vault).as_posix()
            seen.add(rel)
            try:
                mt = p.stat().st_mtime
            except OSError:
                continue
            if rel in self._files and self._files[rel][0] == mt:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")[:400_000]
            except OSError:
                continue
            chunks = []
            for c in _chunks(text):
                ws = words(p.stem + " " + c)
                chunks.append((c, Counter(ws), len(ws)))
            self._files[rel] = (mt, chunks, p.stem)
        self._vault_seen, self._vault_at, self._vault_key = seen, time.time(), key
        return seen

    def search(self, query, limit=5):
        """→ [{"path", "title", "snippet", "score", "hits", "kind"}] — лучшие куски, по одному на файл.
        hits — сколько разных слов вопроса нашлось в куске."""
        q = list(dict.fromkeys(words(query)))
        if not q:
            return []
        with self._lock:
            self._refresh()
            docs = [(rel, title, c, cnt, ln) for rel, (_, chunks, title) in self._files.items() for c, cnt, ln in chunks]
        if not docs:
            return []
        n = len(docs)
        avg = sum(d[4] for d in docs) / n or 1
        df = Counter()
        for d in docs:
            for w in q:
                if w in d[3]:
                    df[w] += 1
        best = {}
        for rel, title, c, cnt, ln in docs:
            s, hit = 0.0, 0
            for w in q:
                f = cnt.get(w, 0)
                if not f:
                    continue
                hit += 1
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                # BM25 с k1=1.2, b=0.75 (2.2 = k1 + 1); 0.25 + 0.75·длина/средняя — поправка на длину куска
                s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * ln / avg))
            if not hit:
                continue
            s *= (hit / len(q)) ** 0.5                      # все слова вопроса нашлись — выше
            if s > best.get(rel, (0,))[0]:
                best[rel] = (s, title, c, hit)
        kind = {f: k for f, k in SOURCES}
        out = [{"path": rel, "title": t, "snippet": re.sub(r"\s+", " ", c).strip()[:500], "score": round(s, 2),
                "hits": h, "kind": "obsidian" if rel.startswith("obsidian:") else kind.get(rel.split("/", 1)[0], "")}
               for rel, (s, t, c, h) in best.items()]
        out.sort(key=lambda x: -x["score"])
        return out[:limit]

    def context(self, question, budget=1600):
        """Подсказка модели перед ответом: только явно относящееся к вопросу (иначе пусто — не сбиваем модель).
        «Явно» — нашлось слово короткого вопроса или хотя бы два слова длинного и счёт не ниже 1.2.
        -> строки «[путь] кусок» общим объёмом около budget знаков."""
        q = list(dict.fromkeys(words(question)))
        if not q:
            return ""
        # «Ум Лиры», ворота внимания (20.11, отчёт №935): «Задача „Создание тестовых материалов B1.7“ — эта задача меня
        # интересует» поднимала старые итоги задач про Obsidian: совпали «задача» и «интересует». Общие слова (задача, файл,
        # папка, работа, интересует…) сами записи не тянут: нужны слова самой темы — и в найденном тоже
        spec = [w for w in q if w not in GENERIC]
        if not spec:
            return ""
        res = self.search(question, limit=4)
        need = 1 if len(spec) <= 2 else 2
        res = [r for r in res if r["score"] >= 1.2 and len(set(spec) & set(words(r["title"] + " " + r["snippet"]))) >= need]
        if not res:
            return ""
        parts, used = [], 0
        for r in res:
            piece = r["snippet"][: max(200, budget - used)]
            # №1117 (26.11): архив разговора — то, что было раньше, а не свежие данные (письма из прошлой проверки почты)
            m = re.match(r"(?:.*/)?Память/Разговоры/(\d{4})-(\d\d)-(\d\d)", r["path"])
            parts.append(f"[{r['path']}] " + (f"(прошлый разговор {m.group(3)}.{m.group(2)} — что было тогда, не свежие данные) " if m else "") + piece)
            used += len(piece)
            if used >= budget:
                break
        return "\n".join(parts)
