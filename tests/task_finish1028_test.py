"""№368 (28.10, Max_Bond): «в долгих задачах итог можно закрыть как выполненный, хотя обещанного результата на диске нет».
Проверяем: отклонённый самопроверкой итог проходит проверки снова при следующем finish (не «запоминается проверенным»);
после нескольких отказов задача останавливается «не выполнено» (failed), а не «готово»; файл, названный в итоге, должен
существовать; остановка из-за повтора — «не выполнено»; list_files и самопроверка видят файлы «Лаборатории» (lab_write)."""
import json, os, re, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"),
                  DEWIAR_REFLECT_EVERY="0")
sys.path.insert(0, str(ROOT / "core"))
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


from workspace import Workspace  # noqa: E402
import tools as T  # noqa: E402
import tasks as TK  # noqa: E402

SCRIPTS = {
    "Упрямая": [("finish", {"summary": "Сайт готов, всё сделано."})] * 8,
    "Обещание": [
        ("finish", {"summary": "Таблица продаж — в файле продажи.csv."}),
        ("write_file", {"path": "outputs/продажи.csv", "content": "месяц,сумма\nянварь,100\nфевраль,120\n"}),
        ("show", {"path": "outputs/продажи.csv", "title": "Продажи"}),
        ("finish", {"summary": "Таблица продаж — в файле продажи.csv."}),
    ],
    "Лаба": [
        ("lab_write", {"name": "calc.py", "content": "print(2 + 2)\n"}),
        ("list_files", {}),
        ("finish", {"summary": "Скрипт calc.py в лаборатории считает сумму. Ссылка на документацию: https://docs.python.org/3/index.html"}),
    ],
    "Молчунья": [("list_files", {}), ("text", "Думаю…"), ("text", "Ещё думаю…"), ("text", "Всё ещё думаю…")],
}
pos, reqs, crit = {}, [], []
lock = threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sysm = body["messages"][0]["content"]
        tc, text = None, ""
        with lock:
            if sysm.startswith("Ты — строгий"):
                user = body["messages"][-1]["content"]
                crit.append(user)
                text = ('{"verdict": "revise", "problems": "Сайта нет: в папке только текст и JSON."}' if "Сайт готов" in user else '{"verdict": "ok"}')
            elif sysm.startswith("Ты — аналитик"):
                text = '{"lessons": []}'
            else:
                title = re.search(r"ЗАДАЧА: (.+)", sysm).group(1).strip()
                i = pos.get(title, 0); pos[title] = i + 1
                sc = SCRIPTS.get(title, [])
                name, args = sc[i] if i < len(sc) else ("text", "…")
                reqs.append({"title": title, "i": i, "messages": body["messages"][1:]})
                if name == "text":
                    text = args
                else:
                    text = f"Шаг {i + 1}. "
                    tc = {"index": 0, "id": f"c{len(reqs)}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for c in [{"choices": [{"delta": {"content": text}}]}] + ([{"choices": [{"delta": {"tool_calls": [tc]}}]}] if tc else []):
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()


class FakeS:
    def get(self, *k): return {} if k[0] == "tools" else None


class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.toolbox = T.Toolbox(FakeS(), None); self.toolbox.hooks["workspace"] = self.workspace
        self.said, self.pushes = [], []
    def persona_name(self): return "Лира"
    def memory(self): return ""
    def llm_profile(self): return {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "m"}
    def max_steps(self): return 30
    def code_auto_run(self): return True
    def confirm(self, q): return True
    def ask_user(self, t, q): pass
    def announce(self, text): self.said.append(text)
    def push(self, title, text="", critical=False, file=None): self.pushes.append((title, text))
    def emit(self, *a, **k): pass


host = Host()
tm = TK.TaskManager(host)
J = lambda t: (t.dir / "журнал.md").read_text(encoding="utf-8")
after = lambda title, i: next((m["content"] for m in reversed([r for r in reqs if r["title"] == title and r["i"] == i][0]["messages"])
                               if m["role"] in ("user", "tool")), "")

t = tm.create("Упрямая", "Сделай сайт-визитку")
ok(wait_for(lambda: t.status in ("done", "failed")), f"«Упрямая» остановилась ({t.status})")
n_crit = sum(1 for c in crit if "Сайт готов" in c)
ok(n_crit >= 2, f"самопроверка идёт при каждом finish, а не один раз: {n_crit} проверок")
ok(t.status == "failed" and "не выполнено" in t.data.get("error", ""), f"отказы проверки не кончились «готово» — «не выполнено»: {t.status} {t.data.get('error', '')[:80]}")
it = (t.dir / "итог.md").read_text(encoding="utf-8")
ok(it.lstrip("# Итог: Упрямая\n").startswith("**Не выполнено:**") and "Сайт готов" in it, "в итоге — честное «не выполнено» и что успела")
ok(any("не выполнена" in s for s in host.said) and not any("готова" in s for s in host.said if "Упрямая" in s), f"вслух — «не выполнена», не «готова»: {host.said[-1:]}")

t = tm.create("Обещание", "Сделай таблицу продаж")
ok(wait_for(lambda: t.status in ("done", "failed")) and t.status == "done", f"«Обещание» готова, когда файл появился ({t.status})")
ok("продажи.csv" in after("Обещание", 1) and "нет на диске" in after("Обещание", 1), "назван файл, которого нет, — итог не принят")

t = tm.create("Лаба", "Посчитай сумму скриптом")
ok(wait_for(lambda: t.status in ("done", "failed")) and t.status == "done", f"«Лаба» готова ({t.status}; {t.data.get('error', '')})")
ok("Лаборатория/calc.py" in after("Лаба", 2), f"list_files видит файл «Лаборатории»: {after('Лаба', 2)[-200:]!r}")
ok(any("Лаборатория/calc.py" in c for c in crit), "самопроверка видит файл «Лаборатории»")

t = tm.create("Молчунья", "Посмотри файлы")
ok(wait_for(lambda: t.status in ("done", "failed")), f"«Молчунья» остановилась ({t.status})")
ok(t.status == "failed" and "не выполнено" in t.data.get("error", ""), f"остановка «сама перестала действовать» — не «готово»: {t.status} {t.data.get('error', '')[:90]}")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
