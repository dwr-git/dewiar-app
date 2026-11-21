"""«Чистый разговор» (владелец 21.11: «напрямую с моделью — глубокие ответы, через Лиру — как у 4B»; снимок: на «как дела?» —
15 тыс. знаков правил и 27 действий при трёх репликах разговора). За переключателем llm.talk_lean: беседа — подсказка без правил
действий, из действий — только «запомнить», «дневник» и more_tools; понадобилось дело — модель просит действия, и следующий
шаг идёт с полной подсказкой. Дела, вопросы для инструментов, повелительное наклонение, идущая работа — полная подсказка."""
import asyncio, json, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import talk_lean as TL  # noqa: E402
import modules  # noqa: E402
talk = lambda t: TL.talk_turn(t, [], modules.wanted(t))   # noqa: E731
for t in ("Привет", "Все хорошо, как твои дела?", "Кратко расскажи о себе", "Что думаешь о Достоевском?", "Почему небо синее?",
          "Мне кажется, я выгораю на работе. Как понять, что пора отдохнуть?", "Давай просто поболтаем, мне скучно"):
    ok(talk(t), f"беседа — облегчённо: «{t}»")
for t in ("Напомни купить хлеб", "Какая погода завтра?", "Включи джаз", "Сколько времени?", "Помаши Мише", "Запиши: молоко, яйца",
          "Найди рецепт борща", "Позвони маме", "Сколько я потратил за неделю?", "Как добавить напоминание в приложении?",
          "Я сделал зарядку", "Открой ютуб"):
    ok(not talk(t), f"дело или вопрос для действия — полная подсказка: «{t}»")
ok(not TL.talk_turn("как дела?", [{"role": "assistant", "content": "Включила радио (выполнено инструментами: play_radio)"}], set()),
   "идёт работа (действия в последних репликах) — полная подсказка")
ls = TL.lean_specs([{"name": n, "description": "d"} for n in ("set_reminder", "remember", "web_search", "write_diary", "more_tools")])
ok([x["name"] for x in ls] == ["remember", "write_diary", "more_tools"] and "core —" in ls[-1]["description"],
   f"в беседе — «запомнить», «дневник» и просьба действий (с группой core): {[x['name'] for x in ls]}")

MOCK = r"""
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
OUT = sys.argv[2]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"data":[{"id":"chat"}]}')
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        names = sorted((t.get("function") or {}).get("name") for t in body.get("tools") or [])
        last = body["messages"][-1]
        with open(OUT, "a") as f:
            f.write(json.dumps({"names": names, "sys": body["messages"][0]["content"], "last": last.get("role")}, ensure_ascii=False) + "\n")
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        def say(t):
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": t}}]}, ensure_ascii=False) + "\n\n").encode())
        def call(n, a):
            tc = {"index": 0, "id": "c1", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"tool_calls": [tc]}}]}) + "\n\n").encode())
        u = str(last.get("content") or "")
        if last.get("role") == "user" and "бодрым" in u and names == ["more_tools", "remember", "write_diary"]:
            call("more_tools", {"packs": ["music"]})
        elif last.get("role") == "tool" and "Добавлены" in u:
            call("play_radio", {"query": "бодрое"}) if "play_radio" in names else say("Не нашла радио.")
        elif last.get("role") == "tool":
            say("Включила бодрое радио.")
        else:
            say("Всё спокойно, слушаю тебя.")
        self.wfile.write(b"data: [DONE]\n\n")
ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
"""


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
UP, PORT = free(), free()
(tmp / "mock.py").write_text(MOCK)
BODIES = tmp / "bodies.jsonl"
mock = subprocess.Popen([sys.executable, str(tmp / "mock.py"), str(UP), str(BODIES)])
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False},
    "llm": {"active": "mock", "talk_lean": True, "profiles": {"mock": {"name": "Проба", "kind": "openai",
                                                                      "base_url": f"http://127.0.0.1:{UP}/v1", "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
R = {}


def rows():
    return [json.loads(x) for x in BODIES.read_text(encoding="utf-8").splitlines()] if BODIES.exists() else []


async def session():
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                            stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
    try:
        ws_ = None
        for _ in range(300):
            await asyncio.sleep(0.2)
            if (tmp / "cfg/token").exists():
                try:
                    ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
                except OSError:
                    continue
        await ws_.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
        cnt, answers = [0], []

        async def reader():
            async for raw in ws_:
                e = json.loads(raw)
                if e["type"] == "answer" and e.get("done"):
                    answers.append(e)
        rd = asyncio.ensure_future(reader())

        async def ask(text):
            n, b0 = len(answers), len(rows())
            cnt[0] += 1
            await ws_.send(json.dumps({"id": cnt[0], "cmd": "say", "args": {"text": text}}))
            for _ in range(400):
                if len(answers) > n:
                    break
                await asyncio.sleep(0.05)
            await asyncio.sleep(1.2)
            mine = [r for r in rows()[b0:] if r["last"] in ("user", "tool") and r["names"] and r["names"] != ["get_time"]]
            return (answers[n].get("text") if len(answers) > n else ""), mine
        R["talk"] = await ask("Как твои дела?")
        R["deed"] = await ask("Найди, что пишут о новом фильме Нолана")
        R["esc"] = await ask("Мне бы взбодриться чем-нибудь бодрым")
        rd.cancel()
        await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()


try:
    asyncio.run(session())
    a, rq = R["talk"]
    ok(rq and rq[0]["names"] == ["more_tools", "remember", "write_diary"] and "СЛОВА НЕ ДЕЙСТВУЮТ" not in rq[0]["sys"]
       and "Сейчас — просто разговор" in rq[0]["sys"], f"«как дела?» — без правил действий, 3 действия: {rq[0]['names'] if rq else None}")
    a2, rq2 = R["deed"]
    ok(rq2 and "web_search" in rq2[0]["names"] and "СЛОВА НЕ ДЕЙСТВУЮТ" in rq2[0]["sys"], "просьба-дело — полная подсказка и все действия")
    ok(rq and rq2 and len(rq[0]["sys"]) < len(rq2[0]["sys"]) * 0.75, f"беседа — подсказка заметно легче: {len(rq[0]['sys']) if rq else 0} против {len(rq2[0]['sys']) if rq2 else 0}")
    a3, rq3 = R["esc"]
    ok(len(rq3) >= 2 and rq3[0]["names"] == ["more_tools", "remember", "write_diary"] and "play_radio" in rq3[1]["names"]
       and "СЛОВА НЕ ДЕЙСТВУЮТ" in rq3[1]["sys"], f"беседа, а понадобилось дело — модель попросила действия, следующий шаг с полной подсказкой: {[r['names'][:4] for r in rq3]}")
    ok("бодрое" in (a3 or "").lower() or "радио" in (a3 or "").lower(), f"и дело сделано: {a3!r}")
finally:
    mock.terminate()
    shutil.rmtree(tmp, ignore_errors=True)
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} не прошло")
sys.exit(1 if fails else 0)
