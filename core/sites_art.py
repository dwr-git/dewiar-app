"""Узоры вместо фото (sites_render.py): SVG-картинки по теме и зерну — пока человек не дал свои фото; карта."""

import math
import sites_kit as K

from sites_style import mix


# ---------- узоры вместо фото ----------


def _rand(seed):
    x = (abs(hash(seed)) if not isinstance(seed, int) else seed) % 2147483647 or 7

    def r():
        nonlocal x
        x = (x * 48271) % 2147483647
        return x / 2147483647
    return r


def _seed(s):
    h = 0
    for ch in str(s):
        h = (h * 131 + ord(ch)) % 2147483647
    return h or 11


def art_svg(kind, pal, seed="a", w=800, h=1000, mark=""):
    """Декоративная композиция вместо фото — в цветах темы, своя для каждого шаблона; seed меняет расклад."""
    r = _rand(_seed(seed))
    bg, a1, a2, ink, sf = pal["surface"], pal["accent"], pal["accent2"], pal["ink"], pal["bg"]
    ln = mix(pal["surface"], pal["ink"], .14)
    o = [f'<svg class="art" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">',
         f'<rect width="{w}" height="{h}" fill="{bg}"/>']
    if kind == "beans":
        o.append(f'<circle cx="{w * (.55 + r() * .2):.0f}" cy="{h * (.35 + r() * .2):.0f}" r="{min(w, h) * .42:.0f}" fill="{mix(bg, a1, .16)}"/>')
        for i in range(9):
            cx, cy, rot = w * r(), h * r(), r() * 180
            s = min(w, h) * (.08 + r() * .07)
            col = [a1, ink, a2][i % 3]
            o.append(f'<g transform="translate({cx:.0f} {cy:.0f}) rotate({rot:.0f})"><ellipse rx="{s:.0f}" ry="{s * .68:.0f}" fill="{col}"/>'
                     f'<path d="M{-s * .8:.0f} 0 C{-s * .3:.0f} {-s * .28:.0f} {s * .3:.0f} {s * .28:.0f} {s * .8:.0f} 0" stroke="{bg}" stroke-width="{s * .09:.1f}" fill="none" stroke-linecap="round"/></g>')
    elif kind == "arches":
        cols = [a1, a2, mix(bg, a1, .35), sf, a1]
        n, cx = 5, w * (.5 + (r() - .5) * .2)
        for i in range(n):
            rw = w * (.46 - i * .075)
            top = h * (.18 + i * .07)
            o.append(f'<path d="M{cx - rw:.0f} {h} V{top + rw:.0f} A{rw:.0f} {rw:.0f} 0 0 1 {cx + rw:.0f} {top + rw:.0f} V{h} Z" fill="{cols[i % len(cols)]}"/>')
        o.append(f'<circle cx="{w * (.15 + r() * .2):.0f}" cy="{h * .12:.0f}" r="{w * .05:.0f}" fill="{a2}"/>')
    elif kind == "frames":
        o.append(f'<rect x="{w * .14:.0f}" y="{h * .12:.0f}" width="{w * .62:.0f}" height="{h * .62:.0f}" fill="{mix(bg, a1, .55)}"/>')
        for i in range(4):
            d = 26 + i * 30
            o.append(f'<rect x="{w * .14 + d:.0f}" y="{h * .12 + d:.0f}" width="{w * .62:.0f}" height="{h * .62:.0f}" fill="none" stroke="{ink}" stroke-opacity="{.5 - i * .1:.2f}" stroke-width="1.5"/>')
        o.append(f'<rect x="{w * .5:.0f}" y="{h * .58:.0f}" width="{w * .34:.0f}" height="{h * .28:.0f}" fill="{a2}"/>')
    elif kind == "dots":
        step = max(w, h) / 18
        dots = "".join(f'<circle cx="{x * step:.0f}" cy="{y * step:.0f}" r="3" fill="{ln}"/>' for x in range(19) for y in range(int(h / step) + 2))
        o.append(dots)
        o.append(f'<circle cx="{w * .62:.0f}" cy="{h * .42:.0f}" r="{w * .3:.0f}" fill="{a1}"/>')
        o.append(f'<path d="M0 {h} V{h * .68:.0f} A{w * .32:.0f} {w * .32:.0f} 0 0 1 {w * .32:.0f} {h} Z" fill="{a2}"/>')
        o.append(f'<rect x="{w * .14:.0f}" y="{h * .16:.0f}" width="{w * .18:.0f}" height="{w * .18:.0f}" rx="{w * .04:.0f}" fill="{ink}" transform="rotate(12 {w * .23:.0f} {h * .16 + w * .09:.0f})"/>')
    elif kind == "blocks":
        n = 4
        cw, chh = w / n, h / 5
        cols = [a1, a2, ink, sf, mix(bg, a1, .3)]
        for x in range(n):
            for y in range(5):
                v = r()
                if v < .42:
                    continue
                col = cols[int(r() * len(cols))]
                if v > .82:
                    o.append(f'<circle cx="{x * cw + cw / 2:.0f}" cy="{y * chh + chh / 2:.0f}" r="{min(cw, chh) * .42:.0f}" fill="{col}"/>')
                elif v > .62:
                    o.append(f'<path d="M{x * cw:.0f} {(y + 1) * chh:.0f} A{cw:.0f} {chh:.0f} 0 0 1 {(x + 1) * cw:.0f} {y * chh:.0f} V{(y + 1) * chh:.0f}Z" fill="{col}"/>')
                else:
                    o.append(f'<rect x="{x * cw + 6:.0f}" y="{y * chh + 6:.0f}" width="{cw - 12:.0f}" height="{chh - 12:.0f}" fill="{col}"/>')
    elif kind == "rings":
        cx, cy = w * (.6 + r() * .15), h * (.4 + r() * .2)
        for i in range(9, 0, -1):
            o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{min(w, h) * .085 * i:.0f}" fill="{mix(bg, a1, .07 * (10 - i)) if i % 2 else bg}"/>')
        o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{min(w, h) * .085:.0f}" fill="{a1}"/>')
        o.append(f'<circle cx="{w * .2:.0f}" cy="{h * .8:.0f}" r="{min(w, h) * .07:.0f}" fill="{a2}"/>')
    elif kind == "stripes":
        sw = max(w, h) / 9
        for i in range(-4, 14):
            col = [a1, a2, sf][i % 3]
            o.append(f'<path d="M{i * sw:.0f} {h} L{i * sw + h * .7:.0f} 0 H{i * sw + h * .7 + sw * .55:.0f} L{i * sw + sw * .55:.0f} {h}Z" fill="{col}"/>')
        o.append(f'<circle cx="{w * .5:.0f}" cy="{h * .5:.0f}" r="{min(w, h) * .26:.0f}" fill="{sf}"/>')
    elif kind == "grid":
        step = 40
        g = "".join(f'<path d="M{x} 0V{h}" stroke="{ln}"/>' for x in range(0, w + 1, step)) + "".join(f'<path d="M0 {y}H{w}" stroke="{ln}"/>' for y in range(0, h + 1, step))
        o.append(g)
        for i in range(3):
            x, y = w * (.12 + i * .1), h * (.14 + i * .24)
            o.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w * .62:.0f}" height="{h * .17:.0f}" rx="18" fill="{sf}" stroke="{ln}" stroke-width="2"/>'
                     f'<circle cx="{x + 46:.0f}" cy="{y + h * .085:.0f}" r="20" fill="{[a1, a2, ink][i]}"/>'
                     f'<rect x="{x + 84:.0f}" y="{y + h * .06:.0f}" width="{w * .3:.0f}" height="12" rx="6" fill="{mix(sf, ink, .25)}"/>'
                     f'<rect x="{x + 84:.0f}" y="{y + h * .095:.0f}" width="{w * .18:.0f}" height="10" rx="5" fill="{mix(sf, ink, .12)}"/>')
    elif kind == "pulse":                              # фитнес: косые полосы скорости и линия пульса
        sw = w / 7
        for i in range(-3, 9):
            col = [a1, mix(bg, a1, .28), mix(bg, ink, .1)][i % 3]
            if r() < .35:
                continue
            o.append(f'<path d="M{i * sw:.0f} {h} L{i * sw + h * .5:.0f} 0 H{i * sw + h * .5 + sw * .42:.0f} L{i * sw + sw * .42:.0f} {h}Z" fill="{col}"/>')
        y0, pts = h * (.5 + (r() - .5) * .16), []
        x = -10
        while x < w + 20:
            pts.append(f"{x:.0f},{y0:.0f}")
            if r() < .5:
                pk = h * (.14 + r() * .12)
                pts += [f"{x + 22:.0f},{y0:.0f}", f"{x + 36:.0f},{y0 - pk:.0f}", f"{x + 54:.0f},{y0 + pk * .7:.0f}", f"{x + 68:.0f},{y0:.0f}"]
                x += 68
            x += w * .1
        o.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{ink}" stroke-width="{max(w, h) * .016:.0f}" stroke-linejoin="round" stroke-linecap="round"/>')
        o.append(f'<circle cx="{w * .82:.0f}" cy="{h * .2:.0f}" r="{min(w, h) * .07:.0f}" fill="{a2}"/>')
    elif kind == "pebbles":                            # стоматология: мягкая галька и блики
        for i in range(7):
            cx, cy = w * (.1 + r() * .8), h * (.1 + r() * .8)
            rx = min(w, h) * (.14 + r() * .16)
            col = [mix(bg, a1, .22), a2, sf, mix(bg, a1, .45)][i % 4]
            o.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{rx * (.62 + r() * .25):.0f}" fill="{col}" transform="rotate({r() * 180:.0f} {cx:.0f} {cy:.0f})"/>')
        for i in range(3):
            cx, cy, s = w * (.2 + r() * .6), h * (.15 + r() * .7), min(w, h) * (.03 + r() * .03)
            o.append(f'<path d="M{cx:.0f} {cy - s * 2:.0f} C{cx + s * .3:.0f} {cy - s * .3:.0f} {cx + s * .3:.0f} {cy - s * .3:.0f} {cx + s * 2:.0f} {cy:.0f} '
                     f'C{cx + s * .3:.0f} {cy + s * .3:.0f} {cx + s * .3:.0f} {cy + s * .3:.0f} {cx:.0f} {cy + s * 2:.0f} C{cx - s * .3:.0f} {cy + s * .3:.0f} {cx - s * .3:.0f} {cy + s * .3:.0f} {cx - s * 2:.0f} {cy:.0f} '
                     f'C{cx - s * .3:.0f} {cy - s * .3:.0f} {cx - s * .3:.0f} {cy - s * .3:.0f} {cx:.0f} {cy - s * 2:.0f}Z" fill="{sf}"/>')
    elif kind == "confetti":                           # детский центр: конфетти — кружки, треугольники, волнистые ленты
        cols = [a1, a2, ink, mix(a1, a2, .5), mix(bg, a1, .5)]
        u = min(w, h)
        o.append(f'<circle cx="{w * (.55 + r() * .2):.0f}" cy="{h * (.45 + r() * .1):.0f}" r="{u * .3:.0f}" fill="{mix(bg, a2, .3)}"/>')
        for i in range(16):
            cx, cy, s, col, rot = w * r(), h * r(), u * (.03 + r() * .04), cols[i % len(cols)], r() * 360
            k = i % 4
            if k == 0:
                o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{s:.0f}" fill="{col}"/>')
            elif k == 1:
                o.append(f'<path d="M0 {-s * 1.2:.0f} L{s * 1.1:.0f} {s * .8:.0f} L{-s * 1.1:.0f} {s * .8:.0f}Z" fill="{col}" transform="translate({cx:.0f} {cy:.0f}) rotate({rot:.0f})"/>')
            elif k == 2:
                o.append(f'<path d="M{-s * 2.4:.0f} 0 q{s * .6:.0f} {-s:.0f} {s * 1.2:.0f} 0 t{s * 1.2:.0f} 0 t{s * 1.2:.0f} 0 t{s * 1.2:.0f} 0" fill="none" stroke="{col}" '
                         f'stroke-width="{s * .55:.0f}" stroke-linecap="round" transform="translate({cx:.0f} {cy:.0f}) rotate({rot:.0f})"/>')
            else:
                o.append(f'<rect x="{-s:.0f}" y="{-s * .45:.0f}" width="{s * 2:.0f}" height="{s * .9:.0f}" rx="{s * .45:.0f}" fill="{col}" transform="translate({cx:.0f} {cy:.0f}) rotate({rot:.0f})"/>')
    elif kind == "hazard":                             # автосервис: сигнальная лента, шестерня и болты
        u = min(w, h)
        g = "".join(f'<path d="M{x} 0V{h}" stroke="{ln}"/>' for x in range(0, w + 1, 50)) + "".join(f'<path d="M0 {y}H{w}" stroke="{ln}"/>' for y in range(0, h + 1, 50))
        o.append(g)
        cx, cy, R1 = w * (.58 + r() * .1), h * .42, u * .3
        teeth = "".join(f'<rect x="{-u * .045:.0f}" y="{-R1 - u * .07:.0f}" width="{u * .09:.0f}" height="{u * .12:.0f}" rx="4" fill="{mix(bg, ink, .22)}" transform="rotate({k * 30})"/>' for k in range(12))
        o.append(f'<g transform="translate({cx:.0f} {cy:.0f})">{teeth}<circle r="{R1:.0f}" fill="{mix(bg, ink, .22)}"/><circle r="{R1 * .42:.0f}" fill="{bg}"/>'
                 f'<circle r="{R1 * .18:.0f}" fill="{a1}"/></g>')
        by, bh = h * .74, h * .12
        cid = f"hz{_seed(f'{seed}-{w}-{h}') % 99991}"                # своё имя на каждый узор: на странице их несколько
        o.append(f'<clipPath id="{cid}"><rect x="0" y="{by:.0f}" width="{w}" height="{bh:.0f}"/></clipPath><g clip-path="url(#{cid})"><rect x="0" y="{by:.0f}" width="{w}" height="{bh:.0f}" fill="{ink}"/>'
                 + "".join(f'<path d="M{x:.0f} {by + bh:.0f} L{x + bh:.0f} {by:.0f} H{x + bh * 1.9:.0f} L{x + bh * .9:.0f} {by + bh:.0f}Z" fill="{a1}"/>' for x in range(-int(bh * 2), w + 1, int(bh * 1.8))) + "</g>")
        for i in range(4):
            bx, byy = [(.1, .1), (.9, .1), (.1, .6), (.9, .6)][i]
            o.append(f'<circle cx="{w * bx:.0f}" cy="{h * byy:.0f}" r="{u * .025:.0f}" fill="none" stroke="{mix(bg, ink, .4)}" stroke-width="3"/>')
    elif kind == "botanic":                            # свадьбы: тонкое золотое кольцо и ветви
        u = min(w, h)
        cx, cy = w * (.5 + (r() - .5) * .16), h * .5                # по центру: кадр 5:4 и 16:9 срезает верх и низ
        o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{u * .27:.0f}" fill="{sf}"/>')
        o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{u * .3:.0f}" fill="none" stroke="{a2}" stroke-width="{u * .006 + 1:.1f}"/>')
        for side, (bx, by, ang) in enumerate(((cx - u * .36, h * .5 + u * .3, -52 - r() * 10), (cx + u * .36, h * .5 + u * .26, -128 + r() * 10),
                                              (cx, h * .5 + u * .36, -90))):
            L = u * (.5 if side < 2 else .34)
            col = [a1, mix(a1, bg, .35), a2][side]
            o.append(f'<g transform="translate({bx:.0f} {by:.0f}) rotate({ang:.0f})"><path d="M0 0 Q{L * .5:.0f} {-L * .06:.0f} {L:.0f} 0" fill="none" stroke="{col}" stroke-width="3"/>')
            for k in range(1, 8):
                px = L * k / 8
                ls = u * (.06 - k * .0045)
                for sgn in (1, -1):
                    o.append(f'<path d="M{px:.0f} 0 q{ls * .5:.0f} {sgn * -ls * .9:.0f} {ls * 1.3:.0f} {sgn * -ls * .7:.0f} q{-ls * .4:.0f} {sgn * ls * .6:.0f} {-ls * 1.3:.0f} {sgn * ls * .7:.0f}Z" fill="{col}"/>')
            o.append("</g>")
    elif kind == "plan":                               # недвижимость: планировка квартиры
        u = min(w, h)
        x0, y0, W2, H2 = w * .12, h * .14, w * .76, h * .72
        st = max(6, u * .016)
        flip = r() < .5
        if flip:
            o.append(f'<g transform="translate({w} 0) scale(-1 1)">')
        o.append(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{W2:.0f}" height="{H2:.0f}" fill="{bg}"/>')
        sx, sy = x0 + W2 * (.42 + r() * .18), y0 + H2 * (.44 + r() * .16)
        o.append(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{sx - x0:.0f}" height="{sy - y0:.0f}" fill="{mix(sf, a1, .16)}"/>')
        o.append(f'<rect x="{sx:.0f}" y="{sy:.0f}" width="{x0 + W2 - sx:.0f}" height="{y0 + H2 - sy:.0f}" fill="{mix(sf, a2, .14)}"/>')
        wall = f'stroke="{ink}" stroke-width="{st:.0f}" stroke-linecap="square" fill="none"'
        o.append(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{W2:.0f}" height="{H2:.0f}" {wall}/>')
        o.append(f'<path d="M{sx:.0f} {y0:.0f}V{sy - H2 * .12:.0f}M{sx:.0f} {sy + H2 * .05:.0f}V{y0 + H2:.0f}M{x0:.0f} {sy:.0f}H{x0 + (sx - x0) * .6:.0f}M{sx + (x0 + W2 - sx) * .3:.0f} {sy:.0f}H{x0 + W2:.0f}" {wall}/>')
        d = H2 * .12                                   # двери — четверть круга
        o.append(f'<path d="M{sx:.0f} {sy - d:.0f} A{d:.0f} {d:.0f} 0 0 1 {sx + d:.0f} {sy:.0f}" fill="none" stroke="{ink}" stroke-width="2" stroke-dasharray="6 5"/>')
        o.append(f'<path d="M{x0 + (sx - x0) * .6:.0f} {sy:.0f} A{d:.0f} {d:.0f} 0 0 0 {x0 + (sx - x0) * .6 + d:.0f} {sy + d:.0f}" fill="none" stroke="{ink}" stroke-width="2" stroke-dasharray="6 5"/>')
        for wx in (x0 + W2 * .18, x0 + W2 * .7):                                 # окна
            o.append(f'<rect x="{wx:.0f}" y="{y0 - st:.0f}" width="{W2 * .14:.0f}" height="{st * 2:.0f}" fill="{bg}" stroke="{ink}" stroke-width="2"/>')
        o.append(f'<rect x="{x0 + W2 * .08:.0f}" y="{y0 + H2 * .1:.0f}" width="{W2 * .16:.0f}" height="{H2 * .24:.0f}" rx="6" fill="{a1}" opacity=".85"/>')
        o.append(f'<circle cx="{sx + (x0 + W2 - sx) * (.4 + r() * .3):.0f}" cy="{y0 + H2 * (.18 + r() * .16):.0f}" r="{u * .07:.0f}" fill="{a2}" opacity=".8"/>')
        o.append(f'<rect x="{sx + (x0 + W2 - sx) * .2:.0f}" y="{sy + (y0 + H2 - sy) * .45:.0f}" width="{(x0 + W2 - sx) * .5:.0f}" height="{(y0 + H2 - sy) * .32:.0f}" rx="8" fill="{mix(sf, ink, .2)}"/>')
        if flip:
            o.append("</g>")
    elif kind == "horizon":                            # туры: солнце, слои гор и волны
        u = min(w, h)
        o.append(f'<circle cx="{w * (.62 + r() * .14):.0f}" cy="{h * .34:.0f}" r="{u * .17:.0f}" fill="{a2}"/>')
        for k, (top, amp, col) in enumerate(((.42, .16, mix(bg, a1, .35)), (.52, .14, mix(bg, a1, .6)), (.62, .1, a1))):
            pts, x, up = [f"0,{h}"], 0.0, True
            while x <= w + 40:
                pts.append(f"{x:.0f},{h * (top + (0 if up else amp * (.6 + r() * .6))):.0f}")
                x += w * (.12 + r() * .14)
                up = not up
            pts.append(f"{w},{h}")
            o.append(f'<polygon points="{" ".join(pts)}" fill="{col}"/>')
        y = h * .76
        o.append(f'<rect x="0" y="{y:.0f}" width="{w}" height="{h - y:.0f}" fill="{ink}"/>')
        for k in range(4):
            yy = y + (h - y) * (.22 + k * .2)
            o.append(f'<path d="M0 {yy:.0f}' + "".join(f" q{w / 16:.0f} {-u * .025:.0f} {w / 8:.0f} 0 t{w / 8:.0f} 0" for _ in range(4)) + f'" fill="none" stroke="{sf}" stroke-opacity="{.5 - k * .1:.2f}" stroke-width="3"/>')
    elif kind == "spots":                              # груминг: пятна, как на шерсти, и косточка
        u = min(w, h)
        for i in range(8):
            cx, cy, s = w * r(), h * r(), u * (.07 + r() * .1)
            col = [a1, a2, mix(bg, ink, .75), mix(bg, a1, .4)][i % 4]
            pts, n = [], 10
            for k in range(n):
                ang = k / n * 6.283
                rr = s * (.86 + r() * .22)
                pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
            dd = f"M{(pts[0][0] + pts[-1][0]) / 2:.0f} {(pts[0][1] + pts[-1][1]) / 2:.0f}" + "".join(
                f" Q{pts[k][0]:.0f} {pts[k][1]:.0f} {(pts[k][0] + pts[(k + 1) % n][0]) / 2:.0f} {(pts[k][1] + pts[(k + 1) % n][1]) / 2:.0f}" for k in range(n)) + "Z"
            o.append(f'<path d="{dd}" fill="{col}"/>')
        bx, by, bl = w * .5, h * .5, u * .34
        o.append(f'<g transform="translate({bx:.0f} {by:.0f}) rotate(-24)" fill="{sf}"><rect x="{-bl / 2:.0f}" y="{-u * .035:.0f}" width="{bl:.0f}" height="{u * .07:.0f}"/>'
                 + "".join(f'<circle cx="{sx * bl / 2:.0f}" cy="{sy * u * .045:.0f}" r="{u * .055:.0f}"/>' for sx in (-1, 1) for sy in (-1, 1)) + "</g>")
    elif kind == "sprinkles":                          # торты: посыпка и торт сверху с волнистым краем
        u = min(w, h)
        cx, cy, R1 = w * (.5 + (r() - .5) * .2), h * (.48 + (r() - .5) * .1), u * .32
        sc = "".join(f'<circle cx="{cx + R1 * math.cos(k / 18 * 6.283):.0f}" cy="{cy + R1 * math.sin(k / 18 * 6.283):.0f}" r="{u * .055:.0f}"/>' for k in range(18))
        o.append(f'<g fill="{a2}">{sc}<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R1:.0f}"/></g><circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R1 * .82:.0f}" fill="{sf}"/>')
        o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R1 * .62:.0f}" fill="none" stroke="{a1}" stroke-width="3" stroke-dasharray="2 12" stroke-linecap="round"/>')
        o.append(f'<circle cx="{cx + R1 * .2:.0f}" cy="{cy - R1 * .22:.0f}" r="{u * .05:.0f}" fill="{mix(a2, ink, .25)}"/>')
        cols = [a1, a2, mix(a2, sf, .5), mix(bg, a1, .5)]
        for i in range(30):
            x, y = w * r(), h * r()
            if (x - cx) ** 2 + (y - cy) ** 2 < (R1 * 1.25) ** 2:
                continue
            s = u * (.018 + r() * .012)
            o.append(f'<rect x="{-s * 1.6:.0f}" y="{-s / 2:.0f}" width="{s * 3.2:.0f}" height="{s:.0f}" rx="{s / 2:.0f}" fill="{cols[i % 4]}" transform="translate({x:.0f} {y:.0f}) rotate({r() * 180:.0f})"/>')
    else:
        o.append(f'<circle cx="{w / 2:.0f}" cy="{h / 2:.0f}" r="{min(w, h) * .3:.0f}" fill="{a1}"/>')
    if mark:
        s = min(w, h) * .2
        o.append(f'<g transform="translate({w - s * 1.5:.0f} {h - s * 1.5:.0f}) scale({s / 24:.2f})" fill="none" stroke="{ink}" stroke-width="1.4" '
                 f'stroke-linecap="round" stroke-linejoin="round" opacity=".55">{(K.MARKS.get(mark) or K.MARKS["spark"])[1]}</g>')
    o.append("</svg>")
    return "".join(o)


def map_svg(pal, seed="m"):
    """Схематичная карта для «Контактов»: улицы и метка (без загрузки чужих карт)."""
    r = _rand(_seed(seed))
    w, h = 640, 420
    bg, ln, a1 = mix(pal["surface"], pal["bg"], .3), mix(pal["surface"], pal["ink"], .1), pal["accent"]
    o = [f'<svg class="art" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><rect width="{w}" height="{h}" fill="{bg}"/>']
    o.append(f'<path d="M0 {h * .72:.0f} C{w * .3:.0f} {h * .62:.0f} {w * .45:.0f} {h * .92:.0f} {w} {h * .8:.0f} V{h} H0Z" fill="{mix(bg, pal["accent2"], .22)}"/>')
    for i in range(7):
        x = w * r()
        o.append(f'<path d="M{x:.0f} -10 L{x + (r() - .5) * 160:.0f} {h + 10}" stroke="{ln}" stroke-width="{6 + r() * 10:.0f}" fill="none"/>')
    for i in range(5):
        y = h * r()
        o.append(f'<path d="M-10 {y:.0f} L{w + 10} {y + (r() - .5) * 120:.0f}" stroke="{ln}" stroke-width="{6 + r() * 12:.0f}" fill="none"/>')
    o.append(f'<path d="M{w / 2} {h * .62:.0f}c-34-40-52-64-52-90a52 52 0 0 1 104 0c0 26-18 50-52 90z" fill="{a1}"/>'
             f'<circle cx="{w / 2}" cy="{h * .62 - 90:.0f}" r="18" fill="{pal["accent_ink"]}"/></svg>')
    return "".join(o)
