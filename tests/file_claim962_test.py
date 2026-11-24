"""№962 (22.11): «при работе с файлами она говорит, что сделала, а по факту никаких изменений» — модель прочитала файл
(действие было, поэтому проверка «сказала, а не сделала» молчала) и ответила «исправила». Просили изменить, а вызваны только
справочные действия — переспрос с честным путём (doc_replace точечно или «сама не меняю» + большая задача)."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
import quality as Q  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


fix = Q.saved_claim("Исправь в файле план.md вторую строку на «купить хлеб»", "Готово, исправила вторую строку.", ("read_file",))
ok(fix.startswith("ПРОВЕРКА") and "только посмотрел" in fix and "doc_replace" in fix and "start_task" in fix,
   "просили исправить, только прочитала, сказала «исправила» — переспрос с честным путём")
ok(not Q.saved_claim("Что у меня в файле план.md", "Вы записали там три пункта: хлеб, молоко, сыр.", ("read_file",)),
   "просто спросили про файл (без просьбы менять) — пересказ «вы записали» не ловим")
ok(not Q.saved_claim("Замени в договор.docx Иванов на Петров", "Готово, заменила: 3 раза.", ("doc_find", "doc_replace")),
   "правка была (doc_replace) — молчим")
ok(not Q.saved_claim("Перепиши заметку про отпуск", "Переписала заметку.", ("find_notes", "save_note")),
   "нашла и сохранила — молчим")
ok(Q.saved_claim("Хотя нет, давай заложим 70 тысяч", "Хорошо, меняю.", ()).startswith("ПРОВЕРКА")
   and "ничего не вызвал" in Q.saved_claim("Хотя нет, давай заложим 70 тысяч", "Хорошо, меняю.", ()),
   "без действий — как раньше")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
