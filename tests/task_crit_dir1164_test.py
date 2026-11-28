"""№1164 (28.11, компьютер 1.0.90): критерий «contains» с путём к папке (outputs/) принимался, а проверка отвечала
«такого текста в файле нет» — модель правила верный файл outputs/engines.html по кругу, задачу остановили за повтор.
Теперь: папка в contains/number/lines/rows/pages при записи критериев — отказ «укажите конкретный файл»; папка без «/»
при проверке — «это папка, а не файл» и в каком файле текст есть; провал по файлу называет, какой файл прочитан."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import quality_task as Q  # noqa: E402

fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


d = Path(tempfile.mkdtemp())
(d / "outputs").mkdir()
(d / "outputs" / "engines.html").write_text("<html><body><h1>Движки</h1><p>Strata — локальный движок</p></body></html>", encoding="utf-8")
(d / "outputs" / "notes.md").write_text("черновик", encoding="utf-8")

items, errs = Q.norm_criteria([{"check": "contains", "target": "outputs/", "value": "Strata"},
                               {"check": "contains", "target": "outputs/engines.html", "value": "Strata"},
                               {"check": "files", "target": "outputs/", "value": "1"}])
ok(len(errs) == 1 and "папка" in errs[0] and "конкретный файл" in errs[0], f"contains по «outputs/» — отказ с подсказкой: {errs}")
ok([c["check"] for c in items] == ["contains", "files"], "верный contains и «files» по папке — приняты")

res = Q.check_criteria([{"check": "contains", "target": "outputs", "value": "Strata"},
                        {"check": "number", "target": "outputs", "value": "5"},
                        {"check": "contains", "target": "outputs/engines.html", "value": "strata"},
                        {"check": "contains", "target": "outputs/engines.html", "value": "Ollama"}], lambda rel: d / rel)
ok(res[0]["ok"] is False and "папка, а не файл" in res[0]["detail"] and "outputs/engines.html" in res[0]["detail"]
   and "notes.md" not in res[0]["detail"], f"папка без «/» — «это папка» и где текст есть: {res[0]['detail']}")
ok(res[1]["ok"] is False and "папка" in res[1]["detail"], f"number по папке — тоже «папка»: {res[1]['detail']}")
ok(res[2]["ok"] is True, "текст в конкретном файле — найден (регистр не важен)")
ok(res[3]["ok"] is False and "outputs/engines.html" in res[3]["detail"], f"провал называет прочитанный файл: {res[3]['detail']}")
note = Q.criteria_note(res)
ok("set_criteria" in note and "папка" in note, "сообщение модели: исправить критерий, а не файл")

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
