"""Идея №171 (10.11, Илья): «при прямом подключении к модели по IP поток ответа регулярно обрывается посреди генерации,
хотя запрос завершается 200». Поддельный сервер режет поток в неудобных местах — посреди «data:», посреди русской буквы,
между \\r и \\n, — шлёт «: ping», поля SSE id/retry/event, «data:» без пробела, мусорную строку «data: keep-alive»,
неверный charset в заголовке, закрывает соединение без завершающего куска. Ответ должен прийти целиком; настоящий обрыв
(без конца ответа) — по-прежнему ошибка, а не «целый» ответ. Модели по голому IP ждём, как своей (600 с, не 180)."""
import json, os, socket, sys, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import llm  # noqa: E402

TEXT = "Привет! Ёжик съел щётку — это «пример» 🙂 с эмодзи и буквами: жщъ."


def ev(content=None, finish=None):
    d = {"choices": [{"index": 0, "delta": {"content": content} if content is not None else {}, "finish_reason": finish}]}
    return json.dumps(d, ensure_ascii=False)


def body(kind):
    words = [TEXT[i:i + 5] for i in range(0, len(TEXT), 5)]
    out = "id: 0\r\nretry: 3000\r\n\r\n: ping\r\n\r\n"
    for i, w in enumerate(words):
        sep = "data:" if i % 3 == 0 else "data: "                     # «data:» без пробела
        out += (f"event: message\r\nid: {i + 1}\r\n" if i % 4 == 1 else "") + sep + ev(w) + "\r\n\r\n"
        if i == 2:
            out += "data: keep-alive\r\n\r\n: ping\r\n\r\n"              # мусорная строка посреди потока
        if i == 5:
            out += "\r\n\r\n"                                             # лишние пустые строки
    out += "data: " + ev(finish="stop") + "\r\n\r\n"
    if kind != "nodone":
        out += "data: [DONE]\r\n\r\n"
    return out.encode("utf-8")


def cut(b):
    """Нарезать байты в неудобных местах: посреди букв, посреди «data:», между \\r и \\n."""
    out, i, sizes = [], 0, [1, 2, 3, 7, 5, 1, 11, 4]
    k = 0
    while i < len(b):
        n = sizes[k % len(sizes)]; k += 1
        out.append(b[i:i + n]); i += n
    return out


MODE = {"v": "ok"}


def serve(conn):
    try:
        req = b""
        while b"\r\n\r\n" not in req:
            d = conn.recv(65536)
            if not d:
                return
            req += d
        head, _, rest = req.partition(b"\r\n\r\n")
        ln = int(next((l.split(b":")[1] for l in head.split(b"\r\n") if l.lower().startswith(b"content-length")), b"0"))
        while len(rest) < ln:
            rest += conn.recv(65536)
        if not head.startswith(b"POST"):
            conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 27\r\nConnection: close\r\n\r\n{"data": [{"id": "m"}]}    ')
            return
        mode = MODE["v"]
        ctype = b"text/event-stream; charset=iso-8859-1" if mode == "charset" else b"text/event-stream"
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: " + ctype + b"\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
        b = body("nodone" if mode in ("close", "broken") else "ok")
        if mode == "broken":
            b = b[:len(b) // 2]                                           # оборвалось посреди ответа, конца нет
        for c in cut(b):
            conn.sendall(b"%x\r\n" % len(c) + c + b"\r\n")
            time.sleep(0.002)
        if mode not in ("close", "broken"):
            conn.sendall(b"0\r\n\r\n")
    finally:
        conn.close()


srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", 0)); srv.listen(8)
PORT = srv.getsockname()[1]


def loop():
    while True:
        c, _ = srv.accept()
        threading.Thread(target=serve, args=(c,), daemon=True).start()


threading.Thread(target=loop, daemon=True).start()
P = {"kind": "openai", "base_url": f"http://127.0.0.1:{PORT}/v1", "model": "m", "api_key": "x", "max_tokens": 200}


def ask():
    return "".join(llm.stream_chat(dict(P), "Ты помощник.", [{"role": "user", "content": "Скажи привет"}]))


for mode, what in (("ok", "поток порезан посреди букв, «data:», \\r|\\n; ping, id/retry/event, «data:» без пробела, мусорная строка"),
                   ("charset", "сервер написал чужой charset (iso-8859-1) — буквы всё равно целые"),
                   ("close", "конец ответа (finish_reason) и закрыл соединение без завершающего куска и без [DONE]")):
    MODE["v"] = mode
    try:
        got = ask()
    except Exception as e:  # noqa: BLE001
        got = f"ОШИБКА: {e}"
    ok(got.strip() == TEXT, f"{what}: ответ целиком ({got[:60]!r}…)")

MODE["v"] = "broken"
try:
    got = ask(); err = ""
except Exception as e:  # noqa: BLE001
    got, err = "", str(e)
ok(bool(err) or got.strip() != TEXT, f"настоящий обрыв посреди ответа — не выдаём за целый ответ ({err[:80] or got[:40]!r})")

# строки — сами, всегда UTF-8, \r\n на стыке кусков — один конец строки
lines = list(llm.sse_lines([b"data: \xd0", b"\x9f\xd1\x80\xd0\xb8\r", b"\ndata: x\r", b"\r\n", b": ping\n\nlast"]))
ok(lines == ["data: При", "data: x", "", ": ping", "", "last"], f"sse_lines: буквы, \\r|\\n и \\r\\r\\n на стыках: {lines}")
c = llm._Collector()
for ln in ["data: keep-alive", "", 'data: {"choices":[{"delta":{"content":"А"}}]}', "id: 5", 'data: {"choices":[{"delta":{"content":"Б"}}]}']:
    c.feed_line(ln)
ok(c.tags.tail() is not None, "разбор строк без исключений")
c2 = llm._Collector(); out = ""
for ln in ["data: {\"choices\": [{\"delta\":", "", 'data: {"choices":[{"delta":{"content":"ок"}}]}']:
    out += c2.feed_line(ln)
ok("ок" in out + c2.flush(), f"оборванный кусок события не отравляет следующие: {out!r}")
ok(llm._ip_base("http://100.122.67.91:11434/v1") and llm._ip_base("http://5.6.7.8:8000/v1") and not llm._ip_base("https://api.openai.com/v1"),
   "модель по голому IP — своя: ждём между словами до 10 минут")
# рецензия 0.87: линейное время, предел строки, «Стоп» посреди длинной строки, ограниченный pending
t0 = time.time(); n = sum(1 for _ in llm.sse_lines(b"a" * 4096 for _ in range(4096)))
ok(time.time() - t0 < 2 and n == 0, f"16 МБ без перевода строки — быстро и выброшено целиком ({time.time() - t0:.2f} с, строк {n})")
big = [b"data: " + b"x" * 5000, b"y" * 5000 + b"\r", b"\ndata: ok\n"]
ok(list(llm.sse_lines(big, limit=4096)) == ["data: ok"], "строка длиннее предела выброшена до своего конца, следующая — целая")
ev = threading.Event(); got = []


def gen():
    for i in range(100000):
        if i == 50:
            ev.set()
        yield b"z" * 4096


t0 = time.time(); got = list(llm.sse_lines(gen(), cancel=ev))
ok(time.time() - t0 < 1 and got == [], f"«Стоп» посреди длинной строки — сразу ({time.time() - t0:.2f} с)")
c3 = llm._Collector(); t0 = time.time(); c3.feed_line('{"message":{"content":"')
for _ in range(50000):
    c3.feed_line("a" * 20)
ok(time.time() - t0 < 2 and len(c3.pending) <= llm._Collector.PENDING_MAX, f"1 МБ JSON по 20 байт — быстро, pending ограничен ({time.time() - t0:.2f} с)")
c4 = llm._Collector(); out = ""
for ln in ['{', '  "choices": [{"delta": {"content": "целиком"}}]', '}']:
    out += c4.feed_line(ln)
ok("целиком" in out + c4.flush(), f"JSON, разбитый на строки, по-прежнему разбирается: {out!r}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
