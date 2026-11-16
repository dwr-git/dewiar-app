"""Пачка 15.11, 23:27:
№760: своя qwen3-4b в LM Studio с малым окном — запрос с действиями (~17 тыс. токенов) не помещался, Лира отвечала без
     действий и называла курс евро «по памяти», да ещё говорила, что взяла его с cbr.ru. Теперь без действий в подсказке
     прямо: свежие данные (курсы, цены, погода, новости, что по ссылке) не называть и не говорить, что где-то посмотрела;
     совет про окно — 16384 (с действиями нужно 12–16 тыс.), а не 8192.
№759: «Посты в каналы и группы» — добавить канал можно, удалить нельзя → крестик (проверка — pbot_posts_studio1029)."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = srctext.text(ROOT, "core/engine_answer.py")
i = src.index("Модель не справилась с инструментами (%s)")
part = src[i:i + 4000]
ok("Свежие данные — курсы валют" in part and "не говори, что где-то их посмотрела" in part, "№760: без действий — свежих цифр не выдумывать")
ok("16384 или больше" in part, "№760: совет про окно — 16384")
import llm  # noqa: E402
ok("16384" in llm.CTX_TEXT and "8192" not in llm.CTX_TEXT, "№760: текст ошибки окна — тоже 16384")
js = (ROOT / "ui/studio/pbot_posts.js").read_text(encoding="utf-8")
ok('"pbot_chat_del"' in js and "pp-x" in js, "№759: «Убрать» канал или группу")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
