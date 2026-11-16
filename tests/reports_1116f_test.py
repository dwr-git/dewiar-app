"""Владелец 16.11, 19:23: подошёл к компьютеру — «С возвращением, Миша! Скоро в 21:00 напомню про итог дня. Хорошо, напомню
сегодня в 21:00: Итог дня. Напоминание при этом не поставлено — скажите ещё раз…». Итог дня в 21:00 — дело по расписанию,
оно стоит; проверка «пообещала напомнить» попросила поставить ещё одно и дописала, что напоминания нет. Теперь: время из
ответа уже стоит — правда; приветствие — не просьба, такую проверку на нём не делаем.
№798 (пакет 19:38, шлюз Vercel AI Gateway): «user message must have content» — пустое сообщение человека в истории, и ни
один вопрос больше не проходил. Пустое сообщение человека уходит серверу как «…»."""
import os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
import srctext  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import quality as Q  # noqa: E402
a = "С возвращением, Миша! Скоро в 21:00 напомню про итог дня."
ok(Q.remind_claim(a, set(), {"21:00"}) == "", "«в 21:00 напомню» — дело на 21:00 уже стоит: правда, не переспрашиваем")
ok(Q.remind_claim(a, set(), set()) != "", "напоминания на это время нет — как раньше, просим поставить")
ok(Q.remind_claim("Напомню тебе в 9:30 и в 21:00", set(), {"21:00"}) != "", "одно из времён не стоит — просим поставить")
ok(Q.remind_claim("Напомню тебе завтра", set(), {"21:00"}) != "", "без времени — как раньше")

import answer_prompt as AP  # noqa: E402
at = (datetime.now() + timedelta(hours=2)).replace(second=0, microsecond=0)
me = SimpleNamespace(reminders=SimpleNamespace(items=[{"at": at.isoformat(timespec="minutes"), "text": "Итог дня", "kind": "job"},
                                                      {"at": (at + timedelta(days=3)).isoformat(timespec="minutes"), "text": "далеко"},
                                                      {"at": at.isoformat(timespec="minutes"), "text": "пауза", "paused": True}]))
got = AP.PromptMixin._reminder_times(me)
ok(got == {at.strftime("%H:%M")}, f"времена стоящих дел на сутки: {got}")
ok(AP.PromptMixin._reminder_times(SimpleNamespace()) == set(), "без «Дел» — пусто, без падения")
src = srctext.text(ROOT, "core/engine_answer.py")
ok('not getattr(turn, "greet", False)' in src and "remind_claim(step_text, called, self._reminder_times())" in src,
   "приветствие «С возвращением» — без проверки «пообещала напомнить»")

import llm  # noqa: E402
r = llm._clean_messages([{"role": "user", "content": ""}, {"role": "assistant", "content": None}, {"role": "user", "content": "привет"},
                         {"role": "user", "content": "  "}, {"role": "tool", "content": "", "tool_call_id": "1"}])
ok([m["content"] for m in r] == ["…", "", "привет", "…", ""], f"№798: пустое сообщение человека — «…», остальное как было: {r}")
lsrc = srctext.text(ROOT, "core/llm.py")
ok("hist = _clean_messages(flat_messages(messages)" in lsrc, "и в истории «текстом» (без ролей инструментов) — тоже")

print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
