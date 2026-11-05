"""Сторож фоновых задач со стороны разговора (№551, пакет 05.11, ПК 0.82.2, Ollama gemma4:12b по сети): «висит уже 2 часа —
обрати внимание на виджет; я спросил дать права — молчит». В виджете «Анализ кода и БД проекта — запускаю Python» с 22:44:
задача не знала, где проект, и час перебирала свою же папку (план 0 из 11), шаг модели дважды молчал по 10 минут
(«Жду ещё»), а «буксует» не срабатывало — каждый шаг оставлял новый файл _run/шагN.py, и это считалось продвижением.

Здесь — честная пауза с понятной причиной, без правки цикла задачи (tasks.py):
- шаг молчит вдвое дольше порога «не отвечает» (модель — 2 × HANG_SEC, инструмент — 2 × HANG_TOOL_SEC);
- час работы, а по плану ни одного пункта.
Пауза: статус «на паузе», причина — в журнал, голосом и на телефон; поток задачи получает отмену (он сохранит паузу)."""
import time

STALL_SEC = 3600            # столько работает, а по плану 0 пунктов — буксует


def why_pause(t, now=None, hang=600.0, hang_tool=1800.0, stall=STALL_SEC):
    """Пора ли поставить работающую задачу на паузу -> причина для человека или "" (t — tasks.Task)."""
    now = time.monotonic() if now is None else now
    if t.data.get("status") != "running" or t.data.get("parent"):
        return ""
    if not (t.thread is not None and t.thread.is_alive()):
        return ""
    beat, tool = getattr(t, "beat", 0.0) or 0.0, getattr(t, "beat_tool", "") or ""
    limit = 2 * (hang_tool if tool else hang)
    if beat and now - beat > limit:
        mins = round((now - beat) / 60)
        what = f"инструмент «{tool}»" if tool else "модель"
        hint = ("" if tool else " Если модель своя (Ollama, LM Studio) — проверьте, что она запущена и не занята другим, "
                "или выберите в «Мозге» облако Dewiar.")
        return (f"шаг не отвечал {mins} мин ({what}) — поставила на паузу, чтобы задача не висела молча.{hint} "
                "Продолжить — «продолжи задачу» или кнопка в «Задачах».")
    t0 = getattr(t, "run_t0", 0.0) or 0.0
    done, total = (list(t.data.get("progress") or [0, 0]) + [0, 0])[:2]
    if t0 and total and not done and now - t0 > stall:
        mins = round((now - t0) / 60)
        return (f"{mins} мин работы, а по плану не сделано ни одного пункта из {total} — похоже, задача не знает, с чем "
                "работать. Поставила на паузу. Напишите ей, где файлы (например, «дай задаче доступ к папке …»), и скажите "
                "«продолжи задачу».")
    return ""


def pause(host, t, why):
    """Поставить на паузу: журнал, статус, голос и телефон; поток задачи получит отмену и оставит статус «на паузе»."""
    t.journal(f"⏸ {why[:1].upper() + why[1:]}")
    t.data.update(status="paused", activity="", auto_resume=False)
    t.save()
    t.cancel.set()
    t.answer_ev.set()
    tm = getattr(host, "tasks", None)
    if tm is not None and hasattr(tm, "_emit"):
        tm._emit(t)
    host.announce(f"Задача «{t.title}» на паузе: {why}")
    try:
        host.push(f"⏸ Задача на паузе: {t.title}", why[:200])
    except Exception:  # noqa: BLE001 — телефон не обязателен
        pass


def check(host, now=None):
    """Пройти по задачам -> [(id, причина)] поставленных на паузу."""
    tm = getattr(host, "tasks", None)
    if tm is None:
        return []
    try:
        import tasks as T
        hang, hang_tool = T.HANG_SEC, T.HANG_TOOL_SEC
    except Exception:  # noqa: BLE001
        hang, hang_tool = 600.0, 1800.0
    out = []
    for t in list(getattr(tm, "tasks", {}).values()):
        why = why_pause(t, now, hang, hang_tool)
        if why:
            pause(host, t, why)
            out.append((t.id, why))
    return out
