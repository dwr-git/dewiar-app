"""Проверка читаемости текста на странице (отзыв 18.10: в теме «Небесный» роли персонажей и таймер виджета почти не
читались). Цвет текста — из стилей (с прозрачностью и opacity предков), фон — со снимка той же страницы, где весь текст
сделан прозрачным: так учтены градиенты, стекло и картинки под текстом. Контраст — по WCAG.

audit(page, scope="body", min_ratio=3.0) -> [{text, ratio, fg, bg, sel}] — тексты ниже порога (видимые, в окне)."""
import io

from PIL import Image

COLLECT = r"""([scope]) => {
  const out = [], root = document.querySelector(scope) || document.body, W = innerWidth, H = innerHeight;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  const rgba = (s) => {                          // rgb()/rgba() и color(srgb …) — так отдаёт color-mix()
    let m = s.match(/rgba?\(([^)]+)\)/);
    if (m) { const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
    m = s.match(/color\(srgb ([^)]+)\)/);
    if (m) { const p = m[1].split(/[ /]+/).filter(Boolean).map(Number); return [p[0] * 255, p[1] * 255, p[2] * 255, p.length > 3 ? p[3] : 1]; }
    return null; };
  while (walker.nextNode()) {
    const n = walker.currentNode, t = n.textContent.replace(/\s+/g, " ").trim();
    if (t.length < 2 || !/[\p{L}\d]/u.test(t)) continue;
    const el = n.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    if (el.closest("svg, canvas, script, style, noscript, option, [aria-hidden=true]")) continue;
    const r = document.createRange(); r.selectNodeContents(n); const b = r.getBoundingClientRect();
    if (b.width < 4 || b.height < 6 || b.right < 0 || b.bottom < 0 || b.left > W || b.top > H) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden") continue;
    let op = 1, a = el, hidden = false;
    for (; a; a = a.parentElement) { const s = getComputedStyle(a); op *= +s.opacity; if (s.display === "none") hidden = true; }
    if (hidden || op < 0.05) continue;
    const fill = cs.webkitTextFillColor && cs.webkitTextFillColor !== cs.color && !/rgba\(0, 0, 0, 0\)/.test(cs.webkitTextFillColor) ? cs.webkitTextFillColor : cs.color;
    const c = rgba(fill); if (!c) continue;
    if (/text/.test(cs.backgroundClip || cs.webkitBackgroundClip || "")) continue;   // текст-градиент — не проверяем
    // сам текст поверх чего-то, что его перекрывает (модальное окно), — не наш случай
    const cx = Math.min(W - 1, Math.max(0, b.left + b.width / 2)), cy = Math.min(H - 1, Math.max(0, b.top + b.height / 2));
    const top = document.elementFromPoint(cx, cy); if (top && top !== el && !el.contains(top) && !top.contains(el)) continue;
    // прокручено за край своего окошка (длинный список в диалоге «Что нового») — не видно, не проверяем
    let clip = false;
    for (let q = el.parentElement; q && q !== document.body; q = q.parentElement) {
      const qs = getComputedStyle(q);
      if (!/(auto|scroll|hidden|clip)/.test(qs.overflow + qs.overflowY + qs.overflowX)) continue;
      const qr = q.getBoundingClientRect();
      if (cy < qr.top || cy > qr.bottom || cx < qr.left || cx > qr.right) { clip = true; break; }
    }
    if (clip) continue;
    const id = out.length; el.dataset.cxi = id;
    out.push({ id, text: t.slice(0, 60), x: b.left, y: b.top, w: b.width, h: b.height, c, op, size: parseFloat(cs.fontSize), weight: +cs.fontWeight || 400,
      sel: el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".") : "") });
  }
  return out;
}"""
HIDE = "*, *::before, *::after { color: transparent !important; -webkit-text-fill-color: transparent !important; text-shadow: none !important; caret-color: transparent !important; }"


def _lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def audit(page, scope="body", min_ratio=3.0, settle=250):
    items = page.evaluate(COLLECT, [scope])
    if not items:
        return []
    h = page.add_style_tag(content=HIDE)
    page.wait_for_timeout(settle)
    shot = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    h.evaluate("e => e.remove()")
    sx = shot.width / page.viewport_size["width"]
    bad = []
    for it in items:
        x0, y0 = int(max(0, it["x"]) * sx), int(max(0, it["y"]) * sx)
        x1, y1 = int(min(shot.width, (it["x"] + it["w"]) * sx)), int(min(shot.height, (it["y"] + it["h"]) * sx))
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        px = list(shot.crop((x0, y0, x1, y1)).resize((max(1, (x1 - x0) // 3), max(1, (y1 - y0) // 3))).getdata())
        bg = tuple(sorted(p[i] for p in px)[len(px) // 2] for i in range(3))
        r, g, b, a = it["c"]
        a *= it["op"]
        fg = (r * a + bg[0] * (1 - a), g * a + bg[1] * (1 - a), b * a + bg[2] * (1 - a))
        k = ratio(fg, bg)
        if k < min_ratio:
            bad.append({"text": it["text"], "ratio": round(k, 2), "fg": tuple(int(v) for v in fg), "bg": bg, "sel": it["sel"], "size": it["size"]})
    return bad
