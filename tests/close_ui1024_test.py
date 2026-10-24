"""«Близкие» на компьютере, 24.10, владелец:
- «не понятно, прочитал ли человек сообщение, дошло ли оно» — у своих сообщений ✓ «отправлено», ✓✓ «доставлено»,
  ✓✓ мятные «прочитано» (номер письма sid и отметки marks от сервера); галочки меняются без перерисовки;
- «в раздел Близкие нужно больше смайлов» — вкладки по темам, первая — частые (реакции);
- «на компе тоже бы видеть, если придёт сообщение от близкого — на виджете что-то засветится?» — строка «💌 Анна: …» у
  виджета держится, пока не прочитали; нажать — студия, «Близкие», сразу эта переписка."""
import json, os, re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { (window.apiCalls = window.apiCalls || []).push([k, ...a]); return Promise.resolve(true); } }) };"
CORE = r"""
(() => { window.calls = [];
  window.ST = { me: { name: "Миша" }, offers: [], people: [
    { pid: "p1", name: "Людмила", devs: [{ dev: "d1" }], unread: 0, marks: [9, 5], last: { out: true, t: "Как дела?" } },
    { pid: "p2", name: "Андрей", devs: [{ dev: "d2" }], unread: 0, marks: [0, 0], last: null }] };
  window.HIST = { p1: [{ mid: "a", ts: Date.now() - 90000, out: true, t: "Привет", f: [], sid: 5 },
                       { mid: "b", ts: Date.now() - 60000, out: false, t: "Привет!", f: [], sid: 7 },
                       { mid: "c", ts: Date.now() - 30000, out: true, t: "Как дела?", f: [], sid: 9 },
                       { mid: "d", ts: Date.now() - 20000, out: true, t: "Ау", f: [], sid: 11 },
                       { mid: "e", ts: Date.now() - 10000, out: true, t: "старое без номера", f: [] }],
                  p2: [{ mid: "x", ts: Date.now() - 5000, out: false, t: "Я переслал!", f: [], sid: 3 }] };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "close_state") return JSON.parse(JSON.stringify(ST));
      if (c === "close_history") { if (a.read !== false) { const p = ST.people.find(x => x.pid === a.pid); if (p) p.unread = 0; } return HIST[a.pid] || []; }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"close\"]').click()"); pg.wait_for_timeout(500)
    pg.evaluate("clOpen('p1')"); pg.wait_for_timeout(300)
    ticks = pg.evaluate("[...document.querySelectorAll('#cl-msgs .cl-m')].map(e => (e.querySelector('.cl-ck') || {}).className || '')")
    ok(ticks == ["cl-ck read", "", "cl-ck dlv", "cl-ck sent", ""], f"свои: прочитано ✓✓, доставлено ✓✓, отправлено ✓; чужие и старые — без галочек: {ticks}")
    ok(pg.evaluate("getComputedStyle(document.querySelector('.cl-ck.read')).color") != pg.evaluate("getComputedStyle(document.querySelector('.cl-ck.dlv')).color"),
       "«прочитано» — другим цветом")
    ok(pg.get_attribute(".cl-ck.dlv", "title").startswith("Доставлено"), "подсказка словами")
    pg.evaluate("document.querySelector('#cl-msgs').scrollTop = 0")
    pg.evaluate("ST.people[0].marks = [11, 11]; core.emit('close', { state: JSON.parse(JSON.stringify(ST)) })"); pg.wait_for_timeout(200)
    ticks = pg.evaluate("[...document.querySelectorAll('#cl-msgs .cl-m')].map(e => (e.querySelector('.cl-ck') || {}).className || '')")
    ok(ticks[3] == "cl-ck read" and ticks[2] == "cl-ck read", f"прочитали — галочки сменились сами: {ticks}")
    ok(pg.evaluate("document.querySelector('#cl-msgs').scrollTop") == 0, "и прокрутка не сбилась (галочки — без перерисовки)")
    # смайлы
    pg.click("#cl-emo-b"); pg.wait_for_timeout(150)
    tabs = pg.evaluate("[...document.querySelectorAll('#cl-emo [data-t]')].map(b => b.textContent)")
    ok(len(tabs) == 7 and tabs[0].startswith("👍") and "Частые" in tabs[0], f"смайлы по вкладкам: {tabs}")
    total = pg.evaluate("CL_EMO_SETS.reduce((a, s) => a + s[1].length, 0)")
    ok(total >= 150 and pg.evaluate("new Set(CL_EMO_SETS.flatMap(s => s[1])).size") == total, f"смайлов {total}, без повторов")
    pg.click("#cl-emo [data-t='5']"); pg.wait_for_timeout(100)
    pg.fill("#cl-text", "Пойдём на "); pg.click("#cl-emo button[data-e='☕']")
    ok(pg.input_value("#cl-text") == "Пойдём на ☕", f"вкладка «Еда» — ☕ в поле: {pg.input_value('#cl-text')!r}")
    pg.screenshot(path="/tmp/claude-0/close_ui.png")
    # пришло новое, открыт раздел — переходим к непрочитанному
    pg.evaluate("ST.people[1].unread = 1"); pg.evaluate("loadClose()"); pg.wait_for_timeout(400)
    ok(pg.evaluate("CL.cur") == "p2", "открыли раздел, есть непрочитанное у Андрея — сразу его переписка")
    reads = [c[1] for c in pg.evaluate("calls") if c[0] == "close_history" and c[1]["pid"] == "p2"]
    ok(reads and reads[-1].get("read") is True, "окно на виду — «прочитано» ставится")

    # виджет
    h = b.new_page(viewport={"width": 420, "height": 700}); h.on("pageerror", lambda e: errs.append(str(e)))
    h.route(re.compile(r"^https?://"), lambda r: r.abort())
    h.add_init_script(FAKE); h.add_init_script(CORE)
    h.goto((ROOT / "ui/hud.html").as_uri()); h.wait_for_timeout(1500)
    ok(not h.evaluate("document.getElementById('clb').classList.contains('on')"), "непрочитанного нет — строки нет")
    h.evaluate("ST.people[1].unread = 2; core.emit('close_msg', { pid: 'p2', name: 'Андрей', text: 'Я переслал!', files: [] })"); h.wait_for_timeout(300)
    ok(h.evaluate("document.getElementById('clb').classList.contains('on')") and "Андрей: Я переслал!" in h.inner_text("#clb") and h.inner_text("#clb-n") == "2",
       f"пришло от Андрея — у виджета «💌 Андрей: Я переслал!» и счётчик: {h.inner_text('#clb')!r}")
    h.screenshot(path="/tmp/claude-0/hud_clb.png")
    h.click("#clb"); h.wait_for_timeout(200)
    ok(["open_settings", "close"] in h.evaluate("window.apiCalls || []"), "нажали — студия, «Близкие»")
    h.evaluate("ST.people[1].unread = 0; core.emit('close', { state: JSON.parse(JSON.stringify(ST)) })"); h.wait_for_timeout(150)
    ok(not h.evaluate("document.getElementById('clb').classList.contains('on')"), "прочитали — строка исчезла")
    h.evaluate("ST.people[0].unread = 1; core.emit('close_msg', { pid: 'p1', name: 'Людмила', text: 'Ты где?', files: [] })"); h.wait_for_timeout(300)
    h.click("#clb-x"); h.wait_for_timeout(100)
    h.evaluate("core.emit('close', { state: JSON.parse(JSON.stringify(ST)) })"); h.wait_for_timeout(100)
    ok(not h.evaluate("document.getElementById('clb').classList.contains('on')"), "✕ — скрыто, пока не придёт новое")
    h.evaluate("ST.people[0].unread = 2; core.emit('close_msg', { pid: 'p1', name: 'Людмила', text: 'Ответь', files: [] })"); h.wait_for_timeout(300)
    ok(h.evaluate("document.getElementById('clb').classList.contains('on')") and "Ответь" in h.inner_text("#clb"), "новое после ✕ — снова видно")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
if fails:
    raise SystemExit(1)
