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

# — уроки 21+: окно браузера, переключатель, всплывашка, окно студии с меню, QR-код —
KIT2_CSS = """
.win { position: absolute; left: 640px; top: 140px; width: 760px; padding: 12px 14px 14px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
.win .bar { display: flex; align-items: center; gap: 9px; height: 40px; padding: 0 6px 10px; }
.win .bar i { width: 13px; height: 13px; border-radius: 50%; background: var(--nd); }
.win .bar span { margin-left: 14px; flex: 1; padding: 7px 16px; border-radius: 99px; box-shadow: var(--press); font-size: 17px; font-weight: 800; color: var(--mut); }
.win .bar span b { color: var(--ink); }
.tgl { width: 76px; height: 42px; border-radius: 99px; box-shadow: var(--press); position: relative; flex: none; }
.tgl i { position: absolute; top: 5px; left: 5px; width: 32px; height: 32px; border-radius: 50%; background: #fff; box-shadow: var(--raise-s); }
.tgl.on { background: var(--brand); box-shadow: none; } .tgl.on i { left: 39px; }
.toast { position: absolute; display: flex; align-items: center; gap: 18px; padding: 20px 26px; border-radius: 26px; background: var(--bg); box-shadow: var(--raise); }
.toast > i { flex: none; width: 60px; height: 60px; border-radius: 18px; display: grid; place-items: center; font-size: 32px; font-style: normal; background: rgba(47,179,131,.16); }
.toast small { display: block; font-size: 16px; font-weight: 800; color: var(--mut); } .toast b { display: block; font-size: 22px; font-weight: 800; margin-top: 2px; }
.st { position: absolute; display: grid; grid-template-columns: 250px 1fr; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); overflow: hidden; }
.st nav { padding: 24px 16px; background: rgba(255,255,255,.38); display: flex; flex-direction: column; gap: 3px; }
.st nav .g { margin: 12px 10px 4px; font-size: 13px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--mut); }
.st nav .g:first-child { margin-top: 0; }
.st nav span { padding: 8px 12px; border-radius: 12px; font-size: 18px; font-weight: 700; white-space: nowrap; }
.st nav span.on { color: #fff; background: var(--brand); }
.st .pg { padding: 28px 32px; } .st .pg h3 { font: 700 30px Unbounded; } .st .pg > small { display: block; margin-top: 6px; font-size: 18px; font-weight: 700; color: var(--mut); }
"""


def qr(n=25, px=8, seed=7):
    """Похожий на настоящий QR-код (рисунок, не ссылка): три «глаза» по углам и шум."""
    import random
    r = random.Random(seed)
    cells = set()
    for i in range(n):
        for j in range(n):
            if r.random() < 0.47:
                cells.add((i, j))
    for ox, oy in ((0, 0), (n - 7, 0), (0, n - 7)):
        for i in range(-1, 8):
            for j in range(-1, 8):
                cells.discard((ox + i, oy + j))
        for i in range(7):
            for j in range(7):
                if i in (0, 6) or j in (0, 6) or (2 <= i <= 4 and 2 <= j <= 4):
                    cells.add((ox + i, oy + j))
    rects = "".join(f'<rect x="{i * px}" y="{j * px}" width="{px}" height="{px}"/>' for i, j in sorted(cells))
    return f'<svg viewBox="0 0 {n * px} {n * px}" width="{n * px}" height="{n * px}" fill="#24324a" shape-rendering="crispEdges">{rects}</svg>'
