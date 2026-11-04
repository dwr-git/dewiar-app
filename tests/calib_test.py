"""«Научить имени»: без GigaAM и без сервера. Три раза «Девиар» → Vosk запоминает, как слышит имя →
«Девиар, …» откликается, похожие фразы без имени — нет. Голос — espeak-ng (разные тембры)."""
import asyncio, json, os, subprocess, sys, tempfile, time, wave
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
from vosk_have import skip_without_vosk  # noqa: E402
skip_without_vosk(ROOT)                                 # отпечаток имени снимает модель Vosk
PORT, LLM_PORT = 8789, 8132
tmp = Path(tempfile.mkdtemp()); (tmp / "cfg").mkdir()
def say(text, voice, speed, name):
    subprocess.run(["espeak-ng", "-v", voice, "-s", str(speed), "-w", str(tmp / "r.wav"), text], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp / "r.wav"), "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(tmp / name)], check=True)
    w = wave.open(str(tmp / name)); return w.readframes(w.getnframes())
sil = lambda s: b"\0\0" * int(16000 * s)
# тренируем одним голосом, проверяем — им же и чуть другим темпом (так ведёт себя живой человек)
V = os.environ.get("VOICE", "ru")
parts = [sil(4)] + [x for i, sp in enumerate((150, 160, 145)) for x in (say("Девиар", V, sp, f"t{i}.wav"), sil(3))]
BARGE = os.environ.get("SCENARIO") == "barge"
if BARGE:
    parts += [sil(3), say("Патрик, расскажи сказку", V, 150, "p.wav"), sil(5),
              say("Девиар, подожди, расскажи лучше про космос и звёзды", V, 145, "b.wav"), sil(9)]
parts += [sil(3), say("Девиар, сколько будет два плюс два", V, 155, "q.wav"), sil(7),
          say("Деревья шумят за окном", V, 155, "n1.wav"), sil(4), say("Девушка пришла домой", V, 155, "n2.wav"), sil(4),
          say("Мы видели вчера закат", V, 155, "n3.wav"), sil(6)]
w = wave.open(str(tmp / "scn.wav"), "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"".join(parts)); w.close()
# имени «Девиар» нет в словаре Vosk — им и проверяем узнавание имён без словаря (свой персонаж; главный — «Агент»)
(tmp / "cfg/personas").mkdir(parents=True, exist_ok=True)
(tmp / "cfg/personas/deviar.json").write_text(json.dumps({"name": "Девиар", "gender": "male", "wake": ["девиар"], "style": "nexus",
    "character": "Тебя зовут Девиар. Ты внимательный помощник."}, ensure_ascii=False), encoding="utf-8")
(tmp / "cfg/settings.json").write_text(json.dumps({"persona": "deviar", "stt": {"engine": "vosk"}, "tts": {"engine": "espeak"},
    "audio": {"sounds": False, "follow_up_seconds": 0},
    "llm": {"active": "t", "profiles": {"t": {"name": "Mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM_PORT}/v1"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1")
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM_PORT)])
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(tmp / "scn.wav"), "--null-audio"], env=env, stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
events = []
async def run():
    for _ in range(100):
        await asyncio.sleep(0.2)
        if (tmp / "cfg/token").exists():
            try: ws = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError: continue
    await ws.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
    started = False
    t0 = time.monotonic()
    async for raw in ws:
        e = json.loads(raw)
        if e["type"] == "level": continue
        events.append(e)
        if not started and e["type"] == "status" and e["status"].get("input"):
            started = True
            await ws.send(json.dumps({"id": 1, "cmd": "calib_start", "args": {"persona": "deviar"}}))
        if e["type"] == "eof" or time.monotonic() - t0 > 120: break
try: asyncio.run(run())
except Exception as e: print("соединение:", e)
finally:
    core.terminate(); mock.terminate(); core.wait(); mock.wait()
log = (tmp / "core.log").read_text()
print("\n".join(l for l in log.splitlines() if any(k in l for k in ("🎓", "👂", "🎤", "❓", "Отпечаток", "Traceback", "ERROR"))))
done = next((e for e in events if e["type"] == "calib" and e.get("step") == "done"), {})
answers = [e["text"] for e in events if e["type"] == "answer" and e.get("done")]
checks = {
    "три образца записаны": sum(e["type"] == "calib" and e.get("step") == "sample" for e in events) == 3,
    "голосовой отпечаток имени сохранён": bool((done.get("voiceprint") or {}).get("samples") == 3),
    "«Девиар, сколько будет…» — откликнулся и ответил": any(("Девиар" in a and "два плюс два" in a) or "будет 4" in a for a in answers),
    "фразы без имени не разбудили": len(answers) == 1,
    "монитор «что я слышу» получал фразы": sum(e["type"] == "hearing" for e in events) >= 4,
}
if BARGE:
    t_int = next((e for e in events if e["type"] == "interrupted"), None)
    checks = {"Патрик начал рассказывать": any(a.startswith("Жил-был") for a in answers),
              "«Девиар, подожди…» перебил Патрика": t_int is not None,
              # в вопросе нет имени; перед ним — перебитый рассказ Патрика (длинный разговор помнит, что успели сказать)
              "ответил Девиар, в вопросе нет имени": any(a.startswith("Я Девиар") and a.split("сказали:")[-1].split("(меня перебили)")[-1].strip().lower().startswith("подожди") for a in answers)}
print("ОТВЕТЫ:", [a[:80] for a in answers])
for k, v in checks.items(): print(("✅" if v else "❌"), k)
sys.exit(0 if all(checks.values()) else 1)
