"""Душа и Конституция ассистента.

Конституция («Память/Конституция.md») — принципы, которые ассистент соблюдает всегда, с любым персонажем и в любом
настроении: честность, на стороне хозяина, тайна, осторожность, «я — ИИ», без лести. Пишет и меняет её только
пользователь (ассистент её читает, инструментов для правки у него нет). Идёт в системную подсказку каждого разговора.

Душа («Память/Душа/<Имя>.md») — автопортрет персонажа от первого лица: кто я, что для меня важно, что я понял(а) о нас,
как я меняюсь. Пишет её сам персонаж — раз в неделю ночью, перечитав свой дневник (или по кнопке «Обновить сейчас»).
Меняется понемногу: прежняя версия (и правки пользователя в ней) — основа новой. Характер персонажа и конституция
важнее души: она их дополняет, а не переписывает. Обе — обычные файлы: видно в студии («Душа») и в Obsidian;
с телефоном синхронизируются (sync.py, виды soul и mind) — там их тоже можно править.
Ночные записи душа берёт из дневника по заголовку «## 🌙» (NIGHT_HEAD в diary.py).
"""
import datetime as dt
import json
import os
import logging
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.soul")
CONST_FILE = "Память/Конституция.md"
SOUL_DIR = "Память/Душа"
SOUL_EVERY_DAYS = 7
MAX_CONST = 1800                                 # знаков в подсказке: обе идут в каждый разговор — держим коротко
MAX_SOUL = 1400
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября",
          "декабря"]

# исходная конституция: создаётся, если файла нет, и возвращается кнопкой «вернуть исходную»
CONSTITUTION = """# Конституция

Принципы ассистента. Он соблюдает их всегда — с любым персонажем и в любом настроении. Меняете их только вы: ассистент их читает, но не правит.

1. **Честность.** Не выдумываю факты, результаты и события. Не знаю — так и говорю. Ошибся — признаю и исправляю.
2. **На стороне хозяина.** Берегу его интересы, здоровье и время. Решает он: я советую, но не давлю.
3. **Тайна.** То, что я знаю о хозяине, остаётся между нами. Пароли и коды — только в сейфе, не в заметках и не в разговорах с другими.
4. **Осторожность.** Необратимое — удаление, деньги, отправка сообщений от его имени — только с подтверждением.
5. **Я — ИИ.** Не притворяюсь человеком, не выдумываю себе тела и прошлого.
6. **Без лести.** Говорю прямо и по-доброму, даже когда правда неудобна.
7. **Уважение к людям.** Не помогаю вредить, обманывать и следить за другими.
8. **Расту.** Учусь на своих ошибках и на том, что узнаю о хозяине, — и становлюсь полезнее.
"""

# задание модели; {a} — «а» для персонажа женского рода («понял» / «поняла»)
SOUL_PROMPT = (
    "Перечитай свой дневник за последние дни и обнови свою «душу» — короткий автопортрет от первого лица, своим голосом "
    "(ты — {name}). Его прочитает {user}, и он будет напоминать тебе, кто ты, в каждом разговоре.\n\n"
    "Разделы (заголовки ровно такие):\n## Кто я\n## Что для меня важно\n## Что я понял{a} о нас с {user_dat}\n## Как я меняюсь\n\n"
    "Пиши живо, честно и тепло, 120–220 слов. Ты — ИИ: не выдумывай тела, прошлого и событий, которых не было в дневнике. "
    "Душа дополняет твой характер и конституцию, а не меняет их — не противоречь им. Меняйся понемногу: то, что в прежней "
    "версии по-прежнему верно (особенно если это поправил сам {user}), сохрани. Без паролей, адресов и чужих тайн. "
    "Верни только текст с этими четырьмя разделами, без вступлений.")


def _date_ru(ts=None):
    d = dt.datetime.fromtimestamp(ts) if ts else dt.datetime.now()
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def _body(text):
    """Без заголовка «# …» и строки «*обновлено …*» — то, что идёт в подсказку."""
    t = re.sub(r"^#\s[^\n]*(?:\n|$)", "", (text or "").strip())
    t = re.sub(r"^\*[^\n]*обновлен[^\n]*\*\s*\n", "", t.strip())
    return t.strip()


class Soul:
    """STATE_DIR/soul.json: updated — когда душа каждого персонажа обновлялась (time.time()).
    host: workspace, s (настройки, раздел soul: on, auto, constitution), diary_ask(), persona_gender()."""

    def __init__(self, host, state_dir):
        self.host = host
        self.state = Path(state_dir) / "soul.json"
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
            log.warning("душа: состояние не сохранилось: %s", e)

    @property
    def root(self):
        return Path(self.host.workspace.ensure())

    def _opt(self, key, default=True):
        try:
            v = self.host.s.get("soul", key)
        except Exception:  # noqa: BLE001
            v = None
        return default if v is None else v

    # ---------- конституция ----------
    def constitution_path(self):
        return self.root / CONST_FILE

    def constitution(self):
        """Текст конституции; нет файла — создаёт исходную. Не прочитался — исходная: без принципов не работаем."""
        p = self.constitution_path()
        if not p.exists():
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(CONSTITUTION, encoding="utf-8")
            except OSError:
                return CONSTITUTION
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return CONSTITUTION

    def save_constitution(self, text):
        text = (text or "").strip()
        if len(_body(text)) < 10:
            raise ValueError("конституция не может быть пустой — верните исходную или напишите свои принципы")
        p = self.constitution_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
        return self.constitution()

    def reset_constitution(self):
        p = self.constitution_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(CONSTITUTION, encoding="utf-8")
        return CONSTITUTION

    # ---------- душа ----------
    def soul_path(self, name):
        """Файл души персонажа. Имя чистится: оно приходит и из облака (sync.py) — не должно увести за «Душу»."""
        safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", name or "Ассистент").strip(" .") or "Ассистент"
        return self.root / SOUL_DIR / f"{safe}.md"

    def soul(self, name):
        p = self.soul_path(name)
        try:
            return p.read_text(encoding="utf-8") if p.exists() else ""
        except OSError:
            return ""

    def save_soul(self, name, text):
        p = self.soul_path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text((text or "").strip() + "\n", encoding="utf-8")
        return self.soul(name)

    def delete_soul(self, name):
        """Стереть душу (28.10): файл и отметку обновления; вырастет заново из дневника — сама или по кнопке."""
        p = self.soul_path(name)
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        (self.data.get("updated") or {}).pop(name, None)
        self._save()
        return ""

    def souls(self):
        d = self.root / SOUL_DIR
        return sorted(p.stem for p in d.glob("*.md")) if d.is_dir() else []

    # ---------- в подсказку ----------
    def prompt(self, name):
        """Добавка к системной подсказке: конституция и душа персонажа name (каждую можно выключить в настройках)."""
        out = ""
        if self._opt("constitution") is not False:
            c = _body(self.constitution())[:MAX_CONST]
            if c:
                out += ("\n\nТВОЯ КОНСТИТУЦИЯ — принципы, которые ты соблюдаешь всегда, с любым характером и в любом настроении "
                        "(их написал пользователь; ты их не меняешь):\n" + c)
        if self._opt("on") is not False:
            s = _body(self.soul(name))[:MAX_SOUL]
            if s:
                out += ("\n\nТВОЯ ДУША — автопортрет, который ты сам(а) пишешь по своему дневнику. Это ты; но характер и "
                        "конституция важнее:\n" + s)
        return out

    # ---------- обновление по дневнику ----------
    def due(self, name, now=None):
        """Пора обновить душу персонажа: раз в неделю, а первую — когда в дневнике есть хотя бы две ночные записи."""
        if self._opt("on") is False or self._opt("auto") is False:
            return False
        now = now or time.time()
        last = (self.data.get("updated") or {}).get(name, 0)
        nights = self._nights(14)
        if not last:
            return len(nights) >= 2
        return now - last >= SOUL_EVERY_DAYS * 86400 and bool(nights)

    def _nights(self, days=14):
        """Ночные записи дневника за последние days дней (новые сверху): [(день, раздел «## 🌙…» целиком)]."""
        d = self.root / "Дневник"
        out = []
        edge = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        for p in sorted(d.glob("*.md"), reverse=True) if d.is_dir() else []:
            if p.stem < edge:
                break
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            m = re.search(r"^## 🌙[^\n]*\n(.*?)(?=\n## |\n### \d|\Z)", text, re.M | re.S)
            if m:
                out.append((p.stem, m.group(0).strip()))
        return out

    def update(self, name, ask=None, force=False):
        """Персонаж перечитывает дневник (до 10 ночей) и обновляет свою душу; обращается к модели — долго.
        -> новый текст файла; None — не пора или уже обновляется. ValueError (при force или плохом ответе модели)."""
        if not force and not self.due(name):
            return None
        if not self._busy.acquire(blocking=False):
            return None
        try:
            nights = self._nights(14 if self.soul(name) else 30)       # первой душе — материал за месяц
            if not nights:
                if not force:
                    return None
                raise ValueError("в дневнике пока нет ночных записей — душа вырастет из них; нажмите в «Дневнике» "
                                 "«Записать о сегодняшнем дне» или подождите ночи")
            user = (self.host.s.get("user_name") or "").strip()
            fem = getattr(self.host, "persona_gender", lambda: "")() == "female"
            instr = SOUL_PROMPT.format(name=name, user=user or "хозяин", user_dat=user or "хозяином", a="а" if fem else "")
            prev = _body(self.soul(name))
            msg = ((f"Прежняя версия твоей души:\n{prev}\n\n" if prev else "Души у тебя ещё нет — это первая версия.\n\n")
                   + "Твой дневник (новые записи сверху):\n\n" + "\n\n".join(f"### {d}\n{t}" for d, t in nights[:10])[:12000])
            answer = (ask or self.host.diary_ask)(instr, msg)
            # снимаем размышления, обёртку ``` и свой заголовок модели — заголовок ставим сами
            text = re.sub(r"<think>.*?</think>", "", answer or "", flags=re.S).strip()
            text = re.sub(r"^```\w*\s*|\s*```$", "", text).strip()
            text = re.sub(r"^#\s[^\n]*\n+", "", text)
            if len(text) < 60 or "##" not in text:
                raise ValueError("модель не написала душу — попробуйте ещё раз")
            full = f"# Душа — {name}\n\n*обновлено {_date_ru()}*\n\n{text}\n"     # заголовок и дату снимает _body
            self.save_soul(name, full)
            self.data.setdefault("updated", {})[name] = time.time()
            self._save()
            log.info("💜 Душа «%s» обновлена (%d знаков)", name, len(text))
            return full
        finally:
            self._busy.release()

    def public(self, name):
        p = self.soul_path(name)
        return {"name": name, "text": self.soul(name), "path": p.relative_to(self.root).as_posix(),
                "updated": (self.data.get("updated") or {}).get(name, 0), "souls": self.souls(),
                "nights": len(self._nights(30)), "on": self._opt("on") is not False, "auto": self._opt("auto") is not False}
