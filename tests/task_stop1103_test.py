"""№448, №460 (ПК 0.76.0, два человека, DeepSeek напрямую): фоновая задача вставала почти сразу — «работа остановлена:
задача повторяла одно и то же или перестала действовать». Причины, которые проверяем:
— DeepSeek писал вызовы текстом в виде, который Dewiar не узнавал: «<｜DSML calls｜>…» (у №448 «｜» и перед «>») и
  «<tool_calls><invoke name="…"><parameter name="…">» без «DSML» (у №460) — три таких ответа, и задача «перестала действовать»;
— после пары действий модель писала отчёт текстом вместо finish — и задача сразу вставала: теперь второй шанс;
— «второй раз прошу — не выполняет»: перезапуск оставлял метку finished, и задача снова вставала после первого действия;
— итог «не выполнено» говорит, что случилось и что задача успела, а не общую фразу."""
import json, os, re, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"),
                  DEWIAR_REFLECT_EVERY="0")
sys.path.insert(0, str(ROOT / "core"))
import llm  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def wait_for(cond, sec=40):
    end = time.time() + sec
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


# ── 1. вызовы DeepSeek в тексте — узнаются в любом виде, обычный текст не трогаем ──
D448 = ('<｜DSML calls｜>\n<｜DSML invoke name="web_search"｜>\n<｜DSML parameter name="query" string="true"｜>Основание 3 сезон дата выхода'
        '</｜DSML parameter｜>\n</｜DSML invoke｜>\n</｜DSML calls｜>')
D460 = ('Начинаю.\n<tool_calls>\n<invoke name="remember">\n<parameter name="fact">Дата: 01.11.2026.</parameter>\n</invoke>\n'
        '<invoke name="notes">\n<parameter name="text"># Блокнот\n- ноутбук <для LLM></parameter>\n</invoke>\n</tool_calls>')
DV4 = ('<｜DSML｜tool▁calls>\n<｜DSML｜invoke name="web_search">\n<｜DSML｜parameter name="query" string="true">x</｜DSML｜parameter>\n'
       '<｜DSML｜parameter name="n" string="false">5</｜DSML｜parameter>\n</｜DSML｜invoke>\n</｜DSML｜tool▁calls>')
OLD = ('<｜DSML｜function_calls><｜DSML｜invoke name="weather"><｜DSML｜parameter name="city" string="true">Москва</｜DSML｜parameter>'
       '</｜DSML｜invoke></｜DSML｜function_calls>')
PLAIN = "Сравни a < b и <b>жирный</b>, <tool> и <invoke> — просто текст. Про DSML тоже. Конец <"
CASES = [(D448, "", [("web_search", {"query": "Основание 3 сезон дата выхода"})]),
         (D460, "Начинаю.\n", [("remember", {"fact": "Дата: 01.11.2026."}), ("notes", {"text": "# Блокнот\n- ноутбук <для LLM>"})]),
         (DV4, "", [("web_search", {"query": "x", "n": 5})]),
         (OLD, "", [("weather", {"city": "Москва"})]),
         (PLAIN, PLAIN, [])]
for i, (src, text, want) in enumerate(CASES):
    good = True
    for n in (1, 2, 3, 7, 1000):
        st = llm.ToolTagStripper(); st.known = {"web_search", "remember", "notes", "weather"}
        out = "".join(st.feed(src[k:k + n]) for k in range(0, len(src), n)) + st.tail()
        got = [(c["name"], c["args"]) for c in st.calls()]
        if out != text or got != want:
            good = False
            print("   ", n, repr(out[:80]), got)
    ok(good, f"вызовы в тексте, вид {i + 1}: {want[0][0] if want else 'обычный текст — без изменений'} — куски по 1…1000 символов")
ok(not llm._dsml_part("<b") and llm._dsml_part("<｜DS") and llm._dsml_part("<tool_ca") and llm._dsml_part("</") and
   not llm._dsml_part("< b и так далее"), "придерживается только начало возможного тега")

# ── 2. задачи: мок модели ──
from workspace import Workspace  # noqa: E402
import tools as T  # noqa: E402
import tasks as TK  # noqa: E402

ok(TK.CALL_MARK_RX.search('<tool_calls>\n<invoke name="x">') and TK.CALL_MARK_RX.search("<DSML calls>")
   and not TK.CALL_MARK_RX.search("Готово: нашла три ноутбука, ссылки ниже."), "вызов текстом узнаётся как попытка действия")

SCRIPT, pos, lock = {}, {}, threading.Lock()


def step(title, i, msgs):
    """-> ("text", str) | (имя, аргументы). Сценарии по названию задачи."""
    last = str(msgs[-1].get("content") or "") if msgs else ""
    if title == "Сериалы":                      # №448: вызовы только текстом DSML, потом finish
        seq = [("text", D448), ("text", D448.replace("Основание", "Комиссар полиции")), ("update_plan", {"plan": "- [x] найти даты"}),
               ("finish", {"summary": "«Основание»: 3 сезон вышел; «Комиссар полиции»: премьера в октябре 2026."})]
        return seq[i] if i < len(seq) else ("text", "…")
    if title == "Ноутбуки":                     # №460: одно действие, потом отчёт текстом; после второго шанса — finish
        if "несколько раз подряд" in last:
            return ("finish", {"summary": "Подобрала 5 ноутбуков до 35 000 ₽ — список с плюсами и минусами ниже."})
        if i == 0:
            return ("update_plan", {"plan": "- [x] Собрать кандидатов\n- [x] Отчёт"})
        return ("text", "### Шаг 3: Сбор данных\n1. Lenovo IdeaPad 3 — ~32 000 ₽\n2. Acer Aspire 5 — ~35 000 ₽")
    if title == "Молчунья":                     # действует раз, дальше только текст — честная остановка
        if SCRIPT.get("Молчунья") == "work":    # после перезапуска — работает: поиск, план, итог
            k = pos["Молчунья работа"] = pos.get("Молчунья работа", -1) + 1
            return [("web_search", {"query": "ноутбук 15.6 8 ГБ"}), ("update_plan", {"plan": "- [x] найти"}),
                    ("finish", {"summary": "Нашла: Lenovo IdeaPad Slim 3 — 34 990 ₽."})][min(k, 2)]
        if i == 0:
            return ("web_search", {"query": "ноутбук до 35000"})
        return ("text", "Понял, продолжу по плану и составлю отчёт.")
    return ("text", "…")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sysm = body["messages"][0]["content"]
        tc, text = None, ""
        with lock:
            if sysm.startswith("Ты — строгий"):
                text = '{"verdict": "ok"}'
            elif sysm.startswith("Ты — аналитик"):
                text = '{"lessons": []}'
            elif not body.get("tools") and "ЗАДАЧА:" not in sysm:
                text = "ok"
            else:
                title = re.search(r"ЗАДАЧА: (.+)", sysm).group(1).strip()
                i = pos.get(title, 0); pos[title] = i + 1
                name, args = step(title, i, body["messages"][1:])
                if name == "text":
                    text = args
                else:
                    tc = {"index": 0, "id": f"c{title}{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        chunks = [{"choices": [{"delta": {"content": text[k:k + 9]}}]} for k in range(0, len(text), 9)]
        if tc:
            chunks.append({"choices": [{"delta": {"tool_calls": [tc]}}]})
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()


class FakeS:
    def get(self, *k): return {} if k[0] == "tools" else None


class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.toolbox = T.Toolbox(FakeS(), None); self.toolbox.hooks["workspace"] = self.workspace
        self.toolbox.run = lambda name, args: (f"Результаты поиска: {args.get('query')} — 1. Ноутбук, 34 990 ₽"
                                               if name == "web_search" else "Готово.")
        self.said = []
    def persona_name(self): return "Лира"
    def memory(self): return ""
    def llm_profile(self): return {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "m"}
    def max_steps(self): return 30
    def code_auto_run(self): return False
    def confirm(self, q, timeout=120, cancel=None): return True
    def ask_user(self, t, q): pass
    def announce(self, text): self.said.append(text)
    def push(self, title, text="", critical=False, file=None): pass
    def emit(self, *a, **k): pass


host = Host()
tm = TK.TaskManager(host)
J = lambda t: (t.dir / "журнал.md").read_text(encoding="utf-8")

t = tm.create("Сериалы", "Следить, когда выйдут сериалы")
ok(wait_for(lambda: t.status in ("done", "failed")) and t.status == "done", f"№448: вызовы DSML выполняются, задача готова ({t.status}; {t.data.get('error', '')[:120]})")
ok("🛠 `web_search` {\"query\": \"Основание 3 сезон" in J(t) and "Комиссар полиции" in J(t), "в журнале — поиски с запросами, а не «ответила текстом»")

t2 = tm.create("Ноутбуки", "Подобрать 5 ноутбуков до 35 000 ₽")
ok(wait_for(lambda: t2.status in ("done", "failed")) and t2.status == "done", f"№460: отчёт текстом — второй шанс, и задача готова ({t2.status}; {t2.data.get('error', '')[:120]})")
ok("даю ещё попытку" in J(t2), "в журнале — второй шанс, а не мгновенная остановка")

t3 = tm.create("Молчунья", "Найти ноутбук")
ok(wait_for(lambda: t3.status in ("done", "failed")) and t3.status == "failed", f"модель только пишет текст — честная остановка ({t3.status})")
err = t3.data.get("error", "")
ok("перестала выполнять действия" in err and "успела: поиск в интернете ×1" in err and "повторяла одно и то же" not in err,
   f"итог понятный: что случилось и что успела — {err[:200]}")
ok("даю ещё попытку" in J(t3), "перед остановкой был второй шанс")
ok(any("не выполнена: модель перестала" in s and "успела:" not in s for s in host.said), f"голосом — причина без счёта: {host.said[-1:]}")

# «второй раз прошу — не выполняет»: перезапуск — новая попытка, а не мгновенное «не выполнено» после первого шага
SCRIPT["Молчунья"] = "work"
n0 = int(t3.data.get("steps") or 0)
tm.start(t3.id)
ok(wait_for(lambda: t3.status in ("done", "failed") and int(t3.data.get("steps") or 0) > n0) and t3.status == "done",
   f"перезапуск после «не выполнено» доводит задачу до конца ({t3.status}; шагов {int(t3.data.get('steps') or 0) - n0}; {t3.data.get('error', '')[:100]})")
ok("Lenovo IdeaPad Slim 3" in (t3.result or "") and "Не выполнено" not in (t3.result or ""), f"итог — новый, без старого «не выполнено»: {(t3.result or '')[:120]!r}")

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
os._exit(1 if fails else 0)
