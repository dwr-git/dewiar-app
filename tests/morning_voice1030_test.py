"""Урок 12 «Утро с Лирой» (30.10) говорит людям: «Скажите „Расскажи утро“». Голосом это уходило модели как обычный вопрос —
без данных «Утра» (погода, дела, сотрудники, клиенты, почта), и она могла сочинить. Теперь фраза — та же сводка, что
кнопка «Расскажи утро» на «Главной»: ход модели с поручением _job_prompt({"brief": True}) (данные — morning.gather).
Посторонние «расскажи про утро в деревне» — не перехватываются. И сценарий экзамена morning_tell — на компьютере."""
import json, os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402

yes = ["Расскажи утро", "Лира, расскажи утро!", "расскажи мне утро", "Давай утреннюю сводку", "расскажи сводку дня",
       "Сделай мне сводку на сегодня", "ну расскажи утро", "Озвучь утреннюю сводку."]
no = ["расскажи про утро в деревне", "расскажи утро стрелецкой казни", "какое утро", "расскажи сказку", "доброе утро",
      "расскажи что-нибудь про утро", "сводка погоды"]
ok(all(EA.MORNING_RX.match(t) for t in yes), f"«Расскажи утро» и похожее — сводка: {[t for t in yes if not EA.MORNING_RX.match(t)]}")
ok(not any(EA.MORNING_RX.match(t) for t in no), f"постороннее — не перехватываем: {[t for t in no if EA.MORNING_RX.match(t)]}")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
i = src.index("MORNING_RX.match(text)")
ok('self.ask(self._job_prompt({"brief": True}), via=via, raw=True, shown=text)' in src[i:i + 400] and "not K" in src[i - 80:i],
   "голосом — та же сводка, что кнопка (поручение brief с данными «Утра»), в детском режиме — нет")
mus = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok('if item.get("brief"):' in mus and "self._brief_context()" in mus, "поручение brief берёт данные «Утра» (_brief_context)")
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ok("morning_tell" in sc and sc["morning_tell"]["steps"][-1]["say"] == "Расскажи утро", "экзамен компьютера: сценарий «Расскажи утро»")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
