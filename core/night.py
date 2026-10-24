"""Ночной обход: ассистент сам разбирает прожитые сутки — что ломалось, что не доделано, — чинит, что может,
и честно рассказывает об остальном.

Когда: раз в сутки, ночью (после diary.hour, по умолчанию 3:00) или утром, как только компьютер проснулся, когда
с ассистентом 10 минут не говорили (engine_music._diary_loop — рядом с ночной записью дневника). Выключается
настройкой night.on = false.

Что делает:
  • журнал сбоев за сутки (incidents.jsonl, health.py) — по видам и подписям: сколько раз и что именно;
  • задачи, которые остановились с ошибкой, — запускает ещё раз, один раз на задачу (не ошибку программы, не
    «зациклилась», не «модель не умеет действия» — там повтор не поможет); результат придёт как обычно;
  • дела по расписанию, которые не удались (last_ok = False), — отмечает;
  • задачи, которые ждут ответа человека, — напомнит утром;
  • проверяет, отвечает ли модель («Мозг») и сколько места на диске.
Итог — в STATE_DIR/night.json: короткая фраза на утро (morning_note: утренняя сводка и «вернулись к компьютеру» её
говорят, один раз), полный разбор — файлом «Здоровье/ГГГГ-ММ-ДД.md» в папке ассистента. Осталось нерешённое и
человек разрешил отчёты при сбое (report.auto) — технический отчёт разработчику (report_send, вид «auto»: подписи
сбоев, версии, что пробовал; без разговоров, файлов и ключей — тексты сбоев уже прошли health.clean_text).
host: tasks, reminders, workspace, s, incidents(), active_llm (s), report_send(), emit()."""
import datetime as dt
import json
import logging
import re
import shutil
import time
from collections import Counter

from settings import STATE_DIR

log = logging.getLogger("dewiar.night")
KIND_RU = {"error": "ошибки программы", "task": "задачи", "job": "дела по расписанию", "llm": "связь с моделью"}
NO_RETRY = ("bug", "loop", "idle_model", "access")
# Не ошибки программы, а состояние модели и сети человека: заряд, ключ, связь, занятость, окно контекста.
# №235 (24.10): «Дело по расписанию не удалось: Заряд Dewiar Облака закончился» уходило разработчику отчётом «при сбое».
SETUP_RX = re.compile(r"заряд|талер|баланс|credits|quota|402|max_tokens|ключ|401|403|forbidden|подключ|connect|интернет|сеть|network|"
                      r"resolve|много людей|занят|перегруж|429|503|busy|не ответил вовремя|timed? ?out|таймаут|окна контекста|context|"
                      r"не запущена|не отвечает|недоступ", re.I)


def setup_issue(text):
    """Сбой из-за модели, связи или заряда человека (а не из-за программы)?"""
    return bool(SETUP_RX.search(str(text or "")))


def _sig(text, n=160):
    """Подпись сбоя: цифры — #, переносы и пробелы — одним пробелом, длинное — по слову с «…»."""
    s = re.sub(r"\s+", " ", re.sub(r"\d+", "#", str(text or ""))).strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return (cut if len(cut) > n // 2 else s[:n]).rstrip(" ,.:;—-") + "…"


class NightWatch:
    def __init__(self, host):
        self.host = host
        self.path = STATE_DIR / "night.json"
        self.data = self._load()

    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            log.info("🌙 обход: не сохранился: %s", e)

    # ---------- когда ----------

    def due(self, now=None, hour=3):
        """Пора ли: после hour часов, сегодня ещё не ходили; компьютер включили днём, а ночью не ходили — тоже пора."""
        now = now or dt.datetime.now()
        if self.host.s.get("night", "on") is False:
            return False
        return self.data.get("last_day") != now.date().isoformat() and now.hour >= hour

    # ---------- утром ----------

    def morning_note(self, take=True):
        """Фраза на утро о ночи («За сутки были сбои связи с моделью; ночью: задача «…» запущена снова»), один раз."""
        note = self.data.get("morning_note") or ""
        if note and take:
            self.data["morning_note"] = ""
            self._save()
        return note

    # ---------- обход ----------

    def run(self, now=None):
        """Сделать обход. -> {day, problems, repaired, left, note, path}."""
        now = now or dt.datetime.now()
        since = float(self.data.get("last_ts") or (time.time() - 86400))
        h = self.host
        problems, repaired, left, setup_left = [], [], [], set()

        # 1) журнал сбоев за сутки
        inc = [r for r in (h.incidents(since) if hasattr(h, "incidents") else []) if r.get("ts", 0) > since]
        by = Counter((r.get("kind") or "error", _sig(r.get("text"))) for r in inc)
        for (kind, sig), n in by.most_common(12):
            problems.append({"kind": kind, "text": sig, "n": n})

        # 2) задачи с ошибкой — ещё раз, один раз на задачу
        tm = getattr(h, "tasks", None)
        for t in list(getattr(tm, "tasks", {}).values()) if tm else []:
            try:
                d = t.data
                if d.get("parent"):
                    continue
                if d.get("status") == "failed" and str(d.get("failed_at") or d.get("updated") or "") >= dt.datetime.fromtimestamp(since).isoformat(timespec="seconds"):
                    if d.get("fail_kind") in NO_RETRY or d.get("night_retry"):
                        hint = (" — ей не хватает прав на файл или папку: дайте доступ (или выберите другую папку) и запустите "
                                "задачу снова" if d.get("fail_kind") == "access" else "")
                        left.append(f"Задача «{t.title}» остановилась: {str(d.get('error') or '')[:160]}{hint}")
                        continue
                    d["night_retry"] = True
                    t.save()
                    tm.tell(t.id, "Ночной обход: в прошлый раз задача остановилась с ошибкой («" + str(d.get("error") or "")[:200]
                            + "»). Попробуй ещё раз довести её до конца — сверься с планом и блокнотом; если мешает то же самое, "
                              "обойди это или честно напиши в итоге, что не получилось и почему.")
                    repaired.append(f"задача «{t.title}» запущена снова")
                elif d.get("status") == "waiting" and d.get("question"):
                    left.append(f"Задача «{t.title}» ждёт ответа: {str(d.get('question'))[:160]}")
            except Exception as e:  # noqa: BLE001
                log.info("🌙 обход, задача: %s", e)

        # 3) дела по расписанию, которые не удались
        try:
            for it in getattr(getattr(h, "reminders", None), "items", []) or []:
                if it.get("kind") == "job" and it.get("last_ok") is False:
                    err = str(it.get('last_error') or '')
                    left.append(f"Дело по расписанию «{str(it.get('text') or '')[:80]}» не удалось: {_sig(err, 120)}")
                    if setup_issue(err):
                        setup_left.add(left[-1])
        except Exception:  # noqa: BLE001
            pass

        # 4) модель отвечает?
        brain = self._check_brain()
        if brain is False:
            left.append("Модель («Мозг») сейчас не отвечает — проверьте сервер модели или интернет.")
        elif brain and any(p["kind"] == "llm" or "Модель" in p["text"] for p in problems):
            repaired.append("связь с моделью проверена — сейчас отвечает")

        # 5) место на диске
        try:
            free = shutil.disk_usage(str(h.workspace.ensure())).free / 2 ** 30
            if free < 1.0:
                left.append(f"На диске осталось {free:.1f} ГБ — задачам и голосу может не хватить места.")
        except Exception:  # noqa: BLE001
            pass

        note = self._note(problems, repaired, left)
        path = self._write(now, problems, repaired, left)
        self.data.update(last_day=now.date().isoformat(), last_ts=time.time(), morning_note=note,
                         last={"problems": problems, "repaired": repaired, "left": left, "path": path})
        self._save()
        # разработчику — только то, что может быть ошибкой программы: сбои модели и сервера (ключ, страна, баланс, сеть)
        # — это настройки человека, их он видит утром сам (пакет 22.10, №193: «сбоев 4, не решено 0» — все про модель)
        # задачи (застряла, не хватило окна) — поведение и настройки модели; «модель не отвечает» в «не решено» — тоже настройки
        # (пакет 23.10, №204, №209, №210)
        # дело по расписанию, не удавшееся из-за заряда, ключа или сети, — тоже настройки человека (№235)
        ours = sum(p["n"] for p in problems if p.get("kind") != "task" and not str(p["text"]).startswith("Модель")
                   and not (p.get("kind") == "job" and setup_issue(p["text"])))
        left_ours = [x for x in left if not x.startswith("Модель") and x not in setup_left]
        sent = self._report(now, problems, repaired, left) if left_ours or ours >= 3 else None
        log.info("🌙 Ночной обход: сбоев %d, починила %d, осталось %d%s", sum(p["n"] for p in problems), len(repaired), len(left),
                 f", отчёт №{sent}" if sent else "")
        return {"day": now.date().isoformat(), "problems": problems, "repaired": repaired, "left": left, "note": note,
                "path": path, "report": sent}

    def _check_brain(self):
        """True — модель ответила, False — нет, None — модели нет или проверять нечем."""
        prof = self.host.s.active_llm() if hasattr(self.host.s, "active_llm") else None
        if not prof:
            return None
        try:
            from llm import stream_chat
            out = "".join(stream_chat(dict(prof, max_tokens=8, timeout=40), "Ответь одним словом.", [{"role": "user", "content": "Скажи: да"}]))
            return bool(out.strip())
        except Exception as e:  # noqa: BLE001
            log.info("🌙 обход: модель не ответила: %s", e)
            return False

    @staticmethod
    def _note(problems, repaired, left):
        """Одна-две фразы на утро; ночь прошла спокойно — пусто (молчим)."""
        n = sum(p["n"] for p in problems)
        if not (repaired or left) and n < 3:
            return ""
        parts = []
        if n:
            kinds = Counter()
            for p in problems:
                kinds[p["kind"]] += p["n"]
            parts.append("за сутки были сбои (" + ", ".join(f"{KIND_RU.get(k, k)} — {v}" for k, v in kinds.most_common(3)) + ")")
        if repaired:
            parts.append("ночью: " + "; ".join(repaired[:3]))
        if left:
            parts.append("ещё не решено: " + left[0][0].lower() + left[0][1:] + (f" (и ещё {len(left) - 1})" if len(left) > 1 else ""))
        s = "; ".join(parts)
        return s[0].upper() + s[1:] + "."

    def _write(self, now, problems, repaired, left):
        """Разбор — файлом «Здоровье/ГГГГ-ММ-ДД.md» в папке ассистента. -> путь или ""."""
        try:
            d = self.host.workspace.ensure() / "Здоровье"
            d.mkdir(parents=True, exist_ok=True)
            f = d / f"{now:%Y-%m-%d}.md"
            body = [f"# Ночной обход {now:%d.%m.%Y}", ""]
            body += ["## Сбои за сутки", ""] + ([f"- {KIND_RU.get(p['kind'], p['kind'])}: {p['text']} — {p['n']} раз" for p in problems] or ["- не было"])
            body += ["", "## Что сделано ночью", ""] + ([f"- {x}" for x in repaired] or ["- ничего не понадобилось"])
            body += ["", "## Что осталось", ""] + ([f"- {x}" for x in left] or ["- всё в порядке"])
            f.write_text("\n".join(body) + "\n", encoding="utf-8")
            return str(f)
        except Exception as e:  # noqa: BLE001
            log.info("🌙 обход: разбор не записан: %s", e)
            return ""

    def _report(self, now, problems, repaired, left):
        """Отчёт разработчику — только с согласия (report.auto) и только технический. -> номер или None."""
        h = self.host
        if h.s.get("report", "auto") is not True or not hasattr(h, "report_send"):
            return None
        note = ("Ночной разбор " + f"{now:%d.%m.%Y}" + "\n\nСбои за сутки:\n"
                + "\n".join(f"- [{p['kind']}] {p['text']} — {p['n']}" for p in problems)
                + "\n\nСделано ночью:\n" + "\n".join(f"- {re.sub(r'«[^»]*»', '«…»', x)}" for x in repaired)
                + "\n\nНе решено:\n" + "\n".join(f"- {re.sub(r'«[^»]*»', '«…»', x)}" for x in left))   # без названий задач и дел
        summary = f"Ночной разбор: сбоев {sum(p['n'] for p in problems)}, не решено {len(left)}" + (
            f" — {problems[0]['text'][:120]}" if problems else "")
        try:
            r = h.report_send(note=note[:2000], auto=True, summary=summary, plain=True)
            return r.get("id")
        except Exception as e:  # noqa: BLE001
            log.info("🌙 обход: отчёт не ушёл: %s", e)
            return None
