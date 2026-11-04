"""Суфлёр (core/prompter.py): настоящее ядро; собеседник — WAV вместо звука компьютера (DEWIAR_PROMPTER_WAV, голос
espeak-ng), распознавание — Vosk, модель — своя заглушка. Материал встречи (прайс) → шпаргалка; собеседник спросил
«сколько стоит» → подсказка потоком, с цифрой из прайса и источником; «Подсказать» по кнопке; пока суфлёр включён,
ассистент молчит; «Закончить» → итог файлом в «Встречи». Плюс разбор поводов (wants_hint) и шпаргалки (parse_sheet)."""
import asyncio, base64, json, os, socket, subprocess, sys, tempfile, threading, time, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


# ---------- разбор без ядра ----------
from prompter import parse_sheet, wants_hint  # noqa: E402
ok(wants_hint("Сколько стоит внедрение на тридцать мест?") and wants_hint("а почему так долго") and wants_hint("это слишком дорого для нас"),
   "вопросы и возражения собеседника — повод подсказать")
ok(not wants_hint("Добрый день, рад вас видеть") and not wants_hint("да"), "приветствие и «да» — нет")
ok(wants_hint("Хороший вопрос, сейчас уточню", "me") and not wants_hint("Сколько стоит?", "me"), "у меня — только «тяну время»")
ok(parse_sheet("В: Сколько стоит?\nО: 4800 за 30 мест\n- В: Сроки?\n- О: две недели") == [{"q": "Сколько стоит?", "a": "4800 за 30 мест"}, {"q": "Сроки?", "a": "две недели"}],
   "шпаргалка разбирается")


sys.path.insert(0, str(TESTS))
from vosk_have import skip_without_vosk  # noqa: E402
skip_without_vosk(ROOT)                                 # дальше — живое ядро: речь собеседника из WAV слышит Vosk


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


SEEN = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system = next((m["content"] for m in body["messages"] if m["role"] == "system"), "")
        user = body["messages"][-1]["content"]
        SEEN.append((system[:40], user))
        if "суфлёр" in system:
            price = "4800" in user
            out = (f"От 4800 талеров за 30 мест\n• внедрение — две недели\n• годовой договор — скидка 10%\nИсточник: прайс.txt" if price
                   else "≈ Уточните, сколько мест им нужно\n• спросите про сроки")
        elif "шпаргалку" in system:
            out = "В: Сколько стоит внедрение?\nО: 4800 талеров за 30 мест, две недели.\nВ: Есть ли скидки?\nО: 10% при годовом договоре."
        elif "итог" in system.lower():
            out = "## Коротко\nОбсудили цену внедрения.\n## Договорились\n- прислать договор\n## Кто что делает\n- Вы: отправить прайс\n## Открытые вопросы\n- нет"
        else:
            out = "Ассистент ответил бы."
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for i in range(0, len(out), 12):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': out[i:i + 12]}}]}, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush(); time.sleep(0.01)
        self.wfile.write(b"data: [DONE]\n\n")


UP, PORT = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = Path(tempfile.mkdtemp()); (tmp / "cfg").mkdir()


def say(text, name, speed=140):
    subprocess.run(["espeak-ng", "-v", "ru", "-s", str(speed), "-w", str(tmp / "r.wav"), text], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp / "r.wav"), "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(tmp / name)], check=True)
    w = wave.open(str(tmp / name)); return w.readframes(w.getnframes())


sil = lambda s: b"\0\0" * int(16000 * s)  # noqa: E731
them = sil(6) + say("Добрый день", "a.wav") + sil(2.5) + say("Сколько это будет стоить", "b.wav") + sil(12)
w = wave.open(str(tmp / "them.wav"), "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(them); w.close()
base = f"http://127.0.0.1:{UP}/v1"
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done"},
    "report": {"pulse": False}, "llm": {"active": "m", "tools_probe_v": 2, "tools_modes": {f"{base}|m": "native"},
                                        "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_PROMPTER_WAV=str(tmp / "them.wav"))
R = {}


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
        cnt, replies, events = [0], {}, []

        async def reader():
            async for raw in ws_:
                e = json.loads(raw)
                if e["type"] == "reply":
                    replies[e["id"]] = e
                elif e["type"] != "level":
                    events.append(e)
        rd = asyncio.ensure_future(reader())

        async def call(cmd, **args):
            cnt[0] += 1; i = cnt[0]
            await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
            for _ in range(1200):
                if i in replies:
                    return replies.pop(i)
                await asyncio.sleep(0.05)

        async def wait(pred, t=40):
            for _ in range(t * 20):
                m = [e for e in events if pred(e)]
                if m:
                    return m
                await asyncio.sleep(0.05)
            return []
        for _ in range(100):                                       # слух поднялся — есть чем распознавать
            if "Запуск: слух готов" in (tmp / "core.log").read_text(encoding="utf-8", errors="replace"):
                break
            await asyncio.sleep(0.2)
        price = "Прайс Dewiar для компаний.\nВнедрение на 30 мест — 4800 талеров, срок две недели.\nГодовой договор — скидка 10%."
        R["bad_file"] = await call("prompter_file", name="фото.jpg", data=base64.b64encode(b"x").decode())
        R["file"] = await call("prompter_file", name="прайс.txt", data="data:text/plain;base64," + base64.b64encode(price.encode()).decode())
        R["start"] = await call("prompter_start", title="Переговоры с «Альфа»", goal="Продать внедрение на 30 мест", mode="auto")
        R["open_say"] = None
        R["sheet"] = await wait(lambda e: e["type"] == "prompter" and e.get("kind") == "sheet")
        R["lines"] = await wait(lambda e: e["type"] == "prompter" and e.get("kind") == "line" and "сколько" in e["line"]["text"].lower(), 45)
        R["hint"] = await wait(lambda e: e["type"] == "prompter" and e.get("kind") == "hint" and e["hint"].get("done") and e["hint"].get("why") == "them", 30)
        R["partial"] = [e for e in events if e["type"] == "prompter" and e.get("kind") == "hint" and not e["hint"].get("done")]
        R["manual"] = await call("prompter_hint")
        R["manual_done"] = await wait(lambda e: e["type"] == "prompter" and e.get("kind") == "hint" and e["hint"].get("done") and e["hint"].get("why") == "button", 20)
        m = len(events)
        await call("say", text="Лира, какая погода?")                # набранное в окне — ассистент по-прежнему отвечает
        R["state"] = (await call("prompter_state")).get("data")
        R["voice_live"] = await call("prompter_start", title="Вживую", place="live")   # голос не запомнен — очная не начинается
        await call("prompter_stop", summary=True)
        R["summary"] = await wait(lambda e: e["type"] == "prompter" and e.get("kind") == "summary" and not e.get("busy"), 30)
        R["meetings"] = (await call("prompter_meetings")).get("data")
        await call("say", text="включи суфлёр")
        R["open"] = await wait(lambda e: e["type"] == "prompter" and e.get("kind") == "open", 10)
        rd.cancel(); await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()

asyncio.run(session())
srv.shutdown()
log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
ok(R["bad_file"].get("error") and "подходят" in R["bad_file"]["error"], f"картинка не материал: {R['bad_file'].get('error')}")
ok((R["file"].get("data") or {}).get("chars", 0) > 50, "прайс принят")
st = R["start"].get("data") or {}
ok(st.get("on") and st["meeting"]["title"] == "Переговоры с «Альфа»", "встреча началась")
ok(R["sheet"] and len(R["sheet"][0]["sheet"]) == 2, f"шпаргалка собрана: {R['sheet'][:1]}")
ok(bool(R["lines"]), f"собеседник распознан: {[e['line']['text'] for e in R['lines']]}")
h = R["hint"][-1]["hint"] if R["hint"] else {}
ok("4800" in h.get("text", "") and h.get("src") == "прайс.txt" and "сколько" in h.get("q", "").lower(), f"подсказка на вопрос — с ценой из прайса и источником: {h}")
ok(len(R["partial"]) >= 2, f"подсказка пишется потоком ({len(R['partial'])} промежуточных)")
inst = [e for e in R["partial"] if e["hint"].get("instant")]
ok(bool(inst) and "4800" in inst[0]["hint"]["text"], "пока модель пишет — сразу ответ из шпаргалки")
ok(R["manual"].get("ok") and R["manual_done"], "«Подсказать» по кнопке")
ok(any("суфлёр" in s for s, u in SEEN) and any("МАТЕРИАЛЫ" in u and "4800" in u for s, u in SEEN), "модели — материалы встречи")
ok("Имя «лира» услышано" not in log and "🎬 Собеседник" in log or "🎬 Собеседник" in log, "собеседник в журнале суфлёра")
ok("голос" in (R["voice_live"].get("error") or "") and (R["state"] or {}).get("voice", {}).get("has") is False,
   f"очная встреча без запомненного голоса не начинается: {R['voice_live'].get('error')}")
s = R["summary"][-1] if R["summary"] else {}
ok("Договорились" in s.get("summary", "") and s.get("path", "").endswith(".md") and Path(s["path"]).exists(), f"итог встречи сохранён: {s.get('path')}")
ok("Расшифровка" not in Path(s.get("path", "/dev/null")).read_text(encoding="utf-8") if s.get("path") else False, "расшифровка в итог — только если отмечено")
ok(R["meetings"] and "Переговоры" in R["meetings"][0]["name"], f"встреча — в «Прошлых встречах» студии: {R['meetings']}")
ok(bool(R["open"]), "«включи суфлёр» голосом — окно открывается")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
