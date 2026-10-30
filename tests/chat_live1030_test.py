"""Студия, «Чат» на слабом компьютере (GitHub №22, ALT Linux: «очень сильно тормозит, особенно окно чата»): пока модель
отвечает, каждый кусок ответа раньше заново собирал ВСЮ ленту (innerHTML + схемы Mermaid). Теперь кусок меняет только
живой пузырь (не чаще кадра), лента не пересобирается; готовый ответ (событие chat) — лента целиком, как раньше."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


items = [{"id": f"m{i}", "ts": 1793300000 + i, "role": "user" if i % 2 == 0 else "assistant", "who": "lira",
          "text": ("Вопрос " if i % 2 == 0 else "Ответ с **жирным** и списком:\n- раз\n- два\n") + str(i)} for i in range(160)]
FAKE_CORE = """(() => {
  window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "chat_list") return { items: %s, more: false };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""" % json.dumps(items, ensure_ascii=False)
with sync_playwright() as p:
    b = p.chromium.launch(); errors = []
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errors.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort())
    st.add_init_script(FAKE_CORE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1500)
    st.evaluate("document.querySelector('nav button[data-p=\"chat\"]').click()"); st.wait_for_timeout(300)
    st.evaluate("loadChat()"); st.wait_for_timeout(600)
    n0 = st.evaluate("document.querySelectorAll('#ch-msgs .cl-m').length")
    st.evaluate("""() => { window._rebuilds = 0; const box = document.getElementById('ch-msgs');
        new MutationObserver(ms => { if (ms.some(m => m.target === box && m.type === 'childList' && m.removedNodes.length > 20)) window._rebuilds++; })
          .observe(box, { childList: true }); }""")
    st.evaluate("""async () => { let t = ''; for (let i = 0; i < 120; i++) { t += 'слово' + i + ' '; core.emit('answer', { text: t }); if (i % 10 === 0) await new Promise(r => setTimeout(r, 16)); } }""")
    st.wait_for_timeout(300)
    R = st.evaluate("""() => [window._rebuilds, (document.getElementById('ch-live') || {}).textContent || '', document.querySelectorAll('#ch-msgs .cl-m').length]""")
    ok(R[0] <= 1, f"120 кусков ответа — лента пересобрана не больше одного раза (первый кусок): {R[0]}")
    ok("слово119" in R[1] and R[2] == n0 + 1, f"живой пузырь — с последним словом, остальная лента на месте: {R[2]} пузырей")
    st.evaluate("core.emit('tool', { name: 'weather', title: 'Узнаю погоду', status: 'run' })"); st.wait_for_timeout(100)
    ok("Узнаю погоду" in st.evaluate("document.getElementById('ch-live').textContent"), "шаг хода — в живом пузыре")
    st.evaluate("""core.emit('chat', { item: { id: 'm999', ts: 1793300999, role: 'assistant', who: 'lira', text: 'Готовый ответ' } })"""); st.wait_for_timeout(300)
    ok(not st.evaluate("!!document.getElementById('ch-live')") and "Готовый ответ" in st.inner_text("#ch-msgs"), "ответ готов — живой пузырь стал обычным сообщением")
    b.close()
ok(not errors, f"без ошибок на странице: {errors[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
