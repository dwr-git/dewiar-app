"""Собирает film.html урока из общих частей серии (как в 07-posts) и своей сцены: python3 mk.py <spec.py> <папка урока>"""
import sys, runpy
D = __file__.rsplit("/", 1)[0] + "/"
R = lambda n: open(D + n, encoding="utf-8").read()
sp = runpy.run_path(sys.argv[1])
POS = {"title": "{ lira: [700, 320, 330, 1], patrik: [1500, 420, 240, 0] }",
       "problem": "{ lira: [330, 470, 280, 0], patrik: [330, 470, 300, 1] }",
       "end": "{ lira: [960, 330, 300, 1], patrik: [330, 470, 300, 0] }"}
DEF = "{ lira: [330, 470, 280, 1], patrik: [330, 470, 300, 0] }"
pos = ",\n".join(f"  {s}: {sp.get('POS', {}).get(s) or POS.get(s) or DEF}" for s in sp["SCENES"])
html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<link rel="stylesheet" href="../../../../ui/assets/fonts.css">
<style>
/* {sp['TITLE']}. Светлый неоморфизм серии. {sp['IDEA']} */
{R('css_base')}{sp['CSS']}
{R('css_tail')}</style></head>
<body><div id="film">
  <div id="bg"></div><div class="blob" id="b1"></div><div class="blob" id="b2"></div>
  <div id="brand"><img src="../../../../ui/assets/logo.png" alt=""><div><b>ИИ Академия Лиры</b><span>{sp['TITLE']}</span></div></div>
  <div class="layer" id="L-title"><div id="plane">{sp['ICON']}</div>
    <div id="t-title"><h1>{sp['H1']}</h1><p>{sp['TAG']}</p></div></div>
{sp['HTML']}
  <div class="layer" id="L-end"><div id="end"><h1>dewiar.pro</h1><p>Бесплатно · Windows, Linux, Android и браузер</p><span class="next">{sp['NEXT']}</span></div></div>

  <div class="seat" id="s-lira" style="--c:var(--lira)"><div class="orb"><canvas id="e-lira" width="600" height="600"></canvas></div><b>Лира</b></div>
  <div class="seat" id="s-patrik" style="--c:var(--patrik)"><div class="orb"><canvas id="e-patrik" width="600" height="600"></canvas></div><b>Патрик</b></div>
  <div id="sub"></div>
</div>
<script>document.write('<script src="' + (new URLSearchParams(location.search).get("tl") || "out/timeline.js") + '"><\\/script>');</script>
<script src="../../../../ui/assets/entities.js"></script>
<script>
{R('js_base')}const POS = {{
{pos},
}};
{R('js_mid')}const type = (txt, k) => txt.slice(0, Math.round(txt.length * clamp(k)));
window.render = function (T, f) {{
  const s = (id) => SC[id];
  $("#b1").style.transform = `translate(${{-150 + 120 * Math.sin(T / 9)}}px, ${{-200 + 80 * Math.cos(T / 11)}}px)`;
  $("#b2").style.transform = `translate(${{1300 + 140 * Math.cos(T / 10)}}px, ${{560 + 90 * Math.sin(T / 8)}}px)`;
  layer("L-title", T, 0.2, s("problem").start);
  vis($("#plane"), out((T - 0.8) / 0.6), 0, .8);
{sp['JS']}
  layer("L-end", T, s("end").start + 0.2, TL.total + 5);
{R('js_seats')}window.__ready = true;
</script>
</body></html>
"""
open(sys.argv[2] + "/film.html", "w", encoding="utf-8").write(html)
print("ok", sys.argv[2])
