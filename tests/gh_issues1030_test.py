"""Обращения на GitHub (dwr-git/dewiar-app, 29.10), подтверждённые по коду:
№26 — блокнот: правка с другого устройства через полсекунды после открытия молча затиралась (допуск «+ 0,5 с»);
№27 — блокнот: после переименования вкладки «назад» (Ctrl+Z) не работал — история жила под старым названием;
№28 — блокнот, Windows: переименование, меняющее только регистр («заметки» → «Заметки»), молча не делалось;
№29 — разбор вызова функции из текста: «D:\\Demo\\new\\test.txt» без экранирования — «\\n» и «\\t» в пути становились
переводом строки и табуляцией.
PR №24 — Claude (Anthropic): кэш подсказки и инструментов (cache_control) — повтор каждого шага в ~10 раз дешевле."""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st")
os.environ["DEWIAR_WORKSPACE_DIR"] = str(tmp / "ws")
os.environ["DEWIAR_WORKSPACE"] = str(tmp / "ws")          # не трогать настоящую папку Dewiar
import settings as ST  # noqa: E402
import workspace as W  # noqa: E402
import pad as PD  # noqa: E402
import llm  # noqa: E402

s = ST.Settings(tmp / "s.json")
P = PD.Pad(W.Workspace(s), s)
P.tabs()
P.new("Работа")
base = P.write("Работа", "моё")["mtime"]
f = P._path("Работа")
f.write_text("с телефона", encoding="utf-8")
os.utime(f, (base + 0.2, base + 0.2))                     # другое устройство записало через 0,2 с
r = P.write("Работа", "моё, дописанное", base=base)
names = [t["name"] for t in P.tabs()["tabs"]]
ok(r.get("conflict") and any("с другого устройства" in n for n in names)
   and P.read(r["conflict"])["text"] == "с телефона", f"№26: правка с другого устройства через 0,2 с не теряется — отдельной вкладкой: {r}")
r2 = P.write("Работа", "ещё", base=r["mtime"])
ok(not r2.get("conflict"), "№26: своя следующая запись — без ложного конфликта")

src = (ROOT / "core/pad.py").read_text(encoding="utf-8")
ok("if q.name == p.name:" in src and "q.exists() and not _same_file(q, p)" in src, "№28: сравнение имён строкой, свой же файл в другом регистре — не «уже есть»")
P.new("заметки")
P.rename("заметки", "Заметки")
names = [t["name"] for t in P.tabs()["tabs"]]
ok("Заметки" in names and "заметки" not in names, f"№28: «заметки» → «Заметки» переименовано: {names}")
P.new("Склад")
try:
    P.rename("Склад", "Работа"); dup = False
except PD.PadError:
    dup = True
ok(dup, "№28: чужое существующее имя — по-прежнему «уже есть»")

raw = '{"path": "D:\\Demo\\new\\test.txt", "text": "a\\tb"}'
a = llm._loads_loose(raw)
ok(a and a["path"] == "D:\\Demo\\new\\test.txt", f"№29: путь Windows без экранирования — как есть: {a and a['path']!r}")
a = llm._loads_loose('{"path": "C:\\Users\\tom\\bin\\run.bat", "q": "\\\'"}')
ok(a and a["path"] == "C:\\Users\\tom\\bin\\run.bat" and a["q"] == "'", f"№29: «\\t», «\\b», «\\r» в пути — буквальные: {a}")
a = llm._loads_loose('{"code": "print(\'x\')\nx = 1", "msg": "строка\\nвторая \\D"}')
ok(a and a["code"] == "print('x')\nx = 1" and a["msg"] == "строка\nвторая \\D", f"№29: обычный текст — как раньше (№390): {a}")
c = llm.parse_tool_call('write_file {"path": "D:\\Demo\\new\\test.txt", "content": "hi"}')
ok(c and c["args"].get("path") == "D:\\Demo\\new\\test.txt", f"№29: и в разборе вызова из текста: {c}")

# PR №24 — Claude: cache_control на подсказке и последнем инструменте
import http.server, threading  # noqa: E402
GOT = []


class Anth(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        GOT.append(json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0))))
        ev = [{"type": "message_start", "message": {"usage": {}}}, {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
              {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Привет"}}, {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
              {"type": "message_stop"}]
        b = "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in ev).encode()
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Anth)
threading.Thread(target=srv.serve_forever, daemon=True).start()
prof = {"kind": "anthropic", "base_url": f"http://127.0.0.1:{srv.server_address[1]}", "api_key": "k", "model": "claude-x"}
tools_ = [{"name": "a", "description": "A", "parameters": {"type": "object", "properties": {}}}, {"name": "b", "description": "B", "parameters": {"type": "object", "properties": {}}}]
try:
    list(llm.stream_events(prof, "Ты — Лира.", [{"role": "user", "content": "привет"}], tools=tools_))
except Exception as e:  # noqa: BLE001
    print("stream:", e)
bd = GOT[-1] if GOT else {}
ok(bd.get("system") == [{"type": "text", "text": "Ты — Лира.", "cache_control": {"type": "ephemeral"}}]
   and bd.get("tools", [{}])[-1].get("cache_control") == {"type": "ephemeral"} and "cache_control" not in bd.get("tools", [{}])[0],
   f"PR №24: Claude — подсказка и инструменты с cache_control: system={str(bd.get('system'))[:80]}")
srv.shutdown()

# №27 — страница блокнота: история «назад» переходит к новому названию
from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = """window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(true) }) };"""
CORE = r"""
(() => { const tabs = { "Главное": "первая строка\n", "Работа": "" };
  window.calls = [];
  const list = () => Object.keys(tabs).map(n => ({ name: n, mtime: 1 }));
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: list(), active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: tabs[a.name], mtime: 1 };
      if (c === "pad_write") { tabs[a.name] = a.text; return { mtime: 2 }; }
      if (c === "pad_rename") { tabs[a.to] = tabs[a.name]; delete tabs[a.name]; return { tabs: list(), active: a.to }; }
      return {}; }; };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 440, "height": 560}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky"); pg.wait_for_timeout(1200)
    pg.click("#ed"); pg.keyboard.press("End"); pg.keyboard.type(" и добавка"); pg.wait_for_timeout(900)
    before = pg.evaluate("Object.keys(H.tabs).map(k => [k, H.tabs[k].s.length])")
    pg.evaluate("""() => { const el = document.querySelector('.tab.on'); rename(el, 'Главное');
      const i = el.querySelector('input'); i.value = 'Дела'; i.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' })); }""")
    pg.wait_for_timeout(800)
    after = pg.evaluate("[P.active, Object.keys(H.tabs)]")
    pg.click("#ed"); pg.keyboard.press("Control+z"); pg.wait_for_timeout(300)
    txt = pg.evaluate("document.querySelector('#ed').innerText")
    ok(after[0] == "Дела" and "Дела" in after[1] and "Главное" not in after[1], f"№27: история переименованной вкладки — под новым названием: {before} → {after}")
    ok("добавка" not in txt and "первая строка" in txt, f"№27: Ctrl+Z после переименования работает: {txt!r}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
