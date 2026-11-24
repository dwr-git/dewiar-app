"""№980 (23.11, телефон 0.9.85): «Лира — основной персонаж, а напоминания приходят от Патрика». Уведомление подписывается
обликом «кто ставил», а без него — текущим (Faces.java, cur). Текущим становился облик, отданный последним: фото грузится
не сразу, и облик Патрика, дорисованный уже после возврата к Лире, перебивал её. Теперь облик отдаётся, только если
персонаж всё ещё тот же; правка напоминания с компьютера не теряет «кто ставил»."""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "android/www-src/app/05-talk.js").read_text(encoding="utf-8")
i = src.index("function faceFor(p) {"); j = src.index("\n}\n", i) + 3
js = """
let cur = "lira"; const personaBase = () => ({ id: cur }); const saved = [];
const D = { setFace: (id) => saved.push(id) };
let pending = [];
global.document = { createElement: () => ({ getContext: () => ({ save(){}, beginPath(){}, arc(){}, clip(){}, createRadialGradient: () => ({ addColorStop(){} }),
  fillRect(){}, fillText(){}, restore(){}, drawImage(){} }), toDataURL: () => "data:image/png;base64,AAA" }) };
global.Image = class { set src(v) { pending.push(this); } };
""" + src[i:j] + """
faceFor({ id: "patrick", name: "Патрик", avatar: "p.webp" });   // фото Патрика ещё грузится
cur = "lira"; faceFor({ id: "lira", name: "Лира" });             // вернулись к Лире (без фото — сразу)
pending.forEach(im => im.onload && im.onload());                 // фото Патрика догрузилось
console.log(JSON.stringify(saved));
"""
r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
ok(r.returncode == 0 and r.stdout.strip() == '["lira"]', f"дорисованный позже облик Патрика не становится текущим: {r.stdout.strip() or r.stderr[:300]}")
sy = (ROOT / "android/www-src/app/16-sync.js").read_text(encoding="utf-8")
ok("was && was.who ? { who: was.who } : {}" in sy, "правка напоминания с компьютера не теряет, кто его ставил")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
