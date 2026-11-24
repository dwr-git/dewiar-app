"""№997 (24.11): Радар, «сильнейшее за неделю» — новость от 17 ноября (прошлая неделя) и не самая сильная. Сила — целое
0–10, десяток много, и при равной силе брались самые старые. Теперь: сильнее — выше, при равной силе — свежее, одно и то же
событие (заголовки совпадают больше чем наполовину) — один раз."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "ui/studio/insight.js").read_text(encoding="utf-8")
i = src.index("    const words = (t) =>"); j = src.index("\n", src.index("    for (const p of [...P].sort(", i))
js = """const P = [
 {id: "a", x: 0.4, s: 10, title: "Спецоперация: главные события 17 ноября"},
 {id: "b", x: 6.8, s: 10, title: "ВС РФ нанесли массированный ракетный удар по энергетике"},
 {id: "c", x: 6.5, s: 10, title: "Массированный ракетный удар по энергетике: подробности"},
 {id: "d", x: 5.0, s: 10, title: "Иранское ПВО сбило два американских дрона"},
 {id: "e", x: 6.9, s: 8, title: "Новость слабее"}];
""" + src[i:j] + "\nconsole.log(JSON.stringify(top.map(p => p.id)));"
f = Path(tempfile.mkdtemp()) / "t.js"; f.write_text(js, encoding="utf-8")
r = subprocess.run(["node", str(f)], capture_output=True, text=True, timeout=30)
got = json.loads(r.stdout or "[]") if r.returncode == 0 else r.stderr[:300]
ok(got == ["b", "d", "a"], f"равная сила — свежее выше, повтор события — один раз, слабее — не в тройке: {got}")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
