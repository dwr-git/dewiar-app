"""Аудит кэша начала запроса (идея №5 «Голос без пауз», 04.11).

vLLM (APC), llama.cpp, LM Studio, Ollama и Claude переиспользуют уже прочитанное начало запроса, только если оно байт в
байт то же. У Qwen шаблон чата кладёт описания инструментов ПОСЛЕ системной подсказки, в тот же блок:
    <|im_start|>system\\n{подсказка}\\n\\n# Tools … <tools>{инструменты}</tools><|im_end|>\\n<|im_start|>user …
— значит, любая мелочь, что меняется в подсказке (время, память, счётчик дел, путь к папке), ломает кэш и всех
инструментов после неё: на облаке Dewiar это ~16 тыс. токенов prefill на каждый вопрос.

Скрипт поднимает настоящее ядро (с заглушкой модели, которая пишет запросы целиком) для двух разных людей, задаёт
вопросы разного рода (привет, стихи, совет фильма, схема, грубость, даты, «запомни…», «я купил хлеб»), между ними
меняет память, и показывает, с какого знака начало запроса расходится — в подсказке, в инструментах и в сборке «как у
Qwen». Запуск:  python3 tools/prefix_audit.py  [--json файл]
Его же зовёт проверка tests/prefix_cache1104_test.py (функция audit())."""
import asyncio, json, os, re, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

QUESTIONS = ("Привет, как дела?", "Напиши стих про осень", "Посоветуй хороший фильм на вечер",
             "Нарисуй схему, как устроен круговорот воды", "Ты тупая железка", "Сколько дней до нового года?",
             "Запомни, что я люблю крепкий чай", "Я купил хлеб, отметь", "Расскажи короткий анекдот")


def _free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _sse(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode()


class _Mock(BaseHTTPRequestHandler):
    """Сервер модели: пишет каждый запрос целиком; «запомни» → remember, «купил хлеб» → mark_done, иначе — короткий текст."""
    log = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "mock"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        _Mock.log.append(body)
        msgs = body.get("messages") or []
        last = msgs[-1] if msgs else {}
        txt = last.get("content") if isinstance(last.get("content"), str) else ""
        tools = {t["function"]["name"] for t in body.get("tools") or []}
        call = None
        if last.get("role") == "user":
            if "Запомни, что я люблю" in txt and "remember" in tools:
                call = ("remember", {"fact": "Любит крепкий чай"})
            elif "купил хлеб" in txt and "mark_done" in tools:
                call = ("mark_done", {"items": ["Купить хлеб"]})
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        if call:
            self.wfile.write(_sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "type": "function",
                                                                          "function": {"name": call[0], "arguments": json.dumps(call[1], ensure_ascii=False)}}]}}]}))
            self.wfile.write(_sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}))
        else:
            self.wfile.write(_sse({"choices": [{"delta": {"content": "Хорошо, вот ответ."}}]}))
            self.wfile.write(_sse({"choices": [{"delta": {}, "finish_reason": "stop"}],
                                   "usage": {"prompt_tokens": 100, "completion_tokens": 5,
                                             "prompt_tokens_details": {"cached_tokens": 60}}}))
        self.wfile.write(b"data: [DONE]\n\n")


def tools_json(tools):
    return "\n".join(json.dumps(t, ensure_ascii=False, sort_keys=False) for t in tools or [])


def render(body):
    """Запрос — строкой, как его соберёт шаблон Qwen: подсказка, за ней инструменты, потом сообщения."""
    msgs = body.get("messages") or []
    sys_ = msgs[0]["content"] if msgs and msgs[0].get("role") == "system" else ""
    out = "<|im_start|>system\n" + sys_
    if body.get("tools"):
        out += "\n\n# Tools\n<tools>\n" + tools_json(body["tools"]) + "\n</tools>"
    out += "<|im_end|>\n"
    for m in msgs[1:] if sys_ else msgs:
        c = m.get("content")
        c = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
        out += f"<|im_start|>{m.get('role')}\n{c or ''}"
        if m.get("tool_calls"):
            out += json.dumps(m["tool_calls"], ensure_ascii=False)
        out += "<|im_end|>\n"
    return out


def common(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _ctx(s, i, w=70):
    return s[max(0, i - w):i].replace("\n", "⏎") + " ‖ " + s[i:i + w].replace("\n", "⏎")


def _run_core(name, ws_extra=None, questions=QUESTIONS, settings_extra=None, files=None):
    """Ядро для одного человека; -> список запросов с инструментами (по вопросу — первый шаг).
    files — {путь в папке ассистента: текст} (заметки — чтобы нашлось «Вспомнил из записей»); в questions можно
    вставить команду студии словарём {"cmd", "args"} — её ответ ждём, запроса к модели она не даёт."""
    tmp = Path(tempfile.mkdtemp(prefix="dw-prefix-"))
    port, llm = _free(), _free()
    _Mock.log = []
    srv = ThreadingHTTPServer(("127.0.0.1", llm), _Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    (tmp / "cfg").mkdir()
    ws = tmp / ("ws-" + name)
    (ws / "Память").mkdir(parents=True)
    (ws / "Память/Обо мне.md").write_text(f"# Обо мне\n\n- Меня зовут {name}.\n" + (ws_extra or ""), encoding="utf-8")
    for rel, txt in (files or {}).items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt, encoding="utf-8")
    st = {"persona": "lira", "user_name": name, "stt": {"engine": "vosk"}, "tts": {"engine": "off"},
          "audio": {"sounds": False, "follow_up_seconds": 0}, "ui": {"welcome": "done", "intro": "done"},
          "llm": {"active": "m", "tools_modes": {}, "profiles": {"m": {"name": "mock", "kind": "openai",
                                                                     "base_url": f"http://127.0.0.1:{llm}/v1", "model": "chat"}}}}
    for k, v in (settings_extra or {}).items():
        st.setdefault(k, {}).update(v) if isinstance(v, dict) else st.__setitem__(k, v)
    (tmp / "cfg/settings.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(port),
               DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(ws), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(ROOT / "tests/silence90.wav"), "--null-audio"],
                            env=env, stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
    import websockets
    marks = []

    async def go():
        ws_ = None
        for _ in range(300):
            await asyncio.sleep(0.2)
            if (tmp / "cfg/token").exists():
                try:
                    ws_ = await websockets.connect(f"ws://127.0.0.1:{port}", max_size=None); break
                except OSError:
                    continue
        await ws_.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
        events, replies, cnt = [], {}, [0]

        async def reader():
            async for raw in ws_:
                e = json.loads(raw)
                if e["type"] == "reply":
                    replies[e["id"]] = e
                elif e["type"] != "level":
                    events.append(e)
        rd = asyncio.ensure_future(reader())
        await asyncio.sleep(2)
        for q in questions:
            if isinstance(q, dict):                # команда студии между вопросами: {"cmd": …, "args": {…}}
                cnt[0] += 1
                await ws_.send(json.dumps({"id": cnt[0], "cmd": q["cmd"], "args": q.get("args") or {}}))
                end = time.monotonic() + 10
                while time.monotonic() < end and cnt[0] not in replies:
                    await asyncio.sleep(0.1)
                continue
            events.clear()
            marks.append((q, len(_Mock.log)))
            cnt[0] += 1
            await ws_.send(json.dumps({"id": cnt[0], "cmd": "say", "args": {"text": q}}))
            end = time.monotonic() + 25
            while time.monotonic() < end and not any(e["type"] == "answer" and e.get("done") for e in events):
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.4)
        rd.cancel()
        await ws_.close()
    try:
        asyncio.run(go())
    finally:
        core.terminate()
        try:
            core.wait(10)
        except Exception:  # noqa: BLE001
            core.kill()
        srv.shutdown()
    log = list(_Mock.log)
    out = []
    for i, (q, at) in enumerate(marks):
        nxt = marks[i + 1][1] if i + 1 < len(marks) else len(log)
        first = next((b for b in log[at:nxt] if b.get("tools") and (b.get("messages") or [{}])[0].get("role") == "system"
                      and len(b["messages"][0]["content"]) > 2000), None)
        if first:
            out.append({"q": q, "body": first})
    return out, (tmp / "core.log").read_text(encoding="utf-8", errors="replace")


def compare(a, b):
    """Два запроса -> где расходятся подсказка, инструменты и сборка «как у Qwen» (без последнего сообщения)."""
    sa, sb = a["messages"][0]["content"], b["messages"][0]["content"]
    ta, tb = tools_json(a.get("tools")), tools_json(b.get("tools"))
    # последнее сообщение (вопрос со справкой) всегда своё — сравниваем всё до него
    ra = render(dict(a, messages=a["messages"][:-1]))
    rb = render(dict(b, messages=b["messages"][:-1]))
    cs, ct, cr = common(sa, sb), common(ta, tb), common(ra, rb)
    return {"sys": cs, "sys_len": max(len(sa), len(sb)), "sys_at": "" if sa == sb else _ctx(sa, cs),
            "tools": ct, "tools_len": max(len(ta), len(tb)), "tools_at": "" if ta == tb else _ctx(ta, ct),
            "tool_names_same": [t["function"]["name"] for t in a.get("tools") or []] == [t["function"]["name"] for t in b.get("tools") or []],
            "render": cr, "render_len": min(len(ra), len(rb)), "render_sys_tools": len(render(dict(a, messages=a["messages"][:1]))),
            "render_at": "" if ra == rb else _ctx(ra, cr)}


def audit(questions=QUESTIONS):
    """-> {"one": [сравнения соседних вопросов одного человека], "two": сравнение двух людей, "reqs": …}."""
    r1, log1 = _run_core("Михаил", "- Живёт в Минске.\n", questions)
    r2, _ = _run_core("Анна", "- Работает учителем.\n- Любит кошек.\n", questions[:1])
    one = [dict(compare(r1[i - 1]["body"], r1[i]["body"]), q=r1[i]["q"]) for i in range(1, len(r1))]
    two = compare(r1[0]["body"], r2[0]["body"]) if r1 and r2 else None
    return {"one": one, "two": two, "reqs": r1, "reqs2": r2, "log": log1}


def _pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "—"


def main():
    res = audit()
    print("Один человек, вопрос за вопросом (общее начало с прошлым запросом):")
    for c in res["one"]:
        print(f"  «{c['q']}»: подсказка {c['sys']}/{c['sys_len']} ({_pct(c['sys'], c['sys_len'])}), "
              f"инструменты {c['tools']}/{c['tools_len']} ({_pct(c['tools'], c['tools_len'])}), "
              f"как у Qwen {c['render']}/{c['render_len']} ≈ {c['render'] // 3} ток.")
        if c["sys_at"]:
            print("      подсказка расходится:", c["sys_at"])
        if c["tools_at"]:
            print("      инструменты расходятся:", c["tools_at"])
    t = res["two"]
    if t:
        print(f"Два разных человека: подсказка {t['sys']}/{t['sys_len']} ({_pct(t['sys'], t['sys_len'])}), "
              f"инструменты {t['tools']}/{t['tools_len']}, как у Qwen {t['render']} из {t['render_sys_tools']} "
              f"(подсказка+инструменты) ≈ {t['render'] // 3} ток.")
        print("      расходится:", t["render_at"])
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps({k: v for k, v in res.items() if k != "log"},
                                                                         ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "core"))
    main()
