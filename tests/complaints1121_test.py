"""Жалобы 21.11 (пакет 11:54).
№944: «не может включить музыку… говорит, что включила радио — но тишина». Окно контекста своей модели мало, действия
отключены, а «включи любую музыку» уходило модели — она «включала» словами. Теперь «любую музыку» и «локальную музыку»
включаем сами, а ответ без действий со словами «включила» заменяется честным.
№941: «Совет ИИ» — прошлые советы не открывались (на Windows .md без программы) и не удалялись: теперь открываются в
«Моих файлах», там же «Удалить».
№938/939: «0 дел сегодня» читалось как «дел на сегодня нет» — подпись «Сделано сегодня» (компьютер и телефон)."""
import os, re, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from engine_music import MusicMixin  # noqa: E402
from engine_mymusic import MINE_RX, MUSIC_CTX_RX  # noqa: E402
from quality import NO_TOOLS_GIVEUP, no_tools_claim  # noqa: E402


class Radio:
    playing = paused = sounding = False
    last = None
    last_at = 0.0
    station = None
    volume = 0.6


class Music:
    def stations(self):
        return [{"name": "Groove Salad", "url": "http://x/1", "tags": "релакс"}, {"name": "Jazz", "url": "http://x/2", "tags": "джаз"}]

    def genres(self):
        return ["джаз", "релакс"]

    def match(self, q):
        return []


class E(MusicMixin):
    def __init__(self):
        self.radio, self.music, self.played, self.said = Radio(), Music(), [], []
        self._music_asked = 0.0

    def _radio_url_cmd(self, text):
        return False

    def _mine_cmd(self, text):
        return False

    def _music_service(self):
        return "radio"

    def _play_station(self, lst, text, fmt):
        self.played.append([x["name"] for x in lst])

    def _say_quick(self, msg, text):
        self.said.append(msg)


for t in ("Включи любую музыку.", "Включи музыку любую.", "включи какую-нибудь музыку", "поставь что-нибудь"):
    e = E()
    r = e._music_cmd(t)
    ok(r is True and e.played and e.played[0][0] == "Groove Salad", f"№944: «{t}» — включаем сами, без модели ({e.played or e.said})")
e = E(); e.radio.last = {"name": "Jazz", "url": "http://x/2", "tags": "джаз"}
e._music_cmd("включи любую музыку")
ok(e.played and e.played[0][0] == "Jazz", f"№944: «любую» — сначала последняя станция ({e.played})")
e = E()
ok(not (e._music_cmd("включи любую песню Мадонны") and e.played), "конкретная песня — не «любая музыка»")

for t in ("включи музыку любую локальную.", "Включи музыку из локальной папки", "включи локальную музыку"):
    ok(bool(MINE_RX.search(t.lower())) and bool(MUSIC_CTX_RX.search(t.lower())), f"№944: «{t}» — своя папка с музыкой")
ok(not MINE_RX.search("запусти программу из локальной папки"), "«запусти программу из локальной папки» — не музыка")

ok(no_tools_claim("включи любую музыку.", "Включила радио «Groove Salad» — спокойная музыка для фона."),
   "№944: без действий «включила радио» — ловим")
ok(not no_tools_claim("как дела?", "Включила бы музыку, да настроения нет."), "не просили действие — не трогаем")
ok(not no_tools_claim("включи музыку", "Сейчас не могу ничего включить — действия недоступны."), "честное «не могу» — не трогаем")
ok("16384" in NO_TOOLS_GIVEUP["ctx"] and "ничего не сделано" in NO_TOOLS_GIVEUP["ctx"], "честный ответ — с причиной и что сделать")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("turn.no_tools =" in src and "no_tools_claim(text, turn.full)" in src, "ответ без действий проверяется на «включила» в конце хода")

co = (ROOT / "ui/studio/council.js").read_text(encoding="utf-8")
ok('openFile(b.dataset.f)' in co and 'core.call("ws_open", { path: b.dataset.f })' not in co,
   "№941: прошлый совет открывается в «Моих файлах» (там «Удалить»), а не отдаётся системе")
for f in ("ui/studio/brain.js", "android/www-src/app/14-sheets.js", "android/assets/www/app.js"):
    s = (ROOT / f).read_text(encoding="utf-8")
    ok("Сделано сегодня" in s and not re.search(r'"дел сегодня"', s), f"№938/939: подпись счётчика — «Сделано сегодня» ({f})")

print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
