"""Общие детали сцен третьего сезона (уроки 16+): облачко фразы, карточка, телефон, окно студии, строки списка.
Сцену урока собирают из них — меньше повторов, один вид у всей серии."""
KIT_CSS = """
#plane svg { stroke: var(--accent); }
.say { position: absolute; left: 620px; top: 190px; max-width: 760px; padding: 22px 28px; border-radius: 28px 28px 8px 28px; background: var(--brand); color: #fff; font-size: 28px; font-weight: 700; line-height: 1.35; }
.card { position: absolute; left: 620px; top: 200px; width: 820px; padding: 32px 38px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); }
.card h3 { font: 700 32px Unbounded; margin-bottom: 8px; } .card > small { display: block; font-size: 18px; font-weight: 800; color: var(--mut); margin-bottom: 8px; }
.row { display: flex; align-items: center; gap: 16px; padding: 16px 18px; border-radius: 18px; box-shadow: var(--raise-s); margin-top: 14px; font-size: 23px; font-weight: 700; }
.row i { font-style: normal; font-size: 30px; } .row em { margin-left: auto; white-space: nowrap; font-style: normal; font-size: 18px; font-weight: 800; padding: 9px 15px; border-radius: 12px; color: var(--accent); background: rgba(69,96,234,.1); }
.row em.ok { color: #1e7d5b; background: rgba(47,179,131,.15); } .row em.warn { color: #b04a5c; background: rgba(176,74,92,.1); }
.chips { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; } .chips span { padding: 14px 20px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 22px; font-weight: 700; }
.chips span.on { color: #fff; background: var(--brand); box-shadow: none; }
.phone { position: absolute; left: 1420px; top: 130px; width: 400px; height: 720px; border-radius: 58px; background: var(--bg); box-shadow: var(--raise); padding: 20px; }
.phone .scr { width: 100%; height: 100%; border-radius: 42px; background: #eef2f8; padding: 30px 22px; overflow: hidden; }
.phone h5 { font: 700 25px Unbounded; margin-bottom: 16px; }
.bub { padding: 14px 18px; border-radius: 20px; background: #fff; font-size: 19px; font-weight: 600; line-height: 1.4; margin-top: 12px; max-width: 86%; }
.bub.me { margin-left: auto; color: #fff; background: var(--brand); }
.big { font: 600 64px Unbounded; color: var(--accent); }
.mess { position: absolute; left: 620px; top: 200px; width: 1180px; height: 560px; }
.mess span { position: absolute; padding: 16px 22px; border-radius: 20px; background: var(--bg); box-shadow: var(--raise-s); font-size: 24px; font-weight: 800; white-space: nowrap; }
.mess b { position: absolute; left: 300px; top: 470px; font: 600 40px Unbounded; color: #b04a5c; }
"""
# разбросанные «бумажки» сцены «проблема»: (текст, x, y)
SPOTS = [(0, 0), (420, 50), (800, 10), (120, 170), (560, 200), (30, 320), (480, 330), (860, 300)]


def mess(items, punch):
    return '<div class="mess" id="mess">' + "".join(f'<span style="left:{x}px;top:{y}px">{t}</span>' for t, (x, y) in zip(items, SPOTS)) + f"<b>{punch}</b></div>"


MESS_JS = """
  scene($("#mess"), T, s("problem").start + 0.3, s(ORDER[2]).start);
  [...$("#mess").querySelectorAll("span")].forEach((c, i) => { const k = out((T - s("problem").start - 0.5 - i * 0.3) / 0.4);
    c.style.opacity = k; c.style.transform = `translate(${Math.sin(T * 0.9 + i) * 8}px, ${(1 - k) * 20 + Math.cos(T * 0.7 + i) * 6}px) rotate(${Math.sin(i * 1.7) * 4}deg)`; });
  vis($("#mess b"), out((T - s("problem").start - 3.2) / 0.4), 12);
"""
