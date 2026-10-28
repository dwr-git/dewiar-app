"""№380 (28.10): «зачем-то включается радио, которого я не просил» — «можно это как-то поправить или проверить» включило
Radio Swiss Pop: «можно» считалось командой «включи», а «поправить» начинается на «поп». «Можно / давай / хочу» — команда
музыки, только если дальше видна музыка; жанр — по основе с коротким окончанием. Ollama, стоящая не в Programs, — найдена."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import music  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


for t in ("можно это как то поправить или проверить", "давай проверим", "хочу понять, почему медленно", "можно попробовать ещё раз",
          "давай поправим настройки", "можно уточнить"):
    ok(music.parse(t) is None, f"не музыка: «{t}»")
for t, q in (("можно джаз", "джаз"), ("хочу русское радио", "русское радио"), ("включи попсу", "попсу"), ("давай что-нибудь спокойное", "что-нибудь спокойное"),
             ("включи джазовую музыку", "джазовую музыку"), ("можно поп", "поп")):
    r = music.parse(t)
    ok(r and r["op"] == "play" and r["query"] == q, f"музыка: «{t}» → {r}")
ok(music.genre_tag("поправить") == "" and music.genre_tag("попсу") == "pop" and music.genre_tag("роковое") == "rock" and music.genre_tag("рокировка") == "",
   "жанр — по основе с коротким окончанием: «поправить», «рокировка» — не жанры")
src = (ROOT / "core/llm.py").read_text(encoding="utf-8")
ok('("ProgramFiles", "Ollama")' in src, "Ollama ищется и в Program Files, и в scoop")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
