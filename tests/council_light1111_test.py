"""Владелец 11.11, 22:46 (неоморфизм): «в „Совете ИИ“ справа вверху синяя плашка выбивается из дизайна — сделать
органичнее». Тёмный «стол» совета в светлых темах — теперь из того же материала, что карточки слева (стекло темы),
текст — цвета темы; в тёмных темах — как был."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => ({}); setTimeout(() => core.emit("hello", {}), 200); }; ready(); })();"""
lum = lambda rgb: sum(int(x) for x in re.findall(r"\d+", rgb)[:3]) / 3   # noqa: E731
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for sk, light in (("neusky", True), ("neu", True), ("brand", False)):
        st = b.new_page(viewport={"width": 1400, "height": 800}); st.on("pageerror", lambda e: errs.append(str(e)))
        st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
        st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1000)
        st.evaluate(f"() => {{ const w = document.querySelector('#wlc'); if (w) w.remove(); studioSkin('{sk}', true); document.querySelector('nav button[data-p=\"council\"]').click(); }}")
        st.wait_for_timeout(500)
        bg = st.evaluate("getComputedStyle(document.querySelector('.co-stage')).backgroundColor")
        img = st.evaluate("getComputedStyle(document.querySelector('.co-stage')).backgroundImage")
        ink = st.evaluate("getComputedStyle(document.querySelector('.co-qline')).color")
        if light:
            ok("#1b1730" not in img and "27, 23, 48" not in img and lum(ink) < 150, f"{sk}: стол совета — светлый материал темы, текст тёмный ({ink})")
        else:
            ok("27, 23, 48" in img and lum(ink) > 150, f"{sk}: тёмная тема — стол как был ({ink})")
        st.close()
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
if fails:
    sys.exit(1)
print("\n✅ всё в порядке")
