"""№428 (30.10): «файлы в Документы добавляются через раз или вообще не добавляются». Своя папка («Документы» →
«Добавить папку») сверялась раз в 20 минут: файл, положенный в неё проводником, Лира не видела — «ничего не нашлось
(файлов в поиске: 0)». Теперь своя папка сверяется перед поиском (давно не сверялась — сразу) и раз в 2 минуты."""
import os, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import knowledge as K  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
own = tmp / "Документы_Dewiar"; own.mkdir()
(own / "старый.txt").write_text("Договор аренды склада на Ленина, 5: оплата до десятого числа.", encoding="utf-8")
ws = types = None
import types as T  # noqa: E402
ws = T.SimpleNamespace(ensure=lambda: tmp / "ws", root=tmp / "ws")
(tmp / "ws").mkdir()
kn = K.Knowledge(ws, tmp / "idx.json", folders=lambda: [str(own)])
threading.Thread(target=kn.watch, daemon=True).start()
time.sleep(1.0)
ok(any("старый" in r["path"] for r in kn.search("аренда склада")), "своя папка прочитана при запуске")
kn.folders_t -= 60                                            # прошла минута — проводником положили новый файл
(own / "Борея.txt").write_text("Компания «Борея»: поставка утеплителя, менеджер Ирина, скидка 7 процентов.", encoding="utf-8")
t0 = time.time()
hits = kn.search("Борея утеплитель")
ok(any("Борея" in r["path"] for r in hits) and time.time() - t0 < 5, f"новый файл в своей папке — найден сразу, без 20 минут ожидания: {[r['path'] for r in hits]}")
t0 = time.time(); kn.search("аренда")
ok(time.time() - t0 < 1.0, "только что сверяли — поиск не ждёт")
ok(K.Knowledge.watch.__defaults__ == (120,), "фоновая сверка — раз в 2 минуты, а не в 20")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
