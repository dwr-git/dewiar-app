"""Пакет здоровья 25.10, №251: слабая модель (qwen2.5:7b в Ollama) посреди русского ответа уходит в китайский
(«…похвало тебя за работу 今天的任务已经完成了…»). Иероглифы из ответа убираем — в потоке и в конце; но если человек сам
пишет иероглифами или просит китайский, японский, корейский — оставляем."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import llm  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def run(chunks, no_cjk=True):
    c = llm._Collector(); c.no_cjk = no_cjk
    return "".join(c.feed_obj({"choices": [{"delta": {"content": x}}]}) for x in chunks) + c.flush()


out = run(["Понял. Похвалю тебя за работу ", "今天的任务", "已经完成了，没有待办事项。", " Хорошего дня!"])
ok("今" not in out and "，" not in out and "Похвалю тебя за работу" in out and "Хорошего дня!" in out, f"иероглифы убраны, русское осталось: {out!r}")
ok(run(["Привет по-китайски — 你好 (нихао)."], no_cjk=False) == "Привет по-китайски — 你好 (нихао).", "просили китайский — иероглифы на месте")
ok(llm.wants_cjk([{"role": "user", "content": "Как будет «спасибо» по-японски?"}]), "вопрос про японский — иероглифы нужны")
ok(llm.wants_cjk([{"role": "user", "content": "что значит 谢谢"}]), "человек сам написал иероглифы — нужны")
ok(not llm.wants_cjk([{"role": "user", "content": "какие у меня дела"}]), "обычный вопрос — иероглифы прочь")
ok(llm.wants_cjk([{"role": "user", "content": [{"type": "text", "text": "переведи на китайский"}]}]), "вопрос с картинкой (список частей) — тоже понимаем")
src = (ROOT / "core/llm.py").read_text(encoding="utf-8")
ok("col.no_cjk = not wants_cjk(messages)" in src, "включено для каждого ответа модели")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
