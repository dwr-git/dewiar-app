"""Пачка 16.11, 00:40:
№766: «перестал открываться персонаж для редактирования» — персонажа «Стратум» записали в обход студии (Кодер): без голоса
     и с обликом «stratum», которого нет. Студия: редактор падал на ed.voice.piper («reading 'piper'»), облик — ошибка каждый
     кадр и пустой круг. Теперь ядро при чтении подставляет голос, облик и слово запуска по умолчанию, студия — тоже.
№767: «Музыка» — окно уже: «Пауза» сплющивалась в овал, громкость вылезала за карточку."""
import json, os, re, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
d = tempfile.mkdtemp()
os.environ.update(DEWIAR_CONFIG_DIR=d + "/cfg", DEWIAR_STATE_DIR=d + "/st")
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from settings import PERSONAS_DIR  # noqa: E402
PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
(PERSONAS_DIR / "stratum.json").write_text(json.dumps({"name": "СТРАТУМ", "style": "stratum", "wake": "стратум, страт",
                                                       "character": "x" * 50000}, ensure_ascii=False), encoding="utf-8")
import personas as P  # noqa: E402
st = P.Personas()
p = st.get("stratum")
ok(isinstance(p.get("voice"), dict) and p["voice"].get("piper"), f"без голоса — голос по умолчанию: {p.get('voice')}")
ok(p.get("style") == "particles", f"облик «stratum» — «частицы»: {p.get('style')}")
ok(p.get("wake") == ["стратум", "страт"], f"слово запуска строкой — списком: {p.get('wake')}")

js = (ROOT / "ui/studio/personas.js").read_text(encoding="utf-8")
i = js.index("function openEditor(p)")
ok("ed.voice = Object.assign(" in js[i:i + 900], "редактор: нет голоса — не падает")
ent = (ROOT / "ui/assets/entities.js").read_text(encoding="utf-8")
ok("(STYLES[this.style] || STYLES.particles)" in ent, "облик, которого нет, — «частицы», а не ошибка каждый кадр")
css = (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8")
ok(".mm-ctl button { flex: none; }" in css and re.search(r"\.mm-ctl \{[^}]*flex-wrap: wrap", css), "№767: кнопки плеера не сжимаются, громкость переносится")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
