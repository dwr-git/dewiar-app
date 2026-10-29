"""«Задачи на часы» (29.10): в карточке задачи — сколько идёт (часы, а не «идёт 185 мин») и сколько примерно осталось —
по среднему времени на пункт плана, только когда пунктов сделано хотя бы два (иначе оценка врёт)."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
JS = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const a = src.indexOf('function tDur'), b = src.indexOf('let tOpenedFor');
eval(src.slice(a, b).replace('function tDur', 'globalThis.tDur = function').replace('function tEta', 'globalThis.tEta = function'));
console.log(JSON.stringify([tDur(5), tDur(65), tDur(120), tEta({progress: [2, 7]}, 40), tEta({progress: [1, 7]}, 40), tEta({progress: [7, 7]}, 90), tEta({progress: [6, 8]}, 200)]));
"""
r = subprocess.run(["node", "-e", JS, str(ROOT / "ui/studio/tasks.js")], capture_output=True, text=True)
got = json.loads(r.stdout or "[]")
want = ["5 мин", "1 ч 5 мин", "2 ч", " · осталось ≈ 1 ч 45 мин", "", "", " · осталось ≈ 1 ч 15 мин"]
print(("✅ " if got == want else "❌ ") + f"идёт — часами, осталось ≈ — после двух пунктов плана: {got} {r.stderr[-200:]}")
sys.exit(0 if got == want else 1)
