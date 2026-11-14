"""№705 (пакет 14.11, Роман): «Удалить материал из радара… попала с виду очень важная статья, которая оказалась
кликбейтом». Кнопка «👎 Не то» была, но ни на что не влияла. Теперь отмеченный материал не идёт в бриф, срочное, тренды,
«Галактику» и ответы по теме (всё берётся из Radar.analyzed), а в ленте опускается вниз — чтобы можно было передумать."""
import os, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_insight as EI  # noqa: E402
now = time.time()
A = lambda s: {"signal": s, "summary": "", "tags": [], "type": "news"}
items = [{"id": "bait", "title": "Срочно: всё изменится", "a": A(9), "ts": now - 60, "fb": -1},
         {"id": "ok", "title": "Вышел Dart 3.14", "a": A(5), "ts": now - 120},
         {"id": "new", "title": "Без разбора", "ts": now}]
r = types.SimpleNamespace(st=types.SimpleNamespace(items=lambda: items))
r.item_view = lambda x: EI.Radar.item_view(r, x)
got = [x["id"] for x in EI.Radar.analyzed(r)]
ok(got == ["ok"], f"«Не то» — не в брифе, срочном и трендах: {got}")
feed = [x["id"] for x in EI.Radar.feed(r, sort="signal")]
ok(feed == ["ok", "bait"], f"в ленте — внизу, даже при сильном сигнале: {feed}")
feed = [x["id"] for x in EI.Radar.feed(r)]
ok(feed == ["ok", "bait"], f"и по времени — внизу: {feed}")
items[0]["fb"] = 0
ok([x["id"] for x in EI.Radar.analyzed(r)] == ["bait", "ok"], "передумали — материал вернулся")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
