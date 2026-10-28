"""Моя музыка (27.10, идея владельца: «папка с музыкой — Лира как диджей»; «главное — с разъяснением для пользователей
и в разделе общих умений, где радио»). Теги без сторонних библиотек (mp3, flac, opus) и имена файлов; подборки по
настроению; фразы голосом; очередь доигрывает сама (radio.on_end); ведущий — не каждый трек; студия и «Что я умею»."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FF = shutil.which("ffmpeg")
tmp = Path(tempfile.mkdtemp())
mus = tmp / "Музыка"
(mus / "Кино" / "1989 - Звезда по имени Солнце").mkdir(parents=True)
(mus / "Разное").mkdir()


def mk(path, secs=1.0, meta=(), extra=()):
    subprocess.run([FF, "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=f=440:d={secs}", *extra,
                    *sum([["-metadata", f"{k}={v}"] for k, v in meta], []), str(path)], check=True)


mk(mus / "Кино" / "1989 - Звезда по имени Солнце" / "01 трек.mp3", meta=[("title", "Звезда по имени Солнце"), ("artist", "Кино"),
   ("album", "Звезда по имени Солнце"), ("date", "1989"), ("genre", "Русский рок")], extra=["-id3v2_version", "3"])
mk(mus / "Кино" / "1989 - Звезда по имени Солнце" / "02 трек.mp3", meta=[("title", "Невесёлая песня"), ("artist", "Кино"),
   ("album", "Звезда по имени Солнце"), ("date", "1989"), ("genre", "Русский рок")], extra=["-id3v2_version", "4"])
mk(mus / "Разное" / "clair.flac", meta=[("TITLE", "Clair de lune"), ("ARTIST", "Debussy"), ("GENRE", "Classical")])
mk(mus / "Разное" / "quiet.opus", meta=[("title", "Тишина"), ("artist", "Эмбиент Бэнд"), ("genre", "Ambient")], extra=["-c:a", "libopus"])
mk(mus / "Разное" / "Сплин - Выхода нет.mp3")
# старый русский mp3: теги в cp1251, а записаны как latin-1
raw = (mus / "Разное" / "cp.mp3")
mk(raw)
title = "Город".encode("cp1251")
frame = b"TIT2" + (len(title) + 1).to_bytes(4, "big") + b"\0\0" + b"\0" + title
art = "Танцы Минус".encode("cp1251")
frame += b"TPE1" + (len(art) + 1).to_bytes(4, "big") + b"\0\0" + b"\0" + art
size = len(frame)
hdr = b"ID3\x03\x00\x00" + bytes([(size >> 21) & 127, (size >> 14) & 127, (size >> 7) & 127, size & 127])
body = raw.read_bytes()
if body[:3] == b"ID3":
    n = (body[6] << 21) | (body[7] << 14) | (body[8] << 7) | body[9]
    body = body[10 + n:]
raw.write_bytes(hdr + frame + body)

import mymusic as MM  # noqa: E402
lib = MM.Library(lambda: str(mus), tmp / "idx.json")
n = lib.scan()
by = {t["title"]: t for t in lib.tracks}
ok(n == 6, f"шесть треков в папке и подпапках: {sorted(by)}")
k = by.get("Звезда по имени Солнце", {})
ok(k.get("artist") == "Кино" and k.get("album") == "Звезда по имени Солнце" and k.get("year") == "1989" and k.get("genre") == "Русский рок",
   "ID3v2.3: название, исполнитель, альбом, год, жанр")
ok(by.get("Невесёлая песня", {}).get("artist") == "Кино", "ID3v2.4 тоже читается")
ok(by.get("Clair de lune", {}).get("genre") == "Classical" and by.get("Тишина", {}).get("artist") == "Эмбиент Бэнд", "FLAC и Opus — теги Vorbis")
ok(by.get("Выхода нет", {}).get("artist") == "Сплин", "без тегов — из имени «Исполнитель - Песня»")
ok(by.get("Город", {}).get("artist") == "Танцы Минус", f"старые теги cp1251 — по-русски, а не «Ãîðîä»: {sorted(by)}")
ok(lib.stats() == {"tracks": 6, "artists": 5, "genres": 3, "folder": str(mus)}, f"счётчики для студии: {lib.stats()}")
lib2 = MM.Library(lambda: str(mus), tmp / "idx.json")
ok(len(lib2.tracks) == 6, "индекс сохранён: при следующем запуске треки сразу, без чтения папки")

m = lambda q, f=(): (lambda r: (r[1], sorted(t["title"] for t in r[0])))(lib.match(q, list(f)))  # noqa: E731
ok(m("кино") == ("Кино", ["Звезда по имени Солнце", "Невесёлая песня"]), "исполнитель")
ok(m("спокойное")[1] == ["Clair de lune", "Тишина"] and m("для работы")[1] == ["Clair de lune", "Тишина"], "настроение: спокойное и для работы — по жанрам")
ok("Звезда по имени Солнце" in m("бодрое")[1], "бодрое — рок")
ok(m("выхода нет") == ("Выхода нет", ["Выхода нет"]), "название песни")
ok(m("любимое", [by["Тишина"]["path"]]) == ("любимое", ["Тишина"]), "любимое")
ok(m("джаз") == ("", []), "чего нет в папке — пусто (тогда радио)")


# ---------- фразы голосом: ядро без звука ----------
class S:
    def __init__(self, folder):
        self.d = {"music": {"folder": folder, "favs": [], "dj_talk": True, "dj_every": 3}}

    def get(self, *ks, default=None):
        v = self.d
        for k in ks:
            v = v.get(k) if isinstance(v, dict) else None
        return default if v is None else v

    def update(self, patch):
        for k, v in patch.items():
            self.d.setdefault(k, {}).update(v)


class FakeRadio:
    def __init__(self):
        self.station, self.paused, self.played, self.on_end = None, None, [], None

    def play(self, st):
        self.station, self.paused = st, None
        self.played.append(st)

    def pause(self):
        self.paused, self.station = self.station, None

    def resume(self):
        self.play(self.paused)

    def stop(self):
        self.station = None

    def status(self):
        return {"playing": bool(self.station)}


from engine_mymusic import MyMusicMixin  # noqa: E402


class E(MyMusicMixin):
    def __init__(self, folder):
        self.s, self.radio, self.said, self.dj_said = S(folder), FakeRadio(), [], []
        self.turn, self.state, self.stopping = None, "idle", threading.Event()
        self._mine_init(tmp / "state")
        self._dj_say = lambda t: self.dj_said.append(t)
        time.sleep(0.3)

    def _say_quick(self, msg, said, **kw):
        self.said.append(msg)

    def emit(self, *a, **k):
        pass

    def _g(self, t):
        return t

    def note(self, t):
        pass


e = E(str(mus))
for _ in range(50):
    if e.mylib.tracks:
        break
    time.sleep(0.1)
ok(e._mine_cmd("Лира, поставь мою музыку") and e.radio.station and e.radio.station.get("_mine"), "«поставь мою музыку» — играет трек из папки")
ok(e.said and any(w in e.said[-1] for w in ("Включаю", "поехали", "Ставлю")) and "»" in e.said[-1] and "не нашёл" not in e.said[-1]
   and e.dj.what == "", f"ведущий называет первый трек: {e.said[-1:]}")
cur = e.dj.current()
ok(e._mine_cmd("Что сейчас играет?") and cur["title"] in e.said[-1] and e.said[-1].startswith("Сейчас играет"), f"«что играет» — трек: {e.said[-1]}")
ok(e._mine_cmd("эту в любимое") and cur["path"] in e.s.get("music", "favs"), "«эту в любимое» — запомнил")
ok(e._mine_cmd("дальше") and e.dj.current() is not cur and e.radio.station["_track"] is e.dj.current(), "«дальше» — следующий трек")
ok(e._mine_cmd("включи что-нибудь спокойное из моей музыки") and e.dj.what == "спокойное" and e.dj.current()["title"] in ("Clair de lune", "Тишина"),
   "«что-нибудь спокойное из моей музыки» — подборка")
ok(e._mine_cmd("поставь Кино") and e.dj.current()["artist"] == "Кино", "«поставь Кино» — исполнитель из папки, без «моей»")
ok(not e._mine_cmd("поставь джаз") and not e._mine_cmd("включи радио") and not e._mine_cmd("включи свет в комнате"),
   "джаз, радио и прочее — не сюда (радио и модель как раньше)")
ok(not e._mine_cmd("включи кино") and not e._mine_cmd("включи выхода нет"), "«включи кино» — может быть фильм; название песни без «моей» — не сюда")
ok(e._mine_cmd("включи песни Кино") and e.dj.current()["artist"] == "Кино", "«включи песни Кино» — музыка")
ok(e._mine_cmd("включи моё любимое") and e.dj.what == "любимое" and e.dj.current()["path"] == cur["path"], "«включи моё любимое»")
ok(e._mine_cmd("убери эту песню из любимого") and not e.s.get("music", "favs"), "«убери из любимого»")
# очередь доигрывает сама; ведущий — раз в три трека
e._mine_cmd("поставь мою музыку")
e.dj_said.clear()
for _ in range(6):
    e._mine_ended(e.radio.station)
ok(len(e.radio.played) >= 7 and len(e.dj_said) == 2, f"трек доиграл — следующий сам; ведущий говорит раз в три трека: {e.dj_said}")
e.s.update({"music": {"dj_talk": False}})
e.dj_said.clear()
for _ in range(3):
    e._mine_ended(e.radio.station)
ok(not e.dj_said, "«Говорить между треками» выключено — молчит")
st = e.mine_command("mm_status", {})
ok(st["stats"]["tracks"] == 6 and st["now"] and "Кино" in st["artists"], "студия: что играет, счётчики, исполнители")
ok(len(e.mine_command("mm_list", {"what": "спокойное"})) == 2, "студия: список подборки")
e.mine_command("mm_ctl", {"act": "pause"})
ok(e.radio.station is None and e.mine_command("mm_status", {})["paused"], "студия: пауза")
e.mine_command("mm_ctl", {"act": "play"})
ok(e.radio.station and e.radio.station.get("_mine"), "студия: играть дальше")

e2 = E("")
ok(e2._mine_cmd("поставь мою музыку") and "не выбрана" in e2.said[-1], "папка не выбрана — подскажет, где её указать")
ok(not e2._mine_cmd("включи радио"), "без папки радио — как раньше")

# ---------- настоящий проигрыватель: доиграл — on_end ----------
from radio import Radio  # noqa: E402


class P:
    device = ""

    def start(self, rate, channels=1):
        pass

    def write(self, b):
        return True

    def stop(self):
        pass


ended = []
r = Radio(P, lambda: FF)
r.on_end = lambda st: ended.append(st)
long = tmp / "long.mp3"
mk(long, secs=4)
r.play({"name": "t", "url": str(long), "_mine": True})
for _ in range(100):
    if ended:
        break
    time.sleep(0.1)
ok(ended and ended[0]["url"] == str(long), "радио-проигрыватель: трек доиграл — зовёт следующий (on_end)")
ended.clear()
r.play({"name": "t", "url": str(long), "_mine": True})
time.sleep(0.5)
r.stop()
time.sleep(1.0)
ok(not ended, "«стоп» — не «доиграл»: следующий сам не включается")

# ---------- объяснения: «Что я умею», справка, студия ----------
T = json.loads((ROOT / "data/tricks.json").read_text(encoding="utf-8"))
snd = next(g for g in T["groups"] if g.get("id") == "sound")
says = [x["say"] for x in snd["items"]]
ok("Поставь мою музыку" in says and "Что сейчас играет?" in says and says.index("Поставь мою музыку") > says.index("Включи радио"),
   "«Что я умею» → «Радио, музыка и звук»: своя музыка рядом с радио")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
help_js = (ROOT / "ui/assets/help.js").read_text(encoding="utf-8")
ok('data-p="music"' in html and 'id="p-music"' in html and "studio/mymusic.js" in html and "music: {" in help_js and "Как попросить" in html,
   "студия: раздел «Музыка» с подсказкой «?» и «Как попросить»")
shutil.rmtree(tmp, ignore_errors=True)
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
