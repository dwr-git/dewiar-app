"""Отчёт №370 (28.10, Linux Mint, компьютер 0.51.0, сам при сбое): «микрофон молчит: нули» (веб-камера C920 через
эхоподавление) — проверка в mic_heal_test (второй раз — напрямую); и «мозг» — qwen2.5-coder:7b: по-русски отвечает плохо,
сбивается на английский («Я не понимаю по-английски») и печатает JSON. Теперь: один раз за запуск — подсказка, какую модель
взять для разговора; обычные модели — без подсказки."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402
notes = []
S = types.SimpleNamespace(get=lambda *k: "lira")
e = types.SimpleNamespace(note=lambda t: notes.append(t), CODER_RX=EA.AnswerMixin.CODER_RX, s=S)
f = lambda prof: EA.AnswerMixin._coder_brain(e, prof)
ok(f({"model": "qwen2.5-coder:7b"}) and "для программирования" in notes[-1] and "qwen2.5:7b" in notes[-1], f"qwen2.5-coder — подсказка: {notes[-1][:90] if notes else ''}")
ok(not f({"model": "qwen2.5-coder:7b"}) and len(notes) == 1, "один раз за запуск")
e2 = types.SimpleNamespace(note=lambda t: notes.append(t), CODER_RX=EA.AnswerMixin.CODER_RX, s=S)
ok(not EA.AnswerMixin._coder_brain(e2, {"model": "qwen2.5:7b"}) and not EA.AnswerMixin._coder_brain(e2, {"model": "llama3.1:8b"})
   and not EA.AnswerMixin._coder_brain(e2, {"model": "gpt-4o"}), "обычные модели — без подсказки")
e3 = types.SimpleNamespace(note=lambda t: notes.append(t), CODER_RX=EA.AnswerMixin.CODER_RX, s=types.SimpleNamespace(get=lambda *k: "agent"))
ok(not EA.AnswerMixin._coder_brain(e3, {"model": "qwen2.5-coder:7b"}), "у Кодера модель для кода — так и задумано, без подсказки")
ok(all(EA.AnswerMixin.CODER_RX.search(m) for m in ("deepseek-coder-v2:16b", "codellama:7b", "starcoder2", "codestral", "devstral")),
   "узнаются и другие модели для кода")
ok("self._coder_brain(prof)" in (ROOT / "core/engine_answer.py").read_text(encoding="utf-8"), "проверка — при первых словах ответа")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
