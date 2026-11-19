"""Замер поиска по книгам (отзыв 19.11, «цифровой двойник» автора по 12 книгам): доля вопросов, на которые нужный
отрывок попадает в выдачу (из limit лучших). Вопросы — data/exam/book_questions.json: [вид, вопрос, книга, что должно
быть в отрывке]; вид f — словами книги, p — пересказом. Книги — папка .txt (замер 19.11: 12 произведений русской
классики, ~4 млн знаков: Капитанская дочка, Пиковая дама, Метель, Станционный смотритель, Гробовщик, Мёртвые души,
Записки сумасшедшего, Княжна Мери, Бэла, Мастер и Маргарита, Анна Каренина, Записки охотника).
    python3 tools/book_eval.py <папка с книгами> [limit=6] [-v]
19.11: было 16/36, Snowball-основы + служебные слова вопроса + книги персонажа без предела «2 отрывка из файла» — 22/36."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.setdefault("DEWIAR_CONFIG_DIR", str(tmp / "cfg"))
os.environ.setdefault("DEWIAR_STATE_DIR", str(tmp / "st"))
import knowledge as K  # noqa: E402


class WS:
    root = tmp / "ws"

    def ensure(self):
        self.root.mkdir(exist_ok=True)
        return self.root


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    corpus, limit = Path(args[0]).resolve(), int(args[1]) if len(args) > 1 else 6
    kn = K.Knowledge(WS(), tmp / "kn.json", extra=lambda: [str(corpus)])
    t0 = time.time()
    kn.refresh_folders()
    print(f"индекс: {time.time() - t0:.1f} с, отрывков {sum(len(e.get('chunks') or []) for e in kn.index.values())}")
    qs = json.loads((ROOT / "data/exam/book_questions.json").read_text(encoding="utf-8"))
    got, miss = {"f": [0, 0], "p": [0, 0]}, []
    for kind, q, book, gold in qs:
        r = kn.search(q, limit, within=[str(corpus)])
        hit = any(book.lower() in Path(x["path"]).name.lower() and gold in x["text"].lower().replace("ё", "е") for x in r)
        got[kind][0] += hit
        got[kind][1] += 1
        if not hit:
            miss.append(q)
    print(f"словами книги {got['f'][0]}/{got['f'][1]}, пересказом {got['p'][0]}/{got['p'][1]}, "
          f"всего {got['f'][0] + got['p'][0]}/{len(qs)}")
    if "-v" in sys.argv:
        for m in miss:
            print("  ✗", m)


if __name__ == "__main__":
    main()
