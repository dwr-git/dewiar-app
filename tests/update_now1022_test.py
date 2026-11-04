"""22.10, владелец: написал Лире «Обновись» — «Сейчас посмотрю, как обновляется Dewiar. Поняла, делаю — узнаю…», и всё.
Теперь «обновись», «проверь обновления», «есть новая версия?» — сразу, без модели: проверка сайта сейчас же и итог одной
фразой (новая версия скачана — плашка в виджете; обновлений нет; сайт не ответил). Похожие просьбы о другом («обнови
список дел») — как раньше, модели."""
import os, sys, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402
from engine_base import UPDATE_RX  # noqa: E402

for t in ("Обновись", "Лира, обновись!", "проверь обновления", "есть новая версия?", "обнови программу", "Обновись, пожалуйста"):
    ok(bool(UPDATE_RX.match(t)), f"«{t}» — проверка обновлений без модели")
for t in ("обнови список дел", "обнови заметку про отпуск", "обновись и расскажи анекдот", "как обновляется Windows?"):
    ok(not UPDATE_RX.match(t), f"«{t}» — не про обновление Dewiar, решает модель")


class Up:
    def __init__(self, info=None, err=""):
        self.info, self.err = info, err
    def check(self, **kw):
        return self.info
    def public(self):
        return {"current": "0.39.1", "error": self.err}


def run(up, text="Обновись"):
    said = []
    me = types.SimpleNamespace(updater=up, _say_quick=lambda msg, heard, via=None: said.append(msg))
    r = EA.AnswerMixin._direct_update(me, text) if hasattr(EA, "AnswerMixin") else None
    for _ in range(50):
        if said:
            break
        time.sleep(0.02)
    return r, said


mix = next(v for v in vars(EA).values() if isinstance(v, type) and "_direct_update" in vars(v))
EA.AnswerMixin = mix
r, said = run(Up({"version": "0.39.2", "path": "/tmp/x.deb"}))
ok(r is True and said and "0.39.2" in said[0] and "уже скачана" in said[0] and "плашку" in said[0], f"есть новая — версия и что нажать: {said}")
r, said = run(Up({"version": "0.39.2", "downloading": True}))
ok(r is True and said and "0.39.2" in said[0] and "Скачиваю" in said[0] and "плашку" in said[0], f"новая ещё качается — так и сказано: {said}")
r, said = run(Up(None))
ok(said and "последняя версия 0.39.1" in said[0], f"обновлений нет — так и сказано: {said}")
r, said = run(Up(None, "timeout"))
ok(said and "не получилось проверить" in said[0], f"сайт не ответил — честно: {said}")
r, said = run(Up(None), "обнови список дел")
ok(r is False and not said, "«обнови список дел» — не перехватываем")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
