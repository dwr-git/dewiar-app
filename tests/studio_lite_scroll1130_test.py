"""№1130 (27.11, CachyOS, NVIDIA, 16 ядер): «проблема при прокрутке и перемещении курсора в окнах приложения — пункт меню
всплывает с сильной задержкой, фризы при вводе; процессор не загружен». Облегчённый вид («Оформление» → «Скорость») для
этого и есть, но «сам» включался только по числу ядер и по кадрам в простое — а в простое кадры быстрые, тяжело при
прокрутке. Теперь замер и при прокрутке: два раза подряд медленно — облегчённый вид; одна заминка, быстрые кадры,
выбранное вручную «выкл.» — нет."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "ui/studio/core.js").read_text(encoding="utf-8")
m = re.search(r"const LITE_SCROLL = .*?\naddEventListener\(\"wheel\", liteScrollProbe, \{ passive: true, capture: true \}\);", src, re.S)
ok(bool(m), "core.js: замер кадров при прокрутке (колесо) — есть")
node = shutil.which("node")
if m and node:
    js = """
const vm = require("vm");
function run(frames, opts) {
  const q = []; const ev = {}; let auto = [];
  const ctx = { LITE: { auto: false }, document: { hidden: false }, liteMode: () => opts.mode || "auto",
    liteAuto: (w) => { auto.push(w); ctx.LITE.auto = true; }, requestAnimationFrame: (f) => q.push(f),
    addEventListener: (n, f) => { ev[n] = f; } };
  vm.createContext(ctx); vm.runInContext(CODE, ctx);
  for (const gaps of frames) {               // один эпизод прокрутки: промежутки между кадрами, мс
    ev.wheel(); ev.wheel();                  // колесо крутят много раз — замер один
    let t = 1000;
    const f0 = q.shift(); if (!f0) continue; f0(t);
    for (const g of gaps) { t += g; const f = q.shift(); if (!f) break; f(t); }
    while (q.length) { t += 16; q.shift()(t); }
  }
  return auto;
}
const fast = Array(80).fill(16), slow = Array(30).fill(70), lag = Array(5).fill(300), hiccup = Array(70).fill(16).concat([400]);
console.log(JSON.stringify({
  slow2: run([slow, slow], {}), slow1: run([slow, fast], {}), fast: run([fast, fast, fast], {}),
  lag2: run([lag, lag], {}), off: run([slow, slow, slow], { mode: "off" }), hic: run([hiccup, hiccup, hiccup], {}),
  alt: run([slow, fast, slow, fast, slow], {}) }));
""".replace("CODE", json.dumps(m.group(0)))
    pr = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    print(pr.stderr[-600:]) if pr.returncode else None
    r = json.loads(pr.stdout)
    ok(r["slow2"] == ["прокрутка рисуется медленно"], f"две прокрутки подряд медленные (кадр 70 мс) — облегчённый вид: {r['slow2']}")
    ok(r["lag2"] == ["прокрутка рисуется медленно"], f"совсем тормозит (кадр 300 мс, меньше 8 кадров) — тоже: {r['lag2']}")
    ok(r["slow1"] == [] and r["alt"] == [], f"одна медленная, потом быстрая — нет: {r['slow1']}, {r['alt']}")
    ok(r["fast"] == [] and r["hic"] == [], f"быстрые кадры и одна заминка за прокрутку — нет: {r['fast']}, {r['hic']}")
    ok(r["off"] == [], "выбрано «выкл.» — не включаем")
elif not node:
    print("⚠️ node нет — поведение не проверено")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
